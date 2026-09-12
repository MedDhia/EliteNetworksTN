# Sources — bourse component

Everything in this dataset comes from two public Tunisian institutions. No
commercial database is used, and nothing is hand-entered.

## Bourse des Valeurs Mobilières de Tunis (BVMT)

* **What**: the roster of securities on the cote — ISIN, ticker, French and
  Arabic names, trading group, last price, market capitalisation.
* **Endpoint**: `https://www.bvmt.com.tn/rest_api/rest/market/groups/11,12,52,99`
* **Role**: the firm identity spine. Provides ISIN, which is the stable key for
  linking to any outside financial source.
* **Limitation**: a snapshot of the *current* cote. It carries no listing
  history, so delisted firms are absent. Each retrieval is archived to
  `data/raw/bvmt_roster_<date>.json`.

Trading groups: `11` continuous, `12` fixing, `52` alternative market,
`99` suspended or under a special regime.

## Conseil du Marché Financier (CMF)

The securities regulator. Every company making a public offering ("faisant appel
public à l'épargne") files with it, and the filings are published openly.

* **Base**: `https://www.cmf.tn/?q=<section>`, paginated with `&page=N`.
* **Sections crawled**: see `config/bourse_sources.yaml`.

### Which filing carries what

| Section | `doc_type` | What it yields |
|---|---|---|
| Documents de référence | `document_de_reference` | **The core source.** Capital structure, named blockholders, board membership, cross-directorships, group participations. |
| Offres publiques | `offre_publique` | Tender (OPA), simplified (OPAS), withdrawal (OPR) and fixed-price (OPF) offers. Ownership movements, and firm entry/exit from the cote. |
| Autres opérations sur capital | `operation_sur_capital` | Threshold-crossing declarations — the cleanest dated record of stake changes. |
| Augmentations de capital réalisées | `augmentation_de_capital` | Completed capital increases; dilution events. |
| Résolutions adoptées | `resolutions_ag` | Adopted AGM resolutions; dated board appointments and renewals. |
| Rapports annuels des sociétés | `rapport_annuel` | **The second core source.** Board membership and blockholder tables for the many issuers that never file a registration document. |
| Prospectus visés | `prospectus` | **The third core source, and the only one that reaches back before 2005.** Capital structure, shareholders and board composition at the time of an issue. 675 filings, 1989–2026. |
| Convocations des assemblées | `convocation_ag` | AGM agendas; signal pending board or capital changes. |
| Communiqués des sociétés | `communique_societe` | Company press releases filed with the regulator. |
| Visas accordés (capital) | `visa_capital` | Regulatory approvals for equity operations. |

### Why registration documents are the backbone

CMF regulation fixes the *contents* of a `document de référence`, so the same
tables appear in every issuer's filing:

| Section | Table | Becomes |
|---|---|---|
| §2.4.1 | Structure du capital | Aggregate resident/foreign, legal/natural-person split |
| §2.4.2 | Actionnaires détenant 3% et plus | `ownership` layer |
| §2.4.3 | Participations des dirigeants | `ownership_director` layer |
| §2.5.1 | Sociétés du groupe | `group_participation` layer |
| §5.1.1 | Membres du Conseil d'administration | `board_seat`, `board_seat_corporate` |
| §5.1.3 | Activités exercées en dehors | `declared_executive` layer |
| §5.1.5 | Mandats dans d'autres sociétés | `declared_mandate` layer |

Section *numbering* drifts between issuers and years, so the extractor keys on
table headers and binds each table to the heading printed directly above it,
rather than trusting the numbering. See `src/bourse/extract/tables.py`.

### Annual reports

Registration documents are the richest filings but the rarest: 213 of them
cover a handful of issuers. Annual reports are filed by many more companies,
and carry the same two tables the network needs — the board membership list and
the list of shareholders above a disclosure threshold. They are parsed with the
same extractor, because that extractor already keys on table *headers* rather
than on section numbering.

Two things about them are not obvious and both are handled in code:

1. **A report is filed the year after the year it reports on.** Dating a row by
   its filing date would shift every annual-report observation forward by one
   year and put it out of step with the registration-document rows.
   `pipeline.detect_report_year()` reads the covered year out of the document
   text ("exercice clos le 31 décembre 2019", "au 31/12/2019") or, failing that,
   out of the file name, and `build_dataset._year()` prefers it over the filing
   date.
2. **Older reports are scanned paper.** The CMF's archive of annual reports is
   not digital-native throughout. Reports for the older financial years are page
   images with no text layer at all, so `pdfplumber` returns nothing from them —
   not a garbled approximation, nothing. Filing becomes born-digital across
   2016–2018. This is a property of the archive, not of the parser, and it is
   why the corpus is read by OCR as well; see *Reading the scanned third of the
   archive* below.

   **Take the reporting year from the file name, not from the text.** The CMF
   names these files with the year (`rapport_annuel_stb_2005.pdf`), and that is
   the only year a scanned report will give you before it is OCR'd. Counting
   financial years from extracted text instead makes the scanned years look
   empty — which is a statement about the text layer, not about what the
   regulator published.

   1,027 reports are held, covering financial years 2004–2025 continuously.

### Prospectuses: the only source that reaches the 1990s

A `prospectus` is filed when a company raises capital or comes to the market,
and the CMF has published them since 1989. They are the only filing type in the
archive with real depth before 2005, and they are dense where it matters: an
issue prospectus states the capital structure, the shareholders above the
disclosure threshold, and the board, because a buyer needs to know who controls
the company.

675 of them are held, and their distribution is almost the mirror image of the
registration documents — 233 filings from 1989–2002, and 142 across 2012–2017,
the years the adopted-resolutions section leaves empty. They go through the same
table extractor.

They are a *snapshot at the moment of an issue*, not an annual return, so the
firms they cover are the firms raising money that year. That is a selection
worth stating plainly: a prospectus-derived observation means the company was
in the market, which is not a random sample of the cote.

### Reading the scanned third of the archive

About a third of the corpus was scanned from paper rather than filed digitally,
and carries no text layer at all: `pdfplumber` returns nothing, not a garbled
approximation of something. These are concentrated exactly where the digital
coverage is weakest — every annual report for FY2004–2011, and most of the older
prospectuses — so ignoring them would mean the dataset thins out before 2012 for
a reason that has nothing to do with Tunisian corporate life.

`src/bourse/extract/ocr.py` reads them with Tesseract's French model and hands
the result to the ordinary table extractor. The design point is that it is the
*same* extractor: OCR produces word boxes, the extractor already knows how to
rebuild a borderless table from word positions, so every classification and
row-parsing rule applies unchanged and an OCR'd table is held to the same
standard as a digital one. Three things make that work:

* **Coordinates are converted back to PDF points.** Every threshold in the
  extractor — the line-bucket height, the minimum column gap — is calibrated in
  points. At 300 dpi, raw pixel coordinates would split each printed line into
  four, tearing every row away from its own figures.
* **Words are snapped to their printed line.** Tesseract reports each word's own
  glyph box, so a word with no ascender ("M.", "au", "par") sits a point or two
  off its neighbours and buckets as a separate line. Tesseract already knows
  which words share a line; that grouping is used rather than guessed at.
* **Tables are found from their headings.** Scanned filings do not number their
  sections; they set titles in capitals, and frequently print no column header
  at all. So the OCR path classifies from the heading — "LE CONSEIL
  D'ADMINISTRATION", "STRUCTURE DU CAPITAL" — and takes the region beneath it.

Two limits are deliberate. `capital_structure` is not read from scanned pages:
its parser maps columns by fixed position, and a scanned table that omits the
shareholder-count column would have its share figures read out of the percentage
column. And OCR spellings are never corrected — "Abdeikader" for "Abdelkader"
stays as it is, surfacing as an unmatched entity a human can see, rather than
being silently merged into a real person.

Every row read this way carries `from_ocr = 1`, through the records and onto the
edge list, so an analyst can weight or exclude the scanned part of the archive
without rejoining anything. **OCR is not in the default `make bourse` chain**:
it needs `tesseract-ocr` and `tesseract-ocr-fra` installed and takes hours. Run
`make bourse-ocr` explicitly.

## Provenance guarantees

* Every extracted row carries `doc_node_key`, `doc_url`, `page` and
  `doc_sha256`.
* `data/processed/bourse/corpus/cmf_registry.jsonl.gz` is the filing manifest (title, date, node
  URL, PDF URLs).
* `data/processed/bourse/corpus/pdf_manifest.jsonl.gz` records each retrieved file's byte length
  and SHA-256, so a silent re-publication at the same URL is detectable.

## Redistribution

Source PDFs are **not** committed (`data/raw/bourse/cmf_pdfs/` is git-ignored). The
registry stores canonical URLs and hashes, so `make bourse-resolve bourse-fetch` reconstructs
the corpus from the CMF's own servers. Cite the CMF as the source of the
underlying documents.

## Crawling conduct

`Fetcher` enforces a randomised minimum delay (default ~1s) with exponential
backoff, runs single-threaded, and identifies itself in the User-Agent. Please
do not lower the delay: the CMF is a small public institution.

## Sources — bourse component deliberately not used

* **ilboursa.com** — returns HTTP 403 to non-browser clients; its data is
  secondary reporting rather than a primary filing.
* **Commercial registry (RNE)** — would give unlisted-firm ownership and
  directors, which would substantially deepen the elite network, but it is not
  openly queryable. A promising extension if institutional access exists.
* **Price history** — the BVMT API exposes no historical endpoint. Market
  capitalisation over time would need a separate source.
