"""Slide creation by cloning.

Storyline has no "make me a slide" schema: a slide is a dense graph of GUIDs
wiring shapes to triggers, states, interactions and feedback layers, on top of
a timeline context (tmCtxLst) that must stay consistent. Generating that from
scratch is brittle, so new slides are made by cloning an existing one and
regenerating exactly the GUIDs that slide *defines*.

Which GUIDs those are is decidable. A slide defines every value that appears in
a g= or verG= attribute, and merely references everything else -- layouts,
masters, variables, other slides. Measured on a real deck: 122 defined, 27
referenced, 13 of those pointing outside the slide. Remapping only the defined
set yields a slide that is structurally identical and internally consistent,
still wired to the same external scaffolding, with every non-GUID byte intact.

A slide must be registered in five places to exist. Miss one and Storyline
either silently drops it or rejects the file:

  1. story/slides/slideN.xml             the slide part itself
  2. story/slides/_rels/slideN.xml.rels  its media relationships
  3. story/_rels/story.xml.rels          part <-> relationship id
  4. story/story.xml                     scene sldIdLst, and the toc entry
  5. [Content_Types].xml                 content-type override

Slide parts are numbered in hexadecimal: slide.xml is 1, slide9.xml is 9,
slidea.xml is 10, slide10.xml is 16.
"""

from __future__ import annotations

import random
import re
import string
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

from .model import slide_index
from .package import STORY_PART, STORY_RELS, StoryPackage, StoryError

CONTENT_TYPES = "[Content_Types].xml"
NULL_GUID = "00000000-0000-0000-0000-000000000000"
GUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
DEFINED_GUID_RE = re.compile(rf'(?<=\s)(?:g|verG)="({GUID})"')
REL_ID_CHARS = string.ascii_letters + string.digits


def new_guid() -> str:
    return str(uuid.uuid4())


def _new_rel_id(existing: set[str]) -> str:
    """Storyline's own form: 'R' followed by 11 alphanumerics."""
    while True:
        candidate = "R" + "".join(random.choices(REL_ID_CHARS, k=11))
        if candidate not in existing:
            return candidate


# ------------------------------------------------------------ slide numbering


def slide_part_name(index: int) -> str:
    """1 -> slide.xml, 2 -> slide2.xml, 10 -> slidea.xml, 16 -> slide10.xml."""
    return f"slide{'' if index == 1 else format(index, 'x')}.xml"


def next_slide_index(pkg: StoryPackage) -> int:
    used = set()
    for part in pkg.slide_parts:
        suffix = re.fullmatch(r"story/slides/slide([0-9a-f]*)\.xml", part)
        if suffix:
            used.add(int(suffix.group(1), 16) if suffix.group(1) else 1)
    index = 1
    while index in used:
        index += 1
    return index


# --------------------------------------------------------------- guid remapping


def _defined_guids(raw: str) -> set[str]:
    return {g for g in DEFINED_GUID_RE.findall(raw) if g != NULL_GUID}


def _remap_guids(raw: str, mapping: dict[str, str]) -> str:
    for old, new in mapping.items():
        raw = raw.replace(old, new)
    return raw


def _rewrite_root_attr(raw: str, attr: str, value: str) -> str:
    """Set an attribute on the slide's root element, touching nothing else."""
    start = raw.index("<", raw.index("?>") + 2)
    end = raw.index(">", start)
    tag = raw[start:end]
    escaped = value.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
    pattern = re.compile(rf'\s{re.escape(attr)}="[^"]*"')
    if pattern.search(tag):
        tag = pattern.sub(f' {attr}="{escaped}"', tag, count=1)
    else:
        tag = f'{tag} {attr}="{escaped}"'
    return raw[:start] + tag + raw[end:]


# ------------------------------------------------------------- registration


def _insert_before(raw: bytes, closing: str, fragment: str) -> bytes:
    text = raw.decode("utf-8")
    at = text.rindex(closing)
    return (text[:at] + fragment + text[at:]).encode("utf-8")


def _register_content_type(pkg: StoryPackage, part: str) -> None:
    fragment = f'<Override PartName="/{part}" ContentType="application/slide+xml" />'
    pkg.replace_raw(
        CONTENT_TYPES, _insert_before(pkg.read(CONTENT_TYPES), "</Types>", fragment)
    )


def _register_story_rel(pkg: StoryPackage, part: str) -> str:
    rels = pkg.read(STORY_RELS)
    existing = set(re.findall(r'Id="([^"]+)"', rels.decode("utf-8")))
    rel_id = _new_rel_id(existing)
    fragment = f'<Relationship Type="slide" Target="/{part}" Id="{rel_id}" />'
    pkg.replace_raw(STORY_RELS, _insert_before(rels, "</Relationships>", fragment))
    return rel_id


def _scene_element(story: ET.Element, scene_name: str | None, fallback_guid: str):
    scene_list = story.find("sceneLst")
    if scene_list is None:
        raise StoryError("story.xml icinde sceneLst yok.")
    if scene_name:
        for scene in scene_list:
            if scene.get("name") == scene_name:
                return scene
        raise StoryError(f"Sahne bulunamadi: {scene_name!r}")
    for scene in scene_list:
        if scene.get("g") == fallback_guid:
            return scene
    raise StoryError("Kaynak slaydin sahnesi cozulemedi.")


def _add_toc_entry(story: ET.Element, scene_guid: str, slide_guid: str) -> bool:
    """Mirror the source's menu entry. Result slides deliberately have none."""
    toc = story.find("toc")
    if toc is None:
        return False
    for scene_entry in toc.iter("tocSceneEntry"):
        if scene_entry.get("refG") != scene_guid:
            continue
        entries = scene_entry.find("entryLst")
        if entries is None:
            entries = ET.SubElement(scene_entry, "entryLst")
        entry = ET.SubElement(entries, "tocSlideEntry")
        entry.set("g", new_guid())
        entry.set("verG", new_guid())
        entry.set("refG", slide_guid)
        entry.set("corG", new_guid())
        entry.set("expanded", "true")
        ET.SubElement(entry, "entryLst")
        return True
    return False


def _source_has_toc_entry(story: ET.Element, slide_guid: str) -> bool:
    toc = story.find("toc")
    if toc is None:
        return False
    return any(e.get("refG") == slide_guid for e in toc.iter("tocSlideEntry"))


# -------------------------------------------------------------------- cloning


SEED_DIR = Path(__file__).resolve().parent / "seeds"


def install_slide(
    pkg: StoryPackage,
    raw: str,
    *,
    scene: str | None = None,
    name: str | None = None,
    rels: bytes | None = None,
) -> dict:
    """Register a slide given as XML, regenerating the GUIDs it defines.

    Used to bring in a bundled seed -- a question slide, say -- so a project
    that contains no such slide can still grow one. Only sound because the
    scaffolding a slide leans on is shared: measured across two projects,
    all 27 slide layouts and masters carry not just the same names but the
    same GUIDs, being Storyline's own default template. So layoutG and the
    feedback-master references resolve unchanged in the destination.
    """
    mapping = {old: new_guid() for old in _defined_guids(raw)}
    new_raw = _remap_guids(raw, mapping)
    slide_guid = re.search(rf'<sld[^>]*\sg="({GUID})"', new_raw)
    if slide_guid is None:
        raise StoryError("Slayt XML'inde kok GUID bulunamadi.")
    new_slide_guid = slide_guid.group(1)
    if name is not None:
        new_raw = _rewrite_root_attr(new_raw, "name", name)

    # SAHNE, HICBIR SEY YAZILMADAN ONCE COZULUR.
    #
    # Cozumleme eskiden asagida, parca/rels/content-type/story-rel YAZILDIKTAN
    # sonra duruyordu. Var olmayan bir sahne adi verildiginde cagri dogru
    # sekilde patliyordu ama paket ARTIK KIRLIYDI: slayt parcasi kaydedilmis,
    # hicbir sahnenin sldIdLst'ine girmemis -- yani SAHNESIZ bir slayt.
    #
    # Olculdu 2026-09-04: builder ilerleme katmanini kurarken var olmayan
    # "99_Sonuc" sahnesini istedi. Hata dogru raporlandi ("Sahne bulunamadi"),
    # kurs yine de 55 yerine 56 slaytla kaydedildi ve o fazladan slayt
    # uretilmis kursta iki kusur uretti (cakisma 1, taban 1) -- kaynagi
    # gorunmez, cunku hicbir sahnede degil.
    #
    # Yer degistirmenin bedeli yok: cozumleme salt-okunur, yan etkisi yok.
    story = pkg.parse(STORY_PART)
    scene_list = story.find("sceneLst")
    scene_el = None
    if scene:
        scene_el = next((s for s in (scene_list or []) if s.get("name") == scene), None)
        if scene_el is None:
            raise StoryError(f"Sahne bulunamadi: {scene!r}")
    elif scene_list is not None and len(scene_list):
        scene_el = scene_list[-1]
    if scene_el is None:
        raise StoryError("Slaydin ekleneceği sahne yok.")

    slides = pkg.slide_parts
    new_part = f"story/slides/{slide_part_name(next_slide_index(pkg))}"
    pkg.add_part(new_part, new_raw.encode("utf-8"),
                 after=slides[-1] if slides else None,
                 like=slides[-1] if slides else None)

    new_rels = f"story/slides/_rels/{new_part.rsplit('/', 1)[1]}.rels"
    if rels:
        pkg.add_part(new_rels, rels, like=f"story/slides/_rels/{slides[-1].rsplit('/', 1)[1]}.rels"
                     if slides else None)
    else:
        minimal_rels = b'<?xml version="1.0" encoding="utf-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>'
        pkg.add_part(new_rels, minimal_rels)

    _register_content_type(pkg, new_part)
    rel_id = _register_story_rel(pkg, new_part)

    # `story` ve `scene_el` YUKARIDA cozuldu. Burada yeniden parse etmek,
    # add_part/_register_* cagrilarinin arasinda story.xml'i degistirmis
    # olabilecegi varsayimina dayanirdi -- degistirmiyorlar, ve iki parse
    # ayrisirsa sldId yanlis agaca yazilirdi.
    id_list = scene_el.find("sldIdLst")
    if id_list is None:
        id_list = ET.SubElement(scene_el, "sldIdLst")
    sld_id = ET.Element("sldId")
    sld_id.text = rel_id
    id_list.append(sld_id)

    in_menu = _add_toc_entry(story, scene_el.get("g", ""), new_slide_guid)
    pkg.replace_xml(STORY_PART, story)

    return {
        "new_slide": new_part.rsplit("/", 1)[1],
        "part": new_part,
        "slide_guid": new_slide_guid,
        "scene": scene_el.get("name", ""),
        "guids_regenerated": len(mapping),
        "added_to_menu": in_menu,
        "source": "bundled",
    }


def clone_slide(
    pkg: StoryPackage,
    source: str,
    *,
    scene: str | None = None,
    name: str | None = None,
) -> dict:
    """Copy a slide, give it fresh identity, and register it in the package.

    scene: target scene name; defaults to the source slide's own scene.
    name:  title for the new slide; defaults to the source's name.
    """
    source_part = pkg.slide_part_for(source)
    index = slide_index(pkg)
    source_ref = index.get(source_part)
    if source_ref is None:
        raise StoryError(f"Kaynak slayt cozulemedi: {source}")

    raw = pkg.read(source_part).decode("utf-8")
    mapping = {old: new_guid() for old in _defined_guids(raw)}
    if source_ref.guid not in mapping:
        raise StoryError("Kaynak slaydin kendi GUID'i bulunamadi; klonlama guvenli degil.")
    new_raw = _remap_guids(raw, mapping)
    new_slide_guid = mapping[source_ref.guid]
    if name is not None:
        new_raw = _rewrite_root_attr(new_raw, "name", name)

    new_part = f"story/slides/{slide_part_name(next_slide_index(pkg))}"
    pkg.add_part(new_part, new_raw.encode("utf-8"), after=source_part)

    # Media relationships are shared, so the source's rels copy across as-is.
    source_rels = f"story/slides/_rels/{source_part.rsplit('/', 1)[1]}.rels"
    new_rels = f"story/slides/_rels/{new_part.rsplit('/', 1)[1]}.rels"
    if pkg.has_part(source_rels):
        pkg.add_part(new_rels, pkg.read(source_rels), after=source_rels)
    else:
        minimal_rels = b'<?xml version="1.0" encoding="utf-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>'
        pkg.add_part(new_rels, minimal_rels)

    _register_content_type(pkg, new_part)
    rel_id = _register_story_rel(pkg, new_part)

    story = pkg.parse(STORY_PART)
    scene_el = _scene_element(story, scene, source_ref.scene_guid)
    id_list = scene_el.find("sldIdLst")
    if id_list is None:
        id_list = ET.SubElement(scene_el, "sldIdLst")
    sld_id = ET.Element("sldId")
    sld_id.text = rel_id
    id_list.append(sld_id)

    in_menu = False
    if _source_has_toc_entry(story, source_ref.guid):
        in_menu = _add_toc_entry(story, scene_el.get("g", ""), new_slide_guid)
    pkg.replace_xml(STORY_PART, story)

    return {
        "new_slide": new_part.rsplit("/", 1)[1],
        "part": new_part,
        "slide_guid": new_slide_guid,
        "rel_id": rel_id,
        "scene": scene_el.get("name", ""),
        "cloned_from": source_ref.basename,
        "guids_regenerated": len(mapping),
        "added_to_menu": in_menu,
        "name": name if name is not None else source_ref.name,
    }


# --------------------------------------------------------------------- scenes


def create_scene(pkg: StoryPackage, name: str) -> dict:
    """Add an empty scene, with a matching menu entry."""
    story = pkg.parse(STORY_PART)
    scene_list = story.find("sceneLst")
    if scene_list is None:
        raise StoryError("story.xml icinde sceneLst yok.")
    if any(s.get("name") == name for s in scene_list):
        raise StoryError(f"Bu isimde bir sahne zaten var: {name!r}")

    scene_guid = new_guid()
    scene = ET.SubElement(scene_list, "scene")
    scene.set("g", scene_guid)
    scene.set("verG", new_guid())
    scene.set("name", name)
    scene.set("desc", "")
    scene.set("primaryId", NULL_GUID)
    scene.set("sceneType", "scene")
    scene.set("collapse", "false")
    ET.SubElement(scene, "sldIdLst")
    ET.SubElement(scene, "localizedName")

    toc = story.find("toc")
    in_menu = False
    if toc is not None:
        entries = toc.find("entryLst")
        if entries is None:
            entries = ET.SubElement(toc, "entryLst")
        scene_entry = ET.SubElement(entries, "tocSceneEntry")
        scene_entry.set("g", new_guid())
        scene_entry.set("verG", new_guid())
        scene_entry.set("refG", scene_guid)
        scene_entry.set("corG", new_guid())
        scene_entry.set("expanded", "true")
        ET.SubElement(scene_entry, "entryLst")
        in_menu = True

    pkg.replace_xml(STORY_PART, story)
    return {"scene": name, "scene_guid": scene_guid, "added_to_menu": in_menu}


def promote_scenes(pkg: StoryPackage, scene_guids: list[str]) -> dict:
    """Verilen sahneleri sceneLst'in ve menunun basina alir.

    Kursun acildigi ekran, sceneLst'in ILK sahnesinin ilk slaydidir: dosyada
    startSceneG gibi bir isaret YOK, bakildi. Kurucu kendi sahnelerini sona
    ekledigi icin ogrenci, sablondan devralinan bos bir slaytla karsilasiyordu
    -- kursun kendisi bir alt siradaydi.

    Hicbir sey SILINMEZ: devralinan sahneler yerinde kalir, yalnizca arkaya
    duser. Silmek de bir secenekti ve elenmesinin sebebi su: kurucu bos bir
    sablona da, kullanicinin kendi dolu kursuna da kosulabiliyor ve ikincisinde
    "devralinan" ile "kullanicinin icerigi" ayrimi guvenilir yapilamiyor.

    MENU DE TASINIR ve bu ayrintiyi atlamak sessiz bir tutarsizlik uretirdi:
    <toc> altindaki tocSceneEntry'ler sahne guid'ine refG ile baglidir ve
    siralari sceneLst'i AYNEN yansitir (olculdu). Yalnizca sceneLst
    siralansaydi dosya gecerli kalir, kurs dogru sahneden acilir, ama oynatici
    menusu eski sirayi gosterirdi -- gecerli dosya, yanlis davranis.
    """
    story = pkg.parse(STORY_PART)
    scene_list = story.find("sceneLst")
    if scene_list is None:
        raise StoryError("story.xml icinde sceneLst yok.")

    istenen = [g for g in scene_guids if g]
    tasinan = [s for s in scene_list if s.get("g") in istenen]
    if not tasinan:
        return {"promoted": 0, "menu": 0}
    # Kendi aralarindaki sira KORUNUR: bolumler 01, 02, 03 diye uretildi ve
    # one alirken karistirmak, duzeltilen seyden daha kotu bir kusur olurdu.
    for offset, scene in enumerate(tasinan):
        scene_list.remove(scene)
        scene_list.insert(offset, scene)

    menu = 0
    toc = story.find("toc")
    entries = toc.find("entryLst") if toc is not None else None
    if entries is not None:
        eslesen = [e for e in entries if e.get("refG") in istenen]
        for offset, entry in enumerate(eslesen):
            entries.remove(entry)
            entries.insert(offset, entry)
        menu = len(eslesen)

    pkg.replace_xml(STORY_PART, story)
    return {"promoted": len(tasinan), "menu": menu}
