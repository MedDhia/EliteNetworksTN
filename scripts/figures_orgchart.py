"""The state's chain of command, and the governance that does not follow it.

Two relations, drawn together because neither is the whole picture.

**Line authority**, solid: the head of state, the head of government under him,
the ministries under that, and the bodies under each ministry. This is a tree
and it is what an organisation chart usually means.

**Co-governance**, dashed: a ministry holding a seat on a body's board. A
Tunisian public enterprise is run by a board carrying representatives of
several ministries at once — the Société tunisienne de l'électricité et du gaz
answers to six, the Agence Nationale des Fréquences to ten — so this relation
is many-to-many and cannot be a tree. 53% of the bodies governed this way have
more than one ministry on them. Forcing it into the tree would mean either
duplicating a company under every ministry that sits on it or picking one and
discarding the rest, and both misdescribe how the thing is actually run.

The solid/dashed pair is the ordinary organisation-chart convention for line
against functional authority, which is what these two relations are.

**Where each comes from.** The dashed edges are read off appointments: the
gazette writes a board seat as "membre représentant le ministère de
l'agriculture", and the ministry named there is the one taking part. Seats held
"représentant l'État" are for the state at large and carry no edge. The solid
edges below the ministries are reconstructed from the register as
``scripts/orgchart.py`` sets out. The solid edges *above* them — ministries
under the head of government, he under the head of state — are the one part of
this chart not read off the data at all: the gazette records appointments, not
the constitution. They are marked ``constitutional`` in the table and the note
says so.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from apparatus import MINISTRY_ENGLISH  # noqa: E402
from figstyle import (  # noqa: E402
    CAT4, ERA_RAMP, INK, MUTED, PROC, RULE, SOURCE, headline, plt, save,
)
from matplotlib.lines import Line2D  # noqa: E402

STATE = "STATE"
PRESIDENCY = "MIN:presidence_republique"
GOVERNMENT = "MIN:presidence_gouvernement"
STRUCTURAL = {"root", "canonical", "constitutional"}

LINE = CAT4[1]      # line authority
DOTTED = CAT4[0]    # co-governance

# Co-governed bodies drawn. Those with the most ministries on them: below three
# the pattern is a single supervising ministry and says nothing this figure is
# about.
MIN_MINISTRIES = 3
MAX_BODIES = 26


def load():
    h = pd.read_csv(PROC / "org_hierarchy.csv.gz", low_memory=False)
    c = pd.read_csv(PROC / "org_cogovernance.csv.gz", low_memory=False)
    h["name"] = h.name.fillna("")
    return h, c


def ministries(h: pd.DataFrame) -> list[dict]:
    """Every ministry with the count of bodies beneath it in the line tree."""
    kids = defaultdict(list)
    for o, p in zip(h.org_id, h.parent_id):
        if isinstance(p, str):
            kids[p].append(o)
    method = dict(zip(h.org_id, h.method))
    name = dict(zip(h.org_id, h.name))

    def below(root):
        n, stack = 0, list(kids.get(root, ()))
        while stack:
            x = stack.pop()
            if method.get(x) not in STRUCTURAL:
                n += 1
            stack.extend(kids.get(x, ()))
        return n

    out = []
    for oid, m in zip(h.org_id, h.method):
        if m != "constitutional" or oid == GOVERNMENT:
            continue
        out.append({"id": oid, "key": oid[4:], "name": name[oid],
                    "n": below(oid)})
    out.sort(key=lambda r: -r["n"])
    return out


def short(s: str, n: int) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1].rstrip(" ,;-") + "…"


def fig_orgchart() -> None:
    h, c = load()
    mins = ministries(h)

    # A ministry appearing as a co-governed body muddles the claim, which is
    # about the enterprises and agencies, so the column is restricted to them.
    c = c[c.body_form != "ministere"]
    per_body = c.groupby("org_id").ministry.nunique()
    keep = per_body[per_body >= MIN_MINISTRIES].sort_values(ascending=False)
    keep = keep.head(MAX_BODIES)
    bodies = (c[c.org_id.isin(keep.index)]
              .drop_duplicates("org_id")
              .set_index("org_id")
              .loc[keep.index])

    m_y = {r["key"]: i for i, r in enumerate(mins)}
    links = c[c.org_id.isin(keep.index) & c.ministry.isin(m_y)]

    # Order bodies by the average height of the ministries that govern them, so
    # the dashed lines cross as little as the data allows. The crossing that
    # remains is the finding.
    bary = links.groupby("org_id").ministry.apply(
        lambda x: np.mean([m_y[k] for k in x]))
    order = bary.sort_values().index.tolist()
    b_y = {oid: i for i, oid in enumerate(order)}

    fig, ax = plt.subplots(figsize=(15.0, 10.4))
    fig.subplots_adjust(top=0.775, bottom=0.075, left=0.012, right=0.988)
    ax.set_xlim(0, 1)
    ax.axis("off")

    n_m, n_b = len(mins), len(order)
    span = max(n_m, n_b)
    ax.set_ylim(span + 0.5, -5.0)
    MX, BX = 0.235, 0.615          # ministry column, body column
    m_pos = lambda i: i * (span / max(n_m - 1, 1)) * 0.995
    b_pos = lambda i: i * (span / max(n_b - 1, 1)) * 0.995

    # --- co-governance, behind everything ---
    for r in links.itertuples():
        y0, y1 = m_pos(m_y[r.ministry]), b_pos(b_y[r.org_id])
        ax.plot([MX + 0.145, BX - 0.006], [y0, y1], color=DOTTED,
                lw=0.55, ls=(0, (2.6, 2.0)), alpha=0.5, zorder=1)

    # --- the constitutional spine ---
    ax.annotate("Présidence de la République", xy=(0.012, -4.4),
                ha="left", va="center", fontsize=11.0, fontweight="bold",
                color=INK, zorder=5)
    ax.annotate("head of state", xy=(0.012, -3.85), ha="left", va="center",
                fontsize=7.4, color=MUTED, zorder=5)
    ax.plot([0.030, 0.030], [-3.55, -3.0], color=LINE, lw=1.4, zorder=3)
    ax.annotate("Présidence du gouvernement", xy=(0.048, -2.8),
                ha="left", va="center", fontsize=10.2, fontweight="bold",
                color=INK, zorder=5)
    ax.annotate("head of government — every ministry below answers to this office",
                xy=(0.048, -2.25), ha="left", va="center", fontsize=7.4,
                color=MUTED, zorder=5)
    # the bus down to the ministries
    ax.plot([0.066, 0.066], [-1.95, m_pos(n_m - 1)], color=LINE, lw=1.4,
            zorder=3)

    # --- ministries ---
    for r in mins:
        y = m_pos(m_y[r["key"]])
        ax.plot([0.066, MX - 0.004], [y, y], color=LINE, lw=0.9, zorder=3)
        ax.annotate(short(r["name"], 32), xy=(MX, y), ha="left", va="center",
                    fontsize=8.4, fontweight="bold", color=INK, zorder=5)
        ax.annotate(f"{r['n']:,}", xy=(MX + 0.138, y), ha="right",
                    va="center", fontsize=7.0, color=MUTED, zorder=5)

    # --- co-governed bodies ---
    for oid in order:
        y = b_pos(b_y[oid])
        k = int(per_body[oid])
        ax.plot([BX - 0.006], [y], "o", ms=3.4, color=DOTTED, zorder=4)
        ax.annotate(short(bodies.loc[oid, "body"], 62), xy=(BX + 0.006, y),
                    ha="left", va="center", fontsize=7.6, color=INK, zorder=5)
        ax.annotate(f"{k}", xy=(0.988, y), ha="right", va="center",
                    fontsize=7.4, color=DOTTED, fontweight="bold", zorder=5)

    ax.annotate("bodies beneath\nin the line tree", xy=(MX + 0.138, -1.25),
                ha="right", va="center", fontsize=7.0, color=MUTED,
                linespacing=1.4, zorder=5)
    ax.annotate("co-governed bodies — boards carrying several ministries",
                xy=(BX - 0.006, -1.25),
                ha="left", va="center", fontsize=8.2, color=INK,
                fontweight="bold", zorder=5)
    ax.annotate("ministries\non the board", xy=(0.988, -1.25), ha="right",
                va="center", fontsize=7.0, color=MUTED, linespacing=1.4,
                zorder=5)

    ax.legend(handles=[
        Line2D([], [], color=LINE, lw=1.6,
               label="line authority — answers to"),
        Line2D([], [], color=DOTTED, lw=1.2, ls=(0, (2.6, 2.0)),
               label="co-governance — holds a seat on the board"),
    ], loc="upper center", bbox_to_anchor=(0.5, -0.012), ncol=2, fontsize=8.4)

    n_multi = int((per_body > 1).sum())
    headline(
        fig,
        "The ministries answer to the head of government; the companies answer to several ministries at once",
        f"Solid lines are line authority: the head of state, the head of "
        f"government beneath him, the {len(mins)} ministries beneath that, and "
        f"the count of bodies under each. Dashed lines are a different "
        f"relation — a ministry holding a seat on a body's board, written in "
        f"the gazette as “membre représentant le ministère de …”. That "
        f"relation is many-to-many and no tree will hold it: of "
        f"{len(per_body):,} bodies governed this way, {n_multi:,} "
        f"({n_multi / len(per_body) * 100:.0f}%) have more than one ministry "
        f"on the board, and the {len(order)} drawn here are those with at "
        f"least {MIN_MINISTRIES}. The Société tunisienne de l'électricité et "
        f"du gaz carries six ministries, the Agence Nationale des Fréquences "
        f"ten. The crossing in the middle of the plate is the point: economic "
        f"governance in this state does not run down the chain of command, it "
        f"runs across it.",
        width=150,
    )
    save(fig, "fig35_state_organigram",
         SOURCE + "  Two relations, two sources. The dashed edges are read "
                  "from appointments: where the gazette records a board seat "
                  "as 'membre représentant le ministère de X', that ministry "
                  "is taking part in the body's governance; seats recorded as "
                  "'représentant l'État' are held for the state at large and "
                  "carry no edge, which is why 1,536 of the 3,023 "
                  "representation appointments are not drawn. The solid edges "
                  "below the ministries are reconstructed from the register — "
                  "neither the organisations table nor the gazette carries a "
                  "parent field, and the parent recorded on a spell belongs to "
                  "the act rather than the body, one body carrying 89 "
                  "different parents that way — so attachment is read from a "
                  "body's own name first, the commonest parent its acts give "
                  "it second, its portfolio third. The solid edges above the "
                  "ministries are not read off the data at all: the gazette "
                  "records appointments, not the constitution, and the "
                  "ordering of head of state, head of government and "
                  "ministries is imposed. It is marked constitutional in the "
                  "table so it can be filtered out. That ordering also moved "
                  "over the period — the 1959 constitution put the prime "
                  "minister well below a dominant president, 2014 made the "
                  "office genuinely semi-presidential, 2022 reduced it again, "
                  "and under the 2014 settlement defence and foreign affairs "
                  "answered to the President directly rather than through the "
                  "head of government. A union chart cannot draw a "
                  "relationship that changed three times, so it draws the "
                  "ordering that held throughout. Bodies are ordered by the "
                  "average position of the ministries governing them, which "
                  "minimises crossing; what crosses anyway is structure and "
                  "not layout. An explorable version carries every one of the "
                  "8,803 bodies in the line tree.")


def main() -> None:
    print("drawing…")
    fig_orgchart()
    print("done")


if __name__ == "__main__":
    main()
