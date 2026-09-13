# Coding instructions — A'lam Tunisiyun gold sample

Two sheets, two questions. Both are drawn with seed `20260913`, so redrawing
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
