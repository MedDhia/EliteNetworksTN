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


def test_double_issue_range_masthead_takes_the_later_bound():
    """A double issue prints a date range, and the later bound is the right one.

    "Mardi 3-Vendredi 6 Septembre 1957" covers two publication days. pub_date
    is used as an *upper bound* on when an act can have happened, so the later
    day is the conservative reading: an act dated the 5th is then correctly
    inside its own issue rather than appearing to postdate publication.
    """
    text = (
        "<!-- page:1 -->\n"
        "N° 12-13 — 75° Année\n"
        "Secrétariat d'Etat à la Présidence\n"
        "Mardi 3-Vendredi 6 Septembre 1957\n\n"
        "# JOURNAL OFFICIEL\n"
        "## Sommaire\n"
    )
    row = resolve_issue("journal-officiel", 1957, "012", text, "fr")
    assert row["pub_date"] == "1957-09-06"
    assert row["is_double_issue"] is True


def test_weekday_of_a_range_is_checked_against_the_line_that_carries_the_date():
    """Both weekdays of a range are legitimate; the schedule line is not.

    Testing only the first weekday made 574 correctly dated 1957-1995 issues
    look like weekday mismatches, because the date taken is the later bound.
    Accepting *any* weekday in the masthead would be too loose, since the
    1950s-60s masthead also advertises the publication schedule ("paraît le
    MARDI et le VENDREDI"), so the candidates come from the date's own line.
    """
    text = (
        "<!-- page:1 -->\n"
        "N° 38. — 106° Année\n"
        "Vendredi 13 - Mardi 17 Juillet 1962 (12-18 Safar 1382)\n"
        "### paraît\n"
        "### le MARDI et le VENDREDI\n"
        "## Sommaire\n"
    )
    row = resolve_issue("journal-officiel", 1962, "038", text, "fr")
    assert row["pub_date"] == "1962-07-17"        # a Tuesday
    assert row["weekday_consistent"] is True
    assert row["needs_review"] is False


def test_a_misprinted_series_ordinal_does_not_discredit_a_confirmed_date():
    """The printed "annee" is the least reliable of the three signals.

    The epoch is not constant across seventy years and the early OCR mangles
    the number: the 1957 issue prints "75" where the epoch implies about 100.
    Where the weekday confirms the date, that is a fault in the ordinal.
    """
    text = (
        "<!-- page:1 -->\n"
        "N° 40 — 75° Année\n"
        "Vendredi 4 Octobre 1957\n"
        "## Sommaire\n"
    )
    row = resolve_issue("journal-officiel", 1957, "040", text, "fr")
    assert row["pub_date"] == "1957-10-04"        # a Friday
    assert row["annee_consistent"] is False
    assert row["date_confidence"] >= 0.85, "a bad ordinal must not sink a confirmed date"


def test_a_street_named_after_a_date_is_not_a_publication_date():
    """"42, rue du 18 Janvier 1952" is the printer's address, in 752 issues.

    Masthead/header agreement absorbed all but five of them, which is exactly
    the kind of margin not to rely on: those five were dated 1952 and produced
    93 events whose act postdated its own publication.
    """
    text = (
        "<!-- page:1 -->\n"
        "N° 42 — 115° Année\n"
        "**IMPRIMERIE OFFICIELLE**\n"
        "42, rue du 18 Janvier 1952 — TUNIS\n"
        "## Sommaire\n"
    )
    row = resolve_issue("journal-officiel", 1971, "042", text, "fr")
    assert row.get("pub_date") != "1952-01-18"
    assert not row.get("pub_date"), "no masthead date should be found at all"


def test_a_date_far_from_the_directory_year_is_rejected_not_merely_doubted():
    """The directory year is the one signal not read out of OCR, so it wins.

    A year or two out is a turn-of-year issue. Thirty years out means the date
    came off something that is not the masthead, and an assertively wrong
    publication date is worse than none: it shifts every event in the issue,
    and as an upper bound it drops real acts as impossible.
    """
    text = (
        "<!-- page:1 -->\n"
        "N° 43\n"
        "Mardi 17 septembre 1996\n"
        "## Sommaire\n"
    )
    row = resolve_issue("journal-officiel", 1963, "043", text, "fr")
    assert not row.get("pub_date")
    assert row["needs_review"] is True
    assert "rejected" in row["review_note"]
