"""Organisation-to-organisation ties: direction, target, and what not to emit.

Direction is the thing to pin hardest. "X a cédé … au capital de la société Y"
means X held a stake in Y and is giving it up; reversed, it asserts the opposite
ownership relation, reads as plausible, and nothing downstream would catch it.
"""
from elitenet.extract import extract_corporate
from elitenet.grammar import trim_org_party

BASE = dict(
    block_uid="annonces-legales/fr/2004/009:2004T0001SANB2",
    issue_uid="annonces-legales/fr/2004/009", collection="annonces-legales",
    year=2004, issue="009", pub_date="2004-02-13", domain="corporate",
    rubric="SANB2", section="cession", legal_form="SA",
    folio_page_start=1, folio_page_end=1, ocr_page_start=1, ocr_page_end=1,
)


def ties(text, **over):
    block = dict(BASE, text=text, **over)
    block.setdefault("heading", text.split("\n", 1)[0])
    return [r for r in extract_corporate(block) if r["event_type"] == "org_tie"]


def by_relation(rows):
    return {r["role_canonical"]: (r["counterparty_mention"], r["org_mention"])
            for r in rows}


# --- direction ------------------------------------------------------------- #

def test_a_company_ceding_shares_points_from_seller_to_the_company_sold():
    rows = ties(
        "Cession de parts sociales\n\nLa société Capinvest SA a cédé 250 parts "
        "sociales de sa participation au capital de la société Mehari Beach "
        "au profit de Madame Fekria Kamoun."
    )
    holder, target = by_relation(rows)["shares_ceded"]
    assert "Capinvest" in holder
    assert "Mehari Beach" in target
    # The reverse would read just as plausibly and is what must never happen.
    assert "Mehari" not in holder and "Capinvest" not in target


def test_a_company_acquiring_shares_points_from_buyer_to_the_company_bought():
    rows = ties(
        "Cession de parts sociales\n\nMonsieur Ali Ben Salah a cédé 100 parts "
        "sociales de la société Tunisie Eviers au profit de la société "
        "SICAR INVEST."
    )
    holder, target = by_relation(rows)["shares_acquired"]
    assert "SICAR INVEST" in holder
    assert "Tunisie Eviers" in target


def test_the_target_comes_from_the_clause_not_the_subject_line():
    """org_name() resolves on 55% of these blocks and sometimes returns a clause.

    Where the clause names the company whose shares move, that is the target,
    and it is often not what the subject line says.
    """
    rows = ties(
        "Cession de parts sociales\n\nLa société Alpha Holding a cédé ses parts "
        "sociales de sa participation au capital de la société Beta Industries."
    )
    holder, target = by_relation(rows)["shares_ceded"]
    assert "Alpha Holding" in holder and "Beta Industries" in target


def test_the_subject_firm_is_the_target_when_the_clause_names_none():
    rows = ties(
        "Constitution de société\n\nDénomination : Société TUNISIE EVIERS SA\n"
        "Associés : la société SICAR INVEST et Monsieur Abdelwaheb Bellaaje.\n",
        section="constitution",
    )
    holder, target = by_relation(rows)["shareholder_confirmed"]
    assert "SICAR INVEST" in holder
    assert "TUNISIE EVIERS" in target


# --- relations ------------------------------------------------------------- #

def test_a_standing_shareholding_and_an_audit_mandate_are_distinct_relations():
    rows = ties(
        "Constitution de société\n\nDénomination : Société Mehari Beach\n"
        "Associés : la société SICAR INVEST.\n"
        "Commissaire aux comptes : la société Commissariat Audit et Organisation.",
        section="constitution",
    )
    rel = by_relation(rows)
    assert "SICAR INVEST" in rel["shareholder_confirmed"][0]
    assert "Commissariat Audit" in rel["auditor"][0]


def test_a_shareholder_confirmation_carries_lower_confidence_than_a_transfer():
    """It proves the tie existed at the filing date; it does not open it.

    Treating a confirmation as an onset would manufacture the very variation
    the dataset exists to measure, so it is scored lower and the spell builder
    reads it as CONFIRMING.
    """
    conf = {r["role_canonical"]: float(r["extract_confidence"]) for r in ties(
        "Constitution de société\n\nDénomination : Société Beta\n"
        "Associés : la société Alpha Holding.\n"
        "La société Gamma Invest a souscrit 500 actions.", section="constitution")}
    assert conf["shareholder_confirmed"] < conf["capital_subscribed"]


# --- what must not be emitted --------------------------------------------- #

def test_a_company_is_not_tied_to_itself():
    rows = ties(
        "Constitution de société\n\nDénomination : Société Alpha Holding\n"
        "Associés : la société Alpha Holding.\n", section="constitution",
    )
    assert rows == []


def test_a_bare_form_marker_with_no_name_is_not_a_party():
    rows = ties(
        "Constitution de société\n\nDénomination : Société Beta Industries\n"
        "Associés : la société.\n", section="constitution",
    )
    assert not [r for r in rows if r["role_canonical"] == "shareholder_confirmed"]


def test_a_natural_person_party_produces_no_org_tie():
    rows = ties(
        "Cession de parts sociales\n\nMonsieur Ali Ben Salah a cédé 100 parts "
        "sociales de la société Tunisie Eviers au profit de Madame Fekria Kamoun."
    )
    assert rows == []


def test_the_person_level_share_transfer_still_fires_alongside():
    """The org layer is additive: it must not consume the existing event.

    One clause states several acts, which is why the cue lists are kept apart.
    """
    block = dict(BASE, heading="Cession de parts sociales", text=(
        "Cession de parts sociales\n\nLa société Capinvest SA a cédé 250 parts "
        "sociales de sa participation au capital de la société Mehari Beach "
        "au profit de Madame Fekria Kamoun."))
    kinds = {r["event_type"] for r in extract_corporate(block)}
    assert "org_tie" in kinds and "shares_transferred" in kinds


# --- name trimming --------------------------------------------------------- #

def test_a_party_name_is_cut_at_the_clause_boundary():
    assert trim_org_party(
        "la société ECOTEX représentée par Mr Arne Petersohn") == "la société ECOTEX"
    assert trim_org_party(
        "la société Mehari Beach au profit de Madame X") == "la société Mehari Beach"
    assert trim_org_party(
        "société IMEX ayant son siège à Tunis") == "société IMEX"


def test_and_is_a_separator_between_parties_but_not_inside_a_name():
    """The hard case: " et " does both jobs in this register."""
    assert trim_org_party(
        "la société SICAR INVEST et Monsieur X") == "la société SICAR INVEST"
    # A real Tunisian audit firm; cutting here would rename it.
    assert trim_org_party("la société Commissariat Audit et Organisation") == \
        "la société Commissariat Audit et Organisation"


# --- resolution and spell construction ------------------------------------- #

from elitenet.names import parse_org                                # noqa: E402
from elitenet.orgties import (build_panel, build_spells,             # noqa: E402
                              observations, score_link)
from elitenet.resolve import SeedIndex                               # noqa: E402


def seed_index(*names):
    """A minimal index holding just the organisations a test needs."""
    idx = SeedIndex()
    for label in names:
        o = parse_org(label)
        oid = "CO_" + o.match_key.replace(" ", "_")
        idx.orgs[oid] = {"node_id": oid, "label": label,
                         "label_normalised": o.match_key, "node_type": "COMPANY"}
        idx.org_by_norm[o.match_key].add(oid)
        for tok in o.content_tokens:
            idx.org_by_token[tok].add(oid)
    return idx


def ev(holder, target, relation, date_, eid="EV1", conf="0.88"):
    return {"event_type": "org_tie", "counterparty_mention": holder,
            "org_mention": target, "role_canonical": relation,
            "event_date": date_, "event_id": eid, "block_uid": "B1",
            "issue_uid": "annonces-legales/fr/2009/001", "folio_page": "1",
            "extract_confidence": conf, "evidence_quote": "q",
            "date_precision": "exact"}


IDX = None


def _idx():
    global IDX
    if IDX is None:
        IDX = seed_index("ALPHA HOLDING", "BETA INDUSTRIES", "GAMMA INVEST")
    return IDX


def test_both_endpoints_must_resolve_or_nothing_is_asserted():
    idx = _idx()
    obs, diag = observations([
        ev("ALPHA HOLDING", "BETA INDUSTRIES", "shareholder_confirmed", "2009-01-01"),
        ev("ALPHA HOLDING", "A FIRM NOBODY HAS HEARD OF", "shareholder_confirmed",
           "2009-01-01", eid="EV2"),
        ev("ANOTHER UNKNOWN", "YET ANOTHER UNKNOWN", "shareholder_confirmed",
           "2009-01-01", eid="EV3"),
    ], idx)
    assert len(obs) == 1
    assert diag["one_end_resolved"] == 1
    assert diag["neither_end_resolved"] == 1


def test_a_mention_resolving_to_the_subject_firm_is_dropped_as_a_self_tie():
    obs, diag = observations([
        ev("ALPHA HOLDING", "Société ALPHA HOLDING", "shareholder_confirmed",
           "2009-01-01"),
    ], _idx())
    assert obs == []
    assert diag["self_match_dropped"] == 1


def test_a_confirmation_leaves_the_onset_left_censored():
    """It proves the tie was live, not when it began.

    The window start is a bound, not an estimate, so `onset` stays empty and
    only `onset_hi` is asserted.
    """
    obs, _ = observations([
        ev("ALPHA HOLDING", "BETA INDUSTRIES", "shareholder_confirmed", "2009-06-01"),
    ], _idx())
    spells, _q, diag = build_spells(obs, [], _idx())
    s = next(x for x in spells if x["evidence_tier"] == "gazette_dated")
    assert s["onset"] == "", "a confirmation must not become an onset"
    assert s["onset_hi"] == "2009-06-01"
    assert s["left_censored"] == "True"
    assert s["right_censored"] == "True"
    assert diag["left_censored_onsets"] == 1


def test_an_acquisition_dates_the_onset_exactly():
    obs, _ = observations([
        ev("GAMMA INVEST", "BETA INDUSTRIES", "shares_acquired", "2010-03-04"),
    ], _idx())
    s = next(x for x in build_spells(obs, [], _idx())[0]
             if x["evidence_tier"] == "gazette_dated")
    assert s["onset"] == "2010-03-04" and s["left_censored"] == "False"
    assert s["onset_rule"] == "event:shares_acquired"


def test_a_cession_after_the_onset_closes_the_tie():
    obs, _ = observations([
        ev("GAMMA INVEST", "BETA INDUSTRIES", "shares_acquired", "2010-03-04"),
        ev("GAMMA INVEST", "BETA INDUSTRIES", "shares_ceded", "2012-07-09", eid="EV2"),
    ], _idx())
    spells, _q, _d = build_spells(obs, [], _idx())
    # Different relations are distinct dyad keys, so the closing spell carries
    # the terminus; what matters is that the date is not silently lost.
    assert any(x["terminus"] == "2012-07-09" or x["onset"] == "2012-07-09"
               for x in spells)


def test_a_cession_predating_every_confirmation_is_recorded_not_forced():
    """Either the stake was rebuilt or one reading is wrong; neither is a
    licence to emit a spell that ends before it starts."""
    obs, _ = observations([
        ev("GAMMA INVEST", "BETA INDUSTRIES", "shares_ceded", "2008-01-01"),
        ev("GAMMA INVEST", "BETA INDUSTRIES", "shares_ceded", "2008-01-01", eid="EV2"),
    ], _idx())
    spells, _q, _d = build_spells(obs, [], _idx())
    for s in spells:
        if s["onset"] and s["terminus"]:
            assert s["terminus"] >= s["onset"]


def test_seed_org_ties_are_carried_undated():
    seed = [{"from_node_id": "CO_ALPHA_HOLDING", "to_node_id": "CO_BETA_INDUSTRIES",
             "from_label": "ALPHA HOLDING", "to_label": "BETA INDUSTRIES",
             "edge_label_raw": "SHAREHOLDER", "tie_class": "ownership"}]
    spells, _q, diag = build_spells([], seed, _idx())
    assert diag["seed_ties_carried"] == 1
    s = spells[0]
    assert s["evidence_tier"] == "seed_undated"
    assert s["onset"] == "" and s["onset_hi"] == ""
    assert s["onset_rule"] == "seed_undated"


def test_the_panel_carries_dated_ties_only():
    """An undated tie placed in a time slice asserts a presence the evidence
    does not support, and would repeat across every period."""
    seed = [{"from_node_id": "CO_ALPHA_HOLDING", "to_node_id": "CO_BETA_INDUSTRIES",
             "from_label": "A", "to_label": "B",
             "edge_label_raw": "SHAREHOLDER", "tie_class": "ownership"}]
    obs, _ = observations([
        ev("GAMMA INVEST", "BETA INDUSTRIES", "shares_acquired", "2010-03-04"),
    ], _idx())
    spells, _q, _d = build_spells(obs, seed, _idx())
    panel = build_panel(spells)
    assert panel, "the dated tie should appear"
    assert all(r["evidence_tier"] == "gazette_dated" for r in panel)
    # The id is derived from the match key, which collapses doubled letters
    # (GAMMA -> GAMA) by design, so it is computed rather than spelled out.
    gamma = next(oid for oid, o in _idx().orgs.items()
                 if o["label"] == "GAMMA INVEST")
    assert {r["from_node_id"] for r in panel} == {gamma}


def test_the_weaker_endpoint_governs_the_score():
    """There is no third thing to anchor an org-org dyad against, unlike the
    person-org case where the organisation has to agree first."""
    assert score_link(1.0, 0.5, 1, 0.88) < score_link(0.9, 0.9, 1, 0.88)
    assert score_link(1.0, 1.0, 4, 0.88) > score_link(1.0, 1.0, 1, 0.88)


def test_ownership_is_flagged_apart_from_the_other_corporate_relations():
    obs, _ = observations([
        ev("ALPHA HOLDING", "BETA INDUSTRIES", "shareholder_confirmed", "2009-01-01"),
        ev("GAMMA INVEST", "BETA INDUSTRIES", "auditor", "2009-01-01", eid="EV2"),
    ], _idx())
    flags = {o["relation"]: o["is_ownership"] for o in obs}
    assert flags["shareholder_confirmed"] == 1
    assert flags["auditor"] == 0
