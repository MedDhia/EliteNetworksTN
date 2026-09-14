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

## One graph, six tie types — `fig12`

`python scripts/figure_elite_graph.py` →
`figures/fig12_elite_graph.{png,pdf}` and
`data/processed/multiplex/elite_graph_{nodes,edges}.csv`

A single entity-level graph — individuals and organisations as separate
nodes, nothing aggregated or projected onto one mode — admitting exactly six
kinds of tie and nothing else:

| category | ties |
|---|---|
| 6 · every edge in the seed file, whatever its label | 30,295 |
| 1 · an individual owning shares in, or on the governing body of, a company (state-owned or not) | 8,434 |
| 5 · an organisation owning shares in another organisation | 1,792 |
| 3 · an individual on an association board or in a party's national structures | 964 |
| 4 · members of the government and of parliament | 293 |
| 2 · individual to individual by family | 13 |

**37,855 entities, 41,791 ties**: 13,630 individuals, 22,920 companies,
1,076 associations and unions, 194 state bodies, 35 parties and
parliamentary blocs. The largest connected component holds **23,808 (63%)**
and is what the figure draws.

The largest nodes are the RCD central committee (419 ties), État Tunisien
(337), the Présidence (196), the SICAR investment vehicles, BIAT and BNA,
and the Nidaa Tounes and Ennahda party organs.

### What is excluded

**5,438 gazette ties** whose holder is a government employee below the
government, parliament and board level: `chef_de_service`,
`sous_directeur`, `secretaire_general`, `directeur general`, `conseiller`,
`representant`, and the state offices whose rank the gazette never states.
Auditors and liquidators go too, and so do chief executives not stated to
sit on a board.

### Three judgement calls, recorded because they are arguable

* **A SARL's `gérant` counts as a governing-body seat.** A SARL has no
  board; the gérant *is* its governing organ and is normally also an
  `associé`. Excluding gérants would drop 10,304 gazette ties and most of
  the private sector with them.
* **A chief executive not stated to sit on the board does not count.**
  `dg`, `dga` and `ceo` are management, and category 1 says "sitting at the
  board" — so 952 gazette `dg` ties are out. Seed-file rows labelled CEO or
  GENERAL MANAGER are in regardless, under requirement 6.
* **`chef_de_cabinet` is out here**, though the broader decision-level cut
  above keeps him: a cabinet chief is neither a member of the government
  nor a board member, and this list is narrower.

`BOARD_OR_OWNER`, `ASSOCIATION_OFFICER` and `GOVERNMENT_MEMBER` in
`scripts/figure_elite_graph.py` are the whole specification, in one place,
to be re-cut.

### Two notes on the drawing

`nx.spring_layout` is unusable at this size: with scipy present it takes
the sparse path, which loops over nodes in **Python** once per iteration,
so 23,808 nodes × 80 iterations ran for 20 minutes without completing a
step. The layout is igraph's DRL, the same class of algorithm in C, which
returns in seconds.

The edge and node lists are written alongside the figure so the graph can
be re-drawn in Gephi, igraph or networkx without re-running the filter.

## Two centres, not one — `fig13`

`python scripts/figure_core_periphery.py` →
`figures/fig13_core_periphery.{png,pdf}` and
`data/processed/multiplex/elite_graph_centrality.csv`

The same six-category graph as `fig12`, restricted to its largest connected
component (**23,274 entities, 31,457 ties**), with two changes: node area is
proportional to **betweenness** rather than degree, and the layout *states*
the core-periphery structure rather than leaving it to a force algorithm —
radius is coreness (equal-width rings), angle is Louvain community (107
communities, modularity 0.899).

Putting brokerage on a radius set by cohesion lets the two disagree, and
they do. **The largest nodes are not in the centre.**

| ring | nodes | peak betweenness | ring median | composition |
|---|---|---|---|---|
| k=1 | 16,254 | 1.3M | 0 | 66% company |
| k=2 | 4,567 | 3.0M | 28,615 | 50% company |
| k=3 | 1,389 | 6.5M | 75,917 | 52% company |
| k=4 | 737 | 30.8M | 183,458 | 56% company |
| **k=5** | **256** | **37.4M** | **330,025** | **68% company** |
| k=6 | 63 | 2.9M | 148,969 | 49% company, **0% state** |
| k=7 | 8 | 4.3M | 55,926 | **100% individual** |

Betweenness climbs to a ridge at **k=5** and then collapses ninefold in the
two rings inside it. Not one of the thirty largest brokers sits at k≥6 — they
are all at k=3–5 — and the best-brokering member of the k=7 core ranks only
41st. So the network has two centres, and they are different entities:

* the **k=5 brokerage ridge** — the banks (BIAT, STB, BNA, Amen, UBCI), the
  SICAR investment vehicles and État Tunisien. These are the bridges.
* the **k≥6 cohesive nucleus** — 71 nodes of private business family, with
  **no state body, no party and no association at all**, and eight people
  and nothing else at k=7.

The mechanism is density. Inside the nucleus the surname blocks are
near-complete cliques, and inside a clique every path has an alternative, so
no member lies on a unique shortest path. Cohesion and brokerage are not the
same property, and here they are held by different entities. This is the same
inversion `fig11` found at decision rank, reached independently: the state's
apparent dominance is a feature of the *periphery's* wiring, not the core's.

### Surname blocks are reported one by one, because pooling would lie

A shared surname is **not** evidence of a family, so each block in the
nucleus is scored on the share of possible person-person pairs that carry an
actual tie:

| block | members | pairs tied | one connected block? |
|---|---|---|---|
| Ben Yedder | 6 | 15 / 15 | 6 / 6 |
| Driss | 5 | 10 / 10 | 5 / 5 |
| Abdelkefi | 8 | 27 / 28 | 8 / 8 |
| Elloumi | 9 | 28 / 36 | 8 / 9 |
| Bouchamaoui | 5 | 3 / 10 | 4 / 5 |
| **Slama** | 5 | **0 / 10** | **1 / 5** |

Four are kinship cliques. **Slama is not**: its five members share a surname
and nothing else — no extracted kinship tie between any pair, and they do not
form one connected block. They reach k≥6 through shared company boards
(Slama Huiles, Slama Frères, Nejma Huiles are all in the nucleus). Pooling
the blocks into one "family nucleus" bar would have published that as
kinship. The figure names the exception instead.

This is the same discipline that killed an earlier "top brokers" bar chart
for `fig10`: 100% of the top five were named *Mohamed* against a 46% base
rate, which would have made a homonym artefact the headline.

### Two rendering decisions worth recording

* **Rings are equal width, not area-proportional to population.** Sizing each
  annulus to its population was tried first and collapses the 8-node k=7 core
  to 2% of the radius, which defeats the purpose of the figure.
* **Area is ∝ √betweenness above a visible floor.** Betweenness is exactly
  **zero for 14,250 of 23,274 nodes (61.2%)**; strict proportionality would
  erase three nodes in five, so the floor is used and the zero share is
  stated on the figure rather than hidden by it.
* **Brokers are numbered on the map and named in the margin.** In-situ labels
  all landed in the same few rings as one unreadable knot.

## Publication figures, and why a date filter is a source filter

`scripts/figure_apsr_network.py` draws the brokerage core at journal scale:
the giant component of the subgraph induced on the 200 highest-betweenness
entities, node **area** strictly proportional to betweenness.

| | `fig15` (pooled) | `fig16` (`--before 2011-01-14`) |
|---|---|---|
| drawn | 191 nodes, 397 ties | 198 nodes, 264 ties |
| share of all betweenness | 39.3% | 79.0% |
| natural persons | 73 | **112** |
| state bodies and parties | 23 | 27 |
| firms, associations, unions | **95** | 59 |
| largest brokers | État Tunisien, Présidence, RCD, BIAT, ATD SICAR | Min. Économie, Présidence, Min. Affaires Étrangères, Mohamed Mahjoub, Mohamed Trabelsi |

**The date cut is exactly a filter on source, and that governs how `fig16`
can be read.** Datability splits the dataset perfectly by evidence tier:

| tier | spells | dated |
|---|---|---|
| `gazette_dated` / `gazette_inferred` / `gazette_snowball` | 22,903 | **100%** |
| `seed_undated` | 27,585 | **0%** |

There is no partially-dated tier and no dating failure to repair. Ownership
(4,184), membership (1,879), kinship (733), leadership (100) and pedagogic
(96) spells are *entirely* seed-derived, carrying
`onset_rule='seed_current_tie'` and `evidence_n=0`.

Dropping them from a pre-2011 figure is therefore **correct, not a
shortfall**: the seed roster asserts a *present* affiliation and was
compiled long after 2011, so carrying those ties into a pre-revolution
graph would be an anachronism. Three consequences must travel with the
figure, and are written into its caption:

* **Betweenness is recomputed** on the pre-2011 graph. The pooled values
  are computed over a different graph and the two are not comparable.
* **The gazette documents state appointments more completely than company
  officers** — every `state_office` spell is gazette-evidenced against half
  of `corporate_officer` — so `fig16` overstates the state's share relative
  to the private layer. The person-heavy, firm-light composition above is
  partly this, and must not be read as a pure finding about 2011.
* The pre-2011 graph is **sparse and fragmented**: 9,734 entities with a
  tie, 2,505 components, and a giant component holding only 31% of them.

Two data defects the date cut exposed, both already handled: an
**unlabelled organisation held 590 pre-2011 offices**, more than any
ministry and the largest node in the graph — OCR damage, dropped under the
same rule as the exploratory figure (only genuinely blank labels, never
merely short ones, since GAT, MAC and PAF are real firms). And organisations
are classified from the tie class the pipeline already coded, never from a
regex on the label, because `SOCIETE REGIONALE DE COMMERCE GOUVERNORAT DE
BEJA` is a firm and a label regex calls it a state body.

## Known limitations

* **Coreness ≠ importance, and neither does betweenness alone.** The two
  disagree here by construction of the data: a family that co-owns its own
  firms generates a dense clique, which maximises coreness and minimises
  betweenness. Reporting either number alone would support the opposite
  conclusion about who is central, which is why `fig13` shows both.
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
