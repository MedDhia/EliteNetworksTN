"""Publication figures for the A'lam Tunisiyun build.

Four figures in two editions -- Arabic labels and Latin ones -- written into
``figures/`` as a 300 dpi PNG and a vector PDF each, in the house style shared
with the gazette build (``house_style.py``). The Latin plates take the ``_en``
suffix and are drawn by the same four functions, so neither edition can drift
from the other.

The Latin labels are the ``name_ijmes`` column, because everything else on the
plate is English. ``name_fr`` is the Tunisian French form and is in the tables;
it is what joins this build to the gazette build, whose 45,634 persons and
8,803 institutions are all named in French.

What they are allowed to show
----------------------------
Only the 38 subjects appear as nodes in the network figures. The other 204
people in the register are alters -- named in passing inside somebody else's
essay -- and their degree measures how often the author mentioned them, not
their standing. ``docs/LIMITATIONS-aalam-tunisiyun.md`` s2 says the two are
not comparable, so drawing them in one node set would invite exactly the
comparison the codebook forbids.

Arabic labels are passed raw. This matplotlib shapes and orders Arabic
itself; pre-processing with arabic-reshaper and python-bidi double-processes
it and silently produces reversed, disjoint text. See ``house_style.py``.
"""
from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.lines import Line2D

from house_style import (ARABIC_FONT, ERA3, INK, MUTED, ORG, PAPER, PERSON,
                         RULE, ROOT, headline, save, stable)

PROC = ROOT / "data" / "processed" / "aalam-tunisiyun"

SOURCE = ("Source: Sadok Zmerli, *A'lam Tunisiyun* (Dar al-Gharb al-Islami, 2000), "
          "38 biographical essays, author's extraction. 866 of 873 ties come from a "
          "model pass over the Arabic text and every one quotes its page verbatim. "
          "On a seeded sample of 206 ties, precision 0.907 (95% CI 0.860-0.940) and "
          "recall 0.672 (0.550-0.774), so counts here are lower bounds: the coders "
          "were further instances of the model that wrote the assertions, which makes "
          "the comparisons between layers meaningful and the headline number not. "
          "See docs/LIMITATIONS-aalam-tunisiyun.md.")

# The author's own three generations, in his order.
COHORTS = ["السابقون", "التابعون", "المعاصرون"]
COHORT_EN = {"السابقون": "The predecessors",
             "التابعون": "The followers",
             "المعاصرون": "The contemporaries"}
COHORT_COLOUR = dict(zip(COHORTS, ERA3))

LAYER_STYLE = {
    "tutelage": ("-", 1.6),
    "office": ("--", 1.2),
    "kinship": ("-", 2.6),
    "membership": (":", 1.2),
}
LAYER_EN = {"tutelage": "Tutelage", "office": "Office",
            "kinship": "Kinship", "membership": "Membership"}


# --- data ------------------------------------------------------------------
def _read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


print("loading tables…")
persons = _read(PROC / "persons.csv")
edges = _read(PROC / "edges" / "all.csv")

subjects = {r["person_id"]: r for r in persons if r["is_subject"] == "yes"}
# Both editions read the same tables. `name_ijmes` is written by
# `python -m aalam.romanise`, gated against the Arabic consonant by consonant.
NAME = {"ar": {r["person_id"]: r["name_ar"] for r in persons},
        "en": {r["person_id"]: r["name_ijmes"] or r["name_ar"] for r in persons}}
name_of = NAME["ar"]
# Nodes the book places only by a relation («الأساتذة الذين ساهموا في تكوينهما»)
# are real ties to unidentified people, but they are not people to draw.
described = {r["person_id"] for r in persons if r.get("name_kind") == "described"}
cohort_of = {pid: r["cohort"] for pid, r in subjects.items()}


def _draw_nodes(ax, pos, nodes, *, colour, size, marker="o", zorder=3):
    """Marks with a 2px paper ring, so overlaps stay readable."""
    xs = [pos[n][0] for n in nodes]
    ys = [pos[n][1] for n in nodes]
    ax.scatter(xs, ys, s=[size[n] for n in nodes],
               c=[colour[n] if isinstance(colour, dict) else colour for n in nodes],
               marker=marker, linewidths=1.4, edgecolors=PAPER, zorder=zorder)


def _separate(pos: dict, min_dist: float = 0.13, rounds: int = 260) -> dict:
    """Push apart nodes the layout left on top of each other.

    A spring layout pulls every teacher of one man onto the same spot, so the
    hollow circles pile up and their labels stack. This is a few rounds of
    plain pairwise repulsion below a floor distance -- it moves nodes far
    enough to read and not far enough to change which cluster they sit in.
    """
    import math
    pos = {n: [float(x), float(y)] for n, (x, y) in pos.items()}
    nodes = sorted(pos)
    for _ in range(rounds):
        moved = False
        for i, a in enumerate(nodes):
            for b in nodes[i + 1:]:
                dx = pos[b][0] - pos[a][0]
                dy = pos[b][1] - pos[a][1]
                d = math.hypot(dx, dy)
                if d >= min_dist:
                    continue
                moved = True
                if d < 1e-9:            # exactly coincident: pick a direction
                    dx, dy, d = 1e-3, 0.0, 1e-3
                push = (min_dist - d) / 2
                ux, uy = dx / d, dy / d
                pos[a][0] -= ux * push
                pos[a][1] -= uy * push
                pos[b][0] += ux * push
                pos[b][1] += uy * push
        if not moved:
            break
    return {n: (x, y) for n, (x, y) in pos.items()}


# Half-width of one character, in data units, at font size 6.5. Both numbers
# are measured off these plates with `get_window_extent`, not guessed: Latin
# sets 1.65 times as wide as Amiri's Arabic at the same point size, so reusing
# the Arabic constant on a Latin plate would size every collision box about a
# third too small and the labels would overprint.
PER_CHAR = {"ar": 0.0135, "en": 0.0223}


def _place_labels(ax, pos, items, *, size, colour, lang="ar", weight="normal",
                  span=(0.052, 0.075), placed=None) -> None:
    """Label nodes, moving a label that would land on one already placed.

    Labels are tried above the node first, then below, then to either side.
    Overlap is measured on a crude box in data units rather than by rendering,
    which is enough here: the failure being avoided is two long names written
    across each other, not a pixel of contact.

    Pass ``placed`` to carry collision state across calls. Two calls without it
    know nothing of each other, which is how the subject and alter labels in
    fig 2 came to be written over one another.
    """
    dx, dy = span
    offsets = [(0, dy), (0, -dy), (0, 1.9 * dy), (0, -1.9 * dy),
               (2.4 * dx, 0.35 * dy), (-2.4 * dx, 0.35 * dy),
               (0, 2.8 * dy), (0, -2.8 * dy)]
    if placed is None:
        placed = []
    for node, text in items:
        half_w = max(0.055, PER_CHAR[lang] * len(text) * size / 6.5)
        half_h = 0.026 * size / 6.5
        x0, y0 = pos[node]
        for ox, oy in offsets:
            x, y = x0 + ox, y0 + oy
            box = (x - half_w, y - half_h, x + half_w, y + half_h)
            if all(box[2] < b[0] or box[0] > b[2] or
                   box[3] < b[1] or box[1] > b[3] for b in placed):
                placed.append(box)
                break
        else:
            x, y = x0, y0 + dy
            placed.append((x - half_w, y - half_h, x + half_w, y + half_h))
        ax.text(x, y, text, ha="center", va="center", fontsize=size,
                color=colour, weight=weight, zorder=6,
                # Amiri's Latin is poor, so only the Arabic edition asks for it.
                **({"fontfamily": ARABIC_FONT} if lang == "ar" else {}),
                bbox=dict(boxstyle="round,pad=0.16", fc=PAPER, ec="none",
                          alpha=0.85))


# --- fig 1: the two-mode network -------------------------------------------
def fig_two_mode(lang: str = "ar", min_subjects: int = 3) -> None:
    """Subjects and the institutions that tie at least two of them together."""
    by_org: dict[str, set[str]] = defaultdict(set)
    org_name: dict[str, str] = {}
    for e in edges:
        if e["to_kind"] == "person" or e["from_id"] not in subjects:
            continue
        # An office is a post, not a body people meet in; it cannot bind two
        # careers the way a school or a newspaper does.
        if e["to_kind"] in {"office", "work"}:
            continue
        by_org[e["to_id"]].add(e["from_id"])
        org_name[e["to_id"]] = {"ar": e["to_name"],
                                "en": e["to_ijmes"] or e["to_name"]}

    hubs = {o: s for o, s in by_org.items() if len(s) >= min_subjects}
    g = nx.Graph()
    for oid, members in hubs.items():
        for pid in members:
            g.add_edge(pid, oid)
    # A small off-to-the-side component costs the whole plate: the spring
    # throws it to a corner and squeezes everything else into the opposite one.
    # Draw the main component and say in the caption what was left out.
    g = stable(g)
    components = sorted(nx.connected_components(g), key=len, reverse=True)
    dropped = sum(len(c) for c in components[1:])
    g = stable(g.subgraph(components[0]).copy())

    persons_in = [n for n in g if n in subjects]
    orgs_in = [n for n in g if n not in subjects]

    pos = _separate(nx.spring_layout(g, k=1.05, iterations=1400, seed=11,
                                     weight=None),
                    min_dist={"ar": 0.16, "en": 0.22}[lang])

    fig, ax = plt.subplots(figsize=(9.4, 7.4))
    ax.axis("off")
    for u, v in g.edges():
        ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]],
                color=RULE, lw=0.85, zorder=1, solid_capstyle="round")

    psize = {n: 40 + 26 * g.degree(n) for n in persons_in}
    osize = {n: 60 + 52 * g.degree(n) for n in orgs_in}
    _draw_nodes(ax, pos, persons_in, colour=PERSON, size=psize, marker="o")
    _draw_nodes(ax, pos, orgs_in, colour=ORG, size=osize, marker="s", zorder=4)

    # Direct-label every institution: they are the finding, and there are few.
    # Biggest first, so a hub keeps the spot nearest its node and a minor body
    # is the one that moves.
    # The one mixed-direction string on the Arabic plate: an Arabic name with
    # an ASCII count after it, which bidi reorders so the count reads at the
    # visual left. The Latin plate has no such problem.
    _place_labels(ax, pos,
                  [(o, f"{org_name[o][lang]} ({g.degree(o)})")
                   for o in sorted(orgs_in, key=lambda o: -g.degree(o))],
                  size=7.4, colour=ORG, lang=lang, weight="bold",
                  span={"ar": (0.052, 0.075), "en": (0.052, 0.105)}[lang])
    # People carry no labels here. Thirty names would bury the institutions,
    # which are what the figure is about; fig 3 names them instead.

    ax.legend(handles=[
        Line2D([], [], marker="o", ls="none", mfc=PERSON, mec=PAPER, ms=8,
               label=f"Subject of an essay ({len(persons_in)} of 38)"),
        Line2D([], [], marker="s", ls="none", mfc=ORG, mec=PAPER, ms=9,
               label=f"Institution tying ≥{min_subjects} subjects ({len(orgs_in)})"),
    ], loc="lower left", fontsize=7.8)

    headline(fig, "What held the Tunisian reform elite together",
             f"The {len(orgs_in)} schools, mosques, newspapers and societies that appear in at "
             f"least {min_subjects} of the 38 biographies, and the {len(persons_in)} subjects "
             "who passed through them. Node size is degree; the number after each institution "
             "is how many of the 38 it ties. Posts and published works are excluded, because "
             "an office is held in turn rather than shared."
             + (f" A separate pair of nodes, unconnected to this component, is not drawn."
                if dropped else ""),
             top=0.995)
    fig.subplots_adjust(top=0.878, bottom=0.045, left=0.02, right=0.98)
    save(fig, _name("fig01_aalam_two_mode", lang), SOURCE)


# --- fig 2: pedagogical descent --------------------------------------------
def fig_tutelage(lang: str = "ar") -> None:
    """Who studied under whom: the layer no other build in this repo has."""
    g = nx.DiGraph()
    for e in edges:
        if e["layer"] != "tutelage" or e["to_kind"] != "person":
            continue
        if e["relation"] == "studied_under":
            g.add_edge(e["to_id"], e["from_id"])          # teacher -> pupil
        elif e["relation"] == "taught":
            g.add_edge(e["from_id"], e["to_id"])
    g.remove_edges_from(nx.selfloop_edges(g))
    g.remove_nodes_from([n for n in list(g) if n in described])

    # The layer is mostly stars -- a subject and the shaykhs he read with --
    # and a spring layout over nine disconnected pieces spends the plate on
    # whitespace and stacks the labels. Draw the one component that is an
    # actual chain of descent, and say how much is left out.
    g = stable(g)
    comps = sorted(nx.weakly_connected_components(g), key=len, reverse=True)
    n_all, c_all = g.number_of_nodes(), len(comps)
    g = stable(g.subgraph(comps[0]).copy())

    pos = _separate(nx.spring_layout(g, k=2.1, iterations=2000, seed=5,
                                     weight=None), min_dist=0.20)
    fig, ax = plt.subplots(figsize=(10.4, 8.0))
    ax.axis("off")

    for u, v in g.edges():
        ax.annotate("", xy=pos[v], xytext=pos[u], zorder=1,
                    arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=0.9,
                                    shrinkA=7, shrinkB=9, alpha=0.75,
                                    connectionstyle="arc3,rad=0.07"))

    subj_in = [n for n in g if n in subjects]
    alter_in = [n for n in g if n not in subjects]
    size = {n: 44 + 30 * (g.in_degree(n) + g.out_degree(n)) for n in g}
    colour = {n: COHORT_COLOUR.get(cohort_of.get(n, ""), MUTED) for n in subj_in}
    _draw_nodes(ax, pos, alter_in, colour="#FFFFFF", size=size, marker="o", zorder=3)
    ax.scatter([pos[n][0] for n in alter_in], [pos[n][1] for n in alter_in],
               s=[size[n] for n in alter_in], facecolors="none",
               edgecolors=MUTED, linewidths=1.0, zorder=4)
    _draw_nodes(ax, pos, subj_in, colour=colour, size=size, marker="o", zorder=5)

    # One collision list across both calls: the subjects claim their slots
    # first and an alter's label moves out of the way, rather than being
    # written on top of a name already on the plate.
    names, placed = NAME[lang], []
    _place_labels(ax, pos, [(n, names.get(n, n)) for n in subj_in],
                  size=6.1, colour=INK, lang=lang, placed=placed)
    _place_labels(ax, pos, [(n, names.get(n, n)) for n in alter_in],
                  size=5.6, colour=MUTED, lang=lang, placed=placed)

    handles = [Line2D([], [], marker="o", ls="none", mfc=COHORT_COLOUR[c],
                      mec=PAPER, ms=8, label=f"Subject — {COHORT_EN[c]}")
               for c in COHORTS]
    handles.append(Line2D([], [], marker="o", ls="none", mfc="none", mec=MUTED,
                          ms=8, label="Teacher or pupil named in passing"))
    ax.legend(handles=handles, loc="lower right", fontsize=7.4)

    headline(fig, "Pedagogical descent",
             f"The largest chain of teacher-pupil ties the book states, drawn from "
             f"teacher to pupil: {g.number_of_nodes()} of the {n_all} people in this layer. "
             f"The rest form {c_all - 1} smaller groups, mostly one subject and the shaykhs "
             "he read with. In this stratum a man's shaykhs place him more reliably than "
             "his appointments do, and this is the only layer in the repository that "
             "records them. Hollow circles are people named only as somebody's teacher "
             "or pupil.", top=0.995)
    fig.subplots_adjust(top=0.872, bottom=0.045, left=0.02, right=0.98)
    save(fig, _name("fig02_aalam_tutelage", lang), SOURCE)


# --- fig 3: the backbone among the 38 --------------------------------------
def fig_subject_backbone(lang: str = "ar") -> None:
    """Ties running between two of the 38, across all four layers."""
    g = nx.Graph()
    g.add_nodes_from(subjects)
    layers: dict[tuple[str, str], set[str]] = defaultdict(set)
    for e in edges:
        a, b = e["from_id"], e["to_id"]
        if a in subjects and b in subjects and a != b:
            layers[tuple(sorted((a, b)))].add(e["layer"])
    for (a, b), ls in layers.items():
        g.add_edge(a, b, layers=ls)
    g = stable(g)

    linked = [n for n in g if g.degree(n) > 0]
    isolated = [n for n in g if g.degree(n) == 0]

    pos = _separate(nx.spring_layout(g.subgraph(linked), k=0.70, iterations=900,
                                     seed=3, weight=None),
                    min_dist={"ar": 0.15, "en": 0.21}[lang])
    if lang != "ar":
        # The spring output is not centred on the origin, and in the Arabic
        # edition the foot row spans the plate and hides it. The Latin foot is
        # two columns, so the drift shows as a network pinned to one side.
        mid = sum(pos[n][0] for n in linked) / len(linked)
        pos = {n: (x - mid, y) for n, (x, y) in pos.items()}
    # Park the unconnected at the foot rather than letting the spring throw them
    # to the corners: they are a finding, not noise.
    #
    # Ten in a row works in Arabic and cannot work in Latin. "Muhammad al-Fadil
    # Ibn Ashur" is 27 characters, wider on its own than the whole cell a row of
    # ten allows, so the Latin edition sets them as two columns of five with the
    # name beside the dot instead of over it.
    foot = sorted(isolated)
    if lang == "ar":
        for i, n in enumerate(foot):
            pos[n] = (-1.16 + 0.255 * i, -1.30)
    else:
        for i, n in enumerate(foot):
            col, row = divmod(i, 5)
            pos[n] = (-1.30 + 1.40 * col, -1.14 - 0.075 * row)

    fig, ax = plt.subplots(figsize=(9.4, 7.6))
    ax.axis("off")
    for u, v, d in g.edges(data=True):
        for layer in sorted(d["layers"]):
            ls, lw = LAYER_STYLE[layer]
            ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]],
                    color=MUTED, lw=lw, ls=ls, alpha=0.6, zorder=1,
                    solid_capstyle="round")

    if lang != "ar":
        # Autoscale would otherwise fit the two foot columns, which occupy the
        # left of the plate, and push the network into the right third.
        ax.set_xlim(-1.45, 1.45)
    size = {n: 52 + 34 * g.degree(n) for n in g}
    colour = {n: COHORT_COLOUR.get(cohort_of.get(n, ""), MUTED) for n in g}
    _draw_nodes(ax, pos, linked, colour=colour, size=size, marker="o", zorder=4)
    ax.scatter([pos[n][0] for n in isolated], [pos[n][1] for n in isolated],
               s=[size[n] for n in isolated],
               c=[colour[n] for n in isolated], marker="o",
               linewidths=1.4, edgecolors=PAPER, alpha=0.42, zorder=4)

    labelled = sorted(g, key=lambda n: -g.degree(n))
    if lang != "ar":
        # The foot list is set by hand, so it is kept out of the collision run.
        labelled = [n for n in labelled if n not in set(foot)]
        for n in foot:
            ax.text(pos[n][0] + 0.05, pos[n][1], NAME[lang][n], ha="left",
                    va="center", fontsize=6.2, color=INK, zorder=6)
    _place_labels(ax, pos, [(n, NAME[lang][n]) for n in labelled],
                  size=6.2, colour=INK, lang=lang)

    handles = [Line2D([], [], marker="o", ls="none", mfc=COHORT_COLOUR[c],
                      mec=PAPER, ms=8, label=COHORT_EN[c]) for c in COHORTS]
    handles += [Line2D([], [], color=MUTED, ls=LAYER_STYLE[l][0],
                       lw=LAYER_STYLE[l][1], label=LAYER_EN[l])
                for l in ("tutelage", "office", "kinship", "membership")]
    ax.legend(handles=handles, fontsize=7.4, ncol=2,
              loc={"ar": "upper right", "en": "upper left"}[lang])

    headline(fig, "The 38 among themselves",
             f"Pairs of subjects the book ties together: {g.number_of_edges()} pairs "
             f"joining {len(linked)} of the 38. The {len(isolated)} shown faded along the foot "
             "connect only outward, to people the book does not give an essay of their own. "
             "Line style is the layer; a pair joined on more than one layer carries more "
             "than one line.", top=0.995)
    fig.subplots_adjust(top=0.884, bottom=0.045, left=0.02, right=0.98)
    save(fig, _name("fig03_aalam_subject_backbone", lang), SOURCE)


# --- fig 4: the lives ------------------------------------------------------
def fig_lives(lang: str = "ar") -> None:
    """Not a network: the three generations the author asserts, as life spans."""
    rows = []
    for pid, r in subjects.items():
        if r["birth_year"] and r["death_year"]:
            rows.append((r["cohort"], int(r["birth_year"]), int(r["death_year"]),
                         NAME[lang][pid]))
    rows.sort(key=lambda t: (COHORTS.index(t[0]), t[1]))

    fig, ax = plt.subplots(figsize=(9.0, 8.2))
    y = 0
    ticks, labels = [], []
    for cohort in COHORTS:
        block = [r for r in rows if r[0] == cohort]
        for _, b, d, name in block:
            ax.plot([b, d], [y, y], lw=5.2, color=COHORT_COLOUR[cohort],
                    solid_capstyle="round", zorder=3)
            ax.text(d + 5, y, f"{b}–{d}", va="center", ha="left",
                    fontsize=6.0, color=MUTED)
            ticks.append(y)
            labels.append(name)
            y -= 1
        y -= 0.9

    ax.set_yticks(ticks)
    ax.set_yticklabels(labels, fontsize=6.8, color=INK,
                       **({"fontfamily": ARABIC_FONT} if lang == "ar" else {}))
    ax.set_xlim(1580, 2010)
    ax.set_ylim(y + 0.4, 1.2)
    ax.set_xlabel("Year")
    ax.grid(axis="x", zorder=0)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)

    # The spans all run to the right, so the left half is empty -- but not at
    # the top, where the first cohort starts earliest of all and Aziza
    # Othmana's bar ran under the legend, nor in the middle, where the Latin
    # names reach furthest right. The foot is clear in both editions.
    ax.legend(handles=[Line2D([], [], color=COHORT_COLOUR[c], lw=5,
                              label=COHORT_EN[c]) for c in COHORTS],
              loc="lower left", fontsize=7.8)

    headline(fig, "Three generations, as the author divides them",
             "Life spans of the 37 subjects whose birth and death the volume both gives. "
             "The three cohorts are Zmerli's own division of his subjects and are recorded "
             "as his judgement, not as an attribute of the people. General Husayn is "
             "absent: the book prints his birth year as an ellipsis. Aziza Othmana sits a "
             "century clear of everyone else.", top=0.995)
    # The y-tick names live in this margin. "Muhammad al-Tahir Ibn Ashur" is
    # half as wide again as the Arabic it renders, so the Latin plate needs
    # more of the plate given over to it.
    # `bottom` has to clear the axis label as well as the ticks, or "Year"
    # sets on top of the source note.
    fig.subplots_adjust(top=0.886, bottom=0.115, right=0.975,
                        left={"ar": 0.20, "en": 0.28}[lang])
    save(fig, _name("fig04_aalam_lives", lang), SOURCE)


def _name(stem: str, lang: str) -> str:
    """The Arabic plates keep the names they were published under."""
    return stem if lang == "ar" else f"{stem}_en"


if __name__ == "__main__":
    for lang in ("ar", "en"):
        print(f"\n--- {lang} ---")
        fig_two_mode(lang)
        fig_tutelage(lang)
        fig_subject_backbone(lang)
        fig_lives(lang)
    n = len(list((ROOT / "figures").glob("*aalam*")))
    print(f"\ndone — {n} A'lam files in figures/")
