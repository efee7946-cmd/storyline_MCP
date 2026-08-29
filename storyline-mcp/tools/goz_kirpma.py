"""Storyline taşan metni KIRPIYOR MU? -- ve kararı önceden yazılmış deney.

Bu soru dort turdur cevapsiz ve her turda ayni sekilde basarisiz oldu:
kontrol dusmedi. Sebep her seferinde fikstuurdu (koordinat uzayi, metin
uzunlugu, wrap, slayt siniri) ama besincisi daha derin:

    FIKSTURUN GUVENCESI, SINANAN FONKSIYONLA URETILIYORDU.

"kontrol %29 tasiyor" cumlesi measured_text_height'tan geliyordu -- yani
sinadigim fonksiyondan. Kanitlanan sey "model tasma ongoruyor"du, "tasma
var" degil. check_thresholds_independent'a kodlanan kuralin fikstuur
tarafindaki hali: bir guard, korudugu seyi referans alamaz.

BU FIKSTURUN GUVENCESI GIRDI SPESIFIKASYONUNDAN OKUNUR:

    10 tane SERT satir sonu (\\n) koyulur. Sarma HIC devreye girmez, cunku
    her satir zaten kendi paragrafi. "10 satir" girdinin TANIMI, girdi
    uzerinde bir hesap degil.

    Kutu 20 birim. Satir yuksekligi ne olursa olsun -- satir basina 1 birim
    varsaysan bile -- 10 satir 20 birime sigmaz. Marj, satir yuksekligi
    donusumundeki butun belirsizligi yutar. Dogru yaklasim kesinlik degil,
    parametrenin makul araliginin tamamina dayaniklilik.

IKI VAKA, cunku biri digerini kapsamiyor:

    dejenere   kutu 20 birim / 10 sert satir. "Hic kirpiyor mu" sorusunu
               kesin cevaplar. Ama dedektorun asil hedefledigi marji
               (%105-120) temsil etmez ve Storyline dejenere bir kutuda
               baska bir yola girebilir.
    marj       kutu 3 satir alacak kadar / 4 sert satir. Mekanizmanin
               uretim bandinda ne yaptigini verir.

KARAR KURALI -- KAREYE BAKMADAN YAZILDI:

    KIRPMA VARSA (dejenere vakada metnin alt satirlari GORUNMUYOR):
        tasma dedektoru bir DOGRULUK kontroludur, kalir.
        Sirada esigin kalibrasyonu var (marj vakasi hangi noktada kirpiyor).
        check_text_fits'in kapsamini katmanlara genisletmek anlamli.

    KIRPMA YOKSA (dejenere vakada 10 satirin hepsi okunuyor, kutunun
    disina tassa bile):
        Storyline metni kutu sinirinin disina tasirip OKUNUR birakiyor.
        O zaman "tasma" bir doğruluk hatasi degil KOZMETIK bir uyaridir:
        ogrenci metni kaybetmiyor, duzen bozuluyor. Dedektor kalir ama
        onceligi duser, ve B3'un altindaki varsayim da degisir.

    ARADA KALIRSA (dejenere kirpiyor, marj kirpmiyor):
        kirpma var ama esikli. Esik olculur, dedektor ona gore ayarlanir.

    python tools/goz_kirpma.py
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
OUT = ROOT.parent / "test" / "_referans" / "KIRPMA.story"

# Her satir NUMARALI: kirpilma varsa kacinci satirdan kesildigi dogrudan
# okunur. "Metin eksik gorunuyor" ile "6. satirdan sonrasi yok" ayni bilgi
# degil -- ikincisi esigi de verir.
DEJENERE = "\n".join(f"{i:02d} SATIR" for i in range(1, 11))
MARJ = "\n".join(f"{i:02d} SATIR" for i in range(1, 5))

DEJENERE_KUTU = 20.0    # birim, 720 uzayinda. 10 satir buraya sigamaz.
MARJ_SATIR = 3          # kutu bu kadar satir alacak sekilde olculur


def _kutu(pkg, part, ad, metin, x, y, genislik, yukseklik, punto, autofit):
    root = pkg.parse(part)
    sw, sh = shapes.slide_size(root)
    kutu = shapes.clone_shape(shapes.find_seed(pkg, "textBox")[0], name=ad)
    shapes.set_shape_slide_size(kutu, sw, sh)
    shapes.set_loc(kutu, x, y, x + genislik, y + yukseklik)
    shapes.set_text_flow(kutu, vertical="t", grow=False)
    kutu.set("autoFit", autofit)
    shapes.add_shape(root, kutu)
    _apply_text(root, kutu, metin, color="#000000", size=punto)
    pkg.replace_xml(part, root)


def _etiket(pkg, part, ad, metin, x, y, genislik, olcek):
    root = pkg.parse(part)
    sw, sh = shapes.slide_size(root)
    lbl = shapes.clone_shape(shapes.find_seed(pkg, "textBox")[0], name=ad)
    shapes.set_shape_slide_size(lbl, sw, sh)
    shapes.set_loc(lbl, x, y, x + genislik, y + 22 * olcek)
    shapes.set_text_flow(lbl, vertical="t", grow=False)
    shapes.add_shape(root, lbl)
    _apply_text(root, lbl, metin, color="#B00000", size=10 * olcek)
    pkg.replace_xml(part, root)


def main() -> int:
    if not REF.is_file():
        print(f"Referans yok: {REF}")
        return 2

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        shutil.copy2(REF, OUT)
        pkg = StoryPackage(OUT)

        # 720 uzayinda bir slayt: sayilar kucuk ve okunur kalsin.
        hedef = None
        for part, ref in model.slide_index(pkg).items():
            if abs(shapes.slide_size(pkg.parse(part))[0] - 720.0) < 1:
                hedef = (part, ref)
                break
        if hedef is None:
            print("720 uzayinda slayt bulunamadi.")
            return 2
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

        punto = 12.0
        # MARJ kutusu: 3 satir alacak kadar. Bu HESAP degil, kaba bir
        # yerlestirme -- karar dejenere vakadan okunuyor, buradan degil.
        marj_yukseklik = MARJ_SATIR * punto * 1.35

        _etiket(pkg, part, "E_dejenere",
                f"A) DEJENERE: kutu {DEJENERE_KUTU:.0f} birim, 10 SERT satir "
                "-> hic kirpiyor mu?", 30, 20, sw - 60, 1.0)
        _kutu(pkg, part, "K_dejenere", DEJENERE, 30, 50, 260,
              DEJENERE_KUTU, punto, "none")

        _etiket(pkg, part, "E_marj",
                f"B) MARJ: kutu ~{MARJ_SATIR} satir ({marj_yukseklik:.0f} "
                "birim), 4 SERT satir -> marjda ne yapiyor?",
                30, 250, sw - 60, 1.0)
        _kutu(pkg, part, "K_marj", MARJ, 30, 280, 260,
              marj_yukseklik, punto, "none")

        # Kontrol: AYNI metin, kutu bol. Kirpma yoksa ikisi ayni gorunur;
        # bu satir "metin zaten cizilmiyor mu" ihtimalini eler.
        _etiket(pkg, part, "E_bol",
                "C) KONTROL: ayni 4 satir, BOL kutu -> metin cizilebiliyor mu?",
                340, 250, sw - 370, 1.0)
        _kutu(pkg, part, "K_bol", MARJ, 340, 280, 260,
              marj_yukseklik * 3, punto, "none")

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
                for el in list(id_lst or []):
                    if (el.text or "").strip() == rid:
                        id_lst.remove(el)
                        id_lst.insert(0, el)
                break
        pkg.replace_xml("story/story.xml", story)
        rapor = pkg.save(OUT, backup=False)

    print(f"uretildi: {OUT.name}  verified={rapor['verified']['ok']}")
    print(f"  slayt {ref.basename} ({sw:.0f}x{sh:.0f}), kursun ILK slaydi")
    print()
    # GUVENCE GIRDIDEN OKUNUR, HESAPTAN DEGIL.
    print("FIKSTUR GUVENCESI (girdi spesifikasyonu, model kullanilmadi):")
    print(f"  A) {DEJENERE.count(chr(10)) + 1} sert satir sonu, kutu "
          f"{DEJENERE_KUTU:.0f} birim.")
    print(f"     Satir basina 1 birim varsaysak bile 10 > {DEJENERE_KUTU:.0f} "
          "degil -- ama\n     10 satir 20 birime hicbir makul satir "
          "yuksekliginde sigmaz.")
    print(f"  B) {MARJ.count(chr(10)) + 1} sert satir, kutu ~{MARJ_SATIR} "
          "satirlik.")
    print(f"  C) AYNI 4 satir, {MARJ_SATIR * 3} satirlik kutuda (kontrol).")
    print()
    print("KARAR KURALI (kareye bakmadan, docstring'de yazili):")
    print("  A'da alt satirlar GORUNMUYORSA  -> kirpma VAR, dedektor dogruluk")
    print("     kontrolu olarak kalir, esik kalibre edilir.")
    print("  A'da 10 satirin hepsi OKUNUYORSA -> kirpma YOK, dedektor")
    print("     KOZMETIK uyariya duser, B3'un varsayimi da degisir.")
    print("  A kirpiyor ama B kirpmiyorsa    -> esikli kirpma, esik olculur.")
    print("  C'de metin gorunmuyorsa          -> tur GECERSIZ (metin hic")
    print("     cizilmiyor demektir, kirpma hakkinda hicbir sey soylenemez).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
