"""Ogretim olcumu: kurs OGRENCIYE BIR SEY YAPTIRIYOR MU.

Projedeki diger olculer kursun NASIL GORUNDUGUNU soruyor (tools/rubric.py
bunu acikca yaziyor: "Icerigin dogrulugunu DEGERLENDIRME; yalnizca gorsel
tasarimi"). Bu modul ayri bir soru soruyor ve ONA da bakan kimse yoktu:
ogrenci ilerlemekten baska bir sey yapiyor mu.

Olcu DETERMINISTIK. Sayilan seyler XML'den dogrudan sayilabilir -- kac soru,
kac ardisik okuma slaydi, sonuc slaydi var mi -- dolayisiyla buna LLM yargici
takmak gereksiz: rubric.py'nin ugrastigi sicaklik ve SIRA kararsizligini
bedavaya geri getirirdi.

ETKILESIM TANIMI (kapsam cumlesi asagida makine tarafindan da donuyor):
bir tetikleyici, OGRENCININ GIRDISIYLE baslayip SALT GEZINME olmayan bir is
yapiyorsa ogrenme etkilesimi sayilir. Iki yarisi da gerekli.
"""

from __future__ import annotations

from . import model

# Kullanicinin FIZIKSEL girdisi. Kalanlar (OnStart, OnEnd, OnTimelineEvent,
# OnAnimationComplete, OnMediaComplete, OnEntersSlide, OnLeavesSlide,
# OnVariableValueChange) kendiliginden atesler; ogrenci bir sey yapmis olmaz.
# Kaynak: logic.EVENTS -- olculerek kurulmus liste (tools/event_probe.py).
GIRDI_EVENTS = frozenset({
    "OnClick", "OnDoubleClick", "OnRightClick", "OnMouseHover", "OnHover",
    "OnKeyPress", "OnDrop", "OnIntersect", "OnStopIntersect",
    "OnClicksOutSide", "OnDialTurns", "OnSliderMoves", "OnLostFocus",
    "OnNextButtonClick",
})

# OnStateChange bilerek DISARIDA: o bir TEPKI, girdi degil. Durumu degistiren
# tiklama zaten sayildi; tepkiyi de saymak ayni etkilesimi iki kez sayar.
TEPKI_EVENTS = frozenset({"OnStateChange", "OnVariableValueChange"})

# SALT GEZINME. Ogrenci tikladi ama yaptigi sey "baska bir sayfaya git".
# Menu slaydinin tiklamasi da BURAYA duser: menu, icerik hakkinda degil SIRA
# hakkinda bir secim -- yoksa tek bir menu slaydi butun kursu gecirirdi.
SALT_GEZINME = frozenset({
    "jumpToSlide", "jumpToScene", "jumpToNextSlide", "jumpToPrevSlide",
    "ReviewQuizSL", "exitCourse",
})

# Sonuc slaydinin imzasi: gomulu tohumdaki (seeds/results.xml) kendine ozgu
# tetikleyici ETIKETLERI. Action'a degil tag'e bakiliyor cunku tag yalnizca
# sonuc slaydinda geciyor.
SONUC_TRIG_TAGLARI = frozenset({
    "submitQuizTrig", "reviewQuizTrig", "resetQuizTrig", "gotoFirstInQuizTrig",
})

KAPSAM = (
    "ETKILESIM = kullanici girdisiyle baslayan VE salt gezinme olmayan "
    "tetikleyici; arti uzerinde soru etkilesimi (freePickOne, dragDrop, "
    "textEntry...) bulunan her slayt. "
    "GEZINME BILEREK SAYILMIYOR: jumpToSlide, jumpToScene, jumpToNextSlide, "
    "jumpToPrevSlide, ReviewQuizSL, exitCourse -- MENU TIKLAMASI DA BUNA "
    "DAHIL (menu icerik degil sira secimidir; sayilsaydi tek menu slaydi "
    "butun kursu gecirirdi). "
    "showSubSlide (katman acma) BURADA SAYILIYOR ama audit'in "
    "slides_without_navigation olcutunde GEZINME sayiliyor: iki ayri soru, "
    "iki ayri kume, bilerek paylasilmiyor. "
    "OnStateChange ve OnVariableValueChange TEPKIdir, girdi degil -- onlari "
    "tetikleyen tiklama zaten sayildi. "
    "Sekil durumlari (hover/down) tek basina etkilesim SAYILMAZ: tetikleyicisi "
    "olmayan bir hover, ogrenciden karar istemez. "
    "TETIKLEYICI YAZILDIGI GIBI SAYILIYOR, ATESLEDIGI GIBI DEGIL. 17 event'in "
    "yalnizca 2'si (OnStart, OnVariableValueChange) preview'da tetiklendigi "
    "GORULEREK olculdu; kalan 15 icin kanit 'Storyline cokmuyor' seviyesinde "
    "(JS_YOL_HARITASI.md). Yoldas alan eksikligi yuzunden sessizce calismayan "
    "bir OnDrop burada ETKILESIM olarak sayilir ve calisma aninda hicbir sey "
    "yapmaz. "
    "SIFIR BULGU IYI KURS DEMEK DEGILDIR: bu olcu etkilesimin VARLIGINI sayar, "
    "ogretme degerini olcmez."
)


def _etkilesimli_mi(trig: dict) -> bool:
    return (trig.get("event") in GIRDI_EVENTS
            and trig.get("action") not in SALT_GEZINME
            and trig.get("action", "") != "")


def olc(pkg) -> dict:
    """Kursun ogretim olculeri. Yazmaz, yalnizca sayar."""
    idx = model.slide_index(pkg)          # sahne sirasinda
    trigs = model.triggers(pkg)
    sorular = model.quiz(pkg)

    # --- etkilesimli slayt kumesi
    etkilesimli: set[str] = {t["slide"] for t in trigs if _etkilesimli_mi(t)}
    etkilesimli |= {q["slide"] for q in sorular}

    # --- ardisik etkilesimsiz slayt (kurs okuma sirasinda en uzun seri)
    okuma_sirasi = [(ref.basename, ref.name, ref.scene_name) for ref in idx.values()]
    en_uzun, seri = 0, 0
    en_uzun_seri: list[str] = []
    simdiki: list[str] = []
    for basename, name, scene in okuma_sirasi:
        if basename in etkilesimli:
            seri, simdiki = 0, []
            continue
        seri += 1
        simdiki.append(f"{basename} ({scene})")
        if seri > en_uzun:
            en_uzun, en_uzun_seri = seri, list(simdiki)

    # --- sahne basina soru
    sahne_sirasi: list[str] = []
    for ref in idx.values():
        if ref.scene_name not in sahne_sirasi:
            sahne_sirasi.append(ref.scene_name)
    soru_sayisi = {s: 0 for s in sahne_sirasi}
    for q in sorular:
        soru_sayisi[q["scene"]] = soru_sayisi.get(q["scene"], 0) + 1
    sorusuz = [s for s in sahne_sirasi if soru_sayisi.get(s, 0) == 0]

    # --- sonuc slaydi
    sonuc_slaytlari = sorted({
        t["slide"] for t in trigs
        if t.get("kind") in SONUC_TRIG_TAGLARI
        or t.get("action") in ("SubmitQuizSL", "ResetQuizSL")
    })

    # --- tetikleyici cesitliligi (TANI, KAPI DEGIL -- notu asagida)
    ciftler: dict[tuple[str, str], int] = {}
    for t in trigs:
        anahtar = (t.get("event", ""), t.get("action", ""))
        ciftler[anahtar] = ciftler.get(anahtar, 0) + 1

    return {
        "ardisik_etkilesimsiz_slayt": {
            "en_uzun": en_uzun,
            "toplam_slayt": len(okuma_sirasi),
            "etkilesimli_slayt": len(etkilesimli),
            "seri": en_uzun_seri,
        },
        "sahne_basina_soru": soru_sayisi,
        "sorusuz_sahneler": sorusuz,
        "sonuc_slaydi": sonuc_slaytlari or None,
        "tetikleyici_cesitliligi": {
            "ayrik_cift": len(ciftler),
            "toplam_tetikleyici": len(trigs),
            "ciftler": [
                {"event": e, "action": a, "adet": n}
                for (e, a), n in sorted(ciftler.items(), key=lambda kv: -kv[1])
            ],
            "not": ("TANI, KAPI DEGIL. Cesitlilik ogretmeyle ozdes degil: "
                    "susleme amacli hover tetikleyicileri bu sayiyi yukseltir "
                    "ve hicbir sey ogretmez; tersine, bastan sona soru olan "
                    "bir kursun cesitliligi dusuk cikabilir. Sayi, etkilesim "
                    "rakaminin NEDENINI acikliyor, kendi basina bir yargi "
                    "degil."),
        },
        "ogretim_kapsam": KAPSAM,
    }
