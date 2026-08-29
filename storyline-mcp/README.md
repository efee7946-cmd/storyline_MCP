# storyline-mcp

Articulate Storyline `.story` projelerini Claude'a bağlayan MCP sunucusu.

## Neden dosya üzerinden çalışıyor

Storyline'ın Blender'daki gibi bir eklenti/script API'si yok; kaydettiği COM
sınıfları yalnızca küçük resim (thumbnail) işleyicileri, yani çalışan uygulamayı
dışarıdan süren bir arayüz bulunmuyor.

Buna karşılık `.story` dosyası bir **OPC paketi** — `.pptx`/`.docx` ile aynı
ZIP + XML + `_rels` mimarisi:

```
kurs.story
├── [Content_Types].xml
├── story/story.xml            sahneler, değişkenler, quizMgr, toc
├── story/slides/slide*.xml    shapeLst (şekiller) + trigLst (tetikleyiciler)
├── story/slideMasters/ , slideLayouts/ , theme/
└── story/media/               png / jpg / mpeg
```

Sunucu bu paketi doğrudan okuyup yazar. Arayüz taklidi (UI automation) yok,
dolayısıyla kırılganlık da yok.

## Metin modeli

Storyline her görünen metni **iki kopya** tutar:

```xml
<textBox g="a76d55de-…">
  <plain>Merhaba</plain>                      <!-- düz kopya -->
  <text>&lt;Document&gt;…                     <!-- biçimli asıl -->
    <Block><Span Text="Merhaba">
      <Style FontFamily="Segoe UI" FontSize="8" ForegroundColor="#12B5CB"/>
    </Span></Block>
  </text>
</textBox>
```

Adreslenebilir en küçük birim `Span`'dir: tam olarak bir biçim koşusuna karşılık
gelir, dolayısıyla `Span/@Text` değiştirildiğinde biçimlendirme hiç bozulmaz.
Düzenleme sonrası `<plain>` kopyası yeniden hesaplanır — bayat kalırsa arama,
anahat ve çeviri dışa aktarımında yanlış görünür.

Metin her zaman şeklin doğrudan çocuğu değildir. Quiz seçenekleri bir seviye
daha derinde, şeklin durum (state) varyantları içinde yaşar:

```
oval[g=shpG] > stateLst > state > shapeLst > textBox > text
```

Bu yüzden "şu şeklin metni" çözümlenirken torunlara da bakılır.

## Araçlar

**Okuma**

| Araç | İş |
|---|---|
| `story_info` | Künye: sahne/slayt sayısı, değişkenler, quiz ve medya özeti |
| `list_slides` | Sahne → slayt ağacı, adlar ve düzen tipleri |
| `extract_text` | Düzenlenebilir tüm metin parçaları, adresleriyle |
| `search_text` | Kurs genelinde düz metin veya regex arama |
| `list_quiz` | Sorular, seçenekler, doğru cevaplar, puanlama |
| `list_variables` | Kullanıcı / yerleşik / özellik değişkenleri |
| `list_triggers` | Olay → eylem, hedef slayt ve değişken eşlemesiyle |
| `list_templates` | Klonlanabilir slaytlar ve dayattıkları seçenek sayısı |
| `audit` | Kullanılmayan değişken, alt metinsiz görsel, çıkışsız slayt, tekrar, **öğretim ölçüleri** |

**Yazma**

| Araç | İş |
|---|---|
| `update_text` | Adreslenmiş metinleri günceller, biçimi korur |
| `add_scene` | Yeni bölüm (sahne) ekler, menüye kaydeder |
| `add_slide` | Şablon klonlayarak içerik slaydı ekler, başlığını yazar |
| `add_question` | Quiz sorusu ekler: kök, seçenekler, doğru cevaplar, puan |
| `duplicate_slide` | Slaydı kopyalar, tüm iç GUID'leri yeniler |
| `set_background` | Slaydı düz renkle kaplar (en arkaya tam sayfa dikdörtgen) |
| `add_text_box` | Metin kutusu ekler: konum, renk, boyut, hizalama |
| `add_button` | Tıklanabilir buton ekler; hedef verilmezse sonraki slayda geçer |
| `restyle_text` | Slayttaki yazıların rengini/boyutunu değiştirir |
| `set_slide_properties` | İlerleme kipi, menü gizleme, geri/ileri düğmeleri |
| `set_story_size` | Proje slayt boyutu (örn. 1920×1080) |
| `set_player_color` | Player'ın adlandırılmış rengi; `alpha` ile şeffaflık |
| `set_button_state` | Buton `Hover`/`Down`/`Visited` görünümü |
| `add_layer` | Slayt katmanı — **popup böyle kurulur** |
| `build_course` | Birçok yazma işlemini tek geçişte uygular, bir kez kaydeder |

Okuma tarafında bunların karşılığı da var: `slide_properties`, `story_size`,
`list_player_colors`, `list_button_states`, `list_layers`.

### Ayarlar nerede duruyor

Üç ayrı yerde, üç ayrı şemada:

| Ayar | Yer |
|---|---|
| Slayt davranışı | Slayt kökü (`advMode`, `hideToc`) + `<navData prev= next=>` |
| Proje boyutu | `story.xml` → `propLst > prop > sz` (kökün doğrudan çocuğu **değil**) |
| Player renkleri | `playerProps.xml` — `<color name><fill><colors><color rgb alpha>` |

Player'da aynı renk adı birden çok grupta geçer (`bg` menüde de, infopanel'de
de vardır), o yüzden `set_player_color` isteğe bağlı `group` alır; verilmezse
hepsi değişir.

Buton state'leri (`Normal`, `Hover`, `Down`, `Visited`, `Disabled`) birer
mini-slayttır — kendi arka planı, şekil listesi ve metni vardır. Hover rengini
değiştirmek, butonun üst seviye dolgusunu değil o state'in içindeki şekilleri
düzenlemek demektir.

Katmanlar da öyle: `sldLayerLst` altında, kendi `shapeLst`'i ve tetikleyicileri
olan slayt-içi slaytlar. Bu yüzden sıfırdan üretilmez, klonlanır — ölçüm: 130
tanımlı GUID'e karşı yalnızca 2–3 dış referans. Katmanı açan tetikleyici
`showSubSlide` eylemini ve `<sldLayer showG="...">` hedefini kullanır.

### Sayfa tasarımı

Şekiller de slaytlar gibi **klonlanarak** üretilir. Önce projenin kendi şekilleri
aranır, böylece yeni şekil kursun görünümünü devralır. Proje boşsa devreye
`storyline_mcp/seeds/` altındaki **gömülü tohumlar** girer.

Bu yedek şart: aksi hâlde boş bir proje ilk metin kutusunu asla üretemez, araç
kullanıcıdan gidip elle bir tane çizmesini istemek zorunda kalır — yani tam da
ortadan kaldırmak için var olduğu manuel işi geri getirir.

Gömüleme yalnızca kendi dışına referans vermeyen şekiller için güvenli. İki
gerçek kurs üzerinde ölçüldü:

| Şekil | Tanımlı GUID | Dış referans |
|---|---|---|
| `textBox` | 6–12 | **0** |
| `rect` | 12 | **0** |
| `btn` | 38–114 | 1–3 (`layoutG`, `qsG`, `jumpG`) |

Butonun dış bağları tohum alınırken boş GUID'e çekilir; `jumpG` zaten yeniden
hedeflenir. Tohum, katıldığı projenin koordinat uzayına (`sldSz`) damgalanır —
1920×1080 bir tohum 720×540 bir kursa olduğu gibi düşerse kendi geometrisi için
yanlış referans çerçevesi taşır.

Konumlar **slaydın yüzdesi** olarak verilir (0–100), piksel değil. Sebebi:
koordinat uzayı projeye göre değişiyor (bu kullanıcının bir kursunda 720×540,
diğerinde 1920×1080), dolayısıyla mutlak sayılar bir kursta doğru, ötekinde
slayt dışında kalır.

Metin iki farklı biçimde saklanır ve ikisi de karşılanmalıdır — metin kutuları
çalışma stili taşır, butonlar çoğu zaman hiç taşımaz:

```xml
<Span Text="..."><Style FontFamily="Segoe UI"/></Span>   <!-- metin kutusu -->
<Span Text="SINAV" />                                     <!-- buton -->
```

Yalnızca mevcut `<Style>` etiketlerini düzenleyen bir biçimlendirici ikincisini
sessizce atlar; bu yüzden kendini kapatan `<Span>` yeniden açılıp stil verilir.

### Kayıt hangi listede duruyor

`<media>` ve `<video>` kayıtları **`mediaLst > mediaLst`** içinde durur —
dıştakinde değil, içtekinde. Ölçüldü (2026-08-29): dört gerçek kursun
dördünde de bütün kayıtlar içteki listede (20, 8, 7 ve 18 kayıt); dıştaki
liste yalnızca içtekini taşıyor.

Kod dıştakine yazıyordu, yani kayıt içteki listenin **kardeşi** oluyordu. Kusur
tamamen sessizdi: paket geçerli kalıyor, `pkg.save`'in doğrulaması temiz
geçiyor, `assetG → kayıt → md5 → bayt → ilişki` zincirinin her halkası
izlenebiliyordu. Yalnızca Storyline kaydı hiç görmüyordu ve slaytta
**"The image can't be displayed"** yazıyordu — iki ayrı kursta, hem JPEG hem
PNG ile.

Ders, kendi DEVIR'imizde zaten yazılı olanın aynısı: *sınandı ≠ bağlandı*.
Probe'lar bağ zincirini ölçüyordu, **kaydın nerede durduğunu** ölçmüyordu.
`tools/medya_probe.py` artık üçünü birden soruyor: içteki liste var mı,
kayıtlar orada mı, dıştaki liste kayıt taşımıyor mu.

### Fotoğrafın üstündeki yazı okunur kalır

Tam sayfa bir fotoğrafın üstüne yazı düşüyorsa arada bir **örtü** olmalı.
Kurucu bunu kapakta zaten çiziyordu (`compose_slide(image_area=True,
image_style="hero")` → `Ton` %32 + `Ortu` gradyan), ama görsel kursa **üç ayrı
yoldan** giriyor: kurucu, komut yolundaki ajan ve panelin Görsel & Video
sekmesi. Garanti yalnızca ilkinde vardı. Ölçüldü (2026-08-29, `denee.story`
slide2): slaytta örtü hiç yoktu, fotoğraf tam sayfa oturdu ve beyaz başlık
aydınlık bir ofis fotoğrafının üzerinde kayboldu.

Artık garanti **uygulamanın kendisinde**: `compose.ensure_scrim` görselin
üstünde yazı var ve arada örtü yoksa iki katman koyar —

- `Ton`: tam sayfa, %32; fotoğrafı bütün olarak yatıştırır
- `Ortu`: **yazı bloğunun arkası**, %82, yazının olmadığı yöne doğru söner

Şerit sabit bir alt gradyan değil: yön yazının kendi yerinden hesaplanır
(başlık üstteyse aşağı, alttaysa yukarı söner). Sabit alt gradyan, üstte duran
bir başlığı kurtarmıyordu.

İki tuzak da ölçülüp kapandı. Biri `send_above_background`'da: "arka plan"
kararı yalnızca geometriye bakıyordu, dolayısıyla tam sayfa **yarı saydam
örtü** de arka plan sayılıyor ve fotoğraf onun üstüne çıkıyordu — yani
okunabilirliği sağlayan tek katman işlevsiz kalıyordu. Öteki, saydamlık
ölçümünün `<bG>` ağacının tamamına bakması: gölge rengindeki alpha yüzünden
altın sarısı opak bir şerit "örtü" sanılıyor ve gerçekten örtüsüz bir slayt
örtülü ilan ediliyordu. Ölçüm artık yalnızca dolgu yuvasına bakıyor.

### Kayıt parçayı değil KAYNAĞI anlatır

Storyline'ın kendi yazdığı bir kayıt okundu (`REF_SONRA.story`, kullanıcı bir
görseli elle ekleyip kaydetti) ve alanların neyi gösterdiği oradan çıktı:

| Alan | Neyi anlatır | Örnek |
|---|---|---|
| `bytes` | **diskteki** dosyanın boyutu | 3.229.567 |
| parça | pakete yazılan baytlar | 532.010 (Storyline yeniden kodluyor) |
| `md5Checksum/stream` | paketteki baytların md5'i | — |
| `md5Checksum/source` | **diskteki** dosyanın md5'i | — |
| `origFile` / `source` | dosyanın tam yolu | `C:\Users\...\foto.jpg` |
| `modDT` | dosyanın değiştirilme zamanı | gerçek zaman damgası |

Biz her alanı **parçadan** türetiyorduk: `origFile` ve `source` boş, `modDT`
sıfır tarih, `bytes` parçanın boyutu, iki md5 de aynı. Sonucu tek cümleyle:
**Storyline görseli hiç göstermedi.** Ne JPEG ne PNG, ne 8 KB'lık ne 3 MB'lık,
dosya geçerli ve `assetG → kayıt → md5 → parça → ilişki` zincirinin her halkası
izlenebilir olduğu hâlde — slaytta "The image can't be displayed" yazıyordu.

Ayırt edici deney: aynı slayta, aynı baytlarla, iki kopya kondu. Biri Storyline'ın
kendi kaydını gösteren ikinci bir `<pic>`, öteki alanları yukarıdaki gibi
doldurulmuş yeni bir kayıt. **İkisi de göründü.** Yani baytlar, şekil, ilişki ve
paket masumdu; kusur kaydın kaynağı anlatmamasıydı.

Hangi alanın tek başına belirleyici olduğu **ayrılmadı**: beşi birlikte
değiştirildi ve birlikte çalıştı. Ayırmak beş ayrı Storyline denemesi demekti ve
değeri, doğru davranışın kendisinden azdı. `tools/medya_probe.py` altısını da
ölçüyor.

### Degrade, saydamlık, katmanlanma

Üretilen slaytların "yapay" görünmesinin üç somut sebebi vardı: zeminler düz
renkti, görsel hiç kullanılmıyordu ve her şey aynı ızgarada duruyordu. Üçü de
biçimde zaten karşılığı olan ama kullanılmayan yapılardı.

```xml
<gradFill type="lin" style="lin" rot="true" angle="90">
  <centerPt x="0.5" y="0.5" /><fillRect l="0" t="0" r="0" b="0" />
  <stops><stop g="…" verG="…" pos="0">…</stop>
         <stop g="…" verG="…" pos="100">…</stop></stops>
</gradFill>

<solidFill><clr><srgbClr val="0E1B3D" /><alpha val="55000" /></clr></solidFill>
```

`gradFill`, `solidFill` ile aynı yuvada durur ve duraklar 0–100 arasıdır. Saydamlık
şeklin değil **rengin** içindedir: `<alpha val="0–100000">`, 100000 opak demek.
Taranan destelerde en çok geçen değerler 60000, 43137 ve 40000 — yani uygulama
bunu sürekli yazıyor, biz yazmıyorduk.

Bunun üstüne görsel yerleşimi (`image_style`) geldi:

| Değer | Ne yapar |
|---|---|
| `panel` | Sağ sütunda yuvarlak kart — güvenli varsayılan |
| `bleed` | Sağ kenardan taşan tam boy blok, yazı solda daralır |
| `hero` | Görsel tüm slaydı kaplar, üstüne okunabilirlik örtüsü konur |

`hero`'nun çalışması için görselin **yazının altına ama zeminin üstüne** girmesi
gerekir. `add_image(behind=true)` bunu yapar; şekli en arkaya atıp sonra tam
kanamalı zemin şekillerinin hemen üstüne taşır. En arkada bıraksaydı, arka plan
dikdörtgeni fotoğrafı tamamen örterdi. "Zemin" isimle değil geometriyle
belirlenir (yığının dibinden başlayıp slaydı bütünüyle kaplayan şekiller), böylece
elle yapılmış slaytlar da aynı davranışı alır.

SVG önizleyici degradeyi `<linearGradient>` olarak, saydamlığı `rgba()` olarak
çiziyor. Önizlemenin işi yapılanı göstermek; degradeyi ilk durağına düzleştirmek
tam da yargılanacak şeyi gizlerdi.

## Slayt üretimi: neden klonlama

Storyline'da "bana slayt yap" diye bir şema yok. Bir slayt; şekilleri
tetikleyicilere, durumlara, etkileşimlere ve geri bildirim katmanlarına
bağlayan yoğun bir GUID grafiği — üstüne tutarlı kalması gereken bir zaman
çizelgesi (`tmCtxLst`). Bunu sıfırdan üretmek kırılgan olur.

Bunun yerine mevcut bir slayt klonlanır ve **yalnızca o slaydın tanımladığı**
GUID'ler yenilenir. Hangilerinin tanımlı olduğu kesin olarak bellidir: bir
slayt `g=` veya `verG=` niteliğinde geçen her değeri tanımlar, geri kalan her
şeye (düzenler, asıl slaytlar, değişkenler, diğer slaytlar) yalnızca referans
verir. Gerçek bir kursta ölçüldüğünde: 122 tanımlı, 27 referans, bunların 13'ü
slayt dışına. Sadece tanımlı kümeyi yeniden eşleyince ortaya yapısı birebir
aynı, kendi içinde tutarlı, aynı dış iskelete bağlı bir slayt çıkar — GUID
olmayan her byte olduğu gibi kalır.

Bir slaydın var olması için **beş** yere kayıt gerekir; biri atlanırsa Storyline
ya slaydı sessizce düşürür ya da dosyayı reddeder:

```
1. story/slides/slideN.xml              slaydın kendisi
2. story/slides/_rels/slideN.xml.rels   medya ilişkileri
3. story/_rels/story.xml.rels           parça <-> ilişki kimliği
4. story/story.xml                      sahne sldIdLst + toc girdisi
5. [Content_Types].xml                  içerik tipi Override
```

Slayt parçaları **onaltılık** numaralanır: `slide.xml`=1, `slide9.xml`=9,
`slidea.xml`=10, `slide10.xml`=16.

### Kurs iskeleti kurma

`build_course` işlemleri sırayla uygular ve sonunda **bir kez** kaydeder:

```json
[
  {"op": "create_scene", "name": "01_Giris"},
  {"op": "add_slide",    "template": "slide7.xml", "scene": "01_Giris",
                         "title": "Bilgi Güvenliği Temelleri"},
  {"op": "add_question", "template": "slide.xml",  "scene": "01_Giris",
                         "prompt": "Kurumsal veriyi en çok riske atan davranış?",
                         "choices": ["Parolayı not kağıdına yazmak",
                                     "Ekranı kilitlemek",
                                     "Güncellemeleri kurmak",
                                     "VPN kullanmak"],
                         "correct": [0], "points": 25}
]
```

### Adres biçimi

```
slide10.xml|<şekilGUID>|<blok>|<span>
```

`extract_text` ve `search_text` her kayıtta bu adresi verir; `update_text` aynı
adresi bekler. GUID yazma sırasında doğrulanır — yanlış slayta yazma olmaz.

## Güvenlik

- **Kilitli dosyaya yazılmaz.** Koruma uygulamaya değil **dosyaya** bakar:
  Storyline yalnızca açık olan projeyi tutar, diğer kurslar o sırada tamamen
  okunabilir ve yazılabilir kalır. "Storyline çalışıyor mu" diye sormak,
  hiçbir şeyin dokunmadığı dosyalarda da çalışmayı durdurur — koruma değil,
  engel olur.
- Araçlar varsayılan olarak `<ad>.edited.story` yazar; `in_place=true` kaynağın
  üzerine yazar ve önce `.bak` alır. **Panel her zaman `in_place` kullanır** —
  gerekçesi aşağıda, "Dosya davranışı".
- Değiştirilmeyen her parça **byte-byte** kopyalanır; yalnızca düzenlenen slayt
  yeniden serileştirilir.
- Yazılan paket baştan açılıp **tüm XML parçaları yeniden ayrıştırılarak**
  doğrulanır; sonuç `verified` alanında döner.

## Kullanım

```
Şu kursu incele: C:\...\kurs.story — kaç slayt, hangi sahneler?
Tüm quiz sorularını ve doğru cevaplarını listele.
"Covid" geçen tüm metinleri bul.
Kursu denetle: kullanılmayan değişken ve alt metinsiz görsel var mı?
Slayt 3'teki soru kökünü daha net bir dille yeniden yaz.

Bu kursa "Parola Güvenliği" diye bir bölüm ekle,
içine bir giriş slaydı ve 5 soruluk bir sınav koy.
```

### Storyline açıkken

Storyline, düzenlediği projeyi **hiçbir paylaşıma izin vermeden** açar: o dosya
okunamaz da, yazılamaz da. Ama kilit yalnızca o dosyaya aittir — ölçüldü:

| Dosya | Okuma | Yazma |
|---|---|---|
| Storyline'da açık olan | reddedilir | reddedilir |
| Diğer `.story` dosyaları | çalışır | **çalışır** |

Başka bir kurs açıkken çalışmak zaten serbesttir. Üzerinde çalışılacak proje
açıksa **panel döngüyü kendisi yürütür**: kaydeder, Storyline'ı kapatır,
değişikliği uygular, dosyayı yeniden açar. Kullanıcıdan bir şey istenmez.

```
⟳ Storyline bu projeyi açık tutuyor — kaydedilip kapatılıyor…
⟳ Kapatıldı. Değişiklik uygulanıyor…
🔧 add_text_box   text=Hoş geldiniz · color=#FFED00
⟳ Storyline'da yeniden açılıyor…
✔ Slayta hoş geldiniz metni eklendi.
```

Açık dosya neden düzenlenemiyor: kilit bir yana, Storyline'ın kendi bellek
kopyası vardır — kaydettiğinde arkadan yapılan değişikliği ezer ve bu arada
ekranda da göstermez. Doğru olan, dosyayı o sırada hiç ellememektir.

Hangi projenin açık olduğu pencere başlığından okunur — ve başlık iki şey
birden söyler:

```
Articulate Storyline - [try.story]     kaydedilmiş
Articulate Storyline - [try.story*]    kaydedilmemiş değişiklik var
```

Böylece "bu, birazdan düzenleyeceğimiz dosya mı?" sorusu kesin yanıtlanır;
çalışan herhangi bir Storyline'ın onu tuttuğu varsayılmaz. Sondaki yıldız da
atılmaz: kaydın gerçekten oturduğu, sabit bir süre bekleyip ummak yerine
**yıldızın kaybolmasıyla doğrulanır**. Temizlenmezse işlem iptal edilir ve
dosyaya dokunulmaz — kaydedilmemiş iş böyle kaybolur.

Bu yıldız bir kez sessiz bir kusura yol açtı: başlıktaki adı dosya adıyla
birebir karşılaştırıyordum, `try.story*` ≠ `try.story` olduğu için döngü hiç
tetiklenmedi ve araç kullanıcıdan dosyayı kapatmasını istedi.

İki koruma var, çünkü bu, kullanıcının içinde çalıştığı bir uygulamayı kapatır:

- **Önce her zaman Ctrl+S gönderilir** ve kaydın oturmasına süre tanınır. En
  kötü ihtimalle zaten kayıtlı bir projede boşa gider.
- **Kapatma nazik bir `WM_CLOSE`'dur, asla öldürme değil.** Storyline çıkmazsa
  — kaydedilmemiş değişiklik uyarısı, açık bir iletişim kutusu — bekleme süresi
  dolar ve işlem **dosyaya hiç dokunmadan** iptal edilir; zorlanmaz.

## Panel (masaüstü arayüzü)

`Storyline Panel.bat` dosyasına çift tıklayın; kendi penceresinde açılır,
Storyline'ın yanına koyabilirsiniz.

Üç sekme var. **Komut** serbest metin alır ve işi yapar; **Genel Bakış**
sonucu gösterir (sahne/slayt ağacı, doğru cevaplarıyla soru listesi), her
komuttan sonra kendini yeniler; **Görsel & Video** kursun sizden beklediği
dosyaları listeler.

```
> SINAV bölümüne oltalama saldırılarıyla ilgili 3 soru ekle
  🔧 list_templates
  🔧 build_course   scene=SINAV · 3 soru
  ✔ SINAV bölümüne 3 soru eklendi.
     6 adım · 18.4 sn        [kurs.story]  [Storyline'da aç]
```

Panel bir zamanlar form tabanlıydı — soru/slayt/bölüm ekleme formları ve bir
işlem kuyruğu. Kaldırıldı: alan doldurmak, işi Storyline'da elle yapmanın
başka bir biçimiydi; aracın var oluş sebebi tam da bunu ortadan kaldırmak.

### Görsel & Video

Kursu kuran model neyin **gösterilmesi** gerektiğini bilir: "burada telefondaki
doğrulama bildiriminin göründüğü 20 saniyelik bir video olmalı". O videoyu
bulamaz, üretemez ve bekleyemez. Üç seçenekten ikisi kötü: kurulum dosya için
dursa kurs hiç bitmez, model sessizce vazgeçse slayt bir kutu metinden ibaret
kalır.

Üçüncüsü uygulanıyor: **kurs eksiksiz kurulur, istek ayrı bir yerde bekler.**

- Kurucu o slaytta `compose_slide`'ı `image_area` ile çağırır, yani **yer
  gerçekten ayrılır** — dosya geldiğinde konacağı kutu bellidir.
- İstek `<kurs>.medya.json` içine yazılır: ne (görsel/video), hangi slaytta,
  neye benzemeli, kaç saniye. Dosyada durur, bellekte değil — panel kapanıp
  açılabilir, kurs bir hafta sonra tamamlanabilir.
- Sekme yalnızca **dosya bekleyen slaytları** gösterir. Slayt listesi değildir;
  bütün slaytları saymak işi yeniden bir gezintiye çevirirdi.
- Dosyayı seçip **Gönder**'e basarsınız: panel dosyaları tam o ayrılmış alana
  koyar, kursu bir kez kaydeder ve istekleri "eklendi" olarak kapatır.

Şeritteki satır **olayı değil durumu** anlatır: süren iş dönen simge taşır,
biten iş ✓ taşır ve birkaç saniye sonra kendi kapanır. Ayrımı yapmayan bir
şerit, iş bittikten sonra da "dosyalar modüle ekleniyor" yazıp duruyordu
(kullanıcı bildirdi). Aynı sebeple bekleme de adını söyler: Storyline arkada
açılırken başlatılan bir ekleme, o açılışı beklerken "Storyline'ın yeniden
açılması bekleniyor" der — yoksa kullanıcı kendi işinin sürdüğünü sanır.

**Sipariş metni kopyalanabilir ve piksel ölçüsünü taşır.** O cümle panelde
okunmak için değil, bir görsel/video üretecine **yapıştırılmak** için var —
yanındaki *Kopyala* düğmesi tam olarak onu verir. Ölçü açıklamaya eklenir,
çünkü açıklama tek başına eksikti: üreteçten çıkan kare, slaytta ayrılan alana
oturmuyor. Sayı yüzdeden değil **o slaydın kendi koordinat uzayından** hesaplanır
(`medya.slayt_olcusu`) ve `medya.olcu` ile **tek yerde** üretilir; iki çağıran
(kurucu ve `request_media`) ayrı ayrı hesaplasaydı aynı slayt için iki farklı
boyut istenebilirdi.

Çerçeve olarak projenin bildirdiği boyut (`settings.story_size`) kullanılmaz ve
bunun sebebi ölçüldü (2026-08-29, `denee.story`): proje **1920×1080** bildiriyor
ama slaytların kimi **720×540**, kimi 1920×1080 — soru slaytları 1920×1080 bir
kurstan hasat edilmiş tohumlardan geliyor, içerik slaytları 720×540 şablondan
klonlanıyor. Sonuç somut: sipariş kullanıcıya "1920×1080 (16:9)" dedi,
kullanıcı tam o oranda bir görsel üretti (2752×1536), `add_image` yerleşimi
slaydın çerçevesinden (4:3) hesapladı ve görselin kenarlarından **%25'ini
kırptı**. İki yer aynı sayıyı ayrı kaynaktan hesapladığı sürece bu kaçınılmazdı;
`medya_akis_probe` artık ikisinin ayrışabildiğini ve siparişin slaydın
çerçevesini kullandığını ölçüyor.

Ölçünün gerçek karşılığı `uygula`'da: `hero` ve `bleed` alanları
**doldurulur**. Sipariş bu yüzden "tam 720×540 (4:3) — daha yüksek çözünürlük
olabilir, oran aynı kalsın" der; `panel` stilinde ise dosya kırpılmadan
sığdırıldığı için "ya da daha büyüğü" yeterlidir. Videoda ayrıca süre yazılır.

#### Doldurmak germek değil, kırpmaktır

Ölçüldü (2026-08-29, kullanıcının kendi kursu): 2172×724 **(3:1)** bir fotoğraf
720×540 **(4:3)** kapağa `keep_ratio=False` ile yerleştirildi, yani genişliği
%44'e sıkıştı. Kusur sessizdi — dosya geçerli, doğrulama temiz, `.story` açılıyor;
yanlış görünen tek şey insanlardı. Kullanıcı "düzgün eklenemedi" diye bildirdi.

`add_image` artık üç seçenekli bir `fit` alıyor: `contain` (sığdır, varsayılan),
`cover` (doldur), `stretch` (ger — yalnızca açıkça istenirse). `cover`
**baytları kırpar**: kaynak, alanın oranına göre ortadan kesilir, sonra tam
alana oturur. Aynı fotoğraf artık 965×724 olarak giriyor — bozulma yok, üstelik
paket de küçülüyor (1675 KB → 718 KB).

Storyline'ın kendi kırpma alanı (`<picFormat><sourceRect>`) **kullanılmadı**:
iki gerçek kursta kırpılmış tek bir `<pic>` yok, yani biriminin ne olduğu
(yüzde mi, EMU mu) ölçülemedi. Tahmin edilen bir birim, dosya açılana kadar
görünmeyen bir kusurdur; kendi kırptığımız baytın nereye oturduğu ise bellidir.
Pillow yoksa `cover` sessizce `contain`'e düşer — kenarda boşluk kalması,
bozulmuş bir kapaktan iyidir.

#### Bekleme, Storyline'ın açılışı kadar

Eklemenin kendisi **1.2 saniye** (ölçüldü: 2.3 MB kurs + 1.6 MB fotoğraf,
kırpma dahil). Geri kalan bekleme Storyline'ın kapanıp yeniden açılmasıydı ve
panel **onu bekliyordu**: iş biteli yarım dakika olmuş bir panele bakılıyordu.
Artık sonuç yazılır yazılmaz dönüyor, Storyline arkada açılıyor ve açıldığında
kendi satırını yazıyor. Açılış sürerken başlatılan her yazma işlemi (`Gönder`,
komut, kurs kurma) önce `_acilisi_bekle()` çağırır — yoksa panel dosyayı
yazarken Storyline eski kopyayı açar ve ilk kaydında üstüne yazardı.

İstek, alan **kesin olarak** ayrılabilen iki durumda kaydedilir: kapak (`hero`)
ve düz metinli `content` (`bleed`). Ölçüldü: `bullets` ve `statement`
düzenlerinde `image_area` her zaman `None` döner, `content+panel`'de ise
varyanta göre değişir — bazı varyantların panel sütunu yoktur. Yer ayrılmadığı
hâlde istek kaydetmek, dosyayı sonradan metnin üstüne düşürmek demekti.

Aynı ölçüm bir tuzağı da açtı: `content` + `bullets` + panel varyantında
ayrılan alanı **kartlar** kullanıyor, ama `compose_slide` onu yine
`image_area` diye bildiriyordu. Prompt "dönen `image_area`'yı aynen
`add_image`'e geçir" dediği için görsel maddelerin üstüne konurdu. Artık
kartlara giden alan dışarıya bildirilmiyor.

**İsteği panel seçer, model yalnızca tarif eder.** 2026-08-29'da üretilen
gerçek kursta model tek bir medya istemedi ve kurs baştan sona metin çıktı.
Prompt'a "iste" yazmak bunu ihtimale bırakır; aynı brief bir koşuda ister,
ötekinde istemez — yani görsel varlığı kursun değil, o koşunun özelliği olur.
İki karar bu yüzden ayrıldı (`builder._medya_plani`):

| Karar | Kim verir | Nasıl |
|---|---|---|
| **Nereye, kaç tane** | kurucu, deterministik | Yer ayrılabilen slaytlar (kapak + düz metinli `content`), sahne başına en fazla bir, toplam ≈ slayt sayısı / 6 (en az 2, en çok 6) |
| **Ne olsun** | model | Yalnızca seçilen yuvalar için, tek çağrıda tarif yazar |

Plan, içerik tamamlandıktan **sonra** ve slaytlar kurulmadan **önce** koşar:
"kaç tane oldu" ancak bütün kurs görünürken bilinebilir. Tarif çağrısı
başarısız olursa yuva boş kalmaz — slaydın kendi metninden mekanik bir sipariş
yazılır ve akışa "tarif modelden gelmedi" diye düşülür. Modelin içerik yazarken
kendiliğinden koyduğu istekler korunur ve hedefe sayılır: konuyu bilerek
yazılmış bir sipariş, buradan üretilenden iyidir.

Künyedeki **Görsel & video** seçimi üç değer alır: `otomatik` (varsayılan),
`yalnızca kapak`, `istenmesin`. Yoğunluk bilerek düşük tutuldu — her istek
kullanıcının bulacağı bir dosya demek ve **doldurulmayan bir istek slaytta boş
bir bant bırakır**. Daha fazlası komutla istenebilir ("3. bölüme de görsel
iste"), çünkü komut yolunda artık `request_media` var.

Kapak her koşulda ilk sırada: hero alanı zaten tam sayfa ve üstündeki örtü
yazıyı okunur tutuyor, yani doldurulmasa bile slayt normal görünür. İç
slaytlarda böyle bir zorlama yok:
konusu görsel olmayan bir slayta boş bant bırakmak, hiç istememekten kötü.

#### Komut yolu da isteyebilir

Komut kutusuna "2. slayda video koy" yazıldığında ajan bir süre şunu
söylüyordu: *"video bu araç setinde hiç desteklenmiyor."* Doğruydu — araç
yoktu. İkisi de eklendi:

- **`add_video`** — diskteki bir mp4/m4v'yi slayda koyar (`add_image`'in
  video karşılığı).
- **`request_media`** — dosya **elde yokken** sipariş bırakır: aynı deftere
  yazar, aynı sekmede görünür. Ajanın prompt'u artık "yapamıyorum" demeyi
  değil, sipariş bırakmayı söylüyor; alan ayırdıysa `compose_slide`'ın dönen
  `image_area`'sını sipariş ile birlikte veriyor.

Defter bu yüzden panelden motora taşındı (`storyline_mcp/medya.py`): iki yol
da aynı dosyaya yazıyor ve biçimi tek yer biliyor.

Komut kutusundaki "Görsel iliştir" düğmesi kaldırıldı. Bir görseli komuta
iliştirmek, nereye konacağını **ayrıca yazmayı** gerektiriyordu; istek zaten
slaydı ve alanı biliyor.

#### Video dosyanın içinde ne oluyor

Görselde dört parça vardı (bayt, `<media>` kaydı, ilişki, `<pic>` şekli).
Videoda ikisi değişir ve ikisi de **gerçek bir kurstan ölçülerek** öğrenildi
(`test/0_duz_kopya.story`, iki video):

- Baytlar `.mpeg` uzantılı bir parça olarak yazılır ve `video/mpeg` ilan
  edilir, ama **MP4'ün kendisidir**: ikisi de `ftypisom` ile başlıyor ve md5'i
  `<video>` kaydının damgasına birebir eşit. Yani Storyline dönüştürmüyor.
- Kayıt `<media>` değil `<video>`: piksel boyu kayıtta, süre ve kare hızı
  şeklin `<movie>` alanında durur. Bunlar MP4'ün `moov` atomundan okunur —
  zaman çizelgesi filmden kısa kalırsa video ortasından kesilir ve dosyada
  hiçbir şey bunu bildirmez.
- `thumbG` bir poster görseline çıkar. Gerçek kare çıkarmak H.264 çözmek
  demek; onun yerine doğru orandaki düz renk bir PNG kaydedilir, böylece
  gösterge hiçbir yere değil, **var olan bir kayda** bakar.

`mp4_info` iki gerçek videoda Storyline'ın kendi yazdığı sayılarla
karşılaştırıldı: 9500 ms / 24 fps / 1280x720 ve 10043 ms / 30 fps / 1920x1080 —
üçü de birebir.

```
.venv/Scripts/python.exe tools/medya_probe.py       # bayt -> kayıt -> şekil
.venv/Scripts/python.exe tools/medya_akis_probe.py  # istek -> dosya -> slayt
```

Desteklenen biçimler: görselde `.png .jpg .jpeg .gif`, videoda `.mp4 .m4v`.

### Komutu ne çalıştırıyor

Panel doğrudan Anthropic API'sine bağlanmaz. VS Code eklentisiyle gelen ve
**zaten oturum açmış** Claude Code CLI'ını headless modda sürer:

```
claude -p "<komut>" --mcp-config <gecici> --strict-mcp-config
        --allowedTools mcp__storyline__* --output-format stream-json
```

Dolayısıyla ikinci bir API anahtarı ve ikinci bir fatura yok; çalışmalar diğer
Claude Code kullanımıyla aynı kotadan yer. Panelde model seçici bulunur —
yapısal komutlar için Haiku genelde yeterlidir ve belirgin biçimde az yer.

`--strict-mcp-config` yalnızca verilen sunucuyu yükler, izin listesi de sadece
storyline araçlarını içerir: kabuk yok, dosya yazma yok, ağ yok. Headless modda
izin sorusunu yanıtlayacak kimse olmadığından liste dışı her şey sıraya
alınmaz, **reddedilir** — kısıt tavsiye değil, uygulanır.

Çıktı satır satır JSON olarak akar ve geldikçe sayfaya basılır; uzun bir kurs
kurulumu donmak yerine ilerlemesini bildirir.

### Dosya davranışı

Komutlar **seçili dosyayı yerinde** düzenler, her yazmadan önce `.bak` alarak.
Başta her sonuç `X.edited.story` olarak yazılıyordu; sonraki komut onu girdi
alınca `X.edited.edited.story` çıkıyordu — ad her talimatta bir katman
büyüyor, proje neredeyse aynı kopyalara dağılıyordu.

`.bak` **tek seviye** geri alma sağlar: her yazma bir öncekinin yedeğini
değiştirir. Bir aşamayı kalıcı saklamak isterseniz o noktada kopyasını alın.

### Neden HTTP sunucusu yok

pywebview'in `js_api` köprüsü sayfadan doğrudan Python çağırır. Port, CORS ve
pencere kapandıktan sonra dinlemeye devam eden yerel sunucu riski böylece
ortadan kalkar.

İki tuzak kodda yorumla işaretli, tekrar düşmemek için:

- **`Api` nesnesinde pencere referansı tutulmaz.** pywebview köprüyü kurarken
  nesnenin özniteliklerini dolaşır; saklanan bir `Window` onu native .NET
  `Form`'a götürür, orada `Bounds.Empty` kendi `.Empty`'sine sahip bir
  `Rectangle` döndürür ve zincir bitmez. Pencereye `webview.windows[0]`
  üzerinden erişilir.
- **`pythonw.exe` sürece stdout/stderr vermez**, ikisi de `None` olur. Günlük
  yazan ilk kitaplık ilk yazımda hata alır ve konsol olmadığı için hata
  hiçbir yere düşmez: pencere sessizce açılmaz. Uygulama başlangıçta bunu
  fark edip akışları `nul`'a yönlendirir.

## Kurulum

```powershell
uv venv
uv pip install -e ".[panel]"     # panel dahil
```

Yalnızca MCP sunucusu yetiyorsa `uv pip install -e .` de olur; panel o zaman
açılmaz. **Sessizce açılmaz:** `Storyline Panel.bat` `pythonw.exe` kullanır ve
o süreç stdout/stderr vermez, dolayısıyla eksik `pywebview`'in `ImportError`'ı
hiçbir yere düşmez — pencere hiç gelmez, hata da görünmez. Panel açılmıyorsa
önce şunu çalıştırın, gerçek sebep orada yazar:

```powershell
.venv/Scripts/python.exe panel/app.py
```

Sanal ortam **tam olarak `storyline-mcp/.venv`** olmalı: `.bat` dosyası
`%~dp0storyline-mcp\.venv\Scripts\pythonw.exe` yolunu sabit tutar.

Claude Code kaydı `~/.claude.json` içinde `mcpServers.storyline` olarak durur.
Panel WebView2 çalışma zamanını kullanır (Edge ile birlikte gelir).

## Bilinen sınırlar

- **Şablonun seçenek sayısı bağlayıcıdır.** 4 seçenekli bir soru şablonu 4
  seçenekli soru üretir; seçenek eklemek/çıkarmak sıfırdan şekil, durum,
  tetikleyici ve puanlama girdisi yaratmak demektir — klonlamanın kaçındığı şey.
  `list_templates` her adayın seçenek sayısını bildirir, uygun olanı seçin.
- **Sürükle-bırak şablonları desteklenmiyor.** Doğruluk `scoringData`'da değil
  eşleştirmede (`matchShpG`) tutulur ve bırakma hedeflerinin de klonlanması
  gerekir. Okumada `correct` yerine `drops_onto` bildirilir.
- Klonlanan slaytların tetikleyicileri **kaynağın hedeflerine** işaret etmeye
  devam eder (dış referanslar bilinçli olarak korunur). Menü slaydı gibi çok
  bağlantılı bir slayt klonlandığında bağlantıları gözden geçirin.
- Bir metin birden çok şekil durumunda kopyalanmışsa her kopya ayrı adrestir;
  `state_guid` alanı bunu görünür kılar.
- `docProps/summary.xml` bir yayınlama önbelleğidir ve güncellenmez; Storyline
  bir sonraki yayınlamada yeniden üretir.
- **Timeline animasyonu yok.** `animEffect` elemanı şekillerde var ama taranan
  62 dosyanın hepsinde boş — klonlanacak çalışan bir örnek bulunamadı. Klonlama
  stratejisinin dayanağı, gerçek bir örneği kopyalamaktır; olmayan bir şey
  kopyalanamaz. Storyline'da elle bir animasyon verilip kaydedilmiş tek bir
  slayt, bu sınırı kaldırmaya yeter.
- **Soru tipleri sınırlı.** Tek/çok seçmeli çalışıyor. Metin girişi, sıcak nokta
  ve soru bankaları için de aynı engel geçerli: klonlanacak örnek yok.

## Donör havuzu (`donors/`)

Tohum kütüphanesi elle yazılmaz, gerçek projelerden hasat edilir. `find_seed`
boş bir projede yalnızca gömülü tohumlara düşüyor — soru tarafında iki dosya —
ve her sınav bu yüzden aynı kılıkta çıkıyor. `donors/` o tavanı kaldırmak için
indirilen hazır projelerin durduğu yer.

Kural: **anatomi alınır, estetik alınmaz.** `<btn>` nitelik seti, durum
iskeleti, tetikleyici bağlantı noktaları ve soru etkileşim bloğu alınır; renk,
degrade, köşe yarıçapı ve font alınmaz. Bu ayrım yüzünden donörün eski olması
sorun değil. Ayrıntı ve indirme listesi [donors/README.md](donors/README.md)'de.

İki araç havuzu ölçer, ikisi de yazmaz:

| Komut | Ne yapar |
|---|---|
| `python tools/open_test.py` | Her dosyayı Storyline'da açtırır. Açılmayan havuza girmez. |
| `python tools/harvest_survey.py` | Envanter: dosya başına kaç `btn` varyantı, kaç soru görünümü, kaç state tanımlı nesne. |

`open_test.py` "açıldı mı" sorusunu kullanıcıya değil Storyline'a sorar: yüklü
proje dosya kilidi ve pencere başlığı bırakır, yükleme başarısızsa ikisi de
oluşmaz. Kendi projeniz açıksa önce kaydedip kapatır; kapanmazsa çalışmayı
zorlamak yerine bırakır.

`harvest_survey.py` varyantı yapısal sayar — geometri, durum kümesi, görsel
taşıyıp taşımadığı, çocuk eleman kümesi. Yalnızca dolgusu farklı iki buton tek
varyanttır, çünkü ikincisini klonlamak kütüphaneye yeni bir şey öğretmez.
Ölçümün kendisi bunu doğruluyor: kendi kurslarında (`kurs.story`) 20 buton var
ve hepsi tek varyant.

Kabul kriteri dosya başına en az 3 farklı buton varyantı; araç bunu kendisi
ölçer ve geçemeyen dosyayı `ZAYIF` diye işaretler.

### Buton bir rol, etiket değil

Havuzdaki 226 state'li şeklin yalnızca 10'u `<btn>`. Tasarımcılar rect, oval,
chevron çizip state veriyor; `<btn>` Storyline'ın kendi buton aracının çıktısı,
yani kaçmak istediğimiz tekdüzelik. Bu yüzden `find_seed` buton ararken etikete
değil **role** bakar: durum listesi taşıyan şekil.

Bunun bir yan etkisi var ve düzeltilmesi gerekti: artık kursun kendi butonu bir
`<roundRect>` olabildiğinden, kart zemini için istenen `roundRect` o butonu
bulup state'leriyle birlikte klonluyordu — süsleme, ölü bir kontrole
dönüşüyordu. `find_seed` artık primitif isterken durumlu şekilleri atlıyor.

### `find_seed` sırası

1. **Projenin kendi şekilleri** — varsa her zaman kazanır. Kurs içi tutarlılık
   havuzun sunabileceği her çeşitlilikten önce gelir; seçimin sabit kalmasını
   sağlayan da budur, ilk buton konduktan sonra her çağrı onu bulur.
2. **Donör havuzu** — hizmet ettiği roller için. Donör, kurs kimliğinden
   türetilir (`donors.choose`), yani kurs boyunca sabit, kurslar arasında farklı.
3. **Gömülü tohum** — son çare. Olmasa boş bir proje ilk metin kutusunu bile
   büyütemezdi.

Kimlik `identity` ile geçer ve verilmezse **proje dosya adına** düşer: iki kurs
iki dosyadır, yani yine farklı donör çekerler. MCP aracında bilerek açık
değildir — slayt başına ayarlanabilseydi, tasarımın yasakladığı şey olurdu:
her slaytta başka bir buton dili. `tools/consistency.py` bunu tesisat sayar.

### Aday havuzu bir sayı değil, bir eğri

Donörler provadan geçerek havuza girer: etiket bas, geri oku, gelmediyse düşür.
Ölçüt üç tane — etiket tutuyor mu, şeklin kendi metin girintisinden sonra
kutuya sığıyor mu, durumları birbirinden farklı mı. Statik bir eleme listesi
yerine prova, çünkü liste yeni donör eklendiği anda bayatlar.

Provanın **örnek etiketi bir ayardır** ve havuz büyüklüğünü o belirler:

Havuz bir dönem etiket uzunluğuna bağlıydı ve uzun etiketlerde çöküyordu —
12 harfte 1 adaya, 18 harfte sıfıra. Sebep, kutunun sabit olmasıydı: uzun
etiket taşıyordu, prova da taşıyan adayı eliyordu. **Kutu artık etikete göre
büyüdüğü için** ([`grow_to_fit`](storyline_mcp/shapes.py)) bağımlılık kalktı:

| prova etiketi | harf | havuz |
|---|---|---|
| Basla · Devam Et · KURSA BASLA · Sonraki Bolume Gec | 5–18 | **10** |

Aynı şey `CHAR_WIDTH_RATIO` için de geçerliydi. Oran 0.52'den 0.72'ye çıkınca
havuz bir ara 10'dan 8'e inmişti — yani havuz üyeliği bir kalibrasyon sabitine
bağlıydı. Büyümeden sonra ölçüldü: havuzdaki 10 adayın hepsi oran **1.00'da
bile** hayatta, yani hiçbiri sınırda durmuyor. Elenen üçü metrikten değil
yapıdan eleniyor (hiç metin koşusu yok).

Geriye kalan çeşitlilik sınırı hash'in kendisi: 10 yuvada beş kursun beşinin
de farklı çıkma oranı %13 — doğum günü aritmetiğinden kötü, çünkü küçük havuzda
düz hash düzensiz dağılıyor. Toplu üretim yapan çağıran
`donors.distinct_identities` ile tuzlanmış kimlik alır ve ayrışma garanti olur;
motor saf kalır, politika çağıranda.

Yan gözlem: havuz 10'dan 8'e inerken oran %13'ten %22'ye **çıkıyor**. Doğum
günü aritmetiği tersini söyler; fark, küçük havuzda düz hash'in düzensiz
dağılmasından. Yani tek tek üretilen kurslarda çeşitlilik teorik sınırdan
kötü. Toplu üretim yapan çağıran `donors.distinct_identities` ile tuzlanmış
kimlik alır ve ayrışma garanti olur; motor saf kalır, politika çağıranda.

## Öğretim ölçüsü: kurs öğrenciye bir şey yaptırıyor mu

Bu projedeki diğer her ölçü kursun **nasıl göründüğünü** soruyor.
`tools/rubric.py` bunu açıkça yazıyor: *"Icerigin dogrulugunu DEGERLENDIRME;
yalnizca gorsel tasarimi."* Beş ölçütün beşi de görsel. Dolayısıyla
tamamen okunur, tek etkileşimi "sonraki slayt" olan bir kurs bu rubrikten
yüksek puan alabilir — ve alırdı, çünkü rubriğin baktığı şey o değil.

`storyline_mcp/pedagogy.py` ayrı soruyu soruyor ve `audit`'ten dönüyor:

| Alan | Ne sayar |
|---|---|
| `ardisik_etkilesimsiz_slayt` | Okuma sırasında hiçbir şey yaptırmayan en uzun seri |
| `sahne_basina_soru` | Sahne → puanlı soru sayısı; `sorusuz_sahneler` boş olanlar |
| `sonuc_slaydi` | Tamamlama kanıtı var mı (sonuç slaydının kendi tetikleyici etiketleri) |
| `tetikleyici_cesitliligi` | Ayrık (event, action) çifti — **tanı, kapı değil** |

Ölçü **deterministik**. Saydığı şeyler XML'den doğrudan sayarak çıkıyor,
o yüzden buna LLM yargıcı takılmadı: `rubric.py`'nin uğraştığı sıcaklık ve
**sıra** karararsızlığını bedavaya geri getirirdi.

### Etkileşim tanımı — ve neden yazılı

Bir tetikleyici, **öğrencinin girdisiyle** başlayıp **salt gezinme olmayan**
bir iş yapıyorsa öğrenme etkileşimi sayılır. İki yarısı da gerekli. Tanım
gevşek bırakılırsa metrik zamanla neyi ölçtüğünü kaybeder, o yüzden seçimler
ad ad yazılı (`pedagogy.KAPSAM`, `audit` çıktısında `ogretim_kapsam`):

- **Menü tıklaması gezinmedir**, etkileşim değil: menü içerik hakkında değil
  **sıra** hakkında bir seçim. Sayılsaydı tek bir menü slaydı bütün kursu
  geçirirdi.
- **`showSubSlide` burada etkileşim sayılıyor**, ama aynı `audit`'in
  `slides_without_navigation` ölçütünde **gezinme** sayılıyor. İki ayrı soru,
  iki ayrı küme; `NAVIGATING_ACTIONS` bilerek paylaşılmıyor. Paylaşılsaydı
  katman açan bir kurs sessizce etkileşimsiz görünürdü.
- **`OnStateChange` tepkidir, girdi değil.** Durumu değiştiren tıklama zaten
  sayıldı; tepkiyi de saymak aynı etkileşimi iki kez sayardı.
- **Şekil durumları (hover/down) tek başına sayılmaz** — tetikleyicisi olmayan
  bir hover öğrenciden karar istemez.

### Kesitin dışında kalan

**Tetikleyici yazıldığı gibi sayılıyor, ateşlediği gibi değil.** 17 event'in
yalnızca ikisi (`OnStart`, `OnVariableValueChange`) preview'da tetiklendiği
**görülerek** ölçüldü; kalan 15 için kanıt hâlâ *"Storyline çökmüyor"*
seviyesinde ([JS_YOL_HARITASI.md](../JS_YOL_HARITASI.md)). Yoldaş alanı
eksik olduğu için sessizce çalışmayan bir `OnDrop` burada **etkileşim olarak
sayılır** ve çalışma anında hiçbir şey yapmaz. Bu, çeşitliliği artırmaya
çalışan bir sonraki turun gerçek riski ve backlog'da bağımlılık olarak yazılı.

**Sıfır bulgu iyi kurs demek değildir.** Ölçü etkileşimin **varlığını** sayar,
öğretme değerini ölçmez.

### Ölçü kullanılmadan önce ayırt ettiği gösterildi

`rubric.py` kendi çıktısından önce **kendini** ölçüyor; aynı disiplin burada
da uygulandı, ama fikstürsüz — 14 gerçek dosya zaten iki uç sunuyordu:

| Küme | `ardisik_etkilesimsiz_slayt` |
|---|---|
| Etkileşim donörleri (Accordion, Tabcordion, Dials, DragDrop) | 0–1 |
| Üretilen anlatım kursları (cyber, teknoloji_bagimliligi, zorMusteri) | 13–19 |

İki küme örtüşmüyor. Taban ölçüm `tools/ogretim_taban.json`'da dondurulmuş
durumda: SYSTEM_PROMPT'a öğretim bölümü eklendikten sonra aynı ölçü tekrar
koşulmadan, değişikliğin davranışı gerçekten değiştirdiği değil yalnızca
kelime sayısını artırdığı da mümkün kalır. İyileşme varsayılmaz, ölçülür.

## Doğrulama

Yazma işlemleri kendini şöyle denetler:

- Değiştirilmeyen her parça **byte-byte** kopyalanır (ölçüm: 120 parçanın
  117'si; değişen yalnızca üç kayıt dosyası).
- Yazılan paket baştan açılır, **tüm XML parçaları yeniden ayrıştırılır** ve
  **BOM'ları denetlenir**; sonuç `verified` alanında döner.
- Klonlar kaynakla **sıfır GUID paylaşır**, dış referanslar birebir korunur.

### UTF-8 BOM: ayrıştırmak yetmiyor

Storyline her XML ve `.rels` parçasını **UTF-8 BOM** ile yazar ve biri eksikse
paketi reddeder:

> This project is invalid or corrupt and cannot be opened.

Python'un XML ayrıştırıcısı BOM'u tümüyle yok sayar. Dolayısıyla BOM'u
düşürülmüş bir parça kusursuz ayrışır, "ayrıştırılabiliyor mu" temelli her
denetimden geçer — ve Storyline yine de açmaz. Bir dosyanın açılıp
açılmayacağına karar veren koşuldan **daha zayıf** bir koşulu denetlemek,
doğrulamayı işe yaramaz kılar.

Bu yüzden BOM yazarken **garanti edilir**, yazıldıktan sonra da denetlenir.

> **13 Ağustos 2026 ölçümü: bu varsayım olduğu gibi tutmuyor.** Kanaryanın
> olumsuz kontrolünü kurarken sınandı: `story/story.xml`'den BOM soyulmuş bir
> proje **açıldı**, `[Content_Types].xml`'den soyulmuş olan da **açıldı**.
> Reddedilen iki şey bozuk XML ve eksik parçaydı.
>
> Tek boş proje, tek Storyline sürümü — kuralı devirmeye yetmez ve BOM'u
> garanti etmek hâlâ ucuz sigorta, o yüzden kalıyor. Ama `verify()`'ın BOM
> denetimini "açılır mı"nın kapı bekçisi sanmayın; ölçüm onu desteklemiyor.
> Kanarya bu yüzden bozuk XML kullanıyor ([tools/canary.py](tools/canary.py)).

Korumak yetmez, garanti etmek gerekir: daha önceki bozuk bir yazmadan gelen bir
proje, parçaları zaten BOM'suz olarak gelir; bulduğunu aynalayan bir yazıcı
hasarı sadakatle taşır ve dosya kaç kez kaydedilirse kaydedilsin açılmaz.
Storyline istisnasız her XML ve `.rels` parçasına BOM koyduğu için yazıcı da
koyar — böylece **hasarlı projeler bir sonraki kayıtta kendiliğinden onarılır**.

Bu iki kez gerçekten oldu ve ikinci sefer öğreticiydi. Önce `replace_xml`
yalnızca XML bildirimini yazıyor, BOM'u düşürüyordu. Düzeltmenin ilk hâli
"orijinalde varsa koru" diyordu — ve zaten bozulmuş bir dosyada yokluğu korudu.
Dosya geçerli ZIP'ti, parçaların 45'te 44'ü sağlamdı, tüm XML testleri
geçiyordu; Storyline yine açmıyordu.

Yine de son söz Storyline'ındır: üretilen dosyayı açıp gözle doğrulayın.
