"""B1'in kalan üç bilinmeyeni, tek karede.

Sirayla, cunku birbirlerine bagliler:

  1. BOS SATIR yuksekligi. Model bos paragrafi TAM satir sayiyor; gercekte
     belirgin sekilde kisa ciziliyor (17 paragrafli bir metin 782 birim
     cizildi, hepsi dolu sayilsaydi 1457 ederdi). Referanstaki 24 tasma
     adayinin 10'u tam olarak bu.

  2. SARMA. MEASURE_LEADING=1.785 SERT satir sonlariyla olculdu -- gizli
     bagimliligi kaldirmak icin dogruydu, ama sonuc yalnizca sert kirilim
     icin gecerli. Gercek kutular SARIYOR. Satir basina karakter tahmini
     %20 saparsa satir sayisi sapar ve leading kalibrasyonu bunu kurtarmaz.

  3. KALAN IKI ADAY. Referansta ayrilmamis iki tasma, ikisi de slidee'de,
     ikisi de sarma yapiyor ve Turkce diakritik tasiyor -- yani (2) ile
     ayni yere bakiyorlar.

OLCUM YONTEMI HER UCUNDE AYNI ve girdi spesifikasyonundan okunur:
sert satir sonlari SAYILIR, sarma kutusunda satirlar KAREDE sayilir.
Hicbiri measured_text_height'a sormuyor -- sinanan sey o.

    python tools/goz_kalibre.py
"""

from __future__ import annotations

import shutil
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from storyline_mcp import compose, model, shapes
from storyline_mcp.authoring import _apply_text
from storyline_mcp.package import StoryPackage

REF = ROOT.parent / "test" / "_referans" / "referans.story"
OUT = ROOT.parent / "test" / "_referans" / "KALIBRE2.story"

PUNTO = 12.0
# 1a: alti DOLU satir, bos yok -> L (dolu satir yuksekligi) dogrulanir.
DOLU6 = "\n".join(f"D{i}" for i in range(1, 7))
# 1b: dort dolu + uc BOS, aralarina serpistirilmis -> B (bos satir) cikar.
#     H(1b) = 4L + 3B, L 1a'dan biliniyor.
BOSLU = "B1\n\nB2\n\nB3\n\nB4"
# 2: TEK paragraf, sert kirilim YOK, bilinen genislikte -> satirlar karede
#    sayilir ve modelin ongordugu satir sayisiyla karsilastirilir.
SARMA_GEN = 300.0
SARMA = ("Bu paragrafta hic sert satir sonu yoktur ve kutunun genisligi "
         "bilindigi icin kac satira sardigi karede sayilarak olculebilir "
         "boylece karakter genisligi tahmini dogrulanir")


def _kutu(pkg, part, ad, metin, x, y, gen, yuk, punto=PUNTO):
    root = pkg.parse(part)
    sw, sh = shapes.slide_size(root)
    box = shapes.clone_shape(shapes.find_seed(pkg, "textBox")[0], name=ad)
    shapes.set_shape_slide_size(box, sw, sh)
    shapes.set_loc(box, x, y, x + gen, y + yuk)
    shapes.set_text_flow(box, vertical="t", grow=False)
    box.set("autoFit", "none")
    box.set("wrap", "true")
    shapes.add_shape(root, box)
    _apply_text(root, box, metin, color="#000000", size=punto)
    pkg.replace_xml(part, root)


def _etiket(pkg, part, ad, metin, x, y, gen):
    root = pkg.parse(part)
    sw, sh = shapes.slide_size(root)
    lbl = shapes.clone_shape(shapes.find_seed(pkg, "textBox")[0], name=ad)
    shapes.set_shape_slide_size(lbl, sw, sh)
    shapes.set_loc(lbl, x, y, x + gen, y + 14)
    shapes.set_text_flow(lbl, vertical="t", grow=False)
    lbl.set("autoFit", "none")
    shapes.add_shape(root, lbl)
    _apply_text(root, lbl, metin, color="#B00000", size=8)
    pkg.replace_xml(part, root)


def main() -> int:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        kaynak = StoryPackage(REF)
        # Kalan iki aday: gercek sekiller, gercek kutulariyla.
        adaylar = []
        for part, ref in model.slide_index(kaynak).items():
            if ref.basename != "slidee.xml":
                continue
            root = kaynak.parse(part)
            for el in root.iter():
                r = shapes.shape_rect(el)
                t = model.shape_text(root, el.get("g") or "").strip()
                # METINLE FILTRELEME YOK. Ilk surumde "IN" in t.upper()
                # yaziyordu ve Turkce buyuk harf tuzagina dustu: metin
                # "ICIN" degil "ICIN" -- I noktali, eslesmedi ve filtre
                # SIFIR aday dondu. Kutu olcusu ile secmek daha saglam.
                if r and t and 45 < r[3] - r[1] < 110 and shapes.wraps(el):
                    adaylar.append((el, r, t))
        adaylar = adaylar[:2]
        print(f"kalan aday: {len(adaylar)}")
        for _el, r, t in adaylar:
            print(f"  kutu {r[2]-r[0]:.0f}x{r[3]-r[1]:.0f}  {t[:34]!r}")

        shutil.copy2(REF, OUT)
        pkg = StoryPackage(OUT)
        hedef = next((p, rf) for p, rf in model.slide_index(pkg).items()
                     if abs(shapes.slide_size(pkg.parse(p))[0] - 720.0) < 1)
        part, ref = hedef

        root = pkg.parse(part)
        compose.clear_slide(root)
        sw, sh = shapes.slide_size(root)
        zemin = shapes.clone_shape(shapes.find_seed(pkg, "rect")[0], name="Zemin")
        shapes.set_shape_slide_size(zemin, sw, sh)
        shapes.set_loc(zemin, 0, 0, sw, sh)
        shapes.set_fill(zemin, "#FFFFFF")
        shapes.add_shape(root, zemin, to_back=True)
        _apply_text(root, zemin, "")
        pkg.replace_xml(part, root)

        _etiket(pkg, part, "E_A", "A) 6 DOLU satir (bos yok)", 25, 18, 300)
        _kutu(pkg, part, "K_A", DOLU6, 25, 34, 260, 140)

        _etiket(pkg, part, "E_B", "B) 4 dolu + 3 BOS satir", 25, 190, 300)
        _kutu(pkg, part, "K_B", BOSLU, 25, 206, 260, 140)

        _etiket(pkg, part, "E_C",
                f"C) SARMA: tek paragraf, kutu {SARMA_GEN:.0f} birim",
                25, 362, 320)
        _kutu(pkg, part, "K_C", SARMA, 25, 378, SARMA_GEN, 140)

        for i, (el, r, t) in enumerate(adaylar):
            y = 34 + i * 200
            _etiket(pkg, part, f"E_D{i}",
                    f"D{i+1}) KALAN ADAY: kutu {r[3]-r[1]:.0f} birim",
                    400, y - 16, 300)
            kopya = shapes.clone_shape(el, name=f"K_D{i}", keep_triggers=False)
            root2 = pkg.parse(part)
            shapes.set_shape_slide_size(kopya, sw, sh)
            shapes.set_loc(kopya, 400, y, 400 + (r[2] - r[0]), y + (r[3] - r[1]))
            shapes.add_shape(root2, kopya)
            pkg.replace_xml(part, root2)

        story = pkg.parse("story/story.xml")
        story.set("pG", ref.scene_guid)
        sahne_lst = story.find("sceneLst")
        for s in list(sahne_lst):
            if s.get("g") == ref.scene_guid:
                sahne_lst.remove(s)
                sahne_lst.insert(0, s)
                id_lst = s.find("sldIdLst")
                rels = {v: k for k, v in model._rel_map(pkg).items()}
                rid = rels.get(part)
                for el2 in list(id_lst or []):
                    if (el2.text or "").strip() == rid:
                        id_lst.remove(el2)
                        id_lst.insert(0, el2)
                break
        pkg.replace_xml("story/story.xml", story)
        rapor = pkg.save(OUT, backup=False)

    per = max(1, int(SARMA_GEN / (PUNTO * shapes.CHAR_WIDTH_RATIO)))
    print(f"\nuretildi: {OUT.name}  verified={rapor['verified']['ok']}")
    print(f"  slayt {ref.basename} ({sw:.0f}x{sh:.0f}), kursun ILK slaydi")
    print("\nGIRDI SPESIFIKASYONU (model sorulmadi):")
    print(f"  A: {DOLU6.count(chr(10))+1} dolu satir, bos YOK")
    print(f"  B: 4 dolu + 3 bos satir")
    print(f"  C: tek paragraf {len(SARMA)} harf, kutu {SARMA_GEN:.0f} birim")
    print(f"\nMODELIN ONGORUSU (karede sayilanla karsilastirilacak):")
    print(f"  C: {per} karakter/satir -> {shapes._wrapped_lines(SARMA, per)} satir")
    print("\nOLCULECEK:")
    print("  A -> dolu satir yuksekligi L (1.785 dogrulanir mi)")
    print("  B -> H(B) = 4L + 3B  =>  bos satir yuksekligi B")
    print("  C -> karede sayilan satir vs model  =>  CHAR_WIDTH_RATIO")
    print("  D -> kalan iki aday gercekten tasiyor mu")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
