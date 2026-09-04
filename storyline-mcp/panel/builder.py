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

try:
    from . import ogretim
except ImportError:  # pragma: no cover - script execution fallback
    import ogretim

try:
    from . import production
except ImportError:  # pragma: no cover - script execution fallback
    import production

try:
    from . import ilerleme
except ImportError:  # pragma: no cover - script execution fallback
    import ilerleme

try:
    from . import dallanma
except ImportError:  # pragma: no cover - script execution fallback
    import dallanma

try:
    from .agent import find_cli
except ImportError:  # pragma: no cover - script execution fallback
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
    reveal     BIR SEFERDE OKUNMAYAN slayt: basliklar gorunur, aciklama
               TIKLAYINCA acilir. Birbirinden ayri 3-5 kavram, belirti ya da
               adim varsa BUNU kullan -- ogrenci her birini kendi acar.
- kind: "content", "question", "drag" (gruplama), "commitment" (yazdirma) veya "hotspot" (sicak nokta)
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
- KURSTA EN AZ BIR REVEAL OLSUN (govde slaydi ucten fazlaysa). Gerekcesi
  olculdu: kalan alti duzenin hepsi "sayfaya yerlestirilmis metin" ve ogrenci
  onlarda ilerlemekten baska bir sey yapmiyor. Reveal, ogrencinin ELINI
  isin icine sokan tek icerik duzeni.
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
  {"kind": "content", "layout": "reveal", "eyebrow": "Belirtiler",
   "title": "Kisa baslik", "body": "Tek cumlelik yonerge.",
   "items": [{"label": "Kisa etiket", "detail": "Bir iki cumlelik aciklama."},
             {"label": "Kisa etiket", "detail": "Bir iki cumlelik aciklama."},
             {"label": "Kisa etiket", "detail": "Bir iki cumlelik aciklama."}]},
  {"kind": "content", "layout": "content", "eyebrow": "Ornek",
   "title": "Kisa baslik", "body": "Bir iki cumle.",
   "medya": {"tur": "video", "saniye": 20,
             "aciklama": "Cerceve ne gostersin, tek iki cumle."}},
  {"kind": "question", "prompt": "Soru metni?",
   "choices": ["A secenegi", "B secenegi", "C secenegi", "D secenegi"],
   "correct": [1],
   "feedback": {"correct": "Neden dogru oldugunu tek cumleyle acikla.",
                "incorrect": "Neden yanlis oldugunu ve dogru davranisi tek cumleyle acikla."}},
  {"kind": "drag", "prompt": "Her ogeyi dogru kutuya surukle.",
   "groups": {"Kutu bir": ["Kisa ad", "Kisa ad"],
              "Kutu iki": ["Kisa ad", "Kisa ad"]},
   "feedback": {"correct": "Tek cumlelik gerekce.",
                "incorrect": "Tek cumlelik gerekce."}},
  {"kind": "commitment", "prompt": "Bu haftaki tek somut adimini yaz."},
  {"kind": "hotspot", "prompt": "Gorsel uzerindeki dogru bolgeye tiklayin.",
   "feedback": {"correct": "Tek cumlelik gerekce.",
                "incorrect": "Tek cumlelik gerekce."}}
]}

Kurallar:
- Slayt sirasi ve layout degerleri asagidaki plana uysun.
- HER DUZEN KENDI ALANINI ISTER, yoksa slayt bos cikar:
    reveal     -> items (3-5 tane), her biri label + detail. bullets DEGIL.
                  label TEK SATIRLIK bir ad (en fazla 30 karakter, cumle
                  degil); detail bir iki cumle. Etiket sigmazsa slayt bos
                  bir bant olur.
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
        ("Istenen Soru/Etkilesim Tipleri", options.get("question_types")),
    ]
    lines = [f"- {label}: {value}" for label, value in fields if value]
    return "\n".join(lines) if lines else "- (belirtilmedi)"


def _question_rule(options: dict, arities: str) -> str:
    per = options.get("questions_per_section")
    q_types = options.get("question_types")

    type_rule = ""
    if q_types:
        if isinstance(q_types, str):
            q_types_list = [t.strip() for t in q_types.split(",") if t.strip()]
        else:
            q_types_list = list(q_types)

        type_names = {
            "single": "question (tek secmeli)",
            "multiple": "question (cok secmeli)",
            "drag": "drag (surukle-birak gruplama)",
            "hotspot": "hotspot (sicak nokta)",
            "commitment": "commitment (metin girisi)",
        }
        allowed = [type_names.get(t, t) for t in q_types_list if t in type_names]
        if allowed:
            type_rule = (
                f"- SECILEN SORU TIPLERI: {', '.join(allowed)}. "
                "Sahnelere soru/etkilesim dagitirken YALNIZCA kullanicinin sectigi bu tipleri kullan.\n"
            )

    if per in (None, "", "auto"):
        rule = ("- Her konu sahnesinde en az 1 soru/etkilesim bulunsun.\n"
                f"- Soru bicimleri: {arities}\n")
    else:
        try:
            count = int(per)
        except (TypeError, ValueError):
            count = 1
        if count <= 0:
            return ("- Bu kursta SORU OLMAYACAK. Hicbir sahneye question ekleme.\n"
                    "  Kullanici bunu ACIKCA istedi; yukaridaki ortak soru\n"
                    "  kurallari bu kursta GECERSIZDIR.\n")
        rule = (f"- Her konu sahnesinde TAM OLARAK {count} adet soru/etkilesim bulunsun.\n"
                f"- Soru bicimleri: {arities}\n")

    return rule + type_rule


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
                [str(cli), "-p", prompt, "--output-format", "json", "--model", model],
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
    """Ask the model for JSON, with no tools attached."""
    cli = find_cli()
    if cli is None:
        raise StoryError("Claude Code CLI bulunamadi.")

    try:
        result = _cli_json(cli, prompt, model, timeout, on_progress, deneme)
    except subprocess.TimeoutExpired:
        raise StoryError(
            f"Model {int(timeout)} saniyede yanit vermedi. Kursa hicbir sey "
            "yazilmadi; komutu yeniden calistirabilirsiniz.") from None

    if result is None or result.returncode != 0:
        err_msg = (result.stderr or "").strip()[:200] if result else "CLI yanit vermedi"
        raise StoryError(f"Icerik uretilemedi: {err_msg}")

    try:
        payload = json.loads(result.stdout)
        text = payload.get("result", "") or payload.get("response", "")
    except json.JSONDecodeError:
        payload, text = None, result.stdout

    # SIFIR CIKIS KODU BASARI DEMEK DEGIL. Claude Code limit dolduğunda ya da
    # erisim kapandiginda 0 ile cikip hatayi govdeye yaziyor. Bu bir zamanlar
    # agy'ye gecis isaretiydi; artik tek motor var, o yuzden ISARET HATA OLARAK
    # SOYLENIR -- yoksa asagidaki JSON aramasi bos donup kullaniciya sebebi
    # gizleyen "Yanitta JSON bulunamadi" hatasi verirdi.
    if isinstance(payload, dict):
        if (payload.get("is_error") or payload.get("api_error_status")
                or "disabled" in str(payload.get("result", "")).lower()):
            raise StoryError(
                "Claude Code istegi reddetti (limit dolmus ya da erisim kapali "
                f"olabilir): {str(text)[:200]}")

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


def _geri_bildirim_yazildi_mi(spec: dict, made: dict | None) -> str | None:
    """Yazarin geri bildirimi ISTENDI ama YAZILAMADI mi -- adiyla soyler.

    NICIN: soru kurucular geri bildirimi yazamadiklarini ZATEN raporluyor
    (`rewritten` / `drag_feedback` sifir doner) ama kurucu bakmıyordu ve
    kayip SESSIZ gecıyordu. Olculdu 2026-09-04: freeHotSpot tohumunda hic
    geri bildirim katmani YOK (bos bir <sldLayer /> var ve intrProps'un
    corFbG/incFbG'si tohumda bulunmayan katmanlari gosteriyor). Yani model
    geri bildirim yaziyor, kurucu geciriyor, hicbir yere konmuyor ve
    hicbir satir bunu soylemiyor.

    Bu fonksiyon KAYBI ONLEMEZ, GORUNUR KILAR. Onlemek tohuma katman
    klonlamak demek ve o ayri bir is.
    """
    if not (spec.get("feedback") or {}):
        return None
    if made is None:
        return None
    # IKI YERE BAKILIR. Soru kurucular iki ayri yoldan geciyor ve sayilar
    # ayni yerde DURMUYOR: `add_question` sonuclari duzlestirip ust duzeye
    # koyuyor, `add_hotspot_question` ise adapt_seeded_slide'in ciktisini
    # `adapted` altinda tasiyor. Yalnizca ust duzeye bakan bir kontrol,
    # tam da kaybin YASANDIGI aileyi (hotspot) gormezdi.
    icice = made.get("adapted") or {}
    for kaynak in (made, icice):
        yazilan = kaynak.get("rewritten")
        if yazilan is None:
            yazilan = kaynak.get("drag_feedback")
        if yazilan is not None:
            break
    if yazilan is None:
        return None                      # kurucu bildirmiyor; iddia etmeyelim
    if yazilan:
        return None
    return (f"{(spec.get('prompt') or spec.get('title') or 'soru')[:44]}: "
            f"geri bildirim yazildi ama slayda KONMADI "
            f"({spec.get('kind')})")


def _reveal_katmanlari(pkg: StoryPackage, slide: str, items: list[dict],
                       laid: dict) -> int:
    """Her etiketi kendi katmanina baglar: tikla, acilsin.

    NICIN VAR: ilk teshis (2026-09-04) su satirdi -- slayt sozlugunun
    yedisinden altisi "sayfaya yerlestirilmis metin". Ogrenci ilerlemekten
    baska bir sey yapmiyorsa, kapilarin hepsinden gecen bir kurs yine de
    sayfa cevirmektir. `reveal` o sozluge BIR SEFERDE OKUNAMAYAN ilk duzeni
    ekliyor: basliklar gorunur, aciklama tiklayinca gelir.

    MEKANIZMA YENI DEGIL, IKI OLCULMUS PARCANIN BILESIMI:
        compose_slide(layout="reveal")   menu ile ayni bant iskeleti
        authoring.add_layer(open_from=)  tiklayinca acilan katman

    ESLESME INDISLE, METINLE DEGIL: iki etiket ayni kelimeyle baslayabilir
    ve `add_layer` metinle de eslestirebiliyor -- yanlis butona baglanmis
    bir katman, disaridan dogru gorunur ve yanlis seyi acar. compose_slide
    buton GUID'ini `laid["buttons"][i]["shape"]` icinde donduruyor.
    """
    butonlar = laid.get("buttons") or []
    kurulan = 0
    for item, buton in zip(items, butonlar):
        guid = (buton or {}).get("shape")
        detay = (item or {}).get("detail")
        if not guid or not detay:
            continue
        try:
            authoring.add_layer(pkg, slide,
                                str(item.get("label") or "Ayrinti")[:40],
                                text=str(detay), open_from=guid)
            kurulan += 1
        except StoryError:
            # Katman kurulamazsa slayt YINE CALISIR: butonlar duruyor,
            # yalnizca acilacak bir sey yok. Kursu dusurmek, calisan bir
            # slaydi yok saymak olurdu.
            continue
    return kurulan


def _otomatik_ilerlemeyi_kaldir(pkg: StoryPackage, slide: str) -> int:
    """Klonlanan icerik slaydindan "acilir acilmaz sonrakine atla"yi siler.

    NICIN: `_content_template` sablonu "en az metin sekli olan" olcutuyle
    seciyor ve bu olcut DAVRANISA BAKMIYOR. Olculdu 2026-09-04, test/bos.story
    uzerinde: secilen sablon slide.xml idi ve slayt duzeyinde

        event=OnStart  action=jumpToSlide  actSubType=next

    tasiyordu. add_slide tetikleyicileri de klonladigi icin kurucunun urettigi
    HER icerik slaydi bunu devraldi -- uretilmis kursta 34 slayt. Sonuc:
    ogrenci bir icerik slaydina girer girmez bir sonrakine atiliyor ve zincir,
    boyle bir tetikleyicisi olmayan ilk slayda -- yani sahnenin sonundaki soru
    slaydina -- kadar suruyor.

    Kullanicinin bildirdigi bicimiyle: "herhangi bir slayda basinca o sahnedeki
    son slayta atiyor". Yazilan icerik hic gorunmuyordu.

    KAPSAM DAR, bilerek: yalnizca OnStart + jumpToSlide, yalnizca SLAYT
    duzeyinde, yalnizca kurucunun kendi olusturdugu slaytta.
      * OnNextButtonClick -> jumpToSlide DOKUNULMAZ: o, ogrencinin ileri
        tusuna basmasi -- gezinmenin kendisi.
      * Sekil uzerindeki tetikleyiciler DOKUNULMAZ: bir butonun atlamasi
        istenen davranis olabilir.
      * Devralinan slaytlar DOKUNULMAZ: kullanicinin dosyasindaki slaytlar
        onun (ayni sozlesme `_inherited` icin de gecerli).
    """
    part = pkg.slide_part_for(slide)
    root = pkg.parse(part)
    trig_list = root.find("trigLst")
    if trig_list is None:
        return 0
    silinen = 0
    for trig in list(trig_list):
        data = trig.find("data")
        if data is None:
            continue
        if (data.get("event") == "OnStart"
                and data.get("action") == "jumpToSlide"):
            trig_list.remove(trig)
            silinen += 1
    if silinen:
        pkg.replace_xml(part, root)
    return silinen


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


# PUANLANAN HER SEY SORUDUR, YALNIZCA "question" DEGIL.
#
# Bu kapi bir donem sadece kind == "question" sayiyordu ve gruplama eklenince
# sessizce yanlislasti: drag ile kapanan bir sahne "sorusuz" gorunur, kadans
# kapisi icerigi bosuna yeniden ister ve model soruyu SIK SECMEYE cevirerek
# "duzeltir" -- yani cesitlilik icin eklenen tip, cesitliligi olcen kapi
# tarafindan geri alinirdi.
#
# commitment DISARIDA, ve bu bilerek: puanlanmiyor, dogru cevabi yok. Onu
# soru saymak "her konu sahnesinde bir puanli olcum" kuralini bosaltirdi.
PUANLI_KINDLER = ("question", "drag")


def _soru_mu(s: dict) -> bool:
    return (s or {}).get("kind") in PUANLI_KINDLER


def _ardisik_okuma(scenes: list[dict], anahtar: str = "slides") -> int:
    """En uzun ardisik OKUMA serisi. TEK HESAPLAYAN YER.

    Seri sahne sinirinda SIFIRLANMAZ, bilerek: ogrenci sahne sinirini
    hissetmiyor, arka arkaya okudugu slaytlari hissediyor.

    Ayri bir fonksiyon, cunku iki yer ayni sayiya ihtiyac duyuyor ve ikisi
    ayri yazilsaydi ayrisirdi -- `_kadans_ihlalleri` ihlali bildirmek icin,
    `_ayrac_yamasi` ekledigi ayracin seriyi bozup bozmadigini anlamak icin.
    """
    seri = en_uzun = 0
    for scene in scenes:
        for s in scene.get(anahtar) or []:
            seri = 0 if _soru_mu(s) else seri + 1
            en_uzun = max(en_uzun, seri)
    return en_uzun


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

    en_uzun = _ardisik_okuma(scenes, anahtar)
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
GOVDE_DUZENLERI = ("content", "bullets", "steps", "statement", "menu",
                   "reveal")


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


def _sahne_basligi(scene: dict) -> str:
    """Sahnenin okunabilir adi. Once title, yoksa makine adindan turetilir.

    Sahne adlari "04_HalkaAcikAglar" biciminde -- basta sira numarasi, sonra
    bosluksuz CamelCase (OUTLINE_PROMPT Turkce karakter ve bosluk yasakliyor).
    Ogrenciye gosterilecek bir ayracin uzerine bunu oldugu gibi yazmak, makine
    adini arayuze sizdirmak olur.
    """
    baslik = (scene.get("title") or "").strip()
    if baslik:
        return baslik
    ham = re.sub(r"^\d+[_-]*", "", scene.get("name") or "")
    bolunmus = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", ham).replace("_", " ")
    return bolunmus.strip() or "Bolum"


# AYRAC KURALI, ve NICIN ASAMAYA GORE DEGISIYOR.
#
# Istenen son durum tek cumle: govde >= 2 ise ayrac olmali, olmamasi
# gereken yerde olmamali. Ama "olmamasi gereken"in siniri, o asamada
# elde bulunan CAREYE bagli -- ve bunu gormemek bir dongu uretti.
#
# PLAN asamasinda care SILME'dir. Slaytin yalnizca basligi var, silmek
# ucuz. Bir ayraci silmek gövde sayisini DEGISTIRMEZ (section zaten govde
# sayilmiyor), dolayisiyla yeni bir ihlal dogurmaz. Burada siki kural
# uygulanabilir: govde < 2 ise ayrac gitmeli.
#
# ICERIK asamasinda care CEVIRME'dir. Metin yazilmis; silmek modelin
# urettigi govdeyi cope atmak olurdu, o yuzden section -> statement.
# Ama statement BIR GOVDE SLAYDIDIR: cevirme govde sayisini bir artirir.
#
#     section + 1 govde  --cevir-->  2 govde, ayrac yok  -->  "ayrac olmali"
#
# Yani siki kurali icerik asamasinda uygulamak, az once kaldirdigi ayraci
# geri isteyen bir dongu uretiyor. Olculdu 2026-08-29 (sentetik): yama
# kostuktan sonra dedektor AYNI iki sahneyi yeniden ihlalli buldu.
#
# Cozum kurali gevsetmek degil, ASAMANIN CARESINE GORE yazmak:
#
#     plan    : govde < 2  -> ayrac gitmeli   (silme donguyu kapatmaz)
#     icerik  : govde == 0 -> ayrac gitmeli   (cevirme 0'i 1 yapar, durur)
#
# Icerikte kalan "section + 1 govde" hali bilincli olarak SERBEST. Arkasinda
# tek slayt olan bir ayrac gereksizdir ama zararsiz; arkasinda HIC slayt
# olmayan bir ayrac ise acikca yanlis. Plan asamasi zaten ilk elemeyi yapiyor
# ve olculdu (DOGRULAMA4): dort gereksiz ayracin dordu de orada temizlendi.
def _ayrac_siniri(anahtar: str) -> int:
    """Bu asamada ayracin YASAK oldugu govde sayisi ust siniri."""
    return 2 if anahtar == "slides" else 1


def _ayrac_ihlalleri(scenes: list[dict], anahtar: str = "slides") -> list[str]:
    """SAF TESPIT, CIFT YONLU: eksik ayrac da fazla ayrac da ihlaldir.

    Dedektor bir donem yalnizca FAZLA ayraci sayiyordu ve bu, kuralin
    yarisini denetlemek demekti: yama iki ayrac ekledigi halde dedektor
    "0 ihlal" diyordu, yani plan asamasinda model bu kusurdan HIC haberdar
    olmuyor ve akista da hicbir sey gorunmuyordu. Olculdu 2026-08-29
    (UZUN.story): iki govde slaydi tasiyan dort sahnenin ikisinde ayrac
    yoktu. Tek yonlu bir kural kendi kor noktasini yesil raporlar.
    """
    ihlaller = []
    konu = set(_konu_araligi(scenes))
    sinir = _ayrac_siniri(anahtar)
    for i, scene in enumerate(scenes):
        slaytlar = [s for s in (scene.get(anahtar) or []) if not _soru_mu(s)]
        ayrac = [s for s in slaytlar if (s.get("layout") or "content") == "section"]
        govde = [s for s in slaytlar
                 if (s.get("layout") or "content") in GOVDE_DUZENLERI]
        ad = scene.get("name") or "?"
        if ayrac and len(govde) < sinir:
            ihlaller.append(f"{ad} sahnesinde ayrac var ama arkasinda "
                            f"{len(govde)} govde slaydi")
        elif not ayrac and len(govde) >= 2 and i in konu:
            ihlaller.append(f"{ad} sahnesinde {len(govde)} govde slaydi var "
                            f"ama ayrac yok")
    return ihlaller


def _ayrac_yamasi(scenes: list[dict], anahtar: str = "slides") -> list[str]:
    """SON CARE, CIFT YONLU: eksik ayraci ekler, fazlasini kaldirir.

    Ekleme her iki asamada da AYNI: basliktan bir section sentezlenir.
    Modele geri donulmez -- eklenecek her sey (sahne basligi) zaten elde ve
    section govdesiz cizilebiliyor. Yeni bir uretim problemi degil, silmenin
    simetrigi.

    AYRAC YALNIZCA KONU SAHNELERINE EKLENIR. Giris ve kapanis
    `_konu_araligi` disinda: bir kapak slaydinin onune bolum ayraci koymak,
    kursu kendi girisinden once bolen bir isaret uretirdi.
    """
    duzeltmeler: list[str] = []
    konu = set(_konu_araligi(scenes))
    sinir = _ayrac_siniri(anahtar)
    for i, scene in enumerate(scenes):
        slaytlar = scene.get(anahtar)
        if slaytlar is None:
            continue
        govde = [s for s in slaytlar
                 if not _soru_mu(s)
                 and (s.get("layout") or "content") in GOVDE_DUZENLERI]
        ayraclar = [s for s in slaytlar
                    if not _soru_mu(s)
                    and (s.get("layout") or "content") == "section"]

        if len(govde) >= 2 and not ayraclar and i in konu:
            # KADANS KORUMASI. Ayrac eklemek bir OKUMA slaydi eklemektir ve
            # ardisik okuma serisini uzatir. Olculdu 2026-08-29: onceki
            # sahnesi soruyla bitmeyen bir yapida iki ayrac eklemek seriyi
            # 5'ten 7'ye cikardi -- yani ayrac kurali kadans kuralini
            # boluyordu. `_kadans_uyarisi`'nda duzeltilen celiskinin aynisi.
            #
            # Geri alma olcusu KARSILASTIRMALI, mutlak degil: deck zaten
            # bozuksa ve ekleme onu DAHA KOTU yapmiyorsa ayrac hakki yenmez.
            once = _ardisik_okuma(scenes, anahtar)
            baslik = _sahne_basligi(scene)
            aday = {"kind": "content", "layout": "section", "title": baslik}
            slaytlar.insert(0, aday)
            sonra = _ardisik_okuma(scenes, anahtar)
            if sonra > 3 and sonra > once:
                slaytlar.remove(aday)
                duzeltmeler.append(
                    f"{baslik}: ayrac EKLENMEDI -- ardisik okuma "
                    f"{once}'ten {sonra}'e cikardi (kadans onceliklidir)")
            else:
                duzeltmeler.append(f"{baslik}: ayrac eklendi "
                                   f"({len(govde)} govde slaydi var)")
            continue

        if len(govde) >= sinir or not ayraclar:
            continue
        s = ayraclar[0]
        ad = (s.get("title") or _sahne_basligi(scene))[:40]
        if anahtar == "slides":
            slaytlar.remove(s)
            duzeltmeler.append(f"{ad}: ayrac plandan cikarildi (arkasi bos)")
        else:
            s["layout"] = "statement"
            duzeltmeler.append(f"{ad}: ayrac -> statement (arkasi bos)")
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


# Hangi ihlal ailesi hangi CAREYI ister. Aile basina ayri, cunku careler
# birbiriyle CELISEBILIYOR: kadans "slayt sayisini azaltma" der, ayrac ise
# cozumu tam da bir slayt silmek olabilen bir kusurdur.
CARELER = {
    "kadans": "Slayt sayisini AZALTMA; soruyu dogru yere koyarak coz.",
    "duzen": ("Duzen ADLARINI degistirerek coz: sira tasiyan bir anlatimi "
              "steps, akilda kalmasi gereken tek bir cumleyi statement yap. "
              "Slayt EKLEME; var olanlarin layout degerini degistir."),
    "ayrac": ("Kural: bir sahnede EN AZ IKI govde slaydi varsa basina "
              "section koy, yoksa KOYMA. Fazla ayrac icin iki yoldan birini "
              "sec -- ya section slaydini SIL (slayt sayisini dusurmek BU "
              "IHLAL ICIN SERBESTTIR), ya da yanina ikinci bir govde slaydi "
              "ekle. Eksik ayrac icin sahnenin basina section ekle."),
}


def _kadans_uyarisi(kadans, duzen=(), ayrac=()) -> str:
    """Ihlalleri ADIYLA soyleyen ek talimat -- model kendi planini duzeltsin.

    NE YA"\n"IS yetmez, NE YAPILACAK da yazmali -- ve care AILEYE OZGU olmali.

    Bu metin bir donem butun ihlalleri tek listede topluyor ve TEK bir care
    cumlesi tasiyordu: "Slayt sayisini AZALTMA; soruyu dogru yere koyarak
    coz." O cumle kadans icin dogru, duzen icin ilgisiz, ayrac icin ise
    ACIKCA YA"\n"IS -- arkasi bos bir ayraci gidermenin iki yolundan biri onu
    SILMEK, yani slayt sayisini dusurmek. Modele kendi kendisiyle celisen
    bir talimat veriliyordu.

    Olculdu 2026-08-29 (DOGRULAMA4): dort ayrac ihlali bildirildi, iskelet
    yeniden istendi, IKINCI PLAN AYNI DORT IHLALI TASIDI ve isi deterministik
    yama bitirdi. Bedeli 373 saniye ve bir fazladan model cagrisi. Teshis
    "prompt zayif" degil; prompt CELISKILIYDI.
    """
    bloklar, kullanilan = [], []
    for ad, liste in (("kadans", kadans), ("duzen", duzen), ("ayrac", ayrac)):
        if not liste:
            continue
        bloklar.append("\n".join("- " + i for i in liste))
        kullanilan.append(CARELER[ad])
    if not bloklar:
        return ""
    return ("\n" + "\n" + "ONCEKI ISKELET SU KURALLARI CIGNEDI, DUZELTEREK YENIDEN URET:" + "\n"
            + "\n".join(bloklar)
            + "\n" + "\n" + "NASIL DUZELTILIR:" + "\n"
            + "\n".join("- " + c for c in kullanilan) + "\n")

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
    # UC LISTE AYRI TUTULUR: uyari metni aileye ozgu care yaziyor ve
    # birlestirilmis bir liste hangi carenin hangi ihlale ait oldugunu
    # kaybeder -- celiskinin ilk cikis noktasi tam olarak buydu.
    i_kadans = _kadans_ihlalleri(scenes, options)
    i_duzen = _duzen_ihlalleri(scenes)
    i_ayrac = _ayrac_ihlalleri(scenes)
    ihlaller = i_kadans + i_duzen + i_ayrac
    if ihlaller:
        # "plan ihlali", cunku liste artik UC kural ailesini birden tasiyor:
        # kadans (soru ritmi), duzen (bilesim cesitliligi) ve ayrac. Hepsine
        # "kadans" demek, akisi okuyan kisiyi yanlis kurala gonderir.
        on_progress("plan ihlali: " + "; ".join(ihlaller)
                    + " -- iskelet yeniden isteniyor")
        try:
            aday = (_run_json(outline_istemi
                              + _kadans_uyarisi(i_kadans, i_duzen, i_ayrac),
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
    # AYNI FIKRIN YERLESIM EKSENDEKI KARSILIGI. `soru_gecmisi` hangi TOHUMUN
    # kullanildigini tutar (mobilya), bu hangi VARYANTIN (yerlesim). Ikisi
    # ayri ayri tekrarlayabilir: ayni tohum farkli varyantla bambaska
    # gorunur, farkli tohum ayni varyantla ayni siluete duser.
    varyant_gecmisi: list[str] = []
    variant_log: list[dict] = []
    kurulan_sahneler: list[str] = []
    # YAZILIP KONMAYAN GERI BILDIRIMLER. Sessiz kayip bu projenin
    # bilinen kusuru: model yaziyor, kurucu geciriyor, tohumda
    # konacak yer yok ve hicbir satir bunu soylemiyor.
    geri_bildirim_dusenler: list[str] = []
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
            if spec.get("kind") == "drag":
                try:
                    made = authoring.add_drag_question(
                        pkg, spec.get("prompt", "Dogru kutuya surukle."),
                        spec.get("groups") or {},
                        scene=scene_name,
                        eyebrow=scene.get("title") or scene_name,
                        palette=palette, points=10,
                        feedback=spec.get("feedback"))
                    _d = _geri_bildirim_yazildi_mi(spec, made)
                    if _d:
                        geri_bildirim_dusenler.append(_d)
                    questions += 1
                except StoryError as exc:
                    # Gruplama REDDEDILEBILIR (etiket hucreye sigmazsa) ve
                    # red sessiz gecilmez: sik secme sorusundaki ile ayni
                    # sozlesme -- gerekce raporda durur.
                    refusals.append({
                        "prompt": str(spec.get("prompt", ""))[:60],
                        "choices": sum(len(v) for v in
                                       (spec.get("groups") or {}).values()),
                        "diagnosis": "surukle-birak-kurulamadi",
                        "why": str(exc)[:160], "resolved": False})
                continue
            if spec.get("kind") == "commitment":
                # `accept` GECIRILIR. add_text_question `graded = bool(accept)`
                # diyor: accept yoksa etkilesim cikarilir ve slayt bir taahhut
                # kutusuna doner. Buradan hic gecirilmedigi icin kurucu PUANLI
                # metin sorusu URETEMIYORDU -- yani `freeTextEntryIntr` bicimi
                # kurucunun hicbir yolundan cikmiyordu. Olculdu 2026-09-04:
                # bicim kapsami 5'te 4'te takildi ve sebebi buydu.
                # Verilmedigindeki davranis DEGISMEZ (None -> taahhut).
                made = authoring.add_text_question(
                    pkg, spec.get("prompt", "Tek somut adimini yaz."),
                    spec.get("accept"),
                    scene=scene_name,
                    eyebrow=scene.get("title") or scene_name,
                    palette=palette)
                continue
            if spec.get("kind") == "hotspot":
                made = authoring.add_hotspot_question(
                    pkg, spec.get("prompt", "Gorsel uzerindeki dogru alana tiklayin."),
                    scene=scene_name,
                    eyebrow=scene.get("title") or scene_name,
                    palette=palette, points=10,
                    feedback=spec.get("feedback"))
                _d = _geri_bildirim_yazildi_mi(spec, made)
                if _d:
                    geri_bildirim_dusenler.append(_d)
                questions += 1
                continue
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
                        # ARDISIK IKI SORU AYNI SILUETI TASIMASIN. Tohum
                        # secimindeki `avoid` ile ayni is, farkli eksende:
                        # o mobilyayi degistirir, bu YERLESIMI.
                        avoid_variant=varyant_gecmisi[-1:],
                    )
                    varyant_gecmisi.append(
                        (made.get("adapted") or {}).get("variant") or "")
                    _d = _geri_bildirim_yazildi_mi(spec, made)
                    if _d:
                        geri_bildirim_dusenler.append(_d)
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
            _otomatik_ilerlemeyi_kaldir(pkg, new["new_slide"])
            # REVEAL'IN ETIKETLERI BUTON BANDINA GIDER. Duzen menu ile ayni
            # iskeleti kullaniyor; fark, tiklamanin nereye gittigi. Etiket
            # yoksa duzen bos bir bant olurdu, o yuzden items bos gelirse
            # slayt normal content gibi kurulur.
            reveal_items = (spec.get("items") or []) if duzen == "reveal" else []
            butonlar = ([str(i.get("label") or "")[:40] for i in reveal_items]
                        if reveal_items else spec.get("buttons"))
            laid = compose.compose_slide(
                pkg, new["new_slide"], duzen,
                title=spec.get("title"), eyebrow=spec.get("eyebrow"),
                body=spec.get("body"), bullets=spec.get("bullets"),
                buttons=butonlar, palette=palette,
                index=spec.get("index"), style=look["name"], clear=True,
                identity=seed, avoid_variant=history,
                image_area=bool(istenen), image_style=stil,
            )
            if reveal_items:
                _acilan = _reveal_katmanlari(pkg, new["new_slide"],
                                             reveal_items, laid)
                # SESSIZ DUSME OLMASIN: etiket kuruldu ama katman kurulmadiysa
                # slayt tiklanabilir gorunur ve hicbir sey acmaz.
                if _acilan < len(reveal_items):
                    on_progress(
                        f"reveal ({spec.get('title', '')}): "
                        f"{len(reveal_items)} etiketin {_acilan} tanesi acildi")
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

    # ILERLEME KATMANI: degisken, kosullu tetikleyici, sonuc slaydi, kilit.
    # Slaytlar kuruldu ama kurs hala sayfa cevirmek -- degiskeni ve kosulu
    # olmayan bir kurs PowerPoint'ten ayrilmiyor (gerekce panel/ilerleme.py).
    #
    # BURADA, promote_scenes'ten ONCE: sonuc slaydi kendi sahnesini kuruyor
    # ve o sahne one alinacaklar listesine girmezse devralinan sahneler
    # arasina, kursun arkasina duserdi.
    #
    # Konu sahnelerini IKINCI KEZ TANIMLAMIYORUZ: _konu_araligi yetkili
    # (giris ve kapanis disi), ve ayri bir tanim yazmak kadans kapisiyla
    # celisen bir ikinci gercek uretirdi.
    konu_adlari = [scenes[i].get("name") or f"Bolum{i}"
                   for i in _konu_araligi(scenes)]
    ilerleme_raporu = ilerleme.kur(pkg, konu_adlari, on_progress=on_progress)
    # DALLANMA ILERLEMEDEN SONRA: ikisi de ayni konu sahnesi listesini
    # kullaniyor ve dallanma, ilerlemenin kurdugu sonuc slaydina degil
    # yalnizca soru slaytlarina dokunuyor -- sira aralarinda bagimlilik
    # kurmuyor, ama ikisi de ayni `konu_adlari`ni almali.
    dallanma_raporu = dallanma.kur(
        pkg, konu_adlari,
        # Ogrenciye MAKINE ADI gosterilmez. `_sahne_basligi` zaten bu isi
        # yapiyor (ayrac slaytlari icin yazilmisti) ve ikinci bir turetme
        # yazmak, ayni sahnenin iki yerde iki farkli adla anilmasi olurdu.
        basliklar={(s.get("name") or ""): _sahne_basligi(s) for s in scenes},
        on_progress=on_progress)
    # TEKRAR EKRANI: bayraklari OKUYAN taraf. Ilerleme (sonuc slaydi) ve
    # dallanma (hata bayraklari) ikisi de kurulduktan SONRA calisir --
    # ikisine de ihtiyaci var.
    tekrar_raporu = dallanma.tekrar_ekrani(
        pkg, ilerleme_raporu.get("sonuc_slaydi"),
        dallanma_raporu.get("bayraklar") or [],
        ilerleme_raporu.get("esik") or len(konu_adlari),
        on_progress=on_progress)
    if ilerleme_raporu.get("sonuc_sahnesi"):
        from storyline_mcp.package import STORY_PART
        _story = pkg.parse(STORY_PART)
        _sonuc_sahne = next(
            (s for s in (_story.find("sceneLst") or [])
             if s.get("name") == ilerleme_raporu["sonuc_sahnesi"]), None)
        if _sonuc_sahne is not None:
            kurulan_sahneler.append(_sonuc_sahne.get("g"))

    # A2: kurs, ogrencinin gordugu ilk ekranda BOS olmasin. Kurucu kendi
    # sahnelerini sona ekliyordu ve kurs, sablondan devralinan bos bir slaytla
    # aciliyordu -- uretilen her sey bir alt siradaydi. Hicbir sey silinmez,
    # devralinan sahneler yalnizca arkaya duser (secenekler ve gerekcesi
    # clone.promote_scenes'in belge dizesinde).
    from storyline_mcp.clone import promote_scenes
    siralama = promote_scenes(pkg, kurulan_sahneler)

    # HAREKET, EN SONDA VE KURSUN TAMAMINA. Tek tek compose_slide'a
    # gecirilseydi yalnizca icerik slaytlari kurgulanirdi: soru slaytlari,
    # sonuc slaydi ve ilerleme/dallanma ekranlari baska yollardan kuruluyor
    # ve hepsi hareketsiz kalirdi -- kursun ucte biri.
    #
    # OLCULDU 2026-09-04: uretilen bir kursta (kosul_probu2.story) 360 seklin
    # 360'i start=0 ve dolu animEffect sayisi 0. Yani panelin urettigi her
    # slaytta her nesne ayni anda beliriyordu. Bu blok o kusuru kapatir.
    from storyline_mcp import anim
    hareket = (options.get("motion") or "sakin").strip()
    # Bilinmeyen kurgu BIR KEZ soylenir. Dogrulama donguye birakilsaydi ayni
    # hata her slayt icin bir kez, elli alti satir halinde yazilirdi ve
    # ilerleme akisi okunmaz olurdu.
    if hareket not in anim.PRESETS and hareket != "yok":
        on_progress(f"bilinmeyen hareket kurgusu {hareket!r}; "
                    f"'sakin' kullanildi")
        hareket = "sakin"
    _kurgulanan = 0
    if hareket != "yok":
        for _parca in list(pkg.slide_parts):
            try:
                _kurgulanan += anim.choreograph(pkg, _parca,
                                                preset=hareket)["animated"]
            except StoryError as exc:
                # Tek slayt kurguyu reddederse kurs yine de kaydedilir;
                # sessiz dusmesin diye ilerlemeye yazilir.
                on_progress(f"hareket atlandi ({_parca}): {exc}")
        on_progress(f"✓ Hareket kurgusu '{hareket}': "
                    f"{_kurgulanan} nesne zaman cizgisine dizildi")

    # SAVE WITH GUARANTEED LOGGING
    try:
        report = pkg.save(Path(path), backup=True)
    except Exception as save_err:
        # Log the save failure before re-raising
        try:
            production.record(
                path,
                "build_save_failed",
                {"verified": {"ok": False, "problems": [str(save_err)]}},
                context={"error": str(save_err)[:200], "brief": brief[:100]},
            )
        except Exception:
            pass  # If logging itself fails, don't hide the original error
        raise  # Re-raise the original save error

    # Log successful save
    try:
        production.record(
            path,
            "build",
            report,
            context={
                "brief": brief[:100],
                "slide_budget": budget,
                "scenes": len(scenes),
                "slides_created": created,
                "questions": questions,
            },
        )
    except Exception as log_err:
        # If logging fails, report it but don't fail the build
        on_progress(f"⚠️ Günlük kaydı başarısız: {str(log_err)[:100]}")

    on_progress(
        f"✓ Kurs kaydedildi: {Path(path).name} "
        f"({report['verified'].get('ok')} doğrulama başarılı)"
    )
    # Defter kursla birlikte YENILENIR. Onceki kurulumun istekleri artik baska
    # slaytlari gosteriyor olurdu -- slayt dosyalari yeniden uretildi.
    if medya_istekleri:
        medya.yaz(path, medya_istekleri)
        on_progress(f"{len(medya_istekleri)} medya istegi yazildi -- "
                    "panelde 'Gorsel & Video' sekmesinde bekliyor")
    else:
        medya.temizle(path)

    # OGRETIM OLCUSU, KAYDEDILMIS DOSYA UZERINDE. Bugune kadar raporun her
    # alani BICIMI olcuyordu -- variety, question_looks, verified -- ve
    # "bu kurs PowerPoint mu" sorusuna bakan hicbir sayi yoktu. pedagogy.olc
    # yazilmisti ve uretim yolundan HIC cagrilmiyordu (olculdu 2026-09-04:
    # builder.py'de `pedagogy` gecmiyordu).
    #
    # KAYDEDILEN DOSYA okunuyor, bellekteki pkg degil: ogrencinin aldigi sey
    # diskteki dosya, ve ikisi ayrisirsa rapor yanlis olani anlatir.
    #
    # OLCU KAPI DEGIL. Dusuk cikan bir sayi kursu reddetmiyor; raporda
    # duruyor. Kapiya cevirmek ayri bir karar ve once bu sayinin uretilen
    # kurslarda ne dagilim verdigi gorulmeli.
    try:
        from storyline_mcp import pedagogy
        _olcu = pedagogy.olc(StoryPackage(path))
        ogretim_olcusu = {
            "ardisik_etkilesimsiz_slayt":
                _olcu["ardisik_etkilesimsiz_slayt"]["en_uzun"],
            "etkilesimli_slayt":
                _olcu["ardisik_etkilesimsiz_slayt"]["etkilesimli_slayt"],
            "toplam_slayt":
                _olcu["ardisik_etkilesimsiz_slayt"]["toplam_slayt"],
            "sorusuz_sahneler": _olcu["sorusuz_sahneler"],
            "sonuc_slaydi": bool(_olcu["sonuc_slaydi"]),
            "toplam_tetikleyici":
                _olcu["tetikleyici_cesitliligi"]["toplam_tetikleyici"],
            "ayrik_tetikleyici_cifti":
                _olcu["tetikleyici_cesitliligi"]["ayrik_cift"],
        }
    except Exception as exc:      # olcu kursu dusurmez
        ogretim_olcusu = {"hata": str(exc)[:160]}
        on_progress(f"ogretim olcusu alinamadi: {str(exc)[:100]}")

    return {
        "opens_on": siralama,
        # ILERLEME KATMANI: kac degisken, kac tetikleyici, sonuc slaydi ve
        # kilit kuruldu mu. Atlananlar listesi de icinde -- sessizce kurulmayan
        # bir sonuc slaydi, kursun LMS'e hic puan raporlayamamasi demek.
        "ilerleme": ilerleme_raporu,
        # DALLANMA: yanlis cevap kac sahnede bir yere goturuyor, hangi
        # yolla taninmis, ve NELER ATLANMIS. Atlananlar sayiya indirgenmiyor:
        # "yanlis katman cozulemedi" ile "sahnede soru yok" ayri isler.
        "dallanma": dallanma_raporu,
        # TEKRAR EKRANI: hata bayraklarini OKUYAN taraf. Bayrak kurulup
        # okunmadigi surece elde veri var ama ogrenci icin hicbir sey
        # degismiyor; bu satir o halkanin kapandigini gosteriyor.
        "tekrar_ekrani": tekrar_raporu,
        # OGRETIM: kurs ogrenciye bir sey yaptiriyor mu. Biçim degil davranis.
        "ogretim": ogretim_olcusu,
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
        # YAZILIP KONMAYAN GERI BILDIRIM. Sayi degil GEREKCE: cikti
        # saglam oldugu icin hicbir test bunu yakalamaz. Olculdu
        # 2026-09-04: freeHotSpot tohumunda geri bildirim katmani hic
        # yok ve o sorularda yazarin metni sessizce dusuyordu.
        "feedback_dropped": geri_bildirim_dusenler,
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
        # HAREKET. Sayi ve kurgu birlikte: "sakin" yazip 0 nesne dizilmis bir
        # kurs, hareketsiz bir kurstur ve rapor bunu ayirt edebilmeli.
        "motion": hareket,
        "motion_shapes": _kurgulanan,
        "verified": report["verified"],
        "written": report["written"],
    }
