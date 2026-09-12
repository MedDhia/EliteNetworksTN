# Codebook

All tables live in `data/processed/`. Identifiers are deterministic hashes of
the normalised string they stand for, so a rebuild on the same corpus produces
the same ids, and a rebuild on a larger corpus keeps existing ids stable except
for person ids (which depend on the resolution pass over all names at once).

Fields ending in `_raw` hold the surface string as printed. They are kept
deliberately: every coding decision can be checked against the text it came
from, and against the scanned page via `pdf_url` and `page`.

---

## `events.csv.gz` — one person–office transition

The unit is an *event*, not a person: someone appointed twice appears twice.

### Provenance

| Field | Description |
|---|---|
| `event_id` | hash of issue, act, person, office and type |
| `issue_key` | `journal-officiel/fr/{year}/{issue}` |
| `year`, `issue` | issue of publication |
| `page` | page of the OCR'd PDF the act begins on |
| `pdf_url` | the scanned original |
| `act_seq` | position of the act within the issue |
| `act_kind` | `decret`, `arrete`, `decision`, `loi` |
| `act_qualifier` | `presidentiel`, `gouvernemental`, `loi`, or empty |
| `act_number` | e.g. `2011-1095` |
| `act_date` | date the act was taken |
| `authority_raw` | ministry / institution heading the act was published under |
| `section_raw` | sub-heading (`NOMINATIONS`, `CESSATION DE FONCTIONS`, …) |
| `source_layer` | see **Source layers** below |

### The event

| Field | Description |
|---|---|
| `event_type` | `appointment`, `board`, `termination`, `renewal`, `retirement`, `delegation` |
| `event_date` | `effect_date` where the act names one, else `act_date` |
| `event_year` | calendar year of `event_date` |
| `effect_date` | date named by an *"à compter du …"* clause |
| `person_id`, `person_raw`, `honorific` | the officeholder |
| `grade_raw` | civil-service grade in apposition (*"administrateur général"*) |
| `position_raw`, `position_clean` | the office |
| `position_rank`, `rank_score` | ordered rank code, see **Rank scale** |
| `org_id`, `org_name`, `org_key` | the organisation |
| `org_source` | `text` if the act named it, `heading` if taken from the ministry heading, `none` |
| `org_form` | `ministere`, `entreprise_publique`, `universite`, … |
| `org_portfolio` | stable ministry portfolio id, see **Ministries over time** |
| `parent_org_id`, `parent_org_name` | the supervising body (the ministry heading) |
| `office_id` | hash of organisation + rank + position, the unit a succession chain runs through |
| `board_body_raw` | the collegial body for a board seat |
| `replaces_id`, `replaces_raw` | the incumbent this act names as replaced |
| `signatory_id`, `signatory_name`, `signatory_office` | who signed the act |
| `proposer_raw` | *"Sur proposition de …"* clause |
| `delegator_raw` | principal named by a delegation of signature |

### Source layers

`source_layer` records **where in the act** a row was read, which is a direct
statement of its evidential status. Filter on it.

| Value | Meaning | Use |
|---|---|---|
| `dispositif` | the operative text of the act | the default; this is the act doing the thing |
| `list` | an entry in an enumerated list under one operative verb | equivalent to `dispositif` |
| `title` | the action was stated in a long-form decree's title | equivalent, slightly noisier |
| `recital` | a *"Vu le décret n° … chargeant M. X …"* clause | **evidence of an earlier act, not this one** |

Recitals are worth keeping — they are dated, numbered citations of past
appointments, and they recover appointments from issues that are missing or
poorly OCR'd — but they are not the act in front of you. `cited_act_number`
and `cited_act_date` identify the act being recited, and `event_date` is set to
the *cited* date, not the publication date. Exclude them with
`events[events.source_layer != "recital"]` for a strict act-level analysis.

---

## `spells.csv.gz` — office-holding spells

One row per continuous tenure of one person in one office.

| Field | Description |
|---|---|
| `spell_id` | hash of person, office and start date |
| `person_id`, `office_id`, `org_id`, `parent_org_id` | who, where |
| `position_clean`, `position_rank`, `rank_score` | what |
| `start_date`, `start_year` | from the opening event's `event_date` |
| `end_date`, `end_year` | see **End reasons** |
| `duration_days` | `end_date - start_date` |
| `end_reason` | how the spell was closed |
| `start_event_id`, `end_event_id`, `start_act`, `start_issue`, `pdf_url` | provenance |
| `predecessor_id` | incumbent named as replaced, if any |
| `renewals` | count of renewal acts observed during the spell |

### End reasons

The gazette announces entries reliably and exits much less so. Three closure
mechanisms are used, in descending order of evidential strength, and the one
that fired is recorded:

| `end_reason` | Meaning | Treat as |
|---|---|---|
| `termination` | an explicit cessation-of-functions act | observed exit |
| `retirement` | an explicit retirement act | observed exit |
| `succeeded` | a successor's act named this person as replaced | observed exit |
| `moved` | the person took another substantive office | observed exit, imputed date |
| `censored` | nothing closed it | **right-censored** |

`moved` rests on an assumption — that the substantive offices in this dataset
are mutually exclusive — which is right for line administration and wrong for
some cabinet-level pluralism. Board seats (`position_rank == "administrateur_ca"`)
are exempt and may run concurrently.

For survival analysis, `censored` and `moved` are different things: the first is
a censoring indicator, the second is an exit with a date that is correct to the
day the person surfaced elsewhere, not necessarily the day they left.

---

## `person_year.csv.gz` — the panel

Person × year × office, exploded from spells. A person holding two offices in
one year (a post and a board seat) has two rows.

| Field | Description |
|---|---|
| `person_id`, `year` | the panel key |
| `spell_id`, `office_id`, `org_id`, `parent_org_id`, `org_portfolio` | the office held |
| `position_rank`, `rank_score` | rank that year |
| `is_entry_year`, `is_exit_year` | spell boundaries |
| `censored` | the spell was never closed |

---

## `persons.csv.gz` and `organisations.csv.gz`

`persons.csv.gz` carries `name` (the most frequent surface spelling),
`name_variants` (every spelling merged into this id — inspect this when a
person looks suspicious), `first_year`, `last_year`, `n_events`, `n_spells`,
`n_orgs`, `career_days`, `peak_rank`, `peak_rank_score` and `roles`.

The register covers everyone any relation references, not only appointees.
`roles` says how a person enters it — `appointee`, `predecessor`, `signatory`,
or a `+`-joined combination. Someone who only ever appears as the incumbent an
act replaces, or only as a signatory, still gets a row (with `n_events` 0), so
a join from `succession.csv.gz` or `signature.csv.gz` never lands on a missing
id.

`organisations.csv.gz` carries `org_name`, `org_form`, `org_portfolio`,
`n_events`, `n_persons`, `first_year`, `last_year`.

---

## Rank scale

`position_rank` maps a position string onto an ordered hierarchy;
`rank_score` is the ordinal value. Higher is more senior. The scale follows
the tiers Tunisian administrative law uses for *emplois fonctionnels*,
extended upwards to political office.

| Score | Code | Typical strings |
|---|---|---|
| 100 | `chef_etat` | Président de la République |
| 95 | `chef_gouvernement` | Premier ministre, Chef(fe) du gouvernement |
| 90 | `ministre` | ministre, ministre d'État |
| 85 | `secretaire_etat` | secrétaire d'État |
| 80 | `gouverneur` | gouverneur |
| 74 | `chef_cabinet` | chef de cabinet, directeur du cabinet |
| 72 | `conseiller_pol` | conseiller auprès du Président, chargé de mission |
| 70 | `secretaire_general` | secrétaire général |
| 68 | `pdg` | président directeur général |
| 65 | `directeur_general` | directeur général, gouverneur de la BCT |
| 64 | `president_juridiction` | premier président de la cour…, procureur général |
| 60 | `inspecteur_general` | inspecteur général, contrôleur général |
| 55 | `directeur` | directeur, commissaire régional, délégué régional |
| 45 | `sous_directeur` | sous-directeur, directeur adjoint |
| 35 | `chef_service` | chef de service / division / bureau / arrondissement |
| 30 | `administrateur_ca` | administrateur, membre du conseil |
| 28 | `magistrat` | juge, conseiller à la cour |
| 20 | `cadre` | attaché, inspecteur, ingénieur, receveur |
| 15 | `local` | cheikh, omda, délégué, maire |
| 12 | `academique` | professeur, maître de conférences, doyen |
| 10 | `medical` | chef de service hospitalier, médecin |
| 5 | `autre` | unmatched |

The scale is a coding decision, not a fact about the world. It is defined in
one place (`RANK_SCALE` in `src/eltn/normalize.py`) precisely so it can be
changed and the dataset rebuilt.

---

## Ministries over time

Tunisian ministries are renamed, split and merged constantly. Treating each
printed title as a distinct organisation would shatter every career; treating
them all as "a ministry" would erase the substance.

`org_portfolio` identifies a ministry by the **policy domains in its title**.
*Ministère de la santé publique* and *Ministère de la santé* are both
`min_sante`; *Ministère du plan et des finances* is `min_finances+plan`, which
is neither `min_finances` nor `min_plan` but is recognisably related to both by
string containment on the domain list.

Two central-executive bodies get fixed ids because their names changed with the
constitutional order rather than the portfolio: `presidence_republique`, and
`presidence_gouvernement` (which absorbs *Premier Ministère*, in use before
2014).

`MINISTRY_DOMAINS` in `normalize.py` is the full list.

---

## Person resolution

Names are matched in two deterministic passes.

1. **Exact key.** Fold accents and case, drop honorifics and relational tokens
   (*épouse*, *née*), drop name particles (*ben*, *el*, *bou*), transliterate
   each remaining token to a consonant skeleton that collapses the vowel and
   digraph variation romanisation introduces (`ch`/`sh`, `ou`/`u`,
   `Chedly`/`Chadly`), strip the assimilated Arabic article
   (`Ennaceur`→`naceur`), then sort the tokens. Sorting makes
   *"Gargouri Mohamed"* and *"Mohamed Gargouri"* one key.
2. **Affix variants.** Within blocks sharing a patronym stem, merge keys whose
   tokens differ only by truncated or extended endings — a dropped final vowel,
   a lost OCR character, a French feminine ending (*Romdhan* / *Romdhane*).
   A prefix relationship is required rather than a similarity score, because
   edit-distance scores cannot separate *Salah* from *Salem*, which are
   different names.

`persons.csv:name_variants` lists every surface string merged into an id.
Homonymy is not resolved — see [`LIMITATIONS.md`](LIMITATIONS.md).

---

## Edge tables

All in `data/processed/edges/`. `source` and `target` are `person_id` except in
`affiliation.csv.gz`, where `target` is an `org_id`.

| File | Key fields |
|---|---|
| `affiliation.csv.gz` | `start_date`, `end_date`, `start_year`, `end_year`, `position_rank`, `end_reason`, `spell_id` |
| `colleague.csv.gz` | `org_id`, `start_date`, `end_date`, `overlap_days`, `rank_gap` |
| `succession.csv.gz` | `office_id`, `org_id`, `position_rank`, `date`, `year` |
| `signature.csv.gz` | `signatory_office`, `org_id`, `position_rank`, `date`, `year`, `event_type` |
| `delegation.csv.gz` | `delegator_raw`, `signatory_office`, `org_id`, `date`, `year` |
| `coappointment.csv.gz` | `issue_key`, `act_seq`, `act_number`, `date`, `year`, `cohort_size` |

`colleague` edges are undirected, stored once with `source < target`.
Organisations with more than 400 spells are skipped: a ministry that appointed
several thousand section chiefs over seventy years is not a co-membership
context, and including it would generate tens of millions of meaningless dyads.
The threshold is the `max_org_size` argument of `network.colleague_edges`.

`coappointment` similarly skips acts naming more than 60 people (mass
promotion lists).
