"""Check extracted records against the page of the filing they cite.

The rest of the validation suite checks the dataset against itself: totals that
should not exceed 100%, endpoints that should resolve, layers that should span
plausible years. None of it can catch a number that was read off the wrong row,
because a misread number is still internally consistent.

This module closes that gap. For a sample of filings it fetches the source PDF,
verifies its sha256 against the corpus manifest, and then asks of every record
drawn from that document: does the name actually appear on the page cited, and
does the figure appear there too? A record that passes both was read off the
page it claims. A record that fails is either a misattribution or a page-offset
bug, and the report names it so it can be looked at.

Run with::

    make bourse-verify                                  # every filing
    PYTHONPATH=src python -m bourse.verify_source --sample 12

A full pass is the default, and cheap: only the pages records actually cite are
rendered, not the several hundred pages of financial statements in each filing.
``--sample`` audits a subset drawn deterministically from a seed, for when the
corpus is not on disk and each filing has to be fetched.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import multiprocessing as mp
import random
import re
import unicodedata
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOURSE = ROOT / "data" / "processed" / "bourse"
MANIFEST = BOURSE / "corpus" / "pdf_manifest.jsonl.gz"
RECORDS = BOURSE / "records"
# The corpus directory the extraction itself reads from; re-using it means a
# verification run after a full build downloads nothing.
CACHE = ROOT / "data" / "raw" / "bourse" / "cmf_pdfs"

LOG = logging.getLogger("verify")

# Record kinds that cite a page and carry a name plus a figure.
CHECKED = {
    "blockholders": ("holder_name_raw", "pct_capital", "n_shares"),
    "board": ("member_name_raw", None, None),
    "director_holdings": ("holder_name_raw", "pct_capital", "n_shares"),
    "subsidiaries": ("subsidiary_name_raw", "pct_capital", None),
    "interlocks": ("person_name_raw", None, None),
    "executives": ("person_name_raw", None, None),
}


def fold(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def name_on_page(name: str, page_text: str) -> bool:
    """True when the page carries enough of the name to have produced it.

    Exact string equality is the wrong test: the extractor joins cells and
    normalises whitespace, and PDF text extraction reorders glyph runs. What
    must hold is that the page contains the name's substantive tokens.
    """
    toks = [t for t in fold(name).split() if len(t) > 2]
    if not toks:
        return True  # nothing to check against
    hay = fold(page_text)
    hits = sum(1 for t in toks if t in hay)
    return hits >= max(1, (len(toks) + 1) // 2)


def number_on_page(value, page_text: str) -> bool:
    """True when the figure appears on the page in any of its printed forms.

    Two haystacks, because the corpus groups thousands both ways. Decimals are
    checked against text with spaces removed and the French comma turned into a
    point, which leaves "9.099.994.900" intact and so could never match an
    integer written that way; integers of four digits or more are therefore
    checked against a digits-only reduction of the page, where every grouping
    convention collapses to the same string. Shorter integers stay on the
    decimal haystack: "10" occurs somewhere on almost any page, and finding it
    among stripped digits would confirm nothing.
    """
    if value is None or value == "":
        return True
    try:
        v = float(value)
    except (TypeError, ValueError):
        return True
    hay_dec = re.sub(r"[\s\u00a0']", "", page_text).replace(",", ".")
    hay_int = re.sub(r"\D", "", page_text)

    if abs(v - round(v)) < 1e-9:
        digits = str(abs(int(round(v))))
        return digits in (hay_int if len(digits) >= 4 else hay_dec)

    cands = set()
    for dp in range(1, 13):
        c = f"{v:.{dp}f}".rstrip("0").rstrip(".")
        # A rounding that has swallowed every significant digit ("0.00000" for
        # 7.143e-07) would match the "0" printed in any other cell of the table.
        if c and any(ch in "123456789" for ch in c):
            cands.add(c)
    return any(c in hay_dec for c in cands)


def load_manifest() -> dict[str, dict]:
    out = {}
    with gzip.open(MANIFEST, "rt", encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if row.get("sha256"):
                out[row["sha256"]] = row
    return out


def load_records() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for kind in CHECKED:
        path = RECORDS / f"{kind}.jsonl.gz"
        if not path.exists():
            continue
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            out[kind] = [json.loads(line) for line in fh]
    return out


def fetch(url: str, sha: str, local_path: str | None = None) -> Path | None:
    """Return the filing's PDF, downloading it only if the corpus lacks it.

    Whether the bytes came from disk or from the CMF, they are accepted only
    against the digest the manifest recorded when the corpus was built. A file
    that no longer hashes to it is not the document the records were read from,
    so it is refused rather than checked against.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    if local_path:
        have = CACHE / local_path
        if have.exists() and hashlib.sha256(have.read_bytes()).hexdigest() == sha:
            return have
    dest = CACHE / f"{sha[:16]}.pdf"
    if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest() == sha:
        return dest
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=180).read()
    except Exception as exc:  # noqa: BLE001
        LOG.warning("fetch failed %s: %s", url[-60:], exc)
        return None
    got = hashlib.sha256(data).hexdigest()
    if got != sha:
        LOG.warning("sha mismatch for %s: manifest %s, fetched %s", url[-60:], sha[:12], got[:12])
        return None
    dest.write_bytes(data)
    return dest


def page_texts(pdf_path: Path, wanted: set[int]) -> dict[int, str]:
    import pdfplumber

    out: dict[int, str] = {}
    with pdfplumber.open(pdf_path) as pdf:
        n = len(pdf.pages)
        for p in sorted(wanted):
            # Records cite 1-based page numbers.
            if 1 <= p <= n:
                out[p] = pdf.pages[p - 1].extract_text() or ""
    return out


def _check_doc(args: tuple) -> tuple[dict, list[dict], int, int]:
    """Verify every record drawn from one filing. Runs in a worker process."""
    meta, rows = args
    sha = meta["sha256"]
    stats: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    path = fetch(meta["pdf_url"], sha, meta.get("local_path"))
    if path is None:
        return stats, [], 0, 1
    pages = {int(r["page"]) for _, r in rows if str(r.get("page", "")).isdigit()}
    try:
        texts = page_texts(path, pages)
    except Exception as exc:  # noqa: BLE001
        LOG.warning("unreadable %s: %s", path.name, exc)
        return stats, [], 0, 1

    failures: list[dict] = []
    for kind, r in rows:
        name_field, pct_field, share_field = CHECKED[kind]
        page = int(r["page"]) if str(r.get("page", "")).isdigit() else None
        text = texts.get(page, "")
        if not text:
            # A page with no extractable text is a scan; the record came from
            # the table layer, so there is nothing here to check it against.
            stats[kind]["no_text"] += 1
            continue
        stats[kind]["checked"] += 1
        ok_name = name_on_page(r.get(name_field, ""), text)
        ok_num = True
        if pct_field:
            ok_num &= number_on_page(r.get(pct_field), text)
        if share_field:
            ok_num &= number_on_page(r.get(share_field), text)
        if ok_name:
            stats[kind]["name_ok"] += 1
        if ok_num:
            stats[kind]["number_ok"] += 1
        if ok_name and ok_num:
            stats[kind]["ok"] += 1
        else:
            failures.append({
                "kind": kind, "page": page,
                "name": str(r.get(name_field, ""))[:60],
                "pct": r.get(pct_field) if pct_field else None,
                "name_ok": ok_name, "number_ok": ok_num,
                "doc": (meta.get("title") or "")[:60],
            })
    return stats, failures, 1, 0


def verify(sample: int | None, seed: int, workers: int = 1) -> dict:
    manifest = load_manifest()
    records = load_records()

    by_sha: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for kind, rows in records.items():
        for r in rows:
            sha = r.get("doc_sha256")
            if sha and r.get("page"):
                by_sha[sha].append((kind, r))

    shas = sorted(s for s in by_sha if s in manifest)
    if sample:
        random.Random(seed).shuffle(shas)
        shas = shas[:sample]
        shas.sort()

    jobs = [(manifest[s], by_sha[s]) for s in shas]
    LOG.info("verifying %d records from %d filings", sum(len(j[1]) for j in jobs), len(jobs))

    if workers > 1:
        with mp.Pool(workers) as pool:
            results = pool.map(_check_doc, jobs, chunksize=1)
    else:
        results = [_check_doc(j) for j in jobs]

    stats: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    failures: list[dict] = []
    docs_ok = docs_failed = 0
    for st, fl, ok, bad in results:
        for kind, counts in st.items():
            for k, v in counts.items():
                stats[kind][k] += v
        failures.extend(fl)
        docs_ok += ok
        docs_failed += bad

    failures.sort(key=lambda f: (f["doc"], f["page"] or 0, f["kind"], f["name"]))
    return {"docs_ok": docs_ok, "docs_failed": docs_failed,
            "sampled": len(shas), "stats": stats, "failures": failures}


def report(res: dict) -> str:
    lines = ["# Source verification", "",
             "Every record drawn from a sampled filing, checked against the page",
             "of the PDF it cites: does the name appear there, and does the figure?",
             "",
             f"Filings checked: **{res['sampled']}** "
             f"(opened and sha256-verified against the corpus manifest: "
             f"{res['docs_ok']}, unavailable: {res['docs_failed']})",
             "",
             "| Record kind | Checked | Name on page | Figure on page | Both |",
             "|---|---:|---:|---:|---:|"]
    tot = defaultdict(int)
    for kind in sorted(res["stats"]):
        s = res["stats"][kind]
        c = s["checked"] or 1
        for k in ("checked", "name_ok", "number_ok", "ok"):
            tot[k] += s[k]
        lines.append(
            f"| `{kind}` | {s['checked']} | {s['name_ok']} ({s['name_ok']/c:.1%}) | "
            f"{s['number_ok']} ({s['number_ok']/c:.1%}) | {s['ok']} ({s['ok']/c:.1%}) |")
    c = tot["checked"] or 1
    lines.append(f"| **all** | **{tot['checked']}** | **{tot['name_ok']/c:.1%}** | "
                 f"**{tot['number_ok']/c:.1%}** | **{tot['ok']/c:.1%}** |")

    if res["failures"]:
        lines += ["", f"## Records not confirmed on the cited page ({len(res['failures'])})", ""]
        for f in res["failures"][:40]:
            why = []
            if not f["name_ok"]:
                why.append("name absent")
            if not f["number_ok"]:
                why.append("figure absent")
            lines.append(f"- `{f['kind']}` p.{f['page']} — {f['name']!r} "
                         f"({', '.join(why)}) — {f['doc']}")
        if len(res["failures"]) > 40:
            lines.append(f"- … and {len(res['failures']) - 40} more")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", type=int, default=0,
                    help="filings to audit; 0 (the default) audits every one")
    ap.add_argument("--seed", type=int, default=20260912)
    ap.add_argument("--workers", type=int, default=max(1, (mp.cpu_count() or 2) - 1))
    ap.add_argument("--out", type=Path,
                    default=BOURSE / "source_verification.md")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")

    res = verify(args.sample or None, args.seed, args.workers)
    text = report(res)
    args.out.write_text(text, encoding="utf-8")
    print(text)
    LOG.info("wrote %s", args.out)


if __name__ == "__main__":
    main()
