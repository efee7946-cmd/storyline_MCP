"""Bir kursa bakıp puan veren rubrik -- ve rubriğin kendisinin ölçülmesi.

Bu, projedeki ilk DETERMINISTIK OLMAYAN dogrulayici. Su ana kadarki her olcu
ya ikili ya fizikseldi: tasti/tasmadi, kac birim, hangi oran. Rubrik yargi
uretiyor ve ayni girdiye iki kez ayni cevabi vermeyebilir.

Bu yuzden rubrigin CIKTISI degil, rubrigin KENDISI once olculur. Uc soru,
ucu de tools/rubric_fixtures.py'de gerekcesiyle yazili:

    kaba ayrim     kotu << iyi        rubrik calisabilir durumda mi
    ince ayrim     orta <  iyi        asil is; uretimdeki kurslar burada
    kararsizlik    (a) sicaklik       ayni girdi, tekrar kosum
                   (b) SIRA           ayni kurs, farkli slayt/olcut sirasi

Ucuncunun ikinci yarisi kolayca unutulur cunku ilki daha kolay olculur. Sira
etkisi tasiyan bir yargic, iki kursu karsilastirdiginda farki icerikten degil
sunum sirasindan uretir -- ve o, orta/iyi karsilastirmasini gecersiz kilar.

BAKILAN SEY ONIZLEME, YAYIN DEGIL. preview.py'nin sadakat notu neyi yaklasik
cizdigini sayiyor. Bir maddesi bu araci dogrudan etkiledi ve DUZELTILDI:
onizleme metni kirpmiyordu, dolayisiyla tasan yazi komsusunun uzerine biniyor
ve rubrik dosyada hic olmayan bir "buton-metin cakismasi" bildiriyordu -- var
olmayan bir kusuru puanliyordu. Artik kirpiyor.

Geri kalan sapmalar duruyor: dikey hizalama uygulanmaz, alti sekil geometrisi
duz dikdortgen cizilir, katmanlar cizilmez. Rubrik "yerlesim ve renk" hakkinda
konusabilir, "Storyline'da tam olarak nasil gorunuyor" hakkinda konusamaz.

    python tools/rubric.py --fixtures            uc fikstur, birer kosu
    python tools/rubric.py --fixtures --repeat 3 sicaklik kararsizligi
    python tools/rubric.py --fixtures --order    sira etkisi
    python tools/rubric.py kurs.story
"""

from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "panel"))
sys.path.insert(0, str(ROOT / "tools"))

from storyline_mcp import model
from storyline_mcp.package import StoryPackage
import agent
import look
import scope
import rubric_fixtures

# Olcutler. Her biri 1-5 ve her biri AYRI bir sey olcuyor -- ustuste binen iki
# olcut, tek bir yargiyi iki kez sayar ve toplami sismis gosterir.
CRITERIA = {
    "cesitlilik": "Slaytlar birbirinden farkli GORUNUYOR mu, yoksa ayni "
                  "sayfanin tekrari gibi mi duruyor? Icerik degil, YERLESIM.",
    "doluluk": "Slaytlarda amacsiz bos alan var mi? Nefes payi iyidir, "
               "yarim bos sayfa degildir.",
    "okunabilirlik": "Yazi zemininden ayrisiyor mu, punto okunacak kadar "
                     "buyuk mu, satirlar tasip kesilmis mi?",
    "hiyerarsi": "Basligin, govdenin ve maddelerin farki ilk bakista belli "
                 "mi, yoksa hepsi ayni sesle mi konusuyor?",
    "tutarlilik": "Kurs tek bir tasarim diline mi sahip, yoksa slaytlar "
                  "farkli yerlerden mi toplanmis gibi?",
}
SCALE = ("1 = kabul edilemez, 2 = zayif, 3 = idare eder, "
         "4 = iyi, 5 = profesyonel")


def prompt_for(image: Path, order: list[str]) -> str:
    lines = "\n".join(f"  {name}: {CRITERIA[name]}" for name in order)
    keys = ", ".join(f'"{name}": <1-5>' for name in order)
    return (
        f"{image.name} dosyasindaki goruntu, bir e-ogrenme kursunun butun "
        f"slaytlarini yan yana gosteriyor. Tasarim kalitesini puanla.\n\n"
        f"Olcutler ({SCALE}):\n{lines}\n\n"
        f"Icerigin dogrulugunu DEGERLENDIRME; yalnizca gorsel tasarimi. "
        f"Yalnizca tek satir JSON dondur, baska hicbir sey yazma:\n"
        f'{{{keys}, "neden": "<en belirgin sorun, 8 kelimeyi gecmeden>"}}'
    )


def render(story: Path, out: Path, *, shuffle: int | None = None) -> Path:
    pkg = StoryPackage(story)
    names = [r.basename for r in model.slide_index(pkg).values()]
    names = [n for n in names if _has_ink(pkg, n)]
    if shuffle is not None:
        random.Random(shuffle).shuffle(names)
    html, width, height = look.page(pkg, names, cols=5, card=300)
    look.shoot(html, width, height, out)
    return out


def _has_ink(pkg: StoryPackage, name: str) -> bool:
    root = pkg.parse(pkg.slide_part_for(name))
    shape_list = root.find("shapeLst")
    return bool(shape_list is not None and len(shape_list))


def score(image: Path, order: list[str], *, timeout: float = 240.0) -> dict:
    """Bir görüntüyü puanlar. Ayrıştırılamayan cevap sessizce sıfır olmaz."""
    cli = agent.find_cli()
    if not cli:
        raise SystemExit("Claude Code CLI bulunamadi.")
    result = subprocess.run(
        [str(cli), "-p", prompt_for(image, order), "--allowedTools", "Read"],
        cwd=str(image.parent), capture_output=True, text=True,
        timeout=timeout, encoding="utf-8", errors="replace",
    )
    raw = (result.stdout or "").strip()
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        # Ayristirilamayan cevap bir puan DEGILDIR. Sifir saymak, modelin
        # "kotu" dedigi ile "cevap veremedim" dedigini ayni kovaya atardi.
        return {"ok": False, "raw": raw[:200]}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"ok": False, "raw": raw[:200]}
    values = {k: data.get(k) for k in CRITERIA}
    if any(not isinstance(v, (int, float)) for v in values.values()):
        return {"ok": False, "raw": raw[:200]}
    return {"ok": True, "scores": values, "total": sum(values.values()),
            "why": str(data.get("neden", ""))[:80]}


def run(story: Path, work: Path, *, repeat: int, order_test: bool) -> list[dict]:
    out = []
    image = render(story, work / f"{story.stem}.png")
    base = list(CRITERIA)
    for i in range(repeat):
        got = score(image, base)
        got["run"], got["kind"] = i, "temel"
        out.append(got)
    if order_test:
        # (b) SIRA. Iki ayri permutasyon: slayt sirasi ve olcut sirasi.
        shuffled = render(story, work / f"{story.stem}_karisik.png", shuffle=7)
        got = score(shuffled, base)
        # Iki permutasyon AYRI kosuluyor. Birlikte degistirilseydi puan
        # oynadiginda hangisinin etkiledigi ayrilamazdi.
        got["run"], got["kind"] = 0, "slayt-sirasi"
        out.append(got)
        flipped = list(reversed(base))
        got = score(image, flipped)
        got["run"], got["kind"] = 0, "olcut-sirasi"
        out.append(got)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("story", nargs="?")
    parser.add_argument("--fixtures", action="store_true")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--order", action="store_true",
                        help="sira etkisini de olc (iki ekstra kosu/kurs)")
    args = parser.parse_args()

    targets: list[Path]
    if args.fixtures:
        rubric_fixtures.OUT.mkdir(parents=True, exist_ok=True)
        rubric_fixtures.build_bad(palette=rubric_fixtures.BAD_PALETTE)
        rubric_fixtures.build_bad(rubric_fixtures.MID)
        rubric_fixtures.build_good()
        targets = [rubric_fixtures.BAD, rubric_fixtures.MID, rubric_fixtures.GOOD]
    elif args.story:
        targets = [Path(args.story).resolve()]
    else:
        parser.error("bir kurs dosyasi ya da --fixtures verin")

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        results = {t.stem: run(t, work, repeat=args.repeat,
                               order_test=args.order) for t in targets}

    failed = sum(1 for runs in results.values() for r in runs if not r["ok"])
    print(f"{'kurs':<10}{'kosu':<14}{'toplam':>7}   " +
          "  ".join(f"{k[:6]:>6}" for k in CRITERIA))
    print("-" * 72)
    for name, runs in results.items():
        for r in runs:
            if not r["ok"]:
                print(f"{name:<10}{r['kind']:<14}{'AYRISTIRILAMADI':>7}")
                continue
            print(f"{name:<10}{r['kind']:<14}{r['total']:>7}   " +
                  "  ".join(f"{r['scores'][k]:>6}" for k in CRITERIA) +
                  f"   {r['why']}")

    print()
    base = {n: [r["total"] for r in runs if r["ok"] and r["kind"] == "temel"]
            for n, runs in results.items()}
    spread: dict[str, tuple[int, int]] = {}
    for name, totals in base.items():
        if len(totals) > 1:
            lo, hi = min(totals), max(totals)
            spread[name] = (lo, hi)
            print(f"  {name:<10} sicaklik: {totals}  aralik {hi - lo}  sapma "
                  f"{statistics.pstdev(totals):.2f}")
            # ALT PUAN KARARLILIGI. Toplam kararli gorunurken alt puanlar
            # kosudan kosuya yer degistiriyorsa, rubrik olcutleri AYIRT
            # ETMIYOR demektir -- genel bir izlenim uretip olcutlere
            # dagitiyordur, ve o izlenim iki kursu karsilastirmaya yetmez.
            runs = [r for r in results[name] if r["ok"] and r["kind"] == "temel"]
            moved = [k for k in CRITERIA
                     if len({r["scores"][k] for r in runs}) > 1]
            print(f"  {'':<10} alt puan oynayan olcut: "
                  f"{', '.join(moved) if moved else 'yok'}"
                  f"  ({len(moved)}/{len(CRITERIA)})")
    # DAGILIMLAR ORTUSUYOR MU. Ortalamada +2 fark, dagilimlar ic ice geciyorsa
    # tek bir kosuda ters yone donebilir; o zaman "ince ayrim gecti" cumlesi
    # kosuya bagli olur, olcuye degil.
    if "orta" in spread and "iyi" in spread:
        (mlo, mhi), (glo, ghi) = spread["orta"], spread["iyi"]
        overlap = not (glo > mhi)
        print(f"  orta {mlo}-{mhi} / iyi {glo}-{ghi}  -> dagilimlar "
              f"{'ORTUSUYOR' if overlap else 'ayrik'}")
    if args.order:
        # Sira etkisi, SICAKLIK GURULTUSUNE karsi okunur. Permutasyon basina
        # tek kosum, sicakligin kendi araligindan kucuk bir farki ayirt
        # edemez: "+1" hem sira etkisi hem gunun gurultusu olabilir. Bunu
        # soylemeden "sira etkisi yok" demek, olculmemis bir seyi olculmus
        # gibi gostermek olurdu.
        print()
        for name, runs in results.items():
            totals = [r["total"] for r in runs if r["ok"] and r["kind"] == "temel"]
            ref = statistics.mean(totals) if totals else None
            noise = (max(totals) - min(totals)) if len(totals) > 1 else None
            for r in runs:
                if not (r["ok"] and r["kind"] != "temel" and ref is not None):
                    continue
                diff = r["total"] - ref
                verdict = ""
                if noise is not None:
                    verdict = ("  sicaklik gurultusunden AYRILAMAZ"
                               if abs(diff) <= noise
                               else "  gurultuden buyuk")
                print(f"  {name:<10} {r['kind']:<14} {r['total']} "
                      f"(temel ort. {ref:.1f}, fark {diff:+.1f}"
                      f"{f', sicaklik araligi {noise}' if noise is not None else ''})"
                      f"{verdict}")

    if args.fixtures:
        got = {n: (statistics.mean(v) if v else None) for n, v in base.items()}
        bad, mid, good = got.get("kotu"), got.get("orta"), got.get("iyi")
        print()
        if None in (bad, mid, good):
            print("KARAR VERILEMEDI: bir fikstur puan alamadi.")
            return 1
        coarse = good - bad
        fine = good - mid
        print(f"  kaba ayrim (iyi - kotu): {coarse:+.1f}   "
              f"{'gecti' if coarse >= 4 else 'ZAYIF'}")
        print(f"  ince ayrim (iyi - orta): {fine:+.1f}   "
              f"{'gecti' if fine >= 2 else 'ZAYIF -- uretimde ise yaramaz'}")
    print(f"\n{failed} kosu ayristirilamadi.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
