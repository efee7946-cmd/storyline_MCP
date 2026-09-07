"""Puanlama zinciri: soru -> quiz -> sonuc slaydi -> LMS.

NEDEN `storyline_mcp/` ICINDE, `tools/` ICINDE DEGIL. Bu kod URETIM
yolundan cagriliyor (panel/builder.py, kurs kaydedildikten sonra) ve
`panel/app.py` sys.path'e yalnizca depo kokunu ve `panel/`i koyuyor --
`tools/` ORADA YOK. `tools/completeness`ten import etmek panelde
ImportError verirdi ve benim except'im onu "zincir olculemedi" diye
okuyup HER kurs kurulumunu dusururdu.

Olculdu 2026-09-07: `tools/produced.py` bu kusuru GOREMIYOR, cunku kendi
sys.path'ine `tools/`u ekliyor -- yani kapi, urunun gezmedigi bir yoldan
geciyordu. `tools/completeness` artik buradan import ediyor; tek yetkili
kaynak burasi.
"""

from __future__ import annotations

from . import model
from .package import StoryPackage


def izleme(pkg: StoryPackage, index: dict) -> dict:
    """Puanlama zincirinin ikinci ve ucuncu halkasi: kayit ve hedef.

    questionIdLst'in cocuklari <item> ve guid ONITELIKTE DEGIL METINDE durur;
    attrib bos gelir. Oniteligi okumaya calisan bir surum her kaydi
    "cozulemedi" sayar ve saglam bir kursu bozuk gosterirdi.
    """
    story = pkg.parse("story/story.xml")
    by_guid = {ref.guid: ref.basename for ref in index.values()}
    manager = story.find("quizMgr")

    # STORYLINE'IN OKUDUGU LISTE. `quizMgr` birden fazla `quizLst` tasiyorsa
    # Storyline ILKINI okur, kalanini dosyadan atar (olculdu 2026-09-07:
    # yks.story acilip kaydedildi, ikinci listedeki `Quiz_Result` silinmis,
    # yerine bos bir `Quiz1` konmustu). Asagidaki dongu `story.iter("quiz")`
    # kullaniyor ve iter HER listenin icine iniyor -- yani var olmayan bir
    # quiz'i "var" gorur. Ayrimi tutan tek sey bu iki satir.
    listeler = manager.findall("quizLst") if manager is not None else []
    okunan = {q.get("g") for q in (listeler[0] if listeler else [])}

    registered: dict[str, str] = {}       # slayt -> quiz adi
    quizzes: list[dict] = []
    gorunmeyen: list[str] = []
    for quiz in story.iter("quiz"):
        id_list = quiz.find("questionIdLst")
        items = [(el.text or "").strip()
                 for el in (list(id_list) if id_list is not None else [])]
        name = quiz.get("name") or "(isimsiz)"
        if quiz.get("g") not in okunan:
            gorunmeyen.append(name)
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
        "quizlst_sayisi": len(listeler),
        "gorunmeyen_quiz": gorunmeyen,
        "registered": registered,
        "lms_hedefi": by_guid.get(lms),
        "lms_bos": not lms or lms.startswith("00000000"),
        "track_mode": manager.get("trackMode") if manager is not None else None,
    }


def zincir(pkg: StoryPackage) -> list[str]:
    """Sonuç slaydı varsa puanlama zinciri BÜTÜN mü? Kırıkları adıyla döner.

    TEK BIRLESIK IDDIA, cunku kablolama birbirinden BAGIMSIZ adimlardan
    olusuyor ve kismi tamamlanma basaridan ayirt edilemiyor. Kullanicinin uc
    kursu ikili degil bir TAYF gosterdi (olculdu 2026-09-07):

        dosya             quizLst   rsltsIntr.quizG      lmsResultSlideG
        savunma           bos       a8f5b72b (yabanci)   00000000...
        etkiliyapayzeka   bos       a8f5b72b (yabanci)   slide10  OK
        tuzla             1 quiz    a8f5b72b (eslesiyor) slided   OK

    Ortadaki satir meselenin ta kendisi: LMS hedefi YAZILMIS ama quiz hic
    kurulmamis. Iki adim, tek ortak iddia yok -- ve her adim tek basina
    "yapildi" gorunuyor.

    a8f5b72b tohumun kendi kursundan gelen bir GUID. `install_slide` yalnizca
    slaydin TANIMLADIGI guid'leri yeniliyor; `quizG` bir REFERANS, oldugu
    gibi geciyor. Hedefte o quiz yoksa sonuc slaydi bir HAYALETI gosteriyor.

    BES KOSUL, cunku hepsi birden tutmadan puan LMS'e gitmiyor:

        0  quiz, Storyline'in OKUDUGU quizLst'te duracak
        1  sonuc slaydi varsa quizLst'te en az bir quiz olacak
        2  sonuc slaydinin `quizG`si var olan bir quiz'i gosterecek
        3  questionIdLst puanli etkilesim tasiyan HER slaydi kapsayacak
        4  quizMgr.lmsResultSlideG o sonuc slaydinin GUID'i olacak

    NEDEN "verified_ok" YETMEDI. O olcu XML butunlugune bakiyor -- parca
    sayisi, BOM, ayristirma. Bir dosya kusursuz bicimli olup LMS'e hicbir sey
    raporlamayabilir; savunma.story tam olarak oyle.

    SIFIRINCI KOSUL SONRADAN EKLENDI (2026-09-07) ve digerlerinden farkli
    bir sinifta: 1-4 dosyada NE VAR diye soruyor, 0 ise Storyline'in ONU
    OKUYUP OKUMADIGINI. `_quiz_kur` `quizLst`i kokte ariyordu (o ise
    `quizMgr`in cocugu), her seferinde ikinci bir liste uretiyordu ve
    Storyline ilkini okuyup otekini atiyordu. Dort kosulun dordu de yesildi
    -- cunku dordu de `story.iter("quiz")` kullaniyor ve iter atilan
    listenin icine de iniyor.

    KAYDEDILMIS DOSYA UZERINDE cagrilmali, bellekteki pkg uzerinde degil:
    ogrencinin aldigi sey dosya.
    """
    index = model.slide_index(pkg)
    _iz = izleme(pkg, index)
    sonuc_slaytlari = []
    quiz_g_ref = None
    for part, ref in index.items():
        kok = pkg.parse(part)
        rslts = next((e for e in kok.iter() if e.tag == "rsltsIntr"), None)
        if rslts is not None:
            sonuc_slaytlari.append((ref.basename, kok.get("g") or ""))
            quiz_g_ref = quiz_g_ref or (rslts.get("quizG") or "")
    if not sonuc_slaytlari:
        return []                    # sonuc slaydi yoksa iddia da yok

    kirik: list[str] = []
    ad, sonuc_guid = sonuc_slaytlari[0]

    # 0 -- quiz Storyline'in OKUDUGU listede mi
    #
    # DOSYADA OLMAK YETMIYOR. `quizMgr` iki `quizLst` tasiyorsa Storyline
    # ilkini okur ve ikincisini -- icindeki quiz'le birlikte -- atar. Kurs
    # bizim gozumuzde tam, ogrencinin dosyasinda puansiz.
    #
    # Bu kosul digerlerinden ONCE geliyor cunku onlarin hepsi
    # `story.iter("quiz")`e dayaniyor ve iter atilacak listeyi de sayiyor:
    # 1-4 arasi kosullarin dordu birden YESIL kalirken quiz yok olabilir.
    # Kapinin denetledigi seyle ayni cozucuyu kullanmasi tam olarak bu.
    if _iz["gorunmeyen_quiz"]:
        kirik.append("quizMgr %d adet quizLst tasiyor; %s ikincisinde ve "
                     "Storyline onu ATIYOR -- sorular puanlanmaz"
                     % (_iz["quizlst_sayisi"],
                        ", ".join(_iz["gorunmeyen_quiz"])))
        return kirik                 # kalan kosullar bu quiz'e dayaniyor

    # 1 -- quiz var mi
    if not _iz["quizzes"]:
        kirik.append("sonuc slaydi (%s) var ama quizLst BOS: kurs LMS'e "
                     "hicbir puan raporlayamaz" % ad)
        return kirik                 # kalan uc kosul bunun turevi

    # 2 -- sonuc slaydinin quizG'si var olan bir quiz'i mi gosteriyor
    story = pkg.parse("story/story.xml")
    quiz_guidleri = {q.get("g") for q in story.iter("quiz")}
    if quiz_g_ref and quiz_g_ref not in quiz_guidleri:
        kirik.append("sonuc slaydinin quizG'si (%s) pakette olmayan bir "
                     "quiz'i gosteriyor -- tohumdan devralinmis referans"
                     % quiz_g_ref[:8])

    # 3 -- puanli her slayt kayitli mi
    kayitli = set(_iz["registered"])
    puanli = [ref.basename for part, ref in index.items()
              if any(e.tag.endswith("Intr") and e.tag != "rsltsIntr"
                     and e.find("intrProps") is not None
                     for e in pkg.parse(part).iter())]
    kayitsiz = [b for b in puanli if b not in kayitli]
    if kayitsiz:
        kirik.append("%d puanli slayt quiz'e kayitli degil (%s): puanlari "
                     "toplama girmez" % (len(kayitsiz), ", ".join(kayitsiz[:4])))

    # 4 -- LMS hedefi sonuc slaydi mi
    if _iz["lms_bos"]:
        kirik.append("quizMgr.lmsResultSlideG BOS: LMS okuyacagi slaydi "
                     "bilmiyor")
    elif _iz["lms_hedefi"] != ad:
        kirik.append("quizMgr.lmsResultSlideG %r gosteriyor, sonuc slaydi %r"
                     % (_iz["lms_hedefi"], ad))
    return kirik


