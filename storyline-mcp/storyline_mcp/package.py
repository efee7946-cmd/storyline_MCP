"""The .story container.

A .story file is an OPC package -- the same ZIP + XML + _rels layout that
.pptx and .docx use. Parts are kept as raw bytes and copied through
byte-for-byte on save; only parts that were explicitly replaced get
re-serialised, so media and untouched XML keep their exact original encoding.
"""

from __future__ import annotations

import re
import shutil
import time
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


# "GUID YOK" degeri. BES KOPYAYDI (clone, compose, donors, model ve
# panel/dallanma) ve besi de ayni sabiti yaziyordu; `verify` altincisini
# isteyince en alt katmana tasindi -- bir degeri bir yer tanimlar.
#
# SAYI IKI KEZ DUZELTILDI ve ikisi de ayni hata: ilk sayim UCU buldu, cunku
# `grep`i `head -3` ile kesmistim -- kesilmis bir olcum TAM bir olcum gibi
# gorunuyor. Ikinci sayim panel'i "import etmiyor" diye disarida birakti;
# oysa `panel/dallanma.py` tam bu satiri import ediyordu. Ikincisi daha
# kotusu: sayiyi olcmedim, GEREKCE UYDURDUM.
NULL_GUID = "00000000-0000-0000-0000-000000000000"


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
            # AYNI KISITIN ACMA UCU. Yazma ucu `save`de (bkz. oradaki
            # "PAYLASIM IHLALI GECICIDIR" notu) ve aralarindaki fark
            # 2026-09-12'ye kadar SURDU: burada kisit KODLANMISTI, orada
            # yalnizca DUZYAZIYDI (`server.py` modul basligi: "Storyline
            # must be closed while a project is rewritten"). Bilinen bir
            # kisit dosya omrunun bir ucunda kodlanmissa, obur ucu
            # ARANMALI -- yoksa kullanicinin kursunu vuran hali orada
            # ham kalir.
            #
            # IKI UC AYNI SEYI YAPMIYOR ve yapmamali: okuma tarafinda
            # tekrar YOK, cunku okunamayan dosya ya Storyline'da acik
            # (kalici) ya da bir sonraki cagrida zaten okunur; yazma
            # tarafinda tekrar VAR, cunku `os.replace` GECICI bir
            # cekismede de dusuyor.
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

    def _fix_orphan_layouts(self) -> None:
        """Remap slide layoutG GUIDs that don't exist in story/slideLayouts/ to valid ones."""
        valid_layouts = {}
        default_guid = None
        quiz_guid = None

        for name in list(self._parts.keys()):
            if name.startswith("story/slideLayouts/") and name.endswith(".xml") and not "_rels" in name:
                try:
                    l_xml = ET.fromstring(self._parts[name])
                    g = l_xml.attrib.get("g")
                    l_name = l_xml.attrib.get("name") or ""
                    if g:
                        valid_layouts[g] = l_name
                        if not default_guid or "Title and Content" in l_name:
                            default_guid = g
                        if "Question" in l_name and not quiz_guid:
                            quiz_guid = g
                except Exception:
                    pass

        if not valid_layouts or not default_guid:
            return

        for sp in self.slide_parts:
            try:
                raw = self._parts[sp].decode("utf-8")
                match = re.search(r'layoutG="([^"]+)"', raw)
                if match:
                    lg = match.group(1)
                    if lg not in valid_layouts:
                        target_lg = quiz_guid if ("Quiz" in raw or "Intr" in raw) and quiz_guid else default_guid
                        raw = raw.replace(f'layoutG="{lg}"', f'layoutG="{target_lg}"')
                        self.replace_raw(sp, raw.encode("utf-8"))
            except Exception:
                pass

    # ----------------------------------------------------------------- save

    def save(self, out_path: str | Path, *, backup: bool = True) -> dict:
        """Write the package out. Writing over the source makes a .bak first."""
        out = Path(out_path)
        same = out.resolve() == self.path.resolve() if out.exists() else False
        backup_path = None
        if same and backup:
            backup_path = self.path.with_suffix(self.path.suffix + ".bak")
            shutil.copy2(self.path, backup_path)

        # Storyline requires every slide XML file to have a corresponding .rels file.
        minimal_rels = b'<?xml version="1.0" encoding="utf-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>'
        slide_parts = [n for n in list(self._parts.keys()) if n.startswith("story/slides/slide") and n.endswith(".xml") and not "_rels" in n]
        for sp in slide_parts:
            rels_part = f"story/slides/_rels/{sp.rsplit('/', 1)[1]}.rels"
            if rels_part not in self._parts:
                self.add_part(rels_part, minimal_rels)

        self._fix_orphan_layouts()

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
        # PAYLASIM IHLALI GECICIDIR, HATA DEGIL -- ve bu bir OLCUMDEN
        # cikti (2026-09-12). `tools/dusen_arguman.py` ayni yola 112 kez
        # yaziyor (~5 yazma/sn) ve suit icinde -- yani onceki sekiz
        # adimin `_canary`ye yuzlerce dosya yazmasinin ardindan -- iki
        # kosuda da su hatayla dustu:
        #
        #     PermissionError: [WinError 5] Erisim engellendi:
        #     'dusen_arguman_rail.story.tmp' -> 'dusen_arguman_rail.story'
        #
        # Tek basina kosunca HIC dusmuyordu. Windows'ta `os.replace`
        # hedef dosya baska bir surec tarafindan aciksa WinError 5 verir
        # ve o surec genelde virus tarayici / indeksleyicidir; dizin
        # mesgulken olasilik artiyor.
        #
        # DUZELTME KAPIDA DEGIL BURADA, cunku kusur kapiya ozgu degil:
        # kullanicinin kursunu tarayici bir an tuttugunda `save` hata
        # firlatiyor ve ajan "basarisiz" diyor -- oysa bir sonraki an
        # yazilabilir. Kisa, sinirli bir tekrar bunu kapatiyor.
        #
        # TEKRAR SONSUZ DEGIL: dosya GERCEKTEN kilitliyse (Storyline onu
        # acmis, ya da salt-okunur) hata yine firlar ve sebebini yazar.
        # Sessizce basarili donmek, duzeltmeye calistigi kayiptan kotu.
        son_hata = None
        for deneme in range(5):
            try:
                tmp.replace(out)
                son_hata = None
                break
            except PermissionError as exc:
                son_hata = exc
                time.sleep(0.1 * (2 ** deneme))      # 0.1 .. 1.6 sn
        if son_hata is not None:
            tmp.unlink(missing_ok=True)
            durum = lock_state(out)
            raise StoryError(
                f"{out.name} yazilamadi: dosyayi baska bir surec tutuyor "
                f"(5 denemede acilmadi). Kilit durumu: {durum}. "
                f"Storyline'da acik olabilir, ya da bir virus tarayici "
                f"dosyayi tariyor olabilir. Ayrinti: {son_hata}")

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

    # Every slide XML file must have a corresponding .rels file and valid layoutG
    names_set = set(names)
    valid_layout_guids = set()
    with zipfile.ZipFile(path) as z:
        for name in names:
            if name.startswith("story/slideLayouts/") and name.endswith(".xml") and not "_rels" in name:
                try:
                    l_xml = ET.fromstring(z.read(name))
                    g = l_xml.attrib.get("g")
                    if g: valid_layout_guids.add(g)
                except Exception:
                    pass

        for name in names:
            if name.startswith("story/slides/slide") and name.endswith(".xml") and not "_rels" in name:
                rels_name = f"story/slides/_rels/{Path(name).name}.rels"
                if rels_name not in names_set:
                    problems.append(f"{name}: Slide relationship (.rels) dosyasi eksik ({rels_name})")
                
                if valid_layout_guids:
                    try:
                        raw = z.read(name).decode("utf-8")
                        match = re.search(r'layoutG="([^"]+)"', raw)
                        if match and match.group(1) not in valid_layout_guids:
                            problems.append(f"{name}: Gecerli olmayan layoutG ('{match.group(1)}')")
                    except Exception:
                        pass

    # assetG COZULUYOR MU -- `layoutG` kontrolunun ESI.
    #
    # KISIT BIR UCTA KODLUYDU. Yukaridaki satirlar "var olmayan bir kaydi
    # gosteren referans" sinifini layout icin kapatiyor. Ayni sinifin
    # MEDYA ucu yalnizca duzyazida duruyordu (`media._media_list`in
    # basligi): kayit yanlis listeye girdiginde paket GECERLI kaliyor,
    # `verify` TEMIZ geciyor, bag zinciri md5'e kadar izlenebiliyor --
    # ama Storyline gorseli hic gostermiyor ("The image can't be
    # displayed"). Kullanici bunu IKI ayri kursta bildirdi; kapali olan
    # uc layout'tu, isiran uc buydu.
    #
    # KAPSAM OLCULDU, HAYAL EDILMEDI (2026-09-12): alti bagisci projesi
    # ve `test/bos.story`de medya kaydini gosteren 51 referansin 51'i
    # `assetG`; etiketler `<pic>` (46) ve `<char>` (5). Yani kontrol
    # etikete DEGIL oznitelik adina bakiyor -- `char` gibi bugun
    # aklimiza gelmeyen bir etiket de kapsamda kalsin diye.
    # `thumbG` (video afisi) DISARIDA: bagiscilarin hicbirinde video yok,
    # yani o referansin kaydi gosterip gostermedigi OLCULMEDI.
    #
    # COZUCU YAZANIN COZUCUSU: kayitlarin hangi listede durdugunu
    # `media._media_list` biliyor (`mediaLst > mediaLst`, dort gercek
    # kursta olculmus). Burada ikinci bir kopya yazmak iki uygulamayi
    # ayristirirdi. Bedeli bir KOR NOKTA: `_media_list` yanlis listeyi
    # secseydi yazan da kontrol de birlikte yanilirdi -- o yuzden
    # `tools/medya_kapi.py` kaydi DISTAKI listeye tasiyip bu kontrolun
    # kizardigini ayrica kanitliyor.
    from .media import _media_list          # dairesel import: yerel kalmali

    kayitli: set[str] = set()
    # DISTAKI liste ayrica tutuluyor, cunku IKI HAL var ve insan
    # tarafindaki eylemleri AYRI. Kontrol "cozulmuyor" demekle yetinse
    # okuyan hangi halde oldugunu bilemez -- ve bu iki halden biri
    # kaydin DURDUGU hal.
    distaki: set[str] = set()
    try:
        with zipfile.ZipFile(path) as z:
            story = ET.fromstring(z.read("story/story.xml"))
        ic = _media_list(story)
        kayitli = {(m.get("g") or "") for m in ic}
        kayitli.discard("")
        dis = story.find("mediaLst")
        distaki = {(m.get("g") or "") for m in (dis if dis is not None else [])
                   if m is not ic and m.tag != "mediaLst"} - kayitli
        distaki.discard("")
    except (KeyError, ET.ParseError, StoryError):
        kayitli = set()                     # paketin baska bir kusuru var

    kopuk: list[tuple[str, str, str, str]] = []
    if kayitli:
        with zipfile.ZipFile(path) as z:
            for name in names:
                if not name.endswith(".xml"):
                    continue
                try:
                    root = ET.fromstring(z.read(name))
                except ET.ParseError:
                    continue                # yukarida zaten raporlandi
                for el in root.iter():
                    asset = el.get("assetG")
                    if not asset or asset == NULL_GUID or asset in kayitli:
                        continue
                    kopuk.append((name, el.tag, el.get("name") or "", asset))

    # RED, SIRADAKI ISI SOYLUYOR -- arac adi vermek zorunda degil.
    #
    # `compose_slide`in reddinin degeri bir arac adi vermesi degildi,
    # okuyanin SIRADA NE OLDUGUNU bilmesiydi. Burada sirada olan sey
    # insan tarafinda ve makine gerektirmiyor: Storyline'da acip gorseli
    # yeniden eklemek. Kalibi `puanlama.zincir`in 3c kosulu: "arac
    # bunlari SILMEZ, once neyi gosterdigi bilinmeli" -- arac yok, ama
    # okuyan halini ve neden otomatik bir hamle olmadigini biliyor.
    #
    # CARE TEK SATIRDA, ILK BULGUNUN YANINDA. `save` yalnizca ilk uc
    # sorunu birlestiriyor; her satira ayni tarifi yazmak reddi uzatir ve
    # okunmaz kilar.
    for sira, (name, tag, ad, asset) in enumerate(kopuk):
        kim = f"{ad!r} " if ad else ""
        nerede = ("kayit DISTAKI listede duruyor" if asset in distaki
                  else "kayit hicbir listede yok")
        satir = (f"{name}: {kim}<{tag}> assetG'si cozulmuyor "
                 f"('{asset}') -- {nerede}")
        if sira == 0:
            ne_yapmali = (
                "Kayit DURUYOR ama Storyline ICTEKI listeden okuyor "
                "(`mediaLst > mediaLst`); arac kaydi kendi TASIMAZ, cunku "
                "hangi gorsele ait oldugu buradan gorunmez."
                if asset in distaki else
                "Kaydi arac kendi KURAMAZ: gorselin baytlari, md5'i ve "
                "kaynak dosya bilgisi kayitta duruyor ve hicbiri buradan "
                "turetilemez.")
            satir += (f". Paket gecerli kalir, Storyline gorseli GOSTERMEZ "
                      f"(toplam {len(kopuk)} sekil). {ne_yapmali} SIRADAKI "
                      f"IS INSAN TARAFINDA: kursu Storyline'da acip bu "
                      f"sekli silin ve gorseli yeniden ekleyin.")
        problems.append(satir)

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
