"""Generate CODEBOOK.md from the data and the configuration.

The codebook is generated rather than written by hand so it cannot drift from
the tables it documents: column lists and row counts are read from the files
themselves, and controlled vocabularies from the YAML that the extractors use.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import date
from pathlib import Path

from .paths import PROCESSED, ROOT, load_config

TABLE_DOCS: dict[str, str] = {
    "seed_nodes.csv":
        "Nodes from the curated seed sheet: persons, companies, organisations, "
        "cabinets, parties, party organs and parliamentary blocs. `seed_degree` "
        "is the number of seed ties incident on the node and is the practical "
        "measure of how central a person is in the curated network.",
    "seed_edges.csv":
        "Seed ties, one row per (source, target, role, is_former). These carry "
        "**no dates**: the seed sheet is a single snapshot. `is_former` is split "
        "out of labels like FORMER MANAGER so a past tie is the same role with a "
        "known-past flag rather than a separate role.",
    "seed_reconciliation.csv":
        "Row-level accounting from the input sheet to the emitted tables, so "
        "every one of the 32,741 input rows is accounted for.",
    "issue_calendar.csv":
        "One row per mirrored gazette issue with its publication date and the "
        "evidence behind it. `date_source` records which signal decided the "
        "date; `date_confidence` is lower where signals disagreed.",
    "blocks_index.csv":
        "One row per announcement block or state act, with its printed folio "
        "page for citation. `rubric` types an announcement from the reference "
        "code's suffix; `ministry` anchors a state act to the body that issued it.",
    "events.csv":
        "The core table: one row per dated relational assertion, with up to four "
        "separate dates, a controlled event type and role, a verbatim quote and "
        "a page citation. Person and organisation names here are **surface "
        "mentions**, not resolved identities; join to `resolution.csv` for those.",
    "resolution.csv":
        "One row per (person mention, organisation mention) dyad, with the score "
        "components behind its link. Nothing is dropped: `unresolved` dyads are "
        "retained so the dataset can be re-thresholded.",
    "review_queue.csv":
        "Ambiguous dyads ordered by how consequential they are (seed degree and "
        "event count), for hand coding. These are cases the matcher declines to "
        "decide, not cases it got wrong.",
    "gazette_only_persons.csv":
        "People named in the gazette who match no seed person. The seed sheet is "
        "an elite snapshot while the gazette covers every registered company, so "
        "these are mostly non-elite — but they are also where new elite entrants "
        "would appear, which is why they are kept.",
    "spells.csv":
        "Person-organisation-role ties as intervals. `onset`/`terminus` are point "
        "estimates; the `_lo`/`_hi` columns carry what is actually known. The "
        "certain core of a spell is [onset_hi, terminus_lo].",
    "spell_observations.csv":
        "Every dated observation attached to a spell. An `obs_kind` of "
        "`confirmation` or `renewal` proves the tie existed at that moment "
        "without asserting when it began.",
    "panel_edges_yearly.csv":
        "Ties active in each calendar year, with an explicit `certainty`.",
    "panel_edges_monthly.csv":
        "As above at monthly resolution, because the January 2011 rupture is "
        "invisible at annual resolution.",
}

COLUMN_NOTES: dict[str, str] = {
    "act_date": "Date of the decision itself ('en date du'). This is when the event happened.",
    "registration_date": "Date the act was registered for tax. Administrative, not substantive.",
    "filing_date": "Date the act was filed at the court registry.",
    "effective_date": "Date the act takes effect. May legitimately precede act_date (retroactive).",
    "pub_date": "Date the gazette published the issue. An **upper bound** on the event date.",
    "event_date": "The date used for analysis, chosen by the priority in date_precision.",
    "event_date_source": "Which of the dates above supplied event_date.",
    "date_precision": "`exact` where a real act date was found; `pub_only` where the event is "
                      "interval-censored and only bounded above by publication.",
    "event_date_lo": "Lower bound on the event date. Empty means unbounded below.",
    "event_date_hi": "Upper bound on the event date.",
    "folio_page": "Printed page number, as cited in scholarship. Not the OCR page index.",
    "evidence_quote": "Verbatim text supporting the record. Validation asserts it occurs in the block.",
    "left_censored": "The tie was already running when observation began; onset unknown.",
    "right_censored": "The tie was still running when observation ended; terminus unknown.",
    "onset_interval_censored": "The start is known only to lie at or before onset_hi.",
    "terminus_interval_censored": "The end is known only to lie at or before terminus_hi.",
    "terminus_rule": "How the spell closed. `displaced_by` means another person was appointed to "
                     "the same single-holder post; `withdrawn_inconsistent` means a parsed end "
                     "preceded the start and was withdrawn rather than guessed at.",
    "evidence_tier": "`gazette_dated` for ties with gazette evidence; `seed_undated` for seed ties "
                     "carried through with no dates. Exclude the latter from survival models.",
    "certainty": "`certain` both endpoints dated; `probable` inside the certain core but an "
                 "endpoint is censored; `possible` only inside the outer envelope; `undated` a "
                 "seed tie with no time information.",
    "link_status": "`resolved` (score >= 0.70), `ambiguous` (0.45-0.70, or a rival within 0.05), "
                   "`unresolved` (< 0.45, retained as a candidate new person).",
    "s_org": "Organisation agreement. Required for a resolution: a name-only link is not an "
             "identification.",
    "s_name": "Name similarity. The surname gates the score and the given names decide it, so a "
              "shared surname alone cannot produce a match.",
    "name_ambiguity": "How many distinct seed persons share the matched person's name key.",
    "margin_to_runner_up": "Score gap to the second-best candidate. A small margin forces review "
                           "regardless of the top score.",
    "seed_degree": "Number of seed ties on the node.",
}


def _table_section(path: Path) -> list[str]:
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, [])
        n = sum(1 for _ in reader)
    out = [f"### `{path.name}`", "", f"{n:,} rows.", ""]
    doc = TABLE_DOCS.get(path.name)
    if doc:
        out += [doc, ""]
    out += ["| column | note |", "| --- | --- |"]
    for col in header:
        out.append(f"| `{col}` | {COLUMN_NOTES.get(col, '')} |")
    out.append("")
    return out


def _vocab_section() -> list[str]:
    ev = load_config("vocab_events")
    roles = load_config("vocab_roles")
    out = ["## Controlled vocabularies", "", "### `event_type`", "",
           "| value | meaning |", "| --- | --- |"]
    for k, v in ev["event_types"].items():
        out.append(f"| `{k}` | {v} |")
    out += ["", "### `role_canonical`", "", "| value | meaning |", "| --- | --- |"]
    for k, v in roles["canonical_roles"].items():
        out.append(f"| `{k}` | {v} |")
    out += ["", "Roles only one person can hold at a time, used to detect "
            "overlapping incumbency and to infer replacement: "
            + ", ".join(f"`{r}`" for r in roles["single_holder_roles"]) + ".", ""]
    out += ["### Announcement rubric codes", "",
            "The 5-character suffix of an announcement's reference code "
            "(`2010G02623`**`SANB1`**) types the notice.", "",
            "| rubric | legal form | section | domain |", "| --- | --- | --- | --- |"]
    for k, v in sorted(ev["rubrics"].items()):
        out.append(f"| `{k}` | {v.get('legal_form') or ''} | {v.get('section') or ''} "
                   f"| {v.get('domain') or ''} |")
    out.append("")
    return out


def _observed_counts() -> list[str]:
    out = ["## Observed distributions", ""]
    path = PROCESSED / "events.csv"
    if path.exists():
        with path.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        out += ["### Events by type", "", "| event_type | n |", "| --- | --- |"]
        for k, v in Counter(r["event_type"] for r in rows).most_common():
            out.append(f"| `{k}` | {v:,} |")
        out += ["", "### Events by role", "", "| role_canonical | n |", "| --- | --- |"]
        for k, v in Counter(r["role_canonical"] or "(none)" for r in rows).most_common(20):
            out.append(f"| `{k}` | {v:,} |")
        out.append("")
    return out


def build() -> Path:
    scope = load_config("scope")
    lines = [
        "# Codebook", "",
        f"Generated {date.today().isoformat()} by `python -m elitenet.codebook`. "
        "Do not edit by hand: column lists and counts are read from the data, and "
        "vocabularies from `config/`, so this file cannot drift from the dataset.",
        "",
        "## Scope", "",
        f"- Window: **{scope['window']['start']} to {scope['window']['end']}**",
        f"- Collections: {', '.join('`' + c + '`' for c in scope['collections'])}",
        f"- Language: `{scope['language']}` (the upstream mirror OCRs French only)",
        "- Source: Journal Officiel de la République Tunisienne, via the public "
        "mirror at jort.tn. The gazette is public domain.",
        "",
        "## How to read a date", "",
        "Every event can carry four different dates and they are never merged. "
        "The act date is when a decision was taken; the registration and filing "
        "dates are administrative steps; the publication date is when the gazette "
        "printed it. `event_date` selects among them by the priority "
        "effective > act > filing > registration > publication, and "
        "`event_date_source` records which one was used. Where only the "
        "publication date exists, `date_precision` is `pub_only` and the event is "
        "interval-censored: it happened at or before that date, with no lower "
        "bound asserted.",
        "",
        "## Time origin for networkDynamic", "",
        "`exports/rnd/*.csv` express time as **integer days since 2008-01-01**. "
        "Censored endpoints are `-Inf` and `Inf`, which `networkDynamic` accepts "
        "natively; the window boundary is deliberately *not* substituted for an "
        "unknown date, because 'still in post at the end of observation' is a "
        "different claim from 'left on 2012-12-31'.",
        "",
        "## Tables", "",
    ]
    for name in TABLE_DOCS:
        p = PROCESSED / name
        if p.exists():
            lines += _table_section(p)
    lines += _vocab_section()
    lines += _observed_counts()

    dest = ROOT / "docs" / "CODEBOOK-multiplex-2008-2012.md"
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description="Generate CODEBOOK.md.").parse_args(argv)
    print(f"wrote {build()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
