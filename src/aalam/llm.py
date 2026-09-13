"""Stage 4: the model pass, and the gate that makes it checkable.

The rule pass in ``extract.py`` is deliberately confined to cues whose
grammar binds the counterparty -- a preposition or a possessive pronoun. That
leaves most of the book unread, because most of what it asserts is carried by
ordinary verb-initial sentences whose subject a pattern cannot identify.

This stage covers that remainder by reading the entries and returning
assertions in the same schema. It is not trusted. Two things constrain it:

1. **Every assertion must quote the entry verbatim.** ``verify`` checks each
   ``evidence_quote`` against the entry text it claims to come from, after the
   same normalisation the text itself went through, and drops any that is not
   literally present. An assertion about a tie the book does not state cannot
   survive, because there is no sentence to quote for it.
2. **The output is committed, and everything after it is deterministic.**
   ``records/assertions_model.jsonl.gz`` is an input to the build, not
   something regenerated on each run, so the tables rebuild byte-identically
   and re-running the model is a reviewable change rather than a silent one.

This is the arrangement the bourse build already uses for its PDF extraction,
and the reason its tables can be diffed in CI.
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
from pathlib import Path

from .extract import ASSERTION_FIELDS
from .paths import INTERIM, PROCESSED, ensure_dirs
from .textnorm_ar import fold

RECORDS = PROCESSED / "records"
MODEL_ASSERTIONS = RECORDS / "assertions_model.jsonl.gz"


def open_text(path: Path, mode: str = "r"):
    """Open a file, transparently gzipping when the name ends in .gz.

    Writes pin the gzip header mtime to 0. A gzip stream otherwise records the
    time it was written, so rebuilding unchanged data would produce different
    bytes and show up as a spurious diff on every run. This is the same opener
    the bourse build uses, and the reason its tables can be byte-diffed.
    """
    if str(path).endswith(".gz"):
        if "w" in mode or "a" in mode:
            raw = gzip.GzipFile(filename=path, mode=mode + "b", mtime=0)
            return io.TextIOWrapper(raw, encoding="utf-8", newline="")
        return gzip.open(path, mode + "t", encoding="utf-8", newline="")
    return path.open(mode, encoding="utf-8", newline="")


def load_entry_texts() -> dict[str, str]:
    src = INTERIM / "entry_texts.jsonl"
    if not src.exists():
        raise SystemExit("entry_texts.jsonl missing. Run `make aalam-segment`.")
    out = {}
    with src.open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            out[rec["entry_uid"]] = rec["text"]
    return out


def quote_is_verbatim(quote: str, text: str) -> bool:
    """Is this quote literally in the entry?

    Compared on the folded form, because the quote is transcribed from the
    same OCR the entry holds but may differ in the orthography folding already
    treats as equivalent. Whitespace is collapsed on both sides: a quote that
    spans a line break in the source is still the same sentence.
    """
    if not quote.strip():
        return False
    return " ".join(fold(quote).split()) in " ".join(fold(text).split())


def verify(rows: list[dict], texts: dict[str, str]) -> tuple[list[dict], list[dict]]:
    """Split assertions into those the text supports and those it does not."""
    kept, rejected = [], []
    for r in rows:
        text = texts.get(r.get("entry_uid", ""))
        if text is None:
            r = dict(r, needs_review="yes")
            rejected.append(dict(r, review_reason="unknown entry_uid"))
        elif not quote_is_verbatim(r.get("evidence_quote", ""), text):
            rejected.append(dict(r, review_reason="quote not found in entry"))
        else:
            kept.append(r)
    return kept, rejected


def run(strict: bool = False) -> dict[str, int]:
    ensure_dirs()
    RECORDS.mkdir(parents=True, exist_ok=True)
    texts = load_entry_texts()

    rows: list[dict] = []
    if MODEL_ASSERTIONS.exists():
        with open_text(MODEL_ASSERTIONS) as fh:
            rows = [json.loads(line) for line in fh if line.strip()]

    kept, rejected = verify(rows, texts)
    if rejected:
        out = INTERIM / "assertions_rejected.jsonl"
        with out.open("w", encoding="utf-8") as fh:
            for r in rejected:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    if strict and rejected:
        raise SystemExit(
            f"{len(rejected)} model assertions do not quote their entry. "
            "See data/interim/aalam/assertions_rejected.jsonl."
        )

    merged = INTERIM / "assertions_model_verified.jsonl"
    kept.sort(key=lambda r: (r.get("entry_uid", ""), r.get("assertion_id", "")))
    with merged.open("w", encoding="utf-8") as fh:
        for r in kept:
            fh.write(json.dumps({k: r.get(k, "") for k in ASSERTION_FIELDS},
                                ensure_ascii=False) + "\n")
    return {"submitted": len(rows), "verified": len(kept), "rejected": len(rejected)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strict", action="store_true",
                    help="fail if any assertion does not quote its entry")
    args = ap.parse_args(argv)
    for k, v in run(strict=args.strict).items():
        print(f"  {k:22} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
