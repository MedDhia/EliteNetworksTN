"""Download the PDFs named in the registry and record their content hashes.

The hash matters: CMF occasionally republishes a filing at the same URL, and a
dataset whose provenance is only a URL cannot tell the two versions apart. Every
downloaded file is recorded as (url, sha256, bytes, retrieved_at).
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from .common import (
    PROCESSED,
    PDF_DIR,
    Fetcher,
    log,
    now_iso,
    read_jsonl,
    sha256_bytes,
    write_jsonl,
)

REGISTRY = PROCESSED / "corpus" / "cmf_registry.jsonl.gz"
MANIFEST = PROCESSED / "corpus" / "pdf_manifest.jsonl.gz"

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def local_name(node_key: str, url: str) -> str:
    """Deterministic on-disk name: node key plus the origin file name."""
    tail = unquote(urlparse(url).path.rsplit("/", 1)[-1]) or "doc.pdf"
    stem = _SAFE.sub("_", unquote(node_key))[:80]
    tail = _SAFE.sub("_", tail)[-60:]
    return f"{stem}__{tail}"


def download(
    fetcher: Fetcher,
    records: list[dict],
    *,
    doc_types: list[str] | None,
    limit: int | None,
    skip_existing: bool = True,
) -> list[dict]:
    manifest = {m["pdf_url"]: m for m in read_jsonl(MANIFEST)}

    todo = []
    for rec in records:
        if doc_types and rec.get("doc_type") not in doc_types:
            continue
        for url in rec.get("pdf_urls") or []:
            if skip_existing and url in manifest:
                # A failed entry carries no local_path, and a file extracted
                # and then pruned no longer exists. Both should be fetched
                # again rather than skipped - or crash the run.
                local = manifest[url].get("local_path")
                if local and (PDF_DIR / local).exists():
                    continue
            todo.append((rec, url))
    if limit:
        todo = todo[:limit]

    log.info("downloading %d PDFs", len(todo))
    for i, (rec, url) in enumerate(todo, 1):
        blob = fetcher.get(url, binary=True, min_bytes=2000)
        if blob is None:
            manifest[url] = {
                "pdf_url": url,
                "node_key": rec["node_key"],
                "doc_type": rec.get("doc_type"),
                "status": "failed",
                "retrieved_at": now_iso(),
            }
            continue
        if not blob[:5].startswith(b"%PDF"):
            log.warning("not a PDF: %s", url)
            manifest[url] = {
                "pdf_url": url,
                "node_key": rec["node_key"],
                "doc_type": rec.get("doc_type"),
                "status": "not_pdf",
                "retrieved_at": now_iso(),
            }
            continue
        name = local_name(rec["node_key"], url)
        (PDF_DIR / name).write_bytes(blob)
        manifest[url] = {
            "pdf_url": url,
            "node_key": rec["node_key"],
            "doc_type": rec.get("doc_type"),
            "title": rec.get("title"),
            "issuer_hint": rec.get("issuer_hint"),
            "filing_date": rec.get("filing_date"),
            "local_path": name,
            "bytes": len(blob),
            "sha256": sha256_bytes(blob),
            "status": "ok",
            "retrieved_at": now_iso(),
        }
        if i % 20 == 0:
            write_jsonl(MANIFEST, list(manifest.values()))
            log.info("  %d/%d downloaded", i, len(todo))
    write_jsonl(MANIFEST, list(manifest.values()))
    ok = sum(1 for m in manifest.values() if m.get("status") == "ok")
    log.info("manifest: %d entries, %d retrieved", len(manifest), ok)
    return list(manifest.values())


def main() -> None:
    ap = argparse.ArgumentParser(description="Download CMF filing PDFs")
    ap.add_argument("--doc-types", nargs="*", default=["document_de_reference"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--all-types", action="store_true")
    args = ap.parse_args()

    records = read_jsonl(REGISTRY)
    if not records:
        raise SystemExit("registry is empty - run elitenet.cmf_crawl first")
    download(
        Fetcher(min_delay=args.delay, timeout=180),
        records,
        doc_types=None if args.all_types else args.doc_types,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
