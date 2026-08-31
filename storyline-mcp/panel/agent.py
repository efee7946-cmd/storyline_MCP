"""Natural-language commands, executed by Claude Code in headless mode.

The panel does not talk to the Anthropic API directly. It drives the Claude
Code CLI that ships inside the VS Code extension, which is already
authenticated -- so there is no second API key to obtain and no second bill.
Runs still draw on the same Claude usage allowance as any other Claude Code
session.

The CLI is launched with --strict-mcp-config and an allow-list naming only the
storyline tools. That means the agent reaches this project's .story operations
and nothing else: no shell, no file writes, no network. In headless mode there
is nobody to answer a permission prompt, so anything outside the allow-list is
denied rather than queued -- the restriction is enforced, not advisory.

Output is streamed as newline-delimited JSON and pushed into the page as it
arrives, so a long build reports progress instead of freezing.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

SERVER_EXE = Path(__file__).resolve().parent.parent / ".venv" / "Scripts" / "storyline-mcp.exe"

EXTENSION_GLOB = "anthropic.claude-code-*/resources/native-binary/claude.exe"
VERSION_RE = re.compile(r"claude-code-(\d+)\.(\d+)\.(\d+)")


def find_claude_cli() -> Path | None:
    on_path = shutil.which("claude")
    if on_path:
        return Path(on_path)

    candidates = sorted(
        (Path.home() / ".vscode" / "extensions").glob(EXTENSION_GLOB),
        key=lambda p: (
            tuple(int(g) for g in VERSION_RE.search(str(p)).groups())
            if VERSION_RE.search(str(p)) else (0, 0, 0)
        ),
        reverse=True,
    )
    for path in candidates:
        if path.is_file():
            return path

    for extra in (
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "claude" / "claude.exe",
        Path.home() / ".local" / "bin" / "claude.exe",
    ):
        if extra.is_file():
            return extra
    return None


def find_agy_cli() -> Path | None:
    on_path = shutil.which("agy") or shutil.which("antigravity")
    if on_path:
        return Path(on_path)

    for extra in (
        Path(os.environ.get("LOCALAPPDATA", "")) / "agy" / "bin" / "agy.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Antigravity" / "bin" / "antigravity.cmd",
        Path.home() / ".local" / "bin" / "agy",
    ):
        if extra.is_file():
            return extra
    return None


_CLAUDE_DISABLED: bool = False


def disable_claude_cli() -> None:
    global _CLAUDE_DISABLED
    _CLAUDE_DISABLED = True


def is_claude_disabled() -> bool:
    return _CLAUDE_DISABLED


def find_cli_info() -> tuple[Path, str] | tuple[None, None]:
    """Locate available CLI: Claude Code first (if operational), Antigravity (agy) fallback second."""
    if not _CLAUDE_DISABLED:
        claude = find_claude_cli()
        if claude:
            return claude, "claude"
    agy = find_agy_cli()
    if agy:
        return agy, "agy"
    claude = find_claude_cli()
    if claude:
        return claude, "claude"
    return None, None


def find_cli() -> Path | None:
    path, _ = find_cli_info()
    return path

TOOLS = [
    "story_info", "list_slides", "extract_text", "search_text",
    "list_variables", "list_triggers", "list_quiz", "list_templates", "audit",
    "question_formats",
    "update_text", "add_scene", "add_slide", "add_question",
    "add_drag_question", "add_text_question", "add_hotspot_question",
    "duplicate_slide", "build_course",
    "compose_slide",
    "set_background", "add_text_box", "add_button", "add_shape",
    "restyle_text", "add_image", "add_video", "request_media",
    "add_results_slide",
    "theme", "set_theme_colors", "set_theme_font",
    "slide_layout",
    "slide_properties", "set_slide_properties", "story_size", "set_story_size",
    "list_player_colors", "set_player_color",
    "list_button_states", "set_button_state",
    "list_layers", "add_layer",
    "add_variable", "add_trigger",
    # JS yetenekleri. Bunlar bir sure MCP'de VARDI ama izin listesinde YOKTU,
    # yani `--strict-mcp-config` altinda ajan onlari hic cagiramiyordu --
    # arac vardi, tek gercek cagiran ona ulasamiyordu.
    "list_js_capabilities", "add_js_capability", "check_javascript",
]
TOOL_PREFIX = "mcp__storyline__"
ALLOWED = [f"{TOOL_PREFIX}{name}" for name in TOOLS]

# Substituted with str.replace, not str.format: the prompt contains literal
# JSON braces as examples, and format() reads those as placeholders and raises
# KeyError before the CLI is ever launched -- a command that simply never runs.
import ogretim

PATH_TOKEN = "__STORY_PATH__"

SYSTEM_PROMPT = """\
Sen bir Articulate Storyline yardimcisisin. Kullanicinin komutlarini storyline \
MCP araclariyla yerine getirirsin. Turkce ve kisa yanit ver.

Uzerinde calisilan dosya: __STORY_PATH__

Kurallar:
- YALNIZCA storyline araclarini kullan. Kabuk (Bash/PowerShell), dosya okuma \
yazma, arsiv acma, kod derleme gibi araclar bu oturumda kapalidir; denemek \
bosa tur harcar. Bir isi storyline araclariyla yapamiyorsan yapamadigini soyle.
- Her arac cagrisinda path olarak bu dosyayi kullan.
- Yazma yapan her cagrida in_place=true ver. output_path VERME ve yeni bir \
dosya adi uydurma. Butun degisiklikler bu tek dosyaya islenir; arac her \
yazmadan once otomatik .bak yedegi alir.
- Once oku, sonra yaz. Yapiyi bilmeden degistirme: list_slides, list_templates \
veya extract_text ile durumu gor.
- JS GEREKEN ISLERDE ONCE KATALOGA BAK. Storyline'in kendi tetikleyicilerinin yapamadigi seyler (tarih/saat yazma, rastgele sayi, Turkce sayi bicimi, Turkce metin karsilastirma, kayipsiz sayac, sayi tasmasi uyarisi) icin `list_js_capabilities` ile bak ve `add_js_capability` ile ekle. Her yetenegin yaninda NASIL OLCULDUGU ve NE ZAMAN CALISMADIGI yazili; eklemeden once "ne zaman calismaz" satirini oku ve kursa uymuyorsa ekleme.
- KENDILIGINDEN JS SERPME. Yetenegi yalnizca kullanicinin istedigi is onu gerektiriyorsa ekle -- ornegin kapanis/sertifika slaydinda tamamlama tarihi, ya da sorulari rastgelelestirme. Istenmeden eklenen bir JS tetikleyicisi kullaniciyi sasirtir.
- HAM JS SON CARE. Katalogda karsiligi yoksa ham kod yazabilirsin, ama once `check_javascript` ile denetle ve temiz cikmadan `add_trigger` ile yazma. Denetim SOZCUKSELDIR: kod parse ediyor ve degisken adlari cozuluyor olsa bile yanlis isi yapiyor olabilir.
- SAYI HASSASIYETI. Storyline'in sayi degiskeni 7 anlamli basamak tasiyor ve otesi SESSIZCE kaybolur (olculdu). Biriken sayac gerekiyorsa `adjust_variable` yerine `sayac` yetenegini kullan; JS tarafi kayipsiz.
- Puanli soru icin add_question kullan ve **template parametresini verme**. \
Bos birakinca uygun kaynak kendiliginden secilir; dosyada hic soru slaydi \
olmasa bile araca gomulu ornekten uretilir. Sablon adi uydurma.
- Ondan once question_formats cagir: kullanilabilir secenek sayilarini soyler \
(orn. tek dogru 2 secenek, cok dogru 5 secenek). Sorulari o sayilara gore yaz; \
baska sayida secenek verirsen arac reddeder.
- Soru slaydi bulamadin diye buton tabanli sahte soru kurma; puanli soru \
kurulabiliyor.
- add_question'a HER ZAMAN sunlari ver: eyebrow (bolumun adi), theme \
(compose_slide ile AYNI tema) ve feedback. Dosyada soru slaydi yoksa araca \
gomulu ornek kullanilir; o ornek baska bir kursun bolum adini, rengini ve \
geri bildirim metnini tasir. Bu ucu verilmezse ogrenci yanlis bolum adini \
ve baska bir kursun aciklamasini gorur.
- feedback={"correct": ..., "incorrect": ...}: \
ogrenci cevabini verdikten sonra okuyacagi metin. Bos bir onay degil, \
kararin GEREKCESI olsun -- tek cumle.
- Birden fazla degisiklik gerekiyorsa tek tek degil build_course ile tek \
geciste uygula; boylece dosya bir kez yazilir.
- Buyuk bir brief geldiginde (cok konulu bir kurs, "su 6 basligi isle" gibi) \
hepsini tek turda bitirmeye calisma. Once iskeleti kur: gereken sahneleri ve \
slaytlari olustur, her slaydin basligini yaz. Sonra en fazla 2-3 slaydin \
icerigini doldur ve DUR; ne yaptigini, hangi slaytlarin bos kaldigini ve \
devam icin ne yazmasi gerektigini kullaniciya soyle. Yarim kalmis bir kurs \
teslim etmek, saatlerce calisip sessiz kalmaktan iyidir.
- Isin sonunda ne yaptigini tek cumleyle bildir. Dosya yolunu tekrar yazma.

Ogretim tasarimi (sayfayi kurmadan ONCE bunu kur):
__OGRETIM_KURALLARI__
- ISI BITIRMEDEN ONCE audit CAGIR. Iki alana bak: sorusuz_sahneler bos mu,
ardisik_etkilesimsiz_slayt 3'ten kucuk mu. Degilse ya duzelt ya da hangi
sahnenin acik kaldigini kullaniciya SOYLE. Kursu yarim teslim etmek serbest;
olcumu atlamak degil.
- SORU ISTENMEMIS EKLENTI DEGILDIR. Yukaridaki "kendiliginden JS serpme" kurali
JS'e ozgudur; olcme kursun tanimina dahildir ve ayrica istenmesi gerekmez.

Sayfa tasarimi:
- Bir slayt kurarken ONCE compose_slide kullan. Kenar boslugu, punto olcegi,
dikey ritim ve vurgu rengi bu araca gomulu; compose_slide'in ZATEN SUNDUGU bir
duzeni elle metin kutusu dizerek taklit edersen sonuc amatorce gorunur.
- Bu kural ETKILESIM kurmayi KAPSAMAZ. add_question kendi basina tam bir slayt
aracidir, add_layer'in da compose_slide'da karsiligi yoktur: asagidaki yedi
duzenin yedisi de SUNUM duzenidir. Etkilesim gerekiyorsa compose_slide'in
disina cikmak dogrudur, amatorluk degildir.
     compose_slide(slide, layout, title, eyebrow, body, bullets, buttons)
     layout: cover | section | content | bullets | steps | statement | menu
- Bir kursun tum slaytlarinda ayni theme'i kullan; boylece kurs tek bir dile
sahip olur. theme: gece, kagit, komur, orman, sis, murdum. Her temanin zemini
ayridir ve zemin slaydin neredeyse tamami demektir -- iki kursu birbirinden
ayiran en guclu sey tema secimidir, vurgu rengi degil.
- brand="#RRGGBB" yalnizca marka rengi zorunluysa. Zemini markadan hesaplar ve
marka koyuysa yazi zemine karisabilir; mumkunse theme kullan.
- eyebrow kisa bir ust etikettir (bolum adi, kategori). Baslik kisa olsun,
aciklamayi body'ye yaz.
- Maddeler icin bullets kullan, body icine tire koyup liste yapma.
- Duzenleri DEGISTIREREK ilerle. Ard arda ayni layout, kursu tek bir uzun
sayfaya cevirir: bolum baslangicinda section, agir bir fikirde statement,
sirali anlatimda steps kullan.
- Ayni layout'u tekrar kullanman gerekiyorsa VARYANTINI degistir. avoid_variant
parametresine bir onceki slaydin varyantini ver (compose_slide'in donusundeki
'variant' alani). Ayni varyanti tasiyan iki komsu slayt ayni siluete sahip
olur; layout adi farkli olsa bile goz onu "ayni sayfa" olarak okur. Varyant
metnin nerede basladigini, basligin kendi seridi olup olmadigini, maddelerin
basligin ustunde mi altinda mi durdugunu degistirir -- rengi degil.
- style ile variant ayni sey degil: style kurs boyunca SABIT kalir (kursu
digerlerinden ayirir), variant her slaytta DEGISIR (slayti bir oncekinden
ayirir).

Gorsel kullanimi (kaliteyi en cok bu yukseltir):
- Elinde bir gorsel varsa compose_slide'i image_area=true ile cagir ve
image_style sec:
     hero  - kapakta: gorsel tum slayti kaplar, uzerine okunabilirlik ortusu
     bleed - ic slaytlarda: sag kenardan tasan tam boy blok, yazi solda
     panel - guvenli varsayilan: sag sutunda kart
- compose_slide'in donusundeki image_area alanini aynen add_image'e gecir:
x/y/w/h oradan gelir. hero'da behind=true de gelir, onu da ilet.
- hero ve bleed'de fit="cover" ver: alan dolar ve fazlalik ortadan
kirpilir. stretch VERME -- oran bozulur ve bozulmayi ancak dosyayi acan
insan gorur.
- Gorselin olmadigi yerde image_area=true VERME; bos bir blok kalir --
TEK istisna asagidaki siparis yolu: alani ayirip request_media ile isteyeceksen
image_area=true VER, cunku dosya tam oraya gelecek.

Elinde dosya YOKKEN gorsel/video (bu yol yeni, kullan):
- add_image ve add_video DISKTEKI bir dosyayi alir. Dosya yoksa "yapilamiyor"
DEME ve sessizce vazgecme: request_media ile SIPARIS birak. Istek panelin
"Gorsel & Video" sekmesinde kullaniciya cikar, dosyayi o verir ve panel senin
ayirdigin alana koyar.
- Sirasi: compose_slide(image_area=true, image_style=...) -> donen image_area
ile request_media(kind, brief, area, style). Var olan bir slayda dokunmadan
istiyorsan once slide_layout ile bos alana bak, area'yi oradan ver.
- brief bir SIPARIStir: cerceve ne gostersin, kim/ne var, hangi an. "guvenlik
gorseli" degil; "telefon ekraninda dogrulama bildirimi, parmak onay tusunun
uzerinde". Gorselin USTUNDE YAZI isteme.
- Videoda saniye ver (10-60). Video dosyasi elindeyse add_video ile koy: mp4/m4v,
sure ve oran dosyanin icinden okunur.
- Siparis birakinca kullaniciya SOYLE: hangi slayt, ne istedin, nereden
verecek.

Ince ayar (compose_slide yetmediginde):
- Yeni bir sayfa tasarlarken once add_slide ile bir icerik slaydi olustur, ama \
title parametresini VERME; basligi sonra add_text_box ile koy. Boylece yazi \
sablondaki bir butonun uzerine yazilmaz.
- Sablonu list_templates ciktisindan sec ve kind="content" olanlardan, \
text_shapes degeri en az 1 olan sade bir slayt tercih et. Cok butonlu menu \
slaytlarini sablon olarak kullanma.
- set_background arka plani kaplar, add_text_box metin ekler, add_button buton \
ekler, restyle_text mevcut yazilarin rengini/boyutunu degistirir.
- Bu araclarda x/y/w/h slaydin YUZDESIdir (0-100), piksel degildir.
- add_text_box'a **h VERME**. Kutu metnin uzunluguna gore kendi boyutlanir; \
sabit yukseklik verirsen uzun paragraf tasar ve kirpilir.
- Bir slayda birden fazla sekil koyacaksan **once slide_layout ile bak**: \
neyin nerede oldugunu gormeden verilen koordinatlar ust uste biner.
- Sayfayi yukaridan asagi kur ve seritler halinde dusun:
     ust etiket   y=8    h~6
     baslik       y=16
     govde metni  y=34
     butonlar     y=78 (yan yana: x=8, x=32, x=56 gibi w=20)
- Butonlari her zaman metinlerin ALTINA koy, ustune degil. Basligi butonlardan \
once ve daha yukari yerlestir.
- Uzun paragraf icin punto 16-20, baslik icin 30-40 uygundur. Govde metnini \
align="l" ile sola yasla; ortalanmis uzun paragraf okunmaz.
- Donen sonuctaki 'box_percent' seklin gercek konumudur ve \
'placed_without_overlap' false ise yer bulunamamis demektir: o zaman duzeni \
yeniden dusun, uzerine yigma.
- Renkler '#RRGGBB'. Once set_background, sonra metinler, en son buton ekle.
- Slaytta metin kutusu olmamasi engel DEGILDIR: araclar gerekli sekli projeden \
bulamazsa gomulu bir ornekten uretir. Kullanicidan asla Storyline'da elle sekil \
olusturmasini isteme; istenen sayfayi dogrudan kur.

Ayar ve etkilesim:
- Slide Properties icin set_slide_properties: advance_by_user=true kullanicinin \
tiklamasini bekletir, prev/next=false o slaytta geri/ileri dugmelerini kapatir, \
hide_from_menu menuden gizler.
- Proje boyutu set_story_size (orn. 1920x1080). Mevcut sekiller kendi \
koordinatlarini korur.
- Player renkleri: once list_player_colors ile ad ve gruplari gor, sonra \
set_player_color. Ayni ad birden cok grupta olabilir; tek grubu degistirmek \
istiyorsan group parametresini ver. alpha 0-100 seffaflik demektir.
- Buton hover/down gorunumu: list_button_states ile state adlarini gor, sonra \
set_button_state (button olarak butonun uzerindeki metni verebilirsin).
- Gorsel eklemek icin add_image kullan; yol diskteki bir dosya olmali \
(png/jpg/gif). Yukseklik gorselin en-boy oranindan hesaplanir, sen sadece \
x/y/w ver. Internetten gorsel indiremezsin.
- Panel, kart, ayirac gibi parcalar icin add_shape: rect, roundRect, oval, \
line, textBox. Tasarimin govdesi bunlardir.
- Buton baska bir bolume gitsin istiyorsan target_scene, bulundugu katmani \
kapatsin istiyorsan closes_layer=true ver.
- Kursun genel rengini/fontunu degistirmek icin set_theme_colors ve \
set_theme_font kullan; tek tek sekil boyamaktan daha tutarli sonuc verir. \
Yuvalar: accent1..accent6, dk1, lt1, dk2, lt2.
- Puanli soru iceren her kurs add_results_slide ile BITER; yalnizca istenirse \
degil, cunku tamamlama ekrani olmadan ogrencinin nerede durdugu gorunmez. \
Kullaniciya "sonuc slaydi eklendi" de, "puanliyor" DEME: puanlamanin dogru \
calistigi yayinlanmadan dogrulanamaz.

- Katman bir OGRETIM aracidir, sadece popup degil: tiklayinca acilan bir \
aciklama, vaka detayi ya da "neden boyle?" cevabi. Anlatimi bolmeden ogrenciye \
karar verdiren en ucuz yol budur.
     add_layer(slide, name, text, open_from=<seklin uzerindeki metin>)
Slaydin katmani olmasi gerekmez; hic katmani olmayan bir slayda da ilk katman \
eklenebilir. open_from verilen sekle tiklaninca katman acilir.
- Katmanin ICINE add_shape veya add_text_box ile sekil KONULAMAZ; ikisi de \
slayta yazar. Katmanin icerigi add_layer'in text alanidir. Puanlama da \
katmanda degil SLAYTTA kurulur: once add_variable ile sayac, sonra ayni sekle \
add_trigger(action="adjust_variable", operation="add", value="1"), en son \
conditions ile esigi yorumlayan kosullu bir adim.

Degisken ve mantik:
- add_variable ile sayac, bayrak veya isim degiskeni olusturabilirsin \
(kind: num | text | bool). Ad harf/alt cizgi ile baslamali, bosluk ve Turkce \
karakter icermemeli.
- add_trigger ile tetikleyici kurarsin:
     adjust_variable  degiskeni degistirir (operation: set | add, value)
     jump_slide       hedef verilmezse sonraki slayda
     jump_scene       target_scene adiyla baska bolume
     show_layer / hide_layer   katman ac/kapat
     change_state     sekli baska bir state'e cevirir
- Kosul icin conditions ver: [{"variable":"Skor","op":"gte","value":6}]
  op: eq, noteq, gt, gte, lt, lte. Boylece kilit mantigi, esik ve dallanma
  kurulur ("6 dogru varsa sinava atla", "5 hotspot tiklanmadan ileri acilmaz").
- shape verilmezse tetikleyici slaydin kendisine baglanir; OnStart icin uygundur.
- Sayac kurarken once add_variable, sonra dogru cevap butonuna adjust_variable,
  en son kosullu jump ekle. Sirasi budur.

Su an YAPILAMAYANLAR (istenirse acikca soyle, uydurma):
- Internetten gorsel/video indirme, ve gorsel/video URETME. add_image ve
add_video DISKTEKI bir dosyayi alir. Dosya yoksa dogru cevap "yapilamiyor"
degil, request_media ile siparis birakmaktir.
- Timeline animasyonlari (62 dosya tarandi, klonlanacak calisan ornek yok).
- Soru bankasi (Question Bank) yapilari. Desteklenen soru tipleri: Tek/Cok Secmeli (add_question), Surukle-Birak (add_drag_question), Metin Girisi (add_text_question) ve Sicak Nokta (add_hotspot_question).
"""

# Ortak ogretim kurallari TEK YERDE durur (panel/ogretim.py) ve iki uretici de
# ayni metni alir: bu prompt ve builder.py. Bir sure ayri yazilmislardi ve
# kurallar sessizce ayristi -- "asagidakilerden hangisi kaliplarindan kacin"
# yalnizca builder tarafinda kalmisti, komut yolundan cikan kursta iki soru
# dogru/yanlis geri cagirmaya coktu (olculdu 2026-08-28).
#
# replace, format DEGIL: yukaridaki metin literal JSON suslu parantezi tasiyor.
SYSTEM_PROMPT = SYSTEM_PROMPT.replace(
    "__OGRETIM_KURALLARI__", ogretim.ORTAK_KURALLAR)


def _mcp_config() -> Path:
    config = {
        "mcpServers": {
            "storyline": {"type": "stdio", "command": str(SERVER_EXE), "args": [], "env": {}}
        }
    }
    handle = tempfile.NamedTemporaryFile(
        "w", suffix=".mcp.json", delete=False, encoding="utf-8"
    )
    json.dump(config, handle)
    handle.close()
    return Path(handle.name)


class AgentRun:
    """One command execution. Streams events to `on_event` until it finishes."""

    def __init__(
        self,
        story_path: str,
        command: str,
        on_event,
        model: str = "sonnet",
        output_path: str | None = None,
        palette: dict | None = None,
        resume: str | None = None,
    ):
        # Onceki komutun oturumu. Verilmezse her komut SIFIRDAN baslar ve
        # onceki alisverisi hic gormez -- olculdu: ajan "hangi slayt?" diye
        # sorup kullanici "2" deyince, bu kez ILK istegi (arka plani duzelt)
        # bilmeden "2. slaytla ilgili ne istiyorsun?" diye geri soruyordu.
        self.resume = resume
        # CLI'nin verdigi oturum kimligi; bir sonraki komut bununla devam eder.
        self.session_id: str | None = None
        # "final" gorulduyse is yapilmistir; sifir disi cikis kodu
        # tek basina "hicbir sey olmadi" demek degildir.
        self._final_gorundu = False
        # Carried into the prompt so a slide added by a single command matches
        # the palette the rest of the course was built with.
        self.palette = palette or {}
        self.story_path = story_path
        # Commands edit the selected file in place. Writing each result to a
        # new ".edited" file meant the next command took that file as input and
        # produced ".edited.edited", so the name grew a layer per instruction
        # and the project scattered across near-identical copies. The engine
        # takes a .bak before every in-place write, so undo survives.
        self.output_path = output_path or story_path
        self.command = command
        self.model = model
        self.on_event = on_event
        self.process: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        # tool_use ids belonging to Storyline calls, so their results can be
        # told apart from those of tools the allow-list refuses.
        self._ours: set[str] = set()

    def _palette_note(self) -> str:
        """Tell the agent the deck's colours, so a new slide is not an orphan."""
        bg, accent = self.palette.get("bg"), self.palette.get("accent")
        if not (bg or accent):
            return ""
        pairs = ", ".join(f'"{k}":"{v}"' for k, v in
                          (("bg", bg), ("accent", accent)) if v)
        return (f"\n\nBu kursun paleti: {{{pairs}}}. compose_slide, set_background "
                f"ve add_button cagirirken bu renkleri kullan; kullanici baska bir "
                f"renk istemedikce degistirme.")

    def run_sync(self) -> None:
        """Run on the calling thread.

        The caller owns the lifecycle -- it may need to close Storyline before
        this runs and reopen it afterwards -- so this does not emit the "done"
        event that ends the run in the UI.
        """
        self._run()

    def cancel(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()

    def _run(self) -> None:
        config: Path | None = None
        try:
            cli, flavor = find_cli_info()
            if cli is None:
                raise RuntimeError("Ne Claude Code CLI ne de Antigravity (agy) CLI bulunamadi.")

            sys_prompt = (
                SYSTEM_PROMPT.replace(PATH_TOKEN, self.story_path)
                + self._palette_note()
            )

            if flavor == "claude":
                config = _mcp_config()
                argv = [
                    str(cli), "-p", self.command,
                    "--mcp-config", str(config),
                    "--strict-mcp-config",
                    "--allowedTools", *ALLOWED,
                    "--output-format", "stream-json",
                    "--verbose",
                    "--model", self.model,
                    "--append-system-prompt", sys_prompt,
                ]
                if self.resume:
                    argv[2:2] = ["--resume", self.resume]
            else:
                # Antigravity (agy) CLI fallback
                full_prompt = f"System instructions:\n{sys_prompt}\n\nUser command:\n{self.command}"
                argv = [
                    str(cli), "-p", full_prompt,
                    "--output-format", "stream-json",
                    "--dangerously-skip-permissions",
                ]

            code, stderr = self._kos(argv)

            if code != 0 and self.resume and not self._final_gorundu and flavor == "claude":
                self.on_event({
                    "kind": "step",
                    "text": "Onceki komutun baglami suruyordu ama acilamadi; "
                            "komut baglamsiz yeniden calistiriliyor.",
                })
                self.resume = None
                temiz, atla = [], False
                for a in argv:
                    if atla:
                        atla = False
                        continue
                    if a == "--resume":
                        atla = True
                        continue
                    temiz.append(a)
                argv = temiz
                code, stderr = self._kos(argv)

            # RUNTIME LIMIT / FAILURE FALLBACK TO ANTIGRAVITY (AGY)
            if code != 0 and flavor == "claude" and not self._final_gorundu:
                disable_claude_cli()
                agy_cli = find_agy_cli()
                if agy_cli:
                    err_msg = (stderr or "").strip()
                    self.on_event({
                        "kind": "step",
                        "text": f"Claude Code erişimi engellendi/limit doldu — Otomatik olarak Antigravity (agy) CLI fallback'ine geçiliyor...",
                    })
                    full_prompt = f"System instructions:\n{sys_prompt}\n\nUser command:\n{self.command}"
                    argv = [
                        str(agy_cli), "-p", full_prompt,
                        "--output-format", "stream-json",
                        "--dangerously-skip-permissions",
                    ]
                    code, stderr = self._kos(argv)

            if code != 0:
                self.on_event({
                    "kind": "error",
                    "text": stderr or f"Komut {code} kodu ile sonlandi.",
                })
        except Exception as exc:  # noqa: BLE001
            self.on_event({"kind": "error", "text": f"{type(exc).__name__}: {exc}"})
        finally:
            if config is not None:
                config.unlink(missing_ok=True)

    def _kos(self, argv: list[str]) -> tuple[int, str]:
        """CLI'yi calistir, akisi olaylara cevir, (cikis kodu, stderr) dondur."""
        self.process = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(Path(self.story_path).parent),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        for line in self.process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                self._dispatch(json.loads(line))
            except json.JSONDecodeError:
                continue
        code = self.process.wait()
        return code, (self.process.stderr.read() or "").strip()

    def _dispatch(self, event: dict) -> None:
        """Translate the CLI's stream into something the page can render."""
        # Handle agy stream-json format
        if "event" in event:
            evt_name = event.get("event")
            if evt_name == "step_update":
                step = event.get("step_update", {})
                if step.get("step_type") == "agent_response":
                    text_delta = step.get("text_delta", "").strip()
                    if text_delta:
                        self.on_event({"kind": "text", "text": text_delta})
                elif step.get("step_type") == "tool_call":
                    tool_calls = step.get("tool_calls", [])
                    for call in tool_calls:
                        name = call.get("name", "")
                        self.on_event({
                            "kind": "tool",
                            "name": name.replace(TOOL_PREFIX, ""),
                            "input": self._brief(call.get("args", {})),
                        })
            elif evt_name == "result":
                self._final_gorundu = True
                res = event.get("result", {})
                resp_text = res.get("response", "") or res.get("result", "")
                written = Path(self.output_path)
                self.on_event({
                    "kind": "final",
                    "error": res.get("status") == "ERROR",
                    "text": resp_text,
                    "duration_ms": int(res.get("duration_seconds", 0) * 1000),
                    "turns": res.get("num_turns"),
                    "output_path": str(written) if written.exists() else None,
                    "session_id": res.get("conversation_id"),
                })
            return

        kind = event.get("type")
        # Her olayda gelebilir; sonuncusu tutulur.
        if event.get("session_id"):
            self.session_id = event["session_id"]

        if kind == "assistant":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "text" and block.get("text", "").strip():
                    self.on_event({"kind": "text", "text": block["text"].strip()})
                elif block.get("type") == "tool_use":
                    name = str(block.get("name", ""))
                    # The CLI's own plumbing -- tool lookups and the like -- is
                    # not work the reader asked for. Only Storyline operations
                    # are reported.
                    if not name.startswith(TOOL_PREFIX):
                        continue
                    self._ours.add(block.get("id"))
                    self.on_event({
                        "kind": "tool",
                        "name": name.replace(TOOL_PREFIX, ""),
                        "input": self._brief(block.get("input", {})),
                    })

        elif kind == "user":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") != "tool_result":
                    continue
                # Successful results are long JSON dumps that say nothing a
                # person needs; the step already showed what ran. Failures are
                # surfaced -- but only for Storyline operations. Everything
                # else that fails here is the allow-list refusing a shell or
                # archive call, which is the restriction working as designed,
                # not a problem for the reader to act on.
                if block.get("is_error") and block.get("tool_use_id") in self._ours:
                    self.on_event({
                        "kind": "result",
                        "error": True,
                        "text": self._summarise(block.get("content")),
                    })

        elif kind == "result":
            self._final_gorundu = True
            written = Path(self.output_path)
            self.on_event({
                "kind": "final",
                "error": bool(event.get("is_error")),
                "text": event.get("result", ""),
                "duration_ms": event.get("duration_ms"),
                "turns": event.get("num_turns"),
                "output_path": str(written) if written.exists() else None,
                "session_id": self.session_id,
            })

    @staticmethod
    def _brief(payload: dict) -> str:
        parts = []
        for key, value in payload.items():
            if key == "path":
                continue
            text = ", ".join(map(str, value)) if isinstance(value, list) else str(value)
            parts.append(f"{key}={text[:60]}")
        return " · ".join(parts)[:180]

    @staticmethod
    def _summarise(content) -> str:
        if isinstance(content, list):
            content = " ".join(
                b.get("text", "") for b in content if isinstance(b, dict)
            )
        text = str(content or "").strip().replace("\n", " ")
        return text[:220]
