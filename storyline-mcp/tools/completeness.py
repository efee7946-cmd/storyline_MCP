"""Kurs İŞLEVSEL olarak eksiksiz mi? Brief ne istedi, dosyada karşılığı var mı?

Bugune kadar kurulan her olcu GEOMETRIK ya da RENKSEL: konum, boyut, taban,
kontrast. Hicbiri "bu kurs calisir mi" diye sormuyor. Uretilmis bir kursta
bulunan on kusurun ikisi tam olarak oradan geldi ve ikisi de estetik degil:

    sinavin puanlanmamasi   LMS'e skor gitmez
    ilk slaydin bos olmasi  ogrencinin gordugu ilk ekran bos

Hicbir yapisal kontrol bunlari goremez: dosya gecerli, slaytlar aciliyor,
kutular yerinde. Eksik olan sey VAR OLMAYAN bir sey, ve var olmayan bir seyin
geometrisi olmaz.

IKI AYRI SORU, ikisi de burada:

  ISTENEN vs URETILEN   brief kac bolum, kac soru istedi; dosyada kac tane var
  DEVRALINAN            kaynak dosyada zaten duran ve ele alinmayan sey

Ikincisi olculdugunde sasirtici cikti: bir kursta bulunan 14 bos slaydin ve
15 kopuk tetikleyicinin TAMAMI kaynak sablondan geliyordu. Kurucu kendi
slaytlarini EKLIYOR, kaynakta ne varsa oldugu gibi birakiyor -- ve o da
ogrenciye gidiyor. Kimse saymadigi icin kimse bilmiyordu.

PUANLAMA BIR ZINCIRDIR, ve "soru var" onun yalnizca ilk halkasi. Bu ayrim
olculerek bulundu ve kontrolu bastan yazdirdi: dondurulmus referansta BES
slayt da freePickOneIntr tasiyor, sonuc slaydi da yerinde -- ama
quizMgr/quizLst/quiz/questionIdLst BOS. Yani ogrenci cevapliyor, sayfa
dogru/yanlis diyor, ve skor hicbir yere gitmiyor.

"Etkilesim var mi" diye soran bir kontrol o kursa 5/5 PUANLI der ve gecer.
Tam olarak kacinmaya calisilan hata: kontrolu yazmadan once ne taradigini
bilmek. Uc halka ayri ayri kirilir, o yuzden ayri ayri sorulur:

    1. etkilesim   slaytta INTERACTION_TAGS'ten biri var mi
    2. kayit       slaydin guid'i bir quiz'in questionIdLst'inde mi
    3. hedef       quiz'in resultSldG'si gercek bir slayda cozuluyor mu,
                   ve story duzeyinde lmsResultSlideG dolu mu

POZITIF KONTROL olmadan bunlarin hicbiri soylenemezdi. Gercek, elle yazilmis
bir kursta (test/0_duz_kopya.story) 11 etkilesimin 11'i de kayitli ve iki
kume BIREBIR ortusuyor -- ne kayitsiz soru var, ne sorusuz kayit. Kayitli bir
kursun neye benzedigini gormeden "kayit yok" demek, K1'in ta kendisi olurdu:
bulamadigini yokluk sanmak.

Kayit iki YONLU sorulur (K7): kayitsiz soru skoru kaybeder, sorusuz kayit ise
olmayan bir soruyu izler. Tek yon tutulsaydi digeri sessizce girerdi.

Bu arac hicbir sey SILMEZ. Kullanicinin dosyasindaki slaytlari silmek onun
karari; buranin isi gormunur kilmak.

    python tools/completeness.py kurs.story
    python tools/completeness.py kurs.story --sections 4 --per-section 1
    python tools/completeness.py --kontrol      dedektorun pozitif kontrolu
"""

from __future__ import annotations

import argparse
import re
import sys
import warnings
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from storyline_mcp import authoring, model, shapes
from storyline_mcp.package import StoryPackage

GUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                  r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def dangling_in_slide(root: ET.Element, known: set) -> list[str]:
    """Hedefi çözülemeyen tetikleyiciler. **Tek otorite.**

    Bu sayi bir donem IKI YERDE hesaplaniyordu ve iki farkli cevap veriyordu:
    completeness 43, inventory 25. Fark bir yuvarlama degildi -- inventory bos
    slaytlarda `continue` edip tetikleyici taramasini hic yapmiyordu, ve
    devralinan donor copu TAM ORADA yasiyor. Yani dusuk sayan surum, kusurun
    en yogun oldugu kesiti atliyordu.

    Bu projede ayni desen daha once de cikti (donors._harvest_file). Iki ayri
    uygulama er ya da gec ayrisir ve ayristiginda hangisinin dogru oldugu
    okunamaz; o yuzden hesap tek yerde durur, cagiranlar buraya sorar.

    Bos slayt ATLANMAZ: slaytta sekil olmamasi tetikleyici olmadigi anlamina
    gelmez -- slaydin kendi <trigLst>'i ve katmanlari yerinde durur.
    """
    out: list[str] = []
    for owner in root.iter():
        trig_list = owner.find("trigLst")
        if trig_list is None:
            continue
        for trig in trig_list:
            refs = {g for g in GUID.findall(ET.tostring(trig, encoding="unicode"))
                    if not g.startswith("00000000") and g not in known}
            refs -= {trig.get("g") or "", trig.get("verG") or ""}
            if refs:
                out.append(trig.get("evt") or trig.get("name") or "?")
    return out


def dangling_triggers(pkg: StoryPackage) -> list[tuple[str, str]]:
    """Kurstaki bütün kopuk tetikleyiciler: (slayt, olay)."""
    index = model.slide_index(pkg)
    story_guids = {e.get("g") for e in pkg.parse("story/story.xml").iter()
                   if e.get("g")}
    out: list[tuple[str, str]] = []
    for part, ref in index.items():
        root = pkg.parse(part)
        known = {e.get("g") for e in root.iter() if e.get("g")} | story_guids
        out += [(ref.basename, evt) for evt in dangling_in_slide(root, known)]
    return out


def _tracking(pkg: StoryPackage, index: dict) -> dict:
    """Puanlama zincirinin ikinci ve ucuncu halkasi: kayit ve hedef.

    questionIdLst'in cocuklari <item> ve guid ONITELIKTE DEGIL METINDE durur;
    attrib bos gelir. Oniteligi okumaya calisan bir surum her kaydi
    "cozulemedi" sayar ve saglam bir kursu bozuk gosterirdi.
    """
    story = pkg.parse("story/story.xml")
    by_guid = {ref.guid: ref.basename for ref in index.values()}
    manager = story.find("quizMgr")
    registered: dict[str, str] = {}       # slayt -> quiz adi
    quizzes: list[dict] = []
    for quiz in story.iter("quiz"):
        id_list = quiz.find("questionIdLst")
        items = [(el.text or "").strip()
                 for el in (list(id_list) if id_list is not None else [])]
        name = quiz.get("name") or "(isimsiz)"
        for guid in items:
            if guid in by_guid:
                registered[by_guid[guid]] = name
        target = quiz.get("resultSldG") or ""
        quizzes.append({
            "name": name,
            "kayit": len(items),
            "cozulemeyen": [g for g in items if g not in by_guid],
            "sonuc_slaydi": by_guid.get(target),
            "sonuc_guid_bos": not target or target.startswith("00000000"),
        })
    lms = (manager.get("lmsResultSlideG") or "") if manager is not None else ""
    return {
        "quizzes": quizzes,
        "registered": registered,
        "lms_hedefi": by_guid.get(lms),
        "lms_bos": not lms or lms.startswith("00000000"),
        "track_mode": manager.get("trackMode") if manager is not None else None,
    }


def survey(pkg: StoryPackage) -> dict:
    """Kursun işlevsel envanteri. Hiçbir şey değiştirmez."""
    index = model.slide_index(pkg)
    story_guids = {e.get("g") for e in pkg.parse("story/story.xml").iter()
                   if e.get("g")}

    empty, dangling, scored, unscored = [], [], [], []
    scenes: dict[str, dict] = {}
    # slide_index sahne sirasina gore doner, dolayisiyla ilk kayit kursun
    # acildigi slayttir.
    ilk_slayt, ilk_bos = None, False
    for part, ref in index.items():
        root = pkg.parse(part)
        shape_list = root.find("shapeLst")
        filled = bool(shape_list is not None and len(shape_list))
        scene = scenes.setdefault(ref.scene_name or "(sahnesiz)",
                                  {"slides": 0, "empty": 0, "questions": 0,
                                   "ilk_bos": None, "ilk": None})
        scene["slides"] += 1
        # A2: ogrencinin gordugu ILK ekran. Sahnenin tamami bos olmasa bile
        # ilk slayt bosse kurs bos bir ekranla aciliyor demektir, ve "tamami
        # bos" olcusu bunu KACIRIR -- referansta tam olarak oyle bir sahne
        # yoktu, ama olmamasi kontrolun gereksiz oldugunu gostermez.
        if ilk_slayt is None:
            ilk_slayt, ilk_bos = ref.basename, not filled
        if ref.position == 1:
            scene["ilk_bos"] = not filled
            scene["ilk"] = ref.basename
        if not filled:
            empty.append((ref.basename, ref.scene_name, ref.name))
            scene["empty"] += 1

        tag, intr = authoring._find_interaction(root)
        if intr is not None:
            scored.append(ref.basename)
            scene["questions"] += 1
        elif filled:
            # Puanlanmayan ama SORU GIBI duran slayt: birden fazla
            # tiklanabilir hedefi olan ama etkilesim kaydi olmayan.
            targets = [s for s in (shape_list or [])
                       if (t := s.find("trigLst")) is not None and len(list(t))
                       and model.shape_text(root, s.get("g") or "").strip()]
            if len(targets) >= 2:
                unscored.append((ref.basename, len(targets)))

        known = {e.get("g") for e in root.iter() if e.get("g")} | story_guids
        for owner in root.iter():
            trig_list = owner.find("trigLst")
            if trig_list is None:
                continue
            for trig in trig_list:
                refs = {g for g in GUID.findall(ET.tostring(trig, encoding="unicode"))
                        if not g.startswith("00000000") and g not in known}
                refs -= {trig.get("g") or "", trig.get("verG") or ""}
                if refs:
                    dangling.append((ref.basename,
                                     trig.get("evt") or trig.get("name") or "?"))

    izleme = _tracking(pkg, index)
    kayitli = izleme["registered"]
    # IKI YON (K7). Kayitsiz soru skoru kaybeder; sorusuz kayit olmayan bir
    # soruyu izler. Tek yonu tutmak, digerinin sessizce girmesine izin verir.
    kayitsiz = [s for s in scored if s not in kayitli]
    sorusuz_kayit = [s for s in kayitli if s not in scored]
    # Devralinan cop bolum sayilmasin: BIR slaydi bile bestelenmemis sahne
    # bolum degildir. Onceki surum "slides > 1" diyordu ve referansta 5 yerine
    # 7 bolum sayiyordu -- devralinan `Konular` ve `SINAV` sahneleri boluume
    # dahil oluyordu, yani olcut devralinan copla KANDIRILABILIYORDU.
    dolu_sahneler = [ad for ad, d in scenes.items() if d["slides"] > d["empty"]]
    return {"slides": len(index), "scenes": scenes,
            "empty": empty, "dangling": dangling,
            "scored": scored, "unscored": unscored,
            "quiz_records": len(model.quiz(pkg)),
            "izleme": izleme, "kayitli": sorted(kayitli),
            "kayitsiz": kayitsiz, "sorusuz_kayit": sorusuz_kayit,
            "dolu_sahneler": dolu_sahneler,
            "ilk_slaydi_bos": [d["ilk"] for d in scenes.values()
                               if d["ilk_bos"]],
            # A2'nin KENDISI. "Herhangi bir sahnenin ilk slaydi" genis bir
            # olcu ve devralinan sahneler yuzunden neredeyse her kursta
            # tetiklenir; asil urun kirigi daha dar: kursun ACILDIGI ekran.
            # Bu, sceneLst'in ilk sahnesinin ilk slaydidir -- dosyada
            # startSceneG gibi bir isaret yok, bakildi.
            "kurs_ilk_slaydi": ilk_slayt,
            "kurs_ilk_bos": ilk_bos}


def report(found: dict, *, sections: int | None = None,
           per_section: int | None = None) -> list[str]:
    problems: list[str] = []
    print(f"slayt {found['slides']}  sahne {len(found['scenes'])}  "
          f"puanli soru {len(found['scored'])}  quiz kaydi {found['quiz_records']}")

    print("\n=== PUANLAMA ZINCIRI (uc halka, ayri ayri kirilir) ===")
    izleme = found["izleme"]
    print(f"  1. etkilesim tasiyan slayt : {len(found['scored'])}")
    print(f"  2. quiz'e kayitli          : {len(found['kayitli'])}")
    for quiz in izleme["quizzes"]:
        hedef = quiz["sonuc_slaydi"] or ("BOS GUID" if quiz["sonuc_guid_bos"]
                                         else "COZULEMEDI")
        print(f"       quiz {quiz['name']!r}: {quiz['kayit']} kayit, "
              f"sonuc slaydi {hedef}")
        if quiz["cozulemeyen"]:
            problems.append(f"quiz {quiz['name']!r}: {len(quiz['cozulemeyen'])} "
                            "kayit hicbir slayda cozulmuyor")
        if quiz["sonuc_slaydi"] is None:
            problems.append(f"quiz {quiz['name']!r}: sonuc slaydi yok "
                            f"({hedef})")
    print(f"  3. story lmsResultSlideG   : "
          f"{izleme['lms_hedefi'] or ('BOS' if izleme['lms_bos'] else 'COZULEMEDI')}"
          f"   trackMode={izleme['track_mode']}")

    if found["kayitsiz"]:
        print(f"  KAYITSIZ SORU: {len(found['kayitsiz'])}  {found['kayitsiz'][:5]}")
        problems.append(f"{len(found['kayitsiz'])} soru quiz'e kayitli degil — "
                        "ogrenci cevapliyor, skor LMS'e gitmiyor")
    if found["sorusuz_kayit"]:
        print(f"  SORUSUZ KAYIT: {len(found['sorusuz_kayit'])}  "
              f"{found['sorusuz_kayit'][:5]}")
        problems.append(f"{len(found['sorusuz_kayit'])} kayit, etkilesimi "
                        "olmayan slaydi izliyor")
    if izleme["lms_bos"] and found["scored"]:
        problems.append("puanlanabilir soru var ama story duzeyinde "
                        "lmsResultSlideG bos — LMS'e bildirilecek sonuc "
                        "slaydi secilmemis")

    print("\n=== ISTENEN vs URETILEN ===")
    if sections is not None:
        content_scenes = found["dolu_sahneler"]
        print(f"  bolum: istenen {sections}, dosyada {len(content_scenes)}"
              f"   (en az bir bestelenmis slaydi olan sahne)")
        if len(content_scenes) < sections:
            problems.append(f"{sections} bolum istendi, {len(content_scenes)} var")
    if per_section is not None and sections:
        want = sections * per_section
        print(f"  soru : istenen {want}, puanli {len(found['scored'])}")
        if len(found["scored"]) < want:
            problems.append(f"{want} soru istendi, {len(found['scored'])} puanli")
    if found["unscored"]:
        print(f"  PUANLANMAYAN soru gibi slayt: {len(found['unscored'])}  "
              f"{found['unscored'][:4]}")
        problems.append(f"{len(found['unscored'])} slayt soru gibi duruyor ama "
                        "puanlanmiyor")

    print("\n=== DEVRALINAN (kaynak dosyadan gelen, ele alinmayan) ===")
    print(f"  bos slayt        : {len(found['empty'])}")
    for basename, scene, name in found["empty"][:6]:
        print(f"     {basename:<12} sahne={scene!r} ad={name[:24]!r}")
    print(f"  kopuk tetikleyici: {len(found['dangling'])}")
    if found["empty"]:
        problems.append(f"{len(found['empty'])} bos slayt ogrenciye gidiyor")
    if found["dangling"]:
        problems.append(f"{len(found['dangling'])} kopuk tetikleyici")
    if found["ilk_slaydi_bos"]:
        print(f"  ILK SLAYDI BOS SAHNE: {found['ilk_slaydi_bos']}")
        problems.append(f"{len(found['ilk_slaydi_bos'])} sahnenin ILK slaydi "
                        "bestelenmemis (menuden erisilebilir)")
    print(f"  KURSUN ACILDIGI SLAYT: {found['kurs_ilk_slaydi']}  "
          f"{'BOS' if found['kurs_ilk_bos'] else 'bestelenmis'}")
    if found["kurs_ilk_bos"]:
        problems.append(f"kurs BOS bir slaytla aciliyor "
                        f"({found['kurs_ilk_slaydi']}) — ogrencinin gordugu "
                        "ilk ekran")

    print("\n=== SAHNE DAGILIMI ===")
    for name, data in found["scenes"].items():
        mark = "  <- tamami bos" if data["empty"] == data["slides"] else ""
        print(f"  {name[:24]:<26} slayt {data['slides']:>2}  bos "
              f"{data['empty']:>2}  soru {data['questions']}{mark}")
    return problems


# --------------------------------------------------------- pozitif kontrol
#
# Dondurulmus referansin sayilari. Bunlar bir HEDEF degil, dedektorun CIPASI:
# referans bilerek bozuk bir snapshot ve o bozukluk sabittir. Dedektor 13 bos
# slayt bulursa korlesmis, 15 bulursa fazla sayiyor -- IKISI DE bagirmali.
# Tek yonlu bir esik (">= 14") korlesmeyi yakalar, fazla saymayi kacirir; bu
# projede tek yonlu guard'in kazanimi sessizce kaybettirdigi ucuncu yer olur.
#
# Sayilar 2026-08-16'da dondurulmus referans uzerinde olculdu.
REFERANS = ROOT.parent / "test" / "_referans" / "referans.story"
SAGLAM = ROOT.parent / "test" / "0_duz_kopya.story"

BEKLENEN_BOZUK = {
    "bos slayt": 14,
    "kopuk tetikleyici": 43,
    "etkilesim tasiyan": 5,
    "quiz'e kayitli": 0,
    "kayitsiz soru": 5,
    "ilk slaydi bos sahne": 4,
    "dolu sahne": 5,
    # Referans, duzeltme ONCESI kodla uretildi: bos bir slaytla aciliyor.
    # Bu 1, duzeltmenin gerektigini kanitlayan sabit -- 0 olursa referans
    # degismis demektir, duzeltme calismis demek degil.
    "kurs bos aciliyor": 1,
}
# Gercek, elle yazilmis bir kursun kaydi. Bu ayak olmadan dedektor "her seye
# kayitsiz de" diyerek birinci ayagi gecerdi.
BEKLENEN_SAGLAM = {
    "etkilesim tasiyan": 11,
    "quiz'e kayitli": 11,
    "kayitsiz soru": 0,
    "sorusuz kayit": 0,
    "kurs bos aciliyor": 0,
}


def _sayilar(found: dict) -> dict:
    return {
        "bos slayt": len(found["empty"]),
        "kopuk tetikleyici": len(found["dangling"]),
        "etkilesim tasiyan": len(found["scored"]),
        "quiz'e kayitli": len(found["kayitli"]),
        "kayitsiz soru": len(found["kayitsiz"]),
        "sorusuz kayit": len(found["sorusuz_kayit"]),
        "ilk slaydi bos sahne": len(found["ilk_slaydi_bos"]),
        "dolu sahne": len(found["dolu_sahneler"]),
        "kurs bos aciliyor": int(found["kurs_ilk_bos"]),
    }


def _olc(path: Path) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return _sayilar(survey(StoryPackage(path)))


def kontrol() -> int:
    """Dedektor hala goruyor mu -- ve gormemesi gerekeni gormuyor mu?"""
    import shutil
    for path in (REFERANS, SAGLAM):
        if not path.is_file():
            print(f"Kontrol dosyasi yok: {path}")
            return 2

    kirik: list[str] = []

    print("=== 1. BILINEN BOZUK (dondurulmus referans) ===")
    bozuk = _olc(REFERANS)
    print(f"  {'olcu':<24}{'beklenen':>9}{'olculen':>9}")
    for ad, bekleniyor in BEKLENEN_BOZUK.items():
        olculen = bozuk[ad]
        tuttu = olculen == bekleniyor
        yon = "" if tuttu else ("  <- AZ SAYIYOR (korlesme)" if olculen < bekleniyor
                                else "  <- COK SAYIYOR")
        print(f"  {ad:<24}{bekleniyor:>9}{olculen:>9}{yon}")
        if not tuttu:
            kirik.append(f"{ad}: beklenen {bekleniyor}, olculen {olculen}")

    print("\n=== 2. BILINEN SAGLAM (gercek, elle yazilmis kurs) ===")
    saglam = _olc(SAGLAM)
    print(f"  {'olcu':<24}{'beklenen':>9}{'olculen':>9}")
    for ad, bekleniyor in BEKLENEN_SAGLAM.items():
        olculen = saglam[ad]
        print(f"  {ad:<24}{bekleniyor:>9}{olculen:>9}")
        if olculen != bekleniyor:
            kirik.append(f"saglam kurs/{ad}: beklenen {bekleniyor}, "
                         f"olculen {olculen}")

    # Ucuncu ayak, ve digerlerinin anlamini veren ayak. Ilk ikisi gecip de
    # dedektor atil olabilir: saglam kursta "kayitsiz 0" demek, hicbir seyi
    # kayitsiz saymayan bir dedektor icin de dogrudur. Kaydi KASTEN silip
    # tam olarak bir kayitsiz soru bekleniyor.
    print("\n=== 3. KASTEN BOZULMUS (saglam kursun bir kaydi silinir) ===")
    work = ROOT.parent / "test" / "_canary" / "kayit_bozuk.story"
    work.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SAGLAM, work)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pkg = StoryPackage(work)
        story = pkg.parse("story/story.xml")
        silinen = None
        for quiz in story.iter("quiz"):
            id_list = quiz.find("questionIdLst")
            if id_list is not None and len(id_list):
                silinen = (list(id_list)[0].text or "").strip()
                id_list.remove(list(id_list)[0])
                break
        pkg.replace_xml("story/story.xml", story)
        pkg.save(work, backup=False)
    if silinen is None:
        print("  saglam kursta silinecek kayit yok — ucuncu ayak kurulamadi.")
        kirik.append("kasten bozma ayagi kurulamadi")
    else:
        bozulmus = _olc(work)
        print(f"  silinen kayit: {silinen[:8]}...")
        print(f"  {'olcu':<24}{'beklenen':>9}{'olculen':>9}")
        for ad, bekleniyor in (("quiz'e kayitli", BEKLENEN_SAGLAM["quiz'e kayitli"] - 1),
                               ("kayitsiz soru", 1)):
            olculen = bozulmus[ad]
            print(f"  {ad:<24}{bekleniyor:>9}{olculen:>9}")
            if olculen != bekleniyor:
                kirik.append(f"kasten bozuldu/{ad}: beklenen {bekleniyor}, "
                             f"olculen {olculen}")

    print()
    if kirik:
        print(f"{len(kirik)} KONTROL TUTMADI:")
        for k in kirik:
            print(f"  ! {k}")
        print("\nDedektorun kendisi degismis olabilir. Sayilar bilerek "
              "degistiyse\nBEKLENEN_* tablolarini guncelleyin; degilse bir "
              "gerileme var.")
        return 1
    print("Dedektor tutuyor: bilinen bozuk kursu birebir sayiyor, saglam "
          "kursu\ntemiz buluyor, ve kasten silinen tek kaydi yakaliyor.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("story", nargs="?")
    parser.add_argument("--sections", type=int)
    parser.add_argument("--per-section", type=int)
    parser.add_argument("--kontrol", action="store_true",
                        help="dedektorun pozitif kontrolu (iki yonlu)")
    args = parser.parse_args()
    if args.kontrol:
        return kontrol()
    if not args.story:
        parser.error("bir kurs dosyasi verin ya da --kontrol kullanin")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pkg = StoryPackage(Path(args.story).resolve())
        found = survey(pkg)
    problems = report(found, sections=args.sections,
                      per_section=args.per_section)

    print()
    if problems:
        print(f"{len(problems)} ISLEVSEL EKSIK:")
        for p in problems:
            print(f"  ! {p}")
        print("\nHicbiri silinmedi: kaynak dosyadaki slaytlar kullanicinin.")
        return 1
    print("Islevsel olarak eksiksiz.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
