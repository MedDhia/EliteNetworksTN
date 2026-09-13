# EliteNetworksTN

A longitudinal, relational dataset of Tunisian bureaucratic elites, built from
the full text of the *Journal Officiel de la République Tunisienne* (JORT),
1957–2026.

The gazette is the state's own record of who holds which office. Every
appointment, board seat, delegation of signature and cessation of functions in
the Tunisian administration is published there, dated, numbered, and signed.
This repository turns seventy years of that record into tables you can put in
a regression, and into networks you can watch change year by year.

**Current build:** 6,378 issues → 117,508 personnel events → 45,634 persons →
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
| `persons.csv.gz` | person register with career summary | 45,634 |
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

## Figures

`figures/` holds nine publication figures, each written as a 300 dpi PNG and a
vector PDF by `python scripts/figures.py`:

| Figure | What it shows |
|---|---|
| `fig01_affiliation_snapshots` | who served where, at four moments |
| `fig02_signature_network` | who signed whose appointment — the patronage structure |
| `fig03_succession_chains` | the six offices with the longest sequence of holders |
| `fig04_coservice_backbone_2011` | the senior co-service network, with its brokers named |
| `fig05_structure_over_time` | size and connectivity of the senior network by year |
| `fig06_appointments_by_rank` | seventy years of appointments by seniority |
| `fig07_cumulative_institution_network` | the whole period at once: institutions tied by shared personnel |
| `fig08_revolution_and_the_apparatus` | what 2011 did, and did not, do to personnel |
| `fig09_bipartite_elite_network` | the two-mode graph itself: people and bodies, and its 2-core |

Colour follows the job it does: a two-slot categorical palette for
person-vs-institution identity, single-hue sequential ramps for seniority and
era, all validated for colour-vision deficiency, chroma and contrast.

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
scripts/        one runnable stage each, plus diagnostics, figures and the explorer export
figures/        nine publication figures, PNG (300 dpi) + vector PDF
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

## A second build: firms, the state, and a curated elite network, 1957–2026

The build described above works from the *Journal Officiel* proper and covers
the bureaucratic state across 1957–2026. A second, separate build sits
alongside it under `data/processed/multiplex/`. It answers a
different question and draws on sources the first build does not touch:

- it starts from a **curated multiplex elite network** of 32,741 ties over
  29,930 nodes — corporate officers and shareholders, cabinets, party organs,
  parliamentary blocs, civil-society bodies, kinship and pedagogical lineage —
  which has no time dimension of its own, and dates it against the gazette;
- it adds the ***annonces légales*** series, the corporate register, which the
  first build does not use at all: 411,940 announcement blocks yielding
  company formations, officer appointments and resignations, share transfers,
  capital changes, dissolutions, and association registrations;
- it is scoped to the **full range the sources support, 1957–2026**, at yearly
  resolution throughout and monthly across 2008–2014, where the January 2011
  rupture is invisible at annual resolution. Widening it from the original
  2008–2012 mattered more than expected: **five of the seed sheet's seven
  governments postdate 2012**, which is why the narrow window could date only
  12.5% of seed ties.

Current build: 9,749 issues → 879,131 blocks → **689,169 dated events** →
13,031 dated person–organisation spells plus 27,585 undated seed ties, 2,314
dated organisation–organisation spells over 2,255 dyads, 37,600 organisation
identifier records and 420,593 act citations. 94% of the hundred
highest-degree seed elites acquire at least one dated event, 81% of the
highest-degree thousand, and 39.4% of all 13,630.

Two of those numbers are worth reading together. Coverage is strongly
correlated with prominence — that is a property of the sources, since the
gazette publishes acts for every registered company while the seed sheet is a
curated elite — and the corporate half of the record does not exist before
2004, so 1957–2003 contributes state appointments and almost no company
filings.

Extraction accuracy on a seeded stratified sample, coded against the printed
French: **precision 0.982** (95% CI 0.937–0.995) with **no spurious events**,
**recall 0.967** (0.886–0.991). Two caveats, and both matter: this is a
self-audit rather than an independent estimate, and it was coded on
**2008–2012 blocks only**, so it is out of the scope of its own evidence for a
1957–2026 dataset. `gold draw --eras` samples across eras instead and reports
per era; until those rows are coded, accuracy outside 2008–2012 is *unmeasured*
rather than good. See `docs/GOLD-SCORE-multiplex.md` and the limitations.

Read `docs/CODEBOOK-multiplex.md` for variable definitions and
`docs/LIMITATIONS-multiplex.md` before using it. For temporal ERGMs,
`make tergm` writes a bipartite network panel with an explicit risk set and
lagged kinship, shareholding and co-membership covariates; read
`docs/TERGM-multiplex.md` first, because right-censoring makes the
dissolution side of such a model uninterpretable here.

`make orgties` builds a second, **one-mode and directed** network of
organisation-to-organisation ties — mostly shareholding, plus audit mandates
and branches — kept apart from the bipartite panel because adding those rows to
it would break every two-mode term silently. The ordinary closure terms
(`triangle`, `gwesp`) are valid there and are not valid on the bipartite panel;
`R/build_org_ownership.R` and `docs/ORG-TIES-multiplex.md` say why, and why the
onsets in that layer are overwhelmingly left-censored.

`make orgattrs` records what the register prints beside a company name: the
matricule fiscal, the registre-de-commerce number and the stated seat. The
identifiers are not only description. A firm has one tax ID, so a node carrying
two is either OCR damage or an **organisation-resolution merge** — which makes
this the only check in the pipeline that can see a merge, since a merge
otherwise looks exactly like a well-corroborated match. See
`docs/ORG-IDENTIFIER-CONFLICTS-multiplex.md`.

`make personties` builds a third layer: **kinship**, one-mode over persons,
read off the `épouse` / `ép.` / `EP` / `veuve` markers the gazette drops into
shareholder and transaction lines. It is separate from the bipartite panel for
the same reason the ownership layer is. Two things to know before using it.
`née X` is a woman's **natal surname**, not a husband, so it is a distinct
relation with `is_marriage = 0` — the validator checks that at ERROR level,
because a `née` read as a marriage invents a man and the resulting tie looks
entirely plausible. And no marriage onset is ever observed: the gazette does
not publish weddings, so every onset is left-censored by construction and a
duration analysis over this layer would be measuring publication frequency.

Coverage beyond the dyad anchor rests on **four labelled inference tiers** —
kinship ties, subsidiaries (`filiale de <firm>`), address corroboration of
organisation identity, and multi-seed snowballing, where what one pass named
becomes the anchor for what it could not. Each is additive over a first pass
left exactly as it was, and each is droppable in one filter:
`resolve_pass == 0` reproduces the single-pass build, `evidence_tier` separates
`gazette_dated` from `gazette_inferred` and `gazette_snowball`, and
`entity_basis` marks an address-corroborated merge. Read
`docs/INFERENCE-TIERS-multiplex.md` for what each rests on and how each can be
wrong — a snowball propagates its own errors, which is why the pass number is
recorded rather than the tier being merged into `resolved`.

`docs/GOLD-FINDINGS-multiplex.md` records the twenty extraction
defects the gold sample exposed, which is also why the figures above supersede
those of the first release.

```bash
make all        # seed -> mirror -> calendar -> segment -> extract -> resolve
                # -> orgentity -> spells -> orgties -> personties
                # -> orgattrs -> export -> tergm -> codebook -> validate
make test
```

Code for this build is `src/elitenet/` (the first build's is `src/eltn/`), and
the two output trees are kept apart so neither overwrites the other. Whether
they should eventually be unified — sharing one person registry and one
organisation registry across 1957–2026 — is an open question, not a settled
design.

---

## A third build: listed companies, shareholders and boards, 1994–2026

The first two builds read the state's record of itself. This one reads the
market's: **the publicly listed companies of the Tunis bourse, who owns them,
and who sits on their boards**, from the filings the Conseil du Marché
Financier requires of every issuer making a public offering.

It is the business half of the same elite structure. A minister recorded in the
gazette and a bank chairman recorded in a registration document are often the
same social stratum and sometimes the same person, but no source covers both,
so they are collected separately and left joinable rather than merged.

Why the CMF filings:

- **the regulator fixes their contents.** A `document de référence` must state
  the capital structure, every shareholder above the disclosure threshold, the
  board, and each director's mandates in other companies. The same tables recur
  in every issuer's filing, which is what makes automated extraction possible;
- **directors declare ties beyond the cote.** The mandates section names
  unlisted companies too, so the network reaches into the private economy that
  no listing-based source sees;
- **movements are dated.** Tender offers and their result notices, capital
  increases, admissions and withdrawals record changes to the day. 400 of them
  are parsed into `movements.csv`, which is what lets ownership be read as
  change rather than as a series of stills;
- **boards are dated too.** Adopted AGM resolutions date every appointment,
  co-optation and renewal to the meeting that took it, and name the departing
  director a co-optation replaces — a handover the source states rather than
  one inferred from consecutive snapshots.

Current build: **213 registration documents, 400 operation notices and 529
adopted-resolution filings → 3,285 entities → 12,604 observed ties across
thirteen layers**, 1994–2026, with 75 entities linked to a BVMT security by
ISIN, plus 400 dated operations, 606 dated board decisions and 29 listing
events. Ownership weights are percentages of capital as reported; interlock
weights are counts of shared directors. Coverage thins sharply before ~2008 —
treat the usable panel as roughly 2008–2026 and check
`data/processed/bourse/layer_year_coverage.csv` before reading any time trend,
because a rise in observed ties can be a rise in filings.

Read [`docs/CODEBOOK-bourse.md`](docs/CODEBOOK-bourse.md) for variable
definitions and [`docs/SOURCES-bourse.md`](docs/SOURCES-bourse.md) for what each
filing type yields. Section 6 of the codebook lists the limitations that matter:
disclosure thresholds truncate ownership, homonyms merge, and carry-forward in
the panel is an assumption rather than an observation.

```bash
make bourse          # spine -> crawl -> resolve -> fetch -> extract -> movements
                     # -> resolutions -> build -> export -> validate
make bourse-test
```

CI (`.github/workflows/ci.yml`) runs the test suite on Python 3.11 and 3.12, and
rebuilds this dataset from the committed extraction records to check that the
committed tables are byte-identical to what the code produces. The data files
are the deliverable here, so a change that silently alters thousands of rows
without touching a test fails the build rather than merging unnoticed.

```r
source("R/load_bourse_multiplex.R")
mx <- load_bourse_multiplex()     # observed ties only
layer_summary(mx)
multiplex_actors(mx, 2024)        # actors present in more than one layer
```

Code is `src/bourse/`, outputs are `data/processed/bourse/`, and source PDFs are
not redistributed: the corpus manifest carries a canonical URL and sha256 per
file, so `make bourse-resolve bourse-fetch` reconstructs it from the CMF's own
servers. As with the second build, the output trees are kept apart; whether the
gazette's person registry and this one should eventually share identifiers is
the same open question, with the same answer — not yet.

---

## A fourth build: a printed biographical dictionary, 1606–1973

The three builds above read institutional records, all of them French-language,
and none reaches back before independence. This one reads a book:
**الصادق الزمالي، أعلام تونسيون** (Sadok Zmerli, *A'lām Tūnisiyyūn*, Dar
al-Gharb al-Islami, Beirut, 2000) — 38 biographical essays on the Tunisian
reform and nationalist elite, from Aziza Othmana (b. 1606) to Muhammad al-Tahir
ibn Ashur (d. 1973).

It adds three things the other builds do not have:

- **the pre-1957 period**, which the gazette cannot reach;
- **Arabic source text**, which required a separate name normaliser — the
  French build's `names.py` uppercases into `[A-Z0-9' ]` and reduces every
  Arabic string to `PERSON_UNKNOWN`;
- **pedagogical lineage** — who studied under whom, and in what. In this
  stratum a man's teachers place him more reliably than his appointments do,
  and the book states those ties explicitly
  («قرأ عليه الفقه والنحو والمنطق والبلاغة»).

The volume has **no text layer**: all 384 pages are bilevel scans, so the build
begins with OCR rather than a download. The scan is not redistributed;
`data/raw/aalam/manifest.csv` carries a sha256 and the exact engine, version
and flags per page, and the OCR'd text is committed so the tables rebuild — and
the provenance guard runs — without an OCR engine installed.

Current build: **384 pages → 455,131 characters → 38 entries → 48 persons,
17 organisations and 33 ties across four layers** (tutelage, office, kinship,
membership).

**Read [`docs/LIMITATIONS-aalam-tunisiyun.md`](docs/LIMITATIONS-aalam-tunisiyun.md)
before using any of it.** In particular: the model pass has so far been run on
**3 of the 38 entries (9.5% of the text)**, so this is a working pipeline rather
than a census of the book's content, and there is **no gold-standard score yet**
— the counts are lower bounds of unknown tightness.

### How it reads narrative prose

Two passes write the same schema.

The **rule pass** matches an Arabic cue table, and is confined to constructions
whose grammar binds the counterparty: after a preposition, or after a
possessive pronoun with no other person named first. The reason is that Arabic
is verb-subject-object — in «ارتقى الأمير مصطفى باي إلى العرش» the name
following the verb is the man ascending, not a counterparty — so a pattern
matched on a bare verb cannot tell a clause's subject from its object. An
earlier version that ignored this made Yusuf Sahib al-Tabi the son of Hammuda
Pasha. Cues marked `vso` are recorded but never emitted.

The **model pass** covers the remainder, and is not trusted. Every assertion
must quote its entry verbatim; `aalam.validate` checks each quote against the
entry text on **every row rather than a sample**, and drops any that is not
literally present. A tie the book does not state has no sentence to quote. The
pass output is committed as a record and everything downstream is
deterministic, so the tables rebuild byte-identically and re-running the model
is a reviewable diff — the arrangement the bourse build already uses.

```bash
make aalam-fetch     # download the scan, verified against a pinned sha256
make aalam-ingest    # OCR 384 pages at native resolution (~6 min)
make aalam           # segment -> extract -> model -> relations -> codebook -> validate
make aalam-test
```

Code is `src/aalam/`, outputs are `data/processed/aalam-tunisiyun/`. See
[`docs/CODEBOOK-aalam-tunisiyun.md`](docs/CODEBOOK-aalam-tunisiyun.md) for
variable definitions. As with the other builds the output trees are kept apart;
whether the gazette's person registry and this one should share identifiers is
the same open question, with the same answer — not yet. The `name_translit`
column exists so the two can be joined by eye in the meantime.
