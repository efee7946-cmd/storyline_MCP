"""Ilerleme seridinin dort adimi GERCEKTEN besleniyor mu.

NICIN VAR. Serit adimi bir sure DURUM METNINDEN tahmin ediyordu: panel
"calisiyor: add_slide" dizgesinde "slayt" gecip gecmedigine bakiyordu.
Arac adlari Ingilizce, anahtar kelimeler Turkceydi. Olculdu 2026-09-14:
54 aracin 52'si hicbir adimi yakmiyordu -- yalniz `list_quiz` ("quiz")
ve `audit` ("audit") tutuyordu. Serit kosu boyunca 1. adimda kaliyor,
2. adim HIC yanmiyordu, ve bu kirilma SESSIZDI: kutular ciziliyordu,
yalnizca hicbiri renk degistirmiyordu.

Vekil olarak duzyazi -- bu depoda tekrar eden sinif. Sayi artik tek
yerde, `panel/agent.py:TOOL_ADIM`'da hesaplaniyor. Bu kapi o tablonun
IZIN LISTESIYLE ORTUSTUGUNU denetler; kaymanin iki yonu de kapali:

    TOOLS'ta var, tabloda yok  -> yeni arac eklendi, serit onu goremez
    Tabloda var, TOOLS'ta yok  -> arac kaldirildi, tablo olu satir tutuyor

Ikinci yon de onemli: olu satirlar tablonun kapsamini OLDUGUNDAN IYI
gosterir, ve "her arac siniflanmis" ifadesini anlamsizlastirir.

UCUNCU AYAK bir sayi degil, bir KANARYA: sahte bir arac TOOLS'a ekilip
kapinin gercekten kirmizi dondugu olculuyor. Yesil bir kapi, denetledigi
sey yanlis olsaydi da yesil kalabilir; kanarya bunu ayirir.

DORDUNCU AYAK CSS: `.hide` kurali stil sayfasinin basinda ve tek sinif
ozgullugunde; asagida tanimlanan her tek-sinif `display` kurali esitlikte
onu YENIYOR. Serit ve bos durum cubugu hicbir komut calismamisken bile
ekranda kaliyordu, cunku `classList.add("hide")` hicbir sey yapmiyordu.
`!important` olmadan kusur, asagiya eklenecek bir sonraki `display`
kuraliyla sessizce geri gelir.

    python tools/adim_kapi.py
"""

from __future__ import annotations

import pathlib
import re
import sys

import ayak

KOK = pathlib.Path(__file__).resolve().parent.parent
# URUNUN YOLUNUN AYNISI, fazlasi degil: `panel/app.py` tam olarak bu iki
# dizini ekliyor (once storyline-mcp/, sonra panel/). Kapi buraya kendi
# kolayligi icin bir sey eklemez -- eklerse, urunun patlayacagi bir
# import'u gormeden yesil doner.
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(KOK / "panel"))

import agent                                                  # noqa: E402

PANEL = KOK / "panel" / "index.html"
ADIMLAR = (1, 2, 3, 4)

AYAKLAR = ayak.Defter(
    "tablo ortusuyor",
    "adimlar besleniyor",
    "ekilmis kusur",
    "hide kurali",
    genislik=20,
)


def _ortusme(tools, tablo) -> list[str]:
    kusur = []
    eksik = [a for a in tools if a not in tablo]
    fazla = [a for a in tablo if a not in tools]
    if eksik:
        kusur.append(
            "TOOLS'ta var, TOOL_ADIM'da YOK: %s. Bu araclar seridi hic "
            "oynatmaz ve bunu kimse fark etmez -- tabloda siniflayin "
            "(okuyan bir arac icin 0)." % ", ".join(sorted(eksik)))
    if fazla:
        kusur.append(
            "TOOL_ADIM'da var, TOOLS'ta YOK: %s. Olu satir; tablonun "
            "kapsamini oldugundan iyi gosterir." % ", ".join(sorted(fazla)))
    return kusur


def main() -> int:
    kusur: list[str] = []
    tools = list(agent.TOOLS)
    tablo = dict(agent.TOOL_ADIM)

    # 1 -- IZIN LISTESIYLE ORTUSME. Ice aktariliyor, ayristirilmiyor.
    ortusme_kusuru = _ortusme(tools, tablo)
    AYAKLAR.yaz("tablo ortusuyor",
                "%d arac / %d satir -- %s"
                % (len(tools), len(tablo),
                   "ortusuyor" if not ortusme_kusuru else "SAPMA"))
    kusur += ortusme_kusuru

    # 2 -- HER ADIMIN BESLEYICISI VAR MI. 1. adim arac ile yanmaz (kosu
    # basinda kurulur), bu yuzden yalniz 2-3-4 araca bagli. Bir adim
    # besleyicisiz kalirsa o kutu hic renk degistirmez -- kirilmanin ilk
    # halinin TAM OLARAK bu oldugu olculdu.
    dagilim = {a: sorted(k for k, v in tablo.items() if v == a)
               for a in ADIMLAR}
    okuma = sorted(k for k, v in tablo.items() if v == 0)
    bos = [a for a in (2, 3, 4) if not dagilim[a]]
    AYAKLAR.yaz("adimlar besleniyor",
                "okuma=%d  2=%d  3=%d  4=%d%s"
                % (len(okuma), len(dagilim[2]), len(dagilim[3]),
                   len(dagilim[4]), "" if not bos else "  <- BOS: %s" % bos))
    if bos:
        kusur.append(
            "Su adimlarin hicbir besleyici araci yok: %s. O kutular kosu "
            "boyunca renk degistirmez." % ", ".join(str(a) for a in bos))
    gecersiz = {k: v for k, v in tablo.items() if v not in (0, 2, 3, 4)}
    if gecersiz:
        kusur.append(
            "Gecersiz adim degeri: %s. Izinli: 0 (okuma), 2, 3, 4. "
            "1. adim araca baglanmaz." % gecersiz)

    # 3 -- EKILMIS KUSUR. Kapi denetledigi sey yanlis olsa kirmizi doner mi.
    ekili = _ortusme(tools + ["__ekilmis_arac__"], tablo)
    AYAKLAR.yaz("ekilmis kusur",
                "sahte arac eklendi -> %s"
                % ("YAKALANDI" if ekili else "KACTI"))
    if not ekili:
        kusur.append(
            "Ekilmis kusur KACTI: TOOLS'a sahte bir arac eklendiginde kapi "
            "hala yesil. Ortusme denetimi hicbir sey olcmuyor.")

    # 4 -- CSS. Duzyazi degil, tek bir bildirimin kendisi okunuyor.
    try:
        css = PANEL.read_text(encoding="utf-8")
    except OSError as hata:
        AYAKLAR.yaz("hide kurali", "index.html OKUNAMADI (%s)" % hata)
        kusur.append("index.html okunamadi: %s. Bu ayak KOSMADI." % hata)
    else:
        kural = re.search(r"^\s*\.hide\s*\{([^}]*)\}", css, re.M)
        metin = (kural.group(1).strip() if kural else "(kural yok)")
        onemli = bool(kural) and "!important" in kural.group(1)
        AYAKLAR.yaz("hide kurali", "%s -> %s"
                    % (metin, "korunuyor" if onemli else "KORUMASIZ"))
        if not onemli:
            kusur.append(
                "`.hide` kurali `!important` tasimiyor (%s). Kural stil "
                "sayfasinin basinda ve tek sinif ozgulluginde: asagidaki "
                "her tek-sinif `display` kurali esitlikte onu yener ve "
                "`classList.add(\"hide\")` sessizce hicbir sey yapmaz."
                % metin)

    kosmayan = AYAKLAR.kosmayanlar()
    if kosmayan:
        kusur.append("Beyanda olup KOSMAYAN ayak: %s." % ", ".join(kosmayan))

    print()
    if kusur:
        for k in kusur:
            print("  KUSUR: %s" % k)
        print("ADIM KAPISI: %d ayak, KALDI (%d kusur)"
              % (len(AYAKLAR), len(kusur)))
        return 1
    print("ADIM KAPISI: %d ayak, %d gecti, 0 kaldi, 0 BAKILMADI"
          % (len(AYAKLAR), len(AYAKLAR)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
