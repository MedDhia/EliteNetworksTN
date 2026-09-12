"""Low-level cleaning of JORT OCR markdown.

The upstream OCR is good but not perfect, and the gazette's own typography
changed several times between 1957 and 2026.  Everything in this module is
about getting from a raw ``.md`` file to a stream of clean body paragraphs
with page provenance attached, so the extractor downstream can work on prose
rather than on layout debris.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

PAGE_MARKER = re.compile(r"<!--\s*page:(\d+)\s*-->")

# Running heads/feet repeated on every printed page.
_BOILERPLATE = [
    re.compile(r"^\s*Journal\s+Officiel\s+de\s+la\s+R[ée]publique\s+[Tt]unisienne.*$", re.I),
    re.compile(r"^\s*LE\s+JOURNAL\s+OFFICIEL\s+DE\s+LA\s+R[ÉE]PUBLIQUE.*$", re.I),
    re.compile(r"^\s*(Page\s*)?\d{1,5}\s*$"),
    re.compile(r"^\s*N[°ᵒo]\s*\d{1,3}\s*$", re.I),
    re.compile(r"^\s*!\[img[^\]]*\]\([^)]*\)\s*$"),
    re.compile(r"^\s*-{3,}\s*$"),
    re.compile(r"^\s*\d{1,3}\s*[ée]me?\s+ANN[ÉE]E.*$", re.I),
    re.compile(r"^\s*IMPRIMERIE\s+OFFICIELLE.*$", re.I),
    re.compile(r"^\s*Les\s+annonces\s+peuvent\s+[êe]tre\s+d[ée]pos[ée]es.*$", re.I),
    re.compile(r"^\s*(T[ée]l|C\.C\.P|Comptes?\s+courants?)\b.*$", re.I),
    re.compile(r"^\s*(Prix\s+du\s+num[ée]ro|Prix\s+des\s+Annonces|TARIFS)\b.*$", re.I),
    re.compile(r"^\s*Abonnement.*$", re.I),
]

# Arabic block — a few early "fr" numbers are in fact Arabic-only scans.
_ARABIC = re.compile(r"[؀-ۿ]")

_HEADING = re.compile(r"^\s*(#{1,6})\s*(.+?)\s*#*\s*$")

# Ligatures / OCR confusables that matter for name and title matching.
_CHAR_FIXES = {
    "’": "'",
    "‘": "'",
    "ʼ": "'",
    "´": "'",
    "“": '"',
    "”": '"',
    "–": "-",
    "—": "-",
    "‑": "-",
    " ": " ",
    "œ": "oe",
    "Œ": "OE",
    "ﬁ": "fi",
    "ﬂ": "fl",
    "…": "...",
}


def fix_chars(text: str) -> str:
    for bad, good in _CHAR_FIXES.items():
        text = text.replace(bad, good)
    return unicodedata.normalize("NFC", text)


def arabic_ratio(text: str) -> float:
    if not text:
        return 0.0
    return len(_ARABIC.findall(text)) / len(text)


@dataclass
class Block:
    """A paragraph (or heading) of body text with provenance."""

    text: str
    page: int
    is_heading: bool
    level: int = 0


def _strip_boilerplate(line: str) -> str | None:
    for pat in _BOILERPLATE:
        if pat.match(line):
            return None
    return line


def to_blocks(raw: str) -> list[Block]:
    """Split raw OCR markdown into cleaned paragraph/heading blocks."""
    raw = fix_chars(raw)
    blocks: list[Block] = []
    page = 0
    buf: list[str] = []

    def flush() -> None:
        if not buf:
            return
        text = re.sub(r"\s+", " ", " ".join(buf)).strip()
        buf.clear()
        if text:
            blocks.append(Block(text=text, page=page, is_heading=False))

    for line in raw.split("\n"):
        m = PAGE_MARKER.search(line)
        if m:
            flush()
            page = int(m.group(1))
            continue
        line = line.rstrip()
        if not line.strip():
            flush()
            continue
        kept = _strip_boilerplate(line)
        if kept is None:
            flush()
            continue
        h = _HEADING.match(kept)
        if h:
            flush()
            title = re.sub(r"\s+", " ", h.group(2)).strip()
            if title:
                blocks.append(
                    Block(text=title, page=page, is_heading=True, level=len(h.group(1)))
                )
            continue
        # Markdown tables: the gazette's summary pages are often OCR'd as
        # tables.  Keep the cell text, drop the pipes.
        if kept.lstrip().startswith("|"):
            cells = [c.strip() for c in kept.strip().strip("|").split("|")]
            cells = [c for c in cells if c and not set(c) <= {"-", ":", " "}]
            if not cells:
                continue
            kept = " ".join(cells)
        buf.append(kept.strip())

    flush()
    return blocks


# --- summary-page detection -------------------------------------------------
#
# Every issue opens with a "Sommaire" that paraphrases each act and ends each
# entry with a printed page number.  Those entries look enough like real acts
# to pollute the extraction, so we locate where the operative text begins.

_SOMMAIRE = re.compile(r"^\s*sommaire\s*$", re.I)
_BODY_MARKER = re.compile(
    r"^\s*(d[ée]crets?\s+et\s+arr[êe]t[ée]s|lois?\s*,?\s*d[ée]crets?\s+et\s+arr[êe]t[ée]s)\s*$",
    re.I,
)
# An operative clause: only ever appears in the body, never in the summary.
_OPERATIVE = re.compile(
    r"\b("
    r"Nous,?\s+[A-ZÉÈÀ]|"
    r"Vu\s+(la\s+loi|le\s+d[ée]cret|l'arr[êe]t[ée]|la\s+constitution)|"
    r"Par\s+(d[ée]cret|arr[êe]t[ée]|d[ée]cision)s?\b|"
    r"D[ée]cr[èe]t(e|ons)\s*:|"
    r"Article\s+premier|"
    r"Sur\s+proposition\s+d)",
    re.I,
)


# A summary entry always ends in the page number it points at.
_SUMMARY_ENTRY = re.compile(r"[.\s]\s*\d{3,5}\s*$")


def body_start(blocks: list[Block]) -> int:
    """Index of the first block belonging to the operative body of the issue.

    Biased towards keeping too much rather than too little: a stray summary
    line produces no events (summary entries are noun phrases with no
    operative verb), whereas cutting one block too far loses the ministry
    heading that gives the first act of the issue its institutional context.
    """
    first_op = next((i for i, b in enumerate(blocks) if _OPERATIVE.search(b.text)), None)
    if first_op is None:
        return 0

    # The authority heading an act sits under ("MINISTERE DE LA SANTE") comes
    # immediately before it, so never cut into the run of headings that
    # directly precedes the first operative block.
    earliest = first_op
    while earliest > 0 and blocks[earliest - 1].is_heading:
        earliest -= 1

    # Prefer an explicit "DECRETS ET ARRETES" body banner that sits after the
    # summary; the same banner also titles the summary, so take the last one
    # occurring at or before the first operative clause.  It is printed as a
    # heading in some years and as a plain line in others.
    start = 0
    for i, b in enumerate(blocks[:first_op]):
        if _BODY_MARKER.match(b.text) or _SOMMAIRE.match(b.text):
            start = i + 1
        elif not b.is_heading and _SUMMARY_ENTRY.search(b.text):
            start = max(start, i + 1)
    return min(start, earliest)
