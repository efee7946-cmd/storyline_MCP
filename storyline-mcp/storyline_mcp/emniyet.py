"""Bu slaydı yeniden bestelemek neyi götürür -- ve götürecekse REDDET.

`compose_slide` slaydi temizleyip bastan cizer. Bos bir slaytta bu
zararsizdir; DOLU bir slaytta elle konmus sekli, soru tetikleyicisini ve
geri bildirim katmanlarini goturur, ve hicbir sey bagirmaz. Kapatilan
kusur sinifi tam olarak bu: ajan bir soru slaydini gorsel icin yeniden
besteler, katmanlar ve gonder tetikleyicisi silinir, cikti "basarili"
doner.

KONTROL TALIMATTA DEGIL EYLEMIN ICINDE. Olcuyu bir MCP araci yapip
"once bunu sor" demek, kurali prompt'a yazmanin baska bir bicimi olurdu:
ajan sormayi unutursa butun zarar geri gelir. Bunun yerine kontrol
`compose_slide`in KENDI icinde kosuyor -- atlanamaz, ve atlandiginda
gorunur (cagri hata firlatir). Ayni olcut `_mark`a uslup baglarken de
kullanildi: iki yolun da gectigi tek nokta.

SOZLUK DONDURULMUS, VE SEBEBI OLCUM. Adlar `tools/yeniden_beste.py`
tarafindan TURETILIYOR -- her duzen x varyant x uslup x uc gorsel durumu
bestelenip ne ad uretiliyorsa o. Ama o tureme 180 kurulum ve ~30 saniye;
her `compose_slide` cagrisinda kosamaz. O yuzden sonuc buraya donduruldu
ve KAYMA RISKINI KAPI ustlendi: `tools/yeniden_beste.py` her kosuda
yeniden turetip bu sabitlerle IKI YONLU karsilastirir. Elle tutulan bir
kopya degil; olculmus bir sabit ve onu dogrulayan bir kapi.

KURUCU YOLU ISIRILMAZ, VE BU DA OLCULDU (2026-09-10): `authoring.add_slide`
taze slaydi sekilsiz, katmansiz ve yalnizca Navigation+Previous ile
birakiyor. Olcut "compose'un koymadigi bir sey var mi" oldugu icin
kapsam kendi kendini sinirliyor -- ayri bir istisna gerekmiyor.
"""

from __future__ import annotations

# OLCULMUS SABITLER. tools/yeniden_beste.py --yaz bunlari uretir, ve ayni
# arac her kosuda yeniden turetip buradakiyle karsilastirir.
SEKIL_SOZLUGU = frozenset({
    "Arka Plan", "Body", "Cizgi", "Display", "Eyebrow", "Gorsel Alani",
    "Kart", "Kenar", "Kose", "Lead", "Numara", "Numeral", "Ortu", "Panel",
    "Serit", "Subtitle", "Title", "Ton", "Vurgu",
})

STANDART_TETIKLEYICILER = frozenset({"Navigation", "Previous"})

# Alani ayrilmis slaytlarin isareti: yalnizca `image_area=True` ile
# ciziliyorlar. `panel` yerlesimi ayirt edici sekil CIZMIYOR (olculdu),
# yani panel ile ayrilmis bir alan buradan taninamaz.
REZERVASYON_SEKILLERI = frozenset({"Gorsel Alani", "Ortu", "Ton"})


def _butonsu(root, el) -> bool:
    """Bu şekil bir buton mu -- ADI KENDI METNINE EŞİT Mİ.

    Buton sekilleri adlarini ETIKETTEN aliyor (`Devam`, `Konu A`), yani
    sozluge giremezler. Tag imzasi DENENDI VE ELENDI: compose'un butonlari
    alti duzende de `roundRect`, yani `Kart` ile ayni tag.
    """
    from . import model
    metin = (model.shape_text(root, el.get("g") or "") or "").strip()
    return bool(metin) and metin == (el.get("name") or "").strip()


def yeniden_beste_engelleri(root) -> list[str]:
    """Bu slaydı yeniden bestelemek NEYI götürür. Boş liste = güvenli.

    Uc ayak, hepsi "bu slaydi compose kurdu ve o gunden beri kimse
    dokunmadi" sorusunun ayri bir yuzu.
    """
    engeller = []

    yabanci = sorted({
        (el.get("name") or "?") for el in list(root.find("shapeLst") or [])
        if not _butonsu(root, el)
        and (el.get("name") or "") not in SEKIL_SOZLUGU})
    if yabanci:
        engeller.append(
            f"compose'un koymadigi {len(yabanci)} sekil var ({', '.join(yabanci[:4])})"
            " -- elle eklenmis ya da tohumdan devralinmis icerik silinir")

    fazla = sorted({
        (tr.get("name") or "(adsiz)")
        for tr in list(root.find("trigLst") or [])
        if (tr.get("name") or "") not in STANDART_TETIKLEYICILER})
    if fazla:
        engeller.append(
            f"standart gezinme disinda {len(fazla)} tetikleyici var "
            f"({', '.join(fazla[:4])}) -- soru ya da katman baglantisi kirilir")

    # KATMAN GITMEZ, SAHIPSIZ KALIR -- VE MESAJ BUNU BOYLE SOYLEMELI
    # (olculdu 2026-09-10, bos.story + add_question, yeniden beste sonrasi):
    #     katman            3 -> 3      katman ici sekil  6 -> 6
    #     slayt sekli       9 -> 4      intrProps         1 -> 0
    #     tetikleyici       1 -> 0      (SubmitInteraction silindi)
    # Yani asil kayip KATMAN degil ETKILESIM: soru soru olmaktan cikar,
    # katmanlar dosyada durur ama onlari acacak hicbir sey kalmaz. Mesaj
    # "katmanlari goturur" diyordu; bunu okuyan ajan katmanlari yedekleyip
    # devam etmeyi cozum sanabilirdi.
    katman = root.find("sldLayerLst")
    if katman is not None and len(katman):
        engeller.append(
            f"{len(katman)} geri bildirim katmani var -- yeniden besteleme "
            f"katmanlari dosyada birakir ama onlari ACAN her seyi siler "
            f"(soru tetikleyicisi ve etkilesim tanimi dahil): katmanlar "
            f"sahipsiz kalir")

    return engeller


def alan_ayrilmis(root) -> bool:
    """Bu slaytta görsel için yer ZATEN ayrılmış mı."""
    return any((el.get("name") or "") in REZERVASYON_SEKILLERI
               for el in list(root.find("shapeLst") or []))
