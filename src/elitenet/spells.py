"""Stage 7 -- turn dated events into tie spells and panel snapshots.

Gazette events are time-stamped assertions about state transitions, and the
gazette publishes arrivals far more reliably than departures: in 2008-2012 the
window carries roughly ten appointment formulas for every explicit exit. A
spell is therefore an interval-censored object, and the censoring is encoded
rather than imputed away.

Three distinctions matter and are kept explicit:

* ``onset``/``terminus`` are point estimates for analysis; ``onset_lo``,
  ``onset_hi``, ``terminus_lo`` and ``terminus_hi`` carry what is actually
  known. The certain core of a spell is ``[onset_hi, terminus_lo]``.
* A renewal, or a later mention of the same officer, is a **confirmation**: it
  proves the tie existed at that moment without asserting when it began.
* Undated seed ties are retained with no invented dates, flagged
  ``seed_only``, so they can be excluded from any survival analysis.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from .paths import INTERIM, PROCESSED, ensure_dirs, load_config

WINDOW_START = date(2008, 1, 1)
WINDOW_END = date(2012, 12, 31)

OPENING = {"appointed", "constituted", "charged_with_functions", "delegated_to_body"}
CONFIRMING = {"renewed"}
CLOSING = {"resigned", "revoked", "terminated", "retired"}
ORG_CLOSING = {"dissolved", "liquidated"}

SPELL_FIELDS = [
    "spell_id", "person_id", "person_label", "org_id", "org_label",
    "role_canonical", "layer", "tie_class",
    "onset", "terminus", "onset_lo", "onset_hi", "terminus_lo", "terminus_hi",
    "left_censored", "right_censored",
    "onset_interval_censored", "terminus_interval_censored",
    "onset_rule", "terminus_rule", "onset_event_id", "terminus_event_id",
    "expected_end_date", "duration_days", "duration_lo", "duration_hi",
    "evidence_n", "evidence_tier", "link_status", "confidence", "needs_review",
]

OBS_FIELDS = ["spell_id", "obs_date", "obs_kind", "obs_event_id", "evidence_quote"]
PANEL_FIELDS = ["panel_id", "granularity", "period_start", "period_end",
                "from_node_id", "to_node_id", "role_canonical", "layer",
                "certainty", "evidence_tier", "spell_id"]


def _d(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _iso(d: date | None) -> str:
    return d.isoformat() if d else ""


def _spell_id(*parts) -> str:
    return "SP_" + hashlib.blake2b("|".join(map(str, parts)).encode(),
                                   digest_size=10).hexdigest()


@dataclass
class Spell:
    person_id: str
    org_id: str
    role: str
    onset: date | None = None
    onset_lo: date | None = None
    onset_hi: date | None = None
    terminus: date | None = None
    terminus_lo: date | None = None
    terminus_hi: date | None = None
    onset_rule: str = ""
    terminus_rule: str = ""
    onset_event_id: str = ""
    terminus_event_id: str = ""
    expected_end: date | None = None
    observations: list[dict] = field(default_factory=list)
    confidence: float = 0.0
    link_status: str = ""
    evidence_tier: str = "gazette_dated"
    person_label: str = ""
    org_label: str = ""
    layer: str = ""
    tie_class: str = ""

    @property
    def open(self) -> bool:
        return self.terminus is None and self.terminus_rule == ""


def build_spells(events: list[dict], resolution: dict, roles_cfg: dict) -> tuple[list[Spell], int]:
    """Group resolved events into spells per (person, organisation, role)."""
    single_holder = set(roles_cfg["single_holder_roles"])

    # Organisation-level events (dissolution, liquidation) carry no person, so
    # they cannot be looked up by dyad. Build a mention -> resolved id map from
    # the dyads that were resolved, so a firm's death can close its open ties.
    org_of_mention: dict[str, str] = {}
    for r in resolution.values():
        if r.get("org_mention") and r.get("resolved_org_id"):
            org_of_mention.setdefault(r["org_mention"], r["resolved_org_id"])

    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    org_events: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        res = resolution.get(f"{e.get('person_mention','')}||{e.get('org_mention','')}")
        if e["event_type"] in ORG_CLOSING:
            oid = ((res or {}).get("resolved_org_id")
                   or org_of_mention.get(e.get("org_mention") or ""))
            if oid:
                org_events[oid].append(e)
            continue
        if not res or res["link_status"] == "unresolved":
            continue
        pid = res["resolved_person_id"]
        oid = res["resolved_org_id"] or ("ORGMENTION_" + (e.get("org_mention") or "")[:60])
        if not pid or not oid:
            continue
        role = e.get("role_canonical") or "unspecified"
        groups[(pid, oid, role)].append(e)

    spells: list[Spell] = []
    replaced = 0
    # Track who currently holds each single-holder post, to close a spell when
    # someone else is appointed to it. Explicit exits are rare, so replacement
    # is what makes most departures observable at all.
    incumbents: dict[tuple[str, str], list[Spell]] = defaultdict(list)

    for (pid, oid, role), evs in groups.items():
        evs.sort(key=lambda e: (e.get("event_date") or "9999", e.get("event_id", "")))
        res = resolution[f"{evs[0].get('person_mention','')}||{evs[0].get('org_mention','')}"]
        current: Spell | None = None

        for e in evs:
            ed = _d(e.get("event_date"))
            interval = e.get("date_precision") == "pub_only"
            lo = _d(e.get("event_date_lo"))
            hi = _d(e.get("event_date_hi")) or ed
            etype = e["event_type"]

            if etype in OPENING:
                if current and current.open:
                    current.observations.append({
                        "obs_date": _iso(ed), "obs_kind": "confirmation",
                        "obs_event_id": e.get("event_id", ""),
                        "evidence_quote": e.get("evidence_quote", ""),
                    })
                    if ed and (current.onset_hi is None or ed < current.onset_hi):
                        pass
                    continue
                current = Spell(
                    person_id=pid, org_id=oid, role=role, onset=ed,
                    onset_lo=lo, onset_hi=hi,
                    onset_rule=f"event:{etype}", onset_event_id=e.get("event_id", ""),
                    onset_interval_censored=interval,
                    confidence=float(e.get("extract_confidence") or 0) * float(res["score"] or 0),
                    link_status=res["link_status"],
                    person_label=res["resolved_person_label"],
                    org_label=res["resolved_org_label"] or e.get("org_mention", ""),
                    layer="state" if e.get("domain") == "state" else "corporate",
                    tie_class="state_office" if e.get("domain") == "state" else "corporate_officer",
                ) if False else Spell(
                    person_id=pid, org_id=oid, role=role, onset=ed,
                    onset_lo=lo, onset_hi=hi,
                    onset_rule=f"event:{etype}", onset_event_id=e.get("event_id", ""),
                    confidence=round(float(e.get("extract_confidence") or 0)
                                     * float(res["score"] or 0), 4),
                    link_status=res["link_status"],
                    person_label=res["resolved_person_label"],
                    org_label=res["resolved_org_label"] or e.get("org_mention", ""),
                    layer="state" if e.get("domain") == "state" else "corporate",
                    tie_class="state_office" if e.get("domain") == "state" else "corporate_officer",
                )
                current.observations.append({
                    "obs_date": _iso(ed), "obs_kind": "onset",
                    "obs_event_id": e.get("event_id", ""),
                    "evidence_quote": e.get("evidence_quote", ""),
                })
                years = e.get("mandate_years")
                if years and ed:
                    try:
                        current.expected_end = ed + timedelta(days=int(float(years) * 365.25))
                    except (TypeError, ValueError):
                        pass
                spells.append(current)
                if role in single_holder:
                    incumbents[(oid, role)].append(current)

            elif etype in CONFIRMING:
                if current and current.open:
                    current.observations.append({
                        "obs_date": _iso(ed), "obs_kind": "renewal",
                        "obs_event_id": e.get("event_id", ""),
                        "evidence_quote": e.get("evidence_quote", ""),
                    })
                else:
                    # A renewal with no observed start: the tie began before we
                    # saw it, so the onset is left-censored rather than set here.
                    current = Spell(
                        person_id=pid, org_id=oid, role=role,
                        onset=None, onset_lo=None, onset_hi=ed,
                        onset_rule="renewal_implies_earlier_onset",
                        onset_event_id=e.get("event_id", ""),
                        confidence=round(float(e.get("extract_confidence") or 0)
                                         * float(res["score"] or 0), 4),
                        link_status=res["link_status"],
                        person_label=res["resolved_person_label"],
                        org_label=res["resolved_org_label"] or e.get("org_mention", ""),
                        layer="state" if e.get("domain") == "state" else "corporate",
                        tie_class="state_office" if e.get("domain") == "state"
                        else "corporate_officer",
                    )
                    current.observations.append({
                        "obs_date": _iso(ed), "obs_kind": "renewal",
                        "obs_event_id": e.get("event_id", ""),
                        "evidence_quote": e.get("evidence_quote", ""),
                    })
                    spells.append(current)
                    if role in single_holder:
                        incumbents[(oid, role)].append(current)

            elif etype in CLOSING:
                target = current if (current and current.open) else None
                if target is None:
                    # An exit with no observed entry: the tie existed and ended,
                    # with an unknown start.
                    target = Spell(
                        person_id=pid, org_id=oid, role=role,
                        onset=None, onset_lo=None, onset_hi=ed,
                        onset_rule="exit_implies_earlier_onset",
                        confidence=round(float(e.get("extract_confidence") or 0)
                                         * float(res["score"] or 0), 4),
                        link_status=res["link_status"],
                        person_label=res["resolved_person_label"],
                        org_label=res["resolved_org_label"] or e.get("org_mention", ""),
                        layer="state" if e.get("domain") == "state" else "corporate",
                        tie_class="state_office" if e.get("domain") == "state"
                        else "corporate_officer",
                    )
                    spells.append(target)
                target.terminus = ed
                target.terminus_lo = lo or target.onset_hi
                target.terminus_hi = hi
                target.terminus_rule = f"event:{etype}"
                target.terminus_event_id = e.get("event_id", "")
                target.observations.append({
                    "obs_date": _iso(ed), "obs_kind": "terminus",
                    "obs_event_id": e.get("event_id", ""),
                    "evidence_quote": e.get("evidence_quote", ""),
                })
                current = None

    # --- replacement inference on single-holder posts -------------------- #
    for (oid, role), holders in incumbents.items():
        holders.sort(key=lambda s: (s.onset or s.onset_hi or WINDOW_END))
        for i, sp in enumerate(holders[:-1]):
            nxt = holders[i + 1]
            start_next = nxt.onset or nxt.onset_hi
            if sp.open and start_next and sp.person_id != nxt.person_id:
                sp.terminus = start_next
                sp.terminus_lo = sp.onset_hi or sp.onset
                sp.terminus_hi = start_next
                sp.terminus_rule = "displaced_by"
                sp.terminus_event_id = nxt.onset_event_id
                # The incumbent may have left earlier; only the upper bound is known.
                sp.terminus_interval_censored = True
                replaced += 1

    # --- organisation death closes its open ties ------------------------ #
    org_death: dict[str, date] = {}
    for oid, evs in org_events.items():
        ds = sorted(d for d in (_d(e.get("event_date")) for e in evs) if d)
        if ds:
            org_death[oid] = ds[0]
    for sp in spells:
        if sp.open and sp.org_id in org_death:
            sp.terminus = org_death[sp.org_id]
            sp.terminus_lo = sp.onset_hi or sp.onset
            sp.terminus_hi = org_death[sp.org_id]
            sp.terminus_rule = "org_dissolved"
            sp.terminus_interval_censored = True

    return spells, replaced


def seed_only_spells(resolved_person_ids: set[str]) -> list[Spell]:
    """Carry undated seed ties through as flagged, dateless spells.

    A seed tie is evidence that a relationship existed; it is not evidence
    about when. Inventing an onset would manufacture the very variation the
    dataset is meant to measure, so these carry no dates at all and are
    labelled so they can be filtered out wholesale.
    """
    out: list[Spell] = []
    with (PROCESSED / "seed_edges.csv").open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row["from_type"] != "PERSON":
                continue
            sp = Spell(
                person_id=row["from_node_id"], org_id=row["to_node_id"],
                role=row["role_canonical"],
                person_label=row["from_label"], org_label=row["to_label"],
                layer=row["layer"], tie_class=row["tie_class"],
                evidence_tier="seed_undated", link_status="seed",
                confidence=0.5,
            )
            if row["is_former"] == "True":
                sp.onset_rule = "seed_former_tie"
                sp.terminus_rule = "ended_before_unknown_date"
            else:
                sp.onset_rule = "seed_current_tie"
            out.append(sp)
    return out


def finalise(sp: Spell) -> dict:
    left_cens = sp.onset is None
    right_cens = sp.terminus is None and sp.terminus_rule == ""
    dur = dur_lo = dur_hi = ""
    if sp.onset and sp.terminus:
        dur = (sp.terminus - sp.onset).days
    core_lo = sp.onset_hi or sp.onset
    core_hi = sp.terminus_lo or sp.terminus
    if core_lo and core_hi:
        dur_lo = max(0, (core_hi - core_lo).days)
    if (sp.onset_lo or sp.onset) and (sp.terminus_hi or sp.terminus):
        dur_hi = max(0, ((sp.terminus_hi or sp.terminus) - (sp.onset_lo or sp.onset)).days)
    return {
        "spell_id": _spell_id(sp.person_id, sp.org_id, sp.role,
                              _iso(sp.onset), sp.onset_rule),
        "person_id": sp.person_id, "person_label": sp.person_label,
        "org_id": sp.org_id, "org_label": sp.org_label,
        "role_canonical": sp.role, "layer": sp.layer, "tie_class": sp.tie_class,
        "onset": _iso(sp.onset), "terminus": _iso(sp.terminus),
        "onset_lo": _iso(sp.onset_lo), "onset_hi": _iso(sp.onset_hi),
        "terminus_lo": _iso(sp.terminus_lo), "terminus_hi": _iso(sp.terminus_hi),
        "left_censored": left_cens, "right_censored": right_cens,
        "onset_interval_censored": sp.onset is None and sp.onset_hi is not None,
        "terminus_interval_censored": getattr(sp, "terminus_interval_censored", False),
        "onset_rule": sp.onset_rule, "terminus_rule": sp.terminus_rule,
        "onset_event_id": sp.onset_event_id, "terminus_event_id": sp.terminus_event_id,
        "expected_end_date": _iso(sp.expected_end),
        "duration_days": dur, "duration_lo": dur_lo, "duration_hi": dur_hi,
        "evidence_n": len(sp.observations), "evidence_tier": sp.evidence_tier,
        "link_status": sp.link_status, "confidence": sp.confidence,
        "needs_review": sp.link_status == "ambiguous",
    }


def periods(granularity: str) -> list[tuple[str, date, date]]:
    out = []
    if granularity == "yearly":
        for y in range(WINDOW_START.year, WINDOW_END.year + 1):
            out.append((str(y), date(y, 1, 1), date(y, 12, 31)))
    else:
        for y in range(WINDOW_START.year, WINDOW_END.year + 1):
            for m in range(1, 13):
                end = date(y + (m == 12), (m % 12) + 1, 1) - timedelta(days=1)
                out.append((f"{y}-{m:02d}", date(y, m, 1), end))
    return out


def build_panels(spell_rows: list[dict], granularity: str) -> list[dict]:
    """Materialise the ties active in each period, with an explicit certainty.

    Every network statistic should be computed three times -- on `certain`
    ties, on `certain`+`probable`, and on all -- because that spread *is* the
    measurement-uncertainty sensitivity analysis for a gazette-derived network.
    """
    out: list[dict] = []
    for period, p_start, p_end in periods(granularity):
        for s in spell_rows:
            if s["evidence_tier"] == "seed_undated":
                # No dates at all: present in every period, flagged as such.
                certainty = "undated"
            else:
                onset = _d(s["onset"]) or _d(s["onset_lo"]) or _d(s["onset_hi"])
                term = _d(s["terminus"]) or _d(s["terminus_hi"])
                if onset and onset > p_end:
                    continue
                if term and term < p_start:
                    continue
                core_lo = _d(s["onset_hi"]) or onset
                core_hi = _d(s["terminus_lo"]) or term
                in_core = ((core_lo is None or core_lo <= p_end)
                           and (core_hi is None or core_hi >= p_start))
                if s["onset"] and (s["terminus"] or s["right_censored"]) and in_core:
                    certainty = "certain"
                elif in_core:
                    certainty = "probable"
                else:
                    certainty = "possible"
            out.append({
                "panel_id": f"{granularity}:{period}", "granularity": granularity,
                "period_start": p_start.isoformat(), "period_end": p_end.isoformat(),
                "from_node_id": s["person_id"], "to_node_id": s["org_id"],
                "role_canonical": s["role_canonical"], "layer": s["layer"],
                "certainty": certainty, "evidence_tier": s["evidence_tier"],
                "spell_id": s["spell_id"],
            })
    return out


def run(include_seed: bool = True) -> dict:
    ensure_dirs()
    roles_cfg = load_config("vocab_roles")
    with (PROCESSED / "resolution.csv").open(encoding="utf-8", newline="") as fh:
        resolution = {r["mention_key"]: r for r in csv.DictReader(fh)}
    with (INTERIM / "events_raw.jsonl").open(encoding="utf-8") as fh:
        events = [json.loads(line) for line in fh]

    spells, replaced = build_spells(events, resolution, roles_cfg)
    rows = [finalise(s) for s in spells]
    obs_rows = [{"spell_id": r["spell_id"], **o}
                for r, s in zip(rows, spells) for o in s.observations]

    n_gazette = len(rows)
    if include_seed:
        resolved_ids = {r["person_id"] for r in rows}
        rows += [finalise(s) for s in seed_only_spells(resolved_ids)]

    # right-censor anything still open at the window edge
    for r in rows:
        if r["evidence_tier"] == "gazette_dated" and r["right_censored"]:
            r["terminus_hi"] = WINDOW_END.isoformat()

    _write(PROCESSED / "spells.csv", rows, SPELL_FIELDS)
    _write(PROCESSED / "spell_observations.csv", obs_rows, OBS_FIELDS)

    stats = {
        "gazette_spells": n_gazette,
        "seed_only_spells": len(rows) - n_gazette,
        "closed_by_event": sum(1 for r in rows if r["terminus_rule"].startswith("event:")),
        "closed_by_replacement": replaced,
        "closed_by_org_death": sum(1 for r in rows if r["terminus_rule"] == "org_dissolved"),
        "right_censored": sum(1 for r in rows if r["right_censored"]),
        "left_censored": sum(1 for r in rows if r["left_censored"]),
        "observations": len(obs_rows),
    }
    for gran in load_config("scope")["panel"]["frequencies"]:
        panel = build_panels(rows, gran)
        _write(PROCESSED / f"panel_edges_{gran}.csv", panel, PANEL_FIELDS)
        stats[f"panel_rows_{gran}"] = len(panel)
    return stats


def _write(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description="Build spells and panel snapshots.").parse_args(argv)
    for k, v in run().items():
        print(f"  {k:26} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
