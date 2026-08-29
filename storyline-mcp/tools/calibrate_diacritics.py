"""Türkçe diakritikleri satır kutusunu büyütüyor mu -- ve hangi ucundan?

`estimate_text_height` ASCII ile kalibre edildi: calibrate_text.py'nin ornek
dizgilerinin hepsi ASCII ("Devam Et", "Nereden devam etmek istersin?"). Uretim
corpus'u ise Turkce. K4'un tam tanimi: kolay veriyle kurulan kalibrasyon,
korudugunu sandigi seyi olcmez.

TEK BIR "DIAKRITIKLI vs DIAKRITIKSIZ" CIFTI YETMEZ, cunku diakritikler tek
eksende degil. Hepsi tek dizgide karistirilsaydi yalnizca "fark var" ogrenilir,
farkin satir kutusunun HANGI UCUNDAN geldigi ogrenilmezdi -- ve duzeltme o
ayrima bagli:

    ust     g-breve, u/o-umlaut, i-nokta   ascent'i buyutur
    alt     s-cedilla, c-cedilla kuyrugu   descent'i buyutur
    hicbiri noktasiz i                     KONTROL: ayni harf sayisi,
                                           diakritik yok, ASCII 'i' ile ayni
                                           yukseklik beklenir

Ikinci eksen: BUYUK I-nokta. Turkce'de buyuk harfin noktasi cap yuksekliginin
USTUNE cikar, ve basliklar buyuk harf yaziliyor. En cok kesilme goruilen yer
degil ama en gorunur yer, ve tam 38pt bolgesinde.

ASCII KONTROL DIZGILERI de var ve olcumun kendisini dogrularlar: ayni puntoda
iki OZDES ASCII dizgi ayni yuksekligi vermeli. Vermiyorsa olcum gurultulu ve
diakritik farki okunamaz -- once gurultu giderilir, sonra fark okunur.

KAPI. Bu dosya yalnizca dosyayi URETIR. Olcum, Storyline dosyaya GERCEKTEN
yazdiktan sonra yapilir ve bunu tools/dirty_gate.py dogrular. Kapi acilmadan
okunan her sayi, Storyline'in ne yaptigini degil deneyin kosmadigini gosterir
-- bu deney bir kez tam olarak oyle gecersiz oldu.

    python tools/calibrate_diacritics.py            dosyayi uret
    python tools/calibrate_diacritics.py --olc      Storyline yazdiktan SONRA
"""

from __future__ import annotations

import argparse
import shutil
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from storyline_mcp import compose, model, shapes
from storyline_mcp.authoring import _apply_text
from storyline_mcp.package import StoryPackage

BLANK = ROOT.parent / "test" / "bos.story"
OUT = ROOT.parent / "test" / "_referans" / "KALIBRE_DIAKRITIK.story"

BOX_W = 300.0
# Kutu KASTEN dar: metin sarmali ki satir sayisi ve satir yuksekligi
# gorunur olsun. Genis kutuda her sey tek satir kalir ve olcu hicbir sey
# soylemez.
BOX_H = 44.0

# ESLESTIRILMIS CIFTLER. Her Turkce dizginin, karakter karakter ayni
# uzunlukta bir ASCII ikizi var ve aralarindaki TEK fark diakritik.
#
# Neden ikiz: kutu buyume modunda olculuyor, yani yukseklik hem satir
# yuksekligine hem SATIR SAYISINA bagli. Farkli uzunluktaki iki dizgi farkli
# sarabilir ve cikan fark "daha yuksek satir" degil "daha cok satir" olur --
# olcu ayni sayiyi verir, sebep baskadir.
#
# Neden uc ayri grup: diakritikler tek eksende degil. Hepsi tek dizgide
# karistirilsaydi yalnizca "fark var" ogrenilirdi; hangi UCTAN geldigi
# ogrenilmezdi ve estimate_text_height'i duzeltirken neyin duzeltildigi
# belirsiz kalirdi.
CIFTLER = [
    # ad,        turkce,                ascii ikiz,           ne olculuyor
    ("ust",      "güğüm öğün üzüm",     "gugum ogun uzum",
     "ascent: breve + umlaut, hepsi cizginin USTUNDE"),
    ("alt",      "çiçek şişe çamur",    "cicek sise camur",
     "descent: cedilla kuyrugu, hepsi cizginin ALTINDA"),
    ("noktasiz", "kırlı lımon dılımı",  "kirli limon dilimi",
     "KONTROL: noktasiz i, diakritik yok -- fark BEKLENMEZ"),
    ("buyukI",   "İSTİKLAL İÇİN İĞNE",  "ISTIKLAL ICIN IGNE",
     "buyuk I-nokta: cap yuksekliginin USTUNE cikar"),
]

# Olcunun kendi gurultusu. Iki OZDES ASCII dizgi ayni yuksekligi vermeli;
# vermiyorsa diakritik farki gurultunun altinda kalir ve okunamaz.
GURULTU = ("gurultu-a", "gurultu-b", "kirli limon dilimi")

# Uretilecek butun kutular: (ad, dizgi).
GRUPLAR = (
    [(GURULTU[0], GURULTU[2]), (GURULTU[1], GURULTU[2])]
    + [(f"{ad}-tr", tr) for ad, tr, _a, _n in CIFTLER]
    + [(f"{ad}-as", asc) for ad, _tr, asc, _n in CIFTLER]
)

PUNTOLAR = [13, 17, 24, 38]


def uret() -> Path:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BLANK, OUT)
    pkg = StoryPackage(OUT)
    index = model.slide_index(pkg)
    slaytlar = [p for p in index]
    if len(slaytlar) < len(PUNTOLAR):
        raise SystemExit(f"{BLANK.name} icinde {len(PUNTOLAR)} slayt yok.")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for part, punto in zip(slaytlar, PUNTOLAR):
            root = pkg.parse(part)
            compose.clear_slide(root)
            sw, sh = shapes.slide_size(root)

            zemin = shapes.clone_shape(shapes.find_seed(pkg, "rect")[0],
                                       name="Zemin")
            shapes.set_shape_slide_size(zemin, sw, sh)
            shapes.set_loc(zemin, 0, 0, sw, sh)
            shapes.set_fill(zemin, "#FFFFFF")
            shapes.add_shape(root, zemin, to_back=True)
            _apply_text(root, zemin, "")

            y = 10.0
            yukseklik = (sh - 20.0) / len(GRUPLAR)
            for ad, dizgi in GRUPLAR:
                kutu = shapes.clone_shape(
                    shapes.find_seed(pkg, "textBox")[0],
                    # AD, olcumun anahtari: geri okurken hangi satirin hangi
                    # grup oldugu addan bulunur, siradan degil -- Storyline
                    # sekilleri yeniden siralayabilir.
                    name=f"K_{punto}_{ad}")
                shapes.set_shape_slide_size(kutu, sw, sh)
                shapes.set_loc(kutu, 30, y, 30 + BOX_W, y + BOX_H)
                # BUYUME ACIK: olculecek sey tam olarak bu -- Storyline
                # kutuyu metnin gercek yuksekligine cekerse, fark dosyadan
                # okunur.
                shapes.set_text_flow(kutu, vertical="t", grow=True)
                shapes.add_shape(root, kutu)
                _apply_text(root, kutu, dizgi, color="#000000", size=punto)
                y += yukseklik
            pkg.replace_xml(part, root)
        rapor = pkg.save(OUT, backup=False)

    print(f"uretildi: {OUT}")
    print(f"  {len(PUNTOLAR)} slayt (punto {PUNTOLAR}), "
          f"slayt basina {len(GRUPLAR)} kutu, kutu {BOX_W:.0f}x{BOX_H:.0f}")
    print(f"  verified={rapor['verified']['ok']}")
    print()
    print("SIRADAKI ADIM ELLE:")
    print(f"  1. {OUT.name} dosyasini Storyline'da ac")
    print("  2. herhangi bir sekli bir tik oynat (baslikta * gorunsun)")
    print("  3. Ctrl+S, sonra kapat")
    print()
    print("Sonra: python tools/calibrate_diacritics.py --olc")
    print("Olcum, dosyanin GERCEKTEN degistigini dogrulamadan baslamaz.")
    return OUT


def _buyume_kaniti(punto: int, grup: str) -> tuple[float, float] | None:
    """(dosyadaki kutu yüksekliği, metnin gerektirdiği yükseklik).

    Mekanizmanin kostugunu kanitlamak icin: metin kutuya sigmiyorsa ve kutu
    yine de yazildigi gibi duruyorsa, Storyline yeniden olcmemis demektir.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pkg = StoryPackage(OUT)
        for part, _ref in model.slide_index(pkg).items():
            root = pkg.parse(part)
            shape_list = root.find("shapeLst")
            for shape in list(shape_list) if shape_list is not None else []:
                if (shape.get("name") or "") != f"K_{punto}_{grup}":
                    continue
                rect = shapes.shape_rect(shape)
                text = model.shape_text(root, shape.get("g") or "").strip()
                if not rect or not text:
                    return None
                genislik, _h = shapes.slide_size(root)
                gereken = shapes.estimate_text_height(
                    text, float(punto), rect[2] - rect[0], genislik)
                return rect[3] - rect[1], gereken
    return None


def olc() -> int:
    if not OUT.is_file():
        print(f"Dosya yok: {OUT}\nOnce: python tools/calibrate_diacritics.py")
        return 2

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pkg = StoryPackage(OUT)
        olculen: dict[int, dict[str, float]] = {}
        for part, _ref in model.slide_index(pkg).items():
            root = pkg.parse(part)
            shape_list = root.find("shapeLst")
            for shape in list(shape_list) if shape_list is not None else []:
                ad = shape.get("name") or ""
                if not ad.startswith("K_"):
                    continue
                _k, punto, grup = ad.split("_", 2)
                rect = shapes.shape_rect(shape)
                if rect:
                    olculen.setdefault(int(punto), {})[grup] = rect[3] - rect[1]

    if not olculen:
        print("Kalibrasyon kutusu bulunamadi.")
        return 2

    # MEKANIZMA POZITIF KONTROLU -- gurultuden de once.
    #
    # dirty_gate dosyanin GERCEKTEN degistigini kanitlar (2.2 MB -> 1.0 MB,
    # Storyline paketi bastan yazdi). Ama "yazdi" ile "OLCTUGUMUZ SEYI yapti"
    # ayni cumle degil, ve burada tam olarak ayrildilar: kutularin hepsi
    # autoFit="resize" tasimaya DEVAM ediyor (Storyline bayragi korudu) ama
    # hicbirinin yuksekligi degismedi -- en buyuk puntoda, metnin kutuya
    # sigmasi matematiksel olarak imkansizken bile.
    #
    # Yani Storyline buyumeyi CIZIM ANINDA hesapliyor ve dosyaya geri
    # YAZMIYOR. Dosya, yazilan kutuyu tutuyor; cizilen kutuyu degil.
    #
    # Bu kontrol olmasaydi cikti "+0.00" dolu bir tablo olurdu ve "diakritik
    # etkilemiyor" diye okunurdu -- bu deneyin UCUNCU kez ayni bicimde
    # gecersiz olmasi. Kutu buyumek ZORUNDA oldugu halde buyumediyse rapor
    # BASILMAZ.
    en_buyuk = max(olculen)
    taban_ad = f"{CIFTLER[0][0]}-as"
    kanit = _buyume_kaniti(en_buyuk, taban_ad)
    if kanit is not None:
        yazilan, gereken = kanit
        print(f"MEKANIZMA KONTROLU ({en_buyuk}pt, {taban_ad}): kutu "
              f"{yazilan:.1f} birim, metin {gereken:.1f} birim istiyor.")
        if gereken > yazilan + 1.0:
            print("\nOLCUM GECERSIZ. Kutu buyumek ZORUNDAYDI ve buyumedi:\n"
                  "Storyline autoFit bayragini koruyor ama hesapladigi\n"
                  "yuksekligi dosyaya geri yazmiyor. Yani bu yontem metin\n"
                  "yuksekligini OLCEMEZ -- dosyadan okunan sey yazilan kutu,\n"
                  "cizilen kutu degil.\n\n"
                  "Diakritik farki hakkinda cikan her sayi sifir olurdu ve\n"
                  "'fark yok' diye okunurdu. DOGRU CEVAP: OLCULEMEDI.\n"
                  "Olcmek icin dosya degil GORUNTU gerekir (tools/shoot.py ya\n"
                  "da gozle), cunku fark yalnizca cizimde var.")
            return 1
        print()

    # ONCE GURULTU. Iki ozdes ASCII dizgi ayni yuksekligi vermiyorsa
    # diakritik farki bu gurultunun altinda kalir ve okunamaz.
    a, b, _t = GURULTU
    print(f"{'punto':<7}{'ozdes-a':>10}{'ozdes-b':>10}   olcu gurultusu")
    gurultulu = []
    for punto in sorted(olculen):
        x, y = olculen[punto].get(a), olculen[punto].get(b)
        if x is None or y is None:
            continue
        fark = abs(x - y)
        if fark > 0.01:
            gurultulu.append(punto)
        print(f"{punto:<7}{x:>10.2f}{y:>10.2f}   "
              f"{'temiz' if fark <= 0.01 else f'FARK {fark:.2f}'}")
    if gurultulu:
        print(f"\nOLCUM GURULTULU ({gurultulu}): iki OZDES dizgi ayni "
              "yuksekligi vermiyor.\nDiakritik farki bu gurultunun altinda "
              "kalabilir; sayilar asagida ama\nOKUNMAMALI -- once sebebi "
              "bulunmali.")

    print(f"\n{'punto':<7}{'grup':<10}{'turkce':>9}{'ascii':>9}{'fark':>9}"
          "   ne olculuyor")
    for punto in sorted(olculen):
        for ad, _tr, _as, ne in CIFTLER:
            t = olculen[punto].get(f"{ad}-tr")
            c = olculen[punto].get(f"{ad}-as")
            if t is None or c is None:
                continue
            print(f"{punto:<7}{ad:<10}{t:>9.2f}{c:>9.2f}{t - c:>+9.2f}   "
                  f"{ne[:42]}")

    print("\nFARK = turkce - ascii, AYNI karakter sayisinda. Sifirdan buyukse")
    print("diakritik satir kutusunu buyutuyor. 'noktasiz' grubunda SIFIR")
    print("beklenir; beklenmiyorsa olcu diakritigi degil baska bir sey goruyor.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--olc", action="store_true",
                        help="Storyline yazdiktan SONRA olc")
    args = parser.parse_args()
    if args.olc:
        return olc()
    uret()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
