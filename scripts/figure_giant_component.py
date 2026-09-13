"""The giant component of the cumulative JORT elite network, as one figure.

Writes ``figures/fig10_giant_component.{png,pdf}``.

Palette, typography and the label-placement helper deliberately mirror
``scripts/figures.py``. That script targets the other build under
``data/processed/``; this one reads ``data/processed/multiplex/`` and the
projection stage, so the two are kept separate rather than sharing a module
whose import loads four large frames this figure does not need.

Why the figure is not a node-link drawing of the network
--------------------------------------------------------

The giant component has 200,991 nodes. Drawn as a force layout that is a
hairball: it would show that the data is large and nothing else, and the
dense middle would read as structure where it is only overplotting.

The cohesive core is small enough to draw -- 193 nodes at k>=7 -- and a
node-link panel of it was built first. It was thrown away, for a reason
worth recording: collapsing its 127 individuals into ties between the 63
organisations they share gives a graph of **density 0.594**. Every ministry
shares personnel with nearly every other, so the "network" of the core is
close to complete, and a node-link drawing of a near-complete graph on 63
long ministry names is a hairball with labels on it. A near-complete
weighted graph wants a MATRIX, so panel (d) is one, ordered by core degree.

That near-completeness is itself the finding: the core is not a set of
ministerial cliques but one integrated cadre.

Colour
------

Three hues, all-pairs validated against the paper surface (worst pair
#B5852A/#A03B2C, dE 15.9 deutan, 18.9 normal):

* **identity** -- person ``#A03B2C`` against organisation ``#1B5FC1``, the
  same two slots the rest of the project uses.
* **the finding** -- state bodies in ``#B5852A``, because panel (c) is an
  organisations-only decomposition where every bar would otherwise be the
  one organisation colour. Gold marks the state, blue stays the ordinary
  organisation, grey is the residual.

Nothing is identified by colour alone: every series is directly labelled and
node rank is reinforced by size.
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
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

PROC = ROOT / "data" / "processed" / "multiplex"
INTERIM = ROOT / "data" / "interim"
FIGS = ROOT / "figures"
FIGS.mkdir(exist_ok=True)
CACHE = INTERIM / "giant_component.pkl"

# --- palette (mirrors scripts/figures.py) ----------------------------------
PERSON = "#A03B2C"
ORG = "#1B5FC1"
STATE = "#B5852A"
RESIDUAL = "#C9C6BD"
INK = "#1A1917"
MUTED = "#6C6D64"
RULE = "#D3D0C7"
PAPER = "#FCFCFB"

plt.rcParams.update({
    "figure.facecolor": PAPER,
    "axes.facecolor": PAPER,
    "savefig.facecolor": PAPER,
    "font.family": "DejaVu Sans",
    "font.size": 8.5,
    "axes.edgecolor": RULE,
    "axes.labelcolor": INK,
    "axes.titlesize": 9.4,
    "axes.titleweight": "semibold",
    "axes.titlecolor": INK,
    "axes.titlelocation": "left",
    "axes.titlepad": 7,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "xtick.labelcolor": MUTED,
    "ytick.labelcolor": MUTED,
    "xtick.major.size": 3,
    "ytick.major.size": 3,
    "grid.color": RULE,
    "grid.linewidth": 0.6,
    "legend.frameon": False,
    "legend.fontsize": 8,
    "pdf.fonttype": 42,
})

# Sequential = one hue, light to dark. Built from the organisation blue so the
# matrix reads as a magnitude on the organisation mode rather than as a new
# categorical identity.
SHARED = LinearSegmentedColormap.from_list(
    "shared", ["#F2F4F8", "#C3D4EC", "#84A8DA", "#3F76C0", "#17408A"])

SOURCE = ("Source: Journal Officiel de la République Tunisienne 1957–2026 "
          "(jort.tn) joined to the Registre National des Entreprises on the "
          "matricule fiscal and RC number, plus a 13,630-name elite roster. "
          "Author's extraction; `make project`, tier `all_sources`.")

# Labels that are extraction noise rather than entities. They are drawn and
# marked rather than deleted: three of the twenty highest-degree
# organisations in this component are artefacts, and a reader who is not told
# that will read them as findings.
ARTEFACT_LABELS = {
    "ASSOCIATIONS, PARTIS, SYNDICATS ET SYNDICS",  # a gazette rubric heading
    "Objectifs",                                    # a clause word
    "Directeur Général", "Directeur Général Adjoint",  # role titles as people
    "",                                             # an unlabelled node
}

# Panel (e). "Mohamed" is the commonest Tunisian male given name, so a node
# that carries it is the likeliest to be several men merged into one. Testing
# the association between bridging rank and that one name turns a suspicion
# into a measurement.
MOHAMED = {"MOHAMED", "MOHAMMED", "MHAMED"}

STATE_WORDS = (
    "MINISTERE", "MINISTÈRE", "PRESIDENCE", "PRÉSIDENCE", "SECRETARIAT D'ETAT",
    "GOUVERNORAT", "MUNICIPALITE", "BANQUE CENTRALE", "OFFICE NATIONAL",
    "AGENCE NATIONALE", "CAISSE NATIONALE", "ASSEMBLEE", "CONSEIL SUPERIEUR",
)


def _iter(name: str, base: Path = PROC):
    path = base / name
    if path.exists():
        with path.open(encoding="utf-8", newline="") as fh:
            yield from csv.DictReader(fh)
        return
    gz = base / (name + ".gz")
    if gz.exists():
        with gzip.open(gz, "rt", encoding="utf-8", newline="") as fh:
            yield from csv.DictReader(fh)


def k_core_numbers(adj: dict[str, set[str]]) -> dict[str, int]:
    """Core number per node, by repeated peeling of the lowest-degree node.

    Written out rather than taken from networkx because the graph is built as
    plain dict-of-sets for memory: 200,991 nodes and 258,931 edges as a
    networkx object costs several times more.
    """
    deg = {n: len(v) for n, v in adj.items()}
    buckets: dict[int, set[str]] = collections.defaultdict(set)
    for n, d in deg.items():
        buckets[d].add(n)
    core: dict[str, int] = {}
    remaining = set(adj)
    k = 0
    while remaining:
        while not buckets[k]:
            k += 1
        n = buckets[k].pop()
        if n not in remaining:
            continue
        core[n] = k
        remaining.discard(n)
        for m in adj[n]:
            if m in remaining:
                buckets[deg[m]].discard(m)
                deg[m] = max(deg[m] - 1, k)
                buckets[deg[m]].add(m)
    return core


def load_labels() -> dict[str, str]:
    """Best available display name per node id, cheapest source first."""
    lab: dict[str, str] = {}
    for r in _iter("seed_nodes.csv"):
        lab.setdefault(r["node_id"], r.get("label", ""))
    for r in _iter("org_entities.csv"):
        lab.setdefault(r["org_entity_id"], r.get("label", ""))
    for r in _iter("spells.csv"):
        lab.setdefault(r["person_id"], r.get("person_label", ""))
        lab.setdefault(r["org_id"], r.get("org_label", ""))
    for r in _iter("rne_company_forms.csv"):
        name = r.get("rne_name_fr") or r.get("jort_label", "")
        if r.get("org_entity_id"):
            lab.setdefault(r["org_entity_id"], name)
        lab.setdefault("RNE_" + r["company_key"], name)
    for r in _iter("rne_company_persons.csv"):
        lab.setdefault(r["person_key"], r.get("person_label", ""))
    for r in _iter("resolution.csv"):
        c = r.get("mention_cluster_id")
        if c:
            lab.setdefault(c, r.get("person_mention", ""))
    return lab


def build(refresh: bool = False) -> dict:
    """The giant component with degree, core number and class per node.

    Cached: `project.build` reads events, resolution and both register tables,
    which takes minutes, and a figure gets re-rendered many times while its
    layout is being settled.
    """
    if CACHE.exists() and not refresh:
        print(f"  cache {CACHE.relative_to(ROOT)}")
        with CACHE.open("rb") as fh:
            return pickle.load(fh)

    from elitenet import project as PJ
    print("  building the all_sources projection (a few minutes)…")
    g, _diag = PJ.build("all_sources")
    comp, _sizes = g.label_components()
    giant_id = collections.Counter(comp.values()).most_common(1)[0][0]
    keep = {n for n, c in comp.items() if c == giant_id}
    adj = {n: (g.adj[n] & keep) for n in keep}
    print(f"  giant component {len(keep):,} nodes; peeling…")
    data = {
        "adj": {n: sorted(v) for n, v in adj.items()},
        "kind": {n: g.kind[n] for n in keep},
        "deg": {n: len(v) for n, v in adj.items()},
        "core": k_core_numbers(adj),
        "labels": load_labels(),
    }
    INTERIM.mkdir(parents=True, exist_ok=True)
    with CACHE.open("wb") as fh:
        pickle.dump(data, fh)
    return data


def classify(node: str, kind: str, label: str, private: set[str]) -> str:
    if kind == "PERSON":
        return "person"
    upper = (label or "").upper()
    if node.startswith("GOV_") or any(w in upper for w in STATE_WORDS):
        return "state"
    if node in private:
        return "private"
    return "other"


def private_firms() -> set[str]:
    out: set[str] = set()
    for r in _iter("rne_company_forms.csv"):
        if r.get("org_entity_id"):
            out.add(r["org_entity_id"])
        out.add("RNE_" + r["company_key"])
    return out


def place_labels(ax, items, *, fontsize=6.2, weight="normal"):
    """Annotate nodes, skipping any label that would collide.

    Taken from scripts/figures.py: a stack of overlapping names is worse than
    naming fewer institutions.
    """
    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    placed: list[tuple[float, float, float, float]] = []
    for text, (x, y) in items:
        for dx, dy in ((0, 10), (0, -12), (24, 3), (-24, 3), (0, 20), (0, -22)):
            ann = ax.annotate(
                text, (x, y), xytext=(dx, dy), textcoords="offset points",
                ha="center", va="center", fontsize=fontsize, color=INK,
                fontweight=weight,
                bbox=dict(boxstyle="round,pad=0.14", fc=PAPER, ec="none",
                          alpha=.86),
            )
            bb = ann.get_window_extent(renderer=renderer)
            box = (bb.x0 - 1, bb.y0 - 1, bb.x1 + 1, bb.y1 + 1)
            if any(box[0] < p[2] and box[2] > p[0]
                   and box[1] < p[3] and box[3] > p[1] for p in placed):
                ann.remove()
                continue
            placed.append(box)
            break


def _fold_name(text: str) -> list[str]:
    """Accent-stripped upper-case tokens, for the given-name test."""
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^A-Za-z ]+", " ", t).upper().split()


def trim(s: str, n: int = 30) -> str:
    s = (s or "").strip()
    s = s.replace("MINISTERE DE L’", "Min. ").replace("MINISTERE DE L'", "Min. ")
    s = s.replace("MINISTERE DES ", "Min. ").replace("MINISTERE DE LA ", "Min. ")
    s = s.replace("MINISTERE DU ", "Min. ").replace("MINISTERE ", "Min. ")
    s = s.replace("PRESIDENCE DE LA ", "Présidence ").replace("PRESIDENCE DU ", "Présidence ")
    if s.isupper():
        s = s.title()
    return s if len(s) <= n else s[: n - 1] + "…"


def headline(fig, title: str, subtitle: str, *, top: float = 0.995) -> None:
    fig.text(0.011, top, title, ha="left", va="top",
             fontsize=13.5, fontweight="bold", color=INK)
    fig.text(0.011, top - 0.030, subtitle, ha="left", va="top",
             fontsize=8.2, color=MUTED)


def save(fig, name: str, note: str) -> None:
    fig.text(0.011, 0.028, note, fontsize=6.4, color=MUTED,
             ha="left", va="top", linespacing=1.5)
    for ext, kw in (("png", {"dpi": 300}), ("pdf", {})):
        path = FIGS / f"{name}.{ext}"
        fig.savefig(path, bbox_inches="tight", pad_inches=0.26, **kw)
        print(f"  {path.relative_to(ROOT)}  {path.stat().st_size / 1024:.0f} KB")
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true",
                    help="rebuild the projection instead of using the cache")
    ap.add_argument("--core", type=int, default=7,
                    help="core number of the sub-network drawn in panel (d)")
    args = ap.parse_args(argv)

    print("loading…")
    d = build(args.refresh)
    adj = {n: set(v) for n, v in d["adj"].items()}
    kind, deg, core, labels = d["kind"], d["deg"], d["core"], d["labels"]
    private = private_firms()
    cls = {n: classify(n, kind[n], labels.get(n, ""), private) for n in adj}

    n_person = sum(1 for n in adj if kind[n] == "PERSON")
    n_org = len(adj) - n_person
    n_edge = sum(deg.values()) // 2
    kmax = max(core.values())

    fig = plt.figure(figsize=(13.0, 10.4))
    gs = fig.add_gridspec(
        2, 3, height_ratios=[0.80, 1.34], hspace=0.40, wspace=0.36,
        top=0.876, bottom=0.205, left=0.075, right=0.985)

    # ---------------- (a) how the component peels --------------------------
    ax = fig.add_subplot(gs[0, 0])
    ks = list(range(1, kmax + 1))
    tot = [sum(1 for n in core if core[n] >= k) for k in ks]
    per = [sum(1 for n in core if core[n] >= k and kind[n] == "PERSON")
           for k in ks]
    org = [t - p for t, p in zip(tot, per)]
    ax.plot(ks, per, color=PERSON, lw=2, marker="o", ms=4.5,
            mec=PAPER, mew=.8, label="individuals", clip_on=False)
    ax.plot(ks, org, color=ORG, lw=2, marker="s", ms=4.2,
            mec=PAPER, mew=.8, label="organisations", clip_on=False)
    ax.set_yscale("log")
    ax.set_xlabel("core number $k$ (nodes with $k$ or more ties inside the core)")
    ax.set_ylabel("nodes remaining")
    ax.set_xticks(ks)
    ax.grid(axis="y", alpha=.55)
    ax.legend(loc="lower left", handlelength=1.6)
    ax.annotate(f"$k\\geq{kmax}$: {tot[-1]:,} nodes,\n"
                f"{100 * tot[-1] / len(adj):.2f}% of the component",
                (ks[-1], tot[-1]), xytext=(0.97, 0.93),
                textcoords="axes fraction", ha="right", va="top",
                fontsize=7.2, color=INK,
                arrowprops=dict(arrowstyle="-", color=MUTED, lw=.7,
                                shrinkB=3,
                                connectionstyle="arc3,rad=0.18"))
    ax.set_title("(a)  It peels to almost nothing")

    # ---------------- (b) degree distribution ------------------------------
    ax = fig.add_subplot(gs[0, 1])
    for pool, colour, lab_, marker in (
            ([n for n in adj if kind[n] == "PERSON"], PERSON, "individuals", "o"),
            ([n for n in adj if kind[n] != "PERSON"], ORG, "organisations", "s")):
        v = np.sort(np.array([deg[n] for n in pool]))
        ccdf = 1.0 - np.arange(len(v)) / len(v)
        ax.plot(v, ccdf, color=colour, lw=1.8, label=lab_, solid_capstyle="round")
        del marker
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("ties (degree)")
    ax.set_ylabel("share with at least this many")
    ax.grid(alpha=.5)
    ax.legend(loc="lower left", handlelength=1.6)
    share1 = sum(1 for n in adj if deg[n] == 1) / len(adj)
    ax.annotate(f"{share1:.0%} of all nodes\nhave exactly one tie",
                (1, 1), xytext=(0.97, 0.97), textcoords="axes fraction",
                ha="right", va="top", fontsize=7.2, color=INK,
                arrowprops=dict(arrowstyle="-", color=MUTED, lw=.7,
                                shrinkB=2, connectionstyle="arc3,rad=-0.25"))
    hub = max(adj, key=lambda n: deg[n] if kind[n] != "PERSON" else -1)
    ax.annotate(f"{trim(labels.get(hub, ''), 26)}  ({deg[hub]:,})",
                (deg[hub], 1 / max(1, n_org)), xytext=(-4, 18),
                textcoords="offset points", ha="right", fontsize=6.8,
                color=ORG, arrowprops=dict(arrowstyle="-", color=MUTED, lw=.7))
    ax.set_title("(b)  A long tail on both modes")

    # ---------------- (c) what the core is made of -------------------------
    ax = fig.add_subplot(gs[0, 2])
    levels = [("all", 1), (f"$k\\geq{kmax - 1}$", kmax - 1), (f"$k\\geq{kmax}$", kmax)]
    series = {"state": [], "private": [], "other": []}
    for _name, k in levels:
        sel = [n for n in core if core[n] >= k and kind[n] != "PERSON"]
        c = collections.Counter(cls[n] for n in sel)
        for key in series:
            series[key].append(100 * c[key] / max(len(sel), 1))
    x = np.arange(len(levels))
    for key, colour, lab_, weight in (
            ("state", STATE, "state bodies", "bold"),
            ("private", ORG, "private firms", "normal"),
            ("other", RESIDUAL, "other bodies", "normal")):
        ax.plot(x, series[key], color=colour, lw=2.6 if key == "state" else 1.8,
                marker="o", ms=5.5, mec=PAPER, mew=.9, clip_on=False, zorder=3)
        dy = {"state": 0, "private": -11, "other": 12}[key]
        ax.annotate(f"{lab_}  {series[key][-1]:.0f}%", (x[-1], series[key][-1]),
                    xytext=(9, dy), textcoords="offset points", ha="left",
                    va="center", fontsize=7.2, fontweight=weight,
                    color=INK if key != "other" else MUTED)
        ax.annotate(f"{series[key][0]:.1f}%", (x[0], series[key][0]),
                    xytext=(-8, 0), textcoords="offset points", ha="right",
                    va="center", fontsize=7.0, color=MUTED)
    ax.set_xticks(x, [n for n, _ in levels])
    ax.set_xlim(-0.34, len(levels) - 0.30)
    ax.set_ylim(-4, 100)
    ax.set_ylabel("share of organisations (%)")
    ax.set_xlabel("restricted to the core at")
    ax.grid(axis="y", alpha=.55)
    ax.set_title("(c)  The core is the state")

    # ---------------- (d) the organisation interlock matrix ----------------
    # A near-complete weighted graph (density 0.594) read as a matrix rather
    # than drawn as a node-link. Artefact nodes are excluded here: an
    # unlabelled row would be unreadable and a rubric heading is not an
    # institution. They are counted in the note instead.
    ax = fig.add_subplot(gs[1, :2])
    K = min(args.core, kmax)
    sel = set(n for n in core if core[n] >= K)
    bodies = [n for n in sel if kind[n] != "PERSON"
              and (labels.get(n, "") or "").strip() not in ARTEFACT_LABELS]
    people = [n for n in sel if kind[n] == "PERSON"
              and (labels.get(n, "") or "").strip() not in ARTEFACT_LABELS]
    n_arte = len(sel) - len(bodies) - len(people)

    top = sorted(bodies, key=lambda n: -len(adj[n] & sel))[:24]
    idx = {n: i for i, n in enumerate(top)}
    M = np.zeros((len(top), len(top)))
    for p in people:
        touched = sorted(idx[o] for o in adj[p] & set(top))
        for i, a in enumerate(touched):
            for b in touched[i + 1:]:
                M[a, b] += 1
                M[b, a] += 1
    np.fill_diagonal(M, np.nan)

    im = ax.imshow(M, cmap=SHARED, vmin=0, aspect="auto",
                   interpolation="nearest")
    names = [trim(labels.get(n, ""), 34) for n in top]
    ax.set_xticks(range(len(top)), names, rotation=90, fontsize=5.9)
    ax.set_yticks(range(len(top)), names, fontsize=5.9)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks(np.arange(-.5, len(top), 1), minor=True)
    ax.set_yticks(np.arange(-.5, len(top), 1), minor=True)
    ax.grid(which="minor", color=PAPER, lw=1.1)
    ax.tick_params(which="minor", length=0)
    cb = fig.colorbar(im, ax=ax, fraction=0.030, pad=0.015)
    cb.set_label("core individuals the pair shares", fontsize=7, color=MUTED)
    cb.ax.tick_params(labelsize=6.5, length=2, color=RULE)
    cb.outline.set_visible(False)
    off = M[~np.isnan(M)]
    filled = float((off > 0).sum()) / off.size
    ax.set_title("(d)  One cadre, not a set of ministerial cliques", pad=17)
    ax.annotate(f"{filled:.0%} of the {len(top)}×{len(top)} ministry pairs "
                f"share at least one individual in the core",
                (0.0, 1.012), xycoords="axes fraction", ha="left",
                va="bottom", fontsize=7.2, color=MUTED)

    # ---------------- (e) the person side is not trustworthy ---------------
    ax = fig.add_subplot(gs[1, 2])
    bridges = {p: len(adj[p] & set(bodies)) for p in people}
    rank = sorted(people, key=lambda p: -bridges[p])

    def given(node: str) -> str:
        tok = _fold_name(labels.get(node, ""))
        return tok[0] if tok else ""

    base = 100 * sum(1 for p in people if given(p) in MOHAMED) / max(len(people), 1)
    ks = list(range(5, len(rank) + 1))
    share = [100 * sum(1 for p in rank[:k] if given(p) in MOHAMED) / k for k in ks]
    ax.plot(ks, share, color=PERSON, lw=2.2, solid_capstyle="round")
    ax.axhline(base, color=MUTED, lw=1, ls=(0, (4, 3)))
    ax.annotate(f"base rate in the core: {base:.0f}%", (len(rank), base),
                xytext=(-2, -12), textcoords="offset points", ha="right",
                va="top", fontsize=6.8, color=MUTED)
    ax.annotate(f"{share[0]:.0f}% of the\ntop {ks[0]} bridges", (ks[0], share[0]),
                xytext=(14, -2), textcoords="offset points", ha="left",
                va="top", fontsize=7.0, color=INK)
    named = ", ".join(trim(labels.get(p, ""), 22) for p in rank[:3])
    ax.annotate(f"The three widest-bridging nodes are\n{named} — one given "
                f"name,\nthree surnames, and between them\n"
                f"{sum(bridges[p] for p in rank[:3])} ties into "
                f"{len(set().union(*[adj[p] & set(bodies) for p in rank[:3]]))} "
                f"of the {len(bodies)} core bodies.\n\n"
                f"Read them as merged homonyms, not brokers.",
                (0.045, 0.05), xycoords="axes fraction", ha="left",
                va="bottom", fontsize=6.9, color=MUTED, linespacing=1.55)
    ax.set_ylim(0, 104)
    ax.set_xlim(0, len(rank))
    ax.set_xlabel("individuals ranked by bodies bridged (top $k$)")
    ax.set_ylabel("share named “Mohamed …” (%)")
    ax.grid(axis="y", alpha=.55)
    ax.set_title("(e)  …but its people are homonyms")

    n_state_core = sum(1 for n in bodies if cls[n] == "state")
    n_state_all = sum(1 for n in adj if cls[n] == "state")
    headline(
        fig,
        "The cumulative Tunisian elite network holds together through the "
        "state, and its core is one integrated cadre",
        f"Giant component of every layer projected into one graph: "
        f"{len(adj):,} nodes — {n_person:,} individuals and {n_org:,} "
        f"organisations — joined by {n_edge:,} ties, 1957–2026. Of the "
        f"{n_org:,} organisations only {n_state_all:,} are state bodies "
        f"({100 * n_state_all / n_org:.1f}%), but they are {n_state_core} of "
        f"the {len(bodies)} organisations in the innermost core.")
    save(fig, "fig10_giant_component",
         SOURCE + f"\nPanel (d) excludes {n_arte} nodes in the k≥{K} core "
         "that are extraction artefacts rather than entities: the rubric "
         "heading “Associations, partis, syndicats et syndics”, the clause "
         "word “Objectifs”, and one unlabelled node."
         "\nCaveat: at this tier a person–organisation tie is a CO-MENTION — "
         "both named in one filing — not a dated appointment, so the "
         "component is an outer bound on who is connected to whom. Panel (e) "
         "is why the person side of the core should not be read as a list of "
         "brokers: individuals outside the elite roster are mention clusters, "
         "so one node can be several men who share a name.")
    print(f"\n  k>={K} core: {len(people)} individuals, {len(bodies)} bodies "
          f"({n_state_core} state), {n_arte} artefacts excluded")
    print(f"  matrix {len(top)}x{len(top)}: {filled:.1%} of pairs non-zero")
    print(f"  homonym: top {ks[0]} bridges {share[0]:.0f}% Mohamed vs "
          f"{base:.0f}% base rate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
