"""Gold sampling for the A'lam Tunisiyun build.

Named apart from the other builds' test modules, as their gold code is.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aalam.gold import SEED, _allocate, _passages, _wilson

GOLD = Path(__file__).resolve().parents[1] / "gold"


def test_wilson_behaves_at_the_edges():
    # Chosen over the normal approximation because the interval has to stay
    # inside [0, 1] at small n and near certainty, which is exactly where a
    # first gold sample sits.
    p, lo, hi = _wilson(10, 10)
    assert p == 1.0 and hi <= 1.0 and lo < 1.0
    p, lo, hi = _wilson(0, 8)
    assert p == 0.0 and lo >= 0.0 and hi > 0.0
    import math
    assert all(math.isnan(v) for v in _wilson(0, 0))


def test_every_stratum_gets_at_least_one_row():
    # A layer with thirty ties rounds to zero under plain proportional
    # allocation, and its failure mode would then never be seen.
    import random
    groups = {"big": [{"_sort": str(i)} for i in range(1000)],
              "tiny": [{"_sort": "a"}, {"_sort": "b"}]}
    picked = _allocate(random.Random(SEED), groups, n=50)
    assert any(r["_sort"] in {"a", "b"} for r in picked)


def test_a_stratum_smaller_than_the_draw_is_taken_whole():
    import random
    groups = {"small": [{"_sort": str(i)} for i in range(3)]}
    picked = _allocate(random.Random(SEED), groups, n=100)
    assert len(picked) == 3


def test_the_draw_is_reproducible():
    # A reviewer has to be able to check the sample was not chosen after
    # seeing the results, which only holds if redrawing reproduces it.
    import random
    groups = {"a": [{"_sort": f"{i:03d}"} for i in range(200)]}
    first = _allocate(random.Random(SEED), groups, n=20)
    second = _allocate(random.Random(SEED), groups, n=20)
    assert [r["_sort"] for r in first] == [r["_sort"] for r in second]


def test_short_fragments_are_merged_into_a_judgeable_passage():
    # A stray page-number line is not something a coder can judge, and left
    # alone it would dilute the recall denominator with empty rows.
    text = "\n\n".join(["ا" * 400, "٣", "ب" * 400])
    out = _passages(text)
    assert len(out) == 2
    assert "٣" in out[0]


def test_every_verdict_is_attributable_and_the_sheet_is_machine_filled():
    # Written first as "the coder columns are blank", which was true only until
    # somebody coded the sheet. The invariant that actually holds either way is
    # this one: the pipeline fills its own columns on every row, and a verdict
    # never appears without a coder to answer for it.
    path = GOLD / "aalam_sample_edges.csv"
    if not path.exists():
        return
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows, "sample sheet is empty"
    assert all(r["evidence_quote"].strip() for r in rows)
    assert all(r["stratum"].strip() for r in rows)
    for r in rows:
        if r["verdict"].strip():
            assert r["coder"].strip(), f"{r['coding_id']} judged by nobody"


def test_a_coded_verdict_is_one_of_the_documented_values():
    # A typo in a verdict would silently leave the row out of the denominator.
    path = GOLD / "aalam_sample_edges.csv"
    if not path.exists():
        return
    allowed = {"correct", "wrong_relation", "wrong_direction",
               "wrong_counterparty", "wrong_subject", "spurious", "unclear", ""}
    with path.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            assert r["verdict"].strip() in allowed, r["coding_id"]


def test_passage_counts_reconcile():
    # found + missed must equal stated, or recall is computed off a denominator
    # that does not mean what the report says it means.
    path = GOLD / "aalam_sample_passages.csv"
    if not path.exists():
        return
    with path.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if not r["passage_relational"].strip():
                continue
            stated, found, missed = (int(r[k] or 0) for k in
                                     ("ties_stated", "ties_found", "ties_missed"))
            assert found + missed == stated, r["coding_id"]


def test_the_rule_pass_is_coded_in_full():
    # Seven ties in total; sampling them would tell us nothing a census does
    # not, and the rule and model passes have to be scorable separately.
    path = GOLD / "aalam_sample_edges.csv"
    if not path.exists():
        return
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert sum(1 for r in rows if r["extractor"] == "rule") == 7


# --- the draw must never destroy coding, and the check must never redraw --- #
#
# The failure these pin actually happened: CI ran `gold draw` and diffed the
# result, so every run blanked 266 coded rows and then reported the blanking as
# "the sample drifted". A coded sheet is the one artefact in this repository
# that no rebuild reproduces, so the guard is worth more than the convenience.

import pytest

from aalam import gold as G


def _sheet(tmp, name, fields, rows):
    path = tmp / name
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    return path


@pytest.fixture
def gold_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(G, "GOLD", tmp_path)
    return tmp_path


def test_the_coder_columns_are_not_part_of_the_comparison():
    # Everything a coder writes must be excluded, or verification would demand
    # that a blank redraw match a coded sheet - which is exactly the old bug.
    for _name, fields, coder_fields, _key in G.SHEETS:
        assert set(coder_fields) <= set(fields)
        for f in coder_fields:
            assert f in fields
    assert "verdict" in G.EDGE_CODER_FIELDS
    assert "ties_stated" in G.PASSAGE_CODER_FIELDS


def test_a_sheet_with_no_coding_is_not_reported_as_coded(gold_dir):
    _sheet(gold_dir, "aalam_sample_edges.csv", G.EDGE_SHEET_FIELDS,
           [{"coding_id": "E0001", "relation": "founded"}])
    assert G._coded_sheets() == []


def test_a_coded_sheet_is_detected(gold_dir):
    _sheet(gold_dir, "aalam_sample_edges.csv", G.EDGE_SHEET_FIELDS,
           [{"coding_id": "E0001", "verdict": "correct"},
            {"coding_id": "E0002", "verdict": ""}])
    coded = G._coded_sheets()
    assert [n for _p, n in coded] == [1]


def test_whitespace_is_not_coding(gold_dir):
    # A sheet of spaces is an uncoded sheet; treating it as coded would block
    # a legitimate redraw.
    _sheet(gold_dir, "aalam_sample_edges.csv", G.EDGE_SHEET_FIELDS,
           [{"coding_id": "E0001", "verdict": "   "}])
    assert G._coded_sheets() == []


def test_draw_refuses_to_overwrite_a_coded_sheet(gold_dir, monkeypatch):
    path = _sheet(gold_dir, "aalam_sample_edges.csv", G.EDGE_SHEET_FIELDS,
                  [{"coding_id": "E0001", "verdict": "correct",
                    "coder": "C1"}])
    before = path.read_bytes()
    monkeypatch.setattr(G, "_sample", lambda *a, **k: ([], [], [], {}))
    with pytest.raises(SystemExit) as e:
        G.draw()
    assert "refusing to redraw" in str(e.value)
    assert path.read_bytes() == before


def test_force_allows_a_deliberate_redraw(gold_dir, monkeypatch):
    path = _sheet(gold_dir, "aalam_sample_edges.csv", G.EDGE_SHEET_FIELDS,
                  [{"coding_id": "E0001", "verdict": "correct"}])
    monkeypatch.setattr(G, "_sample", lambda *a, **k: ([], [], [], {"n": 0}))
    G.draw(force=True)
    with path.open(encoding="utf-8") as fh:
        assert list(csv.DictReader(fh)) == []


def test_a_zero_count_is_not_confused_with_a_blank():
    # `str(0 or "")` is "", which would report every uncoded passage as drift.
    assert G._cell(0) == "0"
    assert G._cell(None) == ""
    assert G._cell("") == ""


# --- the drift ledger ------------------------------------------------------ #

def _ledger(tmp, rows):
    with (tmp / G.DRIFT_LEDGER).open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=G.DRIFT_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in G.DRIFT_FIELDS})


def _one_row_sheets(tmp, relation):
    _sheet(tmp, "aalam_sample_edges.csv", G.EDGE_SHEET_FIELDS,
           [{"coding_id": "E0001", "relation": relation, "verdict": "correct"}])
    _sheet(tmp, "aalam_sample_passages.csv", G.PASSAGE_SHEET_FIELDS, [])
    (tmp / "aalam_sample_texts.jsonl").write_text("", encoding="utf-8")


def _drawn(relation):
    return ([{"coding_id": "E0001", "relation": relation}], [], [], {})


def test_verify_passes_when_nothing_moved(gold_dir, monkeypatch):
    _one_row_sheets(gold_dir, "founded")
    monkeypatch.setattr(G, "_sample", lambda *a, **k: _drawn("founded"))
    assert G.verify()["acknowledged_drift"] == 0


def test_unledgered_drift_fails(gold_dir, monkeypatch):
    _one_row_sheets(gold_dir, "founded")
    monkeypatch.setattr(G, "_sample", lambda *a, **k: _drawn("member_of"))
    with pytest.raises(SystemExit):
        G.verify()


def test_ledgered_drift_passes_but_is_counted(gold_dir, monkeypatch):
    _one_row_sheets(gold_dir, "founded")
    _ledger(gold_dir, [{"sheet": "aalam_sample_edges.csv",
                        "coding_id": "E0001", "column": "relation",
                        "coded_value": "founded",
                        "current_value": "member_of",
                        "assessment": "known"}])
    monkeypatch.setattr(G, "_sample", lambda *a, **k: _drawn("member_of"))
    assert G.verify()["acknowledged_drift"] == 1


def test_a_row_that_moves_again_is_not_excused_by_its_ledger_entry(
        gold_dir, monkeypatch):
    # The reason the ledger pins both values: an entry describing one change
    # must not license the next one.
    _one_row_sheets(gold_dir, "founded")
    _ledger(gold_dir, [{"sheet": "aalam_sample_edges.csv",
                        "coding_id": "E0001", "column": "relation",
                        "coded_value": "founded",
                        "current_value": "member_of"}])
    monkeypatch.setattr(G, "_sample", lambda *a, **k: _drawn("taught_at"))
    with pytest.raises(SystemExit):
        G.verify()


def test_a_ledger_entry_whose_drift_is_gone_fails(gold_dir, monkeypatch):
    # Otherwise the entry rots in place and silently excuses a future change.
    _one_row_sheets(gold_dir, "founded")
    _ledger(gold_dir, [{"sheet": "aalam_sample_edges.csv",
                        "coding_id": "E0001", "column": "relation",
                        "coded_value": "founded",
                        "current_value": "member_of"}])
    monkeypatch.setattr(G, "_sample", lambda *a, **k: _drawn("founded"))
    with pytest.raises(SystemExit):
        G.verify()


def test_strict_refuses_to_pass_on_ledgered_drift(gold_dir, monkeypatch):
    _one_row_sheets(gold_dir, "founded")
    _ledger(gold_dir, [{"sheet": "aalam_sample_edges.csv",
                        "coding_id": "E0001", "column": "relation",
                        "coded_value": "founded",
                        "current_value": "member_of"}])
    monkeypatch.setattr(G, "_sample", lambda *a, **k: _drawn("member_of"))
    with pytest.raises(SystemExit):
        G.verify(strict=True)


def test_a_changed_sample_is_reported_as_a_changed_sample(gold_dir, monkeypatch):
    # Not as a column diff: which rows were drawn is the anti-cherry-picking
    # guarantee, and no ledger entry can excuse it.
    _one_row_sheets(gold_dir, "founded")
    _ledger(gold_dir, [{"sheet": "aalam_sample_edges.csv",
                        "coding_id": "E0001", "column": "relation",
                        "coded_value": "founded", "current_value": "x"}])
    monkeypatch.setattr(G, "_sample",
                        lambda *a, **k: ([{"coding_id": "E0999",
                                           "relation": "founded"}], [], [], {}))
    with pytest.raises(SystemExit):
        G.verify()


def test_verify_writes_nothing(gold_dir, monkeypatch):
    _one_row_sheets(gold_dir, "founded")
    monkeypatch.setattr(G, "_sample", lambda *a, **k: _drawn("founded"))
    before = {p.name: p.read_bytes() for p in gold_dir.iterdir()}
    G.verify()
    assert {p.name: p.read_bytes() for p in gold_dir.iterdir()} == before


# --- the committed ledger describes real, current divergence --------------- #

def test_the_committed_ledger_is_well_formed():
    path = GOLD / G.DRIFT_LEDGER
    if not path.exists():
        return
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    sheets = {n for n, _f, _c, _k in G.SHEETS}
    for r in rows:
        assert r["sheet"] in sheets, r
        assert r["coding_id"], r
        assert r["column"], r
        # Both values are required: an entry with one of them cannot tell a
        # known divergence from the next one.
        assert r["coded_value"] != r["current_value"], r
        assert r["note"].strip(), r["coding_id"]
    # No cell is pinned twice.
    keys = [(r["sheet"], r["coding_id"], r["column"]) for r in rows]
    assert len(keys) == len(set(keys))


def test_the_instructions_are_refreshed_even_when_a_redraw_is_refused(
        gold_dir, monkeypatch):
    # They are generated from the module and hold no sample data, so a change
    # to the coding rules must not need a --force redraw to be published.
    _sheet(gold_dir, "aalam_sample_edges.csv", G.EDGE_SHEET_FIELDS,
           [{"coding_id": "E0001", "verdict": "correct"}])
    monkeypatch.setattr(G, "_sample", lambda *a, **k: ([], [], [], {}))
    with pytest.raises(SystemExit):
        G.draw()
    assert (gold_dir / "AALAM_CODING_INSTRUCTIONS.md").exists()
