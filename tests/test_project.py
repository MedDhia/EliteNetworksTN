"""The whole dataset as one graph.

Four things these tests exist to pin, three of them mistakes made while
building this stage:

1. A node's type comes from the node, not the column it sits in. The seed
   sheet's family edges ride in `spells.csv` with the kin in the `org_id`
   column, and typing by column made 307 people into organisations and 829
   family ties into employment.
2. A register company the gazette also prints is ONE node. The identifier
   join is a node merge; treating it as an edge would tie a firm to itself
   and double every such company.
3. An isolate is data. A register company nobody filed about is a real
   company and a real absence of evidence, and those are only
   distinguishable if it is present with degree 0.
4. The tiers are nested, so a count can only rise as the tier widens. A
   count that falls means a tier dropped something a narrower one had.
"""
from __future__ import annotations

import csv
import gzip
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from elitenet import project as PJ


# --- typing a node -------------------------------------------------------- #

def test_the_seed_sheet_decides_a_type_it_knows():
    seed = {"PERSON_X": "PERSON", "CO_Y": "COMPANY", "GOV_Z": "GOVERNMENT"}
    assert PJ.node_kind("PERSON_X", seed) == "PERSON"
    assert PJ.node_kind("CO_Y", seed) == "ORGANISATION"
    assert PJ.node_kind("GOV_Z", seed) == "ORGANISATION"


def test_an_unknown_node_is_typed_from_its_prefix():
    assert PJ.node_kind("PERSON_UNSEEN", {}) == "PERSON"
    assert PJ.node_kind("ORGE_abc123", {}) == "ORGANISATION"
    assert PJ.node_kind("RNE_B1231999", {}) == "ORGANISATION"
    assert PJ.node_kind("RNEP_B1231999", {}) == "PERSON"


def test_a_person_in_the_organisation_column_is_still_a_person():
    """The bug this test exists for. `spells.csv` carries the seed sheet's
    own parent_of / sibling_of / spouse_of / student_of edges with the kin in
    `org_id`. Typing by column put 307 of them in the organisation set."""
    seed = {"PERSON_A": "PERSON", "PERSON_B": "PERSON"}
    assert PJ.node_kind("PERSON_B", seed) == "PERSON"


def test_a_node_typed_two_ways_is_marked_not_silently_picked():
    """A contradiction means the typing rule is wrong, so it is surfaced for
    the validator rather than resolved by whichever layer was read last."""
    g = PJ.Graph()
    g.add_node("X", "PERSON", "gazette", "seed_anchored")
    g.add_node("X", "ORGANISATION", "gazette", "seed_anchored")
    assert g.kind["X"] == "CONFLICT"


# --- the graph ------------------------------------------------------------ #

def test_an_isolate_is_a_node_with_no_edges():
    g = PJ.Graph()
    g.add_node("CO_ALONE", "ORGANISATION", "rne_company", "all_sources")
    assert "CO_ALONE" in g.adj
    assert g.adj["CO_ALONE"] == set()
    assert g.edges() == 0


def test_a_self_loop_is_not_an_edge():
    """One seed spell has the same person on both ends. A self-loop is not a
    relationship and would inflate the edge count."""
    g = PJ.Graph()
    g.add_node("PERSON_A", "PERSON", "seed", "seed_anchored")
    assert g.add_edge("PERSON_A", "PERSON_A") is False
    assert g.edges() == 0


def test_an_edge_is_undirected_and_counted_once():
    g = PJ.Graph()
    for n in ("A", "B"):
        g.add_node(n, "PERSON", "seed", "seed_anchored")
    assert g.add_edge("A", "B") is True
    assert g.add_edge("B", "A") is True      # idempotent on the adjacency
    assert g.edges() == 1


def test_components_are_labelled_and_isolates_are_their_own():
    g = PJ.Graph()
    for n in ("A", "B", "C", "D"):
        g.add_node(n, "PERSON", "seed", "seed_anchored")
    g.add_edge("A", "B")
    comp, sizes = g.label_components()
    assert sizes == [2, 1, 1]
    assert comp["A"] == comp["B"]
    assert comp["C"] != comp["D"]


# --- the end-to-end stage ------------------------------------------------- #

def _write(tmp_path, name, cols, rows):
    with (tmp_path / name).open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def _register(tmp_path, companies=(), persons=()):
    d = tmp_path / "rne"
    d.mkdir(parents=True, exist_ok=True)
    ccols = ["registres.numRegistre", "registres.identifiantUnique",
             "registres.denominationFr", "registres.categorie"]
    with gzip.open(d / "entreprises.csv.gz", "wt", encoding="utf-8",
                   newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=ccols)
        w.writeheader()
        for r in companies:
            w.writerow({c: r.get(c, "") for c in ccols})
    pcols = ["numRegistre", "identifiantUnique", "nomAr", "prenomAr"]
    with gzip.open(d / "personnes_physiques.csv.gz", "wt", encoding="utf-8",
                   newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=pcols)
        w.writeheader()
        for r in persons:
            w.writerow({c: r.get(c, "") for c in pcols})
    return d


def _minimal(tmp_path, monkeypatch, *, companies=(), persons=(),
             identifiers=()):
    monkeypatch.setattr(PJ, "PROCESSED", tmp_path)
    monkeypatch.setattr(PJ, "RNE", _register(tmp_path, companies, persons))
    _write(tmp_path, "seed_nodes.csv",
           ["node_id", "label", "node_type"],
           [{"node_id": "PERSON_A", "node_type": "PERSON"},
            {"node_id": "PERSON_B", "node_type": "PERSON"},
            {"node_id": "CO_ALPHA", "node_type": "COMPANY"}])
    # PERSON_B sits in the org_id column: a seed family tie, not employment.
    _write(tmp_path, "spells.csv",
           ["person_id", "org_id", "role_canonical", "evidence_tier"],
           [{"person_id": "PERSON_A", "org_id": "CO_ALPHA",
             "role_canonical": "gerant", "evidence_tier": "gazette_dated"},
            {"person_id": "PERSON_A", "org_id": "PERSON_B",
             "role_canonical": "sibling_of", "evidence_tier": "seed_undated"}])
    _write(tmp_path, "org_tie_spells.csv",
           ["holder_id", "target_id", "relation"], [])
    _write(tmp_path, "person_tie_spells.csv",
           ["person_id", "kin_id", "relation"], [])
    _write(tmp_path, "org_entity_members.csv",
           ["org_mention", "org_entity_id"],
           [{"org_mention": "Alpha", "org_entity_id": "CO_ALPHA"}])
    _write(tmp_path, "rne_company_persons.csv",
           ["person_key", "company_key", "org_entity_id"], [])
    _write(tmp_path, "resolution.csv",
           ["resolved_person_id", "mention_cluster_id", "org_mention"], [])
    _write(tmp_path, "org_identifiers.csv",
           ["value_normalised", "org_entity_id"], list(identifiers))


def test_the_seed_tier_types_the_kin_as_a_person(tmp_path, monkeypatch):
    _minimal(tmp_path, monkeypatch)
    g, diag = PJ.build("seed_anchored")
    assert g.kind["PERSON_B"] == "PERSON"
    assert diag["seed_person_person"] == 1
    assert diag["spell_person_organisation"] == 1
    row, _iso, _n = PJ.summarise("seed_anchored", g)
    assert row["individuals"] == 2
    assert row["organisations"] == 1


def test_a_register_company_the_gazette_prints_is_one_node(
        tmp_path, monkeypatch):
    """The identifier join is a node merge. If it were an edge instead, the
    firm would be tied to itself and counted twice."""
    _minimal(tmp_path, monkeypatch,
             companies=[{"registres.numRegistre": "B1231999",
                         "registres.identifiantUnique": "111111A",
                         "registres.denominationFr": "ALPHA"}],
             identifiers=[{"value_normalised": "111111A",
                           "org_entity_id": "CO_ALPHA"}])
    g, diag = PJ.build("all_sources")
    assert diag["register_company_merged_onto_gazette_entity"] == 1
    assert diag.get("register_company_standalone", 0) == 0
    assert "RNE_B1231999" not in g.adj
    # and no self-loop was created by the merge
    assert "CO_ALPHA" not in g.adj["CO_ALPHA"]


def test_a_register_company_the_gazette_never_names_is_an_isolate(
        tmp_path, monkeypatch):
    _minimal(tmp_path, monkeypatch,
             companies=[{"registres.numRegistre": "B9999999",
                         "registres.identifiantUnique": "999999Z",
                         "registres.denominationFr": "INCONNUE"}])
    g, diag = PJ.build("all_sources")
    assert diag["register_company_standalone"] == 1
    assert g.adj["RNE_B9999999"] == set()
    row, iso, _n = PJ.summarise("all_sources", g)
    assert row["isolates"] >= 1
    assert any(r["source"] == "rne_company" and r["n"] >= 1 for r in iso)


def test_a_sole_trader_whose_identifier_is_in_the_gazette_is_bridged(
        tmp_path, monkeypatch):
    """0.26% of them. The bridge is real and is the only thing that makes
    the sole-trader table more than a list."""
    _minimal(tmp_path, monkeypatch,
             persons=[{"numRegistre": "B5551999",
                       "identifiantUnique": "111111A", "nomAr": "x"}],
             identifiers=[{"value_normalised": "111111A",
                           "org_entity_id": "CO_ALPHA"}])
    g, diag = PJ.build("all_sources")
    assert diag["register_sole_trader_bridged"] == 1
    assert "CO_ALPHA" in g.adj["RNEP_B5551999"]
    assert g.kind["RNEP_B5551999"] == "PERSON"


def test_an_unbridged_sole_trader_is_counted_not_dropped(
        tmp_path, monkeypatch):
    _minimal(tmp_path, monkeypatch,
             persons=[{"numRegistre": "B7771999",
                       "identifiantUnique": "777777Q", "nomAr": "y"}])
    g, diag = PJ.build("all_sources")
    assert diag["register_sole_trader_unbridged"] == 1
    assert g.adj["RNEP_B7771999"] == set()


def test_duplicate_register_rows_do_not_become_two_nodes(
        tmp_path, monkeypatch):
    """The register file repeats 180,000 companies byte-identically."""
    row = {"registres.numRegistre": "B1112000",
           "registres.identifiantUnique": "222222B",
           "registres.denominationFr": "BETA"}
    _minimal(tmp_path, monkeypatch, companies=[row, row])
    g, diag = PJ.build("all_sources")
    assert diag["register_company_standalone"] == 1
    assert sum(1 for n in g.adj if n.startswith("RNE_")) == 1


def test_a_co_mention_is_an_edge_only_in_the_widest_tier(
        tmp_path, monkeypatch):
    """Co-mention is a much weaker relation than an affiliation, so it must
    not leak into the tier whose edges the pipeline defends."""
    _minimal(tmp_path, monkeypatch)
    _write(tmp_path, "resolution.csv",
           ["resolved_person_id", "mention_cluster_id", "org_mention"],
           [{"mention_cluster_id": "PERSON_STRANGER", "org_mention": "Alpha"}])
    seeded, _d = PJ.build("seed_anchored")
    assert "PERSON_STRANGER" not in seeded.adj
    widest, diag = PJ.build("all_sources")
    assert diag["co_mention_edges"] == 1
    assert "CO_ALPHA" in widest.adj["PERSON_STRANGER"]


def test_the_tiers_are_nested(tmp_path, monkeypatch):
    """Every count must rise or hold as the tier widens. A fall would mean a
    wider tier dropped something a narrower one had, which would make the
    three-way comparison meaningless."""
    _minimal(tmp_path, monkeypatch,
             companies=[{"registres.numRegistre": "B1231999",
                         "registres.identifiantUnique": "111111A"}],
             persons=[{"numRegistre": "B4441999",
                       "identifiantUnique": "444444D"}])
    _write(tmp_path, "resolution.csv",
           ["resolved_person_id", "mention_cluster_id", "org_mention"],
           [{"mention_cluster_id": "PERSON_STRANGER", "org_mention": "Alpha"}])
    _write(tmp_path, "rne_company_persons.csv",
           ["person_key", "company_key", "org_entity_id"],
           [{"person_key": "PERSON_OFFICER", "company_key": "B1231999",
             "org_entity_id": ""}])
    rows = []
    for tier in PJ.TIERS:
        g, _d = PJ.build(tier)
        rows.append(PJ.summarise(tier, g)[0])
    for key in ("nodes", "edges", "individuals", "organisations"):
        seq = [r[key] for r in rows]
        assert seq == sorted(seq), f"{key} is not monotonic across tiers: {seq}"


def test_the_summary_partitions_every_node(tmp_path, monkeypatch):
    _minimal(tmp_path, monkeypatch,
             companies=[{"registres.numRegistre": "B8881999",
                         "registres.identifiantUnique": "888888X"}])
    g, _d = PJ.build("all_sources")
    row, _iso, nodes = PJ.summarise("all_sources", g)
    assert row["individuals"] + row["organisations"] == row["nodes"]
    assert row["connected_nodes"] + row["isolates"] == row["nodes"]
    assert (row["giant_individuals"] + row["giant_organisations"]
            == row["giant_component"])
    assert len(nodes) == row["nodes"]
    assert sum(1 for n in nodes if n["degree"] == 0) == row["isolates"]


def test_run_writes_all_three_tables(tmp_path, monkeypatch):
    _minimal(tmp_path, monkeypatch,
             companies=[{"registres.numRegistre": "B1231999",
                         "registres.identifiantUnique": "111111A"}])
    diag = PJ.run()
    assert diag["rows"] == len(PJ.TIERS) * len(PJ.STATE_FLOORS)
    for name in ("projection_summary.csv", "projection_isolates.csv",
                 "projection_nodes.csv"):
        assert (tmp_path / name).exists(), name
    summary = list(csv.DictReader(
        (tmp_path / "projection_summary.csv").open(encoding="utf-8")))
    unfiltered = [r for r in summary if r["state_floor"] == "none"]
    assert [r["tier"] for r in unfiltered] == list(PJ.TIERS)
    # The node table is written once, for the UNFILTERED widest tier, with
    # each row also carrying its position under the decision floor.
    nodes = list(csv.DictReader(
        (tmp_path / "projection_nodes.csv").open(encoding="utf-8")))
    assert len(nodes) == int(unfiltered[-1]["nodes"])


def test_an_absent_register_still_produces_the_narrow_tiers(
        tmp_path, monkeypatch):
    """The register is an addition. Without it the seed-anchored tier must
    still be computable, because that is the tier most analysis uses."""
    _minimal(tmp_path, monkeypatch)
    monkeypatch.setattr(PJ, "RNE", tmp_path / "no-register-here")
    g, _d = PJ.build("all_sources")
    assert g.kind["CO_ALPHA"] == "ORGANISATION"
    row, _iso, _n = PJ.summarise("all_sources", g)
    assert row["nodes"] == 3


# --- the decision-level state floor --------------------------------------- #

def test_a_state_body_is_recognised_by_its_label():
    assert PJ.is_state_body("GOV_ANYTHING", "")
    assert PJ.is_state_body("ORGE_x", "MINISTERE DES FINANCES")
    assert PJ.is_state_body("ORGE_x", "PRESIDENCE DE LA REPUBLIQUE")
    assert not PJ.is_state_body("ORGE_x", "POULINA GROUP HOLDING")
    assert not PJ.is_state_body("RNE_B1231999", "STE ALPHA SARL")


def test_the_floor_is_board_member_and_above():
    assert PJ.clears_state_floor({"minister"})
    assert PJ.clears_state_floor({"administrateur"})
    assert PJ.clears_state_floor({"chef_de_cabinet"})
    assert PJ.clears_state_floor({"pdg"})
    # below it
    assert not PJ.clears_state_floor({"chef_de_service"})
    assert not PJ.clears_state_floor({"sous_directeur"})
    assert not PJ.clears_state_floor({"secretaire_general"})
    assert not PJ.clears_state_floor({"dga"})
    assert not PJ.clears_state_floor({"conseiller"})


def test_the_best_rank_ever_stated_decides_the_tie():
    """A person can appear at a body as a minister in one decree and with no
    rank in a later filing. The tie is judged on the best rank stated."""
    assert PJ.clears_state_floor({"chef_de_service", "minister"})


def test_an_unstated_rank_does_not_clear_the_floor():
    """33% of person-to-state co-mention rows state no role. An unstated rank
    is not evidence of seniority, so the decision-level counts are a lower
    bound rather than a census -- which is why the figure says so."""
    assert not PJ.clears_state_floor(set())


def _state_fixture(tmp_path, monkeypatch, role):
    monkeypatch.setattr(PJ, "PROCESSED", tmp_path)
    monkeypatch.setattr(PJ, "RNE", tmp_path / "no-register")
    _write(tmp_path, "seed_nodes.csv", ["node_id", "label", "node_type"],
           [{"node_id": "PERSON_A", "node_type": "PERSON"},
            {"node_id": "GOV_MIN", "label": "MINISTERE DES FINANCES",
             "node_type": "GOVERNMENT"},
            {"node_id": "CO_FIRM", "label": "POULINA GROUP HOLDING",
             "node_type": "COMPANY"}])
    _write(tmp_path, "spells.csv",
           ["person_id", "org_id", "org_label", "role_canonical"],
           [{"person_id": "PERSON_A", "org_id": "GOV_MIN",
             "org_label": "MINISTERE DES FINANCES", "role_canonical": role},
            {"person_id": "PERSON_A", "org_id": "CO_FIRM",
             "org_label": "POULINA GROUP HOLDING", "role_canonical": "gerant"}])
    for name, cols in (("org_tie_spells.csv", ["holder_id", "target_id"]),
                       ("person_tie_spells.csv", ["person_id", "kin_id"]),
                       ("org_entity_members.csv",
                        ["org_mention", "org_entity_id"]),
                       ("rne_company_persons.csv",
                        ["person_key", "company_key", "org_entity_id",
                         "roles"]),
                       ("resolution.csv",
                        ["resolved_person_id", "mention_cluster_id",
                         "org_mention", "role_observed"]),
                       ("org_entities.csv", ["org_entity_id", "label"]),
                       ("org_identifiers.csv",
                        ["value_normalised", "org_entity_id"])):
        _write(tmp_path, name, cols, [])


def test_a_minister_keeps_the_tie_to_the_ministry(tmp_path, monkeypatch):
    _state_fixture(tmp_path, monkeypatch, "minister")
    g, diag = PJ.build("seed_anchored", "decision")
    assert "GOV_MIN" in g.adj["PERSON_A"]
    assert diag["state_tie_clears_the_floor"] == 1


def test_a_chef_de_service_loses_the_tie_to_the_ministry(tmp_path, monkeypatch):
    """The rank that makes a ministry look like a hub: 18,900 such ties."""
    _state_fixture(tmp_path, monkeypatch, "chef_de_service")
    g, diag = PJ.build("seed_anchored", "decision")
    assert "GOV_MIN" not in g.adj["PERSON_A"]
    assert diag["state_tie_below_the_floor"] == 1


def test_the_private_sector_is_never_filtered(tmp_path, monkeypatch):
    """`gerant` is below the state floor, but a gerant of a SARL is the
    decision-maker of his own firm, so the floor must not touch it."""
    _state_fixture(tmp_path, monkeypatch, "chef_de_service")
    g, _d = PJ.build("seed_anchored", "decision")
    assert "CO_FIRM" in g.adj["PERSON_A"], "a private tie was filtered"


def test_the_floor_leaves_the_unfiltered_graph_alone(tmp_path, monkeypatch):
    _state_fixture(tmp_path, monkeypatch, "chef_de_service")
    g, diag = PJ.build("seed_anchored", "none")
    assert "GOV_MIN" in g.adj["PERSON_A"]
    assert "state_tie_below_the_floor" not in diag


def test_kinship_is_not_subject_to_a_rank_floor(tmp_path, monkeypatch):
    """A rank floor is about office. A sibling tie has no rank, and dropping
    it because it states none would delete the seed sheet's family layer."""
    _state_fixture(tmp_path, monkeypatch, "minister")
    _write(tmp_path, "seed_nodes.csv", ["node_id", "label", "node_type"],
           [{"node_id": "PERSON_A", "node_type": "PERSON"},
            {"node_id": "PERSON_B", "node_type": "PERSON"}])
    _write(tmp_path, "spells.csv",
           ["person_id", "org_id", "org_label", "role_canonical"],
           [{"person_id": "PERSON_A", "org_id": "PERSON_B",
             "role_canonical": "sibling_of"}])
    g, diag = PJ.build("seed_anchored", "decision")
    assert "PERSON_B" in g.adj["PERSON_A"]
    assert diag["seed_person_person"] == 1


def test_the_summary_carries_the_floor_it_was_built_at(tmp_path, monkeypatch):
    _state_fixture(tmp_path, monkeypatch, "minister")
    g, _d = PJ.build("seed_anchored", "decision")
    row, iso, _n = PJ.summarise("seed_anchored", g, "decision")
    assert row["state_floor"] == "decision"
    assert "decision-making rank" in row["edge_definition"]
    assert all(r["state_floor"] == "decision" for r in iso)


def test_run_writes_a_row_per_tier_and_floor(tmp_path, monkeypatch):
    _state_fixture(tmp_path, monkeypatch, "minister")
    diag = PJ.run()
    assert diag["rows"] == len(PJ.TIERS) * len(PJ.STATE_FLOORS)
    rows = list(csv.DictReader(
        (tmp_path / "projection_summary.csv").open(encoding="utf-8")))
    assert {r["state_floor"] for r in rows} == set(PJ.STATE_FLOORS)
    # A filter can only remove.
    by = {(r["tier"], r["state_floor"]): int(r["nodes"]) for r in rows}
    for tier in PJ.TIERS:
        assert by[(tier, "decision")] <= by[(tier, "none")]
    # The node table carries both views.
    nodes = list(csv.DictReader(
        (tmp_path / "projection_nodes.csv").open(encoding="utf-8")))
    assert nodes and all("degree_decision" in n for n in nodes)
