"""Two posts back, one post back, and into the centre.

The companion to the one-step figure, which compared the last post before an
arrival at the prime minister's office or the presidency. This adds the post
before that, so the unit is a three-step approach: 1,275 of them, 913 to the
prime minister's office and 362 to the presidency.

**The middle column is real, not decorative.** A three-column alluvial usually
draws its two stages independently: the left-to-middle ribbons are one
crosstab, the middle-to-right ribbons another, and a reader who traces a band
through the middle is following something that does not exist, because nothing
ties the two halves together. Here every path keeps one band through the middle
node — the strip a career enters on is the strip it leaves on — and every
ribbon is coloured by the office it finishes at. Tracing is therefore safe: a
red thread entering `Foreign affairs` from `Social ministries` really is the
people who went on to the presidency.

**The cost of three steps.** Named routes will not carry a ranking at this
depth — the commonest path into the presidency through two named predecessors
is walked by nine people — so the organisations are grouped into nine blocs.
The two offices are not pooled into one of them: doing that made the middle
column report a handover between them as though an office were staffing
itself.

Even then the diagram has a tail: 43 of its 125 left-hand ribbons are fewer
than five people, and together they carry 8% of the flow. Read the columns and
the thick bands; the hairlines are there so the totals are honest, not to be
read individually.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from figures_sankey import ribbon  # noqa: E402
from figures_trajectories import trajectories  # noqa: E402
from figstyle import (  # noqa: E402
    CAT4, INK, MUTED, PAPER, PROC, SOURCE, headline, plt, save,
)
from matplotlib.patches import Patch  # noqa: E402

PM = "Prime Minister's Office"
PRESIDENCY = "Presidency of the Republic"
OFFICES = [PM, PRESIDENCY]

# Same two colours as the one-step figure, and for the same two things, so the
# pair of figures reads as one. Validated under `--pairs all`: worst ΔE 23.6
# protan, 27.9 normal.
OFFICE_COLOUR = {PM: CAT4[1], PRESIDENCY: CAT4[0]}

PM_BLOC = "PM's office"
PR_BLOC = "Presidency"
UNPLACED = "Other / unplaced"

# Nine blocs. Twenty-eight organisations at three steps gives a diagram whose
# every cell is one or two people, so the rest are grouped as in the outflow
# figures — but the two offices are kept apart in every column.
#
# Folding them into one "centre" bloc, as an earlier draft did, hid the thing
# worth seeing. Pooled, the middle column showed 74 careers passing through
# "the centre" on their way to the centre, which reads as an office staffing
# itself. Split, that 74 is 42 from the prime minister's office to the
# presidency and 32 the other way, and *none* of it same-office: consecutive
# posts in one organisation are collapsed, so arriving at an office from
# itself is not a thing the data can contain. The pooled bloc was reporting a
# handover between the two offices as if it were self-recruitment.
BLOC = {PM_BLOC: [PM], PR_BLOC: [PRESIDENCY],
        "Security and territory": ["Interior ministry", "Governorates",
                                   "Municipalities", "Defence"],
        "Economic and public enterprise": ["Finance", "Economy",
                                           "State Property", "Planning",
                                           "Public enterprise", "Investment"],
        "Social ministries": ["Education", "Higher Education", "Health",
                              "Social Affairs", "Culture", "Youth and Sport",
                              "Universities and hospitals", "Employment",
                              "Women and Family", "Religious Affairs"],
        "Infrastructure and production": ["Agriculture", "Public Works",
                                          "Transport", "Industry", "Energy",
                                          "Trade", "Environment", "Tourism",
                                          "Development", "Communications",
                                          "Technologies"],
        "Foreign affairs": ["Foreign Affairs", "International Cooperation"],
        "Justice and oversight": ["Justice", "Courts", "Parliament",
                                  "Independent authorities", "Human Rights",
                                  "Relations with Parliament"]}
OF_ORG = {org: bloc for bloc, orgs in BLOC.items() for org in orgs}

ORDER = [PM_BLOC, PR_BLOC, "Security and territory", "Foreign affairs",
         "Economic and public enterprise", "Infrastructure and production",
         "Social ministries", "Justice and oversight", UNPLACED]


def bloc(org: str) -> str:
    return OF_ORG.get(org, UNPLACED)


def approaches(seqs) -> Counter:
    """(two posts back, one post back, office) for every three-step arrival."""
    out = Counter()
    for q in seqs:
        for i in range(2, len(q)):
            if q[i] in OFFICES:
                out[(bloc(q[i - 2]), bloc(q[i - 1]), q[i])] += 1
    return out


def draw(ax, trip: Counter, fontsize: float = 7.6) -> None:
    total = float(sum(trip.values()))
    gap = 0.030
    cols = [0.0, 0.5, 1.0]
    node_w = 0.019
    usable = 1.0 - gap * (len(ORDER) - 1)

    left_tot = Counter()
    mid_tot = Counter()
    right_tot = Counter()
    for (a, m, d), v in trip.items():
        left_tot[a] += v
        mid_tot[m] += v
        right_tot[d] += v

    def stack(names, totals, span_gap):
        tops, y = {}, 1.0
        for n in names:
            h = usable * (totals.get(n, 0) / total)
            tops[n] = (y, y - h)
            y -= h + span_gap
        return tops

    left = stack(ORDER, left_tot, gap)
    mid = stack(ORDER, mid_tot, gap)
    # Two nodes on the right, so they get a larger gap and their own usable
    # span; otherwise the pair sits as a thin pillar against eight-node columns.
    r_usable = 1.0 - 0.06
    r_tops, y = {}, 1.0
    for d in OFFICES:
        h = r_usable * (right_tot[d] / total)
        r_tops[d] = (y, y - h)
        y -= h + 0.06

    # Each path keeps one band through the middle node: the strip it enters on
    # is the strip it leaves on. Ordering the triples the same way on both
    # sides of that node is what makes the band continuous, and grouping by
    # destination first keeps each colour contiguous rather than interleaved.
    def key(t):
        return (OFFICES.index(t[2]), ORDER.index(t[0]), ORDER.index(t[1]))

    lcur = {n: left[n][0] for n in ORDER}
    mcur_in = {n: mid[n][0] for n in ORDER}
    mcur_out = {n: mid[n][0] for n in ORDER}
    rcur = {d: r_tops[d][0] for d in OFFICES}

    for (a, m, d) in sorted(trip, key=key):
        v = trip[(a, m, d)]
        h = usable * (v / total)
        colour = OFFICE_COLOUR[d]
        y0a, y0b = lcur[a], lcur[a] - h
        y1a, y1b = mcur_in[m], mcur_in[m] - h
        lcur[a] -= h
        mcur_in[m] -= h
        ribbon(ax, cols[0] + node_w, cols[1] - node_w, y0a, y0b, y1a, y1b,
               colour, alpha=0.5)

        hr = r_usable * (v / total)
        y2a, y2b = mcur_out[m], mcur_out[m] - h
        y3a, y3b = rcur[d], rcur[d] - hr
        mcur_out[m] -= h
        rcur[d] -= hr
        ribbon(ax, cols[1] + node_w, cols[2] - node_w, y2a, y2b, y3a, y3b,
               colour, alpha=0.5)

    for x, tops, totals, ha in ((cols[0], left, left_tot, "right"),
                                (cols[1], mid, mid_tot, "center")):
        for n in ORDER:
            ytop, ybot = tops[n]
            if ytop == ybot:
                continue
            ax.add_patch(plt.Rectangle((x - node_w / 2, ybot), node_w,
                                       ytop - ybot, facecolor=INK,
                                       edgecolor="none", zorder=4))
            if ha == "right":
                ax.annotate(f"{n}   {totals[n]}", xy=(x - node_w, (ytop + ybot) / 2),
                            ha="right", va="center", fontsize=fontsize,
                            color=INK, zorder=5)
            else:
                # The middle column's labels sit over the ribbons, so they get
                # a paper-coloured plate behind them; without it the thin type
                # disappears into the bands it is naming.
                ax.annotate(f"{n}   {totals[n]}", xy=(x, ytop + 0.010),
                            ha="center", va="bottom", fontsize=fontsize,
                            color=INK, zorder=6,
                            bbox=dict(boxstyle="round,pad=0.22", facecolor=PAPER,
                                      edgecolor="none", alpha=0.92))

    for d in OFFICES:
        ytop, ybot = r_tops[d]
        ax.add_patch(plt.Rectangle((cols[2] - node_w / 2, ybot), node_w,
                                   ytop - ybot, facecolor=OFFICE_COLOUR[d],
                                   edgecolor="none", zorder=4))
        ax.annotate(f"{d}\n{right_tot[d]} arrivals",
                    xy=(cols[2] + node_w, (ytop + ybot) / 2), ha="left",
                    va="center", fontsize=fontsize + 0.6, color=INK,
                    linespacing=1.5, zorder=5)

    ax.set_xlim(-0.40, 1.30)
    ax.set_ylim(-0.03, 1.09)
    ax.axis("off")
    for x, lab in ((cols[0], "two posts before"), (cols[1], "the post before"),
                   (cols[2], "the arrival")):
        ax.annotate(lab, xy=(x, 1.075), ha="center", va="bottom",
                    fontsize=8.4, color=MUTED, fontweight="bold")


def fig_centre_paths(spells: pd.DataFrame) -> None:
    trip = approaches(trajectories(spells))
    n = sum(trip.values())
    thin = sum(v for v in trip.values() if v < 5)

    by_office = Counter()
    for (_a, _m, d), v in trip.items():
        by_office[d] += v
    # Where the two offices' approaches differ one step further back than the
    # one-step figure could see.
    fa_pr = sum(v for (a, m, d), v in trip.items()
                if d == PRESIDENCY and "Foreign affairs" in (a, m))
    fa_pm = sum(v for (a, m, d), v in trip.items()
                if d == PM and "Foreign affairs" in (a, m))

    # The handover between the two offices, which the pooled bloc concealed.
    hand = {(m, d): sum(v for (_a, mm, dd), v in trip.items()
                        if mm == m and dd == d)
            for m in (PM_BLOC, PR_BLOC) for d in OFFICES}
    back = {(a, d): sum(v for (aa, _m, dd), v in trip.items()
                        if aa == a and dd == d)
            for a in (PM_BLOC, PR_BLOC) for d in OFFICES}
    first_col = Counter()
    for (a, _m, _d), v in trip.items():
        first_col[a] += v
    biggest, biggest_n = first_col.most_common(1)[0]

    fig, ax = plt.subplots(figsize=(13.8, 8.4))
    fig.subplots_adjust(top=0.71, bottom=0.10, left=0.215, right=0.80)
    draw(ax, trip)
    ax.legend(handles=[Patch(facecolor=OFFICE_COLOUR[d], alpha=0.62,
                             label=f"arrives at the {d.lower()}")
                       for d in OFFICES],
              loc="upper center", bbox_to_anchor=(0.5, -0.015), ncol=2,
              title="every ribbon is coloured by where the career ends")

    headline(
        fig,
        "The last two posts before the centre",
        f"All {n:,} three-step approaches to the two offices: the bloc a career "
        "was in two posts before arriving, the bloc it was in immediately "
        "before, and which office it reached. Each path holds one band through "
        "the middle column, so a ribbon can be followed across the whole "
        "diagram rather than only within a stage. Foreign affairs appears "
        f"somewhere in the last two posts of {fa_pr / by_office[PRESIDENCY] * 100:.0f}% "
        "of approaches to the presidency against "
        f"{fa_pm / by_office[PM] * 100:.0f}% of those to the prime minister's "
        "office, so the tilt the one-step figure found survives a step further "
        "back. The two offices are kept apart in every column, which shows what "
        "pooling them hid: where one is the post immediately before an arrival "
        "at the other, every one of those careers is a handover between them — "
        f"{hand[(PM_BLOC, PRESIDENCY)]} from the prime minister's office to the "
        f"presidency and {hand[(PR_BLOC, PM)]} the other way — while two posts "
        f"back the centre is mostly returning to itself, {back[(PM_BLOC, PM)]} "
        "careers leaving the prime minister's office and coming back to it.",
        width=142,
    )
    save(fig, "fig32_centre_three_step",
         SOURCE + "  An approach is a post in one of the two offices with two "
                  "earlier posts in the same career, consecutive posts in one "
                  "organisation collapsed so that what is counted is the "
                  f"crossing. Organisations are grouped into {len(ORDER)} blocs "
                  "because "
                  "at three steps the named routes are single figures — the "
                  "commonest path into the presidency through two named "
                  "predecessors is walked by nine people. The two offices are "
                  "their own blocs in every column. An earlier draft pooled "
                  "them, which made the middle column report a handover from "
                  "one office to the other as though an office were staffing "
                  "itself; no career can arrive at an office from that same "
                  "office here, because consecutive posts in one organisation "
                  "are collapsed before the sequence is read. With the centre "
                  f"split, the largest single bloc two posts before an arrival "
                  f"is {biggest.lower()} at {biggest_n}, not the centre. "
                  "The diagram has a tail: "
                  f"{sum(1 for v in trip.values() if v < 5)} of its "
                  f"{len(trip)} left-hand ribbons carry fewer than five people "
                  f"and between them {thin / n * 100:.0f}% of the flow. They are "
                  "drawn so the column totals are honest, not to be read one by "
                  "one. Three-step approaches are a subset of the arrivals in "
                  "the one-step figure — 1,275 of 2,078 — because a career must "
                  "have two earlier posts in the record to appear here at all, "
                  "and which careers do is itself uneven across the period.")


def main() -> None:
    print("loading tables…")
    spells = pd.read_csv(PROC / "spells.csv.gz", low_memory=False)
    spells["start"] = pd.to_datetime(spells.start_date, errors="coerce")
    spells = spells.dropna(subset=["start"])
    spells["org_name"] = spells.org_name.fillna("")
    spells["org_form"] = spells.org_form.fillna("")
    print("drawing…")
    fig_centre_paths(spells)
    print("done")


if __name__ == "__main__":
    main()
