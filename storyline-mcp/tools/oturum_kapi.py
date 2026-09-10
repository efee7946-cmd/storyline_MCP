"""Koşu başı anlık görüntüsü ve ayak izi ölçüsü ayakta mı.

NICIN VAR. Iki eksik tek modulle kapandi (`storyline_mcp/oturum.py`):
geri donus noktasi ve "kosu basindan beri ne degisti". Ikisi de SESSIZCE
olebilir -- anlik goruntu alinmazsa fark bos doner, ve bos bir fark
"hicbir sey degismedi" gibi okunur. Bu kapi tam olarak o sessizligi
sinar.

ALTI AYAK:
  1 BILGISIZLIK    anlik goruntu YOKKEN fark, sifir degisiklik DEGIL
                   "bakilamadi" demeli (dokunulmadi: None)
  2 CIPA           anlik alindi, hicbir sey yapilmadi -> dokunulmadi True
  3 EKLEME         yeni slayt ve yeni degisken gorulmeli
  4 KIMLIK         ekleme yapildiginda DOKUNULMAMIS slaytlar "degisti"
                   sayilmamali -- fark guid'e bakiyor, konuma degil.
                   Bu ayak olmadan konuma bakan bir uygulama da gecerdi.
  5 YERINDE        var olan slayttaki degisiklik gorulmeli (sekil/metin)
  6 GERI ALMA      kosu basina donunce fark temizlenmeli, ve simdiki hal
                   `.gerialma.bak` olarak SAKLANMALI

  7 SILME          silinen SEKIL farkta gorunmeli. Bu ayak `delete_shape`
                   ile birlikte eklendi; oncesinde silme araci yoktu ve
                   kapi bunu "olculmedi" diye yaziyordu.

HENUZ OLCULMEYEN: SLAYT silme. Slayt silme araci yok (capraz referans
demek: atlama hedefi, quiz kaydi, LMS hedefi), dolayisiyla silinen
SLAYDIN farkta gorunmesi hala sinanmiyor. Sifir bulgu "slayt silme
dogru olculuyor" demek degildir.

    python tools/oturum_kapi.py
"""

from __future__ import annotations

import pathlib
import shutil
import sys
import warnings

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

warnings.simplefilter("ignore")

from storyline_mcp import authoring, compose, duzenle, logic, model, oturum   # noqa: E402
from storyline_mcp.package import StoryPackage, StoryError          # noqa: E402

BLANK = ROOT.parent / "test" / "bos.story"
CANARY = ROOT.parent / "test" / "_canary"
KOSAMADI = 3


def kanarya() -> list[str]:
    kusur: list[str] = []
    CANARY.mkdir(parents=True, exist_ok=True)
    yol = CANARY / "oturum_kapi.story"
    for ek in (oturum.ANLIK_UZANTI, oturum.KUNYE_UZANTI, ".gerialma.bak"):
        (yol.with_suffix(yol.suffix + ek)).unlink(missing_ok=True)
    shutil.copy2(BLANK, yol)

    # 1. BILGISIZLIK
    f = oturum.fark(yol)
    print(f"bilgisizlik : anlik yokken dokunulmadi={f['dokunulmadi']!r} "
          f"(None olmali)")
    if f["anlik_goruntu"] or f["dokunulmadi"] is not None:
        kusur.append("SESSIZ BILGISIZLIK: anlik goruntu yokken fark "
                     "'degismedi' gibi donuyor -- bakilamadi ile degismedi "
                     "ayirt edilemez")

    # 2. CIPA
    k = oturum.anlik_goruntu(yol, etiket="kapi")
    if not k.get("yeni"):
        kusur.append("KANARYA KURULAMADI: anlik goruntu yeni degil")
    f = oturum.fark(yol)
    print(f"cipa        : dokunulmadan dokunulmadi={f['dokunulmadi']}")
    if not f["dokunulmadi"]:
        kusur.append(f"YANLIS POZITIF: hicbir sey yapilmadan degisiklik "
                     f"bildiriliyor ({f['degisen_slaytlar'][:2]})")

    # IKINCI CAGRI DOKUNMAMALI: kosu ortasinda anlik goruntu yenilenirse
    # geri donus noktasi kosuyla birlikte kayar.
    k2 = oturum.anlik_goruntu(yol)
    print(f"sabitlik    : ikinci cagri yeni={k2.get('yeni')} (False olmali)")
    if k2.get("yeni"):
        kusur.append("GERI DONUS NOKTASI KAYIYOR: ikinci cagri anlik "
                     "goruntuyu yeniliyor -- 'kosu basi' diye bir sey kalmaz")

    # 3 + 4. EKLEME, ve KIMLIK
    pkg = StoryPackage(yol)
    onceki = {r.basename for r in model.slide_index(pkg).values()}
    yeni_slayt = authoring.add_slide(pkg, sorted(onceki)[0], name="Kapi")["new_slide"]
    compose.compose_slide(pkg, yeni_slayt, "content", title="Yeni",
                          body="Govde", theme="gece")
    logic.add_variable(pkg, "KapiSayaci", kind="num", default=0)
    pkg.save(yol, backup=False)

    f = oturum.fark(yol)
    ekli = [e["slayt"] for e in f["eklenen_slaytlar"]]
    print(f"ekleme      : slayt={ekli} degisken={f['eklenen_degiskenler']}")
    if not ekli:
        kusur.append("OLCU KOR: eklenen slayt farkta gorunmuyor")
    if "KapiSayaci" not in f["eklenen_degiskenler"]:
        kusur.append("OLCU KOR: eklenen degisken farkta gorunmuyor")

    dokunulmamis_degisen = [d["slayt"] for d in f["degisen_slaytlar"]
                            if d["slayt"] in onceki]
    print(f"kimlik      : dokunulmamis slaytlardan 'degisti' sayilan: "
          f"{dokunulmamis_degisen or 'YOK'}")
    if dokunulmamis_degisen:
        kusur.append(
            f"KONUMA BAKIYOR: slayt eklendikten sonra dokunulmamis "
            f"{len(dokunulmamis_degisen)} slayt 'degisti' sayiliyor "
            f"({dokunulmamis_degisen[:3]}) -- esleme guid uzerinden olmali")

    # 5. YERINDE DEGISIKLIK
    hedef = sorted(onceki)[1]
    pkg2 = StoryPackage(yol)
    compose.compose_slide(pkg2, hedef, "statement", title="Ustune yazildi",
                          body="X", theme="gece")
    pkg2.save(yol, backup=False)
    f2 = oturum.fark(yol)
    yerinde = [d for d in f2["degisen_slaytlar"] if d["slayt"] == hedef]
    print(f"yerinde     : {hedef} -> "
          f"{yerinde[0]['neler'] if yerinde else 'GORULMEDI'}")
    if not yerinde:
        kusur.append(f"OLCU KOR: {hedef} yerinde degistirildi ama farkta "
                     f"gorunmuyor -- ajan kendi ayak izini goremez")

    # 7. SILME -- KENDI DOSYASINDA, ve bu bir DUZELTME.
    #
    # Ilk yazimi bu kapinin ana dosyasini kullaniyordu ve iki kez
    # yaniltiyordu: (a) fark KOSU BASINA gore, ve o anda slaytta 0 sekil
    # vardi -- besten birini silmek "sekil 0->4" olarak, yani ARTI
    # gorunuyordu; (b) iddia `"-" in n` diye yazilmisti ve "0->4"
    # icindeki OKU yakaliyordu. Yani ayak, silme hic olculmese de
    # yesildi. Iki hata da ayni sinifta: olcunun kendi cikti bicimine
    # bakmadan yazilmis bir kabul kosulu.
    yol_sil = CANARY / "oturum_kapi_silme.story"
    for ek in (oturum.ANLIK_UZANTI, oturum.KUNYE_UZANTI, ".gerialma.bak"):
        (yol_sil.with_suffix(yol_sil.suffix + ek)).unlink(missing_ok=True)
    shutil.copy2(BLANK, yol_sil)
    pkg3 = StoryPackage(yol_sil)
    s_sil = authoring.add_slide(pkg3, "slide7.xml", name="Silme")["new_slide"]
    compose.compose_slide(pkg3, s_sil, "content", title="T", body="G",
                          theme="gece")
    pkg3.save(yol_sil, backup=False)
    # ANLIK GORUNTU SEKILLER KURULDUKTAN SONRA: silmenin EKSI olarak
    # gorunmesi ancak taban dolu oldugunda anlamli.
    oturum.anlik_goruntu(yol_sil, etiket="silme ayagi")

    pkg4 = StoryPackage(yol_sil)
    kok4 = pkg4.parse(pkg4.slide_part_for(s_sil))
    once_sayi = len(kok4.find("shapeLst"))
    silinebilir = next(
        (e.get("name") for e in kok4.find("shapeLst")
         if (e.get("name") or "")
         and not duzenle._guid_referanslari(kok4, e.get("g") or "", e)), None)
    if silinebilir is None:
        print("silme       : KOSMADI (referanssiz sekil yok)")
        kusur.append("AYAK KOSMADI: silinecek referanssiz sekil bulunamadi, "
                     "silmenin farkta gorunmesi OLCULMEDI")
    else:
        duzenle.sekil_sil(pkg4, s_sil, silinebilir)
        pkg4.save(yol_sil, backup=False)
        f_sil = oturum.fark(yol_sil)
        neler = [n for d in f_sil["degisen_slaytlar"]
                 if d["slayt"] == s_sil for n in d["neler"]]
        # EKSI DELTA ARANIYOR, ok DEGIL: "(-1)" ile "0->4" ayirt edilmeli.
        dusen = [n for n in neler if n.startswith("sekil") and "(-" in n]
        print(f"silme       : {silinebilir!r} silindi ({once_sayi} sekil "
              f"vardi) -> farkta {dusen or neler or 'GORULMEDI'}")
        if not dusen:
            kusur.append(
                f"OLCU KOR: {silinebilir!r} silindi ama fark EKSI bir sekil "
                f"deltasi bildirmiyor (gorulen: {neler}) -- ajan kendi "
                f"silmesini goremez")

    # 6. GERI ALMA
    g = oturum.geri_al(yol)
    yedek = pathlib.Path(g["onceki_hali"])
    f3 = oturum.fark(yol)
    print(f"geri alma   : dokunulmadi={f3['dokunulmadi']} | "
          f"onceki hal saklandi={yedek.exists()}")
    if not f3["dokunulmadi"]:
        kusur.append(f"GERI ALMA EKSIK: kosu basina donuldu ama fark hala "
                     f"degisiklik bildiriyor ({f3['degisen_slaytlar'][:2]})")
    if not yedek.exists():
        kusur.append("GERI ALMA YIKICI: simdiki hal saklanmadan uzerine "
                     "yazildi -- duzeltmeye calistigi kaybin aynisi")

    # Anlik goruntu yokken geri alma HATA vermeli, sessiz basari degil.
    temiz = CANARY / "oturum_kapi_temiz.story"
    for ek in (oturum.ANLIK_UZANTI, oturum.KUNYE_UZANTI):
        (temiz.with_suffix(temiz.suffix + ek)).unlink(missing_ok=True)
    shutil.copy2(BLANK, temiz)
    try:
        oturum.geri_al(temiz)
        print("geri alma(-): anlik yokken KABUL EDILDI (YANLIS)")
        kusur.append("SESSIZ BASARI: anlik goruntu yokken geri alma hata "
                     "vermiyor -- kullanici donuldugunu saniyor")
    except StoryError:
        print("geri alma(-): anlik yokken REDDEDILDI (dogru)")
    return kusur


def main() -> int:
    if not BLANK.exists():
        print(f"KOSAMADI: fikstur yok ({BLANK}). Ayak izi olcusu "
              f"sinanamadi -- 'gecti' DEGIL, 'bakilmadi'.")
        return KOSAMADI
    kusur = kanarya()
    if kusur:
        print("\nKAPI KALDI:")
        for k in kusur:
            print(f"  - {k}")
        return 1
    print("\nkapi gecti: anlik goruntu sabit, fark ekleme/yerinde degisikligi "
          "goruyor, kimlik uzerinden esliyor, geri alma yikici degil")
    print("KAPSAM: SLAYT silme olculmedi -- araci yok. "
          "SEKIL silme yedinci ayakta olculuyor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
