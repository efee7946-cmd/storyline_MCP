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

## Gereksinimler

| | |
|---|---|
| Windows | `.bat` başlatıcı ve Storyline Windows'ta |
| Articulate Storyline 360 | kursu açmak ve yayınlamak için |
| Python 3.10+ | |
| [Claude Code CLI](https://claude.com/claude-code) / Antigravity (`agy`) | panelin model çağrıları öncelikli Claude Code CLI'ı, eksikliğinde veya kota aşımında otomatik Antigravity (`agy`) CLI fallback'ini kullanır |
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

- **Soru tipleri sınırlı.** Tek ve çok seçmeli çalışıyor. Sürükle-bırak, metin
  girişi ve sıcak nokta için klonlanacak örnek yok.
- **Timeline animasyonu yok.** Taranan 62 dosyanın hepsinde `animEffect` boş;
  kopyalanacak çalışan bir örnek bulunamadı.
- **Şablonun seçenek sayısı bağlayıcıdır.** 4 seçenekli bir şablon 4 seçenekli
  soru üretir.

## Depodaki diğer dosyalar

- **`storyline-mcp/README.md`** — mimari, `.story` metin modeli, ölçüm
  gerekçeleri. Asıl teknik belge burası.
- **`DEVIR.md`**, **`JS_YOL_HARITASI.md`** — geliştirme günlüğü ve JavaScript
  yetenek haritası. Kullanmak için gerekmez.
