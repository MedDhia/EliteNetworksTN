"""Stage 12 -- organisation entities: the unit of analysis for a firm.

Why this exists
---------------

Organisation identity used to be "the seed node this mention fuzzy-matched".
That produced fabricated hubs. `fuzz.token_set_ratio` treats CONTAINMENT as
identity -- it returns 1.0 when the seed label's tokens are a subset of the
mention's, however much else the mention says -- and `seed.py` mints an org id
from the label with legal-form words stripped. So a seed firm called "SOCIETE
TROIS" became `CO_TROIS` with `label_normalised = "TROIS"`, the French for
three, and absorbed every mention containing the word: 135 mentions including
an address and a clause fragment, and 1,003 tie endpoints, which made it the
highest-degree organisation in the org-org layer. `CO_CONSULTING` absorbed
4,076 distinct mentions carrying 1,606 different matricules fiscaux.

The instruction was to fix that **without removing any data**. So nothing is
dropped: identity is refined, and the old seed link is retained on the entity
with the basis that produced it, which makes the previous view exactly
reproducible.

What an entity is
-----------------

One row per organisation as this corpus can distinguish it, keyed in priority
order:

1. the normalised **matricule fiscal**
2. the normalised **registre-de-commerce** number
3. the normalised **mention** itself

The matricule comes first because it is a hard identifier, so it does two jobs
at once. It **splits** a hub -- 1,606 matricules on one node become 1,606
entities -- and it **joins** spelling variants, since 19,795 matricules cover
more than one spelling, folding 52,683 spellings into single firms. That is why
this raises coverage rather than lowering it: the fix is not a stricter
threshold, it is a better key.

Where the mention's seed match is identity-grade (exact, acronym, or a fuzzy
match resting on a discriminating token -- see `resolve.org_match`), the entity
**adopts the seed node's id**. That is not cosmetic: `seed_edges.csv` ties and
every dyadic covariate are keyed on seed node ids, so an entity that did not
adopt would sit on a different vertex from its own seed ties. Entities whose
only seed link is `generic_fuzzy` get a fresh `ORGE_` id, which is precisely
the population that formed the hubs.

What this does not fix
----------------------

Two residual errors, both reported rather than hidden:

* **Name-keyed entities split one firm across spellings** -- the mirror image
  of the merge. Only a third of events carry a matricule, so most entities are
  name-keyed and two spellings of one identifier-less firm stay apart. It
  understates degree where the merge overstated it.
* **A mention carrying several identifiers cannot be attributed.** 98.4% of
  mentions carry exactly one matricule, but `Société de Promotion Immobilière`
  carries 78. An identifier-less event on such a mention gets an
  `ambiguous_mention` entity that is explicitly not an identity, rather than
  being folded in with one of the firms.
* **Seed-sheet collisions persist.** Distinct seed firms whose labels normalise
  identically already share a node id (`seed.py:174`), with the losers in
  `alt_names`. Adoption preserves that, and `orgattrs` reports it.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from .grammar import normalise_mf, normalise_rc
from .names import parse_org
from .paths import INTERIM, PROCESSED, ensure_dirs
from .resolve import build_token_specificity, load_seed, org_match

FIELDS_ENTITY = [
    "org_entity_id", "entity_basis", "entity_key", "n_keys", "label",
    "n_mentions", "n_events", "first_seen", "last_seen",
    "matricule", "rc",
    "seed_org_id", "seed_org_label", "seed_match_basis", "seed_link_is_identity",
    "is_identity", "issue_uid",
]
# Every key an entity was reached by, not just the first. Adoption collapses
# several keys onto one seed id, so a single stored key made `for_event`
# return "" for every other key of that entity -- indistinguishable from an
# inert resolver, which made each such event silently fall back to the OLD
# identity. That is the "half-applied identity" the resolver docstring
# promises cannot happen, and it happened for the normal case.
FIELDS_KEY = ["entity_key", "org_entity_id", "entity_basis", "n_events"]
FIELDS_MEMBER = [
    "org_mention", "org_entity_id", "entity_basis", "n_events",
    "mention_is_ambiguous", "n_identifiers_on_mention",
    "n_entities_on_mention", "seed_org_id", "seed_match_basis",
]

# An entity basis that is not an identity claim. Kept as data, excluded from
# anything that asserts two observations are the same firm.
NON_IDENTITY = ("ambiguous_mention",)


def _read_table(name: str) -> list[dict]:
    """A processed table, following the committed `.gz` when the plain file is
    absent -- which is the normal state in a fresh clone and in CI."""
    path = PROCESSED / name
    if path.exists():
        with path.open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))
    gz = PROCESSED / (name + ".gz")
    if gz.exists():
        with gzip.open(gz, "rt", encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))
    return []


def _eid(key: str) -> str:
    return "ORGE_" + hashlib.blake2b(key.encode(), digest_size=10).hexdigest()


def read_events(events_path: Path | None = None) -> list[dict]:
    """Prefer the interim JSONL, as every other stage does.

    `events.csv` only exists after `export`, so reading it alone would make
    this stage silently produce nothing when run in pipeline order.
    """
    raw = events_path or (INTERIM / "events_raw.jsonl")
    if raw.exists():
        with raw.open(encoding="utf-8") as fh:
            return [json.loads(line) for line in fh]
    return _read_table("events.csv")


def ambiguous_mentions(events: list[dict]) -> dict[str, int]:
    """Mentions carrying more than one hard identifier, and how many.

    Such a mention names more than one firm, so it identifies none of them.
    The same reasoning `tergm.org_lifecycle` and `orgattrs.mention_to_org`
    already apply to a mention resolving to two organisations.
    """
    ids: dict[str, set[str]] = defaultdict(set)
    for e in events:
        m = (e.get("org_mention") or "").strip()
        if not m:
            continue
        for col, norm in (("org_mf", normalise_mf), ("org_rc", normalise_rc)):
            v = norm(e.get(col) or "")
            if v:
                ids[m].add(f"{col}:{v}")
    return {m: len(v) for m, v in ids.items() if len(v) > 1}


def entity_key(event: dict, ambiguous: dict[str, int]) -> tuple[str, str]:
    """The (key, basis) an event's organisation is identified by.

    Deterministic and derivable from the event row alone plus the ambiguity
    map, so `spells` and `orgties` can compute it without a 689,169-row join.
    """
    mention = (event.get("org_mention") or "").strip()
    mf = normalise_mf(event.get("org_mf") or "")
    if mf:
        return f"MF:{mf}", "matricule_fiscal"
    rc = normalise_rc(event.get("org_rc") or "")
    if rc:
        return f"RC:{rc}", "registre_commerce"
    if not mention:
        return "", "none"
    key = parse_org(mention).match_key or mention.upper()
    if mention in ambiguous:
        # The mention names several firms and this event says which one it is
        # not. Kept apart rather than folded into whichever firm was modal.
        return f"AMB:{key}", "ambiguous_mention"
    return f"NAME:{key}", "name"


def build(events: list[dict], idx, ambiguous: dict[str, int] | None = None
          ) -> tuple[list[dict], list[dict], list[dict], dict]:
    """Entities, the key index, the mention map, and diagnostics."""
    ambiguous = ambiguous if ambiguous is not None else ambiguous_mentions(events)
    diag: Counter = Counter()

    # The seed match per distinct mention, with its basis. Cached because
    # org_match is the expensive call and mentions repeat heavily.
    match_cache: dict[str, object] = {}

    def seed_of(mention: str):
        if mention not in match_cache:
            match_cache[mention] = org_match(mention, idx)
        return match_cache[mention]

    agg: dict[str, dict] = {}
    mention_entity: dict[str, Counter] = defaultdict(Counter)

    # Both sides of a tie need an entity. The holder of a shareholding is
    # named inside a clause and carries no identifier of its own, so if it is
    # never keyed it has no entity -- and the caller then falls back to
    # whatever the name matched, which is the merge hub. That left the defect
    # ~90% unfixed on the side where two thirds of it lived.
    keyed: list[tuple[dict, str, str, str]] = []
    for e in events:
        subject = (e.get("org_mention") or "").strip()
        if subject:
            key, basis = entity_key(e, ambiguous)
            if key:
                keyed.append((e, subject, key, basis))
        holder = (e.get("counterparty_mention") or "").strip()
        if holder:
            # A holder has only its name. `entity_key` on a synthetic row with
            # no identifier columns gives exactly the NAME:/AMB: key that
            # `for_mention` will later look up, so the two cannot diverge.
            hkey, hbasis = entity_key({"org_mention": holder}, ambiguous)
            if hkey:
                keyed.append((e, holder, hkey, hbasis))
                diag["holder_mentions_keyed"] += 1

    # The entity id is decided per KEY, in a pass of its own, before any row is
    # built. Deciding it per event let the same matricule map to two entities
    # -- one adopted, one not, depending on which mention was seen -- and then
    # the key index kept whichever sorted later, so adoption was imposed or
    # undone by sort order. A hard identifier is a hard identifier: if any
    # mention carrying it matches a seed organisation at identity grade, every
    # observation of it is that organisation.
    key_seed: dict[str, str] = {}
    for e, mention, key, basis in keyed:
        if basis in NON_IDENTITY or key in key_seed:
            continue
        m = seed_of(mention)
        if m.is_identity:
            key_seed[key] = m.org_id
    # Deterministic and total: a key maps to exactly one id, so the key index
    # cannot be multi-valued and `for_event` can never come back empty for a
    # key the build saw.
    key_id = {k: key_seed.get(k) or _eid(k)
              for k in {key for _e, _m, key, _b in keyed}}

    all_keys: dict[str, Counter] = defaultdict(Counter)
    for e, mention, key, basis in keyed:
        diag[f"events_{basis}"] += 1
        m = seed_of(mention)
        seed_id = m.org_id if m.is_identity else ""
        ent_id = key_id[key]
        if ent_id == key_seed.get(key):
            diag["adopted_seed_id"] += 1

        mention_entity[mention][ent_id] += 1
        all_keys[key][ent_id] += 1
        d = (e.get("event_date") or e.get("pub_date") or "")
        row = agg.get(ent_id)
        if row is None:
            agg[ent_id] = {
                "org_entity_id": ent_id, "entity_basis": basis,
                "entity_key": key, "labels": Counter([mention]),
                "mentions": {mention}, "n_events": 1,
                "first_seen": d, "last_seen": d,
                "matricule": key[3:] if basis == "matricule_fiscal" else "",
                "rc": key[3:] if basis == "registre_commerce" else "",
                "seed_org_id": seed_id,
                "seed_org_label": (idx.orgs[seed_id]["label"] if seed_id else ""),
                "seed_match_basis": m.basis,
                "seed_link_is_identity": int(bool(seed_id)),
                "is_identity": int(basis not in NON_IDENTITY),
                "issue_uid": e.get("issue_uid", ""),
            }
            continue
        row["n_events"] += 1
        row["labels"][mention] += 1
        row["mentions"].add(mention)
        if d:
            if not row["first_seen"] or d < row["first_seen"]:
                row["first_seen"] = d
            if d > row["last_seen"]:
                row["last_seen"] = d
        # An entity reached by several routes keeps the strongest seed link it
        # was given, so one generic-fuzzy mention cannot demote a firm that
        # also matched exactly.
        if seed_id and not row["seed_org_id"]:
            row["seed_org_id"] = seed_id
            row["seed_org_label"] = idx.orgs[seed_id]["label"]
            row["seed_match_basis"] = m.basis
            row["seed_link_is_identity"] = 1

    entities = []
    for row in agg.values():
        row["label"] = row["labels"].most_common(1)[0][0]
        row["n_mentions"] = len(row.pop("mentions"))
        row.pop("labels")
        entities.append(row)
    # One row per KEY, so every key an entity was reached by resolves to it.
    keys = []
    for key, counts in all_keys.items():
        ent_id, _n = counts.most_common(1)[0]
        keys.append({"entity_key": key, "org_entity_id": ent_id,
                     "entity_basis": agg[ent_id]["entity_basis"],
                     "n_events": sum(counts.values())})
    keys.sort(key=lambda r: r["entity_key"])
    n_keys_per_ent: Counter = Counter(r["org_entity_id"] for r in keys)
    for row in entities:
        row["n_keys"] = n_keys_per_ent.get(row["org_entity_id"], 1)
    entities.sort(key=lambda r: (-r["n_events"], r["org_entity_id"]))

    # A key that maps to two entities would make identity depend on sort
    # order, which is how adoption was silently undone in one direction and
    # imposed in the other.
    ambiguous_keys = [k for k, c in all_keys.items() if len(c) > 1]
    diag["keys_mapping_to_several_entities"] = len(ambiguous_keys)

    members = []
    for mention, counts in mention_entity.items():
        ent_id, n = counts.most_common(1)[0]
        m = seed_of(mention)
        members.append({
            "org_mention": mention, "org_entity_id": ent_id,
            "entity_basis": agg[ent_id]["entity_basis"],
            "n_events": sum(counts.values()),
            # This map is per MENTION and so is modal where a mention spans
            # several entities: `Société de Promotion Immobilière` carries 78
            # matricules. The per-event `entity_key` is the authoritative
            # assignment; this column says where the map cannot represent it,
            # rather than letting the modal choice pass as the whole truth.
            "n_entities_on_mention": len(counts),
            "mention_is_ambiguous": int(mention in ambiguous),
            "n_identifiers_on_mention": ambiguous.get(mention, 1),
            "seed_org_id": m.org_id if m.is_identity else "",
            "seed_match_basis": m.basis,
        })
    members.sort(key=lambda r: r["org_mention"])

    by_basis = Counter(r["entity_basis"] for r in entities)
    diag.update({f"entities_{k}": v for k, v in by_basis.items()})
    diag["entities"] = len(entities)
    diag["mentions_mapped"] = len(members)
    diag["ambiguous_mentions"] = len(ambiguous)
    diag["mentions_spanning_entities"] = sum(
        1 for r in members if r["n_entities_on_mention"] > 1)
    diag["name_keyed_share_pct"] = round(
        100 * by_basis.get("name", 0) / max(1, len(entities)), 1)
    # Coverage gained: entities reached by more than one spelling.
    diag["entities_joining_spellings"] = sum(
        1 for r in entities if r["n_mentions"] > 1)
    diag["spellings_joined"] = sum(
        r["n_mentions"] for r in entities if r["n_mentions"] > 1)
    diag["entity_keys"] = len(keys)
    return entities, keys, members, dict(diag)


# --------------------------------------------------------------------------- #
# the resolver the downstream stages use
# --------------------------------------------------------------------------- #

class OrgEntityResolver:
    """Maps an event to its organisation entity id.

    Downstream stages need the entity id per EVENT, not per mention: 1.6% of
    mentions carry more than one hard identifier, and for those the mention
    cannot say which firm an event is about while the event's own matricule
    can. So this recomputes the key rather than joining a 689,169-row map.

    `load()` returns an inert resolver when the entity tables are absent, so
    every stage still runs standalone and simply keeps its previous behaviour
    instead of half-applying the new identity.
    """

    def __init__(self, key_to_id: dict[str, str] | None = None,
                 ambiguous: dict[str, int] | None = None,
                 active: bool = False) -> None:
        self.key_to_id = key_to_id or {}
        self.ambiguous = ambiguous or {}
        self.active = active

    @classmethod
    def load(cls) -> "OrgEntityResolver":
        # `.gz` fallback on BOTH tables. This repo has already been burned by
        # a reader that followed the plain name only: the large tables are
        # committed gzipped, so in a clone the plain file is absent, and a
        # validator that silently read [] made a whole CI gate vacuous. Here
        # the failure would have been worse than vacuous -- `key_to_id` would
        # load while `ambiguous` came back empty, turning every AMB: key into
        # a NAME: key and binding 11,818 unattributable events to whichever
        # firm happened to own that name.
        keys = _read_table("org_entity_keys.csv")
        if not keys:
            # Older builds carried one key per entity row.
            keys = _read_table("org_entities.csv")
        if not keys:
            return cls(active=False)
        key_to_id = {r["entity_key"]: r["org_entity_id"] for r in keys
                     if r.get("entity_key")}
        ambiguous = {r["org_mention"]: int(r.get("n_identifiers_on_mention") or 2)
                     for r in _read_table("org_entity_members.csv")
                     if r.get("mention_is_ambiguous") == "1"}
        return cls(key_to_id, ambiguous, active=bool(key_to_id))

    def for_event(self, event: dict) -> str:
        """The entity id, or "" to leave the caller's own fallback in place."""
        if not self.active:
            return ""
        key, _basis = entity_key(event, self.ambiguous)
        return self.key_to_id.get(key, "") if key else ""

    def for_mention(self, mention: str) -> str:
        """The entity for a mention with no identifier of its own.

        An organisation named inside a clause -- the holder of a shareholding,
        say -- carries no matricule, because the identifiers printed in a
        notice belong to the firm the notice is about. So the only key
        available is the name, which is the weaker half of this layer and is
        recorded as such.
        """
        if not self.active or not mention:
            return ""
        key = parse_org(mention).match_key or mention.strip().upper()
        return self.key_to_id.get(f"NAME:{key}", "")


def threshold_sensitivity(events: list[dict], shares=(0.0002, 0.0005, 0.001)
                          ) -> list[dict]:
    """What the discriminating-token threshold buys, at three settings.

    The threshold is a judgement -- the narrowest observed gap is TROIS at 143
    distinct mentions against TUNISAIR at 22, about 6x -- so it is reported
    rather than asserted.

    The quantity reported is the number of seed nodes that would still hold
    ten or more distinct HARD IDENTIFIERS, which is what a merge actually is.
    Counting mentions per node instead would be misleading in the other
    direction: a real firm legitimately has many spellings, and a node with
    forty of them is not evidence of anything.
    """
    mentions = [e.get("org_mention") or "" for e in events]
    out = []
    for share in shares:
        spec = build_token_specificity(mentions, share=share)
        idx = load_seed(spec)
        refused = identity = 0
        ids_per_node: dict[str, set[str]] = defaultdict(set)
        match_of: dict[str, object] = {}
        for m in {x for x in mentions if x}:
            r = org_match(m, idx)
            match_of[m] = r
            if r.basis == "generic_fuzzy":
                refused += 1
            elif r.is_identity:
                identity += 1
        for e in events:
            m = (e.get("org_mention") or "").strip()
            r = match_of.get(m)
            if not r or not r.is_identity:
                continue
            for col, norm in (("org_mf", normalise_mf), ("org_rc", normalise_rc)):
                v = norm(e.get(col) or "")
                if v:
                    ids_per_node[r.org_id].add(f"{col}:{v}")
        out.append({"share": share, "df_threshold": spec.threshold,
                    "mentions_refused_generic": refused,
                    "mentions_identity_matched": identity,
                    "nodes_with_10plus_identifiers": sum(
                        1 for v in ids_per_node.values() if len(v) >= 10),
                    "worst_node_identifiers": max(
                        (len(v) for v in ids_per_node.values()), default=0)})
    return out


def _write(name: str, rows: list[dict], fields: list[str]) -> None:
    path = PROCESSED / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def run(sensitivity: bool = False) -> dict:
    ensure_dirs()
    events = read_events()
    spec = build_token_specificity(e.get("org_mention") or "" for e in events)
    idx = load_seed(spec)
    entities, keys, members, diag = build(events, idx)

    _write("org_entities.csv", entities, FIELDS_ENTITY)
    _write("org_entity_keys.csv", keys, FIELDS_KEY)
    _write("org_entity_members.csv", members, FIELDS_MEMBER)

    diag["token_df_threshold"] = spec.threshold
    diag["token_df_corpus_mentions"] = spec.n_mentions
    print("organisation entities")
    for k in ("token_df_corpus_mentions", "token_df_threshold",
              "entities", "entity_keys", "mentions_mapped",
              "holder_mentions_keyed", "adopted_seed_id",
              "keys_mapping_to_several_entities",
              "entities_matricule_fiscal", "entities_registre_commerce",
              "entities_name", "entities_ambiguous_mention",
              "name_keyed_share_pct", "ambiguous_mentions",
              "mentions_spanning_entities",
              "entities_joining_spellings", "spellings_joined"):
        if k in diag:
            print(f"  {k:<30} {diag[k]:>10,}")

    if sensitivity:
        print("\n  threshold sensitivity (the choice is a judgement):")
        for r in threshold_sensitivity(events):
            print(f"    share={r['share']:<8} df<{r['df_threshold']:<5} "
                  f"refused={r['mentions_refused_generic']:>7,} "
                  f"identity={r['mentions_identity_matched']:>7,} "
                  f"nodes>=10ids={r['nodes_with_10plus_identifiers']:>5,} "
                  f"worst={r['worst_node_identifiers']:>5,}")
    return diag


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Build organisation entities from hard identifiers")
    ap.add_argument("--sensitivity", action="store_true",
                    help="report hub counts at three thresholds")
    args = ap.parse_args(argv)
    run(sensitivity=args.sensitivity)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
