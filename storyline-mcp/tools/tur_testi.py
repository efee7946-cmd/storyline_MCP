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
KAYDETMEDI = "KAYDETMEDI"

AYAKLAR = ayak.Defter(
    "acildi",
    "yazildi",
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


def _story_ozeti(yol: pathlib.Path) -> str | None:
    """story/story.xml'in sha256'si. Okunamazsa None -- kanit YOK sayilir."""
    import hashlib
    import zipfile
    try:
        with zipfile.ZipFile(yol) as z:
            return hashlib.sha256(z.read("story/story.xml")).hexdigest()
    except Exception:                                  # noqa: BLE001
        return None


def _yazmayi_bekle(yol: pathlib.Path, sure: float = 40.0) -> bool:
    """Dosyanin mtime'i degisip 3 sn DURULANA kadar bekler. Degistiyse True.

    Kirli olmayan projede baslik yildiz TASIMIYOR, yani `save_and_close`un
    "yildiz silinene kadar bekle" olcusu burada kullanilamaz. Dosya
    Storyline aciktayken okunamiyor ama stat'i aliniyor.
    """
    try:
        ilk = yol.stat().st_mtime_ns
    except OSError:
        return False
    son_degisim, onceki = None, ilk
    bitis = time.time() + sure
    while time.time() < bitis:
        time.sleep(0.5)
        try:
            simdi = yol.stat().st_mtime_ns
        except OSError:
            continue
        if simdi != onceki:
            son_degisim, onceki = time.time(), simdi
        elif son_degisim and time.time() - son_degisim >= 3.0:
            return True
    return son_degisim is not None


def tur(yol: pathlib.Path, *, ctrl_s: bool = True) -> list[str]:
    """Bir dosyayi ac-KAYDET-kapat ve NE DEGISTIGINI olc.

    KAYIT KANITLANMADAN HICBIR AYAK HUKUM VERMEZ (2026-09-16). Eskiden
    kaydetme `storyline_ctl.save_and_close`a birakiliyordu ve o Ctrl+S'i
    YALNIZCA KIRLI PENCEREDE gonderiyor -- urun icin dogru: panel
    kapanirken kullanicinin temiz projesini yeniden yazmamali. Ama temiz
    acilan bir projede Storyline dosyayi HIC YAZMIYORDU ve bu kapi yine de
    "Storyline acti, kaydetti" deyip gecti. Olculdu: sahne isareti turu,
    cikis 0, story.xml bayt bayt ayni. Kayit 3->3, quizLst 1->1, "yapisal
    degisiklik yok" -- hepsi YAZILMAMIS dosyada da dogru.

    DUSEN KAYITLI HUKUM: `banka_sorusu.py`nin "Storyline boyle bir kaydi
    KORUYOR" bulgusu tam bu imzaya ("yapi birebir korundu") dayaniyordu.
    Kural: gecmiste bir DEGISIKLIK raporlayan tur gecerli (degisiklik
    yazmanin kanitidir, `yks`teki `Quiz_Result` silinmesi gibi); "hicbir
    sey degismedi" diyen tur KANITSIZ.

    CARE TESTTE, URUNDE DEGIL. Ctrl+S burada KOSULSUZ gonderiliyor;
    `save_and_close`un `if dirty:`i ayakta. Urunu degistirmek her panel
    kapanisini bir yazma islemine cevirirdi.

    KANIT story.xml OZETI, ve yon dogru yanilir: gercek bir kayit bayt
    bayt ayni cikarsa sonuc KAYDETMEDI (bakilmadi) olur, asla "gecti".

    `ctrl_s=False` KANARYADIR (`--kanarya-kaydetme`): eski davranisi
    yeniden uretir ve KAYDETMEDI donmelidir -- donmuyorsa kanit ayagi
    ayirt etmiyor.
    """
    import open_test as ot
    import storyline_ctl as ctl

    kusur: list[str] = []
    for ek in (oturum.ANLIK_UZANTI, oturum.KUNYE_UZANTI):
        (yol.with_suffix(yol.suffix + ek)).unlink(missing_ok=True)
    oturum.anlik_goruntu(yol, etiket="tur testi")
    once = _zincir_hali(yol)
    once_ozet = _story_ozeti(yol)

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

    # KOSULSUZ KAYIT (gerekce: docstring).
    ctrl_s_durumu = "gonderilmedi (kanarya)"
    if ctrl_s:
        pencere = ctl.storyline_window()
        if pencere is None:
            ctrl_s_durumu = "pencere yok"
        elif not ctl._send_save(pencere[0]):
            ctrl_s_durumu = "GONDERILEMEDI (odak alinamadi)"
        else:
            ctrl_s_durumu = ("gonderildi, dosya yazildi"
                             if _yazmayi_bekle(yol) else
                             "gonderildi, mtime KIMILDAMADI")

    # GERCEK YOL. Onceden pencere BASLIGI geciliyordu; kapanis
    # dongusundeki `lock_state` var olmayan bir yolu soruyordu, yani
    # "dosya serbest" hemen dogruydu ve ozet yari yazilmis dosyadan
    # okunabilirdi.
    sonuc = ctl.save_and_close(yol)
    if not sonuc.get("closed"):
        kusur.append(f"{yol.name}: kaydet-kapat basarisiz "
                     f"({sonuc.get('reason','?')}) -- dosya yarim kalmis "
                     f"olabilir, fark okunmamali")
        return kusur

    sonra_ozet = _story_ozeti(yol)
    yazildi = once_ozet is not None and sonra_ozet not in (None, once_ozet)
    AYAKLAR.yaz("yazildi", ("EVET (story.xml ozeti degisti)" if yazildi else
                            "HAYIR (story.xml ayni)")
                           + f" -- Ctrl+S {ctrl_s_durumu}")
    if not yazildi:
        kusur.append(f"{KAYDETMEDI}: {yol.name} turdan story.xml bayt bayt "
                     f"AYNI cikti (Ctrl+S {ctrl_s_durumu}). Storyline dosyayi "
                     f"yazmadi; zincir ve yapisal ayaklar yazilmamis dosyada da "
                     f"dogru olurdu -- OLCULMEDI")
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
    ap.add_argument("--kanarya-kaydetme", action="store_true",
                    help="Ctrl+S GONDERME: eski davranis. KAYDETMEDI donmeli.")
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
        kusur += tur(kopya, ctrl_s=not args.kanarya_kaydetme)

    kosmayan = AYAKLAR.kosmayanlar()
    if kosmayan:
        kusur.append("BEYANDA DURAN AMA KOSMAYAN AYAK: %s"
                     % ", ".join(kosmayan))

    print()
    kaydetmedi = [k for k in kusur if k.startswith(KAYDETMEDI)]
    if args.kanarya_kaydetme:
        # KANARYA: eski davranis KAYDETMEDI uretmeli. Uretmiyorsa kanit
        # ayagi ayirt etmiyor -- ya da pencere kirli acildi ve
        # save_and_close kaydetti (o zaman kanarya KURULAMADI).
        if kaydetmedi:
            print("KANARYA YAKALANDI: Ctrl+S gonderilmeyince tur KAYDETMEDI "
                  "dondu -- kanit ayagi ayirt ediyor.")
            return 0
        print("KANARYA KACTI / KURULAMADI: Ctrl+S gonderilmedigi halde "
              "KAYDETMEDI donmedi.")
        for k in kusur:
            print(f"  - {k}")
        return 1
    if kaydetmedi:
        print("KOSAMADI: Storyline dosyayi YAZMADI, yani turun hicbir "
              "koruma ayagi olculmedi ('gecti' degil).")
        for k in kaydetmedi:
            print(f"  - {k}")
        return KOSAMADI
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
