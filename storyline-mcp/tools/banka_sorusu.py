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

FIKSTUR BU MAKINEDE YOK, ve arandi (2026-09-12): Desktop, Documents ve
Downloads altinda 480 `.story` tarandi; banka DOLU tek dosya bu ipligin
kendi urettigi sentetik deneydi. Storyline kurulumu da orneklerle
gelmiyor (`Program Files\Articulate` altinda .story yok). Yani soruyu
bugun cevaplayacak bir dosya YOK.

OTURUMUN GECERLILIK KOSULU -- ve ilk sondanin hatasi tam buradaydi.
Sonda ilk kosusunda "Storyline KAYDEDIYOR" dedi; oysa kaydi BIZ
yazmistik. Dairesel bir cevapti. Oturum su ucu tasimazsa ayni tuzaga
duser:

  1 KAYDI HICBIR ASAMADA BIZ YAZMAYACAGIZ. Baslangic dosyasinda quiz
    kaydi BULUNMAYACAK (`questionIdLst` bos). Kayit dosyaya elle
    girdiyse "kimin yazdigi" sorusu yine cevapsiz kalir.
  2 HER ADIM STORYLINE'IN ARAYUZUNDEN GECECEK: soru bankasi olustur ->
    bankaya bir soru ekle -> kursa "Draw from Question Bank" ile cekme
    yerlestir -> kaydet.
  3 SONRA TEK SORU: `story.xml`deki `questionIdLst` ne iceriyor?

UC SONUC, UCU DE AYRI TASARIM SONUCU VERIYOR:

    banka sorusunun guid'i -> Storyline banka sorusunu DOGRUDAN
                              kaydediyor
    cekme slaydinin guid'i -> kaydedilen sey CEKME, soru degil;
                              `puanlama.kablola`nin hedefi de o olmali
    bos                    -> Storyline bankayi `questionIdLst`
                              uzerinden HIC raporlamiyor; yol haritasi
                              6'nin banka kismi baska bir mekanizma
                              arayacak

Ucu de tek acista gorunuyor, ve o dosya ayni zamanda 6'nin banka
kisminin FIKSTURU oluyor -- gecerli olmasinin sarti da bu: uctan uca
Storyline'in yazmis olmasi.

BU ARAC O OTURUMU KOSAMAZ. Storyline'i baslatip kaydettirebiliyoruz
(`tools/tur_testi.py` oyle yapiyor) ama ARAYUZUNDEN banka kuramayiz:
menuye tiklamak ne elimizde var ne de bu deponun kabul ettigi bir yol
("arayuz taklidi yok" -- bkz. depo kokundeki README).
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

    # KISA KIMLIK -> PARCA -> GUID. VE BU BIR DUZELTME (2026-09-11):
    # ilk surum `sldIdLst`in cocuklarini dogrudan guid sanip
    # `questionIdLst` ile karsilastiriyordu. `sldIdLst` KISA KIMLIK
    # tutuyor (`R6jC59AwwCRj`), `questionIdLst` ise GUID -- yani kesisim
    # HER ZAMAN bos cikardi ve sonda "kaydetmiyor" diye KENDINDEN EMIN
    # YANLIS bir cevap verirdi. Tam olarak bu ipligin kurali: olcunun
    # kendisi once sinanmali.
    #
    # Zincir `model.slide_index`in kullandiginin aynisi: kisa kimlik
    # `_rel_map`ten parcaya, parcanin kokundeki `g` de guid'e.
    rels = model._rel_map(pkg)
    bankalar = []
    banka_guidleri: set[str] = set()
    cozulemeyen_kisa: list[str] = []
    bank_lst = story.find("quizMgr/bankLst")
    for sahne in (bank_lst if bank_lst is not None else []):
        sld = sahne.find("sldIdLst")
        kisalar = [(el.text or "").strip()
                   for el in (sld if sld is not None else [])]
        kisalar = [k for k in kisalar if k]
        guidler = []
        for kisa in kisalar:
            parca = rels.get(kisa)
            if parca and parca in pkg._parts:
                g = (pkg.parse(parca).get("g") or "").strip()
                if g:
                    guidler.append(g)
                    continue
            cozulemeyen_kisa.append(kisa)
        banka_guidleri |= set(guidler)
        bankalar.append({"ad": sahne.get("desc") or sahne.get("name")
                         or "(isimsiz)",
                         "slayt": len(kisalar), "cozulen": len(guidler),
                         "guidler": guidler})

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
        "banka_slaydi": sum(b["slayt"] for b in bankalar),
        "banka_cozulen": len(banka_guidleri),
        "cozulemeyen_kisa": cozulemeyen_kisa,
        "quiz_kaydi": len(kayitlar),
        # ASIL SORU: bankadaki bir slayt quiz'e kayitli mi.
        "kesisim": sorted(banka_guidleri & set(kayitlar)),
        # INDEKSTEN cozulen kayitlar. "sahneden" DEGIL: slide_index
        # sahnesiz slayt parcalarini da indeksliyor, yani banka
        # slaytlari da buraya girer (olculdu 2026-09-11).
        "indeksten_cozulen": sorted(set(kayitlar) & sahne_guidleri),
        # Ne bankada ne sahnede: 3c'nin bugun "cozulemeyen" dedigi kume
        # Hicbir PARCAYA cozulmeyen: 3c bugun yalnizca bunlari sayar.
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
        print(f"  banka {b['ad']!r}: {b['slayt']} slayt, "
              f"{b['cozulen']}'i guid'e cozuldu")
    print(f"  quiz kaydi          : {r['quiz_kaydi']}")
    print(f"  bankadan kayitli    : {len(r['kesisim'])} {r['kesisim'][:3]}")
    print(f"  indeksten cozulen   : {len(r['indeksten_cozulen'])}")
    print(f"  ne banka ne sahne   : {len(r['hicbiri'])} {r['hicbiri'][:3]}")
    print("  zincir:")
    for k in r["zincir"] or ["    (temiz)"]:
        print(f"    {k[:100]}")

    if r["cozulemeyen_kisa"]:
        print(f"  UYARI: {len(r['cozulemeyen_kisa'])} banka kimligi parcaya "
              f"cozulmedi ({r['cozulemeyen_kisa'][:3]}) -- kesisim EKSIK "
              f"olcuulmus olabilir")
    if r["banka_slaydi"] == 0:
        print()
        print("KOSAMADI: bu projede soru bankasi BOS (banka slaydi 0). "
              "Acik soru cevaplanamaz -- bu 'kaydetmiyor' demek DEGIL, "
              "'bakilamadi' demek. Fikstur nasil uretilir: bkz. baslik.")
        return KOSAMADI

    print()
    # HUKUM DAR TUTULUYOR. Sonda "kayit VAR MI" gorur; kaydi KIMIN
    # yazdigini goremez. Sentetik bir dosyada kaydi biz yazmis olabiliriz
    # (ilk kosumda tam oyle oldu ve cikti "Storyline KAYDEDIYOR" diyordu
    # -- dairesel bir cevap).
    if r["kesisim"]:
        print(f"GORULEN: bankadaki {len(r['kesisim'])} slayt quiz'e KAYITLI.")
        print("  Kaydi KIMIN yazdigi buradan GORUNMEZ. Dosya Storyline'da")
        print("  yazildiysa cevap 'Storyline kaydediyor'dur; sentetik olarak")
        print("  kurulduysa yalnizca 'Storyline boyle bir kaydi KORUYOR'")
        print("  denebilir (olculdu: acilip kaydedildi, yapi birebir korundu).")
    else:
        print("GORULEN: bankadaki hicbir slayt quiz'e kayitli degil.")
        print("  Bankadan soru CEKILMEMIS olabilir (baslik, 3. adim).")
    print()
    print("3c ICIN SONUC -- VE BU ARTIK OLCULDU: banka slaytlari")
    print("`model.slide_index`e SAHNESIZ olarak giriyor (indeks, hicbir")
    print("sahnenin gostermedigi slayt parcalarini da ekliyor), yani quiz")
    print("kayitlari COZULUYOR ve 3c onlar icin HIC atesLENMIYOR. Once")
    print("yazili olan 'banka dolu projede 3c kalici kirmizi' kaygisi")
    print("MEKANIZMA OLARAK YANLISTI ve geri cekildi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
