"""Gorsel ve videoyu bir projeye koy, dosyayi yeniden ac, BAGLARI izle.

Bir video eklemenin dort parcasi var (bayt, kayit, iliski, sekil) ve dordu de
BIRBIRINI ADLA DEGIL, GUID ve md5 ile buluyor. Yani eksik bir bagda dosya
gecerli kalir, Storyline aciir, slaytta yalnizca hicbir sey gorunmez. Bu yuzden
olcu "kaydedildi mi" degil: her bag KAYITTAN BAYTA kadar geri izleniyor.

    .venv/Scripts/python.exe tools/medya_probe.py [kaynak.story] [video.mp4]

Video verilmezse test/0_duz_kopya.story icindeki gercek videolardan biri
cikarilip kullanilir -- Storyline'in kendi yazdigi sayilar (sure, kare hizi,
piksel) o dosyanin icinde durdugu icin ayni zamanda mp4_info'nun dogrulugunu da
olcer.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from storyline_mcp import media, model  # noqa: E402
from storyline_mcp.package import StoryPackage  # noqa: E402

VARSAYILAN_KURS = ROOT.parent / "test" / "c_content.story"
VIDEO_KAYNAGI = ROOT.parent / "test" / "0_duz_kopya.story"


def _video_cikar(hedef: Path) -> Path:
    """Gercek bir kurstan bir mp4 cikar (parcalari .mpeg adiyla saklanir)."""
    with zipfile.ZipFile(VIDEO_KAYNAGI) as z:
        adlar = [n for n in z.namelist() if n.endswith(".mpeg")]
        if not adlar:
            raise SystemExit(f"{VIDEO_KAYNAGI} icinde video yok.")
        kucuk = min(adlar, key=lambda n: z.getinfo(n).file_size)
        hedef.write_bytes(z.read(kucuk))
    return hedef


def _kayitlar(path: Path) -> tuple[dict, dict]:
    """story.xml'deki media ve video kayitlari: guid -> md5."""
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("story/story.xml"))
    resim, video = {}, {}
    for liste in root.iter("mediaLst"):
        for kayit in liste:
            damga = kayit.find("md5Checksum/stream")
            if damga is None:
                continue
            (resim if kayit.tag == "media" else video)[kayit.get("g")] = damga.text
    return resim, video


def _bayt_md5(path: Path) -> dict:
    with zipfile.ZipFile(path) as z:
        return {n: hashlib.md5(z.read(n)).hexdigest()
                for n in z.namelist() if "/media/" in n}


def main() -> int:
    kaynak = Path(sys.argv[1]) if len(sys.argv) > 1 else VARSAYILAN_KURS
    if not kaynak.is_file():
        raise SystemExit(f"Kurs bulunamadi: {kaynak}")

    with tempfile.TemporaryDirectory() as tmp:
        calisma = Path(tmp)
        hedef = calisma / "medya_probe.story"
        shutil.copy2(kaynak, hedef)

        video = (Path(sys.argv[2]) if len(sys.argv) > 2
                 else _video_cikar(calisma / "olcu.mp4"))
        gorsel = calisma / "olcu.png"
        gorsel.write_bytes(media._flat_png(640, 360, "#2EA3B5"))

        pkg = StoryPackage(hedef)
        slayt = sorted(model.slide_index(pkg))[0]
        slayt_adi = slayt.rsplit("/", 1)[1]
        print(f"kurs   : {kaynak.name}")
        print(f"slayt  : {slayt_adi}")

        bilgi = media.mp4_info(video.read_bytes())
        print(f"video  : {video.name} -- {bilgi.get('ms')} ms, "
              f"{bilgi.get('fps')} fps, {bilgi.get('pixels')}")

        r = media.add_image(pkg, slayt_adi, gorsel, x=8, y=30, w=30)
        v = media.add_video(pkg, slayt_adi, video, x=45, y=25, w=45)
        rapor = pkg.save(hedef, backup=False)

        # --- dosyayi yeniden acip her bagi geri izle
        resim_kayit, video_kayit = _kayitlar(hedef)
        baytlar = _bayt_md5(hedef)
        with zipfile.ZipFile(hedef) as z:
            rels = z.read(f"story/slides/_rels/{slayt_adi}.rels").decode("utf-8-sig")
            tipler = z.read("[Content_Types].xml").decode("utf-8-sig")
            kok = ET.fromstring(z.read(f"story/slides/{slayt_adi}"))
        sekiller = {s.tag: s for liste in kok.iter("shapeLst") for s in liste}

        hatalar: list[str] = []

        def olc(ad: str, kosul: bool, kanit: str) -> None:
            print(f"  {'OK ' if kosul else 'HATA'}  {ad}: {kanit}")
            if not kosul:
                hatalar.append(ad)

        # KAYDIN NEREDE DURDUGU. Bag zinciri (assetG -> kayit -> md5 -> bayt)
        # tastamam olsa bile, kayit YANLIS LISTEDEYSE Storyline onu hic gormez
        # ve slaytta "The image can't be displayed" yazar. Olculdu 2026-08-29:
        # dort gercek kursun dordunde de kayitlar ICTEKI mediaLst'te; kod
        # distakine yaziyordu ve iki kursta gorsel hic gorunmedi. Paket
        # gecerliydi, dogrulama temizdi, probe'lar geciyordu.
        with zipfile.ZipFile(hedef) as z:
            _story = ET.fromstring(z.read("story/story.xml"))
        _dis = _story.find("mediaLst")
        _ic = _dis.find("mediaLst") if _dis is not None else None
        print("\nkayitlarin yeri")
        olc("ictek mediaLst var", _ic is not None, "mediaLst > mediaLst")
        olc("kayitlar ICTEKI listede",
            _ic is not None
            and any(c.tag == "media" for c in _ic)
            and any(c.tag == "video" for c in _ic),
            f"ic: {[c.tag for c in _ic][-3:] if _ic is not None else '-'}")
        olc("distaki listede kayit YOK",
            _dis is not None and not any(c.tag in ("media", "video") for c in _dis),
            f"dis: {[c.tag for c in _dis] if _dis is not None else '-'}")

        print("\ngorsel")
        olc("kayit md5 = bayt md5",
            resim_kayit.get(r["asset_guid"]) == baytlar.get(r["media_part"]),
            f"{str(resim_kayit.get(r['asset_guid']))[:12]}… / "
            f"{str(baytlar.get(r['media_part']))[:12]}…")
        olc("iliski slaytta", f'Target="/{r["media_part"]}"' in rels, r["media_part"])
        olc("pic sekli assetG'yi tutuyor",
            sekiller.get("pic") is not None
            and sekiller["pic"].get("assetG") == r["asset_guid"],
            r["asset_guid"][:8] + "…")

        print("\nvideo")
        olc("video kaydi md5 = bayt md5",
            video_kayit.get(v["asset_guid"]) == baytlar.get(v["media_part"]),
            f"{str(video_kayit.get(v['asset_guid']))[:12]}… / "
            f"{str(baytlar.get(v['media_part']))[:12]}…")
        olc("iliski slaytta", f'Target="/{v["media_part"]}"' in rels, v["media_part"])
        olc("mpeg tipi tanimli", 'Extension="mpeg"' in tipler,
            'ContentType="video/mpeg"')
        vs = sekiller.get("video")
        olc("video sekli assetG'yi tutuyor",
            vs is not None and vs.get("assetG") == v["asset_guid"],
            v["asset_guid"][:8] + "…")
        olc("thumbG bir media kaydina cikiyor",
            vs is not None and vs.get("thumbG") in resim_kayit,
            str(vs.get("thumbG") if vs is not None else None)[:8] + "…")
        olc("poster ilikisi slaytta", f'Target="/{v["poster_part"]}"' in rels,
            v["poster_part"])
        film = vs.find("movie") if vs is not None else None
        olc("sure filmin suresi",
            film is not None and film.get("dur") == str(bilgi.get("ms")),
            f"{film.get('dur') if film is not None else '-'} ms")
        zaman = vs.find("tmCtxLst/vidTmCtx") if vs is not None else None
        olc("zaman cizelgesi filmi kesmiyor",
            zaman is not None and zaman.get("dur") == str(bilgi.get("ms")),
            f"{zaman.get('dur') if zaman is not None else '-'} ms")
        boy = vs.find("sldSz") if vs is not None else None
        genislik, yukseklik = ((float(boy.get("w")), float(boy.get("h")))
                               if boy is not None else (0.0, 0.0))
        kutu = (v["box_percent"]["w"] * genislik) / (v["box_percent"]["h"] * yukseklik)
        film_orani = bilgi["pixels"][0] / bilgi["pixels"][1]
        olc("kutu filmin oranini koruyor", abs(kutu - film_orani) < 0.02,
            f"kutu {kutu:.3f} / film {film_orani:.3f} "
            f"({v['box_percent']['w']}% x {v['box_percent']['h']}%)")

        print("\ndosya")
        dogrulama = rapor["verified"]
        olc("paket dogrulandi", dogrulama.get("ok", False),
            f"{dogrulama.get('total_entries', '?')} parca, "
            f"{len(dogrulama.get('problems') or [])} sorun")

        # --- ALANI DOLDURMA. Olculdu 2026-08-29: 3:1 bir fotograf 4:3 kapaga
        # GERILDI ve kimse fark etmedi -- dosya gecerli, dogrulama temiz,
        # yalnizca insanlar yanlis gorunuyordu. Bozulma sessiz oldugu icin
        # burada SAYIYLA sorulur: yerlestirilen baytin orani kutunun oranina
        # esit mi.
        print("\nalani doldurma (fit)")
        genis = calisma / "genis.png"
        genis.write_bytes(media._flat_png(1200, 400, "#C9A227"))   # 3:1
        pkg2 = StoryPackage(hedef)
        from storyline_mcp import shapes as _shapes
        SW, SH = _shapes.slide_size(pkg2.parse(pkg2.slide_part_for(slayt_adi)))
        kutu_orani = SW / SH                          # tam sayfa = slayt orani

        kapla = media.add_image(pkg2, slayt_adi, genis,
                                x=0, y=0, w=100, h=100, fit="cover")
        sigdir = media.add_image(pkg2, slayt_adi, genis,
                                 x=0, y=0, w=100, h=100, fit="contain")
        ger = media.add_image(pkg2, slayt_adi, genis,
                              x=0, y=0, w=100, h=100, fit="stretch")

        yerlesen = kapla["pixels"][0] / kapla["pixels"][1]
        olc("cover: yerlesen bayt kutunun oraninda",
            abs(yerlesen - kutu_orani) < 0.01 * kutu_orani,
            f"{kapla['pixels'][0]}×{kapla['pixels'][1]} = {yerlesen:.3f} "
            f"(kutu {kutu_orani:.3f})")
        olc("cover: kirpma raporlaniyor",
            kapla["cropped"] and kapla["cropped"]["from"] == [1200, 400],
            str(kapla["cropped"]))
        olc("cover: kutu alanin TAMAMI",
            (kapla["box_percent"]["w"], kapla["box_percent"]["h"]) == (100.0, 100.0),
            str(kapla["box_percent"]))
        olc("contain: kirpmaz, kutuya sigar",
            sigdir["cropped"] is None and sigdir["box_percent"]["h"] < 100.0,
            f"{sigdir['box_percent']['w']}×{sigdir['box_percent']['h']}")
        olc("stretch: acikca istenmedikce olmaz",
            ger["cropped"] is None and ger["box_percent"]["h"] == 100.0,
            "yalnizca fit=stretch ile")
        olc("gif kirpilmaz, sigdirmaya duser",
            media._cover_crop(b"GIF89a", ".gif", 1.33) is None, "None")

        # KAYIT KAYNAGI ANLATIR. Alanlari parcadan turetmek Storyline'in
        # gorseli HIC gostermemesine yol aciyordu (olculdu 2026-08-29,
        # MEDYA_TESTI_5/6): bos origFile, sifir modDT ve parcanin boyutu ile
        # yazilan kayit "The image can't be displayed" veriyor, kaynagi
        # anlatan kayit ayni baytlarla goruniyor.
        print("\nkayit kaynagi anlatiyor mu")
        pkg3 = StoryPackage(hedef)
        kapla2 = media.add_image(pkg3, slayt_adi, genis,
                                 x=0, y=0, w=100, h=100, fit="cover")
        pkg3.save(hedef, backup=False)
        with zipfile.ZipFile(hedef) as z:
            _st = ET.fromstring(z.read("story/story.xml"))
            _md5 = {n: hashlib.md5(z.read(n)).hexdigest()
                    for n in z.namelist() if "/media/" in n}
        _ic = _st.find("mediaLst").find("mediaLst")
        kayit = [m for m in _ic if m.get("g") == kapla2["asset_guid"]][0]
        olc("origFile kaynagin yolu", kayit.get("origFile") == str(genis),
            kayit.get("origFile", "")[-28:])
        olc("source = origFile", kayit.get("source") == kayit.get("origFile"), "ayni")
        olc("bytes KAYNAGIN boyutu",
            kayit.get("bytes") == str(genis.stat().st_size),
            f"{kayit.get('bytes')} (parca {len(_md5.get(kapla2['media_part'], '')) and z.getinfo(kapla2['media_part']).file_size})")
        olc("modDT sifir tarih degil",
            kayit.get("modDT") != "0001-01-01T00:00:00", kayit.get("modDT", "")[:19])
        _stream = kayit.find("md5Checksum/stream").text
        _source = kayit.find("md5Checksum/source").text
        olc("md5/stream = PAKETTEKI baytlar",
            _stream == _md5.get(kapla2["media_part"]), str(_stream)[:10])
        olc("md5/source = DISKTEKI dosya (kirpilinca ayrisir)",
            _source == hashlib.md5(genis.read_bytes()).hexdigest() and _source != _stream,
            f"{str(_source)[:10]} != {str(_stream)[:10]}")

    print()
    if hatalar:
        print(f"BASARISIZ: {len(hatalar)} olcu -- " + "; ".join(hatalar))
        return 1
    print("Hepsi gecti.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
