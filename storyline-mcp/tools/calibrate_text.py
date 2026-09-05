"""Kalibrasyon, cakismayan aralikla. Tek punto, artan uzunluk.

Her ornek kendi genis yuvasinda; hangi uzunluktan itibaren ikinci satira
sardigi gozle sayilabilsin diye. Kelime sarmasini olcuyoruz, o yuzden
dizgiler gercek kelimelerden olusuyor.

DOSYA TURU YOLU DENENDI VE OLU CIKTI -- yol KAPALI. (Bu paragraf 2026-09-05'te
duzeltildi; onceki hali "yol KAPALI DEGIL" diyordu ve bir sonraki okuyanı olu
bir deneye gonderiyordu. Nitekim gonderdi.)

    Fikir: kutulari grow=True yapip Storyline'da acmak, kaydetmek ve
    yuksekligi dosyadan geri okumak.

    Ilk deneme (2026-08-14) sifir fark verdi ve "Storyline yeniden
    boyutlandirmiyor" diye okundu. Yanlisti: `save_and_close` Ctrl+S'i yalnizca
    baslik kirliyse gonderiyor, bir dosyayi acmak onu kirletmiyor. Storyline
    hicbir sey yazmadi -- deney olcmeyi amacladigi seyi HIC olcmedi. O yuzden
    `storyline_ctl.make_dirty` ve `tools/dirty_gate.py` yazildi.

    IKINCI DENEME YAPILDI, ve bu sefer kapiyla: `tools/calibrate_diacritics.py`
    ayni turu kirlilik kapisi acikken kosturdu. Dosya GERCEKTEN degisti
    (2.2 MB -> 1.0 MB, Storyline paketi bastan yazdi) ama kutu yukseklikleri
    DEGISMEDI -- en buyuk puntoda, metnin kutuya sigmasi matematiksel olarak
    imkansizken bile. autoFit="resize" bayragi duruyordu.

    Sonuc, `shapes.py`'de cekirdek kural olarak kayitli: Storyline buyumeyi
    CIZIM ANINDA hesapliyor ve dosyaya geri YAZMIYOR. Dosya yazilan kutuyu
    tutuyor, cizilen kutuyu degil. Yani metin yuksekligi DOSYADAN olculemez --
    kac tur denenirse denensin.

GERIYE KALAN YOL GORUNTU, ve o da BUGUN OTOMATIKLESTIRILEMIYOR:

    `tools/shoot.py` Storyline'in gercek cizimini yakaliyor, ama dosyayi STORY
    VIEW'da aciyor ve kucuk resimleri goruyor -- slayt secilemiyor (belge
    dizesinde yazili: "belirli bir slayda bakmak icin o slaydi ELLE acmak
    gerekiyor"). Kucuk resimden sarma noktasi sayilamaz.

    Bu bandi genisletmek icin once shoot.py'nin belirli bir slaydi acabilmesi
    gerekiyor. O olmadan kalan tek yol elle gozle saymaktir -- ki bu aracin
    varlik sebebi o isi silmek.

BANDIN DISINDA KALANIN BEDELI OLCULDU (2026-09-05, uretilmis kurs): 248
yazidan 26'si bant disi, 20'si 11pt. 11pt kaza degil, eyebrow'un tasarim
puntosu; `page.text`'in kucultme dongusu ona hic girmiyor ve bu bir kez
gerilemeye yol acti (bkz. DEVIR "uc Eyebrow tasmasi"). Yani bant disi vakalar
icin "sigiyor" demek, olculmemis bir sayiya guvenmek olur -- olculere
`unmeasured` olarak AYRICA sayilmalarinin sebebi bu.

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
