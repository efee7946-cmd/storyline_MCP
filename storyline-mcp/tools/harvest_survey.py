"""Inventory the donor pool before anything is taken out of it.

A donor is only worth carrying if it holds design the seed library does not
already have. Left unmeasured that is a matter of taste, so it is counted
instead: how many structurally distinct buttons, how many question looks, how
many objects that actually define states.

What counts as distinct follows the pool's own rule -- anatomy is harvested,
aesthetics are not. Two buttons that differ only in fill are one variant here,
because cloning the second one teaches the library nothing that cloning the
first did not. Colour, corner radius and font are GOREV 5's problem, not the
donor's contribution.

A button is counted by role, not by tag. Measured across the pool: six donors
hold 226 shapes carrying state lists and only 10 of them are <btn>. Designers
draw a rect, an oval, a chevron -- even a picture -- and give it states; the
<btn> element is what Storyline's own button tool emits, which is the uniform
look the pool exists to escape. Searching for the tag would find the pool
almost empty and would find exactly the wrong thing when it did hit.

Read-only: opens each project, reports, writes nothing. Deciding what to keep
is a separate step, and installing a seed is a third.
"""

from __future__ import annotations

import argparse
import collections
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from storyline_mcp import model
from storyline_mcp.clone import GUID, NULL_GUID
from storyline_mcp.harvest import app_version
from storyline_mcp.package import StoryPackage, lock_state

DONORS = ROOT / "donors"
QUESTION_KINDS = ("freePickOneIntr", "freePickManyIntr")
RICH_SLIDE = 6  # shapes, above which a slide is a composition worth studying
STOCK_STATES = ("Normal", "Hover", "Down", "Visited", "Disabled")

_GUID_RE = re.compile(GUID)
# Identity and ordering differ between two copies of the same design; they say
# nothing about whether the designs differ.
_IDENTITY_RE = re.compile(r'\s(?:g|verG|stateG|defG|corG|copiedG|id|zOrder)="[^"]*"')


# ------------------------------------------------------------------ anatomy


def walk_outside_states(node: ET.Element):
    """Every element on the slide except the ones inside a state body.

    A state's body is a complete shape element of its own, so a five-state
    button contains five further <btn> elements. Walked naively that is one
    button counted six times, reporting a button's own states as variants of
    it -- and the inflation is worst exactly where the design is richest.
    """
    for child in node:
        if child.tag == "stateLst":
            continue
        yield child
        yield from walk_outside_states(child)


def geometry(shape: ET.Element) -> str:
    """The silhouette. <prstGeom> names it with a child element, not an attribute.

    The child also carries vertexSet, which is how a hand-drawn path is told
    apart from a stock preset -- the difference between a kit that drew its own
    buttons and one that recoloured Storyline's. Shapes with no prstGeom at all
    (a picture used as a button, an imported vector) fall back to their tag.
    """
    geo = shape.find("prstGeom")
    if geo is None:
        return shape.tag
    child = next(iter(geo), None)
    if child is None:
        return shape.tag
    custom = "+cizim" if child.get("vertexSet") == "true" else ""
    return child.tag + custom


CLICK_EVENTS = frozenset({"OnClick", "OnRelease", "OnPress"})


def events(shape: ET.Element) -> frozenset[str]:
    """The events wired to this shape, if any."""
    found = set()
    for trig_list in shape.iter("trigLst"):
        for trig in trig_list:
            data = trig.find("data")
            if data is not None and data.get("event"):
                found.add(data.get("event"))
    return frozenset(found)


def is_candidate(shape: ET.Element) -> bool:
    """Worth cloning as a button: it defines states.

    Triggers are not required. A kit ships styled shapes with no wiring at all
    -- ButtonKit's 26 shapes have states and no triggers -- and that is the
    better donor, because a wired one would arrive pointing at someone else's
    navigation.
    """
    states = shape.find("stateLst")
    return states is not None and len(states) > 0


def state_names(shape: ET.Element) -> tuple[str, ...]:
    lst = shape.find("stateLst")
    return tuple(s.get("name") or "?" for s in (lst if lst is not None else []))


def carries_image(shape: ET.Element) -> bool:
    """An image-backed button is a different animal from a vector one."""
    return any(
        el.get("assetG") not in (None, "", NULL_GUID)
        for el in shape.iter()
    )


def _fingerprint(el: ET.Element) -> str:
    raw = ET.tostring(el, encoding="unicode")
    return _GUID_RE.sub("G", _IDENTITY_RE.sub("", raw))


def states_designed(shape: ET.Element) -> bool:
    """Do the state bodies actually differ, or are they five identical copies?

    Reported, but deliberately kept out of the variant signature: a button
    whose Hover differs from Normal only in colour is still one anatomy, and
    counting it twice would inflate the number the acceptance criterion reads.
    """
    lst = shape.find("stateLst")
    bodies = []
    for state in (lst if lst is not None else []):
        inner = state.find("shapeLst")
        if inner is not None and len(inner):
            bodies.append(_fingerprint(inner))
    return len(set(bodies)) > 1


def anatomy(shape: ET.Element) -> tuple:
    """What makes one button structurally different from another."""
    return (
        geometry(shape),
        state_names(shape),
        carries_image(shape),
        tuple(sorted({c.tag for c in shape})),
        bool(events(shape) & CLICK_EVENTS),
    )


def describe(sig: tuple, baseline: frozenset[str]) -> str:
    """Render a signature so two rows never read alike unless they are alike.

    The child-tag set is what separates most variants and it is far too long to
    print, so it is shown as a delta against what every button in the file has
    in common. A row with no delta shown differs in geometry, states or imagery
    -- which are printed in full.
    """
    geom, states, image, kids, clickable = sig
    bits = [geom]
    if states:
        bits.append(f"{len(states)} durum")
        custom = [s for s in states if s not in STOCK_STATES]
        if custom:
            bits.append("ozel:" + "/".join(custom[:3]))
    else:
        bits.append("durumsuz")
    bits.append("tiklanir" if clickable else "kit")
    if image:
        bits.append("gorselli")
    extra = sorted(set(kids) - baseline)
    missing = sorted(baseline - set(kids))
    if extra:
        bits.append("+" + ",".join(extra))
    if missing:
        bits.append("-" + ",".join(missing))
    return " · ".join(bits)


# ------------------------------------------------------------------ per file


def survey_file(path: Path) -> dict:
    """Everything one donor is worth, in one pass over its slides."""
    report: dict = {"file": path.name, "kb": path.stat().st_size // 1024,
                    "version": app_version(path)}

    lock = lock_state(path)
    if lock != "free":
        report["error"] = f"dosya mesgul ({lock}) — Storyline'da acik olabilir"
        return report
    try:
        pkg = StoryPackage(path)
        index = model.slide_index(pkg)
    except Exception as exc:
        report["error"] = f"okunamadi: {str(exc)[:60]}"
        return report

    buttons: dict[tuple, int] = collections.Counter()
    designed: set[tuple] = set()
    questions: dict[tuple, int] = collections.Counter()
    stateful: dict[str, int] = collections.Counter()
    rich = 0

    for part in index:
        root = pkg.parse(part)
        shape_list = root.find("shapeLst")
        top = list(shape_list) if shape_list is not None else []
        if not top:
            continue

        # Buttons hide inside groups and layers too, so the whole slide is
        # walked -- but never into a state body, which is a copy of its owner.
        for shape in walk_outside_states(root):
            if not is_candidate(shape):
                continue
            sig = anatomy(shape)
            buttons[sig] += 1
            stateful[shape.tag] += 1
            if states_designed(shape):
                designed.add(sig)

        interaction = next((s for s in top if s.tag in QUESTION_KINDS), None)
        if interaction is not None:
            choices = interaction.find("choices")
            count = len(list(choices)) if choices is not None else 0
            alongside = tuple(sorted({s.tag for s in top if not s.tag.endswith("Intr")}))
            questions[(interaction.tag, count, alongside)] += 1
        elif len(top) >= RICH_SLIDE:
            rich += 1

    report.update({
        "slides": len(index),
        "buttons": buttons,
        "designed": designed,
        "questions": questions,
        "stateful": stateful,
        "rich": rich,
    })
    return report


# ------------------------------------------------------------------ output


def print_file(report: dict, min_variants: int) -> None:
    head = f"{report['file']}  ({report['kb']} KB"
    if report.get("version"):
        head += f", surum {report['version']}"
    print(head + ")")

    if "error" in report:
        print(f"    ATLANDI — {report['error']}\n")
        return

    variants = len(report["buttons"])
    total = sum(report["buttons"].values())
    mark = "TAMAM" if variants >= min_variants else "ZAYIF"
    print(f"    {report['slides']} slayt · {report['rich']} zengin slayt (>={RICH_SLIDE} sekil)")
    print(f"    buton adayi: {variants} varyant / {total} adet  [{mark}]")
    baseline = frozenset.intersection(
        *(frozenset(sig[3]) for sig in report["buttons"])) if report["buttons"] else frozenset()
    for sig, n in report["buttons"].most_common(10):
        flag = "durumlari tasarlanmis" if sig in report["designed"] else "durumlar ayni"
        print(f"        x{n:<4} {describe(sig, baseline):<58} {flag}")
    if len(report["buttons"]) > 10:
        print(f"        ... {len(report['buttons']) - 10} varyant daha")

    if report["questions"]:
        print(f"    soru gorunumu: {len(report['questions'])} farkli")
        for (kind, count, alongside), n in report["questions"].most_common(6):
            print(f"        x{n:<4} {kind:<18} {count} secenek  yaninda={list(alongside)[:4]}")

    if report["stateful"]:
        items = ", ".join(f"{tag}x{n}" for tag, n in report["stateful"].most_common(6))
        print(f"    tasiyici eleman: {items}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", nargs="?", default=str(DONORS),
                        help="donor klasoru (varsayilan: donors/)")
    parser.add_argument("--min-variants", type=int, default=3,
                        help="dosya basina beklenen en az buton varyanti (varsayilan: 3)")
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"Klasor yok: {folder}")
        return 2

    files = sorted(folder.glob("*.story"))
    zipped = sorted(folder.glob("*.zip"))
    if zipped:
        print(f"!! {len(zipped)} zip dosyasi var, acilmamis: "
              f"{', '.join(z.name for z in zipped[:4])}")
        print("   Havuza .story girmeli; once bunlari ac.\n")
    if not files:
        print(f"Havuz bos: {folder}")
        print("Ne indirilecegi donors/README.md'de yaziyor.")
        return 2

    print(f"=== DONOR HAVUZU — {len(files)} dosya ===\n")
    reports = [survey_file(f) for f in files]
    for report in reports:
        print_file(report, args.min_variants)

    readable = [r for r in reports if "error" not in r]
    weak = [r for r in readable if len(r["buttons"]) < args.min_variants]
    unread = [r for r in reports if "error" in r]

    pool_buttons: set[tuple] = set()
    pool_questions: set[tuple] = set()
    for r in readable:
        pool_buttons |= set(r["buttons"])
        pool_questions |= set(r["questions"])

    geometries = {sig[0] for sig in pool_buttons}
    state_sets = {sig[1] for sig in pool_buttons}
    print("=== HAVUZ TOPLAMI ===")
    print(f"  okunabilen dosya : {len(readable)}/{len(files)}")
    print(f"  buton varyanti   : {len(pool_buttons)}")
    print(f"  farkli geometri  : {len(geometries)}  {sorted(geometries)}")
    print(f"  farkli durum seti: {len(state_sets)}")
    print(f"  farkli soru      : {len(pool_questions)}")
    print()

    if unread:
        print(f"  ! {len(unread)} dosya okunamadi: "
              f"{', '.join(r['file'] for r in unread)}")
    if weak:
        print(f"  ! {len(weak)} dosya {args.min_variants} varyantin altinda, "
              f"eleyebilirsin: {', '.join(r['file'] for r in weak)}")
    if len(readable) > 5:
        print(f"  ! {len(readable)} dosya fazla — 3-5 yeter, "
              "fazlasi secim mantigini sisirir.")
    if not unread and not weak and readable:
        print("  KABUL KRITERI GECTI.")
    return 1 if (unread or weak) else 0


if __name__ == "__main__":
    raise SystemExit(main())
