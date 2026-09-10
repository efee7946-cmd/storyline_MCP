"""Kablolama bir DEĞİŞMEZ mi, yoksa atlanabilir bir adım mı.

NICIN VAR. Md. 3'un yazma tarafi: quiz kaydi, `quizG` ve
`lmsResultSlideG` her yazmada dosyadakiyle uzlastiriliyor
(`puanlama.kablola`, `server._write` icinden). Gerekce: kablolama
TURETILMIS -- icinde kullanici girdisi yok -- ve turetilmis bir sey
adim degil DEGISMEZDIR. Adim atlanabilir; degismez atlanamaz. Sohbet
yolunun "bitti" ani olmadigi icin bir kapanis ADIMI kurulamiyordu;
degismez o soruyu cozmuyor, ORTADAN KALDIRIYOR.

ALTI AYAK:
  1 EKLER        kaydi silinmis puanli slayt, ilk yazmada geri kayitlanir
  2 DUSURUR      etkilesimi kaldirilmis slaydin BAYAT kaydi dusurulur.
                 Yalnizca ekleyen bir surum bir UST KUMEYE yakinsardi.
  3 COGALTMAZ    temiz kursta 20 yazma cagrisi -> 0 kablolama degisikligi.
                 Olculen sey sure DEGIL: "kac cagrida gercekten yaziyor".
  4 ARA HALI KUSUR SAYMAZ  soru var, sonuc slaydi yok -> HICBIR SEY
                 yapmaz. Yazma anindaki bir REDDIN yapamadigi sey buydu;
                 md. 3'un "gorunur icerik uretme" karari bunu guvenli
                 kilan seyin ta kendisi.
  5 ISPATSIZ SILMEZ  hicbir slayda cozulmeyen kayit SILINMEZ, bildirilir.
                 Soru bankasi sorulari SLAYT olarak yasiyor ama bankanin
                 kendi sahnesinde (`quizMgr/bankLst/scene/sldIdLst`) ve o
                 sahne `sceneLst`te DEGIL -- yani `slide_index`e girmez
                 ve buradan "cozulemeyen" gorunur. Korpusun 52 kursunun
                 52'sinde bankLst VAR. Silmek, kullanicinin bankasini
                 sessizce yok etmek olurdu.
  6 KAYIT NOKTASINDA  soruyla ILGISIZ bir arac (`set_theme_font`) da
                 degismezi korur. Bu ayak, kuralin arac basina degil
                 `_write`ta durdugunu KANITLAR; 55. araci yazan kisi onu
                 bedavaya alir.

Alti olmadan digerleri, kurali yalnizca soru araclarina koymus bir
surumle de gecilirdi -- ve o surum, `move_shape` ya da `update_text`
sonrasi bozulan bir kaydi hic onarmazdi.

    python tools/kablolama_kapi.py

BU KAPIYI SUIT KOSARKEN ELLE KOSTURMAYIN. Kanarya dosyalari SABIT
adli ve `test/_canary/` icinde paylasilan dosyalar (deponun kapi
gelenegi bu: adimlar birbirinin urettigi dosyayi okuyor). Iki kosu ayni
anda ayni dosyaya yazarsa ikisi de yanlis okur.

Olculdu 2026-09-11 ve YANLIS ALARM URETTI: suit kosarken bu kapi elle
iki kez kosuldu; suit'in adimi "DEGISMEZ EKLEMIYOR" diye kirmiziya
dondu, temiz kosuda ayni kod YESIL gecti. Tanidik ayrimin tersi --
"kostu ve dustu" gibi gorunen bir "ortam bozuldu". Ayirt eden sey:
yarisin kapiya OZGU olmasi (elle kosulan yalnizca bu kapiydi ve
yalnizca `kablolama_*` dosyalarina yaziyor), ayni suit'te `ajan yolu`
ve `puanlanabilirlik` yesil kaldi.
"""

from __future__ import annotations

import asyncio
import json
import pathlib
import shutil
import sys
import tempfile
import warnings
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

warnings.simplefilter("ignore")

KOSAMADI = 3
ACILMADI = "SUNUCU ACILMADI"
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError as _eksik:                      # pragma: no cover
    ISTEMCI_YOK = str(_eksik)
else:
    ISTEMCI_YOK = ""

from storyline_mcp.package import StoryPackage      # noqa: E402
from storyline_mcp import authoring, model, puanlama  # noqa: E402

BLANK = ROOT.parent / "test" / "bos.story"
CANARY = ROOT.parent / "test" / "_canary"


def _coz(res):
    veri = getattr(res, "structured_content", None)
    if veri:
        return veri
    icerik = res.content or []
    return json.loads(icerik[0].text) if icerik else {}


def _kurs(ad: str) -> pathlib.Path:
    """Puanli soru + sonuc slaydi olan temiz bir kurs."""
    CANARY.mkdir(parents=True, exist_ok=True)
    yol = CANARY / ad
    shutil.copy2(BLANK, yol)
    pkg = StoryPackage(yol)
    for i in range(2):
        authoring.add_question(pkg, None, f"S{i}", ["a", "b", "c", "d"], [i],
                               eyebrow="B",
                               feedback={"correct": "E", "incorrect": "H"})
    authoring.add_results_slide(pkg)
    pkg.save(yol, backup=False)
    return yol


def _kayitli(yol: pathlib.Path) -> set[str]:
    pkg = StoryPackage(yol)
    return set(puanlama.izleme(pkg, model.slide_index(pkg))["registered"])


async def _kosu(yol: pathlib.Path, cagrilar: list[tuple[str, dict]]) -> tuple:
    """Verilen arac cagrilarini GERCEK sunucuya, stdio uzerinden yap."""
    params = StdioServerParameters(
        command=sys.executable,
        args=["-c", "from storyline_mcp.server import main; main()"], env=None)
    kablolamalar, hatalar = [], []
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8",
                                errors="replace") as tampon:
        async with stdio_client(params, errlog=tampon) as (r, w):
            async with ClientSession(r, w) as s:
                try:
                    await s.initialize()
                except BaseException as acilis:
                    tampon.seek(0)
                    print(f"{ACILMADI} ({type(acilis).__name__}). stderr:")
                    print((tampon.read() or "").strip()[-1200:] or "  (BOS)")
                    return [], [ACILMADI]
                for ad, kw in cagrilar:
                    res = await s.call_tool(
                        ad, {"path": str(yol), "in_place": True, **kw})
                    if getattr(res, "is_error", False):
                        hatalar.append(f"{ad}: " + " ".join(
                            (getattr(b, "text", "") or "")
                            for b in (res.content or []))[:90])
                        continue
                    veri = _coz(res)
                    kablolamalar.append(veri.get("kablolama"))
    return kablolamalar, hatalar


def kanarya() -> list[str]:
    kusur: list[str] = []

    # 1. EKLER
    yol = _kurs("kablolama_ekler.story")
    once = _kayitli(yol)
    pkg = StoryPackage(yol)
    story = pkg.parse("story/story.xml")
    for liste in story.iter("questionIdLst"):
        for oge in list(liste):
            liste.remove(oge)
    pkg.replace_xml("story/story.xml", story)
    pkg.save(yol, backup=False)
    kablo, hata = asyncio.run(_kosu(yol, [("set_theme_font", {"font": "Arial"})]))
    if hata == [ACILMADI]:
        return [ACILMADI]
    sonra = _kayitli(yol)
    print(f"ekler       : kayit {len(once)} -> silindi -> {len(sonra)}")
    if sonra != once:
        kusur.append(f"DEGISMEZ EKLEMIYOR: kayitlar silindikten sonra bir "
                     f"yazma gecti ama {sorted(once - sonra)} geri gelmedi")

    # 6. KAYIT NOKTASINDA -- ayni kosu, SORUYLA ILGISIZ bir aracla yapildi.
    #    (1. ayak zaten `set_theme_font` kullaniyor; bu satir onu iddia
    #    olarak YAZIYOR ki kural arac basina tasinirsa ayak dussun.)
    print(f"kayit nokta.: onarim `set_theme_font` cagrisindan gecti "
          f"({'EVET' if sonra == once else 'HAYIR'})")

    # 2. DUSURUR
    yol2 = _kurs("kablolama_dusurur.story")
    pkg2 = StoryPackage(yol2)
    hedef = sorted(_kayitli(yol2))[0]
    part = pkg2.slide_part_for(hedef)
    kok = pkg2.parse(part)
    liste = kok.find("shapeLst")
    for el in list(liste or []):
        if el.tag.endswith("Intr") and el.tag != "rsltsIntr":
            liste.remove(el)
    pkg2.replace_xml(part, kok)
    pkg2.save(yol2, backup=False)
    kablo2, hata2 = asyncio.run(_kosu(yol2, [("set_theme_font", {"font": "Arial"})]))
    if hata2 == [ACILMADI]:
        return [ACILMADI]
    kalan = _kayitli(yol2)
    print(f"dusurur     : {hedef} etkilesimsiz -> kayitli mi: "
          f"{'EVET (YANLIS)' if hedef in kalan else 'hayir (dogru)'}")
    if hedef in kalan:
        kusur.append(f"DEGISMEZ DUSURMUYOR: {hedef} puanli etkilesim "
                     f"tasimiyor ama quiz kaydi duruyor -- toplama sifir "
                     f"puanli soru girer, ve kablolama bir UST KUMEYE "
                     f"yakinsiyor")

    # 3. COGALTMAZ
    yol3 = _kurs("kablolama_cogaltmaz.story")
    cagrilar = [("add_slide", {"template": "slide7.xml", "name": "X"})]
    cagrilar += [("set_theme_font", {"font": "Arial"}) for _ in range(19)]
    kablo3, hata3 = asyncio.run(_kosu(yol3, cagrilar))
    if hata3 == [ACILMADI]:
        return [ACILMADI]
    yazan = [k for k in kablo3 if k]
    print(f"cogaltmaz   : {len(kablo3)} yazma cagrisi -> {len(yazan)} "
          f"kablolama degisikligi (0 olmali)")
    if yazan:
        kusur.append(f"YAZMA COGALMASI: temiz kursta {len(yazan)}/{len(kablo3)} "
                     f"cagri kablolamayi degistirdi ({yazan[0]}) -- degismez "
                     f"kararli durumda dosyaya dokunmamali")

    # 4. ARA HALI KUSUR SAYMAZ
    yol4 = CANARY / "kablolama_arahal.story"
    shutil.copy2(BLANK, yol4)
    pk4 = StoryPackage(yol4)
    authoring.add_question(pk4, None, "S", ["a", "b", "c", "d"], [1],
                           eyebrow="B",
                           feedback={"correct": "E", "incorrect": "H"})
    pk4.save(yol4, backup=False)
    r4 = puanlama.kablola(StoryPackage(yol4))
    print(f"ara hal     : soru var, sonuc slaydi yok -> degisti="
          f"{r4['degisti']} ({r4['neden'] or '-'})")
    if r4["degisti"]:
        kusur.append(f"ARA HAL KUSUR SAYILIYOR: sonuc slaydi olmayan bir "
                     f"kursta kablolama dosyayi degistirdi ({r4}) -- yapim "
                     f"ortasindaki mesru hal bozuluyor")

    # 5. ISPATSIZ SILMEZ
    yol5 = _kurs("kablolama_ispatsiz.story")
    pk5 = StoryPackage(yol5)
    story5 = pk5.parse("story/story.xml")
    quiz = next(iter(story5.find("quizMgr").findall("quizLst")[0]), None)
    if quiz is None:
        kusur.append("KANARYA KURULAMADI (5): okunan quizLst bos")
    else:
        oge = ET.SubElement(quiz.find("questionIdLst"), "item")
        oge.text = "deadbeef-0000-0000-0000-000000000001"
        pk5.replace_xml("story/story.xml", story5)
        pk5.save(yol5, backup=False)
        kablo5, hata5 = asyncio.run(
            _kosu(yol5, [("set_theme_font", {"font": "Arial"})]))
        if hata5 == [ACILMADI]:
            return [ACILMADI]
        son = pk5 = StoryPackage(yol5)
        kalan_ham = {(el.text or "").strip()
                     for q in son.parse("story/story.xml").iter("quiz")
                     for el in (q.find("questionIdLst") or [])}
        duruyor = "deadbeef-0000-0000-0000-000000000001" in kalan_ham
        # SORU YAPIYA SORULUYOR, DIZGEYE DEGIL -- VE BU BIR DUZELTME.
        #
        # Ilk yazim `any("cozulmuyor" in k for k in zincir(...))` idi:
        # insan-okur bir cumlede ALT DIZI aramasi. `zincir`in 3c mesaji
        # banka bosken "SILINMIS bir slayda isaret ediyor" diye
        # KESINLESTIRILINCE o alt dizi kayboldu ve kapi UC KOSUDA UC KEZ
        # kirmiziya dondu -- davranis hic bozulmadan, yalnizca mesaj
        # degistigi icin.
        #
        # Ayni sinif bu iplikte yedinci kez: hayal edilen bir bicime
        # yazilmis yuklem. `izleme` cozulemeyen kayitlari ZATEN yapisal
        # olarak sayiyor; soru oradan soruluyor.
        _iz = puanlama.izleme(son, model.slide_index(son))
        yapisal = sum(len(q["cozulemeyen"]) for q in _iz["quizzes"])
        bildirdi = yapisal > 0 and bool(puanlama.zincir(son))
        print(f"ispatsiz    : cozulemeyen kayit duruyor={duruyor}, "
              f"izleme sayiyor={yapisal}, zincir konusuyor={bildirdi}")
        if not duruyor:
            kusur.append(
                "ISPATSIZ SILME: hicbir slayda cozulmeyen bir kayit silindi. "
                "Soru bankasi sorulari da boyle gorunur (bankLst/scene, "
                "sceneLst'te DEGIL) -- kullanicinin bankasi sessizce yok "
                "edilebilir.")
        if not bildirdi:
            kusur.append("SESSIZ: cozulemeyen kayit ne siliniyor ne de "
                         "bildiriliyor -- gorunmez kaliyor")
    return kusur


def main() -> int:
    if ISTEMCI_YOK:
        print(f"KOSAMADI: mcp istemcisi yok ({ISTEMCI_YOK}).")
        return KOSAMADI
    if not BLANK.exists():
        print(f"KOSAMADI: fikstur yok ({BLANK}).")
        return KOSAMADI
    kusur = kanarya()
    if kusur == [ACILMADI]:
        print("")
        print("KOSAMADI: sunucu acilmadi (sebep yukarida). Kablolama "
              "degismezi olculemedi -- 'gecti' DEGIL, 'bakilmadi'.")
        return KOSAMADI
    if kusur:
        print("\nKAPI KALDI:")
        for k in kusur:
            print(f"  - {k}")
        return 1
    print("\nkapi gecti: kablolama bir degismez -- ekliyor, bayat kaydi "
          "dusuruyor, kararli durumda yazmiyor, ara hali bozmuyor, "
          "ispatsiz silmiyor")
    print("KAPSAM: GORUNUR ICERIK URETILMEZ (md. 3 karari). Sonuc slaydi\n"
          "        olmayan kurs kablolanmaz -- o hal uyariya kalir\n"
          "        (`puanlama.eksik_sonuc_uyarisi`).")
    # DEGISMEZ HANGI YOLDA: bu asimetri baska hicbir yerde yazili degil.
    print("        DEGISMEZ MCP YOLUNDA duruyor (`server._write`). Panelin")
    print("        kurucu yolu `pkg.save`i DOGRUDAN cagiriyor: zinciri INSA")
    print("        GEREGI dogru kuruyor, DEGISMEZ olarak degil. Bugun fark")
    print("        yok -- bayat kayit `delete_shape` istiyor ve kurucu onu")
    print("        kullanmiyor -- ama 'turetilmis olan degismezdir'")
    print("        gerekcesi yol ayrimi TANIMIYOR.")
    print("        SORU BANKASI: banka DOLU bir projede sinanmadi; fikstur")
    print("        yok (52 kursun 52'sinde bankLst bos, donors/'daki 9")
    print("        projede de banka slaydi 0). Ayrinti: puanlama.zincir 3c.")
    return 0


if __name__ == "__main__":
    # KANARYA KILIDI. Kapilar `test/_canary/` icine SABIT adli dosyalar
    # yaziyor; iki kosu ayni anda ayni dosyaya yazarsa ikisi de yanlis
    # okur ve sonuc "kostu ve dustu" gibi gorunur. Gerekce ve olcum:
    # tools/kanarya_kilit.py.
    from kanarya_kilit import korumali
    raise SystemExit(korumali(main))
