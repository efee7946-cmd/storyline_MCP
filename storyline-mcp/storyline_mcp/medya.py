"""Yapay zekanin istedigi gorsel ve videolar, dosyalar gelene kadar bekleyen.

Kursu kuran model neyin ANLATILDIGINI bilir, elinde ne oldugunu bilmez. Bir
slayt icin "burada MFA ekraninin gorundugu 20 saniyelik bir video olmali"
diyebilir; o videoyu bulamaz, ureteMEZ ve bekleyemez. Kurulum durursa kurs hic
bitmez, sessizce vazgecerse slayt bos bir panelle kalir.

Bu yuzden istek KURSTAN AYRI bir yerde durur: kurs eksiksiz kurulur, istek
`<kurs>.medya.json` icinde bekler, dosya elinize gectiginde panel onu tam olarak
modelin ayirdigi alana koyar.

Istek DOSYADA durur, bellekte degil: panel kapanip acilir, kurs bir hafta sonra
tamamlanabilir. Bellekte tutulsaydi istek panelle birlikte olurdu ve geriye
hicbir aciklamasi olmayan bos bir panel kalirdi.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import compose, media
from .package import StoryPackage, StoryError

# Production logging (panel operations)
try:
    from .panel.production import record as record_production
except ImportError:  # pragma: no cover
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "panel"))
        from production import record as record_production
    except ImportError:  # pragma: no cover
        record_production = None  # Logging optional if module not available

TURLER = ("gorsel", "video")
# Modelin alan ayiramadigi duzenler icin (compose_slide yalnizca cover ve
# content duzenlerinde yer ayirir). Sag sutun, metnin altina inmeyen bir kart.
VARSAYILAN_ALAN = {"x": 56.0, "y": 26.0, "w": 38.0, "h": 46.0}
GORSEL_BICIMLERI = tuple(sorted(media.MEDIA_TYPES))
VIDEO_BICIMLERI = tuple(sorted(media.VIDEO_TYPES))


def dosya(story: str | Path) -> Path:
    """Bir kursun istek defteri: kursun yaninda, kursun adiyla."""
    return Path(story).with_suffix(".medya.json")


def oku(story: str | Path) -> list[dict]:
    yol = dosya(story)
    if not yol.is_file():
        return []
    try:
        veri = json.loads(yol.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    istekler = veri.get("istekler") if isinstance(veri, dict) else veri
    return [i for i in (istekler or []) if isinstance(i, dict)]


def yaz(story: str | Path, istekler: list[dict]) -> Path:
    yol = dosya(story)
    yol.write_text(
        json.dumps({"kurs": str(Path(story).resolve()), "istekler": istekler},
                   ensure_ascii=False, indent=2),
        encoding="utf-8")
    return yol


def temizle(story: str | Path) -> None:
    """Kurs bastan kurulunca eski istekler gecersizdir: slaytlar artik baska."""
    yol = dosya(story)
    if yol.is_file():
        yol.unlink()


# Yakin oranlar ADIYLA anilir: "883x1080" bir uretici icin anlamsiz, "4:5"
# anlamli. Tolerans %2 -- yuzdeden gelen kutu tam sayilara oturmuyor.
ORANLAR = ((16, 9), (9, 16), (4, 3), (3, 4), (3, 2), (2, 3),
           (1, 1), (5, 4), (4, 5), (21, 9))


def _oran_adi(w: int, h: int) -> str:
    if not w or not h:
        return ""
    deger = w / h
    for a, b in ORANLAR:
        if abs(deger - a / b) <= 0.02 * (a / b):
            return f"{a}:{b}"
    return ""


def slayt_olcusu(pkg: StoryPackage, slayt: str) -> tuple[int, int] | None:
    """Istegin cercevesi: O SLAYDIN kendi koordinat uzayi.

    Projenin bildirdigi boyut (settings.story_size) DEGIL. Ikisi ayrisabiliyor
    ve olculdu (2026-08-29, denee.story): proje 1920x1080 bildiriyor, slaytlarin
    kimi 720x540 kimi 1920x1080 -- cunku soru slaytlari 1920x1080 bir kurstan
    hasat edilmis tohumlardan geliyor, icerik slaytlari ise 720x540 sablondan
    klonlaniyor.

    Sonucu somut: siparis kullaniciya "1920x1080 (16:9)" dedi, kullanici tam o
    oranda bir gorsel uretti, `add_image` ise yerlesimi SLAYDIN cercevesinden
    (720x540, yani 4:3) hesapladi ve gorselin kenarlarindan %25'ini kirpti.
    Iki yer ayni sayiyi ayri kaynaktan hesapladigi surece bu kacinilmazdi.
    """
    try:
        from . import shapes
        genislik, yukseklik = shapes.slide_size(pkg.parse(pkg.slide_part_for(slayt)))
        return int(genislik), int(yukseklik)
    except Exception:      # noqa: BLE001 - olcu yoksa siparis boyutsuz gider
        return None


def olcu(alan: dict | None, sahne: tuple[int, int] | None) -> dict | None:
    """Ayrilan alanin PIKSEL karsiligi.

    TEK YERDE hesaplanir. Iki cagiran var (kurucu ve MCP `request_media`) ve
    ikisi ayri ayri yuzdeyi piksele cevirseydi, biri yuvarlamayi degistirdiginde
    ayni slayt icin iki farkli boyut istenirdi.

    Neden onemli: `uygula` hero/bleed alanlarini fit="cover" ile doldurur, yani
    orani tutmayan bir dosyanin KENARLARI KIRPILIR. Kirpma bozmaz ama secer:
    3:1 bir fotografin ortasi alinirken kenardaki sey gider. Boyutu siparise
    yazmak, o secimi hic gerekmeyecek hale getirir.
    """
    if not alan or not sahne:
        return None
    genislik, yukseklik = sahne
    w = int(round(genislik * float(alan.get("w", 0)) / 100))
    h = int(round(yukseklik * float(alan.get("h", 0)) / 100))
    if w < 1 or h < 1:
        return None
    return {"w": w, "h": h, "oran": _oran_adi(w, h)}


def prompt(kayit: dict) -> str:
    """Kopyalanip bir uretece yapistirilabilir SIPARIS metni.

    Aciklama tek basina eksik: uretecin cikardigi kare boyut, slaytta ayrilan
    alana oturmuyor. Boyut cumlesi burada -- panelde ayri, defterde ayri
    yazilsaydi kopyalanan metin ile kaydedilen istek ayrisirdi.
    """
    parcalar = [(kayit.get("aciklama") or "").strip()]
    o = kayit.get("olcu") or {}
    w, h = o.get("w"), o.get("h")
    if w and h:
        oran = f" ({o['oran']})" if o.get("oran") else ""
        if kayit.get("tur") == "video":
            parcalar.append(f"Boyut: {w}×{h} piksel{oran}; video kendi oranını korur.")
        elif kayit.get("stil") in ("hero", "bleed"):
            parcalar.append(
                f"Boyut: {w}×{h} piksel{oran} — bu alan görselle tam doldurulur; "
                "başka oranda bir dosyanın kenarları ortadan kırpılır. Daha "
                "yüksek çözünürlük olabilir, oran aynı kalsın.")
        else:
            parcalar.append(
                f"Boyut: {w}×{h} piksel{oran} ya da daha büyüğü, aynı oranda.")
    if kayit.get("tur") == "video" and kayit.get("saniye"):
        parcalar.append(f"Süre: yaklaşık {kayit['saniye']} saniye.")
    return " ".join(p for p in parcalar if p)


def istek(slayt: str, sahne: str, baslik: str, tur: str, aciklama: str, *,
          saniye: int | None = None, alan: dict | None = None,
          stil: str = "panel", sira: int = 0,
          sahne_px: tuple[int, int] | None = None) -> dict:
    """Tek bir istek kaydi. Alanlar TEK yerde adlandirilir."""
    return {
        "id": f"m{sira:02d}",
        "slayt": slayt,            # slideN.xml -- ad degil, dosya adi
        "sahne": sahne,
        "baslik": baslik,
        "tur": tur if tur in TURLER else "gorsel",
        "aciklama": aciklama,
        "saniye": saniye,
        "alan": alan,
        # Kurs boyutu SONRADAN degisebilir, ama istek o anki alana gore
        # verildi: boyut kayda yazilir, her okumada yeniden hesaplanmaz.
        "olcu": olcu(alan or VARSAYILAN_ALAN, sahne_px),
        "stil": stil,
        "durum": "bekliyor",
        "dosya": None,
    }


def _kabul_edilir(yol: Path, tur: str) -> None:
    if not yol.is_file():
        raise StoryError(f"Dosya bulunamadi: {yol}")
    bicimler = VIDEO_BICIMLERI if tur == "video" else GORSEL_BICIMLERI
    if yol.suffix.lower() not in bicimler:
        raise StoryError(
            f"{yol.name}: {tur} icin desteklenmeyen bicim. "
            f"Kullanilabilir: {', '.join(bicimler)}")


def uygula(story: str | Path, secimler: list[dict]) -> dict:
    """Secilen dosyalari slaytlarina koy ve kursu BIR KEZ kaydet.

    Her sey once dogrulanir, sonra uygulanir. Ortada duran bir hata -- ucuncu
    dosyanin bicimi tutmuyor -- ilk ikisi yazildiktan sonra patlarsa kurs yarim
    kalir ve istek defteri neyin girdigini bilmez. Bu yuzden bir tanesi bile
    kabul edilmiyorsa hicbiri yazilmaz.
    """
    istekler = oku(story)
    dizin = {i.get("id"): i for i in istekler}

    isler = []
    for secim in secimler:
        kayit = dizin.get(secim.get("id"))
        if kayit is None:
            raise StoryError(f"Istek bulunamadi: {secim.get('id')}")
        yol = Path(secim.get("dosya") or "")
        _kabul_edilir(yol, kayit.get("tur", "gorsel"))
        isler.append((kayit, yol))
    if not isler:
        raise StoryError("Eklenecek dosya secilmedi.")

    pkg = StoryPackage(story)
    sonuclar = []
    for kayit, yol in isler:
        alan = kayit.get("alan") or VARSAYILAN_ALAN
        stil = kayit.get("stil") or "panel"
        ortak = dict(x=alan.get("x", VARSAYILAN_ALAN["x"]),
                     y=alan.get("y", VARSAYILAN_ALAN["y"]),
                     w=alan.get("w", VARSAYILAN_ALAN["w"]),
                     h=alan.get("h", VARSAYILAN_ALAN["h"]))
        if kayit.get("tur") == "video":
            # Video her zaman kendi oranini korur: gerilmis bir film, gerilmis
            # bir fotograftan daha gorunur.
            cikti = media.add_video(pkg, kayit["slayt"], yol, name=yol.stem, **ortak)
        else:
            # hero ve bleed alani DOLDURMAK icin ayrilmistir; panel bir karttir
            # ve icindeki fotograf oranini korur. Doldurma GERME DEGIL kirpma:
            # gerilmis bir kapak, dosya acilana kadar kimsenin goremeyecegi bir
            # bozulmadir (olculdu 2026-08-29, 3:1 fotograf 4:3 kapaga gerildi).
            cikti = media.add_image(pkg, kayit["slayt"], yol, name=yol.name,
                                    fit="cover" if stil in ("hero", "bleed")
                                        else "contain",
                                    behind=bool(alan.get("behind")), **ortak)
        # OKUNABILIRLIK, DOSYA GELDIGINDE KONTROL EDILIR. Kurucu kapakta
        # ortuyu kendi ciziyor, ama gorsel komut yolundan ya da bu sekmeden de
        # gelebiliyor ve o slaytta ortu olmayabiliyor. Olculdu 2026-08-29:
        # tam sayfa fotografin uzerindeki beyaz baslik okunmaz hale geldi.
        if kayit.get("tur") != "video" and (
                stil in ("hero", "bleed") or bool(alan.get("behind"))):
            ortu = compose.ensure_scrim(pkg, kayit["slayt"])
            cikti["ortu"] = ortu.get("sebep") if not ortu["eklendi"] else "eklendi"
        kayit["durum"] = "eklendi"
        kayit["dosya"] = str(yol)
        sonuclar.append({"id": kayit["id"], "slayt": kayit["slayt"],
                         "tur": kayit.get("tur"), "dosya": yol.name,
                         "kutu": cikti.get("box_percent"),
                         "sure_ms": cikti.get("duration_ms")})

    rapor = pkg.save(Path(story), backup=True)
    
    # Log to production if available
    if record_production:
        try:
            record_production(
                story,
                "apply_media",
                rapor,
                context={"media_added": len(sonuclar)},
            )
        except Exception:
            pass  # Logging failure shouldn't stop the operation
    
    yaz(story, istekler)
    return {"eklendi": sonuclar, "kalan": bekleyen_sayisi(istekler),
            "verified": rapor["verified"], "written": rapor["written"]}


def atla(story: str | Path, istek_id: str) -> list[dict]:
    """Bir istegi defterden dusur -- o slaytta gorsel istenmiyor."""
    istekler = [i for i in oku(story) if i.get("id") != istek_id]
    yaz(story, istekler)
    return istekler


def bekleyen_sayisi(istekler: list[dict]) -> int:
    return sum(1 for i in istekler if i.get("durum") != "eklendi")
