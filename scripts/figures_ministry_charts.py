"""One organisation chart per ministry, as a multi-page plate.

Thirty-six ministries, thirty-six pages, written to a single PDF so the set
stays one artefact and a reader can page through it.

**Why not one template applied thirty-six times.** The ministries are not
alike enough. Interior holds 1,108 bodies of which 696 are communes and
governorates — a territorial network, not a central administration — while
Communications holds nineteen bodies in a single flat layer and Planning five.
A page that draws Interior's tree at a legible size leaves Planning as four
lines in a corner, and one that suits Planning cannot hold Interior at all. So
each page groups by the kind of body and sizes itself to what the ministry
actually has, drawing what fits and counting the rest.

**The groups are the structure.** A directorate, a governorate, a public
enterprise and a court are four different relations to a ministry: the first
is part of it, the second is territory it administers, the third a company it
governs, the fourth a jurisdiction it supervises without owning. Sorting them
into one list ordered by size would bury that distinction, which for the
interior ministry is the single most important thing about it.

**Each page also carries what the tree cannot.** The titles the register used
for the ministry over seventy years, which is its merger and renaming history;
and the boards it sits on, which is authority running sideways rather than
down.
"""

from __future__ import annotations

import sys
import textwrap
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from figstyle import (  # noqa: E402
    CAT4, FIGS, INK, MUTED, PROC, RULE, plt,
)
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

GOVERNMENT = "MIN:presidence_gouvernement"
STRUCTURAL = {"root", "canonical", "constitutional"}

LINE = CAT4[1]
DOTTED = CAT4[0]

# The kinds of body a ministry can hold, in the order a reader should meet
# them: what it is made of, then what it administers, then what it governs at
# arm's length, then what it merely supervises.
GROUPS = [
    ("Central administration", {"direction", "autre"}, 14),
    ("Territorial administration", {"gouvernorat", "commune"}, 10),
    ("Public enterprises and agencies", {"entreprise_publique", "banque"}, 10),
    ("Courts", {"juridiction"}, 6),
    ("Universities, institutes and hospitals",
     {"universite", "etablissement_sante"}, 8),
    ("Independent authorities", {"instance_independante"}, 5),
]


def load():
    h = pd.read_csv(PROC / "org_hierarchy.csv.gz", low_memory=False)
    c = pd.read_csv(PROC / "org_cogovernance.csv.gz", low_memory=False)
    h["name"] = h.name.fillna("")
    return h, c


def index(h: pd.DataFrame):
    kids = defaultdict(list)
    for o, p in zip(h.org_id, h.parent_id):
        if isinstance(p, str):
            kids[p].append(o)
    return {
        "kids": kids,
        "name": dict(zip(h.org_id, h.name)),
        "form": dict(zip(h.org_id, h.form)),
        "method": dict(zip(h.org_id, h.method)),
        "y0": dict(zip(h.org_id, h.first_year)),
        "y1": dict(zip(h.org_id, h.last_year)),
    }


def descendants(root, ix):
    """Everything under a ministry, stopping where another office begins.

    The constitutional spine makes every ministry a descendant of the head of
    government and so of the head of state, which is true and useless here: a
    walk that descends through those nodes gives the Presidency of the Republic
    all 7,673 bodies in the state and files the tax directorate under it. So
    the walk does not enter a node that is itself an office — it reports what
    this ministry holds, not what the state holds beneath it.
    """
    out, stack = [], [c for c in ix["kids"].get(root, ())
                      if ix["method"].get(c) not in STRUCTURAL]
    while stack:
        c = stack.pop()
        out.append(c)
        stack.extend(k for k in ix["kids"].get(c, ())
                     if ix["method"].get(k) not in STRUCTURAL)
    return out


def sub_size(node, ix):
    n, stack = 0, list(ix["kids"].get(node, ()))
    while stack:
        c = stack.pop()
        n += 1
        stack.extend(ix["kids"].get(c, ()))
    return n


def short(s, n):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1].rstrip(" ,;-") + "…"


def years(oid, ix):
    a, b = ix["y0"].get(oid), ix["y1"].get(oid)
    if pd.isna(a) or pd.isna(b):
        return ""
    a, b = int(a), int(b)
    return str(a) if a == b else f"{a}–{b}"


def draw_page(pdf, mid, ix, cog):
    name = ix["name"][mid]
    # Only bodies that are themselves ministries. A court named "cour d'appel
    # de Tunis détaché au Ministère de l'Intérieur" resolves under interior but
    # is a court seconded to it, not a title the ministry went by.
    titles = [c for c in ix["kids"].get(mid, ())
              if ix["method"].get(c) not in STRUCTURAL
              and ix["form"].get(c) == "ministere"]
    every = descendants(mid, ix)
    by_form = defaultdict(list)
    for c in every:
        by_form[ix["form"].get(c, "autre")].append(c)

    fig = plt.figure(figsize=(13.2, 9.0))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.annotate(name, xy=(0.030, 0.955), ha="left", va="center",
                fontsize=19, fontweight="bold", color=INK)
    seats = cog[cog.ministry == mid[4:]]
    bits = [f"{len(every):,} bodies"]
    if titles:
        bits.append(f"{len(titles)} title{'s' if len(titles) != 1 else ''} in the register")
    if len(seats):
        bits.append(f"seats on {seats.org_id.nunique()} other bodies' boards")
    ax.annotate("   ·   ".join(bits), xy=(0.030, 0.920), ha="left",
                va="center", fontsize=9.2, color=MUTED)
    ax.plot([0.030, 0.970], [0.902, 0.902], color=RULE, lw=1.0)

    # ---- left: the line tree, grouped by what kind of body it is ----
    y = 0.868
    x = 0.030
    ROW = 0.0205
    COL_W = 0.60
    drawn_any = False
    for label, forms, cap in GROUPS:
        members = [c for f in forms for c in by_form.get(f, ())]
        if not members:
            continue
        drawn_any = True
        members.sort(key=lambda c: (-sub_size(c, ix), ix["name"].get(c, "")))
        seen_names, unique = set(), []
        for c in members:
            k = " ".join(str(ix["name"].get(c, "")).split()).lower()
            if k in seen_names:
                continue
            seen_names.add(k)
            unique.append(c)
        ax.annotate(f"{label}", xy=(x, y), ha="left", va="center",
                    fontsize=8.4, fontweight="bold", color=INK)
        ax.annotate(f"{len(members):,}", xy=(x + COL_W, y), ha="right",
                    va="center", fontsize=8.0, color=MUTED)
        y -= ROW * 0.95
        spine_top = y + ROW * 0.45
        last = y
        for c in unique[:cap]:
            ax.plot([x + 0.012, x + 0.026], [y, y], color=LINE, lw=0.7)
            ax.annotate(short(ix["name"].get(c, ""), 74),
                        xy=(x + 0.032, y), ha="left", va="center",
                        fontsize=7.4, color=INK)
            n = sub_size(c, ix)
            tag = years(c, ix)
            if n:
                tag = f"{n:,} below   {tag}" if tag else f"{n:,} below"
            if tag:
                ax.annotate(tag, xy=(x + COL_W, y), ha="right", va="center",
                            fontsize=6.6, color=MUTED)
            last = y
            y -= ROW
            if y < 0.135:
                break
        rest = len(members) - min(cap, len(unique))
        if rest > 0:
            ax.plot([x + 0.012, x + 0.026], [y, y], color=LINE, lw=0.7)
            ax.annotate(f"+ {rest:,} more", xy=(x + 0.032, y), ha="left",
                        va="center", fontsize=7.0, color=MUTED, style="italic")
            last = y
            y -= ROW
        ax.plot([x + 0.012, x + 0.012], [spine_top, last], color=LINE, lw=0.7)
        y -= ROW * 0.5
        if y < 0.155:
            break
    if not drawn_any:
        ax.annotate("No bodies are attached to this ministry in the register.",
                    xy=(x, y), ha="left", va="center", fontsize=8.4,
                    color=MUTED, style="italic")

    # ---- right: titles used, and boards sat on ----
    rx, ry = 0.655, 0.868
    ax.annotate("Titles the register used", xy=(rx, ry), ha="left",
                va="center", fontsize=8.4, fontweight="bold", color=INK)
    ry -= ROW * 0.95
    if titles:
        titles.sort(key=lambda c: (ix["y0"].get(c, 9999), ix["name"].get(c, "")))
        for c in titles[:11]:
            ax.annotate(short(ix["name"].get(c, ""), 52), xy=(rx + 0.006, ry),
                        ha="left", va="center", fontsize=7.2, color=INK)
            ax.annotate(years(c, ix), xy=(0.970, ry), ha="right", va="center",
                        fontsize=6.6, color=MUTED)
            ry -= ROW
        if len(titles) > 11:
            ax.annotate(f"+ {len(titles) - 11} more", xy=(rx + 0.006, ry),
                        ha="left", va="center", fontsize=7.0, color=MUTED,
                        style="italic")
            ry -= ROW
    else:
        ax.annotate("none recorded under this name", xy=(rx + 0.006, ry),
                    ha="left", va="center", fontsize=7.2, color=MUTED,
                    style="italic")
        ry -= ROW
    ry -= ROW * 0.6

    ax.annotate("Boards this ministry sits on", xy=(rx, ry), ha="left",
                va="center", fontsize=8.4, fontweight="bold", color=DOTTED)
    ry -= ROW * 0.95
    if len(seats):
        top = (seats.groupby(["org_id", "body"]).seats.sum()
               .reset_index().sort_values("seats", ascending=False))
        for r in top.head(12).itertuples():
            ax.plot([rx + 0.004, rx + 0.018], [ry, ry], color=DOTTED, lw=0.7,
                    ls=(0, (2.2, 1.8)))
            ax.annotate(short(r.body, 52), xy=(rx + 0.024, ry), ha="left",
                        va="center", fontsize=7.2, color=INK)
            ax.annotate(f"{int(r.seats)}", xy=(0.970, ry), ha="right",
                        va="center", fontsize=6.6, color=MUTED)
            ry -= ROW
        if len(top) > 12:
            ax.annotate(f"+ {len(top) - 12} more", xy=(rx + 0.024, ry),
                        ha="left", va="center", fontsize=7.0, color=MUTED,
                        style="italic")
    else:
        ax.annotate("none recorded", xy=(rx + 0.006, ry), ha="left",
                    va="center", fontsize=7.2, color=MUTED, style="italic")

    ax.annotate(
        textwrap.fill(
            "Journal Officiel de la République Tunisienne, 1957–2026. "
            "Hierarchy reconstructed — the gazette carries no parent field; "
            "see fig35 and scripts/orgchart.py. A union of seventy years: "
            "these bodies did not all exist at once, and the ministry itself "
            "was titled differently at different times. “Below” counts "
            "everything beneath a body at any depth. Board seats are "
            "appointments recorded as “représentant le ministère de …”. "
            "Bodies belonging to another ministry are not counted here even "
            "where the constitutional spine puts them below this office.",
            186),
        xy=(0.030, 0.022), ha="left", va="bottom", fontsize=6.3, color=MUTED,
        linespacing=1.5)
    pdf.savefig(fig)
    plt.close(fig)


def main() -> None:
    print("loading…")
    h, c = load()
    ix = index(h)
    # Both presidencies get a page too: they are offices with bodies under
    # them, not just the top of the spine.
    mins = [(oid, len(descendants(oid, ix)))
            for oid in h.org_id
            if isinstance(oid, str) and oid.startswith("MIN:")]
    mins.sort(key=lambda r: -r[1])

    out = FIGS / "fig36_ministry_charts.pdf"
    print(f"drawing {len(mins)} pages…")
    with PdfPages(out) as pdf:
        for oid, _ in mins:
            draw_page(pdf, oid, ix, c)
        d = pdf.infodict()
        # No creation date, so an unchanged rebuild is byte-identical, as the
        # single-figure plates in this repository already are.
        d["Title"] = "Tunisian ministries: organisation charts"
        d["CreationDate"] = None
    print(f"  wrote {out.relative_to(FIGS.parent)}  "
          f"({out.stat().st_size / 1024:.0f} KB, {len(mins)} pages)")


if __name__ == "__main__":
    main()
