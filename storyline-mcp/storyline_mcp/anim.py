"""Timeline and entrance/exit animation -- the slot the builder never filled.

OLCULDU (2026-09-04). Uretilen bir kurs, test/kosul_probu2.story, 56 slayt ve
360 sekil: DOLU animEffect sayisi 0, ve 360 seklin 360'inin zaman cizgisi
girdisi start="0". Yani uretilen her slaytta her nesne ayni anda, aninda
beliriyor. Taban paket (test/bos.story, 194 sekil) da ayni: kusur uretimde
degil, hic yazilmamis olmasinda -- kod tabaninda animEffect'e yazan ya da
sekil start'ini kuran tek bir satir yoktu.

Sozluk TAHMIN DEGIL, bagis havuzundan olculdu: 6 .story, 1527 animEffect
yuvasi, 74'u dolu. Gorulen fiiller ve kendilerine ozgu nitelikleri:

    fade      dir="none"
    fly       dir="l" | "r" | "t" | "b"
    wipe      dir="none" wd="r"          -- wd icin YALNIZCA "r" olculdu
    growTurn  dir="none"
    random    dir="none" rbDir="horz"

    dur       PT0.25S | PT0.5S | PT0.75S | PT1.25S
    easing    easingType="lin"   easingDir="none"   (havuzda 39 ornek)
              easingType="cubic" easingDir="out"    (havuzda  5 ornek)

HAREKET YOLU HAVUZDA VAR ve bu modul onu HENUZ YAZMIYOR. Ilk taramada
`shapePath` gorulup "geometri" diye elenmisti; degil. Hareket yolu, shapeLst
icinde AYRI BIR SEKIL olarak duruyor ve tasidigi sekli `shapeG` ile
gosteriyor -- animEffect'ten tamamen bagimsiz bir mekanizma:

    <shapePath typeName="Circle_01" shapeG="<tasinan seklin GUID'i>"
               aniDur="PT0.1S" shapeType="cir" reverse="false"
               autoReverse="false" relativeStart="false" orientShape="false"
               originLocked="false" easingDir="inOut" easingType="cubic">
      <tmCtxLst version="2"><txtTmCtx start="0" dur="1000" .../></tmCtxLst>
      <loc .../>   <- yolun slayttaki yeri

Ama KANIT DAR: 15 ornek, tek bagisin tek slaydindan (DragDrop_5_vFINAL1,
slide2), hepsi shapeType="cir" ve aniDur="PT0.1S". Cizgi, egri ve serbest
yolun nasil yazildigi olculmedi. Dairesel yol yazilabilir; "hareket yolu
destegi" demek olcumden buyuk bir iddia olurdu.

SLAYT GECISI OLCULMEDI: havuzda yalnizca <trans dur="PT0.5S"><none/></trans>
var, yani gercek bir gecis TIPI hic gecmiyor. Tahminle yazilmiyor. Prob
yolu: gecisi elle kurulmus bir dosyayi Storyline'da kaydet, taban pakete
karsi tools/paket_farki.py ile farkini al.

CIKIS ANIMASYONU DA OLCULMEDI, ve sebebi zamanlamada: havuzdaki 214 slayt
seklinin 214'u untilEnd="true" tasiyor, yani hicbiri zaman cizgisini erken
terk etmiyor. Cikis animasyonu ancak nesne zaman cizgisinden CIKINCA oynar;
untilEnd="true" bir nesneye cikis yazmak, hicbir zaman oynamayan bir efekt
yazmaktir -- dosya gecerli, Storyline aciyor, hicbir sey olmuyor. Oynamasi
icin gereken untilEnd="false" + sonlu dur bileseninin havuzda ornegi yok.
set_effect(exit=...) yazabilir ama hicbir kurgu kullanmiyor ve arac yuzeyi
sunmuyor; once o bilesenin probu gerekiyor.

UC OLCULEN KURAL, ucu de sessizce bozulabilecek cinsten:

1. start + dur = SLAYDIN ZAMAN CIZGISI UZUNLUGU, ve untilEnd="true".
   Accordion.story/slide.xml'de bes sekil: 750+31375, 1250+30875,
   1750+30375, 250+31875, 0+32125 -- hepsi 32125. Gec giren bir nesnenin
   suresi KISALIR; start'i kurup dur'u oldugu gibi birakmak nesneyi
   sonundan kirpar, ve dosya bu haliyle de tamamen gecerli gorunur.

2. Slayt duzeyindeki <tmCtxLst><tmCtx dur> zaman cizgisinin uzunlugu DEGIL.
   Ayni slaytta o deger 3000 iken icerik 32125'e gidiyor. Uzunluk,
   icindekilerin en uzagidir; slayt girdisine dokunmak gerekmez.

3. Seklin zaman girdisinin ETIKETI degisir: txtTmCtx (havuzda 1474 kez,
   sekil ve yazi), tmCtx (resim), vidTmCtx (video). Etiketi sabit sanan bir
   okuyucu resimleri atlar. vidTmCtx'e BURADAN yazilmaz -- video suresi
   media.py'nin isi ve oradaki not acik: kisa bir girdi filmi cumlenin
   ortasinda keser.

animEffect'i tek basina yazmak YETIYOR. Ayni slaytta animasyonlu ve
animasyonsuz iki textBox karsilastirildi: aralarindaki tek fark yazi
yerlesimi nitelikleri (autoFit, vertAlign, horzAlign, shdw, textDir,
margCalcType). Animasyona eslik etmesi gereken ikinci bir nitelik yok.

Yuva zaten yerinde: uretilen 360 seklin 360'i bos <animEffect /> tasiyor ve
360'inda da <loc> ile <hLink> arasinda duruyor.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from .package import StoryPackage, StoryError

# Fiil -> o fiile OZGU nitelikler. Ortak dortlu (dur, lvl, easingDir,
# easingType) her fiilde ayni ve effect_element icinde yaziliyor.
EFFECTS: dict[str, dict[str, str]] = {
    "fade": {"dir": "none"},
    "fly": {"dir": "b"},
    "wipe": {"dir": "none", "wd": "r"},
    "growTurn": {"dir": "none"},
    "random": {"dir": "none", "rbDir": "horz"},
}
# fly disinda yon OLCULMEDI: havuzda wipe'in wd'si hep "r", digerlerinin
# dir'i hep "none". Yon isteyen bir cagri yalnizca fly'da karsilanir.
DIRECTIONS = ("l", "r", "t", "b")
EASINGS = {"lin": ("lin", "none"), "cubic": ("cubic", "out")}

# Zaman girdisinin olculen etiketleri. vidTmCtx bilerek DISARIDA.
TIME_TAGS = ("txtTmCtx", "tmCtx", "picTmCtx")
VIDEO_TAG = "vidTmCtx"

# Son giren nesne ekranda en az bu kadar kalir. Kademelenme slaydin mevcut
# uzunlugunu asarsa uzunluk buyur; asmazsa slayt UZAMAZ, nesneler yalnizca
# daha gec girer.
MIN_TAIL_MS = 2000

# KATMAN ETIKETLERI IKI TANE, ve bu tek bir yerde yaziyor. Ilk surumde
# yalnizca `sldLayer` araniyordu ve geri bildirim pop-up'lari sessizce
# disarida kaliyordu: olculdu 2026-09-04, uretilen bir kursta sldLayerLst
# cocuklari 25 sldLayer (100 sekil) ve 10 feedBackLayer (28 sekil) --
# yani "katmanlar da kurgulandi" demek, sorularin dogru/yanlis ekranlari
# icin YANLIS olurdu.
#
# Ikisinin yapisi ayni (tmProps, tmCtxLst, sz, bg, shapeLst, trigLst,
# trans), o yuzden ayirt etmeye gerek yok -- yalnizca ikisini de bulmaya.
LAYER_TAGS = ("sldLayer", "feedBackLayer")

# Zemin animasyonlanmaz: slayt bos baslar ve arka plan "ucarak" gelirdi.
GROUND_NAMES = frozenset({"Arka Plan"})
# Etkilesim govdeleri de disarida. Bir sorunun animEffect yuvasi soru
# KAPSAYICISINDA; oraya yazmanin siklara ne yaptigi OLCULMEDI, ve yanlis
# animasyonlanan bir soru cevaplanamayan bir sorudur.
INTERACTION_TAGS = frozenset({
    "freePickOneIntr", "freePickManyIntr", "dragDropIntr", "textEntry",
    "freeTextEntryIntr", "freeHotSpotIntr", "rsltsIntr",
})


def _dur(seconds: float) -> str:
    """PT0.75S bicimi -- havuzda gorulen tam yazim."""
    return f"PT{seconds:g}S"


def effect_element(verb: str, *, seconds: float = 0.75, easing: str = "lin",
                   direction: str | None = None) -> ET.Element:
    """Tek bir efekt ogesi; nitelik SIRASI havuzdakiyle ayni."""
    if verb not in EFFECTS:
        raise StoryError(f"Bilinmeyen efekt: {verb!r}. Secenekler: "
                         f"{', '.join(sorted(EFFECTS))}")
    if easing not in EASINGS:
        raise StoryError(f"Bilinmeyen yumusatma: {easing!r}. Secenekler: "
                         f"{', '.join(sorted(EASINGS))}")
    kind, side = EASINGS[easing]
    attrs = {"dur": _dur(seconds), "lvl": "none",
             "easingDir": side, "easingType": kind}
    attrs.update(EFFECTS[verb])
    if direction is not None:
        if verb != "fly":
            # Sessizce yok saymak, yonu verdigini sanan bir cagrinin
            # sonucunu aciklanamaz hale getirir.
            raise StoryError(f"{verb} yon almiyor; yon yalnizca fly icin "
                             f"olculdu ({', '.join(DIRECTIONS)}).")
        if direction not in DIRECTIONS:
            raise StoryError(f"Bilinmeyen yon: {direction!r}. Secenekler: "
                             f"{', '.join(DIRECTIONS)}")
        attrs["dir"] = direction
    return ET.Element(verb, attrs)


def layers(root: ET.Element) -> list[tuple[str, ET.Element]]:
    """Slaydin katmanlari, ikisi de: (ad, govde).

    Tek giris noktasi. Her cagiran kendi aramasini yazsaydi biri
    feedBackLayer'i unuturdu -- ilk surumde tam olarak bu oldu.
    """
    out: list[tuple[str, ET.Element]] = []
    holder = root.find("sldLayerLst")
    if holder is None:
        return out
    for layer in holder:
        if layer.tag in LAYER_TAGS:
            out.append((layer.get("name", "") or layer.tag, layer))
    return out


def _anim_slot(shape: ET.Element) -> ET.Element:
    """Seklin animEffect yuvasi; yoksa <loc>'un ardina acilir.

    Yer onemli: uretilen 360 seklin 360'inda yuva loc ile hLink arasinda.
    Sona eklemek Storyline'in kendi yazicisinin urettigi sirayi bozar.
    """
    slot = shape.find("animEffect")
    if slot is not None:
        return slot
    slot = ET.Element("animEffect")
    for index, child in enumerate(list(shape)):
        if child.tag == "loc":
            shape.insert(index + 1, slot)
            return slot
    shape.append(slot)
    return slot


def set_effect(shape: ET.Element, *, entrance: str | None = None,
               exit: str | None = None, seconds: float = 0.75,
               easing: str = "lin", direction: str | None = None) -> None:
    """Seklin giris/cikis animasyonunu yazar. None verilen taraf SILINIR.

    Ikisi de None ise animasyon kaldirilir: yuva bos <animEffect /> olarak
    kalir -- tohumdaki hali.
    """
    slot = _anim_slot(shape)
    for child in list(slot):
        slot.remove(child)
    if entrance:
        node = ET.SubElement(slot, "entr")
        node.append(effect_element(entrance, seconds=seconds, easing=easing,
                                   direction=direction))
    if exit:
        node = ET.SubElement(slot, "exit")
        node.append(effect_element(exit, seconds=seconds, easing=easing,
                                   direction=direction))


def timeline_entry(shape: ET.Element) -> ET.Element | None:
    """Seklin zaman cizgisi girdisi -- etiketi ne olursa olsun.

    Video girdisi DONMEZ: suresi filmin kendi uzunlugu ve buradan yazilmaz.
    """
    holder = shape.find("tmCtxLst")
    if holder is None:
        return None
    for child in holder:
        if child.tag == VIDEO_TAG:
            return None
        if child.tag in TIME_TAGS or child.tag.endswith("TmCtx"):
            return child
    return None


def slide_length(root: ET.Element) -> int:
    """Slaydin zaman cizgisi uzunlugu: icindekilerin en uzagi.

    Slayt duzeyindeki <tmCtx dur> DEGIL -- o deger olculen bir slaytta 3000
    iken icerik 32125'e gidiyordu.
    """
    longest = 0
    for shape in root.findall("shapeLst/*"):
        holder = shape.find("tmCtxLst")
        if holder is None:
            continue
        for entry in holder:
            if entry.tag != "tmCtx" and not entry.tag.endswith("TmCtx"):
                continue
            try:
                reach = int(entry.get("start", "0")) + int(entry.get("dur", "0"))
            except ValueError:
                continue
            longest = max(longest, reach)
    return longest


def set_timing(shape: ET.Element, start_ms: int, *, length_ms: int) -> bool:
    """Sekli zaman cizgisine oturtur: start, ve sona kadar suren dur.

    start + dur = length_ms, cunku olculen kural bu. dur'u sabit birakip
    yalnizca start'i kaydirmak nesneyi sonundan kirpar, ve dosya yine
    gecerli gorunur.
    """
    entry = timeline_entry(shape)
    if entry is None:
        return False
    start = max(0, int(start_ms))
    entry.set("start", str(start))
    entry.set("dur", str(max(0, int(length_ms) - start)))
    entry.set("untilEnd", "true")
    return True


# ---------------------------------------------------------------- gruplama

def _cycle(names: list[str]) -> tuple[int, int, int] | None:
    """Tekrar eden desen: (baslangic, periyot, tekrar sayisi).

    Uretilen slaytlar kart ve adim yiginlarini TEKRAR EDEN AD DIZISI olarak
    birakiyor -- olculdu, slide2c.xml: Kart, Kenar, Body bes kez;
    slide31.xml: Numara, Lead, Body bes kez, onunde tek bir Title.

    Bunu gormeyen bir kademelenme her karti uc ayri vurusa boler: bes kart
    on bes vurus olur ve slayt bir kart destesi gibi degil, dokulen bir
    parca yigini gibi acilir. Grup, tek vurustur.
    """
    n = len(names)
    best: tuple[int, int, int, int] | None = None
    for period in range(2, n // 2 + 1):
        for start in range(0, n - 2 * period + 1):
            matched = 0
            while (start + period + matched < n
                   and names[start + period + matched] == names[start + matched]):
                matched += 1
            reps = 1 + matched // period
            if reps < 2:
                continue
            # PERIYOT EN AZ IKI FARKLI AD TASIMALI. Ayni adin tekrari bir
            # YIGIN, bir grup degil: bes ozdes "Kart", periyot 2 ile de
            # eslesiyordu ve [2,2,1] diye keyfi bolunuyordu -- ikisi birlikte,
            # ikisi birlikte, biri yalniz. Olculdu: bir geri bildirim
            # katmaninda alti "Text Box" boyle ikiserli gruplanmisti.
            #
            # Yapisal tekrar (Kart+Kenar+Body) korunur, cunku onun periyodu
            # farkli adlar tasir. Ozdes yigin ise tek tek girer -- bes kart
            # bes vurus.
            if len(set(names[start:start + period])) < 2:
                continue
            covered = period * reps
            # Uzun kapsama kazanir; esitlikte KISA periyot, cunku ayni diziyi
            # iki kat periyotla okumak da mumkun ve o okuma gruplari birlestirir.
            if best is None or covered > best[0] or (covered == best[0]
                                                     and period < best[2]):
                best = (covered, start, period, reps)
    if best is None:
        return None
    return best[1], best[2], best[3]


def beats(shapes: list[ET.Element]) -> list[list[ET.Element]]:
    """Sekilleri vuruslara boler; tekrar eden desen tek vurus sayilir."""
    names = [s.get("name", "") for s in shapes]
    found = _cycle(names)
    if found is None:
        return [[s] for s in shapes]
    start, period, reps = found
    out: list[list[ET.Element]] = [[s] for s in shapes[:start]]
    for index in range(reps):
        head = start + index * period
        out.append(shapes[head:head + period])
    out.extend([s] for s in shapes[start + period * reps:])
    return out


# ---------------------------------------------------------------- kurgular

# Adlar compose.py'nin verdikleri; uretilen bir kurstan SAYILARAK alindi,
# uydurulmadi (kosul_probu2.story, 56 slayt).
_DECOR = {"Vurgu", "Kose", "Serit", "Cizgi", "Kenar", "Ton", "Ortu",
          "Gorsel Alani", "Blok"}
_TEXT = {"Eyebrow", "Display", "Title", "Subtitle", "Lead", "Body",
         "Text Box", "Numeral"}


# Katman govdelerinin etiketleri. Slaytta hic gecmiyorlar, katmanlarda
# sayildi (kosul_probu2.story, 14 slaytta 128 sekil): feedbackTextBox 18,
# feedBackBtn 10, checkMark 3, rsltBtn 3, multiply 1, importedVector 2.
# Bunlar siniflandirilmasaydi hepsi "block" olurdu -- yani geri bildirim
# yazisi da onay isareti gibi kayarak girerdi.
_TEXT_TAGS = frozenset({"textBox", "feedbackTextBox"})
_BUTTON_TAGS = frozenset({"btn", "feedBackBtn", "rsltBtn"})


def _role(shape: ET.Element) -> str:
    name = shape.get("name", "")
    if name in _DECOR:
        return "decor"
    if name in _TEXT or shape.tag in _TEXT_TAGS:
        return "text"
    if shape.tag in _BUTTON_TAGS:
        return "button"
    if shape.tag == "pic":
        return "media"
    return "block"


PRESETS: dict[str, dict] = {
    # Her sey solar. En sessizi, ve bir kursun tamamina uygulanabilecek tek
    # kurgu: hicbir nesne yerinden oynamadigi icin yerlesim kararlarini
    # goruntuye tasimaz.
    "sakin": {
        "step": 180, "seconds": 0.5, "easing": "lin",
        "by_role": {"decor": ("fade", None), "text": ("fade", None),
                    "button": ("fade", None), "media": ("fade", None),
                    "block": ("fade", None)},
    },
    # Suslemeler silinerek, bloklar yerine kayarak girer. "Anlatim" kurgusu:
    # bakis yukaridan asagi tasinir, yazi kimildamaz.
    "anlatim": {
        "step": 240, "seconds": 0.75, "easing": "cubic",
        "by_role": {"decor": ("wipe", None), "text": ("fade", None),
                    "button": ("fade", None), "media": ("fade", None),
                    "block": ("fly", "b")},
    },
    # En hareketlisi: yazi da kayar. Yogun slaytta cok olur -- bu yuzden
    # ayri isim, varsayilan degil.
    "vurgulu": {
        "step": 260, "seconds": 0.75, "easing": "cubic",
        "by_role": {"decor": ("wipe", None), "text": ("fly", "b"),
                    "button": ("fade", None), "media": ("fly", "r"),
                    "block": ("fly", "l")},
    },
}


def _apply(host: ET.Element, plan: dict, *, step: int, start_ms: int,
           include_ground: bool, include_interactions: bool) -> dict:
    """Tek bir GOVDEYI kurgular: slayt kokU ya da bir katman.

    Ikisi ayni yapiya sahip -- olculdu: <sldLayer> cocuklari tmProps,
    tmCtxLst, sz, bg, shapeLst, trigLst, trans; yani katman kendi zaman
    cizgisi olan kucuk bir slayt. Bu yuzden tek bir govde islemi ikisine de
    yeter ve kurgu mantigi iki yerde yazilmaz.
    """
    holder = host.find("shapeLst")
    if holder is None:
        return {"animated": 0, "beats": 0, "length_ms": 0, "skipped": []}

    animatable: list[ET.Element] = []
    skipped: list[str] = []
    for shape in holder:
        name = shape.get("name", "")
        if not include_ground and name in GROUND_NAMES:
            skipped.append(name or shape.tag)
            continue
        if not include_interactions and shape.tag in INTERACTION_TAGS:
            skipped.append(shape.tag)
            continue
        if timeline_entry(shape) is None:
            # Video, ya da zaman girdisi hic olmayan bir govde.
            skipped.append(name or shape.tag)
            continue
        animatable.append(shape)

    groups = beats(animatable)
    last_start = start_ms + max(len(groups) - 1, 0) * step
    length = max(slide_length(host), last_start + MIN_TAIL_MS)

    animated = 0
    for index, group in enumerate(groups):
        at = start_ms + index * step
        for shape in group:
            verb, direction = plan["by_role"][_role(shape)]
            set_effect(shape, entrance=verb, seconds=plan["seconds"],
                       easing=plan["easing"], direction=direction)
            set_timing(shape, at, length_ms=length)
            animated += 1
    return {"animated": animated, "beats": len(groups), "length_ms": length,
            "skipped": skipped}


def choreograph(pkg: StoryPackage, slide: str, *, preset: str = "sakin",
                step_ms: int | None = None, start_ms: int = 0,
                include_ground: bool = False,
                include_interactions: bool = False,
                include_layers: bool = True) -> dict:
    """Bir slaydi ve KATMANLARINI zaman cizgisine dizer.

    Sekiller z-sirasinda okunur -- compose.py onlari yerlestirme sirasiyla
    ekliyor, yani z-sirasi okuma sirasidir. Tekrar eden desenler tek vurusa
    toplanir (bkz. beats).

    KATMANLAR SLAYTTAN AYRI KURGULANIR ve her biri kendi sifirindan baslar.
    Katman, gosterildigi anda acilir; slaydin zaman cizgisindeki yerine gore
    geciktirmek, ogrenci katmani ikinci saniyede actiginda onu bir saniye daha
    bos ekrana baktirirdi.

    Olculdu 2026-09-04: uretilen bir kursta 14 slaytta 128 sekil KATMANLARDA
    yasiyor ve ilk surumde hicbirine dokunulmuyordu -- geri bildirim ve
    reveal pop-up'lari, yani hareketin en cok ise yaradigi yer, hareketsizdi.
    Bagis havuzu bunun mesru oldugunu gosteriyor: donor katmanlarinda 32
    animasyonlu sekil ve 500/1000/2000 ms kademelenme var.
    """
    if preset not in PRESETS:
        raise StoryError(f"Bilinmeyen kurgu: {preset!r}. Secenekler: "
                         f"{', '.join(sorted(PRESETS))}")
    plan = PRESETS[preset]
    step = plan["step"] if step_ms is None else int(step_ms)

    part = pkg.slide_part_for(slide)
    root = pkg.parse(part)
    ortak = {"step": step, "include_ground": include_ground,
             "include_interactions": include_interactions}

    sonuc = _apply(root, plan, start_ms=start_ms, **ortak)

    katmanlar = []
    if include_layers:
        for adi, layer in layers(root):
            # Her katman KENDI sifirindan; slaydin start_ms'i tasinmaz.
            rapor = _apply(layer, plan, start_ms=0, **ortak)
            if rapor["animated"]:
                katmanlar.append({"layer": adi, "tag": layer.tag,
                                  **{k: rapor[k] for k in
                                     ("animated", "beats", "length_ms")}})

    pkg.replace_xml(part, root)
    return {
        "slide": slide,
        "preset": preset,
        "animated": sonuc["animated"] + sum(k["animated"] for k in katmanlar),
        "slide_animated": sonuc["animated"],
        "layer_animated": sum(k["animated"] for k in katmanlar),
        "beats": sonuc["beats"],
        "step_ms": step,
        "length_ms": sonuc["length_ms"],
        "skipped": sonuc["skipped"],
        "layers": katmanlar,
    }


def _clear_host(host: ET.Element) -> int:
    length = slide_length(host)
    count = 0
    for shape in host.findall("shapeLst/*"):
        slot = shape.find("animEffect")
        if slot is not None and len(slot):
            for child in list(slot):
                slot.remove(child)
            count += 1
        if timeline_entry(shape) is not None:
            set_timing(shape, 0, length_ms=length)
    return count


def clear(pkg: StoryPackage, slide: str) -> dict:
    """Slayttaki VE KATMANLARINDAKI animasyonu ve kademelenmeyi geri alir.

    Zamanlama, animasyondan AYRI geri alinir: yalnizca animEffect'i
    bosaltmak, gec baslayan nesneleri gec baslar halde birakir ve slayt
    "bozuk" gorunur -- animasyon yok ama yazi bir saniye sonra beliriyor.

    Katmanlar da temizlenir. Kurgu onlara da yaziyor; yalnizca slayt kokunu
    geri almak, geri bildirim pop-up'ini kademeli halde birakirdi ve "geri
    aldim" demek yanlis olurdu.
    """
    part = pkg.slide_part_for(slide)
    root = pkg.parse(part)
    count = _clear_host(root)
    for _adi, layer in layers(root):
        count += _clear_host(layer)
    pkg.replace_xml(part, root)
    return {"slide": slide, "cleared": count, "length_ms": slide_length(root)}


def describe(pkg: StoryPackage, slide: str,
             include_layers: bool = True) -> list[dict]:
    """Slaytta ne yazili -- olcum ve denetim icin, tahminsiz okuma.

    Katman sekilleri de doner, 'layer' alaninda katmanin adiyla. Yalnizca
    slayt kokune bakan bir okuma, katmanlari hareketsiz birakan bir kusuru
    goremezdi -- ilk surumde tam olarak bu oldu.
    """
    root = pkg.parse(pkg.slide_part_for(slide))
    out = []
    hosts = [(None, root)]
    if include_layers:
        hosts += layers(root)
    for layer_name, host in hosts:
        out.extend(_describe_host(host, layer_name))
    return out


def _describe_host(host: ET.Element, layer_name: str | None) -> list[dict]:
    out = []
    for shape in host.findall("shapeLst/*"):
        holder = shape.find("tmCtxLst")
        entry = holder[0] if holder is not None and len(holder) else None
        slot = shape.find("animEffect")
        record: dict = {
            "shape": shape.tag,
            "name": shape.get("name", ""),
            "layer": layer_name,
            "guid": shape.get("g", ""),
            "start_ms": int(entry.get("start", "0")) if entry is not None else None,
            "dur_ms": int(entry.get("dur", "0")) if entry is not None else None,
            "time_tag": entry.tag if entry is not None else None,
            "entrance": None,
            "exit": None,
        }
        if slot is not None:
            for side in slot:
                if len(side):
                    record["entrance" if side.tag == "entr" else "exit"] = {
                        "effect": side[0].tag,
                        "seconds": side[0].get("dur", ""),
                        "dir": side[0].get("dir", ""),
                        "easing": side[0].get("easingType", ""),
                    }
        out.append(record)
    return out
