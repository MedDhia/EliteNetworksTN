# Inference tiers: what is read off the page, and what is reasoned from it

Four strategies widen coverage beyond what a single dyad-anchored pass can
reach. Each is a **labelled, additive tier** rather than a loosened threshold,
and each is droppable in one filter. That discipline is not stylistic: an
earlier change to this pipeline loosened a guard instead of adding a tier and
silently deleted 372 resolved dyads, 854 spells and 7,171 panel rows.

| tier | what it rests on | where it is labelled | droppable by |
|---|---|---|---|
| kinship ties | an `épouse` / `ép.` / `EP` / `veuve` marker in print | `person_ties.csv`, `relation` | its own layer |
| subsidiaries | a `filiale de <firm>` clause | `org_ties.csv`, `relation = subsidiary_of` | `relation` |
| address corroboration | two spellings at one seat | `org_entities.csv`, `entity_basis = address_corroborated` | `entity_basis` |
| snowballing | an anchor a later pass supplied | `resolution.csv`, `resolve_pass` > 0 and `link_status = snowball` | `resolve_pass == 0` |

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

| pass rule | `snowball_basis` | what it uses |
|---|---|---|
| a named person names their firm | `person_names_org` | the person's own seed organisations as the candidate set |
| a newly named firm names its people | `org_names_person` | the anchor the previous rule created |
| named colleagues name a person | `colleagues_name_person` | two or more co-mentions tied to one seed organisation |

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
