# Codebook

Generated 2026-09-12 by `python -m elitenet.codebook`. Do not edit by hand: column lists and counts are read from the data, and vocabularies from `config/`, so this file cannot drift from the dataset.

## Scope

- Window: **2008-01-01 to 2012-12-31**
- Collections: `journal-officiel`, `annonces-legales`
- Language: `fr` (the upstream mirror OCRs French only)
- Source: Journal Officiel de la République Tunisienne, via the public mirror at jort.tn. The gazette is public domain.

## How to read a date

Every event can carry four different dates and they are never merged. The act date is when a decision was taken; the registration and filing dates are administrative steps; the publication date is when the gazette printed it. `event_date` selects among them by the priority effective > act > filing > registration > publication, and `event_date_source` records which one was used. Where only the publication date exists, `date_precision` is `pub_only` and the event is interval-censored: it happened at or before that date, with no lower bound asserted.

## Time origin for networkDynamic

`exports/rnd/*.csv` express time as **integer days since 2008-01-01**. Censored endpoints are `-Inf` and `Inf`, which `networkDynamic` accepts natively; the window boundary is deliberately *not* substituted for an unknown date, because 'still in post at the end of observation' is a different claim from 'left on 2012-12-31'.

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

1,276 rows.

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

207,369 rows.

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

197,532 rows.

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
| `person_married_name` |  |
| `org_mention` |  |
| `org_mf` |  |
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
| `needs_review` |  |

### `resolution.csv`

113,178 rows.

One row per (person mention, organisation mention) dyad, with the score components behind its link. Nothing is dropped: `unresolved` dyads are retained so the dataset can be re-thresholded.

| column | note |
| --- | --- |
| `mention_key` |  |
| `person_mention` |  |
| `org_mention` |  |
| `org_mf` |  |
| `resolved_person_id` |  |
| `resolved_person_label` |  |
| `resolved_org_id` |  |
| `resolved_org_label` |  |
| `score` |  |
| `link_status` | `resolved` (score >= 0.70), `ambiguous` (0.45-0.70, or a rival within 0.05), `unresolved` (< 0.45, retained as a candidate new person). |
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

### `review_queue.csv`

1,323 rows.

Ambiguous dyads ordered by how consequential they are (seed degree and event count), for hand coding. These are cases the matcher declines to decide, not cases it got wrong.

| column | note |
| --- | --- |
| `mention_key` |  |
| `person_mention` |  |
| `org_mention` |  |
| `org_mf` |  |
| `resolved_person_id` |  |
| `resolved_person_label` |  |
| `resolved_org_id` |  |
| `resolved_org_label` |  |
| `score` |  |
| `link_status` | `resolved` (score >= 0.70), `ambiguous` (0.45-0.70, or a rival within 0.05), `unresolved` (< 0.45, retained as a candidate new person). |
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

### `gazette_only_persons.csv`

84,724 rows.

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

31,872 rows.

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
| `link_status` | `resolved` (score >= 0.70), `ambiguous` (0.45-0.70, or a rival within 0.05), `unresolved` (< 0.45, retained as a candidate new person). |
| `confidence` |  |
| `needs_review` |  |

### `spell_observations.csv`

4,585 rows.

Every dated observation attached to a spell. An `obs_kind` of `confirmation` or `renewal` proves the tie existed at that moment without asserting when it began.

| column | note |
| --- | --- |
| `spell_id` |  |
| `obs_date` |  |
| `obs_kind` |  |
| `obs_event_id` |  |
| `evidence_quote` | Verbatim text supporting the record. Validation asserts it occurs in the block. |

### `panel_edges_yearly.csv`

11,793 rows.

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

115,886 rows.

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

## TERGM panel

Written by `make tergm`. These are the yearly panel re-indexed for a temporal ERGM, not a separate measurement: the ties are the same ties. What they add is a declared bipartite split, a vertex set that does not move between periods, an explicit risk set, and covariates -- none of which an edge list can carry.

**Before specifying a model, read `docs/TERGM-multiplex.md`.** 82.1% of dated spells are right-censored, so a dissolution parameter fitted to this panel estimates when the gazette prints an exit rather than when a tie ends.

### `node_key.csv`

5,507 rows.

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

### `edges_yearly.csv`

10,997 rows.

The yearly panel re-indexed to bipartite vertex ids and reduced to **binary** ties: two roles in one firm in one year is two panel rows and one tie, with the roles preserved pipe-joined. `dissolution_observed` marks the minority of ties actually seen to end, as opposed to right-censored.

| column | note |
| --- | --- |
| `period` |  |
| `tail` |  |
| `head` |  |
| `role_canonical` |  |
| `certainty` | `certain` both endpoints dated; `probable` inside the certain core but an endpoint is censored; `possible` only inside the outer envelope; `undated` a seed tie with no time information. |
| `link_status` | `resolved` (score >= 0.70), `ambiguous` (0.45-0.70, or a rival within 0.05), `unresolved` (< 0.45, retained as a candidate new person). |
| `dissolution_observed` |  |

### `vertex_activity_yearly.csv`

27,535 rows.

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

27,535 rows.

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

11,102 rows.

Dyadic covariates as **sparse triplets** -- dense would be 2,592 x 2,915 per covariate per period. Projected from the seed sheet's undated kinship and shareholding ties, which is what makes them exogenous. `kin_in_org`, `owner_of` and `prior_comembership` are lagged to t-1 and so are absent in the first period; `is_shareholder` needs no lag and is present in all of them.

| column | note |
| --- | --- |
| `period` |  |
| `tail` |  |
| `head` |  |
| `kin_in_org` |  |
| `owner_of` |  |
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
| `appointed` | 83,319 |
| `constituted` | 51,766 |
| `capital_increased` | 14,073 |
| `shares_transferred` | 13,326 |
| `charged_with_functions` | 8,572 |
| `resigned` | 7,851 |
| `headquarters_moved` | 6,158 |
| `liquidated` | 3,646 |
| `renewed` | 3,091 |
| `dissolved` | 2,787 |
| `renamed` | 1,021 |
| `capital_decreased` | 730 |
| `revoked` | 455 |
| `represented_by` | 327 |
| `delegated_to_body` | 285 |
| `terminated` | 125 |

### Events by role

| role_canonical | n |
| --- | --- |
| `(none)` | 98,801 |
| `gerant` | 56,971 |
| `commissaire_aux_comptes` | 5,685 |
| `cogerant` | 3,736 |
| `secretaire_general` | 3,476 |
| `association_president` | 3,451 |
| `treasurer` | 3,261 |
| `administrateur` | 2,876 |
| `liquidateur` | 2,781 |
| `chef_de_service` | 2,723 |
| `pdg` | 2,394 |
| `associe` | 1,966 |
| `dg` | 1,878 |
| `representant` | 1,875 |
| `sous_directeur` | 1,429 |
| `president_ca` | 1,158 |
| `vice_president` | 829 |
| `dga` | 695 |
| `member` | 412 |
| `minister` | 332 |

