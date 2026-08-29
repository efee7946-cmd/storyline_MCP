"""Kalibrasyon, cakismayan aralikla. Tek punto, artan uzunluk.

Her ornek kendi genis yuvasinda; hangi uzunluktan itibaren ikinci satira
sardigi gozle sayilabilsin diye. Kelime sarmasini olcuyoruz, o yuzden
dizgiler gercek kelimelerden olusuyor.

DENENDI, SONUC ALINAMADI -- ama yol KAPALI DEGIL. Fark onemli:

    Fikir: kutulari grow=True yapip Storyline'da acmak, kaydetmek ve
    yuksekligi dosyadan geri okumak. Storyline kutuyu kendi metin olcusune
    gore yeniden boyutlandirirsa, kalibrasyon gozle sayim yerine dosyadan
    okunur -- ve ayni iz metnin kirpilip kirpilmadigini da soylerdi.

    Denendi (2026-08-14): 17/24/32/48 punto, kasitli olarak cok kisa (12
    birim) kutularda. Acildi, save_and_close cagrildi, kapandi. Dort kutu
    da 12.0 birim kaldi ve pakette TEK BIR BAYT degismedi.

    Ama bu "Storyline yeniden boyutlandirmiyor" demek DEGIL. Olculdugunde
    goruldu ki storyline_ctl.save_and_close, Ctrl+S'i yalnizca pencere
    basligi kirli gosteriyorsa gonderiyor; bir dosyayi acmak onu kirletmez.
    Yani Storyline hicbir sey yazmadi. Deney, olcmeyi amacladigi seyi hic
    olcmedi -- sifir fark, "iz yok"un degil "yazma yok"un sonucuydu.

    Tekrar denenecekse ONCE belgeyi kirletmek gerekir (bir slaydi acmak
    kucuk resmi yeniden uretiyor olabilir, ki bu da kirletir). Kirli
    olmadan yapilan her tur, ayni bos sonucu verir.

38pt uzeri hala kalibre EDILMEMIS durumda ve compose._Page.size_of'un
puntoyu oraya cikarmamasinin sebebi bu -- yukaridaki deneyin sonucu degil,
olcumun hic yapilmamis olmasi.
"""
import shutil, sys
from pathlib import Path

ROOT = Path(r"c:\Users\erman\Desktop\Art\storyline-mcp")
sys.path.insert(0, str(ROOT))
from storyline_mcp import compose, model, shapes
from storyline_mcp.authoring import _apply_text
from storyline_mcp.package import StoryPackage

SIZE = int(sys.argv[1]) if len(sys.argv) > 1 else 38
BOX_W = 300.0

BLANK = Path(r"c:\Users\erman\Desktop\Art\test\bos.story")
OUT = Path(r"c:\Users\erman\Desktop\Art\test\g2\KALIBRE.story")
shutil.copy2(BLANK, OUT)

pkg = StoryPackage(OUT)
part, ref = next((p, r) for p, r in model.slide_index(pkg).items()
                 if (r.scene_name or "").lower().startswith("ana"))
root = pkg.parse(part)
compose.clear_slide(root)
sw, sh = shapes.slide_size(root)

bg = shapes.clone_shape(shapes.find_seed(pkg, "rect")[0], name="Zemin")
shapes.set_shape_slide_size(bg, sw, sh)
shapes.set_loc(bg, 0, 0, sw, sh)
shapes.set_fill(bg, "#FFFFFF")
shapes.add_shape(root, bg, to_back=True)
_apply_text(root, bg, "")

# Gercek kelimeler, artan karakter sayisi
SAMPLES = ["Devam Et", "Bilgi Guvenligi", "Nereden devam", "Nereden devam etmek",
          "Nereden devam etmek is", "Nereden devam etmek istersin?"]

SLOT = 82.0
y = 12.0
for text in SAMPLES:
    box = shapes.clone_shape(shapes.find_seed(pkg, "textBox")[0], name=f"n{len(text)}")
    shapes.set_shape_slide_size(box, sw, sh)
    shapes.set_loc(box, 20, y, 20 + BOX_W, y + SLOT - 8)
    shapes.add_shape(root, box)
    _apply_text(root, box, text, color="#000000", size=SIZE)
    # sag kenari isaretle: sarma noktasi gorunsun
    rule = shapes.clone_shape(shapes.find_seed(pkg, "rect")[0], name=f"c{len(text)}")
    shapes.set_shape_slide_size(rule, sw, sh)
    shapes.set_loc(rule, 20 + BOX_W, y, 20 + BOX_W + 2, y + SLOT - 8)
    shapes.set_fill(rule, "#FF0000")
    shapes.add_shape(root, rule)
    _apply_text(root, rule, "")
    y += SLOT

pkg.replace_xml(part, root)
rep = pkg.save(OUT, backup=False)
print(f"{SIZE}pt, kutu {BOX_W} birim, verified={rep['verified']['ok']}")
per_line = int(BOX_W / (SIZE * shapes.CHAR_WIDTH_RATIO))
print(f"mevcut tahmin: satir basina {per_line} karakter")
for t in SAMPLES:
    print(f"  {len(t):>2} harf  tahmin {shapes._wrapped_lines(t, per_line)} satir  {t!r}")
