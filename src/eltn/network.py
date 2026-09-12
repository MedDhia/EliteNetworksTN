"""Dynamic network construction from the spell panel.

Five relations are exported, each with an explicit validity interval so the
network can be replayed over time rather than collapsed into one static
graph:

``affiliation``  person -> organisation, valid for the length of the spell
                 (the bipartite backbone).
``colleague``    person -- person, valid for the overlap of two spells in the
                 same organisation.  This is the projection most elite-network
                 work uses, and the overlap interval is what makes it dynamic.
``succession``   person -> person, directed from outgoing to incoming holder
                 of the same office, dated at the handover.
``signature``    signatory -> appointee, directed, dated at the act.  Who signs
                 whose appointment is the gazette's clearest trace of
                 patronage authority.
``delegation``   principal -> agent for delegations of signature.

Edges are written both as interval lists (Gephi/GraphML dynamic import, or
``networkx`` with ``start``/``end`` attributes) and as yearly snapshots for
analysts who prefer a stack of static graphs.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import pandas as pd

LOG = logging.getLogger(__name__)


def affiliation_edges(spells: pd.DataFrame) -> pd.DataFrame:
    """Person -> organisation, one edge per spell."""
    cols = ["person_id", "org_id", "org_name", "position_rank", "rank_score",
            "start_date", "end_date", "start_year", "end_year", "end_reason",
            "spell_id"]
    out = spells[cols].copy()
    out["relation"] = "affiliation"
    return out.rename(columns={"person_id": "source", "org_id": "target"})


def colleague_edges(spells: pd.DataFrame, *, min_days: int = 1,
                    max_org_size: int = 400) -> pd.DataFrame:
    """Person -- person co-affiliation, valid for the overlap of their spells.

    ``max_org_size`` guards against the quadratic blow-up of very large
    organisations (a ministry that appoints thousands of section chiefs is not
    a meaningful co-membership context); those are dropped and reported.
    """
    rows = []
    skipped = []
    for org_id, grp in spells.groupby("org_id"):
        if not org_id:
            continue
        if len(grp) > max_org_size:
            skipped.append((org_id, len(grp)))
            continue
        recs = grp[["person_id", "start_date", "end_date", "org_name",
                    "rank_score", "position_rank"]].to_dict("records")
        for a, b in combinations(recs, 2):
            if a["person_id"] == b["person_id"]:
                continue
            start = max(a["start_date"], b["start_date"])
            end = min(a["end_date"], b["end_date"])
            if (end - start).days < min_days:
                continue
            src, dst = sorted((a["person_id"], b["person_id"]))
            rows.append({
                "source": src,
                "target": dst,
                "org_id": org_id,
                "org_name": a["org_name"],
                "start_date": start,
                "end_date": end,
                "start_year": start.year,
                "end_year": end.year,
                "overlap_days": (end - start).days,
                "rank_gap": abs(a["rank_score"] - b["rank_score"]),
                "relation": "colleague",
            })
    if skipped:
        LOG.info("colleague: skipped %s oversized organisations (largest %s spells)",
                 len(skipped), max(s[1] for s in skipped))
    return pd.DataFrame(rows)


def succession_edges(spells: pd.DataFrame) -> pd.DataFrame:
    """Outgoing -> incoming holder of the same office."""
    rows = []
    for sp in spells.itertuples(index=False):
        if not sp.predecessor_id or sp.predecessor_id == sp.person_id:
            continue
        rows.append({
            "source": sp.predecessor_id,
            "target": sp.person_id,
            "office_id": sp.office_id,
            "org_id": sp.org_id,
            "org_name": sp.org_name,
            "position_rank": sp.position_rank,
            "date": sp.start_date,
            "year": sp.start_year,
            "relation": "succession",
        })
    return pd.DataFrame(rows)


def signature_edges(events: pd.DataFrame) -> pd.DataFrame:
    """Signatory of the act -> the person it appoints."""
    df = events[(events.signatory_id != "")
                & (events.person_id != "")
                & (events.signatory_id != events.person_id)]
    out = df[["signatory_id", "person_id", "signatory_office", "org_id",
              "org_name", "position_rank", "event_date", "event_year",
              "event_type", "act_kind", "act_number"]].copy()
    out["relation"] = "signature"
    return out.rename(columns={"signatory_id": "source", "person_id": "target",
                               "event_date": "date", "event_year": "year"})


def delegation_edges(events: pd.DataFrame) -> pd.DataFrame:
    """Principal -> agent for delegations of signature."""
    df = events[events.event_type == "delegation"].copy()
    if df.empty:
        return pd.DataFrame()
    # The principal is the signatory where one is printed, otherwise the
    # office named by the "par delegation du ministre ..." clause.
    df["principal"] = df.signatory_id.where(df.signatory_id != "", "")
    out = df[["principal", "person_id", "delegator_raw", "signatory_office",
              "org_id", "org_name", "event_date", "event_year", "act_number"]].copy()
    out["relation"] = "delegation"
    return out.rename(columns={"principal": "source", "person_id": "target",
                               "event_date": "date", "event_year": "year"})


def coappointment_edges(events: pd.DataFrame, *, max_act_size: int = 60) -> pd.DataFrame:
    """Persons named by the same act on the same day.

    A single decree naming several people is a much tighter signal than shared
    employer: they were selected together, by one authority, at one moment.
    """
    rows = []
    key_cols = ["issue_key", "act_seq"]
    for (issue_key, act_seq), grp in events.groupby(key_cols):
        people = sorted(set(grp.person_id) - {""})
        if len(people) < 2 or len(people) > max_act_size:
            continue
        date = grp.event_date.min()
        org = grp.org_name.mode()
        for a, b in combinations(people, 2):
            rows.append({
                "source": a,
                "target": b,
                "issue_key": issue_key,
                "act_seq": act_seq,
                "act_number": grp.act_number.iloc[0],
                "org_name": org.iloc[0] if len(org) else "",
                "date": date,
                "year": date.year if date else None,
                "cohort_size": len(people),
                "relation": "coappointment",
            })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Snapshots and graph export
# --------------------------------------------------------------------------


def yearly_snapshots(interval_edges: pd.DataFrame, years: range) -> pd.DataFrame:
    """Expand interval edges into one row per (edge, year) it is active in."""
    rows = []
    for e in interval_edges.itertuples(index=False):
        lo = max(e.start_year, years.start)
        hi = min(e.end_year, years.stop - 1)
        for y in range(lo, hi + 1):
            rows.append({"source": e.source, "target": e.target, "year": y,
                         "org_id": getattr(e, "org_id", ""),
                         "relation": getattr(e, "relation", "")})
    return pd.DataFrame(rows)


def to_gexf(nodes: pd.DataFrame, edges: pd.DataFrame, path: Path,
            *, label_col: str = "label") -> None:
    """Write a Gephi dynamic GEXF with year-interval edge spells."""
    import networkx as nx

    g = nx.MultiDiGraph()
    for n in nodes.itertuples(index=False):
        attrs = {k: ("" if pd.isna(v) else v) for k, v in n._asdict().items()
                 if k not in {"node_id"}}
        g.add_node(n.node_id, **attrs)
    for e in edges.itertuples(index=False):
        if e.source not in g or e.target not in g:
            continue
        g.add_edge(e.source, e.target,
                   relation=getattr(e, "relation", ""),
                   weight=float(getattr(e, "weight", 1.0) or 1.0),
                   start=int(e.start_year), end=int(e.end_year))
    path.parent.mkdir(parents=True, exist_ok=True)
    nx.write_gexf(g, path)
