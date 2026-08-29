# JavaScript tetikleyicileri — yol haritası

Bu belge DEVIR.md'nin kurallarına tabidir. K-numaraları oradan.

---

## 0. Ne için

Storyline'ın araç tarafından **hiç yazılamayan** tek büyük mekanizması bu.
Bugün bir kurs "e-posta formatını doğrula", "sertifikaya adı bas", "kaldığı
yerden devam et" istediğinde tek yol kullanıcının Storyline'ı açıp elle
trigger yazması. Aracın varlık sebebi o dönüşü silmek; JS kapalıyken bu istek
sınıfının tamamı geri dönüyor.

Kapsam: `Execute JavaScript` tetikleyicisi. Web Object gömme bu yol haritasının
dışında — ayrı bir varlık türü, ayrı bir tur.

---

## 1. Ölçülen durum (2026-08-23)

Tahmin değil, dosyadan okundu.

| ne | nerede | durum |
|---|---|---|
| yazma yolu | `storyline_mcp/logic.py:199-275` | altı eylem: `adjustVar`, `jumpToSlide`, `jumpToScene`, `showSubSlide`, `hideSubSlide`, `changeShapeState`. **JS yok** |
| okuma yolu | `storyline_mcp/model.py:298` | `other/@js` zaten okunuyor, `javascript` alanı olarak dönüyor. **Okuma tarafı hazır** |
| XML slotu | `storyline_mcp/seeds/trigger.xml` | `<other open="" email="" js="" op="ass" …>` — slot tohumda **var ve boş** |
| MCP yüzeyi | `storyline_mcp/server.py:959` | `add_trigger` docstring'i altı eylemi sayıyor |
| op kuyruğu | `storyline_mcp/server.py:199` `_apply_op` | panel ve MCP aynı yerden geçiyor — tek nokta |
| panel UI | `panel/index.html` | trigger bölmesi yok; profil kartı brief alıyor |
| kontroller | `tools/` (40 dosya) | **hiçbiri JS metnine bakmıyor** |

Donör taraması (6 donör + 2 kanarya, bütün `*.xml`):

```
action degerleri:  showSubSlide 136 · changeShapeState 123 · jumpToSlide 43
                   submitInteraction 40 · adjustVar 32 · Move 19 · new 3
                   hideSubSlide 2
js="" gecen yer:   395  (hepsi bos)
JS action'i:       HIC GECMIYOR
```

Yani havuzda JS kullanan tek örnek yok. Biçim buradan okunamaz.

---

## 2. Tek bilinmeyen: action'ın adı

`executeJavaScript` mi, `execJS` mi, başka bir şey mi — bilinmiyor. A1'de aynı
durum vardı ve ders şuydu: **doğru biçim tahmin edilmedi, gerçek bir kurstan
okundu.** Burada da tahmin edilmeyecek.

Tahminin bedeli bu projede ölçülü: `<data>` on iki çocuk slotu taşıyor ve
yokluklarına tolerans yok; parse eden ama açılmayan XML iki kez üretildi.
Yanlış `action` değeri de aynı aileye girer — dosya geçerli kalır, Storyline
trigger'ı sessizce düşürür ya da açmayı reddeder.

---

## 3. Fazlar

### Faz J0 — Biçimi öğren — **BİTTİ (2026-08-23)**

Dördün üçü ölçüldü, biri ölçülmedi ve bu ayrımıyla yazılıyor.

| ne | değer | nasıl |
|---|---|---|
| `data/@action` | **`executeJavaScript`** | iki bağımsız kaynak: DLL taraması (kanaryalı) + Storyline'ın kendi agent şeması |
| `data/@actSubType` | **`spec`** | tur sonrası **aynen** geri geldi, Storyline değiştirmedi |
| `other/@js` kaçışı | **korunuyor** | ElementTree `\n` → `&#10;`, tur sonrası metin **birebir** aynı; `&`, `<`, `"`, `'` sorunsuz |
| uzunluk | **1M'e kadar kırpılma yok** | sentinel ile, beş noktada; üst sınır aranmadı ve bilinmiyor |

**Doğrulama tur sonrası dosyayla bitmedi.** Storyline'ın Triggers paneli
tetikleyiciyi *"When the timeline starts on this slide / JavaScript Trigger /
Execute JavaScript"* diye gösterdi — yani biçim dosyada hayatta kalmakla
kalmadı, **anlamlandırıldı**. Bu, "dosya açılıyor" ile "biçim geçerli"
arasındaki farkı kapatan ölçü.

Ek kanıt, kazara: kirletme yolu bir slayt çoğalttı ve **kopyadaki JS
trigger'ı da aynen durdu**. Storyline trigger'ı kendi klonlama yolundan
geçirdi — okuyup geri yazmakla açıklanamaz.

Araç: `tools/js_probe.py` (`--tarama` Storyline açmadan action adını verir).

<details>
<summary>Özgün plan (referans için)</summary>

Ölçülecek dört şey:

1. `data/@action` değeri
2. `data/@actSubType` değeri (`spec` / `me` / başka)
3. `other/@js`'in kaçış biçimi — satır sonu ham mı `&#xA;` mi; `&`, `<`,
   tırnak nasıl duruyor. **Sessiz bozulmanın en olası yeri burası:** ham `&`
   dosyayı açılmaz yapar.
4. Uzunluk sınırı — 500 satırlık kod aynı öznitelikte mi duruyor, yoksa
   Storyline onu başka bir parçaya mı taşıyor.

**Yöntem A — eleme turu (tercih, elle iş yok).** `tools/js_probe.py`: aday
action değerlerini ayrı kopyalara yazar, `open_test.py` mantığıyla her birini
Storyline'da açar, `storyline_ctl.save_and_close` ile aç-kaydet-kapat turu
yapar ve dosyayı geri okur. Storyline tanımadığı action'ı ya düşürür ya
normalize eder; hayatta kalan aday doğru addır.

Turun koştuğu ayrıca kanıtlanır (`dirty_gate`, bayt farkı) — K3: "değişmedi"
ile "hiç koşmadı" aynı görünür. Hiçbir aday hayatta kalmazsa sonuç
**"bulunamadı"**dır, "JS yok" değil (K1).

**Yöntem B — hazır örnek.** Elde JS trigger'ı taşıyan herhangi bir `.story`
varsa `list_triggers` dördünü de tek atışta verir; `model.py` `javascript`
alanını zaten döküyor. Yöntem A'yı gereksiz kılar.

> J0 bitmeden J1'e geçilmez. Bu faz ölçüm, sonraki faz onun üstüne kuruluyor.

</details>

---

### Faz J1 — Yazma yolu — **BİTTİ (2026-08-23)**

Üç yere bağlandı:

- [`logic.add_trigger`](storyline-mcp/storyline_mcp/logic.py) — `execute_javascript` dalı, `javascript` parametresi
- [`server.add_trigger`](storyline-mcp/storyline_mcp/server.py) — MCP aracı, `javascript` parametresi + köprü açıklaması
- [`server._apply_op`](storyline-mcp/storyline_mcp/server.py) — `add_trigger` **ve** `add_variable`

Üçüncüsü plandan fazlası ve **ayrı bir kusurdu**: op kuyruğunda ne
`add_trigger` ne `add_variable` vardı. `logic.py` ikisini de yazıyor, ikisi de
MCP aracı olarak sunuluyor, ama `build_course` ve panel kuyruğu onları hiç
çağırmıyordu — yani dallanma katmanının tamamı kurs kurma yolundan
**ulaşılamaz** durumdaydı. K8'in tam örneği: sınandı ≠ bağlandı.

Yeni düğüm yaratılmıyor — slot tohumda hazır (`<other ... js="" ...>`).

**Kanarya:** JS trigger'ı üretim yolundan (op kuyruğu) yazıldı, dosya
Storyline'da açıldı ve Triggers panelinde doğru göründü. Kod `&&` ve `<`
içeriyordu; kaçış da o turda doğrulandı.

---

### Yol boyunca çıkan üç kusur — J2'den önce duruyorlar

**1. `EVENTS` kapısının iki değeri Storyline'ı çökertiyordu — ÖLÇÜLDÜ ve DÜZELTİLDİ.**

Liste elle yazılmıştı ve gerçek kümeyle üç yönden ayrışmıştı:

| ne | ölçüm |
|---|---|
| `OnSlideEnd` | **Storyline'ı çökertiyor** — ve listede geçerli sayılıyordu |
| `OnPrevButtonClick` | **Storyline'ı çökertiyor** — o da listedeydi |
| `OnDialTurns` · `OnDrop` · `OnStateChange` | geçerli, donörlerde **105 kez** geçiyor, listede yok → reddediliyordu |
| `OnVariableValueChange` | geçerli — **JS köprüsünün dayandığı olay**, listede yoktu |

Çökme, dosyayı açılmaz **yapmıyor**: dosya açılıyor, tetikleyici paneli
doldurulurken Storyline "Error Report" ile düşüyor. Yani "açıldı mı" diye
soran bir kontrol bu kusuru göremezdi — kart seçip paneli doldurmak ölçümün
parçası, kolaylık değil.

İkisi de kod tabanında hiç kullanılmamıştı: gizli mayın, kullanan ilk kişi
kendi Storyline'ını düşürecekti.

**Çökme deseni gecikmeli bir bozulma riski taşıyor, ve gate'in kritikliği
buradan geliyor.** Dosya build eden ortamda sorunsuz üretilir, açılır, hatta
kaydedilir — çökme ancak *o slaydın tetikleyici paneli açıldığında* olur.
Yani kusur, kursu üreten makinede değil, dosyayı sonradan açan **başka bir
yazarın** ekranında patlar. Bu yüzden gate dokümantasyon notu değil, kod
yolunda reddeden bir kontrol; ve üç yolun üçünde de koştuğu ayrı ayrı ölçüldü
(`logic.add_trigger`, MCP aracı, `_apply_op` kuyruğu — üçü de aynı kapıya
iniyor).

**İki şeyin kanıt olmadığı ayrıca ölçüldü:**

- *Kalıp benzerliği* — `OnNextButtonClick` çalışıyor, ama aynı kalıptaki
  `OnSubmitButtonClick` / `OnFinishButtonClick` / `OnFirstButtonClick` /
  `OnLastButtonClick` dördü de çökertiyor.
- *DLL'de geçmek* — `OnPrevButtonClick` DLL'de duruyor ve çökertiyor;
  oradaki adlar C# olay adları. `ObjectLosesFocus` de öyle, XML karşılığı
  `OnLostFocus`.

Liste artık **ölçülerek** kuruldu: 17 doğrulanmış ad + 9 çökerten ad, ikincisi
özel hata mesajıyla reddediliyor ("`OnSlideEnd` yerine `OnEnd`"). Araç:
`tools/event_probe.py`, `--dogrula` iki yönlü regresyon koşuyor (K7).

Kalan boşluk: "önceki butona tıklama" olayının karşılığı **bulunamadı** —
`OnPrevButtonClick`, `OnPreviousButtonClick`, `OnPrevButton` üçü de çökertiyor.
`PreviousButton` yalnızca **hedef** olarak kullanılabiliyor (`change_state`).
Bu "yok" değil, "bulunamadı".

**2. `add_text_box` her çağrıda `NameError` — DÜZELTİLDİ.**
[authoring.py:1430](storyline-mcp/storyline_mcp/authoring.py#L1430) dönüşte
`label_overflow` kullanıyordu; o değişken `add_button`'da tanımlı, punto
küçültme zincirinin sonunda. `add_text_box` o zinciri hiç çalıştırmıyor —
satır kopyalama artığıydı, kaldırıldı. Açık kalan ayrı iş: `h` verildiğinde
metin sığmıyorsa sessizce kırpılıyor ve bunu sayan ölçü yok.

**3. `make_dirty` Story View'da kirletemiyordu** — düzeltildi
([storyline_ctl.py](storyline-mcp/panel/storyline_ctl.py)), çünkü J0'ın turu
buna bağlıydı. Sebep ölçüldü: Storyline dosyayı Story View'da açıyor, orada
`Ctrl+A` hiçbir şey seçmiyor (kare alındı, "Duplicate" gri kaldı) ve ok
tuşları şekil taşımadığı için undo yığını dolmuyor. Yeni yol slayt kartına
tıklayıp `Ctrl+D` gönderiyor ve **yan etkisini bildiriyor**: bir slayt
çoğaltıyor.

---

### Köprü uçtan uca çalışıyor — **ÖLÇÜLDÜ (2026-08-23)**

Projenin asıl iddiası buydu ve parçalar ayrı ayrı doğru olmasına rağmen
birlikte hiç koşmamıştı. Preview'da koşturuldu; ölçüm yüzeyi **çalışan
slaydın kendisi**, dosya değil.

Üç halka **ayrı ayrı okunabilir** kuruldu, yoksa "çalışmadı" hangi halkanın
kırıldığını söylemez (A1'in dersi). Ekranda iki değer:

```
SKOR=%Skor%     JS'in SetVar'i isledi mi
KANIT=%Kanit%   OnVariableValueChange tetiklendi mi
```

| gözlenen | anlamı |
|---|---|
| `SKOR=0`, `KANIT=BASLANGIC` | JS hiç koşmadı |
| `SKOR=42`, `KANIT=BASLANGIC` | JS koştu, **olay tetiklenmedi** |
| `SKOR=42`, `KANIT=ZINCIR_TAMAM` | tam zincir çalıştı |

**Ve ilk koşu ortadaki hücreyi verdi.** Sebep: `OnVariableValueChange`
izlenen değişkeni ayrı bir alanda taşıyor — `other/@varChangeG` — ve tohumda
o öznitelik yok. Alan yazılmadan olay hiç tetiklenmiyor: dosya açılıyor,
panel tetikleyiciyi gösteriyor, hiçbir şey olmuyor. **Sessiz başarısızlık.**

İki varyant yan yana koşuldu ve aralarındaki tek fark o öznitelikti; alan adı
tahmindi (agent şemasındaki `variableChangeGuid`'den), o yüzden
karşılaştırmayla kanıtlandı.

Düzeltme: `add_trigger`'a **`watch`** parametresi. `OnVariableValueChange`
seçilip `watch` verilmezse çağrı **reddediliyor** — çalışmayan bir trigger
üretmektense hata vermek. `watch` ile `variable` ayrı: biri izlenen, diğeri
değiştirilen ("Skor değişince Kanit'i ayarla").

Son kanıt üretim yolundan alındı: op kuyruğundan `watch` ile kurulan dosya
preview'da `KANIT=ZINCIR_TAMAM` gösterdi.

Yan bulgu: `%Degisken%` düz metin olarak yazıldığında Storyline onu değişken
referansı olarak yorumluyor — araç metin kutusunda değişken gösterebiliyor.

**Komşu boşluk kapalı, ölçüldü:** `watch` var olmayan bir ad alırsa çağrı
reddediliyor ("Degisken bulunamadi ... Mevcut: [...]"). Alan her zaman
dosyadaki gerçek bir değişkenin GUID'ini alıyor, yani "alan dolu ama hiçbir
şeye işaret etmiyor" hâli üretilemiyor. Değişken sonradan silinirse GUID
kopar, ama o `dangling_triggers`'ın kesitine düşer — çözülemeyen GUID arıyor.

---

### AÇIK GEDİK: "EVENTS ölçüldü" ile "EVENTS çökmüyor" aynı şey değil

Zincir testi **17 event'ten yalnızca birinin** gerçekten ateşlediğini
kanıtladı. Diğer 16'sı için eldeki kanıt hâlâ *"Storyline çökmüyor"*
seviyesinde — *"preview'da tetikleniyor"* seviyesinde değil. Bu turda bu
farkın kendisi kanıtlandı: `OnVariableValueChange` panel testini sorunsuz
geçiyordu, trigger doğru görünüyordu, ve **hiçbir şey olmuyordu**.

Ve sebep bir **gizli companion alandı** (`other/@varChangeG`), tohumda yok,
şemadan tahmin edilerek bulundu. Aynı desen başka event'lerde de olabilir:

| event | ihtiyaç duyabileceği alan |
|---|---|
| `OnStateChange` | izlenen şekil + state |
| `OnDrop` | bırakma hedefi |
| `OnDialTurns` | dial referansı |
| `OnIntersect` | kesişilen nesne |
| `OnKeyPress` | tuş (`keyPress` düğümü tohumda **var**, boş) |

İnsan bunları UI'da nesneye tıklayarak kurduğu için alan örtük doluyor;
**programatik yazma yolunda dolmuyor** ve sonuç sessiz başarısızlık oluyor.

Backlog maddesi: kalan 16 event'in preview doğrulaması — her biri için bir
sentinel değer deseni (`%Degisken%` yazdır, olay tetiklenince değiştir).
J2'yi bloklamıyor.

---

### Kaçış sınırları — yüzey 1 ölçüldü, iki kusur çıktı

Üç yüzey ayrı ayrı soruluyor. **Yüzey 1 (yazma) bitti:**

| girdi | ElementTree |
|---|---|
| `0x09`, `0x0A`, `0x0D` | geçerli, korunuyor |
| `0x00`, `0x08`, `0x0B`, `0x0C`, `0x0E`, `0x1F` | **yazıyor, geri okuma `ParseError`** |
| 1 000 000 karakter | sessizce geçiyor — yazma tarafında uzunluk sınırı yok |

Yani ElementTree yasak karakteri kaçırmıyor, **geçersiz XML üretiyor**. Bu iki
kusuru açtı:

**Kusur A — bozuk paket sessizce diske yazılıyordu.** `verify()` sorunu
buluyordu (`ok: false`, `problems` dolu), `save()` raporu **döndürüyordu** ve
kimse bakmıyordu. Kontrol doğruydu; eksik olan verdiktin bir **kapıya
bağlanmasıydı**. Ölçüldü: JS koduna tek bir `0x00` konunca dosya okunamaz hale
geliyor, `save` hiçbir şey söylemiyor, ve geri dönüşü olmayan tek şey diskteki
dosya oluyor. Düzeltme: doğrulama artık `tmp` üzerinde koşuyor ve düşerse
`tmp` silinip hata veriliyor — hedef dosya hiç dokunulmamış kalıyor. Bu her
yazma yolunu korur, sadece JS'i değil.

**Kusur B — hata mesajı ne olduğunu söylemiyordu.** Paket doğrulaması
"not well-formed (invalid token): line 1, column 4260" diyor; kodda görünmez
bir karakter olduğunu söylemiyor. `add_trigger` artık JS metnini önden
denetliyor ve kaçıncı konumda hangi bayt olduğunu yazıyor.

Üç yönlü kanarya geçti: yasak karakter reddediliyor, tab/CR/LF kabul ediliyor,
sağlam paket hâlâ yazılıyor (kapı fazla kapatmıyor). `save` çekirdek olduğu
için suit koşuldu (K10) — düşen tek kapı `invariants`, ve üç bulgusu da
DEVIR'de **önceden kayıtlı** (havuz 40 harfte tabanın altında; `slidee.xml`
katman taşmaları, birebir aynı sayılarla).

**Yüzey 2 ve 3 — uzunluk, sentinel ile ölçüldü.** "Çöktü mü" ikili sorusu
kırpılmayı göremezdi: Storyline JS alanını bir tampon boyutunda kesiyorsa
dosya açılır, panel tetikleyiciyi gösterir, preview çökmez ve kodun kuyruğu
hiç koşmaz. O yüzden sentinel **kodun en sonuna** konuldu; çalışıyorsa kuyruk
sağlam demektir.

Tek dosyada beş nokta, her biri kendi sentinel değişkenini yazıyor:

```
K=OK   10K=OK   100K=OK   500K=OK   1M=OK
```

Yazma tarafı da temiz: 1 610 014 karakter JS, beşi de birebir geri okundu,
paket 0.13 MB (zip tekrarı eziyor).

> **NE ÖLÇÜLDÜ, ne ölçülmedi.** Bu tur **gerçek üst sınırı aramadı**. Dört
> noktada "bu boy güvenli mi" diye sordu ve dördü de geçti — yani aralık
> daralmadı, yalnızca **taban yükseldi**. Doğru cümle: *1M karaktere kadar
> kırpılma gözlenmedi.* "Uzunluk sınırı ölçüldü" değil; sınır 1M'in üstünde
> bir yerde ve nerede olduğu bilinmiyor. Pratik soru için bu yeterli, üst
> sınır sorusu için değil.

---

### Faz J2 — Kör noktayı kapat — **BİTTİ (2026-08-23)**

Ölçülen gerçek buydu: 40 kontrolün hiçbiri JS metnine bakmıyordu, ve yazma
yolu açıldığı anda kurs **suit yemyeşilken** bozulabilir hale geliyordu.

İki ölçü `audit`'e bağlandı, hesap tek yerde (K12):
`model.js_references` adları çözüyor, `jscheck.check` sözdizimine bakıyor.

**Gerekçe önce ölçüldü, varsayılmadı.** "Eşleşmeyen ad sessiz ölü koddur"
cümlesi bir varsayımdı; preview'da sınandı:

```
p.SetVar("HicYokBoyleBirDegisken", "X")   -> hata yok, kod DEVAM ETTI
p.GetVar("BaskaBirYokDegisken")           -> null dondu, kod DEVAM ETTI
```

Yani exception yok, durma yok — sadece hiçbir şey olmuyor, ve `null` JS'te
sessizce yayılıyor (`null + 1 == 1`). Bu, kontrolün **sertliğini** belirledi:
yazma anında hata değil, denetimde bulgu. Çağıran önce tetikleyiciyi sonra
değişkeni ekliyor olabilir ve bu meşru bir sıra.

**`js_sozdizimi`** Node'a bağlı ama koşunun geçerliliği ona bağlı değil
(K13). Node yoksa `js_syntax_errors` **`None`** dönüyor — `0` değil (K1b).
Kanaryası ayrıca koşuldu: `which` boşa çıkarıldığında `available=False`,
`results` boş, ve `audit` "KONTROL EDILEMEDI" diyor.

**Kapsam verdiktin yanında basılıyor (K5).** Regex yalnızca literal adları
çözüyor; `p.SetVar(ad, v)` gibi değişkenli çağrılar kalıbın dışında.
`dynamic_calls` onları sayıyor ve sıfır değilse kapsam cümlesi *"bu kesitte
çözülmeyen olup olmadığı BİLİNMİYOR"* diyor — "çözülmeyen yok" o durumda
"hepsi doğru" demek değil.

İki yönlü kanarya geçti: temiz dosyada üç ölçü de sessiz, bozuk dosyada üçü
de bağırıyor.

> **Ve kanarya kendi işini bu turda kanıtladı.** İlk koşuda üç ölçüden ikisi
> düştü: `js_references` hiçbir şey bulamıyordu. Sebep, regex'in `\b`'sinin
> kaynak dosyaya **gerçek backspace baytı** (0x08) olarak yazılmış olmasıydı
> — yani tam olarak bu turda JS için kapatılan sınıf, kontrolün kendi
> kodunda. Kanarya olmasaydı ölçü "0 çözülmeyen" diye raporlanıp geçecekti:
> çalışmayan bir kontrolün en sinsi hâli.

`dangling_in_slide` yeniden okundu (`tools/completeness.py:75`): çözülemeyen
**GUID** arıyor. JS trigger'ında GUID yok, dolayısıyla kopuk sayılmazlar —
yanlış alarm yok, ama görünmüyorlar da. `audit` artık onları ayrı sayıyor.

> Kural, bu fazdan sonrası için: **yeni bir JS yeteneği, yanında bir ölçü
> olmadan katalogda yer almaz.** JS, ölçüm kapsamının dışına kaçmanın en
> kolay yolu.

---

### Faz J3 — Panel yüzeyi — **BİTTİ (2026-08-23)**

Panel `_apply_op` kuyruğuna op basıyor; sözleşmesi "brief ver, kurs çıksın".
Üç seçenek:

**KARAR (2026-08-23): katalog birincil, ham JS ikincil.** `audit` geldikten
sonra "ham kod doğrulanamaz" gerekçesi zayıfladı ama kapanmadı — üç sebeple:

**1. `audit` sözcüksel, katalog anlamsal.** `audit` bir adın çözülüp
çözülmediğine, sözdiziminin geçerliliğine, çağrının okunabilirliğine bakar.
Katalog ise `SetVar`'ı **yapısal bir parametre** olarak alır: değişkenin var
olduğu, tipi, hedef slaydın gerçekliği yazma anında **kesin** bilinir. Ham
kodda bunlar regex'le çıkarsanır ve `dynamic_calls` sıfır değilken çıkarsama
açıkça *"bilinmiyor"a* düşer. Yani `audit` ham kodu **lint'liyor**,
doğrulamıyor — fark, ölçülmüş regex sınırının kendisi.

**2. Katalog kapalı küme, ham kod sonsuz girdi uzayı.** Bu yol haritasında
kapanan her şey — action adları, `EVENTS`, kaçış sınırları — sonlu olduğu
için tek tek kanaryalanabildi. Ham kod alanı bunu tersine çevirir ve bu
turların yöntemine (tahminden ölçüme) aykırıdır. Katalogda her yetenek bir
kez ölçülüp kilitlenir; ham kodda her çağrı yeni ve ölçülmemiş bir yüzeydir.

**3. Çağıran büyük olasılıkla bir insan değil.** Kursu programatik kuran bir
ajan için tipli bir çağrı kümesi, serbest kod üretmekten güvenilirdir. Bu
oturumun hatalarının çoğu — tahmin edilen alan adı, DLL adıyla XML değerini
karıştırmak, kalıp benzerliğine güvenmek — tam olarak "serbestçe üretilen ama
doğrulanmamış girdi" sınıfındandı.

Ham JS kapatılmıyor: kataloğun kapsamadığı durumlar için, **`audit` kapısından
geçen** ikincil bir gelişmiş yol olarak kalıyor. Ama birincil arayüzün
gerekçesini geçersiz kılacak kadar güçlü sayılmıyor.

Gerekçe K9 ile de tutarlı: panelin hedefi kurs üretmek, JS editörü olmak değil.

**UI yeri değişti — ve gerekçesi ölçümden geldi.** Plan "profil kartının
içinde bir Yetenekler bölmesi" idi: seçim brief'in parçası olsun, kurs sonrası
bir düzenleme olmasın. Kurarken tutmadı: her yetenek **bir slayt** ister
(`add_js_capability(slide=…)`) ve profil kartı kurs daha üretilmeden
doldurulur — o anda seçilebilecek bir slayt yoktur. Brief'e gömmek, slaydı
"sonra bir şekilde" seçmek demekti; bu da kurulan halkanın üçte birini
(kod · değişken · **olay/slayt**) belirsiz bırakırdı.

Yüzey bu yüzden ayrı bir **`JS` sekmesi**: dosya seçili, slayt listesi gerçek,
ve yetenek gerçek bir slayda bağlanıyor.

Panelde duran şey:

| bölme | ne yapar |
|---|---|
| **JS yetenekleri** (kart) | katalog motordan gelir; slayt + yetenek + parametre; `calismaz` ve `olcum` seçimin **yanında** gösterilir |
| **Gelişmiş: ham JavaScript** (katlanmış) | `js_precheck` geçmeden **Ekle** düğmesi açılmaz |

Üç ayrıntı, üçü de bu turun dersinden:

- **Kapı eklemeden ÖNCE bakar.** `audit` yalnızca dosyaya *yazılmış* kodu
  görür; ham kodu önce ekleyip sonra denetlemek kapıyı kapı olmaktan çıkarırdı.
  `model.js_kod_referanslari` bu yüzden eklendi ve `js_references` ile **aynı
  çekirdeği** (`_js_coz`) kullanıyor — iki uygulama olsaydı kapsam cümlesiyle
  sayılar ayrışırdı.
- **Kapı bayatlamaz.** Kod ya da olay değiştirilince **Ekle** kendini yeniden
  kapatır; "denetlendi" damgası denetlenen metne bağlı.
- **Olay listesi panelde elle yazılmaz.** İlk hâlinde üç olay elle
  sayılıyordu — kataloğun 17 olayının 14'ü panelde görünmüyordu. Aynı sınıf
  bu turda bir kez `logic.EVENTS`'i çökerten iki adla dolu bıraktı. Liste
  artık `trigger_events`'ten, tek kaynaktan geliyor. Liste alınamazsa
  **tek bir ada düşürülmez**: "OnStart var" ile "olay listesi bilinmiyor"
  ayrı şeyler, ve sessizce daraltılmış bir liste kullanıcıya kapsam yalanı
  söyler (K1).

---

### Faz J4 — Yetenek kataloğu — **BİTTİ (2026-08-23), ilk tur dört yetenek**

Her yetenek bir dosya ve beş alan taşır: **kod · gerektirdiği değişkenler ·
bağlandığı olay · ne zaman çalışmadığı** (LMS yok / `file://` / CSP) **·
dokunduğu kesit** (`veri` / `player` / `form` / `print` — `slayt` yasaklı,
bkz. 3b).

Dördüncü alan zorunlu. Bir JS yeteneği üç halkadan oluşur — **kod · değişken ·
olay** — ve üçü ayrı ayrı kırılır; A1'in JS'teki hâli. "Trigger var" =
"çalışıyor" değil.

#### İlk dört aday ölçülemedi — kapsam bu yüzden değişti

Planlanan sıra şuydu: LMS'ten öğrenci adı · sertifika/PDF · kaldığı yerden
devam · metin girişi doğrulama. Kurmaya başlarken **dördü de bu ortamda
ölçülemez** çıktı:

| aday | neden ölçülemedi |
|---|---|
| LMS öğrenci adı (`lmsAPI`) | LMS yok; Preview'da `lmsAPI` tanımsız |
| Sertifika / PDF | kütüphane gömme yolu hiç ölçülmedi |
| `localStorage` devam | ölçülebilir ama karşılığı ancak **iki oturum** arasında görünür; tek kare ile ölçülemez |
| Metin girişi doğrulama | **girdi alanı yok** — metin girişi soru tipinin klonlanabilir örneği yok (README, "Bilinen sınırlar") |

Kataloğun kendi kuralı ("ölçüsü olmayan yetenek katalogda yer almaz") burada
kendi planına karşı işledi, ve doğru olan buydu. Kural yazıldıktan sonra ilk
kez ısırdığı yer, onu yazan turun kendi listesi oldu.

İlk tur bu yüzden **Storyline'ın tek başına yapamadığı ve Preview'da tek
karede ölçülebilen** işle kuruldu — dördü de `veri` kesitinde, hiçbiri slayt
DOM'una dokunmuyor:

| yetenek | ne yapar | Preview'da ölçülen (2026-08-23) |
|---|---|---|
| `tarih` | sistem tarihini seçilen biçimde yazar | `gg.aa.yyyy ss:dd` → `23.08.2026 20:45` |
| `rastgele` | alt–üst arası tam sayı | `1–6` → `4` |
| `sayi_bicimi` | binlik nokta, ondalık virgül | `1234567.891`, 2 basamak → `1.234.567,90` |
| `metin_karsilastir` | Türkçe normalize edip karşılaştırır | `İSTANBUL` ~ `istanbul` → `DOGRU` |

#### Ölçüm sırasında çıkan bulgu: Storyline sayı değişkeni 8 anlamlı basamak taşıyor

`sayi_bicimi` beklenen `1.234.567,89` yerine `1.234.567,90` verdi. `toFixed(2)`
kendi başına `.89`'u `.90` yapmaz, yani JS'in gördüğü sayı dosyaya yazılan sayı
değildi. Yazma yolu temizdi (`story.xml` geri okundu: `val="1234567.891"`), yani
kayıp çalışma anındaydı. Çıkarım yapmak yerine ham değer yazdırıldı:

| yazılan | JS'in gördüğü |
|---|---|
| `1234567.891` | `1234567.9` |
| `0.123456789012` | `0.12345679` |
| `123456789012.5` | **`123456790000`** |

Üçü de tam **8 anlamlı basamakta** kesildi. Sınır ondalık basamak değil
**anlamlı basamak**: üçüncü örnekte **tamsayı kısmı bozuldu**. 8 basamağı aşan
bir tutar veya puan sessizce yanlış gösterilir; bu, kodun değil **girdisinin**
sınırı ve `sayi_bicimi`'nin `calismaz` alanında yazılı.

#### Katalog nerede durur — karar

`storyline_mcp/jscat.py`, `jscheck.py`'nin yanında. `seeds/` düşünülmüştü ama
oradaki her şey **klonlanabilir XML parçası**; katalog kaydı kod + parametre
sözleşmesi + ölçüm, klonlanacak XML değil. Paket ayrıca düz — `seeds/` dışında
alt paket yok.

#### Şablonlarda Türkçe harf yok

`metin_karsilastir`'ın regexleri `İ` gibi JS kaçışlarıyla yazılı, harfin
kendisiyle değil; `json.dumps` da `ensure_ascii=True` ile çağrılıyor, yani
üretilen `js` değeri baştan sona ASCII. Gerekçe ölçüm eksikliği: `js` bir XML
özniteliğine giriyor ve bu turda "görünmez/özel karakter sessizce bozuluyor"
sınıfından **iki** kusur çıktı (JS kodunda kontrol karakteri, `model.py`
kaynağında 0x08). ASCII dışı harflerin bu yolda sağlam kaldığı **ölçülmedi** —
ölçülmemiş bir ekseni kullanmak yerine hiç girilmiyor. Kural `import` anında
zorlanıyor.

#### Kapılar — altı bozuk girdide bağırıyor, temizde sessiz

`jscat._kendini_dogrula()` **import anında** koşar: `olcum` boş · `calismaz`
boş · `kesit=slayt` · şablonda ASCII dışı harf · parametresi olmayan yer
tutucu · kullanılmayan parametre. Altısı da ayrı ayrı kanaryalandı.

Çalışma anındaki yedi kapı da ölçüldü: bilinmeyen yetenek · bilinmeyen
parametre · geçersiz değişken adı · seçim dışı değer · sayı yerine metin ·
okunan değişken yok · çökerten olay.

**Enjeksiyon kapalı.** Her yer tutucu `json.dumps` ile tam bir JS değişmezine
çevriliyor, yani şablonda tırnak yok; tırnağı dönüşüm koyuyor. Tırnak, ters
bölü ve yeni satır içeren bir parametreyle sınandı: kod hâlâ parse ediyor,
enjekte edilen `SetVar("HACK",1)` veri olarak kalıyor.

**Üç yol da bağlı:** `jscat.uygula` · `build_course` op kuyruğu
(`add_js_capability`) · `add_js_capability` MCP aracı. Üçüncüsü bu turda bir
kez unutulmuştu (`add_trigger`/`add_variable` op dalları hiç yoktu), o yüzden
üçü ayrı ayrı koşturuldu.

**Slayt içeriğini** DOM'dan ya da CSS'ten hedefleyen yetenek katalog dışı:
publish HTML yapısına bağımlı, Articulate onu sürümler arası değiştiriyor —
ve XML zaten o işi yapıyor (3b). `player` / `form` / `print` kesitindeki CSS
3b'nin izin listesine tabidir; ilk dört adayın hiçbiri o kesite girmiyor.

---

### Sayı sınırı — J4'ün borcu, kapatıldı (2026-08-23)

`sayi_bicimi` ölçülürken çıkan 8 basamak bulgusu J4'ün başarısı değil **açık
bir borçtu**: proje baştan beri "yanlış çalışan bir şey üretmektense reddet"
ilkesiyle çalışıyor (`watch` eksikse reddet, kontrol karakteri reddet,
doğrulamayı geçemeyen paketi yazma) ve büyük bir sayı bu ilkenin dışında
kalmıştı — hata vermiyor, yanlış tutarı gösteriyordu.

#### Önce kapının YERİ ölçüldü

İlk ölçüm "JS'in gördüğü değer 8 basamak" diyordu. Bu kapının nereye
konacağını söylemez: sınır JS köprüsündeyse kapı JS yolunda, Storyline'ın
sayısındaysa `add_variable`'da olmalı. Aynı karede `%A%` (doğrudan gösterim)
ile `%Ajs%` (JS okuması) karşılaştırıldı — **ikisi de aynı**. Yani JS masum,
sınır motorun kendisinde ve **JS'siz bir kurs da aynı ölçüde etkileniyor**.

#### Sonra kayıp yerinin GÖSTERİM mi SAKLAMA mı olduğu

Değer içeride tam durup yalnızca okunurken kırpılıyor olabilirdi; o zaman
"reddet" aşırı olurdu. Gösterime bağımlı olmayan bir deneyle ayrıldı: büyük
sayıdan büyük bir sayı çıkarılıp sonuç küçük aralığa düşürüldü.
`A = 1234567.891`, `A + (−1234567)` → **`0.9`**, `0.891` değil. **Kayıp
saklamada.**

#### Sonra kuralın kendisi — ve iki yanlış model

"8 anlamlı basamak" önce üç noktadan genellendi, sonra kendi verisi onu
çürüttü. Doğru model **üçüncü** denemede çıktı ve bunu yazmak önemli: ilk iki
model *tutarlı görünüyordu* ve yine de yanlıştı.

| model | neyi açıklıyordu | neyi açıklamıyordu |
|---|---|---|
| float32 | — | `16777217`, `33554433`, `99999999` varsayılan olarak **tam** geldi |
| "her yerde 8 basamak" | varsayılanlar | kelepçe okuması `2147484000`; `12345678+87654321 = 100000000` |
| **üç ayrı kesit** | **hepsi** | — |

Ölçülen model:

| kesit | sınır | ölçülen |
|---|---|---|
| değişken varsayılanı (`val=`) | **8 anlamlı basamak** | `123456789012.5` → `123456790000` |
| `adjust_variable` sonucu | **7 anlamlı basamak** | `0 + 12345678` → `12345680` |
| `adjust_variable` literali | **2³¹ int32 doygunluğu** | `3e9` ve `1.23e11` → ikisi de `2147484000` |
| **JS `SetVar`** | **tam** (≥9 basamak ölçüldü) | `199999998`, `16777217`, `33554433` → kayıpsız |

`2147484000` = `2147483647`'nin 7 anlamlı basamağı — önceki modeli çürüten
okuma, yeni modelde tam yerine oturuyor.

> **Kullanım kuralı, tek cümle: hassasiyet önemliyse aritmetiği JS `SetVar`
> üzerinden ifade et, `adjust_variable` literaliyle değil.**

**Çerçeve tersine döndü: JS köprüsü en HASSAS yol.** İlk okumada en riskli
sanılıyordu. `adjust_variable` ondan iki basamak daha kaba.

#### En sert sonuç: sayaç 10 milyonda susuyor

    0 + 1000000  + 1  ->  1000001     ✔
    0 + 10000000 + 1  ->  10000000    ← +1 HİÇ İŞLEMEDİ

Literal `1`. Değişken varsayılanı `0`. İkisi de her eşiğin çok altında. Bozan
şey **birikmiş sonuç**, ve o çalışma anında oluşuyor — yani statik bir kapının
göremeyeceği yerde. Bu, "biriken SKOR" senaryosunun kendisi.

#### Bu storyline_mcp'nin kusuru DEĞİL

Her iki durumda da yazma yolu temiz: `story.xml`'de `val="1234567.891"`,
tetikleyicide `dblVal="-123456780000"` **aynen** geri okundu. Bozan
Storyline'ın kendi motoru. Bu ayrım açıkça yazılıyor ki ileride biri
*"storyline_mcp sayıları bozuyor"* diye yanlış teşhis koymasın.

#### Kapı

| yer | ne yapar |
|---|---|
| `logic.sayi_sorunu` | **tek** hesap yeri; **iki ayrı eşik**, `literal` bayrağıyla ayrılıyor |
| `add_variable` | `num` varsayılanı **8** basamağı aşarsa **reddeder** |
| `add_trigger` | `adjust_variable` literali **7** basamağı ya da 2³¹'i aşarsa **reddeder** |
| `audit` | aracın **üretmediği** dosyalarda mevcut bozuk değerleri sayar |

Eşiklerin ayrı olması ölçümün sonucu, tercih değil: `99999999` varsayılan
olarak **tam geliyor** ama literal olarak `100000000`'e dönüşüyor. Tek eşik
kullanılsaydı ya geçerli varsayılanlar boşuna reddedilirdi ya da bozuk
literaller geçerdi. Kanarya bu ayrımı ayrıca sınıyor.

Hata mesajları ne yapılacağını da söylüyor: ölçeği küçült, `text` değişkende
tut, **ya da JS ile yaz** — çıkış yolu ölçüldü, JS `SetVar` tam değeri taşıyor.

**Kapının kapsamadığı şey, açıkça:** `adjust_variable` sınırını **sonuca**
uyguluyor ve sonuç çalışma anında birikiyor. İki küçük literal üst üste
toplanıp 7 basamağı aşarsa kapı bunu göremez — `0 + 10000000 + 1` örneğinde
literal `1`, varsayılan `0`, ikisi de temiz. Bu kör nokta **kapatılmadı**;
ölçüldü, yazıldı, ve `audit`'in `lossy_number_scope` cümlesi onu söylüyor.
Sıfır bulgu "hiçbir sayı bozulmuyor" demek değil.

#### Aynı düzenlemede iki kez "girdisi olmayan kontrol"

Denetim tarafı ilk yazıldığında **hiç koşmuyordu** ve yine de "0 bulgu"
diyordu — iki ayrı sebeple: `model.triggers` `adjustVar`'ın değerini hiç
açmıyordu, ve değişken tarafında anahtar adı yanlıştı (`dataType`/`val`
yerine `data_type`/`default`). İkisi de temiz bir dosyadan ayırt edilemezdi.
İki yönlü kanarya ikisini de yakaladı; `model.triggers` artık `operation` ve
`value` veriyor (`useVar="true"` ise `value_from_variable`, çünkü o değer
literal değil).

---

### Sayaç ve taşma — tek düzenekte, ikisi birden (2026-08-23)

İki backlog maddesi ayrı turlarda ele alınacaktı; aynı düzeneği paylaştıkları
görülünce tek oturumda ölçüldü: bir slaytta tekrar tekrar artan bir değişken,
`OnVariableValueChange` ile izleniyor. Üç sütun, aynı artış (5× +1), üç yol:

| sütun | başlangıç | yol | sonuç | izleyici saydı |
|---|---|---|---|---|
| SayacT | 10 000 000 | `adjust_variable` | **10000000** | **0** |
| SayacJ | 10 000 000 | JS `SetVar` | **10000005** | 5 |
| Kontrol | 100 | `adjust_variable` | 105 | 5 |

Kontrol sütunu vazgeçilmezdi: SayacT'nin izleyicisi hiç saymadıysa bu ya
"değer değişmedi" ya da "izleyici bozuk" demektir. Kontrol'ün 105 gösterip
izleyicisinin 5 sayması ikinci ihtimali eledi.

**İki sonuç birden:**

1. **JS sayaç tekrarlanan artışta tam** — ve slayt geçişinden sonra da
   korunuyor (ikinci kare, `%SayacJ%` = 10000005). Yeteneğin eksik iki ölçümü
   buydu.
2. **Taşma sessiz ama görünmez değil.** Değer değişmeyi bırakınca
   `OnVariableValueChange` de susuyor. Yani "artırma tetiklendi ama izleyici
   saymadı" çalışma anında yakalanabilir bir imza — henüz bir yeteneğe
   dönüşmedi ama artık varsayım değil, ölçüm.

#### Katalogda: `sayac`

Katalog beşinci yeteneğini aldı. Kendi kuralı gereği **kataloğun ürettiği
kodla** ayrıca ölçüldü — "eşdeğeri ölçüldü" yeterli sayılmadı (K8):
`Ziyaret` 10000000'den 5 katalog çağrısıyla **10000005**, sıfırdan kurulan
`Kanarya` **5**.

`calismaz` alanı üç sınırı da taşıyor: her tetiklemede bir artış (OnStart'ta
"her slayt ziyareti"), aynı değişkene `adjust_variable` ile yazılırsa kazanç
**orada** kaybolur, ve ölçülen üst sınır 9 anlamlı basamak — ötesi ölçülmedi.

#### Taşma uyarısı — tasarım sorusu ölçümle kapandı

İki tasarım vardı: **eşik kontrolü** mü, **artırma/izleyici sayacı
karşılaştırması** mı. Bu turun verisi birincisini seçtirdi.

`OnVariableValueChange` ancak değer **gerçekten değiştiğinde** tetikleniyor
(SayacT sütununda `degisim=0` bunu gösterdi). Yani taşma anında olay
**susuyor** — bir uyarı yeteneği o anda koşamaz. Ama tam bu yüzden ek bir
defter tutmaya da gerek yok: uyarı, değerin eşiğe **girdiği son başarılı
değişimde** yazılır (`9999999 → 10000000`), ve o noktadan sonrası zaten
kayıplıdır. Sayaç karşılaştırması beklenen artış sayısını bilmeyi
gerektirirdi; iki sayaç ve kırılgan bir varsayım demekti.

Eşik `logic.SAYI_ARITMETIK_BASAMAK`'tan türetiliyor — 7 sayısı ikinci bir
yerde yazılmıyor.

Ölçüm (Preview, 2026-08-24), kataloğun ürettiği kodla (K27):

| sütun | başlangıç | 10× +1 sonrası | uyarı |
|---|---|---|---|
| Buyuk | 9 999 995 | **10000000** (kilitli) | **RISK** |
| Kucuk | 100 | 110 | **OK** |

Kanarya sütunu eşiğin gerçekten okunduğunu gösteriyor: mekanizma her
değişimde RISK yazsaydı `Kucuk` de RISK olurdu.

#### Ve tasarımın kendi varsayımı sınandı — varsayım yokmuş

"Son başarılı geçişte ateşle" tasarımı, eşiğe **adım adım** yaklaşıldığını
örtük olarak varsayıyor görünüyordu. Gerçek kullanımda değer tek hamlede
eşiğin çok ötesine sıçrayabilir. Üç ayrı sonuç mümkündü ve üçü farklı anlama
gelirdi; uyarı değişkeninin varsayılanı zaten `-` olduğu için **"hiç
koşmadı"** ile **"koştu ve OK dedi"** ayrı görünüyor — kanarya kurmadan gelen
üç durumlu sentinel.

| sütun | yol | değer | uyarı |
|---|---|---|---|
| J1 | `adjust_variable` +10 000 000 | 15000000 | **RISK** |
| J2 | JS `SetVar(15000000)` | 15000000 | **RISK** |
| J3 | JS `SetVar(15000001)` (8 basamak) | **15000001** tam | **RISK** |
| K | +500 | 600 | **OK** |

Hiçbiri `-` kalmadı. J3 üçüncü ihtimali de çürüttü: tek hamlede hem eşiği
aştı hem hassasiyet sınırının ötesine düştü, JS tam taşıdığı için temiz bir
"eşiğe giren değer" oluştu ve uyarı düştü.

**Yani varsayım yokmuş.** Olay her *gerçek değişimde* ateşliyor ve yetenek
değişim **sonrası** değeri okuyor; değerin oraya nasıl geldiği önemsiz. Belge
bu yüzden **düzeltildi**: `calismaz` var olmayan bir sınır iddia ediyordu, ve
yanlış tarafa yanlış olmak da bir hatadır.

`calismaz`'ın taşıdığı **gerçek** sınır başka: değer **hiç değişmezse** olay
hiç tetiklenmez ve uyarı `-` kalır. Yani varsayılanı zaten eşiğin üstünde
olup hiç değiştirilmeyen bir değişken uyarılmaz — onu `audit` yakalar
(`lossy_numbers`). Bir de eşik, tam sayı +1 sayaçları için kesin;
ondalıklı veya büyük adımlı artışlarda erken/geç olabilir.

Bu, `OnVariableValueChange` kullanan **ilk** katalog yeteneği. `Yetenek`
kaydına bir `izle` alanı eklendi ve yapısal kontrol ikisini birbirine bağladı:
bu olay ile `izle` **birlikte** olmak zorunda — `watch` olmadan olay hiç
tetiklenmiyor (bu turda ölçülmüştü) ve tetikleyici panelde doğru görünmesine
rağmen sessiz kalıyor.

#### Üçüncü kez anahtar adı — bu kez aynı gün yazılan kodda

`jscat.uygula` `dataType` okuyordu, `model.variables` `data_type` veriyor.
Sonuç: **var olan bir değişkeni yeniden kullanan her çağrı** "tipi None" diye
reddediliyordu. Testlerimin hepsi taze ad kullandığı için bu yola hiç
girilmemişti — kapı yanlış tarafa kapalıydı ve hiçbir kanarya oradan geçmiyordu.

K26'nın ek maddesinin tarif ettiği durumun kendisi. Üç yol da (doğru tip /
yanlış tip / hiç yok) artık ayrı ayrı kanaryalı.

**Ve bu bir köşe durumu değil.** Aynı değişkeni birden çok yetenek için
yeniden kullanmak — bir yazarın `SKOR`'u hem `sayac` hem `sayi_bicimi` ile
kullanması — kataloğun gerçek kullanımdaki en olası örüntülerinden biri.
Testlerin hepsinin taze ad kullanması o yolu hiç yormamıştı: *"testlerim
geçti"* ile *"gerçek kullanım yolları test edildi"* arasındaki farkın somut
hâli.

---

### Kalan maddeler kapatıldı (2026-08-26)

#### Üçüncü kaynak: motorun kendi UI kaynak anahtarları

`EVENTS` iki kez türetilmişti — elle (iki çökerten ad taşıdı) ve bağışçılardan
(yalnızca **kullanılan** olayları gösterir). Üçüncüsü `Articulate.Design.dll`:
tetikleyici açılır menüsündeki her olayın bir `<Ad>ComboName` /
`<Ad>DisplayName` kaynak anahtarı var.

Ham dizgi taraması bu işi yapamıyordu ve `event_probe`'un docstring'i bunu
zaten yazmıştı: *"DLL'de geçmek kanıt değil"* — `OnPrevButtonClick` DLL'de
duruyor ve çökertiyor. Kaynak-anahtarı filtresi tam bu farkı yakalıyor ve
**iki yönlü kalibre edildi**:

| yön | sonuç |
|---|---|
| pozitif | 17 bilinen geçerli adın **17'sinin** de kaynak anahtarı var |
| negatif | 9 bilinen çökertenin **9'unun** da yok — dördü ham dizgide **var** |

**Gerekli ama yeterli değil:** 66 ham aday → 10 kaynak anahtarlı aday, ve
bunların **4'ü yine çökertti**. Kaynak anahtarı "UI'da görünür" demek, "XML
değeri kabul edilir" demek değil. `event_probe` ayrıca koştu.

| kabul edildi (6) | çökertiyor (4) |
|---|---|
| `OnClicksOutSide`, `OnEntersSlide`, `OnHover`, `OnLeavesSlide`, `OnSliderMoves`, `OnStopIntersect` | `OnClickFailure`, `OnGesture`, `OnNextGesture`, `OnPreviousGesture` |

`EVENTS` 17 → **23**, `COKERTEN_EVENTS` 9 → **13**.

#### "Önceki buton" sorusu kapandı — ve cevap "yok"

`OnNextButtonClick`'in kaynak anahtarı var, `OnPreviousButtonClick`'inki
**yok**. Tek aday `OnPreviousGesture` idi ve o da **çökertiyor**. Yani
simetrik bir "önceki buton" olayı bulunmuyor. Bu artık *"bulunamadı"* değil,
**ölçüldü**.

#### Ölçüm aracının kendi kusurları

İlk `event_probe` koşusu kanaryayı düşürdü — bilinen geçerli `OnClick`
"AÇILMADI" dedi — ve araç doğru davranıp **verdikt basmadı**. Sebep:
`os.startfile`, yani **shell yolu**. `js_probe._ac`'nin docstring'i bunu
ölçüp yazmıştı: Articulate 360 Desktop App çalışırken shell yolu dosyayı ona
veriyor ve hiçbir pencere açılmıyor. *Ders bir dosyada öğrenilmiş, komşusuna
taşınmamıştı* — bu turda üçüncü kez aynı sınıf. Düzeltildi (exe ile açılış +
tekrar).

`shoot_preview` de iki yerden düzeltildi, ikisini de bu turda ben yedim:

- **F12 tek denemede pes ediyordu.** Aralıklı bir yarış (ön plan), üç turda
  kalıcı bir blok gibi göründü ve yanlış bir teşhise yol açtı. Artık 5 deneme.
- **`--imza` verilmeyince dördüncü guard sessizce silahsız kalıyordu.** Bu
  yüzden boş bir oynatıcı karesi "ölçüm" diye kaydedildi. Guard isteğe bağlı
  kaldı ama artık **uyarıyor**.

#### Kataloğun "ayrı ölçülmedi" dediği yollar ölçüldü

| yol | sonuç |
|---|---|
| `tarih` dört biçim | `yyyy-aa-gg` → 2026-08-26 · `gg.aa.yyyy` → 26.08.2026 · `ss:dd` → 20:40 · dördüncüsü önceden |
| `metin_karsilastir` şapkalı harf | **iki yönlü**: doğru çiftte DOGRU, yanlış çiftte YANLIS |
| `rastgele` uç değerler | alt=1 ust=3, altı çekiliş: `3 2 2 1 1 3` — iki uç da çıktı, taşma yok |

Dağılımın düzgünlüğü ve boşluk kırpma yolu hâlâ ölçülmedi; `olcum` alanları
bunu söylüyor.

#### `add_text_box`'ta `h` — endişe yanlış ifade edilmiş

Ölçüldü: h=30/14/8/5, hepsinde sonundaki `[SON]` işareti **görünüyor**.
Sessiz kırpma **yok** — metin kutuyu aşıyor ve yine de çiziliyor. Risk kayıp
metin değil, **komşusuna binmek**. Ve `invariants` bunu zaten tam bu sözlerle
ölçüyor: *"metin kutusunu aşıyor (kırpılmaz, komşusuna biner)"*.

Yani madde bir ölçüm boşluğu değil, **yanlış ifade edilmiş bir endişeydi** —
K29'un aynısı, bu kez backlog'da.

---

### Koşullu event ailesi — yoldaş alanlar bağışçı XML'inde bulundu (2026-08-24)

`varChangeG` Preview'da öğrenilmişti. Aynı sınıf, **etkileşim gerektirmeden**
bağışçıların kendi XML'iyle karşılaştırarak da bulunabilirmiş — ve bulundu.

**İlk deneme yanlış "temiz" dedi.** Yalnızca `data` ve `data/other`
özniteliklerine baktı, "fark yok" çıktı. Yöntem iki yerden kördü ve ikisi de
ölçüldü:

1. Bağışçılarda `OnVariableValueChange` **hiç yok** → yöntem `varChangeG`'yi
   zaten yakalayamazdı. Kapsam, bağışçıların kullandığı event'lerle sınırlı.
2. `trig`'in ve `data`'nın **alt elemanlarına** hiç bakılmadı — yoldaş alanlar
   tam orada: `data/shape/@stateName`, `.../dropLst`, `data/keyPress/@keys`.

`OnStart` kanarya olarak listede tutuldu ve o da "farklı" çıktı (`cuePoint`);
çalıştığı bilinen bir event'in farklı çıkması eşiği kalibre etti.

#### Eylem tarafı mı, olay tarafı mı — çapraz tabloyla ayrıldı

Bağışçıların eylemi bizimkinden farklı olduğu için listenin çoğu gürültüydü.
Ayırıcı: alan **action**'ı mı yoksa **event**'i mi takip ediyor?

| alan | karar | kanıt |
|---|---|---|
| `shape/dropLst` | **OLAY tarafı** | `OnDrop` 23/23; iki ayrı action'a yayılıyor (`adjustVar` 15, `changeShapeState` 8) |
| `shape/@setStateName` | eylem tarafı | `changeShapeState` 123/123, beş ayrı event'e yayılmış |
| `shape/@stateName` | **ayrılamadı** | `OnStateChange` 5/5, ama beşi de aynı action |
| `intersectLst`, `keyPress/@keys`, `shape/@g` | kapsam sıfır | bağışçılarda hiç dolu değil |

#### İkinci bulgu: bu tetikleyiciler slaytta değil, nesnede yaşıyor

    OnDialTurns    77/77   trigLst < importedVector < shapeLst
    OnDrop         23/23   trigLst < rect < shapeLst
    OnStateChange   5/5    trigLst < btn  < shapeLst

`add_trigger` ise `shape` verilmezse slayda bağlıyordu. Storyline'ın kendi
dosyalarında slayda bağlanmış tek bir örneği yok.

#### Kapı

`logic.HEDEFLI_EVENTS` eklendi. Üçü için `shape` zorunlu; `OnDrop` için
`drop_targets`, `OnStateChange` için `state_name`. Üretilen XML bağışçınınkiyle
birebir aynı biçimde: `<dropLst><g>GUID</g></dropLst>`.

**Reddin gerekçesi "çalışmıyor" değil.** Bu olayların çalışma anındaki
davranışı ölçülmedi — sürükleme ve durum değişimi Preview'da
otomatikleştirilmedi. Gerekçe başka: *Storyline'ın kendisinin hiç üretmediği
bir biçimi üretmiyoruz.* Bunu bir kez yaptık; `varChangeG` boştu, panel doğru
görünüyordu, hiç tetiklenmedi.

`state_name` şartı ayrıca **ihtiyat gerekçesiyle** konuldu ve kod bunu açıkça
söylüyor: alanın olaya mı eyleme mi ait olduğu ayrılamadı. Sessiz başarısızlık
ile gürültülü ret arasında ikincisi seçildi (K29'un tersi değil: burada
"çalışmaz" iddiası yok, "üretmiyoruz" var).

---

### Panel yüzeyi geri alındı: seçen kullanıcı değil, ajan (2026-08-26)

Kullanıcı geri bildirimi: *"bu js kısmı kullanıcının kafasını karıştırır…
brief veya komut verince otomatik olarak o kursta js yetenekleri
kullanılamıyor mu?"*

Haklı, ve J3 kararını kısmen geçersiz kılıyor. J3'te "katalog birincil arayüz"
denmişti ve o doğruydu — ama **arayüzün kime gösterileceği** ayrı bir soru.
Katalog, kurs yazan insanın seçeceği bir menü değil; ajanın kullanacağı bir
araç kutusu. Bir sekme dolusu JS yeteneği, aracın varlık sebebiyle çelişiyor.

**Sekme kaldırılmadan önce ölçüldü: diğer yol açık mıydı?** Değildi.

| yol | durum (ölçüm) |
|---|---|
| Panel JS sekmesi | çalışıyordu |
| Ajan (Komut sekmesi) | **kapalı** — izin listesinde `add_js_capability` / `list_js_capabilities` yoktu |
| Brief → `build_course` | kapalı — boru hattı slayt üretir, op yazmaz |

Sekme öylece kaldırılsaydı özellik **hiçbir yerden** erişilemez olacaktı.
K8'in bir başka örneği: MCP aracı vardı, tek gerçek çağıran ona ulaşamıyordu.
`--strict-mcp-config` altında izin listesinde olmayan araç yok hükmünde.

**Yapılanlar:**

1. `list_js_capabilities`, `add_js_capability`, `check_javascript` ajanın izin
   listesine eklendi. Ayrıca listedeki 43 aracın 43'ünün de MCP'de karşılığı
   olduğu doğrulandı — listenin kendisi elle yazılıyor, yani sessizce
   ayrışabilir.
2. Sistem promptuna dört kural: önce kataloğa bak · **kendiliğinden JS
   serpme** (yalnızca istenen iş gerektiriyorsa) · ham JS son çare ve
   `check_javascript`'ten geçsin · biriken sayaç için `adjust_variable` değil
   `sayac`.
3. Panelin `js_precheck`'i **MCP aracına taşındı** (`check_javascript`).
   Değer panelde kalsaydı sekmeyle birlikte ölürdü; çağıranın olduğu yere
   gitti.
4. JS sekmesi, üç panel API metodu ve ölü importlar kaldırıldı.

**Brief yolu hâlâ JS üretmiyor** ve bu bilinçli: `_run_builder` ajana
devretmiyor, ve her kursa kendiliğinden sayaç/rastgele eklemek tam da ajana
yasakladığım şey olurdu. Brief'ten sonra "kapanışa tamamlama tarihi ekle"
komutu artık çalışıyor.

#### Dördüncü kez: not düşmek düzeltmek değil

`storyline_ctl.reopen` shell yolunu (`cmd /c start`) kullanıyordu. Bu tuzak
`open_test.storyline_exe`'de ölçülüp yazılmış, `js_probe._ac` ise onu tekrar
edip **"`storyline_ctl.reopen` HÂLÂ shell yolunu kullanıyor; panel de aynı
tuzağa açık"** diye not düşmüştü. Not duruyordu, kusur da duruyordu — kayıt
bir eylemi engellemiyordu. Panel her komuttan sonra `reopen` çağırdığı için
bu doğrudan kullanıcıya değen bir kusurdu.

Düzeltildi; `reopen` exe yolunu `open_test.storyline_exe()`'den alıyor, ikinci
bir kopya tutmuyor. Exe bulunamazsa shell yoluna düşüyor — hiç denememekten
iyi, ama o durumda tuzak yeniden açılıyor ve docstring bunu söylüyor.

---

### Dördüncü ölçüm yüzeyi: derleme çıktısı (2026-08-24)

Bu turların tamamı üç yüzeyle çalıştı: **dosya** (ne yazdık), **tetikleyici
paneli** (Storyline nasıl okuyor), **Preview** (çalışıyor mu). Ve altlarında
sessiz bir varsayım vardı: *Preview ayrı bir renderer*. O varsayım yanlış.

Preview, tam bir HTML5 derlemesi üretiyor:

    %LOCALAPPDATA%\Temp\Articulate\Storyline\<id>\Preview        html5/  mobile/  story_content/  preview.html

`story_content/` — yani yayınlanmış bir paketin taşıdığı klasörün ta kendisi,
içinde `triggers.js` ve **`user.js`**.

#### Zincir uçtan uca ölçüldü

| adım | nasıl doğrulandı |
|---|---|
| katalog kodu → `.story` XML | bayt bayt geri okundu |
| `.story` → derleme `user.js` | dört yeteneğin kodu **bayt bayt** derlemede bulundu |
| Preview derlemesi ≡ gerçek SCORM publish | sarmal önek **bayt bayt aynı** (15 `player.*` yardımcısı, aynı `InitUserScripts`) |

Son satır bu makinede duran **gerçek bir publish çıktısıyla** karşılaştırıldı
(kullanıcının kendi kursu, `imsmanifest.xml` + `lms/` + `story_content/`
taşıyan bir SCORM paketi). Yani "aynı derleme hattı olmalı" çıkarımı ölçüme
çevrildi.

#### İki yan bulgu

**Her JS tetikleyici kendi fonksiyon kapsamına giriyor.** Derleme her birini
`window.ScriptN = function() { … }` olarak sarıyor. Yani iki yeteneğin
`var p`'si çakışmıyor — bu bir izolasyon garantisi ve artık varsayım değil.

**`jscheck`'in `new Function(kod)` seçimi doğruymuş.** O seçim "geçici dosya
gerektirmiyor" diye yapılmıştı ve docstring'i "Storyline de kodu bir gövde
içinde koştuğu için bu, üretim koşullarına yakınlaşma" diyordu — *tahmin
olarak*. Derleme çıktısı bunu gösteriyor: kod gerçekten bir fonksiyon
gövdesi. Doğru gerekçe, sonradan ölçülmüş.

#### Geriye ne kaldı

Artefakt zinciri kapandı. Kalan boşluk **yalnızca LMS oturumuna özgü**:
`lmsAPI` üzerinden öğrenci verisi, `suspend_data`'nın oturumlar arası
kalıcılığı, SCORM sürüm farkları. Bunlar LMS olmadan ölçülemez ve
ölçülemediği yazılı kalıyor — ama artık "her şey yalnızca Preview'da
ölçüldü" cümlesi doğru değil.

#### Kural adayı, henüz kural değil

*Ölçmek için düzenek kurmadan önce, ölçümün zaten var olup olmadığına bak.*
Publish diyaloğunu otomatikleştirmeye hazırlanırken iki hazır gözlem çıktı:
Preview'ın kendi derleme klasörü, ve makinedeki gerçek publish çıktısı. İkisi
de aranan cevabı taşıyordu. **İki örnek** var; bu DEVIR'de bir kalıp üçüncü
örnekte kural oluyor, o yüzden şimdilik burada duruyor.

---

### Ölçüm yüzeyinin kendi kusuru — kare "alındı" ile "ölçüleni içeriyor" ayrı

Katalog ölçümünün ilk karesi **boş oynatıcıydı**: başlık `(Preview)`, odak
doğru, pencere önde — ve slayt alanı simsiyah. Dosya yine de yazıldı ve
"ölçüm" diye bakılacaktı.

Sebep aracın kendisinde değil, **kullanımındaydı**. `shoot_preview` bunun için
dördüncü bir guard taşıyor: fikstürün imza rengi karede aranır, yoksa dosya
yazılmaz. Ama guard `--imza` verilmezse **hiç kurulmaz**, ve ben vermemiştim.
Yani mevcut kural, onu kuran turun kendisi tarafından atlandı; fikstüre
`C8F0D2` zemin konup guard silahlandırılınca kare doğru geldi.

Kayda değer olan, guard'ın yokluğu değil **isteğe bağlılığı**: kapı ancak
çağıran onu kurmayı hatırlarsa kapıdır. Aynı desen bu turda üçüncü kez çıkıyor
(`verify` raporu okunmuyordu, `_apply_op` dalı yoktu, şimdi imza verilmiyor).

İkinci bulgu, aynı araçta: `shoot_preview.main` F12'yi **tek denemede**
gönderir ve alamazsa turu bitirir. Üst üste iki tur "foreground lock" ile
düştü; ölçüm o sırada `GetForegroundWindow`'un görünmez bir
`GameInputServiceWindow` döndürdüğünü ve `SPI_GETFOREGROUNDLOCKTIMEOUT`'un
`2147483647` olduğunu gösterdi. Buradan "odak kalıcı olarak kapalı" hipotezi
kuruldu — **ve ölçüm onu çürüttü**: aynı `ctl.focus`, hemen ardından odağı
aldı. Yani blok kalıcı değil, **yarış**; `force_close` sonrası Storyline
yerleşirken F12 erken gidiyor. Hipotez ölçümle düşürüldüğü için `focus`
yoluna dokunulmadı.

Backlog: `shoot_preview`'da F12 için tekrar; ve `--imza`sız çağrıyı
"guard kurulmadı" diye **söyleyen** bir uyarı — sessizce zayıf koşmak yerine.

---

## 3b. CSS ve komşu eksenler — hangisi buraya girer

### CSS ayrı bir kanal değil

Storyline'da CSS tetikleyicisi yok. CSS'in **tek kalıcı yolu** bir JS
trigger'ından `<style>` enjekte etmek: `.story` içinde yaşar, publish'te
taşınır. Publish çıktısındaki `story.html`'e elle eklenen her şey bir sonraki
publish'te kaybolur — araç `.story` yazıyor, publish çıktısı yazmıyor.

Yani **J1 bittiğinde CSS teknik olarak zaten açılmış olur.** Ayrı faz
gerekmiyor. Soru "nasıl yaparız" değil, "hangisine izin veririz".

### İki kullanım, iki farklı cevap

**Slayt içeriğine dokunan CSS — REDDEDİLİR.**

Araç renk, punto, geometri, tema, player rengini zaten XML'den yazıyor
(`compose`, `themes.json`, `set_theme_colors`, `restyle_text`,
`settings.set_player_color`). Aynı şeyi bir de CSS'ten vermek K12'nin görsel
hâli: iki uygulama er ya da geç ayrışır ve ayrıştığında hangisinin doğru
olduğu okunamaz.

Ağır olan yarısı bu değil. **CSS ölçüm zincirinin tamamen dışında** — ölçüldü:

| kontrol | neye bakıyor | CSS'i görür mü |
|---|---|---|
| `preview.py` | slaydın **kendi geometrisi**, SVG'ye çizilir — Storyline'ın renderer'ı değil | hayır |
| `contrast.py` | yazı ve zemin renkleri, XML'den | hayır |
| `silhouette` · `deadband` · `invariants` | XML konum/boyut | hayır |

CSS ile verilen bir renk kontrast kontrolünden **geçmez** — görünmez.
Panelin gördüğü ile öğrencinin gördüğü ayrışır ve suit yemyeşil kalır. K1.

**XML'in ulaşamadığı yere dokunan CSS — meşru kesit.**

Bu kesit gerçek ve dar:

- **player kromu** — rengi `set_player_color` ile ulaşılabiliyor, ama font,
  köşe yuvarlaklığı, gölge, spacing XML'den ulaşılamıyor
- **HTML form elemanları** — text-entry alanları gerçek `<input>`; XML'den
  stil verilemez
- **odak halkası** — klavye erişilebilirliğinin görünürlüğü
- **`@media print`** — sertifika yazdırma

Kural: **CSS yalnızca XML'in ulaşamadığı yere dokunur.** Slayt içeriğine
dokunan selector reddedilir.

### Kırılganlık aynı sınıfta değil

JS `GetPlayer()`'a yaslanıyor — Articulate'in **ilan ettiği sözleşme**.
CSS publish HTML'inin sınıf adlarına yaslanıyor — sözleşme değil, **uygulama
detayı**, ve Articulate onu sürümler arası değiştiriyor.

Bu yüzden CSS kataloğa serbest bir yetenek olarak değil, **dar bir izin
listesiyle** girer. J2'ye üçüncü bir ölçü ekler:

**`css_kesiti`** — enjekte edilen CSS'in selector'ları hangi kesite dokunuyor:
`player` / `form` / `print` geçer, `slayt` reddedilir. Kapsamını yanında
basar: *"kesit denetlendi, görünüm denetlenmedi."*

### Komşu eksenler, güç sırasına göre

CSS aslında en zayıf aday. İki eksen ondan güçlü:

**Web Object** — kendi origin'i, kendi DOM'u; Articulate'in DOM'una hiç
bağımlı değil, `postMessage` ile konuşuyor. Kırılganlık açısından CSS'ten kat
kat iyi, yetenek açısından kat kat güçlü. Ayrı bir varlık türü olduğu için
ayrı tur: `.story` içine web object klasörü yazmak, medya gömmekle aynı
aileden bir iş.

**Publish sonrası paket katmanı** — SCORM manifest, xAPI uç noktası. Araç
`.story` yazıyor, publish çıktısına hiç dokunmuyor; bu **ölçülmemiş bir
boşluk**, kusur olduğu henüz gösterilmedi.

### Sıra

```
J1 (JS yazma yolu)  ->  CSS, J4 katalogunda bir yetenek TURU olarak
                    ->  Web Object, ayri tur
                    ->  paket katmani, once olculsun
```

CSS'e ayrı faz açılmıyor. Katalog kaydına **"dokunduğu kesit"** alanı eklenir
ve `slayt` yasaklı değer olur.

---

## 4. Bu fazın kendi tuzakları

- **Doğrulayıcı burada Storyline'ın kendisi.** Sözdizimi doğru JS, yanlış
  action adıyla dosyayı açılmaz yapabilir. `open_test` bu fazın kanaryası.
- **Storyline JS'i doğrulamıyor.** Hatalı kod sessizce hiçbir şey yapmaz —
  hata yok, uyarı yok, davranış yok. En sinsi geçme biçimi.
- **`js` özniteliği XML'de ham metin.** Kaçış biçimi J0'da ölçülecek, tahmin
  edilmeyecek.
- **JS bir kusuru ölçümün dışına taşıyabilir.** Bir iş JS'e devredildiği anda
  mevcut hiçbir kontrol onu görmez. Faz J2'nin kuralı bu yüzden var.

---

## 5. Baştan kabul edilen sınırlar

Bunlar hata değil; katalog ve panel bunlara göre kurulacak.

- **Önizleme JS çalıştırmaz, CSS uygulamaz.** `preview.py` slaydın kendi
  geometrisini SVG'ye çiziyor; ikisinin de etkisi yalnızca publish çıktısında
  görülür. Panelin "gördüğü" ile öğrencinin gördüğü bu eksende ayrışır — ve
  ayrışmayı kapatmanın yolu önizlemeyi büyütmek değil, kesiti dar tutmak (3b).
- **Değişken tipleri text/number/boolean.** Dizi/nesne yok; JSON string'e
  sıkıştırmak gerekir (SCORM 1.2'de `suspend_data` 4096 karakter).
- **Quiz motoru JS'e kapalı.** Soru puanı ve sonuç hesabı Storyline'da kalır;
  `submitInteraction` taklit edilemez.
- **`fetch` senkron beklenemez.** İstek dönerken slayt devam eder; her ağ
  yeteneği "yükleniyor" katmanı + bitişte `SetVar` sinyali taşımak zorunda.
- **LMS ve CSP kısıtları buradan ölçülemez.** Katalog "ne zaman çalışmaz"
  alanını taşır; "çalışır" garantisi vermez.

---

## 6. Karar bekleyen

~~Panel yüzeyi (b) mi, sonra (c) mi~~ — **karar verildi ve kuruldu**: katalog
birincil, ham JS `js_precheck` kapısından geçen ikincil yol (J3).

~~Katalog nerede durur~~ — **`storyline_mcp/jscat.py`** (J4).

~~`js_sozdizimi` Node'a bağımlılık mı~~ — **çözüldü**: Node yokken
`available: false` döner ve özet `js_syntax_errors: None` verir, `0` değil.
Suit Node'suz da yeşil koşar; kontrol sadece **koşmadığını söyler**.

- CSS izin listesi `player` / `form` / `print` ile mi başlar, yoksa ilk turda
  yalnızca `form` ve `print` mi — player kromu en çok istenen ama en kırılgan
  kesit.
- Web Object turu J4'ten sonra mı, paralel mi. Ayrı varlık türü olduğu için
  J1'i beklemesi gerekmiyor.
- Publish sonrası paket katmanına (SCORM manifest / xAPI) hiç dokunulacak mı.
  Önce **kusur olduğu ölçülmeli** — K20: bir kayıt, kusurun varlığını değil
  birinin onu gördüğünü belgeler.

---

## Sıradaki iş

J0, J1, `EVENTS` ve uçtan uca zincir kapandı. JS köprüsü üretim yolundan
kuruluyor ve **çalıştığı görüldü**.

**J2 de kapandı.** Kör nokta artık kapalı: `audit` çözülmeyen değişken
adlarını, sözdizimi hatalarını ve okunamayan dinamik çağrıları sayıyor;
kontrol karakterleri `add_trigger`'da reddediliyor; bozuk paket `save`'de
duruyor.

**J3 ve J4 de kapandı.** Katalog dört ölçülmüş yetenekle kuruldu, panelde
kendi sekmesinde duruyor, ham JS `js_precheck` kapısının arkasında.

Sıradaki iş:

- ~~"Önceki buton" olayının karşılığı~~ — **kapandı: yok** (ölçüldü).
- ~~`add_text_box`'ta `h` verildiğinde sessiz kırpma~~ — **kapandı: kırpma
  yok, komşusuna biniyor**; `invariants` zaten ölçüyor.
- ~~`shoot_preview`: F12 tekrarı ve `--imza`sız çağrıda uyarı~~ — **kapandı**.
- **Kalan event'lerin Preview doğrulaması.** "EVENTS ölçüldü" hâlâ "EVENTS
  çökmüyor" demek; yalnızca `OnStart` ve `OnVariableValueChange` tetiklendiği
  görüldü. *Yoldaş alan hipotezi bağışçı XML'iyle sınandı ve `OnDrop` için
  doğrulandı, `OnStateChange` için şüpheli kaldı, `OnDialTurns` için
  bulunmadı.* Kalan: bu üçünün çalışma anı (sürükleme/durum otomasyonu), ve
  `OnIntersect` / `OnKeyPress` — ikisinde de bağışçı kapsamı **sıfır**.

  **YENİ BAĞIMLILIK (2026-08-28) — öğretim ölçüsü bu maddeyi bekliyor.**
  `audit`'e eklenen `tetikleyici_cesitliligi` ve `ardisik_etkilesimsiz_slayt`
  (`storyline_mcp/pedagogy.py`), üretilen kursları etkileşim yönünde itecek.
  Çeşitliliği artırmanın en doğal yolu ise tam da bu ölçülmemiş event'lerden
  birine uzanmak: `OnDrop` ile bir seçim etkileşimi, `OnStateChange` ile bir
  sekme. Ölçü tetikleyiciyi **yazıldığı gibi** sayıyor, **ateşlediği gibi
  değil** — kapsam cümlesi bunu söylüyor. Dolayısıyla bu madde kapanmadan
  öğretim tarafındaki kural (B) modeli o event'lere yönlendirirse, metrik
  yükselirken sessizce çalışmayan tetikleyici üretme riski geri gelir: sayı
  iyileşir, kurs iyileşmez. Sıra: **önce kalan 15 event'in preview
  doğrulaması, sonra B'de etkileşim kuralının o event'leri önermesi.** Şimdilik
  B, ölçülmüş iki yola (`add_question` ve `showSubSlide` katmanı) sınırlanmalı.
- **`sayac` ve `tasma_uyarisi`'nın ölçülmemiş kenarları.** 9 anlamlı
  basamağın ötesi; **LMS oturumunda** kalıcılık. *Sıçrama kenarı ve publish
  artefakt zinciri ölçüldü ve kapandı; kalan boşluk LMS'e özgü.*
- **Katalogda ölçülmemiş kalan yüzeyler.** `tarih`'in dört biçiminden biri,
  `metin_karsilastir`'ın şapkalı harf ve boşluk kırpma yolları, `rastgele`'nin
  dağılımı ve uç değerleri: hepsi aynı kod yolundan geçiyor ama **ayrı
  ölçülmedi** ve `olcum` alanları bunu açıkça söylüyor.
- **Katalogun ikinci turu.** İlk turda ölçülemeyen dördü (LMS adı, PDF,
  `localStorage` devam, metin girişi doğrulama) ancak eksik ölçüm yüzeyi
  kurulunca girebilir: LMS taklidi, kütüphane gömme yolu, iki oturumluk
  ölçüm, metin girişi soru tipi bağışçısı.
- **Web Object turu** ve **publish sonrası paket katmanı** — ikincisi önce
  kusur olduğu ölçülmeli.

Ölçüm altyapısı hazır ve elle Storyline işi gerektirmiyor: aç → kirlet →
kaydet → kapat → geri oku (dosya ne diyor), Triggers panelini yakala
(Storyline nasıl okuyor), Preview'ı yakala (gerçekten çalışıyor mu). Üçü ayrı
soru ve biri diğerinin yerine geçmiyor.
