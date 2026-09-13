"""Surnames as a proxy for family, and the limits of that proxy.

Elite studies read shared surnames as a trace of family reproduction inside the
state. The trace is real but noisy, and in this corpus the noise runs in both
directions at once:

**The same family appears under several surnames.** Of the 11,850 people the
register holds under more than one spelling, 77% have variants that disagree
about the surname — Hédi Baccouche is also recorded as Bakis, Bouker, Bakkar
and Beccar. Entity resolution picks one canonical spelling per person, so a
count over canonical names is well defined; but two brothers whose names were
transliterated differently are two surnames, and their tie is invisible here.

**Different families appear under one surname.** The commonest surnames in the
table — Trabelsi, Cherif, Dridi, Hammami, Gharbi, Oueslati — are the commonest
surnames in Tunisia. 132 Trabelsis among 45,388 people is 0.29% of the corpus,
and they are emphatically not one family.

So a surname is a weak instrument for kinship, and the weakness is not uniform:
it is worst for common surnames and least bad for rare ones. That gradient is
the one thing here that can separate family from its main rival explanation,
and the figure is built on it rather than on any count of who appears most.

**What this module deliberately does not compute.** There is no ranking of
over-represented surnames, and none should be added. Such a list reads as an
accusation of nepotism against named living families, on an instrument that
cannot support it for exactly the names that would top the list: the commonest
ones, where the proxy is weakest. The structural result — that co-presence
exceeds chance, and by how much as a function of rarity — needs no such list
and is what the record can actually carry.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Iterable, Sequence

# Particles that begin a family name. Everything from the chosen particle to
# the end of the string is the surname: "Mohamed Ben Abdallah" is a Ben
# Abdallah, not an Abdallah, and collapsing the two merges distinct families.
#
# Which particle is chosen needs two rules, because the corpus shows the two
# kinds behaving differently.
#
# STRONG are patronymic markers, and they chain: 1,078 names in the register
# run "X ben Y ben Z". Tunisian usage makes the terminal patronymic the family
# name, so the surname starts at the LAST strong particle — "Kamel ben Mohamed
# ben Ammar" is a Ben Ammar.
#
# WEAK also occur inside compound given names, which is why they cannot simply
# win by position: "el" is followed by a later ben in 117 names, among them the
# most-recorded name in the corpus. Taking the first particle files Zine El
# Abidine Ben Ali under "el abidine ben ali" instead of "ben ali". So a weak
# particle opens the surname only when no strong one is present, and then it is
# the first that counts — "Béji Caïd Essebsi" is a Caïd Essebsi.
STRONG = {"ben", "bin", "ould"}
WEAK = {"el", "al", "bel", "bou", "sidi", "caid", "haj", "hadj"}
PARTICLE = STRONG | WEAK

# Titles the gazette prints inside the name field.
TITLE = {"docteur", "dr", "monsieur", "madame", "mme", "professeur", "pr"}

# French running text that the extractor has taken for a name. These are verbs
# and participles from the surrounding act ("est chargé de", "à compter du"),
# not people.
EXTRACTION_NOISE = {"compter", "nommer", "charge", "chargee", "fonctions"}

# Given names that turn up as a bare final token — "Mohamed Salah" with no
# particle. The record does not say whether the second token is a family name
# or a second given name, and for these it is usually the latter, so the
# surname is not recoverable and the person is left out rather than filed
# under a name that is not theirs. Names reached through a particle are
# unaffected: "Ben Salah" is a surname and stays one.
GIVEN_AS_LAST = {
    "ali", "salah", "mohamed", "ahmed", "amor", "salem", "hedi", "tahar",
    "habib", "mustapha", "abdallah",
}


def fold(s: str) -> str:
    """Case- and accent-fold, so Béji and Beji are one token."""
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def split_name(name: str) -> tuple[str | None, str | None]:
    """Return ``(given, surname)`` folded, or ``(None, None)``.

    The surname opens at the last strong particle where there is one, at the
    first weak particle otherwise, and is the final token when there is
    neither. See the note on ``STRONG`` and ``WEAK`` for why the two are
    scanned from opposite ends.
    """
    if not name:
        return None, None
    tokens = [t for t in re.split(r"\s+", name.strip()) if t]
    tokens = [t for t in tokens if fold(t) not in TITLE]
    if len(tokens) < 2:
        return None, None
    folded = [fold(t) for t in tokens]

    # A particle in first position is part of the given name — there is no
    # given name left in front of it — so the scan starts at 1 either way.
    strong = [i for i in range(1, len(folded)) if folded[i] in STRONG]
    if strong:
        start = strong[-1]
    else:
        weak = [i for i in range(1, len(folded)) if folded[i] in WEAK]
        start = weak[0] if weak else len(folded) - 1
    return folded[0], " ".join(folded[start:])


def surname(name: str) -> str | None:
    return split_name(name)[1]


def usable(sn: str | None) -> bool:
    """Whether a surname can stand for a family at all.

    The isinstance guard is load-bearing, not defensive noise. ``split_name``
    returns ``None`` for a name with no recoverable surname, but putting that
    list into a DataFrame column stores it as NaN — and ``not float("nan")``
    is False, so a bare falsiness check passes NaN through as a usable
    surname. Every such person then carries the *same* non-value, which a
    frequency count reads as one large family.
    """
    if not isinstance(sn, str) or not sn:
        return False
    if sn in EXTRACTION_NOISE:
        return False
    # Only a bare token is rejected; "ben salah" reached through a particle is
    # a family name and survives.
    return sn not in GIVEN_AS_LAST


def same_surname_probability(names: Sequence[str]) -> float:
    """Chance that two officials drawn from one body share a surname.

    A Herfindahl-style figure rather than a count of duplicates, because bodies
    differ in size by two orders of magnitude and a raw duplicate count would
    rank them by headcount. Sampling is without replacement, so a person is
    never paired with themselves.
    """
    counts = [float(c) for c in Counter(names).values()]
    n = sum(counts)
    if n < 2:
        return float("nan")
    return sum(c * (c - 1) for c in counts) / (n * (n - 1))


def shared_outcome_probability(names: Sequence[str],
                               outcome: Sequence[bool]) -> float:
    """Chance that two people sharing a surname *both* reached the outcome.

    The rank counterpart of ``same_surname_probability``: that one asks how
    often two officials in a body share a name, this one how often two people
    sharing a name share a fate. Sampling is again without replacement, so
    nobody is paired with themselves.

    Returns nan when no two people share a surname, which is the honest answer
    for a set of unique names rather than a zero that would read as evidence
    of no association.
    """
    total = Counter(names)
    hit = Counter(n for n, o in zip(names, outcome) if o)
    den = sum(c * (c - 1) for c in total.values())
    if den == 0:
        return float("nan")
    return sum(c * (c - 1) for c in hit.values()) / den


def shared_outcome_fast(codes, outcome, n_codes: int) -> float:
    """``shared_outcome_probability`` on integer codes, for permutation loops.

    A permutation run evaluates the statistic a few thousand times over forty
    thousand people, and counting strings each pass dominates the cost. This
    is the same quantity by bincount. The string version above stays the
    definition and the tests pin the two together.

    Lives here rather than in the figure module because it is a rule, not a
    drawing: a test that reached for it there would have to import matplotlib,
    which is not a project dependency and is blocked in CI.
    """
    import numpy as np

    n = np.bincount(codes, minlength=n_codes).astype(float)
    h = np.bincount(codes, weights=np.asarray(outcome, dtype=float),
                    minlength=n_codes)
    den = (n * (n - 1)).sum()
    if den == 0:
        return float("nan")
    return (h * (h - 1)).sum() / den


def namesake_hits(rows: Iterable[tuple[object, object, str]]) -> list[bool]:
    """For each arrival in time order, was a namesake already in the body?

    ``rows`` is ``(org_id, person_id, surname)`` sorted by start date. A person
    returning to a body they already served in is not their own namesake, which
    is why the set of prior holders is kept by identity rather than counted.
    """
    seen: dict[tuple[object, str], set] = {}
    out = []
    for org, pid, sn in rows:
        key = (org, sn)
        prior = seen.get(key)
        out.append(prior is not None and (len(prior) > 1 or pid not in prior))
        seen.setdefault(key, set()).add(pid)
    return out


def rarity_band(n: int) -> str:
    """How many people in the whole register carry this surname."""
    if n <= 2:
        return "1–2"
    if n <= 5:
        return "3–5"
    if n <= 20:
        return "6–20"
    if n <= 60:
        return "21–60"
    return "61+"


BANDS = ["1–2", "3–5", "6–20", "21–60", "61+"]
