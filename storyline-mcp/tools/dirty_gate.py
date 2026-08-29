"""Storyline gerçekten yazdı mı? Kalibrasyon ölçümünden ÖNCE koşan kapı.

Bu dosya bir olcu degil, bir ON KOSUL. Varlik sebebi tek bir gecmis hata:

    Kalibrasyon deneyi (2026-08-14) 17/24/32/48 punto ile kasten kucuk
    kutulara yazi koydu, dosyayi Storyline'da acti, save_and_close cagirdi.
    Dort kutu da 12.0 birim kaldi ve pakette TEK BIR BAYT degismedi. Sonuc
    "Storyline yeniden boyutlandirmiyor" diye okundu.

    Yanlisti. save_and_close, Ctrl+S'i yalnizca pencere basligi KIRLI
    gosteriyorsa gonderir; bir dosyayi acmak onu kirletmez. Storyline hicbir
    sey yazmadi. Deney, olcmeyi amacladigi seyi HIC OLCMEDI -- sifir fark,
    "iz yok"un degil "yazma yok"un sonucuydu.

Bu, K3'un en pahali bicimi: negatif sonuc, deneyin calistigi kanitlanmadan
okunamaz. Ve tekrari ozellikle tehlikeli, cunku bir sonraki sefer cikacak
sifir fark "diakritik etkilemiyor" diye okunur ve B1'in butun kapsamini
sessizce kucultur.

O yuzden kirlilik BIR KONTROL, ve olcumden once kosar:

    1. dosya gercekten Storyline'da mi   (kilit + pencere basligi)
    2. belge KIRLI mi                    (basliktaki yildiz)
    3. kaydetme gercekten YAZDI mi       (dosya damgasi/hash degisti mi)

Ucu de gecmezse olcum HIC BASLATILMAZ. "Olculemedi" gecerli bir cevaptir;
"fark yok" degildir.

    python tools/dirty_gate.py kurs.story
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "panel"))

import storyline_ctl
from storyline_mcp.package import lock_state


def _damga(path: Path) -> tuple[int, str]:
    data = path.read_bytes()
    return len(data), hashlib.sha256(data).hexdigest()[:16]


def kapi(path: Path, *, kirlet: bool = True) -> dict:
    """Storyline'in bu dosyaya gercekten yazabildigini kanitlar."""
    out: dict = {"dosya": path.name}

    if not path.is_file():
        return {**out, "gecti": False, "nerede": "dosya yok"}

    # 1. Storyline bu dosyayi tutuyor mu?
    if not storyline_ctl.holds(path):
        return {**out, "gecti": False, "nerede": "acik degil",
                "neden": f"kilit={lock_state(path)}, "
                         f"acik proje={storyline_ctl.open_project()!r}"}
    out["acik"] = True

    # 2. Kirlet ve kirlendigini DOGRULA.
    if kirlet:
        sonuc = storyline_ctl.make_dirty()
        out["kirletme"] = sonuc.get("how")
        if not sonuc.get("dirty"):
            return {**out, "gecti": False, "nerede": "kirletilemedi",
                    "neden": sonuc.get("reason", "")}
    elif not storyline_ctl.is_dirty():
        return {**out, "gecti": False, "nerede": "kirli degil",
                "neden": "kirletme kapali ve belge zaten temiz"}
    out["kirli"] = True

    # 3. Kaydet, kapat, ve dosyanin GERCEKTEN degistigini olc.
    once = _damga(path)
    kapandi = storyline_ctl.save_and_close(path)
    if not kapandi.get("closed"):
        return {**out, "gecti": False, "nerede": "kapanmadi",
                "neden": kapandi.get("reason", "")}
    time.sleep(1.0)
    sonra = _damga(path)
    out["once"], out["sonra"] = once, sonra
    if once == sonra:
        return {**out, "gecti": False, "nerede": "yazma yok",
                "neden": "belge kirliydi ve kapandi, ama dosya damgasi "
                         "degismedi — Storyline yine yazmadi"}
    return {**out, "gecti": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("story")
    parser.add_argument("--kirletme", action="store_true",
                        help="kirletme; belge zaten kirliyse devam et")
    args = parser.parse_args()

    sonuc = kapi(Path(args.story).resolve(), kirlet=not args.kirletme)
    for anahtar, deger in sonuc.items():
        print(f"  {anahtar:<10}{deger}")
    print()
    if sonuc.get("gecti"):
        print("KAPI ACIK: Storyline bu dosyaya gercekten yazdi. Kalibrasyon\n"
              "olcumu baslatilabilir; cikacak sayi bir OLCUMDUR.")
        return 0
    print(f"KAPI KAPALI ({sonuc.get('nerede')}). Kalibrasyon olcumu\n"
          "BASLATILMAMALI: cikacak her sayi, Storyline'in ne yaptigini degil\n"
          "deneyin kosmadigini gosterir. 'Olculemedi' yazin, 'fark yok' degil.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
