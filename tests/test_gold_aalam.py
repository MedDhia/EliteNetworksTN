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


def test_coder_columns_are_empty_in_the_drawn_sheet():
    # The sheet ships blank on purpose: a pre-filled verdict is not a verdict.
    path = GOLD / "aalam_sample_edges.csv"
    if not path.exists():
        return
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows, "sample sheet is empty"
    assert all(r["verdict"] == "" for r in rows)
    assert all(r["coder"] == "" for r in rows)
    # And the columns the pipeline fills are actually filled.
    assert all(r["evidence_quote"].strip() for r in rows)
    assert all(r["stratum"].strip() for r in rows)


def test_the_rule_pass_is_coded_in_full():
    # Seven ties in total; sampling them would tell us nothing a census does
    # not, and the rule and model passes have to be scorable separately.
    path = GOLD / "aalam_sample_edges.csv"
    if not path.exists():
        return
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert sum(1 for r in rows if r["extractor"] == "rule") == 7
