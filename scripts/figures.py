"""Publication figures for the JORT elite-network dataset.

Writes a PNG (300 dpi, for drafts and slides) and a PDF (vector, for
typesetting) of each figure into ``figures/``.

Colour
------
Two jobs, two treatments, per the rules the rest of the project follows:

* **identity** - person vs. institution is a two-slot categorical palette,
  ``#A03B2C`` / ``#1B5FC1``, validated for colour-vision deficiency
  (worst adjacent pair dE 23.6 protan, 27.9 normal) and for chroma and
  contrast against the paper surface.
* **magnitude** - seniority is ordinal, so it gets a single-hue sequential
  ramp light-to-dark rather than a set of unrelated hues.

Nothing is identified by colour alone: every figure carries direct labels or
a legend, and rank order is reinforced by node size.
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

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

# Four-slot categorical palette for cohort comparisons; validated together
# (worst adjacent pair dE 23.6 protan, 22.3 tritan, 27.9 normal vision).
CAT4 = ["#A03B2C", "#1B5FC1", "#B5852A", "#5B4E9E"]
# Single-hue sequential ramp for era, light -> dark, kept in a different hue
# from the seniority ramp so the two are never confused.
ERA_RAMP = ["#CBDCF2", "#92B5E3", "#5A8CD0", "#2F63B4", "#17408A"]
# Single-hue sequential ramp for seniority, light -> dark.
RANK_RAMP = ["#F0C7BC", "#DE9683", "#C4634C", "#9C3626", "#63160F"]
RANK_TIERS = [
    ("Secretary-general, chief executive", 65, 72),
    ("Cabinet chief, adviser", 72, 80),
    ("Governor", 80, 85),
    ("Secretary of state", 85, 90),
    ("Minister and above", 90, 999),
]

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


def headline(fig, title: str, subtitle: str, *, top: float = 0.99) -> None:
    """Title above subtitle, always, with space reserved for both."""
    fig.text(0.012, top, title, ha="left", va="top",
             fontsize=13.5, fontweight="bold", color=INK)
    fig.text(0.012, top - 0.036, subtitle, ha="left", va="top",
             fontsize=8.4, color=MUTED, wrap=True)


def save(fig, name: str, note: str | None = None) -> None:
    """Write both formats and report."""
    if note:
        fig.text(0.012, -0.012, note, fontsize=6.6, color=MUTED,
                 ha="left", va="top")
    for ext, kw in (("png", {"dpi": 300}), ("pdf", {})):
        path = FIGS / f"{name}.{ext}"
        fig.savefig(path, bbox_inches="tight", pad_inches=0.24, **kw)
        print(f"  {path.relative_to(ROOT)}  {path.stat().st_size / 1024:.0f} KB")
    plt.close(fig)


def place_labels(ax, items, *, fontsize=7.0, weight="normal"):
    """Annotate nodes, skipping any label that would collide with one already
    drawn.  A stack of overlapping names is worse than naming fewer people.

    ``items`` is an iterable of (text, (x, y)) in data coordinates, most
    important first.
    """
    fig = ax.figure
    fig.canvas.draw()
    placed: list[tuple[float, float, float, float]] = []
    renderer = fig.canvas.get_renderer()
    for text, (x, y) in items:
        for dx, dy in ((0, 11), (0, -13), (26, 4), (-26, 4), (0, 22), (0, -24)):
            ann = ax.annotate(
                text, (x, y), xytext=(dx, dy), textcoords="offset points",
                ha="center", va="center", fontsize=fontsize, color=INK,
                fontweight=weight,
                bbox=dict(boxstyle="round,pad=0.16", fc=PAPER, ec="none", alpha=.85),
            )
            bb = ann.get_window_extent(renderer=renderer)
            box = (bb.x0 - 1, bb.y0 - 1, bb.x1 + 1, bb.y1 + 1)
            if any(box[0] < p[2] and box[2] > p[0] and box[1] < p[3] and box[3] > p[1]
                   for p in placed):
                ann.remove()
                continue
            placed.append(box)
            break


# --- data ------------------------------------------------------------------
print("loading tables…")
spells = pd.read_csv(PROC / "spells.csv.gz", low_memory=False)
persons = pd.read_csv(PROC / "persons.csv.gz")
events = pd.read_csv(PROC / "events.csv.gz", low_memory=False)
succ = pd.read_csv(PROC / "edges" / "succession.csv.gz")
sig = pd.read_csv(PROC / "edges" / "signature.csv.gz")

name_of = dict(zip(persons.person_id, persons.name))
SENIOR = 72
senior = spells[spells.rank_score >= SENIOR].copy()
# A spell whose act named no organisation and sat under no ministry heading has
# an empty org; it cannot appear in an affiliation network.
for frame in (senior, spells):
    frame["org_id"] = frame.org_id.fillna("").astype(str)
    frame["org_name"] = frame.org_name.fillna("").astype(str)
senior = senior[senior.org_id != ""].copy()
for frame in (succ, sig):
    frame["org_name"] = frame.org_name.fillna("").astype(str)


def stable(g):
    """A copy whose node and edge order does not depend on the process.

    Python hashes strings with a per-process seed, so iterating a set of node
    ids yields a different order on every run.  A force layout starts from
    positions that follow node order, so without this the same data drew a
    visibly different graph each time it was rendered -- about 6% of pixels,
    enough to move labels and re-arrange clusters.  Sorting pins the drawing.
    """
    h = g.__class__()
    for n in sorted(g.nodes()):
        h.add_node(n, **g.nodes[n])
    for u, v in sorted(g.edges()):
        h.add_edge(u, v, **g.edges[u, v])
    return h


def largest_component(g):
    """The biggest connected component, ties broken deterministically."""
    best = max(nx.connected_components(g), key=lambda c: (len(c), min(c)))
    return stable(g.subgraph(best))


def org_label(name: str, n: int = 30) -> str:
    s = str(name or "")
    s = s[0].upper() + s[1:] if s and s.isupper() else s
    return s if len(s) <= n else s[: n - 1] + "…"


def tier_colour(score: float) -> str:
    for colour, (_, lo, hi) in zip(RANK_RAMP, RANK_TIERS):
        if lo <= score < hi:
            return colour
    return RANK_RAMP[0]


def active(df: pd.DataFrame, year: int) -> pd.DataFrame:
    return df[(df.start_year <= year) & (df.end_year >= year)]


# =========================================================================
# Figure 1 - the affiliation network at four moments
# =========================================================================
def fig_affiliation_snapshots(years=(1970, 1987, 2005, 2024), cut: int = 72,
                              min_component: int = 3) -> None:
    """Bipartite officeholder-institution map at four moments.

    Cut at cabinet-adviser rank rather than governor: above that the
    institutions mostly hold a single senior post each, so the graph
    degenerates into disconnected dyads that show nothing. Components of
    fewer than ``min_component`` nodes are dropped for the same reason.
    """
    print("fig01 affiliation snapshots")
    fig, axes = plt.subplots(2, 2, figsize=(9.8, 9.4))

    for ax, year in zip(axes.ravel(), years):
        sub = active(senior[senior.rank_score >= cut], year)
        g = nx.Graph()
        for r in sub.itertuples(index=False):
            g.add_node("p" + r.person_id, kind="p", score=r.rank_score)
            g.add_node("o" + r.org_id, kind="o", label=r.org_name)
            g.add_edge("p" + r.person_id, "o" + r.org_id)

        keep = set()
        for comp in nx.connected_components(g):
            if len(comp) >= min_component:
                keep |= comp
        g = stable(g.subgraph(keep))
        if not len(g):
            ax.set_axis_off()
            continue

        pos = nx.spring_layout(g, k=1.6 / np.sqrt(len(g)), seed=7, iterations=140)

        nx.draw_networkx_edges(g, pos, ax=ax, edge_color=RULE, width=0.5, alpha=.95)

        ppl = [n for n, d in g.nodes(data=True) if d["kind"] == "p"]
        org = [n for n, d in g.nodes(data=True) if d["kind"] == "o"]
        nx.draw_networkx_nodes(
            g, pos, nodelist=ppl, ax=ax,
            node_color=[tier_colour(g.nodes[n]["score"]) for n in ppl],
            node_size=11, edgecolors=PAPER, linewidths=.35,
        )
        nx.draw_networkx_nodes(
            g, pos, nodelist=org, ax=ax, node_color=ORG, node_shape="s",
            node_size=[16 + g.degree(n) * 5.5 for n in org],
            edgecolors=PAPER, linewidths=.6,
        )
        ax.set_title(f"{year}", fontsize=12.5)
        ax.text(0.0, 1.0,
                f"{len(ppl)} officeholders · {len(org)} institutions · "
                f"{g.number_of_edges()} posts",
                transform=ax.transAxes, ha="left", va="bottom",
                fontsize=7.2, color=MUTED)
        ax.set_axis_off()
        ax.margins(.12)
        place_labels(
            ax,
            [(org_label(g.nodes[n].get("label", ""), 24), pos[n])
             for n in sorted(org, key=lambda x: -g.degree(x))[:7]],
            fontsize=6.3,
        )

    handles = [
        Line2D([], [], marker="s", color="none", markerfacecolor=ORG,
               markersize=7, label="Institution"),
    ] + [
        Line2D([], [], marker="o", color="none", markerfacecolor=c,
               markersize=7, label=lab)
        for c, (lab, lo, hi) in zip(RANK_RAMP, RANK_TIERS) if hi > cut
    ]
    fig.legend(handles=handles, loc="lower center", ncol=len(handles),
               bbox_to_anchor=(0.5, 0.004), handletextpad=.4, columnspacing=1.5)

    headline(fig, "Who served where, at four moments in the Tunisian state",
             "Cabinet adviser rank and above. Institution size is its number of senior "
             "posts; components of fewer than three nodes are omitted.")
    fig.tight_layout(rect=(0, 0.038, 1, 0.935))
    save(fig, "fig01_affiliation_snapshots", SOURCE)


# =========================================================================
# Figure 2 - who signs whose appointment
# =========================================================================
def fig_signature_network(top_n: int = 9) -> None:
    print("fig02 signature network")
    counts = sig.source.value_counts().head(top_n)
    keep = set(counts.index)
    sub = sig[sig.source.isin(keep)]

    g = nx.DiGraph()
    for s in keep:
        g.add_node("S" + s, kind="s", n=int(counts[s]))
    for r in sub.itertuples(index=False):
        g.add_node("A" + r.target, kind="a")
        g.add_edge("S" + r.source, "A" + r.target)

    g = stable(g)
    pos = nx.spring_layout(g, k=2.1 / np.sqrt(len(g)), seed=11, iterations=150)

    fig, ax = plt.subplots(figsize=(9.8, 7.0))
    nx.draw_networkx_edges(g, pos, ax=ax, edge_color=RULE, width=0.5,
                           arrows=False, alpha=.85)
    app = [n for n, d in g.nodes(data=True) if d["kind"] == "a"]
    sgn = [n for n, d in g.nodes(data=True) if d["kind"] == "s"]
    nx.draw_networkx_nodes(g, pos, nodelist=app, ax=ax, node_color=ORG,
                           node_size=8, edgecolors=PAPER, linewidths=.25, alpha=.85)
    nx.draw_networkx_nodes(
        g, pos, nodelist=sgn, ax=ax, node_color=PERSON,
        node_size=[60 + g.nodes[n]["n"] * .55 for n in sgn],
        edgecolors=PAPER, linewidths=1.1,
    )
    ax.set_axis_off()
    ax.margins(.1)
    place_labels(
        ax,
        [(f"{name_of.get(n[1:], n[1:])} · {g.nodes[n]['n']}", pos[n])
         for n in sorted(sgn, key=lambda x: -g.nodes[x]["n"])],
        fontsize=7.4, weight="medium",
    )

    ax.legend(handles=[
        Line2D([], [], marker="o", color="none", markerfacecolor=PERSON,
               markersize=9, label="Signing authority · appointments signed"),
        Line2D([], [], marker="o", color="none", markerfacecolor=ORG,
               markersize=5, label="Person appointed"),
    ], loc="lower left", bbox_to_anchor=(0, 0.02), ncol=2)

    headline(fig, "Patronage as the gazette states it: who signed whose appointment",
             "The nine most prolific signatories and every senior appointment they "
             "signed. Direction runs from signatory to appointee.")
    fig.tight_layout(rect=(0, 0, 1, 0.925))
    save(fig, "fig02_signature_network", SOURCE)


# =========================================================================
# Figure 3 - succession chains, one office at a time
# =========================================================================
def fig_succession_chains(n_panels: int = 6) -> None:
    """Handover sequences within a single office.

    Built per ``office_id``, not as one global graph: succession edges chain
    through people who held several posts, so a global graph collapses into a
    single meaningless component spanning thousands of unrelated offices.
    """
    print("fig03 succession chains")
    offices = []
    for office_id, rows in succ.groupby("office_id"):
        g = nx.DiGraph()
        for r in rows.itertuples(index=False):
            g.add_edge(r.source, r.target, year=r.year)
        offices.append((len(g), office_id, stable(g), rows))
    offices.sort(key=lambda t: -t[0])
    offices = offices[:n_panels]

    fig, axes = plt.subplots(2, 3, figsize=(10.4, 6.8))
    for ax, (n, office_id, g, rows) in zip(axes.ravel(), offices):
        pos = nx.kamada_kawai_layout(g)
        nx.draw_networkx_edges(g, pos, ax=ax, edge_color=MUTED, width=0.9,
                               arrows=True, arrowsize=8, arrowstyle="-|>",
                               node_size=110, alpha=.8)
        nx.draw_networkx_nodes(g, pos, ax=ax, node_color=PERSON, node_size=52,
                               edgecolors=PAPER, linewidths=.8)
        years = list(rows.year)
        position = rows.position_rank.mode()
        org = rows.org_name.mode()
        ax.set_title(org_label(org.iloc[0] if len(org) else "", 32), fontsize=8.4)
        ax.text(0.0, 1.0,
                f"{n} holders · {min(years)}–{max(years)}"
                + (f" · {position.iloc[0]}" if len(position) else ""),
                transform=ax.transAxes, ha="left", va="bottom",
                fontsize=6.9, color=MUTED)
        ax.set_axis_off()
        ax.margins(.14)

    for ax in axes.ravel()[len(offices):]:
        ax.set_axis_off()

    headline(fig, "Succession runs through the boards of state enterprises",
             "The six offices with the longest recorded sequence of holders; an arrow "
             "runs from the incumbent an act names as replaced to their replacement. "
             "6,070 of the 6,950 succession ties in the corpus are seats on a conseil "
             "d'administration, because naming the outgoing holder is the standard "
             "phrasing for those acts and not for others.")
    fig.tight_layout(rect=(0, 0, 1, 0.885))
    save(fig, "fig03_succession_chains", SOURCE)


# =========================================================================
# Figure 4 - co-service backbone
# =========================================================================
def fig_colleague_backbone(year: int = 2011, cut: int = 72) -> None:
    print(f"fig04 co-service backbone, {year}")
    sub = active(senior[senior.rank_score >= cut], year)
    by_org = defaultdict(list)
    for r in sub.itertuples(index=False):
        by_org[r.org_id].append(r)

    g = nx.Graph()
    for org_id, rows in by_org.items():
        if len(rows) < 2 or len(rows) > 40:
            continue
        for i, a in enumerate(rows):
            for b in rows[i + 1:]:
                if a.person_id == b.person_id:
                    continue
                g.add_node(a.person_id, score=a.rank_score)
                g.add_node(b.person_id, score=b.rank_score)
                g.add_edge(a.person_id, b.person_id, org=a.org_name)

    if not len(g):
        print("   (no edges)")
        return
    giant = largest_component(g)

    fig, ax = plt.subplots(figsize=(9.8, 7.6))
    pos = nx.spring_layout(giant, k=2.1 / np.sqrt(len(giant)), seed=5, iterations=170)
    nx.draw_networkx_edges(giant, pos, ax=ax, edge_color=RULE, width=0.7)
    scores = [giant.nodes[n]["score"] for n in giant]
    nx.draw_networkx_nodes(
        giant, pos, ax=ax,
        node_color=[tier_colour(s) for s in scores],
        node_size=[26 + giant.degree(n) * 6 for n in giant],
        edgecolors=PAPER, linewidths=.7,
    )
    ax.set_axis_off()
    ax.margins(.11)
    # Name the brokers: highest betweenness, i.e. the people the component
    # would fall apart without. That is the substantive point of the figure.
    btw = nx.betweenness_centrality(giant)
    order = sorted(btw, key=lambda n: -btw[n])[:10]
    place_labels(ax, [(name_of.get(p, p), pos[p]) for p in order], fontsize=6.9)

    ax.legend(handles=[
        Line2D([], [], marker="o", color="none", markerfacecolor=c, markersize=7, label=lab)
        for c, (lab, lo, hi) in zip(RANK_RAMP, RANK_TIERS) if hi > cut
    ], loc="lower left", ncol=2, bbox_to_anchor=(0, 0.02))

    headline(fig, f"The senior co-service network in {year}",
             "Largest connected component: two people are tied when their tenures in "
             "the same institution overlap. Dense clusters are institutions; the ten "
             "people named are those with the highest betweenness — the brokers "
             "holding the component together.")
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    save(fig, f"fig04_coservice_backbone_{year}", SOURCE)


# =========================================================================
# Figure 5 - how the network's structure moves over time
# =========================================================================
class _UF:
    def __init__(self): self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def fig_structure_over_time(cut: int = 72) -> None:
    print("fig05 structure over time")
    years = list(range(1957, 2027))
    n_people, n_orgs, mean_size, giant_share = [], [], [], []

    base = senior[senior.rank_score >= cut]
    for y in years:
        sub = active(base, y)
        people = sub.person_id.unique()
        n_people.append(len(people))
        n_orgs.append(sub.org_id.nunique())
        by_org = sub.groupby("org_id").person_id.nunique()
        mean_size.append(float(by_org.mean()) if len(by_org) else np.nan)

        uf = _UF()
        for _, rows in sub.groupby("org_id").person_id:
            ids = list(dict.fromkeys(rows))
            for other in ids[1:]:
                uf.union(ids[0], other)
        if len(people):
            comp = Counter(uf.find(p) for p in people)
            giant_share.append(max(comp.values()) / len(people))
        else:
            giant_share.append(np.nan)

    panels = [
        ("Senior officeholders in post", n_people, "{:,.0f}"),
        ("Institutions holding them", n_orgs, "{:,.0f}"),
        ("Mean senior posts per institution", mean_size, "{:.1f}"),
        ("Share in the largest co-service component", giant_share, "{:.0%}"),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(9.8, 6.2), sharex=True)
    for ax, (title, series, fmt) in zip(axes.ravel(), panels):
        s = np.array(series, dtype=float)
        ax.fill_between(years, 0, s, color=PERSON, alpha=.13, linewidth=0)
        ax.plot(years, s, color=PERSON, linewidth=1.5)
        ax.set_title(title, fontsize=9)
        ax.grid(axis="y", alpha=.7)
        ax.set_axisbelow(True)
        ax.set_xlim(1957, 2026)
        top = np.nanmax(s)
        ax.set_ylim(0, top * 1.22 if top > 0 else 1)
        if fmt.endswith("%}"):
            ax.set_yticks([0, .25, .5, .75, 1])
            ax.set_yticklabels(["0", "25%", "50%", "75%", "100%"])
        ax.annotate(fmt.format(s[-1]), (years[-1], s[-1]), xytext=(-3, 9),
                    textcoords="offset points", ha="right", fontsize=7.6,
                    color=INK, fontweight="bold")
        for mark in (1987, 2011):
            ax.axvline(mark, color=MUTED, linewidth=.7, linestyle=(0, (3, 3)), alpha=.7)
        ax.tick_params(labelbottom=True)

    for lab, x in (("1987", 1987), ("2011", 2011)):
        axes[0, 0].annotate(lab, (x, 0), xytext=(3, 5), textcoords="offset points",
                            fontsize=6.8, color=MUTED)

    headline(fig, "The senior network grew tenfold; its connectivity did not follow",
             "Cabinet adviser rank and above, in post each year. Dashed lines mark 1987 "
             "and 2011. The largest-component share swings year to year and ends lower "
             "than it began: the state added institutions faster than it added people "
             "who bridge them. Counts after 2020 are inflated by tenures with no "
             "recorded end.")
    fig.tight_layout(rect=(0, 0, 1, 0.885))
    save(fig, "fig05_structure_over_time", SOURCE)


# =========================================================================
# Figure 6 - the composition of appointments by seniority
# =========================================================================
def fig_rank_composition() -> None:
    print("fig06 rank composition")
    ev = events[events.event_type.isin(["appointment", "board"])].copy()
    ev = ev[(ev.year >= 1957) & (ev.year <= 2026)]

    tiers = [
        ("Chef de service and below", 0, 45),
        ("Sous-directeur", 45, 55),
        ("Directeur", 55, 65),
        ("Directeur-general, secretary-general", 65, 80),
        ("Governor, minister and above", 80, 999),
    ]
    years = np.arange(1957, 2027)
    stack = []
    for _, lo, hi in tiers:
        s = ev[(ev.rank_score >= lo) & (ev.rank_score < hi)].groupby("year").size()
        stack.append([int(s.get(y, 0)) for y in years])

    fig, ax = plt.subplots(figsize=(9.8, 5.2))
    ax.stackplot(years, stack, colors=RANK_RAMP, edgecolor=PAPER, linewidth=.6)
    ax.grid(axis="y", alpha=.7)
    ax.set_axisbelow(True)
    ax.set_xlim(1957, 2026)
    ax.set_ylabel("Appointments published")
    ax.margins(y=0)

    total = np.array(stack).sum(axis=0)
    peak = int(years[int(np.argmax(total))])
    ax.annotate(f"{peak}: {total.max():,}", (peak, total.max()),
                xytext=(0, 9), textcoords="offset points", ha="center",
                fontsize=7.8, color=INK, fontweight="bold")
    ax.set_ylim(0, total.max() * 1.12)

    # The legend carries identity; in-band labels on five thin bands collide,
    # so they are not repeated here.
    ax.legend(handles=[Patch(facecolor=c, label=lab)
                       for c, (lab, _, _) in zip(RANK_RAMP, tiers)],
              loc="upper left", ncol=2, bbox_to_anchor=(0.01, 0.99))

    headline(fig, "Seventy years of appointments, by seniority of the post",
             "Colour runs light to dark with seniority. Volume roughly doubles after "
             "2011 and peaks in 2013; the thin early years reflect scan and OCR quality "
             "as much as a smaller state.")
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    save(fig, "fig06_appointments_by_rank", SOURCE)


# =========================================================================
# Figure 7 - the cumulative network of the state apparatus
# =========================================================================
def fig_institution_network(min_holders: int = 40, min_shared: int = 10) -> None:
    """The whole period at once, at the level where it stays legible.

    A cumulative person-level graph over seventy years is 45,000 nodes and
    unreadable. The institution is the unit that survives aggregation: two
    bodies are tied when the same people served in both, so the graph is the
    map of personnel circulation through the state.
    """
    print("fig07 cumulative institution network")
    sub = spells[(spells.org_id != "") & spells.org_id.notna()]

    holders = sub.groupby("org_id").person_id.nunique()
    keep = set(holders[holders >= min_holders].index)
    sub = sub[sub.org_id.isin(keep)]

    orgs_of = defaultdict(set)
    for pid, oid in zip(sub.person_id, sub.org_id):
        orgs_of[pid].add(oid)

    shared: Counter = Counter()
    for oids in orgs_of.values():
        if len(oids) < 2:
            continue
        for a, b in combinations(sorted(oids), 2):
            shared[(a, b)] += 1

    g = nx.Graph()
    for (a, b), w in shared.items():
        if w >= min_shared:
            g.add_edge(a, b, weight=w)
    if not len(g):
        print("   (no edges)")
        return
    g = largest_component(g)
    # The 2-core: drop pendant chains, which a force layout flings across the
    # frame and which say nothing about circulation anyway.
    core = nx.k_core(g, 2)
    if len(core) > 20:
        g = stable(core)

    label_of = (sub.groupby("org_id").org_name
                .agg(lambda s: s.mode().iloc[0] if len(s.mode()) else "").to_dict())
    era = sub.groupby("org_id").start_year.median()
    # Quantile bins, not a fixed range: most institutions in this corpus have a
    # late median year, so equal-width bins put almost every node in one colour.
    cuts = np.quantile(era.values, [.2, .4, .6, .8])
    era = era.to_dict()

    def era_colour(y: float) -> str:
        return ERA_RAMP[int(np.searchsorted(cuts, y, side="right"))]

    def era_label(i: int) -> str:
        edges = [None] + [int(round(c)) for c in cuts] + [None]
        lo_, hi_ = edges[i], edges[i + 1]
        if lo_ is None:
            return f"before {hi_}"
        if hi_ is None:
            return f"after {lo_}"
        return f"{lo_}\u2013{hi_}"

    fig, ax = plt.subplots(figsize=(10.0, 9.4))
    ax.set_aspect("equal")   # a spring layout squashed to the axes aspect
                             # reads as a false east-west structure
    pos = nx.spring_layout(g, k=6.5 / np.sqrt(len(g)), seed=17, iterations=500,
                           weight="weight")

    widths = np.array([g[u][v]["weight"] for u, v in g.edges()], dtype=float)
    nx.draw_networkx_edges(g, pos, ax=ax, edge_color=RULE,
                           width=0.25 + 1.5 * widths / widths.max(), alpha=.75)
    sizes = [14 + np.sqrt(holders.get(n, 0)) * 5.5 for n in g]
    nx.draw_networkx_nodes(
        g, pos, ax=ax,
        node_color=[era_colour(era.get(n, 1990)) for n in g],
        node_size=sizes, edgecolors=PAPER, linewidths=.8,
    )
    ax.set_axis_off()
    ax.margins(.09)

    order = sorted(g.nodes(), key=lambda n: -(holders.get(n, 0)))[:16]
    place_labels(ax, [(org_label(label_of.get(n, ""), 28), pos[n]) for n in order],
                 fontsize=6.6)

    era_handles = [
        Line2D([], [], marker="o", color="none", markerfacecolor=c, markersize=8,
               label=lab)
        for i, (c, lab) in enumerate(
            (c, era_label(i)) for i, c in enumerate(ERA_RAMP))
    ]
    leg = ax.legend(handles=era_handles, loc="lower left", ncol=5,
                    bbox_to_anchor=(0, 0.0),
                    title="Median year its officeholders took post")
    leg.get_title().set_fontsize(7.6)
    leg.get_title().set_color(MUTED)

    headline(fig, "The state apparatus as one cumulative network, 1957–2026",
             f"Institutions with at least {min_holders} recorded officeholders, tied "
             f"when at least {min_shared} people served in both. Node size is the "
             "number of officeholders; edge width is the number shared. The largest "
             f"2-core of the largest connected component: {len(g)} institutions, "
             f"{g.number_of_edges()} ties.")
    fig.tight_layout(rect=(0, 0, 1, 0.915))
    save(fig, "fig07_cumulative_institution_network", SOURCE)


# =========================================================================
# Figure 8 - the revolution and the state apparatus
# =========================================================================
def fig_revolution() -> None:
    """What 2011 did, and did not, do to personnel."""
    print("fig08 revolution")
    fig, axes = plt.subplots(2, 2, figsize=(10.2, 7.4))

    # (a) volume of entries and exits ------------------------------------
    ax = axes[0, 0]
    ev = events[(events.year >= 2000) & (events.year <= 2020)]
    entries = ev[ev.event_type.isin(["appointment", "board"])].groupby("year").size()
    exits = ev[ev.event_type.isin(["termination", "retirement"])].groupby("year").size()
    yr = np.arange(2000, 2021)
    ax.plot(yr, [entries.get(y, 0) for y in yr], color=CAT4[0], linewidth=1.8,
            label="Appointments")
    ax.plot(yr, [exits.get(y, 0) for y in yr], color=CAT4[1], linewidth=1.8,
            label="Cessations of function")
    ax.axvline(2011, color=MUTED, linewidth=.8, linestyle=(0, (3, 3)))
    ax.annotate("2011", (2011, ax.get_ylim()[1]), xytext=(3, -10),
                textcoords="offset points", fontsize=7, color=MUTED)
    ax.set_title("Appointments doubled; recorded exits did not", fontsize=9)
    ax.grid(axis="y", alpha=.7)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left")
    ax.set_ylim(bottom=0)
    ax.set_xticks(np.arange(2000, 2021, 5))

    # (b) newcomers vs. returning officials ------------------------------
    ax = axes[0, 1]
    first_year = dict(zip(persons.person_id, persons.first_year))
    app = events[events.event_type.isin(["appointment", "board"])]
    app = app[(app.year >= 2000) & (app.year <= 2020)]
    is_new = np.array([first_year.get(p, 9999) == y
                       for p, y in zip(app.person_id, app.year)])
    new_by = app[is_new].groupby("year").size()
    old_by = app[~is_new].groupby("year").size()
    n_new = np.array([new_by.get(y, 0) for y in yr])
    n_old = np.array([old_by.get(y, 0) for y in yr])
    ax.stackplot(yr, [n_new, n_old], colors=[CAT4[0], RULE],
                 edgecolor=PAPER, linewidth=.6,
                 labels=["First appearance in the gazette", "Already on the record"])
    ax.axvline(2011, color=MUTED, linewidth=.8, linestyle=(0, (3, 3)))
    share = n_new / np.maximum(n_new + n_old, 1)
    ax.annotate(f"{share[yr == 2010][0]:.0%} new", (2010, n_new[yr == 2010][0]),
                xytext=(-6, 8), textcoords="offset points", ha="right",
                fontsize=7.2, color=INK, fontweight="bold")
    ax.annotate(f"{share[yr == 2013][0]:.0%} new", (2013, n_new[yr == 2013][0]),
                xytext=(6, 8), textcoords="offset points", ha="left",
                fontsize=7.2, color=INK, fontweight="bold")
    ax.set_title("The pool widened in volume, not in composition", fontsize=9)
    ax.grid(axis="y", alpha=.7)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left", fontsize=7.4)
    ax.set_ylim(bottom=0)
    ax.set_xticks(np.arange(2000, 2021, 5))

    # (c) churn: how often postholders are moved -----------------------
    # A "still in post" curve cannot be read off this source: only 5% of
    # spells are closed by an act that states the exit, and 42% are never
    # closed at all, so almost nobody registers as having left on a date.
    # Movement into a new post is recorded, and is what the gazette can
    # actually measure.
    ax = axes[1, 0]
    lead = spells[spells.rank_score >= 55]
    starts = defaultdict(set)
    for pid, y0 in zip(lead.person_id, lead.start_year):
        starts[y0].add(pid)

    churn_years = list(range(1965, 2021))
    rates = []
    for y in churn_years:
        cohort = set(lead[(lead.start_year <= y) & (lead.end_year >= y)].person_id)
        movers = starts[y + 1] | starts[y + 2]
        rates.append(len(cohort & movers) / len(cohort) if cohort else np.nan)

    rates = np.array(rates, dtype=float)
    ax.fill_between(churn_years, 0, rates, color=CAT4[0], alpha=.13, linewidth=0)
    ax.plot(churn_years, rates, color=CAT4[0], linewidth=1.7)
    for mark, lab in ((1987, "1987"), (2011, "2011")):
        ax.axvline(mark, color=MUTED, linewidth=.8, linestyle=(0, (3, 3)))
        i = churn_years.index(mark)
        ax.annotate(f"{lab}\n{rates[i]:.0%}", (mark, rates[i]), xytext=(5, 6),
                    textcoords="offset points", fontsize=7.2, color=INK,
                    fontweight="bold")
    ax.set_title("Share of postholders moved to a new post within two years",
                 fontsize=9)
    ax.set_ylim(0, np.nanmax(rates) * 1.28)
    ax.set_xlim(1965, 2020)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.grid(axis="y", alpha=.7)
    ax.set_axisbelow(True)

    # (d) where the churn landed -----------------------------------------
    ax = axes[1, 1]
    base_pop = (spells[(spells.start_year <= 2010) & (spells.end_year >= 2010)
                       & spells.org_portfolio.notna()
                       & (spells.org_portfolio != "")]
                .groupby("org_portfolio").person_id.nunique())
    churn_ev = (events[(events.year.between(2011, 2013))
                       & events.event_type.isin(["appointment", "board"])
                       & events.org_portfolio.notna()
                       & (events.org_portfolio != "")]
                .groupby("org_portfolio").size())
    rows = []
    for port, n in base_pop.items():
        if n < 30:
            continue
        rows.append((str(port).replace("min_", "").replace("_", " "),
                     churn_ev.get(port, 0) / n, n))
    rows.sort(key=lambda r: r[1])
    rows = rows[-12:]

    yv = np.arange(len(rows))
    ax.barh(yv, [r[1] for r in rows], color=CAT4[0], height=.66)
    ax.set_yticks(yv)
    ax.set_yticklabels([r[0] for r in rows], fontsize=7.2)
    ax.grid(axis="x", alpha=.7)
    ax.set_axisbelow(True)
    for yi, r in zip(yv, rows):
        ax.annotate(f"{r[1]:.1f}", (r[1], yi), xytext=(4, 0),
                    textcoords="offset points", va="center", fontsize=7, color=INK)
    ax.set_xlim(0, max(r[1] for r in rows) * 1.16)
    ax.set_title("Appointments in 2011–13 per person in post in 2010", fontsize=9)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)

    headline(fig, "The revolution reshuffled the apparatus without renewing it",
             "Appointments roughly doubled after 2011 and peaked in 2013 (a), but the "
             "share of appointees appearing in the gazette for the first time barely "
             "moved, from 30% to 35% (b). The churn rate among sitting postholders rose "
             "only to 8%, below the 12% of Ben Ali's 1987 takeover and below most of "
             "the 1990s (c): the state published more appointments because it had grown, "
             "not because it turned over harder. Panels (c) and (d) measure movement "
             "into posts rather than departure from them: only 5% of spells are "
             "closed by an act that states the exit, so departure cannot be "
             "counted directly.")
    fig.tight_layout(rect=(0, 0, 1, 0.845))
    save(fig, "fig08_revolution_and_the_apparatus", SOURCE)



# =========================================================================
# Figure 9 - the two-mode network itself
# =========================================================================
def fig_bipartite_elite(cut: int = 90) -> None:
    """Individuals and organisations as one two-mode graph, cumulative.

    Panel (a) is the whole cabinet-rank network; panel (b) is its 2-core,
    drawn with the two modes in separate columns so the bipartite structure
    is literal rather than implied. The 2-core keeps only people who served
    in more than one body and the bodies that link them -- the circulating
    elite, which is what a two-mode graph is for.
    """
    print("fig09 bipartite elite network")
    sub = spells[(spells.rank_score >= cut) & (spells.org_id != "")]

    g = nx.Graph()
    for r in sub.itertuples(index=False):
        pn, on = "p" + r.person_id, "o" + r.org_id
        if pn not in g:
            g.add_node(pn, kind="p", score=r.rank_score, ref=r.person_id)
        else:
            g.nodes[pn]["score"] = max(g.nodes[pn]["score"], r.rank_score)
        g.add_node(on, kind="o", label=r.org_name, ref=r.org_id)
        g.add_edge(pn, on)

    fig = plt.figure(figsize=(10.4, 13.2))
    gs = fig.add_gridspec(2, 1, height_ratios=[0.92, 1.0], hspace=0.10)

    # --- (a) the whole two-mode network ---------------------------------
    # The giant component: a handful of bodies appointed one person each and
    # nobody else, and a force layout throws those dyads to the corners,
    # squeezing everything that matters into the middle.
    ax = fig.add_subplot(gs[0])
    giant = largest_component(g)
    pos = nx.spring_layout(giant, k=2.7 / np.sqrt(len(giant)), seed=23,
                           iterations=400)
    nx.draw_networkx_edges(giant, pos, ax=ax, edge_color=RULE, width=0.5, alpha=.9)

    ppl = [n for n, d in giant.nodes(data=True) if d["kind"] == "p"]
    org = [n for n, d in giant.nodes(data=True) if d["kind"] == "o"]
    nx.draw_networkx_nodes(
        giant, pos, nodelist=ppl, ax=ax,
        node_color=[tier_colour(giant.nodes[n]["score"]) for n in ppl],
        node_size=[14 + giant.degree(n) * 9 for n in ppl],
        edgecolors=PAPER, linewidths=.4,
    )
    nx.draw_networkx_nodes(
        giant, pos, nodelist=org, ax=ax, node_color=ORG, node_shape="s",
        node_size=[26 + giant.degree(n) * 3.2 for n in org],
        edgecolors=PAPER, linewidths=.7,
    )
    ax.set_axis_off()
    ax.margins(.06)
    place_labels(ax, [(org_label(giant.nodes[n]["label"], 26), pos[n])
                      for n in sorted(org, key=lambda x: -giant.degree(x))[:15]],
                 fontsize=6.5)
    ax.set_title(f"(a)  The connected two-mode network — {len(ppl)} people, "
                 f"{len(org)} organisations, {giant.number_of_edges()} posts",
                 fontsize=9.4)
    ax.legend(handles=[
        Line2D([], [], marker="s", color="none", markerfacecolor=ORG,
               markersize=7, label="Organisation"),
        Line2D([], [], marker="o", color="none", markerfacecolor=RANK_RAMP[3],
               markersize=7, label="Officeholder"),
    ], loc="upper left", ncol=1)

    # --- (b) the 2-core, as an explicit two-mode layout -----------------
    ax2 = fig.add_subplot(gs[1])
    core = largest_component(nx.k_core(giant, 2))
    cp = [n for n, d in core.nodes(data=True) if d["kind"] == "p"]
    co = [n for n, d in core.nodes(data=True) if d["kind"] == "o"]
    # Order each column by the other column's layout so edges cross less.
    co.sort(key=lambda n: -core.degree(n))
    org_rank = {n: i for i, n in enumerate(co)}
    cp.sort(key=lambda n: np.mean([org_rank[m] for m in core.neighbors(n)]))

    pos2 = {}
    for i, n in enumerate(cp):
        pos2[n] = (0.0, 1.0 - (i / max(len(cp) - 1, 1)))
    for i, n in enumerate(co):
        pos2[n] = (1.0, 1.0 - (i / max(len(co) - 1, 1)))

    nx.draw_networkx_edges(core, pos2, ax=ax2, edge_color=RULE, width=0.55, alpha=.95)
    nx.draw_networkx_nodes(
        core, pos2, nodelist=cp, ax=ax2,
        node_color=[tier_colour(core.nodes[n]["score"]) for n in cp],
        node_size=26, edgecolors=PAPER, linewidths=.4,
    )
    nx.draw_networkx_nodes(
        core, pos2, nodelist=co, ax=ax2, node_color=ORG, node_shape="s",
        node_size=[24 + core.degree(n) * 2.4 for n in co],
        edgecolors=PAPER, linewidths=.7,
    )
    for n in cp:
        ax2.annotate(name_of.get(core.nodes[n]["ref"], ""), pos2[n],
                     xytext=(-6, 0), textcoords="offset points",
                     ha="right", va="center", fontsize=5.0, color=INK)
    for n in co:
        ax2.annotate(org_label(core.nodes[n]["label"], 34), pos2[n],
                     xytext=(7, 0), textcoords="offset points",
                     ha="left", va="center", fontsize=5.4, color=INK)
    ax2.set_xlim(-0.42, 1.52)
    ax2.set_ylim(-0.04, 1.04)
    ax2.set_axis_off()
    ax2.set_title(f"(b)  Its 2-core: the {len(cp)} people who served in more than one "
                  f"body, and the {len(co)} bodies that link them",
                  fontsize=9.4)

    headline(fig, "Individuals and organisations as one two-mode network",
             "Cumulative, 1957–2026, at minister rank and above. Circles are people, "
             "squares are organisations, and every edge is one published appointment; "
             "there are no person–person or body–body edges, because the gazette "
             "records only the two-mode tie.", top=0.995)
    fig.subplots_adjust(top=0.902, bottom=0.015, left=0.02, right=0.98)
    save(fig, "fig09_bipartite_elite_network", SOURCE)


if __name__ == "__main__":
    fig_affiliation_snapshots()
    fig_signature_network()
    fig_succession_chains()
    fig_colleague_backbone(2011)
    fig_structure_over_time()
    fig_rank_composition()
    fig_institution_network()
    fig_revolution()
    fig_bipartite_elite()
    print(f"\ndone — {len(list(FIGS.glob('*')))} files in {FIGS.relative_to(ROOT)}/")
