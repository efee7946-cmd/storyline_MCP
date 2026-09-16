"""Sablon sahnelerini AKIS DISI isaretle: sahnenin `desc` alanina onek.

NE ICIN. MCP yolunda sahneler arasi ILERI zinciri akista sayilan sahnelerden
kuruluyor (`authoring.akis_sahneleri`): ISARETSIZ HER SAHNE AKISTA. Bir sablon
dosyasi kursa ait OLMAYAN sahneler tasiyorsa -- `bos.story`de "Ana Menu" ve
"SINAV" -- sahibi onlari BIR KEZ bu aracla isaretler. Anlamin ve tasiyicinin
gerekcesi `authoring.AKIS_DISI_ISARETI`nin yaninda.

NEDEN ARAC, TEK SEFERLIK DUZENLEME DEGIL. Sablon genelde SURUMLENMIYOR
(`test/` .gitignore altinda), yani isaretin NASIL kondugu baska hicbir yerde
kalmaz. Arac prosedurü korur ve sahibinin kuracagi baska sablonlarda da calisir.
Kapilar da KENDI fikstur kopyalarini bununla isaretler: boylece hicbir kapinin
yesili kullanicinin yerel `bos.story`sinin isaretli olmasina baglanmaz (temiz
klonda da ayni sonuc) ve bu arac her kapi kosusunda sinanmis kalir.

DAVRANIS:
  * Sahne ADIYLA secilir (NFC + casefold). Bilinmeyen ya da BIRDEN FAZLA
    sahneye uyan ad varsa HICBIR SEY yazilmaz.
  * Zaten isaretliyse dokunulmaz. Var olan aciklama korunur: isaret ONUNE
    eklenir ("[akis-disi] eski aciklama").
  * CLI tarihli, acik adli bir yedek alir ve var olan yedegin ustune yazmaz.
    Kapilar `yedek=False` ile kendi kopyalarini isaretler.
  * Storyline dosyayi tutuyorsa (kilitli) CLI yazmaz.

    python tools/sablon_isaretle.py <dosya.story> --liste
    python tools/sablon_isaretle.py <dosya.story> <sahne adi> [<sahne adi> ...]
"""

from __future__ import annotations

import datetime
import pathlib
import shutil
import sys
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from storyline_mcp import authoring                        # noqa: E402
from storyline_mcp.package import STORY_PART, StoryPackage  # noqa: E402


def _ad(metin: str | None) -> str:
    return unicodedata.normalize("NFC", metin or "").strip().casefold()


def sahneler(yol: str | pathlib.Path) -> list[dict]:
    """sceneLst sirasinda (ad, isaretli mi, desc)."""
    story = StoryPackage(yol).parse(STORY_PART)
    return [{"ad": s.get("name"), "isaretli": authoring.akis_disi_mi(s),
             "desc": s.get("desc") or ""}
            for s in (story.find("sceneLst") or [])]


def isaretle(yol: str | pathlib.Path, adlar: list[str], *,
             yedek: bool = True) -> dict:
    """Adlari verilen sahneleri akis disi isaretle. Rapor doner, hata firlatmaz."""
    yol = pathlib.Path(yol)
    pkg = StoryPackage(yol)
    story = pkg.parse(STORY_PART)
    elemanlar = list(story.find("sceneLst") or [])
    ada_gore: dict[str, list] = {}
    for s in elemanlar:
        ada_gore.setdefault(_ad(s.get("name")), []).append(s)
    rapor = {"isaretlenen": [], "zaten": [], "bilinmeyen": [],
             "belirsiz": [], "yedek": None, "yazildi": False,
             "mevcut": [s.get("name") for s in elemanlar]}
    for ad in adlar:
        uyan = ada_gore.get(_ad(ad), [])
        if not uyan:
            rapor["bilinmeyen"].append(ad)
        elif len(uyan) > 1:
            rapor["belirsiz"].append(ad)
    if rapor["bilinmeyen"] or rapor["belirsiz"]:
        return rapor                                   # HICBIR SEY yazilmaz

    for ad in adlar:
        sahne = ada_gore[_ad(ad)][0]
        if authoring.akis_disi_mi(sahne):
            rapor["zaten"].append(sahne.get("name"))
            continue
        eski = sahne.get("desc") or ""
        sahne.set("desc", authoring.AKIS_DISI_ISARETI + (" " + eski if eski else ""))
        rapor["isaretlenen"].append(sahne.get("name"))

    if not rapor["isaretlenen"]:
        return rapor
    if yedek:
        bugun = datetime.date.today().isoformat()
        hedef = yol.with_name(f"{yol.name}.isaret-oncesi-{bugun}.bak")
        if hedef.exists():
            saat = datetime.datetime.now().strftime("%H%M%S")
            hedef = yol.with_name(f"{yol.name}.isaret-oncesi-{bugun}-{saat}.bak")
        shutil.copy2(yol, hedef)
        rapor["yedek"] = str(hedef)
    pkg.replace_xml(STORY_PART, story)
    pkg.save(yol, backup=False)
    rapor["yazildi"] = True
    return rapor


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    yol = pathlib.Path(sys.argv[1])
    if not yol.is_file():
        print(f"DOSYA YOK: {yol}")
        return 2
    if sys.argv[2] == "--liste":
        for s in sahneler(yol):
            print(f"  {'[akis disi]' if s['isaretli'] else '[akista]   '} "
                  f"{s['ad']!r}  desc={s['desc']!r}")
        return 0
    from storyline_mcp.package import lock_state
    if lock_state(yol) != "free":
        print("DOSYA KILITLI (Storyline'da acik olabilir) -- yazilmadi.")
        return 3
    rapor = isaretle(yol, sys.argv[2:], yedek=True)
    if rapor["bilinmeyen"] or rapor["belirsiz"]:
        print(f"YAZILMADI. bilinmeyen={rapor['bilinmeyen']} "
              f"belirsiz={rapor['belirsiz']}")
        print(f"  dosyadaki sahneler: {rapor['mevcut']}")
        return 2
    print(f"isaretlenen: {rapor['isaretlenen']}")
    print(f"zaten isaretli: {rapor['zaten']}")
    print(f"yedek: {rapor['yedek']}")
    for s in sahneler(yol):
        print(f"  {'[akis disi]' if s['isaretli'] else '[akista]   '} "
              f"{s['ad']!r}  desc={s['desc']!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
