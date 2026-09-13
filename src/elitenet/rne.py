"""Stage 15 -- the national business register as an identity spine.

The Registre National des Entreprises carries the matricule fiscal and the
registre-de-commerce number as **primary keys**, not as strings parsed out of
OCR'd prose. That is a different kind of evidence from everything else in this
pipeline, and it is worth being precise about what it can and cannot do here.

What it does
------------

It names firms. 325,619 of 393,788 register entries carry a French
denomination, and 76.4% of the matricule values this pipeline scraped out of
the gazette are present in the register. So for a large share of JORT filings
the firm's *official* name is now knowable even where the printed name was
garbled beyond matching.

That is also, indirectly, how the register yields **people**. Person
resolution in this pipeline is dyad-anchored: an individual is credited only
where the organisation agrees. A filing whose firm could not be identified
gave every person in it no anchor at all. Name the firm from its matricule and
every officer named in that filing acquires one. The register reaches persons
by way of the companies they appear in, not by naming them.

What it cannot do
-----------------

**It cannot name individuals directly.** The 615,659 `personnes physiques` are
Arabic-only: **7** of them carry a French name. This pipeline is entirely
French-side, so matching that table against the seed roster would require
cross-script transliteration of hundreds of thousands of names -- exactly the
fuzzy matching that produced the merge hubs, at ten times the scale and with
no identifier on the person side to discipline it. The table is therefore
loaded and reported, and deliberately not matched.

Why the identifier makes a name match safe here
-----------------------------------------------

The register's name is used only to decide *which seed node* an already
identified firm is. The identifier does the joining; the name does the
labelling. A wrong name match therefore mislabels one firm and **cannot merge
two**, because the identifier keeps them apart -- which is the opposite of the
failure mode that produced `CO_CONSULTING` with 1,606 matricules. The match
still runs through `org_match`, so the token-specificity gate applies and a
generic-fuzzy hit is refused as an identity exactly as everywhere else.
"""
from __future__ import annotations

import argparse
import csv
import gzip
from collections import Counter, defaultdict
from pathlib import Path

from .grammar import normalise_mf, normalise_rc
from .paths import DATA, PROCESSED, ensure_dirs
from .resolve import SeedIndex, build_token_specificity, load_seed, org_match

# The register is a shared source, not a product of this build, so it sits
# beside the build directories rather than inside one. `PROCESSED` points at
# data/processed/<build>; this does not.
RNE = DATA / "processed" / "rne"

FIELDS_ORG_LINK = [
    "id_type", "value_normalised", "rne_name_fr", "rne_name_ar",
    "rne_category", "rne_year_creation", "seed_org_id", "seed_org_label",
    "match_basis", "match_score", "is_identity", "n_jort_orgs",
]
FIELDS_UNKNOWN = [
    "id_type", "value_normalised", "n_jort_orgs", "jort_labels",
]


def _read_gz(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _read(name: str) -> list[dict]:
    path = PROCESSED / name
    if path.exists():
        with path.open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))
    gz = PROCESSED / (name + ".gz")
    if gz.exists():
        with gzip.open(gz, "rt", encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))
    return []


def _write(name: str, rows: list[dict], fields: list[str]) -> None:
    path = PROCESSED / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def load_register() -> tuple[dict[str, dict], dict[str, dict], dict]:
    """(by matricule, by RC number, diagnostics) from the register.

    Keyed on the same normalisations the gazette side uses, so the two cannot
    disagree about what a matricule is. Where one identifier appears on two
    register rows with different names, neither is kept: the register is the
    authority and a contradiction inside it is not something to break by
    picking one.
    """
    diag: Counter = Counter()
    by_mf: dict[str, dict] = {}
    by_rc: dict[str, dict] = {}
    conflict_mf: set[str] = set()
    conflict_rc: set[str] = set()

    for row in _read_gz(RNE / "entreprises.csv.gz"):
        diag["register_rows"] += 1
        fr = ((row.get("registres.denominationFr") or "").strip()
              or (row.get("registres.nomCommercialFr") or "").strip()
              or (row.get("registres.nomAssociationFr") or "").strip())
        ar = ((row.get("registres.denominationAr") or "").strip()
              or (row.get("registres.nomCommercialAr") or "").strip()
              or (row.get("registres.nomAssociationAr") or "").strip())
        rec = {
            "rne_name_fr": fr, "rne_name_ar": ar,
            "rne_category": (row.get("registres.categorie") or "").strip(),
            "rne_year_creation": (row.get("year.creation") or "").strip(),
        }
        if fr:
            diag["with_french_name"] += 1
        mf = normalise_mf((row.get("registres.identifiantUnique") or "").strip())
        rc = normalise_rc((row.get("registres.numRegistre") or "").strip())
        for key, store, conflicts in ((mf, by_mf, conflict_mf),
                                      (rc, by_rc, conflict_rc)):
            if not key:
                continue
            prev = store.get(key)
            if prev is None:
                store[key] = rec
            elif prev["rne_name_fr"] != rec["rne_name_fr"]:
                # Two register rows, one identifier, two names. Picking either
                # would assert something the register itself does not.
                conflicts.add(key)
                diag["identifier_conflicts_inside_register"] += 1
    for k in conflict_mf:
        by_mf.pop(k, None)
    for k in conflict_rc:
        by_rc.pop(k, None)

    diag["identifiers_matricule"] = len(by_mf)
    diag["identifiers_rc"] = len(by_rc)
    return by_mf, by_rc, dict(diag)


def person_register_summary() -> dict:
    """What the natural-person table holds, and why it is not matched.

    Reported rather than used. 615,659 rows and 7 French names: matching this
    against a French seed roster means transliterating Arabic names at scale,
    with no identifier on the person side to discipline the result. That is
    the merge-hub failure mode with the safeguards removed, so the honest
    output is the count and the reason.
    """
    diag: Counter = Counter()
    for row in _read_gz(RNE / "personnes_physiques.csv.gz"):
        diag["person_rows"] += 1
        if ((row.get("nomFr") or "").strip() or (row.get("prenomFr") or "").strip()):
            diag["with_french_name"] += 1
        if (row.get("nomAr") or "").strip() or (row.get("prenomAr") or "").strip():
            diag["with_arabic_name"] += 1
        if (row.get("denominationFr") or "").strip():
            diag["business_named_in_french"] += 1
        diag[f"category_{(row.get('categorie') or 'none').lower()}"] += 1
    return dict(diag)


def link_identifiers(by_mf: dict[str, dict], by_rc: dict[str, dict],
                     idx: SeedIndex) -> tuple[list[dict], list[dict], dict]:
    """Match every JORT identifier against the register, and its name to a seed.

    Returns the links, the JORT identifiers the register does not know, and
    diagnostics. The second list is not a failure list: a matricule absent
    from the register is either OCR damage or a firm that predates it, and
    which of those it is cannot be told from here.
    """
    diag: Counter = Counter()
    jort: dict[tuple[str, str], set[str]] = defaultdict(set)
    labels: dict[tuple[str, str], set[str]] = defaultdict(set)
    for r in _read("org_identifiers.csv"):
        v = (r.get("value_normalised") or "").strip()
        if not v:
            continue
        key = (r.get("id_type", ""), v)
        jort[key].add(r.get("org_id", ""))
        if r.get("org_label"):
            labels[key].add(r["org_label"])

    cache: dict[str, object] = {}

    def seed_of(name: str):
        if name not in cache:
            cache[name] = org_match(name, idx)
        return cache[name]

    links: list[dict] = []
    unknown: list[dict] = []
    for (id_type, value), orgs in sorted(jort.items()):
        diag["jort_identifier_values"] += 1
        store = by_mf if id_type == "matricule_fiscal" else by_rc
        rec = store.get(value)
        if rec is None:
            diag["not_in_register"] += 1
            unknown.append({
                "id_type": id_type, "value_normalised": value,
                "n_jort_orgs": len(orgs),
                "jort_labels": " | ".join(sorted(labels[(id_type, value)])[:3]),
            })
            continue
        diag["in_register"] += 1
        m = seed_of(rec["rne_name_fr"]) if rec["rne_name_fr"] else None
        is_identity = bool(m and m.is_identity)
        if not rec["rne_name_fr"]:
            diag["register_entry_has_no_french_name"] += 1
        elif is_identity:
            diag["register_name_identifies_a_seed_org"] += 1
            diag[f"by_{m.basis}"] += 1
        else:
            diag["register_name_matches_no_seed_org"] += 1
        links.append({
            "id_type": id_type, "value_normalised": value,
            **rec,
            "seed_org_id": m.org_id if is_identity else "",
            "seed_org_label": (idx.orgs[m.org_id]["label"]
                               if is_identity and m.org_id in idx.orgs else ""),
            "match_basis": m.basis if m else "no_french_name",
            "match_score": round(m.score, 4) if m else "",
            "is_identity": int(is_identity),
            "n_jort_orgs": len(orgs),
        })
    return links, unknown, dict(diag)


def identifier_seed_map() -> dict[str, dict[str, str]]:
    """identifier value -> seed organisation, for `resolve` to start from.

    Shaped exactly like the per-column map `resolve` builds for itself, so the
    snowball's identifier bridge can be seeded with register-authoritative
    values instead of only the ones it learns from gazette text. Only
    identity-grade rows are included: the register says which firm an
    identifier belongs to, and `org_match` says whether that firm is a seed
    node, and both have to hold.
    """
    out: dict[str, dict[str, str]] = {"org_mf": {}, "org_rc": {}}
    for r in _read("rne_org_links.csv"):
        if r.get("is_identity") != "1" or not r.get("seed_org_id"):
            continue
        col = "org_mf" if r["id_type"] == "matricule_fiscal" else "org_rc"
        out[col][r["value_normalised"]] = r["seed_org_id"]
    return out


def run() -> dict:
    ensure_dirs()
    by_mf, by_rc, d_reg = load_register()
    if not by_mf and not by_rc:
        print("register not present under data/processed/rne -- nothing to do")
        return {}
    # Document frequency over the register's own French names, so the
    # specificity gate is calibrated on the corpus it is judging rather than
    # on the gazette's.
    spec = build_token_specificity(
        v["rne_name_fr"] for v in by_mf.values() if v["rne_name_fr"])
    idx = load_seed(spec)
    links, unknown, d_link = link_identifiers(by_mf, by_rc, idx)
    d_person = person_register_summary()

    _write("rne_org_links.csv", links, FIELDS_ORG_LINK)
    _write("rne_unmatched_identifiers.csv", unknown, FIELDS_UNKNOWN)

    named = sum(1 for r in links if r["is_identity"])
    diag = {**d_reg, **d_link,
            "person_rows": d_person.get("person_rows", 0),
            "person_rows_with_french_name": d_person.get("with_french_name", 0),
            "org_links_written": len(links),
            "seed_orgs_named_by_register": len(
                {r["seed_org_id"] for r in links if r["seed_org_id"]}),
            "identity_grade_links": named}
    print("national business register as an identity spine")
    for k in ("register_rows", "with_french_name", "identifiers_matricule",
              "identifiers_rc", "identifier_conflicts_inside_register",
              "jort_identifier_values", "in_register", "not_in_register",
              "register_entry_has_no_french_name",
              "register_name_identifies_a_seed_org",
              "register_name_matches_no_seed_org",
              "identity_grade_links", "seed_orgs_named_by_register",
              "person_rows", "person_rows_with_french_name"):
        if k in diag:
            print(f"  {k:<38} {diag[k]:>10,}")
    print("  -- the natural-person table is loaded and NOT matched: "
          f"{diag.get('person_rows_with_french_name', 0)} of "
          f"{diag.get('person_rows', 0)} rows carry a French name, and "
          "transliterating the rest would be the merge-hub failure mode "
          "without its safeguards")
    return diag


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(
        description="Link JORT identifiers to the national business register."
    ).parse_args(argv)
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
