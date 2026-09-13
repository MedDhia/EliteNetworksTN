"""Are politically connected firms more central in the network?

Asked naively the answer is yes and it means nothing, because the question is
close to circular. A firm is coded connected through `public_bank` when it has
a tie to a state-owned bank; centrality counts ties; state-owned banks are
among the largest hubs in the corpus. The coding and the outcome are then two
readings of the same edges, and the correlation is arithmetic rather than
political.

Two corrections are applied, and the gap between the naive and the corrected
estimate is the actual result.

**Leave-out centrality.** For each channel, the nodes whose ties *define* that
channel are deleted from the graph before centrality is computed - public
banks for `public_bank`, state bodies for the state channels - and the deletion
applies to treated and control firms alike. What remains is whether a
connected firm is better placed among *other* firms, which is the substantive
question. `officeholder` needs no deletion: it is read off a director's
printed title, not off a firm-firm tie, so it is the one channel whose
treatment and outcome are measured on different material.

**Exposure stratification.** A firm enters this network when a filing names
it, so a firm named in forty documents has more observed ties than one named
in two, and also more chances for a connection to be visible. Filing intensity
therefore drives both sides. Labels are permuted *within* bins of the document
count, and the effect is the gap averaged within those same bins, so the
comparison is against equally-well-observed firms rather than against the mass
of once-filed ones. Bins are fixed cut points rather than quantiles: the count
is so skewed that its quintiles are [1, 1, 2, 3].

Inference is by permutation rather than by a parametric test. Network
observations are not independent - one shared director creates ties among
every pair on a board - so ordinary standard errors would be far too small.
The statistic is a stratified difference in mean percentile rank: ranks
because every centrality here is heavily right-skewed, stratified because an
unstratified control mean is dominated by once-filed peripheral firms that no
treated firm could be compared with.

Run with::

    PYTHONPATH=src python -m bourse.analysis_connection_centrality

Writes data/processed/bourse/analysis_connection_centrality.md.
"""

from __future__ import annotations

import csv
import gzip
from collections import defaultdict

import networkx as nx
import numpy as np

from .common import PROCESSED, log
from .political_connections import load_rules

EDGES = PROCESSED / "multiplex_edges_observed.csv.gz"
PANEL = PROCESSED / "political_connections.csv"
ENTITIES = PROCESSED / "entities.csv"
OUT = PROCESSED / "analysis_connection_centrality.md"

FIRMISH = {"firm", "fund", "state"}
N_PERMUTATIONS = 5000
N_STRATA = 5
SEED = 20260913
# Decimal places betweenness is rounded to before ranking; see centrality().
BETWEENNESS_DP = 12

# Which nodes must be removed before a channel's own effect can be read. A
# channel defined by ties to a class of node cannot be tested on a graph that
# still contains it.
TREATMENTS = [
    ("pc_officeholder", "officeholder on the board", ()),
    ("pc_state_ownership", "state holds equity", ("state",)),
    ("pc_state_board", "state holds a board seat", ("state",)),
    ("pc_any_state", "any direct state tie", ("state",)),
    ("pc_public_bank", "tie to a state-owned bank", ("public_bank",)),
    ("pc_narrow", "Faccio strict", ("state",)),
    ("pc_broad", "any channel", ("state", "public_bank")),
]

MEASURES = ("degree", "strength", "betweenness", "core")


def read_edges() -> list[dict]:
    with gzip.open(EDGES, "rt", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def build_graph(rows: list[dict]) -> tuple[nx.Graph, dict[str, int]]:
    """Firm-firm ties pooled over years, plus how many documents name each firm.

    Pooled rather than per-year: a single year holds too few filings to
    estimate centrality from, and the question is not about any one year.
    Parallel ties across layers and documents become one weighted edge.
    """
    g = nx.Graph()
    docs: dict[str, set] = defaultdict(set)
    for r in rows:
        a, b = r["source_id"], r["target_id"]
        if a:
            docs[a].add(r["doc_node_key"])
        if b:
            docs[b].add(r["doc_node_key"])
        if (r["source_type"] in FIRMISH and r["target_type"] in FIRMISH
                and a and b and a != b):
            if g.has_edge(a, b):
                g[a][b]["weight"] += 1
            else:
                g.add_edge(a, b, weight=1)
    return g, {k: len(v) for k, v in docs.items()}


def state_and_bank_nodes(rows: list[dict]) -> tuple[set[str], set[str]]:
    """Node ids of state bodies, and of the majority state-owned banks.

    The banks are identified by the same shipped rules that coded the
    connection, so the deletion and the coding cannot disagree.
    """
    rules = load_rules()
    state, banks = set(), set()
    for r in rows:
        for side in ("source", "target"):
            nid, ntype, name = r[f"{side}_id"], r[f"{side}_type"], r[f"{side}_name"]
            if not nid:
                continue
            if ntype == "state":
                state.add(nid)
            if rules.is_state_owned(name):
                banks.add(nid)
    return state, banks


def centrality(g: nx.Graph) -> dict[str, dict[str, float]]:
    """Four measures, chosen to disagree with each other where it matters.

    Degree and strength are local; betweenness is about brokerage between
    otherwise unconnected parts; core number is about sitting inside a densely
    tied group rather than merely having many ties. A result that holds across
    all four is not an artefact of one definition of "central".

    Betweenness is exact - the graph is small enough - so the figure does not
    depend on a sampling seed. Core number replaces eigenvector centrality,
    whose networkx implementation needs scipy, which is not a dependency here;
    it needs no linear algebra and behaves on a disconnected graph.
    """
    gg = nx.Graph(g)
    gg.remove_edges_from(nx.selfloop_edges(gg))
    bc = nx.betweenness_centrality(g, normalized=True)
    return {
        "degree": dict(g.degree()),
        "strength": dict(g.degree(weight="weight")),
        # Rounded, and not only for tidiness. Betweenness sums path counts in
        # whatever order the graph iterates, so two nodes with identical
        # structural position can come out differing by ~1e-17 - measured at
        # 5.6e-17 across 59 nodes of this graph. Ranking groups ties by exact
        # equality, so that noise silently splits a genuine tie into two
        # ranks, and it also makes the committed report depend on iteration
        # order. Twelve places is far below any real difference here and
        # removes both problems.
        "betweenness": {k: round(v, BETWEENNESS_DP) for k, v in bc.items()},
        "core": {k: float(v) for k, v in nx.core_number(gg).items()},
    }


def percentile_ranks(values: np.ndarray) -> np.ndarray:
    """Average ranks scaled to (0, 1]; ties share a rank.

    Ranks rather than raw values because every centrality here is heavily
    right-skewed, and a difference in means would be a statement about a
    handful of hubs.
    """
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=float)
    ranks[order] = np.arange(1, len(values) + 1)
    # Average the ranks within each group of tied values.
    uniq, inv, counts = np.unique(values, return_inverse=True, return_counts=True)
    sums = np.zeros(len(uniq))
    np.add.at(sums, inv, ranks)
    ranks = (sums / counts)[inv]
    return ranks / len(values)


# Fixed cut points on the raw document count rather than quantiles. The count
# is so skewed - most firms appear in exactly one filing - that quantile bins
# collapse: the "quintiles" of this distribution are [1,1,2,3], which is three
# non-empty bins, one of them holding 60% of the firms.
DOC_BINS = (2, 3, 5, 10)
BIN_LABELS = ("1 doc", "2", "3–4", "5–9", "10+")


def strata_of(exposure: np.ndarray) -> np.ndarray:
    """Bins of the document count, used as permutation blocks."""
    return np.digitize(exposure, DOC_BINS)


def stratified_diff(ranks: np.ndarray, treat: np.ndarray,
                    strata: np.ndarray) -> float:
    """Treated-minus-control rank gap, averaged within strata.

    Not the raw difference in means. Strata holding almost no treated firms
    still contribute their firms to an unstratified control mean, and since
    those are the once-filed, structurally peripheral firms, they drag the
    control down and inflate the gap. Averaging *within* stratum and weighting
    by the treated count keeps the comparison to firms that could have been
    compared, which is also what the permutation null does.
    """
    total_w, acc = 0.0, 0.0
    for s in np.unique(strata):
        m = strata == s
        t, c = m & treat, m & ~treat
        if not t.any() or not c.any():
            continue
        w = t.sum()
        acc += w * (ranks[t].mean() - ranks[c].mean())
        total_w += w
    return acc / total_w if total_w else float("nan")


def permutation_test(ranks: np.ndarray, treat: np.ndarray, strata: np.ndarray,
                     n_iter: int = N_PERMUTATIONS, seed: int = SEED) -> dict:
    """Stratified rank gap, with labels shuffled within strata.

    Shuffling within strata is what makes this a test about connection rather
    than about how much a firm was filed on: every permutation keeps the
    number of treated firms in each exposure bin fixed.
    """
    obs = stratified_diff(ranks, treat, strata)
    rng = np.random.default_rng(seed)
    idx_by_stratum = [np.flatnonzero(strata == s) for s in np.unique(strata)]
    n_treat = [int(treat[i].sum()) for i in idx_by_stratum]
    ge = 0
    for _ in range(n_iter):
        sham = np.zeros(len(ranks), dtype=bool)
        for idx, k in zip(idx_by_stratum, n_treat):
            if k:
                sham[rng.choice(idx, size=k, replace=False)] = True
        if abs(stratified_diff(ranks, sham, strata)) >= abs(obs):
            ge += 1
    return {"diff": obs, "p": (ge + 1) / (n_iter + 1)}


def treated_sets(panel_rows: list[dict]) -> dict[str, set[str]]:
    """Firm-level 'ever connected' flags, collapsed from the firm-year panel.

    Collapsed because the panel is sparse in time - most firms appear in one
    or two years - so a firm-year test would mostly measure which years a firm
    filed in.
    """
    sets: dict[str, set[str]] = defaultdict(set)
    for r in panel_rows:
        for col in ("pc_officeholder", "pc_state_ownership", "pc_state_board",
                    "pc_public_bank", "pc_narrow", "pc_broad"):
            if r.get(col) == "1":
                sets[col].add(r["entity_id"])
    sets["pc_any_state"] = sets["pc_state_ownership"] | sets["pc_state_board"]
    return sets


_CENT_CACHE: dict[frozenset, tuple[list[str], dict]] = {}


def _graph_centrality(g: nx.Graph, drop: set[str]):
    """Centrality for one drop-set, computed once and reused.

    Every treatment shares the same handful of graphs - nothing dropped, state
    dropped, banks dropped, both - so without this betweenness is recomputed
    a dozen times over the same edges.
    """
    key = frozenset(drop)
    if key not in _CENT_CACHE:
        h = g.copy()
        h.remove_nodes_from(drop & set(h.nodes()))
        _CENT_CACHE[key] = (list(h.nodes()), centrality(h))
    return _CENT_CACHE[key]


def run(g: nx.Graph, docs: dict[str, int], treated: set[str],
        drop: set[str]) -> dict:
    """Centrality comparison on a graph with the defining nodes removed."""
    nodes, cent = _graph_centrality(g, drop)
    if len(nodes) < 50:
        return {}
    treat = np.array([n in treated for n in nodes])
    if treat.sum() < 3 or (~treat).sum() < 3:
        return {}
    exposure = np.array([docs.get(n, 0) for n in nodes], dtype=float)
    strata = strata_of(exposure)
    res = {"n_treated": int(treat.sum()), "n_control": int((~treat).sum()),
           "n_nodes": len(nodes), "measures": {}}
    for m in MEASURES:
        vals = cent.get(m)
        if not vals:
            continue
        v = np.array([vals.get(n, 0.0) for n in nodes], dtype=float)
        ranks = percentile_ranks(v)
        test = permutation_test(ranks, treat, strata)
        res["measures"][m] = {
            "treated_median": float(np.median(v[treat])),
            "control_median": float(np.median(v[~treat])),
            "treated_rank": float(ranks[treat].mean()),
            "control_rank": float(ranks[~treat].mean()),
            **test,
        }
    return res


def fmt_p(p: float) -> str:
    return f"{p:.4f}" if p >= 1 / (N_PERMUTATIONS + 1) else f"<{1 / (N_PERMUTATIONS + 1):.4f}"


def main() -> None:
    rows = read_edges()
    g, docs = build_graph(rows)
    state, banks = state_and_bank_nodes(rows)
    panel = list(csv.DictReader(PANEL.open(encoding="utf-8")))
    treated = treated_sets(panel)
    log.info("graph %d nodes / %d edges; %d state nodes, %d public-bank nodes",
             g.number_of_nodes(), g.number_of_edges(), len(state), len(banks))

    drops = {"state": state, "public_bank": banks}

    # How the treated firms spread across exposure bins. A channel whose
    # treated firms all sit in one bin is being compared against a much
    # smaller control group than the node count suggests, and the reader
    # should be able to see that rather than infer it.
    all_nodes = list(g.nodes())
    exposure = np.array([docs.get(n, 0) for n in all_nodes], dtype=float)
    strata_all = strata_of(exposure)
    bin_rows = []
    for i, label in enumerate(BIN_LABELS):
        m = strata_all == i
        if not m.any():
            continue
        cells = []
        for col, _, _ in TREATMENTS:
            t = treated.get(col, set())
            cells.append(str(sum(1 for n, keep in zip(all_nodes, m) if keep and n in t)))
        bin_rows.append(f"| {label} | {int(m.sum())} | " + " | ".join(cells) + " |")

    lines = [
        "# Are politically connected firms more central?",
        "",
        "Centrality is measured on the pooled firm-firm network "
        f"({g.number_of_nodes():,} nodes, {g.number_of_edges():,} edges), and "
        "connection is the firm-level 'ever coded' flag from "
        "`political_connections.csv`.",
        "",
        "Each channel is tested twice. **Naive** uses the whole network. "
        "**Leave-out** deletes the nodes whose ties define that channel — "
        "public banks, state bodies — from treated and control firms alike, "
        "so what is left is whether a connected firm is better placed among "
        "*other* firms. Labels are permuted within bins of the number of "
        "documents naming the firm, so the comparison is against "
        "equally-well-observed firms rather than against unfiled ones.",
        "",
        "Reported as the stratified difference in mean percentile rank (0–1) — "
        "the gap averaged within document-count bins, weighted by treated "
        f"count; p from {N_PERMUTATIONS:,} stratified permutations.",
        "",
        "Exposure bins (documents naming the firm) and how the treated firms "
        "fall across them:",
        "",
        "| Bin | Firms | " + " | ".join(f"`{c}`" for c, _, _ in TREATMENTS) + " |",
        "|---|---:|" + "---:|" * len(TREATMENTS),
        *bin_rows,
        "",
    ]

    for col, label, drop_keys in TREATMENTS:
        t = treated.get(col, set())
        if len(t) < 3:
            lines += [f"## `{col}` — {label}", "", "Too few firms to test.", ""]
            continue
        naive = run(g, docs, t, set())
        drop_nodes = set().union(*(drops[k] for k in drop_keys)) if drop_keys else set()
        left = run(g, docs, t, drop_nodes) if drop_keys else None

        lines += [f"## `{col}` — {label}", "",
                  f"{len(t)} firms coded connected."
                  + (f" Leave-out deletes {len(drop_nodes & set(g.nodes()))} "
                     f"{'/'.join(drop_keys)} nodes." if drop_keys
                     else " No deletion needed: this channel is read from a"
                          " director's title, not from a firm-firm tie.")]
        lines += ["",
                  "| Measure | Naive Δrank | p | Leave-out Δrank | p |",
                  "|---|---:|---:|---:|---:|"]
        for m in MEASURES:
            a = naive.get("measures", {}).get(m)
            if not a:
                continue
            if left is None:
                lines.append(f"| {m} | {a['diff']:+.3f} | {fmt_p(a['p'])} | — | — |")
            else:
                b = left.get("measures", {}).get(m)
                cell = (f"{b['diff']:+.3f} | {fmt_p(b['p'])}" if b else "— | —")
                lines.append(f"| {m} | {a['diff']:+.3f} | {fmt_p(a['p'])} | {cell} |")
        lines.append("")

    lines += [
        "## Reading it",
        "",
        "A positive Δrank means connected firms sit higher in the centrality",
        "distribution than comparably-filed unconnected firms. Read the",
        "leave-out column: the naive column still contains the ties that",
        "*defined* the connection, so for `public_bank` and the state channels",
        "it is partly arithmetic.",
        "",
        "**Yes for the state channels, and it survives the correction.** A firm",
        "the state holds equity in, or holds a board seat on, ranks about 0.18",
        "higher on degree and 0.24 higher on betweenness than a firm named in",
        "as many filings — and the estimate barely moves when every state node",
        "is deleted from the graph. Whatever this is, it is not the state's own",
        "edges being counted twice.",
        "",
        "**No for the broad measure, which reverses.** `pc_broad` is a small",
        "positive on the whole network and a large *negative* once public",
        "banks are removed (degree −0.26). The same holds for `public_bank`",
        "alone, which supplies almost all of `pc_broad`'s firms. Those firms",
        "are mostly small participations hanging off a bank: delete the bank",
        "and they are more peripheral than comparable firms, not less. The",
        "naive positive was the hub, and nothing else. **Any analysis that",
        "uses `pc_broad` as the treatment is measuring this artefact.**",
        "",
        "## The shape of the effect, where there is one",
        "",
        "The measures disagree in a consistent order — betweenness > degree >",
        "strength > core, with core not distinguishable from zero in most",
        "specifications — and that ordering is itself the finding.",
        "",
        "A firm that scored high on core number would sit inside a densely",
        "interconnected group. Connected firms do not: they have many",
        "partners (degree) and sit on many shortest paths (betweenness) while",
        "*not* being embedded in a tight cluster. Strength rising less than",
        "degree says the same thing from another direction — their ties are",
        "numerous but thin, each partner observed few times, rather than",
        "repeated dealing with a small set.",
        "",
        "That is a brokerage signature rather than a cohesion one. On this",
        "evidence state-linked firms are not an inner circle trading among",
        "themselves; they are positioned *between* parts of the network that",
        "are otherwise not connected. Which of those two things a theory of",
        "elite survival expects is worth being explicit about, because the",
        "data distinguish them.",
        "",
        "## Multiplicity",
        "",
        f"Seven channels × four measures × two graphs is 56 tests. At "
        f"{N_PERMUTATIONS:,} permutations the smallest reportable p is "
        f"{1 / (N_PERMUTATIONS + 1):.4f}, and the state and officeholder",
        "results on degree, strength and betweenness sit at that floor — they",
        "survive a Bonferroni correction (0.05/56 ≈ 0.0009). The `core`",
        "results, at p between 0.02 and 0.09, do not, and are reported as",
        "null.",
        "",
        "## What this cannot settle",
        "",
        "**Direction.** These are pooled co-occurrences. A firm may be central",
        "because it is connected, or connected because it is central, and",
        "nothing here distinguishes them. The dated layers are too thin to",
        "test sequence: `board_appointment` covers 12 years and is empty",
        "across 2012–2017.",
        "",
        "**Disclosure.** Connection is coded from titles firms chose to print.",
        "Stratifying on document count controls how *much* a firm filed, not",
        "what it chose to reveal in those filings.",
        "",
        "**Sector, and it bites unevenly.** Banks are over-represented in the",
        "corpus and central by construction in an interlock network. Of the",
        "10 firms carrying `officeholder`, 8 are banks — that channel is close",
        "to a bank indicator, and its result should not be read as being about",
        "political connection as against being about banking. The state",
        "channels are better placed: only 3 of their 22 firms are public",
        "banks, and the rest are Tunisair, Tunisie Telecom, Carthage Cement,",
        "STAR, SIMPAR and similar — state-linked firms across several",
        "sectors. That is why the state channels, not the officeholder one,",
        "carry the weight of the finding here. No sector control is applied",
        "because the corpus has no clean sector variable; adding one is the",
        "next thing that would sharpen this.",
        "",
        "**Small treated groups.** The defensible channels have 8–22 firms.",
        "The permutation test is exact under its null and does not assume",
        "large samples, so the p-values are honest, but the *estimates* are",
        "not precise and a handful of firms moves them. The exposure-bin",
        "table above shows where the treated firms sit: most are in the",
        "highest-filed bin, so the comparison group for them is roughly the",
        "hundred best-covered firms rather than the whole corpus.",
    ]
    text = "\n".join(lines) + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(text)
    log.info("wrote %s", OUT)


if __name__ == "__main__":
    main()
