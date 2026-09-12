# EliteNetworksTN

A longitudinal, relational dataset of Tunisian bureaucratic elites, built from
the full text of the *Journal Officiel de la République Tunisienne* (JORT),
1957–2026.

The gazette is the state's own record of who holds which office. Every
appointment, board seat, delegation of signature and cessation of functions in
the Tunisian administration is published there, dated, numbered, and signed.
This repository turns seventy years of that record into tables you can put in
a regression, and into networks you can watch change year by year.

**Current build:** 6,378 issues → 123,387 personnel events → 43,406 persons →
office-holding spells and five dated relational structures. See
[`docs/CODEBOOK.md`](docs/CODEBOOK.md) for variable definitions and
[`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) before you use it in a paper.

---

## Why the gazette

Elite-network research on authoritarian and post-authoritarian regimes
normally works from biographical dictionaries, press coverage, or a
hand-collected roster of the top few hundred officials. Those sources are
thin below cabinet level, they are assembled retrospectively, and they encode
the compiler's judgement about who counts as an elite.

The JORT has none of those problems and one big advantage: it is *contemporaneous
and exhaustive by construction*. An appointment is not legally effective until
it is published. That gives:

- **depth** — the ministry section chief and the hospital director are recorded
  on the same terms as the minister, so the administrative middle is visible;
- **exact timing** — acts are dated to the day, and most name a separate
  effective date, which is what makes survival and event-history designs
  possible;
- **explicit relations** — the text names the outgoing incumbent
  (*"en remplacement de M. X"*), the signing authority, and the delegating
  principal. Those are ties stated by the source, not inferred by the analyst.

## Data source

Everything comes from [jort.tn](https://jort.tn), an independent digital mirror
of the Imprimerie Officielle archive, via its documented API
([docs.jort.tn](https://docs.jort.tn)):

| Endpoint | Use |
|---|---|
| `index.jort.tn/issues` | which issues exist per collection/language/year |
| `ocr.jort.tn/{collection}/{lang}/{year}/{issue}.md` | OCR'd full text |
| `lake.jort.tn/…/{issue}.pdf` | original PDF, for verifying any row |

This pipeline uses the **French edition of the `journal-officiel` collection**,
the only one upstream has OCR'd. Read
[`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) on what that implies — since 1993
only the Arabic edition is legally authoritative.

## Quick start

```bash
pip install -r requirements.txt

python scripts/harvest.py     # ~4 min, ~780 MB of text into data/raw/ (gitignored)
python scripts/extract.py 4   # ~40 s, writes data/interim/events_raw.csv
python scripts/build.py       # ~4 min, writes data/processed/
python scripts/diagnostics.py # coverage and quality report
pytest                        # gold-standard tests on hand-coded acts
```

Every stage is cached and idempotent: re-running `harvest.py` only fetches what
is missing, and the extractor always reads from the local mirror, so the whole
dataset rebuilds offline once harvested.

## What you get

`data/processed/`

All tables are gzipped CSV — `pandas.read_csv` and R's `read.csv` open them
directly, no unpacking step.

| File | Grain | Rows |
|---|---|---|
| `events.csv.gz` | one person–office transition | 115,980 |
| `spells.csv.gz` | one office-holding spell, with start, end and end reason | 104,077 |
| `person_year.csv.gz` | person × year panel | 1,317,827 |
| `persons.csv.gz` | person register with career summary | 43,406 |
| `organisations.csv.gz` | organisation register | 8,474 |
| `edges/*.csv.gz` | six relations, each with validity intervals | see below |
| `graphs/affiliation_senior_dynamic.gexf` | dynamic bipartite graph for Gephi, senior offices | |

### The five relations

Each edge carries the interval over which it is valid, so the network can be
replayed rather than collapsed:

| Relation | Direction | Tie | Interval |
|---|---|---|---|
| `affiliation` | person → organisation | held an office there | the spell |
| `colleague` | person – person | overlapping spells in one organisation | the overlap |
| `succession` | outgoing → incoming | named as replaced in the successor's act | handover date |
| `signature` | signatory → appointee | signed the appointing act | act date |
| `delegation` | principal → agent | delegated signature authority | act date |
| `coappointment` | person – person | named by the same act on the same day | act date |

`succession` and `signature` are the analytically distinctive ones. Succession
chains give you the *office* as a durable unit with a sequence of holders —
tenure, turnover, and whether an office is a stepping stone or a graveyard.
Signature ties give you the patronage direction the source itself asserts: who
had the authority to place whom.

### Using it

```python
import pandas as pd, networkx as nx

py = pd.read_csv("data/processed/person_year.csv.gz")
coll = pd.read_csv("data/processed/edges/colleague.csv.gz",
                   parse_dates=["start_date", "end_date"])

# the co-affiliation network as it stood in 1987
year = 1987
active = coll[(coll.start_year <= year) & (coll.end_year >= year)]
g = nx.from_pandas_edgelist(active, "source", "target", edge_attr="overlap_days")
```

For Gephi, open `graphs/affiliation_senior_dynamic.gexf` and enable the timeline; edge
spells are stored as `start`/`end` years.

## Repository layout

```
src/eltn/
  harvest.py    catalogue + cached download of the OCR corpus
  textnorm.py   OCR cleaning, page provenance, summary-page detection
  dates.py      French gazette date parsing, tolerant of OCR damage
  extract.py    act segmentation and personnel-event extraction
  normalize.py  person / organisation / position resolution
  panel.py      spells, person-year panel, registers
  network.py    the five relations, snapshots, GEXF export
scripts/        one runnable stage each, plus diagnostics
tests/          gold-standard acts transcribed by hand from the gazette
docs/           codebook and limitations
```

## Extending it

The pieces most likely to need work for a specific project:

- **`RANK_SCALE` in `normalize.py`** — the ordered position hierarchy. If your
  argument turns on a distinction the current scale collapses (say, cabinet
  *directeur* vs. line *directeur*), add the tier there and rebuild.
- **`MINISTRY_DOMAINS`** — ministries are identified by policy portfolio so
  they stay comparable across renamings. Adjust if your period splits a
  portfolio differently.
- **Arabic** — when upstream OCRs the Arabic edition, `harvest.py` already
  accepts `lang="ar"`; the extractor's patterns would need Arabic equivalents.

## Licence and citation

Code in this repository is offered for research use. The underlying gazette
text is a public record of the Tunisian state, mirrored by jort.tn; cite the
JORT issue and page (every row carries `issue_key`, `page` and `pdf_url`) rather
than this repository when quoting the source.
