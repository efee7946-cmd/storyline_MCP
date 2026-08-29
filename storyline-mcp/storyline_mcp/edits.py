"""Text editing.

Round-tripping the embedded <Document> through ElementTree would silently drop
its unused xmlns:xsi / xmlns:xsd declarations and re-order attributes. So the
Span is located with ElementTree but rewritten by string surgery on the raw
document: only the Text attribute of the targeted Span changes, every other
byte -- styling, namespaces, whitespace -- survives untouched.

The flat <plain> mirror is then recomputed from the edited document, because
Storyline keeps the two copies in sync and a stale <plain> shows up in search,
the outline and translation exports.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import PurePosixPath
from xml.sax.saxutils import escape

from .model import _iter_text_shapes
from .package import StoryPackage, StoryError

SPAN_TAG_RE = re.compile(r"<Span\b[^>]*>")
TEXT_ATTR_RE = re.compile(r'(\bText=")((?:[^"\\]|\\.)*)(")')


@dataclass
class Edit:
    addr: str
    new_text: str


def parse_addr(addr: str) -> tuple[str, str, int, int]:
    parts = addr.split("|")
    if len(parts) != 4:
        raise StoryError(
            f"Gecersiz adres: {addr!r}. Beklenen bicim: slide.xml|<sekilGUID>|<blok>|<span>"
        )
    slide, shape_guid, block, span = parts
    try:
        return slide, shape_guid, int(block), int(span)
    except ValueError:
        raise StoryError(f"Adreste blok/span sayi olmali: {addr!r}") from None


def _escape_attr(value: str) -> str:
    return escape(value, {'"': "&quot;", "\n": "&#10;", "\t": "&#9;"})


def _global_span_index(doc: ET.Element, block: int, span: int) -> int:
    """Document-order index of the (block, span) pair among all <Span> tags."""
    content = doc.find("Content")
    if content is None:
        raise StoryError("Gomulu belgede <Content> yok.")
    blocks = content.findall("Block")
    if block >= len(blocks):
        raise StoryError(f"Blok {block} yok (toplam {len(blocks)}).")
    seen = 0
    for b, blk in enumerate(blocks):
        spans = blk.findall("Span")
        if b == block:
            if span >= len(spans):
                raise StoryError(f"Blok {block} icinde span {span} yok (toplam {len(spans)}).")
            return seen + span
        seen += len(spans)
    raise StoryError("Span bulunamadi.")


def _rewrite_span(raw: str, global_index: int, new_text: str) -> str:
    """Replace the Text attribute of the Nth <Span> in the raw document."""
    matches = list(SPAN_TAG_RE.finditer(raw))
    if global_index >= len(matches):
        raise StoryError(f"Ham belgede span {global_index} yok (toplam {len(matches)}).")
    tag = matches[global_index]
    tag_text = tag.group(0)
    if not TEXT_ATTR_RE.search(tag_text):
        raise StoryError("Hedef <Span> etiketinde Text niteligi yok.")
    new_tag = TEXT_ATTR_RE.sub(
        lambda m: m.group(1) + _escape_attr(new_text) + m.group(3), tag_text, count=1
    )
    return raw[: tag.start()] + new_tag + raw[tag.end() :]


BLOCK_RE = re.compile(r"<Block\b[^>]*?(?:/>|>.*?</Block>)", re.S)


def _drop_trailing_empty_blocks(raw: str) -> str:
    """Sondaki BOS Block'lari dusur -- metnin sonuna satir sonu birakiyorlar.

    Bir <Block> bir PARAGRAFTIR ve _doc_text / _rebuild_plain Block'lari "
"
    ile birlestirir. Dolayisiyla sonunda bos bir Block duran belge, metni
    "Etiket
" diye geri verir ve <plain> aynasina da oyle yazilir.

    Bu iki yoldan olusuyor ve ikisi de olculdu (2026-08-28):
      1. Tohum zaten bos bir Block tasiyor. Gomulu cok-secenekli soru
         tohumunda vardi: girdi TAMAMEN temizken bile her 5 secenekli soruda
         yalnizca indis 1 kirleniyordu.
      2. Sablonun ikinci Block'u DOLU geliyor ve set_shape_text onu bosaltiyor.
         Span'ler bosaltilir ama silinmez (asagidaki dokumana bak); geriye
         icerigi bos bir Block kalir ve sonuc birincisiyle aynidir.

    Ikincisi tohumu temizlemekle KAPANMAZ, o yuzden duzeltme burada duruyor:
    metni yazan tek yer burasi.

    Hepsi silinmez. Bilerek bos birakilmis bir metin kutusu (set_background
    bos metinle cagirir) en az bir Block'la kalir; aksi halde Storyline'in
    bekledigi belge iskeleti bozulur.
    """
    bloklar = list(BLOCK_RE.finditer(raw))
    if len(bloklar) < 2:
        return raw

    def bos(m):
        return not "".join(
            t.group(2) for t in TEXT_ATTR_RE.finditer(m.group(0))
        ).strip()

    kes = len(bloklar)
    while kes > 1 and bos(bloklar[kes - 1]):
        kes -= 1
    if kes == len(bloklar):
        return raw
    return raw[: bloklar[kes].start()] + raw[bloklar[-1].end():]


def _rebuild_plain(raw_doc: str) -> str:
    doc = ET.fromstring(raw_doc)
    content = doc.find("Content")
    if content is None:
        return ""
    return "\n".join(
        "".join(span.get("Text", "") for span in block.findall("Span"))
        for block in content.findall("Block")
    )


def set_shape_text(root: ET.Element, shape_guid: str, text: str) -> bool:
    """Replace a shape's entire text, keeping the first run's styling.

    Used when filling in a freshly cloned slide, where the template's wording
    is thrown away wholesale. The first Span absorbs the new text and inherits
    its own Style; any further Spans are blanked rather than deleted, so the
    document keeps the shape Storyline expects.

    Every document under the shape is rewritten, not just the first one found,
    and so is every plain-text mirror that holds anything. A shape with states
    keeps its label per state, and stopping at the first document wrote it
    into Normal alone: donor-sourced buttons read "Basla" until the pointer
    touched them and then said "BUTTON", the donor's own placeholder, in every
    generated course. A label is a property of the shape, not of the state
    that happens to be showing.

    The mirrors have to be written directly because most state bodies carry no
    document at all -- measured on a five-state donor, one body held the rich
    text and the other four held only <plain>, which is what Storyline drew.
    Rewriting documents alone left every one of those four saying "BUTTON".

    A mirror that is already empty stays empty: a state that deliberately
    shows no text, like Accordion's Invisible, means it.
    """
    shape = None
    for el in root.iter():
        if el.get("g") == shape_guid:
            shape = el
            break
    if shape is None:
        return False

    parents = {c: p for p in shape.iter() for c in p}
    written = False
    for text_el in shape.iter("text"):
        raw = (text_el.text or "").strip()
        if not raw.startswith("<Document"):
            continue
        doc = ET.fromstring(raw)
        spans = list(doc.iter("Span"))
        if not spans:
            continue
        updated = _rewrite_span(raw, 0, text)
        for index in range(1, len(spans)):
            updated = _rewrite_span(updated, index, "")
        updated = _drop_trailing_empty_blocks(updated)
        text_el.text = updated
        owner = parents.get(text_el, shape)
        plain = owner.find("plain")
        if plain is not None:
            plain.text = _rebuild_plain(updated)
        written = True

    for plain in shape.iter("plain"):
        if (plain.text or "").strip():
            plain.text = text
            written = True
    return written


def apply_text_edits(pkg: StoryPackage, edits: list[Edit]) -> dict:
    """Apply edits addressed as slide.xml|shapeGUID|block|span."""
    by_slide: dict[str, list[tuple[str, int, int, str]]] = {}
    for edit in edits:
        slide, shape_guid, block, span = parse_addr(edit.addr)
        part = pkg.slide_part_for(slide)
        by_slide.setdefault(part, []).append((shape_guid, block, span, edit.new_text))

    applied: list[dict] = []
    for part, slide_edits in by_slide.items():
        root = pkg.parse(part)
        shapes = {
            shape.get("g", ""): (shape, text_el)
            for shape, text_el, _doc, _state in _iter_text_shapes(root)
        }
        touched: set[str] = set()
        for shape_guid, block, span, new_text in slide_edits:
            if shape_guid not in shapes:
                raise StoryError(
                    f"{PurePosixPath(part).name} icinde {shape_guid} GUID'li metin sekli yok."
                )
            shape, text_el = shapes[shape_guid]
            # Re-read the raw document each time: an earlier edit in this loop
            # may already have rewritten this same shape.
            raw = (text_el.text or "").strip()
            doc = ET.fromstring(raw)
            index = _global_span_index(doc, block, span)
            old_text = list(doc.iter("Span"))[index].get("Text", "")
            text_el.text = _rewrite_span(raw, index, new_text)
            touched.add(shape_guid)
            applied.append(
                {
                    "addr": f"{PurePosixPath(part).name}|{shape_guid}|{block}|{span}",
                    "old": old_text,
                    "new": new_text,
                }
            )

        for shape_guid in touched:
            shape, text_el = shapes[shape_guid]
            plain = shape.find("plain")
            if plain is not None:
                plain.text = _rebuild_plain(text_el.text or "")

        pkg.replace_xml(part, root)

    return {"applied": applied, "slides_changed": sorted(by_slide)}
