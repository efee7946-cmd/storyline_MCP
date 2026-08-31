"""Read-only model over a .story package.

Storyline keeps every visible string twice: a flat <plain> copy on the shape,
and the authoritative rich-text copy inside <text>, which holds an *embedded*
XML document:

    <shape g="..."><plain>Merhaba</plain>
      <text><Document><Content><Block>
        <Span Text="Merhaba"><Style FontFamily="Segoe UI" .../></Span>
      </Block></Content></Document></text></shape>

A Span is the atomic addressable unit here: it is exactly one formatting run,
so rewriting Span/@Text changes wording without disturbing any styling.

Text is not always a direct child of the shape that owns it. A quiz answer,
for instance, nests one level deeper -- through the shape's state variants:

    oval[g=shpG] > stateLst > state > shapeLst > textBox > text

so anything that resolves "the text of shape X" has to search descendants,
not just children.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import PurePosixPath

from .package import STORY_PART, STORY_RELS, StoryPackage

# Shapes whose text the player generates at runtime, not the author.
GENERATED_TEXT_SHAPES = {"rsltBtn"}


@dataclass
class SlideRef:
    part: str
    basename: str
    guid: str
    name: str
    layout_type: str
    scene_name: str
    scene_guid: str
    position: int  # 1-based position within its scene


@dataclass
class TextRun:
    addr: str
    slide: str
    slide_name: str
    scene: str
    shape_guid: str
    shape_type: str
    shape_name: str
    state_guid: str  # non-empty when the text lives in a shape state variant
    block: int
    span: int
    text: str


# --------------------------------------------------------------------- scenes


def _rel_map(pkg: StoryPackage) -> dict[str, str]:
    """Relationship Id -> part path, from story.xml.rels."""
    root = pkg.parse(STORY_RELS)
    out: dict[str, str] = {}
    for rel in root:
        rid, target = rel.get("Id"), rel.get("Target")
        if rid and target:
            out[rid] = str(PurePosixPath(target.lstrip("/")))
    return out


def _derive_title(root: ET.Element) -> str:
    """Slides may carry no name; fall back to their most title-like text."""
    texts = [
        t
        for shape, _text_el, doc, _state in _iter_text_shapes(root)
        if (t := _doc_text(doc).strip())
    ]
    if not texts:
        return "(isimsiz)"
    return max(texts, key=len)[:60]


def slide_index(pkg: StoryPackage) -> dict[str, SlideRef]:
    """Every slide, keyed by part path, in scene order."""
    rels = _rel_map(pkg)
    story = pkg.parse(STORY_PART)
    index: dict[str, SlideRef] = {}

    def make(part: str, scene_name: str, scene_guid: str, pos: int) -> SlideRef:
        root = pkg.parse(part)
        return SlideRef(
            part=part,
            basename=PurePosixPath(part).name,
            guid=root.get("g", ""),
            name=root.get("name") or _derive_title(root),
            layout_type=root.get("layoutType", ""),
            scene_name=scene_name,
            scene_guid=scene_guid,
            position=pos,
        )

    scene_list = story.find("sceneLst")
    for scene in list(scene_list) if scene_list is not None else []:
        id_list = scene.find("sldIdLst")
        for pos, sld_id in enumerate(list(id_list) if id_list is not None else [], 1):
            part = rels.get((sld_id.text or "").strip())
            if part and part in pkg._parts:
                index[part] = make(part, scene.get("name", ""), scene.get("g", ""), pos)

    # Slides no scene references still deserve to be visible.
    for part in pkg.slide_parts:
        if part not in index:
            index[part] = make(part, "(sahnesiz)", "", 0)
    return index


def scenes(pkg: StoryPackage) -> list[dict]:
    idx = slide_index(pkg)
    grouped: dict[str, dict] = {}
    for ref in idx.values():
        bucket = grouped.setdefault(
            ref.scene_name, {"scene": ref.scene_name, "guid": ref.scene_guid, "slides": []}
        )
        bucket["slides"].append(
            {
                "slide": ref.basename,
                "name": ref.name,
                "layout": ref.layout_type,
                "position": ref.position,
            }
        )
    for bucket in grouped.values():
        bucket["slides"].sort(key=lambda s: s["position"])
    return list(grouped.values())


# ----------------------------------------------------------------- text runs


def _parent_map(root: ET.Element) -> dict[ET.Element, ET.Element]:
    return {child: parent for parent in root.iter() for child in parent}


def _iter_text_shapes(root: ET.Element):
    """Yield (shape, text_element, embedded Document, owning state guid)."""
    parents = _parent_map(root)
    for text_el in root.iter("text"):
        raw = (text_el.text or "").strip()
        if not raw.startswith("<Document"):
            continue
        shape = parents.get(text_el)
        if shape is None or shape.tag in GENERATED_TEXT_SHAPES:
            continue
        try:
            doc = ET.fromstring(raw)
        except ET.ParseError:
            continue
        state_guid = ""
        node = parents.get(shape)
        while node is not None:
            if node.tag == "state":
                state_guid = node.get("g", "")
                break
            node = parents.get(node)
        yield shape, text_el, doc, state_guid


def _doc_text(doc: ET.Element) -> str:
    content = doc.find("Content")
    if content is None:
        return ""
    return "\n".join(
        "".join(span.get("Text", "") for span in block.findall("Span"))
        for block in content.findall("Block")
    )


def text_runs(pkg: StoryPackage, slide: str | None = None) -> list[TextRun]:
    idx = slide_index(pkg)
    parts = [pkg.slide_part_for(slide)] if slide else list(idx)
    runs: list[TextRun] = []
    for part in parts:
        ref = idx.get(part)
        root = pkg.parse(part)
        base = PurePosixPath(part).name
        for shape, _text_el, doc, state_guid in _iter_text_shapes(root):
            shape_guid = shape.get("g", "")
            content = doc.find("Content")
            if content is None:
                continue
            for b, block in enumerate(content.findall("Block")):
                for s, span in enumerate(block.findall("Span")):
                    value = span.get("Text")
                    if value is None or not value.strip():
                        continue
                    runs.append(
                        TextRun(
                            addr=f"{base}|{shape_guid}|{b}|{s}",
                            slide=base,
                            slide_name=ref.name if ref else "",
                            scene=ref.scene_name if ref else "",
                            shape_guid=shape_guid,
                            shape_type=shape.tag,
                            shape_name=shape.get("name", ""),
                            state_guid=state_guid,
                            block=b,
                            span=s,
                            text=value,
                        )
                    )
    return runs


def _find_by_guid(root: ET.Element, guid: str) -> ET.Element | None:
    if not guid:
        return None
    for el in root.iter():
        if el.get("g") == guid:
            return el
    return None


def shape_text(root: ET.Element, shape_guid: str) -> str:
    """Visible text of a shape, searching its descendants (states included)."""
    shape = _find_by_guid(root, shape_guid)
    if shape is None:
        return ""
    for text_el in shape.iter("text"):
        raw = (text_el.text or "").strip()
        if not raw.startswith("<Document"):
            continue
        try:
            text = _doc_text(ET.fromstring(raw))
        except ET.ParseError:
            continue
        if text.strip():
            return text
    return ""


# ----------------------------------------------------------------- variables


def variables(pkg: StoryPackage) -> list[dict]:
    story = pkg.parse(STORY_PART)
    var_list = story.find("varLst")
    return [
        {
            "name": var.get("name", ""),
            "guid": var.get("g", ""),
            "type": var.get("type", ""),
            "data_type": var.get("dataType", ""),
            "default": var.get("val", ""),
        }
        for var in (list(var_list) if var_list is not None else [])
    ]


# ------------------------------------------------------------------ triggers


def triggers(pkg: StoryPackage, slide: str | None = None) -> list[dict]:
    idx = slide_index(pkg)
    var_by_guid = {v["guid"]: v["name"] for v in variables(pkg)}
    slide_by_guid = {r.guid: r for r in idx.values()}
    parts = [pkg.slide_part_for(slide)] if slide else list(idx)

    out: list[dict] = []
    for part in parts:
        ref = idx.get(part)
        root = pkg.parse(part)
        for trig_list in root.iter("trigLst"):
            for trig in trig_list:
                data = trig.find("data")
                if data is None:
                    continue
                entry = {
                    "slide": PurePosixPath(part).name,
                    "slide_name": ref.name if ref else "",
                    "scene": ref.scene_name if ref else "",
                    "kind": trig.tag,
                    "enabled": data.get("enabled", "true") == "true",
                    "event": data.get("event", ""),
                    "action": data.get("action", ""),
                }
                other = data.find("other")
                if other is not None:
                    var_guid = other.get("varG", "")
                    if var_guid in var_by_guid:
                        entry["variable"] = var_by_guid[var_guid]
                    if other.get("js"):
                        entry["javascript"] = other.get("js")
                    # adjustVar'in yazdigi deger. Denetim tarafi bunu
                    # goremeden "bozuk sayi yok" derdi -- girdisi olmayan
                    # kontrol gectigini soylemez (K1b).
                    if data.get("action") == "adjustVar":
                        entry["operation"] = other.get("op", "")
                        if other.get("useVar") == "true":
                            entry["value_from_variable"] = True
                        else:
                            entry["value"] = other.get("dblVal", "")
                    if other.get("open"):
                        entry["url"] = other.get("open")
                for tag in ("slide", "scene"):
                    node = data.find(tag)
                    if node is None:
                        continue
                    for key in ("target", "sldG", "g", "sceneG"):
                        guid = node.get(key)
                        if guid and guid != "00000000-0000-0000-0000-000000000000":
                            target = slide_by_guid.get(guid)
                            entry["target"] = target.name if target else guid
                            break
                out.append(entry)
    return out


# ---------------------------------------------------------------------- quiz

# ETIKET ADLARI TAHMIN EDILMEZ, DOSYADAN OKUNUR.
#
# Bu liste bir donem `textEntryIntr` ve `numericEntryIntr` yaziyordu ve
# Storyline'in metin girisi sorusunun GERCEK etiketi `freeTextEntryIntr`.
# Yani okuyucu o tipi HIC gormuyordu, ve sessizce: `list_quiz` metin girisi
# tasiyan bir dosyada "soru yok" diyor, `_find_interaction` None donuyor,
# ve None donen yerde yazma adimi atlaniyor -- her adim basarili raporlayip
# hicbir sey yazmiyor.
#
# Olculdu 2026-08-30 ve tam olarak bu gerceklesti: puanli metin girisi
# uretildi, "kabul edilen cevap yazildi" gibi dondu, slaytta tohumun kendi
# cevabi (<text>sabun</text>) duruyordu.
#
# ASAGIDAKI ISIMLER 294 .story DOSYASINDA TARANDI. Bulunanlar:
#     freePickOneIntr    476    freeTextEntryIntr    5
#     freePickManyIntr    58    freeHotSpotIntr      5
#     dragDropIntr        43    rsltsIntr           46
# `matchDropDownIntr` ve `seqDropDownIntr` SIFIR kez gecti; adlari
# dogrulanmadi, tahmin olarak duruyorlar ve bu yuzden burada isaretliler.
# Biri elde bir ornekle dogrulanana kadar, o tiplerden birinin sessizce
# gorunmez olmasi HALA mumkun.
INTERACTION_TAGS = (
    "freePickOneIntr",
    "freePickManyIntr",
    "dragDropIntr",
    "freeTextEntryIntr",
    "freeHotSpotIntr",
    # Dogrulanmadi -- korpusta hic ornegi yok (yukariya bakin).
    "matchDropDownIntr",
    "seqDropDownIntr",
    "numericEntryIntr",
)


def quiz(pkg: StoryPackage) -> list[dict]:
    idx = slide_index(pkg)
    out: list[dict] = []
    for part, ref in idx.items():
        root = pkg.parse(part)
        for tag in INTERACTION_TAGS:
            for intr in root.iter(tag):
                props = intr.find("intrProps")
                choices_el = intr.find("choices")
                choices = list(choices_el) if choices_el is not None else []
                out.append(
                    {
                        "slide": ref.basename,
                        "slide_name": ref.name,
                        "scene": ref.scene_name,
                        "type": tag,
                        "correct_points": props.get("corPts") if props is not None else None,
                        "incorrect_points": props.get("incPts") if props is not None else None,
                        "attempts": props.get("attempts") if props is not None else None,
                        "shuffle": props.get("shuffle") if props is not None else None,
                        "prompt": _question_prompt(root, choices),
                        "choices": [_describe_choice(root, c, tag) for c in choices],
                    }
                )
    return out


NULL_GUID = "00000000-0000-0000-0000-000000000000"


def _describe_choice(root: ET.Element, choice: ET.Element, intr_tag: str) -> dict:
    """One answer option.

    UC AILE, UC AYRI YERDE DURAN CEVAP -- ve ucu de olculdu:

      pick    <scoringData correct="true">, secenek metni SEKILDE.
      drag    isaret YOK; cevap `matchShpG`'nin kendisi, yani eslesme.
              (9 kayitli elle yapilmis kursta 9/9 correct="false".)
      text    isaret YOK; kabul edilen cevap kaydin KENDI <text>'inde,
              sekil hic yok (shpG null). Fixture'da <text>sabun</text>
              yaninda scoringData correct="false" duruyordu.

    Yani `correct` bayragini her aileye uygulamak iki yonde de yalan
    soyler: drag'de her suruklenebiliri "yanlis" etiketler, text'te kabul
    edilen cevabi "yanlis" gosterir. Metni sekilden okumak da ayni sinif --
    sekli olmayan ailede "(metin yok)" doner ve cevap kayboldu gorunur.
    """
    scoring = choice.find("scoringData")
    shape_guid = choice.get("shpG", "")
    if intr_tag == "freeTextEntryIntr":
        node = choice.find("text")
        label = (node.text or "").strip() if node is not None else ""
    else:
        label = shape_text(root, shape_guid)
    entry = {
        "text": label or "(metin yok)",
        "points": scoring.get("pts") if scoring is not None else None,
        "shape_guid": shape_guid,
    }
    match_guid = choice.get("matchShpG", NULL_GUID)
    if intr_tag == "dragDropIntr":
        entry["correct"] = None
        entry["drops_onto"] = (
            shape_text(root, match_guid) or match_guid if match_guid != NULL_GUID else None
        )
    elif intr_tag == "freeTextEntryIntr":
        # Listede duruyor olmak KABUL EDILDIGI anlamina gelir; bayrak degil,
        # varlik cevabi tasiyor.
        entry["correct"] = True
    else:
        entry["correct"] = _choice_is_correct(choice)
    return entry


def _choice_is_correct(choice: ET.Element) -> bool | None:
    scoring = choice.find("scoringData")
    if scoring is None or scoring.get("correct") is None:
        return None
    return scoring.get("correct", "").lower() in ("true", "1")


# Shapes whose text is a control label rather than slide copy.
LABEL_SHAPES = {"btn", "rsltBtn", "feedBackBtn", "textEntry"}


def stem_shape_guid(root: ET.Element, choice_guids: list[str]) -> str | None:
    """The shape holding the question itself.

    One definition, used by both the reader and the writer. When they each
    decide separately which shape is the stem they can disagree -- and then a
    question is written into one shape and read back from another, so the
    slide looks wrong while every individual step reports success.

    Scoped to the slide's own <shapeLst>: feedback layers live in
    <sldLayerLst>, and their text ("Correct! Because...") is frequently the
    longest on the slide.
    """
    base = root.find("shapeLst")
    if base is None:
        return None

    excluded: set[str] = set()
    for guid in choice_guids:
        shape = _find_by_guid(root, guid)
        if shape is not None:
            excluded.update(el.get("g", "") for el in shape.iter() if el.get("g"))

    def top_of(element: ET.Element) -> float:
        loc = element.find("loc")
        try:
            return float(loc.get("t")) if loc is not None else float("inf")
        except (TypeError, ValueError):
            return float("inf")

    choice_top = min((top_of(_find_by_guid(root, g)) for g in choice_guids
                      if _find_by_guid(root, g) is not None), default=float("inf"))

    placeholder = None
    candidates: list[tuple[float, str]] = []
    for top in list(base):
        for shape, _t, _doc, _s in _iter_text_shapes(top):
            guid = shape.get("g", "")
            if guid in excluded or shape.tag in LABEL_SHAPES | GENERATED_TEXT_SHAPES:
                continue
            ph = shape.find("ph")
            if ph is not None and ph.get("subType") in ("Question", "Title"):
                placeholder = placeholder or guid
            # Position, not text length. Length changes the moment a question
            # is written, so a longest-text rule picks one shape on the way in
            # and a different one on the way out.
            candidates.append((top_of(shape) if top_of(shape) != float("inf")
                               else top_of(top), guid))
    if placeholder:
        return placeholder
    if not candidates:
        return None
    above = [c for c in candidates if c[0] < choice_top]
    return max(above)[1] if above else min(candidates)[1]


def _question_prompt(root: ET.Element, choices: list[ET.Element]) -> str:
    guid = stem_shape_guid(root, [c.get("shpG", "") for c in choices])
    return shape_text(root, guid) if guid else ""


# --------------------------------------------------------------- js koprusu

# Yalnizca LITERAL argumanli cagrilar yakalanir: p.SetVar("Skor", 1).
# Degiskenli cagri -- p.SetVar(ad, v) -- bu kalibin DISINDA kalir ve ayrica
# sayilir; kapsam verdiktin yaninda basilsin diye (K5).
_JS_LITERAL = re.compile(r"""\b(?:Get|Set)Var\s*\(\s*(['"])(.*?)\1""")
_JS_TUM = re.compile(r"\b(?:Get|Set)Var\s*\(")


def js_references(pkg: StoryPackage, slide: str | None = None) -> dict:
    """JS tetikleyicilerindeki degisken adlari ve cozulup cozulmedigi.

    NEDEN OLCULUYOR. Olmayan bir ada yazmak ya da okumak SESSIZDIR -- bu
    varsayilmadi, preview'da olculdu (2026-08-23):

        p.SetVar("HicYokBoyleBirDegisken", "X")   -> hata yok, kod devam etti
        p.GetVar("BaskaBirYokDegisken")           -> null dondu, kod devam etti

    Yani yanlis yazilmis tek bir ad ne hata verir ne durur; sadece hicbir sey
    olmaz, ve `null` JS'te sessizce yayilir (null + 1 == 1). Editorde de,
    tetikleyici panelinde de gorunmez. Bu yuzden yazma aninda DEGIL denetimde
    yakalanir: cagiran once tetikleyiciyi, sonra degiskeni ekliyor olabilir ve
    bu mesru bir sira.

    KAPSAM: yalnizca literal adlar cozulur. `dynamic_calls` sifir degilse
    bazi adlar hic gorulmemistir -- "cozulmeyen yok" o durumda "hepsi
    dogru" demek DEGILDIR (K1).
    """
    bilinen = {v["name"].casefold() for v in variables(pkg)}
    parcalar = [(t.get("slide", ""), t.get("event", ""), t.get("javascript") or "")
                for t in triggers(pkg, slide)]
    return _js_coz(bilinen, parcalar)


def _js_coz(bilinen: set[str],
            parcalar: list[tuple[str, str, str]]) -> dict:
    """Kod parcalarindaki adlari coz. TEK yer -- ikinci bir uygulama yok.

    Hem dosyadaki tetikleyiciler (`js_references`) hem de HENUZ EKLENMEMIS
    kod (`js_kod_referanslari`) buradan gecer. Iki ayri uygulama olsaydi
    kapsam cumlesi ile sayilar ayrisirdi ve fark yuvarlama gibi degil,
    KESIT farki gibi davranirdi.
    """
    refs: list[dict] = []
    literal_sayisi = 0
    tum_sayisi = 0

    for slayt, olay, js in parcalar:
        if not js:
            continue
        tum_sayisi += len(_JS_TUM.findall(js))
        gorulen = set()
        for m in _JS_LITERAL.finditer(js):
            literal_sayisi += 1
            ad = m.group(2)
            if ad in gorulen:
                continue
            gorulen.add(ad)
            refs.append({
                "slide": slayt,
                "event": olay,
                "name": ad,
                "resolved": ad.casefold() in bilinen,
            })

    dinamik = max(0, tum_sayisi - literal_sayisi)
    return {
        "references": refs,
        "unresolved": [r for r in refs if not r["resolved"]],
        "dynamic_calls": dinamik,
        "scope": (
            "Yalnizca literal adlar cozuldu. "
            + (f"{dinamik} cagri degiskenli argumanla yapilmis ve "
               "ADI OKUNAMADI -- bu kesitte cozulmeyen olup olmadigi "
               "BILINMIYOR." if dinamik else
               "Degiskenli argumanla yapilmis cagri yok; kesit tam.")
        ),
    }


def js_kod_referanslari(pkg: StoryPackage, code: str) -> dict:
    """Henuz dosyada OLMAYAN bir kod parcasini paketin degiskenlerine karsi coz.

    `audit` yalnizca dosyaya yazilmis kodu gorur; ham JS'i eklemeden once
    denetlemek isteyen cagiran icin ayni cozumleme, ayni kapsam cumlesiyle.
    Kapi ancak eklemeden ONCE bakarsa kapidir.
    """
    bilinen = {v["name"].casefold() for v in variables(pkg)}
    return _js_coz(bilinen, [("", "", code or "")])
