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
