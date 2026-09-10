"""Ogretim olcusu KAPI. Suitteki butun kapilar goruntuyu olcuyordu.

NICIN VAR. `tools/suit.py`nin on iki kapisinin hepsi kursun NASIL GORUNDUGUNU
soruyor: tasma, kontrast, tema, butunluk, cesitlilik. Ogretim olcusu
(`storyline_mcp/pedagogy.py`) 2026-08-28'de yazildi, `audit`ten donuyor,
builder her kurulumdan sonra kosturuyor -- ama HICBIR KAPI onu tabanla
karsilastirmiyordu.

Bedeli, tabanin kendi gerekcesinde yaziyor (`tools/ogretim_taban.json`):
"B'den sonra ayni promptla yeni bir kurs uretilip bu olcu tekrar kosulmadan,
degisikligin davranisi degistirdigi degil yalnizca kelime sayisini artirdigi
da mumkun kalir. Iyilesme VARSAYILMAZ, olculur." O tarihten sonra
`panel/ogretim.py`ye alti kural daha eklendi ve olcu bir daha kosulmadi.
Yani kural yerindeydi, uygulayani yoktu.

BU KAPI URETICIYI DEGIL, OLCUYU KORUR -- ve ayrim onemli. Ureticinin ogretim
kalitesi modelin ciktisina bagli; onu kapiya baglamak model cagrisi ister ve
kapilar model cagirmaz (`produced.py`: "model cagrisi YOK"). Kapinin
yapabilecegi ve bugun yapilmayan sey: olcunun kendisi sessizce olmesin.
Olcu olurse her kurs temiz gorunur ve kimse bilmez.

UC AYAK, ve ucuncusu olmadan ilk ikisi ATIL bir olcu tarafindan da gecilir
(`completeness` kapisinin ogrettigi ders):

  1. CIPA      Donmus dosyalarda sayilar birebir tutuyor mu. Kayan sayi ya
               olcunun ya dosyanin degistigini soyler.
  2. KANARYA   Bilinen bir ogretim kusuru EKILINCE olcu goruyor mu. Ekim
               "etkilesimli tetikleyiciyi GEZINMEYE cevir": olcu, kapsam
               cumlesinde "salt gezinme sayilmaz" diyor. Sayi dusmezse olcu
               yalnizca tetikleyici sayiyordur ve kapsam cumlesi yalandir.
  3. AYIRT     Iki bilinen kume ayrilmaya devam ediyor mu: etkilesim
               donorleri (ardisik okuma 0-1) ile anlatim kurslari
               (ardisik okuma 9+). Ortusmeye baslarlarsa olcu ayirt
               etmeyi birakmis demektir.

CIPA DOSYALARI URETICININ YAZMADIKLARI. `donors/*.story` disaridan gelen
gercek kurslar, `referans.story` dondurulmus el yapimi kurs. `uretilmis.story`
BILEREK DISARIDA: onu `produced.py` her kosuda yeniden uretiyor, yani sayilari
ureticiyle birlikte kayar ve cipa olamaz. Onun sayilari RAPOR olarak basiliyor.

TABAN 2026-08-28'DEKI DEGIL. O dosyadaki sekiz kursun yedisi artik diskte yok
ve kaynagi kovalanmadi (kapsami bilinmeyen sayiyi aramak yerine dondur ve
yeniden olc). Bu kapinin cipasi `tools/ogretim_cipa.json`da ve tarihi kendi
icinde yaziyor. Eski taban EVIDENCE olarak duruyor, silinmedi.

    python tools/ogretim_kapi.py              kapi
    python tools/ogretim_kapi.py --yenile     cipayi yeniden yaz
"""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from storyline_mcp import model, pedagogy
from storyline_mcp.package import StoryPackage

CIPA = ROOT / "tools" / "ogretim_cipa.json"
DONOR = ROOT / "donors"
REFERANS = ROOT.parent / "test" / "_referans" / "referans.story"
URETILMIS = ROOT.parent / "test" / "_canary" / "uretilmis.story"
KANARYA_DIZIN = ROOT.parent / "test" / "_canary"

# Ayirt etme bandi. Kayitli kanit (ogretim_taban.json "ayirt_etme_kanidi"):
# etkilesim donorleri ardisik=0-1, uretilen anlatim kurslari ardisik=10-19.
# Bugun yeniden olculdu: donorler 0-1, referans 9. Band ARADA, iki kumenin
# de disinda; daraltmak icin sebep degil, ortusmeyi yakalamak icin var.
AYIRT_TAVAN = 4      # donor bu sayiya kadar cikabilir
AYIRT_TABAN = 6      # anlatim kursu bunun altina inerse kumeler ortusuyor


def _ozet(yol: Path) -> dict:
    """Kapinin bakugu sayilar. Tam cikti degil -- KARARA GIREN alt kume.

    `tetikleyici_cesitliligi` BILEREK disarida: pedagogy.py onu "TANI, KAPI
    DEGIL" diye isaretliyor ve gerekcesi dogru (susleme hover'lari sayiyi
    yukseltir, bastan sona soru olan kursta dusuk cikar). Kapiya baglamak
    o notu yalanlamak olurdu.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        o = pedagogy.olc(StoryPackage(yol))
    a = o["ardisik_etkilesimsiz_slayt"]
    return {
        "ardisik": a["en_uzun"],
        "etkilesimli": a["etkilesimli_slayt"],
        "slayt": a["toplam_slayt"],
        "sorusuz_sahne": len(o["sorusuz_sahneler"]),
        "sonuc_slaydi": bool(o["sonuc_slaydi"]),
    }


def _cipa_dosyalari() -> list[tuple[str, Path]]:
    out = [(p.name, p) for p in sorted(DONOR.glob("*.story"))]
    if REFERANS.is_file():
        out.append((REFERANS.name, REFERANS))
    return out


# ------------------------------------------------------------------ kanarya

def _gezinmeye_cevir(pkg: StoryPackage) -> int:
    """Etkilesimli tetikleyicileri SALT GEZINMEYE cevirir. Kac tane, doner.

    EKIM OLCUNUN KENDI IDDIASINI HEDEFLIYOR. `pedagogy.KAPSAM` diyor ki bir
    tetikleyici ancak "ogrencinin girdisiyle baslayip SALT GEZINME olmayan"
    bir is yapiyorsa etkilesim sayilir. Ekim tam o yarim cumleyi sinar:
    event AYNEN kaliyor (girdi hala girdi), yalnizca action gezinmeye
    cevriliyor.

    Tetikleyici SILINSEYDI kanarya cok daha zayif olurdu: sayilarin dusmesi
    "olcu tetikleyici sayiyor" ile de aciklanirdi. Boyle, tetikleyici
    SAYISI sabit kaliyor ve yalnizca ANLAMI degisiyor -- sayi dusmezse
    kapsam cumlesi yalandir.
    """
    hedef = "jumpToNextSlide"
    sayac = 0
    for part in list(model.slide_index(pkg)):
        root = pkg.parse(part)
        degisti = False
        for trig_list in root.iter("trigLst"):
            for trig in trig_list:
                data = trig.find("data")
                if data is None:
                    continue
                sahte = {"event": data.get("event", ""),
                         "action": data.get("action", "")}
                if pedagogy._etkilesimli_mi(sahte):
                    data.set("action", hedef)
                    sayac += 1
                    degisti = True
        if degisti:
            pkg.replace_xml(part, root)
    return sayac


def kanarya() -> tuple[bool, str]:
    """Olcu, ekilen kusuru goruyor mu. IKI YONLU."""
    kaynak = None
    for ad, yol in _cipa_dosyalari():
        o = _ozet(yol)
        if o["etkilesimli"] >= 5:
            kaynak = (ad, yol, o)
            break
    if kaynak is None:
        return False, ("Kanarya kurulamadi: cipa dosyalarinin hicbirinde "
                       "5+ etkilesimli slayt yok, ekim olculemez.")
    ad, yol, temiz = kaynak
    KANARYA_DIZIN.mkdir(parents=True, exist_ok=True)
    bozuk_yol = KANARYA_DIZIN / "ogretim_kanarya.story"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        shutil.copy2(yol, bozuk_yol)
        pkg = StoryPackage(bozuk_yol)
        cevrilen = _gezinmeye_cevir(pkg)
        if cevrilen == 0:
            return False, ("Kanarya kurulamadi: %s icinde cevrilecek "
                           "etkilesimli tetikleyici yok." % ad)
        pkg.save(bozuk_yol, backup=False)
    bozuk = _ozet(bozuk_yol)

    if bozuk["etkilesimli"] >= temiz["etkilesimli"]:
        return False, ("KOR: %d etkilesimli tetikleyici GEZINMEYE cevrildi "
                       "ama etkilesimli slayt sayisi dusmedi (%d -> %d). "
                       "Olcu ya tetikleyici sayiyor ya da gezinme ayrimini "
                       "yapmiyor; kapsam cumlesi bunu iddia ediyor."
                       % (cevrilen, temiz["etkilesimli"], bozuk["etkilesimli"]))
    return True, ("CANLI: %s uzerinde %d tetikleyici gezinmeye cevrildi, "
                  "etkilesimli slayt %d -> %d dustu."
                  % (ad, cevrilen, temiz["etkilesimli"], bozuk["etkilesimli"]))


# -------------------------------------------------------------------- kapi

def yenile() -> int:
    kayit = {
        "alindi": "2026-09-06",
        "nicin": ("Ogretim olcusunun CIPASI. 2026-08-28 tabanindaki sekiz "
                  "kursun yedisi artik diskte yok; kaynagi kovalanmadi, "
                  "mevcut ve DONMUS dosyalar uzerinde yeniden olculdu. Eski "
                  "taban tools/ogretim_taban.json'da kanit olarak duruyor."),
        "kapsam": pedagogy.KAPSAM,
        "dosyalar": {ad: _ozet(yol) for ad, yol in _cipa_dosyalari()},
    }
    CIPA.write_text(json.dumps(kayit, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    print("cipa yazildi: %s (%d dosya)" % (CIPA.name, len(kayit["dosyalar"])))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yenile", action="store_true",
                    help="cipayi yeniden olcup yaz (KAPI DEGIL)")
    args = ap.parse_args()
    if args.yenile:
        return yenile()

    if not CIPA.is_file():
        print("Cipa yok: %s -- once --yenile ile alin." % CIPA)
        return 2
    kayit = json.loads(CIPA.read_text(encoding="utf-8"))
    beklenen = kayit["dosyalar"]

    kirmizi = []

    # --- 1. CIPA
    print("1. CIPA (donmus dosyalar, uretici bunlari yazmaz)")
    for ad, yol in _cipa_dosyalari():
        simdi = _ozet(yol)
        bek = beklenen.get(ad)
        if bek is None:
            print("   %-38s CIPADA YOK -- yeni dosya, --yenile gerekir" % ad[:38])
            kirmizi.append("%s cipada yok" % ad)
            continue
        fark = {k: (bek[k], simdi[k]) for k in simdi if bek.get(k) != simdi[k]}
        if fark:
            print("   %-38s KAYDI: %s" % (ad[:38], fark))
            kirmizi.append("%s kaydi" % ad)
        else:
            print("   %-38s ardsk=%-3d etkls=%-3d slayt=%-3d  tutuyor"
                  % (ad[:38], simdi["ardisik"], simdi["etkilesimli"],
                     simdi["slayt"]))
    eksik = [a for a in beklenen if a not in dict(_cipa_dosyalari())]
    for a in eksik:
        print("   %-38s DOSYA YOK -- cipa okunamiyor" % a[:38])
        kirmizi.append("%s dosyasi yok" % a)

    # --- 2. KANARYA
    print("\n2. KANARYA (ekilen kusuru goruyor mu)")
    tamam, mesaj = kanarya()
    print("   " + mesaj)
    if not tamam:
        kirmizi.append("kanarya")

    # --- 3. AYIRT ETME
    print("\n3. AYIRT ETME (iki kume ayri duruyor mu)")
    donorler = [(ad, _ozet(y)["ardisik"])
                for ad, y in _cipa_dosyalari() if (DONOR / ad).is_file()]
    anlatim = []
    if REFERANS.is_file():
        anlatim.append((REFERANS.name, _ozet(REFERANS)["ardisik"]))
    if donorler and anlatim:
        d_en = max(v for _a, v in donorler)
        a_en = min(v for _a, v in anlatim)
        print("   donor en yuksek ardisik = %d (tavan %d)" % (d_en, AYIRT_TAVAN))
        print("   anlatim en dusuk ardisik = %d (taban %d)" % (a_en, AYIRT_TABAN))
        if d_en > AYIRT_TAVAN or a_en < AYIRT_TABAN:
            print("   KUMELER ORTUSTU -- olcu ayirt etmeyi birakmis olabilir.")
            kirmizi.append("ayirt etme")
        else:
            print("   Kumeler ayri; olcu hala ayirt ediyor.")
    else:
        print("   Kume kurulamadi (dosya yok) -- AYIRT ETME OLCULMEDI.")
        kirmizi.append("ayirt etme kurulamadi")

    # --- RAPOR (kapi degil)
    print("\nRAPOR (kapi degil): ureticinin son ciktisi")
    if URETILMIS.is_file():
        try:
            u = _ozet(URETILMIS)
            print("   uretilmis.story  ardsk=%d etkls=%d slayt=%d sorusuz=%d "
                  "sonuc=%s" % (u["ardisik"], u["etkilesimli"], u["slayt"],
                                u["sorusuz_sahne"], u["sonuc_slaydi"]))
        except Exception as exc:
            print("   uretilmis.story okunamadi (%s) -- ATLANDI, kapi "
                  "dusmez." % str(exc)[:60])
    else:
        print("   uretilmis.story yok -- ATLANDI.")

    print()
    if kirmizi:
        print("KIRMIZI: " + ", ".join(kirmizi))
        return 1
    print("Ogretim olcusu ayakta: cipa tutuyor, ekilen kusuru goruyor, "
          "iki kumeyi ayiriyor.")
    return 0


if __name__ == "__main__":
    # KANARYA KILIDI. Kapilar `test/_canary/` icine SABIT adli dosyalar
    # yaziyor; iki kosu ayni anda ayni dosyaya yazarsa ikisi de yanlis
    # okur ve sonuc "kostu ve dustu" gibi gorunur. Gerekce ve olcum:
    # tools/kanarya_kilit.py.
    from kanarya_kilit import korumali
    raise SystemExit(korumali(main))
