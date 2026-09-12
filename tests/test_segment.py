"""Segmentation: block boundaries, folio citations, and act anchoring."""
from pathlib import Path

from elitenet.segment import (
    repair_rubric, segment_annonces, segment_jo, strip_chrome, _rubric_table,
)

FIX = Path(__file__).parent / "fixtures"
META_A = {"issue_uid": "annonces-legales/fr/2010/050", "collection": "annonces-legales",
          "year": 2010, "issue": "050", "pub_date": "2010-04-27"}
META_J = {"issue_uid": "journal-officiel/fr/2017/073", "collection": "journal-officiel",
          "year": 2017, "issue": "073", "pub_date": "2017-09-12"}


def _annonces():
    pm = strip_chrome((FIX / "annonces_blocks.md").read_text(encoding="utf-8"))
    return segment_annonces(pm, META_A, _rubric_table())


def test_blocks_are_delimited_by_trailing_reference_codes():
    blocks, _ = _annonces()
    assert [b["ref"] for b in blocks] == ["2010G02623SANB1", "2010T02594SRLB1"]


def test_block_retains_its_full_announcement_not_just_the_tail():
    # The company name, capital and matricule open the notice and must survive:
    # trimming to a later "opener" used to discard exactly this material.
    blocks, _ = _annonces()
    first = blocks[0]["text"]
    assert "SOCIETE TUNISIA BROADCASTING" in first
    assert "1.500.000 DT" in first
    assert "MF : 1147434/Q" in first
    assert "Cyrine Ben Ali Mabrouk" in first


def test_rubric_suffix_types_the_block():
    blocks, _ = _annonces()
    assert (blocks[0]["rubric"], blocks[0]["legal_form"]) == ("SANB1", "SA")
    assert (blocks[1]["rubric"], blocks[1]["legal_form"]) == ("SRLB1", "SARL")
    assert blocks[0]["domain"] == "corporate"


def test_front_matter_is_quarantined_only_for_the_first_block():
    blocks, orphans = _annonces()
    assert len(orphans) <= 1
    assert "Sommaire" not in blocks[0]["text"]


def test_folio_page_is_recorded_before_chrome_is_stripped():
    blocks, _ = _annonces()
    # The running header on page 2 prints folio 2523.
    assert blocks[1]["folio_page_start"] == 2523
    assert "Journal Officiel de la R" not in blocks[1]["text"]


def test_ocr_damaged_rubric_is_repaired_and_flagged():
    table = _rubric_table()
    assert repair_rubric("SRUB1", table) == ("SRUB1", False)
    assert repair_rubric("RUB1", table) == ("SRUB1", True)     # dropped leading S
    assert repair_rubric("ZZZZ9", table)[0] == ""              # too far: left unmapped


def test_acts_are_split_and_anchored_to_their_ministry():
    pm = strip_chrome((FIX / "jo_acts.md").read_text(encoding="utf-8"))
    acts, _ = segment_jo(pm, META_J)
    assert len(acts) == 2
    assert acts[0]["act_number"] == "2017-124"
    assert acts[0]["ministry"].startswith("PRESIDENCE")
    assert "Sont nommés Messieurs" in acts[0]["text"]
    assert acts[1]["ministry"].startswith("MINISTERE DE L'INTERIEUR")


def test_the_verb_arrete_does_not_open_an_act():
    # "Arrête :" introduces a dispositif and occurs ~6,300 times in the window;
    # only "Arrêté du ..." / "Arrêté n° ..." is an act opener.
    pm = strip_chrome((FIX / "jo_acts.md").read_text(encoding="utf-8"))
    acts, _ = segment_jo(pm, META_J)
    assert not any(a["heading"].startswith("Arrête :") for a in acts)


def test_sommaire_entries_are_not_counted_as_acts():
    pm = strip_chrome((FIX / "jo_acts.md").read_text(encoding="utf-8"))
    acts, _ = segment_jo(pm, META_J)
    # The Sommaire repeats the 2017-124 title; it must appear once, from the body.
    assert sum(a["act_number"] == "2017-124" for a in acts) == 1
