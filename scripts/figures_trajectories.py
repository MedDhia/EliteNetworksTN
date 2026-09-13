"""The shapes a bureaucratic career takes across organisations.

A trajectory here is the ordered sequence of organisations a person passes
through, with consecutive posts in the same organisation collapsed: what is
counted is the crossing, not the re-appointment.

**Why this is not a flow diagram.** Every other movement figure in this set is
one, and a three-stage alluvial over twenty-odd organisations is the obvious
next step. It is also unreadable — eight thousand distinct three-step routes
drawn as ribbons is a grey mat, and the question "which trajectories are most
common" is a ranking question, which a ranking answers and a Sankey buries.

**What the ranking shows.** Three-step segments return to where they started
24.2% of the time. Against a first-order Markov null — the next organisation
drawn from where the middle one usually leads, ignoring where the person came
from — the expected rate is 5.6%. Careers are four times more likely to come
back than the transition matrix alone predicts, which is to say they are not
Markovian at all: the origin is still doing work two moves later. This is the
secondment pattern, an official posted out to a public enterprise or a field
office and returning to the ministry that sent them.

The two panels share an x axis, and that is the point of the figure. Round
trips are few routes travelled often; one-way paths are many routes travelled
once. Read the right-hand bars against the left-hand ones rather than against
each other.
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from apparatus import ministry_destination  # noqa: E402
from figstyle import (  # noqa: E402
    CAT4, INK, MUTED, PROC, RULE, SOURCE, headline, plt, save,
)

UNPLACED = "Not identifiable"
TOP_N = 12

# Two validated hues, one per family, reinforced by the panel each sits in and
# by its title. All checks pass under `--pairs all`, worst ΔE 23.6 protan and
# 27.9 normal.
ROUND_TRIP = CAT4[1]
ONE_WAY = CAT4[0]

SHORT = {"Prime Minister's Office": "PM's Office",
         "Presidency of the Republic": "Presidency",
         "Universities and hospitals": "Universities/hospitals",
         "Relations with Parliament": "Parl. relations",
         "International Cooperation": "Int'l Cooperation"}


def squash(seq):
    """Collapse consecutive repeats: a career is counted by its crossings."""
    out = []
    for v in seq:
        if not out or out[-1] != v:
            out.append(v)
    return out


def trajectories(spells: pd.DataFrame, drop_unplaced: bool = True):
    """One list of organisations per person, in order, repeats collapsed."""
    s = spells.sort_values(["person_id", "start", "rank_score"])
    s = s.loc[s.groupby(["person_id", "start"]).rank_score.idxmax()]
    s = s.sort_values(["person_id", "start"])
    state = [ministry_destination(p, o, f) for p, o, f in
             zip(s.org_portfolio, s.org_name, s.org_form)]
    s = s.assign(state=state)
    out = []
    for _pid, g in s.groupby("person_id", sort=False):
        q = list(g.state)
        if drop_unplaced:
            q = [x for x in q if x != UNPLACED]
        q = squash(q)
        if len(q) >= 2:
            out.append(q)
    return out


def return_rate(seqs) -> tuple[int, int, float]:
    """Observed returns, total three-step segments, and the Markov expectation.

    The null asks: if the third organisation were drawn from wherever the
    second one usually leads, ignoring where the person came from, how often
    would it happen to be the origin? Anything above that is memory of origin
    rather than a property of the transition matrix.
    """
    nxt = defaultdict(Counter)
    for q in seqs:
        for i in range(len(q) - 1):
            nxt[q[i]][q[i + 1]] += 1
    total = returns = 0
    expected = 0.0
    for q in seqs:
        for i in range(len(q) - 2):
            a, b, c = q[i], q[i + 1], q[i + 2]
            total += 1
            returns += c == a
            d = nxt[b]
            n = sum(d.values())
            expected += (d.get(a, 0) / n) if n else 0.0
    return returns, total, expected


def families(seqs):
    """Round trips keyed by (origin, waypoint); one-way routes by their triple."""
    rt, ow = Counter(), Counter()
    for q in seqs:
        for i in range(len(q) - 2):
            a, b, c = q[i], q[i + 1], q[i + 2]
            if c == a:
                rt[(a, b)] += 1
            elif len({a, b, c}) == 3:
                ow[(a, b, c)] += 1
    return rt, ow


def _label(parts) -> str:
    return "  →  ".join(SHORT.get(p, p) for p in parts)


def draw_panel(ax, rows, colour: str, xmax: int, title: str) -> None:
    ax.set_title(title, color=INK, fontsize=9.4, loc="left")
    for i, (parts, n) in enumerate(rows):
        y = len(rows) - 1 - i
        ax.barh(y, n, height=0.62, color=colour, alpha=0.8, zorder=3)
        ax.annotate(f"{n}", xy=(n + xmax * 0.012, y), va="center", ha="left",
                    fontsize=7.6, color=INK, zorder=4)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([_label(p) for p, _ in rows][::-1], fontsize=7.8,
                       color=INK)
    ax.set_ylim(-0.7, len(rows) - 0.3)
    ax.set_xlim(0, xmax)
    ax.xaxis.grid(True, lw=0.6)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("career segments taking this route", fontsize=8.2)


def fig_trajectories(spells: pd.DataFrame) -> None:
    seqs = trajectories(spells)
    rt, ow = families(seqs)
    returns, total, expected = return_rate(seqs)
    all_returns, all_total, all_expected = return_rate(
        trajectories(spells, drop_unplaced=False))

    rt_rows = [(list(k) + [k[0]], v) for k, v in rt.most_common(TOP_N)]
    ow_rows = [(list(k), v) for k, v in ow.most_common(TOP_N)]
    xmax = max(v for _p, v in rt_rows) * 1.16

    fig, axes = plt.subplots(1, 2, figsize=(14.4, 6.2), sharex=True)
    fig.subplots_adjust(top=0.66, bottom=0.14, left=0.215, right=0.985,
                        wspace=0.58)

    draw_panel(axes[0], rt_rows, ROUND_TRIP, xmax,
               f"Round trips — out and back\n{len(rt):,} distinct routes, "
               f"{sum(rt.values()):,} segments")
    draw_panel(axes[1], ow_rows, ONE_WAY, xmax,
               f"One-way — three different organisations\n{len(ow):,} distinct "
               f"routes, {sum(ow.values()):,} segments")

    headline(
        fig,
        "The typical bureaucratic career is a round trip, not a ladder",
        "Every three-step sequence of organisations in the record, with "
        "consecutive posts in the same organisation collapsed so that what is "
        f"counted is the crossing. {returns / total * 100:.0f}% of them return "
        "to the organisation they started from. Drawn from where the middle "
        "organisation usually leads, ignoring where the person came from, the "
        f"rate would be {expected / total * 100:.0f}% — so a career comes back "
        f"{returns / expected:.1f} times more often than the transition matrix "
        "alone predicts, and the origin is still doing work two moves later. "
        "Both panels share an x axis: round trips are few routes travelled "
        "often, one-way paths are many routes travelled once.",
        width=146,
    )
    save(fig, "fig30_career_trajectories",
         SOURCE + "  A trajectory is the sequence of organisations a person "
                  "holds posts in, ordered by start date, a person holding "
                  "several posts on one date placed at the highest, and "
                  "consecutive posts in the same organisation collapsed to one "
                  "— an official re-appointed twice inside the finance ministry "
                  "has not crossed anything. Organisations are named as in the "
                  "ministry-flow figure. Posts the record will not place are "
                  "dropped from the sequence before it is collapsed, so a "
                  "return through an unplaceable body still reads as a return; "
                  "keeping them instead gives "
                  f"{all_returns / all_total * 100:.0f}% returning against "
                  f"{all_expected / all_total * 100:.0f}% expected, so the "
                  "result does not rest on that choice. The segments are not "
                  "independent: one long career contributes several, and a "
                  "person who shuttles between two ministries contributes the "
                  "same round trip more than once. Read the panels as a "
                  "description of the routes available, not as a test.")


def main() -> None:
    print("loading tables…")
    spells = pd.read_csv(PROC / "spells.csv.gz", low_memory=False)
    spells["start"] = pd.to_datetime(spells.start_date, errors="coerce")
    spells = spells.dropna(subset=["start"])
    spells["org_name"] = spells.org_name.fillna("")
    spells["org_form"] = spells.org_form.fillna("")
    print("drawing…")
    fig_trajectories(spells)
    print("done")


if __name__ == "__main__":
    main()
