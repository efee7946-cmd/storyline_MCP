"""Suit'in SON SATIRI beş çıkış yolunun beşinde de doğru mu.

NICIN VAR. Son satir artik butun suit'in okundugu YUZEY: uclu sayim
orada duruyor ve `tail -1` yeterli olsun diye oraya kondu. Gerekcesi
olculmus iki kayiptan cikti (2026-09-12):

  * suit `| tail -12` ile kosuldu ve VERDIKT satiri kesilenin icinde
    kaldi -- kesilen sey METINDI
  * ayni kosuda cikis kodu 0 GORUNDU, oysa uc kapi KOSAMADI'ydi.
    Sebep suit degil BORU: `python -c "raise SystemExit(1)" | tail -5`
    icin `$?` = 0, borusuz 1. Yani kesilen sey KODUN KENDISI oldu.

Yuzey oldugu icin kaymasi en pahali yer, ve kaymasi SESSIZ: satir
basilmaya devam eder, sayilar yanlis olur. Ozellikle iki hal:

  KESISEN KOVALAR  `kalanlar` ile `atlananlar` kesisiyor (kosamayan bir
      kapi ikisine de giriyor). Sayim o listelerin uzunluklarindan
      turetilirse TOPLAMAZ; ayri kovalar tutuluyor ve satir kendi
      toplamini denetliyor ([SAYIM TUTMUYOR]).
  EKSIK CIKIS YOLU  main()'in bes donus yolu var ve biri satiri
      basmayi atlarsa `tail -1` tam o durumda -- kotu durumda --
      sessizce baska bir sey gosterir.

BES AYAK, hepsi GERCEK DALI kosuyor: `ADIMLAR` ve `kos()` prob
degerlerle degistiriliyor, ikinci bir uygulama YAZILMIYOR (ayni yontem
suit.py'nin kendi uclu durum notunda da kullanildi, 2026-09-10). Alt
surec yok, bu yuzden kapi ~0.2 saniye.

    python tools/son_satir_kapi.py
"""

from __future__ import annotations

import contextlib
import io
import pathlib
import sys
import warnings

import ayak

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

warnings.simplefilter("ignore")

import suit                                                  # noqa: E402

KOSAMADI = 3

AYAKLAR = ayak.Defter(
    "hepsi gecti",
    "kapi kaldi",
    "bakilmadi",
    "rapor sapmasi",
    "kanarya kaldi",
    genislik=14,
)

# ad -> (adim kodlari, beklenen cikis kodu, son satirda ARANAN parcalar)
#
# Kodlar `kos()` yerine konuyor; "r" adi rapor adimi, otekiler kapi.
# Kanarya vakasinda ad suit.KANARYALAR'dan geliyor, cunku kosunun terk
# edilmesi o kumeye bagli -- adi elle yazmak, kume degisince ayagi
# sessizce baska bir dala tasirdi.
#
# KUME BOSSA KAPI "KOSAMADI" DER, PATLAMAZ. `sorted(...)[0]` bos kumede
# IndexError verirdi: import aninda, gerekcesiz. Bir kapinin en kotu
# hali "gecti" sanilmak, ikincisi ne oldugu anlasilmayan bir yigin izi.
KANARYA_ADI = sorted(suit.KANARYALAR)[0] if suit.KANARYALAR else None

VAKALAR = {
    "hepsi gecti": ({"a": 0, "b": 0, "r": 0}, 0,
                    ("3 adim", "3 gecti", "0 kaldi", "0 BAKILMADI")),
    "kapi kaldi": ({"a": 0, "b": 1, "r": 0}, 1,
                   ("2 gecti", "1 kaldi", "0 BAKILMADI")),
    "bakilmadi": ({"a": 0, "b": 3, "r": 0}, 1,
                  ("2 gecti", "0 kaldi", "1 BAKILMADI")),
    "rapor sapmasi": ({"a": 0, "b": 0, "r": 1}, 0,
                      ("2 gecti", "0 kaldi", "0 BAKILMADI",
                       "1 rapor sapmasi")),
}
if KANARYA_ADI is not None:
    VAKALAR["kanarya kaldi"] = ({KANARYA_ADI: 1, "a": 0, "b": 0, "r": 0}, 1,
                                ("0 gecti", "1 kaldi", "KOSULMADI"))


def _kos_vaka(kodlar: dict) -> tuple[int, list[str]]:
    """Gercek `main()`i prob degerlerle kostur; (kod, satirlar) don."""
    onceki_adimlar, onceki_kos, onceki_argv = suit.ADIMLAR, suit.kos, sys.argv
    try:
        suit.ADIMLAR = [(ad, [sys.executable, f"tools/{ad}.py"], ad != "r",
                         False, "prob") for ad in kodlar]
        suit.kos = lambda ad, komut, _k=kodlar: (_k[ad], 0.1, "prob")
        sys.argv = ["suit.py"]
        tampon = io.StringIO()
        with contextlib.redirect_stdout(tampon):
            kod = suit.main()
    finally:
        suit.ADIMLAR, suit.kos, sys.argv = onceki_adimlar, onceki_kos, onceki_argv
    return kod, [s for s in tampon.getvalue().splitlines() if s.strip()]


def kanarya() -> list[str]:
    kusur: list[str] = []
    for ad, (kodlar, beklenen, aranan) in VAKALAR.items():
        kod, satirlar = _kos_vaka(kodlar)
        son = satirlar[-1] if satirlar else "(cikti yok)"
        AYAKLAR.yaz(ad, f"kod={kod} son={son[:66]}")

        if not son.startswith("SUIT:"):
            kusur.append(
                f"{ad}: SON SATIR sayim DEGIL ({son[:80]!r}). `tail -1` bu "
                f"durumda baska bir sey gosterir -- ve tam bu durum, kotu "
                f"durum.")
            continue
        if kod != beklenen:
            kusur.append(f"{ad}: cikis kodu {kod}, beklenen {beklenen}.")
        eksik = [p for p in aranan if p not in son]
        if eksik:
            kusur.append(
                f"{ad}: son satirda eksik parca {eksik} -- satir basiliyor "
                f"ama SAYILAR yanlis. Kaymanin sessiz hali tam bu.")
        if "SAYIM TUTMUYOR" in son:
            kusur.append(
                f"{ad}: kovalar toplamiyor ({son[:90]}). `kalanlar` ile "
                f"`atlananlar` kesisiyor; sayim onlarin uzunlugundan "
                f"turetilmis olabilir.")
    return kusur


def main() -> int:
    if KANARYA_ADI is None:
        print("KOSAMADI: `suit.KANARYALAR` bos, yani kosunun terk edildigi "
              "dal kurulamiyor. Dort ayak sinanabilir ama besincisi "
              "SINANMAZ -- 'gecti' DEGIL, 'bakilmadi'.")
        return KOSAMADI
    kusur = kanarya()
    _kosmayan = AYAKLAR.kosmayanlar()
    if _kosmayan:
        kusur.append("BEYANDA DURAN AMA KOSMAYAN AYAK: %s"
                     % ", ".join(_kosmayan))
    if kusur:
        print("\nKAPI KALDI:")
        for k in kusur:
            print(f"  - {k}")
        return 1
    print("\nkapi gecti: bes cikis yolunun besi de uclu sayimi SON SATIRA "
          "basiyor")
    print("KAPSAM: satirin BICIMI olculuyor, adimlarin kendisi DEGIL -- "
          "kodlar\n        prob. Gercek kosunun dogrulugu suit'in kendi "
          "adimlarinda.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
