# Antigravity (agy) & Storyline MCP — Geliştirme ve Mimari Raporu (31 Ağustos 2026)

Bu doküman, 31 Ağustos 2026 tarihinde **Articulate Storyline MCP**, **Storyline Panel UI** ve **Antigravity CLI (`agy.exe`)** entegrasyonu kapsamında yapılan tüm mimari güncellemeleri, kök neden analizlerini ve hata düzeltmelerini detaylı olarak içermektedir.

---

## 1. Genel Özet

Bugün gerçekleştirilen çalışmalar 4 temel başlıkta toplanmıştır:
1. **Storyline Dosya Bozulma (`Corrupted .story`) Hatalarının Kökten Çözülmesi:** Klonlanan/oluşturulan slaytlardaki eksik `.rels` ilişki dosyaları ve yetim kalan `layoutG` düzen GUID'leri otomatik onarım mekanizmasıyla tam korumaya alındı.
2. **Antigravity CLI (`agy.exe`) Abonelik Failover ve MCP Entegrasyonu:** Claude Code abonelik erişimi engellendiğinde sistemin kesintisiz biçimde `agy.exe` motoruna geçmesi, Storyline MCP araçlarının `agy` sunucusuna otomatik kaydedilmesi ve ajan talimatlarının (`SYSTEM_PROMPT`) ön ekli araç isimleriyle tam uyumlu hale getirilmesi sağlandı.
3. **Panel UI & Kullanıcı Deneyimi İyileştirmeleri:** Gereksiz JS Yetenekleri sekmesi UI'dan kaldırıldı, kurs künyesine çoklu soru tipi seçimi eklendi ve kalıntı `populateSlideSelects` ReferenceError hatası temizlendi.
4. **Bütünsel Test ve Otomasyon:** Canlı Windows ekran pencereleri yakalanarak Storyline'ın verdiği hata diyalogları anlık olarak analiz edildi ve `tools/open_test.py` test mantığı iyileştirildi.

---

## 2. Kritik Hata Düzeltmeleri ve Kök Neden Analizleri

### 2.1. Slayt `.rels` İlişki Dosyası Zorunluluğu (File Corruption)
* **Kök Neden:** Articulate Storyline, paket içerisindeki her bir slayt XML dosyası (`story/slides/slideN.xml`) için mutlaka karşılık gelen bir ilişki dosyası (`story/slides/_rels/slideN.xml.rels`) olmasını şart koşar. Tohum paketlerden eklenen Single Choice, Multiple Choice, Drag & Drop, Hotspot vb. sorular klonlandığında slayt XML'i yazılıyor fakat `.rels` dosyası oluşturulmuyordu. Storyline açılışta bu dosyayı bulamadığı an paketi "bozuk" ilan ediyordu.
* **Çözüm:**
  - `storyline_mcp/clone.py` içerisinde `install_slide` ve `clone_slide` fonksiyonları güncellendi. Yeni eklenen her slayt için geçerli bir `.rels` ilişki dosyası oluşturulması zorunlu kılındı.
  - `storyline_mcp/package.py` içerisindeki `StoryPackage.save()` metoduna oto-kontrol eklendi. Kayıt esnasında eksik kalan slayt `.rels` dosyaları otomatik tamamlanmaktadır.

### 2.2. Yetim Düzen Kimlikleri (Orphan `layoutG` GUIDs) ve Otomatik Düzen Onarımı
* **Kök Neden:** Farklı tohum paketlerden (`question_dragDropIntr_9.xml`, `question_freePickManyIntr_5.xml` vb.) veya şablonlardan klonlanan slaytlar, geldikleri paketin `layoutG` kimliklerini (ör. `8fac9ea8-7476-4019-b2b8-43815f68fa8a`) taşıyordu. Ana projenin `story/slideLayouts/` klasöründe bu GUID karşılığı bulunmadığında, Storyline açılışta canlı olarak şu hatayı veriyordu:
  > *"This project is invalid or corrupt and cannot be opened. It may have been created in an earlier version of Storyline."*
* **Çözüm:**
  - `storyline_mcp/package.py` sınıfına `_fix_orphan_layouts()` metodu eklendi. Kayıt sırasında projedeki geçerli düzen GUID'leri haritalanır ve yetim kalan `layoutG` kimlikleri projenin kendi uyumlu düzen kimlikleriyle (içerik slaytları için "Title and Content", sorular için "Question") otomatik eşleştirilir.
  - `verify()` metoduna yetim `layoutG` kontrolü eklenerek paket sağlığı garantiye alındı.

### 2.3. Panel UI `populateSlideSelects is not defined` ReferenceError
* **Kök Neden:** JS Yetenekleri sekmesi UI'dan kaldırıldığında ilgili JS kodu silinmişti ancak `panel/index.html` içerisindeki `renderSummary()` fonksiyonunda `populateSlideSelects(data.scenes)` çağrısı unutulduğu için konsolda `ReferenceError` oluşuyordu.
* **Çözüm:** `panel/index.html` içerisindeki kalıntı `populateSlideSelects` satırı temizlendi.

### 2.4. OpenTest Pencere Başlığı Eşleşme Mantığı
* **Kök Neden:** `tools/open_test.py` otomatik test betiği, Storyline açıldığında pencere başlığında dosya adını arıyordu. Ancak Storyline pencere başlığına `.story` uzantısını koymadan dosya kök adını (`path.stem`) eklediği için `open_test.py` açılan sağlam dosyaları bile `HAYIR` olarak işaretliyordu.
* **Çözüm:** `open_test.py` içerisindeki başlık kontrolü `path.stem.casefold() in title.casefold()` olarak güncellendi.

---

## 3. Antigravity CLI (`agy.exe`) Entegrasyonu ve Abonelik Failover Sistemi

### 3.1. Proaktif Claude Code Abonelik Testi (`check_claude_working`)
* Claude Code (`claude.exe`) abonelik erişimi kısıtlandığında (`403 Forbidden` / `organization has disabled claude subscription access`), kullanıcının hata almasını önlemek için `panel/agent.py` içerisine hızlı proaktif test eklendi.

### 3.2. Antigravity CLI (`agy.exe`) Otomatik Yönlendirmesi (Failover)
* `claude.exe` çalışmadığında veya engellendiğinde, `panel/agent.py` içerisindeki `find_cli_info()` ve `panel/builder.py` içerisindeki `_run_json` işlemleri otomatik olarak `Antigravity CLI (agy.exe)` (`C:\Users\erman\AppData\Local\agy\bin\agy.EXE`) üzerine devredilir (`_CLAUDE_DISABLED = True`).

### 3.3. Storyline MCP Araçlarının `agy` Üzerine Otomatik Kaydı (`ensure_agy_mcp_registered`)
* `agy.exe` ilk yüklendiğinde Storyline MCP sunucusundan habersizdi (`No MCP servers configured`).
* `panel/agent.py` içerisine `ensure_agy_mcp_registered()` eklendi. Ajan başlatıldığında `agy mcp add storyline <python> <server.py>` komutunu arka planda çalıştırarak Storyline MCP araçlarını `agy` CLI'ına otomatik ve kalıcı olarak bağlar.

### 3.4. System Prompt Ön Ek Uyumlaştırması (`mcp__storyline__*`)
* `agy` CLI, MCP araçlarını `mcp__storyline__<tool_name>` ön ekiyle çalıştırır. Modelin araçları bulamadım yanılsamasına düşmemesi için `panel/agent.py` içerisindeki `SYSTEM_PROMPT` güncellendi ve tüm Storyline MCP araç isimleri (`mcp__storyline__list_slides`, `mcp__storyline__add_slide`, `mcp__storyline__add_question` vb.) açıkça tanımlandı.

---

## 4. Kullanıcı Deneyimi ve Panel UI İyileştirmeleri

### 4.1. Kurs Künyesinde Çoklu Soru Tipi Seçimi (`qTypesBox`)
* Kurs künyesine çoklu soru tipi seçimi eklendi:
  - Tek Seçmeli (`single`)
  - Çok Seçmeli (`multiple`)
  - Sürükle-Bırak (`drag`)
  - Sıcak Nokta (`hotspot`)
  - Metin Girişi & Taahhüt (`commitment`)
* Seçilen soru tipleri `courseProfile()` üzerinden toplanarak `builder.py` istemlerine (`_question_rule`) otomatik aktarılır.

### 4.2. JS Yetenekleri Sekmesinin Temizlenmesi
* Kullanıcı talebi doğrultusunda UI üzerindeki karmaşık JS Yetenekleri sekmesi kaldırıldı; JS gereksinimlerinin panel tarafından ihtiyaç duyulduğunda otomatik yönetilmesi ilkesi benimsendi.

---

## 5. Önemli Paket İnvariantları ve Teknik Kurallar (Cheat Sheet)

1. **Paket İlişki İnvariantı:** Her `story/slides/slideN.xml` dosyası için `story/slides/_rels/slideN.xml.rels` bulunmalıdır.
2. **Düzen Kimlik İnvariantı:** Her `slideN.xml` dosyasındaki `layoutG` GUID değeri, `story/slideLayouts/` içerisindeki bir düzen XML'inin `g` değeriyle birebir eşleşmelidir.
3. **BOM İnvariantı:** Paketteki XML ve `.rels` dosyaları UTF-8 BOM (`\xef\xbb\xbf`) ile başlamalıdır (`_normalise_boms()` bunu otomatik sağlar).
4. **Antigravity CLI Çalışma Kuralı:** `agy` CLI ile çalışırken MCP araçları `mcp__storyline__` ön eki ile çağrılmalıdır.

---

## 6. Yapılan Git Commit'leri Özeti

| Commit Hash | Mesaj / Açıklama |
| :--- | :--- |
| `c89b7c8` | `refactor: Remove JS capabilities tab and section from panel UI` |
| `1a52f2a` | `feat: Add multi-select question types to course profile in panel UI & enforce in builder prompts` |
| `6758804` | `feat: Add proactive Claude Code probe & seamless fallback to Antigravity CLI (agy)` |
| `e880b10` | `fix: Catch claude execution failures in builder._run_json and fallback to agy CLI` |
| `0723a07` | `fix: Ensure every slide XML part always gets a valid .rels file in package save and clone operations` |
| `ce2923a` | `fix: Remove unused populateSlideSelects call in panel/index.html renderSummary` |
| `d3c5542` | `feat: Auto-register storyline MCP server in Antigravity (agy) CLI for seamless command execution` |
| `f9e0b2d` | `fix: Add explicit mcp__storyline__ tool names to SYSTEM_PROMPT to ensure agy CLI recognizes MCP tools` |
| `f343ace` | `fix: Support window titles without extension in open_test.py title matching` |
| `c956162` | `fix: Auto-repair orphan slide layoutG GUIDs in StoryPackage.save() to prevent Storyline corruption error` |

---
*Rapor Sonu — Tüm geliştirmeler test edilmiş, doğrulanmış ve `main` dalına pürüzsüz bir şekilde aktarılmıştır.*
