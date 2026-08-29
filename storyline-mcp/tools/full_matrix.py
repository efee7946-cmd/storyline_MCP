"""Every write operation, each verified by Storyline itself.

--no-open writes the cases and stops. The write phase takes seconds and the
open phase takes twenty minutes, so a change that breaks the writing is worth
finding before committing to the wait.
"""
import argparse, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from storyline_mcp import model, server as S
from storyline_mcp.package import StoryPackage
from open_test import test_open

args = argparse.ArgumentParser()
args.add_argument("--no-open", action="store_true", help="sadece yazma fazi")
args.add_argument("--only", default="", help="ad parcasiyla filtrele")
OPTS = args.parse_args()

BLANK = Path(r"c:\Users\erman\Desktop\Art\test\try_ONCE.story")     # bos yeni proje
RICH = Path(r"c:\Users\erman\Desktop\Art\test\0_duz_kopya.story")   # dolu gercek kurs
T = Path(r"c:\Users\erman\Desktop\Art\test")

def first_slide(p):
    return next(iter(model.slide_index(StoryPackage(p)).values())).basename

cases = []

def case(name, source, fn):
    if OPTS.only and OPTS.only not in name:
        return
    p = T / f"m_{name}.story"
    shutil.copy2(source, p)
    try:
        fn(str(p), first_slide(p))
        cases.append((name, p, None))
    except Exception as exc:
        cases.append((name, p, str(exc)[:60]))

# --- bos projede ---------------------------------------------------------
case("bos_arkaplan", BLANK, lambda p, s: S.set_background(p, s, "#0A2240", in_place=True))
case("bos_metin", BLANK, lambda p, s: S.add_text_box(p, s, "Baslik", color="#FFED00", size=30, in_place=True))
case("bos_buton", BLANK, lambda p, s: S.add_button(p, s, "Devam", fill="#FFED00", in_place=True))
case("bos_tamsayfa", BLANK, lambda p, s: S.build_course(p, [
    {"op": "set_background", "slide": s, "color": "#16215B"},
    {"op": "add_text_box", "slide": s, "text": "Futbola Giris", "x": 10, "y": 28,
     "w": 80, "h": 20, "color": "#FFED00", "size": 34},
    {"op": "add_button", "slide": s, "text": "KURSA BASLA", "fill": "#FFED00"},
], in_place=True))
case("bos_slayt_ozellik", BLANK, lambda p, s: S.set_slide_properties(
    p, s, advance_by_user=True, prev=False, next=False, in_place=True))
case("bos_boyut", BLANK, lambda p, s: S.set_story_size(p, 1280, 720, in_place=True))

# --- dolu kursta ---------------------------------------------------------
case("dolu_metin", RICH, lambda p, s: S.update_text(p, [{
    "addr": next(r for r in model.text_runs(StoryPackage(p)) if len(r.text.strip()) > 8).addr,
    "new_text": "Degistirildi"}], in_place=True))
case("dolu_slayt_klon", RICH, lambda p, s: S.duplicate_slide(p, s, in_place=True))
case("dolu_sahne", RICH, lambda p, s: S.add_scene(p, "Yeni_Bolum", in_place=True))
def _add_question(p, s):
    # Asked of the engine, not re-derived here. A second opinion about which
    # templates can be filled is a second thing to keep in step, and the two
    # would disagree the moment either changed -- which is how this test came
    # to be picking a template whose options hold no text at all.
    from storyline_mcp.authoring import available_question_shapes
    usable = [e for e in available_question_shapes(StoryPackage(p))
              if e["source"] == "project"]
    if not usable:
        raise RuntimeError("provadan gecen soru sablonu yok")
    tpl = usable[0]
    n = tpl["choices"]
    # The template is a keyword: passing it third would land it in `prompt`.
    S.add_question(p, "Test sorusu?", [chr(65 + i) for i in range(n)], [1],
                   template=tpl["slide"], in_place=True)

case("dolu_soru", RICH, _add_question)
case("dolu_hover", RICH, lambda p, s: S.set_button_state(
    p, s, S.list_button_states(p, s)[0]["shape"], "Hover", fill="#FFED00", in_place=True))
case("dolu_katman", RICH, lambda p, s: S.add_layer(p, s, "Popup", text="Merhaba", in_place=True))
case("dolu_player", RICH, lambda p, s: S.set_player_color(p, "bg", "#0A2240", in_place=True))
case("dolu_restyle", RICH, lambda p, s: S.restyle_slide_text if False else S.restyle_text(
    p, s, color="#FFED00", in_place=True))

if not OPTS.no_open:
    # Bu dosyanin acilis fazi yarim saat suruyor; kanarya tam olarak bunun
    # onunde durmak icin var. open_test.main() kendi kanaryasini kosuyor ama
    # buradan test_open dogrudan cagriliyor, yani atlaniyordu.
    import canary
    verdict = canary.check(test_open, timeout=90.0)
    canary.report(verdict)
    if not verdict["trustworthy"]:
        print("\nKosu iptal edildi. Once araci onar.")
        raise SystemExit(3)
    print()

print(f"{'islem':<22} {'yazma':<10} {'ACILDI':<8} sn")
print("-" * 54)
ok = fail = 0
for name, path, err in cases:
    if err:
        print(f"{name:<22} {'HATA':<10} {'-':<8} {err}")
        fail += 1
        continue
    if OPTS.no_open:
        print(f"{name:<22} {'tamam':<10} {'-':<8} (acilis atlandi)")
        continue
    r = test_open(path)
    mark = "EVET" if r["opened"] else "HAYIR"
    print(f"{name:<22} {'tamam':<10} {mark:<8} {r['seconds'] or '-'}")
    ok += r["opened"]
    fail += not r["opened"]

written = sum(1 for _n, _p, e in cases if not e)
if OPTS.no_open:
    print(f"\nYAZILAN: {written}/{len(cases)}   HATA: {len(cases) - written}")
    raise SystemExit(0 if written == len(cases) else 1)
print(f"\nACILAN: {ok}/{len(cases)}   SORUNLU: {fail}")
raise SystemExit(0 if fail == 0 else 1)
