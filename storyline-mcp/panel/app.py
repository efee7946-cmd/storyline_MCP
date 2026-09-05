"""Storyline Panel -- a desktop control panel for .story projects.

Runs as a native window (WebView2) rather than a browser tab, so it can sit
beside Storyline and reach the local filesystem. There is no HTTP server:
pywebview's js_api bridge lets the page call these methods directly, which
removes the port, the CORS dance, and the risk of leaving a local server
listening after the window closes.

Edits are staged, not applied one by one. The page builds a queue of
operations and hands the whole queue over at once, so a course is written in a
single pass with a single save and a single verification -- the same contract
build_course offers over MCP.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import traceback
from pathlib import Path

# pythonw.exe starts the process with no console, leaving sys.stdout and
# sys.stderr as None. The first library that logs to them raises, and because
# there is no console the traceback goes nowhere -- the window simply never
# appears. Redirect to nul before importing anything that configures logging.
if sys.stdout is None or sys.stderr is None:
    _null = open(os.devnull, "w", encoding="utf-8")
    sys.stdout = sys.stdout or _null
    sys.stderr = sys.stderr or _null

import webview

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import builder  # noqa: E402
import production  # noqa: E402
import storyline_ctl  # noqa: E402
from agent import AgentRun, find_cli  # noqa: E402

from storyline_mcp import authoring, compose, media, medya, model  # noqa: E402
from storyline_mcp.clone import clone_slide, create_scene  # noqa: E402
from storyline_mcp.edits import Edit, apply_text_edits  # noqa: E402
from storyline_mcp.package import StoryPackage, lock_state  # noqa: E402
from storyline_mcp.server import _apply_op, _guard, audit  # noqa: E402

HERE = Path(__file__).resolve().parent

# Held at module level, not on Api: pywebview walks the Api object's attributes
# when it builds the bridge, so anything stored there has to stay trivially
# serialisable.
_ACTIVE_RUN: AgentRun | None = None


def _palette_for(options: dict) -> dict | None:
    """Panelin secimini TAM bir palete cevirir.

    tema  -> themes.json'daki dogrulanmis palet (6 tema x 6 varyant olculdu)
    ozel  -> secilen zeminden turetilir; yazi renkleri zeminden gelir, tersi
             degil, ve karsilasabilecekleri her zemine (bg ve deep) gore
             esigi gecene kadar itilir.
    """
    theme = (options.get("theme") or "").strip()
    if theme and theme != "ozel":
        return {k: v for k, v in compose.theme_palette(theme).items()
                if not k.startswith("_")}
    bg, accent = options.get("bg"), options.get("accent")
    if not bg:
        return None
    return compose.palette_from(bg, accent)


# KOMUTLAR ARASI BAGLAM. Her komut ayri bir CLI oturumuydu ve onceki
# alisverisi hic gormuyordu -- olculdu ve kullanici bildirdi: ajan "hangi
# slayt?" diye sordu, kullanici "2" dedi, ajan bu kez ILK istegi (arka plani
# duzelt) bilmeden "2. slaytla ilgili ne istiyorsun?" diye geri sordu.
#
# Oturum DOSYA BASINA tutulur: baska bir .story baska bir baglamdir ve
# birinin konusmasi digerine tasinirsa ajan yanlis dosyayi hatirlar.
_OTURUM: dict[str, str] = {}
# _push_event'in hangi dosya icin kostugunu bilmesi gerekiyor;
# AgentRun olayi dosya adini tasimiyor.
_SON_YOL: list[str | None] = [None]


def _push_event(event: dict) -> None:
    """Hand one agent event to the page as it arrives."""
    sid = event.get("session_id")
    if sid and event.get("kind") == "final" and _SON_YOL[0]:
        _OTURUM[_SON_YOL[0]] = sid
    if not webview.windows:
        return
    payload = json.dumps(event, ensure_ascii=False)
    try:
        webview.windows[0].evaluate_js(f"window.onAgentEvent({payload})")
    except Exception:  # noqa: BLE001 - the window may be closing mid-run
        pass


# Arkada suren yeniden acma. Panel isini bitirir bitirmez donuyor; Storyline
# kendi zamaninda geri geliyor. Tek tehlike ARALIK: acilis surerken baslatilan
# yeni bir islem, dosyayi Storyline daha almadan yazar, sonra Storyline eski
# kopyayi acar ve ilk kaydinda yeni yaziyi ezer. Bu yuzden her yazan yol once
# _acilisi_bekle() cagirir -- bekleme ancak gercekten cakisirsa hissedilir.
_ACILIS: threading.Thread | None = None


def _arkada_ac(path: str) -> None:
    global _ACILIS
    def _kos() -> None:
        acildi = storyline_ctl.reopen(path)
        # `bitti`: bu satir bir DURUM bildirir, suren bir is degil. Sayfa
        # doner simgeyi ona gore kaldirir -- bitmis bir isin ustunde donen
        # simge birakmak, kullaniciya "hala calisiyor" demektir (kullanici
        # bildirdi, 2026-08-29).
        _push_event({"kind": "medya", "bitti": True,
                     "text": "Storyline'da yeniden açıldı." if acildi else
                             "Yeniden açma doğrulanamadı; dosyayı elle açmanız "
                             "gerekebilir."})
    _ACILIS = threading.Thread(target=_kos, daemon=True)
    _ACILIS.start()


def _acilisi_bekle(timeout: float = 60.0, haber=None) -> None:
    """Arkada suren yeniden acma bitene kadar bekle.

    Beklerken NE BEKLENDIGI yazilir. Yazilmazsa kullanici, kendi istedigi isin
    surdugunu sanir: serit "dosyalar ekleniyor" der ve aslinda hicbir sey
    eklenmemistir, Storyline'in acilmasi beklenmektedir.
    """
    if _ACILIS and _ACILIS.is_alive():
        if haber:
            haber()
        _ACILIS.join(timeout)


def _orchestrate(run: AgentRun, path: str, auto_cycle: bool) -> None:
    """Run a command, closing and reopening Storyline around it if it holds
    the file.

    The project cannot be edited while Storyline has it: the file is locked
    against all access, and Storyline's own in-memory copy would overwrite any
    change on its next save. Rather than making the user do the close/reopen
    dance on every command, the panel does it -- and only when this exact file
    is the one open.
    """
    reopen_after = False
    try:
        if auto_cycle and storyline_ctl.holds(path):
            _push_event({"kind": "step", "text": "Storyline bu projeyi açık tutuyor — kaydedilip kapatılıyor…"})
            result = storyline_ctl.save_and_close(path)
            if not result.get("closed"):
                _push_event({"kind": "error", "text": result.get("reason", "Storyline kapatılamadı.")})
                return
            reopen_after = True
            _push_event({"kind": "step", "text": "Kapatıldı. Değişiklik uygulanıyor…"})

        run.run_sync()

    finally:
        if reopen_after:
            _push_event({"kind": "step", "text": "Storyline'da yeniden açılıyor…"})
            opened = storyline_ctl.reopen(path)
            _push_event({
                "kind": "step",
                "text": "Yeniden açıldı." if opened else
                        "Yeniden açma doğrulanamadı; dosyayı elle açmanız gerekebilir.",
            })
        _push_event({"kind": "done"})


def _run_builder(path: str, brief: str, model: str, options: dict) -> None:
    """Whole-course build, with the same close/reopen courtesy as a command."""
    reopen_after = False
    try:
        _push_event({"kind": "step", "text": "Kurs oluşturma başlıyor…"})
        if storyline_ctl.holds(path):
            _push_event({"kind": "step", "text": "Storyline bu projeyi açık tutuyor — kaydedilip kapatılıyor…"})
            result = storyline_ctl.save_and_close(path)
            if not result.get("closed"):
                _push_event({"kind": "error", "text": result.get("reason", "Storyline kapatılamadı.")})
                return
            reopen_after = True

        palette = _palette_for(options)
        _push_event({"kind": "step", "text": "Builder çalışıyor…"})
        report = builder.build(
            path, brief, model=model, options=options, palette=palette or None,
            on_progress=lambda text: _push_event({"kind": "step", "text": text}),
        )
        verified = report["verified"]
        _push_event({"kind": "step", "text": f"Dosya kaydedildi. Doğrulama: {'✓ Başarılı' if verified.get('ok') else '✗ Sorun var'}"})
        inherited = report.get("inherited") or {}
        note = ""
        if inherited.get("empty_slides"):
            scenes = inherited.get("empty_scenes") or []
            note = (f" Kaynak dosyadan gelen {inherited['empty_slides']} boş slayt "
                    f"duruyor" + (f" ({', '.join(scenes)} sahneleri tamamen boş)"
                                  if scenes else "") + "; silinmedi.")
        if inherited.get("dangling_triggers"):
            note += (f" {inherited['dangling_triggers']} tetikleyicinin hedefi "
                     "yok (Storyline'da 'unassigned' görünür).")
        if report.get("medya_istekleri"):
            note += (f" {report['medya_istekleri']} slayt için görsel/video "
                     "isteniyor — GÖRSEL & VİDEO sekmesinde yazıyor.")
        _push_event({
            "kind": "final",
            "error": not verified["ok"],
            "text": (f"{report['scenes']} bölüm, {report['slides_created']} slayt kuruldu"
                     + (f", {report['questions']} soru eklendi" if report["questions"] else "")
                     + (f" ({report['question_fallbacks']} soru menü olarak kuruldu)"
                        if report["question_fallbacks"] else "")
                     + "." + note),
            "output_path": report["written"],
        })
    except Exception as exc:  # noqa: BLE001
        import traceback
        metin = " ".join(f"{type(exc).__name__}: {exc}".split())
        # Log the build failure to production log
        try:
            production.record(
                path,
                "build_failed",
                {"verified": {"ok": False, "problems": [metin[:200]]}},
                context={
                    "error": metin[:300],
                    "traceback": traceback.format_exc()[:500],
                },
            )
        except Exception:
            pass  # If logging fails, still show error to user
        _push_event({"kind": "error",
                     "text": metin[:400] + ("…" if len(metin) > 400 else "")})
    finally:
        if reopen_after:
            _push_event({"kind": "step", "text": "Storyline'da yeniden açılıyor…"})
            storyline_ctl.reopen(path)
        _push_event({"kind": "done"})


def guarded(fn):
    """Surface failures to the page as data instead of a JS rejection."""

    def wrapper(*args, **kwargs):
        try:
            return {"ok": True, "data": fn(*args, **kwargs)}
        except Exception as exc:  # noqa: BLE001 - the panel reports every failure
            return {
                "ok": False,
                "error": str(exc),
                "detail": traceback.format_exc(limit=3),
            }

    wrapper.__name__ = fn.__name__
    return wrapper


class Api:
    """Bridge exposed to the page as pywebview.api.

    Deliberately holds no window reference. pywebview walks this object's
    attributes when it builds the bridge, and a stored Window leads it into
    the native .NET Form, where Bounds.Empty returns a Rectangle that has its
    own .Empty -- an infinite chain that floods stderr on every call. The
    window is reachable through webview.windows instead.
    """

    # ------------------------------------------------------------- session

    @guarded
    def pick_file(self) -> dict | None:
        # pywebview 6 renamed the constants; the old ones still work but warn.
        dialog = getattr(webview, "FileDialog", None)
        open_dialog = dialog.OPEN if dialog else webview.OPEN_DIALOG
        result = webview.windows[0].create_file_dialog(
            open_dialog,
            allow_multiple=False,
            file_types=("Storyline projesi (*.story)", "Tum dosyalar (*.*)"),
        )
        if not result:
            return None
        return self._summary(result[0])

    @guarded
    def summary(self, path: str) -> dict:
        return self._summary(path)

    def _summary(self, path: str) -> dict:
        pkg = StoryPackage(path)
        index = model.slide_index(pkg)
        questions = model.quiz(pkg)
        scenes = model.scenes(pkg)
        templates = authoring.list_templates(pkg)
        return {
            "path": str(Path(path).resolve()),
            "name": Path(path).name,
            "size_mb": round(Path(path).stat().st_size / 1024 / 1024, 2),
            "slide_count": len(index),
            "scene_count": len(scenes),
            "question_count": len(questions),
            "text_run_count": len(model.text_runs(pkg)),
            "scenes": scenes,
            "templates": templates,
            "scene_names": [s["scene"] for s in scenes],
            # Whether *this* file is held, not whether Storyline is running.
            # Another course being open elsewhere does not affect this one.
            "locked": lock_state(path) != "free",
        }

    @guarded
    def themes(self) -> list[dict]:
        """themes.json'daki paletler, panelde gosterilmek uzere.

        Liste panelde ELLE yazilmaz: themes.json'a bir tema eklendiginde ya
        da cikarildiginda panel sessizce eskir, ve kullanici olmayan bir
        temayi secebilir ya da yeni temayi hic goremez. Tek kaynak motor.
        """
        out = []
        for name in compose.theme_names():
            palette = compose.theme_palette(name)
            out.append({"name": name,
                        "label": compose.themes()[name].get("ad", name),
                        "bg": palette["bg"], "accent": palette["accent"],
                        "text": palette["text"]})
        return out

    @guarded
    def file_locked(self, path: str) -> bool:
        return lock_state(path) != "free"

    # ---------------------------------------------------------- medya istegi
    #
    # Kursu kuran model neyin gosterilmesi gerektigini bilir, dosyayi bulamaz.
    # Istekler `<kurs>.medya.json` icinde bekler; buradaki uc cagri onlari
    # okur, dosya sorar ve slayta koyar. Ayrintili gerekcesi panel/medya.py.

    @guarded
    def media_requests(self, path: str) -> dict:
        # Kopyalanacak metni MOTOR kurar, panel degil: yapistirilan sipariş ile
        # deftere yazılan istek aynı cümle olsun. Okuma anında üretilir, çünkü
        # eski defterlerde `olcu` alanı yok ve onlar da açılabilmeli.
        istekler = [{**i, "prompt": medya.prompt(i)} for i in medya.oku(path)]
        return {"istekler": istekler,
                "bekleyen": medya.bekleyen_sayisi(istekler),
                "gorsel_bicimleri": list(medya.GORSEL_BICIMLERI),
                "video_bicimleri": list(medya.VIDEO_BICIMLERI)}

    @guarded
    def pick_media(self, kind: str = "gorsel") -> dict | None:
        """Bir dosya sec ve yolunu geri ver. Hicbir sey eklenmez."""
        dialog = getattr(webview, "FileDialog", None)
        if kind == "video":
            kabul = ("Video (*" + ";*".join(medya.VIDEO_BICIMLERI) + ")",
                     "Tum dosyalar (*.*)")
        else:
            kabul = ("Gorsel (*" + ";*".join(medya.GORSEL_BICIMLERI) + ")",
                     "Tum dosyalar (*.*)")
        chosen = webview.windows[0].create_file_dialog(
            dialog.OPEN if dialog else webview.OPEN_DIALOG,
            allow_multiple=False, file_types=kabul,
        )
        if not chosen:
            return None
        source = Path(chosen[0])
        pixels = None
        if kind != "video":
            pixels = media.image_size(source.read_bytes())
        return {"path": str(source), "name": source.name,
                "mb": round(source.stat().st_size / 1024 / 1024, 2),
                "pixels": list(pixels) if pixels else None}

    @guarded
    def apply_media(self, path: str, secimler: list[dict]) -> dict:
        """Secilen dosyalari slaytlarina koy, kursu bir kez kaydet.

        Storyline dosyayi tutuyorsa komut yolundaki nezaket burada da gecerli:
        panel kaydeder, kapatir, uygular ve yeniden acar.
        """
        # Olaylar "medya" turunde gider, "step" turunde DEGIL: step, komut
        # akisinin sayacini baslatir ve onu yalnizca "done" durdurur -- medya
        # eklemek komut calistirmadigi icin o sayac hic durmazdi.
        _acilisi_bekle(haber=lambda: _push_event(
            {"kind": "medya",
             "text": "Storyline'ın yeniden açılması bekleniyor…"}))
        reopen_after = False
        if storyline_ctl.holds(path):
            _push_event({"kind": "medya",
                         "text": "Storyline bu projeyi açık tutuyor — kaydedilip kapatılıyor…"})
            closed = storyline_ctl.save_and_close(path)
            if not closed.get("closed"):
                raise RuntimeError(closed.get("reason", "Storyline kapatılamadı."))
            reopen_after = True
        try:
            # Kilit denetimi kapatmadan SONRA: once bakilsaydi, tam da panelin
            # kendi cozdugu durumda -- proje Storyline'da acikken -- reddederdi.
            _guard(path)
            _push_event({"kind": "medya", "text": "Dosyalar modüle ekleniyor…"})
            return medya.uygula(path, secimler)
        finally:
            # YENIDEN ACMA BEKLETMEZ. Eklemenin kendisi olculdu: 1.2 saniye.
            # Storyline'i kapatip yeniden acmak ise yarim dakikayi buluyor ve
            # bu cagri onu BEKLIYORDU -- kullanici, isi biteli otuz saniye
            # olmus bir panele bakiyordu. Is bittiginde sonuc doner; Storyline
            # arkada acilir ve acildiginda kendi satirini yazar.
            if reopen_after:
                _push_event({"kind": "medya",
                             "text": "Eklendi. Storyline arkada yeniden açılıyor…"})
                _arkada_ac(path)

    @guarded
    def skip_media(self, path: str, request_id: str) -> dict:
        istekler = medya.atla(path, request_id)
        return {"istekler": istekler, "bekleyen": medya.bekleyen_sayisi(istekler)}

    @guarded
    def add_image_to_slide(self, path: str, slide: str, x: float = 55,
                           y: float = 22, w: float = 38) -> dict | None:
        """Pick an image and place it on the slide, closing Storyline if needed."""
        chosen = webview.windows[0].create_file_dialog(
            getattr(webview, "FileDialog").OPEN if hasattr(webview, "FileDialog")
            else webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=("Gorsel (*.png;*.jpg;*.jpeg;*.gif)", "Tum dosyalar (*.*)"),
        )
        if not chosen:
            return None

        reopen_after = False
        if storyline_ctl.holds(path):
            _push_event({"kind": "step",
                         "text": "Storyline bu projeyi açık tutuyor — kaydedilip kapatılıyor…"})
            closed = storyline_ctl.save_and_close(path)
            if not closed.get("closed"):
                raise RuntimeError(closed.get("reason", "Storyline kapatılamadı."))
            reopen_after = True
        try:
            _guard(path)
            pkg = StoryPackage(path)
            result = media.add_image(pkg, slide, chosen[0], x=x, y=y, w=w)
            report = pkg.save(Path(path), backup=True)
            production.record(path, "add_image", report, {"slide": slide})
            return {**result, "verified": report["verified"]}
        finally:
            if reopen_after:
                storyline_ctl.reopen(path)

    # --------------------------------------------------------------- reads

    @guarded
    def quiz(self, path: str) -> list[dict]:
        return model.quiz(StoryPackage(path))

    @guarded
    def audit(self, path: str) -> dict:
        return audit(path)

    @guarded
    def search(self, path: str, query: str) -> list[dict]:
        runs = model.text_runs(StoryPackage(path))
        needle = query.casefold()
        return [
            {
                "addr": r.addr,
                "text": r.text,
                "slide": r.slide,
                "slide_name": r.slide_name,
                "scene": r.scene,
            }
            for r in runs
            if needle in r.text.casefold()
        ]

    # -------------------------------------------------------------- writes

    @guarded
    def preview(self, path: str, operations: list[dict]) -> dict:
        """Run the queue in memory and report the outcome without saving."""
        pkg = StoryPackage(path)
        results = [self._run_one(pkg, i, op) for i, op in enumerate(operations)]
        index = model.slide_index(pkg)
        return {
            "results": results,
            "resulting_slide_count": len(index),
            "resulting_scene_count": len({r.scene_name for r in index.values()}),
            "resulting_question_count": len(model.quiz(pkg)),
        }

    @guarded
    def apply(self, path: str, operations: list[dict], in_place: bool = False) -> dict:
        _guard(path)
        pkg = StoryPackage(path)
        results = [self._run_one(pkg, i, op) for i, op in enumerate(operations)]
        source = Path(path)
        target = source if in_place else source.with_suffix(".edited.story")
        report = pkg.save(target, backup=True)
        production.record(
            target,
            "apply",
            report,
            {"operation_count": len(operations), "in_place": in_place},
        )
        return {"results": results, **report}

    def _run_one(self, pkg: StoryPackage, index: int, op: dict) -> dict:
        try:
            return {"index": index, "op": op.get("op"), "ok": True, "result": _apply_op(pkg, op)}
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"{index + 1}. islem ({op.get('op')}) basarisiz: {exc}") from exc

    @guarded
    def replace_all(self, path: str, query: str, replacement: str, in_place: bool = False) -> dict:
        _guard(path)
        pkg = StoryPackage(path)
        needle = query.casefold()
        edits = [
            Edit(addr=r.addr, new_text=r.text.replace(query, replacement))
            for r in model.text_runs(pkg)
            if needle in r.text.casefold()
        ]
        if not edits:
            raise RuntimeError(f"{query!r} hicbir metinde bulunamadi.")
        result = apply_text_edits(pkg, edits)
        source = Path(path)
        target = source if in_place else source.with_suffix(".edited.story")
        report = pkg.save(target, backup=True)
        production.record(
            target,
            "replace_all",
            report,
            {"query": query[:50], "replacements": len(edits), "in_place": in_place},
        )
        return {**result, **report}

    # --------------------------------------------------------------- js capabilities

    @guarded
    def list_js_capabilities(self) -> dict:
        from storyline_mcp import jscat
        items = []
        for cap in jscat.KATALOG.values():
            items.append({
                "name": cap.ad,
                "title": cap.baslik,
                "description": cap.aciklama,
                "event": cap.olay,
                "watch": cap.izle,
                "limitations": cap.calismaz,
                "params": [
                    {
                        "name": p.ad,
                        "type": p.tur,
                        "description": p.aciklama,
                        "default": p.varsayilan,
                        "role": p.rol,
                        "vtype": p.vtur,
                        "options": list(p.secenekler),
                    }
                    for p in cap.parametreler
                ],
            })
        return {"capabilities": items}

    @guarded
    def add_js_capability(
        self, path: str, slide: str, capability: str,
        params: dict | None = None, event: str | None = None,
        in_place: bool = True,
    ) -> dict:
        from storyline_mcp import jscat
        _guard(path)
        pkg = StoryPackage(path)
        result = jscat.uygula(pkg, slide, capability, params=params, event=event)
        source = Path(path)
        target = source if in_place else source.with_suffix(".edited.story")
        report = pkg.save(target, backup=True)
        production.record(
            target,
            "add_js_capability",
            report,
            {"slide": slide, "capability": capability, "in_place": in_place},
        )
        return {**result, **report}

    @guarded
    def add_custom_js_trigger(
        self, path: str, slide: str, code: str,
        event: str = "OnStart", watch: str | None = None,
        in_place: bool = True,
    ) -> dict:
        from storyline_mcp import logic, jscheck
        _guard(path)
        pkg = StoryPackage(path)
        check = jscheck.check(code)
        if check.get("syntax_ok") is False:
            raise RuntimeError(f"JS sözdizimi hatası: {check.get('error')}")
        result = logic.add_trigger(
            pkg, slide, "execute_javascript", event=event, javascript=code, watch=watch
        )
        source = Path(path)
        target = source if in_place else source.with_suffix(".edited.story")
        report = pkg.save(target, backup=True)
        production.record(
            target,
            "add_custom_js_trigger",
            report,
            {"slide": slide, "event": event, "code_length": len(code), "in_place": in_place},
        )
        return {**result, **report}

    # --------------------------------------------------------------- donor pool

    @guarded
    def donor_status(self) -> dict:
        from storyline_mcp import donors
        return donors.summary()

    @guarded
    def open_donors_folder(self) -> dict:
        from storyline_mcp import donors
        folder = donors.pool_dir()
        folder.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(folder))
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(folder)])
        return {"opened": str(folder)}

    # --------------------------------------------------------------- agent

    @guarded
    def agent_available(self) -> dict:
        # TEK MOTOR. Panel bir sure find_cli_info() cagiriyordu ve o, hangi
        # CLI'ya dusuldugunu soyleyen bir "flavor" dondururdu -- Antigravity
        # (agy) yedegi icin. Yedek 2026-09-04'te SOKULDU (gerekcesi
        # agent.find_cli'nin belge dizesinde: agy, panelin dayandigi MCP arac
        # yuzeyini hic tasimiyordu, yani oraya dusen kosu hicbir sey
        # uretmiyordu) ama BU CAGRI GERIDE KALDI ve panel hic acilmaz oldu:
        # ImportError, pythonw altinda hicbir yere dusmez -- cift tiklayan
        # kullanici HICBIR SEY gorur.
        cli = find_cli()
        return {"available": cli is not None,
                "path": str(cli) if cli else None}

    @guarded
    def run_command(
        self, path: str, command: str, model: str = "sonnet",
        auto_cycle: bool = True, palette: dict | None = None,
    ) -> str:
        global _ACTIVE_RUN
        if not command.strip():
            raise RuntimeError("Komut bos.")
        if find_cli() is None:
            # Mesaj da yedekle birlikte gitti: olmayan bir ikinci motoru
            # aramaya cagirmak, kullaniciyi bulunamayacak bir sey aramaya
            # yollar.
            raise RuntimeError("Claude Code CLI bulunamadi.")
        if _ACTIVE_RUN and _ACTIVE_RUN.process and _ACTIVE_RUN.process.poll() is None:
            raise RuntimeError("Zaten calisan bir komut var.")

        _acilisi_bekle()
        _SON_YOL[0] = path
        _ACTIVE_RUN = AgentRun(path, command.strip(), _push_event, model=model,
                               palette=palette, resume=_OTURUM.get(path))
        threading.Thread(
            target=_orchestrate, args=(_ACTIVE_RUN, path, auto_cycle), daemon=True
        ).start()
        return "started"

    @guarded
    def build_course(self, path: str, brief: str, model: str = "sonnet",
                     options: dict | None = None) -> str:
        """Design and build a whole course from a brief, in the background.

        options is the setup collected once: title, audience, goal, minutes,
        sections, questions_per_section, tone, accent/bg colours.
        """
        if not brief.strip():
            raise RuntimeError("Brief bos.")
        if find_cli() is None:
            raise RuntimeError("Claude Code CLI bulunamadi.")
        _acilisi_bekle()
        threading.Thread(
            target=_run_builder,
            args=(path, brief.strip(), model, options or {}),
            daemon=True,
        ).start()
        return "started"

    @guarded
    def cancel_command(self) -> str:
        if _ACTIVE_RUN:
            _ACTIVE_RUN.cancel()
        return "cancelled"

    # --------------------------------------------------------------- shell

    @guarded
    def open_in_storyline(self, path: str) -> str:
        os.startfile(path)  # noqa: S606 - .story is registered to Storyline
        return path

    @guarded
    def reveal(self, path: str) -> str:
        os.startfile(str(Path(path).parent))  # noqa: S606
        return str(Path(path).parent)

    # --------------------------------------------------------------- production log

    @guarded
    def production_log(self, count: int = 20) -> dict:
        """Retrieve the most recent save operations and their validation results."""
        return {
            "entries": production.latest(count),
            "summary": production.summary(),
        }

    @guarded
    def production_log_text(self, count: int = 20) -> str:
        """Retrieve production log as human-readable text."""
        entries = production.latest(count)
        if not entries:
            return "Henüz üretim günlüğü yok."
        lines = ["Üretim Günlüğü (en yeni ilk):", ""]
        for entry in reversed(entries):
            lines.append(production.format_entry(entry))
        return "\n".join(lines)


def main() -> None:
    webview.create_window(
        "Storyline Panel",
        str(HERE / "index.html"),
        js_api=Api(),
        width=1180,
        height=820,
        min_size=(920, 640),
    )
    webview.start()


if __name__ == "__main__":
    main()
