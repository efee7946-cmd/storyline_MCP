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
