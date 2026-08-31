"""Varyans + canli dogrulama: 2 kisa + 1 uzun kosu, ardisik.

NICIN scratchpad'DE DEGIL, DEPODA. Bu betigin ilk surumu bir oturumun gecici
klasorunde durdu ve sonucunu (`varyans.json`) AYNI klasore yazdi. Kosu ~49
dakika surdu, tamamlandi, ve oturum kapaninca **olcum buharlasti**: commit'ler
kaldi, kanit kalmadi. Diske yazmak yetmiyor -- OTURUMU ASAN bir yere yazmak
gerekiyor. Betik de sonuc da artik depoda.

NICIN UCU BIRDEN BIR BETIKTE: her kosu ayni surecte, ayni kod suruunde, ayni
sarmalayicilarla koşar. Ayri ayri elle koşulsalardi aradaki farkin kosudan mi
koddan mi geldigi sorulamazdi.

NICIN ARDISIK, ESZAMANLI DEGIL: 2026-08-29'da bir kosu bos stderr ile dustu
("Icerik uretilemedi:") ve en olasi sebep es zamanli cagri sikismasiydi.
Ucunu birden acmak o riski uce katlardi.

Her kosuda olculenler:
  yeniden_isteme  celiski duzeltmesinin nedensel testi (taban: Kosu 4 = 1)
  ayrac_kararlari dort hucreli dogruluk tablosu (ekleme VE silme)
  duzen_dagilimi  esigi orana cevirmek icin gercek dagilim
  soru            regresyon: 0 menuye dusen surtuyor mu

TABAN KARSILASTIRMASI ARTIK TEMIZ DEGIL -- ve bu bilinerek kosulmali.
2026-08-30'da iki sey degisti ve ikisi de bu olcumlere DOKUNUYOR:
  * CONTENT_PROMPT'a iki yeni soru tipi girdi (drag, commitment), yani
    modelin urettigi plan artik farkli bir uzaydan geliyor.
  * `_soru_mu` gruplamayi da soru sayiyor (PUANLI_KINDLER), ve o fonksiyon
    ayrac yamasinin "govde" sayimini besliyor.
Yani `yeniden_isteme`, "Kosu 4 = 1" tabaniyla dogrudan karsilastirilamaz:
o taban baska bir promptla olculdu. Ayrac dort hucresi ve duzen dagilimi
BUGUNKU kod icin gecerli olcumlerdir -- gecmise dogru nedensel iddia icin
degil, bugun ne oldugunu bilmek icin okunmali.

    python tools/varyans.py            # ~49 dk, model cagirir
    python tools/varyans.py --hizli    # yalnizca KISA_A (~12 dk)
"""
import argparse
import collections
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "panel"))
import builder

# SONUC DEPODA. Gecici klasor degil: bu satir, bu betigin var olma
# sebebindeki dersin ta kendisi.
SONUC = ROOT / "tools" / "varyans_sonuc.json"
CIKTI = Path.home() / "Desktop" / "Storyline"

KISA = """Ofis calisanlari icin bilgi guvenligi farkindalik egitimi.
Kapsanacak ana basliklar:
1. Kimlik avi (phishing) e-postalarini tanima
2. Parola hijyeni ve iki adimli dogrulama
3. Halka acik aglar ve uzaktan calisma
4. Fiziksel guvenlik ve temiz masa
Her bolumde calisanin karar vermesi gereken somut durumlar olsun."""

UZUN = """Ofis calisanlari icin kapsamli bilgi guvenligi farkindalik egitimi.
Kapsanacak ana basliklar:
1. Kimlik avi (phishing) e-postalarini tanima
2. Parola hijyeni ve iki adimli dogrulama
3. Halka acik aglar ve uzaktan calisma
4. Fiziksel guvenlik ve temiz masa
5. Veri siniflandirma ve paylasim kurallari
6. Mobil cihaz ve tasinabilir bellek guvenligi
7. Sosyal muhendislik ve telefon dolandiriciligi
8. Olay bildirimi: bir sey ters gittiginde ne yapmali
Her bolumde calisanin karar vermesi gereken somut durumlar olsun."""

KOSULAR = [
    ("KISA_A", KISA, {"minutes": "20", "sections": "4", "theme": "orman"}),
    ("KISA_B", KISA, {"minutes": "20", "sections": "4", "theme": "orman"}),
    ("UZUN_C", UZUN, {"minutes": "60", "sections": "8", "theme": "komur"}),
]

_asil_yama = builder._ayrac_yamasi


def dokum(scenes, anahtar):
    out = []
    for sc in scenes:
        sl = [s for s in (sc.get(anahtar) or []) if not builder._soru_mu(s)]
        g = [s for s in sl
             if (s.get("layout") or "content") in builder.GOVDE_DUZENLERI]
        a = [s for s in sl if (s.get("layout") or "content") == "section"]
        out.append({"sahne": sc.get("name") or "?", "govde": len(g),
                    "ayrac": len(a)})
    return out


def duzen_sayimi(scenes, anahtar):
    """Ogrencinin gordugu duzen dagilimi -- ESIGI ORANA CEVIRMEK ICIN.

    Ilk surumde bu metrik docstring'de SAYILIYOR ama hic TOPLANMIYORDU
    (2026-08-30'da fark edildi): kosu bitse bile is 2'nin bekledigi veri
    gelmeyecekti. Belgelenen ile toplanan arasindaki fark, bu depodaki
    'yesil biten ama olcmeyen kontrol' kaliginin bir baskasi.

    Soru slaytlari DISARIDA: dagilim govde duzenleri hakkinda bir sey
    soyluyor, ve soru kendi cercevesinden geciyor.
    """
    sayac = collections.Counter()
    for sc in scenes:
        for s in (sc.get(anahtar) or []):
            if builder._soru_mu(s):
                sayac["(soru)"] += 1
                continue
            if (s.get("kind") or "content") == "commitment":
                sayac["(taahhut)"] += 1
                continue
            sayac[s.get("layout") or "content"] += 1
    return dict(sorted(sayac.items()))


def kosuyu_yap(ad, brief, ek, sonuclar):
    kararlar, cagri = [], {"yama": 0, "duzen": {}}

    def izleyen(scenes, anahtar="slides", _k=kararlar, _c=cagri):
        _c["yama"] += 1
        once = dokum(scenes, anahtar)
        r = _asil_yama(scenes, anahtar)
        sonra = dokum(scenes, anahtar)
        # DAGILIM ICERIK ASAMASINDAN, plandan degil: `scene["content"]`
        # plani butunuyle degistiriyor ve ogrencinin gordugu duzen oradan
        # geliyor. Plan asamasindan olcmek, olculmeyen bir yerde yesil
        # gormek olurdu (ayni tuzak `_kadans_ihlalleri`de yazili).
        if anahtar == "content":
            _c["duzen"] = duzen_sayimi(scenes, anahtar)
        for a, b in zip(once, sonra):
            if a["ayrac"] == 0 and a["govde"] < 2:
                continue                      # kural bu sahneyi ilgilendirmiyor
            _k.append({
                "asama": anahtar, "sahne": a["sahne"], "govde": a["govde"],
                "once_ayrac": a["ayrac"], "sonra_ayrac": b["ayrac"],
                "beklenen": a["govde"] >= 2,
                "dogru": (b["ayrac"] > 0) == (a["govde"] >= 2),
            })
        return r

    builder._ayrac_yamasi = izleyen
    CIKTI.mkdir(parents=True, exist_ok=True)
    hedef = CIKTI / f"VAR_{ad}.story"
    shutil.copy2(ROOT.parent / "test" / "bos.story", hedef)
    akis, t0 = [], time.time()

    def haber(t, _a=akis, _t=t0):
        _a.append(t)
        print(f"[{ad}] [{time.time() - _t:6.1f}s] {t}", flush=True)

    print(f"\n{'=' * 70}\n{ad} basliyor\n{'=' * 70}", flush=True)
    try:
        r = builder.build(str(hedef), brief, model="sonnet",
                          options={"title": f"Bilgi Guvenligi {ad}",
                                   "audience": "Ofis calisanlari",
                                   "questions_per_section": "2",
                                   "tone": "kurumsal", "media": "yok", **ek},
                          on_progress=haber)
        hata = None
    except Exception as exc:
        r, hata = {}, f"{type(exc).__name__}: {exc}"
        print(f"[{ad}] DUSTU: {hata}", flush=True)
    finally:
        builder._ayrac_yamasi = _asil_yama

    sonuclar.append({
        "kosu": ad, "hata": hata, "sure_s": round(time.time() - t0, 1),
        "yeniden_isteme": sum(1 for x in akis if "yeniden isteniyor" in x),
        "yama_cagrisi": cagri["yama"], "ayrac_kararlari": kararlar,
        "duzen_dagilimi": cagri["duzen"],
        "scenes": r.get("scenes"), "slides": r.get("slides_created"),
        "questions": r.get("questions"), "fallbacks": r.get("question_fallbacks"),
        "looks": len(r.get("question_looks") or []),
        "written": r.get("written"), "akis": akis,
    })
    # HER KOSUDAN SONRA YAZ, sonda degil: ucuncu kosu duserse ilk ikisinin
    # olcumu de gitmesin. Kaybin bedeli 49 dakika.
    SONUC.write_text(json.dumps(sonuclar, ensure_ascii=False,
                                default=str, indent=2), encoding="utf-8")


def ozet(sonuclar):
    print(f"\n\n{'=' * 70}\nOZET\n{'=' * 70}")
    print(f"{'kosu':8} {'sure':>7} {'yeniden':>8} {'sahne':>6} {'slayt':>6} "
          f"{'soru':>5} {'dusen':>6} {'gorunus':>8}  ayrac_dogru")
    for s in sonuclar:
        k = s["ayrac_kararlari"]
        dogru = sum(1 for x in k if x["dogru"])
        print(f"{s['kosu']:8} {s['sure_s']:7.0f} {s['yeniden_isteme']:8} "
              f"{str(s['scenes']):>6} {str(s['slides']):>6} {str(s['questions']):>5} "
              f"{str(s['fallbacks']):>6} {str(s['looks']):>8}  {dogru}/{len(k)}"
              + (f"   HATA: {s['hata']}" if s["hata"] else ""))

    print("\n=== AYRAC DORT HUCRE (butun kosular) ===")
    h = collections.Counter()
    for s in sonuclar:
        for x in s["ayrac_kararlari"]:
            h[(x["beklenen"], x["sonra_ayrac"] > 0)] += 1
    print(f"  gereken & kaldi   (dogru korunan) : {h[(True, True)]}")
    print(f"  gereken & yok     (EKSIK)         : {h[(True, False)]}")
    print(f"  gereksiz & kaldi  (FAZLA)         : {h[(False, True)]}")
    print(f"  gereksiz & yok    (dogru silinen) : {h[(False, False)]}")

    print("\n=== DUZEN DAGILIMI (esigi orana cevirmek icin) ===")
    for s in sonuclar:
        d = s.get("duzen_dagilimi") or {}
        toplam = sum(v for k, v in d.items() if not k.startswith("("))
        satir = "  ".join(f"{k}={v}" for k, v in d.items())
        print(f"  {s['kosu']:8} govde_toplam={toplam:3}  {satir}")
    print(f"\nsonuc yazildi: {SONUC}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--hizli", action="store_true",
                    help="yalnizca KISA_A kosar (~12 dk)")
    args = ap.parse_args()
    kosular = KOSULAR[:1] if args.hizli else KOSULAR
    sonuclar = []
    for ad, brief, ek in kosular:
        kosuyu_yap(ad, brief, ek, sonuclar)
    ozet(sonuclar)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
