# Ilerleme katmani: olcum kaydi

Tarih: 2026-09-04
Konu: kurucunun urettigi kurs neden PowerPoint'e benziyordu, ve ne baglandi.

## 0. Tespit

Kullanici bildirdi: "iyi moduller olusmuyor, direkt powerpoint dosyalari gibi".

builder.py'nin cagirdigi TUM modul fonksiyonlari dokuldu:

    add_slide + compose_slide                 statik metin duzenleri
    add_question / add_drag_question /
    add_text_question / add_hotspot_question  dort soru tipi
    create_scene, promote_scenes, medya.*

`logic.*` cagrisi: SIFIR. Yani degisken, kosul ve tetikleyici katmani
yazilmis, olculmus ve uretim hattina HIC baglanmamisti. logic.py'nin kendi
baslik cumlesi eksigi zaten yaziyordu: "Without them a deck can only be read
front to back."

Ayrica: pedagogy.olc ("ogrenci bir sey yapiyor mu") uretim yolundan hic
cagrilmiyordu. Build raporunun her alani BICIM olcuyordu (variety,
question_looks, verified) -- kursun davranisina bakan hicbir sayi yoktu.

## 1. Zincir probu (uretim koduna gecmeden ONCE)

test/bos.story uzerinde: degisken -> kosullu tetikleyici -> sonuc slaydi.

    ONCE   etkilesimli_slayt=12  toplam_tetikleyici=84
    SONRA  etkilesimli_slayt=13  toplam_tetikleyici=95  sonuc_slaydi bulundu
    KAYIT  ok=True  sorun=0

Kilit probu ayrica kosuldu: add_layer -> show_layer -> kosul, kayit ok=True.

## 2. Uctan uca: tools/produced.py (model cagrisi YOK)

ILK KOSUM ilerleme katmani bagliyken:

    ilerleme: 3 degisken, 4 tetikleyici, sonuc slaydi KURULAMADI
    atlanan : "sonuc slaydi: Sahne bulunamadi: '99_Sonuc'"
    kusur   : cakisma 1, taban 1, kontrast 4     (taban cizgisi: kontrast 4)

Iki YENI kusur cikti. Kaynak arandi ve UC ayri kusur bulundu:

### 2a. Benim kusurum
`clone.install_slide` sahneyi OLUSTURMAZ, var olmasini bekler. ilerleme.py
sahneyi kurmadan sonuc slaydi istedi. Cozum: `clone.create_scene` once.

### 2b. install_slide'in kusuru (bu oturumda ortaya cikti, benden onceki)
Sahne cozumlemesi parca/rels/content-type/story-rel YAZILDIKTAN SONRA
duruyordu. Var olmayan sahne adi verildiginde cagri DOGRU sekilde patliyor
ama paket kirli kaliyor: kaydedilmis ama hicbir sahnenin sldIdLst'inde
olmayan bir slayt. Olculdu: kurs 55 yerine 56 slaytla kaydedildi ve o
SAHNESIZ slayt iki kusur uretti (cakisma 1, taban 1). Kaynagi gorunmez,
cunku hicbir sahnede degil.

Cozum: cozumleme hicbir sey yazilmadan ONCE. Salt-okunur, yan etkisi yok.

### 2c. seeds/results.xml'in geometrisi (hic kullanilmamisti)
Sonuc slaydi tohumunun kendi yerlesiminde iki kusur vardi. Builder daha once
hic sonuc slaydi eklemedigi icin hic ortaya cikmamislardi:

    "Gecme Puani: %Quiz_Result.PassPoints%"  b=1067 -> %98.8   (FLOOR %92)
    "SONUC" [47,22,821,103] X "Degerlendirme Sonucu" [602,59,1421,155]

Cozum: ortalanmis "Gecme Puani" kutusu 110 birim yukari (b=957, %88.6);
"SONUC" kutusu daraltildi (r=821 -> 560). SONUC metni SOLA hizali (olculdu),
yani kutu daralinca gorunum degismez.

## 3. Sonuc slaydinin gec/kal kosullari OLU idi

Kurulan sonuc slaydinda iki trigCond'un varG'si pakette YOKTU:

    varG  903b3800  -> hedefte yok      (tohumun hasat edildigi projeninki)
    varG2 d0d815e0  -> hedefte yok

Bunlar slayt icinde degil story.xml'de yasayan YERLESIK degiskenler, yani
install_slide'in GUID yenilemesi onlara dokunmuyor; tohum yabanci GUID'i
oldugu gibi tasiyor. Sonuc: slayt goruntuleniyor, "gectiniz/kaldiniz"
katmanlarini acacak kosullar hicbir zaman dogru donmuyor.

Kosullar `dataType="var"` -- skoru gecme puaniyla karsilastiriyorlar.
Cozum: authoring._sonuc_degiskenlerini_bagla, kurulumdan sonra iki GUID'i
hedefin Results.ScorePoints / Results.PassPoints'ine baglar.

Dogrulandi: kopuk referans 2 -> 0.

## 4. Son durum

    ilerleme: 3 degisken, 5 tetikleyici, sonuc slaydi slide38.xml
              sahne 99_Sonuc, kilit esigi 2 bolum, atlanan YOK
    kusur   : kontrast 4 + 3 slayt kurulamadi   == TABAN CIZGISI

Tetikleyici sirasi dogrulandi (sira YUK TASIYOR -- ters sira sessizce
calismaz gorunur):

    OnStart adjustVar Ilerleme:add        EGER Dinleme_Tamam eq False
    OnStart adjustVar Dinleme_Tamam:ass

## 5. Suit: benim degisikliklerim yeni kapi DUSURMEDI

`git stash` ile uc dosyam geri alinip taban alindi. Bes kirmizi kapinin
BESI de tabanda da kirmizi:

    invariants    exit=1  ayni "YENI KIRIK" satirlari
    deadband      exit=1
    golden        exit=1  "Yigin davranisi degisti"
    themes_check  exit=1  6 tema, 24 sorun
    produced      exit=1  kontrast 4 + 3 slayt (tabanla AYNI)

## 6. Kapanmayan

- slideb.xml'de 2 kopuk kosul referansi kaldi. DEVRALINAN sahne (SINAV),
  kullanicinin kendi kaynak dosyasindan geliyor -- dokunulmadi.
- Yukaridaki bes kapi tabanda kirmizi ve bu oturumda ele alinmadi.
- Ogretim olcusu (pedagogy.olc) rapora BAGLANDI ama KAPI DEGIL. Dusuk sayi
  kursu reddetmiyor. Kapiya cevirmek ayri bir karar; once uretilen
  kurslarda bu sayinin ne dagilim verdigi gorulmeli.

## 7. Storyline acilma testi (tools/open_test.py)

    kanarya: saglam=acildi  bozuk=acilmadi  [GUVENILIR]
    uretilmis.story          ACILDI  EVET   10.5 sn   baslik 'uretilmis.story'

Kanarya iki kontrolu de gecti, yani verdict guvenilir: aracin kendisi
"acilmadi" diyemeyecek durumda degildi ve negatif kontrol de olu degildi.

KAPSAM -- bu test NE SOYLEMEZ: dosyanin acilmasi tetikleyicilerin CALISTIGI
anlamina gelmez. pedagogy.py'nin kendi kapsam cumlesi ayni ayrimi yaziyor:
"TETIKLEYICI YAZILDIGI GIBI SAYILIYOR, ATESLEDIGI GIBI DEGIL".

Bu katman icin durum digerlerinden IYI ama tam degil:

  OnStart          17 event icinde preview'da tetiklendigi GORULEN iki
                   event'ten biri (digeri OnVariableValueChange). Kurulan
                   bes tetikleyicinin BESI de OnStart kullaniyor.
  adjust_variable  Preview'da olculdu (sayi hassasiyeti turlerinde
                   calistirildi -- 7 anlamli basamak olcusu buradan geliyor).
  condLst kosulu   PREVIEW'DA DOGRULANMADI. Kodda kosul dogru yaziliyor,
                   dosya aciliyor, ama "Ilerleme yalnizca ilk geliste
                   artiyor" ve "kilit yalnizca eksikken aciliyor"
                   davranislari GORULEREK olculmedi.

Yani kalan bilinmeyen tek ve dar: kosullarin calisma aninda degerlendigi.
Bir sonraki adim bunu Preview'da olcmek olmali -- iki gelis, sayacin 2
degil 1 olmasi.

## 8. EN AGIR BULGU: uretilen icerik slaytlari kendiliginden atliyordu

Kullanici Preview'da bildirdi: "herhangi bir scene'de herhangi bir slayda
basinca o scene'deki son slayta atiyor, hemen asagi iniyor".

Olculdu, uretilmis.story:

    OnStart -> jumpToSlide (actSubType=next) tasiyan slayt: 34
      kurucunun urettigi sahnelerde : 12
      devralinan sahnelerde         : 22

Yani icerik slaydi acilir acilmaz sonrakine atliyor; zincir boyle bir
tetikleyicisi OLMAYAN ilk slayda -- sahne sonundaki soru slaydina -- kadar
suruyor. Yazilan butun icerik ogrenciye HIC gorunmuyordu.

KAYNAK bulundu, test/bos.story uzerinde:

    builder._content_template(pkg) -> slide.xml
    slide.xml slayt duzeyi tetikleyicileri:
        event=OnClick  action=submitInteraction  subType=next
        event=OnStart  action=jumpToSlide        subType=next

`_content_template` sablonu "en az metin sekli olan" olcutuyle seciyor ve bu
olcut DAVRANISA BAKMIYOR. add_slide tetikleyicileri de klonladigi icin her
icerik slaydi otomatik ilerlemeyi devraldi. bos.story'nin kendisinde 37
slaydin 22'sinde bu tetikleyici var, yani secilme ihtimali yuksekti.

CARE: builder._otomatik_ilerlemeyi_kaldir -- add_slide'dan hemen sonra,
YALNIZCA kurucunun kendi olusturdugu slaytta, YALNIZCA slayt duzeyinde,
YALNIZCA OnStart+jumpToSlide.

  DOKUNULMAYANLAR ve gerekceleri:
    OnNextButtonClick -> jumpToSlide   ogrencinin ileri tusu; gezinmenin kendisi
    sekil uzerindeki tetikleyiciler    bir butonun atlamasi istenen olabilir
    devralinan slaytlar                kullanicinin dosyasindaki slaytlar onun

DOGRULANDI:
    kurucunun urettigi slaytlarda otomatik ilerleme : 12 -> 0
    devralinan slaytlarda (dokunulmadi)             : 22 -> 22
    produced.py kusur                               : tabanla AYNI (kontrast 4 + 3 slayt)
    acilma testi                                    : ACILDI 12.0 sn

## 9. Yan bulgu: uretilen kurslarda PLAYER MENUSU KAPALI

playerProps.xml, test/bos.story'den devralinan:

    outline    (Menu)      value=false
    glossary   (Glossary)  value=false
    transcript (Notes)     value=true
    resources  (Resources) value=false

Menu kapali oldugu icin ogrenci nerede oldugunu goremiyor ve bolumler
arasinda gezinemiyor. Bu, olcumu de engelledi: kullanici ayni slayda ikinci
kez giremedi.

Bu bir SABLON AYARI, kod kusuru degil -- bilerek kapatilmis olabilir. Bu
yuzden builder'da DEGISTIRILMEDI; yalnizca olcum dosyasinda acildi.
Kalici acilmasi kullanicinin karari.

## 10. Olcum dosyasi v2

    C:\Users\erman\Desktop\Art\test\olcum2.story

  - otomatik ilerleme kaldirilmis (kurucu slaytlarinda 0)
  - player menusu ACIK
  - uc slaytta okunur bant: 02_Dinleme sonu, 03_Sinir sonu, 99_Sonuc
  - acilma dogrulandi: EVET 10.5 sn

ILK YARI ZATEN OLCULDU (kullanicinin ekran goruntusu, v1):

    [OLCUM] 02_Dinleme sonu | Ilerleme = 1 | Dinleme=true Sinir=false

Bu uc seyi kanitliyor: %Ilerleme% referansi render oluyor; sayac ilk giriste
TAM BIR KEZ artti (tetikleyici zinciri calisma aninda atesliyor); bayraklar
bagimsiz (Sinir hala false).

KALAN TEK BILINMEYEN: ayni slayda IKINCI kez girildiginde kosul sayaci 2'ye
cikmayi engelliyor mu.

## 11. Kosul: calisma ani OLCULEMEDI, yapisal kanit ALINDI

HEDEF: kosullarin calisma aninda degerlendigini GORMEK.

Preview otomasyonu DENENMEDI ve sebebi kayda gecti:
  * tools/shoot_preview.py ise `open_test.force_close()` ile basliyor --
    Storyline'i OLDURUYOR. O sirada kullanicinin Storyline'inda ACIK BIR
    ILETISIM KUTUSU vardi (nazik kapatma denemesi bu yuzden basarisiz oldu),
    ve onu zorla oldurmek kullanicinin oturumunu onun adina atmak olurdu.
  * Aracin KENDI belgesi zaten diyor ki bu olcumu su an veremiyor
    (2026-08-17): oldurulen oturumun cokus raporu bir sonraki acilista
    cikiyor ve otomasyon kendi cop izini olcuyor.

Bunun yerine GUI GEREKTIRMEYEN kanit toplandi: gercek yazarlarin yaptigi
bagisci dosyalarda ayni yapi var mi.

    bagiscilardaki KOSULLU tetikleyici toplami : 105
      Dials_Starter_Kit    OnDialTurns  changeShapeState   77
      DragDrop_5_vFINAL1   OnStart      changeShapeState   11   <-- OnStart!
      DragDrop_5_vFINAL1   OnClick      changeShapeState   10
      DragDrop_5_vFINAL1   OnClick      Move                5
      DragDrop_5_vFINAL1   OnClick      showSubSlide        2   <-- kilidin sekli

  * OnStart uzerinde kosul GERCEK dosyalarda var (11 ornek).
  * showSubSlide uzerinde kosul GERCEK dosyalarda var (2 ornek) -- kilit
    tetikleyicimin birebir sekli.
  * adjustVar uzerinde kosul bagisci havuzunda YOK. Yani sayacin kendi
    kombinasyonu icin bagisci kaniti yok.

XML KARSILASTIRMASI, benim urettigim trigCond ile bagiscininki:

    oznitelik sayisi   13  vs  13
    BAGISCIDA VAR BENDE YOK : yok
    BENDE VAR BAGISCIDA YOK : yok
    yapisal alanlarin HEPSI ayni degerde
      (andOr=and, dataType=value, lightBox=false, op=eq,
       strVal1/2 bos, floatVal1/2=0)
    farklar yalnizca GUID'ler ve boolVal (karsilastirilan degerin kendisi)

YOLDAS ALAN RISKI OLCULDU. Bagiscinin varG2'si DOLU, benimki NULL:

    dataType=value   varG2=dolu   94
    dataType=value   varG2=NULL    4   <-- benim seklim
    dataType=state   varG2=dolu   10
    dataType=state   varG2=NULL    5

Yani benim seklim (value + NULL varG2) gercek dosyalarda DORT kez geciyor --
Storyline'in kendi yazdigi bir bicim, bozuk degil. Ama AZINLIK bicim (98'de
4), dolayisiyla o dortunun islevsel oldugu KANITLANMIS degil. varG2'yi
doldurmak DENENMEDI: value karsilastirmasinda neyi gostermesi gerektigi
bilinmiyor ve tahmin etmek, olculmemis bir alani uydurmak olurdu.

DURUM, tek cumle: kosulun XML'i gercek dosyalarla ozdes ve kullandigim
event/action kombinasyonlarinin ikisi bagiscilarda dogrulaniyor; kosulun
CALISMA ANINDA degerlendigi hala GORULMEDI.

KAPATMANIN YOLU (insan gerektirir, ~1 dakika):
    test/kosul_probu.story  -- tek giriste olcer, GEZINME YOK
    kurs slide26.xml ile aciliyor, bant:  A=%PA%  B=%PB%
        A=0 B=1  kosullar dogru degerleniyor   <- beklenen
        A=1 B=1  kosullar yok sayiliyor
        A=0 B=0  kosullu tetikleyici hic ateslemiyor

## 12. DALLANMA: yanlis cevap artik bir yere goturuyor

TESPIT. Uretilen soru slaydinda yanlis cevabin sonucu HICBIR SEYDI:

    katman[0]  Button  OnClick -> jumpToSlide(next)    dogru: devam
    katman[1]  Button  OnClick -> hideSubSlide(me)     yanlis: kapat, kal

EKSIK PRIMITIF. logic.add_trigger tetikleyiciyi slayda ya da bir SEKLE
baglayabiliyordu; katmanin KENDISINE baglayamiyordu. Yani "yanlis katman
acilinca sunu yap" kurulamiyor, ancak ogrenci bir seye TIKLARSA is
yapilabiliyordu. `owner_layer` parametresi eklendi (katman GUID'i ya da adi).
Sekil aramasi da o katmanla SINIRLANIYOR -- ayni adi tasiyan baska bir
katmandaki sekle baglanmak sessiz bir yanlis hedef olurdu.

KIMLIK TESPITI -- SEZGI YANLIS CIKTI. "katman[1] yanlistir" varsayimi uc
soru ailesinden BIRINDE ters:

    slide29 (dragDrop)      katman[0]=Dogru   katman[1]=Yanlis
    slide2d (freePickMany)  katman[0]=YANLIS  katman[1]=Dogru    <-- TERS
    slide32 (freePickOne)   adlar dolu: 'Dogru Cevap' / 'Yanlis Cevap'

Siraya guvenseydik freePickMany ailesinde DOGRU cevap veren ogrenciyi
telafiye gonderirdik. Yetkili kaynak bulundu:

    <intrProps corFbG="..." incFbG="..." />

SIRA: intrProps -> katman adi -> ATLA VE RAPOR ET. Ucuncu basamak onemli:
yanlis katmana baglamaktansa hic baglamamak.

KAPSAM OLCULDU (uretilmis kurs):
    kurucunun soru slaytlari : 4/4 tanindi (intrProps 3, ad 1)
    devralinan slaytlar      : 4 taninmadi -- zaten dokunulmuyor

NE KURULUYOR, sahne basina:
    <Bolum>_Hata (bool)   yanlis katman ACILINCA kalkar (katman tetikleyicisi,
                          butonun degil -- butona baglansaydi ancak ogrenci
                          tiklarsa kayit olurdu)
    "Konuya don" butonu   yanlis katmanda, sahnenin ILK slaydina atlar

BUTON YERI OLCULEREK KONUYOR, sabit degil: iki ailede mevcut buton iki ayri
yerde (x=41.4% y=65.4% ile x=68.2% y=85.8%). Sabit koordinat, ailelerden
birinde mevcut butonun ustune binerdi. Yeni buton mevcut butonun SOLUNA,
ayni hizada ve ayni boyda konuyor; yer yoksa buton kurulmuyor ve bayrak
tek basina kaliyor (rapora yazilarak).

DOGRULANDI, uretilmis kursta:

    slide2d  katman[0] <<< YANLIS (intrProps)  OnStart->adjustVar(Dinleme_Hata)
                 "Konuya don" -> slide2a.xml   (02_Dinleme'nin ilk slaydi)
    slide32  katman[1] <<< YANLIS (ad)         OnStart->adjustVar(Sinir_Hata)
                 "Konuya don" -> slide2f.xml   (03_Sinir'in ilk slaydi)

    dogru cevap katmanlarina DOKUNULMADI
    rapor: 2 sahne, 2 hata bayragi, 2 donus butonu, atlanan YOK
    produced.py: kontrast 4 + 3 slayt == TABAN CIZGISI (yeni kusur yok)
    acilma testi: kanarya [GUVENILIR] (saglam=acildi bozuk=acilmadi)
                  uretilmis.story ACILDI 9.0 sn

AD URETIMI TEK YERDE: ilerleme._degisken_adi'ya `sonek` parametresi eklendi.
Iki katman ayni sahne icin uyusan adlar uretiyor:
    02_KimlikAvi -> KimlikAvi_Tamam / KimlikAvi_Hata

KAPANMAYAN: <Bolum>_Hata bayragi KURULDU ama HENUZ OKUNMUYOR. Sonuc slaydi
onu raporlamiyor, hicbir kosul ona bakmiyor. Kaydin degeri "hangi konuda
yanildi" verisinin artik VAR olmasi; onu gosteren ekran ayri bir is.

## 13. TEKRAR EKRANI: hata bayraklarini OKUYAN taraf

12. bolumun kapanmayan maddesi buydu: <Bolum>_Hata bayragi KURULUYOR ama
hicbir sey ona bakmiyordu. Elde veri vardi, ogrenci icin hicbir sey
degismiyordu.

KURULAN: sonuc slaydinda, konu basina bir serit --
"Tekrar et:  <Sahne Basligi>" -- yalnizca o konuda yanildiysa gorunur.

HER KONU ICIN AYRI KATMAN, tek katmanda N satir DEGIL. Gerekce: tek
katmandaki satirlari ayri ayri gizlemek "Hidden" durumu gerektirir ve duz
metin kutusunda o durumun XML'de nasil durdugu bu projede OLCULMEDI. Katman
gosterip gizlemek ise olculmus yol -- kilit katmani ayni mekanizmayla
kuruldu ve dosya aciliyor. Storyline katmanlari ust uste gosterebiliyor,
yani serit satir satir birikiyor.

IKI KOSUL, tek degil:
    <Bolum>_Hata == true    o konuda yanildi
    Ilerleme    >= esik     kursu BITIRDI
Ikincisi olmasaydi serit, kilit katmani ("hepsini tamamlamadiniz") ile ayni
anda gorunurdu -- ogrenciye hem "daha bitirmedin" hem "sunu tekrar et"
demek olurdu.

SERIT YERI OLCULEREK SECILDI, tahminle degil. Sonuc slaydinin kok sekilleri:

    y   2.0 -  9.5%   SONUC
    y   5.5 - 14.4%   Degerlendirme Sonucu
    y  36.9 - 56.4%   Puanin
    y  70.1           Line
    y  82.7 - 88.6%   Gecme Puani

%56.4 ile %70.1 arasi BOS. Seritler oraya kondu:

    Tekrar_Dinleme_Hata   x 10-90%   y 58.0 - 63.0%
    Tekrar_Sinir_Hata     x 10-90%   y 63.6 - 68.6%

add_layer tohumdan buyuk bir panel (%8,%12 - %92,%80) + "Devam" butonu
getiriyor. N konu icin N buyuk panel ust uste binerdi ve her birinde ayri
bir Devam butonu olurdu; panel ince seride indiriliyor ve buton
kaldiriliyor (sonuc slaydinin kendi Success/Failure katmanlari zaten kendi
butonlarini tasiyor).

OGRENCIYE MAKINE ADI GOSTERILMIYOR: baslik builder._sahne_basligi'ndan
geliyor (ayrac slaytlari icin zaten yazilmisti). Ikinci bir turetme yazmak,
ayni sahnenin iki yerde iki farkli adla anilmasi olurdu.

    "02_Dinleme"  ->  "Dinleme ve Sahiplenme"
    "03_Sinir"    ->  "Sinir Koyma"

DOGRULANDI, sonuc slaydinin tetikleyicileri:

    OnStart -> showSubSlide  EGER [Results.ScorePoints gte 0]        (tohum)
    OnStart -> showSubSlide  EGER [Results.ScorePoints lt 0]         (tohum)
    OnStart -> showSubSlide  EGER [Ilerleme lt 2]                    (kilit)
    OnStart -> showSubSlide  EGER [Dinleme_Hata eq True, Ilerleme gte 2]
    OnStart -> showSubSlide  EGER [Sinir_Hata   eq True, Ilerleme gte 2]

Ilk ikisi 3. bolumde baglanan skor degiskenleriyle cozuluyor -- kopuk degil.

    rapor: 2 satir, atlanan YOK

    acilma testi: kanarya [GUVENILIR]  uretilmis.story ACILDI 10.5 sn
    produced.py : kontrast 4 + 3 slayt == TABAN CIZGISI

## 14. KOSUL CALISMA ANINDA DOGRULANDI (2026-09-04, Preview)

Kullanici test/kosul_probu.story'yi Preview'da acti ve bandi okudu:

    A=0  B=1

Prob kurgusu (tek giris, gezinme yok), slide26.xml uzerinde OnStart sirasi:

    1. PFlag = true                       kosulsuz
    2. PA += 1   EGER PFlag == false      ATESLEMEMELI
    3. PB += 1   EGER PFlag == true       ATESLEMELI

A=0 B=1 UC SEYI BIRDEN kanitliyor:

  * condLst CALISMA ANINDA DEGERLENIYOR. Kosulu dogru olan tetikleyici
    atesledi (B=1), yanlis olan ateslemedi (A=0). Iki yon de goruldu --
    yalnizca B=1 gorulseydi "kosullar yok sayiliyor, hepsi atesliyor"
    ihtimali ayirt edilemezdi; A=0 onu eliyor.

  * TETIKLEYICI SIRASI LISTEDEKI SIRAYLA ISLIYOR. PFlag, PA'dan ONCE
    yazilmisti ve PA'nin kosulu onu gordu. Bu, ilerleme sayacinin dayandigi
    tam varsayim: "sayac ARTSIN, sonra bayrak kalksin" ancak sira
    korunuyorsa dogru sonuc verir. Ters sirada calissaydi sayac her
    giriste artardi.

  * AZINLIK BICIM CALISIYOR. 11. bolumde isaretlenen risk kapandi:
    bagiscilarda dataType=value + varG2=NULL bicimi 98'de yalnizca 4 kez
    geciyordu ve "o dordunun islevsel oldugu kanitlanmis degil" diye
    yazilmisti. Benim urettigim kosullarin tamami bu bicimde ve
    calisiyorlar. varG2'yi doldurmaya GEREK YOK.

KAPSAM -- BU OLCUM NEYI KAPSAMIYOR, acikca:

  olculen  : bool karsilastirmasi (op=eq, boolVal True/False)
             action=adjustVar uzerinde
  olculmedi: SAYISAL karsilastirma (op=gte / op=lt, floatVal1)
             action=showSubSlide uzerinde

Kilit (Ilerleme lt 2) ve tekrar ekrani (Ilerleme gte 2) SAYISAL karsilastirma
ve showSubSlide kullaniyor. Ayni condLst makinesi, ayni kod yolu -- ve
bagiscilarda showSubSlide+kosul iki gercek ornek var -- ama sayisal
karsilastirmanin calistigi GORULMEDI.

Bu bosluk icin test/kosul_probu2.story hazirlandi: ayni tek-giris kurgusu,
bu kez sayisal. Beklenen A=0 B=1 C=1 D=0.

## 15. GERI BILDIRIM METNI: bir soru ailesinde hic yazilmiyordu

TESPIT, uretilmis kursta olculdu:

    slide29 (dragDrop)      "Dogru | Sira dogru: once dinleme..."      OZEL   ok
    slide32 (freePickOne)   "Dogru  Sakin ton gerginligi dusurur..."   OZEL   ok
    slide2d (freePickMany)  "Bulamadigin ogeler var | , | Cevaplari gor"  TOHUMUN
    slide37 (freePickMany)  ayni                                          TOHUMUN

freePickMany ailesinde ogrenci, cevabini verdikten sonra TOHUMUN HASAT
EDILDIGI KURSUN metnini okuyor; govde tek bir virgul.

IKI KUSUR UST USTE:

  1. compose_feedback_layers panel ile butonu METIN UZUNLUGUYLA ayiriyordu:

         if len(text) < 30: continue    # "buton" sayip gec

     freePickMany tohumunun basligi "Bulamadigin ogeler var" = 22 karakter,
     govdesi 1 karakter. Ikisi de buton sayilip atlandi -- o katmanda
     HICBIR sekil yeniden yazilmadi.

  2. Ayni fonksiyon rolu (dogru/yanlis) katman ADINDAN cikariyordu; o
     ailede adlar BOS. Yazilsaydi bile ikisine de "yanlis" metni giderdi.

KURAL YANLIS YERDEYDI. Ayni kusur drag icin 2026-08-30'da bulunmus ve AYRI
BIR FONKSIYON yazilarak cozulmustu (compose_drag_feedback); belge dizesi 30
karakter esigini birebir tarif ediyor. Duzeltme DALA yazilmis, kurala degil,
ve pick-many o dalin disinda kalmisti. Ustelik drag'in sezgisi de pick-many'de
TERS cevap verirdi: metinde "dogru"/"yanl" gecmiyor -> `index == 0` -> katman[0]
dogru sanilir, oysa intrProps katman[0] icin incFbG diyor.

CARE, iki parca:

  A. compose.geri_bildirim_rolleri -- TEK KARAR YERI, yetkili kaynak
     <intrProps corFbG/incFbG>. Ad, metin ve sira yollari ARKA sirada
     duruyor (yani ad dolu tohumlarda davranis degismedi). Her iki
     fonksiyon da artik buradan okuyor.

  B. Siniflandirma ETIKETTEN, uzunluktan degil. Storyline'in kendi adlari:
         feedbackTextBox   &Title / Feedback Text     metin
         feedBackBtn                                  buton
         roundRect / rect                             tek parcali panel

BASLIK ROL SOZCUGUYSE KORUNUR. Ilk surum drag'in duzgun Turkce
"Dogru"/"Yanlis" basligini ASCII varsayilana dusurdu -- gerileme goruldu ve
kapatildi: baslik bir ROL etiketiyse (kisa ve "dogru"/"yanl" iceriyor)
tohumunki kalir; "Bulamadigin ogeler var" gibi bir CUMLE ise degisir.

DOGRULANDI:
    slide29  "Dogru" / "Yanlis" KORUNDU, govdeler ozel
    slide2d  k[0]=YANLIS(intrProps) ozel metin, k[1] ozel metin
    slide37  ayni
    slide32  DEGISMEDI (zaten calisiyordu)

## 16. HOTSPOT: geri bildirim katmani HIC YOK -- gorunur kilindi, giderilmedi

seeds/question_freeHotSpotIntr_1.xml olculdu:

    sldLayer          : 1 tane, ve BOS (<sldLayer />)
    feedbackTextBox   : 0
    intrProps         : corFbG=b33f5a72  incFbG=f179bbfd
                        IKISI DE tohumda YOK -- kopuk

Yani hotspot sorusunda geri bildirim konacak yer yok; model yaziyor, kurucu
geciriyor, hicbir yere konmuyor.

SESSIZ KAYIP GORUNUR KILINDI: builder._geri_bildirim_yazildi_mi, geri
bildirim ISTENIP yazilamayan soruyu adiyla raporluyor
(rapor alani "feedback_dropped").

    "Gorselde gerginligin ilk isaretini gosteren : geri bildirim yazildi
     ama slayda KONMADI (hotspot)"

IKI YERE BAKIYOR ve bu gerekliydi: add_question sonuclari duzlestirip ust
duzeye koyuyor, add_hotspot_question ise adapt_seeded_slide'in ciktisini
`adapted` altinda tasiyor. Ilk surum yalnizca ust duzeye bakiyordu ve tam da
kaybin yasandigi aileyi GORMUYORDU (feedback_dropped bos donuyordu).

GIDERILMEDI: tohuma iki geri bildirim katmani KLONLAMAK ve corFbG/incFbG'yi
onlara baglamak gerekiyor. Katmanlar elle yazilamaz (klonlanmak zorunda,
compose.py'nin notu), ve baglamanin CALISMA ANINDAKI davranisi olculmedi.
Ayri bir is olarak duruyor.

## 17. REVEAL DUZENI: sozluge bir seferde okunamayan ilk slayt

ILK TESHISIN ASIL CARESI. 2026-09-04'te su satir yazilmisti:

    compose.LAYOUTS = cover, section, content, bullets, steps, statement, menu
    yedisinden ALTISI "sayfaya yerlestirilmis metin"

Kapilarin hepsinden gecen bir kurs yine de sayfa cevirmekti, cunku sozlugun
kendisi PowerPoint'in sozluguydu. `reveal` o sozluge ogrencinin ELINI isin
icine sokan ilk ICERIK duzenini ekliyor: basliklar gorunur, aciklama
TIKLAYINCA acilir.

MEKANIZMA YENI DEGIL -- iki olculmus parcanin bilesimi:

    compose_slide(layout="reveal")    menu ile AYNI bant iskeleti
    authoring.add_layer(open_from=)   tiklayinca acilan katman

menu ile reveal ayni kodu paylasiyor cunku ikisi de "basliklar sayfanin
kendisidir" diyor; fark tiklamanin NEREYE gittigi -- menu baska slayda,
reveal ayni slaytta bir katmana.

PROB ONCE KOSULDU (uretim koduna baglamadan):
    3 etiket, 3 katman, her butonda TAM BIR tetikleyici (OnClick->showSubSlide)
    kaldirilacak jumpToSlide CIKMADI -- add_layer butonu dogrudan bagliyor
    KAYIT ok=True, 0 sorun
    acilma: kanarya [GUVENILIR], reveal.story ACILDI 10.5 sn

ESLESME INDISLE, METINLE DEGIL: add_layer metinle de eslestirebiliyor ve iki
etiket ayni kelimeyle baslayabilir; yanlis butona baglanmis bir katman
disaridan DOGRU gorunur ve yanlis seyi acar. compose_slide artik buton
GUID'ini `laid["buttons"][i]["shape"]` icinde donduruyor.

PROMPTLARA OGRETILDI (yoksa model hic uretmez):
    OUTLINE_PROMPT   duzen listesine reveal + "kursta en az bir reveal olsun"
    CONTENT_PROMPT   items ornegi + alan kurali (label <=30 karakter, detail
                     bir iki cumle; bullets DEGIL)
    GOVDE_DUZENLERI  reveal eklendi -- cesitlilik kapisi onu govde sayiyor

produced.py'ye de bir reveal slaydi konuldu: bu kontrolun isi PROB degil
URETILMIS kursta kosmak. Etiketler sinirda secildi (28-30 karakter); kisa
etiketle kosmak, bandin dar oldugu vakayi gormezden gelmek olurdu.

DOGRULANDI, uretilmis kursta -- dort sahnenin dordunde:

    slide28 01_Gerginlik  katmanlar=['Ses tonundaki yukselme','Ucuncu kez
                          tekrar','Ani sessizlik']
                          tiklanan  = AYNI UCU

`tiklanan` ile `katmanlar` birebir esitse her etiket KENDI katmanini
aciyor demektir; indis eslestirmesinin dogrulugu buradan okunuyor.
