"""SIFIRDAN yeni bir modul kurar ve 2026-09-06'da duzeltilen sinifları sinar.

NICIN VAR. Kullanicinin elle yaptigi denetim yirmi dort kusur buldu ve
onlarin bir kismi kaynakta duzeltildi. Ama "duzeltildi" ile "bir daha
olmayacak" ayni sey DEGIL: duzeltme kaynaktaysa bile, sonraki bir
degisiklik onu sessizce geri alabilir.

Kullanicinin sordugu soru tam buydu -- "bunlari sadece bu modul icin degil,
ileride panelden uretecegim modullerde olmamasi icin yapiyorsun degil mi".
Bu dosya o sorunun makine tarafindan tekrarlanabilir cevabi.

FIKSTUR DEGIL, URETIM YOLU. Kurs `bos.story`den baslayip ureticinin KENDI
fonksiyonlariyla kuruluyor: `add_slide` + `compose_slide` + `add_question` +
`add_drag_question` + `add_text_question` + `add_layer`. Model cagrisi yok
(kapilar model cagirmaz), ama bu fonksiyonlar HER IKI yolun da ortak
govdesi -- panel brief yolu da, komut yolu da buradan geciyor.

SINANAN YEDI SINIF, her biri kullanicinin denetimindeki bir maddeye bagli:

    1  kopuk tetikleyici          hedefi cozulmeyen atlama       (#1)
    2  olu puan degiskeni         tanimsiz degiskene yazan trig  (#4)
    3  intrProps cozuluyor mu     submit'te katman bulunmuyordu  (#5)
    4  taahhut slaydi gezinme     ogrenci slaytta mahsur         (#2)
    5  katman kapaniyor mu        pop-up dugmesi olu             (#8)
    6  katmanda yabanci metin     baska kursun icerigi           (#11)
    7  slayt adlari ayri mi       menude dokuz kez "Intro Slide" (#15)
    8  Turkce buyuk harf          I/Ist ayrimi                   (#13)

Bir sinif kirmizi olursa mesaj HANGI maddeye dondugunu soyler, cunku
"kopuk tetikleyici 3" tek basina ne yapilmasi gerektigini anlatmiyor.

    python tools/yeni_modul.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import completeness
from storyline_mcp import authoring, compose, model
from storyline_mcp.package import StoryPackage

BLANK = ROOT.parent / "test" / "bos.story"
# Donor kursun puan degiskeni: tohumlarin tasidigi, hedefte tanimsiz GUID.
OLU_PUAN_GUID = "8041a620-761b-41d3-955f-ed3c9a72cecc"

BASLIKLAR = ("Savunmanin Temel Ilkeleri",
             "Pozisyon Alma ve Kayma",
             "Iletisim ve Roller")


def kur(yol: Path) -> dict:
    """Yeni bir modul kurar ve olculecek parcalari geri verir."""
    shutil.copy2(BLANK, yol)
    pkg = StoryPackage(yol)
    sablon = list(model.slide_index(pkg).values())[0].basename

    icerik_parcalari = []
    for baslik in BASLIKLAR:
        r = authoring.add_slide(pkg, sablon, scene=None)
        compose.compose_slide(pkg, r["new_slide"], "content",
                              title=baslik, eyebrow=baslik, body="Govde metni.")
        icerik_parcalari.append(pkg.slide_part_for(r["new_slide"]))

    # Acilir katman: icerik slaydinin uzerine
    katman = authoring.add_layer(pkg, model.slide_index(pkg)[icerik_parcalari[0]].basename,
                                 "Neden Onemli", text="Bu maddenin aciklamasi.")

    soru = authoring.add_question(pkg, None, "Hangisi dogru?",
                                  ["A secenegi", "B secenegi", "C secenegi"], [0])
    coklu = authoring.add_question(pkg, None, "Hangileri dogru?",
                                   ["A", "B", "C", "D", "E"], [0, 1])
    surukle = authoring.add_drag_question(
        pkg, "Her ogeyi dogru kutuya surukle.",
        {"Kutu bir": ["Kisa ad", "Kisa ad"], "Kutu iki": ["Kisa ad", "Kisa ad"]})
    taahhut = authoring.add_text_question(pkg, "Bir somut adim yaz.", None)

    pkg.save(yol, backup=False)
    return {"icerik": icerik_parcalari, "katman": katman, "soru": soru,
            "coklu": coklu, "surukle": surukle, "taahhut": taahhut}


def main() -> int:
    if not BLANK.is_file():
        print("Kaynak yok: %s" % BLANK)
        return 2
    yol = Path(tempfile.gettempdir()) / "yeni_modul.story"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        kurulan = kur(yol)
        pkg = StoryPackage(yol)

    kirmizi: list[str] = []

    def bak(etiket: str, madde: str, tamam: bool, olculen: str) -> None:
        print("  %-28s %-9s %s" % (etiket, madde, olculen))
        if not tamam:
            kirmizi.append("%s (%s)" % (etiket, madde))

    print("Yeni modul kuruldu: %d slayt" % len(model.slide_index(pkg)))
    print()

    # 1 -- kopuk tetikleyici
    kopuk = completeness.dangling_triggers(pkg)
    bak("kopuk tetikleyici", "#1", not kopuk,
        "%d (beklenen 0)" % len(kopuk))

    # 2 -- olu puan degiskeni
    olu = 0
    for ad in list(pkg._order):
        if ad.endswith(".xml"):
            olu += pkg.read(ad).decode("utf-8", "replace").count(OLU_PUAN_GUID)
    bak("olu puan degiskeni", "#4", olu == 0, "%d referans (beklenen 0)" % olu)

    # 3 -- intrProps kendi katmanlarini gosteriyor mu
    cozulen = cozulmeyen = 0
    for part, ref in model.slide_index(pkg).items():
        root = pkg.parse(part)
        kl = root.find("sldLayerLst")
        ic = {k.get("g") for k in (list(kl) if kl is not None else [])}
        for props in root.iter("intrProps"):
            for alan in ("corFbG", "incFbG"):
                g = props.get(alan) or ""
                if not g or g.startswith("00000000"):
                    continue
                if g in ic:
                    cozulen += 1
                else:
                    cozulmeyen += 1
    bak("intrProps cozuluyor", "#5", cozulmeyen == 0 and cozulen > 0,
        "%d cozulen / %d cozulmeyen" % (cozulen, cozulmeyen))

    # 4 -- taahhut slaydinda gezinme acik mi
    t_part = pkg.slide_part_for(kurulan["taahhut"]["new_slide"])
    nav = next(pkg.parse(t_part).iter("navData"), None)
    acik = (nav is not None and nav.get("next") == "true"
            and nav.get("submit") == "false")
    bak("taahhut gezinmesi", "#2", acik,
        "next=%s submit=%s" % (nav.get("next") if nav is not None else "?",
                               nav.get("submit") if nav is not None else "?"))

    # 5 ve 6 -- acilir katman: kapaniyor mu, yabanci metin var mi
    k_part = pkg.slide_part_for(kurulan["katman"]["slide"])
    kok = pkg.parse(k_part)
    hedef = next((k for k in (kok.find("sldLayerLst") or [])
                  if k.get("g") == kurulan["katman"]["layer_guid"]), None)
    trig = sum(len(tl) for tl in hedef.iter("trigLst")) if hedef is not None else 0
    bak("katman kapatma trig", "#8", trig > 0, "%d tetikleyici" % trig)

    metinler = []
    if hedef is not None:
        for sh, _t, doc, _s in model._iter_text_shapes(hedef):
            m = model._doc_text(doc).strip()
            if m:
                metinler.append(m)
    yabanci = [m for m in metinler
               if m not in ("Bu maddenin aciklamasi.", "Devam")]
    bak("katmanda yabanci metin", "#11", not yabanci,
        "%d (%s)" % (len(yabanci), yabanci[:2] or "yok"))

    # 7 -- slayt adlari ayri mi
    adlar = [pkg.parse(p).get("name") or "" for p in kurulan["icerik"]]
    bak("slayt adlari ayri", "#15", len(set(adlar)) == len(adlar),
        "%d slayt / %d ayri ad" % (len(adlar), len(set(adlar))))

    # 8 -- Turkce buyuk harf
    buyuk = compose.buyuk("Pozisyon Alma ve Kayma")
    bak("Turkce buyuk harf", "#13", buyuk.startswith("POZİ"),
        repr(buyuk[:12]))

    print()
    if kirmizi:
        print("KIRMIZI: " + ", ".join(kirmizi))
        print("Bu siniflar 2026-09-06'da duzeltilmisti; biri geri gelmis.")
        return 1
    print("Yeni bir modul, duzeltilen sekiz sinifin hicbirini tasimiyor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
