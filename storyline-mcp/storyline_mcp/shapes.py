"""Shape-level authoring: new text boxes, buttons and backgrounds.

The same reasoning that governs slides governs shapes. Storyline has no
schema for "a text box at these coordinates in this colour" -- a shape carries
a timeline context, states, a fill stack and a geometry preset, all wired by
GUID. So shapes are created the way slides are: copy a real one out of the
project, regenerate the GUIDs it defines, then set geometry, text and colour.

That makes the project its own parts bin. A course with no button in it cannot
grow one here, and the tools say so rather than inventing a shape that Storyline
may reject.

Two things vary per project and must be read, never assumed:

  * Slide size. Shapes carry <sldSz>, and it differs between decks -- 720x540
    in one of this user's courses, 1920x1080 in another. Coordinates are
    absolute within that space, so a hardcoded position lands off-slide.
  * Colour. Fills are <solidFill><srgbClr val="RRGGBB"/></solidFill>, but
    theme-driven shapes use <schemeClr val="accent6"/> instead; replacing the
    whole fill slot avoids leaving both in place.
"""

from __future__ import annotations

import re
import warnings
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import NamedTuple

from . import donors
from .clone import _defined_guids, _remap_guids, new_guid
from .model import slide_index
from .package import StoryPackage, StoryError

FILL_TAGS = ("noFill", "solidFill", "gradFill", "gradOvrlyFill", "picFill", "patFill")
# Only these occupy the fill slot at the head of <bG>. gradOvrlyFill is a
# separate overlay that sits later in the sequence and must not be displaced.
FILL_SLOT_TAGS = ("noFill", "solidFill", "gradFill", "picFill", "patFill")
DEFAULT_SLIDE_SIZE = (720.0, 540.0)
# Average glyph width as a fraction of the point size, used to work out how
# many characters fit on a line.
#
# GECMIS (kayit icin): 0.52 -> 0.72 -> 0.79. 0.52, on bes karakterin sigdigini
# iddia ediyordu ve tek satir olculen bir baslik iki satir cizilip govdesi
# uzerine biniyordu. 0.72, 38pt'de gozle sayilmis 8-12 karakterlik bir banttan
# secilmisti -- tek punto, tek metin.
CHAR_WIDTH_RATIO = 0.79
#
# OLCULDU (2026-08-16, Storyline Preview, 12pt, 300 birimlik kutu, sert satir
# sonu YOK). Uc metin, cunku font ORANTILI ve tek metinden cikan oran o
# metnin harf dagilimina ozgudur:
#
#     notr Turkce duzyazi   127 harf -> 4 satir -> 31.8 kar/satir -> 0.79
#     dar harf (illiti...)  118 harf -> 2 satir -> 59.0 kar/satir -> 0.42
#     genis harf (mumwow..)  83 harf -> 4 satir -> 20.8 kar/satir -> 1.20
#
# Yani gercek oran 0.42-1.20 bandinda geziniyor ve TEK BIR SAYI onu temsil
# edemez. 0.79, uretim icerigine en yakin olan duzyazi olcumudur.
#
# Eski deger 0.72'ydi ve duzyaziya gore %9 DAR sayiyordu -- yani satira fazla
# karakter sigdirip satir sayisini AZ veriyordu. Guvensiz yon: kutu metinden
# kisa cikar, blok komsusunun uzerine biner.
#
# Satir sayisi KUANTALI oldugu icin bandin tamamini bir carpanla kapatmak
# MUMKUN DEGIL: uc satirlik bir kutuda bir satirlik sapma %33'tur. Oran
# duzyaziya gore secilir; sentetik uclardaki iskalama bilinen sinirdir.

# KALIBRASYON BANDI. 38pt'de 300 birimde gercek kapasite 8-12 karakter; 13pt'de
# ayni kutuda alti ornegin hepsi 29 karaktere kadar tek satirda kaldi. Bandin
# ustu ve altindaki puntolar REDDEDILMEZ, uyarilir: TYPE_SCALE 11..72 arasi
# calisiyor ve reddetmek bestecinin kendi puntolarini reddetmek olurdu.
#
# TYPE_SCALE runs 11..72, so refusing outside the band would refuse the
# composer's own sizes -- it warns instead. The two ends are not equally
# risky: above 38 an error leaves space, below 13 it overlaps, and small type
# is where body copy and answer labels live.
CALIBRATED_RANGE = (13.0, 38.0)
# How far a box may grow to hold its label, as a multiple of the height asked
# for. Past this the label is not a label any more.
#
# ZEMINI DEGISTI, DEGERI DEGISMEDI (2026-08-16). Bu sayi eski
# CHAR_WIDTH_RATIO=0.72'ye karsi ayarlanmisti: o oran karakteri dar
# sayiyordu, etiket daha az yer istiyordu, kutu daha az buyuyordu ve 2.4
# rahat bir tavandi. Oran olculup 0.79'a cekilince ayni etiket daha genis
# oldu, kutular tavana dayandi ve donor havuzu 40 harfte 8'den 1'e dustu.
#
# 40 harf SENTETIK DEGIL: add_button metni text[:40]'a kirpiyor (bestecinin
# kendi tavani) ve add_question kirpmiyor -- uretilen kursta 60 harflik sik
# etiketleri olculdu. Yani havuz cokusu uretim bandinda.
#
# K14: sabit degismedi, altindaki olcum degisti. Ayni zeminde secilmis her
# esik (POOL_FLOOR, deadband bandi, EMPTY_BASELINE) ayni riski tasiyor.
# 2.4 -> 2.8 (2026-08-17). BU BIR GEVSETME DEGIL, BIRIM DUZELTMESIDIR.
#
# Yargi degismedi: "kutu etiketi tasisin diye buyur, ama bundan fazla buyuyen
# sey artik etiket degil". Degisen sey o yargiyi ifade eden SAYI. Ayni donor,
# ayni etiket, ayni kutu -- model duzeltilince daha buyuk bir oran istiyor.
# Ileride biri bunu "tolerans artisi" sanmasin: TOLERANS AYNI, olcek dogru.
#
# OLCULDU, ve yetkili fonksiyonla (donors.rehearse; ilk denemem
# height_for_label'i sabit bir kutuyla tekrar hesapliyordu ve ayrisiyordu --
# K12). Eski zeminde (CHAR_WIDTH_RATIO=0.72, L=2.4) gecen donor kumesini
# kanonik zeminde AYNEN kapsayan en kucuk esik:
#
#     18 harf : L=2.6   (eski 10 donorun 10'u)
#     40 harf : L=2.8   (eski  2 donorun  2'si)
#
# Ikisini birden koruyan sayi 2.8.
#
# 3.0 SECILMEDI, ve gerekcesi kayda deger. 3.0 havuzu 40 harfte 2'den 8'e
# cikariyor ve dondurulmus POOL_MEASURED[40]=8 ile "uyusuyor". Ama o sayi
# HICBIR ZEMINDE yeniden uretilmiyor (eski zeminde olculen 2), yani
# provenance'i yok; provenance'i olmayan bir sayiya gore esik gevsetmek tam
# olarak bu projenin duzelttigi kalip. Ustelik yedi donor 2.95 civarinda
# KUMELENMIS: 3.0, bir kumenin hemen ustune konmus cizgidir ve kucuk bir
# olcum kaymasi havuzu 8'den 1'e dusurebilir. 2.8 kumeden uzakta, az donor
# veriyor ama ONGORULEBILIR sekilde veriyor.
#
# 40 harfte havuzun 2'ye inmesi ve POOL_FLOOR'un bagirmasi KUSUR DEGIL,
# calisan bir sinyal: o bantta donor cesitliligi yok. Cozum ya havuza uygun
# sekil eklemek ya da 40 harflik buton etiketini tasarim hatasi saymak --
# esigi gevsetmek sinyali susturur ve altindaki gercegi gizler.
GROWTH_LIMIT = 2.8
HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


def parse_color(value: str) -> str:
    match = HEX_RE.match((value or "").strip())
    if not match:
        raise StoryError(f"Renk 6 haneli onaltilik olmali (orn. #0A2240): {value!r}")
    return match.group(1).upper()


# ------------------------------------------------------------------ geometry


def slide_size(root: ET.Element) -> tuple[float, float]:
    """Read the deck's coordinate space off any shape that declares it."""
    for sld_sz in root.iter("sldSz"):
        try:
            width, height = float(sld_sz.get("w", 0)), float(sld_sz.get("h", 0))
        except ValueError:
            continue
        if width > 0 and height > 0:
            return width, height
    return DEFAULT_SLIDE_SIZE


def shape_rect(shape: ET.Element) -> tuple[float, float, float, float] | None:
    loc = shape.find("loc")
    if loc is None:
        return None
    try:
        return (float(loc.get("l", 0)), float(loc.get("t", 0)),
                float(loc.get("r", 0)), float(loc.get("b", 0)))
    except ValueError:
        return None


def occupied_rects(root: ET.Element) -> list[tuple[float, float, float, float]]:
    """Boxes of the slide's top-level shapes, ignoring full-bleed backgrounds.

    A background covers everything by definition; counting it as an obstacle
    would leave nowhere to put anything.
    """
    width, height = slide_size(root)
    shape_list = root.find("shapeLst")
    rects = []
    for shape in list(shape_list) if shape_list is not None else []:
        rect = shape_rect(shape)
        if rect is None:
            continue
        l, t, r, b = rect
        if (r - l) >= width * 0.95 and (b - t) >= height * 0.95:
            continue
        rects.append(rect)
    return rects


def _overlaps(a, b, margin: float = 0.0) -> bool:
    return not (a[2] + margin <= b[0] or a[0] >= b[2] + margin
                or a[3] + margin <= b[1] or a[1] >= b[3] + margin)


def avoid_collisions(
    root: ET.Element, rect: tuple[float, float, float, float], *, gap: float = 0.0
) -> tuple[tuple[float, float, float, float], bool]:
    """Nudge a box vertically until it stops overlapping what is already there.

    Placement is otherwise blind: a caller asking for "bottom right" has no way
    to know a paragraph already reaches there, so buttons land on top of text.
    Moving up rather than shrinking keeps the requested size intact; if nothing
    fits, the original is returned and the caller is told.
    """
    _, height = slide_size(root)
    gap = gap or height * 0.015
    existing = occupied_rects(root)
    l, t0, r, b0 = rect
    box_h = b0 - t0

    def free(top: float) -> bool:
        return not any(_overlaps((l, top, r, top + box_h), o, gap) for o in existing)

    if free(t0):
        return rect, True

    # Downwards first: content is written top to bottom, so whatever is in the
    # way is almost always above. Only if that runs off the slide is upwards
    # tried, which is what a footer button needs.
    for direction in (1, -1):
        top = t0
        for _ in range(40):
            blockers = [o for o in existing
                        if _overlaps((l, top, r, top + box_h), o, gap)]
            if not blockers:
                if 0 <= top and top + box_h <= height:
                    return (l, top, r, top + box_h), True
                break
            top = (max(o[3] for o in blockers) + gap if direction > 0
                   else min(o[1] for o in blockers) - gap - box_h)
            if top < 0 or top + box_h > height:
                break
    return rect, False


# IKI FARKLI SORU, IKI FARKLI SABIT -- ve bir donem ayni formulu
# paylasiyorlardi.
#
#   YERLESIM   "bu blok ne kadar yuksek olsun"  -> tasarim karari, comert
#   OLCUM      "bu kutu gercekten tasiyor mu"   -> fiziksel soru, durust
#
# Paylastiklari surece ikisinden biri yanlis olmak zorundaydi. Comert sabit
# yerlesimde bir GUVENLIK PAYI olarak calisiyor (blok biraz fazla yer ayirir,
# komsusunun ustune binmez) ama olcumde SAHTE TASMA uretiyordu: 'Devam Et' --
# sekiz harf, tek satir, kutu 97 birim -- model 100 diyordu, %3.4. Referans
# kurstaki 37 adayin 21'i tam olarak buydu.
#
# Olcum sabitini dusurup yerlesimi de dusurmek denendi ve dort kapiyi birden
# oynatti (deadband, golden, coverage, invariants/fit_choices) -- hepsi bu
# turun sorusuyla ilgisiz tabanlar. Yerlesim 2.35'te BIRAKILDI.
#
# Bu, check_thresholds_independent'in yakaladigi desenin kardesi: bir olcu,
# korudugu seyle ayni sabiti paylasirsa dogruyu soyleyemez.
# YERLESIM, OLCUMDEN TUREYIP USTUNE PAY EKLER -- ayri bir sihirli sayi degil.
#
# Iki sabit bagimsiz durdugu surece biri guncellenip digeri unutulur ve
# aralarindaki iliski okunamaz hale gelir. Kutu boyunun metnin CIZIM
# yuksekligine bagli olmasi gercek bir bagimlilik; yerlesimin olcume
# dayanmasi dogru.
#
# (Bu, check_thresholds_independent desenini ihlal etmez: orada sorun bir
# GUARD'in korudugu seyi referans almasiydi. Burada dogrulama --
# check_text_fits -- her ikisinden de bagimsiz kalmaya devam ediyor.)
#
# LAYOUT_SAFETY SAF PAYDIR ve BIR YARGIDIR, olcum degil.
#
# Neyi karsiliyor: oran hatasindan ARTA KALAN icerik degiskenligini. Oran
# hatasinin kendisi CHAR_WIDTH_RATIO 0.72'den 0.79'a cekilerek ZATEN kapandi;
# onu burada tekrar saymak cift sayim olurdu (1.09 x 1.15 = 1.25, oysa niyet
# 1.15'ti).
#
# Neyi karsilamiyor: satir sayisindaki KUANTALI iskalama. Uc satirlik bir
# kutuda bir satirlik sapma %33'tur ve hicbir makul carpan bunu kapatmaz.
# Pay, tipik cok satirli kutular icin secilir; kisa kutulardaki tek satirlik
# iskalama BILINEN SINIRDIR ve payi buyuterek kovalanmaz.
#
# Verisi YOK ve olmadigi bilerek kabul edildi: elde tek bir duzyazi ornegi
# var (C1), degiskenlik bir ornekten okunamaz. Yeni bir tur kosulmadi cunku
# sinif KOZMETIK -- kirpma olmadigi olculdu, yani hata iki yonde de ucuz:
# pay kucukse komsuya binme, buyukse bos alan.
#
# NE ZAMAN DEGISIR: birden fazla gercek kurs metninde satir sayisi olculup
# duzyazi orani icin bir YAYILIM elde edildiginde. O zaman bu sayi yargi
# olmaktan cikar.
LAYOUT_SAFETY = 1.05
#
# OLCUM SABITLERI ARTIK OLCULDU (2026-08-16). Oncekiler tahmindi ve ikisi de
# yanlisti -- biri yon olarak da yanlisti.
#
# Deney: 720 uzayinda bir slayda 12pt, ON SERT SATIR SONU, kutu 20 birim.
# Storyline Preview'da acildi, kare yakalandi, on satirin piksel konumu
# olculdu. Satirlar esit aralikli cikti:
#
#     satir adimi 24.33 px, slayt olcegi 0.8802 birim/px -> 21.42 birim
#     21.42 / 12pt = LEADING 1.785
#
# Yani leading TAHMIN EDILENDEN YUKSEK (1.2 yazilmisti, once 1.45'ti).
# Tipografik standarda cekmek yanlisti; Storyline daha genis satir koyuyor.
#
# Peki 'Devam Et' neden sahte tasma veriyordu? PADDING yuzunden. Kutu tam
# bir satir boyundaydi (97 birim) ve 16pt@1920 icin:
#     satir 16*2.667*1.785 = 76.2  +  padding 0.5*42.7 = 21.3  =  97.5 > 97
# Padding sifirlaninca 76.2 < 97, rahatca siginiyor. Hata leading'de degil
# padding terimindeydi ve on satirlik olcumde padding'in KARSILIGI YOK:
# satirlar arasi adim sabit, basta ya da sonda ek bir pay goruilmedi.
#
# KAPSAM: tek font, tek punto (12), tek uzay (720), sert satir sonlariyla.
# BOS PARAGRAFLAR BU OLCUMDE YOK ve ayri davraniyorlar -- 17 paragrafli
# (10'u bos) bir metin 782 birim cizildi, oysa hepsi dolu sayilsaydi 1457
# ederdi. Bos satir belirgin sekilde daha kisa cizilyor; NE KADAR oldugu
# HENUZ OLCULMEDI ve modelde hala tam satir sayiliyor. Siradaki kalibrasyon
# hedefi bu.
MEASURE_LEADING, MEASURE_PADDING = 1.785, 0.0

# Turetilmis: olcum yenilendiginde yerlesim otomatik takip eder ve
# gozden gecirilecek tek politika sayisi LAYOUT_SAFETY olur.
# PADDING DE TURETILIR. Bir donem 0.9'da elle birakildi ve yapiyi
# tutarsiz kildi: leading olcumden turerken padding eski tuning'den
# geliyordu. Sonuc tek satirli kutularda 2.77x -- eski 2.35x'ten de
# comert -- ve cok satirlida zaten buyumus kutularin ustune bir pay
# daha bindi. Olculen padding SIFIR; yerlesim de onu takip eder.
LAYOUT_LEADING = MEASURE_LEADING * LAYOUT_SAFETY
# NOT: MEASURE_PADDING su an 0.0, yani bu carpim BOSTA calisiyor --
# yapi dogru kurulmus ama bir sey turetmiyor. Padding ileride
# sifirdan farkli olculursa carpim aniden anlam kazanir ve o an
# TEST EDILMEMIS bir yol devreye girer. Kayit icin yazildi.
LAYOUT_PADDING = MEASURE_PADDING * LAYOUT_SAFETY

# Satır kutusunun iki bileşeni, ayrı ayrı adlandırılmış.
#
# Bir donem tek bir ifadenin icinde gomuluydu (`lines * line_px * 1.45 +
# line_px * 0.9`) ve TEK SATIR icin 2.35 x punto veriyordu. Tipografik satir
# yuksekligi 1.2-1.5 x puntodur; model tek satiri yaklasik iki katina
# sisiriyordu.
#
# Sonucu olculdu: referans kursta 37 "tasma" adayinin 21'i AYNI sekildi --
# 'Devam Et', sekiz harf, tek satir, kutu 97 birim, model 100 diyordu. %3.4.
# Sekiz harflik bir kelime tasamaz; tasan sey sabitti.
#
# BU DEGERLER OLCUM DEGIL, GEREKCELI SECIM. Dosya turuyla metin yuksekligi
# olculemiyor (kanitlandi: Storyline buyumeyi cizim aninda hesaplayip dosyaya
# yazmiyor), dolayisiyla leading burada tipografik standarttan aliniyor.
# Olculebildigi gun buraya olcum yazilir; o zamana kadar bu bir varsayimdir
# ve oyle okunmalidir.
#
# Esikle susturmak SECILMEDI: sahte tasmalar %3.4-9.4 bandinda kumelenmisti
# ve o bandi yok saymak tek satirlik vakalari susturur, cok satirlidaki ayni
# fazla tahmini sessizce birakirdi -- her satira eklenen fazlalik orada da
# duruyor.
# ---------------------------------------------------------------- UZAY, TEK SAHNE
#
# TEK SAHNE VARDIR: story/story.xml icindeki <sz w h>. Slaytin kendi <sldSz>'i
# bir KOORDINAT UZAYIDIR, cizim uzayi degil. Farkli olduklarinda Storyline
# slaydi sahneye orantili olarak sigdirir; yuzdeler korunur, PUNTODAN TUREYEN
# YUKSEKLIKLER KORUNMAZ.
#
# ESKI TABLO SILINDI, DUZELTILMEDI (2026-08-17):
#
#     MEASURED_HSCALE = {720: 1.000, 1920: 2.667}
#     MEASURED_VSCALE = {720: 1.000, 1920: 2.990}
#
# Ikisi de OLCUM DEGILDI. `kare_satir.py --uzay 1920` piksel/birim oranini
# sahnenin degil SLAYDIN ILAN ETTIGI genisliginden hesapliyordu; sahne 720
# iken 1920'ye bolmek turetilen her "birim"i tam 1920/720 = 2.667 kati
# buyutur. Tabloya yazilan sayi da aynen o.
#
# KANIT, ESKI KARELERDE DURUYORDU ve hipotezden bagimsiz:
#     preview_olcek720.png   slayt x409..1237 y259..822  829x564 px
#     preview_olcek1920.png  slayt x409..1237 y259..822  829x564 px
# 720 slaydi ile 1920 slaydi ekranda BIREBIR AYNI boyutta ciziliyor.
#
# YATAY NEDEN "TUTTU". Yatay hesapta oran SADELESIR: kutu genisligi de
# karakter genisligi de ayni carpanla olceklenir. 2.667 tam olarak
# slide_w/stage_w oldugu icin sessizce sadelesti ve dogru cevap verdi -- uc
# turda. Dikeyde sadelesme yok, cunku SATIR YUKSEKLIGI PUNTOYLA MUTLAKTIR;
# orada ayni hatali zemin 2.990 diye gorundu, gercek deger 2.000.
# Ayni hatali zemin bir eksende gorunur oldu, digerinde saklandi (K17).
#
# 1.121 ARTAKALANI YOK OLDU. Eski 2.990 = 2.667 x 1.121 diye yazilmisti ve
# "%12, sebebi bilinmiyor" diye kayitliydi. Duzeltilmis tabana gore kalinti
# 1.03-1.05 -- bant esigi gurultusunun (%10) icinde. Yanlis tabana gore
# hesaplanmis bir sayiyi ayri bir satira tasimak, ayni yanlis kategoriyi
# surdurmek olurdu. Kalinti YAZILMIYOR; olculebildigi gun olculur.
#
# CARPANLAR ARTIK TABLODA DEGIL. Ikisi de SAF DONUSUM ve yerinde hesaplaniyor.
# Tablo yalnizca gercekten olculmus seyleri tutar; bugun olculmus tek sey
# MEASURE_LEADING (720 sahnede, iki bagimsiz kosu).


# KANONIK TASARIM UZAYI -- OLCULDU, VARSAYILMADI (2026-08-17).
#
# Punto, slaydin ILAN ETTIGI koordinat uzayina 720x540'lik bir tasarima gore
# baglanir. SAHNE MATEMATIGE GIRMEZ; bu, iki sahnede ayni fikstuur kosularak
# olculdu:
#
#     sahne/slayt   13pt birim/punto   21pt birim/punto
#      720x540           1.817              1.810
#     1920x1080          3.577              3.536
#     ------------------------------------------------
#     R = 1920/720       1.969              1.954     ->  2.00
#
# Iki hipotez sinandi ve mevcut veri onlari AYIRAMIYORDU:
#     H_sahne    carpan = slide_h / stage_h   ->  R ~ 1.00   ELENDI
#     H_kanonik  carpan = slide_h / 540       ->  R ~ 2.00   DOGRULANDI
# (Curutulmus eski tablo bu karsilastirmada 2.99 derdi; o da elendi.)
#
# IKI PUNTO %0.8 ICINDE UYUSUYOR: iliski dogrusal, punto-bagimliligi yok.
# Eski tablodaki aciklanmamis 3.28 -> 3.13 kaymasi da boylece kapandi --
# o kayma yanlis zeminin artefaktiymis.
#
# YUZDE, UZAYDAN BAGIMSIZ OLUR ve bu carpimin dogal sonucu: yukseklik
# `punto * (slide_h/540) * leading` ise, slayt yuzdesi
# `punto * leading / 540 * 100` olur -- slide_h SADELESIR. Yani ayni metin
# hangi uzayda cizilirse cizilsin slaydin ayni kesrini kaplar.
KANONIK = (720.0, 540.0)

# OLCULMUS SAHNELER. Artik IKI tane, ve ikisinin ayni yasayi vermesi
# `KANONIK`in sahneden bagimsiz oldugunun kaniti. Liste kayit icin durur;
# carpanlar ona BAKMIYOR (bkz. Space.h / Space.v).
MEASURED_STAGES = ((720.0, 540.0), (1920.0, 1080.0))

class Space(NamedTuple):
    """Bir slaydın koordinat uzayı ve çizildiği sahne.

    Dort sayi birlikte tasinir cunku ikisi ayri ayri anlamsiz: yalnizca
    slayt boyutu, yalnizca sahne boyutu hicbir donusum vermez. `h` ve `v`
    TURETILMIS carpanlardir -- olcum degil, oran (K17).
    """

    slide_w: float
    slide_h: float
    stage_w: float
    stage_h: float

    @property
    def h(self) -> float:
        """YATAY: puntonun slayt birimine oranı. Sahne GİRMİYOR.

        TURETME (olculmedi): dikey eksen olculdu ve kanonik cikti; yatay
        ayni yasayi izliyor VARSAYILIYOR. 1920 SAHNEDE OLCULMEDI -- bu
        turun fikstuurunde etiketler sarmiyordu, dolayisiyla yatay kapasite
        sinanmadi. Simetri gerekcesi guclu ama olcum degil (K17).
        """
        return self.slide_w / KANONIK[0]

    @property
    def v(self) -> float:
        """DİKEY: puntonun slayt birimine oranı. Sahne GİRMİYOR.

        OLCULDU (2026-08-17, iki sahne, iki punto, alti sert satir):
            720  sahne/slayt : birim/punto 1.817 (13pt)  1.810 (21pt)
            1920 sahne/slayt : birim/punto 3.577 (13pt)  3.536 (21pt)
            R = 1.969 ve 1.954  ->  2.00
        """
        return self.slide_h / KANONIK[1]

    @property
    def kaynak(self) -> str:
        return (f"turetildi: {self.slide_w:.0f}x{self.slide_h:.0f} slayt / "
                f"{self.stage_w:.0f}x{self.stage_h:.0f} sahne "
                f"(h={self.h:.3f} v={self.v:.3f})")

    @property
    def tutarli(self) -> bool:
        """Slayt ile sahne aynı en/boy oranında mı?"""
        return abs(self.h - self.v) < 0.01

    @property
    def olculmus_sahne(self) -> bool:
        """Bu sahne boyutunda punto/birim oranı ÖLÇÜLDÜ mü?

        Artik iki sahne olculdu ve IKISI DE ayni yasayi verdi; carpan
        sahneden bagimsiz cikti. Yine de sorulmaya devam ediyor: ucuncu bir
        sahne (1280, 2560...) yine olculmemis bolgedir ve "iki noktadan
        gecen dogru her yerde gecerlidir" bu projede bir kez zaten yanlis
        cikti.
        """
        return any(abs(self.stage_w - w) < 1 and abs(self.stage_h - h) < 1
                   for w, h in MEASURED_STAGES)


def stage_size(pkg) -> tuple[float, float]:
    """Storyline'ın ÇİZDİĞİ sahne: story/story.xml içindeki tek <sz>.

    TEK YETKILI (K12). `package_slide_size` bir donem ilk slaydin kendi
    <sldSz>'ini donduruyordu -- yani siralamaya bagli ve yanlis dugum.
    Uretilen soru slaydi 1920x1080 ilan ederken sahne 720x540'ti ve butun
    dikey matematik o farkin uzerine kuruluyordu.
    """
    try:
        story = pkg.parse("story/story.xml")
    except Exception:
        return DEFAULT_SLIDE_SIZE
    for sz in story.iter("sz"):
        try:
            w, h = float(sz.get("w", 0)), float(sz.get("h", 0))
        except ValueError:
            continue
        if w > 0 and h > 0:
            return w, h
    return DEFAULT_SLIDE_SIZE


def space_of(root: ET.Element, stage: tuple[float, float]) -> Space:
    """Bu slaydın uzayı, verilen sahneye karşı."""
    sw, sh = slide_size(root)
    return Space(sw, sh, stage[0], stage[1])


def _space(space) -> Space:
    """Çağrı yerini uzayı AÇIKÇA vermeye zorlar.

    Ciplak bir float kabul EDILMIYOR ve varsayilan sahne YOK. Varsayilan
    birakilsaydi (mesela "sahne = slayt") gozden kacan her cagri tutarli bir
    deck varsayar ve karisik uzayli deck'te SESSIZCE yanlis olceklenirdi --
    bu oturumda tam olarak bu oldu ve uc tur boyunca gorunmedi.
    """
    if isinstance(space, Space):
        return space
    raise TypeError(
        "uzay bir shapes.Space olmali (slayt VE sahne birlikte). "
        "Ciplak genislik artik kabul edilmiyor: slaydin ilan ettigi boyut "
        "cizim uzayi degil. shapes.space_of(root, shapes.stage_size(pkg)) "
        "kullanin.")

WRAP_YOK = ("none", "false")


def wraps(shape: ET.Element) -> bool:
    """Bu kutu metni sarıyor mu?

    Corpus'ta uc deger var: true (1286), none (916), false (18). Sarmayan bir
    kutuda satir sayisi metnin uzunlugundan BAGIMSIZDIR -- paragraf sayisi
    kadardir, cunku Storyline tek satiri kutunun disina dogru uzatir.

    Nitelik YOKSA sardigi varsayilir. Bu bir olcum degil, bilincli bir yon
    secimi: sarmayan sayilan bir kutu icin tahmin dusuk cikar ve
    estimate_text_height'in kendi notu dusuk tahmini en kotu hata sayiyor
    ("a box too short shows as overlap").
    """
    return (shape.get("wrap") or "true").lower() not in WRAP_YOK


def estimate_text_width(text: str, font_size: float, space) -> float:
    """Sarmayan bir kutuda tek satırın gerektirdiği GENİŞLİK.

    wrap="none" olan bir kutuda dikey tasma IMKANSIZ ve yatay tasma KURAL:
    Storyline satiri kutunun sagina dogru uzatir, gerekirse slaydin disina.
    Olculdu -- 111 harflik bir metin 219 birimlik bir kutuda tek satir cizildi
    ve slaydin sag kenarini asti.

    Bu buyuklugu olcen hicbir sey yoktu: check_text_fits yalnizca yukseklige
    bakiyor, dolayisiyla sarmayan kutularin tasmasi tanim geregi gorunmez.
    """
    line_px = max(font_size, 1) * _space(space).h
    en_uzun = max((len(p) for p in (text or " ").split("\n")), default=0)
    return en_uzun * line_px * CHAR_WIDTH_RATIO


def _text_height(text: str, font_size: float, width: float,
                 space, *, wrap: bool,
                 leading: float, padding: float) -> float:
    """How tall a box must be for this text not to spill out of it.

    Storyline's font sizes are points against a 720-unit design width, so the
    rendered size scales with the deck: 14pt is roughly 37 units on a 1920-wide
    project and 14 on a 720-wide one. Without this, a paragraph asked to fit a
    fixed percentage of the slide simply overflows its box.

    Wrapped by words, because that is how it will actually be drawn. Counting
    characters and dividing said a 29-character title fitted one 30-character
    line; the renderer could not split "istersin?" and used two, and the block
    measured beneath it was placed over the second one. Everything downstream
    trusts this number, so it is the one place where guessing low is worst --
    a box slightly too tall shows as space, a box too short shows as overlap.
    """
    low, high = CALIBRATED_RANGE
    if not low <= font_size <= high:
        warnings.warn(
            f"{font_size}pt metin olcumu kalibre edilmis {low:.0f}-{high:.0f}pt "
            f"araliginin disinda; sonuc tahmindir. "
            f"tools/calibrate_text.py ile bandi genisletin.",
            RuntimeWarning, stacklevel=2)

    uzay = _space(space)
    if not uzay.olculmus_sahne:
        warnings.warn(
            f"{uzay.stage_w:.0f}x{uzay.stage_h:.0f} sahnede punto/birim orani "
            f"OLCULMEDI (olculen tek sahne "
            f"{', '.join(f'{w:.0f}x{h:.0f}' for w, h in MEASURED_STAGES)}); sonuc "
            f"tahmindir. Bu sahnede bir kare turu gerekiyor.",
            RuntimeWarning, stacklevel=3)
    # Satir basina karakter YATAY eksende. Bu hesap uzaydan BAGIMSIZDIR
    # (kutu genisligi de karakter genisligi de ayni carpanla olceklenir);
    # carpan yine de aciktan yaziliyor, cunku sadelestigi icin gorunmez olan
    # bir terim tam olarak bu oturumda uc tur boyunca saklanan seydi.
    per_line = max(1, int(width / (font_size * uzay.h * CHAR_WIDTH_RATIO)))
    # Satir yuksekligi DIKEY eksende, ve burada sadelesme YOK: punto mutlaktir,
    # slaydin ilan ettigi koordinatla degismez. Slayt sahneden yuksekse ayni
    # satir daha AZ slayt birimi kaplar (v > 1 iken bolen degil carpan).
    line_px = max(font_size, 1) * uzay.v
    lines = 0
    for paragraph in (text or " ").split("\n"):
        # SARMA, KUTUNUN OZELLIGI -- her kutu sarmaz. Bu satir bir donem
        # kosulsuzdu ve model her kutunun sardigini varsayiyordu; olculdu:
        # wrap="none" tasiyan bir kutuda 111 harflik metin TEK SATIR cizildi,
        # model 7 satir ongoruyordu. O tek varsayim, uretilmis bir kurstaki
        # 38 "tasma" adayinin 16'sini tek basina uretti -- hepsi artefakt.
        #
        # Sarmayan kutuda satir sayisi metnin uzunlugundan bagimsizdir;
        # tasma dikeyde degil YATAYDA olur (estimate_text_width).
        lines += _wrapped_lines(paragraph, per_line) if wrap else 1
    return lines * line_px * leading + line_px * padding


def layout_text_height(text: str, font_size: float, width: float,
                       space, *, wrap: bool = True) -> float:
    """YER AYIRMAK icin: comert. Blok bu kadar yuksek yapilir."""
    return _text_height(text, font_size, width, space, wrap=wrap,
                        leading=LAYOUT_LEADING, padding=LAYOUT_PADDING)


def measured_text_height(text: str, font_size: float, width: float,
                         space, *, wrap: bool = True) -> float:
    """KUSUR SAYMAK icin: durust. Bu kutu gercekten tasiyor mu?"""
    return _text_height(text, font_size, width, space, wrap=wrap,
                        leading=MEASURE_LEADING, padding=MEASURE_PADDING)


def text_inset(shape: ET.Element) -> tuple[float, float, float, float]:
    """How much of its own box a shape reserves around text: (l, t, r, b).

    Read from the first state body when there is one, because that is what
    Storyline draws and it can differ from the shell. -1 is Storyline's "use
    the default", not a negative inset, so it counts as nothing.
    """
    holder = None
    states = shape.find("stateLst")
    if states is not None and len(states):
        inner = states[0].find("shapeLst")
        if inner is not None and len(inner):
            holder = inner[0].find("textMargin")
    if holder is None:
        holder = shape.find("textMargin")
    if holder is None:
        return 0.0, 0.0, 0.0, 0.0

    def value(key: str) -> float:
        try:
            return max(float(holder.get(key, 0) or 0), 0.0)
        except ValueError:
            return 0.0

    return value("l"), value("t"), value("r"), value("b")


def height_for_label(shape: ET.Element, text: str, size: float,
                     box_width: float, space) -> float:
    """The box height this shape needs to show this label -- the inverse of
    estimate_text_height, asked of a particular shape.

    One function measures, one function sizes to the measurement, and both use
    the same wrap. Where they disagreed the deck overlapped: the composer
    measured a title as one line, the renderer drew two, and the block beneath
    landed on top of it.
    """
    left, top, right, bottom = text_inset(shape)
    usable = max(box_width - left - right, 1.0)
    return layout_text_height(text, size, usable, space) + top + bottom


def grow_to_fit(shape: ET.Element, rect: tuple[float, float, float, float],
                text: str, size: float, space, *, limit: float = None,
                band: tuple[float, float] | None = None,
                ) -> tuple[float, float, float, float]:
    """Give the box the height its label needs, growing about its centre.

    Grown rather than clipped, because a label that does not fit is not a
    smaller label -- it is text drawn outside its shape, which reads as a bug
    and passes every structural check. Height only: in a row of buttons the
    widths are the row's business, and widening one would push it into its
    neighbour.

    Growth is about the centre so a row keeps one centreline, and capped at
    `limit` times the requested height so a runaway label produces a visibly
    too-tall button rather than a shape swallowing the slide.

    band: buyumenin izinli oldugu (ust, alt) sinir. Verilmezse slaydin
    kenarlari kullanilir -- ve ISTE BU bir kusurdu: kompozisyonun tabani
    (FLOOR, %92) slaydin kenari degil, ama buyume slaydin kenarina kadar
    gidiyordu. Uzun etiketli bir buton %99.7'ye kadar uzuyor, tiklama alani
    slaydin altindan tasiyor ve hicbir yapisal kontrol bagirmiyordu.
    Olculdu: menu duzeninde dort butonun dordu, cover duzeninde ikisi.
    Duzene ozgu degil, BUYUME YOLUNA ait bir kusur.
    """
    left, top, right, bottom = rect
    width, height = right - left, bottom - top
    needed = height_for_label(shape, text, size, width, space)
    if needed <= height:
        return rect

    target = min(needed, height * (GROWTH_LIMIT if limit is None else limit))

    # Split about the centre, then give whatever one edge cannot take to the
    # other. Clamping each side independently was quietly short-changing any
    # box near an edge -- it grew by half of what it asked for and the label
    # overflowed again, which is the failure this function exists to remove,
    # reappearing exactly where nobody looks.
    ceiling, floor = band if band else (0.0, _space(space).slide_h)
    new_top, new_bottom = top, bottom
    for _ in range(2):
        short = target - (new_bottom - new_top)
        if short <= 0.01:
            break
        room_up, room_down = new_top - ceiling, floor - new_bottom
        if room_up <= 0 and room_down <= 0:
            break
        up = min(short / 2 if room_down > 0 else short, room_up)
        down = min(short - up, room_down)
        new_top -= up
        new_bottom += down
    return left, new_top, right, new_bottom


def _wrapped_lines(paragraph: str, per_line: int) -> int:
    """Lines this paragraph takes, breaking between words as a renderer does."""
    words = paragraph.split()
    if not words:
        return 1
    lines, current = 1, 0
    for word in words:
        need = len(word) if current == 0 else len(word) + 1
        if current + need <= per_line:
            current += need
            continue
        # A word wider than the whole line is broken across lines; anything
        # else starts a fresh one.
        if len(word) > per_line:
            remaining = len(word)
            if current:
                lines += 1
            lines += (remaining - 1) // per_line
            current = remaining % per_line or per_line
        else:
            lines += 1
            current = len(word)
    return lines


def _colour(parent: ET.Element, value: str, alpha: float | None = None) -> None:
    """A <clr> holding one colour, optionally translucent.

    Transparency lives inside the colour, not on the shape: 0..100000 where
    100000 is opaque. Same structure the application writes.
    """
    clr = ET.SubElement(parent, "clr")
    ET.SubElement(clr, "srgbClr", {"val": parse_color(value)})
    if alpha is not None and alpha < 1.0:
        ET.SubElement(clr, "alpha",
                      {"val": str(int(round(max(alpha, 0.0) * 100000)))})


def set_gradient(shape: ET.Element, start: str, end: str, *, angle: int = 90,
                 start_alpha: float | None = None,
                 end_alpha: float | None = None) -> None:
    """Fill the shape with a two-stop linear gradient.

    A flat field of colour is what makes a generated slide look generated. The
    format has carried gradients all along -- same slot in <bG> as solidFill,
    stops positioned 0..100 -- so this costs nothing but was never used.
    """
    background = shape.find("bG")
    if background is None:
        background = ET.Element("bG")
        shape.insert(0, background)

    at = 0
    for index, child in enumerate(list(background)):
        if child.tag in FILL_SLOT_TAGS:
            at = index
            background.remove(child)
            break

    fill = ET.Element("gradFill", {"type": "lin", "style": "lin",
                                   "rot": "true", "angle": str(angle)})
    ET.SubElement(fill, "centerPt", {"x": "0.5", "y": "0.5"})
    ET.SubElement(fill, "fillRect", {"l": "0", "t": "0", "r": "0", "b": "0"})
    stops = ET.SubElement(fill, "stops")
    for position, colour, alpha in ((0, start, start_alpha), (100, end, end_alpha)):
        stop = ET.SubElement(stops, "stop", {
            "g": new_guid(), "verG": new_guid(), "pos": str(position)})
        _colour(stop, colour, alpha)
    background.insert(at, fill)


def set_scrim(shape: ET.Element, color: str, *, alpha: float = 0.55,
              fade: bool = False, angle: int = 90) -> None:
    """Make the shape a translucent wash, so what is behind it shows through.

    This is what lets words sit on a photograph and stay readable: the picture
    keeps its detail, the wash carries the contrast. fade ramps the wash from
    solid to clear, which is how a cover holds a headline at one edge without
    dulling the whole image.
    """
    alpha = max(0.0, min(alpha, 1.0))
    if fade:
        set_gradient(shape, color, color, angle=angle,
                     start_alpha=alpha, end_alpha=0.0)
    else:
        set_fill(shape, color, alpha=alpha)


def set_text_flow(shape: ET.Element, *, vertical: str = "t", grow: bool = True) -> None:
    """Make text start at the top of its box and let the box grow to fit.

    Every long-text box in the decks measured here uses this pairing
    (vertAlign="t", autoFit="resize"); the default leaves a paragraph
    bottom-anchored and clipped.
    """
    shape.set("vertAlign", {"t": "t", "m": "m", "b": "b"}.get(vertical, "t"))
    shape.set("autoFit", "resize" if grow else "none")
    shape.set("wrap", "true")


def _place(element: ET.Element, left: float, top: float,
           right: float, bottom: float) -> None:
    loc = element.find("loc")
    if loc is None:
        loc = ET.SubElement(element, "loc")
    loc.set("l", _num(left))
    loc.set("t", _num(top))
    loc.set("r", _num(right))
    loc.set("b", _num(bottom))


def set_loc(shape: ET.Element, left: float, top: float, right: float, bottom: float) -> None:
    """Place the shape, and carry its state bodies with it.

    A shape with states is not drawn from its outer element: Storyline draws
    the body of whichever state is showing, and every body holds a <loc> of
    its own in local coordinates. Setting only the outer box moves the hit
    area and leaves the picture where it was.

    That went unnoticed while buttons came from the bundled <btn>, whose seed
    body happens to match. Donors made it plain -- a 193x386 dial and a 40x40
    chevron were both handed the same 144x51 button box and both ignored it,
    one swallowing the slide and the other invisible on it. Layout, overlap
    avoidance and distribution all reason about the outer box, so the bodies
    have to follow it or every one of those calculations is fiction.

    Bodies are positioned from their own origin, and measured across the pool
    none of them carries child shapes, so resizing the body is the whole job.
    """
    _place(shape, left, top, right, bottom)

    states = shape.find("stateLst")
    if states is None:
        return
    width, height = right - left, bottom - top
    for state in states:
        body_list = state.find("shapeLst")
        for body in (body_list if body_list is not None else []):
            _place(body, 0, 0, width, height)


def _num(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else repr(float(value))


# --------------------------------------------------------------------- fill


def set_fill(shape: ET.Element, color: str, *, alpha: float | None = None) -> None:
    """Replace the shape's fill slot with a solid colour.

    The colour sits one level deeper than it looks:

        <solidFill><clr><srgbClr val="12B5CB" /></clr></solidFill>

    Omitting the <clr> wrapper produces XML that parses cleanly and that
    Storyline refuses to open. The fill also belongs at the head of <bG>,
    ahead of the line and overlay entries -- measured across a real deck,
    solidFill and noFill are at index 0 in every one of 705 occurrences.
    """
    background = shape.find("bG")
    if background is None:
        background = ET.Element("bG")
        shape.insert(0, background)

    at = 0
    for index, child in enumerate(list(background)):
        if child.tag in FILL_SLOT_TAGS:
            at = index
            background.remove(child)
            break

    fill = ET.Element("solidFill")
    _colour(fill, color, alpha)
    background.insert(at, fill)


# --------------------------------------------------------------- text style


SPAN_RE = re.compile(r"<Span\b[^>]*?(/?)>")
# Both forms. A <Style> that carries children -- which is how the donor kits
# write theirs -- closes with a plain ">", and a pattern that only matched the
# self-closing form reported "this run has no style" for every one of them.
# The styler then added a second <Style> ahead of the real one, and Storyline
# answered a two-style Span by drawing the document's markup as the label.
STYLE_RE = re.compile(r"<Style\b[^>]*?/?>")


def set_text_style(
    raw_doc: str,
    *,
    color: str | None = None,
    size: float | None = None,
    bold: bool | None = None,
    font: str | None = None,
    align: str | None = None,
) -> str:
    """Restyle every run of an embedded Document, in place.

    Edits the raw string rather than round-tripping through ElementTree, for
    the same reason the text editor does: the Document's xmlns:xsi/xsd
    declarations are unused and ElementTree drops them on serialisation.

    Runs come in two shapes and both must be handled. Text boxes carry a run
    style:

        <Span Text="..."><Style FontFamily="Segoe UI" /></Span>

    while buttons often have none at all:

        <Span Text="SINAV" />

    A styler that only edits existing <Style> tags silently skips the second
    form, so a self-closing Span is reopened and given one.
    """
    updates: dict[str, str] = {}
    if color is not None:
        updates["ForegroundColor"] = "#" + parse_color(color)
    if size is not None:
        updates["FontSize"] = _num(size)
    if bold is not None:
        updates["FontBold"] = "true" if bold else "false"
    if font is not None:
        updates["FontFamily"] = font

    if updates:
        # Reverse order keeps earlier match offsets valid as the string grows.
        for span in reversed(list(SPAN_RE.finditer(raw_doc))):
            if span.group(1) == "/":
                open_tag = span.group(0)[:-2].rstrip() + ">"
                block = open_tag + _merge_attrs("<Style />", updates) + "</Span>"
                raw_doc = raw_doc[: span.start()] + block + raw_doc[span.end() :]
                continue
            tail = raw_doc[span.end() :]
            close = tail.find("</Span>")
            style = STYLE_RE.search(tail if close < 0 else tail[:close])
            if style:
                at = span.end() + style.start()
                raw_doc = (
                    raw_doc[:at]
                    + _merge_attrs(style.group(0), updates)
                    + raw_doc[at + len(style.group(0)) :]
                )
            else:
                raw_doc = (
                    raw_doc[: span.end()]
                    + _merge_attrs("<Style />", updates)
                    + raw_doc[span.end() :]
                )

    if align is not None:
        justification = {"l": "Left", "c": "Center", "r": "Right", "j": "Justify"}.get(
            align[:1].lower(), align.capitalize()
        )
        raw_doc = re.sub(
            r"(<Block\b[^>]*>\s*<Style\b[^>]*?)(\s*/>)",
            lambda m: _merge_attrs(m.group(1) + m.group(2), {"Justification": justification}),
            raw_doc,
        )
    return raw_doc


def _merge_attrs(tag: str, updates: dict[str, str]) -> str:
    """Set attributes on a tag, whether it closes itself or opens an element.

    An opening tag has to stay an opening tag: rewriting <Style ...> as
    <Style ... /> would orphan the </Style> that follows it.
    """
    stripped = tag.rstrip()
    closer = "/>" if stripped.endswith("/>") else ">"
    body = stripped[: -len(closer)].rstrip()
    for key, value in updates.items():
        pattern = re.compile(rf'\s{re.escape(key)}="[^"]*"')
        if pattern.search(body):
            body = pattern.sub(f' {key}="{value}"', body, count=1)
        else:
            body += f' {key}="{value}"'
    return f"{body} {closer}" if closer == "/>" else f"{body}{closer}"


# ------------------------------------------------------------- shape seeds


SEED_DIR = Path(__file__).resolve().parent / "seeds"


def _has_states(shape: ET.Element) -> bool:
    states = shape.find("stateLst")
    return states is not None and len(states) > 0


def find_seed(pkg: StoryPackage, tag: str, *,
              identity: str | None = None) -> tuple[ET.Element, str]:
    """A shape of this kind to copy, and where it came from.

    Three places are tried, in this order.

    *The project*, always first and always winning. A course that already has a
    button grows more of the same button; consistency inside a deck outranks
    any variety the pool could offer. This is also what makes a choice stick --
    once the first one is placed, every later call finds it here.

    *The donor pool*, for the roles it serves. This is what stops every course
    built from a blank wearing the one bundled button. The donor is chosen from
    the course identity, so it holds for the course and differs between
    courses; see donors.choose.

    *The bundled seed*, last. Without it an empty project could never grow its
    first text box -- the tool would have to ask the user to go and draw one by
    hand, which is the manual work it exists to remove.

    Bundling is only sound for shapes that reference nothing outside
    themselves. Measured across two real courses: <textBox> and <rect> have
    zero external GUID references, while <btn> has a few (layoutG, qsG, jumpG)
    which are neutralised to the null GUID when the seed is captured.
    """
    wants_control = tag in donors.ROLES
    for part in slide_index(pkg):
        shape_list = pkg.parse(part).find("shapeLst")
        for shape in list(shape_list) if shape_list is not None else []:
            if shape.tag != tag:
                continue
            # A control is not a parts-bin primitive. Since donors supply
            # buttons drawn as ordinary shapes, the deck's own button is now a
            # <roundRect> -- and asking for a roundRect to back a card would
            # clone it, states and all, turning decoration into a dead control.
            if not wants_control and _has_states(shape):
                continue
            return shape, "project"

    if wants_control:
        # The file name stands in when no identity is given: two courses are
        # two files, so they still draw different donors, while one course
        # keeps drawing the same one.
        picked = donors.choose(identity or pkg.path.stem, tag)
        if picked is not None:
            return picked.element(), f"donor:{picked.origin}"
        if donors.pool_dir().is_dir():
            # Falling through here is correct -- a course still needs a button
            # -- but it is not the same thing as having no pool configured, and
            # saying nothing would let a course quietly lose all its variety.
            warnings.warn(
                f"Donor havuzunda <{tag}> icin uygun aday yok; gomulu tohuma "
                "dusuluyor. Bu kurs cesitlilik kazanmayacak.",
                RuntimeWarning, stacklevel=2)

    seed_file = SEED_DIR / f"{tag}.xml"
    if seed_file.is_file():
        return ET.fromstring(seed_file.read_text(encoding="utf-8")), "bundled"

    raise StoryError(
        f"Bu projede klonlanabilir bir <{tag}> yok ve gomulu bir ornegi de bulunmuyor."
    )


def set_shape_slide_size(shape: ET.Element, width: float, height: float) -> None:
    """Stamp the target deck's coordinate space onto a shape.

    A bundled seed carries the slide size of the course it was captured from;
    left alone, a 1920x1080 seed dropped into a 720x540 deck records the wrong
    reference frame for its own geometry.
    """
    for sld_sz in shape.iter("sldSz"):
        sld_sz.set("w", _num(width))
        sld_sz.set("h", _num(height))


def clone_shape(
    seed: ET.Element, *, name: str | None = None, keep_triggers: bool = False
) -> ET.Element:
    """Copy a shape with a fresh identity, ready to insert elsewhere.

    Triggers are dropped by default: a cloned shape's triggers still point at
    the seed's targets, so a decorative copy would silently inherit someone
    else's navigation. Buttons pass keep_triggers=True and are retargeted.
    """
    raw = ET.tostring(seed, encoding="unicode")
    mapping = {old: new_guid() for old in _defined_guids(raw)}
    shape = ET.fromstring(_remap_guids(raw, mapping))
    if name is not None:
        shape.set("name", name)
    if not keep_triggers:
        for trig_list in shape.iter("trigLst"):
            for trig in list(trig_list):
                trig_list.remove(trig)
    return shape


def retarget_click(shape: ET.Element, *, slide_guid: str | None) -> bool:
    """Point the shape's first trigger at a slide, or at simply "the next one".

    Storyline encodes the destination as <slide jumpG="..."> with
    actSubType="spec"; dropping jumpG and using actSubType="next" is what the
    built-in continue button does.
    """
    for trig_list in shape.iter("trigLst"):
        for trig in trig_list:
            data = trig.find("data")
            if data is None:
                continue
            data.set("enabled", "true")
            data.set("event", "OnClick")
            data.set("action", "jumpToSlide")
            data.set("actSubType", "spec" if slide_guid else "next")
            slide = data.find("slide")
            if slide is None:
                slide = ET.SubElement(data, "slide")
            if slide_guid:
                slide.set("jumpG", slide_guid)
            else:
                slide.attrib.pop("jumpG", None)
            slide.set("showNav", "false")
            scene = data.find("scene")
            if scene is not None:
                scene.attrib.pop("jumpG", None)
            return True
    return False


def retarget_to_layer(shape: ET.Element, layer_guid: str) -> bool:
    """Make the shape's click open a slide layer instead of navigating.

    Layers are shown by action="showSubSlide" with the target carried on
    <sldLayer showG="...">, which is a different slot from the jumpG a slide
    jump uses -- so the navigation target is cleared rather than left dangling.
    """
    for trig_list in shape.iter("trigLst"):
        for trig in trig_list:
            data = trig.find("data")
            if data is None:
                continue
            data.set("enabled", "true")
            data.set("event", "OnClick")
            data.set("action", "showSubSlide")
            data.set("actSubType", "spec")
            layer = data.find("sldLayer")
            if layer is None:
                layer = ET.SubElement(data, "sldLayer")
            layer.set("showG", layer_guid)
            slide = data.find("slide")
            if slide is not None:
                slide.attrib.pop("jumpG", None)
            return True
    return False


# Canonical child order of <sld>, derived from 47 real slides. Storyline's
# reader takes these as a sequence: an element appended at the end instead of
# its declared position yields a file that parses and will not open.
SLIDE_CHILD_ORDER = (
    "tmProps", "tmCtxLst", "sz", "bg", "shapeLst", "trigLst", "localizedName",
    "trans", "propBag", "note", "szCalc", "navData", "sldLayerLst", "thumb",
    "localizedNote", "panTime", "panRect",
)


def insert_in_order(parent: ET.Element, element: ET.Element,
                    order: tuple[str, ...] = SLIDE_CHILD_ORDER) -> ET.Element:
    """Insert a child where the schema expects it, not wherever is convenient.

    Falls back to appending for tags the order does not mention, which is the
    safe choice for anything unrecognised.
    """
    existing = parent.find(element.tag)
    if existing is not None:
        return existing
    if element.tag not in order:
        parent.append(element)
        return element

    rank = order.index(element.tag)
    for index, child in enumerate(list(parent)):
        if child.tag in order and order.index(child.tag) > rank:
            parent.insert(index, element)
            return element
    parent.append(element)
    return element


def ensure_timeline(root: ET.Element) -> bool:
    """Give the slide a timeline context if it has none.

    Every slide that carries shapes has exactly one:

        <tmCtxLst version="1"><tmCtx start="0" dur="0" min="250" .../></tmCtxLst>

    An empty slide legitimately has none -- there is nothing to place on a
    timeline. Adding the first shape therefore has to create it: a shape brings
    its own tmCtxLst, but with no slide-level timeline to host it Storyline
    rejects the project outright ("invalid or corrupt"), even though the XML
    parses and the package is otherwise intact.

    Position matters. The element belongs immediately after <tmProps>, the
    order Storyline's own writer produces.
    """
    if root.find("tmCtxLst") is not None:
        return False

    timeline = ET.Element("tmCtxLst", {"version": "1"})
    ET.SubElement(timeline, "tmCtx", {
        "g": new_guid(), "verG": new_guid(),
        "start": "0", "dur": "0", "min": "250", "max": "0",
        "hasMax": "false", "alwysShw": "false", "untilEnd": "false",
        "assetStart": "0", "name": "",
    })
    insert_in_order(root, timeline)
    return True


def retarget_to_scene(shape: ET.Element, scene_guid: str) -> bool:
    """Make the shape's click jump to another scene.

    A scene jump uses its own slot -- <scene jumpG> -- so the slide target is
    cleared rather than left pointing somewhere the action no longer reads.
    """
    for trig_list in shape.iter("trigLst"):
        for trig in trig_list:
            data = trig.find("data")
            if data is None:
                continue
            data.set("enabled", "true")
            data.set("event", "OnClick")
            data.set("action", "jumpToScene")
            data.set("actSubType", "spec")
            scene = data.find("scene")
            if scene is None:
                scene = ET.SubElement(data, "scene")
            scene.set("jumpG", scene_guid)
            slide = data.find("slide")
            if slide is not None:
                slide.attrib.pop("jumpG", None)
            return True
    return False


def retarget_to_close_layer(shape: ET.Element, layer_guid: str | None = None) -> bool:
    """Make the shape's click close a layer -- its own, unless told otherwise.

    Storyline writes actSubType="me" for "the layer this button sits on",
    which is what a close button on a pop-up needs; naming a layer explicitly
    switches it to that one.
    """
    for trig_list in shape.iter("trigLst"):
        for trig in trig_list:
            data = trig.find("data")
            if data is None:
                continue
            data.set("enabled", "true")
            data.set("event", "OnClick")
            data.set("action", "hideSubSlide")
            data.set("actSubType", "spec" if layer_guid else "me")
            layer = data.find("sldLayer")
            if layer is None:
                layer = ET.SubElement(data, "sldLayer")
            if layer_guid:
                layer.set("hideG", layer_guid)
            else:
                layer.attrib.pop("hideG", None)
            layer.attrib.pop("showG", None)
            return True
    return False


def add_shape(root: ET.Element, shape: ET.Element, *, to_back: bool = False) -> None:
    """Insert a shape and renumber z-order so the stack stays consistent."""
    ensure_timeline(root)
    shape_list = root.find("shapeLst")
    if shape_list is None:
        shape_list = ET.SubElement(root, "shapeLst")
    shape_list.insert(0, shape) if to_back else shape_list.append(shape)
    for index, child in enumerate(shape_list):
        child.set("zOrder", str(index))


def _saydam_dolgu(shape: ET.Element) -> bool:
    """Seklin DOLGUSU saydam mi -- altindaki sey goruniyor mu.

    Yalnizca dolgu yuvasina bakilir, <bG> agacinin tamamina degil: golge ve
    parlama renkleri de alpha tasiyor ve onlara bakan bir olcum, altin sari
    bir seridi "ortu" sanip gercekten ortu olmayan bir slaydi ortulu ilan
    ediyordu (olculdu 2026-08-29, denee.story slide2).
    """
    background = shape.find("bG")
    if background is None:
        return False
    dolgu = next((c for c in background if c.tag in FILL_TAGS), None)
    if dolgu is None:
        return False
    if dolgu.tag == "noFill":
        return True
    for alpha in dolgu.iter("alpha"):
        try:
            if float(alpha.get("val", "100000")) < 99000:
                return True
        except ValueError:
            continue
    return False


def send_above_background(root: ET.Element, shape: ET.Element) -> int:
    """Move a shape to just above the full-bleed background, if there is one.

    "Background" is decided by geometry, not by name: any shape covering
    essentially the whole slide from the very back of the stack. A slide
    composed elsewhere, or one the user made by hand, gets the same treatment.
    """
    shape_list = root.find("shapeLst")
    if shape_list is None:
        return 0
    width, height = slide_size(root)
    # Taken out first: counting positions with the shape still in the list
    # measures the stack it is about to leave, not the one it lands in.
    shape_list.remove(shape)

    floor_index = 0
    for index, child in enumerate(list(shape_list)):
        rect = shape_rect(child)
        if rect is None:
            break
        l, t, r, b = rect
        if not (l <= width * 0.02 and t <= height * 0.02
                and r >= width * 0.98 and b >= height * 0.98):
            break
        # ORTU ZEMIN DEGILDIR. Tam sayfa olmasi yetmiyor: yari saydam bir
        # ortu de tam sayfadir ve resmi onun USTUNE koymak, okunabilirligi
        # saglayan tek katmani islevsiz birakir. Olculdu 2026-08-29: kapakta
        # `Ton` (%30 lacivert) fotografin ALTINDA kaldi, fotograf hic
        # yatismadi ve baslik okunmadi. Ayirt eden sey dolgunun saydamligi.
        if _saydam_dolgu(child):
            break
        floor_index = index + 1

    shape_list.insert(floor_index, shape)
    for index, child in enumerate(shape_list):
        child.set("zOrder", str(index))
    return floor_index


def shape_document(shape: ET.Element) -> ET.Element | None:
    """The <text> element holding this shape's rich-text document."""
    for text_el in shape.iter("text"):
        if (text_el.text or "").strip().startswith("<Document"):
            return text_el
    return None
