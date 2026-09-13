# Coding instructions

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
