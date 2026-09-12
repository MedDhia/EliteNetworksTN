"""Entity normalisation and canonical ID assignment.

Names in Tunisian filings vary in three ways that matter for a network:

* **Orthography.** Accents, punctuation and spacing drift ("COTIF SICAR",
  "COTIF-SICAR", "Cotif Sicar"); Arabic and French forms coexist.
* **Word order.** Persons appear as "Hassine DOGHRI" and as "DOGHRI HASSINE".
* **Legal form.** "Serenity Capital Finance Holding SA" and "Serenity Capital
  Finance Holding" are the same firm.

The matching key therefore strips accents, punctuation and legal-form suffixes,
and - for persons only - sorts the remaining tokens, so that word order stops
mattering. Honorifics are removed before any of this.

Two deliberate limitations, both recorded in the codebook:

1. Homonymous individuals are merged. Tunisian elite families reuse given names
   across generations, so a shared name is not proof of a shared person.
2. Automated clustering is conservative: it merges only on exact key equality.
   Anything looser is left for the researcher to confirm through
   ``config/entity_overrides.csv``, which always wins over the automatic result.
"""

from __future__ import annotations

import csv
import hashlib
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OVERRIDES = ROOT / "config" / "bourse_entity_overrides.csv"

# --------------------------------------------------------------------------
# normalisation
# --------------------------------------------------------------------------

_HONORIFIC = re.compile(
    r"\b(m|mr|mme|mlle|dr|pr|me|monsieur|madame|mademoiselle|prof|sidi|hadj)\b\.?\s*",
    re.I,
)

# Legal forms and investment-vehicle suffixes. Removed from the *matching key*
# only: the display name keeps them, because "COTIF SICAR" and "COTIF SICAF"
# would otherwise be indistinguishable, so SICAR/SICAF/SICAV are kept.
_LEGAL_SUFFIX = re.compile(
    r"\b(s\.?a\.?r\.?l|s\.?a\.?s|s\.?a|sarl|snc|scs|sca|spa|ste|societe|"
    r"company|co|corp|corporation|ltd|limited|plc|gmbh|group|groupe|"
    r"et\s+cie|and\s+co)\b\.?",
    re.I,
)

_PUNCT = re.compile(r"[^\w\s]+", re.UNICODE)
_WS = re.compile(r"\s+")

# "Etat Tunisien (représenté par Monsieur Abdessatar BEN SAAD)" is the state,
# not a separate holder. Board tables name the representative alongside the
# institution; without stripping it the institution becomes a second node and
# its stake is counted twice.
_REPRESENTED_BY = re.compile(
    r"\s*[\(\[][^)\]]*\b(represent\w*|agissant|pour\s+le\s+compte)\b[^)\]]*[\)\]]",
    re.I,
)

# A dotted initialism and its undotted twin are one name: "Financière
# Tunisienne S.A" and "Financière Tunisienne SA". Punctuation stripping alone
# turns the first into the tokens "s" "a", which no legal-form rule removes.
_DOTTED_INITIALISM = re.compile(r"\b((?:\w\.){1,4}\w)\b")

# Footnote markers ride along on the last token: "Moncef CHAFFAR1", "CTAMA*".
# Asterisks fall to _PUNCT; digits are word characters and survive.
_FOOTNOTE_DIGITS = re.compile(r"(?<=[^\W\d_]{3})\d{1,2}\b")

# Vehicle markers that must survive normalisation: they distinguish sibling
# entities inside one group.
_KEEP = {"sicar", "sicaf", "sicav", "holding", "bank", "banque", "leasing",
         "assurance", "assurances", "invest", "capital", "immobiliere", "factoring"}


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def base_normalise(name: str) -> str:
    s = strip_accents(name or "")
    s = _REPRESENTED_BY.sub(" ", s).lower()
    s = s.replace("’", " ").replace("'", " ").replace("-", " ")
    # Collapse dotted initialisms before punctuation is stripped, or "s.a"
    # becomes two single letters instead of the legal form "sa".
    s = _DOTTED_INITIALISM.sub(lambda m: m.group(1).replace(".", ""), s)
    s = _FOOTNOTE_DIGITS.sub("", s)
    s = _HONORIFIC.sub(" ", s)
    s = _PUNCT.sub(" ", s)
    return _WS.sub(" ", s).strip()


# Cells that are not entities at all. Table geometry occasionally hands the
# name column an address line or a mandate period; left in, each becomes a node
# with holdings or a board seat attached.
_NOT_AN_ENTITY = (
    re.compile(r"^\d{4}\s*[-–—/]\s*\d{2,4}$"),                  # "2024 – 2026"
    re.compile(r"\b(etage|immeuble|appartement|bureau\s+n|boite\s+postale)\b"),
    re.compile(r"^(rue|avenue|boulevard|impasse|route)\b"),
    re.compile(r"^[\d\s]+$"),                                    # bare numbers
)


def is_not_an_entity(name: str) -> bool:
    """True for cells that name a place or a period rather than an actor."""
    n = base_normalise(name)
    return not n or any(p.search(n) for p in _NOT_AN_ENTITY)


def has_representative(name: str) -> bool:
    """True for "<institution> (représenté par <person>)".

    Accents are stripped first: the pattern is written unaccented, and the
    filings write "représenté".
    """
    return bool(_REPRESENTED_BY.search(strip_accents(name or "")))


def demote_person_hint(name: str, hint: str | None) -> str | None:
    """Drop a "person" hint from a cell that names a represented institution.

    "Kuwait Investment Authority - KIA (représenté par M. Al Munaifi)" sits in
    a board-holdings column, so the column hint says person. The subject is the
    institution holding the seat, not the individual filling it, and the
    parenthetical is the more specific evidence. Left alone, the institution
    becomes a second node and its stake is counted twice.
    """
    if hint == "person" and has_representative(name):
        return None
    return hint


def _drop_redundant_acronym(toks: list[str]) -> list[str]:
    """Drop a trailing acronym that merely restates the name.

    Filings write both 'Arab Tunisian Bank' and 'Arab Tunisian Bank "ATB"', and
    both 'Kuwait Investment Authority' and 'Kuwait Investment Authority - KIA'.
    Without this the same holder becomes two nodes and its stake is counted
    twice. Only an acronym matching the initials of the preceding words is
    removed, so a genuine suffix is left alone.
    """
    if len(toks) < 3:
        return toks
    last = toks[-1]
    if not (2 <= len(last) <= 6) or not last.isalpha():
        return toks
    initials = "".join(t[0] for t in toks[:-1])
    if last == initials or initials.endswith(last):
        return toks[:-1]
    return toks


def org_key(name: str) -> str:
    """Matching key for organisations: order-preserving, legal forms dropped."""
    s = base_normalise(name)
    toks = [t for t in s.split() if t]
    toks = [t for t in toks if t in _KEEP or not _LEGAL_SUFFIX.fullmatch(t)]
    # Drop standalone single letters left by initialisms ("u b c i" -> "ubci").
    if toks and all(len(t) == 1 for t in toks):
        return "".join(toks)
    toks = _drop_redundant_acronym(toks)
    return " ".join(toks)


def person_key(name: str) -> str:
    """Matching key for persons: order-insensitive, so surname-first matches."""
    s = base_normalise(name)
    toks = sorted(t for t in s.split() if len(t) > 1)
    return " ".join(toks)


# --------------------------------------------------------------------------
# type classification
# --------------------------------------------------------------------------

STATE_PATTERNS = (
    r"\betat\b", r"\bministere\b", r"\btresor\b", r"\bcnss\b", r"\bcnrps\b",
    r"\bcaisse\s+(nationale|des\s+depots)\b", r"\bcdc\b", r"\boffice\b",
    r"\bsteg\b", r"\betap\b", r"\bsonede\b", r"\bstir\b", r"\brtt\b",
    r"\bpublique?s?\b.*\bparticipation", r"\bdomaine\s+de\s+l\s*etat\b",
    r"\bsociete\s+nationale\b", r"\bbanque\s+centrale\b", r"\bconfiscat",
)
FUND_PATTERNS = (
    r"\bsicav\b", r"\bsicar\b", r"\bsicaf\b", r"\bfcp\b", r"\bfonds\b",
    r"\bopcvm\b", r"\bmutual\b", r"\bpension\b",
)
FIRM_PATTERNS = (
    r"\bholding\b", r"\bbank\b", r"\bbanque\b", r"\bsociete\b", r"\bgroupe\b",
    r"\bassurances?\b", r"\bleasing\b", r"\bsa\b", r"\bsarl\b", r"\bcompagnie\b",
    r"\bindustri", r"\bimmobili", r"\binternational\b", r"\bpartners?\b",
    r"\bcapital\b", r"\binvest", r"\bfactoring\b", r"\bcorporation\b", r"\bltd\b",
    # Sector and activity words that mark a corporate name even when no legal
    # form is written out ("BNP PARIBAS IRB PARTICIPATIONS").
    r"\bparticipations?\b", r"\bservices?\b", r"\btechnolog", r"\bdeveloppement\b",
    r"\bgestion\b", r"\bfinanc", r"\bcommerc", r"\bdistribution\b", r"\btrading\b",
    r"\bconsulting\b", r"\benergie?\b", r"\btelecom", r"\bceramic", r"\bciments?\b",
    r"\bgaz\b", r"\bpetrol", r"\btransport", r"\bagricole\b", r"\btunisie(?:nne?s?)?\b",
    r"\bmarketing\b", r"\benergies\b", r"\bmedical", r"\bpharma", r"\bautomobile",
    r"\bmaghreb", r"\bafrique\b", r"\bafrican\b", r"\bunion\b", r"\bcentrale\b",
)

_RE_STATE = re.compile("|".join(STATE_PATTERNS))
_RE_FUND = re.compile("|".join(FUND_PATTERNS))
_RE_FIRM = re.compile("|".join(FIRM_PATTERNS))

# A name written SURNAME-first in caps, or two-to-four capitalised tokens with
# no organisational marker, reads as a natural person.
_PUBLIC_LABEL = re.compile(
    r"^(public|autres?|divers|flottant|total|personnes?\s+(physiques?|morales?)|"
    r"actionnaires?|petits?\s+porteurs?|nominatifs?|au\s+porteur|"
    r"salaries?|personnel|rompus)\b"
)

ENTITY_TYPES = ("person", "firm", "fund", "state", "aggregate", "unknown")

# Totals rows survive extraction in disguise when a PDF letter-spaces or
# overprints them: "T O T A L", "TOOTAL", "ACCTIONNAIRES TUNISIENS". Left alone
# they become nodes holding 100% of a firm.
_AGG_WORDS = ("total", "actionnaires", "actionnairestunisiens", "soustotal",
              "public", "flottant", "divers", "autres")


def _is_spaced_aggregate(n: str) -> bool:
    squashed = re.sub(r"\s+", "", n)
    # Collapse runs of a repeated letter, which is how overprinted bold text
    # extracts: "TOOTAL" -> "total", "ACCTIONNAIRES" -> "actionnaires".
    dedoubled = re.sub(r"(.)\1+", r"\1", squashed)
    # Exact match only: a prefix test would swallow TotalEnergies, a real
    # listed issuer, along with the totals rows.
    return any(
        squashed == w or dedoubled == re.sub(r"(.)\1+", r"\1", w)
        for w in _AGG_WORDS
    )


def classify(name: str, *, hint: str | None = None) -> str:
    """Classify a raw name into an entity type.

    ``hint`` allows the caller to pass through structural knowledge - e.g. a
    board table's "represented by" column always names a natural person.
    """
    hint = demote_person_hint(name, hint)
    if hint in ENTITY_TYPES:
        return hint
    n = base_normalise(name)
    if not n:
        return "unknown"
    if _PUBLIC_LABEL.match(n) or _is_spaced_aggregate(n):
        return "aggregate"
    if _RE_STATE.search(n):
        return "state"
    if _RE_FUND.search(n):
        return "fund"
    if _RE_FIRM.search(n):
        return "firm"
    toks = n.split()
    # Personal names in this corpus are two or three tokens. Four or more
    # without any corporate marker are far more often firms whose sector word
    # we have not catalogued than they are people.
    if 2 <= len(toks) <= 3 and all(t.isalpha() for t in toks):
        return "person"
    if len(toks) >= 4:
        return "firm"
    # A single token is an acronym or trade name - CARTE, GAT, FINOR, SERVITEL.
    # Nobody appears in these tables under one name, so it is not a person.
    if len(toks) == 1 and len(toks[0]) >= 2:
        return "firm"
    return "unknown"


def matching_key(name: str, etype: str) -> str:
    return person_key(name) if etype == "person" else org_key(name)


def make_id(etype: str, key: str) -> str:
    """Stable, content-derived ID: rebuilding the dataset reproduces it."""
    prefix = {"person": "P", "firm": "F", "fund": "U", "state": "S",
              "aggregate": "A", "unknown": "X"}.get(etype, "X")
    h = hashlib.sha1(f"{etype}|{key}".encode("utf-8")).hexdigest()[:10]
    return f"{prefix}{h}"


# --------------------------------------------------------------------------
# registry
# --------------------------------------------------------------------------


def load_overrides() -> dict[str, dict[str, str]]:
    """Researcher corrections: raw_name -> {entity_id, entity_type, canonical_name}.

    Overrides always win. This is the intended place to record judgements the
    matcher cannot make - that two differently-named entities are the same, or
    that two identically-named people are not.
    """
    if not OVERRIDES.exists():
        return {}
    out = {}
    with OVERRIDES.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            raw = (row.get("raw_name") or "").strip()
            if raw:
                out[base_normalise(raw)] = {
                    k: (v or "").strip() for k, v in row.items() if k != "raw_name"
                }
    return out


class Resolver:
    """Assigns canonical IDs to raw names, remembering every alias it saw."""

    def __init__(self) -> None:
        self.overrides = load_overrides()
        self._by_key: dict[tuple[str, str], str] = {}
        self._display: dict[str, Counter] = defaultdict(Counter)
        self._types: dict[str, str] = {}
        self._aliases: dict[str, set[str]] = defaultdict(set)
        self._evidence: dict[str, Counter] = defaultdict(Counter)

    def add_evidence(self, raw: str, etype: str) -> None:
        """Record a type observed from table *structure* rather than spelling.

        Some columns are unambiguous by construction: a "represented by" cell is
        always a natural person, a subsidiary cell always an organisation. Names
        seen in those positions carry their type over to every other position
        they appear in, which is what lets "Altea Packaging" be read as a firm in
        a shareholder table where the string alone looks like a personal name.
        """
        etype = demote_person_hint(raw, etype)
        name = base_normalise(raw)
        if name and etype in ENTITY_TYPES:
            self._evidence[name][etype] += 1

    def _typed(self, name: str, hint: str | None) -> str:
        hint = demote_person_hint(name, hint)
        if hint in ENTITY_TYPES:
            return hint
        ev = self._evidence.get(base_normalise(name))
        if ev:
            best, n = ev.most_common(1)[0]
            # Structural evidence outranks the string heuristic, but never
            # overrides an explicit aggregate label ("Public", "Total").
            if not _PUBLIC_LABEL.match(base_normalise(name)):
                return best
        return classify(name)

    def resolve(self, raw: str, *, hint: str | None = None) -> tuple[str, str] | tuple[None, None]:
        name = (raw or "").strip()
        if not name:
            return None, None

        ov = self.overrides.get(base_normalise(name))
        # An override is a researcher's judgement and always wins, including
        # over the not-an-entity test.
        if ov is None and is_not_an_entity(name):
            return None, None
        if ov and ov.get("entity_id"):
            eid = ov["entity_id"]
            etype = ov.get("entity_type") or self._typed(name, hint)
            self._types[eid] = etype
            disp = ov.get("canonical_name") or name
            self._display[eid][disp] += 1000  # dominate the display vote
            self._aliases[eid].add(name)
            return eid, etype

        etype = (ov.get("entity_type") if ov else None) or self._typed(name, hint)
        key = matching_key(name, etype)
        if not key:
            return None, None
        eid = self._by_key.get((etype, key))
        if eid is None:
            eid = make_id(etype, key)
            self._by_key[(etype, key)] = eid
        self._types[eid] = etype
        self._display[eid][name] += 1
        self._aliases[eid].add(name)
        return eid, etype

    def canonical_name(self, eid: str) -> str:
        """Most frequently observed spelling wins; ties broken by length.

        Honorifics are stripped from personal names first, so that "M. Hakim
        DOGHRI" and "Hakim DOGHRI" vote for the same display form.
        """
        c = self._display.get(eid)
        if not c:
            return ""
        if self._types.get(eid) == "person":
            merged: Counter = Counter()
            for name, n in c.items():
                merged[_HONORIFIC.sub("", name).strip(" .,;:-")] += n
            c = merged
        best = max(c.items(), key=lambda kv: (kv[1], len(kv[0])))
        return best[0]

    def entity_rows(self) -> list[dict]:
        rows = []
        for eid, etype in sorted(self._types.items()):
            aliases = sorted(self._aliases[eid])
            rows.append(
                {
                    "entity_id": eid,
                    "entity_type": etype,
                    "canonical_name": self.canonical_name(eid),
                    "n_aliases": len(aliases),
                    "aliases": " | ".join(aliases),
                }
            )
        return rows

    def alias_rows(self) -> list[dict]:
        rows = []
        for eid, aliases in sorted(self._aliases.items()):
            for a in sorted(aliases):
                rows.append(
                    {
                        "entity_id": eid,
                        "entity_type": self._types.get(eid, "unknown"),
                        "alias_raw": a,
                        "matching_key": matching_key(a, self._types.get(eid, "unknown")),
                    }
                )
        return rows
