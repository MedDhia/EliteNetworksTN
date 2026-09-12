"""Name normalisation: identity must be conservative, matching may be generous."""
import pytest

from elitenet.names import org_id, parse_org, parse_person, person_id


@pytest.mark.parametrize("a,b", [
    ("HATEM BEN-SALEM", "Hatem Ben Salem"),      # seed hyphen vs gazette spacing
    ("HATEM BEN-SALEM", "HATEM BENSALEM"),       # fused particle
    ("HABIB KAMMOUN", "HABIB KAMOUN"),           # doubled consonant
    ("WASSILA HAMMAMI", "WASSILA HAMAMI"),
    ("Moez Zouari", "MOEZ ZOUARI"),              # case
    ("MOHAMED ZINE EL-ABIDINE", "Mohamed Zine El Abidine"),
])
def test_identity_merges_spelling_variants(a, b):
    assert person_id(a) == person_id(b)


@pytest.mark.parametrize("a,b", [
    ("MOHAMED DRISS", "MHAMMED DRISS"),   # distinct given names in practice
    ("HEDI NAKBI", "HADI NAKBI"),
    ("FAYCEL DERBEL", "FAYSAL DERBEL"),   # transliteration: matcher's call, not the id's
])
def test_identity_does_not_merge_transliteration_variants(a, b):
    assert person_id(a) != person_id(b)


def test_transliteration_variants_share_a_match_key():
    # The resolver still gets to see them as candidates.
    assert parse_person("FAYCEL DERBEL").match_key == parse_person("FAYSAL DERBEL").match_key


def test_married_name_is_split_not_merged():
    p = parse_person("Saida Oudi épouse Laâjimi")
    assert p.normalised == "SAIDA OUDI"
    assert p.married_name == "LAAJIMI"


def test_honorifics_are_stripped():
    assert person_id("Monsieur Hatem Ben Salem") == person_id("HATEM BEN-SALEM")


@pytest.mark.parametrize("names", [
    ["SICAR AVENIR", "SICAF AVENIR", "SICAV AVENIR"],   # three distinct vehicles
    ["BTE SICAR", "BTE SICAV", "SOCIETE BTE"],
    ["ATTIJARI SICAR", "GROUPE ATTIJARI"],
])
def test_distinct_legal_vehicles_stay_distinct(names):
    assert len({org_id(n, "COMPANY") for n in names}) == len(names)


@pytest.mark.parametrize("names", [
    ["TUNISIA BROADCASTING", "TUNISIA BROADCASTING SA", "SOCIETE TUNISIA BROADCASTING"],
    ["SOCIETE TUNISIENNE DE SUCRE", "SOCIETE TUNISIENNE DU SUCRE"],
    ["BANQUE INTERNATIONALE ARABE DE TUNISIE BIAT",
     "BANQUE INTERNATIONALE ARABE DE TUNISIE"],
])
def test_generic_form_and_acronym_variants_merge(names):
    assert len({org_id(n, "COMPANY") for n in names}) == 1


def test_acronym_split_only_when_it_is_an_initialism():
    assert parse_org("BANQUE INTERNATIONALE ARABE DE TUNISIE BIAT").acronym == "BIAT"
    # An ordinary trailing word must not be mistaken for an acronym, which
    # matters because the seed sheet gives no case signal.
    assert parse_org("BANQUE INTERNATIONALE ARABE DE TUNISIE").acronym == ""


def test_node_id_namespaces_do_not_collide():
    assert org_id("ENNAHDHA", "PARTY") != org_id("ENNAHDHA", "ORGANIZATION")
