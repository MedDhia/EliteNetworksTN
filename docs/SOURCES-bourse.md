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
| Rapports annuels des sociétés | `rapport_annuel` | Company annual reports. |
| Convocations des assemblées | `convocation_ag` | AGM agendas; signal pending board or capital changes. |
| Prospectus visés | `prospectus` | Pre-IPO ownership structure. |
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
