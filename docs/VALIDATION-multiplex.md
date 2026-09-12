# Validation report

Generated 2026-09-12.

## WARN

- **weekday mismatch** — 47 issues where the printed weekday disagrees with the date (date retained; a lone weekday is likelier a misprint)
- **zero-length spells** — 151 spells open and close on the same day (an officer appointed and replaced in one act)
- **overlapping single-holder posts** — 161 overlaps on gerant/pdg/dg/president posts — candidate resolution errors
- **improbably many posts** — 62 resolved persons hold more than 12 dyads (possible merged homonyms), worst: ('PERSON_TRABELSI_MOHAMED', 89)
- **conflicting matricule_fiscal** — 2805 of 7513 organisations carrying one hold two or more values (37%); a few values clustered around one is OCR, many with nothing in common is an organisation-resolution merge. See docs/ORG-IDENTIFIER-CONFLICTS-multiplex.md
- **conflicting registre_commerce** — 1443 of 4762 organisations carrying one hold two or more values (30%); a few values clustered around one is OCR, many with nothing in common is an organisation-resolution merge. See docs/ORG-IDENTIFIER-CONFLICTS-multiplex.md
- **organisation merge hubs** — 383 nodes carry 10 or more values of one hard identifier and are near-certainly several firms merged into one; worst is LA CONSULTING with 1606 distinct matricule fiscal values. Exclude these before computing organisation-level structure — `org_identifiers.csv` carries `n_values_for_org`, and `exports/tergm/node_key.csv` carries `merge_suspect`.
- **identifiers shared across nodes** — 1465 identifier values appear on more than one organisation node (one firm split in two, or a collision)

## INFO

- **calendar coverage** — 9647/9749 issues dated (99.0%)
- **calendar needs review** — 417 issues flagged
- **events** — 689169 extracted
- **act date after publication** — 0 events where the act postdates the issue that published it
- **retroactive effective dates** — 20567 acts take effect before their own date (lawful)
- **provenance present** — 0 events without a verbatim quote
- **source citation present** — 0 events without an issue reference
- **date precision** — exact=629000, pub_only=60169
- **event types** — appointed=275919, constituted=150066, charged_with_functions=62783, capital_increased=43163, shares_transferred=39464, org_tie=30161, resigned=25972, headquarters_moved=18171
- **quotes verbatim** — 0/2000 sampled quotes not found in their source block
- **spells** — 13031 dated, 27585 undated seed ties
- **no negative durations** — 0 spells end before they begin
- **censoring** — right_censored=9156, closed=3875, left_censored=2729
- **closure mechanism** — (open)=8382, event:resigned=1941, org_dissolved=983, displaced_by=876, withdrawn_inconsistent=774, event:revoked=68, event:terminated=7
- **resolution status** — unresolved=373465, resolved=10844, ambiguous=4832
- **resolutions are dyad-anchored** — 0 resolved links lack organisation agreement (a name-only link is not an identification)
- **review queue** — 4832 ambiguous dyads queued; 249333 gazette-only candidate persons retained
- **seed elites with a dated gazette event** — top 100: 94 (94%); top 500: 434 (87%); top 1000: 811 (81%); all 13630: 5375 (39.4%)
- **negative control** — 0 officer events found in 118975 auction/fonds-de-commerce blocks, which are excluded from extraction (0 expected by construction)
- **ministerial appointments by year** — 1958=6, 1959=1, 1960=2, 1961=3, 1962=3, 1964=1, 1965=3, 1966=10, 1967=4, 1968=3, 1969=10, 1970=4, 1971=12, 1972=20, 1973=12, 1974=18, 1975=4, 1976=7, 1977=13, 1978=17, 1979=6, 1980=43, 1981=63, 1982=21, 1983=53, 1984=44, 1985=37, 1986=45, 1987=81, 1988=45, 1989=27, 1990=36, 1991=45, 1992=47, 1993=36, 1994=42, 1995=41, 1996=39, 1997=50, 1998=27, 1999=45, 2000=44, 2001=56, 2002=33, 2003=25, 2004=29, 2005=67, 2006=42, 2007=55, 2008=57, 2009=30, 2010=57, 2011=102, 2012=178, 2013=118, 2014=138, 2015=195, 2016=190, 2017=164, 2018=131, 2019=73, 2020=243, 2021=88, 2022=69, 2023=20, 2024=52, 2025=15, 2026=3
- **seed cabinets** — 7 government nodes in the seed sheet: CHAHED GOVERNMENT, ESSID GOVERNMENT, FAKHFAKH GOVERNMENT, JEBALI GOVERNMENT, JOMAA GOVERNMENT, LAARAYEDH GOVERNMENT, MECHICHI GOVERNMENT
- **act citation graph** — 420593 citations, 408017 with a resolvable cited date
- **org ties** — 2314 dated, 4614 undated seed ties; 2255 dated dyads
- **org tie relations** — shareholder_confirmed=5016, auditor=1108, shares_ceded=253, funder=201, shares_acquired=195, member=79, branch=42, corporate_officer=33
- **org ties are not self-loops** — 0 ties whose holder and target are the same organisation
- **org tie durations are not negative** — 0 org tie spells end before they begin
- **org tie censoring is consistent** — 0 spells assert an onset while flagged left-censored
- **org tie endpoints are seed nodes** — 0 ties with an endpoint absent from seed_nodes.csv
- **org tie censoring** — left_censored=1865 (81%), right_censored=2061 (89%)
- **organisation identifiers** — 37600 (organisation, identifier, value) rows: matricule_fiscal=26726, registre_commerce=10874
- **organisation addresses** — 67014 dated address observations over 10528 organisations; 1914 are transfer destinations; 6477 organisations have more than one address on record
- **addresses are dated** — 0 address observations carry no date, so they cannot be ordered into a sequence of seats
- **tergm vertex key is mode-blocked** — 6000 persons then 7152 organisations; bipartite = 6000; mode-blocked=True, ids contiguous from 1=True
- **tergm edges respect the mode split** — 0 of 130084 ties do not run from mode 1 to mode 2
- **tergm risk set is contiguous** — 0 vertices go inactive and then active again
- **tergm ties lie inside the risk set** — 0 ties fall in a period where an endpoint is inactive
- **tergm panel covers the configured window** — 70 periods present, 70 configured
- **tergm panel is rectangular** — 70 periods x 13152 vertices; 0 periods with a short attribute or activity table
