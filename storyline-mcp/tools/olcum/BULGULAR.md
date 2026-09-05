# "Invalid or corrupt" — KOK NEDEN BULUNDU (2026-09-04)

Sorulan soru: panelin urettigi `.story` dosyalarini Storyline neden
"This project is invalid or corrupt and cannot be opened" diye reddediyor?

**Cevap: hotspot sorusu tohumundaki tek bir eksik XML niteligi.**

## Sebep

Storyline reddederken gerekcesini KENDI gunlugune yaziyor:
`%LOCALAPPDATA%\Articulate\360\Logs\Storyline_STABLE_*.log`

    System.ArgumentNullException: Value cannot be null. (Parameter 'attribute')
      at Guid System.Xml.Linq.XAttribute.op_Explicit(XAttribute)
      at Articulate.Design.Shapes.Controls.Dials.DialData.ReadXElement(...)
      at Articulate.Design.Shapes.TextBox.ReadXElement(...)
      FilePath: "...\giths.story",  OpenResult: "Fail"

`DialData.ReadXElement` bir nitelii `Guid`'e ceviriyor; nitelik yoksa
ArgumentNullException atiyor ve TUM dosya acilmaz oluyor.

Kaynak: `storyline_mcp/seeds/question_freeHotSpotIntr_1.xml` — 4 `<dialData>`
elemaninin 2'sinde `defVarG` niteligi YOK. Diger 19 tohumun hepsi temiz.

## Zincirin her halkasi olculdu

| halka | kanit |
|---|---|
| bozuk slaytin kimligi | `giths` -> `02_Hotspot_PR_Merge`, `gits` -> `03_Hotspot_PR` (ikisi de hotspot) |
| tohumla bag | dosyadaki kirli `<dialData>` dizesi tohumdakiyle BAYT BAYT ayni |
| oran | 592 `dialData`'dan 1 tanesi eksik -> dosyanin tamami acilmaz |
| kontrol grubu | `bos.story`: 444 `dialData`, 0 eksik -> ACILIYOR |

## Nedensellik kaniti (ayni kosu, yan yana)

    kanarya: saglam=acildi  bozuk=acilmadi  [GUVENILIR]

    _kanit_onarilmis.story   ACILDI: EVET   10.5 sn
    giths.story              ACILDI: HAYIR  -

Iki dosya arasindaki TEK fark: `slideb.xml`'e eklenen 47 bayt
(`defVarG="00000000-0000-0000-0000-000000000000"`). Baska aciklama kalmiyor.

## Yayilim

Kullanicinin 43 dosyasindan 8'i kusurlu — hepsi hotspot sorusu iceren
`git*` ailesi. Her birinde 694-1156 `dialData` icinden TAM BIR tanesi eksik:

    git, github, github kullanımı, github_kullanimi_yeni,
    githubs, gits, giths, newgit

Ariza degil, DETERMINISTIK: hotspot sorusu koyulan her kurs bozuluyor,
koyulmayan hicbiri bozulmuyor.

## Neden hicbir kontrol yakalamadi

`verify()` dort sey soruyor: BOM, XML ayrisiyor mu, slayt `.rels`'i var mi,
`layoutG` gecerli mi. Eksik `defVarG` bunlarin HICBIRINI ihlal etmiyor — XML
kusursuz bicimli. `verified_ok: true` yanlis degildi; sadece ACILIRLIK
hakkinda hicbir sey soylemiyordu.

Ayrica `tools/canary.py` basliginda zaten olculmus: BOM soyulunca dosya YINE
ACILIYOR. Yani `verify()`'in ana gecme olcutu kapici degil.

## Yontem notu

Yapisal tahminlerle cok vakit harcandi (bos `.rels`, `layoutG` cakismasi,
sldId bagi, content-types kapsami — hepsi olculdu, hepsi masum cikti).
REDDEDEN PROGRAMIN KENDI GUNLUGU sebebi tek satirda soyledi. Bir format
tersine muhendisligine girismeden once uygulamanin log'una bakilmali.

## Yapilanlar

- `seeds/question_freeHotSpotIntr_1.xml` duzeltildi (2 nitelik eklendi).
  Bundan sonra uretilecek kurslar kusuru tasimayacak.
- `tools/paket_farki.py` yazildi (yapisal sonda; bu vakada masum cikti ama
  `verify()`'in bakmadigi eksenleri olcuyor).

## Yapilmayanlar (kullanici onayi bekliyor)

- Mevcut 8 bozuk dosyanin onarilmasi (kullanicinin kendi dosyalari).
- `verify()`'a `defVarG` kontrolunun eklenmesi.

Ham ciktilar: `acilma_*.log`

---

# IKINCI KUSUR: slaytlar preview'da atlaniyor (2026-09-04, kullanici bildirimi)

Belirti: dosya aciliyor ama hotspot ve text-entry slaytlarina basildiginda
preview onlari ATLIYOR.

## Sebep: `fakeTrigger`

Uc tohumda, slayt seviyesinde, ADI FAKE OLAN bir tetikleyici var:

    <trig name="fakeTrigger">
      <data enabled="true" event="OnStart" action="jumpToSlide" actSubType="next" ...>

Turkcesi: "zaman cizelgesi baslayinca sonraki slayta atla". Etkin. Yani slayt
kendi kendini atliyor -- belirti bir yan etki degil, tetikleyicinin yazili isi.

Tasiyan tohumlar (baska hicbiri tasimiyor):

    seeds/hotspot_ornek.xml
    seeds/question_freeHotSpotIntr_1.xml
    seeds/question_freeTextEntryIntr_1.xml

Kodda `fakeTrigger` gecmiyor: tohumdan geliyor, uretici yazmiyor.

## Kullanicinin dosyalarinda

    giths  -> 02_Hotspot_PR_Merge, 01_Taahhut_Adimi
    gits   -> 03_Hotspot_PR, 04_Kapanis_Taahhut
    newgit -> Hotspot 3.1 - PR Onayi, Kisisel Taahhut

Bildirilen slaytlarla BIREBIR ayni.

## Bildirilenden GENIS

    bos.story        : 22 slayt (hepsi ICERIK slayti, soru degil)
    uretilmis.story  : 17 slayt   <-- suit kapisinin baktigi kurs

Uclu de ayni: `enabled=true, OnStart, jumpToSlide`, ayni konumda
(`sld > trigLst > trig`). Yani sorun hotspot'a ozgu degil; yalnizca orada
gorulur oldu. bos.story'nin icerik slaytlarinin gercekten atlanip atlanmadigi
PREVIEW ile DOGRULANMADI -- tetikleyicinin anlami olculdu, davranisi degil.

## Ayni sinifta ikinci gizli eksik

`question_freeHotSpotIntr_1.xml` icindeki `<other>` elemaninda `randomMin`
niteligi de yok (uretilmis dosyalarda var). `defVarG` ile ayni sinif: eksik
nitelik. Bugun bir belirti uretmiyor, ama ayni yoldan gelen ucuncu bir kusur
adayi.

## Kendi hatam

Cogunluk-sozlesmesi kontrolunu "gurultu" diye elerken olcutum "dosya
ACILIYOR mu" idi. `textBox/scrollOverflow` bulgusu tam da bu uc tohumu
gosteriyordu ve ben eledim. ACILMA ile CALISMA ayri kapilar; birine gore
kalibre edilen bir eleme, otekinin kusurunu gurultu sayar.

## Durum

- Tohumlar HENUZ duzeltilmedi (fakeTrigger icin). Sebep: hotspot ve
  textEntry tohumlarinda Gonder butonu YOK (calisan soru tohumlarinda 12-45
  btn var, bunlarda 0). Tetikleyiciyi silmek atlamayi durdurur ama ogrencinin
  soruyu gonderebildigini DOGRULAMAZ. Bu bir tasarim karari.
- Test icin iki duzeltmeli kopya uretildi:
  `Desktop\Storyline\_deneme_iki_duzeltme.story`
  (defVarG eklendi x1, fakeTrigger silindi x2, tum XML ayrisiyor)

## Cozum uygulandi (kullanici dogruladi)

Kullanici `_deneme_iki_duzeltme.story`'yi preview'da denedi: slaytlar
ATLAMIYOR ve soru gonderilebiliyor. Yani `fakeTrigger`'i silmek atlamayi
durduruyor ve slayti takili birakmiyor -- tasarim endisesi olculdu ve gecti.

Bunun uzerine tohumlar duzeltildi:

    hotspot_ornek.xml                  fakeTrigger silindi x1
    question_freeHotSpotIntr_1.xml     fakeTrigger silindi x1  (+ defVarG x2)
    question_freeTextEntryIntr_1.xml   fakeTrigger silindi x1

Tum tohumlar ayrisiyor. Kalan fakeTrigger: 0. Kalan defVarG'siz dialData: 0.

## Iki kusurun ozeti

| kusur | belirti | kaynak | durum |
|---|---|---|---|
| eksik `defVarG` | dosya HIC acilmiyor ("invalid or corrupt") | question_freeHotSpotIntr_1.xml | DUZELTILDI, acilma testiyle kanitlandi |
| `fakeTrigger` | slayt preview'da atlaniyor | 3 tohum | DUZELTILDI, kullanici preview'da dogruladi |

Ikisi de ayni yerden: `suit --tam` kapisinin bakmadigi soru tipleri.
`uretilmis.story` fikstürü hotspot ve text-entry ICERMIYOR -- iki kusur da
tam o kor noktada yasiyordu.

## Acik kalan

1. Kullanicinin 8 bozuk dosyasi hala bozuk (onay bekliyor).
2. `uretilmis.story` fikstürü her soru tipini icermiyor -- kapinin kor
   noktasi kapatilmadi. Bu kapatilmazsa ayni sinifta ucuncu kusur yine
   sessizce gecer.
3. `bos.story` (22 slayt) ve `uretilmis.story` (17 slayt) hala fakeTrigger
   tasiyor; tohum duzeltmesi yalnizca BUNDAN SONRAKI uretimleri korur.

---

# KAPININ KOR NOKTASI KAPATILDI (2026-09-04)

Hedef: `suit --tam` icindeki `open_test` adimi Storyline'a "bunu acar misin"
diye soruyor ve DOGRU soru bu. Yanlis olan, SORDUGU KURSTA bugunku iki kusurun
gectigi yollarin bulunmamasiydi.

Baslangic olcumu:

    tohum kutuphanesi : 5 bicim (dragDrop, freeHotSpot, freePickMany,
                                 freePickOne, freeTextEntry)
    kapinin fiksturu  : 2 bicim (freePickOne, freePickMany)

Yani 5 bicimden 3'u kapidan hic gecmiyordu; bugunku iki kusur da o ucun
ikisinde yasiyordu.

## Kapatirken cikan DORT ayri sessiz kusur

Fikstur genisletildi ve kapsam olcumu eklendi. Olcum, daha ilk kosuda kendi
duzeltmemdeki bosluklari acti -- yani lastik damga degil:

1. **Kapsam MIRASTAN doluyordu.** `produced.py`'nin BLANK dedigi
   `test/bos.story`, onceki oturumun debug build'iyle 37 slayda cikmis.
   Kapsam devralinan slaytlardan sayilinca kapi, insa yolu hic calismadigi
   halde yesil veriyordu. Cozum: kapsam yalnizca URETILEN slaytlarda olculur.

2. **Red listesi yanlis anahtarla okunuyordu.** Kontrolu ilk yazisimda
   `report["refusals"]` dedim; builder onu `question_refusals` diye
   donduruyor. Kontrol sessizce hep temiz gorunecekti -- yakalamak icin
   yazildigi hatanin aynisi.

3. **Fikstur her sahneye YANLIS sahnenin icerigini veriyordu.** `canned()`
   cagri sayacina gore cevap veriyordu ve iki varsayimi da yanlisti:
   basta bir degil IKI icerik-disi cagri var, ve builder icerigi YENIDEN
   ISTEYEBILIYOR. Olculdu: 4 sahne icin 5 cagri bekleniyordu, 7 oldu.
   Eklenen gruplama slaydi bu yuzden HIC kurulmadi -- red bile uretmeden.
   Cozum: sahne KIMLIGIYLE (baslik) eslesme, sayacla degil.

4. **Kurucu puanli metin sorusu URETEMIYORDU.** `add_text_question`
   `graded = bool(accept)` diyor, ama builder `accept`'i hic gecirmiyordu.
   Yani `freeTextEntryIntr` bicimi kurucunun hicbir yolundan cikmiyordu.
   Cozum: `spec.get("accept")` gecisi (verilmedigindeki davranis degismez).

## Sonuc

    bicim kapsami 5/5    temiz

Kapsamin beklenen kumesi ELLE YAZILMADI: `question_seeds()` diskteki
tohumlardan turetilir, yani kutuphaneye yeni bir bicim eklendiginde kapi onu
kendiliginden talep eder.

## Kapida kalan iki kirmizi (ikisi de ONCEDEN VARDI)

- `3 slayt kurulamadi (sigdi-ama-elendi)` -- sik sorusu sablon secimi bazi
  slaytlari reddediyor. Her zaman oluyordu; yalnizca artik GORUNUYOR.
- `kontrast 4` + `ikiz slayt 42` -- MIRASTAN. Olculdu: `test/bos.story`
  tek basina kontrast=4 tasiyor. Kapinin BLANK'i artik bos degil.

Ikincisi icin denendi (dosyalara DOKUNULMADAN, gecici olarak):

    BLANK = test/bos.story      -> kontrast 4, ikiz 42, kayitli 12/12
    BLANK = test/try_ONCE.story -> kontrast 0, ikiz  8, kayitli 0/6  (quiz
                                   iskelesi yok, uygun degil)
    BLANK = test/bos.story.bak  -> kontrast 0, ikiz  8, kayitli 6/6  TEMIZ

`bos.story.bak` 30 Agustos tabanindaki blank'in ta kendisi. Kullanicinin
karari: `test/bos.story`'yi ondan geri yazmak tek kopyalik bir islem, ama
kullanicinin dosyasi.

---

# KAPI KAPATILDI (2026-09-05)

Acik kalan 2. madde ("uretilmis.story her soru tipini icermiyor") cozuldu.
Cozumun bir kismi paralel calismada zaten yapilmisti:

- `produced.py::_kapsam_slaytlari()` kalan bicimleri sahnelere dagitiyor
  (drag -> sahne 1, commitment/freeTextEntry -> sahne 2, hotspot -> sahne 3).
- `produced.py::main()` uretilen slaytlardaki `*Intr` bicimlerini tohum
  kutuphanesiyle karsilastirip eksigi KUSUR olarak bildiriyor. Beklenen kume
  ELLE YAZILMADI: `authoring.question_seeds()` diskten turetiliyor, yani yeni
  bir tohum eklendiginde kapi onu kendiliginden talep ediyor.

## Olculen sonuc

    bicim kapsami 5/5    temiz
    uretilen: dragDropIntr, freeHotSpotIntr, freePickManyIntr,
              freePickOneIntr, freeTextEntryIntr  (+rsltsIntr)

Insa yolu, iki kusurdan da temiz:

    YENI KURULAN slaytlarda defVarG eksik : 0
    YENI KURULAN slaytlarda fakeTrigger   : 0
    hotspot slayti (slide36)   : temiz
    textEntry slayti (slide30) : temiz

Kalan 22 fakeTrigger'in TAMAMI devralinan `test/bos.story`'den geliyor
(debug_build.py'nin bozdugu blank). `produced.py` devralinanlari kapsam
olcumunun disinda tuttugu icin kapi mantigi bundan etkilenmiyor.

## Kapinin kendisi kosuldu

    kanarya: saglam=acildi  bozuk=acilmadi  [GUVENILIR]
    uretilmis.story    ACILDI: EVET    9.0 sn

Yani: hotspot + textEntry sorusu ICEREN bir kurs artik aciliyor (defVarG
duzeltmesinden once acilmiyordu), VE kapi bundan boyle o yolu her kosuda
sinaniyor. 2026-09-04'teki iki kusur bugun uretilseydi bu adim kirmizi
verirdi.

Ham cikti: `acilma_kapi_2026-09-05.log`

## Ayrica

`panel/app.py`'de sokumden kalmis bir mesaj duzeltildi: `build_course`
kullaniciya artik kodda olmayan Antigravity CLI'yi kurmasini soyluyordu.

---

# KUSUR 1 (kontrast) KAPANDI — ve sebebi tema degil FIKSTURDU (2026-09-05)

## Sonuc

    themes_check   24 sorun -> GECTI: 6 tema, 0 sorun
    produced.py    kontrast 4 -> 0   (kalan tek kusur: 3 slayt kurulamadi)
    temizlenmis bos.story  ACILDI: EVET 12.0 sn  [kanarya guvenilir]

## Sebep

`test/bos.story` bos sablon DEGILDI: 37 slayt, 22 fakeTrigger, alti soru ve
bir surukle-birak slaydi -- silinen `panel/debug_build.py`'nin artigi.

O devralinan surukle-birak slaydinin grup kutulari `<schemeClr val="accent1"/>`
ile temaya bagli; tema yuvasi yazilmadigi icin Office mavisinde (#4F81BD)
kaliyor ve uzerlerindeki beyaz yazi 4.03 veriyordu. `themes_check` blank'i
kopyalayip PAKETIN TAMAMINI olctugu icin ALTI temada da ayni dort uyari
cikiyordu: 24 "sorun", tek bir devralinan slayttan.

`produced.py`'nin dort kontrast kusuru da ayni slayttaydi (`slide18.xml`).
Yani urun yolu HIC kirik degildi.

## Iki yanlis yol (ikisini de olcum kesti)

1. **Tema yuvasini global boyamak** (`set_theme_colors` builder'da). Kontrasti
   4->0 yapti AMA olculdu: uyarlanmayan devralinan slaytlarin dolgusu da
   degisiyor, yazilari yeniden secilmiyor. Acik vurgulu temalarda DAHA KOTU:
   gece 4.03 -> 1.56, orman 4.03 -> 1.88. Geri alindi.
2. **Uyarlanan slaytta dolguyu boyamak.** Hic atesLenmiyordu: besteci kutulari
   `_recolour_for_palette`'ten ONCE duz renge boyuyor. Kaldirildiginda hicbir
   sayi degismedi -- olu koddu.

Kodda kalan tek degisiklik `_recolour_for_palette`'in `schemeClr` dolguyu
okuyabilmesi. Gercek bir okuma kusuru, ama BUGUN bir kusuru yakalamiyor ve
yorumuna bu acikca yazildi.

## Temizlik ve ucuncu K33 ornegi

`tools/blank_temizle.py` yazildi (tek seferlik). Tuttugu olcut: adsiz +
etkilesimsiz + fakeTrigger'siz slaytlar. 37 -> 9 slayt, 56 parca ve 7 bosalan
sahne cikarildi, boyut 720x540 korundu.

ILK DENEME `verify()`'dan TEMIZ gecti ve Storyline ACMADI. Sebep yine kendi
gunlugundeydi:

    System.Xml.XmlException: Required Types tag not found. Line 1, position 57
      at ContentTypeHelper.ParseContentTypesFile(...)

`[Content_Types].xml` ElementTree ile parse edilip geri yazilinca varsayilan ad
alani onekliye donuyor:

    once  : <Types xmlns="...">
    sonra : <ns0:Types xmlns:ns0="...">

XML olarak esdeger ve kusursuz bicimli -- verify() hicbir sey gormez. OPC
okuyucusu ise `Types` kok etiketini birebir ariyor.

Kod tabani kurali ZATEN biliyordu: `clone._register_content_type` ve
`_register_story_rel` bu iki dosyaya `replace_raw` ile METIN olarak dokunuyor.
Arac o yola cevrildi, ustune bir kapi kondu: yazmadan once kok etiket
dogrulanir, bozuksa dosyaya DOKUNULMAZ.

Yedek: `test/bos.story.kirli-yedek`
Ham cikti: `acilma_blank_2026-09-05.log` (basarisiz), `acilma_blank2_2026-09-05.log` (basarili)

---

# KUSUR 2 (metin tasmasi) KAPANDI (2026-09-05)

## Sonuc

    metin tasmasi   15 -> 2      (kalan 2'si tabanda KAYITLI ve gerekceli)
    invariants      KIRMIZI -> YESIL  ("Taban tutuyor")
    suit            5 kapi kirmizi -> 2  (invariants, deadband, themes_check yesillendi)

## "5 yeni kirik" bir olcum degildi

`check_text_fits` ekrana "15 TASMA" yaziyor ama verdikte `over[:5]` donduruyordu.
Taban, kirpilmis ve SIRAYA BAGLI bir orneklemle karsilastiriliyordu; kapi hem
var olan bir kirige "artik yok" dedi hem eski kiriklara "yeni". Kirpma
kaldirildi (ayri commit).

## Kok neden: tohumda wrap tutarsizligi

Uc geri bildirim butonu `wrap="true"` tasiyordu ve etiketleri kutularina
sigmiyordu. AYNI tohumun kardes katmani ayni etiketi ayni kutuda
`wrap="none"` ile tasiyor ve SIGIYOR:

    question_freePickOneIntr_3.xml
       katman1  wrap=none  'Doğru Cevabı Gör'  ->  57.1 <= 85   sigiyor
       katman2  wrap=true  'Devam'             ->  57.1 <= 85   sigiyor (kisa)
       katman3  wrap=true  'Doğru Cevabı Gör'  -> 114.2 >  85   TASIYOR

Yani ayirt eden sey sarma bayragi degil, "uzun etiket + sarma" birlesimi;
ve dogru yapilandirma tohumun kendi katman1'inde zaten yaziliydi.

Uc buton kardesine uyduruldu. Olcut kod icinde: yalnizca SARAN tasip
SARMAYAN sigiyorsa dokunuldu -- yani degisiklik her vakada olcumle
gerekcelendirildi.

`defVarG` ve `fakeTrigger` ile AYNI SINIF: tohumdaki bir tutarsizlik,
ondan uretilen her kursa geciyor.

## Kendi aracimda ayni hatayi yaptim

`blank_temizle.py`'nin kapisi yalnizca `themes_check`in gereksinimine (6)
bakiyordu. Temizlik 9 slayt birakti ve `variety.py` 10 istedigi icin zincir
kirildi: "bos.story icinde 10 slayt yok (9 var)". Tek tuketiciye bakan bir
kapi, kapi degil.

Duzeltildi: `_en_yuksek_gereksinim()` variety/coverage/themes_check/
calibrate_diacritics'in KENDI listelerini okur ve en yuksegini alir; bir
arac okunamazsa sessiz gecmez, uyarir. Bos sablon 10 slayta tamamlandi
(temiz bir slayt klonlanarak).

## Kalan iki kirmizi kapi

  golden    "Yigin davranisi degisti. Bilerek degistiyse --record ile taban
            yenilenmeli" -- KARAR BORCU, kimse cevaplamadi.
  produced  "3 slayt kurulamadi (sigdi-ama-elendi)"

---

# BUTUN KAPILAR YESIL (2026-09-05)

    baslangic: 5 kapi kirmizi  (invariants, deadband, golden, themes_check, produced)
    son      : 0

## golden -- kusur degildi, KARAR BORCUYDU

Sapma: sik yigini 6.8 puan asagi kaymis (soru yerinde, boylar ve araliklar ayni).

Sebep bulundu: `0f1e22d` commit'i soru duzeni varyantlarini ekledi ve icinde
acikca "IKINCI EKSEN: SIK YIGINI BANDIN NERESINE OTURUR" yaziyor. Taban ise
`e997de1`'de, o ozellik yazilmadan ONCE dondurulmustu.

Tuzak: o commit'in mesaji "Add Antigravity (agy) CLI fallback" diyor ve
yerlesimden tek kelime etmiyor. "Bilerek mi degisti" sorusuna kimsenin cevap
verememesinin sebebi buydu -- mesaja bakan biri orada bir yerlesim
degisikligi oldugunu goremezdi.

Kaydetmeden once dogrulandi: uc kosuda da BIREBIR ayni sayi (rastgelelik yok)
ve alt kenar %85.2 < taban %92 (sinirlar icinde). Taban yenilendi.

## produced -- kapi olmayan bir kusuru sayiyordu

"3 slayt kurulamadi" diyordu. Olculdu: uc kaydin UCU DE `resolved: True`
tasiyor, yani slaytlar KURULDU. Kurucu sablonlari sirayla dener, icerik
sigmayan elenir, sigan bulununca slayt kurulur; kayit "su kadar sablon
elendi" demek.

Kurucunun kendi yorumu bu ayrimi zaten istiyordu ("rapor ... farki
gosterebilmeli"); eksik olan kapinin ona uymasiydi. Cozulen redler artik
bilgi olarak basiliyor, cozulmeyenler kusur sayiliyor.

Bu, ayni gunun ucuncu "kapi yanlis soyluyor" vakasi:
  1. tasma kapisi verdiktini kirpiyordu    -> var olan kirige "artik yok" dedi
  2. blank_temizle tek tuketiciye bakiyordu -> zinciri kirdi
  3. produced cozuleni kusur sayiyordu      -> kurulmus slayta "kurulamadi" dedi

## Suit'in kendi soyledigi sinir

    "bu suit geri bildirim katmanlarini (<sldLayerLst>) hicbir olcuyle
     taramaz -- olculdu, kasten bozularak sinandi. Yesil olmasi,
     katmanlarin dogrulandigi degil, HIC BAKILMADIGI anlamina gelir."

Yani "butun kapilar gecti" cumlesi katmanlar icin bir sey soylemiyor.

---

# KATMANLARDA GORUNMEZ YAZI -- 12 vaka, DUZELTILDI (2026-09-05)

## Sonuc

    reveal katmanlarinda esigin altinda yazi:  12 -> 0
    (olcum kurali: zemin = seklin KENDI dolgusu, yoksa ustunu orten
     katman/temel sekil, yoksa slayt zemini)

## Bulgu

Uretilen kursta icerik slaytlarinin "tikla-acilsin" (reveal) katmanlarinda
12 yazi BEYAZ UZERINE BEYAZ ciziliyordu (oran 1.00). slide4, slide12,
slide18, slide1e -- her birinde uc yazi. Bunlar susleme degil, butona
tiklayinca acilan ACIKLAMA metinleri.

## Kok neden

`_reveal_katmanlari` -> `authoring.add_layer(...)`. `add_layer` PALETI
BILMEZ: katman tohumunu klonlar ve metni yazar, yani yazi tohumun renginde
(beyaz) kalir. Slaydin altindaki temel katmanda #FFFFFF dolgulu bir kart
duruyor ve yazi onun uzerine dusuyor.

Soru yolu bunu ZATEN yapiyordu (`adapt_seeded_slide` -> `_recolour_for_palette`);
baglanmamis olan icerik yoluydu. Duzeltme yeni hesap degil, var olan
makineyi cagirmak: renk ARKASINDAKINE gore secilir.

Dogrulama: `_recolour_for_palette` slide4'e elle kosuldugunda 23 yaziya
dokundu ve rengi #FFFFFF -> #1F1D1A yapti; yani fonksiyon calisiyordu,
yalnizca cagrilmiyordu.

## Neden hicbir kapi soylemiyordu

`contrast.audit`in katman taramasi bir bayragin arkasinda ve varsayilani
KAPALI. Gerekcesi 2026-08-18'de olculmus ve belge dizesinde yazili:

    "kesit acikken uretilen kursta 12 'bulgu' -- hepsi #FFFFFF uzerine
     #FFFFFF, oran 1.00 ... Kendi korlugunu kusur diye raporlayan bir
     kontrol, hic bakmayandan KOTUDUR"

O gun bu 12'nin ARACIN KORLUGU oldugu varsayildi. Bugun olculdu: en az 12'si
GERCEKTI -- yazinin altinda cozulebilir, gercek bir beyaz kart var. Varsayim
"hepsi gurultu" idi; dogrusu "bir kismi gurultu" imis, ve kapali kapinin
arkasindan uretime gitti.

## KENDI OLCUM HATAM (kayit icin)

Ilk sayim 20 idi ve YANLISTI. Sondam zemini ararken sekli KENDISINI hariç
tutuyordu; oysa bir yazinin zemini once kendi dolgusudur. "Cevaplar"
katmanindaki 8 textBox'in dolgusu #A63F26 (kagit vurgusu) ve beyaz yazi
orada 6.25 veriyor -- gayet okunur. Onlar kusur degil, sondanın kusuruydu.

Dogru kuralla olculen sayilar: duzeltme yokken 12, duzeltmeyle 0.

## Acik kalan

  * `contrast.audit` katman varsayilani hala KAPALI. Acmak icin geriye
    kalan sinif: zemini cozulemeyen vakalar (kapali gradOvrlyFill).
  * Acildiginda `coverage.py --kanarya` beklentisi "kor" -> "canli"
    olarak yenilenmeli.

---

# KATMAN KONTRAST KESITI ACILDI (2026-09-05)

## Sonuc

    contrast.audit(katmanlar=...)  varsayilan False -> True
    kanarya: "KOR contrast katmandaki kusuru gormedi"
          -> "CANLI contrast katmandaki kusuru gordu (kesit ACIK)"
    suit: butun kapilar yesil

## Acilmasinin kosulu belge dizesinde yaziliydi

    "yetenek DURUYOR, kapilari BESLEMIYOR. schemeClr cozumu girdiginde
     varsayilan True olur ve kanarya beklentisi kazanc olarak yeniden
     yazilir."

Kapali tutulma gerekcesi: kesit acikken uretilen kursta 12 bulgu cikiyordu ve
hepsi #FFFFFF/#FFFFFF idi; bunlarin ARACIN KORLUGU oldugu varsayilmisti.

## Varsayim yanlisti -- uc gercek kaynak bulundu

  1. reveal katmanlari    builder._reveal_katmanlari palete baglanmamisti
  2. sonuc slaydi katmani ilerleme.kur palete baglanmamisti
  3. bos sablon           katmanlarinda "Tebrikler, sinavi gectin!" yazan
                          kurs artiklari vardi

Ucu de duzeltildikten sonra olculdu, kesit ACIKKEN:

    uretilmis.story   0 bulgu, 0 korluk   (91 olculemeyen, sessiz)
    6 tema fiksturu   0 bulgu, 0 korluk

## Bos sablon ikinci kez temizlendi

Ilk olcut (adsiz + etkilesimsiz + fakeTrigger'siz) yetmedi: kalan uc slaydin
KATMANLARINDA kurs cumleleri vardi. Olcut genisletildi ("katmaninda yazi
tasiyan slayt da artiktir"), sablon 10 temiz slayta getirildi (7 kalan + 3
klon) ve Storyline'da acildi: EVET, 10.5 sn, kanarya guvenilir.

Yan etki, kapi tarafindan yakalandi: `slidee.xml` gidince tabanda kayitli
tasma kirigi de gitti ve invariants "TABAN ESKIMIS" diye bagirdi. Girdi elle
kaldirildi ve gerekcesi tabanin yanina yazildi -- kazanim kaydedilmezse
korunmaz (K7).

## Saklanmayan sinir

Korluk URETIM YOLUNDA bitti, her yerde degil. Elle yapilmis
`test/_referans/referans.story` uzerinde kesit acikken 10 bulgu cikiyor ve
olculdu: hicbiri gercek beyaz-uzerine-beyaz DEGIL -- o dosyada 24 seklin
zemini hic cozulemiyor. Hicbir kapiyi kirmizi yapmiyor (referans zaten
bilerek bozuk bir cipa), ama elle yapilmis bir kursa bu araci dogrultan biri
o gurultuyu gorur. Kalan sinif: kapali gradOvrlyFill.

`inventory`'nin katman taramasi HALA KOR ve kanarya bunu olcmeye devam
ediyor.

---

# 4 SIKLI TEK-SECMELI TOHUM URETILDI (2026-09-05)

## Neden hasat edilemedi

Kullanicinin 43 kursu tarandi:

    freePickOneIntr   2 sik :  67 slayt
    freePickOneIntr   3 sik :  99 slayt
    freePickOneIntr   4 sik :   0        <- hicbir yerde yok
    freePickManyIntr  5 sik :  21 slayt
    dragDropIntr    4/5/6 oge: 15 slayt

Kurslarin hepsi bu araçla kuruldu, arac da ancak tohumu olan bicimi
uretebiliyor. Yani kendi ciktimizdan hasat etmek DONGU olurdu.

## Nasil uretildi

`_3` tohumunun bir sik butonu HAM METIN uzerinde klonlandi, tanimladigi
GUID'ler yenilendi, `<choices>` listesine bir `<intrFreeChoice>` kaydi eklendi.

Uc karar, ucu de olcumle:

  * ElementTree DEGIL. Ilk deneme `ET.tostring` ile yazdi: BOM ve XML
    bildirimi dustu, dosya 36 KB buyudu, sablon degerlendirici
    "ValueError: substring not found" ile patladi. Deponun ilkesi zaten
    tersi -- GUID olmayan her byte oldugu gibi kalir.
  * Klonun tetikleyici hedefi NOTRLENDI. Sik butonlari
    `OnClick -> showSubSlide` tasiyor ve hasat edildigi kursun katmanini
    gosteriyor; klonda yanlis yeri gosterirdi.
  * Dorduncu KATMAN eklenmedi. Olculdu: tohumdaki Cevap1/2/3 katmanlarini
    acan hicbir showLayer tetikleyicisi yok ve intrProps'un corFbG/incFbG'si
    tohumda bulunmayan katmanlari gosteriyor. Geri bildirimi
    `adapt_seeded_slide` yeniden kuruyor (uretilen slaytta 3 degil 2 katman).

## Dogrulama

    sablon secildi   : bundled:freePickOneIntr:4
    yazilan sik      : 4, dogru cevap isaretlendi
    yerlesim         : 4 sik esit aralikli, cakisma 0
    paket            : verify temiz
    Storyline        : ACILDI, 9.0 sn, kanarya guvenilir
    suit             : butun kapilar gecti

## Yol boyunca kendi hatalarim

  1. Kullanicidan Storyline'da dosya hazirlamasini istedim. Kendi kayitli
     kuralimi cignedim: aracin varlik sebebi o isi silmek.
  2. ElementTree ile yazdim (yukarida).
  3. Iki ekleme noktasini bastan basa ekledim; `<choices>` blogu butondan
     ONCE geldigi icin ikinci ofset kaydi ve XML bozuldu. Sondan basa
     eklemek gerekiyordu.
  4. Yerlesim kontrolunde slayt uzayi (1920x1080) yerine story olcusunu
     (720x540) kullandim ve "slayttan tasiyor" diye yanlis alarm verdim.

Tohum kutuphanesinin kaydi artik `storyline_mcp/seeds/README.md`'de.
