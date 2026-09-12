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
    Resolver, base_normalise, classify, demote_person_hint,
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

    def test_the_resolver_declines_a_non_entity(self):
        r = Resolver()
        assert r.resolve("Zénith, 2eme étage") == (None, None)
        assert r.resolve("2024 – 2026**") == (None, None)

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
