"""Ölçülüp doğru bulunan şeyleri, doğru kalmaya zorlar.

Bir ölçüm bir kez alınır ve rapora yazılır; bir invaryant her koşuda sorulur.
Aradaki fark, altı ay sonra GROWTH_LIMIT'e ya da CHAR_WIDTH_RATIO'ya dokunan
birinin bunları sessizce bozup bozamayacağıdır. Bu oturumda tam olarak o
sınıftan altı hata çıktı: hepsinde bir şey görülemediği için yok sayıldı.

Korunan özellik "havuz her etiket uzunluğunda eşit" DEĞİL. Ölçüldü ve öyle
değil: 40 harfte Tabcordion sekmeleri kutuyu 3.49 katına çıkarmak zorunda
kalıyor, çünkü ikon girintisi genişliğin üçte birini yiyor. Onları havuzda
tutmak GROWTH_LIMIT'i 3.5'e çekmek demek ve 3.5 kat uzamış bir şey buton
değil. Elenmeleri doğru davranış.

Korunan özellik, altındaki asıl şey:

  1. Hiçbir etiket uzunluğunda sessiz taşma olmaz. Kutu büyür ya da aday
     gerekçesiyle elenir; etiket şeklin dışına çizilmez.
  2. Havuz hiçbir uzunlukta boşalmaz -- kompozisyonun ürettiği en uzun
     etikette bile (text[:40]) seçilecek bir şey kalır.
  3. Elenen her aday bir gerekçe taşır. Sessiz eleme, eleme değil kayıptır.
  4. Havuz üyeliği kalibrasyon sabitine bağlı değildir: oran bandın her
     yerinde aynı adayları verir.
  5. Şık sayısı uyuşmazlığı sessizleşmez.

Beşincisi hakkında bir uyarı, çünkü bu tür kontroller silinir: **bu ölçüt
bugün geçiyor ve mevcut bir hatayı yakalamıyor.** add_question şu an 4'lük bir
şablona 2 şık verildiğinde hata veriyor; ölçüt, o davranışın ileride sessizce
gevşemesini yakalamak için var. Aşağı yön özellikle sinsi: kalan iki şekil
yerinde durur, sadece boş görünür, hiçbir görsel test bağırmaz -- ve
tetikleyicileri kaldırılmazsa görünmez tıklanabilir alan bırakır.

"Hiç bağırmıyor, demek ki gereksiz" doğru sonuç değil. Aynı gerekçe, 4a'daki
CHAR_WIDTH_RATIO bandı kontrolü için de geçerli.

DÜZEN AİLESİ DENETİMİ (GÖREV 4'e girmeden önce okunacak)
--------------------------------------------------------
Buradaki iddiaların bir kısmı dikey yığına özgü varsayım taşıyor.

GÜNCELLEME (2026-08-17): check_fit_choices ve check_plan_applied SİLİNDİ --
ikisi de üretimde 0/4 kullanılan plan dalını sınıyordu. Yerlerine
check_choice_admission geldi ve o da aynı yığın varsayımını taşıyor, yani
aşağıdaki uyarı geçerliliğini koruyor; yalnızca sayı 5'ten 3'e indi.

Kalanı düzenden bağımsız (havuz tabanı, gerekçe zorunluluğu, oran bandı,
eğri biçimi, punto tabanı, şık sayısı, teşhis yönlendirmesi).

Bugün bunlar yatay şablonu HİÇ GÖRMÜYOR: pick_template yatay düzeni "model
kapsamıyor" diye eliyor, yani vakalar hep yığın. fit_row/fit_grid gelip yatay
seçilebilir olduğunda bu kontroller yanlış patlamayacak -- sessizce geçecekler,
çünkü vakaları elle yazılmış yığın vakaları. Sessizce geçen bir invaryant,
olmayan bir invaryanttan kötüdür: koruma var sanılır.

Yatay aile eklenirken her birinin karşılığı da eklenmeli:
    "son şıkkın alt kenarı"  -> "son sütunun sağ kenarı"
    "boşluk" (dikey aralık)  -> "sütun aralığı"
    "n·kutu + boşluk"        -> "tek satır yüksekliği, n·sütun genişliği"

Ve yığın vakalarının çıktısı bit düzeyinde aynı kalmalı. Ortak soyutlama
çıkarılırken en kolay kaybedilen şey bu, ve kaybedilirse g2'deki farkın
kaynağı okunamaz hale gelir -- yeni şablonların mı geldiği, yoksa eski hesabın
mı kaydığı belirsizleşir.
"""

from __future__ import annotations

import re
import sys
import textwrap
import warnings
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from storyline_mcp import compose, donors, model, preview, shapes
from storyline_mcp.package import StoryPackage
# Gercek kurs metinleri tek yerde dursun: kabul testi ile invaryant ayni
# corpusu kullanmazsa biri gecerken digeri kalabilir ve hangisinin hakli
# oldugu okunamaz.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import variety

# Kompozisyonun gerçekten ürettiği aralık. 40, add_button'a giren text[:40].
LABELS = {
    5: "Basla",
    8: "Devam Et",
    12: "Ornek Etiket",
    18: "Sonraki Bolume Gec",
    40: "Parola yonetimi ve cok adimli dogrulama"[:40],
}
BOX = (144.0, 51.0)          # compose'un bir butona verdiği tipik kutu
SLIDE = (720.0, 540.0)
# ZEMINI OLCULDU (2026-08-17), devralinmadi. Bu sayi da GROWTH_LIMIT ile ayni
# eski zeminde secilmisti ve "cesitlilik iddiasi biter" diyordu; iddianin
# OLCUSU sorulmamisti.
#
#     donor havuzu ham aday                                  13
#     en kisa etikette bile gecmeyen (metin kosusu yok)        3
#         -> triangle, chevron, importedVector: yapisal
#     ETKIN TAVAN                                            10
#     uretilmis kursta donor ailesinden AYRI sekil turu        5
#         -> btn, roundRect, rect, oval, importedVector
#
# Yani 6, etkin tavanin %60'i ve uretimin fiilen kullandigi 5'in bir ustu.
# Taban DEGISMEDI; artik neyi koruduğu yazili. Degistirmek isteyen once
# uretimin kullandigi tur sayisini yeniden olcsun.
POOL_FLOOR = 6               # bunun altına inerse çeşitlilik iddiası biter

# Ve ustunde OLCULEN degerler. Taban tek yonlu bir guard: yalnizca "cok
# dustu"yu yakalar, "biraz dustu"yu degil. Bugun kisa etiketlerde havuz 10 ve
# taban 6 -- yani dort donor sessizce elenebilir, hicbir sey bagirmaz, ve
# GOREV 2'nin cesitlilik iddiasi kimse fark etmeden yariya iner.
#
# Bu, bu oturumda ucuncu kez ayni sinif: GROWTH_LIMIT tek yonlu korunuyordu,
# deadband tabani iyilesmeyi kaydetmiyordu (section %10 -> %6 gorunmedi), ve
# simdi havuz. Kaydedilmeyen bir kazanim korunmuyor demektir.
#
# SLACK: donors/ klasoru degistiginde test kirilmasin diye bir pay. Payin
# ustundeki dusus bilerek verilmis bir karar olmali.
# YENIDEN OLCULDU (2026-08-17, kanonik zemin, GROWTH_LIMIT=2.8).
#
# ESKI TABLO YENIDEN URETILMEDI ve bu kayda geciyor: 40 harf icin 8 yaziyordu,
# ama o sayi HICBIR zeminde cikmiyor -- eski zeminde (ratio 0.72, L=2.4)
# yetkili fonksiyonla olculen 2, kanonik zeminde L=2.8 ile yine 2. 8'i veren
# tek konfigurasyon kanonik L>=3.0, ki o zaman da GROWTH_LIMIT'in oradan
# secilmis olmasi gerekirdi ve secilmemisti.
#
# Yani 8, provenance'i tutmayan bir sayiydi ve uzerine bir guard kurulmustu.
# Kovalanmadi, DONDURULDU ve yeniden olculdu (referansi dondur, provenance
# kovalama). Yeni tablo bugunku kodun urettigi seydir; bir sonraki degisiklik
# onu kaydirirsa fark GORUNUR olur -- eskisinde olmuyordu.
#
# 40 harfte 2, POOL_FLOOR'un ALTINDA ve bu bilerek boyle birakildi: o bantta
# donor cesitliligi gercekten yok ve sinyal susturulmuyor (bkz. GROWTH_LIMIT
# yorumu). Guard bagirmaya devam edecek; bagirdigi sey gercek.
POOL_MEASURED = {5: 10, 8: 10, 12: 10, 18: 10, 40: 2}
POOL_SLACK = 1

# Şık küçültmesinin iki tabanı, burada bilerek ikinci kez yazılı. compose'dan
# okunsalardı bu test tabanı kaldıran değişikliği onaylardı; ölçümüyle test
# edilen ölçüm doğrulanamaz. Değiştirmek isteyen ikisini birden değiştirsin,
# yani kararı bilerek versin.

# Soru cercevesinin tabani, yine BILEREK ikinci kez yazili.
#
# Ilk yazilisinda check_question_frame compose.FLOOR'u OKUYORDU ve kasten
# bozma denemesinde sessizce gecti: taban 92'den 60'a indirilince yerlesim
# motoru de icerigi yukari cekti, olcunun iki yani birlikte kaydi ve sik
# %57.5'te "icerde" sayildi. Yani kontrol, korumasi gereken sabiti referans
# aliyordu -- olcumuyle test edilen olcum dogrulanamaz.
#
# Ayni ders bu dosyada EXPECTED_SIZE_FLOOR icin zaten yaziliydi ve yine de
# tekrarlandi; sabitin burada durmasinin sebebi budur. Degistirmek isteyen
# ikisini birden degistirsin, yani karari bilerek versin.
EXPECTED_FLOOR = 92.0

# Sik puntosu tabani, UCUNCU kez ayni ders (2026-08-17). Yeni yazilan
# check_choice_admission ilk kosusunda `compose.MIN_CHOICE_SIZE` ile
# karsilastiriyordu ve check_thresholds_independent onu ANINDA yakaladi --
# yani yeniden kurulan esik kumesi ilk isinde is gordu.
#
# Ozellikle onemli, cunku compose tarafinda MIN_CHOICE_SIZE artik
# shapes.CALIBRATED_RANGE[0]'a BAGLI. Kontrol oradan okusaydi, kalibrasyon
# bandi genisletildiginde hem motor hem guard birlikte kayardi ve "sik
# puntosu tabani asildi" iddiasi hicbir zaman bagirmazdi.
EXPECTED_CHOICE_SIZE_FLOOR = 13.0


def _quiet(fn, *args, **kwargs):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return fn(*args, **kwargs)


def check() -> list[str]:
    failures: list[str] = []
    every = _quiet(donors._harvest_all_for_probe)
    if not every:
        return ["donor havuzu hic aday vermedi — donors/ bos ya da okunamiyor"]

    print(f"{'harf':<6} {'havuz':<7} {'en dar buyume':<15} taşma")
    print("-" * 52)

    sizes: dict[int, int] = {}
    for size, label in sorted(LABELS.items()):
        pool, reasons = [], []
        for cand in every:
            ok, why = _quiet(donors.rehearse, cand, label=label)
            (pool if ok else reasons).append((cand, why))

        # 3. her elenenin gerekcesi var mi
        for cand, why in reasons:
            if not why or not why.strip():
                failures.append(f"{size} harf: {cand.tag} gerekcesiz elendi")

        # 2. havuz bosalmiyor mu -- ve olculen degerin altina inmiyor mu
        if len(pool) < POOL_FLOOR:
            failures.append(
                f"{size} harf: havuz {len(pool)} adaya dustu (taban {POOL_FLOOR})")
        elif size in POOL_MEASURED and len(pool) < POOL_MEASURED[size] - POOL_SLACK:
            failures.append(
                f"{size} harf: havuz {len(pool)}, olculen {POOL_MEASURED[size]} "
                f"(pay {POOL_SLACK}) — tabanin ustunde ama SESSIZ DUSUS; "
                "donorler elenmeye basladiysa sebebi yazilmali, degilse "
                "POOL_MEASURED guncellenmeli")

        # 1. yerlestirilen etiket tasiyor mu
        worst = 0.0
        for cand, _why in pool:
            shape = shapes.clone_shape(cand.element(), name="p", keep_triggers=False)
            shapes.set_shape_slide_size(shape, *SLIDE)
            rect = (0.0, 200.0, BOX[0], 200.0 + BOX[1])
            _u = shapes.Space(SLIDE[0], SLIDE[1], SLIDE[0], SLIDE[1])
            need = _quiet(shapes.height_for_label, shape, label, 15, BOX[0], _u)
            grown = _quiet(shapes.grow_to_fit, shape, rect, label, 15, _u)
            got = grown[3] - grown[1]
            worst = max(worst, need / BOX[1])
            if got + 0.01 < need:
                failures.append(
                    f"{size} harf: {cand.tag} kutusu {got:.0f}, gereken {need:.0f} "
                    "— sessiz tasma")

        sizes[size] = len(pool)
        mark = "yok" if not any(f.startswith(f"{size} harf") for f in failures) else "VAR"
        print(f"{size:<6} {len(pool):<7} {worst:<15.2f} {mark}")

    # Egrinin bicimi, sayilarin kendisi degil.
    #
    # GROWTH_LIMIT'i DUSURMEK zaten yakalaniyordu: havuz tabanin altina iner.
    # YUKSELTMEK yakalanmiyordu -- ve o, havuz 40 harfte dustugunde akla ilk
    # gelen "cozum". 3.6'ya cikarmak Tabcordion sekmelerini (3.49x isteyen)
    # havuza geri sokar, yani 3.5 kat uzamis butonu. Cikti saglam kalir,
    # taban asilmaz, hicbir sey bagirmazdi.
    #
    # Mutlak sayi yerine karar sabitleniyor: kisa etiketlerde havuz esit
    # olmali, 40 harfte KUCULMELI. Kucumemesi, orantisiz buyumeye izin
    # verildigi anlamina gelir. Boylece donors/ degistiginde test kirilmaz
    # ama tavizin kendisi kirilirsa kirilir.
    short = [sizes[s] for s in (5, 8, 12, 18) if s in sizes]
    if short and len(set(short)) != 1:
        failures.append(
            f"kisa etiketlerde havuz esit degil: {short} — etiket uzunlugu "
            "havuz uyeligini etkiliyor")
    if 40 in sizes and short and sizes[40] >= short[0]:
        failures.append(
            f"40 harfte havuz kucumedi ({sizes[40]} >= {short[0]}) — orantisiz "
            "buyumeye izin veriliyor olabilir (GROWTH_LIMIT yukseltilmis mi?)")

    # 4a. Oranin kendisi olculen bandin icinde mi.
    #
    # Buradaki sinir acikca soylenmeli: bu testler CHAR_WIDTH_RATIO ile
    # hesaplanmis olcumleri kullaniyor, yani oranin YANLIS olmasini
    # yakalayamazlar -- yanlis oran her seyi tutarli bicimde yanlis olcer ve
    # her kontrolden gecer. Denendi: 0.72'yi 0.52'ye cekmek tek bir invaryant
    # bile bozmuyordu, cunku dusuk oran "her sey sigiyor" diyor.
    #
    # Dogru olup olmadigini yalnizca Storyline'in kendi cizimi soyler
    # (tools/calibrate_text.py). Burada yapilabilecek tek sey, kimsenin oranı
    # olculmus bandin disina sessizce tasimadigini garanti etmek.
    low, high = 0.66, 0.99
    if not low <= shapes.CHAR_WIDTH_RATIO <= high:
        failures.append(
            f"CHAR_WIDTH_RATIO={shapes.CHAR_WIDTH_RATIO} olculen "
            f"{low}-{high} bandinin disinda — once tools/calibrate_text.py ile "
            "yeniden olcun, bu testler yanlis orani yakalayamaz")

    # 4b. havuz uyeligi kalibrasyon sabitine bagli mi
    base = shapes.CHAR_WIDTH_RATIO
    try:
        members = {}
        for ratio in (0.66, 0.72, 0.85, 1.00):
            shapes.CHAR_WIDTH_RATIO = ratio
            members[ratio] = frozenset(
                c.sig for c in every if _quiet(donors.rehearse, c)[0])
    finally:
        shapes.CHAR_WIDTH_RATIO = base
    distinct = set(members.values())
    print(f"\nkalibrasyon bandinda havuz uyeligi: "
          f"{'sabit' if len(distinct) == 1 else 'DEGISIYOR'} "
          f"({', '.join(f'{r}:{len(m)}' for r, m in members.items())})")
    if len(distinct) != 1:
        failures.append(
            "havuz uyeligi CHAR_WIDTH_RATIO ile degisiyor — kalibrasyonu "
            "genisletmek havuzu sessizce degistirir")

    failures += check_wrap_model()
    failures += check_thresholds_independent()
    failures += check_choice_admission()
    failures += check_choice_labels()
    failures += check_question_frame()
    failures += check_choice_count()
    failures += check_diagnoses()
    failures += check_variant_reach()
    failures += check_choice_shape()
    failures += check_layout_bands()
    failures += check_button_band()
    failures += check_card_band()
    failures += check_text_fits()
    failures += check_no_overlap()
    failures += check_floor_respected()
    return failures


def check_floor_respected() -> list[str]:
    """Uzun etiketli bir buton hiçbir düzende tabanın altına sarkmaz.

    Buton kutusu etiketi sigsin diye BUYUYOR ve buyume slaydin kenarina kadar
    gidiyordu -- kompozisyonun tabani (%92) slaydin kenari degil. Uzun bir
    etiket butonu %99.7'ye indiriyor, tiklama alani sayfanin altindan tasiyor
    ve hicbir yapisal kontrol bagirmiyordu: dosya gecerli, slayt aciliyor.
    Olculdu, yedi duzenin besinde.

    Duzene ozgu bir kusur DEGILDI, buyume yoluna aitti; o yuzden burada
    butun duzenler taranir. Tek bir duzeni onarmak sinifi kapatmaz.

    Tam kenar susleri (sol serit, alt band) haric: onlar tanim geregi
    slaydin kenarina degiyor.
    """
    import shutil
    source = ROOT.parent / "test" / "bos.story"
    work = ROOT.parent / "test" / "_canary" / "taban.story"
    # GIRDI YOKSA BU BIR HATA, bir "gecti" degil. Eskiden bos liste donuyordu
    # ve bos liste "hicbir ihlal bulunmadi" demek -- yani girdisi olmayan bir
    # invaryant, korudugunu iddia ederek geciyordu. K1'in dosya seviyesindeki
    # hali: bulamadigini yokluk sanmak.
    if not source.is_file():
        return [f"taban kontrolu kosmadi: {source.name} yok — bu bir GECIS "
                "degil, olcum yapilmadi"]
    long_labels = [
        "Sakin bir sesle bu tur ifadelerle gorusmeye devam edemeyecegini soyler",
        "Uyariya ragmen hakaret ve tehdit surerse gorusmeyi hemen sonlandirir",
    ]
    specs = {
        "cover": dict(title="Kisa", body="Tek cumle.", buttons=long_labels),
        "section": dict(title="Kisa", index="02", body="Tek cumle."),
        "content": dict(title="Kisa", body="Tek cumle.", buttons=long_labels),
        "bullets": dict(title="Kisa", bullets=["a", "b"], buttons=long_labels),
        "steps": dict(title="Kisa", bullets=["a", "b"], buttons=long_labels),
        "statement": dict(title="Kisa", body="Tek cumle."),
        "menu": dict(title="Kisa", body="Sec", buttons=long_labels),
    }
    shutil.copy2(source, work)
    pkg = StoryPackage(work)
    names = [r.basename for r in model.slide_index(pkg).values()]
    where = {}
    for slide, (layout, spec) in zip(names, specs.items()):
        _quiet(compose.compose_slide, pkg, slide, layout, identity="taban",
               **dict(spec))
        where[slide] = layout
    pkg.save(work, backup=False)

    done = StoryPackage(work)
    out = []
    for part, ref in model.slide_index(done).items():
        root = done.parse(part)
        shape_list = root.find("shapeLst")
        if shape_list is None or not len(shape_list):
            continue
        width, height = shapes.slide_size(root)
        for shape in shape_list:
            rect = shapes.shape_rect(shape)
            if not rect:
                continue
            if (rect[2] - rect[0]) / width > 0.97 or                     (rect[3] - rect[1]) / height > 0.97:
                continue          # tam kenar susu
            # ICERIK ile SUS ayrimi, isimle degil ANLAMLA.
            #
            # Ilk yazilisinda her sekil sayiliyordu ve `section` duzeninin
            # sus cizgisini yakaladi -- kodda "metin bandinin ALTINDAN
            # slaydi kapatir" diye bilerek konmus, %0.7 yuksekliginde,
            # yazisiz ve tiklanamaz. Onu kusur saymak, invaryanti kapatmaya
            # ya da isim listesi tutmaya zorlardi; ikisi de kotu.
            #
            # Kural: OKUNACAK ya da TIKLANACAK bir sey tabanin altina inemez.
            # Ince bir cizgi inebilir; kimse onu okumuyor.
            has_text = bool(model.shape_text(root, shape.get("g") or "").strip())
            trig = shape.find("trigLst")
            clickable = trig is not None and len(list(trig)) > 0
            if not (has_text or clickable):
                continue
            # Esik compose.FLOOR'dan DEGIL, bagimsiz sabitten. Olculdu:
            # compose.FLOOR 99'a cikarilinca motor icerigi %99.1'e
            # indiriyordu ve bu guard SESSIZ GECIYORDU -- suit'te bastan
            # beri yesil kosan bir kontrol, tehlikeli yonde atildi.
            # check_thresholds_independent bunu buldu.
            if rect[3] / height * 100 > EXPECTED_FLOOR + 0.5:
                out.append(
                    f"{where.get(ref.basename, ref.basename)}: "
                    f"{(shape.get('name') or shape.tag)[:24]!r} alt kenar "
                    f"%{rect[3] / height * 100:.1f}, beklenen taban "
                    f"%{EXPECTED_FLOOR:.0f}")
    print(f"taban ({EXPECTED_FLOOR:.0f}%) altina sarkma, {len(specs)} duzen: "
          f"{'yok' if not out else str(len(out)) + ' SEKIL'}")
    return out[:5]


def check_no_overlap() -> list[str]:
    """İki metin kutusu üst üste biniyor mu?

    Bu sinif HIC kontrol edilmiyordu ve bir rubrik kosusunda ortaya cikti:
    bir slaytta govde metni "Devam" butonuyla %30 x %8 ortusuyordu. Ne tasma
    invaryanti gordu (her yazi KENDI kutusuna siginiyordu), ne acilma testi
    (dosya gecerli), ne deadband (dolu alan zaten dolu sayiliyor). Ortusme
    ayri bir sorudur: her kutu kendi icinde dogru, ikisi birlikte yanlis.

    Sebep de kayda degerdi -- _Page.text yuksekligi FLOOR'a kirpiyordu,
    cagiranin verdigi bandin tabanina degil, dolayisiyla buton icin ayrilan
    band gormezden geliniyordu.
    """
    # Yalnizca variety.story taranmiyor: hata orada YOKTU, fikstuurlerde
    # vardi. Hatanin bulunmadigi bir kesiti tarayan invaryant, kurulur
    # kurulmaz atildir -- ayni ornekleme tuzagi, bu sefer kendi elimden.
    out = []
    sources = [ROOT.parent / "test" / "_canary" / "variety.story"]
    sources += sorted((ROOT.parent / "test" / "_rubrik").glob("*.story"))
    # Hicbir kaynak yoksa kontrol HIC KOSMADI ve bunu soylemeli. Eskiden her
    # eksik kaynak sessizce atlanıyordu; hepsi eksikse dongu bir kez bile
    # donmuyor, ciktiya tek satir basilmiyor ve invaryant "saglam" sayiliyordu.
    # Uretenler: variety.py ve rubric_fixtures.py (sirayi tools/suit.py tutar).
    if not any(s.is_file() for s in sources):
        return ["cakisma kontrolu kosmadi: ne variety.story ne _rubrik/*.story "
                "var — once tools/variety.py ve tools/rubric_fixtures.py"]
    for source in sources:
        if not source.is_file():
            continue
        pkg = StoryPackage(source)
        hits = 0
        for part, ref in model.slide_index(pkg).items():
            root = pkg.parse(part)
            shape_list = root.find("shapeLst")
            boxes: list[tuple[str, tuple[float, float, float, float]]] = []
            for shape in list(shape_list) if shape_list is not None else []:
                text = model.shape_text(root, shape.get("g", "")).strip()
                rect = shapes.shape_rect(shape)
                if text and rect:
                    boxes.append((shape.get("name") or shape.tag, rect))
            for i, (name_a, a) in enumerate(boxes):
                for name_b, b in boxes[i + 1:]:
                    if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                        hits += 1
                        out.append(f"{source.stem}/{ref.basename}: {name_a} ve "
                                   f"{name_b} metin kutulari ust uste biniyor")
        print(f"metin kutusu ortusmesi ({source.stem}): "
              f"{'yok' if not hits else str(hits) + ' CIFT'}")
    return out[:5]


def tasan_yazilar(root, slayt_adi: str, stage) -> tuple[list[str], int, int]:
    """Bu slayttaki taşan yazılar: (liste, ölçülen, bant dışı). TEMEL + KATMAN.

    TEK YETKILI OLCU (K12). Bir donem bu hesap yalnizca check_text_fits'in
    icinde, satir arasinda duruyordu ve baska hicbir kontrol ona ulasamiyordu.
    Sonuc, olculdu (2026-08-17): SORU SLAYTLARINDA metin sigmasini olcen
    hicbir sey yoktu. check_question_frame kutunun ALT KENARINI oluyor,
    check_text_fits ise yalnizca _canary/variety.story'yi (icerik slaytlari)
    okuyor. Ikisinin arasindan gecen bir sik etiketi 97 birimlik kutuda 139
    birim istiyordu ve butun kapilar yesildi.

    Ikinci hesap yazmak yerine hesap disari alindi: cagiran KOK verir, olcu
    tek yerde kalir. Iki uygulama er ya da gec ayrisir ve ayristiginda
    hangisinin dogru oldugu okunamaz.

    KATMANLAR DA TARANIR. check_text_fits bir donem yalnizca
    `root.find("shapeLst")` okuyordu -- yani TEMEL katman. Uretilen soru
    slaydinin iki geri bildirim katmani var ve onlarda yazilan metin bu
    taramanin disindaydi. Kor nokta, kapsamin en pahali turu: tablo "tarandi"
    der, taranmayan yer hic gorunmez.

    GECERLILIK KOSULU degismedi: tahmin yalnizca shapes.CALIBRATED_RANGE
    icinde olculmustur, bant disi puntolar AYRICA SAYILIR. Onlar icin
    "sigiyor" demek olculmemis bir sayiya guvenmek olurdu (K8).
    """
    lo, hi = shapes.CALIBRATED_RANGE
    uzay = shapes.space_of(root, stage)
    slack = compose.FIT_TOLERANCE / 100 * uzay.slide_h
    over: list[str] = []
    checked = unmeasured = 0

    kaplar = [("temel", root.find("shapeLst"))]
    katmanlar = root.find("sldLayerLst")
    for i, katman in enumerate(list(katmanlar) if katmanlar is not None else []):
        kaplar.append((f"katman{i + 1}", katman.find("shapeLst")))

    for nere, kap in kaplar:
        for shape in list(kap) if kap is not None else []:
            text = model.shape_text(root, shape.get("g", "")).strip()
            rect = shapes.shape_rect(shape)
            if not text or not rect:
                continue
            _colour, size, _bold, _align = preview._text_style(shape)
            if not (lo <= size <= hi):
                unmeasured += 1
                continue
            checked += 1
            box_w, box_h = rect[2] - rect[0], rect[3] - rect[1]
            needed = _quiet(shapes.measured_text_height, text, size, box_w,
                            uzay, wrap=shapes.wraps(shape))
            # Yazanla AYNI tolerans, ayni birim. Kendi sayisini yazan bir
            # kontrol, yazma yolunun bilerek izin verdigi seyi kusur sayar.
            if needed > box_h + slack:
                over.append(f"{slayt_adi}/{nere} {size:.0f}pt {text[:26]!r} "
                            f"{needed:.0f} > {box_h:.0f}")
    return over, checked, unmeasured


def check_choice_shape() -> list[str]:
    """Şık kutusu bir MERCEK mi? Elips liste satırına gerilmiş mi?

    OLCULEN KUSUR (2026-08-19, panelle uretilen kurs): siklar `<oval>` ve
    1612.8x58.7 -- en/boy 27.5. Bir elips o orana gerilince MERCEK olur.

    KALIBRASYON BANDI: elle yapilmis kursta hicbir oval 1.6'yi asmiyor.
    Orada ovaller bir fotografin ustunde duran lekeler ve dogrudur; bant
    HEDEF degil REFERANS.

    "En/boy 27.5 kusurdur" tek basina YANLISTI: ayni kursta 48.2'ye kadar
    giden 65 kutu var, hepsi `textBox` -- gorunur silueti olmayan yazi.
    Karsilastirma SINIF ICINDE yapilir, ve bu kontrol yalnizca `oval`
    sinifina bakar.

    KAREYLE AYRILDI (tools/goz_kapsul.py): `prstGeom` cizimi belirliyor,
    tag DEGIL. O yuzden olcut prstGeom'un cocugu; tag'in `oval` kalmasi
    kusur degildir ve bu kontrol ona bakmaz.
    """
    import shutil
    from storyline_mcp import authoring

    source = ROOT.parent / "test" / "bos.story"
    work = ROOT.parent / "test" / "_canary" / "sik_sekli.story"
    if not source.is_file():
        return [f"sik sekli kontrolu kosmadi: {source.name} yok"]

    siklar = ["Alici listesini gondermeden once dogrula",
              "Baglantiyi yalnizca gereken kisiye ver",
              "Dosyayi kisiye ac, baglantisi olan herkese degil",
              "Erisim iznine bir bitis tarihi koy",
              "Yanlis gonderimi kime bildirecegini bil"]
    shutil.copy2(source, work)
    try:
        pkg = StoryPackage(work)
        picked = _quiet(authoring.pick_template_for_question, pkg,
                        "Hangileri dogru?", siklar)
        made = _quiet(authoring.add_question, pkg, picked["template"],
                      "Hangileri dogru?", siklar, [0, 1], eyebrow="Bolum 1")
        pkg.save(work, backup=False)
    except Exception as exc:
        return [f"sik sekli kontrolu kurulamadi: {type(exc).__name__}: "
                f"{str(exc)[:60]}"]

    def olc(dosya):
        """(mercek sayisi, olculen oval sayisi, en buyuk oran)."""
        p2 = StoryPackage(dosya)
        pt = next((q for q, r in model.slide_index(p2).items()
                   if r.basename == made["new_slide"]), None)
        if pt is None:
            return -1, 0, 0.0
        root = p2.parse(pt)
        mercek, n, en = 0, 0, 0.0
        for el in list(root.find("shapeLst") or []):
            if el.tag != "oval":
                continue
            kutu = shapes.shape_rect(el)
            if not kutu:
                continue
            w, h = kutu[2] - kutu[0], kutu[3] - kutu[1]
            if h <= 0:
                continue
            n += 1
            oran = w / h
            en = max(en, oran)
            elips = any(c.tag == "oval"
                        for g in el.iter("prstGeom") for c in list(g))
            if elips and oran > authoring.OVAL_BANDI:
                mercek += 1
        return mercek, n, en

    out: list[str] = []
    mercek, sayi, en = olc(work)
    # KOSTUGUNU KANITLA: hic oval olculmediyse "temiz" sonucu bos calismaktir.
    if sayi < len(siklar):
        return [f"sik sekli: {len(siklar)} sik verildi ama {sayi} oval "
                f"olculebildi — olcu bos calisti, sonucu 'temiz' sayilamaz"]
    if mercek:
        out.append(f"sik sekli: {mercek}/{sayi} sik hala ELIPS ve en/boy "
                   f"{en:.1f} (bant {authoring.OVAL_BANDI:.1f}) — liste "
                   f"satirina gerilmis elips mercek gorunuyor")

    # KANARYA: bir sikkin prstGeom'unu elipse geri cevir, olcu bagirmali.
    kanarya = "kurulamadi"
    k_dosya = ROOT.parent / "test" / "_canary" / "sik_sekli_k.story"
    shutil.copy2(work, k_dosya)
    kp = StoryPackage(k_dosya)
    k_part = next((q for q, r in model.slide_index(kp).items()
                   if r.basename == made["new_slide"]), None)
    if k_part:
        k_root = kp.parse(k_part)
        geri = 0
        for el in list(k_root.find("shapeLst") or []):
            if el.tag != "oval" or geri:
                continue
            for g in el.iter("prstGeom"):
                for c in list(g):
                    if c.tag == "roundRect":
                        g.remove(c)
                        ET.SubElement(g, "oval", {"vertexSet": "false"})
                        geri += 1
        if geri:
            kp.replace_xml(k_part, k_root)
            kp.save(k_dosya, backup=False)
            k_m, _n, k_en = olc(k_dosya)
            kanarya = ("yasiyor (%d mercek yakalandi)" % k_m if k_m
                       else "OLDU — elipse donen sik olcude gorunmuyor")
            if not k_m:
                out.append("sik sekli kanaryasi OLDU: bir sik elipse "
                           "cevrildigi halde olcu temiz dedi")

    print("sik sekli (%s): %d oval, en buyuk en/boy %.1f, mercek %d | "
          "kanarya: %s" % (picked["template"], sayi, en, mercek, kanarya))
    return out


LAYOUT_ZOR_BASLIK = ("Yemek sitesinden sirket parolaniza uzanan zincir "
                     "nasil kuruluyor")
LAYOUT_ZOR_GOVDE = ("Musteri gerildiginde sesin tonu degisir, cumleler kisalir "
                    "ve ayni sikayet farkli kelimelerle ucuncu kez tekrar eder.")
LAYOUT_ZOR_MADDE = [
    "Her hesaba ayri parola: birinin sizmasi digerlerini acmasin",
    "Uzunluk karmasikliktan onemlidir; dort bagimsiz kelime iyi",
    "Parola yoneticisi kullanin, tarayiciya kaydetmeyin",
    "Iki adimli dogrulamayi acin, SMS yerine uygulama secin",
    "Parolayi e-posta, WhatsApp veya not defterinde tasimayin",
]


def check_layout_bands() -> list[str]:
    """HER düzen, sert içerikle: bant metinden önce ayrılıyor mu?

    BU KONTROL YOKTU ve boslugu pahaliya mal oldu. 2026-08-19'da yedi
    duzen sert icerikle surulunce UCU birden kusurlu cikti:

        section  2.6 kat     content  3.2 kat     steps  2.9 kat

    Ucu de ayni sinif: metin ONCE ve SINIRSIZ yaziliyor, ogesayisi
    icerikten gelen gruba KALANI veriliyor. Ayni kural bu oturumda
    bullets, menu, _buttons ve soru cercevesinde de eksikti -- toplam
    YEDI dal. `coverage` ve `deadband` yedi duzeni zaten suruyor ama
    KENDI SPECS'iyle: kisa basliklar, kisa maddeler. Mutlu yol olcum
    yapmaz.

    ICERIK GERCEKTEN OLCULEN degerlerden: panelle uretilen kursta baslik
    medyani 24 (en uzun 32), govde 73 (en uzun 91), bes madde 50-60
    karakter. Prob'un eski icerigi 9 / 21 / 11-22 idi ve hicbir kusur
    uretmiyordu.

    OLCUT ADET DEGIL ORAN, arti TABAN ASIMI ayri sayilir: slayt disina
    tasan bir sekil kozmetik degil.
    """
    import shutil
    from storyline_mcp import compose, preview

    source = ROOT.parent / "test" / "bos.story"
    if not source.is_file():
        return [f"duzen bantlari kontrolu kosmadi: {source.name} yok"]

    AGIR = 2.0

    def olc(dosya, part):
        p2 = StoryPackage(dosya)
        sahne = shapes.stage_size(p2)
        root = p2.parse(part)
        uzay = shapes.space_of(root, sahne)
        _sw, sh = shapes.slide_size(root)
        en, sekil, asan = 0.0, 0, 0
        for el in list(root.find("shapeLst") or []):
            kutu = shapes.shape_rect(el)
            if not kutu:
                continue
            sekil += 1
            if kutu[3] > sh + 1:
                asan += 1
            metin = model.shape_text(root, el.get("g", "")).strip()
            if not metin:
                continue
            _c, punto, _b, _a = preview._text_style(el)
            gereken = shapes.measured_text_height(
                metin, punto, kutu[2] - kutu[0], uzay, wrap=shapes.wraps(el))
            en = max(en, gereken / max(kutu[3] - kutu[1], 1.0))
        return en, sekil, asan

    out: list[str] = []
    kotu, olculen = 0.0, 0
    for duzen in compose.LAYOUTS:
        work = ROOT.parent / "test" / "_canary" / f"duzen_{duzen}.story"
        shutil.copy2(source, work)
        try:
            pkg = StoryPackage(work)
            part = next(iter(model.slide_index(pkg)))
            _quiet(compose.compose_slide, pkg, part, duzen,
                   title=LAYOUT_ZOR_BASLIK, eyebrow="Bolum 1",
                   body=LAYOUT_ZOR_GOVDE, bullets=list(LAYOUT_ZOR_MADDE),
                   buttons=list(LAYOUT_ZOR_MADDE))
            pkg.save(work, backup=False)
        except Exception as exc:
            out.append(f"duzen bandi ({duzen}): cizilemedi — "
                       f"{type(exc).__name__}: {str(exc)[:50]}")
            continue
        en, sekil, asan = olc(work, part)
        # KOSTUGUNU KANITLA: bos bir slayt "temiz" degil, OLCULEMEDI'dir.
        if sekil < 2:
            out.append(f"duzen bandi ({duzen}): {sekil} sekil cizildi — "
                       f"olcu bos calisti, sonucu 'temiz' sayilamaz")
            continue
        olculen += 1
        kotu = max(kotu, en)
        if en > AGIR:
            out.append(f"duzen bandi ({duzen}): metin kutusunu {en:.1f} KAT "
                       f"asiyor (sinir {AGIR:.1f}) — bant metinden once "
                       f"ayrilmamis")
        if asan:
            out.append(f"duzen bandi ({duzen}): {asan} sekil slaydin "
                       f"tabanini asiyor")

    # KANARYA: bir duzenin kutularini ezip olcu bagirmali.
    kanarya = "kurulamadi"
    kaynak_k = ROOT.parent / "test" / "_canary" / "duzen_content.story"
    if kaynak_k.is_file():
        k_dosya = ROOT.parent / "test" / "_canary" / "duzen_k.story"
        shutil.copy2(kaynak_k, k_dosya)
        kp = StoryPackage(k_dosya)
        k_part = next(iter(model.slide_index(kp)))
        k_root = kp.parse(k_part)
        _sw, k_sh = shapes.slide_size(k_root)
        ezildi = 0
        for el in list(k_root.find("shapeLst") or []):
            kutu = shapes.shape_rect(el)
            if not kutu or not model.shape_text(k_root, el.get("g", "")).strip():
                continue
            shapes.set_loc(el, kutu[0], kutu[1], kutu[2], kutu[1] + 0.03 * k_sh)
            ezildi += 1
        if ezildi:
            kp.replace_xml(k_part, k_root)
            kp.save(k_dosya, backup=False)
            k_en, _s, _a = olc(k_dosya, k_part)
            kanarya = ("yasiyor (%.1f kat yakalandi)" % k_en if k_en > AGIR
                       else "OLDU — ezilmis kutular olcude gorunmuyor")
            if k_en <= AGIR:
                out.append("duzen bandi kanaryasi OLDU: kutular %3'e "
                           "ezildigi halde olcu temiz dedi")

    print("duzen bantlari (%d/%d duzen, sert icerik): en buyuk tasma %.1f kat "
          "(sinir %.1f) | kanarya: %s"
          % (olculen, len(compose.LAYOUTS), kotu, AGIR, kanarya))
    return out


def check_button_band() -> list[str]:
    """Buton kutusu etiketini TAŞIYACAK kadar ayrıldı mı?

    OLCULEN KUSUR (2026-08-19, uretilmis kursun geri cekilme menusu):
    buton kutusu %4.0 (21.6 birim), etiket %8.5 (46 birim) istiyordu --
    2.1 kat. Ustelik dort butonluk yigin %103.3'te bitiyordu, yani SLAYTIN
    DISINDA.

    MEKANIZMA, KART BANDIYLA BIREBIR AYNI: rezervasyon
    `n * BUTTON_STACK_MIN_H` idi -- yani TABANI deger olarak kullanan,
    metni hic sormayan bir sabit. `_buttons` icinde de `each = max(each,
    4.0)` kosulsuzdu ve banda bakmiyordu: taban ile bant carpistiginda
    taban sessizce kazaniyordu.

    Bu, ayni kuralin eksik oldugu BESINCI dal (content, cover, bullets,
    menu + `_buttons`in kendisi). K25.

    OLCUT ADET DEGIL ORAN -- kart bandindaki ile ayni sebeple.
    """
    import shutil
    from storyline_mcp import compose, preview

    source = ROOT.parent / "test" / "bos.story"
    work = ROOT.parent / "test" / "_canary" / "buton_bandi.story"
    if not source.is_file():
        return [f"buton bandi kontrolu kosmadi: {source.name} yok"]

    butonlar = [
        "Alici listesini gondermeden once bir kez daha dogrula",
        "Paylasim baglantisini yalnizca isi geregi gereken kisiye ver",
        "Dosyayi kisiye ac, baglantisi olan herkese acik birakma",
        "Erisim iznine bir bitis tarihi koy ve suresi dolunca gozden gecir",
        "Yanlis gonderimi fark ettiginde kime bildirecegini onceden bil",
    ]
    shutil.copy2(source, work)
    try:
        pkg = StoryPackage(work)
        part = next(iter(model.slide_index(pkg)))
        _quiet(compose.compose_slide, pkg, part, "menu",
               title="Paylasilan bir dosyayi gonderirken hangileri dogru?",
               buttons=butonlar)
        pkg.save(work, backup=False)
    except Exception as exc:
        return [f"buton bandi kontrolu kurulamadi: {type(exc).__name__}: "
                f"{str(exc)[:60]}"]

    def olc(dosya):
        """(en buyuk tasma orani, olculen buton sayisi, taban asan sayi)."""
        p2 = StoryPackage(dosya)
        sahne = shapes.stage_size(p2)
        pt = next(iter(model.slide_index(p2)))
        root = p2.parse(pt)
        uzay = shapes.space_of(root, sahne)
        _sw, sh = shapes.slide_size(root)
        en, n, asan = 0.0, 0, 0
        for el in list(root.find("shapeLst") or []):
            metin = model.shape_text(root, el.get("g", "")).strip()
            kutu = shapes.shape_rect(el)
            if not metin or not kutu or metin not in butonlar:
                continue
            n += 1
            if kutu[3] > sh + 1:
                asan += 1
            _c, punto, _b, _a = preview._text_style(el)
            gereken = shapes.measured_text_height(
                metin, punto, kutu[2] - kutu[0], uzay, wrap=shapes.wraps(el))
            en = max(en, gereken / max(kutu[3] - kutu[1], 1.0))
        return en, n, asan

    out: list[str] = []
    AGIR = 1.6
    en, sayi, asan = olc(work)
    # KOSTUGUNU KANITLA: hic buton olculmediyse "temiz" bos calismaktir.
    if sayi < len(butonlar):
        return [f"buton bandi: {len(butonlar)} buton verildi ama {sayi} tanesi "
                f"olculebildi — olcu bos calisti, sonucu 'temiz' sayilamaz"]
    if en > AGIR:
        out.append(f"buton bandi: etiket kutusunu {en:.1f} KAT asiyor "
                   f"(sinir {AGIR:.1f}) — bant buton sayisindan degil sabit "
                   f"tabandan ayrilmis")
    if asan:
        out.append(f"buton bandi: {asan} buton slaydin tabanini asiyor — "
                   f"yigin banda sigmadigi halde yukari kaydirilmamis")

    # KANARYA: kutulari olculen cokmus degere (%4.0) ezip olcu bagirmali.
    kanarya = "kurulamadi"
    k_dosya = ROOT.parent / "test" / "_canary" / "buton_bandi_k.story"
    shutil.copy2(work, k_dosya)
    kp = StoryPackage(k_dosya)
    k_part = next(iter(model.slide_index(kp)))
    k_root = kp.parse(k_part)
    _sw, k_sh = shapes.slide_size(k_root)
    ezildi = 0
    for el in list(k_root.find("shapeLst") or []):
        metin = model.shape_text(k_root, el.get("g", "")).strip()
        kutu = shapes.shape_rect(el)
        if not kutu or metin not in butonlar:
            continue
        shapes.set_loc(el, kutu[0], kutu[1], kutu[2], kutu[1] + 0.04 * k_sh)
        ezildi += 1
    if ezildi:
        kp.replace_xml(k_part, k_root)
        kp.save(k_dosya, backup=False)
        k_en, _n, _a = olc(k_dosya)
        kanarya = ("yasiyor (%.1f kat yakalandi)" % k_en if k_en > AGIR
                   else "OLDU — cokmus buton bandi olcude gorunmuyor")
        if k_en <= AGIR:
            out.append("buton bandi kanaryasi OLDU: kutular %4.0'a ezildigi "
                       "halde olcu temiz dedi")

    print("buton bandi (%d buton): en buyuk tasma %.1f kat (sinir %.1f), "
          "taban asan %d | kanarya: %s"
          % (sayi, en, AGIR, asan, kanarya))
    return out


def check_card_band() -> list[str]:
    """Kart bandi metnini TASIYACAK kadar ayrildi mi?

    OLCULEN KUSUR (2026-08-19, panelle uretilen kurs, gozle goruldu): kartli
    slaytlarda madde metinleri ust uste biniyor ve okunmuyordu. Olculdu: 20
    govde yazisi MEDYAN 4.3 KAT tasiyordu (en kotu 5.7).

    MEKANIZMA: `bullets` dali basligi ONCE yaziyor, kartlara KALANI
    veriyordu. %40 genisliginde bir sutuna yazilan uzun bir baslik %52.8
    yukseklik aldi; kartlara %19.8 kaldi ve bes kart 2.2'ye bolundu --
    MIN_CARD_H'nin (%10.8) BESTE BIRI. Daha uzun bir baslikta ayrilan band
    NEGATIF olculdu: -27.2.

    "Kart bandini metin dagitilmadan ONCE ayir" kurali `content` dalinda da
    `cover` dalinda da VARDI, `bullets` dalinda yoktu. _distribute'un yorumu
    ayni unutmanin ucuncu tekrari oldugunu yaziyor; bu DORDUNCUSU. O yuzden
    olcu artik _card_band'de, TEK yerde -- ve burada kilitleniyor.

    OLCUT ADET DEGIL ORAN. Duzeltmeden sonra adet 20'den 14'e indi (az), ama
    AGIR tasma 15'ten 0'a indi. Adede bakan bir kontrol bu duzeltmeyi
    "kucuk bir iyilesme" diye okurdu; kusuru tasiyan sey orandi.

    KABUL EDILEN SINIR: 1.2-1.6 kat tasma (bir satir payi) bu kontrolde
    gecer. Kapatilan sey, kutunun metnin BESTE BIRINE dusmesi.
    """
    import shutil
    from storyline_mcp import compose, preview

    source = ROOT.parent / "test" / "bos.story"
    work = ROOT.parent / "test" / "_canary" / "kart_bandi.story"
    if not source.is_file():
        return [f"kart bandi kontrolu kosmadi: {source.name} yok"]

    baslik = "Yemek sitesinden sirket parolaniza uzanan zincir nasil kurulur"
    maddeler = [
        "Her hesaba ayri parola: birinin sizmasi digerlerini acmasin",
        "Uzunluk karmasikliktan onemlidir; dort bagimsiz kelime iyi",
        "Parola yoneticisi kullanin, tarayiciya kaydetmeyin",
        "Iki adimli dogrulamayi acin, SMS yerine uygulama secin",
        "Parolayi e-posta, WhatsApp veya not defterinde tasimayin",
    ]
    shutil.copy2(source, work)
    try:
        pkg = StoryPackage(work)
        part = next(iter(model.slide_index(pkg)))
        _quiet(compose.compose_slide, pkg, part, "bullets",
               title=baslik, eyebrow="Parola hijyeni", bullets=maddeler)
        pkg.save(work, backup=False)
    except Exception as exc:
        return [f"kart bandi kontrolu kurulamadi: {type(exc).__name__}: "
                f"{str(exc)[:60]}"]

    def olc(dosya):
        """(en buyuk tasma orani, olculen kart sayisi)."""
        p2 = StoryPackage(dosya)
        sahne = shapes.stage_size(p2)
        pt = next(iter(model.slide_index(p2)))
        root = p2.parse(pt)
        uzay = shapes.space_of(root, sahne)
        en, n = 0.0, 0
        for el in list(root.find("shapeLst") or []):
            if el.get("name") != "Body":
                continue
            metin = model.shape_text(root, el.get("g", "")).strip()
            kutu = shapes.shape_rect(el)
            if not metin or not kutu:
                continue
            _c, punto, _b, _a = preview._text_style(el)
            gereken = shapes.measured_text_height(
                metin, punto, kutu[2] - kutu[0], uzay, wrap=shapes.wraps(el))
            en = max(en, gereken / max(kutu[3] - kutu[1], 1.0))
            n += 1
        return en, n

    out: list[str] = []
    AGIR = 2.0
    en, sayi = olc(work)
    # KOSTUGUNU KANITLA: sifir kart olculduyse "temiz" sonucu bos calismaktir.
    if sayi < len(maddeler):
        return [f"kart bandi: {len(maddeler)} madde verildi ama {sayi} kart "
                f"olculebildi — olcu bos calisti, sonucu 'temiz' sayilamaz"]
    if en > AGIR:
        out.append(f"kart bandi: govde metni kutusunu {en:.1f} KAT asiyor "
                   f"(sinir {AGIR:.1f}) — kart bandi metinden once ayrilmamis, "
                   f"maddeler ust uste biniyor")

    # KANARYA: kart kutularini eski cokmus olcusune indir, olcu bagirmali.
    kanarya = "kurulamadi"
    k_dosya = ROOT.parent / "test" / "_canary" / "kart_bandi_k.story"
    shutil.copy2(work, k_dosya)
    kp = StoryPackage(k_dosya)
    k_part = next(iter(model.slide_index(kp)))
    k_root = kp.parse(k_part)
    _sw, sh = shapes.slide_size(k_root)
    ezildi = 0
    for el in list(k_root.find("shapeLst") or []):
        if el.get("name") != "Body":
            continue
        kutu = shapes.shape_rect(el)
        if not kutu:
            continue
        # olculen cokmus yukseklik: slaytin %2.2'si
        shapes.set_loc(el, kutu[0], kutu[1], kutu[2], kutu[1] + 0.022 * sh)
        ezildi += 1
    if ezildi:
        kp.replace_xml(k_part, k_root)
        kp.save(k_dosya, backup=False)
        k_en, _n = olc(k_dosya)
        kanarya = ("yasiyor (%.1f kat yakalandi)" % k_en if k_en > AGIR
                   else "OLDU — cokmus kart bandi olcude gorunmuyor")
        if k_en <= AGIR:
            out.append("kart bandi kanaryasi OLDU: kutular %2.2'ye ezildigi "
                       "halde olcu temiz dedi")

    print("kart bandi (%d madde, %d kart): en buyuk tasma %.1f kat "
          "(sinir %.1f) | kanarya: %s" % (len(maddeler), sayi, en, AGIR, kanarya))
    return out


def check_text_fits() -> list[str]:
    """Yazı kutusuna sığıyor mu -- yani düzen bozuluyor mu?

    ESKI GEREKCE YANLIS CIKTI ve olcumle duzeltildi (2026-08-16). Once soyle
    yaziyordu: "Storyline tasan metni KIRPAR, dolayisiyla tasma onizlemede
    gorunur ama kursta gorunmez." Bu, tasmayi bir DOGRULUK hatasi yapiyordu.

    Sinandi: 20 birimlik kutuya on sert satir, Storyline Preview. ON SATIRIN
    HEPSI OKUNUYOR -- kutunun disina tasmis, hicbiri kesilmemis. Storyline
    KIRPMIYOR.

    Yani bu olcu bir doğruluk kontrolu degil, DUZEN kontrolu: tasan metin
    kaybolmuyor, komsusunun uzerine biniyor. Onemsiz degil ama sinifi farkli,
    ve bu fark neyin ne kadar acil oldugunu belirliyor.

    UI'ya inmeden olculebilir: kutunun yuksekligi dosyada yaziyor, metnin
    gerektirdigi yukseklik shapes.measured_text_height ile hesaplanabilir.
    Ikisinin farki kirpmadir.

    GECERLILIK KOSULU: tahmin yalnizca shapes.CALIBRATED_RANGE icinde
    olculmustur. Bu yuzden bant disi puntolar ayrica sayilir -- onlar icin
    "sigiyor" demek, olculmemis bir sayiya guvenmek olur. compose._Page
    olcegi 38pt'de durdurdugu icin bestelenen slaytlarda bu sayinin sifira
    yakin kalmasi beklenir; buyumesi, olcegin tavani astigi anlamina gelir.
    """
    source = ROOT.parent / "test" / "_canary" / "variety.story"
    if not source.is_file():
        # Once yalnizca bu satir basiliyor ve BOS LISTE donuyordu -- yani
        # mesaj gorunuyor ama invaryant GECIYORDU. Bir uyari basip gecmek,
        # gecmenin en sinsi bicimi: ciktida bir aciklama var, verdikt yesil.
        print("metin tasmasi: variety.story yok, once tools/variety.py")
        return ["tasma kontrolu kosmadi: variety.story yok — once "
                "tools/variety.py (sirayi tools/suit.py tutar)"]
    pkg = StoryPackage(source)
    over, checked, unmeasured = [], 0, 0
    for part, ref in model.slide_index(pkg).items():
        o, c, u = tasan_yazilar(pkg.parse(part), ref.basename,
                                shapes.stage_size(pkg))
        over += o
        checked += c
        unmeasured += u
    print(f"metin tasmasi ({checked} yazi olculdu, {unmeasured} bant disi "
          f"atlandi): {'yok' if not over else str(len(over)) + ' TASMA'}")
    # Mesaj da duzeltildi: "Storyline kirpar" OLCUMLE YANLIS cikti.
    # Metin kaybolmuyor, kutunun disina tasip komsusunun uzerine biniyor.
    return [f"metin kutusunu asiyor (kirpilmaz, komsusuna biner): {o}"
            for o in over[:5]]


def check_variant_reach() -> list[str]:
    """Sözlükteki her ad gerçekten üretiliyor mu?

    Bu oturumda sözlükte altı ad vardı ve motor dördüne ulaşıyordu: seçim
    `sum(ord(c)) % n` ile yapılıyordu ve karakter toplamı benzer başlıkları
    aynı kovaya yığıyordu. Hiçbir şey bağırmadı -- üretilen dosya geçerli,
    ardışık tekrar sıfır, çeşitlilik testi geçiyor. Yalnızca iki varyant hiç
    doğmuyordu.

    Bu, "göremediğini yokluk sanmak" kalıbının seçim tarafındaki hâli, ve
    sözlüğe her yeni ad eklendiğinde geri gelebilir. Test, yeterince uzun bir
    koşuda her adın en az bir kez çıkmasını ister; çıkmayan ad, yazılmış ama
    erişilemeyen bir varyanttır.
    """
    # Tohumlar GERCEK icerikten gelir, uretilmis degil.
    #
    # Ilk yazilisinda tohumlar "Baslik 0", "Baslik 1" ... idi ve test, yazildigi
    # hatayi yakalayamadi: sentetik tohumlarin karakter toplami duzenli artiyor,
    # dolayisiyla zayif dagitici bile butun kovalari geziyor. Hata gercek
    # basliklarin birbirine yakin toplamlar uretmesinden cikmisti. Kolay veriyle
    # kurulan bir invaryant, korudugunu sandigi seyi korumaz.
    corpus = [(s.get("title") or "") + (s.get("body") or "")[:12]
              for s in variety.DECK]
    out = []
    for layout in sorted(compose.VARIANTS):
        names = compose.variants_for(layout)
        history: list[str] = []
        for seed in corpus:
            history.append(compose.variant_for(
                layout, seed=seed, avoid=history)["name"])
        missing = sorted(set(names) - set(history))
        print(f"varyant erisilebilirligi ({layout}, {len(corpus)} gercek baslik): "
              f"{len(set(history))}/{len(names)}"
              f"{'' if not missing else '  ULASILMAYAN: ' + ', '.join(missing)}")
        if missing:
            out.append(
                f"{layout} duzeninde {len(missing)} varyant {len(corpus)} gercek "
                f"baslikla hic uretilmedi ({', '.join(missing)}) — sozlukte "
                "yazili ama erisilemez")
    return out



def check_diagnoses() -> list[str]:
    """Üç teşhis birbirinden ayrı kalıyor mu?

    "Şablon dar" ile "kök çerçeveyi yedi" farklı işler gerektiriyor: birincisi
    kataloğa şablon eklemekle çözülür, ikincisi çözülmez. İkisi tek bir
    "hiçbir şablon uymuyor"a çökerse, teşhis birini yanlış işe gönderir --
    ve çıktı yine geçerli olduğu için hiçbir şey bağırmaz.
    """
    from storyline_mcp import authoring
    from storyline_mcp.package import StoryPackage

    source = ROOT.parent / "test" / "0_duz_kopya.story"
    if not source.is_file():
        return ["teshis kontrolu icin kaynak proje yok"]
    pkg = StoryPackage(source)

    short = "Ne yaparsin?"
    # Gercekten cerceveyi yiyen bir kok. Ilk yazdigim kisa surumu bu testin
    # kendisi yakaladi: yeterince uzun degildi, sigiyordu, teshis "metin"
    # yerine "plan" donuyordu -- negatif vakanin test verisi de dogrulanmali.
    long_stem = ("Sirket agina baglaniyken tanimadigin bir gonderenden gelen ve "
                 "icinde acil oldugu belirtilen bir baglanti bulunan e-postayi "
                 "aldin. Baglantiya tikladiginda seni kurumsal giris sayfasina "
                 "benzeyen bir forma yonlendiriyor ve kullanici adin ile "
                 "parolani istiyor. Ayni anda telefonuna bir dogrulama kodu "
                 "geliyor ve mesajda kodu kimseyle paylasmamandan bahsediliyor. "
                 "Bu durumda asagidakilerden hangisi yapilmasi gereken ilk ve "
                 "en dogru adimdir, dikkatlice dusun.")

    expect = [("kisa/3", short, ["Evet", "Hayir", "Belki"], "plan"),
              ("kisa/7", short, [f"S{i}" for i in range(7)], "sablon"),
              ("uzun/3", long_stem, ["Evet", "Hayir", "Belki"], "metin")]

    out = []
    for name, stem, choices, want in expect:
        try:
            _quiet(authoring.pick_template_for_question, pkg, stem, choices)
            got = "plan"
        except authoring.StemStarvesFrame:
            got = "metin"
        except authoring.NoTemplateFits:
            got = "sablon"
        if got != want:
            out.append(f"teshis {name}: beklenen {want!r}, gelen {got!r}")
    print(f"teshis ayrimi ({len(expect)} durum): "
          f"{'saglam' if not out else 'BOZUK'}")
    return out



def check_thresholds_independent() -> list[str]:
    """Hiçbir guard, eşiğini koruduğu motordan okumuyor mu?

    Kurali koda tasiyan kontrol. Kaynak ayristirilir; bir check_* fonksiyonu
    icinde motor sabiti bir KARSILASTIRMANIN parcasiysa, o guard kendi
    olcusuyle test ediliyor demektir ve esigi kaldiran degisiklik onu
    sessizce gecer.

    Yalnizca `Compare` icindekilere bakilir: ayni sabiti bir HESAPTA kullanmak
    (mesela pay hesaplamak) sorun degil, ESIK olarak kullanmak sorundur.

    MOTOR SABITLERI LISTEDEN DEGIL, MODULDEN OKUNUR (2026-08-17). Eskiden
    elle yazilmis bir `MOTOR_SABITLERI` kumesi vardi; olu dal temizliginde
    ESIK_ISTISNALARI ile birlikte silindi ve kaynagi kurtarilamadi. Yerine
    elle liste KONMADI, cunku elle liste bu kontrolun kendi hatasini tasir:
    motora yeni bir sabit eklendiginde listeye eklenmezse kontrol o sabiti
    hic gormez ve sessizce gecer -- tam olarak kovaladigi sey.
    Kume artik compose ve shapes'in modul duzeyindeki SAYISAL sabitlerinden
    turetiliyor; yeni sabit eklendigi anda kapsama girer.

    ISTISNA YOK, ve bos olmasi bir iddiadir. Eski surumde bir istisna listesi
    vardi ve icerigi bilinmiyor. Bos baslatildi: bir guard hakli olarak motor
    sabitiyle karsilastirma yapiyorsa kontrol bagirir, ve o zaman istisna
    GEREKCESIYLE yazilir. Bilinmeyen bir listeyi tahminle doldurmak,
    olculmemis bir muafiyet dagitmak olurdu.
    """
    import ast

    def _motor_sabitleri() -> set[str]:
        out = set()
        for mod_adi, mod in (("compose", compose), ("shapes", shapes)):
            for ad in dir(mod):
                if ad.startswith("_") or not ad.isupper():
                    continue
                if isinstance(getattr(mod, ad), (int, float)) and \
                        not isinstance(getattr(mod, ad), bool):
                    out.add(f"{mod_adi}.{ad}")
        return out

    MOTOR_SABITLERI = _motor_sabitleri()
    ESIK_ISTISNALARI: set[tuple[str, str]] = set()

    kaynak = Path(__file__).read_text(encoding="utf-8")
    agac = ast.parse(kaynak)
    out: list[str] = []
    denetlenen = 0

    def adi(node) -> str | None:
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            return f"{node.value.id}.{node.attr}"
        return None

    for fn in ast.walk(agac):
        if not isinstance(fn, ast.FunctionDef) or not fn.name.startswith("check_"):
            continue
        denetlenen += 1
        for node in ast.walk(fn):
            if not isinstance(node, ast.Compare):
                continue
            for parca in [node.left] + list(node.comparators):
                for alt in ast.walk(parca):
                    ad = adi(alt)
                    if ad in MOTOR_SABITLERI and \
                            (fn.name, ad) not in ESIK_ISTISNALARI:
                        out.append(
                            f"{fn.name}: esigi {ad}'den okuyor — korudugu "
                            "sabitle karsilastiriyor, sabiti degistiren bir "
                            "degisiklik bu guard'i SESSIZCE gecer "
                            "(EXPECTED_* gibi bagimsiz bir sabit yazin)")

    # EXPECTED_* sabitleri gercekten LITERAL mi -- yoksa motordan mi turetilmis.
    for node in agac.body:
        if not isinstance(node, ast.Assign):
            continue
        for hedef in node.targets:
            if isinstance(hedef, ast.Name) and hedef.id.startswith("EXPECTED_"):
                if not isinstance(node.value, ast.Constant):
                    out.append(f"{hedef.id}: literal degil — bagimsiz olmasi "
                               "gereken bir sabit motordan turetilmis")

    benzersiz = sorted(set(out))
    print(f"esik bagimsizligi ({denetlenen} check_* fonksiyonu): "
          f"{'saglam' if not benzersiz else str(len(benzersiz)) + ' IHLAL'}")
    return benzersiz


def check_wrap_model() -> list[str]:
    """Sarma, kutunun özelliği olarak okunuyor mu -- iki yönde de?

    Model bir donem HER kutunun sardigini varsayiyordu. Olculdu: wrap="none"
    tasiyan bir kutuda 111 harflik metin Storyline'da TEK SATIR cizildi
    (gozle dogrulandi), model 7 satir ongoruyordu. O tek varsayim, uretilmis
    bir kurstaki 38 "tasma" adayinin 16'sini uretti -- hepsi artefakt.

    IKI YON, cunku tek yon yarim koruma:
      sarmaz  -> satir sayisi PARAGRAF sayisi kadar olmali. Bu yon,
                 wrap'i tumden yok sayan bir gerilemeyi yakalar.
      sarar   -> satir sayisi sarma hesabina gore olmali. Bu yon,
                 wrap="true" olanlari yanlislikla sarmayan sayan bir
                 gerilemeyi yakalar -- ki o gerileme tahmini DUSURUR ve
                 dusuk tahmin bu modelde en kotu hatadir (kutu kisa kalir,
                 metin komsusunun ustune biner).
    """
    metin = ("Bu metin kutuya sigmayacak kadar uzundur ve dort bes satir "
             "gerektirir; kirpilmadan durabilmesi mumkun degildir.")
    iki_paragraf = "Birinci satir.\nIkinci satir."
    # TUTARLI UZAY: bu kontrol sarma modelini sinar, uzay donusumunu degil.
    # Sahne slaytla ayni -> her iki carpan 1.0, yani olcum yalnizca sarmayi
    # gorur. Karisik uzayin kendi kontrolu check_choice_admission'da.
    genislik, punto = 219.0, 14.0
    slayt = shapes.Space(720.0, 540.0, 720.0, 540.0)

    sarmaz = _quiet(shapes.measured_text_height, metin, punto, genislik,
                    slayt, wrap=False)
    sarar = _quiet(shapes.measured_text_height, metin, punto, genislik,
                   slayt, wrap=True)
    tek_satir = _quiet(shapes.measured_text_height, "kisa", punto, genislik,
                       slayt, wrap=False)
    iki = _quiet(shapes.measured_text_height, iki_paragraf, punto, genislik,
                 slayt, wrap=False)

    out = []
    # 1. Sarmayan kutuda uzunluk yuksekligi DEGISTIRMEMELI.
    if abs(sarmaz - tek_satir) > 0.01:
        out.append(f"wrap modeli: sarmayan kutuda uzun metin {sarmaz:.1f}, "
                   f"kisa metin {tek_satir:.1f} — uzunluk yuksekligi "
                   "etkiliyor, oysa sarma yok")
    # 2. Ama PARAGRAF sayisi etkilemeli.
    if iki <= tek_satir + 0.01:
        out.append(f"wrap modeli: sarmayan kutuda iki paragraf {iki:.1f}, "
                   f"tek paragraf {tek_satir:.1f} — satir sonu sayilmiyor")
    # 3. Ters yon: sarma acikken uzun metin GERCEKTEN daha yuksek olmali.
    if sarar <= sarmaz + 0.01:
        out.append(f"wrap modeli: sarma acikken {sarar:.1f}, kapaliyken "
                   f"{sarmaz:.1f} — sarma hesabi devre disi kalmis, tahmin "
                   "DUSUK cikiyor")
    # 4. Nitelik okumasi: yoksa sarar sayilmali (bilincli yon secimi).
    import xml.etree.ElementTree as _ET
    for deger, bekle in (("true", True), ("none", False), ("false", False),
                         (None, True)):
        el = _ET.Element("textBox")
        if deger is not None:
            el.set("wrap", deger)
        if shapes.wraps(el) is not bekle:
            out.append(f"wrap niteligi {deger!r} icin {shapes.wraps(el)} "
                       f"okundu, {bekle} bekleniyordu")

    print(f"sarma modeli (iki yon + nitelik okumasi): "
          f"{'saglam' if not out else 'BOZUK'}"
          f"  sarmaz={sarmaz:.1f} sarar={sarar:.1f}")
    return out


def check_choice_labels() -> list[str]:
    """Öğrenci şık etiketlerini TIKLAMADAN okuyabiliyor mu?

    OLCULEN KUSUR (2026-08-19, panelle uretilen kurs, gozle goruldu):
    coktan-secmeli sorularda ogrenci BES BOS KAPSUL goruyordu. Etiket ancak
    tiklayinca beliriyordu -- yani neyi sectigini okumadan seciyordu.

    MEKANIZMA: gomulu `freePickManyIntr:5` tohumu bir SICAK NOKTA
    etkilesimi (elle yapilmis kursun "bu odada bes risk var, uzerine tikla"
    slaydindan hasat edilmis). Orada ovaller bir fotografin ustunde durur ve
    etiketin gorunmemesi DOGRUDUR. Biz o tohumu metin listesi olarak
    kullaniyoruz ve `adapt_seeded_slide` fotografi siliyor -- geriye
    etiketsiz kapsuller kaliyor.

    NEDEN 5 SIK: mevcut `check_question_frame` fikstuuru 2 sikli ve
    `freePickOneIntr` seciyor; o tohumda etiketler zaten Normal'da. Coktan
    secmeli yol o kesitte HIC gorunmuyordu -- kusurun uretimde olup
    kontrolde olmamasinin sebebi buydu (K1).

    A1 (skor kaydedilmiyor) ve submitG (gonder calismiyor) ile ayni sinif:
    dosya gecerli, hicbir yapisal kontrol bagirmaz, soru islevsiz.
    """
    import shutil
    from storyline_mcp import authoring

    source = ROOT.parent / "test" / "bos.story"
    work = ROOT.parent / "test" / "_canary" / "sik_etiket.story"
    if not source.is_file():
        return [f"sik etiketi kontrolu kosmadi: {source.name} yok"]

    siklar = ["Her hesaba ayri parola", "Iki adimli dogrulama",
              "Ayda bir rakam ekle", "Dort kelimelik parola",
              "Kendine e-postayla gonder"]
    shutil.copy2(source, work)
    out: list[str] = []
    try:
        pkg = StoryPackage(work)
        picked = _quiet(authoring.pick_template_for_question, pkg,
                        "Hangileri dogru?", siklar)
        made = _quiet(authoring.add_question, pkg, picked["template"],
                      "Hangileri dogru?", siklar, [0, 1], eyebrow="Bolum 1")
        pkg.save(work, backup=False)
    except Exception as exc:
        print(f"sik etiketi: {len(siklar)} sikli soru uretilemedi "
              f"({type(exc).__name__})")
        return [f"sik etiketi kontrolu kurulamadi: {type(exc).__name__}: "
                f"{str(exc)[:60]}"]

    gorunur, toplam = _etiket_gorunurlugu(StoryPackage(work), made["new_slide"])
    if toplam and gorunur < toplam:
        out.append(
            f"sik etiketi: {toplam} sikkin {toplam - gorunur} tanesi Normal "
            f"durumda ETIKETSIZ — ogrenci bos kapsul goruyor ve neyi sectigini "
            f"okumadan seciyor")

    # KANARYA: bir sikkin Normal etiketini kasten sil, olcu bagirmali.
    kanarya = "kurulamadi"
    k_dosya = ROOT.parent / "test" / "_canary" / "sik_etiket_k.story"
    shutil.copy2(work, k_dosya)
    kp = StoryPackage(k_dosya)
    part = next((p for p, r in model.slide_index(kp).items()
                 if r.basename == made["new_slide"]), None)
    if part:
        root = kp.parse(part)
        _tag, intr = authoring._find_interaction(root)
        by = {el.get("g"): el for el in root.iter() if el.get("g")}
        silindi = 0
        for g in authoring._choice_shape_guids(intr)[:1]:
            for st in (by.get(g) or []).iter("state") if g in by else []:
                if (st.get("name") or "").lower() != "normal":
                    continue
                lst = st.find("shapeLst")
                for c in list(lst) if lst is not None else []:
                    if c.tag == "textBox":
                        lst.remove(c)
                        silindi += 1
        if silindi:
            kp.replace_xml(part, root)
            kp.save(k_dosya, backup=False)
            g2, t2 = _etiket_gorunurlugu(StoryPackage(k_dosya), made["new_slide"])
            if g2 >= t2:
                kanarya = "OLDU"
                out.append("sik etiketi KANARYASI olmedi: silinen etiket "
                           "yakalanmadi — olcu atil")
            else:
                kanarya = f"yasiyor ({t2 - g2} etiketsiz yakalandi)"

    print(f"sik etiketi gorunurlugu ({picked['template']}): "
          f"{gorunur}/{toplam} sik Normal durumda etiketli  | kanarya: {kanarya}")
    return out


def _etiket_gorunurlugu(pkg, slayt: str) -> tuple[int, int]:
    """(Normal durumda etiketli şık, toplam şık).

    K22: durum govdelerine INILEREK bakilir. `shapeLst` duzeyinde kalan bir
    olcu etiketi hic gormezdi -- etiket `state/shapeLst/textBox` icinde.
    """
    from storyline_mcp import authoring

    part = next((p for p, r in model.slide_index(pkg).items()
                 if r.basename == slayt), None)
    if part is None:
        return (0, 0)
    root = pkg.parse(part)
    _tag, intr = authoring._find_interaction(root)
    if intr is None:
        return (0, 0)
    by = {el.get("g"): el for el in root.iter() if el.get("g")}
    guids = [g for g in authoring._choice_shape_guids(intr) if g in by]
    gorunur = 0
    for g in guids:
        for st in by[g].iter("state"):
            if (st.get("name") or "").lower() != "normal":
                continue
            lst = st.find("shapeLst")
            if lst is not None and any(c.tag == "textBox" for c in lst):
                gorunur += 1
            break
    return (gorunur, len(guids))


def check_choice_admission() -> list[str]:
    """Şablon kabul testi İKİ YÖNLÜ çalışıyor mu? (yeni fit_choices)

    2026-08-17'de yeniden yazilan compose.fit_choices'i sinar. Yeni kod,
    dolayisiyla uzerinde HICBIR eski olcum yok: silinen surumun tabanlari
    (golden, deadband) silme oncesinde alindi ve bu govdeyi hic gormedi.

    IKI YONLU, cunku tek yonlu bir kabul testi hicbir sey ispatlamaz. "Hep
    evet" diyen bir kapi da gecer, "hep hayir" diyen bir kapi da -- ikincisi
    bu projede bir kez zaten oldu (0 bosluk = kanit degil). O yuzden:

        A) sigan vaka KABUL EDILMELI     -- kapi hep 'hayir' demiyor
        B) sigmayan vaka REDDEDILMELI    -- kapi hep 'evet' demiyor
        C) red GEREKCE tasimali          -- ve gerekcesi asilan tabani ADIYLA
                                            soylemeli, yoksa teshis yok

    (B) vakasi UYDURMA DEGIL: 497 birim, olculen sablon genisligi
    (0_duz_kopya soru sablonu), ve 1920 uzayinda uzun bir sik etiketi. Ayni
    kesitin eski sabitlerle %356, yeni sabitlerle %662 tastigi olculmustu.

    DORDUNCU IDDIA -- EKSEN. Ayni girdi 720 ve 1920'de AYNI sonucu verirse
    uzay carpani hic devreye girmiyor demektir; yeniden yazmanin tek gercek
    kazanci da tam olarak o carpanin dogru eksende uygulanmasiydi. Fark
    olmasini beklemek, ozelligin kosuyor olmasini kanitlar (K3: sifir/ayni
    supheli sayidir).
    """
    from storyline_mcp import compose

    failures: list[str] = []
    dar, genis = 497.0, 1613.0
    uzun = ("Musteri gerildiginde sesin tonu degisir ve cumleler kisalir, "
            "ayni sikayet farkli kelimelerle tekrar eder")
    kisa = ["Evet", "Hayir", "Bazen", "Bilmiyorum"]

    _s720 = shapes.Space(720.0, 540.0, 720.0, 540.0)
    _s1920 = shapes.Space(1920.0, 1080.0, 720.0, 540.0)
    sigan = compose.fit_choices(kisa, 60.0, genis, space=_s720)
    if not sigan["ok"]:
        failures.append(f"kabul testi sigan vakayi reddetti: {sigan['why']}")

    tasan = compose.fit_choices([uzun] * 4, 60.0, dar, space=_s1920)
    if tasan["ok"]:
        failures.append(
            f"kabul testi tasan vakayi KABUL ETTI: 4 x {len(uzun)} harf, "
            f"{dar:.0f} birim, %60 alan -> %{tasan['total']:.1f} dedi")
    else:
        gerekce = tasan["why"].lower()
        if "taban" not in gerekce:
            failures.append(f"red gerekcesi asilan tabani soylemiyor: "
                            f"{tasan['why'][:60]}")
        if tasan["size"] > EXPECTED_CHOICE_SIZE_FLOOR:
            failures.append(
                f"red {tasan['size']:.0f}pt'de verildi ama taban "
                f"{EXPECTED_CHOICE_SIZE_FLOOR:.0f}pt — kucultme tabana inmedi")

    # DORDUNCU IDDIA YENIDEN YAZILDI (2026-08-17 kare turundan sonra).
    #
    # Eskiden soyleydi: "ayni girdi iki uzayda FARKLI sonuc vermeli, yoksa
    # carpan devreye girmiyor demektir". O iddia YANLIS SORUYU soruyordu ve
    # duzeltmeden sonra hakli olarak patladi.
    #
    # Dogru olan tam tersi: AYNI FIZIKSEL yerlesim iki koordinat uzayinda
    # AYNI YUZDEYI vermeli. Yuzde uzaydan bagimsizdir; bagimli olan sey
    # puntodan tureyen mutlak yuksekliktir, ve donusum tam da onu duzeltir.
    # Genislik de uzaya cevrilerek verilir -- ayni kutu, iki izgara.
    dar_1920 = genis * _s1920.h                      # ayni kutu, 1920 izgarasi
    kucuk = compose.fit_choices(kisa, 60.0, genis, space=_s720)
    buyuk = compose.fit_choices(kisa, 60.0, dar_1920, space=_s1920)
    if abs(kucuk["box_h"] - buyuk["box_h"]) > 0.05:
        failures.append(
            f"ayni kutu iki izgarada farkli yuzde veriyor: "
            f"720 %{kucuk['box_h']:.2f} vs 1920 %{buyuk['box_h']:.2f} — "
            f"donusum yuzdeyi korumali")

    # BESINCI: karisik uzayda iki eksen AYRISMALI. 1920x1080 slayt 720x540
    # sahnede h=2.667 v=2.000 verir; ikisi esitse donusum tek eksenli
    # calisiyor demektir ve bu oturumdaki kusurun tam kaynagi odur.
    if _s1920.tutarli:
        failures.append(
            f"karisik uzayda h ve v esit ({_s1920.h:.3f}) — donusum tek "
            f"eksenli, oysa slayt 16:9 sahne 4:3")
    if "turetildi" not in buyuk["scale_source"]:
        failures.append(f"uzay kaynagi tasinmiyor: {buyuk['scale_source']}")

    print(f"\nsik kabul testi: sigan={sigan['ok']} ({sigan['size']:.0f}pt) "
          f"tasan={tasan['ok']} ({tasan['size']:.0f}pt, %{tasan['total']:.0f}) "
          f"kutu 720=%{kucuk['box_h']:.2f} 1920=%{buyuk['box_h']:.2f}")
    return failures


def _gonder_baglantisi(pkg, slayt: str) -> bool | None:
    """Bu slaytta CALISIR bir gonder baglantisi var mi?

    None  = slaytta etkilesim yok (sorulacak sey yok)
    False = etkilesim var ama gonder tetikleyicisi yok, YA DA `submitG`
            baska bir seyi gosteriyor
    True  = gonder tetikleyicisi var ve etkilesime cozuluyor

    IKI KUSUR DUZELTILDI (2026-09-05), ikisi de bu olcuyu KOR birakiyordu:

    1. "submitG yoksa None" idi -- yani "sorulacak sey yok". Ama gonder
       tetikleyicisi SILINDIGINDE geriye submitG kalmiyor, dolayisiyla olcu
       tam da kusurun gerceklestigi durumda sessiz kaliyordu. Olculdu: dokuz
       tohumun dokuzunda tetikleyici siliniyordu ve bu satir hicbir zaman
       bagirmadi. Kanarya ciktisi bile "kurulamadi (fikstuurde submitG yok)"
       diyordu -- olcu, olctugu seyin kayboldugunu kendi agziyla soyledi ve
       bu "kanarya kurulamadi" diye okundu.
       Artik: etkilesim VARSA gonder de OLMALI. Yoksa False.

    2. Slayttaki HER submitG'ye bakiyordu. Ama etkilesim ogesinin KENDISI de
       bir submitG tasiyor ve o SIFIR olabiliyor -- olculdu, tohumda:
       freeTextEntryIntr submitG="00000000-...". O yuzden metin girisi
       slaydi saglam oldugu halde False donerdi.
       Artik yalnizca GONDER TETIKLEYICILERININ icindeki submitG sayilir.

    Dogru bicim TAHMIN DEGIL, olculdu: elle yapilmis bir kursta 11 soru
    slaydinin 11'inde submitG o slaydin etkilesim guid'ine esit.
    """
    from storyline_mcp import authoring

    part = next((p for p, r in model.slide_index(pkg).items()
                 if r.basename == slayt), None)
    if part is None:
        return None
    root = pkg.parse(part)
    _tag, intr = authoring._find_interaction(root)
    if intr is None:
        return None
    hedef = intr.get("g")
    bulunan = []
    for trig in root.iter("trig"):
        data = trig.find("data")
        if data is None or data.get("action") != "submitInteraction":
            continue
        bulunan += [el.get("submitG") for el in trig.iter()
                    if el.get("submitG")]
    if not bulunan:
        return False
    return all(s == hedef for s in bulunan)


def _sik_sirasi(pkg, slayt: str) -> list[str] | None:
    """Şık etiketleri, slaytta ÜSTTEN ALTA sırayla. Okunamazsa None.

    Yazarin verdigi sirayla karsilastirilir. Dikkat: guid sirasi DEGIL,
    Y KOORDINATI sirasi -- ogrencinin gordugu sira budur. Ikisi ayrisirsa
    ayrisma tam olarak aranan kusurdur.
    """
    from storyline_mcp import authoring

    part = next((p for p, r in model.slide_index(pkg).items()
                 if r.basename == slayt), None)
    if part is None:
        return None
    root = pkg.parse(part)
    _tag, intr = authoring._find_interaction(root)
    if intr is None:
        return None
    by = {el.get("g"): el for el in root.iter() if el.get("g")}
    satirlar = []
    for g in authoring._choice_shape_guids(intr):
        if g not in by:
            continue
        rect = shapes.shape_rect(by[g])
        text = model.shape_text(root, g).strip()
        if rect and text:
            satirlar.append((rect[1], text))
    return [t for _y, t in sorted(satirlar)] or None


def check_question_frame() -> list[str]:
    """Üretimin GERÇEKTEN kullandığı soru dalı korunuyor mu?

    Bu kontrol bir kusuru degil, bir KAPSAM TERSLIGINI kapatiyor. Olculdu
    (2026-08-16, uretilmis kurs, dort soru):

        pick_template_for_question cagrisi   4
        compose_question_frame cagrisi       4     <- uretimin kullandigi dal
        apply_choice_plan cagrisi            0     <- sinanan dal

    Yani sigdirma sozlesmesi her soruda HESAPLANIP ATILIYOR: gomulu tohum
    yolunda cerceve kendi yerlesimini kuruyor ve plan diske hic yazilmiyor.
    check_fit_choices ve check_plan_applied o atilan dali sinardi; golden de
    oyle. Uretimin kullandigi dali sinayan HICBIR SEY YOKTU. (Ucu de o
    olcumun ardindan silindi; bu kontrol yerlerinde duran sey.)

    Bir cagri sayaci bunu GORMEZ ve "bagli" der: fonksiyon cagriliyor,
    yalnizca ciktisi kullanilmiyor. K8'in ince hali.

    Not: bugun bu dal DOGRU davraniyor -- zorlandi, en kotu vakada sik alt
    kenari %92.0'da durdu ve daha agirinda gerekcesiyle reddetti. Yani
    ciktiyi degil, KORUMAYI ekliyoruz. "Bagirmiyor, demek ki gereksiz" bu
    projede zaten bir kez yanlis cikti.
    """
    import shutil
    from storyline_mcp import authoring

    source = ROOT.parent / "test" / "bos.story"
    work = ROOT.parent / "test" / "_canary" / "soru_cerceve.story"
    if not source.is_file():
        return [f"soru cerceve kontrolu kosmadi: {source.name} yok — "
                "bu bir GECIS degil"]

    kok_uzun = ("Sirket agina bagliyken tanimadigin bir gonderenden gelen ve "
                "icinde acil oldugu belirtilen bir baglanti bulunan e-postayi "
                "aldin. Baglantiya tikladiginda kurumsal giris sayfasina "
                "benzeyen bir forma yonlendiriliyorsun. Ilk ne yapmalisin?")
    uzun = ["Sakin bir tonla dinlemeye devam eder, soyleneni kendi "
            "cumleleriyle ozetleyerek dogrular ve anlasildigini hissettirir",
            "Ayni sertlikte karsilik verip kim oldugunu hatirlatir, gerekirse "
            "gorusmeyi tek tarafli olarak sonlandiracagini bastan bildirir"]
    # ORTA UZUNLUK, ve VAKA MATRISININ DELIGI BURADAYDI (2026-08-17).
    #
    # Uc vaka vardi: kisa/kisa, kisa/uzun, uzun/uzun. Olculdu -- ucu de metin
    # tasmasi URETMIYOR: kisa etiket kutuya sigar, uzun etiket kutuyu
    # BUYUTUR (kutu 99 -> 290 birim), uzun/uzun ise gerekcesiyle reddedilir.
    # Yani matris "kok uzunlugu" ve "sik uzunlugu" eksenlerini geziyor ama
    # ikisinin KESISTIGI kritik hucreyi atliyordu.
    #
    # Kusur tam o hucrede: uzun kok cerceveyi yer (941 birim = slaydin %87'si),
    # siklara 65 birim kalir, ORTA boy etiket 139 birim ister. Kisa etiket o
    # 65'e sigar; uzun etiket kutuyu buyutup kendini kurtarir; ARADAKI boy ne
    # sigar ne buyutur. Uretimde gorulen vaka da tam bu boydaydi.
    #
    # Ders liste bicimindeki kapsamin kendisine ait: her ekseni tek tek
    # gezmek, eksenlerin kesisimini gezmez.
    orta = ["Sakin bir tonla dinlemeye devam eder ve soyleneni ozetleyerek "
            "dogrular",
            "Ayni sertlikte karsilik verip kim oldugunu hatirlatir"]
    vakalar = [
        ("kisa/kisa", "Ne yaparsin?", ["Sakin kal", "Sert cevap ver"]),
        ("kisa/uzun", "Ne yaparsin?", uzun),
        ("uzun/uzun", kok_uzun, uzun),
        ("uzun/orta", kok_uzun, orta),
    ]

    out: list[str] = []
    cerceve_dali = 0
    redler: list[tuple[str, str]] = []
    metin_olculen = metin_bantdisi = 0
    olculen: list[tuple[str, float]] = []
    # Butun vakalar reddedilirse asagidaki kanarya `made`'e dokunmamali;
    # bagli olmayan bir ad, kontrolu NameError ile dusurur ve dusen bir
    # kontrol "bozuk invaryant" gibi degil "arac kirildi" gibi okunur.
    made = None
    son_slayt = None
    kanarya_dosyasi = ROOT.parent / "test" / "_canary" / "soru_cerceve_k.story"
    metin_kanarya_dosyasi = ROOT.parent / "test" / "_canary" / "soru_cerceve_mk.story"

    def yerlesim(pkg, slayt):
        """(en alt sik %, kok ile cakisan sik sayisi)."""
        part = next(p for p, r in model.slide_index(pkg).items()
                    if r.basename == slayt)
        root = pkg.parse(part)
        _w, height = shapes.slide_size(root)
        _tag, intr = authoring._find_interaction(root)
        if intr is None:
            return None, None, None
        by = {el.get("g"): el for el in root.iter() if el.get("g")}
        guids = authoring._choice_shape_guids(intr)
        rects = [shapes.shape_rect(by[g]) for g in guids if g in by]
        rects = [r for r in rects if r]
        if not rects:
            return None, None, None
        kok_guid = model.stem_shape_guid(root, guids)
        kok = shapes.shape_rect(by[kok_guid]) if kok_guid in by else None
        cakisan = 0
        if kok:
            for r in rects:
                if kok[0] < r[2] and r[0] < kok[2] and kok[1] < r[3] and r[1] < kok[3]:
                    cakisan += 1
        return max(r[3] for r in rects) / height * 100, cakisan, len(rects)

    for ad, kok, siklar in vakalar:
        shutil.copy2(source, work)
        pkg = StoryPackage(work)
        try:
            picked = _quiet(authoring.pick_template_for_question, pkg, kok, siklar)
        except (authoring.StemStarvesFrame, authoring.NoTemplateFits) as exc:
            # Red gecerli bir cevap, ama GEREKCESIZ red degil.
            if not str(exc).strip():
                out.append(f"soru cerceve {ad}: gerekcesiz red")
            continue
        # DORDUNCU RED TURU: cerceve taban puntoda bile sigdiramiyor.
        # Gecerli bir cevap, ama GEREKCESIZ red degil -- ve red YERINE
        # sessiz yerlestirme hic degil. `uzun/orta` vakasi tam olarak
        # bunu uretiyor; bir donem yerlestiriliyordu ve metin tasiyordu.
        try:
            made = _quiet(authoring.add_question, pkg, picked["template"],
                          kok, siklar, [0], eyebrow="Bolum 1")
        except authoring.ChoiceLabelsTooLong as exc:
            gerekce = str(exc)
            if "taban" not in gerekce.lower() or "%" not in gerekce:
                out.append(f"soru cerceve {ad}: etiket reddi gerekcesiz — "
                           f"{gerekce[:60]}")
            redler.append((ad, gerekce))
            continue
        pkg.save(work, backup=False)
        if made.get("framed"):
            cerceve_dali += 1

        # Kanarya fikstuurunu HEMEN ayir: bir sonraki vaka reddedilirse
        # work uzerine bos proje kopyalanir ve kanarya kurulamaz hale
        # gelir -- olculdu, "kanarya: kurulamadi" diye cikti.
        shutil.copy2(work, kanarya_dosyasi)
        # METIN kanaryasinin fikstuuru de BURADA ayrilir, ayni sebeple ve ilk
        # yazilisinda ayni tuzaga dusuldu: son vaka reddedilirse `work`
        # uzerine bos proje kopyalanmis olur ve kanarya "kurulamadi" der.
        # Taban kanaryasinin dosyasi kullanilamaz -- onu taban kanaryasi
        # mutasyona ugratiyor ve iki kanarya birbirinin girdisini bozar.
        shutil.copy2(work, metin_kanarya_dosyasi)
        son_slayt = made["new_slide"]
        alt, cakisan, sayi = yerlesim(StoryPackage(work), made["new_slide"])
        if alt is None:
            out.append(f"soru cerceve {ad}: sik dikdortgenleri okunamadi")
            continue
        olculen.append((ad, alt))

        # METIN SIGIYOR MU -- KAPSAM BOSLUGU BURADAYDI (2026-08-17).
        # Yukaridaki `yerlesim` kutunun ALT KENARINI oluyor; kutunun ICINE
        # metnin sigdigini olcen hicbir sey yoktu. Ikisi ayni sey degil:
        # olculdu, alt kenar tam %92.0'da (taban) duran bir sik kutusu 97
        # birim yuksekti ve etiketi 139 birim istiyordu. Geometri yesil,
        # metin tasiyor.
        #
        # Olcu burada TEKRAR YAZILMIYOR, tasan_yazilar'dan geliyor (K12) --
        # ve o hem temel katmani hem geri bildirim katmanlarini tarar.
        part = next(p for p, r in model.slide_index(StoryPackage(work)).items()
                    if r.basename == made["new_slide"])
        _p = StoryPackage(work)
        tasma, olcu, bant = tasan_yazilar(_p.parse(part), made["new_slide"],
                                          shapes.stage_size(_p))
        metin_olculen += olcu
        metin_bantdisi += bant
        for t in tasma:
            out.append(f"soru cerceve {ad}: metin kutusunu asiyor "
                       f"(kirpilmaz, komsusuna biner) — {t}")

        # YAZARIN SIRASI EKRANDA KORUNUYOR MU (2026-08-17).
        #
        # Bunu olcen hicbir sey yoktu: `yerlesim` dikdortgenlerin nerede
        # oldugunu sayiyor, hangi ETIKETIN nerede oldugunu degil. Kusur
        # ancak iki kare gozle karsilastirilinca gorundu.
        #
        # Kusur: `choice_ids = set(...)` sirayi atiyordu ve cerceveye
        # `list(set)` gidiyordu -- yani PYTHONHASHSEED'e bagli, SUREC BASINA
        # degisen bir sira. Olculdu: ayni girdi bes kosu, ucunde dogru cevap
        # ustte ikisinde altta. Puanlama tutarli kaldigi icin hicbir yapisal
        # kontrol bagirmadi, ama sira ICERIGIN PARCASI.
        #
        # BU KONTROLUN SINIRI, ve bilerek yaziliyor: kararsiz bir sirayi
        # HER KOSUDA yakalamaz -- iki sikta rastgele sira zaten yarisinda
        # dogru cikar. Sabit-ama-yanlis sirayi her zaman yakalar, kararsizi
        # olasilikla. Kararsizligi kesin yakalamak icin surec DISINDA tekrar
        # gerekir (PYTHONHASHSEED surec basina sabit), ki o ayri bir kosu.
        # GONDER BAGLANTISI COZULUYOR MU (2026-08-17).
        #
        # Bunu olcen hicbir sey yoktu. `dangling_triggers` sayiyor ama
        # KUSURA OZGU DEGIL: elle yapilmis bir kursta 37 "kopuk" var ve
        # editorde SIFIR uyari; bizim urettigimizde 30 var ve gonder
        # dugmesi calismiyor. Sayinin buyuklugu oncelik gostergesi degil.
        gonder = _quiet(_gonder_baglantisi, StoryPackage(work),
                        made["new_slide"])
        if gonder is not None and not gonder:
            out.append(f"soru cerceve {ad}: gonder baglantisi yok ya da "
                       f"etkilesime cozulmuyor — Submit tusu hicbir sey "
                       f"yapmaz, ogrenci cevabi degerlendirilmez")

        sirali = _quiet(_sik_sirasi, StoryPackage(work), made["new_slide"])
        if sirali is None:
            out.append(f"soru cerceve {ad}: sik sirasi okunamadi")
        elif sirali != siklar:
            out.append(
                f"soru cerceve {ad}: yazarin sirasi ekranda korunmuyor — "
                f"verilen {[s[:18] for s in siklar]}, "
                f"ustten alta {[s[:18] for s in sirali]}")

        if sayi != len(siklar):
            out.append(f"soru cerceve {ad}: {len(siklar)} sik verildi, "
                       f"{sayi} yerlestirildi")
        if alt > EXPECTED_FLOOR + 0.5:
            out.append(f"soru cerceve {ad}: en alt sik %{alt:.1f}, "
                       f"beklenen taban %{EXPECTED_FLOOR:.0f} — "
                       "slaydin altina sarkiyor")
        if cakisan:
            out.append(f"soru cerceve {ad}: {cakisan} sik kokle ust uste")

    # DAL DENETIMI. Uretim bir gun plan dalina gecerse bu kontrol sessizce
    # gecmeye baslar -- vakalari cerceve dali icin yazilmis olur ve baska bir
    # dali "korudugunu" sanir. Sessizce gecen bir invaryant, olmayandan kotu.
    if cerceve_dali == 0 and olculen:
        out.append("soru cerceve: hicbir vaka cerceve dalindan gecmedi — "
                   "uretim yolu degismis olabilir, bu kontrolun vakalari "
                   "artik yanlis dali sinyor")

    # KANARYA: olcunun kendisi bozuk girdide bagiriyor mu? Son vakanin bir
    # sikki kasten tabanin altina indirilir. Bagirmazsa yukaridaki butun
    # "yok"lar hicbir sey soylemez.
    kanarya = "kurulamadi"
    if son_slayt and kanarya_dosyasi.is_file():
        pkg = StoryPackage(kanarya_dosyasi)
        part = next((p for p, r in model.slide_index(pkg).items()
                     if r.basename == son_slayt), None)
        if part:
            root = pkg.parse(part)
            _w, height = shapes.slide_size(root)
            _tag, intr = authoring._find_interaction(root)
            by = {el.get("g"): el for el in root.iter() if el.get("g")}
            hedef = next((by[g] for g in authoring._choice_shape_guids(intr)
                          if g in by), None)
            if hedef is not None:
                r = shapes.shape_rect(hedef)
                shapes.set_loc(hedef, r[0], height * 0.95, r[2], height * 1.05)
                pkg.replace_xml(part, root)
                pkg.save(kanarya_dosyasi, backup=False)
                alt, _c, _n = yerlesim(StoryPackage(kanarya_dosyasi),
                                       son_slayt)
                if alt is None or alt <= EXPECTED_FLOOR + 0.5:
                    kanarya = "OLDU"
                    out.append("soru cerceve KANARYASI olmedi: taban altina "
                               "indirilen sik yakalanmadi — bu kontrol atil")
                else:
                    kanarya = f"yasiyor (ekilen sik %{alt:.0f}'da yakalandi)"

    # IKINCI KANARYA: METIN olcusu icin, AYRI. Taban kanaryasi kutuyu asagi
    # ITER; metin kanaryasi kutuyu KISALTIR. Ayni kanaryaya iki iddia
    # yuklemek, birinin olmesini digerinin arkasina saklar -- ve "kanarya
    # yasiyor" satiri o zaman hangi iddianin yasadigini soylemez.
    #
    # Kutu 1/5'e indirilir ve METIN AYNI KALIR: yani sigmamasi girdinin
    # TANIMI, modelin tahmini degil.
    metin_kanaryasi = "kurulamadi"
    mk_dosya = metin_kanarya_dosyasi
    if son_slayt and mk_dosya.is_file():
        pkg = StoryPackage(mk_dosya)
        part = next((p for p, r in model.slide_index(pkg).items()
                     if r.basename == son_slayt), None)
        if part:
            root = pkg.parse(part)
            _tag, intr = authoring._find_interaction(root)
            by = {el.get("g"): el for el in root.iter() if el.get("g")}
            hedef = next((by[g] for g in authoring._choice_shape_guids(intr)
                          if g in by), None)
            if hedef is not None:
                r = shapes.shape_rect(hedef)
                shapes.set_loc(hedef, r[0], r[1], r[2],
                               r[1] + (r[3] - r[1]) / 5)
                pkg.replace_xml(part, root)
                pkg.save(mk_dosya, backup=False)
                yeni = StoryPackage(mk_dosya)
                p2 = next(p for p, rr in model.slide_index(yeni).items()
                          if rr.basename == son_slayt)
                bulunan, _o, _b = tasan_yazilar(yeni.parse(p2), son_slayt,
                                                shapes.stage_size(yeni))
                # SAYIYA degil, KISALTILAN KUTUYA bakilir. "Liste bos degil"
                # yetmez: bu slaytta ZATEN tasan bir yazi olabilir (bugun var)
                # ve o zaman kanarya, olcu hic kosmasa bile yasamis gorunur --
                # kanaryanin kendi kanaryasi. Aranan sey, raporlanan kutu
                # yuksekligi KISALTILMIS olcuye esit olan bir satir.
                hedef_h = round((r[3] - r[1]) / 5)
                kirpik = [t for t in bulunan
                          if t.rsplit(">", 1)[-1].strip().isdigit()
                          and abs(int(t.rsplit(">", 1)[-1]) - hedef_h) <= 1]
                if not kirpik:
                    metin_kanaryasi = "OLDU"
                    out.append("soru cerceve METIN KANARYASI olmedi: 1/5'e "
                               "indirilen kutu yakalanmadi — metin olcusu atil")
                else:
                    metin_kanaryasi = f"yasiyor ({kirpik[0].split(' ', 1)[1][:38]})"

    # UCUNCU KANARYA: SIRA olcusu icin, yine AYRI.
    #
    # Iki sikkin dikdortgenleri KASTEN takas edilir; etiketler yerinde
    # kalir. Yani slaytta gecerli bir yerlesim var, geometri taban icinde,
    # yalnizca yazarin sirasi bozulmus -- kusurun tam olarak gorundugu hal.
    # Olcu bagirmazsa yukaridaki "korunuyor" satiri hicbir sey soylemez.
    sira_kanaryasi = "kurulamadi"
    sk_dosya = ROOT.parent / "test" / "_canary" / "soru_cerceve_sk.story"
    if son_slayt and metin_kanarya_dosyasi.is_file():
        shutil.copy2(metin_kanarya_dosyasi, sk_dosya)
        pkg = StoryPackage(sk_dosya)
        part = next((p for p, r in model.slide_index(pkg).items()
                     if r.basename == son_slayt), None)
        onceki = _quiet(_sik_sirasi, StoryPackage(sk_dosya), son_slayt)
        if part and onceki and len(onceki) > 1:
            root = pkg.parse(part)
            _tag, intr = authoring._find_interaction(root)
            by = {el.get("g"): el for el in root.iter() if el.get("g")}
            gu = [g for g in authoring._choice_shape_guids(intr) if g in by]
            if len(gu) > 1:
                r0 = shapes.shape_rect(by[gu[0]])
                r1 = shapes.shape_rect(by[gu[1]])
                shapes.set_loc(by[gu[0]], *r1)
                shapes.set_loc(by[gu[1]], *r0)
                pkg.replace_xml(part, root)
                pkg.save(sk_dosya, backup=False)
                sonraki = _quiet(_sik_sirasi, StoryPackage(sk_dosya), son_slayt)
                if sonraki == onceki:
                    sira_kanaryasi = "OLDU"
                    out.append("soru cerceve SIRA KANARYASI olmedi: takas "
                               "edilen iki sik ayni sirada okundu — sira "
                               "olcusu atil")
                else:
                    sira_kanaryasi = f"yasiyor ({onceki[0][:14]!r} -> "
                    sira_kanaryasi += f"{sonraki[0][:14]!r})"

    # DORDUNCU KANARYA: GONDER BAGLANTISI. Bir slaydin submitG'si kasten
    # baska bir guid'e cevrilir; olcu bagirmazsa "cozuluyor" satiri hicbir
    # sey soylemez. Fikstuurde submitG yoksa kanarya KURULAMAZ der --
    # "kuruldu ve gecti" ile karistirilmasin.
    gonder_kanaryasi = "kurulamadi (fikstuurde submitG yok)"
    gk_dosya = ROOT.parent / "test" / "_canary" / "soru_cerceve_gk.story"
    if son_slayt and metin_kanarya_dosyasi.is_file():
        shutil.copy2(metin_kanarya_dosyasi, gk_dosya)
        pkg = StoryPackage(gk_dosya)
        part = next((p for p, r in model.slide_index(pkg).items()
                     if r.basename == son_slayt), None)
        if part:
            root = pkg.parse(part)
            hedefler = [el for el in root.iter() if el.get("submitG")]
            if hedefler:
                for el in hedefler:
                    el.set("submitG", "deadbeef-0000-0000-0000-000000000001")
                pkg.replace_xml(part, root)
                pkg.save(gk_dosya, backup=False)
                sonuc = _quiet(_gonder_baglantisi, StoryPackage(gk_dosya),
                               son_slayt)
                if sonuc is not False:
                    gonder_kanaryasi = "OLDU"
                    out.append("soru cerceve GONDER KANARYASI olmedi: "
                               "bozulan submitG yakalanmadi — olcu atil")
                else:
                    gonder_kanaryasi = f"yasiyor ({len(hedefler)} submitG bozuldu)"

    # PROJE SABLONU DALI, ayri fikstuurde ve bilerek boyle.
    #
    # Yukaridaki dort vaka GOMULU TOHUM'dan uretiliyor ve o tohumda
    # `submitG` HIC YOK -- yani gonder kontrolu orada kurulamiyor ("None
    # doner, kontrol atlar"). Kusur ise PROJE SABLONU yolunda: tohumun
    # icerik slaytlari ölü bir Submit Button tetikleyicisi tasiyor ve
    # klonlandikca cogaliyordu (5 -> 17).
    #
    # KAYNAK DEGISTIRILMEDI, VAKA EKLENDI. Mevcut fikstuuru proje
    # sablonuna cevirmek taban/metin/sira kanaryalarinin ucunun birden
    # zeminini oynatirdi ve biri sessizce olse fark edilmezdi -- guard'in
    # kendi kapsaminin daralmasi sinifi (golden'in sabit alan listesi,
    # <trig> etiket kumesi). Ekleme, degistirmeden daha az yuzey acar.
    proje = ROOT.parent / "test" / "0_duz_kopya.story"
    pk_dosya = ROOT.parent / "test" / "_canary" / "soru_proje.story"
    if proje.is_file():
        shutil.copy2(proje, pk_dosya)
        try:
            pkg = StoryPackage(pk_dosya)
            picked = _quiet(authoring.pick_template_for_question, pkg,
                            "Ne yaparsin?", ["Sakin kal", "Sert cevap ver"])
            yapildi = _quiet(authoring.add_question, pkg, picked["template"],
                             "Ne yaparsin?", ["Sakin kal", "Sert cevap ver"],
                             [0], eyebrow="Bolum 1")
            pkg.save(pk_dosya, backup=False)
            slayt = yapildi["new_slide"]
            bagli = _quiet(_gonder_baglantisi, StoryPackage(pk_dosya), slayt)
            if bagli is None:
                gonder_kanaryasi = ("kurulamadi (proje sablonu da submitG "
                                    "tasimiyor)")
            elif not bagli:
                out.append(
                    "soru cerceve proje/gonder: submitG etkilesime "
                    "cozulmuyor — editorde 'Submit unassigned', ogrenci "
                    "cevabi degerlendirilmez")
                gonder_kanaryasi = "olcu BAGIRDI (kusur var)"
            else:
                # KANARYA: kasten boz, bagirmali.
                p2 = StoryPackage(pk_dosya)
                part = next(p for p, r in model.slide_index(p2).items()
                            if r.basename == slayt)
                kok = p2.parse(part)
                bozulan = 0
                for el in kok.iter():
                    if el.get("submitG"):
                        el.set("submitG",
                               "deadbeef-0000-0000-0000-000000000001")
                        bozulan += 1
                p2.replace_xml(part, kok)
                p2.save(pk_dosya, backup=False)
                if _quiet(_gonder_baglantisi, StoryPackage(pk_dosya),
                          slayt) is not False:
                    gonder_kanaryasi = "OLDU"
                    out.append("soru cerceve GONDER KANARYASI olmedi: "
                               "bozulan submitG yakalanmadi — olcu atil")
                else:
                    gonder_kanaryasi = (f"yasiyor (proje sablonu, "
                                        f"{bozulan} submitG bozuldu)")
        except Exception as exc:
            gonder_kanaryasi = f"kurulamadi ({type(exc).__name__})"

    print(f"  gonder baglantisi kanaryasi: {gonder_kanaryasi}")

    # Kanaryanin BASARISI da basilir. Yalnizca basarisizligini basmak, olcunun
    # kosup kosmadigini goruunmez birakir -- ve bu projede "sessizce gecen
    # kontrol" tam olarak bu bicimde uc kez ortaya cikti.
    print(f"soru cercevesi ({len(vakalar)} durum, {cerceve_dali} cerceve dali): "
          f"{'saglam' if not out else 'BOZUK'}"
          + (f"  en alt sik %{max(a for _n, a in olculen):.1f}" if olculen else "")
          + f"  | kanarya: {kanarya}")
    print(f"  sik sirasi kanaryasi: {sira_kanaryasi}")
    print(f"  soru slaytinda metin ({metin_olculen} yazi olculdu, "
          f"{metin_bantdisi} bant disi atlandi, temel+katman)"
          f"  | metin kanaryasi: {metin_kanaryasi}")
    # REDLER DE BASILIR. Sessizce atlanan bir vaka, kosmus gibi gorunur ve
    # "4 durum" satiri yalan soyler. Hangi vakanin neden dustugu okunabilsin.
    for ad, gerekce in redler:
        print(f"    red {ad}: {gerekce[:88]}")
    return out


def check_choice_count() -> list[str]:
    """Şık sayısı uyuşmazlığı hâlâ bağırıyor mu -- iki yönde de.

    Aşağı yön (şablondan az şık) yukarıdan sinsi: fazla şık verince bir şey
    taşar ve görünür, az verince kalan şekiller yerinde kalıp boş durur.
    Ölçüt "yerleştirilebildi mi" değil, "sessiz kaldı mı".
    """
    from storyline_mcp import authoring
    from storyline_mcp.package import StoryPackage, StoryError

    source = ROOT.parent / "test" / "0_duz_kopya.story"
    if not source.is_file():
        return ["sik sayisi kontrolu icin kaynak proje yok"]

    pkg = StoryPackage(source)
    usable = [e for e in _quiet(authoring.available_question_shapes, pkg)
              if e["source"] == "project"]
    if not usable:
        return ["provadan gecen soru sablonu yok"]

    template, expected = usable[0]["slide"], usable[0]["choices"]
    out = []
    for count, direction in ((max(expected - 2, 1), "az"), (expected + 2, "cok")):
        if count == expected:
            continue
        probe = StoryPackage(source)
        try:
            _quiet(authoring.add_question, probe, template, "Prova",
                   [f"S{i}" for i in range(count)], [0])
        except StoryError:
            continue                       # bagirdi: dogru davranis
        out.append(
            f"{expected} sikli sablona {count} sik ({direction}) sessizce kabul "
            "edildi — kullanilmayan sekiller ve tetikleyicileri kaliyor olabilir")
    print(f"sik sayisi uyusmazligi ({expected} sikli sablon): "
          f"{'bagiriyor' if not out else 'SESSIZ'}")
    return out


# --------------------------------------------------------- bilinen kiriklar
#
# NEDEN BIR TABAN. Bu kapi uc turdur KIRMIZI ve uc kirigin ucu de bilerek acik
# birakilmis sinyal. Ama kalici kirmizi bir kapi, kapi degildir: dorduncu bir
# invaryant kirilsa cikti "4 INVARYANT BOZULDU" derdi ve suit yine "1 KAPI
# KALDI" derdi -- yeni bilgi eskisinin arasina saklanirdi. K26'nin kuzeni:
# kontrol kosuyor ama sonucu yeni ile eskiyi ayirt etmiyor.
#
# TABAN BOOLE DEGIL, DEGER TUTAR. "Hala kirik mi" diye sorsaydi, ayni
# invaryant kirik kalirken DEGERI suruklenebilirdi (havuz 2'den 1'e duser,
# tasma 57>54'ten 57>90'a buyur) ve kapi yine sessiz kalirdi. Bu projede tam
# olarak bu yasandi: eski taban "40 harfte havuz 8" diyordu, o sayi hicbir
# yapilandirmada uretilemiyordu ve uzerine guard kurulmustu.
#
# GEREKCE TABANIN YANINDA DURUR. Yoksa bir sonraki kisi -- ya da birkac tur
# sonra ayni kisi -- "bunlar neden acik" sorusunu dosyaya yeniden sormak
# zorunda kalir. Bu tur tam olarak o yeniden dogrulamayla gecti.
#
# KAPI UC DURUMDA BAGIRIR:
#   * yeni imza          -> yeni bir invaryant kirildi
#   * kaybolan imza      -> kirik duzelmis, TABAN ESKIMIS (tek yonlu susturma
#                           olmasin diye; kazanim kaydedilmezse korunmaz, K7)
#   * ayni imza, farkli deger/adet -> deger surukleniyor

BILINEN_KIRIKLAR = {
    "N harf: havuz N adaya dustu (taban N)": {
        "ornekler": [[40.0, 2.0, 6.0]],
        "gerekce":
            "40 harflik etiket bandinda donor cesitliligi GERCEKTEN yok: "
            "genislik modelinden gecen 2 aday kaliyor, taban 6. Susturmak "
            "sinyali gizlerdi. Eski taban 8 yaziyordu ama o sayi hicbir "
            "zeminde uretilemiyordu -- kovalanmadi, dondurulup yeniden "
            "olculdu (bkz. POOL_MEASURED yorumu).",
    },
    "metin kutusunu asiyor (kirpilmaz, komsusuna biner): "
    "slidee.xml/katmanN Npt '...' N > N": {
        "ornekler": [[1.0, 16.0, 57.0, 54.0], [2.0, 16.0, 114.0, 98.0]],
        "gerekce":
            "slidee'nin iki katmani OKSUZ: 2026-08-26'da dosyaya soruldu -- "
            "variety.story'de 4 gercek katman-acma tetikleyicisi var "
            "(slide6, slideb) ve slidee'nin bu iki katmanina isaret eden "
            "SIFIR. Ogrenci onlari hic acmiyor. Ayrica 'tasma' burada veri "
            "kaybi degil: olculdu ki Storyline KIRPMIYOR, metin komsusunun "
            "uzerine biniyor -- duzen sorunu, dogruluk sorunu degil.",
    },
}


def _imza(mesaj: str) -> str:
    """Kirigi sayilarindan ve alintilarindan arindirilmis kimligi."""
    s = re.sub(r"'[^']*'", "'...'", mesaj)
    return re.sub(r"\d+(?:\.\d+)?", "N", s).strip()


def _sayilar(mesaj: str) -> list[float]:
    return [float(x) for x in re.findall(r"\d+(?:\.\d+)?", mesaj)]


def taban_karsilastir(failures: list[str]) -> list[str]:
    """Kiriklari tabanla karsilastir; SAPMALARI dondur."""
    gelen: dict[str, list[list[float]]] = {}
    for f in failures:
        gelen.setdefault(_imza(f), []).append(_sayilar(f))

    sapma = []
    for imza, kayit in BILINEN_KIRIKLAR.items():
        if imza not in gelen:
            sapma.append(
                f"TABAN ESKIMIS -- bu kirik artik yok, tabandan cikarilmali: "
                f"{imza}")
            continue
        a = sorted(kayit["ornekler"])
        b = sorted(gelen.pop(imza))
        if len(a) != len(b):
            sapma.append(f"ADET DEGISTI ({len(a)} -> {len(b)}): {imza}")
        elif a != b:
            sapma.append(f"DEGER SURUKLENDI {a} -> {b}: {imza}")
    for imza, ornekler in gelen.items():
        for o in ornekler:
            sapma.append(f"YENI KIRIK {o}: {imza}")
    return sapma


def main() -> int:
    failures = check()
    print()
    sapma = taban_karsilastir(failures)

    if failures:
        print(f"{len(failures)} invaryant kirik (tabanda kayitli olanlar):")
        for f in failures:
            print(f"  . {f}")
        print()
        print("Gerekceler:")
        for imza, kayit in BILINEN_KIRIKLAR.items():
            print(f"  - {imza}")
            for satir in textwrap.wrap(kayit["gerekce"], 74):
                print(f"      {satir}")

    if sapma:
        print()
        print(f"{len(sapma)} SAPMA -- taban ile bugunku olcum ayrisiyor:")
        for x in sapma:
            print(f"  ! {x}")
        return 1

    if failures:
        print()
        print("Taban tutuyor: kirik kumesi ve olculen degerler AYNI. "
              "Yeni bir kirik, kaybolan bir kirik ya da kayan bir deger "
              "burada bagirirdi.")
        return 0
    print("Butun invaryantlar saglam.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
