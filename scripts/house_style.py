"""The project's figure house style: palette, page furniture, output.

Extracted so that more than one build can draw in the same style. The
constants are the ones ``scripts/figures.py`` established for the gazette
build; that file still defines its own copies, because it is 970 lines that
produce nine committed figures and rewiring it is a change worth making on its
own, with the figures regenerated and diffed. Anything new imports from here.

Colour, by the job it does
--------------------------
* **identity** -- person vs. institution is a two-slot categorical palette,
  ``#A03B2C`` / ``#1B5FC1``. Validated: lightness band, chroma floor, CVD
  separation (dE 23.6 protan, 26.6 tritan), normal-vision floor (dE 27.9) and
  contrast against the paper all pass.
* **magnitude** -- anything ordinal gets a single-hue sequential ramp,
  light to dark, never a set of unrelated hues.

Nothing is identified by colour alone: every figure carries direct labels or a
legend, and rank order is reinforced by size.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
FIGS = ROOT / "figures"

# --- palette ---------------------------------------------------------------
PERSON = "#A03B2C"
ORG = "#1B5FC1"
INK = "#1A1917"
MUTED = "#6C6D64"
RULE = "#D3D0C7"
PAPER = "#FCFCFB"

# Four-slot categorical palette for cohort comparisons; validated together
# (worst adjacent pair dE 23.6 protan, 22.3 tritan, 27.9 normal vision).
CAT4 = ["#A03B2C", "#1B5FC1", "#B5852A", "#5B4E9E"]
# Single-hue sequential ramp for era, light -> dark.
ERA_RAMP = ["#CBDCF2", "#92B5E3", "#5A8CD0", "#2F63B4", "#17408A"]
# Three steps of it, for a three-level ordinal split. Monotone in OKLab
# lightness (0.764 -> 0.508 -> 0.390, smallest step 0.118), which is what a
# sequential ramp is judged on rather than the categorical checks.
ERA3 = ["#92B5E3", "#2F63B4", "#17408A"]

# Matplotlib picks fonts per glyph from this list, so Latin resolves to DejaVu
# and Arabic falls through to Amiri, a naskh face that carries the joined forms.
#
# Arabic labels are passed **raw**. This matplotlib shapes and orders Arabic
# itself, so putting a string through arabic-reshaper and python-bidi first --
# the usual advice, and what this file did at first -- processes it twice and
# produces mangled, reversed text. The failure is silent: letters still appear,
# and only a reader of Arabic can see they are wrong. Tested against a word
# whose correct output is unambiguous (تونس: ت at the right, س at the left).
FONT_STACK = ["DejaVu Sans", "Amiri", "Noto Naskh Arabic"]
ARABIC_FONT = "Amiri"

plt.rcParams.update({
    "figure.facecolor": PAPER,
    "axes.facecolor": PAPER,
    "savefig.facecolor": PAPER,
    "font.family": FONT_STACK,
    "font.size": 8.5,
    "axes.edgecolor": RULE,
    "axes.labelcolor": INK,
    "axes.titlesize": 10,
    "axes.titleweight": "semibold",
    "axes.titlecolor": INK,
    "axes.titlelocation": "left",
    "axes.titlepad": 8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "xtick.labelcolor": MUTED,
    "ytick.labelcolor": MUTED,
    "xtick.major.size": 3,
    "ytick.major.size": 3,
    "grid.color": RULE,
    "grid.linewidth": 0.6,
    "legend.frameon": False,
    "legend.fontsize": 8,
    "pdf.fonttype": 42,
})


def headline(fig, title: str, subtitle: str, *, top: float = 0.99) -> None:
    """Title above subtitle, always, with space reserved for both."""
    fig.text(0.012, top, title, ha="left", va="top",
             fontsize=13.5, fontweight="bold", color=INK)
    fig.text(0.012, top - 0.036, subtitle, ha="left", va="top",
             fontsize=8.4, color=MUTED, wrap=True)


def save(fig, name: str, note: str | None = None) -> None:
    """Write both formats -- 300 dpi PNG for drafts, vector PDF for setting."""
    if note:
        fig.text(0.012, 0.012, note, ha="left", va="bottom",
                 fontsize=6.8, color=MUTED, wrap=True)
    FIGS.mkdir(parents=True, exist_ok=True)
    for ext, kw in (("png", {"dpi": 300}), ("pdf", {})):
        path = FIGS / f"{name}.{ext}"
        fig.savefig(path, bbox_inches="tight", pad_inches=0.24, **kw)
    plt.close(fig)
    print(f"  wrote figures/{name}.png and .pdf")


def stable(g):
    """A copy whose node and edge order does not depend on the process.

    Python hashes strings with a per-process seed, so iterating a set of node
    ids yields a different order on every run, and a force layout started from
    that order lands somewhere different every time. Sorting first makes the
    drawing reproducible.
    """
    import networkx as nx

    h = nx.DiGraph() if g.is_directed() else nx.Graph()
    h.add_nodes_from(sorted(g.nodes(data=True), key=lambda n: n[0]))
    h.add_edges_from(sorted(g.edges(data=True), key=lambda e: (e[0], e[1])))
    return h
