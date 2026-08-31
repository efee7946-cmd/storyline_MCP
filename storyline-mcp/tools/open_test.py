"""Ask Storyline itself whether each donor opens, instead of asking the user.

Storyline holds the project it has loaded with an exclusive lock and puts its
filename in the window title. Neither happens when a load fails -- the error
dialog appears and the file is released. That makes "did it open?" a question
with a programmatic answer, so a folder of downloads can be checked end to end
without a human double-clicking each one and reporting back.

This matters most for donors. They come from strangers and from older versions
of Storyline, and the "created in an earlier version" refusal is exactly the
failure a survey cannot see: the file parses fine as a zip of XML and still
will not load. A donor that does not open cannot be rehearsed against, so it
does not enter the pool.

Between rungs Storyline is closed. A project that is open is saved first via
the graceful path, so an unsaved session is not the price of running this.
"""

from __future__ import annotations

import argparse
import re
import ctypes
import subprocess
import sys
import time
import winreg
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "panel"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from storyline_mcp.package import lock_state
import storyline_ctl as ctl
import canary

DONORS = ROOT / "donors"


def storyline_exe() -> str | None:
    """Where Storyline lives, asked of the .story association rather than guessed.

    The file is launched through this executable directly and not through
    `start`. Going via the shell hands the path to whatever already has the
    association registered -- with the Articulate 360 desktop app running, that
    came back as "the file is in use by another process" and no window ever
    appeared, so every donor looked like it had failed to open. A test that
    reports a false failure is worse than no test: it would have thrown out a
    pool that opens perfectly well.
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, ".story") as key:
            prog_id, _ = winreg.QueryValueEx(key, "")
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,
                            rf"{prog_id}\shell\open\command") as key:
            command, _ = winreg.QueryValueEx(key, "")
        found = re.match(r'"([^"]+\.exe)"', command or "")
        if found and Path(found.group(1)).is_file():
            return found.group(1)
    except OSError:
        pass
    for base in (r"C:\Program Files\Articulate", r"C:\Program Files (x86)\Articulate"):
        if Path(base).is_dir():
            for path in Path(base).rglob("Storyline.exe"):
                return str(path)
    return None


EXE = storyline_exe()


def launch(path: Path) -> None:
    if EXE:
        subprocess.Popen([EXE, str(path)])
    else:
        subprocess.Popen(["cmd", "/c", "start", "", str(path)], shell=False)


def force_close(*, nazik_sure: float = 12.0) -> dict:
    """Önce NAZİKÇE kapatır, olmazsa öldürür. Hangisi olduğunu döndürür.

    ONCE KOSULSUZ `taskkill /F` IDI ve bedeli olculdu (2026-08-17): oldurulen
    oturumun cokus raporu BIR SONRAKI ACILISTA geliyor ve otomasyon kendi cop
    izini olcuyor. Kare turlari ust uste tukendi -- once B4'un bant disi
    punto kalibrasyonu, sonra B5'in zemin olcumu. "Altyapi, urunu etkilemiyor"
    degerlendirmesi bu noktada yanlisti: iki blokta ilerlemeyi durdurdu.

    Sira: WM_CLOSE gonder, pencerenin GITTIGINI dogrula, gitmezse oldur.
    Nazik kapanis cokus raporu URETMEZ; oldurme uretir. Donen kayit hangi
    yolun kullanildigini soyler, cunku "kapatildi" ile "oldurulduu" bir
    sonraki turun gecerliligini belirliyor.
    """
    import storyline_ctl as _ctl
    yol = "yok"
    bulunan = _ctl.storyline_window()
    if bulunan is not None:
        try:
            user32 = ctypes.windll.user32
            user32.PostMessageW(bulunan[0], 0x0010, 0, 0)   # WM_CLOSE
            son = time.time() + nazik_sure
            while time.time() < son:
                time.sleep(0.5)
                if _ctl.storyline_window() is None:
                    yol = "nazik"
                    break
        except Exception:
            pass
    if _ctl.storyline_window() is not None or yol == "yok":
        onceden = _ctl.storyline_window() is not None
        subprocess.run(["taskkill", "/F", "/IM", "Storyline.exe", "/T"],
                       capture_output=True, timeout=60)
        if onceden:
            yol = "oldurudu"
        time.sleep(3)
    else:
        time.sleep(1.5)
    return {"yol": yol}


def close_user_project() -> bool:
    """Clear the app once, before the run, without costing anyone their work.

    The user may well have their own project open. That one gets the graceful
    path: Ctrl+S, wait for the title's asterisk to clear, then WM_CLOSE. If it
    will not close -- an unsaved-changes prompt, a modal dialog -- the run is
    abandoned rather than forced, because the alternative is to kill an
    application someone is working in.
    """
    if ctl.storyline_window() is None:
        return True
    title = ctl.open_project() or ""
    print(f"Storyline'da {title!r} acik; kaydedilip kapatilacak.")
    # save_and_close needs a path only for its closing "is the file free?"
    # poll; the window disappearing is the signal that matters here.
    result = ctl.save_and_close(title)
    if not result.get("closed"):
        print(f"Kapatilamadi: {result.get('reason', '?')}")
        return False
    return True


def test_open(path: Path, timeout: float = 100.0) -> dict:
    force_close()
    launch(path)

    deadline = time.time() + timeout
    opened_at = None
    while time.time() < deadline:
        locked = lock_state(path) != "free"
        title = ctl.open_project()
        if locked and title and (path.stem.casefold() in title.casefold() or path.name.casefold() in title.casefold()):
            opened_at = round(timeout - (deadline - time.time()), 1)
            break
        time.sleep(1.5)

    result = {
        "file": path.name,
        "opened": opened_at is not None,
        "seconds": opened_at,
        # A different filename in the title means Storyline is showing
        # something else -- usually the error dialog over the last project.
        "final_title": ctl.open_project(),
    }
    force_close()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="*",
                        help=".story dosyalari veya bir klasor (varsayilan: donors/)")
    parser.add_argument("--timeout", type=float, default=100.0,
                        help="dosya basina bekleme suresi, saniye (varsayilan: 100)")
    parser.add_argument("--no-canary", action="store_true",
                        help="kontrolleri atla (kanaryanin kendisini denerken)")
    args = parser.parse_args()

    # Absolute, always: the path is handed to Storyline, which does not share
    # our working directory. Given a relative one it silently opens nothing,
    # and the poll below then reports a perfectly good file as broken.
    files: list[Path] = []
    for raw in (args.paths or [str(DONORS)]):
        target = Path(raw).resolve()
        if target.is_dir():
            files.extend(sorted(p.resolve() for p in target.glob("*.story")))
        elif target.is_file():
            files.append(target)
        else:
            print(f"Bulunamadi: {target}")

    if not files:
        print("Denenecek dosya yok.")
        return 2

    print(f"{len(files)} dosya denenecek. Storyline acilip kapanacak, "
          f"dosya basina {args.timeout:.0f} sn'ye kadar surebilir.")
    print(f"exe: {EXE or 'bulunamadi — shell uzerinden denenecek'}\n")
    if not close_user_project():
        return 2

    # Before the expensive part, not after: a run whose verdict cannot be
    # trusted is worse than no run, because its answer gets believed.
    if not args.no_canary:
        verdict = canary.check(test_open, timeout=min(args.timeout, 90.0))
        canary.report(verdict)
        if not verdict["trustworthy"]:
            print("\nKosu iptal edildi. Once araci onar.")
            return 3
        print()

    print(f"{'dosya':<44} {'ACILDI':<8} {'sn':<7} baslik")
    print("-" * 96)

    failures = []
    for path in files:
        result = test_open(path, timeout=args.timeout)
        mark = "EVET" if result["opened"] else "HAYIR"
        if not result["opened"]:
            failures.append(result["file"])
        print(f"{result['file'][:43]:<44} {mark:<8} "
              f"{str(result['seconds'] or '-'):<7} {result['final_title']!r}")

    print()
    if failures:
        print(f"{len(failures)} dosya acilmadi, havuza alma: {', '.join(failures)}")
        return 1
    print("Hepsi acildi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
