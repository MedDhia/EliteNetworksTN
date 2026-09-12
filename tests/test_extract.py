"""Gold-standard tests: acts transcribed by hand from the published gazette.

Each fixture is a verbatim excerpt of an issue (with its page marker), and the
expected rows were coded by reading the French text.  They cover the four
typographic eras the corpus spans, because the extraction rules are exactly
what drift between them.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eltn.extract import events_from_issue, is_person_name  # noqa: E402
from eltn.dates import parse_date, effective_date  # noqa: E402


def run(text: str, year: int = 2000):
    return events_from_issue(
        text, issue_key=f"journal-officiel/fr/{year}/001",
        year=year, issue="001", pdf_url="",
    )


# --- 1987: short-form decree, ministry heading, "charge des fonctions de" ---

JORT_1987 = """<!-- page:11 -->
# MINISTERE DE LA SANTE PUBLIQUE

## NOMINATIONS

Par décret n° 87-1260 du 27 octobre 1987 :

Mademoiselle Nour El Hayet Yeddès, administrateur général est chargé des
fonctions de directeur des affaires administratives au ministère de la santé
publique.
"""


def test_1987_charge_des_fonctions():
    ev = run(JORT_1987, 1987)
    assert len(ev) == 1
    e = ev[0]
    assert e.person_raw == "Nour El Hayet Yeddès"
    assert e.honorific == "Mademoiselle"
    assert e.event_type == "appointment"
    assert e.position_raw == "directeur des affaires administratives"
    assert e.org_raw == "ministère de la santé publique"
    assert e.act_number == "87-1260"
    assert e.act_date == dt.date(1987, 10, 27)
    assert e.authority_raw.upper().startswith("MINISTERE DE LA SANTE")


# --- 2011: "est nomme", board seat with an explicit predecessor -------------

JORT_2011 = """<!-- page:6 -->
décrets et arrêtés

# PRESIDENCE DE LA REPUBLIQUE

## NOMINATION

Par décret n° 2011-1095 du 5 août 2011.

Monsieur Ahmed Souheil Erraii, (conseiller au tribunal administratif) est
nommé conseiller auprès du Président de la République, à compter du 1er
juillet 2011.

# MINISTERE DES FINANCES

# NOMINATIONS

Par arrêté du ministre des finances du 6 août 2011.

Monsieur Nabil Ajroud est nommé administrateur représentant l'Etat au conseil
d'administration de la banque de l'habitat, et ce, en remplacement de Monsieur
Habib Toumi.
"""


def test_2011_appointment_and_board_seat():
    ev = run(JORT_2011, 2011)
    by_name = {e.person_raw: e for e in ev}

    a = by_name["Ahmed Souheil Erraii"]
    assert a.event_type == "appointment"
    assert a.position_raw == "conseiller auprès du Président de la République"
    assert a.effect_date == dt.date(2011, 7, 1)  # "a compter du", not the act date
    assert a.act_date == dt.date(2011, 8, 5)

    b = by_name["Nabil Ajroud"]
    assert b.event_type == "board"
    assert b.board_body_raw == "conseil d'administration"
    assert "banque de l'habitat" in b.org_raw
    assert b.replaces_raw == "Habib Toumi"
    assert b.act_kind == "arrete"


# --- 1968: enumerated list under one act, per-item effective dates ----------

JORT_1968 = """<!-- page:4 -->
# SECRETARIAT D'ETAT A L'INTERIEUR

## MOUVEMENT DANS LE CORPS DES CHEIKHS

Par arrêtés du Secrétaire d'État à l'Intérieur du 22 octobre 1968 :

Sont nommés Cheikhs à compter des dates suivantes :

Messieurs :

Abdedaiem Ben Nasr Ben Belgacem Taabouri, au Cheikhat de Toucha, Délégation de
Jédliane, Gouvernorat de Kasserine, à compter du 16 août 1968.

Jomaâ Ben M'hamed Ben Jomaâ Ouezred, au Cheikhat de Sadouikèche, Délégation de
Djerba, Gouvernorat de Médenine, à compter du 1er septembre 1968.
"""


def test_1968_enumerated_list():
    ev = run(JORT_1968, 1968)
    assert len(ev) == 2
    assert all(e.source_layer == "list" for e in ev)
    assert all(e.position_raw == "Cheikhs" for e in ev)
    assert ev[0].person_raw == "Abdedaiem Ben Nasr Ben Belgacem Taabouri"
    assert ev[0].effect_date == dt.date(1968, 8, 16)
    assert ev[1].effect_date == dt.date(1968, 9, 1)


# --- Recitals: "Vu le decret ... chargeant M. X" is evidence, not the act ----

JORT_RECITAL = """<!-- page:2 -->
# PRESIDENCE DU GOUVERNEMENT

Arrêté de la Cheffe du Gouvernement du 22 octobre 2021, portant délégation de
signature.

La Cheffe du Gouvernement,

Vu la loi n° 83-112 du 12 décembre 1983 portant statut général des personnels
de l'Etat,

Vu le décret gouvernemental n° 2019-593 du 12 juillet 2019, chargeant Monsieur
Amine Ben Amor, administrateur conseiller, des fonctions de directeur général
d'administration centrale à la direction générale des services communs à la
Présidence du gouvernement,

Arrête :

Article premier - une délégation est donnée à Monsieur Amine Ben Amor,
directeur général à la direction générale des services communs à la Présidence
du gouvernement à l'effet de signer au nom de la Cheffe du Gouvernement tous
les actes concernant ses attributions, et ce à compter du 11 octobre 2021.

Tunis, le 22 octobre 2021.

La Cheffe du Gouvernement
Najla Bouden Romdhane
"""


def test_recital_is_separated_from_the_operative_act():
    ev = run(JORT_RECITAL, 2021)
    layers = {e.source_layer: e for e in ev}

    assert "recital" in layers, "the cited 2019 decree should be harvested"
    r = layers["recital"]
    assert r.cited_act_number == "2019-593"
    assert r.cited_act_date == dt.date(2019, 7, 12)
    assert r.event_type == "appointment"
    assert r.effect_date == dt.date(2019, 7, 12)

    op = layers["dispositif"]
    assert op.event_type == "delegation"
    assert op.person_raw == "Amine Ben Amor"
    assert op.effect_date == dt.date(2021, 10, 11)
    assert op.signatory_name == "Najla Bouden Romdhane"
    assert "Cheffe du Gouvernement" in op.delegator_raw


# --- Termination ------------------------------------------------------------

JORT_END = """<!-- page:3 -->
# PREMIER MINISTERE

## CESSATION DE FONCTIONS

Par décret n° 89-1420 du 20 septembre 1989.

Il est mis fin aux fonctions de Monsieur Hichem Ben Soltane, rédacteur
conseiller en qualité de chargé de mission au Premier ministre, à compter du
1er octobre 1989.
"""


def test_termination():
    ev = run(JORT_END, 1989)
    assert len(ev) == 1
    e = ev[0]
    assert e.event_type == "termination"
    assert e.person_raw == "Hichem Ben Soltane"
    assert e.effect_date == dt.date(1989, 10, 1)
    assert e.section_raw.upper().startswith("CESSATION")


# --- The summary page must not produce events -------------------------------

SOMMAIRE_ONLY = """<!-- page:1 -->
# Journal Officiel de la République Tunisienne

# SOMMAIRE

# décrets et arrêtés

## Ministère des Finances

Nomination d'un administrateur au conseil d'administration de la régie des
Alcools ... 2066

Nomination de deux administrateurs au conseil d'administration de la Banque
Tuniso-Koweïtienne ... 2066
"""


def test_summary_page_yields_nothing():
    assert run(SOMMAIRE_ONLY, 2015) == []


# --- Name validation --------------------------------------------------------


@pytest.mark.parametrize("name,ok", [
    ("Ali Cherif", True),
    ("BEN CAID ES-SEBSI", True),
    ("El Hayet Yeddès", True),
    ("Bourguiba", True),
    ("de", False),
    ("Ben", False),
    ("de conférences", False),
    ("le ministre", False),
])
def test_person_name_filter(name, ok):
    assert is_person_name(name) is ok


# --- Dates ------------------------------------------------------------------


@pytest.mark.parametrize("text,expected", [
    ("5 novembre 1987", dt.date(1987, 11, 5)),
    ("1er juin 2011", dt.date(2011, 6, 1)),
    ("30 septembre 2025", dt.date(2025, 9, 30)),
    ("22 octobre 1968", dt.date(1968, 10, 22)),
    ("9 jouillet 1975", dt.date(1975, 7, 9)),   # OCR variant
    ("pas une date", None),
])
def test_parse_date(text, expected):
    assert parse_date(text) == expected


def test_effective_date_prefers_the_a_compter_clause():
    s = "est nommé directeur, et ce à compter du 1er juillet 2011."
    assert effective_date(s) == dt.date(2011, 7, 1)
