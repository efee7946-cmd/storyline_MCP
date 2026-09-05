"""Storyline'in "duzgun kapanmamis oturum" izini temizler.

NEDEN VAR (olculdu 2026-09-05). Bir kare turu iki diyalogla tukendi:

    'Articulate Storyline'                 -> kurtarma teklifi
    'Articulate Storyline Error Report'    -> cokus raporu

Ikisi de olculecek kutularin ustunde duruyordu. Storyline'i kapatip yeniden
acmak YETMEDI -- diyaloglar geri geldi, yani bunlar onceki oturumun canli
pencereleri degil, SAKLANMIS durum. Sebebi Storyline kendi gunlugune yaziyor:

    "Last session did NOT close properly."   (Storyline_STABLE_824.log)

Iz, DUZGUN bir kapanisla siliniyor. Bu arac tam olarak onu yapar: Storyline'i
dosyasiz acar, cikan diyaloglari WM_CLOSE ile kapatir, sonra ana pencereyi
yine WM_CLOSE ile kapatip GITTIGINI dogrular.

WM_CLOSE, TIKLAMA DEGIL -- ve fark onemli. Kurtarma teklifinin YES/NO'su var;
WM_CLOSE'un anlami "iptal", yani NO tarafi. Hicbir sey kurtarilmaz, hicbir sey
silinmez, kullanicinin dosyasina dokunulmaz. Buton koordinati aramak ise
diyalog duzeni degisince yanlis butona basardi.

OLCULEN DOSYA HAKKINDA HICBIR SEY SOYLEMEZ. Iz, o turda acilan dosyanin adini
tasir ("...problem in 'ORTU'") ve bu, dosyayi bozuk sanmaya yol acti; oysa ayni
dosyanin kendi acilis gunlugunde tek istisna yoktu ve yapisal sonda temizdi.

    python tools/oturum_temizle.py
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "panel"))
sys.path.insert(0, str(ROOT / "tools"))

import open_test
import storyline_ctl as ctl

user32 = ctypes.windll.user32
WM_CLOSE = 0x0010


def _storyline_pencereleri() -> list[tuple[int, str]]:
    """Storyline surecine ait GORUNUR pencereler, ustten alta.

    PID->ad tek seferde cikariliyor; her pencere icin `tasklist` cagirmak
    onlarca surec baslatirdi ve dongu saniyede bir donuyor.
    """
    try:
        satirlar = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Storyline.exe", "/NH", "/FO", "CSV"],
            capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return []
    pidler = set()
    for satir in satirlar.splitlines():
        parca = [p.strip('"') for p in satir.split('","')]
        if len(parca) > 1 and parca[1].isdigit():
            pidler.add(int(parca[1]))
    if not pidler:
        return []
    out = []
    for hwnd, baslik in ctl._windows():
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pidler:
            out.append((hwnd, baslik))
    return out


def _sinif(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def _surec_var() -> bool:
    try:
        cikti = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Storyline.exe", "/NH"],
            capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return True          # bilmiyorsak "gitti" DEMEYIZ
    return "storyline.exe" in cikti.lower()


def temizle(*, bekle: float = 90.0) -> int:
    """Bir DUZGUN acilis-kapanis turu; izi silen sey duzgun kapanistir.

    AYRIM SINIFTAN, BASLIKTAN DEGIL -- ve bu iki turluk bir duzeltme.

    Ilk surum dosyasiz acti ve ana pencereyi hic goremedi: `storyline_window()`
    basligi `Articulate Storyline - [ad]` kalibiyla arar, dosyasiz acilista
    `[ad]` yoktur. Ikinci surum bilinen-iyi bir fikstuurle acti ve yine
    dustu, cunku kurtarma teklifi IPTAL edilince Storyline belgeyi kapatiyor,
    baslik `[ad]`i kaybediyor ve ayni kalip yine tutmuyor. Ustelik teklifin
    baslik cubugu da "Articulate Storyline" yaziyor -- yani baslik, diyalogla
    ana pencereyi AYIRT EDEMIYOR.

    Windows'un ortak diyalog sinifi `#32770`; ana pencere kendi sinifindadir.
    Kapanis ise SUREC uzerinden dogrulaniyor: baslik kaybolmasi "kapandi"
    demek degil, "belge kapandi" demek olabilir.
    """
    fikstur = ROOT.parent / "test" / "bos.story"
    if not fikstur.is_file():
        print("Fikstur yok: %s" % fikstur)
        return 2

    if _surec_var():
        print("Storyline zaten acik; once kapatiliyor.")
        open_test.force_close()

    exe = open_test.storyline_exe()
    if not exe:
        print("Storyline bulunamadi.")
        return 2
    subprocess.Popen([str(exe), str(fikstur)])

    son = time.time() + bekle
    kapatilan: list[str] = []
    ana = None
    sakin = 0
    while time.time() < son:
        time.sleep(2.0)
        pencereler = _storyline_pencereleri()
        if not pencereler:
            continue
        diyaloglar = [(h, b) for h, b in pencereler if _sinif(h) == "#32770"]
        analar = [(h, b) for h, b in pencereler if _sinif(h) != "#32770"]
        if analar:
            ana = analar[-1][0]      # en alttaki: ana cerceve
        for h, b in diyaloglar:
            user32.PostMessageW(h, WM_CLOSE, 0, 0)
            kapatilan.append(b)
            print("  diyalog kapatildi: %r" % b)
        if ana is not None and not diyaloglar:
            sakin += 1
            if sakin >= 3:           # ust uste sakin: yeni diyalog gelmiyor
                break
        else:
            sakin = 0

    if ana is None:
        print("Ana pencere hic gorunmedi -- iz temizlenmis SAYILMAZ.")
        return 1

    user32.PostMessageW(ana, WM_CLOSE, 0, 0)
    son = time.time() + 60
    while time.time() < son:
        time.sleep(1.5)
        # Kapanirken "kaydet?" cikarsa onu da iptal et.
        for h, b in _storyline_pencereleri():
            if _sinif(h) == "#32770":
                user32.PostMessageW(h, WM_CLOSE, 0, 0)
        if not _surec_var():
            print("Storyline DUZGUN kapandi; iz temizlendi "
                  "(kapatilan diyalog: %d)." % len(kapatilan))
            return 0

    print("Kapanis dogrulanamadi -- iz DURUYOR olabilir.")
    return 1


if __name__ == "__main__":
    raise SystemExit(temizle())
