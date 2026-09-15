"""One graph: the Tunisian elite network at entity level, six tie types.

Writes ``figures/fig12_elite_graph.{png,pdf}`` and the edge/node lists behind
it to ``data/processed/multiplex/elite_graph_{nodes,edges}.csv``.

Individuals and organisations are separate nodes -- nothing is aggregated or
projected onto one mode -- and exactly six kinds of tie are admitted:

1. an individual owning shares in, or sitting on the governing body of, a
   company, state-owned or not;
2. an individual to another individual by family;
3. an individual on the board of an association, or holding a seat in a
   party's national structures;
4. members of parliament and of the government;
5. an organisation owning shares in another organisation;
6. every edge in the seed file, whatever its label.

Everything else is excluded, which for the state side means every government
employee who is not a member of the government or of parliament and does not
sit on a board: `chef_de_service`, `sous_directeur`, `secretaire_general`,
`directeur general`, `conseiller`, `representant` and the state offices whose
rank the gazette never states.

Two judgement calls, recorded because they are arguable
-------------------------------------------------------

**A SARL's `gerant` counts as a governing-body seat.** A SARL has no board;
the gerant *is* its governing organ, and the same person is normally an
associe. Excluding gerants would drop 10,304 gazette ties and most of the
private sector with them.

**A chief executive who is not stated to sit on the board does not count.**
`dg`, `dga` and `ceo` are management, and category 1 says "sitting at the
board". That excludes 952 gazette `dg` ties. Seed-file rows labelled CEO or
GENERAL MANAGER are in regardless, under requirement 6. `chef_de_cabinet` is
also out here: a cabinet chief is neither a member of the government nor a
board member, so the narrower list in this request drops him even though the
previous, broader decision-level cut kept him.

Colour and shape
----------------

Three hues, all-pairs validated against the paper surface (worst pair
#B5852A/#A03B2C, dE 15.9 deutan, 18.9 normal). Colour carries the sphere --
red for a person, gold for the political sphere, blue for the economic and
civic one -- and shape carries the entity type, so five classes are
distinguished without a fourth hue. A four-slot categorical palette was
tried and the validator refused it: #5B4E9E against #1B5FC1 is dE 8.9 in
normal vision, under the hard floor of 15.
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import os
import pickle
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D

PROC = ROOT / "data" / "processed" / "multiplex"
INTERIM = ROOT / "data" / "interim"
FIGS = ROOT / "figures"
FIGS.mkdir(exist_ok=True)
GRAPH = INTERIM / "elite_graph.pkl"
LAYOUT = INTERIM / "elite_graph_layout.pkl"

PERSON = "#A03B2C"
ORG = "#1B5FC1"
STATE = "#B5852A"
INK = "#1A1917"
MUTED = "#6C6D64"
RULE = "#D3D0C7"
PAPER = "#FCFCFB"

plt.rcParams.update({
    "figure.facecolor": PAPER, "axes.facecolor": PAPER,
    "savefig.facecolor": PAPER, "font.family": "DejaVu Sans",
    "font.size": 8.5, "axes.titlecolor": INK, "pdf.fonttype": 42,
    "legend.frameon": False,
})

# --- what each category admits -------------------------------------------- #
BOARD_OR_OWNER = {
    "administrateur", "administrateur_delegue", "president_ca", "pdg",
    "chairman", "gerant", "cogerant", "fondateur", "associe", "actionnaire",
    "owner", "shareholder", "president", "premier_responsable",
}
ASSOCIATION_OFFICER = {
    "association_president", "association_officer", "vice_president",
    "treasurer", "secretaire_general_adj",
}
GOVERNMENT_MEMBER = {"minister", "secretary_of_state", "chef_du_gouvernement"}
KEEP_ROLES = BOARD_OR_OWNER | ASSOCIATION_OFFICER | GOVERNMENT_MEMBER
# Tie classes admitted whatever the role: ownership (1), kinship (2),
# membership of a collegial body / party organ / bloc (3), and the seed
# sheet's own leadership, pedagogic, financial and structural classes (6).
KEEP_CLASSES = {"ownership", "kinship", "membership", "leadership",
                "pedagogic", "financial", "structural"}

CATEGORY = {
    "seed:corporate_officer": "6 · seed file",
    "seed:ownership": "6 · seed file",
    "seed:membership": "6 · seed file",
    "seed:kinship": "6 · seed file",
    "seed:financial": "6 · seed file",
    "seed:leadership": "6 · seed file",
    "seed:pedagogic": "6 · seed file",
    "seed:structural": "6 · seed file",
    "gazette:board_or_owner": "1 · shares or board seat",
    "gazette:ownership": "1 · shares or board seat",
    "gazette:kinship": "2 · family",
    "gazette:kinship_layer": "2 · family",
    "gazette:assoc_or_party": "3 · association board, party organ",
    "gazette:membership": "3 · association board, party organ",
    "gazette:government": "4 · government and parliament",
    "gazette:leadership": "3 · association board, party organ",
    "gazette:pedagogic": "6 · seed file",
    "org_ownership": "5 · organisation owns organisation",
}

STATE_RE = re.compile(
    r"MINISTERE|MINISTÈRE|PRESIDENCE|PRÉSIDENCE|GOUVERNORAT|MUNICIPALITE|"
    r"BANQUE CENTRALE|OFFICE NATIONAL|AGENCE NATIONALE|CAISSE NATIONALE|"
    r"ASSEMBLEE|ETAT TUNISIEN|SECRETARIAT", re.I)
ASSOC_RE = re.compile(
    r"ASSOCIATION|SYNDICAT|UNION |FONDATION|PARTI |CLUB |ORDRE DES|"
    r"CHAMBRE |FEDERATION|LIGUE|AMICALE", re.I)


def _iter(name: str):
    path = PROC / name
    if path.exists():
        with path.open(encoding="utf-8", newline="") as fh:
            yield from csv.DictReader(fh)
        return
    gz = PROC / (name + ".gz")
    if gz.exists():
        with gzip.open(gz, "rt", encoding="utf-8", newline="") as fh:
            yield from csv.DictReader(fh)


def build() -> dict:
    """Nodes, edges and the category each edge was admitted under."""
    seed_type: dict[str, str] = {}
    labels: dict[str, str] = {}
    for r in _iter("seed_nodes.csv"):
        seed_type[r["node_id"]] = r["node_type"]
        labels.setdefault(r["node_id"], r.get("label", ""))

    def kind(n: str) -> str:
        t = seed_type.get(n)
        if t:
            return "PERSON" if t == "PERSON" else "ORG"
        return "PERSON" if n.startswith(("PERSON_", "RNEP_")) else "ORG"

    edges: dict[tuple[str, str], str] = {}
    tally: collections.Counter = collections.Counter()

    def add(a: str, b: str, tag: str) -> None:
        if not a or not b or a == b:
            return
        e = (a, b) if a <= b else (b, a)
        if e not in edges:
            edges[e] = tag
            tally[tag] += 1

    # (6) every seed-file edge, unconditionally. Read from seed_edges.csv and
    # not from spells: 4,683 seed pairs are organisation-to-organisation and
    # a person-organisation spell table cannot hold them.
    for r in _iter("seed_edges.csv"):
        labels.setdefault(r["from_node_id"], r.get("from_label", ""))
        labels.setdefault(r["to_node_id"], r.get("to_label", ""))
        add(r["from_node_id"], r["to_node_id"],
            f"seed:{r.get('tie_class', 'other')}")

    # (1)-(4) gazette person ties, filtered by class or role
    for r in _iter("spells.csv"):
        if r["evidence_tier"] == "seed_undated":
            continue
        tc, ro = r["tie_class"], r["role_canonical"]
        if tc in KEEP_CLASSES:
            tag = f"gazette:{tc}"
        elif ro in GOVERNMENT_MEMBER:
            tag = "gazette:government"
        elif ro in ASSOCIATION_OFFICER:
            tag = "gazette:assoc_or_party"
        elif ro in BOARD_OR_OWNER:
            tag = "gazette:board_or_owner"
        else:
            tally[f"excluded:{tc}/{ro or 'blank'}"] += 1
            continue
        labels.setdefault(r["person_id"], r.get("person_label", ""))
        labels.setdefault(r["org_id"], r.get("org_label", ""))
        add(r["person_id"], r["org_id"], tag)

    # (2) the gazette kinship layer
    for r in _iter("person_tie_spells.csv"):
        labels.setdefault(r["person_id"], r.get("person_label", ""))
        labels.setdefault(r["kin_id"], r.get("kin_label", ""))
        add(r["person_id"], r["kin_id"], "gazette:kinship_layer")

    # (5) an organisation owning shares in an organisation
    for r in _iter("org_tie_spells.csv"):
        if r.get("is_ownership") != "1":
            continue
        labels.setdefault(r["holder_id"], r.get("holder_label", ""))
        labels.setdefault(r["target_id"], r.get("target_label", ""))
        add(r["holder_id"], r["target_id"], "org_ownership")

    adj: dict[str, set[str]] = collections.defaultdict(set)
    for a, b in edges:
        adj[a].add(b)
        adj[b].add(a)
    data = {"adj": {n: sorted(v) for n, v in adj.items()},
            "kind": {n: kind(n) for n in adj},
            "labels": labels, "seed_type": seed_type,
            "edges": {f"{a}\t{b}": t for (a, b), t in edges.items()},
            "tally": dict(tally)}
    INTERIM.mkdir(parents=True, exist_ok=True)
    with GRAPH.open("wb") as fh:
        pickle.dump(data, fh)
    return data


def layout(H) -> dict:
    """Force layout via igraph's C implementation.

    `nx.spring_layout` is not usable at this size: with scipy present it
    takes the sparse path, which loops over nodes in PYTHON once per
    iteration, so 23,808 nodes x 80 iterations is hours rather than minutes
    (measured: 20 minutes without finishing a single reported step). igraph
    runs the same Fruchterman-Reingold in C and returns in seconds.
    """
    import igraph as ig

    nodes = sorted(H)
    index = {n: i for i, n in enumerate(nodes)}
    print(f"  laying out {len(nodes):,} nodes with igraph…")
    g = ig.Graph(n=len(nodes),
                 edges=[(index[a], index[b]) for a, b in H.edges()])
    g.simplify()
    coords = g.layout_drl(seed=None, options={"simmer_attraction": 0.5})
    return {n: (float(coords[i][0]), float(coords[i][1]))
            for n, i in index.items()}


def node_class(n: str, kind: str, label: str, seed_type: dict) -> str:
    if kind == "PERSON":
        return "individual"
    t = seed_type.get(n, "")
    if t in ("PARTY", "PARTY STRUCTURE", "PARLIAMENTARY BLOC"):
        return "party / parliamentary bloc"
    if t in ("GOVERNMENT", "GOVERNMENTAL ORGANIZATION"):
        return "state body"
    if t == "ORGANIZATION":
        return "association / union"
    text = label or ""
    if n.startswith("GOV_") or STATE_RE.search(text):
        return "state body"
    if ASSOC_RE.search(text):
        return "association / union"
    return "company"


STYLE = {
    "individual": (PERSON, "o"),
    "company": (ORG, "s"),
    "association / union": (ORG, "^"),
    "state body": (STATE, "s"),
    "party / parliamentary bloc": (STATE, "D"),
}


def trim(s: str, n: int = 30) -> str:
    s = (s or "").strip()
    for a, b in (("MINISTERE DE L’", "Min. "), ("MINISTERE DE L'", "Min. "),
                 ("MINISTERE DES ", "Min. "), ("MINISTERE DE LA ", "Min. "),
                 ("MINISTERE DU ", "Min. "), ("PRESIDENCE DE LA ", "Présidence "),
                 ("PRÉSIDENCE DE LA ", "Présidence "), ("SOCIETE ", "Sté "),
                 ("'S CENTRAL COMMITTEE", " central cttee")):
        s = s.replace(a, b)
    if s.isupper():
        s = s.title()
    return s if len(s) <= n else s[: n - 1] + "…"


def place_labels(ax, items, *, fontsize=6.4, weight="semibold", placed=None):
    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    if placed is None:
        placed = []
    for text, (x, y) in items:
        for dx, dy in ((0, 10), (0, -12), (26, 3), (-26, 3), (0, 20), (0, -22)):
            ann = ax.annotate(
                text, (x, y), xytext=(dx, dy), textcoords="offset points",
                ha="center", va="center", fontsize=fontsize, color=INK,
                fontweight=weight,
                bbox=dict(boxstyle="round,pad=0.14", fc=PAPER, ec="none",
                          alpha=.9), zorder=6)
            bb = ann.get_window_extent(renderer=renderer)
            box = (bb.x0 - 1, bb.y0 - 1, bb.x1 + 1, bb.y1 + 1)
            if any(box[0] < p[2] and box[2] > p[0]
                   and box[1] < p[3] and box[3] > p[1] for p in placed):
                ann.remove()
                continue
            placed.append(box)
            break
    return placed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true",
                    help="rebuild the graph and the layout")
    ap.add_argument("--relayout", action="store_true")
    ap.add_argument("--labels", type=int, default=34,
                    help="how many of the largest nodes to name")
    args = ap.parse_args(argv)

    if GRAPH.exists() and not args.refresh:
        with GRAPH.open("rb") as fh:
            d = pickle.load(fh)
        print(f"  cache {GRAPH.relative_to(ROOT)}")
    else:
        print("  building the six-category graph…")
        d = build()

    adj = {n: set(v) for n, v in d["adj"].items()}
    kind, labels, seed_type = d["kind"], d["labels"], d["seed_type"]
    tally = d["tally"]
    cls = {n: node_class(n, kind[n], labels.get(n, ""), seed_type) for n in adj}
    deg = {n: len(v) for n, v in adj.items()}

    # An unlabelled organisation with 295 ties is OCR damage, not an entity.
    junk = {n for n in adj
            if cls[n] != "individual" and len((labels.get(n, "") or "").strip()) <= 3}

    G = nx.Graph()
    G.add_nodes_from(adj)
    for a, b in ((a, b) for a in adj for b in adj[a] if a < b):
        G.add_edge(a, b)
    giant = max(nx.connected_components(G), key=len)
    H = nx.Graph(G.subgraph(sorted(giant)))
    print(f"  graph {G.number_of_nodes():,} nodes / {G.number_of_edges():,} "
          f"edges; giant component {H.number_of_nodes():,}")

    if LAYOUT.exists() and not (args.refresh or args.relayout):
        with LAYOUT.open("rb") as fh:
            pos = pickle.load(fh)
        print(f"  cache {LAYOUT.relative_to(ROOT)}")
    else:
        pos = layout(H)
        with LAYOUT.open("wb") as fh:
            pickle.dump(pos, fh)
    pos = {n: p for n, p in pos.items() if n in H}

    fig, ax = plt.subplots(figsize=(15.0, 15.0))
    segs = [(pos[a], pos[b]) for a, b in H.edges()]
    ax.add_collection(LineCollection(segs, colors=RULE, linewidths=.16,
                                     alpha=.55, zorder=1))
    counts: dict[str, int] = {}
    order = ["company", "association / union", "party / parliamentary bloc",
             "state body", "individual"]
    for name in order:
        pool = [n for n in H if cls[n] == name]
        if not pool:
            continue
        colour, marker = STYLE[name]
        ax.scatter([pos[n][0] for n in pool], [pos[n][1] for n in pool],
                   s=[2.2 + deg[n] * 1.5 for n in pool], c=colour,
                   marker=marker, linewidths=.22, edgecolors=PAPER,
                   zorder=3 if name != "individual" else 2)
        counts[name] = len(pool)
    named = [n for n in sorted(H, key=lambda x: -deg[x]) if n not in junk]
    place_labels(ax, [(trim(labels.get(n, ""), 30), pos[n])
                      for n in named[:args.labels]], fontsize=6.6)
    ax.set_axis_off()
    ax.autoscale_view()
    # Fixed-size handles. Letting the legend reuse the scatter sizes drew a
    # marker as big as the largest node in each class, straight over the
    # legend's own title.
    leg = ax.legend(
        handles=[Line2D([], [], marker=STYLE[name][1], ls="none",
                        mfc=STYLE[name][0], mec=PAPER, mew=.5, ms=9,
                        label=f"{name} · {counts.get(name, 0):,}")
                 for name in order],
        loc="upper left", labelspacing=.85, handletextpad=.9, fontsize=9.5,
        labelcolor=INK, borderpad=.9,
        title="entity type, and how many are drawn")
    leg.get_title().set_fontsize(8.5)
    leg.get_title().set_color(MUTED)

    cats = collections.Counter()
    for tag, n in tally.items():
        if not tag.startswith("excluded:"):
            cats[CATEGORY.get(tag, tag)] += n
    excluded = sum(n for t, n in tally.items() if t.startswith("excluded:"))
    lines = [f"{k}  —  {v:,} ties" for k, v in sorted(cats.items())]
    ax.text(0.0, -0.005, "Ties admitted\n" + "\n".join(lines),
            transform=ax.transAxes, fontsize=7.6, color=INK, va="top",
            linespacing=1.6)
    ax.text(0.40, -0.005,
            f"Excluded: {excluded:,} gazette ties whose holder is a "
            f"government employee\nbelow the government, parliament and "
            f"board — chef de service, sous-directeur,\nsecrétaire général, "
            f"directeur général, conseiller, représentant, and the\nstate "
            f"offices whose rank is never stated. Also excluded: auditors\n"
            f"and liquidators, and chief executives not stated to sit on a "
            f"board.",
            transform=ax.transAxes, fontsize=7.6, color=MUTED, va="top",
            linespacing=1.6)

    fig.text(0.011, 0.995,
             "The Tunisian elite network: individuals, the organisations they "
             "own and govern, and their families",
             ha="left", va="top", fontsize=15.5, fontweight="bold", color=INK)
    fig.text(0.011, 0.972,
             f"{G.number_of_nodes():,} entities and {G.number_of_edges():,} "
             f"ties, 1957–2026, of which the largest connected component "
             f"({H.number_of_nodes():,} entities, "
             f"{100 * H.number_of_nodes() / G.number_of_nodes():.0f}%) is "
             f"drawn. Every node is one individual or one organisation — "
             f"nothing is aggregated. Node area ∝ ties.",
             ha="left", va="top", fontsize=9.0, color=MUTED)
    fig.text(0.011, 0.012,
             "Source: Journal Officiel de la République Tunisienne 1957–2026 "
             "(jort.tn), the Registre National des Entreprises, and a "
             "13,630-name elite roster. Author's extraction.\nA SARL's "
             "gérant counts as a governing-body seat, because a SARL has no "
             "board and the gérant is its governing organ; a chief executive "
             "not stated to sit on a board does not count.\nIndividuals "
             "outside the 13,630-name roster are mention clusters, so one "
             "node can be several namesakes — see docs/PROJECTION-multiplex.md.",
             ha="left", va="bottom", fontsize=6.8, color=MUTED,
             linespacing=1.6)
    fig.subplots_adjust(top=0.952, bottom=0.155, left=0.012, right=0.988)

    _write_tables(H, adj, cls, deg, labels, d)
    for ext, kw in (("png", {"dpi": 260}), ("pdf", {})):
        p = FIGS / f"fig12_elite_graph.{ext}"
        fig.savefig(p, **kw)
        print(f"  {p.relative_to(ROOT)}  {p.stat().st_size / 1024:.0f} KB")
    plt.close(fig)
    print(f"  classes: {', '.join(f'{k} {v:,}' for k, v in collections.Counter(cls[n] for n in adj).most_common())}")
    return 0


def _write_tables(H, adj, cls, deg, labels, d) -> None:
    """The graph itself, so it can be re-drawn in Gephi or igraph."""
    with (PROC / "elite_graph_nodes.csv").open("w", encoding="utf-8",
                                               newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["node_id", "label", "node_class", "degree",
                    "in_giant_component"])
        for n in sorted(adj):
            w.writerow([n, labels.get(n, ""), cls[n], deg[n], int(n in H)])
    with (PROC / "elite_graph_edges.csv").open("w", encoding="utf-8",
                                               newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["source", "target", "category"])
        for key, tag in sorted(d["edges"].items()):
            a, b = key.split("\t")
            w.writerow([a, b, CATEGORY.get(tag, tag)])
    print(f"  wrote {os.path.relpath(PROC / 'elite_graph_nodes.csv', ROOT)} "
          f"and elite_graph_edges.csv")


if __name__ == "__main__":
    raise SystemExit(main())
