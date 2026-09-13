"""Stage 8 -- publish the dataset in the formats analysis actually uses.

Five outputs, all derived from the same tables so they cannot disagree:

* SQLite -- the canonical single-file store, with views for common cuts.
* Tidy CSVs -- already written by earlier stages; indexed here.
* Gephi GEXF -- a *dynamic* graph with time spells on nodes and edges, so the
  network can be scrubbed across the January 2011 rupture on a timeline.
* networkDynamic / tsna -- vertex and edge spell files in the order the R
  constructor expects, plus a script that builds and exercises the object.
* networkx / igraph -- per-period snapshot edge lists and a loader.

Censoring survives the round trip. GEXF expresses an open endpoint by omitting
``start`` or ``end``; networkDynamic accepts ``-Inf``/``Inf``. Both are used
rather than substituting the window boundary for an unknown date.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import shutil
import sqlite3
from datetime import date, datetime
from pathlib import Path
from xml.sax.saxutils import escape as _xml_escape

from .paths import INTERIM, PROCESSED, ensure_dirs, load_config, window

def escape(text: str) -> str:
    """Escape a string for use inside an XML attribute.

    saxutils.escape leaves quotes alone, and gazette names contain them
    (a firm registered as ... ITALIA "SGATI"), which produces a malformed
    document. Quotes and apostrophes are escaped here as well.
    """
    return _xml_escape(str(text or ""), {'"': "&quot;", "'": "&apos;"})


EXPORTS = PROCESSED / "exports"
# networkDynamic time origin: the first day of the window, documented in the
# codebook. Read from config so it cannot drift from the data it indexes.
T0 = window()[0]

TABLES = {
    "seed_nodes": PROCESSED / "seed_nodes.csv",
    "seed_edges": PROCESSED / "seed_edges.csv",
    "issue_calendar": PROCESSED / "issue_calendar.csv",
    "blocks_index": PROCESSED / "blocks_index.csv",
    "events": PROCESSED / "events.csv",
    "act_citations": INTERIM / "act_citations.csv",
    "resolution": PROCESSED / "resolution.csv",
    "review_queue": PROCESSED / "review_queue.csv",
    "gazette_only_persons": PROCESSED / "gazette_only_persons.csv",
    "spells": PROCESSED / "spells.csv",
    "spell_observations": PROCESSED / "spell_observations.csv",
    "panel_edges_yearly": PROCESSED / "panel_edges_yearly.csv",
    "panel_edges_monthly": PROCESSED / "panel_edges_monthly.csv",
    "org_ties": PROCESSED / "org_ties.csv",
    "org_tie_spells": PROCESSED / "org_tie_spells.csv",
    "panel_org_ties_yearly": PROCESSED / "panel_org_ties_yearly.csv",
    "rne_org_links": PROCESSED / "rne_org_links.csv",
    "rne_unmatched_identifiers": PROCESSED / "rne_unmatched_identifiers.csv",
    "suspect_holes": PROCESSED / "suspect_holes.csv",
    "hole_exposure_by_layer": PROCESSED / "hole_exposure_by_layer.csv",
    "low_degree_audit": PROCESSED / "low_degree_audit.csv",
    "person_ties": PROCESSED / "person_ties.csv",
    "person_tie_spells": PROCESSED / "person_tie_spells.csv",
    "panel_person_ties_yearly": PROCESSED / "panel_person_ties_yearly.csv",
    "org_entities": PROCESSED / "org_entities.csv",
    "org_entity_members": PROCESSED / "org_entity_members.csv",
    "org_identifiers": PROCESSED / "org_identifiers.csv",
    "org_addresses": PROCESSED / "org_addresses.csv",
    "rne_company_forms": PROCESSED / "rne_company_forms.csv",
    "rne_company_persons": PROCESSED / "rne_company_persons.csv",
}

VIEWS = {
    "v_spells_dated":
        "SELECT * FROM spells WHERE evidence_tier='gazette_dated'",
    "v_spells_certain":
        "SELECT * FROM spells WHERE evidence_tier='gazette_dated' "
        "AND onset<>'' AND link_status='resolved'",
    "v_panel_dated_yearly":
        "SELECT * FROM panel_edges_yearly WHERE evidence_tier='gazette_dated' "
        "AND certainty IN ('certain','probable')",
    "v_provenance":
        "SELECT e.event_id, e.event_type, e.person_mention, e.org_mention, "
        "e.role_canonical, e.event_date, e.date_precision, e.issue_uid, "
        "e.folio_page, e.evidence_quote, c.pub_date, "
        "'https://jort.tn/view/'||e.collection||'/fr/'||e.year||'/'||e.issue AS viewer_url, "
        "'https://lake.jort.tn/'||e.collection||'/fr/'||e.year||'/'||e.issue||'.pdf' AS pdf_url "
        "FROM events e LEFT JOIN issue_calendar c ON c.issue_uid=e.issue_uid",
    # The organisation-to-organisation layer. Ownership is separated from the
    # professional-service and structural relations carried alongside it,
    # because an audit mandate and a shareholding mean very different things and
    # an analysis that mixed them would be reporting neither.
    "v_org_ties":
        "SELECT holder_id, holder_label, target_id, target_label, relation, "
        "onset, terminus, left_censored, right_censored, evidence_tier, "
        "confidence FROM org_tie_spells WHERE is_ownership='1'",
    "v_org_ties_dated":
        "SELECT * FROM org_tie_spells WHERE evidence_tier='gazette_dated' "
        "AND link_status='resolved'",
    "v_org_panel_yearly":
        "SELECT * FROM panel_org_ties_yearly WHERE is_ownership='1'",
    # The kinship layer. Marriage is separated from the natal-surname link
    # carried alongside it: "nee X" is the same woman's birth name, not a
    # husband, and an analysis that counted it as a marriage would be wrong
    # about both the tie and the direction.
    "v_marriages":
        "SELECT person_id, person_label, kin_id, kin_label, relation, "
        "onset_hi AS first_seen, terminus, right_censored, evidence_tier, "
        "confidence FROM person_tie_spells WHERE is_marriage='1'",
    "v_marriages_named":
        "SELECT * FROM person_tie_spells WHERE is_marriage='1' "
        "AND evidence_tier='kinship_dated'",
    "v_person_year_degree":
        "SELECT panel_id, from_node_id AS person_id, COUNT(*) AS degree "
        "FROM panel_edges_yearly WHERE evidence_tier='gazette_dated' "
        "AND certainty IN ('certain','probable') GROUP BY panel_id, from_node_id",
}


# --------------------------------------------------------------------------- #
# events.csv (flatten the jsonl produced by extraction)
# --------------------------------------------------------------------------- #

def write_events_csv() -> int:
    import json

    from .extract import EVENT_FIELDS
    src = INTERIM / "events_raw.jsonl"
    dest = PROCESSED / "events.csv"
    n = 0
    with src.open(encoding="utf-8") as fh, dest.open("w", encoding="utf-8", newline="") as out:
        w = csv.DictWriter(out, fieldnames=EVENT_FIELDS)
        w.writeheader()
        for line in fh:
            w.writerow(json.loads(line))
            n += 1
    return n


# --------------------------------------------------------------------------- #
# SQLite
# --------------------------------------------------------------------------- #

def build_sqlite() -> dict:
    path = PROCESSED / "elitenet.sqlite"
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    counts: dict[str, int] = {}
    for name, csv_path in TABLES.items():
        if not csv_path.exists():
            continue
        with csv_path.open(encoding="utf-8", newline="") as fh:
            reader = csv.reader(fh)
            header = next(reader)
            cols = ", ".join(f'"{h}" TEXT' for h in header)
            con.execute(f'CREATE TABLE "{name}" ({cols})')
            ins = f'INSERT INTO "{name}" VALUES ({", ".join("?" * len(header))})'
            rows = list(reader)
            con.executemany(ins, rows)
            counts[name] = len(rows)
    for idx in (
        'CREATE INDEX ix_events_block ON events(block_uid)',
        'CREATE INDEX ix_events_person ON events(person_mention)',
        'CREATE INDEX ix_events_date ON events(event_date)',
        'CREATE INDEX ix_spells_person ON spells(person_id)',
        'CREATE INDEX ix_spells_org ON spells(org_id)',
        'CREATE INDEX ix_panel_y ON panel_edges_yearly(panel_id)',
        'CREATE INDEX ix_res_key ON resolution(mention_key)',
        'CREATE INDEX ix_orgent_seed ON org_entities(seed_org_id)',
        'CREATE INDEX ix_orgmem_ment ON org_entity_members(org_mention)',
        'CREATE INDEX ix_orgid_org ON org_identifiers(org_id)',
        'CREATE INDEX ix_orgid_val ON org_identifiers(value_normalised)',
        'CREATE INDEX ix_orgaddr_org ON org_addresses(org_id)',
    ):
        try:
            con.execute(idx)
        except sqlite3.OperationalError:
            pass
    for name, sql in VIEWS.items():
        con.execute(f'CREATE VIEW "{name}" AS {sql}')
    con.commit()
    con.close()
    return counts


# --------------------------------------------------------------------------- #
# Gephi dynamic GEXF
# --------------------------------------------------------------------------- #

def _spell_attrs(onset: str, terminus: str) -> str:
    """GEXF spell. An omitted bound is how GEXF says 'open', which is exactly
    what a censored endpoint means, so no boundary date is substituted."""
    parts = []
    if onset:
        parts.append(f'start="{onset}"')
    if terminus:
        parts.append(f'end="{terminus}"')
    return " ".join(parts)


def write_gexf(dated_only: bool, filename: str) -> dict:
    with (PROCESSED / "spells.csv").open(encoding="utf-8", newline="") as fh:
        spells = list(csv.DictReader(fh))
    if dated_only:
        spells = [s for s in spells if s["evidence_tier"] == "gazette_dated"]

    with (PROCESSED / "seed_nodes.csv").open(encoding="utf-8", newline="") as fh:
        seed_nodes = {r["node_id"]: r for r in csv.DictReader(fh)}

    # Node activity is the union of its ties' spells.
    nodes: dict[str, dict] = {}
    for s in spells:
        for nid, label, ntype in ((s["person_id"], s["person_label"], "PERSON"),
                                  (s["org_id"], s["org_label"], "ORG")):
            if not nid:
                continue
            n = nodes.setdefault(nid, {
                "label": label or seed_nodes.get(nid, {}).get("label", nid),
                "type": seed_nodes.get(nid, {}).get("node_type", ntype),
                "onsets": [], "termini": [], "open": False,
            })
            if s["onset"]:
                n["onsets"].append(s["onset"])
            if s["terminus"]:
                n["termini"].append(s["terminus"])
            else:
                n["open"] = True

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<gexf xmlns="http://www.gexf.net/1.3" version="1.3">',
             '  <meta lastmodifieddate="%s">' % date.today().isoformat(),
             '    <creator>EliteNetworksTN</creator>',
             f'    <description>Tunisian elite network '
             f'{T0.isoformat()} to {window()[1].isoformat()}, '
             'dated from the Journal Officiel</description>',
             '  </meta>',
             '  <graph mode="dynamic" timeformat="date" defaultedgetype="directed">',
             '    <attributes class="node" mode="static">',
             '      <attribute id="ntype" title="node_type" type="string"/>',
             '    </attributes>',
             '    <attributes class="edge" mode="static">',
             '      <attribute id="role" title="role" type="string"/>',
             '      <attribute id="layer" title="layer" type="string"/>',
             '      <attribute id="tier" title="evidence_tier" type="string"/>',
             '      <attribute id="status" title="link_status" type="string"/>',
             '      <attribute id="trule" title="terminus_rule" type="string"/>',
             '    </attributes>',
             '    <nodes>']
    for nid, n in nodes.items():
        onset = min(n["onsets"]) if n["onsets"] else ""
        terminus = "" if n["open"] or not n["termini"] else max(n["termini"])
        sp = _spell_attrs(onset, terminus)
        lines.append(f'      <node id="{escape(nid)}" label="{escape(n["label"] or nid)}">')
        lines.append('        <attvalues>'
                     f'<attvalue for="ntype" value="{escape(n["type"])}"/></attvalues>')
        if sp:
            lines.append(f'        <spells><spell {sp}/></spells>')
        lines.append('      </node>')
    lines.append('    </nodes>')
    lines.append('    <edges>')
    for s in spells:
        if not s["person_id"] or not s["org_id"]:
            continue
        sp = _spell_attrs(s["onset"], s["terminus"])
        lines.append(f'      <edge id="{escape(s["spell_id"])}" '
                     f'source="{escape(s["person_id"])}" target="{escape(s["org_id"])}">')
        lines.append('        <attvalues>'
                     f'<attvalue for="role" value="{escape(s["role_canonical"])}"/>'
                     f'<attvalue for="layer" value="{escape(s["layer"])}"/>'
                     f'<attvalue for="tier" value="{escape(s["evidence_tier"])}"/>'
                     f'<attvalue for="status" value="{escape(s["link_status"])}"/>'
                     f'<attvalue for="trule" value="{escape(s["terminus_rule"])}"/>'
                     '</attvalues>')
        if sp:
            lines.append(f'        <spells><spell {sp}/></spells>')
        lines.append('      </edge>')
    lines += ['    </edges>', '  </graph>', '</gexf>']

    EXPORTS.mkdir(parents=True, exist_ok=True)
    (EXPORTS / filename).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"nodes": len(nodes), "edges": len(spells)}


# --------------------------------------------------------------------------- #
# networkDynamic / tsna
# --------------------------------------------------------------------------- #

def _days(iso: str) -> str:
    if not iso:
        return ""
    try:
        return str((datetime.strptime(iso[:10], "%Y-%m-%d").date() - T0).days)
    except ValueError:
        return ""


def write_networkdynamic() -> dict:
    rnd = EXPORTS / "rnd"
    rnd.mkdir(parents=True, exist_ok=True)
    with (PROCESSED / "spells.csv").open(encoding="utf-8", newline="") as fh:
        spells = [s for s in csv.DictReader(fh) if s["evidence_tier"] == "gazette_dated"]

    vertices: dict[str, int] = {}

    def vid(node: str) -> int:
        if node not in vertices:
            vertices[node] = len(vertices) + 1     # networkDynamic is 1-indexed
        return vertices[node]

    edge_rows = []
    for s in spells:
        if not s["person_id"] or not s["org_id"]:
            continue
        onset = _days(s["onset"]) or "-Inf"        # left-censored
        term = _days(s["terminus"]) or "Inf"       # right-censored
        edge_rows.append({
            "onset": onset, "terminus": term,
            "tail": vid(s["person_id"]), "head": vid(s["org_id"]),
            "spell_id": s["spell_id"], "role": s["role_canonical"],
            "layer": s["layer"], "link_status": s["link_status"],
        })

    labels: dict[str, str] = {}
    types: dict[str, str] = {}
    for s in spells:
        labels.setdefault(s["person_id"], s["person_label"] or s["person_id"])
        types.setdefault(s["person_id"], "PERSON")
        labels.setdefault(s["org_id"], s["org_label"] or s["org_id"])
        types.setdefault(s["org_id"], "ORG")

    vertex_spells = []
    activity: dict[str, list[tuple[str, str]]] = {}
    for e, s in zip(edge_rows, [x for x in spells if x["person_id"] and x["org_id"]]):
        for node in (s["person_id"], s["org_id"]):
            activity.setdefault(node, []).append((e["onset"], e["terminus"]))
    for node, spans in activity.items():
        onsets = [o for o, _t in spans]
        termini = [t for _o, t in spans]
        onset = "-Inf" if "-Inf" in onsets else str(min(int(o) for o in onsets))
        term = "Inf" if "Inf" in termini else str(max(int(t) for t in termini))
        vertex_spells.append({"onset": onset, "terminus": term,
                              "vertex.id": vertices[node]})

    _csv(rnd / "edge_spells.csv", edge_rows,
         ["onset", "terminus", "tail", "head", "spell_id", "role", "layer", "link_status"])
    _csv(rnd / "vertex_spells.csv", vertex_spells, ["onset", "terminus", "vertex.id"])
    _csv(rnd / "node_key.csv",
         [{"vertex.id": v, "node_id": k, "label": labels.get(k, k),
           "node_type": types.get(k, "")} for k, v in vertices.items()],
         ["vertex.id", "node_id", "label", "node_type"])
    return {"vertices": len(vertices), "edge_spells": len(edge_rows)}


# --------------------------------------------------------------------------- #
# Python snapshots
# --------------------------------------------------------------------------- #

def write_snapshots() -> dict:
    snap = EXPORTS / "snapshots"
    snap.mkdir(parents=True, exist_ok=True)
    written = 0
    for gran in ("yearly", "monthly"):
        src = PROCESSED / f"panel_edges_{gran}.csv"
        if not src.exists():
            continue
        buckets: dict[str, list[dict]] = {}
        with src.open(encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                if r["evidence_tier"] != "gazette_dated":
                    continue
                if r["certainty"] not in ("certain", "probable"):
                    continue
                buckets.setdefault(r["panel_id"].split(":", 1)[1], []).append(r)
        for period, rows in sorted(buckets.items()):
            _csv(snap / f"{gran}_{period}.csv", rows,
                 ["from_node_id", "to_node_id", "role_canonical", "layer",
                  "certainty", "spell_id"])
            written += 1
    return {"snapshot_files": written}


def _csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


# The largest derived tables are committed gzipped: uncompressed they run to
# tens of megabytes, which does not belong in a git history, but they are the
# substance of the dataset and should not merely be "rebuildable".
GZIP_TABLES = ["events.csv", "blocks_index.csv", "resolution.csv",
               "panel_edges_monthly.csv", "panel_edges_yearly.csv",
               "gazette_only_persons.csv", "spells.csv",
               # The organisation attribute tables reach the same scale: an
               # address per observation over 10,528 firms is 17 MB, and the
               # org-tie queue carries 10,586 rows with their evidence quotes.
               "org_addresses.csv", "org_identifiers.csv",
               "org_ties_review_queue.csv", "person_ties_review_queue.csv",
               # 39 MB, 15 MB and 27 MB respectively at full corpus size.
               "org_entities.csv", "org_entity_keys.csv",
               "org_entity_members.csv",
               # 96,002 companies and 113,400 officer links, the latter
               # carrying an evidence quote per row.
               "rne_company_forms.csv", "rne_company_persons.csv"]


def gzip_large_tables() -> dict:
    out = {}
    for name in GZIP_TABLES:
        src = PROCESSED / name
        if not src.exists():
            continue
        dest = src.with_suffix(src.suffix + ".gz")
        with src.open("rb") as fh, gzip.open(dest, "wb", compresslevel=9) as gz:
            shutil.copyfileobj(fh, gz)
        out[name] = round(dest.stat().st_size / 1e6, 1)
    return out


def run() -> dict:
    ensure_dirs()
    stats = {"events_csv_rows": write_events_csv()}
    stats["sqlite_tables"] = len(build_sqlite())
    stats["gexf_dated"] = write_gexf(True, "elite_network_dynamic.gexf")
    stats["gexf_full"] = write_gexf(False, "elite_network_full.gexf")
    stats["networkdynamic"] = write_networkdynamic()
    stats.update(write_snapshots())
    stats["gzipped_MB"] = gzip_large_tables()
    return stats


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description="Export the dataset.").parse_args(argv)
    for k, v in run().items():
        print(f"  {k:22} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
