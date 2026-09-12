"""Export the multiplex into the formats network software actually reads.

Three targets, because each analytic route wants a different shape:

* **muxViz / MuxViz-style extended edge lists** - one multiplex per year, plus
  layer and node index files. This is the canonical input for multilayer
  measures (versatility, multiplex participation, layer correlation).
* **GraphML** - one graph per year with ``layer`` as an edge attribute, for
  igraph/networkx/Gephi.
* **A tidy long edge list** - already written by ``build_dataset``; the R and
  Python loaders here read it directly for anything bespoke.

muxViz indexes nodes and layers from 1 and expects a *shared* node index across
layers, so the node index is built once over the whole period rather than per
year. That keeps node IDs comparable across years, which is what makes the
series longitudinal rather than a stack of unrelated graphs.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from .common import PROCESSED, log, open_text

EDGES_OBS = PROCESSED / "multiplex_edges_observed.csv.gz"
EDGES_PANEL = PROCESSED / "multiplex_edges_panel.csv.gz"
MUXVIZ_DIR = PROCESSED / "muxviz"
GRAPHML_DIR = PROCESSED / "graphml"


def read_edges(path: Path, year_field: str) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"missing {path} - run elitenet.build_dataset first")
    with open_text(path) as fh:
        rows = list(csv.DictReader(fh))
    out = []
    for r in rows:
        y = r.get(year_field)
        if not y or not str(y).isdigit():
            continue
        r["_year"] = int(y)
        try:
            r["_w"] = float(r["weight"]) if r.get("weight") else 1.0
        except ValueError:
            r["_w"] = 1.0
        out.append(r)
    return out


def export_muxviz(edges: list[dict], outdir: Path, entities: dict[str, dict]) -> None:
    outdir.mkdir(parents=True, exist_ok=True)

    # A single node and layer index shared by every year.
    nodes = sorted({e["source_id"] for e in edges} | {e["target_id"] for e in edges})
    node_idx = {n: i + 1 for i, n in enumerate(nodes)}
    layers = sorted({e["layer"] for e in edges})
    layer_idx = {l: i + 1 for i, l in enumerate(layers)}

    with (outdir / "nodes.txt").open("w", encoding="utf-8") as fh:
        fh.write("nodeID nodeLabel entityType\n")
        for n in nodes:
            ent = entities.get(n, {})
            label = (ent.get("canonical_name") or n).replace(" ", "_")
            fh.write(f"{node_idx[n]} {label} {ent.get('entity_type','unknown')}\n")

    with (outdir / "layers.txt").open("w", encoding="utf-8") as fh:
        fh.write("layerID layerLabel\n")
        for l in layers:
            fh.write(f"{layer_idx[l]} {l}\n")

    by_year: dict[int, list[dict]] = defaultdict(list)
    for e in edges:
        by_year[e["_year"]].append(e)

    index_rows = []
    for year in sorted(by_year):
        # Extended edge list: node layer node layer weight (intra-layer only;
        # inter-layer coupling is categorical and left to muxViz's config).
        path = outdir / f"edges_{year}.txt"
        with path.open("w", encoding="utf-8") as fh:
            for e in by_year[year]:
                li = layer_idx[e["layer"]]
                fh.write(
                    f"{node_idx[e['source_id']]} {li} "
                    f"{node_idx[e['target_id']]} {li} {e['_w']:g}\n"
                )
        index_rows.append({"year": year, "edges_file": path.name,
                           "n_edges": len(by_year[year])})
        log.info("muxviz %d: %d edges", year, len(by_year[year]))

    with (outdir / "years_index.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["year", "edges_file", "n_edges"])
        w.writeheader()
        w.writerows(index_rows)


def export_graphml(edges: list[dict], outdir: Path, entities: dict[str, dict]) -> None:
    try:
        import networkx as nx
    except ImportError:
        log.warning("networkx not installed - skipping GraphML export")
        return
    outdir.mkdir(parents=True, exist_ok=True)

    by_year: dict[int, list[dict]] = defaultdict(list)
    for e in edges:
        by_year[e["_year"]].append(e)

    for year, rows in sorted(by_year.items()):
        # MultiDiGraph: a dyad can carry ties in several layers at once, which
        # is the whole point of a multiplex.
        g = nx.MultiDiGraph(year=year)
        for e in rows:
            for nid in (e["source_id"], e["target_id"]):
                if nid not in g:
                    ent = entities.get(nid, {})
                    g.add_node(
                        nid,
                        label=ent.get("canonical_name", nid),
                        entity_type=ent.get("entity_type", "unknown"),
                        is_listed=int(ent.get("is_bvmt_listed", "0") or 0),
                        isin=ent.get("isin", ""),
                    )
            g.add_edge(
                e["source_id"], e["target_id"],
                key=f"{e['layer']}:{e.get('doc_node_key') or 'derived'}:{e.get('page') or ''}",
                layer=e["layer"], weight=e["_w"],
                directed=int(e.get("directed") or 0),
                role=e.get("role") or "",
                obs_date=e.get("obs_date") or "",
                doc_url=e.get("doc_url") or "",
                observation_type=e.get("observation_type", "observed"),
            )
        nx.write_graphml(g, outdir / f"multiplex_{year}.graphml")
    log.info("wrote %d yearly GraphML files -> %s", len(by_year), outdir.name)


def load_entities() -> dict[str, dict]:
    path = PROCESSED / "entities.csv"
    if not path.exists():
        return {}
    with open_text(path) as fh:
        return {r["entity_id"]: r for r in csv.DictReader(fh)}


def main() -> None:
    ap = argparse.ArgumentParser(description="Export multiplex networks")
    ap.add_argument("--panel", action="store_true",
                    help="use the carried-forward panel instead of observed edges only")
    args = ap.parse_args()

    path = EDGES_PANEL if args.panel else EDGES_OBS
    yf = "panel_year" if args.panel else "year"
    edges = read_edges(path, yf)
    log.info("loaded %d edges from %s", len(edges), path.name)

    entities = load_entities()
    suffix = "_panel" if args.panel else ""
    export_muxviz(edges, Path(str(MUXVIZ_DIR) + suffix), entities)
    export_graphml(edges, Path(str(GRAPHML_DIR) + suffix), entities)


if __name__ == "__main__":
    main()
