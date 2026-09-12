# Fitting a TERGM to the 2008–2012 elite panel

Read this before specifying a model. The panel is TERGM-estimable, and
`make tergm` plus `Rscript R/build_tergm_panel.R` produce a list of bipartite
`network` objects with a risk set and covariates attached. But one property of
the source constrains what those objects can support, and it is not visible in
the files themselves.

## The one thing you cannot model here: dissolution

**82.1% of dated tie spells are right-censored** — 3,519 of 4,287. Only 768
(17.9%) have an observed terminus.

That is not a sampling accident. Tunisian company law makes an appointment a
mandatory filing; a departure frequently is not filed, and in this window the
gazette carries roughly **ten appointment formulas for every explicit exit**.
So the panel accumulates:

| transition | ties formed | ties dissolved | dissolution rate |
|---|---|---|---|
| 2008 → 2009 | 793 | 102 | 11.1% |
| 2009 → 2010 | 919 | 106 | 6.6% |
| 2010 → 2011 | 883 | 156 | 6.4% |
| 2011 → 2012 | 720 | 184 | 5.8% |

Edges grow 919 → 3,685 across the window while the dissolution rate *falls*.
No plausible account of Tunisian elite careers makes ties steadily harder to
lose across the 2011 revolution. What the falling rate measures is the
probability that an exit has been *printed* by the end of the window.

**Consequence.** A dissolution or persistence parameter fitted to this panel
estimates gazette publication behaviour, not tie duration. `memory("stability")`
will be large and near-meaningless. Do not interpret it, and do not report a
STERGM dissolution formula from these data as a finding about elite turnover.

### What to do instead

Three defensible options. The exported artifacts support all three, so the
choice is yours rather than baked into the data.

1. **Formation-only (recommended, and what the worked example does).** Model
   tie formation conditional on the previous period. Include
   `memory("stability")` as a nuisance control — it soaks up the accumulation —
   and interpret only the formation side. This is standard practice where exits
   are under-observed.
2. **Restrict to observed exits.** 1,073 binary ties carry
   `dissolution_observed = 1`, meaning the spell was actually seen to end
   (`terminus` present, not right-censored). Within that subpopulation
   dissolution is real. The network is much smaller and selected toward firms
   that dissolve and roles with mandated renewal, which needs saying.
3. **Treat the panel as cumulative co-membership** and state plainly that
   persistence is definitional rather than estimated.

## Two further limits

**Five periods is the floor.** Memory terms consume the first, leaving four
transitions. `timecov` on four points is not worth specifying. Widening the
window is mechanical — the pipeline is parameterised by `config/scope.yaml` —
but costs a full re-mirror and re-extract, and would put the gold-sample
accuracy figures back in question on the new years.

**The 60 monthly periods are not a substitute.** A month is shorter than the
gazette's publication lag, so month-to-month change is dominated by reporting
noise rather than elite turnover, and the per-period networks are extremely
sparse. Use yearly.

**The window is effectively single-layer.** Despite the build's name, the
yearly panel is 11,756 corporate edges against 37 state edges. A multi-layer
TERGM is not supported by this window's data. The state layer is thin because
`journal-officiel` appointments concentrate in cabinet decrees, which name few
people relative to the *annonces légales*.

## The network is two-mode

Every one of the 11,793 panel edges runs person → organisation. There are no
person–person or organisation–organisation ties in the dated panel, so the
network is bipartite and must be declared so.

`exports/tergm/node_key.csv` is **mode-blocked**: persons occupy vertex ids
1–2,592 and organisations 2,593–5,507, which makes `bipartite = 2592` a true
statement about the ordering. This matters more than it sounds. `network` will
build an object from a key that violates the ordering, `btergm` will estimate
on it, and every degree and star coefficient will be computed against a
reference distribution containing person–person dyads that cannot exist. There
is no error message for that failure, which is why
`elitenet.validate --strict` checks the ordering at ERROR level.

**Use two-mode terms only.** `triangle` and `gwesp` count structures that
cannot occur in a bipartite network. The analogues are:

| one-mode | two-mode |
|---|---|
| `gwdegree` | `gwb1degree` (persons), `gwb2degree` (organisations) |
| `kstar(2)` | `b1star(2)`, `b2star(2)` |
| `triangle`, `gwesp` | `cycle(4)` — the shortest closure a two-mode graph admits |

## The risk set

A firm constituted in 2010 is not a non-tie in 2008; it did not exist. Treating
an impossible dyad as an observed absence moves every coefficient, so the risk
set is exported explicitly in `vertex_activity_yearly.csv`.

Organisation lifecycles are recovered by joining `events.csv` (`org_mention`)
to `resolution.csv` (`resolved_org_id`): **1,936 of 2,915 organisations have a
constitution date** and 214 a dissolution date. Organisations with no
constitution date are treated as left-censored and at risk from the window
start (`birth_known = 0`), which is the conservative reading.

Active vertices per period: 4,153 → 4,557 → 4,918 → 5,192 → 5,413 out of 5,507.
Persons are at risk throughout — the gazette records appointments, not births —
which is an assumption rather than a measurement, and one that biases nothing
in a formation model but should not be read as a claim about the population.

**Risk windows are intervals, widened rather than punched through.** Where a
lifecycle date says a firm did not exist in a period where it demonstrably
holds a tie, the window is widened to cover the tie: 87 organisations widened
before a constitution date, 94 after a dissolution date. Two reasons. The risk
set must contain every observed tie, or the estimator is handed a dyad that is
simultaneously a structural zero and an observed edge. And forcing only the
contradicting periods would leave activity non-contiguous, asserting that a
firm blinked out of existence and returned.

Widening past a *dissolution* date is often not even an error — a dissolved
company still has a liquidator appointed, and that appointment is a real tie
postdating the death. Widening past a *constitution* date generally is one, so
the two are counted separately.

**Implementation.** The vertex set is constant across periods and the risk set
is expressed as a structural-zero offset matrix, not by deleting inactive
vertices. `network` does correctly adjust the bipartite count when vertices are
deleted, so deletion is safe in that narrow sense — but it makes the vertex set
differ between periods, and `memory()` then depends on how `btergm` matches
vertices across unequal networks. The offset states the same claim with no such
dependency, via `offset(edgecov(off))` with the coefficient fixed at `-Inf`.

## Covariates

### Nodal — `node_attrs_yearly.csv`

`node_type`, `is_seed`, `seed_degree`, `kin_degree`, `pedagogic_degree`,
`first_seen_year`, `tenure_years`, `cum_degree`, `cum_degree_lag`.

**Use `cum_degree_lag`, not `cum_degree`.** Degree measured at *t* is a
function of the very ties being modelled at *t*. The lagged version counts
distinct alters through *t−1* and is the exogenous one.

### Dyadic — `dyad_cov_yearly.csv`

The seed sheet carries 829 person–person and 4,698 organisation–organisation
ties that the panel deliberately excludes because they are undated. Being
undated means they can never be endogenous in a temporal model — and projected
into person × organisation space they become exactly the elite-reproduction
mechanisms worth testing.

| covariate | definition | nonzero dyads |
|---|---|---|
| `is_shareholder` | person *i* is a recorded shareholder of organisation *j* | 2,570 (514 × 5 periods) |
| `kin_in_org` | *i* is kin to someone who held a post in *j* at *t−1* | 661 |
| `owner_of` | *i* held a post at *t−1* in an organisation that is a shareholder of *j* | 1,663 |
| `prior_comembership` | *i* shared an organisation at *t−1* with someone who held a post in *j* | 7,003 |

`kin_in_org` draws on 733 kinship ties (312 PARENT, 243 SIBLING, 178 SPOUSE);
`pedagogic_degree` on 96 STUDENT-OF ties; `owner_of` on 4,347 company-held
SHAREHOLDER stakes; `is_shareholder` on 4,183 person-held ones.

Both stake types arrive in the seed sheet under the same label
(`edge_label_raw == "SHAREHOLDER"`) and are separated by the mode of the
holder. Conflating them would put an individual's personal holding on every
colleague's dyad.

The first three are lagged to *t−1*, so they are zero in 2008, which has no
lag. `is_shareholder` comes from the undated sheet, is exogenous without a lag,
and is populated in every period including the first — where it is the only
dyadic predictor available.

Stored as **sparse triplets**: dense would be 2,592 × 2,915 per covariate per
period. `R/build_tergm_panel.R` densifies them.

## Sample selection

A TERGM treats a tie as certain. The panel does not:

| | ties |
|---|---|
| `certainty == "certain"` | 9,147 |
| `probable` | 1,527 |
| `possible` | 323 |
| `link_status == "resolved"` | 8,200 |
| `ambiguous` (person not pinned to one identity) | 2,797 |

The R script therefore defaults to **resolved + certain — 6,988 of 10,997
binary ties**. `--all-ties` includes everything, and the spread between the two
fits *is* the measurement-uncertainty sensitivity analysis. Report both.

Note also that the 11,793 panel rows collapse to **10,997 binary ties**: a
person can hold two roles in one firm in one year, which is two panel rows and
one tie. The roles are preserved pipe-joined in `role_canonical`.

## Two known data problems that bite TERGM specifically

**Merged homonyms.** 11 resolved persons hold more than 12 dyads, worst
`PERSON_TRABELSI_MOHAMED` at 39. A fused identity is a fabricated high-degree
vertex, and `gwb1degree` is estimated directly off the person-side degree
distribution — so these do not merely add a wrong edge, they distort the term
most likely to carry your structural argument. 35 overlapping single-holder
posts are the same defect seen from the other side. Both are open WARNs in
`docs/VALIDATION-multiplex-2008-2012.md`.

**Non-firm organisation vertices.** `org_name()` occasionally returns an
address, a role fragment, or a whole clause. 16 such vertices are flagged
`label_suspect = 1` in `node_key.csv`, carrying 77 of 10,997 ties. They are
flagged rather than dropped, because dropping them would change the panel and
this stage only re-indexes it. Consider excluding them.

## Running it

```bash
make tergm                                   # writes exports/tergm/ (~10 s)
Rscript R/build_tergm_panel.R                # builds the network list (~8 s)
Rscript R/build_tergm_panel.R --sample 40    # fast structural smoke test
Rscript R/build_tergm_panel.R --all-ties     # the wider sensitivity sample
```

A smoke or `--all-ties` run writes to its own `.rds`, never over the default.

Memory: the full universe densifies to 2,592 × 2,915 integer matrices, about
30 MB each. Four dyadic covariates over five periods plus the offsets comes to
roughly half a gigabyte of R memory. That is the cost of carrying the full risk
set; `--sample` works smaller.

`R/build_networkdynamic.R` is unchanged and remains the descriptive path for
`tsna`. A `networkDynamic` is a continuous-time object and is not a TERGM input.
