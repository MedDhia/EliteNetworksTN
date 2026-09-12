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
from collections import Counter

import pdfplumber

from .common import PROCESSED, PDF_DIR, log, now_iso, read_jsonl, write_jsonl
from .extract.ocr import has_text_layer, ocr_document
from .extract.records import parse_all
from .extract.tables import extract_tables

MANIFEST = PROCESSED / "corpus" / "pdf_manifest.jsonl.gz"
RECORDS_DIR = PROCESSED / "records"

# How far into a filing to read, by document type. A registration document is
# read whole: it is the validated core source, its governance chapter sits
# after the business description, and there are only ~200 of them. Annual
# reports and prospectuses are read only as far as their front matter, which is
# where the board and shareholder tables are; the rest is financial statements,
# hundreds of pages of it, and reading them cost a worker 11 GB and a kill.
# An explicit --max-pages overrides this.
DEFAULT_MAX_PAGES = {
    "rapport_annuel": 60,
    "prospectus": 80,
}

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


# "Rapport Annuel 2015", "exercice clos le 31 decembre 2015", "exercice 2015",
# and the year the CMF puts in the file name ("rapport_biat_2025.pdf").
_REPORT_YEAR_TEXT = re.compile(
    r"(?:rapport\s+annuel\s+(?:de\s+l['’]exercice\s+)?|"
    r"exercice\s+(?:clos\s+le\s+\d{1,2}\s+\w+\s+)?|"
    r"au\s+31[/\s.-]*(?:12|d[ée]cembre)[/\s.-]*)((?:19|20)\d{2})",
    re.I,
)
_REPORT_YEAR_FILE = re.compile(r"((?:19|20)\d{2})(?=[^0-9]*\.pdf$)", re.I)


def detect_report_year(text: str, local_path: str) -> int | None:
    """Year an annual report covers, which is not the year it was filed.

    Reports are published in the year after the one they describe, so the
    filing date is systematically one year late. The document states its own
    period, and the CMF puts the year in the file name; both are used.
    """
    head = re.sub(r"\s+", " ", text[:6000])
    years = [int(m.group(1)) for m in _REPORT_YEAR_TEXT.finditer(head)]
    years = [y for y in years if 1990 <= y <= 2035]
    if years:
        # The reporting year recurs throughout the front matter; the most
        # frequent mention is more reliable than the first.
        return Counter(years).most_common(1)[0][0]
    m = _REPORT_YEAR_FILE.search(local_path or "")
    if m and 1990 <= int(m.group(1)) <= 2035:
        return int(m.group(1))
    return None


def process_pdf(entry: dict, max_pages: int | None = None,
                ocr: bool = False, ocr_max_pages: int | None = None) -> dict[str, list[dict]]:
    path = PDF_DIR / entry["local_path"]
    issuer, ref_year = issuer_from_title(entry.get("title", ""), entry.get("issuer_hint"))
    doc = {
        "node_key": entry["node_key"],
        "doc_type": entry.get("doc_type"),
        "title": entry.get("title"),
        "pdf_url": entry.get("pdf_url"),
        "filing_date": entry.get("filing_date"),
    }
    if max_pages is None:
        max_pages = DEFAULT_MAX_PAGES.get(entry.get("doc_type"))
    scanned = False
    with pdfplumber.open(path) as pdf:
        n_pages = len(pdf.pages)
        scanned = ocr and not has_text_layer(pdf)
        if not scanned:
            tables = extract_tables(pdf, max_pages=max_pages)
            if entry.get("doc_type") == "rapport_annuel" and ref_year is None:
                head = "\n".join((p.extract_text() or "") for p in pdf.pages[:6])
                ref_year = detect_report_year(head, entry.get("local_path", ""))

    if scanned:
        # No text layer at all: the file is page images. Read it by OCR, which
        # yields word positions and so goes through the from-words path.
        ocr_doc = ocr_document(path, max_pages=ocr_max_pages)
        tables = extract_tables(ocr_doc, from_words=True)
        if entry.get("doc_type") == "rapport_annuel" and ref_year is None:
            head = "\n".join(p.extract_text() for p in ocr_doc.pages[:6])
            ref_year = detect_report_year(head, entry.get("local_path", ""))

    out = parse_all(tables, doc)
    for kind, rows in out.items():
        for r in rows:
            r["issuer_name_raw"] = issuer
            r["issuer_ref_year"] = ref_year
            r["doc_sha256"] = entry.get("sha256")
            r["record_kind"] = kind
            # Marked on every row, because an OCR'd row is weaker evidence than
            # a row read from a text layer and an analyst may want to drop them.
            r["from_ocr"] = scanned
    out["_meta"] = [
        {
            "node_key": entry["node_key"],
            "issuer_name_raw": issuer,
            "issuer_ref_year": ref_year,
            "n_pages": n_pages,
            "n_tables": len(tables),
            "from_ocr": scanned,
            "counts": {k: len(v) for k, v in out.items() if k != "_meta"},
            "extracted_at": now_iso(),
        }
    ]
    return out


def _safe_process(entry: dict, max_pages: int | None, ocr: bool = False,
                  ocr_max_pages: int | None = None):
    """Run extraction, returning (result, error) so one bad file cannot abort a run."""
    try:
        return process_pdf(entry, max_pages=max_pages, ocr=ocr,
                           ocr_max_pages=ocr_max_pages), None
    except Exception as exc:
        return {}, f"{type(exc).__name__}: {exc} | {traceback.format_exc(limit=2)}"


def _safe_process_pair(entry: dict, max_pages: int | None, ocr: bool = False,
                       ocr_max_pages: int | None = None):
    """Pool worker: returns the entry alongside its outcome, to keep them paired."""
    return entry, _safe_process(entry, max_pages, ocr, ocr_max_pages)


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract records from downloaded filings")
    ap.add_argument("--workers", type=int, default=max(1, (mp.cpu_count() or 2) - 1),
                    help="parallel worker processes (1 disables multiprocessing)")
    ap.add_argument("--doc-types", nargs="*", default=["document_de_reference"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--max-pages", type=int, default=None)
    ap.add_argument("--year-min", type=int, default=None,
                    help="only documents whose file name carries a year >= this")
    ap.add_argument("--year-max", type=int, default=None,
                    help="only documents whose file name carries a year <= this")
    ap.add_argument("--skip-processed", action="store_true",
                    help="skip documents already present in the extraction log, "
                         "so a long corpus can be worked through in batches")
    ap.add_argument("--ocr", action="store_true",
                    help="read documents that carry no text layer by OCR; without "
                         "this they are recorded as yielding nothing")
    ap.add_argument("--ocr-max-pages", type=int, default=None,
                    help="pages to OCR per document (default 40). Governance "
                         "tables sit in the front matter; the tail is accounts")
    ap.add_argument("--only-scanned", action="store_true",
                    help="process only documents with no text layer, for working "
                         "through the scanned part of the corpus on its own")
    args = ap.parse_args()

    entries = [
        e for e in read_jsonl(MANIFEST)
        if e.get("status") == "ok"
        and (not args.doc_types or e.get("doc_type") in args.doc_types)
    ]
    if args.year_min or args.year_max:
        # The CMF puts the reporting year in the file name, which lets a
        # particular period be worked through first - useful when the corpus is
        # larger than one sitting and some years matter more than others.
        lo = args.year_min or 0
        hi = args.year_max or 9999

        def _yr(e):
            ys = [int(y) for y in re.findall(r"(?:19|20)\d{2}", e.get("local_path", ""))
                  if 1990 <= int(y) <= 2035]
            return max(ys) if ys else None

        entries = [e for e in entries if (_yr(e) is not None and lo <= _yr(e) <= hi)]
        log.info("restricted to file-name years %s-%s: %d documents", lo, hi, len(entries))

    if args.skip_processed:
        done = {r.get("node_key") for r in read_jsonl(RECORDS_DIR / "extraction_log.jsonl.gz")}
        before = len(entries)
        entries = [e for e in entries if e["node_key"] not in done]
        log.info("%d of %d documents already extracted", before - len(entries), before)
    # The manifest outlives the files: source PDFs are not redistributed, and a
    # corpus larger than the disk is worked through by extracting a batch and
    # dropping its files. A missing file is not a failure to report, it is a
    # document this machine does not currently hold.
    present = [e for e in entries if (PDF_DIR / e["local_path"]).exists()]
    if len(present) != len(entries):
        log.info("%d of %d documents are not downloaded; skipping them",
                 len(entries) - len(present), len(entries))
        entries = present

    if args.only_scanned:
        # Opening every PDF to test its text layer is cheap next to OCR'ing it,
        # and it keeps an OCR run from re-reading the digital majority.
        kept = []
        for e in entries:
            try:
                with pdfplumber.open(PDF_DIR / e["local_path"]) as pdf:
                    if not has_text_layer(pdf):
                        kept.append(e)
            except Exception:
                continue
        log.info("%d of %d documents have no text layer", len(kept), len(entries))
        entries = kept
    if args.limit:
        entries = entries[: args.limit]
    log.info("extracting from %d documents", len(entries))

    buckets: dict[str, list[dict]] = {}
    failures = []
    # Documents are independent and each is CPU-bound in pdfplumber, so this
    # scales close to linearly with cores.
    if args.workers == 1:
        results = ((e, _safe_process(e, args.max_pages, args.ocr, args.ocr_max_pages))
                   for e in entries)
    else:
        # maxtasksperchild returns a worker's memory to the OS between
        # documents. Without it one very large filing leaves the worker fat for
        # the rest of the run, and the next large one tips it over.
        with mp.Pool(args.workers, maxtasksperchild=4) as pool:
            pairs = pool.starmap(
                _safe_process_pair,
                [(e, args.max_pages, args.ocr, args.ocr_max_pages) for e in entries],
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
    # Merge rather than overwrite. Running this stage for one document type
    # must not wipe the records extracted from another: the record files are
    # shared across document types, and a plain write would silently drop
    # everything the previous run produced.
    processed_keys = {e["node_key"] for e in entries}
    for kind in set(buckets) | {"blockholders", "director_holdings",
                                "capital_structure", "subsidiaries", "board",
                                "interlocks", "executives", "_meta"}:
        name = "extraction_log" if kind == "_meta" else kind
        path = RECORDS_DIR / f"{name}.jsonl.gz"
        kept = [r for r in read_jsonl(path)
                if r.get("node_key" if kind == "_meta" else "doc_node_key")
                not in processed_keys]
        rows = kept + buckets.get(kind, [])
        if not rows:
            continue
        n = write_jsonl(path, rows)
        log.info("%-20s %6d rows (%d new, %d kept)",
                 name, n, len(buckets.get(kind, [])), len(kept))
    if failures:
        write_jsonl(RECORDS_DIR / "failures.jsonl.gz", failures)
        log.warning("%d documents failed to parse (see failures.jsonl)", len(failures))


if __name__ == "__main__":
    main()
