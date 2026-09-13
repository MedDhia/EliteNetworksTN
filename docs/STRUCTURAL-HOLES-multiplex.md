# Structural holes: real, or made by resolution?

A structural hole is a finding. Two clusters with nobody bridging them
is what brokerage looks like in a network, and a paper reports it as
such. A hole this pipeline manufactured by failing to resolve an
identity is therefore not a nuisance but a **false finding** -- and it
is the error that most directly corrupts the substantive claim,
because it is indistinguishable from the thing the analysis is looking
for.

This report quantifies the exposure. It fixes nothing.

## The bound

| quantity | asserted | if every declined link were admitted |
|---|---|---|
| person-organisation edges | 20,523 | 23,599 |
| components in the person projection | 4,358 | 4,219 |
| largest component | 2,548 | 2,796 |
| connected person pairs | 3,246,528 | 3,909,027 |

**662,499 person pairs** are unconnected in the dataset as asserted and connected if the review
queue is admitted wholesale -- 20.4% of the connected pairs the dataset does assert.

Neither column is the truth. The left one treats every declined link
as absent, which is what produces false holes; the right treats every
one as real, which would import every bad match in the queue. The
interval between them is the honest statement, and it is printed so a
reader can see its width before treating any particular hole as a
finding.

## Every part of the network, measured the same way

| layer | nodes | components | if admitted | connected pairs | if admitted | exposure |
|---|---|---|---|---|---|---|
| person-organisation (all years) | 7,832 | 4,358 | 4,193 | 3,246,528 | 3,839,388 | 18.3% |
| person-organisation 1957-2010 | 3,879 | 2,604 | 2,543 | 305,522 | 358,482 | 17.3% |
| person-organisation 2011-2026 | 7,629 | 4,424 | 4,310 | 2,355,776 | 2,676,319 | 13.6% |
| organisation ownership | 8,260 | 1,593 | 1,298 | 9,052,835 | 13,854,647 | 53.0% |
| kinship | 26 | 13 | 13 | 13 | 13 | 0.0% |

The layers are reported separately on purpose. The
person-organisation panel is dense and mostly name-resolved, so its
exposure is close to a pure measurement artefact. The ownership
layer's is not: that layer admits a dyad only where **both** ends
resolve to distinct seed organisations, so most of its declined set
sits out by design rather than by failure, and its interval is wide
for a reason that is not an error. The kinship layer is sparse
because a marriage needs two identifiable people. One averaged
figure across the three would mix an artefact with a design
decision and mean nothing.

## Where the suspect holes are

- **23,408 organisation pairs** are plausibly one firm, by a shared hard identifier or a shared
  discriminating seat with an overlapping name. Between them they sit
  across **2,315 person pairs**
  that would be colleagues if the pair were one firm.
- **4,220 person pairs** are a seed node and
  an unresolved gazette cluster bearing the same name, with exactly one
  seed bearer of that name. Splitting one person in two does not merely
  halve their degree -- it removes every path that ran through them,
  which is how a broker disappears and a hole appears in their place.

Every pair is listed in `suspect_holes.csv` with its basis, so none of
this has to be taken on trust.

## The largest suspects, by how many person pairs they separate

| organisation A | organisation B | basis | person pairs |
|---|---|---|---|
| BANQUE INTERNATIONALE ARABE DE TUNISIE | BANQUE DE TUNISIE BT | shared_registre_commerce | 83 |
| COMPOSITES POUR LE SANITAIRE ET L'INDU | SOCIETE M | shared_matricule_fiscal | 63 |
| SOCIETE DE PROMOTION IMMOBILIERE | STRAMICA | shared_matricule_fiscal | 56 |
| SOCIETE DE PROMOTION IMMOBILIERE | STRAMICA | shared_registre_commerce | 56 |
| NEWREST CATERING TUNISIE | TUNISIE CATERING | shared_matricule_fiscal | 48 |
| TUNISIE PROFILES ALUMINIUM TPR | UNION DE FACTORING UNIFACTOR | shared_matricule_fiscal | 39 |
| BANQUE DE FINANCEMENT DES PETITES ET M | GROUPE CHIMIQUE TUNISIEN | shared_registre_commerce | 36 |
| ATTIJARI LEASING | BANQUE DE TUNISIE BT | shared_matricule_fiscal | 34 |
| ATTIJARI LEASING | BANQUE DE TUNISIE BT | shared_registre_commerce | 34 |
| SOCIETE INES | SOCIETE DE PROMOTION IMMOBILIERE | shared_matricule_fiscal | 28 |
| SOCIETE DE PROMOTION IMMOBILIERE | SOCIETE DE PROMOTION IMMOBILIERE INDUS | shared_matricule_fiscal | 28 |
| SOCIETE DE PROMOTION IMMOBILIERE | TELETEC CATERING | shared_registre_commerce | 28 |
| SOCIETE DE PROMOTION IMMOBILIERE | TELETEC INDUSTRIES | shared_registre_commerce | 28 |
| SOCIETE DE PROMOTION IMMOBILIERE | SOCIETE DE PROMOTION IMMOBILIERE KOKET | shared_matricule_fiscal | 27 |
| SOCIETE DE PROMOTION IMMOBILIERE | SOCIETE DE PROMOTION IMMOBILIERE KOKET | shared_registre_commerce | 27 |

## What this does not cover

- A hole between two firms neither of which states an identifier or a
  seat is invisible here. Absence of a suspect is not evidence the hole
  is real.
- Merge hubs are excluded from the projection (any organisation with
  more than 60 officers), because a hub connects everyone to everyone
  and would report the whole network as one blob -- the mirror of the
  error being measured. So the observed column is computed on a
  network with the worst merges already removed.
- The queue's edges are candidates, not findings. An ambiguous dyad
  means the matcher declined to choose among several people, not that
  nobody was there -- which is why admitting them bounds the hole
  count rather than correcting it.
