"""The gazette-evidenced network as of a cut-off date.

One builder, used by both the publication figure and the percolation
harness, so the graph they describe cannot drift apart.

A date cut on this dataset is exactly a filter on **source**. Datability
splits the spell table perfectly by evidence tier: every
``gazette_dated`` / ``gazette_inferred`` / ``gazette_snowball`` spell
carries a date and every ``seed_undated`` spell carries none, with no
partially-dated tier. So restricting to ties evidenced before a date drops
the whole seed layer -- ownership, membership, kinship, leadership and
pedagogic ties are entirely seed-derived, recorded with
``onset_rule='seed_current_tie'`` and ``evidence_n=0``.

That is the correct treatment rather than a shortfall: the seed roster
asserts a *present* affiliation and was compiled long after 2011, so
carrying those ties into a pre-revolution graph would be an anachronism.
Two consequences travel with any analysis built on this:

* the gazette documents state appointments more completely than company
  officers -- all ``state_office`` spells are gazette-evidenced against
  half of ``corporate_officer`` -- so the state's share is overstated
  relative to the private layer;
* centralities must be computed on *this* graph. Values carried over from
  the pooled all-sources graph describe a different object.
"""
from __future__ import annotations

import collections
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed" / "multiplex"

STATE_PREFIXES = ("GOV", "PARTYSTR")


def _first_observation(path: Path) -> dict[str, str]:
    first: dict[str, str] = {}
    with path.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            dt = (r["obs_date"] or "").strip()
            sid = r["spell_id"]
            if dt and (sid not in first or dt < first[sid]):
                first[sid] = dt
    return first


def build(before: str, proc: Path | None = None) -> dict:
    """Nodes and undirected dyads evidenced before ``before`` (YYYY-MM-DD).

    Returns node ids, labels, a drawing/analysis class per node, the dyads
    as index pairs, a tie kind per dyad, and the counts needed to describe
    what was admitted.
    """
    proc = proc or PROC
    first = _first_observation(proc / "spell_observations.csv")

    labels: dict[str, str] = {}
    is_state: set[str] = set()
    persons: set[str] = set()
    spells_on: collections.Counter = collections.Counter()
    kept = collections.Counter()

    with (proc / "spells.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            cand = [x for x in ((r["onset"] or "").strip(),
                                first.get(r["spell_id"], "")) if x]
            if not cand or min(cand) >= before:
                continue
            p, o = r["person_id"], r["org_id"]
            persons.add(p)
            labels.setdefault(p, r["person_label"])
            labels[o] = r["org_label"]
            # Classify from the tie the pipeline already coded, never from
            # a regex on the label: "SOCIETE REGIONALE DE COMMERCE
            # GOUVERNORAT DE BEJA" is a firm, and a label regex calls it a
            # state body.
            if r["tie_class"] == "state_office":
                is_state.add(o)
            spells_on[(p, o)] += 1
            kept[r["tie_class"]] += 1

    n_org_ties = 0
    with (proc / "org_tie_spells.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            on = (r["onset"] or "").strip()
            if not on or on >= before:
                continue
            labels.setdefault(r["holder_id"], r["holder_label"])
            labels.setdefault(r["target_id"], r["target_label"])
            spells_on[(r["holder_id"], r["target_id"])] += 1
            n_org_ties += 1

    for nid in labels:
        if nid.split("_")[0] in STATE_PREFIXES:
            is_state.add(nid)

    # An unlabelled organisation held 590 pre-2011 offices here -- more
    # than any ministry, and the highest-degree node in the graph. It is
    # OCR damage, and a node that is not an entity cannot broker or
    # transmit anything. Only the genuinely blank are dropped, never the
    # merely short: GAT, MAC and PAF are real firms.
    blank = {n for n in labels
             if n not in persons and not (labels[n] or "").strip()}
    pairs = {k: v for k, v in spells_on.items()
             if k[0] not in blank and k[1] not in blank}

    nodes = sorted({n for pr in pairs for n in pr})
    idx = {n: i for i, n in enumerate(nodes)}
    edges, weights = [], []
    for (a, b), n in sorted(pairs.items()):
        edges.append((idx[a], idx[b]))
        weights.append(n)

    cls = ["person" if n in persons else
           "state" if n in is_state else "private" for n in nodes]

    return {
        "nodes": nodes,
        "labels": [labels[n] for n in nodes],
        "cls": cls,
        "edges": edges,
        "spells": weights,
        "kind": [tie_kind(cls[a], cls[b]) for a, b in edges],
        "dropped_blank": len(blank),
        "kept_by_class": dict(kept),
        "n_org_ties": n_org_ties,
        "before": before,
    }


def tie_kind(ca: str, cb: str) -> str:
    """Classify a tie from the classes of its ends."""
    if "state" in (ca, cb):
        return "state"
    if ca == "person" and cb == "person":
        return "kin"
    if ca != "person" and cb != "person":
        return "orgorg"
    return "person"
