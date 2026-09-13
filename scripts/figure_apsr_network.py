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
import pickle
import random
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

FIGS = ROOT / "figures"
FIGS.mkdir(exist_ok=True)
CACHE = ROOT / "data" / "interim" / "core_periphery.pkl"
STEM = "fig15_brokerage_network"

TOP_N = 200
N_LABELS = 12

# Greyscale only, inside the 15-85% band the artwork guide specifies, in
# steps far larger than the 15-20% minimum increment.
INK = "#1A1A1A"          # text
EDGE = "#B0B0B0"         # ~31% black, at 0.4pt so it survives print
T_PERSON = "#262626"     # 85%
T_STATE = "#737373"      # 55%
T_PRIVATE = "#CCCCCC"    # 20%
OUTLINE = "#1A1A1A"

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
    "INTERNATIONAL SICAR": ("International SICAR", None),
}

_KEEP_UPPER = {"RCD", "BIAT", "BNA", "STB", "UBCI", "SICAR", "ATD", "SIM",
               "GAT", "MAC", "PAF", "SA"}


def short_label(raw: str) -> str:
    """The form drawn on the figure."""
    key = " ".join(raw.split())
    if key in SHORT:
        return SHORT[key][0]
    words = [w if w.upper() in _KEEP_UPPER else w.capitalize()
             for w in key.split()]
    out = " ".join(words)
    return out if len(out) <= 20 else out[:19].rsplit(" ", 1)[0] + "…"


def expansion(raw: str) -> str | None:
    """The gloss the caption must carry, if the drawn form is abbreviated."""
    key = " ".join(raw.split())
    if key in SHORT and SHORT[key][1]:
        return f"{SHORT[key][0]}, {SHORT[key][1]}"
    return None


def load() -> dict:
    if not CACHE.exists():
        raise SystemExit(
            f"missing {CACHE.relative_to(ROOT)} — run "
            f"scripts/figure_core_periphery.py first")
    with CACHE.open("rb") as fh:
        return pickle.load(fh)


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


def layout(core: dict, seed: int = 7) -> np.ndarray:
    g = ig.Graph(n=len(core["members"]), edges=core["edges"])
    # igraph wants the stdlib Random interface (it calls .gauss/.random),
    # not a numpy Generator.
    ig.set_random_number_generator(random.Random(seed))
    pos = np.asarray(g.layout_kamada_kawai(maxiter=6000).coords)
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
    args = ap.parse_args(argv)

    d = load()
    nodes, bc, cls, labels, core_k = (d["nodes"], d["bc"], d["cls"],
                                      d["labels"], d["core"])
    core = brokerage_core(d, args.top)
    mem = core["members"]
    pos = layout(core)

    # Three stacked bands -- legend, network, size key -- each in its own
    # axes. Sharing one axes put the key and legend inside the drawing area
    # and cost the network most of its usable height.
    fig = plt.figure(figsize=(args.width, args.width * 1.22))
    ax_leg = fig.add_axes([0.012, 0.930, 0.976, 0.064])
    ax = fig.add_axes([0.006, 0.116, 0.988, 0.812])
    ax_key = fig.add_axes([0.012, 0.006, 0.976, 0.104])
    for a in (ax_leg, ax, ax_key):
        a.set_axis_off()

    # Limits and aspect BEFORE any label placement: the collision test
    # works in display coordinates, so changing the data limits afterwards
    # silently invalidates every box it checked.
    ax.set_aspect("equal")
    ax.set_xlim(-1.045, 1.045)
    h = 1.045 * (0.812 * 1.22) / 0.988
    ax.set_ylim(-h, h)

    segs = [(pos[a_], pos[b_]) for a_, b_ in core["edges"]]
    ax.add_collection(LineCollection(segs, colors=EDGE, linewidths=0.4,
                                     zorder=1))

    # Node AREA strictly proportional to betweenness: matplotlib's `s` is
    # area in points squared, so s = k * betweenness with no exponent.
    bmax = max(bc[i] for i in mem)
    d_max_pt = 17.0
    k = (np.pi * (d_max_pt / 2) ** 2) / bmax
    size = {j: k * bc[i] for j, i in enumerate(mem)}

    for name in ORDER:
        tone, marker, _ = CLASSES[name]
        pool = [j for j, i in enumerate(mem) if klass(cls[nodes[i]]) == name]
        if not pool:
            continue
        ax.scatter(pos[pool, 0], pos[pool, 1], s=[size[j] for j in pool],
                   facecolors=tone, marker=marker, linewidths=0.5,
                   edgecolors=OUTLINE, zorder=3 if name == "person" else 2)

    ax_leg.legend(
        handles=[Line2D([], [], marker=CLASSES[n][1], ls="none",
                        markerfacecolor=CLASSES[n][0], markeredgecolor=OUTLINE,
                        markeredgewidth=.5, markersize=7,
                        label=CLASSES[n][2]) for n in ORDER],
        loc="upper left", bbox_to_anchor=(0, 1.25), ncol=2, fontsize=MIN_PT,
        labelcolor=INK, handletextpad=.5, labelspacing=.35,
        columnspacing=1.2, borderpad=0)

    _size_key(ax_key, k, bmax)

    top = list(range(min(args.labels, len(mem))))
    drawn, shown = place_labels(
        ax,
        [(short_label(labels[nodes[mem[j]]]), pos[j],
          np.sqrt(size[j] / np.pi), labels[nodes[mem[j]]]) for j in top],
        obstacles=node_boxes(ax, pos, size))

    _write_csv(mem, nodes, bc, cls, labels, core_k, pos, core)
    _write_tex(mem, core, labels, nodes, bc, cls, drawn, shown, args)

    pdf = FIGS / f"{STEM}.pdf"
    fig.savefig(pdf)
    png = FIGS / f"{STEM}.png"
    fig.savefig(png, dpi=args.dpi)
    plt.close(fig)

    tif = _write_tiff(png, args.dpi)
    for p in (pdf, png, tif):
        print(f"  {p.relative_to(ROOT)}  {p.stat().st_size / 1024:.0f} KB")
    print(f"  {len(mem)} nodes, {len(core['edges'])} ties; top "
          f"{core['n_selected']} hold {100 * core['share']:.1f}% of all "
          f"betweenness")
    print(f"  labels drawn: {drawn} of {len(top)} requested")
    print(f"  node diameters {2 * np.sqrt(min(size.values()) / np.pi):.1f}"
          f"–{2 * np.sqrt(max(size.values()) / np.pi):.1f} pt")
    return 0


def _size_key(ax, k: float, bmax: float) -> None:
    """A size key, without which an area encoding cannot be decoded.

    Drawn in its own axes in axes-fraction coordinates, so the reference
    circles and their values cannot fall outside the canvas.
    """
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    steps = [m for m in (5e6, 15e6, 35e6) if m <= bmax * 1.02]

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
        ax.text(x, 0.34, f"{m / 1e6:.0f}M", ha="left", va="center",
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


def _write_csv(mem, nodes, bc, cls, labels, core_k, pos, core) -> None:
    path = FIGS / f"{STEM}.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["rank", "node_id", "label", "node_class", "draw_class",
                    "betweenness", "coreness", "x", "y"])
        for j, i in enumerate(mem):
            w.writerow([j + 1, nodes[i], labels[nodes[i]], cls[nodes[i]],
                        klass(cls[nodes[i]]), f"{bc[i]:.1f}", core_k[i],
                        f"{pos[j][0]:.4f}", f"{pos[j][1]:.4f}"])
    print(f"  wrote {path.relative_to(ROOT)}")


def _write_tex(mem, core, labels, nodes, bc, cls, drawn, shown, args) -> None:
    n_person = sum(1 for i in mem if klass(cls[nodes[i]]) == "person")
    n_state = sum(1 for i in mem if klass(cls[nodes[i]]) == "state")
    n_priv = len(mem) - n_person - n_state

    # Gloss every abbreviation that actually reached the figure, so the
    # caption can never promise an expansion the drawing does not use or
    # omit one it does.
    gloss = [g for g in (expansion(r) for r in shown) if g]
    gloss_tex = (" Abbreviations: " + "; ".join(gloss) + "."
                 if gloss else "")

    tex = rf"""% Include at a fixed width: scaling DOWN would push the
% in-figure type below the 9pt floor the artwork guide sets.
\begin{{figure}}[t]
  \centering
  \includegraphics[width={args.width}in]{{{STEM}.pdf}}
  \caption{{\textbf{{The brokerage core of the Tunisian elite network.}}
  Node area is proportional to betweenness centrality. The {len(mem)}
  entities shown, joined by {len(core['edges'])} ties, are the giant
  component of the subgraph induced on the {core['n_selected']} highest
  betweenness entities in the network, which together hold
  {100 * core['share']:.1f}\% of all betweenness. Selection is therefore on
  the quantity the node areas encode; the full network of 23,274 entities
  and 31,457 ties cannot be rendered legibly at page width. The composition
  is {n_person} natural persons, {n_state} state bodies and parties, and
  {n_priv} firms, associations and unions. The {drawn} highest-brokerage
  entities are labelled.{gloss_tex} Ties are undirected
  and undated, pooling shareholding, board and governing-body membership,
  kinship, party and parliamentary structures, and the seed roster over
  1957--2026.}}
  \label{{fig:brokerage-network}}
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
% number of very large nodes, led by {short_label(labels[nodes[mem[0]]])},
% sit at the centre of the diagram and connect several otherwise separate
% dense clusters of smaller nodes. A size key at the lower left gives
% reference areas in millions.
"""
    path = FIGS / f"{STEM}.tex"
    path.write_text(tex, encoding="utf-8")
    print(f"  wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    raise SystemExit(main())
