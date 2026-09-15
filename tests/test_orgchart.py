"""Tests for the organisation-chart reconstruction.

Stdlib and pandas only: ``scripts/orgchart.py`` imports no drawing library,
and matplotlib is not a project dependency.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from orgchart import (  # noqa: E402
    MAX_NAME, chain, clean, fold, modal_parent, represented_body, resolve,
    split_parent, wellformed,
)


class TestRepresentedBody:
    """Board seats: who a ministry-appointed director sits for.

    This is the co-governance relation, and it is not the tree. A public
    enterprise can carry representatives of ten ministries at once and is a
    directorate of none of them.
    """

    def test_a_seat_held_for_a_ministry(self):
        assert represented_body(
            "membre représentant le ministère de l'agriculture"
        ) == "ministère de l'agriculture"

    def test_feminine_and_plural_forms(self):
        assert represented_body("représentante du ministère de la santé") == \
            "ministère de la santé"
        assert represented_body("membres représentants le ministère du plan") == \
            "ministère du plan"

    def test_a_seat_held_for_the_state_carries_no_edge(self):
        # "administrateur représentant l'État" is a seat for the state at
        # large, not for any ministry — 1,536 of the 3,023 representation
        # appointments in the register are these.
        assert represented_body("administrateur représentant l'Etat") is None
        assert represented_body("Administrateur représentant l'État") is None

    def test_an_ordinary_post_is_not_a_seat(self):
        assert represented_body("directeur général") is None
        assert represented_body("") is None
        assert represented_body(None) is None

    def test_bare_representant_with_nothing_after_it(self):
        assert represented_body("représentant") is None


class TestClean:
    def test_strips_act_boilerplate(self):
        assert clean("ministère de la santé; Vu l'avis du ministre") == \
            "ministère de la santé"

    def test_strips_an_appointee_roster(self):
        # Where an act appoints a committee the whole membership list can land
        # in the name field, and every "représentant du ministère de X" in it
        # then reads as an attachment.
        raw = ("ministère de l'industrie, - Monsieur Mustapha Bahloul : "
               "représentant du ministère des finances, - Madame Nour")
        assert clean(raw) == "ministère de l'industrie"

    def test_strips_a_president_membre_roster(self):
        raw = "ministère des domaines de l'Etat : président, - Nooman Majdoub"
        assert clean(raw) == "ministère des domaines de l'Etat"

    def test_leaves_an_ordinary_name_alone(self):
        n = "direction générale des impôts"
        assert clean(n) == n

    def test_handles_empty(self):
        assert clean("") == ""
        assert clean(None) == ""


class TestWellformed:
    def test_a_normal_name_is_wellformed(self):
        assert wellformed("direction générale des impôts")

    def test_an_uncut_act_is_not(self):
        assert not wellformed("ministère de l'industrie " + "x" * MAX_NAME)

    def test_empty_is_not(self):
        assert not wellformed("")


class TestSplitParent:
    def test_au_ministere(self):
        child, parent = split_parent(
            "direction générale des services communs au ministère de l'équipement")
        assert child == "direction générale des services communs"
        assert parent == "ministère de l'équipement"

    def test_relevant_de_la(self):
        child, parent = split_parent(
            "contrôle d'Etat relevant de la Présidence du gouvernement")
        assert child == "contrôle d'Etat"
        assert parent == "Présidence du gouvernement"

    def test_relevant_du_ministere(self):
        _, parent = split_parent(
            "agence de la vulgarisation relevant du ministère de l'agriculture")
        assert parent == "ministère de l'agriculture"

    def test_immediate_parent_not_the_topmost(self):
        # The caller walks further; this returns one step.
        _, parent = split_parent(
            "secrétariat général au commissariat régional de l'éducation à Tunis 1")
        assert parent == "commissariat régional de l'éducation à Tunis 1"

    def test_des_is_not_an_attachment(self):
        # The guard that keeps ordinary French from becoming a hierarchy.
        assert split_parent("direction générale des impôts")[1] is None

    def test_de_la_is_not_an_attachment(self):
        assert split_parent("direction de la santé militaire")[1] is None

    def test_a_place_name_is_not_a_parent(self):
        assert split_parent("tribunal de première instance de Djerba")[1] is None
        assert split_parent("commune de El Ksar")[1] is None

    def test_a_judicial_post_is_not_a_containment(self):
        # "Cour d'Appel de Sfax, Conseiller à la Cour de Cassation" is a judge
        # at Sfax appointed counsellor to the Cassation court. Neither court
        # contains the other, and read as containment the register makes each
        # the other's parent.
        assert split_parent(
            "Cour d'Appel de Sfax, Conseiller à la Cour de Cassation")[1] is None
        assert split_parent(
            "Cour de Cassation, Président de Chambre à la Cour d'Appel de Tunis"
        )[1] is None
        assert split_parent(
            "Tribunal de Première Instance de Tunis, Juge au Tribunal Immobilier"
        )[1] is None

    def test_a_real_attachment_with_a_comma_still_splits(self):
        # The guard must not swallow ordinary names that happen to carry a
        # comma before the separator.
        _, parent = split_parent(
            "direction générale des services communs, des affaires "
            "financières au ministère de l'équipement")
        assert parent == "ministère de l'équipement"

    def test_a_body_is_not_its_own_parent(self):
        assert split_parent("ministère au ministère")[1] is None

    def test_an_uncut_act_yields_no_edge(self):
        raw = ("ministère de l'industrie, - Monsieur X : représentant du "
               "ministère des finances, ") + "y" * MAX_NAME
        assert split_parent(raw)[1] is None


class TestChain:
    def test_single_step(self):
        assert chain("direction X au ministère des finances") == \
            ["ministère des finances"]

    def test_two_steps(self):
        got = chain("direction A au commissariat régional de l'éducation "
                    "au ministère de l'éducation")
        assert got[0].startswith("commissariat régional")
        assert got[-1] == "ministère de l'éducation"

    def test_no_attachment(self):
        assert chain("direction générale des impôts") == []

    def test_terminates_on_a_pathological_name(self):
        # Depth is capped so a degenerate name cannot loop forever.
        assert len(chain(" au ministère" * 50)) <= 8


class TestModalParent:
    def test_picks_the_commonest(self):
        got, share = modal_parent(["a", "a", "b"])
        assert got == "a" and abs(share - 2 / 3) < 1e-9

    def test_variant_spellings_count_together(self):
        # The whole point: MINISTERE DE L'EQUIPEMENT and Ministère de
        # l'Équipement are one parent, not two.
        got, share = modal_parent(["MINISTERE DE L'EQUIPEMENT",
                                   "Ministère de l'Équipement",
                                   "MINISTERE DES FINANCES"])
        assert fold(got) == "ministere de l'equipement"
        assert abs(share - 2 / 3) < 1e-9

    def test_empty(self):
        assert modal_parent([]) == (None, 0.0)
        assert modal_parent(["", "  "]) == (None, 0.0)


class TestResolve:
    def _ministry(self, _portfolio, org):
        return "finances" if "finances" in fold(org or "") else None

    def test_prefers_an_existing_body(self):
        by_name = {"ministere des finances": "O123"}
        assert resolve("Ministère des Finances", by_name, self._ministry) == \
            ("O123", "org")

    def test_falls_back_to_the_canonical_ministry(self):
        # No org row under that exact spelling, but the string names a
        # ministry -- which is how seventy years of renaming collapse onto one
        # node instead of becoming siblings.
        assert resolve("ministère des finances et du budget", {},
                       self._ministry) == ("MIN:finances", "ministry")

    def test_unresolved(self):
        assert resolve("quelque chose", {}, self._ministry) == \
            (None, "unresolved")

    def test_empty(self):
        assert resolve("", {}, self._ministry) == (None, "unresolved")
