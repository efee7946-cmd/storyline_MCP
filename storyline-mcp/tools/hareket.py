"""Bir kursta HAREKET var mi -- sayarak, bakarak degil.

Bir kursun hareketsiz oldugu onizlemeye bakarak anlasilmaz: onizleme her
nesneyi yerinde cizer, ve zaman cizgisi orada yok. Uretilen kurslarin
tamaminin hareketsiz oldugu da bu yuzden aylarca gorulmedi -- dosya gecerli,
slayt dolu, hicbir kontrol bagirmiyor.

Bu sonda ucunu ayirir, cunku ucu de "hareket yok" gibi gorunur:

    KURULMAMIS   animEffect bos VE her start=0.  Panelin bugune kadarki hali.
    YARIM        animasyon var ama kademelenme yok (hepsi start=0), ya da
                 tersi. Ikisi ayri yerde yaziliyor ve ayri ayri dusebilir.
    KIRPILMIS    start+dur, govdenin uzunluguna ESIT DEGIL. anim.py'nin
                 belgeledigi kural bu; bozuldugunda nesne sonundan kesilir ve
                 dosya yine tamamen gecerli gorunur.
    KATMANLAR OLU  Slayt kurulu, katmanlar hareketsiz. Ilk surumun kusuru
                 buydu ve hicbir sayi gostermiyordu: slayt kokune bakan bir
                 olcum "KURULU" der, ogrenci geri bildirim pop-up'inda
                 hicbir hareket gormez. Olculdu -- bir kursta 128 katman
                 sekli boyle sessizce disarida kalmisti.

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

    katman_sekli = katman_animasyonlu = 0

    for part in pkg.slide_parts:
        kayitlar = anim.describe(pkg, part)
        if not kayitlar:
            continue
        # HER GOVDE KENDI UZUNLUGUNU TASIR. Katman, kendi zaman cizgisi olan
        # ayri bir govde; hepsini tek havuzda toplayip tek bir uzunluk
        # hesaplamak, katmani slaydin uzunluguna gore olcer ve dokunulmamis
        # her katmani "KIRPILMIS" ilan ederdi.
        govdeler: dict = {}
        for r in kayitlar:
            govdeler.setdefault(r.get("layer"), []).append(r)

        slayt_animasyonlu = 0
        for govde_adi, grup in govdeler.items():
            uzunluk = max((r["start_ms"] or 0) + (r["dur_ms"] or 0)
                          for r in grup)
            for r in grup:
                if r["start_ms"] is None:
                    continue
                sekil += 1
                if govde_adi is not None:
                    katman_sekli += 1
                basla[r["start_ms"]] += 1
                if r["start_ms"]:
                    kademeli += 1
                if r["entrance"]:
                    animasyonlu += 1
                    efektler[r["entrance"]["effect"]] += 1
                    if govde_adi is None:
                        slayt_animasyonlu += 1
                    else:
                        katman_animasyonlu += 1
                # Kirpilma yalnizca ZAMAN CIZGISINE OTURTULMUS nesnelerde
                # anlamli: hic dokunulmamis bir slaytta sureler tohumdan
                # gelir ve birbirinden farkli olmalari kusur degildir.
                if r["start_ms"] and r["start_ms"] + (r["dur_ms"] or 0) != uzunluk:
                    yer = f"{Path(part).name}:{r['name'] or r['shape']}"
                    kirpilmis.append(yer if govde_adi is None
                                     else f"{yer} (katman {govde_adi})")
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
    elif katman_sekli and not katman_animasyonlu:
        # Slayt kurulu, katmanlar olu. Ilk surumun kusuru tam olarak buydu
        # ve hicbir sayi onu gostermiyordu: slayt kokune bakan bir olcum
        # "KURULU" diyor, ogrenci geri bildirim pop-up'inda hicbir hareket
        # gormuyordu.
        durum = "KATMANLAR OLU"
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
        "katman_sekli": katman_sekli,
        "katman_animasyonlu": katman_animasyonlu,
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
        print(f"  bunun KATMANLARDA olani: {r['katman_animasyonlu']}/"
              f"{r['katman_sekli']} sekil")
        if r["efektler"]:
            print(f"  efektler: {r['efektler']}")
        print(f"  start dagilimi: {r['start_dagilimi']}")
        if r["kirpilmis_sayisi"]:
            print(f"  KIRPILMIS {r['kirpilmis_sayisi']} nesne: {r['kirpilmis']}")
        if r["durum"] in ("KURULMAMIS", "YARIM", "KIRPILMIS", "KATMANLAR OLU"):
            kotu += 1
    return 1 if kotu else 0


if __name__ == "__main__":
    raise SystemExit(main())
