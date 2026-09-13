# Inference tiers: what is read off the page, and what is reasoned from it

Five strategies widen coverage beyond what a single dyad-anchored pass can
reach. Each is a **labelled, additive tier** rather than a loosened threshold,
and each is droppable in one filter. That discipline is not stylistic: an
earlier change to this pipeline loosened a guard instead of adding a tier and
silently deleted 372 resolved dyads, 854 spells and 7,171 panel rows.

| tier | what it rests on | where it is labelled | droppable by |
|---|---|---|---|
| kinship ties | an `épouse` / `ép.` / `EP` / `veuve` marker in print | `person_ties.csv`, `relation` | its own layer |
| subsidiaries | a `filiale de <firm>` clause | `org_ties.csv`, `relation = subsidiary_of` | `relation` |
| address corroboration | two spellings at one seat | `org_entities.csv`, `entity_basis = address_corroborated` | `entity_basis` |
| identifier bridge | a matricule or RC number on two filings | `resolution.csv`, `org_match_basis = identifier_bridge` | `resolve_pass == 0` |
| snowballing | an anchor a later pass supplied | `resolution.csv`, `resolve_pass` > 0 and `link_status = snowball` | `resolve_pass == 0` |
| **national register** | an identifier the RNE also carries | `rne_org_links.csv`; `org_match_basis = hard_identifier` | delete `rne_org_links.csv` |

## What each tier actually produced

Measured on the 781,233-event rebuild, against the 689,169-event baseline.
These are the outcomes, not the potentials, and two of them are much smaller
than the marker counts further down this document would suggest.

| tier | yield | verdict |
|---|---|---|
| **national register** | `org_by_hard_identifier` 4,639 → **7,546 (+63%)**; **2,455** gazette misattributions corrected; **+29** named persons | **quality, not coverage** |
| **identifier bridge** | **672 organisations named** — the largest single snowball channel, ahead of person-anchoring at 537 | works as intended |
| snowballing overall | 460 new person links (`link_status = snowball`), converged at pass 3: +1,104, +565, then 0 | works; cap of 12 never bound |
| subsidiaries | `org_tie` events 30,161 → 30,333 | small and correct |
| address corroboration | 890 entities merged from 20,704 candidate pairs; name-keyed share 62.0% → 61.2% | **high precision, negligible coverage** |
| **kinship ties** | **13 dyads** from 8,769 markers in print; 8,750 queued | **not usable as built** |

Resolution overall: `resolved` 11,036 → **11,286**, `inferred` 11,420 →
12,851, `snowball` 460 new. Named 22,456 → **24,597**. Almost all of that gain
is in the labelled tiers rather than the dyad-anchored count, and saying so is
more useful than a headline that averages them together.

The snowball's per-channel yields are **lower** than in the pre-register run
(745/594/256/241) for a reason worth reading forwards: work moved earlier in
the pipeline. What pass 0 now names by registration number, later passes no
longer have to reach by resemblance. Section 5 has the full accounting.

Nothing here changes pass 0. `resolution.csv` filtered to `resolve_pass == 0`
reproduces the previous build exactly, and `evidence_tier = 'gazette_dated'`
still means what it always meant: the organisation agreed and the date is in
print.

---

## 1 · Kinship: marriage read off a shareholder line

"Mme Senda Bent Khaled Chaabouni épouse Khlil Babbou : 10 parts" is a
shareholding line that also states two of the shareholders are married. The
grammar had captured the marker since the first build, into a column called
`person_married_name`, and **no tie had ever been made of it**.

### Two relations, not one

The single capture group folded together markers that mean opposite things:

| printed | means | relation |
|---|---|---|
| `X épouse Y`, `X ép. Y`, `X EP Y` | X is married to Y | `spouse_of` |
| `X veuve Y`, `X vve Y` | X is the widow of Y | `widow_of` |
| `X née Y` | Y is X's **natal surname** | `maiden_name_of` |

`née` is not a marriage. Reading it as one manufactures a husband out of a
birth name, and it is 8,277 of the 41,088 markers in the corpus. It is kept —
a natal surname is real kinship evidence — in its own relation, with
`is_marriage = 0`, and it is excluded from every marriage count.

### Why the yield rose 40×

The marker was only ever matched after a **title**: `RE_PERSON`,
`RE_CHARGE`, `RE_NOMME` all begin with `Monsieur|Madame|M.|Mme|…`. Most of
these markers sit in prose that never titles the woman:

> la nommée Fekria Bent Mohamed Osman **épouse** Ben Salem a vendu…
> sa mère M'na Bent M'barek Ben Guiza **veuve** Najar Ben Ali Khai…

`RE_NAME_LINK` drops the title requirement. Precision is carried by
`clean_name`, which rejects single tokens and boilerplate: of 41,088 raw
captures it discards 35,123 — "Son épouse Khadija" among them, where *son* is
the French possessive — and leaves 5,965 where **both** ends are full
multi-token names.

**Those 5,965 are grammar captures, not ties, and the gap between the two is
the whole story of this tier.** Extraction emitted 8,769 kinship events across
the corpus. Of those, **18 had both ends named and 14 became dyads**, over 28
people. The other 8,749 are in `person_ties_review_queue.csv`: 8,344 with
neither end named, 405 with one.

The cause is the membership rule below — both spouses must resolve to *seed*
persons — and the arithmetic is unforgiving. The seed sheet holds 13,630
people; the chance that both members of a couple named in an arbitrary company
filing are among them is very small. Worse, the rule discards exactly the
interesting case: a marriage linking a seed elite to someone outside the sheet
is how an elite family extends, and that is precisely the tie this rule
refuses.

So the layer as built cannot support analysis, and the 8,749-row queue is its
real product. Admitting gazette-only persons as kinship endpoints would fix
it, at the cost of widening the node universe and breaking the validator's
closed-world endpoint check. That is a design decision and it has not been
taken.

Bare `EP` is included, as asked. It is rare (122 blocks) and ambiguous in
isolation — "Raison sociale : EP Technology" is a firm — but harmless in this
grammar, because the marker only ever matches immediately after a person name.

### What becomes a tie, and what does not

Both ends must carry a person id.

* A capture whose other side is a **bare surname** ("épouse Bouricha") names no
  identifiable second person and yields no tie. It is not lost: it stays as
  `person_married_name` on the role event, unchanged.
* Where **one** end resolves, the observation goes to
  `person_ties_review_queue.csv` with the failing mention named, not dropped.
* The block's organisation is carried as the resolver's **anchor**, never as a
  claim of office. `spells.KINSHIP` excludes these event types from the
  person-organisation spell builder — without that exclusion the fallback
  `role = "unspecified"` would make every spouse named in a company filing a
  member of it.

### Censoring

The gazette does not publish weddings, so **no `spouse_of` onset is ever
observed**: `onset` is empty, `onset_hi` is the first date the tie was printed,
and `left_censored` is `True` without exception. A duration read off this layer
would be measuring how often a couple appear in print.

`widow_of` is the one marker that dates a boundary — the marriage had ended by
the filing date — and it bounds `terminus` from above, the way a cession bounds
an ownership tie. That is why it is a separate relation.

The **upper** edge is the honest problem, and it is worse here than in the
ownership layer. A marriage first seen in 1960 and never seen to end runs
through to the end of the window, which asserts in 2026 what the sources
support only for 1960 — and people die. Nothing in the evidence resolves it, so
the rows are emitted (dropping them would assert the opposite: that the
marriage ended when the printing stopped) and `last_seen` is carried on every
spell so an analyst can truncate at the last sighting. `certainty` is never
better than `probable` anywhere in this layer, for the same reason.

This layer is **one-mode over persons**, in its own tables. Putting a
person-person tie in `spells.csv` would break mode-blocked vertex ids,
`bipartite = n1`, `gwb1degree` and `gwb2degree` silently.

---

## 2 · Subsidiaries in the ownership layer

`RE_ORG_BRANCH` matched `succursale` only. `filiale` — 1,709 blocks — was not
matched at all, so the ownership layer was missing the one clause that names a
corporate parent outright.

`subsidiary_of` runs **parent → subsidiary**, the same direction as
`shares_acquired` (holder holds a stake in target), and is in `OWNERSHIP`.
`branch` deliberately is not: a *succursale* has no legal personality, so the
relation is structural and its two ends are not two firms.

Only the possessive form counts:

| printed | tie |
|---|---|
| `filiale de la Banque de l'Habitat` | Banque de l'Habitat → subject |
| `filiale du groupe Poulina SA` | Poulina → subject |
| `ouverture d'une filiale` | none — no parent named |
| `création d'une filiale commerciale` | none — no parent, no child |

A pattern that did not require `de <firm>` would emit ties with one end
invented.

`détenue par` was measured and **rejected**: its 2,901 blocks are almost
entirely share cessions between individuals ("38 parts sociales détenues par
Madame Dora Christou"), not parent-subsidiary statements. It would have added
noise to the layer, not subsidiaries.

---

## 3 · Addresses

### 3a · The seat, as corroboration for organisation identity

This is the only tier that **merges**, and it exists to attack the residual
error the identifier tiers cannot reach: two spellings of one identifier-less
firm stay apart, which *understates* degree where the merge hubs overstated it.

Measured over 187,365 distinct normalised addresses:

| firms at one address | addresses |
|---|---|
| 1 | 170,956 |
| 2 | 10,438 |
| 3 | 2,761 |
| 4 | 1,165 |
| 5–12 | 1,699 |
| tail | 253, 219, 99, 94, 83 … |

The tail is domiciliation: `6 rue ibn hazm cité jardins le belvédère 1002
tunis` carries 253 firms. So an address alone is never identity. Four
conditions, all necessary:

1. **both keys name-keyed** — a key carrying a matricule or RC number is
   already identified, and two *different* identifiers at one address are two
   firms sharing a building;
2. a shared normalised address of **≥ 12 characters** — "à Tunis" corroborates
   nothing;
3. the address borne by at most **4** name-keyed firms — the knee in the
   distribution above, and a judgement, so the sensitivity of the merge count
   to it is reported rather than asserted away;
4. labels agreeing at **`token_sort_ratio` ≥ 0.85**.

Condition 4 is the containment-safe metric, not `token_set_ratio`. The set
ratio treats containment as identity — it is what built the merge hubs — and
two firms at one seat are commonly a parent and a subsidiary sharing a stem
("Poulina" inside "Poulina Group Holding Industries"). Merging those would be
the same error in a new place.

**Measured, the tier is high precision and negligible coverage, and that is
worth stating plainly rather than implying otherwise.** It considered 20,704
candidate pairs sharing a discriminating seat and **refused 19,473 of them
(94%)** on the label test, discarded a further 1,404 address groups as
domiciliation, and merged **884 entities** — 0.36% of 235,052. Name-keyed
share moved 62.0% → 61.2%, no more.

That 94% refusal rate carries information of its own: most firms sharing a
seat genuinely have unrelated names, which means they *are* different firms
and the hole between them is real. Those refused pairs are the population
`holes.py` re-examines, because a refusal that is right for *identity* still
leaves a pair worth listing when the question is whether a *hole* is real.

A merged entity's `entity_basis` becomes `address_corroborated`, so the tier is
visible and droppable. Where one side had adopted a seed organisation's id, the
other side joins it: a merge may add spellings to a seed node, never rename
one. The result is independent of iteration order.

### 3b · The residence, as a discriminator for persons

`resides_at` events carry `person_address` and `person_address_normalised`,
extracted wherever the gazette states where someone lives — "demeurant à la
plage - Soliman", "domiciliée au 12 rue de Rome Tunis". Run outside the domain
filter, like kinship: the property and judicial notices the pipeline skips as
non-relational are where most stated residences are.

An address is **not** an identity claim — two brothers share a house — so it is
recorded as an attribute and left to be *scored*, never matched on. What it
buys is the discriminator the corpus otherwise lacks: two mentions of "Mohamed
Trabelsi" at one address are one man, at two addresses they are two. Merged
homonyms are the largest remaining error in the person layer and the reason
degree-ranked percolation on it is not yet trustworthy.

An election of address at a lawyer's office — "élisant domicile en l'étude de
son avocat" — is excluded. Admitting it would put every litigant in a case at
one address and make them homonyms of each other, which is the exact error the
column exists to fix.

---

## 4 · Multi-seed snowballing

Resolution is dyad-anchored: a person is credited only where the organisation
agrees. That leaves a large population unreachable in one pass — not because
the evidence is absent, but because it arrives in the wrong order. The firm is
identified in one filing and the person in another.

Snowballing runs the anchor in **both** directions and repeats until nothing
new is named.

| pass rule | `snowball_basis` | what it uses | yield |
|---|---|---|---|
| **a known identifier names the firm** | `identifier_names_org` | a matricule or RC number seen on another filing | **745** |
| a named person names their firm | `person_names_org` | the person's own seed organisations as the candidate set | 594 |
| named colleagues name a person | `colleagues_name_person` | two or more co-mentions tied to one seed organisation | 256 |
| a newly named firm names its people | `org_names_person` | the anchor a previous rule created | 241 |
| *refused by the ambiguity guard* | — | — | *765* |

### The identifier is an edge, not a lookup

This is the largest channel and for a long time it was not a channel at all.
The matricule-fiscal map was built **once, before the loop**, and seeded
**only** from organisations named by an identity-grade *name* match. So the
strongest anchor in the corpus fired once and then sat idle: a firm named in
pass 1 by its own officer contributed its matricule to nothing, and no other
filing printing that number benefited.

That is backwards. **A name propagates a resemblance; a registration number
propagates an identity.** It is the one channel where compounding carries
almost no error risk, and it was the one channel the snowball was not using.

The map is now live — seeded from what pass 0 learned, re-harvested after
every pass from every organisation named by any route — and one flat map
rather than one per column, which is what lets a firm known by its matricule
be reached by its RC number through any filing carrying both.

The scale it works on, measured over the rebuild: of **118,782** distinct
identifiers, **29,731 span more than one spelling** of the same firm, bridging
**80,805 spellings**. Those were previously connectable only by name
similarity — the mechanism that built the merge hubs.

**Conflict discipline matters more here than anywhere else**, because an
identifier error propagates exactly as confidently as an identifier truth:

* a value naming two organisations is **deleted and blacklisted**, never
  resolved by majority. 472 were refused this build, and `validate` reports
  4,464 identifier values sitting on more than one organisation node. Taking
  the modal side would bury the signal that says a resolution merged two
  firms.
* two identifiers on one filing pointing at two organisations name neither.
  16 filings this build.

One caveat on the 80,805: some bridged "spellings" are extraction noise rather
than spellings. `909923K` links 21 mentions, one of which is
`"1. Société anonyme ne faisant pas appel public à l'é"` — a clause `org_name`
misread as a company in a block that printed a real matricule. The bridge will
not invent a false firm from it, but it pulls junk mentions into a real firm's
mention set. The fix belongs in `org_name`, not here, so 80,805 is gross
potential rather than clean coverage.

The first rule is what makes the second possible, and the second is what makes
this a snowball rather than one extra rule.

### Why a lower floor is defensible

Rule 1 matches at `0.80` against the person's own organisations, below the
global identity floor of `0.88`. The justification is not leniency: the search
space has collapsed from ~10,000 seed organisations to the handful this person
is actually tied to, so the same string similarity carries far more
information.

It uses `token_sort_ratio`, for the same reason the address tier does. Inside a
small candidate set the token-specificity gate has no corpus statistics to work
with, so the metric itself has to be the one that refuses containment.

### The guards

* **Ambiguity blocks a snowball**, by the same margin rule pass 0 applies. A
  snowball that guesses between two equally good candidates propagates the
  guess into every later pass.
* **A tie between two organisations is no anchor.** Rule 3 requires a single
  organisation attested by at least two named colleagues; a tie returns
  nothing, because taking either would be a coin toss recorded as evidence.
* **Nothing is ever downgraded**, and pass 0 rows are untouched.
* At most three passes, and the loop stops as soon as a pass adds nothing.

### Why the pass number is recorded

A snowball propagates its own errors. `resolve_pass` is what makes that
propagation **measurable** rather than merely suspected: a reader can drop the
whole tier, or any single round of it, and see what changes. `spells.py` gives
these links `evidence_tier = gazette_snowball`, kept separate from
`gazette_inferred` because the two fail differently — an inference rests on a
name being unique corpus-wide and cannot propagate; a snowball can.

---

## 5 · The national register as an identity spine

The Registre National des Entreprises publishes what the gazette does not: the
matricule fiscal and the RC number as **primary keys**, each with the firm's
registered name beside it. **203,788 companies** (from 393,788 rows -- see
below), 83.0% carrying a French name.

The gazette already prints these numbers; what it does not give is an
authority on which firm a number belongs to. Until now that authority was
name similarity, applied to whatever spelling the filing happened to use.

### The register joins; the name only labels

`rne.link_identifiers` matches on the **identifier**, and uses the register's
name for one purpose only — to decide which seed organisation, if any, that
identifier denotes. The name never joins. Of 118,584 distinct identifiers the
gazette prints, **87,288 are in the register (73.6%)**; those name **5,251
seed organisations**, and `resolve` reads **10,611** of them as identity-grade.

A contradiction *inside* the register is not resolved by picking a side:
**2,952** identifiers appear on two register rows with different names and are
dropped from the map entirely. The register is the authority, so a
disagreement inside it means the question has no answer from here.

The 31,296 identifiers the register does not carry are **listed, not judged**
(`rne_unmatched_identifiers.csv`). A matricule the register does not know is
either OCR damage or a firm that predates the register, and nothing available
here tells those apart.

### What it changed, on both sides

| | before | after | |
|---|---|---|---|
| `org_by_hard_identifier` | 4,639 | **7,546** | **+63%** |
| `org_resolved` | 86,197 | 89,062 | +2,865 |
| identifiers seeded into the snowball | 14,290 | 18,306 | +28% |
| **`register_overrode_gazette_match`** | — | **2,455** | misattributions corrected |
| identifier values refused as conflicting | 472 | **1,166** | conflicts *exposed*, not created |
| `resolved` (dyad-anchored persons) | 11,032 | **11,286** | +254 |
| `inferred` | 13,039 | 12,851 | −188 |
| `snowball` | 497 | 460 | −37 |
| **total named persons** | 24,568 | **24,597** | **+29 (+0.1%)** |

Read those last four rows together, because the headline is the small number.
254 people gained a **dyad anchor**, but about 225 of them were already named
by a weaker tier: the register mostly **promoted** existing people onto better
evidence rather than finding new ones. Net new named individuals: **29**.

That the snowball's own yield *fell* (672/537/225/235 against
745/594/256/241) is the same effect seen from the other end. Work moved
earlier in the pipeline: what pass 0 now names by registration number, later
passes no longer have to reach by resemblance. The snowball also converged one
pass sooner, because the register supplied up front the identifiers the
snowball previously had to harvest.

The 1,166 refused conflicts are worth stating plainly as a **gain**. Feeding
18,306 register-backed mappings in made more identifier values demonstrably
name two different organisations — conflicts that name similarity had
previously papered over. A refusal here is a merge hub not built.

### The person table is deliberately not matched

The register's natural-person table has **315,659 people and 4 French names
(0.00%)**. It is Arabic-only. Transliterating 315,659 Arabic names against a
French seed roster, with no identifier on the person side to check the result
against, is precisely the merge-hub failure mode with its one safeguard
removed. `rne.person_register_summary` therefore **counts and reports**; it
returns no links of any kind, and a test pins that it never will.

### What this tier is, and what it is not

**The register is a data-quality instrument, not a coverage instrument.** It
made organisational identity substantially better — 2,455 corrections and a
63% rise in hard-identifier matches — and moved the person count by 0.1%.

That is not a disappointment; it locates the bottleneck. The person side is
limited by the **13,630-name seed roster**, not by organisational
identification: **306,324 gazette-only persons** remain outside it. No
improvement in firm identity can name a person the roster does not contain.
Widening the person universe is a separate decision about who counts as an
elite, not a resolution problem.

---

## Known residual errors

* **Truncated left-hand names.** `NAME` allows at most five tokens, so "Malika
  Bent El Haj Mhamed Sghaier" is captured as "Bent El Haj Mhamed Sghaier". This
  predates these tiers and affects the person side of a kinship tie the same way
  it affects a role event.
* **Name-keyed entities still split.** Address corroboration reaches only the
  pairs that share a stated seat; most identifier-less firms state no address.
* **Person-side homonym hubs remain.** `resides_at` supplies the discriminator
  but is not yet wired into the person score, so `PERSON_TRABELSI_MOHAMED` at
  209 seed ties is still a merge of several men.
* **`maiden_name_of` is a family-name link, not a kinship edge to a parent.**
  It says which family a woman was born into, not who her father is.
