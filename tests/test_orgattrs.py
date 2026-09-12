"""Organisation identifiers and addresses.

Two things are being pinned. First, that an identifier is treated as an
identifier: a firm has one matricule fiscal, so two values on one node is a
defect and has to be reported rather than averaged away. Second, that the join
from mention to organisation refuses an ambiguous mention -- a mention
resolving to two firms identifies neither, and assigning it to the first would
stamp an unrelated company with someone else's tax ID.
"""
from elitenet.grammar import (RE_RC, RE_SIEGE, normalise_address, normalise_rc,
                              trim_address)
from elitenet.orgattrs import (addresses, conflicts, identifiers,
                               mention_to_org)


def res(mention, oid, label=""):
    return {"org_mention": mention, "resolved_org_id": oid,
            "resolved_org_label": label or oid}


def ev(mention, **kw):
    row = {"org_mention": mention, "org_mf": "", "org_rc": "",
           "org_address": "", "org_postal_code": "", "event_type": "appointed",
           "event_date": "2009-03-04", "pub_date": "2009-03-06",
           "date_precision": "exact", "issue_uid": "annonces-legales/fr/2009/019",
           "folio_page": "7", "block_uid": "B1"}
    row.update(kw)
    return row


# --- the join -------------------------------------------------------------- #

def test_a_mention_resolving_to_two_organisations_identifies_neither():
    """The guard tergm.org_lifecycle already applies, for the same reason.

    "Mise a jour des statuts" is a section heading that org_name() reads as a
    firm on 87 events, and it resolves to three unrelated companies.
    """
    m2o, _labels = mention_to_org([
        res("Mise à jour des statuts", "CO_A"),
        res("Mise à jour des statuts", "CO_B"),
        res("SOCIETE ALPHA", "CO_ALPHA"),
    ])
    assert "Mise à jour des statuts" not in m2o
    assert m2o["SOCIETE ALPHA"] == "CO_ALPHA"


def test_an_ambiguous_mention_contributes_no_identifier():
    m2o, labels = mention_to_org([res("AMBIG", "CO_A"), res("AMBIG", "CO_B")])
    rows, diag = identifiers([ev("AMBIG", org_mf="1518656S")], m2o, labels)
    assert rows == []
    assert diag["identifier_rows"] == 0


# --- identifiers ----------------------------------------------------------- #

def test_repeated_observations_of_one_value_aggregate_with_a_date_range():
    m2o, labels = mention_to_org([res("ALPHA", "CO_ALPHA", "ALPHA SA")])
    rows, _diag = identifiers([
        ev("ALPHA", org_mf="1518656S", event_date="2009-03-04",
           issue_uid="i1"),
        ev("ALPHA", org_mf="1518656S", event_date="2004-01-09",
           issue_uid="i2"),
        ev("ALPHA", org_mf="1518656S", event_date="2011-07-22",
           issue_uid="i2"),
    ], m2o, labels)
    assert len(rows) == 1
    r = rows[0]
    assert r["n_observations"] == 3
    assert r["n_issues"] == 2
    assert (r["first_seen"], r["last_seen"]) == ("2004-01-09", "2011-07-22")
    assert r["is_conflicting"] == 0


def test_the_two_identifier_kinds_are_separate_rows():
    m2o, labels = mention_to_org([res("ALPHA", "CO_ALPHA")])
    rows, diag = identifiers(
        [ev("ALPHA", org_mf="1518656S", org_rc="B133371997")], m2o, labels)
    assert {r["id_type"] for r in rows} == {"matricule_fiscal",
                                            "registre_commerce"}
    assert diag["orgs_with_matricule_fiscal"] == 1
    assert diag["orgs_with_registre_commerce"] == 1


def test_two_values_of_one_identifier_are_flagged_on_both_rows():
    """A firm has one tax ID. Two is a defect, and neither value is dropped:
    which one is right is a question for a coder, not for the aggregator."""
    m2o, labels = mention_to_org([res("ALPHA", "CO_ALPHA")])
    rows, diag = identifiers([
        ev("ALPHA", org_mf="1518656S"),
        ev("ALPHA", org_mf="1518656S"),
        ev("ALPHA", org_mf="9999111X"),
    ], m2o, labels)
    assert len(rows) == 2
    assert all(r["is_conflicting"] == 1 for r in rows)
    assert all(r["n_values_for_org"] == 2 for r in rows)
    assert diag["conflicting_matricule_fiscal"] == 1
    # Best-corroborated first, so a reader sees the likely-correct value first.
    assert rows[0]["n_observations"] == 2


# --- what the conflicts mean ----------------------------------------------- #

def test_one_character_apart_reads_as_ocr_and_wholly_different_as_a_merge():
    """The distinction is the whole point of the table.

    A substituted digit is one registration misread -- this OCR confuses 4 and
    6 routinely. A wholly different number means two firms were collapsed into
    one node, and every tie on that node is suspect.
    """
    m2o, labels = mention_to_org([res("ALPHA", "CO_ALPHA", "ALPHA SA"),
                                  res("BETA", "CO_BETA", "BETA SA")])
    rows, _diag = identifiers([
        ev("ALPHA", org_mf="1518656S"), ev("ALPHA", org_mf="1518456S"),
        ev("BETA", org_mf="1518656S"), ev("BETA", org_mf="7240001W"),
    ], m2o, labels)
    cons = {c["org_id"]: c for c in conflicts(rows)}
    assert cons["CO_ALPHA"]["likely"] == "ocr"
    assert cons["CO_ALPHA"]["min_distance"] == 1
    assert cons["CO_BETA"]["likely"] == "merge"
    # Closest first: a reader scanning down crosses from OCR into merges.
    assert conflicts(rows)[0]["likely"] == "ocr"


def test_a_consistent_organisation_reports_no_conflict():
    m2o, labels = mention_to_org([res("ALPHA", "CO_ALPHA")])
    rows, _d = identifiers([ev("ALPHA", org_mf="1518656S")] * 4, m2o, labels)
    assert conflicts(rows) == []


# --- addresses ------------------------------------------------------------- #

def test_two_printings_of_one_address_are_not_a_move():
    """Casing, accents and the street abbreviation vary between printings."""
    m2o, labels = mention_to_org([res("ALPHA", "CO_ALPHA")])
    rows, diag = addresses([
        ev("ALPHA", org_address="2, Rue des Métiers Z.I. Charguia"),
        ev("ALPHA", org_address="2, rue des metiers ZI Charguia",
           event_date="2011-01-01"),
    ], m2o, labels)
    assert len(rows) == 1, rows
    assert rows[0]["n_observations"] == 2
    assert diag["orgs_with_two_or_more_addresses"] == 0


def test_a_transfer_destination_is_marked_as_a_move_not_a_stated_seat():
    m2o, labels = mention_to_org([res("ALPHA", "CO_ALPHA")])
    rows, diag = addresses([
        ev("ALPHA", org_address="2, rue des métiers Charguia"),
        ev("ALPHA", org_address="28, rue Alain Savary La Marsa",
           event_type="headquarters_moved", event_date="2011-05-02"),
    ], m2o, labels)
    kinds = {r["obs_kind"]: r for r in rows}
    assert kinds["stated"]["address_normalised"].startswith("2 rue des metiers")
    assert kinds["moved_to"]["observed_date"] == "2011-05-02"
    assert diag["obs_moved_to"] == 1


def test_the_postal_code_is_read_off_the_address():
    m2o, labels = mention_to_org([res("ALPHA", "CO_ALPHA")])
    rows, _d = addresses(
        [ev("ALPHA", org_address="1 bis, rue du Sénégal 1002 Tunis Belvédère")],
        m2o, labels)
    assert rows[0]["postal_code"] == "1002"


# --- the patterns themselves ----------------------------------------------- #
# `R.?C.?` without a leading word boundary matches inside ordinary French, and
# a first corpus probe that allowed it inflated the count by 70%.

def test_the_rc_pattern_rejects_ordinary_french_words():
    for text in ("pour les exercices 2003-2004 et 2005",
                 "les opérations commerciales de la société",
                 "l'exclusion de tout autre objet",
                 "le marché de 100 dinars la part"):
        assert RE_RC.search(text) is None, text


def test_the_rc_pattern_reads_the_printed_forms():
    for text, want in (
        ("R.C : B133371997", "B133371997"),
        ("RC n° 14231996", "14231996"),
        ("RCS : B181991996 Monastir", "B181991996"),
        ("Registre de commerce B124791996", "B124791996"),
        ("immatriculée au registre de commerce sous le n° B 187881996",
         "B187881996"),
    ):
        m = RE_RC.search(text)
        assert m is not None, text
        assert normalise_rc(m.group("rc")) == want, text


def test_a_bare_year_is_not_a_registration_number():
    assert normalise_rc("2003") == ""


def test_an_address_capture_stops_at_the_registration_number_after_it():
    """A sampled capture ran from the seat through the RC number into the next
    clause, which is why the address is trimmed like a corporate-party name."""
    m = RE_SIEGE.search(
        "siège social est à Tunis rue Hédi Nouira RC n° 14231996, ayant élu "
        "domicile en l'étude de son avocat Me Brahim Nouisser")
    assert trim_address(m.group("addr")) == "à Tunis rue Hédi Nouira"


def test_an_address_capture_stops_at_the_next_rubric_label():
    m = RE_SIEGE.search("Siège social : 1 bis, rue du Sénégal 1002 Tunis "
                        "Belvédère.\nForme juridique : Société anonyme")
    assert trim_address(m.group("addr")) == "1 bis, rue du Sénégal 1002 Tunis Belvédère"


def test_the_column_header_form_yields_no_address():
    """In a tabular notice the cell under "Siège social" is sometimes the
    company name, and recording that as an address would be worse than
    recording nothing."""
    m = RE_SIEGE.search('siège social\nSociété de Promotion "Immobilière '
                        'Essakia" – SARL\nAu capital de 100.000 dinars')
    assert trim_address(m.group("addr")) == ""


def test_the_transfer_clause_yields_no_stated_seat():
    """Its first address is the seat being left. Recording that as the current
    one would date the move backwards."""
    m = RE_SIEGE.search(
        "transfert du siège social de la société de 1, rue Jobrane Khalil "
        "Jobrane – Bordj Louzir Ariana à 8, rue Ibn Abi Dhiaf El Menzah V")
    assert m is None or trim_address(m.group("addr")) == ""


def test_normalise_address_folds_accents_and_street_abbreviations():
    a = normalise_address("42, Av. Habib Bourguiba - Z.I. Sfax")
    b = normalise_address("42 avenue habib bourguiba zi sfax")
    assert a == b, (a, b)
