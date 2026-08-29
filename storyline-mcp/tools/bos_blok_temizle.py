"""Sondaki bos Block'lari var olan dosyalardan temizler -- BIR KERELIK.

NICIN AYRI BIR ARAC: kusur artik fonksiyonda degil, DOSYALARDA oturuyor.
`edits.set_shape_text` 2026-08-28'de duzeltildi ve bundan sonra sondaki bos
Block uretmiyor. Ama `_pick_template` / `find_seed` projenin KENDI slaydini
gomulu tohuma tercih eder, dolayisiyla duzeltmeden ONCE yazilmis kirli bir
soru slaydi tasiyan dosya, yeni sorulara ayni kusuru kopyalamaya devam eder.
Fonksiyonu duzeltmek yayilmayi durdurmaz; kaynagi temizlemek durdurur.

Ayni sebeple DONORLER de taranir: donor havuzu `find_seed`'in ikinci
sirasidir, yani kirli bir donor kusuru yeni kurslara tasiyabilir.

KURAL TEK YERDE: silme olcutu `edits._drop_trailing_empty_blocks`'tan gelir,
burada yeniden yazilmaz. Iki uygulama ayrisirdi.

KAPSAM: yalnizca metin belgelerinin SONUNDAKI bos Block'lar dusurulur.
Ortada duran bos Block'a DOKUNULMAZ (bilerek birakilmis bos paragraf
olabilir) ve bir belgenin tum Block'lari bosalacaksa biri korunur.
Bu arac slaytin baska hicbir yanini degistirmez.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storyline_mcp.edits import _drop_trailing_empty_blocks
from storyline_mcp.package import StoryPackage

YEDEK_SONEKI = ".bosblok-oncesi"


def tara(pkg: StoryPackage) -> list[tuple[str, str]]:
    """Temizlenecek (parca, belge_onizleme) ciftleri. Yazmaz."""
    bulunan = []
    for part in pkg.slide_parts:
        root = pkg.parse(part)
        for el in root.iter("text"):
            raw = (el.text or "").strip()
            if not raw.startswith("<Document"):
                continue
            if _drop_trailing_empty_blocks(raw) != raw:
                bulunan.append((part, raw[:70]))
    return bulunan


def temizle(pkg: StoryPackage) -> int:
    """Dosyayi temizler, degisen belge sayisini doner."""
    n = 0
    for part in pkg.slide_parts:
        root = pkg.parse(part)
        degisti = False
        for el in root.iter("text"):
            raw = (el.text or "").strip()
            if not raw.startswith("<Document"):
                continue
            yeni = _drop_trailing_empty_blocks(raw)
            if yeni != raw:
                el.text = yeni
                degisti = True
                n += 1
        if degisti:
            pkg.replace_xml(part, root)
    return n


def main() -> int:
    uygula = "--uygula" in sys.argv
    yollar = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not yollar:
        print("kullanim: python tools/bos_blok_temizle.py <dosya.story ...> [--uygula]")
        return 2

    toplam_dosya = toplam_belge = 0
    for yol in yollar:
        p = Path(yol)
        try:
            pkg = StoryPackage(str(p))
            bulunan = tara(pkg)
        except Exception as exc:  # bozuk ya da kilitli dosya isi durdurmasin
            print(f"  ATLA {p.name}: {type(exc).__name__}: {exc}")
            continue
        if not bulunan:
            print(f"  temiz {p.name}")
            continue
        toplam_dosya += 1
        toplam_belge += len(bulunan)
        print(f"  {p.name}: {len(bulunan)} belge")
        if not uygula:
            continue
        yedek = p.with_suffix(p.suffix + YEDEK_SONEKI)
        shutil.copy2(p, yedek)
        n = temizle(pkg)
        pkg.save(str(p))            # save() paketi yeniden acip dogrular
        sonra = tara(StoryPackage(str(p)))
        durum = "TEMIZ" if not sonra else f"HALA {len(sonra)}"
        print(f"      -> {n} belge yazildi, dogrulama: {durum}  (yedek: {yedek.name})")

    print()
    if uygula:
        print(f"UYGULANDI: {toplam_dosya} dosya, {toplam_belge} belge.")
    else:
        print(f"ONIZLEME: {toplam_dosya} dosya, {toplam_belge} belge temizlenecek.")
        print("Yazmak icin --uygula ekleyin.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
