"""Reconstructing the state's organisation chart from the register.

There is no parent column to read. ``organisations.csv.gz`` carries none at
all, and the ``parent_org_id`` on a spell is assigned from the act the
appointment was published in rather than from the body itself, so it describes
the document and not the hierarchy. Its worst case is one body claiming 89
different parents. The chart therefore has to be rebuilt, and this module is
the rules for doing it.

**The name is the best evidence.** Tunisian administrative names state their
own attachment: *direction générale des services communs **au ministère de
l'équipement***, *contrôle d'Etat **relevant de la Présidence du
gouvernement***, *secrétariat général **au commissariat régional de
l'éducation à Tunis 1***. Where the name says something the act-derived parent
is often wrong — the *commissariat régional de la jeunesse et des sports de
Sidi Bouzid* is filed by its acts under the agriculture ministry, on 29% of
its spells, while its own name says what it belongs to.

So the parent is read from the name first and from the acts only as a
fallback, and every edge carries how it was obtained.

**The splitting guard.** A separator alone is not enough: ``des`` in
*direction générale des impôts* and ``de la`` in *direction de la santé
militaire* are not attachments. A split happens only where the separator is
followed by a word that names a body — ministère, commissariat, direction,
présidence, gouvernorat and the rest of ``BODY_HEAD``. That one condition is
what keeps the parser from inventing a hierarchy out of ordinary French.

**Depth is taken as far as the names allow**, which is what this build was
asked for. Confidence falls with depth and the fall is recorded rather than
hidden: an edge from an explicit name split is not the same evidence as an
edge from a modal parent seen on a third of a body's spells, and callers can
filter on ``method`` and ``confidence``.

**What the chart is not.** It is a union over 1957–2026, so it shows bodies
that never coexisted — superseded ministries stand beside the ones that
replaced them, and a reader who takes it for a snapshot of the state at any
instant will be wrong. Each node carries the years it was actually recorded
so that the union can be cut back to a period.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Iterable


def fold(s: str) -> str:
    """Case- and accent-fold, so Équipement and EQUIPEMENT are one token."""
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


# Words that begin the name of a body. The guard on every split: a separator
# only opens a parent when what follows is one of these, which is why
# "direction générale des impôts" does not split on "des".
BODY_HEAD = {
    "ministere", "ministeres", "presidence", "premier", "secretariat",
    "commissariat", "direction", "directions", "gouvernorat", "commune",
    "agence", "office", "centre", "institut", "conseil", "tribunal", "cour",
    "societe", "entreprise", "etablissement", "hopital", "ecole", "banque",
    "caisse", "universite", "faculte", "academie", "observatoire", "regie",
    "fonds", "autorite", "instance", "comite", "commission", "delegation",
    "inspection", "cabinet", "bureau", "service", "division", "departement",
    "groupement", "union", "chambre", "haut", "haute", "institution",
}

# Separators that can introduce an attachment. Ordered longest first so that
# "relevant du" is tried before the bare "du" inside it.
_SEP = [
    "relevant de la", "relevant de l'", "relevant du", "relevant des",
    "relevant de", "rattache a la", "rattache au", "rattache a",
    "aupres de la", "aupres de l'", "aupres du", "aupres des", "aupres de",
    "pres la", "pres le", "pres l'",
    "au sein de la", "au sein du", "au sein de",
    "aux", "au", "a la", "a l'",
    "de la", "de l'", "du", "des",
]
_SEP_RE = re.compile(
    r"\s(?:" + "|".join(re.escape(s) for s in _SEP) + r")\s+(?=\S)")

# Trailing fragments the segmenter carries in from the act. The second is the
# expensive one: where an act appoints a committee, the whole membership list
# can land in the name field, and every "représentant du ministère de X" in it
# then looks like an attachment. Those names run to a median of 1,051
# characters against 72 for a real one, and left alone they produce chains
# eight deep made entirely of other people's affiliations.
_JUNK = re.compile(
    r"\s*[;,]\s*(vu\b|considerant\b|apres\b|sur\s+proposition).*$", re.I)
_ROSTER = re.compile(
    r"\s*(?::\s*(?:president|presidente|membre|vice-?president|rapporteur)\b"
    r"|,\s*-\s*(?:m\.|mme|mlle|monsieur|madame|mademoiselle)\b"
    r"|,?\s*-\s+(?=\w+\s+\w+\s*(?:,|:))"
    r"|\brepresentante?\s+d)",
    re.I)

# Beyond this a name is a segmentation failure rather than a long title. The
# longest well-formed names in the register — merged ministries with four
# portfolios — run to about 150 characters.
MAX_NAME = 200


def clean(name: str) -> str:
    """Drop act boilerplate and appointee rosters left on the end of a name."""
    n = (name or "").strip()
    n = _JUNK.sub("", n)
    m = _ROSTER.search(fold(n))
    if m:
        n = n[:m.start()]
    return n.strip(" ,;:.-")


def wellformed(name: str) -> bool:
    """Whether a name can carry hierarchy at all.

    A cleaned name still over ``MAX_NAME`` is an act the segmenter failed to
    cut, not a body. Such names are kept as nodes — the appointments in them
    are real — but contribute no edges, because every attachment they appear
    to state belongs to somebody else.
    """
    n = clean(name)
    return bool(n) and len(n) <= MAX_NAME


def split_parent(name: str) -> tuple[str, str | None]:
    """Split ``name`` into (the body, the body it hangs off) or (name, None).

    The first separator followed by a body-naming word wins, so the immediate
    parent is returned rather than the topmost one — *secrétariat général au
    commissariat régional de l'éducation à Tunis 1* yields the commissariat,
    not the education ministry, and walking further is the caller's job.
    """
    n = clean(name)
    if not wellformed(n):
        return n, None
    f = fold(n)
    for m in _SEP_RE.finditer(f):
        head = f[m.end():].split()
        if head and head[0] in BODY_HEAD:
            child = n[:m.start()].strip(" ,;:.")
            parent = n[m.end():].strip(" ,;:.")
            # A body is not its own parent, and an empty child is a split that
            # found the separator at the very front of the string.
            if child and parent and fold(child) != fold(parent):
                return child, parent
    return n, None


def chain(name: str, max_depth: int = 8) -> list[str]:
    """The full attachment chain a name states, nearest parent first.

    *direction X au commissariat régional de l'éducation à Tunis 1* gives the
    commissariat; a name that nests further gives more. ``max_depth`` stops a
    pathological name from looping, not a real one — the deepest chain the
    register actually states is far shorter.
    """
    out: list[str] = []
    cur = name
    for _ in range(max_depth):
        child, parent = split_parent(cur)
        if parent is None:
            break
        out.append(parent)
        cur = parent
    return out


# How an edge was obtained, best evidence first. Callers filter on this.
METHODS = ("name", "modal_parent", "portfolio", "form")

# Confidence floor below which a modal parent is not worth an edge. Hand
# reading of samples puts the turn at roughly here: above it the act-derived
# parent is usually the right ministry under a variant spelling, below it the
# body is one whose appointments were published under many unrelated acts.
MODAL_FLOOR = 0.40


def resolve(parent: str, by_name: dict, ministry_key) -> tuple[str | None, str]:
    """Turn a parent *string* into a node id.

    Three tries, in order of how specific the answer is: the exact body if the
    register holds one under that name, the canonical ministry if the string
    names one, nothing otherwise. Returning the canonical ministry rather than
    the literal string is what collapses seventy years of renaming — équipement,
    équipement et habitat, équipement habitat et aménagement du territoire —
    onto a single node instead of three siblings.
    """
    if not parent:
        return None, "unresolved"
    key = fold(clean(parent))
    if key in by_name:
        return by_name[key], "org"
    m = ministry_key(None, parent)
    if m:
        return f"MIN:{m}", "ministry"
    return None, "unresolved"


# A board seat held on a ministry's behalf. "membre représentant le ministère
# de l'agriculture" at a public enterprise is that ministry taking part in the
# enterprise's governance, which is a different relation from the ownership the
# tree above records — a company can be co-governed by ten ministries at once
# and belongs to none of them.
_REPRESENTS = re.compile(
    r"repr[ée]sentant\w*\s+(?:de\s+la\s+|de\s+l['’]\s*|des\s+|du\s+|de\s+"
    r"|les\s+|le\s+|la\s+|l['’]\s*)?", re.I)
# "représentant l'État" is a seat held for the state at large rather than for
# any ministry, so it carries no edge.
_FOR_THE_STATE = re.compile(r"repr[ée]sentant\w*\s+l['’]\s*[eé]tat\b", re.I)


def represented_body(position: str) -> str | None:
    """The body a board seat is held on behalf of, as written in the position.

    Returns the text after "représentant", for a ministry matcher to resolve,
    or None where the seat is not held on anyone's behalf or is held for the
    state at large.
    """
    if not position or not _REPRESENTS.search(position):
        return None
    if _FOR_THE_STATE.search(position):
        return None
    tail = _REPRESENTS.split(position, maxsplit=1)[-1].strip(" ,;:.")
    return tail or None


def modal_parent(parents: Iterable[str]) -> tuple[str | None, float]:
    """The commonest parent an act ever gave a body, and its share.

    The share is the confidence. A body whose acts agree is usually right; one
    whose modal parent covers a fifth of its spells usually is not, and the
    caller is expected to threshold on this rather than trust every edge
    equally.
    """
    vals = [p for p in parents if p and str(p).strip()]
    if not vals:
        return None, 0.0
    c = Counter(fold(v) for v in vals)
    top, k = c.most_common(1)[0]
    # Return a real spelling rather than the folded key.
    for v in vals:
        if fold(v) == top:
            return clean(v), k / len(vals)
    return None, 0.0
