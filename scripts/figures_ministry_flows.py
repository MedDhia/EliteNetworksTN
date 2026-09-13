"""Where interior and defence officials go, named to the ministry.

The companion figure to the interior–defence exchange, which showed everything
beyond the security apparatus as a single block of 1,654 moves. This opens that
block and names it.

Naming it is most of the work. A portfolio-only classifier leaves 28% of these
destinations unplaced, because roughly half the directorates in the table carry
no portfolio at all; reading the body's own name for the ministry it hangs off
brings that to 8%. What remains unplaced is shown rather than folded into a
ministry it might not belong to.

Not every destination is a ministry, and the ones that are not are kept apart
rather than swept into "other": a public enterprise, a town hall and a court are
each a different kind of landing place, and the distinction is the sort of thing
this figure exists to show.

Twenty-eight ministries appear. Eight are drawn individually — everything above
sixty moves — and the remaining twenty are pooled, because a ribbon of one
person drawn beside a ribbon of six hundred invites a comparison the data will
not support.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from figures_sankey import _label_positions, ribbon  # noqa: E402
from apparatus import (  # noqa: E402
    consecutive_moves, ministry_destination, security_branch,
)
from figstyle import CAT4, INK, MUTED, PROC, SOURCE, headline, plt, save  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

INTERIOR = "Interior ministry"
DEFENCE = "Defence"

# Colour carries which ministry a flow left, and nothing else. The same
# validated pair as the outflow figures, so a reader who has learned the
# encoding once does not relearn it: all checks pass under `--pairs all`,
# worst ΔE 23.6 protan and 27.9 normal.
ORIGIN_COLOUR = {INTERIOR: CAT4[1], DEFENCE: CAT4[0]}

# Individually drawn where a destination takes more than sixty of the 2,693
# moves; the rest of the ministries are pooled. The order is fixed, so a
# destination keeps its place whichever origin is being read.
NAMED = ["Finance", "Prime Minister's Office", "Higher Education",
         "Agriculture", "Social Affairs", "Foreign Affairs", "Education",
         "Health"]
OTHER_MINISTRIES = "Other ministries"
OTHER_BODIES = "Other public bodies"
POOLED_BODIES = {"Courts", "Universities and hospitals",
                 "Independent authorities"}

ORDER = ([INTERIOR, "Governorates", DEFENCE] + NAMED
         + [OTHER_MINISTRIES, "Municipalities", "Public enterprise",
            OTHER_BODIES, "Not identifiable"])

STRUCTURAL = {INTERIOR, "Governorates", DEFENCE, "Municipalities",
              "Public enterprise", "Not identifiable"} | POOLED_BODIES


def collapse(dest: str) -> str:
    if dest in POOLED_BODIES:
        return OTHER_BODIES
    if dest in STRUCTURAL or dest in NAMED:
        return dest
    return OTHER_MINISTRIES          # a ministry below the drawing threshold


def moves(spells: pd.DataFrame) -> pd.DataFrame:
    """Every post-to-post move whose origin is the interior or defence ministry.

    The governorates are not an origin here. They belong to the interior in the
    apparatus sense, but this figure is about the two ministries as employers,
    and a governor is not an official of the ministry's central administration.
    """
    m = consecutive_moves(spells)
    m = m[m.branch.isin(("interior", "defence"))].copy()
    m["origin"] = m.branch.map({"interior": INTERIOR, "defence": DEFENCE})
    m["target"] = [collapse(ministry_destination(p, o, f)) for p, o, f in
                   zip(m.to_portfolio, m.to_org, m.to_form)]
    return m


def draw(ax, mat: pd.DataFrame, fontsize: float = 7.4) -> None:
    total = float(mat.values.sum())
    gap_l, gap_r = 0.10, 0.012
    usable_l = 1.0 - gap_l * (len(mat.index) - 1)
    usable_r = 1.0 - gap_r * (len(mat.columns) - 1)
    x0, x1, node_w = 0.0, 1.0, 0.02

    ax.set_xlim(-0.30, 1.52)
    ax.set_ylim(-0.03, 1.03)
    ax.axis("off")

    def stack(totals, usable, gap):
        tops, y = [], 1.0
        for t in totals:
            h = usable * (t / total)
            tops.append((y, y - h))
            y -= h + gap
        return tops

    lt = mat.sum(axis=1).values.astype(float)
    rt = mat.sum(axis=0).values.astype(float)
    left, right = stack(lt, usable_l, gap_l), stack(rt, usable_r, gap_r)

    lcur = [t for t, _ in left]
    rcur = [t for t, _ in right]
    for i, origin in enumerate(mat.index):
        for jx in range(len(mat.columns)):
            v = mat.iat[i, jx]
            if not v:
                continue
            h = usable_r * (v / total)
            y0a, y0b = lcur[i], lcur[i] - h
            y1a, y1b = rcur[jx], rcur[jx] - h
            lcur[i] -= h
            rcur[jx] -= h
            ribbon(ax, x0 + node_w, x1 - node_w, y0a, y0b, y1a, y1b,
                   ORIGIN_COLOUR[origin], alpha=0.55)

    for (ytop, ybot), t, name in zip(left, lt, mat.index):
        ax.add_patch(plt.Rectangle((x0, ybot), node_w, ytop - ybot,
                                   facecolor=ORIGIN_COLOUR[name],
                                   edgecolor="none", zorder=4))
        ax.annotate(f"{name}\n{int(t):,} moves",
                    xy=(x0 - node_w * 1.8, (ytop + ybot) / 2), ha="right",
                    va="center", fontsize=fontsize + 0.8, color=INK,
                    linespacing=1.4, zorder=5)

    # Sixteen destination nodes, most of them a few percent of the column, so
    # their midpoints sit inside a line-height of one another.
    texts = [f"{c}   {int(t):,}" for c, t in zip(mat.columns, rt)]
    ys = _label_positions(ax, right, texts, fontsize)
    for k, ((ytop, ybot), t, y) in enumerate(zip(right, rt, ys)):
        ax.add_patch(plt.Rectangle((x1 - node_w, ybot), node_w, ytop - ybot,
                                   facecolor=INK, edgecolor="none", zorder=4))
        if t:
            ax.annotate(texts[k], xy=(x1 + node_w * 1.8, y), ha="left",
                        va="center", fontsize=fontsize, color=INK, zorder=5)


def state_baseline(spells: pd.DataFrame, ministries) -> pd.Series:
    """Each ministry's share of all posts in the state, on the same naming.

    The comparison the subtitle rests on. Without it "the outflow looks like
    the state" is an assertion about a distribution with nothing to compare it
    to; with it the claim is a number, and the number can come out wrong.
    """
    d = [ministry_destination(p, o, f) for p, o, f in
         zip(spells.org_portfolio, spells.org_name, spells.org_form)]
    t = pd.Series([collapse(x) for x in d])
    t = t[t.isin(ministries)]
    return t.value_counts(normalize=True) * 100


def fig_ministry_flows(spells: pd.DataFrame) -> None:
    m = moves(spells)
    mat = (pd.crosstab(m.origin, m.target)
           .reindex(index=[INTERIOR, DEFENCE], columns=ORDER)
           .fillna(0).astype(int))

    n_int, n_def = int(mat.loc[INTERIOR].sum()), int(mat.loc[DEFENCE].sum())
    unplaced = int(mat["Not identifiable"].sum())
    stay_int = mat.loc[INTERIOR, INTERIOR] + mat.loc[INTERIOR, "Governorates"]
    stay_def = mat.loc[DEFENCE, DEFENCE]

    ministries = set(NAMED) | {OTHER_MINISTRIES}
    leavers = m[(m.origin == INTERIOR) & m.target.isin(ministries)]
    got = leavers.target.value_counts(normalize=True) * 100
    want = state_baseline(spells, ministries)
    gap = (got - want).dropna()
    worst = gap.abs().idxmax()

    fig, ax = plt.subplots(figsize=(12.4, 9.2))
    fig.subplots_adjust(top=0.80, bottom=0.07, left=0.17, right=0.86)
    draw(ax, mat)
    ax.legend(handles=[Patch(facecolor=ORIGIN_COLOUR[k], alpha=0.62, label=k)
                       for k in (INTERIOR, DEFENCE)],
              loc="upper center", bbox_to_anchor=(0.5, -0.015), ncol=2,
              title="the post held before the move")

    headline(
        fig,
        "Where the two security ministries send people, ministry by ministry",
        "Every consecutive move made from a post in the interior or defence "
        "ministry, across the whole record, 1957–2026, with the destination "
        f"named to its ministry wherever the record allows. Of {n_int:,} moves "
        f"out of the interior, {stay_int / n_int * 100:.0f}% stay in the "
        f"ministry or go to a governorate; of {n_def:,} out of defence, "
        f"{stay_def / n_def * 100:.0f}% stay in defence. What leaves goes nowhere "
        "in particular. Set the interior's outflow against each ministry's "
        "share of all posts in the state and no ministry is out by more than "
        f"{gap.abs().max():.0f} points ({worst}, {gap[worst]:+.0f}); the mean "
        f"miss is {gap.abs().mean():.1f}. The people the interior loses "
        "disperse across the administration in about the proportions the "
        "administration already has. The one conspicuous exception each "
        "ministry makes is to the other.",
        width=132,
    )
    save(fig, "fig28_ministry_flows",
         SOURCE + "  Destination is named from the post's portfolio where it "
                  "has one and from the body's own name where it does not — "
                  "roughly half the directorates in the table carry no "
                  "portfolio, and a portfolio-only rule leaves 28% of these "
                  "destinations unplaced against "
                  f"{unplaced / (n_int + n_def) * 100:.0f}% here. Where a "
                  "portfolio names several merged ministries, the lead one "
                  "stands for it: a person takes one post, and counting the "
                  "move into every merged domain would make the flows sum to "
                  "more than the people. Eight ministries are drawn "
                  "individually, being those above sixty moves; the other "
                  "twenty are pooled. Destinations that are not ministries are "
                  "kept apart rather than swept into the pool. Governorates "
                  "are a destination but not an origin: they belong to the "
                  "interior in the apparatus sense, but this figure treats the "
                  "two ministries as employers and a governor is not an "
                  "official of the central administration. A move is one post "
                  "to the next by start date, a person holding several posts "
                  "placed at the highest. The proportionality in the subtitle "
                  "compares the interior's outflow to each ministry's share of "
                  "every post in the record on the same naming, which is a "
                  "stock against a flow and so a rough benchmark rather than a "
                  "test: it answers whether the outflow is tilted towards any "
                  "ministry, not whether a given tilt is larger than chance. "
                  "The largest tilts are towards the prime minister's office, "
                  "social affairs and higher education, and away from "
                  "education.")


def main() -> None:
    print("loading tables…")
    spells = pd.read_csv(PROC / "spells.csv.gz", low_memory=False)
    spells["start"] = pd.to_datetime(spells.start_date, errors="coerce")
    spells = spells.dropna(subset=["start"])
    spells["org_name"] = spells.org_name.fillna("")
    spells["org_form"] = spells.org_form.fillna("")
    spells["branch"] = [security_branch(p, o, f) for p, o, f in
                        zip(spells.org_portfolio, spells.org_name,
                            spells.org_form)]
    print("drawing…")
    fig_ministry_flows(spells)
    print("done")


if __name__ == "__main__":
    main()
