"""B1 kuyruğu: modelin taşma iddiası GERÇEK mi, artefakt mı?

B1 govdesinde 24 tasma adayinin 24'u de artefakt cikti (sarma niteligi,
kirpma varsayimi, esik-sabit karismasi). Bu turun sorusu, kalan iddianin
o listeye katilip katilmayacagi.

FIKSTUR URETIMIN KENDI CIKTISI, uydurma degil: golden'in CANLI vakasi --
`pick_template_for_question` + `add_question`, gomulu tohum, canli cerceve
dali. Elle yerlestirilmis tek sekil yok.

NEDEN BU VAKA, `uzun/orta` DEGIL. `uzun/orta` daha buyuk tasma uretiyor ama
FOTOGRAFLANAMAZ: sik kutulari y=1135..1282'de, yani 1080 birimlik slaydin
DISINDA (bu, %118.7 bulgusunun kendisi). Bos tuvale tasan metin cekilemez.
GORUNUR_ALT dersi: yakalama sinirinin olculecek seyi kapsadigini varsayma.
Bu tur icin sinir slaydin kendi tuvali, ve once dogrulandi.

TEK KAREDE POZITIF VE NEGATIF KONTROL. Ucu de ayni slaytta:

    13pt 'Sakin...'  kutu 97  model 2 satir  ->  TASAR  (139 > 97)
    13pt 'Ayni...'   kutu 97  model 1 satir  ->  sigar  ( 69 < 97)
    21pt kok         kutu 588 model 5 satir  ->  sigar  (560 < 588)

Ayni punto, ayni kutu yuksekligi, farkli metin: iki 13pt kutu birbirinin
kontrolu. Negatif kontrol olmadan "tasiyor" gozlemi, modelin dogru oldugunu
degil yalnizca bir seyin tastigini soyler.

KARAR KURALI -- KAREYE BAKMADAN YAZILDI:

  1) 'Sakin' 2 SATIR ciziliyorsa
        Model satir sayisini dogru veriyor; 2 x 69.4 = 139 > 97, kutu
        gercekten yetersiz. TASMA GERCEK. Duzeltme koke (uzay karisikligi)
        gider, modele degil. MEASURE_* sabitleri gecerli kalir.

  2) 'Sakin' 1 SATIR ciziliyorsa
        Model sarmayi FAZLA sayiyor: CHAR_WIDTH_RATIO 1920 uzayinda gercek
        kapasiteden dar. Tasma ARTEFAKT ve 24/24 listesine katilir.
        Oran 1920'de ayrica olculmeli.

  3) 'Ayni' 2 veya daha COK satir ciziliyorsa
        Negatif kontrol oldu. Model AZ tahmin ediyor -- kutu metinden kisa
        cikar ve komsusuna biner, yani guvensiz yon. Turun tamami suphelidir
        ve once bu aciklanir.

  4) Kok 5 SATIRDAN COK ciziliyorsa
        Hata 13pt'ye ozgu degil, olcek genelinde. Ayrimi yapan sey ucuncu
        satirin puntosunun farkli olmasi.

  5) Olculen satir ADIMI 69.4'ten (13pt) veya 112.1'den (21pt) sapiyorsa
        MEASURED_VSCALE@1920 = 2.990 ya da MEASURE_LEADING = 1.785 yanlis.
        Sapmanin yonu hangisini gosterdigini soyler; ikisi de ayni carpimin
        parcasi oldugu icin tek kare ikisini AYIRAMAZ, yalnizca carpimi
        duzeltir. Ayirmak icin ikinci punto gerekir -- bu turda kok tam o
        isi goruyor (21pt), cunku ikisi de ayni vscale'i kullanir ama farkli
        puntoyu.

BEDAVA UCUNCU OLCUM: satir adimi bu turda UCUNCU kez bagimsiz olculuyor
(once 720'de iki kosu, sonra OLCEK turu). 1920 uzayinda ilk kez URETIM
CIKTISI uzerinde olculecek -- onceki 1920 olcumu elle kurulmus fikstuurdu.

    python tools/goz_b1.py
    # sonra: Storyline'da ac, Preview, kare al
    # python tools/kare_satir.py kare.png --bolge X0 X1 Y0 Y1 --bekle N
    #        --uzay 1920 --punto 13
"""

from __future__ import annotations

import shutil
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from storyline_mcp import authoring, model, preview, shapes
from storyline_mcp.package import StoryPackage

KAYNAK = ROOT.parent / "test" / "bos.story"
CIKTI = ROOT.parent / "test" / "_referans" / "B1_KARE.story"

# golden.CANLI ile AYNI girdi. Kopyalanmadi, ithal edildi: iki yerde ayri
# yazilan bir fikstuur er ya da gec ayrisir ve o zaman bu tur baska bir
# seyi olcuyor olur (K12).
from golden import CANLI as _CANLI          # noqa: E402
_AD, KOK, SIKLAR = _CANLI


def main() -> int:
    if not KAYNAK.is_file():
        print(f"Kaynak yok: {KAYNAK}")
        return 2

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        shutil.copy2(KAYNAK, CIKTI)
        pkg = StoryPackage(CIKTI)
        picked = authoring.pick_template_for_question(pkg, KOK, SIKLAR)
        made = authoring.add_question(pkg, picked["template"], KOK, SIKLAR,
                                      [0], eyebrow="Bolum 1")
        pkg.save(CIKTI, backup=False)

        # Slaydi kursun BASINA al ki Preview dogrudan ona acilsin. Preview'i
        # elle gezdirmek, turun gecerliligini bir kolaylik adimina baglar
        # (K13) -- ve yanlis slayta bakildigini kare soylemez.
        pkg = StoryPackage(CIKTI)
        part = next(p for p, r in model.slide_index(pkg).items()
                    if r.basename == made["new_slide"])
        ref = model.slide_index(pkg)[part]
        story = pkg.parse("story/story.xml")
        story.set("pG", ref.scene_guid)
        sahne = story.find("sceneLst")
        for s in list(sahne):
            if s.get("g") == ref.scene_guid:
                sahne.remove(s)
                sahne.insert(0, s)
                id_lst = s.find("sldIdLst")
                rels = {v: k for k, v in model._rel_map(pkg).items()}
                rid = rels.get(part)
                for e in list(id_lst or []):
                    if (e.text or "").strip() == rid:
                        id_lst.remove(e)
                        id_lst.insert(0, e)
                break
        pkg.replace_xml("story/story.xml", story)
        rapor = pkg.save(CIKTI, backup=False)

    pkg = StoryPackage(CIKTI)
    part = next(p for p, r in model.slide_index(pkg).items()
                if r.basename == made["new_slide"])
    root = pkg.parse(part)
    sw, sh = shapes.slide_size(root)
    yatay, hk = shapes.hscale(sw)
    dikey, vk = shapes.vscale(sw)

    print(f"uretildi: {CIKTI.name}  verified={rapor['verified']['ok']}")
    print(f"  sablon {picked['template']}  slayt {made['new_slide']} "
          f"({sw:.0f}x{sh:.0f}), kursun ILK slaydi")
    print(f"  cerceve dali: framed={made.get('framed')}")
    print(f"  carpanlar: {hk}={yatay:.3f}  {vk}={dikey:.3f}")

    lo, hi = shapes.CALIBRATED_RANGE
    hedefler = []
    for shp in list(root.find("shapeLst") or []):
        text = model.shape_text(root, shp.get("g", "")).strip()
        rect = shapes.shape_rect(shp)
        if not text or not rect:
            continue
        _c, size, _b, _a = preview._text_style(shp)
        if not (lo <= size <= hi):
            continue
        w, h = rect[2] - rect[0], rect[3] - rect[1]
        per = max(1, int(w / (size * yatay * shapes.CHAR_WIDTH_RATIO)))
        satir = sum(shapes._wrapped_lines(p, per) for p in text.split("\n"))
        adim = size * dikey * shapes.MEASURE_LEADING
        gerek = shapes.measured_text_height(text, size, w, sw,
                                            wrap=shapes.wraps(shp))
        hedefler.append((size, rect, h, gerek, satir, adim, text))

    # YAKALAMA SINIRI ONCE DOGRULANIR, sonra tur kurulur. Bu turun ilk
    # tasarimi (`uzun/orta`) tam burada elendi: kutulari y=1135..1282'deydi,
    # yani 1080 birimlik tuvalin disinda. Sinir varsayilmis olsaydi kare
    # cekilir, hicbir sey gorunmez, ve "tasma yok" diye okunurdu.
    disarida = [h for h in hedefler if h[1][3] > sh]
    print(f"\nYAKALAMA SINIRI: slayt tuvali 0..{sh:.0f} birim "
          f"(16:9 -> oynaticida tamami cizilir, olculdu)")
    for size, rect, *_ in hedefler:
        yer = "KAREDE" if rect[3] <= sh else "*** TUVAL DISI ***"
        print(f"  {size:.0f}pt y={rect[1]:.0f}..{rect[3]:.0f}  {yer}")
    if disarida:
        print(f"\n{len(disarida)} hedef tuval disinda — bu tur GECERSIZ.")
        return 1

    print(f"\nGIRDI SPESIFIKASYONU ve MODELIN IDDIASI:")
    print(f"{'punto':>6} {'kutu':>6} {'gerek':>6} {'satir':>6} {'adim':>7}  iddia")
    for size, _rect, h, gerek, satir, adim, text in hedefler:
        iddia = "TASAR" if gerek > h + 0.1 / 100 * sh else "sigar"
        print(f"{size:>5.0f}p {h:>6.0f} {gerek:>6.0f} {satir:>6} {adim:>7.1f}  "
              f"{iddia:<6} {text[:30]!r}")

    print("\nOLCULECEK: her kutuda GERCEK satir sayisi ve satir adimi.")
    print("Karar kurali bu dosyanin bas yorumunda, KAREYE BAKILMADAN yazildi.")
    print("\nkare_satir.py --bekle degerleri (modelin iddiasi):")
    for size, rect, _h, _g, satir, _a, text in hedefler:
        print(f"  --bekle {satir} --punto {size:.0f} --uzay {sw:.0f}"
              f"   # y={rect[1]:.0f}..{rect[3]:.0f}  {text[:24]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
