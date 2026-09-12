"""`assetG` çözülüyor mu -- ve çözülmezse yazma DÜŞÜYOR mu.

NICIN VAR. `package.verify` bir referans sinifini zaten kapatiyordu:
`layoutG` var olmayan bir layout'u gosteriyorsa paket reddediliyor.
AYNI SINIFIN MEDYA UCU yalnizca duzyazida duruyordu -- `media._media_list`
basliginda, olculmus haliyle: kayit yanlis listeye girdiginde paket
GECERLI kaliyor, `verify` TEMIZ geciyor, bag zinciri md5'e kadar
izlenebiliyor, ama Storyline gorseli hic gostermiyor ("The image can't
be displayed"). Kullanici bunu IKI ayri kursta bildirdi.

Yani kisit biliniyordu, bir ucta KODLUYDU, obur ucta DUZYAZIYDI -- ve
isiran uc duzyazi olandi. Kapi o ucu kodun icine aliyor.

KUSUR KORPUSTA DURUYOR, SENTETIK DEGIL (olculdu 2026-09-12): 85 test
artefaktinin IKISI cozulemeyen `assetG` tasiyor (`hero_test.story` 3,
`cmp_new.story` 2) ve ikisinde de o kayitlar DISTAKI listede oturuyor --
kusurun ta kendisi, dosyalarin icinde donmus halde. Kontrol grubu ayni
klasorde: `cmp_old.story` TEMIZ.

BEDELI DE OLCULDU, cunku `verify`in bulgusu `save`i DUSURUYOR: kontrol
sert. Kullanicinin 51 gercek kursunun 51'i temiz gecti, yani kontrol
hicbir gercek kursu yazilamaz kilmiyor. Tasiyan iki dosya kendi test
artefaktimiz.

ALTI AYAK:
  1 CIPA         normal yol (add_image) TEMIZ gecmeli
  2 DISTAKI      kayit `mediaLst > mediaLst` yerine DISTAKI listeye
                 tasininca KIRMIZI. Tarihsel kusurun tam sekli.
  3 KAYITSIZ     kayit hic yoksa KIRMIZI
  4 NULL ASSET   `assetG` NULL_GUID ise TEMIZ -- "asset yok" demek, ve
                 uc `cmp_*` dosyasinin UCUNDE de birer tane var
  5 SILME YETIMI `sekil_sil`den sonra kayit REFERANSSIZ kalir ve bu
                 TEMIZ sayilmali. Karar olculdu: `test/bos.story` yedi
                 tane tasiyor ve bu deponun urettigi her kurs ondan
                 kopyalaniyor -- acilip kaydediliyorlar. Zararsiz yon
                 CEZALANDIRILMIYOR; tersi (referans var, kayit yok)
                 cezalandiriliyor.
  6 YAZMA KAPISI tohumlu paket `pkg.save()`ten GECMEMELI. 2-4 `verify`i
                 cagiriyor; bu ayak olmadan kontrol dogru calisip yine
                 hicbir seyi engellemiyor olabilirdi (o kusur bu depoda
                 bir kez yasandi: dogrulama kosuyor, rapor donuyor,
                 kimse bakmiyor).

KOR NOKTA YAZILI. Kontrol, kayitlarin hangi listede durdugunu YAZANIN
cozucusunden (`media._media_list`) soruyor -- ikinci bir kopya iki
uygulamayi ayristirirdi. Bedeli: `_media_list` yanlis listeyi secseydi
yazan da kontrol de birlikte yanilirdi. Ayak 2 tam bu yuzden var: kaydi
DISTAKI listeye elle tasiyip kontrolun kizardigini kanitliyor, yani
kontrol yazanin secimini tekrarlamakla yetinmiyor.

    python tools/medya_kapi.py
"""

from __future__ import annotations

import pathlib
import shutil
import sys
import warnings
import zipfile

import ayak

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

warnings.simplefilter("ignore")

from storyline_mcp import authoring, duzenle, media as M            # noqa: E402
from storyline_mcp.package import (NULL_GUID, StoryPackage,         # noqa: E402
                                   StoryError, verify)

BLANK = ROOT.parent / "test" / "bos.story"
CANARY = ROOT.parent / "test" / "_canary"
KOSAMADI = 3

AYAKLAR = ayak.Defter(
    "cipa",
    "distaki",
    "kayitsiz",
    "null asset",
    "silme yetimi",
    "yazma kapisi",
    genislik=14,
)


def _yaz_kapisiz(pkg: StoryPackage, hedef: pathlib.Path) -> None:
    """Paketi `save`in DOGRULAMA KAPISINA takilmadan yaz.

    Tohumlu dosyayi uretmenin tek yolu bu: `save` tam olarak bu kapiyi
    kurdugumuz icin reddediyor (ayak 6 onu ayrica kanitliyor). Yazma
    adimi `save`in kendi adimiyla ayni -- `_entry_info` sikistirmayi
    parca parca koruyor ve `replace_xml` BOM'u yaziyor, yani dosya
    YALNIZCA tohumlanan sebepten kirmizi olabilir.
    """
    with zipfile.ZipFile(hedef, "w", zipfile.ZIP_DEFLATED) as z:
        for name in pkg._order:
            z.writestr(pkg._entry_info(name), pkg._parts[name])


def _asset_sorunlari(yol: pathlib.Path) -> list[str]:
    return [p for p in verify(yol).get("problems", []) if "assetG" in p]


def _kurulum(ad: str) -> tuple[StoryPackage, str, str, pathlib.Path]:
    """Gorsel tasiyan taze bir paket: (pkg, slayt, asset_guid, yol)."""
    yol = CANARY / f"medya_kapi_{ad}.story"
    shutil.copy2(BLANK, yol)
    pkg = StoryPackage(yol)
    slayt = authoring.add_slide(pkg, "slide7.xml", name="Medya")["new_slide"]
    png = CANARY / "medya_kapi_kart.png"
    png.write_bytes(M._flat_png(40, 30, "#3366aa"))
    sonuc = M.add_image(pkg, slayt, png, x=10, y=20, w=40, name="Kart")
    return pkg, slayt, sonuc["asset_guid"], yol


def _kayit(pkg: StoryPackage, guid: str):
    """(story koku, DISTAKI liste, ICTEKI liste, kaydin kendisi)."""
    story = pkg.parse("story/story.xml")
    dis = story.find("mediaLst")
    ic = M._media_list(story)
    kayit = next((m for m in ic if (m.get("g") or "") == guid), None)
    return story, dis, ic, kayit


def kanarya() -> list[str]:
    kusur: list[str] = []
    CANARY.mkdir(parents=True, exist_ok=True)

    # 1. CIPA -- normal yol temiz gecmeli.
    pkg, slayt, guid, yol = _kurulum("cipa")
    _yaz_kapisiz(pkg, yol)
    cipa = _asset_sorunlari(yol)
    AYAKLAR.yaz("cipa", f"normal yol: {len(cipa)} assetG sorunu (beklenen 0)")
    if cipa:
        kusur.append(f"CIPA KIRMIZI: normal `add_image` yolu assetG sorunu "
                     f"uretiyor -- {cipa[0][:120]}")

    # 2. DISTAKI -- kaydi dis listeye tasi. Tarihsel kusurun tam sekli.
    pkg, slayt, guid, yol = _kurulum("distaki")
    story, dis, ic, kayit = _kayit(pkg, guid)
    if kayit is None:
        kusur.append("TOHUM KOSMADI: yeni kayit icteki listede bulunamadi, "
                     "yani 'distaki' ayagi hicbir sey tohumlamiyor.")
    else:
        ic.remove(kayit)
        dis.append(kayit)                 # ICTEKI listenin KARDESI olur
        pkg.replace_xml("story/story.xml", story)
        _yaz_kapisiz(pkg, yol)
        bulgu = _asset_sorunlari(yol)
        AYAKLAR.yaz("distaki", f"kayit dis listeye tasindi: {len(bulgu)} "
                               f"assetG sorunu (beklenen >=1)")
        if not bulgu:
            kusur.append(
                "AYAK KOR: kayit DISTAKI listeye tasindi ve kontrol hicbir "
                "sey demedi. Tam bu hal kullanicinin iki kursunu bozdu; "
                "kontrol yazanin liste secimini tekrarliyor olabilir.")

    # 3. KAYITSIZ -- kaydi tamamen kaldir.
    pkg, slayt, guid, yol = _kurulum("kayitsiz")
    story, dis, ic, kayit = _kayit(pkg, guid)
    if kayit is None:
        kusur.append("TOHUM KOSMADI: kaldirilacak kayit bulunamadi.")
    else:
        ic.remove(kayit)
        pkg.replace_xml("story/story.xml", story)
        _yaz_kapisiz(pkg, yol)
        bulgu = _asset_sorunlari(yol)
        AYAKLAR.yaz("kayitsiz", f"kayit silindi: {len(bulgu)} assetG sorunu "
                                f"(beklenen >=1)")
        if not bulgu:
            kusur.append("AYAK KOR: kayit hic yokken bile assetG 'cozuluyor' "
                         "sayiliyor.")

    # 4. NULL ASSET -- "asset yok" bir kusur DEGIL.
    pkg, slayt, guid, yol = _kurulum("null")
    kok = pkg.parse(pkg.slide_part_for(slayt))
    pic = next((el for el in kok.iter() if el.get("assetG") == guid), None)
    if pic is None:
        kusur.append("TOHUM KOSMADI: assetG tasiyan sekil bulunamadi.")
    else:
        pic.set("assetG", NULL_GUID)
        pkg.replace_xml(pkg.slide_part_for(slayt), kok)
        _yaz_kapisiz(pkg, yol)
        bulgu = _asset_sorunlari(yol)
        AYAKLAR.yaz("null asset", f"assetG=NULL_GUID: {len(bulgu)} assetG "
                                  f"sorunu (beklenen 0)")
        if bulgu:
            kusur.append(
                "YANLIS ALARM: NULL_GUID 'asset yok' demek ve uc `cmp_*` "
                "dosyasinin ucunde de var; kontrol onu kusur sayiyor.")

    # 5. SILME YETIMI -- zararsiz yon cezalandirilmamali.
    pkg, slayt, guid, yol = _kurulum("yetim")
    duzenle.sekil_sil(pkg, slayt, "Kart")
    story, dis, ic, kayit = _kayit(pkg, guid)
    kaldi = kayit is not None
    _yaz_kapisiz(pkg, yol)
    bulgu = _asset_sorunlari(yol)
    AYAKLAR.yaz("silme yetimi", f"sekil silindi, kayit kaldi={kaldi}: "
                                f"{len(bulgu)} assetG sorunu (beklenen 0)")
    if not kaldi:
        kusur.append(
            "AYAK ARTIK OLCMUYOR: `sekil_sil` kaydi da kaldiriyor. Bu bir "
            "DAVRANIS DEGISIKLIGI -- ayak 'referanssiz kayit zararsizdir' "
            "kararini koruyordu; karar degistiyse gerekcesi yeniden "
            "olculmeli (projede PAYLASILAN gorsel var: bagiscilarda bir "
            "kayda 8 referans olculdu).")
    if bulgu:
        kusur.append("YANLIS ALARM: referanssiz kayit kusur sayiliyor. "
                     "`test/bos.story` yedi tane tasiyor ve bu deponun "
                     "urettigi her kurs ondan kopyalaniyor.")

    # 6. YAZMA KAPISI -- `verify` konusuyor ama `save` DUSUYOR mu.
    pkg, slayt, guid, yol = _kurulum("kapi")
    story, dis, ic, kayit = _kayit(pkg, guid)
    if kayit is None:
        kusur.append("TOHUM KOSMADI: yazma kapisi icin kayit bulunamadi.")
    else:
        ic.remove(kayit)
        pkg.replace_xml("story/story.xml", story)
        hedef = CANARY / "medya_kapi_kapi_yazildi.story"
        hedef.unlink(missing_ok=True)
        try:
            pkg.save(hedef)
            AYAKLAR.yaz("yazma kapisi",
                        f"save GECTI, dosya var={hedef.exists()} "
                        f"(beklenen: red)")
            kusur.append(
                "YAZMA KAPISI YOK: tohumlu paket diske yazildi. `verify`in "
                "dogru olmasi yetmiyor -- verdikt bir kapiya bagli olmali; "
                "aksi halde dogrulama kosar, sorunu bulur, kimse bakmaz.")
        except StoryError as red:
            metin = str(red)
            AYAKLAR.yaz("yazma kapisi",
                        f"save REDDETTI, dosya yazilmadi={not hedef.exists()}"
                        f" -- {metin[:52]}")
            if "assetG" not in metin:
                kusur.append(
                    f"RED BASKA SEBEPTEN: save reddetti ama gerekcesinde "
                    f"assetG yok ({metin[:120]}). Tohum iddia edilen kusuru "
                    f"tohumlamamis olabilir.")
            # REDDIN IKINCI YARISI. `save`in kendi gerekcesi "hedef dosya
            # HIC dokunulmamis kalir" diyor; reddedip yarim dosya birakan
            # bir uygulama da bu ayagi gecerdi -- ve geriye donusu olmayan
            # tek sey diskteki dosya.
            if hedef.exists():
                kusur.append(
                    "RED YARIM: save reddetti ama hedef dosyayi yazmis. "
                    "Dogru hata, kirli durum -- kapinin korudugu sey tam "
                    "olarak dosyanin dokunulmamis kalmasi.")
    return kusur


def main() -> int:
    if not BLANK.exists():
        print(f"KOSAMADI: fikstur yok ({BLANK}). assetG kontrolu sinanamadi "
              f"-- 'gecti' DEGIL, 'bakilmadi'.")
        return KOSAMADI
    kusur = kanarya()
    _kosmayan = AYAKLAR.kosmayanlar()
    if _kosmayan:
        kusur.append("BEYANDA DURAN AMA KOSMAYAN AYAK: %s"
                     % ", ".join(_kosmayan))
    if kusur:
        print("\nKAPI KALDI:")
        for k in kusur:
            print(f"  - {k}")
        return 1
    print("\nkapi gecti: cozulemeyen assetG yazmayi DUSURUYOR, "
          "NULL_GUID ve referanssiz kayit dusurmuyor")
    print("KAPSAM: `thumbG` (video afisi) OLCULMEDI -- alti bagiscinin "
          "hicbirinde\n        video yok, yani o referansin kaydi gosterip "
          "gostermedigi bilinmiyor.")
    return 0


if __name__ == "__main__":
    from kanarya_kilit import korumali
    raise SystemExit(korumali(main))
