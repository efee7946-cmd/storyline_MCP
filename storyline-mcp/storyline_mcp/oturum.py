"""Koşu başı anlık görüntü, ve "o noktadan beri ne değişti".

NICIN VAR. `package.save` her yazmada TEK bir `.bak` uretiyor ve ustune
yaziyor. Yirmi arac cagrisi suren bir ajan kosusundan geriye YALNIZCA
son cagrinin yedegi kaliyor: 19 adim geri alinamaz. Ayni eksigin ikinci
yuzu daha sessiz -- ajan kosu boyunca NE DEGISTIRDIGINI bilmiyor.
Onarim araclari tek basina yetmez; bulunamayan sey duzeltilemez.

Ikisi tek modulde, cunku ayni ikili: anlik goruntu "nereye donerim",
fark "oradan beri ne oldu". Ayri ayri ikisi de yarim kalir.

KIMLIK, KONUM DEGIL. Fark `SlideRef.guid` uzerinden anahtarlanir,
`basename` ya da sira uzerinden degil: slayt eklenip silindiginde konum
kayar ve konuma bakan bir fark, DOKUNULMAMIS slaytlari "degismis"
gosterir. basename ve ad rapora yazilir cunku okunan sey odur; ama
esleme guid'dir.

"BITTI" ANI YOK, "BASLADI" ANI VAR. Sohbet yolunda her MCP cagrisi
kendi `_write`'iyla bitiyor, yani kursun ne zaman "tamamlandigini"
soyleyen bir sinir yok. Ama kosunun BASLADIGI an var: paneli calistiran
kisi komutu gonderdiginde. Anlik goruntu oraya dayaniyor (panel/agent.py),
kapanisa degil.

NE OLCULUYOR, NE OLCULMUYOR. Fark YAPISAL: slayt, sekil, tetikleyici,
katman, degisken ve metin ozeti. "Slayt guzellesti mi" diye bir sey
soylemez; metin degisimi de icerigi degil DEGISTIGINI bildirir. Renk,
punto ve konum bu sayida GORUNMEZ -- iki slayt ayni sekil sayisina sahip
olup bambaska gorunebilir.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

from . import model
from .package import StoryPackage, StoryError

# UZANTI, `.bak`TAN AYRI. `.bak` her yazmada ezilen tek adimlik yedek;
# bu, kosu boyunca DOKUNULMAYAN bir baslangic noktasi. Ikisini ayni ada
# yazmak, ikinci arac cagrisinda kosu basini kaybettirirdi.
ANLIK_UZANTI = ".oturum.story"
KUNYE_UZANTI = ".oturum.json"


def anlik_yolu(path: str | Path) -> Path:
    p = Path(path)
    return p.with_suffix(p.suffix + ANLIK_UZANTI)


def kunye_yolu(path: str | Path) -> Path:
    p = Path(path)
    return p.with_suffix(p.suffix + KUNYE_UZANTI)


def _ozet_metin(pkg: StoryPackage, slayt: str) -> str:
    """Slaydin butun metninin ozeti -- ICERIGI degil, DEGISTIGINI tasir."""
    parcalar = [r.text for r in model.text_runs(pkg) if r.slide == slayt]
    ham = "".join(parcalar)
    return hashlib.sha1(ham.encode("utf-8")).hexdigest()[:12]


def _oz(pkg: StoryPackage) -> dict:
    """Bir paketin yapisal ozeti. Farkin IKI YANI da bunu kullanir.

    Tek fonksiyon, cunku iki ayri uygulama (once/sonra) ayni seyi baska
    kesitlerle sayar ve fark, gercek degisimden degil kesit farkindan
    dogar.
    """
    idx = model.slide_index(pkg)
    slaytlar = {}
    for part, ref in idx.items():
        kok = pkg.parse(part)
        sekil = kok.find("shapeLst")
        tetik = kok.find("trigLst")
        katman = kok.find("sldLayerLst")
        slaytlar[ref.guid] = {
            "basename": ref.basename,
            "ad": ref.name,
            "sahne": ref.scene_name,
            "sekil": len(sekil) if sekil is not None else 0,
            "tetik": len(tetik) if tetik is not None else 0,
            "katman": len(katman) if katman is not None else 0,
            "metin": _ozet_metin(pkg, ref.basename),
        }
    return {
        "slaytlar": slaytlar,
        "degiskenler": sorted(v["name"] for v in model.variables(pkg)
                              if v.get("type") == "user"),
    }


def anlik_goruntu(path: str | Path, *, etiket: str = "") -> dict:
    """Kosu basini dondur. Ayni kosuda ikinci cagri DOKUNMAZ.

    Ikinci cagrinin no-op olmasi kasitli: ajan kosu ortasinda bir arac
    daha cagirdiginda anlik goruntu YENILENIRSE geri donus noktasi
    kosuyla birlikte kayar ve "kosu basi" diye bir sey kalmaz.
    """
    kaynak = Path(path)
    if not kaynak.exists():
        raise StoryError(f"Dosya bulunamadi: {kaynak}")
    hedef = anlik_yolu(kaynak)
    kunye = kunye_yolu(kaynak)
    if hedef.exists() and kunye.exists():
        mevcut = json.loads(kunye.read_text(encoding="utf-8"))
        mevcut["yeni"] = False
        return mevcut
    shutil.copy2(kaynak, hedef)
    veri = {
        "yeni": True,
        "kaynak": str(kaynak),
        "anlik": str(hedef),
        "zaman": datetime.now().isoformat(timespec="seconds"),
        "etiket": etiket,
        "boyut": kaynak.stat().st_size,
    }
    kunye.write_text(json.dumps(veri, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
    return veri


def kapat(path: str | Path) -> bool:
    """Anlik goruntuyu birak (kosu bitti). Yoksa False."""
    silindi = False
    for yol in (anlik_yolu(path), kunye_yolu(path)):
        if yol.exists():
            yol.unlink()
            silindi = True
    return silindi


def fark(path: str | Path) -> dict:
    """Kosu basindan BERI ne degisti. Anlik goruntu yoksa bunu SOYLER.

    "Anlik goruntu yok" ile "hicbir sey degismedi" ayni gorunmemeli:
    ikisi de bos bir liste uretirdi ve ikincisi bir guvence, ilki bir
    bilgisizlik.
    """
    kaynak = Path(path)
    anlik = anlik_yolu(kaynak)
    if not anlik.exists():
        return {"anlik_goruntu": False,
                "aciklama": ("Kosu basi anlik goruntusu YOK: bu dosya icin "
                             "ne degistigi olculemez. Bu 'degismedi' demek "
                             "DEGIL, 'bakilamadi' demektir."),
                "eklenen_slaytlar": [], "silinen_slaytlar": [],
                "degisen_slaytlar": [], "eklenen_degiskenler": [],
                "silinen_degiskenler": [], "dokunulmadi": None}

    once = _oz(StoryPackage(str(anlik)))
    sonra = _oz(StoryPackage(str(kaynak)))
    o_s, s_s = once["slaytlar"], sonra["slaytlar"]

    eklenen = [{"slayt": v["basename"], "ad": v["ad"], "sahne": v["sahne"]}
               for g, v in s_s.items() if g not in o_s]
    silinen = [{"slayt": v["basename"], "ad": v["ad"], "sahne": v["sahne"]}
               for g, v in o_s.items() if g not in s_s]

    degisen = []
    for g, yeni in s_s.items():
        eski = o_s.get(g)
        if eski is None:
            continue
        neler = []
        for alan, etiket in (("sekil", "sekil"), ("tetik", "tetikleyici"),
                             ("katman", "katman")):
            if eski[alan] != yeni[alan]:
                delta = yeni[alan] - eski[alan]
                neler.append(f"{etiket} {eski[alan]}->{yeni[alan]} "
                             f"({'+' if delta > 0 else ''}{delta})")
        if eski["metin"] != yeni["metin"]:
            neler.append("metin degisti")
        if eski["ad"] != yeni["ad"]:
            neler.append(f"ad {eski['ad']!r}->{yeni['ad']!r}")
        if neler:
            degisen.append({"slayt": yeni["basename"], "ad": yeni["ad"],
                            "neler": neler})

    ekl_d = [d for d in sonra["degiskenler"] if d not in once["degiskenler"]]
    sil_d = [d for d in once["degiskenler"] if d not in sonra["degiskenler"]]

    return {
        "anlik_goruntu": True,
        "zaman": (json.loads(kunye_yolu(kaynak).read_text(encoding="utf-8"))
                  .get("zaman") if kunye_yolu(kaynak).exists() else None),
        "eklenen_slaytlar": eklenen,
        "silinen_slaytlar": silinen,
        "degisen_slaytlar": degisen,
        "eklenen_degiskenler": ekl_d,
        "silinen_degiskenler": sil_d,
        "dokunulmadi": not (eklenen or silinen or degisen or ekl_d or sil_d),
        "kapsam": ("YAPISAL fark: slayt, sekil, tetikleyici, katman, degisken "
                   "ve metin OZETI. Renk, punto ve konum bu sayida GORUNMEZ -- "
                   "iki slayt ayni sayilara sahip olup bambaska gorunebilir."),
    }


def geri_al(path: str | Path) -> dict:
    """Kosu basina don. Anlik goruntu yoksa hata, sessiz basari degil."""
    kaynak = Path(path)
    anlik = anlik_yolu(kaynak)
    if not anlik.exists():
        raise StoryError(
            f"{kaynak.name}: kosu basi anlik goruntusu yok, geri donulecek "
            f"bir nokta bulunamadi.")
    # SIMDIKI HALI DE SAKLA: geri alma da bir yazmadir ve yanlislikla
    # cagrilabilir. Ustune yazip yok etmek, duzeltmeye calistigi kaybin
    # aynisini uretir.
    shutil.copy2(kaynak, kaynak.with_suffix(kaynak.suffix + ".gerialma.bak"))
    shutil.copy2(anlik, kaynak)
    return {"geri_alindi": str(kaynak), "anlik": str(anlik),
            "onceki_hali": str(kaynak.with_suffix(kaynak.suffix
                                                  + ".gerialma.bak"))}
