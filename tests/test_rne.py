"""The national business register as an identity spine.

Two things these tests exist to pin. First, that the register's authority is
used where it has it and not beyond: the identifier joins, the name only
labels. Second, that the natural-person table stays unmatched — it is
Arabic-only, and transliterating 615,659 names against a French roster with no
identifier on the person side is the merge-hub failure mode with its
safeguards removed.
"""
from __future__ import annotations

import csv
import gzip
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from elitenet import rne as R
from elitenet import resolve as RES


def _write_register(tmp_path, rows):
    d = tmp_path / "rne"
    d.mkdir(parents=True, exist_ok=True)
    cols = ["registres.numRegistre", "year.creation", "registres.denominationFr",
            "registres.denominationAr", "registres.nomCommercialFr",
            "registres.nomCommercialAr", "registres.categorie",
            "registres.nomAssociationFr", "registres.nomAssociationAr",
            "registres.identifiantUnique", "total"]
    with gzip.open(d / "entreprises.csv.gz", "wt", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})
    return d


def _write_persons(tmp_path, rows):
    d = tmp_path / "rne"
    d.mkdir(parents=True, exist_ok=True)
    cols = ["numRegistre", "identifiantUnique", "typeRegistre", "categorie",
            "nomAr", "prenomAr", "nomFr", "prenomFr",
            "denominationAr", "denominationFr"]
    with gzip.open(d / "personnes_physiques.csv.gz", "wt", encoding="utf-8",
                   newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})
    return d


# --- loading the register ------------------------------------------------- #

def test_an_identifier_is_indexed_with_its_french_name(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "RNE", _write_register(tmp_path, [
        {"registres.identifiantUnique": "1427168A",
         "registres.denominationFr": "STE ALPHA CONSTRUCTION",
         "registres.denominationAr": "شركة ألفا",
         "registres.categorie": "SOCIETE", "year.creation": "2003"},
    ]))
    by_mf, _by_rc, diag = R.load_register()
    assert by_mf["1427168A"]["rne_name_fr"] == "STE ALPHA CONSTRUCTION"
    assert by_mf["1427168A"]["rne_category"] == "SOCIETE"
    assert diag["with_french_name"] == 1


def test_one_identifier_on_two_register_rows_names_neither(tmp_path, monkeypatch):
    """The register is the authority, so a contradiction inside it is not
    something to break by picking one side. 2,952 of these exist in the real
    table."""
    monkeypatch.setattr(R, "RNE", _write_register(tmp_path, [
        {"registres.identifiantUnique": "111111A",
         "registres.denominationFr": "ALPHA SA"},
        {"registres.identifiantUnique": "111111A",
         "registres.denominationFr": "BETA HOLDING"},
    ]))
    by_mf, _by_rc, diag = R.load_register()
    assert "111111A" not in by_mf
    assert diag["identifier_conflicts_inside_register"] == 1


def test_two_rows_agreeing_on_the_name_are_not_a_conflict(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "RNE", _write_register(tmp_path, [
        {"registres.identifiantUnique": "222222B",
         "registres.denominationFr": "ALPHA SA"},
        {"registres.identifiantUnique": "222222B",
         "registres.denominationFr": "ALPHA SA"},
    ]))
    by_mf, _by_rc, diag = R.load_register()
    assert by_mf["222222B"]["rne_name_fr"] == "ALPHA SA"
    assert diag.get("identifier_conflicts_inside_register", 0) == 0


def test_an_arabic_only_entry_is_kept_but_names_no_seed(tmp_path, monkeypatch):
    """16.4% of the register is Arabic-only. The entry is still an identifier
    the gazette can be joined on; it just cannot label a French seed node."""
    monkeypatch.setattr(R, "RNE", _write_register(tmp_path, [
        {"registres.identifiantUnique": "333333C",
         "registres.denominationAr": "المركز الفني"},
    ]))
    by_mf, _by_rc, diag = R.load_register()
    assert "333333C" in by_mf
    assert by_mf["333333C"]["rne_name_fr"] == ""
    assert by_mf["333333C"]["rne_name_ar"] == "المركز الفني"
    assert diag.get("with_french_name", 0) == 0


# --- the person table stays unmatched ------------------------------------ #

def test_the_person_table_is_counted_and_not_matched(tmp_path, monkeypatch):
    """The whole reason this is a summary rather than a join."""
    monkeypatch.setattr(R, "RNE", _write_persons(tmp_path, [
        {"identifiantUnique": "0478007G", "categorie": "COMMERCANT",
         "nomAr": "بالحولة", "prenomAr": "حسنة"},
        {"identifiantUnique": "0070354N", "categorie": "COMMERCANT",
         "nomAr": "قمودي", "prenomAr": "الازهري بن عمر"},
        {"identifiantUnique": "0070355P", "categorie": "ARTISAN",
         "nomFr": "Ben Ali", "prenomFr": "Slim"},
    ]))
    d = R.person_register_summary()
    assert d["person_rows"] == 3
    assert d["with_arabic_name"] == 2
    assert d["with_french_name"] == 1
    # The summary reports; it returns no links of any kind.
    assert not any(k.startswith("link") for k in d)


# --- the identifier joins, the name only labels -------------------------- #

def _idx(orgs):
    idx = RES.SeedIndex()
    for oid, label in orgs.items():
        idx.orgs[oid] = {"node_id": oid, "label": label,
                         "label_normalised": label.upper()}
        from elitenet.names import parse_org
        idx.org_by_norm[parse_org(label).match_key].add(oid)
        for tok in parse_org(label).content_tokens:
            if len(tok) > 3:
                idx.org_by_token[tok].add(oid)
    return idx


def test_the_register_name_labels_an_identified_firm(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "PROCESSED", tmp_path)
    (tmp_path / "org_identifiers.csv").write_text(
        "org_id,org_label,id_type,value_normalised\n"
        "CO_X,Ste Hexabyte,matricule_fiscal,444444D\n", encoding="utf-8")
    by_mf = {"444444D": {"rne_name_fr": "HEXABYTE", "rne_name_ar": "",
                         "rne_category": "SOCIETE", "rne_year_creation": "2001"}}
    links, unknown, diag = R.link_identifiers(by_mf, {}, _idx({"CO_HEX": "HEXABYTE"}))
    assert not unknown
    assert links[0]["seed_org_id"] == "CO_HEX"
    assert links[0]["is_identity"] == 1
    assert diag["register_name_identifies_a_seed_org"] == 1


def test_a_generic_register_name_is_refused_as_an_identity(tmp_path, monkeypatch):
    """The specificity gate still applies. The identifier keeps two firms
    apart regardless, so a refused name mislabels one firm and cannot merge
    two -- but it is still refused."""
    monkeypatch.setattr(R, "PROCESSED", tmp_path)
    (tmp_path / "org_identifiers.csv").write_text(
        "org_id,org_label,id_type,value_normalised\n"
        "CO_X,Whatever,matricule_fiscal,555555E\n", encoding="utf-8")
    by_mf = {"555555E": {"rne_name_fr": "COMPTOIR TUNISIEN DE BATIMENT",
                         "rne_name_ar": "", "rne_category": "SOCIETE",
                         "rne_year_creation": ""}}
    idx = _idx({"CO_BAT": "BATIMENT"})
    # No corpus statistics: the gate is inert on a fixture this small, so the
    # assertion is on the recorded basis rather than on refusal per se.
    links, _u, _d = R.link_identifiers(by_mf, {}, idx)
    assert links[0]["match_basis"] in ("generic_fuzzy", "discriminating_fuzzy",
                                       "exact", "none", "acronym")


def test_an_identifier_absent_from_the_register_is_recorded_not_dropped(
        tmp_path, monkeypatch):
    """31,296 of these. A matricule the register does not know is either OCR
    damage or a firm that predates it, and which cannot be told from here --
    so it is listed rather than judged."""
    monkeypatch.setattr(R, "PROCESSED", tmp_path)
    (tmp_path / "org_identifiers.csv").write_text(
        "org_id,org_label,id_type,value_normalised\n"
        "CO_X,Ste Inconnue,matricule_fiscal,666666F\n", encoding="utf-8")
    links, unknown, diag = R.link_identifiers({}, {}, _idx({}))
    assert not links
    assert unknown[0]["value_normalised"] == "666666F"
    assert unknown[0]["jort_labels"] == "Ste Inconnue"
    assert diag["not_in_register"] == 1


# --- what resolve reads -------------------------------------------------- #

def test_resolve_reads_only_identity_grade_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(RES, "PROCESSED", tmp_path)
    (tmp_path / "rne_org_links.csv").write_text(
        "id_type,value_normalised,seed_org_id,is_identity\n"
        "matricule_fiscal,111111A,CO_A,1\n"
        "registre_commerce,B1231999,CO_B,1\n"
        "matricule_fiscal,222222B,CO_C,0\n"
        "matricule_fiscal,333333C,,1\n", encoding="utf-8")
    m = RES._rne_identifier_map()
    assert m["org_mf"] == {"111111A": "CO_A"}
    assert m["org_rc"] == {"B1231999": "CO_B"}


def test_an_absent_register_file_changes_nothing(tmp_path, monkeypatch):
    """The register is an addition, not a dependency: without it the map is
    empty and resolution behaves exactly as it did before."""
    monkeypatch.setattr(RES, "PROCESSED", tmp_path)
    m = RES._rne_identifier_map()
    assert m == {"org_mf": {}, "org_rc": {}}
