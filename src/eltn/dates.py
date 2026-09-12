"""French gazette date parsing, tolerant of OCR damage."""

from __future__ import annotations

import datetime as dt
import re
import unicodedata

_MONTHS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "decembre": 12,
    # OCR variants and older/Tunisian spellings actually observed in the corpus.
    "janiver": 1, "janvler": 1, "fevier": 2, "fevrler": 2, "avirl": 4,
    "juilet": 7, "juiliet": 7, "jouillet": 7, "juillei": 7, "aoout": 8,
    "aou": 8, "aot": 8, "septembere": 9, "setpembre": 9, "ocotbre": 10,
    "octbre": 10, "novembere": 11, "novmbre": 11, "decmbre": 12, "decembr": 12,
}

_MONTH_ALT = "|".join(sorted(_MONTHS, key=len, reverse=True))

DATE_RE = re.compile(
    r"\b(?P<day>1\s*er|1[eè]re|0?[1-9]|[12]\d|3[01])\s*"
    r"(?P<month>[a-zA-Zéèêûôàç]{3,12})\s*"
    r"(?P<year>1[89]\d{2}|20\d{2})\b"
)


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def parse_date(text: str) -> dt.date | None:
    """First French-style date in ``text``, or None."""
    for m in DATE_RE.finditer(text):
        month = _MONTHS.get(_fold(m.group("month")))
        if month is None:
            continue
        digits = re.sub(r"\D", "", m.group("day"))
        day = int(digits) if digits else 1
        year = int(m.group("year"))
        try:
            return dt.date(year, month, day)
        except ValueError:
            continue
    return None


def parse_all_dates(text: str) -> list[dt.date]:
    out = []
    for m in DATE_RE.finditer(text):
        d = parse_date(m.group(0))
        if d:
            out.append(d)
    return out


EFFECT_RE = re.compile(
    r"\b(?:et\s+ce,?\s+)?"
    r"(?P<kind>[àa]\s+compter\s+du|[àa]\s+partir\s+du|avec\s+effet\s+(?:[àa]\s+compter\s+)?du|"
    r"prend\s+effet\s+[àa]\s+compter\s+du|[àa]\s+compter\s+de\s+la\s+date)"
    r"\s*(?P<rest>[^.;]{0,60})",
    re.I,
)


def effective_date(text: str) -> dt.date | None:
    """Date named by an 'a compter du ...' clause, if any."""
    m = EFFECT_RE.search(text)
    if not m:
        return None
    return parse_date(m.group("rest"))
