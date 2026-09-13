"""Stage 1: fetch the scanned volume and OCR it page by page.

The book has no text layer at all -- every page is a full-page CCITT bilevel
scan -- so OCR is the only route to text, and its settings are part of the
dataset's provenance rather than an implementation detail. The manifest
records the engine, its version and the exact flags alongside a sha256 of both
the page image and the resulting text, so a change in any of them shows up as
a diff instead of silently altering thousands of rows downstream.

The PDF itself is not redistributed. ``--fetch`` pulls it from the Internet
Archive and refuses to proceed if the bytes do not match the pinned digest.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from .paths import MANIFEST, PAGES, PDF, ensure_dirs, load_config

MANIFEST_FIELDS = [
    "page_uid", "pdf_page", "folio", "image_sha256", "text_sha256",
    "n_chars", "arabic_char_frac", "ocr_engine", "ocr_version", "ocr_config",
    "status", "needs_review",
]

# Arabic block, Arabic Supplement and Arabic Extended-A. Used to tell a page of
# Arabic prose from a blank, a plate, or a page the engine failed on.
_ARABIC = re.compile(r"[؀-ۿݐ-ݿࢠ-ࣿ]")
_WS = re.compile(r"\s+")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def arabic_fraction(text: str) -> float:
    """Share of non-space characters that are Arabic script."""
    dense = _WS.sub("", text)
    if not dense:
        return 0.0
    return len(_ARABIC.findall(dense)) / len(dense)


def tesseract_version() -> str:
    out = subprocess.run(
        ["tesseract", "--version"], capture_output=True, text=True, check=True
    ).stdout
    return out.splitlines()[0].strip()


def fetch_pdf(dest: Path = PDF, force: bool = False) -> dict:
    """Download the scan and verify it against the pinned digest."""
    cfg = load_config("aalam_scope")["source"]
    expected = cfg["pdf_sha256"]
    if dest.exists() and not force:
        got = sha256_bytes(dest.read_bytes())
        if got == expected:
            return {"fetched": 0, "cached": 1}
        raise SystemExit(
            f"{dest} exists but its sha256 is {got}, not the pinned {expected}. "
            "Delete it and re-run with --fetch to replace it."
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(cfg["pdf_url"], timeout=300) as resp:
        data = resp.read()
    got = sha256_bytes(data)
    if got != expected:
        raise SystemExit(
            f"Downloaded bytes hash to {got}, not the pinned {expected}. "
            "The upstream file has changed; do not proceed on a different scan."
        )
    dest.write_bytes(data)
    return {"fetched": 1, "cached": 0}


def _ocr_one(args: tuple[int, str, str, int, int]) -> dict:
    """OCR a single page. Runs in a worker process, so it takes plain data.

    The embedded scan is used at its native resolution rather than re-rendered.
    Each page is a single full-page image of 2144x3024 pixels, which for a page
    this size is already around 350 dpi; the page box is measured in points, so
    asking PyMuPDF for 300 dpi would upscale it more than fourfold. That is not
    merely wasteful, it is worse: measured against pages transcribed by eye, the
    upscaled render loses words the native image reads correctly (fawa'id as
    fawa'il, yahduhu as yahduru, imaan as ibmaan) and is about ten times slower.

    Provenance hashes the raw embedded stream, not the decoded image, so the
    digest is a property of the PDF rather than of the decoder's version.
    """
    pdf_page, pdf_path, lang, psm, timeout = args
    import pymupdf  # imported in the worker; not needed by the parent

    doc = pymupdf.open(pdf_path)
    page = doc[pdf_page - 1]
    images = page.get_images(full=True)
    if not images:
        doc.close()
        return {
            "pdf_page": pdf_page, "image_sha256": "", "text": "",
            "text_sha256": sha256_bytes(b""), "n_chars": 0,
            "arabic_char_frac": 0.0, "status": "no_image",
        }
    xref = images[0][0]
    raw = doc.xref_stream_raw(xref)
    png = doc.extract_image(xref)["image"]
    doc.close()

    # A page takes well under a second at native resolution. A handful in this
    # volume instead send the layout analyser into a spin that does not
    # terminate -- left alone, one of them consumed twenty minutes of CPU and
    # stalled the whole run. Cap it, record the page as timed out, and keep
    # going: losing one page to review is better than losing the build.
    try:
        proc = subprocess.run(
            ["tesseract", "stdin", "stdout", "-l", lang, "--psm", str(psm)],
            input=png, capture_output=True, check=False, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "pdf_page": pdf_page, "image_sha256": sha256_bytes(raw), "text": "",
            "text_sha256": sha256_bytes(b""), "n_chars": 0,
            "arabic_char_frac": 0.0, "status": "ocr_timeout",
        }
    text = proc.stdout.decode("utf-8", errors="replace") if proc.returncode == 0 else ""
    status = "ok" if proc.returncode == 0 else "ocr_error"

    frac = arabic_fraction(text)
    if status == "ok" and not text.strip():
        status = "empty"
    return {
        "pdf_page": pdf_page,
        "image_sha256": sha256_bytes(raw),
        "text": text,
        "text_sha256": sha256_bytes(text.encode("utf-8")),
        "n_chars": len(text),
        "arabic_char_frac": round(frac, 4),
        "status": status,
    }


def run(limit: int | None = None, progress: bool = False,
        page_timeout: int = 60) -> dict[str, int]:
    ensure_dirs()
    cfg = load_config("aalam_scope")
    vol, ocr = cfg["volume"], cfg["ocr"]
    if shutil.which("tesseract") is None:
        raise SystemExit("tesseract is not installed; `apt-get install tesseract-ocr tesseract-ocr-ara`")
    if not PDF.exists():
        raise SystemExit(f"{PDF} is missing. Run `python -m aalam.ingest --fetch` first.")

    version = tesseract_version()
    config_str = f"--psm {ocr['psm']} -l {ocr['lang']} native-resolution"
    n_pages = vol["n_pdf_pages"] if limit is None else min(limit, vol["n_pdf_pages"])
    offset = vol["folio_offset"]

    # Sequential on purpose. A page takes under a second at native
    # resolution, so the whole volume is a few minutes, and a worker pool buys
    # little while costing determinism in output ordering and a real risk of
    # stalling when the run is detached from a terminal.
    results = []
    for p in range(1, n_pages + 1):
        results.append(_ocr_one((p, str(PDF), ocr["lang"], ocr["psm"], page_timeout)))
        if progress and p % 25 == 0:
            print(f"  ... {p}/{n_pages} pages", flush=True)

    rows, stats = [], {"pages": 0, "ok": 0, "empty": 0, "ocr_error": 0}
    for r in sorted(results, key=lambda r: r["pdf_page"]):
        p = r["pdf_page"]
        path = PAGES / f"p{p:03d}.txt"
        path.write_text(r["text"], encoding="utf-8")
        folio = p - offset
        rows.append({
            "page_uid": f"aalam:p{p:03d}",
            "pdf_page": p,
            "folio": folio if folio > 0 else "",
            "image_sha256": r["image_sha256"],
            "text_sha256": r["text_sha256"],
            "n_chars": r["n_chars"],
            "arabic_char_frac": r["arabic_char_frac"],
            "ocr_engine": ocr["engine"],
            "ocr_version": version,
            "ocr_config": config_str,
            "status": r["status"],
            # Body pages are dense Arabic prose. A low share means a plate, a
            # near-blank page, or an engine failure -- all worth a human look
            # rather than silent inclusion.
            "needs_review": "yes" if r["status"] != "ok" or r["arabic_char_frac"] < 0.5 else "",
        })
        stats["pages"] += 1
        stats[r["status"]] = stats.get(r["status"], 0) + 1

    with MANIFEST.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=MANIFEST_FIELDS)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in MANIFEST_FIELDS})
    stats["needs_review"] = sum(1 for r in rows if r["needs_review"])
    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fetch", action="store_true", help="download the PDF first")
    ap.add_argument("--force", action="store_true", help="re-download even if present")
    ap.add_argument("--limit", type=int, default=None, help="only the first N pages")
    ap.add_argument("--quiet", action="store_true", help="suppress progress output")
    ap.add_argument("--page-timeout", type=int, default=60,
                    help="seconds before a page is abandoned as an OCR timeout")
    args = ap.parse_args(argv)

    if args.fetch:
        for k, v in fetch_pdf(force=args.force).items():
            print(f"  {k:22} {v}")
    for k, v in run(limit=args.limit, progress=not args.quiet,
                    page_timeout=args.page_timeout).items():
        print(f"  {k:22} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
