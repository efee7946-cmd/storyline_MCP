"""Ayirt kaydini OKUR -- `ayirt_kapi`yi kosturmaz.

NICIN AYRI BIR ADIM. `ayirt_kapi` suit'te DEGIL ve olmamali: urun
kaynagini gecici degistiriyor, ve sert bir oldurmede `finally` kosmaz --
mutasyonlu kalan bir agac, duzelttigi seyden kotudur.

Bedeli `ayirt_kapi`nin kendi basliginda yaziyor: "elle kosan sey kayar".
Zarf (`ayirt_sonuc.json`) tam bunun icin var. AMA BIR ACIK KALMISTI:
zarfi kimse okumuyor. Bir JSON dosyasi okunmaz; suit'in ciktisi her
kosuda okunur. Bu adim, "elle kosan sey kayar" notunu OLCULEN BIR
NICELIGE cevirir -- kayma, herkesin zaten baktigi yuzeyde gorunur.

RAPOR, KAPI DEGIL (`consistency`, `completeness`, `inventory` gibi).
Hicbir sey mutasyona ugramiyor, dolayisiyla mutasyon riski SIFIR.

CIKIS KODLARI
    0  kayit tam: her tohumlu ayagin kaniti var
    1  RAPOR SAPMASI -- kayit eksik ya da kendini temsil etmiyor
    3  KOSAMADI -- zarf yok ya da okunamiyor (henuz hic kosulmamis)

YAS BIR SAPMA DEGIL, BIR SAYI. "Kac commit once" basiliyor ama esik
KONMUYOR: "ne kadar eski fazla eski" bir hukum, ve keyfi bir esik
okunmayan gurultu uretir. Okuyan karar verir -- gorunur olmasi yeter.

    python tools/ayirt_rapor.py
"""

from __future__ import annotations

import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
ZARF = ROOT / "tools" / "ayirt_sonuc.json"


def _mesafe(commit: str) -> tuple[str, bool]:
    """(metin, KONUMLANDI mi). Kayittaki commit ile HEAD arasi mesafe.

    Ikinci deger ayri donuyor cunku "bu gecmiste YOK" bir yas degil bir
    SAPMA: kayit, burada bulunmayan bir commit'i adlandiriyorsa hicbir
    seyi konumlandirmaz ve "13/13 kanitli" NEYIN kaniti belli degildir.
    Ilk surumde bu satir basiliyor ama kod 0 donuyordu -- tam olarak bu
    adimin onlemeye calistigi hal: duran, okunan, dayanaksiz bir sayi.
    """
    if not commit:
        return "commit yazili degil", False
    try:
        var = subprocess.run(["git", "cat-file", "-e", commit + "^{commit}"],
                             cwd=ROOT, capture_output=True, timeout=30)
        if var.returncode != 0:
            return "commit bu gecmiste YOK", False
        n = subprocess.run(["git", "rev-list", "--count", f"{commit}..HEAD"],
                           cwd=ROOT, capture_output=True, text=True,
                           timeout=30)
        if n.returncode != 0:
            return "mesafe olculemedi", True
        sayi = n.stdout.strip()
        return ("bu commit" if sayi == "0" else f"{sayi} commit once"), True
    except Exception:                                   # noqa: BLE001
        return "mesafe olculemedi", True


def main() -> int:
    if not ZARF.exists():
        print(f"KOSAMADI: {ZARF.name} yok -- `ayirt_kapi` bu depoda hic "
              "kosulmamis. Kapsam BILINMIYOR (sifir degil).")
        return 3
    try:
        d = json.loads(ZARF.read_text(encoding="utf-8"))
    except Exception as hata:                           # noqa: BLE001
        print(f"KOSAMADI: {ZARF.name} okunamadi ({hata}).")
        return 3

    k = d.get("kapsam", {})
    tohumlu = k.get("tohumlanan")
    kanitli = k.get("kanitli")
    toplam = k.get("toplam")
    commit = d.get("commit", "")
    ortam = d.get("ortam") or {}

    # ESKI ZARF: `kanitli` alani 316906d'den once YOKTU. Yoklugu "sifir"
    # diye okumak, tam da bu adimin onlemeye calistigi kaymanin ta
    # kendisi olurdu -- olculmemis bir sey kotu sonuc gibi gorunur.
    eski_bicim = kanitli is None

    mesafe, konumlandi = _mesafe(commit)
    print(f"son kosu {commit or '(bilinmiyor)'}, {mesafe}, "
          + (f"{tohumlu}/{toplam} tohumlu (kanit sayisi YOK: eski bicim)"
             if eski_bicim else
             f"{kanitli}/{tohumlu} kanitli, {tohumlu}/{toplam} tohumlu"))

    if ortam:
        print(f"  ortam: {ortam.get('surum', '?')} @ "
              f"{pathlib.Path(ortam.get('yorumcu', '?')).as_posix()} "
              f"(mcp: {ortam.get('mcp_ice_aktarilabiliyor')})")
    else:
        print("  ortam: KAYITLI DEGIL (eski bicim) -- kaydi hangi "
              "yorumcunun urettigi bilinmiyor")

    sapma = []
    if not konumlandi:
        sapma.append(f"kayit {commit or '(commit yazili degil)'} diyor ama "
                     "bu commit bu gecmiste YOK -- sayi hicbir seyi "
                     "konumlandirmiyor.")
    if eski_bicim or not ortam:
        sapma.append("zarf ESKI BICIM: yeniden uretin "
                     "(.venv ile `python tools/ayirt_kapi.py`).")
    if not d.get("commit_temsil_ediyor_mu", True):
        sapma.append("kayit bir commit'i TEMSIL ETMIYOR: kosarken "
                     f"{len(d.get('islenmemis_dosyalar') or [])} dosya "
                     "islenmemisti.")
    if not eski_bicim and kanitli != tohumlu:
        eksik = {ad: d["kapsam"].get(ad, 0)
                 for ad in ("kosamadi", "kor", "sapma")
                 if d["kapsam"].get(ad, 0)}
        sapma.append(f"tohumlu {tohumlu} ayagin {tohumlu - kanitli}'inin "
                     f"KANITI YOK: {eksik}. Ucuncu durum: 'kaldi' degil, "
                     "'bakilmadi'.")

    for c in sapma:
        print("  RAPOR SAPMASI: " + c)
    return 1 if sapma else 0


if __name__ == "__main__":
    raise SystemExit(main())
