"""Slaytta hiçbir şeyin olmadığı alan: en büyük yatay bant ve toplam oran.

GÖREV 5 (tipografi ve tema) için ölçülmüş başlangıç referansı. Buradaki sayı
bir hatanın kanıtı değil, işin nereden başlayacağının kaydı: tipografi işine
girildiğinde bu tabana bakılır, yeniden ölçmek gerekmez.

ÖLÇÜLEN (2026-08-14, tools/variety.py DECK'i, content düzeni, altı varyant):

                        en buyuk bant     toplam bos
    maddeli slaytlar     %0 - %7           %0 - %26     (5 slayt)
    maddesiz slaytlar   %10 - %41         %26 - %54     (5 slayt)

Yani seyrek içerikli bir slaytta sayfanın yarıdan fazlası boş kalabiliyor.
Sebep yerleşimde değil: `content` düzeni üç küçük bloğu (üst etiket, başlık,
gövde) bütün çerçeveye dağıtıyor ve içerik azaldığında punto ölçeği yukarı
çıkmıyor. Bir tasarımcı altı kelimelik bir gövdeyi 16:9 bir çerçeveye koyarken
yazıyı büyütür; motor büyütmüyor, boşluğu büyütüyor.

İki grup %26'da değiyor: ayrım kategorik değil, süreklilik. Maddeli bir slayt
da az maddeyle seyrekleşiyor. Tipografi işi "maddesiz slaytları düzelt" diye
değil, "içerik yoğunluğuna göre ölçeklen" diye kurulmalı.

Bu, varyant motorunun getirdiği bir gerileme DEĞİL -- GÖREV 4 öncesinde de
vardı, ilk g2 kursunun "Parola Hijyeni" slaydında aynı boşluk görünüyor.

Tam genişlikte şeritler (arka plan, üst şerit, alt bant) banda sayılmaz:
slaydın her yerine değen bir şerit, boş bir bandı teknik olarak doldurur ama
gözün gördüğü boşluğu doldurmaz.

    python tools/deadband.py                    tabanla karsilastir
    python tools/deadband.py --story kurs.story baska bir kursu olc
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from storyline_mcp import model, shapes
from storyline_mcp.package import StoryPackage
import scope

# Olculen taban: TOPLAM bos oran.
#
# Yogunluk olceklemesinden SONRA yenilendi. Yenilemek zorunlu: guard tek
# yonlu (yalnizca kotulesmeyi gorur), dolayisiyla eski taban birakilsaydi
# %44'ten %54'e geri donus hicbir sey bagirmadan gecerdi -- iyilesmeyi
# kaydetmemek, onu koruyacak testi de kaybetmek demek.
#
#   once  (2026-08-14, olcekleme yok)   maddeli %0-%26   maddesiz %26-%54
#   sonra (yogunluk olcegi devrede)     maddeli %0-%19   maddesiz %24-%44
# YENIDEN OLCULDU (2026-08-17), coverage'in EMPTY_BASELINE'i ile AYNI
# gerekcede ve ayni turda. Ikisi de ayni olcuyu (bos alan) farkli kesitte
# alir, dolayisiyla ayri ayri yenilenmeleri ikisini ayristirirdi.
#
# Gerekce ozeti: eski taban yeniden uretilemedi. Olcum, yerlesim ve yapisal
# sabitlerin hepsi tek tek elendi; `content` icin rejim farki BULUNDU
# (TYPE_LADDER merdiveni, %38 -> %52) ve merdiven tabandan yeni. Kalan
# duzenler icin provenance yok ve kayit ACIK. Ayrinti coverage.py'de.
#
# "maddesiz" ust ucu %46 -> %52: merdivenin bedeli. Merdiven tipografik
# tutarlilik aliyor (uretilmis kursta 16 farkli punto -> 8 basamak),
# doldurma veriyor. Takas BILINCLI; bedeli ilk kez olculdu.
_ESKI_TABAN_2026_08_16 = {"maddeli": (0, 25), "maddesiz": (26, 46)}
BASELINE = {"maddeli": (0, 25), "maddesiz": (26, 52)}
#
# PUNTO MERDIVENI SONRASI (2026-08-16). Iki yonlu degisti, ikisi de kayitli:
#
#     maddesiz  %44 -> %46   artis (kucuk)
#     maddeli   %19 -> %25   artis
#
# Artis bir GERILEME DEGIL, ve bunu ayirt eden sey iki ayri sayinin varligi:
# ayni slaytta EN BUYUK BANT %5te kaldi. Yani %25lik bosluk tek bir cukurda
# degil, alti kucuk aralikta dagilmis -- blok aralari, yani ritim. Tek bir
# ozet sayi tutulsaydi bu "kotulesme" diye okunurdu.
#
# Sebep merdivenin KABALIGI degil: govde araligina bir ara basamak (15pt)
# eklenip olculdu ve sayilar HIC degismedi. Boyle bir notu "muhtemelen
# kabalik" diye birakmak, birinin ileride bosuna basamak eklemesine yol
# acardi.
FULL_WIDTH = 0.97   # bunun ustu serittir, bant doldurmaz
BAND = (8, 92)      # CEILING .. FLOOR


def dead_band(pkg: StoryPackage, part: str) -> tuple[int, int, int]:
    """(en büyük boş bant, toplam boş oran, banda katılan şekil sayısı).

    İkisi birden ölçülür çünkü tek başına ilki yanıltıyor: ortalanmış bir
    buton, aynı büyüklükteki boşluğu ikiye bölüyor ve "en büyük bant" yarıya
    iniyor. Ölçüldü -- bir slayt %41, aynı seyreklikteki bir başkası %10, tek
    fark butonun boşluğun ortasına düşmesi. Toplam boş oran o bölünmeden
    etkilenmez.
    """
    root = pkg.parse(part)
    shape_list = root.find("shapeLst")
    if shape_list is None or not len(shape_list):
        return (0, 0, 0)
    width, height = shapes.slide_size(root)
    rows = [False] * 100
    counted = 0
    for shape in shape_list:
        rect = shapes.shape_rect(shape)
        if not rect:
            continue
        left, top, right, bottom = rect
        if (right - left) * (bottom - top) > 0.92 * width * height:
            continue
        if (right - left) / width > FULL_WIDTH:
            continue
        counted += 1
        for y in range(int(top / height * 100),
                       min(int(bottom / height * 100) + 1, 100)):
            rows[y] = True
    best = run = total = 0
    for y in range(*BAND):
        run = 0 if rows[y] else run + 1
        best = max(best, run)
        total += not rows[y]
    return best, round(total / (BAND[1] - BAND[0]) * 100), counted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--story",
                        default=str(ROOT.parent / "test" / "_canary" / "variety.story"))
    parser.add_argument("--build", action="store_true",
                        help="olcmeden once variety.py ile kursu yeniden kur")
    args = parser.parse_args()

    if args.build:
        import variety
        variety.build()

    story = Path(args.story).resolve()
    if not story.is_file():
        print(f"Proje yok: {story}\n(once: python tools/variety.py)")
        return 2

    pkg = StoryPackage(story)
    groups: dict[str, list[tuple[int, int]]] = {"maddeli": [], "maddesiz": []}
    print(f"{'slayt':<26}{'sekil':>6}{'en buyuk bant':>15}{'toplam bos':>12}")
    for part, ref in model.slide_index(pkg).items():
        band, total, count = dead_band(pkg, part)
        if not count:
            continue
        # Kart tasiyan slaytlar cok daha fazla sekil koyar; ayrimi sekil
        # sayisindan degil, kartlarin varligindan okumak icin esik yeterli.
        kind = "maddeli" if count >= 8 else "maddesiz"
        groups[kind].append((band, total))
        print(f"{ref.name[:25]:<26}{count:>6}{band:>14}%{total:>11}%")

    print()
    drift = []
    for kind, seen in groups.items():
        if not seen:
            continue
        low, high = min(t for _b, t in seen), max(t for _b, t in seen)
        was_low, was_high = BASELINE[kind]
        mark = ""
        if low < was_low - 3 or high > was_high + 3:
            mark = f"  <- taban %{was_low}-%{was_high}"
            drift.append(kind)
        print(f"  {kind:<10} toplam bos %{low}-%{high}  "
              f"({len(seen)} slayt){mark}")
    if drift:
        print(f"\nTaban disina cikti: {', '.join(drift)}. Tipografi isi "
              "bittiyse BASELINE'i guncelleyin; bitmediyse bir gerileme var.")
        scope.show("deadband")
        return 1
    print("\nTabanla uyumlu.")
    scope.show("deadband")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
