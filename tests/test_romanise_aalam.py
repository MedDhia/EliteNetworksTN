"""The Latin edition of the A'lam Tunisiyun registers.

The gate these exercise is the counterpart of the verbatim-quote gate on the
extraction passes. An extracted tie is admitted by quoting its page; a gloss
has no page to quote, so it is admitted by reducing to the same consonants as
the Arabic it claims to render. What neither catches is stated in the module
docstring and in `docs/LIMITATIONS-aalam-tunisiyun.md`.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from aalam.romanise import (MODES, arabic_spine, check, cohorts, descriptors,
                            glosses, latin_spine, spines_agree)

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed" / "aalam-tunisiyun"


def _read(name):
    with (PROC / name).open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# --- the folding rules, one case each ---------------------------------------

@pytest.mark.parametrize("arabic,latin", [
    # The plain reading: consonant for consonant, vowels ignored.
    ("سالم بو حاجب", "Salem Bou Hajeb"),
    ("سالم بو حاجب", "Salim Bu Hajib"),
    # The article, written with a hyphen, without one, and assimilated to a sun
    # letter so that no l survives at all.
    ("البشير صفر", "al-Bashir Safar"),
    ("جريدة الحاضرة", "El Hadhira"),
    ("خير الدين", "Khereddine"),
    # French writes its own article in front of a transliterated name.
    ("الجمعية الخلدونية", "La Khaldounia"),
    # `عبد ال...` is one word in French and three in IJMES.
    ("عبد الجليل الزاوش", "Abdeljelil Zaouche"),
    ("عبد الجليل الزاوش", "Abd al-Jalil al-Zawush"),
    # ق is q, k or the hard g of Tunisian French.
    ("محمود قابادو", "Mahmud Qabadu"),
    ("محمد بورقيبة", "Mohamed Bourguiba"),
    # ...while a soft French g is the sound of ج.
    ("الجنرال حسين", "Général Hussein"),
    # ش is ch in French and sh in IJMES; غ is gh in both, and is not a hard g.
    ("محمد الطاهر بن عاشور", "Mohamed Tahar Ben Achour"),
    ("أحمد الغطاس", "Ahmed Ghattas"),
    # Arabic has no p, so باشا comes back as Pasha.
    ("طاهر باشا خير الدين", "Tahar Pacha Khereddine"),
    # ن before a labial is written m, because that is what is said.
    ("علي باش حانبة", "Ali Bach Hamba"),
    # A doubled Latin consonant is one Arabic letter.
    ("عبد السلام البكوش", "Abdessalem Bakkouche"),
    # ة is silent, except where the word governs the next one.
    ("عزيزة عثمانة", "Aziza Othmana"),
    ("حركة الشباب التونسي", "Harakat al-Shabab al-Tunisi"),
    # A word-final ه is weak and French drops it.
    ("محمد عبده", "Mohamed Abdou"),
    # An organisation is stored with the common noun for what it is; the Latin
    # form drops it, and `org_kind` carries it instead.
    ("جريدة الحاضرة", "al-Hadira"),
    ("المدرسة الصادقية", "al-Sadiqiyya"),
    # ڤ is absent from the identifier table, which deletes it. The gate has its
    # own table so that Guellaty keeps its middle consonant.
    ("حسن ڤلاتي", "Hassen Guellaty"),
    # Arabic has no v either, and writes ف where a European name has one.
    ("لافيس", "Lavisse"),
    ("فيكتور سار", "Victor Sar"),
    # `th` and `dh` are each a digraph and a legal pair of single letters, so
    # both readings are tried: ث in Othmana, ت+ح in Fathallah; ذ in Fadhel,
    # د+ه in Midhat.
    ("حمزة فتح الله", "Hamza Fathallah"),
    ("مدحت باشا", "Midhat Pacha"),
    ("محمد الفاضل بن عاشور", "Mohamed Fadhel Ben Achour"),
    # ...but the unambiguous ones are always folded. Reading the `ch` of Pacha
    # as two letters would invent a consonant the Arabic does not have.
    ("علي بوشوشة", "Ali Bouchoucha"),
    # بال is the preposition bi plus the article. Only the article goes: the b
    # is a consonant the Latin writes.
    ("الجامعة الأمريكية بالقاهرة", "al-Jamia al-Amrikiyya bi-al-Qahira"),
    # A bracket is a word boundary, so the article inside one is still found.
    ("كلية الآداب (السوربون)", "Kulliyyat al-Adab (al-Surbun)"),
])
def test_a_correct_gloss_passes_the_gate(arabic, latin):
    assert spines_agree(arabic, latin), (arabic_spine(arabic), latin_spine(latin))


@pytest.mark.parametrize("arabic,latin", [
    # Another person entirely.
    ("عزيزة عثمانة", "Mohamed Bourguiba"),
    # Right family, wrong given name: the failure a name index makes when it
    # completes a bare given name from the wrong man.
    ("سالم بو حاجب", "Ali Bou Hajeb"),
    # Father against son, both in this volume.
    ("محمد الطاهر بن عاشور", "Mohamed Fadhel Ben Achour"),
    # GOLD-FINDINGS s6: مصطفى آغة and مصطفى رضوان are two men, and the
    # extractor merged them. The gate refuses the merge.
    ("مصطفى آغة", "Mustapha Radhouane"),
    # An honorific the Arabic does not carry.
    ("خير الدين", "Khereddine Pacha Ettounsi"),
    # A name element dropped for elegance.
    ("محمد بن عثمان", "Mohamed Othman"),
    # The French article is a separate word. An earlier pattern matched the
    # bare letters, so `Lavisse` lost its first two and لافيس could not be
    # glossed at all; the fix must not go the other way and accept this.
    ("فيس", "Lavisse"),
])
def test_a_wrong_gloss_is_refused(arabic, latin):
    assert not spines_agree(arabic, latin)


def test_the_gate_cannot_see_a_vowel():
    # The honest limit, asserted rather than described: Arabic does not write
    # short vowels, so `Salim` and `Salem` are one spine and the gate has
    # nothing to tell them apart with. This is why the rows a reader will meet
    # are verified by hand instead.
    assert spines_agree("سالم بو حاجب", "Salim Bou Hajeb")
    assert spines_agree("سالم بو حاجب", "Salem Bou Hajeb")
    assert latin_spine("Salim") == latin_spine("Salem") == latin_spine("Sulaym")


# --- the table --------------------------------------------------------------

def test_every_gloss_in_the_table_holds():
    bad = [p for name, entry in glosses().items() for p in check(name, entry)]
    assert not bad, "\n".join(bad[:20])


def test_every_name_in_every_table_has_a_gloss():
    table = glosses()
    names = ({r["name_ar"] for r in _read("persons.csv")}
             | {r["name_ar"] for r in _read("organisations.csv")})
    missing = sorted(names - set(table))
    assert not missing, f"{len(missing)} unglossed, first: {missing[:5]}"


def test_no_identifier_moved():
    # The whole reason this stage could run after the gold sample was coded:
    # ids hash `name_ar`, so adding display columns cannot change one, and
    # every committed edge_id and every gold verdict stays valid.
    from aalam.names_ar import org_id, person_id
    for r in _read("persons.csv"):
        if r["name_kind"] == "named":
            assert person_id(r["name_ar"]) == r["person_id"]
    for r in _read("organisations.csv"):
        assert org_id(r["name_ar"], r["org_kind"].upper()) == r["org_id"]


# Three Latin forms are each carried by two Arabic strings, and in all three
# the two strings are one man: `علي بو حاجب` against `علي بوحاجب`, the same for
# Khalil, and `حسن قلاتي` against `حسن ڤلاتي`, which are the two ways Tunisian
# Arabic writes a hard g. The register kept them apart because the identity key
# is built from the Arabic and a space is a character; the Latin column is what
# made them visible. They are NOT merged: ids hash `name_ar`, and merging would
# move them and invalidate the gold verdicts coded against the current edges.
# Recorded in `docs/GOLD-FINDINGS-aalam-tunisiyun.md` s15 instead.
KNOWN_DOUBLE_NODES = {
    "Ali Bu Hajib": {"علي بو حاجب", "علي بوحاجب"},
    "Khalil Bu Hajib": {"خليل بو حاجب", "خليل بوحاجب"},
    "Hasan Gallati": {"حسن قلاتي", "حسن ڤلاتي"},
}


def test_no_new_pair_of_people_shares_one_latin_name():
    # A collision not in the list above is either a homonym the Latin column
    # has just merged for the reader -- the risk LIMITATIONS s9 names -- or a
    # fourth duplicate node. Either way it is a finding, not a passing build.
    from collections import defaultdict
    seen = defaultdict(set)
    for r in _read("persons.csv"):
        if r["gloss_mode"] == "translated" or not r["name_ijmes"]:
            continue
        seen[r["name_ijmes"]].add(r["name_ar"])
    clashes = {k: v for k, v in seen.items() if len(v) > 1}
    assert clashes == KNOWN_DOUBLE_NODES, \
        {k: v for k, v in clashes.items() if KNOWN_DOUBLE_NODES.get(k) != v}


def test_no_two_institutions_share_one_latin_name():
    # Unlike the persons, the organisation register has no collisions at all,
    # and a new one would mean two bodies had been given one name.
    from collections import defaultdict
    seen = defaultdict(set)
    for r in _read("organisations.csv"):
        if r["gloss_mode"] == "translated":
            continue
        seen[r["name_ijmes"]].add(r["name_ar"])
    assert not {k: v for k, v in seen.items() if len(v) > 1}


# Four of the twelve `described` nodes are not descriptions. `_DESCRIPTION_HEADS`
# in relations.py lists `ابن ` for "son of", and it also catches the patronymic
# that opens a great many real Arabic names. Ibn Sina, Ibn Rushd, Ibn al-Rumi
# and Ibn Abi Dinar are named people, and glossing them is what made it visible:
# each passes the consonant gate as a transliteration, which a description
# cannot do. Not fixed here, because name_kind feeds nothing that would move an
# id but does feed the figures' exclusion list, and changing it changes what is
# drawn. GOLD-FINDINGS s16.
PATRONYMIC_NOT_DESCRIPTION = {"ابن سينا", "ابن رشد", "ابن الرومي", "ابن أبي دينار"}


def test_a_described_node_is_never_given_a_name():
    # `الأساتذة الذين ساهموا في تكوينهما` is a description, not a person, and a
    # transliteration of it would read as one. GOLD-FINDINGS s7.
    for r in _read("persons.csv"):
        if r["name_kind"] != "described":
            continue
        assert r["gloss_tier"] == "described"
        if r["name_ar"] in PATRONYMIC_NOT_DESCRIPTION:
            assert r["gloss_mode"] == "transliterated"
        else:
            assert r["gloss_mode"] == "translated", r["name_ar"]


def test_no_other_described_node_turns_out_to_be_a_name():
    # The gate is the discriminator: a real description has no consonant spine
    # in common with a rendering of it. A fifth row passing would be a fifth
    # misclassification, and should be added to the set above deliberately.
    from aalam.romanise import spines_agree
    passing = {r["name_ar"] for r in _read("persons.csv")
               if r["name_kind"] == "described"
               and spines_agree(r["name_ar"], r["name_ijmes"])}
    assert passing == PATRONYMIC_NOT_DESCRIPTION


def test_an_office_is_translated_not_transliterated():
    # An office is a common-noun post. `al-Wazir al-Akbar` names nothing a
    # reader could look up; Grand Vizier does.
    offices = [r for r in _read("organisations.csv") if r["org_kind"] == "office"]
    assert offices
    assert all(r["gloss_mode"] == "translated" for r in offices), \
        [r["name_ar"] for r in offices if r["gloss_mode"] != "translated"][:5]


def test_the_edge_tables_carry_both_columns_on_both_ends():
    rows = _read("edges/all.csv")
    assert rows
    for r in rows:
        for col in ("from_fr", "from_ijmes", "to_fr", "to_ijmes"):
            assert r[col].strip(), f"{r['edge_id']} has no {col}"


def test_the_quote_stays_arabic():
    # It is the verbatim gate. A translated quote proves nothing about the
    # page, so the column is left alone and no English sibling is offered.
    rows = _read("edges/all.csv")
    assert all(any("؀" <= c <= "ۿ" for c in r["evidence_quote"])
               for r in rows)


def test_the_cohorts_and_descriptors_are_glossed():
    assert set(cohorts()) == {"السابقون", "التابعون", "المعاصرون"}
    described = [r for r in _read("entries.csv") if r["role_descriptor_ar"]]
    assert all(r["role_descriptor_en"] for r in described), \
        [r["name_ar"] for r in described if not r["role_descriptor_en"]][:5]
    assert descriptors()
