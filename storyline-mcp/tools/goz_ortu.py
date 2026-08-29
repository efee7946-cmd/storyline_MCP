"""overlayFillType="Default" bir kutuya zemin çiziyor mu?

B5'in erisilebilirlik yarisini kilitleyen TEK dugum. Uretilen kursta zemini
okunamayan 56 yazinin 52'sini engelleyen sey ayni: `gradOvrlyFill` tasiyan
bir textBox, ve `overlayFillType="Default"`.

KORPUSTA UC DEGER OLCULDU (2026-08-18, iki kurs):

    overlayFillType="None"      1064 kez  -> ortu KAPALI, boyamiyor
    overlayFillType="Default"    717 kez  -> ANLAMI OLCULMEDI
    overlayFillType="Gradient"      1 kez -> duraklarini boyuyor

"Default" uc durak tasiyor, yani boyayabilir de boyamayabilir de. Tahmin
edilmedi: bu oturumda ad/desen okumasi uc kez yanlis cikti (copiedG, <trig>,
verG).

IKI KUTU, TEK KUTU DEGIL. Tek kutu MUTLAK renk okumaya zorlar ("bu ton
zemin mi ortu mu"); iki kutu KARSILASTIRMAYA izin verir:

    A  overlayFillType="Default"   <- olculen
    B  overlayFillType="None"      <- BILINEN NEGATIF KONTROL (1064 olcum)

B'nin boyamadigi biliniyor. A, B ile AYNI gorunuyorsa seffaf; FARKLI
gorunuyorsa boyuyor. Negatif kontrol olmadan "renk gordum" gozlemi rengin
hangi katmandan geldigini soylemez.

ZEMIN DUZ, degrade DEGIL. Degrade zemin uzerinde "kismen boyuyor" ile
"seffaf ama zemin degisken" AYRILMAZ -- ucuncu dal olculemez hale gelir.

KUTULARDA METIN YOK. Metin rengi dolgu okumasina karisir; olculen sey
yalnizca DOLGU.

KARAR KURALI -- KAREYE BAKILMADAN YAZILDI:

  A ile B AYNI (ikisi de zemin rengi)  ->  "Default" SEFFAF.
      _dolgu_etkin("gradOvrlyFill") "default" icin False doner, altindaki
      sekle bakilir. 52 vaka cozulur.

  A ile B FARKLI (A ortu rengini gosteriyor)  ->  "Default" BOYUYOR.
      _dolgu_etkin True doner ve _paints duraklarini okur. 52 vaka cozulur.

  A ne zemin ne ortu (kismi, karisik, yari saydam)  ->  TUR GECERSIZ.
      "Default" reddedilmeye devam eder ve sebebi bu kayitla birlikte durur.

  Kutulardan biri karede GORUNMUYORSA  ->  TUR GECERSIZ (fikstuur hatasi,
      olcunun sonucu degil).

    python tools/goz_ortu.py
"""

from __future__ import annotations

import copy
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
CIKTI = ROOT.parent / "test" / "_referans" / "ORTU.story"

IMZA = "#E8F0D8"        # duz zemin; kare guard'i bunu arar
ORTU = "D000D0"         # magenta -- paletin hicbir yerinde yok, karisamaz


def _gercek_ortu(pkg):
    """Projeden GERÇEK bir gradOvrlyFill bul ve kopyala.

    ILK SURUM SIFIRDAN KURDU ve Storyline dosyayi HIC ACMADI (olculdu: 120
    saniyede acilmadi). Gercek dugumde `centerPt` ve `fillRect` cocuklari
    var, `angle` 3.4028235E+38, `adjustY` -2147483648 -- benim uydurdugum
    degerler degil.

    Bu, README'nin bastan soyledigi kural: sekli UYDURMA, projeden KOPYALA.
    Bu dosya o kurali bir kez daha ihlal etti ve bedeli bir tur oldu.
    """
    for part in model.slide_index(pkg):
        for el in pkg.parse(part).iter("gradOvrlyFill"):
            if el.findall("stops/stop"):
                return el
    return None


def _ortu_kur(shape, tur, sablon):
    """Gerçek örtüyü kopyalar; yalnızca TİP ve DURAK RENGİ değişir."""
    bg = shape.find("bG")
    if bg is None or sablon is None:
        return False
    for eski in list(bg.findall("gradOvrlyFill")):
        bg.remove(eski)
    el = copy.deepcopy(sablon)
    el.set("overlayFillType", tur)
    for st in el.findall("stops/stop"):
        for clr in st.findall("clr"):
            for cocuk in list(clr):
                clr.remove(cocuk)
            ET.SubElement(clr, "srgbClr", {"val": ORTU})
    bg.append(el)
    return True


def main():
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

        sablon = _gercek_ortu(pkg)
        if sablon is None:
            print("Projede gradOvrlyFill ornegi yok -- TUR GECERSIZ")
            return 1
        kurulan = []
        for i, (ad, tur) in enumerate((("A_Default", "Default"),
                                       ("B_None", "None"))):
            r2 = pkg.parse(part)
            kutu = shapes.clone_shape(shapes.find_seed(pkg, "rect")[0], name=ad)
            shapes.set_shape_slide_size(kutu, sw, sh)
            x = (10 + i * 45) / 100 * sw
            shapes.set_loc(kutu, x, 0.30 * sh, x + 0.35 * sw, 0.62 * sh)
            # DOLGU ZEMINLE AYNI: kutunun kendi dolgusu zeminden ayrilmasin,
            # boylece gorulen her farkli renk YALNIZCA ortuden gelir.
            shapes.set_fill(kutu, IMZA)
            if not _ortu_kur(kutu, tur, sablon):
                print("%s: bG yok, ortu kurulamadi -- TUR GECERSIZ" % ad)
                return 1
            shapes.add_shape(r2, kutu)
            _apply_text(r2, kutu, "")
            pkg.replace_xml(part, r2)

            r3 = pkg.parse(part)
            et = shapes.clone_shape(shapes.find_seed(pkg, "textBox")[0],
                                    name="E_%s" % ad)
            shapes.set_shape_slide_size(et, sw, sh)
            shapes.set_loc(et, x, 0.20 * sh, x + 0.35 * sw, 0.27 * sh)
            shapes.set_text_flow(et, vertical="t", grow=False)
            et.set("autoFit", "none")
            shapes.add_shape(r3, et)
            _apply_text(r3, et, 'overlayFillType=%s' % tur,
                        color="#B00000", size=13)
            pkg.replace_xml(part, r3)
            kurulan.append((ad, tur))

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

    # GERI OKU: ortunun yazildigini DOGRULA. Yazilmadiysa tur olculecek seyi
    # hic icermez ve kare bunu soylemez -- "ekim geri okunur" (K13).
    pkg = StoryPackage(CIKTI)
    root = pkg.parse(part)
    bulunan = {}
    for el in root.iter():
        g = next(el.iter("gradOvrlyFill"), None)
        if g is not None and el.get("name"):
            bulunan[el.get("name")] = (g.get("overlayFillType"),
                                       len(g.findall("stops/stop")))
    print("uretildi: %s  verified=%s" % (CIKTI.name, rapor["verified"]["ok"]))
    print("  slayt %s (%.0fx%.0f), kursun ILK slaydi" % (ref.basename, sw, sh))
    print("  zemin %s (duz)   ortu duraklari #%s (magenta)" % (IMZA, ORTU))
    for ad, tur in kurulan:
        var = bulunan.get(ad)
        print("  %-10s istenen=%-10s yazilan=%s" % (ad, tur, var))
        if not var or var[0] != tur or var[1] != 3:
            print("     ORTU YAZILMADI -- TUR GECERSIZ")
            return 1
    print("\nKARAR KURALI bas yorumda, KAREYE BAKILMADAN yazildi:")
    print("  A ile B AYNI   -> 'Default' SEFFAF")
    print("  A ile B FARKLI -> 'Default' BOYUYOR")
    print("\nkare:")
    print("  python tools/shoot_preview.py %s -o ../test/_referans/ORTU.png "
          "--imza %s --en-az 5" % (CIKTI, IMZA.lstrip("#")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
