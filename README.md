# EliteNetworksTN

A longitudinal, relational dataset of Tunisian bureaucratic elites, built from
the full text of the *Journal Officiel de la République Tunisienne* (JORT),
1957–2026.

The gazette is the state's own record of who holds which office. Every
appointment, board seat, delegation of signature and cessation of functions in
the Tunisian administration is published there, dated, numbered, and signed.
This repository turns seventy years of that record into tables you can put in
a regression, and into networks you can watch change year by year.

**Current build:** 6,378 issues → 117,508 personnel events → 44,271 persons →
99,872 office-holding spells and six dated relational structures. See
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
| `events.csv.gz` | one person–office transition | 117,508 |
| `spells.csv.gz` | one office-holding spell, with start, end and end reason | 99,872 |
| `person_year.csv.gz` | person × year panel | 1,301,001 |
| `persons.csv.gz` | person register with career summary | 44,271 |
| `organisations.csv.gz` | organisation register | 8,803 |
| `edges/*.csv.gz` | six relations, each with validity intervals | see below |
| `graphs/affiliation_senior_dynamic.gexf` | dynamic bipartite graph for Gephi, senior offices | |

### The six relations

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

## The explorer

`explorer/` is a self-contained page that replays the senior network year by
year: a bipartite map of officeholders and the institutions they served,
scrubbed across 1957–2026, with succession and signature ties as overlays and
a dossier panel that cites the decree behind every post and links to the page
of the gazette it was printed on.

Rebuild its payload from the processed tables with:

```bash
python scripts/export_explorer.py   # writes explorer/data.js
```

It covers offices at `rank_score >= 72` (cabinet adviser and above) so the
graph stays legible; change `RANK_CUT` in the script to widen it.

## Repository layout

```
src/eltn/
  harvest.py    catalogue + cached download of the OCR corpus
  textnorm.py   OCR cleaning, page provenance, summary-page detection
  dates.py      French gazette date parsing, tolerant of OCR damage
  extract.py    act segmentation and personnel-event extraction
  normalize.py  person / organisation / position resolution
  panel.py      spells, person-year panel, registers
  network.py    the six relations, snapshots, GEXF export
scripts/        one runnable stage each, plus diagnostics and the explorer export
explorer/       self-contained year-by-year network explorer (index.html + data.js)
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

---

## A second build: firms, the state, and a curated elite network, 2008–2012

The build described above works from the *Journal Officiel* proper and covers
the bureaucratic state across 1957–2026. A second, separate build sits
alongside it under `data/processed/multiplex-2008-2012/`. It answers a
different question and draws on sources the first build does not touch:

- it starts from a **curated multiplex elite network** of 32,741 ties over
  29,930 nodes — corporate officers and shareholders, cabinets, party organs,
  parliamentary blocs, civil-society bodies, kinship and pedagogical lineage —
  which has no time dimension of its own, and dates it against the gazette;
- it adds the ***annonces légales*** series, the corporate register, which the
  first build does not use at all: 172,054 announcement blocks yielding
  company formations, officer appointments and resignations, share transfers,
  capital changes, dissolutions, and association registrations;
- it is scoped to **2008–2012**, straddling the January 2011 rupture, at both
  yearly and monthly resolution.

Current build: 1,271 issues → 207,369 blocks → 197,532 dated events → 4,287
dated tie spells plus 27,585 undated seed ties, and 48,176 act citations.
87% of the hundred highest-degree seed elites acquire at least one dated event.

Extraction accuracy on a seeded stratified sample, coded against the printed
French: **precision 0.982** (95% CI 0.937–0.995) with **no spurious events**,
**recall 0.967** (0.886–0.991). This is a self-audit, not an independent
estimate — see `docs/GOLD-SCORE-multiplex-2008-2012.md` and the limitations.

Read `docs/CODEBOOK-multiplex-2008-2012.md` for variable definitions and
`docs/LIMITATIONS-multiplex-2008-2012.md` before using it.
`docs/GOLD-FINDINGS-multiplex-2008-2012.md` records the twenty extraction
defects the gold sample exposed, which is also why the figures above supersede
those of the first release.

```bash
make all        # seed -> mirror -> calendar -> segment -> extract -> resolve
                # -> spells -> export -> codebook -> validate
make test
```

Code for this build is `src/elitenet/` (the first build's is `src/eltn/`), and
the two output trees are kept apart so neither overwrites the other. Whether
they should eventually be unified — sharing one person registry and one
organisation registry across 1957–2026 — is an open question, not a settled
design.
