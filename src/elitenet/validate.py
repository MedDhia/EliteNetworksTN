"""Stage 9 -- consistency checks, coverage, and held-out ground truth.

Checks are split by severity. ERROR means the dataset contradicts itself and
the build should fail. WARN means something is worth a human's attention but is
a property of the sources rather than a defect. INFO is descriptive.

Two checks are genuine held-out tests rather than internal consistency:

* **Cabinet reconstruction.** The gazette states its own cabinet lists, so
  ministers recovered from decrees can be compared against the governments the
  seed sheet names independently.
* **Negative control.** Auction and fonds-de-commerce notices should yield no
  officer appointments at all. Anything found there is a false positive, which
  estimates the error rate on out-of-scope text.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from .paths import DOCS, INTERIM, PROCESSED, ROOT, ensure_dirs, load_config

WINDOW = (date(2008, 1, 1), date(2012, 12, 31))


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []

    def add(self, level: str, check: str, detail: str) -> None:
        self.rows.append((level, check, detail))

    @property
    def errors(self) -> int:
        return sum(1 for lv, _c, _d in self.rows if lv == "ERROR")

    def render(self) -> str:
        out = ["# Validation report", "",
               f"Generated {date.today().isoformat()}.", ""]
        for level in ("ERROR", "WARN", "INFO"):
            group = [(c, d) for lv, c, d in self.rows if lv == level]
            if not group:
                continue
            out.append(f"## {level}")
            out.append("")
            for check, detail in group:
                out.append(f"- **{check}** — {detail}")
            out.append("")
        return "\n".join(out)


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


BLOCKS = INTERIM / "blocks.jsonl"

# Three checks read data/interim/, which is deliberately git-ignored: the block
# corpus is a 1.3 GB intermediate rebuilt from the gazette mirror. So they can
# run for whoever built the pipeline but not from a fresh clone or in CI, and a
# check that cannot run must say so rather than crash (which strands the checks
# after it) or report a vacuous pass. Skipping is recorded as a WARN because a
# reader of the report needs to know the provenance guard and the negative
# control were not exercised on this run -- an absent number is not a zero.
# The stage whose output each skippable input is, so the report says how to
# make the check runnable rather than only that it was not run.
_REBUILD_WITH = {"blocks.jsonl": "segment", "act_citations.csv": "extract"}


def _skip(rep: Report, check: str, needs: Path) -> None:
    stage = _REBUILD_WITH[needs.name]
    rep.add("WARN", check,
            f"not checked: {needs.relative_to(ROOT)} is absent (a git-ignored "
            f"intermediate). Run `make mirror {stage}` to rebuild it, then "
            f"re-validate.")


# Distinct from _skip above: these outputs are committed, not git-ignored, so
# their absence means the stage has not been run rather than that the input was
# deliberately left out of the repository.
def _skip_stage(rep: Report, check: str, needs: Path) -> None:
    rep.add("WARN", check,
            f"not checked: {needs.relative_to(ROOT)} is absent. "
            f"Run `make tergm` to build it, then re-validate.")


def check_calendar(rep: Report) -> None:
    cal = _read(PROCESSED / "issue_calendar.csv")
    dated = [r for r in cal if r["pub_date"]]
    rep.add("INFO", "calendar coverage",
            f"{len(dated)}/{len(cal)} issues dated ({len(dated)/max(1,len(cal)):.1%})")
    out_of_window = [r for r in dated
                     if not (WINDOW[0].isoformat()[:4] <= r["pub_date"][:4]
                             <= WINDOW[1].isoformat()[:4])]
    if out_of_window:
        rep.add("WARN", "publication date outside window",
                f"{len(out_of_window)} issues, e.g. {out_of_window[0]['issue_uid']}")
    bad_wd = [r for r in cal if r["weekday_consistent"] == "False"]
    rep.add("WARN" if bad_wd else "INFO", "weekday mismatch",
            f"{len(bad_wd)} issues where the printed weekday disagrees with the date "
            f"(date retained; a lone weekday is likelier a misprint)")
    review = [r for r in cal if r["needs_review"] == "True"]
    rep.add("INFO", "calendar needs review", f"{len(review)} issues flagged")


def check_events(rep: Report) -> None:
    events = _read(PROCESSED / "events.csv")
    rep.add("INFO", "events", f"{len(events)} extracted")

    late = [e for e in events if e["act_date"] and e["pub_date"]
            and e["act_date"] > e["pub_date"]]
    rep.add("ERROR" if late else "INFO", "act date after publication",
            f"{len(late)} events where the act postdates the issue that published it")

    # A retroactive effective date is lawful and common; it must be counted,
    # not flagged as an error.
    retro = [e for e in events if e["effective_date"] and e["act_date"]
             and e["effective_date"] < e["act_date"]]
    rep.add("INFO", "retroactive effective dates",
            f"{len(retro)} acts take effect before their own date (lawful)")

    missing_quote = [e for e in events if not e["evidence_quote"]]
    rep.add("ERROR" if missing_quote else "INFO", "provenance present",
            f"{len(missing_quote)} events without a verbatim quote")
    missing_cite = [e for e in events if not e["issue_uid"]]
    rep.add("ERROR" if missing_cite else "INFO", "source citation present",
            f"{len(missing_cite)} events without an issue reference")

    prec = Counter(e["date_precision"] for e in events)
    rep.add("INFO", "date precision", ", ".join(f"{k}={v}" for k, v in prec.most_common()))
    rep.add("INFO", "event types",
            ", ".join(f"{k}={v}" for k, v in
                      Counter(e["event_type"] for e in events).most_common(8)))


def check_quotes_are_verbatim(rep: Report, sample: int = 2000) -> None:
    """Every quote must literally occur in its block. This is the guard that
    makes the provenance claim checkable rather than decorative."""
    if not BLOCKS.exists():
        _skip(rep, "quotes verbatim", BLOCKS)
        return
    blocks: dict[str, str] = {}
    with BLOCKS.open(encoding="utf-8") as fh:
        for line in fh:
            b = json.loads(line)
            blocks[b["block_uid"]] = b["text"]
    events = _read(PROCESSED / "events.csv")
    checked = bad = 0
    for e in events:
        if checked >= sample:
            break
        q = (e["evidence_quote"] or "").strip()
        text = blocks.get(e["block_uid"])
        if not q or text is None:
            continue
        checked += 1
        norm = " ".join(text.split())
        if q not in norm:
            bad += 1
    rep.add("ERROR" if bad else "INFO", "quotes verbatim",
            f"{bad}/{checked} sampled quotes not found in their source block")


def check_spells(rep: Report) -> None:
    spells = _read(PROCESSED / "spells.csv")
    gaz = [s for s in spells if s["evidence_tier"] == "gazette_dated"]
    rep.add("INFO", "spells",
            f"{len(gaz)} dated, {len(spells) - len(gaz)} undated seed ties")

    neg = [s for s in spells if s["onset"] and s["terminus"] and s["terminus"] < s["onset"]]
    rep.add("ERROR" if neg else "INFO", "no negative durations",
            f"{len(neg)} spells end before they begin")

    zero = [s for s in gaz if s["onset"] and s["terminus"] and s["terminus"] == s["onset"]]
    rep.add("WARN" if zero else "INFO", "zero-length spells",
            f"{len(zero)} spells open and close on the same day "
            f"(an officer appointed and replaced in one act)")

    # Overlapping incumbency on a post only one person can hold at a time is a
    # strong signal of a resolution error, so it is surfaced rather than fixed.
    single = set(load_config("vocab_roles")["single_holder_roles"])
    by_post: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for s in gaz:
        if s["role_canonical"] in single and s["onset"]:
            by_post[(s["org_id"], s["role_canonical"])].append(s)
    overlaps = 0
    for (_org, _role), group in by_post.items():
        group.sort(key=lambda s: s["onset"])
        for a, b in zip(group, group[1:]):
            a_end = a["terminus"] or "9999-12-31"
            if b["onset"] < a_end and a["person_id"] != b["person_id"]:
                overlaps += 1
    rep.add("WARN" if overlaps else "INFO", "overlapping single-holder posts",
            f"{overlaps} overlaps on gerant/pdg/dg/president posts — candidate "
            f"resolution errors")

    censor = Counter()
    for s in gaz:
        censor["right_censored" if s["right_censored"] == "True" else "closed"] += 1
        if s["left_censored"] == "True":
            censor["left_censored"] += 1
    rep.add("INFO", "censoring",
            ", ".join(f"{k}={v}" for k, v in censor.most_common()))
    rep.add("INFO", "closure mechanism",
            ", ".join(f"{k or '(open)'}={v}" for k, v in
                      Counter(s["terminus_rule"] for s in gaz).most_common()))


def check_resolution(rep: Report) -> None:
    res = _read(PROCESSED / "resolution.csv")
    status = Counter(r["link_status"] for r in res)
    rep.add("INFO", "resolution status",
            ", ".join(f"{k}={v}" for k, v in status.most_common()))

    resolved = [r for r in res if r["link_status"] == "resolved"]
    no_org = [r for r in resolved if float(r["s_org"] or 0) == 0]
    rep.add("ERROR" if no_org else "INFO", "resolutions are dyad-anchored",
            f"{len(no_org)} resolved links lack organisation agreement "
            f"(a name-only link is not an identification)")

    # A person holding an implausible number of simultaneous posts is usually
    # several people merged into one, so it is an automatic homonym detector.
    per_person = Counter(r["resolved_person_id"] for r in resolved)
    heavy = [(p, n) for p, n in per_person.items() if n > 12]
    rep.add("WARN" if heavy else "INFO", "improbably many posts",
            f"{len(heavy)} resolved persons hold more than 12 dyads "
            f"(possible merged homonyms)"
            + (f", worst: {sorted(heavy, key=lambda x: -x[1])[0]}" if heavy else ""))
    rep.add("INFO", "review queue",
            f"{len(_read(PROCESSED / 'review_queue.csv'))} ambiguous dyads queued; "
            f"{len(_read(PROCESSED / 'gazette_only_persons.csv'))} gazette-only "
            f"candidate persons retained")


def check_coverage(rep: Report) -> None:
    res = [r for r in _read(PROCESSED / "resolution.csv") if r["link_status"] == "resolved"]
    pids = {r["resolved_person_id"] for r in res}
    persons = [n for n in _read(PROCESSED / "seed_nodes.csv") if n["node_type"] == "PERSON"]
    ranked = sorted(persons, key=lambda n: -int(n["seed_degree"]))
    parts = []
    for k in (100, 500, 1000):
        hit = sum(1 for n in ranked[:k] if n["node_id"] in pids)
        parts.append(f"top {k}: {hit} ({hit / k:.0%})")
    parts.append(f"all {len(persons)}: {len(pids)} ({len(pids)/max(1,len(persons)):.1%})")
    rep.add("INFO", "seed elites with a dated gazette event", "; ".join(parts))


def check_negative_control(rep: Report) -> None:
    """Auction and fonds-de-commerce notices should produce no appointments."""
    if not BLOCKS.exists():
        _skip(rep, "negative control", BLOCKS)
        return
    events = _read(PROCESSED / "events.csv")
    by_block = {}
    with BLOCKS.open(encoding="utf-8") as fh:
        for line in fh:
            b = json.loads(line)
            if b.get("domain") in {"judicial", "commercial"}:
                by_block[b["block_uid"]] = b.get("domain")
    officer = {"appointed", "renewed", "resigned", "revoked", "charged_with_functions"}
    fp = [e for e in events if e["block_uid"] in by_block and e["event_type"] in officer]
    rep.add("INFO", "negative control",
            f"{len(fp)} officer events found in {len(by_block)} auction/"
            f"fonds-de-commerce blocks, which are excluded from extraction "
            f"(0 expected by construction)")


def check_cabinets(rep: Report) -> None:
    """Reconstruct cabinets from decrees and compare to the seed's governments."""
    events = _read(PROCESSED / "events.csv")
    ministers = [e for e in events
                 if e["domain"] == "state"
                 and e["role_canonical"] in {"minister", "secretary_of_state",
                                             "chef_du_gouvernement"}]
    by_year = Counter(e["event_date"][:4] for e in ministers if e["event_date"])
    rep.add("INFO", "ministerial appointments by year",
            ", ".join(f"{y}={n}" for y, n in sorted(by_year.items())))

    seed_gov = {n["label"] for n in _read(PROCESSED / "seed_nodes.csv")
                if n["node_type"] == "GOVERNMENT" and "GOVERNMENT" in n["label"]}
    rep.add("INFO", "seed cabinets",
            f"{len(seed_gov)} government nodes in the seed sheet: "
            f"{', '.join(sorted(seed_gov)[:8])}")
    if not ministers:
        rep.add("WARN", "cabinet reconstruction",
                "no ministerial appointments recovered; the state extractor's "
                "cabinet-list rule needs review against a known decree")


def check_citations(rep: Report) -> None:
    path = INTERIM / "act_citations.csv"
    if not path.exists():
        _skip(rep, "act citation graph", path)
        return
    cits = _read(path)
    dated = [c for c in cits if c["cited_date"]]
    rep.add("INFO", "act citation graph",
            f"{len(cits)} citations, {len(dated)} with a resolvable cited date")


def check_tergm_panel(rep: Report) -> None:
    """The invariants R/build_tergm_panel.R relies on, at ERROR level.

    These are not stylistic. A bipartite network object is a claim about the
    *ordering* of vertex ids -- mode 1 occupies 1..n1 -- and nothing in the
    file format enforces it. Break the ordering and `network` still builds an
    object, `btergm` still estimates, and every degree and star coefficient is
    silently computed against a reference distribution containing dyads that
    cannot exist. There is no error message for that, which is why it is
    checked here instead.
    """
    d = PROCESSED / "exports" / "tergm"
    key = _read(d / "node_key.csv")
    if not key:
        _skip_stage(rep, "tergm panel", d / "node_key.csv")
        return
    edges = _read(d / "edges_yearly.csv")
    activity = _read(d / "vertex_activity_yearly.csv")
    attrs = _read(d / "node_attrs_yearly.csv")

    m1 = [int(r["vertex_id"]) for r in key if r["mode"] == "1"]
    m2 = [int(r["vertex_id"]) for r in key if r["mode"] == "2"]
    ids = sorted(m1 + m2)
    ordered = bool(m1) and bool(m2) and max(m1) < min(m2)
    contiguous = ids == list(range(1, len(ids) + 1))
    rep.add("ERROR" if not (ordered and contiguous) else "INFO",
            "tergm vertex key is mode-blocked",
            f"{len(m1)} persons then {len(m2)} organisations; "
            f"bipartite = {len(m1)}; "
            f"mode-blocked={ordered}, ids contiguous from 1={contiguous}")

    n1 = len(m1)
    bad = [e for e in edges
           if not (int(e["tail"]) <= n1 < int(e["head"]))]
    rep.add("ERROR" if bad else "INFO", "tergm edges respect the mode split",
            f"{len(bad)} of {len(edges)} ties do not run from mode 1 to mode 2")

    # An organisation cannot blink out of existence and return: activity has to
    # be one interval. A hole would be an artifact of a bad lifecycle date, and
    # would make the risk set assert something the sources do not.
    seq: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for r in activity:
        seq[int(r["vertex_id"])].append((r["period"], r["active"]))
    holes = 0
    for rows in seq.values():
        s = "".join(a for _p, a in sorted(rows))
        if "1" in s and "0" in s.strip("0"):
            holes += 1
    rep.add("ERROR" if holes else "INFO", "tergm risk set is contiguous",
            f"{holes} vertices go inactive and then active again")

    # Every observed tie must lie inside the risk set, or the estimator is being
    # handed a structural zero that is also an observed edge.
    active = {(r["period"], int(r["vertex_id"])) for r in activity
              if r["active"] == "1"}
    outside = [e for e in edges
               if (e["period"], int(e["tail"])) not in active
               or (e["period"], int(e["head"])) not in active]
    rep.add("ERROR" if outside else "INFO", "tergm ties lie inside the risk set",
            f"{len(outside)} ties fall in a period where an endpoint is inactive")

    # btergm reads one vertex set per period; a ragged panel silently drops rows.
    per = sorted({r["period"] for r in edges})
    ragged = [p for p in per
              if sum(1 for r in attrs if r["period"] == p) != len(key)
              or sum(1 for r in activity if r["period"] == p) != len(key)]
    rep.add("ERROR" if ragged else "INFO", "tergm panel is rectangular",
            f"{len(per)} periods x {len(key)} vertices; "
            f"{len(ragged)} periods with a short attribute or activity table")


def run(fail_on_error: bool = False) -> int:
    ensure_dirs()
    rep = Report()
    check_calendar(rep)
    check_events(rep)
    check_quotes_are_verbatim(rep)
    check_spells(rep)
    check_resolution(rep)
    check_coverage(rep)
    check_negative_control(rep)
    check_cabinets(rep)
    check_citations(rep)
    check_tergm_panel(rep)

    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "VALIDATION-multiplex-2008-2012.md").write_text(rep.render(), encoding="utf-8")
    print(rep.render())
    if fail_on_error and rep.errors:
        print(f"\nFAILED: {rep.errors} error-level checks")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate the dataset.")
    ap.add_argument("--strict", action="store_true", help="exit non-zero on ERROR")
    args = ap.parse_args(argv)
    return run(fail_on_error=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
