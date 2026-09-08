"""Slaytta hiçbir şeyin olmadığı alan: en büyük yatay bant ve toplam oran.

GÖREV 5 (tipografi ve tema) için ölçülmüş başlangıç referansı. Buradaki sayı
bir hatanın kanıtı değil, işin nereden başlayacağının kaydı: tipografi işine
girildiğinde bu tabana bakılır, yeniden ölçmek gerekmez.

ÖLÇÜLEN (2026-08-14, tools/variety.py DECK'i, content düzeni, altı varyant):

                        en buyuk bant     toplam bos
    maddeli slaytlar     %0 - %7           %0 - %26     (5 slayt)
    maddesiz slaytlar   %10 - %41         %26 - %54     (5 slayt)

Yani seyrek içerikli bir slaytta sayfanın yarıdan fazlası boş kalabiliyor.
Sebep yerleşimde değil: `content` düzeni üç küçük bloğu (üst etiket, başlık,
gövde) bütün çerçeveye dağıtıyor ve içerik azaldığında punto ölçeği yukarı
çıkmıyor. Bir tasarımcı altı kelimelik bir gövdeyi 16:9 bir çerçeveye koyarken
yazıyı büyütür; motor büyütmüyor, boşluğu büyütüyor.

İki grup %26'da değiyor: ayrım kategorik değil, süreklilik. Maddeli bir slayt
da az maddeyle seyrekleşiyor. Tipografi işi "maddesiz slaytları düzelt" diye
değil, "içerik yoğunluğuna göre ölçeklen" diye kurulmalı.

Bu, varyant motorunun getirdiği bir gerileme DEĞİL -- GÖREV 4 öncesinde de
vardı, ilk g2 kursunun "Parola Hijyeni" slaydında aynı boşluk görünüyor.

Tam genişlikte şeritler (arka plan, üst şerit, alt bant) banda sayılmaz:
slaydın her yerine değen bir şerit, boş bir bandı teknik olarak doldurur ama
gözün gördüğü boşluğu doldurmaz.

    python tools/deadband.py                    tabanla karsilastir
    python tools/deadband.py --story kurs.story baska bir kursu olc
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from storyline_mcp import model, shapes
from storyline_mcp.package import StoryPackage
import scope

# Olculen taban: TOPLAM bos oran.
#
# Yogunluk olceklemesinden SONRA yenilendi. Yenilemek zorunlu: guard tek
# yonlu (yalnizca kotulesmeyi gorur), dolayisiyla eski taban birakilsaydi
# %44'ten %54'e geri donus hicbir sey bagirmadan gecerdi -- iyilesmeyi
# kaydetmemek, onu koruyacak testi de kaybetmek demek.
#
#   once  (2026-08-14, olcekleme yok)   maddeli %0-%26   maddesiz %26-%54
#   sonra (yogunluk olcegi devrede)     maddeli %0-%19   maddesiz %24-%44
# YENIDEN OLCULDU (2026-08-17), coverage'in EMPTY_BASELINE'i ile AYNI
# gerekcede ve ayni turda. Ikisi de ayni olcuyu (bos alan) farkli kesitte
# alir, dolayisiyla ayri ayri yenilenmeleri ikisini ayristirirdi.
#
# Gerekce ozeti: eski taban yeniden uretilemedi. Olcum, yerlesim ve yapisal
# sabitlerin hepsi tek tek elendi; `content` icin rejim farki BULUNDU
# (TYPE_LADDER merdiveni, %38 -> %52) ve merdiven tabandan yeni. Kalan
# duzenler icin provenance yok ve kayit ACIK. Ayrinti coverage.py'de.
#
# "maddesiz" ust ucu %46 -> %52: merdivenin bedeli. Merdiven tipografik
# tutarlilik aliyor (uretilmis kursta 16 farkli punto -> 8 basamak),
# doldurma veriyor. Takas BILINCLI; bedeli ilk kez olculdu.
_ESKI_TABAN_2026_08_16 = {"maddeli": (0, 25), "maddesiz": (26, 46)}
BASELINE = {"maddeli": (0, 25), "maddesiz": (26, 52)}
#
# PUNTO MERDIVENI SONRASI (2026-08-16). Iki yonlu degisti, ikisi de kayitli:
#
#     maddesiz  %44 -> %46   artis (kucuk)
#     maddeli   %19 -> %25   artis
#
# Artis bir GERILEME DEGIL, ve bunu ayirt eden sey iki ayri sayinin varligi:
# ayni slaytta EN BUYUK BANT %5te kaldi. Yani %25lik bosluk tek bir cukurda
# degil, alti kucuk aralikta dagilmis -- blok aralari, yani ritim. Tek bir
# ozet sayi tutulsaydi bu "kotulesme" diye okunurdu.
#
# Sebep merdivenin KABALIGI degil: govde araligina bir ara basamak (15pt)
# eklenip olculdu ve sayilar HIC degismedi. Boyle bir notu "muhtemelen
# kabalik" diye birakmak, birinin ileride bosuna basamak eklemesine yol
# acardi.
FULL_WIDTH = 0.97   # bunun ustu serittir, bant doldurmaz
BAND = (8, 92)      # CEILING .. FLOOR


def dead_band(pkg: StoryPackage, part: str) -> tuple[int, int, int]:
    """(en büyük boş bant, toplam boş oran, banda katılan şekil sayısı).

    İkisi birden ölçülür çünkü tek başına ilki yanıltıyor: ortalanmış bir
    buton, aynı büyüklükteki boşluğu ikiye bölüyor ve "en büyük bant" yarıya
    iniyor. Ölçüldü -- bir slayt %41, aynı seyreklikteki bir başkası %10, tek
    fark butonun boşluğun ortasına düşmesi. Toplam boş oran o bölünmeden
    etkilenmez.
    """
    root = pkg.parse(part)
    shape_list = root.find("shapeLst")
    if shape_list is None or not len(shape_list):
        return (0, 0, 0)
    width, height = shapes.slide_size(root)
    rows = [False] * 100
    counted = 0
    for shape in shape_list:
        rect = shapes.shape_rect(shape)
        if not rect:
            continue
        left, top, right, bottom = rect
        if (right - left) * (bottom - top) > 0.92 * width * height:
            continue
        if (right - left) / width > FULL_WIDTH:
            continue
        counted += 1
        for y in range(int(top / height * 100),
                       min(int(bottom / height * 100) + 1, 100)):
            rows[y] = True
    best = run = total = 0
    for y in range(*BAND):
        run = 0 if rows[y] else run + 1
        best = max(best, run)
        total += not rows[y]
    return best, round(total / (BAND[1] - BAND[0]) * 100), counted


# Bos hucre esigi. silhouette.grid kismi ortusmeyi de sayiyor: bir seklin
# kenarina degen hucre kucuk bir deger tasir. 0.02, "bu hucrede murekkep
# yok" ile "koseden azicik degmis" arasindaki sinir; hucre alaninin %2'si.
BOS_ESIK = 0.02


def en_buyuk_delik(pkg: StoryPackage, slayt: str) -> tuple[int, int]:
    """(en büyük boş DİKDÖRTGEN %, boş hücre toplamı %).

    NEDEN BANDIN YANINA IKINCI BIR OLCU. `dead_band` TEK BOYUTLU: sekilleri
    y eksenine izdusurur ve "hicbir seklin degmedigi satir" sayar. O olcu
    iki farkli seyi ayni sayiya indiriyor:

        dagilmis bosluk     blok aralari, satir araligi, kartlar arasi nefes
        havuzlanmis bosluk  tek parca delik -- doldurulmamis bir sutun

    Ayrim bu dosyada zaten yaziliydi ("%25lik bosluk tek bir cukurda degil,
    alti kucuk aralikta dagilmis -- ritim") ama yalnizca YATAY eksende.
    Uslup tedavileri gelince fark dikey eksende ortaya cikti ve toplam olcu
    bir kapiyi dusurdu: kart yuzeyini hic cizmeyen `serit` toplamda %38
    veriyordu, `sutun` %25.

    ILK DENENEN OLCU BAGLANTILI BOLGEYDI VE OLCULEREK ELENDI. Izgarada bos
    hucrelerin en buyuk BITISIK kumesi hesaplandi; sonuc neredeyse her
    slaytta TOPLAMIN AYNISI cikti (content: %45 / %45, section: %67 / %67).
    Sebebi geometrik: bir slaytta bosluk icerigin ETRAFINI dolanir, yani
    zaten tek parcadir. Olcu, yerine gecmesi gereken olcuye coktu.
    Kanit ekilmis kusurla da alindi -- sag %45'i bosaltilmis bir slaytta:

        olcu               normal (band/bullets)   ekilmis delik
        toplam bos                  %38                 %40
        baglantili bolge            %38                 %34   <- delik DAHA KUCUK
        BOS DIKDORTGEN              %11                 %29   <- 2.6 kat

    Yani ilk iki olcu ekilmis deligi GORMUYOR; ikincisi ters yone bile
    gidiyor. Ucuncusu goruyor, ve ayrica uslup degisiminden ETKILENMIYOR --
    `content` duzeninde dort uslubun dordu de %31 veriyor. Aranan ozellik
    tam olarak buydu: ayrim eksenini cezalandirmayan, deligi goren olcu.

    Izgara silhouette'inki -- ayni fonksiyon, ikinci bir uygulama degil.
    Tam genislikteki seritler ATLANIR (`FULL_WIDTH`), bu dosyanin bandla
    ayni gerekcesiyle: slaydin her yerine degen bir serit bos bir bolgeyi
    teknik olarak boler ama gozun gordugu boslugu bolmez.
    """
    import silhouette
    # `slayt` SLAYT ADI (basename), parca yolu degil -- silhouette.grid de
    # oyle aliyor.
    hucreler = silhouette.grid(pkg, slayt, en_fazla_genislik=FULL_WIDTH)
    return _delik_izgarada(hucreler, silhouette.COLS, silhouette.ROWS)


def _en_genis_dikdortgen(yukseklikler: list[int]) -> int:
    """Histogramdaki en büyük dikdörtgenin alanı (hücre)."""
    yigin: list[tuple[int, int]] = []
    en = 0
    for i, h in enumerate(yukseklikler + [0]):
        bas = i
        while yigin and yigin[-1][1] >= h:
            bas, hh = yigin.pop()
            en = max(en, hh * (i - bas))
        yigin.append((bas, h))
    return en


def _delik_izgarada(hucreler: list[float], cols: int, rows: int) -> tuple[int, int]:
    """Izgarada en büyük boş dikdörtgen ve toplam boş oran (%).

    Ayri yazildi cunku KANARYA bunu DOGRUDAN cagirabilmeli: elle kurulmus
    bir izgarayla sinanan bir olcu, kurs kurmadan sinanabilir. "Olcu kostu
    mu" sorusu o zaman dosya okumaya bagli kalmaz.
    """
    bos = [v < BOS_ESIK for v in hucreler]
    yuk = [0] * cols
    en_buyuk = 0
    for y in range(rows):
        for x in range(cols):
            yuk[x] = yuk[x] + 1 if bos[y * cols + x] else 0
        en_buyuk = max(en_buyuk, _en_genis_dikdortgen(yuk))
    n = len(bos)
    return round(en_buyuk / n * 100), round(sum(bos) / n * 100)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--story",
                        default=str(ROOT.parent / "test" / "_canary" / "variety.story"))
    parser.add_argument("--build", action="store_true",
                        help="olcmeden once variety.py ile kursu yeniden kur")
    args = parser.parse_args()

    if args.build:
        import variety
        variety.build()

    story = Path(args.story).resolve()
    if not story.is_file():
        print(f"Proje yok: {story}\n(once: python tools/variety.py)")
        return 2

    pkg = StoryPackage(story)
    groups: dict[str, list[tuple[int, int]]] = {"maddeli": [], "maddesiz": []}
    print(f"{'slayt':<26}{'sekil':>6}{'en buyuk bant':>15}{'toplam bos':>12}")
    for part, ref in model.slide_index(pkg).items():
        band, total, count = dead_band(pkg, part)
        if not count:
            continue
        # Kart tasiyan slaytlar cok daha fazla sekil koyar; ayrimi sekil
        # sayisindan degil, kartlarin varligindan okumak icin esik yeterli.
        kind = "maddeli" if count >= 8 else "maddesiz"
        groups[kind].append((band, total))
        print(f"{ref.name[:25]:<26}{count:>6}{band:>14}%{total:>11}%")

    print()
    drift = []
    for kind, seen in groups.items():
        if not seen:
            continue
        low, high = min(t for _b, t in seen), max(t for _b, t in seen)
        was_low, was_high = BASELINE[kind]
        mark = ""
        if low < was_low - 3 or high > was_high + 3:
            mark = f"  <- taban %{was_low}-%{was_high}"
            drift.append(kind)
        print(f"  {kind:<10} toplam bos %{low}-%{high}  "
              f"({len(seen)} slayt){mark}")
    if drift:
        print(f"\nTaban disina cikti: {', '.join(drift)}. Tipografi isi "
              "bittiyse BASELINE'i guncelleyin; bitmediyse bir gerileme var.")
        scope.show("deadband")
        return 1
    print("\nTabanla uyumlu.")
    scope.show("deadband")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
