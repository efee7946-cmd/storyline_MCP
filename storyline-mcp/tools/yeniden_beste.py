"""Hangi slayt YENİDEN BESTELENEBİLİR -- yani görsel için yer açılabilir mi?

Sohbet yolunun kurulum sonrasi medya gecisi bugun yalnizca AYRILMIS alani
buluyor; yer ACMIYOR (README, "Bilinen sinirlar"). Yer acmanin tek yolu
slaydi `image_area=True` ile YENIDEN BESTELEMEK, ve bu yikici bir islem:
compose slaydi temizleyip bastan cizer. Elle eklenmis bir sekil, bir soru
tetikleyicisi ya da bir geri bildirim katmani varsa yeniden besteleme onu
GOTURUR.

O yuzden "yer acalim mi" sorusunun onunde olculmesi gereken bir sayi var:
KAC SLAYT yeniden bestelenmeyi guvenle kaldirir? Sifirsa, yer acan bir
gecis de yer acmayan kadar ise yaramaz -- ve karar degisir.

UC AYAK, hepsi de "bu slaydi compose kurdu ve o gunden beri kimse
dokunmadi" sorusunun ayri bir yuzu:

  sekil    butun sekil adlari compose'un KENDI sozlugunde mi. Yabanci bir
           ad (elle konmus bir kutu, tohumdan devralinmis bir sekil, bir
           soru sikki) slaydin compose disinda da icerik tasidigini soyler.
  tetik    standart gezinme disinda tetikleyici var mi. Bir soru ya da bir
           katman dugmesi buraya yazar.
  katman   geri bildirim katmani var mi.

SOZLUK VE STANDART TETIKLEYICILER OLCULEREK BULUNUR, YAZILARAK DEGIL.
Elle yazilan bir ad listesi compose degistigi gun sessizce yanlis olur ve
bu olcu "her slayt yabanci" demeye baslar. Bunun yerine her duzen x her
varyant x her uslup bir kez kurulur ve ne ad uretiliyorsa sozluk odur.
BUTON SEKILLERI ADLARINI ETIKETTEN ALIYOR (`Devam`, `Konu A`), yani
sozluge giremezler; onlar ADI KENDI METNINE ESIT olmasindan taniniyor --
tag imzasi DENENDI VE ELENDI, compose'un butonlari `Kart` ile ayni tag'i
(`roundRect`) tasiyor.

BAYRAK ESIKSIZ, ve bu bilerek: `acilabilir > 0 ve ayrilmis == 0`, yani
"yer vardi, hicbiri kullanilmadi". Bir buyukluk esigi uydurulmus bir sayi
olurdu ve kurs uzunluguna gore kayardi. Yedi kursta davranisi OLCULDU:

    kurs             acilabilir  ayrilmis  bayrak
    uretilmis                17         4    -
    kosul_probu2             14         6    -
    olcum_ilerleme            6         6    -
    kurs.story               10         0    BAYRAK
    deneme.kurs               0         0    -
    yks                       7         2    -
    savunma                   8         0    BAYRAK

Tam olarak medya boru hattinin yer VARKEN hic calismadigi iki kursu
isaretliyor; yeri OLMAYAN kursta (deneme.kurs) susuyor, kismen
calisanlarda susuyor. savunma'nin bayraklanmasi BAGIMSIZ dogrulama --
o kursun medyasiz ciktigi bu oturumda ayri yoldan tespit edilmisti.

NE OLCMEZ: bu olcu slaydin yeniden bestelenmeye DEGER olup olmadigini
soylemez, yalnizca KALDIRIP kaldiramayacagini. Emniyetten gecen bir slayt
zaten iyi yerlesmis olabilir; gorsel istemek ayri bir karar.

    python tools/yeniden_beste.py kurs.story [kurs2.story ...]
    python tools/yeniden_beste.py --dokum kurs.story   slayt slayt yaz
"""

from __future__ import annotations

import argparse
import shutil
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from storyline_mcp import compose, model, shapes
from storyline_mcp import emniyet as emn
from storyline_mcp.package import StoryPackage

BLANK = ROOT.parent / "test" / "bos.story"
WORK = ROOT.parent / "test" / "_canary" / "yeniden_beste_sozluk.story"

def _butonsu(root, el) -> bool:
    """Bu şekil bir buton mu -- ADI KENDI METNINE EŞİT Mİ.

    Buton sekilleri adlarini ETIKETTEN aliyor (`Devam`, `Konu A`), yani
    sozlukle taninamazlar; ayrica taninmalari gerekiyor.

    ILK DENENEN IMZA TAG'DI VE YANLISTI: bir donor butonu `plaque` olarak
    gorulmustu ve kural oradan yazilmisti. Olculdu -- compose'un kendi
    butonlari ALTI duzende de `roundRect`, yani `Kart` ile ayni tag. Tag
    ayirt etmiyor, ve `Devam` sessizce sekil sozlugune girmisti.

    Ad == metin imzasi ayirt ediyor: compose'un oteki sekillerinde ad ROL
    (Body, Eyebrow, Kart), metin ise ICERIK; ikisi esit olmuyor.
    """
    metin = (model.shape_text(root, el.get("g") or "") or "").strip()
    return bool(metin) and metin == (el.get("name") or "").strip()


def _temiz_slaytlar(pkg: StoryPackage) -> list[str]:
    """Şablonun KENDİ kalıntısını taşımayan slaytlar.

    `bos.story`nin slideb.xml'i iki katman ve iki ADSIZ tetikleyici
    tasiyor. Prob oraya `image_area=True` ile bestelemeye kalkinca
    `compose_slide` -- dogru olarak -- REDDETTI: o slayt gercekten kirli.
    Yani bu arac kendi kurdugu kurala carpti, ve carpmasi kuralin
    calistiginin kaniti.

    Prob artik temiz slayt seciyor. Bu ayni zamanda tetikleyici
    kesisiminin ikinci guvencesi: kalinti kaynakta eleniyor.
    """
    out = []
    for ref in model.slide_index(pkg).values():
        root = pkg.parse(pkg.slide_part_for(ref.basename))
        if not emn.yeniden_beste_engelleri(root):
            out.append(ref.basename)
    return out


def sozluk() -> tuple[set[str], set[str], set[str]]:
    """(şekil adları, standart tetikleyiciler, REZERVASYON şekilleri) -- ÖLÇÜLEREK.

    Her duzen x varyant, icerigin hepsi dolu. Uslup de gezilir cunku
    `mark` uslupla ad degistiriyor (Vurgu / Kose / Serit) ve `cards`
    tedavisi `Kenar` yerine `Cizgi` cizebiliyor.

    GORSEL DURUMLARI DA GEZILIR, VE BU BIR KUSURDAN OGRENILDI. Ilk surum
    yalnizca `image_area=False` ile besteliyordu; uc rezervasyon sekli o
    kumede HIC gecmedi ve sozluk onlari YABANCI saydi. Sonuc: kursun en
    medya-uygun slaydi -- hero kapak -- "yeniden bestelenemez" diye
    eleniyordu, hem de alani zaten ayrilmis oldugu icin. Olculdu (yks):
        slide.xml    yabanci sekil ['Ortu', 'Ton']
    Kapsam yazilmadigi icin iddia sessizce "compose bunlari uretmez"e
    genislemisti -- ayni sekil, ucuncu kez.

    REZERVASYON SINIFI DA BURADAN TURETILIR, yazilmaz:
        rezervasyon = (gorselli adlar) - (gorselsiz adlar)
    Bugun {Gorsel Alani, Ton, Ortu} veriyor; compose yarin dorduncusunu
    eklerse sozluk kendiliginden ogrenir.

    NEYE KOR: `panel` gorsel yerlesimi AYIRT EDICI bir sekil cizmiyor
    (olculdu -- gorselsiz kume ile ayni adlari veriyor), yani panel ile
    ayrilmis bir alan "ayrilmis" diye taninamaz. Yalnizca `bleed` ve
    `hero` taninir.
    """
    adlar: set[str] = set()
    # TETIKLEYICILER BIRLESIM DEGIL KESISIM. Ilk surum birlesim aliyordu ve
    # sozluge bos bir ad ('') girdi -- yani "adsiz tetikleyici standarttir"
    # demis oldu, ki bir soru tetikleyicisi de adsiz olabilir. Kaynak
    # OLCULDU: `bos.story`nin slideb.xml'i iki ADSIZ tetikleyici ve iki
    # katman tasiyor, ve compose sekilleri temizliyor ama tetikleyicileri
    # temizlemiyor. Yani referansi sablonun kendi kalintisi kirletmisti.
    #
    # Kesisim bunu genel olarak cozer: compose her slayda Navigation ve
    # Previous koyuyor, dolayisiyla HER prob slaydinda gorunen ad
    # standarttir; yalnizca bir slaytta gorunen ad sablonun mirasidir.
    # Baska bir bos sablonla da dogru calisir -- slayt adi yazmiyoruz.
    tetik_kumeleri: list[set[str]] = []
    dolu = dict(title="Baslik", eyebrow="Bolum", body="Govde metni burada.",
                bullets=["bir", "iki", "uc", "dort"], buttons=["Devam"],
                index="01")
    hucreler = [(l, v) for l in compose.LAYOUTS
                for v in (compose.variants_for(l) or [None])]
    for style in sorted(compose.STYLES):
        for bas in range(0, len(hucreler), 10):
            parti = hucreler[bas:bas + 10]
            shutil.copy2(BLANK, WORK)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                pkg = StoryPackage(WORK)
                slaytlar = _temiz_slaytlar(pkg)[:len(parti)]
                for slayt, (layout, variant) in zip(slaytlar, parti):
                    compose.compose_slide(pkg, slayt, layout, variant=variant,
                                          style=style, identity="sozluk",
                                          **dict(dolu))
                pkg.save(WORK, backup=False)
            done = StoryPackage(WORK)
            for slayt in slaytlar:
                root = done.parse(done.slide_part_for(slayt))
                for el in list(root.find("shapeLst") or []):
                    if not _butonsu(root, el):
                        adlar.add(el.get("name") or "")
                tetik_kumeleri.append({(tr.get("name") or "")
                                       for tr in list(root.find("trigLst") or [])})
    tetikler = set.intersection(*tetik_kumeleri) if tetik_kumeleri else set()

    # IKINCI GECIS: gorselli. Varyant gezilmez -- rezervasyon sekilleri
    # varyanta degil `image_style`a bagli (olculdu), ve varyant gezmek
    # kosuyu dort katina cikarirdi.
    gorselli: set[str] = set()
    for style in sorted(compose.STYLES):
        for stil in compose.IMAGE_STYLES:
            shutil.copy2(BLANK, WORK)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                pkg = StoryPackage(WORK)
                slaytlar = _temiz_slaytlar(pkg)[:len(compose.LAYOUTS)]
                for slayt, layout in zip(slaytlar, compose.LAYOUTS):
                    compose.compose_slide(pkg, slayt, layout, style=style,
                                          identity="sozluk", image_area=True,
                                          image_style=stil, **dict(dolu))
                pkg.save(WORK, backup=False)
            done = StoryPackage(WORK)
            for slayt in slaytlar:
                root = done.parse(done.slide_part_for(slayt))
                for el in list(root.find("shapeLst") or []):
                    if not _butonsu(root, el):
                        gorselli.add(el.get("name") or "")
    rezervasyon = gorselli - adlar
    return adlar | gorselli, tetikler, rezervasyon


def emniyet(pkg: StoryPackage, slayt: str, adlar: set[str],
            tetikler: set[str], rezervasyon: set[str]) -> dict:
    """Bu slayt yeniden bestelenmeyi kaldırır mı, ve kaldırmıyorsa neden."""
    root = pkg.parse(pkg.slide_part_for(slayt))
    # KURAL URETIMDEN OKUNUR, BURADA IKINCI KEZ YAZILMAZ. Bu aracin kendi
    # kopyasi olsaydi `compose_slide`in reddettigi ile bu aracin
    # "acilabilir" dedigi ayrisirdi -- ve ayrisma sessiz olurdu.
    engeller = emn.yeniden_beste_engelleri(root)
    yabanci = sorted({
        (el.get("name") or "?") for el in list(root.find("shapeLst") or [])
        if not _butonsu(root, el) and (el.get("name") or "") not in adlar})
    fazla = sorted({
        (tr.get("name") or "?") for tr in list(root.find("trigLst") or [])
        if (tr.get("name") or "") not in tetikler})
    katman = root.find("sldLayerLst")
    katman_n = len(katman) if katman is not None else 0
    # Alan ZATEN ayrilmis mi. Sinif TURETILIYOR (bkz. sozluk); elle
    # yazilan bir liste `Ton`/`Ortu`yu kacirmisti ve hero kapak yanlis
    # sinifa dusmustu.
    ayrilmis = emn.alan_ayrilmis(root)
    return {"slayt": slayt, "yabanci": yabanci, "fazla_tetik": fazla,
            "katman": katman_n, "ayrilmis": ayrilmis,
            "engeller": engeller, "gecer": not engeller}


def kanarya(adlar: set[str], tetikler: set[str],
            rezervasyon: set[str]) -> list[str]:
    """Emniyet ölçüsü koşuyor ve GÖRÜYOR mu. DORT AYAK.

    Ilk ayak en onemlisi: bozuk bir sozluk her slaydi "yabanci" gosterir
    ve sonuc "hicbiri gecmiyor" olur -- kor bir olcunun sifiri ile gercek
    sifir AYNI GORUNTUDUR, ve bu aracin urettigi sayi tam olarak bir
    karari (yer acalim mi) belirliyor.
    """
    kusur = []
    yol = ROOT.parent / "test" / "_canary" / "yeniden_beste_kanarya.story"
    shutil.copy2(BLANK, yol)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pkg = StoryPackage(yol)
        adaylar = [r.basename for r in model.slide_index(pkg).values()]
        temiz = adaylar[0]
        compose.compose_slide(pkg, temiz, "content", title="T", eyebrow="E",
                              body="Govde.", bullets=["a", "b"],
                              buttons=["Devam"], identity="kan")
        pkg.save(yol, backup=False)

    # 1. TEMIZ SLAYT GECMELI.
    p1 = StoryPackage(yol)
    r = emniyet(p1, temiz, adlar, tetikler, rezervasyon)
    print(f"kanarya temiz: taze bestelenmis slayt "
          f"{'GECTI' if r['gecer'] else 'KALDI ' + str(r)}")
    if not r["gecer"]:
        kusur.append(f"olcu KOR: compose'un kendi urettigi slayt emniyetten "
                     f"gecmiyor ({r['yabanci']}, {r['fazla_tetik']}, "
                     f"{r['katman']} katman) — sozluk bozuk, sifirlar yalan")

    # 2-3. EKILMIS KUSURLAR: yabanci sekil ve yabanci tetikleyici.
    import xml.etree.ElementTree as ET
    for ad, kur, beklenen in (
            ("yabanci sekil", "shapeLst", "yabanci"),
            ("yabanci tetikleyici", "trigLst", "fazla_tetik")):
        bozuk = yol.with_name(f"yb_{beklenen}.story")
        shutil.copy2(yol, bozuk)
        pk = StoryPackage(bozuk)
        part = pk.slide_part_for(temiz)
        root = pk.parse(part)
        hedef = root.find(kur)
        if hedef is None:
            kusur.append(f"kanarya kurulamadi: {kur} yok")
            continue
        yeni = ET.SubElement(hedef, "rect" if kur == "shapeLst" else "trig")
        yeni.set("name", "ZZ Elle Konmus")
        yeni.set("g", "00000000-0000-0000-0000-0000000000ff")
        pk.replace_xml(part, root)
        pk.save(bozuk, backup=False)
        r2 = emniyet(StoryPackage(bozuk), temiz, adlar, tetikler, rezervasyon)
        print(f"kanarya ekili ({ad}): {'YAKALANDI' if r2[beklenen] else 'KACTI'}")
        if r2["gecer"] or not r2[beklenen]:
            kusur.append(f"olcu KOR: {ad} eklendi ama emniyet hala geciyor")

    # 4b. HERO KAPAK: hem GECMELI hem AYRILMIS sayilmali. Kacirdigim
    # kusurun tam karsiligi -- `Ton`/`Ortu` sozlukte olmadigi icin bu
    # slayt "yabanci sekil" diye eleniyordu, hem de alani zaten ayrilmis
    # oldugu halde.
    yol2 = ROOT.parent / "test" / "_canary" / "yeniden_beste_hero.story"
    shutil.copy2(BLANK, yol2)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pk2 = StoryPackage(yol2)
        hero = [r.basename for r in model.slide_index(pk2).values()][0]
        compose.compose_slide(pk2, hero, "cover", title="Kapak",
                              body="Alt metin.", identity="kan",
                              image_area=True, image_style="hero")
        pk2.save(yol2, backup=False)
    rh = emniyet(StoryPackage(yol2), hero, adlar, tetikler, rezervasyon)
    print(f"kanarya hero: kapak {'GECTI' if rh['gecer'] else 'KALDI'}, "
          f"{'AYRILMIS' if rh['ayrilmis'] else 'ayrilmamis'} sayildi"
          f"{'' if rh['gecer'] else ' -- ' + str(rh['yabanci'])}")
    if not rh["gecer"]:
        kusur.append(f"olcu KOR: hero kapak yabanci sekil sayiliyor "
                     f"({rh['yabanci']}) — sozluk gorsel durumlarini gezmemis")
    if not rh["ayrilmis"]:
        kusur.append("olcu KOR: hero kapagin alani ayrilmis sayilmiyor — "
                     "rezervasyon sinifi eksik")

    # 4c. RED KURUCU YOLUNU ISIRMAMALI. `add_slide`in taze slaydina
    # image_area=True ile gelmek KABUL edilmeli; olcut "compose'un
    # koymadigi bir sey var mi" oldugu icin kapsam kendini sinirliyor,
    # ama bu bir IDDIA ve iddia kosulmadan durmaz.
    from storyline_mcp import authoring
    from storyline_mcp.package import StoryError
    yol3 = ROOT.parent / "test" / "_canary" / "yeniden_beste_taze.story"
    shutil.copy2(BLANK, yol3)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pk3 = StoryPackage(yol3)
        ilk = [r.basename for r in model.slide_index(pk3).values()][0]
        eklendi = authoring.add_slide(pk3, ilk)
        try:
            compose.compose_slide(pk3, eklendi["new_slide"], "content",
                                  title="T", body="B", identity="kan",
                                  image_area=True, image_style="bleed")
            print("kanarya kurucu: taze slayt image_area ile KABUL (dogru)")
        except StoryError as exc:
            print(f"kanarya kurucu: taze slayt REDDEDILDI -> {str(exc)[:90]}")
            kusur.append(f"RED KURUCU YOLUNU ISIRIYOR: taze slayt "
                         f"image_area ile reddediliyor ({str(exc)[:70]})")

    # 4d. RED GERCEKTEN KOSUYOR MU. Katmanli slayda image_area ile gelmek
    # REDDEDILMELI; olcu yesil olup red hic kosmasaydi bu arac yine
    # "acilabilir" sayar ve kusur sinifi acik kalirdi.
    pk4 = StoryPackage(yol)
    katmanli = [a for a in adaylar if a.startswith("slideb")]
    if katmanli:
        try:
            compose.compose_slide(pk4, katmanli[0], "content", title="T",
                                  body="B", identity="kan",
                                  image_area=True, image_style="bleed")
            print("kanarya red: katmanli slayt KABUL EDILDI (YANLIS)")
            kusur.append("RED KOSMUYOR: katmanli slayda image_area ile "
                         "gelinebiliyor — katmanlar sessizce silinir")
        except StoryError:
            print("kanarya red: katmanli slayt image_area ile REDDEDILDI (dogru)")

    # 4. KATMANLI SLAYT KALMALI. bos.story'nin slideb'i iki katman tasiyor.
    if katmanli:
        r3 = emniyet(p1, katmanli[0], adlar, tetikler, rezervasyon)
        print(f"kanarya katman: katmanli slayt "
              f"{'KALDI' if not r3['gecer'] else 'GECTI'} "
              f"({r3['katman']} katman)")
        if r3["gecer"]:
            kusur.append("olcu KOR: iki katman tasiyan slayt emniyetten "
                         "geciyor")
    return kusur


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("kurslar", nargs="+")
    parser.add_argument("--dokum", action="store_true",
                        help="slayt slayt yaz")
    args = parser.parse_args()

    adlar, tetikler, rezervasyon = sozluk()
    print(f"sozluk OLCULDU: {len(adlar)} sekil adi, "
          f"{len(tetikler)} standart tetikleyici {sorted(tetikler)}, "
          f"rezervasyon {sorted(rezervasyon)}")
    # KOSTUGUNU KANITLA: bos bir sozluk her slaydi "yabanci" gosterir ve
    # sonuc "hicbiri gecmiyor" olur -- kor bir olcunun sifiriyla gercek
    # sifir ayni goruntudur.
    if len(adlar) < 8 or not tetikler:
        print("SOZLUK BOS CALISTI: olcu kurulamadi, sayilar okunmamali.")
        return 1
    # KAYMA DENETIMI, IKI YONLU. `storyline_mcp/emniyet.py` sabitleri
    # DONDURULMUS (turetme 180 kurulum, ~30s; her compose_slide cagrisinda
    # kosamaz). Kayma riskini bu kapi ustleniyor: burada yeniden turetilip
    # uretimdekiyle karsilastiriliyor. Sabit elle tutulan bir kopya degil,
    # olculmus bir deger ve onu dogrulayan bir kapi.
    sapma = []
    for ad, olculen, donmus in (
            ("sekil sozlugu", adlar, set(emn.SEKIL_SOZLUGU)),
            ("standart tetikleyici", tetikler, set(emn.STANDART_TETIKLEYICILER)),
            ("rezervasyon sekli", rezervasyon, set(emn.REZERVASYON_SEKILLERI))):
        if olculen - donmus:
            sapma.append(f"{ad}: compose {sorted(olculen - donmus)} uretiyor "
                         f"ama emniyet.py bilmiyor — dolu slaytlar YANLISLIKLA "
                         f"reddedilir")
        if donmus - olculen:
            sapma.append(f"{ad}: emniyet.py {sorted(donmus - olculen)} sayiyor "
                         f"ama compose artik uretmiyor — yabanci icerik "
                         f"SESSIZCE gecer")
    print(f"kayma denetimi: emniyet.py sabitleri "
          f"{'TUTUYOR' if not sapma else 'AYRISMIS'}")
    if sapma:
        print("\nSABITLER AYRISMIS. Asagidaki sayilar okunmamali:")
        for x in sapma:
            print(f"  - {x}")
        return 1

    kusur = kanarya(adlar, tetikler, rezervasyon)
    if kusur:
        print("\nKANARYA KALDI. Asagidaki sayilar okunmamali:")
        for k in kusur:
            print(f"  - {k}")
        return 1

    print(f"\n{'kurs':<34}{'slayt':>7}{'gecen':>8}{'ayrilmis':>10}"
          f"{'ACILABILIR':>12}")
    print("-" * 71)
    toplam_acilabilir = 0
    bayraklar: list[str] = []
    for yol in args.kurslar:
        p = Path(yol)
        if not p.is_file():
            print(f"{p.name:<34}  dosya yok")
            continue
        pkg = StoryPackage(p)
        slaytlar = [r.basename for r in model.slide_index(pkg).values()]
        sonuc = [emniyet(pkg, s, adlar, tetikler, rezervasyon)
                 for s in slaytlar]
        gecen = [r for r in sonuc if r["gecer"]]
        ayrilmis = [r for r in sonuc if r["ayrilmis"]]
        # ASIL SAYI: emniyetten gecen VE alani henuz ayrilmamis olanlar.
        # Gecisin yer ACABILECEGI slaytlar bunlar.
        acilabilir = [r for r in gecen if not r["ayrilmis"]]
        toplam_acilabilir += len(acilabilir)
        # BAYRAK: ESIK DEGIL BIRLESIM. "Yer vardi, hicbiri kullanilmadi."
        # Bir buyukluk esigi ("acilabilir > 5" gibi) uydurulmus bir sayi
        # olurdu ve kurs uzunluguna gore kayardi. Aranan sey buyukluk
        # degil: medya boru hatti yer VARKEN hic mi calismadi.
        bayrak = bool(acilabilir) and not ayrilmis
        print(f"{p.name:<34}{len(sonuc):>7}{len(gecen):>8}"
              f"{len(ayrilmis):>10}{len(acilabilir):>12}"
              f"{'  <- BAYRAK' if bayrak else ''}")
        if bayrak:
            bayraklar.append(p.name)
        if args.dokum:
            for r in sonuc:
                if r["gecer"]:
                    durum = "ayrilmis" if r["ayrilmis"] else "ACILABILIR"
                else:
                    sebep = []
                    if r["yabanci"]:
                        sebep.append(f"yabanci sekil {r['yabanci'][:3]}")
                    if r["fazla_tetik"]:
                        sebep.append(f"tetikleyici {r['fazla_tetik'][:3]}")
                    if r["katman"]:
                        sebep.append(f"{r['katman']} katman")
                    durum = "; ".join(sebep)
                print(f"    {r['slayt']:<16} {durum}")

    print(f"\nyeniden bestelenebilir VE alani ayrilmamis: {toplam_acilabilir}")
    if bayraklar:
        print(f"BAYRAK ({len(bayraklar)}): {', '.join(bayraklar)} -- yer "
              f"acilabilirdi ama hicbir slaytta alan ayrilmamis")
    print("KAPSAM: bu olcu slaydin yeniden bestelenmeye DEGER oldugunu\n"
          "        soylemez, yalnizca KALDIRABILECEGINI. Gorsel istemek\n"
          "        ayri bir karar; bu sayi o kararin UST SINIRI.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
