"""Hangi araç neyi ölçüyor, ve neye kör.

Kapsam ayrı bir belgede durursa okunmaz. Sonucun yanında durursa okunur --
"variety GECTI" cumlesi zamanla "kurs cesitli" diye anlasilir, ve o an
kimse kapsam belgesini acmaz. O yuzden her arac kendi kapsamini kendi
ciktisinda basar.

Metin tek yerde durur: iki kopya kacinilmaz olarak birbirinden kayar ve
kayan kapsam, olmayan kapsamdan daha kotudur -- yanlis bir guvence verir.

TEMA UYARISI ozellikle onemli. GOREV 5 zemini degistiriyor ve zemin,
slayt alaninin %98'i (olculdu). Ama deadband ve silhouette renge kor:
zemin lacivertten kremaya donse de sayilari kimildamaz. Dolayisiyla tema
degisikliginden sonra "butun testler yesil" cumlesi, temanin dogrulandigi
anlamina GELMEZ. Yalnizca temanin iskeleti bozmadigi anlamina gelir.
"""

from __future__ import annotations

import sys

BLIND_TO_COLOR = (
    "renk, punto, agirlik ve ritim farki bu sayida gorunmez"
)

SCOPES = {
    "variety": [
        "bu olcu KONUMSALDIR: " + BLIND_TO_COLOR + ".",
        "tema degisimi bu sayiyi KIMILDATMAZ; yesil kalmasi temanin",
        "dogrulandigi degil, iskeleti bozmadigi anlamina gelir.",
        "tema icin: tools/contrast.py + gozle bakis.",
    ],
    "deadband": [
        "bu olcu GEOMETRIKTIR: bos alanin nerede oldugunu sayar, o alanin",
        "ne renk oldugunu degil. Acik zeminli bir tema ayni sayiyi verir.",
        "okunabilirlik icin: tools/contrast.py.",
    ],
    "silhouette": [
        "bu olcu KONUMSALDIR: iki slaytin ayni renkte olup olmadigini",
        "gormez, yalnizca murekkebin nerede toplandigini gorur.",
    ],
    "rubric": [
        "bu olcu YARGIDIR ve deterministik degildir. Ayirt edebilecegi en",
        "kucuk fark, uretim bandinda (orta-iyi) kabaca 1.5-2 PUAN: uc",
        "kosumda sapma 0.47 olculdu. Bundan kucuk bir iyilestirme rubrikle",
        "OLCULEMEZ -- puan oynamasi ile gercek fark ayrilmaz.",
        "HANGI kursun kararsiz oldugu OLCUME GORE DEGISIYOR: bir turda kotu",
        "sapma 1.41 / iyi 0.00, ertesi turda kotu 0.94 / iyi 1.25. Yani",
        "sapma bir kursun ozelligi degil; 'iyi kurs net gorunuyor' diye",
        "okunmasi yanlisti. Guvenilir olan tek sey, iki turda da orta ile",
        "iyi dagilimlarinin AYRIK kalmasi.",
        "SIRA ETKISI: olculdu, mutlak fark <=1 puan. Ama permutasyon basina",
        "tek kosum var ve sicaklik araligi 2-3 puan -- yani sira etkisi",
        "gurultuden AYRILAMADI. 'Sira etkisi yok' DENEMEZ; 'olculemedi'",
        "denir. Ayirmak icin her permutasyonun tekrarlanmasi gerekir.",
        "Bakilan sey ONIZLEME, yayin degil: preview.py'nin sadakat notu",
        "neyin yaklasik oldugunu sayiyor.",
    ],
    "contrast": [
        "bu olcu RENKSEL ve GUVENLIK esiklidir (WCAG AA): yazinin",
        "okunup okunmadigini soyler, temanin guzel olup olmadigini degil.",
        "zevk icin sayi yok, gozle bakilir.",
    ],
}


# Kapsam cumlelerinin bir kismi DOGRULANABILIR bir iddia icerir. Iddia olarak
# birakilan bir kapsam, zamanla yanlis olur ve kimse fark etmez: "renge kor"
# diye yazilmis bir olcu, birisi renk agirligi ekledigi gun sessizce renge
# duyarli hale gelir ve kapsam cumlesi yalan soylemeye baslar.
#
# Asagidakiler kosulabilir. Kosulamayanlar (contrast'in "guzelligi olcmez"i
# gibi) bir mekanizma degil bir sinir bildirir; onlar iddia olarak kalir.
def verify() -> list[str]:
    """Doğrulanabilir kapsam iddialarını koşar."""
    import shutil
    import warnings
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "tools"))
    from storyline_mcp import compose, model
    from storyline_mcp.package import StoryPackage
    import silhouette

    blank = root.parent / "test" / "bos.story"
    work = root.parent / "test" / "_canary" / "kapsam_iddia.story"
    spec = dict(layout="content", variant="sol-panel", title="Parola Hijyeni",
                eyebrow="Bolum 1", body="Guclu bir parola uzundur.",
                bullets=["Uzun tut", "Tekrar etme"], buttons=["Devam"])

    shutil.copy2(blank, work)
    pkg = StoryPackage(work)
    names = [r.basename for r in model.slide_index(pkg).values()]
    themes = compose.theme_names()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for slide, theme in zip(names, themes):
            compose.compose_slide(pkg, slide, theme=theme, identity="iddia",
                                  **dict(spec))
        pkg.save(work, backup=False)

    # IDDIA: silhouette renge kor. Ayni iskelet, alti farkli tema -> 0.000.
    done = StoryPackage(work)
    used = list(names[:len(themes)])
    worst = max((p["direct"] for p in silhouette.compare(done, used)), default=0.0)
    out = []
    print(f"iddia: silhouette renge kor -> {len(themes)} tema, ayni iskelet, "
          f"en buyuk mesafe {worst:.4f}")
    if worst > 1e-6:
        out.append(f"silhouette renge kor DEGIL: ayni iskelet farkli temalarda "
                   f"{worst:.4f} mesafe veriyor — kapsam cumlesi yanlis")
    return out


def line(tool: str) -> str:
    body = SCOPES.get(tool)
    if not body:
        return ""
    pad = "\n        "
    return "KAPSAM: " + pad.join(body)


def show(tool: str) -> None:
    text = line(tool)
    if text:
        print(text)


if __name__ == "__main__":
    problems = verify()
    for name in sorted(SCOPES):
        print()
        print(f"[{name}]")
        print(line(name))
    print()
    if problems:
        for p in problems:
            print(f"  ! {p}")
        raise SystemExit(1)
    print("Dogrulanabilir kapsam iddialari tutuyor.")
