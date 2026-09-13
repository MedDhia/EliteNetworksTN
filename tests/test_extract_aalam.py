"""Extraction and the quote gate for the A'lam Tunisiyun build.

Named apart from `tests/test_extract.py` and `test_extract_elitenet.py`, which
belong to the `src/eltn` and `src/elitenet` builds.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aalam.extract import (RULE_BINDINGS, _load_cues, _plausible_name,
                           extract_entry, find_persons, load_gazetteer)
from aalam.llm import quote_is_verbatim
from aalam.segment import parse_header

FIX = Path(__file__).parent / "fixtures"
GAZ = load_gazetteer()
CUES = _load_cues()
VOCAB = ["الفقه", "النحو", "المنطق", "البلاغة"]


def _entry(text, name="أحمد بن حسين", uid="aalam:1.04"):
    return extract_entry({"entry_uid": uid, "name_ar": name, "text": text},
                         CUES, GAZ, VOCAB)


# --------------------------------------------------------------------------- #
# what must be extracted
# --------------------------------------------------------------------------- #

def test_the_stock_tutelage_formula_is_read():
    # The densest tie in the book, and the one no other build here has.
    rows = _entry("وارتبط من أول وهلة بشيخها الطاهر بن مسعود وقرأ عليه الفقه والنحو.")
    assert len(rows) == 1
    assert rows[0]["relation"] == "studied_under"
    assert "مسعود" in rows[0]["counterparty_name"]


def test_the_subjects_read_are_kept_not_discarded():
    # What a man read with his shaykh says what kind of authority was being
    # transmitted, so it is an attribute of the tie rather than noise.
    rows = _entry("بشيخها الطاهر بن مسعود وقرأ عليه الفقه والنحو والمنطق والبلاغة.")
    assert rows and set(rows[0]["subjects_studied"].split("|")) >= {"الفقه", "النحو"}


def test_every_assertion_carries_a_quote_from_its_own_text():
    text = "كما قرأ على الشيخ أحمد الأبي البيان لسعد الدين التفتزاني."
    for row in _entry(text):
        assert quote_is_verbatim(row["evidence_quote"], text)


# --------------------------------------------------------------------------- #
# what must NOT be extracted
# --------------------------------------------------------------------------- #

def test_a_postnominal_title_does_not_anchor_a_name_after_it():
    # مصطفى باي is Mustafa Bey. Anchoring forward on باي read the words that
    # followed the title -- "خلفاً لشقيقه حسين" -- as somebody's name.
    found = find_persons("الأمير مصطفى باي خلفاً لشقيقه حسين باي", GAZ)
    assert all("خلفا" not in name for name, _, _ in found)


def test_a_bare_verb_yields_nothing():
    # Arabic is verb-subject-object, so «ارتقى الأمير مصطفى باي إلى العرش» names
    # the man doing the ascending, not a counterparty. Read as an assertion
    # about the entry's subject it made Ibrahim al-Riyahi ascend the throne.
    assert _entry("وعندما ارتقى إلى العرش الأمير مصطفى باي خلفاً لشقيقه حسين باي.",
                  name="إبراهيم الرياحي", uid="aalam:1.03") == []


def test_a_clause_about_someone_else_is_not_attributed_to_the_subject():
    # «وعندما خلف الأمير حمودة باشا والده» is Hammuda succeeding his own father.
    # Attributing it to the man whose entry it sits in made Yusuf Sahib al-Tabi
    # the son of Hammuda Pasha.
    rows = _entry("وعندما خلف الأمير حمودة باشا والده يوم 13 جمادى الثانية.",
                  name="يوسف صاحب الطابع", uid="aalam:1.02")
    assert all(r["relation"] != "child_of" for r in rows)


def test_a_cue_does_not_fire_inside_a_longer_word():
    # "ألف" (he authored) is a substring of "الفقه" (jurisprudence). Unbounded,
    # it turned a man's reading list into a claim that he wrote a book.
    rows = _entry("وقرأ عليه الفقه والنحو.")
    assert all(r["relation"] != "authored" for r in rows)


def test_a_quoted_title_does_not_become_part_of_a_name():
    # Folding strips the guillemets, which let «البيان» run on into the name of
    # the shaykh it was read with.
    rows = _entry("كما قرأ على الشيخ أحمد الأبي «البيان» لسعد الدين التفتزاني.")
    assert rows and "البيان" not in rows[0]["counterparty_name"]


def test_a_name_span_stops_at_a_following_verb():
    found = find_persons("بشيخها الطاهر بن مسعود وقرأ عليه الفقه", GAZ)
    assert found and all("وقرا" not in name for name, _, _ in found)


def test_grammar_is_not_mistaken_for_a_name():
    assert not _plausible_name("إلا أن يعرب", GAZ)
    # A lone unknown token is usually a common noun; it has to be someone the
    # volume has already introduced.
    assert not _plausible_name("الثابتة", GAZ)
    assert _plausible_name("الورداني", GAZ)


def test_a_man_is_not_his_own_teacher():
    rows = _entry("وقرأ على الشيخ أحمد بن حسين الفقه.", name="أحمد بن حسين")
    assert all(r["counterparty_id"] != r["subject_id"] for r in rows)


def test_only_resolvable_bindings_reach_the_rule_pass():
    assert RULE_BINDINGS == {"prepositional", "possessive"}
    assert all(c["binding"] in RULE_BINDINGS for c in CUES)


# --------------------------------------------------------------------------- #
# the gate on the model pass
# --------------------------------------------------------------------------- #

def test_an_unquotable_assertion_is_rejected():
    # The whole basis for trusting the model pass. A tie the book does not
    # state has no sentence to quote, so it cannot survive this check.
    text = "وما إن وصل خير الدين إلى باردو سنة 1838 حتى الحق بمدرسة صغار المماليك."
    assert quote_is_verbatim("الحق بمدرسة صغار المماليك", text)
    assert not quote_is_verbatim("عُيّن خير الدين سفيراً للدولة التونسية في لندن", text)


def test_the_gate_tolerates_a_line_break_but_not_an_invention():
    text = "وصل خير الدين\nإلى باردو سنة 1838."
    assert quote_is_verbatim("وصل خير الدين إلى باردو", text)
    assert not quote_is_verbatim("وصل خير الدين إلى باريس", text)


def test_the_gate_accepts_orthographic_variation_only():
    # The quote is transcribed from the same OCR, so it may differ in exactly
    # the ways folding already treats as equivalent -- and in no other way.
    text = "قرأ على الشيخ أحمد الأبي."
    assert quote_is_verbatim("قرا علي الشيخ احمد الابي", text)


# --------------------------------------------------------------------------- #
# entry headings
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("head,birth,death", [
    ("الجنرال خير الدين\n(1822 - 1890)\nالجندي والمصلح", 1822, 1890),
    # Bidirectional rendering flips the pair on some pages.
    ("محمد بن الخوجة\n)1942 - 1869(\n", 1869, 1942),
    # OCR damage inside the bracket; the years themselves still read.
    ("أحمد بن حسين\n(1800 - 00)1868\n", 1800, 1868),
])
def test_life_dates_are_read_through_damage(head, birth, death):
    got = parse_header(head)
    assert (got["birth_year"], got["death_year"]) == (birth, death)


def test_an_unstated_birth_year_is_not_invented():
    # The volume prints "(... - 1887)" for General Husayn. That is the source
    # declining to say, and must not be recorded as a death year read as birth.
    got = parse_header("الجنرال حسين\n(... - 1887)\nالرجل والمواطن")
    assert got["death_year"] == 1887
    assert got["birth_year"] == ""


# --------------------------------------------------------------------------- #
# the error class the quote gate cannot catch
# --------------------------------------------------------------------------- #

def test_reading_an_author_is_not_studying_under_him():
    # «الغزالي وابن رشد، قد استأثروا بعنايته» says he gave his attention to
    # their writings. Read as a teaching tie it makes Ibn Rushd, dead in 1198,
    # the teacher of a man born in 1871. Ten such ties reached the first model
    # pass and every quote was genuine, so the verbatim check passed all of
    # them: this is the one class that guard is blind to by construction.
    from aalam.llm import reclassify_anachronistic
    rows = [
        {"relation": "studied_under", "counterparty_name": "ابن رشد"},
        {"relation": "studied_under", "counterparty_name": "الشيخ الغزالي"},
        {"relation": "studied_under", "counterparty_name": "أحمد الأبي"},
    ]
    assert reclassify_anachronistic(rows) == 2
    assert rows[0]["relation"] == "read_work_of"
    assert rows[0]["needs_review"] == "yes"
    # A real teacher the book names is untouched.
    assert rows[2]["relation"] == "studied_under"


def test_the_guard_matches_a_whole_name_not_a_substring():
    # A first version matched substrings and reclassified خليل مطران, who died
    # in 1949 and was the subject's contemporary, because "خليل" was on the
    # list as the Maliki digest Mukhtasar Khalil. A guard that silently
    # rewrites the wrong man is worse than the error it was built to catch.
    from aalam.llm import is_classical
    assert is_classical("ابن رشد")
    assert is_classical("الشيخ الغزالي")
    assert not is_classical("خليل")
    assert not is_classical("محمود قابادو")   # really did teach, in person


def test_a_person_placed_only_by_a_relation_is_marked_not_named():
    # «ابنة الأصرم» is a real tie to a woman the book never names. Kept,
    # because dropping it deletes a tie the source states; marked, because
    # counting her as an identified person overcounts the population and
    # invites a merge with some other unnamed daughter.
    from aalam.relations import name_kind
    assert name_kind("ابنة الأصرم") == "described"
    assert name_kind("شقيق محمد باي خير الدين") == "described"
    assert name_kind("البشير صفر") == "named"
