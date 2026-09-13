"""The kinship layer: grammar, extraction and tie construction.

The failure mode these tests exist to pin is the one the single grammar group
had: "nee X" is a woman's natal surname, not a husband, and folding it into the
marriage markers manufactures a spouse out of a birth name.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from elitenet import grammar as G
from elitenet import personties as PT


# --- the marker split ---------------------------------------------------- #

def test_marriage_markers_map_to_marriage():
    assert G.name_link_kind("épouse") == "spouse_of"
    assert G.name_link_kind("ép.") == "spouse_of"
    assert G.name_link_kind("EP") == "spouse_of"
    assert G.name_link_kind("EP.") == "spouse_of"
    assert G.name_link_kind("veuve") == "widow_of"
    assert G.name_link_kind("vve") == "widow_of"


def test_nee_is_a_maiden_name_not_a_spouse():
    """The whole reason the two markers are told apart."""
    assert G.name_link_kind("née") == "maiden_name_of"
    assert G.name_link_kind("nee") == "maiden_name_of"
    links = G.find_name_links("Madame Yosra Tritar née Chelly Ahmed a cédé")
    assert [r for _p, _o, r, _m, _i in links] == ["maiden_name_of"]


def test_unknown_marker_asserts_nothing():
    assert G.name_link_kind("frère") == ""
    assert G.name_link_kind("") == ""


# --- finding pairs in prose ---------------------------------------------- #

def test_untitled_prose_pair_is_found():
    """Two thirds of the corpus's markers sit in prose with no title, which is
    why the title-anchored pattern saw 984 of 41,088."""
    links = G.find_name_links(
        "la nommée Fekria Bent Mohamed Osman épouse Ben Salem Ali a vendu")
    assert links[0][0] == "Fekria Bent Mohamed Osman"
    assert links[0][1] == "Ben Salem Ali"
    assert links[0][2] == "spouse_of"


def test_leading_title_is_not_part_of_the_name():
    """Without a title anchor to consume it, "Mme" lands inside the capture and
    "Mme Sihem Temimi" then resolves as a different person from "Sihem Temimi"."""
    links = G.find_name_links("Mme Sihem Temimi épouse Ben Lamine Mohamed, et")
    assert links[0][0] == "Sihem Temimi"


def test_bare_surname_yields_no_tie():
    """"epouse Bouricha" names no identifiable second person. The claim is not
    lost -- it survives as person_married_name on the role event -- but it is
    not a tie between two nodes."""
    assert G.find_name_links("Mme Fékria Bouzguenda épouse Bouricha") == []


def test_pronoun_is_not_a_person():
    """"Son épouse Khadija" -- "son" is French for "his"."""
    assert G.find_name_links("Son épouse Khadija Staa Ali.") == []


def test_company_named_EP_is_not_a_marriage():
    """The bare EP marker is admitted only in the position after a person name.
    "Raison sociale : EP Technology Engineering" is a firm."""
    assert G.find_name_links("Raison sociale : EP Technology Engineering.") == []


def test_ocr_doubling_is_not_a_marriage_to_oneself():
    assert G.find_name_links("Ali Ben Salah épouse Ali Ben Salah") == []


def test_title_anchored_pattern_still_reports_its_marker():
    m = G.RE_PERSON.search("Mme Fékria Bouzguenda épouse Bouricha Salem")
    assert m.group("link") == "épouse"
    assert m.group("spouse") == "Bouricha Salem"


# --- tie construction ---------------------------------------------------- #

def _ev(relation="spouse_of", person="Ali Ben Salah", kin="Leila Trabelsi",
        org="Societe Alpha", date="2009-05-04", **kw):
    return {"event_type": relation, "event_id": kw.get("event_id", "E1"),
            "person_mention": person, "counterparty_mention": kin,
            "org_mention": org, "event_date": date,
            "date_precision": "day", "role_verbatim": "épouse",
            "block_uid": "B1", "issue_uid": "I1", "folio_page": "3",
            "evidence_quote": "q", "extract_confidence": "0.9", **kw}


def _idx(*rows):
    return {f"{r['person_mention']}||{r['org_mention']}": r for r in rows}


def _res(person, org, pid, status="resolved", label=None):
    return {"person_mention": person, "org_mention": org,
            "resolved_person_id": pid, "resolved_person_label": label or person,
            "link_status": status}


def test_both_ends_named_makes_a_tie():
    idx = _idx(_res("Ali Ben Salah", "Societe Alpha", "P_A"),
               _res("Leila Trabelsi", "Societe Alpha", "P_B"))
    obs, queue, stats = PT.observations([_ev()], idx)
    assert stats["both_ends_named"] == 1 and not queue
    assert (obs[0]["person_id"], obs[0]["kin_id"]) == ("P_A", "P_B")
    assert obs[0]["is_marriage"] == 1
    assert obs[0]["undirected_key"] == "P_A|P_B"


def test_one_end_named_is_queued_not_dropped():
    idx = _idx(_res("Ali Ben Salah", "Societe Alpha", "P_A"))
    obs, queue, stats = PT.observations([_ev()], idx)
    assert not obs and stats["one_end_named"] == 1
    assert queue[0]["failed_end"] == "kin"
    assert queue[0]["failed_mention"] == "Leila Trabelsi"


def test_neither_end_named_is_queued_not_dropped():
    obs, queue, stats = PT.observations([_ev()], {})
    assert not obs and stats["neither_end_named"] == 1
    assert queue[0]["queue_reason"] == "neither_end_named"


def test_unanchored_resolution_row_can_name_an_endpoint():
    """A marker in a property notice has no firm in the block. `resolve` still
    writes a row with an empty org, and the name-rarity tier can name it --
    which is the only route to a node for the majority of these."""
    idx = _idx(_res("Ali Ben Salah", "", "P_A", "inferred"),
               _res("Leila Trabelsi", "", "P_B", "inferred"))
    obs, _queue, stats = PT.observations([_ev(org="")], idx)
    assert stats["both_ends_named"] == 1
    assert obs[0]["person_status"] == "inferred"


def test_ambiguous_status_does_not_name_an_endpoint():
    idx = _idx(_res("Ali Ben Salah", "Societe Alpha", "P_A"),
               _res("Leila Trabelsi", "Societe Alpha", "P_B", "ambiguous"))
    obs, queue, _s = PT.observations([_ev()], idx)
    assert not obs and queue[0]["kin_status"] == "ambiguous"


def test_two_spellings_collapsing_to_one_node_is_not_a_self_tie():
    idx = _idx(_res("Ali Ben Salah", "Societe Alpha", "P_A"),
               _res("Ali Bensalah", "Societe Alpha", "P_A"))
    obs, queue, stats = PT.observations([_ev(kin="Ali Bensalah")], idx)
    assert not obs and not queue and stats["self_tie_dropped"] == 1


def test_maiden_link_is_not_counted_as_a_marriage():
    idx = _idx(_res("Ali Ben Salah", "Societe Alpha", "P_A"),
               _res("Leila Trabelsi", "Societe Alpha", "P_B"))
    obs, _q, _s = PT.observations([_ev(relation="maiden_name_of")], idx)
    assert obs[0]["is_marriage"] == 0
    assert obs[0]["obs_kind"] == "confirmation"


def test_widow_marker_closes_the_tie():
    idx = _idx(_res("Ali Ben Salah", "Societe Alpha", "P_A"),
               _res("Leila Trabelsi", "Societe Alpha", "P_B"))
    obs, _q, _s = PT.observations([_ev(relation="widow_of")], idx)
    assert obs[0]["obs_kind"] == "closing"
    assert obs[0]["is_marriage"] == 1
    spells, stats = PT.build_spells(obs)
    assert stats["ended"] == 1
    assert spells[0]["terminus"] == "2009-05-04"
    assert spells[0]["right_censored"] == "False"


def test_marriage_onset_is_always_left_censored():
    """The gazette does not publish weddings, so no onset is ever observed. A
    point onset here would make a duration analysis read filing frequency as
    marriage tenure."""
    idx = _idx(_res("Ali Ben Salah", "Societe Alpha", "P_A"),
               _res("Leila Trabelsi", "Societe Alpha", "P_B"))
    obs, _q, _s = PT.observations([_ev()], idx)
    spells, _stats = PT.build_spells(obs)
    assert spells[0]["onset"] == ""
    assert spells[0]["onset_hi"] == "2009-05-04"
    assert spells[0]["left_censored"] == "True"
    assert spells[0]["right_censored"] == "True"


def test_inferred_endpoint_gets_its_own_evidence_tier():
    idx = _idx(_res("Ali Ben Salah", "Societe Alpha", "P_A"),
               _res("Leila Trabelsi", "Societe Alpha", "P_B", "inferred"))
    obs, _q, _s = PT.observations([_ev()], idx)
    spells, stats = PT.build_spells(obs)
    assert stats["inferred_endpoint"] == 1
    assert spells[0]["evidence_tier"] == "kinship_inferred"
    assert spells[0]["needs_review"] is True


def test_repeated_observations_raise_confidence_and_keep_the_earliest_date():
    idx = _idx(_res("Ali Ben Salah", "Societe Alpha", "P_A"),
               _res("Leila Trabelsi", "Societe Alpha", "P_B"))
    obs, _q, _s = PT.observations(
        [_ev(event_id="E1", date="2010-01-01"),
         _ev(event_id="E2", date="2008-03-02")], idx)
    spells, stats = PT.build_spells(obs)
    assert stats["dyads"] == 1
    assert spells[0]["evidence_n"] == 2
    assert spells[0]["onset_hi"] == "2008-03-02"


def test_panel_starts_at_first_sighting_and_is_never_certain():
    idx = _idx(_res("Ali Ben Salah", "Societe Alpha", "P_A"),
               _res("Leila Trabelsi", "Societe Alpha", "P_B"))
    obs, _q, _s = PT.observations([_ev(date="2009-05-04")], idx)
    panel = PT.build_panel(PT.build_spells(obs)[0])
    years = {r["panel_id"] for r in panel}
    assert "yearly:2009" in years
    assert "yearly:2008" not in years
    assert {r["certainty"] for r in panel} == {"probable"}


def test_undated_spell_is_absent_from_the_panel():
    idx = _idx(_res("Ali Ben Salah", "Societe Alpha", "P_A"),
               _res("Leila Trabelsi", "Societe Alpha", "P_B"))
    obs, _q, _s = PT.observations([_ev(date="")], idx)
    spells, stats = PT.build_spells(obs)
    assert stats["undated"] == 1
    assert spells[0]["evidence_tier"] == "kinship_undated"
    assert PT.build_panel(spells) == []


# --- the guard that matters most downstream ------------------------------ #

def test_kinship_never_becomes_a_person_org_membership():
    """A kinship event carries the block's organisation as the resolver's
    anchor, not as a claim of office. `spells.py` falls back to
    role = "unspecified" for any resolved event with no role, so without the
    KINSHIP exclusion every spouse named in a company filing would become a
    member of it."""
    from elitenet import spells as S
    assert S.KINSHIP == {"spouse_of", "widow_of", "maiden_name_of"}
    for t in S.KINSHIP:
        assert t not in S.OPENING and t not in S.CLOSING
        assert t not in S.CONFIRMING and t not in S.ORG_CLOSING


def test_resolve_gives_both_kinship_ends_a_dyad():
    """Every other event type has one person and one organisation, so the
    counterparty column was only ever read as an organisation. Both ends of a
    kinship claim are people and both need a node id."""
    from elitenet import resolve as R
    kin = {"event_type": "spouse_of", "person_mention": "A Ben Ali",
           "counterparty_mention": "B Trabelsi"}
    assert R._persons_of(kin) == ["A Ben Ali", "B Trabelsi"]
    org_tie = {"event_type": "org_tie", "person_mention": "",
               "counterparty_mention": "Societe Beta"}
    assert R._persons_of(org_tie) == []
    role = {"event_type": "appointed", "person_mention": "A Ben Ali",
            "counterparty_mention": "Societe Beta"}
    assert R._persons_of(role) == ["A Ben Ali"]
