"""Bir kursta HAREKET var mi -- sayarak, bakarak degil.

Bir kursun hareketsiz oldugu onizlemeye bakarak anlasilmaz: onizleme her
nesneyi yerinde cizer, ve zaman cizgisi orada yok. Uretilen kurslarin
tamaminin hareketsiz oldugu da bu yuzden aylarca gorulmedi -- dosya gecerli,
slayt dolu, hicbir kontrol bagirmiyor.

Bu sonda ucunu ayirir, cunku ucu de "hareket yok" gibi gorunur:

    KURULMAMIS   animEffect bos VE her start=0.  Panelin bugune kadarki hali.
    YARIM        animasyon var ama kademelenme yok (hepsi start=0), ya da
                 tersi. Ikisi ayri yerde yaziliyor ve ayri ayri dusebilir.
    KIRPILMIS    start+dur, slaydin uzunluguna ESIT DEGIL. anim.py'nin
                 belgeledigi kural bu; bozuldugunda nesne sonundan kesilir ve
                 dosya yine tamamen gecerli gorunur.

Kullanim:
    python tools/hareket.py KURS.story [...]
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from storyline_mcp import anim
from storyline_mcp.package import StoryPackage, StoryError


def olc(path: Path) -> dict:
    pkg = StoryPackage(path)
    sekil = animasyonlu = kademeli = 0
    kirpilmis: list[str] = []
    efektler: Counter = Counter()
    basla: Counter = Counter()
    hareketsiz_slayt = 0

    for part in pkg.slide_parts:
        kayitlar = anim.describe(pkg, part)
        if not kayitlar:
            continue
        uzunluk = max((r["start_ms"] or 0) + (r["dur_ms"] or 0)
                      for r in kayitlar)
        slayt_animasyonlu = 0
        for r in kayitlar:
            if r["start_ms"] is None:
                continue
            sekil += 1
            basla[r["start_ms"]] += 1
            if r["start_ms"]:
                kademeli += 1
            if r["entrance"]:
                animasyonlu += 1
                slayt_animasyonlu += 1
                efektler[r["entrance"]["effect"]] += 1
            # Kirpilma yalnizca ZAMAN CIZGISINE OTURTULMUS nesnelerde
            # anlamli: hic dokunulmamis bir slaytta sureler tohumdan gelir
            # ve birbirinden farkli olmalari kusur degildir.
            if r["start_ms"] and r["start_ms"] + (r["dur_ms"] or 0) != uzunluk:
                kirpilmis.append(f"{Path(part).name}:{r['name'] or r['shape']}")
        if not slayt_animasyonlu:
            hareketsiz_slayt += 1

    if not sekil:
        durum = "SEKIL YOK"
    elif not animasyonlu and not kademeli:
        durum = "KURULMAMIS"
    elif kirpilmis:
        durum = "KIRPILMIS"
    elif not animasyonlu or not kademeli:
        durum = "YARIM"
    else:
        durum = "KURULU"

    return {
        "dosya": path.name,
        "durum": durum,
        "slayt": len(pkg.slide_parts),
        "hareketsiz_slayt": hareketsiz_slayt,
        "sekil": sekil,
        "animasyonlu": animasyonlu,
        "kademeli": kademeli,
        "efektler": dict(efektler.most_common()),
        "start_dagilimi": dict(sorted(basla.items())),
        "kirpilmis": kirpilmis[:10],
        "kirpilmis_sayisi": len(kirpilmis),
    }


def main() -> int:
    hedefler = [Path(a) for a in sys.argv[1:]]
    if not hedefler:
        print(__doc__.strip())
        return 2
    kotu = 0
    for hedef in hedefler:
        try:
            r = olc(hedef)
        except StoryError as exc:
            print(f"!! {hedef.name}: {exc}")
            kotu += 1
            continue
        print(f"\n{r['dosya']}  ->  {r['durum']}")
        print(f"  slayt {r['slayt']} ({r['hareketsiz_slayt']} tanesi hareketsiz), "
              f"sekil {r['sekil']}")
        print(f"  animasyonlu {r['animasyonlu']}, kademeli (start>0) {r['kademeli']}")
        if r["efektler"]:
            print(f"  efektler: {r['efektler']}")
        print(f"  start dagilimi: {r['start_dagilimi']}")
        if r["kirpilmis_sayisi"]:
            print(f"  KIRPILMIS {r['kirpilmis_sayisi']} nesne: {r['kirpilmis']}")
        if r["durum"] in ("KURULMAMIS", "YARIM", "KIRPILMIS"):
            kotu += 1
    return 1 if kotu else 0


if __name__ == "__main__":
    raise SystemExit(main())
