"""Hangi kusur hangi kontrol tarafından, hangi kesitte görülüyor?

`coverage.py` urun UZAYININ neresinin tarandigini sayiyordu (duzen x tema).
Bu dosya baska bir soruyu soruyor ve cevabi daha rahatsiz edici:

    kontroller URUNU mu tariyor, yoksa kendi problarini mi?

Uretilmis gercek bir kursta on kusur bulundu. On kusurun ONU DA, butun test
paketi YESILKEN oradaydi. Bu tesaduf degil: paketteki her kontrol kendi
kurdugu sentetik bir prob uzerinde kosuyor --

    variety      varyant SOZLUGUNU tarar, uretilmis kursu degil
    coverage     kendi SPECS'ini kurar, gercek brief'i degil
    themes_check kendi prob slaytlarini kurar
    golden       uc elle yazilmis soru vakasi
    invariants   variety.story + fikstuurler (hepsi kendi urettigi)

Yani "hepsi yesil" cumlesi, "problar saglam" demek. Uretilmis bir kursun
saglam oldugunu SOYLEMIYOR, ve bugune kadar hicbir yerde oyle soylenmedi de.

Bu dosya bir kursu alir, butun olculeri uzerinde kosar ve her bulguyu
etiketler:

    KAPSANIYOR   paket icinde bu sinifi koruyan bir kontrol var
    ACIK         olculebiliyor ama hicbir kontrol kosmuyor
    OLCULMUYOR   bu sinifi olcen bir sey yok

    python tools/inventory.py <kurs.story>
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from storyline_mcp import authoring, compose, model, preview, shapes
from storyline_mcp.package import StoryPackage
import completeness
import contrast
import deadband
import silhouette

# Her kontrolun GERCEKTEN tardigi kesit. "Uretilmis kurs" sutunu, kontrolun
# bir brief'ten cikmis bir dosyaya bakip bakmadigini soyler -- paketteki
# kontrollerin HICBIRI bakmiyor, ve on kusurun onu da oradan geldi.
SCANS = [
    # ad,            tardigi sey,                         uretilmis kurs?
    ("invariants",   "donor havuzu + variety.story + fikstuurler", False),
    ("coverage",     "7 duzen x 6 tema, kendi SPECS'i",           False),
    ("themes_check", "6 tema x 6 content varyanti",               False),
    ("variety",      "varyant sozlugu, sabit icerik",             False),
    ("golden",       "3 elle yazilmis soru vakasi",               False),
    ("deadband",     "variety.story",                             False),
    ("contrast",     "verilen dosya (elle cagrilir)",             True),
    ("scope",        "kapsam iddialari",                          False),
    ("open_test",    "verilen dosya (elle cagrilir)",             True),
]

# Sinif -> paket icinde onu KOSAN bir kontrol var mi.
# "Var" demek, suit kosuldugunda bu sinifin yakalanacagi demek DEGIL: kontrol
# kendi probunda kosuyor. Sutun, sinifin bir invaryanti olup olmadigini
# soyler; kesit sorusu ayri ve yukarida.
GUARDED = {
    "tasma": "invariants.check_text_fits",
    # SIDDET, ADEDIN YANINDA. `tasma` bir SAYAC ve tek basina aciliyet
    # gostermiyor: kart bandi duzeltmesinde adet 20'den 14'e indi (kucuk)
    # ama AGIR tasma 15'ten 0'a indi. Adede bakan bir olcu o duzeltmeyi
    # "ufak bir iyilesme" diye okurdu.
    #
    # 2026-08-16'da olculmustu: Storyline tasan metni KIRPMIYOR, yani tasma
    # metin KAYBI degil. O karar yerinde -- `tasma` bir kapi degil. Ama
    # kutunun metnin BESTE BIRINE dusmesi kozmetik degil: yazi komsusunun
    # uzerine biner ve slayt okunmaz olur. Ayrimi tasiyan sey ORAN.
    "tasma_orani": "invariants.check_card_band (siddet, adet degil)",
    "cakisma": "invariants.check_no_overlap",
    "taban": "invariants.check_floor_respected",
    "kontrast": "contrast.audit / themes_check",
    "bos_alan": "deadband + coverage",
    "erisilebilirlik": "invariants.check_variant_reach",
}
UNGUARDED = {
    "eksik_soru": "brief bolum basina soru istedi, dosyada yok",
    "bos_slayt": "hicbir sey bestelenmemis slayt",
    "kopuk_tetik": "hedefi olmayan tetikleyici",
    "ikiz_slayt": "uretilmis kursta ayni goruen slayt cifti",
    "punto_olcegi": "kursta kac farkli punto var",
    "hizalama": "tek bir x'in payi",
}


def _merdiven_disi(pkg) -> dict:
    """Ölçeğe uymayan yazılar: {'bizim': n, 'devralinan': n}.

    Kaynak ayrimi tohum dosyasindan okunur: adi tohumda da gecen slaytlar
    KULLANICININ, digerleri bizim urettigimiz. Ayni ayrim `submitG` ve
    `drop_orphan_submit` kararlarinda da kullanildi.
    """
    from storyline_mcp import compose
    merdiven = set(compose.TYPE_LADDER)
    tohum_yolu = ROOT.parent / "test" / "bos.story"
    tohum = set()
    if tohum_yolu.is_file():
        try:
            tohum = {r.basename for r in
                     model.slide_index(StoryPackage(tohum_yolu)).values()}
        except Exception:
            tohum = set()
    out = {"bizim": 0, "devralinan": 0}
    for part, ref in model.slide_index(pkg).items():
        root = pkg.parse(part)
        kova = "devralinan" if ref.basename in tohum else "bizim"
        kaplar = [root.find("shapeLst")]
        katmanlar = root.find("sldLayerLst")
        for k in (list(katmanlar) if katmanlar is not None else []):
            kaplar.append(k.find("shapeLst"))
        for kap in kaplar:
            for shape in list(kap) if kap is not None else []:
                if not model.shape_text(root, shape.get("g", "")).strip():
                    continue
                _c, size, _b, _a = preview._text_style(shape)
                if round(size, 1) not in merdiven:
                    out[kova] += 1
    return out


def audit(pkg: StoryPackage) -> dict:
    index = model.slide_index(pkg)
    lo, hi = shapes.CALIBRATED_RANGE
    out = {k: 0 for k in list(GUARDED) + list(UNGUARDED)}
    out["_yatay_temel"] = 0
    sizes: set[int] = set()
    lefts: dict[float, int] = {}
    filled: list[str] = []

    for part, ref in index.items():
        root = pkg.parse(part)
        shape_list = root.find("shapeLst")
        kids = list(shape_list) if shape_list is not None else []
        width, height = shapes.slide_size(root)
        placed = [(s, shapes.shape_rect(s)) for s in kids]
        placed = [(s, r) for s, r in placed if r]
        if not placed:
            out["bos_slayt"] += 1
            continue
        filled.append(ref.basename)

        boxes = []
        for shape, rect in placed:
            guid = shape.get("g") or ""
            text = model.shape_text(root, guid).strip()
            full = ((rect[2] - rect[0]) / width > 0.97
                    or (rect[3] - rect[1]) / height > 0.97)
            if not full:
                lefts[round(rect[0] / width * 100, 1)] = \
                    lefts.get(round(rect[0] / width * 100, 1), 0) + 1
            if text:
                _c, size, _b, _a = preview._text_style(shape)
                sizes.add(round(size))
                boxes.append((shape.get("name") or shape.tag, rect))
                # Yazanla ayni tolerans (compose.FIT_TOLERANCE).
                slack = compose.FIT_TOLERANCE / 100 * height
                # wrap OKUNUR, varsayilana birakilmaz: sarmayan bir kutuda
                # model satir sayisini fazla veriyordu ve bu sayac artefakt
                # sayiyordu -- referansta 38 adayin 16'si tam olarak buydu.
                _uzay = shapes.space_of(root, shapes.stage_size(pkg))
                if lo <= size <= hi:
                    _gereken = shapes.measured_text_height(
                        text, size, rect[2] - rect[0], _uzay,
                        wrap=shapes.wraps(shape))
                    if _gereken > (rect[3] - rect[1]) + slack:
                        out["tasma"] += 1
                    # Oran AYNI hesaptan cikar, ikinci bir uygulama
                    # ACILMAZ: iki uygulama ayrisir ve fark yuvarlama
                    # degil kesit olur.
                    _oran = _gereken / max(rect[3] - rect[1], 1.0)
                    if _oran > out["tasma_orani"]:
                        out["tasma_orani"] = round(_oran, 2)
                # YATAY TASMA, wrap bulgusunun ikinci yarisi. Sarmayan bir
                # kutuda dikey tasma imkansiz, yatay tasma kural: Storyline
                # satiri saga uzatir, gerekirse slaydin disina. Bunu olcen
                # hicbir sey yoktu, dolayisiyla o 16 sekil "duzeltildi" diye
                # sayiliyor ama gercek kusurlari olcusuz kaliyordu.
                if not shapes.wraps(shape) and lo <= size <= hi and \
                        shapes.estimate_text_width(text, size, _uzay) > \
                        (rect[2] - rect[0]) + slack:
                    out["_yatay_temel"] += 1
            trig = shape.find("trigLst")
            clickable = trig is not None and len(list(trig)) > 0
            if not full and rect[3] / height * 100 > compose.FLOOR + 0.5 \
                    and (text or clickable):
                out["taban"] += 1
        for i, (_na, a) in enumerate(boxes):
            for _nb, b in boxes[i + 1:]:
                if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                    out["cakisma"] += 1

        # KATMANLAR DA TASAR -- ve bu sayacin kor noktasiydi.
        #
        # Yukaridaki dongu yalnizca `root.find("shapeLst")`, yani TEMEL katman
        # uzerinde donuyordu. `coverage.py --kanarya` bunu olcuyordu ve
        # "KOR inventory katmandaki AYNI tasmayi gormedi" diyordu: ayni kusur
        # temele ekilince sayiliyor, geri bildirim katmanina ekilince
        # sayilmiyordu.
        #
        # Korlugun bedeli 2026-09-05'te iki kez gorundu: gorunmez katman
        # yazilari ve tasan geri bildirim butonlari -- ikisi de katmanda,
        # ikisi de bu sayacin disindaydi.
        #
        # YALNIZCA TASMA SAYACLARI ACILIYOR. Hizalama histogrami (`lefts`),
        # bos slayt, taban asimi ve cakisma TEMELDE KALIYOR: onlar slaydin
        # kendi izgarasi hakkinda ve katman sekilleri o izgaranin parcasi
        # degil -- pop-up'in solu, slaydin sol hizasi sayilmaz.
        #
        # `_yatay_temel` de adiyla temelde kaliyor; yatay tasmanin katman
        # karsiligi ayri bir olcum ister (kutu genisligi orada baska
        # kurallarla belirleniyor) ve olculmeden sayilmaz.
        _uzay_kat = shapes.space_of(root, shapes.stage_size(pkg))
        _slack_kat = compose.FIT_TOLERANCE / 100 * height
        _katman_listesi = root.find("sldLayerLst")
        for _kat in (list(_katman_listesi) if _katman_listesi is not None else []):
            for _sh in list(_kat.find("shapeLst") or []):
                _metin = model.shape_text(root, _sh.get("g") or "").strip()
                _rect = shapes.shape_rect(_sh)
                if not _metin or not _rect:
                    continue
                _c2, _size2, _b2, _a2 = preview._text_style(_sh)
                if not (lo <= _size2 <= hi):
                    continue
                _gereken2 = shapes.measured_text_height(
                    _metin, _size2, _rect[2] - _rect[0], _uzay_kat,
                    wrap=shapes.wraps(_sh))
                if _gereken2 > (_rect[3] - _rect[1]) + _slack_kat:
                    out["tasma"] += 1
                _oran2 = _gereken2 / max(_rect[3] - _rect[1], 1.0)
                if _oran2 > out["tasma_orani"]:
                    out["tasma_orani"] = round(_oran2, 2)

        # Kopuk tetikleyici burada SAYILMAZ; hesap completeness'te, tek yerde.
        # Buradaki eski kopya bos slaytlari atliyordu (yukaridaki `continue`
        # tetikleyici taramasindan ONCE calisiyor) ve 43 yerine 25 veriyordu --
        # devralinan donor copu tam o atlanan kesitte yasiyor.

    out["kontrast"] = len(contrast.audit(pkg))
    empties = []
    for part, _ref in index.items():
        _band, total, count = deadband.dead_band(pkg, part)
        if count:
            empties.append(total)
    # BOS ALAN OLCUSU DEGISTI (2026-08-18, C2). Eskiden `max(empties)` idi --
    # AZAMI, yani tek seyrek slayt sayiyi tek basina belirleyebiliyordu.
    #
    # IKI AYRI OLCU, IKI AYRI SORU -- ve karistirilmasi bir kez yanlis
    # sonuca goturdu (2026-08-18):
    #
    #   deadband.dead_band  : icerik bandi ICINDE dikey bos bantlar = RITIM
    #   slaydin tamaminin kaplamasi : SEVIYE (bu dosyada olculmuyor)
    #
    # Once slayt geneli raster ile olculdu ve "ritim sorun degil, seviye
    # sorun" sonucuna varildi. YANLISTI: o olcu ritmi hic olcmuyordu.
    # Dogru olcu -- adi zaten ritim olan `deadband` -- tersini soyluyor:
    #
    #     olu bant ortanca   BIZIM 22   ELLE  0
    #     olu bant yayilim   BIZIM 18   ELLE  1
    #
    # Elle yapilmis kursta icerik bandinda olu bosluk YOK. Ritim farki
    # gercek ve buyuk.
    #
    # AZAMI DEGIL ORTANCA + YAYILIM. Eski `max(empties)` tek seyrek slaydin
    # sayiyi belirlemesine izin veriyordu. Yayilim da basiliyor cunku
    # "ortanca 22" ile "bazi slaytlar 0 bazilari 56" ayni sey degil ve
    # duzeltmenin sekli buna bagli.
    import statistics as _st
    out["bos_alan"] = max(empties) if empties else 0          # eski, kayit icin
    out["bos_ortanca"] = round(_st.median(empties)) if empties else 0
    out["bos_yayilim"] = round(_st.pstdev(empties)) if len(empties) > 1 else 0
    pairs = silhouette.compare(pkg, filled)
    out["ikiz_slayt"] = len([p for p in pairs if p["same_idea"]])
    # PUNTO OLCUSU DEGISTI (2026-08-18, C1). Eskiden `len(sizes)` idi --
    # kac CESIT punto var. O sayi KUSURA OZGU DEGIL ve kalibrasyon noktasi
    # bunu gosterdi: elle yapilmis, calisan bir kursta 13 cesit var ve
    # 332 yazinin 332'si merdiven DISINDA -- kendi duzenli olcegini
    # kullaniyor ve sorun yok (K21).
    #
    # Kusur cesit sayisinda degil, OLCEGE UYMAYAN yazida. Yeni olcu onu
    # sayiyor, ve kaynagi ayiriyor: bizim urettigimiz mi, tohumdan devralinan
    # mi. Ayrim `submitG` kararinin aynisi -- kullanicinin kendi slaytlari
    # bizim isimiz degil.
    #
    # Kaydedilmeyen kazanim korunmuyor: bu olcu olmadan C1 duzeltmesi
    # (merdiven disi 20 -> 4 yazi, bizim tarafta SIFIR) bir sonraki
    # regresyonda sessizce geri donerdi.
    out["punto_olcegi"] = len(sizes)
    out["punto_merdiven_disi"] = _merdiven_disi(pkg)
    total_shapes = sum(lefts.values()) or 1
    out["hizalama"] = round(max(lefts.values()) / total_shapes * 100) if lefts else 0
    out["kopuk_tetik"] = len(completeness.dangling_triggers(pkg))
    out["_sizes"] = sorted(sizes)
    out["_slides"] = len(index)
    out["_filled"] = len(filled)
    out["eksik_soru"] = len(model.quiz(pkg))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("story")
    args = parser.parse_args()

    print("=== HANGI KONTROL NEYI TARIYOR ===")
    print(f"  {'kontrol':<14}{'tardigi kesit':<44}uretilmis kurs")
    for name, what, real in SCANS:
        print(f"  {name:<14}{what:<44}{'EVET' if real else 'hayir'}")
    auto = [n for n, _w, r in SCANS if r]
    print(f"\n  Suit kosuldugunda uretilmis bir kursa bakan kontrol: YOK.")
    print(f"  ({', '.join(auto)} elle cagrilir, pakette kosmaz.)")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pkg = StoryPackage(Path(args.story).resolve())
        found = audit(pkg)

    print(f"\n=== {Path(args.story).name}: {found['_slides']} slayt, "
          f"{found['_filled']} dolu ===")
    print(f"  {'sinif':<18}{'bulgu':<10}{'invaryant':<38}durum")
    for key, guard in GUARDED.items():
        value = found[key]
        state = "temiz" if not value else "KUSUR VAR (prob yesil)"
        print(f"  {key:<18}{str(value):<10}{guard:<38}{state}")
    for key, why in UNGUARDED.items():
        value = found[key]
        print(f"  {key:<18}{str(value):<10}{'YOK':<38}{why}")
    print(f"\n  punto dagilimi: {found['_sizes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
