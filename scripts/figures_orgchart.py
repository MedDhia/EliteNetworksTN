"""The state's organisation chart, drawn as a chart of organisation.

A hierarchy is a node-link structure — who answers to whom — so it is drawn
with nodes and connectors, not as an area-filling partition. A treemap or an
icicle encodes *subtree size*, which answers "where is the mass" and not "what
reports to what"; the first version of this figure made that mistake.

**What a page can hold.** 8,803 bodies cannot all be boxes and lines at a
legible size: the register runs to 4,687 nodes at depth three alone, and a
node-link tree of them needs a wall, not a plate. So this draws the top of the
hierarchy properly — the state, every ministry, and the largest bodies under
each — and says in figures what it elides, rather than shrinking everything to
an unreadable size or silently dropping the tail. The explorable version
carries the rest.

**Colour still carries the evidence.** Every attachment was inferred, and the
marker beside each body says from what: its own name, the parent its
appointment acts name, or the portfolio it carries. That is an ordered
quantity and takes the house sequential ramp.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from figstyle import (  # noqa: E402
    ERA_RAMP, INK, MUTED, PROC, RULE, SOURCE, headline, plt, save,
)
from matplotlib.lines import Line2D  # noqa: E402

STATE = "STATE"
STRUCTURAL = {"root", "canonical"}

EVIDENCE = [
    ("name", "its own name says so", ERA_RAMP[4]),
    ("modal_parent", "the parent its acts name", ERA_RAMP[3]),
    ("portfolio", "the portfolio it carries", ERA_RAMP[2]),
    ("form", "nothing placed it", ERA_RAMP[0]),
]
EV_COLOUR = {k: c for k, _, c in EVIDENCE}

# Bodies shown under each ministry. Five is what fits beside thirty-six
# ministries on a page; the rest are counted, never dropped silently.
PER_MINISTRY = 5
COLUMNS = 2


def load():
    df = pd.read_csv(PROC / "org_hierarchy.csv.gz", low_memory=False)
    df["name"] = df.name.fillna("")
    kids = defaultdict(list)
    for o, p in zip(df.org_id, df.parent_id):
        if isinstance(p, str):
            kids[p].append(o)
    return df, kids


def gather(df: pd.DataFrame, kids) -> list[dict]:
    """Each ministry with the bodies beneath it, deepest branch first.

    Descent skips the canonical/register-name tier: that pair is this
    reconstruction's scaffolding for collapsing renamings, not a level of the
    state, and drawing it would put "MINISTERE DES FINANCES" under "Finance"
    as though the ministry reported to itself.
    """
    method = dict(zip(df.org_id, df.method))
    name = dict(zip(df.org_id, df.name))
    form = dict(zip(df.org_id, df.form))

    def below(root):
        out, stack = [], list(kids.get(root, ()))
        while stack:
            c = stack.pop()
            if method.get(c) not in STRUCTURAL:
                out.append(c)
            stack.extend(kids.get(c, ()))
        return out

    def sub(node):
        n, stack = 0, list(kids.get(node, ()))
        while stack:
            c = stack.pop()
            n += 1
            stack.extend(kids.get(c, ()))
        return n

    out = []
    for oid, m in zip(df.org_id, df.method):
        if m != "canonical":
            continue
        d = below(oid)
        # A ministry's direct bodies, ranked by how much hangs off them.
        direct = [c for c in d if method.get(c) != "canonical"
                  and any(c in kids.get(k, ()) for k in [oid] + [
                      x for x in kids.get(oid, ())])]
        ranked = sorted(direct, key=lambda c: (-sub(c), name.get(c, "")))
        out.append({
            "id": oid, "name": name[oid], "total": len(d),
            "children": [{"name": name[c], "n": sub(c),
                          "method": method.get(c, "form"),
                          "form": form.get(c, "")}
                         for c in ranked[:PER_MINISTRY]],
            "n_direct": len(direct),
        })
    out.sort(key=lambda r: -r["total"])
    return out


def short(s: str, n: int) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1].rstrip(" ,;-") + "…"


def draw_column(ax, rows, x0: float, y: float, row_h: float,
                width: float = 0.44) -> float:
    """Draw ministries down a spine; return the y reached."""
    spine_x = x0 + 0.028
    top = y
    for r in rows:
        # ministry node
        ax.plot([x0, spine_x - 0.004], [y, y], color=RULE, lw=0.9, zorder=2)
        ax.annotate(f"{short(r['name'], 40)}",
                    xy=(spine_x, y), ha="left", va="center",
                    fontsize=8.6, fontweight="bold", color=INK, zorder=4)
        ax.annotate(f"{r['total']:,} bodies",
                    xy=(x0 + width, y), ha="right", va="center",
                    fontsize=7.0, color=MUTED, zorder=4)
        y -= row_h

        # its own spine, down to the bodies beneath it
        kid_x = spine_x + 0.022
        branch_top = y + row_h * 0.5
        last = y
        for c in r["children"]:
            ax.plot([kid_x, kid_x + 0.014], [y, y], color=RULE, lw=0.7, zorder=2)
            ax.plot([kid_x + 0.0165], [y], "s", ms=3.1,
                    color=EV_COLOUR.get(c["method"], ERA_RAMP[0]), zorder=4)
            ax.annotate(short(c["name"], 62),
                        xy=(kid_x + 0.024, y), ha="left", va="center",
                        fontsize=7.2, color=INK, zorder=4)
            if c["n"]:
                ax.annotate(f"{c['n']:,}", xy=(x0 + width, y),
                            ha="right", va="center", fontsize=6.6,
                            color=MUTED, zorder=4)
            last = y
            y -= row_h
        rest = r["n_direct"] - len(r["children"])
        if rest > 0:
            ax.plot([kid_x, kid_x + 0.014], [y, y], color=RULE, lw=0.7, zorder=2)
            ax.annotate(f"+ {rest:,} more directly under this ministry",
                        xy=(kid_x + 0.024, y), ha="left", va="center",
                        fontsize=6.9, color=MUTED, style="italic", zorder=4)
            last = y
            y -= row_h
        if r["children"] or rest > 0:
            ax.plot([kid_x, kid_x], [branch_top, last], color=RULE, lw=0.7,
                    zorder=1)
        y -= row_h * 0.42
    ax.plot([x0, x0], [top, y + row_h * 0.42], color=RULE, lw=0.9, zorder=1)
    return y


def fig_orgchart() -> None:
    df, kids = load()
    mins = gather(df, kids)
    bodies = df[~df.method.isin(STRUCTURAL)]
    unplaced = int(((df.parent_id == STATE) & ~df.method.isin(STRUCTURAL)).sum())
    by_method = bodies.method.value_counts()

    half = (len(mins) + 1) // 2
    cols = [mins[:half], mins[half:]]
    rows_needed = max(sum(1 + len(r["children"])
                          + (1 if r["n_direct"] > len(r["children"]) else 0)
                          for r in c) for c in cols)
    row_h = 1.0 / (rows_needed + len(cols[0]) + 4)

    fig, ax = plt.subplots(figsize=(14.6, 15.2))
    fig.subplots_adjust(top=0.885, bottom=0.045, left=0.015, right=0.985)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # The root, and a bus across to both columns: every ministry descends from
    # it, and drawing thirty-six lines across the plate would say the same
    # thing far less clearly.
    ax.annotate("État tunisien", xy=(0.5, 0.985), ha="center", va="center",
                fontsize=12.5, fontweight="bold", color=INK, zorder=5)
    ax.annotate(f"{len(bodies):,} bodies, 1957–2026",
                xy=(0.5, 0.962), ha="center", va="center", fontsize=7.8,
                color=MUTED, zorder=5)
    ax.plot([0.5, 0.5], [0.953, 0.944], color=RULE, lw=1.0)
    ax.plot([0.028, 0.520], [0.944, 0.944], color=RULE, lw=1.0)
    ax.plot([0.028, 0.028], [0.944, 0.936], color=RULE, lw=1.0)
    ax.plot([0.520, 0.520], [0.944, 0.936], color=RULE, lw=1.0)

    draw_column(ax, cols[0], 0.028, 0.936, row_h)
    draw_column(ax, cols[1], 0.520, 0.936, row_h)

    ax.legend(handles=[Line2D([], [], marker="s", ls="", ms=6, color=c,
                              label=lab) for _, lab, c in EVIDENCE],
              loc="lower center", bbox_to_anchor=(0.5, -0.028), ncol=4,
              title="how each attachment was established", fontsize=7.6)

    headline(
        fig,
        "The Tunisian state, ministry by ministry",
        f"Every ministry the Journal Officiel records between 1957 and 2026, "
        f"with the five bodies beneath each that carry the most below them, "
        f"and a count of the rest. {len(bodies):,} bodies in all. The gazette "
        f"publishes no parent field, so every attachment here is inferred and "
        f"the marker says from what: {by_method.get('name', 0):,} from the "
        f"body's own name, which states it outright — “direction générale des "
        f"services communs au ministère de l'équipement” — "
        f"{by_method.get('modal_parent', 0):,} from the parent its appointment "
        f"acts most often name, {by_method.get('portfolio', 0):,} from the "
        f"portfolio it carries. A further {unplaced:,} bodies are not drawn "
        f"here because nothing placed them under any ministry. Successive "
        f"names of one ministry are collapsed, so équipement and équipement et "
        f"habitat are one row rather than two. This is a union of seventy "
        f"years: the ministries listed never all existed at once.",
        width=150,
    )
    save(fig, "fig35_state_organigram",
         SOURCE + "  The hierarchy is reconstructed: neither the "
                  "organisations table nor the gazette carries a parent field, "
                  "and the parent recorded on a spell belongs to the act the "
                  "appointment was published in rather than to the body — one "
                  "body carries 89 different parents that way. Attachment is "
                  "read from the body's own name first, since Tunisian "
                  "administrative titles state what they hang off and beat the "
                  "act where the two disagree; from the commonest parent its "
                  "acts give it second, and only where at least 40% of them "
                  "agree; from its portfolio third. A separator alone is not "
                  "an attachment — the 'des' in direction générale des impôts "
                  "is ordinary French — so a name is only split where the "
                  "separator is followed by a word that names a body. Where an "
                  "act appoints a committee the whole membership list can land "
                  "in the name field, at a median 1,051 characters against 72 "
                  "for a real name, and each 'représentant du ministère de X' "
                  "in it reads as an attachment; those are cut back before "
                  "parsing. The count beside a body is everything beneath it, "
                  "at any depth. Ministries are ordered by how much hangs off "
                  "them and bodies within a ministry likewise, so the five "
                  "shown are the largest branches and not the whole of what a "
                  "ministry directly holds. The full register runs to 4,687 "
                  "bodies at depth three alone, which no node-link chart can "
                  "set legibly on a page; an explorable version carries every "
                  "node, with search, a year filter and the evidence behind "
                  "each attachment.")


def main() -> None:
    print("drawing…")
    fig_orgchart()
    print("done")


if __name__ == "__main__":
    main()
