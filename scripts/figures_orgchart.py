"""The reconstructed state, drawn whole.

8,840 nodes will not fit on a page as an organisation chart in the usual
sense — boxes and connecting lines — so this is an icicle: depth runs left to
right, every body occupies a band whose height is the number of bodies beneath
it, and the state's shape is the silhouette. Nothing is dropped. Branches large
enough to label are labelled; the rest is the texture at the right-hand edge,
which is itself the finding — most of the register is two or three levels of
directorates and communes under a handful of ministries.

**Colour carries the evidence, not the ministry.** Every attachment in this
chart was inferred, and how it was inferred is the thing a reader most needs to
discount for. The ramp is ordinal — a body placed by its own name is better
evidenced than one placed by the parent its acts happen to name most often,
which is better than one placed by a portfolio alone — so it takes a
single-hue sequential ramp rather than four unrelated hues, per the house rule
for anything ordered.

**The union caveat is on the plate.** This is 1957–2026 at once and shows
bodies that never coexisted. The interactive version carries a year filter;
a static page cannot, so it says so instead.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from figstyle import (  # noqa: E402
    ERA_RAMP, INK, MUTED, PROC, RULE, SOURCE, headline, plt, save,
)
from matplotlib.patches import Patch, Rectangle  # noqa: E402

STATE = "STATE"

# Ordinal: how much the attachment is worth, weakest to strongest. A subset of
# the house sequential ramp, which stays monotone in lightness under subsetting
# because that is what a sequential ramp is; the categorical adjacency checks
# that govern CAT4 subsets do not apply to it.
EVIDENCE = [
    ("form", "nothing placed it", ERA_RAMP[0]),
    ("portfolio", "the portfolio it carries", ERA_RAMP[2]),
    ("modal_parent", "the parent its acts name", ERA_RAMP[3]),
    ("name", "its own name says so", ERA_RAMP[4]),
]
EV_COLOUR = {k: c for k, _, c in EVIDENCE}
# Structural nodes: the root and the canonical ministry tier are scaffolding
# this build put in, not bodies the register names, so they are drawn in the
# ink of the page rather than given an evidence colour they did not earn.
STRUCTURAL = {"root", "canonical"}

# Below this share of the column a label cannot be set without overlapping its
# neighbours, so the band is drawn unlabelled rather than crowded.
LABEL_MIN = 0.011


def load() -> pd.DataFrame:
    df = pd.read_csv(PROC / "org_hierarchy.csv.gz", low_memory=False)
    df["name"] = df.name.fillna("")
    return df


def measure(df: pd.DataFrame) -> dict:
    """Subtree size for every node, counting real bodies only.

    The canonical ministry tier would otherwise be counted twice — once as
    itself and once inside the register-named ministry under it.
    """
    kids: dict[str, list[str]] = {}
    for oid, pid in zip(df.org_id, df.parent_id):
        if isinstance(pid, str):
            kids.setdefault(pid, []).append(oid)
    real = {oid for oid, m in zip(df.org_id, df.method)
            if m not in STRUCTURAL}
    size: dict[str, int] = {}

    def walk(node: str) -> int:
        if node in size:
            return size[node]
        n = 1 if node in real else 0
        for k in kids.get(node, ()):
            n += walk(k)
        size[node] = n
        return n

    walk(STATE)
    return {"kids": kids, "size": size}


def layout(df: pd.DataFrame, m: dict, max_depth: int = 5) -> list[dict]:
    """Place every node as a band: x is depth, y is its share of the state."""
    info = df.set_index("org_id")
    total = float(m["size"][STATE]) or 1.0
    out: list[dict] = []

    def place(node: str, depth: int, y0: float, y1: float) -> None:
        r = info.loc[node]
        out.append({"id": node, "name": r["name"], "depth": depth,
                    "y0": y0, "y1": y1, "method": r["method"],
                    "size": m["size"][node], "form": r["form"]})
        if depth >= max_depth:
            return
        ks = sorted(m["kids"].get(node, ()),
                    key=lambda k: (-m["size"][k], info.loc[k, "name"]))
        span = y1 - y0
        # Children are laid out against the parent's own subtree size, so a
        # parent's band is never overrun by the sum of its children.
        denom = float(m["size"][node]) or 1.0
        cur = y0
        for k in ks:
            h = span * m["size"][k] / denom
            if h <= 0:
                continue
            place(k, depth + 1, cur, min(cur + h, y1))
            cur += h

    place(STATE, 0, 0.0, 1.0)
    return out


def short(name: str, n: int) -> str:
    name = " ".join(name.split())
    return name if len(name) <= n else name[: n - 1].rstrip(" ,;-") + "…"


def draw(ax, bands: list[dict], max_depth: int) -> None:
    colw = 1.0 / (max_depth + 1)
    for b in bands:
        x = b["depth"] * colw
        h = b["y1"] - b["y0"]
        colour = (INK if b["method"] in STRUCTURAL
                  else EV_COLOUR.get(b["method"], ERA_RAMP[0]))
        ax.add_patch(Rectangle(
            (x, b["y0"]), colw * 0.965, h,
            facecolor=colour, edgecolor="white",
            linewidth=0.25 if h > 0.002 else 0.0, zorder=2))
        if h >= LABEL_MIN and b["depth"] <= 3:
            # Dark bands take light type and vice versa; the ramp's midpoint
            # is between ERA_RAMP[2] and [3].
            light = b["method"] in STRUCTURAL or b["method"] in (
                "name", "modal_parent")
            ax.annotate(
                short(b["name"], int(52 * (h / 0.05)) if h < 0.05 else 60),
                xy=(x + colw * 0.03, (b["y0"] + b["y1"]) / 2),
                ha="left", va="center", zorder=4,
                fontsize=min(8.2, max(5.4, 150 * h)),
                color="white" if light else INK)
    ax.set_xlim(0, 1)
    ax.set_ylim(1, 0)
    ax.axis("off")

    for d, lab in enumerate(["the state", "ministry (canonical)",
                             "ministry as named", "body", "sub-body",
                             "deeper"][: max_depth + 1]):
        ax.annotate(lab, xy=(d * colw, -0.012), ha="left", va="bottom",
                    fontsize=7.4, color=MUTED, annotation_clip=False)


def fig_orgchart() -> None:
    df = load()
    m = measure(df)
    max_depth = 5
    bands = layout(df, m, max_depth)

    bodies = df[~df.method.isin(STRUCTURAL)]
    attached = int((bodies.parent_id != STATE).sum())
    by_method = bodies.method.value_counts()
    deepest = max(b["depth"] for b in bands)

    fig, ax = plt.subplots(figsize=(13.4, 9.6))
    fig.subplots_adjust(top=0.80, bottom=0.075, left=0.03, right=0.985)
    draw(ax, bands, max_depth)

    ax.legend(
        handles=[Patch(facecolor=c, label=lab) for _, lab, c in EVIDENCE]
        + [Patch(facecolor=INK, label="scaffolding of this reconstruction")],
        loc="upper center", bbox_to_anchor=(0.5, -0.035), ncol=5,
        title="how the attachment was established", fontsize=7.8)

    headline(
        fig,
        "The Tunisian state as the gazette records it, every body at once",
        f"{len(bodies):,} administrative bodies named in the Journal Officiel "
        f"between 1957 and 2026, each a band whose height is the number of "
        f"bodies beneath it. {attached / len(bodies) * 100:.0f}% attach to "
        f"something other than the bare state. The gazette publishes no parent "
        f"field, so every attachment here is inferred and the colour says from "
        f"what: {by_method.get('name', 0):,} from the body's own name, which "
        f"states it outright — “direction générale des services communs au "
        f"ministère de l'équipement” — {by_method.get('modal_parent', 0):,} "
        f"from the parent its appointment acts most often name, and "
        f"{by_method.get('portfolio', 0):,} from the portfolio it carries. The "
        f"{by_method.get('form', 0):,} that nothing placed are drawn against "
        f"the state rather than hidden. This is a union of seventy years and "
        f"shows bodies that never coexisted.",
        width=146,
    )
    save(fig, "fig35_state_organigram",
         SOURCE + "  The hierarchy is reconstructed: neither the "
                  "organisations table nor the gazette carries a parent field, "
                  "and the parent recorded on a spell belongs to the act the "
                  "appointment was published in rather than to the body — one "
                  "body carries 89 different parents that way. Attachment is "
                  "therefore read from the body's own name first, since "
                  "Tunisian administrative titles state what they hang off and "
                  "beat the act when the two disagree; from the commonest "
                  "parent its acts give it second, and only where at least 40% "
                  "of them agree; from its portfolio third. A separator alone "
                  "is not an attachment — the 'des' in direction générale des "
                  "impôts is ordinary French — so a name is only split where "
                  "the separator is followed by a word that names a body. "
                  "Where an act appoints a committee the whole membership list "
                  "can land in the name field, at a median 1,051 characters "
                  "against 72 for a real name, and each 'représentant du "
                  "ministère de X' in it reads as an attachment; those are cut "
                  "back before parsing. Successive names of one ministry "
                  "collapse onto a canonical node, so équipement, équipement "
                  "et habitat, and équipement, habitat et aménagement du "
                  "territoire are one branch and not three. Band height is the "
                  "count of bodies beneath, so a ministry supervising nine "
                  "hundred communes is wide whatever its staff; the canonical "
                  "tier and the root are this reconstruction's own scaffolding "
                  "rather than bodies the register names, and are drawn in ink "
                  f"rather than given an evidence colour. Depth runs to "
                  f"{deepest}. Bands below about one percent of a column are "
                  "drawn unlabelled rather than crowded. An explorable version "
                  "carries search, a year filter and the evidence behind each "
                  "attachment node by node.")


def main() -> None:
    print("drawing…")
    fig_orgchart()
    print("done")


if __name__ == "__main__":
    main()
