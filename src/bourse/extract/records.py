"""Turn classified tables into typed, provenance-carrying records.

Every function here returns plain dicts with a common provenance block, so that
any cell in the final dataset can be traced back to a page of a named CMF
filing. Values that could not be read are left ``None`` rather than guessed:
downstream code treats missing weights as missing, never as zero.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from .tables import FoundTable, norm, strip_accents, to_number

# --------------------------------------------------------------------------
# shared helpers
# --------------------------------------------------------------------------

# Trailing footnote markers on names: "M. Hakim DOGHRI(1)", "Meninx Holding (2)".
_FOOTNOTE = re.compile(r"\s*\(\s*\d{1,2}\s*\)\s*$")
_TITLES = re.compile(
    r"^(mm\.?|messieurs|mesdames|m\.|m|mr\.?|mme\.?|mlle\.?|dr\.?|pr\.?|me\.?|"
    r"monsieur|madame)\s+", re.I
)

# Rows of the aggregate capital-structure table, which must never be read as
# named holders if they leak into a blockholder table.
_CATEGORY_ROW = re.compile(
    r"^(total|sous.total|public|autres|divers|flottant|"
    r"personnes?\s+(morales?|physiques?)|"
    r"participations?\s+|ayant\s+|actionnaires?\s+(tunisiens?|etrangers?)|"
    r"\d+\s*/|rompus)",
    re.I,
)


# A footnote marker *leading* a label: "*** Membre independant", "(2) Nomination
# par l'AGO du 30 avril 2019", "* Personnes Morales :". Markers that attach to a
# real name trail it ("M. Hakim DOGHRI(1)"), so a leading one always introduces
# the legend below a table rather than a row of it.
_LEADING_MARKER = re.compile(r"^\s*(?:\*+|\(\s*\d{1,2}\s*\))\s*:?\s*")


def is_footnote_legend(name: str) -> bool:
    """True for the explanatory lines printed beneath a table.

    Every table in the corpus that uses asterisks to annotate its rows repeats
    those asterisks below it against a sentence explaining them. Those lines sit
    in the same borderless text block as the rows, so row recovery picks them up
    and they would otherwise enter the network as board members with names like
    "*** Membre representant les petits actionnaires".
    """
    s = (name or "").strip()
    return bool(_LEADING_MARKER.match(s)) and bool(_LEADING_MARKER.sub("", s).strip())


def clean_name(s: str) -> str:
    s = _FOOTNOTE.sub("", (s or "").strip())
    s = re.sub(r"\s+", " ", s)
    return s.strip(" .,;:-")


def strip_title(s: str) -> tuple[str, str | None]:
    """Split an honorific off a personal name. Returns (name, title)."""
    m = _TITLES.match(s or "")
    if not m:
        return clean_name(s), None
    return clean_name(s[m.end():]), m.group(1).rstrip(".").lower()


# Table furniture that survives cell extraction and would otherwise become a
# node: column labels, footer words, and stray mandate ranges ("2012-2014*").
_NOISE_LABEL = re.compile(
    r"^(adresse|fonction|onction|qualite|mandat|mandats|nom|prenom|nom et prenom|"
    r"membre|membres|administrateur|administrateurs|administrateur s|"
    r"representant|represente|represente par|surveillance|communication|"
    r"observation|observations|presence|aucun|aucune|neant|par|et|ou|"
    r"total|totaux|sous total|date|annee|exercice|nombre|montant|"
    r"designation|libelle|rubrique|nature|objet|activite|secteur|"
    r"\d{4}\s*[-/]\s*\d{2,4}\*?|n/?a|\W+)$"
)


def is_table_noise(name: str) -> bool:
    """True for leftover header, footer or label text that is not an entity."""
    if is_footnote_legend(name):
        return True
    n = norm(name).strip(" .:*()-")
    if not n or len(n) < 2:
        return True
    if _NOISE_LABEL.match(n):
        return True
    # A bare year or year-range is a mandate cell, never a name.
    if re.fullmatch(r"[\d\s./*-]+", n):
        return True
    return False


def is_category_row(name: str) -> bool:
    n = norm(name)
    return bool(_CATEGORY_ROW.match(_LEADING_MARKER.sub("", n))) or is_table_noise(name)


def first_label(cells: list[str]) -> tuple[int, str]:
    """Return (index, text) of the row's label cell.

    Tables frequently begin with one or more empty spacer columns, so the label
    is not reliably ``cells[0]``: it is the first cell holding text that is not
    purely a figure.
    """
    for i, c in enumerate(cells):
        txt = clean_name(c)
        if txt and to_number(c) is None:
            return i, txt
    return -1, ""


def _numbers_in_row(cells: list[str]) -> list[tuple[int, float, bool]]:
    """Return (column_index, value, had_percent_sign) for numeric cells."""
    out = []
    for i, c in enumerate(cells):
        v = to_number(c)
        if v is not None:
            out.append((i, v, "%" in (c or "")))
    return out


def split_pct(
    cells: list[str], skip_cols: set[int] | None = None
) -> tuple[float | None, float | None, float | None]:
    """Pull (percent, shares, amount) out of a ragged shareholder row.

    Column positions are unreliable: pdfplumber emits empty spacer columns when
    a table's ruling lines do not align. We therefore identify the percentage by
    its ``%`` sign (or, failing that, as the trailing value that could be one)
    and read share count and nominal amount as the two largest remaining
    figures, in document order.
    """
    nums = _numbers_in_row(cells)
    if skip_cols:
        nums = [n for n in nums if n[0] not in skip_cols]
    if not nums:
        return None, None, None

    pct = None
    pct_idx = None
    flagged = [n for n in nums if n[2]]
    if flagged:
        pct_idx, pct, _ = flagged[-1]
    else:
        # No '%' sign: the last value in 0..100 with a fractional part is the
        # best candidate. Integers are left alone - they are share counts.
        for i, v, _ in reversed(nums):
            if 0 <= v <= 100 and abs(v - round(v)) > 1e-9:
                pct_idx, pct = i, v
                break

    rest = [n for n in nums if n[0] != pct_idx]
    shares = rest[0][1] if rest else None
    amount = rest[1][1] if len(rest) > 1 else None
    return pct, shares, amount


def _prov(doc: dict, ft: FoundTable, **extra: Any) -> dict:
    p = {
        "doc_node_key": doc.get("node_key"),
        "doc_type": doc.get("doc_type"),
        "doc_title": doc.get("title"),
        "doc_url": doc.get("pdf_url") or doc.get("node_url"),
        "filing_date": doc.get("filing_date"),
        "page": ft.page,
        "section_heading": ft.heading,
        "as_of": ft.as_of,
    }
    p.update(extra)
    return p


# --------------------------------------------------------------------------
# ownership
# --------------------------------------------------------------------------


def parse_blockholders(ft: FoundTable, doc: dict) -> list[dict]:
    """Named shareholders and their stake (s2.4.2 and equivalents)."""
    out = []
    for row in ft.rows:
        cells = list(row)
        li, name = first_label(cells)
        if not name or len(name) < 2 or is_category_row(name):
            continue
        pct, shares, amount = split_pct(cells)
        if pct is None and shares is None:
            continue
        out.append(
            {
                "holder_name_raw": name,
                "pct_capital": pct,
                "n_shares": shares,
                "nominal_amount_tnd": amount,
                "relation": "block_ownership",
                **_prov(doc, ft),
            }
        )
    return out


def parse_director_holdings(ft: FoundTable, doc: dict) -> list[dict]:
    """Stakes held by board/management members (s2.4.3)."""
    rows = parse_blockholders(ft, doc)
    for r in rows:
        r["relation"] = "director_ownership"
    return rows


def parse_capital_structure(ft: FoundTable, doc: dict) -> list[dict]:
    """Aggregate ownership categories: resident/foreign, legal/natural person.

    This table carries a count-of-shareholders column that the ragged-row
    heuristic would otherwise mistake for a share count, so columns are mapped
    from the header here and the count column is excluded explicitly.
    """
    hdr = [norm(h) for h in ft.header]
    if ft.synthesized:
        # Rows came from text, so they do not share the ruled header's column
        # indices. These filings print the columns in a fixed order:
        # label, number of shareholders, number of shares, amount, percentage.
        i_holders, i_shares, i_amount = 1, 2, 3
    else:
        i_holders = _col(hdr, "nombre d'actionnaires", "nombre d actionnaires",
                         "nbre d'actionnaires")
        i_shares = _col(hdr, "total actions", "nombre d'actions", "nombre d actions",
                        "nbre d'actions")
        i_amount = _col(hdr, "montant")

    out = []
    for row in ft.rows:
        cells = list(row)
        _, label = first_label(cells)
        if not label:
            continue
        skip = {i for i in (i_holders,) if i is not None}
        pct, shares, amount = split_pct(cells, skip_cols=skip)
        if i_shares is not None and i_shares < len(cells):
            shares = to_number(cells[i_shares]) if to_number(cells[i_shares]) is not None else shares
        if i_amount is not None and i_amount < len(cells):
            amount = to_number(cells[i_amount]) if to_number(cells[i_amount]) is not None else amount
        n_holders = (
            to_number(cells[i_holders]) if i_holders is not None and i_holders < len(cells) else None
        )
        if pct is None and shares is None:
            continue
        out.append(
            {
                "category_raw": label,
                "pct_capital": pct,
                "n_shares": shares,
                "n_holders": n_holders,
                "nominal_amount_tnd": amount,
                **_prov(doc, ft),
            }
        )
    return out


_SUB_PCT = re.compile(r"(\d{1,3}[.,]\d+|\d{1,3})\s*%")


def parse_subsidiaries(ft: FoundTable, doc: dict) -> list[dict]:
    """Group participations: issuer -> subsidiary, with the direct stake."""
    hdr = [norm(h) for h in ft.header]
    # Header words wrap mid-token in narrow columns ("participatio n directe"),
    # so match the space-free form.
    def _sq(s: str) -> str:
        return re.sub(r"[\s'.-]+", "", s)

    pct_cols = [
        i for i, h in enumerate(hdr)
        if any(k in _sq(h) for k in ("participation", "detention", "detenu", "%de"))
    ]
    out = []
    for row in ft.rows:
        cells = list(row)
        _, name = first_label(cells)
        if not name or is_category_row(name):
            continue
        pct = None
        for i in pct_cols:
            if i < len(cells):
                pct = to_number(cells[i])
                if pct is not None:
                    break
        if pct is None:
            pct, _, _ = split_pct(cells)
        if pct is None:
            continue
        out.append(
            {
                "subsidiary_name_raw": name,
                "pct_capital": pct,
                "relation": "group_participation",
                **_prov(doc, ft),
            }
        )
    return out


# --------------------------------------------------------------------------
# boards
# --------------------------------------------------------------------------

_MANDATE = re.compile(r"(19|20)(\d{2})\s*[-/–]\s*(?:(19|20))?(\d{2})")


def parse_mandate(s: str) -> tuple[int | None, int | None]:
    """Read a mandate term such as '2023-2025' or '2024/26'."""
    if not s:
        return None, None
    m = _MANDATE.search(s)
    if not m:
        y = re.search(r"(19|20)\d{2}", s)
        return (int(y.group(0)), None) if y else (None, None)
    start = int(m.group(1) + m.group(2))
    end_c = m.group(3) or m.group(1)
    end = int(end_c + m.group(4))
    if end < start:
        end += 100
    return start, end


def _col(hdr: list[str], *names: str) -> int | None:
    for i, h in enumerate(hdr):
        for n in names:
            if n in h:
                return i
    return None


def parse_board(ft: FoundTable, doc: dict) -> list[dict]:
    """Board membership, including legal-person seats and their representatives."""
    hdr = [norm(h) for h in ft.header]
    i_mem = _col(hdr, "membre", "nom et prenom", "administrateur") or 0
    i_rep = _col(hdr, "represente par", "representant")
    i_qual = _col(hdr, "qualite", "fonction")
    i_mand = _col(hdr, "mandat", "echeance", "duree")
    i_addr = _col(hdr, "adresse", "nationalite", "pays")

    out = []
    for row in ft.rows:
        cells = list(row)
        raw = clean_name(cells[i_mem]) if i_mem < len(cells) else ""
        if not raw:
            _, raw = first_label(cells)
        if not raw or is_category_row(raw) or len(raw) < 3:
            continue
        rep_raw = clean_name(cells[i_rep]) if i_rep is not None and i_rep < len(cells) else ""
        # "Lui-Meme" / "Elle-meme" means the seat is held by a natural person.
        if norm(rep_raw) in {"lui-meme", "lui meme", "elle-meme", "elle meme", "-", ""}:
            rep_raw = ""
        role = clean_name(cells[i_qual]) if i_qual is not None and i_qual < len(cells) else ""
        mandate = cells[i_mand] if i_mand is not None and i_mand < len(cells) else ""
        start, end = parse_mandate(mandate)
        name, title = strip_title(raw)
        out.append(
            {
                "member_name_raw": name,
                "member_title": title,
                "member_is_legal_person": title is None and bool(rep_raw),
                "represented_by_raw": strip_title(rep_raw)[0] if rep_raw else None,
                "role_raw": role or None,
                "mandate_raw": clean_name(mandate) or None,
                "mandate_start": start,
                "mandate_end": end,
                "country": clean_name(cells[i_addr]) if i_addr is not None and i_addr < len(cells) else None,
                "relation": "board_seat",
                **_prov(doc, ft),
            }
        )
    return out


# --------------------------------------------------------------------------
# interlocks and outside executive roles
# --------------------------------------------------------------------------

# Role labels used in Tunisian corporate filings. Cell text arrives with its
# line breaks flattened, so "COFITE SICAF Directeur General : X" has no
# separator before the second role; anchoring on these keywords recovers it.
_ROLE_WORDS = (
    r"president(?:e)?(?:\s+directeur\s+general(?:e)?|\s+du\s+conseil"
    r"(?:\s+d['\s]administration)?|\s+du\s+comite[^:]{0,40}|\s+de[^:]{0,30})?",
    r"vice[-\s]?president(?:e)?(?:[^:]{0,40})?",
    r"administrat(?:eur|rice)(?:\s+(?:unique|independant(?:e)?|delegue(?:e)?|"
    r"representant[^:]{0,30}|et\s+membre[^:]{0,40}))?",
    r"directeur\s+general(?:\s+adjoint)?", r"directrice\s+general(?:e)?(?:\s+adjointe)?",
    r"gerant(?:e)?(?:\s+de\s+societe)?", r"membre(?:\s+du[^:]{0,40})?",
    r"censeur", r"secretaire\s+general(?:e)?(?:[^:]{0,30})?",
    r"pdg", r"dg", r"president(?:e)?\s+du\s+directoire", r"liquidateur",
)
_ROLE_ANCHOR = re.compile(
    r"(?:^|[-•·;,]|\s)\s*((?:" + "|".join(_ROLE_WORDS) + r"))\s*:\s*",
    re.I,
)

# Fallback for cells that do use explicit separators before an arbitrary label.
_ROLE_SPLIT = re.compile(r"(?:^|[-•·;\n]|\s{2,})\s*([^:;\n]{3,70}?)\s*:\s*")

_NEANT = {"neant", "none", "-", "aucun", "aucune", "n/a", "na"}


def _split_firms(blob: str) -> list[str]:
    """Split a run of firm names separated by '/', ',' or ' et '."""
    parts = re.split(r"\s*[/|]\s*|\s*,\s*|\s+et\s+", blob)
    out = []
    for p in parts:
        p = clean_name(p)
        # Drop trailing descriptors: "Telnet (Technologie)" -> "Telnet".
        p = re.sub(r"\s*\([^)]*\)\s*$", "", p).strip()
        if len(p) < 2 or norm(p) in _NEANT:
            continue
        if is_category_row(p):
            continue
        out.append(p)
    return out


def parse_role_blob(blob: str) -> list[tuple[str | None, str]]:
    """Parse a mandates cell into (role, firm) pairs."""
    blob = re.sub(r"\s+", " ", blob or "").strip()
    if not blob or norm(blob) in _NEANT:
        return []
    pairs: list[tuple[str | None, str]] = []
    # Prefer keyword-anchored splits; they survive flattened line breaks. Fall
    # back to generic "label :" splitting only if no known role word appears.
    matches = list(_ROLE_ANCHOR.finditer(strip_accents(blob).lower()))
    if matches:
        # Re-align spans onto the original (accented) text: strip_accents is
        # length-preserving, so offsets carry over unchanged.
        spans = [(m.start(1), m.end(1), m.end()) for m in matches]
    else:
        spans = [(m.start(1), m.end(1), m.end()) for m in _ROLE_SPLIT.finditer(blob)]
    if not spans:
        # No explicit role label: treat the whole cell as a list of firms.
        return [(None, f) for f in _split_firms(blob)]
    matches = spans
    for i, (rs, re_, after) in enumerate(matches):
        role = clean_name(blob[rs:re_]).lstrip("-–• ")
        end = matches[i + 1][0] if i + 1 < len(matches) else len(blob)
        for firm in _split_firms(blob[after:end]):
            pairs.append((role or None, firm))
    return pairs


def parse_interlocks(ft: FoundTable, doc: dict) -> list[dict]:
    """Directorships the issuer's board members declare in *other* companies."""
    hdr = [norm(h) for h in ft.header]
    i_mem = _col(hdr, "membre", "nom et prenom", "administrateur") or 0
    i_blob = _col(hdr, "mandat", "autres societes", "societe")
    if i_blob is None or i_blob == i_mem:
        i_blob = 1 if len(hdr) > 1 else None
    if i_blob is None:
        return []

    out = []
    for row in ft.rows:
        cells = list(row)
        if i_blob >= len(cells):
            continue
        mem_raw = clean_name(cells[i_mem]) if i_mem < len(cells) else ""
        if not mem_raw:
            _, mem_raw = first_label(cells)
        person, title = strip_title(mem_raw)
        if not person or is_category_row(person):
            continue
        for role, firm in parse_role_blob(cells[i_blob]):
            out.append(
                {
                    "person_name_raw": person,
                    "person_title": title,
                    "other_firm_name_raw": firm,
                    "role_raw": role,
                    "relation": "declared_mandate",
                    **_prov(doc, ft),
                }
            )
    return out


def parse_executives(ft: FoundTable, doc: dict) -> list[dict]:
    """Executive roles held outside the issuer (s5.1.3 and equivalents)."""
    rows = parse_interlocks(ft, doc)
    for r in rows:
        r["relation"] = "declared_executive_role"
    return rows


PARSERS = {
    "blockholders": parse_blockholders,
    "director_holdings": parse_director_holdings,
    "capital_structure": parse_capital_structure,
    "subsidiaries": parse_subsidiaries,
    "board": parse_board,
    "interlocks": parse_interlocks,
    "executives": parse_executives,
}


def parse_all(tables: Iterable[FoundTable], doc: dict) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {k: [] for k in PARSERS}
    for ft in tables:
        fn = PARSERS.get(ft.kind)
        if fn is None:
            continue
        try:
            out[ft.kind].extend(fn(ft, doc))
        except Exception:  # a malformed table must not abort a whole document
            continue
    return out
