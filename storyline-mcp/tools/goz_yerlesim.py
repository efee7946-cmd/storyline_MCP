"""Yeni yerleşim sabitleriyle iki GERÇEK slayt: hâlâ okunur mu?

Diff'i toptan kabul etmemek icin. Tabanlar yenilenmeden once gozle bakilacak
sey "metin sigiyor mu" DEGIL -- kirpma olmadigi olculdu, sigmak zaten
kozmetik. Bakilacak sey: SLAYT HALA OKUNUR MU. cover %36'dan %52'ye cikti,
yani kutular sadece buyumedi, slayt doldu.

UC SART, ucu de tek turda:

  1. COK SATIRLI KUTU. Buyume orada gorunuyor (+%15-20). Tek satirli kutular
     TERS yonde (-%20) ve tek basina bakilirsa yaniltir.
  2. GOLDEN'IN EN BUYUK IKI SAPMASI temsil edilsin:
        kisa/*     kutu 9.86 -> 7.87  (-%20, tek satir)
        orta/uzun  kok 27.2 -> 29.2   (+%7, cok satir)
     golden regresyon yakalayan taban; toptan yenilenmesi en riskli olan.
  3. 40 HARFLIK ETIKET. Havuzun 40 harfte 8'den 1'e dusmesinin pratikte ne
     urettigini gormeden GROWTH_LIMIT'e karar verilemez.

40 harf SENTETIK DEGIL, ve bu olculdu: add_button metni text[:40]'a kirpiyor
(bestecinin kendi tavani), add_question kirpmiyor ve uretilen kursta 60
harflik sik etiketleri var. Yani bu bant uretimde gercekten yasaniyor --
C2/C3'un sentetik uclarindan farkli.

    python tools/goz_yerlesim.py
"""

from __future__ import annotations

import shutil
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from storyline_mcp import authoring, compose, model, shapes
from storyline_mcp.package import StoryPackage

BLANK = ROOT.parent / "test" / "bos.story"
SRC = ROOT.parent / "test" / "0_duz_kopya.story"
OUT = ROOT.parent / "test" / "_referans" / "YERLESIM.story"

# golden'in orta/uzun vakasi, birebir: uzun kok + uc adet 40 harflik sik.
KOK = ("Sirket agina baglaniyken supheli bir e-posta aldin ve icindeki "
       "baglantiya tikladin. Simdi ne yapmalisin?")
SIKLAR = [t[:40] for t in [
    "Parolayi hemen degistir ve yoneticiye bildir",
    "Once yoneticiye bildir sonra parolayi degistir",
    "Cihazi kapat ve bilgi islem birimini ara hemen",
]]

# Cok satirli govde: buyumenin gorundugu yer.
GOVDE = ("Musteri gerildiginde sesin tonu degisir, cumleler kisalir ve ayni "
         "sikayet farkli kelimelerle tekrar eder. Konusma gecmise kayar, "
         "bugunku sorun yerine eski bir yasanmislik anlatilmaya baslanir.")


def main() -> int:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        shutil.copy2(SRC, OUT)
        pkg = StoryPackage(OUT)

        # 1) SORU slaydi -- golden orta/uzun vakasi + 40 harflik etiketler
        picked = authoring.pick_template_for_question(pkg, KOK, SIKLAR)
        made = authoring.add_question(pkg, picked["template"], KOK, SIKLAR, [0],
                                      eyebrow="Bolum 1")
        # PLAN DALI ARTIK YOK. Eskiden burada `framed` false ise
        # apply_choice_plan cagriliyordu; o dal uretimde 0/4 kullaniliyordu ve
        # silindi. Sessizce atlamak yerine BAGIRIR: dal geri gelirse bu kare
        # olculmemis bir yerlesimi olcuyor olurdu.
        if not made.get("framed"):
            print("framed=False -- plan dali silindi, bu kare gecersiz.")
            return 2
        soru_slayt = made["new_slide"]

        # 2) ICERIK slaydi -- cok satirli govde
        adlar = [r.basename for r in model.slide_index(pkg).values()]
        icerik_slayt = next(a for a in adlar if a != soru_slayt)
        compose.compose_slide(pkg, icerik_slayt, "content",
                              title="Gerginligin Ilk Isaretleri",
                              eyebrow="Bolum 1", body=GOVDE,
                              buttons=["Sonraki Bolume Gec"], identity="yerlesim")

        # Ikisini de basa al ki Preview dogrudan onlara acilsin.
        idx = model.slide_index(pkg)
        hedef = next(r for p, r in idx.items() if r.basename == soru_slayt)
        story = pkg.parse("story/story.xml")
        story.set("pG", hedef.scene_guid)
        sahne = story.find("sceneLst")
        for s in list(sahne):
            if s.get("g") == hedef.scene_guid:
                sahne.remove(s); sahne.insert(0, s)
                id_lst = s.find("sldIdLst")
                rels = {v: k for k, v in model._rel_map(pkg).items()}
                part_of = {r.basename: p for p, r in idx.items()}
                for ad in (soru_slayt,):
                    rid = rels.get(part_of[ad])
                    for e in list(id_lst or []):
                        if (e.text or "").strip() == rid:
                            id_lst.remove(e); id_lst.insert(0, e)
                break
        pkg.replace_xml("story/story.xml", story)
        rapor = pkg.save(OUT, backup=False)

        # Ne uretildigini SAYIYLA da bas: gozle bakis tek basina kalmasin.
        again = StoryPackage(OUT)
        for ad in (soru_slayt, icerik_slayt):
            part = next(p for p, r in model.slide_index(again).items()
                        if r.basename == ad)
            root = again.parse(part)
            W, H = shapes.slide_size(root)
            sl = root.find("shapeLst")
            n = sum(1 for s in (sl or [])
                    if model.shape_text(root, s.get("g") or "").strip())
            alt = max((shapes.shape_rect(s)[3] for s in (sl or [])
                       if shapes.shape_rect(s)), default=0)
            print(f"  {ad:<14}{W:.0f}x{H:.0f}  metinli sekil {n:>2}  "
                  f"en alt %{alt / H * 100:.0f}")

    print(f"\nuretildi: {OUT.name}  verified={rapor['verified']['ok']}")
    print(f"  1. slayt: {soru_slayt}  (golden orta/uzun + 3 x 40 harflik sik)")
    print(f"  2. slayt: {icerik_slayt}  (cok satirli govde + 18 harflik buton)")
    print("\nBAKILACAK: metin sigiyor mu DEGIL -- SLAYT OKUNUR MU.")
    print("  cover %36 -> %52 doldu; kutular buyudu, hava azaldi.")
    print("  Soru slaydinda 40 harflik siklar: havuz 1'e dustugu bant burasi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
