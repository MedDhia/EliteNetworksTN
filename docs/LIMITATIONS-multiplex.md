# Limitations

What this dataset cannot support, stated plainly. Everything here is measured,
not assumed; the figures come from `docs/VALIDATION-multiplex.md`.

## Coverage

**The gazette and the seed sheet cover different populations.** The gazette
publishes acts for every registered Tunisian company; the seed sheet is a
curated elite. So only 39.4% of the 13,630 seed persons acquire a dated event,
while 94% of the hundred highest-degree do, and 87% of the highest-degree five
hundred. Coverage is therefore strongly
correlated with prominence. Any comparison between well-covered and
poorly-covered actors is confounded by that, and descriptive statistics over
"all seed elites" will be dominated by the covered minority.

**Only French is available.** The upstream mirror OCRs French issues only, so
Arabic-language content is entirely absent. Five issues in the window are served
as Arabic under the `/fr/` path; they are detected by script fraction,
quarantined (`status='arabic'` in the manifest), and excluded rather than parsed
as French. Any tie appearing only in the Arabic series is missed.

**The `tribunal-immobilier` series is out of scope.** It has no French OCR at
all, so property-registry ties are not represented.

**Corporate ties cannot go back beyond 2004.** The *annonces légales* series
begins that year, and the window now runs from 1957, so this is the sharpest
discontinuity in the dataset: before 2004 the gazette supports **state
appointments only**, and the whole of 1957–2003 contributes a few dozen dated
corporate ties between them. A rise in corporate or ownership ties over time is
therefore mostly a rise in what the gazette printed, not in what happened.
Never compare corporate density across that boundary.

## Time

**Departures are under-observed.** The window carries roughly ten appointment
formulas for every explicit exit (~14,800 against ~1,400). Most spells are
genuinely right-censored. Replacement inference on single-holder posts recovers
81 departures and organisation dissolution 105 more, and both are
interval-censored upward because the incumbent may have left before the
successor arrived. **A missing terminus does not mean "still in post".**

This has a sharp modelling consequence. 82.1% of dated spells are
right-censored (3,519 of 4,287), and across the window the year-on-year
dissolution rate *falls* from 11.1% to 5.8% while edge count grows 919 to
3,685. No account of Tunisian elite careers makes ties steadily harder to lose
across the 2011 revolution: what the falling rate measures is the probability
that an exit has been printed by the end of the window. So a TERGM or STERGM
dissolution parameter fitted here estimates gazette publication behaviour, not
tie duration. Model formation only, or restrict to the 1,073 ties whose exit
was actually observed. `docs/TERGM-multiplex.md` sets out both.

**Undated seed ties carry no dates, deliberately.** 27,585 spells come from the
seed sheet with `evidence_tier = 'seed_undated'` and no onset or terminus.
Assigning them dates would manufacture the variation the dataset exists to
measure. They appear in panel snapshots with `certainty = 'undated'` and must be
excluded from any survival or event-history model.

**The seed sheet's as-of date is unknown.** Internal evidence brackets it: the
sheet contains a Mechichi government node (September 2020 – October 2021) and no
Bouden government, so it was compiled in that interval. Every `left_censored`
flag on a seed tie depends on this, and it should be pinned down with whoever
compiled the sheet.

**Act dates can precede the observation window.** An issue published in 2008 may
report an act from 2006, so some spells open before 2008-01-01. This is correct
and useful, but it means onset dates are not confined to the window even though
the observation period is.

**89 parsed termini were withdrawn.** Where a parsed end preceded its own start,
the end was removed and the spell reverted to right-censored rather than being
clamped to zero length. A further 19 spells legitimately open and close on the
same day.

## Identity

**Homonymy is irreducible from text alone.** "Mohamed Trabelsi" matches over
1,500 gazette pages across seven decades. Resolution runs on the (person,
organisation) dyad, and every resolved link has organisation agreement — a
name-only link is never treated as an identification. Even so:

- 4,832 dyads are `ambiguous` and queued for hand coding. These are cases the
  matcher declines to decide, not cases it decided wrongly.
- 62 resolved persons hold more than 12 dyads, which usually indicates several
  people merged into one. `PERSON_TRABELSI_MOHAMED` is the worst case at 89 and
  should be treated as unreliable until hand-checked.
- 161 overlaps remain on posts only one person can hold at a time, which is a
  further pointer to merged identities.
- Precision will be worse for common names than rare ones. That bias is
  correlated with how ordinary a person's name is, which is not random with
  respect to class or region. Report results with and without ambiguous links.

**Name containment is genuinely ambiguous.** Treating a shorter name as the same
person as a longer one containing it is right for the maiden-plus-married form
common for Tunisian women (`Aicha Driss` → `Aicha Driss Jenayah`) and wrong when
the shorter name is a given-name pair (`Mohamed Khalil` → `Mohamed Khalil Ben
Ammar`). Both have the same shape, and distinguishing them needs knowledge of
whether a token is a given name or a surname. These land in review.

**249,333 gazette-only candidate persons are retained, unclustered beyond an
identity key.** They are mostly non-elite officers of small firms, but they are
also where new elite entrants would appear. They have not been vetted.

**Four inference tiers widen coverage beyond what the dyad anchor reaches, and
each carries its own failure mode.** See
`docs/INFERENCE-TIERS-multiplex.md` for the design and the measurements; what
follows is what can go wrong with each. All four are labelled and droppable in
one filter, which is the point of labelling them.

- **Snowballed links propagate their own errors.** A link made from an anchor
  a previous pass supplied is only as good as that anchor, and a wrong anchor
  is reused by every later pass. Ambiguity blocks a snowball by the same
  margin rule the first pass applies, and a tie between two candidate
  organisations is refused rather than broken — but neither guard catches a
  confident wrong anchor. `resolve_pass` records which round named each row,
  so the propagation is measurable: filtering to `resolve_pass == 0`
  reproduces the single-pass build exactly, and dropping one round at a time
  shows what each contributed. Downstream these carry
  `evidence_tier = gazette_snowball`, kept apart from `gazette_inferred`
  because an inference rests on a name being unique corpus-wide and cannot
  propagate.
- **Address corroboration can merge a parent with its subsidiary.** Two firms
  at one seat sharing a name stem is the commonest false positive, which is
  why the label test uses `token_sort_ratio` rather than the containment-prone
  `token_set_ratio`, and why a key carrying a matricule is never merged on its
  address. The cap on firms per address (4) is a judgement read off a steep but
  long-tailed distribution; `orgentity --sensitivity` reports the merge count
  at five settings. Where it fires wrongly it *overstates* a firm's degree,
  the same direction as the merge hubs it was built to help correct — so the
  tier is worth dropping in any analysis that turns on organisation degree.
- **The kinship layer is not usable as built, and the number is 14.** 8,769
  kinship markers were extracted; 18 had both ends named; 14 became dyads over
  28 people. The rule that both spouses must resolve to *seed* persons is
  correct for identification and wrong for this layer's purpose: a marriage
  linking a seed elite to someone outside the sheet is how an elite family
  extends, and that is exactly the tie it refuses. The 8,749-row review queue
  is the layer's real product. Do not compute anything on 14 dyads.
- **Kinship ties are as good as the person resolution under them.** A tie whose
  endpoints are two merged homonyms is a marriage between two composites. The
  tier that is weakest here is flagged: `evidence_tier = kinship_inferred`
  marks a dyad with at least one end named by name rarity rather than by an
  organisation agreeing. Separately, `NAME` allows at most five tokens, so a
  long Tunisian name loses its leading given name ("Malika Bent El Haj Mhamed
  Sghaier" → "Bent El Haj Mhamed Sghaier"). That predates this tier and
  affects role events the same way, but it lands on the person side of a
  kinship tie too.
- **A marriage has no observable start.** The gazette does not publish
  weddings, so every `spouse_of` onset is left-censored without exception and
  `onset` is empty by construction. A duration analysis over this layer would
  be measuring how often a couple appear in print. Only `widow_of` bounds a
  terminus.
- **`maiden_name_of` is a family-name link, not a parent edge.** It says which
  family a woman was born into, not who her father is. It carries
  `is_marriage = 0` and must be excluded from any marriage count; the
  validator checks that at ERROR level rather than reporting it, because a
  `née` marker read as a marriage invents a husband and the resulting tie
  looks entirely plausible on inspection.
- **A stated residence is not an identifier.** Two brothers share a house, so
  a residence is scored and never matched on. It is used in one place only: to
  *refuse* a name-rarity inference where one name key appears at two different
  addresses. Absence of an address is not treated as agreement — most mentions
  state none.

**Structural holes may be artefacts, and the exposure is measured rather than
assumed.** A hole this pipeline manufactured by failing to resolve an identity
is indistinguishable from brokerage, which is what a network analysis is
looking for — so it is a false finding, not a blemish. `make holes` reports
the network twice, as asserted and with every declined link admitted, because
neither is the truth and the width of the interval is the honest statement:

| layer | exposure |
|---|---|
| person-organisation, all years | 16.6% |
| person-organisation 1957–2010 | **19.7%** |
| person-organisation 2011–2026 | 11.9% |
| **organisation ownership** | **50.8%** |
| kinship | 0.0% (true zero: the queue bridges nothing among 28 nodes) |

Two things to carry from that table. **Pre-2011 exposure exceeds post-2011**,
so the era most substantive claims concern is the era with the most
false-hole risk. And **ownership at 50.8% is the largest in the dataset** —
that layer admits a dyad only where both ends resolve to seed organisations,
so 10,622 one-end-resolved observations sit out by design; admitting them
would connect half again as many firm pairs as the layer asserts. Any
structural-hole claim about ownership has to carry that interval.

27,656 suspect co-references are enumerated in `suspect_holes.csv` — 23,424
organisation pairs plausibly one firm, 4,232 person pairs plausibly one
person — each with its basis, so none needs taking on trust.

**The low-degree periphery is 74% confirmed sparse, and 26% is not.** Of 5,878
persons with 1 or 2 ties, 4,374 have no additional tie anywhere in the
evidence; 1,504 do, including **845 pendants whose position would change in
kind** rather than degree — a degree-1 node has no closure and no brokerage,
and a second organisation makes it a broker. `low_degree_audit.csv` is the
worklist, ordered by how much each node's position would move. A further 87
persons are reported as **unanswerable** rather than counted, because two or
more resolved nodes share their name key and "the same name elsewhere" is not
evidence about either of them. Any claim about who is peripheral to this
network should be read against that file.

## Extraction

**The accuracy figures are out of the scope of their own evidence.** Precision
0.982 and recall 0.967 were coded on **2008–2012** blocks and are quoted below
for a dataset that now spans **1957–2026**. They are not wrong; they describe
five years of seventy. Three things changed when the window widened, and each
is a different extraction problem:

- **before 2004** the corpus is almost entirely state acts — the commercial
  register in this mirror effectively begins in 2004 — so the clause families
  being matched are different ones;
- **the 1960s–80s scans** carry the worst OCR in the corpus, where digit
  confusion (4 for 6) and broken diacritics are routine;
- **after 2012** the register continues but the political vocabulary changes,
  and five of the seed sheet's seven governments sit here.

`python -m elitenet.gold draw --eras` allocates a sample equally across eras
rather than proportionally, and `score` then reports precision per era into
`docs/GOLD-SCORE-BY-ERA-multiplex.md`. Until those rows are coded, treat the
figures below as measured for 2008–2012 and **unmeasured** elsewhere —
unmeasured, not good.

**Precision 0.982, recall 0.967 on 2008–2012 — measured, but by a self-audit.**
A stratified sample of 402 blocks was drawn with a fixed seed (`gold/`, seed
`20260912`); 112 extracted events and 75 blocks were coded against the printed
French.

| | estimate | 95% CI | basis |
| --- | --- | --- | --- |
| Precision | **0.982** | 0.937–0.995 | 112 events judged; 110 correct |
| Recall | **0.967** | 0.886–0.991 | 60 ties stated in 43 relational blocks; 2 missed |

Two properties of the error profile matter more than the headline numbers.
**No event was spurious**: not one of the 112 asserted a tie the text does not
state. Both errors were misattributions — one name that the source itself runs
together without a separator (`Messieurs Russo Francesco Chiapparone Carmine`
is two people), and one empty organisation name. Errors of that kind degrade a
variable; they do not invent a relationship. And the two recall misses are of a
single structural kind: the action cue fires on a heading that names no person
while the parties appear in a later clause, so nothing links them.

**These figures are a self-audit and must not be published as independent.**
They were produced by the same agent that wrote the extraction rules. That is a
real check on a rule-based parser — every judgement was made against the
printed French, not against the code, and it found and fixed twenty defects
(see `docs/GOLD-FINDINGS-multiplex.md`) — but it is not independent,
and it is a small sample. The seed is fixed, so any stratum can be re-coded by
someone else and compared on exactly the same blocks. Do that before quoting a
number in a paper.

**Roles are unmapped in some events.** Where a role phrase falls outside the
controlled vocabulary the verbatim form is kept and the event flagged
`needs_review`, rather than being forced into the nearest category.

**The generic-name merge was a matcher defect, and the cause has been found
and fixed.** The symptom was large. 288 organisations — 383 counting each
organisation once per identifier kind, which is how `make validate` reports it —
carried ten or more values of a single hard identifier; the worst,
`LA CONSULTING`, carried **1,606 distinct matricules fiscaux** over 3,739
observations, and short generic fragments — `SOCIETE GENERALE` (647 values),
`BATIMENT +` (635), `SA CONFECTION` (532) — collected every firm whose name
began with those words.
Such a node does not degrade a variable; it **fabricates a hub**, and any
degree, centrality or closure statistic computed over it is meaningless. Of
4,248 identifier conflicts measured on that view, 3,638 read as merges and only
610 as OCR damage.

The cause was not a property of the sources or of the seed sheet. Two ordinary
decisions compounded. `resolve.best_org_match` scored its fuzzy tier with
`fuzz.token_set_ratio`, which treats **containment** as identity: it returns
about 1.0 whenever the seed label's token set is a subset of the mention's,
however much else the mention says —
`token_set_ratio("comptoir tunisien de batiment", "batiment") == 1.000`. And
`seed.py` mints an organisation id from the label with legal-form words
stripped, so a seed firm called "SOCIETE TROIS" became `CO_TROIS` with
`label_normalised = "TROIS"` — the French for three, at seed degree 1. It then
absorbed every mention containing that word, including the address `Route de
Sidi Mansour km 6 Sfax` and the clause fragment `pour une periode limitee de
trois ans`, and ended as the highest-degree organisation in the org–org layer
at 1,003 tie endpoints.

**The fix removes no data.** It has two parts, both set out in
`docs/ORG-IDENTITY-multiplex.md`. First, a token-specificity gate: a fuzzy
match must rest on at least one token with low document frequency in the
corpus. Over the 199,608 distinct organisation mentions, CONSULTING appears in
4,738 and SFBT in 3. Token count is not the signal — most single-token seed
labels are proper names (SFBT, TUNISAIR, CONECT) where containment matching is
exactly right — so the gate is on document frequency, configured in
`config/scope.yaml` as `org_identity.discriminating_df_share`. That threshold
is a judgement, not a boundary found in the data: the narrowest observed gap is
TROIS at 143 against TUNISAIR at 22, about 6x. Second, a new organisation
**entity** layer (`make orgentity`, `data/processed/org_entities.csv`) keyed
matricule fiscal → RC number → normalised mention. The matricule both splits
hubs and joins spelling variants: 19,795 matricules cover more than one
spelling, folding 52,683 spellings into single firms, so the entity key raises
coverage rather than lowering it. Nothing was dropped — the seed link and the
basis that produced it are retained on every entity, so the previous view is
exactly reproducible, and a validator ERROR check asserts that every
organisation mention in `events.csv` reaches an entity. Organisation nodes
still carrying ten or more values of a single hard identifier after the
rebuild: **130**, against 288 before, with the worst falling from 1,606
matricules to 154. Every one of them is a **seed** node and not one is an
entity, which locates the residual precisely: it is not the matcher any more
but `seed.py`'s own collapse, where names that normalise to a very short
string (`SOCIETE M` normalises to `M`) or that hundreds of firms genuinely
share (*Société de Promotion Immobilière*) get one node. No name-based method
can separate firms that really do share a name; the entity key can, and does.

**The two layers were affected very unevenly, and the person side is largely
unaffected.** Only 258 of 10,844 resolved person–organisation dyads (2.4%) were
anchored on a hub, because person resolution is dyad-anchored: a person is
resolved only where the organisation agrees, so a generic organisation match
rarely carried a person match with it. The org–org layer was the casualty, at
2,034 of 3,104 observations (65.5%), because `orgties.py` has no dyad to anchor
an endpoint and resolves each one on its own. So the bipartite panel was little
distorted by the defect and is little changed by the fix; the org–org layer is
where the difference lies. Resolved org–org observations after the rebuild:
**4,018, up from 3,104**, and org–org spells 8,178 up from 6,928. The layer
*gained* data because the old code had been deleting it: two firms both
absorbed by one hub read as a firm tied to itself, and `self_match_dropped`
falls from 1,948 to 1,012 accordingly. Top degree in the layer falls from
1,003 to 45.

**Name-keyed entities split one firm across spellings, which is the residual
organisation-identity error.** It is the mirror image of the merge. Only about
a third of events carry a matricule and a sixth an RC number, so most entities
are keyed on the mention, and two spellings of one identifier-less firm stay
separate. Where the merge **overstated** degree, this **understates** it. Treat
organisation degree and centrality as a lower bound over the name-keyed
population, and check whether a result depends on entities with no hard
identifier. Three further residuals stand alongside it. 1.6% of mentions carry
more than one hard identifier — the worst, `Societe de Promotion Immobiliere`,
carries 78 — and an identifier-less event on such a mention is retained as an
`ambiguous_mention` entity that identifies nothing, so those rows must be
excluded from anything asserting that two observations are the same firm.
Seed-sheet collisions persist: distinct seed firms whose labels normalise
identically still share a node id under `seed.py`, with the losers in
`alt_names`, wherever no hard identifier separates them. And the specificity
gate could itself cost legitimate matches; a test asserts that
`"Société SFBT Tunisie"` still matches seed `SFBT`, but the net effect on
resolved dyads is a measured quantity, not an assumption: **10,929, up from
10,844**. Getting there took a second correction. The first rebuild *lost* 372
dyads, because refusing a generic organisation match also removed the dyad
**anchor** — and those are different jobs. Person resolution credits a
candidate only where the organisation agrees across two mentions, which needs
both mentions on the *same* organisation rather than a defensible one, so a
refused match still anchors perfectly well. The anchor now keeps the refused
candidate while `resolved_org_id` carries only identity-grade links.

One reconciliation line remains unexplained and is recorded rather than
resolved: dated spells fall from 13,031 to 12,600 and spell observations from
15,749 to 15,110. The likely cause is consolidation — two spellings of one
firm, joined by a shared matricule, becoming one spell instead of two — but
that is not proven: `spell_observations.csv` does not record every event by
design, so the obvious coverage test is not decisive, and there is no
pre-change baseline for it.

**Organisation resolution remains the weaker half, and it has an independent
check.** A matricule fiscal and a registre-de-commerce number are hard
identifiers: a firm has one of each. So an organisation node carrying two
values of one of them is a defect, and `make orgattrs` reports those into
`docs/ORG-IDENTIFIER-CONFLICTS-multiplex.md`, ordered by how far apart the
values are — a one-character difference is OCR damage, a wholly different
number is a **resolution merge**, and every tie on a merged node is suspect.
This is the signal that exposed the hubs, and it is what the entity key is
audited against, so it is still the check to read before using
organisation-level structure: a merge otherwise looks exactly like a
well-corroborated match, because both names really do appear beside the same
kind of clause. Conflicts are reported rather than resolved, because some are
genuine re-registrations. `exports/tergm/node_key.csv` still carries
`merge_suspect` and `org_identifiers.csv` still carries `n_values_for_org`;
they are now diagnostics on the entity layer rather than a blocklist standing
in for a fix. This is the counterpart to the merged-homonym warning on the
person side.

Firm names are matched on normalised forms, acronyms and token-blocked fuzzy
comparison — the fuzzy tier now conditional on a discriminating token, with a
refused match recorded as `generic_fuzzy` and kept inspectable rather than
discarded — and both hard identifiers are used where present, with the
deliberate exception that where the two disagree, neither is trusted, since
that disagreement is the merge signal itself. `SICAR`, `SICAF`, `SICAV`, `HOLDING` and `GROUPE`
are deliberately *not* stripped as generic suffixes, because in Tunisian
practice they designate different legal vehicles that share a brand name. Even
so, a group and its investment arm can still be conflated where names are close.

**OCR quality is unmeasured, and it is not uniform across the window.** It is
visibly good in 2008–2012 and visibly worse in the 1960s–80s, which is one of
the reasons accuracy is now reported per era rather than pooled. No character-
or field-level error rate has been computed. The identifier-conflict table is
the closest thing to a measurement: a one-character difference between two
matricules on the same firm is an OCR error caught by arithmetic, and the share
of conflicts of that kind is a lower bound on the digit error rate.

**Addresses and registration numbers are recorded, not verified.** `RE_RC` and
`RE_SIEGE` capture what the notice prints, trimmed at the first following
clause. The trim is tested against sampled captures but it is a heuristic: a
long address that runs into an unusual clause can still carry a fragment of it.
Use `org_addresses.csv` for geography and grouping, not as a verified postal
record.

## Reproducibility

The raw mirror is not committed. `data/raw/manifest.csv` holds a SHA-256 per
file and the upstream `ETag` equals the body MD5, so the corpus can be
re-verified with one `HEAD` per file. If the upstream re-OCRs an issue, its hash
will change and `make verify-mirror` will say which — extraction output would
then differ, and the manifest is what makes that visible rather than silent.
