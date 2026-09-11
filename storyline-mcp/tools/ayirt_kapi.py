"""Kapılar gerçekten AYIRT ediyor mu -- kusuru ürün koduna ekerek.

NICIN VAR. Kapilarin kendi kanaryalari kusuru ARTEFAKTA ekiyor
(`ET.SubElement`, `remove()`) ve o ekim kendi kendini kanitliyor: yazdigi
elemani geri okuyor. Ama "bu kapi duzeltme geri alininca kirmiziya
donuyor" iddiasi baska bir sey olcuyor -- kapinin URUN KODUNDAKI bir
degisime tepki verdigini -- ve bu iplikte o iddia hep ELLE, terminalde
sinandi. Terminal ciktisi commit mesajina aliniyor ama arkada bir
artefakt kalmiyor.

IKI KEZ YANILTTI, ve ikisi de ekim adiminin kendi olcumunu
kanitlamamasindan:

  1 `git stash push -- storyline_mcp/server.py` CIKIS 0 verdi ve HICBIR
    SEY kaldirmadi: hedef commit'liydi, kirli agacta degisiklik yoktu.
    Kapi kusursuz urun uzerinde kostu, yesil dondu. O gun "kapi ayirt
    etmiyor" diye okunsaydi yanlis yere bakilirdi.

  2 Kimlik ayagi icin ekilen kusur YANLISTI: `slaytlar[ref.guid]` ->
    `slaytlar[ref.basename]`. basename de KARARLI bir kimlik, yani
    ayagin korudugu kusur (KONUMA bakmak) hic ekilmemisti. Sonuc (0,0)
    okundu ve "kapi kor" gibi gorundu; dogru tohumla -- konum anahtari --
    ayak dusuyor.

Kural bu yuzden iki katmanli: ekim, (a) dosyayi gercekten degistirdigini
VE (b) iddia ettigi KUSURU ektigini kanitlamali. (a) burada otomatik;
(b) tohumu yazanin isi ve her tohumun yanina neyi taklit ettigi yazili.

NICIN SUIT'TE DEGIL. Bu arac URUN KAYNAGINI gecici olarak degistiriyor.
Suit'in bir adimi olsaydi, koşu ortasinda cokme agaci MUTASYONLU
birakabilirdi -- ve o hal, duzelttigi seyden kotu. Elle kosulur, kendi
temizligini `finally` ile yapar, ve hedef dosyalar KIRLIYSE hic
baslamaz (geri yukleme kullanicinin duzenlemesini yutmasin diye).

    python tools/ayirt_kapi.py
    python tools/ayirt_kapi.py --liste
"""

from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable


# Her tohum NEYI TAKLIT ETTIGINI soyluyor: "dosya degisti" yetmez, ekilen
# sey ayagin korudugu kusur OLMALI.
SINAMALAR = [
    dict(ad="oturum/kimlik", ayak="4 KIMLIK",
         taklit="fark KONUMA bakan bir uygulama (guid yerine sira)",
         dosya="storyline_mcp/oturum.py",
         eski="        slaytlar[ref.guid] = {",
         yeni="        slaytlar[str(len(slaytlar))] = {   # MUTASYON",
         kapi="oturum_kapi.py"),
    dict(ad="oturum/geri-alma-yedegi", ayak="6 GERI ALMA",
         taklit="geri alma simdiki hali saklamadan uzerine yaziyor",
         dosya="storyline_mcp/oturum.py",
         eski='    shutil.copy2(kaynak, kaynak.with_suffix(kaynak.suffix + ".gerialma.bak"))',
         yeni="    pass  # MUTASYON",
         kapi="oturum_kapi.py"),
    dict(ad="puanlanabilirlik/kapsam", ayak="3 KAPSAM",
         taklit="olcu 'choices tasiyan her etkilesim' diyor (ilk surum)",
         dosya="storyline_mcp/puanlama.py",
         eski='    OLCULEN_TIPLER = ("freePickOneIntr", "freePickManyIntr")',
         yeni='    OLCULEN_TIPLER = ("freePickOneIntr", "freePickManyIntr", "dragDropIntr")  # MUTASYON',
         kapi="puanlanabilirlik.py"),
    dict(ad="puanlanabilirlik/yazma-kapisi", ayak="4 YAZMA KAPISI",
         taklit="aralik denetimi tohum kolundan SONRA duruyor",
         dosya="storyline_mcp/authoring.py",
         eski=("    if not correct or any(i < 0 or i >= len(choices) for i in correct):\n"
               "        raise StoryError("),
         yeni=("    if False:\n"
               "        raise StoryError(   # MUTASYON"),
         kapi="puanlanabilirlik.py"),
    dict(ad="duzenle/durum-govdesi", ayak="2 DURUM GOVDESI",
         taklit="tasima yalnizca dis kutuyu yaziyor, govdeleri birakiyor",
         dosya="storyline_mcp/shapes.py",
         eski=('    states = shape.find("stateLst")\n'
               "    if states is None:\n"
               "        return"),
         yeni=('    states = shape.find("stateLst")\n'
               "    if True:   # MUTASYON\n"
               "        return"),
         kapi="duzenle_kapi.py"),
    dict(ad="kablolama/degismez", ayak="1 EKLER + 6 KAYIT NOKTASI",
         taklit="kablolama `_write`tan kaldirilmis (arac basina kural)",
         dosya="storyline_mcp/server.py",
         eski="    kablo = puanlama.kablola(pkg)",
         yeni=('    kablo = {"degisti": False, "eklenen": [], "dusen_bayat": [],\n'
               '             "dusen_cozulemeyen": [], "lms_yazildi": False,\n'
               '             "neden": "MUTASYON"}'),
         kapi="kablolama_kapi.py"),
    dict(ad="red_mesaji/donusum", ayak="1 KASITLI RED",
         taklit="StoryError -> ToolError donusumu dusmus (maskeleme geri)",
         dosya="storyline_mcp/server.py",
         eski=("        except StoryError as red:\n"
               "            raise ToolError(str(red)) from red"),
         yeni=("        except StoryError:\n"
               "            raise   # MUTASYON"),
         kapi="red_mesaji.py"),
]


def _kirli(dosyalar: set[str]) -> list[str]:
    """Hedef dosyalarda islenmemis degisiklik var mi."""
    try:
        out = subprocess.run(["git", "status", "--porcelain", "--"] + sorted(dosyalar),
                             cwd=ROOT, capture_output=True, text=True, timeout=30)
    except Exception:                                   # noqa: BLE001
        return []
    return [s[3:].strip() for s in out.stdout.splitlines() if s.strip()]


def _kos(kapi: str) -> int:
    r = subprocess.run([PY, f"tools/{kapi}"], cwd=ROOT,
                       capture_output=True, text=True, timeout=600)
    return r.returncode


def sinama(s: dict) -> dict:
    hedef = ROOT / s["dosya"]
    ham = hedef.read_text(encoding="utf-8")
    if ham.count(s["eski"]) != 1:
        return {**s, "durum": f"EKILEMEDI (desen {ham.count(s['eski'])} kez)",
                "taban": None, "mutasyonlu": None}

    gecici = pathlib.Path(tempfile.mkdtemp()) / hedef.name
    shutil.copy2(hedef, gecici)
    try:
        taban = _kos(s["kapi"])
        hedef.write_text(ham.replace(s["eski"], s["yeni"]), encoding="utf-8")
        # KANIT (a): mutasyon gercekten dosyada mi.
        sonra = hedef.read_text(encoding="utf-8")
        if s["eski"] in sonra or s["yeni"] not in sonra:
            return {**s, "durum": "MUTASYON KANITLANAMADI",
                    "taban": taban, "mutasyonlu": None}
        mutasyonlu = _kos(s["kapi"])
    finally:
        # TEMIZLIK HER HALDE: istisna da olsa urun kaynagi geri yuklenir.
        shutil.copy2(gecici, hedef)
    geri = hedef.read_text(encoding="utf-8") == ham
    return {**s, "durum": "kanitlandi" if geri else "GERI YUKLEME BOZUK",
            "taban": taban, "mutasyonlu": mutasyonlu}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--liste", action="store_true", help="ne sinanacak, kosma")
    args = ap.parse_args()

    if args.liste:
        for s in SINAMALAR:
            print(f"{s['ad']:<30}{s['ayak']:<22}{s['kapi']}")
            print(f"  taklit: {s['taklit']}")
        return 0

    kirli = _kirli({s["dosya"] for s in SINAMALAR})
    if kirli:
        print("KOSAMADI: hedef dosyalarda islenmemis degisiklik var "
              f"({', '.join(kirli)}). Geri yukleme senin duzenlemeni "
              "yutardi; once commit et ya da stash'le.")
        return 3

    print(f"{'sinama':<30}{'ayak':<22}{'taban':>7}{'mutasyon':>10}  hukum")
    print("-" * 92)
    kotu = 0
    for s in SINAMALAR:
        r = sinama(s)
        t, m = r["taban"], r["mutasyonlu"]
        if r["durum"] != "kanitlandi":
            hukum, kotu = r["durum"], kotu + 1
        elif t == 0 and m == 1:
            hukum = "AYIRT EDIYOR"
        elif t == 0 and m == 0:
            hukum, kotu = "AYIRT ETMIYOR <- kapi kor", kotu + 1
        else:
            hukum, kotu = f"beklenmedik ({t},{m})", kotu + 1
        print(f"{r['ad']:<30}{r['ayak']:<22}{str(t):>7}{str(m):>10}  {hukum}")

    print()
    if kotu:
        print(f"{kotu} sinama beklenen sonucu vermedi.")
        return 1
    print("Butun kapilar ekilen kusuru goruyor.")
    print("KAPSAM: her kapinin YALNIZCA listelenen ayagi sinandi. Yesil,\n"
          "        'kapi her kusuru gorur' demek DEGIL -- 'bu kusuru\n"
          "        gorur' demek. Ve tohum, iddia ettigi kusuru ektigini\n"
          "        kanitlamali: 'dosya degisti' yetmez (bkz. baslik, 2).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
