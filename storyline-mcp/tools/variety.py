"""GÖREV 4 kabul ölçütü: on slayt, ardışık tekrar yok, en az beş farklı varyant.

Üç şeyi ayrı ayrı sorar, çünkü üçü ayrı ayrı bozulur:

  yasak    -- iki komsu slayt ayni varyanti tasiyor mu (sifir olmali)
  aralik   -- ayni varyant tekrar geldiginde arada kac slayt var. Sayi tek
              basina yaniltici: bes slayt arayla tekrar ritim, iki slayt
              arayla tekrar "yine ayni sayfa". Ikisi ayni sayiyi uretir.
  fikir    -- sozlukte kac ad yazdigi degil, gozun kac farkli sey gordugu.
              silhouette.py olcer; ayna ve kaydirma ciftleri tek fikre iner.

Ucuncusu olmadan olcut kandirilabilir: sozluge alti ad yazip hepsini metin
sutununun x'ini oynatmaya ayirmak "6 varyant, 0 tekrar" verir ve deck yine
tekduze gorunur. Bu oturumda tam olarak oyle oldu -- dort ad yazildi, goz iki
fikir gordu.

    python tools/variety.py
    python tools/variety.py --png bak.png
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
import scope
import silhouette

BLANK = ROOT.parent / "test" / "bos.story"
WORK = ROOT.parent / "test" / "_canary" / "variety.story"

# Gercek bir kursun sekli: ayni layout birden fazla kez gelir, ki yasagin
# korumasi gereken durum tam olarak budur. Hepsi farkli layout olsaydi olcut
# hicbir sey olcmezdi.
DECK = [
    dict(layout="content", title="Parola Hijyeni", eyebrow="Bolum 1",
         body="Guclu bir parola uzundur ve baska hicbir hesapta kullanilmaz.",
         bullets=["Uzun tut", "Tekrar etme", "Sakla", "Dogrula"], buttons=["Devam"]),
    dict(layout="content", title="Kimlik Dogrulama", eyebrow="Bolum 1",
         body="Iki adimli dogrulama, parola calinsa bile hesabi korur.",
         buttons=["Devam"]),
    dict(layout="content", title="Oltalama E-postalari", eyebrow="Bolum 2",
         body="Gonderen adresi, aciliyet dili ve beklenmedik ek: uc isaret.",
         bullets=["Adresi oku", "Acele etme", "Eki acma"], buttons=["Devam"]),
    dict(layout="content", title="Cihaz Guvenligi", eyebrow="Bolum 2",
         body="Kilitlenmemis bir ekran, acik birakilmis bir kapidir.",
         buttons=["Devam"]),
    dict(layout="content", title="Veri Siniflandirma", eyebrow="Bolum 3",
         body="Her belge dort gizlilik duzeyinden birine girer.",
         bullets=["Acik", "Ic", "Gizli", "Cok gizli"], buttons=["Devam"]),
    dict(layout="content", title="Paylasim Kurallari", eyebrow="Bolum 3",
         body="Disari cikan her dosya once siniflandirmasina bakilarak gonderilir.",
         buttons=["Devam"]),
    dict(layout="content", title="Olay Bildirimi", eyebrow="Bolum 4",
         body="Ilk yirmi dort saat belirleyicidir.",
         bullets=["Tespit et", "Kaydet", "Bildir", "Kapat"], buttons=["Devam"]),
    dict(layout="content", title="Sorumluluklar", eyebrow="Bolum 4",
         body="Guvenlik bir ekibin degil, herkesin isidir.", buttons=["Devam"]),
    dict(layout="content", title="Yedekleme", eyebrow="Bolum 5",
         body="Test edilmemis bir yedek, yedek degildir.",
         bullets=["Duzenli al", "Ayri tut", "Geri yuklemeyi dene"], buttons=["Devam"]),
    dict(layout="content", title="Ozet", eyebrow="Kapanis",
         body="Bes bolum, tek alizkanlik: durup bir saniye dusunmek.",
         buttons=["Bitir"]),
]


# Sozlugun kac farkli iskelet tasidigini sormak icin icerik SABIT tutulur.
# Deckin kendi degisen icerigiyle olculdugunde iki varyantin ayni fikir olup
# olmadigi anlasilmaz: farkli metin, farkli blok yuksekligi, farkli siluet
# uretir ve ayna cifti maskelenir -- olculdu, kontrollu icerikte 0.081 veren
# cift degisken icerikte esigin cok uzerine cikti ve "6 farkli fikir" gibi
# okundu. Iskeleti gormek icin iskelet disindaki her sey sabitlenmeli.
PROBE = dict(title="Parola Hijyeni", eyebrow="Bolum 1",
             body="Guclu bir parola uzundur, tahmin edilemez ve baska hicbir "
                  "hesapta kullanilmaz.",
             bullets=["Uzun tut", "Tekrar etme", "Sakla", "Dogrula"],
             buttons=["Devam"])
PROBE_FILE = ROOT.parent / "test" / "_canary" / "variety_probe.story"


def build_probe(layout: str = "content") -> tuple[StoryPackage, dict[str, str]]:
    """Her varyanttan bir slayt, hepsinde birebir aynı içerik."""
    shutil.copy2(BLANK, PROBE_FILE)
    pkg = StoryPackage(PROBE_FILE)
    names = [r.basename for r in model.slide_index(pkg).values()]
    per_variant: dict[str, str] = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for slide, variant in zip(names, compose.variants_for(layout)):
            compose.compose_slide(pkg, slide, layout, variant=variant,
                                  identity="prob", **dict(PROBE))
            per_variant[variant] = slide
        pkg.save(PROBE_FILE, backup=False)
    return StoryPackage(PROBE_FILE), per_variant


def build() -> tuple[StoryPackage, list[str], list[dict]]:
    shutil.copy2(BLANK, WORK)
    pkg = StoryPackage(WORK)
    names = [r.basename for r in model.slide_index(pkg).values()]
    if len(names) < len(DECK):
        raise SystemExit(f"{BLANK.name} icinde {len(DECK)} slayt yok "
                         f"({len(names)} var).")
    history: list[str] = []
    log, used = [], []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for i, (slide, spec) in enumerate(zip(names, DECK)):
            out = compose.compose_slide(pkg, slide, spec.pop("layout"),
                                        identity="cesitlilik",
                                        avoid_variant=history, **spec)
            history.append(out["variant"])
            log.append({"slide": i, "layout": out["layout"],
                        "variant": out["variant"],
                        "repeated": out["variant_repeated"]})
            used.append(slide)
        pkg.save(WORK, backup=False)
    return StoryPackage(WORK), used, log


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--png", help="ayni kurstan bir goruntu de uret")
    args = parser.parse_args()

    pkg, slides, log = build()
    report = compose.variety_report(log)

    print(f"{report['slides']} slayt, {report['with_variant']} tanesi varyantli\n")
    for entry in log:
        mark = "  <- YASAK CIGNENDI" if entry["repeated"] else ""
        print(f"  {entry['slide']:>2}  {entry['layout']:<9} {entry['variant']}{mark}")

    print(f"\nardisik tekrar : {len(report['consecutive'])}"
          f"{'' if not report['consecutive'] else '  ' + str(report['consecutive'])}")
    print(f"zorunlu cigneme: {len(report['forced'])}"
          f"{'' if not report['forced'] else '  slayt ' + str(report['forced'])}")
    print(f"sozlukte ad    : {report['distinct']}")
    if report["gaps"]:
        print("tekrar araliklari:")
        for key, spread in sorted(report["gaps"].items()):
            print(f"  {key:<22} {spread}")
        print(f"  en yakin tekrar: {report['nearest']} slayt arayla")
    else:
        print("tekrar araliklari: hicbir varyant iki kez kullanilmadi")
    if report["no_variant"]:
        print(f"varyanti olmayan duzenler: {report['no_variant']}  "
              f"(bu duzenlerde yasak hic uygulanamaz)")

    # Sozlukteki ad sayisi degil, gozun gordugu fark.
    #
    # Iki ayri soru var ve tek olcumde birlestirilirse ikisi de kaybolur:
    #   sozluk  -- her varyanttan BIR temsilci; ayna ve kaydirma ciftleri
    #              burada tek fikre iner. "Kac farkli iskelet yazdim."
    #   deck    -- butun slaytlar; ayni varyanti iki kez kullanmak dogal olarak
    #              ayni silueti verir, onemli olan kac slayt arayla.
    probe, per_variant = build_probe()
    reps = list(per_variant.values())
    groups = silhouette.ideas(reps, silhouette.compare(probe, reps))
    by_slide = {v: k for k, v in per_variant.items()}
    print()
    for group in sorted(groups, key=len, reverse=True):
        if len(group) > 1:
            print(f"  tek fikir: {sorted(by_slide[s] for s in group)}")
    print(f"olculen farkli fikir: {len(groups)} "
          f"({len(reps)} varyant yazildi, "
          f"{len(reps) - len(groups)} tanesi baskasinin ayni fikri)")

    twins = [p for p in silhouette.compare(pkg, slides) if p["same_idea"]]
    if twins:
        closest = min(abs(slides.index(p["a"]) - slides.index(p["b"])) for p in twins)
        print(f"deckte ayni goruen slayt cifti: {len(twins)}, "
              f"en yakini {closest} slayt arayla")

    if args.png:
        subprocess.run([sys.executable, str(ROOT / "tools" / "look.py"), str(WORK),
                        "--slides", *slides, "--cols", "3", "--card", "430",
                        "-o", args.png], check=True)

    ok = (not report["consecutive"]) and len(groups) >= 5
    print(f"\n{'GECTI' if ok else 'KALDI'}: ardisik tekrar "
          f"{len(report['consecutive'])} (0 olmali), farkli fikir "
          f"{len(groups)} (>=5 olmali)")
    # Kapsam, sonucun yaninda durur. Ayri bir belgede duran kapsam okunmaz
    # ve "variety GECTI" cumlesi zamanla "kurs cesitli" diye anlasilir.
    scope.show("variety")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
