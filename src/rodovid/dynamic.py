"""When each marriage alliance was contracted, and what the network looked like
as they accumulated.

`rodovid.families` collapses the kinship graph to families and draws one
network: every alliance ever recorded, laid on top of every other. That picture
has no time in it. A house that married widely in the 1820s and a house that
married widely in the 1980s are the same node at the same size, and the
beylical hub at the centre of it is two centuries of marriages stacked into one
dot.

This stage puts the marriages in order.

THE PROBLEM: MARRIAGES ARE NOT DATED

The export records 22,976 marriage lines and **16 of them carry a year**. Dating
the alliances directly is not on the table. What the records do carry is birth
years -- 7,247 of them, 19% of the people -- and a kinship graph to carry them
along. So each person is dated, and each couple is placed by the birth years of
the two spouses.

    naissance: 1898, Tunis     ->  birth 1898, observed
    décès: 1972                ->  birth ~1897 where nothing better exists

A couple's `cohort_year` is the mean birth year of the two spouses. It is *not*
the wedding date: the wedding follows roughly a generation later, and the
measured parent-child gap below is the best available guide to how much later.
Nothing here invents that offset -- the panel is indexed by the generation the
spouses belong to, which is what the period bins mean.

HOW A PERSON WITHOUT A BIRTH YEAR IS DATED

Evidence from relatives, one hop at a time, with the offsets measured on this
dataset rather than assumed:

    a parent    ->  the parent's year + the measured parent-child gap
    a child     ->  the child's year - the same gap
    a spouse    ->  the same year (measured median spouse gap: 6.5 years, and
                    unsigned, so it carries no usable direction)
    a sibling   ->  the same year (measured median gap: 3 years)

The median of whatever evidence a person has, taken in rounds, so that a person
one hop from someone dated is settled before anyone two hops away. Every
estimate records the hop it came from, because the error grows with it, and
`--validate` measures how much by holding out observed years and re-deriving
them. At a 90% holdout, which forces long propagation distances:

    hop 1  MAE  5.6 years    hop 4  MAE 12.4
    hop 2  MAE  8.4          hop 5  MAE 13.0
    hop 3  MAE  9.7          hop 6  MAE 14.7

Median error is +1 year overall: the estimator is close to unbiased, and 95% of
held-out people land within 25 years of the truth, which is one period bin.
That is the resolution this stage claims and no more.

WHAT IS WRITTEN

    person_years.csv      a year and its provenance for every person who can
                          be given one
    marriages_dated.csv   one row per couple, with the cohort year and the
                          quality of the two dates behind it
    alliance_panel.csv    family pair x period: the dynamic edge list, the
                          table a networkDynamic or Gephi timeline reads
    network_evolution.csv one row per period: the structure of the alliance
                          network as it stood, and what was new in it

Stdlib only, deterministic, about twenty seconds.

Run with:  make rodovid-dynamic      (or python -m rodovid.dynamic)
           make rodovid-validate     (adds the held-out error table)
"""
import argparse
import collections
import csv
import datetime
import random
import re
import statistics
import sys

from rodovid.audit import rewire
from rodovid.families import couples, is_family
from rodovid.paths import (
    ALLIANCE_PANEL, DOCS, EVOLUTION, INDIVIDUALS, MARRIAGES, PERSON_YEARS,
    TIES, ensure_dirs,
)

# A four-digit year in the source's own range. The export carries nothing
# before the fifteenth century and nothing beyond the present.
YEAR = re.compile(r"\b(1[0-9]{3}|20[0-2][0-9])\b")
# rodovid writes `vers 1850`, `avant 1900`: a date the contributor was unsure
# of. Kept, and marked, rather than dropped -- an approximate year is still
# worth a great deal more than none at a 25-year resolution.
APPROX = re.compile(r"\bvers\b|\bavant\b|\bapr[eè]s\b|\bcirca\b|\benv\.|\?", re.I)

# Rounds of kinship propagation. Six, because the measured error is still
# usable there (MAE 14.7, 83% inside one period) and the seventh round adds
# fewer than 200 people.
HOPS = 6
# Cohort years are binned into generations. Twenty-five years is the resolution
# the validation supports: 95% of held-out people land inside one bin.
PERIOD = 25
# Periods reported in network_evolution.csv. Earlier ones exist in the panel
# but hold too few marriages to measure a network on.
FIRST_PERIOD = 1775
# The last period whose marriage *flow* is complete. A couple binned at 2000
# was born 2000-2024 and marries around 2030, so those windows are cut off by
# the calendar, not by the source.
LAST_COMPLETE = 1975
# A person born after this is not in the source; an estimate that lands there
# is propagation error, and is dropped rather than published.
THIS_YEAR = datetime.date.today().year
# Random graphs per period for the size-and-density baseline, and the seed they
# are drawn with. Twenty is enough: the spread across draws is a hundredth of
# the gap between the periods being compared.
NULL_DRAWS, NULL_SEED = 20, 0

QUALITY_ORDER = ["observed", "kin1", "kin2", "kin3+", "death", "kin_death"]


# ---- reading the records ---------------------------------------------------

def parse_record(info):
    """Birth and death year out of one `INFO` field, with an approximate flag.

    The field is a French labelled list, one item per line:

        naissance: 29 juin 1931
        mariage : ♂ / Abdelaziz Landolsi
        décès: 26 janvier 2016, Tunis

    Only the first `naissance` and the first `décès` are read; a handful of
    records carry two, and the first is the one rodovid shows.
    """
    out = {"birth": None, "death": None, "approx": False}
    for line in info.split("\n"):
        s = line.strip()
        for label, key in (("naissance", "birth"), ("décès", "death")):
            if s.startswith(label) and ":" in s and out[key] is None:
                body = s.split(":", 1)[1]
                m = YEAR.search(body)
                if m:
                    out[key] = int(m.group(1))
                    if APPROX.search(body):
                        out["approx"] = True
    return out


def load():
    people = {}
    with open(INDIVIDUALS, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            people[r["id"]] = {
                "id": r["id"], "fullname": r["fullname"],
                "surname": r["surname"], **parse_record(r["info"]),
            }
    with open(TIES, encoding="utf-8") as fh:
        ties = list(csv.DictReader(fh))
    return people, ties


def kinship(ties):
    """Parents, children and peers (spouse or sibling) per person."""
    parents = collections.defaultdict(set)
    children = collections.defaultdict(set)
    peers = collections.defaultdict(set)
    for t in ties:
        a, b = t["id_from"], t["id_to"]
        if t["edge"] == "PARENT":
            parents[b].add(a)
            children[a].add(b)
        else:
            peers[a].add(b)
            peers[b].add(a)
    return parents, children, peers


# ---- the offsets, measured on this dataset ---------------------------------

def calibrate(people, parents, children, peers):
    """The three offsets propagation needs, measured where both ends are known.

    Measured rather than assumed, and printed on every run, so a reader can see
    what the arithmetic below actually rests on. The parent-child gap is the
    one that matters: it is the only offset that is not zero.
    """
    obs = {p: d["birth"] for p, d in people.items() if d["birth"]}
    gaps = sorted(obs[c] - obs[p] for p in sorted(children) if p in obs
                  for c in sorted(children[p])
                  if c in obs and 12 <= obs[c] - obs[p] <= 70)
    lives = sorted(d["death"] - d["birth"] for d in people.values()
                   if d["birth"] and d["death"] and 0 <= d["death"] - d["birth"] <= 110)
    spouse_gaps = sorted(abs(obs[a] - obs[b]) for a in sorted(peers)
                         for b in sorted(peers[a]) if a < b and a in obs and b in obs)
    return {
        "gap": int(statistics.median(gaps)), "gap_n": len(gaps),
        "gap_iqr": (statistics.quantiles(gaps, n=4)[0],
                    statistics.quantiles(gaps, n=4)[2]),
        "life": int(statistics.median(lives)), "life_n": len(lives),
        "peer_gap": statistics.median(spouse_gaps), "peer_n": len(spouse_gaps),
        "observed": len(obs),
    }


# ---- dating every person ---------------------------------------------------

def propagate(seed, people, parents, children, peers, gap, hops=HOPS):
    """Carry years along the kinship graph, nearest evidence first.

    Returns id -> (year, hop). Hop 0 is the seed. Each round dates only people
    who have at least one neighbour settled in an earlier round, so an estimate
    never depends on another estimate made in the same round -- which would
    make the result depend on dictionary order.
    """
    est = {p: (y, 0) for p, y in seed.items()}
    for hop in range(1, hops + 1):
        new = {}
        for p in sorted(people):
            if p in est:
                continue
            evidence = []
            for q in sorted(parents[p]):
                if q in est and est[q][1] < hop:
                    evidence.append(est[q][0] + gap)
            for q in sorted(children[p]):
                if q in est and est[q][1] < hop:
                    evidence.append(est[q][0] - gap)
            for q in sorted(peers[p]):
                if q in est and est[q][1] < hop:
                    evidence.append(est[q][0])
            if evidence:
                new[p] = (int(statistics.median(evidence)), hop)
        if not new:
            break
        est.update(new)
    return est


def date_people(people, parents, children, peers, cal):
    """Every person who can be given a birth year, and how good it is.

    Three passes, weakest last, so that a good estimate is never displaced by a
    worse one:

      1. the person's own recorded birth year;
      2. kinship propagation from those;
      3. the person's own death year, less the measured median lifespan, for
         anyone still undated -- then propagation again from those.

    The quality label is what a reader should filter on: each level has its own
    measured error in docs/VALIDATION-rodovid-dynamic.md.
    """
    gap = cal["gap"]
    observed = {p: d["birth"] for p, d in people.items() if d["birth"]}
    est = propagate(observed, people, parents, children, peers, gap)

    quality = {}
    for p, (_, hop) in est.items():
        quality[p] = "observed" if hop == 0 else (
            "kin1" if hop == 1 else "kin2" if hop == 2 else "kin3+")

    # Weak fallback: a death year and nothing else. 87% of these land within
    # 25 years, which is one period -- worth having, worth flagging.
    from_death = {p: d["death"] - cal["life"] for p, d in people.items()
                  if p not in est and d["death"]}
    for p, y in from_death.items():
        est[p] = (y, 0)
        quality[p] = "death"

    if from_death:
        second = propagate({p: y for p, (y, _) in est.items()},
                           people, parents, children, peers, gap)
        for p, (y, hop) in second.items():
            if p not in quality:
                est[p] = (y, hop)
                quality[p] = "kin_death"

    # An estimate in the future is propagation error, not a person.
    dropped = {p for p, (y, _) in est.items() if y > THIS_YEAR or y < 1300}
    for p in dropped:
        del est[p]
        del quality[p]
    return est, quality, len(dropped)


# ---- couples, dated --------------------------------------------------------

def dated_marriages(people, ties, est, quality):
    """One row per couple, placed by the birth years of the two spouses.

    The couple definition is `rodovid.families`' own -- spouses, or two people
    recorded as parents of the same child -- so the family graph here and the
    static one are the same graph, and any difference between the two is time
    and nothing else.
    """
    rows = []
    for a, b in couples(ties):
        if a not in people or b not in people:
            continue
        years = [est[p][0] for p in (a, b) if p in est]
        if not years:
            continue
        qualities = [quality[p] for p in (a, b) if p in est]
        worst = max(qualities, key=QUALITY_ORDER.index)
        sa, sb = people[a]["surname"], people[b]["surname"]
        family_pair = (min(sa, sb), max(sa, sb)) if is_family(sa) and is_family(sb) else None
        rows.append({
            "id_a": a, "id_b": b,
            "name_a": people[a]["fullname"], "name_b": people[b]["fullname"],
            "family_a": family_pair[0] if family_pair else "",
            "family_b": family_pair[1] if family_pair else "",
            "cohort_year": int(round(sum(years) / len(years))),
            "period": int(sum(years) / len(years)) // PERIOD * PERIOD,
            "quality": worst,
            "dates_known": len(years),
            "endogamous": "1" if is_family(sa) and sa == sb else "0",
            "on_graph": "1" if family_pair and family_pair[0] != family_pair[1] else "0",
        })
    rows.sort(key=lambda r: (r["cohort_year"], int(r["id_a"]), int(r["id_b"])))
    return rows


# ---- the network, period by period -----------------------------------------

def neighbours(edges):
    nb = collections.defaultdict(set)
    for a, b in edges:
        nb[a].add(b)
        nb[b].add(a)
    return nb


def clustering(nb):
    """Global clustering: closed triples over all triples."""
    closed = triples = 0
    for node in sorted(nb):
        ns = sorted(nb[node])
        for i, a in enumerate(ns):
            for b in ns[i + 1:]:
                triples += 1
                if b in nb[a]:
                    closed += 1
    return closed / triples if triples else 0.0


def largest_component(nb):
    seen, biggest = set(), 0
    for start in sorted(nb):
        if start in seen:
            continue
        stack, comp = [start], set()
        while stack:
            n = stack.pop()
            if n in comp:
                continue
            comp.add(n)
            stack.extend(nb[n] - comp)
        seen |= comp
        biggest = max(biggest, len(comp))
    return biggest


def centralization(nb):
    """Freeman degree centralization: how far the graph is from a star.

    0 when every family has the same number of allies, 1 when one family is
    allied to all the others and they to no one else. This is the number that
    says whether the beylical hub is the structure or an artifact of stacking
    two centuries into one picture.
    """
    n = len(nb)
    if n < 3:
        return 0.0
    degrees = [len(v) for v in nb.values()]
    top = max(degrees)
    return sum(top - d for d in degrees) / ((n - 1) * (n - 2))


def erdos_renyi(n, m, rng):
    """A random graph on the same number of families and alliances."""
    if n < 2:
        return []
    edges = set()
    limit = n * (n - 1) // 2
    m = min(m, limit)
    while len(edges) < m:
        a = rng.randrange(n)
        b = rng.randrange(n)
        if a != b:
            edges.add((min(a, b), max(a, b)))
    return sorted(edges)


def null_baseline(n, m, draws=NULL_DRAWS, seed=NULL_SEED):
    """What clustering and centralization a graph this size and this sparse
    shows for no reason at all.

    Both statistics move with size and density, and across these periods size
    and density move by an order of magnitude: 57 families at mean degree 1.4
    in 1775, 1,654 at 3.8 by 2025. So the raw series cannot be read across
    periods -- a fall in centralization is what growth alone would produce.
    Each period is therefore also measured against random graphs with its own
    n and its own m, and it is the ratio to that baseline, not the level, that
    is comparable over time.
    """
    cl, ce = [], []
    rng = random.Random(seed)
    for _ in range(draws):
        nb = neighbours(erdos_renyi(n, m, rng))
        # Isolated nodes carry no ties but do count toward centralization.
        for node in range(n):
            nb.setdefault(node, set())
        cl.append(clustering(nb))
        ce.append(centralization(nb))
    return statistics.mean(cl), statistics.mean(ce)


def degree_preserving(edges, draws=NULL_DRAWS, seed=NULL_SEED):
    """Clustering under a null that keeps every family's number of allies.

    The stricter null, and the one `rodovid.audit` uses on the network as a
    whole. The difference between this and the random-graph baseline is the
    whole question of where closure comes from: if a period's triangles
    survive a rewiring that preserves the degree sequence, families are
    marrying into circles; if they do not, the triangles are what having a few
    very widely married houses forces, and no more.
    """
    rng = random.Random(seed)
    return statistics.mean(clustering(neighbours(rewire(edges, rng)))
                           for _ in range(draws))


def measure(edges, label=""):
    """The structure of one alliance graph, against two nulls.

    `label` prefixes every key, so the same measurements can be reported for
    the cumulative network and for one window without either shadowing the
    other.
    """
    nb = neighbours(edges)
    n, m = len(nb), len(edges)
    degrees = {f: len(v) for f, v in nb.items()}
    top = max(sorted(degrees), key=lambda f: (degrees[f], f)) if degrees else ""
    obs_cl, obs_ce = clustering(nb), centralization(nb)
    null_cl, null_ce = null_baseline(n, m)
    lcc = largest_component(nb)
    out = {
        "families": n,
        "alliances": m,
        "mean_degree": round(2 * m / n, 3) if n else 0,
        "largest_component": lcc,
        "share_in_lcc": round(lcc / n, 3) if n else 0,
        "clustering": round(obs_cl, 4),
        "clustering_vs_random": round(obs_cl / null_cl, 2) if null_cl else "",
        "clustering_vs_degree_null": round(obs_cl / degree_preserving(edges), 2)
                                     if obs_cl and m > 2 else "",
        "centralization": round(obs_ce, 4),
        "centralization_vs_random": round(obs_ce / null_ce, 2) if null_ce else "",
        "top_family": top,
        "top_family_allies": degrees.get(top, 0),
        "top_family_share": round(degrees.get(top, 0) / (n - 1), 3) if n > 1 else 0,
    }
    return {label + k: v for k, v in out.items()}


def evolution(marriages):
    """One row per period: the standing alliance network, and what is new.

    Measured twice, because the two answer different questions and only
    together are they safe to read.

    **Cumulative** (unprefixed columns) is every alliance contracted up to and
    including the period, which is the right stock for a relation that does not
    expire: a marriage alliance made in 1850 still ties those families in 1900.

    **Windowed** (`w_` columns) is only the alliances contracted inside the
    period. It exists because the cumulative series has a mechanical bias that
    would otherwise be mistaken for a finding: a house present from 1775
    accumulates allies for two centuries while a house arriving in 1950 has one
    generation to do it, so cumulative concentration rises even if no period's
    marriage market is concentrated at all. If a house leads the window as well
    as the stock, that is the marriage market and not the arithmetic.
    """
    on_graph = [m for m in marriages if m["on_graph"] == "1"]
    periods = sorted({m["period"] for m in on_graph if m["period"] >= FIRST_PERIOD})
    seen_pairs = collections.Counter()
    rows = []
    for period in periods:
        upto = [m for m in on_graph if m["period"] <= period]
        new = [m for m in on_graph if m["period"] == period]
        edges = sorted({(m["family_a"], m["family_b"]) for m in upto})
        new_pairs = {(m["family_a"], m["family_b"]) for m in new}
        first_time = {p for p in new_pairs if seen_pairs[p] == 0}
        for p in new_pairs:
            seen_pairs[p] += 1

        endo = [m for m in marriages
                if m["period"] == period and m["endogamous"] == "1"]
        before = {f for m in upto if m["period"] < period
                  for f in (m["family_a"], m["family_b"])}
        arriving = {f for m in new for f in (m["family_a"], m["family_b"])} - before
        window_edges = sorted({(m["family_a"], m["family_b"]) for m in new})
        rows.append({
            "period": period,
            "new_marriages": len(new),
            "new_alliances": len(first_time),
            "new_families": len(arriving),
            # A couple in the 2000 bin was born 2000-2024 and marries around
            # 2030. Those windows are truncated by construction rather than
            # thin in the source, so the flow columns there are not a decline
            # in anything and the figures stop before them. The stock is still
            # the whole network, so the rows stay.
            "window_complete": "1" if period <= LAST_COMPLETE else "0",
            **measure(edges),
            "endogamous_marriages": len(endo),
            "endogamy_rate": round(len(endo) / (len(new) + len(endo)), 3)
                             if (len(new) + len(endo)) else 0,
            **measure(window_edges, "w_"),
        })
    return rows


def panel(marriages):
    """Family pair x period, the dynamic edge list.

    One row per pair per period in which they married, with a cumulative count
    alongside the new one: `marriages` is the flow, `marriages_cumulative` the
    standing weight of the tie as of that period. Long format, which is what
    networkDynamic, Gephi's timeline and a panel regression all want.
    """
    on_graph = [m for m in marriages if m["on_graph"] == "1"]
    by_pair = collections.defaultdict(collections.Counter)
    for m in on_graph:
        by_pair[(m["family_a"], m["family_b"])][m["period"]] += 1
    rows = []
    for (a, b), periods in sorted(by_pair.items()):
        running = 0
        for period in sorted(periods):
            running += periods[period]
            rows.append({"family_a": a, "family_b": b, "period": period,
                         "marriages": periods[period],
                         "marriages_cumulative": running,
                         "first_period": min(periods)})
    rows.sort(key=lambda r: (r["period"], r["family_a"], r["family_b"]))
    return rows


# ---- validation ------------------------------------------------------------

def validate(people, parents, children, peers, cal, holdout=0.9, seed=0):
    """Hold out observed birth years, re-derive them, and report the error.

    Held out heavily on purpose. At a 20% holdout almost every test person sits
    one hop from a year that was kept, so the deep hops -- which carry a fifth
    of the dated alliances -- come back with five test cases and no usable
    error. Holding out nine in ten forces the propagation to travel, and is the
    harder and more honest test.

    The result is still optimistic in one way that cannot be fixed by
    resampling: everyone testable here is a person whose birth year *was*
    recorded, and such people sit in the better-documented parts of the graph.
    """
    observed = {p: d["birth"] for p, d in people.items() if d["birth"]}
    ids = sorted(observed)
    random.Random(seed).shuffle(ids)
    held = set(ids[:int(len(ids) * holdout)])
    kept = {p: y for p, y in observed.items() if p not in held}

    est = propagate(kept, people, parents, children, peers, cal["gap"])
    by_hop = collections.defaultdict(list)
    for p in sorted(held):
        if p in est:
            by_hop[est[p][1]].append(est[p][0] - observed[p])

    rows = []
    every = []
    for hop in sorted(by_hop):
        errs = by_hop[hop]
        every += errs
        rows.append(_error_row(f"kin, hop {hop}", errs))
    rows.append(_error_row("all kinship estimates", every))

    # The death-year fallback, scored the same way on people who have both.
    both = [d for d in people.values() if d["birth"] and d["death"]
            and 0 <= d["death"] - d["birth"] <= 110]
    rows.append(_error_row("death year - median lifespan",
                           [(d["death"] - cal["life"]) - d["birth"] for d in both]))
    return rows, len(held), len(kept)


def _error_row(label, errs):
    absolute = sorted(abs(e) for e in errs)
    return {
        "estimate": label, "n": len(errs),
        "median_error": round(statistics.median(errs), 1) if errs else 0,
        "mae": round(statistics.mean(absolute), 1) if errs else 0,
        "within_10": round(sum(a <= 10 for a in absolute) / len(absolute), 3) if errs else 0,
        "within_25": round(sum(a <= 25 for a in absolute) / len(absolute), 3) if errs else 0,
    }


def write_validation(rows, held, kept, cal, coverage):
    DOCS.mkdir(parents=True, exist_ok=True)
    path = DOCS / "VALIDATION-rodovid-dynamic.md"
    out = [
        "# Validation — dating the rodovid alliances", "",
        "Generated by `make rodovid-validate`. Every number here is measured on "
        "this dataset, and the whole table is recomputed on each run.", "",
        "## The offsets propagation uses", "",
        "| quantity | measured | n |", "|---|---|---|",
        f"| parent-child birth gap | **{cal['gap']} years** "
        f"(IQR {cal['gap_iqr'][0]:.0f}-{cal['gap_iqr'][1]:.0f}) | {cal['gap_n']} pairs |",
        f"| median lifespan | **{cal['life']} years** | {cal['life_n']} people |",
        f"| spouse/sibling birth gap | {cal['peer_gap']:.1f} years, unsigned | "
        f"{cal['peer_n']} pairs |", "",
        "The spouse and sibling gap is small and carries no usable direction, so "
        "propagation across those ties adds nothing to the year. Only the "
        "parent-child gap is an offset.", "",
        "## Error, against held-out birth years", "",
        f"{held:,} of the {held + kept:,} observed birth years were held out and "
        f"re-derived from the remaining {kept:,}. Holding out nine in ten forces "
        "the propagation to travel far enough to test the deep hops, which carry "
        "about a fifth of the dated alliances; at a light holdout they come back "
        "with too few test cases to score.", "",
        "| estimate | n | median error | MAE | within 10y | within 25y |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        out.append(f"| {r['estimate']} | {r['n']:,} | {r['median_error']:+.0f} | "
                   f"{r['mae']:.1f} | {r['within_10']:.0%} | {r['within_25']:.0%} |")
    out += [
        "", "The last row is scored in sample and is the weaker number on this "
        "page: the median lifespan it subtracts was measured on the same people "
        "it is tested against, and everyone in it had both dates recorded. Read "
        "it as the best case for that fallback, which is why anything resting "
        "on it is labelled `death` in the tables.",
        "", "Median error near zero at every hop: the estimator is close to "
        "unbiased, and the error grows with distance rather than drifting in one "
        "direction. **Within 25 years is the line that matters** — it is one "
        "period bin, which is the resolution anything downstream of this claims.",
        "", "Two ways this is optimistic, neither fixable by resampling:", "",
        "1. Everyone testable here is a person whose birth year *was* recorded, "
        "and such people sit in the better-documented parts of the graph. The "
        "people who actually need an estimate are in thinner country.",
        "2. The held-out person's relatives are the same relatives the estimate "
        "uses in production, so the graph around them is as good as it gets.",
        "", "## Coverage", "",
        "| | n | share |", "|---|---:|---:|",
    ]
    for label, n, d in coverage:
        out.append(f"| {label} | {n:,} | {n / d:.0%} |")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return path


# ---- output ----------------------------------------------------------------

def write(path, rows, columns):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, columns, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--validate", action="store_true",
                    help="also write the held-out error table to docs/")
    args = ap.parse_args(argv)

    ensure_dirs()
    people, ties = load()
    parents, children, peers = kinship(ties)
    cal = calibrate(people, parents, children, peers)
    print("measured on this dataset: parent-child gap %d years (IQR %.0f-%.0f, "
          "n=%d), median lifespan %d (n=%d)"
          % (cal["gap"], cal["gap_iqr"][0], cal["gap_iqr"][1], cal["gap_n"],
             cal["life"], cal["life_n"]))

    est, quality, dropped = date_people(people, parents, children, peers, cal)
    bands = collections.Counter(quality.values())
    print("dated %d of %d people (%.0f%%): %s"
          % (len(est), len(people), 100 * len(est) / len(people),
             ", ".join("%s %d" % (q, bands[q]) for q in QUALITY_ORDER if bands[q])))
    if dropped:
        print("  %d estimates dropped as impossible (after %d or before 1300)"
              % (dropped, THIS_YEAR))

    rows = []
    for p in sorted(people, key=int):
        if p not in est:
            continue
        d = people[p]
        rows.append({
            "id": p, "fullname": d["fullname"], "surname": d["surname"],
            "birth_year": est[p][0], "quality": quality[p], "hop": est[p][1],
            "birth_observed": d["birth"] or "", "death_observed": d["death"] or "",
            "approximate": "1" if d["approx"] else "0",
        })
    write(PERSON_YEARS, rows, ["id", "fullname", "surname", "birth_year",
                               "quality", "hop", "birth_observed",
                               "death_observed", "approximate"])

    marriages = dated_marriages(people, ties, est, quality)
    all_couples = len(couples(ties))
    on_graph = [m for m in marriages if m["on_graph"] == "1"]
    print("dated %d of %d couples (%.0f%%); %d are alliances between two "
          "families and carry the panel"
          % (len(marriages), all_couples, 100 * len(marriages) / all_couples,
             len(on_graph)))
    write(MARRIAGES, marriages, ["id_a", "id_b", "name_a", "name_b", "family_a",
                                 "family_b", "cohort_year", "period", "quality",
                                 "dates_known", "endogamous", "on_graph"])

    panel_rows = panel(marriages)
    write(ALLIANCE_PANEL, panel_rows, ["family_a", "family_b", "period",
                                       "marriages", "marriages_cumulative",
                                       "first_period"])
    evo = evolution(marriages)
    write(EVOLUTION, evo, list(evo[0]) if evo else [])
    print("panel: %d family-pair-periods over %d periods, %s-%s"
          % (len(panel_rows), len(evo), evo[0]["period"], evo[-1]["period"]))
    for r in evo:
        print("  %d  families %4d  alliances %4d  new %3d  lcc %3d (%.0f%%)  "
              "clustering %.3f  centralization %.3f  top %s (%d)"
              % (r["period"], r["families"], r["alliances"], r["new_marriages"],
                 r["largest_component"], 100 * r["share_in_lcc"],
                 r["clustering"], r["centralization"], r["top_family"],
                 r["top_family_allies"]))

    if args.validate:
        vrows, held, kept = validate(people, parents, children, peers, cal)
        coverage = [
            ("people with an observed birth year", cal["observed"], len(people)),
            ("people dated at all", len(est), len(people)),
            ("couples dated", len(marriages), all_couples),
            ("alliances on the family graph, dated", len(on_graph),
             sum(1 for a, b in couples(ties)
                 if a in people and b in people
                 and is_family(people[a]["surname"]) and is_family(people[b]["surname"])
                 and people[a]["surname"] != people[b]["surname"])),
        ]
        path = write_validation(vrows, held, kept, cal, coverage)
        print("wrote %s" % path.relative_to(path.parents[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
