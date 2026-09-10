"""Kanarya artefaktlarına kilit -- çarpışma bir "koşamadı" halidir.

NICIN VAR, ve bir yanlis alarmdan dogdu (2026-09-11). Kapilar
`test/_canary/` icine SABIT adli dosyalar yaziyor; bu deponun kapi
gelenegi bu, cunku adimlar birbirinin urettigi dosyayi okuyor
(`suit.py`nin "SIRA BAGIMLILIKTIR" notu). Ama iki kosu ayni anda ayni
dosyaya yazarsa ikisi de yanlis okur.

Olculdu: suit kosarken `kablolama_kapi.py` elle iki kez kosuldu ve
suit'in adimi "DEGISMEZ EKLEMIYOR" diye kirmiziya dondu; temiz kosuda
ayni kod yesil gecti. Yani "kostu ve dustu" gibi gorunen bir "ortam
bozuldu" -- tanidik ayrimin tersi, ve daha kotusu: cevresel kirmizi,
kirmiziyi okumayi ogreten seydir.

OLAYIN KAPSAMI TEHLIKENIN KAPSAMI DEGILDI. O gun carpisan kapi
tesadufen `kablolama` idi (elle kosulan oydu). Ayni carpismayi
`_canary`ye yazan HER kapi uretebilir: variety, uslup, rubric_fixtures,
oturum, duzenle, ajan yolu, produced, yeni_modul... Bu yuzden not
yakalayan kapinin basliginda BIRAKILMADI; tehlike burada, tek yerde
TESPIT EDILEN bir hale cevrildi.

SOZLESME ZATEN VARDI: kilit tutulamiyorsa bu bir KOSAMADI'dir (cikis 3),
"kapi kaldi" degil. `suit.py` onu ayri bir sutunda gosterir ve
"temiz DEGIL, bakilmadi" yazar.

DEVIR, YOKSA SUIT KENDINI KILITLERDI. `suit.py` de ayni sarmalayiciyi
kullaniyor ve adimlari ALT SUREC olarak calistiriyor. Kilidi devretmese
her adim "kilit tutulamadi" diye 3 donerdi -- yani koruma, korudugu
seyi imkansiz kilardi. Ust surec kilidi alinca ortam degiskenine kendi
pid'ini yaziyor; onu goren cocuk "zaten tutuluyor" deyip gecuyor.

BAYAT KILIT CALINIR, sessizce degil: cokmus bir kosu kilidi ardinda
birakabilir ve o dosya butun kapilari kalici olarak 3'e dusururdu --
kalici bir "bakilmadi", kalici kirmizidan daha sinsi. 30 dakikadan eski
kilit devralinir ve devralindigi YAZILIR.
"""

from __future__ import annotations

import json
import os
import pathlib
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
KILIT = ROOT.parent / "test" / "_canary" / ".kilit"
# SURE BIRINCIL OLCU DEGIL, YEDEK -- VE BU BIR DUZELTME (2026-09-11).
#
# Ilk surum yalnizca sureye bakiyordu: 30 dakikadan eski kilit devralinir.
# Esik, en uzun MESRU tutusun ustunde olmak zorunda ve degildi: suit'in
# kendi basligi acilma fazi icin "~25 dk" diyor (`canary` + `open_test`).
# Bes dakikalik marj asildiginda olan sey tam olarak kilidin engellemek
# icin var oldugu sey -- ikinci kosu, birincisi HALA YAZARKEN devralir --
# ve bu kez SESSIZ, cunku kilit artik "bakildi" diyor.
#
# Esigi yukseltmek marji buyutur, iliskiyi kurmaz. Sorulacak dogru soru
# sure degil GERCEK: o pid yasiyor mu.
#
#   pid olu      -> HEMEN devral (cokmus kosu; esik beklemeye gerek yok)
#   pid canli    -> TUT, sure ne olursa olsun
#   bilinmiyor   -> canli SAY (guvenli yon: "bakilmadi" demek, birinin
#                   yazdigi dosyayi devralmaktan iyidir)
#
# Sure yalnizca PID YENIDEN KULLANIMINA karsi yedek olarak kaliyor ve o
# yuzden cok yuksek: mesru hicbir kosu bu kadar surmez.
BAYATLIK_SN = 4 * 3600
DEVIR = "KANARYA_KILIT_SAHIBI"
KOSAMADI = 3


def _yaz(fd) -> None:
    os.write(fd, json.dumps({
        "pid": os.getpid(), "zaman": time.time(),
        "kosu": os.environ.get("KANARYA_KOSU", "elle"),
    }).encode("utf-8"))


def _yasiyor(pid) -> bool | None:
    """O pid canli mi. Cevap alinamazsa None -- "olu" DEGIL.

    `server._storyline_running` GORUNTU ADINA bakiyor (Storyline.exe),
    pid'e degil; yani devralinacak bir yardimci yok. Bicim ondan alindi:
    `tasklist` + timeout + istisnada sessiz.

    None ile False AYRI: "sorulamadi" ile "olu" ayni sey degil. Olu
    sanmak, birinin yazmakta oldugu dosyalari devralmak demek.
    """
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    import subprocess
    try:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                             capture_output=True, text=True, timeout=10)
    except Exception:                            # noqa: BLE001
        return None
    if out.returncode != 0:
        return None
    return str(pid) in out.stdout


def _al() -> bool:
    """Kilidi al. Alindiysa True, baskasi tutuyorsa False."""
    KILIT.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(KILIT, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            veri = json.loads(KILIT.read_text(encoding="utf-8") or "{}")
        except Exception:                       # noqa: BLE001
            veri = {}
        yas = time.time() - float(veri.get("zaman") or 0)
        canli = _yasiyor(veri.get("pid"))
        if canli is False:
            print(f"kanarya kilidi OLU bir surece ait (pid {veri.get('pid')}, "
                  f"{yas / 60:.0f} dk once) -- devraliniyor.")
            try:
                KILIT.unlink()
            except OSError:
                return False
            return _al()
        if yas > BAYATLIK_SN:
            # YEDEK OLCU: pid canli GORUNUYOR ama kilit mesru hicbir
            # kosunun surmeyecegi kadar eski. En olasi aciklama pid
            # yeniden kullanimi.
            print(f"kanarya kilidi {yas / 3600:.1f} saatlik ve pid "
                  f"{veri.get('pid')} "
                  f"{'canli gorunuyor' if canli else 'sorgulanamadi'} -- "
                  f"pid yeniden kullanimi varsayilip devraliniyor.")
            try:
                KILIT.unlink()
            except OSError:
                return False
            return _al()
        print(f"KOSAMADI: kanarya artefaktlari baska bir kosu tarafindan "
              f"tutuluyor (pid {veri.get('pid')} "
              f"{'CANLI' if canli else 'sorgulanamadi'}, {yas:.0f} sn once). "
              f"Ayni anda iki kosu ayni dosyalara yazarsa IKISI DE yanlis "
              f"okur; bu 'kapi kaldi' DEGIL, 'bakilmadi'.")
        return False
    try:
        _yaz(fd)
    finally:
        os.close(fd)
    return True


def _birak() -> None:
    try:
        KILIT.unlink()
    except OSError:
        pass


def korumali(fn, *args, **kwargs) -> int:
    """`fn`i kanarya kilidi altinda kos. Kilit yoksa KOSAMADI (3).

    Ust surec kilidi tutuyorsa (DEVIR ortam degiskeni) dogrudan kosar:
    suit kendi adimlarini alt surec olarak calistiriyor ve devir olmadan
    koruma, korudugu seyi imkansiz kilardi.
    """
    if os.environ.get(DEVIR):
        return fn(*args, **kwargs)
    if not _al():
        return KOSAMADI
    os.environ[DEVIR] = str(os.getpid())
    try:
        return fn(*args, **kwargs)
    finally:
        os.environ.pop(DEVIR, None)
        _birak()
