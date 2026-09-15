"""Load the Tunisian elite network snapshots as networkx or igraph graphs.

    from python.load_snapshots import load_period, iter_periods, load_spells

    for period, g in iter_periods("yearly"):
        print(period, g.number_of_nodes(), g.number_of_edges())

Only gazette-dated ties at `certain` or `probable` certainty are exported to
the snapshots. Undated seed ties are deliberately excluded here: they carry no
time information, so putting them in a time slice would fabricate variation.
Load them explicitly with `load_spells(include_seed=True)` when you want the
full cross-section.
"""
from __future__ import annotations

import csv
from pathlib import Path

import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS = ROOT / "data" / "processed" / "multiplex" / "exports" / "snapshots"
SPELLS = ROOT / "data" / "processed" / "multiplex" / "spells.csv"


def available_periods(granularity: str = "yearly") -> list[str]:
    return sorted(p.stem.split("_", 1)[1]
                  for p in SNAPSHOTS.glob(f"{granularity}_*.csv"))


def load_period(period: str, granularity: str = "yearly") -> nx.MultiDiGraph:
    """One time slice as a directed multigraph (person -> organisation)."""
    path = SNAPSHOTS / f"{granularity}_{period}.csv"
    g = nx.MultiDiGraph(period=period, granularity=granularity)
    with path.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            g.add_node(r["from_node_id"], bipartite="person")
            g.add_node(r["to_node_id"], bipartite="organisation")
            g.add_edge(r["from_node_id"], r["to_node_id"],
                       key=r["spell_id"], role=r["role_canonical"],
                       layer=r["layer"], certainty=r["certainty"])
    return g


def iter_periods(granularity: str = "yearly"):
    for period in available_periods(granularity):
        yield period, load_period(period, granularity)


def load_spells(include_seed: bool = False) -> list[dict]:
    """Raw spell rows, for survival models that need the censoring flags."""
    with SPELLS.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if include_seed:
        return rows
    return [r for r in rows if r["evidence_tier"] == "gazette_dated"]


def to_igraph(g: nx.MultiDiGraph):
    """Convert a snapshot to igraph, if python-igraph is installed."""
    import igraph as ig

    nodes = list(g.nodes())
    index = {n: i for i, n in enumerate(nodes)}
    edges = [(index[u], index[v]) for u, v, _k in g.edges(keys=True)]
    out = ig.Graph(n=len(nodes), edges=edges, directed=True)
    out.vs["name"] = nodes
    out.es["role"] = [d.get("role", "") for _u, _v, d in g.edges(data=True)]
    return out


if __name__ == "__main__":
    for period, g in iter_periods("yearly"):
        print(f"{period}: {g.number_of_nodes():5} nodes  {g.number_of_edges():5} ties")
