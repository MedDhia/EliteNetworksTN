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

## The decision-level state floor

`state_floor` is a second, **orthogonal** dimension to the tiers. At
`decision`, a tie to a **state body** counts only where the stated rank is
one of: minister or above (`chef_du_gouvernement`, `minister`,
`secretary_of_state`), the minister's own cabinet chief (`chef_de_cabinet`),
a governor, the head of a public establishment, or board level of a
state-owned entity (`administrateur`, `administrateur_delegue`,
`president_ca`, `pdg`, `dg`, `ceo`, `chairman`, `president`,
`premier_responsable`).

**The private sector is not filtered at all.** A *gérant* of a SARL is the
decision-maker of his own firm, so every corporate role is kept.
Organisation-to-organisation ties and kinship are untouched too: a rank
floor is about office, and an ownership tie or a sibling tie has no rank.

| tier | floor | individuals | organisations | nodes | edges | giant |
|---|---|---|---|---|---|---|
| `seed_anchored` | none | 13,630 | 26,755 | 40,385 | 46,579 | 27,002 |
| `seed_anchored` | **decision** | 13,630 | 26,711 | 40,341 | 45,211 | 26,213 |
| `officer_layer` | none | 80,868 | 68,650 | 149,518 | 135,358 | 63,307 |
| `officer_layer` | **decision** | 80,856 | 68,603 | 149,459 | 133,957 | 62,690 |
| `all_sources` | none | 631,754 | 324,687 | 956,441 | 394,113 | 200,991 |
| `all_sources` | **decision** | 599,456 | 324,554 | 924,010 | 338,136 | **156,584** |

`validate` checks at ERROR level that a filter can only remove: at matching
tiers the `decision` family is never larger than `none`.

### What the floor does, and the inversion it produces

**It drops five person-to-state ties in six** — 8,985 clear the floor,
61,287 fall below it. The biggest single category is `chef_de_service`
(18,900), then no role stated (22,570) and `sous_directeur` (7,229).

**The ministry hubs lose 91% of their ties.** The Ministry of the Interior
falls from 5,600 to 423, Finances from 3,877 to 710.

**And the cohesive core inverts.** Unfiltered, the state's share of core
organisations climbs to 82% at k≥7. At decision level it stays flat and
reaches **0%**: no state body survives in the k≥6 core at all.

So the state's apparent dominance of the network was **an artefact of
rank** — a ministry looks like a hub because it appoints thousands of
people, most of them well below any decision-making level.

### What is left is family capitalism

The decision-level k≥6 core is **one interlocked block of 176 nodes** — 78
individuals and 98 organisations, 732 ties — plus an 11-node Bouchamaoui
island. Its 78 individuals carry only **30 surnames**, and the seven
largest carry 48 of them:

| family | individuals in the core |
|---|---|
| Ben Yedder | 12 |
| Elloumi | 9 |
| Abdelkefi | 8 |
| Bayahi | 5 |
| Slama | 5 |
| Driss | 5 |
| Bouricha | 4 |

The firms are Tunisia's private blue chips — Poulina Group Holding, Amen
Bank, Tunisie Leasing, Magasin Général, Ennakl Automobiles, Meublatex,
Electrostar, TPR — held through family groups that interlock into a single
block.

### Two caveats that bound this

**These are a lower bound, not a census.** 22,570 person-to-state ties
state no rank at all, and an unstated rank cannot be shown to clear the
floor, so it is dropped. Some genuine decision-makers are therefore
missing.

**Two judgement calls are recorded rather than hidden.** Secretaries of
state and governors are counted as decision-makers; a ministry's
*directeur général* and *secrétaire général* are not — they are senior
civil servants, below both minister and board. `STATE_DECISION_ROLES` in
`src/elitenet/project.py` is the whole list, in one place, to be re-cut.

**Removing the real hubs promotes the junk.** With the ministries gone, the
top of the degree distribution fills with extraction noise: 390
organisation nodes have labels of three characters or fewer — "S" at 536
ties, "M" at 431, "A" at 303 — and the rubric heading "Associations,
partis, syndicats et syndics" at 1,488 becomes the single largest node.
The figure excludes them and says so; they were always there, masked by
the ministries.

## The figures

`python scripts/figure_giant_component.py` → `figures/fig10_giant_component.{png,pdf}`
`python scripts/figure_decision_core.py` → `figures/fig11_decision_core.{png,pdf}`

**fig11 is the one to read if you care about decision-makers**, and it
reverses fig10's headline for the reason above. fig10 is the unfiltered
view and is kept because the contrast between them *is* the finding.

Five panels on the `all_sources` giant component, and three findings the
tables above do not carry:

**The component is a state appointment fan, not an elite club.** 60% of its
nodes have exactly one tie, and its organisation hubs are ministries — the
Ministry of the Interior alone at 5,600 ties. It peels to nothing: the
innermost core, `k≥7`, is **193 nodes, 0.10%** of it.

**That core is the state, by a factor of about 160.** State bodies are
**369 of 70,658 organisations (0.5%)** in the component but **54 of the 63**
in the core (86%); private SARL/SA firms are a third of all organisations
and 8% of the core. Almost everything the register and the SARL/SA officer
layer contributed sits on the rim.

**The core is one cadre, not a set of ministerial cliques.** Collapsing the
core's 127 individuals into ties between the organisations they share gives
a graph of **density 0.594**, and **95% of the top 24×24 ministry pairs
share at least one individual in the core**. This is also why panel (d) is a
matrix: a node-link drawing of a near-complete graph on 63 long ministry
names is a hairball with labels on it. The first draft of the figure was
exactly that, and it was thrown away.

### What the figure will not let you read

**The person side of the core is homonyms.** 100% of the five
widest-bridging individuals, and 90% of the top ten, are named
"Mohamed …" — against a 46% base rate for that name among core
individuals. Nodes carrying the commonest Tunisian male given name touch
8.44 core organisations on average against 6.65 for everyone else. Those
nodes are several men merged, so the core's brokers are not a finding and
the figure says so on its face.

**Three of the twenty highest-degree organisations are extraction noise**:
the rubric heading "Associations, partis, syndicats et syndics" (1,488
ties), the clause word "Objectifs" (533), and one unlabelled node (532).
They are excluded from panel (d) and named in its note rather than deleted
quietly.

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
