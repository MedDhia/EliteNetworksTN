"""Locate and classify the data tables inside a CMF registration document.

CMF reglementation fixes the *content* of a document de reference but not its
typography: section numbering drifts between issuers and across years, and
headings are reworded. Classifying tables by their **header row** rather than by
section number therefore survives far more of the corpus than an index-based
parser would.

Section headings are still read, but only as disambiguating context. Two tables
share the header ``Actionnaires | Nombre d'actions | Montant | %``: the
blockholder table (s2.4.2) and the directors' own holdings (s2.4.3). They are
different network layers, so the preceding heading decides which is which.
"""

from __future__ import annotations

import itertools
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

# --------------------------------------------------------------------------
# text helpers
# --------------------------------------------------------------------------


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def norm(s: str | None) -> str:
    """Lowercase, de-accent and collapse whitespace, for matching only."""
    if not s:
        return ""
    s = strip_accents(s).lower()
    s = s.replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", s).strip()


_NUM = re.compile(r"^-?[\d\s .,]+$")


def to_number(s: str | None) -> float | None:
    """Parse a French-formatted figure ('1 234 567,89', '39,00%') to float."""
    if s is None:
        return None
    t = str(s).replace(" ", " ").replace("%", "").strip()
    if not t or not _NUM.match(t):
        return None
    t = t.replace(" ", "")
    # French convention: ',' decimal separator, '.' or space thousands.
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif t.count(".") == 1 and len(t.split(".")[-1]) <= 2:
        pass  # already a decimal point
    else:
        t = t.replace(".", "")
    try:
        return float(t)
    except ValueError:
        return None


# Dates written as "au 31/08/2025", "au 31 decembre 2024", "31-12-2023".
_MONTHS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "decembre": 12,
}
_DATE_NUM = re.compile(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})")
_DATE_TXT = re.compile(r"(\d{1,2})\s+(" + "|".join(_MONTHS) + r")\s+(\d{4})")


MIN_YEAR, MAX_YEAR = 1990, 2035


def find_as_of_date(text: str) -> str | None:
    """Return the ISO 'as of' date a heading refers to, if it states one.

    Years outside a plausible reporting window are rejected: issuer documents
    routinely cite founding statutes ("loi n 67-51 du 7 decembre 1967"), which
    would otherwise be read as an observation date.
    """
    n = norm(text)
    m = _DATE_NUM.search(n)
    if m:
        d, mo, y = (int(x) for x in m.groups())
        if 1 <= mo <= 12 and 1 <= d <= 31 and MIN_YEAR <= y <= MAX_YEAR:
            return f"{y:04d}-{mo:02d}-{d:02d}"
    m = _DATE_TXT.search(n)
    if m:
        d, mon, y = int(m.group(1)), _MONTHS[m.group(2)], int(m.group(3))
        if MIN_YEAR <= y <= MAX_YEAR:
            return f"{y:04d}-{mon:02d}-{d:02d}"
    return None


# --------------------------------------------------------------------------
# table classification
# --------------------------------------------------------------------------

TABLE_KINDS = (
    "blockholders",       # named holders and their stake -> ownership layer
    "director_holdings",  # board members' own stakes -> ownership layer (person)
    "capital_structure",  # aggregate categories (resident/foreign, legal/natural)
    "board",              # board membership -> affiliation layer
    "interlocks",         # declared mandates in other firms -> interlock layer
    "executives",         # outside executive roles
    "subsidiaries",       # group participations -> firm-firm ownership layer
)


def _squash(s: str) -> str:
    """Drop all spacing, so header words broken across line wraps still match.

    Narrow table columns wrap mid-word, and pdfplumber preserves the break:
    '% de Participatio n Directe' normalises to 'participatio n directe'.
    Matching the space-free form recovers 'participation'.
    """
    return re.sub(r"[\s'.-]+", "", s)


def _has(hdr: str, *words: str) -> bool:
    return all(w in hdr for w in words)


def _any(hdr: str, *words: str) -> bool:
    sq = _squash(hdr)
    return any(w in hdr or _squash(w) in sq for w in words)


def classify_table(header: list[str], heading: str) -> str | None:
    """Return a TABLE_KIND for a table given its header row and nearest heading."""
    h = " | ".join(norm(c) for c in header)
    ctx = norm(heading)

    if not h.strip(" |"):
        return None

    # Aggregate capital structure first: its rows are categories, not named
    # holders, and it shares the "Actionnaires ... %" header shape with the
    # blockholder table. Two giveaways: a count-of-shareholders column, or a
    # heading that says "structure du capital" (the count column is not always
    # recoverable, because narrow columns split "Nombre d'actionnaires" across
    # several cells).
    if _any(h, "actionnaire") and _any(h, "nombre d'actionnaires", "nombre d actionnaires"):
        return "capital_structure"
    if _any(ctx, "structure du capital") and _any(h, "actionnaire", "%"):
        return "capital_structure"

    # --- shareholder-style tables -----------------------------------------
    if _any(h, "actionnaire", "detenteur") and _any(h, "% du capital", "pourcentage", "%"):
        # s2.4.3 lists the stakes of board/management members specifically.
        if _any(ctx, "organes d'administration", "organes d administration",
                "membres des organes", "dirigeants"):
            return "director_holdings"
        # Group-structure sections list the shareholders of *subsidiaries*, not
        # of the issuer. Reading those as the issuer's own blockholders inflates
        # its declared capital well past 100%, so they are rejected rather than
        # misattributed.
        if _any(ctx, "structure groupe", "structure du groupe", "objectif",
                "filiale", "societes du groupe", "organigramme", "participations"):
            return None
        # Otherwise require the heading to be about capital or shareholders.
        # An unrecognised heading is accepted only when we have none at all.
        if ctx and not _any(
            ctx, "capital", "actionnaire", "actionnariat", "repartition",
            "detenant", "detention", "titres", "droits de vote",
        ):
            return None
        return "blockholders"

    # --- board and mandates ------------------------------------------------
    if _any(h, "membre", "administrateur", "nom et prenom"):
        if _any(h, "autres societes", "autre societe") or _any(
            ctx, "mandats d'administrateurs", "mandats d administrateurs",
            "dans d'autres societes", "dans d autres societes"
        ):
            return "interlocks"
        if _any(h, "activites exercees") or _any(ctx, "activites exercees", "en dehors de"):
            return "executives"
        if _any(h, "qualite", "mandat", "fonction", "represente par"):
            return "board"

    # --- group structure ---------------------------------------------------
    if _any(h, "societe", "filiale") and _any(
        h, "participation", "consolidation", "% de detention", "% detenu"
    ):
        return "subsidiaries"

    return None


# --------------------------------------------------------------------------
# extraction
# --------------------------------------------------------------------------

def _page_lines(page) -> list[tuple[float, str]]:
    """Reconstruct (vertical_position, text) lines from positioned words."""
    try:
        words = page.extract_words(use_text_flow=False)
    except Exception:
        return []
    buckets: dict[int, list] = {}
    for w in words:
        buckets.setdefault(round(w["top"] / 3.0), []).append(w)
    lines = []
    for key in sorted(buckets):
        ws = sorted(buckets[key], key=lambda w: w["x0"])
        lines.append((min(w["top"] for w in ws), " ".join(w["text"] for w in ws)))
    return lines


def page_headings(page_or_text) -> list[tuple[float, str]]:
    """Numbered section headings on a page as (vertical_position, text).

    Table-of-contents lines are excluded: they carry dot leaders and a trailing
    page number, and would otherwise supply the wrong context for every table.
    """
    if isinstance(page_or_text, str):
        lines = [(float(i), ln) for i, ln in enumerate(page_or_text.splitlines())]
    else:
        lines = _page_lines(page_or_text)
    out = []
    for top, line in lines:
        line = line.strip()
        if len(line) < 12 or line.count("....") or line.count(". . ."):
            continue
        if re.match(r"^\d+(\.\d+)*\.?\s+\S", line):
            out.append((top, line))
    return out


# One French-formatted figure: thousands grouped in threes by space or dot,
# optional decimal comma, optional percent sign. Anchoring the group size is
# what stops "1 299 992 12 999 920" being swallowed as a single number.
_FRENCH_NUM = re.compile(
    r"\d{1,3}(?:[\s\u00a0.]\d{3})+(?:[,.]\d+)?\s*%?"   # grouped: 1 299 992
    r"|\d+(?:[,.]\d+)?\s*%?"                            # plain:   12,99
)


def split_label_and_figures(line: str) -> tuple[str, list[str]] | None:
    """Split a borderless table line into (label, [figures]).

    Only the *trailing* run of figures counts: a label may legitimately contain
    digits ("Ayant plus de 0,5% et moins de 3%"), and those must stay in the
    label rather than becoming columns.
    """
    matches = list(_FRENCH_NUM.finditer(line))
    if not matches:
        return None
    # Walk back from the end while each figure is separated from the next only
    # by whitespace; that trailing run is the numeric part of the row.
    start = len(matches)
    end_pos = len(line.rstrip())
    for i in range(len(matches) - 1, -1, -1):
        m = matches[i]
        if line[m.end():end_pos].strip():
            break
        start = i
        end_pos = m.start()
    if start >= len(matches):
        return None
    label = line[: matches[start].start()].strip(" .:-\u2026")
    figures = [m.group(0).strip() for m in matches[start:]]
    return (label, figures) if label else None


def _page_cell_lines(page, gap_factor: float = 2.2, min_gap: float = 4.0):
    """Reconstruct lines as *cells*, splitting on inter-word gaps.

    Flattening a line to a single string loses the column structure, and that
    loss is not recoverable by regex: "975 000 975 000" is equally readable as
    one figure or as two. Word coordinates settle it - a column break is a gap
    much wider than the line's ordinary word spacing.
    """
    try:
        words = page.extract_words(use_text_flow=False)
    except Exception:
        return []
    buckets: dict[int, list] = {}
    for w in words:
        buckets.setdefault(round(w["top"] / 3.0), []).append(w)

    out = []
    for key in sorted(buckets):
        ws = sorted(buckets[key], key=lambda w: w["x0"])
        if not ws:
            continue
        gaps = [b["x0"] - a["x1"] for a, b in zip(ws, ws[1:])]
        if gaps:
            ordinary = sorted(g for g in gaps if g > 0)
            median = ordinary[len(ordinary) // 2] if ordinary else 0.0
            threshold = max(min_gap, median * gap_factor)
        else:
            threshold = min_gap
        cells, cur = [], [ws[0]["text"]]
        for (a, b), gap in zip(zip(ws, ws[1:]), gaps):
            if gap > threshold:
                cells.append(" ".join(cur))
                cur = [b["text"]]
            else:
                cur.append(b["text"])
        cells.append(" ".join(cur))
        out.append((min(w["top"] for w in ws), cells))
    return out


def synth_rows_from_text(page, top: float, bottom: float) -> list[list[str]]:
    """Recover table rows from text when a table has no ruling lines.

    Many issuers typeset shareholder tables with a ruled *header* but a
    borderless body, so pdfplumber reports a two-row table holding only the
    header. The body is still on the page as text.

    Rows are cut on column gaps where the geometry allows it, and fall back to
    regex tokenisation of the flat line otherwise. A row qualifies only if it
    ends in at least two figures, or in one figure carrying a percent sign;
    looser rules pull in running prose and page furniture.
    """
    rows: list[list[str]] = []
    for y, cells in _page_cell_lines(page):
        if not (top < y < bottom):
            continue
        cells = [c.strip() for c in cells if c.strip()]
        if len(cells) < 2:
            flat = " ".join(cells)
            parsed = split_label_and_figures(flat) if len(flat) >= 5 else None
            if not parsed:
                continue
            label, figures = parsed
        else:
            label = cells[0]
            figures = cells[1:]
            # A gap-split cell may still hold several figures. Always re-split on
            # the figure pattern: "12 999 920 12,99%" parses as a single number
            # under a permissive numeric test, so testing to_number() first would
            # silently keep it merged.
            expanded: list[str] = []
            for f in figures:
                hits = [m.group(0).strip() for m in _FRENCH_NUM.finditer(f)]
                expanded.extend(hits if len(hits) > 1 else [f])
            figures = [f for f in expanded if f]
        if not figures or len(label) < 2:
            continue
        if len(figures) < 2 and not any("%" in f for f in figures):
            continue
        if to_number(label) is not None:
            continue
        rows.append([label] + figures)
    return rows


@dataclass
class FoundTable:
    kind: str
    page: int                      # 1-indexed
    heading: str
    as_of: str | None
    header: list[str]
    rows: list[list[str]]
    # True when rows were recovered from text because the table had no ruled
    # body. Header column indices do not apply to such rows.
    synthesized: bool = False
    meta: dict[str, Any] = field(default_factory=dict)


def _clean_cell(c: str | None) -> str:
    if c is None:
        return ""
    return re.sub(r"\s+", " ", c.replace("\n", " ")).strip()


def _is_noise(table: list[list[str]]) -> bool:
    """Drop page-furniture tables (footers, page-number boxes)."""
    if len(table) < 2:
        return True
    cells = [_clean_cell(c) for row in table for c in row]
    filled = [c for c in cells if c]
    if len(filled) < 3:
        return True
    return False


# A page can only hold a table we care about if one of these words appears in
# its text. Checking that first avoids running table detection and word
# extraction over the hundreds of financial-statement pages in each filing,
# which dominate runtime and never classify.
_RELEVANT_PAGE = re.compile(
    r"actionnaire|actionnariat|capital|conseil d|administrat|mandat|"
    r"filiale|participation|membre|dirigeant|organes d",
    re.I,
)


# Scanned filings do not number their sections; they set titles in capitals
# ("STRUCTURE DU CAPITAL", "LE CONSEIL D'ADMINISTRATION"). The heading is then
# the only thing identifying a table, because the column header is frequently
# a single merged cell or missing altogether.
_HEADING_KINDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    # Ordered: the first match wins, so the more specific headings come first.
    ("director_holdings", ("participations des dirigeants", "actions detenues par les membres",
                           "participation des membres", "actions des dirigeants")),
    ("interlocks", ("mandats d'administrateurs", "mandats d administrateurs",
                    "mandats dans d'autres societes", "mandats dans d autres societes",
                    "autres mandats")),
    ("executives", ("activites exercees en dehors", "fonctions exercees en dehors")),
    ("subsidiaries", ("societes du groupe", "filiales et participations",
                      "liste des filiales", "participations financieres",
                      "portefeuille de participations")),
    ("board", ("conseil d'administration", "conseil d administration",
               "membres du conseil", "administrateurs", "president du conseil",
               "president directeur general", "composition du conseil",
               "organes d'administration", "organes d administration",
               "conseil de surveillance", "directoire")),
    ("blockholders", ("principaux actionnaires", "actionnaires detenant",
                      "repartition du capital", "actionnariat",
                      "structure de l'actionnariat", "structure de l actionnariat",
                      "liste des actionnaires")),
)

# Kinds whose rows carry figures, and so can be qualified by the existing
# borderless-row rule. `capital_structure` is deliberately absent: its parser
# maps columns by fixed position for synthesized rows, and a scanned table that
# omits the shareholder-count column would have its share figures read out of
# the percentage column. An aggregate carries no edge, so a wrong number there
# would be a pure loss.
_OCR_FIGURE_KINDS = {"blockholders", "director_holdings", "subsidiaries"}
_OCR_ROSTER_KINDS = {"board", "interlocks", "executives"}

# A synthetic header, since scanned rosters rarely print one. The column order
# is what these filings actually use, and `parse_board` maps by header name.
_ROSTER_HEADER = ["Membre", "Qualité", "Représenté par"]

_HONORIFIC_ONLY = re.compile(r"^(?:mr?|mm|mme|mlle|dr|pr|me)s?\.?$", re.I)
_ROLE_TAIL = re.compile(
    r"\s(?:repr[ée]sentant|repr[ée]sent[ée]\s+par|pr[ée]sident|administrateur|"
    r"directeur\s+g[ée]n[ée]ral|membre)\b.*$", re.I)
_PROSE = re.compile(r"\b(?:que|dont|ainsi|lequel|selon|apres|lors de|il est|elle est)\b", re.I)


def classify_from_heading(heading: str) -> str | None:
    """Identify a table from its heading alone.

    Used only for OCR'd pages. A digital filing is classified from its column
    header, which is far stronger evidence; this is the weaker rule that scanned
    pages leave available, and it is why the OCR path is kept separate.
    """
    ctx = norm(heading)
    if not ctx:
        return None
    for kind, needles in _HEADING_KINDS:
        if _any(ctx, *needles):
            return kind
    return None


def _is_caps_title(line: str) -> bool:
    """Whether a line reads as a typeset section title rather than body text."""
    s = line.strip()
    if not (6 <= len(s) <= 90) or s.endswith((".", ",", ";", ":")):
        return False
    letters = [c for c in s if c.isalpha()]
    if len(letters) < 5:
        return False
    return sum(c.isupper() for c in letters) / len(letters) >= 0.85


def ocr_headings(page) -> list[tuple[float, str]]:
    """Headings on a scanned page: numbered ones, plus capitalised titles."""
    heads = list(page_headings(page))
    seen = {round(y) for y, _ in heads}
    for y, cells in _page_cell_lines(page):
        line = " ".join(c for c in cells if c.strip()).strip()
        if round(y) not in seen and _is_caps_title(line):
            heads.append((y, line))
    heads.sort(key=lambda h: h[0])
    return heads


def _roster_rows(page, top: float, bottom: float) -> list[list[str]]:
    """Rows of a scanned membership list.

    A board list is typeset as a list, not a ruled table: a name, sometimes a
    capacity beside it, sometimes the officer representing a corporate seat.
    There are no figures to qualify a row with, so the test is that the row
    opens with something name-shaped and does not read as a sentence.
    """
    rows = []
    for y, cells in _page_cell_lines(page):
        if not (top < y < bottom):
            continue
        cells = [c.strip() for c in cells if c.strip()]
        if not cells:
            continue
        # "MM." printed once before a column of names is its own cell; it is a
        # label for the list, not a member.
        if _HONORIFIC_ONLY.match(cells[0]) and len(cells) > 1:
            cells = [f"{cells[0]} {cells[1]}"] + cells[2:]
        # A capacity printed tight against the name is not split off by the
        # column-gap rule: "Seifeddine NAGHMOUCHI Representant l'Etat" arrives
        # as one cell. Cutting on the capacity keeps it out of the name.
        m = _ROLE_TAIL.search(cells[0])
        if m and m.start() > 2:
            cells = [cells[0][:m.start()].strip(), cells[0][m.start():].strip()] + cells[1:]
        name = cells[0]
        if len(name) < 3 or len(name) > 70 or len(" ".join(cells)) > 160:
            continue
        if _PROSE.search(" ".join(cells)):
            continue
        # A trailing full stop marks a sentence, but not an acronym: "C.N.S.S."
        # and "E.T.A.P." are corporate board members and must survive.
        if re.search(r"[a-zà-þ]{3,}[.,;]$", name):
            continue
        # Name-shaped: a capitalised word, an all-caps word, or a dotted
        # acronym - state bodies sit on these boards as "E.T.A.P." and "B.C.T.".
        if not re.search(r"[A-ZÀ-Þ][a-zà-þ'’-]|[A-ZÀ-Þ]{2,}|(?:[A-ZÀ-Þ]\.){2,}", name):
            continue
        if is_table_noise_line(name):
            continue
        rows.append(cells)
    return rows


def is_table_noise_line(text: str) -> bool:
    """Page furniture that would otherwise read as a member or a holder."""
    t = norm(text)
    return (
        not t
        or t.isdigit()
        or _any(t, "rapport annuel", "sommaire", "page", "exercice clos",
                "etats financiers", "commissaires aux comptes", "note aux",
                "controleur", "siege social", "capital social")
    )


def tables_from_cell_lines(page, heads, last_heading: str, page_bottom: float):
    """Find tables on a page that reports no ruling lines at all.

    A scanned page has no vector graphics, so `find_tables` sees nothing and the
    ordinary path - which starts from a ruled table and only *fills* a
    borderless body - never runs. Tables are located from their headings
    instead, each running down to the next heading on the page.

    Returns (kind, heading, header, rows) tuples. A region that yields no
    qualifying rows is dropped, which is what keeps a heading with nothing
    beneath it from becoming an empty table.
    """
    out = []
    if not heads:
        heads = []
    bounds = [h[0] for h in heads] + [page_bottom]
    for i, (y, heading) in enumerate(heads):
        kind = classify_from_heading(heading)
        if kind is None:
            continue
        bottom = bounds[i + 1] if i + 1 < len(bounds) else page_bottom
        if bottom <= y:
            bottom = page_bottom
        if kind in _OCR_FIGURE_KINDS:
            rows = synth_rows_from_text(page, y, bottom)
            header = _header_line(page, y, bottom) or ["Actionnaires", "Nombre", "%"]
        elif kind in _OCR_ROSTER_KINDS:
            rows = _roster_rows(page, y, bottom)
            header = _ROSTER_HEADER
        else:
            continue
        if not rows:
            continue
        out.append((kind, heading, header, rows))

    # A scanned page can also carry a genuine column header, which is stronger
    # evidence than the heading. Those are picked up by the ordinary classifier.
    claimed = [(h[0], b) for h, b in zip(heads, bounds[1:])] if heads else []
    for y, cells in _page_cell_lines(page):
        cells = [c.strip() for c in cells if c.strip()]
        if len(cells) < 2 or any(t <= y <= b for t, b in claimed):
            continue
        above = [h for h in heads if h[0] < y]
        heading = above[-1][1] if above else last_heading
        kind = classify_table(cells, heading)
        if kind is None or kind not in _OCR_FIGURE_KINDS:
            continue
        below = [h[0] for h in heads if h[0] > y + 1]
        rows = synth_rows_from_text(page, y, below[0] if below else page_bottom)
        if rows:
            out.append((kind, heading, cells, rows))
    return out


def _header_line(page, top: float, bottom: float) -> list[str] | None:
    """The column header inside a region, where the filing prints one."""
    for y, cells in _page_cell_lines(page):
        if not (top < y < bottom):
            continue
        cells = [c.strip() for c in cells if c.strip()]
        if cells and _any(norm(" ".join(cells)), "actionnaire", "nombre d'actions",
                          "nbre d'actions", "societe", "filiale"):
            return cells
    return None


def _release(page) -> None:
    """Drop a page's cached objects once we are done with it.

    pdfplumber keeps every parsed character, line and rect of every page it has
    touched, so reading a long document end to end grows without bound. A
    500-page annual report - most of it financial statements - took a worker to
    11.4 GB and had it killed, which then hung the whole pool waiting for a
    result that was never coming. Nothing here looks back at an earlier page,
    so the cache can go as soon as the page is processed.
    """
    for release in ("flush_cache", "close"):
        try:
            getattr(page, release)()
        except Exception:
            pass


def extract_tables(pdf, max_pages: int | None = None,
                   from_words: bool = False) -> list[FoundTable]:
    """Walk a pdfplumber PDF and return every table we can classify.

    ``from_words`` switches to reconstructing tables from word positions alone,
    for documents that have been OCR'd and so carry no ruling lines. It is a
    parameter rather than a fallback on an empty ``find_tables`` so that
    digitally filed documents keep their existing, validated behaviour
    unchanged.
    """
    found: list[FoundTable] = []
    last_heading = ""          # carries across pages for tables that continue
    doc_as_of: str | None = None
    pages = pdf.pages if max_pages is None else pdf.pages[:max_pages]
    for idx, page in enumerate(pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        # Cheap text test first: skip pages that cannot hold a table we want.
        # Headings still need tracking across skipped pages, but only from text.
        if not _RELEVANT_PAGE.search(text):
            for _, h in page_headings(text):
                last_heading = h
            _release(page)
            continue

        heads = ocr_headings(page) if from_words else page_headings(page)
        try:
            tables = page.find_tables()
        except Exception:
            tables = []

        table_tops = sorted(t.bbox[1] for t in tables)
        page_bottom = float(page.height)

        if from_words:
            for kind, heading, header, rows in tables_from_cell_lines(
                page, heads, last_heading, page_bottom
            ):
                as_of = (find_as_of_date(heading) or find_as_of_date(text[:600])
                         or doc_as_of)
                if as_of and not doc_as_of:
                    doc_as_of = as_of
                found.append(
                    FoundTable(
                        kind=kind,
                        page=idx + 1,
                        heading=heading.strip(),
                        as_of=as_of,
                        header=header,
                        rows=rows,
                        synthesized=True,
                    )
                )
            if heads:
                last_heading = heads[-1][1]
            _release(page)
            continue

        for tf in tables:
            try:
                tbl = tf.extract()
            except Exception:
                continue
            if _is_noise(tbl):
                continue
            rows = [[_clean_cell(c) for c in row] for row in tbl]
            header = rows[0]
            body = rows[1:]

            # Bind the table to the nearest numbered heading *above* it. This is
            # what separates s2.4.1 from s2.4.2 from s2.4.3 when all three sit on
            # one page.
            top = tf.bbox[1]
            above = [h for h in heads if h[0] < top]
            heading = above[-1][1] if above else last_heading

            kind = classify_table(header, heading)

            # Headers sometimes wrap onto a second ruled row ("Nombre" /
            # "d'actions"), leaving the first row too sparse to classify. Fold
            # in following rows only while classification is still failing:
            # folding unconditionally would consume board tables whole, since
            # their rows contain no figures to mark where the header ends.
            folded = 0
            while kind is None and body and folded < 2:
                header = [f"{a} {b}".strip() for a, b in
                          itertools.zip_longest(header, body[0], fillvalue="")]
                body = body[1:]
                folded += 1
                kind = classify_table(header, heading)

            if kind is None:
                # A heading may be typeset beside rather than above its table.
                for _, h in heads:
                    kind = classify_table(header, h)
                    if kind:
                        heading = h
                        break
            if kind is None:
                continue
            rows = [header] + body

            data_rows = rows[1:]
            synthesized = False
            # Borderless body: the ruled table held only the header. Recover the
            # rows from the text between this table and whatever follows it.
            if not any(any(to_number(c) is not None for c in r) for r in data_rows):
                region_top = tf.bbox[3]
                below = [t for t in table_tops if t > region_top + 1]
                next_head = [h[0] for h in heads if h[0] > region_top + 1]
                region_bottom = min(
                    [b for b in (below[:1] + next_head[:1]) if b] or [page_bottom]
                )
                synth = synth_rows_from_text(page, region_top, region_bottom)
                if synth:
                    data_rows = synth
                    synthesized = True

            as_of = find_as_of_date(heading) or find_as_of_date(text[:600]) or doc_as_of
            if as_of and not doc_as_of:
                doc_as_of = as_of
            found.append(
                FoundTable(
                    kind=kind,
                    page=idx + 1,
                    heading=heading.strip(),
                    as_of=as_of,
                    header=header,
                    rows=data_rows,
                    synthesized=synthesized,
                )
            )
        if heads:
            last_heading = heads[-1][1]
        _release(page)
    return found
