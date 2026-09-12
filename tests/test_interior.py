"""The interior-apparatus test and the destination classifier.

Both are built from specific rows of `spells.csv.gz`, and the cases below are
those rows rather than invented strings. That matters here because the two
guards on the local-attachment rule each exist for one real pattern in the
gazette, and a paraphrase would not exercise either.
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from figures_interior_outflow import destination  # noqa: E402
from figures_sankey import (  # noqa: E402
    _attached_to_local_body, in_interior_apparatus,
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
        assert _attached_to_local_body(
            "direction générale des services techniques à la commune de Tunis",
            "direction")

    def test_regional_council_is_interior(self):
        assert _attached_to_local_body(
            "conseil régional au gouvernorat de Bizerte", "autre")

    def test_a_location_is_not_an_attachment(self):
        # The agricultural training institute *at* Sidi Thabet, which happens
        # to be in Ariana. The form is what rejects it.
        name = ("institut national pédagogique et de la formation continue "
                "agricole de Sidi Thabet au gouvernorat de l'Ariana")
        assert not _attached_to_local_body(name, "universite")
        assert not in_interior_apparatus(None, name, "universite")

    def test_a_ministry_named_later_wins(self):
        # Hospital construction in Kasserine, run by the equipment ministry.
        # The governorate is where the building goes, not who employs you.
        name = ("hôpital régional catégorie « B » à Sbeïtla à l'unité de "
                "gestion par objectifs au gouvernorat du Kasserine au "
                "ministère de l'équipement, de l'habitat et de "
                "l'aménagement du territoire")
        assert not _attached_to_local_body(name, "direction")


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
