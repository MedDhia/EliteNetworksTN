"""Parse dated ownership movements out of CMF notices.

Registration documents give annual *snapshots*: who held what when the document
was drawn up. These notices give *changes*, dated to the day - a tender offer
opening, its result, a capital increase, an admission to the cote, a delisting.
They are what turns the ownership layers from a series of stills into a record
of movement.

They are short prose, not tables, and the prose is highly formulaic because the
regulator prescribes it. The parsers here are therefore pattern-based, and each
extracted field records the sentence it came from so that any figure can be
checked against the notice.

Two structures matter for the network:

* **Concert parties.** An offer is often launched by several companies
  "agissant de concert" - a legally declared coalition. Those are recorded as
  parties to one movement, which yields a coalition tie no ownership table
  states.
* **Entry and exit.** An admission notice dates a firm's arrival on the cote and
  a withdrawal offer dates its radiation. Together they give the listing
  history the BVMT roster snapshot cannot.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from .tables import strip_accents

# --------------------------------------------------------------------------
# normalisation helpers
# --------------------------------------------------------------------------


def flat(text: str) -> str:
    """Collapse a notice to one whitespace-normalised line for matching."""
    return re.sub(r"\s+", " ", text or "").strip()


def norm(text: str) -> str:
    return strip_accents(flat(text)).lower().replace("’", "'")


_MONTHS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "decembre": 12,
}
_DATE_TXT = re.compile(
    r"(\d{1,2})(?:er)?\s+(" + "|".join(_MONTHS) + r")\s+((?:19|20)\d{2})"
)
_DATE_NUM = re.compile(r"(\d{1,2})[/.\-](\d{1,2})[/.\-]((?:19|20)\d{2})")

MIN_YEAR, MAX_YEAR = 1990, 2035


def parse_date(s: str) -> str | None:
    """Return the first plausible ISO date in ``s``."""
    n = norm(s)
    m = _DATE_TXT.search(n)
    if m:
        y = int(m.group(3))
        if MIN_YEAR <= y <= MAX_YEAR:
            return f"{y:04d}-{_MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}"
    m = _DATE_NUM.search(n)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31 and MIN_YEAR <= y <= MAX_YEAR:
            return f"{y:04d}-{mo:02d}-{d:02d}"
    return None


# Figures: "16 205 315", "180.003.600", "13,390", "41,28%".
_NUM = re.compile(r"\d[\d  .]*\d|\d")


def to_num(s: str | None) -> float | None:
    if not s:
        return None
    t = s.replace(" ", " ").replace(" ", " ").strip().rstrip("%").strip()
    # Decimal comma, thousands by space or dot.
    if "," in t:
        t = t.replace(" ", "").replace(".", "").replace(",", ".")
    else:
        t = t.replace(" ", "").replace(".", "")
    try:
        return float(t)
    except ValueError:
        return None


def _pct(s: str | None) -> float | None:
    v = to_num(s)
    return v if v is not None and 0 <= v <= 100 else None


# --------------------------------------------------------------------------
# event typing
# --------------------------------------------------------------------------

# Ordered: the first match wins, so the most specific patterns come first.
EVENT_PATTERNS: list[tuple[str, str]] = [
    ("opa_obligatoire", r"offre publique d'achat obligatoire|opa obligatoire"),
    ("opa_simplifiee", r"offre publique d'achat simplifiee|opa simplifiee"),
    ("opr_retrait", r"offre publique de retrait|\bopr\b"),
    ("opa", r"offre publique d'achat|\bopa\b"),
    ("ope_echange", r"offre publique d'echange|\bope\b"),
    ("opf_prix_ferme", r"offre a prix ferme|\bopf\b"),
    ("opv_prix_ouvert", r"offre a prix ouvert|offre publique de vente|\bopv\b"),
    ("maintien_de_cours", r"maintien de cours"),
    ("reduction_capital", r"reduction (?:de|du) capital|reduction de la valeur nominale"),
    ("augmentation_capital", r"augmentation de capital|augmenter le capital"),
    ("fusion", r"\bfusion\b|absorption|scission"),
    ("admission", r"admission au marche|introduction en bourse|sont introduites au marche"),
]

RESULT_MARKERS = r"resultat de l|a ete cloturee|ont ete acquises|il n'y a eu aucun"


def classify_event(title: str, text: str) -> tuple[str | None, bool]:
    """Return (event_type, is_result).

    ``is_result`` distinguishes a notice reporting an operation's *outcome* from
    one announcing it. The two carry different figures - sought versus acquired -
    and conflating them would double-count the same operation.
    """
    hay = norm(title) + " || " + norm(text)[:4000]
    etype = None
    for name, pat in EVENT_PATTERNS:
        if re.search(pat, hay):
            etype = name
            break
    is_result = bool(re.search(RESULT_MARKERS, norm(title))) or bool(
        re.search(r"resultat de l'offre|a ete cloturee a cette derniere date", norm(text)[:2500])
    )
    return etype, is_result


# --------------------------------------------------------------------------
# field extraction
# --------------------------------------------------------------------------

# Where a party list ends. Company names do not contain these, so the first one
# closes the run: without them the capture swallows the rest of the sentence
# ("Groupe BAYAHI qui détient 16 205 315 actions représentant 41...").
_CLAUSE_END = (
    r"\bqui\b|\bqu'|\bque\b|\bdont\b|\bdurant\b|\bd[ée]tenant\b|\bd[ée]tient\b|"
    r"\bd[ée]tiennent\b|\brepr[ée]sentant\b|\bagissant\b|\bsoit\b|\bet\s+ce\b|"
    r"\bayant\b|\bsur\s+les\b|\bau\s+profit\b|\bconform[ée]ment\b|\bpour\b|"
    r"\bactions\b|\bau\s+prix\b|\best\b|\bsont\b|\ble\s+pr[ée]sent\b|"
    r"\bse\s+propose\b|\ba\s+d[ée]clar[ée]\b|\bvise\b|\bvisant\b|\badresse\b|\bsis\b"
)

# "initiée par la société « Y »"
# "initiée par les sociétés du groupe « La Rose Blanche » : «A», «B», «C»"
_INITIATED_BY = re.compile(
    r"initi[ée]e?s?\s+par\s+"
    r"(?:l(?:a|es|e)\s+)?(?:soci[ée]t[ée]s?\s+)?"
    r"(?:du\s+groupe\s+[«\"“][^»\"”]{2,60}[»\"”]\s*:?\s*)?"   # group name, then its members
    r"(?P<who>.{3,400}?)"
    r"(?=\s*(?:" + _CLAUSE_END + r")|[.;]|$)",
    re.I,
)

# "a déclaré agir de concert avec le Groupe BAYAHI"
# "détenant de concert avec les sociétés du même groupe : «A», «B»"
_CONCERT = re.compile(
    r"(?:agir|agissant|d[ée]tenant|de)\s+concert\s+avec\s+"
    r"(?:l(?:es?|a)\s+)?(?:soci[ée]t[ée]s?\s+(?:du\s+m[êe]me\s+groupe\s*)?)?:?\s*"
    r"(?P<who>.{3,400}?)"
    r"(?=\s*(?:" + _CLAUSE_END + r")|[.;]|$)",
    re.I,
)

# Quoted or capitalised company names inside a party list.
_QUOTED = re.compile(r"[«\"“]\s*([^»\"”]{2,80}?)\s*[»\"”]")

_STOPWORDS = {
    "la societe", "les societes", "le groupe", "la bourse", "le cmf",
    "et", "des", "du", "de", "la", "le", "les", "l", "au", "aux", "sa", "sur",
}


_PARTY_NOISE = re.compile(
    r"\d\s*%|\bactions?\b|\bdinars?\b|\bcapital\b|\bbourse\b|\boffre\b|\bjours?\b|"
    r"\bprix\b|\btitres?\b|\bconseil\b|\bpr[ée]sident\b|\bqualit[ée]\b|\belle\b|\bil\b|"
    r"\bd[ée]cision\b|\bacquisition\b|\bliquidation\b|\breste\b|\bproportion\b|"
    r"\bgroupe d'actionnaires\b|\bsusmentionn|\bpersonnes?\b|\bmorales?\b|"
    r"\bphysiques?\b|\bactionnaires?\b|\bpublic\b|\bdivers\b",
    re.I,
)

# A registered address, which sits next to the company name in these notices
# and is not a party to anything.
_ADDRESS = re.compile(
    r"\bsis(?:e|es)?\s+[àa]\b|\brue\b|\bavenue\b|\bboulevard\b|\bimmeuble\b|"
    r"\bbloc\b|\bcentre\s+urbain\b|\bcit[ée]\s|\b[ée]tage\b|\blot\b|\bkm\b|"
    r"\bz\.?i\.?\b|\bb\.?p\.?\s*\d|\b\d{4}\s+[A-Z]",
    re.I,
)


def is_plausible_party(name: str) -> bool:
    """Reject sentence fragments that a greedy capture can leave behind.

    A party is a company or person name: a handful of words, no figures, and
    none of the vocabulary that only appears in surrounding prose. Without this
    guard, fragments such as "durant les quatre-vingt-dix (90) jours de bourse"
    become nodes in the network.
    """
    n = name.strip()
    nn = norm(n)
    if len(n) < 2 or len(n) > 80 or nn in _STOPWORDS:
        return False
    if re.fullmatch(r"[\d\s.,%-]+", n):
        return False
    if len(n.split()) > 9:
        return False
    # Match on the normalised form: the notices use curly apostrophes, so
    # testing the raw string would miss "groupe d’actionnaires".
    if _PARTY_NOISE.search(nn) or _ADDRESS.search(nn):
        return False
    # A date is not a party: "30 décembre 2020" survives every other test.
    if parse_date(n) and len(n.split()) <= 4:
        return False
    # Must contain at least one letter run that looks like a name.
    return bool(re.search(r"[A-Za-zÀ-ÿ]{2,}", n))


def split_parties(blob: str) -> list[str]:
    """Split a run of party names into individual companies.

    Names are usually quoted, in which case the quotes are authoritative;
    otherwise the run is split on separators and cleaned.
    """
    blob = flat(blob)
    quoted = [q.strip(" .,;:") for q in _QUOTED.findall(blob)]
    if quoted:
        parts = quoted
    else:
        parts = re.split(r"\s*(?:,|;|\bet\b|/)\s*", blob)
    out: list[str] = []
    for p in parts:
        p = re.sub(r"^(?:la|les|le|l')\s+", "", p.strip(" .,;:«»\"“”"), flags=re.I)
        p = re.sub(r"^soci[ée]t[ée]s?\s+", "", p, flags=re.I).strip(" .,;:-")
        # Drop a trailing acronym gloss: "Les Grands Silos de Sud -GSS-".
        p = re.sub(r"\s*[-–]\s*[A-Z][A-Z0-9.&-]{1,12}\s*[-–]?\s*$", "", p).strip()
        p = _strip_gloss(p)
        if not is_plausible_party(p):
            continue
        out.append(p)
    # Preserve order, drop duplicates.
    seen, uniq = set(), []
    for p in out:
        k = norm(p)
        if k not in seen:
            seen.add(k)
            uniq.append(p)
    return uniq[:20]


# Notices are laid out in numbered sections: "I- Identité de l'initiateur :",
# "III- Nombre de titres détenus par l'initiateur de l'offre :".
_SECTION = re.compile(
    r"(?:^|\s)(?P<num>[IVX]{1,5}|\d{1,2})\s*[-–.)]\s*(?P<head>[A-ZÀ-Ý][^:]{3,70}?)\s*:",
)

_SENT_SPLIT = re.compile(r"(?<=[.;])\s+(?=[A-ZÀ-Ý«\"-])")


def split_sections(text: str) -> list[tuple[str, str]]:
    """Split a notice into (heading, body) pairs on its numbered headings."""
    t = flat(text)
    marks = list(_SECTION.finditer(t))
    if not marks:
        return [("", t)]
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(t)
        out.append((flat(m.group("head")), t[m.end():end].strip()))
    return out


def sentences(text: str) -> list[str]:
    return [s for s in _SENT_SPLIT.split(flat(text)) if s.strip()]


# Everything from these markers onward describes where a party is registered,
# not who it is.
_IDENTITY_TAIL = re.compile(
    r"\b(?:adresse|si[èe]ge\s+social|sis(?:e|es)?\b|immatricul|registre|"
    r"forme\s+juridique|nationalit[ée]|capital\s+social|identifiant|"
    r"est\s+l['’]initiat|de\s+droit\s+\w+|\(soci[ée]t[ée])", re.I
)
# A named individual: an honorific followed by capitalised words.
_PERSON = re.compile(
    r"\b(?:M\.|Mr\.?|Mme\.?|Mlle\.?|Mmes)\s+"
    r"([A-ZÀ-Ý][\w'’\-]+(?:\s+[A-ZÀ-Ý][\w'’\-]+){0,3})"
)


def _strip_gloss(name: str) -> str:
    """Remove a parenthetical gloss, closed or left dangling by a truncation."""
    n = re.sub(r"\s*\([^)]*\)\s*", " ", name)
    n = re.sub(r"\s*\(.*$", "", n)
    return re.sub(r"\s+", " ", n).strip(" .,;:-")


def extract_names(segment: str) -> list[str]:
    """Read party names from one sentence or section.

    Quotation marks and honorifics are how these notices actually mark a name,
    so they are tried first. Splitting on commas is the last resort, because an
    address splits into convincing-looking fragments ("Belvédère", "Tunis").
    """
    head = _IDENTITY_TAIL.split(segment, maxsplit=1)[0]
    quoted = [q for q in _QUOTED.findall(segment) if is_plausible_party(q)]
    persons = [p for p in _PERSON.findall(head) if is_plausible_party(p)]
    if quoted or persons:
        names = [_strip_gloss(x) for x in quoted + persons]
        return [x for x in names if is_plausible_party(x)]
    return split_parties(head)


def parties_from_identity(body: str) -> list[str]:
    """Read party names out of an "Identité de l'initiateur" section.

    The section pairs each name with a registered address, and the address
    commas split into convincing-looking fragments ("Belvédère", "Tunis"). So
    names are taken from the structures that actually mark them - quotation
    marks and honorifics - and each entry is cut at the first address marker.
    """
    out: list[str] = []
    for sent in sentences(body)[:4]:
        out.extend(extract_names(sent))
    seen, uniq = set(), []
    for p in out:
        k = norm(p)
        if k and k not in seen:
            seen.add(k)
            uniq.append(p)
    return uniq


def find_parties(text: str) -> tuple[list[str], list[str]]:
    """Return (initiators, concert_parties).

    Parsed from the notice's own structure rather than across the whole
    document. Regexing the flattened text runs past sentence ends and pulls in
    registered addresses and fragments of the next clause; restricting each
    pattern to the section or sentence that states it does not.
    """
    initiators: list[str] = []
    concert: list[str] = []

    # 1. The dedicated "Identité de l'initiateur" section, where present.
    for head, body in split_sections(text):
        h = norm(head)
        if "initiateur" in h and ("identite" in h or h.startswith("initiateur")):
            initiators.extend(parties_from_identity(body))
            if initiators:
                break

    # 2. Otherwise the "initiée par ..." formula, bounded to its own sentence.
    if not initiators:
        for sent in sentences(text):
            m = _INITIATED_BY.search(sent)
            if m:
                initiators = split_parties(m.group("who"))
                if initiators:
                    break

    # 3. Concert parties: only from the sentence that declares the concert.
    for sent in sentences(text):
        m = _CONCERT.search(sent)
        if m:
            concert.extend(extract_names(m.group("who")))

    seen = {norm(i) for i in initiators}
    deduped = []
    for c in concert:
        k = norm(c)
        if k not in seen:
            seen.add(k)
            deduped.append(c)
    return initiators[:20], deduped[:20]


# Price: "au prix unitaire de 13,390 dinars", "au prix de 6,080 dinars"
_PRICE = re.compile(
    r"au prix\s+(?:unitaire\s+|de\s+cession\s+|d'offre\s+)?(?:de\s+)?"
    r"(?P<v>\d[\d  .,]*)\s*dinars?",
    re.I,
)
# Shares sought: "vise l'acquisition de 6 843 844 actions"
_SOUGHT = re.compile(
    r"(?:vise|visant|portant sur|objet de l'\w+)\s+(?:l'acquisition\s+(?:de\s+)?|de\s+)?"
    r"(?P<n>\d[\d  .]*)\s*actions",
    re.I,
)
# "6 843 844 actions SOTUVER représentant 17,43% du capital"
_SHARES_PCT = re.compile(
    r"(?P<n>\d[\d  .]*)\s*actions\b[^.]{0,80}?repr[ée]sentant\s+"
    r"(?P<p>\d[\d.,]*)\s*%\s*(?:du\s+capital|des\s+droits)",
    re.I,
)
# Acquired: "1 561 324 actions ont été acquises"
_ACQUIRED = re.compile(
    r"(?P<n>\d[\d  .]*)\s*actions\s+ont\s+[ée]t[ée]\s+acquises", re.I
)
_NO_DEPOSIT = re.compile(r"il n'y a eu aucun d[ée]p[ôo]t", re.I)

# Capital change. The amounts are written in several ways and the phrase that
# introduces them varies ("capital social de la société de X à Y", "capital
# social de la SOPAT de X DT à Y DT", "augmentation ... de son capital social
# de X à Y"), so the filler between the phrase and the figures is allowed for
# and the currency token is optional.
_MONEY = r"(?:(?:dinars?|dt|d)\b)"
_CAPITAL_CHANGE = re.compile(
    r"capital\s+social\b[^.]{0,70}?\bde\s+(?P<a>\d[\d  .,]{2,})\s*" + _MONEY + r"?"
    r"\s*[àa]\s+(?P<b>\d[\d  .,]{2,})\s*" + _MONEY + r"?",
    re.I,
)
# "Société anonyme au capital de 180 003 600 dinars" - the capital as it stood
# when the notice was drawn up, which many completion notices give in the
# header even where they do not restate the before/after pair.
_CAPITAL_STATED = re.compile(
    r"au\s+capital(?:\s+social)?\s+de\s+(?P<v>\d[\d  .,]{3,})\s*" + _MONEY + r"?",
    re.I,
)

# "porter le capital de X à Y"
_CAPITAL_PORTER = re.compile(
    r"porter\s+(?:ainsi\s+)?(?:le|son)\s+capital[^.]{0,50}?\bde\s+(?P<a>\d[\d  .,]{2,})\s*"
    + _MONEY + r"?\s*[àa]\s+(?P<b>\d[\d  .,]{2,})\s*" + _MONEY + r"?",
    re.I,
)
_CAPITAL_METHOD = re.compile(
    r"par\s+(incorporation de r[ée]serves|[ée]mission[^.,;]{0,60}|"
    r"apport[^.,;]{0,40}|conversion[^.,;]{0,40}|souscription[^.,;]{0,40})",
    re.I,
)
_NEW_SHARES = re.compile(
    r"(?:cr[ée]ation et (?:l')?[ée]mission|[ée]mission)\s+de\s+(?P<n>\d[\d  .]*)\s*actions",
    re.I,
)

# Listing / delisting
_ADMITTED = re.compile(
    r"(?P<n>\d[\d  .]*)\s*actions[^.]{0,120}?sont\s+introduites?\s+au\s+"
    r"(?P<mkt>march[ée][^.,;]{0,40})",
    re.I,
)
_RADIATION = re.compile(
    r"seront\s+radi[ée]s?\s+du\s+(?P<mkt>march[ée][^.,;]{0,60}?)"
    r"[^.]{0,60}?[àa]\s+partir\s+du\s+(?P<d>[^.,;]{4,40})",
    re.I,
)
_ISIN = re.compile(r"\b(TN[A-Z0-9]{10})\b")
_TICKER = re.compile(r"[Cc]ode\s+[Mm]n[ée]monique\s*:?\s*([A-Z0-9]{2,8})")

# Period: "ouverte du 05 août 2026 au 26 août 2026"
_PERIOD = re.compile(
    r"ouverte?\s+du\s+(?P<a>.{4,32}?)\s+au\s+(?P<b>.{4,32}?)(?=\s+a\s+[ée]t[ée]|[.,;]|$)",
    re.I,
)
# Decision date: "Assemblée Générale Extraordinaire tenue le 3 juin 2026"
_AGE_DATE = re.compile(
    r"assembl[ée]e\s+g[ée]n[ée]rale[^.]{0,40}?tenue\s+le\s+(?P<d>.{4,32}?)(?=[,.;]|\s+a\s+d[ée]cid)",
    re.I,
)


def _first(pattern: re.Pattern, text: str, group: str = "v") -> str | None:
    m = pattern.search(text)
    return m.group(group) if m else None


def parse_movement(title: str, text: str) -> dict[str, Any] | None:
    """Extract one movement event from a notice."""
    t = flat(text)
    etype, is_result = classify_event(title, t)
    if etype is None:
        return None

    initiators, concert = find_parties(t)

    rec: dict[str, Any] = {
        "event_type": etype,
        "is_result": is_result,
        "initiators": initiators,
        "concert_parties": concert,
        "price_tnd": to_num(_first(_PRICE, t)),
    }

    # --- offer sizing ------------------------------------------------------
    m = _SOUGHT.search(t)
    if m:
        rec["shares_sought"] = to_num(m.group("n"))
    m = _SHARES_PCT.search(t)
    if m:
        rec["shares_stated"] = to_num(m.group("n"))
        rec["pct_stated"] = _pct(m.group("p"))
    if _NO_DEPOSIT.search(t):
        rec["shares_acquired"] = 0.0
    m = _ACQUIRED.search(t)
    if m:
        rec["shares_acquired"] = to_num(m.group("n"))

    # Largest stated percentage of capital: the concert total where one is
    # given, which is the figure that matters for control.
    pcts = [
        _pct(p) for p in re.findall(
            r"repr[ée]sentant\s+(?:au\s+total\s+)?(\d[\d.,]*)\s*%", t, re.I
        )
    ]
    pcts = [p for p in pcts if p is not None]
    if pcts:
        rec["pct_max_stated"] = max(pcts)

    # --- period and decision dates ----------------------------------------
    m = _PERIOD.search(t)
    if m:
        # "du 11 au 31 octobre 2023": the opening date may omit month and year.
        b = parse_date(m.group("b"))
        a = parse_date(m.group("a")) or (
            parse_date(f"{m.group('a')} {m.group('b')}") if b else None
        )
        rec["open_date"], rec["close_date"] = a, b
    m = _AGE_DATE.search(t)
    if m:
        rec["decision_date"] = parse_date(m.group("d"))

    # --- capital change ----------------------------------------------------
    m = _CAPITAL_CHANGE.search(t) or _CAPITAL_PORTER.search(t)
    if m:
        a, b = to_num(m.group("a")), to_num(m.group("b"))
        # Capital is denominated in whole dinars and is never trivially small;
        # a tiny pair is a share ratio ("1 action pour 20"), not a capital.
        if a and b and a >= 1000 and b >= 1000:
            rec["capital_before_tnd"] = a
            rec["capital_after_tnd"] = b
    m = _CAPITAL_STATED.search(t)
    if m:
        v = to_num(m.group("v"))
        if v and v >= 1000:
            rec["capital_stated_tnd"] = v
    meth = _CAPITAL_METHOD.search(t)
    if meth:
        rec["capital_method"] = flat(meth.group(1)).lower()[:60]
    m = _NEW_SHARES.search(t)
    if m:
        rec["new_shares"] = to_num(m.group("n"))

    # --- listing and delisting --------------------------------------------
    m = _ADMITTED.search(t)
    if m:
        rec["listed_shares"] = to_num(m.group("n"))
        rec["market"] = flat(m.group("mkt"))[:60]
        rec["listing_event"] = "admission"
    m = _RADIATION.search(t)
    if m:
        rec["delisting_date"] = parse_date(m.group("d"))
        rec["market"] = rec.get("market") or flat(m.group("mkt"))[:60]
        rec["listing_event"] = "radiation"
    isin = _ISIN.search(t)
    if isin:
        rec["isin"] = isin.group(1)
    tick = _TICKER.search(text)
    if tick:
        rec["ticker"] = tick.group(1)

    return rec


# --------------------------------------------------------------------------
# target firm
# --------------------------------------------------------------------------

# "sur les actions de la société X", "visant les actions de la Société X"
_TARGET = re.compile(
    r"(?:sur|visant)\s+les\s+actions\s+(?:ordinaires\s+)?(?:de\s+la\s+|de\s+)"
    r"(?:soci[ée]t[ée]\s+)?(?P<who>.{3,90}?)"
    r"(?=\s*[«\"]|\s+initi|[.,;:]|\s+est\b|\s+sont\b|$)",
    re.I,
)
_TITLE_TARGET = re.compile(r"[:\-–]\s*(?P<who>[^:\-–]{2,70})\s*$")

# The issuer's name sits immediately before its registered office in company
# notices: "... Hannibal Lease Siège Social : Rue du Lac Malaren ...".
_BEFORE_SIEGE = re.compile(
    r"(?:^|[.;:»\"”]|\s)(?P<who>[A-ZÀ-Ý][^.:;0-9]{2,70}?)\s*(?:S\.?A\.?)?\s*"
    r"si[èe]ge\s+social\s*:",
    re.I,
)

# Titles that name an operation rather than a company.
_GENERIC_TITLE = re.compile(
    r"augmentation|reduction|offre|admission|introduction|visa|avis|resultat|"
    r"prospectus|emission|fusion|notice|communique|prorogation|cloture"
)


# Words that open a notice banner rather than a company name.
_BANNER_WORDS = {
    "avis", "des", "de", "du", "la", "le", "les", "societes", "societe",
    "augmentation", "reduction", "capital", "realisee", "realise", "annoncee",
    "annonce", "offre", "publique", "achat", "retrait", "vente", "resultat",
    "notice", "communique", "emission", "admission", "introduction", "en",
    "numeraire", "par", "sans", "recours", "appel", "public", "epargne", "a",
    "l", "sur", "actions", "titres", "bourse", "cote", "marche", "visa",
    "anonyme", "au", "dt", "dinars", "dinar", "sans", "realisee", "d",
}


def _strip_banner(name: str) -> str:
    """Drop the boilerplate that precedes an issuer name in a notice header."""
    toks = flat(name).split()
    while toks and strip_accents(toks[0]).lower().strip(" '’-:.,") in _BANNER_WORDS:
        toks.pop(0)
    return " ".join(toks)


def _clean_target(cand: str | None) -> str | None:
    """Trim a captured company name back to the name itself."""
    if not cand:
        return None
    c = _strip_banner(flat(cand).strip(" .,;:«»\"“”"))
    c = re.sub(r"^(?:la|le|les|de\s+la|du|des)\s+", "", c, flags=re.I)
    c = re.sub(r"^soci[ée]t[ée]\s+", "", c, flags=re.I)
    # Notices run straight into their numbered body: "… VIE 1- A partir du …".
    c = re.split(r"\s+\d+\s*[-–)]\s", c)[0]
    c = re.sub(r"[\s–-]+\d{1,2}$", "", c)
    # Drop a trailing acronym gloss and any dangling connector.
    c = re.sub(r"\s*[-–]\s*[A-Z][A-Z0-9.&-]{1,12}\s*[-–]?\s*$", "", c)
    c = re.sub(r"\s+(?:et|de|du|des|la|le|sur|au|aux)$", "", c, flags=re.I)
    c = c.strip(" .,;:-–«»\"")
    if not (2 <= len(c) <= 90):
        return None
    # After stripping boilerplate a real name still has a substantive token.
    if not any(len(tok) >= 3 for tok in re.findall(r"[A-Za-zÀ-ÿ]+", c)):
        return None
    return c


def find_target(title: str, text: str) -> str | None:
    """Name the company whose shares the notice concerns.

    The title is preferred when it quotes a short name, since issuers are named
    consistently there; otherwise the standard "sur les actions de la société X"
    formula in the body is used, and the title's trailing segment is the last
    resort.
    """
    # Titles name the target first and the initiator after: "... sur les actions
    # de la Société Tunisienne de Verreries -SOTUVER- initiée par la société
    # « B.A GLASS B.V »". Cutting at that hinge keeps the last quoted name from
    # being the initiator.
    head = re.split(r"\biniti[ée]e?s?\s+par\b", title or "", maxsplit=1, flags=re.I)[0]
    q = _QUOTED.findall(head)
    if q:
        cleaned = _clean_target(q[-1])
        if cleaned:
            return cleaned
    cleaned = _clean_target(_first(_TARGET, flat(text), "who"))
    if cleaned:
        return cleaned
    # Same cut for the title fallback, or the trailing "initiée par ..." clause
    # becomes the answer.
    m = _TITLE_TARGET.search(flat(head))
    cleaned = _clean_target(m.group("who")) if m else None
    if cleaned:
        return cleaned

    # Company notices open with the issuer's name immediately before its
    # registered office: "... Hannibal Lease Siège Social : Rue du Lac ...".
    m = _BEFORE_SIEGE.search(flat(text))
    if m:
        cleaned = _clean_target(m.group("who"))
        if cleaned:
            return cleaned

    # A short title with no separator is itself the company name
    # ("HANNIBAL LEASE"), provided it is not a generic operation label.
    t = flat(head)
    if 2 <= len(t) <= 60 and not _GENERIC_TITLE.search(norm(t)):
        return _clean_target(t)
    return None
