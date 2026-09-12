"""Assemble extracted records into the analysis-ready longitudinal dataset.

Design decisions that matter for the analysis, stated once here:

**Observation, not interpolation.** Filings are snapshots taken at irregular
dates. Every edge is written at the year of the date the *document itself*
states it is describing ("au 31/08/2025"), falling back to the filing date. A
separate panel expansion carries the last observation forward and flags each
row as ``observed`` or ``carried_forward`` - the choice between them is the
analyst's, so both are shipped and neither is silently assumed.

**Weights are on their natural scale.** Ownership weights are percentages of
capital (0-100) exactly as reported. Interlock and co-ownership weights are
counts of shared individuals or shared blockholders. No normalisation is applied
here: rescaling is a modelling decision and belongs downstream.

**Two-pass entity resolution.** The first pass feeds the resolver type evidence
from table positions that are unambiguous by construction; the second resolves
every name with that evidence available. See :mod:`elitenet.entities`.
"""

from __future__ import annotations

import argparse
import csv
import itertools
from collections import defaultdict
from pathlib import Path

from .common import PROCESSED, log, open_text, read_jsonl
from .entities import Resolver

RECORDS = PROCESSED / "records"
BVMT_CSV = PROCESSED / "bvmt_listed_securities.csv"

# Columns whose contents are unambiguous by table position, used as type
# evidence in pass 1: (file, field, entity type).
EVIDENCE_COLUMNS = [
    ("board.jsonl.gz", "represented_by_raw", "person"),
    ("interlocks.jsonl.gz", "person_name_raw", "person"),
    ("executives.jsonl.gz", "person_name_raw", "person"),
    ("interlocks.jsonl.gz", "other_firm_name_raw", "firm"),
    ("executives.jsonl.gz", "other_firm_name_raw", "firm"),
    ("subsidiaries.jsonl.gz", "subsidiary_name_raw", "firm"),
]


def _year(rec: dict) -> int | None:
    """Year the record describes: the stated 'as of' date, else the filing."""
    for field in ("as_of", "filing_date"):
        v = rec.get(field)
        if v and len(str(v)) >= 4 and str(v)[:4].isdigit():
            y = int(str(v)[:4])
            if 1990 <= y <= 2035:
                return y
    y = rec.get("issuer_ref_year")
    return int(y) if y else None


def _obs_date(rec: dict) -> str | None:
    return rec.get("as_of") or rec.get("filing_date")


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open_text(path, "w") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    log.info("%-34s %6d rows", path.name, len(rows))


# --------------------------------------------------------------------------
# pass 1 - type evidence
# --------------------------------------------------------------------------


def seed_evidence(res: Resolver) -> None:
    for fname, field, etype in EVIDENCE_COLUMNS:
        for rec in read_jsonl(RECORDS / fname):
            v = rec.get(field)
            if v:
                res.add_evidence(v, etype)
    # Listed issuers are firms by definition.
    if BVMT_CSV.exists():
        with BVMT_CSV.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                res.add_evidence(row["name_fr"], "firm")


# --------------------------------------------------------------------------
# pass 2 - edges
# --------------------------------------------------------------------------


def build_edges(res: Resolver) -> tuple[list[dict], dict[str, dict]]:
    """Return observed multiplex edges plus per-firm listing attributes."""
    edges: list[dict] = []
    listed: dict[str, dict] = {}

    if BVMT_CSV.exists():
        with BVMT_CSV.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                eid, _ = res.resolve(row["name_fr"], hint="firm")
                if eid:
                    listed[eid] = {
                        "isin": row["isin"],
                        "ticker": row["ticker"],
                        "name_ar": row.get("name_ar", ""),
                        "bvmt_group_label": row.get("bvmt_group_label", ""),
                    }

    # Row-spanning and repeated header fragments make a table emit the same
    # holder twice on one page. Identical (document, page, tie, weight) rows are
    # therefore artefacts, not two separate disclosures.
    seen_rows: set[tuple] = set()

    def add(layer, src, dst, weight, rec, *, directed=True, **extra):
        fingerprint = (layer, src, dst, weight, rec.get("doc_node_key"), rec.get("page"))
        if fingerprint in seen_rows:
            return
        seen_rows.add(fingerprint)
        edges.append(
            {
                "layer": layer,
                "year": _year(rec),
                "obs_date": _obs_date(rec),
                "source_id": src,
                "target_id": dst,
                "weight": weight,
                "directed": int(directed),
                "doc_node_key": rec.get("doc_node_key"),
                "doc_type": rec.get("doc_type"),
                "doc_url": rec.get("doc_url"),
                "page": rec.get("page"),
                "doc_sha256": rec.get("doc_sha256"),
                **extra,
            }
        )

    # --- ownership: named blockholders and director holdings ---------------
    for fname, layer in (
        ("blockholders.jsonl.gz", "ownership"),
        ("director_holdings.jsonl.gz", "ownership_director"),
    ):
        for rec in read_jsonl(RECORDS / fname):
            issuer, _ = res.resolve(rec.get("issuer_name_raw") or "", hint="firm")
            holder, htype = res.resolve(rec.get("holder_name_raw") or "")
            if not issuer or not holder or htype == "aggregate":
                continue
            if holder == issuer:  # treasury shares, not a tie
                continue
            pct = rec.get("pct_capital")
            if pct is None or not (0 < pct <= 100):
                continue
            add(layer, holder, issuer, pct, rec,
                n_shares=rec.get("n_shares"), holder_type=htype)

    # --- ownership: group participations (issuer -> subsidiary) -----------
    for rec in read_jsonl(RECORDS / "subsidiaries.jsonl.gz"):
        issuer, _ = res.resolve(rec.get("issuer_name_raw") or "", hint="firm")
        sub, _ = res.resolve(rec.get("subsidiary_name_raw") or "", hint="firm")
        pct = rec.get("pct_capital")
        if not issuer or not sub or issuer == sub:
            continue
        if pct is None or not (0 < pct <= 100):
            continue
        add("group_participation", issuer, sub, pct, rec)

    # --- board seats -------------------------------------------------------
    for rec in read_jsonl(RECORDS / "board.jsonl.gz"):
        issuer, _ = res.resolve(rec.get("issuer_name_raw") or "", hint="firm")
        if not issuer:
            continue
        member_raw = rec.get("member_name_raw") or ""
        is_legal = bool(rec.get("member_is_legal_person"))
        member, mtype = res.resolve(member_raw, hint="firm" if is_legal else None)
        rep_raw = rec.get("represented_by_raw")
        if member and member != issuer:
            # A legal person on the board is simultaneously a corporate tie.
            layer = "board_seat_corporate" if mtype in ("firm", "fund", "state") else "board_seat"
            add(layer, member, issuer, 1.0, rec, directed=False,
                role=rec.get("role_raw"), mandate_start=rec.get("mandate_start"),
                mandate_end=rec.get("mandate_end"), seat_holder_type=mtype)
        if rep_raw:
            rep, _ = res.resolve(rep_raw, hint="person")
            if rep and rep != issuer:
                add("board_seat", rep, issuer, 1.0, rec, directed=False,
                    role=rec.get("role_raw"), mandate_start=rec.get("mandate_start"),
                    mandate_end=rec.get("mandate_end"),
                    seat_holder_type="person", represents=member)

    # --- declared mandates in other companies ------------------------------
    for fname, layer in (
        ("interlocks.jsonl.gz", "declared_mandate"),
        ("executives.jsonl.gz", "declared_executive"),
    ):
        for rec in read_jsonl(RECORDS / fname):
            person, _ = res.resolve(rec.get("person_name_raw") or "", hint="person")
            firm, _ = res.resolve(rec.get("other_firm_name_raw") or "", hint="firm")
            if not person or not firm:
                continue
            add(layer, person, firm, 1.0, rec, directed=False, role=rec.get("role_raw"))

    return edges, listed


# --------------------------------------------------------------------------
# derived firm-firm layers
# --------------------------------------------------------------------------


def derive_firm_layers(edges: list[dict]) -> list[dict]:
    """Project person-firm affiliations and shared blockholders onto firm-firm ties.

    Both projections are weighted counts: an interlock weight of 3 means three
    individuals sat on both boards in that year; a co-ownership weight of 2
    means two blockholders held stakes in both firms.
    """
    out: list[dict] = []

    affil = defaultdict(set)     # (year, person) -> {firms}
    coown = defaultdict(set)     # (year, holder)  -> {firms}
    for e in edges:
        if e["year"] is None:
            continue
        if e["layer"] in ("board_seat", "declared_mandate", "declared_executive"):
            affil[(e["year"], e["source_id"])].add(e["target_id"])
        elif e["layer"] in ("ownership", "ownership_director"):
            coown[(e["year"], e["source_id"])].add(e["target_id"])

    def project(index, layer):
        pair_counts: dict[tuple[int, str, str], set[str]] = defaultdict(set)
        for (year, actor), firms in index.items():
            for a, b in itertools.combinations(sorted(firms), 2):
                pair_counts[(year, a, b)].add(actor)
        for (year, a, b), actors in sorted(pair_counts.items()):
            out.append(
                {
                    "layer": layer,
                    "year": year,
                    "obs_date": None,
                    "source_id": a,
                    "target_id": b,
                    "weight": float(len(actors)),
                    "directed": 0,
                    "shared_actors": " | ".join(sorted(actors)),
                    "doc_node_key": None,
                    "doc_type": "derived",
                    "doc_url": None,
                    "page": None,
                    "doc_sha256": None,
                }
            )

    project(affil, "board_interlock")
    project(coown, "coownership")
    return out


# --------------------------------------------------------------------------
# panel expansion
# --------------------------------------------------------------------------


def expand_panel(edges: list[dict], max_carry: int = 3) -> list[dict]:
    """Carry each observed tie forward until the next observation of that dyad.

    ``max_carry`` caps how many years an unrefreshed observation survives, so a
    firm that stopped filing does not keep an ownership tie alive indefinitely.
    Each row is flagged ``observed`` or ``carried_forward``.
    """
    by_dyad: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for e in edges:
        if e["year"] is not None:
            by_dyad[(e["layer"], e["source_id"], e["target_id"])].append(e)

    years = [e["year"] for e in edges if e["year"] is not None]
    if not years:
        return []
    last_year = max(years)

    out: list[dict] = []
    for (layer, src, dst), obs in by_dyad.items():
        obs.sort(key=lambda e: e["year"])
        # One observation per year: keep the latest-dated within the year.
        per_year: dict[int, dict] = {}
        for e in obs:
            cur = per_year.get(e["year"])
            if cur is None or (e.get("obs_date") or "") >= (cur.get("obs_date") or ""):
                per_year[e["year"]] = e
        seq = sorted(per_year.items())
        for i, (year, e) in enumerate(seq):
            nxt = seq[i + 1][0] if i + 1 < len(seq) else None
            out.append({**e, "panel_year": year, "observation_type": "observed"})
            stop = min(nxt - 1 if nxt else last_year, year + max_carry)
            for y in range(year + 1, stop + 1):
                out.append({**e, "panel_year": y, "observation_type": "carried_forward"})
    return out


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

EDGE_FIELDS = [
    "layer", "year", "obs_date", "source_id", "source_name", "source_type",
    "target_id", "target_name", "target_type", "weight", "directed", "role",
    "mandate_start", "mandate_end", "n_shares", "seat_holder_type", "represents",
    "shared_actors", "doc_node_key", "doc_type", "doc_url", "page", "doc_sha256",
]


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the longitudinal multiplex dataset")
    ap.add_argument("--max-carry", type=int, default=3,
                    help="years an observation is carried forward in the panel")
    args = ap.parse_args()

    res = Resolver()
    log.info("pass 1: collecting entity type evidence")
    seed_evidence(res)
    log.info("pass 2: resolving entities and building edges")
    edges, listed = build_edges(res)
    derived = derive_firm_layers(edges)
    all_edges = edges + derived

    # Attach display names now that every alias has voted.
    for e in all_edges:
        e["source_name"] = res.canonical_name(e["source_id"])
        e["target_name"] = res.canonical_name(e["target_id"])
        e["source_type"] = res._types.get(e["source_id"], "unknown")
        e["target_type"] = res._types.get(e["target_id"], "unknown")

    PROCESSED.mkdir(parents=True, exist_ok=True)

    ents = res.entity_rows()
    for row in ents:
        extra = listed.get(row["entity_id"], {})
        row["is_bvmt_listed"] = int(bool(extra))
        row["isin"] = extra.get("isin", "")
        row["ticker"] = extra.get("ticker", "")
        row["name_ar"] = extra.get("name_ar", "")
        row["bvmt_group_label"] = extra.get("bvmt_group_label", "")
    write_csv(PROCESSED / "entities.csv", ents,
              ["entity_id", "entity_type", "canonical_name", "is_bvmt_listed",
               "isin", "ticker", "name_ar", "bvmt_group_label", "n_aliases", "aliases"])
    write_csv(PROCESSED / "entity_aliases.csv", res.alias_rows(),
              ["entity_id", "entity_type", "alias_raw", "matching_key"])

    all_edges.sort(key=lambda e: (e["layer"], e["year"] or 0, e["source_id"], e["target_id"]))
    write_csv(PROCESSED / "multiplex_edges_observed.csv.gz", all_edges, EDGE_FIELDS)

    panel = expand_panel(all_edges, max_carry=args.max_carry)
    panel.sort(key=lambda e: (e["layer"], e["panel_year"], e["source_id"], e["target_id"]))
    write_csv(PROCESSED / "multiplex_edges_panel.csv.gz", panel,
              ["panel_year", "observation_type"] + EDGE_FIELDS)

    # Coverage summary: which layers exist, over which years, how dense.
    summary: dict[tuple[str, int], dict] = {}
    for e in all_edges:
        if e["year"] is None:
            continue
        k = (e["layer"], e["year"])
        s = summary.setdefault(k, {"layer": e["layer"], "year": e["year"], "n_edges": 0,
                                   "nodes": set(), "n_docs": set()})
        s["n_edges"] += 1
        s["nodes"].update((e["source_id"], e["target_id"]))
        if e["doc_node_key"]:
            s["n_docs"].add(e["doc_node_key"])
    rows = [
        {"layer": v["layer"], "year": v["year"], "n_edges": v["n_edges"],
         "n_nodes": len(v["nodes"]), "n_source_docs": len(v["n_docs"])}
        for v in sorted(summary.values(), key=lambda v: (v["layer"], v["year"]))
    ]
    write_csv(PROCESSED / "layer_year_coverage.csv", rows,
              ["layer", "year", "n_edges", "n_nodes", "n_source_docs"])


if __name__ == "__main__":
    main()
