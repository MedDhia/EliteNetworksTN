"""Parse adopted AGM resolutions into dated governance events.

Registration documents state who sat on a board when the document was drawn up.
These state *when the meeting put them there*, which is what turns a board tie
from a snapshot into a spell with a start date and a stated end.

Three things here that the board tables cannot give:

* **A date.** "Résolutions adoptées par l'Assemblée Générale Ordinaire du
  21 mai 2026" dates every appointment in the document to the day.
* **A term.** Resolutions state when a mandate expires, usually as the meeting
  that will rule on a named financial year ("expirant lors de l'assemblée
  générale ordinaire qui statuera sur les états financiers de l'exercice 2023").
* **A predecessor.** A co-opted director is appointed "en remplacement de" a
  named person, which is a succession tie the source states outright - the same
  relation the JORT build recovers from the gazette.

The documents are formulaic because company law prescribes them: a header
naming the company and the meeting, then numbered resolutions each closing with
how the vote went. Parsing works on that structure, resolution by resolution,
so that a name is only ever read in the context of the decision that names it.
"""

from __future__ import annotations

import re
from typing import Any

from .movements import (  # shared helpers: these documents use the same conventions
    flat,
    is_plausible_party,
    norm,
    parse_date,
)

# --------------------------------------------------------------------------
# document structure
# --------------------------------------------------------------------------

_ORDINALS = (
    "premiere|deuxieme|troisieme|quatrieme|cinquieme|sixieme|septieme|huitieme|"
    "neuvieme|dixieme|onzieme|douzieme|treizieme|quatorzieme|quinzieme|seizieme|"
    "dix-septieme|dix-huitieme|dix-neuvieme|vingtieme"
)
ORDINAL_INDEX = {name: i + 1 for i, name in enumerate(_ORDINALS.split("|"))}

# "PREMIERE RESOLUTION :", "Première résolution :", "Résolution n° 5"
_RES_HEAD = re.compile(
    r"(?:^|\s)(?P<ord>" + _ORDINALS + r")\s+resolution\b|"
    r"(?:^|\s)resolution\s+n[°o]?\s*(?P<num>\d{1,2})\b",
    re.I,
)

# "Résolutions adoptées par l'Assemblée Générale Ordinaire du 21 mai 2026"
_MEETING = re.compile(
    r"assemblee\s+generale\s+(?P<kind>ordinaire|extraordinaire|mixte|"
    r"elective|constitutive)?[^.]{0,80}?\bdu\s+(?P<date>[^.,;:]{4,40})",
    re.I,
)
_MEETING_KIND = re.compile(
    r"assemblee\s+generale\s+(ordinaire|extraordinaire|mixte|elective|constitutive)", re.I
)


def split_resolutions(text: str) -> list[tuple[int | None, str]]:
    """Split a filing into (resolution number, body) pairs."""
    t = flat(text)
    n = norm(t)
    marks = list(_RES_HEAD.finditer(n))
    if not marks:
        return [(None, t)]
    out: list[tuple[int | None, str]] = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(t)
        if m.group("ord"):
            num = ORDINAL_INDEX.get(m.group("ord").lower())
        else:
            num = int(m.group("num")) if m.group("num") else None
        # norm() is length-preserving, so offsets carry over to the original.
        out.append((num, t[m.end():end].strip()))
    return out


def meeting_info(text: str) -> tuple[str | None, str | None]:
    """Return (meeting kind, ISO meeting date) from the document header."""
    head = flat(text)[:1200]
    n = norm(head)
    kind = None
    m = _MEETING_KIND.search(n)
    if m:
        kind = m.group(1).lower()
    m = _MEETING.search(n)
    date = parse_date(m.group("date")) if m else None
    if date is None:
        date = parse_date(head)
    return kind, date


# --------------------------------------------------------------------------
# people and roles
# --------------------------------------------------------------------------

# Honorifics. The \b after the alternation is what stops the bare "m" branch
# matching the M of "Messieurs" and leaving "essieurs" as the name.
# Scoped case-insensitivity: the honorific may be written in any case, but the
# name that follows must stay case-sensitive, since capitalisation is what marks
# where the name ends.
_TITLE = (
    r"(?i:monsieur|madame|mademoiselle|messieurs|mesdames|mesdemoiselles|"
    r"mr|mme|mlle|mm|m)\b\.?\s+"
)
# Name tokens must start with a capital: personal names are capitalised in these
# filings, and requiring it keeps trailing connectives ("pour", "en") out.
_NAME_TOKEN = r"[A-ZÀ-Ý][A-Za-zÀ-ÿ'’\-]*"
_NAME = rf"(?P<name>{_NAME_TOKEN}(?:\s+{_NAME_TOKEN}){{0,3}})"

# Capitalised words that are never part of a personal name, so a capture that
# runs on into the next clause ("Rim LAKHOUA La Société ...") can be trimmed.
_NAME_STOP = {
    "la", "le", "les", "societe", "société", "monsieur", "madame", "messieurs",
    "mesdames", "mademoiselle", "et", "en", "pour", "qui", "dont", "aux", "au",
    "banque", "conseil", "administrateur", "administratrice", "membre",
    "president", "directeur", "commissaire", "decidee", "décidée", "sa", "sarl",
    "representee", "représentée", "representant", "cette", "resolution", "the",
    "assemblee", "assemblée", "generale", "générale", "ordinaire", "extraordinaire",
    "ago", "age", "nomme", "nommer", "decide", "décide", "decider", "designer",
    "désigner", "renouveler", "ratifier", "ratfier", "arrive", "echeance",
    "échéance", "comptes", "confie", "confié", "cabinet", "mandat",
}


_CONNECTOR = {"de", "du", "des", "et", "la", "le", "les", "d", "l", "-", "&"}

# Words that end a *personal* name but are ordinary parts of a company name.
# "Banque Tuniso-Koweitienne" must survive as an entity while still stopping a
# person capture that runs on into it.
_ENTITY_ALLOWED = {"banque", "societe", "société", "sa", "sarl", "conseil", "the"}
_ENTITY_STOP = _NAME_STOP - _ENTITY_ALLOWED


def is_plausible_entity(name: str) -> bool:
    """True only for a string that is confidently a company name.

    The capture preceding "représentée par" can begin mid-sentence and pull in
    the verb clause before it ("L'Assemblée Générale Ordinaire nomme"). Since a
    wrong entity is worse than none - it would become a node and a corporate
    board seat - this accepts only what clearly reads as a name: every token
    either capitalised or a connector, no year, and either several tokens or a
    single all-capitals acronym.
    """
    n = flat(name).strip()
    if not (3 <= len(n) <= 70):
        return False
    toks = [t for t in re.split(r"[\s]+", n) if t]
    if not toks:
        return False
    if any(re.fullmatch(r"(?:19|20)\d{2}", t) for t in toks):
        return False
    if any(norm(t).strip(".,;:'’-") in _ENTITY_STOP for t in toks):
        return False
    for t in toks:
        core = norm(t).strip(".,;:'’-")
        # Punctuation between name parts ("Banque Tuniso-Koweitienne - BTK")
        # carries no capital and must not fail the test.
        if not core or core in _CONNECTOR:
            continue
        if not re.match(r"[A-ZÀ-Ý]", t):
            return False
    named = [t for t in toks
             if (norm(t).strip(".,;:'’-") or "") not in _CONNECTOR
             and norm(t).strip(".,;:'’-")]
    if len(named) >= 2:
        return True
    return bool(named) and named[0].isupper() and len(named[0]) >= 2


def trim_name(name: str) -> str:
    """Cut a captured name at the first word that cannot belong to one."""
    toks = flat(name).split()
    out: list[str] = []
    for tok in toks:
        if norm(tok).strip(".,;:'’-") in _NAME_STOP:
            break
        out.append(tok)
    return " ".join(out).strip(" .,;:-'’")


# "monsieur yacine friaa", "Madame Rim Lakhoua", "M. Adel Grar"
_PERSON = re.compile(r"\b" + _TITLE + _NAME)

# A legal person on the board, with the individual who sits for it.
_REPRESENTED = re.compile(
    r"(?P<entity>[^,;:]{3,70}?)\s+(?i:repr[ée]sent[ée]e?s?\s+par)\s+" + _TITLE +
    rf"(?P<rep>{_NAME_TOKEN}(?:\s+{_NAME_TOKEN}){{0,3}})",
)

ROLE_PATTERNS = (
    ("administrateur_independant", r"administrateur\s+independant|administratrice\s+independante"),
    ("administrateur_representant_etat", r"administrateur\s+representant\s+l'?etat"),
    ("president_directeur_general", r"president\s+directeur\s+general|\bpdg\b"),
    ("president_conseil", r"president\s+du\s+conseil"),
    ("directeur_general", r"directeur\s+general"),
    ("commissaire_aux_comptes", r"commissaire\s+aux\s+comptes|co-?commissaire"),
    ("membre_comite", r"membre\s+du\s+comite"),
    ("censeur", r"\bcenseur\b"),
    ("administrateur", r"\badministrat(?:eur|rice)s?\b"),
)


def find_role(segment: str) -> str | None:
    n = norm(segment)
    for name, pat in ROLE_PATTERNS:
        if re.search(pat, n):
            return name
    return None


# --------------------------------------------------------------------------
# event typing
# --------------------------------------------------------------------------

# Ordered most specific first: a cooptation ratification also contains
# "nomination" vocabulary, and a non-renewal contains "renouvel".
EVENT_PATTERNS = (
    ("cooptation_ratified", r"ratifi\w*\s+(?:la\s+)?cooptation|ratifi\w*\s+la\s+nomination"),
    ("cooptation", r"\bcoopt"),
    ("non_renewal", r"ne\s+pas\s+renouveler|non\s+renouvellement"),
    ("renewal", r"renouvel\w*\s+(?:le\s+)?mandat|renouvellement\s+du\s+mandat"),
    ("termination", r"met\s+fin\s+(?:aux|au)\s+fonction|revoque|revocation|"
                    r"demission|constate\s+la\s+demission"),
    ("mandate_expiry", r"constate\s+(?:que\s+)?(?:l')?(?:expiration|echeance)|"
                       r"arrive\s+a\s+echeance|expiration\s+du\s+mandat"),
    ("appointment", r"decide\s+de\s+nommer|\bnomme\b|procede\s+a\s+la\s+nomination|"
                    r"\belit\b|designe\s+en\s+qualite|nomination\s+de"),
    ("remuneration", r"jetons?\s+de\s+presence|remuneration\s+des\s+administrateurs"),
    ("quitus", r"donne\s+quitus"),
)

# Resolutions that change who sits on a board or audits it.
GOVERNANCE_EVENTS = {
    "appointment", "cooptation", "cooptation_ratified", "renewal",
    "non_renewal", "termination", "mandate_expiry",
}


def classify_resolution(body: str) -> str | None:
    n = norm(body)
    for name, pat in EVENT_PATTERNS:
        if re.search(pat, n):
            return name
    return None


# --------------------------------------------------------------------------
# term and succession
# --------------------------------------------------------------------------

_TERM_YEARS = re.compile(
    r"(?:pour\s+une\s+)?dur[ée]e\s+de\s+(?P<n>trois|deux|un|une|quatre|cinq|six|\d{1,2})\s+"
    r"(?:\(\d+\)\s*)?ann[ée]es?",
    re.I,
)
_WORD_NUM = {"un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6}

# "expirant lors de l'assemblée générale ordinaire qui statuera sur les états
# financiers de l'exercice 2023"
_TERM_END = re.compile(
    r"(?:expirant|qui\s+statuera|statuant)[^.]{0,120}?exercice\s+(?P<y>(?:19|20)\d{2})",
    re.I,
)

# "en remplacement de monsieur marouene ben slimene"
_REPLACES = re.compile(
    r"(?i:en\s+remplacement\s+d(?:e|u|es))\s+(?:" + _TITLE + r")?" + _NAME,
)

# "décidée par le conseil d'administration du 19 mai 2026"
# The filings use a typographic apostrophe, so a straight-quote pattern never
# matches here. Patterns that run against norm() are unaffected; this one reads
# the raw text.
_BOARD_DECISION = re.compile(
    r"conseil\s+d['’]administration\s+du\s+(?P<d>[^.,;:]{4,40})", re.I
)

_ADOPTED = re.compile(
    r"adopt[ée]e?\s+a\s+l'unanimite|approuv[ée]e?\s+a\s+l'unanimite", re.I
)
_MAJORITY = re.compile(r"a\s+la\s+majorit[ée]", re.I)
_REJECTED = re.compile(r"n'a\s+pas\s+[ée]t[ée]\s+adopt|rejet[ée]e?", re.I)


def term_end_year(body: str) -> int | None:
    m = _TERM_END.search(norm(body))
    return int(m.group("y")) if m else None


def term_years(body: str) -> int | None:
    m = _TERM_YEARS.search(norm(body))
    if not m:
        return None
    v = m.group("n")
    return _WORD_NUM.get(v.lower(), int(v) if v.isdigit() else None)


def adoption_status(body: str) -> str | None:
    n = norm(body)
    if _REJECTED.search(n):
        return "rejected"
    if _ADOPTED.search(n):
        return "adopted_unanimously"
    if _MAJORITY.search(n):
        return "adopted_by_majority"
    return None


# --------------------------------------------------------------------------
# extraction
# --------------------------------------------------------------------------

# Clauses that introduce the person leaving rather than the one arriving.
_OUTGOING_CONTEXT = re.compile(
    r"en\s+remplacement\s+d|d[ée]part\s+d|d[ée]mission\s+d|"
    r"fin\s+(?:des?\s+)?fonctions?\s+d|retrait\s+d|d[ée]c[èe]s\s+d",
)


# Officers of the meeting itself, and other roles that are not board seats.
_NOT_A_DIRECTOR = re.compile(
    r"commissaire|scrutateur|secretaire\s+de\s+seance|president\s+de\s+seance", re.I
)


def people_in(body: str) -> list[dict[str, Any]]:
    """Return the people a resolution names, with any entity they represent."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Legal-person seats first, so the representative is attached to its entity
    # rather than read as a director in his or her own right.
    for m in _REPRESENTED.finditer(body):
        entity = flat(m.group("entity")).strip(" .,;:-«»\"")
        entity = re.sub(r"^(?:la|le|les|l')\s+", "", entity, flags=re.I)
        entity = re.sub(r"^soci[ée]t[ée]\s+", "", entity, flags=re.I)
        # The capture can start mid-sentence and pick up a trailing year or
        # punctuation from the previous clause ("2023 -AMEN INVEST").
        entity = re.sub(r"^[^A-Za-zÀ-Ý]+", "", entity).strip(" .,;:-–()«»\"")
        # Drop leading connectives ("et Amen Bank" -> "Amen Bank").
        toks = entity.split()
        while toks and norm(toks[0]).strip(".,;:'’-") in _CONNECTOR:
            toks.pop(0)
        entity = " ".join(toks)
        if not is_plausible_entity(entity):
            entity = ""
        rep = trim_name(m.group("rep"))
        if not is_plausible_party(rep):
            continue
        key = norm(rep)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "person_name_raw": rep,
            "entity_name_raw": entity if is_plausible_party(entity) else None,
            "seat_holder_type": "legal_person" if is_plausible_party(entity) else "person",
        })

    for m in _PERSON.finditer(body):
        name = trim_name(m.group("name"))
        if not is_plausible_party(name):
            continue
        key = norm(name)
        if key in seen:
            continue
        # A resolution names the outgoing person as well as the incoming one:
        # "prend acte du départ de M. X ... coopter M. Y en remplacement de M. X".
        # Names introduced by a departure or replacement clause are the person
        # leaving, and are recorded as the predecessor rather than the appointee.
        before = norm(body[max(0, m.start() - 60):m.start()])
        if _OUTGOING_CONTEXT.search(before):
            continue
        seen.add(key)
        out.append({
            "person_name_raw": name,
            "entity_name_raw": None,
            "seat_holder_type": "person",
        })
    return out


def parse_resolution(num: int | None, body: str) -> dict[str, Any] | None:
    """Extract one governance decision from a single resolution."""
    etype = classify_resolution(body)
    if etype is None or etype not in GOVERNANCE_EVENTS:
        return None
    role = find_role(body)
    # An auditor appointment is a real decision but not a board seat; it is
    # kept, flagged by its role, so it can be filtered either way.
    if role is None and _NOT_A_DIRECTOR.search(norm(body)):
        role = "commissaire_aux_comptes"

    rep = _REPLACES.search(body)
    decision = _BOARD_DECISION.search(body)
    people = people_in(body)
    replaces = trim_name(rep.group("name")) if rep else None
    if replaces:
        people = [p for p in people if norm(p["person_name_raw"]) != norm(replaces)]
    return {
        "resolution_number": num,
        "event_type": etype,
        "role": role,
        "people": people,
        "n_people": len(people),
        "replaces_name_raw": replaces,
        "board_decision_date": parse_date(decision.group("d")) if decision else None,
        "term_years": term_years(body),
        "term_end_year": term_end_year(body),
        "adoption": adoption_status(body),
        "excerpt": flat(body)[:400],
    }


def parse_document(text: str) -> dict[str, Any]:
    """Parse a filing into its meeting header and governance resolutions."""
    kind, date = meeting_info(text)
    events = []
    for num, body in split_resolutions(text):
        rec = parse_resolution(num, body)
        if rec:
            events.append(rec)
    return {"meeting_kind": kind, "meeting_date": date, "events": events}
