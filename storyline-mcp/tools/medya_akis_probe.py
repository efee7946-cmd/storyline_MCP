"""Istek defterinden slayta: medya akisini bastan sona kos.

Motor tarafi tools/medya_probe.py ile olculuyor (bayt, kayit, iliski, sekil).
Burada olculen AKIS: modelin istegi kabul ediliyor mu, defter dosyada duruyor
mu, secilen dosya DOGRU slayta ve modelin ayirdigi ALANA giriyor mu, ve istek
bir kez karsilandiktan sonra listeden dusuyor mu.

Ayri duruyor cunku ayri sey olcuyor: motor "dosya gecerli mi" diye sorar, akis
"bekleyen istek gercekten kapandi mi" diye sorar. Ikincisi bozuldugunda dosya
kusursuz kalir -- yalnizca ayni istek her acilista yeniden bekler.

    .venv/Scripts/python.exe tools/medya_akis_probe.py [kaynak.story]
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "panel"))

import builder  # noqa: E402
from storyline_mcp import authoring, compose, media, model, settings, shapes  # noqa: E402
from storyline_mcp import medya as defter  # noqa: E402
from storyline_mcp.package import StoryPackage  # noqa: E402

# Iki slayt gerekiyor: istegin DOGRU slayta gittigi ancak baska bir slayt
# varken olculebilir.
VARSAYILAN_KURS = ROOT.parent / "test" / "bos.story"
VIDEO_KAYNAGI = ROOT.parent / "test" / "0_duz_kopya.story"

# Modelin dondurebilecegi seyler: kabul edilenler ve edilmeyenler.
ORNEKLER = [
    ({"medya": {"tur": "video", "saniye": 20,
                "aciklama": "Telefon ekraninda dogrulama bildirimi, parmak "
                            "onay tusunun uzerinde."}}, True, "tam istek"),
    ({"medya": {"tur": "foto",
                "aciklama": "Masada birakilmis kilitlenmemis bir dizustu "
                            "bilgisayar, ofis arka planda."}}, True,
     "yakin ad (foto -> gorsel)"),
    ({"medya": {"tur": "gorsel", "aciklama": "guvenlik gorseli"}}, False,
     "etiket, siparis degil"),
    ({"medya": {"tur": "ses", "aciklama": "Uzun ve duzgun bir aciklama metni."}},
     False, "desteklenmeyen tur"),
    ({"medya": "video"}, False, "alan sozluk degil"),
    ({}, False, "istek yok"),
]


def _video_cikar(hedef: Path) -> Path:
    with zipfile.ZipFile(VIDEO_KAYNAGI) as z:
        adlar = [n for n in z.namelist() if n.endswith(".mpeg")]
        kucuk = min(adlar, key=lambda n: z.getinfo(n).file_size)
        hedef.write_bytes(z.read(kucuk))
    return hedef


def main() -> int:
    kaynak = Path(sys.argv[1]) if len(sys.argv) > 1 else VARSAYILAN_KURS
    hatalar: list[str] = []

    def olc(ad: str, kosul: bool, kanit: str) -> None:
        print(f"  {'OK ' if kosul else 'HATA'}  {ad}: {kanit}")
        if not kosul:
            hatalar.append(ad)

    print("istek okuma (builder._medya_istegi)")
    for spec, beklenen, ad in ORNEKLER:
        cikti = builder._medya_istegi(spec)
        olc(ad, (cikti is not None) == beklenen,
            f"{'kabul: ' + cikti['tur'] if cikti else 'dusuruldu'}")

    with tempfile.TemporaryDirectory() as tmp:
        calisma = Path(tmp)
        hedef = calisma / "akis.story"
        shutil.copy2(kaynak, hedef)
        video = _video_cikar(calisma / "olcu.mp4")
        gorsel = calisma / "olcu.png"
        gorsel.write_bytes(media._flat_png(800, 500, "#C9A227"))

        # --- kurucunun kapisi: "yer var" dedigi her yerde motor GERCEKTEN
        # yer ayiriyor mu. Ikisi ayri dosyada yasiyor ve ayri ayri dogruyken
        # birlikte yanlis olabilirler: kapi evet der, compose None dondurur ve
        # istek, metnin ustune dusecek bir varsayilan kutuyla kaydedilir.
        print()
        print("kurucu kapisi -> ayrilan alan")
        prova = StoryPackage(hedef)
        sablon = min((t for t in authoring.list_templates(prova)
                      if t["kind"] == "content"),
                     key=lambda t: t["text_shapes"])["slide"]
        for duzen, spec, bekleniyor in [
            ("cover", {"body": "Bir cumle."}, True),
            ("content", {"body": "Bir cumle."}, True),
            ("content", {"bullets": ["a", "b"]}, False),
            ("bullets", {"bullets": ["a", "b"]}, False),
            ("statement", {"body": "Bir cumle."}, False),
        ]:
            kapi = builder._medya_yeri_var(duzen, spec)
            if not kapi:
                etiket = duzen + ("+bullets" if duzen == "content"
                                  and spec.get("bullets") else "")
                olc(f"{etiket}: istek kabul edilmiyor", kapi == bekleniyor,
                    "kapi hayir diyor")
                continue
            yeni = authoring.add_slide(prova, sablon, name=f"prova-{duzen}")
            laid = compose.compose_slide(
                prova, yeni["new_slide"], duzen, title="Baslik",
                body=spec.get("body"), bullets=spec.get("bullets"),
                image_area=True, image_style=builder._medya_stili(duzen),
                clear=True)
            olc(f"{duzen}: alan ayrildi", laid.get("image_area") is not None,
                f"{laid.get('image_style')} -> {laid.get('image_area')}")

        # Kart bandi GORSEL ALANI OLARAK bildirilmesin. Bildiriliyordu ve
        # sessizdi: prompt "donen image_area'yi aynen add_image'e gecir"
        # diyor, yani resim maddelerin ustune konurdu.
        for variant in ("sol-panel", "sag-metin"):
            yeni = authoring.add_slide(prova, sablon, name=f"kart-{variant}")
            laid = compose.compose_slide(
                prova, yeni["new_slide"], "content", title="Baslik",
                bullets=["bir", "iki"], image_area=True, image_style="panel",
                variant=variant, clear=True)
            olc(f"content+bullets/{variant}: kart bandi gorsel alani DEGIL",
                laid.get("image_area") is None, f"{laid.get('image_area')}")

        # PLAN: hangi slaytlar isteyecek. Modele SORULMAZ -- olculdu, sorulunca
        # hic istemedi. Burada model cagrisi bilerek dusurulur, yani olculen sey
        # yalnizca kurucunun kendi karari.
        print()
        print("medya plani (model olmadan)")

        def _kurs():
            def sl(layout, title, **kw):
                return {"kind": "content", "layout": layout, "title": title, **kw}
            return [
                {"name": "01_Giris", "title": "Giris", "content": [
                    sl("cover", "Hos geldiniz", body="Kisa giris."),
                    sl("bullets", "Neler var", bullets=["a", "b"])]},
                {"name": "02_Odak", "title": "Odak", "content": [
                    sl("section", "Odak", body="."),
                    sl("content", "Bolunme maliyeti", body="Her bolunme 23 dakika."),
                    {"kind": "question", "prompt": "Soru?"}]},
                {"name": "03_Plan", "title": "Plan", "content": [
                    sl("content", "Haftalik blok", body="Takvimde blok acin.")]},
                {"name": "04_Sinir", "title": "Sinir", "content": [
                    sl("statement", "Hayir demek", body="."),
                    sl("bullets", "Ozet", bullets=["a"])]},
                {"name": "05_Kapanis", "title": "Kapanis", "content": [
                    sl("content", "Kapanis", body="Bir aliskanlik secin.")]},
            ]

        gercek_run_json = builder._run_json
        builder._run_json = lambda *a, **k: (_ for _ in ()).throw(
            builder.StoryError("olcum: model kapali"))
        try:
            for kip, en_az, en_cok in [("otomatik", 2, 6), ("kapak", 1, 1),
                                       ("yok", 0, 0)]:
                sahneler = _kurs()
                builder._medya_plani(sahneler, {"title": "Zaman", "media": kip},
                                     "brief", "sonnet", lambda t: None)
                konan = [(sc["name"], sp) for sc in sahneler
                         for sp in sc["content"] if sp.get("medya")]
                olc(f"{kip}: istek sayisi araliginda",
                    en_az <= len(konan) <= en_cok,
                    f"{len(konan)} istek: " + ", ".join(s["title"] for _, s in konan))
                olc(f"{kip}: sahne basina en fazla bir",
                    len({ad for ad, _ in konan}) == len(konan),
                    ", ".join(ad for ad, _ in konan) or "-")
                olc(f"{kip}: yalnizca yer ayrilan duzenlerde",
                    all(builder._medya_yeri_var(s.get("layout"), s)
                        for _, s in konan),
                    ", ".join(s.get("layout") for _, s in konan) or "-")
                if kip == "kapak":
                    olc("kapak: secilen slayt kapak",
                        konan and konan[0][1].get("layout") == "cover",
                        konan[0][1]["title"] if konan else "-")
                if kip == "otomatik":
                    olc("otomatik: tarif modelsiz de yazildi",
                        all(len(s["medya"]["aciklama"]) >= 20 for _, s in konan),
                        f"en kisa {min(len(s['medya']['aciklama']) for _, s in konan)} harf")

            # Modelin kendi yazdigi istek KORUNUR: konuyu bilerek yazilmis bir
            # siparis, mekanik yedekten iyidir.
            sahneler = _kurs()
            sahneler[2]["content"][0]["medya"] = {
                "tur": "video", "saniye": 25,
                "aciklama": "Ekranda takvim uygulamasi, haftalik blok aciliyor."}
            builder._medya_plani(sahneler, {"title": "Zaman"}, "brief", "sonnet",
                                 lambda t: None)
            korunan = sahneler[2]["content"][0]["medya"]
            olc("modelin istegi korunuyor",
                korunan["tur"] == "video" and korunan["saniye"] == 25,
                f"{korunan['tur']} · {korunan['saniye']} sn")
        finally:
            builder._run_json = gercek_run_json

        # Kurucunun kendi yazdigi kapak istegi de ayni kapidan gecmeli.
        print()
        print("kapak tabani")
        taban = builder._kapak_istegi(
            {"title": "Zaman Yonetimi", "audience": "Yeni yoneticiler"}, "brief")
        gecen = builder._medya_istegi({"medya": taban})
        olc("kurucunun kapak istegi kapidan geciyor", gecen is not None,
            (taban["aciklama"][:60] + "…"))
        olc("baslik yoksa brief'ten turetiliyor",
            "siber" in builder._kapak_istegi({}, "siber guvenlik egitimi")["aciklama"],
            "brief'in ilk kelimeleri")

        pkg = StoryPackage(hedef)
        slaytlar = sorted(model.slide_index(pkg))
        if len(slaytlar) < 2:
            raise SystemExit(f"{kaynak.name}: en az iki slayt gerekiyor.")
        s1, s2 = (s.rsplit("/", 1)[1] for s in slaytlar[:2])

        # Kurucunun yazdigi defterin aynisi: alan compose_slide'dan gelir.
        alan = {"x": 54.0, "y": 0.0, "w": 46.0, "h": 100.0}
        istekler = [
            defter.istek(s1, "01_Giris", "MFA nasil calisir", "video",
                         "Telefonda dogrulama bildirimi ve onay dokunusu.",
                         saniye=20, alan=alan, stil="bleed", sira=1),
            defter.istek(s2, "02_Parola", "Acik birakilmis ekran", "gorsel",
                         "Masada kilitlenmemis bir dizustu, ofis arka planda.",
                         alan=None, stil="panel", sira=2),
        ]
        defter.yaz(hedef, istekler)

        # OLCU: siparisin icindeki sayi. Yanlissa kimse fark etmez -- dosya
        # gelene kadar gorunmez, geldiginde de "biraz kirpilmis" gorunur.
        print("\nolcu ve kopyalanacak metin")
        sahne_px = settings.story_size(pkg)
        olc("kurs boyutu okundu", sahne_px[0] > 0 and sahne_px[1] > 0,
            f"{sahne_px[0]}×{sahne_px[1]}")
        tam = defter.olcu({"x": 0, "y": 0, "w": 100, "h": 100}, sahne_px)
        olc("tam sayfa alani = kurs boyutu",
            (tam["w"], tam["h"]) == sahne_px, f"{tam['w']}×{tam['h']} {tam['oran']}")
        yarim = defter.olcu({"x": 54, "y": 0, "w": 46, "h": 100}, sahne_px)
        olc("bant alani yuzdeden hesaplandi",
            yarim["w"] == round(sahne_px[0] * 0.46), f"{yarim['w']}×{yarim['h']}")
        olc("yakin oran adiyla aniliyor",
            defter.olcu({"x": 0, "y": 0, "w": 100, "h": 100},
                        (1920, 1080))["oran"] == "16:9", "1920×1080 -> 16:9")
        olc("alan yoksa olcu de yok", defter.olcu(None, sahne_px) is None, "None")

        # SIPARISTEKI ORAN, YERLESIMIN KULLANDIGI ORAN OLMALI. Ikisi ayri
        # kaynaktan geliyordu: siparis projenin bildirdigi boyuttan
        # (settings.story_size), yerlesim slaydin kendi cercevesinden
        # (shapes.slide_size). Olculdu 2026-08-29 (denee.story): proje
        # 1920x1080 bildiriyor, slayt 720x540 -- kullaniciya 16:9 istendi,
        # gelen 16:9 gorselin kenarindan %25 kirpildi.
        buyuk = calisma / "buyuk_proje.story"
        shutil.copy2(hedef, buyuk)
        bpkg = StoryPackage(buyuk)
        settings.set_story_size(bpkg, 1920, 1080)
        bpkg.save(buyuk, backup=False)
        bpkg = StoryPackage(buyuk)
        proje = settings.story_size(bpkg)
        slayt_px = defter.slayt_olcusu(bpkg, s1)
        olc("proje boyutu ile slayt cercevesi ayrisabiliyor",
            tuple(proje) != tuple(slayt_px), f"proje {proje} / slayt {slayt_px}")
        olc("siparis SLAYDIN cercevesini kullaniyor",
            defter.olcu({"x": 0, "y": 0, "w": 100, "h": 100}, slayt_px)["oran"]
            == defter._oran_adi(*slayt_px),
            f"{slayt_px[0]}×{slayt_px[1]}")

        metin = defter.prompt(defter.istek(
            s1, "01", "Kapak", "gorsel", "Dagınık bir masada oturan yonetici.",
            alan={"x": 0, "y": 0, "w": 100, "h": 100}, stil="hero",
            sahne_px=sahne_px))
        olc("kopyalanacak metin boyutu tasiyor",
            f"{tam['w']}×{tam['h']}" in metin and metin.startswith("Dagınık"),
            metin[-72:])
        video_metni = defter.prompt(defter.istek(
            s1, "01", "MFA", "video", "Telefonda onay dokunusu.", saniye=20,
            alan={"x": 54, "y": 0, "w": 46, "h": 100}, stil="bleed",
            sahne_px=sahne_px))
        olc("videoda sure de yaziyor", "20 saniye" in video_metni,
            video_metni[-40:])

        print("\ndefter")
        yol = defter.dosya(hedef)
        olc("defter kursun yaninda", yol.is_file(), yol.name)
        okunan = defter.oku(hedef)
        olc("iki istek bekliyor", defter.bekleyen_sayisi(okunan) == 2,
            f"{len(okunan)} kayit")
        olc("kurs yolu defterde",
            json.loads(yol.read_text(encoding="utf-8"))["kurs"].endswith("akis.story"),
            "kurs alani")

        print("\nuygulama")
        rapor = defter.uygula(hedef, [
            {"id": "m01", "dosya": str(video)},
            {"id": "m02", "dosya": str(gorsel)},
        ])
        olc("ikisi de eklendi", len(rapor["eklendi"]) == 2,
            ", ".join(e["dosya"] for e in rapor["eklendi"]))
        olc("bekleyen kalmadi", rapor["kalan"] == 0, f"kalan {rapor['kalan']}")
        olc("paket dogrulandi", rapor["verified"]["ok"],
            f"{len(rapor['verified']['problems'])} sorun")

        with zipfile.ZipFile(hedef) as z:
            kok1 = ET.fromstring(z.read(f"story/slides/{s1}"))
            kok2 = ET.fromstring(z.read(f"story/slides/{s2}"))
        etiket1 = {s.tag for liste in kok1.iter("shapeLst") for s in liste}
        etiket2 = {s.tag for liste in kok2.iter("shapeLst") for s in liste}
        olc("video ISTEDIGI slaytta", "video" in etiket1 and "video" not in etiket2,
            f"{s1}: video, {s2}: yok")
        olc("gorsel ISTEDIGI slaytta", "pic" in etiket2, f"{s2}: pic")

        # Video, modelin ayirdigi bandin icinde mi (bleed: sagdan %54, tam boy)
        vid = [s for liste in kok1.iter("shapeLst") for s in liste
               if s.tag == "video"][0]
        boy = vid.find("sldSz")
        genislik, yukseklik = float(boy.get("w")), float(boy.get("h"))
        loc = vid.find("loc")
        sol = float(loc.get("l")) / genislik * 100
        sag = float(loc.get("r")) / genislik * 100
        ust = float(loc.get("t")) / yukseklik * 100
        alt = float(loc.get("b")) / yukseklik * 100
        olc("video ayrilan alanin icinde",
            sol >= alan["x"] - 0.5 and sag <= alan["x"] + alan["w"] + 0.5
            and ust >= -0.5 and alt <= 100.5,
            f"x {sol:.1f}–{sag:.1f}% (alan {alan['x']}–"
            f"{alan['x'] + alan['w']}%), y {ust:.1f}–{alt:.1f}%")
        olc("dikeyde ortalanmis", abs((ust) - (100 - alt)) < 0.5,
            f"ust {ust:.1f}% / alt bosluk {100 - alt:.1f}%")

        # KOMUT YOLU: ajan da ayni deftere yazabilmeli. Bu kanal yokken ajan
        # "video bu araç setinde desteklenmiyor" diyordu (kullanici bildirdi,
        # 2026-08-29) -- arac yoktu, dolayisiyla cevap dogruydu.
        print()
        print("komut yolu (MCP request_media)")
        from storyline_mcp import server
        yanit = server.request_media(
            str(hedef), s2, "video",
            "Ekranda takvim uygulamasi, haftalik blok planlama yapiliyor.",
            seconds=25)
        olc("ajan siparis birakabiliyor", yanit["istek"]["tur"] == "video",
            f"{yanit['istek']['id']} · {yanit['bekleyen']} bekleyen")
        olc("sahne ve baslik dosyadan okundu",
            bool(yanit["istek"]["slayt"]) and yanit["istek"]["baslik"] != "",
            f"{yanit['istek']['sahne']} · {yanit['istek']['baslik']}")
        defter.atla(hedef, yanit["istek"]["id"])   # olcum bitti, defteri birak

        # OKUNABILIRLIK. Tam sayfa bir fotografin ustundeki yazi, arada ortu
        # yoksa okunmuyor -- olculdu 2026-08-29: beyaz baslik aydinlik bir ofis
        # fotografinin uzerinde kayboldu. Kurucu kapakta ortuyu ciziyor ama
        # gorsel komut yolundan da, bu sekmeden de gelebiliyor; garanti
        # uygulamanin kendisinde olmali.
        print("\nokunabilirlik ortusu")
        # ORTUSUZ bir kapak kurulur (image_area verilmez, yani compose ortu
        # cizmez) ve gorsel sonradan tam sayfa olarak konur. Kullanicinin
        # kursunda tam bu durum vardi: fotograf geldi, ortu yoktu, beyaz baslik
        # aydinlik fotografin uzerinde kayboldu.
        pkg_h = StoryPackage(hedef)
        sablon_h = min((t for t in authoring.list_templates(pkg_h)
                        if t["kind"] == "content"),
                       key=lambda t: t["text_shapes"])["slide"]
        yeni_h = authoring.add_slide(pkg_h, sablon_h, name="ortu-testi")
        compose.compose_slide(pkg_h, yeni_h["new_slide"], "cover",
                              title="Kapak Basligi", body="Bir cumle.",
                              clear=True)
        pkg_h.save(hedef, backup=False)
        s3 = yeni_h["new_slide"]
        kapak = defter.istek(s3, "01_Giris", "Kapak", "gorsel",
                             "Tam sayfa kapak fotografi, uzerinde yazi olmasin.",
                             alan={"x": 0, "y": 0, "w": 100, "h": 100,
                                   "behind": True},
                             stil="hero", sira=3)
        defter.yaz(hedef, defter.oku(hedef) + [kapak])
        defter.uygula(hedef, [{"id": "m03", "dosya": str(gorsel)}])
        pkg_o = StoryPackage(hedef)
        kok_o = pkg_o.parse(pkg_o.slide_part_for(s3))
        adlar = [s.get("name") for s in kok_o.find("shapeLst")]
        etiketler = [s.tag for s in kok_o.find("shapeLst")]
        olc("gorselin ustune ortu kondu", "Ton" in adlar and "Ortu" in adlar,
            ", ".join(str(a) for a in adlar[:6]))
        if "Ton" in adlar:
            olc("sira: gorsel -> ortu -> yazi",
                etiketler.index("pic") < adlar.index("Ton")
                and adlar.index("Ton") < max(
                    (i for i, t in enumerate(etiketler) if t == "textBox"),
                    default=10**6),
                f"pic z={etiketler.index('pic')}, Ton z={adlar.index('Ton')}")
        ikinci = compose.ensure_scrim(pkg_o, s3)
        olc("ikinci kez ortu koymaz", not ikinci["eklendi"], ikinci.get("sebep", ""))

        # Golge tasiyan opak bir serit ORTU SANILMASIN: olcum <bG> agacinin
        # tamamina bakiyordu ve altin sari bir seridin golge alpha'sini ortu
        # sanip gercekten ortusuz bir slaydi "ortulu" ilan ediyordu.
        golgeli = [s for s in kok_o.find("shapeLst")
                   if s.get("name") == "Kose" or (s.tag == "rect"
                                                  and s.find("bG/shdw") is not None)]
        if golgeli:
            olc("golgeli opak serit ortu sayilmiyor",
                not shapes._saydam_dolgu(golgeli[0]), golgeli[0].get("name") or "rect")

        print("\ndefter, uygulamadan sonra")
        sonra = defter.oku(hedef)
        olc("ikisi de 'eklendi'",
            all(i["durum"] == "eklendi" for i in sonra),
            ", ".join(f"{i['id']}:{i['durum']}" for i in sonra))
        olc("secilen dosya kayitli",
            all(i.get("dosya") for i in sonra),
            ", ".join(Path(i["dosya"]).name for i in sonra))
        once = len(defter.oku(hedef))
        kalan = defter.atla(hedef, "m01")
        olc("atla bir istegi dusuruyor", len(kalan) == once - 1,
            f"{once} -> {len(kalan)} kayit")
        defter.temizle(hedef)
        olc("yeniden kurulum defteri siliyor", not defter.dosya(hedef).is_file(),
            "defter yok")

    print()
    if hatalar:
        print(f"BASARISIZ: {len(hatalar)} olcu -- " + "; ".join(hatalar))
        return 1
    print("Hepsi gecti.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
