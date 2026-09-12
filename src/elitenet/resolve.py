"""Stage 6 -- resolve extracted mentions to the seed network.

Homonymy is the binding constraint on this dataset. "Mohamed Trabelsi" returns
over 1,500 gazette pages across seven decades, so a personal name is not an
identifier. What makes resolution tractable is that the seed sheet already
records *which organisations each person belongs to*: the unit of matching is
therefore the (person, organisation) dyad, not the name.

Nothing is discarded. Every mention is emitted with its score components, the
number of rival candidates, and the margin to the runner-up, so the whole
dataset can be re-thresholded by anyone who disagrees with the cut points.
Mentions that match no seed person are kept and clustered as candidate new
people, because the seed is a single-snapshot sheet while the gazette is not.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from rapidfuzz import fuzz

from .names import org_id, parse_org, parse_person, person_id
from .paths import INTERIM, PROCESSED, ensure_dirs

# Score weights. Organisation agreement outweighs name similarity: two people
# with the same common name are common, but two people with the same name at
# the same firm are not.
W_NAME = 0.35
W_ORG = 0.35
W_MF = 0.10
W_COOCCUR = 0.15
W_ROLE = 0.05

THRESHOLD_RESOLVED = 0.70
THRESHOLD_AMBIGUOUS = 0.45
AMBIGUITY_MARGIN = 0.05      # rivals this close force review regardless of level

# Organisation agreement is powerful but it cannot stand alone. Blocking on the
# organisation makes every seed officer of a matching firm a candidate, which is
# what rescues an OCR-mangled name -- and also what would let any officer of
# that firm absorb a stranger who merely appears in the same announcement. So
# the organisation and matricule signals only count once the name is at least
# plausibly the same name.
NAME_FLOOR_FOR_ORG = 0.70

# Seed edge roles that make a given gazette role plausible for that person.
ROLE_AFFINITY: dict[str, set[str]] = {
    "gerant": {"gerant", "dg", "ceo", "director", "president"},
    "dg": {"dg", "ceo", "gerant", "pdg", "director"},
    "ceo": {"ceo", "dg", "pdg"},
    "pdg": {"pdg", "ceo", "dg", "chairman", "president_ca"},
    "president_ca": {"president_ca", "chairman", "pdg", "president"},
    "chairman": {"chairman", "president_ca", "pdg", "president"},
    "administrateur": {"administrateur", "board_member", "chairman", "president_ca"},
    "dga": {"dga", "dg", "director"},
    "commissaire_aux_comptes": {"commissaire_aux_comptes", "accountant"},
    "representant": {"representant", "shareholder", "administrateur"},
    "shareholder": {"shareholder", "owner", "funder"},
    "member": {"member"},
    "minister": {"minister", "member", "president"},
    "representant_state": {"representant", "member"},
}

RESOLUTION_FIELDS = [
    "mention_key", "person_mention", "org_mention", "org_mf",
    "resolved_person_id", "resolved_person_label", "resolved_org_id",
    "resolved_org_label", "score", "link_status",
    "s_name", "s_org", "s_mf", "s_cooccur", "s_role",
    "n_candidates", "margin_to_runner_up", "runner_up_person_id",
    "n_events", "first_event_date", "last_event_date",
    "seed_degree", "name_ambiguity", "mention_cluster_id", "evidence_quote",
]


# --------------------------------------------------------------------------- #
# seed index
# --------------------------------------------------------------------------- #

@dataclass
class SeedIndex:
    persons: dict[str, dict] = field(default_factory=dict)
    orgs: dict[str, dict] = field(default_factory=dict)
    person_orgs: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    person_neighbours: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    org_persons: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    person_roles: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    # blocking indexes
    by_match_key: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    by_surname_initial: dict[tuple, set[str]] = field(default_factory=lambda: defaultdict(set))
    by_sorted_tokens: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    org_by_norm: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    org_by_acronym: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    org_by_token: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))

    def name_ambiguity(self, match_key: str) -> int:
        """How many distinct seed people share this name key."""
        return len(self.by_match_key.get(match_key, ()))


def load_seed() -> SeedIndex:
    idx = SeedIndex()
    with (PROCESSED / "seed_nodes.csv").open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row["node_type"] == "PERSON":
                idx.persons[row["node_id"]] = row
                p = parse_person(row["label"])
                idx.by_match_key[p.match_key].add(row["node_id"])
                if p.surname_key:
                    idx.by_surname_initial[(p.surname_key, p.first_initial)].add(row["node_id"])
                idx.by_sorted_tokens[" ".join(sorted(p.match_tokens))].add(row["node_id"])
            else:
                idx.orgs[row["node_id"]] = row
                o = parse_org(row["label"])
                if o.match_key:
                    idx.org_by_norm[o.match_key].add(row["node_id"])
                for alt in (row.get("alt_names") or "").split(";"):
                    alt = alt.strip()
                    if not alt:
                        continue
                    if len(alt.split()) == 1 and alt.isupper():
                        idx.org_by_acronym[alt].add(row["node_id"])
                    else:
                        idx.org_by_norm[parse_org(alt).match_key].add(row["node_id"])
                for tok in set(o.content_tokens):
                    if len(tok) > 3:
                        idx.org_by_token[tok].add(row["node_id"])

    with (PROCESSED / "seed_edges.csv").open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            src, dst = row["from_node_id"], row["to_node_id"]
            if row["from_type"] == "PERSON" and row["to_type"] != "PERSON":
                idx.person_orgs[src].add(dst)
                idx.org_persons[dst].add(src)
                idx.person_roles[src].add(row["role_canonical"])
            elif row["from_type"] == "PERSON" and row["to_type"] == "PERSON":
                idx.person_neighbours[src].add(dst)
                idx.person_neighbours[dst].add(src)
    # Co-membership makes two people neighbours for scoring purposes.
    for org, people in idx.org_persons.items():
        if len(people) <= 40:          # skip hub organisations: too unspecific
            for p in people:
                idx.person_neighbours[p] |= (people - {p})
    return idx


# --------------------------------------------------------------------------- #
# organisation resolution
# --------------------------------------------------------------------------- #

def resolve_org(mention: str, idx: SeedIndex) -> tuple[str, float]:
    """Match an organisation mention to a seed organisation."""
    if not mention:
        return "", 0.0
    o = parse_org(mention)
    if not o.match_key:
        return "", 0.0
    hits = idx.org_by_norm.get(o.match_key)
    if hits:
        return sorted(hits)[0], 1.0
    if o.acronym and o.acronym in idx.org_by_acronym:
        return sorted(idx.org_by_acronym[o.acronym])[0], 0.9
    # token-blocked fuzzy comparison
    cands: set[str] = set()
    for tok in set(o.content_tokens):
        if len(tok) > 3:
            cands |= idx.org_by_token.get(tok, set())
        if len(cands) > 400:
            break
    best, best_s = "", 0.0
    for cid in cands:
        label = idx.orgs[cid]["label_normalised"] or idx.orgs[cid]["label"]
        s = fuzz.token_set_ratio(o.match_key, label) / 100.0
        if s > best_s:
            best, best_s = cid, s
    return (best, best_s) if best_s >= 0.88 else ("", best_s)


# --------------------------------------------------------------------------- #
# person resolution
# --------------------------------------------------------------------------- #

def candidates_for(name: str, org_id_resolved: str, idx: SeedIndex) -> set[str]:
    p = parse_person(name)
    if p.is_empty:
        return set()
    out: set[str] = set()
    out |= idx.by_match_key.get(p.match_key, set())
    if p.surname_key:
        out |= idx.by_surname_initial.get((p.surname_key, p.first_initial), set())
    out |= idx.by_sorted_tokens.get(" ".join(sorted(p.match_tokens)), set())
    # Organisation-anchored block: anyone the seed places at this organisation
    # is a candidate even if the OCR mangled their name.
    if org_id_resolved:
        out |= idx.org_persons.get(org_id_resolved, set())
    return out


def name_similarity(a_tokens: tuple[str, ...], b_tokens: tuple[str, ...]) -> float:
    """Similarity that requires the given name to agree, not just the surname.

    A plain token-set ratio scores a shared surname alone at ~0.73, which would
    make "Boubaker Trabelsi" and "Chedly Trabelsi" both match "Mohamed
    Trabelsi" -- and surnames such as Trabelsi are borne by thousands of
    people. Agreement on the family name is therefore treated as necessary but
    far from sufficient: it gates the score, and the given names decide it.

    Both token orders are tried, because the gazette prints "Salah El Mechri"
    and "El Mechri Salah" for the same person.
    """
    if not a_tokens or not b_tokens:
        return 0.0

    def _score(a: tuple[str, ...], b: tuple[str, ...]) -> float:
        surname = fuzz.ratio(a[-1], b[-1]) / 100.0
        if surname < 0.80:
            return 0.0
        a_given, b_given = a[:-1], b[:-1]
        if not a_given or not b_given:
            given = 0.5           # one side has only a family name: weak evidence
        else:
            # Given names are short and distinct, so character-level fuzz is far
            # too generous ("BOUBAKER" against "MOHAMED" scores 0.4 on shared
            # letters alone). Match them as whole tokens instead: what share of
            # the shorter given-name set has a near-identical partner?
            short, long_ = ((a_given, b_given) if len(a_given) <= len(b_given)
                            else (b_given, a_given))
            matched = sum(1 for s_tok in short
                          if any(fuzz.ratio(s_tok, l_tok) >= 85 for l_tok in long_))
            given = matched / len(short)
        return surname * (0.4 + 0.6 * given)

    def _contained() -> float:
        """One full name contained in the other, in any token order.

        Catches the maiden-plus-married form that is common for Tunisian women:
        the seed records "Aicha Driss" while the gazette prints "Aicha Driss
        Jenayah". Scored below an exact agreement, because an extra family name
        can also mark a different person.
        """
        short, long_ = ((a_tokens, b_tokens) if len(a_tokens) <= len(b_tokens)
                        else (b_tokens, a_tokens))
        if len(short) < 2 or len(short) == len(long_):
            return 0.0
        if all(any(fuzz.ratio(s_tok, l_tok) >= 85 for l_tok in long_) for s_tok in short):
            return 0.85
        return 0.0

    return max(_score(a_tokens, b_tokens),
               _score(tuple(reversed(a_tokens)), b_tokens),
               _score(a_tokens, tuple(reversed(b_tokens))),
               _contained())


def score_pair(name: str, cand_id: str, org_resolved: str, org_score: float,
               mf_match: bool, co_mentions: set[str], role: str,
               idx: SeedIndex) -> dict:
    cand = idx.persons[cand_id]
    p_men = parse_person(name)
    p_cand = parse_person(cand["label"])

    s_name = name_similarity(p_men.match_tokens, p_cand.match_tokens)

    name_plausible = s_name >= NAME_FLOOR_FOR_ORG
    s_org = 0.0
    if name_plausible and org_resolved and org_resolved in idx.person_orgs.get(cand_id, ()):
        s_org = min(1.0, org_score)

    s_mf = 1.0 if (mf_match and name_plausible) else 0.0

    neighbours = idx.person_neighbours.get(cand_id, set())
    overlap = 0
    for other in co_mentions:
        for oid in idx.by_match_key.get(parse_person(other).match_key, ()):
            if oid in neighbours:
                overlap += 1
                break
    s_cooccur = min(1.0, overlap / 2.0)

    seed_roles = idx.person_roles.get(cand_id, set())
    affine = ROLE_AFFINITY.get(role, {role} if role else set())
    s_role = 1.0 if (affine & seed_roles) else 0.0

    score = (W_NAME * s_name + W_ORG * s_org + W_MF * s_mf
             + W_COOCCUR * s_cooccur + W_ROLE * s_role)
    return {
        "person_id": cand_id, "score": score, "s_name": s_name, "s_org": s_org,
        "s_mf": s_mf, "s_cooccur": s_cooccur, "s_role": s_role,
    }


# --------------------------------------------------------------------------- #
# driver
# --------------------------------------------------------------------------- #

def run(events_path: Path | None = None) -> dict:
    ensure_dirs()
    idx = load_seed()
    events_path = events_path or (INTERIM / "events_raw.jsonl")

    # Group events by (person, organisation) dyad: the dyad is the unit of
    # identity, so all evidence for one dyad is scored together.
    dyads: dict[tuple[str, str], dict] = {}
    org_cache: dict[str, tuple[str, float]] = {}
    block_people: dict[str, set[str]] = defaultdict(set)

    with events_path.open(encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh]

    for e in rows:
        if e.get("person_mention"):
            block_people[e["block_uid"]].add(e["person_mention"])

    for e in rows:
        person = e.get("person_mention")
        if not person:
            continue
        org_men = e.get("org_mention") or ""
        key = (person, org_men)
        d = dyads.setdefault(key, {
            "person_mention": person, "org_mention": org_men,
            "org_mf": e.get("org_mf") or "", "n_events": 0,
            "dates": [], "roles": set(), "blocks": set(),
            "quote": e.get("evidence_quote") or "",
        })
        d["n_events"] += 1
        if e.get("event_date"):
            d["dates"].append(e["event_date"])
        if e.get("role_canonical"):
            d["roles"].add(e["role_canonical"])
        d["blocks"].add(e["block_uid"])
        if not d["org_mf"] and e.get("org_mf"):
            d["org_mf"] = e["org_mf"]

    # matricule fiscal -> resolved org, learned from unambiguous dyads
    mf_to_org: dict[str, str] = {}
    for (person, org_men), d in dyads.items():
        if d["org_mf"] and org_men:
            if org_men not in org_cache:
                org_cache[org_men] = resolve_org(org_men, idx)
            oid, osc = org_cache[org_men]
            if oid and osc >= 0.99:
                mf_to_org.setdefault(d["org_mf"], oid)

    out_rows: list[dict] = []
    stats = {"dyads": 0, "resolved": 0, "ambiguous": 0, "unresolved": 0,
             "org_resolved": 0, "forced_review_by_margin": 0}

    for (person, org_men), d in sorted(dyads.items()):
        stats["dyads"] += 1
        if org_men not in org_cache:
            org_cache[org_men] = resolve_org(org_men, idx)
        org_resolved, org_score = org_cache[org_men]
        if not org_resolved and d["org_mf"] and d["org_mf"] in mf_to_org:
            org_resolved, org_score = mf_to_org[d["org_mf"]], 0.95
        if org_resolved:
            stats["org_resolved"] += 1

        co_mentions = set()
        for b in d["blocks"]:
            co_mentions |= (block_people.get(b, set()) - {person})

        role = next(iter(d["roles"]), "")
        cands = candidates_for(person, org_resolved, idx)
        scored = [score_pair(person, c, org_resolved, org_score,
                             bool(d["org_mf"] and d["org_mf"] in mf_to_org),
                             co_mentions, role, idx)
                  for c in cands]
        scored.sort(key=lambda r: -r["score"])

        top = scored[0] if scored else None
        runner = scored[1] if len(scored) > 1 else None
        margin = (top["score"] - runner["score"]) if (top and runner) else (
            top["score"] if top else 0.0)

        if top and top["score"] >= THRESHOLD_RESOLVED:
            status = "resolved"
        elif top and top["score"] >= THRESHOLD_AMBIGUOUS:
            status = "ambiguous"
        else:
            status = "unresolved"
        # Ambiguity, not low confidence, is what needs a human: two equally
        # plausible candidates are worse than one middling candidate.
        if top and runner and margin < AMBIGUITY_MARGIN and runner["score"] >= THRESHOLD_AMBIGUOUS:
            if status == "resolved":
                stats["forced_review_by_margin"] += 1
            status = "ambiguous"

        stats[status] = stats.get(status, 0) + 1
        dates = sorted(d["dates"])
        pm = parse_person(person)
        out_rows.append({
            "mention_key": f"{person}||{org_men}",
            "person_mention": person, "org_mention": org_men,
            "org_mf": d["org_mf"],
            "resolved_person_id": top["person_id"] if (top and status != "unresolved") else "",
            "resolved_person_label": (idx.persons[top["person_id"]]["label"]
                                      if (top and status != "unresolved") else ""),
            "resolved_org_id": org_resolved,
            "resolved_org_label": idx.orgs[org_resolved]["label"] if org_resolved else "",
            "score": round(top["score"], 4) if top else 0.0,
            "link_status": status,
            "s_name": round(top["s_name"], 3) if top else 0.0,
            "s_org": round(top["s_org"], 3) if top else 0.0,
            "s_mf": round(top["s_mf"], 3) if top else 0.0,
            "s_cooccur": round(top["s_cooccur"], 3) if top else 0.0,
            "s_role": round(top["s_role"], 3) if top else 0.0,
            "n_candidates": len(scored),
            "margin_to_runner_up": round(margin, 4),
            "runner_up_person_id": runner["person_id"] if runner else "",
            "n_events": d["n_events"],
            "first_event_date": dates[0] if dates else "",
            "last_event_date": dates[-1] if dates else "",
            "seed_degree": (idx.persons[top["person_id"]]["seed_degree"]
                            if (top and status != "unresolved") else ""),
            "name_ambiguity": idx.name_ambiguity(
                parse_person(idx.persons[top["person_id"]]["label"]).match_key
                if (top and status != "unresolved") else pm.match_key),
            "mention_cluster_id": person_id(person),
            "evidence_quote": d["quote"],
        })

    _write(PROCESSED / "resolution.csv", out_rows, RESOLUTION_FIELDS)

    # Review queue: ambiguity first, weighted by how consequential the person is.
    queue = [r for r in out_rows if r["link_status"] == "ambiguous"]
    queue.sort(key=lambda r: -(int(r["seed_degree"] or 0) + 5 * r["n_events"]))
    _write(PROCESSED / "review_queue.csv", queue, RESOLUTION_FIELDS)

    # Gazette-only people: retained as candidate new nodes, not dropped.
    new_people: dict[str, dict] = {}
    for r in out_rows:
        if r["link_status"] != "unresolved":
            continue
        cid = r["mention_cluster_id"]
        n = new_people.setdefault(cid, {
            "candidate_person_id": cid, "label": r["person_mention"],
            "n_mentions": 0, "n_events": 0, "orgs": set(),
            "first_event_date": "", "last_event_date": "",
        })
        n["n_mentions"] += 1
        n["n_events"] += r["n_events"]
        if r["resolved_org_label"] or r["org_mention"]:
            n["orgs"].add(r["resolved_org_label"] or r["org_mention"])
        for k in ("first_event_date", "last_event_date"):
            if r[k] and (not n[k] or (k == "first_event_date" and r[k] < n[k])
                         or (k == "last_event_date" and r[k] > n[k])):
                n[k] = r[k]
    rows_new = [{**n, "orgs": ";".join(sorted(n["orgs"])[:6])} for n in new_people.values()]
    rows_new.sort(key=lambda r: -r["n_events"])
    _write(PROCESSED / "gazette_only_persons.csv", rows_new,
           ["candidate_person_id", "label", "n_mentions", "n_events", "orgs",
            "first_event_date", "last_event_date"])

    stats["gazette_only_persons"] = len(rows_new)
    stats["review_queue"] = len(queue)
    return stats


def _write(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description="Resolve mentions to the seed network.").parse_args(argv)
    for k, v in run().items():
        print(f"  {k:26} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
