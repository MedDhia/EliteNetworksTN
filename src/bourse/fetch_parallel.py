"""Download filing PDFs over several connections at once.

The serial fetcher is the right default: it is polite, and for the small
notices it was written for the per-request delay dominates anyway. Annual
reports are different. They average 21 MB, so the time is spent in transfer
rather than between requests, and one stream leaves most of the link idle -
measured over one cycle, 9m20s downloading against 3m19s extracting.

A handful of connections fixes that without making us noisier: the *request
rate* stays low because each request takes seconds to complete, and the total
number of requests is unchanged. The conduct note in docs/SOURCES-bourse.md
still applies - keep the worker count small, and leave the serial fetcher as
the default path.

The manifest is rewritten periodically rather than once at the end, so a run
that is interrupted keeps what it has already retrieved, and extraction can
run against it at the same time (write_jsonl replaces the file atomically).
"""

from __future__ import annotations

import argparse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from .common import (
    PDF_DIR,
    PROCESSED,
    Fetcher,
    log,
    now_iso,
    read_jsonl,
    sha256_bytes,
    write_jsonl,
)
from .fetch_docs import MANIFEST, REGISTRY, local_name


def main() -> None:
    ap = argparse.ArgumentParser(description="Download CMF filing PDFs in parallel")
    ap.add_argument("--doc-types", nargs="*", default=["rapport_annuel"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=4,
                    help="concurrent connections; keep this small")
    ap.add_argument("--delay", type=float, default=0.8,
                    help="minimum delay between requests *within* one connection")
    ap.add_argument("--skip-extracted", action="store_true")
    args = ap.parse_args()

    manifest = {m["pdf_url"]: m for m in read_jsonl(MANIFEST)}
    extracted: set[str] = set()
    if args.skip_extracted:
        extracted = {r.get("node_key") for r in
                     read_jsonl(PROCESSED / "records" / "extraction_log.jsonl.gz")}

    todo = []
    for rec in read_jsonl(REGISTRY):
        if args.doc_types and rec.get("doc_type") not in set(args.doc_types):
            continue
        if rec["node_key"] in extracted:
            continue
        for url in rec.get("pdf_urls") or []:
            local = manifest.get(url, {}).get("local_path")
            if local and (PDF_DIR / local).exists():
                continue
            todo.append((rec, url))
    if args.limit:
        todo = todo[: args.limit]
    log.info("downloading %d PDFs over %d connections", len(todo), args.workers)
    if not todo:
        return

    lock = threading.Lock()
    # One Fetcher per thread: it holds a requests.Session and its own rate
    # limiter, neither of which is safe to share.
    local_state = threading.local()

    def fetch_one(item):
        rec, url = item
        if not hasattr(local_state, "fetcher"):
            local_state.fetcher = Fetcher(min_delay=args.delay, timeout=240)
        blob = local_state.fetcher.get(url, binary=True, min_bytes=2000)
        base = {"pdf_url": url, "node_key": rec["node_key"],
                "doc_type": rec.get("doc_type"), "retrieved_at": now_iso()}
        if blob is None:
            return url, {**base, "status": "failed"}
        if not blob[:5].startswith(b"%PDF"):
            return url, {**base, "status": "not_pdf"}
        name = local_name(rec["node_key"], url)
        (PDF_DIR / name).write_bytes(blob)
        return url, {
            **base,
            "title": rec.get("title"),
            "issuer_hint": rec.get("issuer_hint"),
            "filing_date": rec.get("filing_date"),
            "local_path": name,
            "bytes": len(blob),
            "sha256": sha256_bytes(blob),
            "status": "ok",
        }

    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(fetch_one, item) for item in todo]
        for fut in as_completed(futures):
            try:
                url, entry = fut.result()
            except Exception as exc:
                log.warning("download failed: %s", exc)
                continue
            with lock:
                manifest[url] = entry
                done += 1
                if done % 10 == 0:
                    write_jsonl(MANIFEST, list(manifest.values()))
                    log.info("  %d/%d downloaded", done, len(todo))
    write_jsonl(MANIFEST, list(manifest.values()))
    ok = sum(1 for m in manifest.values() if m.get("status") == "ok")
    log.info("manifest: %d entries, %d retrieved", len(manifest), ok)


if __name__ == "__main__":
    main()
