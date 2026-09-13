# Codebook — A'lam Tunisiyun

Generated 2026-09-13 by `python -m aalam.codebook`. Do not edit by hand: column lists and counts are read from the data and vocabularies from `config/`, so this file cannot drift from the dataset.

## Source

*أعلام تونسيون* (A'lam Tunisiyun), Sadok Zmerli, Dar al-Gharb al-Islami, Beirut, 2000. 384 pages, Arabic.

38 biographical essays in three parts, which the author calls the predecessors, the followers and the contemporaries. The subjects span 1606-1973.

The volume has no text layer: every page is a bilevel scan, and the text here was produced by OCR whose settings are recorded per page in `data/raw/aalam/manifest.csv`. The scan is not redistributed; the manifest carries a sha256 per page so it can be rebuilt and checked.

## How to read a date

A biography states a relation far more often than it dates one. Where the sentence gives a year, `year` holds it and `date_precision` is `year`. Where it gives a span, `year_lo`/`year_hi` bound it and precision is `year_range`. Where it gives neither, precision is `none`.

`none` is a statement about the source, not a gap to be imputed: the book asserts that the tie existed without saying when. Treating those rows as contemporaneous with anything else is a modelling choice the data does not support.

## Tables

### `entries.csv`

38 rows. One row per biographical essay: the 38 subjects, their cohort, life dates and page range. The spine of the build.

| column | note |
|---|---|
| `entry_uid` | `aalam:<cohort>.<entry>`, e.g. aalam:2.09 for the ninth essay of part two. |
| `cohort` | The author's own generational division: السابقون (predecessors), التابعون (followers), المعاصرون (contemporaries). Assigned by Zmerli, not by us. |
| `cohort_no` |  |
| `entry_no` |  |
| `name_ar` |  |
| `name_toc` |  |
| `birth_year` | From the entry heading. Empty where the volume itself prints '(... - YYYY)'. |
| `death_year` | From the entry heading. |
| `role_descriptor_ar` | The epithet the author gives the subject beneath the dates, e.g. الجندي والمصلح ورجل الدولة. His characterisation, not a coding. |
| `rank` | A title carried in the name (pasha, bey, agha, general). Stripped from the identifier, kept here as evidence of standing. |
| `folio_start` |  |
| `folio_end` |  |
| `pdf_page_start` |  |
| `pdf_page_end` |  |
| `n_pages` |  |
| `n_chars` |  |
| `text_sha1` |  |
| `header_name_agrees` |  |
| `needs_review` | Set where something did not reconcile. Never silently corrected. |
| `review_note` |  |

### `persons.csv`

242 rows. Person register. `is_subject` separates the 38 men and women who have an essay of their own from the alters merely named inside one.

| column | note |
|---|---|
| `person_id` | `PERSON_<SURNAME>_<GIVEN>`, from the identity key only. Titles are stripped, so الجنرال خير الدين and خير الدين باشا are one person. |
| `name_ar` |  |
| `name_translit` | Deterministic lossy ASCII, for joining by eye with the other builds. Not a scholarly transliteration. |
| `is_subject` | `yes` for the 38 with an essay; `no` for someone named inside one. Degrees are not comparable across this line. |
| `name_kind` | `named` where the book gives a name; `described` where it places the person only by a relation (ابنة الأصرم, شقيق محمد باي). A described node is a real tie to an unidentified person, and two such nodes may or may not be the same person. Do not merge them, and exclude them before counting a population. |
| `entry_uid` | `aalam:<cohort>.<entry>`, e.g. aalam:2.09 for the ninth essay of part two. |
| `cohort` | The author's own generational division: السابقون (predecessors), التابعون (followers), المعاصرون (contemporaries). Assigned by Zmerli, not by us. |
| `birth_year` | From the entry heading. Empty where the volume itself prints '(... - YYYY)'. |
| `death_year` | From the entry heading. |
| `role_descriptor_ar` | The epithet the author gives the subject beneath the dates, e.g. الجندي والمصلح ورجل الدولة. His characterisation, not a coding. |
| `rank` | A title carried in the name (pasha, bey, agha, general). Stripped from the identifier, kept here as evidence of standing. |
| `n_assertions` |  |
| `n_ties` |  |
| `first_seen_entry` |  |

### `organisations.csv`

366 rows. Schools, mosques, courts, ministries, newspapers and societies named as the other end of a tie.

| column | note |
|---|---|
| `org_id` |  |
| `name_ar` |  |
| `name_translit` | Deterministic lossy ASCII, for joining by eye with the other builds. Not a scholarly transliteration. |
| `org_kind` |  |
| `n_ties` |  |
| `first_seen_entry` |  |

### `edges/all.csv`

873 rows. Every relational assertion, one row per tie, with the sentence that states it.

| column | note |
|---|---|
| `edge_id` |  |
| `layer` | One of tutelage, office, kinship, membership. |
| `relation` | The directed relation; see the controlled vocabulary below. |
| `from_id` |  |
| `from_name` |  |
| `to_id` |  |
| `to_name` |  |
| `to_kind` |  |
| `subjects_studied` | For a tutelage tie, the subjects named as read with the teacher (الفقه, النحو …), pipe-separated. |
| `year` | A single year where the sentence states one. |
| `year_lo` | Lower bound of the interval the sentence supports. |
| `year_hi` | Upper bound of the interval the sentence supports. |
| `date_precision` | `year`, `year_range`, or `none`. `none` means the source states the tie without placing it in time -- not that the date is merely missing. |
| `evidence_tier` | Always `book_stated`. Everything here is one author's account; nothing is confirmed against a document. |
| `extractor` | `rule` for the cue table, `llm` for the model pass. Both are gated on the quote check; kept apart so either can be excluded from a result. |
| `pattern_id` | The cue that fired, or the model prompt version. |
| `confidence` |  |
| `entry_uid` | `aalam:<cohort>.<entry>`, e.g. aalam:2.09 for the ninth essay of part two. |
| `evidence_quote` | The sentence, verbatim from the OCR. Every row is checked against its entry by `aalam.validate`; a row that cannot be quoted is dropped. |

### `edges/tutelage.csv`

162 rows. Who studied under whom, and where. The layer no other build in this repository has.

| column | note |
|---|---|
| `edge_id` |  |
| `layer` | One of tutelage, office, kinship, membership. |
| `relation` | The directed relation; see the controlled vocabulary below. |
| `from_id` |  |
| `from_name` |  |
| `to_id` |  |
| `to_name` |  |
| `to_kind` |  |
| `subjects_studied` | For a tutelage tie, the subjects named as read with the teacher (الفقه, النحو …), pipe-separated. |
| `year` | A single year where the sentence states one. |
| `year_lo` | Lower bound of the interval the sentence supports. |
| `year_hi` | Upper bound of the interval the sentence supports. |
| `date_precision` | `year`, `year_range`, or `none`. `none` means the source states the tie without placing it in time -- not that the date is merely missing. |
| `evidence_tier` | Always `book_stated`. Everything here is one author's account; nothing is confirmed against a document. |
| `extractor` | `rule` for the cue table, `llm` for the model pass. Both are gated on the quote check; kept apart so either can be excluded from a result. |
| `pattern_id` | The cue that fired, or the model prompt version. |
| `confidence` |  |
| `entry_uid` | `aalam:<cohort>.<entry>`, e.g. aalam:2.09 for the ninth essay of part two. |
| `evidence_quote` | The sentence, verbatim from the OCR. Every row is checked against its entry by `aalam.validate`; a row that cannot be quoted is dropped. |

### `edges/office.csv`

291 rows. Posts taken up and left.

| column | note |
|---|---|
| `edge_id` |  |
| `layer` | One of tutelage, office, kinship, membership. |
| `relation` | The directed relation; see the controlled vocabulary below. |
| `from_id` |  |
| `from_name` |  |
| `to_id` |  |
| `to_name` |  |
| `to_kind` |  |
| `subjects_studied` | For a tutelage tie, the subjects named as read with the teacher (الفقه, النحو …), pipe-separated. |
| `year` | A single year where the sentence states one. |
| `year_lo` | Lower bound of the interval the sentence supports. |
| `year_hi` | Upper bound of the interval the sentence supports. |
| `date_precision` | `year`, `year_range`, or `none`. `none` means the source states the tie without placing it in time -- not that the date is merely missing. |
| `evidence_tier` | Always `book_stated`. Everything here is one author's account; nothing is confirmed against a document. |
| `extractor` | `rule` for the cue table, `llm` for the model pass. Both are gated on the quote check; kept apart so either can be excluded from a result. |
| `pattern_id` | The cue that fired, or the model prompt version. |
| `confidence` |  |
| `entry_uid` | `aalam:<cohort>.<entry>`, e.g. aalam:2.09 for the ninth essay of part two. |
| `evidence_quote` | The sentence, verbatim from the OCR. Every row is checked against its entry by `aalam.validate`; a row that cannot be quoted is dropped. |

### `edges/kinship.csv`

74 rows. Descent, marriage and affinity.

| column | note |
|---|---|
| `edge_id` |  |
| `layer` | One of tutelage, office, kinship, membership. |
| `relation` | The directed relation; see the controlled vocabulary below. |
| `from_id` |  |
| `from_name` |  |
| `to_id` |  |
| `to_name` |  |
| `to_kind` |  |
| `subjects_studied` | For a tutelage tie, the subjects named as read with the teacher (الفقه, النحو …), pipe-separated. |
| `year` | A single year where the sentence states one. |
| `year_lo` | Lower bound of the interval the sentence supports. |
| `year_hi` | Upper bound of the interval the sentence supports. |
| `date_precision` | `year`, `year_range`, or `none`. `none` means the source states the tie without placing it in time -- not that the date is merely missing. |
| `evidence_tier` | Always `book_stated`. Everything here is one author's account; nothing is confirmed against a document. |
| `extractor` | `rule` for the cue table, `llm` for the model pass. Both are gated on the quote check; kept apart so either can be excluded from a result. |
| `pattern_id` | The cue that fired, or the model prompt version. |
| `confidence` |  |
| `entry_uid` | `aalam:<cohort>.<entry>`, e.g. aalam:2.09 for the ninth essay of part two. |
| `evidence_quote` | The sentence, verbatim from the OCR. Every row is checked against its entry by `aalam.validate`; a row that cannot be quoted is dropped. |

### `edges/membership.csv`

346 rows. Belonging to, founding or heading a body.

| column | note |
|---|---|
| `edge_id` |  |
| `layer` | One of tutelage, office, kinship, membership. |
| `relation` | The directed relation; see the controlled vocabulary below. |
| `from_id` |  |
| `from_name` |  |
| `to_id` |  |
| `to_name` |  |
| `to_kind` |  |
| `subjects_studied` | For a tutelage tie, the subjects named as read with the teacher (الفقه, النحو …), pipe-separated. |
| `year` | A single year where the sentence states one. |
| `year_lo` | Lower bound of the interval the sentence supports. |
| `year_hi` | Upper bound of the interval the sentence supports. |
| `date_precision` | `year`, `year_range`, or `none`. `none` means the source states the tie without placing it in time -- not that the date is merely missing. |
| `evidence_tier` | Always `book_stated`. Everything here is one author's account; nothing is confirmed against a document. |
| `extractor` | `rule` for the cue table, `llm` for the model pass. Both are gated on the quote check; kept apart so either can be excluded from a result. |
| `pattern_id` | The cue that fired, or the model prompt version. |
| `confidence` |  |
| `entry_uid` | `aalam:<cohort>.<entry>`, e.g. aalam:2.09 for the ninth essay of part two. |
| `evidence_quote` | The sentence, verbatim from the OCR. Every row is checked against its entry by `aalam.validate`; a row that cannot be quoted is dropped. |

## Controlled vocabularies

### `layer`

| value | meaning |
|---|---|
| `tutelage` | Pedagogical descent: who studied under whom, and in what |
| `office` | Holding, taking up or leaving a post |
| `kinship` | Descent, marriage and affinity |
| `membership` | Belonging to a body: a school, a paper, a society, a party |

### `relation`

| value | meaning |
|---|---|
| `studied_under` | Subject read with, or was the pupil of, the counterparty |
| `taught` | Subject taught the counterparty |
| `licensed_by` | Subject received an ijaza from the counterparty |
| `appointed_to` | Subject took up a named post |
| `left_post` | Subject resigned, was dismissed, or otherwise left a post |
| `succeeded` | Subject took over a post from the counterparty |
| `child_of` | Subject is the child of the counterparty |
| `sibling_of` | Subject is the sibling of the counterparty |
| `married_to` | Subject married the counterparty |
| `kin_of` | Kin, relation unspecified or more distant |
| `member_of` | Subject belonged to a named body |
| `founded` | Subject founded a named body |
| `headed` | Subject presided over a named body |
| `wrote_for` | Subject edited or wrote for a named publication |
| `studied_at` | Subject was educated at a named institution |
| `authored` | Subject wrote a named work |
| `taught_at` | Subject held a teaching post at a named institution |
| `commissioned_by` | Subject was charged with a named mission by the counterparty |
| `patronised_by` | Counterparty advanced, protected or favoured the subject |
| `patronised` | Subject advanced, protected or favoured the counterparty |
| `opposed_by` | Counterparty worked against the subject; rivalry the text states |
| `recommended` | Subject proposed the counterparty for a post |
| `colleague_of` | Named as a friend, associate or fellow of the counterparty |
| `eulogised_by` | Counterparty publicly praised or mourned the subject |
| `read_work_of` | Subject studied the writings of the counterparty, who is not a contemporary and did not teach them in person |

### Cue bindings

The rule pass emits only cues bound by a preposition or a possessive pronoun. Arabic is verb-subject-object, so a bare verb is followed by the clause's subject, and a pattern cannot tell that from the counterparty. Cues marked `vso` in `config/aalam_vocab_relations.yaml` are left to the model pass.

## Observed distributions

### Edges by relation

| relation | n |
|---|---|
| `appointed_to` | 153 |
| `member_of` | 91 |
| `studied_at` | 64 |
| `authored` | 63 |
| `colleague_of` | 57 |
| `headed` | 52 |
| `founded` | 47 |
| `wrote_for` | 46 |
| `studied_under` | 38 |
| `taught_at` | 36 |
| `child_of` | 33 |
| `commissioned_by` | 26 |
| `opposed_by` | 25 |
| `patronised_by` | 21 |
| `kin_of` | 20 |
| `left_post` | 20 |
| `succeeded` | 16 |
| `sibling_of` | 12 |
| `taught` | 11 |
| `patronised` | 10 |
| `read_work_of` | 10 |
| `married_to` | 9 |
| `eulogised_by` | 5 |
| `recommended` | 5 |
| `licensed_by` | 3 |

### Edges by layer

| layer | n |
|---|---|
| `membership` | 346 |
| `office` | 291 |
| `tutelage` | 162 |
| `kinship` | 74 |
