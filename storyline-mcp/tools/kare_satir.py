"""Karede satır sayar -- ve sayısı DOĞRULANMADAN sabit üretmez.

Bu dosya bir KOLAYLIK bilesenidir ve K13 gereği oyle davranir:

    kosunun gecerliligi hicbir kolaylik bilesenine baglanamaz, ve bir
    kolaylik bileseninin ciktisi DOGRULANMADAN olcume giremez.

Neden bu kural burada yazili. Piksel sayaci uc kez ayni sinifta yanildi:

    C1 (720)   pencere ayarina gore kah 3 kah 4 saydi. Gozle 4'tu. 3
               alinsaydi oran 0.79 yerine 0.59 cikardi -- TERS yon.
    D1/D2      renkli metni hic gormedi ("0 satir") cunku yalnizca KOYU
               piksel ariyordu. Sifir bir olcum degil, dedektorun korlugu.
    1920 turu  bindiren kutularda tutarsiz adim verdi (28.9 birim, oysa
               ayni puntonun temiz olcumu 69.6).

Ilk ikisi gozle yakalandi, ucuncusu tutarsiz oldugu icin. DORDUNCUSU
TUTARLI AMA YANLIS olursa yakalanmaz -- ve o sayi dogrudan
CHAR_WIDTH_RATIO'ya girer.

O yuzden sayac artik TEK BASINA sabit uretmiyor. Cagiran, girdi
spesifikasyonundan gelen BEKLENEN satir sayisini vermek zorunda; sayim
onunla uyusmazsa arac hicbir turetilmis sayi basmaz ve gozle sayilmasini
soyler. Uyusursa sayim yalnizca DOGRULANMIS olur -- hizi verir, dogrulugu
girdi spesifikasyonu verir.

    python tools/kare_satir.py kare.png --bolge 445 820 340 620 --bekle 6
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def slayt_bandi(px, W, H):
    """Oynatıcıdaki slaydın beyaz alanı: (x_bas, x_son, y_ust)."""
    def run_at(y, x=800):
        if px[x, y] != (255, 255, 255):
            return None
        a = x
        while a > 0 and px[a - 1, y] == (255, 255, 255):
            a -= 1
        b = x
        while b < W - 1 and px[b + 1, y] == (255, 255, 255):
            b += 1
        return (a, b)
    for y in range(180, H):
        r = run_at(y)
        if r and 380 < r[0] < 470 and 1180 < r[1] < 1290:
            return r[0], r[1], y
    return None


def satirlar(px, x0, x1, y0, y1, *, esik=2, birlestir=8):
    """Yatay mürekkep bantları, yakın olanlar birleştirilmiş.

    RENK BAGIMSIZ: beyaz olmayan her piksel murekkeptir. Yalnizca koyu
    piksel aramak, yesil/kirmizi metni gormedi ve "0 satir" dedi.
    """
    ham, icinde, bas = [], False, 0
    for y in range(y0, y1):
        n = sum(1 for x in range(x0, x1) if px[x, y] != (255, 255, 255))
        if n > esik and not icinde:
            icinde, bas = True, y
        elif n <= esik and icinde:
            icinde = False
            ham.append((bas, y - 1))
    if icinde:
        ham.append((bas, y1 - 1))
    if not ham:
        return []
    out = [list(ham[0])]
    for a, z in ham[1:]:
        if a - out[-1][1] <= birlestir:
            out[-1][1] = z
        else:
            out.append([a, z])
    return [tuple(x) for x in out]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("kare")
    ap.add_argument("--bolge", nargs=4, type=int, required=True,
                    metavar=("X0", "X1", "Y0", "Y1"))
    ap.add_argument("--bekle", type=int, required=True,
                    help="GIRDI SPESIFIKASYONUNDAN gelen satir sayisi")
    ap.add_argument("--uzay", type=float, required=True,
                    help="slayt genisligi (birim)")
    ap.add_argument("--punto", type=float, required=True)
    args = ap.parse_args()

    from PIL import Image
    im = Image.open(args.kare).convert("RGB")
    W, H = im.size
    px = im.load()
    bant = slayt_bandi(px, W, H)
    if bant is None:
        print("Slayt alani bulunamadi -- kare oynatici karesi mi?")
        return 2
    x_bas, x_son, _ust = bant
    birim_px = (x_son - x_bas) / args.uzay

    x0, x1, y0, y1 = args.bolge
    g = satirlar(px, x0, x1, y0, y1)
    print(f"slayt {x_bas}..{x_son} px = {args.uzay:.0f} birim "
          f"({birim_px:.4f} px/birim)")
    print(f"bolge x{x0}..{x1} y{y0}..{y1}")
    print(f"  beklenen satir : {args.bekle}   (girdi spesifikasyonundan)")
    print(f"  sayilan satir  : {len(g)}")
    for i, (a, b) in enumerate(g, 1):
        print(f"     {i:>2}. y {a}..{b}")

    if len(g) != args.bekle:
        print(f"\nSAYIM DOGRULANMADI ({len(g)} != {args.bekle}).")
        print("Turetilmis sayi BASILMIYOR. Satirlari GOZLE sayin ve degeri")
        print("elle verin; bu sayacin uc kez yanildigi sinif tam olarak bu.")
        return 1

    adim_px = (g[-1][0] - g[0][0]) / (len(g) - 1) if len(g) > 1 else 0
    adim = adim_px / birim_px
    print(f"\nSAYIM DOGRULANDI. Turetilenler:")
    print(f"  satir adimi : {adim_px:.2f} px = {adim:.2f} birim")
    print(f"  leading     : {adim / args.punto:.3f}  (adim / punto)")
    print("\n(Bu sayilar yalnizca sayim girdi spesifikasyonuyla UYUSTUGU icin")
    print(" basildi. Uyusmasaydi arac hicbir sey turetmezdi.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
