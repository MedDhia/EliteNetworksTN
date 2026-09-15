# Resilience of the pre-2011 network: dataset, strategies, caveats

`python scripts/percolation_pre2011.py` → `data/processed/percolation/`

Builds the gazette-evidenced network as of 14 January 2011 from
`elitenet.dated_graph` — the same builder the publication figures use, so
the graph analysed and the graph drawn cannot drift apart — and ships it in
the formats a percolation study needs, plus a harness that runs the curves against a degree-preserving null.
`scripts/figure_apsr_percolation.py` turns the result into
`figures/fig17_percolation.pdf` at APSR artwork spec.

| file | contents |
|---|---|
| `pre2011_nodes.csv` | one row per node: class, degree, betweenness, eigenvector, closeness, coreness, participation, community, component, `in_lcc` |
| `pre2011_edges.csv` | undirected dyads with `tie_kind` and `n_spells` |
| `pre2011.graphml` | whole graph, **all attributes attached** — loads in igraph, networkx, Gephi with no join needed |
| `pre2011_lcc.graphml` | largest connected component, centralities **recomputed inside it** |
| `pre2011_attack_orders.csv` | removal rank per node for each static strategy; 0 is removed first |
| `pre2011_percolation_lcc.csv`, `..._full.csv` | the curves: strategy × graph (observed / configuration null) × replicate × step |
| `pre2011_meta_lcc.json`, `..._full.json`, `README.md` | run parameters, counts, column dictionary |

## The graph

**9,734 nodes, 7,619 undirected ties, 2,610 components.** The largest holds
**2,509 nodes (25.8%)** and 2,921 ties. Composition: 3,988 natural persons,
73 state bodies and parties, 5,673 firms, associations and unions. Ties:
6,720 person-to-firm, 780 into a state body or party, 119
organisation-to-organisation.

## Strategies, and where they come from

**Static** — shipped as an explicit removal order:

| strategy | source |
|---|---|
| `random` | Albert, Jeong & Barabási 2000, *Nature* 406:378. Averaged over 20 seeded draws |
| `degree` | initial degree, "ID" in Holme, Kim, Yoon & Han 2002, *Phys. Rev. E* 65:056109 |
| `betweenness` | initial betweenness, "IB" in Holme et al. 2002 |
| `eigenvector` | Restrepo, Ott & Hunt 2006, *PRL* 97:094102 |
| `closeness` | Iyer, Killingback, Sundaram & Wang 2013, *PLoS ONE* 8:e59613 |
| `coreness` | k-shell, Kitsak et al. 2010, *Nature Physics* 6:888 |
| `participation` | inter-module ties first; Guimerà & Amaral 2005, *Nature* 433:895 |

**Adaptive** — order depends on removals already made, so computed at run
time rather than shipped:

| strategy | source |
|---|---|
| `degree_recalc` | "RD" in Holme et al. 2002 |
| `betweenness_recalc` | "RB" in Holme et al. 2002 |

**Substantive**, specific to a two-mode elite network rather than to the
percolation literature: `state_first`, `orgs_first`, `persons_first` remove
one class of entity before the others, each class internally ordered by
degree. These answer "what if the state apparatus goes" rather than "what
is the optimal attack".

## Results of the shipped run (`--scope lcc`)

Robustness *R* is mean *S* over the removal sequence (Schneider et al.
2011, *PNAS* 108:3838); lower is more fragile. `R null` is the
degree-preserving configuration model over 12 rewirings.

| strategy | R obs | R null | obs/null | f at S<0.5 |
|---|---|---|---|---|
| `betweenness_recalc` | 0.0146 | 0.0382 | **0.38×** | 0.010 |
| `degree_recalc` | 0.0162 | 0.0385 | **0.42×** | 0.010 |
| `state_first` | 0.0168 | — | — | 0.010 |
| `degree` | 0.0168 | 0.0398 | **0.42×** | 0.010 |
| `betweenness` | 0.0217 | 0.0452 | **0.48×** | 0.010 |
| `orgs_first` | 0.0251 | — | — | 0.010 |
| `coreness` | 0.0273 | — | — | 0.020 |
| `participation` | 0.0452 | — | — | 0.050 |
| `persons_first` | 0.0694 | — | — | 0.040 |
| `closeness` | 0.1100 | — | — | 0.050 |
| `eigenvector` | 0.1321 | — | — | 0.080 |
| `random` | 0.2571 | 0.3244 | **0.79×** | 0.130 |

Three things to take from this.

**The targeted/random gap is large.** Random failure needs 13% of nodes to
halve the giant component; degree or betweenness needs 1%.

**Against its own degree sequence the network is more fragile than it has
to be, and about twice as much so under attack.** Random failure runs at
0.79× the null, targeted strategies at 0.38–0.48×. Since the null holds
every node's degree exactly and destroys everything else, the excess
vulnerability is structural — it is not a consequence of the degree
distribution alone. This is the comparison that survives the near-tree
problem below, and the one worth reporting.

**`state_first` is as destructive as an optimal degree attack** (R =
0.0168 for both) while `persons_first` is four times less so (0.0694).
Connectivity is carried by the state bodies, not by the officeholders.

`figures/fig17_percolation.pdf` plots panel (a) the curves against the
null and panel (b) *R* for every strategy.

### One caveat on the null itself

Rewiring a near-tree disconnects it: the rewired giant component holds
about **78%** of the nodes (mean 1,965 of 2,509). Comparing a connected
observed component against a fragmented null would confound decay under
attack with initial connectedness, so the null is reduced to its own
largest component and both start at *S* = 1. The cost is that the null's
degree sequence is then the *rewired giant component's*, not the observed
one's exactly. Under `--scope full` no such reduction is needed and the
degree sequence is preserved exactly; that run gives obs/null of
0.63–0.67 for targeted strategies and 0.67 for random, so the direction
and rough magnitude of the finding do not depend on this choice.

## Four caveats on the graph, in order of how much they matter

**1. The largest component is very nearly a tree, so there is almost no
redundancy to destroy.** 2,509 nodes carry 2,921 ties: **413 independent
cycles**, **61% of nodes at degree 1**, and **687 articulation points**
(27% of nodes), any one of which disconnects the graph. Every strategy
therefore looks devastating in absolute terms, and the collapse point is
close to zero for all of them. **The interpretable result is the ranking
between strategies, not the absolute critical fraction.** Reporting "the
network collapses after removing 1% of nodes" without this is misleading:
a tree does that by definition.

**2. Clustering is near zero because the graph is two-mode.** Persons tie
to organisations, so triangles are all but structurally impossible and
transitivity is 0.0002. Any resilience measure that presumes a one-mode
network with meaningful clustering — and much of the percolation literature
does — should not be read off this graph. The two-mode-appropriate
comparison is the class-first strategies.

**3. The graph is fragmented before anything is removed.** Only 25.8% of
nodes are in the largest component, so a curve over the whole graph starts
at *S* = 0.26, not 1.0, and the usual reading of a percolation threshold
does not apply. `--scope lcc` (the default, and what the literature almost
always means) restricts to the largest component; `--scope full` keeps
every node. Say which one you used.

**4. The date cut is also a source cut.** Datability splits the spell table
perfectly by evidence tier: every gazette-evidenced spell carries a date
and every `seed_undated` spell carries none. Ownership, membership,
kinship, leadership and pedagogic ties are *entirely* seed-derived, so they
are absent here — correctly, since that roster asserts present
affiliations and post-dates 2011, but it means **this measures the
resilience of the gazette-evidenced network, not of every relation that
existed before 2011**. Shareholding and kinship, the two layers most likely
to supply the redundancy this graph lacks, are the ones missing. The
near-tree result should be stated as a property of the *observed* network.

The gazette also documents state appointments more completely than company
officers, which inflates the state's structural role — relevant directly to
the `state_first` finding above.

## Two implementation notes

* **Adaptive strategies are batched.** Recomputing betweenness after each
  single removal is 2,509 betweenness computations; `--recalc-every`
  (default 10) sets the interval, it is an approximation, and it is
  recorded in `pre2011_meta.json`.
* **Betweenness is recomputed on this graph**, and again inside the LCC for
  `pre2011_lcc.graphml`. Values from the pooled all-sources figures
  describe a different object and must not be carried across.
