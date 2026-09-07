"""Ilerleme katmani: degisken, kosul, tetikleyici -- kursu sayfa cevirmekten ayiran sey.

NICIN VAR: bu projede kurs kuran yol (panel/builder.py) bugune kadar YALNIZCA
slayt ve soru uretti. Cagrilarinin dokumu alindiginda (2026-09-04) `logic.*`
cagrisi SIFIRDI:

    add_slide + compose_slide                     statik metin duzenleri
    add_question / add_drag_question / ...        dort soru tipi
    create_scene, promote_scenes, medya.*

logic.py'nin kendi baslik cumlesi eksigi zaten yaziyordu -- "Without them a
deck can only be read front to back". Modul yazilmis, olculmus ve uretim
hattina hic baglanmamisti. Kullanicinin bildirdigi sikayet (moduller
PowerPoint dosyalari gibi cikiyor) tam olarak bu satirin sonucu: degiskeni,
kosulu ve sonuc slaydi olmayan bir kurs, tanimi geregi sayfa cevirmektir.

NE KURULUYOR, dordu bir zincir:

    <Bolum>_Tamam (bool)     her konu sahnesi icin bir bayrak
    Ilerleme (num)           kac bolum tamamlandi
    tamamlama tetikleyicisi  sahnenin SON slaydinda, OnStart
    kilit                    sonuc slaydinda kosullu katman

SLAYTLAR PAKETTEN OKUNUYOR, olusturulurken toplanmiyor. Builder'da slayt
alti ayri yerde uretiliyor (icerik, sik secme, gruplama, taahhut, sicak
nokta, menuye dusen soru) ve her birinde bir liste beslemek, alti cagirandan
birinin unutmasi demekti -- bu projenin bilinen kusuru. Yetkili kaynak
paketin kendisi: model.slide_index sahne sirasini zaten veriyor.

SIRA YUK TASIYOR: sayac tetikleyicisi bayraktan ONCE eklenir. Storyline
tetikleyicileri listede yazildiklari sirayla isletir; bayrak once kalkarsa
sayacin kosulu ("bayrak False iken") ayni geliste yanlislanir ve Ilerleme
HIC artmaz. Ters sirayla yazilan bir surum sessizce calisir gorunur: dosya
acilir, panel iki tetikleyiciyi de gosterir, sayi sifirda kalir.

OLCULDU (tools/olcum/ilerleme_kanit.py, 2026-09-04): katman kurulmadan once
ve sonra ayni dosyada pedagogy.olc kosuldu; tetikleyici sayisi ve
sonuc_slaydi alani degisti, kayit dogrulamasi 0 sorunla gecti.
"""

from __future__ import annotations

import re

from storyline_mcp import authoring, clone, logic, model
from storyline_mcp.package import StoryPackage, StoryError

# Turkce harf degisken adinda gecmez: add_variable [A-Za-z_][A-Za-z0-9_]*
# disini REDDEDIYOR. Reddetmeseydi daha kotusu olurdu -- Storyline degiskeni
# sessizce dusurur ve ona bakan kosul hep yanlis doner.
TR_HARF = {"ç": "c", "ğ": "g", "ı": "i", "ö": "o",
           "ş": "s", "ü": "u", "Ç": "C", "Ğ": "G",
           "İ": "I", "Ö": "O", "Ş": "S", "Ü": "U"}

# Sahne adi MENUDE gorunur, o yuzden teknik degil INSAN OKUNUR.
# "99_Sonuc" bir siralama hilesiydi ve ogrencinin sol tarafta
# gordugu satir oluyordu (kullanicinin 8 numarali bulgusuyla ayni
# sinif). Sahne zaten SON eklendigi icin siraya numara gerekmiyor.
SONUC_SAHNESI = "Sonuçlar"
KILIT_KATMANI = "Eksik"


def _ascii(metin: str) -> str:
    return "".join(TR_HARF.get(ch, ch) for ch in metin or "")


def _degisken_adi(sahne_adi: str, sira: int, sonek: str = "Tamam") -> str:
    """Sahne adindan okunabilir bir degisken adi. Turetilemezse siraya duser.

    Ad Storyline'in degisken panelinde GORUNUYOR; "Bolum3_Tamam" ile
    "ParolaHijyeni_Tamam" arasindaki fark, kursu sonradan elle acan kisinin
    hangi bayragin ne oldugunu anlamasi.

    SONEK PARAMETRE, cunku ikinci bir kullanici cikti: dallanma katmani ayni
    sahneler icin "_Hata" bayragi kuruyor. Ad turetme kurallari (Turkce harf,
    bas rakami, gecersiz karakter, uzunluk) TEK YERDE dursun -- iki kopya
    ayrisirsa iki katman ayni sahne icin uyusmayan adlar uretirdi.
    """
    ham = _ascii(sahne_adi or "")
    ham = re.sub(r"^\d+[_-]*", "", ham)          # "02_KimlikAvi" -> "KimlikAvi"
    ham = re.sub(r"[^A-Za-z0-9_]", "", ham)
    if not ham or ham[0].isdigit():
        return f"Bolum{sira}_{sonek}"
    return f"{ham[:40]}_{sonek}"


def _sahne_slaytlari(pkg: StoryPackage) -> dict[str, list[str]]:
    """Sahne adi -> slayt dosyalari, sahne sirasinda."""
    gruplu: dict[str, list[str]] = {}
    for ref in model.slide_index(pkg).values():
        gruplu.setdefault(ref.scene_name, []).append(ref.basename)
    return gruplu


def kur(pkg: StoryPackage, konu_sahneleri: list[str], *,
        on_progress=lambda m: None, palette: dict | None = None) -> dict:
    """Ilerleme takibini, sonuc slaydini ve kilidi kurar.

    konu_sahneleri: giris ve kapanis DISINDAKI sahne adlari. Kimin konu
    sahnesi oldugu sorusu burada IKINCI KEZ cevaplanmiyor --
    builder._konu_araligi zaten cevapliyor ve iki tanim ayrisirdi.
    """
    rapor: dict = {"degiskenler": [], "tetikleyiciler": 0,
                   "sonuc_slaydi": None, "sonuc_sahnesi": None, "kilit": False,
                   "esik": len(konu_sahneleri), "atlanan": []}
    if not konu_sahneleri:
        rapor["atlanan"].append("konu sahnesi yok; ilerleme katmani kurulmadi")
        return rapor

    slaytlar = _sahne_slaytlari(pkg)

    # 1) SAYAC. Bayraklardan once kurulur: bayrak dongusunun ilk adiminda
    #    zaten bu degiskene yazan bir tetikleyici ekleniyor.
    try:
        logic.add_variable(pkg, "Ilerleme", "num", 0)
        rapor["degiskenler"].append("Ilerleme")
    except StoryError as exc:
        # Ayni isimde degisken varsa (kullanicinin kendi dosyasindan gelmis
        # olabilir) devam edilir; yeniden kurmak onunkini ezmek olurdu.
        rapor["atlanan"].append(f"Ilerleme: {exc}")

    # 2) HER KONU SAHNESI ICIN BAYRAK + TAMAMLAMA TETIKLEYICISI
    kurulan = 0
    for sira, sahne in enumerate(konu_sahneleri, 1):
        sahne_slaytlari = slaytlar.get(sahne) or []
        if not sahne_slaytlari:
            rapor["atlanan"].append(f"{sahne}: pakette slayt bulunamadi")
            continue
        son = sahne_slaytlari[-1]
        ad = _degisken_adi(sahne, sira)
        try:
            logic.add_variable(pkg, ad, "bool", False)
        except StoryError as exc:
            rapor["atlanan"].append(f"{ad}: {exc}")
            continue
        rapor["degiskenler"].append(ad)

        # SIRA: once sayac, sonra bayrak. Gerekcesi modul basliginda.
        try:
            logic.add_trigger(pkg, son, "adjust_variable", event="OnStart",
                              variable="Ilerleme", operation="add", value=1,
                              conditions=[{"variable": ad, "op": "eq",
                                           "value": False}])
            logic.add_trigger(pkg, son, "adjust_variable", event="OnStart",
                              variable=ad, operation="set", value=True)
            kurulan += 2
        except StoryError as exc:
            rapor["atlanan"].append(f"{sahne} tetikleyicisi: {exc}")
    rapor["tetikleyiciler"] = kurulan

    # 3) SONUC SLAYDI. LMS'in okudugu nesne bu: yoksa kurs SCORM'a puan
    #    raporlayamaz -- eksik olan bir yayin ayari degil, raporlayacak
    #    nesnenin kursta hic bulunmamasi.
    # SAHNE ONCE KURULUR. add_results_slide -> clone.install_slide sahneyi
    # OLUSTURMAZ, var olmasini bekler. Olculdu 2026-09-04: sahne kurulmadan
    # istendiginde cagri "Sahne bulunamadi" ile dogru sekilde patladi, ama
    # paket kirli kaldi -- install_slide parcayi dogrulamadan ONCE yaziyordu
    # ve kursta sahnesiz bir slayt biraliyordu (o kusur clone.py'de ayrica
    # kapatildi). Burada sahneyi kurmak, ayni hatanin ikinci sebebini kaldirir.
    try:
        clone.create_scene(pkg, SONUC_SAHNESI)
    except StoryError:
        pass          # ayni isimde sahne zaten varsa kullanilir

    try:
        sonuc = authoring.add_results_slide(pkg, scene=SONUC_SAHNESI,
                                            name="Sonuçlar", palette=palette)
        rapor["sonuc_slaydi"] = sonuc.get("new_slide")
        # Sahne ADI geri veriliyor, guid degil: guid'i cagiran story.xml'den
        # cozuyor. install_slide scene_guid dondurmuyor ve burada ikinci bir
        # cozumleme yazmak, ayni guid'i iki yerde aramak olurdu.
        rapor["sonuc_sahnesi"] = sonuc.get("scene") or SONUC_SAHNESI
    except StoryError as exc:
        rapor["atlanan"].append(f"sonuc slaydi: {exc}")
        _bildir(rapor, on_progress)
        return rapor

    # 4) KILIT. "Butun konulari bitirmeden sinava giremezsin" kuralinin bu
    #    kurstaki karsiligi: bolumler bitmeden sonuc ekrani kendini
    #    aciklamasin. Ogrenci baska sahneye ATILMIYOR, bilerek -- kosullu bir
    #    jump geri donen ogrenciyi donguye sokabilir ve sebebini soylemez;
    #    katman sebebi yaziyor.
    esik = len(konu_sahneleri)
    try:
        authoring.add_layer(
            pkg, rapor["sonuc_slaydi"], KILIT_KATMANI,
            text=(f"Bu kursta {esik} bölüm var ve hepsini tamamlamadınız. "
                  "Sonuçlarınız bütün bölümler bittikten sonra hesaplanır."))
        logic.add_trigger(pkg, rapor["sonuc_slaydi"], "show_layer",
                          event="OnStart", layer=KILIT_KATMANI,
                          conditions=[{"variable": "Ilerleme", "op": "lt",
                                       "value": esik}])
        rapor["kilit"] = True
        rapor["tetikleyiciler"] += 1
    except StoryError as exc:
        rapor["atlanan"].append(f"kilit: {exc}")

    # KILIT KATMANI DA KURSUN TEMASINI GIYER.
    #
    # Slaydin kendisi artik `add_results_slide(palette=...)` icinde boyaniyor
    # -- ama KILIT KATMANI ondan SONRA ekleniyor, yani o boyamanin gormedigi
    # bir metin. `add_layer` PALETI BILMEZ: tohumu klonlar, metni yazar, yazi
    # tohumun renginde (beyaz) kalir. Temel katman bundan etkilenmiyor --
    # oradaki yazilar vurgu dolgulu sekillerin uzerinde durur ve beyaz orada
    # okunur. KATMANLAR farkli: "Tebrikler, sinavi gectin" ve
    # "Sinavi gecemedin!" dogrudan slayt zeminine dusuyor.
    #
    # Olculdu 2026-09-05, alti tema x tema fiksturu:
    #     kagit  #FFFFFF / #F7F5EF  oran 1.09
    #     sis    #FFFFFF / #DFE6EC  oran 1.26
    # Koyu temalarda sorun yok, acik temalarda yazi GORUNMUYOR. Ve hicbir kapi
    # soylemiyor: `contrast.audit`in katman taramasi varsayilan olarak kapali.
    #
    # Duzeltme yeni hesap degil, var olan makineyi cagirmak -- ayni yol reveal
    # katmanlarinda da kullanildi (builder._reveal_katmanlari).
    if palette and rapor.get("sonuc_slaydi"):
        try:
            authoring._recolour_for_palette(
                pkg, pkg.slide_part_for(rapor["sonuc_slaydi"]), palette,
                stem=None, choices=set(), eyebrow=None)
        except Exception:
            # Renk duzeltmesi dusrse sonuc slaydi YINE durur; kursu dusurmek
            # calisan bir slaydi yok saymak olurdu.
            pass

    _bildir(rapor, on_progress)
    return rapor


def _bildir(rapor: dict, on_progress) -> None:
    """Akisa tek satir ozet, arti atlanan her madde AYRI satir.

    Atlananlar toplu bir sayiya indirgenmiyor: "3 sey atlandi" ile "sonuc
    slaydi kurulamadi" disaridan ayni gorunur, ve ikincisi kursun LMS'e
    raporlayamamasi demek.
    """
    on_progress(
        f"ilerleme katmani: {len(rapor['degiskenler'])} degisken, "
        f"{rapor['tetikleyiciler']} tetikleyici, "
        f"sonuc slaydi {'kuruldu' if rapor['sonuc_slaydi'] else 'KURULAMADI'}"
        + (f", kilit esigi {rapor['esik']} bolum" if rapor["kilit"] else ""))
    for a in rapor["atlanan"]:
        on_progress(f"ilerleme -- atlandi: {a}")


# --------------------------------------------------------------- yol teshisi
#
# BURADA, `app.py`DE DEGIL. Teshis "Ilerleme degiskeni var mi" sorusudur ve o
# degiskeni KURAN modul burasi -- yani imzanin sahibi. `app.py`de dururken
# yalnizca panelin dosya bilgisi yukunden gorunuyordu; `agent.py` ondan
# import edemez (app zaten agent'i import ediyor, ters yon dongu olurdu) ve
# ikinci bir kopya zamanla ayrisirdi.


def kurucu_yoldan_mi(pkg: StoryPackage) -> bool:
    """Bu kurs panelin "Kurs kur" formundan mi cikti?

    NICIN SORULUYOR. Panelde kurs kurmanin IKI yolu var ve ikisi ayni sey
    degil:

        "Kurs kur" formu    ->  builder.build()  ->  medya plani, ilerleme
                                katmani, sonuc kilidi, dallanma, .medya.json
        Sohbet (CLI + MCP)  ->  ajan MCP araclarini DOGRUDAN cagirir

    Ikincisinde bu adimlarin HICBIRI kosmuyor: `builder.build` tek yerden
    cagriliyor (`panel/app.py`) ve MCP'nin `build_course`u onunla ilgisiz bir
    islem listesi (create_scene, add_slide, add_question...). Yani sohbetle
    kurulan bir kursta gorsel/video HIC istenmiyor -- istek dusmuyor, HIC
    DOGMUYOR -- ve ilerleme takibi ile sonuc kilidi kurulmuyor.

    IMZA `Ilerleme`, VE YALNIZCA O. `kur` onu KOSULSUZ yaratiyor ve
    `bos.story`de o degisken YOK -- yani kullanicinin kaynak dosyasindan
    devralinamaz. Yoklugu tek anlama geliyor.

    DIGER IKI ADAY ELENDI, cunku yoklukları baska turlu de olusabiliyor:

        <Bolum>_Hata   `dallanma.kur` yalnizca baglanacak bir yanlis-cevap
                       katmani bulursa ekler; bulamazsa atlar ve raporlar.
        .medya.json    sifir istekte `medya.temizle` onu SILIYOR.

    Yani ikisi de kurucu yol KOSSA BILE eksik olabilir; onlari imza saymak
    yanlis alarm uretirdi. Bir kez tam da boyle bir hata yapildi: ayni
    teshis slayt ADLARINA dayandirilmis (a280ea2), ad kaynak dosyadan
    devralindigi olculunce gecersiz cikmis ve teshis geri alinmisti
    (3942e71). Teshis dogruydu, dayanagi yanlisti.

    RAPOR EDER, DUZELTMEZ: dosyayi OKUYOR, yazmiyor.
    """
    return "Ilerleme" in {v["name"] for v in model.variables(pkg)}


def medya_yeri_olan_slaytlar(pkg: StoryPackage) -> list[str]:
    """Kaydedilmis slaytlarda gorsel icin GERCEKTEN yer var mi?

    ESIK UYDURULMADI, URUNDEN OKUNUYOR. `compose.VARIANTS["content"]
    ["yan-gorsel"]["gorsel"]` gorsele ayirdigi sutunun genisligini soyluyor;
    bir slayt o kadar bos sag sutun tasimiyorsa, urunun gorseli koydugu
    bicimde koyacak yer YOK demektir. Sabiti buraya yazmak, `compose`
    sutunu daralttiginda bu olcunun sessizce yalan soylemesi olurdu.

    NICIN GEREKLI. Kurucu yolu yeri COMPOSE ANINDA ayirir; sohbet yolunda
    slaytlar zaten kurulmus olarak gelir. Yani "sonradan alan ayir" bedava
    degil ve bu fonksiyon onun ne kadar pahali oldugunu SAYIYLA soyler.

    OLCULDU 2026-09-07, kullanicinin yks kursu (sohbet yolundan, 16 slayt):
    urun %46 sutun istiyor, en comert slaytta %26 bos vardi -- yani uygun
    slayt SIFIR. Istegi yine de yazmak, gorseli metnin ustune dusururdu
    (`builder._medya_yeri_var` ayni tuzagi kendi belge dizesinde anlatiyor).
    """
    from storyline_mcp import compose as _compose, shapes as _shapes
    try:
        gerekli = float(_compose.VARIANTS["content"]["yan-gorsel"]["gorsel"][1])
    except Exception:
        return []
    uygun: list[str] = []
    for part, ref in model.slide_index(pkg).items():
        kok = pkg.parse(part)
        w, h = _shapes.slide_size(kok)
        sekiller = kok.find("shapeLst")
        en_sag = 0.0
        for sekil in list(sekiller) if sekiller is not None else []:
            kutu = _shapes.shape_rect(sekil)
            if kutu is None:
                continue
            l, t, r, b = kutu
            if (r - l) >= w * 0.95 and (b - t) >= h * 0.95:
                continue                  # tam sayfa zemin, yer kaplamiyor
            en_sag = max(en_sag, r / w * 100.0)
        if 100.0 - en_sag >= gerekli:
            uygun.append(ref.basename)
    return uygun


def sohbet_yolu_notu(pkg: StoryPackage) -> str:
    """Sohbetle kurulan kursun SONUNDA soylenecek cumle; kurucu yolda "".

    NICIN BITISTE. Bilgi zaten hesaplaniyordu ama yalnizca panelin dosya
    bilgisi yukunde gorunuyordu -- yani kullanici dosyayi SECTIGINDE. Kurucu
    yolun kendi "sifir medya" uyarisi da `app._run_builder`in bitis notunda,
    yani yalnizca o yolda. Sonuc: sohbetle kurs kuran kisi -- uyariya en cok
    ihtiyaci olan kisi -- kurulum bittiginde hicbir sey gormuyordu.
    """
    if kurucu_yoldan_mi(pkg):
        return ""
    uygun = medya_yeri_olan_slaytlar(pkg)
    toplam = len(model.slide_index(pkg))
    return (" Bu kurs sohbet yolundan kuruldu: gorsel/video PLANLANMADI, "
            "ilerleme takibi ve sonuc kilidi kurulmadi. "
            + ("Gorsel icin yer acilabilecek slayt: %d/%d."
               % (len(uygun), toplam) if uygun else
               "Ustelik %d slaydin hicbirinde gorsel icin bos sutun yok -- "
               "sonradan istek yazmak gorseli metnin ustune dusururdu."
               % toplam))
