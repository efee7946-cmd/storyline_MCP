"""Ajanın yolundan kurulan bir kurs sağlam çıkıyor mu -- uçtan uca.

NICIN VAR. Suit'in kapilari arasinda kursu UCTAN UCA kuran tek adim
`yeni_modul` ve o KURUCU yolu koşuyor: `authoring` + `compose`
fonksiyonlarini dogrudan cagiriyor. Yani takim, birincil OLMAYAN yolu
uctan uca olcuyor ve birincil yapilmak istenen yolu -- ajanin MCP
yuzeyinden gectigi yolu -- hic olcmuyordu.

Fark kozmetik degil. MCP yolunda her cagri kendi `_write`'iyla bitiyor
(dosya her adimda kaydedilip yeniden okunuyor), `_guard` kilidi
kontrol ediyor, `StoryError` -> `ToolError` donusumu calisiyor ve
arac katmani sema dogrulamasi yapiyor. Bunlarin hicbiri fonksiyonlari
dogrudan cagiran bir olcude gezilmiyor.

MODEL CAGIRILMIYOR, VE BU BIR KISITLAMA DEGIL TANIM. Bu kapi
"ajanin modeli dogru araclari SECIYOR mu" diye sormuyor -- o soru
model cagirir, yavas ve deterministik degildir, ve kapilar model
cagirmaz. Sordugu sey: "bu araclardan gecen bir kurulum saglam bir
kurs uretiyor mu". Planlayici degil YOL olculuyor. Betiklenmis cagri
dizisi bir ajan kosusunun yerine gecmiyor; onun GECTIGI yolu geziyor.

IDDIA KUMESI "KURUCUYA ESIT" DEGIL, ve bu bilerek. `ilerleme` katmani
ve medya plani yapi geregi kurucuya ozel (`builder.build` icinde) ve
MCP yuzeyinde karsiliklari YOK. Esitlik iddia eden bir kapi, o yuzey
acilana kadar INSA GEREGI kirmizi kalirdi -- ve kalici kirmizi bir kapi
sinyal uretmeyi birakir (ayni gerekce `coverage --kanarya` notunda
yazili). Bugun doyurulabilir olanlar iddia ediliyor:

    1  puanlama zinciri TEMIZ           (soru -> quiz -> sonuc -> LMS)
    2  cevaplanamaz soru SIFIR
    3  sahipsiz etkilesim YOK           (puanli her slayt quiz'e kayitli)
    4  ayak izi TUTARLI                 (kurulan slaytlar farkta gorunuyor)
    5  sahne sonu ILERI YOLU SAGLAM     (sahne siniri gecilebiliyor)

MD. 5 NICIN SONRADAN EKLENDI. Kural (`ileri_zincirini_kur`) 2026-09-14'te
yazildi ama tek cagirani panelin kurucu yolu oldu; ajanin MCP yolu onu hic
gormuyordu. Kullanici ayni kusuru 2026-09-15'te yeniden bildirdi ve bu kez
kurs BU yoldan kurulmustu -- kendi dosyasinda olculdu: bes sahnenin
besinde de son slaydin ileri yolu "sonraki slayt", `jumpToScene` sifir.
Kural `server._write`e tasindi; md. 5 onun bu yuzeyden gercekten
gezildigini soruyor.

AKIS IKI SAHNE KURUYOR, ve bu md. 5'in on kosulu: tek sahneli bir akista
"sahnenin son slaydi" ile "kursun son slaydi" ayni sey olur ve yuklem
hicbir sey sormaz. Kapsamda tek sahne kalirsa md. 5 bunu KUSUR olarak
bildirir, sessizce yesil donmez.

IDDIA EDILMEYENLER, acikca: `Ilerleme` degiskeni, medya plani, sonuc
kilidi. Bunlar sohbet yolunda KURULMUYOR ve bu kapi onlari sormaz;
sorarsa kalici kirmizi olur ve okunmayi birakir.

KANARYA YUKLEMDEN ONCE YAZILDI. "Yuklemi zaten hesaplanmis olana bagla"
caresi burada YOK: bu olcu turunun ilki ve dayanacagi onceki bir deger
yok. Yerine gecen tek sey iki yonlu kanarya -- kusuru ekip olcunun
KIRMIZIYA dondugunu gormek. Uc ekim:

    a  sonuc slaydi HIC eklenmezse   -> iddia 1 kirmizi olmali
    b  questionIdLst bosaltilirsa    -> iddia 1 ve 3 kirmizi olmali
    c  dogruluk isareti silinirse    -> iddia 2 kirmizi olmali
    d  sahne gecisi bozulursa        -> iddia 5 kirmizi olmali

MD. 5 AYRICA TERS YONDEN SINANDI (2026-09-15): `_zincir_kapsami` bos
donecek sekilde kapatilinca ana kosu KIRMIZIYA dondu (5 cikmaz, ilki
`388e285d` kopuk sahne hedefi). Yani md. 5'in sifiri duzeltmenin
kostugunu gosteriyor, kendi korlugunu degil.

Ucu de kirmiziya donmezse bu kapi KOR demektir ve sifirlari okunmamali.

KANARYALARIN OMRU: MD. 3 LANDIGINDA NE OLACAK.
Ekilen bir kusuru, sonraki bir duzeltme MESRU olarak onarabilir; o gun
kanarya kirmizidan yesile doner ve okuyan kisi bunu GATE REGRESYONU
sanir. Bu yuzden karar simdi veriliyor, kapiyi sonradan yorumlamak
yerine (2026-09-11):

    MD. 3 KABLOLAMA YAPAR, GORUNUR ICERIK URETMEZ.

Yani kapanis adimi quiz kaydini, `quizG`yi ve `lmsResultSlideG`yi
tamamlar; SONUC SLAYDINI YOKTAN VAR ETMEZ. Gerekce iki tane:

  * Gorunur icerik uretmek, kullanicinin istemedigi bir TASARIM karari.
    Kablolama gorunmez tesisat -- tamamlamanin bir bedeli yok.
  * "Ara hal kusur degildir" ilkesiyle tutarli: yapim ortasinda sonuc
    slaydi olmamasi normaldir, ve o hali "duzelten" bir adim kullanicinin
    kursuna slayt ekler.

Olculdu (2026-09-11, diskteki 51 kurs): zinciri kirik 34 kursun 20'si
YALNIZCA kablolama eksigi -- md. 3 bunlari kapatir. Kalan 14'unde sonuc
slaydi HIC yok; onlar uyariya kaliyor (`puanlama.eksik_sonuc_uyarisi`).

BUNUN KANARYALARA SONUCU:
  (a) sonuc slaydi yok      -> KIRMIZI KALIR. Md. 3 onu uretmeyecek.
  (b) questionIdLst bos     -> KIRMIZI KALIR. Kusur artefakta ekiliyor ve
                               ardindan arac cagrisi yok; kablolama
                               calismiyor.
Yani md. 3 landiginda bu kapida hicbir kanarya yon degistirmemeli. Biri
degistirirse ya md. 3 gorunur icerik uretiyordur (karar degismis) ya da
kanarya kendi olcugunu kaybetmistir; ikisi de ARASTIRILMALI, sessizce
yesile alinmamali.

    python tools/ajan_yolu.py
"""

from __future__ import annotations

import asyncio
import json
import pathlib
import shutil
import sys
import warnings

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

warnings.simplefilter("ignore")

KOSAMADI = 3
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError as _eksik:                      # pragma: no cover
    ISTEMCI_YOK = str(_eksik)
else:
    ISTEMCI_YOK = ""

from storyline_mcp.package import StoryPackage      # noqa: E402
from storyline_mcp import model, oturum, puanlama   # noqa: E402
import completeness                                 # noqa: E402

# SUNUCU ACILMAZSA KAPI HUKUM VERMEZ. Asagidaki dizi bir ISARET:
# `akis` onu dondururse ortada olculmus bir sey yok ve kapi KOSAMADI (3)
# doner. Yoksa cikis 1 olur ve "sunucu acilmadi"nin TURETTIGI bulgular
# (ayak izi bos, kanarya kacti) bagimsiz kusurlarmis gibi siralanir --
# okuyan kisi olmayan uc kusur arar.
ACILMADI = "SUNUCU ACILMADI"

BLANK = ROOT.parent / "test" / "bos.story"
# `<navData>` BEYAN ETMEYEN taban: kullanicinin kendi Storyline'inda
# kaydedilmis bos proje (1 sahne / 1 slayt). Md. 6 bu tabana IHTIYAC
# DUYUYOR -- `bos.story`nin her slaydinda navData zaten var, yani orada
# yuklem hicbir zaman kimildamaz ve yesili "gecti" diye okunur.
BEYANSIZ_TABAN = ROOT.parent / "test" / "_referans" / "bos_navdatasiz.story"
CANARY = ROOT.parent / "test" / "_canary"


def _coz(res):
    veri = getattr(res, "structured_content", None)
    if veri:
        return veri
    icerik = res.content or []
    return json.loads(icerik[0].text) if icerik else {}


def _hata_mi(res) -> str:
    if getattr(res, "is_error", False):
        return " ".join((getattr(b, "text", "") or "") for b in (res.content or []))
    return ""


async def akis(yol: pathlib.Path, *, sonuc_slaydi: bool = True) -> list[str]:
    """Betiklenmis ajan kosusu: ARAC YUZEYINDEN, stdio uzerinden.

    Cagri dizisi panelin prompt'unun tarif ettigi sirayi izliyor:
    once iskelet (sahne + slayt), sonra icerik (compose), sonra olcme
    (soru), sonra kapanis (sonuc slaydi), sonra hareket.
    """
    hatalar: list[str] = []
    params = StdioServerParameters(
        command=sys.executable,
        args=["-c", "from storyline_mcp.server import main; main()"], env=None)
    # ALT SURECIN STDERR'I TAMPONLANIYOR -- YUTULMUYOR.
    #
    # Ilk surum `os.devnull` yaziyordu ve kararli durumda dogruydu:
    # sunucu kalibrasyon uyarilari basiyor ve suit'in "son satir"
    # sutununda kapinin HUKMU yerine o uyari goruunuyordu. Ama kosulsuz
    # yutmak, sunucu HIC ACILMAZSA (import hatasi, eksik bagimlilik,
    # sozdizimi kusuru) traceback'i de yutuyor ve elde yalnizca
    # "oturum baslatilamadi" kaliyor.
    #
    # Bu tam olarak bu deponun ayirdigi hal: KOSAMADI ile KOSTU-VE-DUSTU.
    # Tampon ikisini birden veriyor: basarida dusuyor, el sikisma
    # duserse geri sarilip BASILIYOR. Bir kez ve en kotu anda isiracak
    # turden bir kusurdu.
    import tempfile
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8",
                                errors="replace") as _tampon:
        async with stdio_client(params, errlog=_tampon) as (r, w):
            async with ClientSession(r, w) as s:
                try:
                    await s.initialize()
                except BaseException as _acilis:
                    # KOSAMADI, KOSTU-VE-DUSTU DEGIL. Sunucu acilmadiysa
                    # sebep alt surecin stderr'inde duruyor; tampon tam
                    # bunun icin var.
                    _tampon.seek(0)
                    _ciktisi = (_tampon.read() or "").strip()
                    print("SUNUCU ACILMADI (%s). Alt surecin stderr'i:"
                          % type(_acilis).__name__)
                    print(_ciktisi[-1500:] if _ciktisi else "  (stderr BOS)")
                    hatalar.append(
                        "SUNUCU ACILMADI: %s -- ajan yolu OLCULEMEDI "
                        "(stderr yukarida)" % type(_acilis).__name__)
                    return hatalar

                async def cagir(ad, **kw):
                    res = await s.call_tool(ad, {"path": str(yol), "in_place": True,
                                                 **kw})
                    hata = _hata_mi(res)
                    if hata:
                        hatalar.append(f"{ad}: {hata[:110]}")
                        return {}
                    return _coz(res)

                await cagir("add_scene", name="01_Giris")
                # SESSIZ DUSME OLMASIN: sablon listesi cozulemezse sabit bir
                # ada dusmek, `list_templates` cagrisini olcunun disina
                # cikarir ve kapi onu gezdigini SANIR.
                ham = await cagir("list_templates")
                liste = ham.get("result") if isinstance(ham, dict) else ham
                if not isinstance(liste, list):
                    liste = []
                adaylar = [t["slide"] for t in liste
                           if isinstance(t, dict) and t.get("kind") == "content"]
                if not adaylar:
                    hatalar.append(
                        "list_templates icerik sablonu vermedi (donus: "
                        + str(ham)[:60] + ") -- akis sabit bir ada dusuyor ve "
                        "bu cagri OLCULMUYOR")
                    sablon = "slide7.xml"
                else:
                    sablon = adaylar[0]

                for i, (duzen, baslik) in enumerate(
                        (("cover", "Kurs Kapagi"), ("content", "Neden Onemli"),
                         ("bullets", "Uc Kural"))):
                    yeni = await cagir("add_slide", template=sablon,
                                       scene="01_Giris", name=baslik)
                    slayt = yeni.get("new_slide")
                    if not slayt:
                        hatalar.append(f"add_slide donusunde new_slide yok ({yeni})")
                        continue
                    await cagir("compose_slide", slide=slayt, layout=duzen,
                                title=baslik, body="Kisa bir govde metni.",
                                bullets=["Bir", "Iki", "Uc"] if duzen == "bullets"
                                else None,
                                eyebrow="01_Giris", theme="gece")

                # IKINCI SAHNE: SAHNE SINIRI OLMADAN sahne sonu olculemez.
                # Tek sahneli bir akista "sahnenin son slaydi" ile "kursun
                # son slaydi" ayni sey ve iddia 5 hicbir sey sormaz --
                # yuklem bir kesitte kimildamiyorsa yesil, sorunun
                # sorulamamasidir.
                await cagir("add_scene", name="02_Uygulama")
                for duzen, baslik in (("content", "Nasil Uygulanir"),
                                      ("bullets", "Iki Adim")):
                    yeni2 = await cagir("add_slide", template=sablon,
                                        scene="02_Uygulama", name=baslik)
                    slayt2 = yeni2.get("new_slide")
                    if not slayt2:
                        hatalar.append(f"add_slide donusunde new_slide yok ({yeni2})")
                        continue
                    await cagir("compose_slide", slide=slayt2, layout=duzen,
                                title=baslik, body="Kisa bir govde metni.",
                                bullets=["Bir", "Iki"] if duzen == "bullets" else None,
                                eyebrow="02_Uygulama", theme="gece")

                for i in range(2):
                    await cagir("add_question", prompt=f"Soru {i + 1}?",
                                choices=["a", "b", "c", "d"], correct=[i % 4],
                                eyebrow="01_Giris", theme="gece",
                                feedback={"correct": "Dogru, cunku olcut budur.",
                                          "incorrect": "Hayir; olcut sudur."})

                if sonuc_slaydi:
                    await cagir("add_results_slide")
                await cagir("animate_slide", preset="sakin")
    return hatalar


KURULAN_SAHNELER = ("01_Giris", "02_Uygulama")


def _kapsam(pkg: StoryPackage) -> list[str]:
    """Bu akisin KURDUGU sahneler, sceneLst sirasinda.

    Kapsam sunucunun surec-ici kaydindan OKUNMUYOR: kapi ayri bir surecte
    kosuyor ve zaten kendi ne kurdugunu biliyor. Denetledigi kodun
    kapsam cozucusunu cagirmak, o cozucudeki bir kusuru gormemek olurdu.
    """
    story = pkg.parse("story/story.xml")
    return [sc.get("g") for sc in (story.find("sceneLst") or [])
            if sc.get("name") in KURULAN_SAHNELER and sc.get("g")]


def _sahne_sonu_cikmazlari(pkg: StoryPackage, kapsam: list[str]) -> list[str]:
    """Sahne SINIRINDA olu kalan ileri yollari; akisin sonu haric.

    AKISIN SONU DISARIDA ve bu gevseme degil SOZLESME: `_write` zinciri
    `kapat_son=False` ile kuruyor, cunku ajan yolunda kurs parca parca
    buyuyor ve bugunun son sahnesi yarin ortada kalabilir. Kursun
    sonundaki olu ileri dugmesini kapatmak kurucu yolun isi
    (`son_slaydin_ilerisini_kapat`); onu burada istemek kapiyi INSA
    GEREGI kalici kirmiziya cevirirdi, ve kalici kirmizi bir kapi sinyal
    uretmeyi birakir.

    KAPSAMDA TEK SAHNE VARSA IDDIA BOSTUR ve bu bir KUSUR olarak
    dondurulur, sessizce yesil degil: sahne siniri olmayan bir akista bu
    yuklem hicbir sey sormaz ve yesili "gecti" diye okunur.
    """
    if len(kapsam) < 2:
        return ["KAPSAMDA TEK SAHNE: sahne siniri yok, iddia 5 hicbir sey "
                "olcmedi (akis iki sahne kurmali)"]
    index = model.slide_index(pkg)
    son_sahne = kapsam[-1]
    uyeler = sorted((r for r in index.values() if r.scene_guid == son_sahne),
                    key=lambda r: r.position)
    akisin_son_slaydi = uyeler[-1].basename if uyeler else ""
    return [f"{slayt} ({sahne}): {neden}"
            for slayt, sahne, neden in completeness.ileri_cikmazlari(pkg, kapsam)
            if slayt != akisin_son_slaydi]


async def akis_beyansiz(yol: pathlib.Path) -> list[str]:
    """`<navData>` beyan etmeyen bir tabandan KISA bir kurulum.

    Kullanicinin kurdugu sekli izliyor: taban sahnesine de slayt
    ekleniyor (onun dosyasinda 'Intro Scene' 1 -> 2 slayt oldu), cunku
    kursun ILK slaydi devralinandir ve eksikligi tam orada tasir.
    """
    hatalar: list[str] = []
    params = StdioServerParameters(
        command=sys.executable,
        args=["-c", "from storyline_mcp.server import main; main()"], env=None)
    import tempfile
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8",
                                errors="replace") as _tampon:
        async with stdio_client(params, errlog=_tampon) as (r, w):
            async with ClientSession(r, w) as sess:
                try:
                    await sess.initialize()
                except BaseException as _acilis:
                    hatalar.append("SUNUCU ACILMADI: %s" % type(_acilis).__name__)
                    return hatalar

                async def cagir(ad, **kw):
                    res = await sess.call_tool(
                        ad, {"path": str(yol), "in_place": True, **kw})
                    hata = _hata_mi(res)
                    if hata:
                        hatalar.append(f"{ad}: {hata[:110]}")
                        return {}
                    return _coz(res)

                await cagir("add_slide", template="slide.xml",
                            scene="Intro Scene", name="Kapak")
                for ad in ("A_Bolum", "B_Bolum"):
                    await cagir("add_scene", name=ad)
                    await cagir("add_slide", template="slide.xml",
                                scene=ad, name=f"{ad}_1")
    return hatalar


def _tum_sahneler(pkg: StoryPackage) -> list[str]:
    story = pkg.parse("story/story.xml")
    return [sc.get("g") for sc in (story.find("sceneLst") or []) if sc.get("g")]


def _beyansiz_slaytlar(pkg: StoryPackage, kapsam: list[str]) -> list[str]:
    """Kapsamda GERI tetikleyicisi tasiyip `<navData>` BEYAN ETMEYEN slaytlar.

    Kullanicinin 2026-09-15'te bildirdigi ikinci kusurun olcusu: "geri
    tusu calismiyor ama hala". `<navData>` slaydin hangi oynatici
    dugmelerini gosterdigini beyan eden eleman; beyan yoksa
    `NavigationIntent="Previous"` tasiyan tetikleyicinin baglanacagi bir
    GERI dugmesi de yok -- ve Storyline onu "Unassigned" gosteriyor.

    ILERI BU YUKLEMIN DISINDA ve sebebi ayni resmin parcasi: onun olayi
    (`OnNextButtonClick`) dogrudan bir oynatici olayi, slaydin beyanina
    bagli degil. O yuzden ILERI calisirken GERI calismiyordu.
    """
    index = model.slide_index(pkg)
    kapsam_kume = set(kapsam)
    out = []
    for ref in index.values():
        if ref.scene_guid not in kapsam_kume:
            continue
        root = pkg.parse(ref.part)
        if root.find("navData") is not None:
            continue
        if any(t.find("data") is not None
               and t.find("data").get("NavigationIntent") == "Previous"
               for t in root.iter("trig")):
            out.append(ref.basename)
    return sorted(out)


def iddialar(yol: pathlib.Path, *, beklenen_yeni_slayt: int) -> list[str]:
    """Kurulan kursun IDDIALARI. Kurucuya esitlik ARANMIYOR (bkz. baslik)."""
    kusur: list[str] = []
    pkg = StoryPackage(yol)
    index = model.slide_index(pkg)

    # 1. PUANLAMA ZINCIRI
    z = puanlama.zincir(pkg)
    if z:
        kusur.append(f"zincir KIRIK ({len(z)}): {z[0][:100]}")

    # 2. CEVAPLANAMAZ SORU
    c = puanlama.cevaplanamaz(pkg, index)
    if c:
        kusur.append(f"cevaplanamaz soru {len(c)}: {c[0]['slide']} "
                     f"({c[0]['problem'][:60]})")

    # 3. SAHIPSIZ ETKILESIM
    iz = puanlama.izleme(pkg, index)
    kayitli = set(iz.get("registered") or [])
    puanli = puanlama.puanli_slaytlar(pkg, index)
    sahipsiz = [b for b in puanli if b not in kayitli]
    if sahipsiz:
        kusur.append(f"{len(sahipsiz)} puanli slayt quiz'e KAYITLI DEGIL "
                     f"({', '.join(sahipsiz[:3])}): puanlari toplama girmez")

    # 5. SAHNE SONU ILERI YOLU
    #
    # Kullanicinin 2026-09-15'te ikinci kez bildirdigi kusur: "bir
    # sahnenin son slaydindan digerinin ilk slaydina gecmiyor". Kural
    # `server._write`te duruyor; bu iddia onun MCP yuzeyinden GERCEKTEN
    # gezildigini soruyor -- ilk yazildiginda kural yalnizca panelin
    # kurucu yolundaydi ve ajanin yolu onu hic gormuyordu.
    kopuk = _sahne_sonu_cikmazlari(pkg, _kapsam(pkg))
    if kopuk:
        kusur.append(f"sahne sonu ILERI YOLU olu ({len(kopuk)}): {kopuk[0][:90]}")

    # 6. SLAYT OYNATICI DUGMELERINI BEYAN EDIYOR
    beyansiz = _beyansiz_slaytlar(pkg, _kapsam(pkg))
    if beyansiz:
        kusur.append(f"{len(beyansiz)} slayt GERI tetikleyicisi tasiyor ama "
                     f"navData BEYAN ETMIYOR ({', '.join(beyansiz[:3])}): "
                     f"geri dugmesi baglanamaz")

    # 4. AYAK IZI
    f = oturum.fark(yol)
    if not f["anlik_goruntu"]:
        kusur.append("ayak izi OLCULEMEDI: kosu basi anlik goruntusu yok")
    elif len(f["eklenen_slaytlar"]) < beklenen_yeni_slayt:
        kusur.append(f"ayak izi EKSIK: {beklenen_yeni_slayt} slayt kuruldu ama "
                     f"farkta {len(f['eklenen_slaytlar'])} gorunuyor")
    return kusur


def _hazirla(ad: str) -> pathlib.Path:
    CANARY.mkdir(parents=True, exist_ok=True)
    yol = CANARY / ad
    for ek in (oturum.ANLIK_UZANTI, oturum.KUNYE_UZANTI, ".gerialma.bak"):
        (yol.with_suffix(yol.suffix + ek)).unlink(missing_ok=True)
    shutil.copy2(BLANK, yol)
    oturum.anlik_goruntu(yol, etiket="ajan yolu kapisi")
    return yol


def kos() -> list[str]:
    kusur: list[str] = []

    # --- ANA KOSU
    yol = _hazirla("ajan_yolu.story")
    arac_hatalari = asyncio.run(akis(yol))
    if any(h.startswith(ACILMADI) for h in arac_hatalari):
        # Turetilmis bulgulari SIRALAMA: hicbiri olculmedi.
        return [ACILMADI]
    if arac_hatalari:
        kusur.append(f"{len(arac_hatalari)} arac cagrisi HATA dondu: "
                     f"{arac_hatalari[0]}")
    ana = iddialar(yol, beklenen_yeni_slayt=8)
    print(f"ana kosu    : {len(ana)} kusur" +
          ("" if not ana else " -> " + ana[0][:70]))
    kusur.extend(f"AJAN YOLU: {k}" for k in ana)

    # --- KANARYA (a): SONUC SLAYDI YOK -> iddia 1 kirmizi olmali
    yol_a = _hazirla("ajan_yolu_kanarya_a.story")
    asyncio.run(akis(yol_a, sonuc_slaydi=False))
    a = iddialar(yol_a, beklenen_yeni_slayt=7)
    zincir_a = [k for k in a if k.startswith("zincir")]
    print(f"kanarya (a) : sonuc slaydi yok -> "
          f"{'YAKALANDI' if zincir_a else 'KACTI'}")
    if not zincir_a:
        kusur.append("OLCU KOR (a): sonuc slaydi hic eklenmedigi halde zincir "
                     "temiz gorunuyor -- iddia 1 hicbir sey olcmuyor")

    # --- KANARYA (b): questionIdLst bosaltilir -> iddia 1 ve 3 kirmizi
    yol_b = CANARY / "ajan_yolu_kanarya_b.story"
    shutil.copy2(yol, yol_b)
    for ek in (oturum.ANLIK_UZANTI, oturum.KUNYE_UZANTI):
        shutil.copy2(yol.with_suffix(yol.suffix + ek),
                     yol_b.with_suffix(yol_b.suffix + ek))
    pk_b = StoryPackage(yol_b)
    story = pk_b.parse("story/story.xml")
    silinen = 0
    for liste in story.iter("questionIdLst"):
        for oge in list(liste):
            liste.remove(oge)
            silinen += 1
    pk_b.replace_xml("story/story.xml", story)
    pk_b.save(yol_b, backup=False)
    b = iddialar(yol_b, beklenen_yeni_slayt=8)
    print(f"kanarya (b) : {silinen} quiz kaydi silindi -> "
          f"{len(b)} iddia kirmizi")
    if silinen and not b:
        kusur.append("OLCU KOR (b): quiz kayitlari silindigi halde butun "
                     "iddialar temiz -- zincir ve sahipsizlik olculmuyor")
    if not silinen:
        kusur.append("KANARYA KURULAMADI (b): silinecek quiz kaydi yoktu -- "
                     "ana kosu zaten kayitsiz olabilir")

    # --- KANARYA (c): dogruluk isareti silinir -> iddia 2 kirmizi
    yol_c = CANARY / "ajan_yolu_kanarya_c.story"
    shutil.copy2(yol, yol_c)
    for ek in (oturum.ANLIK_UZANTI, oturum.KUNYE_UZANTI):
        shutil.copy2(yol.with_suffix(yol.suffix + ek),
                     yol_c.with_suffix(yol_c.suffix + ek))
    pk_c = StoryPackage(yol_c)
    bozulan = 0
    for part in model.slide_index(pk_c):
        kok = pk_c.parse(part)
        degisti = False
        for intr in kok.iter():
            if intr.tag not in ("freePickOneIntr", "freePickManyIntr"):
                continue
            for secenek in (intr.find("choices") or []):
                sd = secenek.find("scoringData")
                if sd is not None and (sd.get("correct") or "").lower() == "true":
                    sd.set("correct", "false")
                    bozulan += 1
                    degisti = True
        if degisti:
            pk_c.replace_xml(part, kok)
    pk_c.save(yol_c, backup=False)
    c = iddialar(yol_c, beklenen_yeni_slayt=8)
    cev_c = [k for k in c if k.startswith("cevaplanamaz")]
    print(f"kanarya (c) : {bozulan} dogruluk isareti silindi -> "
          f"{'YAKALANDI' if cev_c else 'KACTI'}")
    if bozulan and not cev_c:
        kusur.append("OLCU KOR (c): dogruluk isaretleri silindigi halde "
                     "cevaplanamaz soru sayisi sifir -- iddia 2 olcmuyor")
    if not bozulan:
        kusur.append("KANARYA KURULAMADI (c): bozulacak dogruluk isareti "
                     "yoktu -- ana kosu soru kurmamis olabilir")

    # --- KANARYA (d): sahne sonu baglantisi bozulur -> iddia 5 kirmizi
    #
    # EKILEN KUSUR, KULLANICININ BILDIRDIGI HALIN TA KENDISI: sahne
    # sonundaki `jumpToScene` "sonraki slayt"a ceviriliyor -- sahnenin son
    # slaydinda gidecek slayt yoktur, dugme sessizce hicbir sey yapmaz.
    # Ana kosudaki sifir, ancak bu ekim KIRMIZIYA donerse bir sey soyler.
    yol_d = CANARY / "ajan_yolu_kanarya_d.story"
    shutil.copy2(yol, yol_d)
    pk_d = StoryPackage(yol_d)
    kapsam_d = _kapsam(pk_d)
    idx_d = model.slide_index(pk_d)
    ekilen = 0
    for sahne_guid in kapsam_d:
        uyeler = sorted((r for r in idx_d.values() if r.scene_guid == sahne_guid),
                        key=lambda r: r.position)
        if not uyeler:
            continue
        kok = pk_d.parse(uyeler[-1].part)
        degisti = False
        for trig in kok.iter("trig"):
            veri = trig.find("data")
            if veri is None or veri.get("action") != "jumpToScene":
                continue
            veri.set("action", "jumpToSlide")
            veri.set("actSubType", "next")
            sahne = veri.find("scene")
            if sahne is not None:
                sahne.attrib.pop("jumpG", None)
            degisti = True
            ekilen += 1
        if degisti:
            pk_d.replace_xml(uyeler[-1].part, kok)
    pk_d.save(yol_d, backup=False)
    pk_d2 = StoryPackage(yol_d)
    d = _sahne_sonu_cikmazlari(pk_d2, _kapsam(pk_d2))
    print(f"kanarya (d) : {ekilen} sahne gecisi bozuldu -> "
          f"{'YAKALANDI' if d else 'KACTI'}")
    if ekilen and not d:
        kusur.append("OLCU KOR (d): sahne gecisleri bozuldugu halde sahne "
                     "sonu cikmazi sifir -- iddia 5 olcmuyor")
    if not ekilen:
        kusur.append("KANARYA KURULAMADI (d): bozulacak sahne gecisi yoktu "
                     "-- zincir hic kurulmamis olabilir")

    # --- BEYANSIZ TABAN KOSUSU: md. 6 ancak burada kimildar
    #
    # FIKSTUR YOKSA "GECTI" DEGIL "BAKILMADI". `test/` bu depoda
    # .gitignore altinda, yani taban her calisma agacinda bulunmayabilir.
    # Eksik bir fiksturu sessizce atlamak, md. 6'yi hic kosmadigi halde
    # yesil gosterirdi -- bu deponun ayirdigi tam o hal.
    if not BEYANSIZ_TABAN.is_file():
        print(f"beyansiz tb : BAKILMADI -- fikstur yok ({BEYANSIZ_TABAN.name})")
        kusur.append(f"MD. 6 BAKILMADI: {BEYANSIZ_TABAN.name} yok; navData "
                     f"beyani OLCULMEDI ('gecti' degil)")
        return kusur
    yol_n = CANARY / "ajan_yolu_beyansiz.story"
    for ek in (oturum.ANLIK_UZANTI, oturum.KUNYE_UZANTI, ".gerialma.bak"):
        (yol_n.with_suffix(yol_n.suffix + ek)).unlink(missing_ok=True)
    shutil.copy2(BEYANSIZ_TABAN, yol_n)
    n_hatalari = asyncio.run(akis_beyansiz(yol_n))
    if any(h.startswith(ACILMADI) for h in n_hatalari):
        return [ACILMADI]
    if n_hatalari:
        kusur.append(f"beyansiz taban kosusunda {len(n_hatalari)} arac hatasi: "
                     f"{n_hatalari[0]}")
    pk_n = StoryPackage(yol_n)
    beyansiz = _beyansiz_slaytlar(pk_n, _tum_sahneler(pk_n))
    print(f"beyansiz tb : {len(beyansiz)} slayt navData beyan etmiyor")
    if beyansiz:
        kusur.append(f"AJAN YOLU (beyansiz taban): {len(beyansiz)} slayt GERI "
                     f"tetikleyicisi tasiyor ama navData BEYAN ETMIYOR "
                     f"({', '.join(beyansiz[:3])})")

    # --- KANARYA (e): navData silinir -> md. 6 kirmizi olmali
    yol_e = CANARY / "ajan_yolu_kanarya_e.story"
    shutil.copy2(yol_n, yol_e)
    pk_e = StoryPackage(yol_e)
    silinen = 0
    for ref in model.slide_index(pk_e).values():
        kok = pk_e.parse(ref.part)
        nav = kok.find("navData")
        if nav is None:
            continue
        kok.remove(nav)
        pk_e.replace_xml(ref.part, kok)
        silinen += 1
    pk_e.save(yol_e, backup=False)
    pk_e2 = StoryPackage(yol_e)
    e = _beyansiz_slaytlar(pk_e2, _tum_sahneler(pk_e2))
    print(f"kanarya (e) : {silinen} navData silindi -> "
          f"{'YAKALANDI' if e else 'KACTI'}")
    if silinen and not e:
        kusur.append("OLCU KOR (e): navData'lar silindigi halde beyansiz "
                     "slayt sifir -- md. 6 olcmuyor")
    if not silinen:
        kusur.append("KANARYA KURULAMADI (e): silinecek navData yoktu -- "
                     "beyansiz taban kosusu slayt kurmamis olabilir")
    return kusur


def main() -> int:
    if ISTEMCI_YOK:
        print(f"KOSAMADI: mcp istemcisi yok ({ISTEMCI_YOK}). Ajan yolu "
              f"olculemedi -- 'gecti' DEGIL, 'bakilmadi'.")
        return KOSAMADI
    if not BLANK.exists():
        print(f"KOSAMADI: fikstur yok ({BLANK}).")
        return KOSAMADI
    kusur = kos()
    if kusur == [ACILMADI]:
        print("")
        print("KOSAMADI: sunucu acilmadi (sebep yukarida). Ajan yolu olculemedi "
              "-- bu 'gecti' DEGIL, 'bakilmadi'.")
        return KOSAMADI
    if kusur:
        print("\nKAPI KALDI:")
        for k in kusur:
            print(f"  - {k}")
        return 1
    print("\nkapi gecti: arac yuzeyinden kurulan kurs puanlanabilir, "
          "cevaplanabilir, kayitli ve ayak izi tutarli")
    print("KAPSAM: PLANLAYICI OLCULMEDI -- model cagrilmiyor, cagri dizisi\n"
          "        betiklenmis. 'Ajan dogru araclari secer mi' ayri bir\n"
          "        soru ve bu kapi onu SORMAZ.\n"
          "        IDDIA EDILMEYENLER: Ilerleme degiskeni, medya plani,\n"
          "        sonuc kilidi -- bunlar kurucu yola ozel ve sohbet\n"
          "        yolunda kurulmuyor (yol haritasi md. 3).")
    return 0


if __name__ == "__main__":
    # KANARYA KILIDI. Kapilar `test/_canary/` icine SABIT adli dosyalar
    # yaziyor; iki kosu ayni anda ayni dosyaya yazarsa ikisi de yanlis
    # okur ve sonuc "kostu ve dustu" gibi gorunur. Gerekce ve olcum:
    # tools/kanarya_kilit.py.
    from kanarya_kilit import korumali
    raise SystemExit(korumali(main))
