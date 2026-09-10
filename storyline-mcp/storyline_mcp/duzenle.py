"""Var olan şekli TAŞI ya da SİL -- ajanın kendi hatasını düzeltebilmesi için.

NICIN VAR. Arac yuzeyinin 52 aracinin hepsi EKLIYORDU; hicbiri
duzeltmiyordu. Sonucu su: bir slayt bir kez yanlis kurulduysa kapaniyor.
Tek "geri alma" yolu `compose_slide`in slaydi bastan cizmesiydi ve
`emniyet` kapisi -- hakli olarak -- dolu slaytta onu reddediyor. Yani
ajan kusuru GORUYOR (audit, slide_layout, ve artik reddin gerekcesi de
okunabiliyor) ama eli yok.

SILME REFERANS KIRAR, VE SESSIZ KIRAR. Bir sekli silmek yalnizca
`shapeLst`ten bir ogeyi cikarmak degil: o guid'e bakan tetikleyiciler
(`change_state`in `shapeG`si, katman acan `objG`), soru seceneklerinin
`intrProps` esletmesi ve sekle gomulu kendi tetikleyicileri de o guid'e
bagli. Silip birakmak "basarili" doner ve kurs Storyline'da sessizce
bozulur -- bu deponun kapattigi kusur sinifinin ta kendisi.

O yuzden silme ONCE SORAR: bu guid'e kim bakiyor. Bakan varsa REDDEDER
ve neyin kirilacagini yazar; `compose_slide`in yeniden beste reddiyle
ayni bicim, ayni gerekce. Kirilacak seyi kaldirip gecmek bir tarif
DEGILDIR.

TASIMA `shapes.set_loc`E DAYANIR, kendi `loc`unu yazmaz: durum
(state) tasiyan bir sekil dis kutusundan cizilmiyor ve yalnizca dis
kutuyu tasimak isabet alanini oynatip resmi yerinde birakiyor -- bu
zaten olculmus ve `set_loc`un icinde yaziyor.
"""

from __future__ import annotations

from . import model, shapes
from .logic import _shape_by
from .package import StoryPackage, StoryError

# Bir sekil silinince onunla BIRLIKTE giden, ve gitmesi DOGRU olan sey:
# seklin kendi trigLst'i. Storyline nesne olaylarini (OnClick vb.) daima
# nesnenin kendi listesinde tutuyor (olculdu, bagisci havuzu), yani sekil
# gidince onlar da anlamsiz kaliyor. Yine de SAYILIR ve raporlanir.


def _guid_referanslari(root, guid: str, sekil) -> list[str]:
    """Bu guid'e sekil'in DISINDAN kim bakiyor. Bos liste = silmek guvenli."""
    if not guid:
        return []
    icinde = {el for el in sekil.iter()}
    bulgular = []
    for el in root.iter():
        if el in icinde:
            continue
        for anahtar, deger in el.attrib.items():
            if deger != guid or anahtar == "g":
                continue
            bulgular.append(f"<{el.tag} {anahtar}>")
    return sorted(set(bulgular))


def _sekil_bul(root, tanim: str):
    """guid -> AD -> metin sirasiyla coz. Bu cozucu logic'inkinden GENIS.

    `logic._shape_by` (ve altindaki `_shape_by_text_or_guid`) yalnizca
    guid ve METIN esliyor; ada BAKMIYOR. Tasima/silme icin bu yetmez,
    cunku ajanin elindeki adres `slide_layout`tan geliyor ve orada her
    seklin `name` alani var -- "Title", "Body", "Gorsel Alani" gibi
    metni OLMAYAN sekiller de var, ve onlar metinle hic bulunamaz
    (olculdu: compose'un kurdugu slaytta `Title` aramasi bos donuyor,
    cunku o seklin METNI "Baslik").

    Genis olmak, belirsiz olmak DEGIL: ayni adi tasiyan birden fazla
    sekil varsa SECMIYOR, listeyi yazip birakiyor. Sessizce ilkini
    almak, ajanin baska bir sekli tasidigini/sildigini fark etmemesi
    demekti.
    """
    from . import model as _model
    guid_ile = _model._find_by_guid(root, tanim)
    if guid_ile is not None:
        return guid_ile

    aranan = tanim.casefold().strip()
    liste = root.find("shapeLst")
    ad_ile = [el for el in (list(liste) if liste is not None else [])
              if (el.get("name") or "").casefold().strip() == aranan]
    if len(ad_ile) > 1:
        raise StoryError(
            f"{tanim!r} adini tasiyan {len(ad_ile)} sekil var; hangisi "
            f"oldugu belirsiz. slide_layout ile bakip guid verin.")
    if ad_ile:
        return ad_ile[0]

    bulunan = _shape_by(root, tanim)
    if bulunan is None:
        raise StoryError(
            f"{tanim!r} ile eslesen sekil yok. slide_layout ile slayttaki "
            f"sekillerin adlarini ve metinlerini gorebilirsiniz.")
    return bulunan


def sekil_tasi(pkg: StoryPackage, slide: str, shape: str, *,
               x: float | None = None, y: float | None = None,
               w: float | None = None, h: float | None = None) -> dict:
    """Sekli tasi/boyutlandir. x/y/w/h slaydin YUZDESI (0-100), piksel degil.

    Verilmeyen alan KORUNUR: yalnizca `y` vermek sekli dikey oynatir,
    genisligine dokunmaz.
    """
    part = pkg.slide_part_for(slide)
    root = pkg.parse(part)
    sekil = _sekil_bul(root, shape)
    kutu = shapes.shape_rect(sekil)
    if kutu is None:
        raise StoryError(
            f"{shape!r} seklinin konumu okunamiyor (<loc> yok): bu sekil "
            f"tasinamaz.")
    genislik, yukseklik = shapes.slide_size(root)
    l, t, r, b = kutu
    yeni_l = l if x is None else genislik * x / 100.0
    yeni_t = t if y is None else yukseklik * y / 100.0
    yeni_g = (r - l) if w is None else genislik * w / 100.0
    yeni_y = (b - t) if h is None else yukseklik * h / 100.0
    shapes.set_loc(sekil, yeni_l, yeni_t, yeni_l + yeni_g, yeni_t + yeni_y)
    pkg.replace_xml(part, root)

    def yuzde(a, ust):
        return round(a / ust * 100.0, 1)

    return {
        "slide": slide,
        "shape": sekil.get("name") or shape,
        "onceki": {"x": yuzde(l, genislik), "y": yuzde(t, yukseklik),
                   "w": yuzde(r - l, genislik), "h": yuzde(b - t, yukseklik)},
        "yeni": {"x": yuzde(yeni_l, genislik), "y": yuzde(yeni_t, yukseklik),
                 "w": yuzde(yeni_g, genislik), "h": yuzde(yeni_y, yukseklik)},
    }


def sekil_sil(pkg: StoryPackage, slide: str, shape: str) -> dict:
    """Sekli sil -- ONCE o guid'e kimin baktigina bakarak.

    Referans varsa REDDEDER. Sessizce silip kirmak, `compose_slide`in
    dolu slaydi bastan cizmesiyle ayni sinifta bir kayip olurdu.
    """
    part = pkg.slide_part_for(slide)
    root = pkg.parse(part)
    sekil = _sekil_bul(root, shape)
    liste = root.find("shapeLst")
    if liste is None or sekil not in list(liste):
        raise StoryError(
            f"{shape!r} slaydin ust duzey sekli degil (katman icinde ya da "
            f"bir grubun uyesi olabilir); buradan silinemez.")

    guid = sekil.get("g") or ""
    referanslar = _guid_referanslari(root, guid, sekil)
    if referanslar:
        raise StoryError(
            f"{slide}: {shape!r} silinemez -- bu sekle {len(referanslar)} yerden "
            f"referans var ({', '.join(referanslar[:4])}). Silmek onlari "
            f"KIRAR ve kirilma Storyline'da ancak dosya acilinca gorunur. "
            f"REFERANSLARI KALDIRARAK GECILMEMELI: baska bir sekil secin, ya "
            f"da once o baglantiyi kuran tetikleyiciyi/soruyu degistirin.")

    kendi_trig = sekil.find("trigLst")
    giden_trig = len(kendi_trig) if kendi_trig is not None else 0
    metin = " ".join((model.shape_text(root, guid) or "").split())[:60]
    liste.remove(sekil)
    pkg.replace_xml(part, root)
    return {
        "slide": slide,
        "silinen": sekil.get("name") or shape,
        "tur": sekil.tag,
        "metni": metin,
        "birlikte_giden_tetikleyici": giden_trig,
        "not": ("Seklin KENDI tetikleyicileri onunla birlikte gitti "
                "(Storyline nesne olaylarini nesnenin kendi listesinde "
                "tutar). Slayt duzeyindeki tetikleyiciler etkilenmedi."
                if giden_trig else ""),
    }
