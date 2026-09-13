"""Integrity checks over the built dataset.

These checks do not "clean" anything. They report, because in this corpus an
anomaly is usually evidence about the source rather than a bug: a firm whose
declared stakes sum to 103% has a genuinely inconsistent filing, and the analyst
needs to see that rather than have it silently rescaled.

Severity levels:
  ERROR  - structurally broken; downstream code will misbehave.
  WARN   - substantively suspicious; inspect before using those rows.
  INFO   - coverage facts worth knowing when interpreting results.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

from .common import PROCESSED, log, open_text

REPORT = PROCESSED / "validation_report.md"

# Reported stakes rarely sum to exactly 100: filings round, and blockholder
# tables list only holders above a disclosure threshold. Only a sum meaningfully
# *above* 100 indicates a real inconsistency.
OVER_100_TOLERANCE = 0.5


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open_text(path) as fh:
        return list(csv.DictReader(fh))


def _f(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def run_checks() -> list[dict]:
    findings: list[dict] = []

    def add(level, check, detail, n=None):
        findings.append({"level": level, "check": check, "detail": detail, "n": n})

    entities = _read(PROCESSED / "entities.csv")
    edges = _read(PROCESSED / "multiplex_edges_observed.csv.gz")
    panel = _read(PROCESSED / "multiplex_edges_panel.csv.gz")

    if not entities or not edges:
        add("ERROR", "inputs", "entities.csv or multiplex_edges_observed.csv is missing/empty")
        return findings

    ids = {e["entity_id"] for e in entities}
    add("INFO", "size", f"{len(entities)} entities, {len(edges)} observed edges, "
                        f"{len(panel)} panel rows")

    # --- referential integrity --------------------------------------------
    dangling = {e["source_id"] for e in edges if e["source_id"] not in ids} | {
        e["target_id"] for e in edges if e["target_id"] not in ids
    }
    if dangling:
        add("ERROR", "referential_integrity",
            f"edge endpoints absent from entities.csv: {sorted(dangling)[:5]}", len(dangling))
    else:
        add("INFO", "referential_integrity", "all edge endpoints resolve to an entity")

    # --- self-loops and missing years -------------------------------------
    loops = [e for e in edges if e["source_id"] == e["target_id"]]
    if loops:
        add("ERROR", "self_loops", "edges whose source equals its target", len(loops))

    undated = [e for e in edges if not (e.get("year") or "").isdigit()]
    if undated:
        add("WARN", "undated_edges",
            "edges with no usable year; excluded from every yearly export", len(undated))

    # --- ownership plausibility -------------------------------------------
    bad_pct = [
        e for e in edges
        if e["layer"] in ("ownership", "ownership_director", "group_participation")
        and not (0 < (_f(e["weight"]) or -1) <= 100)
    ]
    if bad_pct:
        add("ERROR", "ownership_range",
            "ownership weights outside (0, 100]", len(bad_pct))

    # Sum one stake per (holder, firm, year): the same tie is reported by every
    # filing that covers the year, and adding those repeats would show spurious
    # >100% totals. Where filings disagree, the largest reported stake is used.
    per_dyad: dict[tuple[str, str, str], float] = {}
    for e in edges:
        if e["layer"] == "ownership" and (e.get("year") or "").isdigit():
            k = (e["source_id"], e["target_id"], e["year"])
            per_dyad[k] = max(per_dyad.get(k, 0.0), _f(e["weight"]) or 0.0)
    sums: dict[tuple[str, str], float] = defaultdict(float)
    for (_src, tgt, year), w in per_dyad.items():
        sums[(tgt, year)] += w
    over = {k: v for k, v in sums.items() if v > 100 + OVER_100_TOLERANCE}
    if over:
        worst = sorted(over.items(), key=lambda kv: -kv[1])[:5]
        detail = "; ".join(f"{k[0]}@{k[1]}={v:.1f}%" for k, v in worst)
        add("WARN", "ownership_sum_over_100",
            f"firm-years whose declared blockholder stakes exceed 100% ({detail})", len(over))
    add("INFO", "ownership_sum_distribution",
        f"median declared blockholder coverage: "
        f"{sorted(sums.values())[len(sums)//2]:.1f}% of capital" if sums else "no ownership edges")

    # --- duplicate ties ----------------------------------------------------
    seen = Counter(
        (e["layer"], e["year"], e["source_id"], e["target_id"], e["weight"]) for e in edges
    )
    dupes = {k: n for k, n in seen.items() if n > 1}
    if dupes:
        add("INFO", "duplicate_edges",
            "identical ties reported by more than one filing (expected; keep for provenance)",
            sum(dupes.values()) - len(dupes))

    # --- entity resolution health -----------------------------------------
    by_type = Counter(e["entity_type"] for e in entities)
    add("INFO", "entity_types", ", ".join(f"{k}={v}" for k, v in sorted(by_type.items())))

    unknown = [e for e in entities if e["entity_type"] == "unknown"]
    if unknown:
        add("WARN", "unclassified_entities",
            "entities whose type could not be determined; add them to "
            "config/entity_overrides.csv", len(unknown))

    singletons = [e for e in entities if int(e.get("n_aliases") or 1) == 1]
    add("INFO", "alias_merging",
        f"{len(entities) - len(singletons)} entities merged from >1 spelling")

    listed = [e for e in entities if e.get("is_bvmt_listed") == "1"]
    add("INFO", "bvmt_linkage",
        f"{len(listed)} entities matched to a BVMT-listed security")

    # --- movements ---------------------------------------------------------
    movements = _read(PROCESSED / "movements.csv")
    if movements:
        add("INFO", "movements", f"{len(movements)} dated operations extracted")
        untargeted = [m for m in movements if not m.get("target_id")]
        if untargeted:
            add("WARN", "movements_without_target",
                "operations whose company could not be resolved; they carry no "
                "edge and no listing event", len(untargeted))
        by_src = Counter(m.get("event_date_source") for m in movements)
        add("INFO", "movement_date_precision",
            ", ".join(f"{k}={v}" for k, v in by_src.most_common()))
        filing_dated = by_src.get("filing_date", 0)
        if filing_dated:
            add("WARN", "movements_dated_by_filing",
                "operations dated only by when the notice was filed, which is an "
                "upper bound on when they happened", filing_dated)
        # A capital increase should increase capital.
        shrank = [
            m for m in movements
            if m.get("event_type") == "augmentation_capital"
            and _f(m.get("capital_before_tnd")) and _f(m.get("capital_after_tnd"))
            and _f(m["capital_after_tnd"]) <= _f(m["capital_before_tnd"])
        ]
        if shrank:
            add("WARN", "capital_increase_not_increasing",
                "capital increases whose stated after-value does not exceed the "
                "before-value; check the notice", len(shrank))

    listings = _read(PROCESSED / "firm_listing_events.csv")
    if listings:
        add("INFO", "listing_events",
            ", ".join(f"{k}={v}" for k, v in
                      Counter(r["listing_event"] for r in listings).most_common()))

    # --- board events ------------------------------------------------------
    board = _read(PROCESSED / "board_events.csv")
    if board:
        add("INFO", "board_events",
            f"{len(board)} governance decisions from AGM resolutions")
        add("INFO", "board_event_types",
            ", ".join(f"{k}={v}" for k, v in
                      Counter(b["event_type"] for b in board).most_common()))
        unnamed = [b for b in board if not b.get("person_id")]
        if unnamed:
            add("WARN", "board_events_without_person",
                "decisions where no name could be read; they carry no edge",
                len(unnamed))
        by_filing = sum(1 for b in board if b.get("meeting_date_source") == "filing_date")
        if by_filing:
            add("WARN", "board_events_dated_by_filing",
                "decisions dated by the filing rather than by the meeting itself",
                by_filing)
        # A mandate that expires before the meeting that granted it is a
        # misread term, not a real one.
        backwards = [
            b for b in board
            if b.get("term_end_year") and b.get("meeting_year")
            and b["term_end_year"].isdigit() and b["meeting_year"].isdigit()
            and int(b["term_end_year"]) < int(b["meeting_year"])
        ]
        if backwards:
            add("WARN", "mandate_ends_before_it_starts",
                "mandates whose stated expiry precedes the meeting that granted "
                "them; check the resolution", len(backwards))
        # The resolutions corpus has a publication gap across 2012-2017. It is a
        # property of the source, and reporting it every run is what keeps an
        # empty post-2011 period from being read as board stability.
        byr = Counter(int(b["meeting_year"]) for b in board
                      if (b.get("meeting_year") or "").isdigit())
        if byr:
            span = range(min(byr), max(byr) + 1)
            missing = [y for y in span if byr.get(y, 0) == 0]
            if missing:
                runs, start = [], missing[0]
                for a, b2 in zip(missing, missing[1:] + [None]):
                    if b2 != (a + 1):
                        runs.append((start, a))
                        start = b2
                gaps = ", ".join(f"{a}" if a == b2 else f"{a}-{b2}" for a, b2 in runs)
                add("WARN", "board_event_year_gaps",
                    f"years inside the observed span with no board event at all: "
                    f"{gaps}. This is a gap in the CMF's publication, not evidence "
                    f"of board stability", len(missing))

        selfsucc = [
            b for b in board
            if b.get("replaces_id") and b.get("person_id")
            and b["replaces_id"] == b["person_id"]
        ]
        if selfsucc:
            add("ERROR", "self_succession",
                "a person recorded as replacing themselves", len(selfsucc))

    # --- temporal coverage -------------------------------------------------
    years = sorted({int(e["year"]) for e in edges if (e.get("year") or "").isdigit()})
    if years:
        add("INFO", "temporal_span", f"{years[0]}-{years[-1]} ({len(years)} distinct years)")
        thin = [y for y in years if sum(1 for e in edges if e.get("year") == str(y)) < 10]
        if thin:
            add("WARN", "thin_years",
                f"years with fewer than 10 observed edges: {thin}", len(thin))

    layer_years = defaultdict(set)
    for e in edges:
        if (e.get("year") or "").isdigit():
            layer_years[e["layer"]].add(int(e["year"]))
    for layer, ys in sorted(layer_years.items()):
        add("INFO", f"layer:{layer}",
            f"{min(ys)}-{max(ys)}, {len(ys)} years, "
            f"{sum(1 for e in edges if e['layer'] == layer)} edges")

    return findings


def write_report(findings: list[dict]) -> None:
    order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    findings = sorted(findings, key=lambda f: order.get(f["level"], 3))
    lines = [
        "# Validation report",
        "",
        "Generated by `python -m elitenet.validate`. See `docs/CODEBOOK.md` for how",
        "each check should be read.",
        "",
        "| Level | Check | Count | Detail |",
        "|---|---|---:|---|",
    ]
    for f in findings:
        n = "" if f["n"] is None else str(f["n"])
        detail = str(f["detail"]).replace("|", "\\|")
        lines.append(f"| {f['level']} | `{f['check']}` | {n} | {detail} |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info("wrote %s", REPORT.name)


def main() -> None:
    findings = run_checks()
    for f in findings:
        fn = {"ERROR": log.error, "WARN": log.warning}.get(f["level"], log.info)
        n = f" [n={f['n']}]" if f["n"] is not None else ""
        fn("%-28s %s%s", f["check"], f["detail"], n)
    write_report(findings)
    if any(f["level"] == "ERROR" for f in findings):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
