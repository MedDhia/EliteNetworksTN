# How an organisation is identified

Read this before treating an organisation vertex as a firm. Identity in this
dataset used to be "the seed node this mention fuzzy-matched", and that
definition fabricated hubs rather than merely blurring names. It has been
replaced by a key built from hard identifiers. Nothing was removed to achieve
that: the change is to what counts as an identity claim, not to what is in the
tables.

## The failure this replaced

Two ordinary decisions compounded into a large one.

**`fuzz.token_set_ratio` treats containment as identity.** It returns roughly
1.0 whenever one string's token set is a subset of the other's, however much
else the longer string says. `resolve.best_org_match` scored its fuzzy tier
with it, so a seed label was matched by any mention that happened to contain
its words:

```
token_set_ratio("comptoir tunisien de batiment", "batiment")   == 1.000
token_set_ratio("plastic research consulting", "la consulting") == 0.870
```

**`seed.py` mints an organisation id from the label with legal-form words
stripped** — `parse_org(label).normalised`. A seed firm called "SOCIETE TROIS"
therefore became `CO_TROIS` with `label_normalised = "TROIS"`, the French for
three, and `seed_degree = 1`.

Together those two facts made a low-degree seed node into the largest
organisation in the corpus. `CO_TROIS` absorbed 135 distinct mentions,
including the address `Route de Sidi Mansour km 6 Sfax` and the clause
fragment `pour une periode limitee de trois ans`, and became the
highest-degree node in the org-org layer at 1,003 tie endpoints.

| node | seed label | distinct mentions absorbed | distinct matricules |
| --- | --- | --- | --- |
| `CO_CONSULTING` | LA CONSULTING | 4,076 | 1,606 |
| `CO_GENERALE` | SOCIETE GENERALE | 1,893 | 647 |
| `CO_BATIMENT` | BATIMENT + | 1,545 | 635 |
| `CO_TROIS` | SOCIETE TROIS | 135 | — |

A matricule fiscal is a hard identifier: a firm has one. A node carrying 1,606
of them is not a noisy match, it is 1,606 firms wearing one name. 288 nodes
carried ten or more values of a single hard identifier.

## How far it spread

The two layers were affected very differently, for a structural reason.

| layer | observations touching a hub node | share |
| --- | --- | --- |
| person–organisation dyads | 258 of 10,844 | 2.4% |
| org–org observations | 2,034 of 3,104 | 65.5% |

Person resolution is dyad-anchored: a person is only resolved where the
organisation agrees, so a generic organisation match rarely carries a person
match with it. That is what held the bipartite panel to 2.4%. `orgties.py` has
no dyad to anchor an endpoint, so it resolves each endpoint on its own, and
two thirds of that layer landed on a hub.

## How the attachment decomposed

A random sample of 3,000 hub-attached mentions (seed 11) splits by the route
that attached them:

| route | share |
| --- | --- |
| fuzzy, seed label's tokens a subset of the mention's | 69.0% |
| fuzzy, partial overlap still clearing 0.88 | 26.3% |
| exact normalised collision between two seed labels | 2.8% |
| the learned matricule map | 2.0% |

95% therefore came through the fuzzy tier, which is why the fix is there. The
2.8% are seed-sheet collisions: two distinct seed firms whose labels normalise
identically already share a node id under `seed.py`, with the losers recorded
in `alt_names`. The 2.0% is second-order — a generic match scoring 1.0 seeded
the learned matricule map, which then propagated it.

## The discriminator is document frequency, not token count

A fuzzy match needs to rest on at least one token that actually distinguishes
a firm. The measurable version of "distinguishes" is document frequency across
the 199,608 distinct organisation mentions in the corpus:

| generic | df | distinctive | df |
| --- | --- | --- | --- |
| CONSULTING | 4,738 | TUNISAIR | 22 |
| DISTRIBUTION | 3,920 | SANIMED | 4 |
| CONFECTION | 2,069 | CEREALIS | 4 |
| CONSEIL | 1,151 | PARENIN | 4 |
| TOURISTIQUE | 972 | SFBT | 3 |
| BATIMENT | 455 | CONECT | 2 |
| GENERALE | 354 | HEXABYTE | 1 |
| TROIS | 143 | | |

This is measured from the corpus itself, so no external stop-word list is
needed. Document frequency is counted over *distinct* mentions, not events: a
firm that files forty times would otherwise make its own name look generic.

**Token count is not the signal.** 2,463 of 15,541 non-person seed nodes have
a single-token normalised label, and most are proper names — SFBT, TUNISAIR,
CONECT — where containment matching is exactly right. Gating on label length
would have refused those and kept CONSULTING.

**The threshold is a judgement and is presented as one.** The narrowest
observed gap is TROIS at 143 against TUNISAIR at 22, about 6x, so there is no
sharp boundary to find. It is configured in `config/scope.yaml` as
`org_identity.discriminating_df_share: 0.0005` — about 100 of 199,608 — and
`make orgentity --sensitivity` reports the outcome at 0.0002, 0.0005 and 0.001
so the choice stays visible. `min_corpus_mentions: 500` makes the gate inert
below that many distinct mentions, so the small test fixtures keep the
pre-change behaviour instead of being gated on noise.

A fuzzy match whose shared tokens are all generic is recorded as
`generic_fuzzy` and is **not** an identity. The candidate and score survive on
the returned `OrgMatch`, so a refusal is as inspectable as an acceptance.

## The entity key

`orgentity.py` builds one row per organisation as this corpus can distinguish
it, keyed in priority order:

1. the normalised matricule fiscal
2. the normalised registre-de-commerce number
3. the normalised mention

The matricule comes first because it does two jobs at once. It **splits** a
hub — 1,606 matricules on one node become 1,606 entities — and it **joins**
spelling variants, because 19,795 matricules cover more than one spelling,
folding 52,683 spellings into single firms. That is why this raises coverage
rather than lowering it: the fix is a better key, not a stricter threshold.

98.4% of mentions carry exactly one matricule. The remaining 1.6% carry more —
the worst, `Societe de Promotion Immobiliere`, carries 78 — and a mention
naming several firms identifies none of them. An identifier-less event on such
a mention gets an `ambiguous_mention` entity, which is retained as data and
explicitly identifies nothing, rather than being folded in with whichever firm
was modal.

The rebuild produced **230,023 entities** over 296,795 distinct mentions: 73,770 keyed on a matricule fiscal, 13,650 on an RC number, 140,005 on a name and 2,598 unattributable. **36,405 entities join more than one spelling**, folding 114,524 spellings into single firms.

## Why entities adopt seed ids

Where the seed match is identity-grade — exact, acronym, or a fuzzy match
resting on a discriminating token — the entity adopts the seed node's id
rather than minting an `ORGE_` one. This is not cosmetic. `seed_edges.csv`
ties and every dyadic covariate in the TERGM export are keyed on seed node
ids, so an entity that did not adopt would sit on a different vertex from its
own seed ties, and the undated ownership and kinship structure would be
projected onto an empty vertex. Entities whose only seed link is
`generic_fuzzy` get a fresh id, which is precisely the population that formed
the hubs.

## Nothing was removed

The constraint the whole design serves is that this be fixed without removing
any data, so membership in the org-org layer is unchanged. An endpoint still
counts if its mention comes within 0.88 of any seed organisation, generic
match included: `best_org_match` reports the candidate even where the
specificity gate refuses it as an identity, because the org-tie review queue
is only adjudicable if a coder can see which seed organisation the other end
nearly matched and by how much. Only identity changed.

`elitenet.validate` carries an ERROR check that every organisation mention in
`events.csv` reaches an entity. A mention reaching none would mean the refined
identity had dropped an observation, which is the one outcome the instruction
forbids.

After the rebuild, **130 organisations still hold ten or more values of a
single hard identifier** (176 organisation-identifier pairs), against 288
before, and the worst node falls from 1,606 matricules to 154. The top
organisation-to-organisation degree falls from 1,003 to 45, and `CO_TROIS` is
gone from the layer entirely.

That is a large reduction and not an elimination, and what remains is a
**different defect**, which is worth separating out. Every one of the 176
remaining pairs sits on a **seed node**; not one sits on an `ORGE_` entity. So
the entity layer is clean and the residual is upstream of it, in `seed.py`:

| node | normalised label | values |
| --- | --- | --- |
| `CO_M` | `M` | 154 matricules |
| `CO_PROMOTION_IMMOBILIERE` | `PROMOTION IMMOBILIERE` | 117 matricules |
| `CO_SMAG` | `SMAG` | 73 |
| `CO_BB` | `BB` | 62 |
| `CO_PNEU` | `PNEU` | 57 |

These are not containment matches — the token-blocking index only holds tokens
longer than three characters, so `M` and `BB` cannot be reached that way. They
are **exact** normalised matches, on the tier the specificity gate deliberately
does not touch: many firms called "Société M …" normalise to the single
character `M` once legal-form words are stripped, and hundreds of firms are
genuinely, separately named *Société de Promotion Immobilière*.

No name-based method can separate firms that really do share a name. Only an
identifier can, which is precisely what the entity key does — and the fact
that zero entities are affected is the evidence that it works. The seed node
stays merged because the seed sheet has one node per name, and every gazette
observation now hangs off the entity rather than off that node.

## What this does not fix

Three residual errors, all reported rather than hidden. The first runs in the
opposite direction from the defect it replaced, which matters for how results
should be read.

**Name-keyed entities split one firm across spellings.** This is the mirror
image of the merge. Only about a third of events carry a matricule and a sixth
an RC number, so most entities are name-keyed, and two spellings of one
identifier-less firm stay apart. Where the merge **overstated** degree, this
**understates** it. Treat organisation-level degree and centrality as a lower
bound on the name-keyed population, and check whether a result depends on
entities with no hard identifier.

**Seed-sheet collisions persist.** Distinct seed firms whose labels normalise
identically still share a node id where no hard identifier separates them.
Adoption preserves that collision rather than introducing it, and `orgattrs`
reports it.

**A mention carrying several identifiers cannot be attributed by name alone.**
The `ambiguous_mention` entities are the honest record of that, not a
resolution of it. They should be excluded from anything that asserts two
observations are the same firm.

## Files

| file | contents |
| --- | --- |
| `data/processed/org_entities.csv` | one row per entity, with `entity_basis`, `entity_key`, seed link and `is_identity` |
| `data/processed/org_entity_members.csv` | mention → entity, with `n_entities_on_mention` where the map cannot represent the assignment |
| `data/interim/org_token_df.json` | the cached document-frequency table and its threshold |

`make orgentity` builds both tables. `OrgEntityResolver.load()` returns an
inert resolver when they are absent, so a downstream stage run standalone
keeps its previous behaviour rather than half-applying the new identity. The
per-event `entity_key` is the authoritative assignment; the member map is
modal per mention and says so in its own columns.
