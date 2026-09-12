"""Stage 12 -- organisation identifiers and addresses.

The register prints three things beside a company name, and until now the
dataset used all three only to help it read something else:

* the **matricule fiscal** was extracted, but only as a resolution signal -- it
  fed a weight and reached no output;
* the **registre-de-commerce number** was pattern-matched only to *reject* such
  lines as company names;
* the **stated seat** was used only to detect that a headquarters had moved.

So there was no organisation attribute table of any kind. This builds two,
because the two kinds of attribute behave differently in time and conflating
them would assert something false:

* `org_identifiers.csv` is **stable**. A firm keeps its tax ID and its
  registration number, so the row is one per (organisation, kind, value), with
  the observation count and the first and last date it was seen in print.
* `org_addresses.csv` is **time-varying**. A firm moves, and there are 18,171
  `headquarters_moved` events to tie transitions to, so the row is one per
  observation, dated, with `obs_kind` separating a stated seat from a
  destination named in a transfer clause.

The identifiers also do work beyond description. A matricule is a hard
identifier, so an organisation carrying two different ones is either OCR damage
on the digits or -- the case that matters -- an organisation-resolution merge
error. That makes it the independent check on org-resolution quality the
dataset otherwise lacks, the counterpart to the merged-homonym warning on the
person side. `conflicts()` reports those, ordered so a reader can tell the two
apart: a one-digit difference is OCR, a wholly different number is a merge.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import date

from .grammar import RE_POSTAL, normalise_address
from .paths import DOCS, INTERIM, PROCESSED, ensure_dirs

FIELDS_ID = [
    "org_id", "org_label", "id_type", "value_normalised", "value_raw",
    "n_observations", "n_issues", "first_seen", "last_seen",
    "is_conflicting", "n_values_for_org", "issue_uid", "folio_page", "block_uid",
]
FIELDS_ADDR = [
    "org_id", "org_label", "address_raw", "address_normalised", "postal_code",
    "observed_date", "date_precision", "obs_kind", "n_observations",
    "first_seen", "last_seen", "issue_uid", "folio_page", "block_uid",
]

ID_TYPES = ("matricule_fiscal", "registre_commerce")
_COLUMN = {"matricule_fiscal": "org_mf", "registre_commerce": "org_rc"}


def _read(name: str) -> list[dict]:
    path = PROCESSED / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def read_events() -> list[dict]:
    """Prefer the interim JSONL, as resolve, spells and orgties all do.

    `events.csv` only exists after `export`, so reading it alone would make
    this stage silently produce nothing when run in pipeline order.
    """
    raw = INTERIM / "events_raw.jsonl"
    if raw.exists():
        with raw.open(encoding="utf-8") as fh:
            return [json.loads(line) for line in fh]
    return _read("events.csv")


def mention_to_org(resolution: list[dict]) -> tuple[dict[str, str], dict[str, str]]:
    """The mention-to-id map, minus every mention that is not unique.

    A mention resolving to more than one organisation identifies none of them.
    The same guard `tergm.org_lifecycle` applies, and for the same reason: the
    section heading "Mise a jour des statuts" is read as a firm on 87 events
    and would otherwise stamp three unrelated companies with one tax ID.
    """
    cands: dict[str, set[str]] = defaultdict(set)
    labels: dict[str, str] = {}
    for r in resolution:
        om, oid = r.get("org_mention"), r.get("resolved_org_id")
        if om and oid:
            cands[om].add(oid)
            labels[oid] = r.get("resolved_org_label") or ""
    return ({om: next(iter(ids)) for om, ids in cands.items() if len(ids) == 1},
            labels)


def _obs_date(e: dict) -> str:
    return (e.get("event_date") or e.get("pub_date") or "")


def identifiers(events: list[dict], m2o: dict[str, str],
                labels: dict[str, str]) -> tuple[list[dict], dict]:
    """One row per (organisation, identifier kind, value)."""
    agg: dict[tuple[str, str, str], dict] = {}
    diag: dict[str, int] = defaultdict(int)

    for e in events:
        oid = m2o.get(e.get("org_mention") or "")
        if not oid:
            continue
        for id_type in ID_TYPES:
            value = (e.get(_COLUMN[id_type]) or "").strip()
            if not value:
                continue
            diag[f"obs_{id_type}"] += 1
            key = (oid, id_type, value)
            d = _obs_date(e)
            row = agg.get(key)
            if row is None:
                agg[key] = {
                    "org_id": oid, "org_label": labels.get(oid, ""),
                    "id_type": id_type, "value_normalised": value,
                    "value_raw": value, "n_observations": 1,
                    "issues": {e.get("issue_uid", "")},
                    "first_seen": d, "last_seen": d,
                    "issue_uid": e.get("issue_uid", ""),
                    "folio_page": e.get("folio_page", ""),
                    "block_uid": e.get("block_uid", ""),
                }
                continue
            row["n_observations"] += 1
            row["issues"].add(e.get("issue_uid", ""))
            if d:
                if not row["first_seen"] or d < row["first_seen"]:
                    row["first_seen"] = d
                if d > row["last_seen"]:
                    row["last_seen"] = d

    # How many distinct values each organisation carries, per kind. Two is
    # already a contradiction: these are identifiers, not attributes.
    per_org: dict[tuple[str, str], int] = defaultdict(int)
    for (oid, id_type, _v) in agg:
        per_org[(oid, id_type)] += 1

    rows = []
    for (oid, id_type, _v), row in agg.items():
        n = per_org[(oid, id_type)]
        row["n_issues"] = len(row.pop("issues") - {""})
        row["n_values_for_org"] = n
        row["is_conflicting"] = int(n > 1)
        rows.append(row)
    rows.sort(key=lambda r: (r["org_id"], r["id_type"],
                             -r["n_observations"], r["value_normalised"]))
    for id_type in ID_TYPES:
        diag[f"orgs_with_{id_type}"] = len(
            {oid for (oid, t) in per_org if t == id_type})
        diag[f"conflicting_{id_type}"] = len(
            {oid for (oid, t), n in per_org.items() if t == id_type and n > 1})
    diag["identifier_rows"] = len(rows)
    return rows, dict(diag)


def addresses(events: list[dict], m2o: dict[str, str],
              labels: dict[str, str]) -> tuple[list[dict], dict]:
    """One row per distinct (organisation, address, kind), dated.

    Aggregated on the normalised address rather than the raw string: casing,
    accents and the abbreviation of the street type vary between two printings
    of the same seat, and keeping the raw strings apart would report a move
    that never happened.
    """
    agg: dict[tuple[str, str, str], dict] = {}
    diag: dict[str, int] = defaultdict(int)
    for e in events:
        oid = m2o.get(e.get("org_mention") or "")
        raw = (e.get("org_address") or "").strip()
        if not oid or not raw:
            continue
        norm = normalise_address(raw)
        if not norm:
            continue
        # The transfer clause is the only one that dates a move, so a seat
        # observed on a `headquarters_moved` event is a destination, and a seat
        # observed anywhere else is only the standing address as printed.
        kind = ("moved_to" if e.get("event_type") == "headquarters_moved"
                else "stated")
        diag[f"obs_{kind}"] += 1
        key = (oid, norm, kind)
        d = _obs_date(e)
        row = agg.get(key)
        if row is None:
            pm = RE_POSTAL.search(raw)
            agg[key] = {
                "org_id": oid, "org_label": labels.get(oid, ""),
                "address_raw": raw, "address_normalised": norm,
                "postal_code": (e.get("org_postal_code")
                                or (pm.group("code") if pm else "")),
                "observed_date": d, "date_precision": e.get("date_precision", ""),
                "obs_kind": kind, "n_observations": 1,
                "first_seen": d, "last_seen": d,
                "issue_uid": e.get("issue_uid", ""),
                "folio_page": e.get("folio_page", ""),
                "block_uid": e.get("block_uid", ""),
            }
            continue
        row["n_observations"] += 1
        if d:
            if not row["first_seen"] or d < row["first_seen"]:
                row["first_seen"] = d
                row["observed_date"] = d
            if d > row["last_seen"]:
                row["last_seen"] = d
    rows = sorted(agg.values(),
                  key=lambda r: (r["org_id"], r["first_seen"] or "9999",
                                 r["address_normalised"]))
    diag["address_rows"] = len(rows)
    diag["orgs_with_address"] = len({r["org_id"] for r in rows})
    diag["orgs_with_two_or_more_addresses"] = sum(
        1 for n in Counter(r["org_id"] for r in rows).values() if n > 1)
    return rows, dict(diag)


def _digit_distance(a: str, b: str) -> int:
    """How far apart two identifier values are, in characters.

    The point is to separate OCR damage from a resolution merge. A single
    substituted digit -- 4 for 6 is the common confusion in this OCR -- is
    almost always the same registration misread; a wholly different value is
    two firms that have been merged into one node.
    """
    if len(a) != len(b):
        return max(len(a), len(b))
    return sum(1 for x, y in zip(a, b) if x != y)


def conflicts(rows: list[dict]) -> list[dict]:
    """Organisations carrying more than one value of the same identifier.

    Classifying these on the distance between the two closest values was
    wrong, and wrong in the worst direction. `SOCIETE LE CONSEIL` carries some
    380 distinct matricules -- it is a name fragment that every firm beginning
    "Societe Le Conseil" resolves onto -- and among 380 numbers there is
    always a pair one character apart, so the most damaging merge in the
    dataset was labelled OCR damage.

    The statistic that separates the two is whether the values *cluster*. OCR
    damage produces a few variants of one number, so nearly every observation
    sits within a character of the modal value. A merge produces values with
    nothing in common, and the modal value accounts for a minority of them. So
    the test is the share of observations near the mode, and a node with many
    distinct values is a merge whatever that share looks like: a firm does not
    have five tax IDs.
    """
    by_org: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        if r["is_conflicting"]:
            by_org[(r["org_id"], r["id_type"])].append(r)
    out = []
    for (oid, id_type), group in by_org.items():
        group = sorted(group, key=lambda r: -r["n_observations"])
        vals = [g["value_normalised"] for g in group]
        counts = [g["n_observations"] for g in group]
        total = sum(counts)
        modal = vals[0]
        near = sum(n for v, n in zip(vals, counts)
                   if _digit_distance(modal, v) <= 1)
        near_share = near / total if total else 0.0
        dist = min((_digit_distance(modal, v) for v in vals[1:]), default=0)
        likely = ("ocr" if len(vals) <= 4 and near_share >= 0.8 else "merge")
        out.append({
            "org_id": oid, "org_label": group[0]["org_label"],
            "id_type": id_type, "n_values": len(group),
            "values": vals, "counts": counts,
            "n_observations": total,
            "modal_value": modal, "near_modal_share": round(near_share, 3),
            "min_distance": dist,
            "likely": likely,
            "issues": [g["issue_uid"] for g in group],
        })
    # Worst merges first. A node carrying hundreds of identifiers is hundreds
    # of firms collapsed into one, and every tie on it is wrong; an OCR pair
    # costs one value. Ordering by severity puts the actionable rows on the
    # first screen rather than five hundred lines down.
    out.sort(key=lambda c: (c["likely"] != "merge", -c["n_values"],
                            c["org_label"]))
    return out


def write_conflict_doc(cons: list[dict], diag: dict) -> None:
    merges = [c for c in cons if c["likely"] == "merge"]
    ocr = [c for c in cons if c["likely"] == "ocr"]
    worst = merges[:1]
    lines = [
        "# Organisation identifier conflicts", "",
        f"Generated {date.today().isoformat()} by `make orgattrs`.", "",
        "A matricule fiscal and a registre-de-commerce number are hard",
        "identifiers: a firm has one of each. An organisation node carrying two",
        "is therefore a defect, and there are two quite different defects here.",
        "",
        "* **A few values clustered around one** — OCR damage. This corpus",
        "  confuses 4 and 6 routinely, so `1518656` and `1518456` are one",
        "  registration read twice. The node is fine; the value needs a vote.",
        "* **Many values with nothing in common** — an organisation-resolution",
        "  **merge**. Two or more firms have been collapsed into one node, and",
        "  every tie on that node is suspect.",
        "",
        "Nothing else in the pipeline can detect the second kind, because a",
        "merge looks exactly like a well-corroborated match: both names really",
        "do appear beside the same kind of clause. That is what makes a hard",
        "identifier worth recording even when it is never used as a variable.",
        "",
        "## What this found",
        "",
        f"| kind | organisations affected |", "| --- | --- |",
    ]
    for id_type in ID_TYPES:
        n = diag.get(f"conflicting_{id_type}", 0)
        tot = diag.get(f"orgs_with_{id_type}", 0)
        share = f"{n / tot:.0%}" if tot else "—"
        lines.append(f"| {id_type} | {n} of {tot} carrying one ({share}) |")
    lines += ["",
              f"Of {len(cons)} conflicts, **{len(merges)} read as merges** and "
              f"{len(ocr)} as OCR damage.", ""]
    if worst:
        w = worst[0]
        lines += [
            "The distribution is not what a metadata problem looks like. The "
            f"worst node, **{w['org_label'] or w['org_id']}**, carries "
            f"**{w['n_values']} distinct {w['id_type'].replace('_', ' ')} "
            f"values** over {w['n_observations']} observations, with its modal "
            f"value accounting for only {w['near_modal_share']:.0%} of them. "
            "That is not one registration misread; it is a generic name "
            "fragment that every firm beginning with those words resolves "
            "onto.", "",
            "**So the dominant failure in organisation resolution is the "
            "generic-name merge, not fuzzy-match noise.** A node like that "
            "does not degrade a variable — it fabricates a hub, and any "
            "centrality computed over it is meaningless. Treat the merge rows "
            "below as a blocklist: exclude those nodes, or split them, before "
            "using organisation-level structure.", "",
            "Classifying these on the distance between the two closest values "
            "was the first attempt and it inverted the signal: among hundreds "
            "of numbers some pair is always one character apart, so the worst "
            "merges were labelled OCR. The test is instead whether the values "
            "cluster around the modal one.", "",
        ]
    lines += ["## Conflicts, worst merges first", "",
              "| organisation | identifier | values | modal share | reads as | "
              "most-observed values |",
              "| --- | --- | --- | --- | --- | --- |"]
    for c in cons[:400]:
        shown = ", ".join(f"`{v}` ({n})"
                          for v, n in list(zip(c["values"], c["counts"]))[:5])
        if c["n_values"] > 5:
            shown += f", … +{c['n_values'] - 5} more"
        lines.append(f"| {c['org_label'] or c['org_id']} | {c['id_type']} | "
                     f"{c['n_values']} | {c['near_modal_share']:.0%} | "
                     f"{c['likely']} | {shown} |")
    if len(cons) > 400:
        lines += ["",
                  f"_{len(cons) - 400} further conflicts are in "
                  "`org_identifiers.csv`, where `is_conflicting = 1`._"]
    (DOCS / "ORG-IDENTIFIER-CONFLICTS-multiplex.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")


def _write(name: str, rows: list[dict], fields: list[str]) -> None:
    path = PROCESSED / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def run() -> dict:
    ensure_dirs()
    events = read_events()
    m2o, labels = mention_to_org(_read("resolution.csv"))
    ids, d1 = identifiers(events, m2o, labels)
    addrs, d2 = addresses(events, m2o, labels)
    cons = conflicts(ids)

    _write("org_identifiers.csv", ids, FIELDS_ID)
    _write("org_addresses.csv", addrs, FIELDS_ADDR)
    write_conflict_doc(cons, d1)

    diag = {**d1, **d2, "resolved_mentions": len(m2o),
            "conflicting_orgs": len({c["org_id"] for c in cons}),
            "conflicts_reading_as_merge":
                len([c for c in cons if c["likely"] == "merge"])}
    print("organisation identifiers and addresses")
    for k in ("resolved_mentions", "obs_matricule_fiscal",
              "obs_registre_commerce", "identifier_rows",
              "orgs_with_matricule_fiscal", "orgs_with_registre_commerce",
              "conflicting_matricule_fiscal", "conflicting_registre_commerce",
              "conflicting_orgs", "conflicts_reading_as_merge",
              "obs_stated", "obs_moved_to", "address_rows",
              "orgs_with_address", "orgs_with_two_or_more_addresses"):
        if k in diag:
            print(f"  {k:<34} {diag[k]:>8,}")
    return diag


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(
        description="Build organisation identifier and address tables"
    ).parse_args(argv)
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
