# SARL and SA companies in the register, and who is connected to them

`make legalform` → `rne_company_forms.csv`, `rne_company_persons.csv`

## The short answer

**61,715 register-listed companies are identifiably a SARL or an SA**
(57,190 SARL + 4,525 SA), with a further **12,822 SUARL** kept beside them
rather than folded in. Across all three forms, **72,689 individuals** are
connected to **54,256 of those companies** through **96,930 person-company
links**.

Of those links, **7,337 (7.6%) reach a person on the 13,630-name seed
roster**. The other 92.4% are people the gazette names in print who are not
in the roster at all. That ratio is the single most important number here: a
version of this answer restricted to known elites would have returned about a
thirteenth of it.

| form | companies | links | links reaching a seed elite |
|---|---|---|---|
| SARL | 57,190 | 72,049 | 4,579 (6.4%) |
| **SA** | 4,525 | 14,662 | **2,334 (15.9%)** |
| SUARL | 12,822 | 10,219 | 424 (4.1%) |
| **total in scope** | **74,537** | **96,930** | **7,337 (7.6%)** |
| with at least one named person | 54,256 | | |

**The seed roster concentrates in the SA.** A link on a société anonyme is
**2.5× more likely** to reach a known elite than one on a SARL and nearly
4× more likely than on a SUARL. That is the expected direction — an SA is
the larger, board-governed form, with administrateurs and a PDG rather than
a single gérant — but the size of the gap is worth having as a measurement
rather than an assumption, and it says where in the corporate population
the sheet's 13,630 names actually sit.

7,948 of these companies are also seed elite organisations in their own
right (`seed_org_id` populated).

## Why this needed both sources, and what neither could do

Neither source answers the question alone, and the two gaps are in different
places.

**The register knows which companies exist but not their legal form.**
`registres.categorie` is `SOCIETE` for 201,938 of 203,788 companies — it separates
a company from an association and stops. SARL, SUARL and SA are one value.
Reading the form out of the registered *name* recovers only **5.4%** of
companies, because most do not carry their form in their denomination.

**The gazette knows the legal form, from its own filing structure.** Every
announcement carries a rubric code and the rubric *is* the form: `SRLB1` is a
SARL constitution, `SANB2` an SA management filing, `SRUB1` a SUARL
constitution (`config/vocab_events.yaml`). This is the gazette's own
structured classification of the notice — not a phrase matched in OCR'd prose
— and it is the strongest legal-form evidence anywhere in this project.

**Neither source knows the officers; only the gazette names people.** The
register has **no officer table**. Its second table, `personnes physiques`,
is 315,659 sole proprietors and merchants registered in their own name —
people who *are* businesses, not people who run companies. No row in the
register connects a natural person to a SARL. So every one of the 96,930
person links comes from JORT, and the register's role is confined to saying
which companies are registered ones.

### Why the join is attributable

A block can name several firms, so a rubric form attached to the wrong one
would be a fabricated attribution. It is not, because `extract` already
clears `org_mf` and `org_rc` when a tie's target is a company named *inside*
a clause rather than the notice's subject. A rubric form and an identifier on
one event therefore always describe the same company.

## The coverage bound

**129,248 of 203,785 register companies (63.4%) have an undetermined legal
form.**

(203,785 rather than the 203,788 above: three companies carry no usable
identifier once the register's own internal conflicts are dropped, so they
cannot be keyed at all.)

That is not the same as "not a SARL or SA", and the table is built so the two
cannot be confused: an undetermined company is **absent** from
`rne_company_forms.csv` rather than recorded as excluded, and `validate`
fails at ERROR level if any row in it carries a blank or out-of-vocabulary
form. The 61,715 is a count of companies whose form is *known*.

The undetermined remainder is not a random subset. It is dominated by
companies that never filed a French-language notice in JORT — mostly small
and mostly Arabic-side — so the SARL/SA population here is skewed toward
firms with enough activity to have filed at all.

| `form_basis` | companies | what it rests on |
|---|---|---|
| `gazette_rubric` | 66,592 | the filing rubric alone |
| `register_name_only` | 4,578 | the registered name; the gazette never filed |
| `gazette_and_register_name_agree` | 3,169 | both, corroborating |
| `gazette_and_register_name_disagree` | 198 | both, differing — rubric kept |

Where the two disagree the rubric wins: a rubric is the section a company
actually filed under, a registered name is a string that may never have been
amended.

## SUARL is reported separately, not folded into SARL

A SUARL is a single-member company — one associate, so no internal coalition
and no shareholder network. Counting the 12,822 of them as SARL would inflate
the SARL population by 22% with firms whose ownership structure is
categorically different. They are labelled and the caller decides — and the
table above shows why it matters: SUARL links reach a seed elite at 4.1%
against the SA's 15.9%, so folding them in would dilute exactly the signal
an elite study is after.

## 746 companies changed legal form, and the dates are recorded

A company filing first under one form and later under another has
*transformed*. A SARL opening its capital to become an SA is a real corporate
event, and `conversion_date` carries the switch.

| direction | companies | reading |
|---|---|---|
| SUARL → SARL | 247 | sole owner took on partners |
| SARL → SA | 231 | capital opened |
| SARL → SUARL | 167 | partners bought out |
| SA → SARL | 94 | capital closed |
| SA → SUARL | 4 | |
| SUARL → SA | 3 | |

### The error this rule was built to fix

The first version took the **latest** filing as the current form. That let a
single stray rubric override every other: `HANNIBAL LEASE` files as an SA 47
times and as a SARL once, and reading the last filing turned a leasing
company into a SARL. The rule produced **1,637 conversions, of which 842 —
51% — were single anomalous filings.**

`decide_form` now requires each side of the switch to carry at least two
filings of its own form, and splits the timeline at the cut that best
separates them. A minority that fails the test is recorded in
`minority_forms` and does not decide: `TEC. SYS PLUS` reads SA with
`SUARL:1` noted, rather than converting on the strength of one filing.
`validate` checks at ERROR level that no surviving conversion rests on a
single filing.

This is the same failure mode as the identifier-conflict classifier earlier
in this project, which ranked by the closest pair among 1,606 values and so
labelled the worst merge in the corpus as OCR damage. Letting an extreme
single observation decide is the mistake in both.

## The person table

One row per (company, person) in `rne_company_persons.csv`.

| `link_grade` | links | what it means |
|---|---|---|
| `gazette_only` | 89,593 | named in print, not on the seed roster |
| `resolved` | 4,719 | dyad-anchored: the organisation agreed |
| `inferred` | 2,520 | name rarity |
| `snowball` | 98 | an anchor a later pass supplied |

A person is keyed on their seed id where resolution named one and on their
mention cluster otherwise, so the two populations are never silently pooled —
`is_seed_elite` is the filter, and `validate` checks at ERROR level that it
never contradicts the grade. Where one person reaches one company by two
routes the **strongest** grade is kept, so a pair never reads weaker than the
best evidence available for it.

Roles accumulate rather than reduce: `role_primary` is the modal role and
`roles` carries all of them with counts, because *gérant* then *liquidateur*
are two relationships at two different times and which one a reader wants is
not this stage's call.

`role_primary` across the 96,930 links:

| role | links |
|---|---|
| gérant | 53,031 |
| *(none stated)* | 15,176 |
| commissaire aux comptes | 8,139 |
| cogérant | 4,318 |
| administrateur | 3,538 |
| liquidateur | 2,972 |
| associé | 2,591 |
| PDG | 2,083 |
| DG | 1,881 |
| président du CA | 1,112 |

## Known limitations

* **`jort_label` can be extraction noise.** Some labels are clauses an
  `org_name` misread as a company — `Article 301 du code des sociétés
  commerciale` appears as one. The *company* is real (its identifier is in
  the register); only the gazette-side label is junk. Prefer `rne_name_fr`
  where it is populated. The fix belongs in `org_name`, not here.
* **A gazette-only person is a mention cluster, not a verified individual.**
  Two men of the same name in the same cluster are one row here. This is the
  same person-side homonym problem `docs/STRUCTURAL-HOLES-multiplex.md`
  quantifies, and it is why these rows are labelled rather than promoted.
* **The form is the form the company *filed under*, at the times it filed.**
  A company that converted before its first JORT filing reads as its later
  form throughout, with no conversion recorded.
* **A person "connected to" a company includes auditors and liquidators.**
  8,139 links are a *commissaire aux comptes* and 2,972 a liquidator —
  connections of a professional rather than proprietary kind. A further
  15,176 links state no role at all. Filter on `role_primary` for ownership
  or management specifically.
