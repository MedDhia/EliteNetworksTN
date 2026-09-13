"""Tests for reading gender off honorifics, and for what follows from it.

The load-bearing decision here is that an unrecorded gender stays unknown.
Folding the unknown two thirds into "men" would understate women by
construction and would never raise an error, so the tests that matter most are
the ones asserting that nothing silently becomes a man.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from collections import Counter

from bourse.analysis_women_centrality import bipartite_betweenness, pooled, yearly
from bourse.gender import classify_title, decide, normalise_title


class TestTitleClassification:
    @pytest.mark.parametrize("raw", ["Mme", "mme", "MME", "Mme.", " Mme ",
                                     "Madame", "Mlle", "Mademoiselle"])
    def test_female_honorifics(self, raw):
        assert classify_title(raw) == "F"

    @pytest.mark.parametrize("raw", ["M", "M.", "m", "Mr", "MR", "Monsieur",
                                     "MM", "Messieurs"])
    def test_male_honorifics(self, raw):
        assert classify_title(raw) == "M"

    @pytest.mark.parametrize("raw", [None, "", "   ", "Dr", "Pr", "Me",
                                     "Président", "Administrateur", "Ing"])
    def test_a_title_that_records_no_gender_returns_none(self, raw):
        # "Dr" and "Pr" are deliberately not male. Reading a doctorate as a man
        # is exactly the kind of inference this module exists to avoid.
        assert classify_title(raw) is None

    def test_normalisation_strips_case_space_and_period(self):
        assert normalise_title("  MME.  ") == "mme"

    def test_the_two_sets_do_not_overlap(self):
        from bourse.gender import FEMALE, MALE
        assert not (FEMALE & MALE)


class TestDecide:
    def test_female_honorifics_decide_female(self):
        assert decide(Counter({"F": 3, "?": 9}))[0] == "F"

    def test_male_honorifics_decide_male(self):
        assert decide(Counter({"M": 1, "?": 40}))[0] == "M"

    def test_no_honorific_stays_unknown(self):
        # The single most important assertion in this file: absence of a title
        # is absence of information, never a man.
        gender, basis = decide(Counter({"?": 25}))
        assert gender == "unknown"
        assert "no honorific" in basis

    def test_conflicting_honorifics_stay_unknown(self):
        # Not resolved by majority: a person styled both ways is a data fault
        # worth surfacing, and a majority rule would bury it.
        gender, basis = decide(Counter({"F": 1, "M": 4}))
        assert gender == "unknown"
        assert "conflict" in basis

    def test_one_observation_is_enough(self):
        # A director styled "Mme" once and untitled in ten other filings is
        # still recorded as a woman; this is what lifts coverage from a third
        # of rows to a third of people.
        assert decide(Counter({"F": 1, "?": 10}))[0] == "F"


class TestBipartiteBetweenness:
    def test_a_director_on_one_board_cannot_broker(self):
        # The premise of the whole figure: betweenness is non-zero only for
        # someone sitting on more than one board.
        bc = bipartite_betweenness([("p1", "f1"), ("p2", "f1"), ("p3", "f2")])
        assert bc["p1"] == 0.0 and bc["p2"] == 0.0

    def test_a_director_bridging_two_boards_does(self):
        bc = bipartite_betweenness([("p1", "f1"), ("p1", "f2"),
                                    ("p2", "f1"), ("p3", "f2")])
        assert bc["p1"] > 0
        assert bc["p2"] == 0.0

    def test_only_person_nodes_are_returned(self):
        bc = bipartite_betweenness([("p1", "f1"), ("p1", "f2")])
        assert set(bc) == {"p1"}

    def test_firms_are_not_collapsed_into_a_clique(self):
        # The reason for the bipartite graph rather than the one-mode
        # projection: on a board of four, projecting makes every pair adjacent
        # and hands all four a centrality they did not earn by brokering.
        seats = [("p1", "f1"), ("p2", "f1"), ("p3", "f1"), ("p4", "f1")]
        assert all(v == 0.0 for v in bipartite_betweenness(seats).values())

    def test_a_graph_too_small_to_have_paths_returns_empty(self):
        assert bipartite_betweenness([("p1", "f1")]) == {}

    def test_structurally_identical_directors_tie_exactly(self):
        # Rounded, so float accumulation order cannot split a genuine tie and
        # make the figure depend on iteration order.
        seats = [("p1", "f1"), ("p1", "f2"), ("p2", "f3"), ("p2", "f4"),
                 ("bridge", "f1"), ("bridge", "f3")]
        bc = bipartite_betweenness(seats)
        assert bc["p1"] == bc["p2"]


def _seats():
    # 2020: one woman on two boards, one man on two, one untitled on one.
    return {2020: [("w1", "f1"), ("w1", "f2"),
                   ("m1", "f1"), ("m1", "f3"),
                   ("u1", "f2")]}


class TestYearly:
    def test_unknown_gender_is_counted_separately(self):
        rows = yearly(_seats(), {"w1": "F", "m1": "M"})
        r = rows[0]
        assert (r["women"], r["men"], r["unknown_gender"]) == (1, 1, 1)

    def test_share_is_of_the_gendered_subset_not_of_everyone(self):
        # 1 woman of 2 gendered is 50%, not 1 of 3 directors.
        rows = yearly(_seats(), {"w1": "F", "m1": "M"})
        assert rows[0]["pct_women_of_gendered"] == pytest.approx(50.0)

    def test_the_unknown_share_is_reported(self):
        rows = yearly(_seats(), {"w1": "F", "m1": "M"})
        assert rows[0]["pct_unknown"] == pytest.approx(100 / 3)

    def test_the_brokerage_pool_counts_multi_board_directors(self):
        rows = yearly(_seats(), {"w1": "F", "m1": "M"})
        r = rows[0]
        assert (r["women_multi_board"], r["men_multi_board"],
                r["unknown_multi_board"]) == (1, 1, 0)

    def test_years_outside_the_window_are_dropped(self):
        seats = {1998: [("w1", "f1"), ("w1", "f2")]}
        assert yearly(seats, {"w1": "F"}) == []


class TestPooled:
    def test_counts_split_three_ways(self):
        pool = pooled(_seats(), {"w1": "F", "m1": "M"})
        assert pool["women"]["n"] == 1
        assert pool["men"]["n"] == 1
        assert pool["unknown"]["n"] == 1

    def test_a_single_board_director_has_no_betweenness(self):
        pool = pooled(_seats(), {"w1": "F", "m1": "M"})
        assert pool["unknown"]["n_nonzero"] == 0

    def test_an_empty_group_does_not_divide_by_zero(self):
        pool = pooled(_seats(), {"m1": "M"})
        assert pool["women"]["n"] == 0
        assert pool["women"]["mean"] == 0.0
        assert pool["women"]["pct_nonzero"] == 0.0
