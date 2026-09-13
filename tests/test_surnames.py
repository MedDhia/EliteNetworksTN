"""Tests for the surname proxy.

Stdlib and pandas only. ``scripts/surnames.py`` imports no drawing library on
purpose, and matplotlib is not a project dependency, so importing the figure
module here would fail under CI.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from surnames import (  # noqa: E402
    fold, namesake_hits, rarity_band, same_surname_probability,
    shared_outcome_fast, shared_outcome_probability, split_name, surname,
    usable,
)


class TestFold:
    def test_strips_accents_and_case(self):
        assert fold("Béji") == "beji"
        assert fold("Hédi") == "hedi"
        assert fold("BACCOUCHE") == "baccouche"

    def test_accented_and_plain_spellings_agree(self):
        assert fold("Béji") == fold("Beji")


class TestSurnameExtraction:
    def test_plain_two_token_name(self):
        assert surname("Hamadi Jebali") == "jebali"

    def test_particle_starts_the_surname(self):
        # Ben Abdallah is a family; filing it under Abdallah merges it with
        # every unrelated Abdallah in the register.
        assert surname("Mohamed Ben Abdallah") == "ben abdallah"
        assert surname("Zine El Abidine Ben Ali") == "ben ali"

    def test_a_weak_particle_inside_a_given_name_does_not_open_the_surname(self):
        # "El" here belongs to the compound given name Zine El Abidine. Taking
        # the first particle files the most-recorded name in the corpus under
        # "el abidine ben ali".
        assert surname("Zine El Abidine Ben Ali") == "ben ali"

    def test_a_strong_particle_outranks_an_earlier_weak_one(self):
        assert surname("Mohamed Bel Hassen Ben Zeineb") == "ben zeineb"

    def test_chained_patronymics_take_the_last(self):
        # Tunisian usage makes the terminal patronymic the family name.
        assert surname("Kamel ben Mohamed ben Ammar") == "ben ammar"

    def test_a_strong_particle_keeps_the_weak_ones_after_it(self):
        assert surname("Ahmed Ben El Hadj Salem") == "ben el hadj salem"

    def test_first_weak_particle_when_there_is_no_strong_one(self):
        assert surname("Béji Caïd Essebsi") == "caid essebsi"

    def test_lowercase_particle(self):
        assert surname("Mohamed ben Salah") == "ben salah"

    def test_titles_are_not_names(self):
        assert surname("Docteur Ahmed Gharbi") == "gharbi"
        assert split_name("Docteur Ahmed Gharbi")[0] == "ahmed"

    def test_single_token_has_no_surname(self):
        assert surname("Mohamed") is None
        assert surname("") is None

    def test_returns_given_name_too(self):
        assert split_name("Hédi Baccouche") == ("hedi", "baccouche")


class TestUsable:
    def test_rejects_extraction_noise(self):
        # French running text from the surrounding act, not a person.
        assert not usable("compter")
        assert not usable("nommer")

    def test_rejects_a_bare_given_name(self):
        assert not usable("ali")
        assert not usable("mohamed")

    def test_keeps_a_given_name_reached_through_a_particle(self):
        # "Ben Ali" is a family name even though "Ali" alone is not.
        assert usable("ben ali")
        assert usable("ben salah")

    def test_rejects_empty(self):
        assert not usable(None)
        assert not usable("")

    def test_rejects_nan(self):
        # Regression. split_name returns None for an unrecoverable name, but
        # putting that list into a DataFrame column stores it as NaN, and
        # `not float("nan")` is False — so a bare falsiness check let 246
        # people through carrying the same non-value, which a frequency count
        # reads as one 246-member family.
        assert not usable(float("nan"))

    def test_rejects_a_non_string(self):
        assert not usable(0)
        assert not usable(["gharbi"])

    def test_keeps_an_ordinary_surname(self):
        assert usable("baccouche")


class TestSameSurnameProbability:
    def test_all_distinct_is_zero(self):
        assert same_surname_probability(["a", "b", "c"]) == 0.0

    def test_all_identical_is_one(self):
        assert same_surname_probability(["a", "a", "a"]) == 1.0

    def test_known_value(self):
        # two of four share: pairs = 2*1 = 2, total ordered pairs = 4*3 = 12
        assert same_surname_probability(["a", "a", "b", "c"]) == 2 / 12

    def test_undefined_below_two_people(self):
        assert math.isnan(same_surname_probability(["a"]))
        assert math.isnan(same_surname_probability([]))

    def test_does_not_pair_a_person_with_themselves(self):
        # Sampling without replacement: one person alone can never be a pair.
        assert same_surname_probability(["a", "b"]) == 0.0


class TestSharedOutcomeProbability:
    def test_both_reached_it(self):
        # one surname, two people, both high: the only pair is a hit
        assert shared_outcome_probability(["a", "a"], [True, True]) == 1.0

    def test_neither_reached_it(self):
        assert shared_outcome_probability(["a", "a"], [False, False]) == 0.0

    def test_only_one_of_the_pair(self):
        assert shared_outcome_probability(["a", "a"], [True, False]) == 0.0

    def test_known_value(self):
        # surname a: 3 people, 2 high -> 2 ordered hit pairs of 6 ordered pairs
        # surname b: 2 people, 0 high -> 0 of 2
        names = ["a", "a", "a", "b", "b"]
        out = [True, True, False, False, False]
        assert shared_outcome_probability(names, out) == 2 / 8

    def test_unique_names_are_undefined_not_zero(self):
        # No two people share a surname, so the quantity does not exist. A
        # zero here would read as evidence of no association.
        assert math.isnan(shared_outcome_probability(["a", "b"], [True, True]))

    def test_singletons_contribute_nothing(self):
        # A person with a unique surname is in no pair either way.
        paired = shared_outcome_probability(["a", "a"], [True, True])
        plus_singleton = shared_outcome_probability(
            ["a", "a", "c"], [True, True, True])
        assert paired == plus_singleton


class TestNamesakeHits:
    def test_first_arrival_has_no_namesake(self):
        assert namesake_hits([("org1", "P1", "gharbi")]) == [False]

    def test_second_person_same_surname_same_org_is_a_hit(self):
        rows = [("org1", "P1", "gharbi"), ("org1", "P2", "gharbi")]
        assert namesake_hits(rows) == [False, True]

    def test_different_org_is_not_a_hit(self):
        rows = [("org1", "P1", "gharbi"), ("org2", "P2", "gharbi")]
        assert namesake_hits(rows) == [False, False]

    def test_different_surname_is_not_a_hit(self):
        rows = [("org1", "P1", "gharbi"), ("org1", "P2", "dridi")]
        assert namesake_hits(rows) == [False, False]

    def test_a_person_is_not_their_own_namesake(self):
        # Returning to a body you already served in must not count; this is
        # the single commonest shape in the table, because spells are split by
        # renewal and re-appointment.
        rows = [("org1", "P1", "gharbi"), ("org1", "P1", "gharbi")]
        assert namesake_hits(rows) == [False, False]

    def test_a_real_namesake_after_ones_own_return_still_counts(self):
        rows = [("org1", "P1", "gharbi"),
                ("org1", "P1", "gharbi"),
                ("org1", "P2", "gharbi")]
        assert namesake_hits(rows) == [False, False, True]

    def test_ones_own_return_after_a_namesake_counts(self):
        # P1 comes back to a body that now also holds P2, a genuine namesake.
        rows = [("org1", "P1", "gharbi"),
                ("org1", "P2", "gharbi"),
                ("org1", "P1", "gharbi")]
        assert namesake_hits(rows) == [False, True, True]


class TestFastPathMatchesTheReference:
    """The permutation loops run the statistic on integer codes for speed.

    The string implementation above is the definition; this pins the two
    together so the fast path cannot drift from it unnoticed.
    """

    def _fast(self, names, outcome):
        import numpy as np
        import pandas as pd
        codes, uniq = pd.factorize(np.array(names))
        return shared_outcome_fast(codes, np.array(outcome), len(uniq))

    def test_agrees_on_a_worked_case(self):
        names = ["a", "a", "a", "b", "b"]
        out = [True, True, False, False, False]
        assert self._fast(names, out) == shared_outcome_probability(names, out)

    def test_agrees_on_random_inputs(self):
        import random
        rnd = random.Random(11)
        for _ in range(25):
            n = rnd.randint(2, 60)
            names = [rnd.choice("abcdefg") for _ in range(n)]
            out = [rnd.random() < 0.4 for _ in range(n)]
            a, b = self._fast(names, out), shared_outcome_probability(names, out)
            assert (math.isnan(a) and math.isnan(b)) or abs(a - b) < 1e-12

    def test_agrees_that_unique_names_are_undefined(self):
        assert math.isnan(self._fast(["a", "b", "c"], [True, True, True]))


class TestRarityBand:
    def test_boundaries(self):
        assert rarity_band(1) == "1–2"
        assert rarity_band(2) == "1–2"
        assert rarity_band(3) == "3–5"
        assert rarity_band(5) == "3–5"
        assert rarity_band(6) == "6–20"
        assert rarity_band(20) == "6–20"
        assert rarity_band(21) == "21–60"
        assert rarity_band(60) == "21–60"
        assert rarity_band(61) == "61+"
        assert rarity_band(1000) == "61+"
