"""Unit tests for the parsing rules that silently corrupt data when wrong.

Run with:  pytest tests/ -q                       (the whole suite, as CI does)
       or: PYTHONPATH=src python tests/test_bourse_extract.py   (this file alone)
"""

from __future__ import annotations

import sys

import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bourse.entities import (
    Resolver, base_normalise, classify, demote_person_hint, trim_cell,
    has_representative, is_not_an_entity, org_key, person_key,
)
from bourse.extract.records import (
    is_category_row,
    is_footnote_legend,
    parse_mandate,
    parse_role_blob,
    split_pct,
    strip_title,
)
from bourse.extract.tables import (
    _cell_gap_threshold, _is_glue, classify_table, explode_row, find_as_of_date,
    to_number,
)

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


# --- scanned filings ------------------------------------------------------
# A third of the archive is page images. These rules are what let the ordinary
# table extractor read OCR output, so they are tested on the shapes that broke
# them: acronym board members, honorific-only cells, capacities run into names.
from bourse.extract.ocr import _text_from_words, _words_from_tsv  # noqa: E402
from bourse.extract.tables import (  # noqa: E402
    _is_caps_title,
    _roster_rows,
    classify_from_heading,
)


class _FakePage:
    """Minimal stand-in carrying positioned words, as an OCR page does."""

    def __init__(self, rows, height=800.0):
        self.words = []
        self.height = height
        for top, cells in rows:
            x = 50.0
            for cell in cells:
                for tok in cell.split():
                    self.words.append({"text": tok, "x0": x, "x1": x + 6.0 * len(tok),
                                       "top": top, "bottom": top + 9.0})
                    x += 6.0 * len(tok) + 3.0
                x += 40.0          # a column gap, wider than word spacing

    def extract_words(self, **_kw):
        return self.words


check("heading identifies a board table",
      classify_from_heading("LE CONSEIL D'ADMINISTRATION"), "board")
check("heading identifies administrators",
      classify_from_heading("ADMINISTRATEURS"), "board")
check("heading identifies named shareholders",
      classify_from_heading("PRINCIPAUX ACTIONNAIRES"), "blockholders")
check("heading identifies group participations",
      classify_from_heading("SOCIETES DU GROUPE"), "subsidiaries")
check("auditors are not a board", classify_from_heading("COMMISSAIRES AUX COMPTES"), None)
check("prose is not a heading", classify_from_heading("Le conseil s'est réuni"), None)

check("capitalised title recognised", _is_caps_title("STRUCTURE DU CAPITAL"), True)
check("sentence is not a title",
      _is_caps_title("Le conseil d'administration s'est réuni quatre fois."), False)

page = _FakePage([
    (100.0, ["M. Laroussi BAYOUDH", "Représentant l'Etat"]),
    (120.0, ["MM.", "Hédi BEN CHEIKH", "Représentant l'Etat"]),
    (140.0, ["E.T.A.P.", "représenté par son P.D.G", "M. Taïeb KAMEL"]),
    (160.0, ["Seïfeddine NAGHMOUCHI Représentant l'Etat"]),
    (180.0, ["Les propriétaires de moins de 10 actions peuvent se réunir."]),
])
rows = _roster_rows(page, 90.0, 200.0)
names = [r[0] for r in rows]
check("dotted acronym survives as a board member", "E.T.A.P." in names, True)
check("honorific-only cell folds into the name",
      any(n.startswith("MM. Hédi") for n in names), True)
check("capacity split off a name that ran into it",
      any(n == "Seïfeddine NAGHMOUCHI" for n in names), True)
check("prose is not a roster row",
      any(n.startswith("Les propriétaires") for n in names), False)

# Tesseract reports each word's own glyph box, so words without ascenders sit a
# point or two off their neighbours. Unsnapped, they bucket as separate lines.
_tsv = {
    "text": ["Laroussi", "BAYOUDH", "M."],
    "conf": [96, 95, 90],
    "left": [300, 700, 100], "top": [1000, 1000, 1006],
    "width": [300, 300, 60], "height": [30, 30, 24],
    "block_num": [1, 1, 1], "par_num": [1, 1, 1], "line_num": [1, 1, 1],
}
_w = _words_from_tsv(_tsv, 1, scale=300 / 72.0)
check("words on one printed line share a vertical position",
      len({round(w["top"], 3) for w in _w}), 1)
check("coordinates come back in points, not pixels",
      round(max(w["x1"] for w in _w)) <= 300, True)
check("a snapped line flattens to one line of text",
      _text_from_words(_w).count("\n"), 0)

_tsv_low = dict(_tsv, conf=[96, 95, 10])
check("low-confidence speckle is dropped",
      len(_words_from_tsv(_tsv_low, 1, scale=300 / 72.0)), 2)


# --- the issuer named after the operation ---------------------------------
# A prospectus is titled by its operation and names the company at the end.
# Stripping only the leading document word left the operation standing where
# the company should be, and those descriptions became firms in the network.
from bourse.pipeline import issuer_from_title  # noqa: E402

for _title, _want in [
    ("Prospectus relatif à l'augmentation de capital de la Société Tunis Re", "Tunis Re"),
    ("Prospectus relatif à l'augmentation de capital de la société Office Plast", "Office Plast"),
    ("Prospectus Abrégé relatif à l’augmentation de capital en numéraire de Total Tunisie",
     "Total Tunisie"),
    ("PROSPECTUS D'EMISSION ET D'ADMISSION EMPRUNT OBLIGATAIRE : UTL", "UTL"),
    ("PROSPECTUS D'EMISSION AUGMENTATION DE CAPITAL -UBCI", "UBCI"),
    # Titles that already name the company must come through untouched.
    ('Document de référence " UBCI 2025 "', "UBCI"),
    ("SOTUVER 2019 - actualise", "SOTUVER"),
]:
    check(f"issuer from {_title[:34]!r}", issuer_from_title(_title)[0], _want)
check("a generic title yields no issuer", issuer_from_title("Rapport Annuel")[0], None)


if __name__ == "__main__":
    if failures:
        print(f"FAILED ({len(failures)}):")
        for f in failures:
            print("  -", f)
        raise SystemExit(1)
    print("all extraction/entity tests passed")


# --------------------------------------------------------------------------
# Name cleaning upstream of entity resolution.
#
# Each of these was a live double-count or a phantom node in the first build:
# the same holder resolved to two ids and its stake was added twice, or a cell
# that named a place or a period became an actor with holdings attached.
# --------------------------------------------------------------------------


class TestRepresentedByParenthetical:
    """"<institution> (représenté par <person>)" is the institution."""

    def test_state_merges_with_its_represented_form(self):
        a = "Etat Tunisien (représenté par Monsieur Monsieur Abdessatar BEN SAAD)"
        assert org_key(a) == org_key("État Tunisien")

    def test_institution_merges_across_representative_and_acronym(self):
        a = "Kuwaït Investment Authority - KIA (représenté par Mohamed Saad AL MUNAIFI)"
        assert org_key(a) == org_key("Kuwaït Investment Authority")

    def test_accented_representative_is_detected(self):
        # The pattern is written unaccented; the filings write "représenté".
        assert has_representative("Amen Bank (représenté par M. Ben Ali)")
        assert not has_representative("Amen Bank")

    def test_person_hint_is_demoted_for_a_represented_institution(self):
        name = "Kuwaït Investment Authority - KIA (représenté par M. Al Munaifi)"
        assert demote_person_hint(name, "person") is None
        assert classify(name, hint="person") != "person"

    def test_person_hint_survives_for_an_ordinary_person(self):
        assert demote_person_hint("Hichem ELLOUMI", "person") == "person"


class TestDottedInitialism:
    """"S.A" and "SA" are one legal form, not two tokens."""

    @pytest.mark.parametrize("a,b", [
        ("Investment Trust Tunisia S.A", "Investment Trust Tunisia SA"),
        ("Financière Tunisienne S.A", "Financière Tunisienne"),
        ("Poulina Group Holding S.A.R.L", "Poulina Group Holding SARL"),
    ])
    def test_dotted_and_undotted_forms_match(self, a, b):
        assert org_key(a) == org_key(b)

    def test_distinct_firms_stay_distinct(self):
        assert org_key("COTIF SICAR") != org_key("COTIF SICAF")


class TestTrimCell:
    """What a mis-split table cell carried in beside the name."""

    @pytest.mark.parametrize("cell,want", [
        # Guillemets introduce a short name; the closing mark fell outside.
        ("Sté. Tunisienne d’Automobiles « STA", "Sté. Tunisienne d’Automobiles"),
        ("Tunisie Leasing et Factoring « TLF", "Tunisie Leasing et Factoring"),
        # A cell that is entirely a quoted short name is that name.
        ("« Serenity Capital Finance Holding » nommée en qualité",
         "Serenity Capital Finance Holding"),
        # Name column never split from the figure columns beside it.
        ("SIBTEL 46 200 100 4 620 000", "SIBTEL"),
        ("BTE – SICAR 300 000 10 3 000 000", "BTE – SICAR"),
        ("Mosbah HELALI 2 000", "Mosbah HELALI"),
    ])
    def test_run_on_material_is_removed(self, cell, want):
        assert trim_cell(cell) == want

    @pytest.mark.parametrize("cell", [
        "Usine 2", "SOTUVER 2", "AMEN BANK", "Tunisie Leasing et Factoring",
    ])
    def test_a_clean_name_is_untouched(self, cell):
        # A digit that belongs to the name has no thousands group, so it is
        # never mistaken for a figure column.
        assert trim_cell(cell) == cell

    def test_the_trimmed_form_matches_the_plain_one(self):
        r = Resolver()
        assert (r.resolve("Tunisie Leasing et Factoring « TLF", hint="firm")[0]
                == r.resolve("Tunisie Leasing et Factoring", hint="firm")[0])


class TestBulletProse:
    """Wingdings bullets survive extraction as private-use codepoints."""

    @pytest.mark.parametrize("cell", [
        " L’entrée en production de la cimenterie Carthage Cement en 2019",
        " Administrateur",
    ])
    def test_a_bulleted_sentence_is_not_an_entity(self, cell):
        # These carry corporate words, so the rule has to fire before the
        # corporate-word test rescues them.
        assert is_not_an_entity(cell)

    def test_a_real_company_still_resolves(self):
        assert not is_not_an_entity("Société Tunisienne de Banque")


class TestTickerAliases:
    """A CMF filing titled `Document de référence " HL 2018 "` is Hannibal Lease.

    The listing roster is the only thing that says so, so these guard both that
    it is consulted and that it is not over-applied.
    """

    @staticmethod
    def _resolver():
        r = Resolver()
        r.add_ticker_alias("HL", "HANNIBAL LEASE")
        r.add_ticker_alias("AB", "AMEN BANK")
        return r

    @pytest.mark.parametrize("ticker_spelling", ["HL", "H L", "H.L."])
    def test_ticker_resolves_to_the_listed_company(self, ticker_spelling):
        r = self._resolver()
        eid, _ = r.resolve(ticker_spelling, hint="firm")
        assert eid == r.resolve("HANNIBAL LEASE", hint="firm")[0]

    def test_the_company_name_wins_the_display_vote(self):
        r = self._resolver()
        eid, _ = r.resolve("HL", hint="firm")
        assert r.canonical_name(eid) == "HANNIBAL LEASE"

    def test_the_ticker_is_kept_as_an_alias(self):
        r = self._resolver()
        eid, _ = r.resolve("HL", hint="firm")
        assert "HL" in r._aliases[eid]

    def test_a_longer_name_reducing_to_a_ticker_is_left_alone(self):
        # "Ab-corporation" only becomes the key "ab" once the legal form is
        # dropped. It is not Amen Bank, and a ticker must not capture it.
        r = self._resolver()
        assert (r.resolve("Ab-corporation", hint="firm")[0]
                != r.resolve("AMEN BANK", hint="firm")[0])
        assert (r.resolve("AB CORPORATION", hint="firm")[0]
                != r.resolve("AMEN BANK", hint="firm")[0])

    def test_a_lower_case_cell_is_not_read_as_a_ticker(self):
        r = self._resolver()
        assert (r.resolve("Hl", hint="firm")[0]
                != r.resolve("HANNIBAL LEASE", hint="firm")[0])

    def test_a_name_typed_as_a_person_is_never_rewritten_to_a_ticker(self):
        # A single-token cell is demoted out of "person" before the rewrite is
        # reached, so the guard only ever bites on a name long enough to stay a
        # person - one whose initials happen to spell a ticker.
        r = self._resolver()
        r.add_ticker_alias("MBS", "MONOPRIX")
        assert (r.resolve("M B S", hint="person")[0]
                != r.resolve("MONOPRIX", hint="firm")[0])

    def test_a_ticker_equal_to_its_name_is_not_registered(self):
        r = Resolver()
        r.add_ticker_alias("ATL", "ATL")
        assert r._ticker == {}


class TestFootnoteMarkers:
    def test_trailing_footnote_digit_is_stripped(self):
        assert person_key("Moncef CHAFFAR1") == person_key("Moncef CHAFFAR")

    def test_trailing_asterisk_is_stripped(self):
        assert org_key("CTAMA*") == org_key("CTAMA")

    def test_a_short_token_keeps_its_digits(self):
        # Guard against eating real name content such as "SOTUVER 2".
        assert "2" in base_normalise("Usine 2")


class TestNotAnEntity:
    @pytest.mark.parametrize("cell", [
        "Zénith, 2eme étage",
        "2024 – 2026**",
        "Immeuble Carthage, 3ème étage",
        "12 345",
        "",
    ])
    def test_non_actors_are_rejected(self, cell):
        assert is_not_an_entity(cell)

    @pytest.mark.parametrize("name", [
        "BTK", "Amen Bank", "SOTUVER", "Mohamed Ali Elloumi",
        "Société Tunisienne de Banque", "Al Mal Investment Company",
        "Kuwaït Investment Authority", "UBCI",
    ])
    def test_real_actors_are_kept(self, name):
        assert not is_not_an_entity(name)

    @pytest.mark.parametrize("cell", [
        # An organ of a company is not a party to anything. These reached the
        # network as companies holding board seats in real firms.
        "Le Conseil d'Administration",
        "PRESIDENT DU CONSEIL D’ADMINISTRATION",
        "Directeur Général",
        "Membres du Conseil d’Administration",
        "Comité Permanent d’Audit Interne",
        "Lui-même",
        "Direction Générale",
        # A numbered governance heading, read as a row by row recovery.
        "3)Rôle de chaque organe d'administration et de direction",
        "2. Composition du conseil",
        # A mandate description rather than the name of the firm it mentions.
        "Administrateur à la Sté STIMEC - Administrateur à la Sté SIM-SICAR",
    ])
    def test_company_organs_are_not_entities(self, cell):
        assert is_not_an_entity(cell)

    @pytest.mark.parametrize("name", [
        # A leading number is also how a company can begin, so the item-number
        # strip must not swallow one.
        "1 Holding SA", "3M Tunisie",
        # Bodies whose names merely contain an organ word.
        "Groupe Chimique Tunisien", "Compagnie d'Assurances",
    ])
    def test_organ_rule_does_not_swallow_companies(self, name):
        assert not is_not_an_entity(name)

    def test_the_resolver_declines_a_non_entity(self):
        r = Resolver()
        assert r.resolve("Zénith, 2eme étage") == (None, None)
        assert r.resolve("2024 – 2026**") == (None, None)
        assert r.resolve("Le Conseil d'Administration") == (None, None)

    def test_an_override_still_wins_over_rejection(self):
        r = Resolver()
        r.overrides[base_normalise("2024 – 2026**")] = {
            "entity_id": "F0000000000", "entity_type": "firm",
            "canonical_name": "Kept by hand",
        }
        eid, etype = r.resolve("2024 – 2026**")
        assert (eid, etype) == ("F0000000000", "firm")


def cells(words_and_gaps, threshold, glue_gap=0.6):
    """Assemble a line into cells the way _page_cell_lines does."""
    words = [w for w, _ in words_and_gaps]
    gaps = [g for _, g in words_and_gaps[1:]]
    out, cur = [], words[0]
    for w, g in zip(words[1:], gaps):
        if g > threshold:
            out.append(cur)
            cur = w
        else:
            cur += ("" if _is_glue(cur, w, g, glue_gap) else " ") + w
    out.append(cur)
    return out


def split_line(words_and_gaps):
    gaps = [g for _, g in words_and_gaps[1:]]
    return cells(words_and_gaps, _cell_gap_threshold(gaps))


class TestColumnGapThreshold:
    """Where a borderless table row is cut into cells.

    The regression these pin down: on a short row the median word gap lands on
    a *column* gap, the threshold derived from it exceeds every gap on the
    line, and the row survives as one cell. Two adjacent figures then read as
    one number, so "PIRECO 750 000 750 000 3,00%" became a holding of
    750,000,750,000 shares.
    """

    # ATL 2016 p.21, measured from the PDF: a two-word name flanked by three
    # column breaks, so more than half the gaps are column gaps.
    PIRECO = [("PIRECO", 0.0), ("750", 155.2), ("000", 2.3),
              ("750", 82.2), ("000", 2.3), ("3,00%", 80.8)]
    # Same table, a row whose longer name gives the median a word gap to land
    # on; this one parsed correctly before the fix and must keep doing so.
    BNA = [("BNA", 0.0), ("2", 163.8), ("500", 2.3), ("000", 2.3),
           ("2", 75.0), ("500", 2.3), ("000", 2.3), ("10,00%", 74.5)]

    def test_the_short_row_splits_into_its_columns(self):
        assert split_line(self.PIRECO) == ["PIRECO", "750 000", "750 000", "3,00%"]

    def test_the_two_figures_are_not_glued_into_one_number(self):
        assert to_number(split_line(self.PIRECO)[1]) == 750_000

    def test_the_long_row_is_unchanged(self):
        assert split_line(self.BNA) == ["BNA", "2 500 000", "2 500 000", "10,00%"]

    def test_prose_spacing_is_not_a_column_break(self):
        # Justified body text: gaps vary, but never bimodally.
        gaps = [2.1, 2.8, 2.4, 3.3, 2.2, 2.9, 3.6, 2.5]
        assert all(g <= _cell_gap_threshold(gaps) for g in gaps)

    def test_a_jump_between_hairline_gaps_is_not_trusted(self):
        # 0.8 -> 3.2 is a fourfold step, but 3.2pt is kerning, not a column.
        assert _cell_gap_threshold([0.8, 0.9, 3.2]) >= 3.2

    def test_a_single_gap_falls_back_to_the_median_rule(self):
        assert _cell_gap_threshold([40.0]) == 40.0 * 2.2


class TestFootnoteLegends:
    """The explanatory lines printed beneath a table are not rows of it."""

    @pytest.mark.parametrize("line", [
        "* Nomme par l'AGO du 30 avril 2021",
        "** Mandats renouveles par l'AGO du 30 avril 2021",
        "*** Membre representant les petits actionnaires",
        "**** Membre independant",
        "*: Mandat renouvele par l'AGO du 20/06/2018",
        "(2) Renouvellement du mandat par l'AGO du 30 avril 2019",
        "* Personnes Morales :",
    ])
    def test_a_legend_is_not_a_row(self, line):
        assert is_footnote_legend(line)
        assert is_category_row(line)

    @pytest.mark.parametrize("name", [
        "M. Hakim DOGHRI(1)", "Meninx Holding (2)", "Amen Bank",
        "Societe Tunisienne de l'Air", "Groupe Atef BEN SLIMANE",
    ])
    def test_a_real_row_survives(self, name):
        assert not is_footnote_legend(name)
        assert not is_category_row(name)

    def test_a_bare_marker_is_not_a_legend(self):
        # Nothing follows the asterisks, so there is no sentence to reject;
        # the emptiness check in is_table_noise handles it instead.
        assert not is_footnote_legend("***")
        assert is_category_row("***")


class TestZeroWidthGapsAreNotWordBreaks:
    """A gap of zero means pdfplumber cut one token in two.

    Both rows are measured from ATL 2016 p.21. Treating the zero-width gaps as
    word spaces turned a holding of 2,666,921 shares into 2, and a stake of
    0.005% into 5%.
    """

    ENNAKL = [("ENNAKL", 0.0), ("Automobiles", 2.3), ("2", 94.6), ("6", 2.3),
              ("66", 0.0), ("921", 2.3), ("2", 75.0), ("666", 2.3),
              ("921", 2.3), ("10,67%", 74.5)]
    TANBOURA = [("Zouheir", 0.0), ("TANBOURA", 2.3), ("1", 241.3), ("3", 2.3),
                ("42", 0.0), ("1", 51.1), ("3", 2.3), ("42", 0.0),
                ("0,00", 41.2), ("5%", 0.0)]

    def test_a_figure_split_mid_number_is_rejoined(self):
        assert split_line(self.ENNAKL) == [
            "ENNAKL Automobiles", "2 666 921", "2 666 921", "10,67%"]
        assert to_number(split_line(self.ENNAKL)[1]) == 2_666_921

    def test_a_percentage_split_mid_number_is_rejoined(self):
        assert split_line(self.TANBOURA) == [
            "Zouheir TANBOURA", "1 342", "1 342", "0,005%"]
        assert to_number(split_line(self.TANBOURA)[3]) == 0.005

    def test_an_ordinary_word_space_still_separates(self):
        # The name keeps its space: 2.3pt is spacing, not a split glyph run.
        assert split_line(self.ENNAKL)[0] == "ENNAKL Automobiles"


class TestGlueNeedsDigitsOnBothSides:
    """Gap width alone cannot decide whether a hairline gap is a space.

    Measured from UNIFACTOR 2015 p.20, whose font sets a word space narrower
    than the space inside a figure: "SPDIT SICAF" is separated by 0.40pt and
    "COTIF SICAR" by -0.06pt, while "150 000" is separated by 0.93pt. An
    absolute threshold that rejoins split figures on this page also welds
    company names into COTIFSICAR. Requiring digits either side separates them.
    """

    SPDIT = [("SPDIT", 0.0), ("SICAF", 0.40), ("150", 228.65), ("000", 0.93),
             ("750", 28.53), ("000", 0.93), ("5,0%", 41.43)]
    COTIF = [("COTIF", 0.0), ("SICAR", -0.06), ("100", 227.12), ("000", 0.93),
             ("500", 28.53), ("000", 0.93), ("3,3%", 41.43)]

    def test_a_name_split_across_a_hairline_gap_keeps_its_space(self):
        assert split_line(self.SPDIT)[0] == "SPDIT SICAF"

    def test_a_name_split_across_an_overlapping_gap_keeps_its_space(self):
        assert split_line(self.COTIF)[0] == "COTIF SICAR"

    def test_the_figures_on_that_line_are_still_read_whole(self):
        assert split_line(self.COTIF)[1:] == ["100 000", "500 000", "3,3%"]

    @pytest.mark.parametrize("left,right,glued", [
        ("6", "66", True),        # a figure cut in two
        ("0,00", "5%", True),     # a percentage cut in two
        ("COTIF", "SICAR", False),
        ("SPDIT", "SICAF", False),
        ("Amen", "Bank", False),
        ("2", "SICAF", False),    # digit meeting letters is not one token
        ("CURAT", "5", False),
    ])
    def test_only_a_break_inside_a_figure_is_glue(self, left, right, glued):
        assert _is_glue(left, right, 0.0, 0.6) is glued

    def test_a_wide_gap_is_never_glue(self):
        assert not _is_glue("150", "000", 0.93, 0.6)


class TestExplodeStackedRow:
    """One ruled row that is really six rows seen column by column.

    Measured from AMEN BANK 2025 p.27, where the table's only ruling lines box
    the whole body. pdfplumber returns a single row whose every cell holds the
    column stacked with newlines, which flattens to one shareholder named
    "STE ASSURANCES COMAR STE PGI HOLDING ..." holding all six stakes at once.
    """

    STACKED = [
        "STE ASSURANCES COMAR\nSTE PGI HOLDING\nSTE ENNAKL AUTOMOBILES",
        "10 041 827\n7 123 168\n2 770 695",
        "50 209 135\n35 615 840\n13 853 475",
        "28,76%\n20,40%\n7,93%",
    ]

    def test_the_stack_becomes_one_row_per_shareholder(self):
        assert explode_row(self.STACKED) == [
            ["STE ASSURANCES COMAR", "10 041 827", "50 209 135", "28,76%"],
            ["STE PGI HOLDING", "7 123 168", "35 615 840", "20,40%"],
            ["STE ENNAKL AUTOMOBILES", "2 770 695", "13 853 475", "7,93%"],
        ]

    def test_each_holder_keeps_its_own_stake(self):
        rows = explode_row(self.STACKED)
        assert [to_number(r[3]) for r in rows] == [28.76, 20.40, 7.93]
        assert to_number(rows[1][1]) == 7_123_168

    def test_an_empty_cell_stays_empty_across_the_split(self):
        rows = explode_row(["A\nB", "", "1\n2"])
        assert rows == [["A", "", "1"], ["B", "", "2"]]

    def test_a_ragged_row_is_left_alone(self):
        # A wrapped header: two lines in one cell, one in another. Splitting
        # here would invent a row, so the row is returned untouched.
        row = ["Actionnaires", "Nombre d'actions et de\ndroits de vote"]
        assert explode_row(row) == [row]

    def test_an_ordinary_row_is_left_alone(self):
        row = ["PIRECO", "750 000", "750 000", "3,00%"]
        assert explode_row(row) == [row]

    def test_a_row_of_none_cells_survives(self):
        assert explode_row([None, None]) == [[None, None]]


class TestPostalAddressTails:
    """The last line of a registered office is not a shareholder.

    Registered offices are printed under the company name in these filings, and
    a row break can leave only the final line of one - "1053 Tunis" - standing
    where a name should be.
    """

    @pytest.mark.parametrize("line", [
        "1053 Tunis", "– 1053 Tunis", "2080 Ariana", "1002 Tunis Belvedere",
    ])
    def test_a_postcode_and_town_is_not_an_entity(self, line):
        assert is_not_an_entity(line)

    @pytest.mark.parametrize("name", [
        "2024 Holding", "3S Invest", "Amen Bank", "Tunis Re", "SIMT",
        "Poulina Group Holding", "Societe Tunisienne de Banque",
    ])
    def test_a_company_led_by_digits_survives(self, name):
        assert not is_not_an_entity(name)

    def test_the_corporate_guard_does_not_revive_a_date_range(self):
        # "2024 - 2026" carries no corporate word, so the guard leaves the
        # existing mandate-range rule to reject it.
        assert is_not_an_entity("2024 – 2026")
