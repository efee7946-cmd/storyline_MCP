"""Kurs İŞLEVSEL olarak eksiksiz mi? Brief ne istedi, dosyada karşılığı var mı?

Bugune kadar kurulan her olcu GEOMETRIK ya da RENKSEL: konum, boyut, taban,
kontrast. Hicbiri "bu kurs calisir mi" diye sormuyor. Uretilmis bir kursta
bulunan on kusurun ikisi tam olarak oradan geldi ve ikisi de estetik degil:

    sinavin puanlanmamasi   LMS'e skor gitmez
    ilk slaydin bos olmasi  ogrencinin gordugu ilk ekran bos

Hicbir yapisal kontrol bunlari goremez: dosya gecerli, slaytlar aciliyor,
kutular yerinde. Eksik olan sey VAR OLMAYAN bir sey, ve var olmayan bir seyin
geometrisi olmaz.

IKI AYRI SORU, ikisi de burada:

  ISTENEN vs URETILEN   brief kac bolum, kac soru istedi; dosyada kac tane var
  DEVRALINAN            kaynak dosyada zaten duran ve ele alinmayan sey

Ikincisi olculdugunde sasirtici cikti: bir kursta bulunan 14 bos slaydin ve
15 kopuk tetikleyicinin TAMAMI kaynak sablondan geliyordu. Kurucu kendi
slaytlarini EKLIYOR, kaynakta ne varsa oldugu gibi birakiyor -- ve o da
ogrenciye gidiyor. Kimse saymadigi icin kimse bilmiyordu.

PUANLAMA BIR ZINCIRDIR, ve "soru var" onun yalnizca ilk halkasi. Bu ayrim
olculerek bulundu ve kontrolu bastan yazdirdi: dondurulmus referansta BES
slayt da freePickOneIntr tasiyor, sonuc slaydi da yerinde -- ama
quizMgr/quizLst/quiz/questionIdLst BOS. Yani ogrenci cevapliyor, sayfa
dogru/yanlis diyor, ve skor hicbir yere gitmiyor.

"Etkilesim var mi" diye soran bir kontrol o kursa 5/5 PUANLI der ve gecer.
Tam olarak kacinmaya calisilan hata: kontrolu yazmadan once ne taradigini
bilmek. Uc halka ayri ayri kirilir, o yuzden ayri ayri sorulur:

    1. etkilesim   slaytta INTERACTION_TAGS'ten biri var mi
    2. kayit       slaydin guid'i bir quiz'in questionIdLst'inde mi
    3. hedef       quiz'in resultSldG'si gercek bir slayda cozuluyor mu,
                   ve story duzeyinde lmsResultSlideG dolu mu

POZITIF KONTROL olmadan bunlarin hicbiri soylenemezdi. Gercek, elle yazilmis
bir kursta (test/0_duz_kopya.story) 11 etkilesimin 11'i de kayitli ve iki
kume BIREBIR ortusuyor -- ne kayitsiz soru var, ne sorusuz kayit. Kayitli bir
kursun neye benzedigini gormeden "kayit yok" demek, K1'in ta kendisi olurdu:
bulamadigini yokluk sanmak.

Kayit iki YONLU sorulur (K7): kayitsiz soru skoru kaybeder, sorusuz kayit ise
olmayan bir soruyu izler. Tek yon tutulsaydi digeri sessizce girerdi.

Bu arac hicbir sey SILMEZ. Kullanicinin dosyasindaki slaytlari silmek onun
karari; buranin isi gormunur kilmak.

    python tools/completeness.py kurs.story
    python tools/completeness.py kurs.story --sections 4 --per-section 1
    python tools/completeness.py --kontrol      dedektorun pozitif kontrolu
"""

from __future__ import annotations

import argparse
import re
import sys
import warnings
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from storyline_mcp import authoring, model, shapes
from storyline_mcp.package import StoryPackage

GUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                  r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


# ISARETCILER, KARA LISTEYLE DEGIL BEYAZ LISTEYLE -- ve liste OLCULDU
# (2026-09-06). Kalibrasyon noktasi: INSAN YAPIMI, CALISAN kurslar. Alti
# donor kursu artı elle yapilmis `0_duz_kopya.story` tarandi ve her `*G`
# oznitelıgının kac degerinin pakette cozuldugu sayildi.
#
# IYI KURSTA %100 COZULENLER  (bir basarisizlik GERCEKTEN kirikliktir):
#
#     jumpG      20 / 0      "su slayda/sahneye git"
#     setStateG 132 / 0      "su seklin durumunu degistir"
#     submitG    13 / 0      "su etkilesimi gonder"
#     hideG       8 / 0      "su katmani gizle"
#
# IYI KURSTA BILE COZULMEYENLER (bunlari kirik saymak YANLIS):
#
#     verG        0 / 628    SURUM DAMGASI -- hicbir zaman cozulmez
#     showG     113 / 86     yerlesik/oynatici katmanlarini da gosteriyor
#     actionG    30 / 41     Storyline'in KENDI eylem sabitleri
#     varG      155 / 10     yerlesik degiskenler pakette durmaz
#     varG2      74 / 32     shapeG 90/22, moveG 19/5, motionPathG 19/5
#
# NICIN BEYAZ LISTE. Once kara liste denendi (`g`, `verG`, `copiedG` dislandi)
# ve YETMEDI: calisan bir donor kursu hala 80 "kopuk" gosteriyordu. Sebep,
# testin kendisinin gecersiz olmasi -- Storyline'in pakette DURMAYAN yerlesik
# nesneleri var (yerlesik degiskenler, eylem sabitleri, oynatici katmanlari)
# ve "pakette cozulmuyor" onlar icin kusur demek degil.
#
# BEDELI OLCULDU: eski sayac uretilmis kursta 44 "kopuk" gosteriyordu ve o
# sayi 2026-09-06'da iki kez yanlis teshise goturdu -- bir kez yanlis sinifa
# yazdirdi, bir kez de Storyline'in kendi sabitini "onarmaya" gonderiyordu.
_ISARETCILER = frozenset({"jumpG", "setStateG", "submitG", "hideG"})


def dangling_in_slide(root: ET.Element, known: set) -> list[str]:
    """Hedefi çözülemeyen tetikleyiciler. **Tek otorite.**

    Bu sayi bir donem IKI YERDE hesaplaniyordu ve iki farkli cevap veriyordu:
    completeness 43, inventory 25. Fark bir yuvarlama degildi -- inventory bos
    slaytlarda `continue` edip tetikleyici taramasini hic yapmiyordu, ve
    devralinan donor copu TAM ORADA yasiyor. Yani dusuk sayan surum, kusurun
    en yogun oldugu kesiti atliyordu.

    Bu projede ayni desen daha once de cikti (donors._harvest_file). Iki ayri
    uygulama er ya da gec ayrisir ve ayristiginda hangisinin dogru oldugu
    okunamaz; o yuzden hesap tek yerde durur, cagiranlar buraya sorar.

    Bos slayt ATLANMAZ: slaytta sekil olmamasi tetikleyici olmadigi anlamina
    gelmez -- slaydin kendi <trigLst>'i ve katmanlari yerinde durur.
    """
    out: list[str] = []
    for owner in root.iter():
        trig_list = owner.find("trigLst")
        if trig_list is None:
            continue
        for trig in trig_list:
            kopuk = set()
            for el in trig.iter():
                for ad, deger in el.attrib.items():
                    if ad not in _ISARETCILER:
                        continue
                    if not GUID.fullmatch(deger or ""):
                        continue
                    if deger.startswith("00000000") or deger in known:
                        continue
                    kopuk.add(deger)
            if kopuk:
                out.append(trig.get("evt") or trig.get("name") or "?")
    return out


# ILERI CIKMAZI: ogrenci ILERI'ye basiyor ve hicbir sey olmuyor.
#
# KENDI OKUYUCUSU VAR, `authoring._ileri_datalari`yi CAGIRMIYOR -- ve bu
# bilerek. Kapi, denetledigi kodun yardimcisini kullanirsa o yardimcidaki
# kusuru goremez: yanlis bir "ileri" tanimi hem yazarda hem kapida ayni
# anda yanlis olur ve kapi yesil kalir. Ayni sozlesme `donors._harvest_file`
# ile `completeness.dangling_in_slide` arasindaki ayrimda da yazili.
#
# QUIZ ETIKETLERI AYRI TUTULUYOR, ve ayrim korpustan olculdu (2026-09-14,
# uretilmis kurs + 0_duz_kopya + bos.story): gezinmenin tamami `<trig>`
# (147 ornek), quiz davranislari kendi etiketlerinde -- `gotoFirstInQuizTrig`,
# `resetQuizTrig`, `reviewQuizTrig`, `submitQuizTrig`. Bir `gotoFirstInQuizTrig`
# de "OnClick -> jumpToSlide/next" tasir, yani BICIMCE bir ILERI dugmesinden
# ayirt edilemez; ama anlami "sinavi yeniden dene"dir, "ileri git" degil.
# O yuzden onlara yalnizca "hedefi cozulmuyor" olcusu uygulanir.
ILERI_OLAYLARI = ("OnNextButtonClick", "OnClick")
QUIZ_ETIKETLERI = ("gotoFirstInQuizTrig", "resetQuizTrig", "reviewQuizTrig",
                   "submitQuizTrig", "textEntryTrig")


def _ileri_kayitlari(root: ET.Element) -> list[tuple[str, ET.Element]]:
    """(etiket, data) -- slayttaki gezinme tetikleyicileri, katmanlar dahil."""
    out: list[tuple[str, ET.Element]] = []
    for owner in root.iter():
        trig_list = owner.find("trigLst")
        if trig_list is None:
            continue
        for trig in trig_list:
            data = trig.find("data")
            if data is None or data.get("event") not in ILERI_OLAYLARI:
                continue
            if data.get("action") not in ("jumpToSlide", "jumpToScene"):
                continue
            out.append((trig.tag, data))
    return out


def _hedef(data: ET.Element) -> tuple[str, str | None]:
    """(tur, hedef guid) -- tur: 'sahne' | 'slayt' | 'sonraki' | 'onceki'."""
    alt = data.get("actSubType")
    if alt != "spec":
        return ("sonraki" if alt == "next" else "onceki"), None
    if data.get("action") == "jumpToScene":
        node = data.find("scene")
        return "sahne", (node.get("jumpG") if node is not None else None)
    node = data.find("slide")
    return "slayt", (node.get("jumpG") if node is not None else None)


def ileri_cikmazlari(pkg: StoryPackage,
                     sahne_guidleri: list[str] | None = None
                     ) -> list[tuple[str, str, str]]:
    """ILERI'ye basinca hicbir sey olmayan yerler: (slayt, sahne, neden).

    KULLANICININ 2026-09-14'te bildirdigi kusurun olcusu: "sahnelerdeki en
    son slayttan sonra ileriye basinca gecmiyor". Uc ayri bicimde oluyor ve
    ucu de burada sayiliyor:

      1. SAHNE SONUNDA "sonraki slayt". Sahnenin son slaydinda sonraki
         slayt YOKTUR; dugme sessizce hicbir sey yapmaz.
      2. SAHNE SONUNDA HIC ILERI YOLU YOK. Olculdu: `freeTextEntryIntr` ve
         `freeHotSpotIntr` tohumlarindan kurulan slaytlar geri bildirim
         katmani tasimiyor, yani DEVAM dugmesi de yok.
      3. HEDEFI COZULMEYEN ATLAMA, slayt nerede olursa olsun. Olculdu:
         uretilmis kursta 16 icerik slaydinin ILERI dugmesi dosyada
         OLMAYAN bir sahneye (`388e285d-...`) atliyordu.

    BILINEN KUME `paket_guidleri` DEGIL. O kume paketteki butun xml'leri
    tariyor, `docProps/summary.xml` dahil, ve o ozet parcasi silinmis
    sahneleri `<scene g="...">` olarak tasiyor: 16 olu dugmenin hepsi
    "cozuluyor" gorunuyordu ve `dangling_triggers` SIFIR diyordu. Oynatici
    `sceneLst`e bakar; bu olcu de oraya bakar.

    KAPSAM: `sahne_guidleri` verilirse yalnizca o sahneler olculur --
    kullanicinin dosyasindan devralinan sahnelerin gezinmesi onun sorunu,
    ureticinin degil. Listedeki SON sahnenin son slaydi "ileri yolu yok"
    diye sayilmaz: kurs orada biter (bkz. `son_slaydin_ilerisini_kapat`).
    """
    story = pkg.parse("story/story.xml")
    sahneler = [s for s in (story.find("sceneLst") or []) if s.get("g")]
    sahne_adi = {s.get("g"): (s.get("name") or "") for s in sahneler}
    kapsam = [g for g in (sahne_guidleri if sahne_guidleri is not None
                          else list(sahne_adi)) if g in sahne_adi]
    index = model.slide_index(pkg)
    slayt_guidleri = {r.guid for r in index.values() if r.guid}
    sahne_guidleri_kume = set(sahne_adi)

    akis: list[tuple[str, list]] = []
    for guid in kapsam:
        uyeler = sorted((r for r in index.values() if r.scene_guid == guid),
                        key=lambda r: r.position)
        if uyeler:
            akis.append((guid, uyeler))

    out: list[tuple[str, str, str]] = []
    for yer, (sahne_guid, uyeler) in enumerate(akis):
        akisin_sonu = yer == len(akis) - 1
        for uye in uyeler:
            root = pkg.parse(uye.part)
            kayitlar = _ileri_kayitlari(root)
            son_mu = uye is uyeler[-1]
            gezinme = [(etiket, data) for etiket, data in kayitlar
                       if etiket not in QUIZ_ETIKETLERI]

            for etiket, data in kayitlar:
                tur, hedef = _hedef(data)
                if tur in ("sahne", "slayt"):
                    bilinen = (sahne_guidleri_kume if tur == "sahne"
                               else slayt_guidleri)
                    if (not hedef or hedef.startswith("00000000")
                            or hedef not in bilinen):
                        out.append((uye.basename, sahne_adi[sahne_guid],
                                    f"{etiket}: hedef {tur} dosyada yok "
                                    f"({(hedef or 'bos')[:8]})"))
                elif (tur == "sonraki" and son_mu
                      and etiket not in QUIZ_ETIKETLERI
                      and data.get("action") != "jumpToScene"):
                    # `jumpToScene/next` BURAYA GIRMEZ: o "sonraki SAHNE"
                    # okunuyor ve sahne sonunda dogru olabilir. Olculmedi,
                    # o yuzden cikmaz da sayilmiyor sessizce de geciliyor
                    # -- `ileri_bilinmeyenleri` onu ayri sayiyor.
                    out.append((uye.basename, sahne_adi[sahne_guid],
                                "sahnenin son slaydinda 'sonraki slayt' "
                                "-- gidecek slayt yok"))

            if son_mu and not gezinme and not akisin_sonu:
                out.append((uye.basename, sahne_adi[sahne_guid],
                            "sahnenin son slaydinda hic ileri yolu yok"))
    return out


def ileri_bilinmeyenleri(pkg: StoryPackage,
                         sahne_guidleri: list[str] | None = None
                         ) -> list[tuple[str, str, str]]:
    """Cikmaz mi degil mi SOYLENEMEYEN ileri yollari: (slayt, sahne, neden).

    UCUNCU DURUM, ve ayri durmasi sart. `jumpToScene` + `actSubType="next"`
    bicimce "sonraki SAHNEYE git" okunuyor; oyleyse sahnenin son slaydinda
    ZATEN dogru ve cikmaz saymak YANLIS POZITIF olur. Degilse gercek bir
    cikmazdir. Ikisi arasindaki farki burada olcmenin yolu yok -- oynatici
    yok -- ve korpus da cevaplamiyor: tek ornek var (`0_duz_kopya.story`,
    `slide4.xml`, 01_Giris'in son slaydi) ve orada yaninda ayrica acik
    hedefli bir `jumpToScene/spec` duruyor.

    O yuzden ne `ileri_cikmazlari`na katiliyor ne de sessizce geciliyor:
    "gecti" ile "kaldi"nin yaninda "bakilmadi" olarak sayiliyor. Iki
    duruma indirgenmis bir sayi, ucuncusunu kaybeder.

    Uretici bu bicimi HIC uretmiyor (taze kursta 0 ornek), yani bu liste
    uretilmis kurslarda bos kalir; insan yapimi bir dosya olculdugunde
    dolar.
    """
    story = pkg.parse("story/story.xml")
    sahne_adi = {s.get("g"): (s.get("name") or "")
                 for s in (story.find("sceneLst") or []) if s.get("g")}
    kapsam = [g for g in (sahne_guidleri if sahne_guidleri is not None
                          else list(sahne_adi)) if g in sahne_adi]
    index = model.slide_index(pkg)
    out: list[tuple[str, str, str]] = []
    for guid in kapsam:
        for ref in sorted((r for r in index.values() if r.scene_guid == guid),
                          key=lambda r: r.position):
            root = pkg.parse(ref.part)
            for etiket, data in _ileri_kayitlari(root):
                if (data.get("action") == "jumpToScene"
                        and data.get("actSubType") == "next"):
                    out.append((ref.basename, sahne_adi[guid],
                                f"{etiket}: jumpToScene/next -- 'sonraki "
                                f"sahne' mi, olu mu: OLCULMEDI"))
    return out


def paket_guidleri(pkg: StoryPackage) -> set:
    """Paketteki BUTUN `g` degerleri. Cozulme kararinin bilinen kumesi.

    Slayt+story YETMIYOR: bir tetikleyici master ya da layout parcasindaki
    bir seyi gosterebilir. Olculdu (2026-09-06, alti donor kursu): dar
    kumeyle `jumpG` 4 cozulen / 7 cozulmeyen, genis kumeyle 11 / 0.
    """
    out: set = set()
    for ad in list(pkg._order):
        if not ad.endswith(".xml"):
            continue
        try:
            kok = pkg.parse(ad)
        except Exception:
            continue
        out |= {e.get("g") for e in kok.iter() if e.get("g")}
    return out


def dangling_triggers(pkg: StoryPackage) -> list[tuple[str, str]]:
    """Kurstaki butun kopuk tetikleyiciler: (slayt, olay)."""
    index = model.slide_index(pkg)
    bilinen = paket_guidleri(pkg)
    out: list[tuple[str, str]] = []
    for part, ref in index.items():
        root = pkg.parse(part)
        out += [(ref.basename, evt)
                for evt in dangling_in_slide(root, bilinen)]
    return out


# TEK YETKILI KAYNAK `storyline_mcp.puanlama` -- URETIM yolu da onu
# cagiriyor ve `tools/` orada sys.path'te YOK. Burada yalnizca ad devrali.
from storyline_mcp.puanlama import izleme as _tracking          # noqa: E402
from storyline_mcp.puanlama import zincir as puanlama_zinciri   # noqa: E402


def survey(pkg: StoryPackage) -> dict:
    """Kursun işlevsel envanteri. Hiçbir şey değiştirmez."""
    index = model.slide_index(pkg)
    # BILINEN KUME PAKETIN TAMAMI, slayt+story degil -- OLCULDU 2026-09-06.
    #
    # Once yalnizca slaydin kendisi ve story.xml taraniyordu. Ama bir
    # tetikleyici MASTER ya da LAYOUT parcasindaki bir seyi de gosterebilir
    # ve o parcalar kumeye girmiyordu. Insan yapimi donor kurslarinda
    # olculdu: dar kumeyle `jumpG` 4 cozulen / 7 cozulmeyen, GENIS kumeyle
    # 11 / 0. Yani "kopuk atlama" diye sayilanlarin tamami saglamdi ve
    # kusur sayacin kendisindeydi.
    story_guids = set()
    for _ad in list(pkg._order):
        if not _ad.endswith(".xml"):
            continue
        try:
            _kok = pkg.parse(_ad)
        except Exception:
            continue
        story_guids |= {e.get("g") for e in _kok.iter() if e.get("g")}

    empty, dangling, scored, unscored = [], [], [], []
    scenes: dict[str, dict] = {}
    # slide_index sahne sirasina gore doner, dolayisiyla ilk kayit kursun
    # acildigi slayttir.
    ilk_slayt, ilk_bos = None, False
    for part, ref in index.items():
        root = pkg.parse(part)
        shape_list = root.find("shapeLst")
        filled = bool(shape_list is not None and len(shape_list))
        scene = scenes.setdefault(ref.scene_name or "(sahnesiz)",
                                  {"slides": 0, "empty": 0, "questions": 0,
                                   "ilk_bos": None, "ilk": None})
        scene["slides"] += 1
        # A2: ogrencinin gordugu ILK ekran. Sahnenin tamami bos olmasa bile
        # ilk slayt bosse kurs bos bir ekranla aciliyor demektir, ve "tamami
        # bos" olcusu bunu KACIRIR -- referansta tam olarak oyle bir sahne
        # yoktu, ama olmamasi kontrolun gereksiz oldugunu gostermez.
        if ilk_slayt is None:
            ilk_slayt, ilk_bos = ref.basename, not filled
        if ref.position == 1:
            scene["ilk_bos"] = not filled
            scene["ilk"] = ref.basename
        if not filled:
            empty.append((ref.basename, ref.scene_name, ref.name))
            scene["empty"] += 1

        tag, intr = authoring._find_interaction(root)
        if intr is not None:
            scored.append(ref.basename)
            scene["questions"] += 1
        elif filled:
            # Puanlanmayan ama SORU GIBI duran slayt: birden fazla
            # tiklanabilir hedefi olan ama etkilesim kaydi olmayan.
            targets = [s for s in (shape_list or [])
                       if (t := s.find("trigLst")) is not None and len(list(t))
                       and model.shape_text(root, s.get("g") or "").strip()]
            if len(targets) >= 2:
                unscored.append((ref.basename, len(targets)))

        known = {e.get("g") for e in root.iter() if e.get("g")} | story_guids
        # TEK OTORITEYE SORULUYOR. Burada bir IKINCI uygulama duruyordu ve
        # `dangling_in_slide`in belge dizesi tam bunu yasakliyor ("bu sayi
        # bir donem IKI YERDE hesaplaniyordu ve iki farkli cevap veriyordu").
        # Nitekim yine ayristi: beyaz liste 2026-09-06'da tek otoriteye
        # eklendi, buradaki kopya eski haliyle kaldi ve ayni dosya icin
        # kapi 42, yardimci 0 dedi.
        dangling += [(ref.basename, evt)
                     for evt in dangling_in_slide(root, known)]

    izleme = _tracking(pkg, index)
    kayitli = izleme["registered"]
    # IKI YON (K7). Kayitsiz soru skoru kaybeder; sorusuz kayit olmayan bir
    # soruyu izler. Tek yonu tutmak, digerinin sessizce girmesine izin verir.
    kayitsiz = [s for s in scored if s not in kayitli]
    sorusuz_kayit = [s for s in kayitli if s not in scored]
    # Devralinan cop bolum sayilmasin: BIR slaydi bile bestelenmemis sahne
    # bolum degildir. Onceki surum "slides > 1" diyordu ve referansta 5 yerine
    # 7 bolum sayiyordu -- devralinan `Konular` ve `SINAV` sahneleri boluume
    # dahil oluyordu, yani olcut devralinan copla KANDIRILABILIYORDU.
    dolu_sahneler = [ad for ad, d in scenes.items() if d["slides"] > d["empty"]]
    return {"slides": len(index), "scenes": scenes,
            "empty": empty, "dangling": dangling,
            "scored": scored, "unscored": unscored,
            "quiz_records": len(model.quiz(pkg)),
            "izleme": izleme, "kayitli": sorted(kayitli),
            "kayitsiz": kayitsiz, "sorusuz_kayit": sorusuz_kayit,
            "dolu_sahneler": dolu_sahneler,
            "ilk_slaydi_bos": [d["ilk"] for d in scenes.values()
                               if d["ilk_bos"]],
            # A2'nin KENDISI. "Herhangi bir sahnenin ilk slaydi" genis bir
            # olcu ve devralinan sahneler yuzunden neredeyse her kursta
            # tetiklenir; asil urun kirigi daha dar: kursun ACILDIGI ekran.
            # Bu, sceneLst'in ilk sahnesinin ilk slaydidir -- dosyada
            # startSceneG gibi bir isaret yok, bakildi.
            "kurs_ilk_slaydi": ilk_slayt,
            "kurs_ilk_bos": ilk_bos}


def report(found: dict, *, sections: int | None = None,
           per_section: int | None = None) -> list[str]:
    problems: list[str] = []
    print(f"slayt {found['slides']}  sahne {len(found['scenes'])}  "
          f"puanli soru {len(found['scored'])}  quiz kaydi {found['quiz_records']}")

    print("\n=== PUANLAMA ZINCIRI (uc halka, ayri ayri kirilir) ===")
    izleme = found["izleme"]
    print(f"  1. etkilesim tasiyan slayt : {len(found['scored'])}")
    print(f"  2. quiz'e kayitli          : {len(found['kayitli'])}")
    for quiz in izleme["quizzes"]:
        hedef = quiz["sonuc_slaydi"] or ("BOS GUID" if quiz["sonuc_guid_bos"]
                                         else "COZULEMEDI")
        print(f"       quiz {quiz['name']!r}: {quiz['kayit']} kayit, "
              f"sonuc slaydi {hedef}")
        if quiz["cozulemeyen"]:
            problems.append(f"quiz {quiz['name']!r}: {len(quiz['cozulemeyen'])} "
                            "kayit hicbir slayda cozulmuyor")
        if quiz["sonuc_slaydi"] is None:
            problems.append(f"quiz {quiz['name']!r}: sonuc slaydi yok "
                            f"({hedef})")
    print(f"  3. story lmsResultSlideG   : "
          f"{izleme['lms_hedefi'] or ('BOS' if izleme['lms_bos'] else 'COZULEMEDI')}"
          f"   trackMode={izleme['track_mode']}")

    if found["kayitsiz"]:
        print(f"  KAYITSIZ SORU: {len(found['kayitsiz'])}  {found['kayitsiz'][:5]}")
        problems.append(f"{len(found['kayitsiz'])} soru quiz'e kayitli degil — "
                        "ogrenci cevapliyor, skor LMS'e gitmiyor")
    if found["sorusuz_kayit"]:
        print(f"  SORUSUZ KAYIT: {len(found['sorusuz_kayit'])}  "
              f"{found['sorusuz_kayit'][:5]}")
        problems.append(f"{len(found['sorusuz_kayit'])} kayit, etkilesimi "
                        "olmayan slaydi izliyor")
    if izleme["lms_bos"] and found["scored"]:
        problems.append("puanlanabilir soru var ama story duzeyinde "
                        "lmsResultSlideG bos — LMS'e bildirilecek sonuc "
                        "slaydi secilmemis")

    print("\n=== ISTENEN vs URETILEN ===")
    if sections is not None:
        content_scenes = found["dolu_sahneler"]
        print(f"  bolum: istenen {sections}, dosyada {len(content_scenes)}"
              f"   (en az bir bestelenmis slaydi olan sahne)")
        if len(content_scenes) < sections:
            problems.append(f"{sections} bolum istendi, {len(content_scenes)} var")
    if per_section is not None and sections:
        want = sections * per_section
        print(f"  soru : istenen {want}, puanli {len(found['scored'])}")
        if len(found["scored"]) < want:
            problems.append(f"{want} soru istendi, {len(found['scored'])} puanli")
    if found["unscored"]:
        print(f"  PUANLANMAYAN soru gibi slayt: {len(found['unscored'])}  "
              f"{found['unscored'][:4]}")
        problems.append(f"{len(found['unscored'])} slayt soru gibi duruyor ama "
                        "puanlanmiyor")

    print("\n=== DEVRALINAN (kaynak dosyadan gelen, ele alinmayan) ===")
    print(f"  bos slayt        : {len(found['empty'])}")
    for basename, scene, name in found["empty"][:6]:
        print(f"     {basename:<12} sahne={scene!r} ad={name[:24]!r}")
    print(f"  kopuk tetikleyici: {len(found['dangling'])}")
    if found["empty"]:
        problems.append(f"{len(found['empty'])} bos slayt ogrenciye gidiyor")
    if found["dangling"]:
        problems.append(f"{len(found['dangling'])} kopuk tetikleyici")
    if found["ilk_slaydi_bos"]:
        print(f"  ILK SLAYDI BOS SAHNE: {found['ilk_slaydi_bos']}")
        problems.append(f"{len(found['ilk_slaydi_bos'])} sahnenin ILK slaydi "
                        "bestelenmemis (menuden erisilebilir)")
    print(f"  KURSUN ACILDIGI SLAYT: {found['kurs_ilk_slaydi']}  "
          f"{'BOS' if found['kurs_ilk_bos'] else 'bestelenmis'}")
    if found["kurs_ilk_bos"]:
        problems.append(f"kurs BOS bir slaytla aciliyor "
                        f"({found['kurs_ilk_slaydi']}) — ogrencinin gordugu "
                        "ilk ekran")

    print("\n=== SAHNE DAGILIMI ===")
    for name, data in found["scenes"].items():
        mark = "  <- tamami bos" if data["empty"] == data["slides"] else ""
        print(f"  {name[:24]:<26} slayt {data['slides']:>2}  bos "
              f"{data['empty']:>2}  soru {data['questions']}{mark}")
    return problems


# --------------------------------------------------------- pozitif kontrol
#
# Dondurulmus referansin sayilari. Bunlar bir HEDEF degil, dedektorun CIPASI:
# referans bilerek bozuk bir snapshot ve o bozukluk sabittir. Dedektor 13 bos
# slayt bulursa korlesmis, 15 bulursa fazla sayiyor -- IKISI DE bagirmali.
# Tek yonlu bir esik (">= 14") korlesmeyi yakalar, fazla saymayi kacirir; bu
# projede tek yonlu guard'in kazanimi sessizce kaybettirdigi ucuncu yer olur.
#
# Sayilar 2026-08-16'da dondurulmus referans uzerinde olculdu.
REFERANS = ROOT.parent / "test" / "_referans" / "referans.story"
SAGLAM = ROOT.parent / "test" / "0_duz_kopya.story"

BEKLENEN_BOZUK = {
    "bos slayt": 14,
    # 43'ten 20'ye dustu (2026-09-06): sayac artik OLCULMUS bir isaretci
    # beyaz listesi kullaniyor. Eski sayi surum damgalarini ve Storyline'in
    # kendi sabitlerini de "kopuk" sayiyordu.
    "kopuk tetikleyici": 20,
    "etkilesim tasiyan": 5,
    "quiz'e kayitli": 0,
    "kayitsiz soru": 5,
    "ilk slaydi bos sahne": 4,
    "dolu sahne": 5,
    # Referans, duzeltme ONCESI kodla uretildi: bos bir slaytla aciliyor.
    # Bu 1, duzeltmenin gerektigini kanitlayan sabit -- 0 olursa referans
    # degismis demektir, duzeltme calismis demek degil.
    "kurs bos aciliyor": 1,
}
# Gercek, elle yazilmis bir kursun kaydi. Bu ayak olmadan dedektor "her seye
# kayitsiz de" diyerek birinci ayagi gecerdi.
BEKLENEN_SAGLAM = {
    "etkilesim tasiyan": 11,
    "quiz'e kayitli": 11,
    "kayitsiz soru": 0,
    "sorusuz kayit": 0,
    "kurs bos aciliyor": 0,
}


def _sayilar(found: dict) -> dict:
    return {
        "bos slayt": len(found["empty"]),
        "kopuk tetikleyici": len(found["dangling"]),
        "etkilesim tasiyan": len(found["scored"]),
        "quiz'e kayitli": len(found["kayitli"]),
        "kayitsiz soru": len(found["kayitsiz"]),
        "sorusuz kayit": len(found["sorusuz_kayit"]),
        "ilk slaydi bos sahne": len(found["ilk_slaydi_bos"]),
        "dolu sahne": len(found["dolu_sahneler"]),
        "kurs bos aciliyor": int(found["kurs_ilk_bos"]),
    }


def _olc(path: Path) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return _sayilar(survey(StoryPackage(path)))


def kontrol() -> int:
    """Dedektor hala goruyor mu -- ve gormemesi gerekeni gormuyor mu?"""
    import shutil
    for path in (REFERANS, SAGLAM):
        if not path.is_file():
            print(f"Kontrol dosyasi yok: {path}")
            return 2

    kirik: list[str] = []

    print("=== 1. BILINEN BOZUK (dondurulmus referans) ===")
    bozuk = _olc(REFERANS)
    print(f"  {'olcu':<24}{'beklenen':>9}{'olculen':>9}")
    for ad, bekleniyor in BEKLENEN_BOZUK.items():
        olculen = bozuk[ad]
        tuttu = olculen == bekleniyor
        yon = "" if tuttu else ("  <- AZ SAYIYOR (korlesme)" if olculen < bekleniyor
                                else "  <- COK SAYIYOR")
        print(f"  {ad:<24}{bekleniyor:>9}{olculen:>9}{yon}")
        if not tuttu:
            kirik.append(f"{ad}: beklenen {bekleniyor}, olculen {olculen}")

    print("\n=== 2. BILINEN SAGLAM (gercek, elle yazilmis kurs) ===")
    saglam = _olc(SAGLAM)
    print(f"  {'olcu':<24}{'beklenen':>9}{'olculen':>9}")
    for ad, bekleniyor in BEKLENEN_SAGLAM.items():
        olculen = saglam[ad]
        print(f"  {ad:<24}{bekleniyor:>9}{olculen:>9}")
        if olculen != bekleniyor:
            kirik.append(f"saglam kurs/{ad}: beklenen {bekleniyor}, "
                         f"olculen {olculen}")

    # Ucuncu ayak, ve digerlerinin anlamini veren ayak. Ilk ikisi gecip de
    # dedektor atil olabilir: saglam kursta "kayitsiz 0" demek, hicbir seyi
    # kayitsiz saymayan bir dedektor icin de dogrudur. Kaydi KASTEN silip
    # tam olarak bir kayitsiz soru bekleniyor.
    print("\n=== 3. KASTEN BOZULMUS (saglam kursun bir kaydi silinir) ===")
    work = ROOT.parent / "test" / "_canary" / "kayit_bozuk.story"
    work.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SAGLAM, work)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pkg = StoryPackage(work)
        story = pkg.parse("story/story.xml")
        silinen = None
        for quiz in story.iter("quiz"):
            id_list = quiz.find("questionIdLst")
            if id_list is not None and len(id_list):
                silinen = (list(id_list)[0].text or "").strip()
                id_list.remove(list(id_list)[0])
                break
        pkg.replace_xml("story/story.xml", story)
        pkg.save(work, backup=False)
    if silinen is None:
        print("  saglam kursta silinecek kayit yok — ucuncu ayak kurulamadi.")
        kirik.append("kasten bozma ayagi kurulamadi")
    else:
        bozulmus = _olc(work)
        print(f"  silinen kayit: {silinen[:8]}...")
        print(f"  {'olcu':<24}{'beklenen':>9}{'olculen':>9}")
        for ad, bekleniyor in (("quiz'e kayitli", BEKLENEN_SAGLAM["quiz'e kayitli"] - 1),
                               ("kayitsiz soru", 1)):
            olculen = bozulmus[ad]
            print(f"  {ad:<24}{bekleniyor:>9}{olculen:>9}")
            if olculen != bekleniyor:
                kirik.append(f"kasten bozuldu/{ad}: beklenen {bekleniyor}, "
                             f"olculen {olculen}")

    print()
    if kirik:
        print(f"{len(kirik)} KONTROL TUTMADI:")
        for k in kirik:
            print(f"  ! {k}")
        print("\nDedektorun kendisi degismis olabilir. Sayilar bilerek "
              "degistiyse\nBEKLENEN_* tablolarini guncelleyin; degilse bir "
              "gerileme var.")
        return 1
    print("Dedektor tutuyor: bilinen bozuk kursu birebir sayiyor, saglam "
          "kursu\ntemiz buluyor, ve kasten silinen tek kaydi yakaliyor.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("story", nargs="?")
    parser.add_argument("--sections", type=int)
    parser.add_argument("--per-section", type=int)
    parser.add_argument("--kontrol", action="store_true",
                        help="dedektorun pozitif kontrolu (iki yonlu)")
    args = parser.parse_args()
    if args.kontrol:
        return kontrol()
    if not args.story:
        parser.error("bir kurs dosyasi verin ya da --kontrol kullanin")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pkg = StoryPackage(Path(args.story).resolve())
        found = survey(pkg)
    problems = report(found, sections=args.sections,
                      per_section=args.per_section)

    print()
    if problems:
        print(f"{len(problems)} ISLEVSEL EKSIK:")
        for p in problems:
            print(f"  ! {p}")
        print("\nHicbiri silinmedi: kaynak dosyadaki slaytlar kullanicinin.")
        return 1
    print("Islevsel olarak eksiksiz.")
    return 0


if __name__ == "__main__":
    # KANARYA KILIDI. Kapilar `test/_canary/` icine SABIT adli dosyalar
    # yaziyor; iki kosu ayni anda ayni dosyaya yazarsa ikisi de yanlis
    # okur ve sonuc "kostu ve dustu" gibi gorunur. Gerekce ve olcum:
    # tools/kanarya_kilit.py.
    from kanarya_kilit import korumali
    raise SystemExit(korumali(main))
