"""A structural guide to the Tunisian state apparatus.

A reference document rather than a plate: every body the register places under
every ministry, nested as it is nested, with what is known about each. Length
follows the material — a ministry with six hundred bodies gets the pages it
needs.

**What is left out, and why.** Communes and governorates are excluded, with
everything beneath them: 1,436 bodies, of which 1,108 hang off the interior
ministry alone. They are territorial administration, and the posts inside them
are overwhelmingly local rather than national. The exclusion is worth being
precise about, because it is not quite free — a *gouverneur* scores 80 on the
codebook's rank scale and is unambiguously an elite post. What goes out is the
governorate as an organisational branch, not the governor as an official; the
appointment record still holds every governor, and fig29 treats their
recruitment directly. Interior falls from 1,108 bodies to 257 as a result,
which is itself the finding: three-quarters of that ministry, as the gazette
records it, is territory.

**What each entry carries.** The name as the register writes it; what kind of
body it is; the years it appears; how many people served in it and how many
appointment acts name it; and the evidence for its placement in the tree,
since the hierarchy is reconstructed and not every attachment is worth the
same. Children are indented under parents to whatever depth the register
states.

**What the tree cannot carry, and each section adds.** The titles a ministry
went by, which is its merger and renaming history — Interior appears under
three, Economy under nine. The boards it holds seats on, which is authority
running sideways rather than down. And the ministries that hold seats on
*its* bodies, which is the same relation seen from the other end and is how a
reader finds out who else has a say in a ministry's enterprises.
"""

from __future__ import annotations

import sys
import textwrap
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from apparatus import MINISTRY_ENGLISH  # noqa: E402

# The canonical node for posts whose portfolio names no ministry. It is not an
# office and must not sit in the contents looking like one, but it holds 42
# bodies and a thousand people and is not dropped either.
LABEL = {"autre": "Unattributed portfolio (not a ministry)"}
from figstyle import (  # noqa: E402
    CAT4, ERA_RAMP, FIGS, INK, MUTED, PROC, RULE, plt,
)
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

GOVERNMENT = "MIN:presidence_gouvernement"
PRESIDENCY = "MIN:presidence_republique"
STRUCTURAL = {"root", "canonical", "constitutional"}
TERRITORIAL = {"gouvernorat", "commune"}

LINE = CAT4[1]
DOTTED = CAT4[0]

EVIDENCE = {
    "name": ("its own name states the attachment", ERA_RAMP[4]),
    "modal_parent": ("the parent its appointment acts name", ERA_RAMP[3]),
    "portfolio": ("the portfolio it carries", ERA_RAMP[2]),
    "form": ("nothing placed it; it sits at the top level", ERA_RAMP[0]),
    "cycle_cut": ("cut loose to break a cycle", ERA_RAMP[0]),
}

KIND = {
    "direction": "directorate", "autre": "body", "juridiction": "court",
    "entreprise_publique": "enterprise", "universite": "university",
    "etablissement_sante": "health", "ministere": "ministry",
    "banque": "bank", "instance_independante": "authority",
    "gouvernorat": "governorate", "commune": "commune",
    "presidence": "presidency",
}

# Page geometry. One column of rows; the document is meant to be read, not
# fitted to a slide.
PAGE = (11.7, 16.5)          # tall, so a long branch stays on one page
TOP, BOTTOM = 0.955, 0.045
ROW = 0.0132
X_NAME, X_KIND, X_YEARS, X_PEOPLE, X_ACTS, X_EV = (
    0.035, 0.605, 0.700, 0.800, 0.868, 0.930)


def load():
    h = pd.read_csv(PROC / "org_hierarchy.csv.gz", low_memory=False)
    c = pd.read_csv(PROC / "org_cogovernance.csv.gz", low_memory=False)
    h["name"] = h.name.fillna("")
    return h, c


def index(h):
    kids = defaultdict(list)
    for o, p in zip(h.org_id, h.parent_id):
        if isinstance(p, str):
            kids[p].append(o)
    g = lambda col: dict(zip(h.org_id, h[col]))  # noqa: E731
    return {"kids": kids, "name": g("name"), "form": g("form"),
            "method": g("method"), "conf": g("confidence"),
            "y0": g("first_year"), "y1": g("last_year"),
            "np": g("n_persons"), "ne": g("n_events")}


def walk(root, ix, depth=0):
    """Every body under ``root``, nested, territorial branches pruned."""
    out = []
    children = [c for c in ix["kids"].get(root, ())
                if ix["method"].get(c) not in STRUCTURAL
                and ix["form"].get(c) not in TERRITORIAL]
    children.sort(key=lambda c: (-subtree(c, ix), str(ix["name"].get(c, ""))))
    for c in children:
        out.append((c, depth))
        out.extend(walk(c, ix, depth + 1))
    return out


def subtree(node, ix):
    n, stack = 0, [node]
    while stack:
        x = stack.pop()
        for k in ix["kids"].get(x, ()):
            if (ix["method"].get(k) in STRUCTURAL
                    or ix["form"].get(k) in TERRITORIAL):
                continue
            n += 1
            stack.append(k)
    return n


def num(v):
    return "" if pd.isna(v) else f"{int(v):,}"


def years(oid, ix):
    a, b = ix["y0"].get(oid), ix["y1"].get(oid)
    if pd.isna(a) or pd.isna(b):
        return ""
    a, b = int(a), int(b)
    return str(a) if a == b else f"{a}–{b}"


def short(s, n):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1].rstrip(" ,;-") + "…"


class Doc:
    """A paginating writer: rows go on until the page ends, then it turns."""

    def __init__(self, pdf):
        self.pdf = pdf
        self.fig = None
        self.n = 0
        self.running = ""

    def page(self, running=None):
        self.close()
        if running is not None:
            self.running = running
        self.fig = plt.figure(figsize=PAGE)
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, 1)
        self.ax.set_ylim(0, 1)
        self.ax.axis("off")
        self.y = TOP
        self.n += 1
        if self.running:
            self.ax.annotate(self.running, xy=(0.035, 0.982), ha="left",
                             va="center", fontsize=7.0, color=MUTED)
            self.ax.annotate(f"{self.n}", xy=(0.965, 0.982), ha="right",
                             va="center", fontsize=7.0, color=MUTED)
            self.ax.plot([0.035, 0.965], [0.972, 0.972], color=RULE, lw=0.6)
        return self.ax

    def close(self):
        if self.fig is not None:
            self.pdf.savefig(self.fig)
            plt.close(self.fig)
            self.fig = None

    def room(self, need=1):
        if self.y - need * ROW < BOTTOM:
            self.page()

    def gap(self, k=1.0):
        self.y -= ROW * k


def column_heads(d):
    a = d.ax
    for x, t, ha in ((X_NAME, "body", "left"), (X_KIND, "kind", "left"),
                     (X_YEARS, "recorded", "left"), (X_PEOPLE, "people", "right"),
                     (X_ACTS, "acts", "right"), (X_EV, "placed by", "left")):
        a.annotate(t, xy=(x, d.y), ha=ha, va="center", fontsize=6.2,
                   color=MUTED)
    d.gap(0.75)
    a.plot([0.035, 0.965], [d.y + ROW * 0.3, d.y + ROW * 0.3], color=RULE,
           lw=0.5)


def body_row(d, oid, depth, ix):
    d.room(1)
    a = d.ax
    ind = X_NAME + depth * 0.016
    if depth:
        a.plot([ind - 0.010, ind - 0.003], [d.y, d.y], color=RULE, lw=0.55)
    a.annotate(short(ix["name"].get(oid, ""), max(20, 96 - depth * 3)),
               xy=(ind, d.y), ha="left", va="center",
               fontsize=7.1 if depth == 0 else 6.8,
               color=INK, fontweight="bold" if depth == 0 else "normal")
    a.annotate(KIND.get(ix["form"].get(oid), ix["form"].get(oid, "")),
               xy=(X_KIND, d.y), ha="left", va="center", fontsize=6.4,
               color=MUTED)
    a.annotate(years(oid, ix), xy=(X_YEARS, d.y), ha="left", va="center",
               fontsize=6.4, color=MUTED)
    a.annotate(num(ix["np"].get(oid)), xy=(X_PEOPLE, d.y), ha="right",
               va="center", fontsize=6.4, color=MUTED)
    a.annotate(num(ix["ne"].get(oid)), xy=(X_ACTS, d.y), ha="right",
               va="center", fontsize=6.4, color=MUTED)
    m = ix["method"].get(oid, "form")
    a.plot([X_EV + 0.004], [d.y], "s", ms=2.6,
           color=EVIDENCE.get(m, EVIDENCE["form"])[1])
    d.gap()


def front_matter(d, h, c, ix, mins, dropped, starts):
    a = d.page("")
    a.annotate("The Tunisian State Apparatus", xy=(0.035, 0.905), ha="left",
               va="center", fontsize=27, fontweight="bold", color=INK)
    a.annotate("A structural guide, 1957–2026", xy=(0.035, 0.868), ha="left",
               va="center", fontsize=13, color=MUTED)
    a.plot([0.035, 0.965], [0.845, 0.845], color=INK, lw=1.2)
    d.y = 0.815

    total = sum(n for _, n in mins)
    for para in [
        f"Every administrative body the Journal Officiel de la République "
        f"Tunisienne places under a ministry between 1957 and 2026: "
        f"{total:,} of them, nested as the register nests them, under "
        f"{len(mins)} offices. Each is given with what is known about it — "
        f"the years it appears, how many people served in it, how many "
        f"appointment acts name it, and the evidence for where it sits.",

        f"Territorial administration is excluded: {dropped:,} communes and "
        f"governorates, with everything beneath them. They are local rather "
        f"than national, and the interior ministry falls from 1,108 bodies to "
        f"257 without them, which is itself worth knowing — three-quarters of "
        f"that ministry, as the gazette records it, is territory. One caveat "
        f"is owed: a gouverneur scores 80 on the codebook's rank scale and is "
        f"an elite post by any measure. What is excluded here is the "
        f"governorate as an organisational branch, not the governor as an "
        f"official; the appointment record holds every one of them.",

        "The hierarchy is reconstructed. Neither the organisations table nor "
        "the gazette carries a parent field, and the parent recorded against "
        "an appointment belongs to the act it was published in rather than to "
        "the body — one body carries 89 different parents that way. So a "
        "body's placement is read from its own name first, since Tunisian "
        "administrative titles state what they hang off; from the parent its "
        "acts most often name second, and only where at least two in five "
        "agree; from the portfolio it carries third. The mark at the right of "
        "every row says which, and they are not worth the same.",

        "The ordering of head of state, head of government and ministries is "
        "the one part not read from the data at all. The gazette records "
        "appointments, not the constitution. That ordering also moved over "
        "the period — 1959 put a prime minister well below a dominant "
        "president, 2014 made the office genuinely semi-presidential, 2022 "
        "reduced it again, and under the 2014 settlement defence and foreign "
        "affairs answered to the President directly.",

        "This is a union of seventy years. The bodies listed under a ministry "
        "did not all exist at once, and neither did the ministries: successive "
        "names of one office are collapsed onto a single entry, whose titles "
        "over time open each section.",
    ]:
        for line in textwrap.wrap(para, 150):
            d.room()
            a.annotate(line, xy=(0.035, d.y), ha="left", va="center",
                       fontsize=8.3, color=INK)
            d.gap(1.18)
        d.gap(0.8)

    d.gap(0.6)
    a.annotate("How to read an entry", xy=(0.035, d.y), ha="left",
               va="center", fontsize=10, fontweight="bold", color=INK)
    d.gap(1.6)
    for k, (desc, col) in EVIDENCE.items():
        if k == "cycle_cut":
            continue
        d.room()
        a.plot([0.042], [d.y], "s", ms=3.4, color=col)
        a.annotate(f"{desc}", xy=(0.058, d.y), ha="left", va="center",
                   fontsize=7.6, color=INK)
        d.gap(1.25)

    # contents
    d.page("")
    a = d.ax
    a.annotate("Contents", xy=(0.035, 0.930), ha="left", va="center",
               fontsize=17, fontweight="bold", color=INK)
    a.plot([0.035, 0.965], [0.910, 0.910], color=INK, lw=1.0)
    d.y = 0.880
    for x, t, ha in ((0.035, "office", "left"), (0.520, "bodies", "right"),
                     (0.605, "titles", "right"), (0.700, "boards it sits on", "right"),
                     (0.880, "people", "right"), (0.965, "page", "right")):
        a.annotate(t, xy=(x, d.y), ha=ha, va="center", fontsize=6.4,
                   color=MUTED)
    d.gap(1.3)
    for oid, n in mins:
        d.room()
        titles = [k for k in ix["kids"].get(oid, ())
                  if ix["method"].get(k) not in STRUCTURAL
                  and ix["form"].get(k) == "ministere"]
        seats = c[c.ministry == oid[4:]].org_id.nunique()
        ppl = sum(int(ix["np"].get(x, 0) or 0)
                  for x, _ in walk(oid, ix))
        a.annotate(LABEL.get(oid[4:], ix["name"][oid]), xy=(0.035, d.y), ha="left", va="center",
                   fontsize=8.2, color=INK)
        a.annotate(f"{n:,}", xy=(0.520, d.y), ha="right", va="center",
                   fontsize=7.4, color=MUTED)
        a.annotate(f"{len(titles)}", xy=(0.605, d.y), ha="right", va="center",
                   fontsize=7.4, color=MUTED)
        a.annotate(f"{seats}", xy=(0.700, d.y), ha="right", va="center",
                   fontsize=7.4, color=MUTED)
        a.annotate(f"{ppl:,}", xy=(0.880, d.y), ha="right", va="center",
                   fontsize=7.4, color=MUTED)
        if starts.get(oid):
            a.annotate(f"{starts[oid]}", xy=(0.965, d.y), ha="right",
                       va="center", fontsize=7.4, color=INK)
        d.gap(1.35)


def ministry_section(d, oid, ix, c, h):
    name = LABEL.get(oid[4:], ix["name"][oid])
    rows = walk(oid, ix)
    a = d.page(name)

    a.annotate(name, xy=(0.035, d.y - ROW), ha="left", va="center",
               fontsize=19, fontweight="bold", color=INK)
    d.gap(3.2)
    people = sum(int(ix["np"].get(x, 0) or 0) for x, _ in rows)
    acts = sum(int(ix["ne"].get(x, 0) or 0) for x, _ in rows)
    seats = c[c.ministry == oid[4:]]
    a.annotate(f"{len(rows):,} bodies   ·   {people:,} people   ·   "
               f"{acts:,} appointment acts"
               + (f"   ·   seats on {seats.org_id.nunique()} other boards"
                  if len(seats) else ""),
               xy=(0.035, d.y), ha="left", va="center", fontsize=9.0,
               color=MUTED)
    d.gap(2.0)

    # --- titles over time ---
    titles = [k for k in ix["kids"].get(oid, ())
              if ix["method"].get(k) not in STRUCTURAL
              and ix["form"].get(k) == "ministere"]
    if titles:
        a.annotate("Titles this office went by", xy=(0.035, d.y), ha="left",
                   va="center", fontsize=9.4, fontweight="bold", color=INK)
        d.gap(1.5)
        titles.sort(key=lambda k: (ix["y0"].get(k, 9999),
                                   str(ix["name"].get(k, ""))))
        for k in titles:
            d.room()
            a.annotate(short(ix["name"].get(k, ""), 104), xy=(0.048, d.y),
                       ha="left", va="center", fontsize=7.2, color=INK)
            a.annotate(years(k, ix), xy=(0.965, d.y), ha="right", va="center",
                       fontsize=6.6, color=MUTED)
            d.gap(1.15)
        d.gap(0.9)

    # --- boards it sits on ---
    if len(seats):
        d.room(4)
        a = d.ax
        a.annotate("Boards this office holds a seat on", xy=(0.035, d.y),
                   ha="left", va="center", fontsize=9.4, fontweight="bold",
                   color=DOTTED)
        d.gap(1.5)
        top = (seats.groupby(["org_id", "body"]).seats.sum().reset_index()
               .sort_values("seats", ascending=False))
        for r in top.itertuples():
            d.room()
            a = d.ax
            a.plot([0.042, 0.054], [d.y, d.y], color=DOTTED, lw=0.6,
                   ls=(0, (2.0, 1.6)))
            a.annotate(short(r.body, 96), xy=(0.060, d.y), ha="left",
                       va="center", fontsize=7.0, color=INK)
            a.annotate(f"{int(r.seats)} appointment"
                       f"{'s' if int(r.seats) != 1 else ''}",
                       xy=(0.965, d.y), ha="right", va="center", fontsize=6.6,
                       color=MUTED)
            d.gap(1.15)
        d.gap(0.9)

    # --- who sits on this office's bodies ---
    mine = {x for x, _ in rows}
    inward = c[c.org_id.isin(mine) & (c.ministry != oid[4:])]
    if len(inward):
        d.room(4)
        a = d.ax
        a.annotate("Other offices holding seats on this one's bodies",
                   xy=(0.035, d.y), ha="left", va="center", fontsize=9.4,
                   fontweight="bold", color=DOTTED)
        d.gap(1.5)
        agg = (inward.groupby("ministry")
               .agg(bodies=("org_id", "nunique"), seats=("seats", "sum"))
               .sort_values("bodies", ascending=False))
        for k, r in agg.iterrows():
            d.room()
            a = d.ax
            a.annotate(MINISTRY_ENGLISH.get(k, k), xy=(0.060, d.y), ha="left",
                       va="center", fontsize=7.0, color=INK)
            a.annotate(f"on {int(r.bodies)} bod"
                       f"{'ies' if r.bodies != 1 else 'y'}",
                       xy=(0.965, d.y), ha="right", va="center", fontsize=6.6,
                       color=MUTED)
            d.gap(1.15)
        d.gap(0.9)

    # --- the hierarchy ---
    d.room(6)
    a = d.ax
    a.annotate("Bodies", xy=(0.035, d.y), ha="left", va="center",
               fontsize=9.4, fontweight="bold", color=INK)
    d.gap(1.5)
    column_heads(d)
    if not rows:
        d.room()
        d.ax.annotate("None recorded under this office.", xy=(0.048, d.y),
                      ha="left", va="center", fontsize=7.4, color=MUTED,
                      style="italic")
        d.gap()
    for oid_c, depth in rows:
        body_row(d, oid_c, depth, ix)


def main() -> None:
    print("loading…")
    h, c = load()
    ix = index(h)
    offices = [oid for oid in h.org_id
               if isinstance(oid, str) and oid.startswith("MIN:")]
    mins = sorted(((oid, len(walk(oid, ix))) for oid in offices),
                  key=lambda r: -r[1])

    # What the prune actually removes: every territorial body under an
    # office, and everything beneath it. The raw count of territorial rows is
    # not the same number and would misstate the exclusion.
    def with_territory(root):
        out, st = [], [c for c in ix["kids"].get(root, ())
                       if ix["method"].get(c) not in STRUCTURAL]
        while st:
            x = st.pop()
            out.append(x)
            st.extend(k for k in ix["kids"].get(x, ())
                      if ix["method"].get(k) not in STRUCTURAL)
        return out
    dropped = sum(len(with_territory(o)) for o in offices) - sum(n for _, n in mins)

    out = FIGS / "fig37_state_apparatus_guide.pdf"

    # Pass one exists only to learn where each section falls, so the contents
    # can carry page numbers. A 131-page reference without them is a list.
    print("pass 1 of 2: paginating…")
    starts: dict[str, int] = {}
    with PdfPages(FIGS / ".guide_pass1.pdf") as scratch:
        d = Doc(scratch)
        front_matter(d, h, c, ix, mins, dropped, {})
        for oid, _ in mins:
            starts[oid] = d.n + 1
            ministry_section(d, oid, ix, c, h)
        d.close()
    (FIGS / ".guide_pass1.pdf").unlink()

    print(f"pass 2 of 2: writing {len(mins)} sections…")
    with PdfPages(out) as pdf:
        d = Doc(pdf)
        front_matter(d, h, c, ix, mins, dropped, starts)
        for oid, _ in mins:
            ministry_section(d, oid, ix, c, h)
        d.close()
        info = pdf.infodict()
        info["Title"] = "The Tunisian State Apparatus: a structural guide"
        info["CreationDate"] = None
    print(f"  wrote {out.relative_to(FIGS.parent)}  "
          f"({out.stat().st_size / 1024:.0f} KB, {d.n} pages)")


if __name__ == "__main__":
    main()
