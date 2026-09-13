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
| `make rodovid-figures` | `rodovid.figures` | the three plates in `figures/` (~6 min, needs matplotlib) |

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
