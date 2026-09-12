# Limitations

What this dataset cannot support, stated plainly. Everything here is measured,
not assumed; the figures come from `docs/validation_report.md`.

## Coverage

**The gazette and the seed sheet cover different populations.** The gazette
publishes acts for every registered Tunisian company; the seed sheet is a
curated elite. So only 12.6% of the 13,630 seed persons acquire a dated event,
while 87% of the hundred highest-degree do. Coverage is therefore strongly
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
begins that year. This dataset starts in 2008 by design, but the constraint
matters for anyone extending it backwards: before 2004 the gazette supports
state appointments only.

## Time

**Departures are under-observed.** The window carries roughly ten appointment
formulas for every explicit exit (~14,800 against ~1,400). Most spells are
genuinely right-censored. Replacement inference on single-holder posts recovers
81 departures and organisation dissolution 105 more, and both are
interval-censored upward because the incumbent may have left before the
successor arrived. **A missing terminus does not mean "still in post".**

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

- 1,064 dyads are `ambiguous` and queued for hand coding. These are cases the
  matcher declines to decide, not cases it decided wrongly.
- Six resolved persons hold more than 12 dyads, which usually indicates several
  people merged into one. `PERSON_TRABELSI_MOHAMED` is the worst case and should
  be treated as unreliable until hand-checked.
- 55 overlaps remain on posts only one person can hold at a time, which is a
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

**66,951 gazette-only candidate persons are retained, unclustered beyond an
identity key.** They are mostly non-elite officers of small firms, but they are
also where new elite entrants would appear. They have not been vetted.

## Extraction

**Precision 0.982, recall 0.967 — measured, but by a self-audit.** A stratified
sample of 402 blocks was drawn with a fixed seed (`gold/`, seed `20260912`);
112 extracted events and 75 blocks were coded against the printed French.

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
(see `docs/GOLD-FINDINGS-multiplex-2008-2012.md`) — but it is not independent,
and it is a small sample. The seed is fixed, so any stratum can be re-coded by
someone else and compared on exactly the same blocks. Do that before quoting a
number in a paper.

**Roles are unmapped in some events.** Where a role phrase falls outside the
controlled vocabulary the verbatim form is kept and the event flagged
`needs_review`, rather than being forced into the nearest category.

**Organisation resolution is the weaker half.** Firm names are matched on
normalised forms, acronyms and token-blocked fuzzy comparison, and matricule
fiscal is used where present. `SICAR`, `SICAF`, `SICAV`, `HOLDING` and `GROUPE`
are deliberately *not* stripped as generic suffixes, because in Tunisian
practice they designate different legal vehicles that share a brand name. Even
so, a group and its investment arm can still be conflated where names are close.

**OCR quality is unmeasured for this window.** It is visibly good in 2008–2012
compared with earlier decades, and the calendar recovered 99.6% of publication
dates, but no character- or field-level error rate has been computed.

## Reproducibility

The raw mirror is not committed. `data/raw/manifest.csv` holds a SHA-256 per
file and the upstream `ETag` equals the body MD5, so the corpus can be
re-verified with one `HEAD` per file. If the upstream re-OCRs an issue, its hash
will change and `make verify-mirror` will say which — extraction output would
then differ, and the manifest is what makes that visible rather than silent.
