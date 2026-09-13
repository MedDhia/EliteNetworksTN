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
| person-organisation edges | 20,426 | 23,422 |
| components in the person projection | 4,343 | 4,236 |
| largest component | 2,513 | 2,737 |
| connected person pairs | 3,158,073 | 3,745,875 |

**587,802 person pairs** are unconnected in the dataset as asserted and connected if the review
queue is admitted wholesale -- 18.6% of the connected pairs the dataset does assert.

Neither column is the truth. The left one treats every declined link
as absent, which is what produces false holes; the right treats every
one as real, which would import every bad match in the queue. The
interval between them is the honest statement, and it is printed so a
reader can see its width before treating any particular hole as a
finding.

## Every part of the network, measured the same way

| layer | nodes | components | if admitted | connected pairs | if admitted | exposure |
|---|---|---|---|---|---|---|
| person-organisation (all years) | 7,815 | 4,343 | 4,209 | 3,158,073 | 3,683,135 | 16.6% |
| person-organisation 1957-2010 | 3,865 | 2,597 | 2,547 | 284,924 | 340,988 | 19.7% |
| person-organisation 2011-2026 | 7,610 | 4,405 | 4,314 | 2,403,413 | 2,689,744 | 11.9% |
| organisation ownership | 8,330 | 1,600 | 1,312 | 9,240,960 | 13,933,876 | 50.8% |
| kinship | 28 | 14 | 14 | 14 | 14 | 0.0% |

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

- **23,424 organisation pairs** are plausibly one firm, by a shared hard identifier or a shared
  discriminating seat with an overlapping name. Between them they sit
  across **2,245 person pairs**
  that would be colleagues if the pair were one firm.
- **4,232 person pairs** are a seed node and
  an unresolved gazette cluster bearing the same name, with exactly one
  seed bearer of that name. Splitting one person in two does not merely
  halve their degree -- it removes every path that ran through them,
  which is how a broker disappears and a hole appears in their place.

Every pair is listed in `suspect_holes.csv` with its basis, so none of
this has to be taken on trust.

## The largest suspects, by how many person pairs they separate

| organisation A | organisation B | basis | person pairs |
|---|---|---|---|
| BANQUE INTERNATIONALE ARABE DE TUNISIE | BANQUE DE TUNISIE BT | shared_registre_commerce | 80 |
| COMPOSITES POUR LE SANITAIRE ET L'INDU | SOCIETE M | shared_matricule_fiscal | 63 |
| SOCIETE DE PROMOTION IMMOBILIERE | STRAMICA | shared_matricule_fiscal | 56 |
| SOCIETE DE PROMOTION IMMOBILIERE | STRAMICA | shared_registre_commerce | 56 |
| GROUPE CHIMIQUE TUNISIEN | ORG_BANQUE_FINANCEMENT_PETITES_MOYENNE | shared_registre_commerce | 45 |
| TUNISIE PROFILES ALUMINIUM TPR | UNION DE FACTORING UNIFACTOR | shared_matricule_fiscal | 39 |
| BANQUE DE TUNISIE BT | BANQUE DE TUNISIE ET DES EMIRATS BTE | shared_matricule_fiscal | 32 |
| SOCIETE DE PROMOTION IMMOBILIERE | TELETEC CATERING | shared_registre_commerce | 28 |
| SOCIETE DE PROMOTION IMMOBILIERE | TELETEC INDUSTRIES | shared_registre_commerce | 28 |
| ALHIFADH SICAV | SICAV ENTREPRISE | shared_matricule_fiscal | 22 |
| COMPTOIR MULTISERVICES AGRICOLES CMA | SOCIETE ELEMENTS + | shared_matricule_fiscal | 22 |
| COMPTOIR MULTISERVICES AGRICOLES CMA | SOCIETE MULTISERVICES | shared_matricule_fiscal | 22 |
| ALHIFADH SICAV | SICAV ENTREPRISE | shared_seat_and_token | 22 |
| COMPTOIR MULTISERVICES AGRICOLES CMA | SOCIETE MULTISERVICES | shared_seat_and_token | 22 |
| COMPTOIR MULTISERVICES AGRICOLES CMA | SOCIETE MULTISERVICES | shared_seat_and_token | 22 |

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
