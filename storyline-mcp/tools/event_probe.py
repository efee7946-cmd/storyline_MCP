"""Bir event adini Storyline'in kendisine sordur: kabul mu, cokme mi.

NEDEN BU ARAC VAR. `logic.EVENTS` elle yazilmis bir beyaz listeydi ve
kapsamiyla gercek kume sessizce ayrismisti (K15). Olculdu (2026-08-23):

  * iki degeri Storyline'i COKERTIYORDU -- `OnSlideEnd`, `OnPrevButtonClick`.
    Arac onlari GECERLI sayip yaziyordu; uretilen dosya aciliyor, sonra
    Storyline "Error Report" ile dusuyordu.
  * donorlerde 105 kez gecen uc olay listede YOKTU ve REDDEDILIYORDU:
    OnDialTurns (77), OnDrop (23), OnStateChange (5).
  * JS koprusunun dayandigi `OnVariableValueChange` da listede yoktu.

IKI SEY KANIT DEGIL, ikisi de olculdu:

  Kalip benzerligi.  `OnNextButtonClick` calisiyor; ayni kaliptaki
                     OnSubmitButtonClick / OnFinishButtonClick /
                     OnFirstButtonClick / OnLastButtonClick DORDU DE cokuyor.
  DLL'de gecmek.     `OnPrevButtonClick` DLL'de duruyor ve cokertiyor.
                     Oradaki adlar C# olay adlari; XML degerleri degil.
                     `ObjectLosesFocus` de oyle -- XML karsiligi OnLostFocus.

OLCU: dosya acilir, tetikleyici paneli dolacak sekilde slayt secilir ve
"Articulate Storyline Error Report" penceresi cikti mi diye bakilir. Cokme
dosyayi ACILMAZ YAPMIYOR -- aciyor, sonra dusuyor; o yuzden "acildi mi"
sorusu bu kusuru GORMEZ.

KANARYA her kosuda birlikte kosar ve iki yonludur (K2):

    OnClick        bilinen gecerli -> COKMEMELI
    zzzNotAnEvent  bilinen sacma   -> COKMELI

Ikisi de beklendigi gibi davranmazsa tespit mekanizmasi calismiyordur ve
aday sonuclari OKUNAMAZ; verdikt basilmaz.

    python tools/event_probe.py OnDialTurns OnDrop
    python tools/event_probe.py --dogrula     # EVENTS + COKERTEN regresyonu

`--dogrula` her ad icin bir Storyline turu acar; liste uzunsa uzun surer.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from ctypes import wintypes
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "panel"))
sys.path.insert(0, str(HERE))

import open_test  # noqa: E402
import storyline_ctl as sc  # noqa: E402
from storyline_mcp import logic, shapes  # noqa: E402
from storyline_mcp.package import StoryPackage  # noqa: E402

user32 = ctypes.windll.user32
user32.SetProcessDPIAware()

TEMEL = ROOT / "test" / "_canary" / "canary_saglam.story"
OUT = ROOT / "test" / "_js" / "ev"

KANARYA_ARTI = "OnClick"
KANARYA_EKSI = "zzzNotAnEvent"

# Story View'da slayt kartinin merkezi, tek bir pencerede olculdu.
KART_ORAN = (0.384, 0.369)


def _pencere_basliklari() -> list[str]:
    out: list[str] = []
    proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                out.append(buf.value)
        return True

    user32.EnumWindows(proto(cb), 0)
    return out


def cokme_var() -> bool:
    return any("Error Report" in t for t in _pencere_basliklari())


def _dosya(event: str) -> Path:
    """Tek trigger, tek degisken: EVENT. action sabit `executeJavaScript`."""
    OUT.mkdir(parents=True, exist_ok=True)
    hedef = OUT / f"{event}.story"
    shutil.copy2(TEMEL, hedef)
    pkg = StoryPackage(hedef)
    part = pkg.slide_parts[0]
    root = pkg.parse(part)
    trig_list = root.find("trigLst")
    if trig_list is None:
        trig_list = shapes.insert_in_order(root, ET.Element("trigLst"))
    trig = logic._blank_trigger()
    trig.set("name", "EV")
    data = trig.find("data")
    data.set("event", event)
    data.set("action", "executeJavaScript")
    data.set("actSubType", "spec")
    data.find("other").set("js", "var p = GetPlayer();")
    trig_list.append(trig)
    pkg.replace_xml(part, root)
    pkg.save(hedef, backup=False)
    return hedef.resolve()


def sor(event: str, *, bekle: float = 90.0, deneme: int = 3) -> str:
    """'saglam' | 'COKTU' | 'ACILMADI'.

    ACILIS SHELL ILE DEGIL, EXE ILE. `os.startfile` kullaniliyordu ve bu
    olculmus bir tuzak: Articulate 360 Desktop App calisirken shell yolu
    dosyayi ONA veriyor, hicbir Storyline penceresi acilmiyor, ve her aday
    "ACILMADI" gorunuyor. Ders `js_probe._ac`'de yaziliydi ama KOMSU DOSYAYA
    TASINMAMISTI -- kanaryanin dusmesi (bilinen gecerli OnClick "ACILMADI"
    dedi) bunu ele verdi.

    VE TEK DENEME YETMIYOR: acilis aralikli olarak dusuyor (on plan yarisi).
    Aralikli bir hata tek denemede kalici bir blok gibi gorunur ve bu turda
    bir kez yanlis teshise yol acti. Deneme sayisi, carenin kendisi degil,
    mevcut yolun taban cizgisi.
    """
    hedef = _dosya(event)
    for tur in range(deneme):
        open_test.launch(hedef)
        son = time.time() + bekle
        while time.time() < son and not sc.holds(hedef):
            if cokme_var():
                break
            time.sleep(1.0)
        if sc.holds(hedef) or cokme_var():
            break
        open_test.force_close()
        if tur + 1 < deneme:
            print(f"   {event}: acilmadi ({tur + 1}/{deneme}), tekrar...")
            time.sleep(3.0)
    if not sc.holds(hedef) and not cokme_var():
        open_test.force_close()
        return "ACILMADI"
    time.sleep(5)

    # Cokme, tetikleyici paneli DOLDURULURKEN oluyor. Slayt secilmezse panel
    # bos kalir ve cokme hic tetiklenmez -- yani "acildi" cevabi kusuru
    # gizler. Karta tiklamak olcumun parcasi, kolaylik degil.
    window = sc.storyline_window()
    if window:
        user32.ShowWindow(window[0], 3)          # SW_MAXIMIZE
        sc.focus(window[0])
        box = wintypes.RECT()
        user32.GetWindowRect(window[0], ctypes.byref(box))
        user32.SetCursorPos(
            box.left + int((box.right - box.left) * KART_ORAN[0]),
            box.top + int((box.bottom - box.top) * KART_ORAN[1]),
        )
        time.sleep(0.3)
        user32.mouse_event(0x0002, 0, 0, 0, 0)
        time.sleep(0.08)
        user32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(4)

    sonuc = "COKTU" if cokme_var() else "saglam"
    open_test.force_close()
    time.sleep(2)
    return sonuc


def kosu(adaylar: list[str]) -> int:
    gorev = [KANARYA_ARTI] + [a for a in adaylar
                              if a not in (KANARYA_ARTI, KANARYA_EKSI)] + [KANARYA_EKSI]
    sonuc: dict[str, str] = {}
    for event in gorev:
        sonuc[event] = sor(event)
        print(f"  {event:26s} {sonuc[event]}")

    arti = sonuc.get(KANARYA_ARTI) == "saglam"
    eksi = sonuc.get(KANARYA_EKSI) == "COKTU"
    print("\n=== KANARYA ===")
    print(f"  K+ {KANARYA_ARTI} saglam kalmali : {'GECTI' if arti else 'DUSTU'}")
    print(f"  K- {KANARYA_EKSI} cokmeli        : {'GECTI' if eksi else 'DUSTU'}")

    print("\n=== VERDIKT ===")
    if not (arti and eksi):
        print("  OLCUM YOK: kanaryalar beklendigi gibi davranmadi.")
        print("  Aday sonuclari okunamaz -- tespit mekanizmasi calismiyor.")
        return 1

    saglam = [e for e, r in sonuc.items()
              if r == "saglam" and e not in (KANARYA_ARTI, KANARYA_EKSI)]
    coken = [e for e, r in sonuc.items()
             if r == "COKTU" and e not in (KANARYA_ARTI, KANARYA_EKSI)]
    acilmayan = [e for e, r in sonuc.items() if r == "ACILMADI"]
    print(f"  KABUL EDILDI : {', '.join(saglam) or '-'}")
    print(f"  COKERTIYOR   : {', '.join(coken) or '-'}")
    if acilmayan:
        print(f"  ACILMADI     : {', '.join(acilmayan)}  (cokmeden AYRI bir durum)")
    print()
    print("  KAPSAM: bu tur adin KABUL EDILDIGINI olcer. Tetikleyicinin")
    print("          panelde DOGRU METINLE gorundugunu olcmez -- kabul edilen")
    print("          bir ad yanlis olayi baglamis olabilir.")
    return 0 if not coken else 0


def dogrula() -> int:
    """Regresyon: EVENTS hala saglam mi, COKERTEN hala cokuyor mu.

    Iki yonlu, cunku tek yonlu guard kazanimi korumaz (K7): yalnizca
    "gecerliler hala gecerli" diye bakan bir kontrol, cokerten bir adin
    listeye geri sizmasini gormez.
    """
    print(f"EVENTS: {len(logic.EVENTS)} ad, COKERTEN: {len(logic.COKERTEN_EVENTS)} ad")
    print(f"Toplam {len(logic.EVENTS) + len(logic.COKERTEN_EVENTS)} Storyline turu.\n")
    hata = 0

    print("--- EVENTS (hepsi saglam kalmali) ---")
    for event in logic.EVENTS:
        r = sor(event)
        iyi = r == "saglam"
        hata += 0 if iyi else 1
        print(f"  {event:26s} {r:10s} {'' if iyi else '<-- BEKLENMEDIK'}")

    print("\n--- COKERTEN (hepsi cokmeli) ---")
    for event in logic.COKERTEN_EVENTS:
        r = sor(event)
        iyi = r == "COKTU"
        hata += 0 if iyi else 1
        print(f"  {event:26s} {r:10s} {'' if iyi else '<-- BEKLENMEDIK'}")

    print(f"\n=== VERDIKT: {'GECTI' if not hata else f'{hata} ad beklenmedik davrandi'} ===")
    return 0 if not hata else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("adaylar", nargs="*", help="sinanacak event adlari")
    ap.add_argument("--dogrula", action="store_true",
                    help="EVENTS + COKERTEN regresyonu (uzun surer)")
    a = ap.parse_args()

    if not TEMEL.is_file():
        print(f"Temel dosya yok: {TEMEL}")
        return 2
    if a.dogrula:
        return dogrula()
    if not a.adaylar:
        ap.print_help()
        return 2
    return kosu(a.adaylar)


if __name__ == "__main__":
    raise SystemExit(main())
