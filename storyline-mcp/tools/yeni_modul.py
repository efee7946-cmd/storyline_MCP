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

SINANAN YIRMI IKI SINIF, her biri kullanicinin denetimindeki bir maddeye bagli:

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
from storyline_mcp import authoring, compose, model
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
    _acik = 0
    for _part, _ref in model.slide_index(pkg).items():
        _root = pkg.parse(_part)
        _sl = _root.find("shapeLst")
        for _sh in (list(_sl) if _sl is not None else []):
            if _sh.tag.endswith("Intr") or _sh.tag in (
                    "btn", "rsltBtn", "feedBackBtn", "pic", "textEntry"):
                continue
            _g = _sh.get("g") or ""
            if not _g or model.shape_text(_root, _g).strip():
                continue
            if (_sh.get("acc") or "") == "true":
                _acik += 1
    bak("dekoratif sekil gizli", "#22", _acik == 0,
        "%d metinsiz sekil ekran okuyucuya acik" % _acik)

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

    # 8 -- Turkce buyuk harf
    buyuk = compose.buyuk("Pozisyon Alma ve Kayma")
    bak("Turkce buyuk harf", "#13", buyuk.startswith("POZİ"),
        repr(buyuk[:12]))

    print()
    if kirmizi:
        print("KIRMIZI: " + ", ".join(kirmizi))
        print("Bu siniflar 2026-09-06'da duzeltilmisti; biri geri gelmis.")
        return 1
    print("Yeni bir modul, duzeltilen yirmi iki sinifin hicbirini tasimiyor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
