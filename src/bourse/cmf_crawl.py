"""Crawl CMF disclosure sections into a provenance-tracked document registry.

Two stages, deliberately separated so the expensive one is resumable:

1. ``crawl_listings`` walks each section's paginated view and records one row
   per filing (title, ISO date, node URL). Cheap: ~20 requests per section.
2. ``resolve_pdfs`` visits each node page to recover the attached PDF URL.
   One request per filing, so it is checkpointed after every section and skips
   anything already resolved.

The registry (``data/interim/cmf_registry.jsonl``) is the manifest the rest of
the pipeline reads. It stores URLs and hashes rather than the PDFs themselves,
so the corpus is reproducible without redistributing CMF documents.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml
from bs4 import BeautifulSoup

from .common import PROCESSED, Fetcher, log, now_iso, read_jsonl, write_jsonl

CONFIG = Path(__file__).resolve().parents[2] / "config" / "bourse_sources.yaml"
REGISTRY = PROCESSED / "corpus" / "cmf_registry.jsonl.gz"

# Filings are keyed by their node path, which is stable across crawls.
_QPATH = re.compile(r"[?&]q=([^&\"#]+)")


def load_config() -> dict:
    with CONFIG.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _node_key(href: str) -> str | None:
    m = _QPATH.search(href)
    if not m:
        return None
    key = m.group(1)
    # Skip navigation targets and the section's own self-link.
    if key in {"node", ""} or key.startswith("admin"):
        return None
    return key


def _row_issuer_hint(row) -> str | None:
    """Read the issuer name some listings expose as a dedicated field.

    Sections such as 'convocation des assemblees' and 'rapports annuels' carry a
    generic title ("Rapport Annuel") and name the company in a separate Drupal
    field instead. That field is the only issuer signal those rows provide.
    """
    for div in row.select("div[class*='field-name-field-']"):
        classes = " ".join(div.get("class") or [])
        if "datestamp" in classes or "date" in classes:
            continue
        item = div.select_one("div.field-item")
        if not item:
            continue
        txt = item.get_text(" ", strip=True)
        if txt and len(txt) < 120:
            return txt
    return None


def parse_listing(html: str, base_url: str) -> list[dict]:
    """Pull one row per filing out of a Drupal views listing page.

    Two row layouts appear across CMF sections: one links the filing from the
    title, the other carries the node path only in the wrapper's ``about``
    attribute and leaves the title unlinked. Both are handled here.
    """
    soup = BeautifulSoup(html, "lxml")
    rows = []
    for row in soup.select("div.views-row"):
        key = None
        for a in row.find_all("a", href=True):
            key = _node_key(a["href"])
            if key:
                break
        if key is None:
            node = row.select_one("div[about]")
            if node:
                key = _node_key(node["about"])
        if key is None:
            continue

        title_el = row.select_one("div.field-name-title") or row.find(["h2", "h3"])
        title = title_el.get_text(" ", strip=True) if title_el else ""
        date_span = row.find("span", class_="date-display-single")
        iso = (date_span.get("content") or "")[:10] if date_span else ""
        rows.append(
            {
                "node_key": key,
                "title": title,
                "issuer_hint": _row_issuer_hint(row),
                "filing_date": iso,
                "filing_date_text": date_span.get_text(strip=True) if date_span else "",
                "node_url": f"{base_url}/?q={key}",
            }
        )
    return rows


def crawl_listings(
    fetcher: Fetcher, cfg: dict, sections: list[str] | None, max_pages: int
) -> list[dict]:
    base = cfg["base_url"].rstrip("/")
    out: list[dict] = []
    for sec in cfg["sections"]:
        if sections and sec["key"] not in sections:
            continue
        seen: set[str] = set()
        empty_streak = 0
        for page in range(max_pages):
            url = f"{base}/?q={sec['slug']}&page={page}"
            html = fetcher.get(url)
            if html is None:
                empty_streak += 1
                if empty_streak >= 2:
                    break
                continue
            rows = parse_listing(html, base)
            fresh = [r for r in rows if r["node_key"] not in seen]
            for r in fresh:
                seen.add(r["node_key"])
                r.update(
                    section=sec["key"],
                    doc_type=sec["doc_type"],
                    priority=sec.get("priority", 2),
                    listing_url=url,
                    listed_at=now_iso(),
                )
            out.extend(fresh)
            # Views pages repeat the last page's rows once exhausted, so an
            # all-duplicate page means we've reached the end.
            if not fresh:
                empty_streak += 1
                if empty_streak >= 2:
                    break
            else:
                empty_streak = 0
        log.info("section %-24s %4d filings", sec["key"], len(seen))
    return out


def parse_node_for_pdf(html: str, base_url: str) -> list[str]:
    """Return PDF URLs attached to a filing node, excluding site-wide boilerplate."""
    soup = BeautifulSoup(html, "lxml")
    urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if ".pdf" not in href.lower():
            continue
        if href.startswith("/"):
            href = base_url + href
        # The "Liste APE" roster PDF is linked from every page's sidebar.
        if "Liste APE" in href or "/acteurs/" in href:
            continue
        if href not in urls:
            urls.append(href)
    return urls


def resolve_pdfs(fetcher: Fetcher, cfg: dict, records: list[dict], limit: int | None) -> None:
    base = cfg["base_url"].rstrip("/")
    todo = [r for r in records if "pdf_urls" not in r]
    todo.sort(key=lambda r: (r.get("priority", 2), r.get("filing_date", ""), ), reverse=False)
    todo = [r for r in todo if r.get("priority", 2) == 1] + [
        r for r in todo if r.get("priority", 2) != 1
    ]
    if limit:
        todo = todo[:limit]
    log.info("resolving PDF links for %d filings", len(todo))
    for i, rec in enumerate(todo, 1):
        html = fetcher.get(rec["node_url"])
        rec["pdf_urls"] = parse_node_for_pdf(html, base) if html else []
        rec["resolved_at"] = now_iso()
        if i % 50 == 0:
            write_jsonl(REGISTRY, records)
            log.info("  resolved %d/%d (checkpoint)", i, len(todo))
    write_jsonl(REGISTRY, records)


def main() -> None:
    ap = argparse.ArgumentParser(description="Crawl CMF filings into a document registry")
    ap.add_argument("--sections", nargs="*", help="section keys (default: all)")
    ap.add_argument("--max-pages", type=int, default=60)
    ap.add_argument("--resolve", type=int, nargs="?", const=0, default=None,
                    help="resolve PDF links; optional cap on filings to resolve")
    ap.add_argument("--delay", type=float, default=1.2)
    args = ap.parse_args()

    cfg = load_config()
    fetcher = Fetcher(min_delay=args.delay)
    existing = {r["node_key"]: r for r in read_jsonl(REGISTRY)}

    if args.resolve is None or not existing:
        found = crawl_listings(fetcher, cfg, args.sections, args.max_pages)
        for r in found:
            if r["node_key"] in existing:
                existing[r["node_key"]].update(
                    {k: v for k, v in r.items() if k not in ("pdf_urls", "resolved_at")}
                )
            else:
                existing[r["node_key"]] = r
        write_jsonl(REGISTRY, list(existing.values()))
        log.info("registry now holds %d filings", len(existing))

    if args.resolve is not None:
        records = list(existing.values())
        resolve_pdfs(fetcher, cfg, records, args.resolve or None)
        with_pdf = sum(1 for r in records if r.get("pdf_urls"))
        log.info("registry: %d filings, %d with a PDF attached", len(records), with_pdf)


if __name__ == "__main__":
    main()
