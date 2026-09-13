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


def declined_person_org_edges_in(lo_year: int, hi_year: int
                                 ) -> set[tuple[str, str]]:
    """Declined person-organisation edges datable to a window.

    An era slice has to slice BOTH sides. Comparing a pre-2011 observed
    network against an all-years declined set adds post-2011 edges to a
    pre-2011 graph, which is how the 1957-2010 slice came out at 222.9%
    exposure: most of what it was "closing" had not happened yet.
    """
    out: set[tuple[str, str]] = set()
    for r in _read("review_queue.csv"):
        pid = r.get("resolved_person_id") or r.get("runner_up_person_id") or ""
        oid = r.get("resolved_org_id") or r.get("org_candidate_id") or ""
        if not (pid and oid):
            continue
        lo = (r.get("first_event_date") or "")[:4]
        hi = (r.get("last_event_date") or "")[:4]
        a = int(lo) if lo.isdigit() else 0
        b = int(hi) if hi.isdigit() else 9999
        if a <= hi_year and b >= lo_year:
            out.add((pid, oid))
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


def one_mode_adjacency(edges: set[tuple[str, str]]) -> dict[str, set[str]]:
    """Adjacency for a layer that is ALREADY one-mode (org-org, kinship).

    No projection: the tie is the edge. Kept separate from `project_persons`
    because conflating them would apply the merge-hub exclusion -- which is
    about how many officers one firm can plausibly have -- to a layer where
    it means nothing.
    """
    adj: dict[str, set[str]] = defaultdict(set)
    for a, b in edges:
        if a and b and a != b:
            adj[a].add(b)
            adj[b].add(a)
    return adj


def layer_exposure(name: str, adj_obs: dict[str, set[str]],
                   adj_pot: dict[str, set[str]],
                   queue_rows: int = 0, usable_declined: int = 0) -> dict:
    """The hole bound for one part of the network.

    Reported per layer because the layers fail differently and an aggregate
    would hide that. The person-organisation panel is dense and mostly
    name-resolved; the ownership layer admits only dyads where BOTH ends are
    seed organisations, so its sparsity is largely a membership rule rather
    than an absence of ownership; the kinship layer is sparse because a
    marriage needs two identifiable people. A single exposure figure across
    all three would average a measurement artefact together with a design
    decision.
    """
    comp_obs, comp_pot = components(adj_obs), components(adj_pot)
    pairs_obs = sum(n * (n - 1) // 2 for n in comp_obs)
    pairs_pot = sum(n * (n - 1) // 2 for n in comp_pot)
    # The two sides must describe the same node set. If the potential graph
    # has nodes the observed one does not, the difference is not a closed
    # hole -- it is a node that was never in the network being measured, and
    # counting its pairs reports the node-set gap as an exposure.
    extra = set(adj_pot) - set(adj_obs)
    return {
        "layer": name,
        "nodes": len(adj_obs),
        "components_observed": len(comp_obs),
        "components_potential": len(comp_pot),
        "largest_observed": comp_obs[0] if comp_obs else 0,
        "largest_potential": comp_pot[0] if comp_pot else 0,
        "connected_pairs_observed": pairs_obs,
        "connected_pairs_potential": pairs_pot,
        "pairs_on_the_boundary": pairs_pot - pairs_obs,
        "exposure_pct": (round(100 * (pairs_pot - pairs_obs) / pairs_obs, 1)
                         if pairs_obs else ""),
        "nodes_only_in_potential": len(extra),
        "comparable": "yes" if not extra else "no: node sets differ",
        "queue_rows": queue_rows,
        "usable_declined_edges": usable_declined,
        # 0% exposure means two opposite things and they must not share a
        # cell. If the queue is empty, nothing was declined and the sparsity
        # is real. If the queue is full but no row carries ids for BOTH ends,
        # the method cannot see the holes at all -- and reporting that as 0%
        # would turn "we cannot measure this" into "there is nothing here",
        # which is the strongest claim in the report and the least supported.
        "verdict": ("no declined links" if not queue_rows else
                    "UNMEASURABLE: queue has no row with both endpoint ids"
                    if not usable_declined else "measured"),
    }


def spell_year_bounds(s: dict) -> tuple[int, int]:
    """The years a spell can have been live in, from whatever dates it carries."""
    lo = (s.get("onset") or s.get("onset_hi") or s.get("onset_lo") or "")[:4]
    hi = (s.get("terminus") or s.get("terminus_hi") or "")[:4]
    return (int(lo) if lo.isdigit() else 0,
            int(hi) if hi.isdigit() else 9999)


def person_org_edges_in(lo_year: int, hi_year: int) -> set[tuple[str, str]]:
    """Person-organisation edges whose spell can have been live in a window.

    An era slice is where a false hole matters most: the substantive claims
    about this network are about the pre-2011 configuration, and a hole
    manufactured there is a false claim about the old regime rather than a
    blemish on a summary statistic.
    """
    out: set[tuple[str, str]] = set()
    for s in _read("spells.csv"):
        if s.get("evidence_tier") not in (
                "gazette_dated", "gazette_inferred", "gazette_snowball"):
            continue
        if not (s.get("person_id") and s.get("org_id")):
            continue
        a, b = spell_year_bounds(s)
        if a <= hi_year and b >= lo_year:
            out.add((s["person_id"], s["org_id"]))
    return out


def org_ownership_edges() -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    """The ownership layer, asserted and declined.

    The declined set here is large and mostly a MEMBERSHIP rule rather than a
    resolution failure: the layer admits a dyad only where both ends resolve
    to distinct seed organisations, so 10,622 one-end-resolved observations
    sit out by design. They still bound the hole count, and that is the point
    of reporting both -- but the interval is wide for a reason that is not an
    error, and the report says so.
    """
    obs: set[tuple[str, str]] = set()
    for r in _read("org_tie_spells.csv"):
        if r.get("holder_id") and r.get("target_id"):
            obs.add((r["holder_id"], r["target_id"]))
    dec: set[tuple[str, str]] = set()
    for r in _read("org_ties_review_queue.csv"):
        # `near_org_id` is deliberately NOT used: it is what a failed match
        # came CLOSEST to, recorded so a coder can adjudicate, and treating it
        # as a claimed endpoint manufactures ties out of near-misses -- which
        # is the merge-hub error in a new place.
        h = r.get("holder_id") or r.get("holder_seed_id") or ""
        t = r.get("target_id") or r.get("target_seed_id") or ""
        if h and t:
            dec.add((h, t))
    return obs, dec


def kinship_edges() -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    """The kinship layer, asserted and declined."""
    obs = {(r["person_id"], r["kin_id"]) for r in _read("person_tie_spells.csv")
           if r.get("person_id") and r.get("kin_id")}
    dec: set[tuple[str, str]] = set()
    for r in _read("person_ties_review_queue.csv"):
        # IDS ONLY. Falling back to the raw mention string, which an earlier
        # version of this did, puts name strings and node ids in one graph:
        # the potential side then gains thousands of nodes the observed side
        # does not have, and the "exposure" it reports is the size of that
        # node-set difference rather than any hole. It printed 279,300%.
        a, b = r.get("person_id") or "", r.get("kin_id") or ""
        if a and b:
            dec.add((a, b))
    return obs, dec


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

    # --- every part of the network, measured the same way ---------------- #
    # One aggregate figure would average a measurement artefact together with
    # a design decision, and the layers fail differently enough that the
    # average would be meaningless. Era slices are included because the
    # substantive claims about this network are about the pre-2011
    # configuration: a hole manufactured there is a false claim about the old
    # regime, not a blemish on a summary statistic.
    n_queue = len(_read("review_queue.csv"))
    layers = [layer_exposure("person-organisation (all years)",
                             adj_obs, adj_pot, n_queue, len(declined))]
    for label, lo, hi in (("person-organisation 1957-2010", 0, 2010),
                          ("person-organisation 2011-2026", 2011, 9999)):
        obs_e = person_org_edges_in(lo, hi)
        dec_e = declined_person_org_edges_in(lo, hi)
        layers.append(layer_exposure(
            label, project_persons(obs_e),
            project_persons(obs_e | dec_e), n_queue, len(dec_e)))
    o_obs, o_dec = org_ownership_edges()
    if o_obs:
        layers.append(layer_exposure(
            "organisation ownership", one_mode_adjacency(o_obs),
            one_mode_adjacency(o_obs | o_dec),
            len(_read("org_ties_review_queue.csv")), len(o_dec)))
    k_obs, k_dec = kinship_edges()
    if k_obs:
        layers.append(layer_exposure(
            "kinship", one_mode_adjacency(k_obs),
            one_mode_adjacency(k_obs | k_dec),
            len(_read("person_ties_review_queue.csv")), len(k_dec)))
    _write("hole_exposure_by_layer.csv", layers, list(layers[0].keys()))

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
    print(f"  {'layer':<32} {'nodes':>7} {'comps':>7} {'->':>7} "
          f"{'pairs':>11} {'->':>11} {'exposure':>9}")
    for L in layers:
        print(f"  {L['layer']:<32} {L['nodes']:>7,} "
              f"{L['components_observed']:>7,} {L['components_potential']:>7,} "
              f"{L['connected_pairs_observed']:>11,} "
              f"{L['connected_pairs_potential']:>11,} "
              f"{(str(L['exposure_pct']) + '%') if L['verdict'] == 'measured' else '--':>9}"
              f"  {L['verdict'] if L['verdict'] != 'measured' else ''}")
    print()
    for k, v in diag.items():
        print(f"  {k:<34} {v:>12,}" if isinstance(v, int)
              else f"  {k:<34} {v:>12}")
    for k, v in why.items():
        print(f"  declined because {k:<18} {v:>12,}")
    _report(diag, suspects, layers)
    return diag


def _report(diag: dict, suspects: list[dict],
            layers: list[dict] | None = None) -> None:
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
        "## Every part of the network, measured the same way",
        "",
        "| layer | nodes | components | if admitted | connected pairs | if admitted | exposure |",
        "|---|---|---|---|---|---|---|",
    ] + [
        f"| {L['layer']} | {L['nodes']:,} | {L['components_observed']:,} | "
        f"{L['components_potential']:,} | {L['connected_pairs_observed']:,} | "
        f"{L['connected_pairs_potential']:,} | {L['exposure_pct']}% |"
        for L in (layers or [])
    ] + [
        "",
        "The layers are reported separately on purpose. The",
        "person-organisation panel is dense and mostly name-resolved, so its",
        "exposure is close to a pure measurement artefact. The ownership",
        "layer's is not: that layer admits a dyad only where **both** ends",
        "resolve to distinct seed organisations, so most of its declined set",
        "sits out by design rather than by failure, and its interval is wide",
        "for a reason that is not an error. The kinship layer is sparse",
        "because a marriage needs two identifiable people. One averaged",
        "figure across the three would mix an artefact with a design",
        "decision and mean nothing.",
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
