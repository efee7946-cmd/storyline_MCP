"""Project, slide and player settings.

These live outside the shape tree, in three different places:

  * Slide behaviour  -- attributes on the slide root (advMode, hideToc, ...)
    plus <navData>, which is what the Slide Properties dialog writes when you
    switch the previous/next buttons off for a slide.
  * Story size       -- <sz w= h=> in story.xml. Note this is the *project*
    size; a shape's own <sldSz> is a separate per-shape reference frame.
  * Player colours   -- playerProps.xml, a different schema entirely: colours
    are <color rgb="0xRRGGBB" alpha="100"> grouped under named entries.

Nothing here clones: every value is a plain attribute Storyline already
understands, so these can be set outright rather than copied from an example.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from . import shapes
from .model import slide_index
from .package import STORY_PART, StoryPackage, StoryError
from .shapes import parse_color

PLAYER_PART = "story/playerProps.xml"

# Slide root attributes the Slide Properties dialog exposes.
SLIDE_FLAGS = {
    "advance_by_user": ("advMode", {True: "user", False: "auto"}),
    "hide_from_menu": ("hideToc", {True: "true", False: "false"}),
    "show_in_review": ("showInReview", {True: "true", False: "false"}),
    "count_in_slide_numbers": ("includeInSlideCounts", {True: "true", False: "false"}),
}

# <navData> switches: the player controls this slide is allowed to show.
NAV_FLAGS = ("prev", "next", "submit", "menu", "res", "glos", "notes",
             "seek", "replay", "play", "search")

# Storyline writes <navData> with its full attribute set, never a subset. A
# partial element -- only the switches a caller asked about -- parses as XML
# and fails to deserialise, so a newly created one starts from these defaults
# and the requested switches are applied on top.
NAV_DEFAULTS = {
    "prev": "true", "prevGesture": "true", "next": "true", "nextGesture": "true",
    "submit": "false", "default": "true", "menu": "true", "res": "true",
    "glos": "false", "notes": "false", "seek": "false", "replay": "false",
    "play": "true", "search": "false", "ltBxClse": "true",
}


def set_slide_properties(
    pkg: StoryPackage,
    slide: str,
    *,
    advance_by_user: bool | None = None,
    hide_from_menu: bool | None = None,
    show_in_review: bool | None = None,
    count_in_slide_numbers: bool | None = None,
    prev: bool | None = None,
    next: bool | None = None,
    submit: bool | None = None,
    menu: bool | None = None,
    seek: bool | None = None,
    replay: bool | None = None,
) -> dict:
    """Slide Properties: advance mode, menu visibility and player controls."""
    part = pkg.slide_part_for(slide)
    root = pkg.parse(part)
    changed: dict[str, str] = {}

    for key, (attr, mapping) in SLIDE_FLAGS.items():
        value = locals()[key]
        if value is not None:
            root.set(attr, mapping[bool(value)])
            changed[attr] = mapping[bool(value)]

    # A blank slide may carry no <navData> yet; it has a declared position in
    # the sequence and a required attribute set, so neither can be improvised.
    nav = shapes.insert_in_order(root, ET.Element("navData", dict(NAV_DEFAULTS)))
    for name, value in (("prev", prev), ("next", next), ("submit", submit),
                        ("menu", menu), ("seek", seek), ("replay", replay)):
        if value is not None:
            nav.set(name, "true" if value else "false")
            changed[f"navData/{name}"] = nav.get(name)

    if not changed:
        raise StoryError("Degistirilecek bir ozellik verilmedi.")
    pkg.replace_xml(part, root)
    return {"slide": slide, "changed": changed}


def read_slide_properties(pkg: StoryPackage, slide: str) -> dict:
    part = pkg.slide_part_for(slide)
    root = pkg.parse(part)
    nav = root.find("navData")
    return {
        "slide": slide,
        "name": root.get("name", ""),
        "advance": root.get("advMode", ""),
        "hidden_from_menu": root.get("hideToc") == "true",
        "show_in_review": root.get("showInReview") == "true",
        "counted": root.get("includeInSlideCounts") == "true",
        "navigation": {k: nav.get(k) for k in NAV_FLAGS} if nav is not None else {},
    }


# ---------------------------------------------------------------- story size


def _size_node(root: ET.Element) -> ET.Element | None:
    """The project's <sz>, which sits at story > propLst > prop > sz.

    Not a direct child of the root, and propLst holds other props too, so the
    tree is searched for the first <sz> carrying a real size.
    """
    for node in root.iter("sz"):
        try:
            if float(node.get("w", 0)) > 0 and float(node.get("h", 0)) > 0:
                return node
        except ValueError:
            continue
    return None


def story_size(pkg: StoryPackage) -> tuple[int, int]:
    node = _size_node(pkg.parse(STORY_PART))
    if node is None:
        raise StoryError("story.xml icinde slayt boyutu bulunamadi.")
    return int(float(node.get("w"))), int(float(node.get("h")))


def set_story_size(pkg: StoryPackage, width: int, height: int) -> dict:
    """Resize the project.

    Only the declared project size changes; existing shapes keep their own
    coordinates, exactly as they do when the size is changed in Storyline.
    """
    if width < 1 or height < 1:
        raise StoryError("Genislik ve yukseklik pozitif olmali.")
    root = pkg.parse(STORY_PART)
    node = _size_node(root)
    if node is None:
        raise StoryError("story.xml icinde slayt boyutu bulunamadi.")
    before = (node.get("w"), node.get("h"))
    node.set("w", str(int(width)))
    node.set("h", str(int(height)))
    pkg.replace_xml(STORY_PART, root)
    return {"before": before, "after": (str(width), str(height))}


# ----------------------------------------------------------------- theme

# The theme's colours and fonts are not in theme.xml -- that part holds only an
# asset list and a list of master ids. They live on each slide master, as
# <clrLst> and <fonts>, which is why searching the file named "theme" for a
# colour scheme finds nothing.
THEME_SLOTS = ("dk1", "lt1", "dk2", "lt2", "accent1", "accent2", "accent3",
               "accent4", "accent5", "accent6", "hlink", "folHlink")


def _master_parts(pkg: StoryPackage) -> list[str]:
    return sorted(
        n for n in pkg._order
        if "slideMasters/slideMaster" in n and n.endswith(".xml") and "_rels" not in n
    )


def slot_colors(pkg: StoryPackage) -> dict[str, str]:
    """`schemeClr val="accent1"` -> `#4F81BD`. Asillarin clrLst'inden okunur.

    Bir sekil hangi asla bagli oldugunu SOYLEMEZ, o yuzden asillar birlestirilir
    ve ilki kazanir. Olculdu (2026-09-05, uretilmis kurs): dort asil da ayni
    paleti tasiyor, yani birlestirme bugun kayipsiz. Asiller ayrisirsa bu
    fonksiyon yanlis renk dondurur -- o gun burasi slayt->asil baginı cozmek
    zorunda kalir; bugun o bag YOK ve varmis gibi yapmiyoruz.
    """
    birlesik: dict[str, str] = {}
    for master in read_theme(pkg)["masters"]:
        for yuva, renk in (master.get("colors") or {}).items():
            birlesik.setdefault(yuva, renk)
    return birlesik


def read_theme(pkg: StoryPackage) -> dict:
    """The colour slots and font of each slide master."""
    out = []
    for part in _master_parts(pkg):
        root = pkg.parse(part)
        colours = {}
        clr_list = root.find("clrLst")
        for slot in list(clr_list) if clr_list is not None else []:
            srgb = slot.find("srgbClr")
            if srgb is not None:
                colours[slot.tag] = "#" + (srgb.get("val") or "")
        fonts = root.find("fonts")
        out.append({
            "master": part.rsplit("/", 1)[1],
            "name": root.get("name"),
            "palette": clr_list.get("name") if clr_list is not None else None,
            "colors": colours,
            "font": fonts.get("name") if fonts is not None else None,
        })
    return {"masters": out, "slots": list(THEME_SLOTS)}


def set_theme_colors(pkg: StoryPackage, colors: dict, master: str | None = None) -> dict:
    """Recolour theme slots, on one master or on all of them.

    Shapes that reference a slot -- <schemeClr val="accent1"> -- follow this,
    so one change restyles everything drawn from the theme rather than each
    shape being repainted one at a time.
    """
    wanted = {k: parse_color(v) for k, v in (colors or {}).items()}
    unknown = sorted(set(wanted) - set(THEME_SLOTS))
    if unknown:
        raise StoryError(f"Bilinmeyen renk yuvasi: {unknown}. Gecerli: {list(THEME_SLOTS)}")
    if not wanted:
        raise StoryError("Degistirilecek renk verilmedi.")

    changed = []
    for part in _master_parts(pkg):
        root = pkg.parse(part)
        if master and part.rsplit("/", 1)[1] != master and root.get("name") != master:
            continue
        clr_list = root.find("clrLst")
        if clr_list is None:
            continue
        touched = {}
        for slot, value in wanted.items():
            node = clr_list.find(slot)
            if node is None:
                continue
            srgb = node.find("srgbClr")
            if srgb is None:
                for child in list(node):
                    node.remove(child)
                srgb = ET.SubElement(node, "srgbClr")
            touched[slot] = "#" + value
            srgb.set("val", value)
        if touched:
            pkg.replace_xml(part, root)
            changed.append({"master": root.get("name"), "colors": touched})
    if not changed:
        raise StoryError("Hicbir master guncellenmedi.")
    return {"masters_changed": changed}


def set_theme_font(pkg: StoryPackage, font: str, master: str | None = None) -> dict:
    """Set the theme font on the slide masters."""
    if not font.strip():
        raise StoryError("Font adi bos.")
    changed = []
    for part in _master_parts(pkg):
        root = pkg.parse(part)
        if master and part.rsplit("/", 1)[1] != master and root.get("name") != master:
            continue
        fonts = root.find("fonts")
        if fonts is None:
            continue
        before = fonts.get("name")
        for attr in ("name", "major", "minor"):
            fonts.set(attr, font)
        pkg.replace_xml(part, root)
        changed.append({"master": root.get("name"), "before": before, "after": font})
    if not changed:
        raise StoryError("Hicbir master guncellenmedi.")
    return {"font": font, "masters_changed": changed}


# -------------------------------------------------------------- player colours


GROUP_RE = re.compile(
    r'<color_group name="(?P<name>[^"]+)">(?P<body>.*?)</color_group>', re.S
)


def _color_pattern(name: str) -> re.Pattern[str]:
    """Match the rgb/alpha pair belonging to one named player colour.

    The value is three levels down -- <color name> wraps a <fill>, which wraps
    <colors>, which holds the actual <color rgb= alpha=>. Matching the name and
    the value together is what keeps the substitution on the right entry.
    """
    return re.compile(
        rf'(<color name="{re.escape(name)}">\s*<fill[^>]*>\s*<colors>\s*<color )'
        rf'rgb="[^"]*" alpha="[^"]*"'
    )


def list_player_colors(pkg: StoryPackage) -> dict:
    """Player colours by group.

    The same name appears in several groups -- "bg" exists under menu, infopanel
    and others -- so a caller that means one of them needs the group too.
    """
    raw = pkg.read(PLAYER_PART).decode("utf-8")
    groups = {
        m.group("name"): sorted(set(re.findall(r'<color name="([^"]+)"', m.group("body"))))
        for m in GROUP_RE.finditer(raw)
    }
    return {
        "groups": groups,
        "all_colors": sorted({c for v in groups.values() for c in v}),
    }


def set_player_color(
    pkg: StoryPackage, name: str, color: str, alpha: int = 100, group: str | None = None
) -> dict:
    """Recolour a named player entry, optionally within one group only.

    playerProps.xml is edited as text: it uses a schema unrelated to the slide
    format and declares namespaces ElementTree would drop, so a targeted
    substitution is both safer and smaller than a round trip.
    """
    if not 0 <= alpha <= 100:
        raise StoryError("alpha 0-100 araliginda olmali.")
    rgb = "0x" + parse_color(color)
    raw = pkg.read(PLAYER_PART).decode("utf-8")
    pattern = _color_pattern(name)
    replacement = rf'\g<1>rgb="{rgb}" alpha="{alpha}"'

    if group:
        found = False
        pieces: list[str] = []
        last = 0
        total = 0
        for m in GROUP_RE.finditer(raw):
            if m.group("name") != group:
                continue
            found = True
            body, count = pattern.subn(replacement, m.group("body"))
            total += count
            pieces.append(raw[last : m.start("body")] + body)
            last = m.end("body")
        if not found:
            raise StoryError(f"Player grubu bulunamadi: {group!r}")
        updated, count = "".join(pieces) + raw[last:], total
    else:
        updated, count = pattern.subn(replacement, raw)

    if not count:
        where = f" ({group} grubunda)" if group else ""
        raise StoryError(
            f"Player renginde {name!r} bulunamadi{where}. "
            f"list_player_colors ile adlari gorun."
        )
    pkg.replace_raw(PLAYER_PART, updated.encode("utf-8"))
    return {"color": name, "group": group, "rgb": rgb, "alpha": alpha, "occurrences": count}
