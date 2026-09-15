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


# The accuracy figures in docs/GOLD-SCORE-multiplex.md were coded on 2008-2012
# blocks and are now quoted for a dataset spanning 1957-2026. They are not
# wrong; they are out of the scope of their own evidence. Three things changed
# when the window widened, and each is a different extraction problem:
#
#  * before 2004 the corpus is almost entirely state acts -- the commercial
#    register effectively begins in 2004 -- so the clause families being
#    matched are different ones;
#  * the 1960s-80s scans are the worst OCR in the corpus, where digit
#    confusion (4 for 6) and broken diacritics are routine;
#  * after 2012 the register continues but the political vocabulary changes,
#    and five of the seed sheet's seven governments sit here.
#
# A pooled figure over all of that would hide whichever era is worst, so the
# sample is allocated across eras and precision is reported per era. The
# 2008-2012 era remains in the design so the new figures can be read against
# the published ones on the same footing.
ERAS = (
    ("1957-1979", 1957, 1979),
    ("1980-2003", 1980, 2003),
    ("2004-2007", 2004, 2007),
    ("2008-2012", 2008, 2012),
    ("2013-2026", 2013, 2026),
)


def _era(year: int) -> str:
    for name, lo, hi in ERAS:
        if lo <= year <= hi:
            return name
    return "out-of-window"


def _stratum(block: dict) -> str:
    if block["block_type"] == "act":
        return f"{block['year']}|journal-officiel|act"
    fam = (block.get("rubric") or "UNKNOWN")[:3]
    return f"{block['year']}|annonces-legales|{fam}"


def draw(n: int = DEFAULT_N, by_era: bool = False,
         out: Path | None = None) -> dict:
    """Draw a seeded stratified sample and write the coding sheets.

    `by_era` allocates across eras rather than proportionally, and `out`
    directs the sheets elsewhere so an era-targeted sample does not overwrite
    a sample that has already been coded.
    """
    ensure_dirs()
    out = out or GOLD
    out.mkdir(parents=True, exist_ok=True)

    by_stratum: dict[str, list[dict]] = defaultdict(list)
    with (INTERIM / "blocks.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            b = json.loads(line)
            if b.get("domain") not in RELATIONAL_DOMAINS:
                continue
            by_stratum[_stratum(b)].append(b)

    # Two allocations, because they answer different questions.
    #
    # Proportional allocation estimates the accuracy of the dataset as a whole:
    # every block is equally likely, so the figure describes the corpus a user
    # actually has. But the corpus is dominated by the post-2004 register, so a
    # proportional sample of 400 puts a handful of blocks in the 1960s and
    # cannot say anything about the era whose OCR is worst.
    #
    # Era allocation divides the sample equally across eras and proportionally
    # within each, which estimates accuracy *per era* at the cost of no longer
    # being a corpus-wide estimate. Neither supersedes the other; the report
    # says which one produced it.
    total = sum(len(v) for v in by_stratum.values())
    alloc: dict[str, int] = {}
    if by_era:
        eras = defaultdict(list)
        for stratum in by_stratum:
            eras[_era(int(stratum.split("|", 1)[0]))].append(stratum)
        for era, strata in eras.items():
            n_era = sum(len(by_stratum[st]) for st in strata)
            budget = n / len(eras)
            for st in strata:
                alloc[st] = max(1, round(budget * len(by_stratum[st]) / n_era))
    else:
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

    _write(out / "sample_blocks.csv", sheet, SHEET_FIELDS)
    _write(out / "sample_events.csv", ev_rows, EVENT_FIELDS)
    with (out / "sample_texts.jsonl").open("w", encoding="utf-8") as fh:
        for cid, text in texts.items():
            fh.write(json.dumps({"coding_id": cid, "text": text},
                                ensure_ascii=False) + "\n")
    (out / "CODING_INSTRUCTIONS.md").write_text(_instructions(), encoding="utf-8")

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

writes `docs/GOLD-SCORE-multiplex.md` with precision and recall by
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


def score(src: Path | None = None) -> dict:
    src = src or GOLD
    dest_name = ("GOLD-SCORE-BY-ERA-multiplex.md" if src != GOLD
                 else "GOLD-SCORE-multiplex.md")
    ev_path = src / "sample_events.csv"
    bl_path = src / "sample_blocks.csv"
    if not ev_path.exists():
        raise SystemExit("no sample found; run `python -m elitenet.gold draw` first")

    with ev_path.open(encoding="utf-8", newline="") as fh:
        events = list(csv.DictReader(fh))
    with bl_path.open(encoding="utf-8", newline="") as fh:
        blocks = list(csv.DictReader(fh))

    judged = [e for e in events if (e.get("verdict") or "").strip()]
    coded_blocks = [b for b in blocks if (b.get("block_relational") or "").strip()]

    lines = ["# Gold-sample score"
             + (" by era" if src != GOLD else ""), "",
             ("Allocated **equally across eras** and proportionally within "
              "each, which estimates accuracy per era and is deliberately "
              "**not** a corpus-wide estimate: the corpus is dominated by the "
              "post-2004 register, so a proportional sample says nothing about "
              "the decades whose OCR is worst. For the corpus-wide figure see "
              "`GOLD-SCORE-multiplex.md`."
              if src != GOLD else
              "Allocated **proportionally** over blocks, so this is a "
              "corpus-wide estimate. For accuracy broken out by era, which a "
              "pooled figure hides, see `GOLD-SCORE-BY-ERA-multiplex.md`."),
             "",
             f"Sampling seed `{SEED}`. "
             f"{len(judged)} of {len(events)} extracted events judged; "
             f"{len(coded_blocks)} of {len(blocks)} blocks coded.", ""]

    if not judged:
        lines += ["No coded verdicts yet. The sample and coding sheets are in "
                  "`gold/`; see `gold/CODING_INSTRUCTIONS.md`.", "",
                  "**Until this is coded, treat every event count in the dataset "
                  "as a lower bound of unknown tightness.**", ""]
        _emit(lines, dest_name)
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
    # --- precision by era ------------------------------------------------
    # A pooled figure over 1957-2026 hides whichever era is worst, and the
    # eras differ in kind: before 2004 the corpus is state acts rather than
    # company filings, the 1960s-80s scans carry the worst OCR, and after 2012
    # the political vocabulary changes. Reported before the by-year table
    # because with a sample of a few hundred the yearly cells are too thin to
    # read, while the era cells are not.
    by_era_v: dict[str, list[str]] = defaultdict(list)
    for e in judged:
        if e["verdict"].strip() != "unclear":
            y = cid_year.get(e["coding_id"], "")
            by_era_v[_era(int(y)) if y.isdigit() else "?"].append(
                e["verdict"].strip())
    order = [nm for nm, _l, _h in ERAS] + ["out-of-window", "?"]
    lines += ["### Precision by era", "",
              "| era | n | correct | precision | 95% CI |",
              "| --- | --- | --- | --- | --- |"]
    for era in order:
        vs = by_era_v.get(era)
        if not vs:
            continue
        k = sum(1 for v in vs if v == "correct")
        pp, l, h = _wilson(k, len(vs))
        lines.append(f"| {era} | {len(vs)} | {k} | {pp:.3f} | {l:.3f}–{h:.3f} |")
    thin = [era for era in order
            if by_era_v.get(era) and len(by_era_v[era]) < 20]
    lines.append("")
    if thin:
        lines += [f"The interval is wide for {', '.join(thin)}: fewer than 20 "
                  "decidable events were coded there, so those rows bound the "
                  "error rate loosely rather than estimating it.", ""]
    missing = [nm for nm, _l, _h in ERAS if nm not in by_era_v]
    if missing:
        lines += [f"**No coded events at all in {', '.join(missing)}.** "
                  "Accuracy in those years is unmeasured, not good.", ""]

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
              "Read `docs/LIMITATIONS-multiplex.md` for who coded this "
              "sample. A figure produced by the same agent that wrote the "
              "extractors is a self-audit: it is a real check on a rule-based "
              "parser, since the judgement is made against the printed French "
              "rather than against the code, but it is not independent. Any "
              "published figure should rest on coding by someone who did not "
              "write the rules.", ""]
    _emit(lines, dest_name)
    return {"judged": len(judged), "precision": round(p, 4),
            "spurious": spurious, "coded_blocks": len(coded_blocks)}


# The era sample gets its own report rather than overwriting the published
# one. The 2008-2012 figures were correctly measured on 2008-2012 blocks and
# stay usable there; replacing them with a wider-but-thinner estimate would
# throw away evidence rather than add to it.
def _emit(lines: list[str], dest_name: str = "GOLD-SCORE-multiplex.md") -> None:
    dest = Path("docs") / dest_name
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
    ap.add_argument("--eras", action="store_true",
                    help="allocate the sample across eras rather than "
                         "proportionally, and write to gold/era/ so an "
                         "already-coded sample is not overwritten")
    args = ap.parse_args(argv)
    out = (GOLD / "era") if args.eras else GOLD
    stats = (draw(args.n, by_era=args.eras, out=out)
             if args.command == "draw" else score(src=out))
    for k, v in stats.items():
        print(f"  {k:24} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
