"""The cumulative network at decision-making rank only.

Writes ``figures/fig11_decision_core.{png,pdf}``.

The companion to ``figure_giant_component.py``, and it reverses that
figure's headline. Unfiltered, the network looks like a state apparatus:
the Ministry of the Interior carries 5,600 ties and 82% of the innermost
core is state bodies. But a ministry accumulates ties by appointing
thousands of people, most of them *chefs de service* and *sous-directeurs*.

This figure applies a rank floor to the state side only -- minister and
above, the minister's cabinet chief, a governor, the head of a public
establishment, and the board level of a state-owned entity -- and keeps the
private sector whole, because a gerant of a SARL is the decision-maker of
his own firm.

What that does
--------------

The ministry hubs collapse by about 85% (Interior 5,600 -> 423, Finances
3,877 -> 710), and the cohesive core **inverts**: at k>=6 it holds no state
body at all. What is left is 188 nodes whose 84 individuals carry only 32
surnames -- Ben-Yedder 12, Elloumi 9, Abdelkefi 8, then Slama, Bouchamaoui,
Driss and Bayahi at 5 each.

So the state's apparent dominance of the network was an artefact of rank.
At decision-making level the densest structure in the Tunisian elite
network is a set of family-held business groups.

Colour
------

Person ``#A03B2C`` against organisation ``#1B5FC1``, all-pairs validated
(dE 23.6 protan, 27.9 normal), plus gold ``#B5852A`` for state bodies where
a third class is needed.

Family is deliberately NOT encoded in colour. The core holds 32 surnames,
and the validator settles the question rather than taste: the project's own
four-slot categorical palette fails an ALL-PAIRS check (#5B4E9E against
#1B5FC1, dE 8.9 normal vision, under the hard floor of 15). Adjacent-pair
validation is enough for a bar chart, where series sit in a fixed order; in
a node-link any two families can land side by side, so all-pairs is the
right test and only three hues survive it. Families are therefore separated
by the layout and named by direct labels.
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import json
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
from matplotlib.lines import Line2D

PROC = ROOT / "data" / "processed" / "multiplex"
INTERIM = ROOT / "data" / "interim"
FIGS = ROOT / "figures"
FIGS.mkdir(exist_ok=True)

PERSON = "#A03B2C"
ORG = "#1B5FC1"
STATE = "#B5852A"
RESIDUAL = "#C9C6BD"
INK = "#1A1917"
MUTED = "#6C6D64"
RULE = "#D3D0C7"
PAPER = "#FCFCFB"

plt.rcParams.update({
    "figure.facecolor": PAPER, "axes.facecolor": PAPER,
    "savefig.facecolor": PAPER, "font.family": "DejaVu Sans",
    "font.size": 8.5, "axes.edgecolor": RULE, "axes.labelcolor": INK,
    "axes.titlesize": 9.4, "axes.titleweight": "semibold",
    "axes.titlecolor": INK, "axes.titlelocation": "left", "axes.titlepad": 7,
    "axes.spines.top": False, "axes.spines.right": False,
    "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": MUTED,
    "ytick.labelcolor": MUTED, "xtick.major.size": 3, "ytick.major.size": 3,
    "grid.color": RULE, "grid.linewidth": 0.6, "legend.frameon": False,
    "legend.fontsize": 8, "pdf.fonttype": 42,
})

SOURCE = ("Source: Journal Officiel de la République Tunisienne 1957–2026 "
          "(jort.tn) joined to the Registre National des Entreprises, plus a "
          "13,630-name elite roster. Author's extraction; `make project`, "
          "tier `all_sources`, state floor `decision`.")

# Organisation labels that are extraction noise, not institutions. The short
# ones matter more here than in the unfiltered figure: removing the genuine
# ministry hubs promotes them to the top of the degree distribution.
ARTEFACT = {"ASSOCIATIONS, PARTIS, SYNDICATS ET SYNDICS", "Objectifs", "",
            "Directeur Général", "Directeur Général Adjoint"}
ROLE_LABEL = {
    "chef_de_service": "chef de service", "sous_directeur": "sous-directeur",
    "secretaire_general": "secrétaire général", "representant": "représentant",
    "administrateur": "administrateur (board)", "minister": "ministre",
    "dg": "directeur général (CEO)", "pdg": "PDG",
    "chef_du_gouvernement": "chef du gouvernement", "gouverneur": "gouverneur",
    "chef_de_cabinet": "chef de cabinet", "conseiller": "conseiller",
    "member": "membre", "president_ca": "président du CA",
    "secretary_of_state": "secrétaire d’État", "(none)": "no role stated",
    "dga": "DG adjoint", "director_general": "directeur général (ministry)",
}


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


def load(floor: str) -> dict:
    name = ("giant_component.pkl" if floor == "none"
            else "giant_component_decision.pkl")
    with (INTERIM / name).open("rb") as fh:
        return pickle.load(fh)


def role_breakdown(labels: dict[str, str], refresh: bool = False) -> dict:
    """Person-to-state-body ties by stated role, for panel (a)."""
    from elitenet import project as PJ
    cache = INTERIM / "state_role_breakdown.json"
    if cache.exists() and not refresh:
        with cache.open(encoding="utf-8") as fh:
            return json.load(fh)
    ent = {r["org_mention"]: r["org_entity_id"]
           for r in _iter("org_entity_members.csv") if r.get("org_mention")}
    is_state: dict[str, bool] = {}

    def state(node: str) -> bool:
        if node not in is_state:
            is_state[node] = PJ.is_state_body(node, labels.get(node, ""))
        return is_state[node]

    c: collections.Counter = collections.Counter()
    for r in _iter("spells.csv"):
        o = r.get("org_id", "")
        if o and state(o) and r.get("person_id"):
            c[(r.get("role_canonical") or "(none)")] += 1
    for r in _iter("resolution.csv"):
        if not (r.get("person_mention") or "").strip():
            continue
        e = ent.get((r.get("org_mention") or "").strip())
        if e and state(e):
            c[(r.get("role_observed") or "(none)")] += 1
    out = {"roles": dict(c), "kept": sorted(PJ.STATE_DECISION_ROLES)}
    INTERIM.mkdir(parents=True, exist_ok=True)
    with cache.open("w", encoding="utf-8") as fh:
        json.dump(out, fh)
    return out


def k_core(adj: dict[str, set[str]]) -> dict[str, int]:
    deg = {n: len(v) for n, v in adj.items()}
    buckets: dict[int, set[str]] = collections.defaultdict(set)
    for n, d in deg.items():
        buckets[d].add(n)
    core: dict[str, int] = {}
    remaining, k = set(adj), 0
    while remaining:
        while not buckets[k]:
            k += 1
        n = buckets[k].pop()
        if n not in remaining:
            continue
        core[n], _ = k, remaining.discard(n)
        for m in adj[n]:
            if m in remaining:
                buckets[deg[m]].discard(m)
                deg[m] = max(deg[m] - 1, k)
                buckets[deg[m]].add(m)
    return core


def surname(label: str) -> str:
    t = re.sub(r"[^A-Za-z \-]+", " ", (label or "")).upper()
    t = t.replace("-", " ").split()
    if not t:
        return ""
    # "BEN YEDDER", "HAJ ROMDHANE": the particle belongs to the surname.
    if len(t) >= 2 and t[-2] in ("BEN", "BEL", "ABOU", "ABU", "EL", "HAJ"):
        return f"{t[-2]} {t[-1]}"
    return t[-1]


def trim(s: str, n: int = 28) -> str:
    s = (s or "").strip()
    for a, b in (("MINISTERE DE L’", "Min. "), ("MINISTERE DE L'", "Min. "),
                 ("MINISTERE DES ", "Min. "), ("MINISTERE DE LA ", "Min. "),
                 ("MINISTERE DU ", "Min. "), ("MINISTERE ", "Min. "),
                 ("PRESIDENCE DE LA ", "Présidence "),
                 ("PRESIDENCE DU ", "Présidence "), ("SOCIETE ", "Sté ")):
        s = s.replace(a, b)
    if s.isupper():
        s = s.title()
    return s if len(s) <= n else s[: n - 1] + "…"


def place_labels(ax, items, *, fontsize=6.0, weight="normal", colour=None,
                 placed=None):
    """Annotate nodes, skipping any label that would collide with one already
    drawn.

    `placed` is threaded between calls on purpose. Two independent calls each
    kept their own collision list, so the second pass drew straight over the
    first -- family names landed on top of firm names. Callers pass the same
    list to every call and place the labels that matter most first.
    """
    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    if placed is None:
        placed = []
    for text, (x, y) in items:
        for dx, dy in ((0, 9), (0, -11), (22, 3), (-22, 3), (0, 18), (0, -20)):
            ann = ax.annotate(
                text, (x, y), xytext=(dx, dy), textcoords="offset points",
                ha="center", va="center", fontsize=fontsize,
                color=colour or INK, fontweight=weight,
                bbox=dict(boxstyle="round,pad=0.12", fc=PAPER, ec="none",
                          alpha=.88))
            bb = ann.get_window_extent(renderer=renderer)
            box = (bb.x0 - 1, bb.y0 - 1, bb.x1 + 1, bb.y1 + 1)
            if any(box[0] < p[2] and box[2] > p[0]
                   and box[1] < p[3] and box[3] > p[1] for p in placed):
                ann.remove()
                continue
            placed.append(box)
            break
    return placed


def headline(fig, title: str, subtitle: str) -> None:
    fig.text(0.011, 0.995, title, ha="left", va="top", fontsize=13.5,
             fontweight="bold", color=INK)
    fig.text(0.011, 0.963, subtitle, ha="left", va="top", fontsize=8.2,
             color=MUTED)


def save(fig, name: str, note: str) -> None:
    fig.text(0.011, 0.030, note, fontsize=6.4, color=MUTED, ha="left",
             va="top", linespacing=1.5)
    for ext, kw in (("png", {"dpi": 300}), ("pdf", {})):
        path = FIGS / f"{name}.{ext}"
        fig.savefig(path, bbox_inches="tight", pad_inches=0.26, **kw)
        print(f"  {path.relative_to(ROOT)}  {path.stat().st_size / 1024:.0f} KB")
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--core", type=int, default=6)
    args = ap.parse_args(argv)
    from elitenet import project as PJ

    print("loading…")
    A, B = load("none"), load("decision")
    labels = {**A["labels"], **B["labels"]}
    adjA = {n: set(v) for n, v in A["adj"].items()}
    adjB = {n: set(v) for n, v in B["adj"].items()}
    coreA, coreB = A["core"], k_core(adjB)
    kindB = B["kind"]

    def is_state(n):
        return PJ.is_state_body(n, labels.get(n, ""))

    fig = plt.figure(figsize=(13.2, 10.6))
    gs = fig.add_gridspec(2, 3, height_ratios=[0.82, 1.30], hspace=0.42,
                          wspace=0.46, top=0.876, bottom=0.175, left=0.085,
                          right=0.985)

    # ---------------- (a) what the floor removes ---------------------------
    ax = fig.add_subplot(gs[0, 0])
    bd = role_breakdown(labels, args.refresh)
    kept = set(bd["kept"])
    rows = sorted(bd["roles"].items(), key=lambda kv: kv[1])[-12:]
    y = np.arange(len(rows))
    ax.barh(y, [v for _k, v in rows], height=.68,
            color=[STATE if k in kept else RESIDUAL for k, _v in rows])
    ax.set_yticks(y, [ROLE_LABEL.get(k, k.replace("_", " ")) for k, _v in rows],
                  fontsize=6.8)
    for i, (k, v) in enumerate(rows):
        ax.annotate(f"{v:,}", (v, i), xytext=(4, 0),
                    textcoords="offset points", va="center", fontsize=6.6,
                    color=INK if k in kept else MUTED,
                    fontweight="semibold" if k in kept else "normal")
    ax.set_xscale("log")
    ax.set_xlabel("person-to-state-body ties (log)")
    ax.grid(axis="x", alpha=.5)
    tot_k = sum(v for k, v in bd["roles"].items() if k in kept)
    tot_d = sum(bd["roles"].values()) - tot_k
    ax.set_title("(a)  The floor drops five ties in six")
    ax.annotate(f"kept {tot_k:,} · dropped {tot_d:,}", (0.5, -0.235),
                xycoords="axes fraction", ha="center", va="top",
                fontsize=7.2, color=INK, fontweight="semibold")

    # ---------------- (b) the ministry hubs collapse -----------------------
    ax = fig.add_subplot(gs[0, 1])
    degA = {n: len(v) for n, v in adjA.items()}
    degB = {n: len(v) for n, v in adjB.items()}
    hubs = sorted((n for n in adjA if is_state(n)),
                  key=lambda n: -degA[n])[:10][::-1]
    y = np.arange(len(hubs))
    for i, n in enumerate(hubs):
        ax.plot([degB.get(n, 0), degA[n]], [i, i], color=RULE, lw=1.6,
                zorder=1, solid_capstyle="round")
    ax.scatter([degA[n] for n in hubs], y, s=34, color=RESIDUAL,
               zorder=2, edgecolor=PAPER, lw=.7, label="all ties")
    ax.scatter([degB.get(n, 0) for n in hubs], y, s=34, color=STATE,
               zorder=3, edgecolor=PAPER, lw=.7, label="decision-level only")
    ax.set_yticks(y, [trim(labels.get(n, ""), 20) for n in hubs], fontsize=6.6)
    ax.set_xscale("log")
    ax.set_xlabel("ties (log)")
    ax.grid(axis="x", alpha=.5)
    ax.legend(loc="lower right", handletextpad=.3)
    drop = 1 - sum(degB.get(n, 0) for n in hubs) / sum(degA[n] for n in hubs)
    ax.set_title(f"(b)  Ministry hubs lose {drop:.0%} of their ties")

    # ---------------- (c) the core inverts ---------------------------------
    ax = fig.add_subplot(gs[0, 2])
    for core, adj_, colour, lab_, ls in (
            (coreA, adjA, RESIDUAL, "all ties", (0, (4, 2))),
            (coreB, adjB, STATE, "decision-level only", "solid")):
        kmax = max(core.values())
        ks = list(range(1, kmax + 1))
        share = []
        for k in ks:
            orgs = [n for n in core
                    if core[n] >= k and not n.startswith(("PERSON_", "RNEP_"))]
            share.append(100 * sum(1 for n in orgs if is_state(n))
                         / max(len(orgs), 1))
        ax.plot(ks, share, color=colour, lw=2.4, ls=ls, marker="o", ms=4.2,
                mec=PAPER, mew=.8, clip_on=False, label=lab_)
        ax.annotate(f"{share[-1]:.0f}%", (ks[-1], share[-1]), xytext=(6, 0),
                    textcoords="offset points", ha="left", va="center",
                    fontsize=7.4, fontweight="semibold",
                    color=INK if colour == STATE else MUTED)
    ax.set_xlabel("restricted to the core at $k\\geq$")
    ax.set_ylabel("state share of core organisations (%)")
    ax.set_ylim(-4, 100)
    ax.grid(axis="y", alpha=.55)
    ax.legend(loc="upper left", handlelength=1.8)
    ax.set_title("(c)  …and the core stops being the state")

    # ---------------- (d) the decision-level core, drawn -------------------
    ax = fig.add_subplot(gs[1, :])
    K = args.core
    sel = [n for n in coreB if coreB[n] >= K
           and (labels.get(n, "") or "").strip() not in ARTEFACT
           and len((labels.get(n, "") or "").strip()) > 3]
    keep = set(sel)
    g = nx.Graph()
    g.add_nodes_from(sel)
    for n in sel:
        for m in adjB[n] & keep:
            if n < m:
                g.add_edge(n, m)
    g.remove_nodes_from([n for n in list(g) if g.degree(n) == 0])
    # The core is one 176-node block plus an 11-node island. A force layout
    # of both leaves the block in a corner and most of the panel empty, so
    # the block gets the whole panel and the island is named in the title.
    parts = sorted(nx.connected_components(g), key=len, reverse=True)
    aside = [sorted(c) for c in parts[1:]]
    g = nx.Graph(g.subgraph(sorted(parts[0])))
    pos = nx.spring_layout(g, seed=7, k=0.46, iterations=600, weight=None)

    people = [n for n in g if kindB[n] == "PERSON"]
    bodies = [n for n in g if kindB[n] != "PERSON"]
    fam = collections.Counter(surname(labels.get(p, "")) for p in people)

    nx.draw_networkx_edges(g, pos, ax=ax, edge_color=RULE, width=.6, alpha=.9)
    nx.draw_networkx_nodes(
        g, pos, nodelist=people, ax=ax, node_color=PERSON, node_shape="o",
        node_size=[16 + g.degree(n) * 4.0 for n in people],
        edgecolors=PAPER, linewidths=.6)
    nx.draw_networkx_nodes(
        g, pos, nodelist=bodies, ax=ax,
        node_color=[STATE if is_state(n) else ORG for n in bodies],
        node_shape="s",
        node_size=[24 + g.degree(n) * 5.0 for n in bodies],
        edgecolors=PAPER, linewidths=.75)

    # Family names first: they are the finding, so they get the space, and
    # the firm labels fill in around whatever is left.
    cents = []
    for name, _cnt in fam.most_common(14):
        pts = [pos[p] for p in people if surname(labels.get(p, "")) == name]
        if name and len(pts) >= 3:
            cents.append((f"{name.title()} ×{len(pts)}",
                          (float(np.mean([p[0] for p in pts])),
                           float(np.mean([p[1] for p in pts])))))
    taken = place_labels(ax, cents, fontsize=8.4, weight="bold",
                         colour=PERSON)
    place_labels(ax, [(trim(labels.get(n, ""), 24), pos[n])
                      for n in sorted(bodies, key=lambda n: -g.degree(n))[:40]],
                 fontsize=5.8, weight="semibold", placed=taken)
    ax.set_axis_off()
    away = sum(len(c) for c in aside)
    ax.set_title(
        f"(d)  The decision-level core is one interlocked block: "
        f"{len(people)} individuals and {len(bodies)} organisations, "
        f"{g.number_of_edges():,} ties, {len(fam)} surnames — the seven "
        f"largest carrying {sum(c for _n, c in fam.most_common(7))} of the "
        f"people. No state body survives in it."
        + (f"  ({away} further nodes, the Bouchamaoui group, form a separate "
           f"island and are not drawn.)" if away else ""), pad=12)
    ax.legend(handles=[
        Line2D([], [], marker="o", ls="none", mfc=PERSON, mec=PAPER, ms=7,
               label="individual (label = family, ×n members)"),
        Line2D([], [], marker="s", ls="none", mfc=ORG, mec=PAPER, ms=8,
               label="private firm"),
        Line2D([], [], marker="s", ls="none", mfc=STATE, mec=PAPER, ms=8,
               label="state body"),
    ], loc="upper left", borderpad=.3, handletextpad=.5, labelcolor=INK)

    n_state_core = sum(1 for n in bodies if is_state(n))
    headline(
        fig,
        "Strip the state to its decision-makers and the core of the Tunisian "
        "elite network is family business, not the bureaucracy",
        f"Same projection as fig10, with one change: a tie to a state body "
        f"counts only where the stated rank is minister or above, cabinet "
        f"chief, governor, head of a public body, or board level of a "
        f"state-owned entity. The private sector is untouched. The giant "
        f"component falls 200,991 → {len(adjB):,} nodes, and the k≥{K} core "
        f"holds {n_state_core} state bodies.")
    save(fig, "fig11_decision_core",
         SOURCE
         + f"\nFloor kept: {', '.join(bd['kept'])}."
         + f"\nFloor dropped: {PJ.STATE_BELOW_FLOOR_NOTE}. A tie whose rank "
           "is UNSTATED is dropped too — it cannot be shown to clear the "
           "floor — so these are a LOWER BOUND on decision-level ties, not a "
           "census. Secretaries of state and governors are counted as "
           "decision-makers; a ministry's directeur général and "
           "secrétaire général are not."
         + "\nPanel (d) also excludes organisation nodes whose label is "
           "three characters or fewer: removing the genuine ministry hubs "
           "promotes 390 such nodes (“S” at 536 ties, “M” at 431) to the top "
           "of the degree distribution, and they are OCR damage, not firms.")
    print(f"\n  decision giant component {len(adjB):,} nodes")
    print(f"  k>={K} core drawn: {len(people)} individuals, {len(bodies)} "
          f"organisations ({n_state_core} state), {g.number_of_edges():,} ties")
    print(f"  families: {', '.join(f'{n.title()} {c}' for n, c in fam.most_common(7))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
