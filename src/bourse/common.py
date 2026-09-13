"""Shared plumbing: paths, polite HTTP, provenance helpers.

Every fact in this dataset must be traceable to a retrieved document. The
helpers here enforce that by recording, for each fetch, the URL, the retrieval
timestamp and the sha256 of the bytes we actually saw.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import logging
import os
import random
import time
from pathlib import Path
from typing import Any, Iterable

import requests

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
# This component lives beside the JORT state-elite build, so every path is
# namespaced under `bourse/` and nothing is shared but the `data/` root.
RAW = DATA / "raw" / "bourse"
INTERIM = DATA / "interim" / "bourse"
PROCESSED = DATA / "processed" / "bourse"
PDF_DIR = RAW / "cmf_pdfs"
TEXT_DIR = INTERIM / "pdftext"

for _d in (RAW, INTERIM, PROCESSED, PDF_DIR, TEXT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

def open_text(path: Path, mode: str = "r"):
    """Open a text file, transparently gzipping when the name ends in .gz.

    Large derived tables are committed gzipped, following the convention the
    JORT build already uses in this repository.

    Writes set the gzip header mtime to 0. A gzip stream otherwise records the
    time it was written, so rebuilding unchanged data would produce different
    bytes and show up as a spurious diff on every run. With the timestamp
    pinned, the same inputs give a byte-identical file - the same guarantee the
    entity ids already make.
    """
    if str(path).endswith(".gz"):
        if "w" in mode or "a" in mode:
            raw = gzip.GzipFile(filename=path, mode=mode + "b", mtime=0)
            return io.TextIOWrapper(raw, encoding="utf-8", newline="")
        return gzip.open(path, mode + "t", encoding="utf-8", newline="")
    return path.open(mode, encoding="utf-8", newline="")


USER_AGENT = (
    "EliteNetworksTN/0.1 (academic research; contact via repository) "
    "python-requests"
)

log = logging.getLogger("bourse")
if not log.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


class Fetcher:
    """Rate-limited session with retries.

    The CMF server drops connections when hit too fast, so every call sleeps a
    randomised minimum interval and retries with exponential backoff.
    """

    def __init__(self, min_delay: float = 1.2, tries: int = 4, timeout: int = 60):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": USER_AGENT})
        self.min_delay = min_delay
        self.tries = tries
        self.timeout = timeout
        self._last = 0.0

    def _wait(self) -> None:
        gap = time.time() - self._last
        need = self.min_delay + random.uniform(0, 0.4) - gap
        if need > 0:
            time.sleep(need)
        self._last = time.time()

    def get(self, url: str, *, binary: bool = False, min_bytes: int = 400):
        """Return text (or bytes) for ``url``, or None if it never succeeded."""
        for attempt in range(self.tries):
            self._wait()
            try:
                r = self.s.get(url, timeout=self.timeout)
                if r.status_code == 200 and len(r.content) >= min_bytes:
                    return r.content if binary else r.text
                log.debug("fetch %s -> HTTP %s (%d bytes)", url, r.status_code, len(r.content))
            except requests.RequestException as exc:
                log.debug("fetch %s -> %s", url, type(exc).__name__)
            time.sleep(2 ** attempt)
        log.warning("giving up on %s", url)
        return None


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    """Replace ``path`` with ``rows``, atomically.

    Written to a temporary file in the same directory and renamed over the
    target, so a reader either sees the whole previous file or the whole new
    one. That is what lets downloading and extraction run at the same time:
    the fetcher rewrites the manifest every few files while the extractor is
    reading it, and an in-place write would hand the reader a truncated file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # The temporary name has to keep the ".gz" suffix: open_text decides
    # whether to compress from the file name, so a temp file called
    # "...jsonl.gz.1234.tmp" would be written as plain text and then renamed
    # over a path everything else opens with gzip.
    suffix = ".gz" if str(path).endswith(".gz") else ""
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp{suffix}")
    n = 0
    try:
        with open_text(tmp, "w") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                n += 1
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
    return n


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with open_text(path) as fh:
        return [json.loads(line) for line in fh if line.strip()]
