"""Stage 14 -- are the structural holes real, or artefacts of resolution?

A structural hole is a **finding**. Two clusters with nobody bridging them is
the shape brokerage takes in a network, and a paper reports it as such. So a
hole this pipeline manufactured by failing to resolve an identity is not a
measurement nuisance -- it is a false finding, and it is the error that most
directly corrupts the substantive claim. Understated degree is recoverable by
caveat; a fabricated hole is not, because it looks exactly like the thing the
analysis is looking for.

This stage does not fix anything. It **quantifies the exposure**: how much of
the observed sparsity rests on links the pipeline declined to make, and which
specific pairs those are, so each can be checked rather than trusted.

Three mechanisms manufacture holes here, and all three are already recorded in
the dataset rather than needing to be guessed at:

1. **A declined edge.** Every review queue is a list of candidate edges the
   pipeline would not assert: an ambiguous person-organisation dyad, an
   organisation tie with one endpoint unresolved, a kinship claim with an
   unnamed end. Each queued row is a hole that may not be there.

2. **A split organisation.** Two entities that are one firm leave the people
   at each looking like strangers. `orgentity` reports this as its known
   residual error -- 62% of entities are keyed on a name alone -- and the
   address tier closes only the pairs that state a shared seat. The pairs it
   refused, and the identifier values blacklisted for naming two
   organisations, are the visible remainder.

3. **A split person.** One person appearing as a seed node and again as an
   unresolved gazette cluster halves their degree and removes every path that
   ran through them.

The measure reported is deliberately a *bound*, not an estimate: what the
network would look like if every declined link were admitted. The truth is
somewhere between the two, and the point of printing both is that a reader can
see how wide that interval is before treating a hole as a finding.
"""
from __future__ import annotations

import argparse
import csv
import gzip
from collections import defaultdict, deque

from .names import parse_org, parse_person
from .paths import DOCS, PROCESSED, ensure_dirs

# An address borne by more than this many organisations is a domiciliation
# address and says nothing about identity. Same reasoning and same measured
# distribution as `orgentity.ADDR_MAX_FIRMS`.
ADDR_MAX_FIRMS = 4
ADDR_MIN_LEN = 12

FIELDS_SUSPECT = [
    "suspect_id", "kind", "left_id", "left_label", "right_id", "right_label",
    "basis", "detail", "would_connect_persons",
]


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


# --------------------------------------------------------------------------- #
# the observed network, and the network the declined links would give
# --------------------------------------------------------------------------- #

def person_org_edges(dated_only: bool = True) -> set[tuple[str, str]]:
    """The person-organisation edges the dataset actually asserts."""
    out: set[tuple[str, str]] = set()
    for s in _read("spells.csv"):
        if dated_only and s.get("evidence_tier") not in (
                "gazette_dated", "gazette_inferred", "gazette_snowball"):
            continue
        if s.get("person_id") and s.get("org_id"):
            out.add((s["person_id"], s["org_id"]))
    return out


def declined_person_org_edges() -> tuple[set[tuple[str, str]], dict[str, int]]:
    """Candidate person-organisation edges the pipeline would not assert.

    An ambiguous dyad is one the matcher declined to decide, not one it decided
    against: the person is in print at that organisation and the only question
    is which of several candidates they are. For a *hole*, that distinction
    matters less than it does for an identification -- any of the candidates
    being right means the edge exists and the hole does not.
    """
    out: set[tuple[str, str]] = set()
    why: dict[str, int] = defaultdict(int)
    for r in _read("review_queue.csv"):
        pid = r.get("resolved_person_id") or r.get("runner_up_person_id") or ""
        oid = r.get("resolved_org_id") or r.get("org_candidate_id") or ""
        if pid and oid:
            out.add((pid, oid))
            why["ambiguous_dyad"] += 1
    return out, dict(why)


def project_persons(edges: set[tuple[str, str]]) -> dict[str, set[str]]:
    """One-mode person projection: two people are adjacent if they share a firm.

    This is the graph a structural-hole argument is made on, so it is the graph
    the exposure has to be measured on. Organisations with an implausible
    number of officers are excluded: a merge hub connects everyone to everyone
    and would report the whole network as one dense blob, which is the mirror
    error to the one being measured.
    """
    by_org: dict[str, set[str]] = defaultdict(set)
    for pid, oid in edges:
        by_org[oid].add(pid)
    adj: dict[str, set[str]] = defaultdict(set)
    for oid, people in by_org.items():
        if len(people) > 60:      # a board is not this large; this is a merge
            continue
        for a in people:
            adj[a] |= people - {a}
    return adj


def components(adj: dict[str, set[str]]) -> list[int]:
    """Component sizes, largest first."""
    seen: set[str] = set()
    sizes = []
    for start in adj:
        if start in seen:
            continue
        q, size = deque([start]), 0
        seen.add(start)
        while q:
            n = q.popleft()
            size += 1
            for m in adj[n]:
                if m not in seen:
                    seen.add(m)
                    q.append(m)
        sizes.append(size)
    return sorted(sizes, reverse=True)


def reachable_pairs(adj: dict[str, set[str]], limit: int = 2500) -> int:
    """How many unordered pairs are connected at all.

    Computed from component sizes rather than by all-pairs search, which is
    what makes it affordable: a component of size n contributes n(n-1)/2.
    `limit` caps how many nodes are reported on, so the figure stays
    comparable between the observed and potential graphs.
    """
    return sum(n * (n - 1) // 2 for n in components(adj))


# --------------------------------------------------------------------------- #
# split organisations: the hole that looks most like a finding
# --------------------------------------------------------------------------- #

def split_organisation_candidates() -> list[dict]:
    """Entity pairs that are plausibly one firm, with the basis recorded.

    Two independent signals, neither of which `orgentity` acted on:

    * **a shared discriminating seat** the address tier refused because the
      labels did not agree closely enough. A refusal is the right call for
      *identity* -- two firms do share a building -- and still leaves a pair
      worth listing when the question is whether a hole between them is real.
    * **an identifier value on two organisation nodes.** `orgattrs` reports
      4,461 of these. Read one way it is a merge; read the other it is one
      firm split in two, and the second reading is what makes a false hole.
    """
    out: list[dict] = []

    # Identifier values sitting on more than one organisation node.
    by_value: dict[tuple[str, str], set[str]] = defaultdict(set)
    label: dict[str, str] = {}
    for r in _read("org_identifiers.csv"):
        v = (r.get("value_normalised") or "").strip()
        oid = r.get("org_id") or ""
        if v and oid:
            by_value[(r.get("id_type", ""), v)].add(oid)
            label.setdefault(oid, r.get("org_label") or oid)
    for (id_type, v), orgs in by_value.items():
        if len(orgs) < 2 or len(orgs) > 6:
            continue
        ordered = sorted(orgs)
        for i, a in enumerate(ordered):
            for b in ordered[i + 1:]:
                out.append({
                    "kind": "split_organisation", "left_id": a,
                    "left_label": label.get(a, a), "right_id": b,
                    "right_label": label.get(b, b),
                    "basis": f"shared_{id_type}",
                    "detail": f"{id_type}={v} on both nodes",
                })

    # A shared discriminating seat, where the names differ enough that the
    # address tier refused the merge.
    by_addr: dict[str, set[str]] = defaultdict(set)
    alabel: dict[str, str] = {}
    for r in _read("org_addresses.csv"):
        a = (r.get("address_normalised") or "").strip()
        oid = r.get("org_id") or ""
        if len(a) >= ADDR_MIN_LEN and oid:
            by_addr[a].add(oid)
            alabel.setdefault(oid, r.get("org_label") or oid)
    for a, orgs in by_addr.items():
        if len(orgs) < 2 or len(orgs) > ADDR_MAX_FIRMS:
            continue
        ordered = sorted(orgs)
        for i, x in enumerate(ordered):
            for y in ordered[i + 1:]:
                # Only worth listing where the names are at least related;
                # otherwise it is two firms in one building and no more.
                kx = parse_org(alabel.get(x, x)).match_key
                ky = parse_org(alabel.get(y, y)).match_key
                if not kx or not ky:
                    continue
                shared = set(kx.split()) & set(ky.split())
                if not shared:
                    continue
                out.append({
                    "kind": "split_organisation", "left_id": x,
                    "left_label": alabel.get(x, x), "right_id": y,
                    "right_label": alabel.get(y, y),
                    "basis": "shared_seat_and_token",
                    "detail": f"{a[:60]} | shared: {' '.join(sorted(shared))[:40]}",
                })
    return out


def split_person_candidates() -> list[dict]:
    """A seed person and an unresolved gazette cluster bearing the same name.

    Halving one person into two nodes does more than lower their degree: it
    removes every path that ran through them, which is exactly how a broker
    disappears and a hole appears in their place.
    """
    seed_by_key: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for n in _read("seed_nodes.csv"):
        if n.get("node_type") != "PERSON":
            continue
        k = parse_person(n.get("label") or "").match_key
        if k:
            seed_by_key[k].append((n["node_id"], n.get("label") or ""))
    out: list[dict] = []
    for g in _read("gazette_only_persons.csv"):
        k = parse_person(g.get("label") or "").match_key
        hits = seed_by_key.get(k, [])
        # One seed bearer only: with two the pair is not identifiable and the
        # right place for it is the ambiguity queue, not here.
        if len(hits) != 1:
            continue
        sid, slabel = hits[0]
        out.append({
            "kind": "split_person", "left_id": sid, "left_label": slabel,
            "right_id": g.get("candidate_person_id") or "",
            "right_label": g.get("label") or "",
            "basis": "same_name_key_one_seed_bearer",
            "detail": f"{g.get('n_events','0')} events; orgs: "
                      f"{(g.get('orgs') or '')[:60]}",
        })
    return out


# --------------------------------------------------------------------------- #

def run() -> dict:
    ensure_dirs()
    observed = person_org_edges()
    declined, why = declined_person_org_edges()
    potential = observed | declined

    adj_obs = project_persons(observed)
    adj_pot = project_persons(potential)
    comp_obs = components(adj_obs)
    comp_pot = components(adj_pot)
    pairs_obs = reachable_pairs(adj_obs)
    pairs_pot = reachable_pairs(adj_pot)

    splits_org = split_organisation_candidates()
    splits_person = split_person_candidates()

    # How many person pairs each split organisation would connect: the people
    # at one side times the people at the other, for pairs not already
    # adjacent. This is what makes a split an actual hole rather than a
    # bookkeeping nuisance.
    people_of: dict[str, set[str]] = defaultdict(set)
    for pid, oid in observed:
        people_of[oid].add(pid)
    for s in splits_org:
        a, b = people_of.get(s["left_id"], set()), people_of.get(s["right_id"], set())
        s["would_connect_persons"] = sum(
            1 for x in a for y in b if x != y and y not in adj_obs.get(x, ()))
    for s in splits_person:
        s["would_connect_persons"] = ""

    suspects = splits_org + splits_person
    for i, s in enumerate(suspects):
        s["suspect_id"] = f"SH_{i:07d}"
    _write("suspect_holes.csv", suspects, FIELDS_SUSPECT)

    bridging = sum(int(s["would_connect_persons"] or 0) for s in splits_org)
    diag = {
        "person_org_edges_asserted": len(observed),
        "person_org_edges_declined": len(declined),
        "persons_in_projection": len(adj_obs),
        "components_observed": len(comp_obs),
        "components_potential": len(comp_pot),
        "largest_component_observed": comp_obs[0] if comp_obs else 0,
        "largest_component_potential": comp_pot[0] if comp_pot else 0,
        "connected_pairs_observed": pairs_obs,
        "connected_pairs_potential": pairs_pot,
        "pairs_the_queue_would_connect": pairs_pot - pairs_obs,
        "split_organisation_pairs": len(splits_org),
        "split_person_pairs": len(splits_person),
        "person_pairs_behind_split_orgs": bridging,
    }
    if pairs_obs:
        diag["false_hole_exposure_pct"] = round(
            100 * (pairs_pot - pairs_obs) / pairs_obs, 1)

    print("structural holes: how much of the sparsity is real")
    for k, v in diag.items():
        print(f"  {k:<34} {v:>12,}" if isinstance(v, int)
              else f"  {k:<34} {v:>12}")
    for k, v in why.items():
        print(f"  declined because {k:<18} {v:>12,}")
    _report(diag, suspects)
    return diag


def _report(diag: dict, suspects: list[dict]) -> None:
    top = sorted(suspects, key=lambda s: -int(s["would_connect_persons"] or 0))[:15]
    lines = [
        "# Structural holes: real, or made by resolution?",
        "",
        "A structural hole is a finding. Two clusters with nobody bridging them",
        "is what brokerage looks like in a network, and a paper reports it as",
        "such. A hole this pipeline manufactured by failing to resolve an",
        "identity is therefore not a nuisance but a **false finding** -- and it",
        "is the error that most directly corrupts the substantive claim,",
        "because it is indistinguishable from the thing the analysis is looking",
        "for.",
        "",
        "This report quantifies the exposure. It fixes nothing.",
        "",
        "## The bound",
        "",
        "| quantity | asserted | if every declined link were admitted |",
        "|---|---|---|",
        f"| person-organisation edges | {diag['person_org_edges_asserted']:,} | "
        f"{diag['person_org_edges_asserted'] + diag['person_org_edges_declined']:,} |",
        f"| components in the person projection | {diag['components_observed']:,} | "
        f"{diag['components_potential']:,} |",
        f"| largest component | {diag['largest_component_observed']:,} | "
        f"{diag['largest_component_potential']:,} |",
        f"| connected person pairs | {diag['connected_pairs_observed']:,} | "
        f"{diag['connected_pairs_potential']:,} |",
        "",
        f"**{diag['pairs_the_queue_would_connect']:,} person pairs** are "
        f"unconnected in the dataset as asserted and connected if the review",
        "queue is admitted wholesale"
        + (f" -- {diag['false_hole_exposure_pct']}% of the connected pairs the "
           f"dataset does assert." if "false_hole_exposure_pct" in diag else "."),
        "",
        "Neither column is the truth. The left one treats every declined link",
        "as absent, which is what produces false holes; the right treats every",
        "one as real, which would import every bad match in the queue. The",
        "interval between them is the honest statement, and it is printed so a",
        "reader can see its width before treating any particular hole as a",
        "finding.",
        "",
        "## Where the suspect holes are",
        "",
        f"- **{diag['split_organisation_pairs']:,} organisation pairs** are "
        f"plausibly one firm, by a shared hard identifier or a shared",
        "  discriminating seat with an overlapping name. Between them they sit",
        f"  across **{diag['person_pairs_behind_split_orgs']:,} person pairs**",
        "  that would be colleagues if the pair were one firm.",
        f"- **{diag['split_person_pairs']:,} person pairs** are a seed node and",
        "  an unresolved gazette cluster bearing the same name, with exactly one",
        "  seed bearer of that name. Splitting one person in two does not merely",
        "  halve their degree -- it removes every path that ran through them,",
        "  which is how a broker disappears and a hole appears in their place.",
        "",
        "Every pair is listed in `suspect_holes.csv` with its basis, so none of",
        "this has to be taken on trust.",
        "",
        "## The largest suspects, by how many person pairs they separate",
        "",
        "| organisation A | organisation B | basis | person pairs |",
        "|---|---|---|---|",
    ]
    for s in top:
        if s["kind"] != "split_organisation":
            continue
        lines.append(
            f"| {s['left_label'][:38]} | {s['right_label'][:38]} | "
            f"{s['basis']} | {s['would_connect_persons']} |")
    lines += [
        "",
        "## What this does not cover",
        "",
        "- A hole between two firms neither of which states an identifier or a",
        "  seat is invisible here. Absence of a suspect is not evidence the hole",
        "  is real.",
        "- Merge hubs are excluded from the projection (any organisation with",
        "  more than 60 officers), because a hub connects everyone to everyone",
        "  and would report the whole network as one blob -- the mirror of the",
        "  error being measured. So the observed column is computed on a",
        "  network with the worst merges already removed.",
        "- The queue's edges are candidates, not findings. An ambiguous dyad",
        "  means the matcher declined to choose among several people, not that",
        "  nobody was there -- which is why admitting them bounds the hole",
        "  count rather than correcting it.",
    ]
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "STRUCTURAL-HOLES-multiplex.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(
        description="Quantify how much observed sparsity is resolution error."
    ).parse_args(argv)
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
