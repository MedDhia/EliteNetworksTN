"""Are the structural holes real, or made by resolution?

The failure this stage exists to prevent is the worst kind available to this
dataset: a hole manufactured by failed resolution is indistinguishable from
brokerage, which is the thing a network analysis is looking for. So these
tests pin the measurement, and in particular that it reports a BOUND rather
than an estimate -- a single number here would be a claim the evidence cannot
support in either direction.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from elitenet import holes as H


# --- the projection the argument is made on ------------------------------ #

def test_two_people_at_one_firm_are_adjacent():
    adj = H.project_persons({("P_A", "CO_1"), ("P_B", "CO_1")})
    assert adj["P_A"] == {"P_B"} and adj["P_B"] == {"P_A"}


def test_two_people_at_different_firms_are_not():
    adj = H.project_persons({("P_A", "CO_1"), ("P_B", "CO_2")})
    assert adj["P_A"] == set() and adj["P_B"] == set()


def test_a_merge_hub_is_excluded_from_the_projection():
    """A hub connects everyone to everyone and would report the whole network
    as one dense blob -- the mirror of the error being measured. So the
    observed side is computed with the worst merges already removed, which
    makes it a conservative baseline rather than a flattering one."""
    hub = {(f"P_{i}", "CO_HUB") for i in range(80)}
    adj = H.project_persons(hub)
    assert all(not v for v in adj.values())
    # A plausible board is kept.
    board = {(f"P_{i}", "CO_REAL") for i in range(8)}
    adj2 = H.project_persons(board)
    assert len(adj2["P_0"]) == 7


def test_components_and_connected_pairs():
    # Two triangles, unconnected: 3 + 3 pairs.
    edges = {("A", "O1"), ("B", "O1"), ("C", "O1"),
             ("D", "O2"), ("E", "O2"), ("F", "O2")}
    adj = H.project_persons(edges)
    assert H.components(adj) == [3, 3]
    assert H.reachable_pairs(adj) == 3 + 3


def test_a_declined_edge_closes_a_hole_and_the_bound_widens():
    """The whole point. Two clusters look unbridged; one declined link would
    join them, and the difference between the two counts IS the exposure."""
    observed = {("A", "O1"), ("B", "O1"), ("C", "O2"), ("D", "O2")}
    declined = {("B", "O2")}
    obs = H.reachable_pairs(H.project_persons(observed))
    pot = H.reachable_pairs(H.project_persons(observed | declined))
    assert obs == 1 + 1                      # two separate pairs
    assert pot == 4 * 3 // 2                  # one component of four
    assert pot > obs


def test_an_empty_network_does_not_divide_by_zero():
    assert H.components({}) == []
    assert H.reachable_pairs(H.project_persons(set())) == 0


# --- the edge set is the one the argument would be made on --------------- #

def test_only_evidenced_tiers_count_as_asserted(tmp_path, monkeypatch):
    """A seed tie carried with no dates is not evidence of co-presence, so it
    must not silently fill a hole the gazette never closed."""
    monkeypatch.setattr(H, "PROCESSED", tmp_path)
    (tmp_path / "spells.csv").write_text(
        "person_id,org_id,evidence_tier\n"
        "P_A,CO_1,gazette_dated\n"
        "P_B,CO_1,gazette_inferred\n"
        "P_C,CO_1,gazette_snowball\n"
        "P_D,CO_1,seed_undated\n", encoding="utf-8")
    edges = H.person_org_edges()
    assert ("P_A", "CO_1") in edges
    assert ("P_B", "CO_1") in edges      # labelled, but still in print
    assert ("P_C", "CO_1") in edges
    assert ("P_D", "CO_1") not in edges  # undated: asserts no co-presence


def test_an_ambiguous_dyad_is_a_candidate_edge(tmp_path, monkeypatch):
    """An ambiguous dyad means the matcher declined to choose among several
    people, not that nobody was there. For a HOLE that distinction is weaker
    than for an identification: any candidate being right means the edge
    exists and the hole does not."""
    monkeypatch.setattr(H, "PROCESSED", tmp_path)
    (tmp_path / "review_queue.csv").write_text(
        "resolved_person_id,runner_up_person_id,resolved_org_id,org_candidate_id\n"
        "P_A,,CO_1,\n"
        ",P_B,,CO_2\n"
        ",,,\n", encoding="utf-8")
    edges, why = H.declined_person_org_edges()
    assert ("P_A", "CO_1") in edges
    assert ("P_B", "CO_2") in edges
    assert len(edges) == 2
    assert why["ambiguous_dyad"] == 2


# --- split organisations: the suspect that looks most like a finding ----- #

def test_one_identifier_on_two_nodes_is_a_split_candidate(tmp_path, monkeypatch):
    """Read one way it is a merge; read the other it is one firm split in two,
    and the second reading is what makes a false hole."""
    monkeypatch.setattr(H, "PROCESSED", tmp_path)
    (tmp_path / "org_identifiers.csv").write_text(
        "org_id,org_label,id_type,value_normalised\n"
        "CO_A,Alpha SA,matricule_fiscal,111111A\n"
        "CO_B,Alpha Holding,matricule_fiscal,111111A\n", encoding="utf-8")
    out = H.split_organisation_candidates()
    assert len(out) == 1
    assert {out[0]["left_id"], out[0]["right_id"]} == {"CO_A", "CO_B"}
    assert out[0]["basis"] == "shared_matricule_fiscal"


def test_an_identifier_on_many_nodes_is_not_a_split(tmp_path, monkeypatch):
    """A value on seven nodes is OCR damage or a collision, not one firm."""
    monkeypatch.setattr(H, "PROCESSED", tmp_path)
    rows = "\n".join(f"CO_{i},Firm {i},matricule_fiscal,222222B" for i in range(7))
    (tmp_path / "org_identifiers.csv").write_text(
        "org_id,org_label,id_type,value_normalised\n" + rows + "\n",
        encoding="utf-8")
    assert H.split_organisation_candidates() == []


def test_a_shared_seat_needs_a_shared_name_token(tmp_path, monkeypatch):
    """Two unrelated firms in one building are two firms, and the hole between
    them is real. Only a shared seat AND an overlapping name is a suspect."""
    monkeypatch.setattr(H, "PROCESSED", tmp_path)
    (tmp_path / "org_addresses.csv").write_text(
        "org_id,org_label,address_normalised\n"
        "CO_A,Societe Hexabyte Tunisie,12 rue de rome 1001 tunis\n"
        "CO_B,Hexabyte Tunisie SA,12 rue de rome 1001 tunis\n"
        "CO_C,Boulangerie du Nord,34 avenue de paris 1002 tunis\n"
        "CO_D,Cimenterie du Sud,34 avenue de paris 1002 tunis\n",
        encoding="utf-8")
    out = H.split_organisation_candidates()
    pairs = {frozenset((o["left_id"], o["right_id"])) for o in out}
    assert frozenset(("CO_A", "CO_B")) in pairs
    assert frozenset(("CO_C", "CO_D")) not in pairs


def test_a_bare_town_seat_is_not_a_suspect(tmp_path, monkeypatch):
    monkeypatch.setattr(H, "PROCESSED", tmp_path)
    (tmp_path / "org_addresses.csv").write_text(
        "org_id,org_label,address_normalised\n"
        "CO_A,Societe Alpha Tunisie,tunis\n"
        "CO_B,Alpha Tunisie SA,tunis\n", encoding="utf-8")
    assert H.split_organisation_candidates() == []


# --- split persons ------------------------------------------------------- #

def test_a_gazette_cluster_matching_one_seed_person_is_a_split(tmp_path, monkeypatch):
    """Splitting one person in two does not merely halve their degree -- it
    removes every path that ran through them, which is how a broker
    disappears and a hole appears in their place."""
    monkeypatch.setattr(H, "PROCESSED", tmp_path)
    (tmp_path / "seed_nodes.csv").write_text(
        "node_id,node_type,label\n"
        "P_HEX,PERSON,Slim Hexabyte\n", encoding="utf-8")
    (tmp_path / "gazette_only_persons.csv").write_text(
        "candidate_person_id,label,n_events,orgs\n"
        "GZ_1,Slim Hexabyte,4,Societe Alpha\n", encoding="utf-8")
    out = H.split_person_candidates()
    assert len(out) == 1 and out[0]["left_id"] == "P_HEX"


def test_two_seed_bearers_of_a_name_are_not_a_split(tmp_path, monkeypatch):
    """With two bearers the pair is not identifiable, and the right place for
    it is the ambiguity queue rather than a suspect list."""
    monkeypatch.setattr(H, "PROCESSED", tmp_path)
    (tmp_path / "seed_nodes.csv").write_text(
        "node_id,node_type,label\n"
        "P_1,PERSON,Mohamed Trabelsi\n"
        "P_2,PERSON,Mohamed Trabelsi\n", encoding="utf-8")
    (tmp_path / "gazette_only_persons.csv").write_text(
        "candidate_person_id,label,n_events,orgs\n"
        "GZ_1,Mohamed Trabelsi,9,Societe Beta\n", encoding="utf-8")
    assert H.split_person_candidates() == []


# --- low-degree nodes: where a missed tie changes the position in KIND --- #

def test_a_pendant_with_the_same_name_elsewhere_is_flagged(tmp_path, monkeypatch):
    """A degree-1 node has no closure and no brokerage and cannot sit on a
    path. A second organisation changes that in kind, not in degree, so every
    claim about who is peripheral rests on this band being genuinely sparse."""
    monkeypatch.setattr(H, "PROCESSED", tmp_path)
    (tmp_path / "resolution.csv").write_text(
        "person_mention,resolved_person_id,resolved_person_label,"
        "resolved_org_id,link_status\n"
        "Slim Hexabyte,P_A,Slim Hexabyte,CO_1,resolved\n"
        "Slim Hexabyte,P_A,Slim Hexabyte,CO_2,resolved\n", encoding="utf-8")
    rows, stats = H.low_degree_audit({("P_A", "CO_1")})
    assert stats["persons_degree_1_with_candidates"] == 1
    assert stats["pendants_that_may_be_brokers"] == 1
    assert rows[0]["candidate_extra_ties"] == 1
    assert rows[0]["would_become_degree"] == 2
    assert "same_name_elsewhere" in rows[0]["sources"]


def test_a_node_with_nothing_extra_is_confirmed_sparse(tmp_path, monkeypatch):
    """The majority case, and the one worth reporting: sparsity checked
    against the evidence rather than assumed."""
    monkeypatch.setattr(H, "PROCESSED", tmp_path)
    (tmp_path / "resolution.csv").write_text(
        "person_mention,resolved_person_id,resolved_person_label,"
        "resolved_org_id,link_status\n"
        "Slim Hexabyte,P_A,Slim Hexabyte,CO_1,resolved\n", encoding="utf-8")
    rows, stats = H.low_degree_audit({("P_A", "CO_1")})
    assert rows == []
    assert stats["persons_degree_1_confirmed_sparse"] == 1


def test_a_shared_name_cannot_answer_and_says_so(tmp_path, monkeypatch):
    """The guard that stops this audit manufacturing a flattering number. If
    two resolved nodes share the name key, "the same name elsewhere" is not
    evidence about either of them -- it is how a homonym becomes a hub. The
    honest output is that the question is unanswerable."""
    monkeypatch.setattr(H, "PROCESSED", tmp_path)
    (tmp_path / "resolution.csv").write_text(
        "person_mention,resolved_person_id,resolved_person_label,"
        "resolved_org_id,link_status\n"
        "Mohamed Trabelsi,P_A,Mohamed Trabelsi,CO_1,resolved\n"
        "Mohamed Trabelsi,P_B,Mohamed Trabelsi,CO_2,resolved\n"
        "Mohamed Trabelsi,P_A,Mohamed Trabelsi,CO_3,resolved\n", encoding="utf-8")
    rows, stats = H.low_degree_audit({("P_A", "CO_1")})
    assert rows == []
    assert stats["persons_whose_name_cannot_answer"] == 1


def test_a_declined_dyad_counts_as_a_candidate(tmp_path, monkeypatch):
    monkeypatch.setattr(H, "PROCESSED", tmp_path)
    (tmp_path / "resolution.csv").write_text(
        "person_mention,resolved_person_id,resolved_person_label,"
        "resolved_org_id,link_status\n"
        "Slim Hexabyte,P_A,Slim Hexabyte,CO_1,resolved\n", encoding="utf-8")
    (tmp_path / "review_queue.csv").write_text(
        "resolved_person_id,runner_up_person_id,resolved_org_id,org_candidate_id\n"
        "P_A,,CO_9,\n", encoding="utf-8")
    rows, stats = H.low_degree_audit({("P_A", "CO_1")})
    assert stats["persons_degree_1_with_candidates"] == 1
    assert "declined_dyad" in rows[0]["sources"]


def test_a_tie_already_asserted_is_not_counted_twice(tmp_path, monkeypatch):
    monkeypatch.setattr(H, "PROCESSED", tmp_path)
    (tmp_path / "resolution.csv").write_text(
        "person_mention,resolved_person_id,resolved_person_label,"
        "resolved_org_id,link_status\n"
        "Slim Hexabyte,P_A,Slim Hexabyte,CO_1,resolved\n", encoding="utf-8")
    (tmp_path / "review_queue.csv").write_text(
        "resolved_person_id,runner_up_person_id,resolved_org_id,org_candidate_id\n"
        "P_A,,CO_1,\n", encoding="utf-8")
    rows, stats = H.low_degree_audit({("P_A", "CO_1")})
    assert rows == [] and stats["persons_degree_1_confirmed_sparse"] == 1


def test_a_well_connected_node_is_out_of_scope(tmp_path, monkeypatch):
    """The audit is about the band where a missed tie changes the position in
    kind. A node with six ties gains degree from a seventh, not a role."""
    monkeypatch.setattr(H, "PROCESSED", tmp_path)
    (tmp_path / "resolution.csv").write_text(
        "person_mention,resolved_person_id,resolved_person_label,"
        "resolved_org_id,link_status\n"
        "Slim Hexabyte,P_A,Slim Hexabyte,CO_9,resolved\n", encoding="utf-8")
    obs = {("P_A", f"CO_{i}") for i in range(5)}
    rows, stats = H.low_degree_audit(obs)
    assert rows == []
    assert not any(k.startswith("persons_degree_") for k in stats)
