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


def _cell_gap_threshold(
    gaps: list[float],
    gap_factor: float = 2.2,
    min_gap: float = 4.0,
    jump_ratio: float = 3.0,
) -> float:
    """Inter-word gap above which a break separates two *columns*, not words.

    Scaling the line's median gap is stable while a line has many words, but a
    short table row does not: ``PIRECO 750 000 750 000 3,00%`` contributes five
    gaps, three of which are column breaks, so the median lands on a column gap
    and the threshold it yields exceeds every gap on the line. The row then
    survives as a single cell, and the two adjacent figures are read as one
    number - a share count of 750,000,750,000.

    Column gaps are sharply bimodal against word gaps, so look for that split
    first: sort the gaps and cut at the largest ratio step. The step must be a
    real jump rather than the ordinary variation of justified spacing, which is
    what ``jump_ratio`` tests; prose lines fail it and fall back to the median
    rule.
    """
    pos = sorted(g for g in gaps if g > 0)
    if not pos:
        return min_gap
    median = pos[len(pos) // 2]
    fallback = max(min_gap, median * gap_factor)

    best_lo = best_hi = best_ratio = 0.0
    for lo, hi in zip(pos, pos[1:]):
        ratio = hi / lo
        if ratio > best_ratio:
            best_ratio, best_lo, best_hi = ratio, lo, hi
    if best_ratio >= jump_ratio and best_hi >= min_gap:
        # Cut strictly above the widest word gap, so every gap in the upper
        # cluster splits and none in the lower one does.
        return best_lo
    return fallback


def _is_glue(left: str, right: str, gap: float, glue_gap: float) -> bool:
    """True when two words are one token that the extractor split in two.

    Requires digits on both sides of the gap as well as a gap too narrow to be a
    space. Restricting it to figures is what keeps the rule from welding company
    names together: a name split across a hairline gap still reads correctly
    with the space left in, whereas a figure does not.
    """
    return bool(gap <= glue_gap and left and right
                and left[-1].isdigit() and right[0].isdigit())


def _page_cell_lines(
    page, gap_factor: float = 2.2, min_gap: float = 4.0, glue_gap: float = 0.6
):
    """Reconstruct lines as *cells*, splitting on inter-word gaps.

    Flattening a line to a single string loses the column structure, and that
    loss is not recoverable by regex: "975 000 975 000" is equally readable as
    one figure or as two. Word coordinates settle it - a column break is a gap
    much wider than the line's ordinary word spacing.

    Three gap sizes, therefore, not two. Beyond the column threshold a new cell
    begins. Below ``glue_gap`` the two words are not separated on the page at
    all: pdfplumber has cut one token in two, which it does inside figures often
    enough to matter ("2 666 921" arriving as "2", "6", "66", "921" with a
    zero-width gap between the "6" and the "66"). Joining those without a space
    is what keeps such a figure from being read as 2. Anything between the two
    is an ordinary word space.

    Gap width alone cannot carry that last decision, which is why ``_is_glue``
    also looks at what sits either side of it. Spacing is set per font, not per
    corpus: on one filing's shareholder table a word space measures 0.40pt and a
    space *inside* a figure measures 0.93pt - the word space is the narrower of
    the two, and one pair of glyphs in a company name overlaps outright at
    -0.06pt. No absolute width separates "COTIF SICAR" from a split figure
    there. What does separate them is that a figure broken in two has digits on
    both sides of the break.
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
            threshold = _cell_gap_threshold(gaps, gap_factor, min_gap)
        else:
            threshold = min_gap
        cells, cur = [], ws[0]["text"]
        for b, gap in zip(ws[1:], gaps):
            if gap > threshold:
                cells.append(cur)
                cur = b["text"]
            else:
                glued = _is_glue(cur, b["text"], gap, glue_gap)
                cur += ("" if glued else " ") + b["text"]
        cells.append(cur)
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


def extract_tables(pdf, max_pages: int | None = None) -> list[FoundTable]:
    """Walk a pdfplumber PDF and return every table we can classify."""
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
            continue

        heads = page_headings(page)
        try:
            tables = page.find_tables()
        except Exception:
            tables = []

        table_tops = sorted(t.bbox[1] for t in tables)
        page_bottom = float(page.height)

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
    return found
