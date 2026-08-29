"""Variables, triggers and conditions -- the branching layer.

Almost everything a scripted course does beyond turning pages rests on three
things: a variable to remember something, a trigger to change it, and a
condition to act on it. Without them a deck can only be read front to back --
no counters, no gating, no "you got six right, skip ahead", no name in the
certificate. Adding them opens most of what was previously refused at once.

The structures, measured rather than assumed:

    <var name="Skor" dataType="num|text|bool" val="0" type="user" .../>

    <data action="adjustVar" actSubType="spec">
      <other varG="…" op="ass|add" dblVal="10" boolVal="True" varVal1=""/>

    <condLst><trigCond op="eq|noteq|gte|lt" dataType="value|var"
                       varG="…" floatVal1="6" strVal1="" andOr="and"/></condLst>

Triggers are cloned from a captured seed rather than written from scratch: a
<data> element carries twelve child slots whose absence is not tolerated, and
this project has already paid twice for elements that parse and will not open.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from . import model, shapes
from .clone import NULL_GUID, new_guid
from .package import STORY_PART, StoryPackage, StoryError

SEED_DIR = Path(__file__).resolve().parent / "seeds"

VAR_TYPES = {"num": "num", "number": "num", "sayi": "num",
             "text": "text", "metin": "text",
             "bool": "bool", "boolean": "bool", "mantik": "bool"}

# adjustVar: assign, or add to. Storyline offers no others.
VAR_OPS = {"set": "ass", "ata": "ass", "assign": "ass",
           "add": "add", "ekle": "add"}


# --------------------------------------------- Storyline'in sayi sinirlari
#
# OLCULDU (Preview, 2026-08-23, yedi tur), varsayilmadi. Ilk iki tur yanlis
# bir model uretti ("her yerde 8 anlamli basamak"); ucuncu tur onu curuttu ve
# asagidaki model butun gozlemleri aciklayan ILK model oldu.
#
# KULLANIM KURALI, tek cumle: HASSASIYET ONEMLIYSE ARITMETIGI JS SetVar
# UZERINDEN IFADE ET, adjust_variable literaliyle degil. Olculdu ve tahminin
# TERSI cikti -- JS koprusu en hassas yol, native adjust_variable ondan iki
# basamak daha kaba.
#
# UC AYRI KESIT, UC AYRI SINIR. Karistirilmamali:
#
#   varsayilan (story.xml val=)  ->  8 ANLAMLI BASAMAK
#   adjust_variable sonucu       ->  7 ANLAMLI BASAMAK
#   JS SetVar                    ->  TAM (en az 9 basamak olculdu)
#
# Yani JS koprusu en HASSAS yol, en riskli yol degil. Ilk okumada tersi
# saniliyordu.
#
# VARSAYILAN -- 8 basamak. Olculen:
#     1234567.891    -> 1234567.9
#     0.123456789012 -> 0.12345679
#     123456789012.5 -> 123456790000     <- tamsayi kismi bozuldu
#     16777217 / 33554433 / 99999999 / 2000000000 -> TAM
#   Son satir float32'yi ELER: float32 olsaydi ucu de bozulurdu.
#   Kayip gosterimde degil SAKLAMADA: A=1234567.891 iken A+(-1234567)
#   sonucu 0.891 degil 0.9 cikti.
#
# ADJUST_VARIABLE -- 7 basamak, ve bu SONUCA uygulanir, literale degil:
#     0 + 1234567           -> 1234567     (7 basamak, TAM)
#     0 + 12345678          -> 12345680    <- 8 basamak, literal 2^31 ALTINDA
#     0 + 1000000 + 1       -> 1000001     (TAM)
#     0 + 10000000 + 1      -> 10000000    <- +1 HIC ISLEMEDI
#     0 + 16777216 + 1      -> 16777220
#     0 + 12345678 + 87654321 -> 100000000 (99999999 olmaliydi)
#   Dorduncu satir bu sinirin neden onemli oldugunu tek basina anlatiyor:
#   10 milyonu gecen bir sayac SESSIZCE saymayi birakir.
#
# LITERAL KELEPCESI -- |deger| >= 2^31 ise int32 doygunlugu (2147483647),
# sonra 7 basamak yuvarlamasi:
#     0 + 2000000000   -> 2000000000   (2^31 alti, TAM -- kontrol)
#     0 + 3000000000   -> 2147484000
#     0 + 123456780000 -> 2147484000   <- 123 milyar ile 3 milyar ayni sayi
#     0 + -3000000000  -> -2147484000
#   2147484000 = 2147483647'nin 7 anlamli basamagi. Bu okuma, onceki "8
#   basamak" modelini curuten veriydi ve yeni modelde tam yerine oturuyor.
#
# KELEPCE YALNIZCA LITERAL YOLUNDA. Kaniti: varsayilani 123456789012.5 olan
# bir degisken 2147484000'e DUSMEDI, 123456790000 gosterdi. Iki sinir ayri
# kesitlerde, o yuzden `sayi_sorunu` bir `literal` bayragi tasiyor.
#
# YAZMA YOLU HER DURUMDA TEMIZ: XML'de degerler aynen duruyor
# (val="1234567.891", dblVal="-123456780000" geri okundu). Bozan
# Storyline'in kendi motoru -- storyline_mcp degil. Bu ayrim onemli ki
# ileride biri "storyline_mcp sayilari bozuyor" diye yanlis teshis koymasin.
#
# KAPININ KAPSAMADIGI SEY, acikca: `adjust_variable` sinirini SONUCA
# uyguluyor, ve sonuc calisma aninda birikir. Iki kucuk deger ust uste
# toplanip 7 basamagi asarsa kapi bunu goremez. Statik olarak bilinebilen
# yalnizca literalin kendisi. Bu kor nokta kapatilmadi -- olculdu ve
# yazildi; `audit`'in kapsam cumlesi de bunu soyluyor.
#
# CIKIS YOLU OLCULDU: JS SetVar tam degeri tasiyor (16777217, 33554433,
# 199999998 -- ucu de kayipsiz). 7 basamagi asabilecek bir sayac
# `adjust_variable` yerine JS ile tutulabilir.
#
# NEDEN REDDEDILIYOR, uyarilmiyor. Bu projenin kapattigi sinif tam olarak
# budur: sessizce yanlis sonuc ureten yol. `watch` eksikken reddediliyor,
# kontrol karakteri reddediliyor, dogrulamayi gecemeyen paket yazilmiyor.
# Buyuk bir sayi gecerli GORUNUR, hata vermez, ve yanlis bir tutar gosterir.

SAYI_VARSAYILAN_BASAMAK = 8      # story.xml val= -- olculdu
SAYI_ARITMETIK_BASAMAK = 7       # adjust_variable sonucu -- olculdu
SAYI_LITERAL_SINIR = 2 ** 31     # int32 doygunlugu -- olculdu


def anlamli_basamak(deger: object) -> int | None:
    """Bir sayinin anlamli basamak sayisi. Sayi degilse None.

    Sondaki sifirlar anlamli SAYILMAZ: 2000000000 tek basamaktir ve olcumde
    tam geldi; 16777217 sekiz basamaktir ve varsayilan olarak o da tam geldi.
    Kural bu ikisini ayirmak zorunda, yoksa gecerli bir yuvarlak sayi bosuna
    reddedilir.
    """
    from decimal import Decimal, InvalidOperation
    if isinstance(deger, bool) or deger is None:
        return None
    try:
        d = Decimal(str(deger).strip())
    except (InvalidOperation, ValueError):
        return None
    if not d.is_finite():
        return None
    return len(d.normalize().as_tuple().digits)


def sayi_sorunu(deger: object, *, literal: bool) -> str | None:
    """Deger Storyline'da sessizce bozulur mu. Bozulursa SEBEBI dondur.

    Tek yer burasi: hem `add_variable`'in num varsayilani hem `add_trigger`'in
    adjust_variable literali buradan geciyor. Esikler AYRI cunku kesitler
    olcumle ayri cikti (8 ve 7); tek esik kullanilsaydi ya gecerli
    varsayilanlar bosuna reddedilirdi ya da bozuk literaller gecerdi.
    """
    basamak = anlamli_basamak(deger)
    if basamak is None:
        return None

    if literal:
        try:
            buyukluk = abs(float(str(deger).strip()))
        except (TypeError, ValueError):
            buyukluk = 0.0
        if buyukluk >= SAYI_LITERAL_SINIR:
            return (
                f"{deger}: Storyline bu degeri 2^31 ({SAYI_LITERAL_SINIR}) "
                f"sinirinda KELEPCELER ve yerine ~2147484000 kullanir -- "
                f"olculdu: 3 milyar da 123 milyar da ayni sayiya donusuyor. "
                f"Hata verilmez, yanlis sayi kullanilir. Dosyaya yazilan deger "
                f"dogrudur; bozan Storyline'in kendi motorudur. Cozum: olcegi "
                f"kucult (kurus yerine lira), degeri metin degiskeninde tut, "
                f"ya da JS ile yaz -- JS SetVar tam degeri tasiyor (olculdu)."
            )
        if basamak > SAYI_ARITMETIK_BASAMAK:
            return (
                f"{deger} degeri {basamak} anlamli basamak iceriyor; "
                f"adjust_variable sonucu {SAYI_ARITMETIK_BASAMAK} basamaga "
                f"yuvarlanir -- olculdu: 0 + 12345678 -> 12345680. Hata "
                f"verilmez. Dosyaya yazilan deger dogrudur; bozan Storyline'in "
                f"kendi motorudur. Cozum: olcegi kucult, ya da degeri JS ile "
                f"yaz -- JS SetVar tam degeri tasiyor (olculdu)."
            )
        return None

    if basamak > SAYI_VARSAYILAN_BASAMAK:
        return (
            f"{deger} degeri {basamak} anlamli basamak iceriyor; Storyline "
            f"degisken varsayilanini {SAYI_VARSAYILAN_BASAMAK} basamaga kadar "
            f"tam tutar, otesini kaybeder -- olculdu: 123456789012.5 -> "
            f"123456790000, yani tamsayi kismi bile bozuluyor. Kayip "
            f"gosterimde degil saklamada, ve hata verilmez. Dosyaya yazilan "
            f"deger dogrudur; bozan Storyline'in kendi motorudur. Cozum: "
            f"kimlik/seri numarasi gibi degerleri metin (text) degiskeninde "
            f"tutun, ya da olcegi kucultun."
        )
    return None


# trigCond comparisons.
COND_OPS = {"eq": "eq", "==": "eq", "esit": "eq",
            "noteq": "noteq", "!=": "noteq", "esitdegil": "noteq",
            "gt": "gt", ">": "gt",
            "gte": "gte", ">=": "gte",
            "lt": "lt", "<": "lt",
            "lte": "lte", "<=": "lte"}

# EVENTS OLCULEREK KURULDU (tools/event_probe.py, 2026-08-23). Her ad tek
# basina bir dosyaya yazildi, Storyline'da acildi, tetikleyici paneli
# doldurulacak sekilde slayt secildi ve "Error Report" penceresi cikip
# cikmadigina bakildi. Her kosuda iki yonlu kanarya birlikte kostu:
# OnClick saglam kalmali, zzzNotAnEvent cokmeli.
#
# ONCEKI LISTE ELLE YAZILMISTI ve iki degeri Storyline'i COKERTIYORDU --
# `OnSlideEnd` ve `OnPrevButtonClick`. Yani arac onlari GECERLI sayip
# yaziyordu ve urettigi dosya kullanicinin Storyline'ini dusuruyordu.
# Ayni listede donorlerde 105 kez gecen uc olay (OnDialTurns 77, OnDrop 23,
# OnStateChange 5) REDDEDILIYORDU. K15: elle yazilmis liste gercek kumeyle
# sessizce ayrisir.
#
# KALIP BENZERLIGI KANIT DEGIL, ve bu olculdu: OnNextButtonClick calisiyor
# ama ayni kaliptaki OnSubmitButtonClick / OnFinishButtonClick /
# OnFirstButtonClick / OnLastButtonClick dordu de cokertiyor. DLL'de gecmek
# de kanit degil: OnPrevButtonClick DLL'de duruyor ve cokertiyor -- oradaki
# adlar C# olay adlari, XML degerleri degil.
# UCUNCU KAYNAK: MOTORUN KENDI UI KAYNAK ANAHTARLARI (2026-08-24).
#
# Liste iki kez turetilmisti: elle (iki cokerten ad tasiyordu) ve donorlerden
# (yalnizca KULLANILAN olaylari gosterir). Ucuncusu Articulate.Design.dll:
# tetikleyici acilir menusundeki her olayin bir `<Ad>ComboName` / DisplayName
# kaynak anahtari var.
#
# YONTEM IKI YONLU KALIBRE EDILDI, ham dizgi taramasindan farki tam burada:
#   pozitif : 17 bilinen gecerli adin 17'sinin de kaynak anahtari VAR
#   negatif : 9 bilinen cokertenin 9'unun da kaynak anahtari YOK
#             -- dordu ham dizgide GECIYOR (OnPrevButtonClick dahil), yani
#             filtre tam da ham taramanin dustugu yerde ayiriyor.
#
# GEREKLI AMA YETERLI DEGIL: 66 ham aday -> 10 kaynak anahtarli aday, ve
# bunlarin 4'u yine cokerttti. Kaynak anahtari "UI'da gorunur" demek, "XML
# degeri kabul edilir" demek degil. Onun icin onu da event_probe olctu.
#
# "ONCEKI BUTON" SORUSU KAPANDI: OnNextButtonClick'in kaynak anahtari var,
# OnPreviousButtonClick'inki YOK. Tek aday OnPreviousGesture idi ve o da
# COKERTIYOR. Yani simetrik bir "onceki buton" olayi yok -- "bulunamadi"
# degil, olculdu.
EVENTS = (
    # nesne olaylari
    "OnClick", "OnDoubleClick", "OnRightClick", "OnMouseHover",
    "OnKeyPress", "OnDrop", "OnIntersect",
    # 2026-08-24 turu: motorun UI kaynak anahtarlarindan turetilip
    # event_probe ile ayri ayri olculdu (asagidaki nota bak)
    "OnHover", "OnStopIntersect", "OnClicksOutSide",
    # zaman cizelgesi
    "OnStart", "OnEnd", "OnTimelineEvent", "OnAnimationComplete",
    "OnMediaComplete",
    # giris / gezinme
    "OnLostFocus", "OnNextButtonClick",
    "OnEntersSlide", "OnLeavesSlide",
    # durum ve kontroller
    "OnStateChange", "OnDialTurns", "OnSliderMoves",
    # degisken -- JS koprusunun dayandigi olay: JS SetVar yapinca Storyline
    # tarafi buna tepki verir
    "OnVariableValueChange",
)

# Yazildiginda Storyline'i cokerten adlar. "Bilinmeyen olay" demek yetmez:
# bu adlarin bazilari makul gorunuyor ve biri bu projede aylarca gecerli
# listede durdu. Hata mesaji ne oldugunu ve varsa karsiligini soylesin.
COKERTEN_EVENTS = {
    # 2026-08-24 turu, kaynak anahtari VAR ama XML degeri kabul edilmiyor
    "OnClickFailure": "Kaynak anahtari var ama XML'de COKERTIYOR (olculdu).",
    "OnGesture": "Kaynak anahtari var ama XML'de COKERTIYOR (olculdu).",
    "OnNextGesture": "Kaynak anahtari var ama XML'de COKERTIYOR (olculdu). "
                     "Gezinme icin OnNextButtonClick kullanin.",
    "OnPreviousGesture": "Kaynak anahtari var ama XML'de COKERTIYOR (olculdu). "
                         "Simetrik bir 'onceki buton' olayi YOK -- "
                         "OnPreviousButtonClick'in kaynak anahtari da yok.",
    "OnSlideEnd": "Bunun yerine OnEnd kullanin (olculdu).",
    "OnPrevButtonClick": ("Storyline'da onceki-buton olayi yok gorunuyor: "
                          "OnPreviousButtonClick ve OnPrevButton da cokuyor. "
                          "PreviousButton yalnizca HEDEF olarak kullanilabilir "
                          "(change_state)."),
    "OnPreviousButtonClick": "Bkz. OnPrevButtonClick.",
    "OnPrevButton": "Bkz. OnPrevButtonClick.",
    "ObjectLosesFocus": "Bu bir UI adi; XML karsiligi OnLostFocus.",
    "OnSubmitButtonClick": "Olculdu: cokertiyor. Gonderme submitInteraction ile kurulur.",
    "OnFinishButtonClick": "Olculdu: cokertiyor.",
    "OnFirstButtonClick": "Olculdu: cokertiyor.",
    "OnLastButtonClick": "Olculdu: cokertiyor.",
}


# --------------------------------------------------------------- variables


def list_variables(pkg: StoryPackage) -> list[dict]:
    return [v for v in model.variables(pkg) if v["type"] == "user"]


def add_variable(pkg: StoryPackage, name: str, kind: str = "num",
                 default: str | float | bool | None = None) -> dict:
    """Create a user variable.

    Names follow Storyline's own rule -- letters, digits and underscore, not
    starting with a digit -- because a name it will not accept produces a
    project that opens with the variable silently missing.
    """
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name or ""):
        raise StoryError(
            f"Gecersiz degisken adi: {name!r}. Harf veya alt cizgi ile baslamali; "
            f"harf, rakam ve alt cizgi kullanilabilir (bosluk ve Turkce karakter yok)."
        )
    data_type = VAR_TYPES.get((kind or "num").lower())
    if data_type is None:
        raise StoryError(f"Bilinmeyen tip: {kind!r}. num, text veya bool olmali.")

    if data_type == "num":
        sorun = sayi_sorunu(default, literal=False)
        if sorun:
            raise StoryError(f"Degisken {name!r} icin gecersiz varsayilan: {sorun}")

    story = pkg.parse(STORY_PART)
    var_list = story.find("varLst")
    if var_list is None:
        raise StoryError("story.xml icinde varLst yok.")
    for existing in var_list:
        if (existing.get("name") or "").casefold() == name.casefold():
            raise StoryError(f"Bu isimde bir degisken zaten var: {name}")

    if default is None:
        value = {"num": "0", "text": "", "bool": "False"}[data_type]
    elif data_type == "bool":
        value = "True" if str(default).strip().lower() in ("true", "1", "dogru", "evet") else "False"
    else:
        value = str(default)

    guid = new_guid()
    var = ET.SubElement(var_list, "var")
    var.set("g", guid)
    var.set("verG", new_guid())
    var.set("name", name)
    var.set("dataType", data_type)
    var.set("val", value)
    var.set("type", "user")
    var.set("propPath", "")
    var.set("isRandom", "false")
    var.set("randomMin", "0")
    var.set("randomMax", "0")
    var.set("defaultEmptyIfZero", "false")
    if data_type == "text":
        ET.SubElement(var, "localizedValue")

    pkg.replace_xml(STORY_PART, story)
    return {"name": name, "type": data_type, "default": value, "guid": guid}


def _variable(pkg: StoryPackage, name: str) -> dict:
    for var in model.variables(pkg):
        if (var["name"] or "").casefold() == (name or "").casefold():
            return var
    known = [v["name"] for v in list_variables(pkg)]
    raise StoryError(f"Degisken bulunamadi: {name!r}. Mevcut: {known}")


# ----------------------------------------------------------------- triggers


def _trigger_seed() -> ET.Element:
    seed = SEED_DIR / "trigger.xml"
    if not seed.is_file():
        raise StoryError("Tetikleyici tohumu bulunamadi.")
    return ET.fromstring(seed.read_text(encoding="utf-8"))


def _blank_trigger() -> ET.Element:
    """A fresh trigger with every slot Storyline expects, all cleared."""
    trig = _trigger_seed()
    trig.set("g", new_guid())
    trig.set("verG", new_guid())
    trig.set("name", "")
    trig.attrib.pop("copiedG", None)
    data = trig.find("data")
    data.set("enabled", "true")
    for tag in ("slide", "scene", "sldLayer"):
        node = data.find(tag)
        if node is not None:
            for key in ("jumpG", "showG", "hideG"):
                node.attrib.pop(key, None)
    conds = trig.find("condLst")
    if conds is not None:
        for child in list(conds):
            conds.remove(child)
    return trig


def _shape_by(root: ET.Element, needle: str) -> ET.Element | None:
    from .authoring import _shape_by_text_or_guid
    return _shape_by_text_or_guid(root, needle)


# HEDEF GEREKTIREN OLAYLAR -- bagisci XML'inden olculdu (2026-08-24).
#
# Bu olaylarin tetikleyicileri Storyline'in kendi dosyalarinda DAIMA nesnenin
# kendi trigLst'inde yasiyor, slaydinkinde degil:
#
#     OnDialTurns    77/77   trigLst < importedVector < shapeLst
#     OnDrop         23/23   trigLst < rect < shapeLst
#     OnStateChange   5/5    trigLst < btn  < shapeLst
#
# Ayrica OnDrop'un YOLDAS ALANI var: data/shape/dropLst, 23/23 dolu. Alanin
# olaya ait oldugu (eyleme degil) capraz tabloyla ayrildi -- iki farkli
# action'a yayiliyor (adjustVar 15, changeShapeState 8), yani action'i degil
# EVENT'i takip ediyor. `varChangeG` ile ayni sinif.
#
# NEDEN REDDEDIYORUZ, "calismiyor" DEMEDEN. Bu olaylarin calisma anindaki
# davranisi olculmedi (surukleme/durum degisimi Preview'da otomatiklestirilmedi).
# Reddin gerekcesi baska: Storyline'in KENDISININ hic uretmedigi bir bicimi
# uretmiyoruz. Bunu bir kez yaptik -- `varChangeG` bos birakildi, tetikleyici
# panelde dogru gorundu, ve HIC tetiklenmedi. Sessizce calismayan bir sey
# uretmektense reddetmek, bu projenin her kapisinda ayni tercih.
HEDEFLI_EVENTS = {
    # --- BAGISCI KANITI VAR (yukaridaki sayimlar) ---
    "OnDrop": "Surukle-birak nesnesine baglanir; ayrica drop_targets gerekir.",
    "OnStateChange": "Durumu izlenen nesneye baglanir; ayrica state_name gerekir.",
    "OnDialTurns": "Kadran nesnesine baglanir.",
    # --- BAGISCI KANITI YOK, YAPISAL CIKARIM (2026-08-24) ---
    # Bu dordu de bir NESNE hakkinda: uzerine gelme, kesisme, kesismeyi
    # birakma, disina tiklama, kaydiraci oynatma. Bagiscilarda ornekleri yok,
    # yani "nesnenin trigLst'inde yasar" OLCULMEDI; kanit iki dolayli
    # kaynaktan:
    #   * olculen uc olayin ucu de (105 ornek) istisnasiz nesnede yasiyor
    #   * motorun kendi alan tablosunda karsilik gelen listeler duruyor:
    #     intersectLst, stopIntersectLst, hoverLst -- dropLst ile ayni yerde
    # `shape` sart kosuluyor ama YOLDAS LISTE sart kosulmuyor: dropLst icin
    # 23/23'luk bir kanit vardi, bunlar icin hicbir sey yok, ve olculmemis
    # bir sarti dayatmak K29'un tersi olurdu.
    "OnHover": "Uzerine gelinen nesneye baglanir (yapisal cikarim).",
    "OnIntersect": "Kesisen nesneye baglanir (yapisal cikarim).",
    "OnStopIntersect": "Kesismeyi birakan nesneye baglanir (yapisal cikarim).",
    "OnClicksOutSide": "Disina tiklanan nesneye baglanir (yapisal cikarim).",
    "OnSliderMoves": "Kaydirac nesnesine baglanir (yapisal cikarim).",
}


def add_trigger(
    pkg: StoryPackage,
    slide: str,
    action: str,
    *,
    shape: str | None = None,
    event: str = "OnClick",
    variable: str | None = None,
    operation: str = "add",
    value: str | float | bool | None = None,
    target_slide: str | None = None,
    target_scene: str | None = None,
    layer: str | None = None,
    state: str | None = None,
    drop_targets: list[str] | None = None,
    state_name: str | None = None,
    javascript: str | None = None,
    watch: str | None = None,
    conditions: list[dict] | None = None,
) -> dict:
    """Attach a trigger to a shape, or to the slide when no shape is named.

    action: adjust_variable | jump_slide | jump_scene | show_layer | hide_layer
            | change_state | execute_javascript
    conditions: [{"variable": "Skor", "op": "gte", "value": 6}]
    """
    part = pkg.slide_part_for(slide)
    root = pkg.parse(part)
    if event in COKERTEN_EVENTS:
        raise StoryError(
            f"{event!r} Storyline'i COKERTIR -- olculdu, tools/event_probe.py. "
            f"{COKERTEN_EVENTS[event]}"
        )
    if event not in EVENTS:
        raise StoryError(f"Bilinmeyen olay: {event!r}. Secenekler: {', '.join(EVENTS)}")

    # OnVariableValueChange IZLENEN DEGISKENI ayri tasir ve bu OLCULDU:
    # `other/@varChangeG` yazilmadan olay HIC tetiklenmiyor. Iki varyant
    # preview'da yan yana kosuldu, aralarindaki tek fark bu oznitelikti:
    #
    #   v1 (oznitelik yok)  SKOR=42  KANIT=BASLANGIC    <- olay tetiklenmedi
    #   v2 (oznitelik var)  SKOR=42  KANIT=ZINCIR_TAMAM <- zincir tamam
    #
    # Yani alan olmadan trigger SESSIZCE calismiyor: dosya aciliyor, panel
    # tetikleyiciyi gosteriyor, hicbir sey olmuyor. Bu A1'in deseni --
    # "tetikleyici var" halkanin yalnizca ilki. O yuzden burada HATA
    # veriliyor: calismayan bir trigger uretmektense cagriyi reddetmek.
    #
    # `watch` ile `variable` AYRI: biri izlenen, digeri degistirilen olabilir
    # ("Skor degisince Kanit'i ayarla").
    if event == "OnVariableValueChange" and not watch:
        raise StoryError(
            "OnVariableValueChange icin watch gerekli: hangi degiskenin "
            "degisimi izlenecek. Olculdu -- watch verilmeden olay hic "
            "tetiklenmiyor ve trigger sessizce calismiyor."
        )
    # Cozumleme burada, YAZMA asagida: `data` henuz yok, ve olmayan bir
    # degisken adi cagrinin en basinda bagirmali.
    izlenen = _variable(pkg, watch) if watch else None

    owner = root
    owner_name = slide
    if shape:
        found = _shape_by(root, shape)
        if found is None:
            raise StoryError(f"{slide} icinde {shape!r} ile eslesen sekil yok.")
        owner, owner_name = found, found.get("name") or shape

    if event in HEDEFLI_EVENTS and not shape:
        raise StoryError(
            f"{event} icin `shape` zorunlu. Bu olayin tetikleyicisi "
            f"Storyline'in kendi dosyalarinda DAIMA nesnenin kendi "
            f"trigLst'inde yasiyor (olculdu, bagisci havuzu); slayda "
            f"baglanmis bir ornegi YOK. {HEDEFLI_EVENTS[event]}")
    if event == "OnDrop" and not drop_targets:
        raise StoryError(
            "OnDrop icin `drop_targets` zorunlu: hangi nesnenin uzerine "
            "birakilinca tetiklenecek. Bagiscilarin 23/23'unde "
            "data/shape/dropLst dolu ve alan EVENT'i takip ediyor (iki ayri "
            "action'a yayiliyor), yani `varChangeG` ile ayni sinif yoldas "
            "alan. Bos birakilirsa tetikleyici panelde dogru gorunur ve "
            "sessizce hic tetiklenmez.")
    if event == "OnStateChange" and not state_name:
        raise StoryError(
            "OnStateChange icin `state_name` zorunlu: hangi duruma gecince "
            "tetiklenecek (ornegin 'Dropped'). Bagiscilarin 5/5'inde "
            "data/shape/@stateName dolu. UYARI -- bu alanin olaya mi eyleme "
            "mi ait oldugu AYRILAMADI (bes ornegin besi de ayni action'i "
            "kullaniyor); sart, kanit degil ihtiyat gerekcesiyle konuldu.")

    trig = _blank_trigger()
    data = trig.find("data")
    data.set("event", event)
    if izlenen is not None:
        data.find("other").set("varChangeG", izlenen["guid"])

    if event in HEDEFLI_EVENTS:
        hedef_sekil = data.find("shape")
        if hedef_sekil is None:
            raise StoryError("Tetikleyici tohumunda data/shape yok.")
        if state_name:
            hedef_sekil.set("stateName", state_name)
        if drop_targets:
            liste = hedef_sekil.find("dropLst")
            if liste is None:
                liste = ET.SubElement(hedef_sekil, "dropLst")
            for ad in drop_targets:
                bulunan = _shape_by(root, ad)
                if bulunan is None:
                    raise StoryError(
                        f"drop_targets icinde {ad!r} ile eslesen sekil yok.")
                ET.SubElement(liste, "g").text = bulunan.get("g")
    detail: dict = {}

    if action in ("adjust_variable", "adjustVar"):
        if not variable:
            raise StoryError("adjust_variable icin variable gerekli.")
        var = _variable(pkg, variable)
        op = VAR_OPS.get((operation or "add").lower())
        if op is None:
            raise StoryError(f"Bilinmeyen islem: {operation!r}. set veya add olmali.")
        if var["data_type"] != "num" and op == "add":
            raise StoryError("add yalnizca sayisal degiskenlerde kullanilir.")
        data.set("action", "adjustVar")
        data.set("actSubType", "spec")
        other = data.find("other")
        other.set("varG", var["guid"])
        other.set("op", op)
        other.set("useVar", "false")
        if var["data_type"] == "num":
            sorun = sayi_sorunu(value, literal=True)
            if sorun:
                raise StoryError(
                    f"{var['name']!r} degiskenine yazilacak deger gecersiz: {sorun}")
        other.set("varVal1", str(value) if var["data_type"] == "text" and value else "")
        other.set("dblVal", str(value) if var["data_type"] == "num" and value is not None else "0")
        other.set("boolVal", "True" if str(value).strip().lower() in
                  ("true", "1", "dogru", "evet") else "False")
        detail = {"variable": var["name"], "op": op, "value": value}

    elif action in ("jump_slide", "jumpToSlide"):
        data.set("action", "jumpToSlide")
        node = data.find("slide")
        if target_slide:
            guid = pkg.parse(pkg.slide_part_for(target_slide)).get("g")
            node.set("jumpG", guid)
            data.set("actSubType", "spec")
        else:
            data.set("actSubType", "next")
        detail = {"target": target_slide or "(sonraki slayt)"}

    elif action in ("jump_scene", "jumpToScene"):
        story = pkg.parse(STORY_PART)
        scene = next((s for s in (story.find("sceneLst") or [])
                      if s.get("name") == target_scene), None)
        if scene is None:
            raise StoryError(f"Sahne bulunamadi: {target_scene!r}")
        data.set("action", "jumpToScene")
        data.set("actSubType", "spec")
        data.find("scene").set("jumpG", scene.get("g"))
        detail = {"target_scene": target_scene}

    elif action in ("show_layer", "hide_layer"):
        layers = root.find("sldLayerLst")
        node = next((l for l in (list(layers) if layers is not None else [])
                     if (l.get("name") or "").casefold() == (layer or "").casefold()), None)
        if node is None:
            names = [l.get("name") for l in (list(layers) if layers is not None else [])]
            raise StoryError(f"Katman bulunamadi: {layer!r}. Mevcut: {names}")
        showing = action == "show_layer"
        data.set("action", "showSubSlide" if showing else "hideSubSlide")
        data.set("actSubType", "spec")
        data.find("sldLayer").set("showG" if showing else "hideG", node.get("g"))
        detail = {"layer": node.get("name")}

    elif action in ("change_state", "changeShapeState"):
        target = _shape_by(root, shape or "")
        if target is None or not state:
            raise StoryError("change_state icin shape ve state gerekli.")
        states = target.find("stateLst")
        wanted = next((s for s in (list(states) if states is not None else [])
                       if (s.get("name") or "").casefold() == state.casefold()), None)
        if wanted is None:
            names = [s.get("name") for s in (list(states) if states is not None else [])]
            raise StoryError(f"{state!r} state'i yok. Mevcut: {names}")
        data.set("action", "changeShapeState")
        data.set("actSubType", "spec")
        node = data.find("shape")
        node.set("setStateG", wanted.get("g", NULL_GUID))
        node.set("setStateName", wanted.get("name", ""))
        node.set("setstateop", "ass")
        detail = {"shape": target.get("name"), "state": wanted.get("name")}

    elif action in ("execute_javascript", "executeJavaScript"):
        # Bicimin dordu de OLCULDU, tahmin edilmedi (tools/js_probe.py ve
        # test/_js turu, 2026-08-23):
        #
        #   action      executeJavaScript   -- DLL taramasi + Storyline'in
        #                                      kendi agent semasi, iki kaynak
        #   actSubType  spec                -- tur sonrasi AYNEN geri geldi
        #   js          ham metin           -- ElementTree `\n`'i `&#10;`
        #                                      yapiyor, Storyline koruyor
        #   dogrulama   Storyline'in Triggers paneli tetikleyiciyi
        #               "When the timeline starts on this slide / Execute
        #               JavaScript" diye GOSTERDI -- yani dosyada hayatta
        #               kalmakla kalmadi, anlamlandirildi.
        #
        # Slot tohumda hazir (`<other ... js="" ...>`), yani yeni dugum
        # yaratilmiyor: bu projede iki kez parse eden ama acilmayan XML
        # uretildi ve o riskin dusuk tarafi burasi.
        if not javascript:
            raise StoryError("execute_javascript icin javascript gerekli.")

        # XML 1.0 attribute'unda yasak kontrol karakterleri. ElementTree
        # bunlari `&#10;` gibi KACIRMAZ: sessizce yazar ve dosya geri
        # okunamaz hale gelir (olculdu -- 0x00, 0x08, 0x0B, 0x0C, 0x0E, 0x1F
        # hepsi ParseError uretti; 0x09/0x0A/0x0D gecerli ve korunuyor).
        #
        # Paket dogrulamasi da bunu yakaliyor ama verdigi mesaj
        # "not well-formed (invalid token): line 1, column 4260" -- kodunda
        # gorunmez bir karakter oldugunu soylemiyor. Burada reddetmek hem
        # daha erken hem de ne oldugunu SOYLUYOR.
        yasak = {i for i, ch in enumerate(javascript)
                 if ord(ch) < 0x20 and ch not in "\t\n\r"}
        if yasak:
            ilk = min(yasak)
            raise StoryError(
                f"JS kodunda XML'de yasak kontrol karakteri var: "
                f"{len(yasak)} adet, ilki {ilk}. konumda (0x{ord(javascript[ilk]):02X}). "
                f"Yalnizca tab, satirbasi ve satirsonu kullanilabilir; "
                f"digerleri paketi okunamaz yapar."
            )

        data.set("action", "executeJavaScript")
        data.set("actSubType", "spec")
        data.find("other").set("js", javascript)
        detail = {"javascript": javascript[:60] + ("..." if len(javascript) > 60 else ""),
                  "uzunluk": len(javascript), "satir": javascript.count("\n") + 1}

    else:
        raise StoryError(
            f"Bilinmeyen eylem: {action!r}. adjust_variable, jump_slide, "
            f"jump_scene, show_layer, hide_layer, change_state, "
            f"execute_javascript"
        )

    applied = _attach_conditions(pkg, trig, conditions or [])

    trig_list = owner.find("trigLst")
    if trig_list is None:
        trig_list = shapes.insert_in_order(owner, ET.Element("trigLst"))
    trig_list.append(trig)
    pkg.replace_xml(part, root)

    return {"slide": slide, "attached_to": owner_name, "event": event,
            "action": data.get("action"), "conditions": applied, **detail}


def _attach_conditions(pkg: StoryPackage, trig: ET.Element,
                       conditions: list[dict]) -> list[dict]:
    """Add 'only when …' clauses to a trigger."""
    if not conditions:
        return []
    cond_list = trig.find("condLst")
    if cond_list is None:
        cond_list = ET.SubElement(trig, "condLst")
    applied = []
    for spec in conditions:
        var = _variable(pkg, spec.get("variable", ""))
        op = COND_OPS.get(str(spec.get("op", "eq")).lower())
        if op is None:
            raise StoryError(f"Bilinmeyen karsilastirma: {spec.get('op')!r}")
        value = spec.get("value")
        cond = ET.SubElement(cond_list, "trigCond")
        cond.set("g", new_guid())
        cond.set("verG", new_guid())
        cond.set("lightBox", "false")
        cond.set("op", op)
        cond.set("strVal1", str(value) if var["data_type"] == "text" else "")
        cond.set("strVal2", "")
        cond.set("floatVal1", str(value) if var["data_type"] == "num" else "0")
        cond.set("floatVal2", "0")
        cond.set("boolVal", ("True" if str(value).strip().lower() in
                             ("true", "1", "dogru", "evet") else "False")
                 if var["data_type"] == "bool" else "")
        cond.set("varG", var["guid"])
        cond.set("varG2", NULL_GUID)
        cond.set("dataType", "value")
        cond.set("andOr", str(spec.get("join", "and")).lower())
        state = ET.SubElement(cond, "shapeState")
        state.set("shapeG", NULL_GUID)
        state.set("op", "eq")
        state.set("name", "Normal")
        ET.SubElement(cond, "localizedValue1")
        applied.append({"variable": var["name"], "op": op, "value": value})
    return applied
