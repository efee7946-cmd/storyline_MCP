"""Learn slide designs from real courses instead of shipping one fixed look.

The seed library began as two question slides captured by hand, so every quiz
in every generated course wore the same furniture. Meanwhile the user's own
projects hold sixteen distinct question designs and a hundred-odd composed
slides -- current-version, already on-brand, and already proven to open.

So the library is harvested rather than authored. Each candidate is rehearsed
before it is kept: installed into a scratch project, written into, read back,
and checked that the stem, the options and the correct answer all survive. A
seed that installs and cannot be filled is worse than no seed, because the
slide looks right in the outline and is empty on screen.

Version matters too. A slide captured from an older Storyline is exactly what
the "created in an earlier version" refusal is about, so sources are checked
before anything is taken from them.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

from . import authoring, clone, model
from .package import StoryPackage, StoryError, lock_state

SEED_DIR = Path(__file__).resolve().parent / "seeds"
QUESTION_KINDS = ("freePickOneIntr", "freePickManyIntr")

STEM = "SORU KOKU DENEMESI"
OPTIONS = ["SECENEK BIR", "SECENEK IKI", "SECENEK UC",
           "SECENEK DORT", "SECENEK BES", "SECENEK ALTI"]


def app_version(path: Path) -> str | None:
    try:
        with zipfile.ZipFile(path) as z:
            app = z.read("docProps/app.xml").decode("utf-8", "replace")
    except Exception:
        return None
    found = re.search(r"<AppVersion>([^<]+)</AppVersion>", app)
    return found.group(1) if found else None


def _major(version: str | None) -> int:
    try:
        return int((version or "0").split(".")[1])
    except (IndexError, ValueError):
        return 0


def _mevcut_kutuphane() -> dict[tuple[str, int], list[Path]]:
    """Diskte HALIHAZIRDA duran soru tohumlari, (tur, sayi) -> dosyalar.

    `authoring.question_seeds` ile ayni adlandirma kuralini okur. Ayri
    yazilmasinin sebebi dongusel ice aktarim: authoring zaten harvest'i
    degil ama clone'u cagiriyor ve harvest authoring'i cagirinca zincir
    kapaniyor. Kural TEK: `question_<tur>_<sayi>[_<gorunus>].xml`.
    """
    out: dict[tuple[str, int], list[Path]] = {}
    for f in sorted(SEED_DIR.glob("question_*.xml")):
        parts = f.stem.split("_")
        if len(parts) < 3 or len(parts) > 4 or not parts[2].isdigit():
            continue
        if len(parts) == 4 and not parts[3].isdigit():
            continue
        out.setdefault((parts[1], int(parts[2])), []).append(f)
    return out


def rehearse(raw: bytes, count: int, blank: Path) -> tuple[bool, str]:
    """Install the candidate, fill it in, read it back."""
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "probe.story"
        shutil.copy2(blank, target)
        pkg = StoryPackage(target)
        try:
            result = clone.install_slide(pkg, raw.decode("utf-8"), name="Deneme")
            authoring._write_question(pkg, result["part"], STEM,
                                      OPTIONS[:count], [1], 20)
            pkg.save(target, backup=False)
        except Exception as exc:
            return False, f"yazilamadi: {str(exc)[:50]}"

        for question in model.quiz(StoryPackage(target)):
            if question["prompt"].strip() != STEM:
                return False, f"kok yanlis: {question['prompt'][:32]!r}"
            texts = [c["text"].strip() for c in question["choices"]]
            if texts != OPTIONS[:count]:
                return False, f"secenekler yanlis: {texts[:2]}"
            correct = [i for i, c in enumerate(question["choices"]) if c["correct"]]
            if correct != [1]:
                return False, f"dogru cevap islenmedi: {correct}"
            return True, "tamam"
        return False, "soru okunamadi"


def harvest_questions(
    sources: list[str | Path],
    blank: str | Path,
    *,
    keep_per_shape: int = 3,
    min_version: int = 100,
    on_progress=lambda text: None,
) -> dict:
    """Collect question-slide designs from real projects into the seed library.

    keep_per_shape caps how many looks are kept for each (type, option count),
    so the library gains variety without carrying near-duplicates.
    """
    blank = Path(blank)
    # SAYAC DISKTEKINDEN BASLAR. Bos baslıyordu ve ilk saklanan gorunus
    # `index_no == 1` aliyor, yani SUFFIKSSIZ ad -- `question_<tur>_<sayi>.xml`.
    # Kutuphanede o adda bir tohum zaten varsa (elle yakalanan iki tohum tam
    # olarak o adlari tasiyor) hasat onu SESSIZCE EZIYORDU: prova edilmis,
    # uretimde calistigi bilinen bir tohumun yerine hic denenmemis bir baskasi
    # geciyor ve rapor "kept: True" diyor. Kayip, kaybedildigi anda gorunmez.
    #
    # Mevcut kutuphaneyi sayarak baslamak iki sey yapar: eski tohum durur, ve
    # keep_per_shape "toplam kac gorunus" anlamina gelir -- "bu kosuda kac
    # tane" degil, ki ikincisi arka arkaya iki hasatta tavani deler.
    mevcut = _mevcut_kutuphane()
    kept: dict[tuple[str, int], int] = {
        key: len(looks) for key, looks in mevcut.items()}
    report: list[dict] = []
    seen_signatures: set[tuple] = set()
    # KUTUPHANEDEKININ AYNISI TEKRAR SAKLANMASIN. `seen_signatures` yalnizca
    # BU KOSUDA gorulenleri biliyor ve imzasi kaba (bicim + sekil etiketleri
    # kumesi); diskte zaten duran bir tohumun BIREBIR AYNISI ondan gecer.
    # Olculdu 2026-08-29: elle yakalanan iki tohum bu kurstan alinmisti, ve
    # hasat `question_freePickOneIntr_2_2.xml` diye ayni 186983 bayti ikinci
    # kez yazdi -- sha256'lari ayni. Kutuphane "2 gorunus" gorunuyor, goz bir
    # tane goruyor. Cesitlilik sayisinin sisirilmesi, cesitliligin kendisinden
    # daha kotu: olcum artik yalan soyluyor.
    icerik_hash: set[str] = {
        hashlib.sha256(f.read_bytes()).hexdigest()
        for looks in mevcut.values() for f in looks}

    for source in sources:
        path = Path(source)
        if not path.is_file() or lock_state(path) != "free":
            continue
        version = app_version(path)
        if _major(version) < min_version:
            report.append({"file": path.name, "skipped": f"eski surum ({version})"})
            continue
        try:
            pkg = StoryPackage(path)
            index = model.slide_index(pkg)
        except Exception as exc:
            report.append({"file": path.name, "skipped": str(exc)[:50]})
            continue

        for part, ref in index.items():
            root = pkg.parse(part)
            shape_list = root.find("shapeLst")
            shapes_here = list(shape_list) if shape_list is not None else []
            interaction = next(
                (s for s in shapes_here if s.tag in QUESTION_KINDS), None)
            if interaction is None:
                continue
            choices = interaction.find("choices")
            count = len(list(choices)) if choices is not None else 0
            if not 2 <= count <= 6:
                continue

            key = (interaction.tag, count)
            if kept.get(key, 0) >= keep_per_shape:
                continue
            # Two slides built from the same furniture teach nothing new.
            signature = (key, tuple(sorted({s.tag for s in shapes_here})))
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)

            on_progress(f"{path.name} / {ref.basename}: {interaction.tag} {count} secenek")
            raw = pkg.read(part)
            ozet = hashlib.sha256(raw).hexdigest()
            if ozet in icerik_hash:
                report.append({"file": path.name, "slide": ref.basename,
                               "type": interaction.tag, "choices": count,
                               "kept": False,
                               "reason": "kutuphanede birebir aynisi var"})
                continue
            ok, why = rehearse(raw, count, blank)
            entry = {"file": path.name, "slide": ref.basename, "type": interaction.tag,
                     "choices": count, "bytes": len(raw), "kept": ok, "reason": why}
            if ok:
                icerik_hash.add(ozet)
                index_no = kept.get(key, 0) + 1
                kept[key] = index_no
                name = f"question_{interaction.tag}_{count}"
                if index_no > 1:
                    name += f"_{index_no}"
                (SEED_DIR / f"{name}.xml").write_bytes(raw)
                entry["seed"] = name + ".xml"
            report.append(entry)

    return {
        "examined": len(report),
        "kept": sum(1 for r in report if r.get("kept")),
        "formats": {f"{k[0]}_{k[1]}": v for k, v in sorted(kept.items())},
        "details": report,
    }


def library() -> list[dict]:
    """What the seed library currently holds."""
    out = []
    for path in sorted(SEED_DIR.glob("*.xml")):
        stem = path.stem
        kind, count = None, None
        parts = stem.split("_")
        if parts[0] == "question" and len(parts) >= 3 and parts[2].isdigit():
            kind, count = parts[1], int(parts[2])
        out.append({"seed": path.name, "kind": kind or stem,
                    "choices": count, "bytes": path.stat().st_size})
    return out
