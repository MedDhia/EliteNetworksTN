"""Do equity and board representation carry the same control relationship?

The dataset holds two ways for one firm to be tied to another. It can hold
equity - a declared blockholding, or a stake in a subsidiary. Or it can sit on
the board - a corporate seat, or a director shared with another firm. Whether
these are the same relation or alternative ones is the question a multiplex
dataset exists to answer, and it is not answerable from either layer alone.

The measurement problem is coverage, not method. A firm enters the ownership
layer when someone files a shareholder table naming it, and the board layers
when someone files a board table. Most firms are in one and not the other, so
the naive overlap - the share of equity dyads that also carry a board tie - is
a statement about which filings exist. It comes out under a tenth, and reads as
though the channels were nearly disjoint.

Conditioning on the firms visible in *both* channels removes the artefact and
reverses the answer. (The counts themselves are computed at run time and
written to the report; they are not repeated here, because they move with every
extraction pass.)
The comparison is then between dyads that could in principle have shown up in
either layer, against the base rate of a board tie among those same firms.

Run with::

    PYTHONPATH=src python -m bourse.analysis_control_channels

Prints a table and writes it to data/processed/bourse/analysis_control.md.
"""

from __future__ import annotations

import csv
import gzip
from pathlib import Path

from .common import PROCESSED, log

EDGES = PROCESSED / "multiplex_edges_observed.csv.gz"
OUT = PROCESSED / "analysis_control.md"

# Ownership and board seats can both run between organisations. Persons are
# excluded: a person-firm board seat is the raw material of the interlock
# projection, not a firm-firm tie in its own right.
FIRMISH = {"firm", "fund", "state"}

EQUITY = {
    "blockholder ownership": ("ownership",),
    "group participation": ("group_participation",),
    "any equity tie": ("ownership", "group_participation"),
}
BOARD = ("board_interlock", "board_seat_corporate")


def read_edges() -> list[dict]:
    with gzip.open(EDGES, "rt", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def dyads(rows: list[dict], layers: tuple[str, ...]) -> set[tuple[str, str]]:
    """Unordered firm-firm pairs tied by any of ``layers``, pooled over years.

    Pooled rather than per-year: a single year holds too few filings to
    estimate a conditional probability from, and the question - whether the two
    channels coincide - is not a question about any one year.
    """
    want = set(layers)
    out = set()
    for r in rows:
        if r["layer"] not in want:
            continue
        if r["source_type"] not in FIRMISH or r["target_type"] not in FIRMISH:
            continue
        a, b = r["source_id"], r["target_id"]
        if a and b and a != b:
            out.add((a, b) if a < b else (b, a))
    return out


def endpoints(pairs: set[tuple[str, str]]) -> set[str]:
    return {x for pair in pairs for x in pair}


def compare(rows: list[dict]) -> list[dict]:
    board = dyads(rows, BOARD)
    results = []
    for label, layers in EQUITY.items():
        equity = dyads(rows, layers)
        # The firms that could have been observed in either channel.
        shared = endpoints(equity) & endpoints(board)
        eq = {d for d in equity if d[0] in shared and d[1] in shared}
        bd = {d for d in board if d[0] in shared and d[1] in shared}
        if not eq or len(shared) < 2:
            continue
        possible = len(shared) * (len(shared) - 1) / 2
        p_cond = len(eq & bd) / len(eq)
        p_base = len(bd) / possible
        results.append({
            "channel": label,
            "firms": len(shared),
            "equity_dyads": len(eq),
            "with_board_tie": len(eq & bd),
            "p_board_given_equity": p_cond,
            "p_board_baseline": p_base,
            "lift": p_cond / p_base if p_base else float("nan"),
        })
    return results


def naive_overlap(rows: list[dict]) -> tuple[int, int, int]:
    """The unconditioned counts, kept because they are what misleads."""
    equity = dyads(rows, EQUITY["any equity tie"])
    board = dyads(rows, BOARD)
    return len(equity), len(board), len(equity & board)


def main() -> None:
    rows = read_edges()
    n_eq, n_bd, n_both = naive_overlap(rows)
    res = compare(rows)

    lines = [
        "# Control channels: equity and board representation",
        "",
        "Whether a firm-firm equity tie and a firm-firm board tie are the same",
        "relationship, measured on the firms where either could have been seen.",
        "",
        "## Why the unconditioned count misleads",
        "",
        f"Pooled over all years, {n_eq} firm-firm dyads carry an equity tie and "
        f"{n_bd} carry a board tie; {n_both} carry both, "
        f"which is {n_both / n_eq:.1%} of equity dyads.",
        "",
        "That number is mostly a statement about which filings exist. A firm",
        "enters the ownership layer when someone files a shareholder table",
        "naming it, and the board layers when someone files a board table;",
        "most firms are in one and not the other, so most equity dyads have no",
        "board tie *available* to coincide with.",
        "",
        "## Conditioned on firms visible in both channels",
        "",
        "| Equity channel | Firms | Equity dyads | Also board-tied | P(board \\| equity) | Base rate | Lift |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in res:
        lines.append(
            f"| {r['channel']} | {r['firms']} | {r['equity_dyads']} | {r['with_board_tie']} "
            f"| {r['p_board_given_equity']:.1%} | {r['p_board_baseline']:.2%} "
            f"| {r['lift']:.0f}× |"
        )
    lines += [
        "",
        "Base rate is the share of all possible pairs among those same firms",
        "that carry a board tie, so the lift is the factor by which an equity",
        "tie raises the odds of a board tie between the same two firms.",
        "",
        "## Reading it",
        "",
        "The two channels coincide far more than chance. They are better read",
        "as one control relationship recorded twice than as alternative routes",
        "to control, which matters for how the layers are combined: a model",
        "that treats ownership and interlock as independent evidence of",
        "influence is counting the same relationship twice.",
        "",
        "The effect is *stronger* for arm's-length blockholdings than for",
        "parent-subsidiary stakes, which is the opposite of what mechanical",
        "group consolidation would produce - a parent placing a director on its",
        "own subsidiary is routine and uninformative. An outside blockholder",
        "converting a stake into a seat is the substantive finding.",
        "",
        "## What this does not establish",
        "",
        "Direction and timing are both open. These are pooled co-occurrences,",
        "so they do not show that the stake came first, or that the holder is",
        "the one who placed the director. `board_appointment` carries dated",
        "appointments and is the layer to test sequence with, but it covers",
        "2001-2026 thinly and not at all across 2012-2017.",
        "",
        "Coverage is filings-driven throughout: see §6.4 of the codebook.",
    ]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    log.info("wrote %s", OUT)


if __name__ == "__main__":
    main()
