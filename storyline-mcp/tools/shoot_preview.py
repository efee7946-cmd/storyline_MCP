"""Storyline PREVIEW penceresinin karesi -- editör penceresinin değil.

NEDEN AYRI BIR ARAC. `shoot.py` Storyline'in EDITOR penceresini yakaliyor.
Bu projedeki butun kalibrasyon olcumleri PREVIEW'de yapildi (kirpma testi,
CHAR_WIDTH_RATIO, MEASURE_LEADING, 2026-08-17 kare turu) ve editor tuvalini
onun yerine koymak, dogrulanmamis bir ikame olurdu: editor secim tutamaklari,
kilavuzlar ve kendi olcegiyle cizer, oynatici cizmez.

UC GUARD, ucu de gecmis turlarin dersi:

  1. ODAK ALINMADAN TUS GONDERILMEZ. `focus()` AttachThreadInput ile alir ve
     ALDIGINI DOGRULAR; alamazsa F12 kullanicinin onundeki uygulamaya giderdi.
  2. PENCERE DOGRULANMADAN KARE ALINMAZ. ImageGrab EKRANI yakalar; onde
     baska bir sey varsa dosya yine uretilir ve "Preview'in cizimi" diye
     bakilan sey Chrome olur. Olculdu: bir kez VS Code kaydedildi.
  3. YAKALAMA ANINDA YENIDEN DOGRULANIR. "O an dogruydu" ile "yakalama
     aninda dogru" ayni sey degil -- settle beklemesi sirasinda odak
     kayabiliyor.

PREVIEW AYRI PENCERE DEGIL -- OLCULDU (2026-08-17). Bu aracin ilk surumu
F12'den once ve sonra acik pencereleri sayip FARK aliyordu ve 90 saniye
bekleyip "Preview acilmadi" dedi. Yanlisti: Storyline onizlemeyi AYNI
pencerede acar, yalnizca BASLIK degisir:

    Articulate Storyline - [SAHNE720.story]              duzenleme
    Articulate Storyline - [SAHNE720.story (Preview)]    onizleme

Guard dogru davrandi -- editor karesini "Preview" diye kaydetmektense hic
kaydetmedi. Yanlis olan varsayimdi, ve varsayim "yeni mod = yeni pencere"
idi. Ayni sinif: gorunmedigini yokluk sanmak.

Sinyal artik BASLIKTAN okunuyor ve `storyline_ctl.storyline_window()` onu
zaten ayristiriyor; ayri bir ad listesi tutulmuyor (K15).

BILINEN SINIR -- BU ARAC SU AN OLCUM VEREMIYOR (2026-08-17). Guard'lar
saglam, ama tur TUKENIYOR:

    `open_test.force_close()` Storyline'i OLDURUYOR. Bir sonraki acilista
    Storyline oldurulen oturumun cokus raporunu gosteriyor -- yani otomasyon
    KENDI COP IZINI olcuyor.

Kanit iki kosudan: SAHNE720/SAHNE1920'de onizleme moduna GECILDI ve kare
cokus diyaloguydu; ayni otomasyondan gecen BILINEN-CALISAN B1_KARE.story'de
ise F12 hic tutmadi (baslik 'B1_KARE.story' olarak kaldi). Iki farkli
basarisizlik, tek ortak sebep: fikstuur degil, ACIS YORDAMI. B1_KARE elle
acildiginda sorunsuz onizleniyor.

BU GUARD'LA YAKALANAMAZ, ve fark onemli: cokus raporu GERCEK bir Storyline
penceresidir, basligi gercekten "(Preview)" olur. Imza rengi guard'i onu
reddeder -- yani YANLIS OLCUM uretilmez -- ama tur yine bos doner.

Duzeltilecek yer force_close sonrasi TEMIZLIK: oldurulen oturumun kurtarma/
rapor durumu silinmeden her otomatik tur bir oncekinin izini olcme riski
tasir. O yapilana kadar kareler ELLE alinmali.

    python tools/shoot_preview.py <proje.story> -o kare.png --imza RRGGBB
"""

from __future__ import annotations

import argparse
import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "panel"))
sys.path.insert(0, str(ROOT / "tools"))

import open_test
import storyline_ctl as ctl

user32 = ctypes.windll.user32
SW_MAXIMIZE = 3
VK_F12 = 0x7B
KEYEVENTF_KEYUP = 0x0002
# Onizleme modunun basliktaki izi. Storyline'in kendi yazdigi sonek; bir ad
# LISTESI degil, tek bir ize bakiliyor ve gorulmezse kare uretilmiyor.
PREVIEW_IZI = "(preview)"



def _pencereler() -> dict[int, str]:
    return dict(ctl._windows())


def _rect(hwnd: int) -> tuple[int, int, int, int]:
    box = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(box))
    return box.left, box.top, box.right, box.bottom


def _f12(hwnd: int, *, deneme: int = 5, ara: float = 2.0) -> bool:
    """Preview'i tetikle -- odak DOĞRULANDIKTAN sonra, ve PES ETMEDEN.

    TEK DENEME YETMIYOR -- ölçüldü (2026-08-23). `ctl.focus` üç ardışık
    çağrıda düştü ve tur "foreground lock" diyerek terk edildi; dördüncüde
    hiçbir şey değişmeden ALDI. Yani engel kalıcı değil, YARIŞ: Storyline
    açılışın hemen ardından ön planı kendisi oynatıyor ve o anda başka bir
    pencere (bu makinede görünmez bir `GameInputServiceWindow`) araya
    giriyor.

    Aralıklı bir hata, tek denemede kalıcı bir blok gibi görünür. Bu, ölçümü
    yapmayı engellemekle kalmadı -- yanlış bir TEŞHİSE de yol açtı ("focus
    servis penceresine attach edemiyor"), ve o teşhis `ctl.focus`'a
    dokunmayı önerecekti. Doğru olan çareyi yazmadan önce mevcut yolu taban
    çizgisi olarak tekrar tekrar koşturmaktı.

    Dönüş değeri hâlâ DOĞRULANMIŞ: `ctl.focus` odağı aldığını kendisi
    doğruluyor, biz yalnızca ona birden çok şans veriyoruz.
    """
    for i in range(deneme):
        if ctl.focus(hwnd):
            time.sleep(0.5)
            user32.keybd_event(VK_F12, 0, 0, 0)
            user32.keybd_event(VK_F12, 0, KEYEVENTF_KEYUP, 0)
            return True
        if i + 1 < deneme:
            print(f"   odak alinamadi ({i + 1}/{deneme}), {ara:.0f} sn sonra "
                  f"tekrar...")
            time.sleep(ara)
    return False


def _renk_orani(im, hedef: tuple[int, int, int], tol: int = 6) -> float:
    """Karenin ne kadarı bu renk? (0..1)"""
    px = im.convert("RGB").load()
    w, h = im.size
    # Her pikseli taramak gerekmiyor: 4'er atlayarak orani kestirmek yeterli
    # ve on kat hizli. Esik %1 mertebesinde oldugu icin ornekleme guvenli.
    say = top = 0
    for y in range(0, h, 4):
        for x in range(0, w, 4):
            r, g, b = px[x, y]
            top += 1
            if (abs(r - hedef[0]) <= tol and abs(g - hedef[1]) <= tol
                    and abs(b - hedef[2]) <= tol):
                say += 1
    return say / max(top, 1)


def preview_karesi(out: Path, *, bekle: float = 90.0, settle: float = 6.0,
                   imza: tuple[int, int, int] | None = None,
                   en_az: float = 0.05, icerik_bekle: float = 60.0) -> Path:
    from PIL import ImageGrab

    bulunan = ctl.storyline_window()
    if not bulunan:
        raise SystemExit("Storyline penceresi bulunamadi.")
    hwnd = bulunan[0]
    user32.ShowWindow(hwnd, SW_MAXIMIZE)

    if not _f12(hwnd):
        raise SystemExit(
            "Storyline one alinamadi (foreground lock); F12 GONDERILMEDI.\n"
            "Gonderilseydi one plandaki baska uygulamaya giderdi.")

    # ONIZLEME MODU BASLIKTAN OKUNUR, ve acilmasi BEKLENIR -- sabit bir
    # uyku degil. "Bekledim, herhalde acildi" bu projede bir kez yanlis
    # cikti; burada mod GORULMEDEN kare uretilmez.
    son = time.time() + bekle
    yeni = None
    while time.time() < son:
        time.sleep(1.0)
        bulunan = ctl.storyline_window()
        if bulunan and PREVIEW_IZI in (bulunan[1] or "").casefold():
            yeni = bulunan[0]
            break
    if yeni is None:
        simdi = ctl.storyline_window()
        raise SystemExit(
            f"{bekle:.0f} sn icinde onizleme moduna gecilmedi; kare "
            f"ALINMADI.\nSon baslik: {simdi[1] if simdi else 'pencere yok'!r}\n"
            f"Alinsaydi DUZENLEME penceresini kaydederdi ve bu projedeki "
            f"butun kalibrasyon Preview'de yapildi.")

    if not ctl.focus(yeni):
        raise SystemExit("Onizleme penceresi one alinamadi; kare ALINMADI.")

    # SABIT BEKLEME DEGIL, ICERIK BEKLENIR (2026-08-18).
    #
    # `settle` sabitti (6 sn) ve yetmiyordu: onizleme moduna gecilmis ama
    # oynatici HENUZ YAYINLAMAMIS oluyordu; kare, yukleme zeminini
    # kaydediyordu (olculdu -- acik mavi bos alan). Sabit uyku, olculecek
    # seyin hazir oldugunu VARSAYAR.
    #
    # Artik olculecek seyin KENDISI sinyal: fikstuurun imza rengi karede
    # gorunene kadar beklenir. Imza verilmemisse eski sabit bekleme kalir,
    # cunku o durumda beklenecek bir isaret yok.
    time.sleep(min(settle, 2.0))
    if imza:
        son = time.time() + icerik_bekle
        while time.time() < son:
            kare = ImageGrab.grab(bbox=_rect(yeni), all_screens=True)
            if _renk_orani(kare, imza) >= en_az:
                break
            time.sleep(1.0)
    else:
        time.sleep(max(settle - 2.0, 0))

    # YAKALAMA ANINDA YENIDEN DOGRULA -- hem odak hem MOD. Onizleme
    # kapanmis olabilir (Esc, yayin hatasi); o zaman baslik geri doner ve
    # kare sessizce editoru kaydederdi.
    if user32.GetForegroundWindow() != yeni and not ctl.focus(yeni):
        raise SystemExit(
            "Yakalama aninda onizleme on planda degildi; kare ALINMADI.")
    son_kontrol = ctl.storyline_window()
    if not son_kontrol or PREVIEW_IZI not in (son_kontrol[1] or "").casefold():
        raise SystemExit(
            "Yakalama aninda onizleme modu kapanmisti; kare ALINMADI.")
    kare = ImageGrab.grab(bbox=_rect(yeni), all_screens=True)

    # DORDUNCU GUARD: KARE, OLCULECEK SEYI ICERIYOR MU (2026-08-17).
    #
    # Ilk uc guard ETIKETI dogruluyordu: odak alindi mi, baslik "(Preview)"
    # mi, yakalama aninda onde mi. Ucu de GECTI ve kare Storyline'in COKME
    # DIYALOGUYDU ("We're sorry, something went wrong"). Baslik onizleme
    # modunu soyluyordu, icerik hata raporuydu.
    #
    # Bu, bu projenin tekrar eden hatasi: gostergeyi dogrulayip gondergeyi
    # dogrulamamak. `negative-result-must-prove-it-ran`in yakalama tarafi --
    # "kare uretildi" ile "olculecek sey karede" ayni sey degil.
    #
    # Cozum fikstuurle BIRLIKTE tasarlaniyor: fikstuur zeminine ayirt edici
    # bir renk koyar, kare o rengi ARAMAK zorundadir. Renk yoksa slayt
    # cizilmemistir ve dosya YAZILMAZ -- yazilsaydi adi bir yalan olurdu.
    if imza:
        oran = _renk_orani(kare, imza)
        if oran < en_az:
            raise SystemExit(
                f"Kare olculecek slaydi ICERMIYOR: fikstuur imza rengi "
                f"#{imza[0]:02X}{imza[1]:02X}{imza[2]:02X} karenin "
                f"%{oran * 100:.2f}'sini kapliyor, en az %{en_az * 100:.1f} "
                f"bekleniyordu.\nDosya YAZILMADI. Ekranda muhtemelen "
                f"Storyline'in hata diyalogu ya da bos oynatici var; "
                f"baslik 'Preview' dese bile icerik slayt degil.")

    out.parent.mkdir(parents=True, exist_ok=True)
    kare.save(out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("story")
    ap.add_argument("-o", "--out", default="preview.png")
    ap.add_argument("--wait", type=float, default=45.0,
                    help="projenin acilmasi icin")
    ap.add_argument("--preview-wait", type=float, default=90.0)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--imza", help="fikstuur zemin rengi, RRGGBB — kare bunu "
                                   "ICERMIYORSA dosya yazilmaz")
    ap.add_argument("--en-az", type=float, default=5.0,
                    help="imza renginin karede kaplamasi gereken en az yuzde")
    args = ap.parse_args()

    story = Path(args.story).resolve()
    if not story.is_file():
        print(f"Proje yok: {story}")
        return 2

    open_test.force_close()
    open_test.launch(story)
    son = time.time() + args.wait
    while time.time() < son:
        bulunan = ctl.storyline_window()
        if bulunan and story.name.lower() in (bulunan[1] or "").lower():
            break
        time.sleep(1.0)
    else:
        open_test.force_close()
        print(f"{story.name} {args.wait:.0f} sn icinde acilmadi.")
        return 1

    try:
        imza = None
        if not args.imza:
            # DORDUNCU GUARD SILAHLANDIRILMADI. Bu turda tam olarak bunun
            # yuzunden bos bir oynatici karesi "olcum" diye kaydedildi:
            # baslik "(Preview)" diyordu, slayt henuz cizilmemisti, ve kare
            # yazildi. Guard istege bagli olmaya devam ediyor (imza rengi
            # olmayan fikstuurler var) ama artik SESSIZ degil.
            print("UYARI: --imza verilmedi. Kare, slaydin cizilip "
                  "cizilmedigi DOGRULANMADAN yazilacak;")
            print("       bos oynatici ya da hata diyalogu 'olcum' diye "
                  "kaydedilebilir.")
            print("       Fikstuure bir zemin rengi verip --imza RRGGBB "
                  "gecmek bunu kapatir.")
        if args.imza:
            h = args.imza.lstrip("#")
            imza = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        yol = preview_karesi(Path(args.out).resolve(),
                             bekle=args.preview_wait,
                             imza=imza, en_az=args.en_az / 100.0)
    finally:
        if not args.keep:
            open_test.force_close()
    print(f"kare: {yol}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
