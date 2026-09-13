"""Where the people holding office at each rupture went next.

One diagram per rupture. The left column is the rank a person stood at on the
eve of the rupture; the right column is the rank of the next post they took
within three years; the ribbon between them is how many people made that move,
coloured by whether it was upward, level, or downward.

Two decisions govern what these can and cannot show.

**Only people observed twice appear.** The gazette records appointments far
better than departures, so "never seen again" mixes genuine exit with a missing
act and cannot be read as removal from the state. Everyone in these diagrams
was observed in a post before and in a post after, which is a fact about the
record rather than an inference from it. The cost is that the diagrams describe
the minority who moved - roughly a tenth of each cohort - and say nothing about
the rest. The counts on each node state that share explicitly.

**Rank is the top of a person's position, not a single post.** Officials hold
several appointments at once, so standing before and after is the highest rank
held on each side. That is what "demotion" has to mean for someone holding
three posts, but it does mean a senior figure whose only new gazetted role is a
minor one reads as a fall.

Ministers and governors are folded into the senior tier: taken alone they
supply 38, 11 and 4 movers across the three ruptures, too few to draw.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from figstyle import (  # noqa: E402
    INK, MUTED, PROC, SOURCE, headline, plt, save,
)
from apparatus import in_interior_apparatus  # noqa: E402
from matplotlib.patches import Patch, PathPatch  # noqa: E402
from matplotlib.path import Path as MplPath  # noqa: E402

RUPTURES = [
    ("1987", pd.Timestamp("1987-11-07"), "7 Nov 1987", "Ben Ali displaces Bourguiba"),
    ("2011", pd.Timestamp("2011-01-14"), "14 Jan 2011", "Ben Ali flees; revolution"),
    ("2021", pd.Timestamp("2021-07-25"), "25 Jul 2021", "Saïed suspends parliament"),
]
RECORD_ENDS = pd.Timestamp("2026-05-31")

# Same-era comparison dates, as elsewhere in this project. They matter more here
# than anywhere else: most of what a diagram of this kind shows is the ordinary
# mobility of the bureaucracy, not the rupture. The three ruptures differ from
# one another by 5.6 to 6.5 points on average across the transition matrix, and
# each differs from its own ordinary times by only 3.1 to 7.0. A share read off
# one of these diagrams is therefore close to meaningless on its own, and every
# figure states the ordinary-times value beside it.
PLACEBO_LAGS = (3, 4, 5, 6, 7)

# Ordered top (most senior) to bottom, which is how the columns are stacked.
TIERS = [
    (60, 999, "Secretary-general,\ndirector-general, minister"),
    (50, 60, "Director"),
    (40, 50, "Deputy director"),
    (0, 40, "Head of service\nand below"),
]
TIER_LABELS = [label for _, _, label in TIERS]

# The same diverging treatment as the demotion figure: two validated hues with a
# neutral grey between them. Direction is also carried by the ribbon's slope, so
# it never rests on colour alone.
MOVE_COLOUR = {"up": "#1B5FC1", "lateral": "#B9B5A8", "down": "#A03B2C"}


def tier_of(score: float) -> str | None:
    for lo, hi, label in TIERS:
        if lo <= score < hi:
            return label
    return None


def transitions(spells: pd.DataFrame, t0: pd.Timestamp, years: int = 3):
    """The rank-to-rank flow matrix, plus how large the cohort behind it was."""
    t1 = min(t0 + pd.DateOffset(years=years), RECORD_ENDS)
    inpost = spells[(spells.start < t0) & (spells.end.isna() | (spells.end > t0))]
    before = inpost.groupby("person_id").rank_score.max()
    after = (spells[(spells.start >= t0) & (spells.start < t1)]
             .groupby("person_id").rank_score.max())
    j = before.to_frame("b").join(after.rename("a"), how="left").dropna()
    j["tb"] = j.b.map(tier_of)
    j["ta"] = j.a.map(tier_of)
    m = (pd.crosstab(j.tb, j.ta)
         .reindex(index=TIER_LABELS, columns=TIER_LABELS)
         .fillna(0).astype(int))
    return m, len(before), len(j)


def ribbon(ax, x0, x1, y0a, y0b, y1a, y1b, colour, alpha=0.62):
    """One flow, drawn as a pair of cubic curves closed into a band.

    The control points sit halfway between the columns, which gives the band a
    flat entry and exit: a ribbon that leaves its node horizontally reads as
    coming *from* that node rather than merely passing near it.
    """
    cx = (x0 + x1) / 2
    verts = [
        (x0, y0a), (cx, y0a), (cx, y1a), (x1, y1a),      # top edge, left→right
        (x1, y1b),                                        # down the right node
        (cx, y1b), (cx, y0b), (x0, y0b),                  # bottom edge, right→left
        (x0, y0a),
    ]
    codes = [MplPath.MOVETO, MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4,
             MplPath.LINETO,
             MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4,
             MplPath.CLOSEPOLY]
    ax.add_patch(PathPatch(MplPath(verts, codes), facecolor=colour, alpha=alpha,
                           edgecolor="none", zorder=2))


def _label_positions(ax, tops, texts, fontsize: float) -> list[float]:
    """Node-midpoint label centres, pushed apart where they would collide.

    A node's label sits at the node's midpoint, which is right until two thin
    nodes sit next to each other: the senior tiers of the interior apparatus
    are a tenth of the column each, and a three-line name centred on one of
    them runs into the name below. So the midpoints are treated as preferences
    rather than as positions, and a single bottom-up sweep opens a gap wherever
    two labels would otherwise meet.

    Line height is taken from the axes' own size in points rather than measured
    from a rendered text: the subplot grid is fixed before drawing, so this is
    known in advance and does not need a draw to resolve.
    """
    span = ax.get_ylim()[1] - ax.get_ylim()[0]
    ax_pts = ax.get_position().height * ax.figure.get_figheight() * 72.0
    line = (fontsize * 1.45 / ax_pts) * span if ax_pts else 0.0
    half = [len(t.split("\n")) / 2 * line for t in texts]

    ys = [(ytop + ybot) / 2 for ytop, ybot in tops]
    # Tiers run top to bottom, so sweep from the last upward and lift each
    # label clear of the one beneath it.
    for i in range(len(ys) - 2, -1, -1):
        floor = ys[i + 1] + half[i + 1] + half[i] + line * 0.25
        ys[i] = max(ys[i], floor)
    return ys


def draw_sankey(ax, m: pd.DataFrame, *, tier_names: bool = True,
                column_headers: bool = True, fontsize: float = 7.6) -> None:
    n = len(TIER_LABELS)
    left_tot = m.sum(axis=1).values.astype(float)
    right_tot = m.sum(axis=0).values.astype(float)
    total = left_tot.sum()

    # Geometry in axis units: columns at x = 0 and 1, a gap between stacked
    # nodes so that adjacent bands never touch.
    gap = 0.035
    usable = 1.0 - gap * (n - 1)
    x0, x1, node_w = 0.0, 1.0, 0.028

    def stack(totals):
        tops, y = [], 1.0
        for t in totals:
            h = usable * (t / total) if total else 0.0
            tops.append((y, y - h))
            y -= h + gap
        return tops

    left, right = stack(left_tot), stack(right_tot)

    # Set before anything is placed: _label_positions reads the y span to
    # convert a type size in points into the axes' own units.
    ax.set_xlim(-0.42 if tier_names else -0.16, 1.16)
    ax.set_ylim(-0.06, 1.06)
    ax.axis("off")

    lcur = [t for t, _ in left]
    rcur = [t for t, _ in right]
    # Within a node, flows are laid out in tier order so the bands do not cross
    # more than the data itself requires.
    for i in range(n):
        for j in range(n):
            v = m.iat[i, j]
            if not v:
                continue
            h_l = usable * (v / total)
            y0a, y0b = lcur[i], lcur[i] - h_l
            y1a, y1b = rcur[j], rcur[j] - h_l
            lcur[i] -= h_l
            rcur[j] -= h_l
            colour = MOVE_COLOUR["lateral"] if i == j else (
                MOVE_COLOUR["up"] if j < i else MOVE_COLOUR["down"])
            ribbon(ax, x0 + node_w, x1 - node_w, y0a, y0b, y1a, y1b, colour)

    for side, tops, totals, xx, ha in (
        ("left", left, left_tot, x0, "right"),
        ("right", right, right_tot, x1, "left"),
    ):
        # Tier names go on the left column only when asked for: the right
        # column repeats the same tiers in the same order, and spelling them
        # out twice crowds the thin nodes at the top.
        named = tier_names and side == "left"
        texts = [f"{TIER_LABELS[i]}\n{int(t):,}" if named else f"{int(t):,}"
                 for i, t in enumerate(totals)]
        ys = _label_positions(ax, tops, texts, fontsize)
        for i, ((ytop, ybot), y) in enumerate(zip(tops, ys)):
            ax.add_patch(plt.Rectangle(
                (xx - node_w if side == "right" else xx, ybot),
                node_w, ytop - ybot, facecolor=INK, edgecolor="none", zorder=4))
            ax.annotate(
                texts[i],
                xy=(xx - node_w * 1.6 if side == "left" else xx + node_w * 1.6,
                    y),
                ha=ha, va="center", fontsize=fontsize, color=INK,
                linespacing=1.45, zorder=5)

    if column_headers:
        ax.annotate("rank held at the rupture", xy=(x0, 1.075), ha="center",
                    va="bottom", fontsize=8.4, color=MUTED, fontweight="bold")
        ax.annotate("rank of the next post taken", xy=(x1, 1.075), ha="center",
                    va="bottom", fontsize=8.4, color=MUTED, fontweight="bold")



# ---------------------------------------------------------------------------
# figure 23 - the interior apparatus
# ---------------------------------------------------------------------------
# The interior ministry on its own cannot carry a diagram of this kind. Over
# three years it supplies 63, 157 and 81 movers, of whom 24, 34 and 21 stand
# above the bottom tier - a dozen or so people spread over nine upper cells,
# which would draw as authoritatively as anything else here and mean nothing.
#
# Three changes make it drawable, and each widens what is being described:
# the unit becomes the ministry *and its territorial administration*, which is
# what the interior ministry is in Tunisia; the window runs five years rather
# than three; and the four rank tiers collapse to three. Together these give
# 198, 711 and 678 movers with every cell populated.
IA_TIERS = [
    (60, 999, "Secretary-general,\ngovernor and above"),
    (40, 60, "Director and\ndeputy director"),
    (0, 40, "Head of service\nand below"),
]
IA_LABELS = [t[2] for t in IA_TIERS]


def ia_tier_of(score: float) -> str | None:
    for lo, hi, label in IA_TIERS:
        if lo <= score < hi:
            return label
    return None


def interior_transitions(spells: pd.DataFrame, t0: pd.Timestamp, years: int = 5):
    """Rank flows for people whose pre-rupture post was in the interior apparatus."""
    t1 = min(t0 + pd.DateOffset(years=years), RECORD_ENDS)
    inpost = spells[(spells.start < t0) & (spells.end.isna() | (spells.end > t0))]
    top = inpost.loc[inpost.groupby("person_id").rank_score.idxmax()]
    top = top[[in_interior_apparatus(p, o, f) for p, o, f in
               zip(top.org_portfolio, top.org_name.fillna(""), top.org_form.fillna(""))]]
    after = (spells[(spells.start >= t0) & (spells.start < t1)]
             .groupby("person_id").rank_score.max())
    j = top.merge(after.rename("a"), left_on="person_id", right_index=True, how="inner")
    if j.empty:
        return None, 0, 0
    m = (pd.crosstab(j.rank_score.map(ia_tier_of), j.a.map(ia_tier_of))
         .reindex(index=IA_LABELS, columns=IA_LABELS).fillna(0).astype(int))
    return m, len(j), len(top)


def fig_interior(spells: pd.DataFrame) -> None:
    global TIER_LABELS
    saved = TIER_LABELS
    TIER_LABELS = IA_LABELS               # draw_sankey reads the module-level list
    try:
        fig, axes = plt.subplots(2, 3, figsize=(14.6, 8.2))
        fig.subplots_adjust(top=0.72, bottom=0.10, left=0.15, right=0.985,
                            wspace=0.26, hspace=0.30)
        deltas = []
        for col, (key, t0, datestr, gloss) in enumerate(RUPTURES):
            m, n, cohort = interior_transitions(spells, t0)
            plc = [interior_transitions(spells, t0 - pd.DateOffset(years=k))
                   for k in PLACEBO_LAGS]
            pm = sum(p[0] for p in plc if p[0] is not None)
            pn = sum(p[1] for p in plc)

            def fell(mat, tot):
                return sum(mat.iat[i, j] for i in range(3) for j in range(3)
                           if j > i) / tot * 100

            for row, (mm, nn, lbl) in enumerate((
                (m, n, f"after {key}"),
                (pm, pn, "ordinary times"),
            )):
                ax = axes[row, col]
                # Named once, top left. The ordinary-times panel below has a
                # thinner senior node, and repeating the names there ran them
                # into the tier beneath.
                draw_sankey(ax, mm, tier_names=(col == 0 and row == 0),
                            column_headers=False, fontsize=6.8)
                ax.set_title(f"{lbl}   ·   {nn:,} movers   ·   "
                             f"{fell(mm, nn):.1f}% fell a tier",
                             color=INK, fontsize=8.6)
            deltas.append(fell(m, n) - fell(pm, pn))
            axes[0, col].annotate(
                f"{key}  ·  {datestr}\n{gloss}", xy=(0.5, 1.30),
                xycoords="axes fraction", ha="center", va="bottom",
                fontsize=9.6, color=INK, fontweight="bold", linespacing=1.5)

        axes[1, 1].legend(handles=[
            Patch(facecolor=MOVE_COLOUR["up"], alpha=0.62, label="moved up a tier"),
            Patch(facecolor=MOVE_COLOUR["lateral"], alpha=0.62, label="stayed in tier"),
            Patch(facecolor=MOVE_COLOUR["down"], alpha=0.62, label="moved down a tier"),
        ], loc="upper center", bbox_to_anchor=(0.5, -0.06), ncol=3)

        headline(
            fig,
            "The interior apparatus, against itself in ordinary times",
            "The ministry of the interior together with the governorates and "
            "municipalities it administers: rank held on the eve of each rupture "
            "against the rank of the next post taken within five years. Each panel "
            "is scaled to its own total. The row beneath every rupture is the same "
            "cohort drawn from five ordinary years of the same era, which is the "
            "only thing that makes the row above it readable. On this measure the "
            "three ruptures move little: "
            # Read off the panels rather than typed in. An earlier figure in this
            # set carried a hand-written claim that its own data had stopped
            # supporting; a subtitle that recomputes cannot drift from the figure
            # above it.
            + ", ".join(f"{d:+.1f}" for d in deltas)
            + " points of tier-crossing demotion against their own eras.",
            width=150,
        )
        save(fig, "fig23_interior_apparatus_flow",
             SOURCE + "  The interior ministry alone cannot carry this figure: over "
                      "three years it supplies 63, 157 and 81 movers, of whom 24, 34 "
                      "and 21 stand above the bottom tier. The unit is therefore the "
                      "ministry with its territorial administration, the window is "
                      "five years rather than three, and the ranks collapse to three "
                      "tiers. Each of those widens the measure, and the result is not "
                      "the +21.0 points the ministry-level demotion figure reports "
                      "for the interior in 2021: that figure counts any fall in rank "
                      "over three years for the ministry proper, where this counts "
                      "only falls that cross one of two boundaries, over five years, "
                      "across a body several times larger. Both are true of what they "
                      "measure; neither is a check on the other.")
    finally:
        TIER_LABELS = saved


def main() -> None:
    print("loading tables…")
    spells = pd.read_csv(PROC / "spells.csv.gz", low_memory=False)
    spells["start"] = pd.to_datetime(spells.start_date, errors="coerce")
    spells["end"] = pd.to_datetime(spells.end_date, errors="coerce")
    spells = spells.dropna(subset=["start"])

    print("drawing…")
    for key, t0, datestr, gloss in RUPTURES:
        m, n_cohort, n_moved = transitions(spells, t0)
        # The share of the senior tier that reappears at the bottom one, against
        # the same share in ordinary times. The level alone is not quotable: at
        # 1987 it is 41%, which sounds severe until the era's own figure turns
        # out to be 45%. Raw up/down totals are not quotable either, since the
        # bottom tier cannot fall and the top cannot rise.
        senior_total = m.iloc[0].sum()
        senior_fell = m.iat[0, len(TIER_LABELS) - 1]
        share = senior_fell / senior_total if senior_total else float("nan")
        base = []
        for lag in PLACEBO_LAGS:
            pm, _, _ = transitions(spells, t0 - pd.DateOffset(years=lag))
            tot = pm.iloc[0].sum()
            if tot:
                base.append(pm.iat[0, len(TIER_LABELS) - 1] / tot)
        ordinary = float(np.mean(base)) if base else float("nan")

        fig, ax = plt.subplots(figsize=(9.4, 5.6))
        fig.subplots_adjust(top=0.70, bottom=0.14, left=0.20, right=0.80)
        draw_sankey(ax, m)
        ax.legend(handles=[
            Patch(facecolor=MOVE_COLOUR["up"], alpha=0.62, label="moved up a tier"),
            Patch(facecolor=MOVE_COLOUR["lateral"], alpha=0.62, label="stayed in tier"),
            Patch(facecolor=MOVE_COLOUR["down"], alpha=0.62, label="moved down a tier"),
        ], loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=3)

        headline(
            fig,
            f"{key}: where the officeholders went   ·   {gloss}",
            f"Of the {n_cohort:,} people holding an office on {datestr}, the "
            f"{n_moved:,} who took a further post within three years "
            f"({n_moved / n_cohort:.0%}), by the rank they held and the rank they "
            f"moved to. Of the {senior_total:,} standing at secretary-general or "
            f"above, {senior_fell:,} ({share:.0%}) next appear at head of service "
            f"or below, against {ordinary:.0%} for the same cohort in ordinary "
            f"times: a difference of {(share - ordinary) * 100:+.0f} points. The "
            f"remaining "
            f"{n_cohort - n_moved:,} of the cohort have no further post in the "
            f"record, which the gazette's patchy treatment of departures makes "
            f"unreadable as removal from the state.",
        )
        save(fig, f"fig{18 + [r[0] for r in RUPTURES].index(key)}_flow_{key}",
             SOURCE + "  Rank is the ordinal scale in the codebook; a person "
                      "holding several posts is placed at the highest, before and "
                      "after alike. Ministers and governors are folded into the "
                      "senior tier, supplying only 38, 11 and 4 movers across the "
                      "three ruptures. Ribbon width is people, and the columns are "
                      "scaled to the same total, so tier heights on the two sides "
                      "are comparable. These diagrams are descriptive and carry no "
                      "counterfactual: a tier that looks busy may simply be a busy "
                      "tier. Whether a rupture demoted more than its era ordinarily "
                      "did is the question the demotion figure answers, against "
                      "placebo cohorts. That figure also counts any fall in rank, "
                      "where these count only falls that cross a tier boundary - "
                      "946 against 537 in 2021 - so its percentages are the larger "
                      "of the two and the two are not in conflict. The three "
                      "diagrams resemble one another because most of what they "
                      "show is the standing mobility of the bureaucracy rather "
                      "than the rupture: across the whole matrix the ruptures "
                      "differ from each other by 5.6 to 6.5 points on average, "
                      "and each from its own ordinary times by 3.1 to 7.0.")
    # --- the three side by side ------------------------------------------
    fig, axes = plt.subplots(1, 3, figsize=(15.0, 5.4))
    fig.subplots_adjust(top=0.64, bottom=0.16, left=0.13, right=0.985, wspace=0.26)
    for ax, (key, t0, datestr, gloss) in zip(axes, RUPTURES):
        m, n_cohort, n_moved = transitions(spells, t0)
        # Every panel is scaled to its own total, so a node's height is the
        # share of that cohort's movers and not a count. The three cohorts run
        # from 1,179 to 4,050, and drawing them at a common scale would leave
        # 1987 a third the size of 2011 and compare nothing.
        # Tier names on the first panel only. The vertical order is identical
        # everywhere, but the heights are not - each panel is scaled to its own
        # cohort - so a single shared label column would sit beside the right
        # tier in one panel and the wrong one in the other two.
        draw_sankey(ax, m, tier_names=ax is axes[0], column_headers=False,
                    fontsize=7.0)
        ax.set_title(f"{key}  ·  {datestr}\n{gloss}\n{n_moved:,} movers of "
                     f"{n_cohort:,} in post",
                     color=INK, fontsize=9.2, linespacing=1.6)

    axes[1].legend(handles=[
        Patch(facecolor=MOVE_COLOUR["up"], alpha=0.62, label="moved up a tier"),
        Patch(facecolor=MOVE_COLOUR["lateral"], alpha=0.62, label="stayed in tier"),
        Patch(facecolor=MOVE_COLOUR["down"], alpha=0.62, label="moved down a tier"),
    ], loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=3)

    headline(
        fig,
        "The three ruptures side by side: mostly the same bureaucracy",
        "In each panel the left column is the rank held on the eve of the "
        "rupture and the right column the rank of the next post taken within "
        "three years, for the people who took one. The diagrams "
        "resemble each other because most of what they show is the standing "
        "mobility of the Tunisian administration rather than the rupture: across "
        "the whole matrix the three differ from one another by 5.6 to 6.5 points "
        "on average, and each from its own era's ordinary times by 3.1 to 7.0. "
        "Only 2021 departs from its own era - 44% of its senior tier reappears at "
        "head of service or below, against 33% in ordinary times, where 1987 and "
        "2011 both fall slightly short of theirs.",
        width=150,
    )
    save(fig, "fig21_flow_all_three",
         SOURCE + "  Each panel is scaled to its own total, so a node's height is "
                  "the share of that cohort's movers, not a count: the cohorts run "
                  "from 1,179 to 4,050 and a common scale would compare nothing. "
                  "Node figures are people. Rank is the ordinal scale in the "
                  "codebook, a person holding several posts placed at the highest. "
                  "Only people observed in a post before and after appear, which "
                  "is a tenth or so of each cohort; the rest have no further post "
                  "in the record, and the gazette's patchy treatment of departures "
                  "makes that unreadable as removal from the state. Falls here "
                  "cross a tier boundary, a higher bar than the any-rank-fall "
                  "measure in the demotion figure.")
    fig_interior(spells)
    print("done")


if __name__ == "__main__":
    main()
