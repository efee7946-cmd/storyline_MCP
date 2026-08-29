"""İki slayt gerçekten farklı mı görünüyor, yoksa aynı resmin kaydırılmışı mı?

Varyant sayısı çeşitlilik ölçüsü değil. Sözlüğe dört ad yazmak dört farklı
slayt demek değildir: dördü de metin sütununun x'ini oynatıyorsa, ikisi
birbirinin kaydırılmışı ve ikisi birbirinin aynası olur -- sayı dört, göz iki
görür. "Farklı görünmüyor" ölçülemez; "aynı siluet" ölçülebilir.

Slayt kaba bir doluluk ızgarasına indirilir (metin ve dolgu ayrı katman olarak,
çünkü büyük bir panel ile bir başlık aynı hücreyi doldurur ama aynı şey
değildir). Sonra iki mesafe hesaplanır:

    dogrudan  -- iki siluet ust uste ne kadar ortusuyor
    aynali    -- biri yatay cevrildiginde ne kadar ortusuyor

Aynalı mesafenin küçük olması, iki varyantın tek fikrin iki yüzü olduğunu
söyler. Kaydırmayı doğrudan mesafe yakalar, aynayı yalnızca ikincisi.

NEYE KÖR OLDUĞU. Bu kaba bir doluluk ızgarası: nerede mürekkep var, ne kadar.
Rengi, puntoyu, yazı ağırlığını, satır ritmini, köşe yarıçapını, gölgeyi
görmez. Bir kez gözü düzeltti -- göz iki varyanta "aynı" demişti, ölçü onları
gerçek ayna çiftinden üç dört kat uzakta gösterdi ve haklıydı. Ama orada fark
KONUMSALDI; ölçünün gördüğü tek eksen o. Farkın konumsal olmadığı bir çiftte
-- aynı yerleşim, farklı tipografi ya da farklı vurgu rengi -- ölçü "aynı"
diyecek ve yanılacak. Ölçü gözü bir kez düzelttiği için ona fazla güvenmek,
bu aracın üretebileceği en pahalı hata olur: gözle bakmayı bıraktırır.

Bu yüzden ölçü bakmanın yerine değil, yanına konur. İkisi çeliştiğinde
çelişkinin hangi eksende olduğu sorulur; konumsalsa ölçü, değilse göz.

    python tools/silhouette.py kurs.story
    python tools/silhouette.py kurs.story --slides slide.xml slide2.xml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from storyline_mcp import model, shapes
from storyline_mcp.package import StoryPackage

COLS, ROWS = 16, 9
# Bunun altindaki iki slayt "ayni fikir" sayilir.
#
# Uc ayri icerik kumesinde olculdu (kartli / kartsiz / uzun). Gercekten tek
# fikrin iki yuzu olan cift ucunde de 0.081-0.090 arasinda kaldi; ondan sonraki
# en yakin cift 0.195'te basladi. Esik ikisinin arasina, iki yana da paylı
# olacak sekilde konuldu -- tek ornekten secilmis bir esik degil.
SAME_IDEA = 0.15


def grid(pkg: StoryPackage, name: str) -> list[float]:
    """Slaydın doluluk ızgarası: her hücrede ne kadar mürekkep var.

    Tam sayfa arka planlar atlanır -- her slaytta olduğu için hiçbir şeyi
    ayırt etmez ve her ölçümü birbirine yaklaştırır.
    """
    part = pkg.slide_part_for(name)
    root = pkg.parse(part)
    W, H = shapes.slide_size(root)
    cells = [0.0] * (COLS * ROWS)
    cw, ch = W / COLS, H / ROWS
    shape_list = root.find("shapeLst")
    for shape in list(shape_list) if shape_list is not None else []:
        rect = shapes.shape_rect(shape)
        if not rect:
            continue
        l, t, r, b = rect
        if (r - l) * (b - t) > 0.92 * W * H:
            continue
        has_text = bool(model.shape_text(root, shape.get("g", "")).strip())
        weight = 1.0 if has_text else 0.55
        for cy in range(ROWS):
            for cx in range(COLS):
                ox = max(0.0, min(r, (cx + 1) * cw) - max(l, cx * cw))
                oy = max(0.0, min(b, (cy + 1) * ch) - max(t, cy * ch))
                if ox > 0 and oy > 0:
                    cells[cy * COLS + cx] += weight * (ox * oy) / (cw * ch)
    return [min(v, 1.0) for v in cells]


def flip(cells: list[float]) -> list[float]:
    out = []
    for y in range(ROWS):
        row = cells[y * COLS:(y + 1) * COLS]
        out.extend(reversed(row))
    return out


def distance(a: list[float], b: list[float]) -> float:
    """0 = aynı siluet, 1 = hiç örtüşmüyor.

    Fark, hücre sayısına değil iki siluetin **birleşimine** bölünür. Hücre
    sayısına bölmek mutlak bir sayı verir ve o sayı slayttaki mürekkep
    miktarına bağlıdır: az doldurulmuş iki slayt, yerleşimleri ne olursa olsun,
    birbirine yakın çıkar. Ölçüldü -- aynı varyant çifti üç ayrı içerikte
    0.229 / 0.200 / 0.203 verdi ve sabit bir eşiğin iki yanına düştü. Birleşime
    bölünce oran ölçeksiz olur: "örtüşmeyen alanın toplam alana payı".
    """
    union = sum(max(x, y) for x, y in zip(a, b))
    if union <= 0:
        return 0.0
    return sum(abs(x - y) for x, y in zip(a, b)) / union


def ideas(names: list[str], pairs: list[dict]) -> list[list[str]]:
    """Slaytları "aynı fikir" bağıntısı altında öbeklere ayırır.

    Öbek saymak gerekiyor, çift saymak değil: A~B ve B~C ise üçü tek fikirdir
    ama iki çift sayılır. "Ad sayısı eksi çift sayısı" aritmetiği bunu
    kaçırır -- ve yeterince çift olduğunda negatif sayı üretir, ki ölçünün
    yanlış olduğunun en ucuz kanıtıdır.
    """
    parent = {n: n for n in names}

    def root(n: str) -> str:
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n

    for pair in pairs:
        if pair["same_idea"]:
            a, b = root(pair["a"]), root(pair["b"])
            if a != b:
                parent[a] = b
    groups: dict[str, list[str]] = {}
    for n in names:
        groups.setdefault(root(n), []).append(n)
    return list(groups.values())


def compare(pkg: StoryPackage, names: list[str]) -> list[dict]:
    grids = {n: grid(pkg, n) for n in names}
    out = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            direct = distance(grids[a], grids[b])
            mirror = distance(grids[a], flip(grids[b]))
            near = min(direct, mirror)
            out.append({"a": a, "b": b, "direct": direct, "mirror": mirror,
                        "same_idea": near < SAME_IDEA,
                        "why": "ayna" if mirror < direct else "kayma"})
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("story")
    parser.add_argument("--slides", nargs="*")
    parser.add_argument("--labels", nargs="*", help="slaytlarla ayni sirada")
    args = parser.parse_args()

    pkg = StoryPackage(Path(args.story).resolve())
    names = args.slides or [r.basename for r in model.slide_index(pkg).values()]
    names = [n for n in names if any(grid(pkg, n))]
    label = dict(zip(names, args.labels)) if args.labels else {}

    pairs = compare(pkg, names)
    print(f"{len(names)} dolu slayt, {len(pairs)} cift\n")
    print(f"{'a':<14}{'b':<14}{'dogrudan':>9}{'aynali':>8}   ")
    same = 0
    for p in sorted(pairs, key=lambda p: min(p["direct"], p["mirror"])):
        mark = f"  <- ayni fikir ({p['why']})" if p["same_idea"] else ""
        same += p["same_idea"]
        print(f"{label.get(p['a'], p['a']):<14}{label.get(p['b'], p['b']):<14}"
              f"{p['direct']:>9.3f}{p['mirror']:>8.3f}{mark}")
    ideas = len(names) - same
    print(f"\n{len(names)} varyant yazildi, {same} cift ayni fikir.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
