"""Dallanma: yanlis cevap ogrenciyi baska yere goturur.

NICIN VAR: uretilen soru slaydinda yanlis cevabin sonucu HICBIR SEYDI.
Olculdu 2026-09-04, uretilmis kursta:

    katman[0]  Button  OnClick -> jumpToSlide(next)    dogru: devam et
    katman[1]  Button  OnClick -> hideSubSlide(me)     yanlis: kapat, kal

Yanlis cevap veren ogrenci katmani kapatiyor ve ayni yerde kaliyor. Ne
konuya donuyor, ne bir kayit tutuluyor. Kullanicinin tablosunda "kosullar
(if/then)" satirinin karsiligi tam olarak buydu.

NE KURULUYOR, sahne basina:

    <Bolum>_Hata (bool)   yanlis katman ACILINCA kalkar
    "Konuya don" butonu   yanlis katmanda, sahnenin ILK icerik slaydina atlar

Bayrak katmanin KENDI tetikleyicisinden kalkiyor, butondan degil: butona
baglansaydi ancak ogrenci TIKLARSA kayit olurdu ve "hangi konuda yanildi"
sorusu, ogrencinin telafiyi secmesine bagli kalirdi.

YANLIS KATMANI NASIL BULUYORUZ -- BU KISIM OLCULDU VE SEZGI YANLISTI.
Ilk akla gelen "katman[1] yanlistir" varsayimi UC AILEDEN BIRINDE TERS:

    slide29 (dragDrop)      katman[0]=Dogru   katman[1]=Yanlis
    slide2d (freePickMany)  katman[0]=YANLIS  katman[1]=Dogru   <-- ters
    slide32 (freePickOne)   adlar dolu: 'Dogru Cevap' / 'Yanlis Cevap'

Sirayla gitseydik freePickMany ailesinde DOGRU cevap veren ogrenciyi
telafiye gonderirdik. Yetkili kaynak <intrProps>:

    <intrProps corFbG="..." incFbG="..." />

incFbG dogrudan yanlis geri bildirim katmaninin GUID'i. Uc aileden ikisinde
cozuluyor; ucuncude (freePickOne) katman adlari dolu oldugu icin ada
dusuluyor. Ikisi de tutmazsa SLAYT ATLANIR ve rapora yazilir -- yanlis
katmana baglamaktansa hic baglamamak.

KAPSAM OLCULDU (uretilmis kurs, 2026-09-04):
    kurucunun soru slaytlari : 4/4 tanindi (3 intrProps, 1 ad)
    devralinan slaytlar      : 4 taninmadi -- zaten dokunulmuyor
"""

from __future__ import annotations

from storyline_mcp import authoring, logic, model, shapes
from storyline_mcp.package import StoryPackage, StoryError

try:
    from . import ilerleme
except ImportError:  # pragma: no cover - script execution fallback
    import ilerleme

NULL_GUID = "00000000-0000-0000-0000-000000000000"

# Geri bildirim katmani tasiyabilen etkilesim etiketleri. model.INTERACTION_TAGS
# ile ayni kume degil bilerek: burada YALNIZCA <intrProps> tasiyanlar var,
# cunku kimlik tespiti o elemana dayaniyor.
ETKILESIM_ETIKETLERI = ("freePickOneIntr", "freePickManyIntr", "dragDropIntr",
                        "freeHotSpotIntr", "freeTextEntryIntr")

BUTON_METNI = "Konuya don"

# Yeni butonun mevcut butondan yatay uzakligi, slayt yuzdesi.
BUTON_ARALIGI = 2.0


def _etkilesim(root):
    for etiket in ETKILESIM_ETIKETLERI:
        for intr in root.iter(etiket):
            return intr
    return None


def _yanlis_katman(root) -> tuple[object | None, str]:
    """Yanlis geri bildirim katmani ve HANGI YOLLA bulundugu.

    Yol adi geri donuyor cunku rapor "bulundu" ile "nasil bulundu"yu ayirt
    edebilmeli: intrProps yetkili kaynak, ad ise ikinci derece kanit.
    """
    katman_listesi = root.find("sldLayerLst")
    katmanlar = list(katman_listesi) if katman_listesi is not None else []
    if not katmanlar:
        return None, "katman yok"

    intr = _etkilesim(root)
    if intr is not None:
        props = intr.find("intrProps")
        inc = props.get("incFbG") if props is not None else None
        if inc and inc != NULL_GUID:
            for katman in katmanlar:
                if katman.get("g") == inc:
                    return katman, "intrProps"

    for katman in katmanlar:
        ad = (katman.get("name") or "").lower()
        if "yanl" in ad or "incorrect" in ad:
            return katman, "ad"

    return None, "cozulemedi"


def _katman_butonu(katman):
    """Katmandaki mevcut buton -- yeni butonun yeri ondan olculuyor.

    Sabit koordinat KULLANILMIYOR: olculdu 2026-09-04, iki soru ailesinde
    buton iki ayri yerde duruyor (x=41.4% y=65.4% ile x=68.2% y=85.8%).
    Sabit bir yer, ailelerden birinde mevcut butonun ustune binerdi.
    """
    sekil_listesi = katman.find("shapeLst")
    for sekil in (list(sekil_listesi) if sekil_listesi is not None else []):
        if (sekil.get("name") or "").lower().startswith("button"):
            return sekil
    return None


def _soru_slaydi(pkg: StoryPackage, slaytlar: list[str]):
    """Sahnenin geri bildirim katmani TASIYAN son slaydi.

    Sondan aranir: bir sahnede birden fazla soru olabilir ve dallanma,
    ogrencinin en son yanildigi yerden konuya donmeli.
    """
    for basename in reversed(slaytlar):
        root = pkg.parse(pkg.slide_part_for(basename))
        if _etkilesim(root) is None:
            continue
        katman = root.find("sldLayerLst")
        if katman is not None and len(list(katman)) >= 2:
            return basename
    return None


def kur(pkg: StoryPackage, konu_sahneleri: list[str], *,
        basliklar: dict[str, str] | None = None,
        on_progress=lambda m: None) -> dict:
    """Her konu sahnesinin sorusuna yanlis-cevap dallanmasi kurar.

    basliklar: sahne adi -> ogrenciye gosterilecek baslik. Verilmezse sahne
    adi kullanilir; "04_HalkaAcikAglar" gibi bir makine adini ogrenciye
    gostermemek icin cagiran kendi basligini gecirmeli.

    rapor["bayraklar"] : [(degisken, baslik)] -- tekrar ekrani bunu okur.
    """
    basliklar = basliklar or {}
    rapor: dict = {"dallanan_sahne": 0, "degiskenler": [], "bayraklar": [],
                   "butonlar": 0, "yol": {}, "atlanan": []}
    if not konu_sahneleri:
        rapor["atlanan"].append("konu sahnesi yok")
        return rapor

    sahne_slaytlari: dict[str, list[str]] = {}
    for ref in model.slide_index(pkg).values():
        sahne_slaytlari.setdefault(ref.scene_name, []).append(ref.basename)

    for sira, sahne in enumerate(konu_sahneleri, 1):
        slaytlar = sahne_slaytlari.get(sahne) or []
        if len(slaytlar) < 2:
            rapor["atlanan"].append(f"{sahne}: iki slayttan az, donulecek yer yok")
            continue

        soru = _soru_slaydi(pkg, slaytlar)
        if soru is None:
            rapor["atlanan"].append(f"{sahne}: geri bildirim katmanli soru yok")
            continue

        # DONUS HEDEFI: sahnenin ilk slaydi. Ayrac (section) varsa o, yoksa
        # ilk icerik. Ayrac da sahnenin basi -- ogrenciyi bolumun basina
        # gondermek, "konuya don" cumlesinin karsiligi.
        hedef = slaytlar[0]
        if hedef == soru:
            rapor["atlanan"].append(f"{sahne}: soru sahnenin tek slaydi")
            continue

        root = pkg.parse(pkg.slide_part_for(soru))
        katman, yol = _yanlis_katman(root)
        rapor["yol"][yol] = rapor["yol"].get(yol, 0) + 1
        if katman is None:
            # SESSIZ GECILMEZ: yanlis katmani bilmeden baglamak, dogru cevap
            # veren ogrenciyi telafiye gondermek olabilirdi.
            rapor["atlanan"].append(
                f"{sahne}/{soru}: yanlis katman {yol} -- dallanma kurulmadi")
            continue

        ad = ilerleme._degisken_adi(sahne, sira, sonek="Hata")
        try:
            logic.add_variable(pkg, ad, "bool", False)
            rapor["degiskenler"].append(ad)
            rapor["bayraklar"].append((ad, basliklar.get(sahne) or sahne))
        except StoryError as exc:
            rapor["atlanan"].append(f"{ad}: {exc}")
            continue

        # 1) BAYRAK: katmanin KENDI tetikleyicisi, butonun degil.
        try:
            logic.add_trigger(pkg, soru, "adjust_variable",
                              owner_layer=katman.get("g"), event="OnStart",
                              variable=ad, operation="set", value=True)
        except StoryError as exc:
            rapor["atlanan"].append(f"{sahne} bayrak tetikleyicisi: {exc}")
            continue

        # 2) BUTON: mevcut butonun SOLUNA, ayni hizada ve ayni boyda.
        eski = _katman_butonu(katman)
        if eski is None:
            rapor["atlanan"].append(
                f"{sahne}/{soru}: katmanda buton yok, yer olculemedi "
                "-- bayrak kuruldu, buton kurulmadi")
            rapor["dallanan_sahne"] += 1
            continue
        genislik, yukseklik = shapes.slide_size(root)
        r = shapes.shape_rect(eski)
        bx = (r[0] / genislik * 100) - BUTON_ARALIGI - ((r[2] - r[0]) / genislik * 100)
        if bx < 1.0:
            rapor["atlanan"].append(
                f"{sahne}/{soru}: mevcut butonun soluna yer yok "
                "-- bayrak kuruldu, buton kurulmadi")
            rapor["dallanan_sahne"] += 1
            continue

        try:
            yeni = authoring.add_button(
                pkg, soru, BUTON_METNI,
                x=round(bx, 1), y=round(r[1] / yukseklik * 100, 1),
                w=round((r[2] - r[0]) / genislik * 100, 1),
                h=round((r[3] - r[1]) / yukseklik * 100, 1),
                target_slide=hedef, avoid_overlap=False)
            _katmana_tasi(pkg, soru, yeni["shape"], katman.get("g"))
            rapor["butonlar"] += 1
        except StoryError as exc:
            rapor["atlanan"].append(
                f"{sahne}/{soru}: buton kurulamadi ({str(exc)[:70]}) "
                "-- bayrak kuruldu")
            rapor["dallanan_sahne"] += 1
            continue

        rapor["dallanan_sahne"] += 1

    on_progress(
        f"dallanma: {rapor['dallanan_sahne']} sahne, "
        f"{len(rapor['degiskenler'])} hata bayragi, "
        f"{rapor['butonlar']} donus butonu"
        + (f" (kimlik: {rapor['yol']})" if rapor["yol"] else ""))
    for a in rapor["atlanan"]:
        on_progress(f"dallanma -- atlandi: {a}")
    return rapor


# Tekrar seridi: sonuc slaydinin BOS bandi. Olculdu 2026-09-04, sonuc
# slaydinin kok sekilleri: baslik %5.5, puan %36.9-56.3, cizgi %70.1,
# gecme puani %82.7. Yani %58-%69 arasi bos ve serit oraya oturuyor.
SERIT_UST = 58.0
SERIT_SOL = 10.0
SERIT_GENISLIK = 80.0
SERIT_YUKSEKLIK = 5.0
SERIT_ARALIK = 5.6


def tekrar_ekrani(pkg: StoryPackage, sonuc_slaydi: str,
                  bayraklar: list[tuple[str, str]], esik: int, *,
                  on_progress=lambda m: None) -> dict:
    """Sonuc slaydinda "su konulari tekrar et" seridi.

    bayraklar: [(degisken_adi, gosterilecek_baslik)] -- dallanmanin kurdugu
    <Bolum>_Hata bayraklari. Bayrak KURULUP OKUNMADIGI surece elde veri var
    ama ogrenci icin hicbir sey degismiyor; bu fonksiyon o halkayi kapatir.

    HER KONU ICIN AYRI KATMAN, tek katmanda N satir DEGIL. Sebep: tek
    katmandaki satirlari ayri ayri gizlemek "Hidden" durumu gerektirir ve
    duz metin kutusunda o durumun XML'de nasil durdugu bu projede
    OLCULMEDI. Katman gosterip gizlemek ise olculmus yol (kilit katmani
    ayni mekanizmayla kuruldu ve dosya aciliyor). Storyline katmanlari
    ust uste gosterebiliyor, yani serit satir satir birikir.

    IKI KOSUL, tek degil:
        <Bolum>_Hata == true   o konuda yanildi
        Ilerleme    >= esik    kursu BITIRDI
    Ikincisi olmasaydi serit, kilit katmani ("hepsini tamamlamadiniz") ile
    ayni anda gorunurdu -- ogrenciye hem "daha bitirmedin" hem "sunu tekrar
    et" demek olurdu.
    """
    rapor = {"satir": 0, "atlanan": []}
    if not sonuc_slaydi:
        rapor["atlanan"].append("sonuc slaydi yok; tekrar ekrani kurulmadi")
        return rapor
    if not bayraklar:
        rapor["atlanan"].append("hata bayragi yok; tekrar ekrani kurulmadi")
        return rapor

    for i, (degisken, baslik) in enumerate(bayraklar):
        katman_adi = f"Tekrar_{degisken}"
        try:
            authoring.add_layer(pkg, sonuc_slaydi, katman_adi,
                                text=f"Tekrar et:  {baslik}")
        except StoryError as exc:
            rapor["atlanan"].append(f"{katman_adi}: {exc}")
            continue
        yerlesti = _seridi_yerlestir(pkg, sonuc_slaydi, katman_adi,
                                     SERIT_UST + i * SERIT_ARALIK)
        if not yerlesti:
            rapor["atlanan"].append(
                f"{katman_adi}: serit yerlestirilemedi, katman varsayilan "
                "boyutta kaldi")
        try:
            logic.add_trigger(
                pkg, sonuc_slaydi, "show_layer", event="OnStart",
                layer=katman_adi,
                conditions=[{"variable": degisken, "op": "eq", "value": True},
                            {"variable": "Ilerleme", "op": "gte", "value": esik}])
            rapor["satir"] += 1
        except StoryError as exc:
            rapor["atlanan"].append(f"{katman_adi} tetikleyicisi: {exc}")

    on_progress(f"tekrar ekrani: {rapor['satir']} satir "
                f"(kosul: konuda yanildi VE kursu bitirdi)")
    for a in rapor["atlanan"]:
        on_progress(f"tekrar -- atlandi: {a}")
    return rapor


def _seridi_yerlestir(pkg: StoryPackage, slayt: str, katman_adi: str,
                      ust_yuzde: float) -> bool:
    """Katmanin panelini ince bir seride indirir ve butonunu kaldirir.

    add_layer tohumdan buyuk bir panel + "Devam" butonu getiriyor (olculdu:
    %8,%12 - %92,%80 ve bir buton). N konu icin N buyuk panel ust uste
    binerdi ve her birinde ayri bir Devam butonu olurdu. Serit bir SATIR;
    butonu da kaldiriliyor cunku sonuc slaydinin kendi Success/Failure
    katmanlari zaten kendi butonlarini tasiyor.
    """
    part = pkg.slide_part_for(slayt)
    root = pkg.parse(part)
    genislik, yukseklik = shapes.slide_size(root)
    katman_listesi = root.find("sldLayerLst")
    katman = next((l for l in (list(katman_listesi) if katman_listesi is not None else [])
                   if (l.get("name") or "") == katman_adi), None)
    if katman is None:
        return False
    sekil_listesi = katman.find("shapeLst")
    if sekil_listesi is None:
        return False
    yerlesen = False
    for sekil in list(sekil_listesi):
        ad = (sekil.get("name") or "").lower()
        if ad.startswith("button"):
            sekil_listesi.remove(sekil)
            continue
        loc = sekil.find("loc")
        if loc is None:
            continue
        loc.set("l", str(round(SERIT_SOL / 100 * genislik)))
        loc.set("t", str(round(ust_yuzde / 100 * yukseklik)))
        loc.set("r", str(round((SERIT_SOL + SERIT_GENISLIK) / 100 * genislik)))
        loc.set("b", str(round((ust_yuzde + SERIT_YUKSEKLIK) / 100 * yukseklik)))
        yerlesen = True
    if yerlesen:
        pkg.replace_xml(part, root)
    return yerlesen


def _katmana_tasi(pkg: StoryPackage, slayt: str, sekil_guid: str,
                  katman_guid: str) -> None:
    """add_button slaydin KOKUNE ekliyor; sekli yanlis katmana taşır.

    add_button'a katman parametresi EKLENMEDI ve sebebi kapsam: o fonksiyon
    tohum secimi, komsu buton kopyalama ve cakisma kacinma tasiyor, hepsi
    slayt koku varsayimiyla yazilmis. Burada yalnizca son adim degisiyor --
    sekil hangi listede duracak. Konum mutlak (loc l/t/r/b), yani tasima
    gorunumu degistirmiyor.
    """
    part = pkg.slide_part_for(slayt)
    root = pkg.parse(part)
    kok_listesi = root.find("shapeLst")
    sekil = next((s for s in (list(kok_listesi) if kok_listesi is not None else [])
                  if s.get("g") == sekil_guid), None)
    if sekil is None:
        raise StoryError(f"Eklenen buton {sekil_guid[:8]} slayt kokunde bulunamadi.")
    katman_listesi = root.find("sldLayerLst")
    katman = next((l for l in (list(katman_listesi) if katman_listesi is not None else [])
                   if l.get("g") == katman_guid), None)
    if katman is None:
        raise StoryError(f"Katman {katman_guid[:8]} bulunamadi.")
    hedef_listesi = katman.find("shapeLst")
    if hedef_listesi is None:
        raise StoryError("Katmanda shapeLst yok.")
    kok_listesi.remove(sekil)
    hedef_listesi.append(sekil)
    pkg.replace_xml(part, root)
