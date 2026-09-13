# The whole dataset as one graph

`make project` → `projection_summary.csv`, `projection_isolates.csv`,
`projection_nodes.csv`

The layers are built separately because they carry different kinds of
evidence. This is the question they cannot answer apart: how many people and
how many organisations are in the network *as one thing*.

**There is no single answer, and that is the finding.** The count moves by
more than an order of magnitude depending on what you let be a node, so all
three readings are reported, nested, each with its edge definition attached.

| tier | individuals | organisations | nodes | edges | isolates | giant component |
|---|---|---|---|---|---|---|
| `seed_anchored` | 13,630 | 26,755 | 40,385 | 46,579 | 1 | **27,002 (66.9%)** |
| `officer_layer` | 80,868 | 68,650 | 149,518 | 135,358 | 1 | **63,307 (42.3%)** |
| `all_sources` | 631,754 | 324,687 | 956,441 | 394,113 | 535,386 | **200,991 (21.0%)** |

| tier | giant: individuals | giant: organisations | 2nd / 3rd component |
|---|---|---|---|
| `seed_anchored` | 8,808 | 18,194 | 29 / 22 |
| `officer_layer` | 33,683 | 29,624 | 52 / 36 |
| `all_sources` | **130,333** | **70,658** | 41 / 36 |

## What each tier admits

**`seed_anchored`** — validated affiliations, ownership ties and gazette
kinship, plus the seed sheet's own family and mentorship edges. Every edge is
a claim the pipeline is prepared to defend. Use this unless you have a
specific reason not to.

**`officer_layer`** — adds the SARL/SA officer roster, which admits
**gazette-only people**: named in print, absent from the 13,630-name roster.

**`all_sources`** — adds the **full gazette co-mention graph** and the whole
register, every company and every sole trader.

### The largest number rests on the weakest edge

`all_sources` is much the biggest, and mostly **not** because of the
register. It is because its person-organisation edge is a **co-mention** — a
person and an organisation named in the same filing — which is a far weaker
relation than a dated affiliation. 378,914 of its 394,113 edges are
co-mentions.

That tier is an **outer bound on who could be connected to whom**, not a
roster of offices held. The 200,991-node core is real in the sense that these
people and firms appear together in print; it is not evidence that any of
them worked together.

## A node universe is not a network

**535,386 nodes — 56% of `all_sources` — have no tie at all.**

| isolate | count |
|---|---|
| register sole traders never named in the gazette | 314,848 |
| register companies never named in the gazette | 138,956 |
| gazette person mentions with no organisation | 67,600 |
| gazette organisation entities with no tie | 13,981 |
| seed organisations with no tie | 1 |

They are kept rather than filtered, because a registered company nobody ever
filed about is both a real company and a real absence of evidence, and those
two facts are only distinguishable if it is present with `degree = 0`.
Dropping them would also quietly convert "we know nothing about this firm"
into "this firm does not exist".

### The register adds entities, not structure

* **64,677 of 203,788 register companies (31.7%)** carry an identifier the
  gazette also prints. Those *are* the gazette entity — one node, not two —
  so they add no nodes at all.
* **139,111 register companies** are standalone isolates.
* **811 of 315,659 sole traders (0.26%)** have an identifier that appears in
  any filing. The other 314,848 are unconnectable: Arabic-only names, no
  identifier in print, and this pipeline is French-side.

So admitting the whole register roughly triples the node count and barely
moves the structure. That asymmetry is the entire content of "everything
included".

## Structure: one core and a cliff

Every tier has the same shape — a single dominant component and then almost
nothing. The second-largest component is **29 nodes** in `seed_anchored`,
**52** in `officer_layer` and **41** in `all_sources`. Below the core:
2,749 isolated pairs in `seed_anchored`, 63,014 in `all_sources`.

**More data made the network more fragmented, not more connected.** From
`seed_anchored` to `officer_layer` the giant component more than doubles in
absolute size (27,002 → 63,307) while its *share* of nodes falls from 66.9%
to 42.3%. Most SARL filings name people who never surface again, so the
officer layer arrives overwhelmingly as isolated dyads rather than as new
paths through the core.

## The edge layers

| layer | edges | tier |
|---|---|---|
| gazette co-mention | 378,914 | `all_sources` |
| SARL/SA officer links | 96,930 | `officer_layer` |
| person-organisation spells | 49,659 | `seed_anchored` |
| organisation ties / ownership | 8,141 | `seed_anchored` |
| seed person-person (family, mentorship) | 828 | `seed_anchored` |
| gazette kinship | 14 | `seed_anchored` |

The last two are worth reading together. The seed sheet's own relational
columns yield **828** person-person ties — 312 `parent_of`, 243
`sibling_of`, 178 `spouse_of`, 96 `student_of` — against the gazette kinship
extraction's **14**. The family structure already in the spreadsheet is 59×
what the `épouse` markers recovered, which bears directly on whether that
layer is worth widening.

## Two identity rules, both wrong on the first attempt

**A node's type comes from the node, not from the column it sits in.**
`spells.csv` carries the seed sheet's relational edges alongside gazette
affiliations, and for those the *kin* sits in the `org_id` column: 829 spells,
all `seed_undated`. Typing by column made **307 people into organisations**
and 829 family ties into employment. `node_kind` now types by seed
`node_type` where known and by id prefix otherwise, and `validate` fails at
ERROR level if any node ends up typed both ways.

**A register company the gazette also prints is one node, not two.** The
identifier join is a node *merge*. Treating it as an edge would invent a
relationship between a firm and itself and double every such company —
64,677 of them.

## What `validate` enforces

Arithmetic and structure, not substance — which tier to believe is the
reader's call. At ERROR level:

* `individuals + organisations == nodes`, per tier
* `connected_nodes + isolates == nodes`, per tier
* the giant component's two halves sum to its size, and it is no larger than
  the graph
* **the tiers are nested**: no count may fall as the tier widens, since a
  fall would mean a wider tier dropped something a narrower one had
* no node is typed both as a person and as an organisation
* the node table's row count and its degree-0 count match the widest tier's
  reported figures

## Known limitations

* **Gazette-only people are mention clusters, not verified individuals.** Two
  spellings of one man can be two nodes; two men of one name can be one node.
  `suspect_holes.csv` flags 4,220 person pairs and 23,414 organisation pairs
  as plausibly one entity, so both node counts carry error in both
  directions — and those suspects were computed on the *observed* network, so
  they understate at `all_sources` scale.
* **`all_sources` is undated.** Co-mention edges carry no spell, so this
  projection is a cross-section of the whole 1957–2026 window and says
  nothing about who was connected *at the same time*. For anything
  longitudinal use `panel_edges_yearly.csv`.
* **The node table is written only for the widest tier.** Narrower tiers are
  a filter on `tier_first_seen`, rather than the same rows three times.
* **Isolates dominate the widest tier**, so any average degree, density or
  centralisation computed over `all_sources` without filtering `degree > 0`
  will be meaningless.
