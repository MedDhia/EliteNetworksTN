"""Harvest the JORT (Journal Officiel de la Republique Tunisienne) OCR corpus.

Source: https://jort.tn — an independent mirror of the Imprimerie Officielle
archive.  See https://docs.jort.tn for the API contract used here:

    index      GET https://index.jort.tn/issues?collection=..&lang=..&year=..
    OCR text   GET https://ocr.jort.tn/{collection}/{lang}/{year}/{issue}.md

Only French issues are OCR'd upstream, so the French edition of the
``journal-officiel`` collection (1957-2026) is the working corpus.  Issues are
cached gzipped on disk so the whole pipeline can be re-run offline.
"""

from __future__ import annotations

import gzip
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from pathlib import Path

import requests

LOG = logging.getLogger(__name__)

INDEX_BASE = "https://index.jort.tn"
OCR_BASE = "https://ocr.jort.tn"
LAKE_BASE = "https://lake.jort.tn"

USER_AGENT = "EliteNetworksTN/0.1 (academic research; longitudinal elite dataset)"


@dataclass(frozen=True)
class Issue:
    """One numbered gazette issue."""

    collection: str
    lang: str
    year: int
    issue: str  # zero-padded 3-digit string, e.g. "007"

    @property
    def key(self) -> str:
        return f"{self.collection}/{self.lang}/{self.year}/{self.issue}"

    @property
    def md_url(self) -> str:
        return f"{OCR_BASE}/{self.key}.md"

    @property
    def pdf_url(self) -> str:
        return f"{LAKE_BASE}/{self.key}.pdf"

    def cache_path(self, root: Path) -> Path:
        return root / self.collection / self.lang / str(self.year) / f"{self.issue}.md.gz"


def _session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


def _get(session: requests.Session, url: str, *, tries: int = 5, timeout: int = 60):
    """GET with exponential backoff.  Returns the response or raises."""
    delay = 2.0
    last: Exception | None = None
    for attempt in range(tries):
        try:
            r = session.get(url, timeout=timeout)
            if r.status_code == 404:
                return r  # a genuine gap in the archive, not a transport error
            r.raise_for_status()
            return r
        except Exception as exc:  # noqa: BLE001 - network layer, retry everything
            last = exc
            if attempt == tries - 1:
                break
            time.sleep(delay)
            delay *= 2
    raise RuntimeError(f"GET failed after {tries} tries: {url}") from last


def list_issues(collection: str, lang: str, year: int, session=None) -> list[Issue]:
    """Ask the upstream index which issue numbers actually exist for a year."""
    session = session or _session()
    url = f"{INDEX_BASE}/issues?collection={collection}&lang={lang}&year={year}"
    r = _get(session, url)
    if r.status_code == 404:
        return []
    payload = r.json()
    return [
        Issue(collection, lang, year, entry["issue"])
        for entry in payload.get("issues", [])
    ]


def build_catalog(
    collection: str = "journal-officiel",
    lang: str = "fr",
    year_from: int = 1957,
    year_to: int = 2026,
    workers: int = 8,
) -> list[Issue]:
    """Enumerate every available issue in a year range."""
    session = _session()
    issues: list[Issue] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(list_issues, collection, lang, y, session): y
            for y in range(year_from, year_to + 1)
        }
        for fut in as_completed(futures):
            year = futures[fut]
            try:
                found = fut.result()
            except Exception as exc:  # noqa: BLE001
                LOG.warning("catalog: year %s failed: %s", year, exc)
                continue
            issues.extend(found)
    issues.sort(key=lambda i: (i.year, i.issue))
    return issues


def fetch_issue(issue: Issue, cache_root: Path, session=None, force: bool = False) -> str | None:
    """Return the OCR markdown for an issue, downloading it if not cached.

    ``None`` means the archive has no OCR text for this issue (a real gap:
    upstream has only OCR'd the French edition, and a handful of early
    "French" numbers are in fact Arabic-only scans).
    """
    path = issue.cache_path(cache_root)
    if path.exists() and not force:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return fh.read()

    session = session or _session()
    r = _get(session, issue.md_url)
    if r.status_code == 404:
        return None
    text = r.content.decode("utf-8", errors="replace")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
        fh.write(text)
    tmp.replace(path)
    return text


def download_corpus(
    issues: list[Issue],
    cache_root: Path,
    workers: int = 12,
    progress_every: int = 250,
) -> dict:
    """Download (or confirm cached) every issue.  Returns a small report."""
    cache_root.mkdir(parents=True, exist_ok=True)
    stats = {"ok": 0, "missing": 0, "error": 0, "bytes": 0}

    def one(issue: Issue) -> tuple[Issue, str | None, Exception | None]:
        try:
            return issue, fetch_issue(issue, cache_root, _session()), None
        except Exception as exc:  # noqa: BLE001
            return issue, None, exc

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for issue, text, exc in pool.map(one, issues):
            done += 1
            if exc is not None:
                stats["error"] += 1
                LOG.warning("fetch %s: %s", issue.key, exc)
            elif text is None:
                stats["missing"] += 1
            else:
                stats["ok"] += 1
                stats["bytes"] += len(text)
            if progress_every and done % progress_every == 0:
                LOG.info("fetched %s/%s (%s)", done, len(issues), stats)
    return stats


def save_catalog(issues: list[Issue], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump([asdict(i) for i in issues], fh, indent=1)


def load_catalog(path: Path) -> list[Issue]:
    with path.open(encoding="utf-8") as fh:
        return [Issue(**row) for row in json.load(fh)]
