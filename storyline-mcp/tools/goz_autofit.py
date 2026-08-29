"""autoFit ne yapıyor: büyütüyor mu, kırpıyor mu? Gözle bakılacak fikstür.

BIRINCI TUR GECERSIZDI ve sebebi kayda deger. Sekiller kendi slaytlarindan
alinip TEK bir slayda kopyalanmisti; genislikler birebir korundu ama SLAYT
BOYUTU korunmadi:

    referans.story IKI koordinat uzayi tasiyor
        720x540    devralinan slaytlar
        1920x1080  kurucunun bestledigi soru slaytlari

slide12'nin koku 1612.8 birim genis -- 1920'nin %84'u. 720'lik bir slayda
kopyalaninca slaydin %224'u oldu, metin tek satira sigdi ve hicbir sey
kirpilmadi. Yani o satir autoFit hakkinda hicbir sey soylemedi.

Ve KONTROL DUSMEDI: autoFit="none" satiri da kirpilmadi. Kirpma bozuk oldugu
icin degil -- metin gercekten tek satira sigdigi icin. Tahmin 21 karakter/satir
diyordu, 25 karakter tek satirda cizildi. Yani sarma tahmini FAZLA veriyor.

Bu surum iki seyi duzeltiyor:

  1. HER SEKIL KENDI UZAYINDA. 1920'lik sekil 1920'lik bir slayda, 720'lik
     sekil 720'lik bir slayda konur. Fikstuur referans.story'nin KOPYASI
     uzerine kurulur, bos.story uzerine degil.
  2. KONTROL KIRPILMAK ZORUNDA. Metin, tahmin %40 fazla verse bile kutuya
     sigmayacak kadar uzun secilir. Negatif kontrol dusmeden hicbir sonuc
     okunamaz -- birinci turun ogrettigi sey tam olarak bu.

    python tools/goz_autofit.py
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
OUT = ROOT.parent / "test" / "_referans" / "GOZ2.story"

# Kontrol metni: 720 uzayinda 219 birim genis, 14pt bir kutuda tahmin 21
# karakter/satir diyor. Tahmin %40 fazla verse (30 kar/satir) bile bu metin
# 4+ satir eder ve 36 birimlik kutuya sigmaz. Kirpilmamasi imkansiz.
UZUN = ("Bu metin kutuya sigmayacak kadar uzundur ve dort bes satir "
        "gerektirir; kirpilmadan durabilmesi mumkun degildir.")


def _slaytlar(pkg, genislik, kac):
    """Verilen koordinat uzayında `kac` tane slayt.

    Uc satir TEK slayda sigmiyordu: iki karsilastirma kutusu 779 birim,
    slayt 1080 -- etiketlerle birlikte 1157 ediyordu ve kontrol satiri
    slaydin disina dusuyordu. Sikistirmak yerine ayri slayt: sikisik bir
    fikstuur, olculen seyin kendisini bozar.
    """
    out = []
    for part, ref in model.slide_index(pkg).items():
        root = pkg.parse(part)
        if abs(shapes.slide_size(root)[0] - genislik) < 1:
            out.append((part, ref))
            if len(out) == kac:
                break
    return out


def _kaynak_sekil(pkg, slayt, kosul):
    for part, ref in model.slide_index(pkg).items():
        if ref.basename != slayt:
            continue
        root = pkg.parse(part)
        for el in root.iter():
            rect = shapes.shape_rect(el)
            if not rect:
                continue
            metin = model.shape_text(root, el.get("g") or "").strip()
            if metin and kosul(el, rect, metin):
                return el, rect, shapes.slide_size(root)
    return None, None, None


def _yaz(pkg, part, ust, cift):
    """ust: tek satir (ustte). cift: YAN YANA iki satir.

    Neden yan yana: karsilastirilan iki kutu 779 birim ve slayt 1080. Ust uste
    konunca ikincisi slaydin DISINA dusuyordu -- ucuncu turda tam olarak oyle
    oldu ve gozle bakan kisi onu gri zeminde gordu. Karsilastirilacak iki sey
    ayni karede ve ayni yukseklikte durmali."""
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

    def koy(ad, sekil, rect, etiket, x, y, genislik):
        lbl = shapes.clone_shape(shapes.find_seed(pkg, "textBox")[0],
                                 name=f"ETIKET_{ad}")
        shapes.set_shape_slide_size(lbl, sw, sh)
        shapes.set_loc(lbl, x, y, x + genislik, y + 24 * olcek)
        shapes.set_text_flow(lbl, vertical="t", grow=False)
        shapes.add_shape(root, lbl)
        _apply_text(root, lbl, etiket, color="#B00000", size=10 * olcek)

        kopya = shapes.clone_shape(sekil, name=f"OLCU_{ad}", keep_triggers=False)
        shapes.set_shape_slide_size(kopya, sw, sh)
        # Kutu YUKSEKLIGI ve GENISLIGI birebir korunur -- olculen sey bu.
        shapes.set_loc(kopya, x, y + 26 * olcek, x + (rect[2] - rect[0]),
                       y + 26 * olcek + (rect[3] - rect[1]))
        shapes.add_shape(root, kopya)
        return y + 26 * olcek + (rect[3] - rect[1])

    kenar = 20 * olcek
    y2 = kenar
    if ust is not None:
        y2 = koy(ust[0], ust[1], ust[2], ust[3], kenar, kenar,
                 sw - 2 * kenar) + 26 * olcek
    for i, (ad, sekil, rect, etiket) in enumerate(cift):
        x = kenar + i * ((sw - 2 * kenar) / 2)
        koy(ad, sekil, rect, etiket, x, y2, (sw - 2 * kenar) / 2 - 10 * olcek)
    pkg.replace_xml(part, root)


def main() -> int:
    if not REF.is_file():
        print(f"Referans yok: {REF}")
        return 2

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        kaynak = StoryPackage(REF)
        buyuk_el, buyuk_r, buyuk_boyut = _kaynak_sekil(
            kaynak, "slide12.xml",
            lambda e, r, t: e.get("autoFit") == "resize" and 110 < r[3] - r[1] < 125)
        # SENTETIK METIN DEGIL, GERCEK KUSUR. Bu sekil referansta
        # %57.5 tasiyor (kutu 779, gereken 1226) ve tasmasi 17 PARAGRAFTAN
        # geliyor -- sarmadan bagimsiz, yani wrap tuzagina dusmez.
        # Sentetik uzun metin, sarmayan bir kutuda tek satir cizilip
        # ucuncu turu bozmustu.
        kucuk_el, kucuk_r, kucuk_boyut = _kaynak_sekil(
            kaynak, "slide12.xml",
            lambda e, r, t: e.get("autoFit") == "def" and t.count("\n") > 5)
        if buyuk_el is None or kucuk_el is None:
            print("Hedef sekiller bulunamadi.")
            return 2
        print(f"kaynak sekiller:")
        print(f"  resize  slide12  {buyuk_r[2]-buyuk_r[0]:.0f}x"
              f"{buyuk_r[3]-buyuk_r[1]:.0f}  slayt {buyuk_boyut[0]:.0f}")
        print(f"  def     slide6   {kucuk_r[2]-kucuk_r[0]:.0f}x"
              f"{kucuk_r[3]-kucuk_r[1]:.0f}  slayt {kucuk_boyut[0]:.0f}")

        shutil.copy2(REF, OUT)
        pkg = StoryPackage(OUT)

        hedefler = _slaytlar(pkg, buyuk_boyut[0], 2)
        if len(hedefler) < 2:
            print("1920 uzayinda iki slayt bulunamadi.")
            return 2
        (p_a, r_a), (p_b, r_b) = hedefler

        none_el = shapes.clone_shape(kucuk_el, name="gecici", keep_triggers=False)
        none_el.set("autoFit", "none")

        # UCU DE AYNI UZAYDA (1920) -> TEK slayda yazilir. Iki ayri _yaz
        # cagrisi ayni slayda denk geldiginde ikincisi birincisini SILIYORDU
        # (clear_slide) ve resize satiri kayboluyordu. Geri okuma bunu
        # "resize BULUNAMADI" diye yakaladi; fikstuur kendini dogrulamasaydi
        # tura oyle girilecekti -- dorduncu kez.
        # SLAYT A = KURSUN ILK SLAYDI, ve oraya KRITIK SORU konur.
        # Preview ilk slayttan basliyor; oynatici icinde gezinmek olculecek
        # seyle ilgisiz bir degisken ve kaldirilabiliyorsa kaldirilir.
        _yaz(pkg, p_a, None,
             [("def", kucuk_el, kucuk_r,
               "SOL: autoFit=def    17 paragraf, kutu 779 / olcum 1003"),
              ("none", none_el, kucuk_r,
               "SAG: autoFit=none   AYNI sekil -> KIRPMA KONTROLU")])
        # SLAYT B: resize satiri (ikincil soru, kucuk kutu).
        _yaz(pkg, p_b,
             ("resize", buyuk_el, buyuk_r,
              "autoFit=resize   kutu 117 / olcum 139  -> buyur mu?"), [])
        # FIKSTUR SLAYTLARINI KURSUN BASINA AL.
        #
        # Preview ilk slayttan baslar ve devralinan bos bir slayt oradaydi;
        # fikstuur 5.4'te kaliyordu, yani Preview'da ona ulasmak icin oynatici
        # icinde gezinmek gerekiyordu. Gezinme, olculecek seyle ilgisiz bir
        # degisken -- kaldirilabiliyorsa kaldirilir.
        story = pkg.parse("story/story.xml")
        sahne_lst = story.find("sceneLst")
        hedef_guid = {r_a.scene_guid, r_b.scene_guid}
        tasinan = [s for s in sahne_lst if s.get("g") in hedef_guid]
        for offset, sahne in enumerate(tasinan):
            sahne_lst.remove(sahne)
            sahne_lst.insert(offset, sahne)
        # Sahne icinde de basa: slayt sirasi sldIdLst'in sirasidir.
        rels = {v: k for k, v in model._rel_map(pkg).items()}
        for sahne in tasinan:
            id_lst = sahne.find("sldIdLst")
            if id_lst is None:
                continue
            for part in (p_a, p_b):
                rid = rels.get(part)
                for el in list(id_lst):
                    if (el.text or "").strip() == rid:
                        id_lst.remove(el)
                        id_lst.insert(0, el)
        # BASLANGIC SAHNESI. Sahne SIRASINI degistirmek yetmedi: Preview yine
        # bos bir slaytta acildi. Baslangic ayri bir isaret ve story kokunun
        # `pG` niteliginde duruyor -- Story View'daki kirmizi bayrak bu.
        # Olculdu: pG=ccdf3166 idi ve o 'Ana Menu' sahnesinin guid'i.
        #
        # Bu, "sira = baslangic" varsayiminin sessizce yanlis olmasiydi;
        # Preview acildi, kare uretildi, ve kare olculecek seyi HIC
        # icermiyordu. Ureten bir deney, cevap veren deney degildir.
        story.set("pG", r_a.scene_guid)
        pkg.replace_xml("story/story.xml", story)

        rapor = pkg.save(OUT, backup=False)

    print(f"\nuretildi: {OUT.name}  verified={rapor['verified']['ok']}")
    print(f"  slayt A: {r_a.basename}  (1. satir: resize)")
    print(f"  slayt B: {r_b.basename}  (2. ve 3. satir yan yana)")

    # FIKSTURU GERI OKU VE KONTROLUN KIRPILACAGINI KANITLA.
    #
    # Uc tur ust uste gecersiz cikti ve ucunde de sebep ayniydi: kurulumun
    # dogru oldugu VARSAYILDI. Sirasiyla koordinat uzayi, metin uzunlugu ve
    # wrap niteligi -- her seferinde klonun getirdigine guvenildi ve her
    # seferinde tura girdikten SONRA anlasildi.
    #
    # Bu blok, yazilan dosyadan okur (bellekteki nesneden degil) ve kontrol
    # satirinin kirpilmak ZORUNDA oldugunu gosterir. Gosteremezse fikstur
    # teslim edilmez.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        geri = StoryPackage(OUT)
        bulunan = {}
        for part, _ref in model.slide_index(geri).items():
            root = geri.parse(part)
            genislik, _h = shapes.slide_size(root)
            sl = root.find("shapeLst")
            for s in list(sl) if sl is not None else []:
                ad = s.get("name") or ""
                if not ad.startswith("OLCU_"):
                    continue
                rect = shapes.shape_rect(s)
                metin = model.shape_text(root, s.get("g") or "").strip()
                from storyline_mcp import preview as _pv
                _c, punto, _b, _a = _pv._text_style(s)
                sarar = shapes.wraps(s)
                bulunan[ad[5:]] = dict(
                    alt=rect[3], slayt_h=shapes.slide_size(root)[1],
                    kutu=rect[3] - rect[1], genislik=rect[2] - rect[0],
                    punto=punto, sarar=sarar, harf=len(metin),
                    gereken=shapes.measured_text_height(
                        metin, punto, rect[2] - rect[0], genislik, wrap=sarar))

    print(f"\n=== FIKSTUR GERI OKUNDU ===")
    print(f"  {'satir':<10}{'wrap':<7}{'harf':>6}{'kutu':>8}{'gereken':>9}"
          f"{'pay':>8}")
    for ad in ("resize", "def", "none"):
        d = bulunan.get(ad)
        if d is None:
            print(f"  {ad:<10}BULUNAMADI")
            continue
        pay = (d["gereken"] - d["kutu"]) / d["kutu"] * 100
        print(f"  {ad:<10}{'sarar' if d['sarar'] else 'SARMAZ':<7}"
              f"{d['harf']:>6}{d['kutu']:>8.0f}{d['gereken']:>9.0f}{pay:>7.0f}%")

    kontrol = bulunan.get("none")
    if kontrol is None:
        print("\nFIKSTUR TESLIM EDILMEDI: kontrol satiri geri okunamadi.")
        return 1
    # SARMA SARTI YOK, ve bu bilincli. Bu metnin tasmasi 17 PARAGRAFTAN
    # geliyor: sarmayan bir kutuda bile 17 satir 17 satirdir. Ucuncu turu
    # bozan sey sentetik TEK paragrafli metindi -- sarmayinca tek satira
    # inip kayboluyordu. Kosul artik dogru yerde: TASMA PAYI.
    # SATIRLAR SLAYDIN ICINDE MI. Ucuncu turda kontrol satiri slaydin BEYAZ
    # alaninin disinda, gri zeminde ciziliyordu -- ve kendi dogrulamam bunu
    # sormuyordu. Slayt disina tasan bir satir, gozle bakan kisinin "yok"
    # diye okuyacagi bir satirdir.
    tasan_satir = [ad for ad, d in bulunan.items() if d["alt"] > d["slayt_h"]]
    if tasan_satir:
        print(f"\nFIKSTUR TESLIM EDILMEDI: {tasan_satir} satiri slaydin "
              "DISINDA.\nGozle bakan kisi onu goremez ya da eksik goruyor "
              "sanir.")
        return 1

    eksik = [ad for ad in ("resize", "def", "none") if ad not in bulunan]
    if eksik:
        print(f"\nFIKSTUR TESLIM EDILMEDI: {eksik} satiri yazilmamis. Iki _yaz "
              "cagrisi\nayni slayda denk geldiyse ikincisi birincisini silmis "
              "olabilir.")
        return 1

    # Esik OLCULEN gurultu bandindan turetildi: referansta sahte tasmalar
    # %3.4-9.4 araliginda kumelendi, gercekler %50+. Esik ikisinin arasinda.
    GURULTU_TAVANI = 9.4
    pay = (kontrol["gereken"] - kontrol["kutu"]) / kontrol["kutu"] * 100
    if pay < GURULTU_TAVANI * 3:
        print(f"\nFIKSTUR TESLIM EDILMEDI: kontrol yalnizca %{pay:.0f} tasiyor."
              f"\nOlculen sahte tasma bandi %3.4-{GURULTU_TAVANI}; ayrilmak "
              f"icin en az %{GURULTU_TAVANI * 3:.0f} gerekir.")
        return 1
    print(f"\nKONTROL SAGLAM: %{pay:.0f} tasma (gurultu bandi %{GURULTU_TAVANI} "
          "civari).\nBAK: 3. satir kesik degilse tur yine gecersizdir.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
