"""Higher-level authoring built on the clone engine.

Cloning gives a structurally valid slide; these functions fill it with new
content. The template's arity is binding: a four-option question slide clones
into a four-option question, because adding or removing an answer means
creating shapes, states, triggers and scoring entries from nothing -- exactly
what cloning exists to avoid. list_templates() reports each candidate's choice
count so a caller can pick a template that already fits.
"""

from __future__ import annotations

import copy as _copy
import hashlib
import re
import xml.etree.ElementTree as ET

from . import clone, donors, model, shapes
from .clone import clone_slide, create_scene  # noqa: F401  (re-exported)
from .edits import set_shape_text
from .package import STORY_PART, StoryPackage, StoryError

# Seeds to try when a background rectangle is wanted, best first. Not every
# deck contains a plain <rect>; a filled text box covers the slide just as well.
BACKGROUND_SEEDS = ("rect", "roundRect", "textBox")


def _find_interaction(root: ET.Element):
    for tag in model.INTERACTION_TAGS:
        for intr in root.iter(tag):
            return tag, intr
    return None, None


def _choice_shape_guids(intr: ET.Element) -> list[str]:
    choices = intr.find("choices")
    return [c.get("shpG", "") for c in (list(choices) if choices is not None else [])]


# Suruklenen ogenin gittigi yer. `matchShpG` PICK ailesinde her zaman bos
# (olculdu: iki tohumda da 9/9 null), dragDrop'ta ise DOGRU CEVABIN TA KENDISI
# -- oge-kutu esleşmesi. O yuzden iki liste ayri okunur ve ikisi de korunur.
def _drop_target_guids(intr: ET.Element) -> list[str]:
    """Birakma hedefleri, ILK GORULME SIRASINDA ve tekrarsiz.

    Sira onemli: `set` kullanmak, sik sirasinda olculen kusurun (bkz.
    adapt_seeded_slide) kutu tarafindaki aynisi olurdu -- ayni kurs iki kez
    uretildiginde kutular farkli yerlere iner. Uyelik testi icin kume,
    SIRA icin liste.
    """
    choices = intr.find("choices")
    out: list[str] = []
    for c in (list(choices) if choices is not None else []):
        guid = c.get("matchShpG", "") or ""
        if guid and not guid.startswith("00000000") and guid not in out:
            out.append(guid)
    return out


def _drag_pairs(intr: ET.Element) -> list[tuple[str, str]]:
    """(suruklenen, hedef) ciftleri -- yazilan cevabin geri okunusu."""
    choices = intr.find("choices")
    return [(c.get("shpG", "") or "", c.get("matchShpG", "") or "")
            for c in (list(choices) if choices is not None else [])]


# The stem is identified in exactly one place, shared with the reader, so a
# question is always read back from the shape it was written into.
_stem_shape_guid = model.stem_shape_guid


# "SIKKI SEC" AILESI. `add_question`, `_pick_template` ve sablon katalogu
# YALNIZCA bunlari uretebilir; kutuphanedeki oteki tohumlar (surukle-birak,
# metin girisi) kendi yollarindan gecer.
#
# Filtre gerekli, cunku `question_seeds()` anahtari (tur, SAYI) ve tuketici
# bir donem yalnizca sayiya bakiyordu: kutuphaneye 9 ogeli bir surukle-birak
# tohumu girdigi anda, 9 sikli bir "hangisi" sorusu onu secer ve yazma yolu
# uyusmayan bir anatomiye carpardi. Sayiyla eslesmek TURU dogrulamaz.
PICK_KINDS = ("freePickOneIntr", "freePickManyIntr")


# ------------------------------------------------------------------ templates


def list_templates(pkg: StoryPackage) -> list[dict]:
    """Slides usable as clone sources, with the arity each one imposes."""
    out: list[dict] = []
    for part, ref in model.slide_index(pkg).items():
        root = pkg.parse(part)
        tag, intr = _find_interaction(root)
        entry = {
            "slide": ref.basename,
            "name": ref.name,
            "scene": ref.scene_name,
            "layout": ref.layout_type,
            "kind": "question" if intr is not None else "content",
            "text_shapes": len(list(model._iter_text_shapes(root))),
        }
        if intr is not None:
            entry["question_type"] = tag
            entry["choice_count"] = len(_choice_shape_guids(intr))
        out.append(entry)
    return out


# ------------------------------------------------------------------ authoring


def bundled_name(kind: str, count: int, look: int = 0) -> str:
    """Gömülü bir soru tohumunun adı. TEK üretici.

    Iki yerde ayri ayri yaziliyordu ve bicimleri ayristi: _pick_template
    "bundled:freePickOneIntr:2" uretiyordu, pick_template ise
    "bundled:freePickOneIntr_2" -- alt cizgiyle. Ikincisi add_question'a
    verildiginde `_, kind, count = template.split(":")` iki parca buluyor ve
    ValueError atiyor.

    Hicbir test yakalamadi cunku hepsi proje sablonu OLAN bir dosyayla
    kosuyordu; gomulu yol ancak bos bir projede devreye giriyor. Ad uretimi
    tek yerde durdugu surece ayrisamaz.
    """
    return f"bundled:{kind}:{count}" if look == 0 else f"bundled:{kind}:{count}:{look}"


def parse_bundled(template: str) -> tuple[str, int, int]:
    """bundled: adını çözer; çözemezse sebebini söyler.

    ÜÇ PARÇA DA GEÇERLİ. `bundled:<tur>:<secenek>` ilk görünüşü adresler ve
    dosyada, kayıtta, raporda yazılı olan eski adlar bozulmadan çözülür;
    dördüncü parça yalnızca ikinci ve sonraki görünüşlerde belirir. Ad
    üretimi tek yerde (`bundled_name`) durduğu sürece iki biçim ayrışamaz --
    bu fonksiyonun docstring'indeki eski uyarı hâlâ geçerli, yalnızca artık
    korunacak iki uzunluk var.
    """
    parts = template.split(":")
    if parts[0] != "bundled" or len(parts) not in (3, 4):
        raise StoryError(
            f"Gomulu sablon adi cozulemedi: {template!r}. Beklenen bicim "
            "'bundled:<tur>:<secenek>' ya da 'bundled:<tur>:<secenek>:<gorunus>'.")
    try:
        return parts[1], int(parts[2]), int(parts[3]) if len(parts) == 4 else 0
    except ValueError:
        raise StoryError(
            f"Gomulu sablon adinda sayi olmayan alan var: {template!r}")


def _pick_template(pkg: StoryPackage, count: int) -> str:
    """A question source with exactly this many choices, project first."""
    for option in available_question_shapes(pkg):
        if option["choices"] == count and option["source"] == "project":
            return option["slide"]
    for (kind, seed_count), looks in question_seeds().items():
        if kind in PICK_KINDS and seed_count == count and looks:
            return bundled_name(kind, count)
    have = sorted({o["choices"] for o in available_question_shapes(pkg)})
    raise StoryError(
        f"{count} secenekli soru uretilemiyor. Kullanilabilir secenek sayilari: {have}. "
        f"Sorularinizi bu sayilardan biriyle yazin."
    )


def _question_from_seed(
    pkg: StoryPackage, template: str, prompt: str, choices: list[str],
    correct: list[int], *, scene, name, points,
    eyebrow: str | None = None, palette: dict | None = None,
    feedback: dict | None = None, style: str | None = None,
    variant: str | None = None,
    avoid_variant: "list[str] | None" = None,
) -> dict:
    """Install a bundled question slide, then write the question into it."""
    kind, count, look = parse_bundled(template)
    seed = question_seed(kind, count, look)
    if seed is None:
        havuz = len(question_seeds().get((kind, count)) or [])
        raise StoryError(
            f"Gomulu soru sablonu yok: {template} "
            f"({kind}/{count} icin kutuphanede {havuz} gorunus var)")

    result = clone.install_slide(
        pkg, seed.read_text(encoding="utf-8"),
        scene=scene, name=name or prompt[:60],
    )
    _write_question(pkg, result["part"], prompt, choices, correct, points)
    adapted = adapt_seeded_slide(pkg, result["part"], eyebrow=eyebrow,
                                 palette=palette, feedback=feedback,
                                 style=style, variant=variant,
                                 avoid_variant=avoid_variant)
    # Klon yolundaki ayni kayit, tohum yolunda da. Iki yoldan yalnizca birine
    # baglamak, sablonun nereden geldigine gore bazen puanlanan bazen
    # puanlanmayan kurslar uretirdi.
    registration = register_question(
        pkg, pkg.parse(result["part"]).get("g", ""))
    return {**result, "question_type": kind, "prompt": prompt,
            "adapted": adapted, "registration": registration,
            # Cerceve burada kuruldu: cagiran ikinci bir yerlesim uygulamamali.
            "framed": bool(adapted.get("framed")),
            "choices": [{"text": t, "correct": i in set(correct)}
                        for i, t in enumerate(choices)]}


def _temizle_donor_katmanlari(root, proje_degiskenleri: set[str]):
    """Katmanlardan DONOR artiklarini siler: (silinen guid kumesi, rapor).

    Iki cagirani var ve ikisi de sart: tohum yolu (adapt_seeded_slide) ve
    KLON yolu (add_question, projede sablon varsa secilen yol). Ilk surum
    yalnizca tohum yolundaydi ve uretimde hicbir sey degismiyordu, cunku
    taban pakette sablon VAR ve klon yolu seciliyor.
    """
    silinen: set[str] = set()
    rapor: list[str] = []
    #
    # Yukaridaki 1. adim "anatomi disinda her sey gider" diyor ama yalnizca
    # slaydin kendi shapeLst'inde yuruyordu. Katmanlar hic temizlenmiyordu ve
    # tohumun hasat edildigi kursun icerigi oradan ogrenciye ULASIYORDU --
    # olculdu 2026-09-05, question_freePickOneIntr_3'un Cevap katmanlari:
    #
    #     group     (metinsiz rozet)         <- kullanicinin gordugu sey
    #     textBox   'Guvenlik Skoru'          <- donorun etiketi
    #     textBox   '%GuvenlikSkoru%'         <- BU PROJEDE OLMAYAN degisken
    #
    # Sonuncusu en kotusu: oynatici cozemedigi degisken adini oldugu gibi
    # yazar. Kullanici bunu "baska slayttan klonlanmis guvenlik skoru" diye
    # bildirdi ve teshis dogruydu.
    #
    # OLCUT DAR TUTULDU, cunku katmanda neyin anatomi oldugu slayttaki kadar
    # net degil: yalnizca (a) kod tabaninin katmanda HIC uretmedigi `group`
    # sekilleri ve (b) bu projede karsiligi olmayan %degisken% referansi
    # tasiyan metinler gider. Geri bildirim yazisi, butonu ve paneli
    # DOKUNULMADAN kalir -- onlari compose_feedback_layers yeniden yaziyor.
    for _kat_adi, katman in model.layers(root):
        kat_liste = katman.find("shapeLst")
        if kat_liste is None:
            continue
        # ROZET TEK SEKIL DEGIL, KUME. Olculdu (freePickOneIntr_3, Cevap1):
        #     group      %80..%97 x , %-0..%11 y
        #     roundRect  %80..%97   , %4..%11
        #     textBox    %80..%91   , %4..%-0     'Guvenlik Skoru'
        #     textBox    %81..%93   , %4..%10     '%GuvenlikSkoru%'
        # Dorduu de sag ust kosede, ayni kutunun icinde. Gercek geri bildirim
        # icerigi (anlatim metni %16..%66, buton %50..%73) tamamen ayri yerde.
        #
        # O yuzden olcut GEOMETRIK ve kendini sinirlar: silinen group'un
        # kutusunun icinde kalan komsulari da gider. Group yoksa hicbir sey
        # silinmez -- kural kendiliginden kapanir.
        rozet_kutulari = []
        for shape in list(kat_liste):
            g = shape.get("g") or ""
            neden = None
            if shape.tag == "group":
                neden = "donor rozeti (group)"
                kutu = _kutu(shape)
                if kutu:
                    rozet_kutulari.append(kutu)
            else:
                metin = model.shape_text(katman, g).strip() if g else ""
                bilinmeyen = [ad for ad in _DEGISKEN_REF.findall(metin)
                              if ad not in proje_degiskenleri]
                if bilinmeyen:
                    neden = f"cozulmeyen degisken referansi %{bilinmeyen[0]}%"
            if neden:
                rapor.append(f"katman {_kat_adi!r}: {shape.tag} -- {neden}")
                silinen |= guids_within(shape)
                kat_liste.remove(shape)

        for shape in list(kat_liste):
            kutu = _kutu(shape)
            if not kutu or not any(_icinde(kutu, r) for r in rozet_kutulari):
                continue
            metin = model.shape_text(katman, shape.get("g") or "").strip()
            rapor.append(f"katman {_kat_adi!r}: {shape.tag} -- rozet kumesi "
                           f"{metin[:20]!r}")
            silinen |= guids_within(shape)
            kat_liste.remove(shape)

    return silinen, rapor


def _kutu(shape: ET.Element) -> tuple[float, float, float, float] | None:
    """Seklin kutusu, KOSELERI SIRALANMIS halde.

    Siralama sart: tohumda b < t olan bir kutu olculdu ('Guvenlik Skoru'
    etiketi, t=40 b=-2). Ham degerlerle yapilan bir kapsama testi onu hic
    yakalamazdi.
    """
    loc = shape.find("loc")
    if loc is None:
        return None
    try:
        l, t, r, b = (float(loc.get(k, 0)) for k in ("l", "t", "r", "b"))
    except (TypeError, ValueError):
        return None
    return (min(l, r), min(t, b), max(l, r), max(t, b))


def _icinde(kucuk, buyuk, pay: float = 0.8) -> bool:
    """kucuk kutunun alaninin en az `pay` kadari buyuk kutunun icinde mi."""
    gx = max(0.0, min(kucuk[2], buyuk[2]) - max(kucuk[0], buyuk[0]))
    gy = max(0.0, min(kucuk[3], buyuk[3]) - max(kucuk[1], buyuk[1]))
    alan = (kucuk[2] - kucuk[0]) * (kucuk[3] - kucuk[1])
    if alan <= 0:
        # Yukseklikisiz/genisliksiz sekil: yalnizca kesisim varsa say.
        return gx > 0 and gy >= 0
    return (gx * gy) / alan >= pay


def guids_within(shape: ET.Element) -> set[str]:
    """Bir seklin ve BUTUN torunlarinin guid'leri.

    Torunlar sart: silinen bir grubun cocuguna bakan tetikleyici, grubun
    kendi guid'ini hic gecirmez.
    """
    return {e.get("g") for e in shape.iter() if e.get("g")}


def _drop_dangling_triggers(pkg: StoryPackage, root: ET.Element,
                            silinen: set[str]) -> int:
    """BIZIM SILDIGIMIZ bir sekli isaret eden tetikleyicileri siler.

    OLCUT DEGISTI (2026-09-05) ve gerekcesi olculdu. Onceki surum sunu
    soruyordu: "bu tetikleyicideki her guid pakette cozuluyor mu?" Cozulmeyen
    bir tanesi bile varsa tetikleyici siliniyordu.

    O oncul YANLIS. Bagis havuzundaki -- yani Storyline'in KENDI yazdigi ve
    sorunsuz acilan -- dosyalarda tetikleyici nitelikleri paketin tamamina
    karsi olculdu:

        showG        56 cozulur /  80 COZULMEZ   (%59)
        actionG      14 cozulur /  14 COZULMEZ   (%50)
        varG2        72 cozulur /  32 COZULMEZ   (%31)
        moveG        19 cozulur /   5 COZULMEZ   (%21)
        shapeG       90 cozulur /  22 COZULMEZ   (%20)

    Yani cozulmeyen guid, calisan Storyline dosyalarinda OLAGAN. Onu yetimlik
    kaniti saymak, saglam tetikleyicileri sildiriyordu.

    BEDELI OLCULDU. Dokuz soru tohumunun dokuzunda `submitInteraction`
    tetikleyicisi, tohumun ICINDE BILE hicbir seye cozulmeyen tek bir
    `actionG` tasiyor (`ded656e9-...`, tum tohumda bir kez gecer, hasat
    edildigi kurstan kalma olu bir kimlik). Supurge her seferinde GONDER
    tetikleyicisini siliyordu -- yani uretilen her kursta, her soru tipinde,
    ogrenci cevabini gonderemiyordu. Dosya gecerli, kontroller sessiz.

    Dogru soru "cozuluyor mu" degil, "BIZ mi sildik". Cagiran ne sildigini
    zaten biliyor; `silinen` o kumedir (bkz. guids_within). Boylece:

      * silinen bir sekle bakan tetikleyici gider     -- supurgenin asil isi
      * katman goster/gizle kalir                     -- katmani silmiyoruz
      * degiskene yazan tetikleyici kalir             -- degiskeni silmiyoruz
      * olu bir `actionG` artik kimseyi sildirmez

    Ilk surumun belge dizesindeki iki olculmus kusur (katman tetikleyicisi ve
    metin girisi baglantisi) bu olcutle KENDILIGINDEN gecer: ikisi de
    silinmemis seyleri isaret ediyordu.

    Iki cagirani var (tohum uyarlama ve metin slaydi) ve `silinen` ZORUNLU
    parametre: varsayilani bos kume yapmak, cagiranin unutmasi halinde
    supurgeyi sessizce etkisiz birakirdi.
    """
    hedef = {g for g in silinen if g and not g.startswith("00000000")}
    if not hedef:
        return 0
    dangling = 0
    for owner in [root] + list(root.iter()):
        trig_list = owner.find("trigLst")
        if trig_list is None:
            continue
        for trig in list(trig_list):
            raw = ET.tostring(trig, encoding="unicode")
            refs = {g for g in _GUID_RE.findall(raw)} & hedef
            refs -= {trig.get("g") or "", trig.get("verG") or ""}
            if refs:
                trig_list.remove(trig)
                dangling += 1
    return dangling


def adapt_seeded_slide(pkg: StoryPackage, part: str, *,
                       eyebrow: str | None = None,
                       palette: dict | None = None,
                       feedback: dict | None = None,
                       style: str | None = None,
                       variant: str | None = None,
                       avoid_variant: "list[str] | None" = None) -> dict:
    """Gömülü tohumdan yalnızca ANATOMİYİ tutar, tasarımı kurstan alır.

    Tohum gercek bir kurstan hasat edildi. Onun tasarimini korumaya calismak
    bir yamalar zinciri uretti -- bir turda su alti kusur tek tek yakalandi
    ve tek tek yamandi:

        yabanci metin (baska bolumun adi, baska kursun degiskeni)
        pakete kurulmamis gorsel
        yazisi silinen rozetin bos kabi
        hedefi olmayan tetikleyiciler
        tohumun kendi zemin rengi
        cumleleri tasiyamayan dagınık sik duzeni

    Hepsi ayni koktendi: **butun slayt klonlaniyordu.** Projenin kendi kurali
    "kabi klonla, ozelligi yaz" -- soru slaydinda bu ayrim hic yapilmamisti.
    Ve bir kurstan tasarim devsirmek, kacilmaya calisilan tavanin ta kendisi.

    Bu yuzden kural tersine cevrildi: TUTULMASI ZORUNLU OLAN disinda her sey
    gider. Zorunlu olanlar, elle yazilirsa dosyayi bozan seyler --

        etkilesim ogesi (*Intr) ve choices kayitlari
        sik kaplarinin anatomisi (durum govdeleri)
        katman kaplari ve goster/gizle tetikleyicileri

    Geri kalan her sey kursun kendi motorundan gelir: zemin, renk, punto,
    ust etiket, kok, sik yerlesimi. Boylece soru slaydi icerik slaytlariyla
    ayni motordan cikar ve tohum havuzu buyudugunde kursun gorunumu
    degismez -- tohumdan yalnizca anatomi alinir.
    """
    from . import compose as _compose

    root = pkg.parse(part)
    shape_list = root.find("shapeLst")
    if shape_list is None:
        return {"removed": [], "kept": 0}

    tag, intr = _find_interaction(root)
    if intr is None:
        return {"removed": [], "kept": 0}
    # SIRA TEK YERDEN: `_choice_shape_guids` belge sirasini dondurur ve o,
    # YAZARIN verdigi siradir. Burada bir donem `set(...)` vardi ve sira
    # kayboluyordu; asagida `list(choice_ids)` diye cerceveye SIRA olarak
    # geri veriliyordu.
    #
    # Sonucu OLCULDU (2026-08-17, ayni girdi bes kosu): sik sirasi
    # KARARSIZ. Uc kosuda dogru cevap ustte, ikisinde altta cikti --
    # `list(set)` dizelerin hash rastgelelestirmesine (PYTHONHASHSEED)
    # dusuyor ve o surec basina degisiyor. Ayni kurs iki kez uretildiginde
    # siklar farkli yerlere iniyordu.
    #
    # Puanlama tutarli kaliyordu (her sekil kendi kimligini tasir), o yuzden
    # hicbir yapisal kontrol bagirmadi. Ama SIRA ICERIGIN PARCASI: "hangisi
    # once gelir", "en uygun olani sec" gibi sorularda yazarin verdigi duzen
    # anlamlidir ve ekranda korunmuyordu.
    #
    # Kume yalnizca UYELIK testi icin; sira ondan TURETILMEZ (K12).
    choice_order = _choice_shape_guids(intr)
    choice_ids = set(choice_order)
    # BIRAKMA HEDEFLERI DE ANATOMI. Olculdu 2026-08-30, bugunku yol taban
    # cizgisi olarak kosturuldu: 9 ogeli/3 kutulu tohum kuruldu, ogelerin
    # 9'u da hayatta kaldi ve KUTULARIN 3'U DE SILINDI -- "yazisiz roundRect"
    # oldukları icin 1. adimin donor-icerik filtresine takildilar. Geriye
    # birakilacak yeri olmayan dokuz surukleme kaldi: dosya gecerli,
    # kontroller sessiz, soru cevaplanamaz. submitG ve A1 ile ayni sinif.
    target_order = _drop_target_guids(intr)
    keep_ids = choice_ids | set(target_order)
    # Kutular sikların ALTINDA duruyor ve yazisiz olabiliyorlar; kok
    # secimine aday olmamalari icin dislanan kumeye onlar da girer.
    stem = _stem_shape_guid(root, choice_order + target_order)

    width, height = shapes.slide_size(root)
    removed: list[str] = []

    # 1. ANATOMI DISINDA HER SEY GIDER.
    #
    # NE SILDIGIMIZ KAYDEDILIYOR: asagidaki 2. adim tetikleyicileri tam
    # olarak bu kumeye gore ayikliyor. "Pakette cozulmeyen guid" olcutu
    # denendi ve saglam tetikleyicileri sildiriyordu (gerekcesi
    # _drop_dangling_triggers'in belge dizesinde).
    silinen: set[str] = set()
    for shape in list(shape_list):
        guid = shape.get("g") or ""
        if shape is intr or shape.tag.endswith("Intr"):
            continue
        if guid in keep_ids or guid == stem:
            continue
        text = model.shape_text(root, guid).strip() if guid else ""
        removed.append(f"{shape.tag}: {text[:24]!r}" if text else shape.tag)
        silinen |= guids_within(shape)
        shape_list.remove(shape)

    # 1-KATMAN. AYNI KURAL KATMANLARDA DA ISLER -- ve IKI YOLDA DA.
    #
    # Cekirdek `_temizle_donor_katmanlari`'nda; burasi tohum yolu, klon yolu
    # ise register_question uzerinden ayni fonksiyonu cagirir. Bir sure
    # yalnizca burada duruyordu ve add_question'in KLON dali (projede sablon
    # varsa secilen yol) hic temizlenmiyordu -- yani uretimde rozet duruyordu.
    # Ayni tuzagin kaydi zaten add_question'da yaziliydi: "iki soru yolu var
    # ve kayit IKISINDE de olmali".
    _kat_silinen, _kat_rapor = _temizle_donor_katmanlari(
        root, {v["name"] for v in model.variables(pkg)})
    removed.extend(_kat_rapor)
    silinen |= _kat_silinen

    # 1a. SICAK NOKTA TOHUMU METIN LISTESINE UYARLANIR -- SILMEDEN SONRA.
    #
    # MEKANIZMA OLCULEREK COZULDU (2026-08-19), ve uc kez yanlis yere
    # bakildi:
    #
    #     TOHUM            <pic> VAR + 5 oval, etiketler GIZLI  <- DOGRU
    #                      (elle yapilmis kursun "bu odada bes risk var,
    #                       uzerine tikla" slaydindan hasat edilmis)
    #     yukaridaki 1.    <pic>'i SILER -- donor icerigi, anatomi disi
    #     SONUC            gorsel yok, etiket hala gizli -> BOS KAPSUL
    #
    # Yani kusur ne tohumda ne metin yaziminda: GORSELI BIZ SILIYORUZ ama
    # etiketi gorunur yapmiyoruz. Ogrenci bes bos kapsul goruyor ve neyi
    # sectigini okuyamadan seciyor. A1 (skor kaydedilmiyor) ve submitG
    # (gonder calismiyor) ile ayni sinif: dosya gecerli, kontroller sessiz,
    # soru islevsiz.
    #
    # OLCUT GORSELIN VARLIGI, ve bu adim silmeden SONRA kosmali. Ilk surum
    # `_write_question` icindeydi -- orada <pic> HENUZ DURUYORDU, guard
    # dogru soruyu YANLIS ANDA sordu ve "dokunma" dedi.
    #
    # Gorsel hayatta kalirsa (ileride sicak nokta destegi gelirse)
    # etiket yine gizli kalir; uyarlama yalnizca gorselsiz baglamda.
    if _etiketi_gorunur_yap(root, choice_order):
        removed.append("sik etiketleri gorunur yapildi (sicak nokta -> liste)")

    # 1a-bis. ELIPS -> KAPSUL BURADA YAPILAMAZ ve cagri KASTEN YOK.
    #
    # Etiket duzeltmesi burada dogru yerde, sekil duzeltmesi DEGIL: bu anda
    # ovaller hala donor olcusunde (olculdu: 161x149 = 1.1, 161x261 = 0.6),
    # yani kalibrasyon bandinin icinde ve guard hakli olarak dokunmuyor.
    # Gerilme compose.compose_question_frame'de oluyor; cevirme de orada.
    # Buraya bir cagri konursa sessizce 0 doner ve "yapildi" gibi gorunur.

    # 1b. GONDER TETIKLEYICISI YENI ETKILESIME BAGLANIR -- silinmez, ONARILIR.
    #
    # OLCULDU (2026-08-17, editorde gozlendi): uretilen soru slaytlarinda
    # Player Triggers soyle goruunuyordu --
    #
    #     Submit Button
    #       When the user clicks submit
    #         Submit [unassigned]        <- kirmizi
    #
    # Yani gonder dugmesi HANGI ETKILESIMI gonderecegini bilmiyor. Ogrenci
    # cevabi isaretliyor, Submit'e basiyor, degerlendirme yapilmiyor. A1'in
    # (skorun questionIdLst'e yazilmamasi) tam kardesi: puanlama zincirinin
    # bir baska kopuk halkasi, ve ikisi de dosyayi GECERLI birakiyor.
    #
    # DOGRU BICIM TAHMIN EDILMEDI, elle yapilmis bir kurstan okundu
    # (0_duz_kopya.story): 11 soru slaydinin 11'inde `submitG`, O SLAYDIN
    # kendi etkilesim guid'ine esit. Onarim o bicime yaziyor.
    #
    # SILMEK YANLIS CEVAP OLURDU. Asagidaki 2. adim hedefi cozulmeyen
    # tetikleyicileri siler; gonder tetikleyicisi de oraya dusseydi soru
    # gonderilemez hale gelirdi -- kusuru baska bir kusurla degistirmek.
    # O yuzden onarim silmeden ONCE kosuyor.
    #
    # Kaynak TEK: yeni etkilesimin kendi `g`'si. Ayri bir yerden okumak
    # `_choice_shape_guids` ayrismasinin aynisi olurdu (K12).
    #
    # BU DAL SU AN HIC KOSMUYOR -- OLCULDU (2026-08-17) ve oyle isaretli
    # kalmali. `pick_template_for_question` HER ZAMAN gomulu tohumu seciyor
    # (0_duz_kopya.story icinde bile: secilen sablon
    # `bundled:freePickOneIntr:2`), ve o tohumda `submitG` yok. Yani
    # onarilacak bir baglanti hic olusmuyor ve kanarya KURULAMIYOR.
    #
    # Silinmedi, cunku sozlesme dogru ve olculmus bir bicime dayaniyor
    # (elle yapilmis kursta 13/13). Ama "korunuyor" da denemez: kosmayan
    # bir dal, sinanmamis daldir. apply_choice_plan'in tersi durum --
    # orada olu dal SINANIYOR ama kosmuyordu; burada kosmuyor ve
    # sinanamiyor da. Proje sablonu yolu acilirsa ilk is kanaryayi kurmak.
    #
    # ACIK SORU, bundan daha ciddi: urettigimiz soru slaytlarinda gonder
    # tetikleyicisi HIC YOK, elle yapilmis kursta 13/13 var. Ogrenci
    # cevabi nasil gonderiyor -- oynaticinin kendi dugmesiyle mi, yoksa
    # hic gonderemiyor mu? XML'den cevaplanamaz; Preview gerekiyor.
    submit_fixed = 0
    for el in root.iter():
        if el.get("submitG") and el.get("submitG") != intr.get("g"):
            el.set("submitG", intr.get("g") or "")
            submit_fixed += 1
    if submit_fixed:
        removed.append(f"{submit_fixed} gonder baglantisi onarildi")

    # 2. Hedefi kalmayan tetikleyiciler. Silinen sekilleri isaret edenler ve
    #    tohumun kendi kursundaki degiskene bakanlar burada dusuyor.
    #    Bilinen kume slaydin TAMAMI: katman guid'leri sldLayerLst'te yasiyor
    #    ve onlari disarida birakmak "Dogru Cevap katmanini goster"
    #    tetikleyicisini de sildiriyordu -- olculdu, soru geri bildirim
    #    veremez hale gelmisti.
    dangling = _drop_dangling_triggers(pkg, root, silinen)
    if dangling:
        removed.append(f"{dangling} kopuk tetikleyici")

    # 3. Zemin kursun temasindan.
    if palette:
        _paint_slide_ground(root, palette.get("bg", "#0E1B3D"))
    pkg.replace_xml(part, root)

    # 4. Cerceve ve yerlesim motordan.
    if tag == "dragDropIntr":
        laid = _compose.compose_drag_frame(
            pkg, part, eyebrow=eyebrow, palette=palette, stem_guid=stem,
            pairs=_drag_pairs(_find_interaction(pkg.parse(part))[1]),
            style=style)
    else:
        laid = _compose.compose_question_frame(
            pkg, part, eyebrow=eyebrow, palette=palette,
            stem_guid=stem, choice_guids=choice_order,
            style=style, variant=variant, avoid_variant=avoid_variant)

    # 5. Geri bildirim katmanlarinin ICI. Kabi klonlanmis kalir.
    layers = _compose.compose_feedback_layers(pkg, part, palette=palette,
                                              feedback=feedback)
    # Boyama paylasilan fonksiyondan, METIN surukle-birakta kendi
    # fonksiyonundan: katman adi bos oldugu icin rol adla cozulemiyor.
    if tag == "dragDropIntr":
        layers = {**layers,
                  **_compose.compose_drag_feedback(pkg, part, feedback=feedback)}

    if palette:
        _recolour_for_palette(pkg, part, palette, stem=stem,
                              choices=keep_ids, eyebrow=None)
    return {"removed": removed, "kept": 1 + len(keep_ids) + (1 if stem else 0),
            **laid, **layers}


def _recolour_for_palette(pkg: StoryPackage, part: str, palette: dict, *,
                          stem: str | None, choices: set,
                          eyebrow: str | None) -> int:
    """Yazı renklerini ARKASINDAKİNE göre seçer, kuralla tahmin etmez.

    Once kural yazilmisti ("sik ise on_accent, degilse text") ve yanlisti:
    tohumun butonlarinin dolgusu yok, etiketleri zeminin uzerinde duruyor ve
    on_accent onlari kirik beyaz uzerinde beyaz birakiyordu (1.09).

    Ve uygulama SAHIBINE gore yapilir: _iter_text_shapes IC sekli veriyor,
    bir butonun etiketi durum govdelerinde yasiyor ve her govdenin kendi
    guid'i var. Dis guid'le karsilastirmak butonlari atliyordu -- dort
    yazidan ucu renkleniyordu.
    """
    from . import preview
    from .compose import _contrast

    def rgb(value: str) -> tuple[int, int, int]:
        h = shapes.parse_color(value)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    root = pkg.parse(part)
    ground_paint = preview.slide_ground(root, [])
    ground = rgb(ground_paint) if (ground_paint or "").startswith("#")         else rgb(palette.get("bg", "#0E1B3D"))
    # KATMANLAR DA BOYANIR. Bir sure yalnizca slaydin kendi shapeLst'i
    # geziliyordu; katman sekilleri `top` icinde bulunmadigi icin sahipleri
    # cozulemiyor ve SESSIZCE atlaniyordu. Sonucu ekranda: slayt kursun
    # temasini giyerken geri bildirim pop-up'i tohumun renklerinde kaliyordu
    # (kullanici bildirdi 2026-09-05; olculdu: uretilen kurslarda katman
    # sekillerinin hicbirinde ne dolgu ne acik yazi rengi vardi).
    #
    # Govde listesi model.bodies'ten gelir -- ayni kural animasyonda ve tohum
    # temizliginde de unutulmustu, o yuzden arama tek yerde durur.
    wanted: dict[str, str] = {}
    top: dict[str, ET.Element] = {}
    for _ad, govde in model.bodies(root):
        # Katmanin KENDI zemini varsa o gecerli; yoksa slaydinki gorunur.
        zemin = ground
        if govde is not root:
            try:
                kat = preview.slide_ground(govde, [])
            except Exception:
                kat = None
            if (kat or "").startswith("#"):
                zemin = rgb(kat)
        for shape in list(govde.find("shapeLst") or []):
            guid = shape.get("g") or ""
            if not guid:
                continue
            own = preview._fill_of(shape, [])
            behind = rgb(own) if (own or "").startswith("#") else zemin
            options = [palette.get("text", "#FFFFFF"),
                       palette.get("on_accent", "#10141B"),
                       palette.get("accent_text", palette.get("accent", "#FFC72C"))]
            wanted[guid] = max(options,
                               key=lambda c: _contrast(rgb(c), behind))
            top[guid] = shape

    parents = model._parent_map(root)
    touched = 0
    for shp, text_el, _doc, _state in model._iter_text_shapes(root):
        node, owner = shp, None
        while node is not None:
            if node.get("g") in top and top[node.get("g")] is node:
                owner = node.get("g")
                break
            node = parents.get(node)
        colour = wanted.get(owner)
        if not colour:
            continue
        text_el.text = shapes.set_text_style(text_el.text or "", color=colour)
        touched += 1
    pkg.replace_xml(part, root)
    return touched


def _restyle_shape_text(root: ET.Element, guid: str, *, size: float) -> None:
    """Bir şeklin (ve durum gövdelerinin) yazı puntosunu değiştirir."""
    parents = model._parent_map(root)
    for shp, text_el, _doc, _state in model._iter_text_shapes(root):
        node = shp
        while node is not None:
            if node.get("g") == guid:
                text_el.text = shapes.set_text_style(text_el.text or "",
                                                     size=size)
                break
            node = parents.get(node)


_GUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
# Oynatici %AD% bicimindeki degisken referansini metin icinde COZER; adi
# bilmiyorsa oldugu gibi YAZAR. Tohumdan gelen bir referans bu projede
# yoksa ogrenci ekranda "%GuvenlikSkoru%" okur -- olculdu 2026-09-05.
_DEGISKEN_REF = re.compile(r"%([A-Za-z_][A-Za-z0-9_]*)%")


def _protected(shape, keep: set, intr) -> bool:
    """Silinmesi YASAK olan şekiller. Tek yerde, çünkü üç silme döngüsü var.

    Etkilesim ogesi (freePickOneIntr / freePickManyIntr) yazisiz ve slaydin
    tamamini kapliyor -- yani "yazisiz buyuk dolgu" diyen her kural onu aday
    sayar. Bir kez tam olarak oyle oldu: silinen gorselin cercevesini
    temizleyen dongu etkilesimi de sildi ve soru soru olmaktan cikti,
    9 sekil kaldi ama puanlanacak hicbir sey yoktu. Hicbir yapisal kontrol
    bagirmazdi: dosya gecerli, slayt aciliyor.

    Korumayi her donguye ayri ayri yazmak, birinde unutmak demektir.
    """
    if shape is intr:
        return True
    if (shape.get("g") or "") in keep:
        return True
    return shape.tag.endswith("Intr")


def _paint_slide_ground(root: ET.Element, colour: str) -> int:
    """Slaydın <bg> öğesini kursun zeminine boyar. Şekil değil, slayt."""
    bg = root.find("bg")
    if bg is None:
        bg = ET.SubElement(root, "bg")
    for tag in ("solidFill", "gradFill", "gradOvrlyFill"):
        for old in bg.findall(tag):
            bg.remove(old)
    fill = ET.SubElement(bg, "solidFill")
    clr = ET.SubElement(fill, "clr")
    ET.SubElement(clr, "srgbClr").set("val", shapes.parse_color(colour))
    return 1


def _installed_assets(pkg: StoryPackage) -> set[str]:
    """story.xml'de kayitli ve baytlari pakette olan medya GUID'leri."""
    import hashlib
    digests = set()
    for name in pkg._order:
        if "/media/" in name:
            try:
                digests.add(hashlib.md5(pkg.read(name)).hexdigest())
            except Exception:
                continue
    out: set[str] = set()
    try:
        story = pkg.parse("story/story.xml")
    except Exception:
        return out
    for entry in story.iter("media"):
        stream = entry.find("md5Checksum/stream")
        digest = (stream.text or "").strip() if stream is not None else ""
        if entry.get("g") and digest in digests:
            out.add(entry.get("g"))
    return out


def _write_question(pkg: StoryPackage, part: str, prompt: str, choices: list[str],
                    correct: list[int], points: int | None) -> None:
    """Replace a question slide's stem, options and scoring."""
    root = pkg.parse(part)
    tag, intr = _find_interaction(root)
    if intr is None:
        raise StoryError("Soru slaydinda etkilesim bulunamadi.")
    guids = _choice_shape_guids(intr)
    if len(guids) != len(choices):
        raise StoryError(f"Sablon {len(guids)} secenek tasiyor, {len(choices)} verildi.")

    stem = _stem_shape_guid(root, guids)
    if stem:
        set_shape_text(root, stem, prompt)
    for guid, text in zip(guids, choices):
        set_shape_text(root, guid, text)


    correct_set = set(correct)
    for index, choice in enumerate(list(intr.find("choices"))):
        scoring = choice.find("scoringData")
        if scoring is not None:
            scoring.set("correct", "true" if index in correct_set else "false")
    if points is not None:
        props = intr.find("intrProps")
        if props is not None:
            props.set("corPts", str(points))
    pkg.replace_xml(part, root)


def question_seeds() -> dict[tuple[str, int], list["Path"]]:
    """Gömülü soru slaytları, (etkileşim türü, şık sayısı) -> GÖRÜNÜŞ LİSTESİ.

    DEĞER LİSTE, ÇÜNKÜ BİR BİÇİMİN BİRDEN ÇOK GÖRÜNÜŞÜ VAR. Burası bir
    zamanlar `dict[(kind, count), Path]` idi ve iki kusuru vardı; ikisi de
    aynı yöne bakıyordu -- kütüphane zenginleşebilir, tüketici göremez:

      1. `len(parts) == 3` filtresi. `harvest_questions` bir biçimin ikinci
         ve üçüncü görünüşünü `question_<tur>_<sayi>_2.xml` diye yazıyor
         (keep_per_shape=3). Dört parçalı bu adlar filtreden DÜŞÜYORDU:
         hasat "3 görünüş saklandı" diyor, üretim yalnızca birini görüyordu.
      2. Anahtar başına tek değer. Filtre geçilseydi bile ikinci görünüş
         birincinin ÜZERİNE yazardı.

    Yani `keep_per_shape` baştan ölüydü ve bunu hiçbir şey söylemiyordu:
    hasat yeşil biter, üretilen kursta bütün sorular aynı mobilyayı giyerdi.
    Ölçüldü 2026-08-29: 6 modül, 25 soru, 2 biçim -- ve o 2, diskteki tohum
    sayısının ta kendisi.

    Sıra KARARLI: aynı kütüphane her koşuda aynı sırayı verir, yoksa "hangi
    görünüş seçildi" tekrar üretilemez bir sayı olurdu.
    """
    from pathlib import Path as _Path
    seeds: dict[tuple[str, int], list[_Path]] = {}
    for f in sorted((clone.SEED_DIR).glob("question_*.xml")):
        parts = f.stem.split("_")
        # question_<tur>_<sayi>[_<gorunus>]
        if len(parts) < 3 or not parts[2].isdigit():
            continue
        if len(parts) == 4 and not parts[3].isdigit():
            continue
        if len(parts) > 4:
            continue
        seeds.setdefault((parts[1], int(parts[2])), []).append(f)
    return seeds


def question_seed(kind: str, count: int, look: int = 0) -> "Path | None":
    """Bir biçimin BELİRLİ görünüşü. Yoksa None -- sessizce ilkine düşmez.

    Sessiz geri düşüş bu projenin en pahalı alışkanlığı: seçilen görünüş
    yoksa çıktı yine geçerli bir dosya olur, hiçbir kontrol bağırmaz ve
    "neden bütün sorular aynı" sorusunun cevabı kaybolur.
    """
    looks = question_seeds().get((kind, count)) or []
    return looks[look] if 0 <= look < len(looks) else None


# --------------------------------------------------- soru provasi, iki asama
#
# Olculen alan asagi akar, ve yalnizca asagi.
#
#   cerceve (baslik, govde, ilerleme, navigasyon)   SABIT
#       |  kendi yuksekligini olcer, kalani bildirir
#       v
#   etkilesim blogu (sik sekilleri, durumlar, tetikleyiciler)   ESNEK
#       |  bildirilen alana sigar: once boslugu, sonra puntoyu kisar
#       v
#   SHRINK_FLOOR'a kadar. Yetmezse sablon reddedilir, gerekcesiyle.
#
# Yon tek tarafli, bilerek. Sik puntosu cerceveyi etkileyebilseydi cerceve
# yeniden olcer, yeni bir kalan bildirir, sik yeniden kisilir -- olcumun
# kendi kuyrugunu kovaladigi bir dongu. Cerceve olcuyu VEREN taraf oldugu
# icin ondan geri besleme alinmaz.
#
# Tasma hicbir kosulda secenek degil: butonda cevap "kutu buyur" idi, burada
# asagi dogru sonsuz alan olmadigi icin cevap "icerik kisilir, yetmezse
# reddedilir". Ikisi de sessiz kalmaz.
#
# SHRINK_FLOOR kalibre bandin alt ucuna baglanir (shapes.CALIBRATED_RANGE[0]),
# sezgiye degil: altina inmek, hata yonunun bilinmedigi olculmemis bolgede
# kucultme yapmak olur ve yanlis yone sapan bir kucultme tam olarak reddettigimiz
# tasmayi arka kapidan geri getirir.

# Gomulu tohumlarin ilan ettigi koordinat uzayi. OLCULDU (2026-08-17):
# add_question'in urettigi slayt 1920x1080 <sldSz> tasiyor, oysa projenin
# sahnesi (story/story.xml <sz>) 720x540. Ikisi ayri ve bu fark bir donem
# butun dikey matematigi kaydirdi (K17).
#
# Sabit BURADA cunku gomulu tohumun slayt parcasi katalog asamasinda
# okunamiyor; okunabildiginde _template_space onu dosyadan alir ve bu sayi
# hic kullanilmaz.
BUNDLED_SPACE = (1920.0, 1080.0)

PROBE_STEM = "PROVA SORU KOKU"
PROBE_CHOICES = ["PROVA BIR", "PROVA IKI", "PROVA UC", "PROVA DORT",
                 "PROVA BES", "PROVA ALTI", "PROVA YEDI", "PROVA SEKIZ"]

_template_cache: dict[tuple, dict[str, tuple[bool, str]]] = {}


def rehearse_template(pkg: StoryPackage, template: str, count: int) -> tuple[bool, str]:
    """Fill this template with probe content and read it back.

    The static half of the check: can this template hold *a* question at all?
    Not whether it can hold *the* question -- the real stem and the real
    options are not known here, and pretending otherwise is the mistake the
    donor pool already made once, where a pool rehearsed against one sample
    label handed out shapes that overflowed on every longer one.

    Run against a throwaway copy of the package on disk, so a project can be
    surveyed without being written to. Unsaved edits in `pkg` are therefore
    invisible here, which is right for a catalogue and wrong for a placement;
    the placement-time check is the other half.
    """
    if count < 1 or count > len(PROBE_CHOICES):
        return False, f"{count} secenek prova araligi disinda"
    try:
        probe = StoryPackage(pkg.path)
        result = add_question(probe, template, PROBE_STEM,
                              PROBE_CHOICES[:count], [0])
    except StoryError as exc:
        return False, str(exc)[:70]
    except Exception as exc:  # bozuk sablon; kataloga girmemeli
        return False, f"{type(exc).__name__}: {str(exc)[:50]}"

    for question in model.quiz(probe):
        if question.get("slide") != result.get("new_slide"):
            continue
        if question["prompt"].strip() != PROBE_STEM:
            return False, f"kok geri okunmadi ({question['prompt'][:20]!r})"
        texts = [c["text"].strip() for c in question["choices"]]
        if texts != PROBE_CHOICES[:count]:
            return False, f"secenekler geri okunmadi ({texts[:2]})"
        if [i for i, c in enumerate(question["choices"]) if c["correct"]] != [0]:
            return False, "dogru cevap islenmedi"
        return True, "tamam"
    return False, "yazilan soru geri okunamadi"


def available_question_shapes(pkg: StoryPackage, *,
                              rehearsed: bool = True) -> list[dict]:
    """Every question arity this project can actually produce.

    "Actually" is the whole point. This used to list every question slide it
    found and leave the filling to be attempted later, so a template whose
    option shapes carry no text run at all -- a deck's author styled them and
    never typed into them -- was offered as available and failed at write
    time, after the caller had planned a course around it.

    So each candidate is rehearsed, the way the seed library rehearses a seed
    before keeping it. rehearsed=False returns the old unchecked list, which
    is only for tools that want to show what was rejected and why.
    """
    out: list[dict] = []
    # Keyed on the file, not just its name: edit a template in Storyline and
    # the old verdict would otherwise outlive the thing it judged, which is
    # this project's favourite failure wearing a cache for a hat -- the check
    # ran, the answer was stale, nothing said so. Same key shape donors uses.
    try:
        stat = pkg.path.stat()
        key = (str(pkg.path), stat.st_mtime_ns, stat.st_size)
    except OSError:
        key = (str(pkg.path), 0, 0)
    verdicts = _template_cache.setdefault(key, {})

    for template in list_templates(pkg):
        if template["kind"] != "question" or template.get("question_type") == "dragDropIntr":
            continue
        entry = {"source": "project", "slide": template["slide"],
                 "type": template["question_type"],
                 "choices": template["choice_count"]}
        if not rehearsed:
            out.append(entry)
            continue
        if template["slide"] not in verdicts:
            verdicts[template["slide"]] = rehearse_template(
                pkg, template["slide"], template["choice_count"])
        ok, why = verdicts[template["slide"]]
        entry["rehearsal"] = why
        if ok:
            out.append(entry)

    # GORUNUS BASINA BIR KAYIT. Bicim basina bir kayit yaziliyordu ve
    # kutuphanedeki ikinci/ucuncu gorunus katalogda HIC GORUNMUYORDU --
    # question_seeds'teki iki kusurun tuketici tarafindaki devami.
    for (kind, count), looks in question_seeds().items():
        if kind not in PICK_KINDS:
            continue
        for i, seed in enumerate(looks):
            out.append({"source": "bundled", "slide": None, "type": kind,
                        "choices": count, "look": i, "seed": seed,
                        "template": bundled_name(kind, count, i),
                        "rehearsal": f"gomulu tohum ({seed.name})"})
    return out


class NoTemplateFits(StoryError):
    """Hicbir sablon bu soruyu tasiyamadi -- ve hangisi neden tasiyamadi.

    Havuz=0'in soru tarafindaki karsiligi. Orada uc ihtimal vardi ve en
    kotusu -- "uygun aday yok"u sessizce gecistirmek -- bir kez gerceklesmisti.
    Burada ayni zemin var, o yuzden tukenme sessiz degil: her adayin gerekcesi
    istisnanin uzerinde tasinir.
    """

    def __init__(self, message: str, rejections: list[dict]):
        super().__init__(message)
        self.rejections = rejections


class ChoiceLabelsTooLong(StoryError):
    """Şıklar taban puntoda bile yuvalarına sığmıyor: etiket sorunu.

    UCUNCU TESHIS, ve digerlerinden ayri durmasi ayni sebeple: farkli is
    gerektiriyor. "Hicbir sablon uymuyor" duyan kataloga sablon ekler; "kok
    cerceveyi yedi" duyan koku kisaltir; buradaki sorun ETIKETLERDE ve
    yalnizca onlari kisaltmakla cozulur.

    NEDEN RED, NEDEN YERLESTIRME DEGIL. compose_question_frame bir donem
    tabana inip sonra `each = min(need, mevcut)` ile kutuyu MEVCUDA
    KIRPIYORDU -- yani sigmadigini biliyor, yine de yerlestiriyor ve metin
    kutunun disina tasiyordu. Olculdu (2026-08-17, uzun/orta vakasi): kutu
    87 birim, etiket 93 istiyor. Hicbir kontrol bagirmiyordu cunku geometri
    taban icinde kaliyor; tasan sey METINDI.

    Sozlesme fit_choices ile ayni: sigmazsa NEDEN. Cagiran taraf (builder)
    bunu StoryError olarak yakalar ve soruyu menu slaydina dusurur --
    gerekcesi rapora yazilir. Sablon dongusu pick_template'te bitmis
    oldugu icin red baska bir sablon denemez; bu bilincli, cunku ayni sik
    sayisinin sablonlari ayni geometri ailesinden.
    """


class StemStarvesFrame(StoryError):
    """Kok cerceveyi yedi: sablon degil metin sorunu.

    NoTemplateFits'ten ayri, cunku teshis ayri ve cozumu ayri. "Hicbir sablon
    uymuyor" duyan biri kataloga sablon ekler; buradaki sorun kataloga sablon
    eklemekle cozulmez, ve yanlis teshis birini o isi yapmaya gonderir.
    """


def pick_template(pkg: StoryPackage, choices: list[str], area_percent: float,
                  *, stage: tuple[float, float] | None = None,
                  stem: str | None = None, eyebrow: str | None = None,
                  avoid: list[str] | None = None) -> dict:
    """Bu soruyu gercekten tasiyabilen ilk sablon, ya da gerekceli tukenme.

    Uc soru, ucu de burada cevaplaniyor:

    *Sirada kim var.* Katalog sirasi korunur ama once secenek sayisi tutanlar
    denenir; tutmayan zaten add_question tarafindan reddedilecektir.

    *Ayni sablon iki kez denenmez.* `seen` bunu garanti eder. Bir sablonun
    iki kez reddedilmesi yalnizca gurultu degil, dongu riskidir.

    *Hepsi reddedilirse.* NoTemplateFits, her adayin gerekcesiyle. Sessizce
    ilk sablona geri dusmek, tam olarak kacinilan sey.

    Red bir sonuc degil bir istek oldugu icin ("baska sablon ver"), donen
    kayit kacinin ve neden reddedildigini de tasir: kompozisyon sessizce
    ucuncu tercihe duserse cikti saglam olur ama tasarim secimi bozulmustur
    ve hicbir test bagirmaz. Sayiyi gormek, katalogun yetersizlestigini fark
    etmenin tek yolu.
    """
    from . import compose

    # SAHNE, ve elle yazilmis varsayilan YOK. Bir donem burada
    # `slide or (720.0, 540.0)` vardi -- olu dalda silinen kusurun aynisi.
    stage = stage or package_stage(pkg)
    space = shapes.Space(stage[0], stage[1], stage[0], stage[1])
    width = compose.CONTENT_W / 100 * stage[0]
    rejections: list[dict] = []
    seen: set[str] = set()

    # SIRA GECMISE GORE. Katalog sirasi sabitti ve secim HER ZAMAN ilk uyan
    # sablona gidiyordu: kutuphaneye ucuncu bir gorunus eklemek katalogda
    # gorunuyor, uretilen kursta hicbir sey degistirmiyordu. Olculdu
    # 2026-08-29 (hasat oncesi): 6 modul, 25 soru, kullanilan gorunus 2.
    #
    # `compose.variant_for` ile AYNI olcu, cunku sorun ayni sorun: en uzun
    # suredir kullanilmayan secilir, esitligi kok metninin hash'i bozar.
    # Hash `sum(ord)` degil -- benzer kokler ayni kovaya yigilmasin diye,
    # ve turetilmis oldugu icin ayni kurs yeniden kuruldugunda ayni sirayi
    # verir. Yasagi cignemek gerekiyorsa cignenir: icerik cesitlilikten
    # once gelir, ve red zaten gerekcesiyle raporlaniyor.
    gecmis = list(avoid or [])

    def _yas(anahtar: str) -> int:
        for geri, kullanilan in enumerate(reversed(gecmis), start=1):
            if kullanilan == anahtar:
                return geri
        return len(gecmis) + 1

    def _anahtar(entry: dict) -> str:
        return entry["slide"] or entry.get("template") or bundled_name(
            entry["type"], entry["choices"], entry.get("look", 0))

    _tohum_ozet = int(hashlib.sha256((stem or "").encode("utf-8")).hexdigest(), 16)
    _katalog = list(available_question_shapes(pkg))
    _adaylar = sorted(
        enumerate(_katalog),
        key=lambda pair: (-_yas(_anahtar(pair[1])),
                          (_tohum_ozet + pair[0]) % max(len(_katalog), 1)))

    for _sira, entry in _adaylar:
        # ADI KATALOG VERIR. Burada `bundled_name(tur, sayi)` ile yeniden
        # uretiliyordu ve GORUNUS INDISINI DUSURUYORDU: ayni bicimin uc
        # gorunusu ayni anahtara iniyor, `seen` ikisini eliyor ve secim
        # her koşuda ilk gorunuse sabitleniyordu -- kutuphane zenginlesir,
        # secim tekduze kalir.
        key = _anahtar(entry)
        if key in seen:
            continue
        seen.add(key)
        if entry["choices"] != len(choices):
            rejections.append({"template": key, "why":
                               f"{entry['choices']} secenekli, {len(choices)} verildi"})
            continue

        # Dorduncu gerekce turu: duzeni modelin kapsamadigi sablon.
        #
        # fit_choices dikey yigina ozgu -- n kutu arti n-1 bosluk. Katalogdaki
        # sablonlarin ucu siklari yatay sirada tutuyor ve orada bir siranin
        # yuksekligi tek kutudur. O sablonu yigin matematigiyle olcup "sigar"
        # demek, hesaplanmamis bir seyi dogrulanmis gibi sunmak olur; yeniden
        # konumlandirmak ise sablonun tasarimini yok eder. Ikisi de yanlis,
        # o yuzden secilmiyor ve nedeni soyleniyor.
        # entry["slide"] YOKSA (gomulu tohum) None doner ve red olmaz:
        # o slayt yeniden cercevelenecek, dizilimi bestecinin.
        arrangement = _template_arrangement(pkg, entry["slide"])
        if arrangement not in ("stack", None):
            # known_limit: bu red her kosuda tekrar edecek, cunku kabul edilmis
            # bir sinirin sonucu. Gercek bir yetersizlikle ayni kanaldan
            # akarsa ikincisi gurultude kaybolur; rapor ikisini ayirabilsin.
            rejections.append({"template": key, "known_limit": True,
                               "why": f"sik duzeni {arrangement!r} — sigdirma "
                                      "modeli yalnizca dikey yigini kapsiyor"})
            continue

        # GENISLIK SABLONDAN OKUNUR. `width` (= icerik bandinin %84'u) yalnizca
        # okunamadiginda kullanilir -- gomulu tohumlarda sablon slaydi yok.
        # Hangisinin kullanildigi plana YAZILIR: bir sayinin nereden geldigi,
        # sayinin kendisi kadar onemli (K14).
        # GENISLIK SAHNE BIRIMINE CEVRILIR. Sablonun dikdortgeni kendi
        # koordinat uzayinda okunuyor (gomulu tohumlarda 1920), olcum ise
        # sahnede yapiliyor (720). Cevrilmezse ayni kutu 2.667 kat genis
        # sayilir ve sigmayan sik "sigar" cikar.
        sablon_gen = _template_choice_width(pkg, entry["slide"])
        if sablon_gen:
            t_uzay = _template_space(pkg, entry["slide"], stage)
            kullanilan = sablon_gen / t_uzay.h
        else:
            kullanilan = width
        plan = compose.fit_choices(choices, area_percent, kullanilan, space=space)
        plan["width"] = kullanilan
        plan["width_source"] = "sablon" if sablon_gen else "icerik bandi (varsayim)"
        if not plan["ok"]:
            rejections.append({"template": key, "why": plan["why"]})
            continue

        # SON YETKI: GERCEK YERLESIM, ATILACAK BIR KOPYADA.
        #
        # `fit_choices` buradan sonra yalnizca UCUZ ON ELEME. Karari o
        # vermiyor, cunku vermeye calistiginda cerceveyle AYRISTI ve
        # ayrisma olculdu (2026-08-19, 5 sikli coktan secmeli):
        #
        #     kabul testi : bant %54.1  kutu %9.02  -> "sigar"
        #     cerceve     : bant %54.1  kutu %9.95  -> RED
        #
        # Bant, `eyebrow` gecildikten sonra BIREBIR ayni. Kalan fark iki
        # ayri fonksiyondan geliyor: kabul testi `layout_text_height`,
        # cerceve `height_for_label` (sekli ve kendi marjlarini okur).
        # Iki formulu uzlastirmak ucuncu bir ayrisma kaynagi acardi.
        #
        # BEDELI OLCULDU ve kucuk degildi: cerceve reddettiginde
        # `add_question` slaydi ZATEN yaratmis oluyor, `panel/builder.py`
        # geri cekilme menusu ekliyor, ve kurs IKISINI BIRDEN gonderiyor.
        # Yetim slayt yalnizca bozuk degil, PUANLANMIYOR: "cevap alinir,
        # skor gitmez" (uretilmis kursta kayitli 2/4).
        #
        # Prova mekanizmasi yeni degil -- `_probe` katalog icin bunu zaten
        # yapiyor. Farki: o JENERIK etiketlerle kosuyor ve docstring'i
        # bunu soyluyor ("not whether it can hold *the* question").
        # Burasi o cumlenin eksik yarisi: GERCEK kok, GERCEK sikler.
        #
        # Boylece ayrisma insaen imkansiz: secilen sablon, ayni cerceve
        # aritmetiginden bir kez GECMIS olan sablondur.
        if stem is not None:
            olur, neden = _gercek_prova(pkg, key, stem, choices, eyebrow)
            if not olur:
                rejections.append({"template": key, "why": neden})
                continue
        return {"template": key, "plan": plan, "rejections": rejections}

    raise NoTemplateFits(
        f"{len(choices)} secenekli soru {area_percent:.1f}% alana sigan bir "
        f"sablon bulamadi; {len(rejections)} aday reddedildi.",
        rejections,
    )



def _template_root(pkg: StoryPackage, slide: str | None,
                   seed: "Path | None" = None):
    """Bir şablonun XML kökü: proje slaydı ya da gömülü tohum DOSYASI.

    UYARI -- SIĞDIRMA YOLU BUNU TOHUM İÇİN KULLANMAZ, ve sebebi ölçüldü.

    Tohumun kendi geometrisini okumak sezgisel olarak doğru görünüyor: hasat
    edilen tohumların üçü de şıklarını YATAY SIRADA tutuyor ve sığdırma
    modeli yalnızca dikey yığını kapsıyor, dolayısıyla "önce geometriyi oku,
    sonra reddet" doğru refleks gibi duruyor.

    Ölçüldü 2026-08-29 ve refleks yanlış çıktı: `add_question` gömülü tohum
    yolunda HER ZAMAN `compose_question_frame`'den geçiyor (`framed: True`)
    ve o, şıkları koşulsuz olarak tam genişlikte alt alta diziyor. Üç ayrı
    yatay tohum, çıktıda BİREBİR aynı yığını veriyor:

        tohumda : row    [(130,745,617,951), (716,756,1204,962), ...]
        çıktıda : stack  [(154,330,1766,398), (154,415,1766,483), ...]

    Yani tohumun kaynak dizilimi ve şık genişliği, üretilen slaytta var
    olmayan ölçüler. Onlara bakıp reddetmek, DEĞİŞTİRİLECEK bir şeyi
    değişmezmiş gibi ölçmek olur -- ve 3 şıklı biçimin tamamını, hiç
    gerçekleşmeyecek bir gerekçeyle kataloğun dışında bırakır.

    Ayrım şu, ve `add_question`'daki iki yoldan geliyor:

        gömülü tohum   -> her zaman yeniden çerçevelenir -> BESTECİNİN ölçüsü
        proje şablonu  -> olduğu gibi klonlanır          -> ŞABLONUN ölçüsü

    Bu yüzden `seed` parametresi burada duruyor ama sığdırma yolundan
    geçirilmiyor; tohum XML'ini okuması gereken (hasat, envanter, teşhis)
    çağıranlar için.
    """
    if slide:
        try:
            return pkg.parse(pkg.slide_part_for(slide))
        except Exception:
            return None
    if seed is not None:
        try:
            return ET.fromstring(seed.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _template_space(pkg: StoryPackage, slide: str | None,
                    stage: tuple[float, float],
                    seed: "Path | None" = None) -> shapes.Space:
    """Bir şablon slaydının kendi uzayı, sahneye karşı.

    Gomulu tohumlar 1920x1080 ilan ediyor, proje sablonlari projenin kendi
    boyutunda. Sablondan okunan her OLCU o slaydin izgarasindadir ve sahne
    biriminde kullanilmadan once cevrilmelidir.

    HASAT EDILEN TOHUM 1920x1080 OLMAK ZORUNDA DEGIL: baska bir projeden
    geliyor ve o proje 720x540 olabilir. Bu yuzden once tohumun KENDI ilani
    okunur; okunamazsa bilinen varsayilana dusulur.
    """
    root = _template_root(pkg, slide, seed)
    if root is not None:
        try:
            return shapes.space_of(root, stage)
        except Exception:
            pass
    # Ne proje slaydi ne de okunabilir tohum: tohumun bilinen uzayi.
    return shapes.Space(*BUNDLED_SPACE, stage[0], stage[1])


def _template_choice_rects(pkg: StoryPackage, slide: str | None,
                           seed: "Path | None" = None) -> list:
    """Bir şablonun şık dikdörtgenleri; okunamazsa boş liste."""
    root = _template_root(pkg, slide, seed)
    if root is None:
        return []
    try:
        _tag, intr = _find_interaction(root)
        if intr is None:
            return []
        by = {el.get("g"): el for el in root.iter() if el.get("g")}
        return [r for r in (shapes.shape_rect(by[g])
                            for g in _choice_shape_guids(intr) if g in by) if r]
    except Exception:
        return []


def _template_choice_width(pkg: StoryPackage, slide: str | None,
                           seed: "Path | None" = None) -> float | None:
    """Şablonun şıkları GERÇEKTE ne kadar geniş? Okunamazsa None.

    NEDEN SABIT OLMAMALI. Bu genislik bir donem `CONTENT_W / 100 * slide_w`
    idi -- bestecinin kendi icerik bandi, yani %84. Sablonun gercek
    geometrisiyle hicbir ilgisi yok, ve olculdu: 0_duz_kopya'nin soru
    sablonunda siklar 497 birim genis, varsayim 1613. Varsayimin %31'i.
    Dar kutuda ayni metin kat kat fazla satira sariyor, dolayisiyla planin
    ayirdigi yukseklik kat kat yetersiz kaliyor -- olculen tasma %356 (eski
    sabitlerle) ve %662 (yeni sabitlerle).
    1613'u 497'ye cevirmek COZUM DEGIL: o da bir sabit, sadece daha az
    yanlis. Sablon degistiginde yine sessizce sapar ve o sefer kimse bakmaz.
    K14: bir sayi hangi olcume karsi secildigini tasiyamiyorsa, sayi
    olmamali. Genislik SABLONDAN okunur; okunamazsa cagiran bilir.
    """
    rects = _template_choice_rects(pkg, slide, seed)
    if not rects:
        return None
    # En DAR sik baglayicidir: hepsi ayni metni tasiyabilmeli ve en dar kutu
    # en cok satira sarar. Ortalama almak, en dar kutuyu sessizce tasirirdi.
    return min(r[2] - r[0] for r in rects)


def _template_arrangement(pkg: StoryPackage, slide: str | None,
                          seed: "Path | None" = None) -> str | None:
    """Bir sablonun sik duzeni; geometrisi hic okunamazsa None."""
    rects = _template_choice_rects(pkg, slide, seed)
    return choice_arrangement(rects) if rects else None


def choice_arrangement(rects: list) -> str:
    """Şıklar nasıl dizilmiş: 'stack', 'row' ya da 'other'.

    Yerleşimi değiştirmeden önce sorulması gereken soru. Katalogdaki on
    şablonun üçü şıkları yatay sırada, üçü dikey yığında, kalanı kademeli
    tutuyor; hepsini tek bir varsayımla ele almak, çoğunun düzenini bozar.
    """
    clean = [r for r in rects if r]
    if len(clean) < 2:
        return "other"
    tops = [r[1] for r in clean]
    lefts = [r[0] for r in clean]
    same_left = max(lefts) - min(lefts) < 40
    same_top = max(tops) - min(tops) < 40
    increasing = all(b > a for a, b in zip(tops, tops[1:]))
    if same_top and not same_left:
        return "row"
    if same_left and increasing:
        return "stack"
    return "other"



def MARGIN_X_UNITS(slide_w: float) -> float:
    from . import compose
    return compose.MARGIN_X / 100 * slide_w


def package_stage(pkg: StoryPackage) -> tuple[float, float]:
    """Storyline'ın ÇİZDİĞİ sahne. Tek yetkili: shapes.stage_size.

    `package_slide_size` ile KARISTIRILMAMALI: o, ilk slaydin kendi
    koordinat uzayini dondurur ve siralamaya baglidir. Uretilen soru
    slaydi 1920x1080 ilan ederken sahne 720x540'ti; punto matematigi o
    farkin uzerine kuruluyordu (bkz. shapes.Space, K17).
    """
    return shapes.stage_size(pkg)


def package_slide_size(pkg: StoryPackage) -> tuple[float, float]:
    """Bu projenin slayt boyutu. Okunur, varsayilmaz."""
    for part in model.slide_index(pkg):
        try:
            return shapes.slide_size(pkg.parse(part))
        except Exception:
            continue
    return shapes.DEFAULT_SLIDE_SIZE


def _gercek_prova(pkg: StoryPackage, template: str, stem: str,
                  choices: list[str], eyebrow: str | None) -> tuple[bool, str]:
    """Bu şablon BU soruyu gerçekten alır mı? Atılacak bir kopyada dener.

    `_probe` katalog icin ayni seyi JENERIK etiketlerle yapiyor; burasi
    gercek kok ve gercek siklarla. Ikisinin ayrimi `_probe`'un kendi
    docstring'inde yaziyordu ve bu fonksiyon o cumlenin eksik yarisi.

    Diskten okunur (`pkg.path`), yani `pkg` uzerindeki KAYDEDILMEMIS
    degisiklikler burada gorunmez. Bu, `_probe` icin de boyle ve orada
    "katalog icin dogru, yerlestirme icin yanlis" diye kayitli. Kalan risk
    kabul edildi ve DEVIR'de yazili: tema/olcu degistiren kaydedilmemis bir
    duzenleme provayi gercekten ayirabilir.

    `eyebrow` GECILIR. Gecilmezse bant eyebrow yuksekligi kadar genis
    olculur ve prova, gercek cagrinin reddettigi bir sablonu kabul eder --
    olculdu: %59.3 yerine %54.1.
    """
    try:
        probe = StoryPackage(pkg.path)
        add_question(probe, template, stem, choices, [0], eyebrow=eyebrow)
    except StoryError as exc:
        return False, str(exc)[:220]
    except Exception as exc:      # bozuk sablon; secilmemeli
        return False, f"{type(exc).__name__}: {str(exc)[:60]}"
    return True, ""


def pick_template_for_question(pkg: StoryPackage, stem: str, choices: list[str],
                               *, eyebrow: str | None = None,
                               stage: tuple[float, float] | None = None,
                               avoid: list[str] | None = None) -> dict:
    """Cerceveyi olcer, kalan alani bulur, o alana sigan sablonu secer.

    Tek yonlu akisin giris noktasi: cerceve bir kez olculur, kalan alan asagi
    verilir, secim o alanda yapilir. Kalan alan bastan yetersizse hic sablon
    denenmez -- denemek, on aday reddi uretip yanlis teshise goturur.
    """
    from . import compose

    # Projenin kendi slayt boyutu, varsayilan degil. Bu deck 1920x1080 ve
    # 720x540 varsaymak butun yuzde matematigini kaydiriyordu: son sikkin alt
    # kenari %178 cikiyordu, yani slaydin disi. README'nin bastan soyledigi
    # sey -- slayt boyutu okunur, asla varsayilmaz -- burada unutulmustu.
    # BUTUN YUZDE MATEMATIGI SAHNE UZAYINDA (2026-08-17). Once burada
    # `package_slide_size` vardi: ILK SLAYDIN kendi koordinat uzayi, yani
    # siralamaya bagli bir sayi. Uretilen soru slaydi 1920x1080 ilan ederken
    # sahne 720x540'ti ve kok yuksekligi %58.31 hesaplanip diskte %87.1
    # cikiyordu -- carpani 1.495, yani tam olarak (1080/540)/(2.990/1.000)
    # farkinin tersi. Sonucu: son sik %118.7'de, slaydin disinda.
    #
    # Sahne uzayinda olcmek dogru olan, cunku Storyline ORADA ciziyor:
    # slaydin kendi izgarasi sahneye orantili olarak esleniyor, dolayisiyla
    # yuzdeler korunur ama PUNTODAN tureyen yukseklikler korunmaz.
    stage = stage or package_stage(pkg)
    space = shapes.Space(stage[0], stage[1], stage[0], stage[1])
    frame = compose.question_frame(stem, space, eyebrow=eyebrow)
    if frame["starves"]:
        raise StemStarvesFrame(frame["why"])
    # KOK ve EYEBROW ASAGI GECER: son yetki gercek yerlesim ve o ikisi
    # olmadan cerceve baska bir bant olcer.
    result = pick_template(pkg, choices, frame["area_h"], stage=stage, avoid=avoid,
                           stem=stem, eyebrow=eyebrow)
    result["frame"] = frame
    return result


# Sik ovali kapsule ne zaman cevrilir. Kalibrasyon noktasindaki ovallerin
# en genisi 1.6; uretilen kursunki 27.5. Esik bu ikisinin ARASINDA herhangi
# bir yerde ayni sonucu verir -- yani karar esige duyarsiz. 3.0 bir TASARIM
# YARGISI ve oyle isaretlendi; olculen sey 1.6 ile 27.5.
OVAL_BANDI = 3.0
# Korpustaki gercek roundRect'ten OKUNDU, uydurulmadi (gradOvrlyFill dersi).
OVAL_RADIUS = "0.16666667"


def _etiketi_gorunur_yap(root, choice_guids) -> int:
    """Şık etiketini `Normal` durumunda da görünür kılar. Görsel varsa dokunmaz.

    Doner: uyarlanan sik sayisi. 0 = ya gorsel var, ya zaten gorunur.
    """
    # GORSEL OLCUTU: slaytta <pic> var mi. Varsa tohum sicak nokta olarak
    # kullaniliyor demektir ve etiket gorunmemeli.
    if any(el.tag == "pic" for el in (root.find("shapeLst") or [])):
        return 0
    by = {el.get("g"): el for el in root.iter() if el.get("g")}
    uyarlanan = 0
    for guid in choice_guids:
        shape = by.get(guid)
        if shape is None:
            continue
        durumlar = {(st.get("name") or "").lower(): st for st in shape.iter("state")}
        normal, secili = durumlar.get("normal"), durumlar.get("selected")
        if normal is None or secili is None:
            continue
        n_lst, s_lst = normal.find("shapeLst"), secili.find("shapeLst")
        if n_lst is None or s_lst is None:
            continue
        if any(c.tag == "textBox" for c in n_lst):
            continue                      # zaten gorunur
        kaynak = next((c for c in s_lst if c.tag == "textBox"), None)
        if kaynak is None:
            continue
        n_lst.append(shapes.clone_shape(kaynak, name="Etiket"))
        uyarlanan += 1
    return uyarlanan


def _ovali_kapsullestir(root, choice_guids) -> int:
    """Liste satirina gerilmis elipsi kapsule cevirir. Gorsel varsa dokunmaz.

    OLCULEN KUSUR (2026-08-19): uyarlanan coktan-secmeli slaytta siklar
    `<oval>` ve 1612.8x58.7 -- en/boy 27.5. Bir elips o orana gerilince
    MERCEK olur; ekranda gorulen bozuk siluet buydu.

    KALIBRASYON BANDI: elle yapilmis kursta hicbir oval 1.6'yi asmiyor
    (olculen: 0.6, 1.1, 1.6). Orada ovaller bir fotografin ustunde duran
    neredeyse dairesel lekeler ve dogrudur. Bant HEDEF degil REFERANS.

    "En/boy 27.5 kusurdur" TEK BASINA yanlisti: ayni kursta en/boy 48.2'ye
    kadar giden 65 kutu var, hepsi `textBox` -- gorunur silueti olmayan bir
    satir yazi. Karsilastirma SINIF ICINDE yapilir.

    KAREYLE OLCULDU (tools/goz_kapsul.py, karar kurali kareye bakilmadan
    yazildi). Uc sekil, ayni oranda:
        A  dokunulmamis <oval>                 -> MERCEK  (negatif kontrol)
        B  prstGeom roundRect, tag oval        -> BAR
        C  tag da roundRect                    -> B ile AYNI
    Yani cizimi belirleyen `prstGeom`, tag DEGIL. Tag'e dokunulmuyor:
    etkilesim GUID'leri, tetikler ve durum govdeleri oldugu gibi kaliyor.

    UC prstGeom VAR, biri degil: taban + durum govdeleri. shapeLst
    seviyesinde yazan bir duzeltme ikisini kacirir (K22). `shape.iter()`
    hepsini gezer.

    Doner: uyarlanan sik sayisi.
    """
    if any(el.tag == "pic" for el in (root.find("shapeLst") or [])):
        return 0
    by = {el.get("g"): el for el in root.iter() if el.get("g")}
    uyarlanan = 0
    for guid in choice_guids:
        shape = by.get(guid)
        if shape is None or shape.tag != "oval":
            continue
        kutu = shapes.shape_rect(shape)
        if not kutu:
            continue
        w, h = kutu[2] - kutu[0], kutu[3] - kutu[1]
        if h <= 0 or w / h <= OVAL_BANDI:
            continue                      # kalibrasyon bandi icinde: dokunma
        degisen = 0
        for g in shape.iter("prstGeom"):
            for c in list(g):
                if c.tag != "oval":
                    continue
                g.remove(c)
                ET.SubElement(g, "roundRect",
                              {"vertexSet": "false", "radius": OVAL_RADIUS})
                degisen += 1
        if degisen:
            uyarlanan += 1
    return uyarlanan


def _seed_submit_trigger(tag: str) -> ET.Element | None:
    """Gomulu tohumlardan bir GONDER tetikleyicisi getirir (kopya).

    Elle yazilmiyor, KOPYALANIYOR -- bu projenin kurali: Storyline'in kendi
    yazdigi bir govdeyi al, guid'lerini yenile. Tohumlarin dokuzunun
    dokuzunda bu tetikleyici var ve hepsi ayni bicimde.

    Ayni etkilesim ailesinden olani tercih edilir; yoksa herhangi biri, cunku
    tetikleyicinin govdesi aileye gore degismiyor -- degisen tek sey
    baglandigi `submitG`.
    """
    adaylar = []
    for yol_listesi in question_seeds().values():
        adaylar.extend(yol_listesi)
    # Ailesi eslesenler basa
    adaylar.sort(key=lambda p: (tag.lower() not in p.name.lower(), p.name))
    for yol in adaylar:
        try:
            kok = ET.fromstring(yol.read_text(encoding="utf-8"))
        except (OSError, ET.ParseError):
            continue
        for trig in kok.iter("trig"):
            data = trig.find("data")
            if data is not None and data.get("action") == "submitInteraction":
                return _copy.deepcopy(trig)
    return None


def ensure_submit_trigger(pkg: StoryPackage, part: str) -> dict:
    """Slaytta CALISIR bir gonder tetikleyicisi olmasini garanti eder.

    PUANLAMA ZINCIRININ BIRINCI HALKASI, ve register_question'in belge
    dizesindeki "bir slayda freePickOneIntr koymak soruyu CEVAPLANABILIR
    yapar" cumlesi onsuz DOGRU DEGIL: gonder tetikleyicisi yoksa oynaticinin
    Submit dugmesinin ateslecegi hicbir sey yoktur. Ogrenci cevabini isaretler,
    tusa basar, hicbir sey olmaz.

    OLCULDU (2026-09-05, kullanici bildirdi ve iki ayri sebep cikti):

      1. TOHUM YOLU. Dokuz tohumun dokuzunda gonder tetikleyicisi VAR, ama
         hepsi cozulmeyen bir `actionG` tasiyor ve eski supurge onu yetimlik
         kaniti sayip tetikleyiciyi siliyordu. (Supurgenin olcutu degisti.)

      2. SABLON YOLU -- ve uretimde ISIRAN bu. add_question, projede soru
         slaydi varsa gomulu tohumu DEGIL o slaydi klonluyor; taban paketin
         (test/bos.story) alti soru slaydinin ALTISINDA da gonder
         tetikleyicisi yok. O yolda adapt_seeded_slide hic kosmuyor, yani
         onarim adimi da kosmuyor. Yalnizca supurgeyi duzeltmek uretimde
         HICBIR SEYI cozmezdi.

    Iki durum, tek sozlesme:
      * tetikleyici varsa `submitG` bu slaydin etkilesimine ONARILIR
      * yoksa tohumdan KLONLANIR (elle yazilmaz)

    `copiedG` slaydin kendi guid'i olur: dokuz tohumun altisinda o alan
    `sld`'yi, ucunde gonder butonunu gosteriyor. Tetikleyici slaydin
    trigLst'inde yasadigi icin slayt dogru olan.

    Olu `actionG` OLDUGU GIBI birakilir. Tohumlar Storyline'in kendi
    ciktisi ve o alan onlarda da cozulmuyor; temizlemek olculmemis bir
    degisiklik olurdu ve supurge artik ona bakmiyor.
    """
    root = pkg.parse(part)
    tag, intr = _find_interaction(root)
    if intr is None:
        return {"submit": "etkilesim yok", "added": 0, "repaired": 0}
    hedef = intr.get("g") or ""

    mevcut = []
    for owner in root.iter():
        trig_list = owner.find("trigLst")
        if trig_list is None:
            continue
        for trig in trig_list:
            data = trig.find("data")
            if data is not None and data.get("action") == "submitInteraction":
                mevcut.append(trig)

    if mevcut:
        onarilan = 0
        for trig in mevcut:
            for el in trig.iter():
                if el.get("submitG") is not None and el.get("submitG") != hedef:
                    el.set("submitG", hedef)
                    onarilan += 1
        if onarilan:
            pkg.replace_xml(part, root)
        return {"submit": "vardi", "added": 0, "repaired": onarilan}

    trig = _seed_submit_trigger(tag)
    if trig is None:
        # Sessiz gecmez: gonderilemeyen bir soru, cevaplanamayan bir sorudur.
        return {"submit": "tohumda gonder tetikleyicisi bulunamadi",
                "added": 0, "repaired": 0}

    trig.set("g", clone.new_guid())
    trig.set("verG", clone.new_guid())
    trig.set("copiedG", root.get("g") or "")
    for el in trig.iter():
        if el.get("submitG") is not None:
            el.set("submitG", hedef)

    trig_list = root.find("trigLst")
    if trig_list is None:
        trig_list = ET.Element("trigLst")
        shapes.insert_in_order(root, trig_list)
    trig_list.append(trig)
    pkg.replace_xml(part, root)
    return {"submit": "eklendi", "added": 1, "repaired": 0}


def register_question(pkg: StoryPackage, slide_guid: str) -> dict:
    """Soruyu quiz'e kaydet -- yoksa cevap alinir, skor gitmez.

    PUANLAMA BIR ZINCIR ve bu onun ikinci halkasi. Bir slayda
    freePickOneIntr koymak soruyu CEVAPLANABILIR yapar; onu LMS'e
    BILDIRILEBILIR yapan sey, guid'inin quizMgr/quizLst/quiz/questionIdLst
    icinde durmasidir. Ikisi bagimsiz ve ikincisi bu kod tabaninda hic
    yazilmiyordu: `questionIdLst` kaynakta bir kez bile gecmiyordu.

    Sonucu olculdu. Uretilen bir kursta bes slayt da soru tasiyor, sonuc
    slaydi da yerinde, ve questionIdLst BOS -- ogrenci cevapliyor, sayfa
    dogru/yanlis diyor, skor hicbir yere gitmiyor. Hicbir yapisal kontrol
    bagirmiyordu, cunku dosya gecerli ve slayt aciliyor.

    Dogru bicim tahmin edilmedi, gercek bir kurstan okundu
    (test/0_duz_kopya.story): 11 sorunun 11'i kayitli, guid ONITELIKTE
    DEGIL <item> METNINDE duruyor, ve story duzeyindeki lmsResultSlideG
    quiz'in kendi resultSldG'siyle AYNI slayda isaret ediyor.
    """
    # BIRINCI HALKA ONCE, ve her erken donusten ONCE. Gonder tetikleyicisi
    # quiz kaydindan BAGIMSIZ: quizMgr olmayan bir pakette bile ogrencinin
    # cevabini gonderebilmesi gerekir. Asagidaki iki erken donusun arkasina
    # konsaydi, tam da o paketlerde sessizce atlanirdi.
    gonder = {"submit": "slayt bulunamadi", "added": 0, "repaired": 0}
    katman_temizligi: list[str] = []
    part = next((p for p, r in model.slide_index(pkg).items()
                 if r.guid == slide_guid), None)
    if part is not None:
        gonder = ensure_submit_trigger(pkg, part)
        # KATMAN TEMIZLIGI DE BURADA, ayni gerekceyle: iki soru yolu var
        # (klon ve gomulu tohum) ve ikisi de buradan geciyor. Tohum yolunda
        # adapt_seeded_slide zaten temizledi; ikinci kosu ZARARSIZ cunku
        # islem etkisiz-tekrarlanabilir (group gittiyse kural kendiliginden
        # kapanir). Klon yolunda ise TEK temizlik burasi.
        _kok = pkg.parse(part)
        _sil, katman_temizligi = _temizle_donor_katmanlari(
            _kok, {v["name"] for v in model.variables(pkg)})
        if katman_temizligi:
            pkg.replace_xml(part, _kok)

    story = pkg.parse(STORY_PART)
    manager = story.find("quizMgr")
    if manager is None:
        return {"registered": False, "why": "quizMgr yok", "gonder": gonder,
                "katman_temizligi": katman_temizligi}
    quiz = next(iter(story.iter("quiz")), None)
    if quiz is None:
        return {"registered": False, "why": "quizLst icinde quiz yok",
                "gonder": gonder,
                "katman_temizligi": katman_temizligi}

    id_list = quiz.find("questionIdLst")
    if id_list is None:
        # Sira onemli: gercek kursta quiz'in cocuklari questionIdLst, dataLst.
        id_list = ET.Element("questionIdLst")
        quiz.insert(0, id_list)
    if any((el.text or "").strip() == slide_guid for el in id_list):
        return {"registered": True, "why": "zaten kayitli", "gonder": gonder,
                "katman_temizligi": katman_temizligi}
    item = ET.SubElement(id_list, "item")
    item.text = slide_guid

    # Ucuncu halka: LMS'e hangi sonuc slaydinin bildirilecegi. Bos birakilirsa
    # kayitli sorular bile bir yere raporlanmaz. Deger icat EDILMIYOR: quiz
    # kendi sonuc slaydini zaten biliyor ve gercek kursta ikisi ayni guid.
    lms = manager.get("lmsResultSlideG") or ""
    target = quiz.get("resultSldG") or ""
    changed_tracking = False
    if (not lms or lms.startswith("00000000")) and target and \
            not target.startswith("00000000"):
        manager.set("lmsResultSlideG", target)
        manager.set("trackMode", "result")
        changed_tracking = True

    pkg.replace_xml(STORY_PART, story)
    return {"registered": True, "why": "kaydedildi",
            "lms_tracking_set": changed_tracking, "gonder": gonder,
            "katman_temizligi": katman_temizligi}


def add_question(
    pkg: StoryPackage,
    template: str | None,
    prompt: str,
    choices: list[str],
    correct: list[int],
    *,
    scene: str | None = None,
    name: str | None = None,
    points: int | None = None,
    eyebrow: str | None = None,
    palette: dict | None = None,
    feedback: dict | None = None,
    style: str | None = None,
    variant: str | None = None,
    avoid_variant: "list[str] | None" = None,
) -> dict:
    """Create a question slide and write a new question into it.

    template names a slide to clone. Passing None picks whatever matches the
    number of choices -- a slide already in the project, or a bundled seed.
    correct: zero-based indexes of the correct options.
    eyebrow / palette: yalnizca GOMULU tohum yolunda kullanilir. Tohum baska
        bir kurstan hasat edildi ve o kursun bolum adini, degiskenini ve
        rengini tasiyor; ikisi verilmezse o izler slaytta kalir.
    """
    # KOK VE SECENEK METNI BURADA NORMALLESTIRILIR -- iki dalin da ONUNDE,
    # cunku ikisi de ayni kusuru uretebilir.
    #
    # Olculdu 2026-08-28: uretilen bir kursta bir secenek metni sondaki satir
    # sonuyla yazildi (sondaki satir sonu korunmus) ve slaytta fazladan bos
    # satir birakiyor. Bunu prompt'a "newline koyma" diye yazmak kurali her
    # cagiranin hatirlamasina birakir; iki uretici (agent ve builder) var ve
    # biri unutur. Burada bir kez temizlenince hicbir cagiran bozamaz.
    #
    # Bosluk dizisini tek boslugua indirmek ayrica genislik hesabini korur:
    # grow_to_fit ve fit_choices etiketi TEK SATIR sayar.
    prompt = " ".join(prompt.split())
    choices = [" ".join(c.split()) for c in choices]

    if template is None:
        template = _pick_template(pkg, len(choices))

    if template.startswith("bundled:"):
        return _question_from_seed(
            pkg, template, prompt, choices, correct,
            scene=scene, name=name, points=points,
            eyebrow=eyebrow, palette=palette, feedback=feedback,
            style=style, variant=variant, avoid_variant=avoid_variant,
        )

    template_part = pkg.slide_part_for(template)
    tag, intr = _find_interaction(pkg.parse(template_part))
    if intr is None:
        raise StoryError(f"{template} bir soru slaydi degil; sablon olarak kullanilamaz.")
    if tag == "dragDropIntr":
        raise StoryError(
            "Surukle-birak sablonlari desteklenmiyor: dogruluk esletirmede tutulur "
            "ve birakma hedefleri de klonlanmali."
        )

    expected = len(_choice_shape_guids(intr))
    if len(choices) != expected:
        raise StoryError(
            f"{template} sablonu {expected} secenek tasiyor, {len(choices)} verildi. "
            f"list_templates ile uygun secenek sayisina sahip bir sablon secin."
        )
    if not correct or any(i < 0 or i >= expected for i in correct):
        raise StoryError(f"correct degerleri 0..{expected - 1} araliginda olmali.")
    if tag == "freePickOneIntr" and len(correct) != 1:
        raise StoryError("Tek secimli soruda tam olarak bir dogru cevap olmali.")

    result = clone_slide(pkg, template, scene=scene, name=name or prompt[:60])

    root = pkg.parse(result["part"])
    _tag, new_intr = _find_interaction(root)
    choice_guids = _choice_shape_guids(new_intr)

    stem_guid = _stem_shape_guid(root, choice_guids)
    if stem_guid and not set_shape_text(root, stem_guid, prompt):
        raise StoryError("Soru koku yazilamadi.")

    for guid, text in zip(choice_guids, choices):
        if not set_shape_text(root, guid, text):
            raise StoryError(f"Secenek metni yazilamadi: {text!r}")

    # SICAK NOKTA TOHUMUNU METIN LISTESINE UYARLA (2026-08-19).
    #
    # OLCULDU, ve teshis ilk okumadan farkli cikti. Uretilen coktan-secmeli
    # sorularda ogrenci BES BOS KAPSUL goruyordu; etiket ancak tiklayinca
    # beliriyordu. Ilk okuma "etiket yanlis durumda" idi. Dogrusu:
    #
    #     Normal   shapeLst = [oval]
    #     Selected shapeLst = [oval, textBox]   <- etiket BURADA
    #
    # Yani tohum bir SICAK NOKTA etkilesimi: elle yapilmis kursun "bu odada
    # bes risk var, uzerine tikla" slaydindan hasat edilmis. Orada etiketin
    # gorunmemesi DOGRU tasarim -- ovaller bir fotografin uzerinde duruyor.
    #
    # Katalogda tek coktan-secmeli tohum var ve o bu (olculdu: 7 tane
    # freePickOneIntr'e karsi 1 tane freePickManyIntr). Yani metin listesi
    # alternatifi YOK.
    #
    # KOSULLU: gorsel varsa dokunulmaz. Gorsel yoksa tohumun sicak-nokta
    # semantigi ZATEN gecersiz -- tiklanacak bir resim yok -- ve etiket
    # gorunur olmali. Boylece tohumun sicak nokta olarak kullanimi bozulmaz.
    #
    # DUGUM UYDURULMUYOR, Selected'taki GERCEK textBox kopyalaniyor. Bu
    # oturumda sifirdan XML kurmak bir turu goturdu (gradOvrlyFill: Storyline
    # dosyayi hic acmadi), ve README'nin kurali zaten bu: sekli uydurma,
    # projeden kopyala.


    correct_set = set(correct)
    choice_els = list(new_intr.find("choices"))
    for i, choice_el in enumerate(choice_els):
        scoring = choice_el.find("scoringData")
        if scoring is not None:
            scoring.set("correct", "true" if i in correct_set else "false")

    if points is not None:
        props = new_intr.find("intrProps")
        if props is not None:
            props.set("corPts", str(points))

    pkg.replace_xml(result["part"], root)
    # Iki soru yolu var (klon ve gomulu tohum) ve kayit IKISINDE de olmali.
    # Yalnizca birine baglanan bir duzeltme, sablonun nereden geldigine gore
    # bazen calisip bazen calismayan bir kurs uretirdi -- ve iki yol da gecerli
    # dosya urettigi icin hicbir sey bagirmazdi.
    registration = register_question(pkg, root.get("g", ""))
    return {
        **result,
        "question_type": tag,
        "prompt": prompt,
        "registration": registration,
        "choices": [
            {"text": t, "correct": i in correct_set} for i, t in enumerate(choices)
        ],
    }


# Shapes whose text is a control label, not slide copy. Overwriting a button
# caption with a slide title silently breaks that slide's navigation.
LABEL_SHAPES = {"btn", "rsltBtn", "feedBackBtn", "textEntry"}


# ---------------------------------------------------------- surukle-birak
#
# ARITE BURADA BAGLAYICI DEGIL, ve modul basligindaki gerekce bunu kapsamiyor:
# orada "sik eklemek yoktan sekil/durum/tetikleyici uretmek demektir" yaziyor.
# Surukle-birakta oyle degil -- tohum ZATEN dokuz suruklenen ve uc kutu
# tasiyor, ve onuncu suruklenen YOKTAN degil, dokuzuncunun KOPYASINDAN
# turuyor. Durumlar (Normal / Drop Correct / Drop Incorrect) kopyayla
# geliyor, tetikleyici zaten yok (olculdu: 9 ogenin 9'unda da trigLst bos;
# surukle-birak mantigi <choices> kayitlarinda durur, sekillerde degil).
#
# Yani gruplama sorusunda kisit "kac oge" degil, "etiketler hucreye siğiyor
# mu" -- ve o soruyu compose_drag_frame olcup gerekcesiyle cevapliyor.


def _fit_shape_pool(shape_list, by_guid: dict, guids: list[str], want: int, *,
                    name: str) -> list[str]:
    """Sekil havuzunu istenen sayiya getirir: fazlasi silinir, eksigi klonlanir.

    Klon KAYNAGI havuzun ilk uyesi, donor ya da gomulu tohum degil: slaydin
    kendi mobilyasi. Ayni gerekce `shapes.find_seed`'in "once proje" kurali
    -- bir kurs zaten bir surukleme kutusu tasiyorsa onuncu de aynisi olmali.
    """
    guids = [g for g in guids if g in by_guid]
    if not guids:
        raise StoryError("Tohumda kopyalanacak sekil yok.")
    while len(guids) > want:
        gone = guids.pop()
        shape = by_guid.pop(gone, None)
        if shape is not None:
            shape_list.remove(shape)
    while len(guids) < want:
        source = by_guid[guids[-1]]
        made = shapes.clone_shape(source, name=name)
        shape_list.insert(list(shape_list).index(source) + 1, made)
        by_guid[made.get("g")] = made
        guids.append(made.get("g") or "")
    return guids


def _write_drag_question(pkg: StoryPackage, part: str, prompt: str,
                         groups: "dict[str, list[str]]",
                         points: int | None) -> dict:
    """Gruplama sorusunu slayda yazar: kok, suruklenenler, kutular, eslesme.

    DOGRULUK `scoringData`'DA DEGIL. Pick ailesinde dogru sik
    `scoringData correct="true"` ile isaretlenir; surukle-birakta oyle bir
    isaret YOK -- dogru cevap `matchShpG`'nin ta kendisi, yani "bu oge bu
    kutuya gider". Olculdu, elle yapilmis kursta 9 kaydin 9'unda da
    correct="false" ve soru dogru puanlaniyor. Buraya correct="true" yazmak,
    modelin `_describe_choice` uyarisinin ("her suruklenebilirl'i yanlis
    etiketlemek") ters yonu olurdu: hepsini dogru etiketlemek.
    """
    root = pkg.parse(part)
    tag, intr = _find_interaction(root)
    if tag != "dragDropIntr" or intr is None:
        raise StoryError(f"Bu slayt bir surukle-birak slaydi degil: {tag!r}")
    shape_list = root.find("shapeLst")
    by_guid = {s.get("g"): s for s in shape_list if s.get("g")}

    labels = list(groups)
    flat = [(index, text) for index, label in enumerate(labels)
            for text in groups[label]]
    if not flat:
        raise StoryError("Hicbir kutuya oge verilmedi.")

    items = _fit_shape_pool(shape_list, by_guid, _choice_shape_guids(intr),
                            len(flat), name="Suruklenen")
    zones = _fit_shape_pool(shape_list, by_guid, _drop_target_guids(intr),
                            len(labels), name="Birakma Kutusu")

    choices = intr.find("choices")
    kalip = _copy.deepcopy(list(choices)[0])
    for old in list(choices):
        choices.remove(old)
    for (zone_index, _text), item_guid in zip(flat, items):
        record = _copy.deepcopy(kalip)
        record.set("g", clone.new_guid())
        record.set("verG", clone.new_guid())
        record.set("shpG", item_guid)
        record.set("matchShpG", zones[zone_index])
        scoring = record.find("scoringData")
        if scoring is not None:
            scoring.set("correct", "false")
            scoring.set("pts", "0")
        choices.append(record)

    stem = _stem_shape_guid(root, items + zones)
    if stem:
        set_shape_text(root, stem, prompt)
    for item_guid, (_zone, text) in zip(items, flat):
        set_shape_text(root, item_guid, text)
    for zone_guid, label in zip(zones, labels):
        set_shape_text(root, zone_guid, label)

    if points is not None:
        props = intr.find("intrProps")
        if props is not None:
            props.set("corPts", str(points))
    pkg.replace_xml(part, root)
    return {"items": len(items), "zones": len(zones), "stem": stem}


def add_drag_question(
    pkg: StoryPackage,
    prompt: str,
    groups: "dict[str, list[str]]",
    *,
    scene: str | None = None,
    name: str | None = None,
    points: int | None = None,
    eyebrow: str | None = None,
    palette: dict | None = None,
    feedback: dict | None = None,
    look: int = 0,
    style: str | None = None,
) -> dict:
    """Gruplama sorusu: ogeler yukarida, kutular asagida, dogru cevap eslesme."""
    seeds = question_seeds().get(("dragDropIntr", 9)) or []
    if not seeds:
        raise StoryError(
            "Gomulu surukle-birak tohumu yok "
            "(seeds/question_dragDropIntr_9.xml bekleniyor).")
    seed = seeds[look % len(seeds)]
    result = clone.install_slide(pkg, seed.read_text(encoding="utf-8"),
                                 scene=scene, name=name or prompt[:60])
    written = _write_drag_question(pkg, result["part"], prompt, groups, points)
    adapted = adapt_seeded_slide(pkg, result["part"], eyebrow=eyebrow,
                                 palette=palette, feedback=feedback,
                                 style=style)
    registration = register_question(
        pkg, pkg.parse(result["part"]).get("g", ""))
    return {**result, "question_type": "dragDropIntr", "prompt": prompt,
            "adapted": adapted, "registration": registration,
            "framed": bool(adapted.get("framed")),
            "groups": {label: list(texts) for label, texts in groups.items()},
            **written}


# ------------------------------------------------------------- metin girisi
#
# IKI KIP, VE AYRIM PUANDA DEGIL ANATOMIDE.
#
#   accept verilir  -> PUANLI. `freeTextEntryIntr` durur, kabul edilen
#                      cevap(lar) <choices><intrFreeChoice><text> icine
#                      yazilir, slayt quiz'e kaydedilir.
#   accept verilmez -> TAAHHUT. Etkilesim ogesi SILINIR ve geriye degiskene
#                      bagli bir yazma kutusu kalir. Slayt puanlanan bir
#                      soru degil, icine yazilan bir icerik slaydi olur.
#
# Ikinci kipin etkilesimi silmesi kasitli. "Puani sifira cek" denendiginde
# geriye hala DOGRU CEVABI OLAN bir soru kalir: kabul listesi bos oldugu
# icin ogrenci ne yazarsa yazsin yanlis geri bildirimini gorur. Puan sifir
# olsa bile ekranda "Yanlis" yazar -- ve taahhut slaydinda yanlis cevap YOK.
#
# DOGRULUK BURADA DA scoringData'DA DEGIL. Olculdu: elle yapilmis fixture'da
# kabul edilen cevap <text>sabun</text> iken ayni kaydin scoringData'si
# correct="false". Surukle-birakin aynisi -- pick ailesinin disina
# cikildiginda `correct` bayragi cevabi TASIMIYOR.


def _unique_variable_name(pkg: StoryPackage, base: str) -> str:
    """Cakismayan bir degisken adi. add_variable ayni adda ikinciyi reddeder."""
    try:
        used = {(v.get("name") or "").casefold()
                for v in (pkg.parse(STORY_PART).find("varLst") or [])}
    except Exception:
        used = set()
    if base.casefold() not in used:
        return base
    index = 2
    while f"{base}{index}".casefold() in used:
        index += 1
    return f"{base}{index}"


def _bind_text_entry(pkg: StoryPackage, part: str, base_name: str) -> dict:
    """Yazma kutusunu BU projedeki bir degiskene baglar.

    Tohumun tetikleyicisi kendi kursundaki degiskeni isaret ediyor (olculdu:
    varG=163dc4e1..., yani deneme.story'nin TextEntry1'i). O guid bu projede
    yok, dolayisiyla `_drop_dangling_triggers` tetikleyiciyi HAKLI OLARAK
    silerdi ve geriye hicbir yere yazmayan bir kutu kalirdi: ogrenci yaziyor,
    yazdigi kayboluyor, hicbir kontrol bagirmiyor. O yuzden baglama
    supurgeden ONCE kosar.
    """
    from . import logic
    name = _unique_variable_name(pkg, base_name)
    made = logic.add_variable(pkg, name, kind="text", default="")
    root = pkg.parse(part)
    rewired = 0
    for trig in root.iter("textEntryTrig"):
        for other in trig.iter("other"):
            if other.get("varG"):
                other.set("varG", made["guid"])
                rewired += 1
    pkg.replace_xml(part, root)
    return {"variable": name, "variable_guid": made["guid"], "rewired": rewired}


def _adapt_text_slide(pkg: StoryPackage, part: str, *,
                      eyebrow: str | None, palette: dict | None,
                      feedback: dict | None, graded: bool,
                      style: str | None = None) -> dict:
    """adapt_seeded_slide'in metin girisi karsiligi.

    Ayri yazildi, cunku korunacak anatomi baska: burada SIK YOK. Tutulanlar
    etkilesim (puanli kipte), yazma kutusu ve kok; gerisi -- tohumun kendi
    mobilyasi -- gider. Ortak iki adim (kopuk tetikleyici supurgesi ve zemin)
    paylasilan yardimcilardan gelir, kopyalanmaz.
    """
    from . import compose as _compose

    root = pkg.parse(part)
    shape_list = root.find("shapeLst")
    if shape_list is None:
        return {"removed": [], "kept": 0}
    tag, intr = _find_interaction(root)
    entry = next((sh for sh in shape_list if sh.tag == "textEntry"), None)
    if entry is None:
        return {"removed": [], "kept": 0, "reason": "yazma kutusu yok"}
    entry_guid = entry.get("g") or ""
    stem = _stem_shape_guid(root, [entry_guid])

    removed: list[str] = []
    silinen: set[str] = set()
    for shape in list(shape_list):
        guid = shape.get("g") or ""
        if shape is entry or guid == stem:
            continue
        if shape.tag.endswith("Intr"):
            if graded:
                continue
            removed.append(f"{shape.tag} (taahhut kipi: puanlama yok)")
            silinen |= guids_within(shape)
            shape_list.remove(shape)
            continue
        text = model.shape_text(root, guid).strip() if guid else ""
        removed.append(f"{shape.tag}: {text[:24]!r}" if text else shape.tag)
        silinen |= guids_within(shape)
        shape_list.remove(shape)

    dangling = _drop_dangling_triggers(pkg, root, silinen)
    if dangling:
        removed.append(f"{dangling} kopuk tetikleyici")
    if palette:
        _paint_slide_ground(root, palette.get("bg", "#0E1B3D"))
    pkg.replace_xml(part, root)

    laid = _compose.compose_text_frame(
        pkg, part, eyebrow=eyebrow, palette=palette,
        stem_guid=stem, entry_guid=entry_guid, style=style)
    layers: dict = {}
    if graded:
        layers = _compose.compose_feedback_layers(pkg, part, palette=palette,
                                                  feedback=feedback)
    if palette:
        _recolour_for_palette(pkg, part, palette, stem=stem,
                              choices={entry_guid}, eyebrow=None)
    kept = 2 + (1 if graded and intr is not None else 0)
    return {"removed": removed, "kept": kept, **laid, **layers}


def add_text_question(
    pkg: StoryPackage,
    prompt: str,
    accept: "list[str] | None" = None,
    *,
    scene: str | None = None,
    name: str | None = None,
    points: int | None = None,
    eyebrow: str | None = None,
    palette: dict | None = None,
    feedback: dict | None = None,
    variable: str | None = None,
    style: str | None = None,
) -> dict:
    """Ogrencinin YAZDIGI slayt. accept verilirse puanli, verilmezse taahhut."""
    seeds = question_seeds().get(("freeTextEntryIntr", 1)) or []
    if not seeds:
        raise StoryError(
            "Gomulu metin girisi tohumu yok "
            "(seeds/question_freeTextEntryIntr_1.xml bekleniyor).")
    graded = bool(accept)
    result = clone.install_slide(pkg, seeds[0].read_text(encoding="utf-8"),
                                 scene=scene, name=name or prompt[:60])
    part = result["part"]
    bound = _bind_text_entry(pkg, part, variable or "Yanit")

    root = pkg.parse(part)
    _tag, intr = _find_interaction(root)
    entry = next((sh for sh in root.find("shapeLst") if sh.tag == "textEntry"), None)
    stem = _stem_shape_guid(root, [entry.get("g") or ""] if entry is not None else [])
    if stem:
        set_shape_text(root, stem, prompt)
    # KUTUNUN ICI BOSALTILIR. Tohumun kutusunda "cevap?" yaziyordu ve
    # temizlenmezse ogrenci onu SILEREK yazmaya basliyor -- ustelik yazi
    # tohumun kendi kursundan gelen bir iz, yani `adapt_seeded_slide`'in
    # bastan sona ugrastigi seyin metin girisi tarafindaki karsiligi.
    # Cizime bakilinca gorundu; hicbir yapisal kontrol bagirmiyordu.
    if entry is not None:
        set_shape_text(root, entry.get("g") or "", "")
    if intr is not None:
        choices = intr.find("choices")
        kalip = _copy.deepcopy(list(choices)[0])
        for old in list(choices):
            choices.remove(old)
        for answer in (accept or []):
            record = _copy.deepcopy(kalip)
            record.set("g", clone.new_guid())
            record.set("verG", clone.new_guid())
            node = record.find("text")
            if node is not None:
                node.text = answer
            choices.append(record)
        if points is not None:
            props = intr.find("intrProps")
            if props is not None:
                props.set("corPts", str(points))
    pkg.replace_xml(part, root)

    adapted = _adapt_text_slide(pkg, part, eyebrow=eyebrow, palette=palette,
                                feedback=feedback, graded=graded, style=style)
    registration = None
    if graded:
        registration = register_question(pkg, pkg.parse(part).get("g", ""))
    return {**result,
            "question_type": "freeTextEntryIntr" if graded else "taahhut",
            "prompt": prompt, "accept": list(accept or []), "graded": graded,
            "adapted": adapted, "registration": registration,
            "framed": bool(adapted.get("framed")), **bound}


def add_hotspot_question(
    pkg: StoryPackage,
    prompt: str,
    *,
    scene: str | None = None,
    name: str | None = None,
    points: int | None = None,
    eyebrow: str | None = None,
    palette: dict | None = None,
    feedback: dict | None = None,
    style: str | None = None,
) -> dict:
    """Sıcak nokta (Hotspot) sorusu: ekrandaki doğru bölgeye tıklama sorusu."""
    seeds = question_seeds().get(("freeHotSpotIntr", 1)) or []
    if not seeds:
        fallback = clone.SEED_DIR / "question_freeHotSpotIntr_1.xml"
        if fallback.is_file():
            seeds = [fallback]
        else:
            raise StoryError("Gömülü sıcak nokta tohumu bulunamadı.")
    seed = seeds[0]
    result = clone.install_slide(pkg, seed.read_text(encoding="utf-8"),
                                 scene=scene, name=name or prompt[:60])
    part = result["part"]
    root = pkg.parse(part)
    _tag, intr = _find_interaction(root)
    stem = _stem_shape_guid(root, [])
    if stem:
        set_shape_text(root, stem, prompt)
    if intr is not None and points is not None:
        props = intr.find("intrProps")
        if props is not None:
            props.set("corPts", str(points))
    pkg.replace_xml(part, root)

    adapted = adapt_seeded_slide(pkg, part, eyebrow=eyebrow, palette=palette,
                                 feedback=feedback, style=style)
    registration = register_question(pkg, pkg.parse(part).get("g", ""))
    return {**result, "question_type": "freeHotSpotIntr", "prompt": prompt,
            "adapted": adapted, "registration": registration,
            "framed": bool(adapted.get("framed"))}


def _title_shape(root: ET.Element) -> str | None:
    """Pick the shape a slide title belongs in: a real text box, not a button."""
    best, best_len = None, -1
    fallback, fallback_len = None, -1
    for shape, _t, doc, _s in model._iter_text_shapes(root):
        guid = shape.get("g", "")
        length = len(model._doc_text(doc).strip())
        if shape.tag not in LABEL_SHAPES and length > best_len:
            best, best_len = guid, length
        if length > fallback_len:
            fallback, fallback_len = guid, length
    return best or fallback


# ------------------------------------------------------- shape composition


def _rect(root: ET.Element, x: float, y: float, w: float, h: float):
    """Percent-of-slide -> absolute coordinates.

    Callers work in percentages because the coordinate space is per-project
    (720x540 in one of this user's decks, 1920x1080 in another), so absolute
    numbers chosen for one course land off-slide in the next.
    """
    width, height = shapes.slide_size(root)
    return (x / 100 * width, y / 100 * height,
            (x + w) / 100 * width, (y + h) / 100 * height)


def _apply_text(root: ET.Element, shape: ET.Element, text: str, **style) -> None:
    guid = shape.get("g", "")
    if text is not None:
        set_shape_text(root, guid, text)
    document = shapes.shape_document(shape)
    if document is not None and any(v is not None for v in style.values()):
        document.text = shapes.set_text_style(document.text or "", **style)


# A bundled text seed carries its source deck's styling -- 8pt in the course it
# was captured from, which renders as a hairline on a title. Project-sourced
# seeds are left alone so new shapes match the deck they join.
BUNDLED_DEFAULT_SIZE = 24


def _seed_for_background(pkg: StoryPackage) -> tuple[ET.Element, str]:
    for tag in BACKGROUND_SEEDS:
        try:
            return shapes.find_seed(pkg, tag)
        except StoryError:
            continue
    raise StoryError(
        "Arka plan icin klonlanabilir bir dikdortgen veya metin kutusu bulunamadi."
    )


def _drop_backgrounds(root) -> list[str]:
    """Slayttaki tam sayfa "Arka Plan" dikdortgenlerini kaldirir.

    Ad + GEOMETRI birlikte aranir: yalnizca ada bakmak, kucuk bir sus
    dikdortgeni ayni adi tasidiginda onu da silerdi; yalnizca geometriye
    bakmak, tam sayfa bir fotograf perdesini ya da yari saydam ortuyu silerdi.
    """
    shape_list = root.find("shapeLst")
    if shape_list is None:
        return []
    slide_w, slide_h = shapes.slide_size(root)
    silinen = []
    for shape in list(shape_list):
        if shape.get("name") != "Arka Plan":
            continue
        loc = shape.find("loc")
        if loc is None:
            continue
        left, top, right, bottom = (float(loc.get(k, 0) or 0)
                                    for k in ("l", "t", "r", "b"))
        if right - left >= slide_w * 0.99 and bottom - top >= slide_h * 0.99:
            shape_list.remove(shape)
            silinen.append(shape.get("g", ""))
    return silinen


def set_background(pkg: StoryPackage, slide: str, color: str) -> dict:
    """Cover the slide with a solid colour, behind everything else.

    Storyline slides here carry backVis="trans" and inherit their background
    from the layout, so a full-bleed rectangle at the back of the z-order is
    both simpler and safer than rewriting layout inheritance.
    """
    part = pkg.slide_part_for(slide)
    root = pkg.parse(part)
    # ONCEKI ZEMIN SILINIR, ALTINA KONMAZ. to_back yeni dikdortgeni en alta
    # koyuyor; slaytta zaten tam sayfa bir "Arka Plan" varsa yenisi ONUN
    # ALTINDA kaliyor ve hic gorunmuyor -- yani ikinci set_background cagrisi
    # sessizce etkisiz kalıyordu. Olculdu 2026-08-29: kullanicinin kapak
    # slaydinda iki tam sayfa zemin ust uste duruyordu (lacivert ve yesil) ve
    # gorunen, sonradan istenen degil ESKISIYDI.
    onceki = _drop_backgrounds(root)
    seed, source = _seed_for_background(pkg)
    shape = shapes.clone_shape(seed, name="Arka Plan")
    shapes.set_shape_slide_size(shape, *shapes.slide_size(root))
    shapes.set_loc(shape, *_rect(root, 0, 0, 100, 100))
    shapes.set_fill(shape, color)
    shapes.add_shape(root, shape, to_back=True)
    _apply_text(root, shape, "")
    pkg.replace_xml(part, root)
    return {
        "slide": slide,
        "color": "#" + shapes.parse_color(color),
        "shape": shape.get("g", ""),
        "replaced": len(onceki),
        "seed": f"{shape.tag} ({source})",
    }


def add_text_box(
    pkg: StoryPackage,
    slide: str,
    text: str,
    *,
    x: float = 10,
    y: float = 40,
    w: float = 80,
    h: float | None = None,
    color: str | None = None,
    size: float | None = None,
    bold: bool | None = None,
    align: str | None = "c",
    font: str | None = None,
    name: str | None = None,
    avoid_overlap: bool = True,
) -> dict:
    """Add a text box. x/y/w are percentages of the slide.

    h is optional: left out, the box is sized to the text so a paragraph is
    not squeezed into a fixed band and clipped.
    """
    part = pkg.slide_part_for(slide)
    root = pkg.parse(part)
    seed, source = shapes.find_seed(pkg, "textBox")
    shape = shapes.clone_shape(seed, name=name or "Metin")
    slide_w, slide_h = shapes.slide_size(root)
    shapes.set_shape_slide_size(shape, slide_w, slide_h)

    if size is None and source == "bundled":
        size = BUNDLED_DEFAULT_SIZE

    left, top, right, _ = _rect(root, x, y, w, h or 10)
    if h is None:
        needed = shapes.layout_text_height(text, size or 18, right - left,
                                           shapes.space_of(root, package_stage(pkg)))
        bottom = min(top + needed, slide_h)
    else:
        bottom = _rect(root, x, y, w, h)[3]

    rect = (left, top, right, bottom)
    placed = True
    if avoid_overlap:
        rect, placed = shapes.avoid_collisions(root, rect)

    shapes.set_loc(shape, *rect)
    shapes.set_text_flow(shape, vertical="t", grow=True)
    shapes.add_shape(root, shape)
    _apply_text(root, shape, text, color=color, size=size, bold=bold, align=align, font=font)
    pkg.replace_xml(part, root)
    return {
        "slide": slide, "text": text, "shape": shape.get("g", ""),
        "seed": f"textBox ({source})", "size": size,
        "box_percent": {
            "x": round(rect[0] / slide_w * 100, 1), "y": round(rect[1] / slide_h * 100, 1),
            "w": round((rect[2] - rect[0]) / slide_w * 100, 1),
            "h": round((rect[3] - rect[1]) / slide_h * 100, 1),
        },
        "height_auto": h is None,
        "placed_without_overlap": placed,
        "label_size": size,
        # `label_overflow` BURADAN KALDIRILDI. add_button'dan kopyalanmisti ve
        # orada tanimli: punto kucultme zincirinin sonunda, sabit yukseklikli
        # bir yuvaya etiket sigmadi mi diye. add_text_box o zinciri hic
        # calistirmiyor ve h verilmezse kutu zaten metne gore buyuyor -- yani
        # ad burada tanimsizdi ve fonksiyon HER cagrida NameError veriyordu.
        #
        # ACIK KALAN, ayri bir is: h VERILDIGINDE metin sigmiyorsa sessizce
        # kirpiliyor ve bunu sayan bir olcu yok. Kaldirilan satir o olcuyu
        # zaten vermiyordu; onu eklemek kapsam genisletmesi.
    }


DECORATIVE_SHAPES = ("rect", "roundRect", "oval", "line", "textBox")


def add_results_slide(
    pkg: StoryPackage, *, scene: str | None = None, name: str = "Sonuclar"
) -> dict:
    """Add a quiz results slide.

    Cloned from a bundled seed, as everything else is. The file opens with it
    in place, in an empty project as much as a full one -- but what it *reports*
    depends on the quiz wiring it inherits, and that cannot be checked without
    publishing. So it is offered as a starting slide, not as verified scoring.
    """
    seed = clone.SEED_DIR / "results.xml"
    if not seed.is_file():
        raise StoryError("Gomulu sonuc slaydi tohumu yok.")
    result = clone.install_slide(
        pkg, seed.read_text(encoding="utf-8"), scene=scene, name=name
    )
    baglanan = _sonuc_degiskenlerini_bagla(pkg, result["part"])
    return {
        **result,
        "score_vars_rebound": baglanan,
        "note": ("Slayt eklendi ve dosya acilir durumda. Puanlama, devraldigi quiz "
                 "baglantilarina bagli; yayinlamadan dogrulanamaz."),
    }


# Tohumun HASAT EDILDIGI projeye ait skor degisken GUID'leri. Bunlar slaydin
# icinde degil story.xml'de yasayan YERLESIK degiskenler, dolayisiyla
# install_slide'in GUID yenilemesi onlara dokunmaz -- tohum yabanci GUID'i
# oldugu gibi taşır ve hedef pakette karsiligi YOKTUR.
#
# OLCULDU 2026-09-04: kurulan sonuc slaydinda iki trigCond'un varG'si pakette
# bulunmuyordu. Sonuc: slayt goruntuleniyor, gectiniz/kaldiniz katmanlarini
# aciracak kosullar HIC dogru donmuyor. Tam olarak projenin "sessizce
# calismayan tetikleyici" sinifi -- dosya acilir, panel tetikleyiciyi
# gosterir, calisma aninda hicbir sey olmaz.
#
# ROLE gore eslesiyor, ada gore degil: iki GUID'in hangi degisken oldugu
# tohumun kendi kosullarindan okundu (dataType="var", skor >= gecme puani).
SONUC_TOHUM_DEGISKENLERI = {
    "903b3800-3db5-4484-bd3c-16161372579b": "Results.ScorePoints",
    "d0d815e0-8c34-48ce-b1f0-8bd2ae7ee506": "Results.PassPoints",
}


def _sonuc_degiskenlerini_bagla(pkg: StoryPackage, part: str) -> list[str]:
    """Tohumun yabanci skor GUID'lerini hedef paketinkilerle degistirir.

    Hedefte degisken yoksa (quiz'i olmayan bir proje) SESSIZ GECILMEZ:
    baglanamayan ad geri dondurulur ve cagiran raporlar.
    """
    hedef = {v["name"]: v["guid"] for v in model.variables(pkg)}
    root = pkg.parse(part)
    baglanan: list[str] = []
    degisti = False
    for cond in root.iter("trigCond"):
        for alan in ("varG", "varG2"):
            ad = SONUC_TOHUM_DEGISKENLERI.get(cond.get(alan) or "")
            if ad and hedef.get(ad):
                cond.set(alan, hedef[ad])
                baglanan.append(ad)
                degisti = True
    if degisti:
        pkg.replace_xml(part, root)
    return sorted(set(baglanan))


def add_decoration(
    pkg: StoryPackage,
    slide: str,
    kind: str = "roundRect",
    *,
    x: float = 10,
    y: float = 30,
    w: float = 30,
    h: float = 15,
    fill: str | None = None,
    text: str | None = None,
    color: str | None = None,
    size: float | None = None,
    align: str = "c",
    name: str | None = None,
    avoid_overlap: bool = False,
) -> dict:
    """Add a plain shape: panel, card, divider, badge.

    These are the pieces a designed slide is actually made of -- a rounded
    panel behind a paragraph, a rule between sections. The deck measured here
    uses 67 rounded rectangles and 10 lines and ovals against 30 plain
    rectangles, so leaving them out left most of a real layout unreachable.
    """
    if kind not in DECORATIVE_SHAPES:
        raise StoryError(
            f"Desteklenmeyen sekil: {kind!r}. Secenekler: {', '.join(DECORATIVE_SHAPES)}"
        )
    part = pkg.slide_part_for(slide)
    root = pkg.parse(part)
    seed, source = shapes.find_seed(pkg, kind)
    shape = shapes.clone_shape(seed, name=name or kind)
    slide_w, slide_h = shapes.slide_size(root)
    shapes.set_shape_slide_size(shape, slide_w, slide_h)

    rect = _rect(root, x, y, w, h)
    placed = True
    if avoid_overlap:
        rect, placed = shapes.avoid_collisions(root, rect)
    shapes.set_loc(shape, *rect)
    if fill:
        shapes.set_fill(shape, fill)
    shapes.add_shape(root, shape)
    if text is not None:
        _apply_text(root, shape, text, color=color, size=size, align=align)
    pkg.replace_xml(part, root)
    return {
        "slide": slide, "kind": kind, "shape": shape.get("g", ""),
        "seed": f"{kind} ({source})", "text": text,
        "fill": ("#" + shapes.parse_color(fill)) if fill else None,
        "box_percent": {"x": x, "y": y, "w": w, "h": h},
        "placed_without_overlap": placed,
    }


def add_button(
    pkg: StoryPackage,
    slide: str,
    text: str,
    *,
    x: float = 74,
    y: float = 84,
    w: float = 20,
    h: float = 10,
    target_slide: str | None = None,
    target_scene: str | None = None,
    closes_layer: bool = False,
    fill: str | None = None,
    color: str | None = None,
    size: float | None = None,
    avoid_overlap: bool = True,
    identity: str | None = None,
    slot: tuple[float, float] | None = None,
) -> dict:
    """Add a clickable button.

    slot: buyumenin izinli oldugu (ust, alt) bant, slayt yuzdesi. Bir yigin
    icindeki butonlar icin ZORUNLU -- yoksa her biri kendi etiketine gore
    buyur ve komsusunun uzerine biner. Olculdu: dort sikli bir yiginda birinci
    ile ikinci, ucuncu ile dorduncu cakisti.

    Where it goes, in order of precedence: a named scene, a named slide, the
    layer it sits on (closes_layer), or simply the next slide.

    identity names the course, and only matters for the very first button in a
    project: it picks which donor the deck borrows its button from. Every
    button after that one finds its predecessor in the project and copies that
    instead, which is what keeps a deck consistent.
    """
    part = pkg.slide_part_for(slide)
    root = pkg.parse(part)

    target_guid = None
    if target_slide:
        index = pkg.slide_part_for(target_slide)
        target_guid = pkg.parse(index).get("g")

    scene_guid = None
    if target_scene:
        story = pkg.parse(STORY_PART)
        found = next((s for s in (story.find("sceneLst") or [])
                      if s.get("name") == target_scene), None)
        if found is None:
            names = [s.get("name") for s in (story.find("sceneLst") or [])]
            raise StoryError(f"Sahne bulunamadi: {target_scene!r}. Mevcut: {names}")
        scene_guid = found.get("g")

    seed, source = shapes.find_seed(pkg, "btn", identity=identity)
    # A donor arrives wired for its own course: an accordion header carries
    # "change the state of that panel", pointing at shapes this project does
    # not contain. Retargeting only rewrites the first trigger and would leave
    # the rest dangling, so the donor's logic is dropped wholesale and a clean
    # click is grafted on. Anatomy from the donor, wiring from the seed.
    from_donor = source.startswith("donor:")
    shape = shapes.clone_shape(seed, name=text[:40] or "Buton",
                               keep_triggers=not from_donor)
    if from_donor:
        donors.ensure_clickable(shape)
    slide_w, slide_h = shapes.slide_size(root)
    shapes.set_shape_slide_size(shape, slide_w, slide_h)
    if scene_guid:
        wired = shapes.retarget_to_scene(shape, scene_guid)
        destination = f"sahne: {target_scene}"
    elif closes_layer:
        wired = shapes.retarget_to_close_layer(shape)
        destination = "katmani kapat"
    else:
        wired = shapes.retarget_click(shape, slide_guid=target_guid)
        destination = target_slide or "(sonraki slayt)"

    rect = _rect(root, x, y, w, h)
    # The box follows the label, not the other way round. Asked for a box that
    # cannot hold the words, the old path drew them outside the shape and no
    # structural check noticed; the donor rehearsal could only guard the one
    # sample label it was given, so anything longer overflowed in silence.
    # Buyume KOMPOZISYONUN bandinda kalir, slaydin kenarinda degil. Slaydin
    # kenarina kadar buyuyen bir buton tabanin altina sarkiyor ve tiklama
    # alani sayfanin disinda kaliyor -- olculdu, uzun etiketli dort butonun
    # dordu %99.7'ye indi ve hicbir kontrol bagirmadi.
    from .compose import CEILING as _CEILING, FLOOR as _FLOOR
    band = ((slot[0] / 100 * slide_h, slot[1] / 100 * slide_h) if slot
            else (_CEILING / 100 * slide_h, _FLOOR / 100 * slide_h))
    size = size or 15
    _uzay = shapes.space_of(root, package_stage(pkg))
    rect = shapes.grow_to_fit(shape, rect, text, size, _uzay, band=band)

    # ZINCIRIN SON HALKASI: kutu buyuyemiyorsa PUNTO kucur.
    #
    # Buyumeyi banda baglamak "slayt disina tasma"yi "kutu disina tasma"ya
    # cevirdi -- olculdu, yedi etiket. Gorunur oldu ama kusur olmaktan
    # cikmadi. Sira sabittir: once kutu buyur, sinira gelince punto kisilir,
    # kalibre bandin (13pt) altina INILMEZ.
    #
    # Tabanda hala sigmiyorsa bu gercek bir "etiket bu yuvaya sigmiyor"
    # durumudur ve donen kayitta label_overflow ile bildirilir; sessizce
    # kirpilmaz.
    from .compose import step_down as _step_down
    floor_pt = shapes.CALIBRATED_RANGE[0]
    box_h = rect[3] - rect[1]
    while size > floor_pt and shapes.height_for_label(
            shape, text, size, rect[2] - rect[0], _uzay) > box_h + 1.0:
        # Merdiven basamagi: "-1" olcek disi punto uretiyordu.
        nxt = _step_down(size, floor_pt)
        if nxt >= size:
            break
        size = nxt
    label_overflow = shapes.height_for_label(
        shape, text, size, rect[2] - rect[0], _uzay) > box_h + 1.0
    placed = True
    if avoid_overlap:
        rect, placed = shapes.avoid_collisions(root, rect)

    shapes.set_loc(shape, *rect)
    if fill:
        shapes.set_fill(shape, fill)
    shapes.add_shape(root, shape)
    # Centred: a label pinned to the left edge of its own button is the kind of
    # thing that reads as unfinished at a glance and never shows up in a
    # geometry check.
    _apply_text(root, shape, text, color=color, size=size, align="c")
    pkg.replace_xml(part, root)
    return {
        "slide": slide,
        "text": text,
        "shape": shape.get("g", ""),
        "seed": f"btn ({source})",
        "target": destination,
        "trigger_wired": wired,
        "box_percent": {
            "x": round(rect[0] / slide_w * 100, 1), "y": round(rect[1] / slide_h * 100, 1),
            "w": round((rect[2] - rect[0]) / slide_w * 100, 1),
            "h": round((rect[3] - rect[1]) / slide_h * 100, 1),
        },
        "placed_without_overlap": placed,
    }


def restyle_slide_text(
    pkg: StoryPackage,
    slide: str,
    *,
    color: str | None = None,
    size: float | None = None,
    bold: bool | None = None,
    font: str | None = None,
    shape: str | None = None,
) -> dict:
    """Restyle text on a slide -- one shape if given, otherwise all of them."""
    part = pkg.slide_part_for(slide)
    root = pkg.parse(part)
    touched = []
    for shp, text_el, _doc, _state in model._iter_text_shapes(root):
        if shape and shp.get("g") != shape:
            continue
        text_el.text = shapes.set_text_style(
            text_el.text or "", color=color, size=size, bold=bold, font=font
        )
        touched.append(shp.get("g", ""))
    if not touched:
        raise StoryError(f"{slide} icinde bicimlenecek metin bulunamadi.")
    pkg.replace_xml(part, root)
    return {"slide": slide, "shapes_restyled": len(touched),
            "color": ("#" + shapes.parse_color(color)) if color else None}


STATE_NAMES = ("Normal", "Hover", "Down", "Visited", "Disabled")


# --------------------------------------------------------------------- layers


def _layer_seed(pkg: StoryPackage) -> ET.Element:
    """A slide layer to copy: the project's own, or the bundled one.

    A layer is a slide within a slide -- its own background, shape list,
    triggers and timeline -- so it is cloned rather than constructed. Measured
    on a real deck: 130 GUIDs defined inside, only 2-3 pointing outward, and
    the layouts those point at are shared across projects.
    """
    for part in model.slide_index(pkg):
        layers = pkg.parse(part).find("sldLayerLst")
        for layer in list(layers) if layers is not None else []:
            return layer

    seed = clone.SEED_DIR / "layer.xml"
    if seed.is_file():
        return ET.fromstring(seed.read_text(encoding="utf-8"))
    raise StoryError("Klonlanabilir bir katman bulunamadi.")


def list_layers(pkg: StoryPackage, slide: str | None = None) -> list[dict]:
    """Slide layers, per slide."""
    index = model.slide_index(pkg)
    parts = [pkg.slide_part_for(slide)] if slide else list(index)
    out = []
    for part in parts:
        root = pkg.parse(part)
        layers = root.find("sldLayerLst")
        for layer in list(layers) if layers is not None else []:
            out.append({
                "slide": index[part].basename if part in index else part,
                "layer": layer.get("name", ""),
                "guid": layer.get("g", ""),
                "shapes": len(layer.find("shapeLst") or []),
            })
    return out


def _ensure_feedback_master(pkg: StoryPackage, root: ET.Element) -> str | None:
    """Bind the slide to a feedback master, which its first layer requires.

    Every slide carrying layers references one through fmGuid; slides without
    layers mostly do not. Adding the first layer to a slide that has no such
    reference is what made the project unopenable -- the layer itself was
    fine, and every other check passed.

    The value is taken from a sibling slide that already has one, so the deck's
    own choice of master is kept; failing that, from the first master in the
    package.
    """
    existing = root.get("fmGuid")
    if existing:
        return existing

    for part in pkg.slide_parts:
        guid = pkg.parse(part).get("fmGuid")
        if guid:
            root.set("fmGuid", guid)
            return guid

    masters = sorted(
        n for n in pkg._order
        if "slideMasters/slideMaster" in n and n.endswith(".xml") and "_rels" not in n
    )
    if masters:
        guid = pkg.parse(masters[0]).get("g")
        if guid:
            root.set("fmGuid", guid)
            return guid
    return None


def add_layer(
    pkg: StoryPackage,
    slide: str,
    name: str,
    *,
    text: str | None = None,
    open_from: str | None = None,
) -> dict:
    """Add a slide layer, optionally opened by clicking an existing shape.

    A pop-up is built this way: the content lives on a layer and a trigger on
    the slide shows it.
    """
    part = pkg.slide_part_for(slide)
    root = pkg.parse(part)

    layer = shapes.clone_shape(_layer_seed(pkg), name=name)
    layer.set("name", name)
    layer_guid = layer.get("g", "")

    master = _ensure_feedback_master(pkg, root)

    # nextIdx is not decoration. Every <sldLayerLst> in a real deck carries it,
    # and a bare one -- valid XML, correctly placed, holding a layer copied
    # byte for byte with its own GUIDs -- still makes the project unopenable.
    # This was the whole of it: not the layer, not the cloning, the container.
    layers = shapes.insert_in_order(root, ET.Element("sldLayerLst", {"nextIdx": "0"}))
    # The seed carries its origin slide's id. Layers are numbered per slide,
    # so a copied id can collide with one already in use here.
    used = {l.get("id") for l in layers}
    next_id = 1
    while str(next_id) in used:
        next_id += 1
    layer.set("id", str(next_id))
    layers.append(layer)

    if text:
        target, longest = None, -1
        for shape, _t, doc, _s in model._iter_text_shapes(layer):
            length = len(model._doc_text(doc).strip())
            if shape.tag not in LABEL_SHAPES and length > longest:
                target, longest = shape.get("g", ""), length
        if target:
            set_shape_text(layer, target, text)

    wired = None
    if open_from:
        opener = _shape_by_text_or_guid(root, open_from)
        if opener is None:
            raise StoryError(f"{open_from!r} ile eslesen sekil bulunamadi.")
        wired = shapes.retarget_to_layer(opener, layer_guid)

    pkg.replace_xml(part, root)
    return {
        "slide": slide,
        "layer": name,
        "layer_guid": layer_guid,
        "text": text,
        "opened_by": open_from,
        "trigger_wired": wired,
        "feedback_master": master,
    }


def _shape_by_text_or_guid(root: ET.Element, needle: str) -> ET.Element | None:
    """Find a shape by GUID, or failing that by the text it displays.

    Callers describing a button as "KURSA BAŞLA" should not have to look a GUID
    up first.
    """
    found = model._find_by_guid(root, needle)
    if found is not None:
        return found
    folded = needle.casefold().strip()
    for shape in root.iter():
        if shape.tag not in ("btn", "rsltBtn", "roundRect", "rect", "oval", "textBox"):
            continue
        text = model.shape_text(root, shape.get("g", "")).casefold().strip()
        if text and (text == folded or folded in text):
            return shape
    return None


def list_button_states(pkg: StoryPackage, slide: str) -> list[dict]:
    """Every shape on the slide that carries state variants, and their names."""
    root = pkg.parse(pkg.slide_part_for(slide))
    out = []
    for shape in root.iter():
        states = shape.find("stateLst")
        if states is None or not len(states):
            continue
        out.append({
            "shape": shape.get("g", ""),
            "type": shape.tag,
            "text": model.shape_text(root, shape.get("g", "")),
            "states": [s.get("name", "") for s in states],
        })
    return out


def set_button_state(
    pkg: StoryPackage,
    slide: str,
    button: str,
    state: str,
    *,
    fill: str | None = None,
    color: str | None = None,
) -> dict:
    """Recolour one state variant of a button (Hover, Down, Visited...).

    A state is a small slide of its own -- it has its own background, shape
    list and text -- so changing the hover look means editing the shapes inside
    that state, not the button's top-level fill.
    """
    if fill is None and color is None:
        raise StoryError("fill veya color verilmeli.")
    part = pkg.slide_part_for(slide)
    root = pkg.parse(part)

    shape = _shape_by_text_or_guid(root, button)
    if shape is None:
        raise StoryError(f"{slide} icinde {button!r} ile eslesen sekil yok.")
    states = shape.find("stateLst")
    if states is None or not len(states):
        raise StoryError(f"{button!r} state tasimiyor.")

    target = next((s for s in states if (s.get("name") or "").casefold() == state.casefold()), None)
    if target is None:
        available = [s.get("name", "") for s in states]
        raise StoryError(f"{state!r} state'i yok. Mevcut: {available}")

    touched = 0
    if fill:
        for inner in target.iter():
            if inner.find("bG") is not None:
                shapes.set_fill(inner, fill)
                touched += 1
        if not touched:
            shapes.set_fill(target, fill)
            touched = 1
    if color:
        for text_el in target.iter("text"):
            raw = (text_el.text or "").strip()
            if raw.startswith("<Document"):
                text_el.text = shapes.set_text_style(raw, color=color)

    pkg.replace_xml(part, root)
    return {
        "slide": slide,
        "shape": shape.get("g", ""),
        "state": target.get("name", ""),
        "fill": ("#" + shapes.parse_color(fill)) if fill else None,
        "text_color": ("#" + shapes.parse_color(color)) if color else None,
        "shapes_filled": touched,
    }


def add_slide(
    pkg: StoryPackage,
    template: str,
    *,
    title: str | None = None,
    scene: str | None = None,
    name: str | None = None,
) -> dict:
    """Clone a content slide, optionally retitling it.

    Returns the new slide's editable text runs so the remaining body copy can
    be written with update_text.
    """
    result = clone_slide(pkg, template, scene=scene, name=name or title)

    if title:
        root = pkg.parse(result["part"])
        target = _title_shape(root)
        if target and set_shape_text(root, target, title):
            pkg.replace_xml(result["part"], root)

    runs = model.text_runs(pkg, result["new_slide"])
    return {
        **result,
        "title": title,
        "editable_text": [
            {"addr": r.addr, "text": r.text, "shape_type": r.shape_type} for r in runs
        ],
    }
