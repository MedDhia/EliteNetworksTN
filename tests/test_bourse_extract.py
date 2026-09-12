"""Unit tests for the parsing rules that silently corrupt data when wrong.

Run with:  PYTHONPATH=src .venv/bin/python -m pytest tests -q
       or: PYTHONPATH=src .venv/bin/python tests/test_bourse_extract.py
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


if failures:
    print(f"FAILED ({len(failures)}):")
    for f in failures:
        print("  -", f)
    raise SystemExit(1)
print("all extraction/entity tests passed")
