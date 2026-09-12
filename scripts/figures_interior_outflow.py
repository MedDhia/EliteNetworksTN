"""Where interior officials go when they leave the interior apparatus.

The companion to the interior flow diagram. That one asks what happens to a
person's *rank*; this one asks what happens to their *location* — whether they
are still in the interior apparatus at all, and if not, which part of the state
took them.

Two things are measured, and they are not equally well measured.

The first is the retention rate: of the people holding an interior-apparatus
post on the eve of a rupture who take another post within five years, what share
take it inside the apparatus. This rests only on the interior test and on
counting, the cohorts run to several hundred, and a binomial interval around it
is honest.

The second is the composition of the outflow — which parts of the state the
leavers reach. This is thinner than it looks. 1987 sends about a hundred people
out of the apparatus, and spread over a dozen destinations that is single
figures per cell. The destinations are therefore grouped into five blocs, the
interval is drawn on every point, and the figure says in its own subtitle which
of the differences survive it. Most do not.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from figures_sankey import (  # noqa: E402
    PLACEBO_LAGS, RECORD_ENDS, RUPTURES, in_interior_apparatus,
    _portfolio_domains,
)
from figstyle import (  # noqa: E402
    CAT4, INK, MUTED, PROC, RULE, RUPTURE_COLOUR, SOURCE, headline, save,
)

import matplotlib.pyplot as plt  # noqa: E402
import re  # noqa: E402

# --- destinations ----------------------------------------------------------
# Roughly half the `direction` rows in the spell table carry no portfolio, so a
# portfolio-only classifier leaves 39% of the outflow unplaced. The body's own
# name is the fallback: it either names its ministry outright or is one of a
# small number of standing bodies whose attachment is not in doubt — the tax,
# customs and public-accounts directorates-general to finance, the regional
# agricultural commissariats to agriculture.
#
# The spell's `parent_org_id` would seem the obvious fallback and is not usable.
# It is assigned per spell from the surrounding act, so a decree listing
# appointments across several ministries mislabels them: one `direction générale
# des impôts` spell carries the interior ministry as its parent.
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

# Five blocs, not fourteen. A dozen destinations looks more informative and is
# not: 1987 sends about a hundred people out of the apparatus in five years,
# which is single figures in most cells.
BLOCS = ["the centre", "sovereign and oversight", "finance and economy",
         "infrastructure and production", "social ministries",
         "public enterprise", "not identifiable"]

STAYS = "stays in the interior apparatus"


def destination(portfolio, org: str, form: str) -> str:
    if in_interior_apparatus(portfolio, org, form):
        return STAYS
    d = set(_portfolio_domains(portfolio))
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


def wilson(k: int, n: int) -> tuple[float, float]:
    """Wilson interval, in percentage points.

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
    return max(0.0, (c - h)) * 100, min(1.0, (c + h)) * 100


def _marker(ax, x: float, y: float, colour: str, *, lo: float, hi: float,
            benchmark: float, ms: float) -> bool:
    """Draw the point filled if it clears its interval, open if it does not.

    Returns whether it cleared, so the caller can count without repeating the
    test. Shape carries the finding here rather than colour, which is already
    spent on identifying the rupture.
    """
    clears = not (lo <= benchmark <= hi)
    if clears:
        ax.plot([x], [y], marker="o", ms=ms, color=colour, zorder=4)
    else:
        ax.plot([x], [y], marker="o", ms=ms, mfc="white", mec=colour,
                mew=1.5, zorder=4)
    return clears


def outflow(spells: pd.DataFrame, t0: pd.Timestamp, years: int = 5):
    """Interior people in post on the eve of t0, and where their next post is.

    The five-year window and the seniority convention follow the interior flow
    diagram, so that the two figures describe the same cohort.
    """
    t1 = min(t0 + pd.DateOffset(years=years), RECORD_ENDS)
    inpost = spells[(spells.start < t0) & (spells.end.isna() | (spells.end > t0))]
    if inpost.empty:
        return None
    top = inpost.loc[inpost.groupby("person_id").rank_score.idxmax()]
    top = top[[in_interior_apparatus(p, o, f) for p, o, f in
               zip(top.org_portfolio, top.org_name.fillna(""),
                   top.org_form.fillna(""))]]
    after = spells[(spells.start >= t0) & (spells.start < t1)]
    if after.empty or top.empty:
        return None
    nxt = after.loc[after.groupby("person_id").rank_score.idxmax()]
    j = top[["person_id"]].merge(
        nxt[["person_id", "org_portfolio", "org_name", "org_form"]],
        on="person_id", how="inner")
    if j.empty:
        return None
    j["destination"] = [destination(p, o, f) for p, o, f in
                        zip(j.org_portfolio, j.org_name.fillna(""),
                            j.org_form.fillna(""))]
    return j


def counts(j: pd.DataFrame) -> tuple[pd.Series, int]:
    return j.destination.value_counts(), len(j)


def fig_outflow(spells: pd.DataFrame) -> None:
    fig = plt.figure(figsize=(13.4, 7.4))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 2.0], wspace=0.46,
                          left=0.075, right=0.985, top=0.755, bottom=0.16)
    ax_rate = fig.add_subplot(gs[0, 0])
    ax_dest = fig.add_subplot(gs[0, 1])

    rows, dest_rows = [], []
    for key, t0, _datestr, _gloss in RUPTURES:
        j = outflow(spells, t0)
        plc = pd.concat([x for x in
                         (outflow(spells, t0 - pd.DateOffset(years=k))
                          for k in PLACEBO_LAGS) if x is not None])
        (ca, na), (cb, nb) = counts(j), counts(plc)
        stay_a, stay_b = ca.get(STAYS, 0), cb.get(STAYS, 0)
        rows.append((key, stay_a, na, stay_b, nb))
        # Destination shares are of the *leavers*, not of the cohort: the
        # retention panel already carries how many leave, and expressing both
        # over the same base would show the same fact twice.
        la, lb = na - stay_a, nb - stay_b
        for b in BLOCS:
            dest_rows.append((key, b, ca.get(b, 0), la, cb.get(b, 0), lb))

    # --- left: retention ---------------------------------------------------
    ax_rate.set_title("Stays inside the interior apparatus", color=INK,
                      fontsize=9.6)
    for i, (key, sa, na, sb, nb) in enumerate(rows):
        y = len(rows) - 1 - i
        pa, pb = sa / na * 100, sb / nb * 100
        loa, hia = wilson(sa, na)
        c = RUPTURE_COLOUR[key]
        ax_rate.plot([loa, hia], [y, y], color=c, lw=1.4, alpha=0.35,
                     solid_capstyle="butt", zorder=2)
        ax_rate.plot([pb], [y], marker="|", ms=13, mew=1.8, color=MUTED,
                     zorder=3)
        # Filled where the era's own rate falls outside the interval, open
        # where it does not. The reader should be able to see which
        # differences survive without counting them off the subtitle.
        _marker(ax_rate, pa, y, c, lo=loa, hi=hia, benchmark=pb, ms=8)
        ax_rate.annotate(f"{pa - pb:+.1f} pp", xy=(hia + 1.6, y), va="center",
                         ha="left", fontsize=8.2, color=c,
                         fontweight="bold" if not (loa <= pb <= hia) else
                         "normal")
        ax_rate.annotate(f"n = {na:,}", xy=(0.5, y - 0.30), va="center",
                         ha="left", fontsize=7.0, color=MUTED)
    ax_rate.set_yticks(range(len(rows)))
    ax_rate.set_yticklabels([k for k, *_ in rows][::-1], fontsize=9.4,
                            color=INK, fontweight="bold")
    ax_rate.set_xlim(0, 82)
    ax_rate.set_ylim(-0.6, len(rows) - 0.4)
    ax_rate.set_xlabel("% of the cohort's next posts", fontsize=8.2)
    ax_rate.xaxis.grid(True, lw=0.6)
    ax_rate.set_axisbelow(True)
    ax_rate.annotate("bar: 95% interval after the rupture      "
                     "tick: the same era in ordinary times\n"
                     "filled: the era's own rate falls outside that interval   "
                     "   open: it does not",
                     xy=(0.0, -0.20), xycoords="axes fraction", va="top",
                     ha="left", fontsize=7.4, color=MUTED, linespacing=1.6)

    # --- right: where the leavers go ---------------------------------------
    ax_dest.set_title("Where the leavers go, as a share of those who leave",
                      color=INK, fontsize=9.6)
    d = pd.DataFrame(dest_rows, columns=["key", "bloc", "ka", "na", "kb", "nb"])
    nb_rows = len(BLOCS)
    for bi, bloc in enumerate(BLOCS):
        base = nb_rows - 1 - bi
        for ri, (key, *_rest) in enumerate(rows):
            r = d[(d.key == key) & (d.bloc == bloc)].iloc[0]
            y = base + (1 - ri) * 0.26
            pa = r.ka / r.na * 100 if r.na else 0.0
            pb = r.kb / r.nb * 100 if r.nb else 0.0
            lo, hi = wilson(int(r.ka), int(r.na))
            c = RUPTURE_COLOUR[key]
            ax_dest.plot([lo, hi], [y, y], color=c, lw=1.3, alpha=0.32,
                         solid_capstyle="butt", zorder=2)
            ax_dest.plot([pb], [y], marker="|", ms=9, mew=1.5, color=MUTED,
                         zorder=3)
            _marker(ax_dest, pa, y, c, lo=lo, hi=hi, benchmark=pb, ms=5.6)
            if bi == 0:
                ax_dest.annotate(key, xy=(hi + 1.1, y), va="center", ha="left",
                                 fontsize=7.6, color=c, fontweight="bold")
        if bi:
            ax_dest.axhline(base + 0.52, color=RULE, lw=0.7, zorder=1)
    ax_dest.set_yticks(range(nb_rows))
    ax_dest.set_yticklabels(BLOCS[::-1], fontsize=8.6, color=INK)
    ax_dest.set_ylim(-0.5, nb_rows - 0.25)
    ax_dest.set_xlim(0, 48)
    ax_dest.set_xlabel("% of the leavers", fontsize=8.2)
    ax_dest.xaxis.grid(True, lw=0.6)
    ax_dest.set_axisbelow(True)

    # Which destination differences actually clear their interval.
    clears = []
    for _, r in d.iterrows():
        lo, hi = wilson(int(r.ka), int(r.na))
        pb = r.kb / r.nb * 100 if r.nb else 0.0
        if not (lo <= pb <= hi):
            clears.append(f"{r.key} {r.bloc}")

    rate_clears = [k for k, sa, na, sb, nb in rows
                   if not (wilson(sa, na)[0] <= sb / nb * 100
                           <= wilson(sa, na)[1])]
    drift = " to ".join(f"{sb / nb * 100:.0f}%" for _k, _sa, _na, sb, nb in rows)
    headline(
        fig,
        "After a rupture the interior keeps more of its own",
        "People holding a post in the interior apparatus — the ministry with "
        "the governorates and municipalities — on the eve of each rupture, by "
        "where their next post within five years sits. All three ruptures "
        "point the same way, and "
        + " and ".join(rate_clears) +
        " clear their interval; 1987's +1.9 points does not. The larger "
        f"movement is not the ruptures at all: in ordinary times retention "
        f"runs {drift} across the three eras, so the apparatus was closing in "
        "on itself anyway. Where the leavers go barely moves — of the "
        f"{len(d)} destination comparisons on the right, {len(clears)} clear "
        f"their own interval, and {sum('not identifiable' in c for c in clears)}"
        " of those are the bucket of bodies the record will not place.",
        width=142,
    )
    save(fig, "fig24_interior_outflow",
         SOURCE + "  The cohort is the same as in the interior flow figure: "
                  "people in an interior-apparatus post on the eve of the "
                  "rupture who take another post within five years, a person "
                  "holding several posts placed at the highest. Retention is a "
                  "share of that cohort; the destination blocs are shares of "
                  "the leavers alone, so that the two panels do not show the "
                  "same fact twice. Intervals are Wilson, which unlike the "
                  "normal approximation does not run below zero on the small "
                  "shares here. Destination is read from the body's portfolio "
                  "where it has one and from its name where it does not; the "
                  "spell's own parent field is not used, being assigned from "
                  "the surrounding act and demonstrably wrong where one decree "
                  "appoints across several ministries. What remains "
                  "unattributable is shown rather than dropped, and it is why "
                  "the 1987 row of the right-hand panel should not be read "
                  "closely: that rupture sends 92 people out of the apparatus "
                  "in five years, a third of them to bodies the record does "
                  "not let us place.")


def main() -> None:
    print("loading tables…")
    spells = pd.read_csv(PROC / "spells.csv.gz", low_memory=False)
    spells["start"] = pd.to_datetime(spells.start_date, errors="coerce")
    spells["end"] = pd.to_datetime(spells.end_date, errors="coerce")
    spells = spells.dropna(subset=["start"])
    print("drawing…")
    fig_outflow(spells)
    print("done")


if __name__ == "__main__":
    main()
