"""Bir düzene verilen argüman çizilmiyorsa çağıran bunu bilsin.

`section`e `buttons` vermek sessizce hicbir sey yapmiyordu. Ogrenciye
gidecek icerik kayboluyor, hicbir sey bagirmiyor, ve slayt "basarili"
donuyor. Bugun sema o duzene `buttons` teklif etmedigi icin kusur
ULASILAMAZ durumda -- ama erisilebilirligi tek bir prompt duzenlemesiyle
degisir. "Bugun ulasilamiyor" bu depoda bir koruma sayilmadi.

IKI SEY VAR VE IKISI AYRI:
  BEYAN   compose.dusecek(layout, verilen) -- bu duzene BU alanlar
          verilirse hangileri cizilmez. Bir IDDIA, kod degil.
  GERCEK  bu kapinin olctugu sey: sentinel metinler verilir, uretilen
          slaydin butun yazilari taranir, hangisi ortaya cikmamis diye
          bakilir.

KARSILASTIRMA IKI YONLU, ve tek yonlu olsaydi ikisi de kacardi:
  beyan var, cizim var   -> beyan FAZLA GENIS. Cagirana "bu cizilmiyor"
                            denir ama ciziliyor; yanlis bir uyari, zamanla
                            butun uyarilari degersizlestirir.
  cizim yok, beyan yok   -> SESSIZ KAYIP. Aranan kusur tam olarak bu.

KUMELER GEZILIR, TEK KUME OLCULMEZ -- VE BU DERS PAHALIYA OGRENILDI.
Ilk surum her duzeni TEK bir arguman kumesiyle (hepsi dolu) olcuyordu ve
su matrisi uretti:

    section    bullets, buttons, eyebrow          <- YANLIS
    statement  bullets, buttons, eyebrow, index   <- YANLIS

Ikisi de o kumede dogru, davranisin tamami olarak yanlisti:
    section    eyebrow'u YALNIZCA `index` de verilmisse duser (ikisi ayni
               yuvaya giriyor; index verilince kutu `Numeral` oluyor)
    statement  title'i YALNIZCA `body` ve `eyebrow` birlikte verilmisse
               duser (iki metin yuvasi var, uc metin sigmiyor)

Tek kumeyle olcen bir prob, kosullu bir davranisi SABIT gorur -- cunku
kosul her cagride saglaniyordu. Bu, kosmayan dalin kosup hicbir sey
yapmayan daldan ayirt edilememesinin ikizi: sonuc ikisinde de ayni.
Care sonucu degil DALIN GEZILDIGINI iddia etmek, yani kumeyi gezdirmek.

USLUP EKSENI de acik: en genis kume dort uslupte ayri ayri olculur.

TURKCE BUYUK HARF TUZAGI, ve bu olcunun ILK kosusunda yakalandi: `eyebrow`
`buyuk()`ten geciyor, 'i' -> 'İ' oluyor, ve Python'un `.lower()`i onu
'i' + birlesik nokta olarak geri veriyor. Sentineller bu yuzden i/I/ı/İ
TASIMIYOR ve karsilastirma ayrica NFKD ile ASCII'ye katlaniyor. Ilk
kosuda sekiz duzenin SEKIZI de "eyebrow dusuruyor" dedi; hicbiri
dogru degildi.

DORT AYAK, ve her biri otekiler yesilken kirmiziya donebilir:
  1 beyan <-> cizim, HER KUMEDE, iki yonlu
  2 en genis kume dort uslupte ayni mi
  3 beyan cagirana ULASIYOR mu (compose_slide donusundeki `cizilmeyen`)
  4 sema PLANLAYICIYA ulasiyor mu (panel/agent.py, __DUZEN_YOKSAYAR__),
    ve KOSULLARIYLA birlikte mi
Ucuncusu olmadan 1-2 dogru bir tabloyla ve sessiz bir donusle gecilirdi;
dorduncusu olmadan tablo dogru olup planlayici yine habersiz kalirdi.

BES EKILMIS KUSURUN BESI DE KIRMIZIYA DONDURDU (olculdu 2026-09-08):
    beyan DAR   (section'dan buttons cikarildi) -> "SESSIZCE dusuyor"
    beyan GENIS (section'a title eklendi)       -> "yanlis uyari gider"
    KOSUL DUZLESTIRILDI (section eyebrow'u kosulsuz duser yapildi)
        -> ['eyebrow'] ve ['eyebrow','title'] kumelerinde yakalandi, yani
           ESKI PROBUN HIC UGRAMADIGI kumelerde. Tek kume gezen surum bu
           kusuru goremezdi ve bu, kume gezmenin tek cumlelik gerekcesi.
    donus bosaltildi (cizilmeyen=[])            -> "cagirana SOYLEMIYOR"
    semadan kosul satiri silindi                -> "prompt KOSULU tasimiyor"

    python tools/dusen_arguman.py
    python tools/dusen_arguman.py --yaz    olculen yuzeyi kume kume bas
"""

from __future__ import annotations

import argparse
import itertools
import shutil
import sys
import unicodedata
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from storyline_mcp import compose, model
from storyline_mcp.package import StoryPackage

BLANK = ROOT.parent / "test" / "bos.story"
WORK = ROOT.parent / "test" / "_canary" / "dusen_arguman_{}.story"

# Sentineller: i/I/ı/İ YOK (Turkce buyuk harf tuzagi), ve hicbiri
# digerinin alt dizisi DEGIL -- "ZQEAZ" ile "ZQEABZ" olsaydi biri
# otekini bulur ve dusen bir arguman bulunmus sayilirdi.
ARGS: dict[str, object] = {
    "title":   "ZQABZ",
    "eyebrow": "ZQBCZ",
    "body":    "ZQCDZ metnabc bwrada durwyor ve okwnabalar olmasa gerekar.",
    "bullets": ["ZQEAZ", "ZQEBZ", "ZQECZ", "ZQEDZ"],
    "buttons": ["ZQFAZ"],
    "index":   "ZQGAZ",
}

# GEZILEN KUMELER. Uc metin alani birbiriyle yuva icin yarisiyor
# (`content = body or title`, `etiket = eyebrow or title`), yani kosullar
# orada doguyor; yapisal alanlar ya hep duser ya hic. O yuzden metin
# alanlarinin BUTUN alt kumeleri, her biri yapisal alanlarla ve onlarsiz:
# 7 x 2 = 14 kume.
#
# 14 KUMENIN YETTIGI OLCULDU, VARSAYILMADI (2026-09-08). Alti alanin
# BUTUN alt kumeleri gezildi -- 63 kume x 8 duzen = 504 kurulum, 114s --
# ve hicbirinde beyan ile cizim ayrismadi. Yani 14'luk gezinti, 63'lukle
# ayni yuzeyi 4.4 kat ucuza veriyor.
#
# Bu satir once "olculdu ki yeni kosul acmiyor" diye YAZILMISTI ve
# olculmemisti; iddia ile olcum arasindaki farki bu dosyanin kendi konusu
# yaptiktan sonra birakilacak bir bosluk degildi.
METIN_ALANLARI = ("title", "eyebrow", "body")
YAPI_ALANLARI = frozenset({"bullets", "buttons", "index"})


def kombolar() -> list[frozenset[str]]:
    out: list[frozenset[str]] = []
    for r in range(1, len(METIN_ALANLARI) + 1):
        for alt in itertools.combinations(METIN_ALANLARI, r):
            out.append(frozenset(alt))
            out.append(frozenset(alt) | YAPI_ALANLARI)
    return out


def _katla(metin: str) -> str:
    """Karşılaştırma biçimi: NFKD + ASCII + küçük harf."""
    return unicodedata.normalize("NFKD", metin).encode(
        "ascii", "ignore").decode().lower()


def _izler(deger: object) -> list[str]:
    if isinstance(deger, list):
        return [_katla(str(v)) for v in deger]
    return [_katla(str(deger).split()[0])]


def olc(layout: str, verilen: "frozenset[str] | set[str]",
        style: str = "rail") -> set[str]:
    """Bu düzen+üslupta, BU alanlar verildiğinde çizilmeyenler."""
    yol = Path(str(WORK).format(style))
    shutil.copy2(BLANK, yol)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pkg = StoryPackage(yol)
        slide = [r.basename for r in model.slide_index(pkg).values()][0]
        compose.compose_slide(
            pkg, slide, layout, style=style, identity="arguman",
            **{k: (list(v) if isinstance(v, list) else v)
               for k, v in ARGS.items() if k in verilen})
        pkg.save(yol, backup=False)
    done = StoryPackage(yol)
    root = done.parse(done.slide_part_for(slide))
    govde = _katla(" ".join(
        (model.shape_text(root, el.get("g") or "") or "")
        for el in list(root.find("shapeLst") or [])))
    return {ad for ad in verilen
            if any(iz not in govde for iz in _izler(ARGS[ad]))}


def kanarya() -> list[str]:
    """Ölçü koşuyor mu, ve KOŞULU görüyor mu. IKI YONLU."""
    kusur = []
    # DUYARLILIK, ve bilerek KOSULLU bir cift uzerinde: tek kume olcen bir
    # prob bu ikisini ayirt edemez, ve ayirt edememesi bu aracin daha once
    # yayimladigi matrisi yanlis yapmisti.
    yok = olc("section", {"eyebrow", "title"})
    var = olc("section", {"eyebrow", "title", "index"})
    print(f"kanarya kosul: section eyebrow -> index'siz "
          f"{'DUSTU' if 'eyebrow' in yok else 'cizildi'}, "
          f"index'li {'DUSTU' if 'eyebrow' in var else 'cizildi'}")
    if "eyebrow" in yok:
        kusur.append("olcu YANLIS ALARM veriyor: section index'siz "
                     "eyebrow'u ciziyor (olculdu) ama olcu dusmus sayiyor")
    if "eyebrow" not in var:
        kusur.append("olcu KOR: section `index` ile eyebrow'u dusuruyor "
                     "(olculdu) ama olcu onu cizilmis sayiyor")
    return kusur


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--yaz", action="store_true",
                        help="olculen yuzeyi kume kume bas")
    args = parser.parse_args()

    kusur = kanarya()
    if kusur:
        print("\nKANARYA KALDI. Asagidaki tablo okunmamali:")
        for k in kusur:
            print(f"  - {k}")
        return 1

    kume_listesi = kombolar()
    sorunlar: list[str] = []
    kosullu_bulunan: list[str] = []

    # 1. AYAK: her duzen, HER KUME, iki yonlu.
    for layout in compose.LAYOUTS:
        for verilen in kume_listesi:
            olculen = olc(layout, verilen)
            beyan = compose.dusecek(layout, set(verilen))
            if args.yaz and olculen:
                print(f"  {layout:<10} {sorted(verilen)} -> {sorted(olculen)}")
            for ad in sorted(beyan - olculen):
                sorunlar.append(
                    f"{layout} {sorted(verilen)}: `{ad}` beyanda DUSUYOR "
                    f"yaziyor ama ciziliyor — cagirana yanlis uyari gider")
            for ad in sorted(olculen - beyan):
                sorunlar.append(
                    f"{layout} {sorted(verilen)}: `{ad}` SESSIZCE dusuyor ve "
                    f"beyanda yok — cagiran icerigin kayboldugunu bilmiyor")
        for alan in compose.ICERIK_ALANLARI:
            tetik = compose.kosul_of(layout, alan)
            if tetik:
                kosullu_bulunan.append(
                    f"{layout}.{alan} <- {' + '.join(sorted(tetik))}")
    print(f"\n{len(compose.LAYOUTS)} duzen x {len(kume_listesi)} kume = "
          f"{len(compose.LAYOUTS) * len(kume_listesi)} kurulum olculdu.")
    print(f"kosullu davranis: {', '.join(kosullu_bulunan) or 'yok'}")

    # 2. AYAK: en genis kume dort uslupte ayni mi.
    tum = frozenset(ARGS)
    for layout in compose.LAYOUTS:
        per = {st: olc(layout, tum, st) for st in sorted(compose.STYLES)}
        if len({frozenset(v) for v in per.values()}) != 1:
            sorunlar.append(
                f"{layout}: dusen alanlar USLUBA GORE degisiyor "
                f"{ {k: sorted(v) for k, v in per.items()} } — tek satirlik "
                f"bir beyan bunu anlatamaz")
    print(f"uslup ekseni: {len(compose.STYLES)} uslup x "
          f"{len(compose.LAYOUTS)} duzen, en genis kume")

    # 3. AYAK: beyan cagirana ULASIYOR mu.
    yol = Path(str(WORK).format("donus"))
    shutil.copy2(BLANK, yol)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pkg = StoryPackage(yol)
        slide = [r.basename for r in model.slide_index(pkg).values()][0]
        sonuc = compose.compose_slide(pkg, slide, "section", title="Baslik",
                                      buttons=["Devam"], identity="arguman")
    bildirilen = sonuc.get("cizilmeyen")
    print(f"donus degeri: section + buttons -> cizilmeyen={bildirilen}")
    if bildirilen != ["buttons"]:
        sorunlar.append(f"compose_slide donusu cagirana SOYLEMIYOR: "
                        f"cizilmeyen={bildirilen!r}, ['buttons'] bekleniyordu")

    # 4. AYAK: sema PLANLAYICIYA ulasiyor mu, KOSULLARIYLA birlikte mi.
    try:
        sys.path.insert(0, str(ROOT / "panel"))
        import agent as _agent
        prompt = _agent.SYSTEM_PROMPT
    except Exception as exc:                       # pragma: no cover
        sorunlar.append(f"prompt okunamadi, sema planlayiciya ulasiyor mu "
                        f"SINANAMADI: {type(exc).__name__}: {str(exc)[:60]}")
    else:
        if "__DUZEN_YOKSAYAR__" in prompt:
            sorunlar.append("prompt'taki __DUZEN_YOKSAYAR__ token'i "
                            "DOLDURULMAMIS — planlayici semayi gormuyor")
        gomulu = prompt.split("HER DUZEN HER ALANI")[-1][:1600]
        eksik = [l for l in compose.LAYOUTS
                 if compose.dusecek(l, set(compose.ICERIK_ALANLARI))
                 and l not in gomulu]
        if eksik:
            sorunlar.append(f"prompt semasinda eksik duzen(ler): {eksik} — "
                            f"planlayici o duzenin yok saydiklarini bilmiyor")
        # KOSULLAR DA GITMELI. Kosulsuz yazilmis bir sema en sik durumda
        # yanlis uyari verir: planlayici `section`a eyebrow'u hic
        # gondermez, oysa index'siz section onu gayet ciziyor.
        for satir in kosullu_bulunan:
            alan = satir.split(" <- ")[0].split(".")[1]
            if f"+ {alan}:" not in gomulu:
                sorunlar.append(f"prompt semasi KOSULU tasimiyor ({satir}) — "
                                f"planlayici alani kosulsuz duser sanir")
        print(f"prompt semasi: {len(compose.LAYOUTS)} duzen gomulu, "
              f"{len(kosullu_bulunan)} kosul gomulu")

    if sorunlar:
        print("\nSORUN:")
        for s in sorunlar:
            print(f"  ! {s}")
        return 1
    print("\nBeyan ile cizim HER KUMEDE ortusuyor; beyan cagirana ve "
          "planlayiciya ulasiyor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
