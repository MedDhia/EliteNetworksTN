"""Run AGM resolution extraction across the corpus.

Writes ``board_events.jsonl.gz``: one row per (resolution, person), because a
single resolution routinely appoints several directors at once and each is a
separate governance event.

Every row carries the meeting date, which is what makes these useful. The board
tables in registration documents say who sat on a board; these say when the
meeting seated them, whom they replaced, and when their mandate runs out.
"""

from __future__ import annotations

import argparse
import hashlib
import multiprocessing as mp
import traceback

import pdfplumber

from .common import PDF_DIR, PROCESSED, log, now_iso, read_jsonl, write_jsonl
from .extract.resolutions import GOVERNANCE_EVENTS, parse_document

MANIFEST = PROCESSED / "corpus" / "pdf_manifest.jsonl.gz"
RECORDS_DIR = PROCESSED / "records"

DOC_TYPE = "resolutions_ag"

# Resolution filings are short; a long tail is annexed financial statements.
MAX_PAGES = 12


def process(entry: dict) -> list[dict]:
    path = PDF_DIR / entry["local_path"]
    with pdfplumber.open(path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages[:MAX_PAGES])
        n_pages = len(pdf.pages)

    doc = parse_document(text)
    issuer = entry.get("issuer_hint") or entry.get("title")
    meeting_date = doc["meeting_date"] or entry.get("filing_date")
    year = int(meeting_date[:4]) if meeting_date and meeting_date[:4].isdigit() else None

    base_id = hashlib.sha1(
        f"{entry['node_key']}|{entry.get('pdf_url', '')}".encode("utf-8")
    ).hexdigest()[:12]

    rows: list[dict] = []
    for ev in doc["events"]:
        prov = {
            "firm_name_raw": issuer,
            "meeting_kind": doc["meeting_kind"],
            "meeting_date": meeting_date,
            "meeting_year": year,
            "meeting_date_source": "document" if doc["meeting_date"] else "filing_date",
            "resolution_number": ev["resolution_number"],
            "n_people_in_resolution": ev["n_people"],
            "event_type": ev["event_type"],
            "role": ev["role"],
            "replaces_name_raw": ev["replaces_name_raw"],
            "board_decision_date": ev["board_decision_date"],
            "term_years": ev["term_years"],
            "term_end_year": ev["term_end_year"],
            "adoption": ev["adoption"],
            "excerpt": ev["excerpt"],
            "doc_node_key": entry["node_key"],
            "doc_type": entry.get("doc_type"),
            "doc_url": entry.get("pdf_url"),
            "doc_sha256": entry.get("sha256"),
            "n_pages": n_pages,
            "extracted_at": now_iso(),
        }
        people = ev["people"]
        if not people:
            # A decision with no readable name is still evidence that the
            # meeting acted; it is kept so coverage is not overstated by
            # silently dropping it.
            rows.append({
                "board_event_id": f"BE{base_id}-{ev['resolution_number'] or 0}-0",
                "person_name_raw": None, "entity_name_raw": None,
                "seat_holder_type": None, **prov,
            })
            continue
        for i, person in enumerate(people):
            rows.append({
                "board_event_id": f"BE{base_id}-{ev['resolution_number'] or 0}-{i}",
                "person_name_raw": person["person_name_raw"],
                "entity_name_raw": person["entity_name_raw"],
                "seat_holder_type": person["seat_holder_type"],
                **prov,
            })
    return rows


def _safe(entry: dict):
    try:
        return entry, process(entry), None
    except Exception as exc:
        return entry, [], f"{type(exc).__name__}: {exc} | {traceback.format_exc(limit=2)}"


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract board events from AGM resolutions")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=max(1, (mp.cpu_count() or 2) - 1))
    args = ap.parse_args()

    entries = [
        e for e in read_jsonl(MANIFEST)
        if e.get("status") == "ok" and e.get("doc_type") == DOC_TYPE
    ]
    if args.limit:
        entries = entries[: args.limit]
    log.info("extracting board events from %d resolution filings", len(entries))

    if args.workers == 1:
        results = [_safe(e) for e in entries]
    else:
        with mp.Pool(args.workers) as pool:
            results = pool.map(_safe, entries, chunksize=4)

    rows, failures, empty = [], [], 0
    for entry, got, err in results:
        if err:
            failures.append({"node_key": entry["node_key"], "error": err})
            continue
        if not got:
            empty += 1
        rows.extend(got)

    RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(RECORDS_DIR / "board_events.jsonl.gz", rows)
    named = sum(1 for r in rows if r["person_name_raw"])
    gov = sum(1 for r in rows if r["event_type"] in GOVERNANCE_EVENTS)
    log.info("board_events         %6d rows (%d naming a person, %d governance)",
             len(rows), named, gov)
    log.info("%d filings carried no governance resolution", empty)
    if failures:
        write_jsonl(RECORDS_DIR / "board_event_failures.jsonl.gz", failures)
        log.warning("%d filings failed to parse", len(failures))


if __name__ == "__main__":
    main()
