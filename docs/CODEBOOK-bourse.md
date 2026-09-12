# Codebook — bourse component (listed companies, 1994–2026)

Variable-level documentation for the Tunisian listed-firm multiplex dataset.
Every table lives in `data/processed/bourse/`.

---

## 1. `entities.csv` — the node list

One row per distinct actor, whether or not it is listed. Nodes are shared across
all layers and all years, which is what makes the series a longitudinal multiplex
rather than a stack of unrelated graphs.

| Variable | Type | Description |
|---|---|---|
| `entity_id` | string | Canonical ID. First character encodes type (`F` firm, `P` person, `U` fund/vehicle, `S` state body, `A` aggregate, `X` unknown), followed by a hash of the matching key. **Stable across rebuilds**: the same inputs always produce the same ID. |
| `entity_type` | factor | `person`, `firm`, `fund`, `state`, `aggregate`, `unknown`. See §5 on how this is assigned. |
| `canonical_name` | string | Most frequently observed spelling. Honorifics are stripped for persons. |
| `is_bvmt_listed` | 0/1 | Matched to a security on the BVMT cote **as observed at the roster snapshot date**. Not a listing history — see §6. |
| `isin` | string | ISIN, if listed. |
| `ticker` | string | BVMT ticker, if listed. |
| `name_ar` | string | Arabic name from the BVMT referential, if listed. |
| `bvmt_group_label` | factor | `continuous`, `fixing`, `alternative`, `suspended_other`. |
| `n_aliases` | int | Distinct spellings merged into this entity. Values > 1 are worth spot-checking. |
| `aliases` | string | All observed spellings, ` | `-separated. |

## 2. `entity_aliases.csv` — the alias crosswalk

One row per (entity, observed spelling). Use it to audit entity resolution, and
to link in outside sources that use a different spelling.

| Variable | Description |
|---|---|
| `entity_id`, `entity_type` | As above. |
| `alias_raw` | The spelling exactly as printed in the filing. |
| `matching_key` | Normalised key that caused the merge. Identical keys merge. |

## 3. `multiplex_edges_observed.csv.gz` — the edge list

**The main analytic file.** One row per tie *as reported by one filing*. A tie
reported by three filings appears three times, each with its own provenance;
this is deliberate, so that nothing is deduplicated away before the analyst has
seen it. Deduplicate on `(layer, year, source_id, target_id)` when a single
observation per dyad-year is wanted.

| Variable | Type | Description |
|---|---|---|
| `layer` | factor | Which relation. See §4. |
| `year` | int | Year the tie is **observed to hold**, taken from the first of these the source supplies: the date the table states it describes (`as_of`); the financial year the document covers; the filing date. The middle step matters for annual reports, which are published the year *after* the year they report on — dating them by filing would shift every tie in them one year late. |
| `obs_date` | date | The underlying date, at day resolution where stated. |
| `source_id`, `target_id` | string | Endpoints (`entity_id`). For directed layers, source → target reads "holds a stake in" / "is parent of". |
| `source_name`, `target_name` | string | Canonical names, denormalised for convenience. |
| `source_type`, `target_type` | factor | Entity types, denormalised. |
| `weight` | float | **Scale depends on the layer** — see §4. |
| `directed` | 0/1 | Whether direction is meaningful for this layer. |
| `role` | string | Reported role, where the source states one (`Président`, `Administrateur`, …). Raw French. |
| `mandate_start`, `mandate_end` | int | Board term as printed ("2023-2025"). Present only for board layers. |
| `n_shares` | float | Share count, where reported. |
| `seat_holder_type` | factor | For board layers: whether the seat is held by a natural or legal person. |
| `represents` | string | For a person occupying a legal person's seat, the `entity_id` of the entity represented. **This is the corporate-control channel behind an apparently personal tie.** |
| `shared_actors` | string | Derived layers only: the `entity_id`s that generate the tie. |
| `doc_node_key`, `doc_type`, `doc_url`, `page` | string/int | Provenance: the filing and the page the tie was read from. |
| `doc_sha256` | string | Hash of the retrieved PDF, so a later re-publication of the same URL is detectable. |

## 4. Layers and their weights

| Layer | Direction | Weight | Read as |
|---|---|---|---|
| `ownership` | directed | % of capital (0–100] | Named blockholder → issuer. From the disclosure table of holders above the reporting threshold (usually 3% or 5%). |
| `ownership_director` | directed | % of capital | Stake held by a board or management member. Overlaps `ownership` by construction when a blockholder also sits on the board. |
| `group_participation` | directed | % of capital | Issuer → subsidiary, from the group-structure table. This is the intra-group control channel. |
| `board_seat` | undirected | 1 | Natural person ↔ firm. Bipartite. |
| `board_seat_corporate` | undirected | 1 | Legal person ↔ firm: a company holding a board seat in another company. |
| `declared_mandate` | undirected | 1 | Person ↔ another company where they declare a directorship. **Extends beyond the cote into unlisted firms**, which is where much of the elite structure sits. |
| `declared_executive` | undirected | 1 | Person ↔ company where they declare an executive role (CEO, managing director). |
| `board_interlock` | undirected | count of shared individuals | *Derived.* Firm ↔ firm projection of person-firm affiliations within a year. |
| `coownership` | undirected | count of shared blockholders | *Derived.* Firm ↔ firm projection of common owners within a year. |

**On weights.** Ownership weights are percentages exactly as reported; interlock
and co-ownership weights are counts. They are deliberately *not* rescaled to a
common range: how to trade off a 30% stake against two shared directors is a
modelling decision. `R/load_bourse_multiplex.R::collapse_year()` takes explicit
`layer_weights` for exactly this reason.

**On derived layers.** `board_interlock` and `coownership` are projections of the
other layers, not independent evidence. Including them *and* their constituent
layers in one model double-counts. Use one or the other.

## 4b. `movements.csv` — dated operations

One row per CMF notice describing an operation on a company's capital or its
shares. Where the ownership layers give annual *snapshots*, these give dated
*changes*.

| Variable | Description |
|---|---|
| `movement_id` | Stable id, hashed from the filing and its PDF URL. |
| `event_type` | `opa_obligatoire`, `opa_simplifiee`, `opr_retrait`, `opf_prix_ferme`, `opv_prix_ouvert`, `ope_echange`, `maintien_de_cours`, `augmentation_capital`, `reduction_capital`, `fusion`, `admission`. |
| `is_result` | `True` where the notice reports an operation's **outcome** rather than announcing it. An announcement and its result are separate rows describing one operation: the first states what was sought, the second what was acquired. **Filter on this before counting operations.** |
| `event_date`, `event_year` | When the operation is dated. |
| `event_date_source` | Which field supplied `event_date`: `close_date`, `open_date`, `decision_date`, `delisting_date`, or `filing_date`. **`filing_date` is only an upper bound** — the notice was filed on that day, the operation happened on or before it. |
| `target_id`, `target_name`, `target_name_raw` | The company whose capital or shares the operation concerns. |
| `price_tnd` | Offer price per share. |
| `pct_stated`, `pct_max_stated` | Percentages of capital the notice states; `pct_max_stated` is the largest, which is normally the concert total. |
| `shares_sought`, `shares_acquired`, `shares_stated` | Share counts. `shares_acquired = 0` is a real outcome (an offer that drew no deposits), not a missing value. |
| `capital_before_tnd`, `capital_after_tnd` | Capital either side of an increase or reduction. |
| `capital_stated_tnd` | Capital as given in the notice header, where the before/after pair is not restated. |
| `capital_method` | `incorporation de réserves`, `souscription en numéraire`, … |
| `new_shares` | Shares created. |
| `open_date`, `close_date`, `decision_date`, `delisting_date` | The underlying dates, where stated. |
| `listing_event`, `market`, `isin`, `ticker` | Admission or radiation details. |
| `doc_*` | Provenance, as elsewhere. |

**A capital increase creates no tie.** It dilutes every existing holder, so it
changes the ownership *weights* rather than adding an edge. It is recorded here
and deliberately not in the edge list.

## 4c. `firm_listing_events.csv` — entry to and exit from the cote

| Variable | Description |
|---|---|
| `entity_id`, `firm_name` | The company. |
| `listing_event` | `admission` (arrival on the cote) or `radiation` (removal). |
| `event_date`, `event_year` | When. |
| `market`, `isin`, `ticker` | As stated in the notice. |

This is the listing history the BVMT roster snapshot cannot give (see §6.3).
It is incomplete: it covers only firms whose admission or withdrawal notice is
in the corpus, so absence of a row is not evidence a firm was never listed.

## 4d. `board_events.csv` — dated board decisions

One row per (resolution, person) from the adopted-resolutions filings. A single
resolution often seats several directors, and each is a separate event.

| Variable | Description |
|---|---|
| `board_event_id` | Stable id, hashed from the filing plus resolution and person index. |
| `meeting_date`, `meeting_year`, `meeting_kind` | The general meeting that took the decision. `meeting_kind` is `ordinaire`, `extraordinaire`, `mixte`, `elective` or `constitutive`. |
| `meeting_date_source` | `document` where the filing states the meeting date, `filing_date` where it had to fall back. |
| `resolution_number` | Position of the resolution in the filing. |
| `n_people_in_resolution` | How many people the resolution names — see the succession caveat below. |
| `event_type` | `appointment`, `cooptation`, `cooptation_ratified`, `renewal`, `non_renewal`, `termination`, `mandate_expiry`. |
| `role` | `administrateur`, `administrateur_independant`, `administrateur_representant_etat`, `president_conseil`, `president_directeur_general`, `commissaire_aux_comptes`, … |
| `firm_id`, `firm_name`, `firm_name_raw` | The company whose board it is. |
| `person_id`, `person_name`, `person_name_raw` | The person seated or removed. Null where the resolution named no readable person. |
| `seat_holder_type` | `person`, or `legal_person` where a company holds the seat. |
| `entity_name_raw`, `represents_id` | The company holding the seat, where one does. |
| `replaces_id`, `replaces_name_raw` | The outgoing director the resolution names ("en remplacement de"). |
| `board_decision_date` | For a ratified co-optation, the date the board itself decided — earlier than the meeting that ratified it. |
| `term_years`, `term_end_year` | Mandate length, and the financial year whose accounts the expiring meeting will rule on. |
| `adoption` | `adopted_unanimously`, `adopted_by_majority`, `rejected`. |
| `excerpt` | The first 400 characters of the resolution, so any coding can be checked. |

**Auditors are included.** `commissaire_aux_comptes` appointments are governance
decisions but not board seats; filter on `role` to separate them.

**Roughly half the filings carry no governance decision at all** — they approve
accounts and grant discharge. Those produce no rows, which is why the table is
much smaller than the number of filings.

## 5. `multiplex_edges_panel.csv.gz` — the balanced panel

Same columns as the observed edge list, plus:

| Variable | Description |
|---|---|
| `panel_year` | The year the row is asserted for. |
| `observation_type` | `observed` — a filing describes this year. `carried_forward` — the last observation is being extended forward. |

`tender_offer`, `concert_party`, `board_appointment` and `board_succession` are
**excluded from the panel**. They are dated events, not states: carrying an
offer or an appointment forward would assert that it happened again. They appear
in the observed edge list only. To build board *spells*, join
`board_appointment` (the start) to `term_end_year` (the stated end) rather than
carrying the tie forward blindly.

Ties are carried forward until the dyad is next observed, capped at
`--max-carry` years (default 3). **Filter to `observation_type == "observed"`
for anything where measurement error in the timing matters.** The panel exists
because ownership disclosures are irregular, not because the ties are known to
persist.

## 6. Known limitations

These are properties of the sources, and should be stated in any write-up.

1. **Disclosure thresholds truncate ownership.** Blockholder tables list holders
   above a threshold (commonly 3% or 5%). Dispersed ownership is invisible, so
   in-degree in the `ownership` layer is *not* the number of shareholders.
   `capital_structure` records (in `data/processed/bourse/records/`) carry the aggregate
   residual for the firms where it was reported.
2. **Homonym merging.** Entity resolution merges on normalised name equality.
   Tunisian elite families reuse given names across generations, so distinct
   individuals sharing a name are merged. Correct known cases in
   `config/bourse_entity_overrides.csv`.
3. **Listing status is a snapshot.** `is_bvmt_listed` reflects the cote at the
   roster snapshot, not at each year. A firm delisted in 2014 is not flagged as
   listed. Entries and exits can be recovered from the `offre_publique` filings
   already in the registry (OPF ≈ entry, OPR ≈ exit).
4. **Coverage is uneven across firms and years.** Registration documents are
   filed by issuers raising capital or as required, not annually by everyone.
   Banks and leasing companies are over-represented. Check
   `layer_year_coverage.csv` before making any claim about change over time —
   a rise in observed ties can be a rise in filings.
5. **Declared mandates are self-reported and "most significant".** The interlock
   layer is what directors chose to disclose, so it under-counts.
6. **Extraction is automated.** Table classification and row parsing are rule-
   based and validated against a sample, not hand-checked for every document.
   `data/processed/bourse/records/failures.jsonl.gz` lists documents that could not be
   parsed; `validation_report.md` reports anomalies that survived.
7. **Known residual artefacts.** Two are worth naming, because they are visible
   in the current build and will recur on rebuild:
   * *Share counts can merge.* Where a borderless table prints two grouped
     figures with only a narrow gap ("975 000 975 000"), column detection
     occasionally reads them as one. The **percentage is unaffected** — it is
     identified by its `%` sign — so `weight` is sound where `n_shares` looks
     implausible. Prefer `pct_capital`/`weight` over `n_shares`.
   * *Spelling variants survive.* "Mohamed FEKIH" and "Mohamed FKIH" appear as
     two entities, each with 18 firm ties. Whether they are one person is a
     substantive judgement the matcher will not make; resolve it in
     `config/bourse_entity_overrides.csv`.
8. **Succession is only drawn where it is unambiguous.** A resolution that
   seats several directors but names one departing person does not say which of
   them replaced that person. Pairing them all would invent handovers, so a
   `board_succession` edge is emitted only where the resolution names exactly
   one appointee (`n_people_in_resolution == 1`). Multi-person resolutions keep
   `replaces_name_raw` in `board_events.csv` for anyone who wants to code the
   pairing by hand.
9. **The resolution corpus has a hole across the revolution.** This is the most
   consequential gap in the dataset and it is a property of the source, not of
   the parser. The CMF's "Résolutions adoptées" section carries 116 filings for
   meetings held in 2010, **one for 2011, and nothing at all for 2012–2017**,
   resuming thinly from 2018:

   | Meeting year | 2001 | 2005 | 2006 | 2007 | 2008 | 2009 | 2010 | 2011 | 2012–17 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2026 |
   |---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
   | Filings | 17 | 11 | 51 | 15 | 87 | 100 | 116 | 1 | **0** | 3 | 2 | 10 | 27 | 8 | 2 | 8 |

   **Do not read the absence of board events in 2012–2017 as board stability.**
   Any before/after design around January 2011 that uses `board_appointment` or
   `board_succession` is comparing a dense pre-period against an empty
   post-period. The `board_seat` layer, which comes from registration documents,
   does cover those years and is the one to use there.

   A further 71 of 529 filings state no readable meeting date and fall back to
   the filing date (`meeting_date_source`).

10. **Board coverage skews to investment funds.** SICAVs file diligently;
    operating companies less so. 483 of 606 rows concern operating companies,
    across 78 firms.

11. **Part of the record is read by OCR, and is weaker evidence.** About a
    third of the corpus was scanned from paper rather than filed digitally and
    carries no text layer at all. These filings are concentrated in exactly the
    years where digital coverage is thinnest, so they are read with Tesseract
    and fed to the same table extractor (see `docs/SOURCES-bourse.md`).

    Every row obtained this way carries **`from_ocr = 1`**, in the records and
    on the edge list. Treat those edges as a lower-confidence stratum: the
    tables are located from their heading rather than a column header, and
    misread characters are left uncorrected on purpose, so a name may appear
    with a wrong letter ("Abdeikader" for "Abdelkader") and resolve to its own
    entity instead of merging. Check `n_aliases` and the alias crosswalk before
    treating a scanned-era actor as distinct, and use `from_ocr` to test whether
    a result depends on the scanned stratum.

    Aggregate `capital_structure` rows are deliberately **not** read from
    scanned pages: that parser maps columns by position, and a scanned table
    omitting the shareholder-count column would take its share figures from the
    percentage column. An aggregate carries no edge, so a wrong number there
    would be pure loss.

12. **Date an annual report by its file name, not by its text.** The CMF names
    these files with the financial year, and for a scanned report that is the
    only year available before OCR. Counting coverage from extracted text makes
    the scanned years look empty — a fact about the text layer, not about what
    the regulator published. An earlier draft of this codebook reported no
    annual reports at all for FY2012–2014 for exactly this reason; there are
    195.

   Two firm-years still show declared stakes above 100% (see
   `validation_report.md`). Both trace to inconsistencies in the filings
   themselves rather than to parsing, and are left as reported.

## 7. `layer_year_coverage.csv`

Edge and node counts per layer-year, plus how many distinct filings contributed.
**Read this before interpreting any time trend.**

## 8. Export formats

* `muxviz/` — `edges_<year>.txt` in extended edge-list format
  (`node layer node layer weight`), with a shared `nodes.txt` and `layers.txt`
  index across all years, so node IDs are comparable over time.
* `graphml/` — one `multiplex_<year>.graphml` per year, `layer` carried as an
  edge attribute, readable by igraph, networkx and Gephi.
* `*_panel/` variants of both, built from the carried-forward panel.
