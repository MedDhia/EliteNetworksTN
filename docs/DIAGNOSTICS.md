# Diagnostics

## Scale

- issues catalogued: **6,378** (French *journal-officiel*, 1957–2026)
- events: **117,508**
- persons: **45,634**
- organisations: **8,803**
- spells: **100,582**

## Yield by decade

`events_per_issue` is the figure to watch across extraction changes. The rise over time is partly real administrative growth and partly better scans; do not read it as a measure of state activity.

|   decade |   issues |   events |   events_per_issue |   persons |   orgs |
|---------:|---------:|---------:|-------------------:|----------:|-------:|
|     1950 |      198 |      781 |                3.9 |       698 |    153 |
|     1960 |      597 |     2832 |                4.7 |      2292 |    527 |
|     1970 |      717 |     6261 |                8.7 |      4573 |    911 |
|     1980 |      846 |    11061 |               13.1 |      6805 |   1197 |
|     1990 |      989 |    18252 |               18.5 |     10075 |   1930 |
|     2000 |     1044 |    20861 |               20   |     12111 |   2345 |
|     2010 |     1040 |    38488 |               37   |     20698 |   3426 |
|     2020 |      947 |    18972 |               20   |     11471 |   2298 |

## Composition

**event_type**

| event_type   |      n |    % |
|:-------------|-------:|-----:|
| appointment  | 100806 | 85.8 |
| board        |   8663 |  7.4 |
| termination  |   3628 |  3.1 |
| delegation   |   2067 |  1.8 |
| transfer     |   2046 |  1.7 |
| renewal      |    286 |  0.2 |
| retirement   |     12 |  0   |

**source_layer**

| source_layer   |     n |    % |
|:---------------|------:|-----:|
| dispositif     | 98585 | 83.9 |
| list           |  9963 |  8.5 |
| recital        |  8858 |  7.5 |
| title          |   102 |  0.1 |

**act_kind**

| act_kind   |     n |    % |
|:-----------|------:|-----:|
| decret     | 67242 | 57.2 |
| arrete     | 49930 | 42.5 |
| decision   |   334 |  0.3 |
| loi        |     2 |  0   |

**org_source**

| org_source   |     n |    % |
|:-------------|------:|-----:|
| text         | 77014 | 65.5 |
| heading      | 39779 | 33.9 |
| none         |   715 |  0.6 |

**position_rank** (top 12)

| rank               |     n |
|:-------------------|------:|
| autre              | 28977 |
| chef_service       | 26901 |
| directeur          | 14250 |
| sous_directeur     | 10603 |
| administrateur_ca  | 10594 |
| cadre              |  5115 |
| directeur_general  |  3657 |
| secretaire_general |  3554 |
| conseiller_pol     |  3504 |
| academique         |  1804 |
| local              |  1271 |
| ministre           |   963 |

## Field completeness

| field                                    |      n |    % |
|:-----------------------------------------|-------:|-----:|
| act_date parsed                          | 110910 | 94.4 |
| effect_date distinct from act_date       |  28046 | 23.9 |
| organisation named in the act text       |  77014 | 65.5 |
| position non-empty                       | 114489 | 97.4 |
| predecessor named ('en remplacement de') |   7084 |  6   |
| signatory identified                     |   7734 |  6.6 |

## Spell closure

The share ending `censored` is a property of the gazette, not of the pipeline: entries into office must be published, exits often need not be.

| end_reason   |     n |    % |
|:-------------|------:|-----:|
| moved        | 44655 | 44.4 |
| censored     | 41923 | 41.7 |
| displaced    |  8657 |  8.6 |
| succeeded    |  3264 |  3.2 |
| termination  |  2079 |  2.1 |
| retirement   |     4 |  0   |

Median observed tenure: **1137 days** (3.1 years); mean 1612 days.

## Entity resolution

- distinct name strings resolved: **66,037**
- persons: **45,634**
- persons with >1 surface spelling: **11,850**
- **suspect ids** (career span > 45 years or > 12 organisations): **596** (1.31%) — likely homonym merges, screen these before analysis

| name             |   first_year |   last_year |   n_orgs |   n_events |
|:-----------------|-------------:|------------:|---------:|-----------:|
| Ali Larayedh     |         1993 |        2013 |       18 |         86 |
| Mohamed Saâd     |         1960 |        2024 |       35 |         65 |
| Mohamed Trabelsi |         1973 |        2025 |       36 |         62 |
| Ahmed Souibgui   |         1990 |        2025 |       25 |         60 |
| Mohamed Manai    |         1985 |        2026 |       24 |         56 |
| Habib Essid      |         1980 |        2023 |       34 |         53 |
| Mohamed Ben Amor |         1972 |        2026 |       34 |         53 |
| Ali Amira        |         1977 |        2025 |       28 |         53 |

## Recall proxy: segmented acts that yielded no event

Sampled issues are re-parsed and every act counted. An act with a personnel keyword in its heading but no extracted event is a candidate miss; sampling from that set and reading the PDF is how the next extraction rule gets found.

- sampled issues: **120** (of which Arabic-only scans: 3)
- acts segmented: **4,305**
- acts yielding no event: **2,076** (48.2%) — most are regulatory, not personnel
- acts under a personnel heading yet yielding nothing: **310** (7.20% of acts)

Examples to inspect:

- `journal-officiel/fr/2003/045` — Arrêté du ministre de l'enseignement supérieur, de la recherche scientifique et de la technologie du 30 mai 2003, fixant les modalités d'organisation …
- `journal-officiel/fr/2003/045` — Arrêté du ministre de l'enseignement supérieur, de la recherche scientifique et de la technologie du 31 mai 2003, portant ouverture d'un concours exte…
- `journal-officiel/fr/2003/045` — Arrêté du ministre de l'enseignement supérieur, de la recherche scientifique et de la technologie du 31 mai 2003, portant ouverture d'un concours inte…
- `journal-officiel/fr/2003/045` — Arrêté du ministre de l'enseignement supérieur, de la recherche scientifique et de la technologie du 31 mai 2003, portant ouverture d'un concours exte…
- `journal-officiel/fr/2003/045` — Arrêté du ministre de l'enseignement supérieur, de la recherche scientifique et de la technologie du 31 mai 2003, portant ouverture d'un concours inte…
- `journal-officiel/fr/2003/045` — Arrêté du ministre de l'enseignement supérieur, de la recherche scientifique et de la technologie du 31 mai 2003, portant ouverture d'un concours exte…
- `journal-officiel/fr/2003/045` — Arrêté du ministre de l'enseignement supérieur, de la recherche scientifique et de la technologie du 31 mai 2003, portant ouverture d'un concours inte…
- `journal-officiel/fr/2003/045` — Arrêté du ministre de l'enseignement supérieur, de la recherche scientifique et de la technologie du 30 mai 2003, portant ouverture d'un examen profes…

