# Control channels: equity and board representation

Whether a firm-firm equity tie and a firm-firm board tie are the same
relationship, measured on the firms where either could have been seen.

## Why the unconditioned count misleads

Pooled over all years, 1111 firm-firm dyads carry an equity tie and 3914 carry a board tie; 103 carry both, which is 9.3% of equity dyads.

That number is mostly a statement about which filings exist. A firm
enters the ownership layer when someone files a shareholder table
naming it, and the board layers when someone files a board table;
most firms are in one and not the other, so most equity dyads have no
board tie *available* to coincide with.

## Conditioned on firms visible in both channels

| Equity channel | Firms | Equity dyads | Also board-tied | P(board \| equity) | Base rate | Lift |
|---|---:|---:|---:|---:|---:|---:|
| blockholder ownership | 141 | 141 | 85 | 60.3% | 1.64% | 37× |
| group participation | 99 | 87 | 29 | 33.3% | 2.54% | 13× |
| any equity tie | 194 | 217 | 103 | 47.5% | 1.46% | 32× |

Base rate is the share of all possible pairs among those same firms
that carry a board tie, so the lift is the factor by which an equity
tie raises the odds of a board tie between the same two firms.

## Reading it

The two channels coincide far more than chance. They are better read
as one control relationship recorded twice than as alternative routes
to control, which matters for how the layers are combined: a model
that treats ownership and interlock as independent evidence of
influence is counting the same relationship twice.

The effect is *stronger* for arm's-length blockholdings than for
parent-subsidiary stakes, which is the opposite of what mechanical
group consolidation would produce - a parent placing a director on its
own subsidiary is routine and uninformative. An outside blockholder
converting a stake into a seat is the substantive finding.

## What this does not establish

Direction and timing are both open. These are pooled co-occurrences,
so they do not show that the stake came first, or that the holder is
the one who placed the director. `board_appointment` carries dated
appointments and is the layer to test sequence with, but it covers
2001-2026 thinly and not at all across 2012-2017.

Coverage is filings-driven throughout: see §6.4 of the codebook.
