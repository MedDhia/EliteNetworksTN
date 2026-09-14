"""Percolation / resilience dataset and harness for the pre-2011 network.

Writes, under ``data/processed/percolation/``:

===============================  ====================================
``pre2011_nodes.csv``            one row per node, with the attributes
                                 every strategy below needs
``pre2011_edges.csv``            undirected dyads, with tie kind and the
                                 number of spells behind each
``pre2011.graphml``              the whole graph, attributes attached
``pre2011_lcc.graphml``          the largest connected component only
``pre2011_attack_orders.csv``    removal rank per node for every *static*
                                 strategy
``pre2011_percolation_SCOPE.csv``  the curves, per --scope
``README.md``                    column dictionary and the caveats
===============================  ====================================

Strategies, and where they come from
------------------------------------

Static (precomputable, and shipped as an explicit order):

* ``random``          -- Albert, Jeong & Barabasi 2000, *Nature* 406:378.
                         Averaged over ``--replicates`` seeded draws.
* ``degree``          -- initial degree, "ID" in Holme, Kim, Yoon & Han
                         2002, *Phys. Rev. E* 65:056109.
* ``betweenness``     -- initial betweenness, "IB" in Holme et al. 2002.
* ``eigenvector``     -- Restrepo, Ott & Hunt 2006, *PRL* 97:094102.
* ``closeness``       -- Iyer, Killingback, Sundaram & Wang 2013,
                         *PLoS ONE* 8:e59613.
* ``coreness``        -- k-shell, Kitsak et al. 2010, *Nature Physics*
                         6:888.
* ``participation``   -- inter-module ties first; Guimera & Amaral 2005,
                         *Nature* 433:895.

Adaptive (the order depends on removals already made, so it cannot be
shipped as a list and is computed at run time):

* ``degree_recalc``      -- "RD" in Holme et al. 2002.
* ``betweenness_recalc`` -- "RB" in Holme et al. 2002.

Substantive, specific to a two-mode elite network rather than to the
percolation literature:

* ``state_first``, ``orgs_first``, ``persons_first`` -- remove one class
  of entity before the others, each class internally ordered by degree.
  These answer "what happens if the state apparatus is removed" rather
  than "what happens under an optimal attack".

What to be careful about
------------------------

**The graph is fragmented before anything is removed.** 9,734 nodes in
2,610 components, the largest holding 2,509 (25.8%). A percolation curve
over the whole graph therefore starts at S = 0.26, not 1.0, and the usual
reading of the critical point does not apply. Both scopes are provided:
``--scope lcc`` (the default, and what the literature almost always
means) restricts to the largest component so curves start at 1.0;
``--scope full`` keeps every node.

**The largest component is very nearly a tree, so it has almost no
redundancy to lose.** 2,509 nodes carry 2,921 ties: 413 independent
cycles, 60.9% of nodes at degree 1, and 687 articulation points, any one of
which disconnects the graph. Every strategy therefore looks devastating,
and targeted ones halve the component after removing 1% of nodes. That is
a property of the topology, not an artefact -- but it means the interesting
comparison here is *between* strategies, not the absolute collapse point.

**Clustering is near zero because the graph is two-mode.** Persons tie to
organisations, so triangles are almost structurally impossible and
transitivity is 0.0002. Resilience measures that assume a one-mode network
with meaningful clustering should not be read off this graph; the
two-mode-appropriate comparison is the class-first strategies below.

**Recalculated strategies are batched.** Recomputing betweenness after
every single removal is 2,509 betweenness computations; the cost is in
``--recalc-every`` (default 10 removals), which is an approximation and is
recorded in the output.

**Betweenness here is not the pooled figure's betweenness.** It is
recomputed on this graph, as it must be.

**The date cut is also a source cut** -- see ``elitenet.dated_graph`` and
``docs/PERCOLATION-pre2011.md``. Ownership, kinship and membership ties
are absent because the roster recording them is undated, so this measures
the resilience of the *gazette-evidenced* network, not of every relation
that existed before 2011.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import igraph as ig
import numpy as np

from elitenet.dated_graph import build

OUT = ROOT / "data" / "processed" / "percolation"
CUT = "2011-01-14"

STATIC = ["random", "degree", "betweenness", "eigenvector", "closeness",
          "coreness", "participation"]
ADAPTIVE = ["degree_recalc", "betweenness_recalc"]
CLASS_FIRST = {"state_first": "state", "orgs_first": None,
               "persons_first": "person"}


def graph_of(d: dict) -> ig.Graph:
    g = ig.Graph(n=len(d["nodes"]), edges=d["edges"])
    g.vs["name"] = d["nodes"]
    g.vs["label"] = d["labels"]
    g.vs["node_class"] = d["cls"]
    g.es["tie_kind"] = d["kind"]
    g.es["n_spells"] = d["spells"]
    return g


def attributes(g: ig.Graph, seed: int = 7) -> dict[str, list]:
    """Everything the static strategies rank on, computed on ``g``."""
    ig.set_random_number_generator(random.Random(seed))
    comps = g.connected_components()
    sizes = comps.sizes()
    giant = int(np.argmax(sizes))
    membership = comps.membership
    comm = g.community_multilevel().membership

    # Closeness is undefined across components; igraph returns nan. Rank
    # on within-component closeness, which is what the measure means here.
    closeness = g.closeness(normalized=True)
    closeness = [0.0 if c is None or np.isnan(c) else c for c in closeness]

    # Eigenvector centrality is undefined across components -- igraph warns
    # and returns near-zeros for every node when handed a disconnected
    # graph. Computed within each component instead, so the value is
    # meaningful inside a component; it is NOT comparable across them.
    eig = [0.0] * g.vcount()
    with warnings.catch_warnings():
        # igraph warns that the measure is meaningless on a disconnected
        # graph. That is exactly why this loops over components; inside a
        # tree-shaped component the leading eigenvector is still degenerate
        # enough to warn, and the values remain usable as a within-component
        # ranking, which is all any strategy here needs.
        warnings.simplefilter("ignore", RuntimeWarning)
        for comp in comps:
            if len(comp) == 1:
                continue
            sub = g.subgraph(comp)
            if not sub.ecount():
                continue
            vals = sub.eigenvector_centrality(scale=True)
            for local, v in enumerate(comp):
                eig[v] = vals[local]

    # Participation: share of a node's ties that leave its own community.
    part = []
    for v in range(g.vcount()):
        nb = g.neighbors(v)
        part.append(0.0 if not nb else
                    sum(1 for u in nb if comm[u] != comm[v]) / len(nb))

    return {
        "degree": g.degree(),
        "betweenness": g.betweenness(),
        "eigenvector": eig,
        "closeness": closeness,
        "coreness": g.coreness(),
        "participation": part,
        "community": comm,
        "component": membership,
        "in_lcc": [1 if m == giant else 0 for m in membership],
    }


def static_order(strategy: str, attr: dict, g: ig.Graph,
                 seed: int = 7) -> list[int]:
    """Removal order, most-removed-first, ties broken by degree then id."""
    n = g.vcount()
    if strategy == "random":
        order = list(range(n))
        random.Random(seed).shuffle(order)
        return order
    if strategy in CLASS_FIRST:
        want = CLASS_FIRST[strategy]
        cls = g.vs["node_class"]
        if strategy == "orgs_first":
            key = lambda v: (0 if cls[v] != "person" else 1, -attr["degree"][v], v)
        else:
            key = lambda v: (0 if cls[v] == want else 1, -attr["degree"][v], v)
        return sorted(range(n), key=key)
    vals = attr[strategy]
    return sorted(range(n), key=lambda v: (-vals[v], -attr["degree"][v], v))


def _metrics(g: ig.Graph, alive: np.ndarray, n0: int) -> tuple[float, float, int]:
    """Relative largest component, mean size of the rest, component count."""
    sub = g.subgraph([int(v) for v in np.flatnonzero(alive)])
    if sub.vcount() == 0:
        return 0.0, 0.0, 0
    sizes = sorted(sub.connected_components().sizes(), reverse=True)
    rest = sizes[1:]
    return sizes[0] / n0, (float(np.mean(rest)) if rest else 0.0), len(sizes)


def run_static(g: ig.Graph, order: list[int], steps: int) -> list[dict]:
    n0 = g.vcount()
    alive = np.ones(n0, dtype=bool)
    marks = sorted({int(round(i * n0 / steps)) for i in range(steps + 1)})
    rows, pos = [], 0
    for m in marks:
        while pos < m:
            alive[order[pos]] = False
            pos += 1
        S, s_mean, ncomp = _metrics(g, alive, n0)
        rows.append({"removed": pos, "f": pos / n0, "S": S,
                     "mean_other": s_mean, "components": ncomp})
    return rows


def run_adaptive(g: ig.Graph, strategy: str, steps: int,
                 recalc_every: int) -> list[dict]:
    n0 = g.vcount()
    alive = np.ones(n0, dtype=bool)
    marks = sorted({int(round(i * n0 / steps)) for i in range(steps + 1)})
    rows, removed = [], 0
    queue: list[int] = []
    for m in marks:
        while removed < m:
            if not queue:
                idx = [int(v) for v in np.flatnonzero(alive)]
                if not idx:
                    break
                sub = g.subgraph(idx)
                vals = (sub.degree() if strategy == "degree_recalc"
                        else sub.betweenness())
                rank = sorted(range(len(idx)), key=lambda i: -vals[i])
                queue = [idx[i] for i in rank[:recalc_every]]
            nxt = queue.pop(0)
            if alive[nxt]:
                alive[nxt] = False
                removed += 1
        S, s_mean, ncomp = _metrics(g, alive, n0)
        rows.append({"removed": removed, "f": removed / n0, "S": S,
                     "mean_other": s_mean, "components": ncomp})
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--before", default=CUT)
    ap.add_argument("--scope", choices=("lcc", "full"), default="lcc",
                    help="run the curves on the largest connected component "
                         "(default, and what the literature means) or on "
                         "every node")
    ap.add_argument("--steps", type=int, default=100,
                    help="points per curve")
    ap.add_argument("--replicates", type=int, default=20,
                    help="seeded draws averaged for the random strategy")
    ap.add_argument("--recalc-every", type=int, default=10,
                    help="removals between recomputations for the adaptive "
                         "strategies")
    ap.add_argument("--null-replicates", type=int, default=5,
                    help="degree-preserving rewirings to run the same "
                         "strategies against; 0 disables the null")
    ap.add_argument("--no-curves", action="store_true",
                    help="write the dataset files only")
    args = ap.parse_args(argv)

    OUT.mkdir(parents=True, exist_ok=True)
    print(f"building the gazette-evidenced graph before {args.before}…")
    d = build(args.before)
    g = graph_of(d)
    attr = attributes(g)
    print(f"  {g.vcount():,} nodes, {g.ecount():,} ties, "
          f"{max(attr['component']) + 1:,} components, "
          f"LCC {sum(attr['in_lcc']):,} "
          f"({100 * sum(attr['in_lcc']) / g.vcount():.1f}%)")

    _write_nodes(g, attr)
    _write_edges(g)
    _write_orders(g, attr)
    # Attach the precomputed attributes to the graph files too, so a
    # GraphML load is self-sufficient and needs no join against the CSV.
    for name in ("degree", "betweenness", "eigenvector", "closeness",
                 "coreness", "participation", "community", "component",
                 "in_lcc"):
        g.vs[name] = attr[name]
    g.write_graphml(str(OUT / "pre2011.graphml"))

    lcc = g.subgraph([v for v in range(g.vcount()) if attr["in_lcc"][v]])
    # Recomputed inside the component: degree is unchanged but betweenness,
    # closeness, eigenvector and coreness all mean something different once
    # the rest of the graph is gone, and the LCC file is what percolation
    # runs on.
    for name, vals in attributes(lcc).items():
        lcc.vs[name] = vals
    lcc.write_graphml(str(OUT / "pre2011_lcc.graphml"))
    print(f"  wrote pre2011.graphml ({g.vcount():,} nodes) and "
          f"pre2011_lcc.graphml ({lcc.vcount():,} nodes)")

    art = lcc.articulation_points()
    ldeg = lcc.degree()
    two_mode = sum(1 for k in d["kind"] if k != "person")
    struct = {
        "lcc_mean_degree": round(2 * lcc.ecount() / lcc.vcount(), 3),
        "lcc_independent_cycles": lcc.ecount() - lcc.vcount() + 1,
        "lcc_articulation_points": len(art),
        "lcc_share_degree_1": round(
            sum(1 for x in ldeg if x == 1) / len(ldeg), 4),
        "lcc_max_degree": max(ldeg),
        "lcc_transitivity": round(lcc.transitivity_undirected(), 6),
        "ties_not_person_to_org": two_mode,
    }
    print(f"  LCC is near-tree: {lcc.ecount():,} ties over {lcc.vcount():,} "
          f"nodes, {struct['lcc_independent_cycles']} independent cycles, "
          f"{100 * struct['lcc_share_degree_1']:.0f}% of nodes degree-1, "
          f"{len(art):,} articulation points")

    meta = {"before": args.before, "scope": args.scope,
            "nodes": g.vcount(), "edges": g.ecount(),
            "components": max(attr["component"]) + 1,
            "lcc_nodes": lcc.vcount(), "lcc_edges": lcc.ecount(),
            "kept_by_tie_class": d["kept_by_class"],
            "org_to_org_ties": d["n_org_ties"],
            "dropped_blank_orgs": d["dropped_blank"],
            "recalc_every": args.recalc_every,
            "random_replicates": args.replicates, **struct}

    if not args.no_curves:
        target = lcc if args.scope == "lcc" else g
        tattr = attributes(target) if args.scope == "lcc" else attr
        rows = _curves(target, tattr, args)
        path = OUT / f"pre2011_percolation_{args.scope}.csv"
        with path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=[
                "strategy", "graph", "scope", "replicate", "removed", "f",
                "S", "mean_other", "components"])
            w.writeheader()
            w.writerows(rows)
        print(f"  wrote {path.relative_to(ROOT)} ({len(rows):,} rows)")
        meta["curve_rows"] = len(rows)
        _report(rows, target.vcount())

    _write_readme(meta)
    mpath = OUT / f"pre2011_meta_{args.scope}.json"
    mpath.write_text(json.dumps(meta, indent=2, ensure_ascii=False),
                     encoding="utf-8")
    print(f"  wrote {mpath.relative_to(ROOT)}")
    return 0


def configuration_null(g: ig.Graph, seed: int) -> ig.Graph:
    """Degree-preserving rewiring: the configuration-model null.

    The observed largest component is nearly a tree, so every attack
    strategy destroys it quickly and the absolute collapse point says
    little on its own. The question that can be answered is whether it
    collapses faster than its own degree sequence implies. This rewires by
    double-edge swaps, which holds every node's degree exactly and
    destroys everything else.

    The rewired graph is reduced to its own largest component before
    use, for the reason given below.

    It does NOT preserve the two-mode structure: rewiring can create
    person-to-person and organisation-to-organisation ties that the
    observed graph does not have. It is a null for the degree sequence
    alone, and should be read as one.
    """
    h = g.copy()
    ig.set_random_number_generator(random.Random(seed))
    h.rewire(n=20 * h.ecount())
    h.vs["node_class"] = g.vs["node_class"]
    # Rewiring a near-tree usually disconnects it, so the rewired graph's
    # largest component holds only about 78% of the nodes. Comparing a
    # connected observed component against a fragmented null would confound
    # decay under attack with initial connectedness, so the null is reduced
    # to its own largest component and both start at S = 1.
    comps = h.connected_components()
    return h.subgraph(comps[int(np.argmax(comps.sizes()))])


def _curves(target: ig.Graph, tattr: dict, args) -> list[dict]:
    rows = []
    for strat in STATIC + list(CLASS_FIRST):
        if strat == "random":
            for rep in range(args.replicates):
                order = static_order("random", tattr, target, seed=1000 + rep)
                for r in run_static(target, order, args.steps):
                    rows.append({"strategy": strat, "graph": "observed",
                                 "scope": args.scope, "replicate": rep, **r})
        else:
            order = static_order(strat, tattr, target)
            for r in run_static(target, order, args.steps):
                rows.append({"strategy": strat, "graph": "observed",
                             "scope": args.scope, "replicate": 0, **r})
        print(f"    {strat} done")
    for strat in ADAPTIVE:
        for r in run_adaptive(target, strat, args.steps, args.recalc_every):
            rows.append({"strategy": strat, "graph": "observed",
                         "scope": args.scope, "replicate": 0, **r})
        print(f"    {strat} done")

    null_sizes = []
    for rep in range(args.null_replicates):
        null = configuration_null(target, seed=500 + rep)
        null_sizes.append(null.vcount())
        nattr = attributes(null, seed=500 + rep)
        for strat in ("random", "degree", "betweenness"):
            order = static_order(strat, nattr, null, seed=500 + rep)
            for r in run_static(null, order, args.steps):
                rows.append({"strategy": strat, "graph": "configuration",
                             "scope": args.scope, "replicate": rep, **r})
        for strat in ADAPTIVE:
            for r in run_adaptive(null, strat, args.steps,
                                  args.recalc_every):
                rows.append({"strategy": strat, "graph": "configuration",
                             "scope": args.scope, "replicate": rep, **r})
        print(f"    configuration null {rep + 1}/{args.null_replicates}"
              f" done ({null.vcount():,} nodes)")
    if null_sizes:
        print(f"    null largest components: mean "
              f"{np.mean(null_sizes):,.0f} of {target.vcount():,} nodes "
              f"({100 * np.mean(null_sizes) / target.vcount():.0f}%) -- "
              f"rewiring a near-tree disconnects it, so the null's degree "
              f"sequence is that of the rewired giant component, not the "
              f"observed one exactly")
    return rows


def _report(rows: list[dict], n0: int) -> None:
    """Robustness R = mean S over the removal sequence (Schneider 2011).

    Reported against the degree-preserving null, because the absolute
    value cannot be read on a near-tree: what is interpretable is whether
    the observed graph is more fragile than its degree sequence implies.
    """
    acc: dict[tuple[str, str], list[float]] = {}
    for r in rows:
        acc.setdefault((r["strategy"], r["graph"]), []).append(r["S"])
    cross: dict[tuple[str, str], list[list[float]]] = {}
    for r in rows:
        cross.setdefault((r["strategy"], r["graph"]), []).append(
            [r["f"], r["S"]])

    def crossing(key, th):
        arr = np.array(sorted(cross[key]))
        # On the full graph S starts at 0.26, so "f at S<0.5" is 0 for
        # every strategy and says nothing. Report that rather than a 0.
        if arr[0, 1] < th:
            return f"n/a S0={arr[0, 1]:.2f}"
        hit = arr[arr[:, 1] < th]
        return f"{hit[0, 0]:.3f}" if len(hit) else "—"

    obs = {k: float(np.mean(v)) for k, v in acc.items() if k[1] == "observed"}
    nul = {k[0]: float(np.mean(v)) for k, v in acc.items()
           if k[1] == "configuration"}

    print("\n  robustness R = mean S over the sequence (lower = more fragile)")
    print(f"  {'strategy':<22} {'R obs':>7} {'R null':>7} {'obs/null':>9}"
          f"  {'f at S<0.5':>14}")
    for (strat, _), R in sorted(obs.items(), key=lambda kv: kv[1]):
        rn = nul.get(strat)
        ratio = f"{R / rn:>8.2f}x" if rn else "        —"
        print(f"  {strat:<22} {R:>7.4f} "
              f"{(f'{rn:.4f}' if rn else '—'):>7} {ratio}"
              f"  {crossing((strat, 'observed'), 0.5):>14}")
    if nul:
        print("\n  the null holds each node's degree exactly and destroys "
              "everything else,")
        print("  so obs/null below 1 means the observed graph is more "
              "fragile than its")
        print("  degree sequence alone requires, and above 1 that it is "
              "less so.")


def _write_nodes(g: ig.Graph, attr: dict) -> None:
    path = OUT / "pre2011_nodes.csv"
    cols = ["degree", "betweenness", "eigenvector", "closeness", "coreness",
            "participation", "community", "component", "in_lcc"]
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["node_id", "label", "node_class"] + cols)
        for v in range(g.vcount()):
            w.writerow([g.vs[v]["name"], g.vs[v]["label"],
                        g.vs[v]["node_class"]]
                       + [attr[c][v] for c in cols])
    print(f"  wrote {path.relative_to(ROOT)}")


def _write_edges(g: ig.Graph) -> None:
    path = OUT / "pre2011_edges.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["source", "target", "tie_kind", "n_spells"])
        for e in g.es:
            w.writerow([g.vs[e.source]["name"], g.vs[e.target]["name"],
                        e["tie_kind"], e["n_spells"]])
    print(f"  wrote {path.relative_to(ROOT)}")


def _write_orders(g: ig.Graph, attr: dict) -> None:
    """Removal rank per node for each static strategy: 0 goes first."""
    path = OUT / "pre2011_attack_orders.csv"
    strategies = [s for s in STATIC if s != "random"] + list(CLASS_FIRST)
    ranks = {}
    for s in strategies:
        order = static_order(s, attr, g)
        r = [0] * g.vcount()
        for pos, v in enumerate(order):
            r[v] = pos
        ranks[s] = r
    for rep in range(3):
        order = static_order("random", attr, g, seed=1000 + rep)
        r = [0] * g.vcount()
        for pos, v in enumerate(order):
            r[v] = pos
        ranks[f"random_seed{1000 + rep}"] = r
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        names = list(ranks)
        w.writerow(["node_id", "in_lcc"] + names)
        for v in range(g.vcount()):
            w.writerow([g.vs[v]["name"], attr["in_lcc"][v]]
                       + [ranks[s][v] for s in names])
    print(f"  wrote {path.relative_to(ROOT)}")


def _write_readme(meta: dict) -> None:
    path = OUT / "README.md"
    path.write_text(f"""# Percolation dataset — the pre-{meta['before']} network

Generated by `scripts/percolation_pre2011.py`. See
`docs/PERCOLATION-pre2011.md` for the strategies, their sources and the
caveats, and `pre2011_meta.json` for the exact parameters of this run.

{meta['nodes']:,} nodes, {meta['edges']:,} undirected ties,
{meta['components']:,} components. The largest holds {meta['lcc_nodes']:,}
nodes ({100 * meta['lcc_nodes'] / meta['nodes']:.1f}%) and
{meta['lcc_edges']:,} ties.

## Files

| file | contents |
|---|---|
| `pre2011_nodes.csv` | one row per node |
| `pre2011_edges.csv` | undirected dyads; `n_spells` is how many spells back the tie |
| `pre2011.graphml` | whole graph, attributes attached — `igraph`, `networkx`, Gephi |
| `pre2011_lcc.graphml` | largest connected component only |
| `pre2011_attack_orders.csv` | removal rank per node per static strategy; 0 is removed first |
| `pre2011_percolation_lcc.csv`, `pre2011_percolation_full.csv` | the curves, one row per strategy × graph × replicate × step |
| `pre2011_meta_lcc.json`, `pre2011_meta_full.json` | run parameters and counts |

## `pre2011_nodes.csv`

| column | meaning |
|---|---|
| `node_id` | stable id; `PERSON_*` are natural persons |
| `label` | name as recorded (unaccented in the gazette layer) |
| `node_class` | `person`, `state` (state body or party), `private` (firm, association, union) |
| `degree` | ties in this graph |
| `betweenness` | recomputed on THIS graph, not carried from the pooled one |
| `eigenvector` | scaled to a maximum of 1 |
| `closeness` | normalised, within-component; 0 for isolates |
| `coreness` | k-shell index |
| `participation` | share of a node's ties leaving its own Louvain community |
| `community` | Louvain membership, seeded |
| `component` | connected-component id |
| `in_lcc` | 1 if in the largest component |

## `pre2011_percolation.csv`

`graph` is `observed` or `configuration` (the degree-preserving null).
`f` is the fraction of nodes removed, `S` the largest remaining component
as a fraction of the starting node count, `mean_other` the mean size of
the other components, `components` how many there are. `replicate` is 0
except for `random`, which is averaged over
{meta['random_replicates']} seeded draws. Adaptive strategies recompute
every {meta['recalc_every']} removals.

**`S` starts at 1.0 only under `--scope lcc`.** On the full graph it
starts at {meta['lcc_nodes'] / meta['nodes']:.2f}, because the network is
already fragmented before anything is removed.
""", encoding="utf-8")
    print(f"  wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    raise SystemExit(main())
