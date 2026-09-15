# What the gold sample found

Coding the sample against the printed French turned up ten extraction defects.
All are fixed; each is quantified corpus-wide and covered by a regression test
in `tests/test_extract_elitenet.py`. They are recorded here rather than only in
a commit message, because the size of some of them bears on how earlier
versions of this dataset should be treated.

| # | defect | scale | effect |
|---|---|---|---|
| 1 | `SANB3` mapped as management when it is the **Convocations** rubric | 10,422 blocks | A convocation lists a *future* meeting's agenda, so nothing in it has happened. Produced **2,303 invented events**, 1,414 of them capital increases that were only proposed |
| 2 | `org_name()` fell back to the block heading, which is usually the *action* rather than the company ("Nomination d'un nouveau gérant", "Transfert du siège social") | **16,079 blocks (12.3%)** | Wrong organisation on one block in eight. Since the organisation anchors identity resolution, a wrong name loses the tie entirely. Now 0%, with 1.95% honestly empty |
| 3 | Infinitive appointment cues absent | `de nommer` 4,983 blocks, `de désigner` 681 | Appointments silently dropped |
| 4 | `désignation` (noun) not matched, only `désigné` | 2,703 corporate blocks | As above |
| 5 | `en tant que` not recognised as a role marker | 5,909 blocks | Role lost even where the person was found |
| 6 | Person regex case-sensitive on the title | lowercase `monsieur` in 4,169 blocks | 5,840 person mentions missed |
| 7 | A clause-level role was applied to every person named in it | logic defect | Gave a chair and a chief executive the same title, and handed an appointment to a bystander who was only transferring shares |
| 8 | Plural-title enumerations kept only the first name | 1,166 corporate blocks | "Messieurs Foued Noomen et Nizar Frikha" lost the second resignation |
| 9 | One clause could yield only one event type | logic defect | "dissolution totale de la société et la désignation de Mr X comme liquidateur" is a dissolution *and* an appointment; one was always dropped |
| 10 | Association bureaus list the role before the name, the reverse of the corporate layout | **3,746 of 7,144 association blocks (52%)** | Every officer of a newly registered association was missed |
| 11 | Share transfers matched only the unaccented present tense | 1,396 blocks | `a cédé/vendu ses parts` dropped |
| 12 | `dissolution totale/définitive de` and `reconduction du mandat` unmatched | 168 + 75 blocks | Dissolutions and renewals dropped |

## Net effect on the event table

| | events |
|---|---|
| first release (PR #3) | 168,789 |
| after the first five fixes | 173,638 |
| after the next six | 184,439 |
| after organisation-name and name-boundary repair | 192,570 |
| **final** | **197,532** |

Roughly 31,000 real ties were being missed and about 2,300 invented ones
recorded. The two move in opposite directions, so the earlier totals were not
simply low — they were wrong in both directions at once, which is why a
measured sample rather than a plausibility check was needed.

Twenty defects were found in all; the table above lists the twelve largest.
The remainder were: a role word bleeding into a name ("Ayadi Bouguerba
Commissaire"), missing plural role forms, a professional qualification
outranking the conferred role, label and closing lines taken as organisation
names, undecoded HTML entities in 2,654 organisation names, reference codes
trailing a line rather than standing alone (1,559 announcements merged into a
neighbour), and four further cue gaps found while measuring recall
("désisté de sa fonction", "augmenter le capital", "changement d'adresse", and
a verb-to-object gap too narrow for an interposed identity-card number).

## Measured accuracy after the fixes

Precision **0.982** (95% CI 0.937–0.995) on 112 coded events, with **no
spurious events**; recall **0.967** (0.886–0.991) on 60 ties in 43 relational
blocks. See `docs/GOLD-SCORE-multiplex.md`. These are self-audit
figures and are not independent.

## Bearing on the earlier release

The dataset merged in PR #3 carries all twelve defects. Its event counts should
not be quoted, and any analysis run on it should be re-run. This is precisely
the risk that the old wording — "treat every event count as a lower bound of
unknown tightness" — was meant to flag, and it turned out to understate the
problem, since defects 1 and 2 are errors of commission rather than omission.
