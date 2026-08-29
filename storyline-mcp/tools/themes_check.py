"""Her tema okunuyor mu, ve temalar birbirinden gerçekten farklı mı?

themes.json'a bir tema eklemek ucuzdur; okunmayan bir tema eklemek de aynı
kadar ucuzdur ve hiçbir yapısal kontrol bağırmaz -- dosya geçerli, slayt
açılıyor, yalnızca yazı zeminine karışıyor. Bu yüzden tema listesi elle değil
burada doğrulanır.

İki soru, ayrı ayrı:

  okunabilirlik  her tema ile gercek bir slayt bestelenir ve butun yazilar
                 WCAG AA esiginden gecer mi diye olculur. Tema tanimindaki
                 renk ciftlerini tek tek kontrol etmek yetmez: bir yazinin
                 arkasinda ne oldugu yerlesime baglidir (buton uzerinde
                 on_accent, panel uzerinde surface, zemin uzerinde bg).

  ayriksilik     iki tema ayni zemine dusuyor mu. Zemin slayt alaninin
                 %98'i (olculdu); iki tema vurgu disinda ayni ise, kurslar
                 gozle ayni gorunur ve palet mesafesi bunu sayiya cevirir.

    python tools/themes_check.py
    python tools/themes_check.py --png temalar.png
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from storyline_mcp import compose, model
from storyline_mcp.package import StoryPackage
import contrast

BLANK = ROOT.parent / "test" / "bos.story"
WORK = ROOT.parent / "test" / "_canary" / "temalar.story"
# Tema basina ayri dosya: alti tema x alti varyant 36 slayt eder ve bos.story
# 14 tasiyor. Boluce her tema kendi paketinde olculur, palet karsilastirmasi
# da dosya duzeyinde temiz olur.
PER_THEME = ROOT.parent / "test" / "_canary" / "tema_{}.story"

# Iki tema bunun altinda birbirinden ayrilmiyor sayilir. contrast.py'deki
# cozunurluk sinamasindan: bir ton kayma 0.015, yakin lacivert 0.279.
# Esik ikisinin arasinda, "gozle ayni ton" ile "baska bir ton" arasinda.
APART = 0.20
#
# TEK YONLU, VE BILEREK. Bu guard yalnizca "cok yakinlasti"yi yakalar;
# ayriksilik artarsa kaydedilmez. deadband ve donor havuzunda ayni yapi bir
# KUSURDU (kaydedilmeyen kazanim korunmuyordu), burada degil: iki temanin
# 0.40 yerine 0.25 ayrik olmasi tasarim acisindan kabul edilebilir, yani
# korunacak bir kazanim yok. Esik bir TABAN, bir taban cizgisi degil.
# Karar bilerek verildi; gozden kacmadi.

# Her tema HER VARYANTLA olculur.
#
# Ilk yazilisinda yalnizca iki varyant vardi (sol-panel, ust-serit) ve kontrol
# "kagit TAMAM" dedi. Ayni tema, alti varyantli gercek bir kursta bes
# okunabilirlik uyarisi verdi: vurgu rengi degradenin KOYU ucunun uzerine
# dustugunde 4.26'ya iniyordu, ve o esleme iki varyantli probda hic olusmadi.
#
# Kismi kapsamin tehlikesi, kapsamadigini soylememesi. Renk ciftleri
# yerlesime bagli oldugu icin "tema guvenli" ancak butun yerlesimlerde
# olculdugunde soylenebilir.
SPEC = dict(layout="content",
            title="Parola Hijyeni", eyebrow="Bolum 1",
            body="Guclu bir parola uzundur ve baska hicbir hesapta kullanilmaz.",
            bullets=["Uzun tut", "Tekrar etme", "Sakla", "Dogrula"],
            buttons=["Devam"])
SPECS = [dict(SPEC, variant=v) for v in compose.variants_for("content")]


def build() -> dict[str, tuple[StoryPackage, list[str]]]:
    out: dict[str, tuple[StoryPackage, list[str]]] = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for theme in compose.theme_names():
            path = Path(str(PER_THEME).format(theme))
            shutil.copy2(BLANK, path)
            pkg = StoryPackage(path)
            names = [r.basename for r in model.slide_index(pkg).values()]
            if len(names) < len(SPECS):
                raise SystemExit(f"{BLANK.name} icinde {len(SPECS)} slayt yok "
                                 f"({len(names)} var).")
            palette = compose.theme_palette(theme)
            used = []
            for slide, spec in zip(names, SPECS):
                compose.compose_slide(pkg, slide, palette=palette,
                                      identity="tema", **dict(spec))
                used.append(slide)
            pkg.save(path, backup=False)
            out[theme] = (StoryPackage(path), used)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--png")
    args = parser.parse_args()

    built = build()
    failures = 0

    print(f"=== OKUNABILIRLIK (WCAG AA, {len(SPECS)} varyant x "
          f"{len(built)} tema) ===")
    per = {theme: contrast.audit(pkg) for theme, (pkg, _s) in built.items()}
    for theme in compose.theme_names():
        hits = per.get(theme, [])
        failures += len(hits)
        print(f"  {theme:<9} {'TAMAM' if not hits else f'{len(hits)} UYARI'}")
        for f in hits[:4]:
            print(f"      {f['ratio']:.2f} (>= {f['need']}) {f['fore']} / "
                  f"{f['back']}  {f['size']:.0f}pt  \"{f['text']}\"")

    print("\n=== AYRIKSILIK (zemin gercekten farkli mi) ===")
    tables = {theme: contrast.palette(pkg, slides)
              for theme, (pkg, slides) in built.items()}
    names = compose.theme_names()
    twins = 0
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            distance = contrast.palette_distance(tables[a], tables[b])
            if distance < APART:
                twins += 1
                print(f"  {a:<9} {b:<9} {distance:.3f}  <- AYNI TON")
    if not twins:
        closest = min(
            (contrast.palette_distance(tables[a], tables[b]), a, b)
            for i, a in enumerate(names) for b in names[i + 1:])
        print(f"  hicbir cift esigin altinda. En yakin: "
              f"{closest[1]} / {closest[2]}  {closest[0]:.3f}  (esik {APART})")
    failures += twins

    if args.png:
        for theme, (pkg, slides) in built.items():
            target = Path(args.png).with_name(
                Path(args.png).stem + f"_{theme}" + Path(args.png).suffix)
            subprocess.run([sys.executable, str(ROOT / "tools" / "look.py"),
                            str(pkg.path), "--slides", *slides, "--cols", "3",
                            "--card", "360", "-o", str(target)], check=True)

    print(f"\n{'GECTI' if not failures else 'KALDI'}: "
          f"{len(compose.theme_names())} tema, {failures} sorun")
    print("KAPSAM: okunabilirlik ve ayriksilik olculur. Temanin GUZEL olup\n"
          "        olmadigi olculmez ve olculmeyecek -- ona gozle bakilir.")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
