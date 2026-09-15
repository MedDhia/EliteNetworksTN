"""Women in the Tunisian listed-company board network, 2005-2026.

Three panels, in the order the argument has to be made.

**A. Participation is estimable and it rose.** The share of gendered directors
who are women, per year. One series, so the title names it and no legend box is
needed.

**B. The brokerage pool did not follow.** Counts of directors holding more than
one board seat, which are the only people who can have non-zero betweenness.
This panel exists to show the reader *why* panel A cannot be repeated for
centrality: the women's bar is 0 to 6 people. Drawing a mean over that as a
line would hand the reader a shape to interpret that the data does not carry.

**C. Pooled over the whole window, where n supports it.** Two separate
single-measure panels rather than one with two y-scales.

Colour follows the person, not the rank: women carry the house PERSON hue and
men the ORG hue, a two-slot categorical pair validated together (CVD dE 23.6
protan, 26.6 tritan, 27.9 normal vision, all above the floor). "Gender not
recorded" is deliberately the neutral grey and deliberately fails a categorical
chroma check - it is absent information, not a third category, and should
recede.

Run with::

    PYTHONPATH=src python scripts/figures_women_centrality.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np

from house_style import CAT4, INK, MUTED, headline, plt, save

from bourse.analysis_women_centrality import FIRST_YEAR, LAST_YEAR, pooled, read_seats
from bourse.gender import load as load_gender

WOMEN = CAT4[0]      # #A03B2C
MEN = CAT4[1]        # #1B5FC1
UNKNOWN = MUTED      # neutral: absent information, not a category

DATA = ROOT / "data" / "processed" / "bourse" / "women_centrality.csv"


def read_series() -> list[dict]:
    with DATA.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        for k, v in r.items():
            if k == "year":
                r[k] = int(v)
            elif v == "":
                r[k] = None
            else:
                r[k] = float(v)
    return rows


def panel_participation(ax, rows, *, marker_note: bool = True) -> None:
    yr = [r["year"] for r in rows]
    pct = [r["pct_women_of_gendered"] for r in rows]
    ax.grid(axis="y", linewidth=0.6, alpha=0.7)
    ax.set_axisbelow(True)
    ax.plot(yr, pct, color=WOMEN, linewidth=2.0, zorder=3)
    # Marker area carries the denominator. A share of 19 people and a share of
    # 130 are not the same claim, and printing the count under every point --
    # the first attempt -- collided with the baseline and broke the rule
    # against a number on every mark. Size says it without words; the exact
    # counts are a column in women_centrality.csv.
    n = np.array([r["women"] + r["men"] for r in rows], dtype=float)
    ax.scatter(yr, pct, s=18 + 90 * n / n.max(), color=WOMEN, zorder=4,
               edgecolor="white", linewidth=0.9)
    ax.set_ylim(0, max(p for p in pct if p is not None) * 1.35)
    ax.set_ylabel("% of gendered directors")
    ax.set_title("A.  Women's share of directors rose — this part is well measured")

    # Direct labels at the ends only: a number on every point is noise.
    for r in (rows[0], rows[-1]):
        ax.annotate(f"{r['pct_women_of_gendered']:.0f}%",
                    (r["year"], r["pct_women_of_gendered"]),
                    textcoords="offset points", xytext=(0, 11),
                    ha="center", fontsize=8.5, fontweight="bold", color=WOMEN)

    # Dropped in the one-column cut: at that width the line runs through
    # wherever this sits, and the same sentence is already in the caption.
    if marker_note:
        ax.annotate("marker area = directors whose gender is recorded that year "
                    f"({int(n.min())}–{int(n.max())})",
                    (0.995, 0.06), xycoords="axes fraction", ha="right",
                    fontsize=6.8, color=MUTED)


def panel_pool(ax, rows, *, legend_size: float = 7.6,
               headroom: float = 1.09) -> None:
    yr = np.array([r["year"] for r in rows])
    w = np.array([r["women_multi_board"] for r in rows])
    m = np.array([r["men_multi_board"] for r in rows])
    u = np.array([r["unknown_multi_board"] for r in rows])
    ax.grid(axis="y", linewidth=0.6, alpha=0.7)
    ax.set_axisbelow(True)
    # A 2px surface gap between adjacent bars, so the groups read as groups.
    width = 0.27
    ax.bar(yr - width, m, width * 0.92, color=MEN, label="Men", zorder=3)
    ax.bar(yr, u, width * 0.92, color=UNKNOWN, label="Gender not recorded",
           zorder=3, alpha=0.55)
    ax.bar(yr + width, w, width * 0.92, color=WOMEN, label="Women", zorder=3)
    ax.set_ylabel("directors on >1 board")
    ax.set_title("B.  But almost no women hold the second seat that brokerage requires")
    # The legend sits over the tallest bar unless the axis is given room for
    # it; ncol=3 keeps it to one line so that room is a strip, not a block.
    ax.set_ylim(0, max(m.max(), u.max(), w.max()) * headroom)
    ax.legend(loc="upper left", ncol=3, fontsize=legend_size,
              columnspacing=1.1, handlelength=1.3, handletextpad=0.5)

    # Label the women's bar every year: these are the numbers the claim rests
    # on, and they are small enough that every one of them matters.
    for x, v in zip(yr, w):
        ax.annotate("0" if v == 0 else f"{v:.0f}", (x + width, v),
                    textcoords="offset points", xytext=(0, 2.5), ha="center",
                    fontsize=6.4, color=WOMEN if v else MUTED,
                    fontweight="bold" if v else "normal")


def panel_pooled(ax, pool, key, title, fmt, ylabel) -> None:
    vals = [pool["women"][key], pool["men"][key]]
    ax.grid(axis="y", linewidth=0.6, alpha=0.7)
    ax.set_axisbelow(True)
    bars = ax.bar(["Women", "Men"], vals, width=0.52, color=[WOMEN, MEN], zorder=3)
    ax.set_ylim(0, max(vals) * 1.32)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=9)
    for b, v in zip(bars, vals):
        ax.annotate(fmt(v), (b.get_x() + b.get_width() / 2, v),
                    textcoords="offset points", xytext=(0, 4), ha="center",
                    fontsize=9, fontweight="bold", color=INK)
    ax.set_xticks([0, 1])
    ax.set_xticklabels([f"Women\nn={pool['women']['n']}",
                        f"Men\nn={pool['men']['n']}"], color=INK, fontsize=8.5)


SUBTITLE = ("Directors of BVMT-listed companies, 2005–2026. Gender is read from "
            "the honorific the filer printed (M./Mme), never guessed from the "
            "given name; the 27–70% of directors carrying no honorific are "
            "counted as unknown, never as men.")
NOTE = ("Betweenness is computed on the bipartite director–firm graph, where it "
        "is non-zero only for a director sitting on more than one board. The "
        "brokerage panel is why no yearly centrality series is drawn: the "
        "women's bar is 0–6 people and zero in 8 of 22 years. Source: CMF "
        "filings, 1,887 documents. Code: scripts/figures_women_centrality.py")


def _year_axis(*axes) -> None:
    for ax in axes:
        ax.set_xlim(FIRST_YEAR - 0.8, LAST_YEAR + 0.8)
        ax.set_xticks(range(FIRST_YEAR, LAST_YEAR + 1, 2))


def fig_participation(rows) -> None:
    """Panel A alone, for a slide or a paper that only needs the trend."""
    fig = plt.figure(figsize=(7.4, 4.3))
    ax = fig.add_subplot(111)
    fig.subplots_adjust(top=0.80, bottom=0.155, left=0.098, right=0.975)
    panel_participation(ax, rows)
    ax.set_title("")           # the headline carries it in this cut
    _year_axis(ax)
    headline(fig, "Women's share of Tunisian listed-company directors, 2005–2026",
             SUBTITLE, top=0.985)
    save(fig, "fig02_bourse_women_participation",
         "Share of directors whose gender the filing records. Marker area is the "
         "number of such directors that year (28–134). Source: CMF filings. "
         "Code: scripts/figures_women_centrality.py")


def fig_slide(rows) -> None:
    """16:9, two panels, larger type — the argument in one screen."""
    with plt.rc_context({"font.size": 10.5, "axes.titlesize": 12,
                         "legend.fontsize": 9.5}):
        fig = plt.figure(figsize=(13.33, 7.5))
        gs = fig.add_gridspec(1, 2, wspace=0.20, top=0.775, bottom=0.115,
                              left=0.062, right=0.978)
        ax_a = fig.add_subplot(gs[0, 0])
        ax_b = fig.add_subplot(gs[0, 1])
        panel_participation(ax_a, rows)
        panel_pool(ax_b, rows, legend_size=9.5, headroom=1.16)
        ax_a.set_title("Women's share of directors rose", fontsize=13)
        ax_b.set_title("The brokerage pool did not", fontsize=13)
        _year_axis(ax_a, ax_b)
        headline(fig,
                 "Women entered Tunisian boards. They did not enter the brokerage.",
                 SUBTITLE, top=0.985)
        save(fig, "fig03_bourse_women_slide", NOTE)


def fig_compact(rows) -> None:
    """One journal column wide: the two yearly panels, stacked and stripped."""
    with plt.rc_context({"font.size": 7, "axes.titlesize": 8,
                         "legend.fontsize": 6.4, "xtick.labelsize": 6.5,
                         "ytick.labelsize": 6.5}):
        fig = plt.figure(figsize=(3.5, 5.0))
        gs = fig.add_gridspec(2, 1, hspace=0.40, top=0.805, bottom=0.105,
                              left=0.168, right=0.985)
        ax_a = fig.add_subplot(gs[0, 0])
        ax_b = fig.add_subplot(gs[1, 0])
        panel_participation(ax_a, rows, marker_note=False)
        panel_pool(ax_b, rows, legend_size=5.8, headroom=1.30)
        ax_a.set_title("A.  Women's share of directors", fontsize=8)
        ax_b.set_title("B.  Directors on more than one board", fontsize=8)
        for ax in (ax_a, ax_b):
            ax.set_xlim(FIRST_YEAR - 0.8, LAST_YEAR + 0.8)
            ax.set_xticks(range(FIRST_YEAR, LAST_YEAR + 1, 5))
        headline(fig, "Women on Tunisian boards, 2005–2026",
                 "Gender from printed honorifics; 27–70% unrecorded and counted "
                 "as unknown, never as men.", top=0.985)
        save(fig, "fig04_bourse_women_compact",
             "Betweenness is non-zero only above one board seat; panel B is why "
             "no centrality series is drawn. Source: CMF filings.")


def main() -> None:
    rows = read_series()
    gender = load_gender()
    pool = pooled(read_seats(), gender)

    fig = plt.figure(figsize=(7.6, 8.8))
    gs = fig.add_gridspec(3, 2, height_ratios=[1.05, 1.0, 0.78],
                          hspace=0.52, wspace=0.30,
                          top=0.875, bottom=0.125, left=0.093, right=0.975)
    ax_a = fig.add_subplot(gs[0, :])
    ax_b = fig.add_subplot(gs[1, :], sharex=ax_a)
    ax_c1 = fig.add_subplot(gs[2, 0])
    ax_c2 = fig.add_subplot(gs[2, 1])

    panel_participation(ax_a, rows)
    panel_pool(ax_b, rows)
    panel_pooled(ax_c1, pool, "pct_nonzero",
                 "C.  Share who broker between firms at all",
                 lambda v: f"{v:.0f}%", "% with betweenness > 0")
    panel_pooled(ax_c2, pool, "mean",
                 "D.  Mean betweenness, pooled 2005–2026",
                 lambda v: f"{v:.4f}", "mean betweenness")

    for ax in (ax_a, ax_b):
        ax.set_xlim(FIRST_YEAR - 0.8, LAST_YEAR + 0.8)
        ax.set_xticks(range(FIRST_YEAR, LAST_YEAR + 1, 2))

    headline(
        fig,
        "Women entered Tunisian boards. They did not enter the brokerage.",
        "Directors of BVMT-listed companies, 2005–2026. Gender is read from the "
        "honorific the filer printed (M./Mme), never guessed from the given name; "
        "the 27–70% of directors carrying no honorific are counted as unknown, "
        "never as men.",
    )
    save(fig, "fig01_bourse_women_centrality",
         "Betweenness is computed on the bipartite director–firm graph, where it "
         "is non-zero only for a director sitting on more than one board. Panel B "
         "is why no yearly centrality series is drawn: the women's bar is 0–6 "
         "people and zero in 8 of 22 years. Source: CMF filings, 1,887 documents. "
         "Code: scripts/figures_women_centrality.py")

    # Three cuts of the same argument, for the places it has to go: the trend
    # alone, a 16:9 screen, and one journal column.
    fig_participation(rows)
    fig_slide(rows)
    fig_compact(rows)


if __name__ == "__main__":
    main()
