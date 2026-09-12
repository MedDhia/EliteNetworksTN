"""Run the extractor across the cached corpus and write the raw event table."""

from __future__ import annotations

import csv
import gzip
import logging
from concurrent.futures import ProcessPoolExecutor
from dataclasses import fields
from pathlib import Path

from .extract import Event, events_from_issue
from .harvest import Issue, load_catalog

LOG = logging.getLogger(__name__)

EVENT_COLUMNS = [f.name for f in fields(Event)]


def _one(args) -> tuple[str, list[dict], str]:
    issue_dict, cache_root = args
    issue = Issue(**issue_dict)
    path = issue.cache_path(Path(cache_root))
    if not path.exists():
        return issue.key, [], "missing"
    try:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            raw = fh.read()
    except Exception as exc:  # noqa: BLE001
        return issue.key, [], f"unreadable: {exc}"
    try:
        events = events_from_issue(
            raw,
            issue_key=issue.key,
            year=issue.year,
            issue=issue.issue,
            pdf_url=issue.pdf_url,
        )
    except Exception as exc:  # noqa: BLE001
        return issue.key, [], f"error: {exc}"
    return issue.key, [e.as_row() for e in events], "ok" if events else "empty"


def run(catalog_path: Path, cache_root: Path, out_path: Path,
        workers: int = 8, chunksize: int = 16) -> dict:
    issues = load_catalog(catalog_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    stats = {"issues": len(issues), "ok": 0, "empty": 0, "missing": 0,
             "error": 0, "events": 0}

    payload = [({"collection": i.collection, "lang": i.lang, "year": i.year,
                 "issue": i.issue}, str(cache_root)) for i in issues]

    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=EVENT_COLUMNS)
        writer.writeheader()
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for n, (key, rows, status) in enumerate(
                pool.map(_one, payload, chunksize=chunksize), 1
            ):
                if status.startswith("error") or status.startswith("unreadable"):
                    stats["error"] += 1
                    LOG.warning("%s: %s", key, status)
                elif status == "missing":
                    stats["missing"] += 1
                else:
                    stats[status] += 1
                for row in rows:
                    writer.writerow(row)
                stats["events"] += len(rows)
                if n % 500 == 0:
                    LOG.info("%s/%s issues, %s events", n, len(issues), stats["events"])
    return stats
