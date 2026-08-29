"""Slaytları gerçekten gözle görülebilir bir görüntüye çevirir.

Buraya kadar her doğrulama yapısaldı: açılıyor mu, taşıyor mu, çakışıyor mu.
Hiçbiri "iyi görünüyor mu" sorusunu sormuyor -- ve bu projenin çözmeye
çalıştığı sorun tam olarak o. preview.py SVG üretiyordu ama SVG'yi kimse
açmadı; üretilmiş ama bakılmamış bir görüntü, üretilmemişle aynı.

Bu araç SVG'yi PNG'ye indirir (Chrome/Edge headless), böylece görüntü
okunabilir bir dosya olur.

BAGLAM YALANI -- bu dosyanin kendi tehlike sinifi. preview.py'nin sadakat
notu tek bir slayt uzerinden yazildi ve orada dogruydu; yalan, birden fazla
slaydi YAN YANA koyunca dogdu. Her SVG kendi degradesine "g0" adini
veriyordu, hepsi tek bir HTML sayfasina konunca ad cakisti ve tarayici
url(#g0)'i sayfadaki ILK tanima bagladi. Sonuc: acik zeminli bir tema koyu
lacivert cizildi, ve hata temada saniliyordu.

Onemli olan tek bir hatanin duzeltilmesi degil, sinifin adi: **tek basina
dogrulanmis bir cizim, bir araya getirildiginde yanlis olabilir.** SVG'de
belge genelinde benzersiz olmasi gereken her ad alani ayni cakismayi
yasar --

    linearGradient / radialGradient      (yasandi, duzeltildi)
    filter, mask, clipPath, pattern      (henuz kullanilmiyor)
    marker, symbol, font-face            (henuz kullanilmiyor)

Bunlardan biri eklendiginde kimligi slayta ozgu yapmak ZORUNLU. Ve bu sefer
gozle fark edilmeyebilir: degrade koyu-acik oldugu icin goze carpti, ama iki
slaydin ayni maskeyi paylasmasi cogu zaman makul gorunen bir sonuc uretir.

    python tools/look.py test/g2/Bilgi_Guvenligi.story -o bak.png
    python tools/look.py kurs.story --slides slide.xml slidea.xml --cols 3
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from storyline_mcp import model, preview
from storyline_mcp.package import StoryPackage

BROWSERS = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
]


def browser() -> Path:
    for path in BROWSERS:
        if path.is_file():
            return path
    raise SystemExit("Chrome/Edge bulunamadi; goruntu alinamaz.")


def page(pkg: StoryPackage, names: list[str], *, cols: int, card: int,
         labels: dict[str, str] | None = None) -> tuple[str, int, int]:
    """Slaytları bir ızgaraya dizip HTML döndürür, ve tuvalin boyutunu."""
    index = model.slide_index(pkg)
    cards, ratio = [], 0.5625
    for name in names:
        svg = preview.render_slide(pkg, name, width=card)
        ref = next((r for r in index.values() if r.basename == name), None)
        head = (labels or {}).get(name) or (ref.name if ref else name)
        # Oranı ilk slayttan öğren: 720x540 ile 1920x1080 farklı yüksekliklerde.
        if 'height="' in svg:
            h = svg.split('height="')[2].split('"')[0]
            ratio = float(h) / card
        cards.append(
            f'<figure><div class="s">{svg}</div>'
            f'<figcaption>{head}</figcaption></figure>')
    rows = -(-len(cards) // cols)
    width = cols * card + (cols + 1) * 16
    height = int(rows * (card * ratio + 34) + (rows + 1) * 16)
    html = f"""<!doctype html><meta charset="utf-8">
<style>
 body{{margin:0;background:#1b1e24;padding:16px;
      font:13px "Segoe UI",system-ui,sans-serif}}
 .g{{display:grid;gap:16px;grid-template-columns:repeat({cols},{card}px)}}
 figure{{margin:0}}
 .s{{border:1px solid #3a4049;border-radius:6px;overflow:hidden;background:#fff;
     line-height:0}}
 figcaption{{color:#aab2bd;padding:5px 2px}}
</style><div class="g">{''.join(cards)}</div>"""
    return html, width, height


def shoot(html: str, width: int, height: int, out: Path) -> Path:
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "look.html"
        src.write_text(html, encoding="utf-8")
        subprocess.run(
            [str(browser()), "--headless=new", "--disable-gpu", "--hide-scrollbars",
             f"--screenshot={out}", f"--window-size={width},{height}",
             f"--user-data-dir={tmp}/profile", src.as_uri()],
            capture_output=True, timeout=90,
        )
    if not out.is_file():
        raise SystemExit("Tarayici goruntu uretmedi.")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("story")
    parser.add_argument("-o", "--out", default="look.png")
    parser.add_argument("--slides", nargs="*")
    parser.add_argument("--cols", type=int, default=2)
    parser.add_argument("--card", type=int, default=520)
    args = parser.parse_args()

    story = Path(args.story).resolve()
    if not story.is_file():
        print(f"Proje yok: {story}")
        return 2
    pkg = StoryPackage(story)
    names = args.slides or [r.basename for r in model.slide_index(pkg).values()]
    html, w, h = page(pkg, names, cols=args.cols, card=args.card)
    out = shoot(html, w, h, Path(args.out).resolve())
    print(f"{len(names)} slayt -> {out}  ({w}x{h})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
