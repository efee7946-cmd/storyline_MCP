"""Storyline banka sorularını `questionIdLst`'e KAYDEDİYOR mu -- açık soru.

NICIN VAR. `puanlama.zincir`in 3c kosulu ("kayit hicbir slayda
cozulmuyor") bir kapsam notu tasiyor: SORU BANKASI sorulari slayt olarak
yasiyor ama bankanin kendi sahnesinde
(`quizMgr/bankLst/scene/sldIdLst`), ve o sahne `sceneLst`te DEGIL --
yani `model.slide_index`e girmiyor ve oradan "cozulemeyen" gorunuyor.

Sonucu iki turlu olabilir ve ikisi COK FARKLI:

  Storyline banka sorularini questionIdLst'e HIC kaydetmiyorsa
      3c'nin riski YOK. Kapsam notu tek cumleye iner.

  Kaydediyorsa
      Banka DOLU her projede 3c her kosuda konusur ve kullanici onu
      KAPATAMAZ. Yanlis uyari zamanla butun uyarilari degersizlestirir
      (ayni gerekce compose.py'de yazili). O zaman cozunurluk
      `bankLst/scene/sldIdLst` uyelerini de kapsamali.

BUGUN OLCULEMIYOR, ve sebebi fikstur yoklugu: diskteki 52 kursun
52'sinde `bankLst` VAR ama hepsi BOS (banka slaydi 0), `donors/`
havuzundaki 9 projede de 0. Yani soruyu cevaplayacak tek bir dosya yok.

BU SONDA O DOSYAYI BEKLIYOR. Elinizde banka DOLU bir `.story` olunca:

    python tools/banka_sorusu.py <kurs.story>

Sonda kendi kendine hukum vermez, OLCER ve neyi gorduguunu yazar:
bankadaki slayt guid'leri, quiz kayitlarindaki guid'ler, ve ikisinin
KESISIMI. Kesisim bos degilse cevap "kaydediyor"dur.

FIKSTUR NASIL URETILIR (Storyline'da, bir kez):
  1 Yeni ya da var olan bir projede Slides > Question Bank > yeni banka
  2 Bankaya EN AZ BIR soru ekle
  3 Kurs icine "Draw from Question Bank" ile o soruyu cek
  4 Kaydet

Ucuncu adim onemli: yalnizca banka kurup CEKMEMEK, sorunun yarisini
olcer. Iki hali de gormek icin ideal olan, cekilmis ve cekilmemis birer
soru tasiyan bir banka.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import warnings                                        # noqa: E402
warnings.simplefilter("ignore")

from storyline_mcp.package import StoryPackage         # noqa: E402
from storyline_mcp import model, puanlama              # noqa: E402

KOSAMADI = 3


def olc(yol: str) -> dict:
    """Bankayi, quiz kayitlarini ve kesisimlerini OLC. Hukum vermez."""
    pkg = StoryPackage(yol)
    story = pkg.parse("story/story.xml")
    index = model.slide_index(pkg)

    bankalar = []
    banka_guidleri: set[str] = set()
    bank_lst = story.find("quizMgr/bankLst")
    for sahne in (bank_lst if bank_lst is not None else []):
        sld = sahne.find("sldIdLst")
        guidler = [(el.text or el.get("g") or "").strip()
                   for el in (sld if sld is not None else [])]
        guidler = [g for g in guidler if g]
        banka_guidleri |= set(guidler)
        bankalar.append({"ad": sahne.get("name") or "(isimsiz)",
                         "slayt": len(guidler), "guidler": guidler})

    kayitlar: list[str] = []
    for quiz in story.iter("quiz"):
        id_list = quiz.find("questionIdLst")
        kayitlar += [(el.text or "").strip()
                     for el in (id_list if id_list is not None else [])]
    kayitlar = [k for k in kayitlar if k]

    sahne_guidleri = {ref.guid for ref in index.values()}
    return {
        "dosya": pathlib.Path(yol).name,
        "bankalar": bankalar,
        "banka_slaydi": len(banka_guidleri),
        "quiz_kaydi": len(kayitlar),
        # ASIL SORU: bankadaki bir slayt quiz'e kayitli mi.
        "kesisim": sorted(banka_guidleri & set(kayitlar)),
        # Kayitlarin kaci NORMAL sahnelerden geliyor (karsilastirma icin)
        "sahneden_kayit": sorted(set(kayitlar) & sahne_guidleri),
        # Ne bankada ne sahnede: 3c'nin bugun "cozulemeyen" dedigi kume
        "hicbiri": sorted(set(kayitlar) - banka_guidleri - sahne_guidleri),
        "zincir": puanlama.zincir(pkg),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("kurs", help="banka DOLU bir .story")
    args = ap.parse_args()

    if not pathlib.Path(args.kurs).exists():
        print(f"KOSAMADI: dosya yok ({args.kurs}).")
        return KOSAMADI

    r = olc(args.kurs)
    print(f"{r['dosya']}")
    for b in r["bankalar"]:
        print(f"  banka {b['ad']!r}: {b['slayt']} slayt")
    print(f"  quiz kaydi          : {r['quiz_kaydi']}")
    print(f"  bankadan kayitli    : {len(r['kesisim'])} {r['kesisim'][:3]}")
    print(f"  sahneden kayitli    : {len(r['sahneden_kayit'])}")
    print(f"  ne banka ne sahne   : {len(r['hicbiri'])} {r['hicbiri'][:3]}")
    print("  zincir:")
    for k in r["zincir"] or ["    (temiz)"]:
        print(f"    {k[:100]}")

    if r["banka_slaydi"] == 0:
        print()
        print("KOSAMADI: bu projede soru bankasi BOS (banka slaydi 0). "
              "Acik soru cevaplanamaz -- bu 'kaydetmiyor' demek DEGIL, "
              "'bakilamadi' demek. Fikstur nasil uretilir: bkz. baslik.")
        return KOSAMADI

    print()
    if r["kesisim"]:
        print(f"CEVAP: Storyline banka sorularini questionIdLst'e KAYDEDIYOR "
              f"({len(r['kesisim'])} guid hem bankada hem kayitta).")
        print("SONUCU: `puanlama.zincir` 3c'nin cozunurlugu bankLst uyelerini "
              "de KAPSAMALI; yoksa banka dolu her projede 3c kalici olarak "
              "konusur ve kullanici onu kapatamaz.")
    else:
        print("CEVAP: bu projede bankadaki hicbir slayt quiz'e kayitli DEGIL.")
        print("SONUCU: 3c'nin riski bu proje icin YOK. Ama kapsam iki sarta "
              "bagli -- bankadan soru CEKILMIS mi (baslik, 3. adim) ve "
              "cekilen soru kursa kopyalanip normal bir sahneye mi giriyor. "
              "Ikisi de dogruysa cevap 'kaydetmiyor' olarak genellenebilir.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
