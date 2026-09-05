"""Ölçüleri PROBA değil, ÜRETİLMİŞ BİR KURSA koşar.

Envanter tek satirda soyle diyordu:

    Suit kosuldugunda uretilmis bir kursa bakan kontrol: YOK.

Paketteki her kontrol kendi kurdugu sentetik prob uzerinde kosuyordu --
variety varyant sozlugunu, coverage kendi SPECS'ini, golden uc elle yazilmis
vakayi. Gercek bir kursta on kusur bulundu ve ONU DA paket yesilken oradaydi.
Bu tesaduf degildi: "hepsi yesil" cumlesi "problar saglam" demekti.

Bu dosya o bosluğu kapatir. Bir brief'ten TAM bir kurs kurar -- iskelet,
icerik, sorular, geri bildirim katmanlari, tema -- ve butun olculeri ciktinin
uzerinde kosar.

MODEL CAGRISI YOK. builder._run_json yerine sabit bir icerik konur: kontrol
insa yolunu olcuyor, modelin o gun ne yazdigini degil. Model cevabi degisken
olsaydi kontrol de degisken olurdu ve bir gerileme ile "model bugun boyle
yazmis" ayirt edilemezdi.

ICERIK ZORLAYICI SECILDI. Mutlu yol olcum yapmaz: uzun sik etiketleri (70+
karakter), seyrek govdeler, cok maddeli kartlar ve uzun bir kok. Bunlarin
her biri bu oturumda gercek bir kusur uretmisti.

    python tools/produced.py
    python tools/produced.py --png bak.png
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import warnings
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "panel"))
sys.path.insert(0, str(ROOT / "tools"))

from storyline_mcp import authoring
from storyline_mcp.package import StoryPackage
import builder
import completeness
import inventory

BLANK = ROOT.parent / "test" / "bos.story"
WORK = ROOT.parent / "test" / "_canary" / "uretilmis.story"

SCENES = [("01_Gerginlik", "Gerginligin Ilk Isaretleri"),
          ("02_Dinleme", "Dinleme ve Sahiplenme"),
          ("03_Sinir", "Sinir Koyma"),
          ("04_Kapanis", "Kapanis ve Kayit")]

# Uzun sik etiketleri: bu oturumda butonlari slaydin altina sarkitan,
# metni kutudan tasiran ve yatay sirayi okunamaz kilan sey tam olarak buydu.
LONG_CHOICES = [
    "Sakin bir tonla dinlemeye devam eder ve ozetleyerek dogrular",
    "Ayni sertlikte karsilik verip kim oldugunu hatirlatir",
]

# BES SIKLI COKTAN SECMELI. Prob yalnizca IKI sikli LONG_CHOICES tasiyordu,
# yani her zaman `freePickOneIntr` seciyordu ve COKTAN SECMELI YOL bu
# kapidan hic gecmiyordu. Bu oturumun iki gorunur kusuru -- bos kapsuller
# (etiket yalnizca `Selected`'da) ve 27.5:1 mercek siluet -- yalnizca o
# yolda uretiliyor. Kapi yesildi cunku kusurun gectigi yol probda YOKTU.
#
# Ayni kor nokta `invariants.check_question_frame`'de de vardi ve orada
# `check_choice_labels` ile kapatilmisti; burada acik kalmis.
#
# Etiket uzunluklari GERCEK kurstan okundu (medyan 51, en uzun 72),
# secilmedi.
MULTI_CHOICES = [
    "Alici listesini gondermeden once bir kez daha dogrula",
    "Paylasim baglantisini yalnizca isi geregi gereken kisiye ver",
    "Dosyayi kisiye ac, baglantisi olan herkese acik birakma",
    "Erisim iznine bir bitis tarihi koy ve suresi dolunca gozden gecir",
    "Yanlis gonderimi fark ettiginde kime bildirecegini onceden bil",
]


# GRUPLAMA MALZEMESI. `add_drag_question` (tur, 9) tohumunu istiyor, yani
# dokuz oge; eksik verilirse kurulum REDDEDILIR ve kapi kusurdan degil
# beslemeden kirmiziya doner.
DRAG_GROUPS = {
    "Once yapilir": ["Sakin bir ton tut", "Kesmeden dinle", "Not al"],
    "Sonra yapilir": ["Ozetleyerek dogrula", "Secenek sun", "Sureyi soyle"],
    "Hic yapilmaz": ["Ayni tonda karsilik ver", "Sozunu kes", "Suclu ara"],
}


def _outline() -> dict:
    return {"scenes": [
        {"name": name, "title": title, "slides": [
            {"title": title, "layout": "section", "kind": "content"},
            {"title": title + " A", "layout": "content", "kind": "content"},
            {"title": title + " B", "layout": "bullets", "kind": "content"},
            {"title": "Soru", "layout": "content", "kind": "question"}]}
        for name, title in SCENES]}


def _content(index: int) -> dict:
    title = SCENES[min(index, len(SCENES)) - 1][1] if index else SCENES[0][1]
    return {"slides": [
        # Seyrek govde: yogunluk olcegini calistirir.
        {"kind": "content", "layout": "section", "eyebrow": f"Bolum {index}",
         "title": title, "body": "Kisa bir giris."},
        {"kind": "content", "layout": "content", "eyebrow": f"Bolum {index}",
         "title": "Gerginlik masaya nasil geliyor",
         "body": "Musteri gerildiginde sesin tonu degisir, cumleler kisalir ve "
                 "ayni sikayet farkli kelimelerle tekrar eder."},
        # KART BANDI TABANI. Onceki hali DORT madde ve 11-22 karakterdi;
        # "cok maddeli kart" diye yaziyordu ama rezervasyonu hic zorlamiyordu
        # ve `tasma_orani` 0.95'te kaliyordu -- yani hicbir kutu dolmuyordu
        # bile. Gercek kursta olculen: BES madde, 50-60 karakter, ve orada
        # kutular metnin BESTE BIRINE dusmustu (oran 5.73).
        #
        # Sayilar GERCEK kurstan okundu, secilmedi: Title medyan 24 (prob 9),
        # Body medyan 73 (prob 21), Lead medyan 64 (prob 15).
        # REVEAL: insa yolunun TIKLANINCA ACILAN duzeni. Buraya konuldu
        # cunku produced.py'nin isi tam olarak bu -- prob degil, URETILMIS
        # kursta kosmak. Etiketler sinirda secildi (28-30 karakter): kisa
        # etiketle kosmak, bandin dar oldugu vakayi gormezden gelmek olurdu.
        {"kind": "content", "layout": "reveal", "eyebrow": f"Bolum {index}",
         "title": "Gerginligin uc isareti",
         "body": "Her birine tiklayarak ac.",
         "items": [
             {"label": "Ses tonundaki yukselme",
              "detail": "Ton, sozcuklerden once degisir. Cumleler kisalir ve "
                        "araliklar daralir; icerik henuz aynidir."},
             {"label": "Ucuncu kez tekrar",
              "detail": "Ayni sikayetin ucuncu kez anlatilmasi, dinlenmedigini "
                        "dusundugunun isaretidir."},
             {"label": "Ani sessizlik",
              "detail": "Sessizlik cogu zaman sakinlesme degil vazgecistir; "
                        "konusma orada biter."}]},
        {"kind": "content", "layout": "bullets", "eyebrow": f"Bolum {index}",
         "title": "Gerginligin masada biraktigi izler",
         "bullets": [
             "Ses tonu yukselir ve cumleler kisalir, sozler ustuste biner",
             "Soz kesilir; karsi taraf dinlendigini artik hissetmiyordur",
             "Ayni sikayet farkli kelimelerle ucuncu kez tekrar edilir",
             "Konusma bugunden gecmise kayar ve eski kayitlar acilir",
             "Cozum yerine suclu aranmaya baslanir, konu dagilir"]},
        # SAHNE 1'DE SIK SORUSU YOK, GRUPLAMA VAR. Sebep olculdu
        # (2026-09-04): `PUANLI_KINDLER = ("question", "drag")` ve sahne
        # basina bir puanli slayt kurali var. Ikisi ayni sahneye konunca
        # gruplama sessizce ELENIYOR -- red bile uretmeden, cunku eleme
        # dispatch'ten ONCE oluyor. `hotspot` ve `commitment` puanli
        # sayilmadigi icin ayni sahnede yasayabiliyor.
        *([] if index == 1 else [{"kind": "question",
         "prompt": f"Bolum {index}: musteri sesini yukseltti ve ayni sikayeti "
                   "ucuncu kez anlatiyor. Ilk ne yaparsin?",
         # IKI YOL DA GECILIR: tek secmeli (2 sik) ve coktan secmeli (5 sik).
         # Tek yolla kosmak, digerinin kusurlarini gorunmez kilar.
         "choices": list(LONG_CHOICES if index % 2 else MULTI_CHOICES),
         "correct": [0] if index % 2 else [0, 1],
         "feedback": {"correct": "Sakin ton gerginligi dusurur ve musteri "
                                 "kendini duyulmus hisseder.",
                      "incorrect": "Ayni tonda karsilik vermek tirmandirir; "
                                   "once kesmeden dinleyin."}}]),
    ]
        # BES BICIMIN HEPSI KAPIDAN GECER. Onceki hali yalnizca `choices`
        # tasiyordu, yani `freePickOne` ile `freePickMany` uretiyor ve
        # kalan UC bicimi -- dragDrop, freeHotSpot, freeTextEntry -- kapinin
        # disinda birakiyordu. Bedeli olculdu 2026-09-04: iki gercek kusur
        # tam o uc bicimin ikisinde yasiyordu ve suit YESILDI.
        #
        #   eksik defVarG (freeHotSpot tohumu)  -> dosya HIC acilmiyor
        #   fakeTrigger   (freeHotSpot + freeTextEntry) -> slayt atlaniyor
        #
        # Ayni kor nokta bu dosyada BIR KEZ DAHA yasandi (coktan secmeli
        # yol yoktu, yukaridaki nota bakin). Ucuncusu olmasin diye kapsam
        # artik `main()` icinde OLCULUYOR, umut edilmiyor.
        + _kapsam_slaytlari(index)}


def _kapsam_slaytlari(index: int) -> list[dict]:
    """Tohum kutuphanesindeki geri kalan bicimleri sahnelere dagitir.

    Dagitim SAHNE SAYISINA bagli; sahne sayisi dusurulurse bir bicim
    disarida kalir. Bu sessiz kalmaz: `main()` kapsami tohum kutuphanesine
    karsi olcup eksigi KUSUR olarak bildirir.
    """
    if index == 1:
        return [{"kind": "drag",
                 "prompt": "Adimlari dogru kutuya surukle.",
                 "groups": dict(DRAG_GROUPS),
                 "feedback": {"correct": "Sira dogru: once dinleme, sonra dogrulama.",
                              "incorrect": "Once dinleme gelir; karsilik vermek tirmandirir."}}]
    if index == 2:
        # accept VERILIR: aksi halde slayt taahhut kutusuna doner ve
        # `freeTextEntryIntr` bicimi kapidan hic gecmez.
        return [{"kind": "commitment",
                 "prompt": "Gerginlik aninda ilk yapilmasi gereken nedir? "
                           "Tek kelimeyle yaz.",
                 "accept": ["dinlemek", "dinle", "dinleme"]}]
    if index == 3:
        return [{"kind": "hotspot",
                 "prompt": "Gorselde gerginligin ilk isaretini gosteren alani tikla.",
                 "feedback": {"correct": "Dogru: ses tonundaki yukselme ilk isarettir.",
                              "incorrect": "Tekrar bak: ilk isaret sozel degil, tonaldir."}}]
    return []


def build() -> StoryPackage:
    calls = {"n": 0}

    def canned(prompt, model="sonnet", timeout=300.0, on_progress=None,
               deneme=2):
        # IMZA BUILDER'INKINI TAKIP EDER. `on_progress` ve `deneme`
        # eklendiginde bu vekil guncellenmemisti ve kontrol TypeError ile
        # duruyordu -- yani uretilmis kursa bakan TEK kontrol, kendi
        # vekilinin eskimesi yuzunden hic kosmuyordu. Sessiz degil ama
        # gorunmez: kimse calistirmadikca yesil de kirmizi da yok.
        # KIMLIKLE ESLE, SAYACLA DEGIL.
        #
        # Onceki hali "birinci cagri iskelet, N'inci cagri (N-1). sahne"
        # varsayiyordu. Iki sey birden yanlisti ve ikisi de SESSIZDI:
        #
        #   1. Basta IKI icerik-disi cagri var, bir tane degil. Yani her
        #      sahne BIR SONRAKININ icerigini aliyordu; sahne 4 hic
        #      tanimlanmamis bir indeksle default'a dusuyordu.
        #   2. builder icerigi YENIDEN ISTEYEBILIYOR ("icerik yeniden
        #      istendi"). Her yeniden istek sayaci bir kaydiriyor, yani
        #      duzeltme istegi bir sonraki sahnenin cevabini aliyordu.
        #
        # Olculdu 2026-09-04: 4 sahne icin 5 cagri bekleniyordu, 7 oldu; ve
        # fiksture eklenen gruplama slaydi bu yuzden HIC kurulmadi -- red
        # bile uretmeden, cunku istegi hic ulasmadi.
        #
        # Sahne basligi istemde birebir duruyor; eslesme oradan kurulur ve
        # yeniden isteklere karsi bagisiktir.
        calls["n"] += 1
        eslesen = [i for i, (_, _baslik) in enumerate(SCENES, start=1)
                   if _baslik in prompt]
        if len(eslesen) == 1:
            return _content(eslesen[0])
        # Tek sahne secilemiyorsa istek iskelet (ya da butun kursu kapsayan
        # bir duzeltme) demektir. Belirsizlik SAYILIR: sessizce dogru cevap
        # vermis gibi yapmak, yukaridaki iki hatanin da yaptigi seydi.
        calls.setdefault("belirsiz", []).append(len(eslesen))
        return _outline()

    original = builder._run_json
    builder._run_json = canned
    try:
        shutil.copy2(BLANK, WORK)
        # DEVRALINAN SLAYTLAR AYRI TUTULUR. BLANK adi "bos" diyor ama oyle
        # olmak zorunda degil ve olculdu (2026-09-04): test/bos.story bir
        # onceki oturumun debug build'iyle 37 slayda cikmisti. Kapsam
        # devralinan slaytlardan doldurulursa kapi, INSA YOLU hic
        # calismadigi halde yesil verir -- nitekim verdi.
        with zipfile.ZipFile(BLANK) as _z:
            devralinan = {n for n in _z.namelist()
                          if n.startswith("story/slides/slide")
                          and n.endswith(".xml") and "_rels" not in n}
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            report = builder.build(str(WORK), "Zor musteriyle iletisim",
                                   options={"theme": "kagit", "minutes": "20",
                                            "questions_per_section": "1",
                                            "tone": "hikaye"},
                                   on_progress=lambda text: None)
    finally:
        builder._run_json = original
    return StoryPackage(WORK), report, devralinan


# Uretilmis bir kursta SIFIR olmasi gereken siniflar. Hicbiri "tasarim
# tercihi" degil: her biri ogrencinin gordugu somut bir bozukluk.
# "tasma" BURADAN CIKARILDI ve sebebi olculdu (2026-08-16).
#
# Iddia suydu: "metin kutusundan tasiyor, Storyline kirpar" -- yani
# ogrenci metnin bir kismini KAYBEDER. Bu bir DOGRULUK hatasi olurdu.
#
# Sinandi: 20 birimlik bir kutuya on sert satir konup Storyline
# Preview'da acildi. ON SATIRIN HEPSI OKUNUYOR -- kutunun cok disina
# tasmis, hicbiri kesilmemis. Ayni sey marj vakasinda da (3 satirlik
# kutu, 4 satir) goruldu, ve kontrol satiri metnin cizildigini
# dogruladi. Yani Storyline TASAN METNI KIRPMIYOR.
#
# Sonuc: tasma bir doğruluk hatasi degil, KOZMETIK bir duzen sorunu.
# Metin kaybolmuyor, komsusunun uzerine biniyor. Olcu KALIYOR ve
# rapor ediliyor, ama uretimi durduran bir kapi degil.
MUST_BE_ZERO = {
    "cakisma": "iki metin kutusu ust uste",
    "taban": "sekil slaydin tabaninin altinda",
    "kontrast": "yazi zemininden ayrismiyor (WCAG AA)",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--png")
    args = parser.parse_args()

    pkg, report, devralinan = build()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        found = inventory.audit(pkg)
        survey = completeness.survey(pkg)

    print(f"uretilen kurs: {found['_slides']} slayt, {found['_filled']} dolu, "
          f"{len(survey['scored'])} puanli soru")
    print()
    problems = []
    for key, why in MUST_BE_ZERO.items():
        value = found[key]
        print(f"  {key:<10}{str(value):<6}{'temiz' if not value else 'KUSUR'}"
              f"   {why}")
        if value:
            problems.append(f"{key}: {value} ({why})")

    # Uretilen sorular istenen kadar mi -- devralinan bos slaytlar AYRI
    # sayilir, cunku onlar kaynak dosyanin sorunu ve burada sabit.
    #
    # "scored" YETMEZ ve bu satir bir kez yaniltti: etkilesim tasimak soruyu
    # cevaplanabilir yapar, LMS'e bildirilebilir yapmaz. Uc halka ayri ayri
    # sorulur, cunku ayri ayri kirilirlar.
    want = len(SCENES)
    izleme = survey["izleme"]
    print(f"\n  soru      {len(survey['scored'])}/{want}"
          f"     {'temiz' if len(survey['scored']) >= want else 'EKSIK'}")
    if len(survey["scored"]) < want:
        problems.append(f"{want} soru istendi, {len(survey['scored'])} puanli")

    print(f"  kayitli   {len(survey['kayitli'])}/{len(survey['scored'])}"
          f"     {'temiz' if not survey['kayitsiz'] else 'KUSUR'}"
          f"   quiz'e kayitli degilse skor LMS'e gitmez")
    print(f"  lms hedef {izleme['lms_hedefi'] or 'BOS':<9}"
          f"  trackMode={izleme['track_mode']}")
    if survey["kayitsiz"]:
        problems.append(f"{len(survey['kayitsiz'])} soru quiz'e kayitli degil "
                        "(cevap alinir, skor gitmez)")
    if survey["sorusuz_kayit"]:
        problems.append(f"{len(survey['sorusuz_kayit'])} kayit etkilesimsiz "
                        "slaydi izliyor")
    if izleme["lms_bos"] and survey["scored"]:
        problems.append("lmsResultSlideG bos — LMS'e bildirilecek sonuc "
                        "slaydi secilmemis")

    # KURULAMAYAN SLAYT SESSIZ KALMAZ.
    #
    # builder gruplama sorusunu REDDEDEBILIR ve reddi `refusals` listesine
    # yazar -- ama bu kontrol o listeye hic bakmiyordu. Olculdu 2026-09-04:
    # fiksture bir gruplama sorusu eklendi, builder onu reddetti, kontrol
    # HIC SES CIKARMADI ve kapsam devralinan bir slayttan doldu. Yani hem
    # kusur hem de kusuru gizleyen sey ayni kosuda vardi.
    # ANAHTAR ADI OLCULDU, TAHMIN EDILMEDI: builder bunu
    # `question_refusals` diye donduruyor. Ilk yazimda `refusals`
    # yazilmisti ve kontrol SESSIZCE hep temiz gorunuyordu -- yani
    # kontrolun kendisi, yakalamak icin yazildigi hatanin aynisini
    # yapiyordu.
    reddedilen = report.get("question_refusals") or []
    if reddedilen:
        print(f"\n  kurulamayan   {len(reddedilen)}")
        for _r in reddedilen[:5]:
            print(f"      {_r.get('diagnosis','?')}: {str(_r.get('why',''))[:90]}")
        problems.append(
            f"{len(reddedilen)} slayt kurulamadi "
            f"({reddedilen[0].get('diagnosis','?')})")

    # BICIM KAPSAMI: kutuphanede ne varsa URETILEN slaytlarda da olmali.
    #
    # Bu olcut BUGUN GECIYOR ve mevcut bir hatayi yakalamiyor. Varlik sebebi
    # olculmus bir gecmis: 2026-09-04'te iki gercek kusur, tam da bu kapinin
    # HIC uretmedigi soru bicimlerinde yasiyordu ve suit YESILDI.
    #
    #   eksik defVarG (freeHotSpot tohumu)          -> dosya HIC acilmiyor
    #   fakeTrigger   (freeHotSpot + freeTextEntry) -> slayt preview'da atlanir
    #
    # Kapi Storyline'a "bunu acar misin" diye soruyordu ve dogru soruydu;
    # yanlis olan, SORDUGU KURSTA o yollarin bulunmamasiydi. Ayni korluk bu
    # dosyada daha once bir kez daha yasandi (coktan secmeli yol yoktu --
    # MULTI_CHOICES notuna bakin). Ucuncusu icin umut yerine olcum konuyor.
    #
    # Beklenen kume ELLE YAZILMADI: question_seeds() diskteki tohumlardan
    # turetilir, yani kutuphaneye yeni bir bicim eklendiginde kapi onu
    # KENDILIGINDEN talep eder.
    #
    # DEVRALINANLAR SAYILMAZ: bkz. build() icindeki not.
    kutuphane = {kind for kind, _ in authoring.question_seeds()}
    uretilen = set()
    with zipfile.ZipFile(WORK) as z:
        for _ad in z.namelist():
            if (_ad.startswith("story/slides/") and _ad.endswith(".xml")
                    and "_rels" not in _ad and _ad not in devralinan):
                _raw = z.read(_ad).decode("utf-8", "replace")
                uretilen |= set(re.findall(r"<(\w+Intr)\b", _raw))
    eksik = sorted(kutuphane - uretilen)
    print(f"\n  bicim kapsami {len(kutuphane & uretilen)}/{len(kutuphane)}"
          f"    {'temiz' if not eksik else 'EKSIK: ' + ', '.join(eksik)}")
    if eksik:
        problems.append(
            f"{len(eksik)} soru bicimi URETILEN slaytlarda YOK "
            f"({', '.join(eksik)}) -- o yollardaki kusurlar acilma testine "
            "hic girmez")

    print(f"\n  ikiz slayt cifti : {found['ikiz_slayt']}")
    print(f"  farkli punto     : {found['punto_olcegi']}  {found['_sizes']}")
    print(f"  en cok x'in payi : %{found['hizalama']}")
    print("  (uc satir TASARIM yonu, kusur degil -- esikleri henuz yok)")

    if args.png:
        subprocess.run([sys.executable, str(ROOT / "tools" / "look.py"),
                        str(WORK), "--cols", "5", "--card", "300",
                        "-o", args.png], check=True)

    print()
    if problems:
        print(f"{len(problems)} KUSUR (uretilmis kursta):")
        for problem in problems:
            print(f"  ! {problem}")
        return 1
    print("Uretilmis kurs, olculen her sinifta temiz.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
