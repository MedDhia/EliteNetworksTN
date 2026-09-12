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


def _one_block(body: str, ref: str = "2008T00001SRLB2", domain_rubric: str = "SRLB2"):
    """Wrap a body in a minimal block and segment it."""
    text = "<!-- page:1 -->\n" + body.rstrip() + f"\n\n{ref}\n"
    (FIX / "_tmp_case.md").write_text(text, encoding="utf-8")
    try:
        return _blocks("_tmp_case.md")[0]
    finally:
        (FIX / "_tmp_case.md").unlink(missing_ok=True)


def test_each_person_keeps_their_own_role():
    # "Mme Saida Bessrour est nommee gerante ... et Mr Sami Ben Sedrine est
    # nomme co-gerant" gave both the same title, because the clause-level role
    # won and "co-gerant" is the longer surface form.
    block = _one_block(
        "### Constitution d'une S.A.R.L.\n\nDénomination : Sté Bouhaira.\n\n"
        "Gérance : Mme Saida Bessrour est nommée gérante de la société avec les "
        "pouvoirs les plus étendus, et Mr Sami Ben Sedrine est nommée co-gérant.")
    roles = {e["person_mention"]: e["role_canonical"]
             for e in extract_corporate(block) if e["person_mention"]}
    assert roles.get("Saida Bessrour") == "gerant"
    assert roles.get("Sami Ben Sedrine") == "cogerant"


def test_a_bystander_is_not_given_the_clause_role():
    # Only the person with a role of their own is the object of the action; the
    # other is transferring shares, and was being handed an appointment.
    block = _one_block(
        "## Cession des parts\n\nDénomination : Société El WAHA.\n\n"
        "il a été décidé de nommer monsieur Haithem Taha en tant que co-gérant "
        "ainsi que Monsieur Mohamed Younès a confié 10% de ces parts à "
        "Monsieur Haithem Taha.")
    appointed = {e["person_mention"] for e in extract_corporate(block)
                 if e["event_type"] == "appointed"}
    assert "Haithem Taha" in appointed
    assert "Mohamed Younès" not in appointed


def test_plural_title_enumeration_finds_every_name():
    # Only the first name after "Messieurs" carries a title of its own.
    block = _one_block(
        "## Gestion\n\nDénomination : Société BAYA.\n\n"
        "- acceptation de la démission de Messieurs Foued Noomen et Nizar "
        "Frikha du poste de cogérants de la société.")
    resigned = {e["person_mention"] for e in extract_corporate(block)
                if e["event_type"] == "resigned"}
    assert resigned == {"Foued Noomen", "Nizar Frikha"}


def test_one_clause_can_state_both_an_org_and_a_person_action():
    # A dissolution and the liquidator's appointment share a sentence; a single
    # first-match-wins cue list dropped one of them.
    block = _one_block(
        "Désignation d'un liquidateur\n\nDénomination : Société Sidi Saad.\n\n"
        "il a été décidé de la dissolution totale de la société et la "
        "désignation de Mr Brahim Hami comme liquidateur.")
    events = extract_corporate(block)
    assert "dissolved" in {e["event_type"] for e in events}
    assert any(e["role_canonical"] == "liquidateur" and e["person_mention"] == "Brahim Hami"
               for e in events)


def test_association_bureau_officers_are_extracted():
    # Role-then-name, the reverse of the corporate layout, in 3,746 of the
    # 7,144 association blocks. Previously yielded nothing.
    block = _one_block(
        "**Constitution d'une association**\n\n"
        "Dénomination de l'association : Association de Réinsertion.\n\n"
        "Bureau :\n- Président : Mohamed Ben Sédrine,\n"
        "- Secrétaire général : Nooman Ben Ameur,\n"
        "- Trésorerie : Lotfi Hedhili.",
        ref="2008R00001APSF1")
    roles = {e["person_mention"]: e["role_canonical"] for e in extract_corporate(block)}
    assert roles.get("Mohamed Ben Sédrine") == "association_president"
    assert roles.get("Nooman Ben Ameur") == "secretaire_general"
    assert roles.get("Lotfi Hedhili") == "treasurer"


def test_reconduction_counts_as_a_renewal():
    block = _one_block(
        "## Reconduction du mandat du gérant\n\nDénomination : Société Fer Décor.\n\n"
        "Reconduction du mandat de Monsieur Slim Aloui en qualité de gérant.")
    assert "renewed" in {e["event_type"] for e in extract_corporate(block)}


@pytest.mark.parametrize("body,expect", [
    # The first heading is the action, not the company.
    ("Désignation d'un liquidateur\nSociété de Développement Agricole - Sidi Saad\n"
     "SA au capital de 920.000 Dinars\n", "Développement Agricole"),
    ("## Reconduction du mandat du gérant\n## Changement du Siège social\n"
     "## Fer Décor - SARL\n", "Fer Décor"),
    # Label variants around the denomination.
    ("**Constitution d'une association**\nDénomination de l'association : "
     "Association de Réinsertion des Prisonniers Libérés.\n", "Réinsertion"),
    ("### Constitution d'une SARL\n- Raison sociale : Société « New Energy Rouatbi ».\n",
     "New Energy Rouatbi"),
])
def test_org_name_is_the_company_not_the_action(body, expect):
    assert expect in org_name(body)


def test_org_name_prefers_empty_over_an_action_title():
    # A wrong name resolves to the wrong organisation, which loses the tie;
    # an empty one merely leaves it unresolved, so empty is the safer failure.
    from elitenet.extract import RE_ACTION_TITLE
    got = org_name("Transfert du siège social\nAvis aux créanciers\n")
    assert not got or not RE_ACTION_TITLE.match(got)


def test_a_role_word_does_not_bleed_into_the_name():
    # "Mr Ayadi Bouguerba Commissaire aux Comptes" yielded a person called
    # "Ayadi Bouguerba Commissaire".
    from elitenet.grammar import find_persons
    names = [n for n, _s, _o in find_persons(
        "2 - Nomination de Mr Ayadi Bouguerba Commissaire aux Comptes pour 2008.")]
    assert names == ["Ayadi Bouguerba"]


@pytest.mark.parametrize("phrase,expect", [
    ("sont nommés les gérants avec les pouvoirs les plus étendus", "gerant"),
    ("Gérance : Nomination de Mr Slaheddine Chamli", "gerant"),
    ("les co-gérants de la société", "cogerant"),
])
def test_plural_role_forms_map(phrase, expect):
    from elitenet.grammar import match_role
    assert match_role(phrase)[0] == expect


def test_a_professional_qualification_does_not_outrank_the_conferred_role():
    # "membre de l'ordre des experts comptables ... comme commissaire aux
    # comptes" states a qualification first and the appointment second.
    block = _one_block(
        "Sociétés anonymes\n\nDénomination : Société MEDI-CULT.\n\n"
        "Désigné, Monsieur Mohamed Naceur GHEDAMSI, membre de l'ordre des "
        "experts Comptables de Tunisie, comme commissaire aux comptes pour 3 "
        "exercices.", ref="2008T00002SANB1")
    roles = {e["person_mention"]: e["role_canonical"]
             for e in extract_corporate(block) if e["person_mention"]}
    assert roles.get("Mohamed Naceur GHEDAMSI") == "commissaire_aux_comptes"


@pytest.mark.parametrize("body", [
    "Nombre d'adhérents : 19\nSociété coopérative El Khadra\n",
    "Forme de la société : société anonyme\nSociété CIPI ACTIA\n",
])
def test_label_lines_are_not_organisation_names(body):
    got = org_name(body)
    assert ":" not in got


def test_a_role_stated_after_a_list_governs_everyone_in_it():
    # "Mr A et Mr B sont nommes les gerants" anchors only the last name, so
    # treating the rest as bystanders dropped them. Distinguishing this from
    # the true bystander case is the point.
    block = _one_block(
        "Constitution d'une SARL\n\nDénomination : Sté Major Confection.\n\n"
        "Gérance : Mr Bazzan GIACOMO et Mr Maule Bruno Antonion sont nommés "
        "les gérants avec les pouvoirs les plus étendus.")
    roles = {e["person_mention"]: e["role_canonical"]
             for e in extract_corporate(block) if e["person_mention"]}
    assert roles == {"Bazzan GIACOMO": "gerant", "Maule Bruno Antonion": "gerant"}


@pytest.mark.parametrize("line", ["Le Gérant", "La Gérance", "Le Liquidateur"])
def test_signature_lines_are_not_people(line):
    from elitenet.grammar import clean_name
    assert clean_name(line) == ""


def test_identity_card_label_is_stripped_from_a_name():
    from elitenet.grammar import clean_name
    assert clean_name("Noomen AZZEZ CIN") == "Noomen AZZEZ"


def test_reference_code_trailing_a_line_still_delimits():
    # In 925 issues the code trails the last sentence instead of standing
    # alone, which merged 1,559 announcements into their neighbour and so
    # attributed them to the wrong company.
    from elitenet.segment import _rubric_table, segment_annonces, strip_chrome
    text = ("<!-- page:1 -->\n"
            "Dénomination : Société ALPHA.\nGérant : Mr A Un. 2009A00360SRLB1\n"
            "Dénomination : Société BETA.\nGérant : Mr B Deux. 2009A00361SRLB1\n")
    (FIX / "_tmp_inline.md").write_text(text, encoding="utf-8")
    try:
        pm = strip_chrome((FIX / "_tmp_inline.md").read_text(encoding="utf-8"))
        blocks, _ = segment_annonces(pm, META, _rubric_table())
        assert [b["ref"] for b in blocks] == ["2009A00360SRLB1", "2009A00361SRLB1"]
        assert "ALPHA" in org_name(blocks[0]["text"])
        assert "BETA" in org_name(blocks[1]["text"])
    finally:
        (FIX / "_tmp_inline.md").unlink(missing_ok=True)


@pytest.mark.parametrize("body,expect", [
    # A capital line contains "S.A" and was preferred over the company name.
    ("Désignation d'un directeur général\nSUD INVEST\n"
     "S.A au capital de 5 000 000 dinars\n", "SUD INVEST"),
    ("Suivant le PV\nS.A au capital de 70 Millions de Dinars\n"
     "Banque Tuniso Libyenne\n", "Banque Tuniso Libyenne"),
    # Nothing in the layout names it, but the prose does.
    ("Une société à responsabilité limitée est constituée dite Comptoir de "
     "Boulanger, son siège social à la route de Tataouine\n", "Comptoir de Boulanger"),
])
def test_org_name_survives_capital_lines_and_prose_only_names(body, expect):
    assert org_name(body) == expect


@pytest.mark.parametrize("body,expect", [
    # The OCR layer leaves HTML entities in place; an undecoded "&amp;"
    # survived into 2,654 organisation names and blocks resolution.
    ("BUSINESS &amp; CO SARL\nAu capital de 10.000 DT\n", "BUSINESS & CO SARL"),
    # Closing and signature lines sit exactly where a name would.
    ("Pour extrait\nSUD INVEST\n", "SUD INVEST"),
    # A bare legal form is not a name.
    ("S.A.R.L non résidente\nSociété HAIRTECH\n", "Société HAIRTECH"),
])
def test_org_name_rejects_entities_closings_and_bare_forms(body, expect):
    assert org_name(body) == expect


@pytest.mark.parametrize("clause,expect", [
    # The identity-card number interposed between the verb and "parts" pushed
    # the two more than 60 characters apart.
    ("ont cédé à Monsieur Salah Ben Braham au CIN 01614532 délivré le 20 août "
     "1999 à Tunis toutes leurs parts sociaux", "shares_transferred"),
    ("s'est désisté de sa fonction de cogérant", "resigned"),
])
def test_person_level_cue_gaps_are_closed(clause, expect):
    import re as _re
    from elitenet.extract import CORP_CUES
    fired = [t for _p, c, t in CORP_CUES if _re.search(c, clause, _re.I)]
    assert fired and fired[0] == expect


@pytest.mark.parametrize("clause,expect", [
    ("il a été décidé d'augmenter le capital social de 649.000 Dinars",
     "capital_increased"),
    ("Extension de l'objet social. Changement d'adresse", "headquarters_moved"),
])
def test_org_level_cue_gaps_are_closed(clause, expect):
    import re as _re
    from elitenet.extract import ORG_CUES
    fired = [t for _p, c, t in ORG_CUES if _re.search(c, clause, _re.I)]
    assert fired and fired[0] == expect


def test_a_state_act_cannot_postdate_its_own_publication():
    """The rule used to live only in the corporate path.

    That left 87 state acts asserting an act date after the issue that printed
    them -- an act printed "1976-01-31" in a 1974 issue, where the day and
    month match the issue to within a week, so 1974 was read as 1976. Both
    extractors now share one implementation of the rule.
    """
    from elitenet.extract import drop_impossible_dates
    out = drop_impossible_dates(
        {"act_date": "1976-01-31", "pub_date": "1974-02-05"}, "1974-02-05")
    assert out["act_date"] == "", "an impossible act date must be dropped"


def test_an_effective_date_may_lawfully_postdate_publication():
    """Unlike an act date. A decree published in 1974 can take effect in 1975,
    and 1,629 acts in this corpus take effect before their own date, which is
    equally lawful -- so effective_date is not subject to the rule."""
    from elitenet.extract import drop_impossible_dates
    out = drop_impossible_dates(
        {"effective_date": "1975-01-01", "pub_date": "1974-02-05"}, "1974-02-05")
    assert out["effective_date"] == "1975-01-01"


def test_a_plausible_act_date_survives():
    from elitenet.extract import drop_impossible_dates
    out = drop_impossible_dates(
        {"act_date": "1974-01-31", "pub_date": "1974-02-05"}, "1974-02-05")
    assert out["act_date"] == "1974-01-31"
