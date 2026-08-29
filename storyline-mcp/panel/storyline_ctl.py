"""Drive the Storyline window so an open project can still be edited.

Storyline opens its project with no file sharing at all: the .story cannot be
read or written by anyone else while it is loaded. There is no API to ask it to
release the file, and writing behind its back would be wrong anyway -- it keeps
its own in-memory copy and would overwrite the change on its next save without
ever showing it.

So the file is not edited while open. Instead the cycle around it is automated:
save, close, edit, reopen. The user types a command and Storyline blinks;
nothing is asked of them.

Two safeguards, because this closes an application the user is working in:

  * Ctrl+S is always sent first and the save is given time to land. Worst case
    it is a no-op on an already-saved project; best case it is the difference
    between a clean close and lost work.
  * The close is a graceful WM_CLOSE, never a kill. If Storyline does not exit
    -- an unsaved-changes prompt, a modal dialog -- the wait times out and the
    whole operation is abandoned with the file untouched, rather than forced.

The window title carries the open project's filename:

    Articulate Storyline - [deneme1.story]

which is how "is this the file we are about to edit?" is answered precisely,
rather than assuming any running Storyline holds it.
"""

from __future__ import annotations

import ctypes
import re
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

from storyline_mcp.package import lock_state

user32 = ctypes.windll.user32

WM_CLOSE = 0x0010
VK_CONTROL, VK_S = 0x11, 0x53
KEYEVENTF_KEYUP = 0x0002

TITLE_RE = re.compile(r"Articulate Storyline\s*-\s*\[(?P<name>[^\]]+)\]")


def _windows() -> list[tuple[int, str]]:
    """Every visible top-level window, as (handle, title)."""
    found: list[tuple[int, str]] = []
    proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def collect(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            found.append((hwnd, buf.value))
        return True

    user32.EnumWindows(proto(collect), 0)
    return found


def storyline_window() -> tuple[int, str, bool] | None:
    """The Storyline window, the project it shows, and whether it is dirty.

    The title marks unsaved changes with a trailing asterisk:

        Articulate Storyline - [try.story]     saved
        Articulate Storyline - [try.story*]    unsaved changes

    That asterisk is worth reading rather than discarding. It is how a save can
    be confirmed to have landed before the window is closed, instead of waiting
    a fixed interval and hoping.
    """
    for hwnd, title in _windows():
        match = TITLE_RE.search(title)
        if match:
            raw = match.group("name")
            dirty = raw.endswith("*")
            return hwnd, raw.rstrip("*").strip(), dirty
    return None


def open_project() -> str | None:
    window = storyline_window()
    return window[1] if window else None


def is_dirty() -> bool:
    window = storyline_window()
    return bool(window and window[2])


def holds(path: str | Path) -> bool:
    """Is this exact file the one Storyline currently has open?"""
    target = Path(path)
    if lock_state(target) == "free":
        return False
    name = open_project()
    return bool(name) and name.casefold() == target.name.casefold()


kernel32 = ctypes.windll.kernel32


def focus(hwnd: int, *, timeout: float = 3.0) -> bool:
    """Pencereyi gerçekten öne al. Alamazsan FALSE dön -- tuş gönderme.

    SetForegroundWindow TEK BASINA YETMEZ ve bu olculdu: cagrildiktan sonra
    GetForegroundWindow hala Chrome'u gosteriyordu. Windows, arka plandaki bir
    islemin one gecmesini engelliyor (foreground lock), ve cagri sessizce
    basarisiz oluyor -- donus degeri kontrol edilmezse hicbir sey belli olmaz.

    Sonucu iki yonlu tehlikeliydi:
      * Storyline'a gitmesi gereken Ctrl+S gitmiyordu, yani save_and_close'un
        "once kaydet" guvencesi o durumda hic calismiyordu.
      * Tuslar KAYBOLMUYOR, ONDEKI UYGULAMAYA gidiyordu. Kullanicinin
        tarayicisina Ctrl+A ve ok tuslari gonderildi.

    Cozum, on plandaki pencerenin girdi kuyruguna baglanmak (AttachThreadInput):
    ayni kuyrugu paylasan bir islem icin kilit uygulanmaz.

    Ve fonksiyon DOGRULAYARAK doner: SetForegroundWindow'un donus degerine
    degil, GetForegroundWindow'un gercekten bu pencereyi gostermesine bakar.
    """
    onceki = user32.GetForegroundWindow()
    if onceki == hwnd:
        return True
    bizim = kernel32.GetCurrentThreadId()
    onun = user32.GetWindowThreadProcessId(onceki, None)
    bagli = bool(user32.AttachThreadInput(bizim, onun, True)) if onun else False
    try:
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
        son = time.time() + timeout
        while time.time() < son:
            if user32.GetForegroundWindow() == hwnd:
                return True
            time.sleep(0.1)
    finally:
        if bagli:
            user32.AttachThreadInput(bizim, onun, False)
    return user32.GetForegroundWindow() == hwnd


def _send_save(hwnd: int) -> bool:
    # ODAK ALINMADAN TUS GONDERILMEZ. Once kosulsuzca gonderiliyordu ve odak
    # alinamadiginda tuslar kullanicinin onundeki uygulamaya gidiyordu.
    if not focus(hwnd):
        return False
    time.sleep(0.4)
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_S, 0, 0, 0)
    user32.keybd_event(VK_S, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
    return True


VK_CTRL_A, VK_LEFT, VK_RIGHT, VK_D = 0x41, 0x25, 0x27, 0x44
SW_MAXIMIZE = 3
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004


def make_dirty(*, settle: float = 1.5) -> dict:
    """Belgeyi kirlet, ki Storyline bir sonraki Ctrl+S'te gerçekten yazsın.

    NEDEN GEREKLI. Kalibrasyon deneyi bir kez yapildi ve GECERSIZDI: dosya
    acildi, save_and_close cagrildi, hicbir bayt degismedi ve sonuc "Storyline
    yeniden boyutlandirmiyor" diye okundu. Oysa save_and_close Ctrl+S'i
    yalnizca baslik KIRLI gosteriyorsa gonderir, ve bir dosyayi acmak onu
    kirletmez -- yani Storyline hic yazmadi. Deney, olcmeyi amacladigi seyi
    hic olcmedi; sifir fark "iz yok"un degil "yazma yok"un sonucuydu.

    Kirletme yontemi: hepsini sec + bir birim oynat + geri oynat. Konum geri
    gelir ama undo yigini dolar, yani belge kirli kalir. KALIBRASYON YUKSEKLIK
    olcer, konum degil -- yani bu dokunus, olculen buyuklugu ilkece de
    etkilemez.

    Ctrl+Z KULLANILMIYOR: undo bazi uygulamalarda kirli bayragini da geri
    alir ve o zaman kirletme sessizce basarisiz olur. Ters yone oynatmak,
    ayni gorsel sonucu kirliligi koruyarak verir.
    """
    window = storyline_window()
    if window is None:
        return {"dirty": False, "reason": "Storyline penceresi bulunamadi."}
    hwnd, name, already = window
    if already:
        return {"dirty": True, "project": name, "how": "zaten kirliydi"}

    # ONE ALMADAN ONCE MAXIMIZE. Bu adim eksikti ve kirletme sessizce
    # basarisiz oluyordu: focus() FALSE donuyor, tus gonderilmiyor, cagiran
    # "Storyline yazmadi" goruyordu. shoot._front ayni isi maximize ile
    # yapiyor ve calisiyor. DURUST NOT: duzeltme sirasinda hem maximize
    # eklendi hem de acilis beklemesi uzatildi; hangisinin belirleyici
    # oldugu AYRILMADI -- ikisi birlikte calisti.
    user32.ShowWindow(hwnd, SW_MAXIMIZE)
    if not focus(hwnd):
        return {"dirty": False, "project": name,
                "reason": "pencere one alinamadi (foreground lock); tus "
                          "GONDERILMEDI -- gonderilseydi kullanicinin "
                          "onundeki uygulamaya giderdi"}
    time.sleep(0.4)
    for keys in ((VK_CONTROL, VK_CTRL_A), (VK_RIGHT,), (VK_LEFT,)):
        for key in keys:
            user32.keybd_event(key, 0, 0, 0)
        for key in reversed(keys):
            user32.keybd_event(key, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.3)
    time.sleep(settle)

    window = storyline_window()
    if window and window[2]:
        return {"dirty": True, "project": name, "how": "sec + oynat + geri oynat"}

    # TUVAL YOLU CALISMADI. Sebep olculdu: Storyline dosyayi STORY VIEW'da
    # aciyor (shoot.py'de de yazili) ve orada Ctrl+A hicbir sey secmiyor --
    # kare alindi, "Duplicate" butonu gri kaldi. Ok tuslari sekil tasimiyor,
    # sadece secimi geziyor, yani undo yigini dolmuyor.
    #
    # Slayda gecmek KAPALI: "klavyeyle acmak denendi (Tab/Home/Enter, odak
    # DOGRULANMIS halde) ve calismadi" (shoot.py). O yuzden Story View'in
    # kendi islemi kullaniliyor: slayt kartina TIKLA, sonra Ctrl+D.
    #
    # YAN ETKISI VAR ve cagiran bilmeli: bu yol bir slayt COGALTIR. Tuval
    # yolu belgeyi degistirmeden kirletiyordu; bu yol degistiriyor. Bedeli
    # kabul edilmesinin sebebi, alternatifin "hic olcememek" olmasi.
    box = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(box))
    # Kart merkezinin orani tek bir pencerede olculdu (1920x1020'de 737,376).
    # Sahne sayisi ya da yerlesim degisirse tutmaz; tutmazsa BASARISIZ doner,
    # ikinci bir noktaya korlemesine tiklamaz.
    x = box.left + int((box.right - box.left) * 0.384)
    y = box.top + int((box.bottom - box.top) * 0.369)
    user32.SetCursorPos(x, y)
    time.sleep(0.3)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.08)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(0.8)

    for key in (VK_CONTROL, VK_D):
        user32.keybd_event(key, 0, 0, 0)
    for key in (VK_D, VK_CONTROL):
        user32.keybd_event(key, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(settle + 1.0)

    window = storyline_window()
    dirty = bool(window and window[2])
    return {"dirty": dirty, "project": name,
            "how": "story view: karta tikla + Ctrl+D" if dirty else "",
            "yan_etki": "bir slayt cogaltildi" if dirty else "",
            "reason": "" if dirty else
                      ("Ne tuval ne story view yolu kirletebildi. Tuslar "
                       "pencereye gidiyor (odak dogrulandi) ama undo yigini "
                       "dolmadi; slayt karti beklenen yerde olmayabilir.")}


def save_and_close(path: str | Path, *, timeout: float = 45.0,
                   save_timeout: float = 25.0) -> dict:
    """Save the open project and close Storyline, so the file becomes free."""
    window = storyline_window()
    if window is None:
        return {"closed": False, "reason": "Storyline penceresi bulunamadi."}
    hwnd, name, dirty = window

    if dirty:
        if not _send_save(hwnd):
            return {"closed": False, "project": name,
                    "reason": ("Pencere one alinamadi, Ctrl+S "
                               "gonderilmedi. Kaydedilmemis degisiklik "
                               "var; dosyaya dokunulmadi.")}
        # Wait for the title's asterisk to clear rather than sleeping blindly:
        # closing while changes are still unsaved is how work gets lost.
        deadline = time.time() + save_timeout
        while time.time() < deadline and is_dirty():
            time.sleep(0.5)
        if is_dirty():
            return {
                "closed": False,
                "project": name,
                "reason": ("Kaydedilmemis degisiklikler kaydedilemedi; dosyaya "
                           "dokunulmadi. Storyline'da bir iletisim kutusu acik "
                           "olabilir."),
            }
    time.sleep(1.0)

    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)

    deadline = time.time() + timeout
    while time.time() < deadline:
        if lock_state(path) == "free" and storyline_window() is None:
            return {"closed": True, "project": name}
        time.sleep(0.5)

    return {
        "closed": False,
        "project": name,
        "reason": (
            "Storyline kapanmadi. Kaydedilmemis degisiklik uyarisi veya baska bir "
            "iletisim kutusu aciksa once onu yanitlayin; dosyaya dokunulmadi."
        ),
    }


def _storyline_exe() -> str | None:
    """`open_test.storyline_exe()` -- TEK yerde hesaplanir, burada kopyalanmaz.

    Exe'nin nerede oldugu ve nasil bulundugu (once .story kayit defteri
    iliskisi, sonra Program Files taramasi) `tools/open_test.py`'de yazili ve
    gerekcesi de orada. Ikinci bir uygulama zamanla ayrisirdi.
    """
    kok = Path(__file__).resolve().parent.parent / "tools"
    if str(kok) not in sys.path:
        sys.path.insert(0, str(kok))
    try:
        import open_test
        return open_test.storyline_exe()
    except Exception:
        return None


def reopen(path: str | Path, *, wait: float = 40.0) -> bool:
    """Open the project again and wait until Storyline has really taken it.

    SHELL YOLU KULLANILMAZ -- olculmus bir tuzak. `cmd /c start` dosyayi
    .story iliskisini tutan sey her neyse ONA verir; Articulate 360 masaustu
    uygulamasi calisirken bu, "dosya baska bir islem tarafindan kullaniliyor"
    ile geri donuyor ve hicbir pencere acilmiyor.

    Bu ders `open_test.storyline_exe`'de yaziliydi ve `js_probe._ac` onu
    tekrar edip "storyline_ctl.reopen HALA shell yolunu kullaniyor; panel de
    ayni tuzaga acik" diye NOT DUSMUSTU. Not dusmek duzeltmek degil: kayit
    bir eylemi engellemiyordu (bu turda ucuncu kez ayni bicim). Ayni gun
    `event_probe` de ayni yuzden yanlis olcum uretti.

    Exe bulunamazsa shell yoluna dusulur -- hic denememekten iyidir, ama
    o durumda bu tuzak yeniden acilir.
    """
    exe = _storyline_exe()
    if exe:
        subprocess.Popen([exe, str(path)])
    else:
        subprocess.Popen(["cmd", "/c", "start", "", str(path)], shell=False)
    deadline = time.time() + wait
    while time.time() < deadline:
        if holds(path):
            return True
        time.sleep(1.0)
    return False
