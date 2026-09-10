"""Taşıma ve silme ayakta mı -- ve silme neyi REDDEDİYOR.

NICIN VAR. Arac yuzeyi 52 araca kadar yalnizca EKLIYORDU. `move_shape`
ve `delete_shape` ilk duzeltme araclari, ve ikisi de yeni bir kusur
sinifi aciyor: yanlis sekli tasimak/silmek, ve silerken referans kirmak.
Ikisi de SESSIZ -- cikti "basarili" doner, kirilma Storyline'da dosya
acilinca gorunur.

ALTI AYAK:
  1 TASIMA        istenen kutu yazilmali, VERILMEYEN alan korunmali
  2 DURUM GOVDESI durum tasiyan bir seklin govdeleri de tasinmali.
                  `shapes.set_loc` bunu yapiyor ve gerekcesi orada
                  yazili; kapi, tasimanin o yoldan gectigini dogrular.
                  Kendi `loc`unu yazan bir uygulama bu ayakta duser:
                  isabet alani oynar, resim yerinde kalir.
  3 SILME         referanssiz sekil gitmeli
  4 SILME REDDI   soru secenegi silinememeli (`intrFreeChoice shpG`)
  5 BELIRSIZLIK   ayni adi tasiyan iki sekil varsa SECILMEMELI
  6 COZUCU        ad ile bulunmali -- ve bu ayak, cozucunun logic'inkinden
                  GENIS oldugunu KANITLAR: ayni sekli `logic._shape_by`
                  bulamiyor (metne bakiyor), `duzenle._sekil_bul` buluyor.
                  Bu ayak olmadan iki cozucu sessizce ayrisir ve
                  "sekil yok" hatasi ajanin dogru adresine verilirdi.

    python tools/duzenle_kapi.py
"""

from __future__ import annotations

import pathlib
import shutil
import sys
import warnings

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

warnings.simplefilter("ignore")

from storyline_mcp import authoring, compose, duzenle, logic, shapes   # noqa: E402
from storyline_mcp.package import StoryPackage, StoryError             # noqa: E402

BLANK = ROOT.parent / "test" / "bos.story"
CANARY = ROOT.parent / "test" / "_canary"
KOSAMADI = 3


def _kok(pkg, slayt):
    return pkg.parse(pkg.slide_part_for(slayt))


def kanarya() -> list[str]:
    kusur: list[str] = []
    CANARY.mkdir(parents=True, exist_ok=True)
    yol = CANARY / "duzenle_kapi.story"
    shutil.copy2(BLANK, yol)
    pkg = StoryPackage(yol)

    s = authoring.add_slide(pkg, "slide7.xml", name="Kapi")["new_slide"]
    compose.compose_slide(pkg, s, "menu", title="Baslik",
                          buttons=["Devam", "Geri"], theme="gece")

    # 1. TASIMA
    r = duzenle.sekil_tasi(pkg, s, "Title", y=60, x=10)
    print(f"tasima      : {r['onceki']} -> {r['yeni']}")
    if not (r["yeni"]["x"] == 10.0 and r["yeni"]["y"] == 60.0):
        kusur.append(f"TASIMA YANLIS: istenen x=10 y=60, yazilan {r['yeni']}")
    if r["yeni"]["w"] != r["onceki"]["w"] or r["yeni"]["h"] != r["onceki"]["h"]:
        kusur.append(f"VERILMEYEN ALAN KORUNMADI: w/h degisti "
                     f"({r['onceki']} -> {r['yeni']})")

    # 2. DURUM GOVDESI. Durum tasiyan sekil ariyoruz; yoksa ayak KOSMADI
    # diye yazilir, sessizce gecilmez.
    root = _kok(pkg, s)
    durumlu = next((e for e in root.find("shapeLst")
                    if e.find("stateLst") is not None
                    and len(e.find("stateLst"))), None)
    if durumlu is None:
        print("durum govdesi: KOSMADI (bu slaytta durum tasiyan sekil yok)")
        kusur.append("AYAK KOSMADI: durum tasiyan sekil bulunamadi, "
                     "govdelerin tasinip tasinmadigi OLCULMEDI")
    else:
        ad = durumlu.get("name") or durumlu.get("g")
        duzenle.sekil_tasi(pkg, s, durumlu.get("g"), x=5, y=5, w=30, h=12)
        root2 = _kok(pkg, s)
        yeni_sekil = next(e for e in root2.find("shapeLst")
                          if e.get("g") == durumlu.get("g"))
        dis = shapes.shape_rect(yeni_sekil)
        genislik, yukseklik = dis[2] - dis[0], dis[3] - dis[1]
        govdeler = [shapes.shape_rect(b)
                    for st in (yeni_sekil.find("stateLst") or [])
                    for b in (st.find("shapeLst") or [])]
        govdeler = [g for g in govdeler if g]
        uyan = [g for g in govdeler
                if abs((g[2] - g[0]) - genislik) < 1
                and abs((g[3] - g[1]) - yukseklik) < 1]
        print(f"durum govdesi: {ad} -> {len(uyan)}/{len(govdeler)} govde "
              f"dis kutuyla ayni olcude")
        if govdeler and len(uyan) != len(govdeler):
            kusur.append(
                f"DURUM GOVDESI TASINMADI: {len(govdeler) - len(uyan)} govde "
                f"eski olcusunde kaldi -- isabet alani oynadi, resim yerinde "
                f"kaldi. Tasima `shapes.set_loc`ten gecmiyor olabilir.")

    # 3. SILME (referanssiz)
    once = [e.get("name") for e in _kok(pkg, s).find("shapeLst")]
    d = duzenle.sekil_sil(pkg, s, "Title")
    sonra = [e.get("name") for e in _kok(pkg, s).find("shapeLst")]
    print(f"silme       : {d['silinen']} gitti | {len(once)} -> {len(sonra)}")
    if "Title" in sonra or len(sonra) != len(once) - 1:
        kusur.append(f"SILME ETKISIZ: {once} -> {sonra}")

    # 4. SILME REDDI -- soru secenegi
    yol2 = CANARY / "duzenle_kapi_soru.story"
    shutil.copy2(BLANK, yol2)
    pk2 = StoryPackage(yol2)
    q = authoring.add_question(
        pk2, None, "Soru?", ["a", "b", "c", "d"], [1], eyebrow="B",
        feedback={"correct": "E", "incorrect": "H"})["new_slide"]
    kokq = _kok(pk2, q)
    secenek = next((e for e in kokq.find("shapeLst") if e.tag == "btn"), None)
    if secenek is None:
        print("silme reddi : KOSMADI (secenek butonu bulunamadi)")
        kusur.append("AYAK KOSMADI: soru secenegi bulunamadi, silme reddi "
                     "OLCULMEDI")
    else:
        try:
            duzenle.sekil_sil(pk2, q, secenek.get("g"))
            print("silme reddi : secenek SILINDI (YANLIS)")
            kusur.append(
                "REFERANS KIRILIYOR: soru secenegi silinebiliyor. "
                "`intrFreeChoice shpG` o guid'e bakiyor; silinen secenek "
                "soruyu sessizce bozar.")
        except StoryError as exc:
            print(f"silme reddi : REDDEDILDI (dogru) -- {str(exc)[:60]}")

    # 5. BELIRSIZLIK -- ayni ad birden fazla sekilde
    kokq = _kok(pk2, q)
    adlar = [e.get("name") for e in kokq.find("shapeLst")]
    cift = next((a for a in adlar if a and adlar.count(a) > 1), None)
    if cift is None:
        print("belirsizlik : KOSMADI (ayni adi tasiyan iki sekil yok)")
        kusur.append("AYAK KOSMADI: tekrar eden ad bulunamadi, belirsizlik "
                     "reddi OLCULMEDI")
    else:
        try:
            duzenle.sekil_sil(pk2, q, cift)
            print(f"belirsizlik : {cift!r} SESSIZCE secildi (YANLIS)")
            kusur.append(
                f"BELIRSIZ SECIM: {cift!r} adini {adlar.count(cift)} sekil "
                f"tasiyor ve arac birini sessizce secti -- ajan baska bir "
                f"sekli sildigini fark etmez")
        except StoryError:
            print(f"belirsizlik : {cift!r} icin REDDEDILDI (dogru)")

    # 6. COZUCU AYRIMI. `Title`in METNI "Baslik"; logic'in cozucusu ada
    # bakmadigi icin onu BULAMAZ. Iki cozucu ayrisirsa bu ayak duser.
    yol3 = CANARY / "duzenle_kapi_cozucu.story"
    shutil.copy2(BLANK, yol3)
    pk3 = StoryPackage(yol3)
    s3 = authoring.add_slide(pk3, "slide7.xml", name="Cozucu")["new_slide"]
    compose.compose_slide(pk3, s3, "content", title="Baslik", body="Govde",
                          theme="gece")
    kok3 = _kok(pk3, s3)
    dar = logic._shape_by(kok3, "Title")
    genis = duzenle._sekil_bul(kok3, "Title")
    print(f"cozucu      : logic {'buldu' if dar is not None else 'BULAMADI'}, "
          f"duzenle {'buldu' if genis is not None else 'BULAMADI'}")
    if genis is None:
        kusur.append("COZUCU DAR: 'Title' adiyla bulunamiyor -- ajanin "
                     "slide_layout'tan aldigi adres ise tam olarak bu")
    if dar is not None:
        kusur.append(
            "AYAK KOR: logic'in cozucusu de ada bakiyor olabilir; bu ayak "
            "artik iki cozucuyu AYIRT ETMIYOR. Genislik iddiasi yeniden "
            "olculmeli.")
    return kusur


def main() -> int:
    if not BLANK.exists():
        print(f"KOSAMADI: fikstur yok ({BLANK}). Tasima/silme sinanamadi "
              f"-- 'gecti' DEGIL, 'bakilmadi'.")
        return KOSAMADI
    kusur = kanarya()
    if kusur:
        print("\nKAPI KALDI:")
        for k in kusur:
            print(f"  - {k}")
        return 1
    print("\nkapi gecti: tasima durum govdelerini de tasiyor, silme "
          "referansli sekli reddediyor, belirsiz ad secilmiyor")
    print("KAPSAM: SLAYT silme/tasima bu kapida YOK -- araclari da yok.\n"
          "        Slayt silmek capraz referans demek (atlama hedefi, quiz\n"
          "        kaydi, LMS hedefi) ve ayri olculmeli.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
