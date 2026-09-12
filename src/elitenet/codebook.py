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
    "node_key.csv":
        "**Mode-blocked** vertex key for the TERGM panel: persons take ids "
        "1..n1 and organisations n1+1..n, which is what makes `bipartite = n1` "
        "a true statement about the ordering. `label_suspect` marks a vertex "
        "whose name is not a firm name (an address, a role fragment, a clause) "
        "and which should probably be excluded.",
    "edges_yearly.csv":
        "The yearly panel re-indexed to bipartite vertex ids and reduced to "
        "**binary** ties: two roles in one firm in one year is two panel rows "
        "and one tie, with the roles preserved pipe-joined. "
        "`dissolution_observed` marks the minority of ties actually seen to "
        "end, as opposed to right-censored.",
    "vertex_activity_yearly.csv":
        "The risk set. An organisation is active between its constitution and "
        "dissolution, widened where needed to cover a period in which it "
        "demonstrably holds a tie, so activity is always one contiguous "
        "interval. `birth_known = 0` means left-censored and at risk from the "
        "window start. Persons are active throughout: the gazette records "
        "appointments, not births.",
    "node_attrs_yearly.csv":
        "Per-period nodal covariates, rectangular by construction (every "
        "vertex appears in every period, isolates included). Use "
        "`cum_degree_lag` rather than `cum_degree` in `nodecov`: degree "
        "measured at t is a function of the ties being modelled at t.",
    "org_ties.csv":
        "Organisation-to-organisation observations, one row per resolved "
        "(holder, target, relation) assertion. Both endpoints must resolve to "
        "**distinct** seed organisations; a mention resolving to the subject "
        "firm is a self-tie and is dropped rather than counted.",
    "org_tie_spells.csv":
        "The org-org layer as intervals, in the same vocabulary as "
        "`spells.csv`. It is a **separate, one-mode, directed** layer: adding "
        "these rows to `spells.csv` would silently break every two-mode term "
        "in the TERGM panel. `evidence_tier` separates gazette-dated spells "
        "from the undated seed ties carried alongside them. Read "
        "`docs/ORG-TIES-multiplex.md` before modelling: the dominant clause "
        "confirms a standing holding rather than dating its start, so onsets "
        "here are overwhelmingly left-censored.",
    "panel_org_ties_yearly.csv":
        "The org-org layer by calendar year, the input to "
        "`R/build_org_ownership.R`.",
    "org_ties_review_queue.csv":
        "Org-org observations a human has to settle. `queue_reason` separates "
        "a dyad whose link score landed in the ambiguous band from the far "
        "larger set with **one end resolved**: there the resolved end anchors "
        "the dyad and only a single name is in question, so `failed_mention`, "
        "`near_org_label` and `near_score` carry what the coder needs.",
    "org_identifiers.csv":
        "Hard identifiers per organisation: the matricule fiscal and the "
        "registre-de-commerce number, one row per (organisation, kind, "
        "value). These are **stable** attributes -- a firm keeps them -- which "
        "is why `is_conflicting = 1` is a defect rather than a change over "
        "time: it means the node holds two values of an identifier a firm has "
        "one of. A one-character difference is OCR; a wholly different value "
        "is an organisation-resolution merge, and every tie on that node is "
        "then suspect. See `docs/ORG-IDENTIFIER-CONFLICTS-multiplex.md`.",
    "org_addresses.csv":
        "Stated seats, one row per (organisation, normalised address, kind), "
        "dated. **Time-varying**, unlike the identifiers: `obs_kind` is "
        "`moved_to` where the address is the destination named in a transfer "
        "clause and `stated` where it is the seat as printed. Aggregated on "
        "the normalised form, because casing, accents and the street "
        "abbreviation vary between two printings of one address and comparing "
        "raw strings would report a move that never happened.",
    "dyad_cov_yearly.csv":
        "Dyadic covariates as **sparse triplets** -- dense would be 2,592 x "
        "2,915 per covariate per period. Projected from the seed sheet's "
        "undated kinship and shareholding ties, which is what makes them "
        "exogenous. `kin_in_org`, `owner_of` and `prior_comembership` are "
        "lagged to t-1 and so are absent in the first period; "
        "`is_shareholder` needs no lag and is present in all of them.",
}

# Under exports/tergm/, and documented by basename above. Kept separate so the
# codebook can introduce them as a group: they are one artifact, not five.
TERGM_TABLES = [
    "exports/tergm/node_key.csv",
    "exports/tergm/edges_yearly.csv",
    "exports/tergm/vertex_activity_yearly.csv",
    "exports/tergm/node_attrs_yearly.csv",
    "exports/tergm/dyad_cov_yearly.csv",
]

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
        f"`exports/rnd/*.csv` express time as **integer days since "
        f"{scope['window']['start']}**. "
        "Censored endpoints are `-Inf` and `Inf`, which `networkDynamic` accepts "
        "natively; the window boundary is deliberately *not* substituted for an "
        "unknown date, because 'still in post at the end of observation' is a "
        f"different claim from 'left on {scope['window']['end']}'.",
        "",
        "## Tables", "",
    ]
    for name in TABLE_DOCS:
        p = PROCESSED / name
        if "/" in name or not p.exists():
            continue
        lines += _table_section(p)

    if any((PROCESSED / n).exists() for n in TERGM_TABLES):
        lines += [
            "## TERGM panel", "",
            "Written by `make tergm`. These are the yearly panel re-indexed for "
            "a temporal ERGM, not a separate measurement: the ties are the same "
            "ties. What they add is a declared bipartite split, a vertex set "
            "that does not move between periods, an explicit risk set, and "
            "covariates -- none of which an edge list can carry.",
            "",
            "**Before specifying a model, read "
            "`docs/TERGM-multiplex.md`.** 82.1% of dated spells are "
            "right-censored, so a dissolution parameter fitted to this panel "
            "estimates when the gazette prints an exit rather than when a tie "
            "ends.",
            "",
        ]
        for name in TERGM_TABLES:
            p = PROCESSED / name
            if p.exists():
                lines += _table_section(p)

    lines += _vocab_section()
    lines += _observed_counts()

    dest = ROOT / "docs" / "CODEBOOK-multiplex.md"
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description="Generate CODEBOOK.md.").parse_args(argv)
    print(f"wrote {build()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
