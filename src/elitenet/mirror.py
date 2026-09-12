"""Stage 2 -- mirror the French OCR markdown for the scoped issues.

Extraction runs offline against this local mirror rather than against the
search API: the upstream index uses an FTS5 trigram tokenizer, so quoted
queries are not truly exact and a recall denominator cannot be computed from
them. A local mirror with committed checksums is also verifiable years later.

Two upstream behaviours verified on 2026-09-12 and handled explicitly here:

* ``ETag`` equals the MD5 of the response body, so integrity can be
  re-validated with one cheap HEAD per file and no re-download.
* A missing issue returns **HTTP 404 with a ~27 KB HTML body**. Success is
  therefore gated on status *and* ``content-type``; the 404 body must never be
  written as content.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .paths import MANIFEST, RAW, ensure_dirs, issue_md_path, load_config

MANIFEST_FIELDS = [
    "issue_uid", "collection", "language", "year", "issue",
    "md_url", "pdf_url", "viewer_url", "pdf_size_bytes",
    "http_status", "content_type", "bytes", "sha256", "etag_md5", "etag_matches_body",
    "n_pages", "arabic_char_frac", "script_lang", "status",
    "local_path", "fetched_at", "attempts", "error",
]

RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}
ARABIC_RANGES = ((0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF))


@dataclass
class Target:
    collection: str
    language: str
    year: int
    issue: str
    md_url: str
    pdf_url: str
    viewer_url: str
    pdf_size_bytes: int | None

    @property
    def uid(self) -> str:
        return f"{self.collection}/{self.language}/{self.year}/{self.issue}"


def arabic_fraction(text: str) -> float:
    """Share of letters that are Arabic script.

    Some issues are served as Arabic under the ``/fr/`` path, so the 'French'
    series is language-contaminated. Measuring this lets those issues be
    quarantined instead of silently producing garbage extractions.
    """
    letters = arabic = 0
    for ch in text:
        if ch.isalpha():
            letters += 1
            cp = ord(ch)
            if any(lo <= cp <= hi for lo, hi in ARABIC_RANGES):
                arabic += 1
    return (arabic / letters) if letters else 0.0


def load_targets(catalog: dict, scope: dict) -> list[Target]:
    lang = scope["language"]
    years = {int(y) for y in scope["window"]["years"]}
    wanted = set(scope["collections"])
    ep = scope["endpoints"]
    out: list[Target] = []
    for coll in catalog.get("collections", []):
        cid = coll.get("id")
        if cid not in wanted:
            continue
        for year, issues in (coll.get("years") or {}).items():
            if int(year) not in years:
                continue
            for issue, langs in issues.items():
                if lang not in langs:
                    continue
                fmt = dict(collection=cid, lang=lang, year=year, issue=issue)
                out.append(
                    Target(
                        collection=cid,
                        language=lang,
                        year=int(year),
                        issue=issue,
                        md_url=ep["ocr_pattern"].format(**fmt),
                        pdf_url=ep["pdf_pattern"].format(**fmt),
                        viewer_url=ep["viewer_pattern"].format(**fmt),
                        pdf_size_bytes=(langs[lang] or {}).get("size"),
                    )
                )
    out.sort(key=lambda t: (t.collection, t.year, t.issue))
    return out


def fetch_catalog(client: httpx.Client, scope: dict) -> dict:
    dest = RAW / "compliance" / f"catalog_{datetime.now(timezone.utc):%Y-%m-%d}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    resp = client.get(scope["endpoints"]["catalog"])
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    return json.loads(resp.content)


def _read_manifest() -> dict[str, dict]:
    if not MANIFEST.exists():
        return {}
    with MANIFEST.open(encoding="utf-8", newline="") as fh:
        return {r["issue_uid"]: r for r in csv.DictReader(fh)}


def fetch_one(client: httpx.Client, target: Target, http_cfg: dict, force: bool) -> dict:
    """Fetch one issue with backoff. Returns a manifest row."""
    path = issue_md_path(target.collection, target.language, target.year, target.issue)
    row = {
        "issue_uid": target.uid, "collection": target.collection,
        "language": target.language, "year": target.year, "issue": target.issue,
        "md_url": target.md_url, "pdf_url": target.pdf_url,
        "viewer_url": target.viewer_url, "pdf_size_bytes": target.pdf_size_bytes or "",
        "http_status": "", "content_type": "", "bytes": "", "sha256": "",
        "etag_md5": "", "etag_matches_body": "", "n_pages": "",
        "arabic_char_frac": "", "script_lang": "", "status": "error",
        "local_path": str(path.relative_to(RAW.parent.parent)), "fetched_at": "",
        "attempts": 0, "error": "",
    }

    if path.exists() and not force:
        text = path.read_text(encoding="utf-8", errors="replace")
        return _finalise(row, text, path, cached=True)

    last_err = ""
    for attempt in range(1, http_cfg["max_retries"] + 1):
        row["attempts"] = attempt
        try:
            resp = client.get(target.md_url)
        except Exception as exc:  # network-level failure
            last_err = f"{type(exc).__name__}: {exc}"
            _sleep(attempt, http_cfg)
            continue

        row["http_status"] = resp.status_code
        row["content_type"] = resp.headers.get("content-type", "")

        if resp.status_code == 404:
            # Verified: 404 ships a ~27 KB HTML body. Terminal, and never written.
            row["status"] = "missing"
            row["error"] = "404 (html body discarded)"
            row["fetched_at"] = _now()
            return row

        if resp.status_code in RETRY_STATUS:
            last_err = f"HTTP {resp.status_code}"
            retry_after = resp.headers.get("retry-after")
            _sleep(attempt, http_cfg, retry_after)
            continue

        if resp.status_code != 200:
            row["status"] = "error"
            row["error"] = f"HTTP {resp.status_code}"
            row["fetched_at"] = _now()
            return row

        # Gate on content type, not on size: the 404 page is large.
        ctype = row["content_type"].lower()
        if "html" in ctype:
            row["status"] = "error"
            row["error"] = f"unexpected content-type {ctype!r}"
            row["fetched_at"] = _now()
            return row

        body = resp.content
        etag = (resp.headers.get("etag") or "").strip('"')
        row["etag_md5"] = etag
        row["etag_matches_body"] = (
            etag.lower() == hashlib.md5(body).hexdigest() if etag else ""
        )

        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".md.part")
        tmp.write_bytes(body)
        tmp.replace(path)  # atomic
        return _finalise(row, body.decode("utf-8", errors="replace"), path)

    row["status"] = "error"
    row["error"] = last_err or "exhausted retries"
    row["fetched_at"] = _now()
    return row


def _finalise(row: dict, text: str, path: Path, cached: bool = False) -> dict:
    data = path.read_bytes()
    frac = arabic_fraction(text)
    row["bytes"] = len(data)
    row["sha256"] = hashlib.sha256(data).hexdigest()
    row["n_pages"] = text.count("<!-- page:")
    row["arabic_char_frac"] = round(frac, 4)
    row["script_lang"] = "ar" if frac > 0.5 else ("mixed" if frac > 0.2 else "fr")
    if not row["http_status"]:
        row["http_status"] = 200 if cached else row["http_status"]
    if len(data) == 0:
        row["status"] = "empty"
    elif frac > 0.2:
        # Arabic served under the /fr/ path: excluded from French extraction.
        row["status"] = "arabic"
    else:
        row["status"] = "ok"
    row["fetched_at"] = _now()
    return row


def _sleep(attempt: int, cfg: dict, retry_after: str | None = None) -> None:
    if retry_after:
        try:
            time.sleep(min(float(retry_after), 60.0))
            return
        except ValueError:
            pass
    base = cfg["backoff_base_seconds"] ** attempt
    time.sleep(min(base + random.uniform(0, base * 0.5), 60.0))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run(force: bool = False, limit: int | None = None) -> dict[str, int]:
    ensure_dirs()
    scope = load_config("scope")
    http_cfg = scope["http"]
    headers = {"User-Agent": http_cfg["user_agent"], "Accept-Encoding": "gzip"}
    limits = httpx.Limits(
        max_connections=http_cfg["concurrency"],
        max_keepalive_connections=http_cfg["concurrency"],
    )

    with httpx.Client(
        timeout=http_cfg["timeout_seconds"], headers=headers,
        limits=limits, follow_redirects=True,
    ) as client:
        catalog = fetch_catalog(client, scope)
        targets = load_targets(catalog, scope)
        if limit:
            targets = targets[:limit]
        print(f"targets in scope: {len(targets)}", flush=True)

        existing = _read_manifest()
        rows: list[dict] = []
        done = 0
        with ThreadPoolExecutor(max_workers=http_cfg["concurrency"]) as pool:
            futures = [pool.submit(fetch_one, client, t, http_cfg, force) for t in targets]
            for fut in futures:
                rows.append(fut.result())
                done += 1
                if done % 100 == 0:
                    print(f"  {done}/{len(targets)}", flush=True)

    merged = {**existing, **{r["issue_uid"]: r for r in rows}}
    ordered = sorted(merged.values(), key=lambda r: (
        r["collection"], int(r["year"]), str(r["issue"])))
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=MANIFEST_FIELDS)
        w.writeheader()
        for r in ordered:
            w.writerow({k: r.get(k, "") for k in MANIFEST_FIELDS})

    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Mirror French OCR markdown for scoped issues.")
    ap.add_argument("--force", action="store_true", help="re-download even if present")
    ap.add_argument("--limit", type=int, default=None, help="cap targets (smoke test)")
    args = ap.parse_args(argv)
    counts = run(force=args.force, limit=args.limit)
    print("status counts:", counts)
    total = sum(counts.values())
    ok = counts.get("ok", 0)
    print(f"usable French issues: {ok}/{total}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
