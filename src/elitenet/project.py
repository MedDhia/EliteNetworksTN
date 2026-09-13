"""Stage 17 -- every layer collapsed into one graph, at three nested tiers.

The dataset is built as separate layers because they carry different kinds of
evidence. This stage answers the question they cannot answer separately: how
many people and how many organisations are in the network *as one thing*, and
how much of it hangs together.

Why three tiers and not one number
----------------------------------

The answer moves by more than an order of magnitude depending on what counts
as a node, and none of the three readings is wrong. So all three are reported,
nested, with the edge definition of each stated:

``seed_anchored``
    Only nodes that are named seed entities or gazette organisation entities,
    joined by validated affiliations, ownership ties and kinship. Every edge
    is a claim the pipeline is prepared to defend.

``officer_layer``
    Adds the SARL/SA officer roster, which admits **gazette-only people** --
    named in print but absent from the 13,630-name seed roster.

``all_sources``
    Adds the **full gazette co-mention graph** and the whole register:
    every company and every sole trader, named or not.

The tiers are nested by construction, so a count can only rise between them,
and `validate` checks that it does.

The weakest edge drives the largest number
------------------------------------------

``all_sources`` is much the biggest, and mostly not because of the register.
It is because its person-organisation edge is a **co-mention** -- a person and
an organisation named in the same filing -- which is a far weaker relation
than a dated affiliation. That tier is an outer bound on who could be
connected to whom, not a roster of offices held, and it should not be used
where `seed_anchored` will do.

A node universe is not a network
--------------------------------

The register lists companies and sole traders whether or not anything is
known about their relationships. Admitting all of them adds several hundred
thousand **isolates** -- nodes with no tie at all -- so this stage reports
isolates separately and by source rather than letting them inflate a headline.
The sole-trader table is the extreme case: 315,659 people, of whom about 800
have an identifier that any filing prints.

Two identity rules, both of which were wrong on the first attempt
-----------------------------------------------------------------

**A node's type comes from the node, not from the column it sits in.**
`spells.csv` carries the seed sheet's own relational edges alongside gazette
affiliations, and for those the *kin* sits in the `org_id` column: 829 spells,
all `seed_undated`, being parent_of, sibling_of, spouse_of and student_of.
Typing by column turned 307 people into organisations and 829 family ties
into employment.

**A register company that the gazette also prints is one node, not two.**
The join on the identifier is a node *merge*, not an edge; treating it as an
edge would invent a relationship between a firm and itself and double every
such company. 64,677 of the register's companies merge this way.
"""
from __future__ import annotations

import argparse
import csv
import gzip
from collections import Counter, defaultdict, deque

from .paths import DATA, PROCESSED, ensure_dirs

RNE = DATA / "processed" / "rne"

# Nested, weakest-evidence-last. Each tier is the union of itself and all
# tiers before it, which is what makes the monotonicity check meaningful.
TIERS = ("seed_anchored", "officer_layer", "all_sources")

FIELDS_SUMMARY = [
    "tier", "edge_definition", "individuals", "organisations", "nodes",
    "edges", "components", "isolates", "connected_nodes",
    "connected_pct", "giant_component", "giant_pct",
    "giant_individuals", "giant_organisations",
    "second_component", "third_component", "components_of_size_2",
]
FIELDS_ISOLATES = ["tier", "source", "node_type", "n"]
FIELDS_NODES = [
    "node_id", "node_type", "source", "degree", "component_id",
    "component_size", "in_giant_component", "tier_first_seen",
]

# How a node id announces where it came from. The register prefixes exist so
# a register key can never be confused with a gazette entity id.
RNE_COMPANY = "RNE_"
RNE_PERSON = "RNEP_"


def _read(name: str) -> list[dict]:
    path = PROCESSED / name
    if path.exists():
        with path.open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))
    gz = PROCESSED / (name + ".gz")
    if gz.exists():
        with gzip.open(gz, "rt", encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))
    return []


def _iter(name: str, base=None):
    """Stream a table. resolution.csv is 462,177 rows and the register
    tables together are a further million."""
    root = base or PROCESSED
    path = root / name
    if path.exists():
        with path.open(encoding="utf-8", newline="") as fh:
            yield from csv.DictReader(fh)
        return
    gz = root / (name + ".gz")
    if gz.exists():
        with gzip.open(gz, "rt", encoding="utf-8", newline="") as fh:
            yield from csv.DictReader(fh)


def _write(name: str, rows: list[dict], fields: list[str]) -> None:
    path = PROCESSED / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


class Graph:
    """Nodes typed on arrival, edges undirected, isolates permitted.

    Isolates are the point of admitting them: a register company nobody ever
    filed about is a real company and a real absence of evidence, and the two
    facts are only distinguishable if it is present with degree 0.
    """

    def __init__(self) -> None:
        self.adj: dict[str, set[str]] = defaultdict(set)
        self.kind: dict[str, str] = {}
        self.source: dict[str, str] = {}
        self.first_tier: dict[str, str] = {}

    def add_node(self, node: str, kind: str, source: str, tier: str) -> None:
        if not node:
            return
        self.adj.setdefault(node, set())
        prev = self.kind.get(node)
        if prev is None:
            self.kind[node] = kind
            self.source[node] = source
            self.first_tier[node] = tier
        elif prev != kind:
            # Never silently repaired. A node that is a person in one layer
            # and an organisation in another means the typing rule is wrong,
            # and the validator raises it as an ERROR rather than this
            # picking a winner.
            self.kind[node] = "CONFLICT"

    def add_edge(self, a: str, b: str) -> bool:
        if not a or not b or a == b:
            return False
        self.adj[a].add(b)
        self.adj[b].add(a)
        return True

    def edges(self) -> int:
        return sum(len(v) for v in self.adj.values()) // 2

    def label_components(self) -> tuple[dict[str, int], list[int]]:
        """(node -> component id, sizes largest first).

        Distinct from `holes.components`, which counts component size under a
        mask because it is measuring an exposure across two different node
        sets. Here there is one node set and membership is the product, so
        the traversal labels rather than counts.
        """
        comp: dict[str, int] = {}
        sizes: list[int] = []
        for start in self.adj:
            if start in comp:
                continue
            cid = len(sizes)
            q = deque([start])
            comp[start] = cid
            size = 0
            while q:
                n = q.popleft()
                size += 1
                for m in self.adj[n]:
                    if m not in comp:
                        comp[m] = cid
                        q.append(m)
            sizes.append(size)
        order = sorted(range(len(sizes)), key=lambda i: -sizes[i])
        return comp, [sizes[i] for i in order]


def node_kind(node: str, seed_type: dict[str, str]) -> str:
    """PERSON or ORGANISATION, from the node's identity.

    The seed sheet is authoritative where it knows the node; otherwise the id
    prefix says. This function exists because typing by column position put
    307 people in the organisation set.
    """
    t = seed_type.get(node)
    if t:
        return "PERSON" if t == "PERSON" else "ORGANISATION"
    if node.startswith(RNE_PERSON):
        return "PERSON"
    if node.startswith(RNE_COMPANY):
        return "ORGANISATION"
    return "PERSON" if node.startswith("PERSON_") else "ORGANISATION"


def _source_of(node: str, seed_type: dict[str, str]) -> str:
    if node.startswith(RNE_PERSON):
        return "rne_sole_trader"
    if node.startswith(RNE_COMPANY):
        return "rne_company"
    if node in seed_type:
        return "seed"
    return "gazette"


def build(tier: str) -> tuple[Graph, dict]:
    """The graph at one tier. Tiers are nested, so each adds to the last."""
    diag: Counter = Counter()
    g = Graph()
    seed_type = {r["node_id"]: r.get("node_type", "")
                 for r in _read("seed_nodes.csv")}
    entity_of = {r["org_mention"]: r["org_entity_id"]
                 for r in _iter("org_entity_members.csv")
                 if r.get("org_mention") and r.get("org_entity_id")}

    def add(node, tier_name=tier):
        g.add_node(node, node_kind(node, seed_type),
                   _source_of(node, seed_type), tier_name)

    # --- every seed entity is a node, tied or not ------------------------
    for nid in seed_type:
        add(nid, "seed_anchored")
    diag["seed_nodes"] = len(seed_type)

    # --- validated person-organisation, and the seed's own kin edges -----
    for r in _iter("spells.csv"):
        a, b = r.get("person_id", ""), r.get("org_id", "")
        if not a or not b:
            continue
        add(a, "seed_anchored"); add(b, "seed_anchored")
        if g.add_edge(a, b):
            key = ("seed_person_person"
                   if node_kind(b, seed_type) == "PERSON"
                   else "spell_person_organisation")
            diag[key] += 1

    for r in _iter("org_tie_spells.csv"):
        a, b = r.get("holder_id", ""), r.get("target_id", "")
        add(a, "seed_anchored"); add(b, "seed_anchored")
        if g.add_edge(a, b):
            diag["organisation_ties"] += 1

    for r in _iter("person_tie_spells.csv"):
        a, b = r.get("person_id", ""), r.get("kin_id", "")
        add(a, "seed_anchored"); add(b, "seed_anchored")
        if g.add_edge(a, b):
            diag["gazette_kinship"] += 1

    if tier == "seed_anchored":
        return g, dict(diag)

    # --- the SARL/SA officer roster, admitting gazette-only people -------
    for r in _iter("rne_company_persons.csv"):
        p = (r.get("person_key") or "").strip()
        o = ((r.get("org_entity_id") or "").strip()
             or RNE_COMPANY + (r.get("company_key") or "").strip())
        if not p or o == RNE_COMPANY:
            continue
        add(p, "officer_layer"); add(o, "officer_layer")
        if g.add_edge(p, o):
            diag["officer_links"] += 1

    if tier == "officer_layer":
        return g, dict(diag)

    # --- the full gazette co-mention graph -------------------------------
    # Weaker than an affiliation: a person and an organisation named in one
    # filing. This is what makes `all_sources` an outer bound.
    for r in _iter("resolution.csv"):
        p = ((r.get("resolved_person_id") or "").strip()
             or (r.get("mention_cluster_id") or "").strip())
        if not p:
            continue
        add(p)
        mention = (r.get("org_mention") or "").strip()
        ent = entity_of.get(mention)
        if not ent:
            diag["co_mention_without_an_organisation"] += 1
            continue
        add(ent)
        if g.add_edge(p, ent):
            diag["co_mention_edges"] += 1

    # --- the whole register ----------------------------------------------
    # A company the gazette also prints IS the gazette entity: the identifier
    # join is a node merge, so nothing is added for it.
    id_to_entity: dict[str, str] = {}
    for r in _iter("org_identifiers.csv"):
        v = (r.get("value_normalised") or "").strip()
        e = (r.get("org_entity_id") or "").strip()
        if v and e:
            id_to_entity.setdefault(v, e)

    seen_co: set[str] = set()
    for r in _iter("entreprises.csv", RNE):
        rc = (r.get("registres.numRegistre") or "").strip()
        if not rc or rc in seen_co:
            diag["duplicate_register_company_rows"] += bool(rc)
            continue
        seen_co.add(rc)
        mf = (r.get("registres.identifiantUnique") or "").strip()
        ent = id_to_entity.get(mf) or id_to_entity.get(rc)
        if ent:
            diag["register_company_merged_onto_gazette_entity"] += 1
            add(ent)
        else:
            diag["register_company_standalone"] += 1
            add(RNE_COMPANY + rc)

    seen_p: set[tuple[str, str]] = set()
    for r in _iter("personnes_physiques.csv", RNE):
        rc = (r.get("numRegistre") or "").strip()
        mf = (r.get("identifiantUnique") or "").strip()
        if not (rc or mf):
            continue
        if (rc, mf) in seen_p:
            diag["duplicate_register_person_rows"] += 1
            continue
        seen_p.add((rc, mf))
        node = RNE_PERSON + (rc or mf)
        add(node)
        ent = id_to_entity.get(mf) or id_to_entity.get(rc)
        if ent:
            add(ent)
            if g.add_edge(node, ent):
                diag["register_sole_trader_bridged"] += 1
        else:
            diag["register_sole_trader_unbridged"] += 1

    return g, dict(diag)


EDGE_DEFINITION = {
    "seed_anchored":
        "validated affiliations, ownership ties and kinship only",
    "officer_layer":
        "plus the SARL/SA officer roster (admits gazette-only people)",
    "all_sources":
        "plus gazette CO-MENTION and the whole register (outer bound)",
}


def summarise(tier: str, g: Graph) -> tuple[dict, list[dict], list[dict]]:
    comp, sizes = g.label_components()
    persons = [n for n in g.adj if g.kind.get(n) == "PERSON"]
    orgs = [n for n in g.adj if g.kind.get(n) == "ORGANISATION"]
    nodes = len(g.adj)
    # Hoisted: this is a million-node graph, and rebuilding the tally per
    # node made the node table quadratic.
    size_of_component = Counter(comp.values())
    giant_id = (size_of_component.most_common(1)[0][0]
                if size_of_component else 0)
    giant = [n for n, c in comp.items() if c == giant_id]
    gp = sum(1 for n in giant if g.kind.get(n) == "PERSON")
    isolates = [n for n in g.adj if not g.adj[n]]
    connected = nodes - len(isolates)

    row = {
        "tier": tier, "edge_definition": EDGE_DEFINITION[tier],
        "individuals": len(persons), "organisations": len(orgs),
        "nodes": nodes, "edges": g.edges(),
        "components": len(sizes), "isolates": len(isolates),
        "connected_nodes": connected,
        "connected_pct": round(100 * connected / max(nodes, 1), 1),
        "giant_component": len(giant),
        "giant_pct": round(100 * len(giant) / max(nodes, 1), 1),
        "giant_individuals": gp,
        "giant_organisations": len(giant) - gp,
        "second_component": sizes[1] if len(sizes) > 1 else 0,
        "third_component": sizes[2] if len(sizes) > 2 else 0,
        "components_of_size_2": sum(1 for s in sizes if s == 2),
    }
    iso_rows = [
        {"tier": tier, "source": src, "node_type": kind, "n": n}
        for (src, kind), n in sorted(Counter(
            (g.source.get(x, "?"), g.kind.get(x, "?")) for x in isolates
        ).items(), key=lambda kv: -kv[1])
    ]
    node_rows = [
        {"node_id": n, "node_type": g.kind.get(n, "?"),
         "source": g.source.get(n, "?"), "degree": len(g.adj[n]),
         "component_id": comp[n],
         "component_size": size_of_component[comp[n]],
         "in_giant_component": int(comp[n] == giant_id),
         "tier_first_seen": g.first_tier.get(n, tier)}
        for n in g.adj
    ]
    return row, iso_rows, node_rows


def run() -> dict:
    ensure_dirs()
    summary: list[dict] = []
    isolates: list[dict] = []
    nodes_out: list[dict] = []
    diags: dict = {}
    for tier in TIERS:
        g, d = build(tier)
        if not g.adj:
            print(f"{tier}: no input tables -- nothing to do")
            continue
        row, iso, nds = summarise(tier, g)
        summary.append(row)
        isolates.extend(iso)
        diags[tier] = d
        if tier == TIERS[-1]:
            # Only the widest tier's node table is written. The narrower
            # tiers are a filter on `tier_first_seen`, so three tables would
            # be the same rows three times.
            nodes_out = nds

    if not summary:
        return {}
    _write("projection_summary.csv", summary, FIELDS_SUMMARY)
    _write("projection_isolates.csv", isolates, FIELDS_ISOLATES)
    _write("projection_nodes.csv", nodes_out, FIELDS_NODES)

    print("the whole dataset projected into one graph")
    print(f"  {'tier':16} {'individuals':>12} {'organisations':>14} "
          f"{'edges':>10} {'isolates':>10} {'giant':>10}")
    for r in summary:
        print(f"  {r['tier']:16} {r['individuals']:>12,} "
              f"{r['organisations']:>14,} {r['edges']:>10,} "
              f"{r['isolates']:>10,} {r['giant_component']:>10,}")
    last = summary[-1]
    print(f"\n  giant component at `{last['tier']}`: "
          f"{last['giant_component']:,} nodes "
          f"({last['giant_pct']}% of all) -- "
          f"{last['giant_individuals']:,} individuals and "
          f"{last['giant_organisations']:,} organisations")
    print(f"  next two components: {last['second_component']:,} / "
          f"{last['third_component']:,}")
    print("  -- isolates by source, widest tier:")
    for r in isolates:
        if r["tier"] == last["tier"]:
            print(f"     {r['source']:22} {r['node_type']:14} {r['n']:>10,}")
    d = diags.get(TIERS[-1], {})
    for k in ("spell_person_organisation", "seed_person_person",
              "organisation_ties", "gazette_kinship", "officer_links",
              "co_mention_edges", "register_company_merged_onto_gazette_entity",
              "register_company_standalone", "register_sole_trader_bridged",
              "register_sole_trader_unbridged"):
        if k in d:
            print(f"  {k:<46} {d[k]:>10,}")
    return {"tiers": len(summary), **{f"{r['tier']}_nodes": r["nodes"]
                                      for r in summary}}


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(
        description="Project every layer into one graph, at three tiers."
    ).parse_args(argv)
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
