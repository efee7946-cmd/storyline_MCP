"""Draw a slide, so its design can be judged instead of guessed at.

Every check up to here has been structural: does it parse, does it open, do
the boxes overlap. None of that says whether a slide looks any good, and a
layout can satisfy all of them and still be ugly. Composing without ever
seeing the result is how "proportionally correct" and "visually mediocre"
end up being the same thing.

This renders the slide's own geometry -- fills, boxes, text, sizes -- to SVG.
It is an approximation, not Storyline's renderer.

NEYI DOGRU, NEYI YAKLASIK CIZDIGI. Bir kez yalan soyledi ve o yalan pahaliydi:
her sekli duz dikdortgen ciziyordu, dolayisiyla bir chevron ile bir bar ayni
gorunuyordu ve "sorun yok" diyordu. Yaklasik cizmek sorun degil; hangi
yaklasimin nerede oldugunu bilmemek sorun. Olculdu (2026-08-14):

  DOGRU
    rect, textBox        zaten dikdortgen; bestelenen 116 seklin hepsi bu
    roundRect, btn       yuvarlak kose
    oval, clkAreaOval    elips
    line                 cizgi
    group                hicbir sey cizilmez -- DOGRU davranis: childLst
                         yalnizca GUID tutar, uyeler zaten ust duzeyde cizilir
                         (26 group olculdu, hicbirinin kendi dolgusu yok)
    pic                  gercek gorsel gomulur. assetG -> story.xml/mediaLst
                         -> md5 -> story/media zinciri yurunur; referans
                         projede 21/21 cozuldu. Cozulemezse KIRMIZI bir kutu
                         cizilir, gri degil: gorseli olmayan bir slaytla
                         karistirilmasin diye.
    slayt zemini         <bg> altindaki solidFill/gradFill. Sekil dolgusu
                         <bG>, slayt zemini <bg> -- tek harf fark. Onceden
                         okunmuyordu ve her slayt beyaza ciziliyordu.

    geometri            prstGeom'un COCUK ogesinden okunur, shape.tag'den
                         degil -- Storyline oyle yapiyor. Onceden etikete
                         bakiliyordu ve ikisi ayrisabiliyordu: geometrisi
                         roundRect'e cevrilmis bir <oval> dosyada dogruydu,
                         onizlemede elips ciziliyordu. Onizleme kendi
                         yaptigi duzeltmeyi gormuyordu.

  YANLIS -- duz dikdortgen cizilir, oysa degil
    triangle, chevron, pentagonArrow, plaque, polygon, importedVector
    Donor havuzundaki 13 adayin 6'si bu grupta. Bir donoru gozle secerken
    onizlemeye bakmak, bu alti aday icin bilgi vermez.

  CIZILMEZ
    sldLayerLst          geri bildirim katmanlari. Soru slaydinin KENDISI
                         gorunur (ust duzeyde 11-25 sekil olculdu); gorunmeyen
                         dogru/yanlis katmanlari, ki acilista zaten gorunmez.
    stateLst             hover/down govdeleri; yalnizca Normal cizilir
    animEffect           zamanlama ve hareket

  TAHMIN
    punto olcegi        DIKEY carpan olculdu (2026-08-17) ve bu dosya
                        onu KULLANMIYOR: `pt * (sw/720)` yaziyor, yani
                        1920'lik bir deckte yaziyi ~%12 KUCUK ciziyor.
                        Yatay carpan dogru (2.667), dikey 2.99 olculdu.
                        Onizlemede kucuk gorunen bir yazi, kursta daha
                        buyuk olabilir.
    satir sarmasi        shapes.CHAR_WIDTH_RATIO ile; olculen bant 13-38pt
    golge, kenarlik, seffaflik disindaki efektler
    metin konumu         DIKEY HIZALAMA artik uygulaniyor: sekil vertAlign
                         tasiyor (t/m/b) ve onizleme onu okuyor. Onceden her
                         yazi kutusunun ustune ciziliyordu; menu butonlarinin
                         hepsi vertAlign="m" oldugu icin uzun bir buton "bos
                         panel" gibi gorunuyordu ve o goruntuye bakip tasarim
                         karari verilmek uzereydi. KIRPMA da uygulaniyor -- kutusuna sigmayan satir cizilmez,
                         Storyline'da oldugu gibi. Once kirpilmiyordu ve
                         tasan yazi komsusunun uzerine biniyordu; bir rubrik
                         kosusu, dosyada hic cakisma olmayan bir kursta
                         "buton-metin cakismasi" bildirdi.
                         Tasmanin KENDISI bu yuzden burada gorunmez; o soru
                         invariants.check_text_fits'te dosyadan olculuyor.
    zemini olmayan slayt beyaz cizilir. Zeminini slideMaster'dan mi aliyor,
                         gercekten beyaz mi -- OLCULMEDI.

Bu kadari sikisikligi, hizasizligi, zayif hiyerarsiyi ve olu alani gormeye
yeter -- kompozisyon katmaninin yanlis yaptigi seyler bunlar. Sekil
anatomisini gormeye yetmez; onun icin Storyline'da acmak gerekir.
"""

from __future__ import annotations

import base64
import hashlib
import io
import math
import re
import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path

from . import model, shapes
from .package import StoryPackage

# Roughly how Storyline renders these outlines, for shapes we draw as boxes.
ROUNDED = {"roundRect", "btn", "rsltBtn", "feedBackBtn", "button"}
ELLIPSE = {"oval", "clkAreaOval", "smileyFace"}
LINEAR = {"line"}

MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".bmp": "image/bmp", ".svg": "image/svg+xml"}
# Gomulen goruntunun en genis kenari. Onizleme 960px cizilir; bunun uzerindeki
# her piksel, bakilmayacak bir ayrinti icin SVG'yi buyutur. Paketteki tek bir
# gorsel 1.3 MB olabiliyor ve on sekiz slaytlik bir deck onlarca tane tasiyor.
MAX_EMBED_PX = 900
_MEDIA_CACHE: dict[tuple, dict[str, str]] = {}
# Degrade kimliklerine eklenen, o cizime ozgu on ek. Tek elemanli liste,
# cunku render_slide her cagrida yerine yazar ve ic fonksiyonlar okur.
_GRAD_PREFIX = [""]

FONT_STACK = "Segoe UI, system-ui, sans-serif"


def drawn_form(shape: ET.Element) -> str:
    """Şeklin ÇİZİLECEK biçimi: prstGeom önce, etiket sonra.

    Storyline geometriyi prstGeom'un COCUK ogesiyle adlandiriyor -- bu
    oturumda olculdu (<button vertexSet="false"/>). Onizleme ise shape.tag'e
    bakiyordu ve ikisi ayrisabiliyor: geometrisi roundRect'e cevrilmis bir
    <oval> dosyada dogru, onizlemede elips ciziliyordu. Yani onizleme,
    KENDI yaptigi duzeltmeyi gormuyordu.
    """
    geom = shape.find("prstGeom")
    child = next(iter(geom), None) if geom is not None else None
    name = child.tag if child is not None else shape.tag
    if name in ROUNDED or shape.tag in ROUNDED:
        return "rounded"
    if name in ELLIPSE:
        return "ellipse"
    if name in LINEAR or shape.tag in LINEAR:
        return "line"
    return "box"


def slide_ground(root: ET.Element, defs: list[str] | None = None) -> str | None:
    """Slaydın kendi zemini, varsa.

    Şekil dolgusu <bG> altında, slayt zemini <bg> altında durur -- tek harf
    fark ve ikisi ayrı dünya. Önizleme yalnızca şekilleri okuduğu için her
    slaydı beyaza çiziyordu, ve bu sessiz bir yalandı: mor zeminli bir slaydın
    üzerindeki beyaz yazı, beyaz zeminde görünmez olur ve okunan şey "yazı
    kaybolmuş" olur. Ölçüldü -- slide5.xml'in zemini #444182.

    Zemini olmayan slayt da vardır (kompozisyon kendi tam sayfa dikdörtgenini
    koyar); orada None döner ve beyaz kalır, ki üstündeki dikdörtgen onu
    zaten örtecektir.
    """
    bg = root.find("bg")
    if bg is None:
        return None
    return _fill_of(bg, defs, direct=True)


def _fill_of(shape: ET.Element, defs: list[str] | None = None,
             *, direct: bool = False) -> str | None:
    """The shape's fill as an SVG paint value.

    direct: dolgu ogeleri elemanin dogrudan altinda (slayt <bg>'si boyle),
    yoksa <bG> alt agacinda aranir (sekiller boyle).

    A gradient becomes a real gradient in the preview rather than its first
    stop: the whole point of the preview is to show what was actually built,
    and flattening the wash here would hide exactly the thing being judged.
    """
    base = "" if direct else "bG/"
    grad = shape.find(f"{base}gradFill")
    if grad is not None and defs is not None:
        stops = []
        for stop in grad.findall("stops/stop"):
            srgb = stop.find("clr/srgbClr")
            if srgb is None or not srgb.get("val"):
                continue
            stops.append((float(stop.get("pos") or 0), "#" + srgb.get("val"),
                          _alpha_of(stop.find("clr"))))
        if len(stops) >= 2:
            # Kimlik slayta ozgu olmali. "g0" gibi bir ad, birden fazla SVG
            # ayni HTML sayfasina konuldugunda cakisir ve tarayici url(#g0)'i
            # sayfadaki ILK tanima baglar -- yani her slayt, ilk slaydin
            # degradesiyle boyanir. Olculdu: acik zeminli bir tema, koyu
            # lacivert cizildi ve hata temada saniliyordu.
            ident = f"{_GRAD_PREFIX[0]}g{len(defs)}"
            angle = float(grad.get("angle") or 90)
            # Storyline measures the sweep clockwise from the x-axis.
            radians = math.radians(angle)
            dx, dy = math.cos(radians) / 2, math.sin(radians) / 2
            body = "".join(
                f'<stop offset="{p:.0f}%" stop-color="{c}" stop-opacity="{a:.3f}"/>'
                for p, c, a in stops)
            defs.append(
                f'<linearGradient id="{ident}" x1="{0.5 - dx:.3f}" y1="{0.5 - dy:.3f}" '
                f'x2="{0.5 + dx:.3f}" y2="{0.5 + dy:.3f}">{body}</linearGradient>')
            return f"url(#{ident})"

    srgb = shape.find(f"{base}solidFill/clr/srgbClr")
    if srgb is None:
        srgb = shape.find(f"{base}solidFill/srgbClr")
    if srgb is None or not srgb.get("val"):
        return None
    value = srgb.get("val")
    opacity = _alpha_of(shape.find(f"{base}solidFill/clr"))
    if opacity >= 1.0:
        return "#" + value
    r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{opacity:.3f})"


def media_index(pkg: StoryPackage) -> dict[str, str]:
    """assetG -> paketteki görsel parçasının adı.

    Bir <pic> hiçbir dosya adı taşımaz; assetG ile story.xml'deki <media>
    kaydına, o kayıt da md5 ile story/media altındaki baytlara bağlanır.
    Zincirin tamamı yürünmeden hangi şeklin hangi resmi gösterdiği bilinemez.

    Sonuç önbelleğe alınır: bir pakette yetmiş sekiz görsel olabiliyor ve
    hepsinin md5'ini her slayt için yeniden hesaplamak, önizlemeyi çizmekten
    uzun sürer.
    """
    try:
        path = Path(pkg.path)
        stat = path.stat()
        key = (str(path), stat.st_mtime_ns, stat.st_size)
    except Exception:
        key = (id(pkg),)
    if key in _MEDIA_CACHE:
        return _MEDIA_CACHE[key]

    by_digest: dict[str, str] = {}
    for part in pkg._order:
        if "/media/" not in part:
            continue
        try:
            by_digest.setdefault(hashlib.md5(pkg.read(part)).hexdigest(), part)
        except Exception:
            continue

    index: dict[str, str] = {}
    try:
        story = pkg.parse("story/story.xml")
    except Exception:
        _MEDIA_CACHE[key] = index
        return index
    for entry in story.iter("media"):
        guid = entry.get("g")
        stream = entry.find("md5Checksum/stream")
        digest = (stream.text or "").strip() if stream is not None else ""
        part = by_digest.get(digest)
        if guid and part:
            index[guid] = part
    _MEDIA_CACHE[key] = index
    return index


def _data_uri(pkg: StoryPackage, part: str, box_px: float) -> str | None:
    """Görselin baytlarını, çizileceği boyuta indirip data URI'ye çevirir."""
    suffix = Path(part).suffix.lower()
    mime = MIME.get(suffix)
    if not mime:
        return None
    try:
        data = pkg.read(part)
    except Exception:
        return None
    if suffix != ".svg":
        # Kucultmek isteğe bağlı: PIL yoksa orijinal baytlar gomulur ve
        # onizleme yine dogru cizer, sadece dosya buyur.
        try:
            from PIL import Image

            target = int(max(min(box_px * 2, MAX_EMBED_PX), 120))
            with Image.open(io.BytesIO(data)) as img:
                if max(img.size) > target:
                    img.thumbnail((target, target))
                    buffer = io.BytesIO()
                    fmt = "PNG" if img.mode in ("RGBA", "LA", "P") else "JPEG"
                    img.convert("RGBA" if fmt == "PNG" else "RGB").save(
                        buffer, fmt, quality=82)
                    data, mime = buffer.getvalue(), (
                        "image/png" if fmt == "PNG" else "image/jpeg")
        except Exception:
            pass
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def _alpha_of(clr: ET.Element | None) -> float:
    """A colour's opacity, 0..1. The format stores it as 0..100000."""
    if clr is None:
        return 1.0
    alpha = clr.find("alpha")
    if alpha is None or not alpha.get("val"):
        return 1.0
    try:
        return max(0.0, min(float(alpha.get("val")) / 100000.0, 1.0))
    except ValueError:
        return 1.0


def _text_style(shape: ET.Element) -> tuple[str, float, bool, str]:
    """Colour, point size, boldness and alignment of a shape's first run."""
    colour, size, bold, align = "#FFFFFF", 16.0, False, "l"
    for text_el in shape.iter("text"):
        raw = (text_el.text or "").strip()
        if not raw.startswith("<Document"):
            continue
        m = re.search(r'ForegroundColor="#?([0-9A-Fa-f]{6})"', raw)
        if m:
            colour = "#" + m.group(1)
        m = re.search(r'FontSize="([\d.]+)"', raw)
        if m:
            size = float(m.group(1))
        bold = 'FontBold="true"' in raw
        m = re.search(r'Justification="(\w+)"', raw)
        if m:
            align = {"Left": "l", "Center": "c", "Right": "r"}.get(m.group(1), "l")
        break
    return colour, size, bold, align


def _wrap(text: str, chars_per_line: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words, current = paragraph.split(), ""
        for word in words:
            if len(current) + len(word) + 1 <= chars_per_line:
                current = f"{current} {word}".strip()
            else:
                if current:
                    lines.append(current)
                current = word
        lines.append(current)
    return lines or [""]


def render_slide(pkg: StoryPackage, slide: str, *, width: int = 960) -> str:
    """One slide as SVG."""
    part = pkg.slide_part_for(slide)
    root = pkg.parse(part)
    _GRAD_PREFIX[0] = hashlib.md5(part.encode("utf-8")).hexdigest()[:6] + "-"
    sw, sh = shapes.slide_size(root)
    scale = width / sw
    height = int(sh * scale)

    out: list[str] = []
    defs: list[str] = []

    shape_list = root.find("shapeLst")
    for shape in list(shape_list) if shape_list is not None else []:
        rect = shapes.shape_rect(shape)
        if rect is None:
            continue
        l, t, r, b = (v * scale for v in rect)
        w, h = max(r - l, 1), max(b - t, 1)
        fill = _fill_of(shape, defs)

        form = drawn_form(shape)
        if form == "line":
            out.append(f'<rect x="{l:.1f}" y="{t:.1f}" width="{w:.1f}" '
                       f'height="{max(h, 2):.1f}" fill="{fill or "#888"}"/>')
        elif form == "ellipse":
            out.append(f'<ellipse cx="{l + w / 2:.1f}" cy="{t + h / 2:.1f}" '
                       f'rx="{w / 2:.1f}" ry="{h / 2:.1f}" '
                       f'fill="{fill or "none"}" stroke="#9993" />')
        elif fill:
            radius = 10 if form == "rounded" else 0
            out.append(f'<rect x="{l:.1f}" y="{t:.1f}" width="{w:.1f}" height="{h:.1f}" '
                       f'rx="{radius}" fill="{fill}"/>')
        elif shape.tag == "pic":
            # Gercek gorsel gomulur. Bir gorsel yer tutucu olarak cizildiginde
            # slaydin dengesi hakkinda hicbir sey soylenemez: sayfanin ucte
            # birini kaplayan bir fotograf, gri bir kutudan tamamen baska bir
            # agirlik tasir ve kompozisyon o agirliga gore kurulur.
            uri = None
            part_name = media_index(pkg).get(shape.get("assetG") or "")
            if part_name:
                uri = _data_uri(pkg, part_name, w)
            if uri:
                out.append(
                    f'<image x="{l:.1f}" y="{t:.1f}" width="{w:.1f}" height="{h:.1f}" '
                    f'preserveAspectRatio="xMidYMid slice" href="{uri}"/>')
            else:
                # Cozulemeyen gorsel, gorseli olmayan bir slaytla ayni
                # gorunmemeli: biri tasarim karari, digeri bu aracin korlugu.
                why = "baglanti yok" if not part_name else "okunamadi"
                out.append(
                    f'<rect x="{l:.1f}" y="{t:.1f}" width="{w:.1f}" height="{h:.1f}" '
                    f'fill="#4A2530" stroke="#B4566E" stroke-dasharray="6 4"/>')
                out.append(
                    f'<text x="{l + w / 2:.1f}" y="{t + h / 2:.1f}" fill="#E8A0B4" '
                    f'font-size="13" text-anchor="middle">gorsel cozulemedi '
                    f'({why})</text>')

        text = model.shape_text(root, shape.get("g", "")).strip()
        if not text:
            continue
        colour, pt, bold, align = _text_style(shape)
        px = pt * (sw / 720) * scale
        px = max(px, 8)
        chars = max(int(w / (px * 0.52)), 8)
        lines = _wrap(text, chars)
        anchor = {"l": "start", "c": "middle", "r": "end"}[align]
        x = {"l": l + 6, "c": l + w / 2, "r": r - 6}[align]

        # DIKEY HIZALAMA. Sekil `vertAlign` tasiyor (t/m/b) ve Storyline onu
        # uyguluyor; onizleme uygulamiyordu, her yaziyi kutusunun ustune
        # ciziyordu. Olculdu: menu secim butonlarinin hepsi vertAlign="m",
        # yani etiket Storyline'da ORTALI -- ve donor havuzundaki on uc
        # adayin on biri de oyle.
        #
        # Bu bir suslemenin degil, bir YARGININ meselesi: yuksek bir butonun
        # etiketi tepede durunca "bos panel" gibi gorunuyor ve o goruntuye
        # bakip tasarim karari vermek uzereydim. Ucuncu kez ayni sinif.
        block = min(len(lines), 9) * px * 1.4
        top_pad = px * 1.05
        vert = shape.get("vertAlign") or "t"
        if vert == "m":
            y = t + max((h - block) / 2, 0) + top_pad
        elif vert == "b":
            y = t + max(h - block, 0) + top_pad
        else:
            y = t + top_pad
        weight = ' font-weight="700"' if bold else ""
        for line in lines[:9]:
            # Storyline tasan metni KIRPAR; onizleme kirpmayinca kutusundan
            # tasan yazi komsusunun uzerine cizilirdi ve okunan sey "cakisma"
            # olurdu. Olculdu: rubrik, dosyada hic cakisma olmayan bir kursta
            # "buton-metin cakismasi" bildirdi -- var olmayan bir kusuru
            # puanladi. Kirpmak sadakat, gizleme degil.
            #
            # Tasmanin kendisi gorunmez hale gelir; o soru burada degil
            # invariants.check_text_fits'te olculuyor (kutu yuksekligi ile
            # gereken yuksekligin farki, dosyadan).
            if y > b + px * 0.25:
                break
            out.append(
                f'<text x="{x:.1f}" y="{y:.1f}" fill="{colour}" font-size="{px:.1f}" '
                f'text-anchor="{anchor}"{weight}>{escape(line)}</text>'
            )
            y += px * 1.4

    header = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" font-family="{FONT_STACK}">',
    ]
    if defs:
        header.append("<defs>" + "".join(defs) + "</defs>")
    header.append(f'<rect width="{width}" height="{height}" '
                  f'fill="{slide_ground(root, defs) or "#FFFFFF"}"/>')
    return "\n".join(header + out + ["</svg>"])


def render_deck(pkg: StoryPackage, slides: list[str] | None = None,
                *, width: int = 460) -> str:
    """Several slides side by side, to see whether a course holds together."""
    index = model.slide_index(pkg)
    names = slides or [ref.basename for ref in index.values()]
    cards = []
    for name in names:
        try:
            svg = render_slide(pkg, name, width=width)
        except Exception:
            continue
        label = next((r.name for r in index.values() if r.basename == name), name)
        cards.append(
            f'<figure style="margin:0"><div style="border:1px solid #2e333c;'
            f'border-radius:8px;overflow:hidden;background:#fff">{svg}</div>'
            f'<figcaption style="font:12px {FONT_STACK};color:#9aa3af;'
            f'padding:6px 2px">{escape(name)} — {escape(label[:44])}</figcaption></figure>'
        )
    return (
        '<div style="display:grid;gap:18px;'
        'grid-template-columns:repeat(auto-fill,minmax(460px,1fr))">'
        + "".join(cards) + "</div>"
    )
