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

The consequence is a distribution nothing downstream can fix. In the current
build:

| | |
| --- | --- |
| `shareholder_confirmed` | 5,016 |
| `auditor` | 1,108 |
| `shares_ceded` | 253 |
| `shares_acquired` | 195 |
| `branch` | 42 |
| **dated spells** | **2,314** over **2,255 dyads** |
| **left-censored onsets** | **1,865 (81%)** |
| **right-censored** | **2,061 (89%)** |

Confirmations outnumber the transfer clauses by more than an order of
magnitude, so four spells in five have a known upper bound on their onset and
no lower bound at all. The 4,614 undated seed ties carried alongside them are
additional to these counts and are not evidence about any particular year.

The layer is also small relative to the person-organisation panel — 2,255
dyads against 13,031 dated person-organisation spells — for a reason worth
stating: an org-org tie needs **both** endpoints to be seed organisations,
and most counterparties named in an ownership clause are firms outside a
curated elite sheet.

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
  dyad, so a coder has only one name to judge. There are **10,586** of them —
  more than four times the number of resolved observations — and **8,189**
  carry a named near-miss, at a median similarity of 0.63. The queue was
  empty before this, not because there was nothing to adjudicate but because
  it was fed only from a score band that `resolve_org`'s 0.88 floor makes
  unreachable.

* **Both candidate targets.** Where the clause names the company whose shares
  move, that reading and the block's subject firm both go forward sharing an
  `alt_group`, and this stage keeps whichever resolves — the stated target
  first, since it is the targeted capture. Letting it override
  unconditionally was measured and is net negative. Of 1,280 such groups,
  318 resolve at both ends; **119 of those resolve only through the subject
  firm**, and those are exactly the resolutions the old override discarded.

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

* **Exclude the merged organisation nodes first.** `make orgattrs` finds 383
  organisation nodes carrying ten or more values of a single hard identifier —
  the worst, `LA CONSULTING`, carries 1,606 distinct matricules. Those are
  generic name fragments that every firm beginning with those words has
  resolved onto, and they are not degraded vertices but *fabricated hubs*.
  This layer is directed and one-mode, so a fabricated hub is exactly the
  vertex a closure or degree term will pick up. `node_key.csv` carries
  `merge_suspect`; `docs/ORG-IDENTIFIER-CONFLICTS-multiplex.md` lists them
  worst first.
