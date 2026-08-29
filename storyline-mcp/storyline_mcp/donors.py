"""The donor pool: button anatomy borrowed from real courses.

An empty project has no shapes to clone, so it falls back to the bundled seeds
-- one <btn>, captured once. Every course built from a blank therefore wore the
same button, and no amount of layout work in the composer changed that: the
furniture was fixed before composition began.

This module widens the parts bin. Real projects downloaded into donors/ are
read for shapes worth cloning, and one of them is chosen per course.

Two findings shape the design.

*A button is a role, not a tag.* Measured across the pool: 226 shapes carry
state lists and only 10 of them are <btn>. Designers draw a rect, an oval, a
chevron, even a picture, and give it states; <btn> is what Storyline's own
button tool emits, which is precisely the uniform look the pool exists to
escape. Searching by tag would find the pool nearly empty, and would find the
wrong thing when it did hit.

*A kit ships unwired shapes.* ButtonKit's 26 shapes have states and no
triggers at all, which is the better donor -- a wired one arrives pointing at
someone else's navigation -- but it cannot be clicked until the wiring is
grafted on. So the trigger comes from the bundled seed and the look comes from
the donor.

The choice is made once per course and held. Picking per slide would scatter a
deck across four button languages, which reads worse than the single boring
one it replaced. Consistency inside a course, difference between courses.
"""

from __future__ import annotations

import hashlib
import os
import re
import warnings
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path

from .clone import _defined_guids, _remap_guids, new_guid
from .model import slide_index
from .package import StoryPackage, StoryError

SEED_DIR = Path(__file__).resolve().parent / "seeds"
DEFAULT_POOL = Path(__file__).resolve().parents[1] / "donors"

# Roles the pool can serve. Everything else keeps the old behaviour: a
# background rect wants Storyline's plain rectangle, not an accordion header
# that happens to be one.
ROLES = ("btn",)

_cache: dict[str, list["Candidate"]] = {}
_cache_key: tuple | None = None
_skipped: list[dict] = []
_rejected: list[dict] = []

_GUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_IDENTITY_RE = re.compile(
    r'\s(?:g|verG|stateG|defG|corG|copiedG|id|zOrder|name)="[^"]*"')


def pool_dir() -> Path:
    return Path(os.environ.get("STORYLINE_DONORS") or DEFAULT_POOL)


class Candidate:
    """One clonable shape, with where it came from."""

    __slots__ = ("xml", "tag", "states", "clickable", "origin", "sig")

    def __init__(self, xml: str, tag: str, states: tuple[str, ...],
                 clickable: bool, origin: str, sig: str = ""):
        self.xml = xml
        self.tag = tag
        self.states = states
        self.clickable = clickable
        self.origin = origin
        self.sig = sig

    def element(self) -> ET.Element:
        return ET.fromstring(self.xml)

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return f"<Candidate {self.tag} {len(self.states)} durum from {self.origin}>"


# ------------------------------------------------------------------ harvesting


CLICK_EVENTS = frozenset({"OnClick", "OnRelease", "OnPress"})


SKIP_SUBTREES = ("stateLst", "trigLst")


def _walk_shapes(node: ET.Element):
    """Every element that could be a slide shape.

    Two subtrees are stepped over. A state's body is a complete shape of its
    own, so a five-state button contains five further shape elements, and
    descending would offer a button's own Hover state as a separate donor. A
    trigger's body contains a <shape> too -- the matcher naming which shape the
    trigger acts on, carrying a stateLst of its own and no geometry at all. It
    looked exactly like a five-state button to an earlier version of this walk.
    """
    for child in node:
        if child.tag in SKIP_SUBTREES:
            continue
        yield child
        yield from _walk_shapes(child)


def _clickable(shape: ET.Element) -> bool:
    for trig_list in shape.iter("trigLst"):
        for trig in trig_list:
            data = trig.find("data")
            if data is not None and data.get("event") in CLICK_EVENTS:
                return True
    return False


NULL_GUID = "00000000-0000-0000-0000-000000000000"


def _needs_media(shape: ET.Element) -> bool:
    """Does this shape lean on a file that lives in the donor package?

    A picture button carries assetG pointing at media in its own project. The
    XML clones perfectly and arrives in the target with the reference dangling,
    which is a button showing nothing. Bringing the media across is a different
    job from borrowing anatomy, so these are left in the donor.
    """
    for el in shape.iter():
        asset = el.get("assetG")
        if asset and asset != NULL_GUID:
            return True
    return False


def _is_button_like(shape: ET.Element) -> bool:
    # A real slide shape has an identity and a position. The elements that fail
    # this are Storyline's internal descriptors, not anything drawable.
    if not shape.get("g") or shape.find("loc") is None:
        return False
    states = shape.find("stateLst")
    if states is None or len(states) < 2:
        # One state is a shape someone left a state list on, not a button.
        return False
    # An unnamed state set is not a design; it is bookkeeping.
    if any(not (s.get("name") or "").strip() for s in states):
        return False
    # A drop target is a question's furniture, not a navigation control; its
    # states are scoring outcomes and mean nothing on a content slide.
    names = {(s.get("name") or "").casefold() for s in states}
    if names & {"dropped", "drop correct", "drop incorrect"}:
        return False
    return not _needs_media(shape)


def _harvest_file(path: Path, skipped: list[dict]) -> list[Candidate]:
    """Candidates from one donor, and a note when there are none to be had.

    A silent skip here is how the pool went from thirteen candidates to six
    without saying so: a donor left open in Storyline is locked, was passed
    over, and every course built meanwhile drew from a quietly smaller pool.
    The reason travels with the result so callers can shout about it.
    """
    out: list[Candidate] = []
    # One reading, not two. This used to ask lock_state first and then open the
    # package anyway -- and the two disagreed in the one case that mattered,
    # lock_state answering "free" for a file StoryPackage could not read. Two
    # paths measuring one fact is how they drift; the one that actually has to
    # succeed is the authority, and its error is the reason.
    try:
        pkg = StoryPackage(path)
        index = slide_index(pkg)
    except Exception as exc:
        skipped.append({"file": path.name, "why": f"okunamadi: {str(exc)[:70]}"})
        return out

    for part in sorted(index):
        try:
            root = pkg.parse(part)
        except Exception:
            continue
        for shape in _walk_shapes(root):
            if not _is_button_like(shape):
                continue
            states = tuple((s.get("name") or "?") for s in shape.find("stateLst"))
            out.append(Candidate(
                xml=ET.tostring(shape, encoding="unicode"),
                tag=shape.tag,
                states=states,
                clickable=_clickable(shape),
                origin=f"{path.name}/{part.rsplit('/', 1)[1]}",
            ))
    return out


def _signature(shape_xml: str) -> str:
    """What makes one donor a different button from another.

    Exactly the anatomy: element, silhouette, state set. Colour and corner
    radius are left out on purpose -- ButtonKit holds four ovals differing only
    in fill, and keeping them apart would take four of the pool's slots and
    make an oval four times likelier than the chevron beside it. That is the
    aesthetic climbing back in through the selection weights.

    Deduplicating on precisely the anatomy also means every slot in the pool is
    a visibly different button, which is what makes two courses drawing two
    slots look genuinely unalike.
    """
    root = ET.fromstring(shape_xml)
    states = tuple((s.get("name") or "?") for s in (root.find("stateLst") or []))
    geo = root.find("prstGeom")
    child = next(iter(geo), None) if geo is not None else None
    silhouette = child.tag if child is not None else root.tag
    return f"{root.tag}|{silhouette}|{','.join(states)}"


def catalogue(*, refresh: bool = False) -> list[Candidate]:
    """Every button-like shape the pool offers, in a stable order."""
    global _cache, _cache_key

    folder = pool_dir()
    files = sorted(folder.glob("*.story")) if folder.is_dir() else []
    key = tuple((f.name, f.stat().st_mtime_ns, f.stat().st_size) for f in files)
    if not refresh and _cache_key == key and "btn" in _cache:
        return _cache["btn"]

    found: list[Candidate] = []
    seen: set[str] = set()
    skipped: list[dict] = []
    rejected: list[dict] = []
    for path in files:
        for candidate in _harvest_file(path, skipped):
            candidate.sig = _signature(candidate.xml)
            if candidate.sig in seen:
                continue
            seen.add(candidate.sig)
            # Rehearsed, not filtered by a list of shape names. A rule written
            # from today's pool goes stale the moment a donor is added; a
            # rehearsal asks the only question that matters and keeps asking.
            ok, why = rehearse(candidate)
            if not ok:
                rejected.append({"tag": candidate.tag, "origin": candidate.origin,
                                 "why": why})
                continue
            found.append(candidate)

    for note in skipped:
        warnings.warn(
            f"Donor havuzu eksik: {note['file']} atlandi — {note['why']}. "
            "Uretilen kurs bu donoru hic gormeyecek.",
            RuntimeWarning, stacklevel=2)

    # Sorted so the pool is an ordered list rather than a filesystem accident:
    # the same donors must yield the same choice on any machine.
    found.sort(key=lambda c: (c.origin, c.tag, c.states))
    _cache = {"btn": found}
    _cache_key = key
    _skipped.clear()
    _skipped.extend(skipped)
    _rejected.clear()
    _rejected.extend(rejected)
    return found


# ------------------------------------------------------------------- choosing


def choose(identity: str, role: str = "btn") -> Candidate | None:
    """The donor this course uses for this role -- the same one every time.

    Keyed on a course identity rather than drawn at random, so a rebuild of the
    same course is identical while the next course differs. sha256 rather than
    hash(): the built-in is salted per process and would pick a different
    button every time the server restarted, mid-course.
    """
    pool = catalogue()
    if not pool:
        return None
    digest = hashlib.sha256(f"{identity}|{role}".encode("utf-8")).digest()
    return pool[int.from_bytes(digest[:8], "big") % len(pool)]


# -------------------------------------------------------------------- wiring


def _seed_trigger() -> ET.Element | None:
    """A working OnClick trigger, taken from the bundled button."""
    seed_file = SEED_DIR / "btn.xml"
    if not seed_file.is_file():
        return None
    seed = ET.fromstring(seed_file.read_text(encoding="utf-8"))
    trig_list = seed.find("trigLst")
    for trig in (trig_list if trig_list is not None else []):
        if trig.find("data") is not None:
            return deepcopy(trig)
    return None


def ensure_clickable(shape: ET.Element) -> bool:
    """Give a kit shape the wiring a button needs, if it has none.

    Grafted onto the shape's own trigLst, never one belonging to a state: a
    trigger inside a state body fires only while that state shows.
    """
    trig_list = shape.find("trigLst")
    if trig_list is not None and any(t.find("data") is not None for t in trig_list):
        return False

    trigger = _seed_trigger()
    if trigger is None:
        return False
    raw = ET.tostring(trigger, encoding="unicode")
    trigger = ET.fromstring(
        _remap_guids(raw, {old: new_guid() for old in _defined_guids(raw)}))
    # copiedG records which shape the trigger belongs to; left pointing at the
    # seed it would name a shape that does not exist in this project.
    trigger.set("copiedG", shape.get("g", ""))

    if trig_list is None:
        trig_list = ET.Element("trigLst")
        # Order matters to Storyline: trigLst sits where the seed keeps it,
        # after childLst rather than appended at the end.
        children = list(shape)
        at = next((i for i, c in enumerate(children) if c.tag == "childLst"), -1)
        shape.insert(at + 1 if at >= 0 else len(children), trig_list)
    trig_list.append(trigger)
    return True


def distinct_identities(names: list[str], role: str = "btn") -> dict[str, str]:
    """Salted identities that draw a different donor for each name.

    choose() is a pure function of one course's identity, which is what keeps
    it stateless and reproducible -- and also means two courses can land on the
    same donor by coincidence. Measured over 2000 groups of five against a
    13-slot pool: all five differ only 49% of the time, matching the birthday
    arithmetic. That is fine for courses built one at a time and not fine for a
    batch meant to demonstrate variety.

    So a batch caller resolves its identities here first and passes the results
    through as the identity. The salt only perturbs the draw; each name still
    maps to one fixed donor, so the same batch rebuilt is the same batch.
    """
    pool = catalogue()
    used: set[str] = set()
    out: dict[str, str] = {}
    for name in names:
        chosen = name
        for salt in range(500):
            key = name if salt == 0 else f"{name}#{salt}"
            picked = choose(key, role)
            if picked is None:
                break
            if picked.sig not in used:
                used.add(picked.sig)
                chosen = key
                break
        else:
            chosen = name  # pool exhausted; repeats are unavoidable
        out[name] = chosen
        if len(used) >= len(pool):
            used.clear()  # more courses than donors: start the cycle again
    return out


def _harvest_all_for_probe() -> list["Candidate"]:
    """Every harvested candidate before rehearsal, for measuring the filter."""
    out: list[Candidate] = []
    seen: set[str] = set()
    folder = pool_dir()
    for path in sorted(folder.glob("*.story")) if folder.is_dir() else []:
        for candidate in _harvest_file(path, []):
            candidate.sig = _signature(candidate.xml)
            if candidate.sig in seen:
                continue
            seen.add(candidate.sig)
            out.append(candidate)
    return out


# The label the rehearsal writes, and therefore the contract a donor has to
# meet. It is a real knob: a longer sample rejects more donors. Measured
# against this pool, "Devam Et" keeps the tab-style buttons and "Ornek Etiket"
# does not, so it is set to the length the composer actually emits for a
# call to action rather than to a number that happened to look tidy.
SAMPLE_LABEL = "Devam Et"


def rehearse(candidate: "Candidate", *, label: str = SAMPLE_LABEL,
             box: tuple[float, float] = (144.0, 51.0)) -> tuple[bool, str]:
    """Put a label on it and read it back. A donor that fails is not a button.

    The same move harvest.py makes on a seed before keeping it, and the one
    available_question_shapes does not make on a template -- offering
    something that cannot be filled is one bug wearing three hats.

    Three ways to fail, each measured rather than guessed:

      *The label does not stick.* A shape carrying states is not necessarily a
      control: an accordion's arrow and a dial's vector have state lists and
      no text run to write into. They accept the call and show nothing.

      *The label does not fit.* Writing succeeds and the word still overflows.
      Measured against the shape's own text inset rather than the outer box,
      because the box is the same for every donor and would tell them apart
      from nothing: Tabcordion's tab indents its text 50 units from the left
      to clear an icon, leaving 81 of a 144-wide button for the word, where
      the kit's shapes leave 124.

      *The states are identical.* A thing whose Hover is byte-for-byte its
      Normal has a state list and no state behaviour, which is a decoration
      someone left a state list on.
    """
    from . import model, shapes  # circular at import time, fine at call time
    from .authoring import _apply_text

    element = candidate.element()
    shape = shapes.clone_shape(element, name="prova", keep_triggers=False)
    shapes.set_shape_slide_size(shape, 720, 540)
    shapes.set_loc(shape, 0, 0, box[0], box[1])

    holder = ET.Element("sld")
    ET.SubElement(holder, "shapeLst").append(shape)

    # Asked before writing, because the answers mean different things. A shape
    # with no text run cannot hold a label and never could -- that is the
    # anatomy of a decoration, and a settled verdict. A shape that has runs and
    # still reads back empty is a writer that failed, which is a bug to chase,
    # not a donor to discard. Collapsing the two into "the label did not stick"
    # is the same mistake that let a narrow regex report "no style" for every
    # style it could not see.
    runs = sum((t.text or "").count("<Span") for t in shape.iter("text"))
    if runs == 0:
        return False, "metin kosusu yok — etiket tasiyamaz, kontrol degil"

    try:
        _apply_text(holder, shape, label, size=15, align="c")
    except Exception as exc:
        return False, f"etiket yazilamadi: {str(exc)[:40]}"

    got = (model.shape_text(holder, shape.get("g", "")) or "").strip()
    if got != label:
        return False, (f"{runs} metin kosusu var ama etiket geri okunmadi "
                       f"({got[:18]!r}) — yazma yolunda hata olabilir")

    if _identical_states(shape):
        return False, "durumlari birbirinin ayni — kontrol degil"

    left, _top, right, _bottom = shapes.text_inset(shape)
    usable_w = box[0] - left - right
    if usable_w < 40:
        return False, f"metne kalan genislik {usable_w:.0f} — sozcuk sigmaz"

    # The box grows to its label now, so "does it overflow" is no longer the
    # question -- it cannot. What is left is how far it has to grow: a shape
    # that reserves most of its width for an icon needs a much taller box for
    # the same word, and a row of those reads as a stack of billboards.
    # TUTARLI UZAY: donor provasi tek bir 720 deck'i varsayar ve sahne de
    # 720'dir, yani her iki carpan da 1.0. Acikca yaziliyor cunku ortuk
    # birakilan uzay bu oturumda uc tur boyunca yanlis olceklendi (K17).
    needed = shapes.height_for_label(shape, label, 15, box[0],
                                     shapes.Space(720.0, 540.0, 720.0, 540.0))
    if needed > box[1] * shapes.GROWTH_LIMIT:
        return False, (f"etiket icin kutuyu {needed / box[1]:.1f} katina "
                       f"cikarmak gerekir — orantisiz")

    return True, "tamam"


def _identical_states(shape: ET.Element) -> bool:
    lst = shape.find("stateLst")
    bodies = []
    for state in (lst if lst is not None else []):
        inner = state.find("shapeLst")
        if inner is not None and len(inner):
            raw = ET.tostring(inner[0], encoding="unicode")
            bodies.append(_GUID_RE.sub("G", _IDENTITY_RE.sub("", raw)))
    return len(bodies) > 1 and len(set(bodies)) == 1


def summary() -> dict:
    """What the pool holds -- for diagnostics and the audit tool."""
    pool = catalogue()
    folder = pool_dir()
    on_disk = sorted(p.name for p in folder.glob("*.story")) if folder.is_dir() else []
    return {
        "folder": str(folder),
        "files_on_disk": on_disk,
        "files_used": sorted({c.origin.split("/")[0] for c in pool}),
        "skipped": list(_skipped),
        "rejected": list(_rejected),
        "candidates": len(pool),
        "tags": sorted({c.tag for c in pool}),
        "clickable": sum(1 for c in pool if c.clickable),
    }
