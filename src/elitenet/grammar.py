"""Shared French grammar primitives for event extraction.

The gazette's language is highly formulaic, so a rule layer carries most of the
work and -- unlike a statistical tagger -- a reviewer can read the rule that
produced any given record. Every pattern here is keyed by a ``pattern_id`` that
is stamped onto the events it generates.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from functools import lru_cache

from .paths import load_config

# Uppercase and lowercase letter classes covering the accented French range.
U = r"A-ZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÑÒÓÔÕÖØÙÚÛÜÝ"
L = r"a-zà-öø-ÿ"

TITLE = (r"(?:Monsieur|Madame|Mademoiselle|Messieurs|Mesdames|"
         r"M\.|Mme|Mlle|Mr\.?|Dr\.?|Me\.?|Maître)")
PARTICLE = r"(?:ben|bent|bin|el|al|ould|ouled|abou|abd|abdel|si|sidi|bel|bou|ibn|ebn)"
_TOK = rf"[{U}][{U}{L}'’\.\-]*"
NAME = rf"(?:{_TOK}|{PARTICLE})(?:[ \-](?:{_TOK}|{PARTICLE})){{0,4}}"
SPOUSE = rf"(?:\s+(?:[ée]pouse|[ée]p\.|n[ée]e|veuve|vve)\s+(?P<spouse>{NAME}))?"

RE_PERSON = re.compile(rf"{TITLE}\s+(?P<name>{NAME}){SPOUSE}", re.UNICODE)

# Words that follow a title in boilerplate but are not names. Without this the
# label "M." in "M. Siege social" and similar produce spurious people.
NAME_STOPWORDS = {
    "SIEGE", "CAPITAL", "DENOMINATION", "OBJET", "DUREE", "FISC", "F", "GERANCE",
    "ADRESSE", "RAISON", "FORME", "SOCIETE", "STE", "EXERCICE", "ASSEMBLEE",
    "CONSEIL", "ADMINISTRATION", "TUNIS", "MATRICULE", "NOMBRE", "VALEUR",
    "AFFECTATION", "DEPOT", "DELAI", "MODALITE", "CONDITIONS", "PROJET",
    "TRIBUNAL", "GREFFE", "RECETTE", "QUITTANCE", "MONSIEUR", "MADAME",
    "ARTICLE", "ART", "NOTA", "REGISTRE", "NATIONAL", "ENTREPRISES",
}

MONTHS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "decembre": 12,
    # OCR and abbreviation variants
    "janiver": 1, "fervier": 2, "fevier": 2, "avirl": 4, "jullet": 7,
    "juilet": 7, "aoutt": 8, "setpembre": 9, "octbre": 10, "novmbre": 11,
    "decmbre": 12, "janv": 1, "fev": 2, "sept": 9, "oct": 10, "nov": 11,
    "dec": 12,
}
_MONTH_ALT = "|".join(sorted(MONTHS, key=len, reverse=True))

RE_DATE_TXT = re.compile(
    r"\b(?P<d>1er|1ere|0?[1-9]|[12][0-9]|3[01])\s*(?:er|ere)?\s+"
    r"(?P<m>" + _MONTH_ALT + r")\s+(?P<y>19[5-9][0-9]|20[0-4][0-9])\b",
    re.IGNORECASE,
)
RE_DATE_NUM = re.compile(
    r"\b(?P<d>0?[1-9]|[12][0-9]|3[01])\s*[/.]\s*(?P<m>0?[1-9]|1[0-2])\s*[/.]\s*"
    r"(?P<y>19[5-9][0-9]|20[0-4][0-9])\b"
)

# A date as it appears inside a clause. Used wherever a clause anchor is
# followed by "du <date>", so the capture cannot drift onto ordinary prose.
DATE_CORE = (r"(?:(?:1er|1ere|\d{1,2})\s*(?:er|ere)?\s+[A-Za-zÀ-ÿ]{3,12}\s+\d{4}"
             r"|(?:1er|\d{1,2})\s*[/.]\s*\d{1,2}\s*[/.]\s*\d{4})")

# --- dated clause anchors: which of the several dates in a block is which ---
RE_ACT_DATE = re.compile(
    r"(?:suivant|selon|aux?\s+termes?\s+d[eu]|d'apr[èe]s)[^\n]{0,200}?"
    r"en\s+date\s+du\s+(?P<date>" + DATE_CORE + r")", re.IGNORECASE)
RE_ACT_DATE_ALT = re.compile(
    r"(?:P\.?V\.?|proc[èe]s[- ]verbal|acte|statuts?|assembl[ée]e[^\n]{0,40}|"
    r"conseil\s+d'administration)[^\n]{0,120}?"
    r"(?:en\s+date\s+du|du|r[ée]unie?\s+le)\s+(?P<date>" + DATE_CORE + r")", re.IGNORECASE)
RE_REG_DATE = re.compile(
    r"enregistr[ée]s?\s+(?:[àa]\s+la\s+|au\s+)?(?:recette|R\.?E\.?A\.?S)"
    r"[^\n]{0,140}?\s(?:le|en\s+date\s+du)\s+(?P<date>" + DATE_CORE + r")", re.IGNORECASE)
RE_FILING_DATE = re.compile(
    r"d[ée]pos[ée]s?\s+au\s+greffe[^\n]{0,160}?\s(?:le|en\s+date\s+du)\s+"
    r"(?P<date>" + DATE_CORE + r")", re.IGNORECASE)
RE_EFFECTIVE_DATE = re.compile(
    r"(?:prend\s+effet\s+)?[àa]\s+compter\s+du\s+(?P<date>" + DATE_CORE + r")", re.IGNORECASE)

# --- firm identifiers and figures ---
RE_MF = re.compile(
    r"(?:M(?:at)?\.?\s*Fisc\.?|\bMF\b|matricule\s+fiscal)\s*[:.]?\s*"
    r"(?P<mf>\d{6,8}\s*[/\s]?[A-Z]{1,4}(?:\s*[/\s]\s*[A-Z])*(?:\s*[/\s]\s*\d{3})?)",
    re.IGNORECASE)
RE_CAPITAL = re.compile(
    r"[Aa]u\s+capital\s+(?:social\s+)?(?:de\s+)?(?P<amount>[\d][\d\s.,]{2,20})\s*"
    r"(?P<cur>dinars?|DT|D\b)", re.IGNORECASE)
RE_MANDATE_YEARS = re.compile(
    r"pour\s+une\s+(?:p[ée]riode|dur[ée]e)\s+de\s+(?P<n>un|deux|trois|quatre|cinq|six|\d{1,2})\s+"
    r"(?:ans?|ann[ée]es?|exercices?)", re.IGNORECASE)
RE_MANDATE_EXERCICES = re.compile(
    r"pour\s+(?:une\s+dur[ée]e\s+de\s+)?(?P<n>un|deux|trois|quatre|cinq|six|\d{1,2})\s+"
    r"exercices?\s+sociaux", re.IGNORECASE)

WORD_NUMBERS = {"un": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6}

# --- representation: a legal person acting through a named individual ---
RE_REPRESENTED = re.compile(
    rf"(?P<org>(?:La\s+)?(?:Soci[ée]t[ée]|STE|Ste|SARL|SA)\s+[^,\n]{{2,80}}?)\s+"
    rf"repr[ée]sent[ée]e?\s+par\s+{TITLE}?\s*(?P<name>{NAME})", re.IGNORECASE)

# --- state appointment / departure formulas (journal-officiel) ---
RE_CHARGE = re.compile(
    rf"{TITLE}\s+(?P<name>{NAME}){SPOUSE}\s*(?:,\s*(?P<grade>[^,\n]{{3,90}}))?,?\s+"
    rf"est\s+charg[ée]{{1,2}}s?\s+des\s+fonctions\s+de\s+(?P<role>[^.\n]{{3,220}})",
    re.IGNORECASE)
RE_NOMME = re.compile(
    rf"{TITLE}\s+(?P<name>{NAME}){SPOUSE}\s*(?:,\s*(?P<grade>[^,\n]{{3,90}}))?,?\s+"
    rf"est\s+nomm[ée]{{1,2}}s?\s+(?P<role>[^.\n]{{3,220}})", re.IGNORECASE)
RE_LIST_HEAD = re.compile(
    r"(?:Sont\s+nomm[ée]{1,2}s?|Sont\s+charg[ée]{1,2}s)\s*"
    r"(?:Messieurs|Mesdames(?:\s+et\s+Messieurs)?|Mesdames|Mesdemoiselles)?\s*:?",
    re.IGNORECASE)
RE_LIST_ITEM = re.compile(
    rf"^\s*[-•*]\s*(?P<name>{NAME})\s*:\s*(?P<role>[^\n]{{3,200}}?)\s*[,;.]?\s*$",
    re.MULTILINE)
RE_CESSATION = re.compile(
    rf"(?:il\s+est\s+mis\s+fin\s+aux\s+fonctions\s+de|cessation\s+de(?:s)?\s+fonctions\s+de|"
    rf"est\s+d[ée]charg[ée]{{1,2}}s?\s+de(?:s)?\s+fonctions\s+de)\s*{TITLE}?\s*"
    rf"(?P<name>{NAME})", re.IGNORECASE)
RE_RETIREMENT = re.compile(
    rf"{TITLE}\s+(?P<name>{NAME})[^.\n]{{0,120}}?(?:est\s+)?admis[e]?\s+[àa]\s+"
    rf"(?:faire\s+valoir\s+ses\s+droits\s+[àa]\s+)?la\s+retraite", re.IGNORECASE)

# --- act citations ("Vu le decret ... du ...") ---
RE_VISA = re.compile(
    r"^Vu\s+(?:le|la|l')\s*(?P<kind>d[ée]cret(?:-loi)?(?:\s+Pr[ée]sidentiel|"
    r"\s+gouvernemental)?|arr[êe]t[ée]|loi(?:\s+organique)?|d[ée]cision)"
    r"[^,\n]{0,60}?(?:n[°ºo]\s*(?P<num>\d{2,4}\s*-\s*\d{1,4}))?"
    r"\s*(?:du\s+(?P<date>" + DATE_CORE + r"))?(?:,\s*(?P<gist>[^,\n]{0,200}))?",
    re.IGNORECASE | re.MULTILINE)

# --- act's own number and date ---
RE_ACT_NUMBER = re.compile(r"n[°ºo]\s*(?P<num>\d{2,4}\s*-\s*\d{1,4})", re.IGNORECASE)

RE_ACT_HEAD = re.compile(
    r"(?P<kind>d[ée]cret(?:-loi)?(?:\s+Pr[ée]sidentiel|\s+gouvernemental)?|"
    r"arr[êe]t[ée]s?|loi(?:\s+organique)?)"
    r"[^\n]{0,140}?(?:n[°ºo]\s*(?P<num>\d{2,4}\s*-\s*\d{1,4}))?"
    r"[^\n]{0,140}?du\s+(?P<date>" + DATE_CORE + r")", re.IGNORECASE)


def strip_accents(text: str) -> str:
    d = unicodedata.normalize("NFKD", text.replace("’", "'"))
    return "".join(c for c in d if not unicodedata.combining(c))


def parse_date_string(text: str) -> date | None:
    """Parse the first date in a short clause, textual or numeric."""
    folded = strip_accents(text).lower()
    m = RE_DATE_TXT.search(folded)
    if m:
        day_raw = m.group("d")
        day = 1 if day_raw.startswith("1er") or day_raw.startswith("1ere") else int(day_raw)
        month = MONTHS.get(m.group("m"))
        if month:
            try:
                return date(int(m.group("y")), month, day)
            except ValueError:
                return None
    m = RE_DATE_NUM.search(folded)
    if m:
        try:
            return date(int(m.group("y")), int(m.group("m")), int(m.group("d")))
        except ValueError:
            return None
    return None


# Lowercase words that may legitimately appear inside a Tunisian name.
_ALLOWED_LOWER = {
    "ben", "bent", "bin", "el", "al", "ould", "ouled", "abou", "abu", "abd",
    "abdel", "si", "sidi", "bel", "bou", "ibn", "ebn", "de", "du", "da", "la",
    "le", "van", "von", "dos", "di",
}


def clean_name(raw: str) -> str:
    """Tidy a captured name and reject boilerplate that is not a name.

    Validation is deliberately strict: the surrounding prose is dense with
    capitalised institutional phrases ("La declaration de souscription",
    "Recu par Madame le Receveur de l'Enregistrement"), and admitting those as
    people would pollute every downstream table.
    """
    name = re.sub(r"\s+", " ", (raw or "").strip())
    name = name.strip(" .,;:-'’")
    # drop a dangling particle left at the end of a truncated capture
    toks = name.split()
    while toks and strip_accents(toks[-1]).lower() in {
        "ben", "bent", "bin", "el", "al", "ould", "ouled", "abou", "abd",
        "abdel", "si", "sidi", "bel", "bou", "ibn", "ebn", "et", "de", "du",
    }:
        toks.pop()
    name = " ".join(toks)
    if len(name) < 4 or " " not in name:
        # A single token is too ambiguous to treat as a person.
        return ""
    toks = name.split()
    if len(toks) > 5:
        return ""
    if re.search(r"[\d:;()/»«\"]", name):
        return ""
    for tok in toks:
        bare = strip_accents(tok).strip(".").upper()
        if bare in NAME_STOPWORDS:
            return ""
        low = strip_accents(tok).strip(".").lower()
        # Every token must look like a name component: capitalised, all-caps,
        # or one of the recognised Arabic/European particles.
        if low not in _ALLOWED_LOWER and not re.match(rf"^[{U}]", tok):
            return ""
    # Require at least one token that is not a particle.
    if not any(strip_accents(t).strip(".").lower() not in _ALLOWED_LOWER for t in toks):
        return ""
    return name


@lru_cache(maxsize=1)
def role_lookup() -> list[tuple[str, str]]:
    """Surface role forms, longest first so 'directeur general adjoint' wins."""
    cfg = load_config("vocab_roles")
    pairs = [(strip_accents(k).lower(), v) for k, v in cfg["surface_forms"].items()]
    return sorted(pairs, key=lambda p: -len(p[0]))


def match_role(text: str) -> tuple[str, str]:
    """Map a role phrase onto the controlled vocabulary.

    Returns (canonical_role, verbatim). The verbatim form is always kept so an
    unmapped or mis-mapped role can be audited and the lexicon extended.
    """
    if not text:
        return "", ""
    verbatim = re.sub(r"\s+", " ", text.strip()).strip(" .,;:")
    folded = strip_accents(verbatim).lower()
    for surface, canon in role_lookup():
        if re.search(rf"(?<![a-z]){re.escape(surface)}(?![a-z])", folded):
            return canon, verbatim[:200]
    return "", verbatim[:200]


def mandate_years(text: str) -> float | None:
    for rx in (RE_MANDATE_YEARS, RE_MANDATE_EXERCICES):
        m = rx.search(text)
        if m:
            raw = m.group("n").lower()
            return float(WORD_NUMBERS.get(raw, raw)) if raw.isalpha() or raw.isdigit() else None
    return None


def normalise_mf(raw: str) -> str:
    """Reduce a matricule fiscal to a comparable stem.

    Three surface forms occur (1518656/S/A/M/000, 1516084T, 007240 WPM 000);
    the leading digits plus the first letter identify the firm.
    """
    if not raw:
        return ""
    compact = re.sub(r"[^0-9A-Za-z]", "", raw).upper()
    m = re.match(r"(\d{6,8})([A-Z])?", compact)
    if not m:
        return ""
    return m.group(1).lstrip("0") + (m.group(2) or "")


def parse_capital(text: str) -> float | None:
    m = RE_CAPITAL.search(text)
    if not m:
        return None
    raw = m.group("amount")
    raw = re.sub(r"[\s.]", "", raw).replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def find_persons(text: str) -> list[tuple[str, str, int]]:
    """Every titled person mention: (name, married_name, offset)."""
    out = []
    for m in RE_PERSON.finditer(text):
        name = clean_name(m.group("name"))
        if name:
            out.append((name, clean_name(m.group("spouse") or ""), m.start()))
    return out


# The role phrase must stop before the next person or the next "en qualite":
# a resolution naming two officers has no punctuation between them, so an
# unbounded capture swallows the second person and mis-titles them.
RE_QUALITE = re.compile(
    r"en\s+(?:sa|leur|ses)?\s*qualit[ée]s?\s+d[e\']\s*"
    r"(?P<role>(?:(?!\s+et\s+(?:" + TITLE + r"))(?!\s+en\s+qualit)[^,.;\n]){3,90})",
    re.IGNORECASE)


def pair_person_roles(clause: str) -> list[tuple[str, str, str]]:
    """Associate each person in a clause with their own role.

    A single resolution often names several people with different roles --
    "a nomme Madame X en qualite de President du Conseil d'Administration et
    Monsieur Y en qualite de Directeur General" -- so a clause-level role
    applied to everyone would silently mis-title people. Each person takes the
    first role phrase that appears after them and before the next person.

    Returns (name, married_name, role_phrase); role_phrase may be empty.
    """
    persons = [(m.start(), clean_name(m.group("name")),
                clean_name(m.group("spouse") or ""))
               for m in RE_PERSON.finditer(clause)]
    persons = [(o, n, s) for o, n, s in persons if n]
    if not persons:
        return []

    roles = [(m.start(), m.group("role")) for m in RE_QUALITE.finditer(clause)]
    out: list[tuple[str, str, str]] = []
    for i, (offset, name, spouse) in enumerate(persons):
        next_offset = persons[i + 1][0] if i + 1 < len(persons) else len(clause) + 1
        own = ""
        for r_off, r_text in roles:
            if offset < r_off < next_offset:
                own = r_text
                break
        out.append((name, spouse, own))

    # If exactly one role phrase precedes every person, it governs them all
    # ("sont nommes en qualite d'administrateurs : X, Y et Z").
    if len(roles) == 1 and all(not r for _n, _s, r in out) and roles[0][0] < persons[0][0]:
        out = [(n, s, roles[0][1]) for n, s, _r in out]
    return out


def split_person_list(text: str) -> list[str]:
    """Split an enumeration of people into individual names.

    Needed for the common 'Monsieur X, Monsieur Y et Madame Z' construction.
    """
    names = [n for n, _s, _o in find_persons(text)]
    if names:
        return names
    # Fall back to splitting an untitled enumeration, but validate each part:
    # a bare comma split over prose otherwise yields institutional phrases.
    out = []
    for part in re.split(r",|\bet\b|;|\n", text):
        part = part.strip()
        if len(part.split()) > 4:
            continue
        name = clean_name(part)
        if name:
            out.append(name)
    return out
