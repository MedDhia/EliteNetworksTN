# Codebook

Generated 2026-09-13 by `python -m elitenet.codebook`. Do not edit by hand: column lists and counts are read from the data, and vocabularies from `config/`, so this file cannot drift from the dataset.

## Scope

- Window: **1957-01-01 to 2026-12-31**
- Collections: `journal-officiel`, `annonces-legales`
- Language: `fr` (the upstream mirror OCRs French only)
- Source: Journal Officiel de la République Tunisienne, via the public mirror at jort.tn. The gazette is public domain.

## How to read a date

Every event can carry four different dates and they are never merged. The act date is when a decision was taken; the registration and filing dates are administrative steps; the publication date is when the gazette printed it. `event_date` selects among them by the priority effective > act > filing > registration > publication, and `event_date_source` records which one was used. Where only the publication date exists, `date_precision` is `pub_only` and the event is interval-censored: it happened at or before that date, with no lower bound asserted.

## Time origin for networkDynamic

`exports/rnd/*.csv` express time as **integer days since 1957-01-01**. Censored endpoints are `-Inf` and `Inf`, which `networkDynamic` accepts natively; the window boundary is deliberately *not* substituted for an unknown date, because 'still in post at the end of observation' is a different claim from 'left on 2026-12-31'.

## Tables

### `seed_nodes.csv`

29,171 rows.

Nodes from the curated seed sheet: persons, companies, organisations, cabinets, parties, party organs and parliamentary blocs. `seed_degree` is the number of seed ties incident on the node and is the practical measure of how central a person is in the curated network.

| column | note |
| --- | --- |
| `node_id` |  |
| `label` |  |
| `node_type` |  |
| `label_normalised` |  |
| `married_or_maiden_name` |  |
| `alt_names` |  |
| `seed_degree` | Number of seed ties on the node. |
| `source` |  |

### `seed_edges.csv`

32,283 rows.

Seed ties, one row per (source, target, role, is_former). These carry **no dates**: the seed sheet is a single snapshot. `is_former` is split out of labels like FORMER MANAGER so a past tie is the same role with a known-past flag rather than a separate role.

| column | note |
| --- | --- |
| `edge_id` |  |
| `from_node_id` |  |
| `to_node_id` |  |
| `from_label` |  |
| `to_label` |  |
| `from_type` |  |
| `to_type` |  |
| `edge_label_raw` |  |
| `role_canonical` |  |
| `tie_class` |  |
| `layer` |  |
| `is_former` |  |
| `is_self_loop` |  |
| `source_line` |  |
| `evidence` |  |

### `seed_reconciliation.csv`

8 rows.

Row-level accounting from the input sheet to the emitted tables, so every one of the 32,741 input rows is accounted for.

| column | note |
| --- | --- |
| `item` |  |
| `count` |  |

### `issue_calendar.csv`

9,749 rows.

One row per mirrored gazette issue with its publication date and the evidence behind it. `date_source` records which signal decided the date; `date_confidence` is lower where signals disagreed.

| column | note |
| --- | --- |
| `issue_uid` |  |
| `collection` |  |
| `year_dir` |  |
| `issue` |  |
| `issue_no` |  |
| `issue_no_end` |  |
| `is_double_issue` |  |
| `pub_date` | Date the gazette published the issue. An **upper bound** on the event date. |
| `pub_date_lo` |  |
| `pub_date_hi` |  |
| `date_source` |  |
| `date_confidence` |  |
| `masthead_date` |  |
| `header_date` |  |
| `n_header_votes` |  |
| `header_agrees` |  |
| `weekday_stated` |  |
| `weekday_actual` |  |
| `weekday_consistent` |  |
| `annee_ordinal` |  |
| `annee_implied_year` |  |
| `annee_consistent` |  |
| `hijri_year` |  |
| `hijri_plausible` |  |
| `n_ocr_pages` |  |
| `folio_first` |  |
| `folio_last` |  |
| `script_lang` |  |
| `needs_review` |  |
| `review_note` |  |

### `blocks_index.csv`

879,131 rows.

One row per announcement block or state act, with its printed folio page for citation. `rubric` types an announcement from the reference code's suffix; `ministry` anchors a state act to the body that issued it.

| column | note |
| --- | --- |
| `block_uid` |  |
| `issue_uid` |  |
| `collection` |  |
| `year` |  |
| `issue` |  |
| `pub_date` | Date the gazette published the issue. An **upper bound** on the event date. |
| `block_type` |  |
| `ref` |  |
| `ref_series` |  |
| `ref_seq` |  |
| `rubric_raw` |  |
| `rubric` |  |
| `rubric_repaired` |  |
| `legal_form` |  |
| `section` |  |
| `domain` |  |
| `ministry` |  |
| `act_kind` |  |
| `act_number` |  |
| `heading` |  |
| `ocr_page_start` |  |
| `ocr_page_end` |  |
| `folio_page_start` |  |
| `folio_page_end` |  |
| `spans_page_break` |  |
| `n_chars` |  |
| `text_sha1` |  |
| `needs_review` |  |
| `review_note` |  |

### `events.csv`

781,233 rows.

The core table: one row per dated relational assertion, with up to four separate dates, a controlled event type and role, a verbatim quote and a page citation. Person and organisation names here are **surface mentions**, not resolved identities; join to `resolution.csv` for those.

| column | note |
| --- | --- |
| `event_id` |  |
| `event_type` |  |
| `source_type` |  |
| `block_uid` |  |
| `issue_uid` |  |
| `collection` |  |
| `year` |  |
| `issue` |  |
| `folio_page` | Printed page number, as cited in scholarship. Not the OCR page index. |
| `ocr_page` |  |
| `person_mention` |  |
| `person_married_name` | The other surname a spousal or natal marker attaches to this person. Ambiguous by itself -- see `person_ties.csv`, which separates a marriage from a birth name. |
| `person_address` | A stated residence, verbatim. NOT an identity claim: two brothers share a house. It is the discriminator the corpus otherwise lacks for telling two people of one name apart. An election of address at a lawyer's office is excluded. |
| `person_address_normalised` |  |
| `org_mention` |  |
| `org_mf` |  |
| `org_rc` |  |
| `org_address` |  |
| `org_postal_code` |  |
| `counterparty_mention` |  |
| `role_canonical` |  |
| `role_verbatim` |  |
| `portfolio` |  |
| `ministry` |  |
| `act_date` | Date of the decision itself ('en date du'). This is when the event happened. |
| `registration_date` | Date the act was registered for tax. Administrative, not substantive. |
| `filing_date` | Date the act was filed at the court registry. |
| `effective_date` | Date the act takes effect. May legitimately precede act_date (retroactive). |
| `pub_date` | Date the gazette published the issue. An **upper bound** on the event date. |
| `event_date` | The date used for analysis, chosen by the priority in date_precision. |
| `event_date_source` | Which of the dates above supplied event_date. |
| `event_date_lo` | Lower bound on the event date. Empty means unbounded below. |
| `event_date_hi` | Upper bound on the event date. |
| `date_precision` | `exact` where a real act date was found; `pub_only` where the event is interval-censored and only bounded above by publication. |
| `mandate_years` |  |
| `amount_dt` |  |
| `legal_form` |  |
| `domain` |  |
| `extractor` |  |
| `pattern_id` |  |
| `extract_confidence` |  |
| `evidence_quote` | Verbatim text supporting the record. Validation asserts it occurs in the block. |
| `alt_group` |  |
| `needs_review` |  |

### `resolution.csv`

462,177 rows.

One row per (person mention, organisation mention) dyad, with the score components behind its link. Nothing is dropped: `unresolved` dyads are retained so the dataset can be re-thresholded.

| column | note |
| --- | --- |
| `mention_key` |  |
| `person_mention` |  |
| `org_mention` |  |
| `org_mf` |  |
| `org_rc` |  |
| `org_match_score` |  |
| `org_match_basis` |  |
| `org_candidate_id` |  |
| `org_shared_tokens` |  |
| `resolved_person_id` |  |
| `resolved_person_label` |  |
| `resolved_org_id` |  |
| `resolved_org_label` |  |
| `score` |  |
| `link_status` | `resolved` (score >= 0.70, the organisation agreed), `ambiguous` (0.45-0.70, or a rival within 0.05), `inferred` (no anchor, but the name is unique on both the seed side and across the corpus), `snowball` (named by a later pass from an anchor the first pass produced -- see `resolve_pass`), `unresolved` (< 0.45, retained as a candidate new person). |
| `s_name` | Name similarity. The surname gates the score and the given names decide it, so a shared surname alone cannot produce a match. |
| `s_org` | Organisation agreement. Required for a resolution: a name-only link is not an identification. |
| `s_mf` |  |
| `s_cooccur` |  |
| `s_role` |  |
| `n_candidates` |  |
| `margin_to_runner_up` | Score gap to the second-best candidate. A small margin forces review regardless of the top score. |
| `runner_up_person_id` |  |
| `runner_up_label` |  |
| `runner_up_score` |  |
| `rival_candidates` |  |
| `n_events` |  |
| `first_event_date` |  |
| `last_event_date` |  |
| `seed_degree` | Number of seed ties on the node. |
| `name_ambiguity` | How many distinct seed persons share the matched person's name key. |
| `mention_cluster_id` |  |
| `evidence_quote` | Verbatim text supporting the record. Validation asserts it occurs in the block. |
| `role_observed` |  |
| `issue_uid` |  |
| `folio_page` | Printed page number, as cited in scholarship. Not the OCR page index. |
| `source_url` |  |
| `pdf_url` |  |
| `candidate_orgs` |  |
| `decided_by` |  |
| `resolve_pass` | Which snowball pass first named this row. 0 is the single dyad-anchored pass; filtering to `resolve_pass == 0` reproduces the pre-snowball build exactly. A snowball propagates its own errors, so this column is what makes the propagation measurable. |
| `snowball_basis` | Which rule named a snowballed row: `person_names_org` (a named person's own seed organisations were the candidate set), `org_names_person` (an organisation a previous pass named supplied the anchor), or `colleagues_name_person` (two or more named co-mentions tied to one seed organisation). |

### `review_queue.csv`

3,770 rows.

Ambiguous dyads ordered by how consequential they are (seed degree and event count), for hand coding. These are cases the matcher declines to decide, not cases it got wrong.

| column | note |
| --- | --- |
| `mention_key` |  |
| `person_mention` |  |
| `org_mention` |  |
| `org_mf` |  |
| `org_rc` |  |
| `org_match_score` |  |
| `org_match_basis` |  |
| `org_candidate_id` |  |
| `org_shared_tokens` |  |
| `resolved_person_id` |  |
| `resolved_person_label` |  |
| `resolved_org_id` |  |
| `resolved_org_label` |  |
| `score` |  |
| `link_status` | `resolved` (score >= 0.70, the organisation agreed), `ambiguous` (0.45-0.70, or a rival within 0.05), `inferred` (no anchor, but the name is unique on both the seed side and across the corpus), `snowball` (named by a later pass from an anchor the first pass produced -- see `resolve_pass`), `unresolved` (< 0.45, retained as a candidate new person). |
| `s_name` | Name similarity. The surname gates the score and the given names decide it, so a shared surname alone cannot produce a match. |
| `s_org` | Organisation agreement. Required for a resolution: a name-only link is not an identification. |
| `s_mf` |  |
| `s_cooccur` |  |
| `s_role` |  |
| `n_candidates` |  |
| `margin_to_runner_up` | Score gap to the second-best candidate. A small margin forces review regardless of the top score. |
| `runner_up_person_id` |  |
| `runner_up_label` |  |
| `runner_up_score` |  |
| `rival_candidates` |  |
| `n_events` |  |
| `first_event_date` |  |
| `last_event_date` |  |
| `seed_degree` | Number of seed ties on the node. |
| `name_ambiguity` | How many distinct seed persons share the matched person's name key. |
| `mention_cluster_id` |  |
| `evidence_quote` | Verbatim text supporting the record. Validation asserts it occurs in the block. |
| `role_observed` |  |
| `issue_uid` |  |
| `folio_page` | Printed page number, as cited in scholarship. Not the OCR page index. |
| `source_url` |  |
| `pdf_url` |  |
| `candidate_orgs` |  |
| `decided_by` |  |
| `resolve_pass` | Which snowball pass first named this row. 0 is the single dyad-anchored pass; filtering to `resolve_pass == 0` reproduces the pre-snowball build exactly. A snowball propagates its own errors, so this column is what makes the propagation measurable. |
| `snowball_basis` | Which rule named a snowballed row: `person_names_org` (a named person's own seed organisations were the candidate set), `org_names_person` (an organisation a previous pass named supplied the anchor), or `colleagues_name_person` (two or more named co-mentions tied to one seed organisation). |

### `gazette_only_persons.csv`

306,324 rows.

People named in the gazette who match no seed person. The seed sheet is an elite snapshot while the gazette covers every registered company, so these are mostly non-elite — but they are also where new elite entrants would appear, which is why they are kept.

| column | note |
| --- | --- |
| `candidate_person_id` |  |
| `label` |  |
| `n_mentions` |  |
| `n_events` |  |
| `orgs` |  |
| `first_event_date` |  |
| `last_event_date` |  |

### `spells.csv`

50,448 rows.

Person-organisation-role ties as intervals. `onset`/`terminus` are point estimates; the `_lo`/`_hi` columns carry what is actually known. The certain core of a spell is [onset_hi, terminus_lo].

| column | note |
| --- | --- |
| `spell_id` |  |
| `person_id` |  |
| `person_label` |  |
| `org_id` |  |
| `org_label` |  |
| `role_canonical` |  |
| `layer` |  |
| `tie_class` |  |
| `onset` |  |
| `terminus` |  |
| `onset_lo` |  |
| `onset_hi` |  |
| `terminus_lo` |  |
| `terminus_hi` |  |
| `left_censored` | The tie was already running when observation began; onset unknown. |
| `right_censored` | The tie was still running when observation ended; terminus unknown. |
| `onset_interval_censored` | The start is known only to lie at or before onset_hi. |
| `terminus_interval_censored` | The end is known only to lie at or before terminus_hi. |
| `onset_rule` |  |
| `terminus_rule` | How the spell closed. `displaced_by` means another person was appointed to the same single-holder post; `withdrawn_inconsistent` means a parsed end preceded the start and was withdrawn rather than guessed at. |
| `onset_event_id` |  |
| `terminus_event_id` |  |
| `expected_end_date` |  |
| `duration_days` |  |
| `duration_lo` |  |
| `duration_hi` |  |
| `evidence_n` |  |
| `evidence_tier` | `gazette_dated` for ties with gazette evidence; `seed_undated` for seed ties carried through with no dates. Exclude the latter from survival models. |
| `link_status` | `resolved` (score >= 0.70, the organisation agreed), `ambiguous` (0.45-0.70, or a rival within 0.05), `inferred` (no anchor, but the name is unique on both the seed side and across the corpus), `snowball` (named by a later pass from an anchor the first pass produced -- see `resolve_pass`), `unresolved` (< 0.45, retained as a candidate new person). |
| `confidence` |  |
| `needs_review` |  |

### `spell_observations.csv`

25,992 rows.

Every dated observation attached to a spell. An `obs_kind` of `confirmation` or `renewal` proves the tie existed at that moment without asserting when it began.

| column | note |
| --- | --- |
| `spell_id` |  |
| `obs_date` |  |
| `obs_kind` |  |
| `obs_event_id` |  |
| `evidence_quote` | Verbatim text supporting the record. Validation asserts it occurs in the block. |

### `panel_edges_yearly.csv`

139,756 rows.

Ties active in each calendar year, with an explicit `certainty`.

| column | note |
| --- | --- |
| `panel_id` |  |
| `granularity` |  |
| `period_start` |  |
| `period_end` |  |
| `from_node_id` |  |
| `to_node_id` |  |
| `role_canonical` |  |
| `layer` |  |
| `certainty` | `certain` both endpoints dated; `probable` inside the certain core but an endpoint is censored; `possible` only inside the outer envelope; `undated` a seed tie with no time information. |
| `evidence_tier` | `gazette_dated` for ties with gazette evidence; `seed_undated` for seed ties carried through with no dates. Exclude the latter from survival models. |
| `spell_id` |  |

### `panel_edges_monthly.csv`

332,179 rows.

As above at monthly resolution, because the January 2011 rupture is invisible at annual resolution.

| column | note |
| --- | --- |
| `panel_id` |  |
| `granularity` |  |
| `period_start` |  |
| `period_end` |  |
| `from_node_id` |  |
| `to_node_id` |  |
| `role_canonical` |  |
| `layer` |  |
| `certainty` | `certain` both endpoints dated; `probable` inside the certain core but an endpoint is censored; `possible` only inside the outer envelope; `undated` a seed tie with no time information. |
| `evidence_tier` | `gazette_dated` for ties with gazette evidence; `seed_undated` for seed ties carried through with no dates. Exclude the latter from survival models. |
| `spell_id` |  |

### `org_ties.csv`

3,991 rows.

Organisation-to-organisation observations, one row per resolved (holder, target, relation) assertion. Both endpoints must resolve to **distinct** seed organisations; a mention resolving to the subject firm is a self-tie and is dropped rather than counted.

| column | note |
| --- | --- |
| `org_tie_obs_id` |  |
| `holder_id` |  |
| `holder_label` |  |
| `target_id` |  |
| `target_label` |  |
| `relation` |  |
| `is_ownership` |  |
| `obs_kind` |  |
| `obs_date` |  |
| `date_precision` | `exact` where a real act date was found; `pub_only` where the event is interval-censored and only bounded above by publication. |
| `holder_mention` |  |
| `target_mention` |  |
| `holder_match` |  |
| `target_match` |  |
| `score` |  |
| `link_status` | `resolved` (score >= 0.70, the organisation agreed), `ambiguous` (0.45-0.70, or a rival within 0.05), `inferred` (no anchor, but the name is unique on both the seed side and across the corpus), `snowball` (named by a later pass from an anchor the first pass produced -- see `resolve_pass`), `unresolved` (< 0.45, retained as a candidate new person). |
| `evidence_quote` | Verbatim text supporting the record. Validation asserts it occurs in the block. |
| `event_id` |  |
| `block_uid` |  |
| `issue_uid` |  |
| `folio_page` | Printed page number, as cited in scholarship. Not the OCR page index. |
| `extract_confidence` |  |
| `holder_basis` |  |
| `target_basis` |  |
| `holder_seed_id` |  |
| `target_seed_id` |  |

### `org_tie_spells.csv`

8,087 rows.

The org-org layer as intervals, in the same vocabulary as `spells.csv`. It is a **separate, one-mode, directed** layer: adding these rows to `spells.csv` would silently break every two-mode term in the TERGM panel. `evidence_tier` separates gazette-dated spells from the undated seed ties carried alongside them. Read `docs/ORG-TIES-multiplex.md` before modelling: the dominant clause confirms a standing holding rather than dating its start, so onsets here are overwhelmingly left-censored.

| column | note |
| --- | --- |
| `org_spell_id` |  |
| `holder_id` |  |
| `holder_label` |  |
| `target_id` |  |
| `target_label` |  |
| `relation` |  |
| `is_ownership` |  |
| `layer` |  |
| `onset` |  |
| `terminus` |  |
| `onset_lo` |  |
| `onset_hi` |  |
| `terminus_lo` |  |
| `terminus_hi` |  |
| `left_censored` | The tie was already running when observation began; onset unknown. |
| `right_censored` | The tie was still running when observation ended; terminus unknown. |
| `onset_rule` |  |
| `terminus_rule` | How the spell closed. `displaced_by` means another person was appointed to the same single-holder post; `withdrawn_inconsistent` means a parsed end preceded the start and was withdrawn rather than guessed at. |
| `onset_event_id` |  |
| `terminus_event_id` |  |
| `duration_days` |  |
| `evidence_n` |  |
| `evidence_tier` | `gazette_dated` for ties with gazette evidence; `seed_undated` for seed ties carried through with no dates. Exclude the latter from survival models. |
| `link_status` | `resolved` (score >= 0.70, the organisation agreed), `ambiguous` (0.45-0.70, or a rival within 0.05), `inferred` (no anchor, but the name is unique on both the seed side and across the corpus), `snowball` (named by a later pass from an anchor the first pass produced -- see `resolve_pass`), `unresolved` (< 0.45, retained as a candidate new person). |
| `confidence` |  |
| `needs_review` |  |

### `panel_org_ties_yearly.csv`

63,900 rows.

The org-org layer by calendar year, the input to `R/build_org_ownership.R`.

| column | note |
| --- | --- |
| `panel_id` |  |
| `granularity` |  |
| `period_start` |  |
| `period_end` |  |
| `from_node_id` |  |
| `to_node_id` |  |
| `relation` |  |
| `is_ownership` |  |
| `layer` |  |
| `certainty` | `certain` both endpoints dated; `probable` inside the certain core but an endpoint is censored; `possible` only inside the outer envelope; `undated` a seed tie with no time information. |
| `evidence_tier` | `gazette_dated` for ties with gazette evidence; `seed_undated` for seed ties carried through with no dates. Exclude the latter from survival models. |
| `org_spell_id` |  |

### `person_ties.csv`

17 rows.

One row per kinship claim in print: a marriage (`spouse_of`), a widowhood (`widow_of`) or a natal surname (`maiden_name_of`), read off the `epouse` / `ep.` / `EP` / `veuve` / `nee` markers. `is_marriage` is 0 for `maiden_name_of`: "nee X" is the same woman's birth name, not a husband, and counting it as a marriage would be wrong about both the tie and its direction. Both ends carry a person id; where only one end could be named the observation is in `person_ties_review_queue.csv` rather than dropped. `org_mention` is the block the claim was read from -- the resolver's anchor -- and is NOT a claim that either party holds office in that firm.

| column | note |
| --- | --- |
| `kin_obs_id` |  |
| `person_id` |  |
| `person_label` |  |
| `kin_id` |  |
| `kin_label` |  |
| `relation` |  |
| `is_marriage` | 1 for `spouse_of` and `widow_of`, 0 for `maiden_name_of`. |
| `obs_kind` |  |
| `obs_date` |  |
| `date_precision` | `exact` where a real act date was found; `pub_only` where the event is interval-censored and only bounded above by publication. |
| `person_mention` |  |
| `kin_mention` |  |
| `person_status` |  |
| `kin_status` |  |
| `marker` |  |
| `undirected_key` |  |
| `evidence_quote` | Verbatim text supporting the record. Validation asserts it occurs in the block. |
| `event_id` |  |
| `block_uid` |  |
| `issue_uid` |  |
| `folio_page` | Printed page number, as cited in scholarship. Not the OCR page index. |
| `org_mention` |  |
| `extract_confidence` |  |

### `person_tie_spells.csv`

13 rows.

The kinship layer as intervals. A **separate, one-mode** layer over persons, for the same reason the org-org layer is separate: a person-person tie in `spells.csv` would silently break every two-mode term in the TERGM panel. Every onset is left-censored without exception -- the gazette does not publish weddings -- so `onset` is empty and `onset_hi` is the first date the tie was seen in print. Only a `widow_of` marker bounds a terminus. See `docs/INFERENCE-TIERS-multiplex.md`.

| column | note |
| --- | --- |
| `kin_spell_id` |  |
| `person_id` |  |
| `person_label` |  |
| `kin_id` |  |
| `kin_label` |  |
| `relation` |  |
| `is_marriage` | 1 for `spouse_of` and `widow_of`, 0 for `maiden_name_of`. |
| `layer` |  |
| `undirected_key` |  |
| `onset` |  |
| `terminus` |  |
| `onset_lo` |  |
| `onset_hi` |  |
| `terminus_lo` |  |
| `terminus_hi` |  |
| `last_seen` | The last date a kinship tie was seen in print. NOT a terminus -- the marriage was not observed to end -- but the only bound available for truncating a panel that otherwise runs a 1960 marriage through to the end of the window. Nothing in the sources resolves that, so the rows are emitted and the bound is carried: dropping them would assert the opposite, that the marriage ended when the printing stopped. |
| `left_censored` | The tie was already running when observation began; onset unknown. |
| `right_censored` | The tie was still running when observation ended; terminus unknown. |
| `onset_rule` |  |
| `terminus_rule` | How the spell closed. `displaced_by` means another person was appointed to the same single-holder post; `withdrawn_inconsistent` means a parsed end preceded the start and was withdrawn rather than guessed at. |
| `evidence_n` |  |
| `evidence_tier` | `gazette_dated` for ties with gazette evidence; `seed_undated` for seed ties carried through with no dates. Exclude the latter from survival models. |
| `confidence` |  |
| `needs_review` |  |

### `panel_person_ties_yearly.csv`

207 rows.

The kinship layer by calendar year. Every row is `probable` at best: a period counts as active from the first date the tie was printed, not from the marriage, which is unknown.

| column | note |
| --- | --- |
| `panel_id` |  |
| `granularity` |  |
| `period_start` |  |
| `period_end` |  |
| `from_node_id` |  |
| `to_node_id` |  |
| `relation` |  |
| `is_marriage` | 1 for `spouse_of` and `widow_of`, 0 for `maiden_name_of`. |
| `layer` |  |
| `certainty` | `certain` both endpoints dated; `probable` inside the certain core but an endpoint is censored; `possible` only inside the outer envelope; `undated` a seed tie with no time information. |
| `evidence_tier` | `gazette_dated` for ties with gazette evidence; `seed_undated` for seed ties carried through with no dates. Exclude the latter from survival models. |
| `kin_spell_id` |  |

### `person_ties_review_queue.csv`

8,750 rows.

Kinship observations retained but not tied, because one or both ends could not be named. `failed_end` and `failed_mention` say which.

| column | note |
| --- | --- |
| `kin_obs_id` |  |
| `person_id` |  |
| `person_label` |  |
| `kin_id` |  |
| `kin_label` |  |
| `relation` |  |
| `is_marriage` | 1 for `spouse_of` and `widow_of`, 0 for `maiden_name_of`. |
| `obs_kind` |  |
| `obs_date` |  |
| `date_precision` | `exact` where a real act date was found; `pub_only` where the event is interval-censored and only bounded above by publication. |
| `person_mention` |  |
| `kin_mention` |  |
| `person_status` |  |
| `kin_status` |  |
| `marker` |  |
| `undirected_key` |  |
| `evidence_quote` | Verbatim text supporting the record. Validation asserts it occurs in the block. |
| `event_id` |  |
| `block_uid` |  |
| `issue_uid` |  |
| `folio_page` | Printed page number, as cited in scholarship. Not the OCR page index. |
| `org_mention` |  |
| `extract_confidence` |  |
| `queue_reason` |  |
| `failed_end` |  |
| `failed_mention` |  |
| `person_cluster_id` |  |
| `kin_cluster_id` |  |

### `org_ties_review_queue.csv`

10,641 rows.

Org-org observations a human has to settle. `queue_reason` separates a dyad whose link score landed in the ambiguous band from the far larger set with **one end resolved**: there the resolved end anchors the dyad and only a single name is in question, so `failed_mention`, `near_org_label` and `near_score` carry what the coder needs.

| column | note |
| --- | --- |
| `org_tie_obs_id` |  |
| `holder_id` |  |
| `holder_label` |  |
| `target_id` |  |
| `target_label` |  |
| `relation` |  |
| `is_ownership` |  |
| `obs_kind` |  |
| `obs_date` |  |
| `date_precision` | `exact` where a real act date was found; `pub_only` where the event is interval-censored and only bounded above by publication. |
| `holder_mention` |  |
| `target_mention` |  |
| `holder_match` |  |
| `target_match` |  |
| `score` |  |
| `link_status` | `resolved` (score >= 0.70, the organisation agreed), `ambiguous` (0.45-0.70, or a rival within 0.05), `inferred` (no anchor, but the name is unique on both the seed side and across the corpus), `snowball` (named by a later pass from an anchor the first pass produced -- see `resolve_pass`), `unresolved` (< 0.45, retained as a candidate new person). |
| `evidence_quote` | Verbatim text supporting the record. Validation asserts it occurs in the block. |
| `event_id` |  |
| `block_uid` |  |
| `issue_uid` |  |
| `folio_page` | Printed page number, as cited in scholarship. Not the OCR page index. |
| `extract_confidence` |  |
| `holder_basis` |  |
| `target_basis` |  |
| `holder_seed_id` |  |
| `target_seed_id` |  |
| `queue_reason` |  |
| `failed_end` |  |
| `failed_mention` |  |
| `near_org_id` |  |
| `near_org_label` |  |
| `near_score` |  |
| `holder_entity_id` |  |
| `target_entity_id` |  |

### `org_entities.csv`

234,978 rows.

**The unit of analysis for an organisation.** One row per firm as this corpus can distinguish it, keyed in priority order on the normalised matricule fiscal, then the registre-de-commerce number, then the normalised mention. Identity used to be *the seed node a mention fuzzy-matched*, and `fuzz.token_set_ratio` treats containment as identity, so a seed firm whose label normalised to `TROIS` -- the French for three -- absorbed every mention containing that word and became the highest-degree organisation in the org-org layer. Keying on a hard identifier splits those hubs and simultaneously *joins* spelling variants, since one matricule often covers several. `seed_org_id` retains the seed link and `seed_match_basis` says what it rests on, so the previous view is exactly reproducible. `is_identity = 0` marks an entity that is retained but claims to identify nothing -- a mention carrying several matricules with no identifier on this event.

| column | note |
| --- | --- |
| `org_entity_id` |  |
| `entity_basis` | How an organisation entity is keyed: `matricule_fiscal`, `registre_commerce`, `address_corroborated` (two name-keyed spellings joined by a shared, discriminating seat), `name`, or `ambiguous_mention` (the mention carries several identifiers and so identifies none of them -- explicitly not an identity). |
| `entity_key` |  |
| `n_keys` |  |
| `label` |  |
| `n_mentions` |  |
| `n_events` |  |
| `first_seen` |  |
| `last_seen` | The last date a kinship tie was seen in print. NOT a terminus -- the marriage was not observed to end -- but the only bound available for truncating a panel that otherwise runs a 1960 marriage through to the end of the window. Nothing in the sources resolves that, so the rows are emitted and the bound is carried: dropping them would assert the opposite, that the marriage ended when the printing stopped. |
| `matricule` |  |
| `rc` |  |
| `seed_org_id` |  |
| `seed_org_label` |  |
| `seed_match_basis` |  |
| `seed_link_is_identity` |  |
| `is_identity` |  |
| `issue_uid` |  |

### `org_entity_members.csv`

302,716 rows.

Mention to entity, one row per distinct organisation mention, so every mention is accounted for and none is silently orphaned — the validator checks exactly that. The map is **modal** where a mention spans several entities (`n_entities_on_mention > 1`); the per-event key in `orgentity.entity_key` is authoritative.

| column | note |
| --- | --- |
| `org_mention` |  |
| `org_entity_id` |  |
| `entity_basis` | How an organisation entity is keyed: `matricule_fiscal`, `registre_commerce`, `address_corroborated` (two name-keyed spellings joined by a shared, discriminating seat), `name`, or `ambiguous_mention` (the mention carries several identifiers and so identifies none of them -- explicitly not an identity). |
| `n_events` |  |
| `mention_is_ambiguous` |  |
| `n_identifiers_on_mention` |  |
| `n_entities_on_mention` |  |
| `seed_org_id` |  |
| `seed_match_basis` |  |

### `org_identifiers.csv`

123,543 rows.

Hard identifiers per organisation: the matricule fiscal and the registre-de-commerce number, one row per (organisation, kind, value). These are **stable** attributes -- a firm keeps them -- which is why `is_conflicting = 1` is a defect rather than a change over time: it means the node holds two values of an identifier a firm has one of. A one-character difference is OCR; a wholly different value is an organisation-resolution merge, and every tie on that node is then suspect. See `docs/ORG-IDENTIFIER-CONFLICTS-multiplex.md`.

| column | note |
| --- | --- |
| `org_id` |  |
| `org_label` |  |
| `org_entity_id` |  |
| `id_type` |  |
| `value_normalised` |  |
| `value_raw` |  |
| `n_observations` |  |
| `n_issues` |  |
| `first_seen` |  |
| `last_seen` | The last date a kinship tie was seen in print. NOT a terminus -- the marriage was not observed to end -- but the only bound available for truncating a panel that otherwise runs a 1960 marriage through to the end of the window. Nothing in the sources resolves that, so the rows are emitted and the bound is carried: dropping them would assert the opposite, that the marriage ended when the printing stopped. |
| `is_conflicting` |  |
| `n_values_for_org` |  |
| `issue_uid` |  |
| `folio_page` | Printed page number, as cited in scholarship. Not the OCR page index. |
| `block_uid` |  |

### `org_addresses.csv`

229,593 rows.

Stated seats, one row per (organisation, normalised address, kind), dated. **Time-varying**, unlike the identifiers: `obs_kind` is `moved_to` where the address is the destination named in a transfer clause and `stated` where it is the seat as printed. Aggregated on the normalised form, because casing, accents and the street abbreviation vary between two printings of one address and comparing raw strings would report a move that never happened.

| column | note |
| --- | --- |
| `org_id` |  |
| `org_label` |  |
| `org_entity_id` |  |
| `address_raw` |  |
| `address_normalised` |  |
| `postal_code` |  |
| `observed_date` |  |
| `date_precision` | `exact` where a real act date was found; `pub_only` where the event is interval-censored and only bounded above by publication. |
| `obs_kind` |  |
| `n_observations` |  |
| `first_seen` |  |
| `last_seen` | The last date a kinship tie was seen in print. NOT a terminus -- the marriage was not observed to end -- but the only bound available for truncating a panel that otherwise runs a 1960 marriage through to the end of the window. Nothing in the sources resolves that, so the rows are emitted and the bound is carried: dropping them would assert the opposite, that the marriage ended when the printing stopped. |
| `issue_uid` |  |
| `folio_page` | Printed page number, as cited in scholarship. Not the OCR page index. |
| `block_uid` |  |

## TERGM panel

Written by `make tergm`. These are the yearly panel re-indexed for a temporal ERGM, not a separate measurement: the ties are the same ties. What they add is a declared bipartite split, a vertex set that does not move between periods, an explicit risk set, and covariates -- none of which an edge list can carry.

**Before specifying a model, read `docs/TERGM-multiplex.md`.** 82.1% of dated spells are right-censored, so a dissolution parameter fitted to this panel estimates when the gazette prints an exit rather than when a tie ends.

### `node_key.csv`

13,230 rows.

**Mode-blocked** vertex key for the TERGM panel: persons take ids 1..n1 and organisations n1+1..n, which is what makes `bipartite = n1` a true statement about the ordering. `label_suspect` marks a vertex whose name is not a firm name (an address, a role fragment, a clause) and which should probably be excluded.

| column | note |
| --- | --- |
| `vertex_id` |  |
| `node_id` |  |
| `label` |  |
| `mode` |  |
| `node_type` |  |
| `is_seed` |  |
| `label_suspect` |  |
| `merge_suspect` |  |
| `n_identifier_values` |  |

### `edges_yearly.csv`

127,602 rows.

The yearly panel re-indexed to bipartite vertex ids and reduced to **binary** ties: two roles in one firm in one year is two panel rows and one tie, with the roles preserved pipe-joined. `dissolution_observed` marks the minority of ties actually seen to end, as opposed to right-censored.

| column | note |
| --- | --- |
| `period` |  |
| `tail` |  |
| `head` |  |
| `role_canonical` |  |
| `certainty` | `certain` both endpoints dated; `probable` inside the certain core but an endpoint is censored; `possible` only inside the outer envelope; `undated` a seed tie with no time information. |
| `link_status` | `resolved` (score >= 0.70, the organisation agreed), `ambiguous` (0.45-0.70, or a rival within 0.05), `inferred` (no anchor, but the name is unique on both the seed side and across the corpus), `snowball` (named by a later pass from an anchor the first pass produced -- see `resolve_pass`), `unresolved` (< 0.45, retained as a candidate new person). |
| `dissolution_observed` |  |

### `vertex_activity_yearly.csv`

926,100 rows.

The risk set. An organisation is active between its constitution and dissolution, widened where needed to cover a period in which it demonstrably holds a tie, so activity is always one contiguous interval. `birth_known = 0` means left-censored and at risk from the window start. Persons are active throughout: the gazette records appointments, not births.

| column | note |
| --- | --- |
| `period` |  |
| `vertex_id` |  |
| `active` |  |
| `birth_known` |  |
| `death_known` |  |
| `risk_start` |  |
| `risk_end` |  |

### `node_attrs_yearly.csv`

926,100 rows.

Per-period nodal covariates, rectangular by construction (every vertex appears in every period, isolates included). Use `cum_degree_lag` rather than `cum_degree` in `nodecov`: degree measured at t is a function of the ties being modelled at t.

| column | note |
| --- | --- |
| `period` |  |
| `vertex_id` |  |
| `node_id` |  |
| `mode` |  |
| `node_type` |  |
| `is_seed` |  |
| `seed_degree` | Number of seed ties on the node. |
| `first_seen_year` |  |
| `tenure_years` |  |
| `cum_degree` |  |
| `cum_degree_lag` |  |
| `kin_degree` |  |
| `pedagogic_degree` |  |

### `dyad_cov_yearly.csv`

302,176 rows.

Dyadic covariates as **sparse triplets** -- dense would be 2,592 x 2,915 per covariate per period. Projected from the seed sheet's undated kinship and shareholding ties, which is what makes them exogenous. `kin_in_org`, `owner_of` and `prior_comembership` are lagged to t-1 and so are absent in the first period; `is_shareholder` needs no lag and is present in all of them.

| column | note |
| --- | --- |
| `period` |  |
| `tail` |  |
| `head` |  |
| `kin_in_org` |  |
| `owner_of` |  |
| `owner_of_seed` |  |
| `prior_comembership` |  |
| `is_shareholder` |  |

## Controlled vocabularies

### `event_type`

| value | meaning |
| --- | --- |
| `appointed` | Person takes up a role (nomination, election, designation, est charge des fonctions) |
| `renewed` | Existing mandate renewed or extended (renouvellement du mandat) |
| `resigned` | Person leaves by own act (demission) |
| `revoked` | Person removed by decision of another (revocation, il est mis fin aux fonctions) |
| `terminated` | Functions cease without attribution of agency (cessation de fonctions) |
| `constituted` | Organisation created; founding officers named |
| `shares_transferred` | Ownership moved between parties (cession/transfert de parts ou actions) |
| `capital_increased` | Registered capital raised (augmentation de capital) |
| `capital_decreased` | Registered capital reduced (reduction de capital) |
| `dissolved` | Organisation dissolved |
| `liquidated` | Organisation in or completing liquidation |
| `renamed` | Legal name changed (changement de denomination) |
| `registered` | Association, party or union legally registered |
| `represented_by` | A legal person acts through a named natural person (representee par) |
| `charged_with_functions` | Assigned to act in a post (est charge des fonctions de) -- legally an assignment, not titular appointment |
| `delegated_to_body` | Named to a commission or council as the delegate of a ministry or organisation (representant du ministere de X) |
| `retired` | Admitted to retirement (admis a la retraite) |
| `headquarters_moved` | Registered seat transferred (transfert du siege social) |

### `role_canonical`

| value | meaning |
| --- | --- |
| `gerant` | Manager of a SARL/SUARL (gerant) |
| `cogerant` | Co-manager |
| `pdg` | President-directeur general (combined chair+CEO) |
| `president_ca` | President du conseil d'administration (chair, non-executive) |
| `dg` | Directeur general (CEO) |
| `dga` | Directeur general adjoint (deputy CEO) |
| `administrateur` | Board member (administrateur) |
| `administrateur_delegue` | Managing director on the board |
| `commissaire_aux_comptes` | Statutory auditor |
| `liquidateur` | Liquidator |
| `fondateur` | Founder named in a constitution act |
| `associe` | Partner/shareholder of a SARL |
| `actionnaire` | Shareholder of a SA |
| `representant` | Natural person representing a legal person |
| `chef_du_gouvernement` | Head of government / Premier ministre |
| `minister` | Minister |
| `secretary_of_state` | Secretaire d'Etat |
| `gouverneur` | Regional governor |
| `director_general` | Directeur general of a ministry or public body |
| `director` | Director (generic, seed sheet DIRECTOR) |
| `sous_directeur` | Sous-directeur |
| `chef_de_service` | Chef de service |
| `secretaire_general` | Secretaire general |
| `chef_de_cabinet` | Chef de cabinet |
| `conseiller` | Conseiller |
| `president_public_body` | President of a public establishment or authority |
| `ceo` | Chief executive as labelled CEO in the seed sheet (kept distinct from dg) |
| `chairman` | Chairman as labelled in the seed sheet |
| `country_manager` | Country manager |
| `premier_responsable` | Premier responsable (senior-most official, seed sheet label) |
| `commandant` | Commandant |
| `accountant` | Accountant |
| `owner` | Owner |
| `shareholder` | Holder of equity, share size unknown |
| `funder` | Provider of funding |
| `member` | Member of a collegial body, party organ or bloc |
| `president` | President of a body (seed sheet PRESIDENT) |
| `branch_of` | Structural: an entity is a branch of another |
| `parent_of` | Kinship: parent of |
| `sibling_of` | Kinship: sibling of |
| `spouse_of` | Kinship: spouse of |
| `student_of` | Pedagogic lineage: was a student of |
| `association_president` | President of an association, party or union |
| `association_officer` | Other named officer of an association |
| `vice_president` | Vice-president |
| `treasurer` | Tresorier / tresorerie |
| `secretaire_general_adj` | Secretaire general adjoint |

Roles only one person can hold at a time, used to detect overlapping incumbency and to infer replacement: `gerant`, `pdg`, `president_ca`, `dg`, `chef_du_gouvernement`.

### Announcement rubric codes

The 5-character suffix of an announcement's reference code (`2010G02623`**`SANB1`**) types the notice.

| rubric | legal form | section | domain |
| --- | --- | --- | --- |
| `APSF1` | ASSOC | registration | association |
| `APSF2` | ASSOC | registration | association |
| `APSF3` | ASSOC | registration | association |
| `BCFA5` |  | bilan | financial |
| `CFA5` |  | bilan | financial |
| `COPB1` | COOP | constitution | corporate |
| `COPB2` | COOP | gestion | corporate |
| `COPB3` | COOP | gestion | corporate |
| `DIVD1` |  | divers | other |
| `DIVD2` |  | divers | other |
| `DIVD3` |  | divers | other |
| `FCCB2` |  | fonds_commerce | commercial |
| `FCCC2` |  | fonds_commerce | commercial |
| `FCCC3` |  | fonds_commerce | commercial |
| `MINA4` |  | bilan | financial |
| `RCFA5` |  | bilan | financial |
| `RECZ9` |  | rectificatif | other |
| `SANB1` | SA | constitution | corporate |
| `SANB2` | SA | gestion | corporate |
| `SANB3` | SA | convocation | convocation |
| `SANB4` | SA | convocation | convocation |
| `SODB1` | AUTRE | constitution | corporate |
| `SODB2` | AUTRE | gestion | corporate |
| `SODB3` | AUTRE | gestion | corporate |
| `SODB3_` | AUTRE | gestion | corporate |
| `SRLB1` | SARL | constitution | corporate |
| `SRLB2` | SARL | gestion | corporate |
| `SRLB3` | SARL | gestion | corporate |
| `SRUB1` | SUARL | constitution | corporate |
| `SRUB2` | SUARL | gestion | corporate |
| `VEPA1` |  | judicial | judicial |
| `VEPA2` |  | judicial | judicial |
| `VEPA3` |  | judicial | judicial |

## Observed distributions

### Events by type

| event_type | n |
| --- | --- |
| `appointed` | 275,919 |
| `constituted` | 150,066 |
| `resides_at` | 83,123 |
| `charged_with_functions` | 62,783 |
| `capital_increased` | 43,163 |
| `shares_transferred` | 39,464 |
| `org_tie` | 30,333 |
| `resigned` | 25,972 |
| `headquarters_moved` | 18,171 |
| `liquidated` | 11,568 |
| `renewed` | 11,274 |
| `dissolved` | 8,704 |
| `spouse_of` | 6,787 |
| `renamed` | 3,128 |
| `capital_decreased` | 2,439 |
| `terminated` | 1,895 |
| `delegated_to_body` | 1,788 |
| `revoked` | 1,518 |
| `represented_by` | 1,137 |
| `widow_of` | 999 |
| `maiden_name_of` | 983 |
| `retired` | 19 |

### Events by role

| role_canonical | n |
| --- | --- |
| `(none)` | 407,124 |
| `gerant` | 172,102 |
| `chef_de_service` | 21,901 |
| `commissaire_aux_comptes` | 18,801 |
| `secretaire_general` | 14,277 |
| `shareholder_confirmed` | 14,043 |
| `association_president` | 13,097 |
| `auditor` | 12,803 |
| `administrateur` | 11,860 |
| `treasurer` | 11,685 |
| `cogerant` | 11,135 |
| `sous_directeur` | 10,705 |
| `liquidateur` | 9,185 |
| `representant` | 9,155 |
| `pdg` | 8,048 |
| `dg` | 7,779 |
| `associe` | 6,071 |
| `president_ca` | 3,972 |
| `vice_president` | 2,783 |
| `minister` | 2,579 |

