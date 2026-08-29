"""27.5:1'e gerilmis bir elips ekranda ne oluyor, ve neyi degistirmek duzeltir?

OLCULEN KUSUR (2026-08-19): uretilen kursta coktan-secmeli siklar `<oval>`
ve 1612.8x58.7 -- en/boy 27.5. Kalibrasyon noktasinda (elle yapilmis kurs)
HICBIR oval 1.6'yi asmiyor; oradaki ovaller bir fotografin ustunde duran
neredeyse dairesel lekeler. Yani bizim uygulamamiz oval SINIFINDA kalibrasyon
bandinin cok disinda.

DIKKAT -- BIR IDDIA CURUDU: "en/boy 27.5 kusurdur" TEK BASINA yanlis.
Kalibrasyon noktasinda en/boy 48.2'ye kadar giden 65 kutu var; ama onlar
`textBox`, yani gorunur silueti olmayan bir satir yazi. Karsilastirma
SINIF ICINDE yapilmali: oval-oval. Bu tur onu olcuyor.

GEOMETRI IKI YERDE YAZILI:
    tag                <oval> / <roundRect>
    prstGeom cocugu    <prstGeom><oval/></prstGeom>
                       <prstGeom><roundRect radius="0.16666667"/></prstGeom>
Hangisinin cizimi belirledigi BILINMIYOR. Tahmin edilmedi.

UC SEKIL, HEPSI AYNI OLCUDE (1612.8x58.7 -- olculen kusurlu olcu):

    A  dokunulmamis <oval>              <- BILINEN NEGATIF KONTROL
    B  tag <oval>, prstGeom roundRect
    C  tag <roundRect> + prstGeom roundRect

A'nin ne yaptigi biliniyor (kusuru uretiyor). A mercek gorunmezse deney
kusuru HIC uretmemis demektir ve B/C hakkinda hicbir sey soylemez.

KARAR KURALI -- KAREYE BAKILMADAN YAZILDI:

  A mercek DEGILSE                    ->  TUR GECERSIZ. Teshis yanlis,
      bastan olcmek gerekir; B ve C yorumlanmaz.

  A mercek, B kapsul                  ->  prstGeom YETER. Duzeltme: butun
      prstGeom dugumlerini roundRect yap -- DURUM GOVDELERI DAHIL (oval uc
      tane tasiyor; shapeLst seviyesinde yazan kod ikisini kacirir, K22).
      Tag'e, GUID'lere, tetiklere dokunulmaz.

  A mercek, B mercek, C kapsul        ->  TAG DA GEREKLI. Duzeltme tag'i de
      cevirmeli; etkilesim GUID'leri korunarak.

  C acilmiyor ya da bozuk ciziliyor   ->  TAG CEVIRME GECERSIZ. Yol katalog
      borcuna (metin-listesi tohumu) doner.

SINIR -- ONCEDEN YAZILDI: buradaki ovaller TEMIZ tohum, etkilesim tasimiyor.
Bu tur SILUET sorusunu cevaplar; "durum govdelerindeki prstGeom da yazildi
mi" sorusunu KARE degil, geri okuma cevaplar (asagida yapiliyor).

    python tools/goz_kapsul.py
"""

from __future__ import annotations

import shutil
import sys
import warnings
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from storyline_mcp import compose, model, shapes
from storyline_mcp.authoring import _apply_text
from storyline_mcp.package import StoryPackage

KAYNAK = ROOT.parent / "test" / "bos.story"
CIKTI = ROOT.parent / "test" / "_referans" / "KAPSUL.story"

IMZA = "#E8F0D8"        # duz zemin; kare guard'i bunu arar
DOLGU = "2E5FA3"        # siluetin gorunmesi icin guclu bir dolgu
EN_BOY = 1612.8 / 58.7  # OLCULEN kusurlu oran (27.5), secilmis degil.
# MUTLAK olcu tasinamaz: kusur 1920x1080 bir slayttan olculdu, fikstuur
# slaydi 720x540. 1612.8'i oldugu gibi koymak sekli slayttan TASIRIR ve tur
# gecersiz olur. Tasinan sey ORAN.
RADIUS = "0.16666667"   # korpustaki gercek roundRect'ten OKUNDU, uydurulmadi


def _kapsul_yap(shape, tag_da: bool) -> int:
    """prstGeom'lari roundRect'e cevirir. Kac dugum degisti doner."""
    n = 0
    for g in shape.iter("prstGeom"):
        for c in list(g):
            if c.tag == "oval":
                g.remove(c)
                ET.SubElement(g, "roundRect",
                              {"vertexSet": "false", "radius": RADIUS})
                n += 1
    if tag_da:
        shape.tag = "roundRect"
    return n


def main() -> int:
    if not KAYNAK.is_file():
        print("Kaynak yok: %s" % KAYNAK)
        return 2
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        shutil.copy2(KAYNAK, CIKTI)
        pkg = StoryPackage(CIKTI)
        part, ref = next(iter(model.slide_index(pkg).items()))
        root = pkg.parse(part)
        compose.clear_slide(root)
        sw, sh = shapes.slide_size(root)

        zemin = shapes.clone_shape(shapes.find_seed(pkg, "rect")[0], name="Zemin")
        shapes.set_shape_slide_size(zemin, sw, sh)
        shapes.set_loc(zemin, 0, 0, sw, sh)
        shapes.set_fill(zemin, IMZA)
        shapes.add_shape(root, zemin, to_back=True)
        _apply_text(root, zemin, "")
        pkg.replace_xml(part, root)

        try:
            tohum = shapes.find_seed(pkg, "oval")[0]
        except Exception as exc:
            print("oval tohumu bulunamadi (%s) -- TUR GECERSIZ"
                  % type(exc).__name__)
            return 1

        kurulan = []
        for i, (ad, prst, tag_da) in enumerate((
                ("A_oval", False, False),
                ("B_prstGeom", True, False),
                ("C_tag", True, True))):
            r2 = pkg.parse(part)
            kutu = shapes.clone_shape(tohum, name=ad)
            shapes.set_shape_slide_size(kutu, sw, sh)
            y = (0.22 + i * 0.22) * sh
            x = 0.08 * sw
            g_w = 0.84 * sw
            g_h = g_w / EN_BOY
            shapes.set_loc(kutu, x, y, x + g_w, y + g_h)
            shapes.set_fill(kutu, DOLGU)
            degisen = _kapsul_yap(kutu, tag_da) if prst else 0
            shapes.add_shape(r2, kutu)
            _apply_text(r2, kutu, "")
            pkg.replace_xml(part, r2)

            r3 = pkg.parse(part)
            et = shapes.clone_shape(shapes.find_seed(pkg, "textBox")[0],
                                    name="E_%s" % ad)
            shapes.set_shape_slide_size(et, sw, sh)
            shapes.set_loc(et, x, y - 0.055 * sh, x + 0.5 * sw, y - 0.01 * sh)
            shapes.set_text_flow(et, vertical="t", grow=False)
            et.set("autoFit", "none")
            shapes.add_shape(r3, et)
            _apply_text(r3, et, "%s  (prstGeom=%s, tag=%s)"
                        % (ad, "roundRect" if prst else "oval",
                           "roundRect" if tag_da else "oval"),
                        color="#B00000", size=13)
            pkg.replace_xml(part, r3)
            kurulan.append((ad, prst, tag_da, degisen))

        story = pkg.parse("story/story.xml")
        story.set("pG", ref.scene_guid)
        sahne = story.find("sceneLst")
        for s in list(sahne):
            if s.get("g") == ref.scene_guid:
                sahne.remove(s)
                sahne.insert(0, s)
                idl = s.find("sldIdLst")
                rels = {v: k for k, v in model._rel_map(pkg).items()}
                rid = rels.get(part)
                for e in list(idl or []):
                    if (e.text or "").strip() == rid:
                        idl.remove(e)
                        idl.insert(0, e)
                break
        pkg.replace_xml("story/story.xml", story)
        rapor = pkg.save(CIKTI, backup=False)

    # GERI OKU (K13): ekilen sey yazildi mi? Yazilmadiysa kare bunu SOYLEMEZ.
    pkg = StoryPackage(CIKTI)
    root = pkg.parse(part)
    print("uretildi: %s  verified=%s" % (CIKTI.name, rapor["verified"]["ok"]))
    print("  slayt %s (%.0fx%.0f), kursun ILK slaydi"
          % (ref.basename, sw, sh))
    _gw = 0.84 * sw
    print("  uc sekil de %.1fx%.1f  (en/boy %.1f) -- OLCULEN kusurlu ORAN"
          % (_gw, _gw / EN_BOY, EN_BOY))
    for ad, prst, tag_da, degisen in kurulan:
        print("  %-12s istenen prstGeom=%-9s tag=%-9s  degisen dugum=%d"
              % (ad, "roundRect" if prst else "oval",
                 "roundRect" if tag_da else "oval", degisen))
    sorun = False
    for el in list(root.find("shapeLst") or []):
        ad = el.get("name") or ""
        if not ad.startswith(("A_", "B_", "C_")):
            continue
        gelen = [c.tag for g in el.iter("prstGeom") for c in list(g)]
        print("  %-12s YAZILAN tag=%-10s prstGeom=%s" % (ad, el.tag, gelen))
        if ad.startswith("A_") and set(gelen) != {"oval"}:
            print("     negatif kontrol BOZUK -- TUR GECERSIZ")
            sorun = True
        if ad.startswith(("B_", "C_")) and "oval" in gelen:
            print("     prstGeom YAZILMADI -- TUR GECERSIZ")
            sorun = True
    if sorun:
        return 1
    print("")
    print("KARAR KURALI bas yorumda, KAREYE BAKILMADAN yazildi.")
    print("  A mercek degil        -> TUR GECERSIZ (teshis yanlis)")
    print("  A mercek, B kapsul    -> prstGeom yeter (durum govdeleri dahil)")
    print("  A/B mercek, C kapsul  -> tag da gerekli")
    print("")
    print("kare:")
    print("  python tools/shoot_preview.py %s -o ../test/_referans/KAPSUL.png "
          "--imza %s --en-az 5" % (CIKTI, IMZA.lstrip("#")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
