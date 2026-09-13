"""Women's position in the board network, year by year - and what is estimable.

The question this answers is how women's *centrality* in the interlock network
evolves. It arrives at a mostly negative answer for the strict version of that
question and a positive one for a weaker version, and the distinction is the
substance rather than a caveat.

Betweenness in a board network is brokerage between firms: it is non-zero only
for a director who sits on more than one board, because nobody else lies on a
path between two firms. Across 2005-2026 the number of *women* holding more
than one seat in a given year runs from 0 to 6, and is zero in eight of the
twenty-two years. A yearly series of women's mean betweenness computed on that
is not a trend; it is one or two people moving in and out of the sample. This
module therefore reports:

* **yearly** - participation (share of directors) and the size of the brokerage
  pool, both of which are estimable;
* **pooled** - betweenness by gender over the whole window, where n is 104
  women against 587 men and a distributional comparison holds.

Centrality is computed on the bipartite director-firm graph rather than on the
one-mode projection of shared directors. Projecting turns every board into a
clique, which inflates the centrality of anyone on a large board for a reason
that has nothing to do with brokerage; in the bipartite graph a director's
betweenness rises only when they actually connect firms that are otherwise
further apart.

Gender comes from honorifics printed in the filings - see ``bourse.gender``.
About two thirds of directors never carry one, and they are reported as
unknown throughout rather than folded into either group.

Run with::

    PYTHONPATH=src python -m bourse.analysis_women_centrality

Writes data/processed/bourse/women_centrality.csv and .md.
"""

from __future__ import annotations

import csv
import gzip
from collections import defaultdict

import networkx as nx
import numpy as np

from .common import PROCESSED, log
from .gender import load as load_gender

EDGES = PROCESSED / "multiplex_edges_observed.csv.gz"
OUT_CSV = PROCESSED / "women_centrality.csv"
OUT_MD = PROCESSED / "women_centrality.md"

# The layers that put a named person on a named company's board or executive.
SEAT_LAYERS = ("board_seat", "declared_mandate", "declared_executive")
ORGISH = {"firm", "fund", "state"}

# Before 2005 the corpus holds a handful of directors a year and almost no
# honorifics, so a yearly figure there is noise; §6.4 of the codebook sets the
# same boundary for the dataset as a whole.
FIRST_YEAR, LAST_YEAR = 2005, 2026

# Betweenness accumulates path counts in graph iteration order, so nodes in
# identical structural positions can differ by ~1e-17 and rank apart. Rounding
# below any real difference makes the figure reproducible.
DP = 12


def read_seats() -> dict[int, list[tuple[str, str]]]:
    """year -> [(person_id, org_id)] for every director-firm seat observed."""
    out: dict[int, list[tuple[str, str]]] = defaultdict(list)
    with gzip.open(EDGES, "rt", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["layer"] not in SEAT_LAYERS:
                continue
            try:
                year = int(r["year"])
            except (ValueError, TypeError):
                continue
            if r["source_type"] == "person" and r["target_type"] in ORGISH:
                person, org = r["source_id"], r["target_id"]
            elif r["target_type"] == "person" and r["source_type"] in ORGISH:
                person, org = r["target_id"], r["source_id"]
            else:
                continue
            if person and org:
                out[year].append((person, org))
    return out


def bipartite_betweenness(seats: list[tuple[str, str]]) -> dict[str, float]:
    """Betweenness of the person nodes in the director-firm graph."""
    g = nx.Graph()
    for person, org in seats:
        g.add_node(person, kind="person")
        g.add_node(org, kind="org")
        g.add_edge(person, org)
    if g.number_of_nodes() < 3:
        return {}
    bc = nx.betweenness_centrality(g, normalized=True)
    return {n: round(bc[n], DP) for n, d in g.nodes(data=True)
            if d["kind"] == "person"}


def yearly(seats_by_year, gender) -> list[dict]:
    rows = []
    for year in range(FIRST_YEAR, LAST_YEAR + 1):
        seats = seats_by_year.get(year, [])
        if not seats:
            continue
        boards = defaultdict(set)
        for person, org in seats:
            boards[person].add(org)
        bc = bipartite_betweenness(seats)

        def tally(pred):
            people = [p for p in boards if pred(gender.get(p))]
            multi = [p for p in people if len(boards[p]) > 1]
            vals = np.array([bc.get(p, 0.0) for p in people]) if people else np.zeros(0)
            return people, multi, vals

        women, w_multi, w_bc = tally(lambda g: g == "F")
        men, m_multi, m_bc = tally(lambda g: g == "M")
        unk, u_multi, _ = tally(lambda g: g is None)
        n_gendered = len(women) + len(men)
        rows.append({
            "year": year,
            "directors": len(boards),
            "women": len(women),
            "men": len(men),
            "unknown_gender": len(unk),
            "pct_women_of_gendered": (100 * len(women) / n_gendered) if n_gendered else "",
            "pct_unknown": 100 * len(unk) / len(boards) if boards else "",
            "women_multi_board": len(w_multi),
            "men_multi_board": len(m_multi),
            "unknown_multi_board": len(u_multi),
            "women_mean_betweenness": f"{w_bc.mean():.6f}" if len(w_bc) else "",
            "men_mean_betweenness": f"{m_bc.mean():.6f}" if len(m_bc) else "",
            "women_share_of_betweenness": (
                f"{100 * w_bc.sum() / (w_bc.sum() + m_bc.sum()):.2f}"
                if (w_bc.sum() + m_bc.sum()) > 0 else ""),
        })
    return rows


def pooled(seats_by_year, gender) -> dict:
    """Betweenness over the whole window, where n supports a comparison."""
    seats = [s for y, ss in seats_by_year.items()
             if FIRST_YEAR <= y <= LAST_YEAR for s in ss]
    bc = bipartite_betweenness(seats)
    boards = defaultdict(set)
    for person, org in seats:
        boards[person].add(org)
    out = {}
    for label, want in (("women", "F"), ("men", "M"), ("unknown", None)):
        people = [p for p in boards if gender.get(p) == want] if want else \
                 [p for p in boards if gender.get(p) is None]
        v = np.array([bc.get(p, 0.0) for p in people]) if people else np.zeros(0)
        multi = [p for p in people if len(boards[p]) > 1]
        out[label] = {
            "n": len(people),
            "n_multi_board": len(multi),
            "pct_multi_board": 100 * len(multi) / len(people) if people else 0.0,
            "n_nonzero": int((v > 0).sum()),
            "pct_nonzero": 100 * (v > 0).sum() / len(v) if len(v) else 0.0,
            "mean": float(v.mean()) if len(v) else 0.0,
            "max": float(v.max()) if len(v) else 0.0,
            "share_of_total": 0.0,
        }
    total = sum(out[k]["mean"] * out[k]["n"] for k in out)
    for k in out:
        out[k]["share_of_total"] = (100 * out[k]["mean"] * out[k]["n"] / total
                                    if total else 0.0)
    return out


def report(rows: list[dict], pool: dict) -> str:
    first, last = rows[0], rows[-1]
    w, m = pool["women"], pool["men"]
    early = [r for r in rows if r["year"] <= 2015 and r["pct_women_of_gendered"] != ""]
    late = [r for r in rows if r["year"] >= 2016 and r["pct_women_of_gendered"] != ""]
    mean_early = np.mean([r["pct_women_of_gendered"] for r in early])
    mean_late = np.mean([r["pct_women_of_gendered"] for r in late])
    zero_years = sum(1 for r in rows if r["women_multi_board"] == 0)

    return "\n".join([
        "# Women in the board network, 2005–2026",
        "",
        "Gender is read from the honorific the filer printed — see",
        "`bourse.gender`. It is not guessed from given names. The price is that",
        f"**{min(r['pct_unknown'] for r in rows):.0f}–"
        f"{max(r['pct_unknown'] for r in rows):.0f}% of directors in any year "
        "carry no honorific and are counted as unknown, never as men.** Every "
        "share below is of the *gendered* subset.",
        "",
        "## What is estimable: participation",
        "",
        f"Women were {mean_early:.1f}% of gendered directors on average across",
        f"2005–2015 and {mean_late:.1f}% across 2016–2026, reaching",
        f"{last['pct_women_of_gendered']:.1f}% in {last['year']}. That series rests on",
        "tens to low hundreds of directors a year and is the solid finding here.",
        "",
        "## What is not: a yearly betweenness series",
        "",
        "Betweenness in a board network is brokerage between firms, and it is",
        "non-zero only for a director sitting on more than one board — nobody",
        "else lies on a path between two firms. The number of women holding",
        "more than one seat in a year runs from",
        f"{min(r['women_multi_board'] for r in rows)} to "
        f"{max(r['women_multi_board'] for r in rows)}, and is **zero in "
        f"{zero_years} of the {len(rows)} years**.",
        "",
        "A yearly mean betweenness computed on that is not a trend. It is one",
        "or two people entering and leaving the sample, and plotting it as a",
        "line would give a reader a shape to interpret that the data does not",
        "support. The column is written to the CSV for completeness and is",
        "deliberately not drawn as a time series.",
        "",
        "## What the pooled window supports",
        "",
        "Over 2005–2026 together, where n is large enough to compare",
        "distributions:",
        "",
        "| | Directors | On >1 board | With non-zero betweenness | Mean betweenness |",
        "|---|---:|---:|---:|---:|",
        f"| Women | {w['n']} | {w['n_multi_board']} ({w['pct_multi_board']:.0f}%) | "
        f"{w['n_nonzero']} ({w['pct_nonzero']:.0f}%) | {w['mean']:.5f} |",
        f"| Men | {m['n']} | {m['n_multi_board']} ({m['pct_multi_board']:.0f}%) | "
        f"{m['n_nonzero']} ({m['pct_nonzero']:.0f}%) | {m['mean']:.5f} |",
        "",
        f"Women's mean betweenness is {100 * w['mean'] / m['mean']:.0f}% of men's, "
        f"and a man is about {m['pct_nonzero'] / max(w['pct_nonzero'], 1e-9):.1f}× "
        "more likely than a woman to broker between firms at all. The gap is in "
        "*reach*, not only in numbers: women are not merely fewer on boards, "
        "they are disproportionately on one board each.",
        "",
        "## What this cannot settle",
        "",
        "**The unknown two thirds.** If honorifics are printed more often for",
        "women than for men — plausible, since a title marks the exception in a",
        "male-dominated list — then the gendered subset over-represents women",
        "and the participation series is biased upward. Nothing here rules that",
        "out, and it is the first thing to check against an external roster.",
        "",
        "**Direction.** These are co-occurrences. Women may hold fewer multiple",
        "seats because they arrive later and accumulate seats more slowly, or",
        "because the recruitment that produces multiple seats excludes them.",
        "The dated appointment layer is far too thin to separate the two.",
        "",
        "**Coverage.** A director enters this network when a filing names them,",
        "so the yearly counts move with filing volume as much as with boards.",
        "See §6.4 of the codebook.",
    ]) + "\n"


FIELDS = ["year", "directors", "women", "men", "unknown_gender",
          "pct_women_of_gendered", "pct_unknown", "women_multi_board",
          "men_multi_board", "unknown_multi_board", "women_mean_betweenness",
          "men_mean_betweenness", "women_share_of_betweenness"]


def main() -> None:
    gender = load_gender()
    if not gender:
        log.error("no director_gender.csv; run `python -m bourse.gender` first")
        return
    seats = read_seats()
    rows = yearly(seats, gender)
    pool = pooled(seats, gender)

    with OUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.2f}" if isinstance(v, float) else v)
                        for k, v in r.items()})
    text = report(rows, pool)
    OUT_MD.write_text(text, encoding="utf-8")
    log.info("%-38s %6d rows", OUT_CSV.name, len(rows))
    print(text)


if __name__ == "__main__":
    main()
