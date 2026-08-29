"""JS yetenek katalogu -- ham kod alani DEGIL, olculmus yetenekler.

NEDEN KATALOG BIRINCIL (karar: 2026-08-23, JS_YOL_HARITASI.md J3).

  * `audit` sozcukseldir, katalog anlamsal. `jscheck` kodun PARSE edildigini
    soyler, DOGRU oldugunu degil; `model.js_references` GetVar/SetVar'in duz
    metin argumanini gorur, degiskenli cagriyi goremez. Yani ham kod
    lint'lenir, dogrulanmaz.
  * Katalog kapali kume, ham kod sonsuz girdi uzayi. Bu turun butun kazanci
    tahminden olcume gecmekti; sonsuz girdi uzayi olculemez.
  * Cagiran buyuk olasilikla bir insan degil. Tipli cagri, serbest metinden
    daha guvenilir.

Ham JS kapanmadi -- katalogun kapsamadigi is icin `audit` kapisindan gecen
ikincil yol olarak duruyor.

KATALOGA GIRIS SARTI (yol haritasinin kendi kurali): bir yetenek, YANINDA BIR
OLCUM OLMADAN katalogda yer almaz. `olcum` alani bos olan kayit yuklenmez --
modul sonundaki yapisal kontrol bunu reddeder. JS, olcum kapsaminin disina
kacmanin en kolay yolu.

ILK TURUN KAPSAMI, acikca. Yol haritasinin ilk dort adayi (LMS ogrenci adi,
PDF sertifika, localStorage devam, metin girisi dogrulama) su anda BU ORTAMDA
OLCULEMEZ: LMS yok, kutuphane gomme yolu olculmedi, metin girisi soru tipinin
klonlanabilir ornegi yok (README "Bilinen sinirlar"). Olculemeyen yetenek
kataloga giremedigi icin ilk tur, Storyline'in tek basina yapamadigi ve
Preview'da olculebilen isle kuruldu: tarih/saat, rastgele sayi, sayi bicimi,
Turkce metin karsilastirma. Hepsi `veri` kesitinde -- hicbiri slayt DOM'una
dokunmuyor.

ENJEKSIYON. Sablonlardaki her yer tutucu `__AD__` bicimindedir ve yerine
DAIMA `json.dumps` ile uretilmis tam bir JS degismezi konur. Yani sablonda
tirnak yoktur; tirnagi donusum koyar. Boylece icinde tirnak, ters bolu veya
yeni satir olan bir parametre kodu bozamaz. (Sablonun kendisi de gecerli JS
olarak parse edilebilir: `__AD__` gecerli bir JS tanimlayicisidir.)

NEDEN KODDA TURKCE HARF YOK. Sablonlardaki Turkce harfler `\\u0130` gibi JS
kacislariyla yazilmistir, harfin kendisiyle degil. `js` degeri bir XML
ozniteligine giriyor ve bu turda tam olarak "gorunmez/ozel karakter sessizce
bozuluyor" sinifindan iki kusur cikti (JS kodunda kontrol karakteri, model.py
kaynaginda 0x08). ASCII disi harflerin bu yolda saglam kaldigi OLCULMEDI;
olculmemis bir ekseni kullanmak yerine hic girmiyoruz. `json.dumps` da
`ensure_ascii=True` ile cagriliyor, boylece kullanicidan gelen metin de ASCII
kacisina cevriliyor -- yani uretilen `js` degeri bastan sona ASCII'dir.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from . import logic, model
from .logic import StoryError
from .package import StoryPackage

_YER_TUTUCU = re.compile(r"__[A-Z][A-Z0-9_]*__")


@dataclass(frozen=True)
class Parametre:
    ad: str
    tur: str                    # "degisken" | "metin" | "sayi" | "secim"
    aciklama: str
    varsayilan: object = None
    rol: str = "yazilan"        # degisken icin: "yazilan" (biz olustururuz)
    #                             veya "okunan" (zaten var olmali)
    vtur: str = "text"          # yazilan degiskenin tipi
    secenekler: tuple[str, ...] = ()


@dataclass(frozen=True)
class Yetenek:
    ad: str
    baslik: str
    aciklama: str
    kod: str
    parametreler: tuple[Parametre, ...]
    olay: str
    kesit: str          # veri | player | form | print -- "slayt" YASAK
    calismaz: str       # ne zaman calismaz; bos birakilamaz
    olcum: str          # nasil olculdu; bos birakilamaz
    # OnVariableValueChange kullanan yetenekler icin: hangi PARAMETRE izlenecek
    # degiskenin adini veriyor. `watch` olmadan bu olay HIC tetiklenmiyor --
    # olculdu, ve tetikleyici panelde dogru gorunmesine ragmen sessiz kaliyor.
    izle: str | None = None


# ----------------------------------------------------------------- katalog

_KAYITLAR = [
    Yetenek(
        ad="tarih",
        baslik="Bugunun tarihi",
        aciklama="Sistem tarihini secilen bicimde bir metin degiskenine yazar. "
                 "Storyline'in kendi degisken aritmetigi tarih uretemez.",
        kod=r"""
var p = GetPlayer();
var d = new Date();
var ik = function (n) { return (n < 10 ? "0" : "") + n; };
var s = __BICIM__;
s = s.replace("yyyy", d.getFullYear())
     .replace("aa", ik(d.getMonth() + 1))
     .replace("gg", ik(d.getDate()))
     .replace("ss", ik(d.getHours()))
     .replace("dd", ik(d.getMinutes()));
p.SetVar(__HEDEF__, s);
""".strip(),
        parametreler=(
            Parametre("hedef", "degisken", "Tarihin yazilacagi metin degiskeni",
                      "Tarih", vtur="text"),
            Parametre("bicim", "secim", "Tarih bicimi", "gg.aa.yyyy",
                      secenekler=("gg.aa.yyyy", "yyyy-aa-gg",
                                  "gg.aa.yyyy ss:dd", "ss:dd")),
        ),
        olay="OnStart",
        kesit="veri",
        calismaz="Saat dilimi ve saat izleyicinin makinesinden gelir -- sunucu "
                 "saati degildir. Makinenin saati yanlissa tarih de yanlistir.",
        olcum="Preview, 2026-08-23: bicim 'gg.aa.yyyy ss:dd' -> '23.08.2026 20:45'. Kod dosyadan bayt bayt geri okundu ve Node ile parse edildi. Dort bicimin DORDU DE olculdu (Preview, 2026-08-26): 'yyyy-aa-gg' -> 2026-08-26, 'gg.aa.yyyy' -> 26.08.2026, 'ss:dd' -> 20:40, 'gg.aa.yyyy ss:dd' -> 23.08.2026 20:45.",
    ),
    Yetenek(
        ad="rastgele",
        baslik="Rastgele tam sayi",
        aciklama="alt ile ust arasinda (ikisi dahil) rastgele bir tam sayi uretir. "
                 "Senaryo veya soru rastgelelestirmesinin girdisi.",
        kod=r"""
var p = GetPlayer();
var alt = __ALT__, ust = __UST__;
p.SetVar(__HEDEF__, Math.floor(Math.random() * (ust - alt + 1)) + alt);
""".strip(),
        parametreler=(
            Parametre("hedef", "degisken", "Sayinin yazilacagi sayi degiskeni",
                      "Rastgele", vtur="num"),
            Parametre("alt", "sayi", "En kucuk deger (dahil)", 1),
            Parametre("ust", "sayi", "En buyuk deger (dahil)", 100),
        ),
        olay="OnStart",
        kesit="veri",
        calismaz="Her tetiklemede yeniden uretir; slayda geri donuldugunde deger "
                 "degisir. Sabit kalmasi isteniyorsa yalnizca bir kez calisan bir "
                 "olaya baglanmali.",
        olcum="Preview, 2026-08-23: alt=1 ust=6 -> 4, yani aralik icinde. Alti cekilis olculdu (Preview, 2026-08-26, alt=1 ust=3): 3 2 2 1 1 3 -- IKI UC DEGER DE cikti ve aralik disina tasan yok. Dagilimin duzgunlugu (uniform mu) hala OLCULMEDI; alti cekilis buna yetmez.",
    ),
    Yetenek(
        ad="sayi_bicimi",
        baslik="Sayiyi Turkce bicimle yaz",
        aciklama="Bir sayi degiskenini binlik ayraci nokta, ondalik ayraci virgul "
                 "olacak sekilde metne cevirir. Storyline sayilari ham gosterir.",
        kod=r"""
var p = GetPlayer();
var v = Number(p.GetVar(__KAYNAK__));
if (!isFinite(v)) {
  p.SetVar(__HEDEF__, "-");
} else {
  var par = v.toFixed(__BASAMAK__).split(".");
  par[0] = par[0].replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  p.SetVar(__HEDEF__, par.join(","));
}
""".strip(),
        parametreler=(
            Parametre("kaynak", "degisken",
                      "Bicimlenecek sayi degiskeni (zaten var olmali)",
                      None, rol="okunan"),
            Parametre("hedef", "degisken", "Bicimli metnin yazilacagi degisken",
                      "Bicimli", vtur="text"),
            Parametre("basamak", "sayi", "Ondalik basamak sayisi", 0),
        ),
        olay="OnStart",
        kesit="veri",
        calismaz="STORYLINE'IN SAYI SINIRLARI UC AYRI KESITTE FARKLI -- olculdu (Preview, 2026-08-23): degisken varsayilani 8 anlamli basamak, adjust_variable sonucu 7 basamak, JS SetVar TAM. Yani bu kodun okudugu deger, oraya NASIL geldigine gore farkli hassasiyette olur. En sert ornek: 0+10000000+1 adjust_variable ile 10000000 verir, +1 hic islemez. `add_variable` ve `add_trigger` artik STATIK degerleri reddediyor ama BIRIKEN deger kapinin disinda kalir ve sessizce bozulur -- 7 basamagi asabilecek bir sayac JS ile tutulmali. Ayrica kaynak sayiya cevrilemiyorsa hedefe \"-\" yazar.",
        olcum="Preview, 2026-08-23: Puan=1234567.891, basamak=2 -> '1.234.567,90'. Beklenen '1.234.567,89' DEGILDI ve sebebi olculdu: kayip bu kodda degil, Storyline'in sayi degiskeninde (asagi bak).",
    ),
    Yetenek(
        ad="metin_karsilastir",
        baslik="Turkce metin karsilastir",
        aciklama="Iki metni Turkce kurallarina gore normalize edip karsilastirir: "
                 "I/i buyuk-kucuk farki, sapkali harfler, bastaki-sondaki bosluk. "
                 "Storyline'in kendi metin karsilastirmasi bunlarin hicbirini yapmaz.",
        kod=r"""
var p = GetPlayer();
var nrm = function (s) {
  s = String(s === null || s === undefined ? "" : s);
  s = s.replace(/I/g, "i").replace(/\u0130/g, "i").replace(/\u0131/g, "i");
  s = s.toLowerCase();
  s = s.replace(/\u015F/g, "s").replace(/\u011F/g, "g").replace(/\u00FC/g, "u")
       .replace(/\u00F6/g, "o").replace(/\u00E7/g, "c");
  return s.replace(/\s+/g, " ").replace(/^ /, "").replace(/ $/, "");
};
p.SetVar(__HEDEF__, nrm(p.GetVar(__KAYNAK__)) === nrm(__BEKLENEN__)
                    ? "DOGRU" : "YANLIS");
""".strip(),
        parametreler=(
            Parametre("kaynak", "degisken",
                      "Karsilastirilacak metin degiskeni (zaten var olmali)",
                      None, rol="okunan"),
            Parametre("beklenen", "metin", "Beklenen dogru cevap", ""),
            Parametre("hedef", "degisken",
                      "Sonucun (DOGRU/YANLIS) yazilacagi degisken", "Sonuc",
                      vtur="text"),
        ),
        olay="OnStart",
        kesit="veri",
        calismaz="Metin girisi soru tipi bu araca henuz klonlanamadigi icin kaynak "
                 "degiskenini su anda yalnizca baska bir tetikleyici doldurabilir; "
                 "kullanicidan dogrudan giris alinamaz.",
        olcum="Preview, 2026-08-23: kaynak degiskeni Turkce buyuk I (U+0130) ile 'ISTANBUL', beklenen 'istanbul' -> 'DOGRU'. Storyline'in kendi metin karsilastirmasi bu ciftte YANLIS derdi. Sapkali harf yolu AYRICA ve IKI YONLU olculdu (Preview, 2026-08-26): kaynak 'SEHIR' (S-sapkali, I-noktali), beklenen 'sehir' -> DOGRU; ayni kaynak, beklenen 'baska' -> YANLIS. Yani hep DOGRU diyen bir karsilastirma degil. Bostan kirpma yolu hala AYRI olculmedi.",
    ),
    Yetenek(
        ad="sayac",
        baslik="Sayac (JS ile, kayipsiz)",
        aciklama="Bir sayi degiskenini her tetiklemede artirir. Storyline'in "
                 "kendi 'degiskeni artir' tetikleyicisi sonucu 7 anlamli "
                 "basamaga yuvarlar; bu yol yuvarlamaz.",
        kod=r"""
var p = GetPlayer();
p.SetVar(__HEDEF__, Number(p.GetVar(__HEDEF__)) + __ADIM__);
""".strip(),
        parametreler=(
            Parametre("hedef", "degisken", "Artirilacak sayi degiskeni",
                      "Sayac", vtur="num"),
            Parametre("adim", "sayi", "Her tetiklemede eklenecek miktar", 1),
        ),
        olay="OnStart",
        kesit="veri",
        calismaz="Her TETIKLEME icin bir kez artirir -- OnStart ile bu 'her "
                 "slayt ziyareti' demektir; slayda geri donuldugunde yeniden "
                 "artar. Ayni degiskene bir yerde adjust_variable ile "
                 "yaziliyorsa O YAZMA 7 basamak kuralina tabidir ve kazanim "
                 "orada kaybolur -- sayaci tek yoldan tut. Olculen ust sinir "
                 "9 anlamli basamak; otesi OLCULMEDI. Kalicilik yalnizca "
                 "Preview'da olculdu, yayinlanmis kurs/LMS oturumunda degil.",
        olcum="Preview, 2026-08-23: hedef 10000000'den basladi, 5 kez "
              "tetiklendi -> 10000005, TAM. Ayni artis adjust_variable ile "
              "10000000'de KILITLI kaldi (5 artisin besi de islemedi). "
              "Slayt gecisinden sonra deger korundu (10000005). Ayni karede "
              "kanarya sutunu (100 -> 105) mekanizmanin calistigini gosterdi, "
              "yani kilitlenme olcum hatasi degil.",
    ),
    Yetenek(
        ad="tasma_uyarisi",
        baslik="Sayi tasmasi uyarisi",
        aciklama="Izlenen sayi degiskeni, Storyline'in aritmetik sinirina "
                 "yaklastiginda bir uyari degiskenine RISK yazar. Sinirin "
                 "otesinde artirmalar SESSIZCE islemez.",
        kod=r"""
var p = GetPlayer();
var v = Number(p.GetVar(__KAYNAK__));
p.SetVar(__HEDEF__, (isFinite(v) && Math.abs(v) >= __ESIK__) ? "RISK" : "OK");
""".strip(),
        parametreler=(
            Parametre("kaynak", "degisken",
                      "Izlenecek sayi degiskeni (zaten var olmali)",
                      None, rol="okunan"),
            Parametre("hedef", "degisken",
                      "Uyarinin (RISK/OK) yazilacagi degisken", "Tasma",
                      vtur="text"),
            Parametre("esik", "sayi",
                      "Bu buyuklukten itibaren RISK. Varsayilan, olculen "
                      "aritmetik sinirindan turetildi.",
                      10 ** logic.SAYI_ARITMETIK_BASAMAK),
        ),
        olay="OnVariableValueChange",
        izle="kaynak",
        kesit="veri",
        calismaz="NEDEN ESIK, NEDEN SAYAC KARSILASTIRMASI DEGIL: bu olay ancak "
                 "deger GERCEKTEN degistiginde tetiklenir; sayac karsilastirmasi "
                 "beklenen artis sayisini bilmeyi ve ayri bir defter tutmayi "
                 "gerektirirdi. Uyari, degisim SONRASI degeri okur -- yani "
                 "degerin oraya nasil geldigi onemli degil (olculdu: bir "
                 "birimlik yaklasma da, tek hamlelik sicrama da RISK yaziyor). "
                 "GERCEK SINIR: deger HIC degismezse olay hic tetiklenmez ve "
                 "uyari varsayilan degerinde ('-') kalir. Yani varsayilani "
                 "zaten esigin ustunde olup hic degistirilmeyen bir degisken "
                 "UYARILMAZ; onu `audit` yakalar (lossy_numbers). Ayrica esik "
                 "tam sayi +1 sayaclari icin kesindir; ondalikli veya buyuk "
                 "adimli artislarda erken/gec olabilir.",
        olcum="Preview, 2026-08-24, iki tur, ikisi de katalogun URETTIGI kodla. "
              "(1) Adim adim: kaynak 9999995'ten adjust_variable ile 10 kez +1 "
              "-> deger 10000000'de kilitlendi, uyari 'RISK'; kanarya sutunu "
              "(100'den 110'a) 'OK' kaldi, yani esik gercekten okunuyor. "
              "(2) Sicrama: 5000000'den tek hamlede 15000000'a -- hem "
              "adjust_variable literaliyle hem JS SetVar ile -- ve 15000001'e "
              "(8 basamak) JS ile; UCU DE 'RISK'. Hicbiri '-' kalmadi, yani "
              "izleyici sicramada da tetiklendi. Uyari degiskeninin varsayilani "
              "'-' oldugu icin 'hic kosmadi' ile 'kostu ve OK dedi' ayri "
              "gorunuyor.",
    ),
]

KATALOG: dict[str, Yetenek] = {y.ad: y for y in _KAYITLAR}


# ---------------------------------------------------------------- donusum


def _js_degismez(deger: object) -> str:
    """Python degerini tam bir JS degismezine cevir -- tirnaklar dahil."""
    if isinstance(deger, float) and (deger != deger or deger in (
            float("inf"), float("-inf"))):
        raise StoryError(f"Sayi degeri JS'e cevrilemez: {deger!r}")
    return json.dumps(deger, ensure_ascii=True)


def _dogrula(y: Yetenek, params: dict) -> dict:
    bilinmeyen = set(params) - {p.ad for p in y.parametreler}
    if bilinmeyen:
        raise StoryError(
            f"{y.ad}: bilinmeyen parametre {sorted(bilinmeyen)}. "
            f"Beklenen: {[p.ad for p in y.parametreler]}")

    cozulmus: dict[str, object] = {}
    for p in y.parametreler:
        deger = params.get(p.ad, p.varsayilan)
        bos = deger is None or (isinstance(deger, str) and not deger.strip())
        if bos and p.tur != "metin":
            raise StoryError(f"{y.ad}: {p.ad!r} gerekli ({p.aciklama}).")

        if p.tur == "degisken":
            ad = str(deger).strip()
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", ad):
                raise StoryError(
                    f"{y.ad}: {p.ad!r} bir degisken adi olmali -- harf veya alt "
                    f"cizgi ile baslar, harf/rakam/alt cizgi icerir: {deger!r}")
            cozulmus[p.ad] = ad
        elif p.tur == "sayi":
            try:
                sayi = float(deger)
            except (TypeError, ValueError):
                raise StoryError(
                    f"{y.ad}: {p.ad!r} sayi olmali: {deger!r}") from None
            if sayi != sayi or sayi in (float("inf"), float("-inf")):
                raise StoryError(
                    f"{y.ad}: {p.ad!r} gecerli bir sayi degil: {deger!r}")
            cozulmus[p.ad] = int(sayi) if sayi.is_integer() else sayi
        elif p.tur == "secim":
            if str(deger) not in p.secenekler:
                raise StoryError(
                    f"{y.ad}: {p.ad!r} su seceneklerden biri olmali "
                    f"{list(p.secenekler)}, gelen: {deger!r}")
            cozulmus[p.ad] = str(deger)
        else:
            cozulmus[p.ad] = "" if deger is None else str(deger)
    return cozulmus


def _doldur(y: Yetenek, cozulmus: dict) -> str:
    kod = y.kod
    for p in y.parametreler:
        kod = kod.replace(f"__{p.ad.upper()}__", _js_degismez(cozulmus[p.ad]))
    kalan = _YER_TUTUCU.findall(kod)
    if kalan:
        raise StoryError(f"{y.ad}: doldurulmamis yer tutucu kaldi: {kalan}")
    return kod


def kod_uret(ad: str, params: dict | None = None) -> str:
    """Yetenegin kodunu parametrelerle doldur -- dosyaya dokunmadan."""
    y = KATALOG.get(ad)
    if y is None:
        raise StoryError(
            f"Bilinmeyen JS yetenegi: {ad!r}. Mevcut: {sorted(KATALOG)}")
    return _doldur(y, _dogrula(y, params or {}))


# --------------------------------------------------------------- uygulama


def liste() -> list[dict]:
    """Panel ve MCP icin katalogun JSON'a cevrilebilir hali."""
    return [
        {
            "ad": y.ad,
            "baslik": y.baslik,
            "aciklama": y.aciklama,
            "olay": y.olay,
            "izlenen_parametre": y.izle,
            "kesit": y.kesit,
            "calismaz": y.calismaz,
            "olcum": y.olcum,
            "parametreler": [
                # rol ve degisken_tipi yalnizca degisken parametreleri icin
                # anlamli. Hepsine yazilsa cagiran, `bicim` icin de bir
                # degisken kurulacagini okur -- alan var diye anlami var
                # sanmak, bu turda birkac kez ayni yerden isirdi.
                {"ad": p.ad, "tur": p.tur, "aciklama": p.aciklama,
                 "varsayilan": p.varsayilan,
                 "rol": p.rol if p.tur == "degisken" else None,
                 "degisken_tipi": p.vtur if p.tur == "degisken" else None,
                 "secenekler": list(p.secenekler)}
                for p in y.parametreler
            ],
        }
        for y in _KAYITLAR
    ]


def _mevcut(pkg: StoryPackage, ad: str) -> dict | None:
    for var in model.variables(pkg):
        if (var["name"] or "").casefold() == ad.casefold():
            return var
    return None


def uygula(pkg: StoryPackage, slide: str, ad: str, *,
           params: dict | None = None, event: str | None = None,
           shape: str | None = None) -> dict:
    """Yetenegi bir slayda bagla: degiskenleri kur, tetikleyiciyi ekle.

    Tetikleyici ham JS ile AYNI yoldan gecer (`logic.add_trigger`) -- yani
    EVENTS kapisi, cokerten olay kapisi ve kontrol karakteri kapisi katalog
    icin de gecerlidir. Katalog o kapilarin YERINE gecmez, ustune biner.
    """
    y = KATALOG.get(ad)
    if y is None:
        raise StoryError(
            f"Bilinmeyen JS yetenegi: {ad!r}. Mevcut: {sorted(KATALOG)}")
    cozulmus = _dogrula(y, params or {})

    kurulan: list[dict] = []
    kullanilan: list[str] = []
    eksik: list[str] = []
    for p in y.parametreler:
        if p.tur != "degisken":
            continue
        vad = cozulmus[p.ad]
        var = _mevcut(pkg, vad)
        if p.rol == "okunan":
            (kullanilan if var is not None else eksik).append(vad)
        elif var is None:
            varsayilan = {"num": 0, "text": "-", "bool": False}[p.vtur]
            logic.add_variable(pkg, vad, p.vtur, varsayilan)
            kurulan.append({"ad": vad, "tip": p.vtur})
        else:
            # `data_type` -- `dataType` DEGIL. Ilk yazimda yanlisti ve
            # kontrol hicbir zaman eslesmedi: var olan bir degiskeni yeniden
            # kullanan her cagri "tipi None" diye reddediliyordu. Testler hep
            # taze ad kullandigi icin bu yola hic girilmedi (K26'nin ek
            # maddesi: kontrolun girdisinin GELDIGI de ayrica gorulmeli).
            if var.get("data_type") != p.vtur:
                raise StoryError(
                    f"{ad}: {vad!r} degiskeni zaten var ama tipi "
                    f"{var.get('data_type')!r}, bu yetenek {p.vtur!r} bekliyor. "
                    f"Baska bir ad ver ya da mevcut degiskeni duzelt.")
            kullanilan.append(vad)

    if eksik:
        raise StoryError(
            f"{ad}: okunacak degisken(ler) yok: {eksik}. Bu yetenek onlari "
            f"OLUSTURMAZ cunku baska bir seyin doldurmasi gerekiyor -- once "
            f"add_variable ile kur ya da dolduran tetikleyiciyi ekle.")

    kod = _doldur(y, cozulmus)
    izlenen = cozulmus[y.izle] if y.izle else None
    trig = logic.add_trigger(pkg, slide, "execute_javascript",
                             event=event or y.olay, shape=shape, javascript=kod,
                             watch=izlenen)
    return {"yetenek": ad, "slide": slide, "event": event or y.olay,
            "kurulan_degiskenler": kurulan, "kullanilan_degiskenler": kullanilan,
            "kod_uzunlugu": len(kod), "trigger": trig,
            "kesit": y.kesit, "calismaz": y.calismaz}


# ----------------------------------------------- yapisal kontrol (import ani)
#
# Sablon ile parametre listesi ayrisirsa kod SESSIZCE `__HEDEF__` iceren bir
# metin olarak yazilir -- gecerli JS'tir, hicbir sey soylemez, hicbir sey
# yapmaz. Bu turda ogrenilen sinif tam olarak bu (bkz. model.py'de 0x08).
# O yuzden ayrisma import aninda patlar.


def _kendini_dogrula() -> None:
    for y in _KAYITLAR:
        adlar = {f"__{p.ad.upper()}__" for p in y.parametreler}
        sablonda = set(_YER_TUTUCU.findall(y.kod))
        if sablonda - adlar:
            raise StoryError(
                f"jscat/{y.ad}: sablonda parametresi olmayan yer tutucu: "
                f"{sorted(sablonda - adlar)}")
        if adlar - sablonda:
            raise StoryError(
                f"jscat/{y.ad}: sablonda kullanilmayan parametre: "
                f"{sorted(adlar - sablonda)}")
        if y.kesit == "slayt":
            raise StoryError(f"jscat/{y.ad}: 'slayt' kesiti yasak.")
        if not y.calismaz.strip():
            raise StoryError(f"jscat/{y.ad}: 'calismaz' bos birakilamaz.")
        if not y.olcum.strip():
            raise StoryError(
                f"jscat/{y.ad}: 'olcum' bos. Kataloga giris sarti bir olcumdur; "
                f"olculmemis yetenek yuklenmez. Yetenegi Preview'da kostur, "
                f"gordugun sonucu buraya yaz, sonra import et.")
        if y.izle and y.izle not in {p.ad for p in y.parametreler}:
            raise StoryError(
                f"jscat/{y.ad}: izle={y.izle!r} boyle bir parametre yok.")
        if (y.olay == "OnVariableValueChange") != bool(y.izle):
            raise StoryError(
                f"jscat/{y.ad}: OnVariableValueChange ile `izle` birlikte "
                f"olmali -- olay={y.olay!r}, izle={y.izle!r}. Watch'siz bu "
                f"olay hic tetiklenmiyor (olculdu).")
        if not y.kod.isascii():
            raise StoryError(
                f"jscat/{y.ad}: sablonda ASCII disi karakter var. Turkce harfler "
                f"JS kacisiyla (\\u0130 gibi) yazilmali -- bu yolun ASCII disi "
                f"karakterle saglam kaldigi olculmedi.")


_kendini_dogrula()
