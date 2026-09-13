"""Run movement extraction across the notice corpus.

Writes two record files under ``data/processed/bourse/records/``:

``movements.jsonl.gz``
    One row per notice: what kind of operation, which company it concerns, its
    dates, and whatever figures the notice states.
``movement_parties.jsonl.gz``
    One row per (movement, party, role). Offers are frequently launched by
    several companies acting in concert, so parties cannot live in the movement
    row itself.

A notice announcing an operation and the notice reporting its result are kept
as separate rows, flagged by ``is_result``. They state different quantities -
sought versus acquired - and merging them would double-count the operation.
"""

from __future__ import annotations

import argparse
import hashlib
import multiprocessing as mp
import traceback

import pdfplumber

from .common import PDF_DIR, PROCESSED, log, now_iso, read_jsonl, write_jsonl
from .extract.movements import find_target, parse_movement

MANIFEST = PROCESSED / "corpus" / "pdf_manifest.jsonl.gz"
RECORDS_DIR = PROCESSED / "records"

MOVEMENT_DOC_TYPES = ("offre_publique", "operation_sur_capital", "augmentation_de_capital")

# Notices are short; the operative text is always at the front. Reading a fixed
# prefix keeps a stray 200-page annex from dominating the run.
MAX_PAGES = 12


def event_date(rec: dict, filing_date: str | None) -> tuple[str | None, str]:
    """Pick the date the movement is dated by, and say which field it came from.

    Preference runs from the most specific statement of when the operation
    happened to the least: an offer's close, its opening, the general meeting
    that decided a capital increase, and finally the filing date, which is only
    ever an upper bound.
    """
    for field in ("close_date", "open_date", "decision_date", "delisting_date"):
        if rec.get(field):
            return rec[field], field
    return filing_date, "filing_date"


def process(entry: dict) -> tuple[dict | None, list[dict]]:
    path = PDF_DIR / entry["local_path"]
    with pdfplumber.open(path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages[:MAX_PAGES])
        n_pages = len(pdf.pages)
    title = entry.get("title") or ""
    rec = parse_movement(title, text)
    if rec is None:
        return None, []

    target = find_target(title, text) or entry.get("issuer_hint")
    date, date_src = event_date(rec, entry.get("filing_date"))

    # Hash rather than a truncated node key: these keys are URL-encoded titles
    # that share long prefixes ("resultat-de-loffre-publique-dachat-..."), so
    # truncating collapses distinct filings onto one id.
    movement_id = "MV" + hashlib.sha1(
        f"{entry['node_key']}|{entry.get('pdf_url', '')}".encode("utf-8")
    ).hexdigest()[:12]
    rec.update(
        {
            "movement_id": movement_id,
            "target_name_raw": target,
            "event_date": date,
            "event_date_source": date_src,
            "event_year": int(date[:4]) if date and date[:4].isdigit() else None,
            "doc_node_key": entry["node_key"],
            "doc_type": entry.get("doc_type"),
            "doc_title": title,
            "doc_url": entry.get("pdf_url"),
            "doc_sha256": entry.get("sha256"),
            "filing_date": entry.get("filing_date"),
            "n_pages": n_pages,
            "extracted_at": now_iso(),
        }
    )

    parties = []
    for role, names in (("initiator", rec.pop("initiators", [])),
                        ("concert_party", rec.pop("concert_parties", []))):
        for name in names:
            parties.append(
                {
                    "movement_id": movement_id,
                    "party_name_raw": name,
                    "role": role,
                    "event_type": rec["event_type"],
                    "event_date": date,
                    "event_year": rec["event_year"],
                    "target_name_raw": target,
                    "doc_node_key": entry["node_key"],
                    "doc_url": entry.get("pdf_url"),
                    "doc_sha256": entry.get("sha256"),
                }
            )
    return rec, parties


def _safe(entry: dict):
    try:
        return entry, process(entry), None
    except Exception as exc:
        return entry, (None, []), f"{type(exc).__name__}: {exc} | {traceback.format_exc(limit=2)}"


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract dated movements from CMF notices")
    ap.add_argument("--doc-types", nargs="*", default=list(MOVEMENT_DOC_TYPES))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=max(1, (mp.cpu_count() or 2) - 1))
    args = ap.parse_args()

    entries = [
        e for e in read_jsonl(MANIFEST)
        if e.get("status") == "ok" and e.get("doc_type") in set(args.doc_types)
    ]
    if args.limit:
        entries = entries[: args.limit]
    log.info("extracting movements from %d notices", len(entries))

    if args.workers == 1:
        results = [_safe(e) for e in entries]
    else:
        with mp.Pool(args.workers) as pool:
            results = pool.map(_safe, entries, chunksize=4)

    movements, parties, failures, skipped = [], [], [], 0
    for entry, (rec, prts), err in results:
        if err:
            failures.append({"node_key": entry["node_key"], "error": err})
            continue
        if rec is None:
            skipped += 1
            continue
        movements.append(rec)
        parties.extend(prts)

    RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(RECORDS_DIR / "movements.jsonl.gz", movements)
    write_jsonl(RECORDS_DIR / "movement_parties.jsonl.gz", parties)
    log.info("movements            %6d rows", len(movements))
    log.info("movement_parties     %6d rows", len(parties))
    if skipped:
        log.info("%d notices had no recognisable operation type", skipped)
    if failures:
        write_jsonl(RECORDS_DIR / "movement_failures.jsonl.gz", failures)
        log.warning("%d notices failed to parse", len(failures))


if __name__ == "__main__":
    main()
