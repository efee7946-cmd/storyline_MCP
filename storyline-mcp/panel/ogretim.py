"""Iki uretici de ayni ogretim kurallarina uyar. Kurallar BURADA durur.

NICIN AYRI MODUL: bu projede kurs ureten IKI yol var ve ikisi ayri kod
yolundan gecer --

    komut yolu : panel/agent.py    -> SYSTEM_PROMPT + storyline araclari
    brief yolu : panel/builder.py  -> kendi promptlari, arac YOK, JSON'dan
                                      deterministik kurulum

Kurallar bir sure ikisine DAGILMISTI ve bu olculebilir bir kusur uretti
(2026-08-28): "asagidakilerden hangisi kaliplarindan kacin" kurali yalnizca
builder'da vardi. Komut yolundan cikan kursta iki soru "Bu ifade dogru
mudur?" biciminde geldi -- cevap sorunun icinde yaziyordu. Kural YAZILMISTI,
sadece diger yarida duruyordu.

Ayni bicimde ters yon de dogruydu: etkilesim ritmi, oz-degerlendirme ve
sinir vakasi kurallari yalnizca SYSTEM_PROMPT'ta vardi, brief yolu onlari
hic gormuyordu.

Burada YALNIZCA iki yolun da uygulayabilecegi kurallar durur. Yola ozgu olan
kendi promptunda kalir: `audit` cagirmak, katman kurmak ve sonuc slaydi
eklemek yalnizca komut yolunun elindedir (builder arac cagirmaz); secenek
sayisi kisiti ve JSON bicimi yalnizca brief yolunu ilgilendirir.
"""

# ASCII: her iki prompt da bastan sona ASCII ve oyle kalmali.
ORTAK_KURALLAR = """\
- Bir kurs okunan sayfalar dizisi DEGILDIR. Ogrenci ilerlemekten baska bir sey
yapmiyorsa ortaya brosur cikar.
- UC SLAYTTAN FAZLA ARDISIK OKUMA OLMASIN.
- HER KONU SAHNESI en az bir puanli soru tasir. Giris ve kapanis sahneleri
bunun disindadir.
- SORU, SLAYTTAKI CUMLEYI GERI SORMAZ. Iki bicim yasak:
     "... dogru bir uygulamadir." Bu ifade dogru mudur?   cevap sorunun icinde
     "Asagidakilerden hangisi ..."                        ezber yoklamasi
  Yerine KARAR VERDIREN durum sor: kisa bir vaka ver, ogrenci ne yapmali ya
  da iki secenekten hangisi dogru diye sor.
- TANIM VEREN SLAYT SINIR VAKASI TASIR. Kurali yazip gecme: birbirine yakin
iki somut ornek ver ve "hangisi?" diye sor. Dogru/yanlis sorusu bunun yerine
GECMEZ.
- "Sunlari kendinizde fark edin" tipi BES MADDELIK LISTE bir sorudur, madde
degil. Cok dogru cevapli soruya cevir ve feedback'te esigi yorumla ("besten
ucunu isaretlediyseniz...").
- BUTUN SECENEKLERI DOGRU ISARETLEME. Yanlisi olmayan soru puanlanamaz:
herkes tam puan alir ve olcum hicbir sey soylemez. Oz-degerlendirme listesini
de puanlanabilir yaz -- en az iki secenek GERCEKTEN yanlis olsun (yanlis bir
uygulama, ya da konuyla ilgisi olmayan bir belirti). Olculdu 2026-08-28: bu
kural yazili degilken uretilen bir soruda bes secenegin besi de dogru
isaretlendi ve soru hicbir sey olcmedi.
- SORU METNI CERCEVEYE SIGMALI. Bu bir uslup tercihi degil, olculmus bir
tavan: kok ve sikler birlikte cerceveyi yerse soru KURULAMAZ ve puanlanmayan
bir menu slaydina duser -- ogrenci icin o slayt artik bir soru degildir.
     kok    : EN FAZLA 140 karakter (yaklasik iki cumle)
     her sik: EN FAZLA 55 karakter  (tek satirlik bir karar, cumle degil)
  Bes secenekli sorularda sinir daha da dardir; sikki kisaltamiyorsan
  secenek sayisini dusur.
- SIKKIN ICINE GEREKCE YAZMA. Gerekce feedback'e gider, sikka degil. Olculdu
2026-08-29: uretilen bir kursta bir sik 148 karakterdi ("...cihazda uretilir
ve SIM takasi ya da SMS yonlendirme gibi yollarla ele gecirilemez") ve soru
kurulamadi. Ayni soru sik 45 karaktere inince sorunsuz kuruldu.
- VAKAYI SIKKA DEGIL KOKE, KISALTARAK KOY. Iki e-postayi, iki adresi ya da
iki ekran goruntusunu kokun icinde bastan sona yazma; farkin GECTIGI yeri yaz.
Olculdu: 351 ve 278 karakterlik iki kok, secenek sayisindan BAGIMSIZ olarak
(2, 3 ve 5 sikta da) cerceveyi yedi ve ikisi de menuye dustu.
- HER soruya feedback yaz. Ogrenci cevabini verdikten sonra bunu okuyacak;
"Dogru!" gibi bos bir onay degil, KARARIN GEREKCESI olsun. Tek cumle.
- Kapanis slaydi aforizma degil, secilen tek bir SOMUT adim olsun.
- SORU TIPINI DEGISTIR. Uc fiil var ve ucu ayri sey olcer:
     sik sec   (question) -- tek bir karar
     grupla    (drag)     -- her oge icin ayri bir karar; siniflandirma,
                             esleştirme, "hangisi nereye ait" anlatan her
                             bolum bununla yoklanir
     yaz       (commitment) -- ogrenci kendi cumlesini kurar; puanlanmaz
  BASTAN SONA "asagidakilerden hangisi" YAZMA. Bir kursta ikiden fazla
  konu sahnesi varsa EN AZ BIRI drag olsun, ve kurs bir commitment ile
  kapansin. Olculdu 2026-08-30: arac o gune kadar yalnizca "sik sec"
  uretebiliyordu ve kullanicinin bildirdigi sikayet "hep ayni sey cikiyor"
  idi -- tipin kendisi tekduzeligin kaynagiydi, metin degil.
- GRUPLAMA SORUSU DAR: her oge etiketi TEK SATIRLIK bir ad olsun (cumle
  degil, yaklasik 30 karakter). Kutu sayisi 2-4, her kutuya en az iki oge.\
"""
