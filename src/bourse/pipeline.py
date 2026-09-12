"""Run table extraction across the downloaded corpus.

Output is one JSONL file per record kind in ``data/interim/records/``. Each row
keeps its full provenance block, and each also carries the *issuer* - the
company the filing is about - because a blockholder row means nothing without
knowing whose capital is being described.
"""

from __future__ import annotations

import argparse
import multiprocessing as mp
import re
import traceback

import pdfplumber

from .common import PROCESSED, PDF_DIR, log, now_iso, read_jsonl, write_jsonl
from .extract.records import parse_all
from .extract.tables import extract_tables

MANIFEST = PROCESSED / "corpus" / "pdf_manifest.jsonl.gz"
RECORDS_DIR = PROCESSED / "records"

# "Document de reference \" UBCI 2025 \"", "Actualisation du Document de
# reference << BTK Leasing 2025 >>", "Rapport Annuel".
_DOC_PREFIX = re.compile(
    r"^\s*(actualisation\s+du\s+)?(document\s+de\s+r[ée]f[ée]rences?|rapport\s+annuel|"
    r"prospectus|note\s+d.op[ée]ration|avis|r[ée]sultat)\b[\s:.-]*",
    re.I,
)
_QUOTES = "\"'«»“”‹›"


def issuer_from_title(title: str, issuer_hint: str | None = None) -> tuple[str | None, int | None]:
    """Recover (issuer name, reference year) from a filing title.

    Sections that expose a dedicated company field are trusted over the title,
    which is often generic ("Rapport Annuel").
    """
    t = (title or "").strip()
    t = _DOC_PREFIX.sub("", t)
    t = t.strip(_QUOTES + " \t:-–")
    year = None
    m = re.search(r"\b(19|20)\d{2}\b", t)
    if m:
        year = int(m.group(0))
        t = (t[: m.start()] + " " + t[m.end():]).strip()
    t = t.strip(_QUOTES + " \t:-–,")
    t = re.sub(r"\s+", " ", t)
    # Editorial suffixes travel in these titles ("DH 2014 - Voir annexes",
    # "SOTUVER 2019 - actualise"). Everything after a dash or colon separator is
    # commentary on the filing, not part of the company name.
    t = re.split(r"\s+[-–:]\s+", t, maxsplit=1)[0].strip(_QUOTES + " \t:-–,")
    name = issuer_hint or (t if len(t) >= 2 else None)
    return name, year


def process_pdf(entry: dict, max_pages: int | None = None) -> dict[str, list[dict]]:
    path = PDF_DIR / entry["local_path"]
    issuer, ref_year = issuer_from_title(entry.get("title", ""), entry.get("issuer_hint"))
    doc = {
        "node_key": entry["node_key"],
        "doc_type": entry.get("doc_type"),
        "title": entry.get("title"),
        "pdf_url": entry.get("pdf_url"),
        "filing_date": entry.get("filing_date"),
    }
    with pdfplumber.open(path) as pdf:
        tables = extract_tables(pdf, max_pages=max_pages)
        n_pages = len(pdf.pages)
    out = parse_all(tables, doc)
    for kind, rows in out.items():
        for r in rows:
            r["issuer_name_raw"] = issuer
            r["issuer_ref_year"] = ref_year
            r["doc_sha256"] = entry.get("sha256")
            r["record_kind"] = kind
    out["_meta"] = [
        {
            "node_key": entry["node_key"],
            "issuer_name_raw": issuer,
            "issuer_ref_year": ref_year,
            "n_pages": n_pages,
            "n_tables": len(tables),
            "counts": {k: len(v) for k, v in out.items() if k != "_meta"},
            "extracted_at": now_iso(),
        }
    ]
    return out


def _safe_process(entry: dict, max_pages: int | None):
    """Run extraction, returning (result, error) so one bad file cannot abort a run."""
    try:
        return process_pdf(entry, max_pages=max_pages), None
    except Exception as exc:
        return {}, f"{type(exc).__name__}: {exc} | {traceback.format_exc(limit=2)}"


def _safe_process_pair(entry: dict, max_pages: int | None):
    """Pool worker: returns the entry alongside its outcome, to keep them paired."""
    return entry, _safe_process(entry, max_pages)


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract records from downloaded filings")
    ap.add_argument("--workers", type=int, default=max(1, (mp.cpu_count() or 2) - 1),
                    help="parallel worker processes (1 disables multiprocessing)")
    ap.add_argument("--doc-types", nargs="*", default=["document_de_reference"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--max-pages", type=int, default=None)
    args = ap.parse_args()

    entries = [
        e for e in read_jsonl(MANIFEST)
        if e.get("status") == "ok"
        and (not args.doc_types or e.get("doc_type") in args.doc_types)
    ]
    if args.limit:
        entries = entries[: args.limit]
    log.info("extracting from %d documents", len(entries))

    buckets: dict[str, list[dict]] = {}
    failures = []
    # Documents are independent and each is CPU-bound in pdfplumber, so this
    # scales close to linearly with cores.
    if args.workers == 1:
        results = ((e, _safe_process(e, args.max_pages)) for e in entries)
    else:
        with mp.Pool(args.workers) as pool:
            pairs = pool.starmap(
                _safe_process_pair,
                [(e, args.max_pages) for e in entries],
                chunksize=1,
            )
        results = iter(pairs)

    for i, (entry, outcome) in enumerate(results, 1):
        res, err = outcome
        if err is not None:
            failures.append({"node_key": entry["node_key"],
                             "local_path": entry["local_path"], "error": err})
            continue
        for kind, rows in res.items():
            buckets.setdefault(kind, []).extend(rows)
        if i % 20 == 0:
            log.info("  %d/%d documents", i, len(entries))

    RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    for kind, rows in buckets.items():
        name = "extraction_log" if kind == "_meta" else kind
        n = write_jsonl(RECORDS_DIR / f"{name}.jsonl.gz", rows)
        log.info("%-20s %6d rows", name, n)
    if failures:
        write_jsonl(RECORDS_DIR / "failures.jsonl.gz", failures)
        log.warning("%d documents failed to parse (see failures.jsonl)", len(failures))


if __name__ == "__main__":
    main()
