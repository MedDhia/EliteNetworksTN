# The organisation-to-organisation layer

`make orgties` builds a second network alongside the person-organisation
panel: organisations tied to organisations, mostly by shareholding. This
documents what it supports and — more to the point — what it does not.

Read this before estimating anything on it. The short version is that the
clause which dominates the source **confirms** a standing holding at a filing
date rather than dating its start, so onsets in this layer are overwhelmingly
left-censored, and a duration model over them would be measuring how often
firms file rather than how long they hold.

## Why it is a separate layer, not extra rows

The person-organisation network is strictly two-mode, and the whole TERGM
export depends on that: mode-blocked vertex ids, `bipartite = n1`,
`gwb1degree` and `gwb2degree`, `b1star` and `b2star`. An organisation-to-
organisation tie in `spells.csv` would break every one of those, and break
them *silently* — `network` would still build the object and `btergm` would
still estimate, against a reference distribution containing dyads that cannot
exist.

So the layer lives in its own tables and its own R script. Two properties
follow that do not hold on the bipartite panel:

* **The ordinary closure terms are valid here.** `triangle`, `gwesp` and
  `kstar` count structures impossible in a two-mode graph, which is why
  `docs/TERGM-multiplex.md` forbids them there. On an ownership network they
  are the interesting terms: a triangle is a cross-holding triad, and
  transitivity is what a pyramid looks like.
* **Ties are directed.** *A holds a stake in B* is not *B holds a stake in A*,
  and collapsing the direction would turn a pyramid into a clique.

## Tables

| file | shape |
| --- | --- |
| `org_ties.csv` | one row per resolved (holder, target, relation) observation |
| `org_tie_spells.csv` | the layer as intervals, same vocabulary as `spells.csv` |
| `panel_org_ties_yearly.csv` | ties active per calendar year |
| `org_ties_review_queue.csv` | what a human has to settle |

## What the register actually says

Six clause families are read, and they differ in what they date:

| relation | clause | bears on the interval |
| --- | --- | --- |
| `shares_acquired` | *X a acquis … au capital de Y* | **opens** |
| `capital_subscribed` | *X a souscrit au capital de Y* | **opens** |
| `shares_ceded` | *X a cédé sa participation au capital de Y* | **closes** |
| `shareholder_confirmed` | *Associés : la société X* | confirms |
| `auditor` | *Commissaire aux comptes : la société X* | confirms |
| `branch` | *succursale de la société X* | confirms |

Only the first three date a boundary. The confirmations prove the tie was live
at a filing date and assert nothing about when it began, so they bound the
onset from above and leave it censored below. That is not a limitation of the
extractor; it is what the notice says.

The consequence is a distribution nothing downstream can fix:
`shareholder_confirmed` outnumbers the transfer clauses by more than an order
of magnitude, so most spells in this layer have a known upper bound on their
onset and no lower bound at all.

## How endpoints are resolved

Both ends must resolve to **distinct** seed organisations. The scoring is
deliberately weaker than the person-organisation case, and says so:

```
score = 0.75 · min(holder_match, target_match) + 0.15 · extract_conf + repeat
```

There, a link is anchored on the dyad — the organisation has to agree, which
makes homonymous persons tractable. Here both ends are organisations and there
is no third thing to anchor against, so the score rests on how well each end
matched, how often the pair was seen across issues, and how certain the clause
was. **The weaker end governs**, because a dyad is only as identified as its
worse-identified endpoint.

Two failure modes are handled rather than hidden:

* **A self-tie.** A mention resolving to the subject firm is the extractor
  having read one company as two. Compared on the normalised key resolution
  uses, not the raw string, so *la société Alpha Holding* and *Société Alpha
  Holding* are caught. Dropped, not counted.
* **One end resolved.** The other end is a firm outside the seed sheet, or a
  name the matcher could not place. These used to be dropped with nothing but
  a counter; they now go to `org_ties_review_queue.csv` with the failing
  mention, the seed organisation it came closest to, and that near-miss score.
  This is the adjudicable material in the layer: the resolved end anchors the
  dyad, so a coder has only one name to judge.

## Modelling it

```r
Rscript R/build_org_ownership.R --all-relations
```

Then, in the script's own words:

```r
m <- btergm(nets ~ edges + mutual +
      gwidegree(0.5, fixed = TRUE) + gwodegree(0.5, fixed = TRUE) +
      gwesp(0.5, fixed = TRUE) +          # valid here, not on the bipartite panel
      memory(type = "stability"),
    R = 200)
```

`memory()` takes its lag from the previous element of the network list and so
consumes one period; with a layer this sparse in its early decades, check how
many periods carry any edges at all before reading a coefficient.

## What not to do with it

* **Do not fit a duration or survival model to the onsets.** Most are
  left-censored by construction, and the ones that are not are the transfers —
  a non-random subset, since a transfer is precisely the event that gets filed.
  Any hazard estimated over this layer is an estimate of filing behaviour.
* **Do not read the undated seed ties as contemporaneous with the dated ones.**
  They are carried in the same table with `evidence_tier = seed_undated`
  because dropping them would lose real structure, but the seed sheet is a
  single snapshot. `R/build_org_ownership.R` excludes them unless asked
  (`--include-seed`), and the panel treats them as a static overlay, never as
  evidence about a particular year.
* **Do not compare ownership density across decades.** The commercial register
  in this corpus effectively begins in 2004; earlier issues carry state acts,
  not company filings. A rise in ownership ties over time is mostly a rise in
  what the gazette printed.
