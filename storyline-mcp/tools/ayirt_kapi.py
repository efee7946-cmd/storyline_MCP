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
         kapi="oturum_kapi.py", kapsadigi=("kimlik",)),
    dict(ad="oturum/geri-alma-yedegi", ayak="6 GERI ALMA",
         taklit="geri alma simdiki hali saklamadan uzerine yaziyor",
         dosya="storyline_mcp/oturum.py",
         eski='    shutil.copy2(kaynak, kaynak.with_suffix(kaynak.suffix + ".gerialma.bak"))',
         yeni="    pass  # MUTASYON",
         kapi="oturum_kapi.py", kapsadigi=("geri alma",)),
    dict(ad="puanlanabilirlik/kapsam", ayak="3 KAPSAM",
         taklit="olcu 'choices tasiyan her etkilesim' diyor (ilk surum)",
         dosya="storyline_mcp/puanlama.py",
         eski='    OLCULEN_TIPLER = ("freePickOneIntr", "freePickManyIntr")',
         yeni='    OLCULEN_TIPLER = ("freePickOneIntr", "freePickManyIntr", "dragDropIntr")  # MUTASYON',
         kapi="puanlanabilirlik.py", kapsadigi=("kapsam",)),
    dict(ad="puanlanabilirlik/yazma-kapisi", ayak="4 YAZMA KAPISI",
         taklit="aralik denetimi tohum kolundan SONRA duruyor",
         dosya="storyline_mcp/authoring.py",
         eski=("    if not correct or any(i < 0 or i >= len(choices) for i in correct):\n"
               "        raise StoryError("),
         yeni=("    if False:\n"
               "        raise StoryError(   # MUTASYON"),
         kapi="puanlanabilirlik.py", kapsadigi=("yazma kapisi",)),
    dict(ad="duzenle/durum-govdesi", ayak="2 DURUM GOVDESI",
         taklit="tasima yalnizca dis kutuyu yaziyor, govdeleri birakiyor",
         dosya="storyline_mcp/shapes.py",
         eski=('    states = shape.find("stateLst")\n'
               "    if states is None:\n"
               "        return"),
         yeni=('    states = shape.find("stateLst")\n'
               "    if True:   # MUTASYON\n"
               "        return"),
         kapi="duzenle_kapi.py", kapsadigi=("durum govdesi",)),
    dict(ad="kablolama/degismez", ayak="1 EKLER + 6 KAYIT NOKTASI",
         taklit="kablolama `_write`tan kaldirilmis (arac basina kural)",
         dosya="storyline_mcp/server.py",
         eski="    kablo = puanlama.kablola(pkg)",
         yeni=('    kablo = {"degisti": False, "eklenen": [], "dusen_bayat": [],\n'
               '             "dusen_cozulemeyen": [], "lms_yazildi": False,\n'
               '             "neden": "MUTASYON"}'),
         kapi="kablolama_kapi.py", kapsadigi=("ekler", "kayit nokta.")),
    dict(ad="red_mesaji/donusum", ayak="1 KASITLI RED",
         taklit="StoryError -> ToolError donusumu dusmus (maskeleme geri)",
         dosya="storyline_mcp/server.py",
         eski=("        except StoryError as red:\n"
               "            raise ToolError(str(red)) from red"),
         yeni=("        except StoryError:\n"
               "            raise   # MUTASYON"),
         kapi="red_mesaji.py", kapsadigi=("kasitli red", "compose kapisi")),
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


def _roster() -> dict:
    """Her kapinin BEYAN ETTIGI ayaklar. Bolen buradan geliyor.

    Kapilarin `AYAKLAR` sabiti okunuyor, docstring'i DEGIL: docstring'den
    saymak sayiyi bir DUZYAZI VEKILINE cevirirdi ve bu depoda o sinif
    yedi kez isirdi.

    KAYMA RISKI DURUYOR VE SAKLANMIYOR: `AYAKLAR` elle tutulan bir beyan,
    kapinin gercekten bastigi satirlardan turetilmiyor. Biri yeni bir ayak
    ekleyip beyani guncellemezse bolen kucuk kalir ve kapsam OLDUGUNDAN
    IYI gorunur. Ucuz denetimi: kapinin ciktisindaki etiketlerle bu liste
    karsilastirilir.
    """
    sys.path.insert(0, str(ROOT / "tools"))
    import warnings
    warnings.simplefilter("ignore")
    out = {}
    for kapi in sorted({s["kapi"] for s in SINAMALAR}):
        mod = __import__(kapi[:-3])
        out[kapi] = tuple(getattr(mod, "AYAKLAR", ()))
    return out


def _zarf(sonuclar: list, kapsam: dict, kirli: list) -> pathlib.Path:
    """Kaydin ZARFI: tarih, commit, kirli bayragi, kapsanmayan.

    ELLE KOSAN SEY KAYAR. Bu arac suit'te degil (urun kaynagini gecici
    degistiriyor; bir suit adimi cokerse agac MUTASYONLU kalirdi), ve
    bedeli su: yeni eklenen ayaklarin tohumu olmaz ve olmadigi hicbir
    yerde gorunmez. Zarf, "olculdu" ile "on bes commit once olculdu"
    arasini okunur kiliyor -- `varyans_sonuc.json`daki ayni bicim.
    """
    import json
    from datetime import datetime
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                cwd=ROOT, capture_output=True, text=True,
                                timeout=30).stdout.strip()
    except Exception:                                   # noqa: BLE001
        commit = ""
    # KIRLILIK DEPO GENELINDE OLCULUYOR, hedef dosyalarda degil.
    #
    # Ilk surum yalnizca MUTASYON HEDEFLERININ kirliligini yaziyordu ve
    # bu yanilticiydi: olcum, `AYAKLAR` beyanlari ve bu aracin kendisi
    # ISLENMEMISKEN kosmustu, yani kaydedilen commit KOSAN KODU
    # tanimlamiyordu. "commit X'te olculdu" ile "commit X + 6 islenmemis
    # dosyada olculdu" ayni gorunmemeli.
    try:
        _ham = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                              capture_output=True, text=True,
                              timeout=30).stdout
    except Exception:                                   # noqa: BLE001
        _ham = ""
    depo_kirli = [l[3:].strip() for l in _ham.splitlines() if l.strip()]

    yol = ROOT / "tools" / "ayirt_sonuc.json"
    yol.write_text(json.dumps({
        "zaman": datetime.now().isoformat(timespec="seconds"),
        "commit": commit,
        "commit_temsil_ediyor_mu": not depo_kirli,
        "islenmemis_dosyalar": depo_kirli,
        "kirli_hedef_dosya": bool(kirli),
        "sinamalar": [{k: r[k] for k in ("ad", "ayak", "kapi", "taklit",
                                         "taban", "mutasyonlu", "durum")}
                      for r in sonuclar],
        "kapsam": kapsam,
        "not": ("Bu kayit ELLE uretiliyor: arac suit'te degil, cunku urun "
                "kaynagini gecici degistiriyor. 'zaman' ve 'commit' eskiyse "
                "kapsanmayan ayaklar buyumus olabilir."),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return yol


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
    sonuclar = []
    for s in SINAMALAR:
        r = sinama(s)
        sonuclar.append(r)
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

    # KAPSAM BIR SAYI, CIKTININ ICINDE. Onceki surum "yedi ayak sinandi,
    # kapilarda otuz kusur var" diye DUZYAZIDA soyluyordu; bilinmeyen bir
    # sey ancak izlenen bir NICELIGE donusunce okunur olur -- bu ipliğin
    # en pahaliya ogrenilen kurali.
    roster = _roster()
    tohumlu: dict[str, set] = {k: set() for k in roster}
    defter = []
    for s in SINAMALAR:
        for ayak in s["kapsadigi"]:
            if ayak not in roster[s["kapi"]]:
                defter.append(f"{s['ad']}: '{ayak}' {s['kapi']}nin AYAKLAR "
                              f"beyaninda YOK -- tohum defteri kaymis")
            else:
                tohumlu[s["kapi"]].add(ayak)
    toplam = sum(len(v) for v in roster.values())
    kapsanan = sum(len(v) for v in tohumlu.values())

    print()
    print(f"KAPSAM: {kapsanan}/{toplam} ayak tohumlandi "
          f"({len(roster)} kapi roster'da).")
    for kapi, ayaklar in roster.items():
        eksik = [a for a in ayaklar if a not in tohumlu[kapi]]
        if eksik:
            print(f"  {kapi:<24} tohumsuz: {', '.join(eksik)}")
    print("  Tohumsuz bir ayak, OLCTUGU SANILAN bir ayaktir: bu iplikte "
          "`red_mesaji`nin\n  `:133` ayagi tam olarak oyle yesildi -- "
          "mesaj hic degismemisti.")

    kapsam = {"tohumlanan": kapsanan, "toplam": toplam,
              "kapsanmayan": {k: [a for a in v if a not in tohumlu[k]]
                              for k, v in roster.items()}}
    zarf = _zarf(sonuclar, kapsam, kirli)
    print(f"  zarf yazildi: {zarf.name} (zaman + commit + kirli bayragi)")

    print()
    if defter:
        print("TOHUM DEFTERI KAYMIS:")
        for d in defter:
            print(f"  - {d}")
        return 1
    if kotu:
        print(f"{kotu} sinama beklenen sonucu vermedi.")
        return 1
    print("Butun kapilar ekilen kusuru goruyor.")
    print("KAPSAM NOTU: yesil, 'kapi her kusuru gorur' demek DEGIL -- "
          "'bu kusuru\n             gorur' demek. Ve tohum, iddia ettigi "
          "kusuru ektigini\n             kanitlamali: 'dosya degisti' "
          "yetmez (bkz. baslik, 2).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
