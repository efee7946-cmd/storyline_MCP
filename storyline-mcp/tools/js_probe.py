"""JS tetikleyicisinin bicimini Storyline'in kendisine sordur.

NEDEN BU ARAC VAR. `add_trigger` alti eylem yaziyor, JS yok. Yazma yolunu
acmak icin dort sey bilinmeli: `data/@action`, `data/@actSubType`,
`other/@js`'in kacis bicimi, ve bir uzunluk siniri olup olmadigi. Donor
havuzunda JS kullanan tek ornek yok (6 donor + 2 kanarya tarandi: 395 yerde
`js=""`, hepsi bos), yani bicim havuzdan okunamiyor.

A1'in dersi burada aynen gecerli: dogru bicim TAHMIN EDILMEZ, olculur.

IKI OLCUM, IKI AYRI KAPSAM -- karistirilmamali:

  --tarama   Storyline'in DLL'lerinde action adini arar. Storyline'i hic
             acmaz, saniyeler surer. YALNIZCA ADI verir; actSubType'i,
             kacis bicimini ve uzunluk sinirini VERMEZ.

  --tur      Dosya turu: prob dosyasini uretir, Storyline'da actirir,
             kirletir, kaydettirir, kapatir ve geri okur. Dordunu de olcer
             ama Storyline'in kurulu olmasini ve ~2 dakika ister.

HER IKI MODUN DA KANARYASI ICINDE.

Tarama kanaryasi: bilinen action adlari (donorlerden olculdu) ayni dosyada
bulunmuyorsa tarama yanlis yerde demektir. O durumda sonuc "BULUNAMADI"dir,
"yok" degil (K1).

Tur kanaryasi iki yonlu ve ikisi de gerekli (K2):

    K+  adjustVar          bilinen gecerli  -> HAYATTA KALMALI
    K-  zzzNotAnAction     bilinen sacma    -> DUSMELI

K+ dusuyorsa tur olcum yapamiyor. K- hayatta kaliyorsa Storyline XML'i oldugu
gibi round-trip ediyor demektir ve tur AYIRT EDICI DEGILDIR -- o durumda
"executeJavaScript hayatta kaldi" cumlesi hicbir sey soylemez. Iki kanarya da
beklendigi gibi davranmadan hicbir verdikt basilmaz.

TURUN KOSTUGU AYRICA KANITLANIR (K3). Kalibrasyon deneyi bir kez gecersiz
koctu: dosya acildi, save_and_close cagrildi, hicbir bayt degismedi ve sonuc
"Storyline yeniden boyutlandirmiyor" diye okundu -- oysa Storyline hic
yazmamisti. Bir dosyayi acmak onu kirletmez. Bu yuzden `make_dirty` cagrilir
ve tur sonrasi sha256 karsilastirilir; hash ayni ise sonuc "TUR KOSMADI"dir,
"degismedi" degil.

KACIS: Python'un ElementTree'si attribute icindeki `\n`'i `&#10;` olarak
kacirir ve geri okurken korur (olculdu). Yani YAZMA tarafi guvenli. Acik olan
soru Storyline'in o `&#10;`'u koruyup korumadigi -- XML attribute-value
normalizasyonu satir sonlarini bosluga cevirebilir, ve tek satira inen bir
kodda `//` yorumu geri kalan her seyi yer. P4 tam bunu olcer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "panel"))
sys.path.insert(0, str(HERE))

from storyline_mcp import logic, model, shapes  # noqa: E402
from storyline_mcp.package import StoryPackage  # noqa: E402

TEMEL = ROOT / "test" / "_canary" / "canary_saglam.story"
CIKTI_DIR = ROOT / "test" / "_js"
PROB = CIKTI_DIR / "probe.story"
PROB_NEG = CIKTI_DIR / "probe_neg.story"
KAYIT = CIKTI_DIR / "probe_kayit.json"

DLL_DIR = Path(r"C:\Program Files\Articulate\360\Storyline 64-bit")

# Donorlerden olculdu (6 donor + 2 kanarya). Tarama kanaryasi bunlar.
BILINEN = ["showSubSlide", "hideSubSlide", "changeShapeState", "jumpToSlide",
           "jumpToScene", "adjustVar", "submitInteraction"]
ADAYLAR = ["executeJavaScript", "execJS", "executeJS", "runJavaScript",
           "execScript", "jsExecute"]

BASIT = "/*JSPROBE*/ var p = GetPlayer();"

# `&`, `<`, `"`, `'`, satir sonu ve Turkce karakter bir arada. Satir sonu
# bilerek bir `//` yorumundan SONRA geliyor: normalize edilirse kodun geri
# kalani yorum icinde kalir ve fark okunur olur.
ZORLU = (
    "/*JSPROBE*/ // ilk satir yorumu -- normalize edilirse asagisi yok olur\n"
    'var a = 1 & 2;\n'
    'if (a < 3 && a > 0) { var s = "cift tirnak"; var t = \'tek tirnak\'; }\n'
    'var tr = "cesitli ogeler: sirali, dogru, uzum";\n'
)

# IKI DOSYA, ve bolunme kasitli. Sacma action'in TUM DOSYAYI dusurme
# ihtimali var; ayni dosyada dursaydi P1-P4 hakkinda hicbir sey ogrenemezdik
# -- "kusur uremiyor" ile "kusuru olcecek vakayi hic kurmadim" ayni gorunur
# (K16). Negatif kanarya kendi dosyasinda, ve yanina bir K+ kopyasi aliyor ki
# o dosyanin actigi da ayrica okunabilsin.
GRUPLAR = {
    "ana": (PROB, [
        ("P1", "executeJavaScript", "spec", BASIT),
        ("P2", "executeJavaScript", "me", BASIT),
        ("P3", "executeJavaScript", None, BASIT),   # actSubType ozniteligi silinir
        ("P4", "executeJavaScript", "spec", ZORLU),
        ("KA", "adjustVar", "spec", None),          # kanarya +: hayatta kalmali
    ]),
    "neg": (PROB_NEG, [
        ("KA2", "adjustVar", "spec", None),         # bu dosyanin kendi K+'si
        ("KE", "zzzNotAnAction", "spec", None),     # kanarya -: dusmeli
    ]),
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


# ------------------------------------------------------------------ tarama


def tarama() -> int:
    """DLL'lerde action adini ara. Storyline acilmaz."""
    if not DLL_DIR.is_dir():
        print(f"Storyline kurulumu bulunamadi: {DLL_DIR}")
        print("Sonuc: OLCULEMEDI (yok degil).")
        return 2

    hedefler = [p for p in DLL_DIR.rglob("*.dll")
                if p.stat().st_size < 120 * 1024 * 1024]

    def ara(blob: bytes, ad: str) -> str | None:
        for etiket, kalip in (("utf8", ad.encode("utf-8")),
                              ("utf16", ad.encode("utf-16-le"))):
            if blob.find(kalip) >= 0:
                return etiket
        return None

    kanarya_gecti = False
    bulgular: dict[str, list[str]] = {}

    for p in hedefler:
        try:
            blob = p.read_bytes()
        except OSError:
            continue
        bilinen_hit = [a for a in BILINEN if ara(blob, a)]
        if not bilinen_hit:
            continue                      # kanaryasi olmayan dosya sayilmaz
        kanarya_gecti = True
        aday_hit = [a for a in ADAYLAR if ara(blob, a)]
        if aday_hit:
            bulgular.setdefault(p.name, []).extend(aday_hit)
        print(f"  {p.name}")
        print(f"      bilinen: {len(bilinen_hit)}/{len(BILINEN)}  "
              f"aday: {', '.join(aday_hit) or '-'}")

    print()
    if not kanarya_gecti:
        print("KANARYA DUSTU: bilinen action adlari hicbir DLL'de bulunamadi.")
        print("Tarama yanlis yerde. Sonuc: BULUNAMADI (yok degil).")
        return 1

    sayim: dict[str, int] = {}
    for adlar in bulgular.values():
        for a in adlar:
            sayim[a] = sayim.get(a, 0) + 1

    print("KANARYA GECTI: bilinen adlar bulundu, tarama dogru yerde.")
    if not sayim:
        print("Aday hicbir yerde gecmiyor. Sonuc: BULUNAMADI.")
        return 1
    for ad, n in sorted(sayim.items(), key=lambda kv: -kv[1]):
        print(f"  {ad:20s} {n} dosyada")
    print()
    print("KAPSAM: tarama yalnizca ADI verir. actSubType, kacis bicimi ve")
    print("        uzunluk siniri olculmedi -- onlar icin --tur gerekir.")
    return 0


# ----------------------------------------------------------------- hazirla


def hazirla() -> int:
    """Iki prob dosyasi uret: ana (P1-P4 + K+) ve neg (K+ kopyasi + K-)."""
    if not TEMEL.is_file():
        print(f"Temel dosya yok: {TEMEL}")
        return 2
    CIKTI_DIR.mkdir(parents=True, exist_ok=True)

    kayit = {"temel_sha": _sha(TEMEL), "gruplar": {}}

    for grup, (hedef, varyantlar) in GRUPLAR.items():
        shutil.copy2(TEMEL, hedef)
        pkg = StoryPackage(hedef)
        parts = pkg.slide_parts
        if not parts:
            print("Temel dosyada slayt yok.")
            return 2

        kg: dict = {"dosya": str(hedef), "varyantlar": {}}
        for i, (etiket, action, alt, js) in enumerate(varyantlar):
            part = parts[i % len(parts)]

            # K+ PROJENIN KENDI YOLUNDAN yazilir, elle degil. Ilk surumde
            # `_blank_trigger` ile elle yazilmisti ve `other/@varG` bos
            # kaliyordu -- yani "bilinen gecerli" olmasi gereken kanarya
            # GECERSIZ bir adjustVar uretiyordu ve Storyline dosyanin
            # TAMAMINI acmiyordu. Butun varyantlar onun yuzunden olculemedi
            # ve cikti "prob dosyasi reddedildi" diye okundu.
            # Kanaryanin kendisi yalanci cikti (K2), ve ikiye bolme testi
            # ayirdi: tek JS trigger'li dosya aciliyor, tek gecerli
            # adjustVar'li dosya da aciliyor.
            if action == "adjustVar":
                ad = f"ProbVar{etiket}"
                logic.add_variable(pkg, ad, "num", 0)
                sonuc = logic.add_trigger(
                    pkg, PurePosixPath(part).name, "adjust_variable",
                    event="OnStart", variable=ad, operation="add", value=1)
                kg["varyantlar"][etiket] = {
                    "guid": sonuc.get("trigger") or sonuc.get("guid"),
                    "part": part, "action": "adjustVar", "actSubType": alt,
                    "js": None, "not": "projenin kendi yazma yolundan"}
                continue

            root = pkg.parse(part)
            trig = logic._blank_trigger()
            trig.set("name", f"JSPROBE_{etiket}")
            data = trig.find("data")
            data.set("event", "OnStart")
            data.set("action", action)
            if alt is None:
                data.attrib.pop("actSubType", None)
            else:
                data.set("actSubType", alt)
            if js is not None:
                data.find("other").set("js", js)

            trig_list = root.find("trigLst")
            if trig_list is None:
                trig_list = shapes.insert_in_order(root, ET.Element("trigLst"))
            trig_list.append(trig)
            pkg.replace_xml(part, root)

            kg["varyantlar"][etiket] = {
                "guid": trig.get("g"), "part": part, "action": action,
                "actSubType": alt, "js": js,
            }

        pkg.save(hedef, backup=False)
        kg["yazim_sha"] = _sha(hedef)
        kayit["gruplar"][grup] = kg
        print(f"{grup}: {hedef.name}  varyant {len(varyantlar)}  "
              f"slayt {len(parts)}  sha {kg['yazim_sha']}")

    KAYIT.write_text(json.dumps(kayit, indent=2), encoding="utf-8")
    return 0


# --------------------------------------------------------------------- tur


def _ac(hedef: Path, bekle: float = 150.0) -> bool:
    """Storyline'i DOGRUDAN exe ile ac; shell yolu (`start`) kullanilmaz.

    Bu ayrim `open_test.py`'de olculmus ve gerekcesi orada yazili: Articulate
    360 Desktop App calisirken `start` yolu dosyayi ONA verir, hicbir pencere
    acilmaz, ve her dosya REDDEDILMIS gibi gorunur. Ilk turumuz tam bu tuzaga
    dustu -- dort Storyline penceresi acildi, hicbiri dosya yuklemedi, ve cikti
    "Storyline dosyayi ALMADI" dedi. O cumle dogruydu ama sebebi yanlis okunurdu.

    `storyline_ctl.reopen` HALA shell yolunu kullaniyor. Ders bir dosyada
    ogrenilmis ama komsusuna tasinmamis; panel de ayni tuzaga acik.
    """
    import open_test
    import storyline_ctl as sc

    open_test.launch(hedef)
    son = time.time() + bekle
    while time.time() < son:
        if sc.holds(hedef):
            return True
        time.sleep(1.0)
    return False


def _tur_bir(sc, grup: str, hedef: Path, kg: dict) -> dict:
    """Tek dosyanin turu. Sonucu kg icine yazar ve dondurur."""
    once = _sha(hedef)
    kg["tur_oncesi_sha"] = once
    print(f"\n[{grup}] {hedef.name}  sha oncesi {once}")

    if not _ac(hedef):
        # Bu bir hata degil, BULGU olabilir: Storyline dosyayi reddetmis
        # olabilir. Ayirmak icin `holds` sorulur -- reddedilen dosya serbest
        # kalir. Yine de "acilmadi" ile "olcum yok" ayri raporlanir (K1).
        kg["acildi"] = False
        kg["tur_sonrasi_sha"] = once
        print("  Storyline dosyayi ALMADI -> tur kosmadi (ya da dosya reddedildi).")
        return kg

    kg["acildi"] = True
    print("  acildi; belge kirletiliyor...")
    kg["kirletme"] = str(sc.make_dirty())
    print(f"    {kg['kirletme']}")

    kapandi = sc.save_and_close(hedef)
    kg["kapanis"] = str(kapandi)
    print(f"  kapanis: {kapandi}")
    if not kapandi.get("closed"):
        kg["tur_sonrasi_sha"] = once
        print("  Storyline kapanmadi; dosyaya dokunulmadi -> TUR KOSMADI.")
        return kg

    sonra = _sha(hedef)
    kg["tur_sonrasi_sha"] = sonra
    print(f"  sha sonrasi {sonra}  ->  "
          f"{'YAZILDI' if sonra != once else 'DEGISMEDI (tur kosmadi)'}")
    return kg


def tur() -> int:
    """Her prob dosyasini Storyline'a actir, kirlet, kaydettir, kapat."""
    import storyline_ctl as sc

    if not KAYIT.is_file():
        print("Kayit yok. Once --hazirla.")
        return 2
    kayit = json.loads(KAYIT.read_text(encoding="utf-8"))

    import open_test
    print("Acik Storyline pencereleri temizleniyor (once nazik yol)...")
    print(f"  {open_test.force_close()}")

    for grup, (hedef, _) in GRUPLAR.items():
        kg = kayit["gruplar"].get(grup)
        if kg is None or not hedef.is_file():
            print(f"[{grup}] dosya yok, atlandi.")
            continue
        if _sha(hedef) != kg.get("yazim_sha"):
            print(f"[{grup}] UYARI: dosya yazimdan sonra degismis.")
        _tur_bir(sc, grup, hedef, kg)
        KAYIT.write_text(json.dumps(kayit, indent=2), encoding="utf-8")

    kostu = [g for g, kg in kayit["gruplar"].items()
             if kg.get("tur_sonrasi_sha") != kg.get("tur_oncesi_sha")]
    print(f"\nTur kosan dosya: {', '.join(kostu) if kostu else 'HICBIRI'}")
    return 0 if kostu else 1


# --------------------------------------------------------------------- oku


def _kalanlar(hedef: Path) -> dict[str, dict]:
    pkg = StoryPackage(hedef)
    out: dict[str, dict] = {}
    for part in pkg.slide_parts:
        root = pkg.parse(part)
        for trig in root.iter("trig"):
            data = trig.find("data")
            if data is None:
                continue
            other = data.find("other")
            out[trig.get("g")] = {
                "name": trig.get("name", ""),
                "action": data.get("action", ""),
                "actSubType": data.get("actSubType"),
                "js": (other.get("js") if other is not None else None),
            }
    return out


def oku() -> int:
    """Prob dosyalarini geri oku ve iki yonlu kanaryayi degerlendir."""
    if not KAYIT.is_file():
        print("Kayit yok. Once --hazirla.")
        return 2
    kayit = json.loads(KAYIT.read_text(encoding="utf-8"))

    sonuc: dict[str, dict | None] = {}
    kostu: dict[str, bool] = {}

    for grup, (hedef, varyantlar) in GRUPLAR.items():
        kg = kayit["gruplar"].get(grup, {})
        kostu[grup] = bool(kg.get("tur_sonrasi_sha")
                           and kg.get("tur_oncesi_sha") != kg.get("tur_sonrasi_sha"))
        print(f"\n=== GRUP {grup} ({hedef.name}) ===")
        print(f"  acildi: {kg.get('acildi')}   tur kostu: {kostu[grup]}")
        if not hedef.is_file():
            print("  dosya yok.")
            for etiket, *_ in varyantlar:
                sonuc[etiket] = None
            continue

        kalan = _kalanlar(hedef)
        for etiket, action, alt, js in varyantlar:
            beklenen = kg.get("varyantlar", {}).get(etiket, {})
            bulunan = kalan.get(beklenen.get("guid"))
            sonuc[etiket] = bulunan
            print(f"\n  {etiket}  {action}  actSubType={alt!r}  -> "
                  f"{'HAYATTA' if bulunan else 'DUSTU'}")
            if not bulunan:
                continue
            print(f"      action     : {bulunan['action']!r}")
            print(f"      actSubType : {bulunan['actSubType']!r}")
            if js is None:
                continue
            geri = bulunan["js"] or ""
            print(f"      js uzunluk : yazilan {len(js)} / okunan {len(geri)}")
            print(f"      satir sonu : {'KORUNDU' if chr(10) in geri else 'KAYIP'}")
            eksik = [k for k in ("&", "<", '"', "'") if k in js and k not in geri]
            print(f"      kayip karakter: {eksik or '-'}")
            if geri != js:
                print(f"      METIN DEGISTI. okunan: {geri[:140]!r}")

    print("\n=== KANARYA ===")
    ka_ok = sonuc.get("KA") is not None
    neg_acildi = kayit["gruplar"].get("neg", {}).get("acildi")
    ka2_ok = sonuc.get("KA2") is not None
    ke_dustu = sonuc.get("KE") is None
    print(f"  K+  adjustVar, ana dosya (hayatta kalmali) : "
          f"{'GECTI' if ka_ok else 'DUSTU'}")
    print(f"  K+  adjustVar, neg dosya                   : "
          f"{'HAYATTA' if ka2_ok else 'DUSTU'}")
    print(f"  K-  zzzNotAnAction (dusmeli)               : "
          f"{'GECTI' if ke_dustu else 'HAYATTA KALDI'}")
    if neg_acildi is False:
        print("      not: neg dosyasi hic acilmadi -- Storyline onu reddetmis")
        print("      olabilir. Bu da ayirt edicilik lehine bir isaret, ama")
        print("      'reddetti' ile 'tur kosmadi' bu turda AYRILAMAZ.")

    print("\n=== VERDIKT ===")
    if not kostu.get("ana"):
        print("  OLCUM YOK: ana dosyada tur kosmadi (hash degismedi).")
        print("  'Hayatta kaldi' cumlesi bu durumda hicbir sey soylemez.")
        return 1
    if not ka_ok:
        print("  OLCUM YOK: K+ dustu. Tur gecerli bir trigger'i bile")
        print("  koruyamiyor; varyant sonuclari okunamaz.")
        return 1
    if not kostu.get("neg"):
        print("  KISMI: neg dosyasinda tur kosmadi, yani K- degerlendirilemedi.")
        print("  executeJavaScript sonuclari okunabilir ama 'hayatta kalmak'")
        print("  gecerlilik kaniti SAYILMAZ -- ayirt edicilik olculmedi (K2).")
    elif not ke_dustu:
        print("  OLCUM YOK: K- hayatta kaldi. Storyline XML'i oldugu gibi")
        print("  round-trip ediyor -- tur AYIRT EDICI DEGIL. Bir action adinin")
        print("  hayatta kalmasi onun gecerli oldugunu GOSTERMEZ.")
        return 1
    else:
        print("  Iki yonlu kanarya gecti. Varyant sonuclari okunabilir.")

    js_kalan = [e for e in ("P1", "P2", "P3", "P4") if sonuc.get(e)]
    if js_kalan:
        print(f"\n  executeJavaScript hayatta kalan: {', '.join(js_kalan)}")
        for e in js_kalan:
            print(f"     {e}: action -> {sonuc[e]['action']!r}   "
                  f"actSubType -> {sonuc[e]['actSubType']!r}")
    else:
        print("\n  executeJavaScript varyantlarinin hepsi dustu.")

    print()
    print("  KAPSAM: bu tur BICIMI olcer -- Storyline dosyayi kabul etti mi,")
    print("          neyi korudu. Kodun CALISTIGINI gostermez; o yalnizca")
    print("          publish ciktisinda gorulur.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tarama", action="store_true", help="DLL taramasi (Storyline acilmaz)")
    ap.add_argument("--hazirla", action="store_true", help="prob dosyasini uret")
    ap.add_argument("--tur", action="store_true", help="Storyline'da ac-kaydet-kapat")
    ap.add_argument("--oku", action="store_true", help="prob dosyasini geri oku")
    a = ap.parse_args()

    if not any((a.tarama, a.hazirla, a.tur, a.oku)):
        ap.print_help()
        return 2

    kod = 0
    if a.tarama:
        print("--- TARAMA ---")
        kod |= tarama()
    if a.hazirla:
        print("--- HAZIRLA ---")
        kod |= hazirla()
    if a.tur:
        print("--- TUR ---")
        kod |= tur()
    if a.oku:
        print("--- OKU ---")
        kod |= oku()
    return kod


if __name__ == "__main__":
    raise SystemExit(main())
