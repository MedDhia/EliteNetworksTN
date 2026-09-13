"""The interior-apparatus test and the destination classifier.

Both are built from specific rows of `spells.csv.gz`, and the cases below are
those rows rather than invented strings. That matters here because the two
guards on the local-attachment rule each exist for one real pattern in the
gazette, and a paraphrase would not exercise either.

The rules live in ``scripts/apparatus.py`` rather in the figure scripts so
that this module imports no drawing library: matplotlib is not a dependency of
this project, and a test that needed it would be skipped in CI, which is the
one place these rules most need checking.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from apparatus import (  # noqa: E402
    SECURITY_STAYS, attached_to_local_body, destination, in_interior_apparatus,
    in_security_apparatus, security_branch, security_destination, wilson,
)


class TestInteriorApparatus:
    def test_portfolio_names_the_interior(self):
        assert in_interior_apparatus("min_interieur", "", "ministere")

    def test_compound_portfolio_still_counts(self):
        # "Ministère de l'Intérieur et du Développement Local" - the interior
        # under another name, and 396 spells of it.
        assert in_interior_apparatus(
            "min_developpement+interieur",
            "MINISTERE DE L'INTERIEUR ET DU DEVELOPPEMENT LOCAL", "ministere")

    def test_territorial_forms_count_without_a_portfolio(self):
        assert in_interior_apparatus(None, "Gouvernorat de Bizerte", "gouvernorat")
        assert in_interior_apparatus(None, "Commune de Sfax", "commune")

    def test_security_bodies_count(self):
        assert in_interior_apparatus(None, "direction de la sûreté nationale",
                                     "direction")
        assert in_interior_apparatus(None, "garde nationale", "autre")

    def test_a_portfolio_elsewhere_is_not_the_interior(self):
        assert not in_interior_apparatus("min_finances",
                                         "ministère des finances", "ministere")


class TestLocallyAttachedBodies:
    """Bodies that hang off a commune or a governorate.

    Roughly half the `direction` rows carry no portfolio at all, so without
    this rule the municipal services of Tunis fall outside the apparatus. The
    spell's own `parent_org_id` cannot do the job: it is assigned from the
    surrounding act, and one `direction générale des impôts` spell carries the
    interior ministry as its parent because a single decree appointed across
    several ministries.
    """

    def test_municipal_services_are_interior(self):
        assert attached_to_local_body(
            "direction générale des services techniques à la commune de Tunis",
            "direction")

    def test_regional_council_is_interior(self):
        assert attached_to_local_body(
            "conseil régional au gouvernorat de Bizerte", "autre")

    def test_a_location_is_not_an_attachment(self):
        # The agricultural training institute *at* Sidi Thabet, which happens
        # to be in Ariana. The form is what rejects it.
        name = ("institut national pédagogique et de la formation continue "
                "agricole de Sidi Thabet au gouvernorat de l'Ariana")
        assert not attached_to_local_body(name, "universite")
        assert not in_interior_apparatus(None, name, "universite")

    def test_a_ministry_named_later_wins(self):
        # Hospital construction in Kasserine, run by the equipment ministry.
        # The governorate is where the building goes, not who employs you.
        name = ("hôpital régional catégorie « B » à Sbeïtla à l'unité de "
                "gestion par objectifs au gouvernorat du Kasserine au "
                "ministère de l'équipement, de l'habitat et de "
                "l'aménagement du territoire")
        assert not attached_to_local_body(name, "direction")


class TestDestination:
    def test_an_interior_move_is_not_an_exit(self):
        assert destination("min_interieur", "", "ministere").startswith("stays")

    def test_unportfolioed_revenue_bodies_go_to_finance(self):
        # No portfolio, no ministry in the name; placed by the body's own name.
        for name in ("direction générale des impôts",
                     "direction générale du contrôle fiscal",
                     "direction générale des douanes"):
            assert destination(None, name, "direction") == "finance and economy"

    def test_regional_agricultural_commissariats_are_placed(self):
        assert destination(
            None, "commissariat régional au développement agricole de Sousse",
            "autre") == "infrastructure and production"

    def test_the_centre_is_its_own_bloc(self):
        assert destination("presidence_republique", "", "presidence") == "the centre"
        assert destination("presidence_gouvernement", "", "autre") == "the centre"

    def test_what_cannot_be_placed_says_so(self):
        assert destination(None, "centre national du cuir et de la chaussure",
                           "autre") == "not identifiable"


class TestWilson:
    """The interval used on the outflow figure.

    Wilson rather than the normal approximation because several of these shares
    sit near zero on cohorts of a hundred, where the normal interval runs below
    zero and reports something that cannot happen.
    """

    def test_never_runs_below_zero(self):
        lo, hi = wilson(0, 92)
        assert lo == 0.0
        assert 0.0 < hi < 10.0

    def test_never_runs_above_a_hundred(self):
        lo, hi = wilson(92, 92)
        assert hi == 100.0
        assert 90.0 < lo < 100.0

    def test_brackets_the_point_estimate(self):
        lo, hi = wilson(29, 198)
        assert lo < 29 / 198 * 100 < hi

    def test_a_larger_cohort_gives_a_tighter_interval(self):
        small = wilson(30, 100)
        large = wilson(300, 1000)
        assert (large[1] - large[0]) < (small[1] - small[0])

    def test_an_empty_cohort_does_not_divide_by_zero(self):
        assert wilson(0, 0) == (0.0, 0.0)


class TestSecurityApparatus:
    """A different body from the interior apparatus, and the difference matters.

    It adds defence and military justice; it drops the municipalities. A
    governor moving to a town hall has left the security apparatus without
    leaving the interior ministry's remit, and the two figures built on these
    rules disagree about that move on purpose.
    """

    def test_interior_and_governorates_are_security(self):
        assert in_security_apparatus("min_interieur", "", "ministere")
        assert in_security_apparatus(None, "Gouvernorat de Bizerte", "gouvernorat")
        assert in_security_apparatus(None, "garde nationale", "autre")

    def test_defence_is_security_but_not_interior(self):
        for port, org in (("min_defense", ""),
                          (None, "ministère de la défense nationale"),
                          (None, "tribunal militaire de Tunis")):
            assert in_security_apparatus(port, org, "ministere")
            assert not in_interior_apparatus(port, org, "ministere")

    def test_municipalities_are_interior_but_not_security(self):
        assert in_interior_apparatus(None, "Commune de Sfax", "commune")
        assert not in_security_apparatus(None, "Commune de Sfax", "commune")

    def test_a_commune_attached_body_is_not_security(self):
        # The governorate half of the local-attachment rule applies here; the
        # commune half must not.
        name = "direction générale des services techniques à la commune de Tunis"
        assert in_interior_apparatus(None, name, "direction")
        assert not in_security_apparatus(None, name, "direction")

    def test_a_governorate_attached_body_is_security(self):
        assert in_security_apparatus(
            None, "conseil régional au gouvernorat de Bizerte", "autre")

    def test_a_ministry_named_later_still_wins(self):
        name = ("hôpital régional catégorie « B » à Sbeïtla au gouvernorat du "
                "Kasserine au ministère de l'équipement, de l'habitat et de "
                "l'aménagement du territoire")
        assert not in_security_apparatus(None, name, "direction")

    def test_the_interior_test_runs_before_the_territorial_one(self):
        # A post naming both is the ministry's, not the governorate's.
        assert security_branch(
            "min_interieur", "services au gouvernorat de Sousse",
            "direction") == "interior"

    def test_branches_are_named(self):
        assert security_branch("min_interieur", "", "ministere") == "interior"
        assert security_branch("min_defense", "", "ministere") == "defence"
        assert security_branch(None, "", "gouvernorat") == "territorial"
        assert security_branch("min_finances", "", "ministere") is None


class TestSecurityDestination:
    def test_staying_inside_is_not_an_exit(self):
        assert security_destination(None, "", "gouvernorat") == SECURITY_STAYS
        assert security_destination("min_defense", "", "ministere") == SECURITY_STAYS

    def test_a_town_hall_is_its_own_destination(self):
        # Not folded into the residual: it is a legible career step.
        assert security_destination(
            None, "Commune de Sfax", "commune") == "municipal government"

    def test_outside_bodies_classify_as_for_the_interior(self):
        assert (security_destination(None, "direction générale des impôts",
                                     "direction")
                == destination(None, "direction générale des impôts", "direction")
                == "finance and economy")
