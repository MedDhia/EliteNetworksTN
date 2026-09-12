"""Export a compact payload for the interactive network explorer.

Restricted to the senior elite (rank_score >= 72: chief of state through
political adviser and secretary-general) so the graph stays legible and the
payload stays small.  Everything is index-encoded against shared string
tables.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUT = ROOT / "explorer" / "data.js"
RANK_CUT = 72
MAX_POSITION_CHARS = 90

persons = pd.read_csv(PROC / "persons.csv.gz")
spells = pd.read_csv(PROC / "spells.csv.gz", low_memory=False)
events = pd.read_csv(PROC / "events.csv.gz", low_memory=False)

elite = persons[persons.peak_rank_score >= RANK_CUT].copy()
elite_ids = set(elite.person_id)
print(f"elite persons (rank_score >= {RANK_CUT}): {len(elite):,}")

sp = spells[spells.person_id.isin(elite_ids)].copy()
print(f"spells: {len(sp):,}")

# --- string tables --------------------------------------------------------
# Organisations are keyed by org_id, not by the printed string: the gazette
# sets the same ministry as "MINISTERE DE L'INTERIEUR" in one issue and
# "Ministère de l'Intérieur" in the next, and keying on the surface form
# splits one institution into several hubs on the map.
from collections import Counter, defaultdict  # noqa: E402

variants: dict[str, Counter] = defaultdict(Counter)
for oid, name in zip(sp.org_id.fillna("").astype(str),
                     sp.org_name.fillna("").astype(str)):
    if oid:
        variants[oid][name] += 1


def display_name(counter: Counter) -> str:
    """Prefer a mixed-case spelling: those carry the accents."""
    mixed = {k: v for k, v in counter.items() if k and not k.isupper()}
    pool = mixed or dict(counter)
    best = max(pool.items(), key=lambda kv: (kv[1], len(kv[0])))[0]
    if best.isupper():
        best = best.capitalize()
    return best


org_ids = sorted(variants)
orgs = [display_name(variants[o]) for o in org_ids]
org_ix = {o: i for i, o in enumerate(org_ids)}
form_by_id = (events.drop_duplicates("org_id")
              .set_index("org_id").org_form.to_dict())
org_forms = [str(form_by_id.get(o, "autre")) for o in org_ids]
print(f"organisations: {len(orgs):,} (from {sp.org_name.nunique():,} printed spellings)")
ranks = sorted(set(sp.position_rank.fillna("").astype(str))
               | set(elite.peak_rank.fillna("").astype(str)))
rank_ix = {r: i for i, r in enumerate(ranks)}

pid_ix = {p: i for i, p in enumerate(elite.person_id)}

rank_score = (spells.drop_duplicates("position_rank")
              .set_index("position_rank").rank_score.to_dict())

people = [
    [
        row.name_,
        rank_ix.get(str(row.peak_rank), 0),
        int(row.first_year),
        int(row.last_year),
    ]
    for row in elite.rename(columns={"name": "name_"}).itertuples(index=False)
]


def issue_ref(issue_key: str) -> str:
    """'journal-officiel/fr/1987/078' -> '1987/078'."""
    parts = str(issue_key).split("/")
    return "/".join(parts[-2:]) if len(parts) >= 2 else ""


spell_rows = []
for s in sp.itertuples(index=False):
    spell_rows.append([
        pid_ix[s.person_id],
        org_ix.get(str(s.org_id), 0),
        rank_ix.get(str(s.position_rank), 0),
        int(s.start_year),
        int(s.end_year),
        str(s.position_clean)[:MAX_POSITION_CHARS] if pd.notna(s.position_clean) else "",
        str(s.start_act) if pd.notna(s.start_act) else "",
        str(s.start_date)[:10] if pd.notna(s.start_date) else "",
        issue_ref(s.start_issue),
        str(s.end_reason),
    ])

# --- relations ------------------------------------------------------------
coll = pd.read_csv(PROC / "edges" / "colleague.csv.gz")
coll = coll[coll.source.isin(elite_ids) & coll.target.isin(elite_ids)]
colleague = [
    [pid_ix[e.source], pid_ix[e.target], int(e.start_year), int(e.end_year),
     org_ix.get(str(e.org_id), 0)]
    for e in coll.itertuples(index=False)
]
print(f"colleague edges: {len(colleague):,}")

succ = pd.read_csv(PROC / "edges" / "succession.csv.gz")
succ = succ[succ.source.isin(elite_ids) & succ.target.isin(elite_ids)]
succession = [
    [pid_ix[e.source], pid_ix[e.target], int(e.year), org_ix.get(str(e.org_id), 0)]
    for e in succ.itertuples(index=False)
]
print(f"succession edges: {len(succession):,}")

sig = pd.read_csv(PROC / "edges" / "signature.csv.gz")
sig = sig[sig.source.isin(elite_ids) & sig.target.isin(elite_ids)]
signature = [
    [pid_ix[e.source], pid_ix[e.target], int(e.year), org_ix.get(str(e.org_id), 0)]
    for e in sig.itertuples(index=False)
]
print(f"signature edges: {len(signature):,}")

# --- context series -------------------------------------------------------
by_year = events.groupby("year").size()
years = list(range(1957, 2027))
series = [int(by_year.get(y, 0)) for y in years]

payload = {
    "meta": {
        "rank_cut": RANK_CUT,
        "years": [years[0], years[-1]],
        "n_events": int(len(events)),
        "n_persons_total": int(len(persons)),
        "n_spells_total": int(len(spells)),
        "n_issues": 6378,
    },
    "orgs": orgs,
    "orgForms": org_forms,
    "ranks": ranks,
    "rankScore": [int(rank_score.get(r, 5)) for r in ranks],
    "people": people,
    "spells": spell_rows,
    "colleague": colleague,
    "succession": succession,
    "signature": signature,
    "eventsPerYear": series,
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(
    "window.__JORT = " + json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + ";",
    encoding="utf-8",
)
print(f"wrote {OUT} — {OUT.stat().st_size / 1e6:.2f} MB")
