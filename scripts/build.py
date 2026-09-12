"""Build every processed table from data/interim/events_raw.csv."""

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from eltn import network as nw
from eltn import panel as pn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

t0 = time.time()
raw = pd.read_csv(ROOT / "data" / "interim" / "events_raw.csv", low_memory=False)
logging.info("raw events: %s", len(raw))

events = pn.normalise_events(raw)
logging.info("normalised events: %s | persons: %s | orgs: %s",
             len(events), events.person_id.nunique(), events.org_id.nunique())

spells = pn.build_spells(events)
logging.info("spells: %s", len(spells))

person_year = pn.build_person_year(spells)
logging.info("person-years: %s", len(person_year))

persons, orgs = pn.build_registers(events, spells)
logging.info("registers: %s persons, %s organisations", len(persons), len(orgs))

# --- relations ------------------------------------------------------------
aff = nw.affiliation_edges(spells)
coll = nw.colleague_edges(spells)
succ = nw.succession_edges(spells)
sig = nw.signature_edges(events)
dele = nw.delegation_edges(events)
coapp = nw.coappointment_edges(events)
for name, df in [("affiliation", aff), ("colleague", coll), ("succession", succ),
                 ("signature", sig), ("delegation", dele), ("coappointment", coapp)]:
    logging.info("edges %-14s %s", name, len(df))

# --- write ----------------------------------------------------------------
# Everything is gzipped: pandas and R read .csv.gz transparently, and it keeps
# the whole dataset small enough to live in the repository next to the code
# that produced it.


def write(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, compression="gzip")
    logging.info("wrote %-42s %6.1f MB", path.name, path.stat().st_size / 1e6)


write(events, OUT / "events.csv.gz")
write(spells, OUT / "spells.csv.gz")
write(person_year, OUT / "person_year.csv.gz")
write(persons, OUT / "persons.csv.gz")
write(orgs, OUT / "organisations.csv.gz")

edge_dir = OUT / "edges"
write(aff, edge_dir / "affiliation.csv.gz")
write(coll, edge_dir / "colleague.csv.gz")
write(succ, edge_dir / "succession.csv.gz")
write(sig, edge_dir / "signature.csv.gz")
if not dele.empty:
    write(dele, edge_dir / "delegation.csv.gz")
write(coapp, edge_dir / "coappointment.csv.gz")

# Dynamic bipartite graph for Gephi.  Restricted to senior offices: the full
# 43k-person graph is neither loadable nor readable in a layout tool, and the
# complete edge list is already available as CSV for programmatic work.
SENIOR = 55  # directeur and above; see RANK_SCALE in normalize.py
senior_aff = aff[aff.rank_score >= SENIOR]
senior_people = set(senior_aff.source)
senior_orgs = set(senior_aff.target)
nodes = pd.concat([
    persons[persons.person_id.isin(senior_people)]
    [["person_id", "name", "peak_rank", "first_year", "last_year"]]
    .rename(columns={"person_id": "node_id", "name": "label",
                     "peak_rank": "category"})
    .assign(kind="person"),
    orgs[orgs.org_id.isin(senior_orgs)]
    [["org_id", "org_name", "org_form", "first_year", "last_year"]]
    .rename(columns={"org_id": "node_id", "org_name": "label",
                     "org_form": "category"})
    .assign(kind="organisation"),
], ignore_index=True).drop_duplicates("node_id")
nw.to_gexf(nodes, senior_aff.assign(weight=1.0),
           OUT / "graphs" / "affiliation_senior_dynamic.gexf")
logging.info("gexf: %s nodes, %s edges (rank_score >= %s)",
             len(nodes), len(senior_aff), SENIOR)

logging.info("DONE in %.1fs", time.time() - t0)
