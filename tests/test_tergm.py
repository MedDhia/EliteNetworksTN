"""TERGM re-indexing: the bipartite ordering, the risk set, and the lags.

Everything here is a claim the R side cannot check for itself. A bipartite
network object is an assertion about vertex-id *ordering*, and `network` will
happily build one from a key that violates it; a covariate measured at t
instead of t-1 is still a number; a risk set with a hole still estimates. None
of those produce an error, which is why they are pinned here.
"""
from elitenet.tergm import build

P1, P2 = "PERSON_A", "PERSON_B"
O1, O2 = "CO_ONE", "CO_TWO"


def panel_row(period, person, org, role="gerant", spell=None, certainty="certain"):
    return {"panel_id": f"yearly:{period}", "from_node_id": person,
            "to_node_id": org, "role_canonical": role, "certainty": certainty,
            "spell_id": spell or f"SP_{person}_{org}"}


def spell_row(person, org, role="gerant", terminus="", right_censored="True",
              link_status="resolved"):
    return {"spell_id": f"SP_{person}_{org}", "person_id": person,
            "person_label": person.replace("PERSON_", ""), "org_id": org,
            "org_label": org.replace("CO_", ""), "role_canonical": role,
            "terminus": terminus, "right_censored": right_censored,
            "link_status": link_status}


def node(nid, ntype, degree="1"):
    return {"node_id": nid, "label": nid.split("_", 1)[1], "node_type": ntype,
            "seed_degree": degree}


def run(panel, spells, seed_nodes=None, seed_edges=None, events=None,
        resolution=None):
    return build(panel=panel, spells=spells,
                 seed_nodes=seed_nodes if seed_nodes is not None else [],
                 seed_edges=seed_edges or [], events=events or [],
                 resolution=resolution or [])


# --- the bipartite ordering -------------------------------------------------

def test_vertex_ids_are_mode_blocked():
    # Two persons and two organisations, deliberately named so that sorting
    # them together would interleave the modes (CO_ before PERSON_).
    out = run([panel_row("2008", P1, O1), panel_row("2008", P2, O2)],
              [spell_row(P1, O1), spell_row(P2, O2)])
    key = {r["node_id"]: r for r in out["node_key"]}
    persons = [r["vertex_id"] for r in out["node_key"] if r["mode"] == 1]
    orgs = [r["vertex_id"] for r in out["node_key"] if r["mode"] == 2]
    assert max(persons) < min(orgs), "a person id must never exceed an org id"
    assert sorted(persons + orgs) == [1, 2, 3, 4]
    assert out["diag"]["n_persons"] == 2
    assert key[P1]["mode"] == 1 and key[O1]["mode"] == 2


def test_every_edge_runs_from_mode_one_to_mode_two():
    out = run([panel_row("2008", P1, O1)], [spell_row(P1, O1)])
    n1 = out["diag"]["n_persons"]
    for e in out["edges"]:
        assert e["tail"] <= n1 < e["head"]


# --- the risk set -----------------------------------------------------------

def _birth(org, iso):
    return ([{"org_mention": org, "event_type": "constituted", "event_date": iso}],
            [{"org_mention": org, "resolved_org_id": org}])


def test_firm_is_not_at_risk_before_it_is_constituted():
    events, resolution = _birth(O1, "2010-06-01")
    out = run([panel_row("2011", P1, O1)], [spell_row(P1, O1)],
              events=events, resolution=resolution)
    act = {r["period"]: r["active"] for r in out["activity"]
           if r["vertex_id"] == 2}          # the only organisation
    assert act["2008"] == 0 and act["2009"] == 0, "a firm that did not exist yet"
    assert act["2010"] == 1 and act["2011"] == 1 and act["2012"] == 1


def test_firm_is_not_at_risk_after_it_is_dissolved():
    events = [{"org_mention": O1, "event_type": "dissolved",
               "event_date": "2010-03-01"}]
    resolution = [{"org_mention": O1, "resolved_org_id": O1}]
    out = run([panel_row("2009", P1, O1)], [spell_row(P1, O1)],
              events=events, resolution=resolution)
    act = {r["period"]: r["active"] for r in out["activity"]
           if r["vertex_id"] == 2}
    # Still at risk during the year it dies -- it existed for part of it.
    assert act["2009"] == 1 and act["2010"] == 1
    assert act["2011"] == 0 and act["2012"] == 0


def test_firm_with_no_lifecycle_dates_is_left_censored_and_always_at_risk():
    out = run([panel_row("2010", P1, O1)], [spell_row(P1, O1)])
    act = {r["period"]: r["active"] for r in out["activity"]
           if r["vertex_id"] == 2}
    assert all(v == 1 for v in act.values())
    assert all(r["birth_known"] == 0 for r in out["activity"]
               if r["vertex_id"] == 2)


def test_risk_window_widens_to_cover_an_observed_tie_and_stays_contiguous():
    # The firm is recorded as constituted in 2011 but holds a tie in 2008.
    # One of the two is wrong; excluding 2008 would make an observed tie a
    # structural zero, and punching a hole would claim the firm vanished.
    events, resolution = _birth(O1, "2011-01-01")
    out = run([panel_row("2008", P1, O1), panel_row("2012", P1, O1)],
              [spell_row(P1, O1)], events=events, resolution=resolution)
    act = [r["active"] for r in sorted(
        (r for r in out["activity"] if r["vertex_id"] == 2),
        key=lambda r: r["period"])]
    assert act == [1, 1, 1, 1, 1], "widened to the observed tie, no hole"
    assert out["diag"]["risk_widened_start"] == 1


def test_persons_are_at_risk_throughout_and_say_so():
    # The gazette records appointments, not births. Treating a person as absent
    # before their first appointment would encode the register's coverage as if
    # it were the person's existence.
    out = run([panel_row("2012", P1, O1)], [spell_row(P1, O1)])
    act = [r["active"] for r in out["activity"] if r["vertex_id"] == 1]
    assert act == [1, 1, 1, 1, 1]


def test_an_ambiguous_org_mention_dates_nothing():
    # "Mise a jour des statuts" is a section heading org_name() mistakes for a
    # firm; in the real corpus it resolves to three unrelated companies. Using
    # it would stamp all three with one birth date.
    events = [{"org_mention": "HEADING", "event_type": "constituted",
               "event_date": "2011-01-01"}]
    resolution = [{"org_mention": "HEADING", "resolved_org_id": O1},
                  {"org_mention": "HEADING", "resolved_org_id": O2}]
    out = run([panel_row("2008", P1, O1)], [spell_row(P1, O1)],
              events=events, resolution=resolution)
    assert all(r["birth_known"] == 0 for r in out["activity"])


# --- covariates -------------------------------------------------------------

def kin(a, b, label="PARENT"):
    return {"from_node_id": a, "to_node_id": b, "tie_class": "kinship",
            "edge_label_raw": label}


def test_kin_in_org_fires_only_through_a_kinship_tie_and_only_from_the_lag():
    # B holds a post in O1 in 2008. A is B's child. So for 2009, the dyad
    # (A, O1) carries kin_in_org: a relative was already inside.
    out = run([panel_row("2008", P2, O1), panel_row("2009", P1, O2)],
              [spell_row(P2, O1), spell_row(P1, O2)],
              seed_edges=[kin(P1, P2)])
    rows = {(r["period"], r["tail"], r["head"]): r for r in out["dyads"]}
    a, o1 = 1, 3                      # PERSON_A -> 1, CO_ONE -> 3
    assert rows[("2009", a, o1)]["kin_in_org"] == 1
    # Not in 2008: the covariate is lagged, and 2008 has no prior period.
    assert not any(p == "2008" for p, _t, _h in rows)


def test_kin_in_org_does_not_fire_without_a_kinship_tie():
    # Identical structure, but the two people are unrelated.
    out = run([panel_row("2008", P2, O1), panel_row("2009", P1, O2)],
              [spell_row(P2, O1), spell_row(P1, O2)], seed_edges=[])
    assert all(r["kin_in_org"] == 0 for r in out["dyads"])


SHAREHOLDING = {"from_node_id": O1, "to_node_id": O2,
                "tie_class": "ownership", "edge_label_raw": "SHAREHOLDER"}


def test_owner_of_follows_the_shareholder_direction():
    # O1 is a shareholder of O2, and A sits in O1 at t-1. The covariate belongs
    # on (A, O2) -- the firm A's company owns -- not on (A, O1). O2 needs a tie
    # of its own to be a vertex at all; see the next test.
    out = run([panel_row("2008", P1, O1), panel_row("2009", P1, O1),
               panel_row("2008", P2, O2)],
              [spell_row(P1, O1), spell_row(P2, O2)],
              seed_edges=[SHAREHOLDING])
    rows = {(r["period"], r["tail"], r["head"]): r for r in out["dyads"]}
    o1 = next(r["vertex_id"] for r in out["node_key"] if r["node_id"] == O1)
    o2 = next(r["vertex_id"] for r in out["node_key"] if r["node_id"] == O2)
    assert rows[("2009", 1, o2)]["owner_of"] == 1
    assert rows.get(("2009", 1, o1), {}).get("owner_of", 0) == 0


def test_owner_of_cannot_point_at_a_firm_that_is_not_a_vertex():
    # The seed sheet knows of 14,933 companies; only the ones carrying a dated
    # tie become vertices. A shareholding edge into a firm outside the panel
    # has no dyad to land on, and must be dropped rather than crash or invent
    # a vertex the risk set knows nothing about.
    out = run([panel_row("2008", P1, O1), panel_row("2009", P1, O1)],
              [spell_row(P1, O1)], seed_edges=[SHAREHOLDING])
    assert all(r["node_id"] != O2 for r in out["node_key"])
    assert all(r["owner_of"] == 0 for r in out["dyads"])


def test_dyad_table_is_sparse_carrying_only_nonzero_rows():
    out = run([panel_row("2008", P1, O1), panel_row("2009", P1, O1)],
              [spell_row(P1, O1)], seed_edges=[])
    # No kinship, no ownership, and a single member so no co-membership: the
    # whole covariate table is therefore empty rather than a wall of zeros.
    assert out["dyads"] == []


def test_lagged_degree_excludes_the_period_it_predicts():
    out = run([panel_row("2008", P1, O1), panel_row("2009", P1, O2)],
              [spell_row(P1, O1), spell_row(P1, O2)])
    attrs = {(r["period"], r["vertex_id"]): r for r in out["node_attrs"]}
    assert attrs[("2008", 1)]["cum_degree_lag"] == 0
    assert attrs[("2008", 1)]["cum_degree"] == 1
    assert attrs[("2009", 1)]["cum_degree_lag"] == 1     # only O1 so far
    assert attrs[("2009", 1)]["cum_degree"] == 2


# --- rectangularity ---------------------------------------------------------

def test_a_person_with_no_tie_in_a_period_is_still_a_vertex_that_period():
    # This is the whole reason the stage exists. Built from an edge list alone,
    # 2009 would contain neither A nor O1 and the vertex set would move.
    out = run([panel_row("2008", P1, O1), panel_row("2010", P1, O1)],
              [spell_row(P1, O1)])
    per_2009 = [r for r in out["node_attrs"] if r["period"] == "2009"]
    assert len(per_2009) == len(out["node_key"]) == 2
    assert {r["vertex_id"] for r in per_2009} == {1, 2}
    assert not any(e["period"] == "2009" for e in out["edges"])


def test_node_attrs_and_activity_are_rectangular():
    out = run([panel_row("2008", P1, O1), panel_row("2011", P2, O2)],
              [spell_row(P1, O1), spell_row(P2, O2)])
    n, periods = len(out["node_key"]), 5
    assert len(out["node_attrs"]) == n * periods
    assert len(out["activity"]) == n * periods


# --- ties -------------------------------------------------------------------

def test_two_roles_in_one_firm_collapse_to_one_binary_tie():
    # TERGM models a binary tie. Two roles is two panel rows and one tie, and
    # the roles are kept rather than silently discarded.
    out = run([panel_row("2008", P1, O1, role="pdg", spell="SP_a"),
               panel_row("2008", P1, O1, role="administrateur", spell="SP_b")],
              [dict(spell_row(P1, O1), spell_id="SP_a"),
               dict(spell_row(P1, O1), spell_id="SP_b")])
    assert len(out["edges"]) == 1
    assert out["edges"][0]["role_canonical"] == "administrateur|pdg"


def test_tie_keeps_the_strongest_certainty_and_resolved_status():
    out = run([panel_row("2008", P1, O1, role="pdg", spell="SP_a",
                         certainty="possible"),
               panel_row("2008", P1, O1, role="dg", spell="SP_b",
                         certainty="certain")],
              [dict(spell_row(P1, O1), spell_id="SP_a",
                    link_status="ambiguous"),
               dict(spell_row(P1, O1), spell_id="SP_b",
                    link_status="resolved")])
    assert out["edges"][0]["certainty"] == "certain"
    assert out["edges"][0]["link_status"] == "resolved"


def test_dissolution_observed_marks_only_spells_seen_to_end():
    out = run([panel_row("2008", P1, O1), panel_row("2008", P2, O2)],
              [spell_row(P1, O1, terminus="2008-06-01",
                         right_censored="False"),
               spell_row(P2, O2)])
    by_tail = {e["tail"]: e for e in out["edges"]}
    assert by_tail[1]["dissolution_observed"] == 1
    assert by_tail[2]["dissolution_observed"] == 0


# --- labels -----------------------------------------------------------------

def test_gazette_only_org_takes_its_label_from_the_spell():
    out = run([panel_row("2008", P1, O1)],
              [dict(spell_row(P1, O1), org_label="TANKOIL")], seed_nodes=[])
    org = next(r for r in out["node_key"] if r["node_id"] == O1)
    assert org["label"] == "TANKOIL"
    assert org["is_seed"] == 0


def test_a_role_clause_mistaken_for_a_firm_is_flagged_not_dropped():
    out = run([panel_row("2008", P1, O1)],
              [dict(spell_row(P1, O1),
                    org_label="directeur général et du président")])
    org = next(r for r in out["node_key"] if r["node_id"] == O1)
    assert org["label_suspect"] == 1
    # Flagged, still present: dropping it would change the panel, and this
    # stage only re-indexes it.
    assert len(out["edges"]) == 1


def test_a_long_real_firm_name_is_not_flagged():
    # An earlier version of the rule used length, and flagged four genuine
    # Tunisian firms whose names run past sixty characters.
    out = run([panel_row("2008", P1, O1)],
              [dict(spell_row(P1, O1),
                    org_label="Société d'Engrais et de Produits Chimiques "
                              "de Mégrine S.E.P.C.M")])
    org = next(r for r in out["node_key"] if r["node_id"] == O1)
    assert org["label_suspect"] == 0


def test_curated_seed_labels_are_never_flagged():
    out = run([panel_row("2008", P1, O1)], [spell_row(P1, O1)],
              seed_nodes=[node(P1, "PERSON"),
                          node(O1, "COMPANY")])
    assert all(r["label_suspect"] == 0 for r in out["node_key"])


def test_personal_shareholding_is_exogenous_so_needs_no_lag():
    # A person's own stake comes from the undated seed sheet, so it cannot be
    # caused by the tie being modelled. Unlike the three lagged covariates it
    # is therefore available in the first period too, where it is the only
    # dyadic predictor there is.
    out = run([panel_row("2008", P1, O1)], [spell_row(P1, O1)],
              seed_nodes=[node(P1, "PERSON"), node(O1, "COMPANY")],
              seed_edges=[{"from_node_id": P1, "to_node_id": O1,
                           "tie_class": "ownership",
                           "edge_label_raw": "SHAREHOLDER"}])
    rows = {(r["period"], r["tail"], r["head"]): r for r in out["dyads"]}
    assert rows[("2008", 1, 2)]["is_shareholder"] == 1
    assert len(rows) == 5, "one row per period, including the first"


def test_a_persons_stake_and_a_companys_stake_feed_different_covariates():
    # Both arrive as edge_label_raw == SHAREHOLDER. A stake held by a person is
    # is_shareholder on that dyad; a stake held by a company is owner_of on the
    # dyads of the people inside it. Conflating them would put an individual's
    # holding on every colleague's dyad.
    out = run([panel_row("2008", P1, O1), panel_row("2009", P1, O1),
               panel_row("2008", P2, O2)],
              [spell_row(P1, O1), spell_row(P2, O2)],
              seed_nodes=[node(P1, "PERSON"), node(P2, "PERSON"),
                          node(O1, "COMPANY"), node(O2, "COMPANY")],
              seed_edges=[{"from_node_id": P1, "to_node_id": O2,
                           "tie_class": "ownership",
                           "edge_label_raw": "SHAREHOLDER"},
                          {"from_node_id": O1, "to_node_id": O2,
                           "tie_class": "ownership",
                           "edge_label_raw": "SHAREHOLDER"}])
    o2 = next(r["vertex_id"] for r in out["node_key"] if r["node_id"] == O2)
    row = next(r for r in out["dyads"]
               if (r["period"], r["tail"], r["head"]) == ("2009", 1, o2))
    assert row["is_shareholder"] == 1     # A holds the stake personally
    assert row["owner_of"] == 1           # and sits in O1, which also holds one
    # B sits in O2 but owns nothing and is in no company that does.
    b_rows = [r for r in out["dyads"] if r["tail"] == 2]
    assert all(r["is_shareholder"] == 0 and r["owner_of"] == 0 for r in b_rows)
