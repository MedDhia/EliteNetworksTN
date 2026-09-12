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
| `year` | int | Year the tie is **observed to hold**: the year of the date the document states it describes (`as_of`), else the filing date. |
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

## 5. `multiplex_edges_panel.csv.gz` — the balanced panel

Same columns as the observed edge list, plus:

| Variable | Description |
|---|---|
| `panel_year` | The year the row is asserted for. |
| `observation_type` | `observed` — a filing describes this year. `carried_forward` — the last observation is being extended forward. |

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
6. **Extraction is automated, and every record has been checked against its
   page.** Table classification and row parsing are rule-based.
   `make bourse-verify` re-opens each source PDF, accepts it only if the bytes
   hash to the digest in `corpus/pdf_manifest.jsonl.gz`, and asks of every
   record drawn from it whether the name and the figure appear on the page
   cited. The current pass reads **7,593 records from 179 filings and confirms
   100.0% of names and 99.9% of figures**; `source_verification.md` carries the
   table and names every record that did not confirm.

   This check is not redundant with `validation_report.md`. Those checks test
   the dataset against itself — stakes that should not exceed 100%, endpoints
   that should resolve — and a figure read off the wrong row passes all of
   them, because a misread figure is still internally consistent. Running the
   source check found four extraction defects that the internal checks could
   not see, described in §6.1.

   `records/failures.jsonl.gz` lists documents that could not be parsed at all.
7. **Known residual artefacts.**
   * *Spelling variants survive.* "Mohamed FEKIH" and "Mohamed FKIH" appear as
     two entities, each with 18 firm ties. Whether they are one person is a
     substantive judgement the matcher will not make; resolve it in
     `config/bourse_entity_overrides.csv`.
   * *Six records out of 7,593 are not confirmed on their page*, all of them
     rows of tables that interleave a figure column with commentary. They are
     named individually in `source_verification.md`.
   * *Thin years.* 1994 and 2001 carry fewer than ten observed edges each. That
     is a property of how many filings cover them, not a parsing failure.

## 6.1 Defects the source check found, and what they mean for earlier builds

Four extraction defects were found by checking records against their pages, and
all four are fixed. They are recorded here because any analysis run against a
build from before this fix carries them.

* *Two adjacent figures read as one number.* On a short borderless row the
  column threshold could exceed every gap on the line, leaving the row as a
  single cell: `PIRECO 750 000 750 000 3,00%` became a holding of
  750,000,750,000 shares.
* *A figure split mid-number.* Where the extractor cut one token in two,
  `2 666 921` arrived as `2`,`6`,`66`,`921` and was read as **2 shares**; a
  stake printed `0,005%` was read as **5%**.
* *Table footnote legends parsed as rows.* 61 records carried names such as
  `*** Membre indépendant`.
* *A whole table body read as one row.* Where a table's only ruling lines box
  the body rather than each row, every cell held its column stacked with
  newlines. Flattened, the six largest shareholders of Amen Bank became one
  shareholder holding the concatenation of their six stakes. This one destroyed
  data rather than merely mangling it, and unwinding it recovered the
  controlling blocks of several of the largest firms in the corpus.

The first two corrupted `n_shares` and `nominal_amount_tnd` but **not**
`pct_capital`, which is identified by its `%` sign and was never ambiguous; the
network layers weight on percentage, so their edge weights were not affected.
The last two did change the node set.

Note for anyone reading the merged history: the codebook previously described
merged share counts as an artefact that "will recur on rebuild", and attributed
two firm-years with stakes above 100% to "inconsistencies in the filings
themselves rather than to parsing". Both statements were wrong. The first is
fixed at source above. The second were entity-resolution double counts, and the
arithmetic matched the double-counted excess exactly; they are now gone.

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
