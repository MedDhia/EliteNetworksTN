"""Unit tests for the parsing rules that silently corrupt data when wrong.

Run with:  pytest tests/ -q                       (the whole suite, as CI does)
       or: PYTHONPATH=src python tests/test_bourse_extract.py   (this file alone)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bourse.entities import Resolver, classify, org_key, person_key
from bourse.extract.records import (
    is_category_row,
    parse_mandate,
    parse_role_blob,
    split_pct,
    strip_title,
)
from bourse.extract.tables import classify_table, find_as_of_date, to_number

failures: list[str] = []


def check(label, got, want):
    if got != want:
        failures.append(f"{label}\n     got:  {got!r}\n     want: {want!r}")


# --------------------------------------------------------------------------
# French number parsing
# --------------------------------------------------------------------------
check("thousands spaces", to_number("7 800 000"), 7800000.0)
check("decimal comma", to_number("39,00"), 39.0)
check("percent sign", to_number("11,09%"), 11.09)
check("narrow nbsp", to_number("2 217 766"), 2217766.0)
check("dotted thousands", to_number("1.234.567"), 1234567.0)
check("not a number", to_number("SERENITY"), None)
check("empty", to_number(""), None)

# --------------------------------------------------------------------------
# ragged shareholder rows
# --------------------------------------------------------------------------
# Real shape from UBCI s2.4.2, where pdfplumber emits empty spacer columns.
check(
    "ragged row",
    split_pct(["SERENITY CAPITAL FINANCE HOLDING", "7 800 000", "39 000 000", "", "", "39,00%", "", ""]),
    (39.0, 7800000.0, 39000000.0),
)
check("clean row", split_pct(["MENINX HOLDING", "2 036 067", "10 180 335", "10,18%"]),
      (10.18, 2036067.0, 10180335.0))
# A count column must be excludable, or it is mistaken for a share count.
check("skip count column",
      split_pct(["Personnes Morales", "45", "12 281 013", "61 405 065", "61,400%"], skip_cols={1}),
      (61.4, 12281013.0, 61405065.0))
# No percent sign anywhere: only a fractional value may be read as a percentage.
check("no pct sign", split_pct(["X", "1 000", "5 000"]), (None, 1000.0, 5000.0))

# --------------------------------------------------------------------------
# aggregate rows must never become nodes
# --------------------------------------------------------------------------
for label in ["Total", "Public ayant au maximum 0,5 %", "Personnes Morales",
              "Ayant 3 % et plus", "1/ Participations Privés Tunisiennes",
              "Actionnaires Tunisiens", "Rompus d'actions"]:
    if not is_category_row(label):
        failures.append(f"category row not detected: {label!r}")
for label in ["SERENITY CAPITAL FINANCE HOLDING", "BOURICHA SONYA", "MENINX HOLDING"]:
    if is_category_row(label):
        failures.append(f"real holder wrongly treated as category: {label!r}")

# --------------------------------------------------------------------------
# mandate terms
# --------------------------------------------------------------------------
check("mandate full", parse_mandate("2023-2025"), (2023, 2025))
check("mandate short end", parse_mandate("2024/26"), (2024, 2026))
check("mandate single", parse_mandate("2025"), (2025, None))
check("mandate empty", parse_mandate("-"), (None, None))

# --------------------------------------------------------------------------
# role blobs -> (role, firm) pairs
# --------------------------------------------------------------------------
pairs = parse_role_blob(
    "- Président du Conseil : CARTE IARD / CARTE VIE / COTIF SICAR "
    "- Administrateur : ASKIA Assurances / COFITE SICAF"
)
check("role blob count", len(pairs), 5)
check("role blob first", pairs[0], ("Président du Conseil", "CARTE IARD"))
check("role blob last", pairs[-1], ("Administrateur", "COFITE SICAF"))

# Line breaks are flattened inside a cell, so roles run together with no
# separator; the keyword anchor must still split them.
run_on = parse_role_blob("Président Directeur Général : COFITE SICAF Directeur Général : SIDHET")
check("run-on roles", run_on,
      [("Président Directeur Général", "COFITE SICAF"), ("Directeur Général", "SIDHET")])

check("neant", parse_role_blob("Néant"), [])
check("no role label", parse_role_blob("Altea Packaging / Cogitel"),
      [(None, "Altea Packaging"), (None, "Cogitel")])
# Parenthetical sector descriptors are not part of the firm name.
check("descriptor stripped", parse_role_blob("Administrateur : Telnet (Technologie)"),
      [("Administrateur", "Telnet")])

# --------------------------------------------------------------------------
# honorifics
# --------------------------------------------------------------------------
check("title M.", strip_title("M. Hakim DOGHRI"), ("Hakim DOGHRI", "m"))
check("title Mme", strip_title("Mme Mongia CHABLY"), ("Mongia CHABLY", "mme"))
check("no title", strip_title("Meninx Holding"), ("Meninx Holding", None))

# --------------------------------------------------------------------------
# 'as of' dates
# --------------------------------------------------------------------------
check("as-of numeric", find_as_of_date("2.4.2 ... au 31/08/2025 :"), "2025-08-31")
check("as-of textual", find_as_of_date("Structure du capital au 31 décembre 2024"), "2024-12-31")
# Founding statutes must not be read as observation dates.
check("as-of implausible", find_as_of_date("loi n° 67-51 du 7 décembre 1967"), None)

# --------------------------------------------------------------------------
# table classification
# --------------------------------------------------------------------------
check("classify capital structure",
      classify_table(["ACTIONNAIRES", "Nombre d'actionnaires", "Total Actions",
                      "Montant en DT", "% du capital"], "2.4.1. Structure du capital"),
      "capital_structure")
check("classify blockholders",
      classify_table(["Actionnaires", "Nombre d'actions", "Montant en DT", "% du capital"],
                     "2.4.2. Actionnaires détenant individuellement 3% et plus"),
      "blockholders")
check("classify director holdings",
      classify_table(["Actionnaires", "Nombre d'actions", "Montant en DT", "% du capital"],
                     "2.4.3. Pourcentage détenu par les membres des organes d'administration"),
      "director_holdings")
check("classify board",
      classify_table(["Membre", "Représenté par", "Qualité", "Mandat", "Adresse"],
                     "5.1.1 Membres du Conseil d'administration"),
      "board")
check("classify interlocks",
      classify_table(["Membre", "Mandat d'administrateurs dans d'autres sociétés"],
                     "5.1.5. Mandats d'administrateurs"),
      "interlocks")
# Header words broken across a line wrap must still match.
check("classify subsidiaries wrapped",
      classify_table(["Sociétés", "Capital", "Nombre d'actions",
                      "% de Participatio n Directe", "Consolidati on"],
                     "2.5.1 Présentation des sociétés du groupe"),
      "subsidiaries")

# --------------------------------------------------------------------------
# entity resolution
# --------------------------------------------------------------------------
check("person key order-free", person_key("DOGHRI HAKIM"), person_key("M. Hakim Doghri"))
check("org key legal form", org_key("Serenity Capital Finance Holding SA"),
      org_key("SERENITY CAPITAL FINANCE HOLDING"))
# Vehicle type distinguishes siblings and must survive normalisation.
if org_key("COTIF SICAR") == org_key("COTIF SICAF"):
    failures.append("SICAR and SICAF collapsed to the same key")

check("classify state", classify("Etat Tunisien"), "state")
check("classify fund", classify("HANNIBAL SICAV"), "fund")
check("classify firm marker", classify("BNP PARIBAS IRB PARTICIPATIONS"), "firm")
check("classify person", classify("Mongia CHABLY"), "person")
check("classify aggregate", classify("Public ayant au maximum 0,5 %"), "aggregate")

r = Resolver()
a, _ = r.resolve("M. Hakim DOGHRI")
b, _ = r.resolve("DOGHRI HAKIM")
check("alias merge", a, b)
check("canonical drops honorific", r.canonical_name(a), "Hakim DOGHRI")

# Structural evidence overrides an ambiguous string.
r2 = Resolver()
r2.add_evidence("Altea Packaging", "firm")
check("evidence wins", r2.resolve("Altea Packaging")[1], "firm")
# ...but never relabels an explicit aggregate.
r3 = Resolver()
r3.add_evidence("Total", "firm")
check("aggregate protected", r3.resolve("Total")[1], "aggregate")


def test_parsing_and_entity_rules():
    """Pytest entry point.

    The checks above run at import, accumulating into ``failures``; this exposes
    them to pytest as one case. Without it the module contributes no test cases,
    a regression surfaces only as a collection error, and a green `pytest -q`
    says nothing about the bourse parsers.
    """
    assert not failures, f"{len(failures)} check(s) failed:\n" + "\n".join(
        f"  - {f}" for f in failures
    )




# ==========================================================================
# movement notices
# ==========================================================================

from bourse.extract.movements import (  # noqa: E402
    classify_event,
    find_target,
    is_plausible_party,
    parse_date,
    parse_movement,
)

# --- event typing ---------------------------------------------------------
check("classify OPA obligatoire",
      classify_event("Avis d'ouverture d'une Offre Publique d'Achat Obligatoire", "")[0],
      "opa_obligatoire")
check("classify OPR", classify_event("Offre Publique de Retrait sur les actions", "")[0],
      "opr_retrait")
check("classify augmentation",
      classify_event("Augmentation de capital par incorporation de réserves : PGH", "")[0],
      "augmentation_capital")
# A result notice states outcomes, not intentions, and must be distinguishable.
check("result flagged",
      classify_event("Résultat de l'Offre Publique d'Achat Obligatoire", "")[1], True)
check("announcement not flagged",
      classify_event("Avis d'ouverture d'une Offre Publique d'Achat", "")[1], False)

# --- dates ----------------------------------------------------------------
check("date textual", parse_date("ouverte du 05 août 2026"), "2026-08-05")
check("date 1er", parse_date("à compter du 1er janvier 2026"), "2026-01-01")
check("date numeric", parse_date("par décision du 31/07/2026"), "2026-07-31")
check("date implausible year", parse_date("la loi de 1887"), None)

# --- capital changes, across the phrasings the corpus actually uses -------
for label, text, before, after in [
    ("dinars",
     "a décidé d'augmenter le capital social de la société de 180 003 600 dinars "
     "à 189 003 780 dinars",
     180003600.0, 189003780.0),
    ("DT abbreviation",
     "augmentation de capital social de la SOPAT de 21.941.250 DT à 25.000.000 DT",
     21941250.0, 25000000.0),
    ("filler words",
     "l'augmentation en numéraire du capital social de la société de 5 218 750 dinars "
     "à 6 000 000 dinars",
     5218750.0, 6000000.0),
]:
    r = parse_movement("Augmentation de capital", text)
    check(f"capital {label}", (r.get("capital_before_tnd"), r.get("capital_after_tnd")),
          (before, after))

# A share-attribution ratio must never be read as a capital amount.
r = parse_movement(
    "Augmentation de capital",
    "augmentation de capital à attribuer gratuitement à raison d'une (1) action "
    "nouvelle pour vingt (20) actions anciennes",
)
check("ratio is not capital", r.get("capital_before_tnd"), None)

# --- offer figures --------------------------------------------------------
r = parse_movement(
    "Résultat de l'Offre Publique d'Achat Obligatoire",
    "L'opération d'Offre Publique d'Achat Obligatoire sur les actions de la société "
    "SOTUVER, au prix unitaire de 13,390 dinars, ouverte du 05 août 2026 au 26 août 2026 "
    "a été clôturée. L'initiatrice vise l'acquisition de 6 843 844 actions SOTUVER "
    "représentant 17,43% du capital de la société.",
)
check("offer price", r.get("price_tnd"), 13.39)
check("offer open", r.get("open_date"), "2026-08-05")
check("offer close", r.get("close_date"), "2026-08-26")
check("offer shares sought", r.get("shares_sought"), 6843844.0)
check("offer pct", r.get("pct_stated"), 17.43)
check("offer is result", r.get("is_result"), True)

# Six-decimal percentages occur verbatim in these notices.
r = parse_movement(
    "Résultat de l'OPA",
    "a porté sur l'acquisition de 16 204 636 actions représentant 41,280990% du capital",
)
check("six-decimal pct", r.get("pct_stated"), 41.28099)

# "aucun dépôt" is a zero result, not a missing one.
r = parse_movement("Résultat de l'OPA obligatoire",
                   "il n'y a eu aucun dépôt de pli à la Bourse en réponse à la présente OPA")
check("no deposits means zero", r.get("shares_acquired"), 0.0)

# --- parties --------------------------------------------------------------
r = parse_movement(
    "Avis d'ouverture d'une Offre Publique d'Achat Obligatoire",
    "I- Identité de l'initiateur : La société « B.A GLASS B.V » (société à "
    "responsabilité limitée de droit néerlandais) est l'initiateur de l'OPA obligatoire. "
    "II- Titres : La société « B.A GLASS B.V » a déclaré agir de concert avec le Groupe "
    "BAYAHI qui détient 16 205 315 actions représentant 41,28% du capital.",
)
check("initiator from identity section", r.get("initiators"), ["B.A GLASS B.V"])
check("concert party", r.get("concert_parties"), ["Groupe BAYAHI"])

# Fragments a greedy capture leaves behind must never become parties.
for junk in ["morales", "des personnes physiques", "30 décembre 2020",
             "durant les quatre-vingt-dix (90) jours de bourse",
             "sis à l'immeuble Yasmine Tower Bloc C", "un groupe d'actionnaires"]:
    if is_plausible_party(junk):
        failures.append(f"implausible party accepted: {junk!r}")
for real in ["B.A GLASS B.V", "Groupe BAYAHI", "BELHASSEN TRABELSI", "MEDIGRAIN"]:
    if not is_plausible_party(real):
        failures.append(f"real party rejected: {real!r}")

# --- target naming --------------------------------------------------------
check("target from quoted title",
      find_target('Résultat de l\'OPA sur les actions de la société « SOTUVER »', ""),
      "SOTUVER")
check("target from body formula",
      find_target("Résultat de l'OPA",
                  "sur les actions de la société Tunisienne de Verreries -SOTUVER-"),
      "Tunisienne de Verreries")
# The issuer's name precedes its registered office in company notices.
check("target before siege social",
      find_target("HANNIBAL LEASE",
                  "AVIS DES SOCIETES AUGMENTATION DE CAPITAL REALISEE Hannibal Lease "
                  "Siège Social : Rue du Lac Malaren"),
      "Hannibal Lease")
# The title names the target first and the initiator after; the initiator must
# not be mistaken for the company being bid for.
check("target not the initiator",
      find_target("Avis d'ouverture d'une Offre Publique d'Achat Obligatoire sur les "
                  "actions de la Société Tunisienne de Verreries -SOTUVER- initiée par "
                  "la société « B.A GLASS B.V »",
                  "Le Conseil du Marché Financier a fixé les conditions de l'Offre "
                  "Publique d'Achat obligatoire visant les actions de la Société "
                  "Tunisienne de Verreries -SOTUVER-."),
      "Tunisienne de Verreries")

# A trailing list number is layout, not part of the name. The notices run their
# numbered body straight on from the company name.
check("target trailing list number",
      find_target("Résultat de l'offre",
                  "Résultat de l'offre sur les actions de la société ADWYA 1- A partir "
                  "du mercredi 28 décembre 2022, les 20 000 000 actions sont introduites"),
      "ADWYA")



# ==========================================================================
# AGM resolutions
# ==========================================================================

from bourse.extract.resolutions import (  # noqa: E402
    classify_resolution,
    is_plausible_entity,
    meeting_info,
    parse_resolution,
    split_resolutions,
    term_end_year,
    trim_name,
)

# --- document structure ---------------------------------------------------
DOC = (
    "RESOLUTIONS ADOPTEES TUNISO-EMIRATIE SICAV "
    "Résolutions adoptées par l'Assemblée Générale Ordinaire du 21 mai 2026 "
    "Première résolution : approuve les états financiers. "
    "Cette résolution mise aux voix est adoptée à l'unanimité "
    "Cinquième résolution : l'Assemblée Générale Ordinaire ratifie la cooptation de "
    "Monsieur Yacine FRIAA en qualité d'administrateur, décidée par le conseil "
    "d’administration du 19 mai 2026, en remplacement de Monsieur Marouene Ben Slimene."
)
check("meeting kind and date", meeting_info(DOC), ("ordinaire", "2026-05-21"))
check("resolutions split", [n for n, _ in split_resolutions(DOC)], [1, 5])

# --- event typing ---------------------------------------------------------
check("classify cooptation ratified",
      classify_resolution("ratifie la cooptation de Monsieur X"), "cooptation_ratified")
check("classify renewal",
      classify_resolution("décide de renouveler le mandat de Monsieur X"), "renewal")
check("classify appointment",
      classify_resolution("décide de nommer les administrateurs suivants"), "appointment")
# A quitus resolution is a decision but not a governance one, so it yields nothing.
check("quitus is not governance",
      parse_resolution(3, "donne quitus entier aux membres du conseil d'administration"),
      None)

# --- the co-optation resolution parses whole -------------------------------
res = parse_resolution(5, split_resolutions(DOC)[1][1])
check("cooptation event type", res["event_type"], "cooptation_ratified")
check("cooptation role", res["role"], "administrateur")
check("cooptation appointee", [p["person_name_raw"] for p in res["people"]],
      ["Yacine FRIAA"])
check("cooptation predecessor", res["replaces_name_raw"], "Marouene Ben Slimene")
# The board's own decision date, written with a typographic apostrophe.
check("board decision date", res["board_decision_date"], "2026-05-19")
check("adoption status", res["adoption"], None)

# --- the outgoing person is not the appointee -----------------------------
# "prend acte du départ de M. X ... coopter M. Y en remplacement de M. X"
res = parse_resolution(4, (
    "L'Assemblée Générale prend acte du départ de M. Alain Dallard ayant la qualité "
    "d'administrateur. L'Assemblée Générale décide de ratifier la décision du conseil "
    "d’administration de coopter M. Hatem SAIGHI en remplacement de M. Alain Dallard."
))
check("departing person excluded from appointees",
      [p["person_name_raw"] for p in res["people"]], ["Hatem SAIGHI"])
check("departing person is the predecessor", res["replaces_name_raw"], "Alain Dallard")

# --- terms ----------------------------------------------------------------
check("term end year",
      term_end_year("pour une durée de trois ans expirant lors de l'assemblée générale "
                    "ordinaire qui statuera sur les états financiers de l'exercice 2023"),
      2023)

# --- legal-person seats ---------------------------------------------------
res = parse_resolution(5, (
    "L'Assemblée Générale Ordinaire décide de nommer les administrateurs suivants : "
    "La Banque Tuniso-Koweitienne - BTK représentée par Madame Rim LAKHOUA"
))
check("representative read", [p["person_name_raw"] for p in res["people"]], ["Rim LAKHOUA"])
check("seat held by a legal person", res["people"][0]["seat_holder_type"], "legal_person")

# --- name trimming --------------------------------------------------------
check("trim trailing connective", trim_name("Marouene Ben Slimene pour"),
      "Marouene Ben Slimene")
check("trim following clause", trim_name("Rim LAKHOUA La Société"), "Rim LAKHOUA")

# --- entity plausibility --------------------------------------------------
# A wrong entity becomes a node and a corporate board seat, so the test is strict.
for good in ["AMEN BANK", "Banque Tuniso-Koweitienne", "CIL", "GAPCORP FNI- FZLLC"]:
    if not is_plausible_entity(good):
        failures.append(f"real entity rejected: {good!r}")
for junk in ["décide", "de renouveler", "arrive à échéance", "Désigner",
             "L'Assemblée Générale Ordinaire nomme", "Monsieur Adel GRAR 2023 -AMEN BANK"]:
    if is_plausible_entity(junk):
        failures.append(f"fragment accepted as entity: {junk!r}")


# --- annual-report reference year -----------------------------------------
# A report is filed the year after the year it covers, so reading the covered
# year out of the document is what keeps its ties from being dated a year late.
from bourse.build_dataset import _year  # noqa: E402
from bourse.pipeline import detect_report_year  # noqa: E402

check("report year from the title line",
      detect_report_year("RAPPORT ANNUEL 2019\nSociété X", ""), 2019)
check("report year from the closing date",
      detect_report_year("États financiers de l'exercice clos le 31 décembre 2015", ""), 2015)
check("report year from a balance-sheet date",
      detect_report_year("Bilan arrêté au 31/12/2021", ""), 2021)
check("report year from the file name when the text is silent",
      detect_report_year("", "cmf_pdfs/rapport_biat_2020.pdf"), 2020)
check("no year invented", detect_report_year("", "cmf_pdfs/rapport.pdf"), None)
check("the most-mentioned year wins over the first",
      detect_report_year("Rapport annuel 2018 - comparatif. Exercice 2019. "
                         "Rapport annuel 2019. Exercice clos 2019", ""), 2019)

# _year's precedence is the point: the reference year must beat the filing date.
check("reference year beats the filing date",
      _year({"issuer_ref_year": 2019, "filing_date": "2020-06-30"}), 2019)
check("as_of beats the reference year",
      _year({"as_of": "2018-12-31", "issuer_ref_year": 2019}), 2018)
check("filing date is the last resort",
      _year({"filing_date": "2020-06-30"}), 2020)


if __name__ == "__main__":
    if failures:
        print(f"FAILED ({len(failures)}):")
        for f in failures:
            print("  -", f)
        raise SystemExit(1)
    print("all extraction/entity tests passed")
