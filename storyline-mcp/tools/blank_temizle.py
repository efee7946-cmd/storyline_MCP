"""Kurs artiklarini bos sablondan cikarir -- BIR KERELIK.

NICIN VAR: `test/bos.story` bir BOS SABLON olmali; kurucu onu kopyalayip
uzerine kurar, `themes_check` her tema icin ondan bir kopya alir. Ama dosya
bos degildi -- olculdu 2026-09-05: 37 slayt, 22 `fakeTrigger`, alti soru ve
bir surukle-birak slaydi. Kaynagi belli: silinen `panel/debug_build.py` bos
sablonun uzerine tam bir kurs kurmustu.

BEDELI OLCULDU, VARSAYILMADI:

  * `themes_check` bos sablonu kopyalayip yalnizca ilk alti slaydi besteler,
    sonra PAKETIN TAMAMINI olcer. Devralinan surukle-birak slaydinin grup
    kutulari `<schemeClr val="accent1"/>` ile temaya bagli, tema yuvasi ise
    yazilmiyor; uzerlerindeki beyaz yazi 4.03 veriyor (esik 4.5). Alti temanin
    ALTISINDA da ayni dort uyari cikiyordu -- 24 "sorun", tek bir devralinan
    slayttan.
  * `produced.py`'nin kontrast kusurlarinin DORDU de ayni slayttaydi
    (`slide18.xml`), yani urun yolunda degil, fiksturde.
  * Uretilen her kursa 22 "baslayinca sonraki slayta atla" tetikleyicisi
    devrediliyordu.

NE TUTULUR: adi olmayan, etkilesim tasimayan ve `fakeTrigger` tasimayan
slaytlar. Bunlar sablonun kendi bos slaytlari. `themes_check` en az
`len(compose.variants_for("content"))` slayt ister; tutulan sayi bunun
altina duserse arac DURUR ve dosyaya dokunmaz.

BES YER: bir slayt bes yerde kayitlidir ve biri atlanirsa Storyline ya slaydi
sessizce duşurur ya da dosyayi reddeder (bkz. README "Slayt uretimi"). Silme
de ayni bes yeri gezer:

    1. story/slides/slideN.xml            parcanin kendisi
    2. story/slides/_rels/slideN.xml.rels iliski parcasi
    3. story/_rels/story.xml.rels         parca <-> iliski kimligi
    4. story/story.xml                    sahne sldIdLst + tocSlideEntry
    5. [Content_Types].xml                Override

Bosalan sahneler de kaldirilir; sahnesiz kalan bir sldIdLst Storyline'da
gorunmez bir sahne birakir.

DOGRULAMA BURADA BITMEZ: `pkg.save` paketi dogrular, ama "gecerli paket"
"Storyline aciyor" demek degildir (bkz. DEVIR.md K33). Bu arac kosulduktan
sonra `tools/open_test.py` ile acilma sinanmalidir.

    python tools/blank_temizle.py                # ne yapacagini yazar
    python tools/blank_temizle.py --uygula       # yazar
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from storyline_mcp import compose  # noqa: E402
from storyline_mcp.package import STORY_PART, StoryPackage  # noqa: E402

HEDEF = ROOT.parent / "test" / "bos.story"
CT = "[Content_Types].xml"
REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
CT_NS = "{http://schemas.openxmlformats.org/package/2006/content-types}"


def _slayt_parcalari(pkg: StoryPackage) -> list[str]:
    return [n for n in pkg._order
            if n.startswith("story/slides/slide") and n.endswith(".xml")
            and "_rels" not in n]


def _kirli_mi(raw: bytes) -> tuple[bool, str]:
    """Bu slayt kurs artigi mi? Gerekcesiyle birlikte doner."""
    metin = raw.decode("utf-8", "replace")
    kok = ET.fromstring(raw)
    ad = (kok.get("name") or "").strip()
    if ad:
        return True, f"adlandirilmis ({ad[:28]})"
    intr = sorted(set(re.findall(r"<(\w+Intr)\b", metin)))
    if intr:
        return True, f"etkilesim ({','.join(intr)})"
    if 'name="fakeTrigger"' in metin:
        return True, "fakeTrigger"
    return False, ""


def plan(pkg: StoryPackage) -> tuple[list[str], list[tuple[str, str]]]:
    tut, at = [], []
    for part in _slayt_parcalari(pkg):
        kirli, neden = _kirli_mi(pkg.read(part))
        (at if kirli else tut).append(part if not kirli else (part, neden))
    return tut, at


def uygula(pkg: StoryPackage, atilacak: list[str]) -> dict:
    # AD ALANLI PARCALAR METIN OLARAK DUZENLENIR.
    #
    # `[Content_Types].xml` ve `story.xml.rels` varsayilan ad alani tasiyor
    # (`<Types xmlns="...">`). ElementTree ile parse edip geri yazmak onlari
    # `<ns0:Types xmlns:ns0="...">` haline getiriyor ve Storyline paketi
    # ACMIYOR -- olculdu 2026-09-05, kendi gunlugunde yazili:
    #
    #   System.Xml.XmlException: Required Types tag not found. Line 1, pos 57
    #     at ContentTypeHelper.ParseContentTypesFile(...)
    #
    # `verify()` bunu YAKALAMAZ: dosya kusursuz bicimli XML. Kod tabani kurali
    # zaten biliyor -- `clone._register_content_type` ve `_register_story_rel`
    # bu iki dosyaya `replace_raw` ile, metin olarak dokunuyor. Ayni yol.
    #
    # `story.xml`'in ad alani YOK (`<story>`, `<sceneLst>` ciplak), orada
    # ElementTree guvenli.
    story = pkg.parse(STORY_PART)
    rels_ham = pkg.read("story/_rels/story.xml.rels").decode("utf-8-sig")
    ct_ham = pkg.read(CT).decode("utf-8-sig")

    # part -> rel id   (hedefler mutlak: /story/slides/slideN.xml)
    part_to_rel: dict[str, str] = {}
    for m in re.finditer(r"<Relationship\b[^>]*/>", rels_ham):
        etiket = m.group(0)
        hedef = re.search(r'Target="([^"]*)"', etiket)
        kimlik = re.search(r'Id="([^"]*)"', etiket)
        if hedef and kimlik:
            part_to_rel[hedef.group(1).lstrip("/")] = kimlik.group(1)

    atilan_rel = {part_to_rel.get(p) for p in atilacak}
    atilan_guid = {ET.fromstring(pkg.read(p)).get("g") for p in atilacak}

    # 4a. sahne sldIdLst
    sahne_lst = story.find("sceneLst")
    bosalan_sahne = []
    for sahne in list(sahne_lst or []):
        idl = sahne.find("sldIdLst")
        if idl is None:
            continue
        for sld in list(idl):
            if (sld.text or "").strip() in atilan_rel:
                idl.remove(sld)
        if len(idl) == 0:
            bosalan_sahne.append(sahne)

    # 4b. tocSlideEntry (refG = slaydin GUID'i)
    for ana in story.iter():
        for e in list(ana):
            if e.tag == "tocSlideEntry" and e.get("refG") in atilan_guid:
                ana.remove(e)

    # bosalan sahneler ve toc karsiliklari
    bos_guid = {s.get("g") for s in bosalan_sahne}
    for s in bosalan_sahne:
        sahne_lst.remove(s)
    for ana in story.iter():
        for e in list(ana):
            if e.tag == "tocSceneEntry" and e.get("refG") in bos_guid:
                ana.remove(e)

    # 3. story.xml.rels -- METIN
    def _rel_at(metin: str) -> str:
        def kalsin(m):
            kimlik = re.search(r'Id="([^"]*)"', m.group(0))
            return "" if (kimlik and kimlik.group(1) in atilan_rel) else m.group(0)
        return re.sub(r"<Relationship\b[^>]*/>", kalsin, metin)

    # 5. content types -- METIN
    atilan_yollar = set(atilacak) | {
        f"story/slides/_rels/{Path(p).name}.rels" for p in atilacak}

    def _ct_at(metin: str) -> str:
        def kalsin(m):
            yol = re.search(r'PartName="([^"]*)"', m.group(0))
            return "" if (yol and yol.group(1).lstrip("/") in atilan_yollar) else m.group(0)
        return re.sub(r"<Override\b[^>]*/>", kalsin, metin)

    yeni_rels = _rel_at(rels_ham)
    yeni_ct = _ct_at(ct_ham)
    # KOK ETIKET KORUNDU MU -- Storyline'in reddettigi tam olarak buydu.
    if not re.search(r"<Types\s+xmlns=", yeni_ct):
        raise SystemExit("[Content_Types].xml kok etiketi bozuldu; yazilmadi.")
    if not re.search(r"<Relationships\s+xmlns=", yeni_rels):
        raise SystemExit("story.xml.rels kok etiketi bozuldu; yazilmadi.")

    pkg.replace_xml(STORY_PART, story)
    pkg.replace_raw("story/_rels/story.xml.rels", yeni_rels.encode("utf-8"))
    pkg.replace_raw(CT, yeni_ct.encode("utf-8"))

    # 1 + 2. parcalar
    silinen = 0
    for yol in sorted(atilan_yollar):
        if yol in pkg._parts:
            del pkg._parts[yol]
            pkg._order.remove(yol)
            silinen += 1
    return {"parca": silinen, "sahne": len(bosalan_sahne)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--uygula", action="store_true", help="degisikligi yaz")
    ap.add_argument("--hedef", default=str(HEDEF))
    args = ap.parse_args()

    yol = Path(args.hedef)
    pkg = StoryPackage(yol)
    tut, at = plan(pkg)
    gerek = len(compose.variants_for("content"))

    print(f"{yol.name}: {len(tut) + len(at)} slayt")
    print(f"  TUTULACAK {len(tut):3}  (adsiz, etkilesimsiz, fakeTrigger'siz)")
    print(f"  ATILACAK  {len(at):3}")
    for part, neden in at[:8]:
        print(f"      {Path(part).name:16} {neden}")
    if len(at) > 8:
        print(f"      ... ve {len(at) - 8} tane daha")

    if len(tut) < gerek:
        print(f"\nDURDU: themes_check en az {gerek} slayt istiyor, "
              f"tutulacak {len(tut)} var. Dosyaya DOKUNULMADI.")
        return 2

    if not args.uygula:
        print("\n(kuru kosu -- yazmak icin --uygula)")
        return 0

    sonuc = uygula(pkg, [p for p, _ in at])
    rapor = pkg.save(yol, backup=True)
    print(f"\n{sonuc['parca']} parca, {sonuc['sahne']} bosalan sahne cikarildi.")
    print(f"dogrulama: {'temiz' if rapor['verified']['ok'] else rapor['verified']['problems'][:2]}")
    print("SIRADAKI: python tools/open_test.py <dosya>  -- gecerli paket "
          "acilir paket demek degildir.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
