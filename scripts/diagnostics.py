"""Coverage and quality report for the built dataset.

Writes docs/DIAGNOSTICS.md and prints the same to stdout.  Run it after every
rebuild: the per-decade yield and the unresolved-act count are the two numbers
that tell you whether an extraction change helped or hurt.
"""

from __future__ import annotations

import gzip
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from eltn.extract import iter_acts, extract_events
from eltn.harvest import load_catalog
from eltn.textnorm import arabic_ratio

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"

out: list[str] = []


def say(line: str = "") -> None:
    print(line)
    out.append(line)


def table(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False)


# --------------------------------------------------------------------------
say("# Diagnostics")
say()

events = pd.read_csv(PROC / "events.csv.gz", low_memory=False)
spells = pd.read_csv(PROC / "spells.csv.gz", low_memory=False)
persons = pd.read_csv(PROC / "persons.csv.gz")
catalog = load_catalog(RAW / "catalog_journal-officiel_fr.json")

say("## Scale")
say()
say(f"- issues catalogued: **{len(catalog):,}** (French *journal-officiel*, "
    f"{min(i.year for i in catalog)}–{max(i.year for i in catalog)})")
say(f"- events: **{len(events):,}**")
say(f"- persons: **{persons.person_id.nunique():,}**")
say(f"- organisations: **{events.org_id.nunique():,}**")
say(f"- spells: **{len(spells):,}**")
say()

# --- coverage by decade ---------------------------------------------------
say("## Yield by decade")
say()
say("`events_per_issue` is the figure to watch across extraction changes. The "
    "rise over time is partly real administrative growth and partly better "
    "scans; do not read it as a measure of state activity.")
say()
issues_by_decade = Counter((i.year // 10) * 10 for i in catalog)
ev = events.copy()
ev["decade"] = (ev.year // 10) * 10
dec = ev.groupby("decade").agg(
    events=("event_id", "size"),
    persons=("person_id", "nunique"),
    orgs=("org_id", "nunique"),
).reset_index()
dec["issues"] = dec.decade.map(issues_by_decade)
dec["events_per_issue"] = (dec.events / dec.issues).round(1)
say(table(dec[["decade", "issues", "events", "events_per_issue", "persons", "orgs"]]))
say()

# --- composition ----------------------------------------------------------
say("## Composition")
say()
for col in ("event_type", "source_layer", "act_kind", "org_source"):
    counts = events[col].value_counts()
    share = (counts / len(events) * 100).round(1)
    say(f"**{col}**")
    say()
    say(table(pd.DataFrame({col: counts.index, "n": counts.values,
                            "%": share.values})))
    say()

say("**position_rank** (top 12)")
say()
r = events.position_rank.value_counts().head(12)
say(table(pd.DataFrame({"rank": r.index, "n": r.values})))
say()

# --- field completeness ---------------------------------------------------
say("## Field completeness")
say()
checks = {
    "act_date parsed": events.act_date.notna(),
    "effect_date distinct from act_date": events.effect_date.notna()
        & (events.effect_date != events.act_date),
    "organisation named in the act text": events.org_source == "text",
    "position non-empty": events.position_clean.fillna("").str.len() > 2,
    "predecessor named ('en remplacement de')": events.replaces_id.fillna("") != "",
    "signatory identified": events.signatory_id.fillna("") != "",
}
comp = pd.DataFrame({
    "field": list(checks),
    "n": [int(v.sum()) for v in checks.values()],
    "%": [round(float(v.mean()) * 100, 1) for v in checks.values()],
})
say(table(comp))
say()

# --- spell closure --------------------------------------------------------
say("## Spell closure")
say()
say("The share ending `censored` is a property of the gazette, not of the "
    "pipeline: entries into office must be published, exits often need not be.")
say()
er = spells.end_reason.value_counts()
say(table(pd.DataFrame({"end_reason": er.index, "n": er.values,
                        "%": (er / len(spells) * 100).round(1).values})))
say()
observed = spells[spells.end_reason != "censored"]
if len(observed):
    say(f"Median observed tenure: **{observed.duration_days.median():.0f} days** "
        f"({observed.duration_days.median() / 365.25:.1f} years); "
        f"mean {observed.duration_days.mean():.0f} days.")
    say()

# --- entity-resolution health --------------------------------------------
say("## Entity resolution")
say()
span = persons.last_year - persons.first_year
suspect = persons[(span > 45) | (persons.n_orgs > 12)]
variants = persons.name_variants.fillna("")
n_strings = int(variants.str.count(r"\|").sum() + len(persons))
n_multi = int(variants.str.contains(r"\|").sum())
say(f"- distinct name strings resolved: **{n_strings:,}**")
say(f"- persons: **{len(persons):,}**")
say(f"- persons with >1 surface spelling: **{n_multi:,}**")
say(f"- **suspect ids** (career span > 45 years or > 12 organisations): "
    f"**{len(suspect):,}** ({len(suspect) / len(persons) * 100:.2f}%) — "
    "likely homonym merges, screen these before analysis")
say()
if len(suspect):
    top = suspect.nlargest(8, "n_events")[
        ["name", "first_year", "last_year", "n_orgs", "n_events"]]
    say(table(top))
    say()

# --- recall proxy: acts that produced nothing -----------------------------
say("## Recall proxy: segmented acts that yielded no event")
say()
say("Sampled issues are re-parsed and every act counted. An act with a "
    "personnel keyword in its heading but no extracted event is a candidate "
    "miss; sampling from that set and reading the PDF is how the next "
    "extraction rule gets found.")
say()

random.seed(11)
sample = random.sample(catalog, 120)
tot_acts = empty_acts = personnel_empty = arabic = 0
misses: list[tuple[str, str]] = []
for issue in sample:
    path = issue.cache_path(RAW / "jort")
    if not path.exists():
        continue
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        raw = fh.read()
    if arabic_ratio(raw[:4000]) > 0.15:
        arabic += 1
        continue
    for act in iter_acts(raw, issue_key=issue.key, year=issue.year, issue=issue.issue):
        tot_acts += 1
        got = extract_events(act, issue.pdf_url)
        if got:
            continue
        empty_acts += 1
        context = f"{act.section_raw} {act.title}".lower()
        if any(w in context for w in ("nomination", "cessation", "mouvement",
                                      "retraite", "décharge", "désignation")):
            personnel_empty += 1
            if len(misses) < 8:
                misses.append((issue.key, act.text[:160]))

say(f"- sampled issues: **{len(sample)}** (of which Arabic-only scans: {arabic})")
say(f"- acts segmented: **{tot_acts:,}**")
say(f"- acts yielding no event: **{empty_acts:,}** "
    f"({empty_acts / max(tot_acts, 1) * 100:.1f}%) — most are regulatory, not personnel")
say(f"- acts under a personnel heading yet yielding nothing: **{personnel_empty}** "
    f"({personnel_empty / max(tot_acts, 1) * 100:.2f}% of acts)")
say()
if misses:
    say("Examples to inspect:")
    say()
    for key, text in misses:
        say(f"- `{key}` — {text.strip()[:150]}…")
    say()

doc = ROOT / "docs" / "DIAGNOSTICS.md"
doc.write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"\nwritten: {doc}")
