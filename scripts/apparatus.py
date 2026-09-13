"""What counts as the interior apparatus, and where a post outside it sits.

Separated from the figure scripts so that it can be tested without a drawing
library. Matplotlib is not a dependency of this project — the figures are built
from the same tables as everything else but are not part of the package — so a
test that imports a figure module cannot run in CI, and a rule about which
bodies belong to the interior is exactly the kind of thing that should be under
test rather than checked by eye on a finished chart.

Nothing here draws. The classification rules need nothing but the standard
library; the one table helper at the end needs pandas, which is a dependency of
the project and is available wherever the tests run.
"""

from __future__ import annotations

import math
import re

# ---------------------------------------------------------------------------
# the interior apparatus
# ---------------------------------------------------------------------------
# In Tunisia the interior ministry is not the building: it is the ministry
# together with the governorates and municipalities it administers. Taking the
# ministry alone leaves too few people to say anything — over three years it
# supplies 63, 157 and 81 movers across the three ruptures, of whom 24, 34 and
# 21 stand above the bottom rank tier.
_INTERIOR_CORE = re.compile(
    r"minist[eè]re de l'int[ée]rieur|secr[ée]tariat d'etat [aà] l'int[ée]rieur|"
    r"s[uû]ret[ée] nationale|garde nationale|protection civile", re.I)

# A body attached to a commune or a governorate belongs to the territorial
# administration whatever its own form says: the municipal technical services of
# Tunis and the regional council of Bizerte are not free-standing. Roughly half
# the `direction` rows in the spell table carry no portfolio at all, so without
# this they fall out of the apparatus entirely — 608 spells of it.
#
# Two guards, each earning its place on a case the other misses. The form
# restriction drops the agricultural training institute *at* Sidi Thabet "au
# gouvernorat de l'Ariana", where the phrase gives a location and not an
# attachment. The ministry rule drops the hospital-construction units "au
# gouvernorat du Kasserine au ministère de l'équipement", where a ministry named
# further along the string is the real parent.
#
# The spell's own `parent_org_id` would seem the obvious way to do this and is
# not usable: it is assigned per spell from the surrounding act, so a decree
# listing appointments across several ministries mislabels them — one
# `direction générale des impôts` spell carries the interior ministry as its
# parent.
_LOCALLY_ATTACHED = re.compile(r"(?:[àa]|de) la commune d|au gouvernorat d", re.I)
_UNDER_MINISTRY = re.compile(r"au minist[eè]re d", re.I)


def portfolio_domains(label) -> tuple[str, ...]:
    """The policy domains a portfolio label names.

    Compound portfolios ("min_developpement+interieur") count toward each
    domain they name, which is what stops a ministry rename reading as an
    abolition.
    """
    if not isinstance(label, str) or not label:
        return ()
    if label.startswith("min_"):
        return tuple(d for d in label[4:].split("+") if d)
    return (label,)


def attached_to_local_body(org: str, form: str) -> bool:
    if form not in ("direction", "autre"):
        return False
    m = _LOCALLY_ATTACHED.search(org)
    return bool(m) and _UNDER_MINISTRY.search(org, m.end()) is None


def in_interior_apparatus(portfolio, org: str, form: str) -> bool:
    return ("interieur" in portfolio_domains(portfolio)
            or bool(_INTERIOR_CORE.search(org))
            or form in ("gouvernorat", "commune")
            or attached_to_local_body(org, form))


# ---------------------------------------------------------------------------
# destinations outside it
# ---------------------------------------------------------------------------
# Roughly half the `direction` rows carry no portfolio, so a portfolio-only
# classifier leaves 39% of the outflow unplaced. The body's own name is the
# fallback: it either names its ministry outright or is one of a small number of
# standing bodies whose attachment is not in doubt — the tax, customs and
# public-accounts directorates-general to finance, the regional agricultural
# commissariats to agriculture.
_BY_NAME = [
    ("finance and economy", re.compile(
        r"minist[eè]re des finances|minist[eè]re de l'[ée]conomie|"
        r"minist[eè]re du plan|domaines de l'etat|"
        r"direction g[ée]n[ée]rale des imp[ôo]ts|contr[ôo]le fiscal|"
        r"comptabilit[ée] publique|direction g[ée]n[ée]rale des douanes|"
        r"direction g[ée]n[ée]rale des participations", re.I)),
    ("infrastructure and production", re.compile(
        r"minist[eè]re de l'agriculture|minist[eè]re de l'[ée]quipement|"
        r"minist[eè]re du transport|minist[eè]re de l'industrie|"
        r"minist[eè]re du commerce|minist[eè]re du tourisme|"
        r"minist[eè]re de l'environnement|minist[eè]re de l'[ée]nergie|"
        r"minist[eè]re des communications|minist[eè]re des technologies|"
        r"d[ée]veloppement agricole|d[ée]veloppement r[ée]gional|"
        r"ponts et chauss[ée]es", re.I)),
    ("social ministries", re.compile(
        r"minist[eè]re de l'[ée]ducation|enseignement sup[ée]rieur|"
        r"commissariat r[ée]gional de l'[ée]ducation|universit[ée]|"
        r"minist[eè]re de la sant[ée]|h[ôo]pital|affaires sociales|"
        r"minist[eè]re de l'emploi|formation professionnelle|"
        r"minist[eè]re de la culture|affaires religieuses|"
        r"minist[eè]re de la jeunesse|minist[eè]re des sports", re.I)),
    ("sovereign and oversight", re.compile(
        r"affaires [ée]trang[eè]res|d[ée]fense nationale|"
        r"minist[eè]re de la justice|cour de cassation|tribunal|"
        r"cour d'appel|conseil d'etat|cour des comptes|"
        r"assembl[ée]e des repr[ée]sentants du peuple|chambre des d[ée]put[ée]s|"
        r"chambre des conseillers", re.I)),
    ("the centre", re.compile(
        r"pr[ée]sidence de la r[ée]publique|pr[ée]sidence du gouvernement|"
        r"premier minist[eè]re|secr[ée]tariat d'etat [aà] la pr[ée]sidence", re.I)),
]

# Five blocs and not fourteen. A dozen destinations looks more informative and
# is not: 1987 sends about a hundred people out of the apparatus in five years,
# which is single figures in most cells.
BLOCS = ["the centre", "sovereign and oversight", "finance and economy",
         "infrastructure and production", "social ministries",
         "public enterprise", "not identifiable"]

STAYS = "stays in the interior apparatus"


def destination(portfolio, org: str, form: str) -> str:
    if in_interior_apparatus(portfolio, org, form):
        return STAYS
    d = set(portfolio_domains(portfolio))
    if form == "presidence" or {"presidence_republique",
                                "presidence_gouvernement"} & d:
        return "the centre"
    if form == "juridiction" or {"justice", "defense",
                                 "affaires_etrangeres"} & d:
        return "sovereign and oversight"
    if {"finances", "economie", "domaines_etat", "plan"} & d:
        return "finance and economy"
    if form in ("entreprise_publique", "banque"):
        return "public enterprise"
    if form == "instance_independante":
        return "sovereign and oversight"
    if ({"education", "enseignement_superieur", "sante", "affaires_sociales",
         "emploi", "culture", "affaires_religieuses", "jeunesse_sport",
         "femme_famille"} & d
            or form in ("universite", "etablissement_sante")):
        return "social ministries"
    if {"equipement", "transport", "agriculture", "energie", "industrie",
        "environnement", "commerce", "tourisme", "developpement",
        "information", "technologies"} & d:
        return "infrastructure and production"
    for label, pat in _BY_NAME:          # portfolio blank: read the name
        if pat.search(org):
            return label
    return "not identifiable"


# ---------------------------------------------------------------------------
# the security apparatus
# ---------------------------------------------------------------------------
# Not the same body as the interior apparatus, and the difference is the point
# of treating it separately: it takes in defence and military justice, and it
# leaves out the municipalities. A commune's technical services are local
# government, not a coercive institution, so a governor moving to a town hall
# is leaving the security apparatus even though they never left the interior
# ministry's remit.
#
# The branches follow the security-branch figure already in this repository, so
# that the two describe the same body. What is added here is the portfolio test
# and the governorate-attachment test, which that figure reads off the
# organisation's name alone.
_DEFENCE = re.compile(r"d[ée]fense nationale|tribunal militaire|arm[ée]e", re.I)
_GOVERNORATE_ATTACHED = re.compile(r"au gouvernorat d", re.I)

SECURITY_STAYS = "stays in the security apparatus"


def _attached_to_governorate(org: str, form: str) -> bool:
    """As `attached_to_local_body`, but governorates only.

    The commune half of that rule has to be dropped here: municipalities are
    outside the security apparatus, so a body hanging off one is outside it too.
    """
    if form not in ("direction", "autre"):
        return False
    m = _GOVERNORATE_ATTACHED.search(org)
    return bool(m) and _UNDER_MINISTRY.search(org, m.end()) is None


def security_branch(portfolio, org: str, form: str) -> str | None:
    """Which arm of the security apparatus a post sits in, or None if outside.

    Order matters: the interior test runs first, so a post that names both the
    interior ministry and a governorate is read as the ministry's.
    """
    d = portfolio_domains(portfolio)
    if "interieur" in d or _INTERIOR_CORE.search(org):
        return "interior"
    if "defense" in d or _DEFENCE.search(org):
        return "defence"
    if form == "gouvernorat" or _attached_to_governorate(org, form):
        return "territorial"
    return None


def in_security_apparatus(portfolio, org: str, form: str) -> bool:
    return security_branch(portfolio, org, form) is not None


def security_destination(portfolio, org: str, form: str) -> str:
    """Where a post sits, from the security apparatus's point of view.

    Everything outside it is classified exactly as for the interior, with one
    addition: bodies that are interior-but-not-security — the municipalities and
    what hangs off them — are named as their own destination rather than folded
    into the residual, because a move from a governorate to a town hall is a
    specific and legible career step and not an unclassifiable one.
    """
    if in_security_apparatus(portfolio, org, form):
        return SECURITY_STAYS
    if in_interior_apparatus(portfolio, org, form):
        return "municipal government"
    return destination(portfolio, org, form)


def wilson(k: int, n: int) -> tuple[float, float]:
    """Wilson interval for a proportion, in percentage points.

    Used rather than the normal approximation because several of these shares
    sit near zero on cohorts of a hundred, where the normal interval runs below
    it and reports something impossible.
    """
    if not n:
        return 0.0, 0.0
    z, p = 1.96, k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h) * 100, min(1.0, c + h) * 100


# ---------------------------------------------------------------------------
# building moves out of spells
# ---------------------------------------------------------------------------
def consecutive_moves(spells, branch_col: str = "branch"):
    """One row per post-to-post move: the post held, and the one taken next.

    Two things here are easy to get wrong, and both were got wrong first.

    *One post per person-date.* Several appointments are often gazetted on the
    same day, so the senior one stands for where the person was.

    *Whether a next post exists is read off its start date, never off its
    branch.* A destination outside the classified body has no branch, so a
    branch of NaN means either "outside" or "no next post at all". Filtering on
    the branch collapses those two and silently discards every move out of the
    body — which is most of them. It left one figure showing 904 of 2,333
    interior moves, and the diagram looked entirely reasonable.

    Returns the frame with `to_branch` added and only rows that have a next
    post. Callers decide what an absent `to_branch` means for them.
    """
    import pandas as pd  # noqa: F401  (imported here to keep the rules stdlib-only)

    s = spells.sort_values(["person_id", "start", "rank_score"])
    s = s.loc[s.groupby(["person_id", "start"]).rank_score.idxmax()]
    s = s.sort_values(["person_id", "start"])
    nxt = s.groupby("person_id").shift(-1)
    out = s.assign(to_branch=nxt[branch_col], _has_next=nxt.start.notna())
    return out[out._has_next].drop(columns="_has_next")
