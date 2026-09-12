# Overrides

Human decisions that the pipeline must not overwrite. Each file is read at the
highest priority by the stage named below, so a decision made once survives
every rebuild.

## `entity_decisions.csv`

Adjudications of ambiguous identities, read by `src/elitenet/resolve.py`.

| column | meaning |
| --- | --- |
| `mention_key` | the `mention_key` from `resolution.csv` (`"<person mention>\|\|<org mention>"`) |
| `person_id` | the seed person this mention *is*. Leave empty with `decision=none` to record that it matches no seed person |
| `decision` | `link` to accept `person_id`, `none` for no seed match, `defer` to leave it queued |
| `coder` | who decided |
| `rationale` | why, in a few words — this is what makes the decision reviewable later |

A row here sets `link_status` to `manual` and pins `resolved_person_id`, ahead
of any score the matcher computes. Work from
`data/processed/multiplex/review_queue.csv`, which is ordered so the
most consequential ambiguities come first and carries the gazette URL, the
folio page, and the rival candidates needed to decide without rerunning
anything.
