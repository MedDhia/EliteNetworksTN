"""Publication figure: brokerage is non-monotonic in cohesion.

Writes ``figures/fig14_cohesion_brokerage.{pdf,png}``, the plotted quantities
as ``figures/fig14_cohesion_brokerage.csv``, and a ready-to-paste LaTeX
snippet as ``figures/fig14_cohesion_brokerage.tex``.

Sized for a journal column, NOT for screen. The exploratory map in
``figure_core_periphery.py`` is 18.4 inches wide and carries 6.8pt
annotations; reduced to a 5.2-inch text block it is an unreadable speckle.
This is the same finding rebuilt as one claim at final size, so nothing is
scaled down after rendering and every character stays at or above 8pt.

The claim
---------

The k-core decomposition and betweenness centrality identify *different*
elites in this network, and they disagree in a specific, non-monotonic way:
brokerage rises to a peak at the k=5 shell and then falls in the more
cohesive shells inside it, while the composition of that brokerage inverts
from organisations to natural persons at the same boundary.

Why the figure carries its own robustness check
-----------------------------------------------

The obvious objection is that this is a degree artefact -- betweenness
correlates with degree, and mean degree also falls from k=5 (21.1) to k=6
(15.5). It is not. Holding degree in [15, 30], the median betweenness is
957,498 at k=5 against 384,446 at k=6, a factor of 2.5. That degree-matched
series is plotted alongside the unmatched one rather than being asserted in
the text, because it is the comparison a reader should be able to check.

Note this is *smaller* than the ratio of maxima the exploratory figure
reports (37.4M / 4.3M = 9x). The ninefold figure is a true statement about
maxima and a misleading one about the effect, so the degree-matched 2.5x is
what this figure and its caption use.

What is deliberately NOT claimed
--------------------------------

The k=7 shell holds **8 nodes**, and only one of them falls in the
degree-matched band. It cannot carry an inference and is drawn with open
markers and excluded from the matched series. The composition inversion at
k=7 (100% natural persons) is reported as description, not as a test.
"""
from __future__ import annotations

import argparse
import collections
import csv
import pickle
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

FIGS = ROOT / "figures"
FIGS.mkdir(exist_ok=True)
CACHE = ROOT / "data" / "interim" / "core_periphery.pkl"
STEM = "fig14_cohesion_brokerage"

# Value-encoded, not hue-encoded: journal print is frequently greyscale, so
# identity is carried by lightness, marker shape and direct labels. One
# accent is used, for the boundary the figure is about.
BLACK = "#111111"
DARK = "#3F3F3D"
MID = "#8A8A85"
LIGHT = "#D9D7D0"
PALE = "#EFEEE9"
ACCENT = "#A03B2C"

# The degree band the matched comparison is made in, and the minimum cell
# size to plot a matched point at all.
DEG_LO, DEG_HI = 15, 30
MIN_CELL = 20

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white",
    "savefig.facecolor": "white", "font.family": "DejaVu Sans",
    "font.size": 9.0, "pdf.fonttype": 42, "ps.fonttype": 42,
    "legend.frameon": False, "axes.linewidth": 0.7,
})

PERSON_CLASS = "individual"


def load() -> list[dict]:
    if not CACHE.exists():
        raise SystemExit(
            f"missing {CACHE.relative_to(ROOT)} — run "
            f"scripts/figure_core_periphery.py first")
    with CACHE.open("rb") as fh:
        d = pickle.load(fh)
    return [{"bc": d["bc"][i], "k": d["core"][i], "deg": d["degree"][i],
             "is_person": d["cls"][d["nodes"][i]] == PERSON_CLASS}
            for i in range(len(d["nodes"]))]


def shells(rows) -> list[dict]:
    """Per k-shell: the betweenness distribution, matched and unmatched."""
    by = collections.defaultdict(list)
    for r in rows:
        by[r["k"]].append(r)

    out = []
    for k in sorted(by):
        v = by[k]
        b = sorted(r["bc"] for r in v)
        matched = [r["bc"] for r in v if DEG_LO <= r["deg"] <= DEG_HI]
        mass = sum(b)
        person_mass = sum(r["bc"] for r in v if r["is_person"])
        out.append({
            "k": k, "n": len(v),
            "median": st.median(b),
            "q25": b[int(.25 * (len(b) - 1))],
            "q75": b[int(.75 * (len(b) - 1))],
            "max": b[-1],
            "n_matched": len(matched),
            "median_matched": st.median(matched) if matched else float("nan"),
            "mean_degree": st.mean(r["deg"] for r in v),
            "mass": mass,
            "person_share": person_mass / mass if mass else float("nan"),
            "n_persons": sum(1 for r in v if r["is_person"]),
            # The composition baseline. Without it, panel (b) cannot
            # distinguish "persons broker more than their numbers" from
            # "the shell happens to contain persons" -- and at k=7, where
            # there are no organisations at all, only the latter is true.
            "person_node_share": sum(1 for r in v if r["is_person"]) / len(v),
        })
    return out


def _spines(ax) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(DARK)
    ax.tick_params(colors=DARK, labelsize=8.5, length=3, width=.7)
    for lbl in ax.get_yticklabels() + ax.get_xticklabels():
        lbl.set_color(BLACK)


def boundary(ax, at: float) -> None:
    ax.axvline(at, color=ACCENT, lw=.9, ls=(0, (4, 2.5)), zorder=1,
               alpha=.85)


def panel_a(ax, sh) -> None:
    ks = [s["k"] for s in sh]
    floor = 6e3  # a log axis cannot draw the k=1 median, which is exactly 0

    ax.fill_between(ks, [max(s["q25"], floor) for s in sh],
                    [max(s["q75"], floor) for s in sh],
                    color=PALE, zorder=1, lw=0)
    ax.plot(ks, [max(s["median"], floor) for s in sh], "-", color=BLACK,
            lw=1.6, zorder=3)

    small = [s for s in sh if s["n"] < 30]
    big = [s for s in sh if s["n"] >= 30]
    ax.plot([s["k"] for s in big], [max(s["median"], floor) for s in big],
            "o", ms=5.2, mfc=BLACK, mec="white", mew=.8, zorder=4,
            label="all nodes in the shell")
    ax.plot([s["k"] for s in small], [max(s["median"], floor) for s in small],
            "o", ms=5.2, mfc="white", mec=BLACK, mew=1.1, zorder=4,
            label="shell has < 30 nodes")

    m = [s for s in sh if s["n_matched"] >= MIN_CELL]
    ax.plot([s["k"] for s in m], [s["median_matched"] for s in m],
            ls=(0, (3.5, 2)), color=MID, lw=1.4, zorder=2)
    ax.plot([s["k"] for s in m], [s["median_matched"] for s in m], "s",
            ms=4.6, mfc="white", mec=MID, mew=1.2, zorder=4,
            label=f"matched on degree {DEG_LO}–{DEG_HI}")

    ax.set_yscale("log")
    ax.set_ylim(floor * .62, 6.0e6)
    ax.set_yticks([1e4, 1e5, 1e6])
    ax.set_yticklabels(["$10^4$", "$10^5$", "$10^6$"])
    ax.set_ylabel("Betweenness centrality", fontsize=9, color=BLACK)
    _spines(ax)
    ax.grid(axis="y", color=PALE, lw=.7, zorder=0)
    ax.set_axisbelow(True)

    peak = max(sh, key=lambda s: s["median_matched"]
               if s["n_matched"] >= MIN_CELL else -1)
    nxt = next(s for s in sh if s["k"] == peak["k"] + 1)
    ratio = peak["median_matched"] / nxt["median_matched"]
    boundary(ax, peak["k"] + .5)

    # A bracket spanning the two degree-matched values, rather than a leader
    # line: the leader had to cross the unmatched series to reach its text,
    # which made it ambiguous which series the ratio referred to.
    bx = nxt["k"] + .30
    lo, hi = nxt["median_matched"], peak["median_matched"]
    ax.plot([bx, bx], [lo, hi], color=ACCENT, lw=.9, zorder=5,
            solid_capstyle="butt")
    for yy in (lo, hi):
        ax.plot([bx - .075, bx], [yy, yy], color=ACCENT, lw=.9, zorder=5)
    ax.annotate(f"{ratio:.1f}×", (bx, (lo * hi) ** .5), xytext=(4, 0),
                textcoords="offset points", ha="left", va="center",
                fontsize=8.5, color=ACCENT, fontweight="semibold")

    ax.annotate("median is 0", (1, floor), xytext=(7, 1),
                textcoords="offset points", ha="left", va="center",
                fontsize=8, color=MID)
    handles, _ = ax.get_legend_handles_labels()
    handles.append(Patch(fc=PALE, ec="none",
                         label="interquartile range, all nodes"))
    # Two columns, not four rows: stacked, the last entry reached down into
    # the degree-matched series it was meant to describe.
    ax.legend(handles=handles, loc="upper left", fontsize=8, ncol=2,
              labelcolor=BLACK, handlelength=1.9, handletextpad=.5,
              labelspacing=.32, columnspacing=1.1, borderpad=.15,
              borderaxespad=.2)


def panel_b(ax, sh) -> None:
    ks = [s["k"] for s in sh]
    person = [100 * s["person_share"] for s in sh]

    ax.fill_between(ks, 0, person, color=LIGHT, lw=0, zorder=1)
    ax.fill_between(ks, person, 100, color=DARK, lw=0, zorder=1)

    # The composition baseline: persons' share of the shell's NODES. Where
    # the boundary sits away from it, brokerage is not tracking headcount.
    nodeshare = [100 * s["person_node_share"] for s in sh]
    ax.plot(ks, nodeshare, ls=(0, (1.4, 1.8)), color="white", lw=1.5,
            zorder=3)
    ax.plot(ks, nodeshare, ls=(0, (1.4, 1.8)), color=BLACK, lw=1.0, zorder=3)

    ax.plot(ks, person, "-", color="white", lw=1.5, zorder=4)
    ax.plot(ks, person, "o", ms=4.4, mfc="white", mec=BLACK, mew=1.0,
            zorder=5)

    ax.text(1.13, 88, "Organisations", fontsize=9, color="white",
            fontweight="semibold", va="center", zorder=6)
    ax.text(1.13, 7, "Natural persons", fontsize=9, color=BLACK,
            fontweight="semibold", va="center", zorder=6)
    ax.annotate("persons' share of nodes", (1, nodeshare[0]),
                xytext=(9, -11), textcoords="offset points", ha="left",
                va="center", fontsize=8, color=BLACK, zorder=6)

    # Direct value labels on the boundary rather than a leader and a
    # sentence: the sentence belongs in the caption, and a leader into a
    # filled region had nothing to point at.
    trough = min(sh, key=lambda s: s["person_share"])
    for s, share in zip(sh, person):
        emph = s["k"] in (trough["k"], ks[-1])
        # Labels sit below the boundary, inside the light band. At the last
        # shell the band reaches the top, so that one also shifts left or it
        # lands on the tapering dark fill and loses contrast.
        last = s["k"] == ks[-1]
        # At the last shell both series converge on 100, so this label is
        # steered into the gap between them rather than nudged off the point.
        ax.annotate(f"{share:.0f}", (s["k"], share),
                    xytext=(-26 if last else 0, -26 if last else -11),
                    textcoords="offset points",
                    ha="center", va="center",
                    fontsize=8.6 if emph else 8.0, zorder=5,
                    color=BLACK if emph else MID,
                    fontweight="semibold" if emph else "normal")
    boundary(ax, trough["k"] + .5)

    ax.set_ylim(0, 100)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_yticklabels(["0", "25", "50", "75", "100%"])
    ax.set_ylabel("Share of the shell's total\nbetweenness", fontsize=9,
                  color=BLACK, linespacing=1.5)
    ax.set_xlabel("Coreness $k$   (peripheral  →  most cohesive)",
                  fontsize=9, color=BLACK, labelpad=4)
    _spines(ax)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--width", type=float, default=5.2,
                    help="final width in inches; APSR text block is ~5.2")
    args = ap.parse_args(argv)

    sh = shells(load())
    ks = [s["k"] for s in sh]

    fig, (ax_a, ax_b) = plt.subplots(
        2, 1, figsize=(args.width, args.width * 1.04), sharex=True,
        gridspec_kw=dict(height_ratios=[1.28, 1.0], hspace=.13))

    panel_a(ax_a, sh)
    panel_b(ax_b, sh)

    ax_b.set_xlim(min(ks) - .32, max(ks) + .52)
    ax_b.set_xticks(ks)

    # n per shell along the top, so no point is read without its cell size
    for s in sh:
        ax_a.annotate(f"{s['n']:,}", (s["k"], 1.0),
                      xycoords=("data", "axes fraction"), xytext=(0, 4),
                      textcoords="offset points", ha="center", va="bottom",
                      fontsize=8.0, color=MID)
    ax_a.annotate("nodes:", (0, 1.0), xycoords="axes fraction",
                  xytext=(-4, 4), textcoords="offset points", ha="right",
                  va="bottom", fontsize=8.0, color=MID)

    # (a) sits a line above the shell-size row, which shares its corner
    ax_a.annotate("(a)", (0, 1.0), xycoords="axes fraction",
                  xytext=(-34, 19), textcoords="offset points", ha="left",
                  va="bottom", fontsize=10, color=BLACK, fontweight="bold")
    ax_b.annotate("(b)", (0, 1.0), xycoords="axes fraction",
                  xytext=(-34, 5), textcoords="offset points", ha="left",
                  va="bottom", fontsize=10, color=BLACK, fontweight="bold")

    fig.subplots_adjust(left=0.158, right=0.985, top=0.905, bottom=0.093)

    for ext, kw in (("pdf", {}), ("png", {"dpi": 600})):
        p = FIGS / f"{STEM}.{ext}"
        fig.savefig(p, **kw)
        print(f"  {p.relative_to(ROOT)}  {p.stat().st_size / 1024:.0f} KB")
    plt.close(fig)

    _write_csv(sh)
    _write_tex(sh)
    for s in sh:
        print(f"  k={s['k']}  n={s['n']:>6}  median {s['median']:>10,.0f}  "
              f"matched(n={s['n_matched']:>3}) "
              f"{s['median_matched']:>12,.0f}  persons "
              f"{100 * s['person_share']:>5.1f}%")
    return 0


def _write_csv(sh) -> None:
    path = FIGS / f"{STEM}.csv"
    cols = ["k", "n", "n_persons", "mean_degree", "median", "q25", "q75",
            "max", "n_matched", "median_matched", "mass", "person_share"]
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for s in sh:
            w.writerow([s[c] for c in cols])
    print(f"  wrote {path.relative_to(ROOT)}")


def _write_tex(sh) -> None:
    """The caption, with every number pulled from the data it describes."""
    peak = max(sh, key=lambda s: s["median_matched"]
               if s["n_matched"] >= MIN_CELL else -1)
    nxt = next(s for s in sh if s["k"] == peak["k"] + 1)
    inner = min(sh, key=lambda s: s["person_share"])
    last = sh[-1]
    gap = next(s for s in sh if s["k"] == inner["k"] + 1)
    total_n = sum(s["n"] for s in sh)

    tex = rf"""\begin{{figure}}[t]
  \centering
  \includegraphics[width=\textwidth]{{{STEM}.pdf}}
  \caption{{\textbf{{Brokerage is non-monotonic in cohesion.}}
  Panel (a): betweenness centrality by $k$-core shell, median with
  interquartile range shaded. Brokerage rises to a peak at $k$={peak['k']}
  and falls in the more cohesive shells inside it. The dashed series repeats
  the comparison among nodes of comparable degree
  ({DEG_LO}--{DEG_HI} ties), where the median falls from
  {peak['median_matched']:,.0f} at $k$={peak['k']} to
  {nxt['median_matched']:,.0f} at $k$={nxt['k']}, a factor of
  {peak['median_matched'] / nxt['median_matched']:.1f}; the fall is therefore
  not a degree artefact. Panel (b): the composition of each shell's
  brokerage inverts at the same boundary. Organisations hold
  {100 - 100 * inner['person_share']:.0f}\% of betweenness at
  $k$={inner['k']} and {100 - 100 * gap['person_share']:.0f}\% at
  $k$={gap['k']}. The dotted line gives natural persons' share of each
  shell's \emph{{nodes}}, so the two can be compared: persons are
  {100 * inner['person_node_share']:.0f}\% of the $k$={inner['k']} shell
  but hold only {100 * inner['person_share']:.0f}\% of its brokerage,
  and {100 * gap['person_node_share']:.0f}\% of the $k$={gap['k']} shell
  while holding {100 * gap['person_share']:.0f}\% of its brokerage. The
  inversion is therefore not a headcount effect. At $k$={last['k']} the
  shell consists of {last['n']} natural persons and no organisation at
  all, so its 100\% is compositional and is reported as description
  only.
  Cells of fewer than 30 nodes are drawn with open markers and excluded from
  the degree-matched series; the $k$={last['k']} shell holds {last['n']}
  nodes and is descriptive only.
  $N = {total_n:,}$ entities in the largest connected component.}}
  \label{{fig:cohesion-brokerage}}
\end{{figure}}
"""
    path = FIGS / f"{STEM}.tex"
    path.write_text(tex, encoding="utf-8")
    print(f"  wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    raise SystemExit(main())
