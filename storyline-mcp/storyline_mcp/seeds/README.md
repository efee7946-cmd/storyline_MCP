# Tohumlar

Storyline'da "bana slayt yap" diye bir şema yok: bir slayt, şekilleri
tetikleyicilere, durumlara ve etkileşimlere bağlayan GUID grafı. Bu yüzden
üretim **klonlamayla** çalışır ve klonlanacak şeyler burada durur.

Ad kuralı, `authoring.question_seeds()` tarafından okunur:

    question_<etkileşimTürü>_<şıkSayısı>[_<görünüş>].xml

`<görünüş>` aynı biçimin ikinci/üçüncü tasarımıdır; kütüphane zenginleştikçe
üretilen kurslarda sorular birbirine benzemez.

## Nereden geldiler

Çoğu **hasat edilmiştir**: gerçek Storyline projelerinden
`harvest.harvest_questions` ile alınmış, GUID'leri yenilenmiş slaytlar.

Bir tanesi **türetilmiştir** ve bunu bilmek önemli:

| dosya | kaynağı |
|---|---|
| `question_freePickOneIntr_4.xml` | `_3`'ten üretildi (2026-09-05) |

4 şıklı tek seçmeli hiçbir yerde yoktu — ne kütüphanede, ne 43 üretilmiş
kursta (ölçüldü). Kendi çıktımızdan hasat etmek döngü olurdu, o yüzden
`_3`'ün bir şık butonu **ham metin üzerinde** klonlandı, tanımladığı GUID'ler
yenilendi ve `<choices>` listesine bir `<intrFreeChoice>` kaydı eklendi.

Üç şey bilerek yapıldı:

* **ElementTree ile değil, ham metin üzerinde.** İlk deneme `ET.tostring` ile
  yazdı ve dosya BOM'unu, XML bildirimini ve biçimlemesini kaybetti; şablon
  değerlendirici `ValueError` ile patladı. Bu deponun ilkesi zaten bunun
  tersi: *GUID olmayan her byte olduğu gibi kalır.*
* **Klonun tetikleyici hedefi nötrlendi.** Şık butonları
  `OnClick → showSubSlide` taşıyor ve hasat edildiği kursun katmanını
  gösteriyor; klonda o hedef yanlış bir yeri gösterirdi. `showG` boş GUID'e
  çekildi, gerisini `authoring._drop_dangling_triggers` temizliyor.
* **Dördüncü katman eklenmedi.** Tohumdaki `Cevap1/2/3` katmanları şıklara
  bağlı değil (ölçüldü: hiçbir `showLayer` tetikleyicisi onları açmıyor ve
  `intrProps`'un `corFbG/incFbG`'si tohumda bulunmayan katmanları gösteriyor).
  Geri bildirimi `adapt_seeded_slide` zaten yeniden kuruyor — üretilen
  slaytta 3 değil 2 katman oluyor.

Doğrulandı: kurucu bu tohumdan 4 şıklı soru kuruyor, doğru cevap
işaretleniyor, dört şık çakışmadan yerleşiyor ve dosya Storyline'da açılıyor.

## Yeni tohum eklerken

Hasat yolu tercih edilir (`harvest.harvest_questions`) — gerçek bir tasarım
taşır. Türetme yalnızca hiçbir yerde örneği olmayan bir biçim için yapılır ve
**buraya kaydı düşülür**, çünkü türetilmiş bir tohum kütüphaneye yeni tasarım
öğretmez, yalnızca yeni bir *kapasite* açar.
