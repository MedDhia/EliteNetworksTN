"""Organisation entities, and the gate that stopped the merge hubs forming.

The bug these pin is worth stating precisely, because it produced a plausible
dataset rather than an obviously broken one. `fuzz.token_set_ratio` treats
CONTAINMENT as identity -- it returns 1.0 when one token set is a subset of
the other -- and `seed.py` mints an organisation id from the label with
legal-form words stripped. So a seed firm called "SOCIETE TROIS" became
`CO_TROIS` with `label_normalised = "TROIS"`, the French for three, and
absorbed every gazette mention containing that word until it was the
highest-degree organisation in the org-org layer at 1,003 tie endpoints.

Two things therefore have to hold at once, and a test for either alone would
let a regression through:

* a match resting only on common descriptors is refused as an identity;
* a match resting on a distinctive token is still accepted, because most
  single-token seed labels are proper names (SFBT, TUNISAIR) where
  containment matching is exactly right.
"""
import pytest

from elitenet.names import parse_org
from elitenet.orgentity import (OrgEntityResolver, ambiguous_mentions, build,
                                entity_key)
from elitenet.resolve import SeedIndex, build_token_specificity, org_match

# A corpus where BATIMENT is a common descriptor and SFBT is not, which is the
# real distribution: CONSULTING appears in 4,738 of 199,608 distinct mentions,
# SFBT in 3.
CORPUS = ([f"SOCIETE {i} DE BATIMENT" for i in range(600)]
          + ["SFBT TUNISIE"]
          + [f"ENTREPRISE {i}" for i in range(600)])


@pytest.fixture
def idx():
    ix = SeedIndex()
    for nid, label in (("CO_BATIMENT", "BATIMENT"), ("CO_SFBT", "SFBT")):
        ix.orgs[nid] = {"label": label, "label_normalised": label,
                        "node_type": "COMPANY"}
        o = parse_org(label)
        ix.org_by_norm[o.match_key].add(nid)
        for tok in o.content_tokens:
            if len(tok) > 3:
                ix.org_by_token[tok].add(nid)
    ix.token_spec = build_token_specificity(CORPUS)
    return ix


def ev(mention, mf="", rc="", date="2009-01-01"):
    return {"org_mention": mention, "org_mf": mf, "org_rc": rc,
            "event_date": date, "pub_date": date, "issue_uid": "i1"}


# --- the gate -------------------------------------------------------------- #

def test_a_generic_containment_match_is_not_an_identity(idx):
    """The exact case that built the hubs, and it still scores a perfect 1.0."""
    m = org_match("Comptoir Tunisien de Batiment", idx)
    assert m.score == 1.0, "containment still scores perfectly; that is the trap"
    assert m.basis == "generic_fuzzy"
    assert not m.is_identity
    assert m.org_id == ""
    # The candidate survives, so a refusal is auditable and the review queue
    # can still name what the mention came closest to.
    assert m.candidate_id == "CO_BATIMENT"


def test_a_distinctive_containment_match_is_still_an_identity(idx):
    """The gate must not cost legitimate matches.

    Most single-token seed labels are proper names, where a mention containing
    the label really is the same firm.
    """
    m = org_match("Societe SFBT Tunisie", idx)
    assert m.is_identity
    assert m.org_id == "CO_SFBT"
    assert m.basis == "discriminating_fuzzy"


def test_the_gate_is_inert_on_a_corpus_too_small_to_measure(idx):
    """Document frequency over a handful of mentions is noise, not evidence.

    Without this the gate would silently reject everything in any small
    fixture, which would make every other test here pass for the wrong reason.
    """
    idx.token_spec = build_token_specificity(["SOCIETE UNE DE BATIMENT"])
    assert not idx.token_spec.active
    assert org_match("Comptoir Tunisien de Batiment", idx).is_identity


def test_an_exact_match_is_never_gated(idx):
    """Only the fuzzy tier is in question; an exact normalised hit is identity
    whatever the token's frequency."""
    m = org_match("BATIMENT", idx)
    assert m.basis == "exact"
    assert m.is_identity and m.org_id == "CO_BATIMENT"


# --- the entity key -------------------------------------------------------- #

def test_the_matricule_wins_over_the_name(idx):
    key, basis = entity_key(ev("Comptoir Tunisien de Batiment", mf="1518656S"), {})
    assert basis == "matricule_fiscal"
    assert key == "MF:1518656S"


def test_the_rc_number_is_the_second_key(idx):
    key, basis = entity_key(ev("Une Societe", rc="B133371997"), {})
    assert basis == "registre_commerce"
    assert key == "RC:B133371997"


def test_a_firm_with_no_identifier_falls_back_to_its_name(idx):
    key, basis = entity_key(ev("Une Societe Quelconque"), {})
    assert basis == "name"
    assert key.startswith("NAME:")


# --- splitting and joining ------------------------------------------------- #

def test_two_spellings_sharing_a_matricule_become_one_entity(idx):
    """This is where the fix gains coverage rather than losing it: 19,795
    matricules cover more than one spelling in the corpus."""
    ents, _keys, _members, diag = build([
        ev("Comptoir Tunisien de Batiment", mf="1518656S"),
        ev("COMPTOIR TUNISIEN BATIMENT", mf="1518656/S/A/000"),
    ], idx)
    assert len(ents) == 1
    assert ents[0]["n_mentions"] == 2
    assert diag["spellings_joined"] == 2


def test_two_firms_sharing_a_generic_name_do_not_share_an_entity(idx):
    """The merge, from the other side. Both mentions contain BATIMENT and both
    used to land on CO_BATIMENT."""
    ents, _keys, _m, _d = build([
        ev("Comptoir Tunisien de Batiment", mf="1518656S"),
        ev("Dana Travaux de Batiment", mf="9999111X"),
    ], idx)
    assert len({e["org_entity_id"] for e in ents}) == 2
    assert all(e["org_entity_id"] != "CO_BATIMENT" for e in ents)
    assert all(not e["seed_org_id"] for e in ents), (
        "a generic fuzzy match must not be recorded as an identity-grade "
        "seed link")


def test_a_genuine_seed_organisation_adopts_the_seed_node_id(idx):
    """Not cosmetic: seed_edges.csv ties and every dyadic covariate are keyed
    on seed node ids, so an entity that did not adopt would sit on a different
    vertex from its own seed ties."""
    ents, _keys, _m, diag = build([ev("Societe SFBT Tunisie", mf="7240001W")], idx)
    assert ents[0]["org_entity_id"] == "CO_SFBT"
    assert ents[0]["seed_org_id"] == "CO_SFBT"
    assert diag["adopted_seed_id"] == 1


# --- what cannot be attributed --------------------------------------------- #

def test_a_mention_carrying_several_identifiers_is_flagged_not_guessed(idx):
    """`Société de Promotion Immobilière` carries 78 matricules in the corpus.
    An identifier-less event on such a mention names no particular firm."""
    events = [ev("Societe de Promotion Immobiliere", mf="1111111A"),
              ev("Societe de Promotion Immobiliere", mf="2222222B"),
              ev("Societe de Promotion Immobiliere")]
    amb = ambiguous_mentions(events)
    assert amb == {"Societe de Promotion Immobiliere": 2}

    key, basis = entity_key(events[2], amb)
    assert basis == "ambiguous_mention"

    ents, _keys, _m, _d = build(events, idx, amb)
    unattributed = [e for e in ents if e["entity_basis"] == "ambiguous_mention"]
    assert len(unattributed) == 1
    assert unattributed[0]["is_identity"] == 0, (
        "an unattributable observation must be retained but must not claim to "
        "identify a firm")
    # Retained, not dropped: three events, three entities, nothing lost.
    assert sum(e["n_events"] for e in ents) == 3


def test_nothing_is_dropped_and_every_mention_reaches_an_entity(idx):
    """The whole point of the change: identity is refined, data is not removed."""
    events = [ev("Comptoir Tunisien de Batiment", mf="1518656S"),
              ev("Dana Travaux de Batiment"),
              ev("Societe SFBT Tunisie", mf="7240001W"),
              ev("Une Societe Sans Identifiant")]
    ents, _keys, members, _d = build(events, idx)
    assert sum(e["n_events"] for e in ents) == len(events)
    assert {m["org_mention"] for m in members} == {
        e["org_mention"] for e in events}


# --- the resolver downstream stages use ------------------------------------ #

def test_the_resolver_is_inert_without_the_tables():
    """Every stage must still run standalone, keeping its old behaviour rather
    than half-applying the new identity."""
    r = OrgEntityResolver()
    assert not r.active
    assert r.for_event(ev("Anything", mf="1518656S")) == ""


def test_the_resolver_keys_an_event_on_its_own_identifier(idx):
    ents, _keys, _m, _d = build([ev("Comptoir Tunisien de Batiment", mf="1518656S")], idx)
    r = OrgEntityResolver({e["entity_key"]: e["org_entity_id"] for e in ents},
                          {}, active=True)
    # A different spelling, same matricule -> the same entity.
    assert r.for_event(ev("CTB", mf="1518656S")) == ents[0]["org_entity_id"]


# --- regressions from an adversarial review -------------------------------- #
# Three defects that each left the fix mostly ineffective while every earlier
# test still passed. They are pinned separately because each failed for a
# different reason and a single test would not have caught the others.

def test_adoption_honours_the_score_floor(idx):
    """`is_identity` checked the basis but not the score, while `resolve_org`
    applied the 0.88 floor separately. So a 0.52 name match adopted a seed id
    and put two firms with different matricules on one vertex -- a new merge
    hub, created by the stage whose purpose is to split them."""
    # The seed label must not be CONTAINED in the mention, or the score is
    # 1.0 by containment and the floor is not what is under test.
    label = "EL MOUNA SERVICES INTERNATIONAL"
    ix = SeedIndex()
    ix.orgs["CO_MOUNA"] = {"label": label, "label_normalised": label}
    o = parse_org(label)
    ix.org_by_norm[o.match_key].add("CO_MOUNA")
    for tok in o.content_tokens:
        if len(tok) > 3:
            ix.org_by_token[tok].add("CO_MOUNA")
    ix.token_spec = build_token_specificity(
        [f"FIRM {i}" for i in range(600)] + [label])

    weak = org_match("El Mouna Transport", ix)
    assert weak.basis == "discriminating_fuzzy"
    assert 0 < weak.score < 0.88, weak
    assert not weak.is_identity, (
        "a sub-threshold match must not be an identity anywhere, or the "
        "stages disagree about what counts as the same firm")

    ents, _k, _m, _d = build([
        ev("El Mouna Transport", mf="1111111A"),
        ev("Societe Immobiliere El Mouna", mf="2222222B"),
    ], ix)
    assert len({e["org_entity_id"] for e in ents}) == 2
    assert all(e["org_entity_id"] != "CO_MOUNA" for e in ents)


def test_a_holder_mention_gets_an_entity_of_its_own(idx):
    """Only `org_mention` was keyed, so the holder of a shareholding -- named
    inside a clause, carrying no identifier -- had no entity at all. The caller
    then fell back to whatever the name matched, which was the hub, leaving two
    thirds of the layer untouched by the fix."""
    e = ev("Societe SFBT Tunisie", mf="7240001W")
    e["counterparty_mention"] = "Comptoir Tunisien de Batiment"
    _ents, keys, members, diag = build([e], idx)
    assert diag["holder_mentions_keyed"] == 1
    assert "Comptoir Tunisien de Batiment" in {m["org_mention"] for m in members}
    r = OrgEntityResolver({k["entity_key"]: k["org_entity_id"] for k in keys},
                          {}, active=True)
    holder_ent = r.for_mention("Comptoir Tunisien de Batiment")
    assert holder_ent, "a holder with no identifier still needs an identity"
    assert holder_ent != "CO_BATIMENT", "and it must not be the hub"


def test_every_key_an_entity_was_reached_by_resolves_to_it(idx):
    """Adoption collapses several keys onto one id. Storing only the first one
    made `for_event` return "" for every other key -- indistinguishable from
    an inert resolver, so the caller silently applied the OLD identity for
    those events. That is the half-applied state the resolver is supposed to
    make impossible."""
    events = [ev("Societe SFBT Tunisie", mf="7240001W"),
              ev("SFBT", mf="1112223X"),
              ev("SFBT Tunisie")]
    _ents, keys, _m, _d = build(events, idx)
    r = OrgEntityResolver({k["entity_key"]: k["org_entity_id"] for k in keys},
                          {}, active=True)
    for e in events:
        assert r.for_event(e), (
            f"no entity for {e['org_mention']!r} with mf {e['org_mf']!r}; the "
            "caller would silently fall back to the pre-change identity")


def test_one_hard_identifier_maps_to_exactly_one_entity(idx):
    """Deciding the id per event let the same matricule map to two entities --
    one adopted, one not, depending which mention was seen -- and the key
    index then kept whichever sorted later, so adoption was imposed or undone
    by sort order. A hard identifier is a hard identifier."""
    events = [ev("Societe SFBT Tunisie", mf="7240001W"),      # identity-grade
              ev("Comptoir Tunisien de Batiment", mf="7240001W")]  # generic
    ents, keys, _m, diag = build(events, idx)
    assert diag["keys_mapping_to_several_entities"] == 0
    mf_keys = [k for k in keys if k["entity_key"] == "MF:7240001W"]
    assert len(mf_keys) == 1
    assert len({e["org_entity_id"] for e in ents
                if e["entity_basis"] == "matricule_fiscal"}) == 1
    # Any mention carrying it matching at identity grade settles the firm.
    assert mf_keys[0]["org_entity_id"] == "CO_SFBT"
