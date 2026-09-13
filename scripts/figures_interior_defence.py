"""Movement between the interior and defence ministries, over the whole record.

This figure exists to show an absence, and the absence is the finding: across
sixty-nine years of the gazette the two ministries exchange thirty-two people.

It is deliberately not drawn per rupture, the way every other flow diagram in
this set is. The five-year windows around the three ruptures contain nought and
nought, one and one, two and three crossings. Six panels drawn on that would put
a ribbon of one person beside a ribbon of four hundred and invite a reader to
compare them.

So the unit is the whole record and both ministries appear on one scale. That
costs the internal detail of the defence column, which is a sixth the size of
the interior's — but the relative size of the two is part of what is being
shown, and a diagram that scaled each to its own total would hide it.

The crossings are drawn in colour and every other flow in neutral grey. This is
emphasis and not identity: there is no categorical palette here to validate,
because the only distinction the colour makes is between the flow the figure is
about and all the others.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from figures_sankey import RUPTURES, RECORD_ENDS, _label_positions, ribbon  # noqa: E402
from apparatus import consecutive_moves, security_branch  # noqa: E402
from figstyle import CAT4, INK, MUTED, PROC, SOURCE, headline, plt, save  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

INTERIOR = "Interior ministry"
DEFENCE = "Defence and\nmilitary justice"
GOVERNORATES = "Governorates"
OUTSIDE = "Outside the\nsecurity apparatus"

ORIGINS = [INTERIOR, DEFENCE]
TARGETS = [INTERIOR, DEFENCE, GOVERNORATES, OUTSIDE]

BRANCH_LABEL = {"interior": INTERIOR, "defence": DEFENCE,
                "territorial": GOVERNORATES}

CROSSING = CAT4[0]
NEUTRAL = "#B9B5A8"


def moves(spells: pd.DataFrame) -> pd.DataFrame:
    """Every consecutive post-to-post move whose origin is interior or defence.

    One post per person-date: where several are gazetted the same day, the
    senior one stands for the move. The whole record, with no window.
    """
    m = consecutive_moves(spells)
    m = m[m.branch.isin(("interior", "defence"))].copy()
    m["origin"] = m.branch.map(BRANCH_LABEL)
    m["target"] = [BRANCH_LABEL.get(b, OUTSIDE) for b in m.to_branch]
    return m


def draw(ax, mat: pd.DataFrame, fontsize: float = 8.2) -> None:
    total = float(mat.values.sum())
    gap_l, gap_r = 0.07, 0.035
    usable_l = 1.0 - gap_l * (len(mat.index) - 1)
    usable_r = 1.0 - gap_r * (len(mat.columns) - 1)
    x0, x1, node_w = 0.0, 1.0, 0.022

    ax.set_xlim(-0.34, 1.46)
    ax.set_ylim(-0.04, 1.04)
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
        for jx, target in enumerate(mat.columns):
            v = mat.iat[i, jx]
            if not v:
                continue
            h = usable_r * (v / total)
            y0a, y0b = lcur[i], lcur[i] - h
            y1a, y1b = rcur[jx], rcur[jx] - h
            lcur[i] -= h
            rcur[jx] -= h
            crossing = {origin, target} == {INTERIOR, DEFENCE}
            ribbon(ax, x0 + node_w, x1 - node_w, y0a, y0b, y1a, y1b,
                   CROSSING if crossing else NEUTRAL,
                   alpha=0.85 if crossing else 0.5)
            if crossing:
                # Sixteen people against a column of 2,693 is a hairline, so
                # the ribbon is labelled where it lands rather than left to be
                # measured off the node.
                ax.annotate(f"{int(v)}", xy=(0.5, (y0a + y0b + y1a + y1b) / 4),
                            ha="center", va="center", fontsize=7.4,
                            color=CROSSING, fontweight="bold", zorder=6)

    for (ytop, ybot), t, name in zip(left, lt, mat.index):
        ax.add_patch(plt.Rectangle((x0, ybot), node_w, ytop - ybot,
                                   facecolor=INK, edgecolor="none", zorder=4))
        ax.annotate(f"{name}\n{int(t):,} moves",
                    xy=(x0 - node_w * 1.8, (ytop + ybot) / 2), ha="right",
                    va="center", fontsize=fontsize, color=INK,
                    linespacing=1.4, zorder=5)

    texts = [f"{c}   {int(t):,}" for c, t in zip(mat.columns, rt)]
    ys = _label_positions(ax, right, texts, fontsize)
    for k, ((ytop, ybot), t, y) in enumerate(zip(right, rt, ys)):
        ax.add_patch(plt.Rectangle((x1 - node_w, ybot), node_w, ytop - ybot,
                                   facecolor=INK, edgecolor="none", zorder=4))
        if t:
            ax.annotate(texts[k], xy=(x1 + node_w * 1.8, y), ha="left",
                        va="center", fontsize=fontsize, color=INK,
                        linespacing=1.4, zorder=5)


def fig_interior_defence(spells: pd.DataFrame) -> None:
    m = moves(spells)
    mat = (pd.crosstab(m.origin, m.target)
           .reindex(index=ORIGINS, columns=TARGETS).fillna(0).astype(int))

    i2d = int(mat.loc[INTERIOR, DEFENCE])
    d2i = int(mat.loc[DEFENCE, INTERIOR])
    n_int = int(mat.loc[INTERIOR].sum())
    n_def = int(mat.loc[DEFENCE].sum())

    cross = m[((m.origin == INTERIOR) & (m.target == DEFENCE))
              | ((m.origin == DEFENCE) & (m.target == INTERIOR))]
    people = cross.person_id.nunique()
    both = int((cross.groupby("person_id").origin.nunique() > 1).sum())

    fig, ax = plt.subplots(figsize=(11.6, 6.4))
    fig.subplots_adjust(top=0.70, bottom=0.10, left=0.16, right=0.90)
    draw(ax, mat)
    ax.legend(handles=[
        Patch(facecolor=CROSSING, alpha=0.85,
              label="between the two ministries"),
        Patch(facecolor=NEUTRAL, alpha=0.5, label="every other move"),
    ], loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=2)

    headline(
        fig,
        "The interior and defence ministries barely exchange anyone",
        "Every consecutive move made by someone holding a post in one of the "
        "two ministries, across the whole record, 1957–2026. Of "
        f"{n_int:,} moves out of an interior post, {i2d} go to defence; of "
        f"{n_def:,} out of a defence post, {d2i} go to the interior. That is "
        f"{i2d / n_int * 100:.1f}% and {d2i / n_def * 100:.1f}% — {people} "
        f"people in sixty-nine years, {both} of whom crossed in both "
        "directions. Both ministries recruit their next officeholder from "
        "themselves or from outside the security apparatus altogether, and "
        "almost never from each other.",
        width=124,
    )
    save(fig, "fig27_interior_defence_exchange",
         SOURCE + "  Both ministries are drawn on one scale, so the defence "
                  "column's height is its share of the two ministries' moves "
                  "and not a separate diagram: that relative size is part of "
                  "what is shown. This is the one flow figure in the set not "
                  "drawn per rupture, because the five-year windows around the "
                  "three ruptures contain 0 and 0 crossings for 1987, 1 and 1 "
                  "for 2011, and 2 and 3 for 2021 — six panels on that would "
                  "set a ribbon of one person beside a ribbon of hundreds and "
                  "invite the comparison. Colour marks the flow the figure is "
                  "about against all others; it carries no category. A move is "
                  "one post to the next by start date, a person holding "
                  "several posts placed at the highest, so a spell that ends "
                  "with no further gazetted post does not appear — the gazette "
                  "records appointments far better than departures. Defence "
                  "here is the ministry, the military tribunals and the army by "
                  "name, plus any body whose portfolio names defence, which is "
                  "the test the security-branch figure already uses. Widening "
                  "it to every body with \u2018militaire\u2019 in its name — the "
                  "military hospitals, the housing office, the research centre — "
                  "adds 62 spells and takes defence-to-interior from 16 to 20, "
                  "leaving interior-to-defence at 16. The narrow test is kept "
                  "because much of what widening adds is board seats held by "
                  "other ministries\u2019 representatives, where the officeholder "
                  "is a domains or finance official rather than a defence one. "
                  "The conclusion is the same either way.")


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
    fig_interior_defence(spells)
    print("done")


if __name__ == "__main__":
    main()
