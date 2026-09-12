# Validation report

Generated 2026-09-12.

## ERROR

- **act date after publication** — 87 events where the act postdates the issue that published it

## WARN

- **weekday mismatch** — 47 issues where the printed weekday disagrees with the date (date retained; a lone weekday is likelier a misprint)
- **zero-length spells** — 146 spells open and close on the same day (an officer appointed and replaced in one act)
- **overlapping single-holder posts** — 153 overlaps on gerant/pdg/dg/president posts — candidate resolution errors
- **improbably many posts** — 62 resolved persons hold more than 12 dyads (possible merged homonyms), worst: ('PERSON_TRABELSI_MOHAMED', 89)

## INFO

- **calendar coverage** — 9647/9749 issues dated (99.0%)
- **calendar needs review** — 417 issues flagged
- **events** — 687799 extracted
- **retroactive effective dates** — 20582 acts take effect before their own date (lawful)
- **provenance present** — 0 events without a verbatim quote
- **source citation present** — 0 events without an issue reference
- **date precision** — exact=627766, pub_only=60033
- **event types** — appointed=275919, constituted=150066, charged_with_functions=62783, capital_increased=43163, shares_transferred=39464, org_tie=28791, resigned=25972, headquarters_moved=18171
- **quotes verbatim** — 0/2000 sampled quotes not found in their source block
- **spells** — 12713 dated, 27585 undated seed ties
- **no negative durations** — 0 spells end before they begin
- **censoring** — right_censored=9038, closed=3675, left_censored=2642
- **closure mechanism** — (open)=8301, event:resigned=1860, org_dissolved=930, displaced_by=818, withdrawn_inconsistent=737, event:revoked=60, event:terminated=7
- **resolution status** — unresolved=373985, resolved=10626, ambiguous=4530
- **resolutions are dyad-anchored** — 0 resolved links lack organisation agreement (a name-only link is not an identification)
- **review queue** — 4530 ambiguous dyads queued; 249408 gazette-only candidate persons retained
- **seed elites with a dated gazette event** — top 100: 94 (94%); top 500: 433 (87%); top 1000: 807 (81%); all 13630: 5300 (38.9%)
- **negative control** — 0 officer events found in 118975 auction/fonds-de-commerce blocks, which are excluded from extraction (0 expected by construction)
- **ministerial appointments by year** — 1958=6, 1959=1, 1960=2, 1961=3, 1962=3, 1964=1, 1965=3, 1966=10, 1967=4, 1968=3, 1969=10, 1970=4, 1971=12, 1972=20, 1973=12, 1974=18, 1975=4, 1976=7, 1977=13, 1978=17, 1979=6, 1980=43, 1981=63, 1982=21, 1983=53, 1984=44, 1985=37, 1986=45, 1987=81, 1988=45, 1989=27, 1990=36, 1991=45, 1992=47, 1993=36, 1994=42, 1995=41, 1996=39, 1997=50, 1998=27, 1999=45, 2000=44, 2001=56, 2002=33, 2003=25, 2004=29, 2005=67, 2006=42, 2007=55, 2008=57, 2009=30, 2010=57, 2011=102, 2012=178, 2013=118, 2014=138, 2015=195, 2016=190, 2017=164, 2018=131, 2019=73, 2020=243, 2021=88, 2022=69, 2023=20, 2024=52, 2025=15, 2026=3
- **seed cabinets** — 7 government nodes in the seed sheet: CHAHED GOVERNMENT, ESSID GOVERNMENT, FAKHFAKH GOVERNMENT, JEBALI GOVERNMENT, JOMAA GOVERNMENT, LAARAYEDH GOVERNMENT, MECHICHI GOVERNMENT
- **act citation graph** — 420593 citations, 408017 with a resolvable cited date
- **org ties** — 2255 dated, 4626 undated seed ties; 2202 dated dyads
- **org tie relations** — shareholder_confirmed=5002, auditor=1100, shares_ceded=232, funder=201, shares_acquired=192, member=79, branch=41, corporate_officer=33
- **org ties are not self-loops** — 0 ties whose holder and target are the same organisation
- **org tie durations are not negative** — 0 org tie spells end before they begin
- **org tie censoring is consistent** — 0 spells assert an onset while flagged left-censored
- **org tie endpoints are seed nodes** — 0 ties with an endpoint absent from seed_nodes.csv
- **org tie censoring** — left_censored=1830 (81%), right_censored=2023 (90%)
- **tergm vertex key is mode-blocked** — 5933 persons then 7080 organisations; bipartite = 5933; mode-blocked=True, ids contiguous from 1=True
- **tergm edges respect the mode split** — 0 of 127550 ties do not run from mode 1 to mode 2
- **tergm risk set is contiguous** — 0 vertices go inactive and then active again
- **tergm ties lie inside the risk set** — 0 ties fall in a period where an endpoint is inactive
- **tergm panel is rectangular** — 66 periods x 13013 vertices; 0 periods with a short attribute or activity table
