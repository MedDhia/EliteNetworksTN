"""Stage 1 -- ingest and clean the curated seed edge list.

The seed sheet is the project's atemporal backbone: a multiplex elite network
with no dates. This stage parses it, quarantines anything it cannot interpret
(never silently dropping a row), splits ``FORMER *`` labels into a role plus a
known-past flag, and emits normalised node and edge tables keyed by stable ids.

Every row of the input is accounted for in ``seed_reconciliation.csv``.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from .names import node_id, parse_org, parse_person
from .paths import INTERIM, PROCESSED, RAW, ensure_dirs, load_config

SHEET_ID = "1aHQnVDFfQEoF6JRAB8HHnFcqG3n2FV2i0OA7tNXc3EI"
SHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

EXPECTED_COLUMNS = ["FROM_TYPE", "FROM", "EDGE", "TO_TYPE", "TO"]

NODE_TYPES = {
    "PERSON",
    "COMPANY",
    "ORGANIZATION",
    "GOVERNMENT",
    "GOVERNMENTAL ORGANIZATION",
    "PARTY",
    "PARTY STRUCTURE",
    "PARLIAMENTARY BLOC",
    "CONSORTIUM",
}

# Which analytic layer a tie belongs to, derived from the target node type.
# Kept separate from tie_class (which comes from the edge label) because a
# MEMBER tie means something different to a party organ than to a company.
LAYER_BY_TARGET = {
    "COMPANY": "corporate",
    "ORGANIZATION": "civil_society",
    "GOVERNMENT": "state",
    "GOVERNMENTAL ORGANIZATION": "state",
    "PARTY": "party",
    "PARTY STRUCTURE": "party",
    "PARLIAMENTARY BLOC": "parliament",
    "CONSORTIUM": "corporate",
    "PERSON": "interpersonal",
}


@dataclass
class Reject:
    line_no: int
    reason: str
    raw: str


def fetch_sheet(dest: Path, url: str = SHEET_CSV_URL) -> Path:
    """Download the seed sheet CSV. Committed to data/raw/seed for provenance."""
    import httpx

    dest.parent.mkdir(parents=True, exist_ok=True)
    cfg = load_config("scope")["http"]
    with httpx.Client(
        timeout=cfg["timeout_seconds"],
        follow_redirects=True,
        headers={"User-Agent": cfg["user_agent"]},
    ) as client:
        resp = client.get(url)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    return dest


def _read_rows(path: Path) -> tuple[list[dict], list[Reject]]:
    """Parse with a real CSV reader; quarantine structurally bad rows."""
    rows: list[dict] = []
    rejects: list[Reject] = []
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        if [h.strip() for h in header] != EXPECTED_COLUMNS:
            raise ValueError(f"unexpected header: {header!r}")
        for line_no, fields in enumerate(reader, start=2):
            raw = ",".join(fields)
            if len(fields) != 5:
                rejects.append(Reject(line_no, f"field_count={len(fields)}", raw))
                continue
            if not any(f.strip() for f in fields):
                rejects.append(Reject(line_no, "blank_row", raw))
                continue
            rec = dict(zip(EXPECTED_COLUMNS, (f.strip() for f in fields)))
            if rec["FROM_TYPE"] not in NODE_TYPES:
                rejects.append(Reject(line_no, f"bad_FROM_TYPE={rec['FROM_TYPE']!r}", raw))
                continue
            if rec["TO_TYPE"] not in NODE_TYPES:
                rejects.append(Reject(line_no, f"bad_TO_TYPE={rec['TO_TYPE']!r}", raw))
                continue
            if not rec["FROM"] or not rec["TO"]:
                rejects.append(Reject(line_no, "empty_endpoint", raw))
                continue
            rec["_line"] = line_no
            rows.append(rec)
    return rows, rejects


def build(seed_csv: Path) -> dict[str, int]:
    ensure_dirs()
    roles = load_config("vocab_roles")
    seed_map: dict = roles["seed_edge_map"]

    rows, rejects = _read_rows(seed_csv)

    # ---------------- edges ----------------
    edges: list[dict] = []
    seen: set[tuple] = set()
    dup_count = 0
    unmapped_edges: Counter = Counter()

    for rec in rows:
        label = rec["EDGE"]
        mapping = seed_map.get(label)
        if mapping is None:
            unmapped_edges[label] += 1
            rejects.append(
                Reject(rec["_line"], f"unmapped_EDGE={label!r}", ",".join(
                    rec[c] for c in EXPECTED_COLUMNS)))
            continue

        src = node_id(rec["FROM"], rec["FROM_TYPE"])
        dst = node_id(rec["TO"], rec["TO_TYPE"])
        key = (src, dst, mapping["role_canonical"], mapping["is_former"])
        if key in seen:
            dup_count += 1
            continue
        seen.add(key)

        edges.append(
            {
                "edge_id": "SEEDE_" + hashlib.blake2b(
                    "|".join(map(str, key)).encode(), digest_size=8).hexdigest(),
                "from_node_id": src,
                "to_node_id": dst,
                "from_label": rec["FROM"],
                "to_label": rec["TO"],
                "from_type": rec["FROM_TYPE"],
                "to_type": rec["TO_TYPE"],
                "edge_label_raw": label,
                "role_canonical": mapping["role_canonical"],
                "tie_class": mapping["tie_class"],
                "layer": LAYER_BY_TARGET.get(rec["TO_TYPE"], "other"),
                "is_former": mapping["is_former"],
                "is_self_loop": src == dst,
                "source_line": rec["_line"],
                "evidence": "seed_only",
            }
        )

    # ---------------- nodes ----------------
    degree: Counter = Counter()
    labels: dict[str, Counter] = defaultdict(Counter)
    types: dict[str, str] = {}
    acronyms: dict[str, set[str]] = defaultdict(set)

    for rec in rows:
        for side in ("FROM", "TO"):
            nt = rec[f"{side}_TYPE"]
            label = rec[side]
            nid = node_id(label, nt)
            degree[nid] += 1
            labels[nid][label] += 1
            types[nid] = nt
            if nt != "PERSON":
                acr = parse_org(label).acronym
                if acr:
                    acronyms[nid].add(acr)

    nodes: list[dict] = []
    for nid, deg in degree.items():
        nt = types[nid]
        label = labels[nid].most_common(1)[0][0]
        alt = {lab for lab in labels[nid] if lab != label} | acronyms[nid]
        if nt == "PERSON":
            parsed = parse_person(label)
            normalised = parsed.normalised
            married = parsed.married_name
        else:
            normalised = parse_org(label).normalised
            married = ""
        nodes.append(
            {
                "node_id": nid,
                "label": label,
                "node_type": nt,
                "label_normalised": normalised,
                "married_or_maiden_name": married,
                "alt_names": ";".join(sorted(a for a in alt if a)),
                "seed_degree": deg,
                "source": "seed",
            }
        )
    nodes.sort(key=lambda r: (-r["seed_degree"], r["node_id"]))

    # ---------------- write ----------------
    _write_csv(PROCESSED / "seed_nodes.csv", nodes)
    _write_csv(PROCESSED / "seed_edges.csv", edges)
    _write_csv(
        INTERIM / "seed_rejects.csv",
        [{"line_no": r.line_no, "reason": r.reason, "raw_row": r.raw} for r in rejects],
        fieldnames=["line_no", "reason", "raw_row"],
    )

    recon = [
        {"item": "input_data_rows", "count": len(rows) + len(rejects)},
        {"item": "rows_parsed_ok", "count": len(rows)},
        {"item": "rows_quarantined", "count": len(rejects)},
        {"item": "duplicate_edges_collapsed", "count": dup_count},
        {"item": "edges_emitted", "count": len(edges)},
        {"item": "nodes_emitted", "count": len(nodes)},
        {"item": "self_loops_flagged", "count": sum(e["is_self_loop"] for e in edges)},
        {"item": "former_edges", "count": sum(e["is_former"] for e in edges)},
    ]
    _write_csv(PROCESSED / "seed_reconciliation.csv", recon, fieldnames=["item", "count"])

    stats = {r["item"]: r["count"] for r in recon}
    if unmapped_edges:
        print(f"  unmapped edge labels: {dict(unmapped_edges)}", file=sys.stderr)
    return stats


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows and not fieldnames:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = fieldnames or list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ingest and clean the seed edge list.")
    ap.add_argument("--fetch", action="store_true", help="re-download the sheet first")
    ap.add_argument(
        "--seed-csv",
        type=Path,
        default=RAW / "seed" / "tunisia_elites_seed.csv",
        help="local path to the seed CSV",
    )
    args = ap.parse_args(argv)

    if args.fetch or not args.seed_csv.exists():
        print(f"fetching seed sheet -> {args.seed_csv}")
        fetch_sheet(args.seed_csv)
    digest = hashlib.sha256(args.seed_csv.read_bytes()).hexdigest()
    (args.seed_csv.with_suffix(".csv.sha256")).write_text(
        f"{digest}  {args.seed_csv.name}\n", encoding="utf-8")

    stats = build(args.seed_csv)
    print(f"seed sha256: {digest}")
    for k, v in stats.items():
        print(f"  {k:28} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
