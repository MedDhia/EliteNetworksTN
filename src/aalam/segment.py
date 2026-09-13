"""Stage 2: cut the volume into its 38 biographical entries.

Entry boundaries come from the printed table of contents (pp. 377-379),
transcribed into ``config/aalam_entries.csv``, rather than from detecting
headwords in the text. That choice is forced by the source: entry headings are
set in elongated display type, which is the one thing on these pages tesseract
reads badly -- Ali al-Wardani's dates come through as ``(1561 11)1905)``. The
body text, which is what the extractor actually reads, is clean.

So the table of contents supplies the spine and the page header is used only
to *check* it. Where the two disagree the row is flagged rather than silently
trusted, which is also how the calendar stage in the multiplex build arbitrates
between its date signals.

Printed folio and PDF page index differ by a constant offset, and the printed
folio itself OCRs unreliably (97 reads as "07", 193 as "103"). The PDF page
index is therefore authoritative throughout; the folio is carried for citation.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import re

from .paths import (CONFIG, INTERIM, MANIFEST, PROCESSED, ensure_dirs,
                    load_config, page_text_path)
from .names_ar import parse_person
from .textnorm_ar import arabic_only, clean_page, fold

ENTRY_FIELDS = [
    "entry_uid", "cohort", "cohort_no", "entry_no", "name_ar", "name_toc",
    "birth_year", "death_year", "role_descriptor_ar", "rank",
    "folio_start", "folio_end", "pdf_page_start", "pdf_page_end", "n_pages",
    "n_chars", "text_sha1", "header_name_agrees", "needs_review", "review_note",
]

# A year in this volume is a four-digit Gregorian year between the Hafsids and
# the present. Anything outside that is OCR damage, not a date.
_YEAR = re.compile(r"\b(1[0-9]{3}|20[0-2][0-9])\b")
_PAGENO = re.compile(r"^\s*\d{1,3}\s*$")
# The volume marks an unknown year with an ellipsis inside the date bracket.
_UNKNOWN_YEAR = re.compile(r"\.{2,}|…|؟")


def _load_spine() -> list[dict]:
    with (CONFIG / "aalam_entries.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["cohort_no"] = int(r["cohort_no"])
        r["entry_no"] = int(r["entry_no"])
        r["folio_start"] = int(r["folio_start"])
    return rows


def _names_agree(header_name: str, toc_name: str) -> bool:
    """Does the heading name the same man as the table of contents?

    Compared on the honorific-stripped matching key, because the heading
    carries titles the contents list omits (الشيخ إبراهيم الرياحي against
    إبراهيم الرياحي). Surname containment counts as agreement: display type
    damages the given name far more often than the surname, so
    "محمد الأميسن الشسابسى" should still be recognised as al-Shabbi.
    """
    h, t = parse_person(header_name), parse_person(toc_name)
    if h.is_empty or t.is_empty:
        return False
    if h.match_key == t.match_key:
        return True
    return h.surname_key == t.surname_key


def _page_text(pdf_page: int) -> str:
    path = page_text_path(pdf_page)
    return path.read_text(encoding="utf-8") if path.exists() else ""


def strip_chrome(text: str) -> str:
    """Drop the running page number, keeping everything else.

    A page number is a short all-digit line. Dropping it by shape rather than
    by position matters because it sits at the foot on some pages and the head
    on others, and because an entry's body can legitimately open with a digit.
    """
    kept = [ln for ln in text.splitlines() if not _PAGENO.match(ln)]
    return "\n".join(kept)


def parse_header(text: str) -> dict:
    """Read the name, life dates and role descriptor from an entry's opening.

    Every entry opens the same way: the name, then the birth and death years in
    parentheses, then a short descriptor the author assigns
    (الجندي والمصلح ورجل الدولة). The parentheses are frequently damaged, so
    years are taken as the first two plausible four-digit numbers near the top
    of the page rather than by matching the bracket shape.
    """
    lines = [ln.strip() for ln in strip_chrome(text).splitlines() if ln.strip()]
    head = lines[:6]
    name = head[0] if head else ""

    years, year_line = [], None
    for i, ln in enumerate(head):
        found = _YEAR.findall(ln)
        if len(found) >= 2:
            years, year_line = [int(found[0]), int(found[1])], i
            break
        if found and years:
            years.append(int(found[0]))
            break
        if found:
            years, year_line = [int(found[0])], i

    # Bidirectional rendering flips the pair on some pages: Ibn al-Khuja's
    # dates come out as ")1942 - 1869(". The smaller year is the birth either
    # way, so order the pair rather than trusting the order it was read in.
    birth = death = ""
    if len(years) >= 2:
        birth, death = min(years[:2]), max(years[:2])
    elif len(years) == 1:
        # The book prints "(... - 1887)" where it does not know a birth year.
        # That is the source declining to state it, not OCR failing to read
        # it, and the two must not be reported as the same kind of gap.
        line = head[year_line] if year_line is not None else ""
        if _UNKNOWN_YEAR.search(line):
            death = years[0]
        else:
            birth = years[0]

    role = ""
    if year_line is not None:
        for ln in head[year_line + 1:]:
            if not _YEAR.search(ln) and len(arabic_only(ln)) > 4:
                role = ln
                break
    return {"name": name, "birth_year": birth, "death_year": death,
            "role_descriptor_ar": role}


def run() -> dict[str, int]:
    ensure_dirs()
    cfg = load_config("aalam_scope")
    offset = cfg["volume"]["folio_offset"]
    n_pdf = cfg["volume"]["n_pdf_pages"]
    if not MANIFEST.exists():
        raise SystemExit("data/raw/aalam/manifest.csv missing. Run `make aalam-ingest`.")

    spine = _load_spine()
    # The last entry runs to the index, which the table of contents places at
    # folio 377. Everything from there on is apparatus, not biography.
    index_folio = 377
    bounds = [r["folio_start"] for r in spine[1:]] + [index_folio]

    rows, texts, stats = [], {}, {"entries": 0, "flagged": 0, "pages": 0}
    for r, next_start in zip(spine, bounds):
        f_start, f_end = r["folio_start"], next_start - 1
        p_start, p_end = f_start + offset, min(f_end + offset, n_pdf)
        body = "\n".join(_page_text(p) for p in range(p_start, p_end + 1))
        header = parse_header(_page_text(p_start))

        agrees = _names_agree(header["name"], r["name_ar"])
        notes = []
        if not agrees:
            notes.append(f"header reads {header['name']!r}, TOC reads {r['name_ar']!r}")
        if not header["death_year"]:
            notes.append("life dates not parsed from header")
        elif not header["birth_year"]:
            # Recorded, not flagged: the source itself leaves it open.
            pass
        if not body.strip():
            notes.append("no OCR text for this page range")

        text = clean_page(strip_chrome(body))
        uid = f"aalam:{r['cohort_no']}.{r['entry_no']:02d}"
        texts[uid] = text
        rows.append({
            "entry_uid": uid,
            "cohort": r["cohort"], "cohort_no": r["cohort_no"],
            "entry_no": r["entry_no"],
            # The table of contents is the authority on the name: it is set in
            # body type and reads cleanly, while the heading on the page is
            # display type and does not.
            "name_ar": r["name_ar"], "name_toc": r["name_ar"],
            "birth_year": header["birth_year"], "death_year": header["death_year"],
            "role_descriptor_ar": header["role_descriptor_ar"], "rank": "",
            "folio_start": f_start, "folio_end": f_end,
            "pdf_page_start": p_start, "pdf_page_end": p_end,
            "n_pages": p_end - p_start + 1,
            "n_chars": len(text),
            "text_sha1": hashlib.sha1(text.encode("utf-8")).hexdigest(),
            "header_name_agrees": "yes" if agrees else "no",
            "needs_review": "yes" if notes else "",
            "review_note": "; ".join(notes),
        })
        stats["entries"] += 1
        stats["pages"] += p_end - p_start + 1
        if notes:
            stats["flagged"] += 1

    rows.sort(key=lambda r: (r["cohort_no"], r["entry_no"]))
    with (PROCESSED / "entries.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=ENTRY_FIELDS)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in ENTRY_FIELDS})

    INTERIM.mkdir(parents=True, exist_ok=True)
    with (INTERIM / "entry_texts.jsonl").open("w", encoding="utf-8") as fh:
        import json
        for row in rows:
            fh.write(json.dumps(
                {"entry_uid": row["entry_uid"], "text": texts[row["entry_uid"]]},
                ensure_ascii=False) + "\n")

    stats["dated"] = sum(1 for r in rows if r["birth_year"] and r["death_year"])
    return stats


def main(argv=None) -> int:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    for k, v in run().items():
        print(f"  {k:22} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
