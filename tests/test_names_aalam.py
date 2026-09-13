"""Arabic name normalisation for the A'lam Tunisiyun build.

Named apart from `tests/test_names.py`, which belongs to the `src/elitenet`
build and tests the French-language normaliser.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aalam.names_ar import org_id, parse_person, person_id, transliterate
from aalam.textnorm_ar import clean_page, fold, fold_pattern


def test_the_french_normaliser_cannot_be_reused_here():
    # The reason this module exists. names.py uppercases into [A-Z0-9' ] and
    # so reduces every Arabic string to the empty one; reusing it would have
    # made all 38 subjects a single PERSON_UNKNOWN node.
    from elitenet.names import person_id as fr_person_id
    assert fr_person_id("محمد الطاهر بن عاشور") == "PERSON_UNKNOWN"
    assert person_id("محمد الطاهر بن عاشور") != "PERSON_UNKNOWN"


@pytest.mark.parametrize("a,b", [
    # The book calls one man الجنرال خير الدين on p.97 and خير الدين باشا on
    # p.193. A title in the identity key would make those two people.
    ("الجنرال خير الدين", "خير الدين باشا"),
    ("الشيخ محمد الطاهر بن عاشور", "محمد الطاهر بن عاشور"),
    # bin- and ibn- are the same particle; the book uses both spellings.
    ("محمد الطاهر بن عاشور", "محمد الطاهر ابن عاشور"),
    # OCR does not reliably distinguish the hamza forms of alif.
    ("أحمد بن أبي الضياف", "احمد بن ابي الضياف"),
])
def test_spelling_variants_give_one_identifier(a, b):
    assert person_id(a) == person_id(b)


@pytest.mark.parametrize("a,b", [
    # Two Ben Achours, father and son, both in the volume. Fusing them would
    # collapse a kinship tie into a self-loop.
    ("محمد الطاهر بن عاشور", "محمد الفاضل بن عاشور"),
    ("علي بو حاجب", "سالم بو حاجب"),
    ("الشاذلي خير الله", "خير الله بن مصطفى"),
])
def test_distinct_people_keep_distinct_identifiers(a, b):
    assert person_id(a) != person_id(b)


def test_rank_is_recorded_not_discarded():
    # Titles are stripped from the identity key but they are evidence of
    # standing, so they come back as an attribute of the mention.
    assert parse_person("الجنرال خير الدين").rank == "general"
    assert parse_person("خير الدين باشا").rank == "pasha"
    assert parse_person("مصطفى آغة").rank == "agha"


def test_compound_names_survive_the_article_rule():
    # Stripping the definite article token by token reduces خير الدين to
    # "خير دين" and makes the man's surname read as al-Din.
    assert "KHYRALDYN" in person_id("خير الدين باشا")
    assert "ZYNALABDYN" in person_id("زين العابدين السنوسي")


def test_theophoric_compounds_are_one_given_name():
    # عبد السلام is a single name. Split, every Abd- in the book collides.
    p = parse_person("عبد السلام البكوش")
    assert len(p.tokens) == 2
    assert person_id("عبد السلام البكوش") != person_id("عبد الجليل الزاوش")


def test_a_bare_title_is_not_a_person():
    # "الشيخ" alone appears constantly in running prose. If it parsed as a
    # name it would become one of the best-connected nodes in the graph.
    assert parse_person("الشيخ").is_empty
    assert person_id("الشيخ") == "PERSON_UNKNOWN"


def test_surname_alone_matches_the_full_name_for_blocking():
    # The book introduces a man in full and refers to him by surname after.
    full = parse_person("علي الورداني")
    short = parse_person("الورداني")
    assert full.surname_key == short.surname_key


def test_identifiers_are_ascii_and_greppable():
    # They must sit alongside the other builds' PERSON_BENACHOUR_MOHAMED form
    # so a reader can join the two registries by eye.
    pid = person_id("محمد الطاهر بن عاشور")
    assert pid.isascii() and pid.startswith("PERSON_")
    assert org_id("المدرسة الصادقية", "SCHOOL").startswith("SCH_")
    # The node type namespaces the identifier, as in the other builds.
    assert org_id("الزيتونة", "MOSQUE") != org_id("الزيتونة", "SCHOOL")


def test_transliteration_is_deterministic():
    assert transliterate("محمد") == transliterate("محمد")


def test_fold_collapses_what_ocr_confuses():
    assert fold("التى") == fold("التي")      # alif maqsura vs ya
    assert fold("مدرسة") == fold("مدرسه")    # ta marbuta vs ha
    assert fold("أحمد") == fold("احمد")      # hamza forms


def test_fold_pattern_keeps_regex_syntax():
    # A cue is written as the book prints it but matched against folded text.
    # Folding it with fold() would strip the metacharacters and the cue table
    # would silently stop matching.
    assert fold_pattern(r"قرأ\s+على") == r"قرا\s+علي"


def test_clean_page_repairs_the_comma_without_touching_words():
    # tesseract reads the Arabic comma as a guillemet at a clause boundary.
    out = clean_page("وقد كان حريصا على تلخيصها» ثم")
    assert "،" in out and "»" not in out
