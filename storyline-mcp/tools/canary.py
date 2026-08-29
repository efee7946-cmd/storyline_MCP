"""Test the tester, before trusting a run that costs half an hour.

Twice now a checker answered wrongly without saying so. open_test.py handed
Storyline a relative path, opened nothing, and reported all six donors broken
-- a verdict that would have thrown out a pool that opens perfectly. donors.py
skipped a file another process had locked and quietly served a pool of six
where there were thirteen. Both were silent, and both depended on Storyline's
process state, which is exactly what the open phase spends twenty-five minutes
sitting on top of.

So every run starts with two controls:

  saglam   a project known to open. If it reports "did not open", the tool is
           broken, not the file, and the run is abandoned.
  bozuk    the same project with story.xml made ill-formed. If it reports
           "opened", the negative control is inert and a pass from this run
           means nothing either.

The damaged control was chosen by measurement, not by reading the docs. The
first attempt stripped the UTF-8 BOM, which this project's notes describe as
the corruption Storyline refuses -- and the file opened anyway. Stripping it
from story.xml and from [Content_Types].xml both opened. Removing story.xml
entirely and breaking its markup are refused, so markup is what the control
uses: it damages the part the writer actually touches while leaving the
package structure intact, so the test exercises the ordinary path.

(That the BOM did not stop a load here is worth knowing on its own. Writing it
is still cheap insurance and stays, but verify()'s BOM check is not the
gatekeeper the note claims. Measured on one blank project, one Storyline
build -- not enough to rewrite the rule, enough not to lean on it.)

Both fixtures are built fresh from the current blank rather than committed, so
they can never drift out of step with the environment they are vouching for.
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = ROOT.parent / "test"
FIXTURES = TEST_DIR / "_canary"
STORY_PART = "story/story.xml"

# A small blank project; the controls are about the harness, not the content.
SOURCE_CANDIDATES = (
    TEST_DIR / "try_ONCE.story",
    TEST_DIR / "bos.story",
)


def _source() -> Path:
    for path in SOURCE_CANDIDATES:
        if path.is_file():
            return path
    raise FileNotFoundError("Kanarya icin bos bir proje bulunamadi.")


def build(workdir: Path | None = None) -> tuple[Path, Path]:
    """A file that must open and a file that must not, side by side."""
    workdir = workdir or FIXTURES
    workdir.mkdir(parents=True, exist_ok=True)
    source = _source()
    good = workdir / "canary_saglam.story"
    broken = workdir / "canary_bozuk.story"
    shutil.copy2(source, good)

    # Rewritten at the zip level on purpose: StoryPackage repairs what it
    # writes -- that is its job -- so building the damaged control through it
    # would produce a second healthy file and a control that proves nothing.
    with zipfile.ZipFile(good) as src:
        with zipfile.ZipFile(broken, "w", zipfile.ZIP_DEFLATED) as out:
            for info in src.infolist():
                data = src.read(info.filename)
                if info.filename == STORY_PART:
                    data = data.replace(b"<sceneLst", b"<sceneLst<", 1)
                out.writestr(info, data)
    return good, broken


def check(test_open, workdir: Path | None = None, *, timeout: float = 90.0) -> dict:
    """Run both controls. Returns a verdict; 'trustworthy' is the only pass."""
    good, broken = build(workdir)
    good_result = test_open(good, timeout=timeout)
    broken_result = test_open(broken, timeout=timeout)

    problems = []
    if not good_result["opened"]:
        problems.append(
            "saglam dosya 'acilmadi' dedi — arizali olan test araci, dosyalar degil")
    if broken_result["opened"]:
        problems.append(
            "bozuk dosya 'acildi' dedi — olumsuz kontrol calismiyor, "
            "bu kosudan gelen 'acildi' sonuclari da anlamsiz")

    return {
        "trustworthy": not problems,
        "saglam_acildi": good_result["opened"],
        "bozuk_acildi": broken_result["opened"],
        "problems": problems,
    }


def report(verdict: dict) -> None:
    mark = "GUVENILIR" if verdict["trustworthy"] else "ARIZALI"
    print(f"kanarya: saglam={'acildi' if verdict['saglam_acildi'] else 'ACILMADI'}  "
          f"bozuk={'ACILDI' if verdict['bozuk_acildi'] else 'acilmadi'}  [{mark}]")
    for problem in verdict["problems"]:
        print(f"  ! {problem}")


# ---------------------------------------------------------------------------
# KANARYA YALNIZCA DOGRULAYICILAR ICIN DEGIL, DENEYLER ICIN DE GEREKLI
#
# Bu dosya "acilma testi dogru mu calisiyor" sorusunu soruyor. Ayni soru her
# DENEY icin de gecerli ve bir kez pahaliya ogrenildi:
#
#   Storyline'in metin kutularini yeniden boyutlandirip boyutlandirmadigi
#   olculmek istendi. Dosya acildi, kaydedildi, kapandi; pakette tek bayt
#   degismedi. Sonuc "Storyline yeniden boyutlandirmiyor" diye okundu ve
#   koda "bir daha deneme" notu olarak yazildi. Yanlisti: save_and_close
#   Ctrl+S'i yalnizca belge kirliyken gonderiyor, bir dosyayi acmak onu
#   kirletmiyor. Storyline HIC YAZMAMISTI. Sifir fark, "iz yok"un degil
#   "yazma yok"un sonucuydu.
#
# Asimetri sudur:
#
#   POZITIF sonuc kendini kanitlar.  Bir sey degistiyse deney kosmustur.
#   NEGATIF sonuc kanitlamaz.        "Degismedi" ile "hic kosmadi" ayni
#                                    gorunur, ve ikisi arasindaki farki
#                                    yalnizca ayri bir kontrol soyler.
#
# Kural: negatif sonuc veren her deney, once kendi kostugunu kanitlamali.
# Yukaridaki ornekte karsiligi, ayni turda Storyline'in KESIN degistirecegi
# bir sey koymak olurdu -- degisirse deney calisiyor, o zaman kutunun
# degismemesi bir bulgudur; degismezse hicbir sey olculmemistir.
#
# NOT STANDARDI. Bu projedeki notlarin cogu "sunu deneme" biciminde ve her
# biri gelecekte bir yolu kapatiyor. Acik bir kapiyi kapali ilan etmek, hic
# not yazmamaktan kotudur. Bu yuzden: bir notun gerekcesi bir deneyin
# sonucuysa, DENEYIN GECERLILIGI de notta olmali -- neyin kosuldugu, neyin
# kanitlandigi, ve neyin kanitlanmadigi.
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    # Bu dosya bir kutuphane: hukum vermek icin Storyline'i acan bir test_open
    # gerekiyor ve onu open_test.py sagliyor. Dogrudan calistirildiginda hicbir
    # sey yazmadan 0 donuyordu -- yani "gecti" gibi okunuyordu. Hukum
    # uretilmediyse cikis kodu basari olmamali; bu aracin varlik sebebi tam
    # olarak "olcmedigi seye gecti dememek".
    good, broken = build()
    print(f"kanarya fikstürleri hazir:\n  saglam: {good}\n  bozuk : {broken}")
    print("\nHUKUM YOK. Kanarya kendi basina karar veremez; Storyline'i acan\n"
          "bir kosucuya ihtiyaci var:\n\n    python tools/open_test.py\n")
    raise SystemExit(2)
