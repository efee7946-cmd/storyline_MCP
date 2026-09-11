"""Bütün kontroller, doğru sırada, tek çıkış koduyla.

"On bir kontrol yesil" cumlesi elle kosulan on bir komut demekti. Bu bir
kayit tutma sorunu degil, bir K8 sorunu: cagrilmayan kontrol kontrol degil
script. Envanter cikarilirken goruldu ki `inventory.py` ve `produced.py` --
paketin uretilmis bir kursa bakabilen tek iki araci -- hicbir yerden
cagrilmiyordu.

Bu dosyanin ucu birden yapmasi gereken sey var:

  SIRA        Bazi kontroller baskasinin urettigi dosyayi okuyor ve bu bagimlilik
              bugune kadar hicbir yerde yaziliydi degildi. invariants.check_text_fits
              ve deadband, _canary/variety.story'yi okur -- onu variety.py
              uretir. invariants.check_no_overlap ayrica test/_rubrik/*.story
              okur, onu rubric_fixtures.py uretir. Yanlis sirada kosuldugunda
              bu kontroller BAGIRMAZ: dosya yoksa sessizce bos liste doner
              (check_text_fits'in kendi kodunda yazili). Yani yanlis sira,
              gecen bir suit uretir.

  KANARYA     Once dogrulayici sinanir. canary.py Storyline'in gercekten
              acip acmadigini sorar (pahali, --tam ile), coverage --kanarya
              kapsam iddiasini kasten bozarak sinar (ucuz, her zaman kosar).
              Kanarya kalirsa geri kalan hicbir yesil bir sey ifade etmez ve
              kosu terk edilir.

  KAPI/RAPOR  Her arac bir kapi degil. consistency.py, inventory.py ve
              silhouette.py ne yazarsa yazsin 0 doner -- onlar olcum basar,
              verdikt vermez. Ikisini ayni listede esit gostermek, olmayan
              bir korumayi var sanmaktir; o yuzden sutun ayri.

    python tools/suit.py           Storyline gerektirmeyen her sey
    python tools/suit.py --tam     + canary/open_test (acilma fazi ~25 dk)
    python tools/suit.py --liste   ne kosacagini yaz, kosma
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
# Referans, depo kokunun DISINDA (Art/test/...). Adimlar ROOT icinden
# kosuluyor, dolayisiyla goreli bir yol sessizce yanlis yere bakar -- ilk
# kosuda tam olarak oyle oldu ve iki adim "Dosya bulunamadi" ile dustu.
REFERANS = str(ROOT.parent / "test" / "_referans" / "referans.story")
URETILMIS = str(ROOT.parent / "test" / "_canary" / "uretilmis.story")

# ad, komut, kapi mi, pahali mi, uretir/okur notu, [beklenen cikis kodu]
#
# Beklenen kod varsayilan 0, ama her adim icin 0 DOGRU CEVAP DEGIL:
# canary.py tasarim geregi 2 doner ("hukum yok"). Bunu tek tek yazmak,
# "sifir disi = hata" varsayimini adim adim sinanabilir kilar.
#
# Sira BAGIMLILIKTIR, tercih degil. Uretenler tuketicilerinden once gelir;
# asagidaki "uretir/okur" sutunu o zinciri gorunur tutar, boylece birisi
# sirayi degistirdiginde neyi kirdigini okuyabilir.
ADIMLAR = [
    ("scope",           [PY, "tools/scope.py"],
     True,  False, "kapsam iddialarini kosar"),
    ("consistency",     [PY, "tools/consistency.py"],
     False, False, "yalnizca kaynak kodu; 3 = KOSAMADI (mcp paketi yok)"),
    # RED MESAJI KAPISI. Ustteki kapilarin hepsi URETILEN seye bakiyor;
    # bu, aracin REDDEDERKEN ne soyledigine. Kapatilan kusur sinifi:
    # mcp 2.x yalnizca `ToolError`in metnini geciriyor, `StoryError` duz
    # bir RuntimeError oldugu icin maskeleniyordu -- yani depodaki 157
    # `raise StoryError`in MCP yuzeyinden gecen her biri DILSIZDI ve
    # ajanin gordugu tek sey "Error executing tool <ad>" oluyordu.
    #
    # Nicin bir kapi: bu bir gorunum kusuru degil. Reddin sebebini
    # okuyamayan ajan, en cok isiranda (`build_course`) hangi islemin
    # dustugunu de goremez -- teshis URETILIYOR ve maske onu yiyordu.
    # Sessizce geri dusen bir yama, kursu bozmadan ajani korlestirir.
    #
    # Fikstur GEREKTIRMEZ (kasitli red icin olmayan bir dosya yolu yeter),
    # o yuzden `produced`tan once ve temiz klonda da kosar. Fikstur varsa
    # ustune compose kapisini da ucdan uca sinar.
    ("red mesaji",      [PY, "tools/red_mesaji.py"],
     True,  False, "gercek istemci + stdio; 3 = KOSAMADI (mcp istemcisi yok)"),
    # PUANLANABILIRLIK KAPISI. `ogretim` gibi URETICIYI DEGIL OLCUYU
    # koruyor. Iki kusur sinifi da "arac basariyla dondu" halinde dogar:
    # cevaplanamaz soru (aralik disi `correct`, tohum kolu denetimden
    # once donuyordu) ve bos quiz kaydi (51 kursun 24'unde quizLst tek ve
    # BOS -- kurs LMS'e hicbir puan raporlayamaz). Dort ayak: cipa,
    # ekili kusur, KAPSAM (surukle-birak cevapsiz sayilmamali) ve yazma
    # kapisi. Ucuncusu olmadan ilk ikisi kor bir olcuyle de gecilir.
    ("puanlanabilirlik", [PY, "tools/puanlanabilirlik.py"],
     True,  False, "URETIR: _canary/puanlanabilirlik*.story; 3 = fikstur yok"),
    # OTURUM KAPISI. Geri donus noktasi ve ayak izi olcusu -- ikisi de
    # SESSIZCE olebilir: anlik goruntu alinmazsa fark bos doner ve bos
    # fark "hicbir sey degismedi" gibi okunur. Alti ayak, en onemlisi
    # KIMLIK: eslesme guid uzerinden, konum uzerinden degil (konuma bakan
    # bir uygulama, slayt eklenince dokunulmamis slaytlari "degisti"
    # gosterirdi). SILME bu kapida OLCULMUYOR -- araci henuz yok.
    ("oturum",          [PY, "tools/oturum_kapi.py"],
     True,  False, "URETIR: _canary/oturum_kapi*.story; 3 = fikstur yok"),
    # DUZENLEME KAPISI. `move_shape`/`delete_shape` yuzeyin ILK duzeltme
    # araclari: 52 aracin hepsi ekliyordu. Ikisi de yeni bir sessiz kusur
    # sinifi aciyor -- yanlis sekli tasimak/silmek ve silerken referans
    # kirmak; ikisi de "basarili" doner. Alti ayak, ikisi ozellikle:
    # DURUM GOVDESI (tasima `shapes.set_loc`ten gecmezse isabet alani
    # oynar, resim yerinde kalir) ve COZUCU (duzenle'nin cozucusu
    # logic'inkinden GENIS; ayak ikisinin ayristigini kanitlar).
    ("duzenle",         [PY, "tools/duzenle_kapi.py"],
     True,  False, "URETIR: _canary/duzenle_kapi*.story; 3 = fikstur yok"),
    ("variety",         [PY, "tools/variety.py"],
     True,  False, "URETIR: _canary/variety.story"),
    # USLUP AYRIMI. variety bir kursun KENDI icinde tekrar edip etmedigine
    # bakar; bu, IKI KURSUN birbirine benzeyip benzemedigine. "Panelden cikan
    # her sey tek makineden gecmis gibi" sikayetinin olculebilir hali.
    #
    # KAPI OLAN SEY ORAN DEGIL, OLCUNUN KENDISI. Oran TABANA
    # (uslup_taban.json) karsi raporlanir; kapi, arac kendi iki yonlu
    # kanaryasini gecti mi.
    #
    # Olcu ilk kuruldugunda oran 0.000'di: dort uslup 21 hucrenin
    # hicbirinde farkli bir resim uretmiyordu, cunku STYLES geometriye
    # dokunmuyordu. `cards`/`cta` tedavilerinden sonra 0.444. Orani kapi
    # yapmak o gun suiti KALICI kirmiziya boyardi ve kalici kirmizi bir
    # kapi sinyal uretmeyi birakir -- taban o yuzden ulasilan degerde
    # dondurulur, kapi degil.
    # Sifir, olcu korlestiginde de basilir -- ayirt eden tek sey o kanarya.
    ("uslup",           [PY, "tools/uslup.py"],
     True,  False, "kendi prob kurslarini kurar; KAPI = olcunun kanaryasi"),
    # DUSEN ARGUMAN KAPISI. Ustteki kapilar kursun NASIL GORUNDUGUNE
    # bakiyor; bu, cagiranin VERDIGI seyin slayda GIRIP girmedigine.
    # `section`e `buttons` vermek sessizce hicbir sey yapmiyordu --
    # ogrenciye gidecek icerik kayboluyor ve slayt "basarili" donuyordu.
    #
    # Uc ayak: beyan ile cizim IKI YONLU ortusuyor mu, ve beyan cagirana
    # GERCEKTEN ulasiyor mu (compose_slide donusundeki `cizilmeyen`).
    # Ucuncusu olmadan ilk ikisi dogru bir tabloyla ve sessiz bir donusle
    # de gecilirdi.
    ("dusen arguman",   [PY, "tools/dusen_arguman.py"],
     True,  False, "8 duzen x 4 uslup; beyan <-> cizim iki yonlu"),
    ("rubric_fixtures", [PY, "tools/rubric_fixtures.py"],
     True,  False, "URETIR: test/_rubrik/*.story"),
    ("invariants",      [PY, "tools/invariants.py"],
     True,  False, "OKUR: variety.story + _rubrik/*"),
    ("deadband",        [PY, "tools/deadband.py"],
     True,  False, "OKUR: variety.story"),
    ("golden",          [PY, "tools/golden.py"],
     True,  False, "OKUR: test/0_duz_kopya.story"),
    ("themes_check",    [PY, "tools/themes_check.py"],
     True,  False, "kendi prob slaytlarini kurar"),
    ("coverage",        [PY, "tools/coverage.py"],
     True,  False, "6 tema x 7 duzen sweep"),
    ("kapsam kanaryasi", [PY, "tools/coverage.py", "--kanarya"],
     True,  False, "OKUR: test/_referans/referans.story"),
    # Dedektorun kendi kontrolu, KAPI. Referans kusurlari uzerinde olculdugu
    # icin secilmis bir SNAPSHOT ve bozuklugu SABIT; onu saglik kapisi yapmak
    # suiti kalici kirmiziya boyar, kalici kirmizi bir kapi da sinyal uretmeyi
    # birakir. Dogru bicimi tersi: referans, dedektorun CIPASI.
    #
    # Uc ayak: bilinen bozuk referansi birebir sayiyor mu (IKI YONLU -- az
    # saymak korlesme, cok saymak gurultu, ikisi de bagirir), bilinen saglam
    # kursu temiz buluyor mu, ve kasten silinen tek kaydi yakaliyor mu.
    # Ucuncusu olmadan ilk ikisi atil bir dedektor tarafindan da gecilir:
    # hicbir seyi kayitsiz saymayan bir dedektor de "saglam kursta 0" der.
    ("completeness kontrolu", [PY, "tools/completeness.py", "--kontrol"],
     True,  False, "OKUR: referans + 0_duz_kopya; kasten bozma ayagi var"),
    ("completeness",    [PY, "tools/completeness.py", REFERANS],
     False, False, "rapor: referans BILEREK bozuk, kirmizi olmasi beklenir"),
    ("produced",        [PY, "tools/produced.py"],
     True,  False, "builder ile kurs kurar (model cagrisi YOK)"),
    # OGRETIM KAPISI. Ustteki kapilarin hepsi kursun NASIL GORUNDUGUNU
    # olcuyor; bu, ogrencinin bir sey YAPIP yapmadigina bakan olcunun
    # ayakta oldugunu olcer. `produced`tan SONRA, cunku rapor satiri
    # ureticinin taze ciktisini okuyor.
    #
    # Ureticiyi degil OLCUYU koruyor: ogretim kalitesi modelin ciktisina
    # bagli ve kapilar model cagirmaz. Korunan sey su -- olcu sessizce
    # olurse her kurs temiz gorunur.
    # YENI MODUL KAPISI. Yukaridaki kapilar kursun olculerine bakiyor;
    # bu, SIFIRDAN kurulan yeni bir modulun 2026-09-06'da duzeltilen sekiz
    # kusur sinifindan hicbirini tasimadigini sinar.
    #
    # Nicin ayri: "duzeltildi" ile "bir daha olmayacak" ayni sey degil.
    # Kullanicinin sordugu soru da buydu -- duzeltmeler bu modul icin mi,
    # yoksa sonrakiler icin mi. Bu kapi, o sorunun her kosuda tekrarlanan
    # cevabi.
    ("yeni modul",      [PY, "tools/yeni_modul.py"],
     True,  False, "URETIR: sifirdan modul; 8 kusur sinifini sinar"),
    # AJAN YOLU KAPISI, `yeni modul`un HEMEN YANINDA ve bu bilerek:
    # ikisi ayni soruyu iki YOLDAN soruyor. `yeni modul` kurucu yolu
    # (authoring + compose fonksiyonlari) uctan uca kosuyordu; bu, ajanin
    # gectigi yolu -- gercek MCP sunucusu, stdio, her cagrida `_write` --
    # kosar. Takim bir sure BIRINCIL OLMAYAN yolu uctan uca olcup
    # birincil yapilmak isteneni hic olcmuyordu.
    #
    # MODEL CAGIRMAZ: cagri dizisi betiklenmis. Olculen sey PLANLAYICI
    # degil YOL. Iddia kumesi kurucuya ESIT DEGIL (Ilerleme, medya plani
    # ve sonuc kilidi disarida) -- esitlik iddia eden bir kapi yol
    # haritasinin 3. maddesi acilana kadar INSA GEREGI kirmizi kalirdi.
    # KABLOLAMA DEGISMEZI (md. 3'un yazma tarafi). Kablolama TURETILMIS
    # -- quiz kaydi, quizG ve lmsResultSlideG dosyada zaten var olandan
    # cikiyor -- ve turetilmis bir sey adim degil DEGISMEZDIR. Adim
    # atlanabilir, degismez atlanamaz: sohbet yolunun "bitti" ani
    # olmadigi icin kapanis ADIMI kurulamiyordu, degismez o soruyu
    # ortadan kaldiriyor. `server._write` icinde, arac basina DEGIL.
    #
    # Alti ayak; ikisi ozellikle: COGALTMAZ (temiz kursta 20 yazma
    # cagrisi -> 0 degisiklik; olculen sey sure degil "kac cagrida
    # gercekten yaziyor") ve ISPATSIZ SILMEZ (soru bankasi sorulari
    # slide_index'e girmez ve "cozulemeyen" gorunur -- korpusun 52
    # kursunun 52'sinde bankLst var).
    ("kablolama",       [PY, "tools/kablolama_kapi.py"],
     True,  False, "URETIR: _canary/kablolama_*.story; 3 = mcp istemcisi yok"),
    ("ajan yolu",       [PY, "tools/ajan_yolu.py"],
     True,  False, "URETIR: _canary/ajan_yolu*.story; 3 = mcp istemcisi yok"),
    # MEDYA YERI. `produced`tan SONRA, cunku taze uretilmis kursu okuyor.
    # KAPI OLAN SEY BAYRAK DEGIL, OLCUNUN KANARYASI (uslup ile ayni bicim):
    # bes ayak -- taze slayt gecmeli, yabanci sekil/tetikleyici yakalanmali,
    # hero kapak hem gecmeli hem AYRILMIS sayilmali, katmanli slayt kalmali.
    # Bayrak (`acilabilir>0 ve ayrilmis==0`) rapor satiri; esigi yok, cunku
    # aranan sey buyukluk degil birlesim.
    ("medya yeri",      [PY, "tools/yeniden_beste.py", URETILMIS],
     True,  False, "OKUR: uretilmis kurs; KAPI = olcunun bes ayakli kanaryasi"),
    ("ogretim",         [PY, "tools/ogretim_kapi.py"],
     True,  False, "OKUR: donors/* + referans; kanarya URETIR"),
    ("inventory",       [PY, "tools/inventory.py", REFERANS],
     False, False, "rapor: kusur sinifi x invaryant"),
    # KAPI DEGIL, FIKSTUR KURUCU -- ve bunu ilk --tam kosusu ogretti. canary.py
    # tek basina hukum VEREMEZ: saglam/bozuk ikilisini kurar, "HUKUM YOK" yazar
    # ve HER ZAMAN 2 doner. Kapi sayildiginda suit onu "kanarya kaldi" diye
    # okudu ve kosuyu daha basta terk etti. Cikis kodu burada bir sonuc degil
    # bir imza: 2 beklenen degerdir, baska her sey gercek bir hatadir.
    # Asil hukmu open_test verir; kanarya kontrollerini kendi icinde kosturur.
    ("canary (fikstur)", [PY, "tools/canary.py"],
     False, True,  "URETIR: saglam/bozuk ikilisi; hukum open_test'te", 2),
    # URETILEN KURSU DE ACAR, ve bu bilerek eklendi. open_test varsayilan
    # olarak yalnizca donors/ acar; oyle birakilsaydi --tam kosusu yirmi bes
    # dakika harcayip yazma yolu hakkinda HICBIR SEY soylemezdi. Kayit
    # duzeltmesi story.xml'e yaziyor -- paketin en hassas parcasi -- ve onu
    # Storyline'in gercekten kabul ettigini yalnizca bu adim gosterir.
    # `produced` daha once kostugu icin dosya taze.
    # TUR TESTI: "aciliyor mu"nun USTUNDEKI soru -- Storyline bizim
    # yazdigimizi KORUYOR mu. `open_test` yalnizca acilmayi soruyor ve
    # acilmak dusuk bir esik: Storyline sevmedigi seyi sessizce yeniden
    # yazip kaydedebilir. Depo bundan bir kez isirildi ve kesif KAZAYDI
    # (yks.story: ikinci quizLst'teki Quiz_Result silinmis, yerine bos
    # bir Quiz1 konmustu). Uclu artik elimizde: anlik goruntu -> ac ve
    # kaydet -> fark.
    #
    # KAPI ZINCIRI savunuyor (kayit kaybi, ikinci quizLst, tur oncesi
    # temiz zincirin bozulmasi); yapisal fark RAPOR kalir, cunku
    # Storyline'in mesru normallestirmelerini kusur saymak kapiyi
    # kalici kirmiziya boyardi.
    ("tur testi",       [PY, "tools/tur_testi.py", URETILMIS],
     True,  True,  "URETILMIS'i Storyline'da ac/kaydet/karsilastir"),
    ("open_test",       [PY, "tools/open_test.py", URETILMIS, "donors"],
     True,  True,  "Storyline acar: URETILEN kurs + donor havuzu"),
]

# KOSAMADI, KOSTU-VE-DUSTU DEGIL. Bir adim on kosulu saglanmadigi icin
# hic bakamadiysa (paket yok, dosya yok) 3 doner. Ayni satirda "1" olarak
# gorunmesi tam olarak normallesen sinyal bicimi: birkac hafta sonra
# "o adim zaten kirmizi" olur, ve gercekten bir sey buldugu gun okunusu
# ayni kalir.
#
# KOSAMAYAN BIR KAPI YESILE SAYILMAZ. Bu dosyanin ilk cumlesi zaten
# "cagrilmayan kontrol kontrol degil script" diyor; bakamayan bir kontrol
# de guvence uretmez, o yuzden kapiysa kosuyu dusurur. Rapor adimlarinda
# yalnizca goruunur kalir.
#
# UC DURUM DA SINANDI (2026-09-10, ADIMLAR ve kos() prob degerlerle
# degistirilerek -- gercek dallar kosuldu, ikinci bir uygulama yazilmadi):
#     rapor kosamadi (3)     -> kod 0, "1 adim KOSAMADI: ... (rapor)"
#     KAPI kosamadi  (3)     -> kod 1, "... (KOSAMADI -- guvence uretmedi)"
#     KAPI kostu ve dustu(1) -> kod 1, duz "KAPI KALDI"
# Ucuncusunun ayri gorunmesi onemli: ikisini ayirmak icin kuruldu.
KOSAMADI = 3

# Kanaryalar en basta kosar ve KALIRSA kosu terk edilir. canary.py'nin kendi
# sozlesmesi bu: bozuk kontrol bagirmiyorsa, o kosudan gelen bir "gecti"
# hicbir sey soylemez.
KANARYALAR = {"kapsam kanaryasi"}


# Her adimin TAM ciktisi diske yazilir. Ozet tablo yalnizca son satiri
# gosteriyordu ve bu, pahali adimlarda okunamaz bir yesil uretiyor: open_test
# "Hepsi acildi" der, ama kanarya ayaklarinin gercekten AYRISTIGI -- saglam
# acildi, bozuk acilmadi -- o satirda gorunmez. Bu projede kanaryanin kendisi
# bir kez yalanci cikti; hukmun gerekcesini atan bir kosucu, o hatayi
# tekrarlanabilir kilar.
LOG = ROOT.parent / "test" / "_canary" / "suit_log"


def kos(ad: str, komut: list[str]) -> tuple[int, float, str]:
    basladi = time.monotonic()
    try:
        sonuc = subprocess.run(komut, cwd=ROOT, capture_output=True,
                               text=True, encoding="utf-8", errors="replace")
    except OSError as exc:
        return 2, time.monotonic() - basladi, str(exc)[:70]
    gecen = time.monotonic() - basladi
    govde = (sonuc.stdout or "") + (sonuc.stderr or "")
    LOG.mkdir(parents=True, exist_ok=True)
    dosya = LOG / (ad.replace(" ", "_").replace("(", "").replace(")", "") + ".txt")
    dosya.write_text(f"$ {' '.join(komut)}\n# cikis kodu {sonuc.returncode}, "
                     f"{gecen:.1f}s\n\n{govde}", encoding="utf-8")
    son = [s for s in govde.strip().splitlines() if s.strip()]
    ozet = son[-1][:70] if son else ""
    # KONSOLA YAZILAMAYAN KARAKTER RUNNER'I DUSURMEMELI. Bir adimin son
    # satirinda bozuk bir bayt vardi ve suit UnicodeEncodeError ile
    # coktu -- yani bir OLCUM sonucu, ozeti basilamadigi icin kayboldu.
    # Ozet bir kolaylik; kosunun kendisi ona bagli olmamali.
    return sonuc.returncode, gecen, ozet.encode(
        sys.stdout.encoding or "utf-8", "replace").decode(
        sys.stdout.encoding or "utf-8", "replace")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tam", action="store_true",
                        help="Storyline acan pahali adimlari da kos")
    parser.add_argument("--liste", action="store_true",
                        help="ne kosacagini yaz, kosma")
    args = parser.parse_args()

    secili = [a for a in ADIMLAR if args.tam or not a[3]]
    # Kanaryalar one alinir, ic sira korunur.
    secili.sort(key=lambda a: a[0] not in KANARYALAR)

    if args.liste:
        w = max(len(a[0]) for a in secili) + 2
        print(f"{'adim':<{w}}{'tur':<8}{'pahali':<8}not")
        for ad, _k, kapi, pahali, notu, *_b in secili:
            print(f"{ad:<{w}}{'kapi' if kapi else 'rapor':<8}"
                  f"{'evet' if pahali else 'hayir':<8}{notu}")
        atlanan = [a[0] for a in ADIMLAR if a not in secili]
        if atlanan:
            print(f"\natlanan (--tam ile gelir): {', '.join(atlanan)}")
        return 0

    # Genislik icerikten: elle yazilan bir genislik, adim adi uzadigi gun
    # sutunlari birbirine yapistirir ("completeness kontrolukapi").
    w = max(len(a[0]) for a in secili) + 2
    print(f"{len(secili)} adim, kanaryalar once.\n")
    print(f"{'adim':<{w}}{'tur':<7}{'sure':>7}{'kod':>5}  son satir")
    print("-" * (w + 78))

    kalanlar, raporlar, atlananlar = [], [], []
    for ad, komut, kapi, _pahali, _notu, *beklenen in secili:
        kod, gecen, son = kos(ad, komut)
        bekle = beklenen[0] if beklenen else 0
        tur = "kapi" if kapi else "rapor"
        if kod == KOSAMADI and bekle != KOSAMADI:
            tur = "ATLANDI"
        print(f"{ad:<{w}}{tur:<7}{gecen:>6.1f}s"
              f"{kod:>5}  {son}")
        if kod == KOSAMADI and bekle != KOSAMADI:
            atlananlar.append(f"{ad} ({'KAPI' if kapi else 'rapor'})")
            if kapi:
                kalanlar.append(f"{ad} (KOSAMADI -- guvence uretmedi)")
            continue
        if ad in KANARYALAR and kod != bekle:
            print(f"\nKANARYA KALDI ({ad}). Kosu terk edildi: dogrulayici\n"
                  "yalan soyluyorsa, geri kalan her yesil anlamsizdir.")
            return 1
        if kod != bekle:
            (kalanlar if kapi else raporlar).append(
                ad if bekle == 0 else f'{ad} (beklenen {bekle})')

    print()
    if atlananlar:
        print(f"{len(atlananlar)} adim KOSAMADI: {', '.join(atlananlar)}")
        print("  (on kosulu saglanmadi; 'temiz' DEGIL, 'bakilmadi')")
    if raporlar:
        print(f"rapor adimlarinda sifir-disi kod: {', '.join(raporlar)} "
              "(kapi degil, kosuyu dusurmez)")
    if kalanlar:
        print(f"{len(kalanlar)} KAPI KALDI: {', '.join(kalanlar)}")
        return 1
    print("Butun kapilar gecti.")
    print("KAPSAM: geri bildirim katmanlari (<sldLayerLst>) taraniyor.\n"
          "        2026-09-05'te iki kesit acildi ve kanarya ikisini de\n"
          "        dogruluyor (tools/coverage.py --kanarya): contrast.audit\n"
          "        katmanlara varsayilan olarak bakiyor, inventory.audit\n"
          "        tasmayi katmanlarda da sayiyor. Tasma olcusu zaten\n"
          "        bakiyordu (invariants.tasan_yazilar).\n"
          "        HALA OLCULMEYEN: katmanda hizalama/cakisma/taban (bunlar\n"
          "        slaydin kendi izgarasi hakkinda, katman sekilleri o\n"
          "        izgaranin parcasi degil), yatay tasmanin katman\n"
          "        karsiligi, ve elle yapilmis kurslarda zemini cozulemeyen\n"
          "        sekiller -- sonuncular 'olculemeyen' sayilir ve SESSIZ\n"
          "        kalir, ihlal diye raporlanmaz.")
    return 0


if __name__ == "__main__":
    # KANARYA KILIDI. Kapilar `test/_canary/` icine SABIT adli dosyalar
    # yaziyor; iki kosu ayni anda ayni dosyaya yazarsa ikisi de yanlis
    # okur ve sonuc "kostu ve dustu" gibi gorunur. Gerekce ve olcum:
    # tools/kanarya_kilit.py.
    from kanarya_kilit import korumali
    raise SystemExit(korumali(main))
