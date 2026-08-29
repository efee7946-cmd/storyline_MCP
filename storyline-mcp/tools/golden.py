"""Doğrulanmış yığın davranışını dondurur, sonra aynı kaldığını sorar.

GÖREV 4 fit_row/fit_grid ekleyecek ve ortak bir soyutlama çıkaracak. O sırada
en kolay kaybedilen şey, bugünkü yığın vakalarının çıktısının aynı kalmasıdır
-- ve kaybedilirse g2'deki farkın kaynağı okunamaz hale gelir: yeni şablonlar
mı geldi, yoksa eski hesap mı kaydı, ayırt edilemez.

Kopya iki katmanı birden tutar, çünkü aralarındaki fark gerçek hataları
yakaladı:

  plan  : fit_choices ne söyledi (punto, boşluk, kutu, alan)
  disk  : dosyaya ne yazıldı (gerçek punto, gerçek aralık, son alt kenar)

Plan doğruyken yazma yanlış olabiliyor -- bu oturumda tam olarak öyle oldu,
slayt boyutu varsayımı ve düzen ezme ikisi de yazma katmanındaydı. Soyutlama
plan üretimini hiç değiştirmese bile, düzen ailesine göre dallanan yazma yolu
değişebilir; o yüzden ikisi de dondurulur.

    python tools/golden.py --record    tabanı kaydet (bilerek, nadiren)
    python tools/golden.py             taban hâlâ tutuyor mu
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from storyline_mcp import authoring, model, shapes
from storyline_mcp.package import StoryPackage

BASELINE = ROOT / "tools" / "golden_stack.json"
SOURCE = ROOT.parent / "test" / "0_duz_kopya.story"
WORK = ROOT.parent / "test" / "_canary" / "golden_probe.story"

LONG_THREE = [t[:40] for t in [
    "Parolayi hemen degistir ve yoneticiye bildir",
    "Once yoneticiye bildir sonra parolayi degistir",
    "Cihazi kapat ve bilgi islem birimini ara hemen",
]]
CASES = [
    ("kisa/kisa", "Ne yaparsin?", ["Evet", "Hayir", "Belki"]),
    ("kisa/uzun", "Ne yaparsin?", LONG_THREE),
    ("orta/uzun", "Sirket agina baglaniyken supheli bir e-posta aldin ve "
                  "icindeki baglantiya tikladin. Simdi ne yapmalisin?", LONG_THREE),
]

# CANLI DAL VAKASI. Ustteki uc vakanin UCU DE olu daldan geciyor
# (apply_choice_plan, uretimde 0/4) -- olculdu, hepsi 1920 uzayinda ve
# hepsi `plan`. Yani golden bugune kadar URETIMIN KULLANDIGI dali hic
# gormedi, ve dokuz sapmasinin tamami olu daldan geliyordu.
#
# Bu vaka bos bir projeden gecer: proje icinde soru sablonu olmadigi icin
# GOMULU TOHUM secilir, compose_question_frame kosar ve `framed` doner --
# uretimin gercekten kullandigi yol.
#
# COK SATIRLI, ve bu sart: kalibrasyon gecisi tek satirda -%20, cok satirda
# +%15-20 -- TERS yonlerde. Tek satirlik bir vaka tabani yesile dondurup
# yanlis yonde rahatlatirdi.
# TABAN GECMISI HAKKINDA: bu vakanin "oncesi" golden_stack.json'da YOK.
# Vaka, kalibrasyon gecisinden SONRA eklendi; eski sabitlerle olculen degerler
# oturum kaydinda duruyor (2026-08-17):
#
#     kok yuksekligi  %34.7 -> %54.5  (+57%)
#     sik yuksekligi  %16.3 ->  %9.0  (-45%)
#     ve eski sabitlerde SIK SIRASI TERSTI (sik2 %53.3, sik1 %71.2);
#     yeni sabitlerde duzeldi -- olu dal diff'inde gorunmeyen gercek bir
#     duzelme.
#
# Sabitleri geri sarip "once" kaydi uretmek SECILMEDI: yeni bir hata yuzeyi
# acardi ve karsilastirma zaten elde. Alti ay sonra bu vakanin taban gecmisi
# yokmus gibi gorunmesin diye buraya yazildi.
CANLI_KAYNAK = ROOT.parent / "test" / "bos.story"
CANLI = ("canli/cok-satir",
         "Musteri gerildiginde sesin tonu degisir, cumleler kisalir ve ayni "
         "sikayet farkli kelimelerle tekrar eder. Bu noktada ilk yapman "
         "gereken nedir?",
         ["Sakin bir tonla dinlemeye devam eder ve soyleneni ozetleyerek "
          "dogrular",
          "Ayni sertlikte karsilik verip kim oldugunu hatirlatir"])


def _quiet(fn, *args, **kwargs):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return fn(*args, **kwargs)


def _canli_olc() -> dict:
    """Canlı dalın ürettiği GEOMETRI. Plan yok, cerceve var.

    Olu dalda "plan" ile "disk" ayri ayri dondurulur, cunku ikisi ayrisabilir.
    Canli dalda plan hic uygulanmaz -- compose_question_frame kendi
    yerlesimini kurar. Dolayisiyla dondurulacak sey CIKTININ KENDISI: kok ve
    sik dikdortgenleri, ve slayt uzayi.
    """
    ad, kok, siklar = CANLI
    shutil.copy2(CANLI_KAYNAK, WORK)
    pkg = StoryPackage(WORK)
    picked = _quiet(authoring.pick_template_for_question, pkg, kok, siklar)
    made = _quiet(authoring.add_question, pkg, picked["template"], kok,
                  siklar, [0], eyebrow="Bolum 1")
    pkg.save(WORK, backup=False)
    again = StoryPackage(WORK)
    part = next(p for p, r in model.slide_index(again).items()
                if r.basename == made["new_slide"])
    root = again.parse(part)
    genislik, yukseklik = shapes.slide_size(root)
    _tag, intr = authoring._find_interaction(root)
    by = {el.get("g"): el for el in root.iter() if el.get("g")}
    guids = authoring._choice_shape_guids(intr)
    rects = [shapes.shape_rect(by[g]) for g in guids if g in by]
    rects = [r for r in rects if r]
    kok_guid = model.stem_shape_guid(root, guids)
    kok_r = shapes.shape_rect(by[kok_guid]) if kok_guid in by else None

    def yuzde(r):
        return [round(r[0] / genislik * 100, 2), round(r[1] / yukseklik * 100, 2),
                round(r[2] / genislik * 100, 2), round(r[3] / yukseklik * 100, 2)]

    return {ad: {
        "template": picked["template"],
        "dal": "cerceve" if made.get("framed") else "PLAN (beklenmedik)",
        "uzay": [genislik, yukseklik],
        "kok": yuzde(kok_r) if kok_r else None,
        # Yuzde olarak: uzay degisirse mutlak sayilar kayar ama oran kalir.
        "siklar": [yuzde(r) for r in rects],
    }}


def measure() -> dict:
    """Canlı dalın ürettiği geometriyi dondurur.

    Uc olu dal vakasi (kisa/kisa, kisa/uzun, orta/uzun) SILINDI: ucu de
    apply_choice_plan yolundan geciyordu ve o yol uretimde 0/4 kullaniliyordu.
    Dokuz sapmasinin tamami oradan geliyordu, yani golden bugune kadar
    URETIMIN KULLANDIGI dali hic gormemisti.
    """
    return _canli_olc()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--record", action="store_true",
                        help="mevcut davranisi taban olarak kaydet")
    args = parser.parse_args()

    if not SOURCE.is_file():
        print(f"Kaynak proje yok: {SOURCE}")
        return 2

    current = measure()
    if args.record:
        BASELINE.write_text(json.dumps(current, indent=2, ensure_ascii=False),
                            encoding="utf-8")
        print(f"Taban kaydedildi: {BASELINE.name}  ({len(current)} vaka)")
        # ESKI OZET SILINDI. `plan.size` / `plan.gap` / `disk.bottom` olu dal
        # vakalarinin anahtarlariydi; canli dal geometriyi DISKTEN okur ve
        # plan uretmez. Ozet artik olculen seyi yaziyor.
        for name, entry in current.items():
            print(f"  {name:<12} {entry['template']:<28} "
                  f"{entry['uzay'][0]:.0f}x{entry['uzay'][1]:.0f}  "
                  f"{len(entry['siklar'])} sik  dal={entry['dal']}")
        return 0

    if not BASELINE.is_file():
        print(f"Taban yok. Once: python tools/golden.py --record")
        return 2

    saved = json.loads(BASELINE.read_text(encoding="utf-8"))
    drift = []
    for name in sorted(set(saved) | set(current)):
        was, now = saved.get(name), current.get(name)
        if was is None or now is None:
            drift.append(f"{name}: vaka {'eklendi' if was is None else 'kayboldu'}")
            continue
        # ALANLAR SABIT LISTEDEN DEGIL, KAYITTAN. Burada bir donem
        # ("plan","frame","disk","template") yazili duruyordu -- olu dal
        # vakalarinin anahtarlari. Dal silinince liste hem KeyError verdi
        # hem de canli vakanin alanlarini (uzay, kok, siklar) HIC gormedi.
        # Sabit liste, kapsamin sessizce daralmasinin en ucuz yolu: kayda
        # alan eklenir, karsilastirma onu atlar, taban korumus gorunur.
        for alan in sorted(set(was) | set(now)):
            if was.get(alan) != now.get(alan):
                drift.append(f"{name}/{alan}: {was.get(alan)} -> {now.get(alan)}")

    print(f"{len(current)} vaka karsilastirildi.")
    if drift:
        print(f"\n{len(drift)} SAPMA:")
        for d in drift:
            print(f"  ! {d}")
        print("\nYigin davranisi degisti. Bilerek degistiyse --record ile "
              "tabani yenileyin; degilse soyutlama sirasinda kaydi.")
        return 1
    print("Yigin davranisi tabanla birebir ayni.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
