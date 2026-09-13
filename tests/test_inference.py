"""Inference from name rarity, and the homonym it must still refuse.

The dyad anchor exists because "Mohamed Trabelsi" matches over 1,500 gazette
pages; a name-only link there merges dozens of people into one vertex. But the
danger is not uniform -- measured over the 2,563 seed persons who are named in
print with no anchor available, 98% bear a name held by exactly one seed person
and matching exactly one gazette candidate. For those a name IS an identifier.

So the tier is gated on rarity, and these pin both directions.
"""
from elitenet.resolve import NameRarity, INFERRED_NAME_FLOOR


def test_a_name_unique_on_both_sides_can_identify():
    r = NameRarity(seed_count={"RARE NAME": 1}, gazette_count={"RARE NAME": 1})
    assert r.is_unique("RARE NAME")


def test_a_name_borne_by_two_seed_persons_cannot():
    """The Trabelsi case: the seed sheet itself says the name is ambiguous."""
    r = NameRarity(seed_count={"MOHAMED TRABELSI": 7},
                   gazette_count={"MOHAMED TRABELSI": 1})
    assert not r.is_unique("MOHAMED TRABELSI")


def test_a_name_matching_several_gazette_candidates_cannot():
    """Unique in the sheet but not in print: several distinct candidate keys
    means the corpus holds people the sheet does not distinguish."""
    r = NameRarity(seed_count={"COMMON IN PRINT": 1},
                   gazette_count={"COMMON IN PRINT": 4})
    assert not r.is_unique("COMMON IN PRINT")


def test_an_unseen_name_is_treated_as_unique():
    """Absent from both counts means nobody else bears it, which is the
    permissive direction -- but the name-similarity floor still applies, so an
    unseen key cannot resolve on its own."""
    r = NameRarity()
    assert r.is_unique("NEVER SEEN")
    assert INFERRED_NAME_FLOOR >= 0.90, (
        "the rarity gate is necessary but not sufficient; the names must still "
        "agree closely or a rare misspelling becomes an identification")
