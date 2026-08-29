"""Is a capability reachable everywhere it needs to be?

Four times this session a capability existed in the engine and could not be
reached: a tool missing from the allow-list, a restriction left in the prompt
after the code dropped it, a required argument that hid the default path, and a
parameter the engine accepted but the tool did not expose. Comparing tool names
alone caught only the first kind, so parameters are compared too.
"""
import ast, asyncio, inspect, sys, textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "panel"))
from storyline_mcp import authoring, compose, media, server, settings
import agent

# Plumbing, not interface. The check asks "can the agent reach every feature?",
# so a parameter the agent must NOT set is not a gap.
#
# identity names the course for donor selection. Exposing it per call would
# hand the agent the one thing the design forbids -- choosing a different
# button on each slide, which scatters a deck across four button languages.
# It is set once, by the builder, and defaults to the project file name.
# slot: bir yigin icindeki butonun buyume yuvasi. Kompozisyon yigini kurarken
# kendisi hesaplar; ajana acmak, butonlarin birbirine binmesini ajanin
# sorumlulugu yapmak olurdu.
PLUMBING = {"pkg", "identity", "slot"}

tools = {t.name for t in asyncio.run(server.mcp.list_tools())}
allowed = set(agent.TOOLS)
print(f"  MCP araci      : {len(tools)}")
print(f"  izin listesi   : {len(allowed)}")
print(f"  izinde olmayan : {sorted(tools - allowed) or 'yok'}")
print(f"  kodda olmayan  : {sorted(allowed - tools) or 'yok'}")

# The engine function behind each tool, where the names line up.
PAIRS = [
    ("compose_slide", compose.compose_slide, {"slide", "layout"}),
    ("add_question", authoring.add_question, {"prompt", "choices", "correct"}),
    ("add_text_box", authoring.add_text_box, {"slide", "text"}),
    ("add_button", authoring.add_button, {"slide", "text"}),
    ("add_image", media.add_image, {"slide", "image"}),
    ("add_layer", authoring.add_layer, {"slide", "name"}),
    ("set_slide_properties", settings.set_slide_properties, {"slide"}),
]
print("\n=== MOTOR PARAMETRELERI ARAYUZDE ACIK MI ===")
gaps = 0
for name, engine, skip in PAIRS:
    tool = getattr(server, name, None)
    if tool is None:
        print(f"  {name:<22} arac yok")
        continue
    engine_params = set(inspect.signature(engine).parameters) - skip - PLUMBING
    tool_params = set(inspect.signature(tool).parameters)
    missing = sorted(p for p in engine_params if p not in tool_params)
    print(f"  {name:<22} {'TAMAM' if not missing else 'EKSIK: ' + ', '.join(missing)}")
    gaps += len(missing)

# DORDUNCU KONTROL: parametre ILETILIYOR mu, yoksa yalnizca duruyor mu.
#
# Ilk uc ayak "motorda var mi", "arac aciyor mu", "istemde geciyor mu" diye
# soruyordu. Ucu de EVET olup ozellik yine calismayabilir: bu oturumda
# add_question'a eyebrow/theme/palette IMZAYA eklendi ama govdede motora hic
# gecirilmedi. Kontrol 0 bosluk dedi, cunku yalnizca AD karsilastiriyordu.
# Ozellik gorunurde vardi, gercekte yoktu.
print("\n=== PARAMETRE GOVDEDE ILETILIYOR MU ===")
ignored = 0
for name, engine, skip in PAIRS:
    tool = getattr(server, name, None)
    if tool is None:
        continue
    try:
        body = inspect.getsource(tool)
    except OSError:
        continue
    # ILETIM, GOVDEDE ADIN KULLANILMASI demek -- ve iki tuzak var:
    #
    #   1. Belge dizesi de govdenin parcasi. Duz metin aramasi yapildiginda
    #      docstring'de anlatilan eyebrow ve feedback "iletiliyor" sayildi ve
    #      kontrol, tam yakalamak icin yazildigi hatayi kacirdi.
    #   2. "ad=" aramasi konumsal iletimi kacirir: template, add_question'a
    #      ikinci sirada konumsal gecirilyor ve yanlislikla "iletilmiyor"
    #      diye isaretlendi.
    #
    # ast ile belge dizesi atilir ve ad, govdede bir DEGISKEN olarak aranir;
    # ikisini de karsilar.
    try:
        tree = ast.parse(textwrap.dedent(body))
        fn = tree.body[0]
        stmts = fn.body[1:] if (fn.body and isinstance(fn.body[0], ast.Expr)
                                and isinstance(getattr(fn.body[0], "value", None),
                                               ast.Constant)) else fn.body
        used = {n.id for s in stmts for n in ast.walk(s)
                if isinstance(n, ast.Name)}
        used |= {n.arg for s in stmts for n in ast.walk(s)
                 if isinstance(n, ast.keyword) and n.arg}
    except SyntaxError:
        used = set()
    engine_params = set(inspect.signature(engine).parameters) - skip - PLUMBING
    tool_params = set(inspect.signature(tool).parameters)
    dead = sorted(p for p in engine_params & tool_params if p not in used)
    print(f"  {name:<22} {'TAMAM' if not dead else 'ILETILMIYOR: ' + ', '.join(dead)}")
    ignored += len(dead)

stale = [p for p in ("YALNIZCA zaten katmani", "ilk katmani eklemek",
                     "list_templates cagir ve secenek") if p in agent.SYSTEM_PROMPT]

# Ucuncu ayak. Ilk iki ayak "motorda var mi" ve "arac aciyor mu" sorularini
# soruyor; ikisi de EVET olup ozellik yine de hic kullanilmayabilir, cunku
# ajan istemde adi gecmeyen bir parametreyi kendiliginden secmez. O yuzden
# ajanin AKTIF OLARAK secmesi gereken yetenekler burada adlariyla aranir.
# Otomatiklestirilemez: her motor parametresi isteme girmez (cogu varsayilanla
# dogru calisir), hangilerinin karar gerektirdigi bir tasarim kararidir.
MUST_APPEAR = {
    "avoid_variant": "ardisik slaytlarin ayni silueti tasimasini engelleyen tek sey",
    "image_style": "gorsel yerlesimi secilmezse hepsi ayni panele duser",
    "brand": "renk paleti tek renkten turetiliyor",
    "theme": "zemin slayt alaninin %98'i; kurslari ayiran en guclu eksen",
    "feedback": "geri bildirim katmani; verilmezse ogrenci baska kursun metnini okur",
}
absent = {name: why for name, why in MUST_APPEAR.items()
          if name not in agent.SYSTEM_PROMPT}
print(f"\n  istemde bayat kisit : {stale or 'yok'}")
print(f"  istemde eksik yetenek: {sorted(absent) or 'yok'}")
for name, why in sorted(absent.items()):
    print(f"    ! {name}: {why}")
print(f"  toplam bosluk       : "
      f"{gaps + len(tools - allowed) + len(stale) + len(absent) + ignored}")
