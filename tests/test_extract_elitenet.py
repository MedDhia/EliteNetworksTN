"""Event extraction for `src/elitenet`: action cues, role attribution, and what
must NOT be extracted.

Named apart from `tests/test_extract.py`, which belongs to the `src/eltn`
build and holds its own hand-coded gold-standard tests.
"""
from pathlib import Path

import pytest

from elitenet.extract import extract_corporate, is_convocation, org_name
from elitenet.segment import _rubric_table, segment_annonces, strip_chrome

FIX = Path(__file__).parent / "fixtures"
META = {"issue_uid": "annonces-legales/fr/2008/006", "collection": "annonces-legales",
        "year": 2008, "issue": "006", "pub_date": "2008-01-11"}


def _blocks(name):
    pm = strip_chrome((FIX / name).read_text(encoding="utf-8"))
    return segment_annonces(pm, META, _rubric_table())[0]


def test_convocation_yields_no_events():
    # The agenda of a meeting yet to happen reads like a list of acts
    # ("1 - Augmentation du capital"). Extracting from it invented 2,303
    # events across the corpus, 1,414 of them capital increases.
    block = _blocks("annonces_convocation.md")[0]
    assert is_convocation(block)
    assert extract_corporate(block) == []


def test_infinitive_appointment_is_caught():
    # "il a ete decide de nommer ..." appears in 4,983 blocks and was missed
    # entirely by cues that only matched conjugated forms.
    block = _blocks("annonces_infinitive.md")[0]
    events = extract_corporate(block)
    appointed = [e for e in events if e["event_type"] == "appointed"]
    assert appointed, "infinitive 'de nommer' produced no appointment"
    assert any("Haithem" in e["person_mention"] for e in appointed)


def test_en_tant_que_is_a_role_marker():
    block = _blocks("annonces_infinitive.md")[0]
    roles = {e["role_canonical"] for e in extract_corporate(block)
             if "Haithem" in e["person_mention"]}
    assert "cogerant" in roles


def test_lowercase_title_still_finds_the_person():
    # The gazette prints "monsieur" in lower case 5,840 times.
    block = _blocks("annonces_infinitive.md")[0]
    assert any("Haithem" in e["person_mention"] for e in extract_corporate(block))


@pytest.mark.parametrize("prose", [
    "la déclaration de souscription et de versement",
    "monsieur le receveur de l'enregistrement des actes de sociétés",
    "Reçu par Madame le Receveur de l'Enregistrement",
])
def test_institutional_prose_does_not_become_a_person(prose):
    from elitenet.grammar import find_persons
    assert find_persons(prose) == []


def test_share_transfer_catches_the_past_participle():
    # "a cede ses parts" occurs in 1,396 blocks and was missed by a cue that
    # only matched the unaccented present tense.
    text = ("### Cession de parts\n\nSuivant P.V. en date du 3 mars 2010, "
            "Monsieur Ali Ben Salah a cédé ses parts sociales à "
            "Monsieur Karim Zouari.\n\n2010T00001SRLB2\n")
    (FIX / "_tmp_cede.md").write_text("<!-- page:1 -->\n" + text, encoding="utf-8")
    try:
        block = _blocks("_tmp_cede.md")[0]
        types = {e["event_type"] for e in extract_corporate(block)}
        assert "shares_transferred" in types
    finally:
        (FIX / "_tmp_cede.md").unlink(missing_ok=True)


def test_org_name_prefers_the_stated_denomination():
    text = ("### Constitution d'une SARL\n\nSuivant acte en date du 1 mars 2010\n\n"
            "- Dénomination : Sté EL WAFA DE QUINCAILLERIE.\n- Capital social : 9 000 dinars.\n")
    assert org_name(text) == "Sté EL WAFA DE QUINCAILLERIE"
