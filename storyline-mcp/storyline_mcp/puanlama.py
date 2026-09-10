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


def puanli_slaytlar(pkg: StoryPackage, index: dict) -> list[str]:
    """Puanli etkilesim tasiyan slaytlar. Zincirin ILK halkasi.

    Ayri bir fonksiyon cunku IKI kosul bunu soruyor: "sonuc slaydi yoksa
    ortada puanlanacak bir sey var mi" ve "questionIdLst hepsini kapsiyor
    mu". Iki kopya, iki farkli kesit ve sessizce ayrisan iki sayi demekti.
    """
    return [ref.basename for part, ref in index.items()
            if any(e.tag.endswith("Intr") and e.tag != "rsltsIntr"
                   and e.find("intrProps") is not None
                   for e in pkg.parse(part).iter())]


def zincir(pkg: StoryPackage) -> list[str]:
    """Puanlama zinciri BÜTÜN mü? Kırıkları adıyla döner.

    Sonuc slaydi YOKSA da konusur: puanli soru varken sonuc slaydinin
    olmamasi zincirin bir kirigidir (2026-09-10'da eklendi; onceden
    kosulsuz bos donuyordu ve en eksik kurs en temiz gorunuyordu).

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
        # SESSIZLIK, "SORUN YOK" DEMEK DEGIL -- VE BURADA OYLE OKUNUYORDU.
        #
        # Eski satir kosulsuz `return []` idi ve gerekcesi makuldu: "sonuc
        # slaydi yoksa iddia da yok". Ama olculdu (2026-09-10, diske
        # yazilmis dosya): uc puanli soru + sonuc slaydi YOK ->
        # `zincir` bos, yani EN EKSIK kurs en temiz gorunuyordu.
        # Ogrenci puanini hic gormuyor, LMS'e hicbir sey gitmiyor.
        #
        # Iddiasizlik dogru cevap YALNIZCA ortada puanlanacak bir sey
        # yokken. Puanli soru varsa sonuc slaydinin YOKLUGU zincirin
        # ucuncu halkasinin kirikligidir, ayri bir sinif degil.
        puanli = puanli_slaytlar(pkg, index)
        if puanli:
            return ["%d puanli slayt var ama SONUC SLAYDI YOK (%s): ogrenci "
                    "puanini hic gormez ve LMS'e rapor gitmez -- "
                    "add_results_slide ile kapatilmali"
                    % (len(puanli), ", ".join(puanli[:4]))]
        return []                    # puanlanacak bir sey de yok

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
    puanli = puanli_slaytlar(pkg, index)
    kayitsiz = [b for b in puanli if b not in kayitli]
    if kayitsiz:
        kirik.append("%d puanli slayt quiz'e kayitli degil (%s): puanlari "
                     "toplama girmez" % (len(kayitsiz), ", ".join(kayitsiz[:4])))

    # 3b -- AYNASI. 3. kosul TEK YONLUYDU: "questionIdLst puanli her slaydi
    # KAPSAYACAK". Tersi yazili degildi -- listede olup artik puanli
    # etkilesim TASIMAYAN bir slayt.
    #
    # NICIN SIMDI: o hal `delete_shape` gelene kadar ULASILAMAZDI (olculdu
    # 2026-09-11, diskteki 51 kursta 0 ornek). Silme araci kapiyi acti:
    # bir sorunun secenekleri ya da etkilesimi kaldirilirsa slayt durur,
    # kaydi durur, ama puanlanacak bir sey kalmaz. Storyline o kaydi
    # cozer ve toplama SIFIR puanli bir soru girer.
    #
    # AYRICA UZLASTIRICI ICIN GEREKLI: kablolama yalnizca EKLERSE bir ust
    # kumeye yakinsar (bayat kayit hic dusmez) ve bu kosul olmadan o
    # yakinsama olculemez. Ayna once yazildi, uzlastirici sonra.
    # 3c -- COZULEMEYEN KAYIT. `izleme` bunu zaten sayiyordu ve `zincir`
    # HIC bildirmiyordu: quiz bir guid'e kayit tutuyor, o guid hicbir
    # slayda cozulmuyor. `bos.story`nin kendi quiz'inde ALTI tane var.
    # Uzlastirici bunlari SILMIYOR (soru bankasi sorulari da boyle
    # gorunur -- bkz. `kablola`); ispatsiz bir silme yerine bildirim.
    # KAPSAM, VE OLCULEMEDIGI ICIN YAZILIYOR (2026-09-11). Bu kosulun
    # cozunurlugu `izleme.by_guid`den geliyor ve o `model.slide_index`
    # uzerine kurulu -- yani `sceneLst`teki slaytlar. SORU BANKASI
    # sorulari bankanin KENDI sahnesinde yasiyor
    # (`quizMgr/bankLst/scene/sldIdLst`) ve o sahne `sceneLst`te DEGIL.
    #
    # Dolayisiyla banka DOLU bir projede, bankadan gelen kayitlar burada
    # "cozulemeyen" gorunebilir ve bu kosul HER KOSUDA konusur --
    # kullanicinin kapatamayacagi bir uyari. Yanlis uyari zamanla butun
    # uyarilari degersizlestirir (ayni gerekce compose.py'de yazili).
    #
    # BUGUN OLCULEMIYOR, ve bu saklanmiyor: korpustaki 52 kursun 52'sinde
    # `bankLst` VAR ama hepsi BOS; donors/ havuzundaki 9 projede de banka
    # slaydi 0. Yani elde banka dolu tek bir fikstur yok.
    #
    # ACIK SORU, ve bir gercek proje tek acista cevaplar: Storyline banka
    # sorularini `questionIdLst`e HIC kaydediyor mu, yoksa yalnizca
    # CEKILEN slaytlari mi kaydediyor? Cevap "hic" ise buradaki risk
    # yoktur ve bu not bir cumleye iner. Cevap "kaydediyor" ise
    # cozunurluk `bankLst/scene/sldIdLst` uyelerini de kapsamali.
    cozulemeyen = sorted({g for q in _iz["quizzes"] for g in q["cozulemeyen"]})
    if cozulemeyen:
        kirik.append("%d quiz kaydi hicbir slayda cozulmuyor (%s): ya silinmis "
                     "bir slayda ya da soru bankasina isaret ediyor -- arac "
                     "bunlari SILMEZ, once neyi gosterdigi bilinmeli"
                     % (len(cozulemeyen),
                        ", ".join(g[:8] for g in cozulemeyen[:4])))

    bayat = [b for b in kayitli if b not in set(puanli)]
    if bayat:
        kirik.append("%d slayt quiz'e KAYITLI ama puanli etkilesim tasimiyor "
                     "(%s): toplama sifir puanli soru girer"
                     % (len(bayat), ", ".join(sorted(bayat)[:4])))

    # 4 -- LMS hedefi sonuc slaydi mi
    if _iz["lms_bos"]:
        kirik.append("quizMgr.lmsResultSlideG BOS: LMS okuyacagi slaydi "
                     "bilmiyor")
    elif _iz["lms_hedefi"] != ad:
        kirik.append("quizMgr.lmsResultSlideG %r gosteriyor, sonuc slaydi %r"
                     % (_iz["lms_hedefi"], ad))
    return kirik




def cevaplanamaz(pkg: StoryPackage, index: dict) -> list[dict]:
    """Doğru cevabı HİÇ işaretlenmemiş sorular -- öğrenci asla tutturamaz.

    NICIN BU BICIM, ve olcum once yapildi (2026-09-10). `add_question`
    dogruluk isaretini `choices/*/scoringData[@correct]` uzerine yaziyor:

        correct_set = set(correct)
        for i, choice_el in enumerate(choice_els):
            scoring.set("correct", "true" if i in correct_set else "false")

    Yani `i` HER ZAMAN 0..n-1 ve kume disindaki her deger sessizce duser.
    Uc girdi de ayni artefakti uretiyor (olculdu, 4 secenekli soru):

        correct=[0..3]  -> tam bir scoringData correct="true"
        correct=[9]     -> HICBIRI
        correct=[-1]    -> HICBIRI    <- Python indekslemesi UYGULANMIYOR
        correct=[]      -> HICBIRI

    `-1`in son secenegi isaretlemesinden kaygilanilmisti; olcum bunu
    disladi. Dolayisiyla aranacak sekil TEK ve sade: "hic dogru yok".
    "Yanlis dogru" diye bir hal uretilmiyor, o yuzden aranmiyor.

    KAPSAM BEYAZ LISTE, VE BU BIR DUZELTME (olculdu 2026-09-10).
    Ilk surum "choices tasiyan her etkilesim" diyordu ve diskteki 32
    kursun 18'inde tam olarak 1 bulgu uretti -- 18 bagimsiz yazim hatasi
    degil, bir OLCUM IMZASI. Sebep: `dragDropIntr` de `choices` tasiyor
    ama dogrulugu orada TUTMUYOR; tuzla.story/slide9'da dort secenegin
    dordu de `scoringData correct="false"`, dogruluk surukleme
    ciftlerinde. Yani olcu, saglam surukle-birak sorularini cevapsiz
    sayiyordu.

    Beyaz liste, kara liste DEGIL: kara liste yeni bir soru tipini
    sessizce yanlis olcerdi. Burada yalnizca mekanizmasi OLCULMUS iki tip
    var; otekiler (dragDrop, freeHotSpot, freeTextEntry) bu sayinin
    DISINDA ve sifir bulgu "her soru cevaplanabilir" demek degil,
    "tek/cok secmeli sorularin hepsi cevaplanabilir" demektir.
    """
    OLCULEN_TIPLER = ("freePickOneIntr", "freePickManyIntr")
    bulgular = []
    for part, ref in index.items():
        root = pkg.parse(part)
        for intr in root.iter():
            if intr.tag not in OLCULEN_TIPLER:
                continue
            secenekler = intr.find("choices")
            if secenekler is None or not len(secenekler):
                continue
            dogru = sum(
                1 for secenek in secenekler
                if (secenek.find("scoringData") is not None
                    and (secenek.find("scoringData").get("correct") or "")
                    .lower() == "true"))
            if dogru == 0:
                bulgular.append({
                    "slide": ref.basename, "slide_name": ref.name,
                    "interaction": intr.tag, "choices": len(secenekler),
                    "problem": "hicbir secenek dogru isaretli degil: "
                               "ogrenci bu soruyu dogru cevaplayamaz"})
    return bulgular


def eksik_sonuc_uyarisi(pkg: StoryPackage) -> str:
    """Bu kurs bir puan raporlayabilir mi -- SORUYU EKLEYEN AN İÇİN.

    NICIN UYARI, RED DEGIL -- VE FARK BICIMDE DEGIL, KAYBIN SEKLINDE.
    `compose_slide`in reddi bir EYLEMIN icinde durabiliyor cunku kayip o
    eylemin SONUCU: slaydi bastan cizmek katmanlari goturuyor. Burada
    kayip bir YOKLUK -- hicbir eylem onu uretmiyor, dolayisiyla hicbir
    eylemin icine konamaz. Yazmayi reddetmek daha kotusu olurdu: yapim
    ortasinda soru eklenmis ve sonuc slaydi henuz eklenmemis bir kurs
    KUSURLU DEGIL, ARA HALDIR, ve o hali reddeden bir kapi dogru kurulusu
    imkansiz kilar.

    YUKLEM `zincir`IN KENDISI, ve BU BIR DUZELTME (2026-09-10).
    Ilk surum kendi kosulunu tasiyordu: "pakette `rsltsIntr` var mi".
    O, `zincir`in DORT kosulundan yalnizca BIRIYDI (sonuc slaydinin
    varligi). Sonuc: `add_results_slide` cagrildigi anda uyari
    susuyordu -- zincir kurulsun ya da kurulmasin. Diskte olculdu:
    `rsltsIntr` tasiyan 10 kursun 8'inde `zincir` kirik bildiriyor ve
    uyari hepsinde SESSIZ. Yani uyari, var olmak icin kuruldugu
    basarisizligin BIR ADIM ONCESINDE susuyordu.

    Duzeltme yapiskanlik degil, tek yuklem: `zincir` dordunu de
    hesapliyor ve temizse BOS donuyor. Sonuc slaydinin yoklugu da o
    bulgulardan biri. Uyari boylece yalnizca DOGRU olayda susar.
    `neler`in dizgeden yapiya cevrilmesiyle ayni hamle: tek soru icin
    iki yuklem tutmayi birakmak.

    KAYDEDILMIS HALE ESIT OLDUGU AN cagrilmali (yazmadan hemen sonra):
    `izleme` story.xml'i okuyor ve bellekteki agac ancak o noktada
    dosyayla ayni.

    BU UYARI KALICI, md. 3 gelse bile. Kapanis adimi KABLOLAMA yapacak
    (quiz kaydi, quizG, lmsResultSlideG) ama SONUC SLAYDINI yoktan var
    ETMEYECEK -- karar ve gerekcesi `tools/ajan_yolu.py` basliginda.
    Dolayisiyla "sonuc slaydi hic yok" hali otomatik kapanmayacak ve bu
    cumle onu soylemeye devam edecek: olculdu (51 kurs), zinciri kirik
    34 kursun 14'u tam olarak bu halde.
    """
    kirik = zincir(pkg)
    if not kirik:
        return ""
    if len(kirik) == 1:
        return kirik[0]
    return "%s (+%d kirik daha; tamami icin audit)" % (kirik[0], len(kirik) - 1)


def kablola(pkg: StoryPackage) -> dict:
    """Quiz kaydını dosyadakiyle UZLAŞTIR. Değişmez, adım değil.

    NICIN HER YAZMADA. Kablolama TURETILMIS: hangi slaytlarin puanli
    etkilesim tasidigi ve hangisinde sonuc slaydi oldugu dosyada zaten
    yazili; icinde kullanici girdisi YOK. Turetilmis bir sey adim degil
    DEGISMEZDIR -- adim atlanabilir, degismez atlanamaz. Sohbet yolunun
    "bitti" ani olmadigi icin bir kapanis ADIMI kurulamiyordu; degismez
    o soruyu cozmuyor, ORTADAN KALDIRIYOR.

    GORUNUR ICERIK URETMEZ (md. 3 karari, bkz. tools/ajan_yolu.py):
    sonuc slaydi yoksa baglanacak bir sey de yoktur ve bu fonksiyon
    HICBIR SEY yapmaz. Yapim ortasindaki mesru ara hal -- soru var,
    sonuc slaydi henuz yok -- boylece kusur sayilmiyor. Yazma anindaki
    bir REDDIN yapamadigi sey buydu.

    UZLASTIRIR, EKLEMEZ. Yalnizca ekleyen bir surum bir UST KUMEYE
    yakinsardi: `delete_shape` ile etkilesimi kaldirilan bir sorunun
    kaydi listede kalir ve Storyline toplama sifir puanli bir soru
    katardi. Ucu birden yapiliyor ve ucu de ayri raporlaniyor.

    STORYLINE'IN OKUDUGU QUIZ'E yazar. `authoring.register_question`
    `story.iter("quiz")` kullaniyor ve iter ATILAN quizLst'in icine de
    iniyor; gorunmeyen bir quiz'e kayit yapmak hicbir sey yapmamakla
    ayni sey. Ayrimi `izleme` tutuyor, bu fonksiyon da ondan okuyor.

    DEGISIKLIK YOKSA DOSYAYA DOKUNMAZ (`degisti: False`). Kararli
    durumda maliyeti bir karsilastirma; olculdu (tools/kablolama_kapi.py):
    temiz bir kursta arac cagrilari 0 yazma uretiyor.
    """
    import xml.etree.ElementTree as ET

    index = model.slide_index(pkg)
    # `dusen_cozulemeyen` DUSURULMEZ, yalnizca BILDIRILIR: adi mirastir,
    # anlami asagida yazili (kanitlayabildigimiz kadarini sil).
    rapor = {"eklenen": [], "dusen_bayat": [], "dusen_cozulemeyen": [],
             "lms_yazildi": False, "degisti": False, "neden": ""}

    story = pkg.parse("story/story.xml")
    manager = story.find("quizMgr")
    if manager is None:
        rapor["neden"] = "quizMgr yok"
        return rapor
    listeler = manager.findall("quizLst")
    quiz = next(iter(listeler[0]), None) if listeler else None
    if quiz is None:
        # Sonuc slaydi (ve dolayisiyla quiz) henuz kurulmamis olabilir:
        # bu ARA HAL, kusur degil.
        rapor["neden"] = "Storyline'in okudugu quizLst'te quiz yok"
        return rapor

    guid_ile = {ref.guid: ref.basename for ref in index.values()}
    ad_ile = {ref.basename: ref.guid for ref in index.values()}
    puanli = set(puanli_slaytlar(pkg, index))

    id_list = quiz.find("questionIdLst")
    if id_list is None:
        id_list = ET.Element("questionIdLst")
        quiz.insert(0, id_list)

    mevcut = {}
    for el in list(id_list):
        g = (el.text or "").strip()
        mevcut.setdefault(g, []).append(el)

    # 1. BAYAT kayitlari dusur -- COZULEMEYENLERE DOKUNMA.
    #
    # KANITLAYABILDIGIMIZ KADARINI SIL. Bayat kayit ispatli: slayt
    # DURUYOR ve puanli etkilesim tasimiyor. Cozulemeyen kayit ise
    # ispatsiz -- guid'in neyi gosterdigini bilmiyoruz.
    #
    # VE BILMEMEK BURADA SOMUT BIR RISK (olculdu 2026-09-11): soru
    # bankasi sorulari SLAYT olarak yasiyor ama bankanin kendi
    # sahnesinde (`quizMgr/bankLst/scene/sldIdLst`), ve o sahne
    # `sceneLst`te DEGIL -- yani `model.slide_index`e girmiyorlar ve
    # buradan "cozulemeyen" gorunurler. Korpustaki 52 kursun 52'sinde
    # bankLst VAR (hepsi bugun bos, ama kullanicinin projesi bos olmak
    # zorunda degil). Onlari silmek, kullanicinin soru bankasi
    # kayitlarini sessizce yok etmek olurdu.
    #
    # Cozulemeyen kayit SILINMIYOR ama SAKLANMIYOR da: `zincir` onu
    # ayri bir kirik olarak bildiriyor. Rapor ve tamir ayri seyler.
    for g, ogeler in mevcut.items():
        basename = guid_ile.get(g)
        if basename is None:
            rapor["dusen_cozulemeyen"].append(g[:8])   # yalnizca BILDIRIM
        elif basename not in puanli:
            for el in ogeler:
                id_list.remove(el)
            rapor["dusen_bayat"].append(basename)

    # 2. EKSIK kayitlari ekle.
    kalan = {(el.text or "").strip() for el in list(id_list)}
    for basename in sorted(puanli):
        g = ad_ile.get(basename)
        if g and g not in kalan:
            oge = ET.SubElement(id_list, "item")
            oge.text = g
            rapor["eklenen"].append(basename)

    # 3. LMS hedefi -- deger ICAT EDILMIYOR, quiz kendi sonuc slaydini
    #    zaten biliyor.
    lms = manager.get("lmsResultSlideG") or ""
    hedef = quiz.get("resultSldG") or ""
    if (not lms or lms.startswith("00000000")) and hedef \
            and not hedef.startswith("00000000"):
        manager.set("lmsResultSlideG", hedef)
        manager.set("trackMode", "result")
        rapor["lms_yazildi"] = True

    # `dusen_cozulemeyen` DEGISIKLIK SAYILMAZ: dosyaya dokunulmadi.
    rapor["degisti"] = bool(rapor["eklenen"] or rapor["dusen_bayat"]
                            or rapor["lms_yazildi"])
    if rapor["degisti"]:
        pkg.replace_xml("story/story.xml", story)
    return rapor
