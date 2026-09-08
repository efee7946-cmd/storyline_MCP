"""Bir düzene verilen argüman çizilmiyorsa çağıran bunu bilsin.

`section`e `buttons` vermek sessizce hicbir sey yapmiyordu. Ogrenciye
gidecek icerik kayboluyor, hicbir sey bagirmiyor, ve slayt "basarili"
donuyor. Bugun sema o duzene `buttons` teklif etmedigi icin kusur
ULASILAMAZ durumda -- ama erisilebilirligi tek bir prompt duzenlemesiyle
degisir. "Bugun ulasilamiyor" bu depoda bir koruma sayilmadi.

IKI SEY VAR VE IKISI AYRI:
  BEYAN   compose.LAYOUT_DROPS -- hangi duzen hangi argumani cizmiyor.
          Bir IDDIA, kod degil; elle tutulan her kopya koddan kayar.
  GERCEK  bu kapinin olctugu sey: sentinel metinler verilir, uretilen
          slaydin butun yazilari taranir, hangisi ortaya cikmamis diye
          bakilir.

KARSILASTIRMA IKI YONLU, ve tek yonlu olsaydi ikisi de kacardi:
  beyan var, cizim var   -> beyan FAZLA GENIS. Cagirana "bu cizilmiyor"
                            denir ama ciziliyor; yanlis bir uyari, zamanla
                            butun uyarilari degersizlestirir.
  cizim yok, beyan yok   -> SESSIZ KAYIP. Aranan kusur tam olarak bu.

USLUP EKSENI ACIK. Dort uslup ayri ayri olculur: bir tedavi bir argumani
cizmeyi birakirsa (ornegin kart yuzeyi olmayan bir uslup madde metnini
dusurse) tek uslup kosan bir kapi bunu goremezdi. Bu turda ayni kusur
uc kapida ayri ayri bulundu.

TURKCE BUYUK HARF TUZAGI, ve bu olcunun ILK kosusunda yakalandi: `eyebrow`
`buyuk()`ten geciyor, 'i' -> 'İ' oluyor, ve Python'un `.lower()`i onu
'i' + birlesik nokta olarak geri veriyor. Sentineller bu yuzden i/I/ı/İ
TASIMIYOR ve karsilastirma ayrica NFKD ile ASCII'ye katlaniyor. Ilk
kosuda sekiz duzenin SEKIZI de "eyebrow dusuruyor" dedi; hicbiri
dogru degildi.

UC EKILMIS KUSURUN UCU DE KIRMIZIYA DONDURDU (olculdu 2026-09-08); bir
kapinin dusebildigi gosterilmeden yesili bir sey ifade etmez:
    beyan DAR   (section'dan `buttons` cikarildi)  -> "SESSIZCE dusuyor"
    beyan GENIS (section'a `title` eklendi)        -> "yanlis uyari gider"
    donus bosaltildi (cizilmeyen=[])               -> "cagirana SOYLEMIYOR"
Ucuncusu ayri bir ayak ve gerekli: tablo dogru olup donus degeri bos
kalsaydi ilk iki ayak yesil kalir, kullanici yine habersiz olurdu.

    python tools/dusen_arguman.py
    python tools/dusen_arguman.py --yaz    olculen tabloyu bas (beyan icin)
"""

from __future__ import annotations

import argparse
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

# Sentineller: i/I/ı/İ YOK (Turkce buyuk harf tuzagi), ve her biri
# digerlerinin alt dizisi DEGIL -- "ZQEAZ" ile "ZQEABZ" olsaydi biri
# digerini bulur ve dusen bir arguman bulunmus sayilirdi.
ARGS: dict[str, object] = {
    "title":   "ZQABZ",
    "eyebrow": "ZQBCZ",
    "body":    "ZQCDZ metnabc bwrada durwyor ve okwnabalar olmasa gerekar.",
    "bullets": ["ZQEAZ", "ZQEBZ", "ZQECZ", "ZQEDZ"],
    "buttons": ["ZQFAZ"],
    "index":   "ZQGAZ",
}


def _katla(metin: str) -> str:
    """Karşılaştırma biçimi: NFKD + ASCII + küçük harf."""
    return unicodedata.normalize("NFKD", metin).encode(
        "ascii", "ignore").decode().lower()


def _izler(deger: object) -> list[str]:
    if isinstance(deger, list):
        return [_katla(str(v)) for v in deger]
    return [_katla(str(deger).split()[0])]


def olc(layout: str, style: str) -> set[str]:
    """Bu düzen+üslupta ÇİZİLMEYEN argümanların adları."""
    yol = Path(str(WORK).format(style))
    shutil.copy2(BLANK, yol)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pkg = StoryPackage(yol)
        slide = [r.basename for r in model.slide_index(pkg).values()][0]
        compose.compose_slide(
            pkg, slide, layout, style=style, identity="arguman",
            **{k: (list(v) if isinstance(v, list) else v)
               for k, v in ARGS.items()})
        pkg.save(yol, backup=False)
    done = StoryPackage(yol)
    root = done.parse(done.slide_part_for(slide))
    govde = _katla(" ".join(
        (model.shape_text(root, el.get("g") or "") or "")
        for el in list(root.find("shapeLst") or [])))
    return {ad for ad, deger in ARGS.items()
            if any(iz not in govde for iz in _izler(deger))}


def gercek() -> dict[str, set[str]]:
    """{duzen: cizilmeyen argumanlar} -- dört üslubun ORTAK kesişimi değil,
    BİRLEŞİMİ değil: her üslup ayrı raporlanır ve ayrışma da bir kusurdur."""
    out: dict[str, set[str]] = {}
    for layout in compose.LAYOUTS:
        per = {st: olc(layout, st) for st in sorted(compose.STYLES)}
        farkli = {frozenset(v) for v in per.values()}
        if len(farkli) != 1:
            # Uslup basina degisen bir dusme, tablonun tek satirla
            # anlatilamayacagi anlamina gelir; sessiz gecmemeli.
            out[layout] = set.union(*per.values()) | {"__uslup_ayrisiyor__"}
        else:
            out[layout] = next(iter(per.values()))
    return out


def kanarya() -> list[str]:
    """Kapı gerçekten koşuyor ve gerçekten görüyor mu. IKI YONLU."""
    kusur = []
    # DUYARLILIK: bilinen bir dusme beyandan cikarilirsa kapi bagirmali.
    # Beyan gecici olarak bozulur, sonuc olculur, geri konur.
    layout = "section"
    gercekten = olc(layout, "rail")
    print(f"kanarya duyarlilik: {layout}/rail gercekte dusurdukleri = "
          f"{sorted(gercekten) or '-'}")
    if "buttons" not in gercekten:
        kusur.append(f"olcu KOR: {layout} `buttons`i cizmiyor (olculdu, "
                     f"2026-09-08) ama olcu onu cizilmis sayiyor")
    # KARARLILIK: cizilen bir arguman yanlislikla "dusmus" sayilmamali.
    if "title" in gercekten:
        kusur.append(f"olcu YANLIS ALARM veriyor: {layout} basligi ciziyor "
                     f"ama olcu dusmus sayiyor — sentinel ya da katlama bozuk")
    return kusur


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--yaz", action="store_true",
                        help="olculen tabloyu LAYOUT_DROPS bicimiinde bas")
    args = parser.parse_args()

    kusur = kanarya()
    if kusur:
        print("\nKANARYA KALDI. Asagidaki tablo okunmamali:")
        for k in kusur:
            print(f"  - {k}")
        return 1

    olculen = gercek()
    if args.yaz:
        print("\nLAYOUT_DROPS = {")
        for layout in compose.LAYOUTS:
            deger = tuple(sorted(olculen[layout]))
            etiket = f'"{layout}":'
            print(f"    {etiket:<14} {deger!r},")
        print("}")
        return 0

    print(f"\n{'duzen':<11}{'beyan':<34}{'olculen':<34}")
    print("-" * 79)
    sorunlar = []
    for layout in compose.LAYOUTS:
        beyan = set(compose.LAYOUT_DROPS.get(layout, ()))
        olc_ = olculen[layout]
        print(f"{layout:<11}{str(sorted(beyan)):<34}{str(sorted(olc_)):<34}")
        # BEYAN VAR, CIZIM VAR: yanlis uyari.
        for ad in sorted(beyan - olc_):
            sorunlar.append(f"{layout}: `{ad}` beyanda DUSUYOR yaziyor ama "
                            f"ciziliyor — cagirana yanlis uyari gider")
        # CIZIM YOK, BEYAN YOK: SESSIZ KAYIP. Aranan kusur bu.
        for ad in sorted(olc_ - beyan):
            sorunlar.append(f"{layout}: `{ad}` verildiginde SESSIZCE dusuyor "
                            f"ve beyanda yok — cagiran icerigin kayboldugunu "
                            f"bilmiyor")

    # Beyanin cagirana GERCEKTEN ulastigini da sinar: tablo dogru olup
    # donus degeri bos kalsaydi kapi yesil, kullanici yine habersiz olurdu.
    yol = Path(str(WORK).format("donus"))
    shutil.copy2(BLANK, yol)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pkg = StoryPackage(yol)
        slide = [r.basename for r in model.slide_index(pkg).values()][0]
        sonuc = compose.compose_slide(pkg, slide, "section", title="Baslik",
                                      buttons=["Devam"], identity="arguman")
    bildirilen = sonuc.get("cizilmeyen")
    print(f"\ndonus degeri: section + buttons -> cizilmeyen={bildirilen}")
    if bildirilen != ["buttons"]:
        sorunlar.append(f"compose_slide donusu cagirana SOYLEMIYOR: "
                        f"cizilmeyen={bildirilen!r}, ['buttons'] bekleniyordu")

    if sorunlar:
        print("\nSORUN:")
        for s in sorunlar:
            print(f"  ! {s}")
        return 1
    print("\nBeyan ile cizim ortusuyor, ve beyan cagirana ulasiyor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
