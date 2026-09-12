"""Shared drawing conventions for the JORT figures.

Kept in one module so that every figure in the repository agrees on colour,
type and page furniture. ``scripts/figures.py`` predates this file and still
carries its own copy of these constants; the values here are identical to it,
and the two should be kept in step until that script is moved across.

Colour
------
Two jobs, two treatments:

* **identity** - unordered categories get a categorical palette whose members
  are validated against one another for colour-vision deficiency, chroma and
  contrast on the paper surface.
* **magnitude** - anything ordinal (seniority, era) gets a single-hue
  sequential ramp light-to-dark, never a set of unrelated hues.

Nothing is ever identified by colour alone: every figure carries direct labels
or a legend, and ordering is reinforced by position or size.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
FIGS = ROOT / "figures"
FIGS.mkdir(exist_ok=True)

# --- palette ---------------------------------------------------------------
PERSON = "#A03B2C"
ORG = "#1B5FC1"
INK = "#1A1917"
MUTED = "#6C6D64"
RULE = "#D3D0C7"
PAPER = "#FCFCFB"

# Four-slot categorical palette, validated together (worst adjacent pair
# dE 23.6 protan, 22.3 tritan, 27.9 normal vision).
CAT4 = ["#A03B2C", "#1B5FC1", "#B5852A", "#5B4E9E"]

# The three ruptures are unordered categories, so they take categorical slots
# rather than a ramp. Fixed here so a given rupture keeps its colour in every
# figure that shows all three.
RUPTURE_COLOUR = {"1987": CAT4[0], "2011": CAT4[1], "2021": CAT4[3]}

ERA_RAMP = ["#CBDCF2", "#92B5E3", "#5A8CD0", "#2F63B4", "#17408A"]
RANK_RAMP = ["#F0C7BC", "#DE9683", "#C4634C", "#9C3626", "#63160F"]

plt.rcParams.update({
    "figure.facecolor": PAPER,
    "axes.facecolor": PAPER,
    "savefig.facecolor": PAPER,
    "font.family": "DejaVu Sans",
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

SOURCE = ("Source: Journal Officiel de la République Tunisienne, 1957–2026 "
          "(6,378 French issues, jort.tn). Author's extraction.")


def headline(fig, title: str, subtitle: str, *, top: float = 0.99,
             width: int = 118) -> None:
    """Title above subtitle, always, with space reserved for both.

    The subtitle is wrapped here rather than left to Matplotlib's ``wrap=True``,
    which measures against the figure but is applied after ``bbox_inches="tight"``
    has already decided how wide the canvas is. A long unwrapped subtitle
    therefore stretches the saved page instead of folding, which is what turned
    several of these figures into letterbox strips.
    """
    fig.text(0.012, top, title, ha="left", va="top",
             fontsize=13.5, fontweight="bold", color=INK)
    fig.text(0.012, top - 0.045, textwrap.fill(subtitle, width),
             ha="left", va="top", fontsize=8.4, color=MUTED, linespacing=1.45)


def save(fig, name: str, note: str | None = None) -> None:
    """Write a 300-dpi PNG for drafts and a vector PDF for typesetting."""
    if note:
        fig.text(0.012, -0.012, textwrap.fill(note, 150), fontsize=6.6,
                 color=MUTED, ha="left", va="top", linespacing=1.5)
    for ext, kw in (("png", {"dpi": 300}), ("pdf", {})):
        path = FIGS / f"{name}.{ext}"
        fig.savefig(path, bbox_inches="tight", pad_inches=0.24, **kw)
        print(f"  {path.relative_to(ROOT)}  {path.stat().st_size / 1024:.0f} KB")
    plt.close(fig)
