"""Tests for the political-connection coding.

Most of these are regressions. Coding a firm as politically connected is a
claim about real organisations and real people, and every bug caught while
building this one made a *specific* false claim - a chief of staff read as a
prime minister, a retired official read as a ministry, a former central-bank
deputy read as the sitting governor. Each is pinned here by the title that
produced it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bourse.political_connections import (
    FACCIO_THRESHOLD, Rules, load_rules, norm, to_panel,
)


@pytest.fixture(scope="module")
def rules() -> Rules:
    """The real shipped rules: these tests guard the config, not a mock."""
    return load_rules()


class TestNormalisation:
    def test_accents_are_stripped(self):
        assert norm("Ministère") == "ministere"

    @pytest.mark.parametrize("dash", ["-", "‐", "‑", "–", "—", "―", "−"])
    def test_every_dash_folds_to_hyphen(self, dash):
        # "Ex - vice–Gouverneur" was read as a *serving* governor because the
        # en dash the typesetter used was not in the pattern's separator class.
        assert norm(f"vice{dash}Gouverneur") == "vice-gouverneur"

    def test_whitespace_collapses(self):
        assert norm("  Chef   de\ncabinet ") == "chef de cabinet"


class TestOfficeTitles:
    """One case per office, plus the traps."""

    @pytest.mark.parametrize("title,category,tenure", [
        ("Ex-ministre de l'industrie et de la technologie", "minister", "former"),
        ("Ex-Ministre des Finances par intérim", "minister", "former"),
        ("Secrétaire d'Etat aux affaires étrangères", "secretary_of_state", "current"),
        ("Fonctionnaire au Ministère des Finances", "civil_servant", "current"),
        ("Administrateur, représentant l'Etat", "state_representative", "current"),
        ("MINISTERE DES FINANCES Membre M. X", "ministry_organ", "current"),
        ("BANQUE CENTRALE DE TUNISIE Membre M. X", "central_bank", "current"),
    ])
    def test_office_is_read_from_the_title(self, rules, title, category, tenure):
        assert rules.office_match(title) == (category, tenure)

    def test_administrateur_is_not_a_minister(self, rules):
        # "adMINISTrateur" contains the letters of "ministre". Without word
        # boundaries every director in the corpus is flagged.
        assert rules.office_match("Administrateur") is None
        assert rules.office_match("Administrateur indépendant") is None

    def test_chief_of_staff_is_not_the_minister(self, rules):
        # "Chef de cabinet du Premier Ministre" contains "Ministre" and was
        # coded as a sitting prime minister until the staff rule was moved
        # ahead of the bare minister rule.
        assert rules.office_match("Chef de cabinet du Premier Ministre") \
            == ("cabinet_staff", "current")

    def test_adviser_to_a_minister_is_not_the_minister(self, rules):
        assert rules.office_match(
            "Maitre assistant Habilité et Conseillé du ministre de l'enseignement supérieur"
        ) == ("ministerial_adviser", "current")

    def test_retired_official_is_not_the_ministry(self, rules):
        # Coded `ministry_organ` - the ministry itself holding the seat -
        # until a former-civil-servant rule was added ahead of it.
        assert rules.office_match(
            "Retraité, ancien cadre au Ministère de l'Économie et des Finances"
        ) == ("civil_servant", "former")

    def test_former_beats_current_in_a_mixed_title(self, rules):
        # "Ex - vice-Gouverneur de la BCT, ex-SEAE et ex-ministre du commerce"
        # names three offices, all former. Reading it as a sitting minister is
        # the more consequential error, so `former` wins.
        cat, tenure = rules.office_match(
            "Ex - vice–Gouverneur de la BCT, ex-SEAE4 et ex-ministre du com- merce")
        assert tenure == "former"

    def test_an_ordinary_title_is_not_an_office(self, rules):
        for title in ["Président Directeur Général", "Administrateur indépendant",
                      "Directeur Général Adjoint", "Membre du Comité d'audit", ""]:
            assert rules.office_match(title) is None, title


class TestStateOwnedBanks:
    @pytest.mark.parametrize("name", [
        "STB", "STB BANK", "Société Tunisienne de Banque", "BNA",
        "Banque Nationale Agricole", "BH", "BH BANK", "Banque de l'Habitat",
    ])
    def test_the_three_public_banks_are_recognised(self, rules, name):
        assert rules.is_state_owned(name) == "public_bank"

    @pytest.mark.parametrize("name", [
        "STB SICAR", "STB INVEST", "BNA CAPITAUX", "BH LEASING",
        "STB SECURITE ET GARDIENNAGE",
    ])
    def test_subsidiaries_are_excluded_by_default(self, rules, name):
        # A stake in a bank's leasing arm is not a credit relationship with
        # the bank. Widening this is the analyst's call, made in the config.
        assert rules.is_state_owned(name) is None

    @pytest.mark.parametrize("name", ["BIAT", "AMEN BANK", "UBCI", "ATTIJARI BANK"])
    def test_private_banks_are_not_flagged(self, rules, name):
        assert rules.is_state_owned(name) is None


class TestPoliticalFigureRoster:
    def test_the_shipped_roster_is_empty(self, rules):
        # Deliberate: a name here asserts that a real, often living person was
        # tied to an authoritarian regime, which needs a citable source per
        # row. If this fails, someone populated it - check their sources.
        assert rules.figures == {}

    def test_matching_works_when_a_roster_is_supplied(self):
        r = Rules([{"rule_kind": "political_figure", "pattern": "Leila Ben Ali",
                    "category": "ben_ali_family", "tenure": "",
                    "source": "JORT decree"}])
        assert r.figure_match("Leila Ben Ali")["category"] == "ben_ali_family"

    def test_roster_matching_is_order_insensitive(self):
        # Filings print "BEN ALI Leila" and "Leila Ben Ali" interchangeably.
        r = Rules([{"rule_kind": "political_figure", "pattern": "Leila Ben Ali",
                    "category": "ben_ali_family", "tenure": "", "source": "x"}])
        assert r.figure_match("BEN ALI Leila") is not None

    def test_an_unlisted_person_is_not_matched(self):
        r = Rules([{"rule_kind": "political_figure", "pattern": "Leila Ben Ali",
                    "category": "ben_ali_family", "tenure": "", "source": "x"}])
        assert r.figure_match("Hakim DOGHRI") is None


def _ev(**kw):
    base = {"entity_id": "F1", "canonical_name": "ACME", "year": "2010",
            "channel": "state_ownership", "category": "state_shareholder",
            "tenure": "", "stake_pct": "", "from_ocr": "0"}
    return {**base, **kw}


class TestPanel:
    def test_faccio_threshold_gates_the_narrow_flag(self):
        below = to_panel([_ev(stake_pct=str(FACCIO_THRESHOLD - 0.1))])[0]
        at = to_panel([_ev(stake_pct=str(FACCIO_THRESHOLD))])[0]
        assert below["pc_narrow"] == 0
        assert at["pc_narrow"] == 1
        # Both are still state ownership, and so still broadly connected.
        assert below["pc_state_ownership"] == at["pc_state_ownership"] == 1
        assert below["pc_broad"] == 1

    def test_a_state_stake_of_unstated_size_is_not_narrow(self):
        row = to_panel([_ev(stake_pct="")])[0]
        assert row["pc_state_ownership"] == 1 and row["pc_narrow"] == 0

    def test_a_sitting_officeholder_is_narrow(self):
        row = to_panel([_ev(channel="officeholder", category="minister",
                            tenure="current")])[0]
        assert row["pc_narrow"] == 1

    def test_a_former_officeholder_alone_is_not_narrow(self):
        row = to_panel([_ev(channel="officeholder", category="minister",
                            tenure="former")])[0]
        assert row["pc_officeholder"] == 1
        assert row["pc_officeholder_former"] == 1
        assert row["pc_narrow"] == 0

    def test_a_public_bank_tie_alone_is_not_narrow(self):
        # The filings show governance, not lending, so this stays out of the
        # strict definition however strong the tie looks.
        row = to_panel([_ev(channel="public_bank", category="public_bank_equity")])[0]
        assert row["pc_public_bank"] == 1
        assert row["pc_public_bank_equity"] == 1
        assert row["pc_narrow"] == 0
        assert row["pc_broad"] == 1

    def test_an_interlock_does_not_set_the_equity_flag(self):
        row = to_panel([_ev(channel="public_bank", category="public_bank_interlock")])[0]
        assert row["pc_public_bank"] == 1 and row["pc_public_bank_equity"] == 0

    def test_the_largest_state_stake_in_a_year_is_kept(self):
        rows = to_panel([_ev(stake_pct="12"), _ev(stake_pct="41.5"), _ev(stake_pct="7")])
        assert rows[0]["max_state_stake_pct"] == "41.5"

    def test_evidence_is_counted_and_ocr_tracked(self):
        rows = to_panel([_ev(), _ev(from_ocr="1"), _ev(from_ocr="1")])
        assert rows[0]["n_evidence"] == 3
        assert rows[0]["n_evidence_ocr"] == 2

    def test_firm_years_are_separate_rows(self):
        rows = to_panel([_ev(year="2010"), _ev(year="2011")])
        assert len(rows) == 2

    def test_a_firm_with_no_evidence_produces_no_row(self):
        # The panel holds only coded firms; a zero elsewhere means "not seen",
        # not "not connected", which is why absence is never written as a 0.
        assert to_panel([]) == []
