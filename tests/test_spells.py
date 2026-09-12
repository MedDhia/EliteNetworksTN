"""Tests for spell closure, and especially for inferred displacement.

The gazette publishes entries reliably and exits rarely, so most of what the
spell layer knows about departure is inferred.  The inference that carries the
most weight -- appointing someone to a singular office means the incumbent has
gone -- is also the one that does damage when it fires on an office that is
not in fact singular, so its guards are pinned down here.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eltn.panel import build_spells, normalise_events  # noqa: E402


def _event(person, position, org, date, *, event_type="appointment",
           issue="journal-officiel/fr/2000/001", act_seq=1, authority="",
           replaces="", org_source_text=True):
    """One raw extractor row, as `normalise_events` expects to receive it."""
    return {
        "issue_key": issue,
        "year": int(date[:4]),
        "issue": issue.rsplit("/", 1)[-1],
        "page": 1,
        "act_seq": act_seq,
        "act_kind": "decret",
        "act_qualifier": "",
        "act_number": "",
        "act_date": date,
        "authority_raw": authority or org,
        "section_raw": "",
        "signatory_office": "",
        "signatory_name": "",
        "proposer_raw": "",
        "pdf_url": "",
        "event_type": event_type,
        "person_raw": person,
        "honorific": "Monsieur",
        "source_layer": "dispositif",
        "cited_act_number": "",
        "cited_act_date": "",
        "grade_raw": "",
        "position_raw": position,
        "org_raw": org if org_source_text else "",
        "board_body_raw": "",
        "replaces_raw": replaces,
        "delegator_raw": "",
        "effect_date": date,
        "sentence": "",
    }


def spells_from(rows, **kw):
    return build_spells(normalise_events(pd.DataFrame(rows)), **kw)


def closure(sp, person_name_fragment, ev):
    """The end_reason of the spell belonging to a given person."""
    pid = ev[ev.person_raw.str.contains(person_name_fragment)].person_id.iloc[0]
    row = sp[sp.person_id == pid]
    return row.end_reason.iloc[0] if len(row) else None


# --- the core inference -----------------------------------------------------

SINGULAR = [
    # (position, organisation) pairs that name one post
    ("directeur des affaires administratives", "ministère de la santé"),
    ("secrétaire général", "ministère de la santé"),
    ("président directeur général", "société tunisienne de l'électricité"),
    ("directeur général", "agence foncière d'habitation"),
]


@pytest.mark.parametrize("position,org", SINGULAR)
def test_appointing_a_successor_evicts_the_incumbent(position, org):
    rows = [
        _event("Ahmed Alpha", position, org, "2000-01-10"),
        _event("Bechir Beta", position, org, "2004-06-15",
               issue="journal-officiel/fr/2004/050"),
    ]
    ev = normalise_events(pd.DataFrame(rows))
    sp = build_spells(ev)
    assert closure(sp, "Alpha", ev) == "displaced"
    alpha = sp[sp.end_reason == "displaced"].iloc[0]
    assert alpha.end_date == dt.date(2004, 6, 15)
    assert alpha.end_precision == "upper_bound"
    # and the successor is left open
    assert closure(sp, "Beta", ev) == "censored"


def test_displacement_can_be_switched_off():
    rows = [
        _event("Ahmed Alpha", "directeur des affaires administratives",
               "ministère de la santé", "2000-01-10"),
        _event("Bechir Beta", "directeur des affaires administratives",
               "ministère de la santé", "2004-06-15",
               issue="journal-officiel/fr/2004/050"),
    ]
    ev = normalise_events(pd.DataFrame(rows))
    sp = build_spells(ev, infer_displacement=False)
    assert closure(sp, "Alpha", ev) == "censored"
    assert "displaced" not in set(sp.end_reason)


def test_an_explicit_successor_beats_the_inference():
    """"en remplacement de" is stated, so the closure is exact, not inferred."""
    rows = [
        _event("Ahmed Alpha", "directeur général", "agence foncière d'habitation",
               "2000-01-10"),
        _event("Bechir Beta", "directeur général", "agence foncière d'habitation",
               "2004-06-15", issue="journal-officiel/fr/2004/050",
               replaces="Ahmed Alpha"),
    ]
    ev = normalise_events(pd.DataFrame(rows))
    sp = build_spells(ev)
    assert closure(sp, "Alpha", ev) == "succeeded"
    assert sp[sp.end_reason == "succeeded"].iloc[0].end_precision == "exact"


# --- the guards -------------------------------------------------------------


def test_board_seats_are_never_displaced():
    """A conseil d'administration seats many people at once."""
    rows = [
        _event("Ahmed Alpha", "administrateur représentant l'Etat",
               "banque de l'habitat", "2000-01-10", event_type="board"),
        _event("Bechir Beta", "administrateur représentant l'Etat",
               "banque de l'habitat", "2004-06-15", event_type="board",
               issue="journal-officiel/fr/2004/050"),
    ]
    ev = normalise_events(pd.DataFrame(rows))
    sp = build_spells(ev)
    assert closure(sp, "Alpha", ev) == "censored"


def test_a_bare_rank_inside_a_ministry_is_not_a_post():
    """A ministry has many "chefs de service" at once; the title names no unit."""
    rows = [
        _event("Ahmed Alpha", "chef de service", "ministère de l'agriculture",
               "2000-01-10"),
        _event("Bechir Beta", "chef de service", "ministère de l'agriculture",
               "2004-06-15", issue="journal-officiel/fr/2004/050"),
    ]
    ev = normalise_events(pd.DataFrame(rows))
    sp = build_spells(ev)
    assert closure(sp, "Alpha", ev) == "censored"


def test_a_named_unit_inside_a_ministry_is_a_post():
    """The same rank, once it says which service, is singular again."""
    rows = [
        _event("Ahmed Alpha", "chef de service du budget",
               "ministère de l'agriculture", "2000-01-10"),
        _event("Bechir Beta", "chef de service du budget",
               "ministère de l'agriculture", "2004-06-15",
               issue="journal-officiel/fr/2004/050"),
    ]
    ev = normalise_events(pd.DataFrame(rows))
    sp = build_spells(ev)
    assert closure(sp, "Alpha", ev) == "displaced"


def test_an_office_one_act_fills_twice_is_treated_as_collegial():
    """Two people, one act, one office: the post is plural or the id collided."""
    rows = [
        _event("Ahmed Alpha", "membre du comité", "instance nationale",
               "2000-01-10", act_seq=7),
        _event("Bechir Beta", "membre du comité", "instance nationale",
               "2000-01-10", act_seq=7),
        _event("Chedli Gamma", "membre du comité", "instance nationale",
               "2008-03-01", issue="journal-officiel/fr/2008/020"),
    ]
    ev = normalise_events(pd.DataFrame(rows))
    sp = build_spells(ev)
    assert set(sp.end_reason) == {"censored"}


def test_two_entries_on_one_day_do_not_make_a_zero_day_tenure():
    """Same day, different acts: a merged id, not an instant handover."""
    rows = [
        _event("Ahmed Alpha", "directeur des affaires administratives",
               "ministère de la santé", "2000-01-10", act_seq=1),
        _event("Bechir Beta", "directeur des affaires administratives",
               "ministère de la santé", "2000-01-10", act_seq=2),
    ]
    ev = normalise_events(pd.DataFrame(rows))
    sp = build_spells(ev)
    assert "displaced" not in set(sp.end_reason)
    assert (sp.duration_days > 0).all()


def test_a_position_with_no_organisation_is_not_a_post():
    """"Cheikhs" with no body attached is one office for the whole country."""
    rows = [
        _event("Ahmed Alpha", "cheikh", "", "2000-01-10",
               authority="", org_source_text=False),
        _event("Bechir Beta", "cheikh", "", "2004-06-15",
               authority="", org_source_text=False,
               issue="journal-officiel/fr/2004/050"),
    ]
    ev = normalise_events(pd.DataFrame(rows))
    sp = build_spells(ev)
    assert "displaced" not in set(sp.end_reason)


# --- ordering ---------------------------------------------------------------


def test_a_chain_of_holders_closes_each_in_turn():
    org, position = "agence foncière d'habitation", "directeur général"
    rows = [
        _event(n, position, org, d, issue=f"journal-officiel/fr/{d[:4]}/001")
        for n, d in [("Ahmed Alpha", "1990-01-01"),
                     ("Bechir Beta", "1995-01-01"),
                     ("Chedli Gamma", "2001-01-01")]
    ]
    ev = normalise_events(pd.DataFrame(rows))
    sp = build_spells(ev).sort_values("start_date")
    assert list(sp.end_reason) == ["displaced", "displaced", "censored"]
    assert list(sp.end_date)[:2] == [dt.date(1995, 1, 1), dt.date(2001, 1, 1)]
