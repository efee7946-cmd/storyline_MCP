"""Tema doğrulamasının ölçülebilir yarısı: okunuyor mu, ve gerçekten farklı mı.

GÖREV 5 renk getiriyor ve `silhouette.py` renge kör -- konumsal bir ölçü.
"variety GECTI" cümlesi tema hakkında hiçbir şey söylemez, ve bunu baştan
söylemezsek zamanla "kurs çeşitli" diye okunur. O yüzden tema üç ayrı soruya
bölündü; üçünü tek sayıda toplamak, bu oturumda "en büyük bant" ile "toplam
boş"u karıştırmakla aynı hata olurdu:

  1. ISKELET CESITLILIGI   -> tools/variety.py     (konumsal, renge kor)
  2. OKUNABILIRLIK         -> burada, olculur      (yazi zemininden ayrisiyor mu)
  3. PALET AYRIKSILIGI     -> burada, olculur      (iki kurs gercekten farkli mi)
  4. TEMA GUZEL MI         -> yalnizca gozle       (sayisi yok, olmayacak)

Dorduncusu icin sayi uretmeyecegim. Uretilen sayi, olculmeyen bir seyi
olculmus gibi gosterir ve bu oturumda kovalanan hatanin tasarim tarafindaki
hali olur.

OKUNABILIRLIK neden burada olculebilir hale geldi: yazinin arkasindaki rengi
bilmek gerekiyor ve slaydin kendi zemini (<bg>) bu oturumda okunmaya basladi.
Oncesinde her slayt beyaz sayiliyordu, dolayisiyla mor zemindeki beyaz yazi
"kontrast sorunu" gibi gorunurdu -- olculmeyen bir hayalet.

Esikler WCAG 2.1 AA: normal yazi 4.5, buyuk yazi (>=18pt, ya da kalin >=14pt)
3.0. Bunlar tercih degil, yayimlanmis esikler.

VE BU GUARD TEK YONLU KALIYOR, bilerek. 4.5'in ustundeki bir iyilesme
kaydedilmez ve korunmaz. deadband ile donor havuzunda ayni yapi bir kusurdu
-- orada esik OLCULEN bir degerdi ve kaydedilmeyen kazanim sessizce geri
donebiliyordu. Burada esik dis bir standart: 7.2 kontrastin 5.0'a inmesi bir
gerileme degil, hala gecerli bir tasarim. Korunacak bir taban cizgisi yok.

    python tools/contrast.py kurs.story
    python tools/contrast.py a.story b.story --palette
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from storyline_mcp import model, preview, shapes
from storyline_mcp.package import StoryPackage
import scope

AA_NORMAL, AA_LARGE = 4.5, 3.0
LARGE_PT, LARGE_BOLD_PT = 18.0, 14.0


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


_TEMA_ONBELLEK: dict[int, dict] = {}


def tema_slotlari(pkg) -> dict:
    """Yuva adı → renk. Master'lar AYRIŞIYORSA boş döner (çözmez).

    schemeClr bir YUVA ADI tasir (accent1, lt1, dk1, custom1...) ve gercek
    renk temadan gelir. Cozulmezse `_paints` bos doner, zemin varsayilana
    duser ve arac kendi korlugunu kontrast hatasi diye raporlar -- olculdu,
    uretilen kursta 56 vaka.

    IKI TUZAK OLCULDU, ikisi de bu dosyalarda YOK ama kural yine de burada:

      donusum   schemeClr uzerine lumMod/lumOff/alpha binebilir; ham slot
                rengini alip donusumu atlamak sayi uretir ama YANLIS. Cocuk
                dugum varsa cozum REDDEDILIR.
      esleme    Office'te lt1/dk1 gibi adlar clrMap/clrMapOvr ile yeniden
                eslenebilir. Esleme varsa cozum REDDEDILIR.

    UCUNCU: proje birden cok master tasiyor (olculdu: dorder tane) ve bir
    slaydin hangisine bagli oldugu guvenilir okunamiyor. Bu dosyalarda
    master'larin HEPSI her slotta ayni degeri veriyor, yani secim karari
    degistirmiyor -- ama ayristigi bir dosyada degistirir. O yuzden ayrisma
    varsa cozum REDDEDILIR, "ilk master" varsayilmaz.
    """
    key = id(pkg)
    if key in _TEMA_ONBELLEK:
        return _TEMA_ONBELLEK[key]
    try:
        from storyline_mcp import settings
        masters = settings.read_theme(pkg)["masters"]
    except Exception:
        masters = []
    out: dict = {}
    if masters:
        slotlar = set()
        for m in masters:
            slotlar |= set(m.get("colors") or {})
        for slot in slotlar:
            degerler = {m.get("colors", {}).get(slot) for m in masters}
            degerler.discard(None)
            if len(degerler) == 1:
                out[slot] = degerler.pop()
    _TEMA_ONBELLEK[key] = out
    return out


# schemeClr uzerine binen donusumler. Uygulanmazlarsa ham slot rengi YANLIS
# sonuc verir; olculdu (2026-08-18, iki kurs):
#
#     solidFill  schemeClr + tint     25      + shade   25    + alpha  48
#     gradFill   schemeClr + satMod/lumMod/tint/shade   66
#     gradOvrlyFill duraklari: schemeClr + tint + satMod   HEPSI
#
# ILK SURUMUM BU KONTROLU YANLIS YERDE YAPTI: donusumleri `schemeClr`'in
# COCUKLARINDA aradi, oysa `<clr>` icinde KARDES duruyorlar. Yani kontrol
# hicbir zaman tetiklenmedi ve ham slot rengi doner hale geldi -- olculen
# "73 vaka cozuldu" iyilesmesinin bir kismi yanlis renkti.
#
# Kullanicinin uyarisi tam olarak buydu ve yine de yapildi; ders, uyariyi
# duymanin kontrolu DOGRU YERE koymak anlamina gelmedigi.
DONUSUMLER = ("tint", "shade", "alpha", "lumMod", "lumOff", "satMod",
              "hueMod", "grad")

# UYGULANABILEN donusumler. Listede OLMAYAN her donusum cozumu REDDETTIRIR --
# "bilmedigimi atla" degil, "bilmedigim varsa olcme".
#
# `alpha` bilerek DISARIDA: renk donusumu degil SAYDAMLIK. Efektif renk
# altindaki zemine baglidir ve `_paints` alpha'yi zaten ayri kanalda tasiyip
# `_over` ile harmanliyor; burada da uygulamak IKI KEZ saymak olurdu.
# `grad` da disarida: durak listesi, tek renk degil.
UYGULANABILIR = ("tint", "shade", "lumMod", "lumOff", "satMod")


def _hsl(rgb):
    r, g, b = (c / 255 for c in rgb)
    mx, mn = max(r, g, b), min(r, g, b)
    l = (mx + mn) / 2
    if mx == mn:
        return 0.0, 0.0, l
    d = mx - mn
    s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
    if mx == r:
        h = ((g - b) / d + (6 if g < b else 0)) / 6
    elif mx == g:
        h = ((b - r) / d + 2) / 6
    else:
        h = ((r - g) / d + 4) / 6
    return h, s, l


def _rgb_den_hsl(h, s, l):
    def kanal(p, q, t):
        t = t % 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p
    if s == 0:
        v = round(l * 255)
        return (v, v, v)
    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    return tuple(max(0, min(255, round(kanal(p, q, t) * 255)))
                 for t in (h + 1 / 3, h, h - 1 / 3))


def _donusum_uygula(rgb, clr):
    """<clr> içindeki dönüşümleri BELGE SIRASINDA uygular.

    ZEMIN: ECMA-376 (DrawingML) tanimlari, OLCUM DEGIL. Sira onemli ve
    XML'deki yazim sirasi uygulama sirasidir -- 66 vakada satMod/lumMod/
    tint/shade birlikte geliyor ve farkli sirada farkli renk cikar.

      tint/shade  RGB'de dogrusal karisim (beyaza / siyaha)
      lumMod      HSL parlaklik carpani
      lumOff      HSL parlaklik ekleme
      satMod      HSL doygunluk carpani

    lumMod/lumOff/satMod HSL uzayindadir; RGB'de uygulamak YANLIS sonuc
    verir ve bu, sayinin uretilip yanlis olmasi sinifidir.
    """
    for el in clr:
        ad = el.tag
        if ad == "schemeClr" or ad == "srgbClr":
            continue
        if ad == "alpha":
            # SAYDAMLIK, RENK DONUSUMU DEGIL. `preview._alpha_of` bunu ayri
            # kanalda okuyor ve `_over` zeminle harmanliyor; burada da
            # uygulamak IKI KEZ saymak olurdu. Atlanir, REDDEDILMEZ.
            #
            # Ilk surum reddediyordu ve yorumu "ayri kanalda tasiniyor"
            # diyordu -- yorum ile kod celisiyordu, ve bedeli 32 vakanin
            # bosuna "olculemedi" sayilmasiydi.
            continue
        if ad not in UYGULANABILIR:
            return None                      # bilinmeyen donusum -> olculemez
        try:
            v = float(el.get("val", "0")) / 100000.0
        except ValueError:
            return None
        if ad == "tint":
            rgb = tuple(round(c * v + 255 * (1 - v)) for c in rgb)
        elif ad == "shade":
            rgb = tuple(round(c * v) for c in rgb)
        else:
            h, sat, l = _hsl(rgb)
            if ad == "lumMod":
                l = l * v
            elif ad == "lumOff":
                l = l + v
            elif ad == "satMod":
                sat = sat * v
            rgb = _rgb_den_hsl(h, max(0.0, min(1.0, sat)),
                               max(0.0, min(1.0, l)))
        rgb = tuple(max(0, min(255, c)) for c in rgb)
    return rgb


def _scheme_rengi(clr, slotlar: dict):
    """<clr><schemeClr val=.../></clr> → renk; dönüşüm varsa None.

    Cagiran `<clr>` SARMALAYICISINI verir, `schemeClr`'i degil: donusumler
    orada kardes olarak duruyor ve schemeClr'a bakarak gorulemezler.
    """
    if clr is None or not slotlar:
        return None
    sch = clr.find("schemeClr")
    if sch is None:
        return None
    deger = slotlar.get(sch.get("val") or "")
    if not deger or not deger.startswith("#"):
        return None
    return _donusum_uygula(_rgb(deger), clr)


def _paints(shape: ET.Element, *, direct: bool = False,
            slotlar: dict | None = None) -> list[tuple[tuple[int, int, int], float]]:
    """Bir öğenin dolgusundaki renkler ve opaklıkları.

    Degrade tek renge indirgenmez: her durak ayrı bir aday olarak döner ve
    okunabilirlik en KOTU durak uzerinden karara baglanir. Ortalamasini almak,
    yazinin bir ucta okunmadigi gercegini gizler.
    """
    base = "" if direct else "bG/"
    out = []
    grad = shape.find(f"{base}gradFill")
    if grad is not None:
        for stop in grad.findall("stops/stop"):
            srgb = stop.find("clr/srgbClr")
            if srgb is not None and srgb.get("val"):
                out.append((_rgb(srgb.get("val")),
                            preview._alpha_of(stop.find("clr"))))
                continue
            renk = _scheme_rengi(stop.find("clr"), slotlar or {})
            if renk is not None:
                out.append((renk, preview._alpha_of(stop.find("clr"))))
        if out:
            return out
    # `find(a) or find(b)` YAZILMAZ: cocugu olmayan bir Element falsy'dir ve
    # <srgbClr/> tam olarak oyledir, dolayisiyla bulunan dogru sonuc atlanir
    # ve dolgu "yok" sayilir. Ilk kosuda her yazinin arkasi beyaz cikti,
    # yani arac kendi korlugunu kontrast hatasi diye raporladi.
    srgb = shape.find(f"{base}solidFill/clr/srgbClr")
    if srgb is None:
        srgb = shape.find(f"{base}solidFill/srgbClr")
    if srgb is not None and srgb.get("val"):
        out.append((_rgb(srgb.get("val")),
                    preview._alpha_of(shape.find(f"{base}solidFill/clr"))))
        return out
    # TEMA YUVASI. srgbClr yoksa dolgu schemeClr ile verilmis olabilir --
    # elle yapilmis kursta 34 sekil YALNIZCA boyle (olculdu). Cozulemezse
    # bos donmeye devam eder ve cagiran "olculemedi" der; sessizce
    # varsayilan renge dusmez.
    clr = shape.find(f"{base}solidFill/clr")
    if clr is not None:
        renk = _scheme_rengi(clr, slotlar or {})
        if renk is not None:
            out.append((renk, preview._alpha_of(clr)))
    return out


def _over(top: tuple[tuple[int, int, int], float],
          under: tuple[int, int, int]) -> tuple[int, int, int]:
    (r, g, b), alpha = top
    return tuple(round(c * alpha + u * (1 - alpha)) for c, u in ((r, under[0]),
                                                                 (g, under[1]),
                                                                 (b, under[2])))


def _luminance(rgb: tuple[int, int, int]) -> float:
    def channel(value: int) -> float:
        v = value / 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(fore: tuple[int, int, int], back: tuple[int, int, int]) -> float:
    a, b = sorted((_luminance(fore), _luminance(back)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def _behind(shapes_in_order: list, index: int, centre: tuple[float, float],
            ground: tuple[int, int, int],
            slotlar: dict | None = None) -> list[tuple[int, int, int]]:
    """Yazının arkasındaki renk adayları, çizim sırasına göre.

    Bir yazının arkasında ne olduğu, çizim sırasıyla belirlenir: ondan ÖNCE
    çizilmiş, merkezini içeren ve dolgusu olan en son şekil. Kendi dolgusu
    varsa (buton) o kazanır. Yarı saydam bir örtü altındakiyle harmanlanır --
    kompozisyon hero görsellerde tam olarak bunu kullanıyor.
    """
    stack: list[tuple[tuple[int, int, int], float]] = []
    for i in range(index + 1):
        shape = shapes_in_order[i]
        rect = shapes.shape_rect(shape)
        if not rect:
            continue
        left, top, right, bottom = rect
        if not (left <= centre[0] <= right and top <= centre[1] <= bottom):
            continue
        paints = _paints(shape, slotlar=slotlar)
        if paints:
            stack.append(paints)
    result = [ground]
    for paints in stack:
        result = [_over(p, base) for base in result for p in paints]
    # Aday sayisi degradelerle carpilarak buyuyebilir; en koyu ve en acik
    # ucu tutmak yeterli, cunku en kotu kontrast hep bir ucta olur.
    result.sort(key=_luminance)
    return [result[0], result[-1]] if len(result) > 2 else result


def _kaplar(root):
    """(nere, çizim sırası, ölçülecek ilk indeks) — TEMEL ve her KATMAN.

    KATMAN METNI TEMEL SLAYDIN USTUNE CIZILIR. Bir katman yazisinin
    arkasindaki yigin `temel + katman` siralamasidir; katmani tek basina
    taramak zemini beyaz sanar ve aracin kendi korlugu kontrast hatasi diye
    raporlanir -- bu dosyada bir kez tam olarak oyle oldu (bkz. _paints).

    UCUNCU ELEMAN, temel sekillerin IKI KEZ olculmesini onler: katman
    kabinda onlar yalnizca ZEMIN olarak duruyor, olcum katmanin kendi
    sekillerinden basliyor.

    KESIT ACILDI (2026-08-18). Olculdu: themes_check, contrast ve
    check_no_overlap -- ucu de sldLayerLst'i atliyordu. Uretilen kursun
    geri bildirim katmanlarinda donorden kalan iki renk vardi (#92D050,
    #FF0000) ve hicbir kontrol onlari GOREMIYORDU.
    """
    temel = list(root.find("shapeLst") or [])
    out = [("temel", temel, 0)]
    katmanlar = root.find("sldLayerLst")
    for i, katman in enumerate(list(katmanlar) if katmanlar is not None else [], 1):
        ust = list(katman.find("shapeLst") or [])
        if ust:
            out.append((f"katman{i}", temel + ust, len(temel)))
    return out


def _dolgu_etkin(shape, etiket: str) -> bool:
    """Bu dolgu etiketi GERÇEKTEN boya sürüyor mu?

    `gradOvrlyFill` bir ORTUDUR ve `overlayFillType` ile acilip kapanir.
    Olculdu (2026-08-18, iki kurs):

        overlayFillType="None"      1064 kez   -> ORTU KAPALI, boyamiyor
        overlayFillType="Default"    717 kez   -> ANLAMI OLCULMEDI
        overlayFillType="Gradient"      1 kez  -> duraklarini boyuyor

    Kapali ortuyu "dolgusu var ama okunamiyor" saymak, seffaf bir kutuyu
    opak sanmak demek -- ve tam olarak oyle oldu: uretilen kursta zemini
    okunamayan 56 yazinin 52'sini engelleyen sey kapali bir ortuydu.
    Yazi aslinda ALTTAKI zemin uzerinde duruyor.

    "Default" REDDEDILIYOR, cunku ne yaptigi olculmedi. Tahmin etmek bu
    oturumda uc kez yanlis cikti (copiedG, <trig>, verG).
    """
    el = next(shape.iter(etiket), None)
    if el is None:
        return False
    # noFill ADI USTUNDE: dolgu YOK. "Dolgu etiketi var" diye opak saymak,
    # seffaf bir kutuyu zemin sanmak olur ve altindaki gercek zemini gizler.
    if etiket == "noFill":
        return False
    if etiket == "gradOvrlyFill":
        tur = (el.get("overlayFillType") or "").lower()
        if tur == "none":
            return False          # ortu kapali: seffaf say, altina bak
        if tur == "gradient":
            return True
        return True               # "Default": olculmedi -> okunamaz say
    return True


def _zemin_cozuldu(shapes_in_order: list, index: int,
                   centre: tuple[float, float],
                   slotlar: dict | None = None) -> bool:
    """Bu yazının arkasında GERÇEKTEN okunabilen bir dolgu var mı?

    `_behind` dolgu bulamazsa varsayilan zemini dondurur ve cagiran bunu
    olculmus bir renk sanar. Iki dolgu sinifi bugun cozulmuyor ve ikisi de
    olculdu (2026-08-18):

        gradOvrlyFill   overlayFillType="None" -> ortu KAPALI, boyamiyor
        schemeClr       temaya bagli; elle yapilmis kursta 34 sekil
                        YALNIZCA schemeClr tasiyor ve srgbClr yok

    Ikisi de cozulene kadar, o yazilarin kontrasti OLCULEMEZ.
    """
    # EN USTTEKI KAPSAYAN SEKIL BELIRLER, herhangi biri degil. Ilk surum
    # "yiginda boyali bir sey var mi" diye soruyordu ve fazla gevsekti:
    # metnin hemen altindaki panel cozulemese bile, ALTTAKI beyaz slayt
    # zemini bulunuyor ve sonuc "beyaz uzerine beyaz" cikiyordu -- yani
    # arac yine kendi korlugunu raporluyordu, sadece bir kat asagidan.
    #
    # Dogru soru: metnin ARKASINDAKI ilk dolgulu sekil OKUNABILIYOR MU.
    # Dolgu ETIKETI var ama rengi cozulemiyorsa (schemeClr, kapali
    # gradOvrlyFill) zemin BILINMIYOR demektir ve olcum yapilamaz.
    for i in range(index, -1, -1):
        shape = shapes_in_order[i]
        rect = shapes.shape_rect(shape)
        if not rect:
            continue
        if not (rect[0] <= centre[0] <= rect[2] and rect[1] <= centre[1] <= rect[3]):
            continue
        dolgu_var = any(_dolgu_etkin(shape, t) for t in shapes.FILL_TAGS)
        if not dolgu_var:
            continue          # seffaf: altindakine bak
        return bool(_paints(shape, slotlar=slotlar))
    return False


def audit(pkg: StoryPackage, *, katmanlar: bool = True,
          olculemeyenler: bool = False) -> list[dict]:
    """Kontrast ihlalleri. Katman taraması VARSAYILAN OLARAK ACIK.

    ACILDI (2026-09-05). Bir donem KAPALIYDI ve o da olculmus bir karardi:
    kesit acikken uretilen kursta 12 "bulgu" cikiyordu ve hepsi
    `#FFFFFF uzerine #FFFFFF, oran 1.00` idi. Gerekce dogruydu -- kendi
    korlugunu kusur diye raporlayan bir kontrol, hic bakmayandan KOTUDUR:
    insanlari bakmamaya alistirir ve gercek bulguyu gurultuye gomer.

    AMA O 12 BULGU KORLUK DEGILDI. 2026-09-05'te tek tek olculdu: yazinin
    altinda COZULEBILIR, gercek bir #FFFFFF kart duruyordu. Yani kesit
    kapatilirken varsayim "hepsi gurultu" idi; dogrusu "hepsi GERCEK" imis
    ve kapali kapinin arkasindan uretime gitti. Uc kaynak bulundu ve
    duzeltildi:

        reveal katmanlari      builder._reveal_katmanlari palete baglanmamisti
        sonuc slaydi katmani   ilerleme.kur palete baglanmamisti
        bos sablon             katmanlarinda "Tebrikler, sinavi gectin!"
                               yazan kurs artiklari vardi

    Bugunku olcum, kesit ACIKKEN:

        uretilmis.story      0 bulgu, 0 korluk   (91 olculemeyen, SESSIZ)
        6 tema fiksturu      0 bulgu, 0 korluk

    Cozulemeyen zemin sinifi (kapali `gradOvrlyFill`) HALA VAR ama gurultu
    uretmiyor: `_zemin_cozuldu` onlari "olculemeyen" kovasina ayiriyor ve
    olculemeyen yalnizca acikca istenirse doner (K18). Sayilari buyurse
    zemin cozumunun geriledigini soyler.

    KAPSAM, ve saklanmiyor: bu "0 korluk" URETILEN dosyalar icin olculdu.
    Elle yapilmis `test/_referans/referans.story` uzerinde kesit acikken 10
    bulgu cikiyor ve olculdu: hicbiri gercek beyaz-uzerine-beyaz DEGIL --
    o dosyada 24 seklin zemini hic cozulemiyor. Yani korluk bu kesitte
    BITMEDI, uretim yolunda bitti. Hicbir kapiyi kirmizi yapmiyor
    (`referans` zaten bilerek bozuk bir cipa), ama elle yapilmis bir kursa
    bu araci dogrultan biri o gurultuyu gorur.
    """
    findings = []
    slotlar = tema_slotlari(pkg)
    for part, ref in model.slide_index(pkg).items():
        root = pkg.parse(part)
        # ESLEME VARSA COZUM REDDEDILIR. clrMap/clrMapOvr yuva adlarini
        # yeniden esler ve ham slot rengini almak yanlis sayi uretir.
        # Bu dosyalarda yok (olculdu) ama kural olcume degil VARLIGA bakar.
        yerel = {} if any(next(root.iter(t), None) is not None
                          for t in ("clrMap", "clrMapOvr")) else slotlar
        ground_paint = preview.slide_ground(root, [])
        ground = (255, 255, 255)
        if ground_paint and ground_paint.startswith("#"):
            ground = _rgb(ground_paint)
        kaplar = _kaplar(root) if katmanlar else _kaplar(root)[:1]
        for nere, order, bastan in kaplar:
            for index in range(bastan, len(order)):
                shape = order[index]
                text = model.shape_text(root, shape.get("g", "")).strip()
                rect = shapes.shape_rect(shape)
                if not text or not rect:
                    continue
                colour, size, bold, _align = preview._text_style(shape)
                centre = ((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2)
                need = AA_LARGE if (size >= LARGE_PT
                                    or (bold and size >= LARGE_BOLD_PT))                     else AA_NORMAL
                # ZEMIN GERCEKTEN COZULDU MU. Cozulmediyse `_behind` varsayilan
                # zemini (beyaz) geri verir ve arac KENDI KORLUGUNU kontrast
                # hatasi diye raporlar -- bu dosyada iki kez oldu, ikincisi
                # kesit katmanlara acildiginda: uretilen kursta 12 bulgu
                # cikti ve hepsi `#FFFFFF uzerine #FFFFFF, oran 1.00` idi.
                #
                # Cozulemeyen vaka IHLAL DEGIL, OLCULEMEYEN'dir ve oyle
                # raporlanir (K18). Susturmak degil: sayisi ayrica basiliyor,
                # cunku buyumesi zemin cozumunun gerilediğini soyler.
                if not _zemin_cozuldu(order, index, centre, yerel):
                    # SOZLESME KORUNUYOR: cagiranlar `len(audit(pkg))` aliyor
                    # ve olculemeyen bir vakayi ihlal saymak, kapilari sahte
                    # sayilarla doldurur -- denendi, `produced` 0'dan 56'ya
                    # cikti. Olculemeyen yalnizca ACIKCA istenirse doner.
                    if not olculemeyenler:
                        continue
                    findings.append({
                        "slide": ref.basename, "name": ref.name[:28],
                        "nere": nere, "text": text[:34], "fore": colour,
                        "back": None, "size": size, "ratio": None,
                        "need": need, "en_iyi": None, "belirsiz": False,
                        "olculemedi": True,
                    })
                    continue
                arkalar = _behind(order, index, centre, ground, yerel)
                if not arkalar:
                    continue
                oranlar = [ratio(_rgb(colour), b) for b in arkalar]
                worst, best = min(oranlar), max(oranlar)
                against = arkalar[oranlar.index(worst)]
                if worst < need:
                    findings.append({
                        "slide": ref.basename, "name": ref.name[:28],
                        "nere": nere,
                        "text": text[:34], "fore": colour,
                        "back": "#%02X%02X%02X" % against,
                        "size": size, "ratio": worst, "need": need,
                        # ZEMIN BELIRSIZSE ARALIK, tek sayi DEGIL.
                        # Degradeler ve yari saydam ortuler birden cok zemin
                        # adayi birakir. En iyi aday esigi geciyor ama en
                        # kotu gecmiyorsa karar "zemine bagli"dir; tek sayi
                        # basmak, olculemeyeni olculmus gibi gostermek olur
                        # (K18).
                        "en_iyi": best,
                        "belirsiz": best >= need > worst,
                    })
    return findings


def palette(pkg: StoryPackage, slides: list[str] | None = None) -> dict[str, float]:
    """Kursun renk dağılımı: hangi renk, alanın ne kadarını kaplıyor.

    slides verilirse yalnizca o slaytlar sayilir -- tek dosyada birden fazla
    tema tasiyan bir prob icin gerekli.
    """
    keep = set(slides) if slides else None
    weights: dict[str, float] = {}
    for part, _ref in model.slide_index(pkg).items():
        if keep is not None and _ref.basename not in keep:
            continue
        root = pkg.parse(part)
        shape_list = root.find("shapeLst")
        for shape in list(shape_list) if shape_list is not None else []:
            rect = shapes.shape_rect(shape)
            if not rect:
                continue
            area = (rect[2] - rect[0]) * (rect[3] - rect[1])
            for rgb, alpha in _paints(shape):
                key = "#%02X%02X%02X" % rgb
                weights[key] = weights.get(key, 0.0) + area * alpha
    total = sum(weights.values()) or 1.0
    return {k: v / total for k, v in sorted(weights.items(),
                                            key=lambda kv: -kv[1])}


# İki rengin "başka renk" sayılması için gereken sRGB uzaklığı. Ölçekte üst
# sınır 441 (siyah-beyaz); 120, aynı tonun iki komşusu ile gerçekten farklı iki
# rengi ayıracak kadar geniş.
COLOR_APART = 120.0


def _apart(a: str, b: str) -> float:
    ra, ga, ba = _rgb(a)
    rb, gb, bb = _rgb(b)
    # Goz yesile en duyarli, maviye en az; agirliklar bunu kabaca yansitir.
    d = (2 * (ra - rb) ** 2 + 4 * (ga - gb) ** 2 + 3 * (ba - bb) ** 2) ** 0.5
    return min(d / COLOR_APART, 1.0)


def palette_distance(a: dict[str, float], b: dict[str, float]) -> float:
    """0 = aynı palet, 1 = ortak hiçbir tona yaklaşmıyor. Alanla ağırlıklı.

    Renkler HEX olarak eşleştirilmez. Eşleştirilseydi ölçü doyuma ulaşırdı:
    `derive_palette` her marka rengi için tamamen farklı hex değerleri üretir,
    dolayısıyla dört ayrı palet birbirine 1.000 uzaklıkta çıkar -- ve aynı
    sayı, `#0E1B3D` ile `#0E1B3E` arasında da çıkardı. Ayırt etme gücü
    olmayan bir ölçü, "tema çalıştı" sorusuna cevap veremez.

    Bunun yerine her renk, öteki paletteki EN YAKIN tonla eşleştirilir ve
    maliyet o tonla arasındaki algısal uzaklık kadardır. Simetrik olsun diye
    iki yönün ortalaması alınır.
    """
    if not a or not b:
        return 1.0

    def one_way(src: dict[str, float], dst: dict[str, float]) -> float:
        return sum(weight * min(_apart(colour, other) for other in dst)
                   for colour, weight in src.items())

    return (one_way(a, b) + one_way(b, a)) / 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("stories", nargs="+")
    parser.add_argument("--palette", action="store_true",
                        help="kurslarin paletlerini karsilastir")
    args = parser.parse_args()

    packages = [(Path(s).name, StoryPackage(Path(s).resolve()))
                for s in args.stories]

    if args.palette:
        if len(packages) < 2:
            print("Palet karsilastirmasi icin en az iki kurs gerekir.")
            return 2
        tables = [(name, palette(pkg)) for name, pkg in packages]
        for name, table in tables:
            top = ", ".join(f"{k} %{v*100:.0f}" for k, v in
                            list(table.items())[:4])
            print(f"  {name:<28} {top}")
        print()
        for i, (name_a, table_a) in enumerate(tables):
            for name_b, table_b in tables[i + 1:]:
                distance = palette_distance(table_a, table_b)
                mark = "  <- AYNI PALET" if distance < 0.15 else ""
                print(f"  {name_a:<24} {name_b:<24} {distance:.3f}{mark}")
        return 0

    failures = 0
    for name, pkg in packages:
        findings = audit(pkg)
        failures += len(findings)
        print(f"\n{name}: {len(findings)} okunabilirlik uyarisi")
        for f in findings[:25]:
            print(f"  {f['slide']:<12} {f['ratio']:.2f} (>= {f['need']}) "
                  f"{f['fore']} / {f['back']}  {f['size']:.0f}pt  "
                  f"\"{f['text']}\"")
    if failures:
        print("\nYAZI ZEMININDEN YETERINCE AYRISMIYOR. Onizlemede goze "
              "carpmayabilir;\nWCAG esigi tercihe degil olcume dayanir.")
        return 1
    print("\nButun yazilar esigin uzerinde.")
    scope.show("contrast")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
