"""Stage 5: assertions become a person register, an organisation register and
a layered edge list.

Both passes write the same assertion schema, so this stage does not care which
produced a row; it carries ``extractor`` through to every edge instead, so any
result can be recomputed with the model pass excluded.

Persons are split into ``subject`` and ``alter``. The 38 subjects are described
exhaustively, each with a whole essay; an alter appears only where the author
happened to mention them. Their degrees are therefore not comparable, and
merging the two into one undifferentiated node set would invite exactly that
comparison. The flag is the guard against it.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from functools import lru_cache

from .extract import ASSERTION_FIELDS
from .llm import open_text
from .names_ar import org_id, parse_person, person_id, transliterate
from .paths import INTERIM, PROCESSED, ensure_dirs, load_config
from .textnorm_ar import fold

PERSON_FIELDS = [
    "person_id", "name_ar", "name_translit", "is_subject", "name_kind",
    "entry_uid", "cohort", "birth_year", "death_year", "role_descriptor_ar",
    "rank", "n_assertions", "n_ties", "first_seen_entry",
]

# The book often places a person without naming them: «ابنة الأصرم»,
# «شقيق محمد باي خير الدين», «زوجته الثانية القيروانية». The tie is real -- a
# marriage happened, a brother existed -- but the node is a description, not
# an identity, and two such descriptions in different entries may well be the
# same person or different ones with no way to tell. They are kept, because
# dropping them would delete ties the source states, and marked, because
# treating them as identified individuals would overcount the population and
# invite a merge that nothing supports.
_DESCRIPTION_HEADS = (
    "شقيق", "ابن عم", "ابنة عم", "والد", "والدة", "أخو", "أخت", "زوجة",
    "زوجته", "ابنة", "ابن ", "حفيد", "عم ", "خال ", "صهر", "الأساتذة",
    "أبناء", "بنت", "أساتذة", "تلاميذ", "التلاميذ", "مخاطبي", "زملاء",
    "الزملاء", "رفقاء", "أصدقاء", "الأصدقاء",
)

# A relative clause is the other shape a description takes:
# «الأساتذة الذين ساهموا في تكوينهما», «الأساتذة القلائل الذين اختارهم والده».
# These are groups the text characterises, not people it names, and they
# entered the graph as single high-degree nodes.
_RELATIVE = (" الذين ", " الذي ", " التي ", " اللذين ")


def name_kind(name: str) -> str:
    """`described` for a node the book places only by its relation to another."""
    stripped = (name or "").strip()
    if stripped.startswith(_DESCRIPTION_HEADS):
        return "described"
    if any(r in f" {stripped} " for r in _RELATIVE):
        return "described"
    return "named"
ORG_FIELDS = ["org_id", "name_ar", "name_translit", "org_kind", "n_ties", "first_seen_entry"]
EDGE_FIELDS = [
    "edge_id", "layer", "relation", "from_id", "from_name", "to_id", "to_name",
    "to_kind", "subjects_studied", "year", "year_lo", "year_hi",
    "date_precision", "evidence_tier", "extractor", "pattern_id", "confidence",
    "entry_uid", "evidence_quote",
]


@lru_cache(maxsize=1)
def _org_aliases() -> dict[str, str]:
    """Folded surface form -> canonical name, from config.

    One body arrives under several names because the register is built from
    whatever string a sentence used. Left split, the Khaldouniyya counts as two
    smaller institutions than it is. The mapping is hand-picked rather than
    inferred: a containment rule proposes 109 pairs over 366 organisations and
    most are wrong, since التونسي is a substring of a party, a movement and a
    government. See config/aalam_org_aliases.yaml.
    """
    out: dict[str, tuple[str, str]] = {}
    for canon, spec in load_config("aalam_org_aliases")["aliases"].items():
        out[fold(canon)] = (canon, spec["kind"])
        for surface in spec["surfaces"]:
            out[fold(surface)] = (canon, spec["kind"])
    return out


def canonical_org(name: str, kind: str) -> tuple[str, str]:
    """Resolve a surface form to its canonical name *and* kind.

    Both, because identifiers are namespaced by kind: a body arriving once as
    an `association` and once as a `school` stays two nodes even after the
    names agree.
    """
    return _org_aliases().get(fold(name), (name, kind))


def _load_assertions() -> list[dict]:
    rows: list[dict] = []
    for path in (INTERIM / "assertions_rule.jsonl",
                 INTERIM / "assertions_model_verified.jsonl"):
        if path.exists():
            with path.open(encoding="utf-8") as fh:
                rows.extend(json.loads(line) for line in fh if line.strip())
    return rows


def run() -> dict[str, int]:
    ensure_dirs()
    entries_path = PROCESSED / "entries.csv"
    if not entries_path.exists():
        raise SystemExit("entries.csv missing. Run `make aalam-segment`.")
    with entries_path.open(encoding="utf-8") as fh:
        entries = list(csv.DictReader(fh))

    rows = _load_assertions()

    persons: dict[str, dict] = {}
    orgs: dict[str, dict] = {}
    counts: dict[str, int] = defaultdict(int)
    ties: dict[str, int] = defaultdict(int)

    for e in entries:
        pid = person_id(e["name_ar"])
        p = parse_person(e["name_ar"])
        persons[pid] = {
            "person_id": pid, "name_ar": e["name_ar"],
            "name_translit": transliterate(p.normalised or e["name_ar"]),
            "is_subject": "yes", "name_kind": "named",
            "entry_uid": e["entry_uid"],
            "cohort": e["cohort"], "birth_year": e["birth_year"],
            "death_year": e["death_year"],
            "role_descriptor_ar": e["role_descriptor_ar"], "rank": p.rank,
            "first_seen_entry": e["entry_uid"],
        }

    edges = []
    for r in rows:
        sid = r["subject_id"]
        if sid not in persons:
            p = parse_person(r["subject_name"])
            persons[sid] = {
                "person_id": sid, "name_ar": r["subject_name"],
                "name_translit": transliterate(p.normalised or r["subject_name"]),
                "is_subject": "no", "name_kind": name_kind(r["subject_name"]),
                "entry_uid": "", "cohort": "",
                "birth_year": "", "death_year": "", "role_descriptor_ar": "",
                "rank": p.rank, "first_seen_entry": r["entry_uid"],
            }
        counts[sid] += 1

        kind = r["counterparty_kind"]
        if kind != "person":
            canon, kind = canonical_org(r["counterparty_name"], kind)
            if (canon, kind) != (r["counterparty_name"], r["counterparty_kind"]):
                r = dict(r, counterparty_name=canon, counterparty_kind=kind,
                         counterparty_id=org_id(canon, kind.upper()))
        cid = r["counterparty_id"]
        if kind == "person":
            if cid not in persons:
                p = parse_person(r["counterparty_name"])
                persons[cid] = {
                    "person_id": cid, "name_ar": r["counterparty_name"],
                    "name_translit": transliterate(p.normalised or r["counterparty_name"]),
                    "is_subject": "no",
                    "name_kind": name_kind(r["counterparty_name"]),
                    "entry_uid": "", "cohort": "",
                    "birth_year": "", "death_year": "", "role_descriptor_ar": "",
                    "rank": p.rank, "first_seen_entry": r["entry_uid"],
                }
        elif cid not in orgs:
            orgs[cid] = {
                "org_id": cid, "name_ar": r["counterparty_name"],
                "name_translit": transliterate(r["counterparty_name"]),
                "org_kind": kind, "first_seen_entry": r["entry_uid"],
            }
        ties[sid] += 1
        ties[cid] += 1

        edges.append({
            "edge_id": r["assertion_id"].replace("AS_", "ED_"),
            "layer": r["layer"], "relation": r["relation"],
            "from_id": sid, "from_name": r["subject_name"],
            "to_id": cid, "to_name": r["counterparty_name"], "to_kind": kind,
            "subjects_studied": r.get("subjects_studied", ""),
            "year": r.get("year", ""), "year_lo": r.get("year_lo", ""),
            "year_hi": r.get("year_hi", ""),
            "date_precision": r.get("date_precision", "none"),
            # Everything here is the book speaking, never a gazette act, so the
            # tier is uniform and says so rather than implying documentary
            # confirmation the source does not provide.
            "evidence_tier": "book_stated",
            "extractor": r.get("extractor", ""), "pattern_id": r.get("pattern_id", ""),
            "confidence": r.get("confidence", ""), "entry_uid": r["entry_uid"],
            "evidence_quote": r.get("evidence_quote", ""),
        })

    for pid, p in persons.items():
        p["n_assertions"] = counts.get(pid, 0)
        p["n_ties"] = ties.get(pid, 0)
    for oid, o in orgs.items():
        o["n_ties"] = ties.get(oid, 0)

    def write(path, fields, data, key):
        data = sorted(data, key=key)
        with open_text(path, "w") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            for row in data:
                w.writerow({k: row.get(k, "") for k in fields})

    write(PROCESSED / "persons.csv", PERSON_FIELDS, persons.values(),
          lambda r: (r["is_subject"] != "yes", r["person_id"]))
    write(PROCESSED / "organisations.csv", ORG_FIELDS, orgs.values(),
          lambda r: r["org_id"])
    (PROCESSED / "edges").mkdir(parents=True, exist_ok=True)
    write(PROCESSED / "edges" / "all.csv", EDGE_FIELDS, edges,
          lambda r: (r["layer"], r["from_id"], r["to_id"], r["year"], r["edge_id"]))
    by_layer = defaultdict(list)
    for e in edges:
        by_layer[e["layer"]].append(e)
    for layer, rows_ in by_layer.items():
        write(PROCESSED / "edges" / f"{layer}.csv", EDGE_FIELDS, rows_,
              lambda r: (r["from_id"], r["to_id"], r["year"], r["edge_id"]))

    stats = {
        "persons": len(persons),
        "subjects": sum(1 for p in persons.values() if p["is_subject"] == "yes"),
        "alters": sum(1 for p in persons.values() if p["is_subject"] == "no"),
        "organisations": len(orgs), "edges": len(edges),
        "described_alters": sum(1 for p in persons.values()
                                if p.get("name_kind") == "described"),
    }
    for layer, rows_ in sorted(by_layer.items()):
        stats[f"edges_{layer}"] = len(rows_)
    for ex in ("rule", "llm"):
        stats[f"edges_{ex}"] = sum(1 for e in edges if e["extractor"] == ex)
    return stats


def main(argv=None) -> int:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    for k, v in run().items():
        print(f"  {k:22} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
