"""Storyline'ın kendi çizimini yakalar. Önizleme değil, gerçek.

preview.py bir yaklasim ve sadakat notu neyi yaklasik cizdigini sayiyor. Bir
madde bu turda dogrudan devrede: **metin kutusunun ustunden baslar ve kutuya
kirpilmaz.** Storyline dikey hizalamayi uygular ve tasani kirpar. Yani punto
olceklemesinin sonucunu onizlemeden okumak IYIMSER cevap verir -- onizlemede
sigmis gorunen bir metin, gercekte kesilmis olabilir.

Punto buyutmenin dogrulanmasi bu yuzden burada yapilir: dosya Storyline'da
acilir, pencere yakalanir, goruntu okunur. Yavas ve gurultulu (uygulama
cercevesi de goruntude), ama olculen sey gercek.

    python tools/shoot.py kurs.story -o bak.png

SLAYT SECILEMEZ. Belge dizesi bir donem `--slide 3` yaziyordu; oyle bir
argüman hic olmadi. Storyline dosyayi STORY VIEW'da aciyor ve arac ne
gorunuyorsa onu yakaliyor -- yani kucuk resimler. Belirli bir slayda
bakmak icin o slaydi elle acmak gerekiyor; klavyeyle acmak denendi
(Tab/Home/Enter, odak DOGRULANMIS halde) ve calismadi.

Bakilacak sey ilk slayda TASINABILIYORSA yol acik: sorulari tek bir
slayda toplayan bir dosya uret, sonra yakala.
"""

from __future__ import annotations

import argparse
import ctypes
import subprocess
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


def _front(hwnd: int) -> bool:
    """Pencereyi öne al ve ALDIĞINI DOĞRULA.

    ImageGrab EKRANI yakalar, pencereyi degil. Yani pencere gercekten one
    gelmediyse goruntude baska bir uygulama olur ve dosya yine uretilir --
    "Storyline'in kendi cizimi" diye bakilan sey, ustteki tarayici olabilir.

    SetForegroundWindow tek basina yetmiyor: Windows arka plandaki bir islemin
    one gecmesini engelliyor ve cagri SESSIZCE basarisiz oluyor. Olculdu --
    cagridan sonra on plandaki pencere hala Chrome'du. Donus degeri
    kontrol edilmediginde bu hicbir yerde gorunmez.
    """
    user32.ShowWindow(hwnd, SW_MAXIMIZE)
    ok = ctl.focus(hwnd)
    time.sleep(1.2)
    return ok


def _rect(hwnd: int) -> tuple[int, int, int, int]:
    box = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(box))
    return box.left, box.top, box.right, box.bottom


def capture(out: Path, *, settle: float = 6.0) -> Path:
    from PIL import ImageGrab

    found = ctl.storyline_window()
    if not found:
        raise SystemExit("Storyline penceresi bulunamadi.")
    hwnd = found[0]
    # Odak alinamadiysa GORUNTU URETILMEZ. Uretilseydi ekranda ne varsa o
    # kaydedilirdi ve dosya, adi "Storyline ciziminin gercegi" olan bir
    # yalan olurdu -- bakilan her sey yanlis bir temele oturur.
    if not _front(hwnd):
        raise SystemExit(
            "Storyline penceresi one alinamadi (foreground lock); goruntu "
            "ALINMADI.\nAlinsaydi ekrandaki baska bir uygulamayi kaydederdi.")
    time.sleep(settle)

    # ODAK, YAKALAMANIN TAM ONCESINDE YENIDEN DOGRULANIR.
    #
    # Bir kez one almak yetmiyor: settle beklemesi sirasinda baska bir
    # uygulama one gecebiliyor ve ImageGrab EKRANI yakaladigi icin ustteki
    # pencere kaydediliyor. Olculdu -- Preview yakalanacakken kareye VS Code
    # dustu ve dosya yine uretildi.
    #
    # Guard vardi ama YANLIS ANDA kosuyordu: "o an dogruydu" ile "yakalama
    # aninda dogru" ayni sey degil.
    if user32.GetForegroundWindow() != hwnd and not ctl.focus(hwnd):
        raise SystemExit(
            "Yakalama aninda Storyline on planda degildi; goruntu ALINMADI.\n"
            "Baska bir uygulama one gecmis -- kare onu kaydederdi.")
    image = ImageGrab.grab(bbox=_rect(hwnd), all_screens=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("story")
    parser.add_argument("-o", "--out", default="storyline.png")
    parser.add_argument("--keep", action="store_true",
                        help="isi bitince Storyline'i acik birak")
    parser.add_argument("--wait", type=float, default=35.0)
    args = parser.parse_args()

    story = Path(args.story).resolve()
    if not story.is_file():
        print(f"Proje yok: {story}")
        return 2

    open_test.force_close()
    open_test.launch(story)
    deadline = time.time() + args.wait
    while time.time() < deadline:
        found = ctl.storyline_window()
        if found and story.name.lower() in (found[1] or "").lower():
            break
        time.sleep(1.0)
    else:
        open_test.force_close()
        raise SystemExit(f"{story.name} {args.wait:.0f} sn icinde acilmadi.")

    out = capture(Path(args.out).resolve())
    if not args.keep:
        open_test.force_close()
    print(f"{story.name} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
