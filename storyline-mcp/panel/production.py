"""Production tracing: log every save operation with validation details.

Tracks where .story files are written, validation results, and timing.
Enables diagnosing file corruption before it reaches Storyline.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


class ProductionLog:
    """Append-only log of every package save operation."""

    def __init__(self, log_path: str | Path | None = None):
        self.log_path = Path(log_path) if log_path else self._default_path()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _default_path() -> Path:
        """Default log location next to the panel script."""
        panel_dir = Path(__file__).parent
        return panel_dir / "production.jsonl"

    def record(
        self,
        target_path: str | Path,
        operation: str,
        save_report: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> None:
        """Log a save operation with full validation details.

        Args:
            target_path: Where the .story file was written.
            operation: What created it (e.g. "build", "apply", "add_image").
            save_report: The dict returned by StoryPackage.save().
            context: Optional metadata (e.g. brief, slide count, operation index).
        """
        context = context or {}
        target = Path(target_path)
        verified = save_report.get("verified", {})
        entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "target": str(target.resolve()),
            "target_exists": target.is_file(),
            "target_size_bytes": target.stat().st_size if target.is_file() else None,
            "backup": save_report.get("backup"),
            "verified_ok": verified.get("ok"),
            "xml_parts_checked": verified.get("xml_parts_checked"),
            "xml_parts_with_bom": verified.get("xml_parts_with_bom"),
            "total_entries": verified.get("total_entries"),
            "problems_count": len(verified.get("problems", [])),
            "problems": verified.get("problems", [])[:5],  # First 5 only
            "parts_rewritten_count": len(save_report.get("parts_rewritten", [])),
            "bom_repaired": save_report.get("bom_repaired", []),
            "context": context,
        }
        line = json.dumps(entry, ensure_ascii=False)
        # EKLEYEREK YAZ, bastan yazarak degil. Onceki hali her kayitta
        # gunlugun TAMAMINI okuyup geri yaziyordu -- N kayit icin O(N^2)
        # bayt. 206 kayitta gorunmezdi; kayit artik `server._write`ten de
        # geliyor (arac basina bir satir, dikis olcumu) ve ayni dosyaya
        # cok daha hizli birikiyor. Davranis ayni: append-only bir gunluge
        # tek satir ekleniyor.
        with self.log_path.open("a", encoding="utf-8") as akis:
            print(line, file=akis)

    def latest(self, count: int = 10) -> list[dict[str, Any]]:
        """Retrieve the most recent log entries."""
        if not self.log_path.is_file():
            return []
        lines = self.log_path.read_text(encoding="utf-8").strip().split("\n")
        entries = []
        for line in lines[-count:]:
            if line.strip():
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return entries

    def summary(self) -> dict[str, Any]:
        """Overall statistics from the log."""
        entries = self.latest(count=10000)
        if not entries:
            return {"entries": 0, "success_count": 0, "problem_count": 0}
        success = sum(1 for e in entries if e.get("verified_ok"))
        with_problems = sum(1 for e in entries if e.get("problems_count", 0) > 0)
        return {
            "entries": len(entries),
            "success_count": success,
            "success_pct": round(100 * success / len(entries), 1),
            "with_problems": with_problems,
            "recent_problems": [e["problems"] for e in entries[-3:] if e.get("problems_count")],
        }


_LOGGER = ProductionLog()


def record(
    target_path: str | Path,
    operation: str,
    save_report: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> None:
    """Module-level record function."""
    _LOGGER.record(target_path, operation, save_report, context)


def latest(count: int = 10) -> list[dict[str, Any]]:
    """Module-level latest retrieval."""
    return _LOGGER.latest(count)


# KAPI KOSULARI GUNLUGE DE YAZAR, ve nufusun cogunlugunu onlar olusturur.
#
# `server._write` her yazmayi kaydediyor (dikis olcumu) ve kapilar da o
# yoldan geciyor: TEK bir `kablolama_kapi` kosusu 23 satir birakti.
# Analizi sonra yazan kisi suzgeci unutursa sayi gercek kullanimi degil
# kendi kapilarimizi olcer -- ve gurultu sinyalden buyuk.
#
# SUZGEC OKUYAN TARAFTA, VE TEK YERDE. Yazma yolunda DURAMAZ: `test/_canary/`
# bir DEPO SOZLESMESI, urun gercegi degil; `server._write`in onu bilmesi
# urunun kendi test duzenine bagimli olmasi olurdu. Ama her okuyana
# "sen suz" demek, kuralin 55. cagriyi yazan kisi tarafindan unutulmasi
# demek. O yuzden varsayilan DOGRU olan burada hesaplaniyor: ham liste
# `latest()` olarak durmaya devam ediyor, suzulmus olan kendi adiyla
# cagriliyor.
#
# ELEME OLCUTU ADRESTIR, arac adi degil. Hangi araclarin "kapi" oldugunu
# saymak, kapi listesi degistikce bayatlayacak ikinci bir defter olurdu;
# hedef YOLU ise fikstur oldugunu kendisi soyluyor.
#
# BEDELI VAR VE YAZILI: eslesme TAM PARCA uzerinden ("Testler" elenmez,
# "test" elenir), ama kullanicinin kendi kurslari `test` adli bir klasorde
# dursaydi bu suzgec onlari SESSIZCE eler. Bugun oyle bir kayit yok --
# 253 kaydin hedefi tek tek bakildi (2026-09-15), hepsi `test/_canary/`
# ya da gecici dizin. Bir gun eleme sasarsa isaret sudur: `latest()`
# doluyken `gercek_kullanim()` inatla bos kalir.
FIKSTUR_PARCALARI = ("_canary", "test")


def _fikstur_mu(hedef: str) -> bool:
    """Bu yazma bir kapinin/probun artefaktina mi gitti."""
    import tempfile

    yol = Path(hedef)
    parcalar = {p.casefold() for p in yol.parts}
    if parcalar & {p.casefold() for p in FIKSTUR_PARCALARI}:
        return True
    # Gecici dizin: `yeni_modul` ve elle kosulan problar oraya yaziyor.
    try:
        gecici = Path(tempfile.gettempdir()).resolve()
        return gecici in yol.resolve().parents
    except OSError:
        return False


def gercek_kullanim(count: int = 10000) -> list[dict[str, Any]]:
    """Kapi/prob artefaktlari AYIKLANMIS kayitlar -- analizin varsayilani.

    Dikis sorusu ("bir dosyaya kac ayri yazma cagrisi sahne ekliyor")
    GERCEK kullanim hakkinda. Ham liste icin `latest()` duruyor; ikisi
    ayri isimde, cunku hangi nufusa bakildigi iddianin parcasi.
    """
    return [e for e in _LOGGER.latest(count)
            if not _fikstur_mu(e.get("target", ""))]


def summary() -> dict[str, Any]:
    """Module-level summary."""
    return _LOGGER.summary()


def format_entry(entry: dict[str, Any]) -> str:
    """Format a log entry as human-readable text for the panel."""
    ok = "✓" if entry.get("verified_ok") else "✗"
    target = Path(entry.get("target", "")).name
    problems = entry.get("problems_count", 0)
    op = entry.get("operation", "?")
    ts = entry.get("timestamp", "").split("T")[1][:8] if entry.get("timestamp") else "?"
    if problems:
        return f"{ok} {ts} {op:12} {target:30} — {problems} sorun"
    return f"{ok} {ts} {op:12} {target:30}"
