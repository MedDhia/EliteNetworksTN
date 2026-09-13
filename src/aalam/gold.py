"""Gold-standard sampling and scoring.

This build's biggest weakness is that no precision or recall figure exists for
it, so every count is a lower bound of unknown tightness. This module closes
that by drawing a reproducible stratified sample and emitting coding sheets
that put the Arabic passage, the extractor's output, and the page reference
side by side, so a coder can mark each tie right or wrong and record what was
missed.

    python -m aalam.gold draw    # stratified sample -> coding sheets
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
the results.
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


def draw(n_edges: int = DEFAULT_EDGES, n_passages: int = DEFAULT_PASSAGES) -> dict:
    ensure_dirs()
    GOLD.mkdir(parents=True, exist_ok=True)

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

    _write(GOLD / "aalam_sample_edges.csv", edge_rows, EDGE_SHEET_FIELDS)
    _write(GOLD / "aalam_sample_passages.csv", passage_rows, PASSAGE_SHEET_FIELDS)
    with (GOLD / "aalam_sample_texts.jsonl").open("w", encoding="utf-8") as fh:
        for t in passage_texts:
            fh.write(json.dumps(t, ensure_ascii=False) + "\n")
    (GOLD / "AALAM_CODING_INSTRUCTIONS.md").write_text(_instructions(), encoding="utf-8")

    return {
        "edges_in_corpus": len(edges), "edges_sampled": len(edge_rows),
        "edge_strata": len(by_stratum), "strata_taken_whole": len(take_all),
        "passages_in_corpus": sum(len(v) for v in pool.values()),
        "passages_sampled": len(passage_rows),
        "sampling_seed": SEED,
    }


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

    lines += [
        "## Caveat on provenance of these figures", "",
        "This sample was drawn, and may have been coded, by the same agent that "
        "wrote the extractors. That makes it a self-audit, not an independent "
        "estimate, and it must not be published as one. An independent coder "
        "working from `gold/AALAM_CODING_INSTRUCTIONS.md` and the printed "
        "volume would produce the figure that can be.", "",
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
    ap.add_argument("command", choices=["draw", "score"])
    ap.add_argument("-n", "--edges", type=int, default=DEFAULT_EDGES,
                    help="target number of ties to sample for precision")
    ap.add_argument("-p", "--passages", type=int, default=DEFAULT_PASSAGES,
                    help="target number of passages to sample for recall")
    args = ap.parse_args(argv)
    stats = draw(args.edges, args.passages) if args.command == "draw" else score()
    for k, v in stats.items():
        print(f"  {k:22} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
