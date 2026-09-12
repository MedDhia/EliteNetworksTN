"""Publication-date resolution, including the cases that actually go wrong."""
from datetime import date
from pathlib import Path

import pytest

from elitenet.calendar import find_dates, resolve_issue

FIX = Path(__file__).parent / "fixtures"


def _resolve(name, collection="annonces-legales", year=2008, issue="010"):
    return resolve_issue(collection, year, issue,
                         (FIX / name).read_text(encoding="utf-8"), "fr")


@pytest.mark.parametrize("text,expected", [
    ("1er février 2008", date(2008, 2, 1)),          # accented month, ordinal day
    ("1 juillet 2010", date(2010, 7, 1)),            # bare 1 instead of 1er
    ("- 27 avril 2010 N° 50", date(2010, 4, 27)),    # running-header form
    ("Mardi 21 dhoulhijja 1438 – 12 septembre 2017", date(2017, 9, 12)),
    ("20 juin 2017", date(2017, 6, 20)),
])
def test_gregorian_dates_parse(text, expected):
    assert find_dates(text)[0] == expected


def test_ocr_month_variants_parse():
    assert find_dates("4 jullet 2009")[0] == date(2009, 7, 4)


def test_masthead_and_headers_agreeing_gives_top_confidence():
    row = _resolve("masthead_annonces_2008_010.md")
    assert row["pub_date"] == "2008-02-01"
    assert row["date_source"] == "masthead+header"
    assert row["date_confidence"] >= 0.99
    assert row["issue_no"] == 10
    assert row["weekday_consistent"] is True


def test_weekday_arbitrates_against_a_header_majority():
    # Three running headers say 16 July; the masthead says Friday 18 July.
    # 2008-07-18 is a Friday and 2008-07-16 is a Wednesday, so the masthead wins
    # despite being outvoted.
    row = _resolve("masthead_conflict_2008_061.md", issue="061")
    assert row["pub_date"] == "2008-07-18"
    assert row["date_source"] == "masthead_weekday_arbitrated"
    assert row["needs_review"] is True


def test_sommaire_dates_are_not_mistaken_for_the_issue_date():
    # The Sommaire cites acts from 2013 and 2016; the issue is September 2017.
    row = _resolve("masthead_sommaire_trap.md", collection="journal-officiel",
                   year=2017, issue="073")
    assert row["pub_date"] == "2017-09-12"


def test_arabic_under_fr_path_is_not_given_a_date():
    row = resolve_issue("journal-officiel", 2011, "045", "نص عربي", "ar")
    assert not row.get("pub_date")
    assert row["needs_review"] is True
    assert "not French" in row["review_note"]


def test_series_ordinal_implies_the_year():
    row = _resolve("masthead_annonces_2008_010.md")
    assert row["annee_ordinal"] == 24
    assert row["annee_implied_year"] == 2008      # annonces series began 1984
    assert row["annee_consistent"] is True
