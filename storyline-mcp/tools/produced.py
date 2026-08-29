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
import shutil
import subprocess
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "panel"))
sys.path.insert(0, str(ROOT / "tools"))

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
        {"kind": "content", "layout": "bullets", "eyebrow": f"Bolum {index}",
         "title": "Gerginligin masada biraktigi izler",
         "bullets": [
             "Ses tonu yukselir ve cumleler kisalir, sozler ustuste biner",
             "Soz kesilir; karsi taraf dinlendigini artik hissetmiyordur",
             "Ayni sikayet farkli kelimelerle ucuncu kez tekrar edilir",
             "Konusma bugunden gecmise kayar ve eski kayitlar acilir",
             "Cozum yerine suclu aranmaya baslanir, konu dagilir"]},
        {"kind": "question",
         "prompt": f"Bolum {index}: musteri sesini yukseltti ve ayni sikayeti "
                   "ucuncu kez anlatiyor. Ilk ne yaparsin?",
         # IKI YOL DA GECILIR: tek secmeli (2 sik) ve coktan secmeli (5 sik).
         # Tek yolla kosmak, digerinin kusurlarini gorunmez kilar.
         "choices": list(LONG_CHOICES if index % 2 else MULTI_CHOICES),
         "correct": [0] if index % 2 else [0, 1],
         "feedback": {"correct": "Sakin ton gerginligi dusurur ve musteri "
                                 "kendini duyulmus hisseder.",
                      "incorrect": "Ayni tonda karsilik vermek tirmandirir; "
                                   "once kesmeden dinleyin."}}]}


def build() -> StoryPackage:
    calls = {"n": 0}

    def canned(prompt, model="sonnet", timeout=300.0, on_progress=None,
               deneme=2):
        # IMZA BUILDER'INKINI TAKIP EDER. `on_progress` ve `deneme`
        # eklendiginde bu vekil guncellenmemisti ve kontrol TypeError ile
        # duruyordu -- yani uretilmis kursa bakan TEK kontrol, kendi
        # vekilinin eskimesi yuzunden hic kosmuyordu. Sessiz degil ama
        # gorunmez: kimse calistirmadikca yesil de kirmizi da yok.
        calls["n"] += 1
        return _outline() if calls["n"] == 1 else _content(calls["n"] - 1)

    original = builder._run_json
    builder._run_json = canned
    try:
        shutil.copy2(BLANK, WORK)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder.build(str(WORK), "Zor musteriyle iletisim",
                          options={"theme": "kagit", "minutes": "20",
                                   "questions_per_section": "1",
                                   "tone": "hikaye"},
                          on_progress=lambda text: None)
    finally:
        builder._run_json = original
    return StoryPackage(WORK)


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

    pkg = build()
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
