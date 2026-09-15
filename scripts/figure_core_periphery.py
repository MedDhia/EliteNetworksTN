"""The elite network as a core-periphery map, sized by betweenness.

Writes ``figures/fig13_core_periphery.{png,pdf}``.

The companion to ``figure_elite_graph.py``: the same six-category graph, the
same entity classes, but two deliberate changes.

**Node area is proportional to betweenness centrality**, not to degree. A
hub with many ties inside one family group brokers nothing; a node with few
ties that are the only route between two groups brokers everything. Degree
and betweenness disagree here, and betweenness is the one that answers "who
holds this network together".

**The layout states the core-periphery structure instead of leaving it to a
force algorithm.** A force layout of 23,274 nodes produces a uniform disc in
which a reader cannot tell core from periphery. Here:

* **radius comes from coreness** -- the innermost ring is the k=7 core, the
  outermost is the k=1 fringe, one equal-width ring per level. Spacing the
  rings so each annulus's area matched its population was tried first and
  defeats the purpose: with 16,254 nodes at k=1 and 8 at k=7 it collapses
  the core to a dot 2% of the radius across. Equal width still gives the
  outer rings most of the ink, because an annulus's area grows with r.
* **angle comes from community** (Louvain, 107 communities, modularity
  0.899). Each community gets an angular sector in proportion to its size,
  so a community reads as a radial wedge and its members stay together
  across rings.

So position is interpretable in both directions: in towards brokerage, round
towards a group.

The finding the figure is built around
--------------------------------------

Sizing by betweenness on a radius set by coreness makes the two disagree
visibly, and they do: **the largest nodes are not in the centre.** Not one
of the thirty largest brokers sits at k=6 or k=7. Betweenness climbs to a
ridge at k=5 (max 37.4M) and then *collapses* ninefold in the two rings
inside it (2.9M, 4.3M). The best-brokering member of the k=7 core ranks
41st.

So the network has two centres, and they are different entities:

* the **k=5 brokerage ridge** -- 256 nodes, 68% companies: the banks, the
  SICAR investment vehicles and État Tunisien. These are the bridges.
* the **k>=6 cohesive nucleus** -- 71 nodes, 0% state bodies, 0% parties,
  0% associations: private business families. The k=7 core is 8 people and
  nothing else.

The mechanism is in the density. Inside the nucleus the surname blocks are
near-complete cliques -- Abdelkefi 27 of 28 possible person-person pairs,
Ben Yedder 15 of 15, Driss 10 of 10, Elloumi 28 of 36 -- and inside a clique
every path has an alternative, so no member lies on a unique shortest path.
Cohesion and brokerage are not the same property, and here they are held by
different people.

That panel is reported per surname rather than pooled, because pooling would
have hidden a real distinction: **Slama has 0 of 10 possible kinship pairs.**
Its five members reach k=6 through shared company boards (Slama Huiles,
Slama Frères, Nejma Huiles are all in the nucleus), not through any extracted
kinship tie, and they do not form one connected block. Four of the six blocks
are kinship cliques; two are not, and the figure says which.

Two things measured rather than assumed
---------------------------------------

**Betweenness is exactly zero for 61.2% of nodes.** Area strictly
proportional to it would render three nodes in five invisible, so area is
proportional to the square root of betweenness above a visible floor, and
the zero share is stated on the figure rather than hidden by the floor.

**The single largest broker in the graph was not an entity.** An
organisation node with no label at all carried 295 ties and a betweenness of
76.7 million -- the highest of any node, ahead of Etat Tunisien. It is OCR
damage, and a non-entity cannot broker anything, so blank-labelled
organisations are dropped before the structure is computed.

Only the genuinely blank ones. A first pass dropped every organisation whose
label was three characters or fewer, which is wrong: of the 214 such nodes,
most are real firms trading under initials -- GAT is Generale Assurance
Tunisienne, MAC and PAF are likewise real -- and deleting them to be rid of
one bad node would have been a worse error than the one it fixed.
"""
from __future__ import annotations

import argparse
import collections
import csv
import pickle
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Circle

PROC = ROOT / "data" / "processed" / "multiplex"
INTERIM = ROOT / "data" / "interim"
FIGS = ROOT / "figures"
FIGS.mkdir(exist_ok=True)
GRAPH = INTERIM / "elite_graph.pkl"
CACHE = INTERIM / "core_periphery.pkl"

PERSON = "#A03B2C"
ORG = "#1B5FC1"
STATE = "#B5852A"
INK = "#1A1917"
MUTED = "#6C6D64"
RULE = "#D3D0C7"
FAINT = "#E8E5DD"
PAPER = "#FCFCFB"

plt.rcParams.update({
    "figure.facecolor": PAPER, "axes.facecolor": PAPER,
    "savefig.facecolor": PAPER, "font.family": "DejaVu Sans",
    "font.size": 8.5, "pdf.fonttype": 42, "legend.frameon": False,
})

STATE_RE = re.compile(
    r"MINISTERE|MINISTÈRE|PRESIDENCE|PRÉSIDENCE|GOUVERNORAT|MUNICIPALITE|"
    r"BANQUE CENTRALE|OFFICE NATIONAL|AGENCE NATIONALE|CAISSE NATIONALE|"
    r"ASSEMBLEE|ETAT TUNISIEN|SECRETARIAT", re.I)
ASSOC_RE = re.compile(
    r"ASSOCIATION|SYNDICAT|UNION |FONDATION|PARTI |CLUB |ORDRE DES|"
    r"CHAMBRE |FEDERATION|LIGUE|AMICALE", re.I)

STYLE = {
    "individual": (PERSON, "o"),
    "company": (ORG, "s"),
    "association / union": (ORG, "^"),
    "state body": (STATE, "s"),
    "party / parliamentary bloc": (STATE, "D"),
}
ORDER = ["company", "association / union", "party / parliamentary bloc",
         "state body", "individual"]


def node_class(n, kind, label, seed_type) -> str:
    if kind == "PERSON":
        return "individual"
    t = seed_type.get(n, "")
    if t in ("PARTY", "PARTY STRUCTURE", "PARLIAMENTARY BLOC"):
        return "party / parliamentary bloc"
    if t in ("GOVERNMENT", "GOVERNMENTAL ORGANIZATION"):
        return "state body"
    if t == "ORGANIZATION":
        return "association / union"
    if n.startswith("GOV_") or STATE_RE.search(label or ""):
        return "state body"
    if ASSOC_RE.search(label or ""):
        return "association / union"
    return "company"


def trim(s: str, n: int = 30) -> str:
    s = (s or "").strip()
    for a, b in (("MINISTERE DE L’", "Min. "), ("MINISTERE DE L'", "Min. "),
                 ("MINISTERE DES ", "Min. "), ("MINISTERE DE LA ", "Min. "),
                 ("PRESIDENCE DE LA ", "Présidence "),
                 ("PRÉSIDENCE DE LA ", "Présidence "), ("SOCIETE ", "Sté "),
                 ("'S CENTRAL COMMITTEE", " central cttee"),
                 ("BANQUE INTERNATIONALE ARABE DE TUNISIE ", "")):
        s = s.replace(a, b)
    if s.isupper():
        s = s.title()
    return s if len(s) <= n else s[: n - 1] + "…"


def structure(refresh: bool = False) -> dict:
    """Betweenness, coreness and communities on the cleaned giant component."""
    if CACHE.exists() and not refresh:
        with CACHE.open("rb") as fh:
            return pickle.load(fh)
    import igraph as ig

    with GRAPH.open("rb") as fh:
        d = pickle.load(fh)
    adj = {n: set(v) for n, v in d["adj"].items()}
    labels, kind, seed_type = d["labels"], d["kind"], d["seed_type"]

    # A node with no label at all is not an entity, and the unlabelled one
    # was the highest-betweenness node in the whole graph. Only genuinely
    # blank labels: short ones are real firms trading under initials.
    blank = {n for n in adj
             if kind[n] != "PERSON" and not (labels.get(n, "") or "").strip()}
    for n in blank:
        for m in adj[n]:
            adj[m].discard(n)
        del adj[n]
    print(f"  dropped {len(blank):,} organisation nodes with no label at all")

    seen: set[str] = set()
    best: list[str] = []
    for s in adj:
        if s in seen:
            continue
        stack, comp = [s], []
        seen.add(s)
        while stack:
            x = stack.pop()
            comp.append(x)
            for y in adj[x]:
                if y not in seen:
                    seen.add(y)
                    stack.append(y)
        if len(comp) > len(best):
            best = comp
    nodes = sorted(best)
    index = {n: i for i, n in enumerate(nodes)}
    edges = [(index[a], index[b]) for a in nodes for b in adj[a]
             if a < b and b in index]
    g = ig.Graph(n=len(nodes), edges=edges)
    g.simplify()
    print(f"  giant component {g.vcount():,} nodes / {g.ecount():,} edges")
    print("  betweenness…")
    bc = g.betweenness()
    core = g.coreness()
    comm = g.community_multilevel()
    print(f"  {len(comm):,} communities, modularity {comm.modularity:.3f}")
    out = {
        "nodes": nodes, "edges": [(a, b) for a, b in g.get_edgelist()],
        "bc": bc, "core": core, "comm": list(comm.membership),
        "labels": {n: labels.get(n, "") for n in nodes},
        "cls": {n: node_class(n, kind[n], labels.get(n, ""), seed_type)
                for n in nodes},
        "degree": g.degree(), "n_blank": len(blank),
    }
    with CACHE.open("wb") as fh:
        pickle.dump(out, fh)
    return out


def radial_layout(nodes, core, comm, bc) -> dict:
    """Radius from coreness, angle from community.

    Rings are EQUAL WIDTH, one per coreness value. Spacing them so each
    annulus's area matched its population was tried first and defeats the
    purpose: with 16,254 nodes at k=1 and 8 at k=7, it collapses the core to
    a dot 2% of the radius across. Equal width still gives the outer rings
    most of the ink -- an annulus's area grows with r, so the k=1 rim holds
    27% of the area against the core's 2% -- while leaving the core visible,
    which is the whole point of the figure.
    """
    kmax = max(core)
    pop = collections.Counter(core)
    edge_r = {k: (kmax - k + 1) / kmax for k in range(1, kmax + 1)}
    inner = {k: edge_r[k] - 1.0 / kmax for k in range(1, kmax + 1)}

    # angular sector per community, proportional to size, largest first
    size = collections.Counter(comm)
    ordered = [c for c, _ in size.most_common()]
    start, sector = {}, {}
    acc = 0.0
    for c in ordered:
        sector[c] = 2 * np.pi * size[c] / len(nodes)
        start[c] = acc
        acc += sector[c]

    # within a community sector, order by coreness then betweenness so the
    # brokers of each group sit at the clockwise edge of its wedge
    members = collections.defaultdict(list)
    for i, n in enumerate(nodes):
        members[comm[i]].append(i)
    pos = {}
    rng = np.random.default_rng(11)
    for c, mem in members.items():
        mem.sort(key=lambda i: (core[i], bc[i]))
        for j, i in enumerate(mem):
            frac = (j + 0.5) / len(mem)
            ang = start[c] + sector[c] * frac
            lo, hi = inner[core[i]], edge_r[core[i]]
            r = lo + (hi - lo) * (0.15 + 0.7 * rng.random())
            pos[nodes[i]] = (r * np.cos(ang), r * np.sin(ang))
    return pos, edge_r, inner, pop


def place_labels(ax, items, *, fontsize=6.8, placed=None):
    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    if placed is None:
        placed = []
    for text, (x, y) in items:
        for dx, dy in ((0, 11), (0, -13), (30, 3), (-30, 3), (0, 22), (0, -24)):
            ann = ax.annotate(
                text, (x, y), xytext=(dx, dy), textcoords="offset points",
                ha="center", va="center", fontsize=fontsize, color=INK,
                fontweight="semibold",
                bbox=dict(boxstyle="round,pad=0.16", fc=PAPER, ec="none",
                          alpha=.92), zorder=7)
            bb = ann.get_window_extent(renderer=renderer)
            box = (bb.x0 - 1, bb.y0 - 1, bb.x1 + 1, bb.y1 + 1)
            if any(box[0] < p[2] and box[2] > p[0]
                   and box[1] < p[3] and box[3] > p[1] for p in placed):
                ann.remove()
                continue
            placed.append(box)
            break
    return placed


NUCLEUS_K = 6


def ring_stats(bc, core) -> list[dict]:
    """Per coreness ring: population, peak and median betweenness."""
    by = collections.defaultdict(list)
    for i, k in enumerate(core):
        by[k].append(bc[i])
    out = []
    for k in sorted(by):
        v = sorted(by[k])
        mid = v[len(v) // 2] if len(v) % 2 else (v[len(v) // 2 - 1]
                                                + v[len(v) // 2]) / 2
        out.append({"k": k, "n": len(v), "max": v[-1], "median": mid})
    return out


PARTICLE = {"BEN", "BENT", "BINT", "ABOU", "ABU", "OULD", "EL", "AL"}


def surname(label: str) -> str:
    """Last name token, carrying a nasab particle with it.

    Splitting on the last token alone turns BEN-YEDDER into YEDDER, which
    is not what the family is called.
    """
    parts = [p for p in re.split(r"[ \-]", label) if p]
    parts = [p for p in parts if len(p) > 2 or p.upper() in PARTICLE]
    if not parts:
        return ""
    if len(parts) > 1 and parts[-2].upper() in PARTICLE:
        return f"{parts[-2]} {parts[-1]}"
    return parts[-1]


def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def nucleus_blocks(d, min_members: int = 4) -> list[dict]:
    """Surname blocks in the k>=6 nucleus, with kinship actually verified.

    Sharing a surname is not evidence of a family. For each block this
    reports the share of possible person-person pairs that carry an actual
    tie inside the nucleus, which is what separates the four real cliques
    from the two blocks that only co-sit on company boards.
    """
    nodes, core, cls, labels = d["nodes"], d["core"], d["cls"], d["labels"]
    nucleus = {i for i in range(len(nodes)) if core[i] >= NUCLEUS_K}
    adj = collections.defaultdict(set)
    internal = 0
    for a, b in d["edges"]:
        if a in nucleus and b in nucleus:
            adj[a].add(b)
            adj[b].add(a)
            internal += 1

    groups = collections.defaultdict(list)
    for i in nucleus:
        if cls[nodes[i]] == "individual":
            groups[surname(labels[nodes[i]])].append(i)

    out = []
    for name, mem in groups.items():
        if len(mem) < min_members:
            continue
        possible = len(mem) * (len(mem) - 1) // 2
        tied = sum(1 for a in mem for b in mem if a < b and b in adj[a])
        seen, stack, ms = {mem[0]}, [mem[0]], set(mem)
        while stack:
            for v in adj[stack.pop()]:
                if v in ms and v not in seen:
                    seen.add(v)
                    stack.append(v)
        out.append({"name": name, "n": len(mem), "tied": tied,
                    "possible": possible, "share": tied / possible,
                    "largest_block": len(seen)})
    out.sort(key=lambda r: (-r["share"], -r["n"]))
    return out, len(nucleus), internal


def _bare(ax) -> None:
    ax.set_facecolor(PAPER)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(RULE)
        ax.spines[side].set_linewidth(.8)
    ax.tick_params(colors=MUTED, labelsize=7.2, length=3, width=.8)


def panel_ridge(ax, stats) -> None:
    """Betweenness against coreness: the ridge at k=5 and the fall inside it."""
    ks = [r["k"] for r in stats]
    peak = max(stats, key=lambda r: r["max"])
    floor = 4e3  # a log axis cannot draw the k=1 median, which is exactly 0

    for r, style, colour, lbl in (
            ("max", "-", INK, "highest in the ring"),
            ("median", "--", MUTED, "ring median")):
        y = [max(s[r], floor) for s in stats]
        ax.plot(ks, y, style, color=colour, lw=1.8, zorder=3,
                marker="o" if r == "max" else "s", ms=5.0,
                mfc=colour, mec=PAPER, mew=.8, label=lbl)

    ax.set_yscale("log")
    ax.set_xlim(0.6, max(ks) + 0.45)
    ax.set_ylim(floor * 0.7, peak["max"] * 4.6)
    ax.set_xticks(ks)
    ax.set_xlabel("coreness $k$  (outer ring → core)", fontsize=7.4,
                  color=MUTED, labelpad=2)
    ax.set_yticks([1e4, 1e5, 1e6, 1e7])
    ax.set_yticklabels(["10k", "100k", "1M", "10M"])
    _bare(ax)
    ax.grid(axis="y", color=FAINT, lw=.7, zorder=0)
    ax.set_axisbelow(True)

    ax.annotate(f"ridge · {peak['max'] / 1e6:.0f}M",
                (peak["k"], peak["max"]), xytext=(7, 9),
                textcoords="offset points", ha="left", va="bottom",
                fontsize=7.4, color=INK, fontweight="semibold")
    inside = [s for s in stats if s["k"] > peak["k"]]
    if inside:
        drop = peak["max"] / max(s["max"] for s in inside)
        tgt = inside[0]
        ax.annotate(f"{drop:.0f}× lower\ninside the ridge",
                    (tgt["k"], tgt["max"]), xytext=(3, -7),
                    textcoords="offset points", ha="left", va="top",
                    fontsize=7.2, color=PERSON, fontweight="semibold",
                    linespacing=1.45)
    ax.annotate("median is 0 here", (1, floor), xytext=(4, 5),
                textcoords="offset points", ha="left", va="bottom",
                fontsize=6.8, color=MUTED)
    ax.legend(loc="upper left", fontsize=7.2, labelcolor=INK,
              handlelength=1.9, handletextpad=.55, borderpad=.2,
              labelspacing=.3)
    ax.set_title("Brokerage peaks one ring OUTSIDE the core, then collapses",
                 fontsize=8.4, color=INK, fontweight="semibold", loc="left",
                 pad=6)


def panel_blocks(ax, blocks) -> None:
    """Which surname blocks in the nucleus are kinship cliques, and which are not."""
    blocks = list(reversed(blocks))
    y = np.arange(len(blocks))
    ax.barh(y, [1.0] * len(blocks), height=.62, color=FAINT, zorder=1)
    ax.barh(y, [b["share"] for b in blocks], height=.62, color=PERSON,
            zorder=2)

    for i, b in enumerate(blocks):
        ax.text(-0.035, i, f"{b['name'].title()} · {b['n']}", ha="right",
                va="center", fontsize=7.4, color=INK,
                fontweight="semibold" if b["share"] > 0 else "normal")
        inside = b["share"] > 0.45
        ax.text(b["share"] - 0.02 if inside else b["share"] + 0.02, i,
                f"{b['tied']}/{b['possible']}", ha="right" if inside else "left",
                va="center", fontsize=7.0,
                color=PAPER if inside else MUTED,
                fontweight="semibold" if inside else "normal", zorder=3)

    ax.set_xlim(0, 1.0)
    ax.set_ylim(-0.7, len(blocks) - 0.3)
    ax.set_yticks([])
    ax.set_xticks([0, .5, 1.0])
    ax.set_xticklabels(["0", "half", "every pair"])
    _bare(ax)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("share of possible person-person pairs actually tied",
                  fontsize=7.2, color=MUTED, labelpad=3)
    ax.set_title("The nucleus is cliques — but only where kinship is evidenced",
                 fontsize=8.4, color=INK, fontweight="semibold", loc="left",
                 pad=30)
    # The caveat goes between title and bars: below them it collided with the
    # x-axis label, and it is the point of the panel, not a footnote to it.
    zero = [b for b in blocks if b["share"] == 0]
    if zero:
        ax.annotate(
            f"name · members, bar = share of pairs tied.  "
            f"{zero[0]['name'].title()} shares only a surname:\nno kinship "
            f"tie between any of its {zero[0]['n']}, which reach "
            f"$k$≥{NUCLEUS_K} on company boards alone.",
            (0, 1.0), xycoords="axes fraction", xytext=(0, 6),
            textcoords="offset points", ha="left", va="bottom", fontsize=6.9,
            color=MUTED, linespacing=1.45)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--labels", type=int, default=30)
    args = ap.parse_args(argv)

    print("loading…")
    d = structure(args.refresh)
    nodes, bc, core, comm = d["nodes"], d["bc"], d["core"], d["comm"]
    labels, cls, deg = d["labels"], d["cls"], d["degree"]
    idx = {n: i for i, n in enumerate(nodes)}

    pos, edge_r, inner, pop = radial_layout(nodes, core, comm, bc)
    kmax = max(core)
    zero = sum(1 for v in bc if v == 0)
    bmax = max(bc)

    stats = ring_stats(bc, core)
    blocks, n_nucleus, n_internal = nucleus_blocks(d)
    ridge = max(stats, key=lambda r: r["max"])
    n_ridge = ridge["n"]
    ridge_co = sum(1 for i, n in enumerate(nodes)
                   if core[i] == ridge["k"] and cls[n] == "company")
    top_all = sorted(range(len(nodes)), key=lambda i: -bc[i])
    best_nucleus = min(r for r, i in enumerate(top_all, 1)
                       if core[i] >= NUCLEUS_K)

    fig, ax = plt.subplots(figsize=(18.4, 14.2))

    # ring guides, outermost first so the core draws over them
    for k in range(1, kmax + 1):
        ax.add_patch(Circle((0, 0), edge_r[k], fill=False, ec=FAINT, lw=.8,
                            zorder=0))
        ang = np.deg2rad(58)
        ax.annotate(f"$k$={k}  ·  {pop[k]:,}",
                    (edge_r[k] * np.cos(ang), edge_r[k] * np.sin(ang)),
                    xytext=(0, 0), textcoords="offset points",
                    ha="center", va="center",
                    fontsize=7.4, color=MUTED, zorder=6,
                    bbox=dict(boxstyle="round,pad=0.14", fc=PAPER, ec="none",
                              alpha=.9))

    segs = [(pos[nodes[a]], pos[nodes[b]]) for a, b in d["edges"]]
    ax.add_collection(LineCollection(segs, colors=RULE, linewidths=.14,
                                     alpha=.5, zorder=1))

    # area proportional to sqrt(betweenness), above a floor: strict
    # proportionality would make 61% of nodes invisible.
    def size_of(i):
        return 1.6 + 250.0 * np.sqrt(bc[i] / bmax)

    counts = {}
    for name in ORDER:
        pool = [i for i, n in enumerate(nodes) if cls[n] == name]
        if not pool:
            continue
        colour, marker = STYLE[name]
        ax.scatter([pos[nodes[i]][0] for i in pool],
                   [pos[nodes[i]][1] for i in pool],
                   s=[size_of(i) for i in pool], c=colour, marker=marker,
                   linewidths=.22, edgecolors=PAPER,
                   zorder=3 if name != "individual" else 2)
        counts[name] = len(pool)

    # The brokers are by definition in the core, so in-situ names pile into
    # one unreadable knot at the centre. Number them on the map instead and
    # spell them out in the margin.
    top = sorted(range(len(nodes)), key=lambda i: -bc[i])[:args.labels]
    for rank, i in enumerate(top, 1):
        x, y = pos[nodes[i]]
        ax.annotate(str(rank), (x, y), xytext=(0, 0),
                    textcoords="offset points", ha="center", va="center",
                    fontsize=6.6, fontweight="bold", color=PAPER, zorder=7,
                    bbox=dict(boxstyle="circle,pad=0.16", fc=INK, ec=PAPER,
                              lw=.6, alpha=.95))

    # Name the two centres on the map, or the reader is left wondering why
    # the largest nodes sit in a middle ring.
    def polar(r, deg):
        a = np.deg2rad(deg)
        return r * np.cos(a), r * np.sin(a)

    for text, tgt, txy, ha in (
            (f"THE BROKERAGE RIDGE · $k$={ridge['k']}, {n_ridge} nodes\n"
             f"the banks, the SICAR investment vehicles and État Tunisien.\n"
             f"Every one of the 30 largest brokers is in this ring or "
             f"outside it.",
             polar(edge_r[ridge["k"]] - .02, 170), polar(.70, 150), "left"),
            (f"THE COHESIVE NUCLEUS · $k$≥{NUCLEUS_K}, {n_nucleus} nodes\n"
             f"private business families, and at $k$={kmax} eight people and "
             f"nothing else.\nMost cohesive, yet its best broker ranks only "
             f"{ordinal(best_nucleus)} — inside a clique\nevery path has an "
             f"alternative, so no member is anyone's only route.",
             (0, 0), polar(.56, 250), "left")):
        ax.annotate(
            text, tgt, xytext=txy, textcoords="data", ha=ha, va="center",
            fontsize=7.3, color=INK, linespacing=1.55, zorder=9,
            bbox=dict(boxstyle="round,pad=0.42", fc=PAPER, ec=RULE, lw=.8,
                      alpha=.96),
            arrowprops=dict(arrowstyle="-", color=MUTED, lw=1.0,
                            shrinkA=3, shrinkB=2,
                            connectionstyle="arc3,rad=0.08"))

    ax.set_aspect("equal")
    ax.set_xlim(-1.06, 1.06)
    ax.set_ylim(-1.06, 1.06)
    ax.set_axis_off()

    leg = ax.legend(
        handles=[Line2D([], [], marker=STYLE[n][1], ls="none",
                        mfc=STYLE[n][0], mec=PAPER, mew=.5, ms=9,
                        label=f"{n} · {counts.get(n, 0):,}") for n in ORDER],
        loc="upper left", bbox_to_anchor=(0.004, 1.012), labelspacing=.85,
        handletextpad=.9, fontsize=9.5, labelcolor=INK, borderpad=.9,
        title="entity type, and how many are drawn")
    leg.get_title().set_fontsize(8.5)
    leg.get_title().set_color(MUTED)

    fig.text(0.011, 0.996,
             "The Tunisian elite network has two centres, and they are not "
             "the same people",
             ha="left", va="top", fontsize=15.5, fontweight="bold", color=INK)
    fig.text(0.011, 0.972,
             f"{len(nodes):,} entities and {len(d['edges']):,} ties — the "
             f"largest connected component of the six-category graph.  "
             f"Node area ∝ √betweenness; radius is coreness, one equal-width "
             f"ring per level; angle is community\n"
             f"(Louvain, {len(set(comm))} communities, modularity 0.899), so "
             f"each group reads as a radial wedge.  Sizing by brokerage on a "
             f"radius set by cohesion lets the two disagree — and they do: "
             f"the biggest nodes are NOT in the centre.\n"
             f"Brokerage peaks at $k$={ridge['k']} ({n_ridge} nodes, "
             f"{100 * ridge_co / n_ridge:.0f}% companies: the banks, the "
             f"SICARs, État Tunisien) and collapses "
             f"inside it.  The $k$≥{NUCLEUS_K} nucleus is {n_nucleus} nodes of "
             f"private business family — no state body, no party, no "
             f"association —\nand its best broker ranks only "
             f"{ordinal(best_nucleus)}. Cohesion and brokerage are different "
             f"properties, held here by different entities.",
             ha="left", va="top", fontsize=9.0, color=MUTED, linespacing=1.55)

    rows = []
    for rank, i in enumerate(top, 1):
        n = nodes[i]
        rows.append(f"{rank:>2}.  {trim(labels[n], 30):32} "
                    f"{bc[i] / 1e6:6.1f}M   k={core[i]}")
    kset = sorted({core[i] for i in top})
    fig.text(0.678, 0.884,
             "The brokers, numbered on the map\n"
             "betweenness in millions, and the ring they sit in — every one "
             f"of the {len(top)} is at $k$={kset[0]}–{kset[-1]},\n"
             f"none in the $k$≥{NUCLEUS_K} nucleus",
             ha="left", va="top", fontsize=8.6, color=INK,
             fontweight="semibold", linespacing=1.5)
    fig.text(0.678, 0.828, "\n".join(rows), ha="left", va="top",
             fontsize=7.4, color=INK, family="DejaVu Sans Mono",
             linespacing=1.62)

    panel_ridge(fig.add_axes([0.706, 0.300, 0.266, 0.138]), stats)
    panel_blocks(fig.add_axes([0.706, 0.118, 0.266, 0.100]), blocks)

    n_blocks = len(blocks)
    n_clique = sum(1 for b in blocks if b["share"] >= 0.7)
    fig.text(0.011, 0.014,
             f"Betweenness is exactly ZERO for {zero:,} of {len(nodes):,} "
             f"nodes ({100 * zero / len(nodes):.0f}%) — they lie on no "
             f"shortest path between any other pair, so they broker nothing. "
             f"Area is ∝ √betweenness above a visible floor; strict "
             f"proportionality would erase three nodes in five.\n"
             f"Peak betweenness by ring: "
             + ", ".join(f"$k$={s['k']} {s['max'] / 1e6:.1f}M"
                         for s in stats)
             + f".  Coreness and Louvain communities are computed on the "
             f"undirected simple graph; {n_internal} of the {len(d['edges']):,} "
             f"ties drawn fall inside the $k$≥{NUCLEUS_K} nucleus.\n"
             f"Surname blocks in the nucleus are reported one by one rather "
             f"than pooled, because pooling hides a real distinction: a "
             f"shared surname is not evidence of a family. {n_clique} of the "
             f"{n_blocks} blocks are near-complete kinship cliques; Slama "
             f"has none at all.\n"
             f"{d['n_blank']:,} organisation nodes with no label at all are "
             f"dropped: one carried 295 ties and the HIGHEST betweenness in "
             f"the graph (76.7M, ahead of État Tunisien), and a node that is "
             f"not an entity cannot broker anything. Short labels are kept — "
             f"GAT, MAC and PAF are real firms.\n"
             f"Source: Journal Officiel de la République Tunisienne "
             f"1957–2026 (jort.tn), the Registre National des Entreprises, "
             f"and a 13,630-name elite roster. Author's extraction; "
             f"`scripts/figure_core_periphery.py`.",
             ha="left", va="bottom", fontsize=6.9, color=MUTED,
             linespacing=1.7)
    fig.subplots_adjust(top=0.900, bottom=0.082, left=0.008, right=0.668)

    _write_table(nodes, bc, core, comm, cls, labels, deg)
    for ext, kw in (("png", {"dpi": 260}), ("pdf", {})):
        p = FIGS / f"fig13_core_periphery.{ext}"
        fig.savefig(p, **kw)
        print(f"  {p.relative_to(ROOT)}  {p.stat().st_size / 1024:.0f} KB")
    plt.close(fig)
    print(f"  betweenness zero for {zero:,}/{len(nodes):,} "
          f"({100 * zero / len(nodes):.1f}%)")
    print(f"  coreness rings: " + ", ".join(f"k={k}:{pop[k]:,}"
                                            for k in sorted(pop)))
    print("  top brokers: " + "; ".join(
        f"{trim(labels[nodes[i]], 26)} {bc[i] / 1e6:.1f}M" for i in top[:5]))
    del idx
    return 0


def _write_table(nodes, bc, core, comm, cls, labels, deg) -> None:
    path = PROC / "elite_graph_centrality.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["node_id", "label", "node_class", "degree",
                    "betweenness", "coreness", "community"])
        for i, n in enumerate(nodes):
            w.writerow([n, labels[n], cls[n], deg[i], f"{bc[i]:.1f}",
                        core[i], comm[i]])
    print(f"  wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    raise SystemExit(main())
