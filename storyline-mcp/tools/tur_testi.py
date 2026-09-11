"""Storyline bizim yazdığımızı KORUYOR mu -- aç, kaydet, farkı ölç.

NICIN VAR. `tools/open_test.py` tek bir soru soruyor: dosya ACILIYOR mu.
Acilmak bir esik ama dusuk bir esik -- Storyline bir projeyi acar, icinde
sevmedigi seyi SESSIZCE yeniden yazar ve kaydeder. "Acildi" o yeniden
yazmayi gormez.

DEPO BUNDAN BIR KEZ ISIRILDI, ve kesif KAZAYDI: `yks.story` acilip
kaydedildiginde Storyline ikinci `quizLst`teki `Quiz_Result`i SILMIS,
yerine bos bir `Quiz1` koymustu (olculdu 2026-09-07). Butun puanlama
zinciri ipligi o kazadan cikti -- `izleme`nin "Storyline'in OKUDUGU
liste" ayrimi, `zincir`in sifirinci kosulu, hepsi.

Kazayi kontrole ceviren ucluyu artik elimizde:

    anlik goruntu  ->  Storyline'da AC ve KAYDET  ->  fark

Anlik goruntu ve fark `storyline_mcp/oturum.py`den (kimlige dayali,
yapisal: slayt, sekil, tetikleyici, katman, degisken, metin ozeti).
Puanlama zinciri `puanlama.izleme/zincir`den. Bu arac ikisini birlestirip
karsilastiriyor; kendi olcusunu YAZMIYOR.

KAPI ILE RAPOR AYRI, ve ayrim kasitli:
    KAPI   puanlama zinciri tur sonrasi BOZULMAMALI -- kayitlar
           kaybolmamali, quizLst sayisi artmamali. `yks` isirmasi tam
           olarak buydu.
    RAPOR  yapisal fark yazilir ama HUKUM VERMEZ. Storyline'in mesru
           normallestirmeleri var (ad, sira, bicim) ve onlari kusur
           saymak kapiyi kalici kirmiziya boyardi.

PAHALI: Storyline aciliyor. `--tam` tarafinda durur, gunluk kosuda degil.

ONCEDEN ACIK PROJEYE DOKUNMAZ: Storyline penceresi varsa KOSAMADI (3)
doner. Baskasinin acik projesini kaydedip kapatmak, olcum icin
odenecek bir bedel degil.

    python tools/tur_testi.py <kurs.story> [<kurs2.story> ...]
"""

from __future__ import annotations

import argparse
import pathlib
import shutil
import sys
import time
import warnings

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "panel"))

warnings.simplefilter("ignore")

import ayak                                            # noqa: E402
from storyline_mcp.package import StoryPackage         # noqa: E402
from storyline_mcp import model, oturum, puanlama      # noqa: E402

KOSAMADI = 3
ACILMADI = "ACILMADI"

AYAKLAR = ayak.Defter(
    "acildi",
    "zincir",
    "kayit",
    "quizLst",
    "yapisal",
    genislik=10,
)


def _zincir_hali(yol: pathlib.Path) -> dict:
    pkg = StoryPackage(yol)
    index = model.slide_index(pkg)
    iz = puanlama.izleme(pkg, index)
    return {
        "kayitli": set(iz["registered"]),
        "quizlst": iz["quizlst_sayisi"],
        "gorunmeyen": list(iz["gorunmeyen_quiz"]),
        "kirik": puanlama.zincir(pkg),
    }


def tur(yol: pathlib.Path) -> list[str]:
    """Bir dosyayi ac-kaydet-kapat ve NE DEGISTIGINI olc."""
    import open_test as ot
    import storyline_ctl as ctl

    kusur: list[str] = []
    for ek in (oturum.ANLIK_UZANTI, oturum.KUNYE_UZANTI):
        (yol.with_suffix(yol.suffix + ek)).unlink(missing_ok=True)
    oturum.anlik_goruntu(yol, etiket="tur testi")
    once = _zincir_hali(yol)

    # ONCE TEMIZ ZEMIN. `test_open` da boyle yapiyor ve sebebi olculdu:
    # bir onceki turdan kapanmakta olan surec varken `launch` yeni bir
    # ornek baslatmiyor ve dosya HIC acilmiyor. O hal "Storyline acmadi"
    # diye okunursa urune ait olmayan bir kusur bildirilmis olur.
    def _surec_var() -> bool:
        import subprocess
        try:
            out = subprocess.run(["tasklist", "/FI",
                                  "IMAGENAME eq Storyline.exe", "/NH"],
                                 capture_output=True, text=True, timeout=10)
        except Exception:                              # noqa: BLE001
            return False
        return "Storyline.exe" in out.stdout

    def _dene() -> str | None:
        # SUREC GERCEKTEN GITSIN. `force_close` PENCERENIN gittigini
        # dogruluyor; surec hala olurken `launch` cagrilirsa yeni ornek
        # baslamiyor ve dosya HIC acilmiyor -- olculdu: kapi "Storyline
        # acmadi" diyordu, ayni dosya elle 15 saniyede aciliyordu.
        ot.force_close()
        for _ in range(20):
            if not _surec_var():
                break
            time.sleep(1)
        ot.launch(yol)
        for _ in range(40):
            time.sleep(2)
            baslik = ctl.open_project() or ""
            if yol.stem.casefold() in baslik.casefold():
                return baslik
        return None

    # IKI DENEME. Ilki cevresel bir yarisa denk gelebilir; ikincisi de
    # dusuyorsa sebep dosyadadir.
    acildi = _dene() or _dene()
    AYAKLAR.yaz("acildi", f"{yol.name} -> {'EVET' if acildi else 'HAYIR'}")
    if not acildi:
        ot.force_close()
        # KOSAMADI, KOSTU-VE-DUSTU DEGIL: dosya acilmadiysa turun HICBIR
        # ayagi olculmedi. Bunu "kapi kaldi" diye bildirmek, urune ait
        # olmayan bir kusur uydurur -- ve olculdu: bir onceki turdan
        # kapanmakta olan Storyline varken tam bu hal dogdu.
        kusur.append(ACILMADI + f": {yol.name} Storyline'da acilmadi "
                     f"(son baslik: {ctl.open_project()!r})")
        return kusur

    sonuc = ctl.save_and_close(acildi)
    if not sonuc.get("closed"):
        kusur.append(f"{yol.name}: kaydet-kapat basarisiz "
                     f"({sonuc.get('reason','?')}) -- dosya yarim kalmis "
                     f"olabilir, fark okunmamali")
        return kusur

    sonra = _zincir_hali(yol)

    # KAPI 1: kayitlar kaybolmamali.
    kayip = sorted(once["kayitli"] - sonra["kayitli"])
    AYAKLAR.yaz("kayit", f"{len(once['kayitli'])} -> {len(sonra['kayitli'])}"
                         + (f" KAYBOLAN: {kayip[:3]}" if kayip else ""))
    if kayip:
        kusur.append(f"{yol.name}: Storyline {len(kayip)} quiz kaydini SILDI "
                     f"({', '.join(kayip[:3])}) -- o sorular artik puana "
                     f"girmiyor")

    # KAPI 2: quizLst sayisi artmamali (yks isirmasinin imzasi).
    AYAKLAR.yaz("quizLst", f"{once['quizlst']} -> {sonra['quizlst']}"
                           + (f", gorunmeyen: {sonra['gorunmeyen']}"
                              if sonra["gorunmeyen"] else ""))
    if sonra["quizlst"] > once["quizlst"]:
        kusur.append(f"{yol.name}: quizLst {once['quizlst']} -> "
                     f"{sonra['quizlst']} -- Storyline ikinci bir liste "
                     f"uretti ve ilkini okur; ikincideki quiz ATILIR")

    # KAPI 3: zincir tur ONCESI temizse SONRASI da temiz olmali.
    AYAKLAR.yaz("zincir", f"once {len(once['kirik'])} kirik -> sonra "
                          f"{len(sonra['kirik'])}")
    if not once["kirik"] and sonra["kirik"]:
        kusur.append(f"{yol.name}: zincir tur ONCESI temizdi, SONRASI kirik "
                     f"({sonra['kirik'][0][:80]})")

    # RAPOR: yapisal fark. Hukum YOK -- Storyline'in mesru
    # normallestirmeleri var ve onlari kusur saymak kapiyi kalici
    # kirmiziya boyardi.
    f = oturum.fark(yol)
    if not f["anlik_goruntu"]:
        AYAKLAR.yaz("yapisal", "OLCULEMEDI (anlik goruntu yok)")
    elif f["dokunulmadi"]:
        AYAKLAR.yaz("yapisal", "Storyline hicbir yapisal degisiklik yapmadi")
    else:
        ozet = []
        if f["eklenen_slaytlar"]:
            ozet.append(f"+{len(f['eklenen_slaytlar'])} slayt")
        if f["silinen_slaytlar"]:
            ozet.append(f"-{len(f['silinen_slaytlar'])} slayt")
        if f["degisen_slaytlar"]:
            ozet.append(f"~{len(f['degisen_slaytlar'])} slayt")
        if f["eklenen_degiskenler"] or f["silinen_degiskenler"]:
            ozet.append(f"degisken +{len(f['eklenen_degiskenler'])}"
                        f"/-{len(f['silinen_degiskenler'])}")
        AYAKLAR.yaz("yapisal", ", ".join(ozet) + "  (RAPOR, hukum degil)")
        for d in f["degisen_slaytlar"][:3]:
            print(f"              {d['slayt']}: {d['ozet']}")
    return kusur


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("kurslar", nargs="+")
    args = ap.parse_args()

    import open_test as ot
    import storyline_ctl as ctl
    if ot.EXE is None:
        print("KOSAMADI: Storyline kurulu degil.")
        return KOSAMADI
    if ctl.storyline_window() is not None:
        print("KOSAMADI: Storyline'da bir proje ACIK. Baskasinin acik "
              "projesini kaydedip kapatmak olcum icin odenecek bedel degil; "
              "kapatip tekrar deneyin.")
        return KOSAMADI

    kusur: list[str] = []
    for ad in args.kurslar:
        # MUTLAK YOL SART. `launch` Storyline'i ALT SUREC olarak
        # baslatiyor (`Popen([EXE, str(path)])`) ve goreli bir yol o
        # surecin kendi calisma dizinine gore cozulur -- dosya bulunmaz,
        # Storyline BOS acilir, ve kapi bunu "acilmadi" diye okur.
        # Olculdu: ayni dosya mutlak yolla 15 saniyede aciliyor, goreli
        # yolla hic acilmiyordu. Kapinin uc kosusunu yiyen sebep buydu;
        # surec bekleme ve tekrar deneme onu duzeltmedi cunku kusur
        # cevrede degil CAGRIDAYDI.
        yol = pathlib.Path(ad).resolve()
        if not yol.exists():
            print(f"KOSAMADI: dosya yok ({yol}).")
            return KOSAMADI
        # TURU ORIJINAL USTUNDE YAPMA: Storyline dosyayi yeniden yaziyor.
        kopya = yol.with_suffix(yol.suffix + ".tur.story")
        shutil.copy2(yol, kopya)
        kusur += tur(kopya)

    kosmayan = AYAKLAR.kosmayanlar()
    if kosmayan:
        kusur.append("BEYANDA DURAN AMA KOSMAYAN AYAK: %s"
                     % ", ".join(kosmayan))

    print()
    if any(k.startswith(ACILMADI) for k in kusur):
        print("KOSAMADI: dosya Storyline'da acilmadi, yani turun hicbir "
              "ayagi olculmedi.")
        for k in kusur:
            print(f"  - {k}")
        return KOSAMADI
    if kusur:
        print("KAPI KALDI:")
        for k in kusur:
            print(f"  - {k}")
        return 1
    print("kapi gecti: Storyline acti, kaydetti, ve puanlama zinciri "
          "turdan saglam cikti")
    print("KAPSAM: yapisal fark RAPOR -- Storyline'in mesru")
    print("        normallestirmeleri (ad, sira, bicim) kusur sayilmaz.")
    print("        Kapi yalnizca ZINCIRI savunuyor: kayit kaybi, ikinci")
    print("        quizLst, ve tur oncesi temiz olan zincirin bozulmasi.")
    return 0


if __name__ == "__main__":
    from kanarya_kilit import korumali
    raise SystemExit(korumali(main))
