"""Rubriğin kanaryası: bilerek kötü ve bilerek iyi iki kurs.

GÖREV 7 bir rubrik kuracak ve rubrik YARGI uretecek -- muhtemelen bir model
tarafindan. Bu, projede ilk kez dogrulayicinin kendisinin deterministik
olmamasi demek. Su ana kadarki her olcu ya ikili ya fiziksel: tasti/tasmadi,
kac birim, hangi oran. Rubrik oyle degil.

O yuzden kanarya sorusu yeni bir bicimde geri geliyor ve rubrik yazilmadan
ONCE cevaplanmasi gerekiyor:

    rubrik bilerek kotu bir kursa KOTU puan veriyor mu?
    rubrik bilerek iyi bir kursa  IYI  puan veriyor mu?

Ikisi de sinanmadan rubrigin ciktisi okunamaz. Tek yonlu bir sinama yeterli
degil: her seye dusuk puan veren bir rubrik birinci testi gecer, her seye
yuksek puan veren ikinciyi.

BU DOSYA RUBRIGI DEGIL, FIKSTURLERI KURAR -- ve fikstuurlerin gercekten
farkli oldugunu KANITLAR. Kanitlamadan biraksaydik, atil bir olumsuz kontrol
elde ederdik: bu oturumda kanaryanin kendisi bir kez yalanci cikti (BOM'u
silinmis dosyalar aciliyordu), ve ders su ki olumsuz kontrol de olculmeli.

Fark, rubrikten BAGIMSIZ araclarla olculur -- deadband, silhouette, contrast.
Rubrigin kendi olcusuyle olculseydi, "fikstuurler farkli" ile "rubrik
calisiyor" ayni cumle olurdu.

RUBRIK YAZILDIGINDA YAPILACAK UC OLCUM -- simdi yazili, cunku ilki en kolay
olculdugu icin digerleri unutulur:

  1. KABA AYRIM     kotu << iyi. Bu dosyanin garanti ettigi sey. Gectiginde
                    rubrigin CALISABILECEK durumda oldugu bilinir, calistigi
                    degil.

  2. INCE AYRIM     orta < iyi. Asil is bu. Uretimde cikacak kurslarin hepsi
                    orta ile iyi arasinda olacak; ikisi de yuksek puan
                    aliyorsa rubrik uretimde ise yaramaz, cunku GOREV 4 ve
                    5'in getirdigi farki -- yani olcmek istedigimiz seyi --
                    goremiyor demektir. Kaba ayrimin gecmesi bunu GARANTI
                    ETMEZ.

  3. KARARSIZLIK    surekli cikti ureten bir yargicin IKI ayri kararsizligi
                    var ve ikincisi unutulur:

                    a. sicaklik  -- ayni girdi, tekrar kosum, puan dagilimi
                    b. SIRA      -- ayni kurs, farkli slayt sirasi; ve ayni
                                    kurs, farkli olcut sirasi. Puan degisiyor
                                    mu?

                    (a) kolay olculur, o yuzden (b) atlanir. Sira etkisi
                    tasiyan bir rubrik, iki kursu karsilastirdiginda farki
                    icerikten degil sunum sirasindan uretir.

    python tools/rubric_fixtures.py
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
import deadband
import silhouette
import variety

BLANK = ROOT.parent / "test" / "bos.story"
OUT = ROOT.parent / "test" / "_rubrik"
BAD, GOOD = OUT / "kotu.story", OUT / "iyi.story"

# UC FIKSTUR, IKI SORU.
#
# Ilk denemede "kotu" fikstur motorun GOREV 3 halini taklit ediyordu ve
# olculdugunde alti olcunun ucunde "iyi"den ayrisamadi -- gozle bakildiginda
# da kotu degil, tutarli bir sablon gibi duruyordu. Ders: kanarya once KABA
# ayrimi sinamali. Rubrik acikca bozuk bir kursu ayirt edemiyorsa, ince
# ayrimi hic edemez ve ince sonucu okumanin anlami yoktur.
#
#   kotu  acikca bozuk: okunmayan renk, tek siluet, olcek kapali
#   orta  motorun GOREV 4/5 oncesi hali -- INCE soru, once kaba gecmeli
#   iyi   bugunku motor, varsayilandan uzak bir tema ile
#
# "kotu"nun paleti artik ACIKCA yazili, bir fonksiyonun hatasina dayanmiyor.
#
# Once derive_palette'e koyu bir marka rengi verilerek uretiliyordu, cunku o
# yol olculdugunde 1.16 kontrast veriyordu. Ama o kusur DUZELTILDI (yazi
# renkleri artik karsilasabilecegi her zemine gore turetiliyor) ve fikstur
# aninda atil hale geldi: kotu ile iyi arasinda kontrast farki kalmadi.
#
# Ders: bir olumsuz kontrol, bir hatanin varligina dayanmamali. Hata
# duzeltilince kontrol de kaybolur ve bunu ancak fikstur denetimi soyler.
# Kotu palet artik burada, elle, ve neden kotu oldugu yazili: yazi zemine
# neredeyse esit, vurgu zeminden ayrismiyor.
# Bos.story on dort slayt tasiyor, DECK on tane. Ilk denemede geri kalan dordu
# BOS kaldi ve model ciktisi ilk bakista onlari isaretledi ("four blank white
# slides at end"). Bos slayt her puani asagi ceker ve olculmek istenen farki
# gizler; DECK dondurulerek butun slaytlar doldurulur.
BAD_VARIANT = "sol-panel"
BAD_PALETTE = {
    "bg": "#0E1B3D", "deep": "#0B1631", "surface": "#16265A",
    "accent": "#1B2C5E", "accent_text": "#1B2C5E",
    "text": "#2A3A66", "muted": "#22315C", "on_accent": "#16265A",
}
GOOD_THEME = "kagit"      # varsayilan palet lacivert; "gece" onunla ayni cikardi
MID = OUT / "orta.story"


def build_bad(path: Path = BAD, *, palette=None) -> StoryPackage:
    shutil.copy2(BLANK, path)
    pkg = StoryPackage(path)
    names = [r.basename for r in model.slide_index(pkg).values()]
    ceiling = compose.MAX_TYPE_SCALE
    try:
        compose.MAX_TYPE_SCALE = 1.0          # yogunluk olcegi devre disi
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for i, slide in enumerate(names):
                body = dict(variety.DECK[i % len(variety.DECK)])
                body.pop("layout", None)
                compose.compose_slide(pkg, slide, "content",
                                      variant=BAD_VARIANT, identity="kotu",
                                      palette=palette, **body)
            pkg.save(path, backup=False)
    finally:
        compose.MAX_TYPE_SCALE = ceiling
    return StoryPackage(path)


def build_good() -> StoryPackage:
    shutil.copy2(BLANK, GOOD)
    pkg = StoryPackage(GOOD)
    names = [r.basename for r in model.slide_index(pkg).values()]
    history: list[str] = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for i, slide in enumerate(names):
            body = dict(variety.DECK[i % len(variety.DECK)])
            body.pop("layout", None)
            out = compose.compose_slide(pkg, slide, "content",
                                        theme=GOOD_THEME, identity="iyi",
                                        avoid_variant=history, **body)
            history.append(out["variant"])
        pkg.save(GOOD, backup=False)
    return StoryPackage(GOOD)


def describe(pkg: StoryPackage, label: str) -> dict:
    """Fikstürü rubrikten bağımsız araçlarla ölçer."""
    slides = [r.basename for r in model.slide_index(pkg).items().__iter__()] \
        if False else [r.basename for r in model.slide_index(pkg).values()]
    filled = [n for n in slides if any(silhouette.grid(pkg, n))]

    empties = []
    for part, _ref in model.slide_index(pkg).items():
        _band, total, count = deadband.dead_band(pkg, part)
        if count:
            empties.append(total)

    pairs = silhouette.compare(pkg, filled)
    twins = [p for p in pairs if p["same_idea"]]
    groups = silhouette.ideas(filled, pairs)

    return {
        "label": label,
        "slides": len(filled),
        "empty_worst": max(empties) if empties else 0,
        "empty_mean": round(sum(empties) / len(empties)) if empties else 0,
        "silhouettes": len(groups),
        "twin_pairs": len(twins),
        "contrast_warnings": len(contrast.audit(pkg)),
        "palette": contrast.palette(pkg),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--png", help="ikisini yan yana goruntule")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    bad = describe(build_bad(palette=BAD_PALETTE), "kotu")
    mid = describe(build_bad(MID), "orta")
    good = describe(build_good(), "iyi")

    print(f"{'olcu':<26}{'kotu':>8}{'orta':>8}{'iyi':>8}   kaba ayrim")
    print("-" * 70)
    # "ortalama bos alan" bilerek YOK. Olculdu ve bu fikstuurleri ayirmiyor,
    # cunku panelin varligi olcekten daha baskin: her slaytta panel kullanan
    # tek-varyantli kurs, panelsiz varyantlar iceren cesitli kurstan daha
    # DOLU cikiyor. Yani o sayi tipografiyi degil varyant secimini olcuyor.
    # Ayirt etmeyen bir olcuyu kanaryada tutmak, kanaryayi zayiflatir.
    # "en kotu bos alan" CIKARILDI (2026-08-16). Punto merdiveni sonrasi uc
    # fikstuur de %46 veriyor -- olcu ikisini ayirt etmiyor. Ayirt etmeyen bir
    # olcuyu kanaryada tutmak kanaryayi zayiflatir: gecmesi bir sey soylemez.
    # Ayni gerekce daha once "ortalama bos alan" icin de gecerliydi.
    rows = [
        ("farkli siluet", bad["silhouettes"], good["silhouettes"], "buyuk iyi"),
        ("ayni goruen cift", bad["twin_pairs"], good["twin_pairs"], "kucuk iyi"),
        ("kontrast uyarisi", bad["contrast_warnings"], good["contrast_warnings"],
         "kucuk iyi"),
    ]
    inert = []
    for name, b, g, direction in rows:
        better = g < b if direction == "kucuk iyi" else g > b
        mark = "evet" if better else ("HAYIR" if b != g else "AYNI")
        if not better:
            inert.append(name)
        m = {"farkli siluet": mid["silhouettes"],
             "ayni goruen cift": mid["twin_pairs"],
             "kontrast uyarisi": mid["contrast_warnings"]}[name]
        print(f"  {name:<24}{b:>8}{m:>8}{g:>8}   {mark}")

    distance = contrast.palette_distance(bad["palette"], good["palette"])
    print(f"  {'palet mesafesi':<24}{'':>8}{distance:>8.3f}   "
          f"{'evet' if distance >= 0.15 else 'HAYIR'}")
    if distance < 0.15:
        inert.append("palet mesafesi")

    if args.png:
        for pkg_path, name in ((BAD, "kotu"), (GOOD, "iyi")):
            target = Path(args.png).with_name(
                Path(args.png).stem + f"_{name}" + Path(args.png).suffix)
            subprocess.run([sys.executable, str(ROOT / "tools" / "look.py"),
                            str(pkg_path), "--cols", "5", "--card", "300",
                            "-o", str(target)], check=True)
            print(f"  goruntu: {target}")

    print()
    if inert:
        print(f"ATIL FIKSTUR: {len(inert)} olcu ikisini ayirt etmiyor "
              f"({', '.join(inert)}).\nRubrik bunlarla sinanamaz -- ayirt "
              "etmeyen bir olumsuz kontrol, olumsuz kontrol degildir.")
        return 1
    print("Fikstuurler her olcude ayrisiyor. Rubrik kanaryasi kurulabilir.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
