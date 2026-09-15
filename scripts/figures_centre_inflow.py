"""Which parts of the state feed the two offices at the centre.

The prime minister's office and the presidency of the republic are the top of
two different hierarchies — the head of government and the head of state — and
this asks whether they are staffed from the same places.

The unit is an arrival: a post in one of the two offices, preceded in the same
career by a post somewhere else, with consecutive posts in one organisation
collapsed so that what is counted is the crossing. 1,505 arrivals at the prime
minister's office and 573 at the presidency.

**Why one step and not a longer path.** Two-step approaches exist but will not
carry a ranking: the most common route into the presidency through two named
predecessors is walked by nine people, and there are 224 distinct ones. The
last post before arrival is the deepest the record supports here.

**Why shares and not counts.** The prime minister's office takes nearly three
times as many arrivals as the presidency, so a count comparison would say only
that one office is bigger. The question is whether the *mix* differs, which is
a question about composition; counts are on the figure so the base is never out
of sight.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from figures_trajectories import trajectories  # noqa: E402
from apparatus import wilson  # noqa: E402
from figstyle import (  # noqa: E402
    CAT4, INK, MUTED, PROC, RULE, SOURCE, headline, plt, save,
)
from matplotlib.lines import Line2D  # noqa: E402

PM = "Prime Minister's Office"
PRESIDENCY = "Presidency of the Republic"

# The validated pair again, one office each, reinforced by the legend and by
# the direct labels on every row.
PM_COLOUR = CAT4[1]
PR_COLOUR = CAT4[0]

# Below this an origin's two shares are being compared on a handful of people
# and the dumbbell would be drawing noise at full width.
MIN_ARRIVALS = 40

SHORT = {"Universities and hospitals": "Universities and hospitals",
         "Prime Minister's Office": "PM's Office"}


def arrivals(seqs) -> dict[str, Counter]:
    """For each of the two offices, what post each arrival came from."""
    out = {PM: Counter(), PRESIDENCY: Counter()}
    for q in seqs:
        for i in range(1, len(q)):
            if q[i] in out:
                out[q[i]][q[i - 1]] += 1
    return out


def rows(seqs):
    a = arrivals(seqs)
    n_pm, n_pr = sum(a[PM].values()), sum(a[PRESIDENCY].values())
    out = []
    for org in set(a[PM]) | set(a[PRESIDENCY]):
        if org in (PM, PRESIDENCY):      # the two offices feed each other; that
            continue                     # is a different question from this one
        k_pm, k_pr = a[PM][org], a[PRESIDENCY][org]
        if k_pm + k_pr < MIN_ARRIVALS:
            continue
        p_pm, p_pr = k_pm / n_pm * 100, k_pr / n_pr * 100
        lo, hi = wilson(k_pr, n_pr)      # the smaller base carries the interval
        out.append({"org": org, "k_pm": k_pm, "k_pr": k_pr, "p_pm": p_pm,
                    "p_pr": p_pr, "diff": p_pr - p_pm,
                    "clears": not (lo <= p_pm <= hi), "lo": lo, "hi": hi})
    out.sort(key=lambda r: r["diff"])
    return out, n_pm, n_pr


def fig_centre_inflow(spells: pd.DataFrame) -> None:
    seqs = trajectories(spells)
    data, n_pm, n_pr = rows(seqs)

    fig, ax = plt.subplots(figsize=(12.0, 7.4))
    fig.subplots_adjust(top=0.70, bottom=0.19, left=0.235, right=0.90)

    for i, r in enumerate(data):
        y = i
        ax.plot([r["p_pm"], r["p_pr"]], [y, y], color=RULE, lw=1.6, zorder=2,
                solid_capstyle="round")
        # Filled where the presidency's interval excludes the prime minister's
        # office's share; open where the two are not separable.
        for x, colour in ((r["p_pm"], PM_COLOUR), (r["p_pr"], PR_COLOUR)):
            if r["clears"]:
                ax.plot([x], [y], marker="o", ms=8, color=colour, zorder=4)
            else:
                ax.plot([x], [y], marker="o", ms=8, mfc="white", mec=colour,
                        mew=1.6, zorder=4)
        right = max(r["p_pm"], r["p_pr"])
        ax.annotate(f"{r['diff']:+.1f} pp", xy=(right + 0.45, y), va="center",
                    ha="left", fontsize=7.8, color=INK if r["clears"] else MUTED,
                    fontweight="bold" if r["clears"] else "normal")
        ax.annotate(f"{r['k_pm']} / {r['k_pr']}", xy=(-0.55, y), va="center",
                    ha="right", fontsize=7.0, color=MUTED)

    ax.set_yticks(range(len(data)))
    ax.set_yticklabels([SHORT.get(r["org"], r["org"]) for r in data],
                       fontsize=8.6, color=INK)
    ax.set_ylim(-0.7, len(data) - 0.3)
    ax.set_xlim(-3.2, 14.6)
    ax.set_xticks([0, 2, 4, 6, 8, 10, 12, 14])
    ax.set_xlabel("share of that office's arrivals (%)", fontsize=8.4)
    ax.xaxis.grid(True, lw=0.6)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.legend(handles=[
        Line2D([], [], marker="o", ls="", ms=8, color=PM_COLOUR,
               label=f"Prime Minister's Office  ({n_pm:,} arrivals)"),
        Line2D([], [], marker="o", ls="", ms=8, color=PR_COLOUR,
               label=f"Presidency of the Republic  ({n_pr:,})"),
        Line2D([], [], marker="o", ls="", ms=8, mfc="white", mec=INK, mew=1.6,
               label="open: the two shares are not separable"),
    # Below the axis, not inside it: at lower right the legend sat on top of
    # the finance row, which is the largest difference on the figure.
    ], loc="upper center", bbox_to_anchor=(0.5, -0.085), ncol=3)

    # Largest difference first in both lists, so the sentence names the
    # strongest case rather than whichever row happened to sort first.
    up = sorted((r for r in data if r["clears"] and r["diff"] > 0),
                key=lambda r: -r["diff"])
    down = sorted((r for r in data if r["clears"] and r["diff"] < 0),
                  key=lambda r: r["diff"])
    headline(
        fig,
        "The presidency recruits from the outward-facing state, the prime minister's office from the domestic one",
        "The post held immediately before an arrival at each office, as a share "
        "of that office's arrivals. The counts to the left of each row are "
        "prime minister's office and presidency. The two offices draw on "
        "different parts of the administration: "
        + ", ".join(r["org"].lower() for r in up) +
        " send a larger share of their movers to the presidency, while "
        + ", ".join(r["org"].lower() for r in down) +
        " send a larger share to the prime minister's office. Foreign affairs "
        f"alone supplies {data[-1]['p_pr']:.0f}% of the presidency's arrivals "
        f"against {data[-1]['p_pm']:.0f}% of the prime minister's.",
        width=140,
    )
    save(fig, "fig31_centre_inflow",
         SOURCE + "  An arrival is a post in one of the two offices preceded "
                  "in the same career by a post elsewhere, consecutive posts in "
                  "one organisation collapsed so that what is counted is the "
                  "crossing. Origins supplying fewer than "
                  f"{MIN_ARRIVALS} arrivals across both offices are not drawn: "
                  "below that the two shares are being compared on a handful of "
                  "people. The two offices feed each other — the prime "
                  "minister's office is the second largest single source of "
                  "arrivals at the presidency — and that row is left out here "
                  "because it answers a different question from which parts of "
                  "the administration supply the centre. The interval is "
                  "Wilson on the presidency's share, the smaller of the two "
                  "bases; a filled pair means it excludes the prime minister's "
                  "office's share. Shares are of arrivals, not of the "
                  "originating body's size, so a large ministry can lead on "
                  "count without leading on either share. Two-step approaches "
                  "are not drawn: the commonest route into the presidency "
                  "through two named predecessors is walked by nine people.")


def main() -> None:
    print("loading tables…")
    spells = pd.read_csv(PROC / "spells.csv.gz", low_memory=False)
    spells["start"] = pd.to_datetime(spells.start_date, errors="coerce")
    spells = spells.dropna(subset=["start"])
    spells["org_name"] = spells.org_name.fillna("")
    spells["org_form"] = spells.org_form.fillna("")
    print("drawing…")
    fig_centre_inflow(spells)
    print("done")


if __name__ == "__main__":
    main()
