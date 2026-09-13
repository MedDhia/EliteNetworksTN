"""Flow diagram of where interior officials go when they leave the apparatus.

The dot-plot version of this question puts retention and destination on two
different bases — retention as a share of the cohort, destinations as a share of
the leavers — deliberately, so that neither panel restates the other. The cost is
that nothing shows the two together. This does: every panel is one cohort of
movers on a single scale, so how much stays inside and how the rest divides are
read off the same picture.

Why the left column is seniority and not a single node. A flow diagram with one
source is a bar chart with curves — it adds ink and no information. Splitting the
source by rank makes the diagram answer something the bar chart cannot: whether
the people the apparatus loses from its senior ranks go to different places than
the ones it loses from below. After 2021 they do — 30% of senior leavers go to
the infrastructure and production ministries against 12% of those below.

Two tiers, not the three of the rank-flow figure. At three the cells fall to one
and two people and the diagram would draw noise as confidently as signal; even at
two, 1987's smallest ribbon is a single person, which the note says outright.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from figures_sankey import (  # noqa: E402
    PLACEBO_LAGS, RECORD_ENDS, RUPTURES, _label_positions, ribbon,
)
from apparatus import STAYS, destination, in_interior_apparatus  # noqa: E402
from figstyle import (  # noqa: E402
    CAT4, INK, MUTED, PAPER, PROC, SOURCE, headline, plt, save,
)
from matplotlib.patches import Patch  # noqa: E402

# Colour carries which tier a flow came from, and nothing else. Two slots of the
# four-slot categorical palette, revalidated as their own pair rather than
# assumed from the parent: all checks pass under `--pairs all`, worst ΔE 23.6
# protan and 27.9 normal. Destination identity is carried by position and a
# direct label, never by colour.
TIERS = [(40, "Director and above", CAT4[1]),
         (0, "Head of service and below", CAT4[0])]

# Fixed for every panel, so that a destination sits in the same place whichever
# rupture is being read and whatever its rank in that panel. Ordering by each
# panel's own totals would repaint and reposition the diagram under the reader.
ORDER = [STAYS, "social ministries", "infrastructure and production",
         "finance and economy", "the centre", "public enterprise",
         "sovereign and oversight", "not identifiable"]

SHORT = {STAYS: "Stays in the\ninterior apparatus",
         "social ministries": "Social ministries",
         "infrastructure and production": "Infrastructure\nand production",
         "finance and economy": "Finance and economy",
         "the centre": "The centre",
         "public enterprise": "Public enterprise",
         "sovereign and oversight": "Sovereign and oversight",
         "not identifiable": "Not identifiable"}


def movers(spells: pd.DataFrame, t0: pd.Timestamp, years: int = 5):
    """Interior people in post on the eve of t0 who take another post.

    Same cohort rule as the rank-flow and retention figures: in post on the eve,
    observed in a further post inside the window, a person holding several posts
    placed at the highest.
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
    if top.empty or after.empty:
        return None
    nxt = after.loc[after.groupby("person_id").rank_score.idxmax()]
    j = top[["person_id", "rank_score"]].merge(
        nxt[["person_id", "org_portfolio", "org_name", "org_form"]],
        on="person_id", how="inner")
    if j.empty:
        return None
    j["tier"] = [next(lab for lo, lab, _ in TIERS if r >= lo)
                 for r in j.rank_score]
    j["dest"] = [destination(p, o, f) for p, o, f in
                 zip(j.org_portfolio, j.org_name.fillna(""),
                     j.org_form.fillna(""))]
    return j


def matrix(j: pd.DataFrame) -> pd.DataFrame:
    # The placebo frame is several cohorts concatenated, so its row labels
    # repeat; crosstab carries that through and the reindex below then refuses
    # the axis. The row labels mean nothing here - one row is one person-move.
    j = j.reset_index(drop=True)
    return (pd.crosstab(j.tier, j.dest)
            .reindex(index=[lab for _, lab, _ in TIERS], columns=ORDER)
            .fillna(0).astype(int))


def draw(ax, m: pd.DataFrame, *, label_dests: bool, fontsize: float = 6.6) -> None:
    total = float(m.values.sum())
    if not total:
        ax.axis("off")
        return
    gap_l, gap_r = 0.06, 0.022
    usable_l = 1.0 - gap_l * (len(m.index) - 1)
    usable_r = 1.0 - gap_r * (len(m.columns) - 1)
    x0, x1, node_w = 0.0, 1.0, 0.026

    ax.set_xlim(-0.60 if label_dests else -0.34, 1.62)
    ax.set_ylim(-0.05, 1.05)
    ax.axis("off")

    def stack(totals, usable, gap):
        tops, y = [], 1.0
        for t in totals:
            h = usable * (t / total)
            tops.append((y, y - h))
            y -= h + gap
        return tops

    lt = m.sum(axis=1).values.astype(float)
    rt = m.sum(axis=0).values.astype(float)
    left, right = stack(lt, usable_l, gap_l), stack(rt, usable_r, gap_r)

    lcur = [t for t, _ in left]
    rcur = [t for t, _ in right]
    for i in range(len(m.index)):
        colour = TIERS[i][2]
        for jx in range(len(m.columns)):
            v = m.iat[i, jx]
            if not v:
                continue
            h = usable_r * (v / total)
            y0a, y0b = lcur[i], lcur[i] - h
            y1a, y1b = rcur[jx], rcur[jx] - h
            lcur[i] -= h
            rcur[jx] -= h
            ribbon(ax, x0 + node_w, x1 - node_w, y0a, y0b, y1a, y1b, colour,
                   alpha=0.55)

    for (ytop, ybot), t, colour in zip(left, lt, [c for _, _, c in TIERS]):
        ax.add_patch(plt.Rectangle((x0, ybot), node_w, ytop - ybot,
                                   facecolor=colour, edgecolor="none", zorder=4))
        ax.annotate(f"{int(t):,}", xy=(x0 - node_w * 1.4, (ytop + ybot) / 2),
                    ha="right", va="center", fontsize=fontsize + 0.6,
                    color=INK, fontweight="bold", zorder=5)

    # Six of the eight destination nodes are a few percent of the column each,
    # so their midpoints sit within a line-height of one another and the labels
    # overlap. Same sweep as the rank-flow figure: midpoints are preferences,
    # and a pass from the bottom up opens a gap wherever two would meet.
    texts = [(f"{SHORT[c]}   {int(t):,}" if label_dests else f"{int(t):,}")
             for c, t in zip(m.columns, rt)]
    ys = _label_positions(ax, right, texts, fontsize)
    for k, ((ytop, ybot), t, y) in enumerate(zip(right, rt, ys)):
        ax.add_patch(plt.Rectangle((x1 - node_w, ybot), node_w, ytop - ybot,
                                   facecolor=INK, edgecolor="none", zorder=4))
        if not t:
            continue
        ax.annotate(texts[k], xy=(x1 + node_w * 1.4, y), ha="left",
                    va="center", fontsize=fontsize, color=INK,
                    linespacing=1.3, zorder=5)


def fig_outflow_sankey(spells: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(15.2, 8.6))
    fig.subplots_adjust(top=0.71, bottom=0.09, left=0.055, right=0.90,
                        wspace=0.62, hspace=0.34)

    kept, social = [], []
    for col, (key, t0, datestr, gloss) in enumerate(RUPTURES):
        j = movers(spells, t0)
        plc = pd.concat([x for x in
                         (movers(spells, t0 - pd.DateOffset(years=k))
                          for k in PLACEBO_LAGS) if x is not None])
        for row, (jj, lbl) in enumerate(((j, f"after {key}"),
                                         (plc, "ordinary times"))):
            m = matrix(jj)
            draw(axes[row, col], m, label_dests=(col == 2))
            stay = m[STAYS].sum() / m.values.sum() * 100
            axes[row, col].set_title(
                f"{lbl}   ·   {len(jj):,} movers   ·   {stay:.0f}% stay",
                color=INK, fontsize=8.4, loc="left", x=-0.10)
            if row == 0:
                kept.append(stay)
                leavers = m.drop(columns=[STAYS])
                social.append((key, m["social ministries"].sum()
                               / leavers.values.sum() * 100))
        axes[0, col].annotate(f"{key}  ·  {datestr}\n{gloss}",
                              xy=(0.42, 1.32), xycoords="axes fraction",
                              ha="center", va="bottom", fontsize=9.6,
                              color=INK, fontweight="bold", linespacing=1.5)

    axes[1, 1].legend(handles=[Patch(facecolor=c, alpha=0.62, label=lab)
                               for _, lab, c in TIERS],
                      loc="upper center", bbox_to_anchor=(0.42, -0.07), ncol=2,
                      title="rank held in the interior on the eve of the rupture",
                      title_fontsize=8)

    headline(
        fig,
        "Where the interior sends the people it loses",
        "Everyone holding an interior-apparatus post on the eve of a rupture who "
        "took a further post within five years, by where that post sat. Each "
        "panel is one cohort on one scale, so how much the apparatus keeps and "
        "how the rest divides are read together. The row beneath each rupture is "
        "the same cohort drawn from five ordinary years of its own era. The "
        "apparatus keeps more of its own after every rupture than its era does "
        "ordinarily — "
        + ", ".join(f"{k:.0f}%" for k in kept) +
        " against 52%, 56% and 66%. The social ministries take the largest "
        "identified share of what it loses in "
        # 1987 is not in this list and must not be: its largest bucket is the
        # unattributable one, and a sentence that swept all three together
        # would be reporting a pattern two of them have.
        + " and ".join(k for k, v in social if v >= 25)
        + f" ({', '.join(f'{v:.0f}%' for _k, v in social if v >= 25)} of their "
        "leavers), in ordinary times as much as after the rupture. 1987 is not "
        "comparable on this: its largest single bucket is the bodies the record "
        "will not place.",
        width=150,
    )
    save(fig, "fig25_outflow_destinations_flow",
         SOURCE + "  Node figures are people. The left column is rank held in "
                  "the interior, at two tiers rather than the three of the "
                  "rank-flow figure: at three the cells fall to one and two "
                  "people, and a diagram of this kind draws noise as "
                  "confidently as signal. Even at two, the smallest ribbon in "
                  "the 1987 panel is one person, and that panel's outflow is 92 "
                  "people spread over seven destinations — read its node totals, "
                  "not its individual ribbons. The seniority split is not "
                  "decoration: after 2021, 30% of senior leavers go to the "
                  "infrastructure and production ministries against 12% of those "
                  "leaving from below. Destinations keep the same position in "
                  "every panel whatever their rank within it, so the six "
                  "diagrams can be read against one another. Destination is read "
                  "from the body's portfolio where it has one and from its name "
                  "where it does not; what remains unattributable is shown "
                  "rather than dropped.")


def main() -> None:
    print("loading tables…")
    spells = pd.read_csv(PROC / "spells.csv.gz", low_memory=False)
    spells["start"] = pd.to_datetime(spells.start_date, errors="coerce")
    spells["end"] = pd.to_datetime(spells.end_date, errors="coerce")
    spells = spells.dropna(subset=["start"])
    print("drawing…")
    fig_outflow_sankey(spells)
    print("done")


if __name__ == "__main__":
    main()
