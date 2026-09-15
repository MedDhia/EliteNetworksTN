"""The alliance network as it accumulated, and what changed while it did.

Three plates over `network_evolution.csv` and `alliance_panel.csv`.

  fig04_rodovid_network_growth   the network at six dates, every family in the
                       same place in all six. One layout is computed on the
                       final network and every panel is drawn into it, so what
                       moves between panels is the network and not the drawing.
                       A family appears when it first marries out.
  fig05_rodovid_structure_over_time  four series: how big, how connected, how
                       closed, how concentrated -- each against the null that
                       makes it comparable across periods.
  fig06_rodovid_houses_over_time  the ten widest-married houses, one row each,
                       marriages per generation. This is the plate that says
                       whether a house was always central or accumulated its
                       way there.

Needs matplotlib and numpy. About four minutes, nearly all of it the layout.

Run with:  make rodovid-figures-dynamic   (or python -m rodovid.figures_dynamic)
"""
import collections
import csv
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from rodovid.figures import (
    CMAP, EDGE_INK, INK, INK_2, SURFACE, Graph, arcs, layout, place_labels,
    save_figure, shade, sizes,
)
from rodovid.paths import ALLIANCE_PANEL, EVOLUTION, ensure_dirs

from matplotlib.collections import PathCollection

# The six dates fig04 draws. Chosen to bracket the change rather than to space
# evenly: two panels before the field connects, two across the transition, two
# after it has.
PANELS = (1800, 1850, 1875, 1900, 1925, 1975)

SOURCE = ("Source: rodovid.org genealogies, filtered and collapsed to families "
          "by the rodovid build, dated by rodovid.dynamic. Marriages carry no "
          "date in the source: a couple is placed by the mean birth year of the "
          "two spouses, so a period is the generation the spouses belong to and "
          "the wedding follows roughly 25-30 years later. 85% of the alliances "
          "in the static network can be dated; see docs/LIMITATIONS-rodovid.md.")


def read_panel():
    with open(ALLIANCE_PANEL, encoding="utf-8") as fh:
        return [{**r, "period": int(r["period"]),
                 "marriages": int(r["marriages"]),
                 "marriages_cumulative": int(r["marriages_cumulative"])}
                for r in csv.DictReader(fh)]


def read_evolution():
    def num(v):
        if v == "":
            return None
        try:
            return int(v)
        except ValueError:
            try:
                return float(v)
            except ValueError:
                return v
    with open(EVOLUTION, encoding="utf-8") as fh:
        return [{k: num(v) for k, v in r.items()} for r in csv.DictReader(fh)]


# ---- fig04: the network at six dates ---------------------------------------

def cumulative_edges(panel, period):
    """Every alliance contracted by `period`, weighted by marriages so far."""
    weight = collections.Counter()
    for r in panel:
        if r["period"] <= period:
            weight[(r["family_a"], r["family_b"])] += r["marriages"]
    return weight


def growth_plate(panel):
    final = cumulative_edges(panel, max(r["period"] for r in panel))
    edges = [(a, b, w) for (a, b), w in sorted(final.items())]
    graph = Graph(edges)
    index = {f: i for i, f in enumerate(graph.families)}
    top = graph.marriages.max()

    print("laying out %d families, %d alliances (this is the slow part)"
          % (graph.n, len(edges)))
    radii = np.sqrt(sizes(graph.marriages, top, 90.0, 0.05)) * 0.012
    pos = layout(graph, radii, iterations=500, declutter=0.10)

    fig, axes = plt.subplots(2, 3, figsize=(16.5, 12.4))
    fig.patch.set_facecolor(SURFACE)
    span = np.abs(pos).max() * 1.04

    for ax, period in zip(axes.flat, PANELS):
        weight = cumulative_edges(panel, period)
        present = sorted({f for pair in weight for f in pair})
        mine = np.zeros(graph.n)
        for (a, b), w in weight.items():
            mine[index[a]] += w
            mine[index[b]] += w

        ax.set_facecolor(SURFACE)
        ax.set_axis_off()
        ax.set_aspect("equal")
        ax.set_xlim(-span, span)
        ax.set_ylim(-span, span)

        # Everything not yet married in, as a faint ground, so the eye sees
        # the field filling rather than six differently shaped blobs.
        ax.scatter(pos[:, 0], pos[:, 1], s=1.4, c="#e8e7e2", linewidths=0,
                   zorder=1)

        if weight:
            ends = np.array([(index[a], index[b]) for a, b in sorted(weight)])
            w = np.array([weight[p] for p in sorted(weight)], dtype=float)
            heavy = (w / w.max()) ** 0.7
            rgb = matplotlib.colors.to_rgb(EDGE_INK)
            ax.add_collection(PathCollection(
                arcs(pos, ends, 0.06), facecolors="none", zorder=2,
                capstyle="round",
                edgecolors=[(*rgb, 0.16 + 0.48 * h) for h in heavy],
                linewidths=0.55 * (0.35 + 1.9 * heavy)))
            idx = [index[f] for f in present]
            ax.scatter(pos[idx, 0], pos[idx, 1],
                       s=sizes(mine[idx], top, 90.0, 0.05),
                       c=CMAP(shade(mine[idx], top)), linewidths=0.35,
                       edgecolors=SURFACE, zorder=3)

        ax.text(0.5, 1.005, "by %d" % period, transform=ax.transAxes,
                fontsize=13, fontweight="bold", color=INK, ha="center",
                va="bottom")
        ax.text(0.5, 0.975, "%d families, %d alliances"
                % (len(present), len(weight)), transform=ax.transAxes,
                fontsize=9, color=INK_2, ha="center", va="bottom")

        # Name the widest-married houses of this panel, not of the final one:
        # the point of the plate is that the answer changes.
        fig.canvas.draw()
        order = sorted(present, key=lambda f: (-mine[index[f]], f))[:10]
        place_labels(ax, fig, [
            (pos[index[f], 0],
             pos[index[f], 1] + np.sqrt(sizes(mine[index[f]], top, 90.0, 0.05)) * 0.012 + 0.30,
             f, 7.4, "bold", INK) for f in order])

    fig.suptitle("A marriage field assembling itself", x=0.008, y=0.995,
                 ha="left", va="top", fontsize=17, color=INK,
                 fontweight="bold")
    fig.text(0.008, 0.962,
             "Tunisian elite families and the marriages between them, as they "
             "accumulate. Every family sits in the same place in all six "
             "panels, so a node darkening or an edge appearing is a marriage "
             "and nothing else.\nA family is drawn once it has married outside "
             "its own surname; the pale ground is the families still to come. "
             "Node size and shade are marriages into other families by that "
             "date.",
             ha="left", va="top", fontsize=9.6, color=INK_2, linespacing=1.45)
    fig.text(0.008, 0.018, SOURCE, ha="left", va="bottom", fontsize=7.0,
             color=INK_2, wrap=True)
    fig.subplots_adjust(left=0.004, right=0.996, top=0.905, bottom=0.048,
                        wspace=0.01, hspace=0.06)
    save_figure(fig, "fig04_rodovid_network_growth")
    plt.close(fig)
    print("fig04: six panels, %d families placed" % graph.n)


# ---- fig05: the series ------------------------------------------------------

def structure_plate(evo):
    complete = [r for r in evo if r["window_complete"] == 1]
    years = [r["period"] for r in evo]
    wyears = [r["period"] for r in complete]

    fig, axes = plt.subplots(2, 2, figsize=(12.6, 8.6))
    fig.patch.set_facecolor(SURFACE)
    blue, warm = CMAP(0.78), "#b4553f"

    def frame(ax, title, note):
        """Title above its unit line, both clear of the axes.

        The pad has to clear the note rather than the axes: a title set at the
        default pad lands on top of the line below it.
        """
        ax.set_facecolor(SURFACE)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color("#d3d0c7")
        ax.tick_params(colors=INK_2, labelsize=8.5)
        ax.set_title(title, fontsize=11.5, color=INK, fontweight="bold",
                     loc="left", pad=24)
        ax.text(0, 1.012, note, transform=ax.transAxes, fontsize=8.4,
                color=INK_2, va="bottom", ha="left")
        ax.grid(axis="y", color="#ecebe6", linewidth=0.8)
        ax.set_axisbelow(True)

    ax = axes[0][0]
    ax.plot(years, [r["families"] for r in evo], color=blue, lw=2.0,
            marker="o", ms=3.4, label="families, cumulative")
    ax.plot(wyears, [r["w_families"] for r in complete], color=warm, lw=1.7,
            marker="o", ms=3.0, ls="--", label="families marrying in the period")
    frame(ax, "How big", "families on the alliance graph")
    ax.legend(frameon=False, fontsize=8.2, loc="upper left")

    ax = axes[0][1]
    ax.plot(years, [100 * r["share_in_lcc"] for r in evo], color=blue, lw=2.0,
            marker="o", ms=3.4, label="cumulative")
    ax.plot(wyears, [100 * r["w_share_in_lcc"] for r in complete], color=warm,
            lw=1.7, marker="o", ms=3.0, ls="--", label="within the period")
    ax.set_ylim(0, 100)
    frame(ax, "How connected",
          "% of families in the largest connected component")
    ax.legend(frameon=False, fontsize=8.2, loc="upper left")

    ax = axes[1][0]
    ax.axhline(1.0, color=INK_2, lw=0.9, ls=":")
    ax.plot(years, [r["clustering_vs_random"] or 0 for r in evo], color=blue,
            lw=2.0, marker="o", ms=3.4, label="vs. a random graph of the same size")
    deg = [(r["period"], r["clustering_vs_degree_null"]) for r in evo
           if r["clustering_vs_degree_null"] not in (None, "")]
    ax.plot([p for p, _ in deg], [v for _, v in deg], color=warm, lw=1.7,
            marker="o", ms=3.0, ls="--",
            label="vs. a rewiring that keeps every family's allies")
    # Headroom, so the legend sits clear of the series rather than on it.
    ax.set_ylim(0, max(r["clustering_vs_random"] or 0 for r in evo) * 1.32)
    frame(ax, "How closed", "triangles, as a multiple of the null's")
    ax.legend(frameon=False, fontsize=8.2, loc="upper left")

    ax = axes[1][1]
    ax.axhline(1.0, color=INK_2, lw=0.9, ls=":")
    ax.plot(years, [r["centralization_vs_random"] or 0 for r in evo],
            color=blue, lw=2.0, marker="o", ms=3.4, label="cumulative")
    ax.plot(wyears, [r["w_centralization_vs_random"] or 0 for r in complete],
            color=warm, lw=1.7, marker="o", ms=3.0, ls="--",
            label="within the period")
    ax.set_ylim(0, max(r["centralization_vs_random"] or 0 for r in evo) * 1.32)
    frame(ax, "How concentrated",
          "degree centralization, as a multiple of the null's")
    ax.legend(frameon=False, fontsize=8.2, loc="upper left")

    fig.suptitle("What changed as the field assembled", x=0.008, y=0.995,
                 ha="left", va="top", fontsize=16, color=INK, fontweight="bold")
    fig.text(0.008, 0.958,
             "Each panel against the null that makes it comparable across "
             "periods: size and density move by an order of magnitude between "
             "1775 and today, and both closure and concentration move with them "
             "for no substantive reason. Dashed series stop at 1975, the last "
             "generation whose marriages have happened.\n"
             "Two readings to resist. In “how closed”, only the dashed "
             "line — against a rewiring that keeps every family's number of "
             "allies — is evidence of families marrying in circles; it is "
             "above 1 in 1875–1900 and nowhere else. In “how "
             "concentrated”,\nthe cumulative line partly counts elapsed "
             "time, because a house present from 1775 has had two centuries to "
             "collect allies and one arriving in 1950 has had one generation.",
             ha="left", va="top", fontsize=9.0, color=INK_2, linespacing=1.5)
    fig.text(0.008, 0.012, SOURCE, ha="left", va="bottom", fontsize=6.9,
             color=INK_2, wrap=True)
    fig.subplots_adjust(left=0.055, right=0.985, top=0.805, bottom=0.105,
                        wspace=0.18, hspace=0.50)
    save_figure(fig, "fig05_rodovid_structure_over_time")
    plt.close(fig)
    print("fig05: four series over %d periods" % len(evo))


# ---- fig06: the houses ------------------------------------------------------

def houses_plate(panel, evo, n_houses=10):
    per_family = collections.defaultdict(collections.Counter)
    for r in panel:
        per_family[r["family_a"]][r["period"]] += r["marriages"]
        per_family[r["family_b"]][r["period"]] += r["marriages"]
    totals = {f: sum(c.values()) for f, c in per_family.items()}
    houses = sorted(totals, key=lambda f: (-totals[f], f))[:n_houses]
    periods = [r["period"] for r in evo if r["window_complete"] == 1]

    fig, axes = plt.subplots(n_houses, 1, figsize=(8.8, 11.2), sharex=True)
    fig.patch.set_facecolor(SURFACE)
    ceiling = max(max(per_family[f][p] for p in periods) for f in houses)

    for ax, family in zip(axes, houses):
        counts = [per_family[family][p] for p in periods]
        ax.set_facecolor(SURFACE)
        ax.fill_between(periods, counts, color=CMAP(0.55), alpha=0.85, lw=0)
        ax.plot(periods, counts, color=CMAP(0.88), lw=1.3)
        ax.set_ylim(0, ceiling * 1.08)
        ax.set_yticks([])
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color("#d3d0c7")
        ax.tick_params(colors=INK_2, labelsize=9)
        peak = max(periods, key=lambda p: per_family[family][p])
        ax.text(-0.005, 0.5, family, transform=ax.transAxes, fontsize=10,
                color=INK, fontweight="bold", ha="right", va="center")
        ax.text(1.004, 0.5, "%d marriages\npeak %ds"
                % (totals[family], peak), transform=ax.transAxes, fontsize=7.6,
                color=INK_2, ha="left", va="center", linespacing=1.35)

    fig.suptitle("The ten widest-married houses, generation by generation",
                 x=0.008, y=0.995, ha="left", va="top", fontsize=15.5,
                 color=INK, fontweight="bold")
    fig.text(0.008, 0.958,
             "Marriages into other families per 25-year birth cohort, on one "
             "shared vertical scale. Surnames are rodovid's own reduction of "
             "the name, so a patronymic node aggregates unrelated people;\nBey, "
             "Mrad, Cherif and Belkhodja are houses, Ali and Youssef are not.",
             ha="left", va="top", fontsize=9.0, color=INK_2, linespacing=1.45)
    fig.text(0.008, 0.012, SOURCE, ha="left", va="bottom", fontsize=6.9,
             color=INK_2, wrap=True)
    fig.subplots_adjust(left=0.115, right=0.855, top=0.905, bottom=0.075,
                        hspace=0.22)
    save_figure(fig, "fig06_rodovid_houses_over_time")
    plt.close(fig)
    print("fig06: %s" % ", ".join(houses))


def main():
    ensure_dirs()
    panel = read_panel()
    evo = read_evolution()
    structure_plate(evo)
    houses_plate(panel, evo)
    growth_plate(panel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
