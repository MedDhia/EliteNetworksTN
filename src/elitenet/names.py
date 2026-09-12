"""Name and organisation normalisation.

The seed sheet stores ASCII uppercase names with hyphenated Arabic particles
(``HATEM BEN-SALEM``); the gazette prints mixed case with spaces and accents
(``Hatem Ben Salem``). Everything here exists to make those two spellings, and
the transliteration and OCR variants around them, compare equal -- while never
silently merging information we should keep separate (a married name, for
instance, is split out rather than folded in).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache

from .paths import load_config


# --------------------------------------------------------------------------- #
# rule tables
# --------------------------------------------------------------------------- #

@lru_cache(maxsize=1)
def _rules() -> dict:
    cfg = load_config("name_variants")
    # token -> canonical member of its equivalence class (the first listed)
    variant_map: dict[str, str] = {}
    for cls in cfg["equivalence_classes"]:
        canon = cls[0]
        for member in cls:
            variant_map[member] = canon
    return {
        "particles": set(cfg["particles"]),
        "collapse_doubled": cfg.get("identity_orthography", {}).get(
            "collapse_doubled_consonants", True),
        "honorifics": set(cfg["honorifics"]),
        "spouse_markers": set(cfg["spouse_markers"]),
        "variant_map": variant_map,
        "org_legal_forms": set(cfg["org_legal_forms"]),
        "ocr_confusions": [tuple(p) for p in cfg["ocr_confusions"]],
    }


def strip_accents(text: str) -> str:
    """Remove diacritics; 'Béji' -> 'Beji'. Also normalises curly apostrophes."""
    text = text.replace("’", "'").replace("ʼ", "'").replace("`", "'")
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


_NONWORD = re.compile(r"[^A-Z0-9' ]+")
_WS = re.compile(r"\s+")


_DOUBLE_CONS = re.compile(r"([BCDFGJKLMNPQRSTVXZ])\1+")


def collapse_doubles(token: str) -> str:
    """KAMMOUN -> KAMOUN, HAMMAMI -> HAMAMI.

    A spelling variant of one string, so it is safe to apply to identifiers.
    Vowels are left alone: AA and OO carry meaning (NAAMA, BOURICHA).
    """
    return _DOUBLE_CONS.sub(r"\1", token)


def _basic_clean(text: str) -> str:
    text = strip_accents(text or "").upper()
    text = text.replace("-", " ").replace("_", " ")
    text = _NONWORD.sub(" ", text)
    return _WS.sub(" ", text).strip()


# --------------------------------------------------------------------------- #
# person names
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class PersonName:
    """A parsed person name plus the keys used to compare it."""

    raw: str
    tokens: tuple[str, ...] = ()
    normalised: str = ""          # IDENTITY key: orthographic normalisation only
    match_tokens: tuple[str, ...] = ()
    match_key: str = ""           # MATCHING key: transliteration variants folded in
    married_name: str = ""        # text following 'epouse' / 'nee' / 'veuve'
    surname_key: str = ""         # last token of match_key, for blocking
    first_initial: str = ""       # first initial of match_key, for blocking

    @property
    def is_empty(self) -> bool:
        return not self.tokens


def parse_person(raw: str) -> PersonName:
    """Parse and normalise a person name from either source.

    Particles are fused to the following token so ``BEN-SALEM``, ``Ben Salem``
    and ``BENSALEM`` all yield ``BENSALEM``. A married-name marker splits the
    string: what follows is returned separately, never merged into the name.
    """
    rules = _rules()
    cleaned = _basic_clean(raw)
    if not cleaned:
        return PersonName(raw=raw or "")

    tokens = cleaned.split(" ")

    # drop honorifics anywhere in the string
    tokens = [t for t in tokens if t not in rules["honorifics"]]

    # split on a married-name marker
    married: list[str] = []
    for i, tok in enumerate(tokens):
        if tok in rules["spouse_markers"]:
            married = tokens[i + 1 :]
            tokens = tokens[:i]
            break

    # fuse particles onto the following token: BEN + SALEM -> BENSALEM
    fused: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in rules["particles"] and i + 1 < len(tokens):
            fused.append(tok + tokens[i + 1])
            i += 2
        else:
            fused.append(tok)
            i += 1

    # IDENTITY key: orthographic normalisation only. Transliteration variants are
    # deliberately NOT folded in here -- an identifier is irreversible, and
    # MOHAMED vs MHAMMED is a judgement the resolver should score, not assume.
    ident = tuple(collapse_doubles(t) if rules["collapse_doubled"] else t for t in fused)
    ident = tuple(t for t in ident if t)

    if not ident:
        return PersonName(raw=raw or "", married_name=" ".join(married))

    # MATCHING key: variants folded in, for blocking and similarity scoring only.
    vm = rules["variant_map"]
    match = tuple(vm.get(t, t) for t in ident)

    return PersonName(
        raw=raw or "",
        tokens=ident,
        normalised=" ".join(ident),
        match_tokens=match,
        match_key=" ".join(match),
        married_name=" ".join(married),
        surname_key=match[-1],
        first_initial=match[0][0] if match[0] else "",
    )


def apply_ocr_repairs(token: str) -> set[str]:
    """Return plausible OCR-repaired spellings of a token, including itself.

    Used only as a fallback when a name fails to match, never as a primary key.
    """
    out = {token}
    for a, b in _rules()["ocr_confusions"]:
        for src, dst in ((a, b), (b, a)):
            if src in token:
                out.add(token.replace(src, dst))
    return out


# --------------------------------------------------------------------------- #
# organisation names
# --------------------------------------------------------------------------- #

_ACRONYM_TAIL = re.compile(r"\s+([A-Z]{2,10})$")


def _is_initialism(candidate: str, head_tokens: list[str]) -> bool:
    """True if `candidate` reads as an initialism of `head_tokens`.

    The seed sheet is entirely uppercase, so case cannot distinguish an acronym
    from an ordinary trailing word: "BANQUE INTERNATIONALE ARABE DE TUNISIE"
    would otherwise lose TUNISIE. Testing the initials settles it -- BIAT is an
    initialism of that name, TUNISIE is not.
    """
    forms = _rules()["org_legal_forms"]
    content = [w for w in head_tokens if w not in forms]
    if len(content) < 2 or len(candidate) < 2:
        return False
    initials = "".join(w[0] for w in content)
    if candidate == initials:
        return True
    # allow an initialism that skips some words, provided it covers most of them
    it = iter(initials)
    if all(ch in it for ch in candidate) and len(candidate) >= max(2, len(initials) - 2):
        return True
    return False


@dataclass(frozen=True)
class OrgName:
    raw: str
    normalised: str = ""          # IDENTITY key: generic legal forms removed only
    match_key: str = ""           # MATCHING key: also doubled-consonant collapsed
    acronym: str = ""             # trailing acronym split off the seed label
    label: str = ""               # raw minus the trailing acronym
    content_tokens: tuple[str, ...] = field(default=())


def parse_org(raw: str) -> OrgName:
    """Normalise an organisation name and split any glued trailing acronym.

    The seed sheet appends acronyms to full names
    (``BANQUE INTERNATIONALE ARABE DE TUNISIE BIAT``). The acronym is a useful
    alternative name, so it is separated rather than discarded.
    """
    text = strip_accents(raw or "").upper().strip()
    if not text:
        return OrgName(raw=raw or "")

    acronym = ""
    label = text
    m = _ACRONYM_TAIL.search(text)
    if m:
        candidate = m.group(1)
        head = text[: m.start()].strip()
        # Keep it as an acronym only if it is not a generic legal-form marker
        # (SA, SARL -- stripped as forms) and it actually reads as an initialism.
        if (
            candidate not in _rules()["org_legal_forms"]
            and candidate not in head.split()
            and _is_initialism(candidate, head.split())
        ):
            acronym = candidate
            label = head

    cleaned = _basic_clean(label)
    forms = _rules()["org_legal_forms"]
    toks = tuple(t for t in cleaned.split(" ") if t and t not in forms)

    return OrgName(
        raw=raw or "",
        normalised=" ".join(toks),
        match_key=" ".join(collapse_doubles(t) for t in toks),
        acronym=acronym,
        label=label,
        content_tokens=toks,
    )


# --------------------------------------------------------------------------- #
# stable identifiers
# --------------------------------------------------------------------------- #

_ID_SAFE = re.compile(r"[^A-Z0-9]+")


def _slug(text: str, limit: int = 60) -> str:
    slug = _ID_SAFE.sub("_", strip_accents(text or "").upper()).strip("_")
    return slug[:limit].rstrip("_")


def person_id(name: str) -> str:
    """Deterministic id: PERSON_<SURNAME>_<GIVEN...>."""
    p = parse_person(name)
    if p.is_empty:
        return "PERSON_UNKNOWN"
    ordered = (p.tokens[-1],) + p.tokens[:-1]
    return "PERSON_" + _slug(" ".join(ordered))


def org_id(name: str, node_type: str = "ORGANIZATION") -> str:
    """Deterministic id prefixed by node type so namespaces never collide."""
    prefix = {
        "COMPANY": "CO",
        "ORGANIZATION": "ORG",
        "GOVERNMENT": "GOV",
        "GOVERNMENTAL ORGANIZATION": "GOVORG",
        "PARTY": "PARTY",
        "PARTY STRUCTURE": "PARTYSTR",
        "PARLIAMENTARY BLOC": "BLOC",
        "CONSORTIUM": "CONS",
    }.get(node_type, "ORG")
    o = parse_org(name)
    # The trailing acronym is deliberately excluded from the identifier: the seed
    # sheet glues it on ("... DE TUNISIE BIAT") while the gazette does not, so
    # including it would split one bank into two nodes. It is kept as an alt name.
    core = o.normalised or _basic_clean(name)
    return f"{prefix}_" + _slug(core)


def node_id(name: str, node_type: str) -> str:
    return person_id(name) if node_type == "PERSON" else org_id(name, node_type)
