"""Where governors come from, and whether the answer changed with the regime.

The other flow figures in this set ask where people go. This asks where one
office is filled from: the governorate, the senior field post of the Tunisian
state and the one an incoming regime can change without changing a law.

Three things had to be settled before it could be drawn.

**Which "governor".** In French the head of the central bank is also a
*gouverneur*, and the position appears in the record under the same rank. All
twelve of those spells carry a bare "Gouverneur" against the Banque Centrale and
nothing else does, so they are excluded by their organisation.

**Where the post says it sits.** A governor's organisation is recorded
sometimes as the governorate and sometimes as the interior ministry, and for a
handful of decrees as whatever ministry headed the page — one run of territorial
governors is filed under foreign affairs. The position itself is reliable where
the organisation is not, so the office is identified by rank and the
organisation is used only to exclude the bank.

**The 36% with no earlier post.** A governor with no previous gazetted post is
not a governor who came from nowhere: the gazette records appointments, so a
first appearance is a first *gazetted* post and may follow a career in the
party, the army or outside the state entirely. That group is drawn as its own
source rather than dropped, because dropping it would silently turn a figure
about recruitment into a figure about the two-thirds of it that is legible.

The right-hand column is the regime in force at the appointment, which is what
makes this a flow diagram rather than a bar chart: the question is not only
where governors come from but whether each regime drew on a different pool.
Each era carries appointments per year as well as a count, because the four
windows run from five years to twenty-seven and the counts are not comparable.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from figures_sankey import _label_positions, ribbon  # noqa: E402
from apparatus import ministry_destination, wilson  # noqa: E402
from figstyle import (  # noqa: E402
    CAT4, INK, MUTED, PROC, SOURCE, headline, plt, save,
)
from matplotlib.patches import Patch  # noqa: E402

RECORD_ENDS = pd.Timestamp("2026-05-31")

# The office, not the rank word. The central bank's governor holds the same rank
# in this table; every one of those spells names the Banque Centrale and no
# territorial governor's does.
CENTRAL_BANK = "banque centrale"

ERAS = [
    ("Bourguiba", pd.Timestamp("1956-03-20"), pd.Timestamp("1987-11-07")),
    ("Ben Ali", pd.Timestamp("1987-11-07"), pd.Timestamp("2011-01-14")),
    ("After the revolution", pd.Timestamp("2011-01-14"), pd.Timestamp("2021-07-25")),
    ("Saïed", pd.Timestamp("2021-07-25"), RECORD_ENDS),
]
ERA_NAMES = [e[0] for e in ERAS]

NO_PRIOR = "No earlier gazetted post"
ALREADY = "Already a governor"
INSIDE = {ALREADY, "Governorates", "Interior ministry"}
OTHER_MINISTRIES = "Other ministries"
OTHER_BODIES = "Other public bodies"
KEEP = {"Public enterprise", "Agriculture", "Not identifiable"}

SOURCES = [NO_PRIOR, ALREADY, "Governorates", "Interior ministry",
           "Public enterprise", "Agriculture", OTHER_MINISTRIES,
           OTHER_BODIES, "Not identifiable"]

# Two validated hues and a neutral. Colour carries the one thing the node
# labels cannot: whether the appointment came from inside the apparatus the
# governor belongs to or from the rest of the state. The absence of a record is
# not a third kind of origin, so it takes grey rather than a hue. The pair
# passes every check under `--pairs all`, worst ΔE 23.6 protan, 27.9 normal.
FROM_INSIDE = CAT4[1]
FROM_ELSEWHERE = CAT4[0]
FROM_UNKNOWN = "#B9B5A8"


def source_colour(src: str) -> str:
    if src == NO_PRIOR:
        return FROM_UNKNOWN
    if src in INSIDE:
        return FROM_INSIDE
    return FROM_ELSEWHERE


def collapse(dest: str) -> str:
    if dest in KEEP or dest in INSIDE:
        return dest
    if dest in ("Municipalities", "Universities and hospitals", "Courts",
                "Independent authorities"):
        return OTHER_BODIES
    return OTHER_MINISTRIES


def era_of(d: pd.Timestamp) -> str | None:
    for name, lo, hi in ERAS:
        if lo <= d < hi:
            return name
    return None


def appointments(spells: pd.DataFrame) -> pd.DataFrame:
    """Every appointment to a governorship, with the post held before it."""
    s = spells.sort_values(["person_id", "start", "rank_score"])
    s = s.loc[s.groupby(["person_id", "start"]).rank_score.idxmax()]
    s = s.sort_values(["person_id", "start"])
    prev = s.groupby("person_id").shift(1)

    a = s[s.is_governor].copy()
    has_prev = prev.loc[a.index, "start"].notna().values
    was_gov = prev.loc[a.index, "is_governor"].fillna(False).values
    src = []
    for ok, gov, port, org, form in zip(
            has_prev, was_gov,
            prev.loc[a.index, "org_portfolio"].values,
            prev.loc[a.index, "org_name"].fillna("").values,
            prev.loc[a.index, "org_form"].fillna("").values):
        if not ok:
            src.append(NO_PRIOR)
        elif gov:
            src.append(ALREADY)
        else:
            src.append(collapse(ministry_destination(port, org, form)))
    a["source"] = src
    a["era"] = [era_of(d) for d in a.start]
    return a.dropna(subset=["era"])


def draw(ax, mat: pd.DataFrame, rates: dict, fontsize: float = 7.8) -> None:
    total = float(mat.values.sum())
    gap_l, gap_r = 0.022, 0.055
    usable_l = 1.0 - gap_l * (len(mat.index) - 1)
    usable_r = 1.0 - gap_r * (len(mat.columns) - 1)
    x0, x1, node_w = 0.0, 1.0, 0.022

    ax.set_xlim(-0.52, 1.46)
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
    for i, src in enumerate(mat.index):
        colour = source_colour(src)
        for jx in range(len(mat.columns)):
            v = mat.iat[i, jx]
            if not v:
                continue
            h = usable_r * (v / total)
            y0a, y0b = lcur[i], lcur[i] - h
            y1a, y1b = rcur[jx], rcur[jx] - h
            lcur[i] -= h
            rcur[jx] -= h
            ribbon(ax, x0 + node_w, x1 - node_w, y0a, y0b, y1a, y1b, colour,
                   alpha=0.6)

    texts = [f"{n}   {int(t):,}" for n, t in zip(mat.index, lt)]
    ys = _label_positions(ax, left, texts, fontsize)
    for k, ((ytop, ybot), t, y) in enumerate(zip(left, lt, ys)):
        ax.add_patch(plt.Rectangle((x0, ybot), node_w, ytop - ybot,
                                   facecolor=source_colour(mat.index[k]),
                                   edgecolor="none", zorder=4))
        if t:
            ax.annotate(texts[k], xy=(x0 - node_w * 1.8, y), ha="right",
                        va="center", fontsize=fontsize, color=INK, zorder=5)

    for (ytop, ybot), t, name in zip(right, rt, mat.columns):
        ax.add_patch(plt.Rectangle((x1 - node_w, ybot), node_w, ytop - ybot,
                                   facecolor=INK, edgecolor="none", zorder=4))
        ax.annotate(f"{name}\n{int(t):,} appointments\n{rates[name]:.1f} a year",
                    xy=(x1 + node_w * 1.8, (ytop + ybot) / 2), ha="left",
                    va="center", fontsize=fontsize, color=INK, linespacing=1.5,
                    zorder=5)


def fig_governor_inflow(spells: pd.DataFrame) -> None:
    a = appointments(spells)
    mat = (pd.crosstab(a.source, a.era)
           .reindex(index=SOURCES, columns=ERA_NAMES).fillna(0).astype(int))

    years = {n: (min(hi, RECORD_ENDS) - lo).days / 365.25 for n, lo, hi in ERAS}
    counts = mat.sum(axis=0)
    rates = {n: counts[n] / years[n] for n in ERA_NAMES}

    inside = int(mat.loc[[s for s in SOURCES if s in INSIDE]].values.sum())
    known = int(mat.drop(index=NO_PRIOR).values.sum())
    no_prior = int(mat.loc[NO_PRIOR].sum())

    # The share recruited from inside, era by era, on the appointments whose
    # predecessor is in the record. Computed rather than asserted: the first
    # draft of this figure was titled on a reading of the pooled number and the
    # era-by-era series says something sharper and different.
    ins_by_era = {}
    for name in ERA_NAMES:
        col = mat[name].drop(index=NO_PRIOR)
        k = int(col.sum())
        i = int(col.loc[[s for s in col.index if s in INSIDE]].sum())
        ins_by_era[name] = (i, k, wilson(i, k) if k else (0.0, 0.0))

    fig, ax = plt.subplots(figsize=(12.6, 7.6))
    fig.subplots_adjust(top=0.71, bottom=0.11, left=0.24, right=0.80)
    draw(ax, mat, rates)
    ax.legend(handles=[
        Patch(facecolor=FROM_INSIDE, alpha=0.65,
              label="from inside the interior apparatus"),
        Patch(facecolor=FROM_ELSEWHERE, alpha=0.65,
              label="from elsewhere in the state"),
        Patch(facecolor=FROM_UNKNOWN, alpha=0.65,
              label="no earlier gazetted post"),
    ], loc="upper center", bbox_to_anchor=(0.5, -0.01), ncol=3)

    fastest = max(rates, key=rates.get)
    big = [n for n in ERA_NAMES if ins_by_era[n][1] >= 30]
    trend = " to ".join(f"{ins_by_era[n][0] / ins_by_era[n][1] * 100:.0f}%"
                        for n in big)
    headline(
        fig,
        "The governorship has stopped being a promotion from within",
        "Every appointment to a governorship in the record, by the post the "
        "person held immediately before it and the regime in force at the time. "
        f"Of the {known} appointments whose predecessor is in the record, "
        f"{inside} come from inside the interior apparatus — a governorate, the "
        "ministry, or another governorship — and the share falls era by era, "
        f"{trend}; the first and last of those do not overlap at 95%. The "
        f"remaining {no_prior} appointments have no earlier gazetted post at "
        "all. What also moves is the pace: "
        f"{fastest} replaces governors at {rates[fastest]:.1f} a year against "
        + ", ".join(f"{rates[n]:.1f}" for n in ERA_NAMES if n != fastest)
        + " for the others.",
        width=132,
    )
    save(fig, "fig29_governor_inflow",
         SOURCE + "  The office is identified by rank, not by organisation. A "
                  "governor's organisation is recorded sometimes as the "
                  "governorate and sometimes as the interior ministry, and for "
                  "a few decrees as whatever ministry headed the page — one run "
                  "of territorial governors is filed under foreign affairs. The "
                  "organisation is used for one thing only: the head of the "
                  "central bank is also a gouverneur and carries the same rank, "
                  "and all twelve of those spells name the Banque Centrale "
                  "where no territorial governor's does. A governor with no "
                  "earlier gazetted post is not one who came from nowhere: the "
                  "gazette records appointments, so a first appearance is a "
                  "first gazetted post and may follow a career in the party, "
                  "the army, or outside the state. That group is shown rather "
                  "than dropped. Era windows run from five years to twenty-"
                  "seven, so each carries a rate as well as a count; the last "
                  "is open at the end of the record and its rate is the least "
                  "settled. Two limits on the fall in the subtitle. The Saïed "
                  "era contributes ten appointments with a known predecessor "
                  "and an interval of 6 to 51 points, so it is drawn but is no "
                  "part of the claim. And the share with no earlier gazetted "
                  "post is itself uneven across eras — 47%, 28%, 33%, 47% — so "
                  "if an official already inside the administration is likelier "
                  "to have a gazetted predecessor, a thinner early record would "
                  "inflate the early inside share. Part of the fall may be the "
                  "record improving rather than the practice changing.")


def main() -> None:
    print("loading tables…")
    spells = pd.read_csv(PROC / "spells.csv.gz", low_memory=False)
    spells["start"] = pd.to_datetime(spells.start_date, errors="coerce")
    spells = spells.dropna(subset=["start"])
    spells["org_name"] = spells.org_name.fillna("")
    spells["org_form"] = spells.org_form.fillna("")
    spells["is_governor"] = (
        (spells.position_rank == "gouverneur")
        & ~spells.org_name.str.lower().str.contains(CENTRAL_BANK)
    )
    print("drawing…")
    fig_governor_inflow(spells)
    print("done")


if __name__ == "__main__":
    main()
