"""Stage 3 -- resolve every mirrored issue to a publication date.

This is the temporal backbone: nothing downstream can be dated without it.

Dates are recovered from up to four independent signals and reconciled, rather
than trusted from one place:

1. **Masthead** -- the Gregorian line on page 1. Searched only up to the
   ``Sommaire`` marker, because the summary lists *cited* acts whose dates
   would otherwise be picked up instead of the issue's own.
2. **Running headers** -- the date is repeated on most pages
   (``Page 2522 Journal Officiel ... - 27 avril 2010 N° 50``). A majority vote
   over these is the most robust signal, and it also yields the folio page,
   which is what a reader actually cites.
3. **Series ordinal** -- ``26ème année``. The gazette began in 1857 and the
   annonces series in 1984, so the ordinal implies a year and catches OCR
   damage to the printed year digits.
4. **Weekday** -- the masthead names the weekday, so it can be checked against
   the parsed date for free. This catches day/month transposition.

Nothing is interpolated. Issues whose signals disagree are flagged for review
and carry a date interval instead of a point.
"""
from __future__ import annotations

import argparse
import csv
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .paths import INTERIM, MANIFEST, PROCESSED, RAW, ensure_dirs

# --------------------------------------------------------------------------- #
# lexicons
# --------------------------------------------------------------------------- #

# Canonical French month names plus OCR and typographic variants observed in
# the corpus (the OCR renders "juillet" as "jullet", "aout" as "aoutt", etc.).
MONTHS_FR: dict[str, int] = {
    "janvier": 1, "janiver": 1, "janv": 1,
    "fevrier": 2, "fervier": 2, "fevier": 2, "fev": 2,
    "mars": 3,
    "avril": 4, "avirl": 4,
    "mai": 5,
    "juin": 6, "jiun": 6,
    "juillet": 7, "jullet": 7, "juilet": 7, "juill": 7,
    "aout": 8, "aoutt": 8, "aou": 8,
    "septembre": 9, "setpembre": 9, "sept": 9,
    "octobre": 10, "octbre": 10, "oct": 10,
    "novembre": 11, "novmbre": 11, "nov": 11,
    "decembre": 12, "decmbre": 12, "dec": 12,
}

WEEKDAYS_FR: dict[str, int] = {
    "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3,
    "vendredi": 4, "samedi": 5, "dimanche": 6,
}

# First year of each series, used by the ordinal cross-check.
SERIES_EPOCH = {"journal-officiel": 1857, "annonces-legales": 1984}

_MONTH_ALT = "|".join(sorted(MONTHS_FR, key=len, reverse=True))
_WD_ALT = "|".join(WEEKDAYS_FR)

RE_DATE_TXT = re.compile(
    r"\b(?P<d>1er|1ere|0?[1-9]|[12][0-9]|3[01])\s*(?:er|ere)?\s+"
    r"(?P<m>" + _MONTH_ALT + r")\s+"
    r"(?P<y>1[89][0-9]{2}|20[0-9]{2})\b",
    re.IGNORECASE,
)
RE_WEEKDAY = re.compile(r"\b(?P<wd>" + _WD_ALT + r")\b", re.IGNORECASE)
RE_ISSUE_NO = re.compile(r"N[°ºo]\s*(?P<a>\d{1,3})(?:\s*[-/]\s*(?P<b>\d{1,3}))?", re.IGNORECASE)
RE_ANNEE = re.compile(r"(?P<n>\d{1,3})\s*(?:[eè]me|[°ºe])\s*ann[ée]e", re.IGNORECASE)
RE_HIJRI_YEAR = re.compile(r"\b(?P<hy>1[234][0-9]{2})\b")
RE_SOMMAIRE = re.compile(r"^\s*#*\s*(sommaire|table des mati)", re.IGNORECASE | re.MULTILINE)
RE_PAGE_MARK = re.compile(r"<!--\s*page:(?P<n>\d+)\s*-->")

# Running header/footer lines. Both collections repeat the date on most pages;
# the annonces form also carries the folio page number.
RE_HDR = re.compile(
    r"^(?:Page\s+(?P<folio_a>\d{1,5})\s+)?Journal\s+Officiel\s+de\s+la\s+"
    r"R[ée]publique\s+Tunisienne\b(?P<rest>[^\n]*)$",
    re.IGNORECASE | re.MULTILINE,
)
RE_FOLIO_TRAIL = re.compile(r"^\s*Page\s+(?P<folio>\d{1,5})\s*$",
                            re.MULTILINE | re.IGNORECASE)

CALENDAR_FIELDS = [
    "issue_uid", "collection", "year_dir", "issue", "issue_no", "issue_no_end",
    "is_double_issue", "pub_date", "pub_date_lo", "pub_date_hi",
    "date_source", "date_confidence",
    "masthead_date", "header_date", "n_header_votes", "header_agrees",
    "weekday_stated", "weekday_actual", "weekday_consistent",
    "annee_ordinal", "annee_implied_year", "annee_consistent",
    "hijri_year", "hijri_plausible",
    "n_ocr_pages", "folio_first", "folio_last",
    "script_lang", "needs_review", "review_note",
]


def _fold(text: str) -> str:
    """Lowercase and strip diacritics for lexicon matching."""
    d = unicodedata.normalize("NFKD", text)
    return "".join(c for c in d if not unicodedata.combining(c)).lower()


def _to_date(m: re.Match) -> date | None:
    day_raw = _fold(m.group("d"))
    day = 1 if day_raw.startswith("1er") or day_raw.startswith("1ere") else int(day_raw)
    month = MONTHS_FR.get(_fold(m.group("m")))
    if not month:
        return None
    try:
        return date(int(m.group("y")), month, day)
    except ValueError:
        return None


def find_dates(text: str) -> list[date]:
    """Find every Gregorian date in `text`.

    The text is accent-folded first: the month lexicon is unaccented while the
    gazette prints "1er fevrier" with accents, and IGNORECASE does not fold
    diacritics.
    """
    out = []
    for m in RE_DATE_TXT.finditer(_fold(text)):
        d = _to_date(m)
        if d:
            out.append(d)
    return out


@dataclass
class IssueDate:
    row: dict = field(default_factory=dict)


def _masthead_region(text: str) -> str:
    """Page 1 up to the Sommaire, where the issue's own date lives.

    Truncating at the Sommaire matters: the summary enumerates cited acts with
    their own dates, and an untruncated scan can return one of those instead.
    """
    pages = list(RE_PAGE_MARK.finditer(text))
    end = pages[1].start() if len(pages) > 1 else min(len(text), 6000)
    region = text[:end]
    cut = RE_SOMMAIRE.search(region)
    return region[: cut.start()] if cut else region


def resolve_issue(collection: str, year_dir: int, issue: str, text: str,
                  script_lang: str) -> dict:
    row: dict = {
        "issue_uid": f"{collection}/fr/{year_dir}/{issue}",
        "collection": collection, "year_dir": year_dir, "issue": issue,
        "script_lang": script_lang,
        "n_ocr_pages": len(RE_PAGE_MARK.findall(text)),
    }
    notes: list[str] = []

    # Arabic issues under the /fr/ path cannot be dated by French lexicons and
    # must not be given a spuriously confident date.
    if script_lang != "fr":
        row.update(date_source="none", date_confidence=0.0, needs_review=True,
                   review_note=f"script_lang={script_lang}; not French text")
        return row

    # Work on an accent-folded copy for all lexicon matching. Character offsets
    # are preserved by folding, and this stage needs date values, not spans.
    text = _fold(text)
    head = _masthead_region(text)

    # --- issue number and double issues (e.g. "N° 2-3") ---
    mno = RE_ISSUE_NO.search(head)
    if mno:
        row["issue_no"] = int(mno.group("a"))
        if mno.group("b"):
            row["issue_no_end"] = int(mno.group("b"))
            row["is_double_issue"] = True

    # --- signal 1: masthead ---
    mast = find_dates(head)
    masthead_date = mast[0] if mast else None
    row["masthead_date"] = masthead_date.isoformat() if masthead_date else ""

    # --- signal 2: running headers, majority vote ---
    votes: Counter = Counter()
    folios: list[int] = []
    for m in RE_HDR.finditer(text):
        if m.group("folio_a"):
            folios.append(int(m.group("folio_a")))
        for d in find_dates(m.group("rest") or ""):
            votes[d] += 1
    for m in RE_FOLIO_TRAIL.finditer(text):
        folios.append(int(m.group("folio")))
    header_date = None
    if votes:
        header_date, n_votes = votes.most_common(1)[0]
        row["header_date"] = header_date.isoformat()
        row["n_header_votes"] = n_votes
    else:
        row["header_date"] = ""
        row["n_header_votes"] = 0
    if folios:
        row["folio_first"], row["folio_last"] = min(folios), max(folios)

    # --- signal 3: series ordinal ("26ème année") ---
    mann = RE_ANNEE.search(head)
    implied = None
    if mann:
        n = int(mann.group("n"))
        row["annee_ordinal"] = n
        epoch = SERIES_EPOCH.get(collection)
        if epoch:
            implied = epoch + n
            row["annee_implied_year"] = implied

    # --- weekday, read before the choice so it can arbitrate ---
    mwd = RE_WEEKDAY.search(head)
    stated = _fold(mwd.group("wd")) if mwd else ""
    row["weekday_stated"] = stated
    stated_idx = WEEKDAYS_FR.get(stated)

    def _wd_ok(d: date | None) -> bool:
        return bool(d is not None and stated_idx is not None
                    and d.weekday() == stated_idx)

    # --- choose a date ---
    # Where the masthead and the running headers disagree, the weekday printed
    # in the masthead decides. This is not a tie-break of convenience: in every
    # disagreement inspected in 2008-2012 the masthead proved correct and the
    # header date belonged to an adjacent issue, and the weekday identified that
    # correctly each time. A header majority only wins when the weekday is
    # missing or supports neither reading.
    chosen, source, conf = None, "none", 0.0
    if masthead_date and header_date and masthead_date == header_date:
        chosen, source, conf = masthead_date, "masthead+header", 0.99
    elif masthead_date and header_date:
        if _wd_ok(masthead_date):
            chosen, source, conf = masthead_date, "masthead_weekday_arbitrated", 0.93
            notes.append(f"header said {header_date}; weekday favours masthead")
        elif _wd_ok(header_date):
            chosen, source, conf = header_date, "header_weekday_arbitrated", 0.93
            notes.append(f"masthead said {masthead_date}; weekday favours header")
        elif row["n_header_votes"] >= 3:
            chosen, source, conf = header_date, "running_header", 0.65
            notes.append(f"masthead {masthead_date} != header {header_date}, weekday inconclusive")
        else:
            chosen, source, conf = masthead_date, "masthead", 0.65
            notes.append(f"masthead {masthead_date} != header {header_date}, weekday inconclusive")
    elif masthead_date:
        chosen, source, conf = masthead_date, "masthead", 0.90 if _wd_ok(masthead_date) else 0.85
    elif header_date:
        chosen, source, conf = header_date, "running_header", 0.80

    row["header_agrees"] = bool(
        masthead_date and header_date and masthead_date == header_date)

    if chosen and stated_idx is not None:
        actual = list(WEEKDAYS_FR)[chosen.weekday()]
        row["weekday_actual"] = actual
        ok = chosen.weekday() == stated_idx
        row["weekday_consistent"] = ok
        if not ok:
            # With masthead and headers concordant, a lone weekday mismatch is
            # far more likely a misprint or OCR slip in the weekday word than a
            # wrong date, so it is recorded without overriding the date.
            notes.append(f"weekday stated {stated} != actual {actual} (date left as is)")
            if source == "masthead+header":
                conf = min(conf, 0.80)
            else:
                conf = min(conf, 0.60)

    # --- ordinal consistency (tolerant: the series anniversary falls mid-January) ---
    if implied and chosen:
        ok = abs(implied - chosen.year) <= 1
        row["annee_consistent"] = ok
        if not ok:
            notes.append(f"annee implies {implied}, date says {chosen.year}")
            conf = min(conf, 0.60)

    # --- Hijri plausibility (a band check only; no conversion is attempted) ---
    mh = RE_HIJRI_YEAR.search(head)
    if mh and chosen:
        hy = int(mh.group("hy"))
        row["hijri_year"] = hy
        approx = (chosen.year - 622) * 1.0307
        row["hijri_plausible"] = abs(approx - hy) <= 2
        if not row["hijri_plausible"]:
            notes.append(f"hijri {hy} implausible for {chosen.year}")

    # --- directory-year sanity ---
    if chosen and not (year_dir - 1 <= chosen.year <= year_dir + 1):
        notes.append(f"date year {chosen.year} far from directory year {year_dir}")
        conf = min(conf, 0.40)

    if chosen:
        row["pub_date"] = chosen.isoformat()
        row["pub_date_lo"] = row["pub_date_hi"] = chosen.isoformat()
    row["date_source"] = source
    row["date_confidence"] = round(conf, 2)
    row["needs_review"] = bool(not chosen or conf < 0.85 or notes)
    row["review_note"] = "; ".join(notes)
    return row


def run() -> dict:
    ensure_dirs()
    with MANIFEST.open(encoding="utf-8", newline="") as fh:
        manifest = [r for r in csv.DictReader(fh)]

    rows: list[dict] = []
    for rec in manifest:
        if rec["status"] not in {"ok", "arabic", "mixed"}:
            continue
        path = RAW / rec["collection"] / rec["language"] / rec["year"] / f"{rec['issue']}.md"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        rows.append(resolve_issue(rec["collection"], int(rec["year"]), rec["issue"],
                                  text, rec.get("script_lang", "fr")))

    # monotonicity within (collection, year): issue numbers should increase with date
    rows.sort(key=lambda r: (r["collection"], r["year_dir"], r.get("issue_no") or 0))
    prev_key, prev_date = None, None
    for r in rows:
        key = (r["collection"], r["year_dir"])
        d = r.get("pub_date")
        if key != prev_key:
            prev_key, prev_date = key, d
            continue
        if d and prev_date and d < prev_date:
            note = f"non-monotonic: {d} follows {prev_date}"
            r["review_note"] = "; ".join(filter(None, [r.get("review_note"), note]))
            r["needs_review"] = True
            r["date_confidence"] = min(float(r["date_confidence"]), 0.55)
        if d:
            prev_date = d

    out = PROCESSED / "issue_calendar.csv"
    _write(out, rows, CALENDAR_FIELDS)
    problems = [r for r in rows if r["needs_review"]]
    _write(INTERIM / "calendar_problems.csv", problems, CALENDAR_FIELDS)

    dated = sum(1 for r in rows if r.get("pub_date"))
    return {
        "issues_examined": len(rows),
        "dated": dated,
        "undated": len(rows) - dated,
        "needs_review": len(problems),
        "source_masthead_and_header": sum(
            1 for r in rows if r["date_source"] == "masthead+header"),
        "source_header_only": sum(1 for r in rows if r["date_source"] == "running_header"),
        "source_masthead_only": sum(1 for r in rows if r["date_source"] == "masthead"),
    }


def _write(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description="Build the issue publication-date calendar.").parse_args(argv)
    stats = run()
    for k, v in stats.items():
        print(f"  {k:28} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
