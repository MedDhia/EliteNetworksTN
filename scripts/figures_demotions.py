"""Who was demoted in the security apparatus after 2011, and who was not.

A demotion here is a move to a lower-ranked post: the same person, the next
appointment the gazette records for them, at a lower point on the codebook's
ordinal scale. Leaving the record entirely is a different event and is not
counted, because a career that stops cannot be told apart from a career the
register stops following.

**The obvious story is wrong and the figure says so.** Taken whole, the
security apparatus was not demoted more than the rest of the state after the
revolution: 31.0% of its moves went downward in 2011–13 against 31.5% for
everyone else. The demotion rate rose across the state at once, which is what
a change of regime does to an administration, and reading the security figure
alone would credit the revolution with something general.

**The finding is in the branch split.** The territorial arm — governors,
regional commissariats, the security administration outside the capital — went
from 24.3% before the revolution to 44.6% after, and those two Wilson
intervals do not overlap. The central interior ministry did not move at all
(26.1% to 23.8%). What happened after 2011 happened to the provinces.

**It did not revert.** The territorial rate never returns to its pre-2011
level: by the three years before 2021 it stands at 51.7%. Whatever the
revolution changed about the security administration of the provinces, it
stayed changed, which is why the panel runs to the end of the record rather
than stopping at 2013.

**On the other ruptures.** 1987 moves the same way — 27.0% to 52.9% — but on
thirty-seven moves before the coup the intervals overlap and it cannot be
called. 2021 does not move at all. 2011 is the only rupture in the record
where the territorial jump is separable from chance, and the note says so
rather than leaving the reader to assume the other two were tested and failed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from apparatus import consecutive_moves, security_branch, wilson  # noqa: E402
from figstyle import (  # noqa: E402
    CAT4, INK, MUTED, PROC, RULE, RUPTURE_COLOUR, SOURCE, headline, plt, save,
)
from matplotlib.lines import Line2D  # noqa: E402

TERRITORIAL = CAT4[0]
CENTRAL = CAT4[1]

# Three-year windows. A single year of territorial moves runs to a median of
# 26 and dips under fifteen in the 1960s; every three-year window in the drawn
# span clears twenty-five, so each point rests on a real sample.
HALF = 1
MIN_WINDOW = 25
SPAN = (1968, 2024)

RUPTURES = {1987: "1987", 2011: "2011", 2021: "2021"}
PRE, POST = (2008, 2010), (2011, 2013)
FELL = (2011, 2013)


def moves(spells: pd.DataFrame) -> pd.DataFrame:
    s = spells.copy()
    s["org_name"] = s.org_name.fillna("")
    s["org_form"] = s.org_form.fillna("")
    s["start"] = pd.to_datetime(s.start_date, errors="coerce")
    s = s.dropna(subset=["start", "rank_score"])
    s["branch"] = [security_branch(p, o, f) for p, o, f in
                   zip(s.org_portfolio, s.org_name, s.org_form)]
    m = consecutive_moves(s).dropna(subset=["to_rank_score"])
    # Strictly lower. A lateral move at equal rank is not a demotion, and
    # counting it as one would put a third of ordinary reassignments into the
    # series.
    m["down"] = m.to_rank_score < m.rank_score
    return m


def series(m: pd.DataFrame, pick) -> list[dict]:
    sub = m[pick(m)]
    out = []
    for y in range(SPAN[0], SPAN[1] + 1):
        w = sub[sub.start_year.between(y - HALF, y + HALF)]
        if len(w) < MIN_WINDOW:
            continue
        k, n = int(w.down.sum()), len(w)
        lo, hi = wilson(k, n)
        out.append({"year": y, "rate": k / n * 100, "lo": lo, "hi": hi, "n": n})
    return out


def window(m: pd.DataFrame, pick, lo, hi):
    w = m[pick(m) & m.start_year.between(lo, hi)]
    k, n = int(w.down.sum()), len(w)
    return k, n, (k / n * 100 if n else float("nan")), wilson(k, n) if n else (0, 0)


def fell(m: pd.DataFrame) -> list[dict]:
    """Where the demoted territorial officials landed, by the post they held."""
    d = m[(m.branch == "territorial") & m.down
          & m.start_year.between(*FELL)]
    g = (d.groupby("position_rank")
         .agg(n=("down", "size"), frm=("rank_score", "median"),
              to=("to_rank_score", "median"))
         .reset_index())
    g = g[g.n >= 5].sort_values("frm", ascending=False)
    return g.to_dict("records")


LABEL = {"gouverneur": "Gouverneur", "secretaire_general": "Secrétaire général",
         "directeur": "Directeur", "chef_service": "Chef de service",
         "sous_directeur": "Sous-directeur", "local": "Local official",
         "autre": "Other post"}


def draw_left(ax, terr, cent, rest) -> None:
    ys = [r["year"] for r in terr]
    ax.fill_between(ys, [r["lo"] for r in terr], [r["hi"] for r in terr],
                    color=TERRITORIAL, alpha=0.13, lw=0, zorder=1)
    for rows, colour, lw in ((rest, MUTED, 1.4), (cent, CENTRAL, 1.6),
                             (terr, TERRITORIAL, 2.2)):
        ax.plot([r["year"] for r in rows], [r["rate"] for r in rows],
                color=colour, lw=lw, zorder=3, solid_capstyle="round")

    for y, lab in RUPTURES.items():
        ax.axvline(y, color=RUPTURE_COLOUR[lab], lw=0.9, ls=(0, (3, 2.4)),
                   zorder=2)
        ax.annotate(lab, xy=(y, 62.5), ha="center", va="bottom", fontsize=7.4,
                    color=RUPTURE_COLOUR[lab], fontweight="bold")

    ax.set_xlim(SPAN[0] - 1, SPAN[1] + 1)
    ax.set_ylim(5, 66)
    ax.set_yticks([10, 20, 30, 40, 50, 60])
    ax.set_yticklabels([f"{v}%" for v in (10, 20, 30, 40, 50, 60)])
    ax.set_ylabel("moves that go down in rank, three-year window", fontsize=8.4)
    ax.yaxis.grid(True, lw=0.6)
    ax.set_axisbelow(True)
    ax.set_title("When", fontsize=9.8)
    ax.legend(handles=[
        Line2D([], [], color=TERRITORIAL, lw=2.2,
               label="territorial security — governors, regional commissariats"),
        Line2D([], [], color=CENTRAL, lw=1.6, label="interior ministry, central"),
        Line2D([], [], color=MUTED, lw=1.4, label="the rest of the state"),
    ], loc="upper center", bbox_to_anchor=(0.5, -0.10), ncol=1, fontsize=8.0)


def draw_right(ax, rows) -> None:
    y = np.arange(len(rows))[::-1]
    for i, r in zip(y, rows):
        ax.annotate("", xy=(r["to"], i), xytext=(r["frm"], i),
                    arrowprops=dict(arrowstyle="-|>", color=TERRITORIAL,
                                    lw=1.8, shrinkA=0, shrinkB=0,
                                    mutation_scale=11))
        ax.plot([r["frm"]], [i], "o", ms=7, color=TERRITORIAL, zorder=4)
        ax.annotate(f"{LABEL.get(r['position_rank'], r['position_rank'])}",
                    xy=(r["frm"] + 1.5, i + 0.30), ha="left", va="bottom",
                    fontsize=8.2, fontweight="bold", color=INK)
        ax.annotate(f"{int(r['frm'])} → {int(r['to'])}   ·   {int(r['n'])} people",
                    xy=(r["to"] - 1.5, i - 0.02), ha="right", va="center",
                    fontsize=7.2, color=MUTED)
    ax.set_yticks([])
    ax.set_ylim(-0.7, len(rows) - 0.25)
    ax.set_xlim(-4, 97)
    ax.set_xticks([0, 20, 35, 55, 70, 80, 95])
    ax.set_xlabel("rank on the codebook's ordinal scale", fontsize=8.4)
    ax.xaxis.grid(True, lw=0.6)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.set_title("How far, 2011–2013", fontsize=9.8)


def fig_demotions(spells: pd.DataFrame) -> None:
    m = moves(spells)
    is_terr = lambda d: d.branch == "territorial"      # noqa: E731
    is_cent = lambda d: d.branch == "interior"         # noqa: E731
    is_rest = lambda d: d.branch.isna()                # noqa: E731

    terr, cent, rest = (series(m, p) for p in (is_terr, is_cent, is_rest))
    rows = fell(m)

    is_sec = lambda d: d.branch.notna()                # noqa: E731
    _, n_tp, r_tp, (lo_tp, hi_tp) = window(m, is_terr, *PRE)
    _, n_to, r_to, (lo_to, hi_to) = window(m, is_terr, *POST)
    # The whole apparatus, for the claim about it. Reading the territorial
    # rate here is what made the first version of this subtitle say the
    # apparatus was no worse treated while quoting a number fourteen points
    # above the comparison.
    _, _, r_sp, _ = window(m, is_sec, *PRE)
    _, _, r_so, _ = window(m, is_sec, *POST)
    _, _, r_cp, _ = window(m, is_cent, *PRE)
    _, _, r_co, _ = window(m, is_cent, *POST)
    _, _, r_rp, _ = window(m, is_rest, *PRE)
    _, _, r_ro, _ = window(m, is_rest, *POST)
    _, _, r_late, _ = window(m, is_terr, 2018, 2020)
    disjoint = hi_tp < lo_to

    fig, axes = plt.subplots(1, 2, figsize=(14.2, 7.4),
                             gridspec_kw={"width_ratios": [1.35, 1.0]})
    fig.subplots_adjust(top=0.755, bottom=0.205, left=0.065, right=0.975,
                        wspace=0.20)
    draw_left(axes[0], terr, cent, rest)
    draw_right(axes[1], rows)

    top = rows[0]
    steep = max(rows, key=lambda r: r["frm"] - r["to"])
    headline(
        fig,
        "After 2011 the provinces were demoted, not the ministry",
        f"A demotion is a move to a lower-ranked post. Taken whole the "
        f"security apparatus was no worse treated than anyone else after the "
        f"revolution — {r_so:.0f}% of its moves went down in 2011–13 against "
        f"{r_ro:.0f}% for the rest of the state, and both rose together. The "
        f"split is the finding: the territorial arm went from {r_tp:.0f}% "
        f"before the revolution to {r_to:.0f}% after, on {n_tp} and {n_to} "
        f"moves, and those Wilson intervals "
        + ("do not overlap" if disjoint else "overlap") +
        f"; the central interior ministry went from {r_cp:.0f}% to "
        f"{r_co:.0f}%, a {r_co - r_cp:+.0f}-point move against the "
        f"territorial {r_to - r_tp:+.0f}. Nor did it revert — the "
        f"territorial rate stands at {r_late:.0f}% in the three years before "
        f"2021. Right: where the demoted territorial officials landed. "
        f"{int(top['n'])} governors fell from {int(top['frm'])} to "
        f"{int(top['to'])} on the rank scale; "
        f"{LABEL.get(steep['position_rank'], '').lower()}s fell furthest, "
        f"{int(steep['frm'])} to {int(steep['to'])}.",
        width=150,
    )
    save(fig, "fig38_security_demotions",
         SOURCE + "  A demotion is a move to a strictly lower rank on the "
                  "codebook's ordinal scale: the same person, the next "
                  "appointment the gazette records for them, lower than the "
                  "one before. A lateral move at equal rank is not counted, "
                  "and neither is leaving the record — a career that stops "
                  "cannot be told from a career the register stops following, "
                  "so purges that ended in dismissal rather than demotion are "
                  "outside this figure and would if anything make the pattern "
                  "stronger. Each point is a three-year window: a single year "
                  "of territorial moves runs to a median of twenty-six and "
                  "thins below fifteen in the 1960s, while every window drawn "
                  "here clears twenty-five. The band on the territorial series "
                  "is its Wilson interval; the other two are drawn without one "
                  "to keep the plate readable, and rest on far larger samples. "
                  "The territorial branch is the security administration "
                  "outside the capital — governorates, regional commissariats, "
                  "delegations — and the central branch is the interior "
                  "ministry proper; the split is the one scripts/apparatus.py "
                  "already used for the outflow figures. On the other "
                  "ruptures: 1987 moves the same way, 27% to 53%, but on "
                  "thirty-seven moves before the coup the intervals overlap "
                  "and it cannot be called; 2021 does not move. 2011 is the "
                  "only rupture in the record where this jump is separable "
                  "from chance. Ranks on the right are medians over the "
                  "demoted, and a post appears only where at least five people "
                  "held it.")


def main() -> None:
    print("loading tables…")
    spells = pd.read_csv(PROC / "spells.csv.gz", low_memory=False)
    print("drawing…")
    fig_demotions(spells)
    print("done")


if __name__ == "__main__":
    main()
