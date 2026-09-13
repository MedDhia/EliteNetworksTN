"""Legal form per registered company, and the people connected to them.

Three things these tests exist to pin, each of them a mistake made while
building this stage rather than a hypothetical:

1. A single stray filing must not decide a company's legal form. Reading the
   latest filing made `HANNIBAL LEASE` a SARL on one filing against 47, and
   produced 842 false conversions out of 1,637.
2. The Arabic phrase for *limited liability* is a SARL, not a SUARL. The
   sole-partner qualifier is what makes it a SUARL, and the first version of
   the name reader mapped every Arabic SARL to SUARL.
3. An undetermined form is not "not SARL/SA". 76.1% of register identifiers
   have no determinable form and must never be counted as excluded.
"""
from __future__ import annotations

import csv
import gzip
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from elitenet import legalform as L


# --- the form read off a registered name ---------------------------------- #

def test_a_french_sarl_suffix_is_read():
    assert L.form_from_name("STE ALPHA SARL", "") == "SARL"
    assert L.form_from_name("ALPHA S.A.R.L.", "") == "SARL"


def test_suarl_wins_over_sarl_because_it_contains_it():
    """Every SUARL string contains a SARL substring, so order matters."""
    assert L.form_from_name("BETA SUARL", "") == "SUARL"
    assert L.form_from_name("NOVA S.U.A.R.L", "") == "SUARL"


def test_arabic_limited_liability_is_a_sarl_not_a_suarl():
    """The bug this test exists for: the bare phrase means limited liability,
    which is a SARL. Reading it as SUARL would have relabelled every
    Arabic-named SARL as a single-member company."""
    assert L.form_from_name("", "شركة ذات مسؤولية محدودة") == "SARL"


def test_arabic_sole_partner_qualifier_makes_it_a_suarl():
    assert L.form_from_name(
        "", "شركة ذات مسؤولية محدودة ذات الشريك الواحد") == "SUARL"


def test_arabic_share_company_is_an_sa():
    assert L.form_from_name("", "شركة خفية الاسم") == "SA"


def test_a_leading_sa_is_not_a_legal_form():
    """`SA MAISON DU PAIN` is a bakery, not a societe anonyme. A bare SA is
    only a form where a form goes: at the end."""
    assert L.form_from_name("SA MAISON DU PAIN", "") == ""
    assert L.form_from_name("GAMMA SA", "") == "SA"


def test_a_name_stating_nothing_returns_nothing():
    assert L.form_from_name("EPSILON HOLDING", "") == ""
    assert L.form_from_name("", "") == ""


# --- deciding one company's form ------------------------------------------ #

def test_one_form_filed_many_times_is_that_form():
    d = L.decide_form(Counter({"SARL": 9}),
                      [("2009-01-01", "SARL"), ("2011-01-01", "SARL")])
    assert d["legal_form"] == "SARL"
    assert d["is_conversion"] == 0
    assert d["minority_forms"] == ""


def test_a_single_stray_filing_does_not_decide_the_form():
    """HANNIBAL LEASE: 47 SA filings and one SARL, the SARL last. Taking the
    latest filing called a leasing company a SARL. The stray is recorded and
    ignored."""
    dated = [(f"200{i}-01-01", "SA") for i in range(1, 8)]
    dated.append(("2018-05-10", "SARL"))
    d = L.decide_form(Counter({"SA": 7, "SARL": 1}), dated)
    assert d["legal_form"] == "SA"
    assert d["is_conversion"] == 0
    assert d["minority_forms"] == "SARL:1"


def test_a_stray_filing_at_the_start_does_not_decide_either():
    """The mirror case: UNIVERSAL GOMME, one SA filing earliest against 32
    SARL. `legal_form_first` must not become SA."""
    dated = [("2004-06-28", "SA")] + [(f"201{i}-01-01", "SARL")
                                      for i in range(1, 8)]
    d = L.decide_form(Counter({"SARL": 7, "SA": 1}), dated)
    assert d["legal_form"] == "SARL"
    assert d["legal_form_first"] == "SARL"
    assert d["is_conversion"] == 0


def test_a_sustained_switch_is_a_conversion_and_is_dated():
    """STE CLINIQUE LES JASMINS: SARL filings then SA filings, both with real
    support. This is the case the rule must still catch."""
    dated = [("2007-05-09", "SARL"), ("2008-01-01", "SARL"),
             ("2009-01-01", "SARL"), ("2013-06-29", "SA"),
             ("2015-01-01", "SA"), ("2018-07-23", "SA")]
    d = L.decide_form(Counter({"SARL": 3, "SA": 3}), dated)
    assert d["is_conversion"] == 1
    assert d["legal_form_first"] == "SARL"
    assert d["legal_form"] == "SA"
    assert d["conversion_date"] == "2013-06-29"


def test_two_forms_with_no_dates_cannot_be_a_conversion():
    """A conversion is a claim about order. Without dates there is no order,
    so the modal form stands rather than a coin toss being recorded."""
    d = L.decide_form(Counter({"SARL": 5, "SA": 2}), [])
    assert d["legal_form"] == "SARL"
    assert d["is_conversion"] == 0


def test_the_minority_form_is_always_recorded_even_when_ignored():
    """Ignored is not discarded: a reader must be able to find every company
    whose filings disagreed, and re-judge it."""
    dated = [("2005-01-01", "SARL"), ("2006-01-01", "SARL"),
             ("2007-01-01", "SARL"), ("2020-01-01", "SUARL")]
    d = L.decide_form(Counter({"SARL": 3, "SUARL": 1}), dated)
    assert d["is_conversion"] == 0
    assert "SUARL:1" in d["minority_forms"]


# --- one company, two identifiers ----------------------------------------- #

def test_both_of_a_companys_numbers_resolve_to_one_company():
    """99.0% of register rows carry both a matricule and a numRegistre.
    Keying a company on the identifier counted it twice wherever the gazette
    printed both numbers -- 13,111 of them."""
    rec = {"rne_name_fr": "ALPHA", "rne_matricule": "111111A",
           "rne_num_registre": "B1111"}
    companies, key_of = L.company_index({"111111A": rec}, {"B1111": rec})
    assert len(companies) == 1
    assert key_of["111111A"] == key_of["B1111"] == "B1111"


def test_one_filing_printing_both_numbers_is_one_form_observation(
        tmp_path, monkeypatch):
    """Otherwise a company that prints both of its numbers on every filing
    reads as having filed twice as often as it did."""
    monkeypatch.setattr(L, "PROCESSED", tmp_path)
    _write_events(tmp_path, [
        {"legal_form": "SARL", "org_mf": "111111A", "org_rc": "B1231999",
         "org_mention": "ALPHA", "event_date": "2010-01-01"},
    ])
    obs, _d = L.gazette_forms({"111111A": "B1111", "B1231999": "B1111"})
    assert list(obs) == ["B1111"]
    assert obs["B1111"]["n_events"] == 1
    assert obs["B1111"]["forms"] == Counter({"SARL": 1})
    assert obs["B1111"]["identifiers"] == {"111111A", "B1231999"}


# --- a role title is not a person ----------------------------------------- #

def test_a_bare_role_title_is_not_a_person():
    """`Directeur Général` was the individual connected to the most companies
    in the first build of this table -- 100 of them. It is a title that
    escaped `clean_name`, not a person."""
    assert not L.is_a_person_name("Directeur Général")
    assert not L.is_a_person_name("Directeur Général Adjoint")
    assert not L.is_a_person_name("Nomination de M")
    assert not L.is_a_person_name("")


def test_a_real_name_is_a_person():
    assert L.is_a_person_name("Slim Ben Ali")
    assert L.is_a_person_name("MOHAMED MARWEN MABROUK")


def test_a_role_title_mention_is_excluded_and_counted(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "PROCESSED", tmp_path)
    _write_resolution(tmp_path, [
        {"person_mention": "Directeur Général", "org_mf": "111111A",
         "link_status": "unresolved", "mention_cluster_id": "C9",
         "role_observed": "dg"},
    ])
    rows, diag = L.company_persons(_forms(), KEY_OF, {})
    assert rows == []
    assert diag["mention_is_a_role_title_not_a_person"] == 1


# --- the register side ---------------------------------------------------- #

def _write_events(tmp_path, rows):
    cols = ["event_id", "legal_form", "org_mf", "org_rc", "org_mention",
            "event_date", "pub_date", "person_mention"]
    (tmp_path / "events.csv").write_text(
        ",".join(cols) + "\n" + "\n".join(
            ",".join(str(r.get(c, "")) for c in cols) for r in rows) + "\n",
        encoding="utf-8")


def test_only_register_listed_identifiers_are_kept(tmp_path, monkeypatch):
    """The question is about companies *in the register*. A matricule the
    gazette prints that the register does not carry is counted as such and
    left out of the answer."""
    monkeypatch.setattr(L, "PROCESSED", tmp_path)
    _write_events(tmp_path, [
        {"legal_form": "SARL", "org_mf": "1427168A", "org_mention": "ALPHA",
         "event_date": "2010-01-01"},
        {"legal_form": "SA", "org_mf": "9999999Z", "org_mention": "GHOST",
         "event_date": "2010-01-01"},
    ])
    obs, diag = L.gazette_forms({"1427168A": "B1234"})
    assert set(obs) == {"B1234"}
    assert diag["identifier_not_in_register"] == 1


def test_a_rubric_form_out_of_scope_is_not_collected(tmp_path, monkeypatch):
    """ASSOC and COOP rubrics exist. They are not SARL or SA and this stage
    is not about them."""
    monkeypatch.setattr(L, "PROCESSED", tmp_path)
    _write_events(tmp_path, [
        {"legal_form": "ASSOC", "org_mf": "1427168A", "org_mention": "AMICALE",
         "event_date": "2010-01-01"},
    ])
    obs, _diag = L.gazette_forms({"1427168A": "B1234"})
    assert obs == {}


def test_the_register_name_covers_a_company_the_gazette_never_filed_about(
        tmp_path, monkeypatch):
    monkeypatch.setattr(L, "PROCESSED", tmp_path)
    companies = {"B5555": {"rne_name_fr": "STE OMEGA SARL", "rne_name_ar": "",
                           "rne_category": "SOCIETE",
                           "rne_year_creation": "2004",
                           "rne_matricule": "555555E",
                           "rne_num_registre": "B5555"}}
    rows, diag = L.register_name_only(companies, set(), {})
    assert len(rows) == 1
    assert rows[0]["legal_form"] == "SARL"
    assert rows[0]["form_basis"] == "register_name_only"
    assert rows[0]["n_events"] == 0
    assert diag["companies"] == 1


def test_a_company_the_gazette_already_covered_is_not_added_twice(
        tmp_path, monkeypatch):
    monkeypatch.setattr(L, "PROCESSED", tmp_path)
    companies = {"B5555": {"rne_name_fr": "STE OMEGA SARL", "rne_name_ar": "",
                           "rne_category": "", "rne_year_creation": "",
                           "rne_matricule": "555555E",
                           "rne_num_registre": "B5555"}}
    rows, _d = L.register_name_only(companies, {"B5555"}, {})
    assert rows == []


def test_the_gazette_rubric_outranks_a_disagreeing_register_name(
        tmp_path, monkeypatch):
    """A rubric is the section a company actually filed under; a registered
    name is a string that may never have been amended. Where they differ the
    rubric is kept and the disagreement is recorded."""
    monkeypatch.setattr(L, "PROCESSED", tmp_path)
    companies = {"B1111": {"rne_name_fr": "ALPHA SARL", "rne_name_ar": "",
                           "rne_category": "SOCIETE", "rne_year_creation": "",
                           "rne_matricule": "111111A",
                           "rne_num_registre": "B1111"}}
    obs = {"B1111": {"forms": Counter({"SA": 6}),
                     "dated": [("2010-01-01", "SA")], "label": "ALPHA",
                     "n_events": 6, "first_seen": "2010-01-01",
                     "last_seen": "2010-01-01",
                     "identifiers": {"111111A"}}}
    rows, diag = L.build_forms(companies, obs, {}, {})
    assert rows[0]["legal_form"] == "SA"
    assert rows[0]["form_basis"] == "gazette_and_register_name_disagree"
    assert diag["register_name_disagrees"] == 1


# --- the person side ------------------------------------------------------ #

def _write_resolution(tmp_path, rows):
    cols = ["person_mention", "org_mf", "org_rc", "link_status",
            "resolved_person_id", "resolved_person_label", "resolved_org_id",
            "mention_cluster_id", "role_observed", "n_events",
            "first_event_date", "last_event_date", "issue_uid", "source_url",
            "evidence_quote"]
    with (tmp_path / "resolution.csv").open("w", encoding="utf-8",
                                            newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


CK = "B1111"
KEY_OF = {"111111A": CK, "B1111": CK}


def _forms(form="SARL"):
    return {CK: {"company_key": CK, "matricule": "111111A",
                 "num_registre": CK, "legal_form": form,
                 "rne_name_fr": "ALPHA SARL", "jort_label": "ALPHA"}}


def test_a_gazette_only_person_is_included_and_labelled(tmp_path, monkeypatch):
    """95% of this table is people the 13,630-name seed roster does not
    contain. Excluding them answers a different question; pooling them with
    seed elites hides which is which. So: included, and labelled."""
    monkeypatch.setattr(L, "PROCESSED", tmp_path)
    _write_resolution(tmp_path, [
        {"person_mention": "Slim Ben Ali", "org_mf": "111111A",
         "link_status": "unresolved", "mention_cluster_id": "PERSON_BENALI_S",
         "role_observed": "gerant", "n_events": "2"},
    ])
    rows, diag = L.company_persons(_forms(), KEY_OF, {})
    assert len(rows) == 1
    assert rows[0]["link_grade"] == "gazette_only"
    assert rows[0]["is_seed_elite"] == 0
    assert rows[0]["person_key"] == "PERSON_BENALI_S"
    assert rows[0]["role_primary"] == "gerant"
    assert diag["dyads_gazette_only"] == 1


def test_a_resolved_person_is_keyed_on_their_seed_id(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "PROCESSED", tmp_path)
    _write_resolution(tmp_path, [
        {"person_mention": "M. Slim Ben Ali", "org_mf": "111111A",
         "link_status": "resolved", "resolved_person_id": "PERSON_SEED_1",
         "resolved_person_label": "Slim BEN ALI",
         "mention_cluster_id": "PERSON_BENALI_S", "n_events": "3"},
    ])
    rows, _d = L.company_persons(_forms(), KEY_OF, {})
    assert rows[0]["person_key"] == "PERSON_SEED_1"
    assert rows[0]["is_seed_elite"] == 1
    assert rows[0]["link_grade"] == "resolved"


def test_the_strongest_grade_wins_when_one_pair_arrives_twice(
        tmp_path, monkeypatch):
    """The same person can reach one company by two routes. The pair must
    read at the best evidence available for it, not the last row seen."""
    monkeypatch.setattr(L, "PROCESSED", tmp_path)
    _write_resolution(tmp_path, [
        {"person_mention": "Slim Ben Ali", "org_mf": "111111A",
         "link_status": "inferred", "resolved_person_id": "PERSON_SEED_1",
         "resolved_person_label": "Slim BEN ALI", "n_events": "1"},
        {"person_mention": "M. Slim Ben Ali", "org_mf": "111111A",
         "link_status": "resolved", "resolved_person_id": "PERSON_SEED_1",
         "resolved_person_label": "Slim BEN ALI", "n_events": "2"},
    ])
    rows, _d = L.company_persons(_forms(), KEY_OF, {})
    assert len(rows) == 1
    assert rows[0]["link_grade"] == "resolved"
    assert rows[0]["n_events"] == 3


def test_roles_accumulate_rather_than_overwrite(tmp_path, monkeypatch):
    """gerant then liquidateur are two relationships at two times. Reducing
    them to one would throw away the more interesting of the two."""
    monkeypatch.setattr(L, "PROCESSED", tmp_path)
    _write_resolution(tmp_path, [
        {"person_mention": "Slim Ben Ali", "org_mf": "111111A",
         "link_status": "unresolved", "mention_cluster_id": "C1",
         "role_observed": "gerant", "n_events": "4"},
        {"person_mention": "Slim Ben Ali", "org_mf": "111111A",
         "link_status": "unresolved", "mention_cluster_id": "C1",
         "role_observed": "liquidateur", "n_events": "1"},
    ])
    rows, _d = L.company_persons(_forms(), KEY_OF, {})
    assert rows[0]["role_primary"] == "gerant"
    assert "liquidateur:1" in rows[0]["roles"]


def test_a_person_on_a_company_outside_the_scope_is_not_collected(
        tmp_path, monkeypatch):
    monkeypatch.setattr(L, "PROCESSED", tmp_path)
    _write_resolution(tmp_path, [
        {"person_mention": "Slim Ben Ali", "org_mf": "222222B",
         "link_status": "resolved", "resolved_person_id": "PERSON_SEED_1"},
    ])
    rows, _d = L.company_persons(_forms(), KEY_OF, {})
    assert rows == []


def test_a_row_with_no_person_is_not_a_person_link(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "PROCESSED", tmp_path)
    _write_resolution(tmp_path, [
        {"person_mention": "", "org_mf": "111111A", "link_status": "resolved"},
    ])
    rows, _d = L.company_persons(_forms(), KEY_OF, {})
    assert rows == []


def test_person_counts_are_written_back_onto_the_company(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "PROCESSED", tmp_path)
    _write_resolution(tmp_path, [
        {"person_mention": "A Ben Salah", "org_mf": "111111A",
         "link_status": "resolved", "resolved_person_id": "PERSON_SEED_1"},
        {"person_mention": "B Trabelsi", "org_mf": "111111A",
         "link_status": "unresolved", "mention_cluster_id": "C2"},
    ])
    forms = _forms()
    _rows, _d = L.company_persons(forms, KEY_OF, {})
    assert forms[CK]["n_persons"] == 2
    assert forms[CK]["n_persons_seed_elite"] == 1
    assert forms[CK]["n_persons_gazette_only"] == 1


# --- the coverage bound --------------------------------------------------- #

def test_an_absent_register_makes_the_stage_a_no_op(tmp_path, monkeypatch):
    """The register is a dependency of this stage specifically, so its
    absence must produce nothing rather than a crash or an empty claim."""
    monkeypatch.setattr(L, "PROCESSED", tmp_path)
    monkeypatch.setattr("elitenet.rne.RNE", tmp_path / "nothing")
    assert L.run() == {}


def test_undetermined_is_reported_and_is_not_an_exclusion(tmp_path,
                                                          monkeypatch):
    """The central honesty property. A register identifier with no gazette
    filing and no form in its name is UNDETERMINED. It must appear in
    `form_undetermined` and must not appear in the answer at all -- counting
    it as 'not SARL/SA' would assert something no source states."""
    rne = tmp_path / "rne"
    rne.mkdir(parents=True, exist_ok=True)
    cols = ["registres.numRegistre", "year.creation", "registres.denominationFr",
            "registres.denominationAr", "registres.nomCommercialFr",
            "registres.nomCommercialAr", "registres.categorie",
            "registres.nomAssociationFr", "registres.nomAssociationAr",
            "registres.identifiantUnique", "total"]
    with gzip.open(rne / "entreprises.csv.gz", "wt", encoding="utf-8",
                   newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerow({**{c: "" for c in cols},
                    "registres.identifiantUnique": "111111A",
                    "registres.denominationFr": "ALPHA SARL"})
        w.writerow({**{c: "" for c in cols},
                    "registres.identifiantUnique": "222222B",
                    "registres.denominationFr": "BETA HOLDING"})
    monkeypatch.setattr(L, "PROCESSED", tmp_path)
    monkeypatch.setattr("elitenet.rne.RNE", rne)
    _write_events(tmp_path, [])
    _write_resolution(tmp_path, [])
    diag = L.run()
    assert diag["companies_in_scope"] == 1          # only ALPHA SARL
    assert diag["form_undetermined"] == 1           # BETA HOLDING, unknown
    written = list(csv.DictReader(
        (tmp_path / "rne_company_forms.csv").open(encoding="utf-8")))
    assert [r["matricule"] for r in written] == ["111111A"]
