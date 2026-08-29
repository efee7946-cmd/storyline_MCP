"""Whole-course construction from a brief.

A brief like "a 25-40 minute security course covering these six topics" cannot
be done in one agent run: the turn budget runs out, and a single long silence
is indistinguishable from a crash. Splitting it into many small agent runs
would be slow and would still put every slide at the mercy of a tool call
going wrong halfway.

So authoring and construction are separated. The model is asked only for
*content* -- as JSON, with no tools attached, which is what it is good at and
what a single response can hold. The panel then builds the course from that
JSON deterministically: no further model calls, no turn limits, and a failure
in slide nine cannot corrupt slides one to eight.

Content is requested one section at a time so each response stays small and
progress is visible while it happens.

A brief is also thin instruction. Asked only for "a security course", the model
has to guess the audience, the length, the tone and whether questions are wanted
at all -- and it guesses differently every run. So a short setup is collected
once and folded into every prompt: who this is for, how long, what tone, how
many questions and in what shape. Each field changes the output or it would not
be worth asking for.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from storyline_mcp import authoring, compose, medya, model as sl_model, settings
from storyline_mcp.package import StoryPackage, StoryError

import ogretim
from agent import find_cli

OUTLINE_PROMPT = """\
Asagidaki brief icin bir e-ogrenme kursu iskeleti tasarla.

Yanit YALNIZCA gecerli JSON olsun. Aciklama, markdown, kod bloklari YAZMA.

Bicim:
{"scenes": [
  {"name": "01_Giris", "title": "Giris", "slides": [
     {"title": "Kursa Hos Geldiniz", "layout": "cover", "kind": "content"},
     {"title": "Neler Ogrenecegiz", "layout": "bullets", "kind": "content"}
  ]}
]}

Kurallar:
- layout su yedi degerden biri, ve HER BIRININ BIR ISI VAR:
    cover      kursun ilk slaydi; bir kez kullanilir
    section    bir bolumun ayraci; her konu sahnesinin basinda
    content    bir iki cumlelik aciklama -- gorsel istenecekse BU duzen
    bullets    kisa maddeler, sirasi onemli OLMAYAN
    steps      SIRALI adimlar; numaralanir, yani sira anlam tasiyorsa kullan
    statement  akilda kalmasi gereken TEK cumle; govdesi kisa olmali
    menu       ogrencinin secim yaptigi slayt; secenekler buttons alaninda
- kind: "content" veya "question"
- Ilk sahne bir kapak (cover) slaydiyla baslasin.
- Brief'te gecen her ana baslik icin ayri bir sahne olustur; sahne adlari
  "01_Ad", "02_Ad" biciminde, Turkce karakter ve bosluk kullanma.
- Konu sahnesi EN FAZLA 2 icerik slaydi tasisin ve bir question ile kapansin.
  Uc icerik slaydi koyarsan ardisik okuma DORDE cikar; ritim kurali bunu
  yasakliyor.
- SECTION KOSULLU: bir sahnede section'dan sonra EN AZ IKI gövde slaydi
  gelecekse ayraç koy, yoksa KOYMA. Arkasinda tek slayt olan bir ayrac hicbir
  seyi ayirmiyor, yalnizca yer kapliyor -- ve bütçe darken kurs bastan sona
  ayrac gibi gorunuyor. Olculdu 2026-08-29: kurulan 8 slaydin 5'i section'di,
  cunku alti sahnenin her biri zorunlu bir ayrac tasiyordu.
- Ayni layout'u ust uste tekrarlama.
- GOVDE SLAYTLARINDA EN AZ UC FARKLI DUZEN KULLAN. Govde, cover ve section
  DISINDA kalanlardir. Hepsini content ve bullets yaparsan kurs bastan sona
  ayni gorunur -- olculdu 2026-08-29: uretilmis bir kursta 15 govde slaydi
  UC bilesime sigmisti (bes content, bes bullets, bes section) ve kullanici
  "hepsi ayni tasarim" diye bildirdi. Sira tasiyan bir anlatimi steps yap,
  akilda kalmasi gereken cumleyi statement yap.
- Toplam slayt sayisi {slide_budget} civarinda olsun.
{ogretim}
{question_rule}
KUNYE:
{profile}

BRIEF:
{brief}
"""

CONTENT_PROMPT = """\
Bir e-ogrenme kursunun "{scene}" bolumu icin slayt icerigi yaz.

Yanit YALNIZCA gecerli JSON olsun. Aciklama, markdown, kod bloklari YAZMA.

Bicim:
{"slides": [
  {"kind": "content", "layout": "section", "eyebrow": "Bolum 2",
   "title": "Kisa baslik", "body": "Bir iki cumle."},
  {"kind": "content", "layout": "bullets", "eyebrow": "Ozet",
   "title": "Kisa baslik", "bullets": ["Madde bir", "Madde iki"]},
  {"kind": "content", "layout": "steps", "eyebrow": "Nasil yapilir",
   "title": "Kisa baslik", "bullets": ["Once sunu yap", "Sonra sunu"]},
  {"kind": "content", "layout": "statement", "eyebrow": "Akilda kalsin",
   "title": "Kisa baslik", "body": "Tek cumlelik, akilda kalacak fikir."},
  {"kind": "content", "layout": "content", "eyebrow": "Ornek",
   "title": "Kisa baslik", "body": "Bir iki cumle.",
   "medya": {"tur": "video", "saniye": 20,
             "aciklama": "Cerceve ne gostersin, tek iki cumle."}},
  {"kind": "question", "prompt": "Soru metni?",
   "choices": ["A secenegi", "B secenegi", "C secenegi", "D secenegi"],
   "correct": [1],
   "feedback": {"correct": "Neden dogru oldugunu tek cumleyle acikla.",
                "incorrect": "Neden yanlis oldugunu ve dogru davranisi tek cumleyle acikla."}}
]}

Kurallar:
- Slayt sirasi ve layout degerleri asagidaki plana uysun.
- HER DUZEN KENDI ALANINI ISTER, yoksa slayt bos cikar:
    steps      -> bullets (en az iki madde). body degil.
    statement  -> kisa bir body. bullets degil.
    bullets    -> bullets.
    section / content -> body.
- title kisa olsun (en fazla 6 kelime). Aciklamayi body'ye yaz.
- body en fazla 3 cumle. bullets en fazla 5 madde, her madde tek satir.
- correct, dogru seceneklerin sifir tabanli indisleridir.
- SECENEK SAYISI SERBEST DEGIL. Kullanilabilir bicimler: {arities}
  Her soruyu bu bicimlerden birine gore yaz; baska sayida secenek yazarsan
  soru puanlanamaz. Tek dogru cevapli sorularda tek indis, cok dogru cevapli
  sorularda birden fazla indis ver.
- Turkce yaz, teknik terimleri sade anlat.

MEDYA ISTEGI (secmeli, "medya" alani):
- Bu alan bir SIPARISTIR, bir dosya adi degil. Sen dosyayi bulamazsin; istek
  panelde kullaniciya gosterilir, dosyayi o verir ve panel tam olarak bu
  slaydin ayrilmis alanina koyar.
- GORMEK ogretiyorsa iste: bir ekranin nasil gorundugu, bir isin nasil
  yapildigi, iki seyin farki, somut bir sahne. Bu bolumde boyle bir slayt
  varsa ISTE -- kurs bastan sona metin olarak cikarsa brosur olur.
- Susleme icin isteme: aciklamasini yazamiyorsan istek de yoktur.
- Yalnizca layout "content" ya da "cover" olan slaytlarda gecerlidir. Medya
  istedigin content slaydinda bullets KULLANMA, body yaz: yer yalnizca duz
  metinli content ve cover slaytlarinda ayrilabiliyor.
- Bu bolumde EN FAZLA BIR medya istegi olsun.
- medya.tur: "gorsel" ya da "video". Videoda saniye de ver (10-60).
- aciklama somut olsun: cerceve ne gostersin, kim/ne var, hangi an.
  Kotu: "guvenlik temali bir gorsel". Iyi: "telefon ekraninda dogrulama
  bildirimi, parmak onay tusunun uzerinde".
- Gorselin ya da videonun USTUNDE YAZI olmasini isteme; yaziyi slayt tasir.
{ogretim}
{tone_rule}
KUNYE:
{profile}

BU BOLUMUN PLANI:
{plan}

KURSUN GENEL BRIEFI:
{brief}
"""

TONES = {
    "kurumsal": "Ton: kurumsal ve olculu. Ikinci cogul sahis kullan, abartma.",
    "samimi": "Ton: samimi ve dogrudan. Ikinci tekil sahis kullan, kisa cumleler.",
    "teknik": "Ton: teknik ve kesin. Terimleri dogru kullan, gerekirse tanimla.",
    "hikaye": "Ton: senaryo anlatimi. Somut bir calisanin basindan gecenler uzerinden anlat.",
}

# Roughly how many slides a learner gets through per minute of course time.
SLIDES_PER_MINUTE = 0.55


def _profile_text(options: dict) -> str:
    """The setup, as lines the model can act on. Blank fields are omitted."""
    fields = [
        ("Kurs basligi", options.get("title")),
        ("Hedef kitle", options.get("audience")),
        ("Amac", options.get("goal")),
        ("Sure", f"{options['minutes']} dakika" if options.get("minutes") else None),
        ("Bolum sayisi", options.get("sections")),
    ]
    lines = [f"- {label}: {value}" for label, value in fields if value]
    return "\n".join(lines) if lines else "- (belirtilmedi)"


def _question_rule(options: dict, arities: str) -> str:
    per = options.get("questions_per_section")
    if per in (None, "", "auto"):
        return ("- Her konu sahnesinde en az 1 question bulunsun.\n"
                f"- Soru bicimleri: {arities}\n")
    try:
        count = int(per)
    except (TypeError, ValueError):
        count = 1
    if count <= 0:
        return ("- Bu kursta SORU OLMAYACAK. Hicbir sahneye question ekleme.\n"
                "  Kullanici bunu ACIKCA istedi; yukaridaki ortak soru\n"
                "  kurallari bu kursta GECERSIZDIR.\n")
    return (f"- Her konu sahnesinde TAM OLARAK {count} adet question bulunsun.\n"
            f"- Soru bicimleri: {arities}\n")


def slide_budget(options: dict, fallback: int = 18) -> int:
    minutes = options.get("minutes")
    try:
        return max(int(round(int(minutes) * SLIDES_PER_MINUTE)), 6)
    except (TypeError, ValueError):
        return fallback


def _cli_json(cli, prompt: str, model: str, timeout: float,
              on_progress=None, deneme: int = 2):
    """CLI'i cagir; zaman asiminda bir kez daha dene."""
    for kalan in range(deneme - 1, -1, -1):
        try:
            return subprocess.run(
                [str(cli), "-p", prompt, "--output-format", "json",
                 "--model", model],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=timeout,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired:
            if not kalan:
                raise
            if on_progress:
                on_progress(f"model {int(timeout)} saniyede yanit vermedi -- "
                            "bir kez daha deneniyor")


# OLCULDU (2026-08-29, sonnet, gercek brief): 4665 karakterlik iskelet istemi
# 394.8 saniyede dondu -- tek tur, 3.2 KB cikti, ve surenin TAMAMI API
# cagrisinin icinde (api_ms 393852). Yani 300 saniyelik eski duvar bu brief
# icin bastan yetersizdi; kullanicinin gordugu sey bir hata degil, dar bir
# duvardi.
#
# Sayilar o olcumden turetildi, secilmedi:
#   iskelet  900 s -- olculenin ~2.3 kati; en buyuk tek JSON burada uretiliyor
#   icerik   420 s -- bir sahnelik JSON, iskeletin ucte biri kadar
#   medya    300 s -- birkac cumlelik tarif
# Tekrar da buna gore: iskelette YOK (bir kez on bes dakika beklemek yeterli
# sabir; asarsa sorun gecici degil, brief cok buyuktur), icerikte VAR.
ISKELET_SURESI = 900.0
ICERIK_SURESI = 420.0
MEDYA_SURESI = 300.0


def _run_json(prompt: str, model: str = "sonnet", timeout: float = ICERIK_SURESI,
              on_progress=None, deneme: int = 2) -> dict:
    """Ask the model for JSON, with no tools attached.

    Tools are deliberately absent: this pass writes nothing, and a model that
    cannot reach for a tool cannot spend turns on one.

    ZAMAN ASIMINDA BIR KEZ TEKRAR. Bir kurs bes-yedi cagri suruyor ve icerik
    ancak hepsi bittikten sonra dosyaya yaziliyor: altinci cagrida takilan bir
    kosu, oncekilerin tamamini cope atiyor. Tekrar bunu ucuza kapatir --
    takilma gecici oldugunda (olculdu 2026-08-29: ayni istem bir kosuda 300
    saniyeyi asti, otekinde normal surede dondu) ikinci deneme calisir. Sessiz
    degil: bekleyen kullanici, birinci denemenin dustugunu akista gorur.
    """
    cli = find_cli()
    if cli is None:
        raise StoryError("Claude Code CLI bulunamadi.")
    try:
        result = _cli_json(cli, prompt, model, timeout, on_progress, deneme)
    except subprocess.TimeoutExpired:
        # ISTEM HATA METNINE GIRMEZ. TimeoutExpired'in kendi metni CAGRIYI
        # tasiyor, yani bes bin karakterlik istemi -- panele oldugu gibi
        # basildi ve kullanicinin gordugu sey, ne oldugunu soyleyen bir cumle
        # yerine kendi brief'inin kacisli hali oldu (olculdu 2026-08-29).
        raise StoryError(
            f"Model {int(timeout)} saniyede yanit vermedi. Kursa hicbir sey "
            "yazilmadi; komutu yeniden calistirabilirsiniz.") from None
    except OSError as exc:
        raise StoryError(f"Claude Code CLI calistirilamadi: {exc}") from None
    if result.returncode != 0:
        raise StoryError(f"Icerik uretilemedi: {(result.stderr or '').strip()[:200]}")
    try:
        payload = json.loads(result.stdout)
        text = payload.get("result", "")
    except json.JSONDecodeError:
        text = result.stdout

    # Models wrap JSON in prose or fences often enough that it is cheaper to
    # dig the object out than to insist the prompt was obeyed.
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise StoryError(f"Yanitta JSON bulunamadi: {text[:200]}")
    return json.loads(match.group(0))


# ----------------------------------------------------------------- execution


def _question_template(pkg: StoryPackage, choice_count: int) -> str | None:
    for template in authoring.list_templates(pkg):
        if (template["kind"] == "question"
                and template.get("question_type") != "dragDropIntr"
                and template.get("choice_count") == choice_count):
            return template["slide"]
    return None


def _inherited(path) -> dict:
    """Kaynak dosyadan gelen ve ele alinmayan sey: bos slayt, kopuk tetik.

    Kurucunun urettigi degil, DEVRALDIGI kusur. Ayri sayilir cunku cozumu de
    ayri: uretilen bir kusur duzeltilir, devralinan bir kusur kullaniciya
    bildirilir -- onun dosyasindaki slaytlari silmek bizim karariiz degil.
    """
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        import completeness
        found = completeness.survey(StoryPackage(Path(path)))
    except Exception as exc:            # olcum kursu bozmamali
        return {"error": str(exc)[:120]}
    empty_scenes = [name for name, data in found["scenes"].items()
                    if data["empty"] == data["slides"] and data["slides"]]
    return {
        "empty_slides": len(found["empty"]),
        "empty_scenes": empty_scenes,
        "dangling_triggers": len(found["dangling"]),
        "unscored_question_like": len(found["unscored"]),
    }


def _content_template(pkg: StoryPackage) -> str:
    candidates = [t for t in authoring.list_templates(pkg) if t["kind"] == "content"]
    if not candidates:
        raise StoryError("Klonlanacak bir icerik slaydi yok.")
    return min(candidates, key=lambda t: t["text_shapes"])["slide"]


def _sorular_kapali(options: dict) -> bool:
    per = options.get("questions_per_section")
    if per in (None, "", "auto"):
        return False
    try:
        return int(per) <= 0
    except (TypeError, ValueError):
        return False


def _konu_araligi(scenes: list[dict]):
    """Konu sahneleri: ilk ve son disindakiler.

    Giris ve kapanis muaf -- ORTAK_KURALLAR da onlari disarida birakiyor,
    ve iki yerde iki farkli tanim olsaydi kapi promptla celiserdi.
    """
    return range(1, len(scenes) - 1) if len(scenes) > 2 else range(len(scenes))


def _soru_mu(s: dict) -> bool:
    return (s or {}).get("kind") == "question"


def _kadans_ihlalleri(scenes: list[dict], options: dict,
                      anahtar: str = "slides") -> list[str]:
    """SAF TESPIT: plani degistirmez, ihlalleri sayar.

    ANAHTAR: plan ("slides") YETKILI DEGIL. Icerik gecisi
    `scene["content"] = filled.get("slides")` ile plani BUTUNUYLE degistirir
    ve plana uydugu hic denetlenmez -- olculdu 2026-08-28: plan temizken
    uretilen kursta bir konu sahnesi sorusuz kaldi ve plan kapisi hicbir sey
    raporlamadi. Bu yuzden ayni dedektor iki asamada da kosulur: once plan
    ("slides"), sonra icerik ("content").

    Tespit duzeltmeden AYRI durur ve bunun somut bir sebebi var: yeniden
    istenen bir plan, bulunan ihlali giderirken BASKA bir ihlal uretebilir
    (baska bir sahnede yeni bir ardisiklik, ya da kaybolan bir soru). Kontrol
    "orijinal ihlal duzeldi mi" diye sorsaydi, YER DEGISTIREN bir kusur
    sessizce gecerdi. Ayni saf dedektor ikinci kez kosuldugu icin yeniden
    kontrol her zaman TUM kural setine karsi yapilir.
    """
    if _sorular_kapali(options) or len(scenes) < 2:
        return []
    konu = _konu_araligi(scenes)
    ihlaller: list[str] = []

    for i in konu:
        if not any(_soru_mu(s) for s in (scenes[i].get(anahtar) or [])):
            ihlaller.append(f"{scenes[i].get('name') or i} sahnesinde hic soru yok")

    seri = 0
    en_uzun = 0
    for scene in scenes:
        for s in scene.get(anahtar) or []:
            seri = 0 if _soru_mu(s) else seri + 1
            en_uzun = max(en_uzun, seri)
    if en_uzun > 3:
        ihlaller.append(f"{en_uzun} slayt ardisik okuma (en fazla 3 olmali)")
    return ihlaller


def _kadans_yamasi(scenes: list[dict], options: dict) -> list[str]:
    """SON CARE: plani deterministik olarak duzeltir, yerinde degistirir.

    Yalnizca PLAN yuvasi eklenir ({"kind": "question"}); sorunun metni yine
    CONTENT_PROMPT'tan, diger her soruyla ayni cagridan gelir. Yani icerik
    uydurulmaz, yalnizca yeri acilir.

    Reddetmek yerine yamamanin sebebi: reddedilecek sey KULLANICI GIRDISI
    degil, modelin kendi ciktisi. Brief dogruyken "brief'i duzeltin" demek
    kullaniciyi cikamayacagi bir donguye sokar ve ayni brief bazen gecip
    bazen reddedilecegi icin hata ARALIKLI gorunur.
    """
    if _sorular_kapali(options) or len(scenes) < 2:
        return []
    konu = _konu_araligi(scenes)
    yeni_soru = lambda: {"title": "Kontrol", "kind": "question"}
    duzeltmeler: list[str] = []

    for i in konu:
        slides = scenes[i].setdefault("slides", [])
        if not any(_soru_mu(s) for s in slides):
            slides.append(yeni_soru())
            duzeltmeler.append(f"{scenes[i].get('name') or i}: soru yoktu, eklendi")

    for _ in range(50):          # sonlanma garantisi
        seri, kirilma = 0, None
        for i, scene in enumerate(scenes):
            for j, s in enumerate(scene.get("slides") or []):
                if _soru_mu(s):
                    seri = 0
                    continue
                seri += 1
                if seri > 3 and i in konu:
                    kirilma = (i, j)
                    break
            if kirilma:
                break
        if not kirilma:
            break
        i, j = kirilma
        scenes[i]["slides"].insert(j, yeni_soru())
        duzeltmeler.append(
            f"{scenes[i].get('name') or i}: ardisik okuma 3'u asiyordu, araya soru kondu")
    return duzeltmeler


# Govde slaytlari: kapak ve bolum ayraci HARIC. Ikisi de kadansin zorunlu
# kildigi slaytlar -- her sahnede bir section, kursta bir cover -- yani
# "cesitlilik" sayarken onlari saymak, zorunlu tekrari cesitlilik sanmaktir.
GOVDE_DUZENLERI = ("content", "bullets", "steps", "statement", "menu")


def _govde(scenes: list[dict], anahtar: str) -> list[dict]:
    return [s for scene in scenes for s in (scene.get(anahtar) or [])
            if not _soru_mu(s) and (s.get("layout") or "content") in GOVDE_DUZENLERI]


def _duzen_ihlalleri(scenes: list[dict], anahtar: str = "slides") -> list[str]:
    """SAF TESPIT: govde slaytlari kac FARKLI duzen kullaniyor?

    KADANSTAN AYRI BIR KURAL, o yuzden ayri fonksiyon. Kadans "ogrenci ne
    kadar ard arda okuyor" diye sorar; bu "slaytlar birbirine benziyor mu"
    diye sorar ve ikisi bagimsiz bozulur: her sahnede sorusu olan, hicbir
    yerde uc slayttan fazla okutmayan bir kurs, govdesinin tamami `content`
    oldugu icin bastan sona ayni gorunebilir.

    Olculdu 2026-08-29, uretilmis alti modulde blok bilesimi sayilarak:

        egitim    15 slayt -> 13 bilesim
        cyber     19 slayt ->  9
        musteri   11 slayt ->  7
        toy       15 slayt ->  3      <-- 5 + 5 + 5

    toy.story yedi duzenden UCUNU kullanmis (section, bullets, content) ve
    beser kez tekrarlamis. Kullanicinin "hepsi ayni tasarim" dedigi sey bu
    satir. Varyant makinesi calisiyordu -- ayni bilesimi farkli x'lerde
    ciziyordu, ve goz onu yeni bir tasarim saymiyor.

    ESIK SLAYT SAYISINA BAGLI: uc govde slaydi olan bir kurstan uc farkli
    duzen istemek, cesitlilik degil zorlama olurdu.
    """
    govde = _govde(scenes, anahtar)
    if len(govde) < 3:
        return []
    farkli = {(s.get("layout") or "content") for s in govde}
    gerekli = min(3, len(govde))
    if len(farkli) < gerekli:
        return [f"govde slaytlarinin tamami {len(farkli)} duzene sigmis "
                f"({', '.join(sorted(farkli))}); en az {gerekli} farkli duzen olmali"]
    return []


def _duzen_yamasi(scenes: list[dict], anahtar: str = "slides") -> list[str]:
    """SON CARE: duzeni deterministik olarak cesitlendirir, yerinde.

    ICERIK UYDURULMAZ, yalnizca ayni icerigi TASIYABILEN baska bir duzene
    gecirilir. Iki takas guvenli, cunku hedef duzen kaynagin doldurdugu
    alanlari tuketiyor (compose.py'de okundu):

        bullets -> steps       ikisi de `bullets` + `title` kullanir
        content -> statement   `body`i tek buyuk fikir olarak dizer

    MEDYASI OLAN SLAYT TAKAS EDILMEZ: `_medya_yeri_var` yalnizca content ve
    cover duzenlerinde alan ayirabiliyor, yani takas edilen bir slaytta
    istek sessizce dusurulurdu.

    En COK tekrarlanan duzenden baslanir: tekil bir duzeni bozmak
    cesitliligi artirmaz, yalnizca yerini degistirir.
    """
    govde = _govde(scenes, anahtar)
    if len(govde) < 3:
        return []
    gerekli = min(3, len(govde))
    duzeltmeler: list[str] = []

    def farkli() -> set:
        return {(s.get("layout") or "content") for s in govde}

    for hedef, kaynak, uygun in (
        ("steps", "bullets",
         lambda s: len(s.get("bullets") or []) >= 2),
        ("statement", "content",
         lambda s: (s.get("body") and not s.get("bullets")
                    and not s.get("medya"))),
    ):
        if len(farkli()) >= gerekli:
            break
        if hedef in farkli():
            continue
        adaylar = [s for s in govde
                   if (s.get("layout") or "content") == kaynak and uygun(s)]
        # Kaynak duzenden GERIYE en az bir slayt kalsin: hepsini cevirmek
        # bir tekduzeligi digeriyle degistirmek olur.
        if len(adaylar) < 2:
            continue
        secilen = adaylar[len(adaylar) // 2]
        secilen["layout"] = hedef
        duzeltmeler.append(
            f"{(secilen.get('title') or 'slayt')[:40]}: {kaynak} -> {hedef}")
    return duzeltmeler


def _ayrac_ihlalleri(scenes: list[dict], anahtar: str = "slides") -> list[str]:
    """SAF TESPIT: arkasinda tek gövde slaydi olan ayraclar.

    Bir section slaydinin isi bolum ACMAK. Arkasinda tek slayt varsa hicbir
    sey acmiyor -- ogrenci ayraci okuyor, tek slaydi okuyor, soruya geciyor.
    Bedeli yalnizca bosluk degil, TEKDUZELIK: ayrac kursun en cok tekrarlanan
    bilesimi ve slayt butcesi darken deck'in yarisini kaplayabiliyor.

    Olculdu 2026-08-29 (DOGRULAMA3): 8 kurulan slaydin 5'i section. Sebep
    besteci degil aritmetik -- alti sahne, her birine zorunlu bir ayrac,
    ~11 slaytlik butce ve 8 soru; govdeye iki slayt kaliyor.
    """
    ihlaller = []
    for scene in scenes:
        slaytlar = [s for s in (scene.get(anahtar) or []) if not _soru_mu(s)]
        ayrac = [s for s in slaytlar if (s.get("layout") or "content") == "section"]
        govde = [s for s in slaytlar
                 if (s.get("layout") or "content") in GOVDE_DUZENLERI]
        if ayrac and len(govde) < 2:
            ihlaller.append(
                f"{scene.get('name') or '?'} sahnesinde ayrac var ama arkasinda "
                f"{len(govde)} govde slaydi")
    return ihlaller


def _ayrac_yamasi(scenes: list[dict], anahtar: str = "slides") -> list[str]:
    """SON CARE, ve iki asamada iki AYRI davranis -- cunku kayip ayni degil.

    PLANDA (anahtar="slides") ayrac SILINIR. Plan bir iskelet: slaytin
    yalnizca basligi var, govdesi henuz yazilmadi. Silmek bir baslik kaybi,
    ve icerik gecisi zaten kalan slaytlar icin yazacak.

    ICERIKTE (anahtar="content") ayrac SILINMEZ, `statement`a CEVRILIR.
    Burada metin YAZILMIS durumda ve silmek modelin urettigi govdeyi cope
    atmak olurdu. statement ayni alanlari tuketiyor (`body or title`), yani
    icerik korunur ve bilesim de degisir -- ayni hamlede tekduzelik azalir.
    """
    duzeltmeler = []
    for scene in scenes:
        slaytlar = scene.get(anahtar) or []
        govde = [s for s in slaytlar
                 if not _soru_mu(s)
                 and (s.get("layout") or "content") in GOVDE_DUZENLERI]
        if len(govde) >= 2:
            continue
        for s in slaytlar:
            if _soru_mu(s) or (s.get("layout") or "content") != "section":
                continue
            ad = (s.get("title") or scene.get("name") or "ayrac")[:40]
            if anahtar == "slides":
                slaytlar.remove(s)
                duzeltmeler.append(f"{ad}: ayrac plandan cikarildi (arkasi bos)")
            else:
                s["layout"] = "statement"
                duzeltmeler.append(f"{ad}: ayrac -> statement (arkasi bos)")
            break
    return duzeltmeler


def _plan_kabul_edilebilir(aday: list[dict], orijinal: list[dict]) -> bool:
    """Yeniden istenen plan, orijinalin yerine gecmeye deger mi.

    Model kadansi duzeltirken kursu kucultebilir. Ihlal SAYISI dusse bile
    icerigin dortte birini kaybetmis bir plan iyilesme degildir.
    """
    if not aday or len(aday) < len(orijinal):
        return False
    say = lambda ss: sum(len(s.get("slides") or []) for s in ss)
    return say(aday) >= say(orijinal) * 0.75


def _medya_istegi(spec: dict) -> dict | None:
    """Modelin medya istegini kabul et, ya da sessizce dus.

    Kabul dar tutulur cunku REDDETMENIN BEDELI YOK: istek dusunce slayt normal
    kurulur ve kimse bir sey kaybetmez. Kabulun bedeli ise gercek -- bos bir
    gorsel alani ayrilmis, ne konacagi da yazmayan bir slayt kalir.

    Bu yuzden aciklama bir ETIKET olamaz: "guvenlik gorseli" kullaniciya ne
    arayacagini soylemez, o istek dosya beklerken kursu eksik gosterir.
    """
    ham = spec.get("medya")
    if not isinstance(ham, dict):
        return None
    tur = str(ham.get("tur") or "").strip().lower()
    tur = {"resim": "gorsel", "foto": "gorsel", "fotograf": "gorsel",
           "image": "gorsel", "photo": "gorsel", "film": "video",
           "gorsel": "gorsel", "video": "video"}.get(tur)
    if tur is None:
        return None
    aciklama = " ".join(str(ham.get("aciklama") or "").split())
    if len(aciklama) < 20:
        return None
    try:
        saniye = int(ham.get("saniye"))
    except (TypeError, ValueError):
        saniye = None
    return {"tur": tur, "aciklama": aciklama[:400],
            "saniye": saniye if tur == "video" else None}


def _kapak_istegi(options: dict, brief: str) -> dict:
    """Kapak icin taban istek -- model hic istemediginde bile.

    NICIN DETERMINISTIK: 2026-08-29'da uretilen gercek kursta model TEK bir
    medya istegi yazmadi ve kurs bastan sona metin olarak cikti; kullanicinin
    bildirdigi kusur buydu. Prompt'a "iste" yazmak bunu ihtimale birakir --
    ayni brief bir kosuda ister, digerinde istemez.

    Kapak secildi cunku kapakta gorselin YERI TARTISMASIZ: hero alani zaten
    tam sayfa ve uzerindeki ortu yaziyi okunur tutuyor. Ic slaytlarda ayni
    seyi zorlamak, konusu gorsel olmayan bir slayta bos bir bant birakirdi.

    Model kapakta kendi istegini yazdiysa BU CALISMAZ: siparisi yazan, konuyu
    bilen taraf olsun.
    """
    konu = (options.get("title") or "").strip()
    kitle = (options.get("audience") or "").strip()
    if not konu:
        konu = " ".join(brief.split()[:8])
    return {
        "tur": "gorsel",
        "aciklama": (
            f"Kapak fotografi: \"{konu}\" konusunu temsil eden genis bir sahne"
            + (f"; {kitle} kendini icinde gorebilsin" if kitle else "")
            # ORANI BURADA SOYLEME. Boyutu ve orani `medya.prompt` kursun
            # kendi olcusunden yaziyor; burada "16:9" yazsaydi 720x540 bir
            # kursta ayni cumlenin iki yarisi birbiriyle celisirdi.
            + ". Uzerinde YAZI OLMASIN ve alt yarisi sakin kalsin -- baslik "
              "oraya biniyor."),
        "saniye": None,
    }


MEDYA_PROMPT = """\
Bir e-ogrenme kursunun asagidaki slaytlari icin gorsel/video SIPARISI yaz.

Yanit YALNIZCA gecerli JSON olsun. Aciklama, markdown, kod bloklari YAZMA.

Bicim:
{"siparisler": [
  {"no": 1, "tur": "gorsel",
   "aciklama": "Masada birakilmis kilitlenmemis bir dizustu bilgisayar, ofis arka planda, kimse yok."},
  {"no": 2, "tur": "video", "saniye": 20,
   "aciklama": "Telefon ekraninda dogrulama bildirimi cikiyor, parmak onay tusuna dokunuyor."}
]}

Kurallar:
- HER slayt icin bir siparis yaz; "no" degerini asagidaki listeden aynen al.
- Bu bir SIPARIStir, etiket degil: cerceve ne gostersin, kim/ne var, hangi an.
  Kotu: "guvenlik temali bir gorsel". Iyi: "telefon ekraninda dogrulama
  bildirimi, parmak onay tusunun uzerinde".
- tur: bir SUREC ya da davranis gosterilecekse "video", bir durum, ortam ya da
  ekran gosterilecekse "gorsel". Videoda saniye de ver (10-60).
- Gorselin ya da videonun USTUNDE YAZI olmasini isteme; yaziyi slayt tasir.
- Aciklama tek paragraf, en fazla iki cumle olsun.
- Turkce yaz.

KUNYE:
{profile}

SLAYTLAR:
{slaytlar}
"""

# Kac medya? Yaklasik alti slaytta bir -- yani ~3 dakikada bir gorsel duraga
# denk gelir. Sayi degil ORAN sabittir; 15 dakikalik kurs 2, 60 dakikalik kurs
# 5-6 istek alir. Ust sinir kullanicinin isini korur: her istek onun bulacagi
# bir dosya demek ve on bekleyen istek, panelin bir is listesine donmesidir.
MEDYA_ARALIGI = 6
MEDYA_TAVANI = 6


def _medya_kipi(options: dict) -> str:
    """otomatik | kapak | yok -- kunyedeki secim, varsayilan otomatik."""
    kip = str(options.get("media") or "otomatik").strip().lower()
    return kip if kip in ("otomatik", "kapak", "yok") else "otomatik"


def _medya_hedefi(options: dict, planlanan: int) -> int:
    kip = _medya_kipi(options)
    if kip == "yok":
        return 0
    if kip == "kapak":
        return 1
    return max(2, min(MEDYA_TAVANI, round(planlanan / MEDYA_ARALIGI)))


def _mekanik_aciklama(scene: dict, spec: dict) -> str:
    """Model tarif yazmadiginda slaydin KENDI metninden cikan siparis.

    Iyi bir siparis degil -- slaydin cumlesini tekrar eder. Ama bos birakmaktan
    iyidir: kullanici en azindan neyin anlatildigini gorur ve kendi arayacagi
    seyi bilir. Sessizce vazgecmek, ayrilmis bos bir alan birakirdi.
    """
    baslik = " ".join(str(spec.get("title") or "").split())
    govde = " ".join(str(spec.get("body") or "").split())[:200]
    konu = baslik or scene.get("title") or scene.get("name") or "Slayt"
    return (f"\"{konu}\" slaydini anlatan gercekci bir fotograf. "
            + (f"Slaytta soyle deniyor: {govde} " if govde else "")
            + "Anlatilan ani gosteren bir sahne olsun; uzerinde yazi olmasin.")


def _medya_plani(scenes: list[dict], options: dict, brief: str, model: str,
                 on_progress) -> list[str]:
    """HANGI slaytlar medya isteyecek: kurucu secer, model yalnizca tarif eder.

    Secimi modele birakmak olculdu ve tutmadi (2026-08-29): brief yolundan
    cikan gercek kursta model TEK bir istek yazmadi, kurs bastan sona metin
    olarak cikti ve kullanici "hic gorsel/video kullanmadik" diye bildirdi.
    Ayni brief bir kosuda ister, otekinde istemez -- yani gorsel varligi
    KURSUN OZELLIGI degil, o kosunun sansi olurdu.

    Bu yuzden iki karar ayrildi:

      NEREYE ve KAC TANE -- kurucunun karari, deterministik. Yer ayrilabilen
      slaytlar (kapak ve duz metinli content) bilinir, sahne basina en fazla
      bir tane konur, toplam kurs uzunluguna oranlanir.

      NE OLSUN -- modelin isi, cunku konuyu o biliyor. Yalnizca secilen
      yuvalar icin, tek cagrida, tarif yazar. Cagri basarisiz olursa yuva
      bos kalmaz: slaydin kendi metninden mekanik bir siparis uretilir.

    Modelin icerik yazarken kendiliginden koydugu istekler KORUNUR ve hedefe
    sayilir -- konuyu bilerek yazilmis bir siparis, buradan uretilenden iyidir.
    """
    hedef = _medya_hedefi(options, sum(len(s.get("content") or []) for s in scenes))
    if hedef <= 0:
        return ["medya istegi kapali (kunye)"]

    # Sahne basina TEK aday: ilk uygun slayt. Ikinci bir alan, ayni bolumu
    # doldurulmayi bekleyen iki bos panelle birakir.
    adaylar: list[tuple[int, int]] = []
    for i, scene in enumerate(scenes):
        for j, spec in enumerate(scene.get("content") or []):
            if spec.get("kind") == "question":
                continue
            if _medya_yeri_var(spec.get("layout") or "content", spec):
                adaylar.append((i, j))
                break

    secilen = [(i, j) for i, j in adaylar
               if _medya_istegi(scenes[i]["content"][j]) is not None]
    for aday in adaylar:
        if len(secilen) >= hedef:
            break
        if aday not in secilen:
            secilen.append(aday)
    secilen.sort()

    eksik = [(i, j) for i, j in secilen
             if _medya_istegi(scenes[i]["content"][j]) is None]
    tarifler: dict[int, dict] = {}
    if eksik:
        satirlar = []
        for no, (i, j) in enumerate(eksik, 1):
            spec = scenes[i]["content"][j]
            satirlar.append(
                f"{no}. bolum: {scenes[i].get('title') or scenes[i].get('name')} | "
                f"duzen: {spec.get('layout') or 'content'} | "
                f"baslik: {spec.get('title') or '-'} | "
                f"metin: {' '.join(str(spec.get('body') or '').split())[:220] or '-'}")
        on_progress(f"{len(eksik)} slayt icin gorsel/video siparisi yaziliyor…")
        try:
            yanit = _run_json(
                MEDYA_PROMPT.replace("{profile}", _profile_text(options))
                            .replace("{slaytlar}", "\n".join(satirlar)),
                model=model, on_progress=on_progress, timeout=MEDYA_SURESI)
        except StoryError:
            yanit = {}
        for kayit in (yanit.get("siparisler") or []):
            try:
                no = int(kayit.get("no"))
            except (TypeError, ValueError):
                continue
            tarifler[no] = kayit

    notlar: list[str] = []
    for no, (i, j) in enumerate(eksik, 1):
        spec = scenes[i]["content"][j]
        aday = _medya_istegi({"medya": tarifler.get(no)})
        if aday is None:
            # Kapagin mekanik yedegi ayri: kursun kunyesini bilir, slaydin
            # tek cumlesini tekrar etmez.
            ham = (_kapak_istegi(options, brief)
                   if (spec.get("layout") or "") == "cover"
                   else {"tur": "gorsel",
                         "aciklama": _mekanik_aciklama(scenes[i], spec)})
            aday = _medya_istegi({"medya": ham})
            notlar.append(f"{spec.get('title') or scenes[i].get('name')}: "
                          "tarif modelden gelmedi, slaydin metninden yazildi")
        spec["medya"] = aday
    notlar.insert(0, f"{len(secilen)} slayta gorsel/video istegi kondu "
                     f"(hedef {hedef}, uygun slayt {len(adaylar)})")
    return notlar


def _medya_yeri_var(layout: str, spec: dict) -> bool:
    """compose_slide bu slaytta GERCEKTEN yer ayirir mi.

    Ayirmayacagi bir slaytta istegi kaydetmek, dosyayi sonradan metnin ustune
    dusurmek demek: alan None doner ve panel varsayilan bir karta duser, ki o
    kart metnin durdugu yere denk gelebilir. Olculdu: bullets ve statement
    duzenlerinde alan HER ZAMAN None, content+panel'de ise varyanta gore
    degisiyor -- bazi varyantlarin panel sutunu yok.

    Bu yuzden yalnizca kesin olan iki durum kabul edilir: kapak (hero) ve duz
    metinli content (bleed). Ikisi de varyanttan bagimsiz olarak yer ayirir.
    """
    if layout == "cover":
        return True
    return layout == "content" and not spec.get("bullets")


def _medya_stili(layout: str) -> str:
    """Istegin hangi alana oturacagi. Duzen karar verir, istegin turu degil.

    hero  kapakta: gorsel slaydin zemini olur, yazi ortunun uzerinde kalir
    bleed icerikte: sag kenardan tasan tam boy blok, yazi sola cekilir

    "panel" yok: o, varyantin panel sutunu varsa ayrilan karttir ve
    olmadiginda sessizce hicbir yer ayirmaz.
    """
    return "hero" if layout == "cover" else "bleed"


def _icerik_istemi(scene: dict, arity_text: str, options: dict,
                   profile: str, brief: str) -> str:
    """Bir sahnenin icerik istemi. Dongu de yeniden-isteme de BURADAN alir;
    iki yerde kurulsaydi biri gunceenmeden kalirdi."""
    return (CONTENT_PROMPT
            .replace("{scene}", str(scene.get("title") or scene.get("name")))
            .replace("{plan}", json.dumps(scene.get("slides") or [], ensure_ascii=False))
            .replace("{arities}", arity_text)
            .replace("{tone_rule}", TONES.get(options.get("tone", ""), ""))
            .replace("{profile}", profile)
            .replace("{brief}", brief)
            .replace("{ogretim}", ogretim.ORTAK_KURALLAR))


def _kadans_uyarisi(ihlaller: list[str]) -> str:
    """Ihlalleri ADIYLA soyleyen ek talimat -- model kendi planini duzeltsin."""
    bas = ("\n\nONCEKI ISKELET SU KURALLARI CIGNEDI, DUZELTEREK YENIDEN URET:\n")
    orta = "\n".join(f"- {i}" for i in ihlaller)
    son = "\nSlayt sayisini AZALTMA; soruyu dogru yere koyarak coz.\n"
    return bas + orta + son

def build(
    path: str,
    brief: str,
    *,
    model: str = "sonnet",
    palette: dict | None = None,
    options: dict | None = None,
    on_progress=lambda text: None,
) -> dict:
    """Design a course from the brief and build it, section by section.

    options carries the setup: title, audience, goal, minutes, sections,
    questions_per_section, tone. Anything omitted simply is not asserted.
    """
    options = options or {}
    profile = _profile_text(options)
    budget = slide_budget(options)

    # One style and one palette for the whole course: consistent inside, and
    # different from the next course, because both are derived from its title
    # rather than fixed in the composer.
    seed = options.get("title") or brief[:60]
    look = compose.style_for(options.get("style"), seed=seed)
    if not palette and (options.get("theme") or options.get("bg")):
        # Panel artik tam palet gonderiyor; bu dal yalnizca dogrudan cagiran
        # icin. derive_palette DEGIL: o, zemini marka renginden hesapliyor ve
        # marka koyuysa vurgu ile zemin cakisiyor.
        theme = (options.get("theme") or "").strip()
        if theme and theme != "ozel":
            palette = {k: v for k, v in compose.theme_palette(theme).items()
                       if not k.startswith("_")}
        elif options.get("bg"):
            palette = compose.palette_from(options["bg"], options.get("accent"))

    # What the project can actually score dictates how questions must be
    # written. Asking for four options when nothing can hold four produces
    # questions that have to be downgraded to plain menus afterwards.
    pkg_probe = StoryPackage(path)
    shapes_available = authoring.available_question_shapes(pkg_probe)
    arities = sorted({(o["type"], o["choices"]) for o in shapes_available})
    arity_text = ", ".join(
        f"{'tek dogru cevap' if t == 'freePickOneIntr' else 'birden fazla dogru cevap'}"
        f" ile {c} secenek" for t, c in arities
    ) or "yok"

    # Ne kadar bekleyecegi YAZIYOR. Akista saniye sayaci var ama "ne kadari
    # normal" bilinmeden sayac yalnizca kaygi uretir: olculen en uzun iskelet
    # 6.5 dakika surdu ve o koşu, kullaniciya asilmis gibi gorundu.
    on_progress("Kurs iskeleti tasarlaniyor… (uzun brief'lerde dakikalar "
                "surebilir; olculen en uzunu 6.5 dakika)")
    outline_istemi = (
        OUTLINE_PROMPT.replace("{brief}", brief)
                      .replace("{slide_budget}", str(budget))
                      .replace("{question_rule}", _question_rule(options, arity_text))
                      .replace("{profile}", profile)
                      .replace("{ogretim}", ogretim.ORTAK_KURALLAR))
    outline = _run_json(outline_istemi, model=model, on_progress=on_progress,
                        timeout=ISKELET_SURESI, deneme=1)
    scenes = outline.get("scenes") or []
    if not scenes:
        raise StoryError("Iskelet uretilemedi.")

    # KAPI: iskelet KURULMADAN once denetlenir; icerik gecisi duzeltilmis
    # plani alir, yani eklenen soru yuvalari icin icerik de yazilir.
    #
    # SIRA: ihlali adiyla soyle -> bir kez yeniden iste -> hala varsa yama.
    # Yeniden kontrol AYNI saf dedektorle yapilir, yani TUM kural setine
    # karsi: model bir ihlali giderirken baskasini uretirse yakalanir.
    duzeltmeler: list[tuple[str, str]] = []
    ihlaller = (_kadans_ihlalleri(scenes, options) + _duzen_ihlalleri(scenes)
                + _ayrac_ihlalleri(scenes))
    if ihlaller:
        # "plan ihlali", cunku liste artik UC kural ailesini birden tasiyor:
        # kadans (soru ritmi), duzen (bilesim cesitliligi) ve ayrac. Hepsine
        # "kadans" demek, akisi okuyan kisiyi yanlis kurala gonderir.
        on_progress("plan ihlali: " + "; ".join(ihlaller)
                    + " -- iskelet yeniden isteniyor")
        try:
            aday = (_run_json(outline_istemi + _kadans_uyarisi(ihlaller),
                              model=model, on_progress=on_progress,
                              timeout=ISKELET_SURESI, deneme=1)
                    .get("scenes") or [])
        except StoryError:
            aday = []       # yeniden isteme basarisiz; yama zaten devrede
        if aday and _plan_kabul_edilebilir(aday, scenes):
            aday_ihlal = (_kadans_ihlalleri(aday, options)
                          + _duzen_ihlalleri(aday) + _ayrac_ihlalleri(aday))
            if len(aday_ihlal) < len(ihlaller):
                scenes, ihlaller = aday, aday_ihlal
                duzeltmeler.append(("iskelet", "yeniden istendi ve duzeldi"))
    # ETIKET YALAN SOYLEMESIN. Iki yamanin ciktisi tek listede toplanip
    # hepsi "kadans --" diye basiliyordu; ayrac duzeltmesi kadans duzeltmesi
    # DEGIL ve akisi okuyan kisi hangi kuralin devreye girdigini oradan
    # ogreniyor. Olculdu 2026-08-29: dort ayrac cikarildi ve dordu de
    # "kadans" adiyla yazildi.
    if ihlaller:
        for d in _kadans_yamasi(scenes, options):
            duzeltmeler.append(("kadans", d))
        for d in _ayrac_yamasi(scenes):
            duzeltmeler.append(("ayrac", d))
    for etiket, d in duzeltmeler:
        on_progress(f"{etiket} -- {d}")

    planned = sum(len(s.get("slides") or []) for s in scenes)
    on_progress(f"{len(scenes)} bolum, {planned} slayt planlandi "
                f"(hedef ~{budget}; soru bicimleri: {arity_text}). Icerik yaziliyor…")

    # Content first, all of it, before anything is written to the project: a
    # half-generated course is worse than none.
    for index, scene in enumerate(scenes, 1):
        on_progress(f"Icerik {index}/{len(scenes)}: {scene.get('name', '')}")
        filled = _run_json(
            _icerik_istemi(scene, arity_text, options, profile, brief),
            model=model, on_progress=on_progress,
        )
        scene["content"] = filled.get("slides") or []

    # IKINCI KAPI -- YETKILI OLAN BU. Plan kapisi yetmiyor: yukaridaki satir
    # plani icerik ciktisiyla BUTUNUYLE degistiriyor ve plana uydugu hic
    # denetlenmiyor. Olculdu 2026-08-28: plan temizken uretilen kursta bir
    # konu sahnesi sorusuz kaldi ve plan kapisi hicbir sey raporlamadi.
    #
    # Burada YAMA YOK: icerik asamasinda eksik soruyu yamamak, metnini
    # uydurmak demek olurdu. Bunun yerine O SAHNENIN icerigi bir kez
    # yeniden istenir; yine gelmezse durum RAPOR EDILIR, sessiz gecmez.
    # DUZEN CESITLILIGI ICERIKTE OLCULUR, PLANDA DEGIL. Icerik gecisi
    # `scene["content"] = filled.get("slides")` ile plani BUTUNUYLE
    # degistiriyor: plandaki duzen dagilimi ne olursa olsun, ogrencinin
    # gordugu duzen buradan geliyor. Yalnizca plani duzeltmek, olculmeyen
    # bir yerde yesil gormekti -- ayni tuzak `_kadans_ihlalleri`nin
    # docstring'inde soru icin yazili.
    # SIRA: once ayrac, sonra duzen. Ayrac yamasi bir section'i statement'a
    # cevirdiginde ortaya YENI bir govde duzeni cikiyor; duzen yamasi once
    # kosarsa o kazanci goremez ve gereksiz bir ikinci takas yapar.
    for d in _ayrac_yamasi(scenes, "content"):
        on_progress(f"ayrac -- {d}")
    for d in _duzen_yamasi(scenes, "content"):
        on_progress(f"duzen -- {d}")

    icerik_ihlalleri = _kadans_ihlalleri(scenes, options, "content")
    if icerik_ihlalleri:
        on_progress("icerik kadansi: " + "; ".join(icerik_ihlalleri))
        for i_s in _konu_araligi(scenes):
            scene = scenes[i_s]
            if any(_soru_mu(x) for x in (scene.get("content") or [])):
                continue
            on_progress(f"{scene.get('name', '')}: soru dusmus, icerik yeniden isteniyor")
            try:
                tekrar = _run_json(
                    _icerik_istemi(scene, arity_text, options, profile, brief)
                    + _kadans_uyarisi([f"{scene.get('name', '')} sahnesinde soru yok"]),
                    model=model, on_progress=on_progress)
            except StoryError:
                tekrar = {}
            aday = tekrar.get("slides") or []
            if any(_soru_mu(x) for x in aday):
                scene["content"] = aday
                on_progress(f"kadans -- {scene.get('name', '')}: icerik yeniden istendi, soru geldi")
                duzeltmeler.append(f"{scene.get('name', '')}: icerik yeniden istendi")
        icerik_ihlalleri = _kadans_ihlalleri(scenes, options, "content")
        for d in icerik_ihlalleri:
            on_progress(f"KADANS ACIK KALDI -- {d}")

    # MEDYA PLANI. Icerik tamam, slaytlar henuz yok: hangi slaydin gorsel ya da
    # video isteyecegi ancak butun kurs gorunurken secilebilir (sahne basina
    # tek, toplam kurs uzunluguna oranli). Slaytlar kurulurken secilseydi
    # "kac tane oldu" ancak son slaytta bilinirdi.
    for d in _medya_plani(scenes, options, brief, model, on_progress):
        on_progress(f"medya -- {d}")

    on_progress("Slaytlar olusturuluyor…")
    pkg = StoryPackage(path)
    content_template = _content_template(pkg)
    created, questions, fallbacks = 0, 0, 0
    refusals: list[dict] = []
    known_limits: set = set()
    # Kurs boyunca tasinir: yasak ancak bir onceki slaydin varyanti bilinirse
    # uygulanabilir, ve envanter ancak butun kullanimlar toplanirsa aralik
    # verebilir. Sahne dongusunun disinda durur -- sahne sinirinda sifirlanirsa
    # her sahnenin ilk slaydi bir oncekiyle ayni cikabilir.
    # GECMIS, tek bir "onceki" degil.
    #
    # Once `last_variant` tek bir ad tutuyordu ve HER slaytta yazilyordu --
    # varyanti olmayan duzenler (cover, section, bullets, steps, statement,
    # menu) None dondurunce gecmis SIFIRLANIYORDU. Bir kapak slaydindan
    # sonraki iki content slaydi ayni varyanti alabiliyordu ve yasak hic
    # calismamis oluyordu. Olculdu: iki content slaytli bir kursta "1 farkli
    # varyant, 1 ardisik tekrar".
    #
    # Liste ayrica araligi da buyutur: secim en uzun suredir kullanilmayana
    # gider, yalnizca bir oncekinden kacmakla yetinmez.
    history: list[str] = []
    # SORULARIN KENDI GECMISI. Icerik slaytlarinda ardisik tekrar yasagi
    # vardi, sorularda YOKTU: `pick_template` katalogdaki ilk uyan sablonu
    # donduruyordu, yani kutuphane ne kadar buyurse buyusun bir kurstaki
    # butun sorular ayni gorunusu giyiyordu. Olculdu 2026-08-29: uretilmis
    # 6 modulde 25 soru, 2 bicim -- ve toy.story'de 15 sorunun 15'i tek
    # bicim. Liste `avoid` olarak asagi gecer ve secim en uzun suredir
    # kullanilmayana gider; icerik tarafiyla ayni olcu.
    #
    # SAHNE SINIRINDA SIFIRLANMAZ, `history` ile ayni sebeple: her sahnenin
    # ilk sorusu bir oncekinin sonuncusuyla ayni cikardi.
    soru_gecmisi: list[str] = []
    variant_log: list[dict] = []
    kurulan_sahneler: list[str] = []
    # Yapay zekanin istedigi ama veremedigi seyler. Kurs onlari beklemez:
    # slayt alani ayrilmis olarak kurulur, istek `<kurs>.medya.json` icinde
    # bekler ve panelin "Gorsel & Video" sekmesinde kullaniciya gorunur.
    medya_istekleri: list[dict] = []

    for scene in scenes:
        scene_name = scene.get("name") or "Bolum"
        sahne_medyasi = 0
        try:
            compose.create_scene  # noqa: B018 - presence check only
        except AttributeError:
            pass
        from storyline_mcp.clone import create_scene
        try:
            kuruldu = create_scene(pkg, scene_name)
            kurulan_sahneler.append(kuruldu["scene_guid"])
        except StoryError:
            pass  # scene already exists

        for spec in scene["content"]:
            if spec.get("kind") == "question":
                choices = spec.get("choices") or []
                prompt = spec.get("prompt", "Soru")
                try:
                    # Cerceve olculur, kalan alan bulunur, sablon o alana gore
                    # secilir. Secimi add_question'a birakmak, alani hic
                    # sormadan sablon secmek demekti.
                    # EYEBROW KABUL TESTINE DE GECER. Gecmiyordu ve olculdu:
                    # kabul testi bandi %59.3 sanip "sigar" diyor, cerceve
                    # eyebrow'lu %54.1 ile calisip REDDEDIYORDU. Ayni deger
                    # zaten add_question'a geciliyor; iki cagrinin ayni
                    # bandi gormemesi icin bir sebep yoktu.
                    picked = authoring.pick_template_for_question(
                        pkg, prompt, choices,
                        eyebrow=scene.get("title") or scene_name,
                        avoid=soru_gecmisi)
                    made = authoring.add_question(
                        pkg, picked["template"], prompt, choices,
                        spec.get("correct") or [0], scene=scene_name,
                        name=prompt[:60],
                        # Gomulu tohum baska bir kursun bolum adini ve rengini
                        # tasiyor; bunlar verilmezse ogrenci yanlis bolum
                        # adini gorur.
                        eyebrow=scene.get("title") or scene_name,
                        palette=palette,
                        # Gomulu tohumun geri bildirim katmanlari hasat
                        # edildigi kursun metnini tasiyor; verilmezse notr
                        # varsayilan yazilir, tohumunki asla kalmaz.
                        feedback=spec.get("feedback"),
                    )
                    # TEK YERLESIM OTORITESI: compose_question_frame.
                    #
                    # Burada bir zamanlar `apply_choice_plan` dali vardi ve
                    # `made["framed"]` false ise kosuyordu. Olculdu: uretimde
                    # 0/4 -- tohum yolu HER ZAMAN framed donuyor, yani o dal
                    # hic calismiyordu. Ustelik iki kusur tasiyordu (sabit
                    # genislik varsayimi, yuzde planin yanlis uzaya
                    # uygulanmasi). Silindi; gerekcesi DEVIR 4d'de.
                    verdict = {}
                    # Secilen sablon geçmişe YAZILIR. Yazilmazsa `avoid` hep
                    # bos kalir ve siralama hicbir sey degistirmez -- kapinin
                    # kurulup baglanmamasi, bu projenin bilinen kusuru.
                    soru_gecmisi.append(picked["template"])
                    questions += 1
                    # Bilinen sinirdan gelen redler ayri sayilir. Her koşuda
                    # tekrar edecekleri icin gercek bir yetersizligi
                    # gizlemesinler: rapor "3 sablon bilinen sinir yuzunden
                    # disarida" ile "2 sablon icerik sigmadigi icin reddedildi"
                    # arasindaki farki gosterebilmeli.
                    real = [r for r in picked["rejections"]
                            if not r.get("known_limit")]
                    if real:
                        refusals.append({
                            "prompt": prompt[:60], "choices": len(choices),
                            "diagnosis": "sigdi-ama-elendi",
                            "why": f"sigdi, ama once {len(real)} sablon icerik "
                                   "nedeniyle reddedildi",
                            "templates_tried": len(picked["rejections"]),
                            "resolved": True,
                        })
                    known_limits.update(
                        r["template"] for r in picked["rejections"]
                        if r.get("known_limit"))
                    continue
                except StoryError as exc:
                    # Nothing can score this many options. The choices still
                    # become a real decision, as a menu of buttons -- a slide
                    # that works, clearly marked as unscored in the report.
                    #
                    # The reason is kept, not just the count. A course that
                    # quietly drops to its third choice is still a valid file,
                    # so nothing fails and nothing complains; the only way to
                    # notice the template catalogue going thin is to read why
                    # each question gave up.
                    fallbacks += 1
                    detail = getattr(exc, "rejections", None)
                    refusals.append({
                        "prompt": prompt[:60],
                        "choices": len(choices),
                        # Teshis turu de kayda giriyor: "sablon dar" ile "kok
                        # cerceveyi yedi" farkli isler gerektiriyor ve ikisini
                        # tek sayida toplamak, hangisinin oldugunu kaybetmek.
                        # UC DEGIL DORT TESHIS (2026-08-17). "etiket",
                        # cerceve taban puntoda bile sigdiramadiginda gelir
                        # ve digerlerinden ayri is gerektirir: kataloga
                        # sablon eklemek de koku kisaltmak da cozmez, sikkin
                        # KENDISI kisalmali.
                        "diagnosis": (
                            "etiket" if isinstance(exc, authoring.ChoiceLabelsTooLong)
                            else "metin" if isinstance(exc, authoring.StemStarvesFrame)
                            else "sablon"),
                        "why": str(exc)[:140],
                        "templates_tried": len(detail) if detail else 0,
                    })
                    # BUTUN SIKLAR GECER. `choices[:4]` idi ve BESINCI
                    # SIKKI SESSIZCE ATIYORDU -- ogrenci bes secenekten
                    # dordunu goruyor, rapor bunu soylemiyordu. Duzenden
                    # agir: icerik kaybi.
                    #
                    # Kirpma muhtemelen yigin slayttan tastigi icin
                    # konulmustu; sebep artik yok, cunku buton bandi
                    # _button_band ile SAYIDAN ayriliyor (bes buton
                    # 5*4.0 + 4*1.6 = %26.4 ve banda siğar).
                    spec = {"kind": "content", "layout": "menu",
                            "title": spec.get("prompt", "Soru"),
                            "buttons": choices}

            duzen = spec.get("layout") or "content"
            # Bir sahnede tek istek: ikinci bir alan, bir bolumu doldurulmayi
            # bekleyen iki bos panelle birakabilir.
            # Yuvalar ARTIK BURADA SECILMIYOR: _medya_plani, icerik tamamken
            # hangi slaytlarin isteyecegini kursun tamamina bakarak secti ve
            # spec["medya"]'ya yazdi. Buradaki is yalnizca uygulamak.
            istenen = _medya_istegi(spec) if sahne_medyasi == 0 else None
            # SESSIZ DUSME OLMASIN. Istek uc ayri sebeple dusebilir ve ucu de
            # disaridan AYNI gorunur: "kurs medyasiz cikti". Hangisi oldugu
            # akista yazmazsa, model mi istemedi yoksa kapi mi dusurdu ayirt
            # edilemez -- olculdu 2026-08-29: kurs medyasiz cikti ve hicbir
            # kayit sebebini soylemedi.
            if spec.get("medya") and not istenen and sahne_medyasi == 0:
                on_progress(f"medya istegi dusuruldu ({spec.get('title', '')}): "
                            "aciklama siparis degil ya da tur taninmadi")
            if istenen and not _medya_yeri_var(duzen, spec):
                on_progress(f"medya istegi dusuruldu ({spec.get('title', '')}): "
                            f"{duzen} duzeninde gorsel alani ayrilamiyor")
                istenen = None          # yer ayrilamayacak slaytta istek tutma
            stil = _medya_stili(duzen) if istenen else "panel"
            new = authoring.add_slide(pkg, content_template, scene=scene_name,
                                      name=(spec.get("title") or "Slayt")[:60])
            laid = compose.compose_slide(
                pkg, new["new_slide"], duzen,
                title=spec.get("title"), eyebrow=spec.get("eyebrow"),
                body=spec.get("body"), bullets=spec.get("bullets"),
                buttons=spec.get("buttons"), palette=palette,
                index=spec.get("index"), style=look["name"], clear=True,
                identity=seed, avoid_variant=history,
                image_area=bool(istenen), image_style=stil,
            )
            # KAYIT, AYRILMIS ALANA BAGLI. Kapi "yer var" dese bile yetkili
            # olan motorun donusudur; alan yoksa istek de yok, cunku dosya
            # geldiginde konacagi yer varsayilan bir kutuya duser ve o kutu
            # metnin ustune gelebilir.
            if istenen and not laid.get("image_area"):
                on_progress(f"medya istegi dusuruldu ({spec.get('title', '')}): "
                            "motor bu varyantta yer ayirmadi")
            if istenen and laid.get("image_area"):
                sahne_medyasi += 1
                medya_istekleri.append(medya.istek(
                    new["new_slide"], scene_name,
                    spec.get("title") or "Slayt", istenen["tur"],
                    istenen["aciklama"], saniye=istenen.get("saniye"),
                    # Alani MOTOR verir, prompt degil: dosya geldiginde tam
                    # olarak burada ayrilan yere oturur.
                    alan=laid.get("image_area"),
                    # Piksel boyutu O SLAYDIN cercevesinden cikar. Projenin
                    # bildirdigi boyut degil: ikisi ayrisabiliyor ve ayristigi
                    # anda siparis, yerlesimin kullanmayacagi bir orani ister.
                    sahne_px=medya.slayt_olcusu(pkg, new["new_slide"]),
                    stil=laid.get("image_style") or stil,
                    sira=len(medya_istekleri) + 1))
            # Yasagi tasiyan tek sey bu satir: bir onceki slaydin varyanti
            # sonrakine gecmezse motor her slaytta ayni tohumdan ayni secimi
            # yapar ve komsu iki slayt ayni silueti tasiyabilir.
            if laid["variant"]:
                history.append(laid["variant"])
            variant_log.append({"slide": created, "layout": laid["layout"],
                                "variant": laid["variant"],
                                "repeated": laid["variant_repeated"]})
            created += 1

    # A2: kurs, ogrencinin gordugu ilk ekranda BOS olmasin. Kurucu kendi
    # sahnelerini sona ekliyordu ve kurs, sablondan devralinan bos bir slaytla
    # aciliyordu -- uretilen her sey bir alt siradaydi. Hicbir sey silinmez,
    # devralinan sahneler yalnizca arkaya duser (secenekler ve gerekcesi
    # clone.promote_scenes'in belge dizesinde).
    from storyline_mcp.clone import promote_scenes
    siralama = promote_scenes(pkg, kurulan_sahneler)

    report = pkg.save(Path(path), backup=True)
    # Defter kursla birlikte YENILENIR. Onceki kurulumun istekleri artik baska
    # slaytlari gosteriyor olurdu -- slayt dosyalari yeniden uretildi.
    if medya_istekleri:
        medya.yaz(path, medya_istekleri)
        on_progress(f"{len(medya_istekleri)} medya istegi yazildi -- "
                    "panelde 'Gorsel & Video' sekmesinde bekliyor")
    else:
        medya.temizle(path)
    return {
        "opens_on": siralama,
        # Kurs eksiksiz kuruldu ama TAMAMLANMADI: bu kadar slayt bir dosya
        # bekliyor. Sayi raporda durmazsa istek yalnizca sekmede kalir ve
        # kimse bakmadikca bos panel kursla birlikte yayina gider.
        "medya_istekleri": len(medya_istekleri),
        "scenes": len(scenes),
        "slides_created": created,
        "questions": questions,
        "question_fallbacks": fallbacks,
        # Sayı değil gerekçe: kaç soru hangi sebeple sınav olamadı. Çıktı
        # sağlam olduğu için hiçbir test bunu yakalayamaz; katalogun
        # yetersizleştiğini fark etmenin tek yolu bunu okumak.
        "question_refusals": refusals,
        # HANGI GORUNUSLER KULLANILDI. Sayi degil kume: "8 soru" ile "8 soru,
        # 1 gorunus" ayni satirda ayni gorunuyordu ve tekduzelik tam olarak
        # ikincisi. Kutuphane buyudugunde bunun da buyumesi gerekir; buyumuyorsa
        # eklenen tohum uretime hic ulasmamis demektir.
        "question_looks": sorted(set(soru_gecmisi)),
        "question_look_uses": len(soru_gecmisi),
        # Kabul edilmis sinir, her kosuda ayni: gurultu degil, envanter.
        "known_template_limits": sorted(known_limits),
        # Ardisik tekrar yasaginin envanteri: kac kez cignendi VE ne kadar
        # arayla. Sayi tek basina iki farkli gorunumu ayni gosteriyor.
        "variety": compose.variety_report(variant_log),
        # ISLEVSEL EKSIKSIZLIK. Bugune kadar her olcu geometrikti; hicbiri
        # "bu kurs calisir mi" diye sormuyordu. Olculdu: bir kursta 14 bos
        # slayt ve 33 kopuk tetikleyici vardi ve HEPSI kaynak dosyadan
        # geliyordu -- kurucu kendi slaytlarini EKLIYOR, kaynakta ne varsa
        # oldugu gibi birakiyor ve o da ogrenciye gidiyor.
        #
        # Silinmiyor: kullanicinin dosyasindaki slaytlar onun. Ama sessiz
        # kalmak, bos bir sahneyi kursun parcasi yapmak demek.
        "inherited": _inherited(path),
        "style": look["name"],
        "palette": palette or "varsayilan",
        "verified": report["verified"],
        "written": report["written"],
    }
