"""`overlayFillType="Default"` boyuyor mu? SONUCUNDAN olculur.

BAYRAGIN ANLAMI TAHMIN EDILMEZ -- iki okumanin BEDELI olculur. Dosyadan iki
hipotez zaten dustu (2026-09-05): Default duz dolguyla birlikte gelmiyor, ve
"hepsi sentinel" ayirt etmiyor cunku `None` da tam-sentinel olabiliyor.
Goruntu yolu da ORTAM engeline takildi (bkz. shoot_preview.py "BILINEN SINIR").

KANIT NEREDEN GELIYOR. Insanlarin Storyline'da yaptigi gercek kurslar ezici
cogunlukla OKUNABILIR -- yazar ekranda gordugunu duzeltir. O halde bayragin
DOGRU okumasi gercek kurslarda okunabilir bir tablo uretmeli; YANLIS okuma
ise olmayan kontrast ihlalleri UYDURMALI. Ayirt eden sey bu.

KORPUS YALNIZCA INSAN YAPIMI. `donors/` altindaki kurslar profesyonel
Storyline yazarlarinin isi. Bu projenin URETTIGI dosyalar kanit olamaz:
onlarin ortuleri zaten bu kod tarafindan yazildi, yani kendi varsayimimizi
geri okurduk (dairesel). `referans.story` de disarida -- bilerek bozuk cipa.

UC DURUM VAR, IKI DEGIL:

    A  Default SEFFAF        ortuyu atla, ALTTAKI dolguya bak
    B  Default BOYUYOR       zemin, ortunun kendi duraklari
    S  simdiki hal           "dolgu var ama cozulemiyor" -> OLCULEMEYEN

S bir okuma degil, okumayi REDDETME. Bu arac A ile B'yi karsilastirir; S
ancak ikisi de ayirt etmezse yerinde kalir.

YALNIZCA AYIRAN VAKALAR SAYILIR. A ile B ayni KARARA variyorsa (ikisi de
gecti, ya da ikisi de kaldi) o vaka hicbir sey soylemez ve sayilmaz.

KARAR KURALI -- SAYILARA BAKILMADAN YAZILDI:

  Ayiran vaka sayisi < 20               ->  ORNEKLEM YETERSIZ, S kalir.
      Kusuru bulan orneklem, duzeltmeyi dogrulamaya yetmez.

  A'nin ihlali B'ninkinin YARISINDAN az ->  Default SEFFAF.
      `_dolgu_etkin` "default" icin False dondurmeli.

  B'nin ihlali A'ninkinin YARISINDAN az ->  Default BOYUYOR.
      `_dolgu_etkin` True kalmali ve `_paints` ortunun duraklarini okumali.

  Ikisi de degilse                      ->  AYIRT ETMEDI, S kalir.
      Iki kat fark yoksa gurultudan ayrilmaz.

    python tools/ortu_sonuc.py
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import contrast
from storyline_mcp import model, preview, shapes
from storyline_mcp.package import StoryPackage

DONOR = ROOT / "donors"


def _ortu_renkleri(shape, slotlar):
    """Bir gradOvrlyFill'in duraklari: (renk, opaklik) listesi.

    `_paints` bunu OKUMUYOR -- gradFill ve solidFill'e bakiyor. Ortunun
    duraklari ayni yapida (`stops/stop/clr`), o yuzden ayni cozumleyiciler
    kullaniliyor; kopyalanan sey YOL, mantik degil.
    """
    el = shape.find("bG/gradOvrlyFill")
    if el is None:
        return []
    out = []
    for stop in el.findall("stops/stop"):
        clr = stop.find("clr")
        if clr is None:
            continue
        srgb = clr.find("srgbClr")
        if srgb is not None and srgb.get("val"):
            out.append((contrast._rgb(srgb.get("val")), preview._alpha_of(clr)))
            continue
        renk = contrast._scheme_rengi(clr, slotlar or {})
        if renk is not None:
            out.append((renk, preview._alpha_of(clr)))
    return out


def _default_ortu(shape) -> bool:
    el = shape.find("bG/gradOvrlyFill")
    return (el is not None
            and (el.get("overlayFillType") or "").lower() == "default")


def _ilk_default(order, index, centre):
    """Yazinin altindaki yiginda ILK karsilasilan Default ortulu sekil.

    Ustunde baska bir etkin dolgu varsa vaka AYIRMAZ: o dolgu zaten zemini
    belirler ve ortunun ne yaptigi gorunmez. O yuzden orada durulur.
    """
    for i in range(index, -1, -1):
        shape = order[i]
        rect = shapes.shape_rect(shape)
        if not rect:
            continue
        if not (rect[0] <= centre[0] <= rect[2]
                and rect[1] <= centre[1] <= rect[3]):
            continue
        if _default_ortu(shape):
            return i, shape
        if any(contrast._dolgu_etkin(shape, t) for t in shapes.FILL_TAGS):
            return None, None
    return None, None


def olc(yol: Path) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pkg = StoryPackage(yol)
    slotlar = contrast.tema_slotlari(pkg)
    sonuc = {"ayiran": 0, "A_ihlal": 0, "B_ihlal": 0,
             "ayni": 0, "cozulemedi": 0}
    for part, ref in model.slide_index(pkg).items():
        root = pkg.parse(part)
        yerel = {} if any(next(root.iter(t), None) is not None
                          for t in ("clrMap", "clrMapOvr")) else slotlar
        zp = preview.slide_ground(root, [])
        zemin = (contrast._rgb(zp) if (zp or "").startswith("#")
                 else (255, 255, 255))
        for _nere, order, bastan in contrast._kaplar(root):
            for index in range(bastan, len(order)):
                shape = order[index]
                text = model.shape_text(root, shape.get("g", "")).strip()
                rect = shapes.shape_rect(shape)
                if not text or not rect:
                    continue
                colour, size, bold, _align = preview._text_style(shape)
                if not (colour or "").startswith("#"):
                    continue
                centre = ((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2)
                oi, ortu = _ilk_default(order, index, centre)
                if ortu is None:
                    continue

                b_renkler = _ortu_renkleri(ortu, yerel)
                a_renkler = contrast._behind(order, oi - 1, centre, zemin, yerel)
                if not b_renkler or not a_renkler:
                    sonuc["cozulemedi"] += 1
                    continue

                b_duz = [contrast._over(c, zemin) for c in b_renkler]
                need = (contrast.AA_LARGE
                        if (size >= contrast.LARGE_PT
                            or (bold and size >= contrast.LARGE_BOLD_PT))
                        else contrast.AA_NORMAL)
                fore = contrast._rgb(colour)
                a_en_kotu = min(contrast.ratio(fore, g) for g in a_renkler)
                b_en_kotu = min(contrast.ratio(fore, g) for g in b_duz)

                if (a_en_kotu >= need) == (b_en_kotu >= need):
                    sonuc["ayni"] += 1
                    continue
                sonuc["ayiran"] += 1
                if a_en_kotu < need:
                    sonuc["A_ihlal"] += 1
                if b_en_kotu < need:
                    sonuc["B_ihlal"] += 1
    return sonuc


def main() -> int:
    dosyalar = sorted(DONOR.glob("*.story"))
    if not dosyalar:
        print("Donor havuzu bos: %s -- kanit yok, olcum YAPILMADI." % DONOR)
        return 1
    toplam = {"ayiran": 0, "A_ihlal": 0, "B_ihlal": 0,
              "ayni": 0, "cozulemedi": 0}
    print("%-38s %7s %7s %7s %7s"
          % ("kurs", "ayiran", "A_ihl", "B_ihl", "ayni"))
    for yol in dosyalar:
        try:
            s = olc(yol)
        except Exception as exc:
            print("%-38s  HATA: %s" % (yol.name[:38], str(exc)[:40]))
            continue
        print("%-38s %7d %7d %7d %7d"
              % (yol.name[:38], s["ayiran"], s["A_ihlal"],
                 s["B_ihlal"], s["ayni"]))
        for k in toplam:
            toplam[k] += s[k]
    print("%-38s %7d %7d %7d %7d"
          % ("TOPLAM", toplam["ayiran"], toplam["A_ihlal"],
             toplam["B_ihlal"], toplam["ayni"]))
    print("  ayirmayan (iki okuma ayni karar): %d" % toplam["ayni"])
    print("  zemini hic cozulemeyen          : %d" % toplam["cozulemedi"])

    print("\nKARAR KURALI bas yorumda, SAYILARA BAKILMADAN yazildi:")
    n, a, b = toplam["ayiran"], toplam["A_ihlal"], toplam["B_ihlal"]
    if n < 20:
        print("  -> ORNEKLEM YETERSIZ (%d < 20). Default REDDEDILMEYE devam."
              % n)
        return 0
    if a * 2 < b:
        print("  -> Default SEFFAF. A'nin ihlali (%d), B'ninkinin (%d) "
              "yarisindan az." % (a, b))
    elif b * 2 < a:
        print("  -> Default BOYUYOR. B'nin ihlali (%d), A'ninkinin (%d) "
              "yarisindan az." % (b, a))
    else:
        print("  -> AYIRT ETMEDI (A=%d, B=%d; iki kat fark yok). "
              "Default REDDEDILMEYE devam." % (a, b))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
