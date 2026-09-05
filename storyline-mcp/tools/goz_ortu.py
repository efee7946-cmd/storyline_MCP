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

UC KUTU, IKI DEGIL -- ve ucuncusu 2026-09-05'te EKLENDI.

    A  overlayFillType="Default"    <- olculen
    B  overlayFillType="None"       <- NEGATIF kontrol (1064 olcum: boyamaz)
    C  overlayFillType="Gradient"   <- POZITIF kontrol (duraklarini boyar)

NEDEN POZITIF KONTROL SART. Ilk tasarimda yalnizca A ve B vardi ve o kurulum
bir basarisizligi digerinden AYIRAMIYOR: "Default boyamiyor" ile "ektigim ortu
Storyline tarafindan hic dikkate alinmadi" ayni goruntuyu verir -- ikisinde de
magenta yoktur. Nitekim ilk turda tam bu belirsizlik olustu: A'nin gorunen
kismi zemin rengindeydi ve bu, tek basina, ortunun YASADIGINI gostermiyordu.

C bunu kapatir: C magenta gosteriyorsa ekim YASIYOR ve boya yolu calisiyor;
o zaman A'nin magenta gostermemesi "Default" hakkinda bir sey soyler. C de
magenta gostermiyorsa olculen sey bayrak degil, kendi ekimimizdir.

KUTULAR SOL SERITTE, ve bu da olculdu. Storyline'in onizleme diyaloglari
karenin SAG-ORTASINDA duruyor (olculen iki turda da: x>=595, yani slaydin
%19'undan sagi). Slaydin sol %18'i her iki turda da tertemiz kaldi. Fikstuur
engelle savasmak yerine engelin DISINA kuruluyor; kutular sol sutunda alt
alta. Kare kirlense bile olcum alani acik kalir.

ZEMIN DUZ, degrade DEGIL. Degrade zemin uzerinde "kismen boyuyor" ile
"seffaf ama zemin degisken" AYRILMAZ -- ucuncu dal olculemez hale gelir.

KUTULARDA METIN YOK. Metin rengi dolgu okumasina karisir; olculen sey
yalnizca DOLGU. Kutular KONUMDAN taninir (asagidaki kesirler), etiketten
degil -- etiket diyalogun altinda kalabilir.

KARAR KURALI -- KAREYE BAKILMADAN YAZILDI:

  C magenta GOSTERMIYOR                ->  TUR GECERSIZ.
      Ekim yasamadi; olculen sey bayrak degil. A'ya BAKILMAZ.

  C magenta, A zemin rengi (B gibi)    ->  "Default" SEFFAF.
      _dolgu_etkin("gradOvrlyFill") "default" icin False doner, altindaki
      sekle bakilir.

  C magenta, A da magenta (B degil)    ->  "Default" BOYUYOR.
      _dolgu_etkin True kalir ve _paints duraklarini okur.

  A ne zemin ne ortu (kismi, karisik)  ->  TUR GECERSIZ.
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


def _gercek_ortu(pkg, tur):
    """Projeden ISTENEN TIPTE gercek bir gradOvrlyFill bul.

    TIPE GORE ARIYOR, ve bu bir duzeltme (2026-09-05). Onceki surum HERHANGI
    bir ortuyu buluyor, kopyaliyor ve `overlayFillType`i cevirip birakiyordu.
    Bulunan sey pratikte hep bir `None` ortusuydu ve onun geometrisi
    KAPALI bir ortununki: type="def", style="def", angle=3.4028235E+38,
    alpha="-1", scale="-1". Bayragi "Gradient" yapmak o sentinel'leri
    doldurmuyor.

    Bedeli olculdu: POZITIF kontrol (C_Gradient) karede hic magenta
    gostermedi. Yani "Gradient boyar" diye bilinen tip bile boyamadi --
    cunku boyayan gercek dugum degil, bayragi cevrilmis kapali dugumdu.

    Bu, bu dosyanin bastan yazdigi kuralin ayni ihlali: "sekli UYDURMA,
    projeden KOPYALA". Ilk surumde sifirdan kurmak bir tur goturmustu;
    ikinci surumde bayrak cevirmek bir tur daha goturdu.

    `bos.story` ucunu de tasiyor (olculdu: Default 104, None 15,
    Gradient 5), o yuzden ucu de HASAT edilebiliyor.
    """
    hedef = (tur or "").lower()
    for kaynak in (pkg,) + tuple(_YEDEK_KAYNAKLAR()):
        el = _ara(kaynak, hedef)
        if el is not None:
            return el
    return None


def _YEDEK_KAYNAKLAR():
    """Durakli ortu tasiyan baska paketler.

    OLCULDU (2026-09-05): `bos.story` ve alti donor kursun HICBIRINDE
    durakli bir gradOvrlyFill yok -- Default 104/0, Gradient 5/0, None 15/0
    (durakli/duraksiz). Yani Storyline'in KENDI yazdigi dosyalarda ortuler
    duraksiz geliyor ve duraksiz bir ortunun boyayacak rengi YOKTUR.

    Durakli ortu yalnizca `referans.story`de (135 Default) ve bu aracin
    URETTIGI dosyalarda var; uretilenlerinki tohumlardan geliyor
    (seeds/*.xml icinde 381 durakli Default).
    """
    aday = ROOT.parent / "test" / "_referans" / "referans.story"
    if aday.is_file():
        try:
            return (StoryPackage(aday),)
        except Exception:
            return ()
    return ()


def _ara(pkg, hedef):
    for part in model.slide_index(pkg):
        for el in pkg.parse(part).iter("gradOvrlyFill"):
            if not el.findall("stops/stop"):
                continue
            if (el.get("overlayFillType") or "").lower() == hedef:
                return el
    # Slaytlarda yoksa sablon/duzen parcalarina bak.
    for ad in list(pkg._order):
        if not ad.endswith(".xml"):
            continue
        try:
            kok = pkg.parse(ad)
        except Exception:
            continue
        for el in kok.iter("gradOvrlyFill"):
            if not el.findall("stops/stop"):
                continue
            if (el.get("overlayFillType") or "").lower() == hedef:
                return el
    return None


def _ortu_kur(shape, sablon):
    """Gerçek örtüyü OLDUĞU GİBİ takar; duraklara DOKUNULMAZ.

    DURAK RENKLERI DEGISTIRILMIYOR (2026-09-05). Onceki surum duraklarin
    `clr` cocuklarini silip yerine `srgbClr` magenta koyuyordu -- yani
    olculecek dugumun icini kurcaliyordu. Gercek duraklar `schemeClr` +
    `tint` + `satMod` tasiyor; onlari duz bir srgbClr ile degistirmek,
    "ortu boyuyor mu" sorusunu "benim yazdigim durak boyuyor mu"ya
    cevirir.

    Ayirt etme artik RENKTEN degil, FARKTAN: kutunun kendi dolgusu zeminle
    ayni, o yuzden kutu zemin renginde gorunuyorsa ortu boyamamis,
    baska bir renk gorunuyorsa boyamistir. Magenta yalnizca ORTUSUZ
    kontrol kutusunda (D) kullaniliyor.
    """
    bg = shape.find("bG")
    if bg is None or sablon is None:
        return False
    for eski in list(bg.findall("gradOvrlyFill")):
        bg.remove(eski)
    bg.append(copy.deepcopy(sablon))
    return True


def _ortu_sil(shape):
    """Tohumun kendi örtüsünü kaldırır -- D kontrolü için.

    `rect` tohumu kendi `gradOvrlyFill`ini tasiyor (overlayFillType="None").
    D'nin "ortusuz" olmasi gerekiyor, yoksa kontrol, olcmek istedigi seyin
    bir kopyasini tasir.
    """
    bg = shape.find("bG")
    if bg is None:
        return
    for eski in list(bg.findall("gradOvrlyFill")):
        bg.remove(eski)


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

        kurulan = []
        # D KUTUSU ORTU TASIMAZ: duz magenta dolgu. "Kutu ciziliyor mu"
        # sorusunu "ortu boyuyor mu" sorusundan AYIRIR. Eklendi cunku ilk
        # uc-kutulu turda POZITIF kontrol (C_Gradient) de magenta
        # gostermedi; o tek basina "Gradient boyamiyor" demek degil,
        # "kutularim hic cizilmiyor" da olabilir. Ikisi ayrilmadan hicbir
        # sey olculmus sayilmaz.
        for i, (ad, tur) in enumerate((("A_Default", "Default"),
                                       ("B_None", "None"),
                                       ("C_Gradient", "Gradient"),
                                       ("D_DuzDolgu", None))):
            r2 = pkg.parse(part)
            kutu = shapes.clone_shape(shapes.find_seed(pkg, "rect")[0], name=ad)
            shapes.set_shape_slide_size(kutu, sw, sh)
            # SOL SUTUN, ALT ALTA. Olculdu (2026-09-05): onizleme
            # diyaloglari slaydin %19'undan sagini kapliyor, sol %18'i
            # iki turda da temiz kaldi. Karenin alti da pencereye
            # sigmiyor, o yuzden %78'in altinda kaliniyor.
            x = 0.02 * sw
            y = (0.08 + i * 0.23) * sh
            shapes.set_loc(kutu, x, y, x + 0.15 * sw, y + 0.17 * sh)
            # DOLGU ZEMINLE AYNI: kutunun kendi dolgusu zeminden ayrilmasin,
            # boylece gorulen her farkli renk YALNIZCA ortuden gelir.
            if tur is None:
                # Kontrol kutusu: ortu YOK, dolgu dogrudan magenta.
                _ortu_sil(kutu)
                shapes.set_fill(kutu, "#" + ORTU)
            else:
                shapes.set_fill(kutu, IMZA)
                sablon = _gercek_ortu(pkg, tur)
                if sablon is None:
                    print("%s: korpusta DURAKLI '%s' ortusu YOK -- TUR "
                          "GECERSIZ." % (ad, tur))
                    print("   Olculdu (2026-09-05): bos.story ve alti donor "
                          "kursta gradOvrlyFill hic durak tasimiyor")
                    print("   (Default 104/0, Gradient 5/0, None 15/0 = "
                          "durakli/duraksiz). Duraksiz ortunun boyayacak")
                    print("   rengi yoktur. Durakli Default yalnizca "
                          "referans.story'de (135) ve bu aracin uretttigi")
                    print("   dosyalarda var (tohumlarda 381).")
                    print("   POZITIF KONTROL BU KORPUSTAN KURULAMAZ: hicbir "
                          "dosyada durakli Gradient ortusu yok (her yerde")
                    print("   0/5). Kontrol olmadan A'nin sonucu okunmaz -- "
                          "bkz. bas yorumdaki karar kurali.")
                    return 1
                if not _ortu_kur(kutu, sablon):
                    print("%s: bG yok, ortu kurulamadi -- TUR GECERSIZ" % ad)
                    return 1
            shapes.add_shape(r2, kutu)
            _apply_text(r2, kutu, "")
            pkg.replace_xml(part, r2)

            r3 = pkg.parse(part)
            et = shapes.clone_shape(shapes.find_seed(pkg, "textBox")[0],
                                    name="E_%s" % ad)
            shapes.set_shape_slide_size(et, sw, sh)
            # Etiket kutunun SAGINDA: olcum alanina girmesin, ve
            # okunamazsa da zarar vermesin (kutular KONUMDAN taniniyor).
            shapes.set_loc(et, x + 0.17 * sw, y + 0.05 * sh,
                           x + 0.60 * sw, y + 0.13 * sh)
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
        if tur is None:
            print("  %-11s ortusuz kontrol (duz #%s)" % (ad, ORTU))
            if var is not None:
                print("     BEKLENMEYEN ORTU -- TUR GECERSIZ")
                return 1
            continue
        print("  %-11s istenen=%-10s yazilan=%s" % (ad, tur, var))
        if not var or var[0] != tur or var[1] != 3:
            print("     ORTU YAZILMADI -- TUR GECERSIZ")
            return 1
    print("\nKARAR KURALI bas yorumda, KAREYE BAKILMADAN yazildi:")
    print("  C magenta DEGILSE        -> TUR GECERSIZ (ekim yasamadi)")
    print("  C magenta, A zemin rengi -> 'Default' SEFFAF")
    print("  C magenta, A da magenta  -> 'Default' BOYUYOR")
    print("  kutular KONUMDAN taninir (slayt kesiri):")
    for i, (ad, _tur) in enumerate(kurulan):
        print("    %-11s x 0.02..0.17  y %.2f..%.2f"
              % (ad, 0.08 + i * 0.23, 0.08 + i * 0.23 + 0.17))
    print("\nkare:")
    print("  python tools/shoot_preview.py %s -o ../test/_referans/ORTU.png "
          "--imza %s --en-az 5" % (CIKTI, IMZA.lstrip("#")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
