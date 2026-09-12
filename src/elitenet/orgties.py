"""Stage 11 -- the organisation-to-organisation tie layer.

The person-organisation network is strictly two-mode, and the whole TERGM layer
depends on that: mode-blocked vertex ids, `bipartite = n1`, gwb1degree and
gwb2degree, b1star and b2star. Adding org-org ties to `spells.csv` would break
every one of those silently.

So this is a separate layer. It is one-mode, which means the ordinary ERGM
closure terms -- `triangle`, `gwesp`, `kstar` -- are valid on it and never were
on the bipartite panel. Both layers share a vocabulary and a censoring
convention so they are read the same way.

What the sources support, and what they do not:

* The dominant clause is "actionnaires : la societe X", which **confirms** a
  standing holding at a filing date. It does not open one. Onsets in this layer
  are therefore left-censored far more often than in the person-organisation
  layer, and a duration analysis over it would be measuring filing frequency
  rather than ownership tenure.
* A transfer -- "X a cede sa participation au capital de Y" -- is the only
  clause that genuinely dates a boundary, and it is rare by comparison.
* Both endpoints must resolve to distinct seed organisations. A mention that
  resolves to the subject firm itself is a self-tie and is dropped, not counted.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from datetime import date, datetime

from .paths import INTERIM, PROCESSED, ensure_dirs, window
from .resolve import (THRESHOLD_AMBIGUOUS, THRESHOLD_RESOLVED, SeedIndex,
                      best_org_match, load_seed, resolve_org)
from .spells import periods

# How each relation bears on the interval. `shares_ceded` is the holder giving
# a stake up, so it closes the tie; `shares_acquired` and a subscription open
# one. The rest prove the tie was live at that date without dating its start.
OPENING = {"shares_acquired", "capital_subscribed"}
CLOSING = {"shares_ceded"}
CONFIRMING = {"shareholder_confirmed", "auditor", "branch"}

# Ownership proper, as against the professional-service and structural
# relations carried alongside it. Exports default to this.
OWNERSHIP = {"shares_acquired", "shares_ceded", "shareholder_confirmed",
             "capital_subscribed"}

FIELDS_TIES = [
    "org_tie_obs_id", "holder_id", "holder_label", "target_id", "target_label",
    "relation", "is_ownership", "obs_kind", "obs_date", "date_precision",
    "holder_mention", "target_mention", "holder_match", "target_match",
    "score", "link_status", "evidence_quote", "event_id", "block_uid",
    "issue_uid", "folio_page", "extract_confidence",
]
# The queue carries two kinds of row -- a dyad that resolved ambiguously, and
# an observation with only one end resolved -- so it names the reason and, for
# the second kind, the mention that failed and what it came closest to. Without
# those columns the row is not adjudicable: a coder cannot confirm or reject a
# match they cannot see.
FIELDS_QUEUE = FIELDS_TIES + [
    "queue_reason", "failed_end", "failed_mention",
    "near_org_id", "near_org_label", "near_score",
]
FIELDS_SPELLS = [
    "org_spell_id", "holder_id", "holder_label", "target_id", "target_label",
    "relation", "is_ownership", "layer", "onset", "terminus",
    "onset_lo", "onset_hi", "terminus_lo", "terminus_hi",
    "left_censored", "right_censored", "onset_rule", "terminus_rule",
    "onset_event_id", "terminus_event_id", "duration_days",
    "evidence_n", "evidence_tier", "link_status", "confidence", "needs_review",
]
FIELDS_PANEL = [
    "panel_id", "granularity", "period_start", "period_end",
    "from_node_id", "to_node_id", "relation", "is_ownership", "layer",
    "certainty", "evidence_tier", "org_spell_id",
]


def _d(iso: str) -> date | None:
    if not iso:
        return None
    try:
        return datetime.strptime(iso[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _sid(*parts: str) -> str:
    return "OS_" + hashlib.blake2s("|".join(parts).encode(),
                                   digest_size=11).hexdigest()


def _read(name: str) -> list[dict]:
    path = PROCESSED / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def read_events() -> list[dict]:
    """Extraction output, from the interim jsonl where it exists.

    `resolve` and `spells` both read events_raw.jsonl directly, and this stage
    consumes the same thing, so it reads from the same place rather than
    depending on `export` having flattened it first -- which would have made
    the stage order in the Makefile wrong. From a clone, where data/interim is
    git-ignored, the committed events.csv is the fallback.
    """
    raw = INTERIM / "events_raw.jsonl"
    if raw.exists():
        out = []
        with raw.open(encoding="utf-8") as fh:
            for line in fh:
                e = json.loads(line)
                if e.get("event_type") == "org_tie":
                    out.append(e)
        return out
    return [e for e in _read("events.csv") if e.get("event_type") == "org_tie"]


def _write(name: str, rows: list[dict], fields: list[str]) -> None:
    path = PROCESSED / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def score_link(holder_match: float, target_match: float, n_obs: int,
               extract_conf: float) -> float:
    """Confidence in an organisation-to-organisation link.

    Weaker evidence than the person-organisation case, and deliberately scored
    so. There, a link is anchored on the dyad: the organisation has to agree
    before a name is allowed to decide, which is what makes a common name
    tractable. Here both ends are organisations and there is no third thing to
    anchor against, so the score rests on how well each end matched, how often
    the pair was seen, and how certain the clause was.
    """
    ends = min(holder_match, target_match)      # the weaker end governs
    repeat = min(0.10, 0.035 * (n_obs - 1))     # corroboration across issues
    return round(min(1.0, 0.75 * ends + 0.15 * extract_conf + repeat), 4)


# One observation row, shared by the resolved path and the review queue so a
# queued row carries the same provenance columns a resolved one does.
def _obs_row(e: dict, idx: SeedIndex, hid: str, hs: float, tid: str, ts: float,
             hlabel: str, tlabel: str) -> dict:
    relation = e.get("role_canonical") or "shareholder_confirmed"
    kind = ("opening" if relation in OPENING else
            "closing" if relation in CLOSING else "confirmation")
    return {
        "org_tie_obs_id": _sid(e.get("event_id", ""), hid, tid, relation),
        "holder_id": hid, "holder_label": hlabel,
        "target_id": tid, "target_label": tlabel,
        "relation": relation,
        "is_ownership": int(relation in OWNERSHIP),
        "obs_kind": kind,
        "obs_date": e.get("event_date", ""),
        "date_precision": e.get("date_precision", ""),
        "holder_mention": (e.get("counterparty_mention") or "").strip(),
        "target_mention": (e.get("org_mention") or "").strip(),
        "holder_match": round(hs, 4), "target_match": round(ts, 4),
        "evidence_quote": e.get("evidence_quote", ""),
        "event_id": e.get("event_id", ""), "block_uid": e.get("block_uid", ""),
        "issue_uid": e.get("issue_uid", ""), "folio_page": e.get("folio_page", ""),
        "extract_confidence": e.get("extract_confidence", ""),
    }


def observations(events: list[dict],
                 idx: SeedIndex) -> tuple[list[dict], list[dict], dict]:
    """Resolve each org_tie event to a (holder, target) pair of seed orgs.

    Returns the resolved observations, the rows that need a human (one end
    resolved), and diagnostics.
    """
    out: list[dict] = []
    pending: list[dict] = []
    diag = defaultdict(int)
    cache: dict[str, tuple[str, float]] = {}

    def rv(mention: str) -> tuple[str, float]:
        if mention not in cache:
            cache[mention] = resolve_org(mention, idx)
        return cache[mention]

    # The extractor emits both candidate targets for a clause that states one,
    # sharing an `alt_group`, and the choice belongs here: this is the first
    # stage that knows which candidate is a seed organisation. Alternates are
    # walked in the order emitted -- stated target first -- and the first that
    # resolves at both ends wins the group, so a stated target that resolves
    # beats the subject firm and a stated target that does not costs nothing.
    # Collapsing by group is also what keeps one clause from becoming two
    # dyads.
    groups: dict[str, list[dict]] = defaultdict(list)
    singles: list[dict] = []
    for e in events:
        if e.get("event_type") != "org_tie":
            continue
        g = (e.get("alt_group") or "").strip()
        (groups[g] if g else singles).append(e)

    chosen: list[dict] = list(singles)
    for g, alts in groups.items():
        both = [a for a in alts
                if rv((a.get("counterparty_mention") or "").strip())[0]
                and rv((a.get("org_mention") or "").strip())[0]]
        if both:
            diag["alt_group_target_chosen"] += 1
            # The first alternate is the stated target; taking it over the
            # subject firm is only right when it actually resolved, which is
            # the measured failure of the old unconditional override.
            if both[0] is not alts[0]:
                diag["alt_group_fell_back_to_subject"] += 1
            chosen.append(both[0])
        else:
            # Nothing in the group resolves at both ends. Keep the first
            # alternate so the clause still reaches the review queue rather
            # than vanishing, and count the group once, not twice.
            diag["alt_group_unresolved"] += 1
            chosen.append(alts[0])

    for e in chosen:
        diag["events"] += 1
        holder_m = (e.get("counterparty_mention") or "").strip()
        target_m = (e.get("org_mention") or "").strip()
        hid, hs = rv(holder_m)
        tid, ts = rv(target_m)
        if not hid and not tid:
            diag["neither_end_resolved"] += 1
            continue
        if not hid or not tid:
            # One end is a seed organisation and the other is not. This is the
            # adjudicable material: the resolved end anchors the dyad, so a
            # coder has only to judge a single name. It used to reach nothing
            # -- the queue was fed only by the ambiguous band of score_link,
            # which resolve_org's 0.88 floor makes unreachable, so the file was
            # always empty while ten thousand of these were dropped silently.
            diag["one_end_resolved"] += 1
            failed_m = target_m if hid else holder_m
            near_id, near_s = best_org_match(failed_m, idx)
            pending.append({
                **_obs_row(e, idx,
                           hid or "", hs, tid or "", ts,
                           idx.orgs[hid]["label"] if hid else "",
                           idx.orgs[tid]["label"] if tid else ""),
                "score": round(near_s, 4), "link_status": "unresolved",
                "queue_reason": "one_end_resolved",
                "failed_end": "target" if hid else "holder",
                "failed_mention": failed_m,
                "near_org_id": near_id,
                "near_org_label": idx.orgs[near_id]["label"] if near_id else "",
                "near_score": round(near_s, 4),
            })
            continue
        if hid == tid:
            # The clause named the subject firm as its own party. Usually the
            # target capture and the holder capture landed on the same name.
            diag["self_match_dropped"] += 1
            continue
        out.append(_obs_row(e, idx, hid, hs, tid, ts,
                            idx.orgs[hid].get("label", ""),
                            idx.orgs[tid].get("label", "")))
    diag["resolved_observations"] = len(out)
    diag["queued_one_end"] = len(pending)
    return out, pending, dict(diag)


def build_spells(obs: list[dict], seed_edges: list[dict],
                 idx: SeedIndex) -> tuple[list[dict], list[dict], dict]:
    """Group observations into intervals; carry undated seed ties alongside."""
    w_start, w_end = window()
    by_dyad: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for o in obs:
        by_dyad[(o["holder_id"], o["target_id"], o["relation"])].append(o)

    spells: list[dict] = []
    queue: list[dict] = []
    diag = defaultdict(int)

    for (hid, tid, relation), rows in by_dyad.items():
        dated = sorted((r for r in rows if _d(r["obs_date"])),
                       key=lambda r: r["obs_date"])
        score = score_link(
            min(float(r["holder_match"]) for r in rows),
            min(float(r["target_match"]) for r in rows),
            len(rows),
            max((float(r["extract_confidence"] or 0) for r in rows), default=0.0),
        )
        status = ("resolved" if score >= THRESHOLD_RESOLVED else
                  "ambiguous" if score >= THRESHOLD_AMBIGUOUS else "unresolved")
        for r in rows:
            r["score"] = score
            r["link_status"] = status
        if status != "resolved":
            diag["not_resolved_dyads"] += 1
            if status == "ambiguous":
                queue.append({**rows[0], "score": score, "link_status": status,
                              "queue_reason": "ambiguous_dyad"})
            continue
        if not dated:
            diag["resolved_but_undated"] += 1
            continue

        opens = [r for r in dated if r["obs_kind"] == "opening"]
        closes = [r for r in dated if r["obs_kind"] == "closing"]
        confs = [r for r in dated if r["obs_kind"] == "confirmation"]

        onset = onset_lo = onset_hi = None
        onset_rule = ""
        onset_event = ""
        if opens:
            onset = onset_lo = onset_hi = _d(opens[0]["obs_date"])
            onset_rule = f"event:{opens[0]['relation']}"
            onset_event = opens[0]["event_id"]
        elif confs:
            # A confirmation proves the tie was live, not when it began. The
            # onset is bounded above by it and left-censored below: the window
            # start is a bound, not an estimate, and must not be substituted
            # for a date.
            onset_hi = _d(confs[0]["obs_date"])
            onset_lo = w_start
            onset_rule = "left_censored:first_confirmation"
            onset_event = confs[0]["event_id"]
            diag["left_censored_onsets"] += 1

        terminus = terminus_lo = terminus_hi = None
        terminus_rule = ""
        terminus_event = ""
        if closes:
            last_open = onset_hi or onset
            cand = [r for r in closes
                    if not last_open or _d(r["obs_date"]) >= last_open]
            if cand:
                terminus = terminus_lo = terminus_hi = _d(cand[-1]["obs_date"])
                terminus_rule = "event:shares_ceded"
                terminus_event = cand[-1]["event_id"]
            else:
                # A cession predating every confirmation of the same dyad is
                # not this spell's end: the stake was rebuilt, or one of the
                # two readings is wrong. Recorded rather than forced.
                diag["cession_before_onset"] += 1

        eff_onset = onset or onset_hi
        spells.append({
            "org_spell_id": _sid(hid, tid, relation),
            "holder_id": hid, "holder_label": idx.orgs[hid].get("label", ""),
            "target_id": tid, "target_label": idx.orgs[tid].get("label", ""),
            "relation": relation, "is_ownership": int(relation in OWNERSHIP),
            "layer": "ownership" if relation in OWNERSHIP else "corporate_other",
            "onset": onset.isoformat() if onset else "",
            "terminus": terminus.isoformat() if terminus else "",
            "onset_lo": onset_lo.isoformat() if onset_lo else "",
            "onset_hi": onset_hi.isoformat() if onset_hi else "",
            "terminus_lo": terminus_lo.isoformat() if terminus_lo else "",
            "terminus_hi": (terminus_hi.isoformat() if terminus_hi
                            else w_end.isoformat()),
            "left_censored": str(onset is None and onset_hi is not None),
            "right_censored": str(terminus is None),
            "onset_rule": onset_rule, "terminus_rule": terminus_rule,
            "onset_event_id": onset_event, "terminus_event_id": terminus_event,
            "duration_days": ((terminus - eff_onset).days
                              if terminus and eff_onset else ""),
            "evidence_n": len(rows), "evidence_tier": "gazette_dated",
            "link_status": status, "confidence": score,
            "needs_review": str(score < 0.8),
        })

    # Undated seed organisation-organisation ties, carried exactly as the
    # undated person-organisation ties already are: present, dateless, and
    # excludable by evidence_tier. Assigning them dates would manufacture the
    # variation the dataset exists to measure.
    seen = {(s["holder_id"], s["target_id"], s["relation"]) for s in spells}
    for e in seed_edges:
        a, b = e["from_node_id"], e["to_node_id"]
        if a not in idx.orgs or b not in idx.orgs or a == b:
            continue
        relation = _seed_relation(e)
        if not relation or (a, b, relation) in seen:
            continue
        spells.append({
            "org_spell_id": _sid(a, b, relation, "seed"),
            "holder_id": a, "holder_label": e.get("from_label", ""),
            "target_id": b, "target_label": e.get("to_label", ""),
            "relation": relation, "is_ownership": int(relation in OWNERSHIP),
            "layer": "ownership" if relation in OWNERSHIP else "corporate_other",
            "onset": "", "terminus": "", "onset_lo": "", "onset_hi": "",
            "terminus_lo": "", "terminus_hi": "",
            "left_censored": "True", "right_censored": "True",
            "onset_rule": "seed_undated", "terminus_rule": "",
            "onset_event_id": "", "terminus_event_id": "", "duration_days": "",
            "evidence_n": 1, "evidence_tier": "seed_undated",
            "link_status": "seed", "confidence": 1.0, "needs_review": "False",
        })
        diag["seed_ties_carried"] += 1

    return spells, queue, dict(diag)


_SEED_RELATION = {
    "SHAREHOLDER": "shareholder_confirmed",
    "FUNDER": "funder",
    "MEMBER": "member",
    "BRANCH": "branch",
}


def _seed_relation(edge: dict) -> str:
    raw = (edge.get("edge_label_raw") or "").strip().upper()
    if raw in _SEED_RELATION:
        return _SEED_RELATION[raw]
    return "corporate_officer" if edge.get("tie_class") == "corporate_officer" else ""


def build_panel(spells: list[dict]) -> list[dict]:
    """Ties active per year. Dated spells only, for the reason panel_edges
    gives: an undated tie placed in a time slice asserts a presence the
    evidence does not support."""
    out: list[dict] = []
    for period, p_start, p_end in periods("yearly"):
        for s in spells:
            if s["evidence_tier"] != "gazette_dated":
                continue
            onset = _d(s["onset"]) or _d(s["onset_hi"])
            term = _d(s["terminus"]) or _d(s["terminus_hi"])
            if onset and onset > p_end:
                continue
            if term and term < p_start:
                continue
            core_lo = _d(s["onset"]) or onset
            certainty = "certain" if (core_lo and core_lo <= p_end and
                                      s["left_censored"] == "False") else "probable"
            out.append({
                "panel_id": f"yearly:{period}", "granularity": "yearly",
                "period_start": p_start.isoformat(), "period_end": p_end.isoformat(),
                "from_node_id": s["holder_id"], "to_node_id": s["target_id"],
                "relation": s["relation"], "is_ownership": s["is_ownership"],
                "layer": s["layer"], "certainty": certainty,
                "evidence_tier": s["evidence_tier"],
                "org_spell_id": s["org_spell_id"],
            })
    return out


def run() -> dict:
    ensure_dirs()
    idx = load_seed()
    obs, pending, d1 = observations(read_events(), idx)
    spells, queue, d2 = build_spells(obs, _read("seed_edges.csv"), idx)
    panel = build_panel(spells)
    # Both queue sources in one file, ambiguous dyads first: they are fewer and
    # a decision on one settles every observation of that dyad.
    queue = queue + pending

    _write("org_ties.csv", obs, FIELDS_TIES)
    _write("org_tie_spells.csv", spells, FIELDS_SPELLS)
    _write("panel_org_ties_yearly.csv", panel, FIELDS_PANEL)
    _write("org_ties_review_queue.csv", queue, FIELDS_QUEUE)

    dated = [s for s in spells if s["evidence_tier"] == "gazette_dated"]
    diag = {**d1, **d2,
            "dyads_dated": len({(s["holder_id"], s["target_id"]) for s in dated}),
            "spells_dated": len(dated),
            "spells_seed_undated": len(spells) - len(dated),
            "panel_rows": len(panel), "review_queue": len(queue)}
    print("organisation-to-organisation layer")
    for k in ("events", "resolved_observations", "one_end_resolved",
              "neither_end_resolved", "self_match_dropped",
              "alt_group_target_chosen", "alt_group_fell_back_to_subject",
              "alt_group_unresolved", "queued_one_end", "not_resolved_dyads",
              "left_censored_onsets", "cession_before_onset", "dyads_dated",
              "spells_dated", "spells_seed_undated", "seed_ties_carried",
              "panel_rows", "review_queue"):
        if k in diag:
            print(f"  {k:<26} {diag[k]:>8,}")
    return diag


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(
        description="Build the organisation-to-organisation tie layer."
    ).parse_args(argv)
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
