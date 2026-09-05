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
     False, False, "yalnizca kaynak kodu; cikis kodu YOK"),
    ("variety",         [PY, "tools/variety.py"],
     True,  False, "URETIR: _canary/variety.story"),
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
    ("open_test",       [PY, "tools/open_test.py", URETILMIS, "donors"],
     True,  True,  "Storyline acar: URETILEN kurs + donor havuzu"),
]

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

    kalanlar, raporlar = [], []
    for ad, komut, kapi, _pahali, _notu, *beklenen in secili:
        kod, gecen, son = kos(ad, komut)
        bekle = beklenen[0] if beklenen else 0
        print(f"{ad:<{w}}{'kapi' if kapi else 'rapor':<7}{gecen:>6.1f}s"
              f"{kod:>5}  {son}")
        if ad in KANARYALAR and kod != bekle:
            print(f"\nKANARYA KALDI ({ad}). Kosu terk edildi: dogrulayici\n"
                  "yalan soyluyorsa, geri kalan her yesil anlamsizdir.")
            return 1
        if kod != bekle:
            (kalanlar if kapi else raporlar).append(
                ad if bekle == 0 else f'{ad} (beklenen {bekle})')

    print()
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
    raise SystemExit(main())
