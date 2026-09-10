"""Kurs bir PUAN uretebiliyor mu -- ve bunu olcen iki olcu ayakta mi.

NICIN VAR. Bu iki kusur sinifi "arac basariyla dondu" halinde dogar,
yani hicbir cagri kirmizi olmadan kurs bozuk cikar:

  cevaplanamaz soru   `add_question` aralik disi bir `correct` kabul
                      ediyordu -- tohum kolu (`bundled:`) denetimden
                      ONCE donuyordu ve o kol tam olarak AJANIN kullandigi
                      kol (panel promptu "template VERME" diyor). Uretilen
                      sey hicbir secenegi dogru isaretlenmemis bir soru:
                      ogrenci ne isaretlerse yanlis alir.

  puanlama zinciri    soru -> quiz -> sonuc slaydi -> LMS. Diskteki 51
                      kurs okundu (2026-09-10): 24'unde quizLst tek ve
                      BOS. Butun arac cagrilari "ok" donmustu.

BU KAPI URETICIYI DEGIL OLCUYU KORUYOR. Kurs kalitesi modelin ciktisina
bagli ve kapilar model cagirmaz. Korunan sey su: olcu sessizce olurse
her kurs temiz gorunur. `tools/ogretim_kapi.py` ile ayni bicim.

DORT AYAK:
  1 CIPA        saglam soru isaretlenmemeli (yanlis pozitif yok)
  2 EKILI       dogruluk isareti silinmis soru GORULMELI
  3 KAPSAM      surukle-birak sorusu cevapsiz SAYILMAMALI -- ilk surum
                tam olarak bunu yapiyordu ve 51 kursun 18'inde birer
                yanlis pozitif uretiyordu
  4 YAZMA KAPISI aralik disi `correct` REDDEDILMELI, ve tohum kolundan da

Ucuncusu olmadan ilk ikisi "choices tasiyan her sey" diyen kor bir
olcuyle de gecilirdi.

    python tools/puanlanabilirlik.py
"""

from __future__ import annotations

import pathlib
import shutil
import sys
import warnings

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

warnings.simplefilter("ignore")

from storyline_mcp import authoring, model, puanlama          # noqa: E402
from storyline_mcp.package import StoryPackage, StoryError    # noqa: E402

BLANK = ROOT.parent / "test" / "bos.story"
CANARY = ROOT.parent / "test" / "_canary"
KOSAMADI = 3


def _kok(pkg, slayt):
    for part in pkg._parts:
        if (part.endswith("/" + slayt) and part.startswith("story/slides/")
                and "_rels" not in part):
            return part, pkg.parse(part)
    raise KeyError(slayt)


def kanarya() -> list[str]:
    kusur: list[str] = []
    CANARY.mkdir(parents=True, exist_ok=True)
    yol = CANARY / "puanlanabilirlik.story"
    shutil.copy2(BLANK, yol)
    pkg = StoryPackage(yol)

    # 1. CIPA: saglam soru.
    saglam = authoring.add_question(
        pkg, None, "Saglam soru", ["a", "b", "c", "d"], [1],
        eyebrow="B", feedback={"correct": "E", "incorrect": "H"})["new_slide"]
    b = puanlama.cevaplanamaz(pkg, model.slide_index(pkg))
    print(f"cipa        : saglam soru {'TEMIZ' if not b else 'ISARETLENDI'}")
    if b:
        kusur.append(f"YANLIS POZITIF: saglam soru cevapsiz sayiliyor ({b})")

    # 2. EKILI KUSUR: dogruluk isaretini sil. Yazma kapisi artik aralik
    # disi degeri reddettigi icin kusur ARTEFAKTA ekiliyor -- kapi ile
    # olcu ayri seyler ve ayri sinaniyor.
    part, root = _kok(pkg, saglam)
    silinen = 0
    for intr in root.iter():
        if intr.tag != "freePickOneIntr":
            continue
        for secenek in (intr.find("choices") or []):
            sd = secenek.find("scoringData")
            if sd is not None and (sd.get("correct") or "").lower() == "true":
                sd.set("correct", "false")
                silinen += 1
    pkg.replace_xml(part, root)
    if not silinen:
        kusur.append("KANARYA KURULAMADI: silinecek dogru isareti bulunamadi "
                     "-- olcu bos bir dosyada kosuyor olabilir")
    b2 = puanlama.cevaplanamaz(pkg, model.slide_index(pkg))
    print(f"ekili kusur : {'YAKALANDI' if b2 else 'KACTI'} "
          f"({silinen} isaret silindi)")
    if not b2:
        kusur.append("OLCU KOR: dogruluk isareti silinmis soru cevapsiz "
                     "sayilmiyor -- cevaplanamaz sorular gorunmez")

    # 3. KAPSAM: surukle-birak cevapsiz SAYILMAMALI.
    yol2 = CANARY / "puanlanabilirlik_drag.story"
    shutil.copy2(BLANK, yol2)
    pk2 = StoryPackage(yol2)
    try:
        authoring.add_drag_question(
            pk2, "Surukle", {"A": ["x", "y"], "B": ["z"]},
            eyebrow="B", feedback={"correct": "E", "incorrect": "H"})
    except (StoryError, TypeError) as exc:
        print(f"kapsam      : KURULAMADI ({str(exc)[:60]})")
        kusur.append(f"KANARYA KURULAMADI: surukle-birak sorusu kurulamadi "
                     f"({str(exc)[:60]}) -- kapsam ayagi olculmedi")
    else:
        b3 = puanlama.cevaplanamaz(pk2, model.slide_index(pk2))
        print(f"kapsam      : surukle-birak {'TEMIZ' if not b3 else 'YANLIS ISARETLENDI'}")
        if b3:
            kusur.append(
                "KAPSAM KAYMASI: surukle-birak sorusu cevapsiz sayiliyor -- "
                "dogrulugu scoringData'da tutmuyor, beyaz liste bozulmus")

    # 4. YAZMA KAPISI, ve TOHUM KOLUNDAN. Kacan kol buydu.
    yol3 = CANARY / "puanlanabilirlik_kapi.story"
    shutil.copy2(BLANK, yol3)
    pk3 = StoryPackage(yol3)
    for etiket, deger in (("aralik disi", [9]), ("negatif", [-1]), ("bos", [])):
        try:
            authoring.add_question(
                pk3, None, "S", ["a", "b", "c", "d"], deger,
                eyebrow="B", feedback={"correct": "E", "incorrect": "H"})
            print(f"yazma kapisi: {etiket} correct KABUL EDILDI (YANLIS)")
            kusur.append(
                f"YAZMA KAPISI ACIK: correct={deger} kabul ediliyor ve "
                f"cevaplanamaz soru uretiyor. Denetim `bundled:` dalindan "
                f"SONRA duruyor olabilir -- ajanin kolu o.")
        except StoryError:
            print(f"yazma kapisi: {etiket} correct REDDEDILDI (dogru)")
    return kusur


def main() -> int:
    if not BLANK.exists():
        print(f"KOSAMADI: fikstur yok ({BLANK}). Puanlanabilirlik olculemedi "
              f"-- bu 'gecti' DEGIL, 'bakilmadi'.")
        return KOSAMADI
    kusur = kanarya()
    if kusur:
        print("\nKAPI KALDI:")
        for k in kusur:
            print(f"  - {k}")
        return 1
    print("\nkapi gecti: olcu ekili kusuru goruyor, saglami ve surukle-birakı "
          "isaretlemiyor, yazma kapisi aralik disini reddediyor")
    print("KAPSAM: bu kapi kursun PUANLANABILIR oldugunu soylemez, olcunun\n"
          "        AYAKTA oldugunu soyler. Kursun kendi sayisi audit'te:\n"
          "        cevaplanamaz_sorular + puanlama_zinciri.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
