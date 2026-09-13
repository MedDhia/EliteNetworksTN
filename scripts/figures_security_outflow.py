"""Flow diagram of where the security apparatus sends the people it loses.

Deliberately the same form as the interior outflow diagram — same cohort rule,
same window, same seniority split, same colour assignment — so that the two can
be laid side by side and the difference read off them is a difference between
the two bodies rather than between two ways of drawing.

The bodies are not the same. The security apparatus takes in defence and
military justice and leaves out the municipalities, so a governor moving to a
town hall counts as leaving it while never leaving the interior ministry's
remit. That move is given its own destination rather than dropped into the
residual, because it is a legible career step and not an unclassifiable one.

It is also smaller: 169, 464 and 278 movers against the interior apparatus's
198, 711 and 678. Destinations are therefore collapsed further than in the
interior figure — seven rather than eight, with the two economic destinations
merged and the two sovereign ones merged — and even so the 1987 and 2021 senior
rows carry cells of one person. The note says so, and says to read those rows'
node totals rather than their ribbons.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from figures_sankey import (  # noqa: E402
    PLACEBO_LAGS, RECORD_ENDS, RUPTURES, _label_positions, ribbon,
)
from apparatus import (  # noqa: E402
    SECURITY_STAYS, in_security_apparatus, security_destination,
)
from figstyle import CAT4, INK, PROC, SOURCE, headline, plt, save  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

# Same assignment as the interior outflow figure: colour carries the tier a flow
# left from and nothing else. Keeping it identical is what lets the two figures
# be compared - a reader who has learned the encoding once does not relearn it.
TIERS = [(40, "Director and above", CAT4[1]),
         (0, "Head of service and below", CAT4[0])]

# The outflow here is 107, 260 and 147 people. Eight destinations would put
# several cells at one and two, so the two economic destinations are merged and
# the two sovereign ones are merged.
MERGE = {"finance and economy": "Economic ministries\nand public enterprise",
         "public enterprise": "Economic ministries\nand public enterprise",
         "the centre": "The centre and\nsovereign bodies",
         "sovereign and oversight": "The centre and\nsovereign bodies",
         "social ministries": "Social ministries",
         "infrastructure and production": "Infrastructure\nand production",
         "municipal government": "Municipal government",
         "not identifiable": "Not identifiable",
         SECURITY_STAYS: "Stays in the\nsecurity apparatus"}

# Fixed for every panel, so a destination does not move under the reader between
# one rupture and the next.
ORDER = ["Stays in the\nsecurity apparatus", "Social ministries",
         "Infrastructure\nand production", "Economic ministries\nand public enterprise",
         "Municipal government", "The centre and\nsovereign bodies",
         "Not identifiable"]


def movers(spells: pd.DataFrame, t0: pd.Timestamp, years: int = 5):
    """Security-apparatus people in post on the eve of t0 who take another post."""
    t1 = min(t0 + pd.DateOffset(years=years), RECORD_ENDS)
    inpost = spells[(spells.start < t0) & (spells.end.isna() | (spells.end > t0))]
    if inpost.empty:
        return None
    top = inpost.loc[inpost.groupby("person_id").rank_score.idxmax()]
    top = top[[in_security_apparatus(p, o, f) for p, o, f in
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
    j["tier"] = [next(lab for lo, lab, _ in TIERS if r >= lo) for r in j.rank_score]
    j["dest"] = [MERGE[security_destination(p, o, f)] for p, o, f in
                 zip(j.org_portfolio, j.org_name.fillna(""),
                     j.org_form.fillna(""))]
    return j


def matrix(j: pd.DataFrame) -> pd.DataFrame:
    # The placebo frame is several cohorts concatenated, so its row labels
    # repeat and crosstab carries that into an axis reindex cannot accept.
    j = j.reset_index(drop=True)
    return (pd.crosstab(j.tier, j.dest)
            .reindex(index=[lab for _, lab, _ in TIERS], columns=ORDER)
            .fillna(0).astype(int))


def draw(ax, m: pd.DataFrame, *, label_dests: bool, fontsize: float = 6.6) -> None:
    total = float(m.values.sum())
    if not total:
        ax.axis("off")
        return
    gap_l, gap_r = 0.06, 0.024
    usable_l = 1.0 - gap_l * (len(m.index) - 1)
    usable_r = 1.0 - gap_r * (len(m.columns) - 1)
    x0, x1, node_w = 0.0, 1.0, 0.026

    ax.set_xlim(-0.62 if label_dests else -0.34, 1.62)
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

    texts = [(f"{c}   {int(t):,}" if label_dests else f"{int(t):,}")
             for c, t in zip(m.columns, rt)]
    ys = _label_positions(ax, right, texts, fontsize)
    for k, ((ytop, ybot), t, y) in enumerate(zip(right, rt, ys)):
        ax.add_patch(plt.Rectangle((x1 - node_w, ybot), node_w, ytop - ybot,
                                   facecolor=INK, edgecolor="none", zorder=4))
        if not t:
            continue
        ax.annotate(texts[k], xy=(x1 + node_w * 1.4, y), ha="left", va="center",
                    fontsize=fontsize, color=INK, linespacing=1.3, zorder=5)


def fig_security_outflow(spells: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(15.2, 8.6))
    fig.subplots_adjust(top=0.71, bottom=0.09, left=0.055, right=0.895,
                        wspace=0.62, hspace=0.34)

    kept, kept_plc = [], []
    for col, (key, t0, datestr, gloss) in enumerate(RUPTURES):
        j = movers(spells, t0)
        plc = pd.concat([x for x in
                         (movers(spells, t0 - pd.DateOffset(years=k))
                          for k in PLACEBO_LAGS) if x is not None])
        for row, (jj, lbl) in enumerate(((j, f"after {key}"),
                                         (plc, "ordinary times"))):
            m = matrix(jj)
            draw(axes[row, col], m, label_dests=(col == 2))
            stay = m[ORDER[0]].sum() / m.values.sum() * 100
            axes[row, col].set_title(
                f"{lbl}   ·   {len(jj):,} movers   ·   {stay:.0f}% stay",
                color=INK, fontsize=8.4, loc="left", x=-0.10)
            (kept if row == 0 else kept_plc).append(stay)
        axes[0, col].annotate(f"{key}  ·  {datestr}\n{gloss}",
                              xy=(0.42, 1.32), xycoords="axes fraction",
                              ha="center", va="bottom", fontsize=9.6,
                              color=INK, fontweight="bold", linespacing=1.5)

    axes[1, 1].legend(handles=[Patch(facecolor=c, alpha=0.62, label=lab)
                               for _, lab, c in TIERS],
                      loc="upper center", bbox_to_anchor=(0.42, -0.07), ncol=2,
                      title="rank held in the security apparatus on the eve of "
                            "the rupture", title_fontsize=8)

    moves = [f"{k} {a - b:+.0f}" for (k, _t, _d, _g), a, b
             in zip(RUPTURES, kept, kept_plc)]
    headline(
        fig,
        "The ruptures pull the security apparatus in opposite directions",
        "Everyone holding a post in the interior ministry, the governorates or "
        "defence on the eve of a rupture who took a further post within five "
        "years, by where that post sat. Municipalities are outside this body, so "
        "a governor moving to a town hall counts as leaving it. Retention runs "
        + ", ".join(f"{k:.0f}%" for k in kept) +
        " against " + ", ".join(f"{k:.0f}%" for k in kept_plc) +
        " in each era's ordinary times: " + ", ".join(moves) +
        " points. 1987 and 2021 move it in opposite directions and both clear a "
        "95% interval; 2011 does not move it at all. That is unlike the interior "
        "apparatus, where all three ruptures raise retention, and unlike it "
        "again in the baseline — the interior's ordinary-times retention climbs "
        "across the three eras, 52% to 56% to 66%, where this falls back in the "
        "2020s.",
        width=150,
    )
    save(fig, "fig26_security_outflow_flow",
         SOURCE + "  Drawn to match the interior outflow figure so the two can "
                  "be compared: same cohort rule, same five-year window, same "
                  "seniority split, same colour assignment. The body differs — "
                  "it adds defence and military justice and drops the "
                  "municipalities. It is also smaller, 169, 464 and 278 movers "
                  "against the interior apparatus's 198, 711 and 678, so "
                  "destinations are collapsed to seven, with the two economic "
                  "and the two sovereign destinations merged. Even then the "
                  "senior rows of the 1987 and 2021 panels carry cells of one "
                  "person, where 2011's smallest cell is eight: read those two "
                  "rows' node totals, not their individual ribbons. Defence "
                  "supplies 10, 23 and 32 of the movers, so "
                  "nothing here should be read as a statement about the "
                  "military specifically.")


def main() -> None:
    print("loading tables…")
    spells = pd.read_csv(PROC / "spells.csv.gz", low_memory=False)
    spells["start"] = pd.to_datetime(spells.start_date, errors="coerce")
    spells["end"] = pd.to_datetime(spells.end_date, errors="coerce")
    spells = spells.dropna(subset=["start"])
    print("drawing…")
    fig_security_outflow(spells)
    print("done")


if __name__ == "__main__":
    main()
