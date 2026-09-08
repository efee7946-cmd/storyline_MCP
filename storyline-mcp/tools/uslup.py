"""Aynı içerik, farklı üslup: resim gerçekten değişiyor mu?

"Panelden cikan her kurs tek makineden gecmis gibi" cumlesinin olculebilir
hali. Sikayet zevk gibi duruyor ama bir mekanizmasi var ve o mekanizma
STYLES'in kendi yorumunda yazili: "Each layout has one skeleton, which is
what keeps a deck coherent -- and also what makes every deck resemble every
other one."

SORU. Iki kurs FARKLI uslupla uretildiginde, ayni iskelet ayni icerikle
cizildiginde, ortaya cikan resim ne kadar ayrisiyor?

YONTEM. Her (duzen, varyant) hucresi icin ayni icerik dort uslupla ayri ayri
cizilir ve siluetleri karsilastirilir. Icerik SABIT tutulur, cunku degisken
icerik uslup farkini taklit eder: farkli metin farkli blok yuksekligi, farkli
blok yuksekligi farkli siluet verir ve "usluplar ayrisiyor" diye okunur.
variety.py ayni tuzagi bir kez olcmus ve ayni cozume varmis -- iskeleti
gormek icin iskelet disindaki her sey sabitlenmeli.

Esik silhouette'in kendi kalibre esigi (SAME_IDEA). Yeni bir sayi
uydurulmadi: "iki slayt ayni fikir mi" sorusu bu depoda zaten bir kez
olculmus, uc icerik kumesinde 0.081-0.195 araligina oturtulmus.

NEYE KOR. silhouette KONUMSALDIR. Uslup yalnizca rengi, puntoyu ya da
harf araligini degistiriyorsa bu sayi KIMILDAMAZ -- ve bugun STYLES'in
yaptigi seyin buyuk kismi tam olarak odur. Dolayisiyla dusuk bir ayrim
orani "usluplar hicbir sey yapmiyor" demek DEGIL; "usluplar GEOMETRIYE
dokunmuyor" demek. Ikisi ayni sey degil, ve hangisinin istendigi bir karar.

KANARYA IKI YONLU. Sifir, olcunun kor olmasi durumunda da basilir. O yuzden
once olcunun kendisi sinanir:
  duyarlilik -- ayni uslupta iki FARKLI varyant esigi asmali (asmazsa
                karsilastirma korlesmis, asagidaki sifir hicbir sey soylemez)
  kararlilik -- ayni hucre ayni uslupla iki kez kurulunca mesafe 0 olmali
                (olmazsa sayi gurultu, fark degil)

Iki ayagin da KIRMIZIYA DONEBILDIGI ayri ayri olculdu (2026-09-08), cunku
dusmeyen bir kanarya kanarya degil suslemedir:
  distance() hep 0 dondurulunce   -> duyarlilik dustu, cikis kodu 1
  grid()'e gurultu eklenince      -> kararlilik dustu (0.0268), cikis kodu 1
Ikisinde de kosu ORANI BASMADAN terk edildi; kor bir olcunun 0.000'i,
saglam bir olcunun 0.000'iyle ayni goruntuye sahip olurdu.

    python tools/uslup.py
    python tools/uslup.py --esik 0.30    ayrim orani bunun altindaysa KAPI dusur
    python tools/uslup.py --taban-yaz    olculen orani tabana dondur
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from storyline_mcp import compose, model
from storyline_mcp.package import StoryPackage
import scope
import silhouette

BLANK = ROOT.parent / "test" / "bos.story"
WORKDIR = ROOT.parent / "test" / "_canary"
TABAN = Path(__file__).resolve().parent / "uslup_taban.json"

# Icerik SABIT. Her hucre, her uslup, ayni sozcukler.
PROBE = dict(title="Parola Hijyeni", eyebrow="Bolum 1",
             body="Guclu bir parola uzundur, tahmin edilemez ve baska hicbir "
                  "hesapta kullanilmaz.",
             bullets=["Uzun tut", "Tekrar etme", "Sakla", "Dogrula"],
             buttons=["Devam"], index="1")


def hucreler() -> list[tuple[str, str | None]]:
    """Sozlukteki her (duzen, varyant) cifti. Varyantsiz duzenler de girer."""
    out: list[tuple[str, str | None]] = []
    for layout in compose.LAYOUTS:
        variants = compose.variants_for(layout)
        if variants:
            out.extend((layout, v) for v in variants)
        else:
            out.append((layout, None))
    return out


def kur(etiket: str, plan: list[tuple[str, str | None]],
        style: str) -> tuple[StoryPackage, list[str]]:
    """Bir uslupla, verilen hucreleri sirayla cizer. Tek fark: style."""
    yol = WORKDIR / f"uslup_{etiket}.story"
    shutil.copy2(BLANK, yol)
    pkg = StoryPackage(yol)
    names = [r.basename for r in model.slide_index(pkg).values()]
    if len(names) < len(plan):
        raise SystemExit(f"{BLANK.name} icinde {len(plan)} slayt yok "
                         f"({len(names)} var).")
    used = names[:len(plan)]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for slide, (layout, variant) in zip(used, plan):
            compose.compose_slide(pkg, slide, layout, variant=variant,
                                  style=style, identity="uslup", **dict(PROBE))
        pkg.save(yol, backup=False)
    return StoryPackage(yol), used


def olc(plan: list[tuple[str, str | None]], styles: list[str]) -> list[dict]:
    """Her hucre icin butun uslup ciftlerinin mesafesi."""
    izgara: dict[str, dict[int, list[float]]] = {}
    for style in styles:
        pkg, used = kur(f"p{len(plan)}_{style}", plan, style)
        izgara[style] = {i: silhouette.grid(pkg, s) for i, s in enumerate(used)}
    out = []
    for i, (layout, variant) in enumerate(plan):
        for a_i, a in enumerate(styles):
            for b in styles[a_i + 1:]:
                ga, gb = izgara[a][i], izgara[b][i]
                dogrudan = silhouette.distance(ga, gb)
                aynali = silhouette.distance(ga, silhouette.flip(gb))
                yakin = min(dogrudan, aynali)
                out.append({"layout": layout, "variant": variant,
                            "a": a, "b": b, "dogrudan": dogrudan,
                            "aynali": aynali,
                            "ayni": yakin < silhouette.SAME_IDEA})
    return out


def kanarya() -> list[str]:
    """Ölçü gerçekten koşuyor ve gerçekten görebiliyor mu. IKI YONLU."""
    kusur = []

    # DUYARLILIK. Ayni uslup, iki farkli `content` varyanti. variety.py bu
    # sozlukte en az bes AYRI fikir oldugunu kapi olarak tutuyor; o dogruysa
    # bu ikisinin de esigi asmasi gerekir. Asmazsa karsilastirma yolu
    # korlesmis demektir ve asagidaki her sifir anlamsizdir.
    ikili = [("content", "sol-panel"), ("content", "sag-metin")]
    pkg, used = kur("kanarya_duyar", ikili, "rail")
    d = silhouette.distance(silhouette.grid(pkg, used[0]),
                            silhouette.grid(pkg, used[1]))
    print(f"kanarya duyarlilik: iki farkli varyant, ayni uslup -> {d:.4f} "
          f"(esik {silhouette.SAME_IDEA})")
    if d < silhouette.SAME_IDEA:
        kusur.append(f"olcu KOR: bilinen iki ayri varyant {d:.4f} mesafede, "
                     f"yani 'ayni fikir' sayiliyor")

    # KARARLILIK. Ayni hucre, ayni uslup, iki ayri dosya. Sifir olmali;
    # olmazsa asagidaki mesafeler gurultu tasiyor ve fark diye okunur.
    tek = [("content", "sol-panel")]
    p1, u1 = kur("kanarya_kar1", tek, "rail")
    p2, u2 = kur("kanarya_kar2", tek, "rail")
    s = silhouette.distance(silhouette.grid(p1, u1[0]),
                            silhouette.grid(p2, u2[0]))
    print(f"kanarya kararlilik: ayni hucre iki kez kuruldu -> {s:.4f} "
          f"(0 olmali)")
    if s > 1e-6:
        kusur.append(f"olcu KARARSIZ: ayni hucre iki kurulusta {s:.4f} "
                     f"mesafe veriyor -- uslup farki bu gurultuden ayrilamaz")
    return kusur


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--esik", type=float,
                        help="ayrim orani bunun altindaysa KAPI olarak dusur")
    parser.add_argument("--taban-yaz", action="store_true",
                        help="olculen orani tabana dondur")
    args = parser.parse_args()

    kusur = kanarya()
    if kusur:
        print("\nKANARYA KALDI. Asagidaki sayilar okunmamali:")
        for k in kusur:
            print(f"  - {k}")
        return 1
    print()

    styles = sorted(compose.STYLES)
    plan = hucreler()
    # bos.story on slayt tasiyor; hucreler partiler halinde kurulur.
    ADIM = 10
    sonuc: list[dict] = []
    for bas in range(0, len(plan), ADIM):
        sonuc.extend(olc(plan[bas:bas + ADIM], styles))

    ayrisan = [r for r in sonuc if not r["ayni"]]
    oran = len(ayrisan) / len(sonuc) if sonuc else 0.0

    print(f"{len(plan)} hucre (duzen x varyant), {len(styles)} uslup, "
          f"{len(sonuc)} karsilastirma\n")

    # Hucre bazinda: bu hucrede HIC ayrisan uslup cifti var mi.
    print(f"{'duzen':<10}{'varyant':<14}{'ayrisan cift':>13}{'en buyuk':>10}")
    print("-" * 47)
    for layout, variant in plan:
        satir = [r for r in sonuc
                 if r["layout"] == layout and r["variant"] == variant]
        ayri = sum(1 for r in satir if not r["ayni"])
        en = max((min(r["dogrudan"], r["aynali"]) for r in satir), default=0.0)
        print(f"{layout:<10}{str(variant or '-'):<14}"
              f"{ayri:>6}/{len(satir):<6}{en:>10.4f}")

    print(f"\n{'uslup cifti':<20}{'ayrisan hucre':>14}{'ortalama':>10}")
    print("-" * 44)
    for a_i, a in enumerate(styles):
        for b in styles[a_i + 1:]:
            cift = [r for r in sonuc if r["a"] == a and r["b"] == b]
            ayri = sum(1 for r in cift if not r["ayni"])
            ort = sum(min(r["dogrudan"], r["aynali"]) for r in cift) / len(cift)
            print(f"{a + ' / ' + b:<20}{ayri:>7}/{len(cift):<6}{ort:>10.4f}")

    print(f"\nUSLUP AYRIM ORANI: {oran:.3f}  "
          f"({len(ayrisan)}/{len(sonuc)} karsilastirmada resim gercekten farkli)")

    taban = json.loads(TABAN.read_text(encoding="utf-8")) if TABAN.exists() else None
    if args.taban_yaz:
        TABAN.write_text(json.dumps(
            {"oran": round(oran, 4), "hucre": len(plan), "uslup": styles,
             "esik": silhouette.SAME_IDEA,
             "not": "silhouette KONUMSAL; renk/punto/harf araligi bu sayida yok"},
            ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"taban yazildi: {TABAN.name}")
    elif taban:
        fark = oran - taban["oran"]
        print(f"taban {taban['oran']:.3f} ({taban['hucre']} hucre) -> "
              f"{'+' if fark >= 0 else ''}{fark:.3f}")

    # Kapsam sonucun YANINDA durur, ve metni tek yerde (scope.py): ayri
    # belgede duran kapsam okunmaz, iki kopya duran kapsam birbirinden kayar.
    print()
    scope.show("uslup")

    if args.esik is not None and oran < args.esik:
        print(f"\nKALDI: ayrim orani {oran:.3f} < {args.esik}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
