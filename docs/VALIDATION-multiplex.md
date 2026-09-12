# Validation report

Generated 2026-09-12.

## ERROR

- **act date after publication** — 93 events where the act postdates the issue that published it
- **quotes verbatim** — 1/2000 sampled quotes not found in their source block

## WARN

- **publication date outside window** — 4 issues, e.g. journal-officiel/fr/1958/025
- **weekday mismatch** — 46 issues where the printed weekday disagrees with the date (date retained; a lone weekday is likelier a misprint)
- **zero-length spells** — 147 spells open and close on the same day (an officer appointed and replaced in one act)
- **overlapping single-holder posts** — 156 overlaps on gerant/pdg/dg/president posts — candidate resolution errors
- **improbably many posts** — 60 resolved persons hold more than 12 dyads (possible merged homonyms), worst: ('PERSON_TRABELSI_MOHAMED', 88)

## INFO

- **calendar coverage** — 9648/9749 issues dated (99.0%)
- **calendar needs review** — 418 issues flagged
- **events** — 659013 extracted
- **retroactive effective dates** — 20510 acts take effect before their own date (lawful)
- **provenance present** — 0 events without a verbatim quote
- **source citation present** — 0 events without an issue reference
- **date precision** — exact=601236, pub_only=57777
- **event types** — appointed=275924, constituted=150066, charged_with_functions=62783, capital_increased=43163, shares_transferred=39464, resigned=25972, headquarters_moved=18171, liquidated=11568
- **spells** — 12652 dated, 27585 undated seed ties
- **no negative durations** — 0 spells end before they begin
- **censoring** — right_censored=8995, closed=3657, left_censored=2611
- **closure mechanism** — (open)=8217, event:resigned=1851, org_dissolved=932, displaced_by=807, withdrawn_inconsistent=778, event:revoked=60, event:terminated=7
- **resolution status** — unresolved=374000, resolved=10642, ambiguous=4504
- **resolutions are dyad-anchored** — 0 resolved links lack organisation agreement (a name-only link is not an identification)
- **review queue** — 4504 ambiguous dyads queued; 249421 gazette-only candidate persons retained
- **seed elites with a dated gazette event** — top 100: 94 (94%); top 500: 433 (87%); top 1000: 807 (81%); all 13630: 5311 (39.0%)
- **negative control** — 0 officer events found in 118951 auction/fonds-de-commerce blocks, which are excluded from extraction (0 expected by construction)
- **ministerial appointments by year** — 1958=6, 1959=1, 1960=2, 1961=3, 1962=3, 1964=1, 1965=3, 1966=10, 1967=4, 1968=3, 1969=10, 1970=4, 1971=12, 1972=20, 1973=12, 1974=18, 1975=4, 1976=7, 1977=13, 1978=17, 1979=6, 1980=43, 1981=63, 1982=21, 1983=53, 1984=44, 1985=37, 1986=45, 1987=81, 1988=45, 1989=27, 1990=36, 1991=45, 1992=47, 1993=36, 1994=42, 1995=41, 1996=39, 1997=50, 1998=27, 1999=45, 2000=44, 2001=56, 2002=33, 2003=25, 2004=29, 2005=67, 2006=42, 2007=55, 2008=57, 2009=30, 2010=57, 2011=102, 2012=178, 2013=118, 2014=138, 2015=195, 2016=190, 2017=164, 2018=131, 2019=73, 2020=243, 2021=88, 2022=69, 2023=20, 2024=52, 2025=15, 2026=3
- **seed cabinets** — 7 government nodes in the seed sheet: CHAHED GOVERNMENT, ESSID GOVERNMENT, FAKHFAKH GOVERNMENT, JEBALI GOVERNMENT, JOMAA GOVERNMENT, LAARAYEDH GOVERNMENT, MECHICHI GOVERNMENT
- **act citation graph** — 420617 citations, 408038 with a resolvable cited date
- **tergm vertex key is mode-blocked** — 5932 persons then 7082 organisations; bipartite = 5932; mode-blocked=True, ids contiguous from 1=True
- **tergm edges respect the mode split** — 0 of 127377 ties do not run from mode 1 to mode 2
- **tergm risk set is contiguous** — 0 vertices go inactive and then active again
- **tergm ties lie inside the risk set** — 0 ties fall in a period where an endpoint is inactive
- **tergm panel is rectangular** — 66 periods x 13014 vertices; 0 periods with a short attribute or activity table
