"""Unit tests for the rodovid rules that silently corrupt data when wrong.

Run with:  pytest tests/ -q                       (the whole suite, as CI does)
       or: PYTHONPATH=src python -m pytest tests/test_rodovid.py -q

The build itself is checked by rebuilding and diffing in CI, which catches any
change to what the filter keeps. What that cannot catch is a rule that is wrong
in the same way before and after — so the cases below are the ones where a
plausible-looking edit changes the meaning of a table without changing its
shape: which surnames count as families, what counts as a couple, and whether
the null model still preserves degree.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rodovid import audit, build, families, paths


# --- who counts as a family ------------------------------------------------

def test_placeholders_are_not_families():
    """rodovid's unresolved link and unknown-name marker are not houses.

    Left in the person-level files, kept off the family graph, where they would
    otherwise read as one very large and entirely fictitious family.
    """
    assert not families.is_family("Personne")
    assert not families.is_family("?")
    assert not families.is_family("")
    assert not families.is_family("1892")      # no letter at all
    assert families.is_family("Belkhodja")
    assert families.is_family("Caïd Essebsi")  # accents and spaces are fine


# --- what counts as a couple ----------------------------------------------

def _tie(a, b, edge):
    return {"id_from": a, "id_to": b, "edge": edge, "from": "", "to": ""}


def test_spouses_are_a_couple_once_each_way():
    ties = [_tie("1", "2", "SPOUSE"), _tie("2", "1", "SPOUSE")]
    assert families.couples(ties) == [("1", "2")]


def test_parents_of_a_shared_child_are_a_couple():
    """The export sometimes carries the children without the marriage."""
    ties = [_tie("1", "3", "PARENT"), _tie("2", "3", "PARENT")]
    assert families.couples(ties) == [("1", "2")]


def test_a_parent_is_not_married_to_the_child():
    """The direction matters: id_from is the parent, id_to the child.

    Reading the tie the other way round would marry every parent to their own
    child and put the resulting 'alliance' on the family graph.
    """
    ties = [_tie("1", "3", "PARENT")]
    assert families.couples(ties) == []


def test_half_siblings_do_not_marry_their_parents_other_spouse():
    """Two children, two shared parents each: one couple per child, not four."""
    ties = [_tie("1", "3", "PARENT"), _tie("2", "3", "PARENT"),
            _tie("1", "4", "PARENT"), _tie("5", "4", "PARENT")]
    assert families.couples(ties) == [("1", "2"), ("1", "5")]


# --- the place signal ------------------------------------------------------

def test_foreign_scripts_are_detected_but_arabic_is_not():
    """Arabic is deliberately absent from the foreign-script list: Tunisian
    rows routinely carry the name in Arabic beside the transliteration."""
    assert build.foreign_script("Пётр Романов")
    assert build.foreign_script("Κωνσταντίνος")
    assert not build.foreign_script("محمد بن مراد")
    assert not build.foreign_script("Mohamed Ben Mrad")


def test_tunisian_and_foreign_place_vocabularies_do_not_overlap():
    """Both patterns matching one record would make the signal read 0.0 —
    'no evidence' — on the record that has the most of it."""
    for info in ("Né à Sousse", "Bey de Tunis", "Collège Sadiki", "La Marsa"):
        assert build.TUNISIAN.search(info) and not build.FOREIGN.search(info)
    for info in ("Sankt Petersburg", "Dolmabahçe", "Copenhague"):
        assert build.FOREIGN.search(info) and not build.TUNISIAN.search(info)


# --- the null model --------------------------------------------------------

def test_rewiring_preserves_every_degree():
    """The whole comparison in docs/LIMITATIONS-rodovid.md rests on this: a
    null that changed the degree sequence would not be a null for closure."""
    import collections
    import random

    edges = [("a", "b"), ("a", "c"), ("b", "c"), ("c", "d"), ("d", "e"),
             ("e", "f"), ("f", "a"), ("b", "e")]
    before = collections.Counter(n for e in edges for n in e)
    swapped = audit.rewire(edges, random.Random(0))
    after = collections.Counter(n for e in swapped for n in e)

    assert before == after
    assert len(swapped) == len(edges)
    assert all(a != b for a, b in swapped)                      # no self-loops
    assert len({tuple(sorted(e)) for e in swapped}) == len(edges)  # no doubles


def test_k_core_strips_until_nothing_is_left_to_strip():
    """A triangle with a pendant: the pendant goes, and so does the node that
    held it once it drops below k itself."""
    edges = [("a", "b"), ("b", "c"), ("a", "c"), ("c", "d")]
    assert audit.k_core(edges, 2) == {"a", "b", "c"}
    assert audit.k_core(edges, 3) == set()


# --- the committed tables --------------------------------------------------

def test_family_tables_agree_with_each_other():
    """Every allied pair is a family with a row, and the per-family marriage
    counts are the edge weights summed. Cheap, and it catches a family table
    regenerated against a stale person table."""
    with paths.FAMILY_NODES.open(encoding="utf-8") as fh:
        nodes = {r["family"]: r for r in csv.DictReader(fh)}
    with paths.FAMILY_ALLIANCES.open(encoding="utf-8") as fh:
        edges = [(r["family_a"], r["family_b"], int(r["marriages"]))
                 for r in csv.DictReader(fh)]

    marriages, allies = {}, {}
    for a, b, w in edges:
        for f, other in ((a, b), (b, a)):
            assert f in nodes, f"{f} is allied but has no family_nodes row"
            marriages[f] = marriages.get(f, 0) + w
            allies.setdefault(f, set()).add(other)

    for f, total in marriages.items():
        assert int(nodes[f]["marriages"]) == total
        assert int(nodes[f]["allies"]) == len(allies[f])
