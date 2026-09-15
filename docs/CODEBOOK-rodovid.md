# Codebook — Rodovid genealogies

A crawl of [rodovid.org](https://rodovid.org) seeded on Tunisian elite families,
filtered down to the Tunisians. Two files describe the people and the kinship
between them; a third holds everyone the filter removed, so the call can be
checked rather than taken on trust. Two more collapse the people to families,
which is the level at which elite alliance is usually read.

Everything lives in `data/processed/rodovid/`.

| file | rows | what |
|---|---|---|
| `tunisian_individuals.csv` | 37,819 | people classified as Tunisian, with the evidence for each |
| `tunisian_ties.csv` | 23,565 | parent, sibling and spouse ties where both ends are Tunisian |
| `excluded_individuals.csv` | 27,716 | everyone removed, with the same evidence columns |
| `family_nodes.csv` | 3,243 | families: people recorded, marriages out, allies, marriages within the surname |
| `family_alliances.csv` | 3,642 | family pairs, and how many marriages join them |
| `person_years.csv` | 18,782 | a birth year for every person who can be given one, and where it came from |
| `marriages_dated.csv` | 3,592 | one row per couple, with the generation it belongs to |
| `alliance_panel.csv` | 3,260 | family pair × period: the dynamic edge list |
| `network_evolution.csv` | 11 | one row per 25-year period: the network as it stood, and what was new |
| `source/rodovid_individuals.csv.gz` | 65,535 | the `Individuals` sheet of the source workbook, verbatim |
| `source/rodovid_ties.csv.gz` | 65,535 | the `Ties` sheet, verbatim |

Rebuild everything with `make rodovid` — stdlib only for the three table
stages, about fifteen seconds, byte-identical on every run. The figure stage is
separate and needs matplotlib; see below.

**Read [`LIMITATIONS-rodovid.md`](LIMITATIONS-rodovid.md) before using any of
it.** The export is truncated, and that is a property of the source rather than
of the code.

The two files under `source/` are the workbook's own sheets, dumped to CSV once
and committed so the build needs no Excel reader:

```python
import pandas as pd                                        # needs pandas, xlrd
for sheet, out in [("Individuals", "rodovid_individuals.csv.gz"),
                   ("Ties", "rodovid_ties.csv.gz")]:
    pd.read_excel("RodovidData234862.xls", sheet).to_csv(
        "data/processed/rodovid/source/" + out, index=False, lineterminator="\n",
        compression={"method": "gzip", "mtime": 0})
```

## Stages

| stage | module | what it writes |
|---|---|---|
| `make rodovid-build` | `rodovid.build` | the three person-level tables |
| `make rodovid-families` | `rodovid.families` | the two family-level tables |
| `make rodovid-audit` | `rodovid.audit` | nothing; exits non-zero if a published claim stops being true |
| `make rodovid-dynamic` | `rodovid.dynamic` | the four dated tables |
| `make rodovid-validate` | `rodovid.dynamic --validate` | `docs/VALIDATION-rodovid-dynamic.md` |
| `make rodovid-figures` | `rodovid.figures` | the three static plates in `figures/` (~6 min, needs matplotlib) |
| `make rodovid-figures-dynamic` | `rodovid.figures_dynamic` | the three plates over time (~4 min, needs matplotlib) |

## What the source is, and what was wrong with it

The source is `RodovidData234862.xls`, an export of a rodovid.org crawl seeded
on Tunisian families. Crawls follow marriages, and this one overran its
subject: alongside the Tunisian families the export carries French aristocratic
and industrial lineages (Polignac, La Rochefoucauld, Prouvost, Tiberghien),
German, Russian, Danish and Swedish royalty, the Ottoman house and its Abkhaz
and Circassian beys, the London Rothschild–Montefiore connection, and Egyptian
and Persian court families. Slightly more than four rows in ten had nothing to
do with Tunisia.

**The export is truncated.** Both sheets came out of Excel at exactly 65,535
data rows — the BIFF8 row limit — so both were cut, not merely the larger one.
Two consequences: 3,872 people are referenced by a tie but have no row of their
own, and 22,857 of the Tunisians kept here have no surviving tie at all, which
is a property of the export rather than of the families. Anything computed on
the kinship graph is a lower bound. A re-export in `.xlsx` would lift the cap.

## How the filter works

Nothing is hand-listed. Each of the 65,535 people is scored on four signals,
each in [-1, 1], positive for Tunisian:

| signal | weight | what it reads |
|---|---|---|
| `sig_place` | 2.0 / 1.5 | Tunisian toponyms and beylical offices in the person's own `INFO` against foreign countries, capitals and dynastic seats, plus the script the name is written in |
| `sig_name` | 1.2 | a character n-gram Naive Bayes model over `FULLNAME` |
| `sig_family` | 1.0 | the place evidence of everyone *else* sharing the surname |
| `sig_network` | 1.5 | the direct evidence of relatives one and two steps away in the kinship graph |

A person is kept when the weighted sum is positive (above 0.1 — a record with
no signal at all is not evidence of a Tunisian).

The name model is trained on the 13,242 people the place signal already
labels, and scores 0.966 on a held-out fifth, printed on every run. It is what
carries the 26,000-odd rows whose own record names no place, and it is why
`sig_name` and the seeding place evidence should not be read as independent.

Tunisian place evidence is weighted more heavily than foreign (2.0 against
1.5) because the evidence is asymmetric: the crawl was seeded on Tunisians, so
a Tunisian record routinely names Istanbul, Paris or Rome — study, exile,
Ottoman ancestry, a Turco-Tunisian mamluk line — while a European or Ottoman
record has no reason to name Sousse.

### Columns

`tunisian_individuals.csv` and `excluded_individuals.csv` carry the same
columns, except that `married_in` is meaningful only among the kept:

| column | meaning |
|---|---|
| `id` | rodovid person id, unique, the key `tunisian_ties.csv` joins on |
| `fullname`, `surname`, `gender` | as exported; `surname` is rodovid's own reduction of the name |
| `score` | the weighted sum; rows are written in descending order |
| `confidence` | `high` (\|score\| ≥ 1.5), `medium` (≥ 0.5), `low` (below) |
| `sig_place`, `sig_name`, `sig_family`, `sig_network` | the four signals, before weighting |
| `degree` | ties in the export, before filtering |
| `married_in` | kept, but the person's own name and record are foreign — a foreign spouse inside a Tunisian family (68 rows) |
| `tunisia_link` | excluded, but the record names a Tunisian place (8 rows) |
| `info` | the source `INFO` field, verbatim: births, deaths, marriages, offices, schooling |

Both flags mark the cases where the signals disagree, which are the ones worth
a look. `tunisia_link` is mostly protectorate France — Roger Seydoux, résident
général; Baron Rodolphe d'Erlanger of Sidi Bou Saïd; a British vice-consul —
people whose lives ran through Tunisia but whose families are European.

Because every signal is written out, the threshold can be moved without
rerunning anything: a stricter set is `confidence == "high"` (32,320 people),
and rows the filter dropped at `score` just below zero are the top of
`excluded_individuals.csv`.

`tunisian_ties.csv` is one row per tie: `id_from`, `from`, `edge`, `to`,
`id_to`, where `edge` is `PARENT`, `SIBLING` or `SPOUSE` and the two name
columns are the source's own labels. Parent ties are directed from parent to
child; sibling and spouse ties are written once, deduplicated across the two
directions the export lists them in.

`family_nodes.csv` is one row per surname — `family`, `people`, `marriages`,
`allies`, `endogamous` — and `family_alliances.csv` one row per allied pair,
`family_a`, `family_b`, `marriages`.

## What it kept, and what it dropped

Across twenty well-known Tunisian elite families — Bourguiba, Ben Ali, Mzali,
Nouira, Chenik, Caïd Essebsi, Ghannouchi, Materi, Ben Ammar, Belkhodja,
Khaznadar, Baccouche, Sfar, Zarrouk, Trabelsi, Saied, Mestiri, Lasram,
Djellouli, Ben Achour — all 2,906 rows are kept.

Of the export's largest single lineage cluster, 10,670 people of French and
European descent, 115 are kept: the Tunisians the crawl reached through it,
among them Ahmed Ben Salah and Hamed Karoui, both of whom would have been lost
to a filter that worked cluster by cluster rather than person by person.

Kept, correctly, on Tunisian evidence despite European names: the Italian and
Maltese families of Tunis — Tortorici, Vignale, Mascaro, Spiteri, Muscat,
Miceli, Raffo. Dropped, correctly, on foreign evidence despite Arabic names:
the Egyptian pashas, the Hejaz and Persian courts, the Ottoman and Abkhaz beys.

The kept graph has 23,565 ties — 13,215 parent, 6,234 sibling, 4,116 spouse —
over 14,962 people; the remaining 22,857 are isolated by the truncation. Its largest
connected component holds 4,189 people. The people carry 3,249 distinct
surnames; 20,757 are recorded male, 16,676 female, 386 unrecorded.

## The family network

`rodovid.families` collapses the person-level graph to families. A *couple* is
two people joined by a spouse tie, or two recorded as parents of the same child
— the export sometimes carries the children without the marriage. A couple
whose surnames differ is one *alliance*; a couple sharing a surname is counted
as endogamy and stays off the graph. That yields **3,642 alliances carrying
3,912 marriages between 1,853 families**, against 197 marriages within a
surname.

Surnames are rodovid's own reduction of the name, and a blunt one: `Mohamed
Salah Ben Mrad` reduces to `Mrad`, which is right, but `Ahmed Ben Ali` with no
family name reduces to `Ali`, which makes a "family" out of a patronymic. Nodes
like `Ali`, `Mahmoud`, `Youssef` and `Amor` are aggregates of unrelated people.
The large houses — Bey, Mrad, Cherif, Belkhodja, Darghouth, Miled, Ayed,
Lasram — are not affected.

Three figures, from `rodovid.figures`:

| figure | what |
|---|---|
| `figures/fig01_rodovid_alliances` | all 1,853 families; the thirty widest-married named, and a corona of the 955 that married into the field exactly once |
| `figures/fig02_rodovid_alliance_core` | the 5-core, 236 families, each named where its neighbours leave room. The 6-core is empty, so this is the deepest core the network has |
| `figures/fig03_rodovid_alliance_null` | that core beside a degree-preserving rewiring of itself |

The beylical house is the reason the picture has a centre at all: **`Bey`
marries into 160 different families, 218 marriages**, where the next widest,
`Mrad`, reaches 95. `rodovid.audit` recomputes all of it and exits non-zero if
any of these numbers stops being true, which is why it runs in CI.

What the network is *not* — the reading the figures do not support — is in
[`LIMITATIONS-rodovid.md`](LIMITATIONS-rodovid.md), with the null comparison
that establishes it.

## Putting the marriages in time

The network above has no time in it: a house that married widely in the 1820s
and one that married widely in the 1980s are the same node at the same size.
`rodovid.dynamic` puts the marriages in order.

**Marriages are not dated in the source.** The export carries 22,976 marriage
lines and 16 of them name a year. What the records do carry is birth years —
7,247 of them, 19% of the people — and a kinship graph to carry them along. So
each *person* is dated, and each *couple* is placed by the birth years of the
two spouses.

A couple's `cohort_year` is the mean birth year of the two spouses, and the
period is the 25-year bin holding it. **It is not the wedding date.** The
wedding follows roughly a generation later: the measured parent-child gap in
this dataset is 31 years (IQR 27–36), so a couple in the 1900 bin married
around 1925–1935. Nothing here invents that offset — the panel is indexed by
the generation the spouses belong to, and the figures say so.

A person without a birth year is dated from relatives, one hop at a time, with
every offset measured on this dataset rather than assumed:

| evidence | the year it implies |
|---|---|
| a parent | the parent's year **+ 31** (the measured parent-child gap) |
| a child | the child's year **− 31** |
| a spouse or sibling | the same year (measured gap 4 years, unsigned) |
| nothing, but a death year | the death year **− 75** (the measured median lifespan) |

The median of whatever evidence a person has, in rounds, so someone one hop
from a known year is settled before anyone two hops away. Each estimate records
the hop it came from, and each level has its own measured error in
[`VALIDATION-rodovid-dynamic.md`](VALIDATION-rodovid-dynamic.md) — from MAE 5.6
years at one hop to 14.7 at six. **95% of held-out people land within 25 years
of the truth**, which is one period bin, and that is the resolution anything
here claims.

This dates **18,782 people (50%)** and **3,371 of the 3,912 alliances (86%)**.

### `person_years.csv`

| column | meaning |
|---|---|
| `id`, `fullname`, `surname` | as in `tunisian_individuals.csv` |
| `birth_year` | the year used downstream, observed or estimated |
| `quality` | `observed`, `kin1`, `kin2`, `kin3+`, `death`, `kin_death` — the ordered scale to filter on |
| `hop` | kinship steps from the year that seeded it; 0 for `observed` and `death` |
| `birth_observed`, `death_observed` | what the record itself said, empty where it said nothing |
| `approximate` | the source hedged the date (`vers 1850`, `avant 1900`) |

### `marriages_dated.csv`

One row per couple — spouses, or two people recorded as parents of the same
child, the same definition `rodovid.families` uses.

| column | meaning |
|---|---|
| `id_a`, `id_b`, `name_a`, `name_b` | the two people |
| `family_a`, `family_b` | their surnames, in sorted order; empty where either is a placeholder |
| `cohort_year` | mean birth year of the two spouses |
| `period` | the 25-year bin `cohort_year` falls in |
| `quality` | the *worse* of the two spouses' date qualities |
| `dates_known` | 1 or 2, how many of the couple could be dated |
| `endogamous` | both spouses carry the same surname |
| `on_graph` | two different real families, so the couple is an alliance and carries the panel |

### `alliance_panel.csv`

The dynamic edge list: one row per family pair per period in which they
married. `marriages` is the flow, `marriages_cumulative` the standing weight of
the tie as of that period, `first_period` when the two families first married.
Long format, which is what a networkDynamic object, a Gephi timeline and a
panel regression all want.

### `network_evolution.csv`

One row per period, measured twice. Unprefixed columns are **cumulative** —
every alliance contracted up to and including that period, the right stock for
a relation that does not expire. `w_` columns are **windowed**, only what was
contracted inside the period.

Both are needed. The cumulative series has a mechanical bias that would
otherwise read as a finding: a house present from 1775 accumulates allies for
two centuries while one arriving in 1950 has a single generation, so cumulative
concentration climbs even if no period's marriage market is concentrated at
all. Where a house leads the window as well as the stock, that is the marriage
market rather than the arithmetic.

`clustering` and `centralization` are also given as ratios to two nulls,
because both statistics move with size and density and both move by an order of
magnitude across these periods:

- `_vs_random` — a graph with the same number of families and alliances. This
  controls for size and density, and is what makes the series comparable
  across periods at all.
- `clustering_vs_degree_null` — a rewiring that also keeps every family's exact
  number of allies, the null `rodovid.audit` uses. **This is the strict one**:
  only a value above 1 here is evidence of families marrying in circles.

`window_complete` is 0 for the last two periods, where the flow is cut off by
the calendar rather than by the source: a couple binned at 2000 was born
2000–2024 and marries around 2030.

## What the dated network shows

| | 1775 | 1875 | 1925 | 1975 |
|---|---:|---:|---:|---:|
| families (cumulative) | 57 | 400 | 1,215 | 1,639 |
| in the largest component | 32% | 59% | 94% | 97% |
| closure vs. the degree-preserving null | — | 2.10 | 1.37 | 0.98 |
| concentration vs. random, within the period | 0.4 | 2.5 | 8.7 | 2.2 |
| endogamy rate | 9.5% | 7.8% | 5.3% | 1.5% |

Three things happen, and they are not the same thing:

1. **The field connects.** Through 1850 the alliance network is pockets: a
   third of families in the largest component. By 1925 it is 94% and by 1975
   97%. Within a single generation's marriages the same shift runs from 9% to
   90%. A set of separate marriage circles becomes one field.

2. **Closure appears, then goes.** Against the strict degree-preserving null,
   closure rises clear of 1 only in the 1875 and 1900 cohorts (2.10 and 2.28),
   fades through 1925 (1.37), and from 1950 sits at 1.0. Before 1850 the
   network has no triangles at all — less closed than chance, not more. The
   static build's headline — that the elite marries widely rather than in
   circles, closure 1.00x its null — is the *average* over this, and the dated
   series says the exception is one half-century around the turn of the
   twentieth.

3. **The `Bey` node is more accumulation than dominance.** The beylical house
   tops the cumulative network in all eleven periods, from 16 allied families
   to 158. But it tops the *window* in only five — 1800, 1850, 1875, 1925,
   1950 — and never after 1950, when `Mahjoub`, `Moussa` and `Mrabet` lead
   generations of their own. Concentration within a generation peaks in the
   1925–1950 cohorts, marrying roughly 1950–1980, and falls back to twice
   random after.

Endogamy — marriage inside the surname — falls steadily, from between one
marriage in six and one in ten before 1850 to one in seventy by 1975. Read it
with the
patronymic caveat above: a shrinking rate of same-surname marriage is also what
a growing, better-recorded set of distinct surnames produces.
