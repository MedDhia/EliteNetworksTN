"""Tests for the connection-centrality analysis.

The statistics here are the kind that fail silently: a stratified estimator
that quietly ignores its strata, a permutation test that shuffles across
blocks instead of within them, a rank function that mishandles ties. None of
those raise; they just return a confident wrong number. Each is pinned below
against a case with a known answer.
"""

from __future__ import annotations

import sys
from pathlib import Path

import networkx as nx
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bourse.analysis_connection_centrality import (
    build_graph, centrality, percentile_ranks, permutation_test,
    stratified_diff, strata_of, treated_sets,
)


def _edge(src, tgt, **kw):
    base = {"source_id": src, "target_id": tgt, "source_type": "firm",
            "target_type": "firm", "source_name": src, "target_name": tgt,
            "layer": "board_interlock", "year": "2015", "doc_node_key": "d1"}
    return {**base, **kw}


class TestBuildGraph:
    def test_parallel_ties_become_one_weighted_edge(self):
        g, _ = build_graph([_edge("A", "B", doc_node_key="d1"),
                            _edge("A", "B", doc_node_key="d2")])
        assert g.number_of_edges() == 1
        assert g["A"]["B"]["weight"] == 2

    def test_person_firm_ties_are_excluded(self):
        # The firm-firm network is the object of study; a person-firm seat is
        # the raw material of the interlock projection, not a firm-firm tie.
        g, _ = build_graph([_edge("P", "A", source_type="person")])
        assert g.number_of_edges() == 0

    def test_self_loops_are_excluded(self):
        g, _ = build_graph([_edge("A", "A")])
        assert g.number_of_edges() == 0

    def test_document_counts_are_distinct_documents(self):
        _, docs = build_graph([_edge("A", "B", doc_node_key="d1"),
                               _edge("A", "B", doc_node_key="d1"),
                               _edge("A", "C", doc_node_key="d2")])
        assert docs["A"] == 2
        assert docs["C"] == 1

    def test_a_person_endpoint_still_counts_towards_exposure(self):
        # Exposure is "how much was this firm filed on", which a person-firm
        # board seat evidences even though it adds no firm-firm edge.
        _, docs = build_graph([_edge("P", "A", source_type="person")])
        assert docs["A"] == 1


class TestPercentileRanks:
    def test_ties_share_the_average_rank(self):
        r = percentile_ranks(np.array([5.0, 5.0, 1.0, 9.0]))
        assert r[0] == r[1]

    def test_order_is_preserved(self):
        r = percentile_ranks(np.array([1.0, 2.0, 3.0]))
        assert r[0] < r[1] < r[2]

    def test_all_equal_values_all_rank_the_same(self):
        # A centrality that is constant must produce a zero effect, not a
        # spurious ordering from argsort's tie-breaking.
        r = percentile_ranks(np.zeros(6))
        assert len(set(r)) == 1

    def test_ranks_lie_in_the_unit_interval(self):
        r = percentile_ranks(np.array([3.0, 1.0, 4.0, 1.0, 5.0]))
        assert r.min() > 0 and r.max() <= 1


class TestStrata:
    def test_bins_follow_the_document_count(self):
        s = strata_of(np.array([1, 2, 3, 4, 5, 9, 10, 50], dtype=float))
        assert list(s) == [0, 1, 2, 2, 3, 3, 4, 4]

    def test_a_degenerate_count_does_not_crash(self):
        assert len(strata_of(np.ones(10))) == 10


class TestStratifiedDiff:
    def test_a_stratum_without_both_groups_is_skipped(self):
        # The whole point: stratum 1 has no control, so it must not
        # contribute. Without the skip its treated firms would be compared
        # against controls from a different exposure level.
        ranks = np.array([0.1, 0.9, 0.5, 0.5])
        treat = np.array([True, False, True, True])
        strata = np.array([0, 0, 1, 1])
        assert stratified_diff(ranks, treat, strata) == pytest.approx(0.1 - 0.9)

    def test_strata_are_weighted_by_treated_count(self):
        ranks = np.array([1.0, 0.0, 1.0, 0.0, 1.0, 0.0])
        treat = np.array([True, False, True, True, False, False])
        strata = np.array([0, 0, 1, 1, 1, 1])
        # Stratum 0: 1 treated, gap 1.0. Stratum 1: 2 treated, mean treated
        # rank 0.5, mean control 0.5, gap 0.0. Weighted: (1*1 + 2*0)/3.
        assert stratified_diff(ranks, treat, strata) == pytest.approx(1 / 3)

    def test_no_comparable_stratum_gives_nan(self):
        ranks = np.array([0.5, 0.5])
        treat = np.array([True, True])
        assert np.isnan(stratified_diff(ranks, treat, np.array([0, 0])))

    def test_an_unstratified_mean_would_differ(self):
        # Guards the reason the estimator exists. A large control-only
        # stratum of peripheral firms drags a raw difference in means, but
        # must not move the stratified estimate at all.
        ranks = np.concatenate([np.array([0.9, 0.8]), np.zeros(100)])
        treat = np.array([True, False] + [False] * 100)
        strata = np.array([0, 0] + [1] * 100)
        raw = ranks[treat].mean() - ranks[~treat].mean()
        assert stratified_diff(ranks, treat, strata) == pytest.approx(0.9 - 0.8)
        assert raw > 0.5  # the number the stratification is there to avoid


class TestPermutationTest:
    def test_a_real_separation_is_detected(self):
        ranks = np.concatenate([np.linspace(0.9, 1.0, 20), np.linspace(0, 0.5, 80)])
        treat = np.array([True] * 20 + [False] * 80)
        strata = np.zeros(100, dtype=int)
        out = permutation_test(ranks, treat, strata, n_iter=500)
        assert out["diff"] > 0 and out["p"] < 0.01

    def test_noise_is_not_detected(self):
        rng = np.random.default_rng(0)
        ranks = rng.random(200)
        treat = np.zeros(200, dtype=bool)
        treat[rng.choice(200, 40, replace=False)] = True
        out = permutation_test(ranks, treat, np.zeros(200, dtype=int), n_iter=500)
        assert out["p"] > 0.05

    def test_permuting_within_strata_removes_a_pure_exposure_effect(self):
        # Centrality is perfectly determined by the stratum, and every firm
        # in a stratum is identical. A test that shuffled across strata would
        # call this a large effect; shuffling within them must not.
        ranks = np.array([0.9] * 10 + [0.1] * 10)
        treat = np.array([True] * 5 + [False] * 5 + [True] * 5 + [False] * 5)
        strata = np.array([0] * 10 + [1] * 10)
        out = permutation_test(ranks, treat, strata, n_iter=500)
        assert out["diff"] == pytest.approx(0.0)
        assert out["p"] > 0.5

    def test_the_test_is_deterministic(self):
        ranks = np.linspace(0, 1, 60)
        treat = np.array([True] * 20 + [False] * 40)
        strata = np.zeros(60, dtype=int)
        a = permutation_test(ranks, treat, strata, n_iter=200)
        b = permutation_test(ranks, treat, strata, n_iter=200)
        assert a == b


class TestCentrality:
    @pytest.fixture
    def star(self):
        g = nx.Graph()
        for leaf in "BCDE":
            g.add_edge("A", leaf, weight=1)
        return g

    def test_the_hub_leads_every_measure(self, star):
        c = centrality(star)
        for m in ("degree", "strength", "betweenness"):
            assert c[m]["A"] == max(c[m].values())

    def test_core_number_does_not_single_out_a_star_hub(self, star):
        # The point of including core: a star has a central node by degree
        # and betweenness but no dense group, so every node is in the
        # 1-core. This is what makes core disagree with degree in the report.
        c = centrality(star)
        assert len(set(c["core"].values())) == 1

    def test_core_number_rises_inside_a_clique(self):
        g = nx.complete_graph(5)
        g.add_edge(0, "pendant")
        c = centrality(g)
        assert c["core"][0] > c["core"]["pendant"]

    def test_every_measure_covers_every_node(self, star):
        c = centrality(star)
        for m, vals in c.items():
            assert set(vals) == set(star.nodes()), m

    def test_structurally_identical_nodes_tie_exactly(self):
        # Betweenness accumulates path counts in iteration order, so nodes in
        # identical positions came out differing by ~1e-17. Ranking groups
        # ties by exact equality, so that noise split a genuine tie into two
        # ranks. Symmetric graphs must produce exactly equal values.
        g = nx.barbell_graph(6, 3)
        c = centrality(g)
        bt = c["betweenness"]
        # The barbell is symmetric about its middle: node i and its mirror
        # must have identical betweenness.
        n = g.number_of_nodes()
        for i in range(n // 2):
            assert bt[i] == bt[n - 1 - i], i

    def test_centrality_is_invariant_to_graph_copying(self):
        # A copy can iterate in a different order; the reported numbers must
        # not depend on that, or the committed report is not reproducible.
        g = nx.barbell_graph(8, 4)
        assert centrality(g) == centrality(nx.Graph(g))


class TestTreatedSets:
    def test_firm_years_collapse_to_ever_connected(self):
        rows = [{"entity_id": "F1", "pc_officeholder": "1", "pc_broad": "1"},
                {"entity_id": "F1", "pc_officeholder": "0", "pc_broad": "1"}]
        sets = treated_sets(rows)
        assert sets["pc_officeholder"] == {"F1"}

    def test_any_state_is_the_union_of_the_two_state_channels(self):
        rows = [{"entity_id": "F1", "pc_state_ownership": "1"},
                {"entity_id": "F2", "pc_state_board": "1"}]
        assert treated_sets(rows)["pc_any_state"] == {"F1", "F2"}

    def test_zero_flags_produce_no_membership(self):
        rows = [{"entity_id": "F1", "pc_officeholder": "0", "pc_broad": "0"}]
        assert treated_sets(rows)["pc_officeholder"] == set()
