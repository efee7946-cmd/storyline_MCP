"""Sarma kalibrasyonu: model satır sayısını doğru mu veriyor?

B1'in KALAN TEK olculmemis sabiti. Leading olculdu (1.785, iki bagimsiz
kosuda), bos satir olculdu (dolu satirla ayni, model zaten dogru sayiyor),
kirpma olculdu (yok). Modelin kalan hatasinin tamami sarmada:

    D2 vakasi (16pt, kutu 98): gercek 86 birim = 3.0 satir
                               model 114 birim = 4.0 satir

Yani leading dogru, SATIR SAYISI fazla. Sebep CHAR_WIDTH_RATIO.

UC KUTU, TEK ORAN DEGIL. Model satir basina karakteri
`genislik / (ratio * punto)` diye hesapliyor -- yani her karakterin ESIT
genislikte oldugunu varsayiyor. Gercek font orantili: ayni karakter sayisi
farkli metinde farkli yer kaplar. TEK kutudan cikan oran, o metnin harf
dagilimina ozgu bir sayidir ve evrensel sanilir. Bu, son uc duzeltmenin
ortak hatasi.

    C1  notr Turkce duzyazi   -- gercek icerige en yakin, ASIL kalibrasyon
    C2  dar harf agirlikli    -- ratio'nun ust ucu
    C3  genis harf agirlikli  -- ratio'nun alt ucu

C2 ile C3 arasi, oranin YAYILIMINI verir. LAYOUT_SAFETY'nin okunmasi gereken
sey de bu: nokta tahmin degil, gercek metinlerin gezindigi bant.

SERT SATIR SONU YOK -- olculen sey tam olarak sarma davranisi.

YAKALAMA SINIRI ONCEDEN OLCULDU. Onceki turda sarma kutusu y=518'de
bitiyordu ve kare slaydin alt 52 birimini kesiyor (olculdu: gorunur bant
0..488). Kutu kesildi ve bunu kareyi OLCMEYE calisirken ogrendim -- shoot.py'
in odak sorununun ayni sinifi: yakalama sinirinin olculecek seyi kapsadigini
varsaymak. Butun kutular artik y=458'in ustunde bitiyor.

    python tools/goz_sarma.py
"""

from __future__ import annotations

import argparse
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
OUT = ROOT.parent / "test" / "_referans" / "SARMA{}.story"

PUNTO = 12.0
KUTU_GEN = 300.0
GORUNUR_ALT = 458.0     # olculdu; bunun altinda kalan sey karede yok

KUTULAR = [
    ("C1", "notr Turkce duzyazi",
     "Musteri gerildiginde sesin tonu degisir ve cumleler kisalir, ayni "
     "sikayet farkli kelimelerle tekrar eder, konusma gecmise kayar"),
    ("C2", "dar harf agirlikli",
     "illiti tillit ilitli titili lilith itilil tilili ithili liltit "
     "iltili tilith ilitil titlil lithil itilti lilith tiliti"),
    ("C3", "genis harf agirlikli",
     "mumwow wowmum mowwum wummow owmumw mowwum wumowm mowmuw "
     "owwumm mumwow wowmum mowwum"),
]


# LEADING KUTUSU: alti SERT satir. Ayni fikstuurde olculunce leading IKINCI
# BAGIMSIZ kosuda dogrulanir -- MEASURE_LEADING'i guvenilir yapan sey buydu.
LEADING_METIN = "\n".join(f"L{i}" for i in range(1, 7))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--uzay", type=int, choices=(720, 1920), default=720)
    args = ap.parse_args()
    out = Path(str(OUT).format(args.uzay))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        shutil.copy2(REF, out)
        pkg = StoryPackage(out)
        part, ref = next((p, r) for p, r in model.slide_index(pkg).items()
                         if abs(shapes.slide_size(pkg.parse(p))[0] - args.uzay) < 1)

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

        # PUNTO OLCEKLENMEZ. Ilk 1920 turunda punto da uzayla carpilmisti
        # (12 x 2.667 = 32pt) ve metin o kadar cok satira sardi ki kutular
        # birbirine bindi, sayac guvenilmez oldu. Olculen sey ORAN; kutunun
        # slaydin ayni kesrinde olmasi GEREKMIYOR. Sabit 12pt, genis kutu.
        #
        # ARALIK COMERT, ve bilerek MODELDEN TURETILMIYOR: model %50 yanilsa
        # bile kutular bindirmeyecek kadar bosluk var. Aralig i modelin
        # tahminine gore vermek, fikstuurun ilk turundaki dongusellige geri
        # donmek olurdu -- olculecek seyi olcume sokmak.
        o = 1.0
        SATIR_ARALIK = 240.0 if sw > 1000 else 145.0
        KUTU_W = 800.0 if sw > 1000 else KUTU_GEN
        hepsi = KUTULAR + [("L", "LEADING: 6 sert satir", LEADING_METIN)]
        for i, (ad, aciklama, metin) in enumerate(hepsi):
            sutun, satir = i % 2, i // 2
            x = 30 + sutun * (KUTU_W + 60)
            y = 24 + satir * SATIR_ARALIK
            r2 = pkg.parse(part)
            lbl = shapes.clone_shape(shapes.find_seed(pkg, "textBox")[0],
                                     name=f"E_{ad}")
            shapes.set_shape_slide_size(lbl, sw, sh)
            shapes.set_loc(lbl, x, y, x + KUTU_W, y + 16)
            shapes.set_text_flow(lbl, vertical="t", grow=False)
            lbl.set("autoFit", "none")
            shapes.add_shape(r2, lbl)
            _apply_text(r2, lbl, f"{ad}) {aciklama} — {len(metin)} harf",
                        color="#B00000", size=9)
            pkg.replace_xml(part, r2)

            r3 = pkg.parse(part)
            box = shapes.clone_shape(shapes.find_seed(pkg, "textBox")[0],
                                     name=f"K_{ad}")
            shapes.set_shape_slide_size(box, sw, sh)
            shapes.set_loc(box, x, y + 20, x + KUTU_W, y + 20 + SATIR_ARALIK - 40)
            shapes.set_text_flow(box, vertical="t", grow=False)
            box.set("autoFit", "none")
            box.set("wrap", "true")
            shapes.add_shape(r3, box)
            _apply_text(r3, box, metin, color="#000000", size=PUNTO)
            pkg.replace_xml(part, r3)

        story = pkg.parse("story/story.xml")
        story.set("pG", ref.scene_guid)
        sahne = story.find("sceneLst")
        for s in list(sahne):
            if s.get("g") == ref.scene_guid:
                sahne.remove(s); sahne.insert(0, s)
                id_lst = s.find("sldIdLst")
                rels = {v: k for k, v in model._rel_map(pkg).items()}
                rid = rels.get(part)
                for e in list(id_lst or []):
                    if (e.text or "").strip() == rid:
                        id_lst.remove(e); id_lst.insert(0, e)
                break
        pkg.replace_xml("story/story.xml", story)
        rapor = pkg.save(out, backup=False)

    son_alt = 24 + ((len(hepsi) - 1) // 2) * SATIR_ARALIK + 20 + (SATIR_ARALIK - 40)
    print(f"uretildi: {out.name}  verified={rapor['verified']['ok']}")
    print(f"  slayt {ref.basename} ({sw:.0f}x{sh:.0f}), kursun ILK slaydi")
    # 16:9 slayt oynaticida 4:3'ten KISA render oluyor: 1920x1080 slayt
    # 828 px genisliginde 466 px yuksek cizilir ve kareye TAMAMI girer.
    # 720x540 ise 621 px yuksek cizilir ve alt 52 birimi kesilir (olculdu).
    # Siniri tek sayiya sabitlemek, 1920'de olmayan bir kisiti uydururdu.
    sinir = GORUNUR_ALT if sw < 1000 else sh
    print(f"\nYAKALAMA SINIRI: gorunur bant 0..{sinir:.0f} birim "
          f"({'4:3, alt kesiliyor' if sw < 1000 else '16:9, tamami goruinur'})")
    print(f"  en alttaki kutu y={son_alt:.0f}'de bitiyor -> "
          + ("KAREDE GORUNUR" if son_alt <= sinir else "KESILIR, DUZELT"))
    if son_alt > sinir:
        return 1

    print(f"\nGIRDI SPESIFIKASYONU (sert satir sonu YOK):")
    olcek, kaynak = shapes.space_scale(sw)
    per = max(1, int(KUTU_W / (PUNTO * olcek * shapes.CHAR_WIDTH_RATIO)))
    print(f"  uzay carpani: {olcek:.3f} ({kaynak})")
    print(f"  modelin satir basina karakteri: {per} "
          f"(ratio {shapes.CHAR_WIDTH_RATIO})")
    for ad, aciklama, metin in KUTULAR:
        print(f"  {ad}: {len(metin):>3} harf -> model "
              f"{shapes._wrapped_lines(metin, per)} satir  ({aciklama})")
    print("\nOLCULECEK: karede satir SAYILIR, sonra geri hesap:")
    print("  gercek_ratio = KUTU_GEN / (gercek_satir_basina_karakter * PUNTO)")
    print("  C2 ile C3 arasi -> oranin YAYILIMI -> LAYOUT_SAFETY buradan okunur")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
