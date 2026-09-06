"""SIFIRDAN yeni bir modul kurar ve 2026-09-06'da duzeltilen sinifları sinar.

NICIN VAR. Kullanicinin elle yaptigi denetim yirmi dort kusur buldu ve
onlarin bir kismi kaynakta duzeltildi. Ama "duzeltildi" ile "bir daha
olmayacak" ayni sey DEGIL: duzeltme kaynaktaysa bile, sonraki bir
degisiklik onu sessizce geri alabilir.

Kullanicinin sordugu soru tam buydu -- "bunlari sadece bu modul icin degil,
ileride panelden uretecegim modullerde olmamasi icin yapiyorsun degil mi".
Bu dosya o sorunun makine tarafindan tekrarlanabilir cevabi.

FIKSTUR DEGIL, URETIM YOLU. Kurs `bos.story`den baslayip ureticinin KENDI
fonksiyonlariyla kuruluyor: `add_slide` + `compose_slide` + `add_question` +
`add_drag_question` + `add_text_question` + `add_layer`. Model cagrisi yok
(kapilar model cagirmaz), ama bu fonksiyonlar HER IKI yolun da ortak
govdesi -- panel brief yolu da, komut yolu da buradan geciyor.

SINANAN OTUZ BIR SINIF, her biri kullanicinin denetimindeki bir maddeye bagli:

    1  kopuk tetikleyici          hedefi cozulmeyen atlama       (#1)
    2  olu puan degiskeni         tanimsiz degiskene yazan trig  (#4)
    3  intrProps cozuluyor mu     submit'te katman bulunmuyordu  (#5)
    4  taahhut slaydi gezinme     ogrenci slaytta mahsur         (#2)
    5  katman kapaniyor mu        pop-up dugmesi olu             (#8)
    6  katmanda yabanci metin     baska kursun icerigi           (#11)
    7  slayt adlari ayri mi       menude dokuz kez "Intro Slide" (#15)
    8  Turkce buyuk harf          I/I ayrimi                     (#13)
    9  oynatici etiketleri        Next/Submit/resume Ingilizce   (#20)
   10  puanlama zinciri           soru->quiz->sonuc->LMS      (#3/#24)
   11  dekoratif sekil gizli      metinsiz sekil acc=true        (#22)
   12  koordinat uzayi tek        720 ve 1920 karisik            (#16)
   13  soru katmani yabanci       baska kursun cevap listesi    (#11b)
   14  punto merdiveni            sonuc slaydi ayri olcekte      (#17)
   15  tasma                      baslik+govde tek kutuda        (#12)
   16  degisken referanslari      %Quiz_Result...% cozulmuyor   (#3b)
   17  katman metni ayri          iki yanlis katman ayni metin    (#9)
   18  dugme ziplamiyor           katman degisince yer degistiriyor (#10)
   19  quizsiz kaynak             quiz yoksa zincir kurulmuyordu  (#3c)
   20  gonderiden geciyor         soru hic submit edilmiyordu      (#4)
   21  sahne adi okunur           menude '01_YZ_Nedir' goruluyordu  (#8)
   22  son slayt ILERI            gidecek yer yokken dugme duruyordu (#10)

Bir sinif kirmizi olursa mesaj HANGI maddeye dondugunu soyler, cunku
"kopuk tetikleyici 3" tek basina ne yapilmasi gerektigini anlatmiyor.

    python tools/yeni_modul.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import completeness
from storyline_mcp import authoring, clone, compose, model, preview, shapes
from storyline_mcp.package import StoryPackage

BLANK = ROOT.parent / "test" / "bos.story"
# Donor kursun puan degiskeni: tohumlarin tasidigi, hedefte tanimsiz GUID.
OLU_PUAN_GUID = "8041a620-761b-41d3-955f-ed3c9a72cecc"

BASLIKLAR = ("Savunmanin Temel Ilkeleri",
             "Pozisyon Alma ve Kayma",
             "Iletisim ve Roller")


def kur(yol: Path) -> dict:
    """Yeni bir modul kurar ve olculecek parcalari geri verir."""
    shutil.copy2(BLANK, yol)
    pkg = StoryPackage(yol)
    sablon = list(model.slide_index(pkg).values())[0].basename

    icerik_parcalari = []
    for baslik in BASLIKLAR:
        r = authoring.add_slide(pkg, sablon, scene=None)
        compose.compose_slide(pkg, r["new_slide"], "content",
                              title=baslik, eyebrow=baslik, body="Govde metni.")
        icerik_parcalari.append(pkg.slide_part_for(r["new_slide"]))

    # Acilir katman: icerik slaydinin uzerine
    katman = authoring.add_layer(pkg, model.slide_index(pkg)[icerik_parcalari[0]].basename,
                                 "Neden Onemli", text="Bu maddenin aciklamasi.")

    soru = authoring.add_question(pkg, None, "Hangisi dogru?",
                                  ["A secenegi", "B secenegi", "C secenegi"], [0])
    coklu = authoring.add_question(pkg, None, "Hangileri dogru?",
                                   ["A", "B", "C", "D", "E"], [0, 1])
    surukle = authoring.add_drag_question(
        pkg, "Her ogeyi dogru kutuya surukle.",
        {"Kutu bir": ["Kisa ad", "Kisa ad"], "Kutu iki": ["Kisa ad", "Kisa ad"]})
    taahhut = authoring.add_text_question(pkg, "Bir somut adim yaz.", None)
    sonuc = authoring.add_results_slide(pkg)
    # Ureticinin build() sonunda yaptigi son adim: kursun son slaydinda
    # olu ILERI dugmesini kapat. `produced.py` bu yolu gezmiyor (olculdu:
    # ilerleme.kur oradaki kosuda hic calismiyor), o yuzden kapi burada.
    authoring.son_slaydin_ilerisini_kapat(pkg)

    pkg.save(yol, backup=False)
    return {"icerik": icerik_parcalari, "katman": katman, "soru": soru,
            "coklu": coklu, "surukle": surukle, "taahhut": taahhut,
            "sonuc": sonuc}


def main() -> int:
    if not BLANK.is_file():
        print("Kaynak yok: %s" % BLANK)
        return 2
    yol = Path(tempfile.gettempdir()) / "yeni_modul.story"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        kurulan = kur(yol)
        pkg = StoryPackage(yol)

    kirmizi: list[str] = []

    def bak(etiket: str, madde: str, tamam: bool, olculen: str) -> None:
        print("  %-28s %-9s %s" % (etiket, madde, olculen))
        if not tamam:
            kirmizi.append("%s (%s)" % (etiket, madde))

    print("Yeni modul kuruldu: %d slayt" % len(model.slide_index(pkg)))
    print()

    # 1 -- kopuk tetikleyici
    kopuk = completeness.dangling_triggers(pkg)
    bak("kopuk tetikleyici", "#1", not kopuk,
        "%d (beklenen 0)" % len(kopuk))

    # 2 -- olu puan degiskeni
    olu = 0
    for ad in list(pkg._order):
        if ad.endswith(".xml"):
            olu += pkg.read(ad).decode("utf-8", "replace").count(OLU_PUAN_GUID)
    bak("olu puan degiskeni", "#4", olu == 0, "%d referans (beklenen 0)" % olu)

    # 3 -- intrProps kendi katmanlarini gosteriyor mu
    cozulen = cozulmeyen = 0
    for part, ref in model.slide_index(pkg).items():
        root = pkg.parse(part)
        kl = root.find("sldLayerLst")
        ic = {k.get("g") for k in (list(kl) if kl is not None else [])}
        for props in root.iter("intrProps"):
            for alan in ("corFbG", "incFbG"):
                g = props.get(alan) or ""
                if not g or g.startswith("00000000"):
                    continue
                if g in ic:
                    cozulen += 1
                else:
                    cozulmeyen += 1
    bak("intrProps cozuluyor", "#5", cozulmeyen == 0 and cozulen > 0,
        "%d cozulen / %d cozulmeyen" % (cozulen, cozulmeyen))

    # 4 -- taahhut slaydinda gezinme acik mi
    t_part = pkg.slide_part_for(kurulan["taahhut"]["new_slide"])
    nav = next(pkg.parse(t_part).iter("navData"), None)
    acik = (nav is not None and nav.get("next") == "true"
            and nav.get("submit") == "false")
    bak("taahhut gezinmesi", "#2", acik,
        "next=%s submit=%s" % (nav.get("next") if nav is not None else "?",
                               nav.get("submit") if nav is not None else "?"))

    # 5 ve 6 -- acilir katman: kapaniyor mu, yabanci metin var mi
    k_part = pkg.slide_part_for(kurulan["katman"]["slide"])
    kok = pkg.parse(k_part)
    hedef = next((k for k in (kok.find("sldLayerLst") or [])
                  if k.get("g") == kurulan["katman"]["layer_guid"]), None)
    trig = sum(len(tl) for tl in hedef.iter("trigLst")) if hedef is not None else 0
    bak("katman kapatma trig", "#8", trig > 0, "%d tetikleyici" % trig)

    metinler = []
    if hedef is not None:
        for sh, _t, doc, _s in model._iter_text_shapes(hedef):
            m = model._doc_text(doc).strip()
            if m:
                metinler.append(m)
    yabanci = [m for m in metinler
               if m not in ("Bu maddenin aciklamasi.", "Devam")]
    bak("katmanda yabanci metin", "#11", not yabanci,
        "%d (%s)" % (len(yabanci), yabanci[:2] or "yok"))

    # 7 -- slayt adlari ayri mi
    adlar = [pkg.parse(p).get("name") or "" for p in kurulan["icerik"]]
    bak("slayt adlari ayri", "#15", len(set(adlar)) == len(adlar),
        "%d slayt / %d ayri ad" % (len(adlar), len(set(adlar))))

    # 9 -- oynatici etiketleri Turkce mi
    import re as _re
    _ham = pkg.read("story/playerProps.xml").decode("utf-8-sig", "replace")
    _eksik = []
    for _k, _tr in __import__("storyline_mcp.settings", fromlist=["x"]).OYNATICI_TR.items():
        _m = _re.search(r'<string id="%s"[^>]*>([^<]*)</string>' % _re.escape(_k), _ham)
        if _m is not None and _m.group(1) != _tr:
            _eksik.append(_k)
    bak("oynatici Turkce", "#20", not _eksik,
        "%d etiket cevrilmemis" % len(_eksik))

    # 10 -- puanlama zinciri: soru -> quiz -> sonuc slaydi -> LMS
    _s = completeness.survey(pkg)
    _iz = _s["izleme"]
    _olu = sum(len(q["cozulemeyen"]) for q in _iz["quizzes"])
    _bagli = [q for q in _iz["quizzes"] if q["sonuc_slaydi"]]
    _zincir = (not _s["kayitsiz"] and not _iz["lms_bos"]
               and _olu == 0 and bool(_bagli))
    bak("puanlama zinciri", "#3/#24", _zincir,
        "kayitsiz=%d olu_kayit=%d lms=%s sonuc_slaydi=%s"
        % (len(_s["kayitsiz"]), _olu, not _iz["lms_bos"],
           _bagli[0]["sonuc_slaydi"] if _bagli else None))

    # 11 -- dekoratif sekiller ekran okuyucudan gizli mi
    #
    # UC KEZ GENISLETILDI ve her genisleme bir olcumden geldi:
    #
    # (a) KATMANLAR DAHIL. Ilk surumu yalnizca `root.shapeLst`i geziyordu --
    #     duzelttigi kodla AYNI kor noktayi paylasiyordu, yani kusuru degil
    #     kodun varsayimini olcuyordu. Olculdu 2026-09-06: temelde 0,
    #     katmanlarda 7 acik dekoratif sekil.
    #
    # (b) KAYNAK DOSYANIN SLAYTLARI HARIC. O yedinin ikisi `bos.story`nin
    #     kendi slaydindaydi (slideb, "TIK1"/"TIK2") -- kullanicinin kendi
    #     icerigi. Bu arac ona dokunmuyor.
    #
    # (c) SORU-ILK BIR KURULUM DA SINANIR. `shapes.find_seed` "once
    #     projeninki" diyor: `page.band` yeni dikdortgen uretmez, pakette
    #     olani klonlar. Bir icerik slaydi once bestelenmisse onun temiz
    #     dikdortgeni kaynak olur ve soru slaydi TEMIZ dogar; hicbir icerik
    #     slaydi yoksa gomulu tohum kaynak olur ve KIRLI dogar. Bu
    #     fikstuurde her zaman once icerik slaydi var, yani kapi kusuru
    #     goremezdi (K33) -- ikinci bir paket, soruyla BASLAYARAK kuruluyor.
    _kaynak_slaytlar = set()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for _kp in model.slide_index(StoryPackage(BLANK)):
            _kaynak_slaytlar.add(_kp)

    def _acc_tara(_paket):
        _bulunan = []
        for _p11, _r11 in model.slide_index(_paket).items():
            if _p11 in _kaynak_slaytlar:
                continue
            _k11 = _paket.parse(_p11)
            for _ad11, _gv11 in model.bodies(_k11):
                _sl11 = _gv11.find("shapeLst")
                for _sh11 in (list(_sl11) if _sl11 is not None else []):
                    if _sh11.tag.endswith("Intr") or _sh11.tag in (
                            "btn", "rsltBtn", "feedBackBtn", "pic", "textEntry"):
                        continue
                    _g11 = _sh11.get("g") or ""
                    if not _g11 or model.shape_text(_gv11, _g11).strip():
                        continue
                    if (_sh11.get("acc") or "") == "true":
                        _bulunan.append("%s/%s/%s(%s)" % (
                            _r11.basename, _ad11 or "temel", _sh11.tag,
                            _sh11.get("name") or "-"))
        return _bulunan

    _acik_yer = _acc_tara(pkg)

    _yol11 = Path(tempfile.gettempdir()) / "yeni_modul_sorufirst.story"
    shutil.copy2(BLANK, _yol11)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _p11k = StoryPackage(_yol11)
        clone.create_scene(_p11k, "Bolum Bir")
        authoring.add_question(
            _p11k, None, "Hangisi dogru?",
            ["A secenegi", "B secenegi", "C secenegi"], [0],
            palette=compose.theme_palette("gece"), eyebrow="Bolum Bir",
            variant="sag")
        _p11k.save(_yol11, backup=False)
    _acik_yer += ["soru-ilk: " + x for x in _acc_tara(StoryPackage(_yol11))]

    bak("dekoratif sekil gizli", "#22", not _acik_yer,
        "%d metinsiz sekil ekran okuyucuya acik %s"
        % (len(_acik_yer), _acik_yer[:2]))

    # 12 -- koordinat uzayi tek mi
    from storyline_mcp import shapes as _shapes
    _sahne = _shapes.stage_size(pkg)
    _uzaylar = {_shapes.slide_size(pkg.parse(_p))
                for _p in model.slide_index(pkg)}
    bak("koordinat uzayi tek", "#16", _uzaylar == {_sahne},
        "sahne=%dx%d slayt uzaylari=%s" % (_sahne[0], _sahne[1],
                                           sorted(_uzaylar)))

    # 13 -- SORU katmanlarinda yabanci metin (11'in ikinci yolu)
    from storyline_mcp import compose as _c
    _yabanci_soru = []
    for _part, _ref in model.slide_index(pkg).items():
        _root = pkg.parse(_part)
        if not any(e.tag.endswith("Intr") for e in _root.iter()):
            continue
        for _k in list(_root.find("sldLayerLst") or []):
            for _sh, _e2, _d, _st in model._iter_text_shapes(_k):
                _t = model._doc_text(_d).strip()
                # Donor kursun izleri: bu modulun hicbir yerinde gecmeyen
                # ve tohumdan gelen ozgun cumleler.
                if _t in ("Yapışkan nottaki parola", "Varsayılan parolalı modem",
                          "Masada açıkta duran belgeler", "Açık Telefon",
                          "Açık kapı ve görüş alanı"):
                    _yabanci_soru.append((_ref.basename, _t))
    bak("soru katmani yabanci", "#11b", not _yabanci_soru,
        "%d donor metni" % len(_yabanci_soru))

    # 14 -- metin merdiveni (dugmeler haric)
    _disari = []
    for _part, _ref in model.slide_index(pkg).items():
        _root = pkg.parse(_part)
        for _kap in [_root] + list(_root.find("sldLayerLst") or []):
            for _sh, _e2, _d, _st in model._iter_text_shapes(_kap):
                # DUGMELER DISARIDA, ve bu ACIKCA yazilmali: dugme puntosu
                # kendi bandindan hesaplaniyor (`compose`ta band yuksekligine
                # oranli), merdiven ise METIN hiyerarsisi icin. Bu satir
                # yokken kapi yalnizca merdiven disi dugme OLMADIGI icin
                # geciyordu -- 2026-09-06'da taahhut slaydina 15pt'lik bir
                # "Devam" dugmesi eklenince kirmiziya dondu ve kusur
                # dugmede degil, kapinin kapsam varsayimindaydi.
                if _sh.tag in ("btn", "rsltBtn", "feedBackBtn"):
                    continue
                if not model._doc_text(_d).strip():
                    continue
                _cc, _sz, _bb, _aa = __import__(
                    "storyline_mcp.preview", fromlist=["x"])._text_style(_sh)
                if _sz and round(_sz) not in _c.TYPE_LADDER:
                    _disari.append((_ref.basename, round(_sz)))
    bak("punto merdiveni", "#17", not _disari,
        "%d merdiven disi yazi" % len(_disari))

    # 15 -- katmanlarda tasma (yeni fikstuurun actigi sinif)
    import inventory as _inv
    _o = _inv.audit(pkg)
    bak("tasma", "#12", _o["tasma"] == 0,
        "%d tasan yazi (oran %.2f)" % (_o["tasma"], _o["tasma_orani"]))

    # 16 -- ekrandaki %degisken% referanslari cozuluyor mu
    import re as _re2, zipfile as _zip
    _ham = "".join(pkg.read(_a).decode("utf-8", "replace")
                   for _a in list(pkg._order) if _a.endswith(".xml"))
    _ref = set(_re2.findall(r"%([A-Za-z_][A-Za-z0-9_.]{2,40})%", _ham))
    _adlar2 = {v["name"] for v in model.variables(pkg)}
    _kirik = sorted(_ref - _adlar2)
    bak("degisken referanslari", "#3b", not _kirik,
        "%d cozulmeyen %s" % (len(_kirik), _kirik[:2] or ""))

    # 17 -- yanlis cevap katmanlari birbirinden ayri mi
    _ayni = []
    for _part, _ref in model.slide_index(pkg).items():
        _root = pkg.parse(_part)
        _kl = list(_root.find("sldLayerLst") or [])
        if len(_kl) < 3:
            continue
        _metinler = []
        for _k in _kl:
            _t = [model._doc_text(_d).strip()
                  for _s2, _e2, _d, _st in model._iter_text_shapes(_k)
                  if model._doc_text(_d).strip()]
            if _t:
                _metinler.append(_t[0])
        if len(set(_metinler)) < len(_metinler):
            _ayni.append(_ref.basename)
    bak("katman metni ayri", "#9", not _ayni,
        "%d slaytta ayni metin" % len(_ayni))

    # 18 -- katman degisince dugme ziplamiyor mu
    from storyline_mcp import shapes as _sh2
    _ziplayan = []
    for _part, _ref in model.slide_index(pkg).items():
        _root = pkg.parse(_part)
        _kl = list(_root.find("sldLayerLst") or [])
        if len(_kl) < 2:
            continue
        _kon = {}
        for _k in _kl:
            _sl = _k.find("shapeLst")
            _d = [_x for _x in (list(_sl) if _sl is not None else [])
                  if _x.tag in ("btn", "rsltBtn", "feedBackBtn")]
            if len(_d) != 1:
                continue          # cok dugmeli katman ayri duzen
            _r = _sh2.shape_rect(_d[0])
            if _r:
                _kon.setdefault((round(_r[2] - _r[0]), round(_r[3] - _r[1])),
                                set()).add((round(_r[0]), round(_r[1])))
        for _boyut, _yerler in _kon.items():
            if len(_yerler) > 1:
                _ziplayan.append((_ref.basename, sorted(_yerler)))
    bak("dugme ziplamiyor", "#10", not _ziplayan,
        "%d slaytta ayni boyutta dugme farkli yerde" % len(_ziplayan))

    # 19 -- QUIZ'I OLMAYAN kaynaktan da zincir kuruluyor mu
    #
    # Yukaridaki fikstuur `bos.story`den basliyor ve onun quiz'i VAR, yani
    # "quiz yoksa kur" yolunu hic gezmiyor. Kullanicinin kendi baslangic
    # dosyasinda quiz YOKTU ve dort sorunun dordu de kayitsiz kaldi (K33:
    # kapi, fikstuurunun gezmedigi yoldaki kusuru goremez).
    import shutil as _sh3
    _yol2 = Path(tempfile.gettempdir()) / "yeni_modul_quizsiz.story"
    _sh3.copy2(BLANK, _yol2)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _p2 = StoryPackage(_yol2)
        _st = _p2.parse(model.STORY_PART)
        for _eb in _st.iter():
            for _c in list(_eb):
                if _c.tag == "quiz":
                    _eb.remove(_c)
        _p2.replace_xml(model.STORY_PART, _st)
        _p2.save(_yol2, backup=False)
        _p2 = StoryPackage(_yol2)
        authoring.add_question(_p2, None, "Soru?", ["A", "B", "C"], [0])
        authoring.add_results_slide(_p2)
        _p2.save(_yol2, backup=False)
        _s3 = completeness.survey(StoryPackage(_yol2))
    _iz3 = _s3["izleme"]
    _tamam = (not _s3["kayitsiz"] and _iz3["quizzes"]
              and _iz3["quizzes"][0]["sonuc_slaydi"] and not _iz3["lms_bos"])
    bak("quizsiz kaynak", "#3c", bool(_tamam),
        "kayitsiz=%d quiz=%s" % (len(_s3["kayitsiz"]),
                                 [(q["name"], q["kayit"]) for q in _iz3["quizzes"]]))

    # 20 -- her yol GONDERIDEN geciyor mu
    _gondersiz = []
    for _part, _ref in model.slide_index(pkg).items():
        _root = pkg.parse(_part)
        _sik = compose.katman_sik_etiketleri(_root)
        if len(_sik) < 2:
            continue                      # dallanma sorusu degil
        _roller = compose.geri_bildirim_rolleri(_root)
        _dogru = next((_g for _g in _sik if _roller.get(_g) is True), None)
        if _dogru is None:
            continue
        _kat = next((_k for _k in (_root.find("sldLayerLst") or [])
                     if _k.get("g") == _dogru), None)
        _sira = [_t.find("data").get("action")
                 for _tl in (_kat.iter("trigLst") if _kat is not None else [])
                 for _t in _tl if _t.find("data") is not None]
        # gonder ILERLEMEDEN once gelmeli
        if "submitInteraction" not in _sira:
            _gondersiz.append((_ref.basename, "gonder yok"))
        elif _sira.index("submitInteraction") > min(
                [_sira.index(_a) for _a in ("jumpToSlide", "jumpToScene")
                 if _a in _sira] or [99]):
            _gondersiz.append((_ref.basename, "gonder ilerlemeden SONRA"))
    bak("gonderiden geciyor", "#4", not _gondersiz,
        "%d slaytta gonder yolu kirik %s" % (len(_gondersiz), _gondersiz[:1]))

    # 21 -- menude gorunen sahne adlari teknik mi
    import re as _re4
    _teknik = []
    for _part, _ref in model.slide_index(pkg).items():
        _ad = _ref.scene_name or ""
        # "01_YZ_Nedir" kalibi: basta numara ve/veya alt cizgi
        if _re4.match(r"^\d+[_-]", _ad) or "_" in _ad:
            if _ad not in _teknik:
                _teknik.append(_ad)
    bak("sahne adi okunur", "#8", not _teknik,
        "%d teknik ad %s" % (len(_teknik), _teknik[:2]))

    # 22 -- son slaytta olu ILERI kalmasin
    _idx = list(model.slide_index(pkg).items())
    _spart, _sref = _idx[-1]
    _sroot = pkg.parse(_spart)
    _nav = next(_sroot.iter("navData"), None)
    _olu = [1 for _tl in _sroot.iter("trigLst") for _t in _tl
            if _t.find("data") is not None
            and _t.find("data").get("event") == "OnNextButtonClick"
            and _t.find("data").get("actSubType") == "next"]
    _kapali = (_nav is not None and _nav.get("next") == "false" and not _olu)
    bak("son slayt ILERI", "#10", _kapali,
        "%s next=%s olu_tetikleyici=%d" % (_sref.basename,
        _nav.get("next") if _nav is not None else "?", len(_olu)))

    # 23 -- ZEMINLER kursun paletinden mi, ve UZERLERINDEKI YAZI okunuyor mu
    #
    # Yukaridaki fikstuur soru/sonuc cagrilarini PALETSIZ yapiyor, yani
    # boyamanin yolunu hic gezmiyor (K33). Panelin gercek yolu paleti
    # tasiyor; kapi da oradan gecmeli.
    #
    # UC KUSUR SINIFI, ucu de olculdu 2026-09-06:
    #
    # (a) Sonuc slaydinin zemini `gradOvrlyFill schemeClr accent1 tint 66%`
    #     (~#8BACD3) kaliyordu; boyayan onu okuyamayip `palette["bg"]`ye
    #     dusuyor ve yaziyi KOYU zemine gore seciyordu. Alti temanin
    #     dordunde 2.10-2.35.
    # (b) Tek secimli soru slaydinin geri bildirim katmanlari donorun
    #     #5A5794 morunu tasiyordu; katman zemini slaydin TAMAMINI kapladigi
    #     icin lacivert kursun uzerine mor bir yikama iniyordu.
    # (c) Sonuc slaydinin Success/Failure katmanlari `schemeClr accent3/2`
    #     (yesil/kirmizi) -- BILEREK boyanmiyor, gecti/kaldi anlami tasiyor.
    #     Ama zemin schemeClr oldugu icin cozulemiyor, yazi yine temel
    #     slayda gore seciliyordu: gece "Tebrikler" 2.18, kagit "Maalesef"
    #     3.60.
    #
    # KAPI KODUN KENDI COZUCULERINI CAGIRIR (`authoring.yazi_arkalari`).
    # Iki onceki surumu kendi kopyasini yazmisti ve IKI KEZ yanildi: once
    # `schemeClr` zeminleri cozemedigi icin (c)'yi goremedi, sonra
    # `_iter_text_shapes`in IC sekli verdigini unuttugu icin buton
    # etiketlerini yanlis zemine gore olctu ve olmayan kirk sorun bildirdi.
    # Kapinin kendi kopyasi varsa, kapi kusuru degil kendi varsayimini olcer.
    from panel import ilerleme as _ilerleme
    from storyline_mcp import settings as _settings, shapes as _shapes
    from storyline_mcp.compose import _contrast as _kontrast
    import shutil as _sh4

    def _rgb(v):
        h = _shapes.parse_color(v)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    _bulgu = []
    # IKI TEMA, biri koyu biri acik: kusurlarin cogu temadan bagimsiz (donor
    # rengi de sema rengi de temayla degismiyor), ama duzeltmenin yazi
    # rengini iki yone de cevirebildigi ancak iki kutupla gorulur.
    for _tema in ("gece", "kagit"):
        _palet = compose.theme_palette(_tema)
        _yol4 = Path(tempfile.gettempdir()) / ("yeni_modul_%s.story" % _tema)
        _sh4.copy2(BLANK, _yol4)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _p4 = StoryPackage(_yol4)
            _sab = list(model.slide_index(_p4).values())[0].basename
            clone.create_scene(_p4, "Bolum Bir")
            _r4 = authoring.add_slide(_p4, _sab, scene="Bolum Bir")
            compose.compose_slide(_p4, _r4["new_slide"], "content",
                                  title="Baslik", eyebrow="Baslik",
                                  body="Govde metni.", palette=_palet)
            authoring.add_question(_p4, None, "Hangisi dogru?",
                                   ["A secenegi", "B secenegi", "C secenegi"],
                                   [0], palette=_palet, eyebrow="Bolum Bir")
            authoring.add_question(_p4, None, "Hangileri dogru?",
                                   ["A", "B", "C", "D", "E"], [0, 1],
                                   palette=_palet, eyebrow="Bolum Bir")
            authoring.add_drag_question(
                _p4, "Surukle.", {"Kutu bir": ["Kisa", "Kisa"],
                                  "Kutu iki": ["Kisa", "Kisa"]}, palette=_palet)
            authoring.add_text_question(_p4, "Bir adim yaz.", None,
                                        palette=_palet)
            _ilerleme.kur(_p4, ["Bolum Bir"], palette=_palet)
            _p4.save(_yol4, backup=False)

        _p4 = StoryPackage(_yol4)
        _yuva = _settings.slot_colors(_p4)
        for _part4, _ref4 in model.slide_index(_p4).items():
            _k4 = _p4.parse(_part4)
            # (a)+(b): DUZ HEX bir zemin paletin disindaysa donor artigi.
            # schemeClr zeminler muaf -- temaya bagli ya da anlam tasiyor.
            for _ad4, _gv in model.bodies(_k4):
                _bgel = _gv.find("bg")
                if _bgel is None \
                        or _bgel.find("solidFill/clr/srgbClr") is None:
                    continue
                _z = authoring.kap_zemini(_gv, _yuva)
                if _z and _z.upper() != _palet["bg"].upper():
                    _bulgu.append("%s/%s/%s: zemin %s (palet %s)"
                                  % (_tema, _ref4.basename, _ad4 or "temel",
                                     _z, _palet["bg"]))
            # (a): SONUC SLAYDININ temel zemini paletten mi.
            #
            # Ayri bir kontrol, cunku yukaridaki dongu onu GOREMEZ: tohumun
            # zemini `gradOvrlyFill` ve `solidFill/clr/srgbClr` aramasina
            # takilmaz. `kap_zemini` de onu cozemez (gradyan) -- yani
            # "cozulemedi" ile "dogru" ayni gorunur. Sonuc slaydinin zemini
            # BOYANMIS olmali; cozulememesi tek basina bir bulgu.
            if any(_e.tag == "rsltsIntr" for _e in _k4.iter()):
                _zs = authoring.kap_zemini(_k4, _yuva)
                if (_zs or "").upper() != _palet["bg"].upper():
                    _bulgu.append("%s/%s: sonuc slaydinin zemini %s (palet %s)"
                                  % (_tema, _ref4.basename, _zs, _palet["bg"]))

            # (c): zemin ne olursa olsun uzerindeki yazi okunmali.
            for _kap4, _shp4, _el4, _arka in authoring.yazi_arkalari(
                    _k4, _yuva, _palet["bg"]):
                if not (_el4.text or "").strip():
                    continue
                if not _arka:
                    # Sahibi cozulemeyen yazi: boyayan onu ATLIYOR, yani
                    # donorun renginde kaliyor. Olculemeyen bir yazi
                    # "sorunsuz" degildir.
                    _bulgu.append("%s/%s/%s: yazinin sahibi cozulemedi"
                                  % (_tema, _ref4.basename, _kap4 or "temel"))
                    continue
                _col = preview._text_style(_shp4)[0]
                if not (_col or "").startswith("#"):
                    continue
                _o = _kontrast(_rgb(_col), _rgb(_arka))
                if _o < 4.5:
                    _bulgu.append("%s/%s/%s: %s uzerine %s = %.2f"
                                  % (_tema, _ref4.basename, _kap4 or "temel",
                                     _arka, _col, _o))
    bak("zemin ve okunurluk", "#3/#5", not _bulgu,
        "%d sorun %s" % (len(_bulgu), _bulgu[:1]))

    # 24 -- PAYLASILAN COZUCULERIN KENDISI
    #
    # Yukaridaki kapi kodun cozuculerini cagiriyor ve bu DOGRU -- kendi
    # kopyasini yazdiginda iki kez yanildi. Ama paylasmanin bir bedeli var:
    # cozucunun KENDISI bozulursa kapi da ayni koru olur ve sessizce yesil
    # kalir. Olculdu 2026-09-06: `kap_zemini`nin sema dali devre disi
    # birakildiginda boru hatti kapisi hicbir sey gormedi.
    #
    # O yuzden ikinci bir kat: cozuculer BIRIM olarak, boru hattindan
    # bagimsiz sinaniyor. Uc dal da ayri ayri, cunku ucunun de bir kusur
    # gecmisi var:
    #   duz hex      -- donorun kendi rengi
    #   schemeClr    -- yesil/kirmizi anlam katmanlari (cozulmuyordu)
    #   cozulemez    -- gradyan; None DONMELI, uydurma bir renk degil
    # ve `yazi_rengi_sec` zor bir zeminde (#C0504D) esigi gecmeli.
    import xml.etree.ElementTree as _ET
    _kanarya = []

    def _kap(xml: str):
        return _ET.fromstring(xml)

    _duz = _kap('<sldLayer><bg><solidFill><clr><srgbClr val="5A5794"/>'
                '</clr></solidFill></bg></sldLayer>')
    if authoring.kap_zemini(_duz, {}) != "#5A5794":
        _kanarya.append("duz hex zemin cozulmuyor: %r"
                        % authoring.kap_zemini(_duz, {}))
    _sema = _kap('<sldLayer><bg><solidFill><clr><schemeClr val="accent3"/>'
                 '</clr></solidFill></bg></sldLayer>')
    if authoring.kap_zemini(_sema, {"accent3": "#9BBB59"}) != "#9BBB59":
        _kanarya.append("sema zemin cozulmuyor: %r"
                        % authoring.kap_zemini(_sema, {"accent3": "#9BBB59"}))
    _grad = _kap('<sldLayer><bg><gradOvrlyFill type="def"/></bg></sldLayer>')
    if authoring.kap_zemini(_grad, {}) is not None:
        _kanarya.append("cozulemeyen zemin None donmuyor")
    # `compose.kucuk` DE PAYLASILAN BIR COZUCU: 26. sinif etiket eslemesini
    # ona yaptiriyor. Bozulursa esleme sessizce bosa duser ve kapi yesil
    # kalir -- `kap_zemini`de tam olarak boyle olmustu.
    for _ham, _bek in (("IŞIK", "ışık"), ("İLKE", "ilke"),
                       ("Cevapları Göster", "cevapları göster")):
        if compose.kucuk(_ham) != _bek:
            _kanarya.append("kucuk(%r) = %r, beklenen %r"
                            % (_ham, compose.kucuk(_ham), _bek))
    for _zor in ("#C0504D", "#9BBB59"):
        _sec = authoring.yazi_rengi_sec(compose.theme_palette("orman"), _zor)
        _o = _kontrast(_rgb(_sec), _rgb(_zor))
        if _o < 4.5:
            _kanarya.append("%s icin secilen %s = %.2f" % (_zor, _sec, _o))
    bak("cozucu kanaryasi", "#3/#5", not _kanarya,
        "%d sorun %s" % (len(_kanarya), _kanarya[:1]))

    # 25 -- SORU VARYANTLARINDA OLU BANT
    #
    # `sag` varyanti metni %35'ten baslatiyordu ve sol bantta yalnizca zemin
    # vardi: 35 x 94.5, yani slaydin UCTE BIRI, hem de kursun en yogun slayt
    # tipinde. Diger uc varyantin bos bandi %8 -- o bir kenar bosluğu; bu bir
    # delikti. Kullanicinin sozuyle "eksik yarisi olan bir karar".
    #
    # DORT VARYANT DA ACIKCA KURULUYOR, hash'in secmesi beklenmiyor: varyant
    # kok metninden turetiliyor ve bu fikstuurun kokU her kosuda ayni sonucu
    # verir -- yani uc varyant hic gezilmezdi (K33).
    #
    # KURAL: metin sutunundan genis bir bant bos kaliyorsa (kenar
    # bosluğundan buyuk), orada TAM BOY bir sekil olmali. Tam kapli zemin ve
    # etkilesim ogesi sayilmaz -- ikisi de her slaytta var ve hicbir seyi
    # doldurmuyor; vurgu isareti de sayilmaz, cunku `Kose` sol ustte
    # %5.5 yukseklikte duruyor ve altindaki bosluğu kapatmiyor.
    _KENAR = 10.0                      # 8 kenar bosluğu + olcum payi
    _olu = []
    for _v, _spec in sorted(compose.QUESTION_VARIANTS.items()):
        _yol5 = Path(tempfile.gettempdir()) / ("varyant_%s.story" % _v)
        shutil.copy2(BLANK, _yol5)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _p5 = StoryPackage(_yol5)
            clone.create_scene(_p5, "Bolum Bir")
            _r5 = authoring.add_question(
                _p5, None, "Tersanelerin yogunlastigi bolge hangisidir?",
                ["Icmeler", "Orhanli", "Aydinli", "Tersaneler"], [3],
                palette=compose.theme_palette("gece"), eyebrow="Bolum Bir",
                variant=_v)
            _p5.save(_yol5, backup=False)
        _p5 = StoryPackage(_yol5)
        _k5 = _p5.parse(_p5.slide_part_for(_r5["new_slide"]))
        _w5, _h5 = shapes.slide_size(_k5)
        _sol = min(_spec["stem"][0], _spec["choices"][0])
        _sag = max(_spec["stem"][0] + _spec["stem"][1],
                   _spec["choices"][0] + _spec["choices"][1])

        def _dolduran(bant_x0, bant_x1):
            """Bandi kapatan tam boy bir sekil var mi."""
            _genis = bant_x1 - bant_x0
            for _sh in list(_k5.find("shapeLst") or []):
                if _sh.tag.endswith("Intr"):
                    continue
                _r = shapes.shape_rect(_sh)
                if not _r:
                    continue
                _x0, _y0, _x1, _y1 = (_r[0] / _w5 * 100, _r[1] / _h5 * 100,
                                      _r[2] / _w5 * 100, _r[3] / _h5 * 100)
                if _x1 - _x0 >= 99.0:
                    continue                      # tam kapli zemin
                if _y1 - _y0 < 50.0:
                    continue                      # vurgu seridi degil, pano
                if _x0 <= bant_x0 + 1 and _x1 - _x0 >= _genis * 0.6:
                    return True
            return False

        # OLCUT SIMETRI, GENISLIK DEGIL.
        #
        # Ilk surumu "kenardan genis her bant dolmali" diyordu ve
        # `ortalanmis`i (18/18) da kirmizi yapti -- oysa iki yani esit olan
        # bir sutun genis kenarli, ORTALANMIS bir karardir; bakan onu
        # kasitli okur. Kusur genislikte degil DENGESIZLIKTE: `sag` bir yana
        # 35, obur yana 8 birakiyordu. Kullanicinin sozu de tam buydu --
        # "eksik YARISI olan bir karar".
        _bos = {"sol": _sol, "sag": 100.0 - _sag}
        _buyuk = max(_bos, key=_bos.get)
        _fark = _bos[_buyuk] - min(_bos.values())
        if _fark > _KENAR:
            _bant = (0.0, _sol) if _buyuk == "sol" else (_sag, 100.0)
            if not _dolduran(*_bant):
                _olu.append("%s: %s %.0f%% bos, karsisi %.0f%%"
                            % (_v, _buyuk, _bos[_buyuk], min(_bos.values())))
    bak("varyantta olu bant", "#6", not _olu,
        "%d varyant %s" % (len(_olu), _olu[:2]))

    # 26 -- DUGME ETIKETI YAPTIGI ISI DOGRU ANLATIYOR MU
    #
    # Olculdu 2026-09-06, taze modul (uretim yolu), surukle-birak slaydi:
    #
    #     katman  dugme "Cevaplari Goster"  ->  ['jumpToSlide']
    #
    # Etiket cevaplari gosterecegini soyluyor, tetikleyici slaydi terk
    # ediyor, ve o slaytta gosterilecek bir cevap katmani zaten YOK. Etiket
    # donorun kursundan geliyordu.
    #
    # Kural HER SLAYT tipinde taraniyor, yalnizca surukle-birakta degil:
    # ayni tohum ailesi soru slaytlarinda da kullaniliyor ve kusurun
    # gorunmedigi bir yol, kusurun olmadigi anlamina gelmez.
    _yalan = []
    for _part6, _ref6 in model.slide_index(pkg).items():
        _k6 = pkg.parse(_part6)
        for _kat6 in (_k6.find("sldLayerLst") or []):
            _eylem = {_t.find("data").get("action")
                      for _tl in _kat6.iter("trigLst") for _t in _tl
                      if _t.find("data") is not None}
            _sl6 = _kat6.find("shapeLst")
            for _d6 in (list(_sl6) if _sl6 is not None else []):
                if _d6.tag not in ("btn", "rsltBtn", "feedBackBtn"):
                    continue
                _m6 = (model.shape_text(_kat6, _d6.get("g") or "") or "").strip()
                if not _m6:
                    continue
                # SOZ VEREN etiket: "... Gor" / "... Goster"
                if not compose.kucuk(_m6).endswith(
                        ("gor", "gör", "goster", "göster")):
                    continue
                if "showSubSlide" not in _eylem:
                    _yalan.append("%s/%s: %r ama %s"
                                  % (_ref6.basename,
                                     (_kat6.get("name") or "-")[:12],
                                     _m6[:22], sorted(_eylem)))
    bak("dugme sozunu tutuyor", "#2", not _yalan,
        "%d yalan etiket %s" % (len(_yalan), _yalan[:1]))

    # 27 -- AYNI ISI YAPAN DUGMELER AYNI ADI TASIYOR MU
    #
    # Olculdu 2026-09-06, taze modul: ayni soru slaydinda
    #
    #     Cevap2  "Cevabi Gor"          -> DOGRU katmani
    #     Cevap3  "Dogru Cevabi Gor"    -> DOGRU katmani
    #
    # Iki dugme, ayni hedef, iki ayri isim. Kullanicinin 9 numarali bulgusu.
    # Sebep benim onceki duzeltmemdi: etiket dugme BASINA, o dugmenin kendi
    # kutusuna sigacak sekilde seciliyordu ve kutular farkli genislikteydi.
    #
    # KAPSAM: bir SIKKA bagli geri bildirim katmanlari. Onlarin dugmeleri
    # tanim geregi ayni isi yapiyor (yanlis katmanlar dogru katmani acar),
    # yani "ayni is" burada tahmin degil, `geri_bildirim_rolleri`nin verdigi
    # bir olgu. Sonuc slaydinin iki dugmesi ("Gozden Gecir" / "Yeniden Dene")
    # farkli isler yapiyor ve bu kurala girmiyor.
    _ayrik = []
    for _part7, _ref7 in model.slide_index(pkg).items():
        _k7 = pkg.parse(_part7)
        _sik7 = set(compose.katman_sik_etiketleri(_k7))
        if len(_sik7) < 2:
            continue
        _rol7 = compose.geri_bildirim_rolleri(_k7)
        _dogru7 = next((_g for _g in _sik7 if _rol7.get(_g) is True), None)
        if _dogru7 is None:
            continue
        _etiketler = {}
        for _kat7 in (_k7.find("sldLayerLst") or []):
            _g7 = _kat7.get("g")
            if _g7 not in _sik7 or _g7 == _dogru7:
                continue                    # yalnizca YANLIS katmanlar
            _sl7 = _kat7.find("shapeLst")
            _d7 = [x for x in (list(_sl7) if _sl7 is not None else [])
                   if x.tag in ("btn", "rsltBtn", "feedBackBtn")]
            if len(_d7) != 1:
                continue
            _t7 = (model.shape_text(_kat7, _d7[0].get("g") or "") or "").strip()
            if _t7:
                _etiketler[(_kat7.get("name") or "-")] = _t7
        if len(set(_etiketler.values())) > 1:
            _ayrik.append("%s: %s" % (_ref7.basename, _etiketler))
    bak("ayni is ayni ad", "#9", not _ayrik,
        "%d slaytta ayrisik etiket %s" % (len(_ayrik), _ayrik[:1]))

    # 28 -- KONU SAHNESI SAYIMI: son sahne kapanis SANILMASIN
    #
    # `_konu_araligi` konu sahnelerini KONUMDAN okuyordu ("ilk = giris,
    # son = kapanis") ve planin kapanisla bittigini hicbir sey dogrulamiyor:
    # prompt kapanis slaydindan soz ediyor ama SART kosmuyor.
    #
    # Olculdu 2026-09-06, iki plan, ayni kod:
    #
    #     [giris, T1, T2, kapanis]  ->  konu T1,T2   esik 2
    #     [giris, T1, T2]           ->  konu T1      esik 1, T2 IZLENMIYOR
    #
    # Bedeli sessiz ve buyuk: T2'nin tamamlama bayragi hic kurulmuyor ve
    # kilit esigi bire dusuyor -- ogrenci IKI bolumun BIRINI bitirince sonuc
    # ekrani aciliyor. "Butun konulari bitirmeden sinava giremezsin"
    # kuralinin tam tersi, ve dosya gecerli, kurs aciliyor.
    #
    # BIRIM OLARAK SINANIR, boru hattindan degil: kural bir PLAN kurali ve
    # beklentiler elle yaziliyor -- kapinin `_konu_araligi`yi yardimci diye
    # cagirip kendi varsayimini olcmesi boyle onleniyor.
    from panel import builder as _builder
    _S = [{"kind": "content"}, {"kind": "question"}]       # puanli sahne
    _O = [{"kind": "content"}, {"kind": "commitment"}]     # okuma sahnesi

    def _plan(*govdeler):
        return [{"name": "S%d" % i, "slides": g} for i, g in enumerate(govdeler)]

    _bekleme = [
        ("giris,T1,T2,kapanis", _plan(_O, _S, _S, _O), [1, 2]),
        ("giris,T1,T2  (kapanissiz)", _plan(_O, _S, _S), [1, 2]),
        ("giris,T1,kapanis", _plan(_O, _S, _O), [1]),
        ("giris,T1     (iki sahne)", _plan(_O, _S), [0, 1]),
    ]
    _sapan = []
    for _ad28, _plan28, _bek28 in _bekleme:
        _cikan = list(_builder._konu_araligi(_plan28))
        if _cikan != _bek28:
            _sapan.append("%s: %s (beklenen %s)" % (_ad28, _cikan, _bek28))
    bak("konu sahnesi sayimi", "#11", not _sapan,
        "%d sapma %s" % (len(_sapan), _sapan[:1]))

    # 29 -- BOLGE AYIRAN ICERIK VARYANTI, BOLGE BOSKEN DELIK BIRAKMASIN
    #
    # `sol-panel` metni %8-53.4'e daraltip sag %46.6'yi `panel`e ayirir;
    # `sag-metin` aynisini solda, `yan-gorsel` sag %48'i gorsele. O bolgeler
    # yalnizca IClerini dolduracak sey varken ciziliyor (`panel` -> kart ya
    # da gorsel, `gorsel` -> gorsel); ikisi de yoksa sutun ayrilir ve BOS
    # kalir. Kullanicinin urettigi tuzla.story slide6 tam bu durumdaydi.
    #
    # OLCUT SIMETRI DEGIL, BOLGENIN DOLULUGU. Yalnizca `panel`/`gorsel`
    # BEYAN EDEN varyantlar sinaniyor: `alt-baslik` (fark 24.0) ve
    # `genis-olcu` (15.1) de asimetrik ama hicbir sey ayirmiyorlar -- onlarin
    # darligi bir OKUMA OLCUSU, bos bir yuva degil. Hepsini simetriye
    # zorlamak tasarim dilini tek olcuye indirirdi.
    #
    # DUZELTME ELEME DEGIL GENISLETME, ve bu ikinci yol. Once bolge ayiran
    # varyantlar havuzdan cikarildi; secim yeniden dagildi ve `variety`
    # destesinde slide3 `alt-baslik`ten `ortalanmis`e kaydi -- orada govde
    # punto TABANINDA (13pt) bile sigmiyor (46 > 42) ve `invariants` hakli
    # olarak kirmiziya dondu. Eleme, deligin yerine tasma koyuyordu.
    _delik = []
    for _v29, _sp29 in sorted(compose.VARIANTS["content"].items()):
        if not (_sp29.get("panel") or _sp29.get("gorsel")):
            continue
        _yol29 = Path(tempfile.gettempdir()) / ("bolge_%s.story" % _v29)
        shutil.copy2(BLANK, _yol29)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _p29 = StoryPackage(_yol29)
            clone.create_scene(_p29, "B")
            _r29 = authoring.add_slide(
                _p29, list(model.slide_index(_p29).values())[0].basename,
                scene="B")
            compose.compose_slide(
                _p29, _r29["new_slide"], "content",
                title="Gerginlik masaya nasil geliyor", eyebrow="Bolum",
                body="Musteri gerildiginde sesin tonu degisir.",
                palette=compose.theme_palette("gece"),
                variant=_v29)               # GORSEL YOK, MADDE YOK
            _p29.save(_yol29, backup=False)
        _p29 = StoryPackage(_yol29)
        _k29 = _p29.parse(_p29.slide_part_for(_r29["new_slide"]))
        _w29, _h29 = shapes.slide_size(_k29)
        _sol29, _sag29 = 100.0, 0.0
        for _sh29 in list(_k29.find("shapeLst") or []):
            if (_sh29.get("name") or "") in ("Arka Plan", "Vurgu", "Kose",
                                             "Serit", "Blok")                     or _sh29.tag.endswith("Intr"):
                continue
            _rc29 = shapes.shape_rect(_sh29)
            if not _rc29:
                continue
            _x0, _x1 = _rc29[0] / _w29 * 100, _rc29[2] / _w29 * 100
            if _x1 - _x0 >= 99:
                continue
            _sol29, _sag29 = min(_sol29, _x0), max(_sag29, _x1)
        _fark29 = abs(_sol29 - (100.0 - _sag29))
        if _fark29 > 10.0:
            _delik.append("%s: %.1f->%.1f, fark %.1f"
                          % (_v29, _sol29, _sag29, _fark29))
        # IKI OLCU, cunku iki AYRI kusur var ve biri otekini gizliyor.
        #
        # Bolgeyi metne verirken sag kenari icerik marjina kirpmak gerekiyor:
        # `yan-gorsel`in gorsel sutunu slaydin ta kenarina (100) kadar gider
        # -- gorsel icin dogru, YAZI icin degil. Kirpma kaldirildiginda
        # denge olcusu bunu GOREMEZ, hatta iyilesmis gorur (8/0 -> fark 8,
        # esigin altinda). Olculdu 2026-09-06: kanarya sessiz kaldi.
        # Marj kendi basina bir kosul, dengenin turevi degil.
        elif min(_sol29, 100.0 - _sag29) < 7.0:
            _delik.append("%s: %.1f->%.1f, marj %.1f (en az 8 olmali)"
                          % (_v29, _sol29, _sag29, min(_sol29, 100.0 - _sag29)))
    bak("bos bolge deligi", "#14", not _delik,
        "%d varyant %s" % (len(_delik), _delik[:1]))

    # 30 -- PUANLAMA ZINCIRI BUTUN MU (TEK BIRLESIK IDDIA)
    #
    # Kullanicinin uc kursu ikili degil bir TAYF gosterdi (olculdu
    # 2026-09-07):
    #
    #     dosya             quizLst   rsltsIntr.quizG      lmsResultSlideG
    #     savunma           bos       a8f5b72b (yabanci)   00000000...
    #     etkiliyapayzeka   bos       a8f5b72b (yabanci)   slide10  OK
    #     tuzla             1 quiz    a8f5b72b (eslesiyor) slided   OK
    #
    # Ortadaki satir mesele: LMS hedefi YAZILMIS, quiz hic kurulmamis. Iki
    # adim, tek ortak iddia yok -- ve her adim tek basina "yapildi" gorunuyor.
    # `verified_ok` bunu goremiyor: o XML butunlugune bakiyor, dosya kusursuz
    # bicimli olup LMS'e hicbir sey raporlamayabiliyor.
    #
    # UCUNCU KIRIK KURUCU YOLDA CIKTI: `uretilmis.story`nin quiz'i
    # b577f71e, sonuc slaydinin `quizG`si a8f5b72b -- yani sonuc slaydi bir
    # HAYALETI gosteriyordu. Insan yapimi iki kursta (0_duz_kopya, tuzla)
    # ikisi HER ZAMAN eslesiyor, yani bu bir degismez.
    #
    # IKI YOLDA DA SINANIR. Medya bulgusunun bir ust katmandaki aynisi: bir
    # kontrol yalnizca `builder.build` icinde yasarsa, o kontrolu kosmayan
    # yoldan cikan dosyalari iskalar -- bozuk iki dosya tam olarak oyle
    # cikmisti.
    from storyline_mcp import puanlama as _puanlama
    _zincir_kirik = []
    for _etiket30, _paket30 in (("komut yolu", pkg),
                                ("quizsiz kaynak", StoryPackage(_yol2))):
        for _k30 in _puanlama.zincir(_paket30):
            _zincir_kirik.append("%s: %s" % (_etiket30, _k30))

    # SONUC SLAYDINDAN SONRA EKLENEN SORU da kayitli olmali: `etkiliyapayzeka`
    # kalibi. Geriye donuk kayit bir donem `if quiz_kurulumu["kuruldu"]`
    # kapisinin arkasindaydi -- quiz ZATEN varsa hic kosmuyordu ve bu
    # sessizdi.
    _yol30 = Path(tempfile.gettempdir()) / "zincir_sonradan.story"
    shutil.copy2(BLANK, _yol30)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _p30 = StoryPackage(_yol30)
        clone.create_scene(_p30, "B")
        authoring.add_question(_p30, None, "Soru bir?",
                               ["A secenegi", "B secenegi", "C secenegi"], [0])
        authoring.add_results_slide(_p30)
        authoring.add_question(_p30, None, "Soru iki?",
                               ["A secenegi", "B secenegi", "C secenegi"], [1])
        _p30.save(_yol30, backup=False)
    for _k30 in _puanlama.zincir(StoryPackage(_yol30)):
        _zincir_kirik.append("sonradan soru: %s" % _k30)

    # KOPYALANAN SORU DA KAYITLI OLMALI, ve geriye donuk kaydin KOSULSUZ
    # olmasinin gerekcesi tam olarak bu vaka. `clone_slide` bir soru slaydini
    # cogaltir ama `register_question` cagirmaz -- ajanin sohbet yolunda
    # yapacagi en dogal sey. Quiz ZATEN var oldugu icin eski
    # `if quiz_kurulumu["kuruldu"]` kapisi geriye donuk kaydi hic
    # kosturmuyordu.
    #
    # Olculdu 2026-09-07, ayni fikstur iki surumle:
    #     kosulsuz  -> geriye_donuk_kayit ['slide.xml','slide5.xml'], zincir TEMIZ
    #     kosullu   -> geriye_donuk_kayit [], "1 puanli slayt kayitli degil"
    _yol31 = Path(tempfile.gettempdir()) / "zincir_kopya.story"
    shutil.copy2(BLANK, _yol31)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _p31 = StoryPackage(_yol31)
        clone.create_scene(_p31, "B")
        _q31 = authoring.add_question(
            _p31, None, "Soru bir?",
            ["A secenegi", "B secenegi", "C secenegi"], [0])
        clone.clone_slide(_p31, _q31["new_slide"])
        authoring.add_results_slide(_p31)
        _p31.save(_yol31, backup=False)
    for _k30 in _puanlama.zincir(StoryPackage(_yol31)):
        _zincir_kirik.append("kopyalanan soru: %s" % _k30)

    bak("puanlama zinciri", "#3", not _zincir_kirik,
        "%d kirik %s" % (len(_zincir_kirik), _zincir_kirik[:1]))

    # 31 -- AYRILAN GORSEL ALANI GERCEKTEN BOS MU
    #
    # `compose_slide` disariya "gorsel buraya" diye bir alan bildiriyor
    # (`image_area`) ve cagiran dosyayi TAM oraya koyuyor. O alanin uzerinde
    # yazi varsa resim metnin ustune duser.
    #
    # Olculdu 2026-09-07, `yan-gorsel` + dort madde + gorsel alani:
    #
    #     ayrilan alan            x=54  w=46
    #     BOLUM / baslik / govde  x 8 -> 92
    #     iki kart                x 54 -> 90
    #
    # BES oge resmin alanindaydi. Sebep bir kacis kapagi: kartlar dar sutuna
    # sigmayinca metin tam genislige geri aciliyordu, ve o kapak ayrilmis
    # sutundan habersizdi. Kodun KENDI YORUMU dogru kurali yaziyordu
    # ("gorsel icin ayrilmis bir alan yokken genisletilir") ama kosul
    # yazilmamisti -- yorumla kod ayrismisti.
    _ustune = []
    for _v31 in ("yan-gorsel", None):
        _yol32 = Path(tempfile.gettempdir()) / ("alan_%s.story" % (_v31 or "auto"))
        shutil.copy2(BLANK, _yol32)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _p32 = StoryPackage(_yol32)
            clone.create_scene(_p32, "B")
            _r32 = authoring.add_slide(
                _p32, list(model.slide_index(_p32).values())[0].basename,
                scene="B")
            _laid32 = compose.compose_slide(
                _p32, _r32["new_slide"], "content",
                title="Oltalama isaretleri", eyebrow="Bolum",
                body="Her birini sirayla kontrol et.",
                bullets=["Gonderen adresini dogrula",
                         "Aciliyet dilinden supheelen",
                         "Baglantiyi tiklamadan once bak",
                         "Ekleri acmadan tara"],
                palette=compose.theme_palette("gece"),
                variant=_v31, image_area=True, image_style="bleed")
            _p32.save(_yol32, backup=False)
        _alan = _laid32.get("image_area")
        if not _alan:
            continue                     # alan ayrilmadiysa iddia da yok
        _p32 = StoryPackage(_yol32)
        _k32 = _p32.parse(_p32.slide_part_for(_r32["new_slide"]))
        _w32, _h32 = shapes.slide_size(_k32)
        _gx0, _gx1 = _alan["x"], _alan["x"] + _alan["w"]
        _gy0, _gy1 = _alan["y"], _alan["y"] + _alan["h"]
        for _sh32 in list(_k32.find("shapeLst") or []):
            _t32 = (model.shape_text(_k32, _sh32.get("g") or "") or "").strip()
            _rc32 = shapes.shape_rect(_sh32)
            if not _rc32 or not _t32:
                continue
            _x0 = _rc32[0] / _w32 * 100; _x1 = _rc32[2] / _w32 * 100
            _y0 = _rc32[1] / _h32 * 100; _y1 = _rc32[3] / _h32 * 100
            if (min(_x1, _gx1) - max(_x0, _gx0) > 0.5
                    and min(_y1, _gy1) - max(_y0, _gy0) > 0.5):
                _ustune.append("%s: %r alanin ustunde"
                               % (_v31 or "auto", _t32[:24]))
    bak("ayrilan alan bos", "#14", not _ustune,
        "%d yazi %s" % (len(_ustune), _ustune[:1]))

    # 8 -- Turkce buyuk harf
    buyuk = compose.buyuk("Pozisyon Alma ve Kayma")
    bak("Turkce buyuk harf", "#13", buyuk.startswith("POZİ"),
        repr(buyuk[:12]))

    print()
    if kirmizi:
        print("KIRMIZI: " + ", ".join(kirmizi))
        print("Bu siniflar 2026-09-06'da duzeltilmisti; biri geri gelmis.")
        return 1
    print("Yeni bir modul, duzeltilen otuz bir sinifin hicbirini tasimiyor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
