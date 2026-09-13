# Validation report

Generated 2026-09-13.

## WARN

- **weekday mismatch** — 47 issues where the printed weekday disagrees with the date (date retained; a lone weekday is likelier a misprint)
- **zero-length spells** — 139 spells open and close on the same day (an officer appointed and replaced in one act)
- **overlapping single-holder posts** — 129 overlaps on gerant/pdg/dg/president posts — candidate resolution errors
- **links inferred from name rarity** — 13039 links over 4820 persons rest on the name being borne by one seed person and matching one gazette candidate, with no organisation to anchor them. They are NOT counted as resolved. Exclude them for any claim that needs dyad-anchored identification; include them for coverage.
- **improbably many posts** — 67 resolved persons hold more than 12 dyads (possible merged homonyms), worst: ('PERSON_TRABELSI_MOHAMED', 91)
- **entities keyed only by name** — 146886 of 235052 entities (62%) have no hard identifier and are keyed on the mention, so two spellings of one such firm stay separate -- the mirror image of the merge, and it understates degree rather than overstating it
- **conflicting matricule_fiscal** — 2148 of 79431 organisations carrying one hold two or more values (3%); a few values clustered around one is OCR, many with nothing in common is an organisation-resolution merge. See docs/ORG-IDENTIFIER-CONFLICTS-multiplex.md
- **conflicting registre_commerce** — 2058 of 33702 organisations carrying one hold two or more values (6%); a few values clustered around one is OCR, many with nothing in common is an organisation-resolution merge. See docs/ORG-IDENTIFIER-CONFLICTS-multiplex.md
- **organisation merge hubs** — 134 organisations (179 organisation-identifier pairs) hold 10 or more values of a single hard identifier and are near-certainly several firms merged into one; worst is SOCIETE M with 154 distinct matricule fiscal values. Exclude these before computing organisation-level structure — `org_identifiers.csv` carries `n_values_for_org`, and `exports/tergm/node_key.csv` carries `merge_suspect`.
- **identifiers shared across nodes** — 4450 identifier values appear on more than one organisation node (one firm split in two, or a collision)
- **kinship ties resting on an inferred endpoint** — 10 of 14 dyads have at least one end named by name rarity rather than by an organisation agreeing; they carry evidence_tier=kinship_inferred and are excluded from any filter on kinship_dated
- **resolution rests partly on snowballed anchors** — 497 links were made from an anchor a later pass supplied rather than from the organisation agreeing. They carry link_status=snowball and evidence_tier=gazette_snowball downstream; filter resolve_pass==0 to reproduce the single-pass build exactly

## INFO

- **calendar coverage** — 9647/9749 issues dated (99.0%)
- **calendar needs review** — 417 issues flagged
- **events** — 781233 extracted
- **act date after publication** — 0 events where the act postdates the issue that published it
- **retroactive effective dates** — 21363 acts take effect before their own date (lawful)
- **provenance present** — 0 events without a verbatim quote
- **source citation present** — 0 events without an issue reference
- **date precision** — exact=696521, pub_only=84712
- **event types** — appointed=275919, constituted=150066, resides_at=83123, charged_with_functions=62783, capital_increased=43163, shares_transferred=39464, org_tie=30333, resigned=25972
- **quotes verbatim** — 0/2000 sampled quotes not found in their source block
- **spells** — 12200 dated, 38175 undated seed ties
- **no negative durations** — 0 spells end before they begin
- **censoring** — right_censored=8703, closed=3497, left_censored=2627
- **closure mechanism** — (open)=8214, event:resigned=1815, org_dissolved=1081, displaced_by=531, withdrawn_inconsistent=489, event:revoked=68, event:terminated=2
- **resolution status** — unresolved=433920, inferred=13039, resolved=11032, ambiguous=3689, snowball=497
- **resolutions are dyad-anchored** — 0 resolved links lack organisation agreement (a name-only link is not an identification)
- **review queue** — 3689 ambiguous dyads queued; 306344 gazette-only candidate persons retained
- **seed elites with a dated gazette event** — top 100: 94 (94%); top 500: 434 (87%); top 1000: 812 (81%); all 13630: 5398 (39.6%)
- **negative control** — 0 officer events found in 118975 auction/fonds-de-commerce blocks, which are excluded from extraction (0 expected by construction)
- **ministerial appointments by year** — 1958=6, 1959=1, 1960=2, 1961=3, 1962=3, 1964=1, 1965=3, 1966=10, 1967=4, 1968=3, 1969=10, 1970=4, 1971=12, 1972=20, 1973=12, 1974=18, 1975=4, 1976=7, 1977=13, 1978=17, 1979=6, 1980=43, 1981=63, 1982=21, 1983=53, 1984=44, 1985=37, 1986=45, 1987=81, 1988=45, 1989=27, 1990=36, 1991=45, 1992=47, 1993=36, 1994=42, 1995=41, 1996=39, 1997=50, 1998=27, 1999=45, 2000=44, 2001=56, 2002=33, 2003=25, 2004=29, 2005=67, 2006=42, 2007=55, 2008=57, 2009=30, 2010=57, 2011=102, 2012=178, 2013=118, 2014=138, 2015=195, 2016=190, 2017=164, 2018=131, 2019=73, 2020=243, 2021=88, 2022=69, 2023=20, 2024=52, 2025=15, 2026=3
- **seed cabinets** — 7 government nodes in the seed sheet: CHAHED GOVERNMENT, ESSID GOVERNMENT, FAKHFAKH GOVERNMENT, JEBALI GOVERNMENT, JOMAA GOVERNMENT, LAARAYEDH GOVERNMENT, MECHICHI GOVERNMENT
- **act citation graph** — 420593 citations, 408017 with a resolvable cited date
- **org ties** — 3524 dated, 4634 undated seed ties; 3479 dated dyads
- **org tie relations** — shareholder_confirmed=5718, auditor=1546, shares_ceded=288, shares_acquired=231, funder=201, member=79, branch=45, corporate_officer=33
- **org ties are not self-loops** — 0 ties whose holder and target are the same organisation
- **org tie durations are not negative** — 0 org tie spells end before they begin
- **org tie censoring is consistent** — 0 spells assert an onset while flagged left-censored
- **org tie endpoints are known nodes** — 0 ties with an endpoint in neither seed_nodes.csv nor org_entities.csv
- **org tie censoring** — left_censored=3004 (85%), right_censored=3236 (92%)
- **organisation entities** — 235052 entities over 302716 distinct mentions: name=143883, matricule_fiscal=73703, registre_commerce=13618, ambiguous_mention=3003, address_corroborated=845
- **every org mention has an entity** — 0 of 277960 organisation mentions in events.csv reach no entity
- **mentions spanning several entities** — 9571 mentions carry more than one hard identifier, so the mention-level map is modal for them; the per-event key in orgentity.entity_key is the authoritative assignment
- **entities linked to a seed organisation** — 12319 of 235052 entities carry an identity-grade seed link and adopt that node's id, so seed ties and the dyadic covariates projected from them stay on the same vertex
- **organisation identifiers** — 123464 (organisation, identifier, value) rows: matricule_fiscal=86084, registre_commerce=37380
- **organisation addresses** — 230066 dated address observations over 173595 organisations; 12050 are transfer destinations; 24585 organisations have more than one address on record
- **addresses are dated** — 0 address observations carry no date, so they cannot be ordered into a sequence of seats
- **person ties** — 14 kinship dyads; 14 marriages, 0 natal-surname links
- **person tie relations** — spouse_of=13, widow_of=1
- **a natal surname is not a marriage** — 0 spells whose relation and is_marriage disagree
- **kinship ties are not self-loops** — 0 ties whose two ends are the same person
- **no marriage onset is asserted** — 0 spells assert an onset the sources cannot date
- **kinship onsets are left-censored** — 0 spells not flagged left-censored
- **only a widow marker ends a tie** — 0 non-widow spells carry a terminus
- **kinship endpoints are known persons** — 0 ties with an endpoint outside seed_nodes.csv
- **person tie review queue** — 8749 observations retained but not tied: neither_end_named=8344, one_end_unnamed=405
- **snowball links** — 497 of 462177 mentions named by a later pass (pass 1=420, pass 2=77)
- **snowball bases** — colleagues_name_person=256, org_names_person=241
- **snowball marginal yield** — pass 1: +420, pass 2: +77
- **every snowballed link names its pass and rule** — 0 rows with link_status=snowball but no pass number or basis
- **a pass number names the rule that earned it** — 0 rows carry a pass number with no snowball_basis
- **an organisation-naming pass leaves an organisation named** — 0 rows name an organisation rule but carry no resolved_org_id
- **a person-naming pass leaves link_status=snowball** — 0 rows name a person rule without link_status=snowball
- **tergm vertex key is mode-blocked** — 5713 persons then 7197 organisations; bipartite = 5713; mode-blocked=True, ids contiguous from 1=True
- **tergm edges respect the mode split** — 0 of 124517 ties do not run from mode 1 to mode 2
- **tergm risk set is contiguous** — 0 vertices go inactive and then active again
- **tergm ties lie inside the risk set** — 0 ties fall in a period where an endpoint is inactive
- **tergm panel covers the configured window** — 70 periods present, 70 configured
- **tergm panel is rectangular** — 70 periods x 12910 vertices; 0 periods with a short attribute or activity table
