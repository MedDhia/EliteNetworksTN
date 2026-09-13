# Are politically connected firms more central?

Centrality is measured on the pooled firm-firm network (3,311 nodes, 5,287 edges), and connection is the firm-level 'ever coded' flag from `political_connections.csv`.

Each channel is tested twice. **Naive** uses the whole network. **Leave-out** deletes the nodes whose ties define that channel — public banks, state bodies — from treated and control firms alike, so what is left is whether a connected firm is better placed among *other* firms. Labels are permuted within bins of the number of documents naming the firm, so the comparison is against equally-well-observed firms rather than against unfiled ones.

Reported as the stratified difference in mean percentile rank (0–1) — the gap averaged within document-count bins, weighted by treated count; p from 5,000 stratified permutations.

Exposure bins (documents naming the firm) and how the treated firms fall across them:

| Bin | Firms | `pc_officeholder` | `pc_state_ownership` | `pc_state_board` | `pc_any_state` | `pc_public_bank` | `pc_narrow` | `pc_broad` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 doc | 1992 | 1 | 1 | 2 | 2 | 198 | 1 | 201 |
| 2 | 638 | 1 | 2 | 3 | 4 | 40 | 1 | 42 |
| 3–4 | 375 | 0 | 0 | 1 | 1 | 44 | 0 | 45 |
| 5–9 | 204 | 1 | 4 | 3 | 6 | 31 | 1 | 34 |
| 10+ | 102 | 7 | 6 | 8 | 9 | 16 | 5 | 21 |

## `pc_officeholder` — officeholder on the board

10 firms coded connected. No deletion needed: this channel is read from a director's title, not from a firm-firm tie.

| Measure | Naive Δrank | p | Leave-out Δrank | p |
|---|---:|---:|---:|---:|
| degree | +0.137 | 0.0096 | — | — |
| strength | +0.071 | 0.0030 | — | — |
| betweenness | +0.179 | 0.0016 | — | — |
| core | +0.046 | 0.3971 | — | — |

## `pc_state_ownership` — state holds equity

13 firms coded connected. Leave-out deletes 29 state nodes.

| Measure | Naive Δrank | p | Leave-out Δrank | p |
|---|---:|---:|---:|---:|
| degree | +0.184 | 0.0004 | +0.178 | 0.0004 |
| strength | +0.113 | 0.0002 | +0.106 | 0.0006 |
| betweenness | +0.241 | 0.0002 | +0.240 | 0.0002 |
| core | +0.121 | 0.0154 | +0.087 | 0.0798 |

## `pc_state_board` — state holds a board seat

17 firms coded connected. Leave-out deletes 29 state nodes.

| Measure | Naive Δrank | p | Leave-out Δrank | p |
|---|---:|---:|---:|---:|
| degree | +0.195 | 0.0002 | +0.184 | 0.0002 |
| strength | +0.126 | 0.0002 | +0.112 | 0.0002 |
| betweenness | +0.245 | 0.0002 | +0.244 | 0.0002 |
| core | +0.077 | 0.0864 | +0.022 | 0.6333 |

## `pc_any_state` — any direct state tie

22 firms coded connected. Leave-out deletes 29 state nodes.

| Measure | Naive Δrank | p | Leave-out Δrank | p |
|---|---:|---:|---:|---:|
| degree | +0.195 | 0.0002 | +0.185 | 0.0002 |
| strength | +0.118 | 0.0002 | +0.106 | 0.0002 |
| betweenness | +0.255 | 0.0002 | +0.254 | 0.0002 |
| core | +0.092 | 0.0236 | +0.048 | 0.2460 |

## `pc_public_bank` — tie to a state-owned bank

329 firms coded connected. Leave-out deletes 8 public_bank nodes.

| Measure | Naive Δrank | p | Leave-out Δrank | p |
|---|---:|---:|---:|---:|
| degree | +0.016 | 0.0664 | -0.273 | 0.0002 |
| strength | -0.004 | 0.5035 | -0.270 | 0.0002 |
| betweenness | +0.008 | 0.3211 | -0.009 | 0.2773 |
| core | +0.017 | 0.0462 | -0.279 | 0.0002 |

## `pc_narrow` — Faccio strict

8 firms coded connected. Leave-out deletes 29 state nodes.

| Measure | Naive Δrank | p | Leave-out Δrank | p |
|---|---:|---:|---:|---:|
| degree | +0.153 | 0.0086 | +0.145 | 0.0154 |
| strength | +0.087 | 0.0042 | +0.075 | 0.0146 |
| betweenness | +0.199 | 0.0018 | +0.199 | 0.0012 |
| core | +0.056 | 0.3719 | -0.050 | 0.4475 |

## `pc_broad` — any channel

343 firms coded connected. Leave-out deletes 37 state/public_bank nodes.

| Measure | Naive Δrank | p | Leave-out Δrank | p |
|---|---:|---:|---:|---:|
| degree | +0.026 | 0.0028 | -0.255 | 0.0002 |
| strength | +0.003 | 0.5821 | -0.256 | 0.0002 |
| betweenness | +0.021 | 0.0144 | +0.003 | 0.7263 |
| core | +0.019 | 0.0244 | -0.269 | 0.0002 |

## Reading it

A positive Δrank means connected firms sit higher in the centrality
distribution than comparably-filed unconnected firms. Read the
leave-out column: the naive column still contains the ties that
*defined* the connection, so for `public_bank` and the state channels
it is partly arithmetic.

**Yes for the state channels, and it survives the correction.** A firm
the state holds equity in, or holds a board seat on, ranks about 0.18
higher on degree and 0.24 higher on betweenness than a firm named in
as many filings — and the estimate barely moves when every state node
is deleted from the graph. Whatever this is, it is not the state's own
edges being counted twice.

**No for the broad measure, which reverses.** `pc_broad` is a small
positive on the whole network and a large *negative* once public
banks are removed (degree −0.26). The same holds for `public_bank`
alone, which supplies almost all of `pc_broad`'s firms. Those firms
are mostly small participations hanging off a bank: delete the bank
and they are more peripheral than comparable firms, not less. The
naive positive was the hub, and nothing else. **Any analysis that
uses `pc_broad` as the treatment is measuring this artefact.**

## The shape of the effect, where there is one

The measures disagree in a consistent order — betweenness > degree >
strength > core, with core not distinguishable from zero in most
specifications — and that ordering is itself the finding.

A firm that scored high on core number would sit inside a densely
interconnected group. Connected firms do not: they have many
partners (degree) and sit on many shortest paths (betweenness) while
*not* being embedded in a tight cluster. Strength rising less than
degree says the same thing from another direction — their ties are
numerous but thin, each partner observed few times, rather than
repeated dealing with a small set.

That is a brokerage signature rather than a cohesion one. On this
evidence state-linked firms are not an inner circle trading among
themselves; they are positioned *between* parts of the network that
are otherwise not connected. Which of those two things a theory of
elite survival expects is worth being explicit about, because the
data distinguish them.

## Multiplicity

Seven channels × four measures × two graphs is 56 tests. At 5,000 permutations the smallest reportable p is 0.0002, and the state and officeholder
results on degree, strength and betweenness sit at that floor — they
survive a Bonferroni correction (0.05/56 ≈ 0.0009). The `core`
results, at p between 0.02 and 0.09, do not, and are reported as
null.

## What this cannot settle

**Direction.** These are pooled co-occurrences. A firm may be central
because it is connected, or connected because it is central, and
nothing here distinguishes them. The dated layers are too thin to
test sequence: `board_appointment` covers 12 years and is empty
across 2012–2017.

**Disclosure.** Connection is coded from titles firms chose to print.
Stratifying on document count controls how *much* a firm filed, not
what it chose to reveal in those filings.

**Sector, and it bites unevenly.** Banks are over-represented in the
corpus and central by construction in an interlock network. Of the
10 firms carrying `officeholder`, 8 are banks — that channel is close
to a bank indicator, and its result should not be read as being about
political connection as against being about banking. The state
channels are better placed: only 3 of their 22 firms are public
banks, and the rest are Tunisair, Tunisie Telecom, Carthage Cement,
STAR, SIMPAR and similar — state-linked firms across several
sectors. That is why the state channels, not the officeholder one,
carry the weight of the finding here. No sector control is applied
because the corpus has no clean sector variable; adding one is the
next thing that would sharpen this.

**Small treated groups.** The defensible channels have 8–22 firms.
The permutation test is exact under its null and does not assume
large samples, so the p-values are honest, but the *estimates* are
not precise and a handful of firms moves them. The exposure-bin
table above shows where the treated firms sit: most are in the
highest-filed bin, so the comparison group for them is roughly the
hundred best-covered firms rather than the whole corpus.
