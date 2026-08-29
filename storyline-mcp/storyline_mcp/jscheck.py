"""JS sozdizimi denetimi -- ve denetlenemediginde bunu SOYLEMEK.

Storyline JS'i dogrulamiyor: sozdizimi bozuk bir kod ne hata verir ne uyari;
tetikleyici panelde durur, calisma aninda hicbir sey olmaz. Yani "tetikleyici
var" ile "kod calisiyor" arasindaki mesafeyi kapatan tek sey bu kontrol.

DENETIM TARAFINDA, yazma tarafinda DEGIL. Iki sebep:

  * Node bir bagimlilik ve yazma yolunun gecerliligi ona baglanamaz (K13:
    kosunun gecerliligi hicbir kolaylik bilesenine baglanamaz). Node yoksa
    kurs uretilemez hale gelmemeli.
  * Bozuk sozdizimi dosyayi BOZMAZ -- paket gecerli kalir, yalnizca kod
    kosmaz. Kontrol karakterlerinden farkli bir sinif; onlar yazma aninda
    reddediliyor cunku paketi okunamaz yapiyorlar.

NODE YOKSA "GECTI" DENMEZ. `available=False` doner ve cagiran bunu verdikte
cevirmemek zorundadir: girdisi olmayan kontrol gecti demez (K1b).

`new Function(kod)` kullaniliyor, `node --check` degil: gecici dosya
gerektirmiyor ve kodu PARSE edip CALISTIRMIYOR. Tek fark, kodu bir fonksiyon
govdesi sayiyor olmasi -- yani en ust duzeyde `return` gecerli goruluyor.
Storyline de kodu bir govde icinde kostugu icin bu, uretim kosullarina
uzaklasma degil yakinlasma.
"""

from __future__ import annotations

import json
import shutil
import subprocess

_SCRIPT = r"""
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', d => { input += d; });
process.stdin.on('end', () => {
  let arr;
  try { arr = JSON.parse(input); } catch (e) { process.stdout.write('[]'); return; }
  const out = arr.map(code => {
    try { new Function(code); return { ok: true, error: null }; }
    catch (e) { return { ok: false, error: String(e && e.message || e) }; }
  });
  process.stdout.write(JSON.stringify(out));
});
"""


def node_path() -> str | None:
    return shutil.which("node")


def check(codes: list[str], *, timeout: float = 30.0) -> dict:
    """Her kodu ayri ayri parse et.

    Doner: {"available": bool, "reason": str, "results": [{"ok", "error"}, ...]}
    `available` False ise `results` BOSTUR -- "hepsi gecti" degil.
    """
    exe = node_path()
    if exe is None:
        return {"available": False,
                "reason": "Node bulunamadi; sozdizimi KONTROL EDILEMEDI "
                          "(gectigi anlamina gelmez).",
                "results": []}
    if not codes:
        return {"available": True, "reason": "denetlenecek JS yok", "results": []}

    try:
        proc = subprocess.run(
            [exe, "-e", _SCRIPT],
            input=json.dumps(codes),
            capture_output=True, text=True, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False,
                "reason": f"Node calistirilamadi ({type(exc).__name__}); "
                          "sozdizimi KONTROL EDILEMEDI.",
                "results": []}

    if proc.returncode != 0:
        return {"available": False,
                "reason": f"Node hata dondu (kod {proc.returncode}); "
                          "sozdizimi KONTROL EDILEMEDI.",
                "results": []}
    try:
        sonuc = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return {"available": False,
                "reason": "Node ciktisi okunamadi; sozdizimi KONTROL EDILEMEDI.",
                "results": []}

    if len(sonuc) != len(codes):
        return {"available": False,
                "reason": f"Node {len(sonuc)} sonuc dondu, {len(codes)} bekleniyordu; "
                          "sonuclar eslestirilemez.",
                "results": []}
    return {"available": True, "reason": "", "results": sonuc}
