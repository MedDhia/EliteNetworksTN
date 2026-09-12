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


def draw_sankey(ax, m: pd.DataFrame) -> None:
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
        for i, ((ytop, ybot), t) in enumerate(zip(tops, totals)):
            ax.add_patch(plt.Rectangle(
                (xx - node_w if side == "right" else xx, ybot),
                node_w, ytop - ybot, facecolor=INK, edgecolor="none", zorder=4))
            ax.annotate(
                f"{TIER_LABELS[i]}\n{int(t):,}",
                xy=(xx - node_w * 1.6 if side == "left" else xx + node_w * 1.6,
                    (ytop + ybot) / 2),
                ha=ha, va="center", fontsize=7.6, color=INK, linespacing=1.45,
                zorder=5)

    ax.set_xlim(-0.42, 1.42)
    ax.set_ylim(-0.06, 1.06)
    ax.axis("off")
    ax.annotate("rank held at the rupture", xy=(x0, 1.075), ha="center",
                va="bottom", fontsize=8.4, color=MUTED, fontweight="bold")
    ax.annotate("rank of the next post taken", xy=(x1, 1.075), ha="center",
                va="bottom", fontsize=8.4, color=MUTED, fontweight="bold")


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
    print("done")


if __name__ == "__main__":
    main()
