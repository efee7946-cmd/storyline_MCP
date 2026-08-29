"""Images and video.

A <pic> shape names no file. It carries assetG, which points at a <media>
entry in story.xml, and that entry names no file either -- it carries an md5
checksum. The bytes in story/media are found by matching that checksum. Nothing
in the slide mentions a filename or a relationship id, which is why the link
looks missing until the checksum is noticed: measured on a real course, all 18
media records resolve this way and none resolve any other.

So adding an image means four things, and all four or none:

  1. the bytes, as a new part under story/media
  2. a <media> record carrying their md5
  3. a media relationship on the slide
  4. a <pic> shape whose assetG points at the record

The image's own dimensions are read from its header so the frame keeps the
aspect ratio. A picture stretched to fit whatever box was asked for is the
kind of thing nobody reports as a bug and everybody notices.

Video is the same four things plus two: the record is <video> rather than
<media>, and the shape has to be told how long the film runs -- which is read
out of the MP4 itself, because a timeline entry shorter than the film cuts it
off mid-sentence and nothing in the project complains.
"""

from __future__ import annotations

import hashlib
import random
import re
import string
import struct
import zlib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from . import shapes
from .clone import _register_content_type  # noqa: F401  (kept for symmetry)
from .clone import new_guid
from .package import STORY_PART, StoryPackage, StoryError

MEDIA_TYPES = {".png": "Png", ".jpg": "Jpeg", ".jpeg": "Jpeg", ".gif": "Gif"}

# Video is stored the same four ways, with two differences that were measured
# rather than guessed (test/0_duz_kopya.story, two videos):
#
#   * the bytes keep a .mpeg part name and are declared video/mpeg, but they
#     are the original MP4 -- both parts start with "ftypisom" and their md5
#     equals the <video> record's checksum, so nothing is transcoded;
#   * the record is <video>, not <media>, and it carries the pixel size, while
#     the shape carries the duration and the frame rate in <movie>.
#
# A poster is registered alongside as an ordinary Png record, because that is
# what thumbG points at in both measured cases. Leaving thumbG null would be a
# reference to nothing on a slide the learner sees.
VIDEO_TYPES = {".mp4": "Mp4", ".m4v": "Mp4"}
VIDEO_PART_EXT = ".mpeg"
POSTER_COLOR = "#12161D"
CONTENT_TYPES = "[Content_Types].xml"
MIME = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "gif": "image/gif", "mpeg": "video/mpeg"}
NAME_CHARS = string.ascii_letters + string.digits


def _media_name(extension: str) -> str:
    return "R" + "".join(random.choices(NAME_CHARS, k=11)) + extension


def _rel_id(existing: set[str]) -> str:
    while True:
        candidate = "R" + "".join(random.choices("0123456789abcdef", k=16))
        if candidate not in existing:
            return candidate


def image_size(data: bytes) -> tuple[int, int] | None:
    """Pixel dimensions from a PNG or JPEG header, without decoding the image."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        width, height = struct.unpack(">II", data[16:24])
        return int(width), int(height)
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                          0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                height, width = struct.unpack(">HH", data[i + 5:i + 9])
                return int(width), int(height)
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            (length,) = struct.unpack(">H", data[i + 2:i + 4])
            i += 2 + length
    return None


def _ensure_extension(pkg: StoryPackage, extension: str) -> None:
    """Declare the file type in [Content_Types] if the package has not met it."""
    raw = pkg.read(CONTENT_TYPES).decode("utf-8")
    ext = extension.lstrip(".")
    if re.search(rf'<Default Extension="{ext}"', raw):
        return
    fragment = f'<Default Extension="{ext}" ContentType="{MIME[ext]}" />'
    at = raw.index("<Override")
    pkg.replace_raw(CONTENT_TYPES, (raw[:at] + fragment + raw[at:]).encode("utf-8"))


def _media_part(pkg: StoryPackage, data: bytes, extension: str) -> str:
    """Write the bytes as a new part under story/media and declare the type."""
    existing = [n for n in pkg._order if "/media/" in n]
    part = f"story/media/{_media_name(extension)}"
    pkg.add_part(part, data,
                 after=existing[-1] if existing else None,
                 like=existing[-1] if existing else None)
    _ensure_extension(pkg, extension)
    return part


def _link_media(pkg: StoryPackage, slide_part: str, media_part: str) -> str:
    """Point the slide's relationship file at the bytes, and say with what id.

    One function for both kinds on purpose: a video links exactly the way a
    picture does (Type="media"), and two copies of this would drift the moment
    one of them learned something the other did not.
    """
    rels_part = f"story/slides/_rels/{slide_part.rsplit('/', 1)[1]}.rels"
    if pkg.has_part(rels_part):
        raw = pkg.read(rels_part).decode("utf-8")
        rel = _rel_id(set(re.findall(r'Id="([^"]+)"', raw)))
        fragment = f'<Relationship Type="media" Target="/{media_part}" Id="{rel}" />'
        at = raw.rindex("</Relationships>")
        pkg.replace_raw(rels_part, (raw[:at] + fragment + raw[at:]).encode("utf-8"))
        return rel
    rel = _rel_id(set())
    body = ('﻿<?xml version="1.0" encoding="utf-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Type="media" Target="/{media_part}" Id="{rel}" />'
            '</Relationships>')
    pkg.add_part(rels_part, body.encode("utf-8"),
                 like=f"story/slides/_rels/{pkg.slide_parts[0].rsplit('/', 1)[1]}.rels")
    return rel


FIT_MODES = ("contain", "cover", "stretch")


def _cover_crop(data: bytes, extension: str, oran: float) -> tuple[bytes, tuple[int, int]] | None:
    """Kaynagi kutunun ORANINA gore ortadan kirp; kirpilamadiysa None.

    NICIN KIRPMA, NICIN GERME. Kapak ve tam boy bantlar alani DOLDURMAK icin
    ayrilir ve doldurmanin uc yolu var: germek, sigdirmak, kirpmak.

      germek   -- olculdu 2026-08-29: 2172x724 (3:1) bir fotograf 720x540'lik
                  (4:3) kapaga gerildi, yani genisligi %44'e sikisti. Kullanici
                  "duzgun eklenemedi" diye bildirdi. Bozulma sessizdir: dosya
                  gecerli, dogrulama temiz, yalnizca insanlar yanlis gorunur.
      sigdirmak -- bozmaz ama kapagi doldurmaz; 3:1 bir fotograf kapagin
                  ortasinda ince bir serit olarak kalir, alti ustu bos zemin.
      kirpmak  -- fotografin ortasi alinir, oran korunur, alan dolar.

    Ucuncusu yapiliyor ve BAYT DUZEYINDE yapiliyor: Storyline'in kendi kirpma
    alani (<picFormat><sourceRect>) ELIMIZDE OLCULMEDI -- iki gercek kursta
    kirpilmis tek bir <pic> yok, yani birimlerini (yuzde mi, EMU mu) tahmin
    etmek gerekirdi. Tahmin edilen bir birim, dosya acilana kadar gorunmeyen
    bir kusurdur. Kendi kirptigimiz baytin nereye oturdugu ise belli.

    Pillow yoksa None doner ve cagiran SIGDIRMAYA duser: bozmak, kirpamamaktan
    kotudur.
    """
    if extension == ".gif":
        return None            # animasyonlu olabilir; yeniden kodlamak dondurur
    try:
        from PIL import Image  # noqa: PLC0415 - istege bagli bagimlilik
    except ImportError:
        return None
    try:
        import io as _io
        with Image.open(_io.BytesIO(data)) as im:
            im.load()
            genislik, yukseklik = im.size
            if not genislik or not yukseklik:
                return None
            simdiki = genislik / yukseklik
            # Zaten oraninda: kirpma bir sey kazandirmaz, yeniden kodlama
            # yalnizca kalite kaybi ve boyut degisimi getirir.
            if abs(simdiki - oran) <= 0.01 * oran:
                return None
            if simdiki > oran:                     # cok genis -> yanlardan kirp
                yeni_g = int(round(yukseklik * oran))
                kutu = ((genislik - yeni_g) // 2, 0,
                        (genislik - yeni_g) // 2 + yeni_g, yukseklik)
            else:                                  # cok uzun -> alt/usttan kirp
                yeni_y = int(round(genislik / oran))
                kutu = (0, (yukseklik - yeni_y) // 2,
                        genislik, (yukseklik - yeni_y) // 2 + yeni_y)
            kirpik = im.crop(kutu)
            cikti = _io.BytesIO()
            if extension in (".jpg", ".jpeg"):
                kirpik.convert("RGB").save(cikti, "JPEG", quality=90,
                                           optimize=True)
            else:
                kirpik.save(cikti, "PNG", optimize=True)
            return cikti.getvalue(), kirpik.size
    except Exception:          # noqa: BLE001 - bozuk dosya kursu durdurmasin
        return None


def _fit_box(slide_w: float, slide_h: float, x: float, y: float, w: float,
             h: float | None, pixels: tuple[int, int] | None,
             keep_ratio: bool = True) -> tuple[float, float, float, float]:
    """The rectangle a piece of media actually gets, in slide units.

    One place computes it because a picture and a video are framed by the same
    two rules: keep the source ratio, and stay inside the room given. A tall
    image at a given width can be several times the slide's height -- 579x2048
    asked to fill 38% of the width comes out at 179% -- and keeping the ratio
    means scaling both sides down to fit, not letting one run off.

    h is the AREA's height, not the picture's. Given one, the media is fitted
    into that area and centred in it; without one there is only an anchor, and
    the slide's bottom edge is the single bound. That distinction was missing:
    h was read only when keep_ratio was off, so a picture handed the reserved
    panel's height kept its ratio and then overflowed the panel, bounded by
    nothing but the foot of the slide.
    """
    left, top = x / 100 * slide_w, y / 100 * slide_h
    area_w = w / 100 * slide_w
    area_h = (h / 100 * slide_h) if h is not None else (slide_h - top)
    box_w = area_w
    if h is not None and not keep_ratio:
        box_h = area_h                     # fill the area; hero and bleed want this
    elif pixels and pixels[0]:
        box_h = box_w * pixels[1] / pixels[0]
    else:
        box_h = area_h
    if box_h > area_h:
        box_w *= area_h / box_h
        box_h = area_h
    if h is None:
        return left, top, box_w, box_h
    # Centred in what the area has left over. Anchored top-left, a 16:9 film in
    # a full-height slab hangs from the ceiling with a band of empty panel
    # underneath it.
    return left + (area_w - box_w) / 2, top + (area_h - box_h) / 2, box_w, box_h


def _media_list(story):
    """Kayitlarin gercekten durdugu liste: mediaLst > mediaLst.

    DISTAKI DEGIL ICTEKI. Bu bir uslup tercihi degil, olculdu (2026-08-29):
    dort gercek kursun DORDUNDE de her <media> ve <video> kaydi ICTEKI listede
    duruyor (20, 7, 8 ve 18 kayit). Kod distakine ekliyordu, yani kayit ictek
    listenin KARDESI oluyordu.

    Sonucu sessiz ve tamdi: paket gecerli kaliyor, dogrulama temiz geciyor, her
    bag md5'e kadar izlenebiliyor -- ama Storyline kaydi hic gormuyor, <pic>
    sekli assetG'yi cozemiyor ve slaytta "The image can't be displayed" yaziyor.
    Kullanici bunu iki ayri kursta bildirdi; yapisal probe'lar bag zincirini
    olcuyor, KAYDIN NEREDE DURDUGUNU olcmuyordu (sinandi != baglandi).
    """
    dis = story.find("mediaLst")
    if dis is None:
        raise StoryError("story.xml icinde mediaLst yok.")
    ic = dis.find("mediaLst")
    return ic if ic is not None else dis


def _register_media(pkg: StoryPackage, data: bytes, display_name: str,
                    kind: str, *, source: Path | None = None,
                    original: bytes | None = None) -> str:
    """Add the <media> record and return its GUID.

    KAYIT, KAYNAGI ANLATIR; PARCAYI DEGIL. Bu ayrimi Storyline'in kendi
    yazdigi bir kayittan okuduk (REF_SONRA.story, 2026-08-29):

        bytes    = DISKTEKI dosyanin boyutu   (3.229.567)
        parca    = pakete yazilan baytlar     (532.010 -- Storyline yeniden kodluyor)
        md5/stream = paketteki baytlarin md5'i
        md5/source = DISKTEKI dosyanin md5'i
        origFile / source = dosyanin tam yolu
        modDT    = dosyanin degistirilme zamani

    Biz her alani PARCADAN turetiyorduk: origFile ve source bos, modDT sifir
    tarih, bytes parcanin boyutu, iki md5 de ayni. Sonucu tek kelimeyle:
    Storyline gorseli HIC gostermedi -- ne JPEG ne PNG, ne kucugu ne buyugu,
    dosya gecerli ve her bag izlenebilir oldugu halde ("The image can't be
    displayed"). Alanlari yukaridaki gibi doldurdugumuz kopya ise ayni slaytta
    ayni baytlarla GORUNDU. Ayirt edici deney MEDYA_TESTI_5/6'da.

    Hangi alanin tek basina belirleyici oldugu ayrilmadi: besi birlikte
    degistirildi ve birlikte calisti. Ayirmak bes ayri Storyline denemesi
    demekti; degeri, dogru davranisin kendisinden az.
    """
    story = pkg.parse(STORY_PART)
    media_list = _media_list(story)
    ham = original if original is not None else data

    guid = new_guid()
    entry = ET.SubElement(media_list, "media")
    entry.set("g", guid)
    entry.set("verG", new_guid())
    entry.set("type", kind)
    entry.set("displayName", display_name)
    entry.set("origFile", str(source) if source else "")
    entry.set("source", str(source) if source else "")
    entry.set("useCnt", "0")
    entry.set("bytes", str(len(ham)))
    entry.set("modDT", _mod_time(source))
    entry.set("addDT", datetime.now(timezone.utc).astimezone().isoformat())
    ET.SubElement(entry, "langAltText")
    checksum = ET.SubElement(entry, "md5Checksum")
    ET.SubElement(checksum, "stream").text = hashlib.md5(data).hexdigest()
    ET.SubElement(checksum, "source").text = hashlib.md5(ham).hexdigest()
    pkg.replace_xml(STORY_PART, story)
    return guid


def _mod_time(source: Path | None) -> str:
    """Kaynak dosyanin degistirilme zamani, Storyline'in yazdigi bicimde."""
    if source is None:
        return "0001-01-01T00:00:00"
    try:
        return datetime.fromtimestamp(source.stat().st_mtime).astimezone().isoformat()
    except OSError:
        return "0001-01-01T00:00:00"


def add_image(
    pkg: StoryPackage,
    slide: str,
    image: str | Path,
    *,
    x: float = 10,
    y: float = 30,
    w: float = 40,
    h: float | None = None,
    name: str | None = None,
    fit: str = "contain",
    behind: bool = False,
) -> dict:
    """Place an image file on a slide. x/y/w/h are percentages of the slide.

    fit, alanla gorselin orani tutmadiginda ne olacagini soyler:
      contain - alanin icine sigar, orani korunur (varsayilan)
      cover   - alani DOLDURUR; fazlalik ortadan kirpilir (bkz. _cover_crop)
      stretch - alana gerilir; oran bozulur, yalnizca acikca istenirse

    behind sends the picture to the back, under the text already on the slide.
    That is what a full-bleed cover needs: the photograph is the ground, the
    scrim sits on it, and the words sit on the scrim.
    """
    if fit not in FIT_MODES:
        raise StoryError(f"Bilinmeyen fit: {fit!r}. Secenekler: {', '.join(FIT_MODES)}")
    source = Path(image)
    if not source.is_file():
        raise StoryError(f"Gorsel bulunamadi: {source}")
    extension = source.suffix.lower()
    if extension not in MEDIA_TYPES:
        raise StoryError(
            f"Desteklenmeyen bicim: {extension}. Kullanilabilir: "
            f"{', '.join(sorted(MEDIA_TYPES))}"
        )

    data = source.read_bytes()
    ham = data                      # kirpmadan onceki hali: kayit BUNU anlatir
    part = pkg.slide_part_for(slide)
    root = pkg.parse(part)
    slide_w, slide_h = shapes.slide_size(root)

    # 0. KIRPMA, baytlari yazmadan once: alani dolduracaksa gorselin ORANI
    # alanin oranina getirilir. Sonra sigdirma matematigi zaten tam alani
    # verir -- germeye gerek kalmaz, cunku gerecek bir fark kalmaz.
    kirpildi = None
    if fit == "cover" and h is not None:
        alan_orani = (w / 100 * slide_w) / (h / 100 * slide_h)
        kirpildi = _cover_crop(data, extension, alan_orani)
        if kirpildi:
            data = kirpildi[0]
        else:
            # Kirpilamadi (Pillow yok, gif, ya da bozuk dosya). SIGDIR --
            # germek, kimsenin dosya acilana kadar goremeyecegi bir bozulma.
            fit = "contain"

    # 1. bytes
    media_part = _media_part(pkg, data, extension)

    # 2. record
    asset = _register_media(pkg, data, name or source.name, MEDIA_TYPES[extension],
                            source=source, original=ham)

    # 3. relationship on the slide
    _link_media(pkg, part, media_part)

    # 4. the shape
    seed, seed_source = shapes.find_seed(pkg, "pic")
    shape = shapes.clone_shape(seed, name=name or source.stem)
    shape.set("assetG", asset)
    shapes.set_shape_slide_size(shape, slide_w, slide_h)

    pixels = image_size(data)
    # cover: kirpma orani zaten tutturdu, kalan fark yuvarlamadan ibaret --
    # alanin tamami verilir ki kapagin dibinde bir birimlik zemin serdi kalmasin.
    left, top, box_w, box_h = _fit_box(slide_w, slide_h, x, y, w, h,
                                       pixels, keep_ratio=fit == "contain")
    shapes.set_loc(shape, left, top, left + box_w, top + box_h)
    if behind:
        # Behind the text, but still in front of the painted ground -- sent all
        # the way back, a full-bleed picture would sit under the background
        # rectangle and never be seen.
        shapes.add_shape(root, shape, to_back=True)
        shapes.send_above_background(root, shape)
    else:
        shapes.add_shape(root, shape)
    pkg.replace_xml(part, root)

    return {
        "slide": slide,
        "image": source.name,
        "media_part": media_part,
        "asset_guid": asset,
        "md5": hashlib.md5(data).hexdigest(),
        "pixels": image_size(data),
        "fit": fit,
        # Kirpma RAPOR EDILIR: dosyanin bir kismi atildi ve bunu yalnizca
        # sonucu okuyan gorebilir -- slaytta "kirpildi" diye bir iz yok.
        "cropped": ({"from": list(image_size(source.read_bytes()) or []),
                     "to": list(kirpildi[1])} if kirpildi else None),
        "seed": f"pic ({seed_source})",
        "box_percent": {
            "x": round(left / slide_w * 100, 1), "y": round(top / slide_h * 100, 1),
            "w": round(box_w / slide_w * 100, 1), "h": round(box_h / slide_h * 100, 1),
        },
    }


# ------------------------------------------------------------------- video


def _boxes(data: bytes, start: int, end: int):
    """Walk one level of MP4 atoms: (kind, body offset, end offset)."""
    i = start
    while i + 8 <= end:
        size = struct.unpack(">I", data[i:i + 4])[0]
        kind = data[i + 4:i + 8]
        body = i + 8
        if size == 1:                      # 64-bit size follows the header
            size = struct.unpack(">Q", data[i + 8:i + 16])[0]
            body = i + 16
        elif size == 0:                    # runs to the end of the file
            size = end - i
        if size < 8 or i + size > end:
            return
        yield kind, body, i + size
        i += size


def _atom(data: bytes, path: list[bytes], start: int = 0,
          end: int | None = None) -> tuple[int, int] | None:
    end = len(data) if end is None else end
    for kind, body, stop in _boxes(data, start, end):
        if kind != path[0]:
            continue
        if len(path) == 1:
            return body, stop
        found = _atom(data, path[1:], body, stop)
        if found:
            return found
    return None


def _timescale(data: bytes, at: int) -> tuple[int, int]:
    """(timescale, duration) out of an mvhd or mdhd body."""
    if data[at] == 1:
        return (struct.unpack(">I", data[at + 20:at + 24])[0],
                struct.unpack(">Q", data[at + 24:at + 32])[0])
    return (struct.unpack(">I", data[at + 12:at + 16])[0],
            struct.unpack(">I", data[at + 16:at + 20])[0])


def mp4_info(data: bytes) -> dict:
    """Duration in ms, frame rate and pixel size, read out of the moov atom.

    Storyline records all three -- the <video> record holds the size, the
    shape's <movie> holds duration and frame rate -- and reads them from the
    file, so this reads the same places instead of asking the user to type
    numbers it can measure.

    Checked against the two videos in a real course, where Storyline's own
    figures sit in the file to compare against: 9500 ms / 24 fps / 1280x720
    and 10043 ms / 30 fps / 1920x1080. Both exact.
    """
    out: dict = {}
    moov = _atom(data, [b"moov"])
    if not moov:
        return out
    start, end = moov
    mvhd = _atom(data, [b"mvhd"], start, end)
    if mvhd:
        scale, duration = _timescale(data, mvhd[0])
        if scale:
            out["ms"] = int(round(duration / scale * 1000))

    for kind, body, stop in _boxes(data, start, end):
        if kind != b"trak":
            continue
        hdlr = _atom(data, [b"mdia", b"hdlr"], body, stop)
        if not hdlr or data[hdlr[0] + 8:hdlr[0] + 12] != b"vide":
            continue                       # audio and subtitle tracks have no size
        tkhd = _atom(data, [b"tkhd"], body, stop)
        if tkhd:
            at = tkhd[0] + (88 if data[tkhd[0]] == 1 else 76)
            out["pixels"] = (struct.unpack(">I", data[at:at + 4])[0] >> 16,
                             struct.unpack(">I", data[at + 4:at + 8])[0] >> 16)
        mdhd = _atom(data, [b"mdia", b"mdhd"], body, stop)
        stts = _atom(data, [b"mdia", b"minf", b"stbl", b"stts"], body, stop)
        if mdhd and stts:
            scale, duration = _timescale(data, mdhd[0])
            at = stts[0]
            entries = struct.unpack(">I", data[at + 4:at + 8])[0]
            samples = sum(
                struct.unpack(">I", data[at + 8 + i * 8:at + 12 + i * 8])[0]
                for i in range(entries))
            if scale and duration:
                out["fps"] = round(samples / (duration / scale), 3)
        break
    return out


def _flat_png(width: int, height: int, color: str) -> bytes:
    """A single-colour PNG, written by hand.

    It stands in for the poster frame Storyline extracts when it imports a
    video. Pulling a real frame would mean decoding H.264; a flat card of the
    right shape keeps thumbG pointing at something that exists, which is the
    part the file cares about.
    """
    rgb = bytes(int(color.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    raw = (b"\x00" + rgb * width) * height

    def chunk(tag: bytes, payload: bytes) -> bytes:
        body = tag + payload
        return (struct.pack(">I", len(payload)) + body
                + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def _register_video(pkg: StoryPackage, data: bytes, display_name: str,
                    source: Path, info: dict) -> str:
    """Add the <video> record and return its GUID."""
    story = pkg.parse(STORY_PART)
    media_list = _media_list(story)

    width, height = info.get("pixels") or (1280, 720)
    guid = new_guid()
    entry = ET.SubElement(media_list, "video")
    entry.set("g", guid)
    entry.set("verG", new_guid())
    entry.set("type", VIDEO_TYPES[source.suffix.lower()])
    entry.set("displayName", display_name)
    entry.set("origFile", str(source))
    entry.set("source", str(source))
    entry.set("useCnt", "0")
    entry.set("bytes", str(len(data)))
    entry.set("modDT", _mod_time(source))
    entry.set("addDT", datetime.now(timezone.utc).astimezone().isoformat())
    entry.set("hasClosedCaptions", "false")
    entry.set("as", "as3")
    entry.set("origModDt", _mod_time(source))
    entry.set("origBytes", str(len(data)))
    entry.set("compressedOnInsert", "false")
    ET.SubElement(entry, "langAltText")
    state = ET.SubElement(entry, "userState")
    state.set("w", str(width))
    state.set("h", str(height))
    checksum = ET.SubElement(entry, "md5Checksum")
    digest = hashlib.md5(data).hexdigest()
    ET.SubElement(checksum, "stream").text = digest
    ET.SubElement(checksum, "source").text = digest
    ET.SubElement(entry, "wordTimings")
    pkg.replace_xml(STORY_PART, story)
    return guid


def add_video(
    pkg: StoryPackage,
    slide: str,
    video: str | Path,
    *,
    x: float = 10,
    y: float = 25,
    w: float = 45,
    h: float | None = None,
    name: str | None = None,
    keep_ratio: bool = True,
    poster_color: str = POSTER_COLOR,
) -> dict:
    """Place a video file on a slide. x/y/w/h are percentages of the slide.

    The box keeps the film's own ratio, for the reason a picture does: a
    stretched frame is never reported and always noticed.
    """
    source = Path(video)
    if not source.is_file():
        raise StoryError(f"Video bulunamadi: {source}")
    extension = source.suffix.lower()
    if extension not in VIDEO_TYPES:
        raise StoryError(
            f"Desteklenmeyen video bicimi: {extension}. Kullanilabilir: "
            f"{', '.join(sorted(VIDEO_TYPES))}"
        )

    data = source.read_bytes()
    info = mp4_info(data)
    pixels = info.get("pixels")
    part = pkg.slide_part_for(slide)
    root = pkg.parse(part)
    slide_w, slide_h = shapes.slide_size(root)

    # 1. bytes -- under a .mpeg part name, which is what Storyline itself does
    media_part = _media_part(pkg, data, VIDEO_PART_EXT)

    # 2. record
    asset = _register_video(pkg, data, name or source.name, source, info)

    # 3. relationship on the slide
    _link_media(pkg, part, media_part)

    # 4. the poster thumbG points at, registered like any other picture
    poster_w = min(pixels[0] if pixels else 1280, 640)
    poster_h = (max(int(round(poster_w * pixels[1] / pixels[0])), 1) if pixels
                else int(poster_w * 9 / 16))
    poster = _flat_png(poster_w, poster_h, poster_color)
    poster_part = _media_part(pkg, poster, ".png")
    thumb = _register_media(pkg, poster, f"{source.stem}.png", "Png")
    _link_media(pkg, part, poster_part)

    # 5. the shape
    seed, seed_source = shapes.find_seed(pkg, "video")
    shape = shapes.clone_shape(seed, name=name or source.stem)
    shape.set("assetG", asset)
    shape.set("thumbG", thumb)
    # Each measured video shape carries its own ansG and nothing else in the
    # package refers to it; two shapes sharing one value would be the only
    # place in the file where that is not true.
    shape.set("ansG", new_guid())
    shapes.set_shape_slide_size(shape, slide_w, slide_h)

    duration = int(info.get("ms") or 0)
    movie = shape.find("movie")
    if movie is not None:
        if duration:
            movie.set("dur", str(duration))
        if info.get("fps"):
            movie.set("fps", str(int(round(info["fps"]))))
        size = movie.find("sz")
        if size is not None and pixels:
            size.set("w", str(pixels[0]))
            size.set("h", str(pixels[1]))
    # The timeline entry decides how much of the film plays. Left at the seed's
    # value, a longer video is cut off at the seed's length -- and nothing
    # reports it, because the file is perfectly valid either way.
    for ctx in shape.iter("vidTmCtx"):
        ctx.set("start", "0")
        ctx.set("assetStart", "0")
        if duration:
            ctx.set("dur", str(duration))

    left, top, box_w, box_h = _fit_box(slide_w, slide_h, x, y, w, h,
                                       pixels, keep_ratio)
    shapes.set_loc(shape, left, top, left + box_w, top + box_h)
    shapes.add_shape(root, shape)
    pkg.replace_xml(part, root)

    return {
        "slide": slide,
        "video": source.name,
        "media_part": media_part,
        "poster_part": poster_part,
        "asset_guid": asset,
        "thumb_guid": thumb,
        "md5": hashlib.md5(data).hexdigest(),
        "pixels": list(pixels) if pixels else None,
        "duration_ms": duration or None,
        "fps": info.get("fps"),
        "seed": f"video ({seed_source})",
        "box_percent": {
            "x": round(left / slide_w * 100, 1), "y": round(top / slide_h * 100, 1),
            "w": round(box_w / slide_w * 100, 1), "h": round(box_h / slide_h * 100, 1),
        },
    }
