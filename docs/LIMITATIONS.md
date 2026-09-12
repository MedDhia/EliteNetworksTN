# Limitations

Read this before the dataset goes into a paper. Most of what follows is a
property of the source rather than of the code, and none of it is fixable by
tuning a regex.

## 1. French edition only, and after 1993 it is not the authoritative text

The upstream mirror has OCR'd only the French edition. Since
**loi n° 93-64 du 5 juillet 1993**, only the Arabic version of the JORT is
legally authoritative; the French version is informative. In practice the two
carry the same acts, but where they differ the Arabic governs, and the French
edition has occasionally omitted or delayed items.

Practical consequence: treat post-1993 coverage as a faithful but not
constitutive record, and do not make claims about the *absence* of an act from
the French edition alone.

`harvest.py` already accepts `lang="ar"`. When upstream OCRs the Arabic
edition, the harvester needs no change; the extractor's patterns would have to
be rewritten in Arabic.

## 2. Coverage is uneven across the period, in two different ways

**Real growth.** The administration expanded enormously, so more events per
year in 2015 than 1965 is substantively true, not an artefact.

**Artefactual variation.** OCR quality is worse on the earliest scans; the
1957–60 volumes include numbers filed as French that are in fact Arabic-only
(these are detected and skipped, not silently mis-parsed); typography changed
several times, and the extraction rules match the later conventions better than
the earliest ones.

Do not read a time series of raw event counts as a measure of state activity.
Run `scripts/diagnostics.py` for the per-decade yield and OCR-health figures,
and normalise by issues or pages if the trend matters to your argument.

## 3. Exits are recorded far less reliably than entries

An appointment must be published to take effect. A departure often need not
be: people retire, resign, or are quietly moved without a cessation act. Only
**5.3%** of spells are closed by an act that states the exit.

The spell logic therefore closes tenures four ways — an explicit termination or
retirement, a successor naming the incumbent replaced, someone else being
appointed to the same singular office, or the person surfacing in another
office — and right-censors the remaining **41.7%**. That share is not a bug in
the pipeline; it is the shape of the source.

**The load-bearing distinction is `end_precision`, not `end_reason`.** Two of
the four mechanisms date the exit exactly because an act says so; the other two
only establish that the person was gone *by* that date. Read as exact exits,
they bias tenure upward, and badly in the tail: a `displaced` spell running
thirty years means nobody was recorded in that post for thirty years, not that
one person held it that long.

```python
spells = pd.read_csv("data/processed/spells.csv.gz")
exact = spells[spells.end_precision == "exact"]          # 5.3%
interval = spells[spells.end_precision == "upper_bound"] # 53.0%
censored = spells[spells.end_precision == "censored"]    # 41.7%
```

Use survival methods that handle right-censoring, and treat `upper_bound` rows
as interval-censored rather than exact. If your design cannot accommodate
interval censoring, the defensible fallback is to treat `upper_bound` as
censored too and fit on the 5.3% that is stated — small, but unbiased in a way
the rest is not.

`displaced` is the newest and most consequential of the four. Its guards are
documented in the codebook; `build_spells(ev, infer_displacement=False)` turns
it off if you would rather have censoring than inference.

## 4. Homonymy is not resolved

Person resolution merges spelling variants of the same name. It cannot
separate two different people who share a name — and Tunisian naming is
concentrated enough that this is common for frequent combinations
(*Mohamed Ben Salah*, *Ali Ben Ali*).

The failure mode is a small number of implausible super-careers: one id holding
incompatible offices in distant places, or spanning fifty years. Screen for
them before analysis:

```python
persons = pd.read_csv("data/processed/persons.csv.gz")
suspect = persons[(persons.last_year - persons.first_year > 45)
                  | (persons.n_orgs > 12)]
```

`name_variants` shows every string merged into an id. For a study of a defined
elite (a ministry, a cohort, the top of the rank scale) hand-checking the
suspect list is a few hours' work and worth doing.

The resolver errs towards merging. If your design is more damaged by false
merges than by false splits, call `normalize.resolve_persons(names, fuzzy=False)`
and rebuild: that drops the affix-variant pass and keeps only exact-key
matching.

## 5. The organisation of an event is sometimes imputed

Where the act names a workplace, that is used. Where it does not — common in
short-form ministry appointments — the organisation is taken from the ministry
heading the act was published under. `org_source` records which happened
(`text` vs `heading`). Restrict to `org_source == "text"` if the distinction
between a ministry and its subordinate agencies is load-bearing for you.

## 6. Recitals are evidence of a different act

Rows with `source_layer == "recital"` come from *"Vu le décret n° … chargeant
M. X …"* clauses. They record an **earlier** appointment, dated to that earlier
act. They are genuinely useful — they recover appointments from issues that
are missing or badly OCR'd — but they are second-hand and they are not
distributed randomly (an official gets recited when their file is touched
again). Exclude them for act-level analysis; keep them when reconstructing
individual careers.

## 7. The rank scale and the portfolio crosswalk are coding decisions

`RANK_SCALE` imposes an ordering on offices, and `MINISTRY_DOMAINS` decides
when a renamed ministry is "the same" ministry. Both are defensible and both
are contestable. They are defined in one place each in
`src/eltn/normalize.py`, and the dataset rebuilds in about five minutes, so
treat them as parameters of your design rather than as fixed features of the
data. A robustness check that varies them is cheap.

## 8. What the extractor misses

Precision was prioritised over recall. Known systematic gaps:

- acts whose operative verb is phrased in a form not in the verb tables
  (`APPOINT_VERBS` and friends in `extract.py`);
- appointments embedded in the body of long regulatory decrees rather than in a
  personnel section;
- military and judicial movements published in aggregate tabular form, which
  OCR renders as pipe-delimited rows the paragraph parser does not read as
  prose;
- the 1957–1962 volumes generally, where scan quality is worst.

`scripts/diagnostics.py` reports the count of acts that were segmented but
yielded no event, which is the best available proxy for recall. Sampling from
that set and reading the PDFs is the way to find the next pattern worth adding.

## 9. This is office-holding, not influence

The gazette records formal position. It does not record who actually decided
anything, informal networks, family ties, party membership, or business
interests. Co-affiliation in a ministry is a *structural opportunity* for a
relation, not evidence of one. The two relations that come closest to a claim
about power — `succession` and `signature` — are still statements about legal
authority, not about patronage as a motive.
