"""Composed slides: one call lays out a whole page.

The primitives -- a rectangle, a text box, a button -- can build anything and
suggest nothing. Asked for a slide, a caller has to invent a margin, a type
size, a gap under the title and a place for the buttons, and inventing those
per call is what makes output look improvised.

So the design decisions live here. Two of them are structural, and they are
what separate a deck that looks composed from one that looks generated:

*Each layout has its own skeleton.* A cover is not a content slide with larger
type. When every slide repeats one accent rail, one rule and one downward
stack, the deck reads as a template applied six times -- correct, and dull. A
cover anchors low against a corner block; a section divider centres on its
index; content splits into columns; bullets become cards. The structure itself
tells the reader where they are.

*Content is distributed, not stacked.* Measuring the blocks first and then
placing them lets a layout fill its frame -- spreading the gaps, centring the
group, or anchoring it to the floor. Stacking downward from a fixed start
leaves the same dead band at the bottom of every slide.

Everything derives from the slide's own size, so a layout holds on a 720x540
project and a 1920x1080 one alike.
"""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from . import model, preview as _preview, shapes
from .authoring import ChoiceLabelsTooLong, _apply_text, _ovali_kapsullestir
from .edits import set_shape_text
from .package import StoryPackage, StoryError

# Type scale in points against the 720-unit design width, the basis Storyline
# uses. Ratios rather than round numbers: each step is about 1.25x the last,
# so a heading and its body never read as the same voice.
TYPE_SCALE = {
    "eyebrow": 11,
    "caption": 13,
    "body": 17,
    "lead": 21,
    "subtitle": 26,
    "title": 38,
    "display": 54,
    "numeral": 72,
}

# ---------------------------------------------------------------- punto merdiveni
#
# TYPE_SCALE sekiz basamak tanimliyor ama URETILMIS bir kursta on alti farkli
# punto olculdu: 11, 13, 14, 15, 16, 17, 18, 20, 21, 23, 29, 33, 37, 38, 42, 48.
# Sebep tek bir hata degil, ALTI BAGIMSIZ YOL: her biri kendi puntosunu
# uyduruyordu --
#
#   density_scale       olcegi 0.05'lik adimlarla surekli buyutuyor
#   _Page.size_of       taban x olcek, kesirli
#   _Page.text          sigmayinca x0.88, yuvarlanmis
#   fit_choices         -1
#   add_button          -1
#   compose_question_frame  -1
#
# Her yol kendi icinde dogru, birlikte olcek yok. Ve olcek yoksa hiyerarsi de
# yok: 20pt ile 21pt bir okuyucu icin ayni ses, ama iki ayri karar.
#
# Merdiven tek yer. Sigdirma "bir eksilt" degil "bir basamak in" olur; boylece
# kucultme bile olcegin icinde kalir.
TYPE_LADDER = tuple(sorted(set(TYPE_SCALE.values())))


def snap(size: float) -> float:
    """En yakın merdiven basamağı."""
    return min(TYPE_LADDER, key=lambda step: (abs(step - size), step))


def step_down(size: float, floor: float) -> float:
    """Bir basamak aşağı; tabanın altına inmez.

    Doner deger degismezse cagiran donguyu sonlandirmali -- taban asildi
    demektir.
    """
    below = [s for s in TYPE_LADDER if s < size and s >= floor]
    return max(below) if below else max(floor, min(TYPE_LADDER))


UNIT = 0.028            # one spacing unit, as a fraction of slide height
MARGIN_X = 8.0          # percent
CONTENT_W = 100 - MARGIN_X * 2
FLOOR = 92.0            # nothing is placed below this
CEILING = 8.0

DEFAULT_PALETTE = {
    "bg": "#0E1B3D",
    "deep": "#060C1E",
    "surface": "#16265A",
    "accent": "#FFC72C",
    # Vurgunun YAZI hali. Ayri bir renk, cunku bir vurgu iyi bir DOLGU olup
    # kotu bir YAZI olabilir: olculdu, #B4472B lacivert zemin uzerinde dolgu
    # olarak sorunsuz, ust etiket yazisi olarak 3.12 -- esigin altinda.
    # Verilmezse accent'in kendisi kullanilir (varsayilanda ikisi ayni).
    "accent_text": "#FFC72C",
    "text": "#FFFFFF",
    "muted": "#B9C4DE",
    "on_accent": "#0E1B3D",
}
_THEMES: dict[str, dict] | None = None

# --------------------------------------------- etkilesim blogunu alana sigdirma
#
# Kucultmenin iki kademesi var ve ikisinin de tabani olmali. Boslugu kismak
# okunabilirligi puntoyu kismaktan daha az bozar, o yuzden once o gider -- ama
# sifira kadar degil: sifir bosluklu bir sik listesi teknik olarak sigar,
# tiklanabilir hedefler birbirine yapisir ve hicbir yapisal kontrol bagirmaz.
# Denetimsiz kalan kademe, denetlenmeyen kademedir.
#
# IKI TABANIN ZEMINI AYRI, ve 2026-08-17'de ayri ayri kaydedildi (K14).
# Ikisi de silinen fit_choices'ten devralindi; devralmak dogrulamak degil.
#
# MIN_CHOICE_GAP = 1.6  ZEMINI DOGRULANMADI. Nereden geldigi bilinmiyor:
#   ne bir tiklama hedefi olcumune, ne bir goz turuna, ne bir kaynaga bagli.
#   "Sifir olmasin" gerekcesi bir TABAN OLMASINI gerektirir, 1.6 OLMASINI
#   degil. GROWTH_LIMIT=2.4 ile ayni sinif: uzerine bir sey insa edilmis
#   ama kendisi olculmemis. Olculene kadar boyle isaretli durur.
#
# MIN_CHOICE_SIZE  ARTIK KOPYA DEGIL, BAGLI. Bir donem `13.0` yazili bir
#   sabitti ve yanindaki yorum "shapes.CALIBRATED_RANGE alt ucu" diyordu --
#   yani bagli oldugunu SOYLUYOR ama bagli DEGILDI. Kalibre band genisletilse
#   taban yerinde kalir, kimse fark etmezdi. Bu, invariants'ta olculen
#   "esik kendi olctugu sabiti okuyor" hatasinin AYNASI: orada bagimsiz
#   olmasi gereken sey bagliydi, burada bagli olmasi gereken sey bagimsizdi.
#   Deger bugun degismiyor (13.0 == CALIBRATED_RANGE[0]); degisen, yarin
#   sessizce ayrisamayacak olmasi.
MIN_CHOICE_GAP = 1.6      # slayt yuksekliginin yuzdesi; ZEMINI DOGRULANMADI
MIN_CHOICE_SIZE = shapes.CALIBRATED_RANGE[0]   # punto; olculmus bandin alt ucu

# Bir kartin karti olarak okunmasi icin gereken en az yukseklik ve aralarindaki
# bosluk. Tabani olmayan kademe denetlenmeyen kademedir: kart bandi artan
# alandan hesaplandiginda kartlar okunamaz seritlere iniyordu.
#
# 9.0 SECILMISTI, OLCULMEMISTI -- ve yanlisti. Olculdu: _cards etiketi kartin
# %70'ine koyuyor, ve tek satirlik bir etiket kalibre bandin ALT ucunde (13pt)
# %7.54 istiyor, yani kart en az %10.78 olmali. Taban %9'da birakildiginda
# etiket 13pt'nin altina kuculuyordu -- olculmemis bir bolgeye.
#
# Sayi artik gerekcesini tasiyor: bir kart, etiketini kalibre edilmis en kucuk
# puntoda tasiyabilecek kadar yuksek. Bunun altinda kart degil, serittir.
MIN_CARD_H = 10.8         # slayt yuksekliginin yuzdesi; 13pt tek satir / 0.7

# METIN SIGDI SAYILMASI ICIN izin verilen tasma, slayt yuksekliginin yuzdesi.
#
# Yazan ile OLCEN ayni toleransi kullanmali. Kullanmiyorlardi: _Page.text
# "room + 0.4" ile sigmis sayiyordu (%0.4 = 1080'lik bir slaytta ~4 birim),
# invaryant ise "+ 1.0 BIRIM" ile olcuyordu. Dort kat fark, ve uretilmis bir
# kursta bir blok tam aralarina dustu -- yazan "sigdi" dedi, olcen "tasti"
# dedi, ikisi de kendi icinde tutarliydi.
#
# Iki tolerans, iki birim, tek kaynak: burasi. Deger kucultuldu cunku %0.4
# 21pt'de bir satirin besde biri kadar; goz onu tasma olarak gorur.
FIT_TOLERANCE = 0.1       # slayt yuksekliginin yuzdesi
CARD_GAP = 2.2            # SECILMIS, olculmemis -- kartlar arasi nefes payi

# Icerik yogunluguna gore punto olcegi (bkz. density_scale). Ayrim kategorik
# degil sureklilik: "maddesiz slaytlari duzelt" diye kurulmadi, az icerikli
# her slayt olcusunu buyutur.
MAX_TYPE_SCALE = 1.7
# Satir uzunlugu tabani. Belge tipografisinin 45-75 karakter kurali BURAYA
# AIT DEGIL: olculdu, alti varyant taban puntoda 25.9 ile 49.4 karakter
# arasinda calisiyor ve tasarim boyle kabul edilmis durumda. 40 yazildiginda
# alti varyantin dordu daha basta kilitlendi ve olcek hic devreye girmedi.
# 22, halihazirda gonderilen en dar olcunun (25.9) biraz altinda: olcegin
# hareket alani var ama iki kelimelik satira inemez.
MIN_LINE_CHARS = 22.0
TARGET_FILL = 0.62        # bandin tamamini doldurmak sikisik gorunur
# Olcegi akan metin rolleri tasir. Bir sayi ya da ust etiket zaten kisadir;
# satir uzunlugu tabani onlar icin anlamsizdir ve olcegi gereksiz kisitlar.
FLOWING = ("body", "lead", "subtitle")
#
# Buyume ile kucultme ayni blokta karsi karsiya gelir: uzun bir sik etiketi
# kutuyu buyuturken alan darligi onu kucultmeye calisir. Sira sabittir ve
# oncelik buyumenindir --
#
#   1. Her sik, kendi etiketini tasiyacak kadar buyur. Tasma yasak.
#   2. Blok alana sigmiyorsa once bosluk, sonra punto kisilir.
#   3. Kucultme (2) adimini gecersiz kilamaz: yeni puntoda etiket yine
#      sigmiyorsa cevap "daha da kis" degil, sablonun reddidir.
#
# Ucuncu kural olmadan iki kademe birbirini kovalar ve sonunda etiket kutunun
# disina tasar -- yani tam olarak birinci kuralin yasakladigi sey, ikinci
# kuralin eliyle geri gelir.

# Rahat bosluk: yarim satir. YENI YARGI (2026-08-17), devralinmis degil.
# Sabit bir yuzde YERINE turetiliyor cunku bosluk puntoya baglidir: 38pt sik
# listesinde %2 bosluk sifira yakin gorunur, 13pt'de fazla acik. Turetilmis
# oldugu icin punto her kisildiginda bosluk da kendiliginden kisilir ve
# kucultme dongusune ayri bir kademe eklemek gerekmez.
# Bu bir OLCUM DEGIL, bir secim -- ama en azindan tek bir puntoya cakili
# degil. MIN_CHOICE_GAP tabani bunun altinda durur.
CHOICE_GAP_LINES = 0.5


def fit_choices(labels: list[str], area_h: float, area_w: float, *,
                space: shapes.Space,
                size: float = TYPE_SCALE["body"]) -> dict:
    """Bu şıklar bu alana sığar mı, sığmazsa neden? -- şablon kabul testi.

    YENI KOD, ESKI AD (2026-08-17). Onceki fit_choices olu dal temizliginde
    FAZLADAN silindi: `apply_choice_plan` gercekten oluydu, ama plani URETEN
    bu fonksiyon degildi -- pick_template onu kabul testi olarak cagiriyor ve
    canli yol da oradan geciyor. Kaynak kurtarilamadi (yedek yok, depo git
    degil, .pyc silme sonrasi yeniden derilmisti).

    SOZLESME ayni, GOVDE yeni, DAVRANIS ESDEGERLIGI DOGRULANMADI -- ve
    dogrulanamaz, cunku karsilastirilacak sey yok. Bu fonksiyonun uzerinde
    durdugu tabanlar (golden, deadband) silme ONCESINDE alindi; onlari "bu
    kodun sinanmis oldugunun kaniti" saymayin. Tabanlar yenilendiginde bu
    notun tarihi de yenilenmeli.

    KAPSAM DARALDI, ve bilerek. Eski surum bir PLAN uretiyordu (punto, bosluk,
    kutu) ve `apply_choice_plan` onu diske yaziyordu. Yazan taraf silindi;
    geriye tek soru kaldi: *bu sablon bu siklari alir mi.* Donen olculer artik
    RAPOR icin -- gercek yerlesimi compose_question_frame ile sablonun kendi
    geometrisi yapiyor. Kimse bu sayilari cizmiyor; "plan boyle dedi" ile
    "ekranda boyle" ayni sey degil.

    EKSEN AYRIMI, yeniden yazmanin tek gercek kazanci. Silinen surum
    `slide_w / 720` diye TEK bir carpan hesapliyordu ve ayni sayiyi hem
    karakter genisligine hem satir yuksekligine uyguluyordu. Olculdu: bu iki
    carpan ayni degil (1920'de 2.667 ve 2.990). Yeni govde kendi olcek
    matematigini HIC yapmiyor; yuksekligi shapes.layout_text_height'a
    soruyor, o da yatayi hscale, dikeyi vscale ile aliyor.

    KUCULTME MERDIVENDE. Eski surum puntoyu "bir eksilt" diye kisiyordu ve
    TYPE_LADDER notunda uretilmis kurstaki on alti farkli puntonun alti
    kaynagindan biri olarak adiyla anilir. Yeni govde `step_down` kullanir:
    kucultme bile olcegin icinde kalir.

    BIRIMLER KARISIK, cunku cagri yeri boyle kuruyor:
        area_h, gap, box_h, total   slayt YUKSEKLIGININ yuzdesi
        area_w                      BIRIM (sablondan okunan sik genisligi)
    Karistirmamak icin yuzde tasiyan her sayi %'yle basilir.
    """
    slide_h = space.slide_h
    n = len(labels)
    dikey = space.v
    kaynak = space.kaynak

    def sonuc(ok, punto, gap, box_h, toplam, why):
        return {"ok": ok, "size": punto, "gap": round(gap, 2),
                "box_h": round(box_h, 2), "total": round(toplam, 2),
                "why": why, "scale_source": kaynak}

    if n < 1:
        return sonuc(False, size, 0.0, 0.0, 0.0, "sik verilmedi")
    if area_w <= 0 or area_h <= 0:
        return sonuc(False, size, 0.0, 0.0, 0.0,
                     f"alan gecersiz: {area_w:.0f} birim genislik, "
                     f"%{area_h:.1f} yukseklik")

    araliklar = max(n - 1, 0)
    punto = snap(size)
    while True:
        # EN UZUN ETIKET DEGIL, EN YUKSEK KUTU. Sarma kelime sinirindan olur,
        # dolayisiyla harf sayisi ile satir sayisi dogru orantili degil: 30
        # harflik tek kelime iki satira sarabilir, 34 harflik uc kelime bir
        # satirda kalabilir. Hepsi olculur, en buyugu alinir -- siklar esit
        # yukseklikte cizildigi icin blogu belirleyen zaten odur.
        birim = max(shapes.layout_text_height(etiket or " ", punto, area_w,
                                              space, wrap=True)
                    for etiket in labels)
        box_h = birim / slide_h * 100

        # ONCE BOSLUK. Rahat bosluktan basla, alan yetmiyorsa tabanina kadar
        # kis. Tabanin ALTINA inmez: sifir bosluklu bir sik listesi teknik
        # olarak sigar, tiklama hedefleri birbirine yapisir ve hicbir yapisal
        # kontrol bagirmaz.
        istenen = CHOICE_GAP_LINES * punto * dikey / slide_h * 100
        gap = (max(MIN_CHOICE_GAP, min(istenen, (area_h - n * box_h) / araliklar))
               if araliklar else 0.0)
        toplam = n * box_h + araliklar * gap

        if toplam <= area_h + FIT_TOLERANCE:
            return sonuc(True, punto, gap, box_h, toplam,
                         f"{n} x %{box_h:.2f} + {araliklar} x %{gap:.2f} = "
                         f"%{toplam:.1f} <= %{area_h:.1f} ({punto:.0f}pt, "
                         f"{area_w:.0f} birim)")

        # SONRA PUNTO, ve yalnizca bir basamak. Taban MIN_CHOICE_SIZE, yani
        # olculmus kalibrasyon bandinin alt ucu: altinda kucultme, hata
        # yonunun bilinmedigi bir bolgede kucultme olur.
        asagi = step_down(punto, MIN_CHOICE_SIZE)
        if asagi >= punto:
            return sonuc(False, punto, gap, box_h, toplam,
                         f"{n} x %{box_h:.2f} kutu + {araliklar} x %{gap:.2f} "
                         f"bosluk = %{toplam:.1f} > %{area_h:.1f} alan; "
                         f"punto tabani {MIN_CHOICE_SIZE:.0f}pt ve bosluk "
                         f"tabani %{MIN_CHOICE_GAP:.1f} asildi "
                         f"({area_w:.0f} birim genislikte)")
        punto = asagi


# "reveal": menu ile AYNI iskelet, farkli is. Menu SIRA sectirir
# (tiklama baska slayda gider); reveal ICERIGI acar (tiklama katman
# gosterir, ogrenci ayni slaytta kalir). Ayni bant kodunu paylasiyorlar
# cunku ikisi de "basliklar sayfanin kendisidir" diyor.
LAYOUTS = ("cover", "section", "content", "bullets", "steps", "statement",
           "menu", "reveal")
IMAGE_STYLES = ("panel", "bleed", "hero")

# Structural variants. Each layout has one skeleton, which is what keeps a deck
# coherent -- and also what makes every deck resemble every other one. A style
# shifts where the accent sits and how a heading is set, so two courses differ
# while either one stays internally consistent.
# "ground" is how the slide is painted underneath everything: a flat field is
# the giveaway that nobody designed it. A gradient costs one extra element and
# reads as depth, so only "plain" keeps the flat ground, on purpose.
STYLES = {
    "rail":   {"mark": "rail",   "rule": True,  "eyebrow_case": "upper",
               "ground": ("grad", 90)},
    "corner": {"mark": "corner", "rule": False, "eyebrow_case": "upper",
               "ground": ("grad", 45)},
    "band":   {"mark": "band",   "rule": False, "eyebrow_case": "title",
               "ground": ("grad", 135)},
    "plain":  {"mark": "none",   "rule": True,  "eyebrow_case": "title",
               "ground": ("flat", 0)},
}


# ------------------------------------------------------------------- varyantlar
#
# STYLES vurgunun rengini ve nerede durdugunu degistirir; iskelet ayni kalir.
# Olcum bunun yetmedigini gosterdi: dort farkli duzenle uretilen bir deckte
# konumlu 23 seklin 18'i ayni x'ten (%8) basliyordu, cunku MARGIN_X bir modul
# sabiti ve her duzen her ogeyi oradan aciyor. Bulaniklastirildiginda dort
# slayt ayni resim -- duzen adlari farkli, siluet ayni.
#
# Varyant bu ekseni acar: metin sutunu nerede baslar, ne kadar genis, dikey
# bandin neresine oturur, ve cagri butonu hangi kenara yaslanir. Renk degil,
# iskelet. Iki slayt ayni varyanti tasidiginda ayni siluete sahip olur; ardisik
# tekrar yasaginin korudugu sey de tam olarak bu.
#
# Olculer slayt yuzdesidir: (sol_kenar, genislik).
VARIANTS: dict[str, dict[str, dict]] = {
    # section ve bullets EKLENDI (2026-08-18). Gerekcesi olculdu, secilmedi:
    # uretilen kursta `content` 4 slaydini 4 FARKLI varyanta dagitiyor ve
    # tekrar uretmiyor; tekrarin tamami varyanti OLMAYAN iki duzenden geliyor
    # (section 4 slayt, bullets 4 slayt, ikisi de tek imza). 16 slaydin 14'u
    # uc imzaya yigilmisti.
    #
    # DIGER DORT DUZENE (cover, steps, statement, menu) VARYANT EKLENMEDI:
    # bu kursta HIC kullanilmiyorlar (olculdu), yani cesitlilik oradan
    # gorunmez. Kullanilmayan yola is harcamamak -- apply_choice_plan'in
    # 0/4'uyle ayni refleks.
    #
    # DEGERLER OLCUM DEGIL, YARGI. Ama serbest de degil: mevcut dort imza
    # ([0,8], [0,8,62], [0,22,35], [0,48,62]) bir tasarim dili kurmus
    # durumda ve yeni varyantlar o dilin ICINDE kaliyor -- ayni x
    # yogunlasmalarini kullanip KOMBINASYONU degistiriyorlar. Rastgele x
    # uretmek cesitliligi artirir ama tutarliligi dusurur; C3'un kusuru
    # tekduzelik, cozumu rastgelelik degil.
    #
    # SAYI, SLAYT SAYISINA GORE: her iki duzen de kursta 4 kez uretiliyor,
    # dolayisiyla 3-4 varyant yeter. content alti varyantla dort imza
    # veriyor -- ikisi fazlalik, ve o fazlalik burada tekrarlanmadi.
    "section": {
        "sol":        {"text": (8.0, 84.0),  "cizgi_x": 8.0},
        "ortalanmis": {"text": (22.0, 56.0), "cizgi_x": 22.0},
        "sag":        {"text": (48.0, 44.0), "cizgi_x": 48.0},
        "sol-serit":  {"text": (8.0, 60.0),  "cizgi_x": 62.0},
    },
    "bullets": {
        "tam":       {"text": (8.0, 84.0), "kart": (8.0, 84.0)},
        "girintili": {"text": (8.0, 84.0), "kart": (22.0, 56.0)},
        "sag-kart":  {"text": (8.0, 40.0), "kart": (48.0, 44.0)},
    },
    # statement EKLENDI (2026-08-29). Yukaridaki "kullanilmayan yola is
    # harcamamak" gerekcesi BU DUZEN ICIN ARTIK GECERSIZ: ayrac kapisi
    # (_ayrac_yamasi) arkasi bos bir section'i statement'a ceviriyor ve
    # olculdu -- alti sahneli bir kursta UC section birden statement oldu.
    # Tek imzali bir duzeni sik kullanmak, tekduzeligi tasimak demek; kapi
    # bir monotonlugu digeriyle takas etmis olurdu.
    #
    # UCU DE AYNI DILDE: x yogunlasmalari (8, 22) ve olculer degismiyor.
    # Degisen sey BILESIM -- yanda ince vurgu / hic mobilya yok / arkada
    # yatay serit. Uc ayri siluet, uc ayri agirlik merkezi.
    "statement": {
        "sol-vurgu":  {"bicim": "vurgu", "text": (MARGIN_X + 4, CONTENT_W * 0.74),
                       "hiza": "l"},
        "ortalanmis": {"bicim": "sade",  "text": (22.0, 56.0), "hiza": "c"},
        "serit":      {"bicim": "serit", "text": (22.0, 56.0), "hiza": "c"},
    },
    "content": {
        "sol-panel":  {"text": (8.0, 45.4),  "panel": (57.4, 34.6),
                       "band": "spread", "cta": "left"},
        "genis-olcu": {"text": (8.0, 68.9),  "panel": None,
                       "band": "top",    "cta": "left"},
        "sag-metin":  {"text": (48.0, 44.0), "panel": (8.0, 34.0),
                       "band": "centre", "cta": "right"},
        "ortalanmis": {"text": (22.0, 56.0), "panel": None,
                       "band": "centre", "cta": "centre"},
        "ust-serit":  {"text": (8.0, 84.0),  "panel": None,
                       "band": "top",    "cta": "right", "head": "band"},
        "alt-baslik": {"text": (8.0, 60.0),  "panel": None,
                       "band": "centre", "cta": "left",  "order": "reverse"},
    },
}


def variants_for(layout: str) -> list[str]:
    return sorted(VARIANTS.get(layout, {}))


def variant_for(layout: str, *, name: str | None = None, seed: str = "",
                avoid: str | list[str] | None = None) -> dict:
    """Bir düzenin varyantını seçer; ardışık tekrarı elinden geldiğince önler.

    `avoid` ya bir öncekinin adı, ya da geçmiş (en yenisi sonda). Geçmiş
    verildiğinde seçim **en uzun süredir kullanılmayana** gider. Yalnızca bir
    öncekine bakmak yasağı tutar ama aralığı tutmaz: on slaytlık bir kurs
    ardışık tekrar olmadan aynı varyantı iki slayt arayla geri getirebilir ve
    göz bunu "yine aynı sayfa" diye okur. Ölçüldü -- aynı varyant, aynı
    içerik şekli, siluet farkı 0.000. Aralığı büyüten tek şey geçmiş.

    Eşitliği hash bozar, `sum(ord(c))` değil: karakter toplamı benzer
    başlıkları aynı kovaya yığıyor ve sözlüğün bir kısmı hiç seçilmiyordu.
    Altı ad yazılıp dördüne ulaşılması, havuzun beyan edilenden küçük olması
    demek -- kendi sözlüğünü görememenin, yokluk olarak raporlanması.

    Tek varyantlı bir ailede kaçınılan ad yine gelir ve karar önceden
    verilmiştir: **yasak çiğnenir, sessizce değil.** Alternatif, slaydı hiç
    üretmemek olurdu; içerik çeşitlilikten önce gelir. Çiğneme `repeated=True`
    ile döner ve çağıran onu bilinen-sınır kanalına yazar.
    """
    table = VARIANTS.get(layout) or {}
    if not table:
        return {"name": None, "repeated": False, "pool": 0}
    keys = sorted(table)
    history = [avoid] if isinstance(avoid, str) else list(avoid or [])
    previous = history[-1] if history else None

    if name in table:
        picked = name
    else:
        def age(key: str) -> int:
            # Kac slayt once kullanildi; hic kullanilmadiysa sonsuz.
            for back, used in enumerate(reversed(history), start=1):
                if used == key:
                    return back
            return len(history) + 1

        digest = int(hashlib.sha256((seed or "").encode("utf-8")).hexdigest(), 16)
        best = max(age(k) for k in keys)
        options = [k for k in keys if age(k) == best]
        picked = options[digest % len(options)]

    return {"name": picked, "repeated": picked == previous and previous is not None,
            "pool": len(keys), **table[picked]}


def _apply_style(page: "_Page", colors: dict, style: str | None,
                 pkg: StoryPackage) -> dict:
    """Zemin ve vurgu isareti. UC CERCEVE DE BURADAN GECER.

    Ayri yazilmasinin sebebi kopyalamamak degil, UNUTMAMAK: uc cerceveden
    biri bu adimi atlarsa o tip slayt kursun icinde duz zeminli ve
    isaretsiz durur, ve fark ancak yan yana konunca gorunur. Kural tek
    yerde durunca "yeni bir cerceve yazildi, uslup baglanmadi" durumu
    olamaz.
    """
    look = style_for(style, seed=pkg.path.stem)
    kind, angle = look.get("ground", ("flat", 0))
    if kind == "grad" and colors.get("deep"):
        page.background(colors["bg"], to=colors["deep"], angle=angle)
    else:
        page.background(colors["bg"])
    _mark(page, look, colors, "content")
    return look


# ------------------------------------------------------ soru duzeni varyantlari
#
# EKSEN, ICERIK VARYANTLARININ AYNISI: metin sutunu nerede baslar, ne kadar
# genis. Renk degil, ISKELET -- iki soru ayni varyanti tasiyorsa bulaniklastirildiginda
# ayni resim olur, ve "butun sorular ayni" sikayetinin olculebilir hali budur.
#
# SIK SUTUNU KOKTEN AYRI VERILIYOR, ve bu bilerek: `girintili` varyantinda
# kok tam genislikte durur, siklar iceri cekilir. Tek bir (x, w) ciftiyle o
# siluet kurulamazdi ve kurulabilen tek sey "her sey ayni yerden baslar"
# olurdu -- kacilan seyin ta kendisi.
#
# DEGERLER OLCUM DEGIL, YARGI -- ama serbest de degil: icerik varyantlarinin
# kurdugu dilin ICINDE kaliyorlar (8 / 22 / 35 / 48 yogunlasmalari).
# IKINCI EKSEN: SIK YIGINI BANDIN NERESINE OTURUR.
#
# Yatay eksen tek basina yetmedi, ve bu CIZIME BAKILARAK gorundu: dort
# varyant dort farkli x veriyordu ama dordunde de yigin kokun hemen altina
# yapisip slaydin alt yarisi bos kaliyordu. Yani siluetler farkliydi,
# AGIRLIK MERKEZI ayniydi -- bulaniklastirildiginda dordu de "ustte bir
# blok, altta bos" resmi.
#
# `anchor` o bosluğu boluşturur: "ust" bugunku davranis (bosluk altta),
# "orta" yigini kalan bandin ortasina alir. Uc-bir dagitildi, cunku dordu
# de ortalanmis olsaydi eksen yine tek degerli olurdu.
QUESTION_VARIANTS: dict[str, dict] = {
    "tam":        {"stem": (8.0, 84.0),  "choices": (8.0, 84.0),  "anchor": "orta"},
    "ortalanmis": {"stem": (18.0, 64.0), "choices": (18.0, 64.0), "anchor": "orta"},
    "girintili":  {"stem": (8.0, 84.0),  "choices": (22.0, 70.0), "anchor": "ust"},
    "sag":        {"stem": (35.0, 57.0), "choices": (35.0, 57.0), "anchor": "orta"},
}
QUESTION_DEFAULT = "tam"


def question_variant_for(seed: str = "", *, name: str | None = None,
                         avoid: "list[str] | None" = None) -> str:
    """Varyant secimi: verilirse o, yoksa TOHUMDAN turetilir.

    Turetme rastgele degil: ayni kurs iki kez uretildiginde ayni varyantlar
    cikmali, yoksa "hangi varyant secildi" tekrar uretilemeyen bir sayi
    olurdu. `avoid` ardisik tekrari kirar -- icerik tarafindaki yasagin
    soru tarafindaki karsiligi.
    """
    if name in QUESTION_VARIANTS:
        return name
    havuz = [v for v in sorted(QUESTION_VARIANTS) if v not in (avoid or [])]
    if not havuz:
        havuz = sorted(QUESTION_VARIANTS)
    # SECICI ICERIK TARAFIYLA AYNI KALIR (ord toplami), ve bunun bir
    # hikayesi var -- yaziliyor, cunku yanlis tesis edilmis bir "kusur"
    # duzeltmesi kodda gerekcesiyle donup kalirsa bir sonraki okuyucu onu
    # olculmus sanar.
    #
    # 2026-08-30: dort soru kokuyle denendi, dordu de dort kovadan IKISINE
    # dustu (mod4 = 0,1,0,1). Bu "karakter toplami yigiliyor" diye okundu
    # ve secici sha256'ya cevrildi. SONRA GERCEK ORNEKLEMLE OLCULDU --
    # korpustaki 67 benzersiz soru koku:
    #
    #     eski (ord toplami)   ki-kare 1.48   ← DUZ
    #     yeni (sha256)        ki-kare 3.27   ← o da duz, ama daha az
    #     (3 serbestlik derecesi, p=0.05 esigi 7.81)
    #
    # Yani yigilma YOKTU: dort ornek yeterince kucuktu ki 0,1,0,1 dizisi
    # rastlanti olsun. Tesis kucuk orneklemden geldi, DOGRULAMA DA AYNI
    # DORT ORNEKLE yapildi -- olcumun kendi kuyrugunu isirmasi.
    #
    # Ardisik tekrari kiran sey hash degil, `avoid`: ayni 67 kokte
    # avoid'siz 11/66 ardisik tekrar var, avoid'li 0/66 -- ve bu iki
    # secicide de AYNI. Dolayisiyla sha256 olculebilir hicbir sey
    # kazandirmiyordu; birakilsaydi geriye ayni soruyu ("hangi varyant?")
    # iki farkli yoldan cevaplayan iki mekanizma kalirdi.
    return havuz[sum(ord(c) for c in (seed or "x")) % len(havuz)]


def _question_frame_once(pkg: StoryPackage, part: str, *,
                         eyebrow: str | None, palette: dict | None,
                         stem_guid: str | None,
                         choice_guids: list[str],
                         style: str | None,
                         variant: str) -> dict:
    """Soru slaydının çerçevesini KURAR: üst etiket, kök, şık yığını.

    Tohumdan yalnizca anatomi kaldi (etkilesim, sik kaplari, katmanlar);
    gorunen her sey burada kurulur ve icerik slaytlariyla AYNI olculeri
    kullanir -- ayni kenar boslugu, ayni tipografi olcegi, ayni taban.
    Boylece bir soru slaydi kursun icinde yabanci durmaz.

    Siklar tam genislikte alt alta dizilir. Olculdu: yatay bir sira hicbir
    sik sayisinda cumle tasiyamiyor (iki sikta bile satir basi 18 karakter,
    okunabilir taban 22), ve bir soru sikki cumledir.
    """
    root = pkg.parse(part)
    shape_list = root.find("shapeLst")
    if shape_list is None:
        return {"framed": False}
    colors = _palette(palette)
    page = _Page(pkg, root, colors)
    width, height = page.width, page.height

    # USLUP VE VARYANT, ICERIK SLAYTLARINDAKI AYNI IKI EKSEN.
    #
    # Bu fonksiyonun bir donem HIC uslubu yoktu: `style` parametresi bile
    # almiyordu. Sonucu olculdu 2026-08-30 -- icerik slaytlari dort uslup ve
    # (duzenine gore) alti varyant arasindan seciliyorken soru slaydi
    # 1x1'di: her kursta, her soruda ayni duz zemin, ayni isaretsiz kenar,
    # ayni tam genislikte dikey yigin. Tohum havuzunu buyutmek bunu
    # degistirmiyordu, cunku tohumdan yalnizca anatomi aliniyor ve gorunen
    # her sey burada kuruluyor. Yani "butun sorular ayni" sikayetinin
    # kaynagi kutuphane degil, BU FONKSIYONDU.
    # USLUP TOHUMU KOK DEGIL, KURSUN KIMLIGI. Kokten turetmek her soruya
    # ayri bir uslup veriyordu (olculdu: dort soru, iki uslup, sirayla) --
    # oysa uslup kurs ICINDE sabit, kurslar ARASINDA farkli olmali; bu,
    # donors.choose'un zaten uyguladigi kural. Varyant soru basina degisir,
    # uslup degismez: biri ritim, digeri kimlik.
    look = _apply_style(page, colors, style, pkg)
    if eyebrow and look["eyebrow_case"] == "title":
        eyebrow = eyebrow.title()
    else:
        eyebrow = eyebrow.upper() if eyebrow else eyebrow
    spec = QUESTION_VARIANTS.get(variant) or QUESTION_VARIANTS[QUESTION_DEFAULT]
    kok_x, kok_w = spec["stem"]
    sik_x, sik_w = spec["choices"]
    sik_hizasi = spec.get("anchor", "ust")

    by_guid = {s.get("g"): s for s in shape_list if s.get("g")}
    choices = [by_guid[g] for g in choice_guids if g in by_guid]
    stem = by_guid.get(stem_guid or "")

    top = CEILING
    if eyebrow:
        h = page.text_height(eyebrow, "eyebrow", kok_w)
        page.text(eyebrow, top, role="eyebrow", height=h, x=kok_x, w=kok_w,
                  color=colors["accent_text"])
        top += h + UNIT * 100 * 0.5

    # SIK BANDI KOKTEN ONCE AYRILIR.
    #
    # Eski hali koku ONCE ve SINIRSIZ yaziyor, siklara KALANI veriyordu.
    # Olculdu (2026-08-19, bes uzun sikli soru): bant %37.9'dan basliyor,
    # her yuvaya %9.54 kaliyor, en uzun etiket %9.95 istiyor -- yani
    # cerceve %4'luk bir farkla REDDEDIYOR. Red "hicbir sablon bes sikki
    # tasiyamaz" diye okundu; dogru okuma "kok cerceveyi yedi" idi.
    #
    # Bedeli buyuktu: red -> geri cekilme -> soru PUANLANMIYOR. Yani
    # kataloga tohum eklemekle cozulecek sanilan sey, bir yerlestirme
    # kusuruydu.
    #
    # Ayni kural content, cover, bullets, menu ve _buttons'ta ya vardi ya
    # bu oturumda konuldu. Bu YEDINCISI (K25).
    sik_bandi = 0.0
    if choices:
        n_sik = len(choices)
        # TABAN PUNTODA olculur: tabanda sigan bant her zaman sigar, ve
        # asagidaki dongu yer varsa daha buyuk punto secebilir.
        taban_birim = max(shapes.height_for_label(
            s, model.shape_text(root, s.get("g") or "").strip(),
            MIN_CHOICE_SIZE, sik_w / 100 * width, page.space)
            for s in choices)
        sik_bandi = (taban_birim / height * 100) * n_sik             + MIN_CHOICE_GAP * (n_sik - 1)
        # Kok en az BIR SATIR alir; siklar gerisini alir. Kokten tumuyle
        # pay almak, soruyu okunamaz yapardi.
        kok_min = page.text_height("X", "lead", kok_w)
        sik_bandi = min(sik_bandi,
                        max(FLOOR - top - kok_min - UNIT * 100, 0.0))
    kok_tabani = FLOOR - sik_bandi - (UNIT * 100 if sik_bandi else 0.0)

    stem_size = None
    if stem is not None:
        text = model.shape_text(root, stem_guid or "").strip()
        # Kokun PUNTOSU da kursun olceginden gelir. Tohumunki birakiliyordu
        # ve merdivende olmayan tek deger oydu: kutu 21pt'ye gore olculup
        # 18pt yaziliyordu -- yani olcum ile cizim ayri puntodan konusuyordu.
        stem_size = page.size_of("lead")
        stem_h = page.text_height(text, "lead", kok_w)
        # KOK KENDI BANDINA KUCULUR. Kok kucultulebilir (kalibre bandin
        # ustunde baslar), sik kutusu kucultulemez -- o yuzden sikisma
        # koke biner. `page.text` ayni sirayi zaten baska yerde uyguluyor.
        oda = max(kok_tabani - top, 0.0)
        while stem_h > oda + FIT_TOLERANCE and stem_size > MIN_CHOICE_SIZE:
            nxt = step_down(stem_size, MIN_CHOICE_SIZE)
            if nxt >= stem_size:
                break
            stem_size = nxt
            stem_h = shapes.layout_text_height(
                text, stem_size, kok_w / 100 * width,
                page.space) / height * 100
        stem_h = min(stem_h, oda) if oda else stem_h
        shapes.set_loc(stem, kok_x / 100 * width, top / 100 * height,
                       (kok_x + kok_w) / 100 * width,
                       (top + stem_h) / 100 * height)
        shapes.set_text_flow(stem, vertical="t", grow=False)
        top += stem_h + UNIT * 100

    # Siklar: olculen ihtiyaca gore yuva, sigmiyorsa punto kisilir.
    if choices:
        left = sik_x / 100 * width
        right = (sik_x + sik_w) / 100 * width
        floor = FLOOR / 100 * height
        band_top = top / 100 * height
        gap = MIN_CHOICE_GAP / 100 * height
        size = TYPE_SCALE["body"]
        while True:
            need = max(shapes.height_for_label(
                s, model.shape_text(root, s.get("g") or "").strip(),
                size, right - left, page.space) for s in choices)
            total = need * len(choices) + gap * (len(choices) - 1)
            if total <= floor - band_top or size <= MIN_CHOICE_SIZE:
                break
            nxt = step_down(size, MIN_CHOICE_SIZE)
            if nxt >= size:
                break
            size = nxt
        # TABANDA SIGMIYORSA YERLESTIRME, GEREKCELI RED VER.
        #
        # Asagidaki `each` bir donem KOSULSUZ `min(need, mevcut)` idi: yani
        # sigmadigini bildigi halde kutuyu mevcuda kirpiyor, metin de kutunun
        # disina tasiyordu. Geometri taban icinde kaldigi icin hicbir yapisal
        # kontrol bagirmiyordu -- tasan sey METINDI ve onu olcen yoktu.
        #
        # Sozlesme fit_choices ile ayni tutuluyor: sigmazsa NEDEN. Iki
        # hesabin ayni soruya ayni cevabi vermesi gerekiyor; bugun
        # vermiyorlar (fit_choices "sigar" derken cerceve sigdiramiyor) ve
        # bu ayrisma DEVIR'de kayitli. Red, en azindan sessiz olmayi bitirir.
        mevcut = max((floor - band_top - gap * (len(choices) - 1))
                     / len(choices), height * 0.06)
        if need > mevcut + FIT_TOLERANCE / 100 * height:
            raise ChoiceLabelsTooLong(
                f"{len(choices)} sik taban puntoda ({size:.0f}pt) bile "
                f"sigmiyor: her yuvaya %{mevcut / height * 100:.2f} kaliyor, "
                f"en uzun etiket %{need / height * 100:.2f} istiyor "
                f"(bant %{band_top / height * 100:.1f}..%{floor / height * 100:.1f}, "
                f"bosluk %{MIN_CHOICE_GAP:.1f}, varyant {variant!r} sutunu "
                f"%{sik_w:.0f}). Etiketleri kisaltin — sablon eklemek bu "
                f"durumu cozmez.")
        each = min(need, mevcut)
        # HIZA: artan bosluk ya altta kalir ya ikiye bolunur. Kok her zaman
        # yukarida durur -- ortalanan sey yigin, slaydin tamami degil;
        # soruyu okumadan siklara bakilmaz, o yuzden okuma sirasi bozulmaz.
        toplam = each * len(choices) + gap * (len(choices) - 1)
        artan = max(floor - band_top - toplam, 0.0)
        if sik_hizasi == "orta":
            band_top += artan / 2
        for index, shape in enumerate(choices):
            slot = band_top + index * (each + gap)
            shapes.set_loc(shape, left, slot, right, slot + each)
            if palette:
                shapes.set_fill(shape, colors["surface"])

        # ELIPS -> KAPSUL, GEOMETRI NIHAI OLDUKTAN SONRA.
        #
        # Bu cagri once `adapt_seeded_slide`'daydi ve HIC atesle medi. Olculdu:
        # o anda ovaller hala donor olcusunde (161x149 = 1.1 ve 161x261 = 0.6),
        # yani kalibrasyon bandinin ICINDE -- guard dogru davranip dokunmadi.
        # Gerilme burada oluyor (1613x74 = 21.9), dolayisiyla cevirme de
        # burada olmali. "Dogru kosul, yanlis an" bu oturumda ucuncu kez
        # cikti; kosulun kendisi degil, YERI yanlisti.
        _ovali_kapsullestir(root, [s.get("g") or "" for s in choices])
        pkg.replace_xml(part, root)
        if stem_guid and stem_size:
            _restyle(pkg, part, stem_guid, size=stem_size)
        for shape in choices:
            _restyle(pkg, part, shape.get("g") or "", size=size)
        return {"framed": True, "choice_size": size, "stem_size": stem_size,
                "style": look["name"], "variant": variant,
                "choice_height_pct": round(each / height * 100, 1)}

    pkg.replace_xml(part, root)
    if stem_guid and stem_size:
        _restyle(pkg, part, stem_guid, size=stem_size)
    return {"framed": True, "stem_size": stem_size,
            "style": look["name"], "variant": variant}


def compose_question_frame(pkg: StoryPackage, part: str, *,
                           eyebrow: str | None, palette: dict | None,
                           stem_guid: str | None,
                           choice_guids: list[str],
                           style: str | None = None,
                           variant: str | None = None,
                           avoid_variant: "list[str] | None" = None) -> dict:
    """Soru cercevesi, uslup ve varyantla. Sigmayan varyant TAM'a duser.

    GERI DUSUS SESSIZ DEGIL. Dar bir sutun uzun bir sikki tasiyamayabilir ve
    o durumda dogru davranis soruyu reddetmek DEGIL: varyant susleme, sik
    metni islev. Ama dusus rapora yazilir (`variant_fallback`), cunku
    sessizce genisleyen bir sutun "neden butun sorular yine ayni gorunuyor"
    sorusunun cevabini gizlerdi -- bu dosyanin en pahali aliskanligi.
    """
    seed = (model.shape_text(pkg.parse(part), stem_guid or "") or "")[:24]
    secilen = question_variant_for(seed, name=variant, avoid=avoid_variant)
    try:
        return _question_frame_once(
            pkg, part, eyebrow=eyebrow, palette=palette, stem_guid=stem_guid,
            choice_guids=choice_guids, style=style, variant=secilen)
    except ChoiceLabelsTooLong as dar:
        if secilen == QUESTION_DEFAULT:
            raise
        out = _question_frame_once(
            pkg, part, eyebrow=eyebrow, palette=palette, stem_guid=stem_guid,
            choice_guids=choice_guids, style=style, variant=QUESTION_DEFAULT)
        return {**out, "variant_fallback": secilen, "fallback_reason": str(dar)[:120]}


# ------------------------------------------------------------- surukle-birak
#
# AYRI CERCEVE, cunku AYRI ISKELET. compose_question_frame'in tek bir duzeni
# var -- kok, altinda tam genislikte dikey sik yigini -- ve o duzen surukle-
# birak'i tasiyamaz: burada ekranda IKI kume durur (suruklenenler ve kutular)
# ve aralarindaki bosluk anlamin kendisidir. Ayni fonksiyona bir bayrakla
# eklemek iki iskeleti tek dallanma agacina sikistirmak olurdu; ayirmak,
# "her duzene bir is" kuralinin soru tarafindaki karsiligi.
#
# ORANLAR OLCUM DEGIL, ELLE YAPILMIS KURSTAN OKUNDU (0_duz_kopya slide18,
# 1920x1080): suruklenenler bandi 250..613 (%33.6), kutular 712..1036 (%30).
# Yani ikisi kabaca esit ve suruklenen tarafi bir tik genis. Asagidaki
# 0.52/0.48 bolusumu o okumanin yuzdeye cevrilmis haliydi -- ve SABITTI.
#
# SABIT BOLUSUM OLCULDU VE COKTU (2026-08-30). 12 oge / 4 kutu, etiketler
# "Erisim gozden gecirme" uzunlugunda -- yani pedagoji promptunun 55
# karakterlik tavaninin cok altinda. Cerceve yine de REDDETTI (hucreye
# %8.71 kaliyor, en uzun etiket %9.95 istiyor) ve gerekce "etiketleri
# kisaltin" dedi. Etiket zaten kisaydi; bos yer YARI BOS DURAN kuyu
# bandindaydi. Bu, bu dosyada zaten kayitli olan kusurun aynisi (bkz.
# "SIK BANDI KOKTEN ONCE AYRILIR"): red dogru sinyal, YANLIS SEBEP.
#
# O yuzden bolusum artik satir sayisina bakiyor. Iki egri ayri: oge
# izgarasinin ihtiyaci SATIRLA buyur, kuyununki KUTU SAYISIYLA -- ve kutu
# sayisi zaten sutun sayisini belirledigi icin genislikten karsilaniyor.
DRAG_ITEM_BAND_RANGE = (0.45, 0.76)


def _drag_band_share(rows: int) -> float:
    """Oge izgarasinin kalan banttan aldigi pay, SATIR SAYISINA GORE.

    rows=2 -> 0.59, rows=3 -> 0.68, rows=4 -> 0.74. Iki satirda eski sabite
    (0.52) yakin duruyor -- elle yapilmis kurs iki satirliydi ve oran oradan
    okunmustu. Dorde cikildiginda izgara nefes aliyor, kuyu hala slaydin
    yaklasik besde biri.
    """
    alt, ust = DRAG_ITEM_BAND_RANGE
    return max(alt, min(ust, rows / (rows + 1.4)))
DRAG_GAP_X = 1.6          # sutunlar arasi, slayt GENISLIGININ yuzdesi

# IKI BANT ARASI, SATIR ARASINDAN GENIS OLMAK ZORUNDA. Ilk surumde ikisi de
# MIN_CHOICE_GAP idi ve cizime BAKINCA gorundu: alti suruklenen ve uc kutu
# tek bir 3x3 izgara gibi okunuyordu. Burada bosluk susleme degil, ANLAM --
# "sunlar" ile "sunlarin icine" arasindaki siniri gozun cizmesi gerekiyor,
# ve tek isareti dolgu farkiysa siniri ancak deneyerek buluyor.
# 2.5 DENENDI VE YETMEDI -- cizime bakildi, iki bant hala tek izgara gibi
# okunuyordu (%1.6'ya karsi %2.5, 520px'lik cizimde 8px'e karsi 13px).
# Sinirin ROW ARASINDAN acikca genis olmasi gerekiyor; 5.0 ucte bir bantlik
# bir nefes birakiyor ve kuyu bandi zaten buyuk oldugu icin bedeli yok.
DRAG_BAND_GAP = 5.0       # MIN_CHOICE_GAP'in ~3 kati


def _shrink_to_cells(root, page, shapes_by_guid, guids, size, cell_w, cell_h):
    """Butun etiketler kendi hucresine sigana kadar puntoyu kis.

    compose_question_frame'deki dongu ile ayni sozlesme: once kucult, sonra
    TABANDA hala sigmiyorsa sessizce kirpma -- gerekce ver. Fark yalnizca
    hucrenin iki boyutlu olmasi.
    """
    need = 0.0
    while True:
        need = max(shapes.height_for_label(
            shapes_by_guid[g], model.shape_text(root, g).strip(),
            size, cell_w, page.space) for g in guids)
        if need <= cell_h or size <= MIN_CHOICE_SIZE:
            break
        nxt = step_down(size, MIN_CHOICE_SIZE)
        if nxt >= size:
            break
        size = nxt
    return size, need


def compose_drag_frame(pkg: StoryPackage, part: str, *,
                       eyebrow: str | None, palette: dict | None,
                       stem_guid: str | None,
                       pairs: list[tuple[str, str]],
                       style: str | None = None) -> dict:
    """Surukle-birak slaydinin cercevesi: ust etiket, kok, oge izgarasi, kutular.

    pairs, `<choices>` belge sirasinda (suruklenen, hedef) ciftleridir --
    dogru cevabin ta kendisi. Buradan iki liste turer ve ikisi de SIRAYI
    korur: ayni girdiyle iki kosu ayni yerlesimi vermeli.
    """
    root = pkg.parse(part)
    shape_list = root.find("shapeLst")
    if shape_list is None:
        return {"framed": False}
    colors = _palette(palette)
    page = _Page(pkg, root, colors)
    width, height = page.width, page.height
    # Uslup soru cercevesiyle AYNI kaynaktan. Baglanmasaydi surukle-birak
    # slaydi duz zeminli ve isaretsiz kalir, yani kursun icinde yabanci
    # dururdu -- tohumdan yalnizca anatomi alma kuralinin bedeli.
    look = _apply_style(page, colors, style, pkg)
    if eyebrow:
        eyebrow = eyebrow.title() if look["eyebrow_case"] == "title" else eyebrow.upper()

    by_guid = {s.get("g"): s for s in shape_list if s.get("g")}
    items: list[str] = []
    zones: list[str] = []
    for item_guid, zone_guid in pairs:
        if item_guid in by_guid and item_guid not in items:
            items.append(item_guid)
        if zone_guid in by_guid and zone_guid not in zones:
            zones.append(zone_guid)
    if not items or not zones:
        # Sessizce "framed: True" demek, tam olarak kacinilan sey: kutusu
        # silinmis bir slayt gecerli bir dosya uretir ve cevaplanamaz.
        return {"framed": False,
                "reason": f"suruklenen={len(items)} kutu={len(zones)}"}

    stem = by_guid.get(stem_guid or "")
    top = CEILING
    if eyebrow:
        h = page.text_height(eyebrow, "eyebrow", CONTENT_W)
        page.text(eyebrow, top, role="eyebrow", height=h,
                  color=colors["accent_text"])
        top += h + UNIT * 100 * 0.5

    stem_size = None
    if stem is not None:
        text = model.shape_text(root, stem_guid or "").strip()
        stem_size = page.size_of("lead")
        stem_h = page.text_height(text, "lead", CONTENT_W)
        shapes.set_loc(stem, MARGIN_X / 100 * width, top / 100 * height,
                       (MARGIN_X + CONTENT_W) / 100 * width,
                       (top + stem_h) / 100 * height)
        shapes.set_text_flow(stem, vertical="t", grow=False)
        top += stem_h + UNIT * 100

    ara = MIN_CHOICE_GAP
    kalan = FLOOR - top - DRAG_BAND_GAP
    if kalan <= 0:
        raise ChoiceLabelsTooLong(
            f"Surukle-birak kokunden sonra bant kalmadi (%{FLOOR - top:.1f}). "
            f"Koku kisaltin.")
    # SUTUN SAYISI KUTU SAYISINDAN. Uc kutu icin uc sutun, elle yapilmis
    # kurstaki 3x3 izgaranin aynisi -- goz ustteki sutunla alttaki kutuyu
    # esler. Tavan 4: besinci sutunda hucre genisligi bir cumleyi tasimiyor
    # (compose_question_frame'de yatay sira ayni sebeple reddedilmisti).
    cols = max(2, min(len(zones), 4))
    cols = min(cols, len(items))
    rows = -(-len(items) // cols)
    oge_bandi = kalan * _drag_band_share(rows)
    kutu_bandi = kalan - oge_bandi
    cell_w = (CONTENT_W - DRAG_GAP_X * (cols - 1)) / cols
    cell_h = (oge_bandi - ara * (rows - 1)) / rows

    size, need = _shrink_to_cells(root, page, by_guid, items,
                                  TYPE_SCALE["body"],
                                  cell_w / 100 * width, cell_h / 100 * height)
    if need > cell_h / 100 * height + FIT_TOLERANCE / 100 * height:
        raise ChoiceLabelsTooLong(
            f"{len(items)} surukleme etiketi taban puntoda ({size:.0f}pt) bile "
            f"{cols}x{rows} izgaraya sigmiyor: hucreye "
            f"%{cell_h:.2f} kaliyor, en uzun etiket "
            f"%{need / height * 100:.2f} istiyor. Etiketleri kisaltin ya da "
            f"oge sayisini dusurun.")

    for index, guid in enumerate(items):
        row, col = divmod(index, cols)
        left = (MARGIN_X + col * (cell_w + DRAG_GAP_X)) / 100 * width
        slot = (top + row * (cell_h + ara)) / 100 * height
        shapes.set_loc(by_guid[guid], left, slot,
                       left + cell_w / 100 * width,
                       slot + cell_h / 100 * height)
        if palette:
            shapes.set_fill(by_guid[guid], colors["surface"])

    # KUTULAR ICERI CEKILMIS OKUNMALI. Suruklenenle ayni dolguyu verirsek
    # ekranda on iki esdeger kutu olur ve hangisinin hedef oldugu ancak
    # denenerek anlasilir. "deep" zaten paletin en koyu yuzeyi.
    zone_top = top + oge_bandi + DRAG_BAND_GAP
    zone_w = (CONTENT_W - DRAG_GAP_X * (len(zones) - 1)) / len(zones)
    zone_size, zone_need = _shrink_to_cells(
        root, page, by_guid, zones, TYPE_SCALE["body"],
        zone_w / 100 * width, kutu_bandi / 100 * height)
    for index, guid in enumerate(zones):
        left = (MARGIN_X + index * (zone_w + DRAG_GAP_X)) / 100 * width
        shapes.set_loc(by_guid[guid], left, zone_top / 100 * height,
                       left + zone_w / 100 * width,
                       (zone_top + kutu_bandi) / 100 * height)
        if palette:
            shapes.set_fill(by_guid[guid], colors["deep"])
        shapes.set_text_flow(by_guid[guid], vertical="t", grow=False)

    pkg.replace_xml(part, root)
    if stem_guid and stem_size:
        _restyle(pkg, part, stem_guid, size=stem_size)
    for guid in items:
        _restyle(pkg, part, guid, size=size)
    for guid in zones:
        _restyle(pkg, part, guid, size=zone_size)
    return {"framed": True, "layout": "drag", "style": look["name"],
            "grid": f"{cols}x{rows}",
            "items": len(items), "zones": len(zones),
            "choice_size": size, "zone_size": zone_size, "stem_size": stem_size}


# --------------------------------------------------------------- metin girisi
#
# UCUNCU ISKELET. Burada ekranda tek bir sey var -- yazilacak kutu -- ve o
# kutunun BUYUK olmasi bir tasarim tercihi degil davet: bir satirlik alan
# "bir kelime yaz" der, dort satirlik alan "dusun ve yaz" der. Olculen bir
# sey degil, ama kararin nerede verildigi kayitli olsun.
TEXT_ENTRY_LINES = 4


def compose_text_frame(pkg: StoryPackage, part: str, *,
                       eyebrow: str | None, palette: dict | None,
                       stem_guid: str | None, entry_guid: str | None,
                       lines: int = TEXT_ENTRY_LINES,
                       style: str | None = None) -> dict:
    """Metin girisi slaydinin cercevesi: ust etiket, kok, yazma kutusu."""
    root = pkg.parse(part)
    shape_list = root.find("shapeLst")
    if shape_list is None:
        return {"framed": False}
    colors = _palette(palette)
    page = _Page(pkg, root, colors)
    width, height = page.width, page.height
    by_guid = {sh.get("g"): sh for sh in shape_list if sh.get("g")}
    entry = by_guid.get(entry_guid or "")
    stem = by_guid.get(stem_guid or "")
    if entry is None:
        return {"framed": False, "reason": "yazma kutusu yok"}
    look = _apply_style(page, colors, style, pkg)

    top = CEILING
    if eyebrow:
        if look["eyebrow_case"] == "title":
            eyebrow = eyebrow.title()
        else:
            eyebrow = eyebrow.upper()
        h = page.text_height(eyebrow, "eyebrow", CONTENT_W)
        page.text(eyebrow, top, role="eyebrow", height=h,
                  color=colors["accent_text"])
        top += h + UNIT * 100 * 0.5

    stem_size = None
    if stem is not None:
        text = model.shape_text(root, stem_guid or "").strip()
        stem_size = page.size_of("lead")
        stem_h = page.text_height(text, "lead", CONTENT_W)
        shapes.set_loc(stem, MARGIN_X / 100 * width, top / 100 * height,
                       (MARGIN_X + CONTENT_W) / 100 * width,
                       (top + stem_h) / 100 * height)
        shapes.set_text_flow(stem, vertical="t", grow=False)
        top += stem_h + UNIT * 100

    # Kutu satir sayisindan buyur ama TABANI asla asmaz; kalan alan
    # yetmiyorsa kutu kalani alir -- kirpilan sey metin degil, davet.
    satir = shapes.layout_text_height("X", TYPE_SCALE["body"],
                                      CONTENT_W / 100 * width,
                                      page.space) / height * 100
    istenen = satir * lines
    kutu_h = min(istenen, max(FLOOR - top, satir))
    shapes.set_loc(entry, MARGIN_X / 100 * width, top / 100 * height,
                   (MARGIN_X + CONTENT_W) / 100 * width,
                   (top + kutu_h) / 100 * height)
    shapes.set_text_flow(entry, vertical="t", grow=False)
    if palette:
        shapes.set_fill(entry, colors["surface"])

    pkg.replace_xml(part, root)
    if stem_guid and stem_size:
        _restyle(pkg, part, stem_guid, size=stem_size)
    _restyle(pkg, part, entry.get("g") or "", size=TYPE_SCALE["body"])
    return {"framed": True, "layout": "text", "style": look["name"],
            "stem_size": stem_size,
            "entry_lines": lines,
            "entry_height_pct": round(kutu_h, 1)}


NULL_GUID = "00000000-0000-0000-0000-000000000000"

# Geri bildirim katmani tasiyan etkilesimler. intrProps HEPSINDE var.
_INTR_ETIKETLERI = ("freePickOneIntr", "freePickManyIntr", "dragDropIntr",
                    "freeHotSpotIntr", "freeTextEntryIntr")


def _rol_sozcugu(metin: str) -> bool:
    """Metin bir ROL etiketi mi ("Dogru", "Yanlis"), yoksa cumle mi.

    Rol etiketi her soruya uyar ve tohumdan geleni ezmek kayiptir; cumle ise
    hasat edildigi kursa aittir ve mutlaka degismelidir. Ayrim ROL
    COZUMLEYICININ kullandigi testin aynisi, bilerek: iki yerde iki farkli
    "dogru sayilir mi" tanimi olsaydi biri digerini yanlislardi.
    """
    d = (metin or "").casefold().strip()
    if not d or len(d) > 24:
        return False
    return any(k in d for k in ("dogru", "doğru", "yanl", "correct", "incorrect"))


def geri_bildirim_rolleri(root) -> dict:
    """katman GUID -> dogru mu (bool). TEK KARAR YERI.

    NICIN BURADA VE TEK: bu soru uc yerde uc ayri sekilde cevaplaniyordu ve
    ucu de eksikti --

        compose_feedback_layers   katman ADINDAN     (pick tohumlarinda ad var)
        compose_drag_feedback     katman METNINDEN   (drag tohumunda ad bos)
        (hicbiri)                 pick-many          <- ikisi de yanlis cevap verir

    freePickMany tohumunda ad BOS ve metin "dogru"/"yanlis" GECMIYOR
    ("Bulamadigin ogeler var" / "Hepsini Buldun"). Ad yolu ikisini de
    "yanlis" sayar; metin yolu `index == 0`a duser ve katman[0]'i DOGRU
    sanir -- oysa olculdu (2026-09-04), intrProps katman[0] icin incFbG
    diyor. Yani sirayla giden her yol o ailede TERS cevap veriyor.

    YETKILI KAYNAK <intrProps>: Storyline'in KENDISI hangi katmani ne zaman
    acacagini oradan okuyor.

        <intrProps corFbG="..." incFbG="..." />

    Cozulmezse ada, o da olmazsa metne, o da olmazsa siraya dusulur --
    hepsi eskiden beri var olan yollar, yalnizca artik ARKA sirada.
    """
    roller: dict = {}
    katman_listesi = root.find("sldLayerLst")
    katmanlar = list(katman_listesi) if katman_listesi is not None else []
    if not katmanlar:
        return roller

    intr = None
    for etiket in _INTR_ETIKETLERI:
        for x in root.iter(etiket):
            intr = x
            break
        if intr is not None:
            break
    props = intr.find("intrProps") if intr is not None else None
    if props is not None:
        for alan, dogru_mu in (("corFbG", True), ("incFbG", False)):
            guid = props.get(alan)
            if guid and guid != NULL_GUID:
                roller[guid] = dogru_mu

    for index, katman in enumerate(katmanlar):
        guid = katman.get("g") or ""
        if guid in roller:
            continue                       # intrProps zaten soyledi
        ad = (katman.get("name") or "").casefold()
        if "yanl" in ad or "incorrect" in ad:
            roller[guid] = False
            continue
        if "dogru" in ad or "doğru" in ad or "correct" in ad:
            roller[guid] = True
            continue
        sekil_listesi = katman.find("shapeLst")
        birlesik = " ".join(
            model.shape_text(katman, sh.get("g") or "").strip()
            for sh in (list(sekil_listesi) if sekil_listesi is not None else [])
        ).casefold()
        if "yanl" in birlesik or "incorrect" in birlesik:
            roller[guid] = False
        elif "dogru" in birlesik or "doğru" in birlesik or "correct" in birlesik:
            roller[guid] = True
        else:
            roller[guid] = index == 0
    return roller


def compose_drag_feedback(pkg: StoryPackage, part: str, *,
                          feedback: dict | None) -> dict:
    """Surukle-birak katmanlarina YAZARIN geri bildirimini yazar.

    NEDEN AYRI BIR FONKSIYON. `compose_feedback_layers` rolu katmanin
    ADINDAN cikariyor ve gerekcesi saglam -- pick tohumlarinda ad var. Ama
    surukle-birak tohumunda katman adlari BOS (olculdu: iki katmanin ikisi
    de name=""), dolayisiyla ikisi de "yanlis" sayiliyor. Ustelik govde
    metni 30 karakterin altinda ("Dogru Eslestirdin!" = 18) ve o esik onu
    PANEL degil BUTON sayiyor, yani hic yeniden yazilmiyor.

    Sonucu olculdu 2026-08-30: feedback={"correct": "Dogru ayirdin.",
    "incorrect": "Sinifi yeniden dusun."} verildi ve uretilen slaytta
    tohumun kendi metni duruyordu. Bu kez tohum metni MASUM -- "Dogru
    Eslestirdin!" her gruplama sorusuna uyar -- ve tam da bu yuzden
    tehlikeli: kusur gorunmuyor, ama sozlesme kirik. Yazar geri bildirim
    veriyor, ogrenci baska bir sey okuyor, hicbir kontrol bagirmiyor.

    Rol SIRADAN degil METINDEN okunur; sira yalnizca yedek. Tohum
    degistirilirse ad yine bos olabilir, ama "Dogru"/"Yanlis" basligi
    katmanin ne oldugunu soyler.
    """
    if not feedback:
        return {"drag_feedback": 0}
    root = pkg.parse(part)
    layers = root.find("sldLayerLst")
    if layers is None:
        return {"drag_feedback": 0}

    # ROL ARTIK BURADA COZULMUYOR: `geri_bildirim_rolleri` tek karar yeri ve
    # yetkili kaynagi (intrProps) kullaniyor. Eski metin/sira sezgisi orada
    # ARKA sirada duruyor, yani drag icin davranis degismiyor.
    roller = geri_bildirim_rolleri(root)

    written = 0
    for index, layer in enumerate(list(layers)):
        shape_list = layer.find("shapeLst")
        texts = [(model.shape_text(layer, sh.get("g") or "").strip(),
                  sh.get("g") or "")
                 for sh in (list(shape_list) if shape_list is not None else [])]
        texts = [(t, g) for t, g in texts if t and g]
        if not texts:
            continue
        is_correct = roller.get(layer.get("g") or "", index == 0)
        given = feedback.get("correct" if is_correct else "incorrect")
        if not given:
            continue
        # Govde = katmanin EN UZUN metni. Baslik ("Dogru") ve buton
        # ("Devam") kisadir; ikisi de korunur, cunku biri rolu soyler
        # digeri tiklanir.
        _uzun, guid = max(texts, key=lambda pair: len(pair[0]))
        set_shape_text(layer, guid, str(given))
        written += 1
    if written:
        pkg.replace_xml(part, root)
    return {"drag_feedback": written}


FEEDBACK_DEFAULT = {
    True:  ("Dogru", "Bu secim, bolumde anlatilan davranisla ortusuyor."),
    False: ("Tekrar dusunelim",
            "Bu secim, bolumde anlatilan davranisla ortusmuyor. "
            "Soru koku yeniden okunmali."),
}


def compose_feedback_layers(pkg: StoryPackage, part: str, *,
                            palette: dict | None,
                            feedback: dict | None = None) -> dict:
    """Geri bildirim katmanlarinin ICINI kurar; kabini korur.

    Katman kabi ve goster/gizle tetikleyicileri klonlanmak zorunda -- elle
    yazilirsa dosya bozulur. Ama ICERIGI tohumdan gelmemeli: hasat edildigi
    kursun metni oradaydi ve HER soruda ayni sey yaziyordu --

        "Dogru Cevap ... Bu mail oltalamadir cunku: ..."

    Musteri iletisimi kursunda oltalama gerekcesi. Ogrenci cevabini verdikten
    sonra okudugu sey, baska bir kursun aciklamasi. Hicbir yapisal kontrol
    bunu goremez: dosya gecerli, katman aciliyor, metin var.

    feedback: {"correct": ..., "incorrect": ...} -- icerikten gelir.
    Verilmezse notr bir varsayilan yazilir. Tohumun metni HICBIR durumda
    kalmaz: yanlis bir aciklama, bos bir aciklamadan kotudur.
    """
    root = pkg.parse(part)
    layers = root.find("sldLayerLst")
    if layers is None:
        return {"layers": 0, "rewritten": 0}
    colors = _palette(palette)
    width, height = shapes.slide_size(root)
    rewritten = 0

    # PUNTOYU MERDIVENE OTURT (2026-08-18, C1).
    #
    # Bu fonksiyon puntoyu HIC AYARLAMIYORDU: dolgu, konum ve metin yaziyor,
    # boyut gomulu tohumdan miras kaliyordu. Olculdu -- uretilen kursta
    # merdiven disi kalan tek yol buydu:
    #
    #     BIZIM   16pt Button x8,  18pt Rectangle x8    <- burasi
    #     TOHUM   14pt Text Box x2, 16pt Text Box x2    <- KULLANICININ, dokunulmaz
    #
    # TYPE_SCALE'in altmis yol kaydinda "compose_question_frame -1" diye
    # gecen alti yoldan besi TYPE_LADDER ile kapanmisti; kalan tek yol bu.
    #
    # ROL ATANMIYOR, MEVCUT PUNTO SNAP EDILIYOR. Rol atamak (mesela "panel
    # body olsun") bir TASARIM karari olurdu ve tohumun kurdugu hiyerarsiyi
    # ezerdi; snap etmek yalnizca "olcegin icine al" der. Kusurun tanimi da
    # buydu: merdiven disi punto.
    #
    # snap hedefleri olculdu: 14->13, 16->17, 18->17 -- ucu de degisiyor,
    # yani duzeltme sessiz kalmiyor (content varyantlarinda uc varyantin
    # ayni imzayi vermesi bu tuzagin son ornegiydi).
    _ebeveyn = model._parent_map(root)

    def _olcege_al(shape):
        """Şeklin BÜTÜN metin gövdelerini merdivene oturtur.

        KIMLIK KARSILASTIRMASI YETMEDI ve olculdu: ilk surum
        `_s is shape` diyordu ve 18pt Rectangle'lari duzeltirken 16pt
        Button'lara HIC dokunmadi. Sebep, butonun metninin DURUM
        GOVDELERINDE yasamasi -- alti durum, alti ayri govde, ve hicbiri
        disariadaki <btn> ile ayni nesne degil.
        `_restyle` bu yuzden ata zinciri yuruyor; ayni yol burada da
        gerekli, ve bir durumu duzeltip besini birakmak yarim is olurdu.
        """
        guid = shape.get("g") or ""
        if not guid:
            return 0
        n = 0
        for _s, el, _d, _st in model._iter_text_shapes(root):
            node = _s
            while node is not None:
                if node.get("g") == guid:
                    break
                node = _ebeveyn.get(node)
            if node is None or not el.text:
                continue
            _c, size, _b, _a = _preview._text_style(_s)
            hedef = snap(size)
            if abs(hedef - size) < 0.01:
                continue
            el.text = shapes.set_text_style(el.text, size=hedef)
            n += 1
        return n

    # ROL: tek karar yerinden. Eski "katman adindan cikar" yolu orada ARKA
    # sirada duruyor, yani adi dolu tohumlarda davranis degismiyor.
    roller = geri_bildirim_rolleri(root)

    olceklenen = 0
    for index, layer in enumerate(layers):
        is_correct = roller.get(layer.get("g") or "", False)
        head, body = FEEDBACK_DEFAULT[is_correct]
        if feedback:
            given = feedback.get("correct" if is_correct else "incorrect")
            if given:
                body = str(given)

        shape_list = layer.find("shapeLst")
        adaylar = []
        for shape in list(shape_list) if shape_list is not None else []:
            rect = shapes.shape_rect(shape)
            if not rect:
                continue
            text = model.shape_text(layer, shape.get("g") or "").strip()
            # Tam boy ince serit: tohumun vurgu cizgisi, kursun rengine.
            if (rect[2] - rect[0]) / width < 0.03:
                if palette:
                    shapes.set_fill(shape, colors["accent"])
                continue
            if not text:
                continue
            adaylar.append((shape, text))

        # SINIFLANDIRMA ETIKETTEN, METIN UZUNLUGUNDAN DEGIL.
        #
        # Eski olcut `len(text) < 30` idi: kisa metinli sekil "buton" sayilip
        # ATLANIYORDU. Olculdu 2026-09-04 -- freePickMany tohumunun basligi
        # "Bulamadigin ogeler var" (22 karakter) ve govdesi tek bir virgul,
        # yani o ailenin HICBIR sekli yeniden yazilmadi ve ogrenci, tohumun
        # hasat edildigi kursun metnini okudu. Ayni kusur drag icin
        # 2026-08-30'da bulunmus ve AYRI BIR FONKSIYON yazilarak cozulmustu
        # (compose_drag_feedback); pick-many o dalin disinda kalmisti.
        #
        # Etiketler Storyline'in KENDI adlari, olculdu:
        #     feedbackTextBox  &Title / Feedback Text   metin
        #     feedBackBtn                               geri bildirim butonu
        #     roundRect / rect                          tek parcali panel
        butonlar = [(s, t) for s, t in adaylar
                    if s.tag in ("feedBackBtn", "btn", "rsltBtn")]
        metinler = [(s, t) for s, t in adaylar if s.tag == "feedbackTextBox"]
        paneller = [(s, t) for s, t in adaylar
                    if s not in [x for x, _ in butonlar + metinler]]

        for shape, _t in butonlar:
            # Metni KORUNUR ("Devam", "Cevaplari Goster"): rolu tiklamak,
            # aciklamak degil.
            if palette:
                shapes.set_fill(shape, colors["accent"])
            olceklenen += _olcege_al(shape)

        if metinler:
            baslik = next((s for s, _t in metinler
                           if (s.get("name") or "") == "&Title"), None)
            govde = next((s for s, _t in metinler if s is not baslik), None)
            if baslik is not None and govde is not None:
                # BASLIK ROL SOZCUGUYSE KORUNUR. Ayrim, rol cozumleyicinin
                # kullandigi testin aynisi: baslik "Dogru"/"Yanlis" gibi bir
                # ROL etiketiyse tohumun yazdigi sey her soruya uyar ve
                # ezmek kayiptir -- olculdu 2026-09-04, drag tohumunun
                # duzgun Turkce "Dogru"/"Yanlis" basligi ASCII varsayilana
                # dusuyordu. Ama freePickMany tohumunun basligi
                # "Bulamadigin ogeler var": bu bir rol etiketi degil, HASAT
                # EDILDIGI KURSUN cumlesi, ve mutlaka degismeli.
                mevcut = model.shape_text(
                    layer, baslik.get("g") or "").strip()
                if not _rol_sozcugu(mevcut):
                    set_shape_text(layer, baslik.get("g") or "", head)
                set_shape_text(layer, govde.get("g") or "", body)
                olceklenen += _olcege_al(baslik) + _olcege_al(govde)
                rewritten += 1
            else:
                # Tek metin kutusu: tohumun DOGRU katmaninda govde sekli yok
                # (olculdu: freePickMany'nin dogru katmani yalnizca &Title
                # tasiyor). Basligi ve govdeyi ayni kutuya yazmak, govdeyi
                # hic yazmamaktan iyi -- yazarin metni ogrenciye ulasir.
                tek = baslik or metinler[0][0]
                set_shape_text(layer, tek.get("g") or "",
                               head + chr(10) + chr(10) + body)
                olceklenen += _olcege_al(tek)
                rewritten += 1

        for shape, text in paneller:
            if len(text) < 30 and not metinler:
                # Etiketsiz kisa metin: eski davranis korunuyor. Bu dal
                # yalnizca taninmayan bir tohum icin calisir.
                if palette:
                    shapes.set_fill(shape, colors["accent"])
                olceklenen += _olcege_al(shape)
                continue
            if len(text) < 30:
                continue
            # Panel: cerceveye oturur, icerigi yeniden yazilir.
            shapes.set_loc(shape,
                           MARGIN_X / 100 * width,
                           (CEILING + 4) / 100 * height,
                           (MARGIN_X + CONTENT_W) / 100 * width,
                           (FLOOR - 12) / 100 * height)
            if palette:
                shapes.set_fill(shape, colors["surface"])
            set_shape_text(layer, shape.get("g") or "",
                           head + chr(10) + chr(10) + body)
            olceklenen += _olcege_al(shape)
            rewritten += 1
    pkg.replace_xml(part, root)
    return {"layers": len(list(layers)), "rewritten": rewritten,
            "olcege_alinan": olceklenen}


# GEOMETRI YAZILAMAZ -- DENENDI, DOSYA ACILMADI.
#
# Bes sikli tohumun siklari <oval>. Tam genislige uzatildiginda okunabilir
# ama "hap" gibi duruyor ve ayni kursta iki sikli tohumun dikdortgen
# butonlariyla yan yana geldiginde kurs iki dilde konusuyor. Cozum olarak
# prstGeom'un cocugu <oval> -> <roundRect> yapildi: sekil klonlanmis halde
# duruyor, yalnizca geometriyi adlandiran cocuk degisiyor, yani "ozellik
# yazmak" gibi gorunuyordu.
#
# KONTROLLU DENEY (2026-08-16). Ayni icerik, tek fark bu degisiklik:
#
#     geom_acik.story    (geometri degistirildi)  ACILMADI
#     geom_kapali.story  (dokunulmadi)            acildi
#     kanarya: saglam=acildi, bozuk=acilmadi  [GUVENILIR]
#
# Negatif sonuc kendi kostugunu kanitliyor: kanarya ayni kosuda gecti ve
# kontrol dosyasi acildi. Yani "acilmadi" sonucu deneyin calismamasindan
# degil, degisikligin kendisinden geliyor.
#
# SONUC: prstGeom'un cocugu, sekil etiketinden BAGIMSIZ olarak yazilamaz.
# Geometri "kabin" parcasi, "ozelligin" degil -- projenin sabit ilkesinin
# siniri tam burada. Bir sik ovalse oval kalir.
#
# BILINEN SINIR: iki tohum iki farkli sik geometrisi tasiyor (oval ve
# button) ve ayni kursta yan yana gelebilirler. Cozumu geometri yazmak
# DEGIL, ovalsiz bir bes sikli tohum bulmak ya da hasat etmek.


def _restyle(pkg: StoryPackage, part: str, guid: str, *, size: float) -> None:
    """Bir şeklin bütün metin gövdelerinin puntosunu değiştirir."""
    root = pkg.parse(part)
    parents = model._parent_map(root)
    for shp, text_el, _doc, _state in model._iter_text_shapes(root):
        node = shp
        while node is not None:
            if node.get("g") == guid:
                text_el.text = shapes.set_text_style(text_el.text or "",
                                                     size=size)
                break
            node = parents.get(node)
    pkg.replace_xml(part, root)


def variety_report(log: list[dict]) -> dict:
    """Ardışık tekrar yasağının kursta nasıl tuttuğunun envanteri.

    Sayı tek başına yanıltıcı. Beş slaytta bir tekrarlanan bir varyant ile iki
    slaytta bir tekrarlanan varyant aynı sayıyı üretir ve gözle taban tabana
    zıt görünür; ilki ritim, ikincisi tekrardır. Bu yüzden kayıt **aralığı**
    da tutar: aynı varyantın iki kullanımı arasında kaç slayt var.

    log: [{"slide": sıra_no, "layout": ..., "variant": ..., "repeated": bool}]

    `repeated`, motorun yasağı çiğnemek zorunda kaldığı yerdir -- düzenin tek
    varyantı varsa ve o da bir öncekinde kullanıldıysa. Karar önceden verildi:
    içerik çeşitlilikten önce gelir, slayt üretilir, çiğneme burada ayrı bir
    kalem olarak görünür. Gerçek yetersizlik (sözlük dar) gürültüye karışmasın
    diye toplam sayıya değil kendi kalemine yazılır.
    """
    used = [e for e in log if e.get("variant")]
    consecutive = [
        (a["slide"], b["slide"], b["variant"])
        for a, b in zip(used, used[1:])
        if a["variant"] == b["variant"] and a["layout"] == b["layout"]
    ]
    seen: dict[str, list[int]] = {}
    for entry in used:
        seen.setdefault(f'{entry["layout"]}/{entry["variant"]}', []).append(entry["slide"])
    gaps: dict[str, list[int]] = {
        key: [b - a for a, b in zip(hits, hits[1:])]
        for key, hits in seen.items() if len(hits) > 1
    }
    every = [g for spread in gaps.values() for g in spread]
    return {
        "slides": len(log),
        "with_variant": len(used),
        "distinct": len(seen),
        "consecutive": consecutive,
        # Yasagi cignemek zorunda kalinan yerler; havuz=1 olan aileler.
        "forced": [e["slide"] for e in log if e.get("repeated")],
        # Ayni varyantin iki kullanimi arasindaki slayt sayisi. En kucugu,
        # gozun "yine ayni sayfa" diyecegi yerdir.
        "gaps": gaps,
        "nearest": min(every) if every else None,
        "no_variant": sorted({e["layout"] for e in log if not e.get("variant")}),
    }


def question_frame(stem: str, space: shapes.Space, *,
                   eyebrow: str | None = None,
                   size: float = TYPE_SCALE["lead"]) -> dict:
    """Çerçevenin yüksekliğini bir kez ölçer ve kalan alanı bildirir.

    "Çerçeve sabit" demek, ölçülmeden önce sabit demek değil -- soru metni
    değişken ve burada ölçülüyor. Sabit olan, bir kez hesaplandıktan sonra bir
    daha değişmemesi: aşağıdan gelen hiçbir şey bu sayıyı yeniden hesaplatmaz.
    Uzun bir kök çerçeveyi büyütür, kalanı daraltır, fit_choices daha çok
    kısar; akış hep aynı yönde.

    Ama sınırsız değil. Yeterince uzun bir kök kalan alanı sıfıra indirir ve o
    noktada "hiçbir şablon uymuyor" demek yanlış teşhistir: sorun şablonda
    değil, metinde. Kataloğa şablon eklemek bu durumu çözmez. Bu yüzden
    kalan alan taban altına düştüğünde nedeni burada işaretlenir.
    """
    slide_w, slide_h = space.slide_w, space.slide_h
    width = CONTENT_W / 100 * slide_w
    band = FLOOR - CEILING

    frame = 0.0
    if eyebrow:
        frame += shapes.layout_text_height(
            eyebrow, TYPE_SCALE["eyebrow"], width, space) / slide_h * 100
        frame += UNIT * 100 * 0.5
    stem_h = shapes.layout_text_height(stem, size, width, space) / slide_h * 100
    frame += stem_h + UNIT * 100

    remaining = band - frame
    # İki şıkın taban punto ve taban boşlukla kapladığı en az alan: bunun
    # altında hiçbir şablonun şansı yok, sebep şablon değil.
    floor_box = shapes.layout_text_height("Wg", MIN_CHOICE_SIZE, width, space)
    minimum = 2 * (floor_box / slide_h * 100) + MIN_CHOICE_GAP

    return {
        "frame_h": frame,
        "stem_h": stem_h,
        "area_h": max(remaining, 0.0),
        "starves": remaining < minimum,
        "minimum": minimum,
        "why": (f"soru koku cerceveyi yedi: kok {stem_h:.1f}%, cerceve "
                f"{frame:.1f}%, {band:.1f}% bandda siklara {max(remaining, 0.0):.1f}% "
                f"kaldi (en az {minimum:.1f}% gerekli) — sablon sorunu degil, "
                f"metin kisaltilmali")
        if remaining < minimum else "",
    }



def style_for(name: str | None, seed: str = "") -> dict:
    """Resolve a style by name, or derive one from the course.

    Derived from a seed rather than chosen at random: the same course rebuilt
    twice looks the same, while two different courses do not.
    """
    if name in STYLES:
        return {"name": name, **STYLES[name]}
    keys = sorted(STYLES)
    picked = keys[sum(ord(c) for c in (seed or "")) % len(keys)] if seed else "rail"
    return {"name": picked, **STYLES[picked]}


def themes() -> dict[str, dict]:
    """themes.json'daki paletler. Zemin türetilmez, seçilir."""
    global _THEMES
    if _THEMES is None:
        raw = json.loads((Path(__file__).with_name("themes.json"))
                         .read_text(encoding="utf-8"))
        _THEMES = {k: v for k, v in raw.items() if not k.startswith("_")}
    return _THEMES


def theme_names() -> list[str]:
    return sorted(themes())


def theme_palette(name: str | None, seed: str = "") -> dict:
    """Bir temayı adıyla getirir, ya da kurstan türetir.

    Kurs adından türetmek rastgele seçmekten farklıdır: aynı kurs her
    yeniden kurulduğunda aynı temayı alır, iki farklı kurs almaz.
    """
    table = themes()
    if name in table:
        picked = name
    else:
        keys = theme_names()
        digest = int(hashlib.sha256((seed or "").encode("utf-8")).hexdigest(), 16)
        picked = keys[digest % len(keys)] if seed else keys[0]
    entry = table[picked]
    out = {k: v for k, v in entry.items() if k in DEFAULT_PALETTE}
    # themes.json accent_text tasimiyor: her tema icin zeminden turetilir,
    # boylece yeni bir tema eklemek bir renk daha yazmayi gerektirmez ve
    # unutuldugunda varsayilan lacivertin vurgusuna dusmez.
    if "accent_text" not in out:
        def rgb(value: str) -> tuple[int, int, int]:
            h = shapes.parse_color(value)
            return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
        # Iki zemin de sayilir: slayt degradeyle boyaniyor ve ust etiket
        # `deep` ucunun uzerine de dusebiliyor.
        grounds = (rgb(out.get("bg", "#000000")),
                   rgb(out.get("deep", out.get("bg", "#000000"))))
        towards = (255, 255, 255) if entry.get("koyu", True) else (0, 0, 0)
        out["accent_text"] = _readable_on(rgb(out.get("accent", "#FFFFFF")),
                                          towards, grounds)
    return {"_theme": picked, **out}


def palette_from(bg: str, accent: str | None = None) -> dict:
    """Seçilen bir zeminden TAM palet. Eksik renk bırakmaz.

    Panel iki renk seçici gösteriyordu (arka plan, vurgu) ve bunları KISMI
    palet olarak geçiyordu: kalan beş renk -- deep, surface, text, muted,
    on_accent -- varsayılan lacivertte kalıyordu. Sonuç ölçüldü: açık bir
    zemin seçildiğinde başlık beyaz kalıyor ve kontrast oranı 1.09'a
    düşüyordu, yani yazı görünmez oluyordu. Orta parlaklıkta iki uyarı.
    Yalnızca koyu lacivert çalışıyordu, o da varsayılanla aynı olduğu için.

    Buradaki kural basit ve ölçülebilir: yazı rengi ZEMİNDEN türetilir, tersi
    değil. Açık zemin koyu yazı ister; bu bir tercih değil, WCAG eşiğinin
    zorunlu kıldığı şey.
    """
    ground = shapes.parse_color(bg)
    r, g, b = (int(ground[i:i + 2], 16) for i in (0, 2, 4))
    # "Koyu mu" sorusu bir PARLAKLIK ESIGIYLE degil, KONTRAST OLCUMUYLE
    # cevaplanir. Once `luminance < 140` yaziliyordu ve orta tonlarda
    # yaniliyordu: #7A8CA3'un parlakligi 138, yani "koyu" sayiliyor ve beyaz
    # yazi aliyordu -- olculdu, 3.44. Ayni zeminde siyah yazi 6.10 veriyor.
    # Esik uydurulmus bir sayiydi; hangi yazinin daha okunur oldugu ise
    # dogrudan olculebilir.
    dark = _contrast((255, 255, 255), (r, g, b)) >= _contrast((22, 24, 29), (r, g, b))

    def mix(c1, c2, t):
        return tuple(round(a + (b_ - a) * t) for a, b_ in zip(c1, c2))

    def hexed(rgb):
        return "#%02X%02X%02X" % tuple(max(0, min(255, v)) for v in rgb)

    base = (r, g, b)
    # deep: zeminin bir tik ilerisi -- koyuda daha koyu, acikta daha koyu ama
    # az, cunku acik bir temada "derin" uc griye kacarsa kirli gorunur.
    deep = mix(base, (0, 0, 0), 0.45 if dark else 0.10)
    surface = mix(base, (255, 255, 255), 0.10) if dark else \
        mix(base, (255, 255, 255), 0.55)
    text = "#FFFFFF" if dark else "#16181D"
    # muted: zeminden yaziya dogru itilir, ta ki KARSILASABILECEGI HER
    # ZEMINDE esigi gecene kadar. Tek zemin (bg) yeterli degil: slayt bir
    # degradeyle boyaniyor ve metin `deep` ucunun uzerine de dusebiliyor.
    # Olculdu -- #7A8CA3 zemininde govde metni bg'ye karsi geciyordu, deep
    # (#6E7E93) ucuna karsi 3.22 veriyordu ve orasi da slaydin yarisi.
    grounds = ((r, g, b), tuple(deep))
    muted = _readable_on(base, (255, 255, 255) if dark else (0, 0, 0), grounds)
    tone = shapes.parse_color(accent) if accent else None
    tone_rgb = tuple(int(tone[i:i + 2], 16) for i in (0, 2, 4)) if tone else (
        (255, 199, 44) if dark else (180, 71, 43))
    accent_lum = (0.2126 * tone_rgb[0] + 0.7152 * tone_rgb[1]
                  + 0.0722 * tone_rgb[2])
    on_accent = "#10141B" if accent_lum > 140 else "#FFFFFF"

    accent_text = _readable_on(tone_rgb, (255, 255, 255) if dark else (0, 0, 0),
                               grounds)
    return {
        "bg": "#" + ground,
        "deep": hexed(deep),
        "surface": hexed(surface),
        "accent": hexed(tone_rgb),
        "accent_text": accent_text,
        "text": text,
        "muted": muted,
        "on_accent": on_accent,
    }


def _readable_on(tone, towards, grounds) -> str:
    """Bir yazı rengini, KARŞILAŞABİLECEĞİ HER zeminde eşiği geçene kadar iter.

    İki ders bir arada:

      Aynı rengi hem dolgu hem yazı yapmak, seçilen tonu yazı olarak okunmaz
      bırakıyordu -- dolgu tarafında hiçbir sorunu olmadığı hâlde. Ölçüldü:
      #B4472B lacivert zeminde dolgu olarak sorunsuz, üst etiket yazısı
      olarak 3.12.

      Ve tek bir zemine göre türetmek yetmiyor: slayt bir degradeyle
      boyanıyor, metin `deep` ucunun üzerine de düşebiliyor ve orası slaydın
      yarısı. Ölçüldü -- bg'ye karşı geçen bir gövde metni deep'e karşı 3.22.

    Hiçbir adımda eşiği geçemezse en iyi adımı döndürür; sessizce başarısız
    olmaz, çağıran palette_warnings ile bunu görebilir.
    """
    best, best_score = tuple(tone), -1.0
    for step in range(14):
        candidate = tuple(round(a + (b - a) * (0.07 * step))
                          for a, b in zip(tone, towards))
        score = min(_contrast(candidate, g) for g in grounds)
        if score > best_score:
            best, best_score = candidate, score
        if score >= 4.5:
            break
    return "#%02X%02X%02X" % tuple(max(0, min(255, v)) for v in best)


def _contrast(fore, back) -> float:
    """WCAG bagil kontrast. contrast.py ile ayni formul, motor tarafinda."""
    def channel(value: int) -> float:
        v = value / 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    def lum(rgb) -> float:
        r, g, b = (channel(c) for c in rgb)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    a, b = sorted((lum(fore), lum(back)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def derive_palette(brand: str, *, dark: bool = True) -> dict:
    """A full palette from one brand colour.

    KULLANMADAN ONCE OKU. Bu, tek bir marka renginden altı renk üretir ve iki
    olculmus kusuru var:

      1. Marka koyu oldugunda cokuyor. Vurgu markanin kendisi, zemin markanin
         %90 siyaha cekilmisi; marka zaten koyuysa ikisi ustuste biner.
         Olculdu -- #0E1B3D icin vurgu/zemin kontrast orani 1.16, yani
         gorunmez yazi. Kurumsal markalarin cogu koyu, yani bu uc durum degil.

      2. Duzeltilse bile temalari birbirine yaklastirir. Dort ayri markadan
         turetilen dort tema, slayt alaninin %98'inde neredeyse ayni siyahi
         kullandi; degisen yalnizca %2'lik vurgu oldu.

    Bu yuzden tercih edilen yol themes.json'dur (bkz. theme_palette): orada
    zemin ayri secilmis bir degerdir, markadan hesaplanmaz. Burasi yalnizca
    "elimde tek bir marka rengi var ve tema listesinde karsiligi yok" durumu
    icin durur.
    """
    value = shapes.parse_color(brand)
    r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))

    def mix(c1, c2, t):
        return tuple(round(a + (b_ - a) * t) for a, b_ in zip(c1, c2))

    def hexed(rgb):
        return "#%02X%02X%02X" % tuple(max(0, min(255, v)) for v in rgb)

    # Ground: the accent dragged far toward near-black, keeping its hue so the
    # background reads as chosen rather than a default grey.
    ground = mix((r, g, b), (8, 10, 18), 0.90) if dark else mix((r, g, b), (252, 252, 255), 0.90)
    surface = mix(ground, (r, g, b), 0.16)
    text = "#FFFFFF" if dark else "#10141B"
    muted = hexed(mix(ground, (255, 255, 255) if dark else (0, 0, 0), 0.62))
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    # The far end of the background gradient. Pulled toward the accent's hue
    # rather than simply darkened, so the wash carries colour instead of
    # looking like a printing fault.
    deep = mix(ground, (r // 2, g // 2, b // 2) if dark else (r, g, b), 0.62)
    grounds = (tuple(ground), tuple(deep))
    towards = (255, 255, 255) if dark else (0, 0, 0)
    return {
        "bg": hexed(ground),
        "deep": hexed(deep),
        "surface": hexed(surface),
        "accent": "#" + value,
        # Bu yol da desteklendigi surece guvenli olmali: vurgu YAZI olarak
        # zeminle cakisabiliyordu ve marka koyuysa bu kacinilmazdi.
        "accent_text": _readable_on((r, g, b), towards, grounds),
        "text": text,
        "muted": _readable_on(tuple(ground), towards, grounds),
        "on_accent": "#10141B" if luminance > 140 else "#FFFFFF",
    }


def _palette(overrides: dict | None) -> dict:
    palette = dict(DEFAULT_PALETTE)
    for key, value in (overrides or {}).items():
        if key in palette and value:
            palette[key] = value
    return palette


def clear_slide(root: ET.Element) -> int:
    shape_list = root.find("shapeLst")
    if shape_list is None:
        return 0
    removed = len(list(shape_list))
    for shape in list(shape_list):
        shape_list.remove(shape)
    return removed


def drop_orphan_submit(root: ET.Element) -> int:
    """Etkileşimi olmayan slayttaki GÖNDER tetikleyicilerini siler.

    OLCULDU (2026-08-17, editorde gozlendi). Uretilen kursun ICERIK
    slaytlarinda Player Triggers soyle goruunuyordu:

        Submit Button
          When the user clicks submit
            Submit [unassigned]        <- kirmizi

    Kaynak: tohumun (bos.story) bes icerik slaydi bu tetikleyiciyi tasiyor
    ve hedefi kendi kursundaki, artik var olmayan bir etkilesim. Klonlandikca
    cogaliyor -- tohumda 5, uretilen kursta 17.

    SILINIYOR, ONARILMIYOR, ve fark olculdu: bu slaytlarda ETKILESIM YOK.
    Onarilacak bir hedef olmadigi icin "yeni etkilesime bagla" anlamsiz;
    dogru cevap, olmayan bir soruyu gondermeye calisan dugmenin kendisini
    kaldirmak. (Soru slaydinda tam tersi gecerli ve orada ONARIM yapiliyor
    -- bkz. authoring.adapt_seeded_slide adim 1b. Ayni nitelik, iki farkli
    dogru cevap; ayirt eden sey slaytta etkilesim olup olmamasi.)

    Elle yapilmis bir kursta bu durum HIC yok: 13 submitG'nin 13'u kendi
    etkilesimine cozuluyor ve etkilesimsiz slaytta submitG bulunmuyor.
    """
    for tag in ("freePickOneIntr", "freePickManyIntr", "dragDropIntr",
                "textEntryIntr", "rsltsIntr"):
        if next(root.iter(tag), None) is not None:
            return 0          # etkilesim VAR: burasi onarim isi, silme degil

    dusen = 0
    for owner in [root] + list(root.iter()):
        trig_list = owner.find("trigLst")
        if trig_list is None:
            continue
        for trig in list(trig_list):
            if any(el.get("submitG") for el in trig.iter()):
                trig_list.remove(trig)
                dusen += 1
    return dusen


class _Page:
    """Places shapes on a slide, in percentages of it."""

    def __init__(self, pkg: StoryPackage, root: ET.Element, palette: dict):
        self.pkg = pkg
        self.root = root
        self.palette = palette
        self.width, self.height = shapes.slide_size(root)
        # UZAY, SAHNEYE KARSI. `self.width` slaydin ILAN ETTIGI koordinat
        # uzayi; Storyline story/story.xml'deki <sz> uzerinde cizer. Ikisi
        # ayrildiginda punto matematigi kayar (bkz. shapes.Space).
        self.space = shapes.space_of(root, shapes.stage_size(pkg))
        # Icerik yogunluguna gore punto olcegi. 1.0 = TYPE_SCALE oldugu gibi.
        self.scale = 1.0

    # ---------------------------------------------------------------- measure

    def size_of(self, role: str) -> float:
        """Rolün puntosu, ölçek uygulanmış hâliyle.

        Ölçek, puntoyu kalibrasyon bandının ÜSTÜNE çıkaramaz. Ölçüldü:
        ölçekleme başlıkları 40-53pt'ye çıkarıyordu ve
        shapes.CALIBRATED_RANGE 13-38. O bandın dışında
        estimate_text_height bir tahmindir, yani ölçeklenen her slaydın
        yerleşim kararı ölçülmemiş bir sayıya dayanırdı -- boşluğu
        doldurmak için doğruluğu harcamak olurdu.

        Bandi genisletmenin yolu acik, yalnizca henuz yurunmedi:
        tools/calibrate_text.py'nin basinda hangi denemenin neden sonuc
        vermedigi yaziyor (Storyline dosyayi hic yazmamisti, iz yok
        demek degil).

        Yani baslik, band 38pt'nin uzerine genisletilene kadar buyumez;
        govde ve ust etiket buyur. Hiyerarsi bir miktar sikisir (38:17
        yerine 38:24) ama olculmemis bir tahmine dayanmaz.
        """
        base = TYPE_SCALE[role]
        if self.scale == 1.0:
            return base
        scaled = min(base * self.scale, max(base, shapes.CALIBRATED_RANGE[1]))
        # Olcek surekli, punto degil: ara deger uretmek olcegi bozar.
        return snap(scaled)

    def text_height(self, content: str, role: str, w: float) -> float:
        """Height a run of text needs, as a percentage of the slide."""
        box_w = w / 100 * self.width
        needed = shapes.layout_text_height(content, self.size_of(role),
                                             box_w, self.space)
        return needed / self.height * 100

    def line_chars(self, role: str, w: float) -> float:
        """Bu puntoda, bu genişlikte bir satıra kaç karakter sığar."""
        box_w = w / 100 * self.width
        # YATAY eksen: olculen carpan (720+1920) formulle ortusuyor,
        # ama kaynagi tasinsin -- olcum yenilenirse burasi takip eder.
        pixels = self.size_of(role) * self.space.h
        return box_w / max(pixels * shapes.CHAR_WIDTH_RATIO, 0.01)

    # ---------------------------------------------------------------- drawing

    def _rect(self, x, y, w, h):
        return (x / 100 * self.width, y / 100 * self.height,
                (x + w) / 100 * self.width, (y + h) / 100 * self.height)

    def _seed(self, tag):
        seed, source = shapes.find_seed(self.pkg, tag)
        shape = shapes.clone_shape(seed, name=tag)
        shapes.set_shape_slide_size(shape, self.width, self.height)
        return shape

    def background(self, color: str, *, to: str | None = None, angle: int = 90) -> None:
        shape = self._seed("rect")
        shape.set("name", "Arka Plan")
        shapes.set_loc(shape, *self._rect(0, 0, 100, 100))
        if to:
            shapes.set_gradient(shape, color, to, angle=angle)
        else:
            shapes.set_fill(shape, color)
        shapes.add_shape(self.root, shape, to_back=True)
        _apply_text(self.root, shape, "")

    def band(self, x, y, w, h, color, *, name="Blok", rounded=False,
             alpha=None) -> None:
        shape = self._seed("roundRect" if rounded else "rect")
        shape.set("name", name)
        shapes.set_fill(shape, color, alpha=alpha)
        shapes.set_loc(shape, *self._rect(x, y, w, h))
        shapes.add_shape(self.root, shape)
        _apply_text(self.root, shape, "")

    def scrim(self, x, y, w, h, color, *, alpha=0.72, fade=False,
              angle=90, name="Ortu") -> None:
        """A translucent panel, for laying text over a picture."""
        shape = self._seed("rect")
        shape.set("name", name)
        shapes.set_scrim(shape, color, alpha=alpha, fade=fade, angle=angle)
        shapes.set_loc(shape, *self._rect(x, y, w, h))
        shapes.add_shape(self.root, shape)
        _apply_text(self.root, shape, "")

    def text(self, content, y, *, role="body", color=None, align="l",
             x=MARGIN_X, w=CONTENT_W, bold=None, height=None,
             bottom=FLOOR) -> float:
        """Place text at an absolute y. Returns the height it took.

        Kept inside the frame here rather than trusted to each layout: a block
        that starts above the top edge or runs past the bottom is invisible in
        the finished course, and invisible to an overlap check too, since a box
        off the slide overlaps nothing.
        """
        size = self.size_of(role)
        natural = self.text_height(content, role, w)
        y = max(y, 1.5)
        room = height if height is not None else natural
        # Tavan, cagiranin verdigi bandin tabani -- FLOOR degil.
        #
        # FLOOR'a kirpmak, buton icin ayrilmis bandi gormezden gelir: bandin
        # altina yakin oturan bir blok, kendi olculen yuksekligiyle butonun
        # icine uzanir. Olculdu -- bir slaytta govde metni "Devam" butonuyla
        # %30 x %8 ortustu, ve bunu ne overlap kontrolu ne de tasma
        # invaryanti gordu; rubrik gordu.
        room = min(room, max(bottom - y, 4.0))

        # Step the type down until the words fit the room they were given.
        # Clamping the box alone only hides the problem: the box stops at the
        # limit and the text keeps going, straight across whatever is below it.
        # Kucultmenin tabani KALIBRE BANDIN alt ucu, 10 degil.
        #
        # Once 10'a kadar iniyordu ve bu, olculmemis bir sabiti olculmus gibi
        # kullanmakti: 13pt altinda estimate_text_height bir tahmin, yani
        # kucultulen metnin sigip sigmadigina dair karar, dogrulanmamis bir
        # sayiya dayaniyordu. Olculdu -- uretilen bir kursta bir govde 10pt'ye
        # inmisti (%4 yuksekliginde bir banda sikismis 30 karakter) ve hicbir
        # kontrol bagirmadi, cunku "tasma yok": metin kuculmustu.
        #
        # Taban konunca tasma GORUNUR hale gelir ve invariants.check_text_fits
        # onu yakalar. Gorunur bir basarisizlik, sessiz bir tahminden iyidir.
        floor = shapes.CALIBRATED_RANGE[0]
        box_w = w / 100 * self.width
        while natural > room + FIT_TOLERANCE and size > floor:
            nxt = step_down(size, floor)
            if nxt >= size:
                break
            size = nxt
            natural = (shapes.layout_text_height(content, size, box_w, self.space)
                       / self.height * 100)
        h = max(min(natural, room), 3.0)
        shape = self._seed("textBox")
        shape.set("name", role.capitalize())
        shapes.set_loc(shape, *self._rect(x, y, w, h))
        shapes.set_text_flow(shape, vertical="t", grow=True)
        shapes.add_shape(self.root, shape)
        _apply_text(self.root, shape, content,
                    color=color or self.palette["text"], size=size,
                    bold=bold if bold is not None else role in ("title", "display", "numeral"),
                    align=align)
        return h


def density_scale(page: _Page, parts: list[tuple[str, str, float]],
                  band: float) -> float:
    """Seyrek içerikte punto ölçeğini yukarı çeker.

    Ölçüldü: maddesiz slaytlarda bandın %26-%54'ü boş kalıyordu, maddeli
    slaytlarda %0-%26. Sebep yerleşim değil, ölçek: altı kelimelik bir gövde
    17 punto ile yazıldığında 16:9 bir çerçevenin yarısını dolduramaz ve
    layout boşluğu büyütür. Bir tasarımcı bu durumda yazıyı büyütür.

    İki tavan var ve ikisi de gerekli:

      MAX_TYPE_SCALE  punto sinirsiz buyuyemez -- uc kelimelik bir govde
                      afise donusur ve kurs icindeki diger slaytlarla ayni
                      sesi tasimaz.
      MIN_LINE_CHARS  SATIR UZUNLUGU. Sabit genislikte puntoyu buyutmek
                      satirdaki karakter sayisini DUSURUR; kirk karakterin
                      altina inen bir olcu, her satirda goz atlatir ve
                      "buyuk ama okunmaz" uretir. Bu taban olmadan olcek
                      bosluk doldurmak icin okunabilirligi harcar.

    Bandin tamamini doldurmaya calismaz: TARGET_FILL'in ustu sikisik gorunur
    ve nefes payi tasarimin parcasi. Hedef "boslugu bitirmek" degil, "boslugu
    kasitli hale getirmek".
    """
    if not parts or band <= 0:
        return 1.0
    base = page.scale
    best = base

    # SEYREKTE BUYUTUR, YOGUNDA KUCULTUR -- IKINCI YARI YOKTU.
    #
    # Olculdu (2026-08-19, `section` dali, 62 harflik baslik): bloklar
    # %253.7 isterken bu fonksiyon 1.000 dondu. Yani "yerlesim yogunlugunu
    # ayarlayan" olcu, YOGUN icerikte hic calismiyordu; yalnizca seyrekte.
    # Sonuc: `_distribute` yuksekligi kisiyor, kisma tabani (0.35) bandi
    # asiyor ve son blok bandin DISINA dusuyor (%85.5, bant %78'de bitiyor).
    #
    # Kucultmenin tabani UYDURULMAZ: en kucuk rolun puntosu kalibre bandin
    # alt ucune (13pt) inince durur. Altinda `estimate_text_height` bir
    # tahmin, yani kucultulen metnin sigip sigmadigina dair karar
    # dogrulanmamis bir sayiya dayanirdi.
    def _kullanilan() -> float:
        return sum(page.text_height(text, role, width)
                   for role, text, width in parts)             + UNIT * 100 * (len(parts) - 1)

    if _kullanilan() > band:
        # TABAN AKAN METINDEN GELIR, en kucuk rolden DEGIL.
        #
        # Ilk surum tabani `min(size_of(role))` ile hesapladi ve HIC
        # KOSMADI: `eyebrow` merdivende zaten 11pt, yani kalibre bandin
        # (13pt) ALTINDA ve bilerek oyle -- o bir etiket, okunan metin
        # degil. 13/11 = 1.18 > 1.0 cikinca dongu bastan yanlisti.
        #
        # Kalibre band OKUNAN metin icin olculdu; tabani okunan rollerden
        # almak gerekir. Zaten bandin altinda baslayan bir rol, olcegi
        # kilitlemez.
        okunan = [page.size_of(role) for role, _t, _w in parts
                  if page.size_of(role) >= shapes.CALIBRATED_RANGE[0]]
        taban_olcek = (shapes.CALIBRATED_RANGE[0] / min(okunan)
                       if okunan else 0.5)
        try:
            olcek = base
            while olcek > taban_olcek:
                # ILERLEME YOKSA DUR. `round(...,2)` tabani yukari
                # yuvarlayabiliyor (0.619 -> 0.62) ve o zaman olcek hic
                # kucultmeden donguye geri giriyor: SONSUZ DONGU olculdu,
                # tur 300 saniyede bitmedi. Depo ayni guard'i `step_down`
                # cagirilarinda zaten kullaniyor: `if nxt >= size: break`.
                yeni = round(max(olcek - 0.05, taban_olcek), 2)
                if yeni >= olcek:
                    page.scale = yeni
                    best = yeni
                    break
                page.scale = yeni
                best = yeni
                if _kullanilan() <= band:
                    break
                olcek = yeni
        finally:
            page.scale = base
        return best

    try:
        scale = base
        while scale < MAX_TYPE_SCALE:
            page.scale = round(scale + 0.05, 2)
            if any(page.line_chars(role, width) < MIN_LINE_CHARS
                   for role, _text, width in parts if role in FLOWING):
                break
            used = sum(page.text_height(text, role, width)
                       for role, text, width in parts)
            used += UNIT * 100 * (len(parts) - 1)
            best = page.scale
            if used >= band * TARGET_FILL:
                break
            scale = page.scale
    finally:
        page.scale = base
    return best


def _distribute(blocks: list[float], top: float, bottom: float,
                *, mode: str = "spread") -> list[float]:
    """Vertical positions for a set of block heights within a band.

    spread -- gaps shared evenly, so the group reaches both edges
    centre -- natural gaps, group centred
    top    -- natural gaps from the top
    """
    span = bottom - top

    # BLOKLARIN KENDISI SIGMIYORSA, PAYLARINI KIS.
    #
    # Bosluk kismak ancak bosluk varken ise yarar. Bloklarin toplami bandi
    # sifir boslukla bile asiyorsa yapilacak tek sey bloklari kucultmektir --
    # aksi halde sonuncusu bandin disina cikar ve page.text onu 4 birimlik bir
    # kutuya sikistirip biraktigi yerde birakir. Olculdu: bloklar [5.0, 26.7,
    # 12.6] = 44.3, band 29; ucuncu blok %82.8'de basladi, band tabani %80'di,
    # ve %82.5'ten baslayan butona girdi.
    #
    # Bu adim `cover` dalinda VARDI, `content` dalinda yoktu. O yuzden artik
    # burada: her cagiran ayni kurali kendi eliyle yazmak zorunda kalirsa,
    # biri yazmayi unutur -- ve bu ucuncu kez oldu.
    total = sum(blocks)
    if total > span and total > 0:
        share = max((span - UNIT * 100 * 0.4 * max(len(blocks) - 1, 0)) / total,
                    0.35)
        blocks = [b * share for b in blocks]
        total = sum(blocks)

    if mode == "spread" and len(blocks) > 1:
        gap = max((span - total) / (len(blocks) - 1), UNIT * 100 * 0.6)
    else:
        gap = UNIT * 100 * 1.1
    used = total + gap * (len(blocks) - 1)

    # Bant bir siniirdir, bir oneri degil. Sabit bosluklu kipler (top, centre)
    # bloklari bandin ASAGISINA tasirabiliyordu ve yukseklik kirpmasi bunu
    # duzeltmez -- y zaten disarida. Olculdu: govde metni bandin tabani %80
    # iken %83.5'te basladi ve %82.5'ten baslayan butona girdi.
    #
    # Once bosluk kisilir, sonra grup yukari cekilir. Bloklarin kendisi banda
    # sigmiyorsa (total > span) baslangic tavana oturur ve puntoyu text()
    # kucultur; o durumda tasma yerine kucultme olur, ki dogru sira budur.
    if used > span and len(blocks) > 1:
        gap = max((span - total) / (len(blocks) - 1), 0.0)
        used = total + gap * (len(blocks) - 1)
    start = top if mode in ("top", "spread") else top + max((span - used) / 2, 0)
    if start + used > bottom:
        start = max(top, bottom - used)

    positions, y = [], start
    for h in blocks:
        positions.append(y)
        y += h + gap
    # Kisilmis yukseklikler de doner: cagiran eski yuksekliklerle cizerse
    # bloklar yine tasar ve kisma hicbir sey yapmamis olur.
    return positions, blocks


def compose_slide(
    pkg: StoryPackage,
    slide: str,
    layout: str = "content",
    *,
    title: str | None = None,
    eyebrow: str | None = None,
    body: str | None = None,
    bullets: list[str] | None = None,
    buttons: list[str] | None = None,
    palette: dict | None = None,
    index: str | None = None,
    image_area: bool = False,
    image_style: str = "panel",
    style: str | None = None,
    clear: bool = True,
    identity: str | None = None,
    variant: str | None = None,
    avoid_variant: str | list[str] | None = None,
    theme: str | None = None,
    motion: str | None = None,
) -> dict:
    """Lay out a whole slide in one pass.

    layout: cover | section | content | bullets | steps | statement | menu
    index:  a section number or step label, where the layout shows one
    image_area: reserve space for a picture
    image_style: how that space is shaped --
        panel  a rounded card in the right-hand column
        bleed  a full-height slab running off the right edge, text on the left
        hero   the whole slide, with a wash so the words stay readable
    identity: names the course, so the deck draws its button from one donor
        and keeps to it. Pass the same value for every slide of a course.
    variant: the skeleton within the layout -- where the text column sits, how
        wide it runs, where the call to action leans. Left unset it is derived
        from the slide's own text, so a rebuild repeats.
    avoid_variant: the previous slide's variant, or the whole run of them with
        the most recent last. Two neighbours sharing a variant share a
        silhouette, which is what reads as a template applied twice. Passing
        the run rather than one name also widens the gap between reuses, which
        is the part a repeat count cannot see. Where a layout has only one
        variant this cannot be honoured; the result then carries repeated=True
        instead of failing.
    motion: the reveal choreography -- sakin | anlatim | vurgulu, or None for
        none. Applied LAST, after the buttons, because it reads the finished
        shapeLst: the order shapes were placed in is the order they enter.
        Left unset a slide has no timeline at all -- every object at start=0,
        every animEffect empty, which is what every produced course carried
        (measured 2026-09-04: 360 shapes, 0 animations). See anim.py.
    """
    if layout not in LAYOUTS:
        raise StoryError(f"Bilinmeyen duzen: {layout!r}. Secenekler: {', '.join(LAYOUTS)}")
    if image_style not in IMAGE_STYLES:
        raise StoryError(f"Bilinmeyen gorsel yerlesimi: {image_style!r}. "
                         f"Secenekler: {', '.join(IMAGE_STYLES)}")

    part = pkg.slide_part_for(slide)
    root = pkg.parse(part)
    # Tema, acikca verilen bir palete YENIK dusmez sirasi tersine de olmaz:
    # palette daha ozeldir ve verildiginde temayi ezer. Ikisi de yoksa
    # varsayilan kalir -- yani "tema secilmedi" sessizce "gece" demek degil.
    if palette is None and theme:
        palette = {k: v for k, v in theme_palette(theme).items()
                   if not k.startswith("_")}
    colors = _palette(palette)
    removed = clear_slide(root) if clear else 0
    # Tohumdan devralinan OLU gonder tetikleyicisi. Sekiller silinince
    # tetikleyici de anlamsiz kaliyor ama trigLst'te duruyordu ve editorde
    # "Submit unassigned" olarak goruunuyordu (olculdu).
    oksuz = drop_orphan_submit(root)

    look = style_for(style, seed=(title or "") + layout[:1])
    shape_var = variant_for(layout, name=variant,
                            seed=(title or "") + (body or "")[:12],
                            avoid=avoid_variant)
    page = _Page(pkg, root, colors)
    kind, angle = look.get("ground", ("flat", 0))
    # A cover carries the strongest wash; interior slides keep it quieter so
    # the deck does not read as a run of title screens.
    if kind == "grad" and colors.get("deep"):
        page.background(colors["bg"], to=colors["deep"],
                        angle=angle if layout in ("cover", "section", "statement") else 90)
    else:
        page.background(colors["bg"])
    _mark(page, look, colors, layout)
    if eyebrow and look["eyebrow_case"] == "title":
        eyebrow = eyebrow.title()
    button_specs: list[dict] = []
    reserved: dict | None = None

    if layout == "cover":
        # Anchored low. The accent is whatever the style places; a second block
        # of its own would double the mark on every cover.
        text_w = CONTENT_W
        if image_area and image_style == "hero":
            # The picture becomes the slide. A wash rising from the bottom edge
            # keeps the headline legible without flattening the whole image --
            # the picture is added afterwards with behind=True, under this.
            reserved = {"x": 0, "y": 0, "w": 100, "h": 100, "behind": True}
            page.scrim(0, 0, 100, 100, colors["bg"], alpha=0.30, name="Ton")
            page.scrim(0, 38, 100, 62, colors["bg"], alpha=0.88,
                       fade=True, angle=270, name="Ortu")
        elif image_area and image_style == "bleed":
            # Off the right edge, full height: the frame stops being a box and
            # starts being an edge, which is most of what "designed" looks like.
            text_w = CONTENT_W * 0.52
            reserved = {"x": 52, "y": 0, "w": 48, "h": 100}
            page.scrim(52, 0, 48, 100, colors["surface"], alpha=1.0, name="Gorsel Alani")

        blocks, parts = [], []
        if eyebrow:
            h = page.text_height(eyebrow.upper(), "eyebrow", text_w)
            blocks.append(h); parts.append(("eyebrow", eyebrow.upper(), h))
        h = page.text_height(title or "Baslik", "display", text_w * 0.86)
        blocks.append(h); parts.append(("display", title or "Baslik", h))
        if body:
            h = page.text_height(body, "lead", text_w * 0.62)
            blocks.append(h); parts.append(("lead", body, h))
        # The band a button occupies plus clearance above it. A last line whose
        # descenders reach into the button reads as a mistake even though the
        # boxes technically clear each other.
        bottom = FLOOR - (18 if buttons else 0)
        needed = sum(blocks) + UNIT * 100 * len(blocks)
        top = max(bottom - needed, CEILING + 4)
        # Eksigi paylastirma adimi burada DEGIL, _distribute'ta: her dal
        # kendi kopyasini tasidiginda biri unutuyor ve bloklar bandin disina
        # cikiyor. Burada bir kez vardi, content dalinda yoktu.
        ys, blocks = _distribute(blocks, top, bottom, mode="top")
        for (role, content, _measured), y, h in zip(parts, ys, blocks):
            page.text(content, y, role=role, height=h,
                      w=text_w * (0.86 if role == "display" else
                                  0.62 if role == "lead" else 1.0),
                      color=colors["accent_text"] if role == "eyebrow" else
                            colors["muted"] if role == "lead" else colors["text"])
        button_specs = _buttons(buttons, y=FLOOR - 9.5, fill=colors["accent"],
                                color=colors["on_accent"],
                                space=page.space)

    elif layout == "section":
        # A divider earns its slide by being nearly empty: a large index, a
        # title, and air. Centred, because there is nothing to read past.
        # SUTUN VARYANTIN KARARI, sabitin degil. Once her sey MARGIN_X'ten
        # aciliyordu ve dort section slaydi TEK imza uretiyordu.
        s_x, s_w = shape_var.get("text", (MARGIN_X, CONTENT_W))

        # OLCEK ONCE, BLOKLAR SONRA -- `content` dali bunu zaten yapiyordu,
        # bu dal YAPMIYORDU.
        #
        # Olculdu (2026-08-19, 62 harflik baslik + uzun govde): `display`
        # blogu %206.2 istedi. `_distribute` paylari kisti ama kisma
        # TABANI (0.35) bandi asiyor: 253.7 * 0.35 = %88.8 > %66 bant. Son
        # blok bandin DISINA, %85.5'e dustu ve `page.text` odayi 6.5'e
        # kirpti -- govde 2.6 kat tasti.
        #
        # Yani burada da bir TABAN ile bir BANT carpisti ve taban sessizce
        # kazandi. Cozum ayni: bloklari olcmeden ONCE puntoyu bulmak, ki
        # kisma yuksekligi degil PUNTOYU kissin.
        _bant = (FLOOR - 14) - (CEILING + 4)
        _spec = ([("numeral", index, 20.0)] if index
                 else [("eyebrow", eyebrow.upper(), CONTENT_W)] if eyebrow
                 else [])             + [("display", title or "Bolum", s_w * 0.95)]             + ([("lead", body, s_w * 0.83)] if body else [])
        page.scale = density_scale(page, _spec, _bant)

        blocks, parts = [], []
        if index:
            h = page.text_height(index, "numeral", 20)
            blocks.append(h); parts.append(("numeral", index, h, 20))
        elif eyebrow:
            h = page.text_height(eyebrow.upper(), "eyebrow", CONTENT_W)
            blocks.append(h); parts.append(("eyebrow", eyebrow.upper(), h, CONTENT_W))
        h = page.text_height(title or "Bolum", "display", s_w * 0.95)
        blocks.append(h); parts.append(("display", title or "Bolum", h, s_w * 0.95))
        if body:
            h = page.text_height(body, "lead", s_w * 0.83)
            blocks.append(h); parts.append(("lead", body, h, s_w * 0.83))
        # The rule closes the slide from below the text band, not inside it:
        # placed at the floor it ended up drawn behind the last line.
        ys, blocks = _distribute(blocks, CEILING + 4, FLOOR - 14, mode="centre")
        for (role, content, _measured, w), y, h in zip(parts, ys, blocks):
            page.text(content, y, role=role, height=h, w=w, x=s_x,
                      color=colors["accent_text"] if role in ("numeral", "eyebrow")
                            else colors["muted"] if role == "lead" else colors["text"])
        page.band(shape_var.get("cizgi_x", MARGIN_X), FLOOR + 2.5, 18, 0.7,
                  colors["accent"], name="Cizgi")

    elif layout == "content":
        # Two columns when there is something to put beside the text. The
        # panel is not decoration: it is where a picture goes, and reserving
        # it keeps the text measure readable instead of running the full width.
        #
        # Where that column sits is the variant's decision, not a constant's.
        # A picture overrides it: once an image bleeds off an edge, the text has
        # one place left to go and pretending otherwise puts words under it.
        bleed = image_area and not bullets and image_style in ("bleed", "hero")
        text_x, text_w = shape_var["text"]
        panel = shape_var["panel"]
        if bleed:
            # Full-height slab off the right edge. Bullets still get the card
            # panel, because cards need a margin to read as cards.
            page.scrim(54, 0, 46, 100, colors["surface"], alpha=1.0,
                       name="Gorsel Alani")
            reserved = {"x": 54, "y": 0, "w": 46, "h": 100}
            text_x, text_w = MARGIN_X, CONTENT_W * 0.44
        elif panel and (image_area or bullets):
            px, pw = panel
            reserved = {"x": px, "y": CEILING + 4, "w": pw,
                        "h": FLOOR - CEILING - 8}
            page.band(px, reserved["y"], pw, reserved["h"],
                      colors["surface"], name="Panel", rounded=True)

        ceiling = CEILING + 4
        if shape_var.get("head") == "band" and not bleed:
            # The heading leaves the column and becomes a full-bleed strip.
            # This is the axis the first four variants were missing: they all
            # moved the text column sideways, and sideways only ever produces
            # a shift or a mirror of the same picture. A band changes which
            # block dominates and where the slide's weight sits.
            head_h = page.text_height(title or "Baslik", "title", CONTENT_W)
            if eyebrow:
                head_h += page.text_height(eyebrow.upper(), "eyebrow", CONTENT_W)
            strip = head_h + UNIT * 100 * 1.6
            page.band(0, 0, 100, strip, colors["surface"], name="Serit")
            y = UNIT * 100 * 0.7
            if eyebrow:
                y += page.text(eyebrow.upper(), y, role="eyebrow", x=MARGIN_X,
                               w=CONTENT_W, color=colors["accent_text"])
            page.text(title or "Baslik", y, role="title", x=MARGIN_X,
                      w=CONTENT_W, color=colors["text"])
            ceiling = strip + UNIT * 100
            title, eyebrow = None, None

        bottom = FLOOR - (12 if buttons else 0)
        # Olcek, bloklar olculmeden ONCE belirlenir: bloklarin yuksekligi
        # olcege bagli, dolayisiyla once olcegi bul sonra olc. Kartlar
        # olcege girmez -- kendi taban yukseklikleri var ve punto onlari
        # buyutmez, yalnizca metnin sigacagi alani daraltir.
        spec = ([("eyebrow", eyebrow.upper(), text_w)] if eyebrow else []) \
            + ([("title", title, text_w)] if title else []) \
            + ([("body", body, text_w)] if body else [])
        room = bottom - ceiling
        if bullets and not reserved:
            # Sayi _card_band'den: iki yerde hesaplanan bir sayi ayrisir.
            _rows, _band = _card_band(page, bullets, text_w)
            room -= min(_band, room * 0.62)
        page.scale = density_scale(page, spec, room)

        blocks, parts = [], []
        for role, content, width in spec:
            h = page.text_height(content, role, width)
            blocks.append(h); parts.append((role, content, h))
        text_bottom, text_top, cards_area = bottom, ceiling, reserved
        if bullets and not reserved:
            # No panel in this variant: the points sit under the text. Their
            # band is taken out of the frame *before* the text is distributed,
            # not left over afterwards -- text spread across the whole band and
            # cards given the remainder collapses them into unreadable strips,
            # which is what the first look showed.
            _rows, _band = _card_band(page, bullets, text_w)
            # SUTUN DAR MI? `bullets` dalinda bu kosullu genislétme VAR,
            # bu dalda YOKTU. Olculdu (2026-08-19): %34.6 genisliginde bir
            # kart sutununda 60 harflik madde 116 birim istiyor, kutu 48 --
            # 2.4 kat. Tam genislikte ayni madde cok daha az satira sarar.
            #
            # Kosullu: yalnizca OLCUM dar dediginde ve gorsel icin ayrilmis
            # bir alan yokken (`not reserved`) genisletilir; aksi halde
            # varyantin sutun karari korunur.
            if _band > (bottom - ceiling) * 0.62 and text_w < CONTENT_W:
                _r2, _b2 = _card_band(page, bullets, CONTENT_W)
                if _b2 < _band:
                    text_x, text_w = MARGIN_X, CONTENT_W
                    _rows, _band = _r2, _b2
            need = min(_band, (bottom - ceiling) * 0.62)
            # Kart bandi ayri tutulur: `reserved` disariya "gorsel buraya"
            # diye bildirilir ve kartlarla dolu bir bandi oyle bildirmek,
            # cagirani resmi kartlarin ustune koymaya davet eder.
            if shape_var.get("order") == "reverse":
                # Points first, heading at the floor. Reading order is a
                # structural axis too: the same blocks in the other sequence
                # cannot be reached by shifting or mirroring the first one.
                cards_area = {"x": text_x, "y": ceiling, "w": text_w, "h": need}
                text_top = ceiling + need + CARD_GAP
            else:
                cards_area = {"x": text_x, "y": bottom - need,
                              "w": text_w, "h": need}
                text_bottom = bottom - need - CARD_GAP
        ys, blocks = _distribute(blocks, text_top, text_bottom,
                                 mode=shape_var["band"])
        align = "c" if shape_var["cta"] == "centre" else "l"
        # Kisilmis yukseklikle cizilir. Olculen yukseklikle cizilseydi kisma
        # hicbir sey yapmazdi -- konum duzelir, kutu yine tasardi.
        for (role, content, _measured), y, h in zip(parts, ys, blocks):
            page.text(content, y, role=role, height=h, x=text_x, w=text_w,
                      align=align, bottom=text_bottom,
                      color=colors["accent_text"] if role == "eyebrow"
                            else colors["muted"] if role == "body" else colors["text"])
        if bullets and cards_area:
            _cards(page, bullets, cards_area, colors)
            if cards_area is reserved:
                # AYRILAN ALAN KARTLARA GITTI, disariya "gorsel buraya" diye
                # bildirilemez. Bildiriliyordu: donen image_area kartlarin
                # bandiydi ve prompt "donen image_area'yi aynen add_image'e
                # gecir" diyor -- yani resim maddelerin ustune konurdu.
                # Yirmi satir yukarida ayni tuzak kartlarin KENDI dalinda
                # yaziliyla isaretlenmis, ama donusu kimse duzeltmemis.
                reserved = None
        button_specs = _buttons(buttons, y=FLOOR - 9.5, fill=colors["accent"],
                                color=colors["on_accent"],
                                x=text_x, w_avail=text_w,
                                anchor=shape_var["cta"], space=page.space)

    elif layout == "bullets":
        # Cards, not dots. Each point gets a surface of its own, which reads as
        # a set of things rather than a list that ran out of page.
        _b_x, _b_w = shape_var.get("text", (MARGIN_X, CONTENT_W))
        head = []
        if eyebrow:
            head.append(("eyebrow", eyebrow.upper(),
                         page.text_height(eyebrow.upper(), "eyebrow", _b_w)))
        head.append(("title", title or "Baslik",
                     page.text_height(title or "Baslik", "title", _b_w)))
        # BASLIK SUTUNU ve KART ALANI varyantin karari. Ikisi de MARGIN_X'e
        # cakiliydi ve dort bullets slaydi TEK imza uretiyordu.
        b_x, b_w = shape_var.get("text", (MARGIN_X, CONTENT_W))
        k_x, k_w = shape_var.get("kart", (MARGIN_X, CONTENT_W))
        bottom = FLOOR - (12 if buttons else 0)
        head_top = CEILING + 2
        frame = bottom - head_top

        # KART BANDI BASLIKTAN ONCE AYRILIR.
        #
        # Eski hali basligi ONCE yaziyor, kartlara KALANI veriyordu. Olculdu
        # (2026-08-19, uretilen kursta slide3): %40 genisliginde bir sutuna
        # yazilan uzun bir baslik %52.8 yukseklik aldi, kartlara %19.8 kaldi,
        # bes kart 2.2'ye bolundu -- MIN_CARD_H'nin %20'si. Yirmi govde
        # yazisi medyan 4.3 kat tasti (en kotu 5.7). Daha uzun bir baslikta
        # `bottom - top` NEGATIF olculdu: -27.2.
        #
        # Ayni kural `content` dalinda da `cover` dalinda da ZATEN VARDI, bu
        # dalda yoktu. _distribute'un yorumu bunun ucuncu tekrari oldugunu
        # yaziyor; bu DORDUNCUSU. O yuzden sayi artik _card_band'de, tek
        # yerde.
        rows, band = _card_band(page, bullets or [], k_w)

        # SUTUN DAR MI? Varyantin dar kart sutunu gorsel cesitlilik icin
        # secilmisti (C3). Ama olcum dar sutunda maddeyi 3 satira, tam
        # genislikte 2 satira sardigini soyluyor. Tasarim tercihi ancak
        # icerik siginca tercihtir; sigmiyorsa kusurdur. Kosullu: yalnizca
        # OLCUM dar dediginde tam genislige gecilir, aksi halde varyant
        # kararina dokunulmaz.
        if band > frame * 0.72 and k_w < CONTENT_W:
            genis_x, genis_w = MARGIN_X, CONTENT_W
            _r2, band2 = _card_band(page, bullets or [], genis_w)
            if band2 < band:
                k_x, k_w, rows, band = genis_x, genis_w, _r2, band2

        # Tavan kartlarin cerceveyi tumuyle yutmasini engeller. Bu dalda
        # kartlar ASIL ICERIK, baslik ikincil -- o yuzden pay basligin degil
        # kartlarin lehine (content dalindaki 0.62 orada dogru, burada degil).
        need = min(band, frame * 0.78) if rows else 0.0
        head_bottom = bottom - need - (CARD_GAP if need else 0.0)

        # BASLIK BANDININ TABANI. Kart bandini once ayirmak basligi kisiyordu
        # ve olculdu (ayni tur): uc EYEBROW 1.2 kat tasti -- YENI bir kusur,
        # duzeltmenin kendi urettigi. Sebep: eyebrow puntosu zaten kalibre
        # bandin ALTINDA, yani page.text onu kucultemez (while size > floor
        # bastan yanlis). Kucultulemeyen bir bloktan pay kismak, tasmayi
        # garanti etmektir.
        #
        # Taban: kucultulemeyen bloklar kendi dogal yuksekligini korur,
        # baslik en az BIR SATIR alir. Farki kartlar geri verir.
        head_min = sum(h for role, _c, h in head if role != "title")
        if any(role == "title" for role, _c, _h in head):
            head_min += page.text_height("X", "title", b_w)
        if head_bottom < head_top + head_min:
            head_bottom = min(head_top + head_min, bottom - MIN_CARD_H)
            need = max(bottom - head_bottom - CARD_GAP, 0.0)

        # PAY YALNIZCA KUCULEBILEN BLOKTAN KISILIR.
        #
        # Ilk sürüm basligi _distribute'a veriyordu ve o "sigmiyorsa paylari
        # kis" kuralini ORANTILI uyguluyor -- eyebrow dahil. Olculdu: eyebrow
        # 11pt, 14 karakter, tek satir 19.6 birim istiyor, kutusu 16.2'ye
        # dustu ve UC EYEBROW tasti. Eyebrow kalibre tabanin (13pt) ALTINDA,
        # yani page.text'in kucultme dongusu ona hic girmez; kucultulemeyen
        # bir bloktan pay kismak tasmayi GARANTI eder.
        #
        # Dolayisiyla: kucultulemeyen bloklar dogal yuksekligini korur,
        # sikisma tek kucultulebilir bloga -- basliga -- biner. Baslik 21pt,
        # 13pt'ye kadar inebilir; inemedigi yerde GORUNUR bicimde tasar.
        y = head_top
        for role, content, h in head:
            if role == "title":
                continue
            page.text(content, y, role=role, height=h, x=b_x, w=b_w,
                      bottom=head_bottom, color=colors["accent_text"])
            y += h + UNIT * 100 * 0.7
        for role, content, h in head:
            if role != "title":
                continue
            page.text(content, y, role=role, height=min(h, max(head_bottom - y, 0.0)),
                      x=b_x, w=b_w, bottom=head_bottom, color=colors["text"])
            y += min(h, max(head_bottom - y, 0.0)) + UNIT * 100 * 0.7
        # Kartlar basligin HEMEN ALTINDAN baslar, ayrilan bandin tabanindan
        # degil. Tabana yaslamak olculdu ve `coverage` kapisini dusurdu:
        # bullets'ta bos alan %10'dan %38'e cikti -- tasmayi cozerken
        # BOSLUK uretmek. Rezervasyon zaten `bottom - head_bottom >= need`
        # garantisini veriyor, dolayisiyla basligin altindan baslamak
        # kartlara need KADAR VEYA DAHA COK verir ve kalan yeri doldurur.
        top = y - UNIT * 100 * 0.7 + UNIT * 100 * 0.6
        if rows:
            # Baslik kendi bandini asarsa (13pt tabanda bile sigmadi) yine de
            # kartlarin ayrilmis bandina girmesine izin verilmez.
            top = min(top, bottom - need)
        _cards(page, bullets or [], {"x": k_x, "y": top, "w": k_w,
                                     "h": max(bottom - top, 0.0)}, colors)
        button_specs = _buttons(buttons, y=FLOOR - 9.5, fill=colors["accent"],
                                color=colors["on_accent"],
                                space=page.space)

    elif layout == "steps":
        # A sequence, numbered because the order carries meaning here.
        # ADIM BANDI BASLIKTAN ONCE AYRILIR.
        #
        # Eski hali basligi ONCE ve SINIRSIZ yaziyor, adimlara KALANI
        # bolüyordu (`slot = (bottom - top) / len(items)`). Olculdu
        # (2026-08-19, uzun baslik + bes uzun madde): kutu %3.0 (16 birim),
        # metin 46 istiyor -- 2.9 kat.
        #
        # Ayni kural content, cover, bullets, menu, _buttons ve soru
        # cercevesinde ya vardi ya bu oturumda konuldu. Bu SEKIZINCISI (K25).
        bottom = FLOOR - (12 if buttons else 0)
        items = bullets or []
        head_top = CEILING + 2
        _slot, _band = _yigin_bandi(page, items, CONTENT_W - 7.5, pay=0.7)
        # Baslik en az BIR SATIR alir; gerisi adimlarin.
        if _band:
            _bas_min = page.text_height("X", "title", CONTENT_W)
            _band = min(_band, max(bottom - head_top - _bas_min - UNIT * 100,
                                   0.0))
            _slot = _band / len(items)
        head_bottom = bottom - _band - (UNIT * 100 if _band else 0.0)
        head_h = page.text_height(title or "Adimlar", "title", CONTENT_W)
        head_h = min(head_h, max(head_bottom - head_top, 0.0))
        page.text(title or "Adimlar", head_top, role="title", height=head_h,
                  bottom=head_bottom)
        top = min(head_top + head_h + UNIT * 100, bottom - _band)
        if items:
            # OLCULEN YUVA BIR TABAN, DEGER DEGIL. Yalnizca `_slot`
            # kullanmak bandi doldurmayi birakiyor ve olculdu: `coverage`
            # steps'te bos alan %24'ten %30'a cikti -- tasmayi cozerken
            # BOSLUK uretmek. (Ayni gerileme kart bandinda da olmustu.)
            slot = max(_slot, (bottom - top) / len(items))
            for i, item in enumerate(items):
                y = top + i * slot
                page.band(MARGIN_X, y, 5.5, slot * 0.62, colors["accent"],
                          name="Numara", rounded=True)
                page.text(str(i + 1), y + slot * 0.12, role="lead", w=5.5,
                          x=MARGIN_X, align="c", color=colors["on_accent"])
                page.text(item, y + slot * 0.08, role="body",
                          x=MARGIN_X + 7.5, w=CONTENT_W - 7.5,
                          height=slot * 0.7, color=colors["text"])
        button_specs = _buttons(buttons, y=FLOOR - 9.5, fill=colors["accent"],
                                color=colors["on_accent"],
                                space=page.space)

    elif layout == "statement":
        # One idea, large, with room around it. Used where a slide exists to
        # be remembered rather than read.
        #
        # UC BILESIM, UC SILUET. Bu duzen bir donem tek imzaliydi ve o zaman
        # zarars1zdi cunku neredeyse hic kullanilmiyordu. Ayrac kapisi onu
        # sik kullanilan bir duzen yaptigi anda tek imza bir kusura donustu.
        content = body or title or "…"
        bicim = shape_var.get("bicim", "vurgu")
        tx, tw = shape_var.get("text", (MARGIN_X + 4, CONTENT_W * 0.74))
        hiza = shape_var.get("hiza", "l")
        if bicim == "serit":
            # Yatay slab: agirlik slaydin ortasinda ve TAM GENISLIKTE.
            h = page.text_height(content, "subtitle", tw)
            serit_h = min(h + UNIT * 100 * 2.4, FLOOR - CEILING)
            serit_y = max((100 - serit_h) / 2, CEILING)
            page.band(0, serit_y, 100, serit_h, colors["surface"], name="Serit")
            page.text(content, serit_y + UNIT * 100 * 1.2, role="subtitle",
                      x=tx, w=tw, height=h, align=hiza, bold=False,
                      bottom=serit_y + serit_h)
            if title and body:
                page.text(title, min(serit_y + serit_h + UNIT * 100 * 0.8,
                                     FLOOR - 4),
                          role="eyebrow", x=tx, w=tw, align=hiza,
                          color=colors["accent_text"])
        else:
            if bicim == "vurgu":
                page.band(MARGIN_X, CEILING + 8, 0.8, FLOOR - CEILING - 16,
                          colors["accent"], name="Vurgu")
            h = page.text_height(content, "subtitle", tw)
            page.text(content, max((100 - h) / 2, CEILING), role="subtitle",
                      x=tx, w=tw, height=h, align=hiza, bold=False)
            if title and body:
                page.text(title, FLOOR - 6, role="eyebrow", x=tx, w=tw,
                          align=hiza, color=colors["accent_text"])

    elif layout in ("menu", "reveal"):
        # Choices are the content: the buttons get the room, not the copy.
        # BUTON BANDI BASLIKTAN ONCE AYRILIR.
        #
        # Bu dalin kendi yorumu zaten "Choices are the content: the buttons
        # get the room, not the copy" diyor -- ama kod basligi ONCE ve
        # SINIRSIZ yaziyordu. Olculdu (2026-08-19, geri cekilme menusu):
        # soru koku baslik rolunde %65.9 yukseklik aldi, butonlara %12.5
        # kaldi ve dort butonluk yigin %103.3'te bitti.
        #
        # Ayni kural `content`, `cover` ve (bu oturumda) `bullets`
        # dallarinda var. Bu BESINCISI. Sayi artik _button_band'de, tek
        # yerde: sira mi yigin mi karari da oradan okunuyor, cunku band
        # ayirmak o karari bilmeyi gerektiriyor.
        _b_each, _b_need = _button_band(buttons or [], w_avail=CONTENT_W,
                                        space=page.space)
        _b_head_bottom = FLOOR - _b_need - (UNIT * 100 if _b_need else 0.0)
        y = CEILING + 2
        h = page.text_height(title or "Secim yapin", "title", CONTENT_W)
        h = min(h, max(_b_head_bottom - y, 0.0))
        page.text(title or "Secim yapin", y, role="title", height=h,
                  bottom=_b_head_bottom)
        y += h + UNIT * 100 * 0.6
        if body:
            bh = page.text_height(body, "body", CONTENT_W * 0.8)
            page.text(body, y, role="body", height=bh, w=CONTENT_W * 0.8,
                      color=colors["muted"])
            y += bh + UNIT * 100
        # The choices are the slide, so they take the band -- not a fifth of
        # it with the rest left over.
        #
        # Ortalamak yetmiyordu: bandin %42'sini kaplayan bir sira, ortaya
        # konuldugunda olu alani yok etmez, IKIYE BOLER. Olculdu -- menu
        # slaydinin %40-55 ve %80-92 araliklari bostu, ikisi de butonun
        # ustunde ve altinda kalan yarim bosluklar. Toplam %45 ile en kotu
        # content vakasi kadar.
        #
        # Ama bandi butonla DOLDURMAK cozum degildi: %34'e cikarilan bir sira,
        # bakildiginda buton gibi degil bos panel gibi duruyor -- tek kelimelik
        # bir etiket, yuksekliginin dortte birini bile kullanmiyor. Olcu
        # iyilesti (%45 -> %29), tasarim bozuldu; sayiyi hedef sanmak buydu.
        #
        # Menude bosluk kusur DEGIL. Kusur, boslugun IKIYE BOLUNMESIYDI:
        # butonun ustunde %15, altinda %12, ve grup havada duruyor gibi
        # okunuyor. Asagida TOPLANAN bosluk "sayfa bitti" demektir ve bu
        # normaldir. O yuzden buton buton kalir, grup metnin altina yaslanir,
        # ve artan alan tek parca halde altta birikir.
        # Bant ayrilmis olani ASMAZ: baslik kisildiktan sonra bile yigin
        # kendi bandinda baslar.
        band_top, band_bottom = min(y + 2, FLOOR - _b_need), FLOOR
        height = min(max((band_bottom - band_top) * 0.42, 11.0), 20.0)
        button_specs = _buttons(buttons, y=band_top + UNIT * 100,
                                fill=colors["surface"], color=colors["text"],
                                height=height, space=page.space,
                                bottom=FLOOR)

    pkg.replace_xml(part, root)

    from .authoring import add_button
    placed = []
    for spec in button_specs:
        result = add_button(
            pkg, slide, spec["text"], x=spec["x"], y=spec["y"],
            w=spec["w"], h=spec["h"], fill=spec["fill"], color=spec["color"],
            avoid_overlap=False, identity=identity, slot=spec.get("slot"),
        )
        # GUID DE DONUYOR: reveal katmani butona `open_from` ile
        # baglaniyor ve metinle eslestirme guvenilir degil (iki sik
        # ayni kelimeyle baslayabilir).
        placed.append({"text": result["text"], "box": result["box_percent"],
                       "shape": result.get("shape", "")})

    # Kurgu EN SONDA: butonlar add_button ile eklendi ve parcayi yeniden
    # yazdi, yani buradan once okunan bir shapeLst butonsuz olurdu -- ve
    # butonsuz bir kademelenme, slaydin son vurusunu kaybeder.
    choreography = None
    if motion:
        from . import anim
        choreography = anim.choreograph(pkg, slide, preset=motion)

    return {
        "slide": slide,
        "layout": layout,
        "variant": shape_var["name"],
        "variant_repeated": shape_var["repeated"],
        "variant_pool": shape_var["pool"],
        "cleared_shapes": removed,
        "palette": colors,
        "buttons": placed,
        "image_area": reserved,
        "image_style": image_style if reserved else None,
        "motion": choreography,
    }


def _mark(page: _Page, look: dict, colors: dict, layout: str) -> None:
    """The recurring accent, placed where this style puts it."""
    mark = look["mark"]
    if mark == "rail":
        page.band(0, 0, 0.7, 100, colors["accent"], name="Vurgu")
    elif mark == "corner":
        page.band(0, 0, 34, 5.5, colors["accent"], name="Kose")
    elif mark == "band":
        page.band(0, 96.5, 100, 3.5, colors["accent"], name="Serit")


def _columns(items: list[str], width: float) -> int:
    """Two columns once there are four or more: a single column of six cards is
    a list again, and leaves half the slide empty.

    Split out because the band that reserves room for the cards and the code
    that draws them have to agree on the row count. Two copies of this rule
    drift, and the drift shows up as cards that overrun the band they were
    measured into.
    """
    return 2 if len(items) >= 4 and width > 45 else 1


def _yigin_bandi(page: _Page, items: list[str], width: float, *,
                 pay: float = 1.0, taban: float = 0.0,
                 bosluk: float = 0.0) -> tuple[float, float]:
    """Tek sütunlu bir yığının OLÇULEN bandı: (öğe başına %, toplam %).

    `pay` -- kutunun ne kadari metne ayriliyor (steps'te slot*0.7).
    `taban` -- alt sinir; DEGER degil, yalnizca alt sinir.

    Olcek OVERRIDE EDILMEZ: cagiran hangi olcekte ciziyorsa o olcekte
    olculur. `_card_band` scale'i 1.0'a cekiyor cunku `_cards` de oyle
    ciziyor; buradaki cagiranlar cekmiyor. Olcum ile cizimin ayri puntodan
    konusmasi bu depoda daha once olcuulmus bir kusur.
    """
    if not items:
        return 0.0, 0.0
    gereken = max(page.text_height(str(item), "body", width) for item in items)
    her = max(gereken / pay if pay else gereken, taban)
    return her, len(items) * her + bosluk * (len(items) - 1)


def _card_band(page: _Page, items: list[str], width: float) -> tuple[int, float]:
    """Kart bandinin OLCULEN yuksekligi: (satir, toplam yukseklik).

    TEK YETKILI. Rezervasyon ile cizim ayni sayiyi buradan okur; iki yerde
    hesaplanirsa ayrisirlar ve fark yuvarlama degil KESIT olur.

    Onceki rezervasyon `rows * MIN_CARD_H` idi -- yani SABIT, metni hic
    sormayan bir sayi. MIN_CARD_H bir TABAN, ama deger olarak kullaniliyordu.
    Bu fonksiyon onun yerine metni olcer ve tabani yalnizca ALT SINIR olarak
    kullanir.

    Olcum scale 1.0'da yapilir cunku _cards de oyle ciziyor (kart etiketi
    olcege girmez). Baska bir olcekte olcmek, cizilenden baska bir sayi verir.
    """
    if not items:
        return 0, 0.0
    columns = _columns(items, width)
    rows = -(-len(items) // columns)
    card_w = (width - CARD_GAP * (columns - 1)) / columns
    scale = page.scale
    page.scale = 1.0
    try:
        # _cards metni x+3.2, w=card_w-5 ile yaziyor; ayni genislikle olc.
        need = max(page.text_height(it, "body", card_w - 5) for it in items)
    finally:
        page.scale = scale
    # Kutunun %70'i metne ayriliyor (_cards: height=card_h*0.7).
    card_h = max(need / 0.7, MIN_CARD_H)
    return rows, rows * card_h + (rows - 1) * CARD_GAP


def _cards(page: _Page, items: list[str], area: dict, colors: dict) -> None:
    """Lay items out as surfaces filling the given area."""
    if not items:
        return
    columns = _columns(items, area["w"])
    rows = -(-len(items) // columns)
    gap = CARD_GAP
    # Kart etiketi olcege GIRMEZ. Bant hesabi zaten oyle yapiyor (kartlarin
    # kendi taban yuksekligi var), ama etiket page.text uzerinden yaziliyordu
    # ve o self.scale'i uyguluyordu -- yani kart 17pt'ye gore olculup 18pt'yle
    # yazilyordu. Bir birim tasma, ve kucultme tabani konulana kadar gorunmez
    # kaldi: metin sessizce kuculuyordu.
    scale = page.scale
    page.scale = 1.0
    card_w = (area["w"] - gap * (columns - 1)) / columns
    card_h = (area["h"] - gap * (rows - 1)) / rows

    for i, item in enumerate(items):
        col, row = i % columns, i // columns
        x = area["x"] + col * (card_w + gap)
        y = area["y"] + row * (card_h + gap)
        page.band(x, y, card_w, card_h, colors["surface"], name="Kart", rounded=True)
        page.band(x, y, 0.7, card_h, colors["accent"], name="Kenar")
        page.text(item, y + card_h * 0.18, role="body", x=x + 3.2,
                  w=card_w - 5, height=card_h * 0.7,
                  bottom=y + card_h, color=colors["text"])
    page.scale = scale


# Yigin kutusunun TABANI. `_buttons` icinde ciplak 4.0 olarak duruyordu ve
# menu dali rezervasyonu ondan okuyamiyordu -- okuyamayinca da bandi buton
# sayisindan degil sabit bir yuzdeden ayirdi ve yigin slayttan tasti.
BUTTON_STACK_MIN_H = 4.0
BUTTON_STACK_GAP = 1.6


def _buttons_stacked(labels, *, w_avail, space) -> bool:
    """Sıra mı yığın mı -- TEK YETKILI.

    Karar `_buttons`in icinde gomuluydu ve disaridan sorulamiyordu. Bandi
    ayirmasi gereken cagiran, yigin mi kurulacagini BILMEDEN ayiramaz:
    yigin n kutu, sira tek kutu. Iki yerde ayri ayri karar verilirse
    ayrisirlar (K25).
    """
    if not labels:
        return False
    count = len(labels)
    gap = 2.5
    width = min((w_avail - gap * (count - 1)) / count, 30.0)
    uzay = shapes._space(space)
    per_px = 16.0 * uzay.h * shapes.CHAR_WIDTH_RATIO
    row_chars = int((width / 100 * uzay.slide_w) / per_px)
    return max(len(str(label)) for label in labels) > row_chars


# Sekil marji: `height_for_label` (sekli ve kendi marjlarini okur) ile
# `measured_text_height` (sekilsiz) arasindaki fark, GERCEK buton
# sekillerinde olculdu (2026-08-19, uretilen menu slaydi, 720x540):
#     1 satir : 23.2 -> 28.4   (+5.2 birim = %0.96)
#     2 satir : 46.4 -> 52.7   (+6.3 birim = %1.17)
# Sabit DEGIL, satirla hafif artiyor. Rezervasyon UST degeri kullanir: az
# ayirmak tasma uretir, cok ayirmak bosluk -- ve bosluk geri alinabilir.
#
# Neden dogrudan `height_for_label` cagrilmiyor: rezervasyon aninda buton
# SEKLI HENUZ YOK (`add_button` onu sonra klonluyor). O yuzden sekilsiz
# olcum + OLCULEN marj. Fark buyurse burasi yeniden olculmeli.
BUTTON_LABEL_MARGIN = 1.2      # slayt yuksekliginin yuzdesi


def _button_band(labels, *, w_avail, space, height=9.0) -> tuple[float, float]:
    """(her butonun yuksekligi %, toplam bant %) -- TEK YETKILI.

    Onceki hali `n * BUTTON_STACK_MIN_H` idi: yani TABANI deger olarak
    kullaniyordu ve metni hic sormuyordu. Olculdu (2026-08-19): buton
    kutusu %4.0, etiket %8.5 istiyordu -- 2.1 kat. MIN_CARD_H ile ayni
    hastalik; taban bir ALT SINIR, deger degil.

    Punto TABANDAN olculur: `add_button` 15pt'ten baslayip kalibre tabana
    kadar kuculuyor, yani tabanda sigan bir kutu HER ZAMAN sigar.
    """
    if not labels:
        return 0.0, 0.0
    if not _buttons_stacked(labels, w_avail=w_avail, space=space):
        return height, height
    uzay = shapes._space(space)
    n = len(labels)
    w_units = w_avail / 100 * uzay.slide_w
    gereken = max(shapes.measured_text_height(str(label),
                                              shapes.CALIBRATED_RANGE[0],
                                              w_units, uzay)
                  for label in labels)
    each = gereken / uzay.slide_h * 100 + BUTTON_LABEL_MARGIN
    each = max(each, BUTTON_STACK_MIN_H)
    return each, n * each + (n - 1) * BUTTON_STACK_GAP


def _buttons(labels, *, y, fill, color, height=9.0, x=MARGIN_X,
             w_avail=CONTENT_W, anchor="left", space=None,
             bottom=FLOOR) -> list[dict]:
    """Butonları yerleştirir -- ve etiket uzunsa SIRA yerine YIĞIN kurar.

    Buton her slaytta sol alt köşede duruyordu, çünkü başlangıcı sabitti.
    Yaslama burada verilir; grubun toplam genişliği ölçülür, sonra banda göre
    kaydırılır.

    SIRA MI YIGIN MI, karar metnin uzunlugundan gelir. Olculdu, 16pt ve
    %84 icerik genisliginde:

        sik   buton g%   satir basi karakter
         2      30.0            18
         3      26.3            16
         4      19.1            11
         5      14.8             9
        tek sutun (tam genislik)  52

    MIN_LINE_CHARS 22 -- yani YATAY SIRA HICBIR SIK SAYISINDA cumle
    tasiyamaz. Bir soru sikki cumledir; "Sakin bir sesle, bu tur ifadelerle
    gorusmeye devam edemeyecegini soyler" 71 karakter ve dort butona
    bolundugunde her satira 11 karakter dusuyor. Storyline'da acildiginda
    etiketlerin alti kesilmis halde goruldu.

    Kural: en uzun etiket sira genisliginde TEK SATIRA sigmiyorsa sira
    yanlistir; siklar tam genislikte alt alta dizilir. Kisa etiketler
    ("Devam", "Konu A") sirada kalir -- orada sira dogru bicim.
    """
    if not labels:
        return []
    count = len(labels)
    gap = 2.5
    width = min((w_avail - gap * (count - 1)) / count, 30.0)

    uzay = shapes._space(space)
    if _buttons_stacked(labels, w_avail=w_avail, space=space):
        # YIGIN: tam genislik, alt alta, banda sigacak yukseklikte.
        stack_gap = BUTTON_STACK_GAP
        # OLCULEN yukseklik, sabit degil -- rezervasyonu yapan da ayni
        # sayiyi buradan okur, yani yuva ile bant AYRISAMAZ.
        each, toplam = _button_band(labels, w_avail=w_avail, space=space,
                                    height=height)
        # TABAN BANDI ASAMAZ. `max(each, 4.0)` kosulsuzdu ve banda
        # bakmiyordu: olculdu (2026-08-19), dort buton y=%82.5'ten
        # basladi, her biri %4.0 oldu ve yigin %103.3'te bitti -- yani
        # SLAYTIN DISINDA. Taban ile bant carpistiginda once yigin YUKARI
        # kayar; taban ancak yukari kayacak yer kalmadiginda esner.
        if y + toplam > bottom:
            y = max(bottom - toplam, CEILING)
        if y + toplam > bottom:
            # Yukari kayacak yer de yok: kutu kisilir. Gorunur bir kucultme,
            # slayt disina tasan bir yigindan iyidir.
            each = max((bottom - y - stack_gap * (count - 1)) / count, 2.0)
        return [{"text": label, "x": x, "y": y + i * (each + stack_gap),
                 "w": w_avail, "h": each, "fill": fill, "color": color,
                 # Buyume KENDI yuvasinda kalir. Yoksa uzun etiketli bir sik
                 # asagi uzar ve bir sonrakinin uzerine biner -- yigin bunu
                 # cozmek icin kuruldu, cozdugunu sanip geri getirmesin.
                 "slot": (y + i * (each + stack_gap),
                          y + i * (each + stack_gap) + each)}
                for i, label in enumerate(labels)]
    span = count * width + gap * (count - 1)
    start = {"left": x, "right": x + w_avail - span,
             "centre": x + (w_avail - span) / 2}.get(anchor, x)
    y = min(y, FLOOR - height)
    return [{"text": label, "x": start + i * (width + gap), "y": y,
             "w": width, "h": height, "fill": fill, "color": color}
            for i, label in enumerate(labels)]


# ------------------------------------------------------- okunabilirlik ortusu


def ensure_scrim(pkg: StoryPackage, slide: str, *, palette: dict | None = None,
                 alpha: float = 0.32, band_alpha: float = 0.82) -> dict:
    """Tam sayfa bir gorselin ustune yazi okunacaksa, arasina ortu koy.

    NICIN MOTORDA, NICIN HER SEFERINDE. Gorsel kursa uc ayri yoldan giriyor:
    kurucu (kapak icin alan ayirir ve ortuyu kendi cizer), komut yolundaki ajan,
    ve panelin "Gorsel & Video" sekmesi. Okunabilirligi yalnizca ilki
    garantiliyordu; olculdu 2026-08-29 (denee.story, slide2): slaytta ortu HIC
    yoktu, fotograf tam sayfa oturdu ve beyaz baslik aydinlik bir ofis
    fotografinin uzerinde okunamaz hale geldi. Kullanicinin bildirdigi kusur
    buydu ve "bu modul icin degil, gelecekte de duzgun olmali" dedi.

    Iki katman konur:
      Ton   tam sayfa, hafif (varsayilan %32) -- fotografi butun olarak yatistirir
      Serit yazi blogunun arkasi, guclu (%82) ve yazinin OLMADIGI yone dogru
            soner. Yon yaziya gore secilir: baslik ustteyse asagi, alttaysa
            yukari soner. Sabit bir alt gradyan, ustte duran bir basligi
            kurtarmiyordu.

    Zaten bir ortu varsa dokunulmaz: iki kat ortu fotografi camurlastirir.
    """
    part = pkg.slide_part_for(slide)
    root = pkg.parse(part)
    shape_list = root.find("shapeLst")
    if shape_list is None:
        return {"slide": slide, "eklendi": False, "sebep": "sekil listesi yok"}
    width, height = shapes.slide_size(root)

    sekiller = list(shape_list)
    resim, resim_i = None, -1
    for i, s in enumerate(sekiller):
        if s.tag != "pic":
            continue
        kutu = shapes.shape_rect(s)
        if kutu and (kutu[2] - kutu[0]) >= width * 0.9 and (kutu[3] - kutu[1]) >= height * 0.9:
            resim, resim_i = s, i
    if resim is None:
        return {"slide": slide, "eklendi": False, "sebep": "tam sayfa gorsel yok"}

    ustunde = sekiller[resim_i + 1:]
    if any(shapes._saydam_dolgu(s) for s in ustunde):
        return {"slide": slide, "eklendi": False, "sebep": "ortu zaten var"}

    yazilar = [s for s in ustunde if s.tag == "textBox" and shapes.shape_rect(s)]
    if not yazilar:
        return {"slide": slide, "eklendi": False, "sebep": "gorselin ustunde yazi yok"}

    ust = min(shapes.shape_rect(s)[1] for s in yazilar)
    alt = max(shapes.shape_rect(s)[3] for s in yazilar)
    colors = _palette(palette)
    zemin = colors["bg"]

    def yeni_rect(ad: str, x, y, w, h, a, fade, angle):
        tohum, _ = shapes.find_seed(pkg, "rect")
        sekil = shapes.clone_shape(tohum, name=ad)
        shapes.set_shape_slide_size(sekil, width, height)
        shapes.set_scrim(sekil, zemin, alpha=a, fade=fade, angle=angle)
        shapes.set_loc(sekil, x / 100 * width, y / 100 * height,
                       (x + w) / 100 * width, (y + h) / 100 * height)
        _apply_text(root, sekil, "")
        return sekil

    # Yazi ust yaridaysa serit yukaridan baslar ve asagi soner; alt yaridaysa
    # tersi. Olcu yazinin KENDI yerinden geliyor, sabit bir banttan degil.
    orta = (ust + alt) / 2 / height * 100
    if orta < 50:
        y0, yh, angle = 0.0, min(alt / height * 100 + 8, 100.0), 90
    else:
        y0 = max(ust / height * 100 - 8, 0.0)
        yh, angle = 100.0 - y0, 270

    ton = yeni_rect("Ton", 0, 0, 100, 100, alpha, False, 90)
    serit = yeni_rect("Ortu", 0, y0, 100, yh, band_alpha, True, angle)
    shape_list.insert(resim_i + 1, ton)
    shape_list.insert(resim_i + 2, serit)
    for i, s in enumerate(shape_list):
        s.set("zOrder", str(i))
    pkg.replace_xml(part, root)
    return {"slide": slide, "eklendi": True,
            "ton": {"alpha": alpha}, "serit": {"y": round(y0, 1),
                                               "h": round(yh, 1), "angle": angle}}
