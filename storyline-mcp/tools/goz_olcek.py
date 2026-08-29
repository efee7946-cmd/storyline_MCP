"""Punto, slayt uzayına göre ölçekleniyor mu? -- ve doğrusal mı?

estimate_text_height'in ICINDE bir IDDIA var ve hic olculmedi:

    scale = slide_width / 720
    line_px = font_size * scale

Yani 17pt'nin 1920'lik bir slaytta 45 birim cizildigi varsayiliyor. Butun
kalibrasyon 720'de yapildi (KIRPMA, KALIBRE2, SARMA -- ucu de 720x540), ve
uretimdeki soru slaytlarinin HEPSI 1920. Varsayim en cok orada is goruyor,
en az orada sinandi.

FIKSTUR SARMA'NIN KOPYASI, yalnizca slayt uzayi degisiyor. Yeni tasarim yok.

IKI PUNTO, cunku scale DOGRUSAL varsayiliyor. Tek puntoda olcmek o noktadaki
degeri dogrular, doğrusallığı degil -- C1'den ogrenilen sey tam buydu: tek
nokta yayilimi gostermez. 12 ve 17, dogrusal mi baska bir yol mu var onu
ayirir. Ayrim onemli cunku fit_choices her puntoda calisiyor.

AYNI PUNTO IKI UZAYDA, tek yontemle. 720 olcumu elde zaten var ama baska bir
fikstuurden, baska puntoda; ayni karede tekrarlamak "iki tur arasinda baska
ne degisti" sorusunu kapatir.

KARAR KURALI -- KAREYE BAKMADAN YAZILDI:

  OLCEK DOGRULANIRSA (1920 adimi ~2.667 x 720 adimi):
      fit_choices'in kalan %90 tasmasi GERCEK. Genislik duzeltmesi yetmedi,
      ikinci bir yere daha bakmak gerekiyor.
      MEASURE_* sabitleri gecerli kalir.

  OLCEK YANLISSA (adim iki uzayda AYNI, ya da carpan 2.667 degil):
      scale formulu duzelir ve sonuc DAHA BUYUK: MEASURE_LEADING=1.785 ve
      CHAR_WIDTH_RATIO=0.79'un ikisi de 720'de olculdu, dolayisiyla
      "1920'de de gecerli" olmalari OLCULMEMIS bir varsayim olarak aciga
      cikar. Dort kirmizi kapinin bir kismi kendiliginde donebilir.

  DOGRUSAL DEGILSE (12pt ve 17pt farkli carpan veriyorsa):
      scale tek bir bolme degil; formul punto-bagimli hale gelir ve
      fit_choices'in her puntoda ayri dogrulanmasi gerekir.

    python tools/goz_olcek.py --uzay 720
    python tools/goz_olcek.py --uzay 1920
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
OUT = ROOT.parent / "test" / "_referans" / "OLCEK{}.story"

PUNTOLAR = (12.0, 17.0)
SATIR = 6
# Sert satir sonlari: sarma HIC devreye girmesin. Olculen sey yalnizca
# satir yuksekligi, ve "6 satir" girdinin TANIMI.
def metin(p):
    return "\n".join(f"{int(p)}pt-{i}" for i in range(1, SATIR + 1))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--uzay", type=int, choices=(720, 1920), required=True)
    args = ap.parse_args()
    out = Path(str(OUT).format(args.uzay))

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        shutil.copy2(REF, out)
        pkg = StoryPackage(out)
        hedef = next(((p, r) for p, r in model.slide_index(pkg).items()
                      if abs(shapes.slide_size(pkg.parse(p))[0] - args.uzay) < 1),
                     None)
        if hedef is None:
            print(f"{args.uzay} uzayinda slayt yok.")
            return 2
        part, ref = hedef

        root = pkg.parse(part)
        compose.clear_slide(root)
        sw, sh = shapes.slide_size(root)
        olcek = sw / 720.0
        zemin = shapes.clone_shape(shapes.find_seed(pkg, "rect")[0], name="Zemin")
        shapes.set_shape_slide_size(zemin, sw, sh)
        shapes.set_loc(zemin, 0, 0, sw, sh)
        shapes.set_fill(zemin, "#FFFFFF")
        shapes.add_shape(root, zemin, to_back=True)
        _apply_text(root, zemin, "")
        pkg.replace_xml(part, root)

        for i, punto in enumerate(PUNTOLAR):
            x = (30 + i * 340) * olcek
            for ad, y, icerik, renk, boy in (
                    (f"E_{int(punto)}", 20 * olcek,
                     f"{int(punto)}pt, {SATIR} sert satir", "#B00000", 9 * olcek),
                    (f"K_{int(punto)}", 42 * olcek, metin(punto), "#000000", punto)):
                r2 = pkg.parse(part)
                box = shapes.clone_shape(shapes.find_seed(pkg, "textBox")[0],
                                         name=ad)
                shapes.set_shape_slide_size(box, sw, sh)
                shapes.set_loc(box, x, y, x + 300 * olcek, y + 380 * olcek)
                shapes.set_text_flow(box, vertical="t", grow=False)
                box.set("autoFit", "none")
                box.set("wrap", "true")
                shapes.add_shape(r2, box)
                _apply_text(r2, box, icerik, color=renk, size=boy)
                pkg.replace_xml(part, r2)

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

    print(f"uretildi: {out.name}  verified={rapor['verified']['ok']}")
    print(f"  slayt {ref.basename}  {sw:.0f}x{sh:.0f}  (kursun ILK slaydi)")
    print(f"\nGIRDI: her kutuda {SATIR} SERT satir, punto {PUNTOLAR}")
    print("MODELIN ONGORDUGU satir yuksekligi (birim):")
    for punto in PUNTOLAR:
        print(f"  {int(punto)}pt -> {punto * (sw / 720.0) * shapes.MEASURE_LEADING:.1f}"
              f"   (scale {sw / 720.0:.3f} x leading {shapes.MEASURE_LEADING})")
    print("\nOLCULECEK: karede satir ADIMI. Iki uzaydaki adim orani, scale'in")
    print("kendisidir -- turetilmez, dogrudan gozlenir.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
