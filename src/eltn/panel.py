"""Build the longitudinal tables from the raw event stream.

Output tables
-------------
``events.csv``       normalised events, one row per person-office transition
``persons.csv``      person register with first/last appearance and peak rank
``organisations.csv``organisation register
``spells.csv``       office-holding spells with start, end and end reason
``person_year.csv``  person x year panel of office held

The spell logic is the analytically load-bearing part.  The gazette reliably
announces entries into office; it announces exits far less often.  Three
closure mechanisms are therefore used, in order of evidential strength:

1. an explicit termination / retirement act for the same person and office;
2. a successor's appointment naming the incumbent ("en remplacement de X") --
   this is the gazette's own statement that X's tenure ended;
3. the same person taking a different substantive office (offices below are
   treated as mutually exclusive, board seats excepted).

Spells that none of these close are right-censored, and the reason is
recorded so that survival models can treat them correctly.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from . import normalize as nz

LOG = logging.getLogger(__name__)

CENSOR_DATE = dt.date(2026, 12, 31)

# Event types that put someone into an office vs. take them out of one.
ENTRY_TYPES = {"appointment", "board", "renewal", "transfer"}
EXIT_TYPES = {"termination", "retirement", "resignation"}

# Offices held alongside a main post rather than instead of it.
CONCURRENT_RANKS = {"administrateur_ca"}


def _oid(prefix: str, value: str) -> str:
    if not value:
        return ""
    h = hashlib.blake2s(value.encode("utf-8"), digest_size=4).hexdigest()
    return f"{prefix}{h}"


def _to_date(v) -> dt.date | None:
    if not v or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return dt.date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Normalisation pass
# --------------------------------------------------------------------------


def normalise_events(raw: pd.DataFrame) -> pd.DataFrame:
    """Attach person / organisation / position ids to the raw event table."""
    df = raw.copy()
    for col in ("person_raw", "replaces_raw", "org_raw", "authority_raw",
                "position_raw", "signatory_name", "delegator_raw", "proposer_raw",
                "board_body_raw", "grade_raw", "section_raw"):
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str)

    # Persons: appointees, the incumbents they replace, and the officials who
    # sign the acts all belong in the same register.
    all_names = pd.unique(
        pd.concat([df.person_raw, df.replaces_raw, df.signatory_name]).astype(str)
    )
    all_names = [n for n in all_names if n.strip()]
    LOG.info("resolving %s distinct name strings", len(all_names))
    pmap = nz.resolve_persons(all_names)

    df["person_id"] = df.person_raw.map(pmap).fillna("")
    df["replaces_id"] = df.replaces_raw.map(pmap).fillna("")
    df["signatory_id"] = df.signatory_name.map(pmap).fillna("")

    # Organisation: the text of the act when it names one, otherwise the
    # ministry heading the act was published under.
    org_text = df.org_raw.map(nz.clean_org)
    heading = df.authority_raw.map(nz.clean_org)
    df["org_name"] = org_text.where(org_text.str.len() > 2, heading)
    df["org_source"] = pd.Series(
        ["text" if len(t) > 2 else ("heading" if len(h) > 2 else "none")
         for t, h in zip(org_text, heading)],
        index=df.index,
    )
    df["org_key"] = df.org_name.map(nz.org_key)
    df["org_id"] = df.org_key.map(lambda k: _oid("O", k))
    df["org_form"] = df.org_name.map(nz.org_form)
    df["org_portfolio"] = df.org_name.map(nz.ministry_portfolio)

    # The ministry heading is kept separately: it is the supervising body even
    # when the act names a subordinate agency as the workplace.
    df["parent_org_name"] = heading
    df["parent_org_id"] = heading.map(nz.org_key).map(lambda k: _oid("O", k))

    df["position_clean"] = df.position_raw.map(nz.clean_position)
    ranks = df.position_clean.map(nz.position_rank)
    df["position_rank"] = [r[0] for r in ranks]
    df["rank_score"] = [r[1] for r in ranks]
    df["position_key"] = df.position_clean.map(nz.position_key)

    df["office_id"] = [
        _oid("F", f"{o}|{r}|{p}") if (o or p) else ""
        for o, r, p in zip(df.org_key, df.position_rank, df.position_key)
    ]

    df["event_date"] = [
        _to_date(e) or _to_date(a) for e, a in zip(df.effect_date, df.act_date)
    ]
    df = df[df.event_date.notna() & (df.person_id != "")].copy()
    df["event_year"] = [d.year for d in df.event_date]
    df["event_id"] = [
        _oid("E", f"{k}|{s}|{p}|{f}|{t}")
        for k, s, p, f, t in zip(df.issue_key, df.act_seq, df.person_id,
                                 df.office_id, df.event_type)
    ]
    return df


# --------------------------------------------------------------------------
# Spells
# --------------------------------------------------------------------------


def build_spells(ev: pd.DataFrame, censor: dt.date = CENSOR_DATE) -> pd.DataFrame:
    """Turn entry/exit events into dated office-holding spells."""
    ev = ev.sort_values(["event_date", "issue_key", "act_seq"]).reset_index(drop=True)

    open_spells: dict[tuple[str, str], dict] = {}
    closed: list[dict] = []

    def close(key, end_date, reason, evidence):
        sp = open_spells.pop(key, None)
        if sp is None:
            return
        sp["end_date"] = max(end_date, sp["start_date"])
        sp["end_reason"] = reason
        sp["end_event_id"] = evidence
        closed.append(sp)

    def match(person: str, office: str, org: str, rank: str) -> tuple | None:
        """Find the open spell an event refers to.

        Matching on ``office_id`` alone is too strict: the gazette rarely
        repeats a job title verbatim, so a cessation act and the appointment
        it ends are often worded differently.  Falling back to the same
        organisation, first at the same rank and then at any rank, recovers
        those pairings; a person with exactly one open spell is the last
        resort.
        """
        if (person, office) in open_spells:
            return (person, office)
        mine = [k for k in open_spells if k[0] == person]
        if not mine:
            return None
        same_org_rank = [k for k in mine
                         if open_spells[k]["org_id"] == org
                         and open_spells[k]["position_rank"] == rank]
        if len(same_org_rank) == 1:
            return same_org_rank[0]
        same_org = [k for k in mine if open_spells[k]["org_id"] == org]
        if len(same_org) == 1:
            return same_org[0]
        if len(mine) == 1:
            return mine[0]
        return None

    for row in ev.itertuples(index=False):
        person, office = row.person_id, row.office_id
        if not office:
            continue
        key = (person, office)

        if row.event_type in EXIT_TYPES:
            found = match(person, office, row.org_id, row.position_rank)
            if found:
                close(found, row.event_date, row.event_type, row.event_id)
            continue

        if row.event_type == "delegation":
            continue  # a delegation is a tie, not tenure of an office

        if row.event_type not in ENTRY_TYPES:
            continue

        if row.event_type == "renewal":
            found = match(person, office, row.org_id, row.position_rank)
            if found:
                open_spells[found]["renewals"] += 1
                continue

        # The gazette's own statement that the previous holder is out.
        if row.replaces_id:
            found = match(row.replaces_id, office, row.org_id, row.position_rank)
            if found:
                close(found, row.event_date, "succeeded", row.event_id)

        # A restatement of a tenure already open in the same organisation at
        # the same rank is not a move -- the gazette simply worded the office
        # differently.  Only a genuine change of organisation or of rank ends
        # the previous spell.
        if key in open_spells:
            continue
        continuation = [k for k in open_spells
                        if k[0] == person
                        and open_spells[k]["org_id"] == row.org_id
                        and open_spells[k]["position_rank"] == row.position_rank]
        if continuation:
            continue

        if row.position_rank not in CONCURRENT_RANKS:
            for other in [k for k in open_spells
                          if k[0] == person and k[1] != office
                          and open_spells[k]["position_rank"] not in CONCURRENT_RANKS]:
                close(other, row.event_date, "moved", row.event_id)

        open_spells[key] = {
            "person_id": person,
            "office_id": office,
            "org_id": row.org_id,
            "org_name": row.org_name,
            "org_form": row.org_form,
            "org_portfolio": row.org_portfolio,
            "parent_org_id": row.parent_org_id,
            "parent_org_name": row.parent_org_name,
            "position_clean": row.position_clean,
            "position_rank": row.position_rank,
            "rank_score": row.rank_score,
            "start_date": row.event_date,
            "start_event_id": row.event_id,
            "start_act": f"{row.act_kind} {row.act_number}".strip(),
            "start_issue": row.issue_key,
            "pdf_url": row.pdf_url,
            "predecessor_id": row.replaces_id,
            "source_layer": row.source_layer,
            "renewals": 0,
            "end_date": None,
            "end_reason": "",
            "end_event_id": "",
        }

    for key, sp in open_spells.items():
        sp["end_date"] = censor
        sp["end_reason"] = "censored"
        closed.append(sp)

    out = pd.DataFrame(closed)
    if out.empty:
        return out
    out["start_year"] = [d.year for d in out.start_date]
    out["end_year"] = [d.year for d in out.end_date]
    out["duration_days"] = [(e - s).days for s, e in zip(out.start_date, out.end_date)]
    out["spell_id"] = [
        _oid("S", f"{p}|{o}|{s}") for p, o, s in
        zip(out.person_id, out.office_id, out.start_date)
    ]
    cols = ["spell_id"] + [c for c in out.columns if c != "spell_id"]
    return out[cols].sort_values(["start_date", "person_id"]).reset_index(drop=True)


def build_person_year(spells: pd.DataFrame, censor: dt.date = CENSOR_DATE) -> pd.DataFrame:
    """Explode spells into a person x year panel."""
    rows = []
    for sp in spells.itertuples(index=False):
        for year in range(sp.start_year, min(sp.end_year, censor.year) + 1):
            rows.append({
                "person_id": sp.person_id,
                "year": year,
                "spell_id": sp.spell_id,
                "office_id": sp.office_id,
                "org_id": sp.org_id,
                "org_name": sp.org_name,
                "org_portfolio": sp.org_portfolio,
                "parent_org_id": sp.parent_org_id,
                "position_rank": sp.position_rank,
                "rank_score": sp.rank_score,
                "is_entry_year": year == sp.start_year,
                "is_exit_year": year == sp.end_year and sp.end_reason != "censored",
                "censored": sp.end_reason == "censored",
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # One row per person-year: keep the highest office when several overlap.
    df = (df.sort_values(["person_id", "year", "rank_score"], ascending=[True, True, False])
            .drop_duplicates(["person_id", "year", "office_id"]))
    return df.reset_index(drop=True)


def build_registers(ev: pd.DataFrame, spells: pd.DataFrame
                    ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Person and organisation reference tables."""
    names: dict[str, Counter] = defaultdict(Counter)
    for pid, raw in zip(ev.person_id, ev.person_raw):
        if pid:
            names[pid][nz.clean_name(raw)] += 1
    for pid, raw in zip(ev.replaces_id, ev.replaces_raw):
        if pid and raw:
            names[pid][nz.clean_name(raw)] += 1

    grp = ev.groupby("person_id")
    persons = pd.DataFrame({
        "person_id": list(grp.groups.keys()),
    })
    agg = grp.agg(
        n_events=("event_id", "size"),
        first_year=("event_year", "min"),
        last_year=("event_year", "max"),
        peak_rank_score=("rank_score", "max"),
        n_orgs=("org_id", "nunique"),
    ).reset_index()
    persons = agg
    persons["name"] = persons.person_id.map(
        lambda p: nz.person_display(names[p]) if names.get(p) else ""
    )
    persons["name_variants"] = persons.person_id.map(
        lambda p: " | ".join(sorted(names.get(p, {}))) if names.get(p) else ""
    )
    peak = (ev.sort_values("rank_score", ascending=False)
              .drop_duplicates("person_id")[["person_id", "position_rank"]]
              .rename(columns={"position_rank": "peak_rank"}))
    persons = persons.merge(peak, on="person_id", how="left")
    if not spells.empty:
        sp = spells.groupby("person_id").agg(
            n_spells=("spell_id", "size"),
            career_days=("duration_days", "sum"),
        ).reset_index()
        persons = persons.merge(sp, on="person_id", how="left")
    persons = persons.sort_values("peak_rank_score", ascending=False).reset_index(drop=True)

    org_names: dict[str, Counter] = defaultdict(Counter)
    for oid, name in zip(ev.org_id, ev.org_name):
        if oid:
            org_names[oid][name] += 1
    orgs = ev[ev.org_id != ""].groupby("org_id").agg(
        n_events=("event_id", "size"),
        n_persons=("person_id", "nunique"),
        first_year=("event_year", "min"),
        last_year=("event_year", "max"),
    ).reset_index()
    orgs["org_name"] = orgs.org_id.map(
        lambda o: max(org_names[o].items(), key=lambda kv: (kv[1], len(kv[0])))[0]
    )
    orgs["org_form"] = orgs.org_id.map(
        ev.drop_duplicates("org_id").set_index("org_id").org_form.to_dict()
    )
    orgs["org_portfolio"] = orgs.org_id.map(
        ev.drop_duplicates("org_id").set_index("org_id").org_portfolio.to_dict()
    )
    orgs = orgs.sort_values("n_events", ascending=False).reset_index(drop=True)
    return persons, orgs
