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
90% of the hundred highest-degree seed elites acquire at least one dated event.

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
make bourse-verify   # re-read the filings; check each record against its page
```

`make bourse-verify` is the check the rest of the suite cannot do. Every other
check tests the dataset against itself, and a figure read off the wrong row
passes all of them, because a misread figure is still internally consistent.
This one re-opens each source PDF, accepts it only if the bytes hash to the
digest recorded in the corpus manifest, and asks of every record whether its
name and its figure appear on the page it cites. The current pass confirms
**100.0% of 7,593 names and 99.9% of figures** across 179 filings; the result
is written to `data/processed/bourse/source_verification.md`, which names every
record that did not confirm. Running it is what turned up the four extraction
defects recorded in §6.1 of the codebook.

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

Current build: **384 pages → 455,131 characters → all 38 entries → 242 persons,
366 organisations and 873 ties across four layers** (tutelage, office, kinship,
membership). 28 of the 38 subjects are tied to at least one other subject, and
the institutions that bind them are legible: Zaytuna (10 subjects), the Sadiqi
college (8), the newspaper *al-Hadira* (7), the Khaldouniyya and the Young
Tunisians (6 each).

**Read [`docs/LIMITATIONS-aalam-tunisiyun.md`](docs/LIMITATIONS-aalam-tunisiyun.md)
before using any of it.** In particular: the gold sample is coded —
**precision 0.907** (95% CI 0.860–0.940) and **recall 0.672** (0.550–0.774) on
206 ties and 60 passages — but it is a **self-audit**, drawn and coded by the
same system that wrote the extractors, so the layer-by-layer comparisons hold
and the headline numbers are not citable. Tutelage is the weakest layer at
0.821, and it is the layer this build exists for; 709 of the 873 ties carry no
date, because a biography states that a relation existed far more often than it
says when; and 866 of 873 ties come from the model pass rather than the rule
table, for the reason given below.

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

The **model pass** covers the remainder, and carries almost the whole dataset.
It is not trusted. Every assertion must quote its entry verbatim;
`aalam.validate` checks each quote against the entry text on **every row rather
than a sample**, and drops any that is not literally present. A tie the book
does not state has no sentence to quote. The pass output is committed as a
record and everything downstream is deterministic, so the tables rebuild
byte-identically and re-running the model is a reviewable diff — the
arrangement the bourse build already uses.

That gate catches invention but not misreading, and the difference is not
academic. The book names what a man read by listing its authors
(«والغزالي وابن رشد، قد استأثروا بعنايته»), which read as a teaching tie makes
a scholar dead in 1198 the teacher of a man born in 1871. Ten such ties got
through, 12% of the tutelage layer at the time, every quote genuine. They are
now reclassified to `read_work_of`, flagged for review, and a validation check
fails the build if one survives. The class was found by reading twelve rows at
random, which is the honest measure of how much else may be there.

### Reading it without Arabic

Every name in the volume is Arabic script, and the column that looks like the
Latin one is not: `name_translit` is a vowel-less consonant skeleton built to
generate identifiers, so `سالم بو حاجب` comes out `SALM BW HAJB`. Arabic does
not write short vowels, and nothing recovers `Salem` from that.

`python -m aalam.romanise` therefore writes two supplied columns on every
table. **`name_fr`** is Tunisian French orthography (Mohamed Tahar Ben Achour,
Bechir Sfar), which is how these people are spelled in Tunisian archives and
what joins this build to the gazette build, whose 45,634 persons and 8,803
organisations are all named in French. **`name_ijmes`** is the Middle East
studies convention without diacritics (Muhammad al-Tahir Ibn Ashur). The edge
tables carry both on both ends.

Neither translates: a newspaper called جريدة الحاضرة is `al-Hadira`, never
"The Metropolis". Where a row is a common-noun post rather than a name
(`وزير الداخلية`) it is translated instead, and `gloss_mode` says so, because
reading `Minister of the Interior` as somebody's name is the error the column
exists to prevent.

**Every gloss is gated.** A Latin form is reduced to its consonants and
compared with the same reduction of the Arabic, on every row rather than a
sample — the counterpart of the verbatim-quote gate on the extraction passes.
It refuses `مصطفى آغة` glossed as Mustapha Radhouane, which is the exact
homonym merge the gold coding caught. It cannot see a vowel: `Salim` and
`Salem` are one spine, because the Arabic never recorded the difference. So
`gloss_tier` marks the 112 rows a reader actually meets, which were checked by
hand, apart from the tail, which was not. See
[`docs/LIMITATIONS-aalam-tunisiyun.md`](docs/LIMITATIONS-aalam-tunisiyun.md)
§10.

`evidence_quote` stays Arabic. It is the verbatim gate, and a translated quote
proves nothing about the page.

### Figures

`python scripts/figures_aalam.py` writes four figures into `figures/` in two
editions, one labelled in Arabic and one in Latin, each a 300 dpi PNG and a
vector PDF, in the house style shared with the gazette build
(`scripts/house_style.py`). The Latin plates take the `_en` suffix and come
from the same four functions, so the two editions cannot drift apart:

| Figure | What it shows |
|---|---|
| `fig01_aalam_two_mode` | the institutions that tie three or more of the 38 together, and who passed through them |
| `fig02_aalam_tutelage` | the largest chain of teacher-pupil ties, drawn teacher to pupil |
| `fig03_aalam_subject_backbone` | the 46 pairs of subjects the book joins, by layer |
| `fig04_aalam_lives` | the 37 datable life spans, grouped by the author's three cohorts |

Arabic labels are passed **raw**. This matplotlib shapes and orders Arabic
itself, so putting a string through `arabic-reshaper` and `python-bidi` first —
the usual advice — processes it twice and silently produces reversed, disjoint
text that still looks like Arabic to anyone who cannot read it.

```bash
make aalam-fetch       # download the scan, verified against a pinned sha256
make aalam-ingest      # OCR 384 pages at native resolution (~6 min)
make aalam             # segment -> extract -> model -> relations -> codebook -> validate
make aalam-gold-draw   # seeded stratified sample -> coding sheets in gold/
make aalam-gold-score  # coded sheets -> precision/recall with Wilson intervals
make aalam-test
```

The gold pass is two sheets because precision and recall are not answerable
from the same unit. Precision is judged per tie, stratified by layer and by
extractor so the rule pass and the model pass are scored apart. Recall is
judged per passage: a tie the extractor never found is not in the table to be
sampled, so a coder reads paragraphs of the book and counts what they state
against what came back.

Code is `src/aalam/`, outputs are `data/processed/aalam-tunisiyun/`. See
[`docs/CODEBOOK-aalam-tunisiyun.md`](docs/CODEBOOK-aalam-tunisiyun.md) for
variable definitions. As with the other builds the output trees are kept apart;
whether the gazette's person registry and this one should share identifiers is
the same open question, with the same answer — not yet. The `name_translit`
column exists so the two can be joined by eye in the meantime.
