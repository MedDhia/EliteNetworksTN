"""Gold-standard sampling and scoring.

This build's biggest weakness is that no precision or recall figure exists for
it, so every count is a lower bound of unknown tightness. This module closes
that by drawing a reproducible stratified sample and emitting coding sheets
that put the Arabic passage, the extractor's output, and the page reference
side by side, so a coder can mark each tie right or wrong and record what was
missed.

    python -m aalam.gold draw    # stratified sample -> coding sheets
    python -m aalam.gold verify  # the committed sheets are still that sample
    python -m aalam.gold score   # coded sheets -> precision/recall

Two units, because precision and recall are not answerable from the same one.

**Precision** is judged per tie. The sheet shows a tie and the sentence it
claims, and the coder says whether the sentence supports it. Stratified by
layer x extractor, so the rule pass and the model pass are scored separately
and a weak layer cannot hide inside a strong one. All seven rule-pass ties are
included outright: at that size a sample would tell us nothing a census does
not.

**Recall** cannot be judged from the ties we found -- a tie we never extracted
is not in the table to sample. It is judged per passage instead: the coder
reads a paragraph of the book, counts the relations it actually states, and
compares that with what the extractor returned for it. Stratified by cohort,
so a generation the extractor reads badly shows up rather than averaging out.

Sampling is seeded and the corpus is sorted before drawing, so the same sample
comes out every time and a reviewer can check it was not chosen after seeing
the results. That check is `verify`, not a redraw: the sheets on disk carry
verdicts a person wrote, no input reproduces them, and `draw` writes the coder
columns back empty. `draw` therefore refuses to overwrite a coded sheet unless
forced.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

from .llm import open_text
from .paths import DOCS, GOLD, INTERIM, PROCESSED, ensure_dirs
from .textnorm_ar import arabic_only, fold

SEED = 20260913
DEFAULT_EDGES = 200
DEFAULT_PASSAGES = 60

# A paragraph shorter than this is a page-number fragment or a stray line, not
# a passage a coder can judge; it is merged into the one before it.
MIN_PASSAGE_CHARS = 200

EDGE_SHEET_FIELDS = [
    "coding_id", "stratum", "edge_id", "entry_uid", "subject_name", "relation",
    "layer", "counterparty_name", "counterparty_kind", "year", "extractor",
    "pattern_id", "folio", "evidence_quote",
    # --- filled in by the coder -------------------------------------------
    "verdict", "correct_relation", "correct_counterparty", "coder", "coder_note",
]

PASSAGE_SHEET_FIELDS = [
    "coding_id", "stratum", "entry_uid", "subject_name", "cohort",
    "folio_start", "folio_end", "n_chars", "n_edges_extracted",
    # --- filled in by the coder -------------------------------------------
    "ties_stated", "ties_found", "ties_missed", "passage_relational",
    "coder", "notes",
]


def _wilson(k: int, n: int) -> tuple[float, float, float]:
    """Point estimate and 95% interval. Wilson because it behaves sensibly at
    small n and near 0 or 1, where the normal approximation does not."""
    if n == 0:
        return (float("nan"), float("nan"), float("nan"))
    z = 1.959963985
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, centre - half), min(1.0, centre + half))


def _passages(text: str) -> list[str]:
    """Split an entry into judgeable paragraphs."""
    out: list[str] = []
    for part in text.split("\n\n"):
        part = part.strip()
        if not part:
            continue
        if out and len(arabic_only(part)) < MIN_PASSAGE_CHARS:
            out[-1] = out[-1] + "\n\n" + part
        else:
            out.append(part)
    return out


def _allocate(rng: random.Random, groups: dict[str, list], n: int,
              take_all: set[str] | None = None) -> list:
    """Proportional allocation with a floor of one per stratum.

    The floor is what stops a small stratum vanishing: a layer with thirty ties
    would otherwise round to zero and its failure mode would never be seen.
    """
    take_all = take_all or set()
    total = sum(len(v) for v in groups.values())
    chosen = []
    for key in sorted(groups):
        pool = sorted(groups[key], key=lambda r: r["_sort"])
        if key in take_all:
            chosen.extend(pool)
            continue
        want = max(1, round(n * len(pool) / total)) if total else 0
        chosen.extend(pool if want >= len(pool) else rng.sample(pool, want))
    return chosen


def _sample(n_edges: int = DEFAULT_EDGES,
            n_passages: int = DEFAULT_PASSAGES) -> tuple[list, list, list, dict]:
    """Draw the sample without writing anything.

    Split out from ``draw`` so the draw can be checked without being redone:
    the sheets on disk carry a coder's verdicts, and regenerating them to see
    whether the sample moved would destroy the work being checked.
    """
    ensure_dirs()

    with open_text(PROCESSED / "edges" / "all.csv") as fh:
        edges = list(csv.DictReader(fh))
    with (PROCESSED / "entries.csv").open(encoding="utf-8") as fh:
        entries = {r["entry_uid"]: r for r in csv.DictReader(fh)}
    texts = {}
    with (INTERIM / "entry_texts.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            texts[rec["entry_uid"]] = rec["text"]

    rng = random.Random(SEED)

    # ---- precision sheet: ties ------------------------------------------ #
    by_stratum: dict[str, list] = defaultdict(list)
    for e in edges:
        e["_sort"] = e["edge_id"]
        by_stratum[f"{e['layer']}|{e['extractor']}"].append(e)
    # The rule pass has seven ties in total. Sampling seven tells us nothing a
    # census does not, so every one is coded.
    take_all = {k for k, v in by_stratum.items() if len(v) <= 10}
    picked = _allocate(rng, by_stratum, n_edges, take_all)
    picked.sort(key=lambda r: (r["layer"], r["extractor"], r["edge_id"]))

    edge_rows = []
    for i, e in enumerate(picked, 1):
        ent = entries.get(e["entry_uid"], {})
        edge_rows.append({
            "coding_id": f"E{i:04d}",
            "stratum": f"{e['layer']}|{e['extractor']}",
            "edge_id": e["edge_id"], "entry_uid": e["entry_uid"],
            "subject_name": e["from_name"], "relation": e["relation"],
            "layer": e["layer"], "counterparty_name": e["to_name"],
            "counterparty_kind": e["to_kind"], "year": e["year"],
            "extractor": e["extractor"], "pattern_id": e["pattern_id"],
            "folio": f"{ent.get('folio_start','')}-{ent.get('folio_end','')}",
            "evidence_quote": e["evidence_quote"],
            "verdict": "", "correct_relation": "", "correct_counterparty": "",
            "coder": "", "coder_note": "",
        })

    # ---- recall sheet: passages ----------------------------------------- #
    folded_quotes = defaultdict(list)
    for e in edges:
        folded_quotes[e["entry_uid"]].append(" ".join(fold(e["evidence_quote"]).split()))

    pool: dict[str, list] = defaultdict(list)
    for uid, text in texts.items():
        ent = entries[uid]
        for j, passage in enumerate(_passages(text)):
            pool[ent["cohort"]].append({
                "_sort": f"{uid}:{j:03d}", "entry_uid": uid, "passage_no": j,
                "text": passage, "cohort": ent["cohort"],
                "subject_name": ent["name_ar"],
                "folio_start": ent["folio_start"], "folio_end": ent["folio_end"],
            })
    chosen = _allocate(rng, pool, n_passages)
    chosen.sort(key=lambda r: r["_sort"])

    passage_rows, passage_texts = [], []
    for i, p in enumerate(chosen, 1):
        folded = " ".join(fold(p["text"]).split())
        n_here = sum(1 for q in folded_quotes[p["entry_uid"]] if q and q in folded)
        cid = f"P{i:04d}"
        passage_rows.append({
            "coding_id": cid, "stratum": p["cohort"],
            "entry_uid": p["entry_uid"], "subject_name": p["subject_name"],
            "cohort": p["cohort"], "folio_start": p["folio_start"],
            "folio_end": p["folio_end"], "n_chars": len(p["text"]),
            "n_edges_extracted": n_here,
            "ties_stated": "", "ties_found": "", "ties_missed": "",
            "passage_relational": "", "coder": "", "notes": "",
        })
        passage_texts.append({"coding_id": cid, "entry_uid": p["entry_uid"],
                              "text": p["text"]})

    stats = {
        "edges_in_corpus": len(edges), "edges_sampled": len(edge_rows),
        "edge_strata": len(by_stratum), "strata_taken_whole": len(take_all),
        "passages_in_corpus": sum(len(v) for v in pool.values()),
        "passages_sampled": len(passage_rows),
        "sampling_seed": SEED,
    }
    return edge_rows, passage_rows, passage_texts, stats


def draw(n_edges: int = DEFAULT_EDGES, n_passages: int = DEFAULT_PASSAGES,
         *, force: bool = False) -> dict:
    edge_rows, passage_rows, passage_texts, stats = _sample(n_edges, n_passages)
    GOLD.mkdir(parents=True, exist_ok=True)

    # Written before the guard below, and deliberately: the instructions are
    # generated from this module alone and hold no sample data, so refreshing
    # them destroys nothing. Were they behind the guard, an edit to the coding
    # rules could not be published without a --force redraw of the sheets.
    (GOLD / "AALAM_CODING_INSTRUCTIONS.md").write_text(_instructions(), encoding="utf-8")

    # A redraw writes the coder columns back as empty strings, so running this
    # over sheets that have been coded silently deletes the coding - the one
    # thing in this repository no rebuild can reproduce. Refuse by default;
    # `--force` is for a deliberate redraw after the corpus has changed, which
    # means recoding anyway.
    coded = _coded_sheets()
    if coded and not force:
        raise SystemExit(
            "refusing to redraw: " + ", ".join(
                f"{p.name} carries {n} coded row(s)" for p, n in coded) +
            ".\nA redraw blanks the coder columns and the verdicts are not "
            "recoverable from any input.\nTo check the draw has not moved, run "
            "`python -m aalam.gold verify`, which redraws in memory.\nTo redraw "
            "deliberately and recode from scratch, pass --force.")

    _write(GOLD / "aalam_sample_edges.csv", edge_rows, EDGE_SHEET_FIELDS)
    _write(GOLD / "aalam_sample_passages.csv", passage_rows, PASSAGE_SHEET_FIELDS)
    with (GOLD / "aalam_sample_texts.jsonl").open("w", encoding="utf-8") as fh:
        for t in passage_texts:
            fh.write(json.dumps(t, ensure_ascii=False) + "\n")

    return stats


# The columns a human fills in. Everything else on a sheet is machine-written,
# so everything else is what a redraw is allowed to be compared against.
EDGE_CODER_FIELDS = ("verdict", "correct_relation", "correct_counterparty",
                     "coder", "coder_note")
PASSAGE_CODER_FIELDS = ("ties_stated", "ties_found", "ties_missed",
                        "passage_relational", "coder", "notes")

SHEETS = (
    ("aalam_sample_edges.csv", EDGE_SHEET_FIELDS, EDGE_CODER_FIELDS, "coding_id"),
    ("aalam_sample_passages.csv", PASSAGE_SHEET_FIELDS, PASSAGE_CODER_FIELDS,
     "coding_id"),
)


def _cell(v) -> str:
    """A sheet cell as text. Deliberately not ``str(v or "")``: a count of zero
    is a fact the coder was shown, and folding it to the empty string would
    report every uncoded passage as drift."""
    return "" if v is None else str(v)


def _coded_sheets() -> list[tuple[Path, int]]:
    """Which committed sheets already carry a coder's work, and how much."""
    out = []
    for name, _fields, coder_fields, _key in SHEETS:
        path = GOLD / name
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as fh:
            n = sum(1 for r in csv.DictReader(fh)
                    if any((r.get(c) or "").strip() for c in coder_fields))
        if n:
            out.append((path, n))
    return out


DRIFT_LEDGER = "aalam_coding_drift.csv"
DRIFT_FIELDS = ["sheet", "coding_id", "column", "coded_value", "current_value",
                "assessment", "note"]


def _load_drift_ledger() -> dict[tuple[str, str, str], dict]:
    """Drift between the coded sheets and the current pipeline, acknowledged.

    A coded sheet is the one artefact in this repository that no rebuild can
    reproduce, so when the extractors improve the sheets do not follow. Two
    wrong answers are available: rewrite the machine columns, which destroys
    the record of what the coder actually judged and would silently turn a
    `wrong_relation` verdict into a row that looks like it was always right;
    or drop the check, which lets the sample itself drift unnoticed.

    This is the third: each known divergence is pinned with both values, so
    the guard still fails on anything new or on any further movement of a row
    already listed, and clearing an entry means recoding that row deliberately.
    """
    path = GOLD / DRIFT_LEDGER
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        return {(r["sheet"], r["coding_id"], r["column"]): r
                for r in csv.DictReader(fh)
                if r.get("sheet") and not r["sheet"].startswith("#")}


def verify(n_edges: int = DEFAULT_EDGES, n_passages: int = DEFAULT_PASSAGES,
           *, strict: bool = False) -> dict:
    """Check the committed sheets are still the sample the seed produces.

    The point of a seeded draw is that a reviewer can tell the sample was not
    chosen after the results were seen. That only needs the draw repeated, not
    the sheets rewritten, so this compares in memory and touches nothing.

    Every machine-written column is compared, not just the row keys. A verdict
    is a judgement about a specific quote shown to the coder; if the quote or
    the extracted counts move underneath it, the verdict no longer applies to
    what is in the table, and that is drift worth failing on.
    """
    edge_rows, passage_rows, passage_texts, stats = _sample(n_edges, n_passages)
    drawn = {"aalam_sample_edges.csv": edge_rows,
             "aalam_sample_passages.csv": passage_rows}
    problems: list[str] = []
    ledger = _load_drift_ledger()
    acknowledged: list[tuple[str, str, str]] = []

    for name, fields, coder_fields, key in SHEETS:
        path = GOLD / name
        if not path.exists():
            problems.append(f"{name}: missing; run `gold draw` to create it")
            continue
        with path.open(encoding="utf-8") as fh:
            have = list(csv.DictReader(fh))
        want = drawn[name]
        compared = [f for f in fields if f not in coder_fields]

        have_keys = [r.get(key, "") for r in have]
        want_keys = [r[key] for r in want]
        if have_keys != want_keys:
            gone = sorted(set(want_keys) - set(have_keys))
            extra = sorted(set(have_keys) - set(want_keys))
            problems.append(
                f"{name}: the draw selected {len(want_keys)} row(s), the sheet "
                f"holds {len(have_keys)}"
                + (f"; not in the sheet: {gone[:5]}" if gone else "")
                + (f"; not in the draw: {extra[:5]}" if extra else ""))
            continue

        for h, w in zip(have, want):
            for f in compared:
                a, b = _cell(h.get(f)), _cell(w.get(f))
                if a == b:
                    continue
                cid = _cell(h.get(key))
                pinned = ledger.get((name, cid, f))
                # Pinned with both values, so a row that moves again is not
                # covered by the entry that described its last move.
                if (pinned and pinned["coded_value"] == a
                        and pinned["current_value"] == b):
                    acknowledged.append((name, cid, f))
                    continue
                problems.append(
                    f"{name}: row {cid} column {f} drifted\n"
                    f"    sheet:   {a[:120]!r}\n"
                    f"    current: {b[:120]!r}"
                    + (f"\n    (the ledger pins a different pair for this "
                       f"cell: {pinned['coded_value'][:60]!r} -> "
                       f"{pinned['current_value'][:60]!r}; it moved again)"
                       if pinned else
                       "\n    not in the drift ledger: either recode the row "
                       f"or pin it in gold/{DRIFT_LEDGER}"))

    texts_path = GOLD / "aalam_sample_texts.jsonl"
    if not texts_path.exists():
        problems.append("aalam_sample_texts.jsonl: missing")
    else:
        with texts_path.open(encoding="utf-8") as fh:
            have_texts = [json.loads(line) for line in fh if line.strip()]
        if have_texts != passage_texts:
            problems.append(
                "aalam_sample_texts.jsonl: the passages a coder read are not "
                f"the ones the draw produces ({len(have_texts)} committed, "
                f"{len(passage_texts)} drawn)")

    # A ledger entry whose drift has gone means the row now agrees with the
    # pipeline again. Left in place it would quietly excuse a future change to
    # the same cell, so it is a failure until it is removed.
    for keyed in sorted(set(ledger) - set(acknowledged)):
        problems.append(
            f"{keyed[0]}: row {keyed[1]} column {keyed[2]} is pinned in "
            f"gold/{DRIFT_LEDGER} but no longer drifts; delete the entry")

    if problems:
        print("  the committed gold sample no longer matches the corpus:")
        for p in problems[:20]:
            print(f"    - {p}")
        if len(problems) > 20:
            print(f"    ... and {len(problems) - 20} more")
        raise SystemExit(1)

    if acknowledged:
        rows = sorted({(s, c) for s, c, _f in acknowledged})
        print(f"  {len(acknowledged)} acknowledged drift(s) over "
              f"{len(rows)} coded row(s); see gold/{DRIFT_LEDGER}:")
        for name, cid in rows:
            cols = sorted(f for s, c, f in acknowledged
                          if (s, c) == (name, cid))
            note = ledger[(name, cid, cols[0])].get("assessment", "")
            print(f"    - {cid} ({', '.join(cols)}) {note}")
        if strict:
            print("  --strict: acknowledged drift is a failure. Recode the "
                  "rows above and clear the ledger.")
            raise SystemExit(1)

    coded = dict(_coded_sheets())
    stats["sheets_verified"] = len(SHEETS)
    stats["coded_rows_intact"] = sum(coded.values())
    stats["acknowledged_drift"] = len(acknowledged)
    return stats


def _instructions() -> str:
    return f"""# Coding instructions — A'lam Tunisiyun gold sample

Two sheets, two questions. Both are drawn with seed `{SEED}`, so redrawing
reproduces them exactly.

## 1. `aalam_sample_edges.csv` — is this tie right?

One row per extracted tie. Columns up to `evidence_quote` are filled in; you
fill the rest. Read `evidence_quote` and judge **only whether that sentence
supports the tie as recorded**. Do not use knowledge of Tunisian history: the
question is whether the book says this, not whether it is true.

Set `verdict` to one of:

| verdict | meaning |
| --- | --- |
| `correct` | the sentence states this relation, this direction, these two parties |
| `wrong_relation` | the parties are right but the relation is not what the sentence says |
| `wrong_direction` | right relation, reversed (X taught Y recorded as Y taught X) |
| `wrong_counterparty` | the sentence names a different person or body |
| `wrong_subject` | the tie is real but belongs to someone else in the sentence |
| `spurious` | the sentence does not state a relation at all |
| `unclear` | the sentence is too OCR-damaged or ambiguous to judge |

`unclear` is excluded from the denominator. Everything else counts against
precision. Record `spurious` honestly and separately — a tie asserted where
the text states none is categorically worse than a mislabelled one, because it
is the failure the verbatim-quote guard was built to make impossible.

Where you can, put the right value in `correct_relation` or
`correct_counterparty`. That turns the sample into a fix list as well as a
score.

**The reading-versus-tutelage case.** The book lists authors a man read
(«والغزالي وابن رشد، قد استأثروا بعنايته»). If a `studied_under` row rests on
such a list, mark it `wrong_relation` and put `read_work_of` in
`correct_relation`. Rows already carrying `read_work_of` were reclassified by
the pipeline; judge them on the sentence like any other.

## 2. `aalam_sample_passages.csv` — what did we miss?

One row per paragraph of the book. Read the passage (in
`aalam_sample_texts.jsonl`, keyed by `coding_id`) and count the relations it
**states** between named people or between a person and a named body.

- `passage_relational` — `yes` if the passage states at least one tie, else `no`.
- `ties_stated` — how many the passage states in total.
- `ties_found` — how many of those appear in `n_edges_extracted` for this row.
- `ties_missed` — `ties_stated` minus `ties_found`.

`n_edges_extracted` is what the pipeline returned for this passage, matched by
quote. It can disagree with your count in both directions, and both directions
are informative: more than you counted usually means duplicates or a spurious
tie, fewer means a miss.

Count a tie once even if the passage repeats it. Do not count a relation the
passage merely implies — if it needs an inference, it is not stated.

## Both sheets

Put your initials in `coder`. Leave a row blank rather than guessing; a blank
row is excluded, a guessed one corrupts the estimate.

When finished, run `python -m aalam.gold score`.

## Rows the pipeline has changed since they were coded

Your verdicts cannot be regenerated, so the extractors are allowed to improve
without the sheets being rewritten underneath them. Where a sampled row has
since moved, the divergence is recorded in `aalam_coding_drift.csv` with both
the value you were shown and the value the pipeline now produces, and the
score report lists the affected rows under "Coding currency".

Some of those entries are bookkeeping — an organisation's name gaining its
head-word — and some are open questions flagged `NEEDS RECODING`, where the
register no longer draws a distinction your note relied on. Those are worth
your attention on a second pass; start there.

`python -m aalam.gold verify` checks the sample is still the one the seed
draws. It does not rewrite the sheets, and `draw` refuses to run over coded
sheets without `--force`, so neither can cost you your work.
"""


def score() -> dict:
    ensure_dirs()
    edges_path = GOLD / "aalam_sample_edges.csv"
    passages_path = GOLD / "aalam_sample_passages.csv"
    if not edges_path.exists():
        raise SystemExit("No sample drawn. Run `python -m aalam.gold draw` first.")

    with edges_path.open(encoding="utf-8") as fh:
        edges = list(csv.DictReader(fh))
    passages = []
    if passages_path.exists():
        with passages_path.open(encoding="utf-8") as fh:
            passages = list(csv.DictReader(fh))

    judged = [e for e in edges if (e.get("verdict") or "").strip()]
    lines = [
        "# Gold-standard score — A'lam Tunisiyun", "",
        f"Generated by `python -m aalam.gold score`. Sampling seed `{SEED}`.",
        f"Sample: {len(edges)} ties drawn from the corpus, "
        f"{len(passages)} passages drawn for recall.", "",
    ]

    if not judged:
        lines += [
            "## Not yet coded", "",
            f"{len(edges)} ties and {len(passages)} passages are waiting in "
            "`gold/`. No verdict has been recorded, so **there is no precision "
            "or recall estimate for this build**.", "",
            "Until this is coded, treat every tie count in the dataset as a "
            "lower bound of unknown tightness, and do not publish a precision "
            "figure, because there is not one.", "",
            "See `gold/AALAM_CODING_INSTRUCTIONS.md`.", "",
        ]
        _emit(lines)
        return {"coded": 0, "sampled": len(edges)}

    verdicts = Counter(e["verdict"].strip() for e in judged)
    unclear = verdicts.get("unclear", 0)
    decidable = len(judged) - unclear
    correct = verdicts.get("correct", 0)
    spurious = verdicts.get("spurious", 0)
    p, lo, hi = _wilson(correct, decidable)

    lines += [
        "## Precision", "",
        f"**{p:.3f}** (95% CI {lo:.3f}–{hi:.3f}) on {decidable} decidable ties "
        f"of {len(judged)} coded; {unclear} unclear excluded.", "",
        f"Ties asserted where the text states none: **{spurious}**.", "",
        "| verdict | n | share |", "| --- | --- | --- |",
    ]
    for v, k in verdicts.most_common():
        lines.append(f"| `{v}` | {k} | {k / len(judged):.1%} |")
    lines.append("")

    # The precision figure is a judgement about rows as the coder saw them.
    # Where the pipeline has since moved a row, the figure is measuring the old
    # row, and the direction of the resulting bias is knowable, so say it here
    # rather than let the number stand unqualified.
    ledger = _load_drift_ledger()
    if ledger:
        stale = defaultdict(list)
        for (sheet, cid, col), r in ledger.items():
            if sheet == "aalam_sample_edges.csv":
                stale[cid].append((col, r))
        adopted = sorted(
            cid for cid, cols in stale.items()
            if any(c == "relation" for c, _r in cols)
            and any((e.get("correct_relation") or "").strip()
                    == dict(cols)["relation"]["current_value"]
                    for e in edges if e["coding_id"] == cid))
        lines += [
            "## Coding currency", "",
            f"{len(stale)} of the {len(edges)} sampled ties have changed in the "
            "pipeline since they were coded, so the verdict above describes the "
            "row as it then stood. Each divergence is pinned with both values "
            f"in `gold/{DRIFT_LEDGER}`; the sample itself is unchanged.", "",
        ]
        if adopted:
            lines += [
                f"**The precision figure is a lower bound.** On {len(adopted)} "
                f"row(s) ({', '.join(adopted)}) the pipeline has adopted the "
                "correction the coder wrote in `correct_relation`, so a tie "
                "that is now right is still scored as an error here. Recoding "
                "those rows can only raise precision, never lower it.", "",
            ]
        lines += ["| row | columns | assessment |", "| --- | --- | --- |"]
        for cid in sorted(stale):
            cols = ", ".join(f"`{c}`" for c, _r in sorted(stale[cid]))
            note = sorted(stale[cid])[0][1].get("assessment", "")
            lines.append(f"| `{cid}` | {cols} | {note} |")
        lines.append("")

    for label, key in (("layer", "layer"), ("extractor", "extractor")):
        groups = defaultdict(list)
        for e in judged:
            if e["verdict"].strip() != "unclear":
                groups[e[key]].append(e["verdict"].strip())
        lines += [f"### Precision by {label}", "",
                  f"| {label} | n | precision | 95% CI |", "| --- | --- | --- | --- |"]
        for g, vs in sorted(groups.items()):
            k = sum(1 for v in vs if v == "correct")
            pp, l, h = _wilson(k, len(vs))
            lines.append(f"| `{g}` | {len(vs)} | {pp:.3f} | {l:.3f}–{h:.3f} |")
        lines.append("")

    coded_p = [r for r in passages if (r.get("passage_relational") or "").strip()]
    rel = [r for r in coded_p if r["passage_relational"].strip().lower() == "yes"]
    if rel:
        def _int(v):
            try:
                return int(str(v).strip() or 0)
            except ValueError:
                return 0
        found = sum(_int(r["ties_found"]) for r in rel)
        missed = sum(_int(r["ties_missed"]) for r in rel)
        denom = found + missed
        r_, rl, rh = _wilson(found, denom) if denom else (float("nan"),) * 3
        silent = sum(1 for r in rel if _int(r["n_edges_extracted"]) == 0)
        lines += [
            "## Recall", "",
            f"**{r_:.3f}** (95% CI {rl:.3f}–{rh:.3f}) on {denom} ties stated "
            f"across {len(rel)} relational passages of {len(coded_p)} coded.", "",
            f"Passages that state a tie and yielded nothing at all: "
            f"**{silent}**. That is where an added rule or a re-read buys most.", "",
        ]
    else:
        lines += ["## Recall", "",
                  "No passage has been coded, so there is no recall estimate. "
                  "Precision alone says nothing about what the pass missed.", ""]

    coders = sorted({(e.get("coder") or "").strip() for e in judged} - {""})
    lines += [
        "## Caveat on provenance of these figures", "",
        "**This is a self-audit and must not be published as an independent "
        "estimate.** The sample was drawn by the same system that wrote the "
        "extractors, and coded by it as well"
        + (f" (coders: {', '.join(f'`{c}`' for c in coders)})." if coders else "."),
        "",
        "Separate coder identities do not make this independent. They are "
        "separate instances of the same model that produced the assertions, so "
        "the errors a coder is disposed to overlook are the errors the "
        "extractor is disposed to make. That correlation inflates precision by "
        "an unknown amount, and it inflates recall further, because the recall "
        "sheet asks a coder to enumerate the ties a passage states -- which is "
        "the extraction task over again, done by the same kind of reader.", "",
        "What the figures are good for is comparison within the sample: which "
        "layer is weaker, whether the rule pass or the model pass fails more "
        "often, which relation types go wrong. Those comparisons hold even "
        "under a shared bias, because the bias applies to both sides.", "",
        "What they are not good for is a headline number in a paper. For that, "
        "a coder who did not build this, working from "
        "`gold/AALAM_CODING_INSTRUCTIONS.md` and the printed volume, has to "
        "recode the same seeded sample -- which is why the sample is seeded.", "",
    ]
    _emit(lines)
    return {"coded": len(judged), "sampled": len(edges),
            "precision": round(p, 3), "spurious": spurious}


def _emit(lines: list[str]) -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    path = DOCS / "GOLD-SCORE-aalam-tunisiyun.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  wrote {path}")


def _write(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["draw", "verify", "score"])
    ap.add_argument("-n", "--edges", type=int, default=DEFAULT_EDGES,
                    help="target number of ties to sample for precision")
    ap.add_argument("-p", "--passages", type=int, default=DEFAULT_PASSAGES,
                    help="target number of passages to sample for recall")
    ap.add_argument("--force", action="store_true",
                    help="redraw even if the sheets are coded, discarding the "
                         "coding")
    ap.add_argument("--strict", action="store_true",
                    help="verify: treat ledgered drift as a failure too")
    args = ap.parse_args(argv)
    if args.command == "draw":
        stats = draw(args.edges, args.passages, force=args.force)
    elif args.command == "verify":
        stats = verify(args.edges, args.passages, strict=args.strict)
    else:
        stats = score()
    for k, v in stats.items():
        print(f"  {k:22} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
