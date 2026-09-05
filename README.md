# Storyline Panel

Bir brief yazarsınız, panel Articulate Storyline kursunu kurar.

Storyline'ın eklenti/script API'si yok. Bu proje `.story` dosyasını ne olduğu
üzerinden — bir OPC paketi, yani `.pptx` ile aynı ZIP + XML mimarisi — doğrudan
okuyup yazar. Arayüz taklidi yok, dolayısıyla kırılganlık da yok.

## Ne yapar

Panelde tek bir metin kutusu var ve yazdığınızın uzunluğuna göre iki yoldan
biri çalışır:

**Brief yolu** — kapsamı ve başlıkları içeren uzun bir metin yapıştırırsınız.
Panel önce iskeleti tasarlatır, sonra bölüm bölüm içerik yazdırır, sonra kursu
**deterministik olarak** kurar. Model yalnızca JSON üretir; slaytları, soruları
ve tetikleyicileri kod kurar. Dokuzuncu slaytta çıkan bir hata ilk sekizi
bozamaz.

**Komut yolu** — kısa bir istek yazarsınız ("3. slaydın başlığını değiştir").
Ajan MCP araçlarıyla dosyayı düzenler.

Ayrıca panelde: kurs künyesi (süre, hedef kitle, ton, bölüm başına soru),
altı hazır tema ya da özel renk, puanlanan sorular ve geri bildirim katmanları,
görsel/video sipariş defteri, sahne/slayt/soru dökümü, Storyline'da açma.

Beş soru tipi seçilebilir ve hepsi kuruluyor: tek seçmeli, çok seçmeli,
sürükle-bırak (gruplama), sıcak nokta ve metin girişi/taahhüt.

## Gereksinimler

| | |
|---|---|
| Windows | `.bat` başlatıcı ve Storyline Windows'ta |
| Articulate Storyline 360 | kursu açmak ve yayınlamak için |
| Python 3.10+ | |
| [Claude Code CLI](https://claude.com/claude-code) | panelin model çağrıları bunun üzerinden gider; kurulu ve oturum açmış olmalı |
| WebView2 | Edge ile birlikte gelir, ayrıca kurmanız gerekmez |

## Kurulum

```powershell
git clone https://github.com/efee7946-cmd/storyline_MCP.git
cd storyline_MCP\storyline-mcp
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[panel]"
```

`[panel]` ekini **atlamayın**: `pywebview` onunla gelir ve o olmadan panel
açılmaz.

Sanal ortam tam olarak `storyline-mcp/.venv` olmalı. Hem başlatıcı `.bat`
hem de panelin ürettiği MCP kaydı bu yolu sabit tutar. MCP sunucusunu Claude
Code'a ayrıca kaydetmeniz gerekmez — panel yapılandırmayı her çalıştırmada
kendisi üretir.

**Temiz klonda doğrulandı (5 Eylül 2026).** GitHub'dan yeni klonlanmış bir
depoda yukarıdaki iki komut koşuldu ve ölçüldü: 113 paket kuruldu,
`panel/app.py` import edildi, panel Claude Code CLI'ı buldu, beş soru tohumu
biçiminin hepsi yerindeydi ve MCP sunucusu el sıkışıp **51 araç** bildirdi.
Yani depoyu klonlayan biri paneli aynı şekilde kullanabilir.

## Çalıştırma

Depo kökündeki **`Storyline Panel.bat`** dosyasına çift tıklayın.

## İlk kurs

1. **Storyline'da bir proje açıp kaydedin.** Panel var olan bir `.story`
   dosyasının *içine* kurar; depoda hazır dosya yok. Projenin en az bir
   slaydı olsun — panel içerik slaytlarını ondan çoğaltır.
2. Panelde **Dosya seç**.
3. **Kurs künyesi**ni doldurun. Boş bıraktığınız alan iddia edilmez; süre
   slayt sayısını, "bölüm başına soru" ise soru sayısını doğrudan belirler.
4. Brief'i yapıştırıp gönderin. Akış şeridi ne yapıldığını canlı yazar.

Dosya Storyline'da açıkken kurulum yapılamaz; panel kilit uyarısı verir.

## Panel açılmıyorsa

`.bat` artık eksik kurulumu söyleyip bekler. Başka bir sebep varsa panel
`pythonw.exe` ile başladığı için hata hiçbir yere düşmez — konsollu
çalıştırın, gerçek sebep orada yazar:

```powershell
storyline-mcp\.venv\Scripts\python.exe storyline-mcp\panel\app.py
```

`Klonlanacak bir icerik slaydi yok` hatası alırsanız seçtiğiniz `.story`
dosyasında hiç içerik slaydı yoktur; Storyline'da bir slayt ekleyip kaydedin.

## Depoda olmayanlar

| Yok | Neden | Kaybedilen |
|---|---|---|
| `storyline-mcp/donors/` | üçüncü tarafın telifli Storyline projeleri | butonların kurstan kursa değişmesi |
| `test/`, `storyline-mcp/test/` | 2.3 GB fikstür; yerelde üretiliyor | kontrol paketi koşamaz |
| `.venv/`, `__pycache__/` | kurulum artığı | — |

**Kurs kurulumu bunların hiçbirini gerektirmez.** Soru slaytları, şekiller,
katmanlar, tetikleyiciler ve sonuç slaydı `storyline_mcp/seeds/` içinde ve
depoda; içerik slaytları zaten sizin kendi `.story` dosyanızdan çoğaltılıyor.
Klonlanmış bir depoda tam bir kurs kurulduğu ölçüldü: 4 bölüm, 12 slayt,
4 puanlı soru, 3 farklı soru görünüşü, paket doğrulaması temiz.

İki bedeli var ve saklamıyoruz:

- **Kontrol paketi koşmaz.** `tools/suit.py` fikstürleri okuyor, onlar burada
  değil. Kodu kullanabilirsiniz, doğrulayamazsınız.
- **Butonlar tek görünüşe iner.** `shapes.find_seed` sırayla projeye, donör
  havuzuna, sonra gömülü tohuma bakar. Havuz yokken her kurs aynı gömülü
  butonu giyer — ölçüldü: havuzla üç kurs üç farklı donörden buton alıyor,
  havuzsuz üçü de `bundled`. Diğer şekiller (`rect`, `textBox`) zaten her
  iki durumda da gömülü tohumdan geliyor, yani orada fark yok.

  Kod bu düşüşü **haber vermez**: uyarı yalnızca havuz var ama uygun aday
  yokken çıkar, havuz hiç yokken sessizdir. Buton çeşitliliği istiyorsanız
  kendi Storyline projelerinizi `storyline-mcp/donors/` içine koyun ya da
  `STORYLINE_DONORS` ortam değişkeniyle başka bir klasör gösterin.

## Bilinen sınırlar

- **Şablonun seçenek sayısı bağlayıcıdır.** 4 seçenekli bir soru şablonu 4
  seçenekli soru üretir; seçenek eklemek/çıkarmak sıfırdan şekil ve durum
  üretmek demek ve bu yapılmıyor.
- **Animasyon sözlüğü ölçülenle sınırlı.** `fade`, `fly`, `wipe`, `growTurn`,
  `random` çalışır — bunlar donör havuzundaki 1527 yuvanın dolu olan 74'ünden
  çıkarıldı. Havuzda görülmeyen bir efekt tahmin edilerek yazılmaz.
- **Buton çeşitliliği donör havuzuna bağlı.** Havuz yokken her kurs aynı gömülü
  butonu giyer — gerekçesi ve ölçümü "Depoda olmayanlar" bölümünde.

Eskiden burada yazan iki sınır artık geçerli değil: sürükle-bırak, sıcak nokta
ve metin girişi için tohum **var** ve kuruluyor; timeline animasyonu da
`storyline_mcp/anim.py` ile geldi.

## Depodaki diğer dosyalar

- **`storyline-mcp/README.md`** — mimari, `.story` metin modeli, ölçüm
  gerekçeleri. Asıl teknik belge burası.
- **`DEVIR.md`**, **`JS_YOL_HARITASI.md`** — geliştirme günlüğü ve JavaScript
  yetenek haritası. Kullanmak için gerekmez.
