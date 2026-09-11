"""Ayak defteri: beyan TEK DEĞER, satırlar ondan basılır.

NICIN VAR. Kapilarin ayak sayisi bir sure IKI YERDE duruyordu: modul
duzeyindeki `AYAKLAR` beyani, ve kapinin gercekten bastigi satirlar.
`tools/ayirt_kapi.py` boleni beyandan okuyordu ve bakim TEK YONLUYDU --
tohum beyanda olmayan bir ayagi adlandirirsa kirmizi doner. Ters yon
DENETLENMIYORDU: kapi yeni bir ayak KAZANIR, kimse beyana eklemez,
bolen ayni kalir ve kapsam OLDUGUNDAN IYI gorunur (9/34 diye okunur,
oysa 9/35). Tam da o araci kapsami gorunur kilmak icin yazmistik.

COZUM "BASILAN SATIRLARDAN TURET" DEGIL: o, defteri bir GORUNTULEME
bicimine baglamak olurdu -- bu depoda yedi kez isiran sinif (vekil
olarak duzyazi). Cozum iki defteri TEK DEGERE indirmek: beyan kaynak,
ve satirlar beyandan geciyor. Ayak eklemek beyani degistirmeden MUMKUN
DEGIL, cunku basilan sey beyandan geliyor.

IKI KAYMA YONU DE KAPANIYOR:
    basildi ama beyansiz  -> `yaz()` HATA verir (SystemExit), kapi duser
    beyanli ama basilmadi -> `kosmayanlar()` bitiste bildirir

Ikincisi ayri bir kusur sinifi: beyanda duran ama artik kosmayan bir
ayak, kapsam sayisini SISIRIR ve "olculuyor" sanilir.

GOC BLOKLAMADAN: beyani olmayan kapilar `ayirt_kapi` tarafindan
"beyansiz" diye raporlanir ve BOLENE GIRMEZ. Kapsam bugunden durust
kalir, gecis asamali olur, ve eksik kume her kosuda gorunur.

KURALIN EN DAR HALI, ve bu modul onun altyapisi:

    Olctugun sey deponun SAHIP OLDUGU kodsa, ICE AKTAR -- ayristirma.

Beyan zaten bir Python nesnesi; icerine metin olarak bakmak, hesaplanmis
bir sayiyi f-string'e gomup geri aramakla ayni hamle. Bu modulun goc
turunda iki hata da tam olarak oydu: bir desen kaynaktaki `print`
satirlarini cevirirken HUKUM satirlarini da "ayak" sandi, ve bir analiz
betigi `uyari(a)` adindaki parantezde erken kapanip beyani yanlis okudu.
Ikincisi `AYAKLAR.adlar` okunarak duzeldi.

Gerekcenin tamami ve yedi olculmus ornek: `storyline-mcp/README.md`,
"Olcu yazmanin kurali: ice aktar, ayristirma".
"""

from __future__ import annotations


class Defter:
    """Bir kapinin ayaklari. Hem beyan hem yazici.

    `len`, `in` ve iterasyon destekleniyor ki `ayirt_kapi` onu duz bir
    dizi gibi okuyabilsin -- boylece gocte cagiran taraf degismiyor.
    """

    def __init__(self, *adlar: str, genislik: int = 12):
        self.adlar = tuple(adlar)
        self.genislik = genislik
        self.basilanlar: list[str] = []

    def __len__(self) -> int:
        return len(self.adlar)

    def __iter__(self):
        return iter(self.adlar)

    def __contains__(self, ad) -> bool:
        return ad in self.adlar

    def yaz(self, ad: str, metin: str) -> None:
        """Ayagin satirini bas. Beyansiz ad KABUL EDILMEZ.

        Hata SystemExit: kapi calisirken duser ve sebebini yazar. Sessiz
        bir uyari, tam olarak engellemeye calistigi kaymayi uretirdi --
        kimse okumadan ayak eklenir ve bolen geride kalir.
        """
        if ad not in self.adlar:
            raise SystemExit(
                f"BEYANSIZ AYAK: {ad!r} bu kapinin AYAKLAR beyaninda yok. "
                f"Beyan TEK DEGER: satirlar ondan basiliyor ve "
                f"`tools/ayirt_kapi.py` boleni oradan okuyor. Ayagi "
                f"beyana ekleyin (bkz. tools/ayak.py).")
        self.basilanlar.append(ad)
        print(f"{ad:<{self.genislik}}: {metin}")

    def kosmayanlar(self) -> list[str]:
        """Beyanda duran ama bu kosuda BASILMAYAN ayaklar.

        Bos olmasi beklenir. Dolu olmasi iki sey demek olabilir: ayak
        kaldirildi ve beyan guncellenmedi (kapsam sisiyor), ya da ayak
        bir kosulun arkasinda kaldi ve o kosul saglanmadi (o zaman kapi
        zaten "KOSMADI" demis olmali).
        """
        return [a for a in self.adlar if a not in set(self.basilanlar)]
