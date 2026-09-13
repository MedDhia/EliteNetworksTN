"""Stage 13 -- the person-to-person kinship layer.

Marriage and natal-family claims, read off the two markers the gazette uses in
passing. "Mme Senda Bent Khaled Chaabouni epouse Khlil Babbou : 10 parts" is a
shareholder line, but it also states that two of the shareholders are married,
and that is a tie the person-organisation panel cannot express.

Why this is a separate layer, and not rows in `spells.csv`: that panel is
strictly two-mode and the whole TERGM specification rests on it -- mode-blocked
vertex ids, `bipartite = n1`, gwb1degree and gwb2degree. A person-person tie in
it would break every one of those silently. This layer is one-mode over
persons, the mirror of what `orgties` is over organisations.

What the sources support, and what they do not:

* A marriage marker **confirms** a standing state at the filing date. It never
  opens one: the gazette does not publish weddings. So every `spouse_of` onset
  is left-censored, and a duration read off this layer would be measuring how
  often the couple appear in print, not how long they were married.
* `widow_of` is the one marker that dates a boundary. It says the marriage had
  ended by the filing date, which bounds the terminus from above the way a
  cession bounds an ownership tie. It is kept as its own relation for that
  reason, not folded into `spouse_of`.
* `maiden_name_of` ("nee X") is **not** a marriage. It is the same woman's
  natal surname, and what it gives is a link to a family name rather than to a
  spouse. Folding it in -- which the single grammar group used to do -- would
  turn a birth name into a husband. It is carried here because a natal surname
  is real kinship evidence, in its own relation and its own layer, never in
  the marriage count.
* Both endpoints must carry a person id. A marker whose other side is a bare
  surname ("epouse Bouricha") names no second person and yields no tie; it
  survives as `person_married_name` on the role event, which is unchanged.
  Where one end resolves and the other does not, the observation goes to the
  review queue rather than being dropped.

Directionality: `person_id` is the subject the marker attaches to and
`kin_id` the other party, so `widow_of` and `maiden_name_of` read correctly in
that order. `spouse_of` is symmetric in fact but asymmetric as printed, and the
printed order is kept rather than canonicalised, so the evidence quote can
always be checked against the row. `undirected_key` is provided for analyses
that want the unordered dyad.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from datetime import date, datetime

from .paths import INTERIM, PROCESSED, ensure_dirs
from .resolve import KINSHIP
from .spells import periods

# Relations that state the tie has ended, as against those that confirm it
# standing. Only the first bounds a terminus.
ENDING = {"widow_of"}

# Marriage proper, as against the natal-surname link carried alongside it.
# Exports and counts default to this.
MARRIAGE = {"spouse_of", "widow_of"}

# A link status that names a person node. `inferred` is the name-rarity tier:
# the name is unique on the seed side and unique across the corpus, so it
# identifies without an organisation to anchor it. It is admitted here because
# a kinship marker usually sits in prose with no office attached, which is
# exactly the case dyad anchoring cannot reach -- and it stays visible as its
# own `evidence_tier` on the spell, so an analysis can drop it in one filter.
NAMED = {"resolved", "inferred"}

FIELDS_TIES = [
    "kin_obs_id", "person_id", "person_label", "kin_id", "kin_label",
    "relation", "is_marriage", "obs_kind", "obs_date", "date_precision",
    "person_mention", "kin_mention", "person_status", "kin_status",
    "marker", "undirected_key", "evidence_quote", "event_id", "block_uid",
    "issue_uid", "folio_page", "org_mention", "extract_confidence",
]
FIELDS_QUEUE = FIELDS_TIES + ["queue_reason", "failed_end", "failed_mention"]
FIELDS_SPELLS = [
    "kin_spell_id", "person_id", "person_label", "kin_id", "kin_label",
    "relation", "is_marriage", "layer", "undirected_key",
    "onset", "terminus", "onset_lo", "onset_hi", "terminus_lo", "terminus_hi",
    "last_seen",
    "left_censored", "right_censored", "onset_rule", "terminus_rule",
    "evidence_n", "evidence_tier", "confidence", "needs_review",
]
FIELDS_PANEL = [
    "panel_id", "granularity", "period_start", "period_end",
    "from_node_id", "to_node_id", "relation", "is_marriage", "layer",
    "certainty", "evidence_tier", "kin_spell_id",
]


def _d(iso: str) -> date | None:
    if not iso:
        return None
    try:
        return datetime.strptime(iso[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _iso(d: date | None) -> str:
    return d.isoformat() if d else ""


def _sid(*parts: str) -> str:
    return "KS_" + hashlib.blake2s("|".join(parts).encode(),
                                   digest_size=8).hexdigest()


def _oid(*parts: str) -> str:
    return "KO_" + hashlib.blake2s("|".join(parts).encode(),
                                   digest_size=8).hexdigest()


def _read(name: str) -> list[dict]:
    """A processed table, from its plain or gzipped form.

    The gz fallback is not cosmetic: the large tables are committed compressed
    only, and a reader without it returns an empty list and silently reports
    that nothing needs doing.
    """
    import gzip
    path = PROCESSED / name
    if path.exists():
        with path.open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))
    gz = PROCESSED / (name + ".gz")
    if gz.exists():
        with gzip.open(gz, "rt", encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))
    return []


def _write(name: str, rows: list[dict], fields: list[str]) -> None:
    path = PROCESSED / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def read_events() -> list[dict]:
    """The kinship events, from the same interim jsonl every other stage reads."""
    raw = INTERIM / "events_raw.jsonl"
    if raw.exists():
        out = []
        with raw.open(encoding="utf-8") as fh:
            for line in fh:
                e = json.loads(line)
                if e.get("event_type") in KINSHIP:
                    out.append(e)
        return out
    return [e for e in _read("events.csv") if e.get("event_type") in KINSHIP]


def load_person_index() -> dict[str, dict[str, str]]:
    """mention||org -> the resolution row, for naming an endpoint.

    Keyed exactly as `resolve` writes it, because a person mention resolves
    *per organisation anchor*: the same name in two firms' filings is two rows
    and may legitimately be two people.
    """
    out: dict[str, dict[str, str]] = {}
    for r in _read("resolution.csv"):
        out[f"{r.get('person_mention','')}||{r.get('org_mention','')}"] = r
    return out


def endpoint(mention: str, org_mention: str,
             index: dict[str, dict[str, str]]) -> tuple[str, str, str]:
    """(person_id, label, status) for one end of a kinship claim.

    Tried against this block's organisation first, then against no anchor at
    all. The second is what reaches the marker in a property or judicial
    notice, where there is no firm in the block: `resolve` still writes a row
    for the mention with an empty org, and the name-rarity tier can name it.
    """
    for key in (f"{mention}||{org_mention}", f"{mention}||"):
        r = index.get(key)
        if not r:
            continue
        if r.get("link_status") in NAMED and r.get("resolved_person_id"):
            return (r["resolved_person_id"],
                    r.get("resolved_person_label") or mention,
                    r["link_status"])
    # Report the status of the anchored row where there is one, so the queue
    # can say *why* the end failed rather than only that it did.
    r = index.get(f"{mention}||{org_mention}") or index.get(f"{mention}||")
    return "", mention, (r or {}).get("link_status", "absent")


def observations(events: list[dict],
                 index: dict[str, dict[str, str]]) -> tuple[list[dict], list[dict], dict]:
    """One row per kinship claim in print, with both ends named where possible."""
    obs: list[dict] = []
    queue: list[dict] = []
    stats = {"events": len(events), "both_ends_named": 0, "one_end_named": 0,
             "neither_end_named": 0, "self_tie_dropped": 0}
    for e in events:
        relation = e["event_type"]
        org_men = e.get("org_mention") or ""
        p_men = e.get("person_mention") or ""
        k_men = e.get("counterparty_mention") or ""
        if not p_men or not k_men:
            continue
        pid, plab, pst = endpoint(p_men, org_men, index)
        kid, klab, kst = endpoint(k_men, org_men, index)
        # Two mentions that resolve to one node are the same person written
        # twice -- which the grammar already guards against on the match key,
        # but resolution can still collapse two spellings onto one id.
        if pid and pid == kid:
            stats["self_tie_dropped"] += 1
            continue
        row = {
            "kin_obs_id": _oid(e.get("event_id", ""), relation, p_men, k_men),
            "person_id": pid, "person_label": plab,
            "kin_id": kid, "kin_label": klab,
            "relation": relation,
            "is_marriage": int(relation in MARRIAGE),
            # A marker that says the tie has ended closes it; everything else
            # only proves it was live at this date.
            "obs_kind": "closing" if relation in ENDING else "confirmation",
            "obs_date": e.get("event_date", ""),
            "date_precision": e.get("date_precision", ""),
            "person_mention": p_men, "kin_mention": k_men,
            "person_status": pst, "kin_status": kst,
            "marker": e.get("role_verbatim", ""),
            "undirected_key": "|".join(sorted([pid, kid])) if pid and kid else "",
            "evidence_quote": e.get("evidence_quote", ""),
            "event_id": e.get("event_id", ""),
            "block_uid": e.get("block_uid", ""),
            "issue_uid": e.get("issue_uid", ""),
            "folio_page": e.get("folio_page", ""),
            "org_mention": org_men,
            "extract_confidence": e.get("extract_confidence", ""),
        }
        if pid and kid:
            stats["both_ends_named"] += 1
            obs.append(row)
        elif pid or kid:
            stats["one_end_named"] += 1
            queue.append({**row, "queue_reason": "one_end_unnamed",
                          "failed_end": "kin" if pid else "person",
                          "failed_mention": k_men if pid else p_men})
        else:
            stats["neither_end_named"] += 1
            queue.append({**row, "queue_reason": "neither_end_named",
                          "failed_end": "both", "failed_mention": f"{p_men} / {k_men}"})
    return obs, queue, stats


def build_spells(obs: list[dict]) -> tuple[list[dict], dict]:
    """One spell per directed (person, kin, relation) dyad.

    Onsets are left-censored without exception: no marker in the corpus dates a
    marriage's start. A terminus exists only where a `widow_of` marker was
    seen, and is then bounded by the date it was printed -- the death happened
    at or before that filing, never after it.
    """
    by_dyad: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for o in obs:
        by_dyad[(o["person_id"], o["kin_id"], o["relation"])].append(o)

    spells: list[dict] = []
    stats = {"dyads": len(by_dyad), "dated": 0, "undated": 0, "ended": 0,
             "inferred_endpoint": 0}
    for (pid, kid, relation), rows in by_dyad.items():
        rows.sort(key=lambda r: (r["obs_date"] or "9999", r["event_id"]))
        dates = sorted(d for d in (_d(r["obs_date"]) for r in rows) if d)
        first = dates[0] if dates else None
        last = dates[-1] if dates else None
        closing = [r for r in rows if r["obs_kind"] == "closing"]
        close_d = min((d for d in (_d(r["obs_date"]) for r in closing) if d),
                      default=None)
        inferred = any(r["person_status"] == "inferred" or r["kin_status"] == "inferred"
                       for r in rows)
        if inferred:
            stats["inferred_endpoint"] += 1
        if dates:
            stats["dated"] += 1
        else:
            stats["undated"] += 1
        if close_d:
            stats["ended"] += 1
        tier = ("kinship_undated" if not dates else
                "kinship_inferred" if inferred else "kinship_dated")
        spells.append({
            "kin_spell_id": _sid(pid, kid, relation),
            "person_id": pid, "person_label": rows[0]["person_label"],
            "kin_id": kid, "kin_label": rows[0]["kin_label"],
            "relation": relation, "is_marriage": rows[0]["is_marriage"],
            "layer": "kinship",
            "undirected_key": rows[0]["undirected_key"],
            # No onset is ever observed, so the point estimate is left empty
            # and only the bound is given: the tie existed at or before the
            # first date it was printed.
            "onset": "", "onset_lo": "", "onset_hi": _iso(first),
            # The last date the tie was seen in print. Not a terminus -- the
            # marriage was not observed to end -- but the only bound an
            # analyst has for truncating a panel that otherwise runs a 1960
            # marriage through to 2026. See build_panel.
            "last_seen": _iso(last),
            "terminus": _iso(close_d), "terminus_lo": "",
            "terminus_hi": _iso(close_d),
            "left_censored": "True",
            "right_censored": "False" if close_d else "True",
            "onset_rule": "left_censored:marriage_not_dated",
            "terminus_rule": "event:widow_of" if close_d else "right_censored",
            "evidence_n": len(rows),
            "evidence_tier": tier,
            "confidence": round(min(0.95, 0.70 + 0.05 * len(rows)), 3),
            "needs_review": inferred,
        })
    return spells, stats


def build_panel(spells: list[dict]) -> list[dict]:
    """Ties active per year.

    A marriage has no observed onset, so a period counts as active from the
    first date the tie was printed -- not from the marriage, which is unknown.
    Every row is therefore `probable` at best on its lower edge, and that is
    what `certainty` says. Undated spells are excluded for the reason
    `panel_edges` gives: placing an undated tie in a time slice asserts a
    presence the evidence does not support.

    The upper edge is the honest problem here, and it is worse than in the
    ownership layer. A marriage first seen in 1960 and never seen to end runs
    through to the end of the window, which asserts in 2026 something the
    sources support only for 1960 -- and people die. Nothing in the evidence
    resolves that, so the rows are emitted (dropping them would assert the
    opposite, that the marriage ended when the printing stopped) and
    `last_seen` is carried on every spell so an analyst can truncate at the
    last sighting. `certainty` is never better than `probable` anywhere in
    this layer for the same reason.
    """
    out: list[dict] = []
    for period, p_start, p_end in periods("yearly"):
        for s in spells:
            first = _d(s["onset_hi"])
            if not first or first > p_end:
                continue
            term = _d(s["terminus"])
            if term and term < p_start:
                continue
            out.append({
                "panel_id": f"yearly:{period}", "granularity": "yearly",
                "period_start": p_start.isoformat(), "period_end": p_end.isoformat(),
                "from_node_id": s["person_id"], "to_node_id": s["kin_id"],
                "relation": s["relation"], "is_marriage": s["is_marriage"],
                "layer": s["layer"], "certainty": "probable",
                "evidence_tier": s["evidence_tier"],
                "kin_spell_id": s["kin_spell_id"],
            })
    return out


def run() -> dict:
    ensure_dirs()
    index = load_person_index()
    obs, queue, d1 = observations(read_events(), index)
    spells, d2 = build_spells(obs)
    panel = build_panel(spells)

    _write("person_ties.csv", obs, FIELDS_TIES)
    _write("person_tie_spells.csv", spells, FIELDS_SPELLS)
    _write("panel_person_ties_yearly.csv", panel, FIELDS_PANEL)
    _write("person_ties_review_queue.csv", queue, FIELDS_QUEUE)

    by_rel: dict[str, int] = defaultdict(int)
    for s in spells:
        by_rel[s["relation"]] += 1
    diag = {**d1, **d2, "panel_rows": len(panel), "review_queue": len(queue),
            "marriage_dyads": sum(v for k, v in by_rel.items() if k in MARRIAGE),
            "maiden_dyads": by_rel.get("maiden_name_of", 0),
            "persons_in_layer": len({p for s in spells
                                     for p in (s["person_id"], s["kin_id"])})}
    print("person-to-person kinship layer")
    for k in ("events", "both_ends_named", "one_end_named", "neither_end_named",
              "self_tie_dropped", "dyads", "dated", "undated", "ended",
              "inferred_endpoint", "marriage_dyads", "maiden_dyads",
              "persons_in_layer", "panel_rows", "review_queue"):
        if k in diag:
            print(f"  {k:<24} {diag[k]:>8,}")
    return diag


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(
        description="Build the person-to-person kinship layer.").parse_args(argv)
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
