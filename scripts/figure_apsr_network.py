"""Publication network figure: the brokerage core, nodes sized by betweenness.

Writes ``figures/fig15_brokerage_network.{pdf,tif,png}``, the plotted node
table as ``figures/fig15_brokerage_network.csv``, and a LaTeX snippet with
caption and accessibility description as
``figures/fig15_brokerage_network.tex``.

Built to the published APSR / Cambridge artwork requirements rather than to
screen conventions. Each of these is a stated requirement, not a preference:

* **Readable in greyscale.** APSR: figures "should be readable in
  grayscale", and if colour is used, vary it "not by shade, but by intensity
  and tones", because "classic blue, black, red and green all look the same"
  once printed. This figure is therefore *pure greyscale* -- which also
  avoids the colour-print charge, which APSR bills to the author.
* **Tones between 15% and 85% black, in increments of at least 15-20%.**
  The three node classes sit at 20%, 55% and 85%, so the smallest step
  between them is 30 points, and none is outside the band.
* **No font smaller than 9pt at final size.** Everything here is 9pt.
* **No line weight below 0.3pt at final size**, with prominent lines near
  1pt. Ties are 0.4pt, marker outlines and label leaders 0.5-0.6pt.
* **Resolution**: line art at 1000 dpi. A vector PDF is emitted for
  typesetting, plus a 1000 dpi LZW-compressed greyscale TIFF, which is the
  format Cambridge names as preferred.
* **Font**: Liberation Sans, which is metrically identical to Arial, one of
  the recommended faces.
* **Accessibility.** APSR requires an image description (WCAG 2.1 AA), so
  one is generated into the .tex alongside the caption.

Sized at 4.5 x 5.49in (114 x 139mm) so it fits a single-column text block
at scale 1.0. If it is scaled DOWN on inclusion the 9pt floor is breached,
so the caption snippet sets an explicit width rather than \\textwidth.

Why this is not the whole network
---------------------------------

The full graph is 23,274 entities and 31,457 ties. At 114mm that is roughly
2,000 nodes per square inch: an unreadable speckle in which node area
carries no information at all, which is the opposite of the point. The
exploratory version of that map exists in ``figure_core_periphery.py`` and
is 18.4 inches wide.

So this draws the **brokerage core**: the 200 entities with the highest
betweenness, reduced to the giant component of the subgraph they induce
(191 nodes, 397 ties). Those 200 hold 39.3% of all betweenness in the
network. The selection is on the plotted quantity and the caption says so
plainly; the alternative structural reduction, the k>=5 core, was rejected
because it drops the second and third largest brokers in the network
(Présidence de la République and the RCD central committee, both k=4).
"""
from __future__ import annotations

import argparse
import collections
import csv
import math
import pickle
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib

matplotlib.use("Agg")

import igraph as ig
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon
from matplotlib.path import Path as MplPath
from scipy.spatial import ConvexHull

FIGS = ROOT / "figures"
FIGS.mkdir(exist_ok=True)
CACHE = ROOT / "data" / "interim" / "core_periphery.pkl"
PROC = ROOT / "data" / "processed" / "multiplex"
STEM = "fig15_brokerage_network"
STEM_DATED = "fig16_brokerage_network_pre2011"

TOP_N = 400
N_LABELS = 16
HULL_MIN = 6         # smallest community given a hull
HULL_MAX_INTRUDER_FRAC = 0.25  # non-members a hull may enclose
CURVE = 0.13      # edge arc, as a fraction of chord length

# Greyscale only, inside the 15-85% band the artwork guide specifies, in
# steps far larger than the 15-20% minimum increment.
INK = "#1A1A1A"          # text
EDGE = "#B0B0B0"         # ~31% black, at 0.4pt so it survives print
T_PERSON = "#262626"     # 85%
T_STATE = "#737373"      # 55%
T_PRIVATE = "#CCCCCC"    # 20%
OUTLINE = "#1A1A1A"

# Edge tones. Kind is derived from the endpoint classes, so it needs no
# extra data and means the same thing in both universes.
E_STATE = "#8C8C8C"      # a tie into a state body or party
E_CORP = "#C2C2C2"       # person to firm, association or union
E_ORGORG = "#A8A8A8"     # organisation to organisation, drawn dashed
E_KIN = "#6E6E6E"        # person to person
EDGE_STYLE = {
    "state":  (E_STATE, "solid", 0.55, "tie into a state body or party"),
    "person": (E_CORP, "solid", 0.40, "person to firm, association, union"),
    "orgorg": (E_ORGORG, (0, (2.2, 1.4)), 0.50, "organisation to organisation"),
    "kin":    (E_KIN, (0, (0.9, 1.1)), 0.55, "person to person"),
}
EDGE_ORDER = ["person", "state", "orgorg", "kin"]

# Community hull wash. Below the artwork guide's 15% floor on purpose: this
# is a ground, not a category to be told apart, and the 0.4pt outline is
# what guarantees the grouping survives print if the tint does not.
HULL_FILL = "#F0F0F0"
HULL_LINE = "#C8C8C8"

# label -> (tone, marker, legend caption); shape carries identity as well as
# tone, so the classes never rest on lightness alone
CLASSES = {
    "person": (T_PERSON, "o", "Natural persons"),
    "state": (T_STATE, "s", "State bodies and parties"),
    "private": (T_PRIVATE, "s", "Firms, associations, unions"),
}
ORDER = ["person", "state", "private"]

MIN_PT = 9.0

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white",
    "savefig.facecolor": "white",
    "font.family": "Liberation Sans",   # metrically identical to Arial
    "font.size": MIN_PT, "pdf.fonttype": 42, "ps.fonttype": 42,
    "legend.frameon": False, "axes.linewidth": 0.5,
    # Matplotlib renders $...$ in DejaVu by default, which would mix a
    # second typeface into a figure set in the Arial-metric face.
    "mathtext.fontset": "custom", "mathtext.rm": "Liberation Sans",
    "mathtext.it": "Liberation Sans:italic",
    "mathtext.bf": "Liberation Sans:bold",
})


def klass(node_class: str) -> str:
    if node_class == "individual":
        return "person"
    if node_class in ("state body", "party / parliamentary bloc"):
        return "state"
    return "private"


# At 114mm, a 9pt rendering of "Banque Internationale Arabe de Tunisie"
# is a third of the frame wide. These institutions all have conventional
# short forms, so the figure uses them and the caption expands every one it
# draws -- generated from this map, so the two cannot drift apart.
SHORT = {
    "ETAT TUNISIEN": ("État Tunisien", None),
    "PRÉSIDENCE DE LA RÉPUBLIQUE": ("Présidence", "Présidence de la République"),
    "RCD'S CENTRAL COMMITTEE": ("RCD", "central committee of the RCD"),
    "BANQUE INTERNATIONALE ARABE DE TUNISIE BIAT":
        ("BIAT", "Banque Internationale Arabe de Tunisie"),
    "MINISTERE DE L'ECONOMIE NATIONALE":
        ("Min. Économie", "Ministère de l'Économie Nationale"),
    "MOHAMED TRABELSI": ("M. Trabelsi", "Mohamed Trabelsi"),
    "MOUVEMENT NIDAA TOUNES": ("Nidaa Tounes", "Mouvement Nidaa Tounes"),
    "SOCIETE TUNISIENNE DE BANQUE": ("STB", "Société Tunisienne de Banque"),
    "BANQUE NATIONALE AGRICOLE BNA": ("BNA", "Banque Nationale Agricole"),
    "FAYCEL DERBEL": ("F. Derbel", "Faycel Derbel"),
    "CHAMBRE TUNISO-FRANCAISE DE COMMERCE ET D'INDUSTRIE":
        ("Ch. Tuniso-Française", "Chambre Tuniso-Française de Commerce "
                                 "et d'Industrie"),
    "UNION BANCAIRE POUR LE COMMERCE ET L'INDUSTRIE UBCI":
        ("UBCI", "Union Bancaire pour le Commerce et l'Industrie"),
    "ATD SICAR": ("ATD SICAR", None),
    "SIM SICAR": ("SIM SICAR", None),
    "SICAR INVEST": ("SICAR Invest", None),
    "AMEN BANK": ("Amen Bank", None),
    "STB SICAR": ("STB SICAR", None),
    "MINISTERE DE L'EDUCATION ET DES SCIENCES":
        ("Min. Éducation", "Ministère de l'Éducation et des Sciences"),
    "MINISTERE DE LA COOPERATION INTERNATIONALE ET DE L'INVESTISSEMENT "
    "EXTERIEUR":
        ("Min. Coopération", "Ministère de la Coopération Internationale "
                             "et de l'Investissement Extérieur"),
    "MINISTERE DE L'AGRICULTURE, DE L'ENVIRONNEMENT ET DES RESSOURCES "
    "HYDRAULIQUES":
        ("Min. Agriculture", "Ministère de l'Agriculture, de "
                             "l'Environnement et des Ressources Hydrauliques"),
    "COMPAGNIE DASSURANCES ET DE REASSURANCES ASTREE":
        ("ASTREE", "Compagnie d'Assurances et de Réassurances ASTREE"),
    "SOCIETE TUNISIENNE DES FILTRES MISFAT":
        ("MISFAT", "Société Tunisienne des Filtres MISFAT"),
    "MINISTERE DES AFFAIRES ETRANGERES":
        ("Min. Aff. étrangères", "Ministère des Affaires Étrangères"),
    "MINISTERE DE LA CULTURE": ("Min. Culture", None),
    "INTERNATIONAL SICAR": ("International SICAR", None),
}

_KEEP_UPPER = {"RCD", "BIAT", "BNA", "STB", "UBCI", "SICAR", "ATD", "SIM",
               "GAT", "MAC", "PAF", "SA", "BT", "MISFAT", "ASTREE"}

# The gazette layer stores labels unaccented ("PRESIDENCE DE LA REPUBLIQUE"),
# the seed layer accented. Keys are matched accent-folded so one map serves
# both; without this the pre-2011 figure fell through to the truncating
# fallback and drew three separate ministries as "Ministere De…".
_FOLD = str.maketrans("ÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜÝàáâãäåçèéêëìíîïñòóôõöùúûüý",
                      "AAAAAACEEEEIIIINOOOOOUUUUYaaaaaaceeeeiiiinooooouuuuy")

# Accents the abbreviator restores on the ministry stem it keeps.
_ACCENTED = {"Economie": "Économie", "Education": "Éducation",
             "Etrangeres": "Étrangères", "Cooperation": "Coopération",
             "Interieur": "Intérieur", "Sante": "Santé",
             "Defense": "Défense", "Developpement": "Développement",
             "Equipement": "Équipement", "Energie": "Énergie"}

_MINISTRY = re.compile(
    r"^MINISTERE\s+(?:DE\s+L['’]|DE\s+LA\s+|DES\s+|DU\s+|DE\s+)?(.*)$")


def _norm(raw: str) -> str:
    return " ".join(raw.split()).translate(_FOLD).upper()


_SHORT_FOLDED = {_norm(k): v for k, v in SHORT.items()}


def short_label(raw: str) -> str:
    """The form drawn on the figure."""
    key = _norm(raw)
    if key in _SHORT_FOLDED:
        return _SHORT_FOLDED[key][0]

    m = _MINISTRY.match(key)
    if m:
        # Keep the distinguishing head of the portfolio: cut at the first
        # comma or conjunction, then at most two words. Truncating from the
        # left instead yields "Ministere De…", which names nothing.
        stem = re.split(r",| ET ", m.group(1))[0].split()
        head = " ".join(w.capitalize() for w in stem[:2])
        head = " ".join(_ACCENTED.get(w, w) for w in head.split())
        return f"Min. {head}" if head else "Ministère"

    words = [w if w.upper() in _KEEP_UPPER else w.capitalize()
             for w in " ".join(raw.split()).split()]
    out = " ".join(words)
    if len(out) <= 20:
        return out
    # A trailing all-caps brand is the name people use (…FILTRES MISFAT).
    tail = words[-1]
    if len(tail) >= 4 and tail.upper() in _KEEP_UPPER:
        return tail
    return out[:19].rsplit(" ", 1)[0] + "…"


def expansion(raw: str) -> str | None:
    """The gloss the caption must carry, if the drawn form is abbreviated."""
    key = _norm(raw)
    if key in _SHORT_FOLDED and _SHORT_FOLDED[key][1]:
        return f"{_SHORT_FOLDED[key][0]}, {_SHORT_FOLDED[key][1]}"
    # Only curated expansions are emitted. Deriving one mechanically
    # title-cased French badly ("Compagnie Dassurances Et De Reassurances"),
    # which reads worse in a caption than leaving the short form to stand.
    return None


def load() -> dict:
    if not CACHE.exists():
        raise SystemExit(
            f"missing {CACHE.relative_to(ROOT)} — run "
            f"scripts/figure_core_periphery.py first")
    with CACHE.open("rb") as fh:
        return pickle.load(fh)


def pooled_universe() -> dict:
    """The undated, all-sources graph behind fig15."""
    d = load()
    return {"nodes": d["nodes"], "bc": d["bc"], "edges": d["edges"],
            "cls": [klass(d["cls"][n]) for n in d["nodes"]],
            "labels": [d["labels"][n] for n in d["nodes"]],
            "dropped_blank": d["n_blank"]}


def dated_universe(before: str) -> dict:
    """Gazette-evidenced ties whose earliest evidence predates ``before``.

    The date filter is not a filter on time alone; it is exactly a filter on
    **source**, and that has to be understood before the figure is read.
    Every gazette-evidenced spell in this dataset carries a date and every
    seed-derived spell carries none -- the split is total, 22,903 against
    27,585, with no partially-dated tier. So restricting to ties evidenced
    before a date drops the entire seed layer.

    That is the correct treatment rather than a shortfall. Seed ties are
    recorded as ``evidence_tier='seed_undated'`` with
    ``onset_rule='seed_current_tie'`` and ``evidence_n=0``: they assert a
    *present* affiliation from a roster compiled long after 2011. Carrying
    them into a pre-revolution figure would be an anachronism, not extra
    coverage. What it does mean is that this graph and the pooled one are
    different objects and their betweenness is not comparable, which is why
    it is recomputed here rather than carried across.
    """
    first: dict[str, str] = {}
    with (PROC / "spell_observations.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            dt = (r["obs_date"] or "").strip()
            sid = r["spell_id"]
            if dt and (sid not in first or dt < first[sid]):
                first[sid] = dt

    labels: dict[str, str] = {}
    is_state: set[str] = set()
    persons: set[str] = set()
    pairs: set[tuple[str, str]] = set()
    kept = collections.Counter()

    with (PROC / "spells.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            cand = [x for x in ((r["onset"] or "").strip(),
                                first.get(r["spell_id"], "")) if x]
            if not cand or min(cand) >= before:
                continue
            p, o = r["person_id"], r["org_id"]
            persons.add(p)
            labels.setdefault(p, r["person_label"])
            labels[o] = r["org_label"]
            # Classify from the tie the pipeline already coded, not from a
            # regex on the label: "SOCIETE REGIONALE ... GOUVERNORAT DE
            # BEJA" is a firm, and a label regex calls it a state body.
            if r["tie_class"] == "state_office":
                is_state.add(o)
            pairs.add((p, o))
            kept[r["tie_class"]] += 1

    n_oo = 0
    with (PROC / "org_tie_spells.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            on = (r["onset"] or "").strip()
            if not on or on >= before:
                continue
            labels.setdefault(r["holder_id"], r["holder_label"])
            labels.setdefault(r["target_id"], r["target_label"])
            pairs.add((r["holder_id"], r["target_id"]))
            n_oo += 1

    for nid in labels:
        if nid.split("_")[0] in ("GOV", "PARTYSTR"):
            is_state.add(nid)

    # An unlabelled organisation held 590 pre-2011 offices here -- more than
    # any ministry, and the largest node in the graph. It is OCR damage, and
    # a node that is not an entity cannot broker anything. Same rule as the
    # exploratory figure: drop only the genuinely blank, never the merely
    # short, since GAT, MAC and PAF are real firms.
    blank = {n for n in labels
             if n not in persons and not (labels[n] or "").strip()}
    pairs = {(a, b) for a, b in pairs if a not in blank and b not in blank}

    nodes = sorted({n for pr in pairs for n in pr})
    idx = {n: i for i, n in enumerate(nodes)}
    edges = sorted({(idx[a], idx[b]) for a, b in pairs})

    g = ig.Graph(n=len(nodes), edges=edges)
    bc = g.betweenness()

    return {
        "nodes": nodes, "bc": bc, "edges": edges,
        "cls": ["person" if n in persons else
                "state" if n in is_state else "private" for n in nodes],
        "labels": [labels[n] for n in nodes],
        "dropped_blank": len(blank),
        "kept_by_class": dict(kept), "n_org_ties": n_oo,
    }


def brokerage_core(d: dict, top_n: int) -> dict:
    """The top-N by betweenness, reduced to the giant component they induce."""
    nodes, bc = d["nodes"], d["bc"]
    order = sorted(range(len(nodes)), key=lambda i: -bc[i])
    keep = set(order[:top_n])
    sub = [(a, b) for a, b in d["edges"] if a in keep and b in keep]

    adj = collections.defaultdict(set)
    for a, b in sub:
        adj[a].add(b)
        adj[b].add(a)

    seen, comps = set(), []
    for s in keep:
        if s in seen:
            continue
        stack, comp = [s], [s]
        seen.add(s)
        while stack:
            for v in adj[stack.pop()]:
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
                    comp.append(v)
        comps.append(comp)

    giant = set(max(comps, key=len))
    idx = {g: j for j, g in enumerate(sorted(giant, key=lambda i: -bc[i]))}
    return {
        "members": sorted(giant, key=lambda i: -bc[i]),
        "idx": idx,
        "edges": [(idx[a], idx[b]) for a, b in sub
                  if a in giant and b in giant],
        "share": sum(bc[i] for i in keep) / sum(bc),
        "n_selected": len(keep),
        "n_components": len(comps),
    }


def layout(core: dict, comm: list[int] | None = None,
           seed: int = 7, w_in: float = 8.0) -> np.ndarray:
    """Force layout, optionally pulled together within communities.

    Laying out the raw graph and then hulling the communities does not work
    here: every community holds both central hubs and peripheral chains, so
    each hull is a wedge running from the middle to the rim and 22 of them
    tile the whole frame. Weighting intra-community ties above inter-
    community ones separates the clusters spatially first, which is what
    makes a hull mean anything.
    """
    g = ig.Graph(n=len(core["members"]), edges=core["edges"])
    # igraph wants the stdlib Random interface (it calls .gauss/.random),
    # not a numpy Generator.
    ig.set_random_number_generator(random.Random(seed))
    if comm is None:
        pos = np.asarray(g.layout_kamada_kawai(maxiter=6000).coords)
    else:
        wts = [w_in if comm[a] == comm[b] else 1.0
               for a, b in core["edges"]]
        pos = np.asarray(g.layout_fruchterman_reingold(
            niter=2000, weights=wts).coords)
    # Fit the bounding box to [-1,1] ISOTROPICALLY -- scaling the axes
    # independently would stretch the drawing and make graph distances lie.
    lo, hi = pos.min(axis=0), pos.max(axis=0)
    pos -= (lo + hi) / 2
    return pos / (max(hi - lo) / 2)


OBSTACLE_MIN_PT = 7.0


def node_boxes(ax, pos, size, min_pt: float = OBSTACLE_MIN_PT) -> list[tuple]:
    """Display-space boxes for the markers, so labels can avoid them.

    Only the visually significant nodes count as obstacles. Treating all
    191 as obstacles left almost no free position in the dense core and
    placed 3 labels of 12; a 9pt label with a white halo reads perfectly
    over a 3pt dot or a hairline edge, and only collides meaningfully with
    a marker big enough to be identified in its own right.
    """
    dpi = ax.figure.dpi
    xy = ax.transData.transform(pos)
    out = []
    for j, (px, py) in enumerate(xy):
        dia = 2 * np.sqrt(size[j] / np.pi)
        if dia < min_pt:
            continue
        half = (dia / 2) * dpi / 72.0
        out.append((px - half, py - half, px + half, py + half))
    return out


def edge_kind(ca: str, cb: str) -> str:
    """Classify a tie from the classes of its ends.

    Derived rather than looked up, so it carries the same meaning in the
    pooled and the date-restricted graph without either having to store an
    extra column.
    """
    if "state" in (ca, cb):
        return "state"
    if ca == "person" and cb == "person":
        return "kin"
    if ca != "person" and cb != "person":
        return "orgorg"
    return "person"


def communities(core: dict, seed: int = 7) -> list[int]:
    """Louvain membership, seeded.

    community_multilevel is randomised. Left unseeded it returned a
    different partition on each run, which changed the layout weights and
    the number of hulls drawn -- a figure that will not regenerate
    identically is not publishable.
    """
    ig.set_random_number_generator(random.Random(seed))
    g = ig.Graph(n=len(core["members"]), edges=core["edges"])
    return g.community_multilevel().membership


def _hull_ring(pts: np.ndarray, pad: float) -> np.ndarray | None:
    """Convex hull of a community, pushed out from its centroid by ``pad``."""
    if len(pts) < 3:
        return None
    uniq = np.unique(pts, axis=0)
    if len(uniq) < 3:
        return None
    try:
        ring = uniq[ConvexHull(uniq).vertices]
    except Exception:
        return None                      # degenerate (collinear) community
    c = ring.mean(axis=0)
    v = ring - c
    n = np.linalg.norm(v, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return c + v + (v / n) * pad


def _area(ring: np.ndarray) -> float:
    x, y = ring[:, 0], ring[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


def draw_hulls(ax, pos: np.ndarray, comm: list[int], pad: float = 0.035) -> int:
    """Light grounds behind the COMPACT communities only.

    Hulling every community was tried first and is wrong for this graph.
    Most communities here are a hub with long chains hanging off it, and the
    convex hull of a star is a huge spiky sliver: 22 of them overlapped
    across the whole frame, which looked busier while asserting a spatial
    grouping that does not exist. A hull is only drawn where the members
    really do occupy a compact patch, so it marks the cohesive clusters and
    stays off the spokes.
    """
    groups = collections.defaultdict(list)
    for i, c in enumerate(comm):
        groups[c].append(i)
    drawn = 0
    for c, mem in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        if len(mem) < HULL_MIN:
            continue
        ring = _hull_ring(pos[mem], pad)
        if ring is None:
            continue
        # The decisive test: does the hull enclose nodes that are not in
        # the community? A wedge running from the hub out to the rim sweeps
        # up other groups on the way, and outlining it asserts a grouping
        # that is not there. Bounding-box area and aspect both failed to
        # catch this -- a diagonal wedge has an unremarkable bbox.
        inside = MplPath(ring).contains_points(pos)
        intruders = int(inside.sum()) - len(mem)
        if intruders > HULL_MAX_INTRUDER_FRAC * len(mem):
            continue
        ax.add_patch(Polygon(ring, closed=True, facecolor=HULL_FILL,
                             edgecolor=HULL_LINE, linewidth=0.4,
                             joinstyle="round", zorder=0))
        drawn += 1
    return drawn


def curved_segments(pos: np.ndarray, edges, bend: float = CURVE, n: int = 14):
    """Quadratic arcs instead of straight chords.

    A star-shaped graph drawn with straight lines collapses many ties onto
    the same pixels; arcing them apart lets a reader follow one tie out of a
    hub, and gives the drawing some texture.
    """
    out = []
    t = np.linspace(0, 1, n)[:, None]
    for a, b in edges:
        p0, p2 = pos[a], pos[b]
        mid = (p0 + p2) / 2
        d = p2 - p0
        normal = np.array([-d[1], d[0]])
        ctrl = mid + normal * bend
        out.append((1 - t) ** 2 * p0 + 2 * (1 - t) * t * ctrl + t ** 2 * p2)
    return out


def place_labels(ax, items, *, fontsize=MIN_PT, obstacles=None):
    """Greedy non-overlapping placement.

    Must be called only after the axes limits and aspect are final: the
    overlap test is in display coordinates, and re-limiting the axes
    afterwards moves every label without re-testing it.

    Returns (count drawn, raw labels drawn) so the caption can gloss
    exactly the abbreviations that made it onto the figure.
    """
    fig = ax.figure
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    x0, x1 = sorted(ax.transData.transform([(ax.get_xlim()[0], 0),
                                            (ax.get_xlim()[1], 0)])[:, 0])
    y0, y1 = sorted(ax.transData.transform([(0, ax.get_ylim()[0]),
                                            (0, ax.get_ylim()[1])])[:, 1])
    placed, drawn, shown = list(obstacles or []), 0, []
    for text, (x, y), r, raw in items:
        near = [(0, r + 7), (0, -r - 7), (r + 5, 0), (-r - 5, 0),
                (r + 4, r + 5), (-r - 4, r + 5), (r + 4, -r - 5),
                (-r - 4, -r - 5), (0, r + 16), (0, -r - 16)]
        # Fallback ring: further out, reached by a leader line. The top
        # brokers sit in the densest part of the drawing, so for some of
        # them no adjacent slot exists at any font size.
        far = [(np.cos(t) * (r + d), np.sin(t) * (r + d))
               for d in (30, 44, 60)
               for t in np.deg2rad(np.arange(0, 360, 30))]

        for dx, dy in near + far:
            lead = (dx, dy) in far
            ha = "center" if abs(dx) < 3 else ("left" if dx > 0 else "right")
            ann = ax.annotate(
                text, (x, y), xytext=(dx, dy), textcoords="offset points",
                ha=ha, va="center", fontsize=fontsize, color=INK, zorder=9,
                path_effects=[pe.withStroke(linewidth=2.4,
                                            foreground="white")],
                arrowprops=dict(arrowstyle="-", color=INK, lw=0.6,
                                shrinkA=1, shrinkB=r + 1.5,
                                patchA=None, patchB=None) if lead else None)
            bb = ann.get_window_extent(renderer=rend)
            box = (bb.x0 - 1.5, bb.y0 - 1.0, bb.x1 + 1.5, bb.y1 + 1.0)
            outside = (box[0] < x0 or box[2] > x1
                       or box[1] < y0 or box[3] > y1)
            clash = any(box[0] < p[2] and box[2] > p[0]
                        and box[1] < p[3] and box[3] > p[1] for p in placed)
            if outside or clash:
                ann.remove()
                continue
            placed.append(box)
            drawn += 1
            shown.append(raw)
            break
    return drawn, shown


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--width", type=float, default=4.5,
                    help="final width in inches (4.5in = 114mm)")
    ap.add_argument("--top", type=int, default=TOP_N)
    ap.add_argument("--labels", type=int, default=N_LABELS)
    ap.add_argument("--dpi", type=int, default=1000,
                    help="raster dpi; Cambridge asks 1000 for line art")
    ap.add_argument("--before", metavar="YYYY-MM-DD", default=None,
                    help="restrict to ties evidenced before this date; "
                         "this selects the gazette layer, since every "
                         "seed-derived tie is undated")
    args = ap.parse_args(argv)

    stem = STEM if args.before is None else STEM_DATED
    d = pooled_universe() if args.before is None else dated_universe(args.before)
    nodes, bc, cls, labels = d["nodes"], d["bc"], d["cls"], d["labels"]
    core = brokerage_core(d, args.top)
    mem = core["members"]
    comm = communities(core)
    pos = layout(core, comm)

    # Three stacked bands -- legend, network, size key -- each in its own
    # axes. Sharing one axes put the key and legend inside the drawing area
    # and cost the network most of its usable height.
    #
    # The figure's HEIGHT is derived from the layout's own aspect rather
    # than fixed. With a fixed near-square frame and a layout half as tall
    # as it is wide, preserving aspect (which a force layout requires --
    # scaling the axes independently makes graph distances lie) left a
    # third of the canvas empty.
    span = pos.max(axis=0) - pos.min(axis=0)
    data_ar = float(span[1] / span[0]) if span[0] > 0 else 1.0
    data_ar = min(max(data_ar, 0.55), 1.45)
    net_w_in = args.width * 0.988
    net_h_in = net_w_in * data_ar
    leg_h_in, key_h_in = 0.62, 0.58
    fig_h = net_h_in + leg_h_in + key_h_in
    fig = plt.figure(figsize=(args.width, fig_h))
    ax_leg = fig.add_axes([0.012, 1 - (leg_h_in - 0.04) / fig_h,
                           0.976, (leg_h_in - 0.05) / fig_h])
    ax = fig.add_axes([0.006, key_h_in / fig_h, 0.988, net_h_in / fig_h])
    ax_key = fig.add_axes([0.012, 0.006, 0.976, (key_h_in - 0.06) / fig_h])
    for a in (ax_leg, ax, ax_key):
        a.set_axis_off()

    # Limits and aspect BEFORE any label placement: the collision test
    # works in display coordinates, so changing the data limits afterwards
    # silently invalidates every box it checked.
    ax.set_aspect("equal")
    frame_ar = net_h_in / net_w_in
    half = np.abs(pos).max(axis=0) * 1.02 + 0.015
    # Grow the short side to the frame's aspect rather than scaling the
    # axes independently, which would stretch the layout and make graph
    # distances lie. With the frame now cut to the data's own aspect there
    # is very little left to grow.
    if half[1] / half[0] < frame_ar:
        half[1] = half[0] * frame_ar
    else:
        half[0] = half[1] / frame_ar
    ax.set_xlim(-half[0], half[0])
    ax.set_ylim(-half[1], half[1])

    n_hulls = draw_hulls(ax, pos, comm)

    # Ties grouped by kind so each gets its own tone, dash and weight. One
    # flat grey collection made a 400-node graph read as a single texture.
    ekind = [edge_kind(cls[mem[a_]], cls[mem[b_]]) for a_, b_ in core["edges"]]
    n_by_kind = collections.Counter(ekind)
    for kind in EDGE_ORDER:
        sel = [e for e, k in zip(core["edges"], ekind) if k == kind]
        if not sel:
            continue
        colour, dash, lw, _ = EDGE_STYLE[kind]
        ax.add_collection(LineCollection(
            curved_segments(pos, sel), colors=colour, linewidths=lw,
            linestyles=dash, zorder=1,
            capstyle="round"))

    # Node AREA strictly proportional to betweenness: matplotlib's `s` is
    # area in points squared, so s = k * betweenness with no exponent.
    bmax = max(bc[i] for i in mem)
    d_max_pt = 17.0
    k = (np.pi * (d_max_pt / 2) ** 2) / bmax
    size = {j: k * bc[i] for j, i in enumerate(mem)}

    for name in ORDER:
        tone, marker, _ = CLASSES[name]
        pool = [j for j, i in enumerate(mem) if cls[i] == name]
        if not pool:
            continue
        ax.scatter(pos[pool, 0], pos[pool, 1], s=[size[j] for j in pool],
                   facecolors=tone, marker=marker, linewidths=0.5,
                   edgecolors=OUTLINE, zorder=3 if name == "person" else 2)

    handles = [Line2D([], [], marker=CLASSES[n][1], ls="none",
                      markerfacecolor=CLASSES[n][0], markeredgecolor=OUTLINE,
                      markeredgewidth=.5, markersize=7, label=CLASSES[n][2])
               for n in ORDER]
    handles += [Line2D([], [], color=EDGE_STYLE[k][0], lw=EDGE_STYLE[k][2] * 2.4,
                       ls=EDGE_STYLE[k][1], label=EDGE_STYLE[k][3])
                for k in EDGE_ORDER if n_by_kind.get(k)]
    ax_leg.legend(handles=handles, loc="upper left", bbox_to_anchor=(0, 1.02),
                  ncol=2, fontsize=MIN_PT, labelcolor=INK, handletextpad=.5,
                  labelspacing=.34, columnspacing=1.1, handlelength=1.9,
                  borderpad=0)

    _size_key(ax_key, k, bmax)

    top = list(range(min(args.labels, len(mem))))
    # A white ring behind each labelled node, so a name can be tied to its
    # marker even where the community ground runs behind it.
    ax.scatter(pos[top, 0], pos[top, 1],
               s=[size[j] * 1.6 + 15 for j in top], facecolors="none",
               edgecolors="white", linewidths=1.1, zorder=2.5)
    drawn, shown = place_labels(
        ax,
        [(short_label(labels[mem[j]]), pos[j],
          np.sqrt(size[j] / np.pi), labels[mem[j]]) for j in top],
        obstacles=node_boxes(ax, pos, size))

    _write_csv(stem, mem, nodes, bc, cls, labels, pos)
    _write_tex(stem, mem, core, labels, cls, drawn, shown, args, d)

    pdf = FIGS / f"{stem}.pdf"
    fig.savefig(pdf)
    png = FIGS / f"{stem}.png"
    fig.savefig(png, dpi=args.dpi)
    plt.close(fig)

    tif = _write_tiff(png, args.dpi)
    for p in (pdf, png, tif):
        print(f"  {p.relative_to(ROOT)}  {p.stat().st_size / 1024:.0f} KB")
    print(f"  {len(mem)} nodes, {len(core['edges'])} ties; top "
          f"{core['n_selected']} hold {100 * core['share']:.1f}% of all "
          f"betweenness")
    print(f"  labels drawn: {drawn} of {len(top)} requested")
    print(f"  communities {len(set(comm))}, hulls drawn {n_hulls}; "
          f"ties by kind {dict(n_by_kind)}")
    print(f"  node diameters {2 * np.sqrt(min(size.values()) / np.pi):.1f}"
          f"–{2 * np.sqrt(max(size.values()) / np.pi):.1f} pt")
    return 0


def _nice(v: float) -> float:
    """Round to a 1/2/2.5/5 x 10^n step, so key values read as round numbers."""
    if v <= 0:
        return 1.0
    e = 10 ** math.floor(math.log10(v))
    for mult in (1, 2, 2.5, 5):
        if v <= mult * e:
            return mult * e
    return 10 * e


def _nice_down(v: float) -> float:
    """Largest 1/2/2.5/5 x 10^n step not exceeding v."""
    if v <= 0:
        return 1.0
    e = 10 ** math.floor(math.log10(v))
    best = e
    for mult in (1, 2, 2.5, 5):
        if mult * e <= v:
            best = mult * e
    return best


def _fmt(v: float) -> str:
    return f"{v / 1e6:g}M" if v >= 1e6 else f"{v / 1e3:g}k"


def _size_key(ax, k: float, bmax: float) -> None:
    """A size key, without which an area encoding cannot be decoded.

    Drawn in its own axes in axes-fraction coordinates, so the reference
    circles and their values cannot fall outside the canvas.
    """
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    # Steps derived from the graph actually drawn. Hardcoding 5/15/35M
    # suited the pooled figure and silently emptied the key on the
    # pre-2011 graph, whose maximum is an order of magnitude smaller.
    # The top step rounds DOWN: rounding up drew a reference circle larger
    # than any node in the figure, which reads as a node that is not there.
    # Each step a quarter of the one above it, so the three circles are
    # plainly different sizes. Deriving them from bmax/8 and bmax/3 put 20M
    # and 25M side by side, which reads as one circle drawn twice.
    top = _nice_down(bmax)
    steps = sorted({_nice_down(top / 16), _nice_down(top / 4), top})

    ax.text(0, 0.93, "Node area proportional to betweenness centrality",
            ha="left", va="top", fontsize=MIN_PT, color=INK,
            transform=ax.transAxes)

    # Values go to the RIGHT of each circle, not below: the band is only
    # about 40pt tall, and a label under the largest circle fell off the
    # bottom of the canvas.
    band_pt = ax.figure.get_figwidth() * 72 * ax.get_position().width
    x = 0.012
    for m in steps:
        dia = 2 * np.sqrt((k * m) / np.pi)          # points
        ax.scatter([x + (dia / 2) / band_pt], [0.34], s=k * m,
                   facecolors="none", edgecolors=OUTLINE, linewidths=0.5,
                   transform=ax.transAxes, clip_on=False, zorder=4)
        x += dia / band_pt + 3.0 / band_pt
        ax.text(x, 0.34, _fmt(m), ha="left", va="center",
                fontsize=MIN_PT, color=INK, transform=ax.transAxes)
        x += 26.0 / band_pt


def _write_tiff(png: Path, dpi: int) -> Path:
    """Greyscale LZW TIFF at the stated dpi — Cambridge's preferred format."""
    from PIL import Image

    tif = png.with_suffix(".tif")
    with Image.open(png) as im:
        im.convert("L").save(tif, format="TIFF", compression="tiff_lzw",
                             dpi=(dpi, dpi))
    return tif


def _write_csv(stem, mem, nodes, bc, cls, labels, pos) -> None:
    path = FIGS / f"{stem}.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["rank", "node_id", "label", "draw_class", "betweenness",
                    "x", "y"])
        for j, i in enumerate(mem):
            w.writerow([j + 1, nodes[i], labels[i], cls[i], f"{bc[i]:.1f}",
                        f"{pos[j][0]:.4f}", f"{pos[j][1]:.4f}"])
    print(f"  wrote {path.relative_to(ROOT)}")


def _write_tex(stem, mem, core, labels, cls, drawn, shown, args, uni) -> None:
    n_person = sum(1 for i in mem if cls[i] == "person")
    n_state = sum(1 for i in mem if cls[i] == "state")
    n_priv = len(mem) - n_person - n_state

    # Gloss every abbreviation that actually reached the figure, so the
    # caption can never promise an expansion the drawing does not use or
    # omit one it does.
    gloss = [g for g in (expansion(labels[i]) for i in
                         [mem[k] for k in range(len(mem))
                          if labels[mem[k]] in shown]) if g]
    seen, uniq = set(), []
    for g in gloss:
        if g not in seen:
            seen.add(g)
            uniq.append(g)
    gloss_tex = (" Abbreviations: " + "; ".join(uniq) + "." if uniq else "")

    if args.before is None:
        head = "The brokerage core of the Tunisian elite network."
        scope = (rf"""Selection is therefore on
  the quantity the node areas encode; the full network of 23,274 entities
  and 31,457 ties cannot be rendered legibly at page width. Ties are
  undirected and undated, pooling shareholding, board and governing-body
  membership, kinship, party and parliamentary structures, and the seed
  roster, over 1957--2026.""")
    else:
        head = (f"The brokerage core of the Tunisian elite network before "
                f"{args.before}.")
        k = uni["kept_by_class"]
        scope = (rf"""Ties are those evidenced in the
  \emph{{Journal Officiel}} before {args.before}, the day Ben Ali left office:
  {k.get('corporate_officer', 0):,} company board and officer ties and
  {k.get('state_office', 0):,} state offices, plus {uni['n_org_ties']}
  dated inter-organisational ties, over {len(uni['nodes']):,} entities in
  all. \textbf{{This is a filter on source as well as on time.}} Every
  gazette-evidenced tie in the dataset carries a date and every
  seed-derived tie carries none, so restricting to ties evidenced before a
  date necessarily drops the whole seed layer: shareholding, kinship,
  association and party membership are absent here, not because they did
  not exist before 2011, but because the roster that records them asserts
  present affiliations and is undated. Betweenness is recomputed on this
  graph and is not comparable with the pooled figure. The gazette also
  documents state appointments more completely than company officers,
  which will overstate the state's share relative to the private
  layer.""")

    tex = rf"""% Include at a fixed width: scaling DOWN would push the
% in-figure type below the 9pt floor the artwork guide sets.
\begin{{figure}}[t]
  \centering
  \includegraphics[width={args.width}in]{{{stem}.pdf}}
  \caption{{\textbf{{{head}}}
  Node area is proportional to betweenness centrality. The {len(mem)}
  entities shown, joined by {len(core['edges'])} ties, are the giant
  component of the subgraph induced on the {core['n_selected']} highest
  betweenness entities, which together hold {100 * core['share']:.1f}\% of
  all betweenness in the graph. {scope}
  The composition is {n_person} natural persons, {n_state} state bodies and
  parties, and {n_priv} firms, associations and unions. The {drawn}
  highest-brokerage entities are labelled.{gloss_tex}}}
  \label{{fig:{stem}}}
\end{{figure}}

% ---------------------------------------------------------------------
% Accessibility description (APSR requires one; WCAG 2.1 AA)
% ---------------------------------------------------------------------
% A node-link diagram of {len(mem)} entities connected by
% {len(core['edges'])} lines, drawn in greyscale. Circles are natural
% persons, squares are organisations; darker fills are state bodies and
% parties, lighter fills are firms, associations and unions. The area of
% each shape is proportional to its betweenness centrality, so the
% entities that lie on the most shortest paths appear largest. A small
% number of very large nodes, led by {short_label(labels[mem[0]])},
% sit at the centre of the diagram and connect several otherwise separate
% dense clusters of smaller nodes. A size key at the lower left gives
% reference areas in millions.
"""
    path = FIGS / f"{stem}.tex"
    path.write_text(tex, encoding="utf-8")
    print(f"  wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    raise SystemExit(main())
