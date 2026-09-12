"""Gold-standard sampling and scoring.

The dataset's biggest weakness is that no precision or recall figure exists
for it, so event counts are lower bounds of unknown tightness. This module
closes that by drawing a reproducible stratified sample of blocks and emitting
a coding sheet that puts the source text, the parser's output, and the gazette
URL side by side -- so a coder can mark each extracted event right or wrong and
record anything the parser missed.

Two commands:

    python -m elitenet.gold draw    # stratified sample -> coding sheet
    python -m elitenet.gold score   # coded sheet -> precision/recall by stratum

Sampling is stratified by year x collection x rubric family and seeded, so the
same sample is drawn every time and a reviewer can verify it was not chosen
after seeing the results.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

from .paths import GOLD, INTERIM, PROCESSED, ensure_dirs

SEED = 20260912
DEFAULT_N = 400

# Only blocks the extractor is meant to act on are sampled for precision.
# Judicial and fonds-de-commerce notices are handled by the negative control
# in the validation suite instead.
RELATIONAL_DOMAINS = {"corporate", "association", "state"}

SHEET_FIELDS = [
    "coding_id", "stratum", "block_uid", "collection", "year", "issue",
    "pub_date", "rubric", "domain", "folio_page", "source_url",
    "n_events_extracted",
    # --- filled in by the coder -------------------------------------------
    "events_correct", "events_wrong", "events_missed",
    "block_relational", "coder", "notes",
]

EVENT_FIELDS = [
    "coding_id", "block_uid", "event_id", "event_type", "person_mention",
    "org_mention", "role_canonical", "event_date", "event_date_source",
    "pattern_id", "evidence_quote",
    # --- filled in by the coder -------------------------------------------
    "verdict", "correct_event_type", "correct_role", "coder_note",
]


def _stratum(block: dict) -> str:
    if block["block_type"] == "act":
        return f"{block['year']}|journal-officiel|act"
    fam = (block.get("rubric") or "UNKNOWN")[:3]
    return f"{block['year']}|annonces-legales|{fam}"


def draw(n: int = DEFAULT_N) -> dict:
    """Draw a seeded stratified sample and write the coding sheets."""
    ensure_dirs()
    GOLD.mkdir(parents=True, exist_ok=True)

    by_stratum: dict[str, list[dict]] = defaultdict(list)
    with (INTERIM / "blocks.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            b = json.loads(line)
            if b.get("domain") not in RELATIONAL_DOMAINS:
                continue
            by_stratum[_stratum(b)].append(b)

    # Proportional allocation with a floor of one per stratum, so every
    # year-by-rubric cell is represented and a failure localised to one of them
    # cannot hide in the pooled figure.
    total = sum(len(v) for v in by_stratum.values())
    alloc: dict[str, int] = {}
    for stratum, blocks in by_stratum.items():
        alloc[stratum] = max(1, round(n * len(blocks) / total))

    rng = random.Random(SEED)
    chosen: list[dict] = []
    for stratum in sorted(by_stratum):
        blocks = sorted(by_stratum[stratum], key=lambda b: b["block_uid"])
        k = min(alloc[stratum], len(blocks))
        chosen.extend(rng.sample(blocks, k))
    chosen.sort(key=lambda b: b["block_uid"])

    events_by_block: dict[str, list[dict]] = defaultdict(list)
    with (INTERIM / "events_raw.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            e = json.loads(line)
            events_by_block[e["block_uid"]].append(e)

    sheet: list[dict] = []
    ev_rows: list[dict] = []
    texts: dict[str, str] = {}
    for i, b in enumerate(chosen, 1):
        cid = f"G{i:04d}"
        url = (f"https://jort.tn/view/{b['collection']}/fr/{b['year']}/{b['issue']}")
        evs = events_by_block.get(b["block_uid"], [])
        sheet.append({
            "coding_id": cid, "stratum": _stratum(b), "block_uid": b["block_uid"],
            "collection": b["collection"], "year": b["year"], "issue": b["issue"],
            "pub_date": b["pub_date"], "rubric": b.get("rubric", ""),
            "domain": b.get("domain", ""), "folio_page": b.get("folio_page_start", ""),
            "source_url": url, "n_events_extracted": len(evs),
            "events_correct": "", "events_wrong": "", "events_missed": "",
            "block_relational": "", "coder": "", "notes": "",
        })
        for e in evs:
            ev_rows.append({
                "coding_id": cid, "block_uid": b["block_uid"],
                "event_id": e["event_id"], "event_type": e["event_type"],
                "person_mention": e.get("person_mention", ""),
                "org_mention": e.get("org_mention", ""),
                "role_canonical": e.get("role_canonical", ""),
                "event_date": e.get("event_date", ""),
                "event_date_source": e.get("event_date_source", ""),
                "pattern_id": e.get("pattern_id", ""),
                "evidence_quote": e.get("evidence_quote", ""),
                "verdict": "", "correct_event_type": "", "correct_role": "",
                "coder_note": "",
            })
        texts[cid] = b["text"]

    _write(GOLD / "sample_blocks.csv", sheet, SHEET_FIELDS)
    _write(GOLD / "sample_events.csv", ev_rows, EVENT_FIELDS)
    with (GOLD / "sample_texts.jsonl").open("w", encoding="utf-8") as fh:
        for cid, text in texts.items():
            fh.write(json.dumps({"coding_id": cid, "text": text},
                                ensure_ascii=False) + "\n")
    (GOLD / "CODING_INSTRUCTIONS.md").write_text(_instructions(), encoding="utf-8")

    return {
        "sampling_seed": SEED, "strata": len(by_stratum),
        "eligible_blocks": total, "blocks_sampled": len(chosen),
        "events_to_judge": len(ev_rows),
        "blocks_with_no_events": sum(1 for r in sheet if r["n_events_extracted"] == 0),
    }


def _instructions() -> str:
    return """# Coding instructions

Three files make up the sample:

- `sample_blocks.csv` — one row per sampled block. Judge the block as a whole.
- `sample_events.csv` — one row per event the parser extracted. Judge each one.
- `sample_texts.jsonl` — the full source text of each block, keyed by `coding_id`.

Work from `sample_texts.jsonl` (or open `source_url` and find the folio page).
The sample is drawn with a fixed seed, so it can be redrawn identically.

## Judging an extracted event (`sample_events.csv`)

Set `verdict` to one of:

| verdict | meaning |
| --- | --- |
| `correct` | the event type, person, organisation and role all match the text |
| `wrong_type` | a real event, but the wrong `event_type`. Put the right one in `correct_event_type` |
| `wrong_role` | right event, wrong role. Put the right one in `correct_role` |
| `wrong_person` | the person named is not the person the text assigns this to |
| `wrong_org` | the organisation is wrong |
| `spurious` | no such event in the text at all (a false positive) |
| `unclear` | the text is too OCR-damaged or ambiguous to judge |

More than one thing can be wrong; use the most serious (`spurious` beats
`wrong_*`). `wrong_*` verdicts count against precision for the specific field
and are reported separately, because a role error and an invented person are
not equally bad.

## Judging a block (`sample_blocks.csv`)

- `block_relational` — `yes` if the block states at least one person-to-
  organisation tie, `no` otherwise. This is the denominator for recall: a block
  with no tie in it cannot be missed.
- `events_correct` / `events_wrong` — counts, for a cross-check against the
  per-event verdicts.
- `events_missed` — **how many ties stated in the text the parser did not
  produce at all.** This is what recall is computed from, and it is the number
  that cannot be recovered any other way, so it matters most.
- `coder` — your initials. If two people code the same block, use separate
  files so agreement can be measured.

## Then

    python -m elitenet.gold score

writes `docs/GOLD-SCORE-multiplex-2008-2012.md` with precision and recall by
event type and by stratum, with intervals.
"""


# --------------------------------------------------------------------------- #
# scoring
# --------------------------------------------------------------------------- #

def _wilson(k: int, n: int) -> tuple[float, float, float]:
    """Wilson score interval: behaves sensibly at small n and near 0 or 1,
    unlike the normal approximation, which is why it is used here."""
    if n == 0:
        return (float("nan"), float("nan"), float("nan"))
    z = 1.959963985
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return p, max(0.0, centre - half), min(1.0, centre + half)


def score() -> dict:
    ev_path = GOLD / "sample_events.csv"
    bl_path = GOLD / "sample_blocks.csv"
    if not ev_path.exists():
        raise SystemExit("no sample found; run `python -m elitenet.gold draw` first")

    with ev_path.open(encoding="utf-8", newline="") as fh:
        events = list(csv.DictReader(fh))
    with bl_path.open(encoding="utf-8", newline="") as fh:
        blocks = list(csv.DictReader(fh))

    judged = [e for e in events if (e.get("verdict") or "").strip()]
    coded_blocks = [b for b in blocks if (b.get("block_relational") or "").strip()]

    lines = ["# Gold-sample score", "",
             f"Sampling seed `{SEED}`. "
             f"{len(judged)} of {len(events)} extracted events judged; "
             f"{len(coded_blocks)} of {len(blocks)} blocks coded.", ""]

    if not judged:
        lines += ["No coded verdicts yet. The sample and coding sheets are in "
                  "`gold/`; see `gold/CODING_INSTRUCTIONS.md`.", "",
                  "**Until this is coded, treat every event count in the dataset "
                  "as a lower bound of unknown tightness.**", ""]
        _emit(lines)
        return {"judged": 0, "coded_blocks": len(coded_blocks)}

    # --- precision --------------------------------------------------------
    verdicts = Counter(e["verdict"].strip() for e in judged)
    correct = verdicts.get("correct", 0)
    spurious = verdicts.get("spurious", 0)
    unclear = verdicts.get("unclear", 0)
    decidable = len(judged) - unclear
    p, lo, hi = _wilson(correct, decidable)

    lines += ["## Precision", "",
              f"**{p:.3f}** (95% CI {lo:.3f}–{hi:.3f}) on {decidable} decidable "
              f"events; {unclear} judged unclear and excluded.", "",
              "| verdict | n | share |", "| --- | --- | --- |"]
    for v, k in verdicts.most_common():
        lines.append(f"| `{v}` | {k} | {k/len(judged):.1%} |")
    lines += ["",
              f"Strictly spurious events — a tie asserted that the text does not "
              f"state — are {spurious} of {decidable} ({spurious/max(1,decidable):.1%}). "
              f"The remaining errors are events that exist but were mistyped or "
              f"misattributed, which degrade a variable rather than invent a tie.",
              ""]

    # --- precision by event type -----------------------------------------
    by_type: dict[str, list[str]] = defaultdict(list)
    for e in judged:
        if e["verdict"].strip() != "unclear":
            by_type[e["event_type"]].append(e["verdict"].strip())
    lines += ["### Precision by event type", "",
              "| event_type | n | correct | precision | 95% CI |",
              "| --- | --- | --- | --- | --- |"]
    for etype, vs in sorted(by_type.items(), key=lambda kv: -len(kv[1])):
        k = sum(1 for v in vs if v == "correct")
        pp, l, h = _wilson(k, len(vs))
        lines.append(f"| `{etype}` | {len(vs)} | {k} | {pp:.3f} | {l:.3f}–{h:.3f} |")
    lines.append("")

    # --- precision by stratum (year) -------------------------------------
    cid_year = {b["coding_id"]: b["year"] for b in blocks}
    by_year: dict[str, list[str]] = defaultdict(list)
    for e in judged:
        if e["verdict"].strip() != "unclear":
            by_year[cid_year.get(e["coding_id"], "?")].append(e["verdict"].strip())
    lines += ["### Precision by year", "",
              "| year | n | precision | 95% CI |", "| --- | --- | --- | --- |"]
    for year, vs in sorted(by_year.items()):
        k = sum(1 for v in vs if v == "correct")
        pp, l, h = _wilson(k, len(vs))
        lines.append(f"| {year} | {len(vs)} | {pp:.3f} | {l:.3f}–{h:.3f} |")
    lines.append("")

    # --- recall -----------------------------------------------------------
    rel = [b for b in coded_blocks if b["block_relational"].strip().lower() == "yes"]
    if rel:
        found = missed = 0
        for b in rel:
            try:
                found += int(b["events_correct"] or 0)
                missed += int(b["events_missed"] or 0)
            except ValueError:
                continue
        denom = found + missed
        r, rl, rh = _wilson(found, denom) if denom else (float("nan"),) * 3
        lines += ["## Recall", "",
                  f"**{r:.3f}** (95% CI {rl:.3f}–{rh:.3f}) over {denom} ties "
                  f"stated in {len(rel)} relational blocks: {found} extracted, "
                  f"{missed} missed.", ""]
        empty = [b for b in rel if b["n_events_extracted"] == "0"]
        if empty:
            lines += [f"{len(empty)} blocks state a tie but yielded no event at "
                      f"all — these are the blocks a rule layer misses entirely, "
                      f"and the place where an added pattern buys the most.", ""]
    else:
        lines += ["## Recall", "",
                  "No blocks coded for `block_relational` yet, so recall cannot "
                  "be estimated.", ""]

    lines += ["## Caveat on provenance of these figures", "",
              "Read `docs/LIMITATIONS-multiplex-2008-2012.md` for who coded this "
              "sample. A figure produced by the same agent that wrote the "
              "extractors is a self-audit: it is a real check on a rule-based "
              "parser, since the judgement is made against the printed French "
              "rather than against the code, but it is not independent. Any "
              "published figure should rest on coding by someone who did not "
              "write the rules.", ""]
    _emit(lines)
    return {"judged": len(judged), "precision": round(p, 4),
            "spurious": spurious, "coded_blocks": len(coded_blocks)}


def _emit(lines: list[str]) -> None:
    dest = Path("docs") / "GOLD-SCORE-multiplex-2008-2012.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {dest}")


def _write(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gold-sample drawing and scoring.")
    ap.add_argument("command", choices=["draw", "score"])
    ap.add_argument("-n", type=int, default=DEFAULT_N, help="target sample size")
    args = ap.parse_args(argv)
    stats = draw(args.n) if args.command == "draw" else score()
    for k, v in stats.items():
        print(f"  {k:24} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
