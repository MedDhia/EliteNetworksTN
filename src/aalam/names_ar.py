"""Arabic name normalisation, transliteration and identifier minting.

``src/elitenet/names.py`` cannot be reused here. It is not source-agnostic but
Latin-agnostic: its ``_NONWORD`` class is ``[^A-Z0-9' ]+`` and it uppercases
before filtering, so every Arabic string reduces to the empty one and every
person becomes ``PERSON_UNKNOWN``. This module keeps that file's *design* and
replaces its rules.

The design, restated, because it is what makes identifiers safe to publish:

``display``   the name as printed, untouched.
``normalised`` the IDENTITY key. Orthographic folding only -- particles fused,
              the article dropped, titles removed. ``person_id`` hashes this.
``match_key`` the MATCHING key. Adds the transliteration and OCR equivalence
              classes on top. Used for blocking and similarity, never for ids.

Honorifics are the reason the identity key must strip titles: this book calls
one man الجنرال خير الدين on page 97 and خير الدين باشا on page 193. If a title
entered the identifier, that would be two people. The rank is not discarded --
it comes back as ``rank``, an attribute of the mention.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

from .paths import load_config
from .textnorm_ar import fold, strip_harakat

_WS = re.compile(r"\s+")
_ID_SAFE = re.compile(r"[^A-Z0-9]+")


@lru_cache(maxsize=1)
def _rules() -> dict:
    cfg = load_config("aalam_name_variants")
    variant_map: dict[str, str] = {}
    for cls in cfg.get("equivalence_classes") or []:
        canon = fold(cls[0])
        for member in cls:
            variant_map[fold(member)] = canon
    return {
        "particles": {fold(p) for p in cfg["particles"]},
        "particle_canonical": {
            fold(k): fold(v) for k, v in (cfg.get("particle_canonical") or {}).items()
        },
        "compounds": [
            tuple(fold(t) for t in pair) for pair in (cfg.get("compounds") or [])
        ],
        "theophoric": {fold(t) for t in cfg["theophoric_heads"]},
        "honorifics": {fold(h) for h in cfg["honorifics"]},
        "ranks": {fold(k): v for k, v in (cfg.get("rank_titles") or {}).items()},
        "article": fold(cfg["article"]),
        "translit": cfg["translit"],
        "variant_map": variant_map,
    }


def strip_article(token: str) -> str:
    """Drop a leading definite article: الورداني -> وردانى -> وردani.

    Only when something survives it: ال on its own is a token, not an article,
    and a two-letter word beginning with alif-lam is more likely a word than an
    articled one.
    """
    art = _rules()["article"]
    if token.startswith(art) and len(token) > len(art) + 1:
        return token[len(art):]
    return token


def fuse_compounds(tokens: list[str]) -> list[str]:
    """Fuse names whose elements are never used apart: خير الدين -> خيرالدين.

    Run before the particle and article rules, which would otherwise strip the
    article from the second element and leave the compound looking like two
    ordinary tokens.
    """
    compounds = _rules()["compounds"]
    if not compounds:
        return tokens
    out: list[str] = []
    i = 0
    while i < len(tokens):
        if i + 1 < len(tokens) and (tokens[i], tokens[i + 1]) in compounds:
            out.append(tokens[i] + tokens[i + 1])
            i += 2
            continue
        out.append(tokens[i])
        i += 1
    return out


def fuse_particles(tokens: list[str]) -> list[str]:
    """Fuse nasab particles and theophoric heads onto the following token.

    بن عاشور -> بنعاشور, so that "ابن عاشور" and "بن عاشور" land on one surname.
    عبد السلام -> عبدالسلام, so that the theophoric compound stays one given
    name rather than colliding with every other Abd-.
    """
    r = _rules()
    out: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in r["particles"] | r["theophoric"] and i + 1 < len(tokens):
            nxt = tokens[i + 1]
            # Spelling variants of the particle itself are folded first, so
            # that ibn- and bin- give one surname rather than two.
            head = r["particle_canonical"].get(tok, tok)
            # The article between a particle and its head is silent:
            # عبد ال سلام and عبد السلام are one name.
            out.append(head + strip_article(nxt))
            i += 2
            continue
        out.append(tok)
        i += 1
    return out


@dataclass(frozen=True)
class ArabicName:
    raw: str
    tokens: tuple[str, ...] = ()
    normalised: str = ""
    match_tokens: tuple[str, ...] = ()
    match_key: str = ""
    rank: str = ""
    honorifics: tuple[str, ...] = ()
    surname_key: str = ""
    first_token: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.tokens


def parse_person(raw: str) -> ArabicName:
    """Split a printed Arabic name into its identity and matching keys."""
    r = _rules()
    folded = fold(raw or "")
    if not folded:
        return ArabicName(raw=raw or "")

    titles, rank, body = [], "", []
    for tok in folded.split(" "):
        if tok in r["honorifics"]:
            titles.append(tok)
            if not rank and tok in r["ranks"]:
                rank = r["ranks"][tok]
            continue
        body.append(tok)

    # A name that is nothing but titles is not a name. Keep the tokens rather
    # than returning empty, so "الشيخ" alone is visibly a non-person upstream
    # instead of silently vanishing.
    if not body:
        return ArabicName(raw=raw or "", rank=rank,
                          honorifics=tuple(titles))

    body = fuse_particles(fuse_compounds(body))
    tokens = tuple(strip_article(t) for t in body if strip_article(t))
    if not tokens:
        return ArabicName(raw=raw or "", rank=rank, honorifics=tuple(titles))

    match_tokens = tuple(r["variant_map"].get(t, t) for t in tokens)
    return ArabicName(
        raw=raw or "",
        tokens=tokens,
        normalised=" ".join(tokens),
        match_tokens=match_tokens,
        match_key=" ".join(match_tokens),
        rank=rank,
        honorifics=tuple(titles),
        surname_key=match_tokens[-1],
        first_token=match_tokens[0],
    )


def transliterate(text: str) -> str:
    """Deterministic lossy ASCII for identifiers, not a scholarly scheme."""
    table = _rules()["translit"]
    out = []
    for ch in strip_harakat(text):
        if ch == " ":
            out.append(" ")
        else:
            out.append(table.get(ch, ""))
    return _WS.sub(" ", "".join(out)).strip()


def _slug(text: str, limit: int = 60) -> str:
    return _ID_SAFE.sub("_", transliterate(text).upper()).strip("_")[:limit].strip("_")


def person_id(name: str) -> str:
    """``PERSON_<SURNAME>_<GIVEN...>``, matching the other builds' shape.

    Built from the identity key only. Transliteration equivalence classes are
    deliberately excluded, for the reason names.py gives: an identifier is
    irreversible, and folding two spellings together is a judgement the
    resolver should score rather than one an id should assume.
    """
    p = parse_person(name)
    if p.is_empty:
        return "PERSON_UNKNOWN"
    ordered = (p.tokens[-1],) + p.tokens[:-1]
    slug = _slug(" ".join(ordered))
    return f"PERSON_{slug}" if slug else "PERSON_UNKNOWN"


_ORG_PREFIX = {
    "SCHOOL": "SCH", "MOSQUE": "MSQ", "MINISTRY": "MIN", "NEWSPAPER": "NEWS",
    "ASSOCIATION": "ASSOC", "PARTY": "PARTY", "COURT": "COURT",
    "GOVERNMENT": "GOV", "ORGANIZATION": "ORG",
}


def org_id(name: str, node_type: str = "ORGANIZATION") -> str:
    """``<PREFIX>_<SLUG>``; the type namespaces the id, as in the other builds."""
    prefix = _ORG_PREFIX.get(node_type, "ORG")
    folded = fold(name or "")
    tokens = [strip_article(t) for t in folded.split(" ") if strip_article(t)]
    slug = _slug(" ".join(tokens))
    return f"{prefix}_{slug}" if slug else f"{prefix}_UNKNOWN"
