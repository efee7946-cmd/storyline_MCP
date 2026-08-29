# storyline-mcp — Devir Notu

Bu belge, projeye yeni giren bir asistan içindir. Sırayla oku, atlama.

---

## 0. Önce bunları oku (kod yazmadan önce)

Bu projede kazanılmış disiplin, kodun içinde yazılı. Aşağıdaki dosyaların başındaki
yorumlar bu projenin en pahalı öğrenilmiş dersleridir. **Onları okumadan hiçbir
kontrole dokunma.**

| dosya | ne anlatıyor |
|---|---|
| `tools/canary.py` | doğrulayıcının kendisi yalan söyleyebilir; negatif sonuç kendini kanıtlamaz |
| `tools/scope.py` | her ölçünün kapsamı, verdiktinin yanında basılır |
| `tools/look.py` | önizlemenin sadakat notu — neyi doğru, neyi yaklaşık çizdiği |
| `tools/invariants.py` | korunan invaryantlar ve her birinin geçerlilik koşulu |
| `tools/silhouette.py` | ölçünün kör noktası (renk, punto, ağırlık, ritim görünmez) |
| `storyline_mcp/pedagogy.py` | öğretim ölçüsü: etkileşim tanımı ve kesitin dışı (K30) |
| `README` (bilinen sınırlar bölümü) | kabul edilmiş sınırlar — bunlar hata değil |

---

## 1. Durum

Yol haritasının yedi görevi kapandı: donör anatomisi, kurs başına farklı buton,
soru slaydı bölmesi ve sığdırma, varyant motoru, SVG önizleme, tema sistemi,
rubrik değerlendirme.

Yeşil koşan kontroller:
`invariants` (11 madde) · `golden` · `variety` · `deadband` · `themes_check` ·
`coverage` · `contrast` · `rubric_fixtures` · `scope` · `consistency` · `canary`

**Ama üretilen gerçek kursta on kusur var ve onu da bu paket yeşilken buldum.**
Yani asıl iş kusurları düzeltmek değil — kusurların neden yakalanmadığını bulmak.

**2026-08-28 — ikinci eksen açıldı: eğiticilik.** Yukarıdaki kontrollerin
tamamı kursun *nasıl göründüğünü* ölçüyor. Üretilen `teknoloji_bagimliligi`
bu paket yeşilken **eğiticilik açısından boş** çıktı: 0 soru, 0 etkileşim,
14 slaydın 14'ü ardışık okuma. Sebep K30'da. Ölçü kuruldu
(`storyline_mcp/pedagogy.py`, `audit`'ten dönüyor) ve taban donduruldu
(`tools/ogretim_taban.json`).

Sıradaki iş **B**: `SYSTEM_PROMPT`'a öğretim tasarımı bölümü. Taban bu yüzden
B'den ÖNCE alındı — B'den sonra aynı promptla yeni bir kurs üretip ölçüyü
tekrar koşmadan, değişikliğin davranışı değiştirdiği değil yalnızca kelime
sayısını artırdığı da mümkün kalır. İyileşme varsayılmaz, ölçülür.
B'nin etkileşim kuralı şimdilik **ölçülmüş iki yola** sınırlı
(`add_question`, `showSubSlide` katmanı) — gerekçe: JS_YOL_HARITASI.md'deki
"kalan 15 event'in preview doğrulaması" maddesi.

**B uygulandı (2026-08-28).** `SYSTEM_PROMPT`'a `Ogretim tasarimi:` bölümü
eklendi (Sayfa tasarımı'ndan önce), artı üç cerrahi düzeltme: "parça parça"nın
kapsamı daraltıldı (etkileşim kurmayı kapsamıyor — `add_question` ve
`add_layer` compose_slide'ın alternatifi değil, karşılığı olmayan yollar),
sonuç slaydı opsiyondan kurala çevrildi, katman "popup" yerine öğretim aracı
olarak çerçevelendi ve kurulabilir tarifi yazıldı.

**Döngü henüz KAPANMADI.** Kalan iki adım, ikisi de zorunlu:

1. **MCP sunucusu yeniden başlatılmalı.** B'nin "işi bitirmeden önce `audit`
   çağır ve `sorusuz_sahneler`'e bak" kuralı, A'nın alanlarının canlı olmasına
   bağlı. Sunucu eski kodu tutarken model `audit` çağırır, alanı bulamaz ve
   kural **sessizce hiçbir şey yapmaz** — K26'nın birebir şekli (kontrol hiç
   koşmuyor, ama koşmuş gibi görünüyor).
2. **Yeni bir kurs üretilip ölçü tekrar koşulmalı.** Taban
   `tools/ogretim_taban.json`'da duruyor. Bu yapılmadan B'nin davranışı
   değiştirdiği değil, yalnızca prompt'u 380 kelime uzattığı da mümkün.

Ayrıca B'den bağımsız bir düzeltme geçti: `SYSTEM_PROMPT`'un
"YAPILAMAYANLAR" listesi kendi kendisiyle çelişiyordu — "diskten görsel
ekleme" ve "tema rengi/fontu değiştirme" yapılamaz diye yazılıyken aynı
prompt 30 satır yukarıda `add_image`, `set_theme_colors` ve `set_theme_font`
kullanmayı öğretiyordu (üçü de kayıtlı araç). K29: var olmayan bir sınırı
belgelemek de hatadır. Liste gerçek sınırlarla değiştirildi (internetten
indirme, timeline animasyonu, sürükle-bırak/metin girişi/soru bankası).

---

## 2. Değişmez kurallar

Bunlar tercih değil. Bu projede her biri en az bir kez pahalıya öğrenildi.

**K32 — İki üretici varsa kural ikisinin de okuduğu yerde durur.**
Bu projede kurs üreten **iki** yol var ve ayrı kod yolundan geçerler:
`panel/agent.py` (SYSTEM_PROMPT + araçlar) ve `panel/builder.py` (kendi
promptları, araç yok, JSON'dan deterministik kurulum). Pedagoji kuralları bir
süre ikisine dağılmıştı ve bu **ölçülebilir bir kusur üretti** (2026-08-28):

- `"asagidakilerden hangisi kaliplarindan kacin"` yalnızca builder'daydı →
  komut yolundan çıkan kursta iki soru *"Bu ifade doğru mudur?"* biçiminde
  geldi, cevap sorunun içinde yazıyordu. **Kural yazılmıştı, diğer yarıdaydı.**
- Ters yön de doğruydu: etkileşim ritmi, öz-değerlendirme ve sınır vakası
  kuralları yalnızca SYSTEM_PROMPT'taydı, brief yolu onları hiç görmüyordu.

Kurallar `panel/ogretim.py` → `ORTAK_KURALLAR`'a alındı; iki prompt da
`.replace("{ogretim}", ...)` ile aynı metni yerleştiriyor. Yola özgü olan
kendi promptunda kaldı: `audit` çağırmak, katman kurmak ve sonuç slaydı
eklemek yalnızca komut yolunun elinde (builder araç çağırmaz); seçenek sayısı
kısıtı ve JSON biçimi yalnızca brief yolunu ilgilendirir.

Bir çelişki de bu sırada kapatıldı: kullanıcı künyeden "soru olmasın"
seçtiğinde `_question_rule` artık ortak kuralı **açıkça geçersiz kıldığını**
söylüyor; yoksa aynı prompt hem "her konu sahnesinde soru olsun" hem "soru
olmayacak" derdi.

Kural: aynı işi yapan iki üretici varsa, ortak kural ikisinin de okuduğu tek
bir yerde durur. [[K30a]] belgenin üreticiye ulaşmadığını söylüyordu; bu onun
ikizi — kural doğru yere yazılmış olsa bile, **yerlerden yalnızca birine**
yazılmışsa yarısı boşta kalır.

**K31 — Kusur veriye yazıldıysa, fonksiyonu düzeltmek yayılmayı durdurmaz.**
2026-08-28: üretilen bir kursta çok-doğru sorularının 1 numaralı seçeneği
sonuna satır sonu alıyordu. Zincir üç katmandı ve **her katman ayrı düzeltme
istedi**:

| katman | kusur | düzeltme |
|---|---|---|
| tohum | `question_freePickManyIntr_5.xml`'de başıboş `<Block />` | tohumdan silindi |
| fonksiyon | `set_shape_text` Span'leri boşaltıyor, Block silmiyor → şablonun ikinci Block'u da aynı sonucu veriyor | `_drop_trailing_empty_blocks` eklendi |
| **veri** | düzeltmeden önce yazılmış slaytlar dosyada duruyor | `tools/bos_blok_temizle.py` |

Üçüncüsü atlanırsa ilk ikisi **işe yaramaz görünür**: tohum temizlendikten
sonra `egitim.story` üzerinde test edildi ve hâlâ kirli çıktı, çünkü
`_pick_template` gömülü tohum yerine projenin **kendi** (kirli) soru slaydını
tercih ediyor. Yani her kirli slayt yeni bir klonlama kaynağıdır ve dosya
kendi kusurunu çoğaltır.

Kural: bir kusur üretilmiş dosyalara yazılmışsa, düzeltme üç soruyu ayrı
ayrı sorar — *kaynak ne üretiyordu*, *fonksiyon ne yazıyordu*, *dosyalarda ne
duruyor*. Üçüncüsü cevaplanmadan "düzeltildi" denemez. Ölçüldü: 7 dosya, 83
belge kirliydi; biri **donör havuzundaydı**, yani kusurun yeni kurslara
girmek için ikinci bir yolu daha vardı.

**K30 — Ölçülmeyen eksen optimize edilmez; üretici ölçüleni üretir.**
2026-08-28: üretilen `teknoloji_bagimliligi.story` görsel olarak düzgündü ve
eğiticilik olarak boştu — 14 slayt, 28 tetikleyicinin **hepsi** "sonraki
slayda git", 0 soru, 0 katman. Bu bir üretim kazası değildi; sistem tam olarak
kendisine söylenen ve puanlanan şeyi üretti:

| yer | ne diyor |
|---|---|
| `panel/agent.py` → `SYSTEM_PROMPT` | 4 bölüm, dördü de görünüş ve mekanik. Öğretimle ilgili tek satır: feedback "gerekçe olsun". |
| `tools/rubric.py` → `prompt_for()` | birebir: *"Icerigin dogrulugunu DEGERLENDIRME; yalnizca gorsel tasarimi."* Beş ölçütün beşi de görsel. |
| `storyline_mcp/compose.py` → `LAYOUTS` | 7 düzenin 7'si de sunum. Etkileşimli düzen yok — ve prompt "önce compose_slide kullan" diyor. |

Yani en az dirençli yol her zaman okunur bir sayfa üretiyordu. **Yetenek eksik
değildi** — `add_question`, `add_results_slide`, `add_layer` hepsi çalışıyor.
Eksik olan talimat ve ölçüydü. Bir rubrik bu kursa yüksek puan verirdi ve
vermekte haklı olurdu: baktığı şey o değil.

Kural: bir kalite ekseni için **ölçü yoksa, o eksende iyileşme de yoktur** —
üretici ölçülmeyeni serbest bırakır. Yeni bir kalite iddiası ("kurslar daha
öğretici olsun") önce bir ölçüye bağlanır, sonra talimata.

**K30a — Belge üreticiye ulaşmaz; kural aktörün okuduğu yere yazılır.**
Aynı turda ölçüldü: projede hiç `CLAUDE.md` yok, ve panel `claude`'u
`cwd = <story dosyasının klasörü>` ile koşuyor (`panel/agent.py`, `Popen`).
Yani `Art/` veya `storyline-mcp/` altına konacak bir `CLAUDE.md` headless
çalışmaya **hiç yüklenmez**. Headless Claude'a giden tek metin
`--append-system-prompt SYSTEM_PROMPT`.

Bunun sonucu, bu DEVIR dahil her belge için geçerli: **buradaki bir kural
üreticinin davranışını değiştirmez.** Belge insanı ve projeye yeni giren
asistanı bağlar; üreticiyi yalnızca `SYSTEM_PROMPT` bağlar. İkisi karıştırılırsa
kural doğru yazılmış ama yanlış yerde durmuş olur ve her kurs onu yeniden
unutur.

*(Story klasörüne `CLAUDE.md` koymak teknik olarak üreticiye ulaşırdı — cwd
orası. Önerilmiyor: depodan görünmez, o klasördeki her oturuma sızar ve aynı
kuralı `SYSTEM_PROMPT` ile iki yerde tutar. İki yer ayrışır.)*


**K29 — Var olmayan bir sınırı belgelemek de hatadır; eksen iki yönlüdür.**
Bu DEVIR'deki hataların hemen hepsi tek yönde: **bozukken sağlam görünmek**
(K8 bağ yok, K26 kontrol hiç koşmuyor, K27 üretici ölçülmemiş). Diğer uç da
gerçek: **sağlamken kısıtlı görünmek.**

`tasma_uyarisi`'nın `calismaz` alanı "eşiği tek hamlede aşarak atlayan sıçrama
ölçülmedi" diyordu. Ölçüldüğünde sınır **yoktu** — olay her gerçek değişimde
tetikleniyor ve yetenek değişim sonrası değeri okuyor; yol önemsiz. Varsayım
tasarımda değil, tasarımın **anlatısındaydı**.

Bu hata çökme üretmez, sessiz veri kaybı üretmez, hiçbir kanaryayı düşürmez —
bu yüzden fark edilmeden kalır. Maliyeti başka: yeteneği hak etmediği bir
şüpheyle sunar, çağıranı gereksiz yere ihtiyatlı yapar, ve yanlış yerde
çözüm arattırır.

Kural: bir sınır yazmadan önce, onun **ölçüldüğü** mü yoksa **düşünüldüğü** mü
belli olsun. "Ölçülmedi" yazmak dürüsttür; "çalışmaz" yazmak bir iddiadır ve
iddia ölçü ister. Ölçüm bir sınırı çürütürse belge, kod kadar hızlı düzeltilir.

**K28 — Bir gözlem sinyalinin en az ÜÇ hâli olmalı.**
İkiye indirgenen her sinyalde "hiç gözlenmedi" ile "gözlendi, sorun yok" aynı
okumaya çöker. Bu turda iki ayrı biçimde kuruldu:

| biçim | üç hâl |
|---|---|
| değer bazlı | SayacT (kilitli) · SayacJ (tam) · Kontrol (kanarya — mekanizma çalışıyor mu) |
| durum bazlı | `-` hiç ateşlemedi · `OK` ateşledi, eşik altı · `RISK` ateşledi, eşik üstü |

İkincisi ekstra bir kanarya gerektirmedi: uyarı değişkeninin **varsayılanı**
üçüncü hâli taşıyor. Sinyal tasarlanırken "gözlenmedi" hâline bir yer
ayrılırsa, sonradan kanarya eklemeye gerek kalmaz.

K26'nın kuzeni ama ayrı: K26 kontrolün **çalıştığını** kanıtlamakla ilgili,
K28 kontrolün **sonucunu yanlış okumamakla**.

**K27 — Bir tekniğin ölçülmesi, o tekniği ÜRETEN sarmalayıcının ölçülmüş olduğu anlamına gelmez.**
Teknik doğru olabilir ve onu üreten katman yine de yanlış üretiyor olabilir.
Bu projede en az üç kez, üç ayrı katmanda çıktı:

| teknik ölçüldü | üretici ölçülmedi | sonuç |
|---|---|---|
| `verify()` bozuk paketi doğru raporluyordu | `save()` o raporu hiçbir kapıya bağlamıyordu | bozuk paket diske yazıldı |
| el yazması JS Preview'da çalışıyordu | `js_precheck`'in beslendiği alanlar | denetim eklemeden **sonra** bakıyordu, yani kapı değildi |
| el yazması JS sayaç kayıpsızdı | `jscat.uygula`'nın ürettiği kod | var olan değişkeni yeniden kullanan her çağrı reddediliyordu |

Üçüncüsü kuralın kendi turunda çıktı: el yazması teknik ölçülmüştü, "eşdeğeri
ölçüldü" denip geçilebilirdi. Ayrıca ölçülünce kusur oradan çıktı.

Kural: bir teknik ölçüldükten sonra, onu **üreten** yol ayrıca ölçülür —
kendi çıktısıyla, kendi çağrı yolundan. K8'in ("test edilen ≠ bağlanan")
üretim tarafı: orada bağ eksikti, burada bağ var ama **ürettiği şey** farklı.

**K26 — Yeni bir "0 / temiz" döndüren kontrol, bozuk girdiyle bağırdığı görülmeden kapanmış sayılmaz.**
Üç kez, birbirinden bağımsız yerlerde, aynı biçim çıktı: kontrol **hiç
çalışmıyordu** ve tam da bu yüzden "0 bulgu" diyordu.

| nerede | neden hiç çalışmadı | nasıl görünüyordu |
|---|---|---|
| `model.py` regex | `` kaynağa **gerçek backspace** (0x08) yazılmış, hiçbir şeyle eşleşmiyor | "0 çözülmeyen değişken" |
| `package.save` | `verify()` doğru rapor veriyor ama **hiçbir kapıya bağlı değil** | rapor temiz görünüyor, bozuk paket diske yazılıyor |
| `audit` sayı kontrolü | `model.triggers` `adjustVar` değerini hiç açmıyor; değişken tarafında anahtar adı yanlış varsayılmış | "0 bozuk sayı" |

Ortak nokta: **temiz bir dosyadan ayırt edilemez.** Yeşil çıktı, kontrolün
çalıştığının değil yalnızca patlamadığının kanıtı. Ve bu üçü, kontrolü kuran
turun kendisinde oluştu — yani "dikkatli yazdım" bir savunma değil.

Kural: bir kontrol, kurulduğu turda **bilinen bozuk bir girdiyle pozitif
test edilmeden** bitmiş sayılmaz. Negatif taraf (temizde sessiz) tek başına
yetmez; ikisi birlikte kanaryadır. Kontrol dış bir girdiye dayanıyorsa
(dosya alanı, sözlük anahtarı, başka bir fonksiyonun döndürdüğü alan) o
girdinin **geldiği** de ayrıca görülmeli — anahtar adı varsayımı sessizce
boş küme üretir.

K1'in yazma tarafı: orada "bulamadım ≠ yok", burada "bulamadım ≠ **baktım**".

**K1 — Göremediğini yokluk sanma.**
Bu projenin tekrar eden tek hata sınıfı budur. Örnekleri: regex stili göremiyordu
ve "stil yok" sandı; prova metin koşusu olmayan şekle "etiket tutmadı" dedi;
önizleme geometriyi bilmediği için düz dikdörtgen çizdi ve "sorun yok" dedi.
Her kontrolde "bulamadım" ile "yok" ayrı raporlanmalı.

**K2 — Doğrulayıcıyı doğrulamadan güvenme.**
Her kontrol, kasten bozularak sınanmalı. Bozuk girdide bağırmayan bir kontrol,
olmayan bir kontroldür. Kanaryanın kendisi de bir kez yalancı çıktı.
**Yönü de sına:** `check_floor_respected` taban *düşürülünce* bağırıyordu ama
*yükseltilince* sessiz geçiyordu — tehlikeli yön oydu.

**K2b — Guard'ın eşiği, koruduğu modülden okunamaz.**
Okunursa ölçünün iki yanı birlikte kayar ve eşiği kaldıran değişiklik sessizce
geçer. Bu kural DEVIR'de ve `invariants.py`'de **iki kez yazılıydı** ve üçüncü
kez ihlal edildi — yazılı ders tekrarı engellemedi. O yüzden belgeden koda
taşındı: `check_thresholds_independent` kaynağı ayrıştırıp her `check_*`
fonksiyonunda motor sabitinin **karşılaştırma içinde** kullanılıp
kullanılmadığına bakar. İlk koşuda önceden var olan bir örneği buldu
(`check_floor_respected`, `compose.FLOOR`) ve o örneğin gerçekten atıl olduğu
ölçülerek doğrulandı: taban 99'a çıkarıldığında içerik %99.1'e iniyor ve guard
susuyordu. Tolerans istisnadır ve gerekçesiyle listede
(`ESIK_ISTISNALARI`) — yazma yolunun bilerek verdiği pay paylaşılmalı.

**K3 — Negatif sonuç kendini kanıtlamaz.**
"Değişmedi" ile "hiç koşmadı" aynı görünür. Bir deney negatif sonuç veriyorsa,
önce deneyin çalıştığı ayrıca kanıtlanmalı. Bir notun gerekçesi bir deneyin
sonucuysa, deneyin geçerliliği de notta dursun.

**K4 — Kolay veriyle kurulan kontrol, koruduğunu sanmaz.**
Sentetik test verisi çoğu zaman hatayı üretemez. Kontroller gerçek üretim
corpus'una bağlanmalı. (Örnek: kalibrasyon Türkçe diakritik içermeyen metinle
yapıldı ve satır yüksekliği eksik tahmin ediliyor olabilir.)

**K5 — Kapsamı verdiktin yanında bas.**
Ayrı belgede duran kapsam okunmaz. "variety GEÇTİ" zamanla "kurs çeşitli" diye
anlaşılır. Her ölçü ne ölçmediğini kendi çıktısında söylemeli.

**K6 — Kısmi kapsam, kapsamadığını söylemez.**
Bu projede üç kez oldu: 2 varyantla bakan prob "TAMAM" dedi, 6 varyantta hata
çıktı. Kontroller örneklem değil tam çarpım taramalı, taramıyorsa bunu yazmalı.

**K7 — Guard tek yönlüyse kazanım korunmaz.**
Kötüleşmeyi yakalayan ama iyileşmeyi kaydetmeyen kontrol, iyileşmenin sessizce
geri dönmesine izin verir. Ölçülmüş eşikler iki yönlü olmalı. (Dış standarttan
gelen eşikler — WCAG gibi — bilinçli olarak tek yönlü kalır.)

**K1b — Girdisi olmayan kontrol "geçti" demez.**
K1'in dosya seviyesindeki hâli ve ayrı yazılmayı hak ediyor. `check_text_fits`
girdisi yokken bir uyarı basıp **boş liste** dönüyordu — çıktıda açıklama var,
verdikt yeşil; geçmenin en sinsi biçimi. Faz 1'de tarandı, `invariants.py`'de
üç yer bulundu (`floor`, `no_overlap`, `text_fits`), üçü de artık hata
döndürüyor. Kasten girdi saklanarak sınandı.

**K8 — Sınandı ≠ bağlandı.**
Bir fonksiyon test ediliyor olabilir ama üretim yolu onu hiç çağırmıyor olabilir.
Bu projede üç kez oldu. Her düzeltmede "bu kod gerçekten üretim yolunda mı"
ayrıca doğrulanmalı.

**K9 — Ölçüyü hedefle karıştırma.**
Bir kez boş alan yüzdesini düşürmek için butonlar şişirildi: sayı iyileşti,
tasarım bozuldu. Ölçü hedefin göstergesidir, hedefin kendisi değil.

**K11 — Uzun koşu sürerken kaynağa dokunma.**
Dokunduysan o adımın verdiktini at, geçmiş olsa bile. Koşu başladığı andaki
kodla bittiği andaki kod aynı değilse, yeşil hangi koda ait bilinmez. Faz 1'de
`--tam` koşarken `invariants.py` düzenlendi; adım temiz geçti ama sonuç
atıldı ve son kodla yeniden koşuldu. Aynısı **dosyalar** için de geçerli ve
orası daha sinsi: bir fikstürü geçici olarak taşımak, o sırada koşan bir
adımın girdisini yok eder.

**K12 — Bir sayıyı bir yer hesaplar.**
İki uygulama er ya da geç ayrışır, ve ayrıştığında hangisinin doğru olduğu
okunamaz. Bu projede üç kez oldu: `donors._harvest_file`, ve Faz 1'de kopuk
tetikleyici — `completeness` 43, `inventory` 25 diyordu. Fark yuvarlama
değildi: `inventory` boş slaytlarda taramayı atlıyordu ve devralınan çöp tam
orada yaşıyor. Hesap `completeness.dangling_triggers`'a indirildi.

**K13 — Kolaylık bileşeni, koşunun geçerliliğini taşıyamaz.**
Üç kez aynı desen: odak guard'ı (öne alma "kolaylık"tı, tuşlar Chrome'a gitti),
piksel sayacı (satır saymak "yardımcı"ydı, ters yönde oran üretecekti), özet
kodlaması (son satır "kolaylık"tı, `UnicodeEncodeError` bütün suit'i düşürdü).
Kural: **koşunun geçerliliği hiçbir kolaylık bileşenine bağlı olamaz**, ve bir
kolaylık bileşeninin çıktısı **doğrulanmadan ölçüme giremez**. Piksel sayacı
şu an hâlâ bu durumda — "yardımcı" etiketi bir sonraki turda ona güvenilmesini
engellemiyor.

**K14 — Her sabit, hangi ölçüme karşı seçildiğini yanında taşısın.**
Bir politika sayısı sessizce bir model hatasını massedebilir ve o hata
düzeltildiğinde ortaya çıkar. İki örnek aynı oturumda çıktı: `2.35×` "yerleşim
güvenlik payı" sanılıyordu — ölçüldü, çok satırda **yetersizmiş**; ve
`GROWTH_LIMIT = 2.4` eski `CHAR_WIDTH_RATIO = 0.72`'ye karşı ayarlanmıştı —
oran 0.79'a çekilince donör havuzu 40 harfte **8'den 1'e** düştü. Sabitin
kendisi değişmedi, altındaki zemin değişti. Aynı zeminde seçilmiş her eşik
(`POOL_FLOOR`, `deadband` bandı, `EMPTY_BASELINE`) aynı riski taşır; sessiz
kalanlar, kendini gösterenden tehlikelidir.

**K18 — Ölçüm noktası, ölçülen şey tarafından sıfırlanıyor olabilir.**
`density_scale` ölçülürken çağrı sonrası `page.scale` okundu ve altı çağrıda
da 1.0 çıktı; "mekanizma dönmüyor" sonucuna varıldı. Yanlıştı: fonksiyonun
kendi `finally` bloğu `page.scale = base` yapıp değeri geri alıyor, yani
gözlemlenen sayı **tanım gereği sabit**. Doğru ölçüm (dönüş değeri) 1.7
gösterdi — mekanizma tam kapasite çalışıyormuş.

Sayacın kendi çıktısını doğrulaması ailesinden: gözlem noktası, gözlenen
şeyin temizlik/geri-alma yoluna düşerse ölçüm sessizce sabitlenir ve
**tutarlı ama yanlış** çıkar — yakalanması en zor tür. Bir değeri okumadan
önce sor: bu değeri, okuduğum an kim yazıyor?

**K24 — Bir hipotezi elemek için tekrar tekrar kullanılan sayı, kendisi bulgu olabilir.**
Bir ölçüm birden çok kez "bu kusur değil" demek için kullanılıyorsa, o sayının
**kendisine** bakılmalı. Elemek, açıklamakla aynı şey değil.

*Slayt başına ortanca şekil sayısı — bizde 5, elle yapılmış kursta 14* — bu
oturumda **üç ayrı yerde** çıktı:

- C3'ün slayt içi yarısını çürüttü (oran farkı yoğunluk artefaktıydı)
- C2'nin "içerik azlığı" hipotezini doğurdu ve sonra kapsam dışı sayıldı
- `density_scale`'in tavana dayanmasını açıkladı

Üçünde de bir kusuru **elemek** için kullanıldı. Hiçbirinde *"bu sayının
kendisi bulgu olabilir mi"* diye sorulmadı — oysa aracın insanın koyacağının
**üçte biri kadar öğe** koyduğunu söylüyor, ve bu kusur listesindeki hiçbir
maddeye girmiyor.

**K23 — İki ölçüm yan yana konmadan önce aynı kümeyi kapsadıkları doğrulanır.**
K12'nin kesit tarafı. Bu turda **iki kez** aynı hataya yol açtı:

- `bos_alan` iki farklı şeyi ölçüyordu: benim raster'ım slayt geneli
  kaplamayı, `inventory`'ninki `deadband` üzerinden **içerik bandındaki
  ölü boşlukları**. Aynı ad, farklı soru — ve yeni ölçüye güvenip
  "ritim sorun değil" sonucuna varıldı; `deadband` tersini söylüyordu.
- Ölü bant dökümünde `%0` görünen dört slayt `section` sanıldı ve
  "C3 düzeltmesi C2'yi kötüleştirdi" diye yazılmak üzereydi. O dört slayt
  **soru slaydıydı**: `add_question`'dan geçiyorlar, `compose_slide`'dan
  geçmiyorlar, dolayısıyla varyant dökümünde hiç görünmüyorlar. İki liste
  yan yana konup aynı kümeye ait sanıldı.

İkisi de ölçümle döndü (varyantlar kapatılıp yeniden koşuldu: `section`
varyantsız **%48**, varyantlı **%43** — iyileşmiş). Ama ikisi de kayda
"düzeltildi" diye geçebilirdi.

**K22 — `shapeLst` düzeyinde çalışan her şey BUTON DURUMLARINI atlar.**
Bir buton altı durum taşır (normal, hover, down, visited…) ve her durumun
**kendi gövdesi** vardır. `shapeLst`'i gezip şekil düzeyinde iş yapan kod o
gövdeleri görmez — ve bu oturumda **üç kez** kör nokta oldu:

| nerede | nasıl göründü |
|---|---|
| `contrast` dönüşümlü renkler | tek dönüşümlü dolguların **hepsi** `bG < btn < shapeLst < state` içinde; doğrulama için uygun vaka sıfır çıktı |
| `_merdiven_disi` punto sayımı | "solidFill + tint 25" sayımı şeklin kendi dolgusunu değil **durum** dolgularını sayıyormuş |
| `compose_feedback_layers` snap | `_s is shape` kimlik karşılaştırması `Rectangle`'ları düzeltip **`Button`'lara hiç dokunmadı** |

Üçünde de kod "şekilleri gezdim" diyordu ve durum gövdeleri dışarıda kaldı.
`compose._restyle` bu yüzden **ata zinciri** yürüyor; şekil düzeyinde yazılan
her yeni ölçü ya aynı yolu izlemeli ya da neyi atladığını söylemeli.

**K21 — Bir metrik, insan ürününde de kötü değer veriyorsa kusuru değil olguyu ölçüyordur.**
Kalibrasyon noktası: aynı alanda çalışan, elle yapılmış, kabul edilmiş bir
ürün. Metrik orada da "kötü" çıkıyorsa ölçtüğü şey kusur değil, işin doğası.

C fazında **beş ölçütten dördü** bu testte düştü:

| ölçüt | çürüten ölçüm |
|---|---|
| C1 punto çeşidi | elle kursta 13 çeşit, **332/332 merdiven dışı**, sorun yok |
| C4 ikiz slayt | elle kursta **26 çift**, bizde 13 — iki katı |
| C3 ızgara/monopol ayrımı (rol karışımı) | elle kursun baskın x'inde de **dört rol** |
| C3 slayt içi oran (%67 vs %29) | **yoğunluk artefaktı**: ortanca 5 vs 14 şekil |
| C3 slaytlar arası imza | **çürümedi — gerçek kusurdu** |

Beşi de makul görünen ölçütlerdi. Kalibrasyon noktası olmasaydı dördüne de
iş harcanırdı. **K19'un operasyonel hâli**: sayının büyüklüğüne bakmadan
önce, aynı sayının kabul edilmiş bir üründe ne verdiğine bak.

**K20 — Bir kusur kaydı, kusurun varlığını değil, birinin onu gördüğünü belgeler.**
DEVIR kaydı **hipotez**, envanter **gözlem**. Bir bloğa girerken varsayılan
ilk adım tarifi ölçümle doğrulamaktır. Üç blokta üst üste ayrıştı:

| blok | tarif | ölçüm |
|---|---|---|
| B3 | "editörde `unassigned` görünüyor" | doğru, ama sayılan 37'nin **%0'ı** görünürdü; gerçek kusur başka sınıftaydı |
| B4 | "`slided`'de `Subtitle` ile `Eyebrow` üst üste" | o adlar dosyada **yok**; benzer çakışma var ama kullanıcının kendi kursunda |
| B5 | "tema geri bildirim katmanlarına ulaşmıyor" | **18/20 ulaşıyor**; 2 donör kalıntısı |

Üçü de yanlış değil — hepsi bir şey görülmüş olmasından geliyor. Ama hiçbiri
kusurun **kapsamını** doğru veriyordu, ve kapsam düzeltmenin şeklini belirler.
Tarifi doğrulamadan düzeltme tasarlamak, yanlış büyüklükte bir iş kurar.

**K19 — Sayının büyüklüğü, öncelik göstergesi değildir.**
Bir kontrolün *saydığı şey* ile kullanıcının *gördüğü kusur* arasındaki
mesafe ölçülmeden, sayı bir şey söylemez. B3'te ölçüldü:

```
elle yapilmis kurs : 37 "kopuk tetikleyici"  ->  editorde 0 uyari
bizim urettigimiz  : 30 "kopuk tetikleyici"  ->  neredeyse her sayfada
```

Ters orantılı. `dangling_triggers` **yanlış değil**, ama **kusura özgü de
değil** — ve bu ikisi karıştırıldığında 30 sayısı bir aciliyet gibi okunur.
Gerçek kusur o 30'un içinde bir alt küme (17 `interaction.submitG`) ve
onu ayıran şey sayım değil, **editörde tek bir bakıştı**.

Aynı aile: `check_question_frame` geometriye bakıp sıraya bakmıyordu;
`POOL_FLOOR` bağırıyor ama sebebini söylemiyordu. Ortak biçim: ölçü var,
kusura özgü değil.

**K18 — Ölçüm noktası, ölçülen şey tarafından sıfırlanıyor olabilir.**
`density_scale` ölçülürken çağrı sonrası `page.scale` okundu ve altı çağrıda
da 1.0 çıktı; "mekanizma dönmüyor" sonucuna varıldı. Yanlıştı: fonksiyonun
kendi `finally` bloğu `page.scale = base` yapıp değeri geri alıyor, yani
gözlemlenen sayı **tanım gereği sabit**. Doğru ölçüm (dönüş değeri) 1.7
gösterdi — mekanizma tam kapasite çalışıyormuş.

B3'te aynı sınıf ikinci kez çıktı: sıfır-GUID hedefleri "referans değil"
diye **filtreleyip** sonra "kusur yok" demek. Bir değeri okumadan önce sor:
bu değeri, okuduğum an kim yazıyor — ve filtrem aradığım şeyi eliyor mu?

**K17 — Bir sabitin doğrulanması, altındaki zeminin doğrulanması değildir.**
K14'ün eksik yarısı. Sabitin kaynağını yanında taşımak yetmiyor; **kaynağın
kendisinin ölçüm mü türetme mi olduğu** da taşınmalı.

`MEASURED_HSCALE[1920] = 2.667` üç turda "tuttu" ve üçünde de aslında ölçüm
değildi: `1920/720`'nin ta kendisiydi, ve `kare_satir.py --uzay 1920` piksel/
birim oranını sahnenin değil **slaydın ilan ettiği** genişlikten hesapladığı
için tabloya öyle yazılmıştı. Doğru cevap verdi, çünkü **yatay hesapta oran
sadeleşiyor** — kutu genişliği de karakter genişliği de aynı çarpanla
ölçekleniyor. Dikeyde sadeleşme yok (satır yüksekliği puntoyla mutlaktır),
ve orada aynı yanlış zemin `2.990` diye göründü; gerçek değer `2.000`.

Yani **aynı hatalı zemin bir eksende görünür oldu, diğerinde saklandı.** Bir
sabitin üç kez doğru sonuç vermesi, ölçülmüş olduğunun kanıtı değil.

Pratik hâli: tablo yalnızca **gerçekten ölçülmüş** uzayları tutar. Türetilmiş
bir çarpan tabloya girmez — kod onu yerinde hesaplar ve türetme olduğunu
söyler. Bir satırın "ölçüldü@X" etiketi taşıması, o etiketi kimin ve neye
bakarak yazdığı sorulmadan güvence sayılmaz.

**K16 — Vaka matrisinde eksenler tek tek değil, kesişimleriyle gezilir.**
Tek eksenli vakalar iki eşiğin **arasında** kalan bölgeyi hiç görmez.
`check_question_frame`'in üç vakası (`kisa/kisa`, `kisa/uzun`, `uzun/uzun`)
kök uzunluğu ve şık uzunluğu eksenlerinin ikisini de geziyordu ve **hiçbiri
kusuru üretmiyordu**: kısa etiket kutuya sığar, uzun etiket kutuyu *büyütür*
(99 → 290 birim), `uzun/uzun` gerekçesiyle reddedilir. Kusur `uzun/orta`
hücresinde — ne sığacak kadar kısa, ne büyütecek kadar uzun. Üretimde görülen
vaka tam o boydaydı.

Kayda değer ikinci yarısı: **boşluk kapsamdaydı, guard'da değil.** Taban
kapısı doğru yazılmıştı ve vaka eklenir eklenmez bağırdı (%118.7). "Kusur
üremiyor" ile "kusuru üretecek vakayı hiç kurmadım" aynı görünür — ve bu
projede ikincisi birincisi sanıldı.

**K15 — Kapsam sessizce daralır; her kapsam ölçülerek okunur.**
İki yüzü aynı oturumda çıktı ve ikisi de aynı aile:

*Silme kapsamı çağrı grafiğinden okunur.* Dosya, isim veya kavram yakınlığı
ölü olma kanıtı değildir. Silinecek **her sembol için ayrı ayrı** çağrılma
ölçümü yapılır.

*Karşılaştırma kapsamı kayıttan okunur, sabit listeden değil.* `golden`
alanları `("plan","frame","disk","template")` diye sabit listeden
karşılaştırıyordu; ölü dal silinince hem `KeyError` verdi hem de canlı
vakanın alanlarını (`uzay`, `kok`, `siklar`) **hiç görmedi**. Sabit liste,
kayda alan eklenip karşılaştırmanın onu atlamasıyla sessizce daralır ve
taban korumuş **görünür**.

Genel hâli: bir kapsam (neyin silindiği, neyin karşılaştırıldığı, neyin
tarandığı) elle yazılmış bir listeden okunuyorsa, o liste ile gerçek küme
ayrışır ve ayrışma **sessizdir**. Kapsam mümkün olan her yerde
**türetilmelidir** — çağrı grafiğinden, kaydın anahtarlarından, modülün
sabitlerinden. (`check_thresholds_independent`'ın motor sabitleri kümesi de
bu yüzden elle liste değil.)
Dosya, isim veya kavram yakınlığı ölü olma kanıtı değildir. Silinecek **her
sembol için ayrı ayrı** çağrılma ölçümü yapılır. 2026-08-17'de ölçülen şey
`apply_choice_plan`'ın kullanımıydı (üretimde 0/4) ama silinen şey onun
etrafındaki her şey oldu: `fit_choices` aynı dosyada, aynı "plan" sözlüğüyle
anılıyordu ve **canlı yolun şablon kabul testiydi** — `pick_template` onu
çağırıyor. Aynı turda `invariants.MOTOR_SABITLERI` ve `ESIK_ISTISNALARI` de
gitti; ikisi de ilgisiz bir kontrolün verisiydi ve kaybolduklarını ancak
`check_thresholds_independent` `NameError` verince fark ettik.

Üçünün de kaynağı kurtarılamadı: yedek yok, depo git değil, `.pyc`'ler silme
sonrası yeniden derilmişti. **Ölçtüğüm şey dalın uygulanmasıydı, sildiğim şey
dalın hesabıydı.**

Kural **onaylayan taraf için de geçerli**: bir silme listesini onaylamak,
içindeki her sembolün ayrı ölçüldüğünü göstermez. Onay listesinin kendisi bir
ölçüm değildir.

**K10 — Çekirdek fonksiyona dokunduysan regresyonu koş.**
`set_loc`, `_apply_text`, `height_for_label`, `grow_to_fit`, `fit_choices`,
`compose_slide` çekirdektir.

---

## 3. Kusurlar

### A — Ürün kırıkları (önce bunlar)

**A1. Sınav puanlanmıyor.** ~~5 senaryonun 1'i puanlı. Dosyada tek
`freePickOneIntr` var (`slideb`).~~ **DÜZELTİLDİ — mekanizma belgede yazandan
başkaydı (Faz 1, ölçüldü).**

Referansta **beş slaydın beşi de** `freePickOneIntr` taşıyor, sonuç slaydı da
yerinde. Kırık olan halka başkaydı: `quizMgr/quizLst/quiz/questionIdLst` **boş**,
ve `questionIdLst` kod tabanında bir kez bile geçmiyordu. Yani kayıt kaybolmuyordu
— hiç denenmiyordu. Story düzeyinde `lmsResultSlideG` de NULL, `trackMode="def"`.

Doğru biçim tahmin edilmedi, gerçek bir kurstan okundu (`test/0_duz_kopya.story`):
11 sorunun 11'i kayıtlı, guid **öznitelikte değil `<item>` metninde**, ve
`lmsResultSlideG == quiz.resultSldG`.

> **Puanlama bir zincirdir ve "soru var" onun yalnızca ilk halkası.**
> "Etkileşim var mı" diye soran bir kontrol o kursa *5/5 puanlı* der ve geçer.
> Üç halka ayrı ayrı kırılır, o yüzden ayrı ayrı sorulur: etkileşim · kayıt ·
> hedef.

Düzeltme `authoring.register_question`'da, **her iki soru yoluna da** bağlı
(klon ve gömülü tohum). Üretilen kurs artık 4/4 kayıtlı, `trackMode=result`.

**A2. İlk slayt boş.** `slide.xml` ("Intro Slide") hiç bestelenmemiş — ve
öğrencinin gördüğü ilk ekran o.

**Ölçüldü (Faz 1) — kontrol var, düzeltme KARAR BEKLİYOR.** Kusur builder'ın
ürettiğinde değil, `test/bos.story`'nin kendisinde: şablon dört sahne ve
14 boş slaytla geliyor (`Konular` 6, `Ana Menü` 1, `SINAV` 6, `ANKET` 1) ve
bunlar builder'ın kendi sahnelerinden ÖNCE duruyor. Builder'ın ürettiği
sahnelerde (`01_…`–`05_…`) sıfır boş slayt var.

Kontrol kuruldu: `ilk_slaydi_bos` — her sahnenin **ilk** slaydı bestelenmiş mi.
"Sahnenin tamamı boş" ölçüsü bunu kaçırırdı. Referansta 4 sahne düşüyor.

**DÜZELTİLDİ — sahne sıralaması** (`clone.promote_scenes`, builder'a bağlı).
Builder kendi sahnelerini `sceneLst`'in başına alıyor; kurs artık bestelenmiş
bir slaytla açılıyor. Hiçbir şey silinmiyor, devralınan sahneler arkaya düşüyor.

Elenen seçenekler ve gerekçeleri:

| seçenek | neden değil |
|---|---|
| `bos.story`'yi temizle | 14 slayt test araçlarının tuvali; `variety` 10, `coverage` 7, `themes_check` 6 tüketiyor — şablon küçülürse suit çöker |
| devralınan sahneleri sil | builder kullanıcının kendi dolu kursuna da koşulabiliyor ve orada "devralınan" ile "kullanıcının içeriği" ayrımı güvenilir yapılamıyor |
| ilk slaydı bestele (kapak) | kalan 13 boş slayt yerinde kalır, öğrenci menüden onlara gider |

**Menü de taşınıyor**, ve bu ayrıntıyı atlamak sessiz bir tutarsızlık üretirdi:
`toc/tocSceneEntry@refG` sahne guid'ine bağlı ve sırası `sceneLst`'i aynen
yansıtıyor (ölçüldü). Yalnızca `sceneLst` sıralansaydı dosya geçerli kalır,
kurs doğru sahneden açılır, ama oynatıcı menüsü eski sırayı gösterirdi.

Kontrol iki ölçüye ayrıldı: `kurs_ilk_bos` (kursun açıldığı ekran — ürün
kırığı) ve `ilk_slaydi_bos` (herhangi bir sahnenin ilki — menüden erişilebilir,
daha geniş).

> Bu ikisi geometrik değil. Mevcut ölçülerin hepsi konum/boyut/renk ölçüyor;
> hiçbiri "kurs işlevsel olarak eksiksiz mi" diye sormuyor. **Yeni bir kontrol
> ailesi gerekiyor: eksiksizlik.** Brief ne istedi, dosyada karşılığı var mı.

### B — Ölçüm ve kapsam hataları

**B1. Metin taşması — 24 adet.** Çoğu 13pt kart etiketi; kutu 38 birim,
gereken 49–68. Storyline kırpıyor, alt satırlar kesik görünüyor.
`check_text_fits` "taşma yok" diyor.
İlk ayrım: bu şekiller kontrolün ölçtüğü kümede mi, "bant dışı atlandı"
kümesinde mi? Formül hatası ile kapsam deliğini bu ayırır.
Formül adayları: satır kutusu (leading) puntoyla eşitlenmiş; `tIns`/`bIns`
payı sayılmıyor; kalibrasyon corpus'unda Türkçe diakritik yok.
Not: tek satırlık bir rakam bile kesiliyor — yani sorun sarma tahmininde değil,
tek satırın yüksekliğinde. Kesilme her zaman alttan, yani sistematik eksik tahmin.

**Faz 0 ölçümü — kapsam bu üç eksenin hepsinde dar, ve dosya ekseni ilk sırada:**
`check_text_fits` `_canary/variety.story`'yi okuyor, üretilmiş kursa hiç
bakmıyor. Sonra katman ekseni (33/38 taşma adayı katmanlarda), sonra bant.
Referansta bandın altındaki 10 yazının hepsi `Eyebrow` etiketi ve hiçbiri
taşmıyor — yani "bant dışı atlandı" kümesi orada taşma saklamıyor.
**Kısmen düzelmiş:** soru kökü sınıfı (5 örnek, `slide12`/`16`/`1a`/`1e`/`22`,
18pt kutu 117 gereken 182) daha yeni kodda kapanmış — aynı slaytta kutu
117 → 213 birime çıkıyor, metin uzunluğu benzerken. Faz 2'de B1'in kalan
kapsamı: katman kör noktası, `slidef`'teki yeni 11pt aday, diakritik kalibrasyonu.

**B1 KAPANMADI — yeni bulgu (2026-08-17): şık etiketleri canlı dalda taşıyor
ve bunu ölçen hiçbir kontrol yok.**

Ölü dal silindikten sonra `golden`'ın dondurmak üzere olduğu dosya ölçüldü
(temel + katman):

```
slidef.xml  13pt 'Sakin bir tonla dinlemeye devam ed'   139 > 97   <- şık etiketi
slidee.xml  16pt 'İŞİNİZE YARAMADIĞI İÇİN ÜZGÜNÜM'      114 > 98   <- geri bildirim katmanı
slidee.xml  16pt 'İŞİNİZE YARADIĞI İÇİN SEVİNDİM'        57 > 54
```

Kaynağı ayrıldı: `compose.fit_choices` maymun-yamayla sayıldı, **0 çağrı** ile
aynı şablon elle verildi, taşma **aynen durdu**. Yani kusur kabul testinde
değil, `compose_question_frame`'de — yeniden yazılan koddan gelmiyor.

**Koruma boşluğu B2'nin bir kat derini:** `check_question_frame` şık
kutularının **alt kenarının** taban altına sarkmadığını ölçüyor, kutunun
**içine metnin sığdığını** değil. `check_text_fits` ise yalnızca
`_canary/variety.story`'yi (içerik slaytları) okuyor. **Soru slaytlarında
metin sığmasını ölçen hiçbir şey yok** — geometri yeşil, metin taşıyor.

Aynı ölçümdeki ikinci sınıf: iki taşma **geri bildirim katmanlarında**.
**Düzeltme (kesit ölçüldü):** o iki taşma `slidee.xml`'de ve `slidee`
**tohum dosyasının kendi slaydı** — `bos.story`'nin 15 slaydı da 720×540 ve
`slidee` bunlardan biri. `add_question`'ın ürettiği slayt `slidef`, 1920×1080.
Yani üretilen slaytta taşma **bir** tane; diğer ikisi tohum içeriği. Üç
sanılmıştı.

#### KARE TURU (2026-08-17): taşma ARTEFAKT, ve iki eksen çarpanı da geçersiz

`test/_referans/b1_Kare.png` — üretimin kendi çıktısı (golden CANLI vakası),
Storyline Preview. Ölçüm `tools/goz_b1.py`'nin baş yorumundaki karar
kuralına karşı yapıldı, kural kareden **önce** yazılmıştı.

| ölçüm | model | kare | karar |
|---|---|---|---|
| kök satır sayısı | 5 | **4** | model fazla |
| şık 1 satır | 2 | **2** | ✓ |
| şık 2 satır | 1 | **1** | ✓ |
| şık 1 taşıyor mu | taşar (139>97) | **taşmıyor** | **ARTEFAKT** |

Turuncu kutu `y=348..385`, yazı bantları `(353–363)` ve `(373–382)` — ikisi
de kutunun içinde. Kutu büyümemiş (`autoFit="none"`, altı durumun altısı da
97 birim); gözle "daha yüksek" görünmesi yanılsamaydı, mor kutuyla **aynı**
38 px.

**Sahne 720×540, ve bu iki bağımsız yoldan çıkıyor:**

```
slayt karede 593x443 px, en/boy 1.339
   720x540  varsayarsa  0.8236 / 0.8204 px/birim   <- TUTARLI
  1920x1080 varsayarsa  0.3089 / 0.4102 px/birim   <- %33 celiskili
```

#### `MEASURED_HSCALE`/`MEASURED_VSCALE`'in 1920 satırı ölçüm değil, artefakt

Kanıt eski karelerde duruyordu. `preview_olcek720.png` ile
`preview_olcek1920.png` **aynı slayt bandını** veriyor: `x409..1237,
y259..822, 829×564 px`. 720 slaydı ile 1920 slaydı ekranda **aynı boyutta**
çiziliyor — çünkü ikisi de aynı story sahnesinde (`<sz w=720 h=540>`).

`kare_satir.py --uzay 1920` ise piksel/birim oranını **slaydın ilan ettiği**
genişlikten hesaplıyordu (`birim_px = genislik_px / 1920`). Sahne 720 iken
1920'ye bölmek, türetilen her "birim" değerini tam **1920/720 = 2.667** katı
büyütür. Ve tabloda yazan sayı da tam o:

```
MEASURED_HSCALE[1920] = 2.667  = 1920/720, KIL PAYI DEGIL, AYNEN
MEASURED_VSCALE[1920] = 2.990  = 2.667 x 1.121
```

`hscale`'in "işe yaramasının" sebebi de bu: **yatay hesap uzaydan
bağımsızdır** — kutu genişliği de karakter genişliği de aynı çarpanla
ölçeklenir, oran sadeleşir. 2.667 tam olarak dönüşüm katsayısı olduğu için
sessizce sadeleşti ve doğru cevap verdi. Dikeyde sadeleşme yok: **satır
yüksekliği puntoyla mutlaktır**, slaydın ilan ettiği koordinatla değil.

Artakalan `1.121` gerçek bir kalıntı ve DEVIR'de zaten "%12" diye
kayıtlıydı — "en az iddialı yere kondu" denmişti. Şimdi belli ki o 12'nin
altındaki 2.667 hiç ölçüm değildi.

**Tek sahne vardır: story'nin `<sz>`'i.** Farklı koordinat ilan eden bir
slayt orantılı ölçeklenir; yüzdeler korunur, ama puntodan türeyen
yükseklikler **story biriminde** hesaplanmalıdır.

#### DÜZELTME (2026-08-17): tek sahne, `shapes.Space`

`MEASURED_HSCALE`/`MEASURED_VSCALE` tabloları **silindi, düzeltilmedi** —
ölçüm değillerdi, yerlerine düzeltilmiş sayı yazmak aynı yanlış kategoriyi
sürdürürdü. Yerine `shapes.Space(slide_w, slide_h, stage_w, stage_h)` geldi;
`h` ve `v` **türetilmiş oranlar**, tabloda tutulan sabit değil (K17).

- `shapes.stage_size(pkg)` — `story/story.xml`'deki tek `<sz>`; tek yetkili.
- `shapes._space()` **çıplak float'ı reddeder.** Varsayılan sahne yok:
  varsayılan bırakılsaydı gözden kaçan her çağrı tutarlı bir deck varsayar
  ve karışık uzayda sessizce yanlış ölçeklenirdi — bu oturumda tam olarak
  bu oldu ve üç tur boyunca görünmedi.
- Bütün yüzde matematiği **sahne uzayında**: `pick_template_for_question`
  artık `package_slide_size` (ilk slaydın koordinatı, sıralamaya bağlı)
  yerine `package_stage` kullanıyor.
- Şablondan okunan genişlik sahne birimine **çevriliyor** (`_template_space`).

**Diskten ölçülen sonuç:**

| vaka | önce | sonra |
|---|---|---|
| CANLI: kök | %54.4 | **%36.4** |
| CANLI: en alt şık | %92.0 | **%78.4** |
| CANLI: taşma | 1 | **0** |
| uzun/orta: en alt şık | **%118.7** (slayt dışı) | **%92.0** (tabanda) |
| uzun/orta: taşma | 139 > 65 | 93 > 87 |

**Kalan iki iş, ikisi de yeni görünür oldu:**

1. ~~Çerçeve tabana inip sonra sessizce taşıyor.~~ **DÜZELTİLDİ** (aşağıda).

2. ~~1920×1080 sahne hiç ölçülmedi.~~ **ÖLÇÜLDÜ** (aşağıda).

#### 1920 SAHNE TURU (2026-08-17): çarpan kanonik, sahne matematiğe girmiyor

Turu kurarken **mevcut verinin iki hipotezi ayıramadığı** çıktı — bu, `Space.v`
yazılırken yapılmış ve fark edilmemiş bir seçimdi:

```
H_sahne     carpan = slide_h / stage_h      <- o günkü kod
H_kanonik   carpan = slide_h / 540
```

17 Ağustos kare turunda ölçülen tek vaka 1920 slayt / 720 sahne idi ve orada
**ikisi de 2.000** verir (`1080/540 = 1080/540`). Yani o ölçüm çarpanı
doğrulamış, **formülü doğrulamamıştı**. Ayrım yalnızca **tutarlı bir 1920
deck**'te görünür.

İki gerçek, tutarlı proje (`bos.story` 720/720, `0_duz_kopya.story`
1920/1920), aynı fikstür, altı sert satır, iki punto:

| | 13pt birim/punto | 21pt birim/punto |
|---|---|---|
| 720 sahne | 1.817 | 1.810 |
| 1920 sahne | 3.577 | 3.536 |
| **R** | **1.969** | **1.954** |

**R ≈ 2.00 → `H_kanonik`.** `H_sahne` (R≈1.00) ve çürütülmüş eski tablo
(R≈2.99) elendi. Dört sayımın dördü de 6 satır. İki punto %0.8 içinde
uyuşuyor — ilişki doğrusal; eski tablodaki açıklanmamış **3.28 → 3.13**
kayması da böylece kapandı, o kayma yanlış zeminin artefaktıymış.

`shapes.KANONIK = (720, 540)`. `Space.v = slide_h/540`, `.h = slide_w/720`;
**sahne matematiğe girmiyor.** Doğal sonucu: yükseklik
`punto × (slide_h/540) × leading` olunca slayt yüzdesi
`punto × leading / 540 × 100` olur — `slide_h` **sadeleşir**. Yüzdeler
uzaydan gerçekten bağımsız, ama sahneden değil, **540'lık kanonik
tasarımdan**. Ölçüldü: üç konfigürasyonda da 13pt tek satır = slaydın
%4.297'si.

`check_diagnoses`'in `uzun/3` regresyonu **kendiliğinden kapandı** — karar
kuralının `H_kanonik` dalında, karelere bakılmadan önce yazıldığı gibi.

**Yatay eksen bu turda ölçülmedi** (fikstürde etiketler sarmıyordu, yatay
kapasite sınanmadı); simetriyle türetildi ve `Space.h`'nin docstring'inde
öyle işaretli (K17).

#### Kare otomasyonu: yanlış kare üretmiyor, henüz üretemiyor

`tools/shoot_preview.py` yazıldı — `shoot.py` editör penceresini yakalıyordu,
oysa bütün kalibrasyon Preview'de yapıldı. İki ölçüm çıktı:

- **Preview ayrı pencere açmıyor**; aynı pencerenin başlığı
  `[X.story (Preview)]` oluyor. İlk sürüm "yeni pencere" arayıp 90 sn bekledi.
- **Üç guard etiketi doğruluyordu, göndergeyi değil.** Odak ✓, başlık
  "(Preview)" ✓, yakalama anında ön planda ✓ — üçü de geçti ve iki kare
  **kaydedildi**; içerikleri Storyline'ın çökme diyaloğuydu.

Dördüncü guard fikstürle **birlikte** tasarlandı: fikstür zeminine imza rengi
(`#E8F0D8`) konuyor, kare onu aramak zorunda, bulamazsa **dosya yazılmıyor**.
Beyaz olamaz — çökme diyaloğu da beyaz. Guard aynı gün üç kez iş gördü.

Çökmenin sebebi diskten üç hipotez elenerek daraltıldı (kopuk referans:
çalışan dosyada **daha fazla** var; `clear_slide`: kaynak slaytta şekil yok,
no-op; kaynak proje: aynı projeden üretilen B1_KARE elle sorunsuz açılıyor).
Kalan ve muhtemel sebep **açış yordamı**: `open_test.force_close()` Storyline'ı
öldürüyor, sonraki açılışta öldürülen oturumun çöküş raporu geliyor — otomasyon
kendi çöp izini ölçüyor. Bilinen sınır olarak koda yazıldı; kareler bu tur
**elle** alındı.

#### Çerçeve artık tabanda REDDEDİYOR — ve `golden` donduruldu

`compose_question_frame`'in şık yerleştirmesi şöyleydi:

```python
each = min(need, max((floor - band_top - gap * (n - 1)) / n, height * 0.06))
```

Yani taban puntoya inip **sığmadığını bildiği hâlde** kutuyu mevcuda kırpıyor,
metin de kutunun dışına taşıyordu. Geometri taban içinde kaldığı için hiçbir
yapısal kontrol bağırmıyordu — taşan şey **metindi** ve onu ölçen yoktu.

**Çağrı yolu önce okundu** (kararı belirledi):

```
builder -> pick_template_for_question   (sablon dongusu BURADA)
        -> add_question(secilmis TEK sablon) -> compose_question_frame
        except StoryError -> menu slaydi + gerekce rapora
```

`add_question` şablon denemiyor. Yani red başka şablona **dönmüyor**, üretimi
de **durdurmuyor**: mevcut ve tasarlanmış bozulma yoluna düşüyor. Red doğru
cevap.

`ChoiceLabelsTooLong(StoryError)` eklendi — **dördüncü teşhis**. Ayrı durması
aynı sebeple: farklı iş gerektiriyor. "Şablon dar" → kataloğa şablon ekle;
"kök çerçeveyi yedi" → kökü kısalt; **"etiket sığmıyor" → şıkkın kendisini
kısalt**. `builder` bunu `diagnosis: "etiket"` diye ayrı sayıyor.

```
red uzun/orta: 2 sik taban puntoda (13pt) bile sigmiyor: her yuvaya %8.04
kaliyor, en uzun etiket %9.39 istiyor (bant %74.3..%92.0, bosluk %1.6).
Etiketleri kisaltin — sablon eklemek bu durumu cozmez.
```

**`golden` donduruldu.** CANLI vakası 0 taşma, en alt şık %78.4. Tabanın
koruduğu kanıtlandı: kayda **0.9 puanlık** kasıtlı kayma verildi, bağırdı,
geri yüklendi.

Aynı turda `golden`'ın karşılaştırması da düzeltildi: alanlar
`("plan","frame","disk","template")` diye **sabit listeden** okunuyordu — ölü
dal vakalarının anahtarları. Dal silinince hem `KeyError` verdi hem de canlı
vakanın alanlarını (`uzay`, `kok`, `siklar`) **hiç görmedi**. Artık kayıttaki
tüm alanlar karşılaştırılıyor. Sabit liste, kapsamın sessizce daralmasının en
ucuz yolu.

**Açık kalan K12:** `fit_choices` "sığar" derken çerçeve sığdıramıyor — iki
yer aynı soruyu ayrı hesaplıyor (biri `layout_text_height` + şablon genişliği,
diğeri `height_for_label` + içerik bandı + kendi stem yerleşimi). Red sessizliği
bitirdi ama ayrışmayı bitirmedi.

Ve ayrışmanın **kullanıcıya dönük** sonucu var: ikisi aynı soruyu ayrı
hesapladığı sürece **iki farklı gerekçe** üretebilir — `pick_template` "şu
şablon sığmadı" derken çerçeve "etiket sığmıyor" diyebilir, ya da tersi.
Rapor iki gerekçe gösterdiğinde kullanıcı hangisine göre iş yapacağını
bilemez, ve teşhisin bütün değeri "ne yapmalıyım"ı söylemesinden geliyor.

**DOĞRULANDI, kanonik düzeltmeden SONRA (2026-08-17 kapanış).** Kayıt o
düzeltmeden önce yazılmıştı ve iki taraf da o uzay matematiğini kullanıyor,
yani bayatlamış olabilirdi (`GROWTH_LIMIT` iki kez geçersizleşmişti). İki
vaka koşuldu — tek vaka rastlantı olurdu:

```
uzun/orta   fit_choices ok=True   cerceve REDDETTI    -> AYRISIYOR
kisa/kisa   fit_choices ok=True   cerceve YERLESTIRDI -> uyusuyor
```

Ayrışma **koşula bağlı**, yani gerçek.

**GİRİŞ SORUSU — ve "hangisini diğerine uyduralım" DEĞİL.** Ayrışma hangi
tarafın doğru olduğunu söylemiyor. Üç ihtimal var ve ayrılmadan düzeltme
tasarlanamaz:

1. `fit_choices` fazla iyimser (kabul etmemesi gerekeni ediyor),
2. çerçeve fazla katı (yerleştirebileceğini reddediyor),
3. ikisi **farklı şey** ölçüyor (biri şablon genişliği + `layout_text_height`,
   diğeri içerik bandı + `height_for_label` + kendi kök yerleşimi).

B3'ün dersi burada da geçerli: gerçek kusur envanterde değil, **kullanıcının
gördüğü yerde**. Ölçülecek ilk şey, `uzun/orta` vakasında o şıkların gerçekten
sığıp sığmadığı — modelin iddiası değil, karedeki hâli.

Sıraya gireceği yer: **POOL üçlüsünden sonra** (POOL bitti; sıra bu blokta).

#### Şık sırası KARARSIZDI — `set()` tek satırı, ve `golden` donduruldu

`GROWTH_LIMIT` düzeltmesinden sonra `golden` kırmızıya döndü. Sapma yalnızca
**sıra** görünüyordu, koordinatlar aynıydı — kozmetik sanılabilirdi. Ölçüldü
(aynı girdi, beş koşu):

```
tur 0: USTTE 'Sakin'   tur 1: USTTE 'Ayni'   tur 2: USTTE 'Ayni'
tur 3: USTTE 'Sakin'   tur 4: USTTE 'Sakin'
```

**Aynı kurs iki kez üretildiğinde şıklar farklı yerlere iniyordu.** Sebep tek
satır (`authoring.py:190`):

```python
choice_ids = set(_choice_shape_guids(intr))   # sira burada kayboluyor
...
choice_guids=list(choice_ids)                 # ve cerceveye SIRA olarak gidiyor
```

`list(set)` dizelerin hash rastgeleleştirmesine (`PYTHONHASHSEED`) düşüyor ve
o **süreç başına** değişiyor; `compose_question_frame` de `enumerate(choices)`
ile index 0'ı en üste koyuyor.

Puanlama tutarlı kalıyordu — her şekil kendi kimliğini taşır — o yüzden
hiçbir yapısal kontrol bağırmadı. Ama **sıra içeriğin parçası**: "hangisi önce
gelir", "en uygun olanı seç" gibi sorularda yazarın verdiği düzen anlamlıdır.

Düzeltme K12: sıra **tek yerden** (`_choice_shape_guids`, belge sırası =
yazarın sırası); küme yalnızca üyelik testi için, ve sıra ondan türetilmiyor.
İki sırayı "senkron tutmak" ayrışmayı ertelemek olurdu.

**Kapsam boşluğu da kapandı.** `check_question_frame` dikdörtgenlerin
*nerede* olduğunu ölçüyordu, hangi *etiketin* nerede olduğunu değil — kusur
ancak iki kare gözle karşılaştırılınca göründü. `_sik_sirasi()` eklendi
(guid sırası değil, **y koordinatı** sırası — öğrencinin gördüğü) ve üçüncü
bir kanarya: iki şıkkın dikdörtgenleri kasten takas ediliyor, etiketler
yerinde kalıyor. Kanarya yaşıyor.

**Kontrolün sınırı yazılı:** kararsız bir sırayı *her koşuda* yakalamaz — iki
şıkta rastgele sıra zaten yarısında doğru çıkar. Sabit-ama-yanlış sırayı her
zaman yakalar, kararsızı olasılıkla; kesin yakalamak süreç **dışında** tekrar
ister (`PYTHONHASHSEED` süreç başına sabit).

`golden` üç ayrı süreçte aynı çıktı, sonra donduruldu.

#### B1-kuyruk kök nedeni: yüzde, metin için uzaydan bağımsız DEĞİL

Kapsam kapatılınca vaka matrisine `uzun/orta` eklendi ve kusur üredi. Zincir:

| adım | uzay | sonuç |
|---|---|---|
| `package_slide_size(bos.story)` | — | **(720, 540)** — projenin kendi slaytları |
| `question_frame(stem, slide)` | 720 | `stem_h = %58.31`, şıklara `area_h = %22.89` |
| `fit_choices(..., 605 birim)` | 720 | **ok=True**, 13pt, toplam %19.6 ≤ %22.9 |
| `add_question` gömülü tohumu koyar | — | slayt **1920×1080** doğuyor |
| `compose_question_frame` | 1920 | kök **941 birim = %87.1**, şıklara 65 birim kalıyor |
| sonuç | | en alt şık **%118.7**, etiket **139 > 65** |

Sebep bu oturumda ölçülen eksen ayrımının doğrudan sonucu:

```
DIKEY carpan    720 -> 1.000    1920 -> 2.990     orani 2.990
SLAYT yuksekligi 540 -> 1080                      orani 2.000
                                        metin/slayt = 1.495
```

**Aynı metin 1920 uzayında slaydın 1.495 katı kadar yer kaplıyor.** Öngörü:
`%58.31 × 1.495 = %87.2`. Diskte ölçülen: **%87.1**. Fark %0.1.

Yani `question_frame`/`fit_choices` yüzdeleri doğru hesaplıyor — **yanlış
uzayda**. Yüzde, geometri için uzaydan bağımsız ama **metin için değil**,
çünkü satır adımı slayt yüksekliğiyle aynı oranda ölçeklenmiyor.

**Ölü dalı bunun için silmiştik.** Ölü daldaki kusur #2 "yüzde plan yanlış
uzaya uygulanıyor"du ve elle yazılmış `(720.0, 540.0)` yüzündendi. Canlı
dalda aynı kusur var, ama elle yazılmış sabitten değil: `package_slide_size`
**projenin** boyutunu veriyor, üretilen slayt ise **gömülü tohumun**
boyutunda doğuyor. İkisi ayrı ve hiçbir şey bunu söylemiyordu.

#### B2 geri açıldı: kusur ÜREMİYOR değil, VAKA YOKMUŞ

B2 "şıklar %139–156" diye açılmış, Faz 2'de "kusur üremiyor, koruma boşluğu
gerçek" diye kapanmıştı. `uzun/orta` vakası **%118.7** üretiyor — yani kusur
üretilebiliyor. `check_question_frame`'in taban kapısı zaten doğru çalışıyordu
ve vaka eklenir eklenmez bağırdı; eksik olan koruma değil, **vakaydı**.

Matris deliği kendi başına bir ders: üç vaka (`kisa/kisa`, `kisa/uzun`,
`uzun/uzun`) iki ekseni tek tek geziyordu ama **kesişimi** gezmiyordu. Kısa
etiket kutuya sığar; uzun etiket kutuyu **büyütür** (99 → 290 birim);
`uzun/uzun` gerekçesiyle reddedilir. Arada kalan boy ne sığıyor ne büyütüyor —
ve üretimde görülen vaka tam o boydaydı.

**B2. 12 şekil slaydın dışında.** ~~`slide7`'de şıklar %139–156.~~
**ÖLÇÜLDÜ (Faz 2) — kusur ÜREMİYOR, koruma boşluğu GERÇEK.**

Dondurulmuş referansta ve üretilen kursta şıkların alt kenarı en fazla
**%88.8** — hepsi içeride. %139–156 artık elimizde olmayan, eski kodla
üretilmiş bir dosyadan. Zorlayıcı içerikle sınandı: en kötü vaka %92.0'da
durdu, daha ağırı `NoTemplateFits` ile **gerekçeli reddedildi** — sözleşmenin
son basamağı çalışıyor.

Asıl bulgu K8'in ince hali ve DEVIR'in tahmininden farklı. `builder`
`pick_template_for_question`'ı **her soruda çağırıyor** — bir çağrı sayacı
"bağlı" der ve yanıltır. Ölçüldü (üretilen kurs, 4 soru):

| | çağrı |
|---|---|
| `pick_template_for_question` | 4 |
| `compose_question_frame` | **4** ← üretimin kullandığı dal |
| `apply_choice_plan` | **0** ← sınanan dal |

Plan her soruda **hesaplanıp atılıyor**: gömülü tohum yolunda çerçeve kendi
yerleşimini kuruyor. Ve invaryant kapsamı **tam ters**: `check_fit_choices`,
`check_plan_applied`, `golden` ve `coverage` hep ölü dalı koruyor; canlı dalı
koruyan hiçbir şey yoktu.

Çare: `invariants.check_question_frame` — canlı dalı sınar, **dal denetimi**
taşır (üretim plan dalına geçerse sessizce geçmek yerine bağırır) ve gömülü
bir kanaryası vardır. `EXPECTED_FRAME_FLOOR` bilerek ikinci kez yazılı:
ilk yazılışında `compose.FLOOR` okunuyordu ve kasten bozmada **sessiz geçti**
— taban düşünce ölçünün iki yanı birlikte kaydı. Aynı ders dosyada
`EXPECTED_SIZE_FLOOR` için zaten yazılıydı ve yine tekrarlandı.
Ayrıca `look.py` slayt dışını sessizce kırpıyor — aracın dördüncü yalanı.
Çare: viewBox'ı slayt sınırının biraz dışını kapsayacak şekilde genişletip
taşan öğeleri kırmızıyla göstermek.

**B3. 25 slaytta kopuk tetikleyici.** Editörde `unassigned` görünüyor; hedefi
`previous slide`, bağlı olduğu nesne slaytta yok. Donörden klonlanmış, hedef
projede karşılığı olmayan referans — `pic`/`assetG` sorununun tetikleyici
tarafındaki hali. **Referans bütünlüğü hiç kontrol edilmiyor.**

**B3 — KAPANDI (2026-08-17), ama iddia edildiği gibi değil.**

*Öncül sınandı ve düştü.* "25 slaytta kopuk tetikleyici" sayısı gerçek ama
**kusura özgü değil**: elle yapılmış bir kursta 37 tane var ve editörde
**sıfır** `unassigned`; bizim ürettiğimizde 30 var ve gönder düğmesi
çalışmıyordu. Ters orantı (K19).

*Gerçek kusur, editörde tek bakışla ayrıldı.* İçerik slaytları tohumdan
devralınan **ölü bir Submit Button tetikleyicisi** taşıyor:

```
Submit Button / When the user clicks submit / Submit [unassigned]
```

Kaynak `bos.story`'nin 5 içerik slaydı; klonlandıkça çoğalıyor (5 → 17).

*Düzeltme: `compose.drop_orphan_submit`.* Etkileşimi olmayan slayttan gönder
tetikleyicisi **silinir** — onarılacak hedef yok. Ölçüldü:

```
aracin URETTIGI slaytlarda : 12  ->  0
tohumdan devralinanlarda   :  5  ->  5   (kullanicinin kendi slaytlari)
```

*İki nitelik, iki farklı doğru cevap*, ayırt edici "slaytta etkileşim var mı":
soru slaydında **onar** (`adapt_seeded_slide` 1b), içerik slaydında **sil**.
Ters yönler: onarımı silmeye çevirmek soruyu gönderilemez yapardı, silmeyi
onarıma çevirmek olmayan hedefe bağlamak olurdu. Doğru biçim ölçüldü — elle
yapılmış kursta 13/13 `submitG` kendi etkileşimine çözülüyor, etkileşimsiz
slaytta hiç yok.

*1b KOŞMUYOR ve öyle işaretli.* `pick_template_for_question` her zaman gömülü
tohumu seçiyor (`0_duz_kopya.story` içinde bile) ve o tohumda `submitG` yok
— onarılacak bağlantı hiç oluşmuyor, kanarya **kurulamıyor**. Silinmedi
çünkü sözleşme ölçülmüş bir biçime dayanıyor ve proje şablonu yolu açılırsa
gerekli olacak; ama "korunuyor" da denmiyor: koşmayan dal sınanmamış daldır.

*Yan soru kapandı:* ürettiğimiz soru slaytlarında gönder tetikleyicisi hiç
yok, elle yapılmışta 13/13 var. **Preview'da doğrulandı: geri bildirim
geliyor** — oynatıcı kendi düğmesiyle hallediyor, kusur değil.

*Yolda iki hipotez çürüdü ve kaydı duruyor:* `copiedG` köken damgası (tek
kesik örnekten atlanan sonuç), ve sıfır-GUID filtresi (K18). Ayrıca düzeltme
**önce yanlış yola** yazıldı — soru yoluna, oysa kusur içerik slaytlarındaydı;
doğrulama ölçümü yakaladı (`COZULUYOR 0 / KOPUK 0 / ETKILESIMSIZ 17`).

**B4. Kutu çakışması.** `slided`'de `Subtitle` ile `Eyebrow` üst üste.
Bu sınıf bir kez düzeltildi (`_distribute` bandı sınır değil öneri gibi
davranıyordu) ama çakışma invaryantı dar kesitte koşuyor olabilir.

**B4 — ENVANTER ÇIKARILDI, DONDURULDU (2026-08-18).** Düzeltme yapılmadı;
ilerlemesini engelleyen şey ölçüm altyapısı. **Üç ayrı bulgu:**

*1. Kesit körlüğü — ölçüldü, kalibrasyondan bağımsız, düzeltilebilir.*
`check_no_overlap` yalnızca `variety.story` + `_rubrik/{iyi,kotu,orta}` tarıyor
ve yalnızca `root.find("shapeLst")` — **temel katman**. Taranmayan: üretilmiş
kurs, `referans.story`, ve `sldLayerLst` (her dosyada 3 slaytta katman var).

*2. Ölçü körlüğü — kutu sayıyor, mürekkep nerede saymıyor.* B1 ölçtü:
Storyline **kırpmıyor**, taşan metin kutunun dışına çıkıp komşusuna biniyor.
Yani kutular çakışmasa da metin çakışabilir. Kanıt aynı turda çıktı:

```
referans.story   KUTU cakismasi 0   METIN cakismasi 10   (hepsi KATMANLARDA)
```

İki bağımsız körlük aynı yerde: ne kesit kapsıyor, ne ölçü o sınıfı ölçüyor.
**Ama o 10 sayı da modelin iddiası** ve doğrulanmadı — B1'de 24/24 artefakt
çıkmıştı; aynı şüpheyle bakılacak.

*3. Kalibrasyon tıkandı — ve bu `.h` + `force_close` işine bağlı.*
`0_duz_kopya`'daki 42 kutu çakışması sınıflandırıldı (veriden, ad koymadan):

```
10  dikey ortusme < 10 birim (kenar seridi, ow 100-1162 iken oh 1-8)
 8  tam kapsama
23  gercek kismi ortusme adayi (18'i textBox+textBox)
```

23'ün **18'i ölçülemedi**: puntolar `CALIBRATED_RANGE` (13–38) dışında (8pt,
9pt). Yani **gürültü oranı sorusu cevapsız** — asıl soru buydu (K19).

**Basılan `%0 gürültü oranı` GEÇERSİZ SAYILDI** ve sebebi kayda değer:
ölçülemeyen 18 vaka orana katılmıştı, yani ölçüm noktasının kapsamadığı
bölge **sıfır olarak raporlanıyordu**. `density_scale`'in `finally`
bloğuyla aynı sınıf — **K18'in yeni bir örneği**.

*`slided` — tarife uyan vaka BULUNAMADI.* B4 "`slided`'de `Subtitle` ile
`Eyebrow` üst üste" diyor. `slided.xml` `0_duz_kopya.story` içinde bulundu
("Tıklamadan Önce 3 Kural", 1920×1080) ve iki kutu çakışması taşıyor (13 ve
46 birim; mürekkep de 21 birim örtüşüyor) — **ama o adlar orada yok**, hepsi
`Text Box`. Kayıt başka bir dosyayı anlatıyor olabilir ve o dosya elimizde
değil. Doğrusu: *tarife uyan vaka doğrulanamadı; benzer bir çakışma
kullanıcının kendi kursunda var.* **Aracın çıktısında (`uretilmis.story`)
hem kutu hem metin çakışması 0.**

**Açılması gereken:** `force_close` temizliği + `.h` kare turu. Kuyrukta
duruyordu; bugün bir bloğu **bloke ettiği ölçüldü** — önceliği yükseldi.

**B5. Tema geri bildirim katmanlarına ulaşmıyor.** Doğru/yanlış katmanlarında
yeşil metin var — hiçbir temanın rengi değil, donörden kaldığı gibi.
`themes_check` ve `contrast` bu kesiti taramıyor. Yeşil-üstü-krem muhtemelen
WCAG AA'yı geçmiyor.

### C — Tasarım eksikleri (en son)

**B5 — KESİT AÇILDI, ÖLÇÜ HENÜZ GÜVENİLİR DEĞİL (2026-08-18).**

*Tarif düzeltildi (K20).* "Tema geri bildirim katmanlarına ulaşmıyor" deniyordu.
Ölçüldü — üretilen kursun katmanlarında:

```
#FFFFFF (18)   <- temaya ulasiyor
#92D050 (1)  #FF0000 (1)   <- donorden kalmis
```

**18/20 ulaşıyor.** Kusur gerçek ama tarifin onda biri kadar.

*Kesit körlüğü ölçüldü ve üç kontrolde ortak:* `themes_check`, `contrast` ve
`check_no_overlap` — üçü de `sldLayerLst`'i atlıyordu.

*`contrast.audit` katmanlara açıldı.* Yeni mekanizma değil, mevcut `_behind()`
genişletildi. `_kaplar()` her katman için yığını **`temel + katman`** olarak
veriyor (katman metni temel slaydın üstüne çizilir; katmanı tek başına
taramak zemini beyaz sanardı) ve üçüncü bir dönüş değeriyle temel şekillerin
**iki kez ölçülmesini** önlüyor.

*Kontrast aralık olarak raporlanıyor, tek sayı değil.* Zemin belirsizse
(`en_iyi >= eşik > en_kötü`) bulgu `belirsiz` işaretleniyor — ölçülemeyeni
ölçülmüş gibi göstermemek için (K18).

**AMA ÖLÇÜ HENÜZ KULLANILAMAZ.** Kesit açılır açılmaz üretilen kursta 12
"bulgu" çıktı ve hepsi **`#FFFFFF üzerine #FFFFFF, oran 1.00`** — yani aracın
kendi körlüğü. `_paints`'in kendi yorumu bu tuzağı zaten belgeliyordu
("araç kendi körlüğünü kontrast hatası diye raporladı") ve ikinci kez oldu.

Zemin çözümünün iki ölçülmüş boşluğu:

```
gradOvrlyFill   overlayFillType="None"  -> ortu KAPALI, gercekten boyamiyor
                (yani _paints'in bos donmesi DOGRU; sorun baska yerde)
schemeClr       ELLE kursta 34 sekil YALNIZCA schemeClr -> tema cozumu yok
```

**Hiçbir katman bulgusu, zemin çözümü oturmadan güvenilir değil.** Elle
yapılmış kursta çözülen zeminler gerçek renk veriyor (`#BA2D2D` üzerine
`#444182`, oran 1.51) — yani mekanizma çalışıyor, eksik olan bazı dolgu
sınıfları.

*Tutarlılık düzeltmesi (2 donör rengini temaya bağlamak) BİLEREK
YAPILMADI:* yeni renklerin kontrastı da bilinmiyor, ve zemin ölçülmeden
`#FF0000`'ı tema kırmızısıyla değiştirmek yine AA'yı geçmeyen bir şey
üretebilir. Düzeltme zemin çözümünden sonra.

**B5 — DÜĞÜM YENİDEN ADLANDIRILDI, ARİTMETİK YAZILDI, DOĞRULANMADI
(2026-08-18).**

*Düğüm `overlayFillType` DEĞİLMİŞ.* Üç fikstür denemesi bunu bulamadı; tek
korpus taraması buldu. Bütün örtü durakları şöyle:

```xml
<clr><schemeClr val="accent1"/><tint val="66000"/><satMod val="160000"/></clr>
```

`Default` de `None` de aynı yapıyı taşıyor. Tıkayan şey örtünün açık/kapalı
olması değil, **durak renklerinin dönüşüm taşıması**. Bu, B5'i "ölçülemeyen
semantik soru"dan **"uygulanabilir kod boşluğu"na** çevirdi.

*Aritmetik yazıldı:* `tint`/`shade` RGB'de doğrusal karışım,
`lumMod`/`lumOff`/`satMod` **HSL**'de (RGB'de uygulamak yanlış sonuç verir),
dönüşümler **belgedeki sırada**. Bilinmeyen dönüşüm çözümü **reddettirir** —
"bilmediğimi atla" değil, "bilmediğim varsa ölçme".

*İki özdüzeltme, ikisi de ölçümle döndü:*

- **`_scheme_rengi` dönüşüm kontrolünü yanlış yere koydu.** `schemeClr`'ın
  ÇOCUKLARINA baktı, oysa `tint`/`shade`/`satMod` `<clr>` içinde KARDEŞ.
  Kontrol hiç tetiklenmedi, ham slot rengi döndü. Ölçüldü: `solidFill`+`tint`
  25, `+shade` 25, `+alpha` 48, `gradFill`+ağır zincir 66. Düzeltince
  `olculemedi` 165→180, `IHLAL` 36→31 — yani **15 vaka yanlış renkle
  çözülüyordu, 5'i ihlal olarak raporlanıyordu.** Kullanıcı bunu yazmadan
  önce uyarmıştı; uyarıyı duymak, kontrolü doğru yere koymayı garanti etmiyor
  (aynı sınıf: `submitG` düzeltmesinin yanlış yola yazılması).
- **`alpha`: yorum ile kod çelişiyordu.** Yorum "ayrı kanalda taşınıyor,
  atlanır" diyor, kod reddediyordu. `preview._alpha_of` onu zaten okuyor.
  Düzeltince 32 vaka boşuna reddedilmekten çıktı (180→172).

*BAĞIMSIZ DOĞRULAMA ALINAMADI, ve sebebi ölçüldü.* Palete eşitlik kendi
formülü kendisiyle doğrular; gerçek kontrol karedeki pikselle
karşılaştırmaktır. Uygun vaka arandı (düz `solidFill`, tek dönüşüm, üzerinde
metin yok, üstünde şekil yok, yeterince büyük) ve **sıfır** çıktı. Sebep:

```
donusum=tint    zincir= bG < btn < shapeLst < state   25
donusum=shade   zincir= bG < btn < shapeLst < state   25
```

Tek dönüşümlü dolguların **hepsi buton DURUMLARININ içinde** (hover, down,
visited) — statik Preview karesinde çizilmiyorlar. Doğrulama, üzerine gelme
etkileşimi gerektirir ve o ayrı bir tur.

Aritmetiğin zemini **ECMA-376 tanımı**, ölçüm değil — kodda öyle işaretli.
Storyline'ın spec'i nasıl uyguladığı ayrı soru (`<sz>`/`<sldSz>` boşluğunun
aynısı).

*`contrast.audit(katmanlar=True)` HÂLÂ KAPALI.* Açmak aritmetiğin doğru
olduğunu bilmeyi gerektiriyor ve bilinmiyor. Üretilen kursta `olculemedi`
56'da sabit; oradaki tıkanma `Default` örtülerinin durakları ve onlar da
aynı dönüşümleri taşıyor.

*BUTON DURUMU TURU icin fare yetenegi OLCULDU (2026-08-18), planlanmadan
once.* Aritmetigin dogrulanmasi bir buton durumunun (hover) karesini
gerektiriyor ve statik yakalama yetmiyor. Otomasyonun fare hareketi yapip
yapamadigi bilinmiyordu; olculdu:

```
imlec tasima  : CALISIYOR (SetCursorPos + GetCursorPos ile dogrulandi)
mouse_event   : var        SendInput: var
```

Yani yol acik. **Hala olculmemis olan**, hover'in Preview'da durumu
gercekten degistirip degistirmedigi ve hedefin ekranda konumlandirilip
konumlandirilamayacagi -- ikisi de o turun ilk adimi olmali, yoksa "tur
tukendi" dongusu tekrarlar (bu oturumda iki kez oldu).

*Otomasyon borcu kapandı ve KANITLANDI:* `force_close` artık `WM_CLOSE` ile
nazik kapatıp pencerenin gittiğini doğruluyor (sert öldürme, öldürülen
oturumun çöküş raporunu bir sonraki açılışa taşıyordu), ve kare **imza rengi
görünene kadar** bekliyor (sabit `settle` yükleme zeminini kaydediyordu).
`B1_KARE.story` elle müdahale olmadan yakalandı. Bu borç iki blokta
ilerlemeyi durdurmuştu.

**C1. Tipografik ölçek yok.** 16 farklı punto: 11,13,14,15,16,17,18,20,21,23,
29,33,37,38,42,48. Ölçek olsa 6–8 basamak olurdu. Her slaytta ayrı karar
verilmiş demek — `density_scale` ve `fit_choices` bağımsız çalışıyor.
**Bu tek bulgu C2 ve C4'ü de açıklıyor.** Önce bu çözülmeli.

**C1 — KAPANDI (2026-08-18): tek yol, ölçülmüş, ve ölçüsü değiştirildi.**

*Tarif çürümüştü, kapsam daralmıştı* (envanter, yukarıda): 16 punto → 10,
altı yol → **tek yol**, ve kaçakların hepsi geri bildirim katmanlarında.

*Kusur:* `compose_feedback_layers` puntoyu **hiç ayarlamıyordu** — dolgu,
konum ve metin yazıyor, boyut gömülü tohumdan miras kalıyordu.

*Düzeltme:* mevcut punto merdivene **snap** ediliyor. **Rol atanmadı** —
"panel body olsun" demek bir tasarım kararı olur ve tohumun kurduğu
hiyerarşiyi ezerdi; snap yalnızca "ölçeğin içine al" der, ki kusurun tanımı
da buydu. Hedefler önceden ölçüldü: `14→13`, `16→17`, `18→17` — üçü de
değişiyor, yani düzeltme sessiz kalmıyor.

*İlk sürüm YARIM İŞ yaptı ve ölçüm yakaladı.* `_s is shape` kimlik
karşılaştırması `Rectangle`'ları düzeltip **`Button`'lara hiç dokunmadı**:
butonun metni **altı durum gövdesinde** yaşıyor ve hiçbiri dıştaki `<btn>`
ile aynı nesne değil. `_restyle` bu yüzden ata zinciri yürüyor; aynı yol
kullanılınca sekizi de düzeldi.

```
merdiven disi YAZI:  20  ->  4     (%24 -> %5)
BIZIM URETTIGIMIZ :   16 ->  0
TOHUMDAN          :    4 ->  4     <- kullanicinin slaytlari, DOKUNULMADI
```

Tohum ayrımı `submitG` ve `drop_orphan_submit` kararlarının aynısı.

*ÖLÇÜ DEĞİŞTİRİLDİ, yoksa kazanç korunmazdı.* `inventory.punto_olcegi`
kaç **çeşit** punto olduğunu sayıyordu ve o sayı kusura özgü değil (K21:
elle kursta 13 çeşit, 332/332 merdiven dışı, sorun yok). Yerine
`punto_merdiven_disi` geldi: ölçeğe uymayan yazı sayısı, **kaynağına göre
ayrılmış** (`{'bizim': 0, 'devralinan': 4}`).

**Bilinen sınır:** yeni ölçünün "bizim / devralınan" ayrımı `bos.story`
karşılaştırmasına dayanıyor, yani bizim üretim hattımıza özgü. Başka bir
kurs ölçüldüğünde (elle yapılmış gibi) her şey "bizim" görünür — o sayı
üretim hattı dışında yorumlanmamalı.

**C2. Boşluk ritmi yok.** `slide10` %37, `slidef` %30, `slide4`/`slide8` %29 —
ama `slideb`, `slided`, `slide6` %0–1.

**C3. Hizalama tekeli.** Konumlu şekillerin %56'sı tek bir x'ten (%8) başlıyor.

**C4 — KAPANDI (2026-08-19): kusur değil, olgu (K21).**

*Ön adım:* `ikiz_slayt` C3'ün kopyası mı? **Değil.** `silhouette.grid` bir
doluluk ızgarası kuruyor (metinliye 1.0, metinsize 0.55) ve `flip` ile ayna
simetrisini de karşılaştırıyor. Bileşenleri: x konumu (C3'ün ölçtüğü), **y
konumu, şekil boyutu, alan kaplama, mürekkep ağırlığı, ayna simetrisi**
(C3'ün ölçmediği). C3 düzeltmesinin metriği hareket ettirmesi (13→7) x
bileşeninden; kalanı bağımsız.

*Normalize karşılaştırma (K23):* ikiz sayısı `n(n-1)/2` ile büyür, ham sayı
karşılaştırması yanıltıcı — 26/27 slayt ile 7/16 slayt aynı ölçekte değil.
Olası çift sayısına normalize edilince:

| bileşen | BİZİM | ELLE | |
|---|---|---|---|
| tam ızgara | %5.8 | %7.4 | yakın |
| satır (y) | %15.8 | %17.9 | yakın |
| sütun (x) | %21.7 | %19.7 | yakın |

**Maskelenmiş yığılma yok.** Üç bileşenin üçünde de elle yapılmış kursla aynı
bantta; ikisinde daha iyiyiz. `sutun(x)` 2 puan yüksek — C3'ün alanı ve
oradan kazanç zaten alındı.

Tarif *"18 slaydın 16 çifti aynı silüette"* diyordu; ham sayı bugün 7, ve
insan ürününde 26. **K21: metrik kötü değer veriyor ama aynı alanda çalışan
bir insan ürününde daha da kötü — kusur değil, olgu.**

**C2 — KAPANDI (2026-08-18): üç ayrı olgu, biri kasıtlı, biri kapsam dışı.**

*Tarif "boşluk ritmi yok" diyordu ve DOĞRUYDU* — ama önce yanlış ölçüyle
çürütülmeye kalkıldı (K23). Doğru ölçü, adı zaten ritim olan `deadband`:

```
olu bant   BIZIM ortanca 21, aralik 0..56    ELLE ortanca 0, aralik 0..7
```

Elle yapılmış kursta içerik bandında ölü boşluk **yok**. Fark gerçek ve büyük.
"İçerik azlığı" açıklaması da çürüdü: elle kursta da az öğeli slayt var ama
ölü bandı yok — öğeler bandı **dağıtıyor**, bizimkiler yığılıyor.

*Düzen kırılımı üç ayrı olgu gösterdi:*

| düzen | ölü bant | yorum |
|---|---|---|
| `section` | %38–56 | **KASITLI** — ayraç slaydı, kodun kendi yorumu: *"A divider earns its slide by being nearly empty"*. Metrik kötü değer veriyor ama tasarım öyle istiyor (K21'in kardeşi). Varyantsız hâlinde de %48. |
| `content` | %31–43 | **gerçek boşluk**, sebebi ölçülü: `density_scale` 1.7'de tavana dayanıyor, `MAX_TYPE_SCALE` atıl, sınırlayan merdiven kuantumu + `MIN_LINE_CHARS`. Punto büyütme yolu **tükendi**; kalan yol slayt başına daha çok öğe = **içerik üretimi**, bu listenin kapsamı dışında. |
| `bullets` | %8–12 | sorun yok — ve **nedeni bilgi**: `_distribute` kullanmıyor, kartlar kendi alanını dolduruyor. `content` için ileride yön ipucu. |

*ÖLÇÜ DEĞİŞTİRİLDİ:* `inventory.bos_alan` `max(empties)` idi — azami, tek
seyrek slayt sayıyı belirleyebiliyordu. Yerine `bos_ortanca` + `bos_yayilim`
geldi; **ikisi birden**, çünkü "ortanca 21" ile "bazıları 0 bazıları 56" ayrı
şeyler ve düzeltmenin şekli buna bağlı. Eski azami kayıt için duruyor.

*İKİ HİPOTEZ ÖLÇÜMLE DÜŞTÜ:*

- **`ust-serit` suçlu**: fikstürde %52 veriyordu, gerçek kursta aynı gövde
  uzunluğuyla **%32** ve en iyilerden biri. **Fikstür ölçümü taşınmadı ve
  sebebi HÂLÂ BİLİNMİYOR** — fikstürle ölçüm yapan bir sonraki iş bunu
  bilmeli.
- **"C3 düzeltmesi C2'yi kötüleştirdi"**: varyantlar kapatılıp yeniden
  koşuldu, `section` varyantsız %48 → varyantlı %43. **İyileşmiş.** Yanlış
  çıkarımın sebebi K23'te.

**C3 — KAPANDI (2026-08-18): bir gerçek kusur düzeltildi, bir sahte kusur elendi.**

Envanter C3'ü **iki bileşene** ayırdı ve ikisi ayrı sonuç verdi.

*(1) SLAYTLAR ARASI — gerçek kusurdu, düzeltildi.*

```
16 slayt -> 5 x-IMZASI   (altisi birebir [0,8])
```

Ölçüm kusurun yerini kesinleştirdi: `content` 4 slaydını **4 farklı
varyanta** dağıtıyor ve tekrar üretmiyor — mekanizma kusursuz. Tekrarın
tamamı varyantı **olmayan** iki düzenden geliyordu: `section` 4 slayt,
`bullets` 4 slayt, ikisi de tek imza. Diğer dört düzen (`cover`, `steps`,
`statement`, `menu`) bu kursta **hiç kullanılmıyor** — onlara varyant
eklemek çeşitliliği değiştirmezdi (`apply_choice_plan`'in 0/4'üyle aynı
refleks: kullanılmayan yola iş harcamamak).

`VARIANTS`'a `section` (4) ve `bullets` (3) eklendi. **Değerler ölçüm değil
yargı, ama serbest değil**: mevcut dört imzanın (`[0,8]`, `[0,8,62]`,
`[0,22,35]`, `[0,48,62]`) kurduğu x dilinin içinde kalıp **kombinasyonu**
değiştiriyorlar. Rastgele x çeşitliliği artırır ama tutarlılığı düşürür;
C3'ün kusuru tekdüzelik, çözümü rastgelelik değil.

Yazdıktan **hemen sonra** ölçüldü — `content`'te üç varyant aynı `[0,8]`'i
veriyordu, aynı tuzak burada da vardı: **7 varyant → 7 farklı imza**, tuzağa
düşülmedi.

| ölçü | önce | sonra | elle (REFERANS BANDI, hedef değil) |
|---|---|---|---|
| x-imzası | 5 / 16 | **8 / 16** | 27 / 27 |
| hizalama (en sık x) | %60 | **%46** | %11 |
| ikiz slayt | 13 | **7** | 26 |

`check_variant_reach` yeni düzenleri **otomatik kapsadı** —
`sorted(compose.VARIANTS)` üzerinden dönüyor, sabit liste değil (golden'ın
sabit alan listesi tuzağı burada yok): `section 4/4`, `bullets 3/3`,
`content 6/6`.

*(2) SLAYT İÇİ DENGE — kusur DEĞİL, C2'ye devrediliyor.*

Tarif "%67 tek x'te, elle kursta %29" diyordu. Ölçüldü: baskın x **iki
korpusta da aynı şeyi** taşıyor —

```
BIZIM slide10  x=%8: yazi(11pt) + yazi(38pt) + yazi(17pt)
ELLE  slide    x=%9: yazi(36pt) + yazi(14pt) + yazi(10pt)
```

üst etiket + başlık + gövde, tek kolonda. Bu **ızgaranın kendisi**, monopol
değil. Oran farkının sebebi yoğunluk:

```
BIZIM  slayt basina sekil: ortanca  5   -> baskin x %67
ELLE   slayt basina sekil: ortanca 14   -> baskin x %29
```

İkinci bir hizalama noktası açmak oranı düşürür ama **yapay dağınıklık**
üretirdi. Gerçek fark "kaç hizalama noktası" değil **slayt başına kaç öğe**.

**C2 UYARISI — orada tekrar keşfedilmesin:** boş alan farkı (%56 vs %7) aynı
sınıf risk taşıyor. Slayt başına 5 vs 14 şekil, boş alanın da doğrudan
sebebi olabilir. C2 envanterinin **ilk sorusu**: kusur boşluk ritmi mi,
yoksa slayt başına içerik azlığı mı? İkincisiyse çözüm yerleşimde değil
**içerik üretiminde**.

**C4 GİRDİSİ:** `ikiz_slayt` C3 düzeltmesine **duyarlı** çıktı (13 → 7).
Yani "ikiz slayt" ile "x-imzası tekrarı" bağımsız olgular değil. Yeni ölçü
tasarlanırken bu bağımlılık bilinmeli, yoksa C4 düzeltmesi C3'ün kazancını
**tekrar sayar**.

**C4. Kurs tekdüze.** 18 dolu slaydın 16 çifti aynı silüette; üçü neredeyse
birebir (`slide6`/`slide12` = 0.000, `slide7`/`slide13` = 0.019,
`slide9`/`slide11` = 0.022).
Not: `variety` GEÇTİ diyordu ama o ölçü **varyant sözlüğünü** tarıyor,
üretilmiş kursun slaytlarını değil.
~~Ardışık tekrar yasağı var, ikizlik yasağı yok.~~ **Düzeltme (Faz 0):** ikizlik
**ölçülüyor** — `variety.py:180` deck ikizlerini hesaplayıp basıyor — ama
`191`'deki `ok` kararına katılmıyor. Yani ölçü var, kapı yok. Bu daha ucuz iş:
kapıyı açmak, yeni ölçü yazmaktan kolay.

---

## 3b. Faz 3 (C) ENVANTERİ — 2026-08-18, düzeltme yok

Dört kusur, üç soru (kesit / ne sayıyor / tarif bugün doğrulanıyor mu), ve
**kalibrasyon noktası** `0_duz_kopya.story` — elle yapılmış, editörde açılan,
çalışan bir kurs.

| | BİZİM | ELLE | tarif |
|---|---|---|---|
| **C1** punto çeşidi | 7 | 12 | **çürüdü** |
| **C2** boş alan | **%60** | %7 | **doğrulandı, kötüleşti** |
| **C3** hizalama (en sık x) | **%60** | %11 | **doğrulandı** |
| **C4** ikiz slayt | 13 | **26** | **tersine döndü** |

**C1 — tarif çürüdü, kapsam daraldı.** "16 farklı punto, altı bağımsız yol"
deniyordu. Bugün 10 punto, ve 7'si `TYPE_LADDER`'da. Merdiven dışı **3**
değer (14, 16, 18) ve hepsinin yeri ölçüldü:

```
BIZIM URETTIGIMIZ / katman1+2 : 18pt Rectangle x8,  16pt Button x8
TOHUMDAN          / katman1+2 : 14pt Text Box x2,   16pt Text Box x2
```

**Temel katmanda tek kaçak yok** — `compose`'un çizdiği her şey merdivende.
Kalan tek yol `compose_feedback_layers`, ve `snap` etmiyor. Altı yoldan beşi
`TYPE_LADDER` ile zaten kapanmış.

*Kalibrasyon tarifi çürüttü:* elle yapılmış kursta **332 yazının 332'si**
merdiven dışı (kendi düzenli ölçeği: 8,10,12,…,36) ve kurs sorunsuz. Yani
"kaç farklı punto" **kusura özgü değil** (K19); kusur ölçek YOKLUĞUNDA, ve
bizimkinde ölçek var — bir yol ona uymuyor.

**C2 — doğrulandı ve tarifin ötesinde.** Tarif %37/%30/%29 diyordu; bugün
**%60**, elle kursta %7. Ama ölçü şüpheli: `inventory.bos_alan` =
`max(empties)` — **dağılım değil AZAMİ**. Tek seyrek slayt sayıyı tek başına
belirleyebilir.

**C3 — doğrulandı, ve kesiti C1'in TERSİ.** 117 şeklin %60'ı tek x'ten
(%8); elle kursta %11 ve **69 farklı x** (bizde 8). Monopol **temel
katmanda**; katmanlarda 28 şekil, 11 farklı x. Tarifin doğrulandığı tek C
kusuru.

**C4 — tarif tersine döndü.** Elle kursta **26 ikiz çift**, bizde 13 — daha
az slaytla iki katı. Metrik kusura özgü değil; C1'deki punto çeşidiyle aynı
sınıf.

**Ortak bulgu:** dört metriğin ikisi (C1 punto çeşidi, C4 ikiz) elle yapılmış
kursta bizden KÖTÜ çıkıyor ve orada sorun değil. K19 dördüncü kez: sayının
büyüklüğü öncelik göstermiyor, ve ayrımı kalibrasyon noktası açtı.

**Düzeltme sırası, envanterden çıkan:** C3 (gerçek, dar, temel katman) →
C1 (dar, tek yol, `compose_feedback_layers` snap etsin) → C2 (önce ölçü
düzelsin: azami değil dağılım) → C4 (tarif çürük, yeniden tanımlanmadan iş
yok).

---

## 3-ÜRÜN. GÖZLE BAKILDI (2026-08-19) — ve ölçüm kapsamının çöktüğü yer

Panelle yeni bir kurs üretildi (`Desktop\Storyline\yeni.story`, parola
hijyeni, 14 slayt) ve **Preview'da bakıldı**. Suit 13/14 yeşilken ürün şu
hâldeydi:

**1. ŞIK ETİKETLERİ GÖRÜNMÜYOR — DÜZELTİLDİ.** Öğrenci çoktan-seçmeli
soruda **beş boş kapsül** görüyordu; etiket ancak tıklayınca beliriyordu.
Yani neyi seçtiğini okumadan seçiyordu. A1 (skor kaydedilmiyor) ve `submitG`
(gönder çalışmıyor) ile aynı sınıf.

*Mekanizma üç yanlış okumadan sonra çözüldü:*

```
TOHUM             <pic> VAR + 5 oval, etiketler GIZLI   <- DOGRU tasarim
adapt_seeded 1.   <pic>'i SILER (donor icerigi)
SONUC             gorsel yok, etiket hala gizli -> BOS KAPSUL
```

Gömülü `freePickManyIntr:5` tohumu bir **sıcak nokta** etkileşimi — elle
yapılmış kursun *"bu odada beş risk var, üzerine tıkla"* slaydından hasat
edilmiş. Orada etiketin görünmemesi doğru. Biz görseli siliyoruz ama etiketi
görünür yapmıyoruz.

*Kalibrasyon noktası yine ayırdı (yedinci kez):* elle kursun `slide1a`'sı
aynı yapıyı taşıyor ve orada **kusur değil** — fotoğraf duruyor.

*Düzeltme koşullu ve `adapt_seeded_slide`'da, SİLMEDEN SONRA:* görsel yoksa
`Selected` durumundaki gerçek `textBox` `Normal`'a **kopyalanır** (düğüm
uydurulmaz — `gradOvrlyFill` dersi). Görsel varsa dokunulmaz, yani tohumun
sıcak nokta kullanımı bozulmaz.

*İlk sürüm `_write_question` içindeydi ve çalışmadı:* orada `<pic>` **henüz
duruyordu**, guard doğru soruyu **yanlış anda** sordu ve "dokunma" dedi.

*İnvaryant + kanarya eklendi* (`check_choice_labels`): **5 şıklı** bir soru
üretir, çünkü mevcut fikstür 2 şıklı ve `freePickOneIntr` seçiyor — çoktan
seçmeli yol o kesitte **hiç görünmüyordu** (K1).

**2. 52 METİN TAŞMASI — AÇIK.** Aynı kursta ölçüldü, en kötüsü `93 > 16`:
kart kutusu 16 birim, metin 93 istiyor. `_cards` metni almayacak kadar kısa
yer ayırıyor ve Storyline kırpmadığı için metinler **üst üste biniyor,
okunmuyor**.

**3. ÖLÇÜ KÖRLÜĞÜ — C2'nin `bullets` sonucunu ÇÜRÜTÜR.** C2'de `bullets`
*"%8-12, sorun yok, en iyi"* diye ölçülmüştü. Kare tam tersini söylüyor: en
kötü olan o. Sebep — `bos_alan` kartların **kapladığı alanı** sayıyor;
kartlar dolu, içindeki metin taşıyor. Metrik "dolu" diyor, göz "okunmuyor"
diyor. **K19'un en keskin örneği.**

**4. ŞIK KUTUSU EN/BOY 27.5** (1613×59) — "mercek" görüntüsü.
`GROWTH_LIMIT` büyüme *miktarını* sınırlıyor, **en/boy oranını** değil.

**Bu bulguların hiçbiri suit'te görünmüyordu**, çünkü `check_text_fits`
yalnızca `_canary/variety.story`'yi okuyor ve soru slaytları birçok dökümde
yok. **Kapı yeşil, ürün kırık** — bütün oturumun en somut dersi.

---

## 3d. KART BANDI düzeltildi (2026-08-19) — ve "sayı aciliyet göstermez"in örneği

**Kusur.** Kartlı slaytlarda madde metinleri üst üste biniyor, okunmuyordu.

**Önce kesit (K2).** Taşımakta olduğum "52 metin taşması" sayısı **yanlıştı**:
52, `goz_ortu.py`'nin *kontrast* sayısı (okunamayan zemin). Taşma ölçüldüğünde
taban katmanda **29**, katmanlar dahil **60** çıktı. İki farklı kusurun sayısı
aynı rakama denk geldiği için birbirine karışmış. Kesit:

| şekil | adet | medyan | katman | görünürlük |
|---|---|---|---|---|
| **Body (kartlar)** | 20 | **4.3×** (en kötü 5.7) | taban | her zaman |
| Text Box | 33 | 1.6× | geri bildirim | cevaptan sonra |
| Oval | 4 | 1.6× | taban | her zaman |
| Lead / Eyebrow | 3 | 1.2× | taban | her zaman |

Text Box sayıca en kalabalık ama 1.6× ve ancak cevaptan sonra görünüyor;
Body 4.3× ve hep ekranda. **Hedef sayıdan değil orandan seçildi.**

**Mekanizma — çıkarım değil, ölçüm.** Çağrı yeri traceback ile belirlendi:
`compose.py:1653`, yani **`bullets` dalı**. Zincir:

```
frame 8→92 = 84
Title      52.8   <- bir cümle, başlık rolünde, %40 genişlikte sütun
kartlara kalan   19.8   ->  5 kart × 2.2 = MIN_CARD_H'nin (%10.8) BEŞTE BİRİ
```

Daha uzun bir başlıkta ayrılan bant **negatif** ölçüldü: **-27.2**.

**Kök sebep tek cümle:** `bullets` dalı başlığı ÖNCE yazıp kartlara KALANI
veriyordu. "Kart bandını metin dağıtılmadan önce ayır" kuralı `content`
dalında **vardı**, `cover` dalında **vardı**, `bullets` dalında **yoktu**.
`_distribute`'un kendi yorumu bunun *üçüncü* tekrarı olduğunu yazıyor. Bu
**dördüncüsü**.

> **K25 — Aynı kural üçüncü kez unutulduysa kural yanlış yerde durur.**
> Her çağıranın kendi eliyle yazdığı bir kural, çağıran sayısı kadar kez
> unutulur. Çözüm o dalı da düzeltmek değil, kuralı **tek bir fonksiyona**
> taşımaktır. Ölçülen: aynı rezervasyon kuralı dört daldan üçünde vardı,
> dördüncüsünde yoktu ve kusur tam oradan çıktı.

**Düzeltme.**
- `compose._card_band()` — **tek yetkili** ölçü. Rezervasyon da çizim de aynı
  sayıyı buradan okur. Eski rezervasyon `rows * MIN_CARD_H` idi: metni hiç
  sormayan bir **sabit**, ve `MIN_CARD_H` bir *taban* olduğu halde *değer*
  olarak kullanılıyordu.
- `bullets` dalı kart bandını başlıktan **önce** ayırıyor.
- Kart sütunu **koşullu** genişliyor: ölçüm dar dediğinde (%44 → %84), yoksa
  varyantın kararına dokunulmuyor. Ölçüldü: dar sütunda madde 3 satır, tam
  genişlikte 2 satır.
- `content` dalı da aynı `_card_band`'e bağlandı (bir sayıyı bir yer hesaplar).

**Sonuç — ölçüldü, aynı içerik, aynı yol:**

| | önce | sonra |
|---|---|---|
| **ağır taşma (>2 kat)** | **15** | **0** |
| medyan | 4.3× | 1.3× |
| en kötü | 5.7× | 1.6× |
| adet | 20 | 14 |

**Adet 20→14 (küçük), ağır taşma 15→0 (tamamı).** Adede bakan bir kontrol bu
düzeltmeyi "ufak bir iyileşme" diye okurdu. K24'ün ("sayı aciliyet
göstermez") ürün tarafındaki karşılığı, ve bu yüzden `check_card_band`'in
ölçütü **oran**.

**Düzeltmenin kendi ürettiği iki gerileme — ikisi de ölçümle yakalandı:**

1. **Üç Eyebrow taşması (yeni).** Kart bandı önce ayrılınca başlık kısıldı ve
   `_distribute` payı **orantılı** kısıyor — eyebrow dahil. Eyebrow 11pt, yani
   kalibre tabanın (13pt) **altında**: `page.text`'in küçültme döngüsü ona hiç
   girmez. **Küçültülemeyen bir bloktan pay kısmak taşmayı garanti eder.**
   Düzeltme: küçültülemeyen bloklar doğal yüksekliğini korur, sıkışma tek
   küçültülebilir bloğa — başlığa — biner.
2. **`coverage` kapısı kırmızıya döndü** (bullets boş alan %10 → %38).
   Kartları ayrılan bandın tabanına yaslamak boşluk üretti. Düzeltme: kartlar
   başlığın hemen altından başlıyor; rezervasyon zaten `≥ need` garantisini
   veriyor.

İkisi de **benim düzeltmemin ürünüydü** ve ikisi de suit tarafından değil,
düzeltmeyi kendime karşı ölçtüğüm turda çıktı.

**Kanarya.** `invariants.check_card_band()` — 5 maddelik gerçek fikstür,
ölçüt oran (sınır 2.0), ve kutuları ölçülen çökmüş değere (%2.2) ezen bir
kanarya. Çıktı: `en buyuk tasma 1.0 kat | kanarya: yasiyor (5.9 kat
yakalandi)`. Ayrıca "boş çalışma" koruması: 5 madde verilip 5 kart
ölçülemezse sonuç *temiz* sayılmıyor.

**Suit:** 13/14 yeşil, tek kırmızı `invariants` — aynı üç bilinen kasıtlı
sinyal (40 harflik havuz 2 < taban 6; `slidee.xml`'de iki erişilemez tohum
katmanı taşması). Yeni kırmızı yok.

### Açık kalanlar

- **14 hafif taşma (1.2–1.6×)** — bir satır payı. Kapatılmadı; `check_card_band`
  bu bandı kasten geçiriyor.
- **`MIN_CARD_H = 10.8` zemini tutmuyor.** Yorumu "13pt tek satır / 0.7" diyor,
  ölçüldü: 13pt tek satır %4.30, /0.7 = **%6.14**, yani sabit **1.8 katı**.
  `GROWTH_LIMIT` 2.4→2.8 ile aynı sınıf (birim/zemin uyuşmazlığı). Sabit
  **değiştirilmedi** — referans dondurulur, provenance kovalanmaz; kayda geçti.
- **33 Text Box taşması** (geri bildirim katmanları, 1.6×) — ayrı kod yolu.
- **Şık kutusu en/boy 27.5** — hâlâ açık, ayrı kusur.

---

## 3e. ŞIK OVALLERİ — ölçüm bitti, kare bekliyor (2026-08-19)

**Kendi kaydımı düzeltiyorum.** §3-ÜRÜN'de "şık kutusu en/boy 27.5" diye
yazmıştım. Bu ifade **eksik tanımlanmış**: kalibrasyon noktasında en/boy
**48.2**'ye kadar çıkan **65** kutu var ve hiçbiri kusur değil — çünkü onlar
`textBox`, yani görünür silueti olmayan bir satır yazı. Geniş-ve-kısa olmak
tek başına kusur değildir.

İddia ancak **sınıf içinde** karşılaştırılınca ayakta kalıyor:

| | kalibrasyon (elle yapılmış) | üretilen |
|---|---|---|
| `Oval` en/boy | 0.6 – **1.6** (5 oval) | **27.5** (5 oval) |
| `textBox` en/boy | 48.2'ye kadar, 65 adet | 27.5 – 37.3 |

Kalibrasyon noktasında **hiçbir oval 1.6'yı aşmıyor**. Bizim uygulamamız
oval sınıfında bandın çok dışında. Kalibrasyon noktası bu oturumda
**sekizinci** kez bir ölçütü kesti — ama bu sefer ölçütü tamamen düşürmedi,
**yeniden tanımlattı**.

### Çürüyen iki hipotez

1. **"Yetim ovaller kalıyor"** — çürüdü. Fotoğraf silindikten sonra donörün
   fotoğrafa göre konumlanmış ovallerinin ortada kaldığını sanmıştım. İlk
   tarama bunu destekler gibiydi (11 benzersiz oval, dağınık konumlar) ama
   tarama **buton durum gövdelerini** de sayıyordu (K22). Taban `shapeLst`'e
   inince: **5 oval, x %8'de, düzgün aralıklı** — uyarlama konumlandırmayı
   **doğru** yapıyor.
2. **"Konumlar fotoğrafa göre"** — çürüdü, aynı ölçümle. x yayılımı %0.0.

Geriye tek fark kalıyor: **şekil sınıfı**. Bir elips 27.5:1'e gerilince
mercek oluyor; kullanıcının gördüğü bozuk siluet bu.

### Geometri iki yerde yazılı

```
tag                <oval>                        / <roundRect>
prstGeom cocugu    <prstGeom><oval/></prstGeom>  / <prstGeom><roundRect radius="0.16666667"/></prstGeom>
```

Hangisinin çizimi belirlediği **bilinmiyor** ve tahmin edilmedi. Ayrıca oval
**üç** `prstGeom` taşıyor (taban + durum gövdeleri) — `shapeLst` seviyesinde
yazan bir düzeltme ikisini kaçırır (K22).

### Kare turu kuruldu: `tools/goz_kapsul.py`

Üç şekil, hepsi ölçülen kusurlu **oranda** (27.5); A dokunulmamış `<oval>` =
**bilinen negatif kontrol**. Karar kuralı kareye bakılmadan yazıldı:

- A mercek **değilse** → tur geçersiz, teşhis yanlış.
- A mercek, B kapsül → `prstGeom` yeter; düzeltme durum gövdeleri dahil.
- A/B mercek, C kapsül → tag da gerekli.
- C açılmıyor/bozuk → tag çevirme geçersiz, yol katalog borcuna döner.

**Mutlak ölçü taşınamadı, oran taşındı.** İlk sürüm 1612.8'i olduğu gibi
koydu; kusur 1920×1080 bir slayttan ölçülmüştü, fikstür slaydı 720×540 —
şekiller slayttan taşardı ve tur geçersiz olurdu. Taşınan şey **oran**
(604.8×22.0).

### Kare sonucu — `tools/goz_kapsul.py` (2026-08-19)

| şekil | çizilen |
|---|---|
| A dokunulmamış `<oval>` | **MERCEK** — negatif kontrol kusuru üretti, tur geçerli |
| B `prstGeom`→roundRect, tag `oval` | **BAR** |
| C tag da `roundRect` | **B ile aynı** |

Karar kuralı: *"A mercek, B kapsül → `prstGeom` yeter."* Çizimi belirleyen
`prstGeom`, **tag değil**. Yani tag'e, etkileşim GUID'lerine, tetiklere
dokunmadan düzeltilebiliyor — en az riskli dal ölçümle seçildi, tahminle
değil.

**Düzeltme:** `authoring._ovali_kapsullestir()`. İki koşul, ikisi de ölçülmüş:
slaytta `<pic>` yok **ve** en/boy bandın dışında. `shape.iter("prstGeom")`
**üç** düğümü de gezer (taban + durum gövdeleri) — `shapeLst` seviyesinde
yazan kod ikisini kaçırırdı (K22).

`OVAL_BANDI = 3.0` bir **tasarım yargısı** ve öyle işaretlendi: ölçülen şey
1.6 (kalibrasyon) ile 27.5 (üretilen); eşik bu ikisi arasında herhangi bir
yerde aynı sonucu verir, yani karar eşiğe duyarsız. `OVAL_RADIUS` korpustaki
gerçek `roundRect`'ten **okundu**, uydurulmadı.

### "Doğru koşul, yanlış an" — dördüncü kez

Çağrı önce `adapt_seeded_slide`'a kondu ve **hiç ateşlemedi**. Ölçüldü: o
anda ovaller hâlâ donör ölçüsünde (161×149 = **1.1**, 161×261 = **0.6**),
yani kalibrasyon bandının **içinde** — guard doğru davranıp dokunmadı.
Gerilme `compose.py:533`'te oluyor (1613×74 = 21.9). Koşul doğruydu, **yeri**
yanlıştı.

Bu oturumda aynı sınıf dört kez çıktı: `_etiketi_gorunur_yap` iki kez
(klon yolu, sonra `<pic>` hâlâ dururken), `_ovali_kapsullestir` bir kez, ve
kart bandı kuralının `bullets` dalında hiç olmaması. `authoring`'de artık
**çağrı yerine gerekçeli bir yorum** duruyor: oraya konursa sessizce 0 döner
ve "yapıldı" gibi görünür.

### Gerçek soru slaydının karesi — `tools/goz_sik.py`

Tek kare, iki borç: etiket görünürlüğü (etiket düzeltmesinden beri açıktı) ve
siluet. **Gerçek soru**, fikstür değil — bu oturumda bir fikstür ölçümü
gerçeğe aktarılmamıştı (üst-şerit: fikstürde %52, gerçekte %32).

**İlk tur GEÇERSİZ çıktı ve sebebi kendi kusurumdu.** Palet vermeden
koştum; paletsiz şıklar `noFill` alıyor ve **dolgusuz bir şekilde elips ile
kapsül aynı görünür** — deney tam ölçeceği şeyi içermiyordu. Panelle
üretilen kursta şıklar `solidFill=1B2C5E` taşıyor (ölçüldü). Fikstüre palet
eklendi ve artık dolgu yoksa tur kendini **geçersiz ilan ediyor**.

**Sonuç:** etiketler tıklanmadan okunuyor ✓, şık kutuları **bar** ✓. Her iki
düzeltme de gerçek yolda — durum gövdeleri, GUID'ler ve tetikler yerindeyken
— doğrulandı.

**Karede görünen ama ÜRÜNÜN kusuru olmayan şey:** başlık ve eyebrow soluk.
`gece` paleti koyu zemin için yazılmış, ben imza zeminini açık renk yaptım.
Fikstür artefaktı; ürüne yazılmadı.

### Kanarya

`invariants.check_choice_shape()` — ölçüt `prstGeom`in çocuğu (tag'e bakmaz,
çünkü kare tag'in çizimi belirlemediğini gösterdi), yalnızca `oval` sınıfına
bakar, ve kanarya bir şıkkı elipse geri çevirip ölçünün bağırdığını
doğruluyor. Çıktı: `5 oval, en buyuk en/boy 27.5, mercek 0 | kanarya:
yasiyor (1 mercek yakalandi)`. "Boş çalışma" koruması var: 5 şık verilip 5
oval ölçülemezse sonuç *temiz* sayılmıyor.

---

## 3f. "Kapı yeşil, ürün kırık"ın mekanizması bulundu (2026-08-19)

`produced` kapısı üretilmiş bir kursu ölçüyor ve *"ölçülen her sınıfta
temiz"* diyordu — 60 taşmalık bir kurs bu kapıdan **yeşil geçti**.

Sebep tek satırda: `MUST_BE_ZERO` = **çakışma, taban, kontrast**. **Taşma
listede yoktu.** Öte yandan `check_text_fits` taşmayı ölçüyor ama **kendi
fikstüründe**. İki kontrol de doğruydu; **kesişimleri boştu**.

Eklemeden önce metriğin kusuru gerçekten görüp görmediği ölçüldü — yoksa
eklemek sahte rahatlık olurdu (bu oturumun tekrar eden tuzağı). Panelle
üretilen kusurlu kursta:

```
inventory.audit(yeni.story)  ->  tasma=28   cakisma=1   taban=3   kontrast=0
```

Metrik kusura duyarlı. `"tasma"` kapıya eklendi; `produced` yine yeşil.

Not: `cakisma=1` ve `taban=3` **zaten** kapıdaydı — yani o kurs üretilmiş
olsaydı kapı düşerdi. Kapının kendi sentetik kursu o kusurları
üretmiyordu. Yani boşluk iki katmanlı: ölçülmeyen bir sınıf **ve** kusuru
üretmeyen bir prob.

---

## 3g. PROB kusur üretmiyordu — sertleştirildi ve iki kusur çıktı (2026-08-19)

§3f'de kapının ölçmediği bir sınıf bulunmuştu. Asıl mesele daha derindi:
**kapının probu kusuru üretmiyordu.** Kusur sayılarını karşılaştırmak
yanıltırdı (`yeni.story` düzeltme öncesi, prob düzeltilmiş kodla kuruluyor),
o yüzden **girdi ve yol** ölçüldü:

| | PROB | GERÇEK |
|---|---|---|
| Title medyan | **9** | **24** (en uzun 32) |
| Body medyan | **21** | **73** (en uzun 91) |
| Lead medyan | **15** | **64** (en uzun 181) |
| bullets | 4 madde, 11–22 krk | 5 madde, 50–60 krk |
| şık sayısı | **2** (tek seçmeli) | **5** (çoktan seçmeli) |

Prob'un docstring'i *"İÇERİK ZORLAYICI SEÇİLDİ… uzun şık etiketleri (70+
karakter)… uzun bir kök"* diyordu. **İddia tutmuyordu.**

En ağırı sonuncu satır: `LONG_CHOICES` **iki şıklı**, yani prob her zaman
`freePickOneIntr` seçiyor ve **çoktan-seçmeli yol bu kapıdan hiç
geçmiyordu**. Bu oturumun iki görünür kusuru — boş kapsüller ve 27.5:1
mercek siluet — yalnızca o yolda üretiliyor. Kapı yeşildi çünkü **kusurun
geçtiği yol probda yoktu**. Aynı kör nokta `check_question_frame`'de de
vardı ve orada `check_choice_labels` ile kapatılmıştı; burada açık kalmış.

### Bir hatam ve geri alınışı

`tasma`'yı `MUST_BE_ZERO`'ya ekledim — **hemen üstündeki kaydı okumadan**.
Orada 2026-08-16'da ölçümle alınmış bir karar duruyordu: Storyline taşan
metni **kırpmıyor**, yani taşma metin kaybı değil, kozmetik; ölçü kalır ama
kapı olmaz. Kasıtlı ve gerekçeli bir kararı ezmişim. **Geri alındı.**

İkisini uzlaştıran ayrım **adet değil şiddet**: kutunun metnin beşte birine
düşmesi kozmetik değil, yazı komşusunun üzerine biner. `inventory.audit`
artık `tasma_orani` da veriyor — **aynı hesaptan**, ikinci bir uygulama
açılmadan.

```
KUSURLU gercek kurs : tasma=28  tasma_orani=5.73
PROB (eski icerik)  : tasma=0   tasma_orani=0.95   <- hicbir kutu dolmuyordu
PROB (sertlestirilmis): tasma=18 tasma_orani=8.06
```

### Sertleştirme neyi açtı

Prob 5 şıklı çoktan-seçmeli yolu geçince `compose_question_frame`
**`ChoiceLabelsTooLong` ile reddediyor** — red doğru çalışıyor. Ama
`add_question` slaydı **istisnadan önce** yaratıp değiştiriyor ve
`panel/builder.py:402`'deki `except StoryError` geri çekilme menüsü
eklerken **yarım kalmış slayt pakette kalıyor**:

```
slide16  freePickManyIntr   <- YETIM: donor ovaller 161x149, tasma 6.5 kat
slide17  (etkilesim yok)    <- geri cekilme menusu, 1 sekil taban altinda
```

Kurs **ikisini birden** gönderiyor. Ve yetim yalnızca görsel değil:

```
taban     4     KUSUR   sekil slaydin tabaninin altinda
kayitli   2/4   KUSUR   quiz'e kayitli degilse skor LMS'e gitmez
```

**İki sorunun cevabı alınıyor, skoru gitmiyor** — A1 ile aynı sınıf.

### Bu, kayıtlı ayrışmanın ölçülmemiş bedeli

`pick_template_for_question` "sığar" deyip şablonu veriyor,
`compose_question_frame` "sığmıyor" deyip reddediyor. Kodun kendi yorumu
zaten yazıyordu:

> *"İki hesabın aynı soruya aynı cevabı vermesi gerekiyor; bugün
> vermiyorlar."*

**Ayrışma kayıtlıydı, sonucu kayıtlı değildi.** Sonuç: yetim, puanlanmayan,
taban altına taşan bir slayt — ve hiçbir kapı bunu görmüyordu.

### Durum

`produced` kapısı **kırmızı ve bu doğru**: her zaman orada olan ama
görünmeyen iki kusuru bildiriyor. Kapı artık ölçtüğünü sanmıyor.

### Sıradaki iş — düzeltme yapılmadı

1. **Yetim slayt geri alınmalı.** Yaratan temizlemeli: `add_question` çerçeve
   reddettiğinde yarattığı slaydı kaldırmalı. Pakette slayt silme yolu
   **yok**; yazılması gerekiyor (rels, sahne listesi, tetikler).
2. **Asıl çözüm ayrışmayı kapatmak** — `fit_choices` ile
   `compose_question_frame` aynı sayıyı tek yerden okumalı. O zaman red
   slayt yaratılmadan **önce** verilir ve yetim hiç oluşmaz.
3. Geri çekilme menüsünün butonları taban altına taşıyor (%103.2) — ayrı.

---

## 3h. AYRIŞMA KAPATILDI — ikinci formülün yetkisi kaldırıldı (2026-08-19)

§3g'de yetim slaydın sebebi bulunmuştu: `pick_template_for_question` "sığar"
diyor, `compose_question_frame` "sığmıyor" diyor. Ayrışma iki parçaymış ve
**ikisi de ölçüldü**:

**1. `eyebrow` kabul testine geçmiyordu.** Builder onu `add_question`'a
geçiriyor ama seçime geçirmiyordu. Tek değişkenle ölçüldü:

```
eyebrow YOK : kabul testi bandi %59.3  ->  "sigar"
eyebrow VAR : kabul testi bandi %54.1  ->  cercevenin bandi ile BIREBIR
```

Bant farkı **tamamen** bundan. Builder artık aynı değeri iki çağrıya da
geçiriyor.

**2. Kalan fark iki ayrı fonksiyondan.** Bant eşitlendikten sonra bile:

```
kabul testi : kutu %9.02   (layout_text_height)
cerceve     : kutu %9.95   (height_for_label — sekli ve marjlarini okur)
```

Aynı genişlik oranı (%84), aynı punto (13), aynı etiketler — **farklı sayı**.

### Çözüm: paritenin peşine düşmemek

İki formülü uzlaştırmak **üçüncü** bir ayrışma kaynağı açardı. Bunun yerine
ikinci formülün **yetkisi kaldırıldı**: seçim artık atılacak bir kopyada
**gerçek `add_question`**'ı koşturuyor (`_gercek_prova`). Seçilen şablon,
aynı çerçeve aritmetiğinden bir kez **geçmiş** şablondur — ayrışma
**inşaen imkânsız**.

Mekanizma yeni değil: `_probe` katalog için bunu zaten yapıyor. Farkı,
kendi docstring'inde yazıyordu:

> *"Not whether it can hold **the** question — the real stem and the real
> options are not known here… the placement-time check is the other half."*

`_gercek_prova` o cümlenin eksik yarısı. `fit_choices` kalıyor ama artık
**ucuz ön eleme**; kararı vermiyor.

**Kalan risk, kayda geçti:** prova diskten okuyor, yani `pkg` üzerindeki
kaydedilmemiş bir düzenleme (tema/ölçü değiştiren) provayı gerçek çağrıdan
ayırabilir. `_probe` için de böyle ve orada zaten "katalog için doğru,
yerleştirme için yanlış" diye yazılı.

### Sonuç: yetim gitti

```
ONCE:  slide16 freePickManyIntr (bozuk, puanlanmayan)  +  slide17 menu
SONRA: slide16 menu
```

```
kayitli   2/4  KUSUR   ->  2/2  temiz
taban     4    KUSUR   ->  0    temiz
tasma_orani    8.06    ->  2.15
```

**"Cevap alınır, skor gitmez" kapandı.**

### Menü dalı — aynı kural, BEŞİNCİ dal (K25)

Yetim gidince altından geri çekilme menüsünün kendi kusuru çıktı. Dalın
kendi yorumu *"Choices are the content: the buttons get the room, not the
copy"* diyor — ama kod başlığı **önce ve sınırsız** yazıyordu:

```
Title    y%10.0  h%65.9  38pt   <- soru koku, slaydin ucte ikisi
buton 4  y%99.2         -> alt kenar %103.3   SLAYT DISI
```

Aritmetik: `_buttons` içinde `each = max(each, 4.0)` — **taban, banda sığıp
sığmadığına bakmadan kazanıyordu**. 4×4.0 + 3×1.6 = %20.8, başlangıç %82.5
→ %103.3. Ölçülen %103.2.

Kart bandıyla **birebir aynı hastalık**, ve aynı kuralın eksik olduğu
**beşinci** dal. Düzeltme aynı biçimde:

- `_buttons_stacked()` ve `_button_band()` — **tek yetkili**. Bandı ayıracak
  çağıran, yığın mı sıra mı kurulacağını bilmek zorunda; karar `_buttons`
  içinde gömülüydü ve dışarıdan sorulamıyordu.
- `BUTTON_STACK_MIN_H = 4.0` çıplak sayı olmaktan çıktı; rezervasyon onu
  **okuyor**.
- Yığın bandına sığmıyorsa önce **yukarı kayar**, taban ancak yer kalmayınca
  esner.
- Menü dalı bandı başlıktan **önce** ayırıyor.

Sonuç: Title %65.9 → **%36.1** (38pt → 26pt, kendi bandına küçüldü),
butonlar %65.6–92.0, `taban 0`.

### Sessiz içerik kaybı

`spec["buttons"] = choices[:4]` — geri çekilme **beşinci şıkkı sessizce
atıyordu**. Öğrenci beş seçenekten dördünü görüyor, rapor bunu söylemiyor.
Düzenden ağır: **içerik kaybı**. Kırpma muhtemelen yığın slayttan taştığı
için konulmuştu; sebep artık yok (bant sayıdan ayrılıyor), kaldırıldı.

### Açık kalan: `soru 2/4`

`produced` hâlâ kırmızı ve **doğru söylüyor**: beş uzun şıklı soruyu
puanlayabilen şablon **yok**, o yüzden puanlanmayan menüye düşüyor. Bu, (c)
katalog borcunun ta kendisi — metin listesi çoktan-seçmeli tohumu. Kapı artık
bu eksikliği gizlemiyor.

### Buton bandı da ölçümden ayrılıyor — düzeltildi

Yığın slayt içine girdi ama etiket kutusunu **2.1 kat** aşıyordu (kutu %4.0
= 21.6 birim, etiket 46 birim istiyor). Sebep aynı: rezervasyon
`n * BUTTON_STACK_MIN_H` idi — **tabanı değer olarak kullanan**, metni hiç
sormayan bir sabit. `MIN_CARD_H` ile birebir aynı hastalık.

`_button_band` artık ölçüyor ve **tek yetkili**: yuvayı da bandı da aynı
sayı belirliyor, dolayısıyla ayrışamazlar.

Punto **tabandan** ölçülüyor: `add_button` 15pt'ten başlayıp kalibre tabana
kadar küçülttüğü için, tabanda sığan bir kutu her zaman sığar.

**Şekil marjı ölçüldü, uydurulmadı.** `height_for_label` (şekli ve marjlarını
okur) ile `measured_text_height` (şekilsiz) arasındaki fark gerçek buton
şekillerinde:

```
1 satir : 23.2 -> 28.4   (+5.2 birim = %0.96)
2 satir : 46.4 -> 52.7   (+6.3 birim = %1.17)
```

Sabit değil, satırla artıyor. `BUTTON_LABEL_MARGIN = 1.2` üst değeri alıyor
ve gerekçesi kodda duruyor. Doğrudan `height_for_label` çağrılamıyor çünkü
rezervasyon anında **buton şekli henüz yok** (`add_button` onu sonra
klonluyor) — bu sınır da yazıldı.

```
kutu   %4.0  ->  %9.8      etiket 46 istiyor, 52.9 var
tasma  2.1 kat -> 0.9 kat
prob   tasma=0  tasma_orani=0.95  cakisma=0  taban=0
```

**Kanarya:** `invariants.check_button_band()` — ölçüt oran (sınır 1.6),
taban aşımı ayrı sayılıyor, ve kanarya kutuları ölçülen çökmüş değere (%4.0)
ezip **kusurun kendi sayısını** yakalıyor: `2.1 kat`. Boş çalışma koruması
var.

### Turun toplamı

```
PROB (eski, yumusak)      : tasma=0   oran=0.95  taban=0  <- kusuru URETMIYORDU
PROB (sertlestirilmis)    : tasma=18  oran=8.06  taban=4  kayitli 2/4
PROB (yetim duzeltildi)   : tasma=10  oran=2.15  taban=0  kayitli 2/2
PROB (buton bandi)        : tasma=0   oran=0.95  taban=0  kayitli 2/2
```

Baştaki ve sondaki satır aynı sayıları taşıyor ama **aynı şey değil**:
ilkinde prob kusuru üretmiyordu, sonuncusunda üretiyor ve ürün geçiyor.

### "(c) katalog borcu" TEŞHİSİ YANLIŞTI — kod kusuruymuş

`produced`'ın son kırmızısını *"beş uzun şıklı soruyu puanlayabilen şablon
yok"* diye okudum ve Erman'dan **elle yapılmış bir tohum** istedim. İkisi de
yanlıştı; ikincisi ayrıca aracın varlık sebebine aykırı — bu iş silinsin
diye var.

Erman itiraz etti (*"amaç zaten otomatik oluşturmak değil mi"*) ve redde
tekrar bakınca sayı zaten oradaydı:

```
her yuvaya %9.54 kaliyor, en uzun etiket %9.95 istiyor
```

**%4'lük bir fark.** "Hiçbir şablon taşıyamaz" değil. Bant %37.9'dan
başlıyordu çünkü `compose_question_frame` **soru kökünü önce ve sınırsız**
yazıyor, şıklara kalanı veriyordu.

Yani aynı kuralın eksik olduğu **YEDİNCİ** yer. Şablon eksikliği sanılan
şey, bir yerleştirme kusuruydu.

**Düzeltme, diğer altısıyla aynı:** şık bandı kökten **önce** ayrılıyor,
taban puntoda ölçülerek (tabanda sığan bant her zaman sığar; yer varsa
aşağıdaki döngü daha büyük punto seçer). Kök en az bir satır alır, gerisini
şıklar alır. Sıkışma **köke** biner çünkü kök küçültülebilir, şık kutusu
küçültülemez.

```
ONCE : bant %37.9'dan basliyor -> RED -> geri cekilme -> soru PUANLANMIYOR
SONRA: kok 21pt -> 17pt (182 gerekiyor, 191 var)
       5 oval, her biri %10.0, en cok 93 istiyor, 107 var
       hicbir yerde tasma yok
```

```
soru      2/4 EKSIK  ->  4/4 temiz
kayitli   2/2        ->  4/4 temiz
```

**`produced` YEŞİL.** Suit 13/14; tek kırmızı `invariants` ve o da aynı üç
bilinen kasıtlı sinyal.

**Ders, K25'in ötesinde:** bir eksikliği "katalog/varlık borcu" diye
sınıflamadan önce reddin **sayısına** bak. %4'lük bir fark katalogla değil
kodla kapanır. Ve bu oturumda aynı yerleşim kuralı yedi ayrı dalda eksikti
— sekizincisini aramak, yeni bir tohum aramaktan daha verimli.

---

## 3i. SEKİZİNCİ DAL ARANDI — üç tane çıktı (2026-08-19)

Yedi düzen sert içerikle sürüldü. Karar kuralı **sonuca bakılmadan** yazıldı:
ağır taşma (>2.0 kat) veya taban aşımı → kusurlu; içerik hiç çizilmiyorsa
**ölçülemedi** (temiz *değil*).

```
duzen        tasma  en kotu  taban   karar
cover            2      1.2      0   temiz
section          2      2.6      0   KUSURLU
content          7      3.2      0   KUSURLU
bullets          5      1.2      0   temiz
steps            5      2.9      0   KUSURLU
statement        0      0.0      0   temiz
menu             0      0.0      0   temiz
```

**En kötüsü `content`** — yani "kural zaten var" diye **okuduğum** dal. Kod
okuması davranışla bu oturumda dördüncü kez ayrıştı; karar kuralına "kanıt
ölçüm olacak, kod okuması değil" yazmam bunu yakaladı.

### `steps` — sekizinci dal

`slot = (bottom - top) / len(items)`: başlık önce ve sınırsız, adımlara
kalan bölünüyor. Kutu %3.0 (16 birim), metin 46 istiyor.

Düzeltme: `_yigin_bandi()` — ölçen ortak yetkili (dördüncü bir kopya
açmamak için). Band başlıktan önce ayrılıyor, başlık en az bir satır alıyor.
**2.9 → 1.1.**

### `section` — dokuzuncu, ve `density_scale`'in eksik yarısı

Burada zincir daha derin. `_distribute` izlendi:

```
istenen bloklar: [3.8, 206.2, 43.7]     <- display %206.2 istiyor
verilen bloklar: [1.3,  72.2, 15.3]     <- pay kisildi, toplam %88.8
konumlar       : [12.0, 13.3, 85.5]     <- bant %78'de bitiyor, son blok DISINDA
```

Kısma tabanı (`0.35`) bandı aşıyor: 253.7 × 0.35 = %88.8 > %66. Yani yine
**bir taban ile bir bant çarpıştı ve taban sessizce kazandı** — bu oturumda
dördüncü kez (kart bandı, buton bandı, `_distribute`, şık bandı).

Kök sebep daha da yukarıda: **`density_scale` yalnızca YUKARI çekiyor.**
Docstring'i de öyle diyor — *"Seyrek içerikte punto ölçeğini yukarı çeker."*
Yoğun içerikte küçültecek yarı **hiç yoktu**: bloklar %253.7 isterken
fonksiyon **1.000** döndü.

Küçültme yarısı eklendi. Tabanı uydurulmadı: en küçük **okunan** rolün
puntosu kalibre bandın alt ucuna (13pt) inince durur.

**Kendi yamamın iki hatası, ikisi de ölçümle çıktı:**

1. **Taban yanlış rolden.** İlk sürüm `min(size_of(role))` kullandı ve
   **hiç koşmadı**: `eyebrow` merdivende zaten 11pt, yani kalibre bandın
   altında ve *bilerek* öyle — o bir etiket, okunan metin değil.
   13/11 = 1.18 > 1.0 çıkınca döngü baştan yanlıştı. Taban artık yalnızca
   ≥13pt başlayan rollerden geliyor.
2. **Sonsuz döngü.** `round(0.619, 2) = 0.62 > 0.619` — ölçek ilerlemiyor,
   tur 300 saniyede bitmedi. Deponun başka yerlerde kullandığı *"ilerleme
   yoksa dur"* guard'ı (`if nxt >= size: break`) eklendi.

Sonuç: ölçek 1.000 → **0.620**, bloklar 206.2 → 92.3, konumlar bandın
içinde. **2.6 → 1.7.**

### `content` — onuncu

Kalan taşma kartlarda: kutu %8.8 (48 birim), metin 116 istiyor. Sebep kart
sütununun dar olması (%34.6). `bullets` dalında koşullu genişletme **vardı**,
bu dalda **yoktu** — aynı düzeltmenin yarısı bir dalda kalmış. **3.2 → 1.6.**

### Kendi ürettiğim gerileme

`steps` düzeltmesi `coverage` kapısını düşürdü: boş alan %24 → %30. Ölçülen
yuvayı **değer** olarak kullanınca bant doldurulmaz oldu — *taşmayı çözerken
boşluk üretmek*, kart bandında da olan gerilemenin aynısı. Ölçülen yuva
artık **taban**: `slot = max(_slot, (bottom - top) / len(items))`.

### Ve asıl eksik: bu kontrol yoktu

`coverage` ve `deadband` yedi düzeni **zaten** sürüyor — ama **kendi
SPECS'iyle**: kısa başlıklar, kısa maddeler. Mutlu yol ölçüm yapmaz. Üç
kusur yıllardır o taramanın içinden geçiyordu.

`invariants.check_layout_bands()` eklendi: yedi düzen, **gerçek kurstan
ölçülen** sert içerikle (başlık 24–32, gövde 73–91, beş madde 50–60 karakter),
ölçüt oran + taban aşımı ayrı, ve boş çalışma koruması ("2'den az şekil
çizildiyse *temiz* değil, **ölçülemedi**"). Çıktı: `7/7 duzen, en buyuk
tasma 1.7 kat | kanarya: yasiyor (4.3 kat yakalandi)`.

### Sayım

Aynı kural — *"bandı metinden önce ayır"* — **on** ayrı yerde eksikti:
content, cover, bullets, menu, `_buttons`, soru çerçevesi, steps, section,
`_distribute`'un kısma tabanı, ve `density_scale`'in küçültme yarısı.
K25'in gerekçesi artık iki değil **on** ölçümle duruyor.

**Suit:** 13/14 · tek kırmızı `invariants`, aynı üç bilinen kasıtlı sinyal.

---

## 3a. SIRADAKİ İLK İŞ: ürüne bak — kare turundan ÖNCE (2026-08-19)

**Bu, kusur listesinde olmayan ve muhtemelen en önemli sınır.**

DEVIR bir kusur listesi, ve liste geometrik bakıyor: taşma, hizalama,
kontrast. "Slayt seyrek" maddesi yok — çünkü onu yazan da geometrik
bakıyordu. C2'de `content`'in %31–43 boşluğu "kapsam dışı" sayıldı ve o,
çerçevenin **içinde** tutarlıydı. Çerçevenin kendisi eksik.

**Ölçüm zaten söylüyordu (K24):**

```
slayt basina ortanca sekil:  BIZIM 5    ELLE 14
```

Araç teknik olarak temiz kurslar üretiyor ama **insanın koyacağının üçte
biri kadar öğe** koyuyor. Bu üç ayrı ölçümde çıktı ve üçünde de bir kusuru
elemek için kullanıldı.

**Yapılacak şey ölçüm değil YARGI**, ve onu ancak Erman verebilir:
`test/_canary/uretilmis.story`'yi Storyline'da aç, baştan sona bak, ve sor —
*"bunu böyle gönderir miydim?"*

Çıkacak şey muhtemelen yeni bir kusur listesi olacak, ve bu seferki tarifler
**gözlemden** gelmiş olacak, hipotezden değil (K20'nin tersi: envanterin
kaydı doğrulaması yerine, gözlem kaydı üretmesi).

**Kare turundan ÖNCE**, çünkü o dört borç teknik borç; bu ise aracın işe
yarayıp yaramadığı sorusu ve cevabı diğer dördünün **önceliğini
değiştirebilir**.

---

## 3c. KARE TURU — dört borç, sırası belirlenmiş (2026-08-19)

Otomasyon hazır ve kanıtlandı: `force_close` nazik kapatıyor, kare içerik
görünene kadar bekliyor, `B1_KARE.story` elle müdahale olmadan yakalandı,
fare yeteneği ölçüldü (`SetCursorPos` çalışıyor; hover davranışı ölçülmedi).

**SIRA, ve gerekçesi:**

**1. Fikstür/gerçek ayrışması — ÖNCE BU.** C2'de ölçüldü: `ust-serit`
varyantı fikstürde **%52** ölü bant veriyor, gerçek kursta aynı gövde
uzunluğuyla **%32**. Sebebi bilinmiyor.

Bu, diğer üçünün **zeminini** ilgilendiriyor: `.h` ve bant dışı punto
kalibrasyonu **ikisi de fikstür ölçümü**, ve elde artık fikstürde ölçülen
bir sayının gerçek kursta tutmadığı bir vaka var. Ayrışmanın sebebi
bulunursa diğer iki kalibrasyonun güvenilirliği artar; bulunmazsa onların
sonuçları da **aynı şüpheyle işaretlenmeli**.

**2. `.h` — 1920 sahnede yatay çarpan.** `Space.h` simetriyle türetildi
(`slide_w/720`), ölçülmedi. Fikstür hazır (`goz_sahne.py`), karar kuralı
yazılı.

**3. Dönüşüm aritmetiği doğrulaması — buton durumu karesi.** `tint`/`shade`/
`lumMod`/`satMod` yazıldı, zemini ECMA-376, **bağımsız doğrulaması yok**.
Uygun vaka statik karede yok: tek dönüşümlü dolguların hepsi
`bG < btn < shapeLst < state` içinde (K22), yani **hover** gerekiyor.
Bu, `contrast.audit(katmanlar=True)`'ı açan tek düğüm.

**4. B4 bant dışı punto (8/9pt).** `CALIBRATED_RANGE` alt ucu; B4'ün
gürültü oranı sorusu bununla cevaplanıyor.

---

## 4. İş sırası

### Faz 0 — Kapsam envanteri — **BİTTİ (2026-08-16)**

Çıktılar:

- `tools/coverage.py --envanter [kurs]` — beş eksenli kapsam tablosu (23 kesit)
  ve kör nokta nüfus sayımı.
- `tools/coverage.py --kanarya` — kapsam iddiasını **kasten bozarak** sınar.
  İki yönlü: aynı kusur temel katmanda yakalanmalı, geri bildirim katmanında
  yakalanmamalı. Canlı kontrol olmadan "bulamadı" hiçbir şey söylemez.
- `tools/suit.py` — bütün kontroller, doğru sırada, tek çıkış kodu. Sıra
  bağımlılıktır: `variety` → `variety.story` → `invariants`/`deadband`.
  Yanlış sıra sessizce **geçen** bir suit üretiyordu.
- `test/_referans/referans.story` — dondurulmuş referans kurs
  (sha256 `dcbd4729ebb365d3`, eski `_canary/modul.story`).

**Belgedeki on kusurun sayıları ölçüm değil, sohbet kaydıdır.** Kapsamı
bilinmeyen bir ölçümün üstüne invaryant kurmak, aynı hatayı kaynak seviyesinde
tekrarlamak olur. O sayılar bundan sonra "işi başlatan gözlem"dir, hedef değil;
Faz 2'nin K2+K4 kanıtı dondurulmuş referansa ve yeni ölçüme bağlanır.

Ölçülen (referans.story, 34 slayt / 20 dolu):

| bulgu | sayı |
|---|---|
| metin taşıyan şeklin kör noktada olan payı | 44/124 = **%35** |
| tahmini taşma: kontrolün kesitinde / kör noktada | **5 / 33** |
| geri bildirim katmanı üzerinde verdikt veren kontrol | **YOK** (ölçüldü) |
| `scope.py` kapsam cümlesi olan / olmayan kontrol | 5 / 12 |

Kör noktadaki 33 bir **kusur sayısı değil, aday sayısıdır**:
`estimate_text_height` yalnızca bestelenen temel katman yazısında kalibre
edildi, donörden gelen katman metninde ne ölçtüğü ölçülmedi. Ayırmak Faz 2'nin
işi.

---

### Faz 0 — özgün tanım (referans için)

On kusurdan yedisi "kontrol var, kesit yanlış" biçiminde. Envanter çıkmadan
düzeltmeye başlanırsa, aynı hatanın ölçülmeyen başka bir kesitte durduğu
bilinemez.

Çıkarılacak tablo — her kontrol için:
hangi dosyalar, hangi slayt türleri, hangi katmanlar (temel/geri bildirim),
hangi şekil sınıfları (metin/dekoratif/görsel), hangi tema × düzen kesiti.

`coverage.py` bunun bir kısmını zaten yapıyor; genişlet.
Çıktı, `scope.py`'nin bastığı kapsam cümleleriyle uyumlu olmalı — uyumsuzluk
varsa cümle yanlış demektir.

### Faz 1 — Ürün kırıkları (A1, A2) — **BİTTİ (2026-08-16)**

A1 ve A2 düzeltildi (§3'te mekanizmalarıyla). Ayrıca:

- `completeness.py --kontrol` — dedektörün **üç ayaklı** pozitif kontrolü:
  dondurulmuş referansı birebir sayıyor mu (**iki yönlü** — az saymak
  körleşme, çok saymak gürültü), bilinen sağlam kursu temiz buluyor mu,
  ve **kasten silinen tek kaydı** yakalıyor mu. Üçüncüsü olmadan ilk ikisini
  atıl bir dedektör de geçer.
- `tools/suit.py` — adım başına **tam log** (`test/_canary/suit_log/`).
  Özet tablo yalnızca son satırı gösteriyordu ve `open_test`'in kanarya
  ayaklarının ayrıştığı satır orada görünmüyordu.
- Sessiz-geçiş taraması: `invariants.py`'de üç yer (bkz. K1b).
- Kopuk tetikleyici tek otoriteye indirildi (bkz. K12).

**`--tam` koşuldu ve kanarya ayrıştı:** `saglam=acildi bozuk=acilmadi
[GUVENILIR]`. Üretilen kurs — her iki `story.xml` yazımını da taşıyor —
Storyline'da açıldı.

İki bulgu, ikisi de "kontrol var ama işini yapmıyor" sınıfı ve ikisi de
yalnızca runner yazıldığı için görünür oldu:

- `canary.py` her zaman `2` döner (fikstür kurucu, hüküm verici değil).
  Kapı sayıldığında suit koşuyu daha başta terk etti.
- `open_test` varsayılan olarak yalnızca `donors/` açıyordu — `--tam`'ın en
  pahalı adımı, yazma yolu hakkında hiçbir şey söylemeyecekti.

---

### Faz 1 — özgün tanım (referans için)

Yeni kontrol ailesi: **eksiksizlik**. Brief'teki bölüm sayısı ve bölüm başına
soru sayısı, üretilen dosyada karşılığını buluyor mu; her senaryo slaydı
puanlanabilir bir soru tipi mi; her sahnenin ilk slaydı bestelenmiş mi.

### Faz 2 — Ölçüm hataları (B1, B2, B3, B4, B5)

Her biri için invaryant, ve **invaryantın koşulan kesitte bu hatayı gerçekten
üretebildiğinin kanıtı** (K2 + K4). Sıra: B2 → B1 → B3 → B5 → B4.
B2 önce, çünkü sözleşme ihlali muhtemelen bir kod yolunun hiç bağlanmamış
olmasından geliyor ve bu diğerlerini de etkileyebilir.

#### Faz 2 durumu (2026-08-17 kapanış)

| | durum |
|---|---|
| **B1** metin taşması | **BİTTİ** — 24 adayın 24'ü artefakt çıktı; kalan iddia da kareyle çürütüldü. Kök neden kanonik ölçek. Çerçeve artık tabanda gerekçeli reddediyor. |
| **B2** şekil slaydın dışında | **BİTTİ** — "üremiyor" sanılmıştı, `uzun/orta` hücresinde üredi (%118.7); kapı zaten doğruydu, vaka eksikti (K16). |
| **B3** kopuk tetikleyici | **BİTTİ** — öncül düştü (37 kopuk / 0 uyarı), gerçek kusur ölü Submit tetikleyicisiydi: araç kaynaklı 12 → 0. |
| **B4** kutu çakışması | başlanmadı |
| **B5** tema katmanlara ulaşmıyor | başlanmadı |

> **GÜNCELLEME (2026-08-26): kapı artık yeşil, ama susturularak değil.**
> Kalıcı kırmızı bir kapı kapı değildir: dördüncü bir invaryant kırılsaydı
> çıktı "4 INVARYANT BOZULDU" derdi, suit yine "1 KAPI KALDI" derdi ve yeni
> bilgi eskisinin arasına saklanırdı. `invariants.BILINEN_KIRIKLAR` eklendi:
> üç kırığın **ölçülmüş değerlerini** (boole değil) ve **gerekçelerini**
> taşıyor. Kapı üç durumda bağırıyor — yeni imza, kaybolan imza (taban
> eskimiş; tek yönlü susturma olmasın), ve aynı imzada kayan değer/adet.
> Sonuncusu tasarımın asıl sebebi: boole tutan bir taban, havuz 2'den 1'e
> düşerken ya da taşma 57>54'ten 57>90'a büyürken sessiz kalırdı — bu
> DEVIR'in kendi "taban 8" hikâyesinin küçük bir tekrarı olurdu.
> Altı senaryoyla sınandı (bugünkü küme sessiz; yeni kırık, kaybolan kırık,
> adet değişimi ve iki ayrı değer sürüklenmesi bağırıyor).
>
> Gerekçelerden biri bu turda **yeniden ölçüldü**: `slidee`'nin iki katmanı
> gerçekten öksüz mü diye kayda değil dosyaya soruldu — `variety.story`'de
> 4 gerçek katman-açma tetikleyicisi var (`slide6`, `slideb`) ve `slidee`'nin
> o iki katmanına işaret eden **sıfır**. Arama mekanizmasının başka katmanları
> bulabildiği ayrıca görüldü, yani sıfır gerçek bir sıfır (K26).

`suit.py`: **14 adımın 13'ü yeşil, 1 kapı kırmızı** (`invariants`).

Kırmızı kalan üç kırığın **hiçbiri düzeltilecek kusur değil**, üçü de bilerek
açık bırakılmış sinyal:

- `40 harf: havuz 2 (taban 6)` — o etiket bandında donör çeşitliliği gerçekten
  yok. Susturmak sinyali gizlerdi (bkz. `GROWTH_LIMIT` yorumu).
- `slidee.xml/katman1` ve `katman2` taşması — tohumun **hiç bağlanmamış** iki
  katmanı; öğrenci onları görmüyor. B3'ün katman ekseni, kuyrukta.

Yenilenen tabanlar, hepsi gerekçeli: `golden` (dondurulmadan önce 0.9 puanlık
kanaryayla koruduğu doğrulandı), `EMPTY_BASELINE`, `deadband.BASELINE`,
`POOL_MEASURED`.

**`golden` bilerek dondurulmadı.** Dondurulacak dosyada bilinen bir taşma var
(B1 yeni bulgu) ve kusuru tabana yazmak tabanın koruyuculuğunu bozar.

**Kalan üç taban için ölçüm yapıldı ve teoriyi çürüttü.** "Yeni sabitler
tabanı geçersiz kıldı" varsayımı sınandı — her tur bir sabiti eski değerine
alıp `coverage.sweep()` tekrarlandı (her tur sabitin gerçekten değiştiğini
ve türetilmiş `LAYOUT_*`'ın yeniden hesaplandığını basıyor):

| tur | cover | section | content | bullets | steps | statement | menu |
|---|---|---|---|---|---|---|---|
| **TABAN** | 23 | 36 | 44 | 8 | 14 | 12 | 45 |
| bugün | 27 | 52 | 52 | 10 | 24 | 13 | 50 |
| `ratio` 0.72 | 27 | 51 | 52 | 10 | 24 | 13 | 50 |
| `safety` 1.00 | 31 | 54 | 54 | 8 | 29 | 13 | 52 |
| `leading` 1.20 | 45 | 36 | 65 | 8 | 30 | 13 | 58 |
| 0.72 + 1.20 | 45 | 40 | 65 | 8 | 30 | 13 | 58 |

Hiçbir tur tabanı geri getirmiyor: `CHAR_WIDTH_RATIO` neredeyse hiç
oynatmıyor, `LAYOUT_SAFETY`'yi kaldırmak **kötüleştiriyor**. Yani boş alan
artışı bu turda düzeltilen ölçüm sabitlerinden **gelmiyor**; sebep başka bir
yerde ve **aranmadan** taban yenilenmemeli. `EMPTY_BASELINE`'ı "eski zemin"
diye yazmak kolay ama ölçüm onu desteklemiyor.

**TEKRARLANDI, DOĞRU ZEMİNDE (2026-08-17).** Yukarıdaki ölçüm yanlış `vscale`
üstünde koşmuştu, yani çürütme şüpheliydi. Kanonik düzeltmeden sonra
tekrarlandı: **sayılar birebir aynı**. Sebebi de doğrulandı —
`coverage.sweep()` `bos.story` üzerinde koşuyor, **tutarlı 720/720** deck; o
uzayda eski `vscale(720)=1.000` ile yeni `v=540/540=1.000` aynı sayı,
dolayısıyla kanonik düzeltme bu fikstürleri hiç oynatmaz. **Çürütme
geçerli — artık şüphe değil, doğrulanmış.**

**İkinci kat: YERLEŞİM sabitleri de açıklamıyor.**

| tur | cover | section | content | bullets | steps | menu |
|---|---|---|---|---|---|---|
| TABAN | 23 | 36 | 44 | 8 | 14 | 45 |
| bugün | 27 | 52 | 52 | 10 | 24 | 50 |
| `MIN_CARD_H` 10.8→9.0 | 27 | 52 | 52 | 10 | 24 | 50 |
| `MAX_TYPE_SCALE` 1.7→2.4 | 27 | 52 | 52 | 10 | 24 | 50 |
| `MIN_LINE_CHARS` 22→40 | 27 | 52 | **60** | 10 | 24 | 50 |
| `TARGET_FILL` 0.62→0.85 | 27 | 52 | 52 | 10 | 24 | 50 |
| `CARD_GAP` 2.2→1.0 | 27 | 52 | 52 | **8** | 24 | 50 |

Üç sabit **sıfır etki**. Bu bir bulgu: `MAX_TYPE_SCALE` ve `TARGET_FILL`
`density_scale`'in iki kolu, ve kol çevirmek hiçbir şeyi oynatmıyorsa
mekanizma sorgulanmalı (K3: sıfır şüpheli sayıdır).

**`density_scale` ölçüldü ve bir kez YANLIŞ ölçüldü.** İlk sayaç dönüş
değeri yerine çağrı sonrası `page.scale`'i okudu — o, fonksiyonun kendi
`finally` bloğunda `base`'e geri alınıyor, yani **tanım gereği her zaman
1.0**. "Mekanizma dönmüyor" sonucu buradan çıkmıştı ve yanlıştı. Doğru
ölçüm:

```
density_scale cagrisi : 6      (42 slaydin 6'si -- 7 duzenin YALNIZCA BIRI)
DONEN olcek           : 1.7    (altisinda da)
DURMA SEBEBI          : MAX_TYPE_SCALE tavani
```

Yani mekanizma **tam kapasite çalışıyor** ve tavana dayanıyor. Tavanı 2.4'e
çekmenin hiçbir şeyi oynatmaması da açıklanıyor: `size_of` merdivene
`snap` ediyor, gövde 17pt × 1.7 = 28.9 → **26pt**; bir sonraki basamak 38pt
ve orada `MIN_LINE_CHARS` devreye girip büyümeyi kesiyor. **26 ile 38
arasında basamak yok**, dolayısıyla tavanı yükseltmek aynı puntoyu üretiyor.
`MAX_TYPE_SCALE` bugün **atıl bir sabit** — sınırlayan o değil.

**Sonuç: boş alan kayması temiz bir bilinmeyen.** Ölçüm sabitleri elendi
(doğrulanmış), yerleşim sabitleri elendi (ölçülmüş), doldurma mekanizması
pratik azamisinde çalışıyor. Taban yenilemesi hâlâ gerekçesiz; ya `content`
yapısal olarak %52 boş bırakıyor ya da taban başka bir yapısal rejimde
kaydedilmiş.

### Faz 3 — Tasarım (C1 → C2 → C3 → C4)

Bu faz hata düzeltme değil, yön kararı. Kaynak: E-Learning Heroes
**Course Starter Kits** (çok slaytlı setler — slaytlar arası ritmi orada
görebilirsin, tek şablonda göremezsin).

İlk ölçüm: o sette kaç farklı punto var ve aralarındaki oranlar ne?
Sonra dikey boşluklar hangi birimin katları.

Uyarı: şablonu **klonlama, tarif çıkar**. "Sol %38 görsel bandı, sağ %62 metin,
başlık gövdeden 2.2 kat büyük" gibi — içerik uzunluğundan bağımsız, mevcut
`height_for_label` / `fit_choices` altyapısına bağlanabilir bir tarif.
Klonlanan şablon içeriğine bağlı kalır ve sığmayan metinle bozulur.

---

## 4b. UI turlarının denetimi (2026-08-16)

`SetForegroundWindow`'un dönüş değeri hiçbir yerde kontrol edilmiyordu ve
Windows foreground lock yüzünden çağrı **sessizce başarısız oluyordu**. Ölçüldü:
çağrıdan sonra ön plandaki pencere hâlâ Chrome'du. Tuşlar kaybolmuyor,
**öndeki uygulamaya gidiyor.**

Geçmişte "üç UI turunda tuval açılmadı, odak kaçtı" diye kaydedilen şey
muhtemelen semptom değil, **sebebin kendisiydi.**

Hangi sonuç şüpheli, hangisi değil — ayrım, sonucun **tuşa mı okumaya mı**
dayandığı:

| sonuç | dayanağı | verdikt |
|---|---|---|
| **13pt / 38pt kalibrasyon bandı** | gözle sayım (ekrana bakıp satır sayma) | **şüpheli DEĞİL** — tuş gerekmedi |
| `grow=True` yuvarlak seferi | `save_and_close` → Ctrl+S | **geçersiz** (zaten biliniyordu; şimdi ikinci bağımsız sebep) |
| `shoot.py` ile alınmış her görüntü | — | **hiç kullanılmamış**: `PIL` venv'de kurulu değildi, yani araç bir kez bile koşmamış. Hiçbir sonuç ona dayanmıyor (DEVIR ve README tarandı). Odak körlüğü yine de düzeltildi, çünkü artık kullanılacak |
| `open_test` açılma verdikti | dosya kilidi + pencere başlığı (okuma) | **şüpheli DEĞİL** |
| `canary` sağlam/bozuk ayrımı | aynı okuma | **şüpheli DEĞİL** |
| panel'in kaydet-kapat döngüsü | Ctrl+S | güvenli tarafa düşüyordu (yıldız temizlenmeyince kapatmayı reddediyor), ama kaydetme hiç olmuyordu |

Düzeltme: `storyline_ctl.focus()` `AttachThreadInput` ile kilidi aşıyor ve
**`GetForegroundWindow` gerçekten hedefi gösteriyor mu diye doğrulayarak**
dönüyor. `_send_save`, `make_dirty` ve `shoot._front` odak alınamazsa
**tuş göndermiyor / görüntü üretmiyor**. Körlemesine tuş göndermek yasak:
gönderilen tuş kullanıcının öndeki uygulamasına gider.

---

## 4c. Sabitler hangi UZAYDA ölçüldü (2026-08-17)

K14'ün doğal sütunu. `GORUNUR_ALT = 458` yanlış değildi — **fazla
genelleştirilmişti**: 720'de ölçülmüştü ve 1920'de olmayan bir kısıtı
uyduruyordu (16:9 slayt oynatıcıda 4:3'ten kısa render olduğu için kareye
tamamen giriyor). `scale`'in %20 sapmasıyla aynı kök: tek uzayda ölçülmüş bir
sayının bütün uzaylarda geçerli sanılması.

Tek örnek değilmiş. Fikstür dosyalarının uzayları:

| dosya | uzay |
|---|---|
| `bos.story` | **720 tek başına** |
| `_canary/variety.story` | **720 tek başına** |
| `0_duz_kopya.story` | **1920 tek başına** |

Ve sabitler:

İki sütun gerekiyor: **hangi uzayda** ölçüldü, ve **hangi eksende** geçerli.
İkincisi `MEASURED_SCALE`'in tek çarpan olmasından çıktı — ölçüldüğünde yatay
ve dikey ayrıştı.

| sabit | uzay | eksen | durum |
|---|---|---|---|
| `CHAR_WIDTH_RATIO = 0.79` | **720 + 1920** | yatay | **kapandı** — iki uzayda da aynı |
| `MEASURED_HSCALE` | **720 + 1920** | yatay | ölçüldü; 2.667, formülle örtüşüyor |
| `MEASURED_VSCALE` | **720 + 1920** | dikey | ölçüldü; **2.99**, formülden %12 yüksek |
| `MEASURE_LEADING = 1.785` | **720** (iki koşu) | dikey | sağlam ama 1920'de bağımsız koşu yok |
| `MEASURE_PADDING = 0.0` | **720** | dikey | 1920'de ölçülmedi, **eksen sorusu sorulmadı** |
| boş satır ≈ dolu satır | **720** | dikey | 1920'de ölçülmedi |
| `CALIBRATED_RANGE (13–38)` | **720** | — | 1920'de ölçülmedi |
| `EMPTY_BASELINE`, `deadband` bandı | **720** | — | 720 sweep, tutarlı |
| `POOL_MEASURED`, `GROWTH_LIMIT` | `invariants.SLIDE = (720,540)` **sabit yazılı** | — | 1920'lik şablonları koruyor → **uzay uyuşmazlığı** |
| `golden` tabanı | **1920** | — | tutarlı |
| `GORUNUR_ALT = 458` | **720** | — | iki uzaya birden uygulanıyordu, **düzeltildi** |

**Dikey sapmanın yeri tartışmalı ve bu koda yazıldı.** Dikey/yatay oranı
2.99/2.667 = 1.12; `MEASURE_LEADING` 720'de 1.785, yani 1920'de fiilen
1.785 × 1.12 ≈ 2.0. Aynı olgu "dikey ölçek farklı" diye de yazılabilir,
"leading uzaya göre değişiyor" diye de. Mekanizma bilinmeden hangisi doğru
söylenemez. **En az iddialı yere** kondu: sapma satır adımında görülüyor,
orada tutuldu; `MEASURE_LEADING`'e dokunulmadı çünkü o iki bağımsız koşuda
doğrulanmış sağlam bir ölçüm.

**Varsayılan eksen yok.** Tek çarpan döndüren `space_scale` kaldırıldı; her
çağrı `hscale` ya da `vscale` diyerek eksenini açıkça söylüyor. Varsayılan
bırakmak, gözden kaçan bir çağrının sessizce yanlış eksende ölçeklenmesine
izin verirdi — son üç turda kovalanan hata sınıfının tam kendisi.

**En ciddi satır sondan üçüncü:** `invariants.py`'de `SLIDE = (720.0, 540.0)`
sabit yazılı ve donör provası ile `check_fit_choices` onu kullanıyor — ama
korudukları soru şablonları `0_duz_kopya`'dan geliyor, yani **1920**.
`GROWTH_LIMIT`'in havuzu 40 harfte 1'e düşürmesi de bu uzayda ölçüldü.

Yani `GROWTH_LIMIT` kararı verilmeden önce prova uzayının düzeltilmesi
gerekiyor; aksi halde 720'de ölçülmüş bir dağılıma göre 1920'lik şablonlar
hakkında karar verilir.

---

## 4d. Ölü dal silindi (2026-08-17) — ve barındırdığı iki kusur

`apply_choice_plan` / `fit_choices`'in plan yolu silindi. Gerekçe zinciri:

- üretimde **0/4** kullanılıyordu (ölçüldü, B2)
- koruma gerekçesi (`golden` onu donduruyor) `golden`'a **canlı dal vakası**
  eklendiğinde kalktı
- iki bağımsız kusur barındırdığı ölçüldü (aşağıda)
- düzeltilse bile arkasından `GROWTH_LIMIT` prova uzayı, `check_fit_choices`'in
  720 varsayımı ve üç `golden` vakası geliyordu — hepsi çalışmayan bir yol için

**Kodu silmek bulguyu silmez.** Ölü dalın barındırdığı iki kusur, canlı dalda
tekrar edebilecek hata sınıflarıdır:

1. **Sabit genişlik varsayımı.** `fit_choices`'e şık genişliği olarak içerik
   bandının %84'ü veriliyordu (1613 birim); şablonun gerçek şık genişliği 497.
   Varsayımın %31'i. Dar kutuda metin kat kat fazla satıra sarar, planın
   ayırdığı yükseklik o oranda yetersiz kalır. Ölçülen taşma: **%356** (eski
   sabitler), **%662** (yeni sabitler).
2. **Yüzde plan yanlış uzaya uygulanıyordu.** `apply_choice_plan` çağrısında
   slayt boyutu `(720.0, 540.0)` **elle yazılıydı**, oysa `package_slide_size`
   doğru değeri (1920×1080) zaten döndürüyordu. Plan `box_h = %15.73` olarak
   geliyor; 540'a uygulanınca 85 birim, 1080'e uygulanması gerekirdi → 170.
   Kutu **tam yarısı** kadar yapılıyordu.

İkisi de aynı sınıf: **bir uzayda doğru olan sayının başka bir bağlama elle
taşınması** — `GORUNUR_ALT` ve tek-eksenli `scale` ile aynı kök. Bu sınıf bu
oturumda **dört kez** çıktı.

### 4d-bis. Silme fazla oldu — `fit_choices` yeniden yazıldı

`fit_choices` ölü değildi: `pick_template` onu **şablon kabul testi** olarak
çağırıyor ve canlı yol oradan geçiyor. Ölü olan yalnızca `apply_choice_plan`,
yani planın **diske uygulanması**. Planın **üretilmesi** hâlâ gerekli çünkü
"bu şablon bu şıkları alır mı" sorusunu o cevaplıyor. Kaynak kurtarılamadı;
ayrıntı ve genel kural **K15**'te.

**Yeniden yazıldı (b yolu): sözleşme aynı, gövde yeni, davranış eşdeğerliği
DOĞRULANMADI ve doğrulanamaz** — karşılaştırılacak şey yok. `golden` ve
`deadband` tabanları **silme öncesinde** alındı ve bu gövdeyi hiç görmedi;
onları "bu kodun sınanmış olduğunun kanıtı" saymayın.

Yeniden yazmanın kazandırdıkları, kaydı için:

| konu | silinen sürüm | yeni gövde |
|---|---|---|
| uzay çarpanı | `slide_w / 720`, **tek** sayı iki eksende | ölçek matematiği yok; `layout_text_height`'a soruyor (yatay `hscale`, dikey `vscale`) |
| küçültme | punto "bir eksilt" | `step_down` — merdivende bir basamak |
| kapsam | plan üretir, `apply_choice_plan` uygular | yalnızca kabul testi; dönen ölçüler **rapor** |
| gerekçe | red gerekçeli | red gerekçeli **+ aşılan tabanı adıyla söyler** |

**Tabanların zemini ayrı ayrı kaydedildi (K14):**

- `MIN_CHOICE_GAP = 1.6` — **zemini doğrulanmadı.** Nereden geldiği bilinmiyor;
  ne tıklama hedefi ölçümüne ne bir göz turuna bağlı. "Sıfır olmasın" gerekçesi
  bir tabanın *olmasını* gerektirir, **1.6 olmasını değil**. `GROWTH_LIMIT`
  ile aynı sınıf.
- `MIN_CHOICE_SIZE` — artık kopya değil, **bağlı**: `shapes.CALIBRATED_RANGE[0]`.
  Bir dönem `13.0` yazılı bir sabitti ve yanındaki yorum bağlı olduğunu
  *söylüyor* ama bağlı *değildi*. Değer bugün değişmedi; değişen, yarın sessizce
  ayrışamayacak olması.
- `CHOICE_GAP_LINES = 0.5` — **yeni yargı**, devralınmış değil. Rahat boşluk
  sabit yüzde yerine yarım satırdan türetiliyor, böylece punto kısılınca boşluk
  da kendiliğinden kısılıyor. Ölçüm değil, seçim — ama tek puntoya çakılı değil.

**Yerine gelen kontrol:** `invariants.check_choice_admission`, dört yönlü —
sığan kabul edilmeli, taşan reddedilmeli, red **tabanı adıyla** söylemeli, ve
aynı girdi iki uzayda **farklı** sonuç vermeli (eksen çarpanı gerçekten
koşuyor mu; K3).

**İkinci kayıp, aynı turdan:** `invariants.MOTOR_SABITLERI` ve
`ESIK_ISTISNALARI` de silinmiş — `check_thresholds_independent` `NameError`
veriyordu. Elle liste **konmadı**; küme artık `compose` ve `shapes`'in modül
düzeyindeki sayısal sabitlerinden **türetiliyor**, çünkü elle liste bu
kontrolün kendi hatasını taşır (yeni sabit listeye girmezse sessizce geçer).
İstisna listesi **boş** başlatıldı ve bu bir iddiadır. Türetilmiş küme **ilk
koşusunda iş gördü**: yeni yazdığım `check_choice_admission`'ın eşiğini
`compose.MIN_CHOICE_SIZE`'den okuduğunu yakaladı → `EXPECTED_CHOICE_SIZE_FLOOR`
eklendi. Aynı ders üçüncü kez.

**Canlı dal da taranmıştı ve temiz çıkmadı:** `compose._Page.line_chars` ve
`compose` içindeki satır-genişliği hesabı `self.width / 720` formülünü
kullanıyor. Bunlar **yatay** hesap ve yatayda ölçülen çarpan zaten 2.667 =
width/720 — yani doğru eksende doğru formül, ama kaynağı taşımıyordu;
`hscale()`'e çevrildi. `preview.py`'nin `pt * (sw/720)` çizimi ise **dikey**
kullanım ve ölçülen 2.99'a göre 1920'de yazıyı ~%12 küçük çiziyor — önizlemenin
sadakat notuna eklenecek yedinci madde.

---

## 5. Kabul edilmiş sınırlar — bunlar hata değil

Bunları "düzeltmeye" kalkma; gerekçeleri kodda yazılı.

- **Kalibrasyon bandı 13–38pt.** Üstü ölçülmedi. Ölçek bandın üstüne çıkmıyor:
  boşluğu doldurmak için doğruluğu harcamak yanlış takas. Bandı genişletme
  denemesi bir kez yapıldı ve **deney geçersizdi** (Storyline hiç yazmadı,
  çünkü belge kirletilmemişti). Yol kapalı değil, ölçüm hiç yapılmadı.
- **Üç yatay şablon seçilemiyor.** Sığdırma modeli yalnızca dikey yığını
  kapsıyor. `known_template_limits` kanalında, envanter olarak.
- **`menu` %45 boş.** Üç turda ölçüldü: konumdan da boyuttan da gelmiyor.
  Üç tek kelimelik etiket 16:9'u dolduramaz. Çözüm bir özellik (seçimlere
  gövde/ikon vermek), yerleşim ayarı değil.
- **Yoğunluk ölçeği yalnızca `content` dalında.** Diğer düzenler seyrek
  içerikte puntoyu büyütmüyor.
- **`cover` %23 boş** — tamamı tasarlanmış kenar payı. Burada iş yok.
- **Dosya turu ile metin yüksekliği ÖLÇÜLEMEZ.** (2026-08-16, kanıtlandı)
  Fikir şuydu: kutuları `autoFit="resize"` ile yaz, Storyline'da aç-kaydet-kapat,
  büyümüş yüksekliği dosyadan geri oku. Bu tur **kapı açıkken** koşuldu —
  `dirty_gate` dosyanın gerçekten değiştiğini gösterdi (2 216 749 → 1 014 646
  bayt, Storyline paketi baştan yazdı). Yine de 40 kutunun 40'ı da **tam
  yazıldığı boyutta** kaldı; 38pt'de metin 144 birim isterken kutu 44'te durdu.
  Bayrak korunmuş (`autoFit="resize"` hepsinde duruyor) ama hesaplanan
  yükseklik dosyaya geri yazılmıyor: **dosya yazılan kutuyu tutuyor, çizilen
  kutuyu değil.** Yol kapalı — ölçmek için görüntü gerekir, dosya değil.
  `calibrate_diacritics.py --olc` artık bu durumu tespit edip **raporu hiç
  basmıyor**; yoksa "+0.00" dolu bir tablo "diakritik etkilemiyor" diye
  okunurdu.
- **Rubrik 1.5–2 puanın altını göremez.** Daha küçük değişimleri onunla ölçme.
- **Rubrikte sıra etkisi ölçülmedi** — "yok" değil, ayrılamadı.
- **Video, Storyline'da AÇILARAK doğrulanmadı** (2026-08-29). `media.add_video`
  dosya biçimini gerçek bir kurstan geri çıkararak yazıyor
  (`test/0_duz_kopya.story`, iki video) ve yapının her bağı ölçülüyor:
  `tools/medya_probe.py` baytı, `<video>` kaydını, ilişkiyi, şekli, süreyi ve
  oranı geri izliyor; `mp4_info`'nun süresi/kare hızı/pikseli Storyline'ın aynı
  dosyaya yazdığı sayılarla birebir. **Ölçülmeyen tek şey ekran:** dosya
  Storyline'da açılıp video oynatılmadı. Yani "geçerli paket" kanıtlandı,
  "editörde sorunsuz görünüyor" kanıtlanmadı. İlk gerçek videoyu ekledikten
  sonra Storyline'da bir kez açıp bakın; sorun çıkarsa ilk şüpheli **poster**
  (`thumbG`, düz renk PNG olarak üretiliyor — Storyline gerçek bir kare
  çıkarıyor) ve **`.mpeg` uzantısı altındaki MP4 baytları**.
- **Yalnızca `.mp4`/`.m4v`.** `<video>` kaydının `type` alanı için başka bir
  değer ölçülmedi; `.mov`/`.webm` uydurmak yerine reddediliyor.
- **`set_background` artık önceki zemini SİLİYOR, altına koymuyor** — ama bunun
  bir probe'u yok. Eski davranışta `to_back` yeni dikdörtgeni en alta koyuyordu,
  yani ikinci çağrı sessizce etkisizdi (ölçüldü 2026-08-29: kullanıcının kapak
  slaydında iki tam sayfa zemin üst üste, görünen eskisi). Düzeltildi ve elle
  ölçüldü; `tools/` altında `set_background`'ı sınayan bir dosya olmadığı için
  invaryant bırakılamadı.
- **Kırpma Storyline'da açılarak doğrulanmadı** (2026-08-29). `fit="cover"`
  baytı Pillow ile kesiyor ve `tools/medya_probe.py` yerleşen baytın oranının
  kutunun oranına eşit olduğunu ölçüyor — yani "gerilmiyor" kanıtlandı,
  "editörde istenildiği gibi görünüyor" kanıtlanmadı.
- **Medya isteğini artık panel seçiyor** (`builder._medya_plani`): nereye ve
  kaç tane kurucunun deterministik kararı, ne olsun modelin. Sebep ölçüldü —
  2026-08-29'da üretilen kursta (`zamanynt.story`, 13:39) `<kurs>.medya.json`
  hiç oluşmadı, model tek bir istek yazmamıştı. **Yoğunluk (≈ slayt/6) bir
  yargı, ölçüm değil**: doldurulmayan her istek slaytta boş bir bant bırakıyor,
  o yüzden düşük tutuldu.
- **Üretilen kursta slayt boyutları KARIŞIK.** Ölçüldü 2026-08-29
  (`denee.story`, 25 slayt): proje 1920×1080 bildiriyor, içerik slaytları
  720×540, soru slaytları 1920×1080. Sebep: soru slaytları `seeds/` altındaki
  1920×1080 bir kurstan hasat edilmiş tohumlardan klonlanıyor, içerik slaytları
  ise kaynak dosyanın 720×540 şablonundan. **Storyline'da nasıl göründüğü
  ölçülmedi** — düzeltilmesi gerekip gerekmediği de bu yüzden açık. Medya
  siparişi artık her hâlükârda o slaydın kendi çerçevesini kullanıyor, yani bu
  karışıklık en azından yanlış boyut istemiyor.
- **Okunabilirlik artık uygulamada garanti** (`compose.ensure_scrim`), çünkü
  görsel üç yoldan giriyor ve garanti yalnızca kurucudaydı. **Örtünün rengi
  paletten geliyor, fotoğraftan değil**: açık bir fotoğrafta koyu örtü işe
  yarıyor, ama koyu bir fotoğrafta koyu örtü ikisini birden karartıyor —
  fotoğrafın kendi parlaklığına bakan bir ölçüm yok.
- **Görsel görünmemesinin İKİ sebebi vardı, ikisi de sessizdi.** Birincisi
  kaydın yanlış listede olması (aşağıda), ikincisi kaydın **parçayı** anlatması:
  `origFile`/`source` boş, `modDT` sıfır tarih, `bytes` parçanın boyutu, iki md5
  aynı. Storyline'ın kendi kaydı bunların hepsinde **diskteki dosyayı** anlatıyor.
  Alanlar hizalanınca aynı baytlar aynı slaytta göründü (MEDYA_TESTI_5/6).
  **Hangi alanın belirleyici olduğu ayrılmadı** — beşi birlikte değişti.
- **Kayıt yerinin kendisi de yanlıştı.**
  `<media>`/`<video>` kayıtları `mediaLst > mediaLst` içinde durur (dört gerçek
  kursta dördü de öyle); kod dıştaki listeye yazıyordu. Paket geçerli, doğrulama
  temiz, bağ zinciri eksiksiz — ama Storyline kaydı görmüyor. **Hiçbir görsel
  hiçbir kursta görünmemişti** ve bunu ancak kullanıcı bildirdi. Format
  şüphesi (JPEG mi?) ölçümle elendi: aynı slaytta JPEG de PNG de görünmedi.
  Artık `tools/medya_probe.py` kaydın yerini de ölçüyor. **Storyline'da
  doğrulaması bekliyor** — `MEDYA_TESTI_2.story` bunun için.
- **`atla` boş bandı kapatmıyor.** Bir istek listeden düşürüldüğünde slayt
  olduğu gibi kalır — `image_area` ile ayrılmış alan boş durur. Doğrusu o
  slaydı medyasız yeniden kurmak olurdu; yapılmadı.

---

## 6. Çalışma biçimi

- Tek fazı bitirmeden diğerine geçme.
- Çekirdek fonksiyona dokunduysan regresyonu koş (K10).
- Açılış fazı (~25 dk) pahalı: birden çok değişikliği biriktirip tek seferde
  koş, ama bozulursa ayırt edilebilecek kadar farklı yerlere dokunsunlar.
- Her düzeltme bir invaryant bırakmalı. Aynı hata ikinci kez sessizce
  dönebiliyorsa iş bitmemiştir.
- Bir şeyi ölçemiyorsan, ölçmüş gibi gösterme. "Ayrılamadı" geçerli bir
  cevaptır; "yok" değildir.
