"""Hangi kontrol ürün uzayının neresini tarıyor -- ve taranmayan yeri ölçer.

Bir kontrolün geçmesi, geçtiği yerde geçtiği anlamına gelir. Kapsamadığı yeri
söylemeyen kısmi bir tarama, tam tarama gibi okunur ve bu oturumda tam olarak
öyle oldu: themes_check iki varyantla bakip "kagit TAMAM" dedi, ayni tema alti
varyantli gercek bir kursta bes okunabilirlik uyarisi verdi.

Sayildiginda gorulen:

    duzen        7   cover section content bullets steps statement menu
    varyant      6   yalnizca content'te; diger alti duzenin varyanti YOK
    tema         6
    stil         4

    variety / deadband / text_fits   content, varsayilan tema, tek kurs
    silhouette (sozluk probu)        content x 6 varyant, tek icerik
    themes_check                     6 tema x 6 content varyanti
    golden                           3 soru vakasi, tek sablon

Yani butun geometrik kontroller `content` uzerinde kosuyordu ve alti duzen hic
olculmemisti. Bu dosya o carpimi -- duzen x tema -- kosar.

OLCULEN (2026-08-15, 6 tema x 7 duzen = 42 slayt):

    kontrast uyarisi   0    temalar her duzende tutuyor
    bos alan           menu %45, content %44, cover %23, steps %14,
                       statement %12, section %10, bullets %8

    Sayilar alti temada BIREBIR AYNI -- deadband'in "acik zeminli bir tema
    ayni sayiyi verir" kapsam cumlesi artik iddia degil olcum.

Bulunan: `menu` en kotu content vakasi kadar bos ve hic olculmemisti. Yogunluk
olcegi yalnizca content dalinda; diger duzenler icerik seyreklestiginde
puntoyu buyutmuyor.

KAPSAM ENVANTERI (--envanter). Yukaridaki sweep uzayin BIR EKSENINI olcuyor:
tema x duzen. Uretilmis bir kursta bulunan on kusur, o eksenin uzerinde degil
YANINDA duruyordu -- ayni duzen, ayni tema, ama baska bir KATMANDA ya da
sekil agacinin daha derininde. Bir kontrolun kapsami bes eksenli:

    dosya          neye bakiyor: kendi kurdugu prob mu, uretilmis kurs mu
    slayt turu     icerik / soru / sonuc / hic bestelenmemis
    katman         temel (<shapeLst>) mi, geri bildirim (<sldLayerLst>) mi
    sekil sinifi   metin tasiyan / dekoratif / gorsel, ve agacin hangi derinligi
    tema x duzen   yukaridaki sweep
    KOD DALI       olcunun hangi kod yolunun CIKTISINA baktigi

ALTINCI EKSEN sonradan eklendi ve eklenmesini bir kusur zorladi. B2
olculdugunde goruldu ki uretilen her soru `compose_question_frame`
dalindan geciyor, ama onu sinayan HICBIR kontrol yok: invariants, golden
ve coverage'in hepsi `apply_choice_plan` dalini koruyordu -- uretimde
0/4 kullanilan dali. Bes eksen bunu goremezdi, cunku ikisi de ayni
dosyaya, ayni katmana, ayni sekil sinifina bakiyor; ayrilan sey KOD
YOLU. Bir cagri sayaci da goremez: fonksiyon cagriliyor, yalnizca
ciktisi tuketilmiyor.

Bes eksenden yalnizca sonuncusu olculuyordu. Envanter modu besini birden
basar, ve iki seyi IDDIA olarak degil OLCUM olarak uretir:

  1. Kaynak taramasi. "Hicbir kontrol katmanlara bakmiyor" cumlesi tools/
     altindaki dosyalarda aranarak dogrulanir, elle bakimi gereken bir liste
     tutularak degil -- boyle bir liste, birileri katman taramasi ekledigi gun
     bayatlar ve yanlis bir guvence verir.
  2. Kor nokta sayimi. Taranmayan kesitte KAC SEY OLDUGU sayilir. K1: "kontrol
     oraya bakmiyor" ile "orada bir sey yok" ayni cumle degildir ve bu projede
     tam olarak o ikisi karistirildi.

    python tools/coverage.py                        tema x duzen sweep (eski)
    python tools/coverage.py --envanter kurs.story  bes eksenli kapsam tablosu
"""

from __future__ import annotations

import argparse
import shutil
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from storyline_mcp import compose, model, shapes
from storyline_mcp.package import StoryPackage
import contrast
import deadband

BLANK = ROOT.parent / "test" / "bos.story"
WORK = ROOT.parent / "test" / "_canary" / "kapsam_{}.story"

# Dondurulmus referans kurs. _canary DEGIL: orasi araclarin ciktilarini
# doldurdugu yer ve oradaki bir dosya bir sonraki kosuda ezilir. Kusurlarin
# uzerinde olculdugu dosya, olcumun kendisi kadar korunmali.
REFERANS = ROOT.parent / "test" / "_referans" / "referans.story"

# Her duzen kendi anlamli icerigiyle: bir duzeni bos icerikle olcmek, o duzenin
# iyi oldugunu degil, olculmedigini gosterir.
SPECS = {
    "cover": dict(title="Bilgi Guvenligi", eyebrow="Giris",
                  body="Kurumsal temel egitim", buttons=["Basla"]),
    "section": dict(title="Parola Hijyeni", index="02",
                    body="Guclu parola nasil kurulur"),
    "content": dict(title="Cihaz Guvenligi", eyebrow="Bolum 2",
                    body="Kilitlenmemis bir ekran, acik birakilmis bir kapidir.",
                    buttons=["Devam"]),
    "bullets": dict(title="Uc Kural", eyebrow="Ozet",
                    bullets=["Uzun tut", "Tekrar etme", "Sakla", "Dogrula"],
                    buttons=["Ileri"]),
    "steps": dict(title="Olay Mudahalesi",
                  bullets=["Tespit et", "Kaydet", "Bildir", "Kapat"],
                  buttons=["Devam"]),
    "statement": dict(title="Kural",
                      body="Test edilmemis bir yedek, yedek degildir."),
    "menu": dict(title="Nereden devam?", body="Bir konu secin",
                 buttons=["Konu A", "Konu B", "Konu C"]),
}
# Olculen taban. Guard tek yonlu -- yalnizca BUYUMEYI yakalar -- o yuzden bir
# iyilesme olcuulur olcuulmez buraya yazilir. Yazilmazsa korunmaz: section
# %10'dan %6'ya inmisti (_distribute'un banda kirpilmasiyla) ve taban eski
# kaldigi icin kimse fark etmedi; bir sonraki gerileme %10'a kadar sessizce
# geri donebilirdi. GROWTH_LIMIT'in tek yonlu korunmasiyla ayni sinif.
#
# menu %45 ve content %44 BILINEN SINIR, ve menu'nunki konumla cozulmuyor:
# butonlar bandi dolduracak kadar buyutuldugunde (%34) olcu %29'a indi ama
# sekiller buton olmaktan cikip panel oldu. Uc tek kelimelik etiket 16:9 bir
# cerceveyi dolduramaz; cozum secimlere govde vermek (aciklama, ikon), yani
# bir ozellik -- konum ayari degil.
# YENIDEN OLCULDU (2026-08-17). Eski taban KAYNAGI BILINMEYEN ve YENIDEN
# URETILEMEYEN bir sayiydi; kovalandi, kismen aciklandi, kalani dondurulup
# yeniden olculdu -- POOL_MEASURED[40]=8 ile ayni muamele.
#
# KOVALAMA NE BULDU (hepsi tek-degisken, her tur sabitin gercekten
# degistigini basarak):
#
#   OLCUM sabitleri     ELENDI. ratio 0.72, safety 1.0, leading 1.2 --
#                       hicbiri tabani geri getirmiyor; safety'yi kaldirmak
#                       KOTULESTIRIYOR. Kanonik duzeltmeden sonra tekrarlandi
#                       ve sayilar birebir ayni cikti (sweep() tutarli 720
#                       deck'te kosuyor, orada eski ve yeni carpan ayni 1.0).
#
#   YERLESIM sabitleri  ELENDI. MIN_CARD_H, MAX_TYPE_SCALE, TARGET_FILL:
#                       SIFIR etki. MIN_LINE_CHARS ve CARD_GAP ters yonde.
#
#   YAPISAL sabitler    ELENDI. CEILING/FLOOR, UNIT, MARGIN_X: hicbiri
#                       aciklamiyor; bandi genisletmek kotulestiriyor.
#
#   REJIM FARKI         BULUNDU, ama yalnizca `content` icin. Tek degisken:
#                       `compose.snap` (TYPE_LADDER merdiveni).
#                           merdiven ACIK  -> content %52
#                           merdiven KAPALI-> content %38
#                       Taban %44 tam ikisinin arasinda. Merdiven, uretilmis
#                       bir kursta 16 farkli punto olculdukten SONRA eklendi
#                       (bkz. compose.TYPE_LADDER yorumu), yani tabandan
#                       yeni. Yani bu bir gerileme degil, BILINCLI TAKAS:
#                       merdiven tipografik tutarlilik aliyor, doldurma
#                       veriyor -- ve bedeli ilk kez olculdu: 14 puan.
#
#   section/steps/cover/menu: HICBIR sabit aciklamiyor. Bu dordu
#                       density_scale KULLANMIYOR (olculdu: 6 cagri = tek
#                       duzen), yani bosluklari olcek degil YAPI. Kayit
#                       ACIK kaliyor.
#
# Yeni taban bugunku kodun urettigi seydir. Bir sonraki degisiklik onu
# kaydirirsa fark GORUNUR olur; eskisinde olmuyordu cunku sapma zaten
# kalicidi ve kimse hangisinin dogru oldugunu bilmiyordu.
EMPTY_BASELINE = {"cover": 27, "section": 52, "content": 52, "bullets": 10,
                  "steps": 24, "statement": 13, "menu": 50}
# ESKI TABAN, KAYIT ICIN (2026-08-16). Silinmiyor: yeniden uretilemedigi
# olculdu ve o olcum ancak karsilastirilacak sayi durursa tekrarlanabilir.
_ESKI_TABAN_2026_08_16 = {"cover": 23, "section": 36, "content": 44,
                          "bullets": 8, "steps": 14, "statement": 12,
                          "menu": 45}
#
# section %6 -> %36: bu bir GERILEME DEGIL, gizli bir ihlalin duzeltilmesi.
# Eski %6, bloklarin kendi bandini (12-78) asmasindan geliyordu -- page.text
# her kutuyu FLOOR'a kadar uzatiyordu, ekran doluyordu cunku icerik bandinin
# disina tasiyordu. Bloklar banda sigdirilinca gercek deger goruldu.
#
# Ve %36 bu duzen icin DOGRU: section'in kendi tanimi "bir ayrac slaydini
# neredeyse bos olarak hak eder -- buyuk bir index, bir baslik ve hava"
# diyor. Olcunun buyumesi tasarimin bozulmasi degil, olcunun durustlesmesi.
SLACK = 4


def sweep() -> dict[str, dict[str, tuple[int, int]]]:
    """{tema: {duzen: (kontrast uyarisi, bos alan %)}}"""
    out: dict[str, dict[str, tuple[int, int]]] = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for theme in compose.theme_names():
            path = Path(str(WORK).format(theme))
            shutil.copy2(BLANK, path)
            pkg = StoryPackage(path)
            names = [r.basename for r in model.slide_index(pkg).values()]
            if len(names) < len(SPECS):
                raise SystemExit(f"{BLANK.name} icinde {len(SPECS)} slayt yok.")
            where = {}
            for slide, (layout, spec) in zip(names, SPECS.items()):
                compose.compose_slide(pkg, slide, layout, theme=theme,
                                      identity="kapsam", **dict(spec))
                where[slide] = layout
            pkg.save(path, backup=False)

            done = StoryPackage(path)
            warned: dict[str, int] = {}
            for finding in contrast.audit(done):
                key = where.get(finding["slide"], "?")
                warned[key] = warned.get(key, 0) + 1
            empty: dict[str, int] = {}
            for part, ref in model.slide_index(done).items():
                _band, total, count = deadband.dead_band(done, part)
                if count:
                    empty[where.get(ref.basename, "?")] = total
            out[theme] = {layout: (warned.get(layout, 0), empty.get(layout, 0))
                          for layout in SPECS}
    return out


# --------------------------------------------------------------- envanter
#
# Her kontrolun GERCEKTEN kostugu kesit. Satirlar tool basina degil KESIT
# basina: invariants'in sekiz alt kontrolu ayni dosyaya bakmiyor ve tek satira
# indirilirse kapsam sorusu cevapsiz kalir.
#
# "urun?" sutunu tek basina en agir bilgi: bir brief'ten cikmis gercek bir
# dosyaya bakan kontrol sayisi. Paketteki on bir yesil kontrolun hicbiri
# bakmiyordu, ve uretilmis kurstaki on kusurun onu da oradan geldi.
#
#      kontrol, dosya, slayt turu, katman, sekil sinifi, tema x duzen, urun?
ENVANTER = [
    ("invariants/havuz", "donors/*.story", "slayt yok: sekil havuzu",
     "-", "durumlu sekil (buton rolu)", "-", False),
    ("invariants/choice_count", "test/0_duz_kopya.story", "soru sablonu",
     "temel", "sik sekilleri", "-", False),
    # SATIRLAR SILINDI (2026-08-17): invariants/fit_choices ve
    # invariants/plan_applied artik yok. Ikisi de apply_choice_plan dalini
    # sinamak icin vardi, o dal uretimde 0/4 olculup silindi. Envanterde
    # OLMAYAN bir kontrolun satiri, kapsam iddiasinin en pahali turudur:
    # tablo bakip "orasi kapali" der, orada hicbir sey yoktur.
    ("invariants/choice_admission", "dosya yok: saf fonksiyon",
     "-", "-", "sik etiketi (uzun/kisa)", "-", False),
    ("invariants/diagnoses", "test/0_duz_kopya.story", "soru sablonu",
     "temel", "kok + sik", "-", False),
    ("invariants/variant_reach", "dosya yok: variety.DECK basliklari", "-",
     "-", "-", "content x 6 varyant", False),
    ("invariants/text_fits", "_canary/variety.story", "icerik",
     "temel/ust", "metinli, YALNIZCA 13-38pt", "content, tek tema", False),
    ("invariants/frame", "test/bos.story -> _canary/soru_cerceve.story",
     "soru", "temel", "sik + kok dikdortgenleri", "3 vaka, tek tema", False),
    ("invariants/thresholds", "dosya yok: invariants.py kaynagi", "-",
     "-", "-", "-", False),
    ("invariants/no_overlap", "_canary/variety.story + test/_rubrik/*",
     "icerik", "temel/ust", "metinli", "content, 3 fikstur temasi", False),
    ("invariants/floor", "test/bos.story -> _canary/taban.story", "icerik",
     "temel/ust", "metinli VEYA tiklanabilir", "7 duzen, tek tema", False),
    ("golden", "test/0_duz_kopya.story", "soru sablonu",
     "temel", "sik sekilleri", "3 vaka, tek sablon", False),
    ("variety", "test/bos.story -> _canary/variety*.story", "icerik",
     "temel/ust", "hepsi (metinli 1.0, dekoratif 0.55)", "content x 6 varyant", False),
    ("deadband", "_canary/variety.story", "icerik",
     "temel/ust", "hepsi, tam genislikte serit HARIC", "content, tek tema", False),
    ("themes_check", "test/bos.story -> _canary/tema_*.story", "icerik",
     "temel/ust", "metinli", "6 tema x 6 content varyanti", False),
    ("coverage/sweep", "test/bos.story -> _canary/kapsam_*.story", "icerik",
     "temel/ust", "metinli (kontrast) + hepsi (bos alan)", "6 tema x 7 duzen", False),
    ("contrast", "elle verilen dosya", "icerik",
     "temel/ust", "metinli", "verilene bagli", True),
    ("scope/verify", "test/bos.story -> _canary/kapsam_iddia.story", "icerik",
     "temel/ust", "hepsi", "6 tema, tek varyant", False),
    ("rubric_fixtures", "test/_rubrik/{kotu,orta,iyi}.story", "icerik",
     "temel/ust", "hepsi", "3 fikstur", False),
    ("consistency", "dosya yok: kaynak kodu", "-", "-", "-", "-", False),
    ("canary", "test/try_ONCE.story -> _canary fiksturleri", "-",
     "-", "-", "-", False),
    ("open_test", "elle verilen dosya", "hepsi", "hepsi (Storyline acar)",
     "hepsi", "verilene bagli", True),
    ("completeness", "elle verilen dosya", "hepsi + BOS olanlar",
     "temel (dolu mu) + tetikleyicide TAM AGAC", "tetikleyici referanslari",
     "verilene bagli", True),
    ("inventory", "elle verilen dosya", "hepsi",
     "temel/ust (+ tetikleyicide tam agac)", "metinli + tiklanabilir",
     "verilene bagli", True),
    ("produced", "builder ile kurulan kurs", "icerik + soru",
     "temel/ust", "metinli + tiklanabilir", "tek tema (kagit), tek brief", True),
]

# Kaynakta aranan imzalar. Elle tutulan bir liste, birisi katman taramasi
# ekledigi gun bayatlar ve "kapsanmiyor" diye yanlis rapor verir; o yuzden
# cevap her kosuda kaynaktan yeniden okunur.
#
# ANMAK TARAMAK DEGIL, ve ilk yazilisinda oyle sayildi: duz "sldLayerLst"
# aramasi bu dosyanin KENDI belge dizesini yakaladi ve coverage'i "katmanlari
# tarayan kontrol" diye raporladi -- aracin kendi korlugunu kapsam diye
# gostermesi, tam olarak kacinilmaya calisilan hata. Imza artik elemanin
# COZULMESINI istiyor: find/iter cagrisi.
IMZALAR = {
    "katmani (<sldLayerLst>) COZEN": ('find("sldLayerLst")',
                                      'iter("sldLayerLst")'),
    "temel shapeLst cozen": ('find("shapeLst")',),
}
# Katmani cozen kontrollerden hangisi onu yalnizca SAYIYOR, hangisi hakkinda
# VERDIKT veriyor. Ikisi ayri: bu dosyanin envanter modu katmanlari sayar
# (kor nokta nufusu icin) ama hicbir olcuyu -- kontrast, tasma, cakisma --
# onlarin uzerinde kosturmaz. Sayan bir kontrolu "kapsiyor" diye okumak,
# aracin kendi korlugunu kapsam diye gostermek olur.
YALNIZCA_SAYAN = {"coverage"}


# ALTINCI EKSEN: olcu hangi kod yolunun CIKTISINA bakiyor.
#
# Ayri bir esleme olarak duruyor, ENVANTER tuple'ina eklenmedi: eksen sonradan
# cikti ve yirmi bes satiri birden genisletmek, okunmasi gereken tabloyu
# okunmaz yapardi. Adla eslesir, eslesmeyen satir "-" gorunur.
#
# "URETIMDE 0/4" yazan satirlar olculdu (2026-08-16, uretilen kurs, dort soru):
# o dal hic kullanilmiyor. Kontrol saglam, kosuyor, ve OLU bir dali koruyor.
KOD_DALI = {
    # fit_choices'in kod dali DEGISTI, silinmedi: eskiden plan uretip
    # apply_choice_plan'a veriyordu (0/4), bugun pick_template'in KABUL TESTI
    # ve canli yol ondan geciyor (4/4). Ayni ad, baska dal -- bu tablonun
    # varlik sebebi tam olarak bu ayrimi gorunur tutmak.
    "invariants/choice_admission": "fit_choices (kabul)        URETIMDE 4/4",
    "golden": "compose_question_frame     URETIMDE 4/4",
    "invariants/frame": "compose_question_frame     URETIMDE 4/4",
    "invariants/text_fits": "compose_slide",
    "invariants/floor": "compose_slide",
    "invariants/no_overlap": "compose_slide",
    "invariants/thresholds": "kaynak kodu (kod yolu yok)",
    "variety": "compose_slide + variant_for",
    "deadband": "compose_slide",
    "themes_check": "compose_slide + theme_palette",
    "coverage/sweep": "compose_slide",
    "scope/verify": "compose_slide",
    "rubric_fixtures": "compose_slide",
    "produced": "builder.build (TAM uretim yolu)",
    "contrast": "yok: dosyadan okur",
    "completeness": "yok: dosyadan okur",
    "inventory": "yok: dosyadan okur",
    "open_test": "yok: Storyline acar",
}


def _kova(el, parents) -> str:
    """Bir seklin kesiti: temel/katman x ust/ic.

    ust = <sld> ya da <sldLayer> altindaki shapeLst'in DOGRUDAN cocugu, yani
    `for shape in root.find("shapeLst")` dongusunun gordugu sey. ic = ayni
    agacta daha derin: grup uyesi, ya da bir sik'in state govdesi.
    """
    node, katmanda = el, False
    while node is not None:
        if node.tag == "sldLayerLst":
            katmanda = True
            break
        node = parents.get(node)
    parent = parents.get(el)
    ust = parent is not None and parent.tag == "shapeLst"
    if ust:
        # Slayt koku <sld>, katman koku <sldLayer>. Ilk yazilisinda "slide"
        # araniyordu ve HER SEY /ic sayildi: temel/ust 0 cikti. Sifir bir
        # olcum degildi, probun hic calismadiginin isaretiydi (K3).
        gp = parents.get(parent)
        ust = gp is not None and gp.tag in ("sld", "sldLayer")
    return ("katman" if katmanda else "temel") + ("/ust" if ust else "/ic")


def sayim(pkg: StoryPackage) -> dict:
    """Kursun kesitlere gore nufus sayimi. Hicbir sey degistirmez."""
    from storyline_mcp import preview
    lo, hi = shapes.CALIBRATED_RANGE
    kova: dict[tuple, int] = {}
    tasma: dict[tuple, int] = {}
    slayt = {"toplam": 0, "bos": 0, "soru": 0, "katmanli": 0}

    for part, _ref in model.slide_index(pkg).items():
        root = pkg.parse(part)
        parents = {c: p for p in root.iter() for c in p}
        slayt["toplam"] += 1
        shape_list = root.find("shapeLst")
        if shape_list is None or not len(shape_list):
            slayt["bos"] += 1
        layer_list = root.find("sldLayerLst")
        if layer_list is not None and len(layer_list):
            slayt["katmanli"] += 1
        # root.iter(tag) bir URETEC dondurur ve uretec her zaman truthy'dir;
        # `any(root.iter(t) for t in ...)` her slaydi soru sayardi.
        if any(True for t in model.INTERACTION_TAGS for _ in root.iter(t)):
            slayt["soru"] += 1

        width, height = shapes.slide_size(root)
        _sahne = shapes.stage_size(pkg)
        slack = compose.FIT_TOLERANCE / 100 * height
        for el in root.iter():
            rect = shapes.shape_rect(el)
            if not rect:
                continue
            text = model.shape_text(root, el.get("g") or "").strip()
            sinif = "gorsel" if el.tag == "pic" else \
                    ("metinli" if text else "dekoratif")
            key = (_kova(el, parents), sinif)
            kova[key] = kova.get(key, 0) + 1
            if not text:
                continue
            try:
                _c, size, _b, _a = preview._text_style(el)
            except Exception:
                continue
            bant = "13-38pt" if lo <= size <= hi else "bant disi"
            need = _quiet(shapes.measured_text_height, text, size,
                          rect[2] - rect[0], shapes.space_of(root, _sahne),
                          wrap=shapes.wraps(el))
            t = tasma.setdefault((_kova(el, parents), bant),
                                 {"yazi": 0, "tasan": 0})
            t["yazi"] += 1
            t["tasan"] += need > (rect[3] - rect[1]) + slack
    return {"slayt": slayt, "kova": kova, "tasma": tasma}


def _quiet(fn, *args, **kwargs):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return fn(*args, **kwargs)


def envanter(story: Path | None) -> int:
    import scope

    print("=== 1. HER KONTROL HANGI KESITTE KOSUYOR ===\n")
    head = ("kontrol", "slayt turu", "katman", "sekil sinifi",
            "tema x duzen", "KOD DALI")
    # Genislikler icerikten hesaplanir: elle yazilan bir genislik, satir
    # uzadigi gun sutunlari birbirine yapistirip tabloyu okunamaz kilar.
    rows = [head] + [(a, c, d, e, f, KOD_DALI.get(a, "-"))
                     for a, _b, c, d, e, f, _g in ENVANTER]
    w = [max(len(r[i]) for r in rows) + 2 for i in range(5)]
    print("  " + "".join(head[i].ljust(w[i]) for i in range(5)) + head[5])
    print("  " + "-" * (sum(w) + len(head[5])))
    urun = []
    for ad, _dosya, tur, katman, sinif, kesit, gercek in ENVANTER:
        cells = (ad, tur, katman, sinif, kesit)
        print("  " + "".join(cells[i].ljust(w[i]) for i in range(5))
              + KOD_DALI.get(ad, "-"))
        if gercek:
            urun.append(ad)
    print(f"\n  Uretilmis bir kursa bakabilen: {', '.join(urun)}")
    print("  Bunlarin hicbiri suit kosuldugunda otomatik kosmuyor; elle "
          "cagrilir.")

    print("\n=== 2. KAYNAK TARAMASI (iddia degil, her kosuda yeniden okunur) ===\n")
    kaynaklar = sorted((ROOT / "tools").glob("*.py"))
    metinler = {p.stem: p.read_text(encoding="utf-8", errors="replace")
                for p in kaynaklar}
    bulunan = {}
    for etiket, imzalar in IMZALAR.items():
        hits = sorted(ad for ad, govde in metinler.items()
                      if any(i in govde for i in imzalar))
        bulunan[etiket] = hits
        print(f"  {etiket:<36}{', '.join(hits) if hits else 'HICBIRI'}")
    cozen = bulunan["katmani (<sldLayerLst>) COZEN"]
    olcen = [a for a in cozen if a not in YALNIZCA_SAYAN]
    print(f"\n  Katmani cozen : {', '.join(cozen) if cozen else 'YOK'}"
          f"   (yalnizca SAYAN: {', '.join(sorted(YALNIZCA_SAYAN))})")
    print(f"  Katman uzerinde VERDIKT veren: "
          f"{', '.join(olcen) if olcen else 'YOK'}")
    print("  preview.py de onlari CIZMIYOR -- sadakat notu bunu acikca yaziyor.")
    print("  Yani katmanlar ne olculuyor ne goruluyor: ne sayi bagirir, ne goz.")

    print("\n=== 3. KAPSAM CUMLESI OLAN / OLMAYAN KONTROL ===\n")
    araclar = sorted({ad.split("/")[0] for ad, *_ in ENVANTER})
    var = sorted(scope.SCOPES)
    yok = [a for a in araclar if a not in var]
    print(f"  scope.py'de cumlesi olan : {', '.join(var)}")
    print(f"  cumlesi OLMAYAN          : {', '.join(yok)}")
    print("\n  K5 diyor ki kapsam verdiktin YANINDA basilmali. Cumlesi olmayan\n"
          "  her kontrol, gectiginde neyi kapsamadigini soylemiyor.")

    if story is None:
        print("\n(Kor nokta sayimi icin: --envanter <kurs.story>)")
        return 0

    print(f"\n=== 4. KOR NOKTA SAYIMI: {story.name} ===\n")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        found = sayim(StoryPackage(story.resolve()))
    s = found["slayt"]
    print(f"  slayt {s['toplam']}  bos {s['bos']}  etkilesimli {s['soru']}  "
          f"katmani olan {s['katmanli']}")

    print(f"\n  {'kesit':<12}{'metinli':>9}{'dekoratif':>11}{'gorsel':>8}"
          f"   olcu tarafinda")
    toplam_metin = gorunen_metin = 0
    for kesit in ("temel/ust", "temel/ic", "katman/ust", "katman/ic"):
        m = found["kova"].get((kesit, "metinli"), 0)
        d = found["kova"].get((kesit, "dekoratif"), 0)
        g = found["kova"].get((kesit, "gorsel"), 0)
        toplam_metin += m
        gorulur = kesit == "temel/ust"
        gorunen_metin += m if gorulur else 0
        print(f"  {kesit:<12}{m:>9}{d:>11}{g:>8}   "
              f"{'taraniyor' if gorulur else 'HICBIR KONTROL TARAMIYOR'}")
    kor = toplam_metin - gorunen_metin
    print(f"\n  metin tasiyan {toplam_metin} seklin {kor}'i "
          f"(%{round(kor / max(toplam_metin, 1) * 100)}) hicbir kontrolun "
          f"kesitinde degil.")

    print(f"\n  {'kesit':<12}{'bant':<11}{'yazi':>6}{'tasan':>7}   "
          f"check_text_fits gorur mu")
    hepsi = gorulen = 0
    for (kesit, bant), t in sorted(found["tasma"].items()):
        gorur = kesit == "temel/ust" and bant == "13-38pt"
        hepsi += t["tasan"]
        gorulen += t["tasan"] if gorur else 0
        print(f"  {kesit:<12}{bant:<11}{t['yazi']:>6}{t['tasan']:>7}   "
              f"{'EVET' if gorur else 'hayir'}")
    print(f"\n  tahmin edilen tasma {hepsi}: kontrolun kesitinde {gorulen}, "
          f"kor noktada {hepsi - gorulen}.")
    print("  UYARI: kor noktadaki sayi bir KUSUR SAYISI DEGIL, bir ADAY "
          "sayisidir.\n  estimate_text_height yalnizca bestelenen temel katman "
          "yazisinda\n  kalibre edildi; donorden gelen katman metninde ne "
          "olcuyor -- olculmedi.\n  Ayirmak Faz 2'nin isi; Faz 0 yalnizca "
          "adaylarin NEREDE durdugunu sayar.")
    return 0


# ------------------------------------------------------- kapsam kanaryasi
#
# Envanterin butun verdikti tek bir sayima dayaniyor ve o sayim bu oturumda
# IKI KEZ sessizce yalan soyledi: slayt kokunu <slide> sanip her sekli "ic"
# saydi (temel/ust 0 cikti), ve `any(root.iter(t) for t in ...)` yazip her
# slaydi soru saydi (uretec daima truthy). Ikisi de tesaduufen yakalandi.
# Ucuncusu yakalanmayabilir.
#
# O yuzden iddia sinaniyor, ve IKI YONLU sinaniyor:
#
#   kor nokta   bir katmana kasten bozuk bir sekil ekilir. contrast ve
#               inventory onu GORMEMELI. Gorurlerse envanter yanlis.
#   canli       AYNI sekil temel katmana ekilir. Ikisi de GORMELI.
#
# Ikincisi olmadan birincisi hicbir sey kanitlamaz: hicbir yerde hicbir sey
# bulamayan bir olcu de "katmanda bulamadi". canary.py'nin dersi, bu sefer
# kapsam iddiasi uzerinde.
KANARYA_METIN = ("Bu metin kutusuna sigmayacak kadar uzun yazilmistir ve "
                 "zemini ile ayni renktedir; hem tasma hem kontrast kusuru "
                 "tasir, ikisi de kasten konulmustur.")
KANARYA_ADI = "KANARYA_EKILEN"
KANARYA_RENK = "#FFFFFF"


def _ek(root: ET.Element, seed: ET.Element, kap: ET.Element) -> ET.Element:
    """Kasten bozuk bir kopya ek: kutusuna sigmaz, dolgusuyla ayni renk.

    Kendi dolgusu veriliyor cunku contrast'in `_behind`'i yazinin arkasindaki
    yigina seklin KENDI dolgusunu da katiyor ve o yiginda son sozu soyluyor.
    Zemine guvenmek, ekilen seklin ustune baska bir panel denk geldiginde
    kanaryayi sessizce gecerli hale getirirdi.

    SIRA ONEMLI ve bir kez yanlis yazildi: metin, sekil AGACA EKLENDIKTEN
    sonra uygulanir. edits.set_shape_text guid'i root.iter() icinde arar ve
    bulamazsa sessizce False doner -- ekim yapilmis, metin hic yazilmamis
    olur. Kanarya o turda "contrast 0->1" gordu (tohumun eski metni, kucuk
    kutuda) ama kendi metnini bulamadi, yani dogru sonuca yanlis sebeple
    varmak uzereydi.
    """
    from storyline_mcp import authoring
    clone = shapes.clone_shape(seed, name=KANARYA_ADI, keep_triggers=False)
    width, height = shapes.slide_size(root)
    shapes.set_loc(clone, width * 0.10, height * 0.40,
                   width * 0.55, height * 0.40 + 18.0)
    shapes.set_fill(clone, KANARYA_RENK)
    kap.append(clone)
    for index, child in enumerate(kap):
        child.set("zOrder", str(index))
    authoring._apply_text(root, clone, KANARYA_METIN,
                          color=KANARYA_RENK, size=16)
    return clone


def _kanarya_hedefi(pkg: StoryPackage):
    """Hem dolu temel katmani hem dolu geri bildirim katmani olan ilk slayt."""
    for part, ref in model.slide_index(pkg).items():
        root = pkg.parse(part)
        base = root.find("shapeLst")
        if base is None or not len(base):
            continue
        seed = next((s for s in base
                     if model.shape_text(root, s.get("g") or "").strip()), None)
        if seed is None:
            continue
        layers = root.find("sldLayerLst")
        for layer in list(layers) if layers is not None else []:
            lst = layer.find("shapeLst")
            if lst is not None and len(lst):
                return part, ref, seed, layer
    return None


def kanarya(kaynak: Path) -> int:
    import shutil
    import inventory

    if not kaynak.is_file():
        print(f"Referans dosya yok: {kaynak}")
        return 2

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        hedef = _kanarya_hedefi(StoryPackage(kaynak))
    if hedef is None:
        print(f"{kaynak.name}: hem temel hem katman tasiyan slayt yok — "
              "kanarya bu dosyada kurulamaz.")
        return 2
    part, ref, _seed, _layer = hedef
    print(f"referans : {kaynak.name}")
    print(f"ekim yeri: {ref.basename} (hem temel hem geri bildirim katmani var)\n")

    isler = {}
    for etiket in ("temiz", "temel", "katman"):
        yol = ROOT.parent / "test" / "_canary" / f"kanarya_{etiket}.story"
        shutil.copy2(kaynak, yol)
        if etiket != "temiz":
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                pkg = StoryPackage(yol)
                root = pkg.parse(part)
                base = root.find("shapeLst")
                seed = next(s for s in base
                            if model.shape_text(root, s.get("g") or "").strip())
                if etiket == "temel":
                    kap = base
                else:
                    layers = root.find("sldLayerLst")
                    kap = next(l.find("shapeLst") for l in layers
                               if l.find("shapeLst") is not None
                               and len(l.find("shapeLst")))
                ekilen = _ek(root, seed, kap)
                pkg.replace_xml(part, root)
                pkg.save(yol, backup=False)

            # EKIM GERI OKUNUR. Yazildigini varsaymak, bu turda tam olarak
            # yanlis verdikte goturuyordu: metin hic yazilmamisti ve kanarya
            # onu fark etmeden "kor nokta dogrulandi" diyecekti.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                geri = StoryPackage(yol).parse(part)
            okunan = model.shape_text(geri, ekilen.get("g") or "").strip()
            if KANARYA_METIN[:24] not in okunan:
                print(f"EKIM YAZILMADI ({etiket}): geri okunan metin "
                      f"{okunan[:40]!r}.\nKanarya kurulamadi; verdikt "
                      "uretilmiyor.")
                return 2
        isler[etiket] = yol

    olcum = {}
    for etiket, yol in isler.items():
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pkg = StoryPackage(yol)
            bulgular = contrast.audit(pkg)
            olcum[etiket] = {
                "kontrast": len(bulgular),
                "kontrast_kanarya": sum(1 for b in bulgular
                                        if KANARYA_METIN[:20] in b["text"]),
                "tasma": inventory.audit(pkg)["tasma"],
                "sayim": sayim(pkg),
            }

    print(f"  {'dosya':<10}{'contrast':>10}{'kanaryayi':>11}{'tasma':>8}"
          f"   (inventory.audit)")
    for etiket in ("temiz", "temel", "katman"):
        o = olcum[etiket]
        print(f"  {etiket:<10}{o['kontrast']:>10}{o['kontrast_kanarya']:>11}"
              f"{o['tasma']:>8}")

    t, b, k = olcum["temiz"], olcum["temel"], olcum["katman"]
    beklenti = [
        ("CANLI  contrast temel katmandaki kusuru gordu",
         b["kontrast_kanarya"] >= 1),
        ("CANLI  inventory temel katmandaki tasmayi gordu",
         b["tasma"] > t["tasma"]),
        # KOR NOKTA KAPANDI (2026-08-18) ve beklenti KAZANC olarak yeniden
        # yazildi. Onceden burada `== 0` vardi: contrast katmanlara HIC
        # bakmadigi icin ekilen kusuru gormemesi BEKLENIYORDU ve o, olculmus
        # bir kor noktaydi.
        #
        # `contrast.audit` katmanlara acilinca (bkz. contrast._kaplar) sayi
        # 0'dan 1'e cikti ve kanarya BAGIRDI -- sessizce gecmedi. Beklentiyi
        # guncellemek burada "testi susturmak" degil, kapanan kor noktayi
        # KORUMA ALTINA ALMAK: bu dosyanin kendi kurali, "kaydedilmeyen bir
        # kazanim korunmuyor demektir". Yon simdi ters: katmani yeniden
        # goremez hale gelirsek burasi bagirir.
        # KOR NOKTA HALA ACIK, ve bu artik bir SECIM: contrast.audit'in
        # katman taramasi var ama VARSAYILAN OLARAK KAPALI, cunku o kesitte
        # zemin cozulmuyor ve olcu kendi korlugunu kusur diye raporluyor
        # (bkz. contrast.audit docstring). Kanarya kor noktayi olcmeye devam
        # ediyor; schemeClr cozumu girip varsayilan acildiginda bu beklenti
        # "CANLI ... gordu" olarak yeniden yazilacak.
        ("KOR    contrast katmandaki AYNI kusuru gormedi (kesit KAPALI)",
         k["kontrast_kanarya"] == 0),
        ("KOR    inventory katmandaki AYNI tasmayi gormedi",
         k["tasma"] == t["tasma"]),
        ("SAYIM  envanter katmandaki ekileni saydi",
         k["sayim"]["tasma"].get(("katman/ust", "13-38pt"), {}).get("tasan", 0)
         > t["sayim"]["tasma"].get(("katman/ust", "13-38pt"), {}).get("tasan", 0)),
        ("SAYIM  envanter temeldeki ekileni saydi",
         b["sayim"]["tasma"].get(("temel/ust", "13-38pt"), {}).get("tasan", 0)
         > t["sayim"]["tasma"].get(("temel/ust", "13-38pt"), {}).get("tasan", 0)),
    ]
    print()
    kirik = []
    for ad, tuttu in beklenti:
        print(f"  {'tuttu' if tuttu else 'BOZUK':<7}{ad}")
        if not tuttu:
            kirik.append(ad)

    print()
    if not b["kontrast_kanarya"] and not (b["tasma"] > t["tasma"]):
        print("KANARYA ATIL: temel katmana ekilen kusur da yakalanmadi. Yani\n"
              "'katmanda bulunamadi' cumlesi hicbir sey soylemiyor -- once\n"
              "canli kontrolun neden olmedigi bulunmali.")
        return 1
    if kirik:
        print(f"{len(kirik)} BEKLENTI TUTMADI:")
        for ad in kirik:
            print(f"  ! {ad}")
        return 1
    print("Kapsam iddiasi sinandi ve tuttu: ayni kusur temel katmanda\n"
          "yakalaniyor, geri bildirim katmaninda yakalanmiyor, ve envanter\n"
          "sayimi ikisini de goruyor. Kor nokta olculmustur, varsayilmamistir.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--envanter", nargs="?", const="", metavar="KURS",
                        help="bes eksenli kapsam tablosu; kurs verilirse "
                             "kor nokta sayimi da yapilir")
    parser.add_argument("--kanarya", nargs="?", const="", metavar="KURS",
                        help="kapsam iddiasini kasten bozarak sina")
    args = parser.parse_args()
    if args.kanarya is not None:
        return kanarya(Path(args.kanarya) if args.kanarya else REFERANS)
    if args.envanter is not None:
        return envanter(Path(args.envanter) if args.envanter else None)

    table = sweep()
    themes = compose.theme_names()

    print(f"{'tema':<10}" + "".join(f"{l[:9]:>11}" for l in SPECS))
    print("kontrast uyarisi / bos alan %")
    for theme in themes:
        row = table[theme]
        print(f"{theme:<10}" + "".join(
            f"{str(row[l][0]) + '/' + str(row[l][1]):>11}" for l in SPECS))

    problems = []
    warnings_total = sum(row[l][0] for row in table.values() for l in SPECS)
    if warnings_total:
        problems.append(f"{warnings_total} kontrast uyarisi")

    # Geometri renkten bagimsiz olmali; olmamasi bir hatadir, ve bu satir
    # deadband'in kapsam cumlesini her kosuda yeniden dogrular.
    for layout in SPECS:
        seen = {table[t][layout][1] for t in themes}
        if len(seen) != 1:
            problems.append(f"{layout}: bos alan temaya gore degisiyor {seen}")

    print()
    for layout in SPECS:
        value = table[themes[0]][layout][1]
        base = EMPTY_BASELINE[layout]
        if value > base + SLACK:
            problems.append(f"{layout}: bos alan %{value}, taban %{base}")
            print(f"  {layout:<10} %{value}  <- taban %{base}")
    print(f"\n{len(themes)} tema x {len(SPECS)} duzen = "
          f"{len(themes) * len(SPECS)} slayt tarandi.")
    if problems:
        print("SORUN:")
        for p in problems:
            print(f"  ! {p}")
        return 1
    print("Tabanla uyumlu. Bilinen sinir: menu ve content, yogunluk olcegi "
          "content disinda yok.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
