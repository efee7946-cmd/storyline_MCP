"""Uretilen coktan-secmeli soru ekranda ne gorunuyor? Iki borcu birden kapatir.

IKI DUZELTME, TEK KARE:

  1. ETIKET GORUNURLUGU (_etiketi_gorunur_yap). Ogrenci bes BOS KAPSUL
     goruyordu; etiket ancak tiklayinca beliriyordu. Duzeltildi ama
     "onay kutusu listesi gibi gorunur" TAHMINDI -- olculmedi.

  2. SILUET (_ovali_kapsullestir). Sik ovalleri 27.5:1'e gerilmis elipsti,
     yani MERCEK. tools/goz_kapsul.py karesi `prstGeom`in cizimi
     belirledigini gosterdi ve duzeltme ona gore yazildi.

NEDEN GERCEK SORU, FIKSTUUR DEGIL: bu oturumda bir fikstuur olcumu gercege
AKTARILMADI (ust-serit fikstuurde %52, gercek kursta %32 -- ayni govde
uzunluguyla). goz_kapsul.py TEMIZ bir oval tohumuyla olctu; buradaki sik
ovalleri etkilesim GUID'leri, tetikler ve ALTI DURUM GOVDESI tasiyor.
Mekanizmanin ayni davranmasi BEKLENIR ama beklenti olcum degildir.

KARAR KURALI -- KAREYE BAKILMADAN YAZILDI:

  Etiketler TIKLANMADAN okunuyor       ->  (1) dogrulandi.
  Etiketler gorunmuyor                 ->  (1) gercege AKTARILMADI; fikstuur
      yesil olmasina ragmen kusur duruyor, ve kontrol kesiti yanlis yerde.

  Sik kutulari BAR/kapsul              ->  (2) dogrulandi.
  Sik kutulari hala MERCEK             ->  (2) aktarilmadi; goz_kapsul'un
      temiz tohum sonucu durum govdeli sekle gecmiyor.

  Slayt hic cizilmiyor / soru acilmiyor ->  TUR GECERSIZ. Iki dal hakkinda
      da hicbir sey soylemez; once acilma sorunu olculur.

NOT -- BU KARE SUNU OLCMEZ: siklarin TIKLANABILIRLIGI, skorun kaydi,
Gonder'in calismasi. Onlar ayri ve kayitli.

    python tools/goz_sik.py
"""

from __future__ import annotations

import shutil
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from storyline_mcp import authoring, compose, model, shapes
from storyline_mcp.authoring import _apply_text
from storyline_mcp.package import StoryPackage

KAYNAK = ROOT.parent / "test" / "bos.story"
CIKTI = ROOT.parent / "test" / "_referans" / "SIK.story"

IMZA = "#E8F0D8"        # duz zemin; kare guard'i bunu arar

SORU = "Paylasilan bir dosyayi gonderirken hangileri dogru?"
SIKLAR = [
    "Alici listesini gondermeden once dogrula",
    "Baglantiyi yalnizca gereken kisiye ver",
    "Dosyayi kisiye ac, baglantisi olan herkese degil",
    "Erisim iznine bir bitis tarihi koy",
    "Yanlis gonderimi kime bildirecegini bil",
]


def main() -> int:
    if not KAYNAK.is_file():
        print("Kaynak yok: %s" % KAYNAK)
        return 2
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        shutil.copy2(KAYNAK, CIKTI)
        pkg = StoryPackage(CIKTI)
        try:
            secim = authoring.pick_template_for_question(pkg, SORU, SIKLAR)
            # PALET SART. Ilk tur palet VERMEDEN kosuldu ve kare (2) icin
            # GECERSIZ cikti: paletsiz sikler `noFill` aliyor, dolgusuz bir
            # sekilde elips ile kapsul AYNI gorunur -- deney tam olcecegi
            # seyi icermiyordu. Panelle uretilen kursta sikler solidFill
            # 1B2C5E tasiyor (olculdu); gercek yol paletli.
            yapilan = authoring.add_question(
                pkg, secim["template"], SORU, SIKLAR, [0, 1],
                eyebrow="Bolum 1",
                palette=compose.theme_palette("gece"))
        except Exception as exc:
            print("soru uretilemedi (%s: %s) -- TUR GECERSIZ"
                  % (type(exc).__name__, str(exc)[:70]))
            return 1
        pkg.save(CIKTI, backup=False)

        pkg = StoryPackage(CIKTI)
        part = next((p for p, r in model.slide_index(pkg).items()
                     if r.basename == yapilan["new_slide"]), None)
        if part is None:
            print("uretilen slayt bulunamadi -- TUR GECERSIZ")
            return 1
        root = pkg.parse(part)
        sw, sh = shapes.slide_size(root)

        # IMZA ZEMINI EN ARKAYA. Kare guard'i bu rengi arar; onde olursa
        # soruyu kapatir ve tur kendi olcecegi seyi gizlemis olur.
        zemin = shapes.clone_shape(shapes.find_seed(pkg, "rect")[0],
                                   name="Zemin")
        shapes.set_shape_slide_size(zemin, sw, sh)
        shapes.set_loc(zemin, 0, 0, sw, sh)
        shapes.set_fill(zemin, IMZA)
        shapes.add_shape(root, zemin, to_back=True)
        _apply_text(root, zemin, "")
        pkg.replace_xml(part, root)

        story = pkg.parse("story/story.xml")
        ref = model.slide_index(pkg)[part]
        story.set("pG", ref.scene_guid)
        sahne = story.find("sceneLst")
        for s in list(sahne):
            if s.get("g") == ref.scene_guid:
                sahne.remove(s)
                sahne.insert(0, s)
                idl = s.find("sldIdLst")
                rels = {v: k for k, v in model._rel_map(pkg).items()}
                rid = rels.get(part)
                for e in list(idl or []):
                    if (e.text or "").strip() == rid:
                        idl.remove(e)
                        idl.insert(0, e)
                break
        pkg.replace_xml("story/story.xml", story)
        rapor = pkg.save(CIKTI, backup=False)

    # GERI OKU (K13): iki duzeltme de dosyaya YAZILDI mi? Yazilmadiysa kare
    # bunu soylemez -- "gorunmuyor" ile "hic yazilmadi" ayni gorunur.
    pkg = StoryPackage(CIKTI)
    root = pkg.parse(part)
    _tag, intr = authoring._find_interaction(root)
    guidler = authoring._choice_shape_guids(intr) if intr is not None else []
    by = {el.get("g"): el for el in root.iter() if el.get("g")}
    etiketli = elips = toplam = 0
    en_oran = 0.0
    for g in guidler:
        shape = by.get(g)
        if shape is None:
            continue
        toplam += 1
        durum = {(st.get("name") or "").lower(): st
                 for st in shape.iter("state")}
        normal = durum.get("normal")
        lst = normal.find("shapeLst") if normal is not None else None
        if lst is not None and any(c.tag == "textBox" for c in lst):
            etiketli += 1
        kutu = shapes.shape_rect(shape)
        if kutu and kutu[3] - kutu[1] > 0:
            en_oran = max(en_oran, (kutu[2] - kutu[0]) / (kutu[3] - kutu[1]))
        if any(c.tag == "oval"
               for gg in shape.iter("prstGeom") for c in list(gg)):
            elips += 1

    print("uretildi: %s  verified=%s" % (CIKTI.name, rapor["verified"]["ok"]))
    print("  sablon %s" % secim["template"])
    print("  slayt %s (%.0fx%.0f), kursun ILK slaydi" % (ref.basename, sw, sh))
    print("  sik sayisi        : %d" % toplam)
    print("  Normal'da etiketli: %d/%d" % (etiketli, toplam))
    print("  en buyuk en/boy   : %.1f" % en_oran)
    print("  hala elips        : %d/%d" % (elips, toplam))
    dolgular = []
    for g in guidler:
        shape = by.get(g)
        bg = shape.find("bG") if shape is not None else None
        for f in (bg.iter() if bg is not None else []):
            if f.tag.endswith("Fill") and f.tag != "gradOvrlyFill":
                dolgular.append(f.tag)
                break
    print("  dolgu             : %s" % (sorted(set(dolgular)) or "YOK"))
    if "noFill" in dolgular or not dolgular:
        print("  SIKLARDA DOLGU YOK -- siluet olculemez, TUR (2) ICIN GECERSIZ")
        return 1
    if toplam != len(SIKLAR):
        print("  SIK SAYISI TUTMUYOR -- TUR GECERSIZ")
        return 1
    if etiketli < toplam or elips:
        print("  DOSYAYA YAZILMAMIS -- kare bu iki dali olcemez, TUR GECERSIZ")
        return 1
    print("")
    print("KARAR KURALI bas yorumda, KAREYE BAKILMADAN yazildi.")
    print("  etiket okunuyor + kutu bar  -> iki duzeltme de dogrulandi")
    print("  etiket yok                  -> (1) gercege aktarilmadi")
    print("  kutu mercek                 -> (2) gercege aktarilmadi")
    print("")
    print("kare:")
    print("  python tools/shoot_preview.py %s -o ../test/_referans/SIK.png "
          "--imza %s --en-az 5" % (CIKTI, IMZA.lstrip("#")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
