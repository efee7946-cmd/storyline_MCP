"""Kablolama bir DEĞİŞMEZ mi, yoksa atlanabilir bir adım mı.

NICIN VAR. Md. 3'un yazma tarafi: quiz kaydi, `quizG` ve
`lmsResultSlideG` her yazmada dosyadakiyle uzlastiriliyor
(`puanlama.kablola`, `server._write` icinden). Gerekce: kablolama
TURETILMIS -- icinde kullanici girdisi yok -- ve turetilmis bir sey
adim degil DEGISMEZDIR. Adim atlanabilir; degismez atlanamaz. Sohbet
yolunun "bitti" ani olmadigi icin bir kapanis ADIMI kurulamiyordu;
degismez o soruyu cozmuyor, ORTADAN KALDIRIYOR.

YEDI AYAK:
  0 YENIDEN DENE sonuc slaydinin "Sinavi Yeniden Dene" hedefi ilk KAYITLI
                 soruya baglanir. `clone`un yeniden yazma dali onu
                 "sonraki slayt"a ceviriyordu ve kendi notu bunun ANLAMCA
                 yanlis oldugunu yaziyordu; erteleme gerekcesi ("sonuc
                 slaydi hicbir quiz'e kayitli degil") bu degismez
                 kurulunca GECERSIZ kaldi. Ayak dort yonlu: tohumun
                 gerceklen hasarli dogdugu, onarim, KARARLILIK (ikinci
                 cagri yazmamali) ve SINIR (cozulen bir hedef ezilmemeli).
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
                 GEREKCE 2026-09-11'DE DARALDI: once "banka sorulari
                 `slide_index`e girmez, cozulemeyen gorunur" diye
                 yaziyordu ve bu YANLISTI -- `slide_index` sahnesiz slayt
                 parcalarini da indeksliyor, yani banka kayitlari
                 COZULUYOR (olculdu). Ayak yine de dogru: guid'in neyi
                 gosterdigini bilmeden silmek, ispatsiz bir silmedir.
                 Bugun bilinen tek ispatsiz hal, hicbir PARCAYA
                 cozulmeyen kayit -- silinmis bir slayt ya da bu paketin
                 disindan gelen bir referans.
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

import ayak
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

warnings.simplefilter("ignore")

KOSAMADI = 3

# AYAKLAR BEYAN EDILIYOR, SAYILMIYOR. `tools/ayirt_kapi.py` kac ayagin
# tohumlandigini bildiriyor ve boleni buradan okuyor; docstring'den
# okusaydi sayi bir DUZYAZI VEKILI olurdu -- bu depoda yedi kez isiran
# sinif. Adlar kapinin kendi bastigi etiketlerle ayni tutulmali.
AYAKLAR = ayak.Defter(
    "yeniden dene",
    "ekler",
    "kayit nokta.",
    "dusurur",
    "cogaltmaz",
    "ara hal",
    "ispatsiz",
    "cift liste",
)


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


def _kurs(ad: str, *, kablola: bool = True) -> pathlib.Path:
    """Puanli soru + sonuc slaydi olan temiz bir kurs.

    "TEMIZ" = KARARLI DURUM, ve bunu tek tek saymak gerekiyor. Fikstur
    `authoring`i DOGRUDAN cagiriyor, yani sunucunun `_write` sarmalayicisini
    ATLIYOR -- oysa degismez orada kosuyor. `kablola` cagrilmazsa kurs bir
    seyi turetilmemis halde dogar (bugun: yeniden dene hedefi) ve ILK arac
    cagrisi onu onarir. O onarim CAGALMA DEGIL, bir kerelik uzlastirma --
    ama "20 cagri -> 0 degisiklik" olcusu ikisini ayirt edemez ve
    `cogaltmaz` ayagi bu yuzden bir kez kirmiziya dondu (olculdu
    2026-09-12).
    Gercek ajan yolunda pencere YOK: `add_results_slide` de `_write`ten
    geciyor, yani uzlastirma ayni arac cagrisinda oluyor.

    `kablola=False` ile hasarli hal KASITLI olarak korunur -- "yeniden
    dene" ayagi tohumunu boyle kuruyor.
    """
    CANARY.mkdir(parents=True, exist_ok=True)
    yol = CANARY / ad
    shutil.copy2(BLANK, yol)
    pkg = StoryPackage(yol)
    for i in range(2):
        authoring.add_question(pkg, None, f"S{i}", ["a", "b", "c", "d"], [i],
                               eyebrow="B",
                               feedback={"correct": "E", "incorrect": "H"})
    authoring.add_results_slide(pkg)
    if kablola:
        puanlama.kablola(pkg)
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


def _yeniden_dene_hedefi(yol: pathlib.Path) -> list[tuple[str, str]]:
    """Sonuc slaydindaki `gotoFirstInQuizTrig` hedefleri: (actSubType, ad)."""
    pkg = StoryPackage(yol)
    index = model.slide_index(pkg)
    g2ad = {ref.guid: ad for ad, ref in index.items()}
    out = []
    for ad in index:
        kok = pkg.parse(pkg.slide_part_for(ad))
        for trig in kok.iter("gotoFirstInQuizTrig"):
            veri = trig.find("data")
            if veri is None:
                continue
            slayt = veri.find("slide")
            g = (slayt.get("jumpG") or "").strip() if slayt is not None else ""
            out.append((veri.get("actSubType") or "",
                        g2ad.get(g, "COZULMEZ" if g else "YOK")))
    return out


def kanarya() -> list[str]:
    kusur: list[str] = []

    # 0. YENIDEN DENE HEDEFI -- ertelenmis bir notun kapanisi.
    #
    # `clone._kopuk_atlamalari_onar` cozulmeyen her atlamayi "sonraki
    # slayt"a ceviriyor ve kendi notu sinirini yaziyordu: yeniden dene
    # dugmesi icin bu ANLAMCA yanlis. Erteleme gerekcesi "sonuc slaydi
    # bugun hicbir quiz'e kayitli degil" idi -- `kablola` bir degismez
    # oldugundan o gerekce artik gecersiz, ve hedef TURETILEBILIR.
    #
    # AYAK DORT YONLU, cunku ucu tek basina yetmiyor:
    #   tohum   hasarli hal GERCEKTEN dogmus mu (yoksa ayak bos gecer)
    #   onarim  hedef ilk KAYITLI soruya baglaniyor mu
    #   kararli ikinci cagri DEGISIKLIK URETMEMELI (sifir yazma
    #           ozelligini bozmak, "cogaltmaz" ayagini da yalanlardi)
    #   sinir   COZULEN bir hedef EZILMEMELI -- kasitli olabilir
    # TOHUM KASITLI: `kablola=False` ile hasarli hal korunuyor,
    # yoksa fikstur onarilmis dogar ve ayak hicbir sey olcmez.
    yol0 = _kurs("kablolama_yeniden_dene.story", kablola=False)
    hasarli = _yeniden_dene_hedefi(yol0)
    pkg0 = StoryPackage(yol0)
    kablo0 = puanlama.kablola(pkg0)
    pkg0.save(yol0, backup=False)
    onarilmis = _yeniden_dene_hedefi(yol0)

    pkg0b = StoryPackage(yol0)
    kablo0b = puanlama.kablola(pkg0b)

    # SINIR: hedefi COZULEN baska bir slayda cevir, kablola dokunmamali
    pkg0c = StoryPackage(yol0)
    index0 = model.slide_index(pkg0c)
    baska = next((ref.guid for ad, ref in index0.items()
                  if ad != "slide.xml"), "")
    for ad in list(index0):
        kok = pkg0c.parse(pkg0c.slide_part_for(ad))
        degisti = False
        for trig in kok.iter("gotoFirstInQuizTrig"):
            veri = trig.find("data")
            slayt = veri.find("slide") if veri is not None else None
            if slayt is not None and baska:
                slayt.set("jumpG", baska)
                degisti = True
        if degisti:
            pkg0c.replace_xml(pkg0c.slide_part_for(ad), kok)
    puanlama.kablola(pkg0c)
    pkg0c.save(yol0, backup=False)
    korundu = _yeniden_dene_hedefi(yol0)

    AYAKLAR.yaz("yeniden dene",
                f"hasarli={hasarli} -> onarilmis={onarilmis}; "
                f"ikinci cagri degisti={kablo0b['degisti']}; "
                f"cozulen hedef korundu={korundu}")

    if not any(h[1] == "COZULMEZ" for h in hasarli):
        kusur.append(
            "TOHUM KOSMADI: kurulan kursta yeniden dene hedefi zaten "
            "cozuluyor, yani bu ayak ONARIMI olcmuyor. `clone`un yeniden "
            "yazma dali degismis olabilir -- once o olculmeli.")
    elif not all(h[1] != "COZULMEZ" and h[0] == "spec" for h in onarilmis):
        kusur.append(
            f"ONARILMADI: hedef {onarilmis} -- ilk kayitli soruya "
            f"baglanmasi gerekiyordu (tetikleyicinin adi "
            f"`gotoFirstInQuizTrig`, yani hedef bir tercih degil).")
    if kablo0b["degisti"]:
        kusur.append(
            "KARARLI DEGIL: ikinci `kablola` cagrisi yine yaziyor. Sifir "
            "yazma ozelligi bozulursa her arac cagrisi dosyayi buyutur.")
    if baska and not all(h[1] != "slide.xml" for h in korundu):
        kusur.append(
            "COZULEN HEDEF EZILDI: kablola, cozulen bir yeniden-dene "
            "hedefini kendi turettigiyle degistirdi. Sinir dar olmaliydi: "
            "yalnizca COZULMEYEN hedef onarilir.")

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
    AYAKLAR.yaz("ekler", f"kayit {len(once)} -> silindi -> {len(sonra)}")
    if sonra != once:
        kusur.append(f"DEGISMEZ EKLEMIYOR: kayitlar silindikten sonra bir "
                     f"yazma gecti ama {sorted(once - sonra)} geri gelmedi")

    # 6. KAYIT NOKTASINDA -- ayni kosu, SORUYLA ILGISIZ bir aracla yapildi.
    #    (1. ayak zaten `set_theme_font` kullaniyor; bu satir onu iddia
    #    olarak YAZIYOR ki kural arac basina tasinirsa ayak dussun.)
    AYAKLAR.yaz("kayit nokta.", f"onarim `set_theme_font` cagrisindan gecti "
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
    AYAKLAR.yaz("dusurur", f"{hedef} etkilesimsiz -> kayitli mi: "
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
    AYAKLAR.yaz("cogaltmaz", f"{len(kablo3)} yazma cagrisi -> {len(yazan)} "
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
    AYAKLAR.yaz("ara hal", f"soru var, sonuc slaydi yok -> degisti="
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
        AYAKLAR.yaz("ispatsiz", f"cozulemeyen kayit duruyor={duruyor}, "
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

    # 7. CIFT LISTE -- YAZICI, STORYLINE'IN OKUDUGU LISTEYE YAZAR
    #
    # AYNI TURETMENIN IKI UYGULAMASI VARDI ve quiz'i farkli buluyorlardi:
    #     kablola            quizMgr.findall("quizLst")[0]   okunan liste
    #     register_question  next(iter(story.iter("quiz")))  her listeye iner
    # Ikincisi `izleme`nin kendi docstring'inin uyardigi kalip. Olculdu
    # (2026-09-16, MCP `add_question`, test/_canary/cift_liste.log): ilk
    # liste bos, quiz ikincide (yks/tuzla sekli) -> yeni sorunun guid'i
    # IKINCI listeye yazildi; kablola okunan listeyi bos bulup hicbir sey
    # raporlamadi; arac yanitinda uyari yok. Kontrol kolu (tek liste):
    # guid liste 0'da, zincir temiz.
    #
    # IDDIA DAR: "atilan listeye yazmaz". Cift listeli dosyada puanlamanin
    # CALISTIGINI iddia etmiyor -- o sekli `zincir`in 0 numarali kosulu
    # zaten bildiriyor ve onarimi ayri bir karar.
    yol7 = _kurs("kablolama_cift_liste.story")
    pkg7 = StoryPackage(yol7)
    st7 = pkg7.parse("story/story.xml")
    mgr7 = st7.find("quizMgr")
    ilk7 = mgr7.find("quizLst")
    mgr7.insert(list(mgr7).index(ilk7), mgr7.makeelement("quizLst", {}))
    pkg7.replace_xml("story/story.xml", st7)
    pkg7.save(yol7, backup=False)
    once7 = {r.guid for r in model.slide_index(StoryPackage(yol7)).values()}
    _, hata7 = asyncio.run(_kosu(yol7, [("add_question", {
        "prompt": "Cift liste?", "choices": ["a", "b"], "correct": [0],
        "feedback": {"correct": "E", "incorrect": "H"}})]))
    if hata7 == [ACILMADI]:
        return [ACILMADI]
    pkg7b = StoryPackage(yol7)
    yeni7 = [r.guid for r in model.slide_index(pkg7b).values()
             if r.guid not in once7]
    atilan7 = []
    listeler7 = pkg7b.parse("story/story.xml").find("quizMgr").findall("quizLst")
    for liste in listeler7[1:]:
        for quiz in liste:
            ids = {(e.text or "").strip()
                   for e in (quiz.find("questionIdLst") or [])}
            atilan7 += [g for g in yeni7 if g in ids]
    AYAKLAR.yaz("cift liste", f"yeni soru {len(yeni7)}, ATILAN listeye "
                              f"yazilan {len(atilan7)} (liste {len(listeler7)})")
    if hata7:
        kusur.append(f"KANARYA KURULAMADI (cift liste): {hata7[0]}")
    elif not yeni7:
        kusur.append("KANARYA KURULAMADI (cift liste): add_question yeni "
                     "slayt kurmadi")
    elif atilan7:
        kusur.append("YAZICI ATILAN LISTEYE KAYDETTI: ilk quizLst bos, quiz "
                     "ikincide; yeni soru Storyline'in kaydederken ATACAGI "
                     "quiz'e yazildi ve arac bunu bildirmedi")
    return kusur


def main() -> int:
    if ISTEMCI_YOK:
        print(f"KOSAMADI: mcp istemcisi yok ({ISTEMCI_YOK}).")
        return KOSAMADI
    if not BLANK.exists():
        print(f"KOSAMADI: fikstur yok ({BLANK}).")
        return KOSAMADI
    kusur = kanarya()
    # DEFTERIN IKINCI YONU: beyanli ama BASILMAYAN ayak. Ilk yon
    # (`yaz` beyansiz adi reddediyor) kapiyi ayak kazandiginda korur;
    # bu yon, ayak KALDIRILDIGINDA korur -- beyanda duran olu bir ayak
    # `ayirt_kapi`nin bolenini sisirir ve kapsam OLDUGUNDAN KOTU
    # gorunur. Ikisi birlikte beyani tek deger yapiyor.
    _kosmayan = AYAKLAR.kosmayanlar()
    if _kosmayan:
        kusur.append("BEYANDA DURAN AMA KOSMAYAN AYAK: %s -- ya ayak "
                     "kaldirildi ve beyan guncellenmedi (kapsam siser), "
                     "ya da bir kosulun arkasinda kaldi ve kapi bunu "
                     "'KOSMADI' diye yazmali" % ", ".join(_kosmayan))
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
    #
    # "BUGUN FARK YOK" ARTIK DOGRU DEGIL -- OLCULDU 2026-09-14. Bu not
    # asimetriyi dogru yaziyordu ama zararsiz sayiyordu ("bayat kayit
    # `delete_shape` istiyor ve kurucu onu kullanmiyor"). Kapsam eksikti:
    # kablolamanin `yeniden_dene` ayagi `delete_shape` istemiyor ve
    # kurucunun ciktisinda ATESLENIYOR. produced.py'nin taze kursunda
    # olculdu:
    #
    #     kablola(...) -> {'yeniden_dene': ['slidef.xml'], digerleri 0}
    #
    # Yani sonuc slaydindaki "SINAVI YENIDEN DENE" dugmesi panelden
    # uretilen her kursta OLUYDU: tohumun kopuk hedefi "sonraki slayt"a
    # cevrilmis, sonuc slaydi kursun sonunda oldugu icin sonraki slayt yok.
    # `builder.build` artik kaydetmeden hemen once `puanlama.kablola`
    # cagiriyor; asimetri kapandi, not kanit olarak kaliyor.
    print("        DEGISMEZ MCP YOLUNDA kuruldu (`server._write`); panelin")
    print("        kurucu yolu `pkg.save`i dogrudan cagirdigi icin DISARIDA")
    print("        kalmisti. Fark olculdu (2026-09-14): 'yeniden dene'")
    print("        dugmesi uretilen her kursta oluydu. `builder.build` artik")
    print("        kaydetmeden once kablolamayi kosuyor.")
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
