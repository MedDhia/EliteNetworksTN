"""The interior-apparatus test and the destination classifier.

Both are built from specific rows of `spells.csv.gz`, and the cases below are
those rows rather than invented strings. That matters here because the two
guards on the local-attachment rule each exist for one real pattern in the
gazette, and a paraphrase would not exercise either.

The rules live in ``scripts/apparatus.py`` rather than in the figure scripts so
that this module imports no drawing library: matplotlib is not a dependency of
this project, and a test that needed it would be skipped in CI, which is the
one place these rules most need checking.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import pandas as pd  # noqa: E402

from apparatus import (  # noqa: E402
    MINISTRY_ENGLISH, SECURITY_STAYS, attached_to_local_body,
    consecutive_moves, destination, in_interior_apparatus,
    in_security_apparatus, ministry_destination, ministry_of, security_branch,
    security_destination, wilson,
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


class TestConsecutiveMoves:
    """Building post-to-post moves out of the spell table.

    The second rule below is here because breaking it is silent. Filtering on
    the next post's *branch* rather than its start date discards every move out
    of the classified body, which is most of them, and the figure drawn on the
    remainder looks entirely reasonable.
    """

    @staticmethod
    def _frame(rows):
        import pandas as pd
        f = pd.DataFrame(rows, columns=["person_id", "start", "rank_score",
                                        "branch"])
        f["start"] = pd.to_datetime(f.start)
        return f

    def test_a_move_out_of_the_body_is_kept(self):
        f = self._frame([("P1", "2000-01-01", 50, "interior"),
                         ("P1", "2003-01-01", 50, None)])
        m = consecutive_moves(f)
        assert len(m) == 1
        assert m.iloc[0].branch == "interior"
        assert m.iloc[0].to_branch is None or pd.isna(m.iloc[0].to_branch)

    def test_a_spell_with_no_next_post_is_dropped(self):
        f = self._frame([("P1", "2000-01-01", 50, "interior")])
        assert len(consecutive_moves(f)) == 0

    def test_the_last_spell_of_a_person_is_dropped_not_joined_to_the_next(self):
        # Without the per-person grouping, P1's last post would "move" to P2's
        # first one and invent a crossing that never happened.
        f = self._frame([("P1", "2000-01-01", 50, "interior"),
                         ("P2", "2001-01-01", 50, "defence")])
        assert len(consecutive_moves(f)) == 0

    def test_one_post_per_person_date_and_the_senior_one_wins(self):
        f = self._frame([("P1", "2000-01-01", 30, "interior"),
                         ("P1", "2000-01-01", 70, "defence"),
                         ("P1", "2004-01-01", 50, "interior")])
        m = consecutive_moves(f)
        assert len(m) == 1
        assert m.iloc[0].branch == "defence"      # the senior post stands
        assert m.iloc[0].to_branch == "interior"

    def test_moves_are_ordered_by_date_not_by_table_order(self):
        f = self._frame([("P1", "2008-01-01", 50, "defence"),
                         ("P1", "2002-01-01", 50, "interior")])
        m = consecutive_moves(f)
        assert len(m) == 1
        assert (m.iloc[0].branch, m.iloc[0].to_branch) == ("interior", "defence")


class TestMinistryNaming:
    """Naming the ministry a destination belongs to.

    A portfolio-only rule leaves 28% of the interior's and defence's
    destinations unplaced, because roughly half the directorates carry no
    portfolio; reading the body's own name brings that to 8%.
    """

    def test_a_portfolio_names_its_ministry(self):
        assert ministry_of("min_finances", "") == "finances"
        assert ministry_of("min_sante", "") == "sante"

    def test_a_compound_portfolio_resolves_to_its_lead_domain(self):
        # A convention, not a fact: a person takes one post, so counting the
        # move into every merged domain would make flows exceed people.
        assert ministry_of("min_finances+plan", "") == "finances"
        assert ministry_of("min_commerce+tourisme", "") == "commerce"

    def test_an_unportfolioed_body_is_named_from_its_own_name(self):
        assert ministry_of(None, "direction générale des impôts") == "finances"
        assert ministry_of(
            None, "commissariat régional au développement agricole de Sousse"
        ) == "agriculture"
        assert ministry_of(
            None, "direction des affaires au ministère de la santé") == "sante"

    def test_an_unplaceable_body_returns_nothing(self):
        assert ministry_of(None, "centre national du cuir et de la chaussure") is None

    def test_every_named_domain_has_an_english_name(self):
        # A domain the naming table does not cover would silently fall through
        # to "Not identifiable" and be read as a gap in the record.
        for key, _pat in __import__("apparatus")._MINISTRY_BY_NAME:
            assert key in MINISTRY_ENGLISH


class TestMinistryDestination:
    def test_the_security_branches_keep_their_own_names(self):
        # A move inside the apparatus must never read as a move to "Interior"
        # as though it were any other ministry.
        assert ministry_destination("min_interieur", "", "ministere") == "Interior ministry"
        assert ministry_destination("min_defense", "", "ministere") == "Defence"
        assert ministry_destination(None, "", "gouvernorat") == "Governorates"

    def test_a_ministry_is_named_in_english(self):
        assert ministry_destination("min_finances", "", "ministere") == "Finance"
        assert ministry_destination(
            None, "direction générale des impôts", "direction") == "Finance"

    def test_bodies_that_are_not_ministries_are_kept_apart(self):
        assert ministry_destination(None, "Commune de Sfax", "commune") == "Municipalities"
        assert ministry_destination(
            None, "office des terres domaniales", "entreprise_publique") in (
                "Public enterprise", "Agriculture")
        assert ministry_destination(
            None, "cour des comptes", "juridiction") == "Courts"

    def test_what_cannot_be_placed_says_so(self):
        assert ministry_destination(
            None, "centre national du cuir et de la chaussure",
            "autre") == "Not identifiable"


class TestConsecutiveMovesCarriesTheNextPost:
    @staticmethod
    def _frame(rows):
        f = pd.DataFrame(rows, columns=["person_id", "start", "rank_score",
                                        "branch", "org_portfolio", "org_name",
                                        "org_form"])
        f["start"] = pd.to_datetime(f.start)
        return f

    def test_the_next_posts_attributes_come_through(self):
        f = self._frame([
            ("P1", "2000-01-01", 50, "interior", "min_interieur", "x", "ministere"),
            ("P1", "2004-01-01", 50, None, "min_finances", "y", "ministere"),
        ])
        m = consecutive_moves(f)
        assert len(m) == 1
        r = m.iloc[0]
        assert r.to_portfolio == "min_finances"
        assert r.to_org == "y"
        assert r.to_form == "ministere"

    def test_the_next_rank_comes_through(self):
        f = self._frame([
            ("P1", "2000-01-01", 80, "territorial", "min_interieur", "x", "ministere"),
            ("P1", "2004-01-01", 55, None, "min_finances", "y", "ministere"),
        ])
        r = consecutive_moves(f).iloc[0]
        assert r.rank_score == 80
        assert r.to_rank_score == 55
        assert r.to_rank_score < r.rank_score          # a demotion

    def test_an_unranked_destination_stays_nan_not_zero(self):
        # A zero would sit at the bottom of the scale and make every move to an
        # unranked post look like the steepest demotion in the table.
        import math
        f = self._frame([
            ("P1", "2000-01-01", 80, "territorial", "min_interieur", "x", "ministere"),
            ("P1", "2004-01-01", None, None, "min_finances", "y", "ministere"),
        ])
        r = consecutive_moves(f).iloc[0]
        assert math.isnan(r.to_rank_score)

    def test_the_next_start_comes_through(self):
        f = self._frame([
            ("P1", "2000-01-01", 50, "interior", "min_interieur", "x", "ministere"),
            ("P1", "2004-06-01", 50, None, "min_finances", "y", "ministere"),
        ])
        r = consecutive_moves(f).iloc[0]
        assert r.to_start == pd.Timestamp("2004-06-01")

    def test_an_absent_next_name_becomes_an_empty_string(self):
        # The classifiers take strings; a NaN here would raise inside a regex.
        f = self._frame([
            ("P1", "2000-01-01", 50, "interior", "min_interieur", "x", "ministere"),
            ("P1", "2004-01-01", 50, None, None, None, None),
        ])
        m = consecutive_moves(f)
        assert m.iloc[0].to_org == ""
        assert m.iloc[0].to_form == ""
        assert ministry_destination(m.iloc[0].to_portfolio, m.iloc[0].to_org,
                                    m.iloc[0].to_form) == "Not identifiable"
