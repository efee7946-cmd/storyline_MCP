"""The .story container.

A .story file is an OPC package -- the same ZIP + XML + _rels layout that
.pptx and .docx use. Parts are kept as raw bytes and copied through
byte-for-byte on save; only parts that were explicitly replaced get
re-serialised, so media and untouched XML keep their exact original encoding.
"""

from __future__ import annotations

import re
import shutil
import struct
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

# Central directory record: signature, and the offset of external_attr within it.
CD_SIGNATURE = b"PK\x01\x02"
CD_EXTERNAL_ATTR = 38
STORYLINE_EXTERNAL_ATTR = 0

XML_DECL = b'<?xml version="1.0" encoding="utf-8" standalone="yes"?>'

# Storyline writes every XML and .rels part with a UTF-8 byte-order mark and
# refuses a package where one is missing -- "This project is invalid or corrupt
# and cannot be opened." Python's XML parser ignores a BOM entirely, so a part
# stripped of it still parses perfectly and passes any check built on parsing.
# The mark therefore has to be preserved deliberately, and verified explicitly.
BOM = b"\xef\xbb\xbf"

STORY_PART = "story/story.xml"
STORY_RELS = "story/_rels/story.xml.rels"
SLIDE_RE = re.compile(r"^story/slides/slide[^/]*\.xml$")


class StoryError(RuntimeError):
    pass


def lock_state(path: str | Path) -> str:
    """How usable a .story file is right now: 'free', 'readonly' or 'locked'.

    Storyline opens the project it is editing with no sharing at all -- every
    access mode is refused, so the file cannot even be read. Crucially it locks
    only *that* file: other courses stay fully readable and writable while the
    app runs.

    So "is Storyline.exe running?" is the wrong question. It blocks work on
    every other project for no reason, which is the difference between a guard
    and an obstacle. The right question is whether this particular file is
    held.
    """
    target = Path(path)
    if not target.is_file():
        return "free"
    try:
        with open(target, "r+b"):
            return "free"
    except PermissionError:
        pass
    except OSError:
        return "free"
    try:
        with open(target, "rb"):
            return "readonly"
    except OSError:
        return "locked"


class StoryPackage:
    """In-memory, order-preserving view of a .story package."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.is_file():
            raise StoryError(f"Dosya bulunamadi: {self.path}")
        self._order: list[str] = []
        self._parts: dict[str, bytes] = {}
        self._infos: dict[str, zipfile.ZipInfo] = {}
        self._dirty: set[str] = set()
        try:
            with zipfile.ZipFile(self.path) as z:
                for info in z.infolist():
                    self._order.append(info.filename)
                    self._parts[info.filename] = z.read(info.filename)
                    self._infos[info.filename] = info
        except zipfile.BadZipFile as exc:
            raise StoryError(
                f"{self.path.name} gecerli bir .story paketi degil (ZIP acilamadi)."
            ) from exc
        except PermissionError as exc:
            raise StoryError(
                f"{self.path.name} su anda kilitli, okunamiyor. Bu dosya "
                f"Storyline'da acik olmali; kapatip tekrar deneyin. "
                f"(Storyline acik kalabilir, yeter ki bu proje kapali olsun.)"
            ) from exc
        if STORY_PART not in self._parts:
            raise StoryError(f"{self.path.name} icinde {STORY_PART} yok.")

    # ---------------------------------------------------------------- parts

    def read(self, part: str) -> bytes:
        try:
            return self._parts[part]
        except KeyError:
            raise StoryError(f"Pakette bulunmayan parca: {part}") from None

    def parse(self, part: str) -> ET.Element:
        return ET.fromstring(self.read(part))

    def replace_xml(self, part: str, root: ET.Element) -> None:
        """Re-serialise one XML part with Storyline's byte prelude."""
        body = ET.tostring(root, encoding="utf-8", xml_declaration=False)
        self._parts[part] = BOM + XML_DECL + body
        self._dirty.add(part)

    def replace_raw(self, part: str, data: bytes) -> None:
        """Replace a part with exact bytes.

        Preferred over replace_xml for namespaced parts ([Content_Types].xml,
        *.rels): round-tripping those through ElementTree rewrites the default
        namespace into ns0: prefixes and drops the byte-order mark.
        """
        if part not in self._parts:
            raise StoryError(f"Pakette bulunmayan parca: {part}")
        self._parts[part] = data
        self._dirty.add(part)

    def add_part(
        self, part: str, data: bytes, *, after: str | None = None, like: str | None = None
    ) -> None:
        """Add a new part, optionally right behind an existing one.

        `like` names an existing part whose ZIP conventions the new one should
        copy -- compression method above all, since Storyline stores some parts
        uncompressed and a new part written differently from its siblings does
        not match the package it joins.
        """
        if part in self._parts:
            raise StoryError(f"Parca zaten var: {part}")
        if after and after in self._order:
            self._order.insert(self._order.index(after) + 1, part)
        else:
            self._order.append(part)
        self._parts[part] = data
        self._dirty.add(part)
        template = self._infos.get(like or after or "")
        if template is not None:
            self._infos[part] = self._clone_info(template, part)

    @staticmethod
    def _clone_info(template: zipfile.ZipInfo, name: str) -> zipfile.ZipInfo:
        info = zipfile.ZipInfo(name, date_time=template.date_time)
        info.compress_type = template.compress_type
        info.create_system = template.create_system
        info.create_version = template.create_version
        info.extract_version = template.extract_version
        info.external_attr = template.external_attr
        info.internal_attr = template.internal_attr
        info.flag_bits = template.flag_bits
        return info

    def has_part(self, part: str) -> bool:
        return part in self._parts

    @property
    def dirty_parts(self) -> list[str]:
        return sorted(self._dirty)

    @property
    def slide_parts(self) -> list[str]:
        """Slide parts in the package's own order (not scene order)."""
        return [n for n in self._order if SLIDE_RE.match(n)]

    def slide_part_for(self, name: str) -> str:
        """Resolve a slide by part path, file name, or the title it displays.

        Callers describe slides the way they see them -- "Intro Slide" in the
        outline, not "slide.xml" -- so accepting the name avoids a failed call
        and a retry every time.
        """
        if name in self._parts:
            return name
        candidate = f"story/slides/{name}"
        if candidate in self._parts:
            return candidate
        if not name.endswith(".xml"):
            candidate = f"story/slides/{name}.xml"
            if candidate in self._parts:
                return candidate

        wanted = name.casefold().strip()
        for part in self.slide_parts:
            title = (ET.fromstring(self._parts[part]).get("name") or "").casefold().strip()
            if title and title == wanted:
                return part
        raise StoryError(
            f"Slayt bulunamadi: {name}. list_slides ile dosya adlarini gorebilirsiniz."
        )

    # ----------------------------------------------------------------- save

    def save(self, out_path: str | Path, *, backup: bool = True) -> dict:
        """Write the package out. Writing over the source makes a .bak first."""
        out = Path(out_path)
        same = out.resolve() == self.path.resolve() if out.exists() else False
        backup_path = None
        if same and backup:
            backup_path = self.path.with_suffix(self.path.suffix + ".bak")
            shutil.copy2(self.path, backup_path)

        repaired = self._normalise_boms()

        tmp = out.with_suffix(out.suffix + ".tmp")
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            for name in self._order:
                z.writestr(self._entry_info(name), self._parts[name])
        self._restore_external_attrs(tmp)

        # DOGRULAMA YERINE KOYMADAN ONCE, ve sonucu bir KAPIYA bagli.
        #
        # Onceden sira sooyleydi: tmp.replace(out) -> verify(out) -> raporu
        # DONDUR. Yani dogrulama kosuyordu, sorunu buluyordu, `ok: false`
        # yaziyordu ve kimse bakmiyordu -- bozuk paket diske yazilmis
        # halde kaliyordu. Olculdu: JS koduna bir 0x00 konunca dosya
        # okunamaz hale geliyor, `save` hicbir sey soylemiyor, ve geriye
        # donusu olmayan tek sey diskteki dosya oluyordu.
        #
        # Kontrolun kendisi dogruydu; eksik olan verdiktin bir kapiya
        # baglanmasiydi. Simdi dogrulama `tmp` uzerinde kosuyor ve sorun
        # varsa `tmp` silinip hata veriliyor: hedef dosya HIC dokunulmamis
        # kaliyor, .bak da yerinde duruyor.
        report = verify(tmp)
        if not report.get("ok"):
            tmp.unlink(missing_ok=True)
            raise StoryError(
                "Yazilan paket dogrulamayi gecemedi, dosyaya DOKUNULMADI: "
                + "; ".join(report.get("problems", [])[:3])
            )
        tmp.replace(out)

        return {
            "written": str(out),
            "backup": str(backup_path) if backup_path else None,
            "parts_rewritten": self.dirty_parts,
            "bom_repaired": repaired,
            "verified": report,
        }

    def _restore_external_attrs(self, path: Path) -> int:
        """Stamp Storyline's external_attr onto every central directory record.

        Python's zipfile treats external_attr == 0 as "not set" and quietly
        substitutes 0o600 << 16, so the value Storyline uses cannot survive a
        round trip through its API. The field exists only in the central
        directory, at a fixed offset per record, so it is written afterwards
        without touching a byte of file data.

        The value is fixed rather than copied from the input, for the same
        reason the BOM is. A project already rewritten by a broken build
        carries the wrong attribute on every entry, and "restore what was
        there" would faithfully restore the damage. Every entry of every
        Storyline-written package measured here -- 178 of them, media
        included -- has 0.
        """
        raw = bytearray(path.read_bytes())
        at = raw.find(CD_SIGNATURE)
        patched = 0
        while at != -1:
            name_len, extra_len, comment_len = struct.unpack_from("<HHH", raw, at + 28)
            struct.pack_into("<I", raw, at + CD_EXTERNAL_ATTR, STORYLINE_EXTERNAL_ATTR)
            patched += 1
            at = raw.find(CD_SIGNATURE, at + 46 + name_len + extra_len + comment_len)
        path.write_bytes(bytes(raw))
        return patched

    def _entry_info(self, name: str) -> zipfile.ZipInfo:
        """Rebuild a part's ZIP entry exactly as the original package had it.

        The container is part of the format, not packaging noise. Storyline
        writes some parts uncompressed -- [Content_Types].xml, _rels/.rels and
        the core-properties .psmdcp -- and passing a bare filename to writestr
        would deflate all three, while also stamping a different create_version
        and external_attr on every entry. Reusing the original ZipInfo keeps
        the rewritten package a faithful copy of the one Storyline produced.
        """
        template = self._infos.get(name)
        if template is None:
            return zipfile.ZipInfo(name)
        return self._clone_info(template, name)

    def _normalise_boms(self) -> list[str]:
        """Guarantee the UTF-8 BOM on every XML part before writing.

        Merely *preserving* whatever the input had is not enough. A project
        damaged by an earlier write arrives with parts already missing their
        mark, and a writer that mirrors what it finds carries the damage
        forward faithfully -- the file stays unopenable no matter how many
        times it is saved. Storyline puts a BOM on every XML and .rels part it
        writes, without exception, so the writer guarantees it rather than
        copying it. Damaged projects then heal on the next save.
        """
        repaired: list[str] = []
        for name in self._order:
            if not name.endswith((".xml", ".rels")):
                continue
            data = self._parts[name]
            if not data.startswith(BOM):
                self._parts[name] = BOM + data
                repaired.append(name)
        return repaired


def verify(path: str | Path) -> dict:
    """Re-open a written package and check it the way Storyline would.

    Parsing alone is not enough. A part can be flawless XML and still be
    rejected, because Storyline also requires the UTF-8 BOM that its own writer
    emits. Checking only "does it parse?" is checking a weaker condition than
    the one that actually decides whether the file opens, so the mark is
    verified too -- against the package's own convention rather than a rule
    assumed in advance.
    """
    problems: list[str] = []
    parts = 0
    with_bom = 0
    without_bom: list[str] = []
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        for name in names:
            if not name.endswith(".xml") and not name.endswith(".rels"):
                continue
            parts += 1
            data = z.read(name)
            if data.startswith(BOM):
                with_bom += 1
            else:
                without_bom.append(name)
            try:
                ET.fromstring(data)
            except ET.ParseError as exc:
                problems.append(f"{name}: {exc}")

    # If the package overwhelmingly uses BOMs, the odd part without one is a
    # part we wrote and broke -- not a deck that never used them.
    if with_bom and without_bom and with_bom >= len(without_bom):
        for name in without_bom:
            problems.append(f"{name}: UTF-8 BOM eksik (Storyline paketi reddeder)")

    return {
        "ok": not problems,
        "xml_parts_checked": parts,
        "xml_parts_with_bom": with_bom,
        "total_entries": len(names),
        "problems": problems,
    }
