"""1920 SAHNE turu: punto başına birim, sahne boyutundan bağımsız mı?

SONUC (2026-08-17) -- H_KANONIK DOGRULANDI, H_SAHNE ELENDI:

                    13pt birim/punto   21pt birim/punto
      720 sahne          1.817              1.810
     1920 sahne          3.577              3.536
     --------------------------------------------------
     R                   1.969              1.954    ->  2.00

Dort sayimin dordu de 6 satir. Iki punto %0.8 icinde uyusuyor: iliski
dogrusal, punto-bagimliligi YOK -- eski tablodaki aciklanmamis 3.28 -> 3.13
kaymasi da boylece kapandi, o kayma yanlis zeminin artefaktiymis.

`shapes.Space.v` artik `slide_h / 540`, `.h` artik `slide_w / 720`; SAHNE
matematige GIRMIYOR. Sonucu: yuzdeler uzaydan bagimsiz hale geldi ve
`check_diagnoses`'in uzun/3 regresyonu KENDILIGINDEN kapandi -- karar
kuralinin H_kanonik dalinda onceden yazildigi gibi.

Yatay eksen bu turda OLCULMEDI (etiketler sarmadi); simetriyle turetildi ve
kodda oyle isaretli.

--- turun kurulusu (kayit icin) ---


MEASURED_STAGE bugun tek uzay tutuyor: 720x540. Butun kalibrasyon kareleri
orada alindi. `shapes.Space.v` tutarli bir deck'te 1.0 doner -- yani "punto
basina birim, sahne boyutundan BAGIMSIZ" varsayilir. O varsayim BASKA BIR
SAHNEDE HIC OLCULMEDI.

MEVCUT VERI IKI HIPOTEZI AYIRAMIYOR, ve turun butun sebebi bu:

    H_sahne      carpan = slide_h / stage_h      <- bugunku kod
    H_kanonik    carpan = slide_h / 540          <- punto 540'lik bir tasarim
                                                    yuksekligine gore sabit

2026-08-17 kare turunda olculen tek vaka 1920x1080 slayt / 720x540 sahne idi
ve orada IKISI DE 2.000 veriyor (1080/540 = 1080/540). Yani o olcum ikisini
AYIRAMAZ; dogruladigi sey yalnizca "carpan 2.0", hangi formulden geldigi
degil. Ayrimin gorundugu tek yer TUTARLI bir 1920 deck:

    H_sahne      1080/1080 = 1.000
    H_kanonik    1080/540  = 2.000

Iki kat fark. Ayni fikstuur iki sahnede kosarsa oran DOGRUDAN okunur.

NEDEN IKI GERCEK PROJE, sentetik yeniden boyutlandirma DEGIL. `set_story_size`
yalnizca story.xml'deki <sz>'i degistirir; slaytlarin kendi <sldSz>'i yerinde
kalir ve ortaya semantigi TAHMINE dayali bir karisik deck cikar. Bu turun
sorusu zaten "karisik uzayda ne olur" degil -- o olculdu. Soru "TUTARLI bir
1920 deck'te punto kac birim". O yuzden ikisi de Storyline'in kendi urettigi,
kendi icinde tutarli projeler:

    720  sahne : bos.story          (sahne 720x540, 14 slaydin 14'u 720x540)
    1920 sahne : 0_duz_kopya.story  (sahne 1920x1080, 27 slaydin 27'si ayni)

referans.story KULLANILMADI ve sebebi kayda deger: o KARISIK bir deck (29
slayt 720, 5 slayt 1920) ve MEASURED_*SCALE'in sahte 2.667/2.990'i tam olarak
oradaki 1920 slaytlardan turetilmisti. Ayni kaynaga geri donmek, curutulen
olcumu ayni zeminde tekrarlamak olurdu.

SAHNE story.xml'DEN DOGRULANIR, slayt duzeyinden DEGIL. Bu turun butun
anlami o ayrimda; arac kosmadan once ikisini de basar ve uyusmazsa durur.

AYNI TURDA, IKI SAHNE. Ayri turlarda olcmek MEASURE_LEADING'i referans almayi
zorunlu kilar; ayni turda olcmek ORANI dogrudan verir ve "iki tur arasinda
baska ne degisti" sorusunu kapatir.

IKI PUNTO, cunku tek punto sahne carpanini verir ama DOGRUSALLIGI vermez.
3.28 -> 3.13 kaymasi (eski, sahte tabloda) hala aciklanmadi ve ilk kez temiz
zeminde sinanacak.

SERT SATIR SONU, SARMA YOK. Olculen sey yalnizca satir ADIMI. Beklenen satir
sayisi GIRDI SPESIFIKASYONUNDAN gelir (kac tane \\n yazildigi), modelden
degil; kare_satir.py uyusmazsa hicbir sey turetmez.

KARAR KURALI -- KARELERE BAKILMADAN YAZILDI:

  R = (1920 sahnede birim/punto) / (720 sahnede birim/punto)

  R ~ 1.00  ->  H_SAHNE DOGRULANDI. Bugunku kod dogru; MEASURED_STAGE ikinci
                uzayla genisler ve `_text_height`'in uyarisi 1920 icin kalkar.
                check_diagnoses'in uzun/3 vakasi GERCEKTEN 'plan' olmali ve
                fikstuur metni (eski, sahte 2.99'a gore ayarlanmis) uzatilir.

  R ~ 2.00  ->  H_KANONIK DOGRULANDI. `Space.v` yanlis: bolen stage_h degil
                sabit 540 olmali (yatayda 720). Duzeltme tek satir, ama
                karisik-uzay olcumunu BOZMAZ -- o vakada ikisi zaten esitti.
                check_diagnoses'in regresyonu kendiliginden kapanir.

  R baska bir sayi  ->  Ikisi de yanlis. O zaman R'nin kendisi olculmus bir
                olgudur ve 1.121 ARTAKALANININ YERI BELLI OLUR: bugune kadar
                hep yanlis bir carpanin (2.667) uzerinde duruyordu ve
                mekanizmasi hic sorulamadi. Ilk kez temiz zeminde.
                UYARI: R'yi tabloya SABIT olarak yazma -- iki nokta bir
                fonksiyon vermez. Once mekanizma sorulur.

  13pt ve 21pt FARKLI R veriyorsa  ->  Iliski saf olcek degil, puntoya
                bagli. O zaman tek carpanli her formul (ucu de) yanlis ve
                MEASURE_LEADING'in kendisi punto-bagimli olabilir.

  Herhangi bir karede sayilan satir 6 degilse  ->  TUR GECERSIZ. Sert satir
                sonu sayisi girdinin TANIMI; sapma sayacin ya da fikstuurun
                bozuk oldugunu soyler, sahnenin degil.

BEDAVA IKINCI OLCUM: her karede slayt bandinin en/boy orani. 720 -> 4:3,
1920 -> 16:9 beklenir. Uymuyorsa sahne okumasi yanlis ve tur oradan durur.

    python tools/goz_sahne.py
"""

from __future__ import annotations

import shutil
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from storyline_mcp import compose, model, shapes
from storyline_mcp.authoring import _apply_text
from storyline_mcp.package import StoryPackage

# (etiket, kaynak, BEKLENEN sahne)
KAYNAKLAR = [
    ("720",  ROOT.parent / "test" / "bos.story",         (720.0, 540.0)),
    ("1920", ROOT.parent / "test" / "0_duz_kopya.story", (1920.0, 1080.0)),
]
CIKTI = ROOT.parent / "test" / "_referans" / "SAHNE{}.story"

PUNTOLAR = (13.0, 21.0)
SATIR = 6

# GORUNUR BANT. 4:3 slayt oynaticida 621 px yuksek cizilir ve karenin alt
# 52 birimi kesilir (olculdu); 16:9 tamami girer. Kutular her iki sahnede de
# slaydin %80'inin ustunde bitiyor -- sinir varsayilmiyor, hesaplaniyor.
ALT_SINIR_YUZDE = 80.0

# Fikstür zemininin İMZA rengi. Storyline'in kendi arayuzunde ve hata
# diyalogunda gecmeyecek kadar ayirt edici olmali; kare guard'i bunu ARAR ve
# bulamazsa dosya yazmaz. Beyaz OLAMAZ: cokme diyalogu da beyazdir ve ilk
# turda guard tam olarak bu yuzden cokmeyi "slayt" sandi.
IMZA = "#E8F0D8"


def metin(p: float) -> str:
    """Altı SERT satır. Sarma devreye girmez; 6, girdinin TANIMI."""
    return "\n".join(f"{int(p)}pt-{i}" for i in range(1, SATIR + 1))


def kur(etiket: str, kaynak: Path, beklenen: tuple[float, float]) -> dict | None:
    out = Path(str(CIKTI).format(etiket))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        shutil.copy2(kaynak, out)
        pkg = StoryPackage(out)

        # SAHNE story.xml'DEN, ve KOSMADAN ONCE dogrulanir.
        sahne = shapes.stage_size(pkg)
        if abs(sahne[0] - beklenen[0]) > 1 or abs(sahne[1] - beklenen[1]) > 1:
            print(f"  {etiket}: sahne {sahne[0]:.0f}x{sahne[1]:.0f}, "
                  f"beklenen {beklenen[0]:.0f}x{beklenen[1]:.0f} — TUR GECERSIZ")
            return None

        part, ref = next(iter(model.slide_index(pkg).items()))
        root = pkg.parse(part)
        sw, sh = shapes.slide_size(root)
        # TUTARLILIK: slayt kendi sahnesiyle ayni olmali, yoksa bu tur
        # karisik uzay olcuyor demektir ve soru o degil.
        if abs(sw - sahne[0]) > 1 or abs(sh - sahne[1]) > 1:
            print(f"  {etiket}: slayt {sw:.0f}x{sh:.0f} sahneden farkli — "
                  f"KARISIK deck, TUR GECERSIZ")
            return None

        compose.clear_slide(root)
        zemin = shapes.clone_shape(shapes.find_seed(pkg, "rect")[0], name="Zemin")
        shapes.set_shape_slide_size(zemin, sw, sh)
        shapes.set_loc(zemin, 0, 0, sw, sh)
        shapes.set_fill(zemin, IMZA)
        shapes.add_shape(root, zemin, to_back=True)
        _apply_text(root, zemin, "")
        pkg.replace_xml(part, root)

        # ARALIK COMERT ve MODELDEN TURETILMIYOR. Model %100 yanilsa bile
        # kutular bindirmez. Araligi modelin tahminine gore vermek,
        # olcelecek seyi olcume sokmak olurdu.
        for i, punto in enumerate(PUNTOLAR):
            x = (6 + i * 46) / 100 * sw
            for ad, y_pct, icerik, renk, boy in (
                    (f"E_{int(punto)}", 4.0,
                     f"{int(punto)}pt, {SATIR} sert satir", "#B00000", 11.0),
                    (f"K_{int(punto)}", 10.0, metin(punto), "#000000", punto)):
                r2 = pkg.parse(part)
                box = shapes.clone_shape(shapes.find_seed(pkg, "textBox")[0],
                                         name=ad)
                shapes.set_shape_slide_size(box, sw, sh)
                y = y_pct / 100 * sh
                shapes.set_loc(box, x, y, x + 0.40 * sw,
                               y + (ALT_SINIR_YUZDE - y_pct) / 100 * sh)
                shapes.set_text_flow(box, vertical="t", grow=False)
                box.set("autoFit", "none")
                # SARMA NITELIGI "true", ama SARMA YINE DE DEVREDE DEGIL:
                # etiketler yedi harflik ("13pt-1") ve kutu slaydin %40'i.
                # Sarma icin yer yok, dolayisiyla olculen sey yine yalnizca
                # satir ADIMI.
                #
                # Ilk surum wrap="none" yaziyordu ve Storyline IKI fikstuurde
                # de COKTU (hata raporu diyalogu). Bilinen-calisan fikstuurler
                # (goz_sarma, goz_olcek) wrap="true" kullaniyor ve onlar
                # sorunsuz onizlendi; tek yapisal fark buydu.
                box.set("wrap", "true")
                shapes.add_shape(r2, box)
                _apply_text(r2, box, icerik, color=renk, size=boy)
                pkg.replace_xml(part, r2)

        story = pkg.parse("story/story.xml")
        story.set("pG", ref.scene_guid)
        sahne_lst = story.find("sceneLst")
        for s in list(sahne_lst):
            if s.get("g") == ref.scene_guid:
                sahne_lst.remove(s)
                sahne_lst.insert(0, s)
                id_lst = s.find("sldIdLst")
                rels = {v: k for k, v in model._rel_map(pkg).items()}
                rid = rels.get(part)
                for e in list(id_lst or []):
                    if (e.text or "").strip() == rid:
                        id_lst.remove(e)
                        id_lst.insert(0, e)
                break
        pkg.replace_xml("story/story.xml", story)
        rapor = pkg.save(out, backup=False)

    uzay = shapes.Space(sw, sh, sahne[0], sahne[1])
    return {"etiket": etiket, "dosya": out, "slayt": ref.basename,
            "sahne": sahne, "uzay": uzay, "ok": rapor["verified"]["ok"],
            "en_boy": sahne[0] / sahne[1]}


def main() -> int:
    kurulan = []
    for etiket, kaynak, beklenen in KAYNAKLAR:
        if not kaynak.is_file():
            print(f"{etiket}: kaynak yok ({kaynak.name})")
            return 2
        k = kur(etiket, kaynak, beklenen)
        if k is None:
            return 1
        kurulan.append(k)

    print("IKI SAHNE, AYNI FIKSTUR:\n")
    for k in kurulan:
        u = k["uzay"]
        print(f"  {k['etiket']:>4} sahne : {k['dosya'].name}  slayt {k['slayt']}")
        print(f"        sahne (story.xml <sz>) : "
              f"{k['sahne'][0]:.0f}x{k['sahne'][1]:.0f}   en/boy {k['en_boy']:.3f} "
              f"({'16:9' if k['en_boy'] > 1.6 else '4:3'})")
        print(f"        uzay  : {u.kaynak}")
        print(f"        olculmus sahne mi : {u.olculmus_sahne}")
        print(f"        verified={k['ok']}")

    print(f"\nGIRDI SPESIFIKASYONU: her kutuda {SATIR} SERT satir, "
          f"wrap=none, punto {PUNTOLAR}")
    print("\nIKI HIPOTEZIN ONGORDUGU birim/punto (satir adimi / punto):")
    print(f"{'sahne':>6} {'H_sahne':>10} {'H_kanonik':>11}   (MEASURE_LEADING="
          f"{shapes.MEASURE_LEADING})")
    for k in kurulan:
        sh_h = k["sahne"][1]
        print(f"{k['etiket']:>6} {shapes.MEASURE_LEADING * (sh_h / sh_h):>10.3f} "
              f"{shapes.MEASURE_LEADING * (sh_h / 540.0):>11.3f}")
    print("\nAYIRAN SAYI:  R = (1920 birim/punto) / (720 birim/punto)")
    print("     H_sahne -> R ~ 1.00      H_kanonik -> R ~ 2.00")
    print("     (eski, curutulmus tablo bu karsilastirmada 2.99 derdi)")

    print("\nOLCULECEK, her kare icin:")
    for k in kurulan:
        for punto in PUNTOLAR:
            print(f"  python tools/kare_satir.py <kare> --bolge X0 X1 Y0 Y1 "
                  f"--bekle {SATIR} --punto {int(punto)} "
                  f"--uzay {k['sahne'][0]:.0f}   # {k['etiket']} sahne")
    print("\nKarar kurali bu dosyanin bas yorumunda, KARELERE BAKILMADAN yazildi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
