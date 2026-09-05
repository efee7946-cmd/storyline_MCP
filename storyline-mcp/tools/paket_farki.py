"""Iki .story paketini YAPISAL olarak karsilastir: verify()'in bakmadigi yerler.

verify() dort sey soruyor: BOM var mi, XML ayrisiyor mu, slayt .rels'i var mi,
layoutG gecerli mi. Storyline bunlarin hepsi saglanmisken de dosyayi
reddedebiliyor -- yani reddin sebebi bu dortlunun DISINDA. Bu sonda o disariyi
tariyor: paket sozlesmesinin verify()'in hic sormadigi kisimlarini.

Kullanim:
    python tools/paket_farki.py SUPHELI.story [TABAN.story]
"""

from __future__ import annotations

import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

CT = "[Content_Types].xml"
CT_NS = "{http://schemas.openxmlformats.org/package/2006/content-types}"
REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def incele(path: Path) -> dict:
    """Bir paketi ac ve sozlesmesini cikar. Yorum yok, sadece olcum."""
    rapor: dict = {"dosya": path.name, "sorunlar": []}
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        rapor["girdi_sayisi"] = len(names)

        # 1. YINELENEN GIRDI. Zip ayni adi iki kez tasiyabilir; okuyucu
        # hangisini aldigini soylemez. verify() namelist uzerinde donuyor ve
        # ikisini de "gecerli" sayiyor.
        tekrar = [n for n, c in Counter(names).items() if c > 1]
        if tekrar:
            rapor["sorunlar"].append(f"yinelenen zip girdisi: {tekrar[:5]}")
        rapor["yinelenen"] = len(tekrar)

        # 2. CONTENT TYPES KAPSAMI. Beyan edilmemis bir uzanti, paketi
        # acilmaz yapar; verify() bu dosyaya hic bakmiyor.
        if CT not in names:
            rapor["sorunlar"].append(f"{CT} YOK")
            rapor["ct_default"] = rapor["ct_override"] = 0
        else:
            ct = ET.fromstring(z.read(CT))
            defaults = {d.attrib["Extension"].lower()
                        for d in ct.findall(f"{CT_NS}Default")}
            overrides = {o.attrib["PartName"].lstrip("/")
                         for o in ct.findall(f"{CT_NS}Override")}
            rapor["ct_default"] = len(defaults)
            rapor["ct_override"] = len(overrides)
            kapsamsiz = []
            for n in names:
                if n.endswith("/") or n == CT:
                    continue
                # `.rels` gibi noktayla BASLAYAN adlarda Path.suffix bos
                # doner (gizli dosya kurali). Uzantiyi elle al: aksi
                # halde saglam bir pakette `_rels/.rels` "kapsamsiz"
                # gorunur -- olculdu, taban dosyada yanlis alarm verdi.
                ad = Path(n).name
                ext = ad.rsplit(".", 1)[-1].lower() if "." in ad else ""
                if n not in overrides and ext not in defaults:
                    kapsamsiz.append(n)
            rapor["ct_kapsamsiz"] = len(kapsamsiz)
            if kapsamsiz:
                rapor["sorunlar"].append(
                    f"content-types kapsaminda olmayan {len(kapsamsiz)} parca: "
                    f"{kapsamsiz[:5]}")
            # Override edilmis ama pakette olmayan parca
            hayalet = sorted(o for o in overrides if o not in names)
            rapor["ct_hayalet"] = len(hayalet)
            if hayalet:
                rapor["sorunlar"].append(
                    f"content-types'ta beyan edilip pakette OLMAYAN "
                    f"{len(hayalet)} parca: {hayalet[:5]}")

        # 3. ILISKI HEDEFLERI. Bir .rels dosyasi var olmayan bir parcaya
        # isaret ediyorsa Storyline yuklenirken kirilir. verify() yalnizca
        # .rels'in VAR OLDUGUNA bakiyor, icindekilerin cozulup cozulmedigine
        # degil.
        kirik = []
        rels_sayisi = 0
        for n in names:
            if not n.endswith(".rels"):
                continue
            rels_sayisi += 1
            taban = Path(n).parent.parent  # _rels/x.rels -> x'in klasoru
            try:
                kok = ET.fromstring(z.read(n))
            except ET.ParseError as exc:
                kirik.append(f"{n}: ayrismadi ({exc})")
                continue
            for r in kok.findall(f"{REL_NS}Relationship"):
                if r.attrib.get("TargetMode") == "External":
                    continue
                hedef = r.attrib.get("Target", "")
                if not hedef or hedef.startswith(("http://", "https://")):
                    continue
                cozum = (taban / hedef).as_posix().replace("/./", "/")
                while "/../" in cozum:
                    once, sonra = cozum.split("/../", 1)
                    cozum = str(Path(once).parent.as_posix()) + "/" + sonra
                cozum = cozum.lstrip("/")
                if cozum not in names:
                    kirik.append(f"{n} -> {hedef} (cozum: {cozum})")
        rapor["rels_sayisi"] = rels_sayisi
        rapor["kirik_iliski"] = len(kirik)
        if kirik:
            rapor["sorunlar"].append(
                f"hedefi pakette olmayan {len(kirik)} iliski: {kirik[:5]}")

        # 3b. BOS SLAYT ILISKISI. save() eksik bir slayt .rels'i gordugunde
        # yerine ICI BOS bir Relationships parcasi koyuyor. verify() bundan
        # sonra ".rels var" deyip geciyor -- ama bos bir iliski listesi,
        # slaytin duzenine/medyasina giden BAGIN OLMADIGI anlamina gelir.
        # Kontrolu memnun eden sey, dosyayi acilir yapan sey degil.
        bos_rels = []
        for n in names:
            if not (n.startswith("story/slides/_rels/") and n.endswith(".rels")):
                continue
            try:
                kok = ET.fromstring(z.read(n))
            except ET.ParseError:
                continue
            if len(kok.findall(f"{REL_NS}Relationship")) == 0:
                bos_rels.append(n)
        rapor["bos_slayt_rels"] = len(bos_rels)
        rapor["bos_slayt_rels_adlar"] = bos_rels
        if bos_rels:
            rapor["sorunlar"].append(
                f"ICI BOS slayt iliski dosyasi ({len(bos_rels)} adet): "
                f"{[Path(x).name for x in bos_rels][:8]}")

        # 4. KOK ILISKI. _rels/.rels olmadan paket girisi yoktur.
        if "_rels/.rels" not in names:
            rapor["sorunlar"].append("_rels/.rels YOK (paketin girisi yok)")

        # 5. SIKISTIRMA/ISIM ANOMALILERI. Ters bolu veya mutlak yol tasiyan
        # girdi, zip sozlesmesini bozar.
        tuhaf = [n for n in names if "\\" in n or n.startswith("/")]
        rapor["tuhaf_isim"] = len(tuhaf)
        if tuhaf:
            rapor["sorunlar"].append(f"tuhaf girdi adi: {tuhaf[:5]}")

    rapor["ok"] = not rapor["sorunlar"]
    return rapor


def yaz(r: dict) -> None:
    isaret = "OK " if r["ok"] else "!! "
    print(f"{isaret}{r['dosya']}")
    print(f"    girdi={r['girdi_sayisi']}  rels={r['rels_sayisi']}  "
          f"ct_default={r['ct_default']}  ct_override={r['ct_override']}")
    print(f"    ct_kapsamsiz={r.get('ct_kapsamsiz', '?')}  "
          f"ct_hayalet={r.get('ct_hayalet', '?')}  "
          f"kirik_iliski={r['kirik_iliski']}  yinelenen={r['yinelenen']}  "
          f"bos_slayt_rels={r.get('bos_slayt_rels', '?')}")
    for s in r["sorunlar"]:
        print(f"    - {s}")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    for raw in sys.argv[1:]:
        yaz(incele(Path(raw).resolve()))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
