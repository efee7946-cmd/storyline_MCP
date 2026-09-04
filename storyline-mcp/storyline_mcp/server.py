"""MCP tool surface for Articulate Storyline projects.

Every tool takes the path to a .story file, so calls stay stateless. Writes
never touch the original unless explicitly asked to, and Storyline must be
closed while a project is rewritten -- it holds the package open and will
overwrite anything changed behind its back.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import asdict
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from . import (anim, authoring, compose, jscat, jscheck, logic, media, medya,
               model, pedagogy, settings)
from .clone import clone_slide, create_scene
from .edits import Edit, apply_text_edits
from .package import STORY_PART, StoryPackage, StoryError, lock_state

mcp = MCPServer("storyline")

MAX_RUNS = 400
NAVIGATING_ACTIONS = {
    "jumpToSlide",
    "jumpToScene",
    "showSubSlide",
    "submitInteraction",
    "ReviewQuizSL",
    "jumpToNextSlide",
    "jumpToPrevSlide",
}


def _storyline_running() -> bool:
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Storyline.exe", "/NH"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return "Storyline.exe" in out.stdout
    except Exception:
        return False


def _guard(path: str) -> None:
    """Refuse to write a file another process is holding.

    Scoped to the file, not to Storyline as a whole: Storyline locks only the
    project it has open, so every other course stays safe to edit while the
    app runs. Blocking on the process instead would stop work on files nothing
    is touching.
    """
    state = lock_state(path)
    if state == "free":
        return
    hint = (
        " Bu proje Storyline'da acik gorunuyor; kapatip tekrar deneyin."
        if _storyline_running()
        else " Baska bir uygulama dosyayi tutuyor."
    )
    detail = "salt okunur olarak acilabiliyor" if state == "readonly" else "hic acilamiyor"
    raise StoryError(f"{Path(path).name} kilitli ({detail}).{hint}")


# ------------------------------------------------------------------ reading


@mcp.tool()
def story_info(path: str) -> dict:
    """Kursun kunyesi: sahne/slayt sayilari, degiskenler, quiz ozeti, medya."""
    pkg = StoryPackage(path)
    idx = model.slide_index(pkg)
    variables = model.variables(pkg)
    questions = model.quiz(pkg)
    layouts: dict[str, int] = {}
    for ref in idx.values():
        key = ref.layout_type or "(bos)"
        layouts[key] = layouts.get(key, 0) + 1
    return {
        "file": str(Path(path).resolve()),
        "size_mb": round(Path(path).stat().st_size / 1024 / 1024, 2),
        "story_guid": pkg.parse(STORY_PART).get("id", ""),
        "scene_count": len({r.scene_name for r in idx.values()}),
        "slide_count": len(idx),
        "slides_by_layout": layouts,
        "variable_count": len(variables),
        "user_variables": [v["name"] for v in variables if v["type"] == "user"],
        "question_count": len(questions),
        "media_count": len([n for n in pkg._order if "/media/" in n]),
        "text_run_count": len(model.text_runs(pkg)),
    }


@mcp.tool()
def list_slides(path: str) -> list[dict]:
    """Sahne -> slayt agaci: her slaydin adi, dosyasi ve duzen tipi."""
    return model.scenes(StoryPackage(path))


@mcp.tool()
def extract_text(path: str, slide: str | None = None, offset: int = 0) -> dict:
    """Duzenlenebilir metin parcalarini adresleriyle doker.

    Her kaydin 'addr' alani update_text icin kullanilir. slide verilirse
    ('slide10.xml') yalnizca o slayt taranir. state_guid dolu ise metin bir
    sekil durumunun (hover, selected...) icinde yasiyor demektir.
    """
    runs = model.text_runs(StoryPackage(path), slide)
    window = runs[offset : offset + MAX_RUNS]
    return {
        "total": len(runs),
        "offset": offset,
        "returned": len(window),
        "more": offset + len(window) < len(runs),
        "runs": [asdict(r) for r in window],
    }


@mcp.tool()
def search_text(
    path: str, query: str, regex: bool = False, ignore_case: bool = True
) -> list[dict]:
    """Kurs genelinde metin arar; bulunan her parcayi adresiyle dondurur."""
    runs = model.text_runs(StoryPackage(path))
    if regex:
        pattern = re.compile(query, re.IGNORECASE if ignore_case else 0)
        return [asdict(r) for r in runs if pattern.search(r.text)]
    needle = query.casefold() if ignore_case else query
    return [
        asdict(r)
        for r in runs
        if needle in (r.text.casefold() if ignore_case else r.text)
    ]


@mcp.tool()
def list_variables(path: str) -> list[dict]:
    """Projedeki tum degiskenler (kullanici, yerlesik ve ozellik degiskenleri)."""
    return model.variables(StoryPackage(path))


@mcp.tool()
def list_triggers(path: str, slide: str | None = None) -> list[dict]:
    """Tetikleyiciler: hangi olayda hangi eylem, hedefi ve degiskeni ile."""
    return model.triggers(StoryPackage(path), slide)


@mcp.tool()
def list_quiz(path: str) -> list[dict]:
    """Quiz sorulari: soru koku, secenekler, dogru cevap ve puanlama."""
    return model.quiz(StoryPackage(path))


# ------------------------------------------------------------------ writing


@mcp.tool()
def update_text(
    path: str,
    edits: list[dict],
    output_path: str | None = None,
    in_place: bool = False,
) -> dict:
    """Metin parcalarini adresleyerek gunceller; bicimlendirme korunur.

    edits: [{"addr": "slide10.xml|<sekilGUID>|0|0", "new_text": "yeni metin"}]
    Varsayilan olarak '<ad>.edited.story' yazilir. in_place=True kaynagin
    uzerine yazar ve once .bak yedegi alir. Yazilan paket bastan dogrulanir.
    """
    if not edits:
        raise StoryError("Bos duzenleme listesi.")
    _guard(path)

    pkg = StoryPackage(path)
    result = apply_text_edits(
        pkg, [Edit(addr=e["addr"], new_text=e["new_text"]) for e in edits]
    )

    return {**result, **_write(pkg, path, output_path, in_place)}


# ----------------------------------------------------------------- authoring


def _write(pkg: StoryPackage, path: str, output_path: str | None, in_place: bool) -> dict:
    source = Path(path)
    if in_place:
        target = source
    else:
        target = Path(output_path) if output_path else source.with_suffix(".edited.story")
    return pkg.save(target, backup=True)


def _apply_op(pkg: StoryPackage, op: dict) -> dict:
    kind = op.get("op")
    if kind == "create_scene":
        return create_scene(pkg, op["name"])
    if kind == "duplicate_slide":
        return clone_slide(pkg, op["slide"], scene=op.get("scene"), name=op.get("name"))
    if kind == "add_slide":
        return authoring.add_slide(
            pkg,
            op["template"],
            title=op.get("title"),
            scene=op.get("scene"),
            name=op.get("name"),
        )
    if kind == "add_question":
        return authoring.add_question(
            pkg,
            op.get("template"),
            op["prompt"],
            op["choices"],
            op["correct"],
            scene=op.get("scene"),
            name=op.get("name"),
            points=op.get("points"),
            eyebrow=op.get("eyebrow"),
            feedback=op.get("feedback"),
            style=op.get("style"),
            variant=op.get("variant"),
            avoid_variant=op.get("avoid_variant"),
            palette=op.get("palette") or (
                {k: v for k, v in compose.theme_palette(op["theme"]).items()
                 if not k.startswith("_")} if op.get("theme") else None),
        )
    if kind == "add_drag_question":
        return authoring.add_drag_question(
            pkg,
            op["prompt"],
            op["groups"],
            scene=op.get("scene"),
            name=op.get("name"),
            points=op.get("points"),
            eyebrow=op.get("eyebrow"),
            feedback=op.get("feedback"),
            palette=op.get("palette") or (
                {k: v for k, v in compose.theme_palette(op["theme"]).items()
                 if not k.startswith("_")} if op.get("theme") else None),
        )
    if kind == "add_text_question":
        return authoring.add_text_question(
            pkg,
            op["prompt"],
            op.get("accept"),
            scene=op.get("scene"),
            name=op.get("name"),
            points=op.get("points"),
            eyebrow=op.get("eyebrow"),
            feedback=op.get("feedback"),
            variable=op.get("variable"),
            palette=op.get("palette") or (
                {k: v for k, v in compose.theme_palette(op["theme"]).items()
                 if not k.startswith("_")} if op.get("theme") else None),
        )
    if kind == "add_hotspot_question":
        return authoring.add_hotspot_question(
            pkg,
            op["prompt"],
            scene=op.get("scene"),
            name=op.get("name"),
            points=op.get("points"),
            eyebrow=op.get("eyebrow"),
            feedback=op.get("feedback"),
            palette=op.get("palette") or (
                {k: v for k, v in compose.theme_palette(op["theme"]).items()
                 if not k.startswith("_")} if op.get("theme") else None),
        )
    if kind == "update_text":
        return apply_text_edits(
            pkg, [Edit(addr=e["addr"], new_text=e["new_text"]) for e in op["edits"]]
        )
    if kind == "set_background":
        return authoring.set_background(pkg, op["slide"], op["color"])
    if kind == "add_text_box":
        return authoring.add_text_box(
            pkg, op["slide"], op["text"],
            **{k: op[k] for k in ("x", "y", "w", "h", "color", "size", "bold", "align", "font", "name")
               if k in op},
        )
    if kind == "add_button":
        return authoring.add_button(
            pkg, op["slide"], op["text"],
            **{k: op[k] for k in ("x", "y", "w", "h", "target_slide", "target_scene",
                                  "closes_layer", "fill", "color", "size") if k in op},
        )
    if kind == "add_shape":
        return authoring.add_decoration(
            pkg, op["slide"], op.get("kind", "roundRect"),
            **{k: op[k] for k in ("x", "y", "w", "h", "fill", "text", "color",
                                  "size", "align", "name") if k in op},
        )
    if kind == "set_theme_colors":
        return settings.set_theme_colors(pkg, op["colors"], master=op.get("master"))
    if kind == "set_theme_font":
        return settings.set_theme_font(pkg, op["font"], master=op.get("master"))
    if kind == "add_results_slide":
        return authoring.add_results_slide(
            pkg, scene=op.get("scene"), name=op.get("name", "Sonuclar")
        )
    if kind == "restyle_text":
        return authoring.restyle_slide_text(
            pkg, op["slide"],
            **{k: op[k] for k in ("color", "size", "bold", "font", "shape") if k in op},
        )
    if kind == "set_slide_properties":
        return settings.set_slide_properties(
            pkg, op["slide"],
            **{k: op[k] for k in ("advance_by_user", "hide_from_menu", "show_in_review",
                                  "count_in_slide_numbers", "prev", "next", "submit",
                                  "menu", "seek", "replay") if k in op},
        )
    if kind == "set_story_size":
        return settings.set_story_size(pkg, op["width"], op["height"])
    if kind == "set_player_color":
        return settings.set_player_color(
            pkg, op["name"], op["color"], alpha=op.get("alpha", 100)
        )
    if kind == "set_button_state":
        return authoring.set_button_state(
            pkg, op["slide"], op["button"], op["state"],
            fill=op.get("fill"), color=op.get("color"),
        )
    if kind == "add_layer":
        return authoring.add_layer(
            pkg, op["slide"], op["name"],
            text=op.get("text"), open_from=op.get("open_from"),
        )
    if kind == "add_image":
        return media.add_image(
            pkg, op["slide"], op["image"],
            **{k: op[k] for k in ("x", "y", "w", "h", "fit", "behind", "name")
               if k in op},
        )
    if kind == "add_video":
        return media.add_video(
            pkg, op["slide"], op["video"],
            **{k: op[k] for k in ("x", "y", "w", "h", "name") if k in op},
        )
    if kind == "compose_slide":
        return compose.compose_slide(
            pkg, op["slide"], op.get("layout", "content"),
            **{k: op[k] for k in ("title", "eyebrow", "body", "bullets", "buttons",
                                  "palette", "index", "image_area", "image_style",
                                  "style", "clear", "variant", "avoid_variant",
                                  "theme")
               if k in op},
        )
    # Degisken ve tetikleyici bu listede YOKTU, ve yokluklari sessizdi:
    # `logic.py` ikisini de yaziyor, `add_trigger`/`add_variable` MCP araci
    # olarak sunuluyor, ama build_course ve panel kuyrugu onlari hic
    # cagirmiyordu. Yani dallanma katmani tek tek cagrilarla ulasilabilir,
    # kurs kurma yolundan ULASILAMAZ durumdaydi (K8: sinandi != baglandi).
    if kind == "add_variable":
        return logic.add_variable(
            pkg, op["name"], op.get("kind", "num"), op.get("default")
        )
    if kind == "add_trigger":
        return logic.add_trigger(
            pkg, op["slide"], op["action"],
            **{k: op[k] for k in ("shape", "event", "variable", "operation",
                                  "value", "target_slide", "target_scene",
                                  "layer", "state", "javascript", "watch",
                                  "drop_targets", "state_name", "conditions")
               if k in op},
        )
    if kind == "add_js_capability":
        return jscat.uygula(
            pkg, op["slide"], op["capability"],
            params=op.get("params"), event=op.get("event"),
            shape=op.get("shape"),
        )
    raise StoryError(f"Bilinmeyen islem: {kind!r}")


@mcp.tool()
def list_templates(path: str) -> list[dict]:
    """Klonlanabilir slaytlar. Soru slaytlarinda 'choice_count' zorunludur:
    yeni soru, sablonun secenek sayisiyla ayni sayida secenek almalidir."""
    return authoring.list_templates(StoryPackage(path))


@mcp.tool()
def duplicate_slide(
    path: str,
    slide: str,
    scene: str | None = None,
    name: str | None = None,
    output_path: str | None = None,
    in_place: bool = False,
) -> dict:
    """Bir slaydi kopyalar: tum ic GUID'ler yenilenir, slayt sahneye ve menuye
    kaydedilir. Icerigi sonra update_text ile degistirilebilir."""
    _guard(path)
    pkg = StoryPackage(path)
    result = clone_slide(pkg, slide, scene=scene, name=name)
    return {**result, **_write(pkg, path, output_path, in_place)}


@mcp.tool()
def add_slide(
    path: str,
    template: str,
    title: str | None = None,
    scene: str | None = None,
    name: str | None = None,
    output_path: str | None = None,
    in_place: bool = False,
) -> dict:
    """Icerik slaydi ekler (bir sablonu klonlayarak) ve basligini yazar.

    Donen 'editable_text' listesi, govde metnini update_text ile doldurmak
    icin gereken adresleri icerir."""
    _guard(path)
    pkg = StoryPackage(path)
    result = authoring.add_slide(pkg, template, title=title, scene=scene, name=name)
    return {**result, **_write(pkg, path, output_path, in_place)}


@mcp.tool()
def question_formats(path: str) -> list[dict]:
    """Bu dosyada uretilebilen soru bicimleri ve secenek sayilari.

    add_question'dan ONCE buraya bakin. 'project' kaynakli olanlar dosyanin
    kendi soru slaytlaridir; 'bundled' olanlar araca gomulu orneklerdir ve
    dosyada hic soru slaydi olmasa bile kullanilabilir."""
    return authoring.available_question_shapes(StoryPackage(path))


@mcp.tool()
def add_question(
    path: str,
    prompt: str,
    choices: list[str],
    correct: list[int],
    template: str | None = None,
    scene: str | None = None,
    name: str | None = None,
    points: int | None = None,
    eyebrow: str | None = None,
    theme: str | None = None,
    palette: dict | None = None,
    feedback: dict | None = None,
    style: str | None = None,
    variant: str | None = None,
    avoid_variant: list[str] | None = None,
    output_path: str | None = None,
    in_place: bool = False,
) -> dict:
    """Puanli quiz sorusu ekler: soru koku, secenekler ve dogru cevap(lar).

    template VERMEYIN. Bos birakildiginda secenek sayisina uyan bir kaynak
    kendiliginden secilir: once dosyanin kendi soru slaytlari, yoksa araca
    gomulu ornekler. Dosyada hic soru slaydi olmamasi engel degildir.

    KURSA UYDURMA -- gomulu ornek kullanildiginda ONEMLI. Gomulu soru
    slaytlari gercek bir kurstan alindi ve o kursun izlerini tasiyor: baska
    bir bolumun adi, baska bir kursun degiskeni, pakete kurulmamis bir gorsel
    ve kendi zemin rengi. eyebrow ve theme (ya da palette) verildiginde bu
    izler temizlenir, ust etikete SIZIN bolum adiniz yazilir ve slayt kursun
    temasina boyanir. VERILMEZSE izler slaytta kalir ve ogrenci yanlis bolum
    adini gorur.
      eyebrow: bu sorunun ait oldugu bolumun adi
      theme:   compose_slide ile AYNI temayi verin
      feedback: {"correct": "...", "incorrect": "..."} -- dogru ve yanlis
        cevap katmanlarinda ogrencinin okuyacagi aciklama. Verilmezse notr
        bir varsayilan yazilir; tohumun kendi metni hicbir durumda kalmaz.

    DUZEN CESITLILIGI. Soru slaydinin iskeleti artik tek degil: variant
    ("tam", "ortalanmis", "girintili", "sag") kokun ve sik yiginin slaydin
    neresinde durdugunu degistirir. VERMEYIN -- bos birakildiginda soru
    kokunden turer ve ayni kurs iki kez uretildiginde ayni sonucu verir.
    avoid_variant, ardisik iki sorunun ayni siluetle cikmasini engeller;
    bir onceki sorunun varyantini gecin.

    style (rail/corner/band/plain) zemin ve vurgu isaretini secer ve KURS
    ICINDE SABIT olmalidir: verilmezse dosya adindan turer, yani ayni
    kursun butun sorulari ayni uslubu giyer.

    Secenek sayisi serbest degildir; question_formats ile kullanilabilir
    sayilari gorun ve sorulari ona gore yazin.
    correct: dogru seceneklerin sifir tabanli indisleri."""
    _guard(path)
    pkg = StoryPackage(path)
    result = authoring.add_question(
        pkg, template, prompt, choices, correct, scene=scene, name=name,
        points=points, eyebrow=eyebrow, feedback=feedback,
        style=style, variant=variant, avoid_variant=avoid_variant,
        palette=palette or (
            {k: v for k, v in compose.theme_palette(theme).items()
             if not k.startswith("_")} if theme else None),
    )
    return {**result, **_write(pkg, path, output_path, in_place)}


@mcp.tool()
def add_drag_question(
    path: str,
    prompt: str,
    groups: dict,
    scene: str | None = None,
    name: str | None = None,
    points: int | None = None,
    eyebrow: str | None = None,
    theme: str | None = None,
    palette: dict | None = None,
    feedback: dict | None = None,
    output_path: str | None = None,
    in_place: bool = False,
) -> dict:
    """Gruplama sorusu ekler: ogeler yukarida, kutular asagida, ogrenci surukler.

    groups, KUTU ADI -> O KUTUYA AIT OGELER esleşmesidir; dogru cevap bu
    esleşmenin ta kendisidir, ayri bir 'correct' listesi YOKTUR.

        {"Gizli": ["Musteri fiyat teklifi", "Calisan bordrosu"],
         "Halka acik": ["Basin bulteni", "Is ilani"]}

    add_question'dan FARKI, ve niye ayri bir arac: sikki secmek tek bir
    karardir, gruplamak her oge icin bir karardir. Tanim/siniflandirma
    anlatan bir bolum "asagidakilerden hangisi" ile yoklandiginda ezber
    olcer; ayni bolum gruplama ile yoklandiginda AYRIMI olcer.

    Kutu sayisi sutun sayisini belirler (tavan 4); oge sayisi serbesttir --
    tohum dokuz oge tasir, fazlasi kopyalanir, azi silinir. Etiketler
    hucreye sigmazsa soru kurulmaz ve gerekce doner: her oge etiketi tek
    satirlik bir ad olsun, cumle degil.

    eyebrow ve theme, add_question'daki ile ayni islevi gorur ve AYNI
    sebeple onemlidir: tohum gercek bir kurstan alindi.
    """
    _guard(path)
    pkg = StoryPackage(path)
    result = authoring.add_drag_question(
        pkg, prompt, groups, scene=scene, name=name, points=points,
        eyebrow=eyebrow, feedback=feedback,
        palette=palette or (
            {k: v for k, v in compose.theme_palette(theme).items()
             if not k.startswith("_")} if theme else None),
    )
    return {**result, **_write(pkg, path, output_path, in_place)}


@mcp.tool()
def add_text_question(
    path: str,
    prompt: str,
    accept: list[str] | None = None,
    scene: str | None = None,
    name: str | None = None,
    points: int | None = None,
    eyebrow: str | None = None,
    theme: str | None = None,
    palette: dict | None = None,
    feedback: dict | None = None,
    variable: str | None = None,
    output_path: str | None = None,
    in_place: bool = False,
) -> dict:
    """Ogrencinin YAZDIGI slayt. Iki kipi var ve ayrimi `accept` yapar.

    TAAHHUT KIPI (accept VERILMEZ) -- onerilen kullanim. Puanlama yoktur,
    dogru cevap yoktur; geriye bir soru koku ve bir yazma kutusu kalir.
    Yazilan sey bir degiskene gider (adi donuste bildirilir), yani sonraki
    slaytlarda %DegiskenAdi% ile geri gosterilebilir.

        "Bu haftaki tek somut adimini yaz: hangi hesabinda iki adimli
         dogrulamayi acacaksin?"

    Kapanis slaydinin aforizma olmamasi kuralinin uygulanabilir hali budur:
    ogrenci bir sey SECMEZ, bir sey YAZAR.

    PUANLI KIP (accept verilir) -- kabul edilen cevaplarin listesi. Eslesme
    metnin kendisiyle yapilir, yani yalnizca tek kelimelik ve yazimi kesin
    cevaplarda ise yarar ("bildir", "raporla").

      UYARI, VE OLCULDU: gomulu tohumda GERI BILDIRIM KATMANI YOK
      (sldLayerLst hic yok). Puanli kipte ogrenci cevabini verdikten sonra
      okuyacagi bir aciklama YAZILAMAZ; oynaticinin kendi varsayilani ne
      gosteriyorsa onu gorur. Ogretim kurali "HER soruya feedback yaz"
      diyor ve bu kip onu KARSILAMIYOR. Aciklama gerektiren bir olcum icin
      add_question ya da add_drag_question kullanin.
    """
    _guard(path)
    pkg = StoryPackage(path)
    result = authoring.add_text_question(
        pkg, prompt, accept, scene=scene, name=name, points=points,
        eyebrow=eyebrow, feedback=feedback, variable=variable,
        palette=palette or (
            {k: v for k, v in compose.theme_palette(theme).items()
             if not k.startswith("_")} if theme else None),
    )
    return {**result, **_write(pkg, path, output_path, in_place)}


@mcp.tool()
def add_hotspot_question(
    path: str,
    prompt: str,
    scene: str | None = None,
    name: str | None = None,
    points: int | None = None,
    eyebrow: str | None = None,
    theme: str | None = None,
    palette: dict | None = None,
    feedback: dict | None = None,
    output_path: str | None = None,
    in_place: bool = False,
) -> dict:
    """Sıcak nokta (Hotspot) sorusu ekler: ekrandaki doğru alana tıklama sorusu."""
    _guard(path)
    pkg = StoryPackage(path)
    result = authoring.add_hotspot_question(
        pkg, prompt, scene=scene, name=name, points=points,
        eyebrow=eyebrow, feedback=feedback,
        palette=palette or (
            {k: v for k, v in compose.theme_palette(theme).items()
             if not k.startswith("_")} if theme else None),
    )
    return {**result, **_write(pkg, path, output_path, in_place)}


@mcp.tool()
def add_scene(
    path: str,
    name: str,
    output_path: str | None = None,
    in_place: bool = False,
) -> dict:
    """Bos bir sahne (bolum) ekler ve menuye kaydeder."""
    _guard(path)
    pkg = StoryPackage(path)
    result = create_scene(pkg, name)
    return {**result, **_write(pkg, path, output_path, in_place)}


@mcp.tool()
def set_background(
    path: str,
    slide: str,
    color: str,
    output_path: str | None = None,
    in_place: bool = False,
) -> dict:
    """Slaydin arka planini duz renkle kaplar (orn. '#0A2240').

    Slaytlar arka planlarini duzenden miras aldigi icin, en arkaya tam sayfa
    renkli bir dikdortgen konur."""
    _guard(path)
    pkg = StoryPackage(path)
    result = authoring.set_background(pkg, slide, color)
    return {**result, **_write(pkg, path, output_path, in_place)}


@mcp.tool()
def add_text_box(
    path: str,
    slide: str,
    text: str,
    x: float = 10,
    y: float = 40,
    w: float = 80,
    h: float | None = None,
    color: str | None = None,
    size: float | None = None,
    bold: bool | None = None,
    align: str = "c",
    font: str | None = None,
    name: str | None = None,
    avoid_overlap: bool = True,
    output_path: str | None = None,
    in_place: bool = False,
) -> dict:
    """Slayda metin kutusu ekler.

    x/y/w slaydin YUZDESIdir (0-100). h VERMEYIN: kutu metne gore boyutlanir,
    boylece uzun paragraf sabit bir seride sikisip tasmaz.
    Varsayilan olarak mevcut sekillerle cakismaz; donen 'box_percent' gercek
    konumu, 'placed_without_overlap' yerlestirmenin temiz olup olmadigini soyler."""
    _guard(path)
    pkg = StoryPackage(path)
    result = authoring.add_text_box(
        pkg, slide, text, x=x, y=y, w=w, h=h, color=color, size=size, bold=bold,
        align=align, font=font, name=name, avoid_overlap=avoid_overlap,
    )
    return {**result, **_write(pkg, path, output_path, in_place)}


@mcp.tool()
def compose_slide(
    path: str,
    slide: str,
    layout: str = "content",
    title: str | None = None,
    eyebrow: str | None = None,
    body: str | None = None,
    bullets: list[str] | None = None,
    buttons: list[str] | None = None,
    palette: dict | None = None,
    brand: str | None = None,
    index: str | None = None,
    image_area: bool = False,
    image_style: str = "panel",
    style: str | None = None,
    clear: bool = True,
    variant: str | None = None,
    avoid_variant: str | None = None,
    theme: str | None = None,
    motion: str | None = None,
    output_path: str | None = None,
    in_place: bool = False,
) -> dict:
    """Bir slaydi tek seferde, oranlari tutarli bicimde kurar.

    Tercih edilen yol budur: parca parca kurmak yerine burayi kullanin.
    Kenar boslugu, punto olcegi, dikey ritim ve vurgu araca gomulu. Her
    duzenin KENDI iskeleti vardir; ayni sayfayi tekrar etmezler.

    layout:
      cover     - kapak: alta yaslanmis baslik, kose blogu
      section   - bolum ayraci: buyuk index, ortalanmis, bos
      content   - iki sutun; image_area=true gorsel alani ayirir
      bullets   - maddeler KART olarak, 4+ ise iki sutun
      steps     - numarali sira (adim adim anlatim)
      statement - tek buyuk cumle, akilda kalmasi icin
      menu      - secim butonlari one cikar

    index: section/steps duzeninde gosterilen numara ("02" gibi)
    image_area: gorsel icin yer ayirir (cover ve content duzenlerinde). Donen
      'image_area' alani add_image icin hazir x/y/w/h degerlerini verir.
    image_style: o yer nasil bicimlenir --
      panel - sag sutunda yuvarlak kartli panel (guvenli varsayilan)
      bleed - sag kenardan tasan tam boy blok, yazi solda (asimetrik)
      hero  - tum slayt gorsel; uzerine yaziyi okunur kilan ortu konur.
              Donen alanda behind=true gelir; add_image'i behind=true ile
              cagirin, yoksa gorsel yazinin ustune biner.
    Kapakta hero, ic slaytlarda bleed kullanin; hepsinde ayni yerlesim
    kurs geneline tekduze bir gorunum verir.

    RENK: theme="gece|kagit|komur|orman|sis|murdum" verin. Her temanin ZEMINI
    ayri secilmistir ve zemin slayt alaninin %98'idir -- kurslarin birbirine
    benzemesini bitiren sey budur. Hepsi WCAG AA esiginden gecirilmistir.
    BIR KURSTAKI TUM SLAYTLARDA AYNI theme'i kullanin.
    brand="#RRGGBB" yalnizca tema listesinde karsiligi olmayan bir marka rengi
    varsa kullanilir; zemini markadan hesaplar ve marka koyuysa yaziyi
    okunmaz hale getirebilir. palette ikisini de ezer.

    STIL: style, vurgunun nereye konacagini belirler ve kursu digerlerinden
    ayirir: rail (sol seritt), corner (ust kose blogu), band (alt serit),
    plain (isaretsiz). Verilmezse baslikdan turetilir; ayni kurs her zaman
    ayni stili alir. BIR KURSTAKI TUM SLAYTLARDA AYNI style'i kullanin.

    VARYANT: style vurgunun rengini oynatir, iskeleti degil. variant iskeleti
    oynatir -- metin sutunu nerede baslar, basligin kendi seridi var mi,
    maddeler basligin ustunde mi altinda mi. content duzeninde alti varyant
    var: sol-panel, genis-olcu, sag-metin, ortalanmis, ust-serit, alt-baslik.

    ARDISIK TEKRAR: avoid_variant'a BIR ONCEKI SLAYDIN varyantini verin (donen
    'variant' alanindan). Iki komsu slayt ayni varyanti tasidiginda ayni
    siluete sahip olur ve kurs "sablon iki kez uygulanmis" gibi okunur; bunu
    engelleyen tek sey budur. Duzenin tek varyanti varsa yasak cignenir ve
    sonuc variant_repeated=true ile doner -- sessizce degil.
    style'i sabit tutun, variant'i her slaytta degistirin.

    HAREKET: motion, slaydin AcILIS kurgusudur -- nesneler zaman cizgisine
    kademeli dizilir ve giris animasyonu alir. Verilmezse slayt hareketsizdir:
    her nesne ayni anda, aninda belirir.
      sakin   - her sey solarak girer, 180 ms araliklarla (guvenli varsayilan)
      anlatim - susleme silinerek, blok yerine kayarak, yazi solarak
      vurgulu - yazi da kayar; yogun slaytta cok olur
    Kart ve adim yiginlari TEK VURUS sayilir: bes kart, on bes parca degil
    bes adim halinde acilir. BIR KURSTAKI TUM SLAYTLARDA AYNI motion'i
    kullanin. Sonradan degistirmek/kaldirmak icin animate_slide."""
    _guard(path)
    pkg = StoryPackage(path)
    if palette is None and brand:
        palette = compose.derive_palette(brand)
    result = compose.compose_slide(
        pkg, slide, layout, title=title, eyebrow=eyebrow, body=body,
        bullets=bullets, buttons=buttons, palette=palette,
        index=index, image_area=image_area, image_style=image_style,
        style=style, clear=clear, variant=variant, avoid_variant=avoid_variant,
        theme=theme, motion=motion,
    )
    return {**result, **_write(pkg, path, output_path, in_place)}


@mcp.tool()
def animate_slide(
    path: str,
    slide: str | None = None,
    preset: str = "sakin",
    step_ms: int | None = None,
    start_ms: int = 0,
    include_interactions: bool = False,
    output_path: str | None = None,
    in_place: bool = False,
) -> dict:
    """Slaydi zaman cizgisine dizer: kademeli giris + animasyon.

    slide verilmezse KURSUN TAMAMI kurgulanir -- bir kursu tek cagriyla
    hareketlendirmenin yolu budur.

    Nesneler z-sirasinda, yani yerlestirildikleri sirada girer. Tekrar eden
    desenler (kart yigini, numarali adimlar) TEK VURUS sayilir: bes kart, on
    bes parca degil bes adim halinde acilir. Ayni adin tekrari yigin sayilir,
    grup degil -- bes ozdes kart bes ayri vurus.

    KATMANLAR DA KURGULANIR (sldLayer ve feedBackLayer), her biri KENDI
    sifirindan. Katman gosterildigi anda acilir; slaydin zaman cizgisine
    gore geciktirmek, ogrenciyi actigi pop-up'ta bos ekrana baktirirdi.
    include_layers=false yalnizca slayt kokunu kurgular.

    preset:
      sakin   - her sey solarak, 180 ms araliklarla. Hicbir nesne yerinden
                oynamaz; kurs geneline uygulanabilecek en guvenli kurgu.
      anlatim - susleme silinerek (wipe), blok asagidan kayarak, yazi solarak
      vurgulu - yazi da kayar; yogun slaytta cok olur
    step_ms araligi ezer. start_ms kurgunun tamamini geciktirir.

    ATLANANLAR: zemin ("Arka Plan"), video, ve SORU GOVDELERI. Sorunun
    animEffect yuvasi soru kapsayicisindadir ve oraya yazmanin siklara ne
    yaptigi olculmedi -- yanlis animasyonlanan bir soru cevaplanamayan bir
    sorudur. include_interactions=true bu korumayi kaldirir.

    YOK -- ve hepsinin sebebi ayni: OLCULMEDI, tahminle yazilmiyor.
      cikis animasyonu  havuzdaki 214 slayt seklinin 214'u untilEnd="true",
                        yani hicbiri zaman cizgisini erken terk etmiyor.
                        Cikis ancak nesne cizgiden CIKINCA oynar; boyle bir
                        nesneye cikis yazmak hic oynamayan efekt yazmaktir.
      hareket yolu      havuzda VAR (shapePath, shapeG ile tasidigi sekli
                        gosteriyor) ama kanit dar: 15 ornek, tek slayttan,
                        hepsi dairesel. Cizgi/egri/serbest yol olculmedi.
      slayt gecisi      havuzda yalnizca <none/> var.

    Geri almak icin preset="yok" -- katmanlar dahil."""
    _guard(path)
    pkg = StoryPackage(path)
    targets = [pkg.slide_part_for(slide)] if slide else list(pkg.slide_parts)
    slides = []
    for part in targets:
        if preset == "yok":
            slides.append(anim.clear(pkg, part))
        else:
            slides.append(anim.choreograph(
                pkg, part, preset=preset, step_ms=step_ms, start_ms=start_ms,
                include_interactions=include_interactions))
    return {
        "preset": preset,
        "slide_count": len(slides),
        "animated": sum(s.get("animated", 0) for s in slides),
        "cleared": sum(s.get("cleared", 0) for s in slides),
        "slides": slides,
        **_write(pkg, path, output_path, in_place),
    }


@mcp.tool()
def list_animations(path: str, slide: str) -> list[dict]:
    """Slayttaki her seklin zamanlamasi ve animasyonu -- oldugu gibi.

    start_ms/dur_ms zaman cizgisindeki yeri, entrance/exit yazili efekti
    verir. Hicbir sey yazilmamissa her sekil start=0 ve entrance=null gelir;
    kursun hareketsiz oldugunu boyle gorursunuz."""
    return anim.describe(StoryPackage(path), slide)


@mcp.tool()
def animation_effects() -> dict:
    """Yazilabilen efektler ve kurgular -- OLCULEN sozluk, tahmin degil.

    Her deger bagis havuzundaki gercek Storyline dosyalarindan sayildi. Burada
    olmayan bir efekt "desteklenmiyor" demek degil, "nasil yazildigi henuz
    olculmedi" demektir."""
    return {
        "effects": {verb: sorted(attrs) for verb, attrs in anim.EFFECTS.items()},
        "directions": list(anim.DIRECTIONS),
        "direction_note": "yon yalnizca fly icin olculdu",
        "easings": sorted(anim.EASINGS),
        "presets": {name: {"step_ms": plan["step"], "seconds": plan["seconds"],
                           "easing": plan["easing"], "by_role": plan["by_role"]}
                    for name, plan in anim.PRESETS.items()},
        "preset_note": "animate_slide ayrica preset='yok' alir: kurguyu ve "
                       "kademelenmeyi birlikte geri alir",
        "layer_tags": list(anim.LAYER_TAGS),
        "missing": {
            "cikis_animasyonu":
                "havuzdaki 214 slayt seklinin 214'u untilEnd=true; nesne "
                "zaman cizgisini hic terk etmiyor, yani cikis oynamaz. "
                "Oynamasi icin gereken untilEnd=false + sonlu dur olculmedi.",
            "hareket_yolu":
                "havuzda VAR: <shapePath shapeG=... aniDur=PT0.1S "
                "shapeType=cir easingType=cubic>. Ama 15 ornek, tek bagisin "
                "tek slaydindan ve hepsi dairesel; cizgi/egri/serbest yol "
                "olculmedi. Henuz yazilmiyor.",
            "slayt_gecisi":
                "havuzda yalnizca <trans><none/></trans> var; gercek bir "
                "gecis tipi hic gecmiyor.",
        },
        "missing_note": "hicbiri tahminle yazilmaz; once Storyline'da prob "
                        "uretilip tools/paket_farki.py ile farki alinmali",
    }


@mcp.tool()
def add_image(
    path: str,
    slide: str,
    image: str,
    x: float = 10,
    y: float = 30,
    w: float = 40,
    h: float | None = None,
    fit: str = "contain",
    behind: bool = False,
    name: str | None = None,
    output_path: str | None = None,
    in_place: bool = False,
) -> dict:
    """Diskteki bir gorseli slayda yerlestirir (png / jpg / gif).

    x/y/w slaydin YUZDESIdir; yukseklik gorselin en-boy oranindan hesaplanir ve
    slayta sigacak sekilde kucultulur. Gorsel pakete kopyalanir, story.xml'e
    medya kaydi eklenir ve slayda bir <pic> sekli konur.

    behind=true gorseli yazinin ALTINA koyar (zeminin ustunde kalir). Tam
    kanamali kapak icin sarttir: compose_slide'i image_style="hero" ile
    cagirdiysaniz donen alanda behind=true gelir, aynen iletin.

    fit, gorselin orani alanla tutmadiginda ne olacagini soyler:
      contain (varsayilan) alana sigar, kenarda bosluk kalabilir
      cover   alani doldurur, fazlalik ORTADAN KIRPILIR -- hero ve bleed
              alanlarinda bunu verin
      stretch alana gerilir ve ORAN BOZULUR; ancak acikca istenirse."""
    _guard(path)
    pkg = StoryPackage(path)
    result = media.add_image(pkg, slide, image, x=x, y=y, w=w, h=h,
                             fit=fit, behind=behind, name=name)
    return {**result, **_write(pkg, path, output_path, in_place)}


@mcp.tool()
def add_video(
    path: str,
    slide: str,
    video: str,
    x: float = 10,
    y: float = 25,
    w: float = 45,
    h: float | None = None,
    name: str | None = None,
    output_path: str | None = None,
    in_place: bool = False,
) -> dict:
    """Diskteki bir videoyu slayda yerlestirir (mp4 / m4v).

    x/y/w/h slaydin YUZDESIdir ve h verildiginde bir ALAN tarif eder: video o
    alanin icine kendi oranini koruyarak yerlesir ve ortalanir. compose_slide'i
    image_area=true ile cagirdiysaniz donen alani aynen buraya gecin.

    Sure, kare hizi ve piksel boyu MP4'un icinden okunur; zaman cizelgesi filmin
    tam boyuna ayarlanir. Video icin bir poster (thumbG) da uretilip kaydedilir.

    Dosya YOKSA burayi cagirmayin: request_media ile isteyin, kullanici panelin
    "Gorsel & Video" sekmesinden versin."""
    _guard(path)
    pkg = StoryPackage(path)
    result = media.add_video(pkg, slide, video, x=x, y=y, w=w, h=h, name=name)
    return {**result, **_write(pkg, path, output_path, in_place)}


@mcp.tool()
def request_media(
    path: str,
    slide: str,
    kind: str,
    brief: str,
    seconds: int | None = None,
    area: dict | None = None,
    style: str = "panel",
) -> dict:
    """Elinizde OLMAYAN bir gorsel/video icin SIPARIS birakir.

    Kurs uretirken bir slaydin gorsel ya da video istedigi cok olur ve dosya
    sizde olmaz. Uc secenegin ikisi kotu: "yapamiyorum" demek isi bitirir,
    sessizce vazgecmek slaydi eksik birakir. Ucuncusu bu: istek
    `<kurs>.medya.json` defterine yazilir, panelin "Gorsel & Video" sekmesinde
    kullaniciya gorunur, dosyayi o verdiginde panel tam olarak buraya koyar.

    kind: "gorsel" ya da "video". brief bir SIPARIStir, etiket degil: cerceve
    ne gostersin, kim/ne var, hangi an. "guvenlik gorseli" degil, "telefon
    ekraninda dogrulama bildirimi, parmak onay tusunun uzerinde".

    area: slaytta yer ayirdiysaniz compose_slide'in donusundeki image_area'yi
    aynen verin (style ile birlikte). Vermezseniz panel sag sutunda varsayilan
    bir kart kullanir -- o yuzden once slide_layout ile bos alana bakin.

    Bu cagri kursu DEGISTIRMEZ, yalnizca defteri yazar; dosya kilitliyken de
    calisir."""
    pkg = StoryPackage(path)
    ref = model.slide_index(pkg).get(pkg.slide_part_for(slide))
    istekler = medya.oku(path)
    kayit = medya.istek(
        pkg.slide_part_for(slide).rsplit("/", 1)[1],
        ref.scene_name if ref else "",
        ref.name if ref else slide,
        "video" if str(kind).lower().startswith("v") else "gorsel",
        brief, saniye=seconds, alan=area, stil=style,
        sira=len(istekler) + 1,
        sahne_px=medya.slayt_olcusu(pkg, slide),
    )
    istekler.append(kayit)
    defter = medya.yaz(path, istekler)
    return {"istek": kayit, "bekleyen": medya.bekleyen_sayisi(istekler),
            "defter": str(defter),
            "not": "Kullanici panelin 'Gorsel & Video' sekmesinden dosyayi "
                   "verdiginde slayta kendisi yerlesecek."}


@mcp.tool()
def slide_layout(path: str, slide: str) -> dict:
    """Slayttaki sekillerin yerlesimi (yuzde olarak) ve bos alanlar.

    Yeni bir sekil koymadan once burayi okuyun: neyin nerede oldugunu
    bilmeden verilen koordinatlar ust uste biner."""
    from . import shapes as _shapes

    pkg = StoryPackage(path)
    root = pkg.parse(pkg.slide_part_for(slide))
    width, height = _shapes.slide_size(root)
    items = []
    shape_list = root.find("shapeLst")
    for shape in list(shape_list) if shape_list is not None else []:
        rect = _shapes.shape_rect(shape)
        if rect is None:
            continue
        l, t, r, b = rect
        items.append({
            "type": shape.tag,
            "name": shape.get("name", ""),
            "text": model.shape_text(root, shape.get("g", ""))[:50],
            "x": round(l / width * 100, 1), "y": round(t / height * 100, 1),
            "w": round((r - l) / width * 100, 1), "h": round((b - t) / height * 100, 1),
        })
    used = [(i["y"], i["y"] + i["h"]) for i in items if i["w"] < 95 or i["h"] < 95]
    free = []
    cursor = 0.0
    for top, bottom in sorted(used):
        if top - cursor > 8:
            free.append({"y": round(cursor, 1), "h": round(top - cursor, 1)})
        cursor = max(cursor, bottom)
    if 100 - cursor > 8:
        free.append({"y": round(cursor, 1), "h": round(100 - cursor, 1)})
    return {"slide": slide, "slide_size": [int(width), int(height)],
            "shapes": items, "free_bands": free}


@mcp.tool()
def add_button(
    path: str,
    slide: str,
    text: str,
    x: float = 74,
    y: float = 84,
    w: float = 20,
    h: float = 10,
    target_slide: str | None = None,
    target_scene: str | None = None,
    closes_layer: bool = False,
    fill: str | None = None,
    color: str | None = None,
    size: float | None = None,
    avoid_overlap: bool = True,
    output_path: str | None = None,
    in_place: bool = False,
) -> dict:
    """Tiklanabilir buton ekler.

    Nereye gidecegi, oncelik sirasiyla: target_scene (baska bolum),
    target_slide (belirli slayt), closes_layer=True (bulundugu katmani kapatir,
    popup kapatma dugmesi icin) ya da hicbiri verilmezse sonraki slayt.
    x/y/w/h slaydin YUZDESIdir; varsayilan konum sag alttir."""
    _guard(path)
    pkg = StoryPackage(path)
    result = authoring.add_button(
        pkg, slide, text, x=x, y=y, w=w, h=h, target_slide=target_slide,
        target_scene=target_scene, closes_layer=closes_layer,
        fill=fill, color=color, size=size, avoid_overlap=avoid_overlap,
    )
    return {**result, **_write(pkg, path, output_path, in_place)}


@mcp.tool()
def add_shape(
    path: str,
    slide: str,
    kind: str = "roundRect",
    x: float = 10,
    y: float = 30,
    w: float = 30,
    h: float = 15,
    fill: str | None = None,
    text: str | None = None,
    color: str | None = None,
    size: float | None = None,
    align: str = "c",
    output_path: str | None = None,
    in_place: bool = False,
) -> dict:
    """Slayda sekil ekler: panel, kart, ayirac, rozet.

    kind: rect | roundRect | oval | line | textBox
    Tasarimin govdesi bunlardir: paragrafin arkasindaki yuvarlak panel,
    bolumler arasindaki ince cizgi. x/y/w/h slaydin YUZDESIdir."""
    _guard(path)
    pkg = StoryPackage(path)
    result = authoring.add_decoration(
        pkg, slide, kind, x=x, y=y, w=w, h=h,
        fill=fill, text=text, color=color, size=size, align=align,
    )
    return {**result, **_write(pkg, path, output_path, in_place)}


@mcp.tool()
def restyle_text(
    path: str,
    slide: str,
    color: str | None = None,
    size: float | None = None,
    bold: bool | None = None,
    font: str | None = None,
    shape: str | None = None,
    output_path: str | None = None,
    in_place: bool = False,
) -> dict:
    """Slayttaki metinlerin rengini/boyutunu degistirir; shape verilmezse hepsi."""
    _guard(path)
    pkg = StoryPackage(path)
    result = authoring.restyle_slide_text(
        pkg, slide, color=color, size=size, bold=bold, font=font, shape=shape
    )
    return {**result, **_write(pkg, path, output_path, in_place)}


@mcp.tool()
def slide_properties(path: str, slide: str) -> dict:
    """Slaydin ilerleme kipi, menu gorunurlugu ve player kontrolleri."""
    return settings.read_slide_properties(StoryPackage(path), slide)


@mcp.tool()
def set_slide_properties(
    path: str,
    slide: str,
    advance_by_user: bool | None = None,
    hide_from_menu: bool | None = None,
    show_in_review: bool | None = None,
    count_in_slide_numbers: bool | None = None,
    prev: bool | None = None,
    next: bool | None = None,
    submit: bool | None = None,
    menu: bool | None = None,
    seek: bool | None = None,
    replay: bool | None = None,
    output_path: str | None = None,
    in_place: bool = False,
) -> dict:
    """Slide Properties: ilerleme kipi ve player dugmeleri.

    advance_by_user=True kullanicinin tiklamasini bekler. prev/next=False o
    slaytta geri/ileri dugmelerini kapatir."""
    _guard(path)
    pkg = StoryPackage(path)
    result = settings.set_slide_properties(
        pkg, slide, advance_by_user=advance_by_user, hide_from_menu=hide_from_menu,
        show_in_review=show_in_review, count_in_slide_numbers=count_in_slide_numbers,
        prev=prev, next=next, submit=submit, menu=menu, seek=seek, replay=replay,
    )
    return {**result, **_write(pkg, path, output_path, in_place)}


@mcp.tool()
def story_size(path: str) -> dict:
    """Projenin slayt boyutu (piksel)."""
    width, height = settings.story_size(StoryPackage(path))
    return {"width": width, "height": height}


@mcp.tool()
def set_story_size(
    path: str,
    width: int,
    height: int,
    output_path: str | None = None,
    in_place: bool = False,
) -> dict:
    """Proje slayt boyutunu degistirir (orn. 1920x1080).

    Mevcut sekiller kendi koordinatlarini korur; Storyline'da boyut
    degistirildiginde de boyle olur."""
    _guard(path)
    pkg = StoryPackage(path)
    result = settings.set_story_size(pkg, width, height)
    return {**result, **_write(pkg, path, output_path, in_place)}


@mcp.tool()
def theme(path: str) -> dict:
    """Tema renk yuvalari ve fontu (slide master'larda tutulur)."""
    return settings.read_theme(StoryPackage(path))


@mcp.tool()
def set_theme_colors(
    path: str,
    colors: dict,
    master: str | None = None,
    output_path: str | None = None,
    in_place: bool = False,
) -> dict:
    """Tema renklerini degistirir: {"accent1": "#FFC72C", "dk1": "#0E1B3D"}

    Yuvalar: dk1, lt1, dk2, lt2, accent1..accent6, hlink, folHlink.
    schemeClr ile bu yuvalara bagli her sekil birden degisir; tek tek
    boyamaktan farki budur. master verilmezse tum master'lar guncellenir."""
    _guard(path)
    pkg = StoryPackage(path)
    result = settings.set_theme_colors(pkg, colors, master=master)
    return {**result, **_write(pkg, path, output_path, in_place)}


@mcp.tool()
def set_theme_font(
    path: str,
    font: str,
    master: str | None = None,
    output_path: str | None = None,
    in_place: bool = False,
) -> dict:
    """Tema fontunu degistirir (orn. 'Open Sans', 'Inter', 'Segoe UI')."""
    _guard(path)
    pkg = StoryPackage(path)
    result = settings.set_theme_font(pkg, font, master=master)
    return {**result, **_write(pkg, path, output_path, in_place)}


@mcp.tool()
def add_results_slide(
    path: str,
    scene: str | None = None,
    name: str = "Sonuclar",
    output_path: str | None = None,
    in_place: bool = False,
) -> dict:
    """Quiz sonuc slaydi ekler (puan raporlama ekrani).

    Slayt eklenir ve dosya acilir durumda kalir; puanlamanin dogru calismasi
    devraldigi quiz baglantilarina baglidir ve yayinlamadan dogrulanamaz."""
    _guard(path)
    pkg = StoryPackage(path)
    result = authoring.add_results_slide(pkg, scene=scene, name=name)
    return {**result, **_write(pkg, path, output_path, in_place)}


@mcp.tool()
def list_player_colors(path: str) -> dict:
    """Player'da adiyla degistirilebilen renkler ve gruplari."""
    return settings.list_player_colors(StoryPackage(path))


@mcp.tool()
def set_player_color(
    path: str,
    name: str,
    color: str,
    alpha: int = 100,
    group: str | None = None,
    output_path: str | None = None,
    in_place: bool = False,
) -> dict:
    """Player'in adlandirilmis bir rengini degistirir. alpha 0-100 (seffaflik).

    Ayni renk adi birden cok grupta gecebilir; group verilmezse hepsi degisir."""
    _guard(path)
    pkg = StoryPackage(path)
    result = settings.set_player_color(pkg, name, color, alpha=alpha, group=group)
    return {**result, **_write(pkg, path, output_path, in_place)}


@mcp.tool()
def list_button_states(path: str, slide: str) -> list[dict]:
    """Slayttaki state tasiyan sekiller (Normal/Hover/Down/Visited/Disabled)."""
    return authoring.list_button_states(StoryPackage(path), slide)


@mcp.tool()
def set_button_state(
    path: str,
    slide: str,
    button: str,
    state: str,
    fill: str | None = None,
    color: str | None = None,
    output_path: str | None = None,
    in_place: bool = False,
) -> dict:
    """Bir butonun belirli state'ini renklendirir (orn. state='Hover').

    button olarak sekil GUID'i ya da uzerindeki metin verilebilir."""
    _guard(path)
    pkg = StoryPackage(path)
    result = authoring.set_button_state(pkg, slide, button, state, fill=fill, color=color)
    return {**result, **_write(pkg, path, output_path, in_place)}


@mcp.tool()
def list_layers(path: str, slide: str | None = None) -> list[dict]:
    """Slayt katmanlari (layer)."""
    return authoring.list_layers(StoryPackage(path), slide)


@mcp.tool()
def add_layer(
    path: str,
    slide: str,
    name: str,
    text: str | None = None,
    open_from: str | None = None,
    output_path: str | None = None,
    in_place: bool = False,
) -> dict:
    """Slayda katman ekler; popup boyle kurulur.

    open_from verilirse o sekle tiklaninca katman acilir (showSubSlide)."""
    _guard(path)
    pkg = StoryPackage(path)
    result = authoring.add_layer(pkg, slide, name, text=text, open_from=open_from)
    return {**result, **_write(pkg, path, output_path, in_place)}


@mcp.tool()
def add_variable(
    path: str,
    name: str,
    kind: str = "num",
    default: str | None = None,
    output_path: str | None = None,
    in_place: bool = False,
) -> dict:
    """Kullanici degiskeni olusturur (sayac, bayrak, isim gibi).

    kind: num | text | bool. Ad harf/alt cizgi ile baslamali, bosluk ve Turkce
    karakter icermemeli (Storyline'in kurali)."""
    _guard(path)
    pkg = StoryPackage(path)
    result = logic.add_variable(pkg, name, kind, default)
    return {**result, **_write(pkg, path, output_path, in_place)}


@mcp.tool()
def add_trigger(
    path: str,
    slide: str,
    action: str,
    shape: str | None = None,
    event: str = "OnClick",
    variable: str | None = None,
    operation: str = "add",
    value: str | None = None,
    target_slide: str | None = None,
    target_scene: str | None = None,
    layer: str | None = None,
    state: str | None = None,
    javascript: str | None = None,
    watch: str | None = None,
    drop_targets: list[str] | None = None,
    state_name: str | None = None,
    conditions: list[dict] | None = None,
    output_path: str | None = None,
    in_place: bool = False,
) -> dict:
    """Tetikleyici ekler. Sayac, kilit ve dallanma mantigi bununla kurulur.

    action:
      adjust_variable    - degiskeni degistirir (operation: set | add, value)
      jump_slide         - target_slide verilmezse sonraki slayda gider
      jump_scene         - target_scene adiyla baska bolume gider
      show_layer         - layer adiyla katman acar
      hide_layer         - katmani kapatir
      change_state       - shape'in gorunumunu state adina cevirir
      execute_javascript - javascript alanindaki kodu calistirir

    HEDEF GEREKTIREN OLAYLAR (OnDrop, OnStateChange, OnDialTurns) icin `shape`
    ZORUNLU: bu olaylarin tetikleyicileri Storyline'in kendi dosyalarinda
    daima nesnenin kendi trigLst'inde yasiyor (olculdu). Ayrica:
      OnDrop        -> drop_targets: uzerine birakilinca tetikleyecek nesneler
      OnStateChange -> state_name: hangi duruma gecince tetiklenecek

    event=OnVariableValueChange ise `watch` ZORUNLU: hangi degiskenin degisimi
    izlenecek. Olculdu -- watch olmadan olay hic tetiklenmiyor, trigger
    sessizce calismiyor. JS koprusunun geri yonu budur:
      JS SetVar("Skor", 42)  ->  OnVariableValueChange (watch="Skor")  ->  dallanma

    shape verilmezse tetikleyici slaydin kendisine baglanir (event=OnStart icin
    uygundur). shape olarak sekil GUID'i ya da uzerindeki metin verilebilir.

    JS ile Storyline arasindaki kopru degiskenlerdir:
      var p = GetPlayer(); p.GetVar("Ad"); p.SetVar("Sonuc", 42);
    Yazilan degiskenin dosyada VAR OLMASI gerekir -- olmayan bir ada yazan kod
    hata vermez, hicbir sey yapmaz.

    conditions: [{"variable": "Skor", "op": "gte", "value": 6}]
      op: eq, noteq, gt, gte, lt, lte"""
    _guard(path)
    pkg = StoryPackage(path)
    result = logic.add_trigger(
        pkg, slide, action, shape=shape, event=event, variable=variable,
        operation=operation, value=value, target_slide=target_slide,
        target_scene=target_scene, layer=layer, state=state,
        javascript=javascript, watch=watch, drop_targets=drop_targets,
        state_name=state_name, conditions=conditions,
    )
    return {**result, **_write(pkg, path, output_path, in_place)}


@mcp.tool()
def list_js_capabilities() -> dict:
    """Olculmus JS yeteneklerini listeler -- JS yazmanin BIRINCIL yolu.

    Her kayit bes alan tasir: kod, gerektirdigi degiskenler (parametreler),
    baglandigi olay, NE ZAMAN CALISMADIGI, ve NASIL OLCULDUGU. Son ikisi
    sussleme degil giris sarti: olcumu olmayan yetenek kataloga alinmaz.

    Neden ham kod degil de katalog: `audit` JS'i SOZCUKSEL denetler (Node ile
    parse eder, GetVar/SetVar'in duz metin argumanini cozer) ama kodun DOGRU
    oldugunu soyleyemez. Katalog kapali bir kume oldugu icin her girdisi
    olculebilir; ham kod sonsuz girdi uzayidir ve olculemez.

    Ham JS kapali degil: `add_trigger(action="execute_javascript")` duruyor.
    Ama once `audit` calistirilmali -- js_syntax_errors ve
    js_unresolved_variables alanlari sessiz kalan kodu gosterir.

    parametreler[].rol:
      yazilan  - yetenek bu degiskeni KENDISI olusturur
      okunan   - degisken ONCEDEN var olmali; yetenek onu olusturmaz"""
    return {"capabilities": jscat.liste(),
            "kapsam": f"{len(jscat.KATALOG)} yetenek, hepsi 'veri' kesitinde; "
                      f"slayt DOM'una dokunan yetenek yok."}


@mcp.tool()
def check_javascript(path: str, code: str) -> dict:
    """Ham JS'i EKLEMEDEN ONCE denetle -- katalogun disina cikan yolun kapisi.

    `audit` yalnizca dosyaya YAZILMIS kodu gorur, yani ham kodu once eklemek
    sonra denetlemek gerekirdi; o sirada kapi kapi degildir. Burada ayni iki
    kontrol koda dogrudan uygulanir:

      * sozdizimi (Node ile parse). Node yoksa "gecti" DENMEZ:
        syntax_checked=false doner ve bunu verdikte cevirmeyin.
      * degisken adlari. Olmayan bir ada yazan JS hata vermez, hicbir sey
        yapmaz (olculdu) -- yani sessizce kaybolur.
      * XML'de yasak kontrol karakterleri. Bunlar paketi okunamaz yapar ve
        `add_trigger` zaten reddeder; burada once gorulur.

    Ikisi de SOZCUKSEL: kod parse ediyor ve adlari cozuluyor olabilir ama
    yine de yanlis isi yapiyor olabilir. Onun icin once `list_js_capabilities`
    bakin -- katalogda karsiligi varsa ham kod yazmayin."""
    _guard(path)
    pkg = StoryPackage(path)
    refs = model.js_kod_referanslari(pkg, code)
    sozdizimi = jscheck.check([code or ""])
    hata = None
    if sozdizimi["available"] and sozdizimi["results"]:
        r = sozdizimi["results"][0]
        hata = None if r["ok"] else r["error"]
    yasak = sorted(i for i, ch in enumerate(code or "")
                   if ord(ch) < 0x20 and ch not in "\t\n\r")
    return {
        "syntax_checked": sozdizimi["available"],
        "syntax_reason": sozdizimi["reason"],
        "syntax_error": hata,
        "unresolved_variables": [u["name"] for u in refs["unresolved"]],
        "dynamic_calls": refs["dynamic_calls"],
        "scope": refs["scope"],
        "control_chars": yasak[:5],
        "clean": (hata is None and not refs["unresolved"] and not yasak
                  and sozdizimi["available"]),
    }


@mcp.tool()
def add_js_capability(
    path: str,
    slide: str,
    capability: str,
    params: dict | None = None,
    event: str | None = None,
    shape: str | None = None,
    output_path: str | None = None,
    in_place: bool = False,
) -> dict:
    """Katalogdaki bir JS yetenegini slayda baglar.

    `list_js_capabilities` ile adlari ve parametreleri gorun. Yetenegin
    "yazilan" degiskenleri yoksa OLUSTURULUR; "okunan" degiskenleri yoksa
    HATA verilir -- cunku onlari baska bir seyin doldurmasi gerekir ve
    olmayan bir ada yazan JS sessizce hicbir sey yapmaz.

    event verilmezse yetenegin kendi olayi kullanilir. Tetikleyici ham JS ile
    ayni yoldan gecer, yani EVENTS kapisi ve kontrol karakteri kapisi burada
    da gecerlidir."""
    _guard(path)
    pkg = StoryPackage(path)
    result = jscat.uygula(pkg, slide, capability, params=params, event=event,
                          shape=shape)
    return {**result, **_write(pkg, path, output_path, in_place)}


@mcp.tool()
def build_course(
    path: str,
    operations: list[dict],
    output_path: str | None = None,
    in_place: bool = False,
) -> dict:
    """Birden cok yazma islemini tek seferde uygular ve bir kez kaydeder.

    Kurs iskeleti kurmanin yolu budur; islemler sirayla islenir:
      {"op": "create_scene",    "name": "01_Giris"}
      {"op": "add_slide",       "template": "slide7.xml", "scene": "01_Giris",
                                "title": "Hos geldiniz"}
      {"op": "add_question",    "template": "slide.xml",  "scene": "01_Giris",
                                "prompt": "...", "choices": ["a","b","c","d"],
                                "correct": [1], "points": 20}
      {"op": "duplicate_slide", "slide": "slide3.xml"}
      {"op": "update_text",     "edits": [{"addr": "...", "new_text": "..."}]}
      {"op": "set_background",  "slide": "slidef.xml", "color": "#0A2240"}
      {"op": "add_text_box",    "slide": "slidef.xml", "text": "Hos geldiniz",
                                "x": 10, "y": 30, "w": 80, "h": 18,
                                "color": "#FFED00", "size": 40, "align": "c"}
      {"op": "add_button",      "slide": "slidef.xml", "text": "Devam",
                                "x": 74, "y": 84, "w": 20, "h": 10}
      {"op": "restyle_text",    "slide": "slidef.xml", "color": "#FFED00"}
      {"op": "add_variable",    "name": "Skor", "kind": "num", "default": 0}
      {"op": "add_trigger",     "slide": "slidef.xml", "action": "adjust_variable",
                                "shape": "Devam", "variable": "Skor",
                                "operation": "add", "value": 1}
      {"op": "add_js_capability", "slide": "slidef.xml", "capability": "tarih",
                                  "params": {"hedef": "Tarih"}}

    Sekil islemlerinde x/y/w/h slaydin YUZDESIdir (0-100).

    JS icin `add_js_capability` BIRINCIL yoldur: adlari ve parametreleri
    `list_js_capabilities` verir, her yetenegin yaninda nasil olculdugu ve
    NE ZAMAN CALISMADIGI yazilidir. Katalogun kapsamadigi is icin
    `add_trigger` + `action: "execute_javascript"` durur, ama o kod
    dogrulanmaz -- eklendikten sonra `audit` calistirin.
    """
    if not operations:
        raise StoryError("Bos islem listesi.")
    _guard(path)
    pkg = StoryPackage(path)
    results = []
    for i, op in enumerate(operations):
        try:
            results.append({"index": i, "op": op.get("op"), "result": _apply_op(pkg, op)})
        except Exception as exc:
            raise StoryError(f"{i}. islem ({op.get('op')!r}) basarisiz: {exc}") from exc
    return {"operations": results, **_write(pkg, path, output_path, in_place)}


# -------------------------------------------------------------------- audit


@mcp.tool()
def audit(path: str) -> dict:
    """Tutarlilik ve erisilebilirlik denetimi: kullanilmayan degiskenler,
    alt metinsiz gorseller, cikissiz slaytlar, bos metin kutulari, tekrarlar,
    ve JS koprusu (cozulmeyen degisken adlari + sozdizimi)."""
    pkg = StoryPackage(path)
    idx = model.slide_index(pkg)
    runs = model.text_runs(pkg)
    trigs = model.triggers(pkg)
    variables = model.variables(pkg)

    all_text = "\n".join(r.text for r in runs)
    used_vars = {t["variable"] for t in trigs if "variable" in t}
    unused = [
        v["name"]
        for v in variables
        if v["type"] == "user"
        and v["name"] not in used_vars
        and f"%{v['name']}%" not in all_text
    ]

    images_without_alt: list[dict] = []
    empty_text: list[dict] = []
    for part, ref in idx.items():
        root = pkg.parse(part)
        for pic in root.iter("pic"):
            alt_node = pic.find("langAltText")
            alt = (pic.get("altText") or "") + (
                (alt_node.text or "") if alt_node is not None else ""
            )
            if not alt.strip() and pic.get("acc", "true") == "true":
                images_without_alt.append(
                    {"slide": ref.basename, "slide_name": ref.name, "shape": pic.get("g", "")}
                )
        for shape, _text_el, doc, _state in model._iter_text_shapes(root):
            if not model._doc_text(doc).strip():
                empty_text.append(
                    {
                        "slide": ref.basename,
                        "slide_name": ref.name,
                        "shape_type": shape.tag,
                        "shape": shape.get("g", ""),
                    }
                )

    slides_with_exit = {t["slide"] for t in trigs if t["action"] in NAVIGATING_ACTIONS}
    dead_ends = [
        {"slide": ref.basename, "slide_name": ref.name, "scene": ref.scene_name}
        for ref in idx.values()
        if ref.basename not in slides_with_exit
    ]

    seen: dict[str, set[str]] = {}
    for run in runs:
        text = run.text.strip()
        if len(text) >= 25:
            seen.setdefault(text, set()).add(f"{run.slide} ({run.slide_name})")
    duplicates = [
        {"text": text[:90], "slides": sorted(places)}
        for text, places in seen.items()
        if len(places) > 1
    ]

    # JS KOPRUSU. Iki ayri soru, ikisi de SESSIZ kusur sinifi:
    #   cozulmeyen ad -> olculdu, hata vermiyor; SetVar hicbir sey yapmiyor,
    #                    GetVar null donuyor ve null JS'te sessizce yayiliyor
    #   sozdizimi     -> Storyline JS'i dogrulamiyor; bozuk kod panelde durur
    #                    ve calisma aninda hicbir sey olmaz
    # Hesap tek yerde: adlari model.js_references cozuyor (K12).
    # SAYI KAYBI -- aracin URETMEDIGI dosyalar icin. Yazma kapilari
    # (`add_variable`, `add_trigger`) bundan sonrasini engelliyor ama zaten
    # var olan bir projede bozuk deger duruyor olabilir ve sessizdir.
    kayipli_sayilar = []
    for degisken in model.variables(pkg):
        if degisken.get("data_type") != "num" or degisken.get("type") != "user":
            continue
        sorun = logic.sayi_sorunu(degisken.get("default"), literal=False)
        if sorun:
            kayipli_sayilar.append({"where": "variable", "name": degisken["name"],
                                    "value": degisken.get("default"),
                                    "problem": sorun})
    for trig in model.triggers(pkg):
        deger = trig.get("value")
        if trig.get("action") != "adjustVar" or deger in (None, ""):
            continue
        sorun = logic.sayi_sorunu(deger, literal=True)
        if sorun:
            kayipli_sayilar.append({"where": "trigger", "slide": trig.get("slide", ""),
                                    "name": trig.get("variable", ""),
                                    "value": deger, "problem": sorun})

    # OGRETIM OLCUSU. Kursun NASIL GORUNDUGU degil, ogrenciye BIR SEY
    # YAPTIRIP yaptirmadigi. Ayri modulde cunku tek yerde hesaplanmali:
    # ikinci bir uygulama, ayni sayiyi baska bir kesitle uretirdi.
    ogretim = pedagogy.olc(pkg)

    js_refs = model.js_references(pkg)
    js_kodlari = [t["javascript"] for t in trigs if t.get("javascript")]
    js_sozdizimi = jscheck.check(js_kodlari)
    bozuk_kod = []
    if js_sozdizimi["available"]:
        eslesme = [t for t in trigs if t.get("javascript")]
        for trig, sonuc in zip(eslesme, js_sozdizimi["results"]):
            if not sonuc.get("ok"):
                bozuk_kod.append({"slide": trig.get("slide", ""),
                                  "event": trig.get("event", ""),
                                  "error": sonuc.get("error")})

    return {
        "unused_user_variables": unused,
        "images_without_alt_text": images_without_alt,
        "empty_text_shapes": empty_text,
        "slides_without_navigation": dead_ends,
        "ardisik_etkilesimsiz_slayt": ogretim["ardisik_etkilesimsiz_slayt"],
        "sahne_basina_soru": ogretim["sahne_basina_soru"],
        "sorusuz_sahneler": ogretim["sorusuz_sahneler"],
        "sonuc_slaydi": ogretim["sonuc_slaydi"],
        "tetikleyici_cesitliligi": ogretim["tetikleyici_cesitliligi"],
        "ogretim_kapsam": ogretim["ogretim_kapsam"],
        "duplicate_text": duplicates[:25],
        "js_unresolved_variables": js_refs["unresolved"],
        "js_reference_scope": js_refs["scope"],
        "js_syntax_errors": bozuk_kod,
        "lossy_numbers": kayipli_sayilar,
        "lossy_number_scope": (
            "Yalnizca STATIK degerler bakildi: degisken varsayilanlari "
            "(8 anlamli basamak siniri) ve adjust_variable literalleri "
            "(7 basamak + 2^31 kelepcesi). BIRIKEN degerler bu kesitin "
            "DISINDA: adjust_variable sinirini SONUCA uyguluyor ve sonuc "
            "calisma aninda olusuyor -- olculdu, 0+10000000+1 = 10000000, "
            "yani +1 hic islemedi. Iki kucuk literal ust uste toplanip 7 "
            "basamagi asarsa burada GORUNMEZ. Sifir bulgu 'hicbir sayi "
            "bozulmuyor' demek degildir. 7 basamagi asabilecek sayaclar "
            "adjust_variable yerine JS ile tutulmali: JS SetVar tam degeri "
            "tasiyor (olculdu)."),
        "js_syntax_scope": (
            js_sozdizimi["reason"] or
            f"{len(js_kodlari)} JS tetikleyicisi parse edildi; "
            "sozdizimi denetlendi, DAVRANIS denetlenmedi."),
        "summary": {
            "unused_variables": len(unused),
            "images_missing_alt": len(images_without_alt),
            "empty_text_shapes": len(empty_text),
            "slides_without_navigation": len(dead_ends),
            "duplicate_text_blocks": len(duplicates),
            "js_triggers": len(js_kodlari),
            "js_unresolved_variables": len(js_refs["unresolved"]),
            "js_dynamic_calls": js_refs["dynamic_calls"],
            # Node yoksa None -- "0 hata" DEGIL (K1b: girdisi olmayan
            # kontrol gecti demez).
            "js_syntax_errors": (len(bozuk_kod) if js_sozdizimi["available"]
                                 else None),
            "lossy_numbers": len(kayipli_sayilar),
            # OGRETIM. Ozetteki digerleri "kac kusur" sayar; bunlar DURUM
            # sayar -- esigi cagiran koyar, arac yargilamaz.
            "ardisik_etkilesimsiz_slayt": (
                ogretim["ardisik_etkilesimsiz_slayt"]["en_uzun"]),
            "etkilesimli_slayt": (
                ogretim["ardisik_etkilesimsiz_slayt"]["etkilesimli_slayt"]),
            "toplam_soru": sum(ogretim["sahne_basina_soru"].values()),
            "sorusuz_sahne": len(ogretim["sorusuz_sahneler"]),
            "sonuc_slaydi": bool(ogretim["sonuc_slaydi"]),
            "tetikleyici_ayrik_cift": (
                ogretim["tetikleyici_cesitliligi"]["ayrik_cift"]),
        },
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
