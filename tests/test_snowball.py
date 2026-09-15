"""Multi-seed snowballing and the address tier.

Both are additive tiers over a first pass that is left exactly as it was, and
both can propagate an error the single pass could not make. These tests pin
the guards that stop them: containment must not pass for identity, ambiguity
must block a snowball the same way it blocks a first-pass link, and a
domiciliation address must corroborate nothing.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from elitenet import orgentity as OE
from elitenet.names import parse_person
from elitenet import resolve as R


# --- org_match_within: the restricted matcher ----------------------------- #

def _idx(orgs=None, persons=None, person_orgs=None):
    idx = R.SeedIndex()
    for oid, label in (orgs or {}).items():
        idx.orgs[oid] = {"node_id": oid, "label": label,
                         "label_normalised": label.upper()}
    for pid, label in (persons or {}).items():
        idx.persons[pid] = {"node_id": pid, "label": label, "seed_degree": "1"}
    for pid, oids in (person_orgs or {}).items():
        idx.person_orgs[pid] = set(oids)
    return idx


def test_restricted_match_finds_the_persons_own_firm():
    idx = _idx(orgs={"CO_SFBT": "SFBT", "CO_POULINA": "POULINA"})
    oid, score = R.org_match_within("Société SFBT", {"CO_SFBT", "CO_POULINA"}, idx)
    assert oid == "CO_SFBT" and score >= R.SNOWBALL_ORG_FLOOR


def test_restricted_match_refuses_containment():
    """The whole reason this uses token_sort_ratio. A small candidate set gives
    the specificity gate no corpus statistics to work with, so the metric has
    to be the one that does not treat containment as identity."""
    idx = _idx(orgs={"CO_BATIMENT": "BATIMENT"})
    oid, _score = R.org_match_within(
        "comptoir tunisien de batiment et de travaux publics",
        {"CO_BATIMENT"}, idx)
    assert oid == ""


def test_restricted_match_refuses_an_unrelated_name():
    idx = _idx(orgs={"CO_SFBT": "SFBT"})
    assert R.org_match_within("Boulangerie du Nord", {"CO_SFBT"}, idx)[0] == ""


def test_restricted_match_needs_a_candidate_set():
    idx = _idx(orgs={"CO_SFBT": "SFBT"})
    assert R.org_match_within("SFBT", set(), idx) == ("", 0.0)
    assert R.org_match_within("", {"CO_SFBT"}, idx) == ("", 0.0)


# --- the snowball passes -------------------------------------------------- #

def _row(person, org, pid="", oid="", status="unresolved"):
    return {"mention_key": f"{person}||{org}", "person_mention": person,
            "org_mention": org, "resolved_person_id": pid,
            "resolved_person_label": pid, "resolved_org_id": oid,
            "resolved_org_label": oid, "link_status": status,
            "org_match_score": 0.0, "org_match_basis": "none",
            "score": 0.0, "s_name": 0.0, "s_org": 0.0, "s_mf": 0.0,
            "s_cooccur": 0.0, "s_role": 0.0, "margin_to_runner_up": 0.0,
            "resolve_pass": 0, "snowball_basis": ""}


def _dyad(person, org, blocks=("B1",)):
    return {"person_mention": person, "org_mention": org, "org_mf": "",
            "org_rc": "", "n_events": 1, "dates": [], "roles": set(),
            "blocks": set(blocks), "quote": "", "issue_uid": "",
            "folio_page": "", "collection": "", "year": "", "issue": ""}


def test_a_named_person_names_their_firm():
    """Pass 1. The person resolved, the organisation did not, and the person's
    own seed organisations are a candidate set of three rather than ten
    thousand."""
    idx = _idx(orgs={"CO_SFBT": "SFBT"}, persons={"P_A": "Ali Ben Salah"},
               person_orgs={"P_A": {"CO_SFBT"}})
    rows = [_row("Ali Ben Salah", "Societe SFBT", "P_A", status="resolved")]
    stats = R.snowball(rows, {("Ali Ben Salah", "Societe SFBT"):
                              _dyad("Ali Ben Salah", "Societe SFBT")},
                       idx, {})
    assert stats["org_named_by_person"] == 1
    assert rows[0]["resolved_org_id"] == "CO_SFBT"
    assert rows[0]["org_match_basis"] == "person_anchored"
    assert rows[0]["snowball_basis"] == "person_names_org"
    assert rows[0]["resolve_pass"] == 1
    # The person's own status is untouched: it was already resolved.
    assert rows[0]["link_status"] == "resolved"


def test_a_newly_named_firm_names_its_people():
    """Pass 2, which is what makes this a snowball rather than one extra rule:
    the anchor pass 1 created is what names the second person."""
    idx = _idx(orgs={"CO_SFBT": "SFBT"},
               persons={"P_A": "Ali Ben Salah", "P_B": "Leila Trabelsi"},
               person_orgs={"P_A": {"CO_SFBT"}, "P_B": {"CO_SFBT"}})
    idx.org_persons["CO_SFBT"] = {"P_A", "P_B"}
    idx.by_match_key["BEN SALAH ALI"] = {"P_A"}
    idx.by_match_key["TRABELSI LEILA"] = {"P_B"}
    rows = [_row("Ali Ben Salah", "Societe SFBT", "P_A", status="resolved"),
            _row("Leila Trabelsi", "Societe SFBT")]
    dyads = {("Ali Ben Salah", "Societe SFBT"): _dyad("Ali Ben Salah", "Societe SFBT"),
             ("Leila Trabelsi", "Societe SFBT"): _dyad("Leila Trabelsi", "Societe SFBT")}
    stats = R.snowball(rows, dyads, idx, {"B1": {"Ali Ben Salah", "Leila Trabelsi"}})
    assert stats["org_names_person"] == 1
    assert rows[1]["link_status"] == "snowball"
    assert rows[1]["resolved_person_id"] == "P_B"
    assert rows[1]["snowball_basis"] == "org_names_person"


def test_pass_zero_rows_are_never_downgraded():
    idx = _idx(orgs={"CO_SFBT": "SFBT"}, persons={"P_A": "Ali Ben Salah"},
               person_orgs={"P_A": {"CO_SFBT"}})
    rows = [_row("Ali Ben Salah", "Societe SFBT", "P_A", "CO_SFBT", "resolved")]
    R.snowball(rows, {("Ali Ben Salah", "Societe SFBT"):
                      _dyad("Ali Ben Salah", "Societe SFBT")}, idx, {})
    assert rows[0]["link_status"] == "resolved"
    assert rows[0]["resolve_pass"] == 0
    assert rows[0]["resolved_org_id"] == "CO_SFBT"


def test_ambiguity_blocks_a_snowball():
    """A snowball that guesses between two equally good candidates propagates
    the guess into every later pass, so it applies the same margin rule the
    first pass does."""
    idx = _idx(orgs={"CO_SFBT": "SFBT"},
               persons={"P_A": "Mohamed Trabelsi", "P_B": "Mohamed Trabelsi"},
               person_orgs={"P_A": {"CO_SFBT"}, "P_B": {"CO_SFBT"}})
    idx.org_persons["CO_SFBT"] = {"P_A", "P_B"}
    idx.by_match_key["TRABELSI MOHAMED"] = {"P_A", "P_B"}
    rows = [_row("Mohamed Trabelsi", "SFBT", "", "CO_SFBT")]
    stats = R.snowball(rows, {("Mohamed Trabelsi", "SFBT"):
                              _dyad("Mohamed Trabelsi", "SFBT")}, idx, {})
    assert rows[0]["link_status"] == "unresolved"
    assert stats.get("snowball_blocked_by_ambiguity", 0) >= 1


def test_colleagues_name_a_person_only_when_two_agree():
    """Pass 3. One named colleague is a coincidence; two tied to the same firm
    in the seed is a board."""
    idx = _idx(orgs={"CO_SFBT": "SFBT"},
               persons={"P_A": "Ali Ben Salah", "P_B": "Leila Trabelsi",
                        "P_C": "Sami Gharbi"},
               person_orgs={"P_A": {"CO_SFBT"}, "P_B": {"CO_SFBT"},
                            "P_C": {"CO_SFBT"}})
    idx.org_persons["CO_SFBT"] = {"P_A", "P_B", "P_C"}
    for key, pid in (("BEN SALAH ALI", "P_A"), ("TRABELSI LEILA", "P_B"),
                     ("GHARBI SAMI", "P_C")):
        idx.by_match_key[key] = {pid}
    block = {"B1": {"Ali Ben Salah", "Leila Trabelsi", "Sami Gharbi"}}
    # No organisation mention at all -- the property-notice case.
    rows = [_row("Ali Ben Salah", "", "P_A", status="resolved"),
            _row("Leila Trabelsi", "", "P_B", status="resolved"),
            _row("Sami Gharbi", "")]
    dyads = {(r["person_mention"], ""): _dyad(r["person_mention"], "") for r in rows}
    stats = R.snowball(rows, dyads, idx, block)
    assert stats["colleagues_name_person"] == 1
    assert rows[2]["link_status"] == "snowball"
    assert rows[2]["snowball_basis"] == "colleagues_name_person"


def test_one_colleague_is_not_enough():
    idx = _idx(orgs={"CO_SFBT": "SFBT"},
               persons={"P_A": "Ali Ben Salah", "P_C": "Sami Gharbi"},
               person_orgs={"P_A": {"CO_SFBT"}, "P_C": {"CO_SFBT"}})
    idx.org_persons["CO_SFBT"] = {"P_A", "P_C"}
    idx.by_match_key["BEN SALAH ALI"] = {"P_A"}
    idx.by_match_key["GHARBI SAMI"] = {"P_C"}
    rows = [_row("Ali Ben Salah", "", "P_A", status="resolved"),
            _row("Sami Gharbi", "")]
    dyads = {(r["person_mention"], ""): _dyad(r["person_mention"], "") for r in rows}
    R.snowball(rows, dyads, idx, {"B1": {"Ali Ben Salah", "Sami Gharbi"}})
    assert rows[1]["link_status"] == "unresolved"


def test_a_tie_between_two_organisations_is_no_anchor():
    idx = _idx(orgs={"CO_A": "ALPHA", "CO_B": "BETA"},
               persons={"P_A": "Ali Ben Salah", "P_B": "Leila Trabelsi"},
               person_orgs={"P_A": {"CO_A"}, "P_B": {"CO_B"}})
    person_of = {"Ali Ben Salah": "P_A", "Leila Trabelsi": "P_B"}
    block = {"B1": {"Ali Ben Salah", "Leila Trabelsi", "Sami Gharbi"}}
    assert R._comember_anchor(_dyad("Sami Gharbi", ""), "Sami Gharbi",
                              block, person_of, idx) == ""


def test_the_snowball_stops_when_a_pass_adds_nothing():
    idx = _idx(orgs={"CO_SFBT": "SFBT"}, persons={"P_A": "Ali Ben Salah"},
               person_orgs={"P_A": {"CO_SFBT"}})
    rows = [_row("Ali Ben Salah", "SFBT", "P_A", "CO_SFBT", "resolved")]
    stats = R.snowball(rows, {("Ali Ben Salah", "SFBT"):
                              _dyad("Ali Ben Salah", "SFBT")}, idx, {})
    assert stats["pass_1_links"] == 0
    assert "pass_2_links" not in stats


# --- the address tier ----------------------------------------------------- #

def _keyed(*specs):
    """(event, mention, key, basis) tuples from (mention, address) pairs."""
    return [({"org_address": addr}, mention, f"NAME:{mention.upper()}", "name")
            for mention, addr in specs]


def test_a_shared_seat_joins_two_spellings_of_one_firm():
    """The residual error this tier exists for: two spellings of one
    identifier-less firm stay apart and understate its degree."""
    keyed = _keyed(("Societe Hexabyte Tunisie", "12 rue de Rome 1001 Tunis"),
                   ("Hexabyte Tunisie SA", "12 Rue de Rome, 1001 Tunis"))
    key_id = {k: OE._eid(k) for _e, _m, k, _b in keyed}
    before = dict(key_id)
    n, merged = OE._merge_on_address(keyed, key_id, {}, Counter())
    assert n == 1 and len(merged) == 1
    assert len(set(key_id.values())) == 1
    assert set(before.values()) != set(key_id.values())


def test_two_different_firms_at_one_seat_stay_apart():
    """Corroboration, never identity on its own: a building holds two firms."""
    keyed = _keyed(("Boulangerie du Nord", "12 rue de Rome 1001 Tunis"),
                   ("Cimenterie du Sud", "12 rue de Rome 1001 Tunis"))
    key_id = {k: OE._eid(k) for _e, _m, k, _b in keyed}
    n, _merged = OE._merge_on_address(keyed, key_id, {}, Counter())
    assert n == 0 and len(set(key_id.values())) == 2


def test_a_domiciliation_address_corroborates_nothing():
    """The measured tail: one address in this corpus carries 253 firms. An
    address borne by more than ADDR_MAX_FIRMS says only that a registered
    agent works there."""
    keyed = _keyed(*[(f"Societe Alpha {i}", "6 rue ibn hazm cite jardins 1002 tunis")
                     for i in range(OE.ADDR_MAX_FIRMS + 1)])
    key_id = {k: OE._eid(k) for _e, _m, k, _b in keyed}
    diag: Counter = Counter()
    n, _merged = OE._merge_on_address(keyed, key_id, {}, diag)
    assert n == 0
    assert diag["address_groups_too_broad"] == 1


def test_a_bare_town_name_corroborates_nothing():
    keyed = _keyed(("Societe Hexabyte Tunisie", "Tunis"),
                   ("Hexabyte Tunisie SA", "Tunis"))
    key_id = {k: OE._eid(k) for _e, _m, k, _b in keyed}
    n, _merged = OE._merge_on_address(keyed, key_id, {}, Counter())
    assert n == 0


def test_a_parent_and_its_subsidiary_at_one_seat_stay_apart():
    """The failure mode the containment-safe metric exists for. "Poulina" is
    contained in "Poulina Group Holding" and they share a head office, and they
    are two firms."""
    keyed = _keyed(("Poulina", "34 rue de Marseille 1001 Tunis"),
                   ("Poulina Group Holding Industries", "34 rue de Marseille 1001 Tunis"))
    key_id = {k: OE._eid(k) for _e, _m, k, _b in keyed}
    n, _merged = OE._merge_on_address(keyed, key_id, {}, Counter())
    assert n == 0


def test_an_identified_firm_is_never_merged_on_its_address():
    """A key carrying a matricule is already identified, and two different
    matricules at one address are two firms sharing a building."""
    keyed = [({"org_address": "12 rue de Rome 1001 Tunis"}, "Hexabyte",
              "MF:111111A", "matricule_fiscal"),
             ({"org_address": "12 rue de Rome 1001 Tunis"}, "Hexabyte SA",
              "MF:222222B", "matricule_fiscal")]
    key_id = {k: OE._eid(k) for _e, _m, k, _b in keyed}
    n, _merged = OE._merge_on_address(keyed, key_id, {}, Counter())
    assert n == 0 and len(set(key_id.values())) == 2


def test_a_merge_keeps_the_adopted_seed_id():
    """A merge may add spellings to a seed node; it must never rename one."""
    keyed = _keyed(("Societe Hexabyte Tunisie", "12 rue de Rome 1001 Tunis"),
                   ("Hexabyte Tunisie SA", "12 rue de Rome 1001 Tunis"))
    k1, k2 = [k for _e, _m, k, _b in keyed]
    # k2 sorts first, so without the seed rule it would win the union.
    key_seed = {k1: "CO_HEXABYTE"}
    key_id = {k1: "CO_HEXABYTE", k2: OE._eid(k2)}
    n, _merged = OE._merge_on_address(keyed, key_id, key_seed, Counter())
    assert n == 1
    assert key_id[k1] == key_id[k2] == "CO_HEXABYTE"


def test_the_merge_is_independent_of_iteration_order():
    specs = [("Societe Hexabyte Tunisie", "12 rue de Rome 1001 Tunis"),
             ("Hexabyte Tunisie SA", "12 rue de Rome 1001 Tunis"),
             ("Hexabyte Tunisie", "12 rue de Rome 1001 Tunis")]
    results = []
    for order in (specs, list(reversed(specs))):
        keyed = _keyed(*order)
        key_id = {k: OE._eid(k) for _e, _m, k, _b in keyed}
        OE._merge_on_address(keyed, key_id, {}, Counter())
        results.append(set(key_id.values()))
    assert results[0] == results[1] and len(results[0]) == 1


# --- the residence discriminator on the inference tier -------------------- #

NAME = "Mohamed Trabelsi"
KEY = parse_person(NAME).match_key


def _rarity(*residences):
    idx = _idx(persons={"P_A": NAME})
    idx.by_match_key[KEY] = {"P_A"}
    return R.build_name_rarity(idx, [NAME], [(NAME, a) for a in residences])


def test_two_addresses_refuse_a_name_rarity_inference():
    """A unique spelling says nobody else is written that way; it says nothing
    about how many people are. "Mohamed Trabelsi" at Sfax and at Ariana is one
    spelling and two men, and the inference tier has no anchor to tell it so."""
    assert not _rarity("12 rue de rome tunis",
                       "34 avenue farhat hached sfax").is_unique(KEY)


def test_one_address_leaves_the_inference_standing():
    assert _rarity("12 rue de rome tunis").is_unique(KEY)


def test_no_address_leaves_the_inference_standing():
    """Most mentions state no residence. Absence must not be read as conflict,
    or the tier would collapse to nothing."""
    assert _rarity().is_unique(KEY)


# --- the identifier bridge ------------------------------------------------ #
# A name propagates a resemblance; a matricule fiscal propagates an identity.
# It is the safest edge in the snowball and the one it was not using: the map
# was built once, before the first pass, and seeded only from organisations
# named by an identity-grade NAME match.

def _row_id(person, org, mf="", rc="", pid="", oid="", status="unresolved"):
    r = _row(person, org, pid, oid, status)
    r["org_mf"], r["org_rc"] = mf, rc
    return r


def _dyad_id(person, org, mf="", rc="", blocks=("B1",)):
    d = _dyad(person, org, blocks)
    d["org_mf"], d["org_rc"] = mf, rc
    return d


def test_a_matricule_learned_in_one_filing_names_the_firm_in_another():
    """The gap this closes. One filing prints the firm's name readably and its
    matricule; another prints only the matricule. Nothing but the identifier
    connects them."""
    idx = _idx(orgs={"CO_SFBT": "SFBT"}, persons={"P_A": "Ali Ben Salah"},
               person_orgs={"P_A": {"CO_SFBT"}})
    rows = [_row_id("Ali Ben Salah", "SFBT", mf="111111A",
                    pid="P_A", oid="CO_SFBT", status="resolved"),
            _row_id("Leila Trabelsi", "Ste illisible XYZ", mf="111111A")]
    dyads = {("Ali Ben Salah", "SFBT"): _dyad_id("Ali Ben Salah", "SFBT", mf="111111A"),
             ("Leila Trabelsi", "Ste illisible XYZ"):
                 _dyad_id("Leila Trabelsi", "Ste illisible XYZ", mf="111111A")}
    stats = R.snowball(rows, dyads, idx, {})
    assert stats["org_named_by_identifier"] == 1
    assert rows[1]["resolved_org_id"] == "CO_SFBT"
    assert rows[1]["org_match_basis"] == "identifier_bridge"
    assert rows[1]["snowball_basis"] == "identifier_names_org"


def test_an_identifier_earned_by_person_anchoring_then_propagates():
    """The compounding step. The firm is named in pass 1 by its officer, its
    matricule enters the map, and a third filing carrying only that matricule
    is reached in pass 2. Seeding the map once, before the loop, could never
    do this."""
    idx = _idx(orgs={"CO_SFBT": "SFBT"}, persons={"P_A": "Ali Ben Salah"},
               person_orgs={"P_A": {"CO_SFBT"}})
    rows = [_row_id("Ali Ben Salah", "Societe SFBT", mf="222222B",
                    pid="P_A", status="resolved"),
            _row_id("Leila Trabelsi", "Ste illisible", mf="222222B")]
    dyads = {("Ali Ben Salah", "Societe SFBT"):
                 _dyad_id("Ali Ben Salah", "Societe SFBT", mf="222222B"),
             ("Leila Trabelsi", "Ste illisible"):
                 _dyad_id("Leila Trabelsi", "Ste illisible", mf="222222B")}
    stats = R.snowball(rows, dyads, idx, {})
    # Pass 1 names the firm from its officer; pass 2 bridges on the matricule.
    assert stats["org_named_by_person"] == 1
    assert stats["org_named_by_identifier"] == 1
    assert rows[1]["resolved_org_id"] == "CO_SFBT"
    assert rows[1]["resolve_pass"] == 2


def test_an_rc_number_bridges_to_a_firm_known_by_its_matricule():
    """One flat map, not one per column: a firm identified by its matricule in
    one filing is reachable by its RC number in another, because a filing
    carrying both links the two values."""
    idx = _idx(orgs={"CO_SFBT": "SFBT"}, persons={"P_A": "Ali Ben Salah"},
               person_orgs={"P_A": {"CO_SFBT"}})
    rows = [_row_id("Ali Ben Salah", "SFBT", mf="333333C", rc="B1231999",
                    pid="P_A", oid="CO_SFBT", status="resolved"),
            _row_id("Leila Trabelsi", "Ste illisible", rc="B1231999")]
    dyads = {("Ali Ben Salah", "SFBT"):
                 _dyad_id("Ali Ben Salah", "SFBT", mf="333333C", rc="B1231999"),
             ("Leila Trabelsi", "Ste illisible"):
                 _dyad_id("Leila Trabelsi", "Ste illisible", rc="B1231999")}
    R.snowball(rows, dyads, idx, {})
    assert rows[1]["resolved_org_id"] == "CO_SFBT"


def test_one_identifier_on_two_firms_names_neither():
    """4,461 identifier values in this corpus sit on more than one
    organisation node. Taking the modal side would bury exactly the signal
    that says a resolution merged two firms, so a conflicting value is deleted
    and blacklisted."""
    idx = _idx(orgs={"CO_A": "ALPHA", "CO_B": "BETA"},
               persons={"P_A": "Ali Ben Salah", "P_B": "Sami Gharbi"},
               person_orgs={"P_A": {"CO_A"}, "P_B": {"CO_B"}})
    rows = [_row_id("Ali Ben Salah", "ALPHA", mf="444444D",
                    pid="P_A", oid="CO_A", status="resolved"),
            _row_id("Sami Gharbi", "BETA", mf="444444D",
                    pid="P_B", oid="CO_B", status="resolved"),
            _row_id("Leila Trabelsi", "Ste illisible", mf="444444D")]
    dyads = {("Ali Ben Salah", "ALPHA"): _dyad_id("Ali Ben Salah", "ALPHA", mf="444444D"),
             ("Sami Gharbi", "BETA"): _dyad_id("Sami Gharbi", "BETA", mf="444444D"),
             ("Leila Trabelsi", "Ste illisible"):
                 _dyad_id("Leila Trabelsi", "Ste illisible", mf="444444D")}
    stats = R.snowball(rows, dyads, idx, {})
    assert stats["identifier_conflicts"] >= 1
    assert stats["identifiers_refused_as_conflicting"] >= 1
    assert rows[2]["resolved_org_id"] == ""


def test_two_identifiers_disagreeing_on_one_filing_name_neither():
    """A filing whose matricule and RC number point at two organisations is
    the merge signal orgattrs reports. Guessing here would bury it."""
    idx = _idx(orgs={"CO_A": "ALPHA", "CO_B": "BETA"},
               persons={"P_A": "Ali Ben Salah", "P_B": "Sami Gharbi"},
               person_orgs={"P_A": {"CO_A"}, "P_B": {"CO_B"}})
    rows = [_row_id("Ali Ben Salah", "ALPHA", mf="555555E",
                    pid="P_A", oid="CO_A", status="resolved"),
            _row_id("Sami Gharbi", "BETA", rc="B9992001",
                    pid="P_B", oid="CO_B", status="resolved"),
            _row_id("Leila Trabelsi", "Ste illisible", mf="555555E", rc="B9992001")]
    dyads = {("Ali Ben Salah", "ALPHA"): _dyad_id("Ali Ben Salah", "ALPHA", mf="555555E"),
             ("Sami Gharbi", "BETA"): _dyad_id("Sami Gharbi", "BETA", rc="B9992001"),
             ("Leila Trabelsi", "Ste illisible"):
                 _dyad_id("Leila Trabelsi", "Ste illisible",
                          mf="555555E", rc="B9992001")}
    stats = R.snowball(rows, dyads, idx, {})
    assert stats["identifier_disagreement"] >= 1
    assert rows[2]["resolved_org_id"] == ""


def test_the_pass_zero_map_seeds_the_snowball():
    """What pass 0 learned from identity-grade name matches is available from
    round one, rather than only to whatever named it."""
    idx = _idx(orgs={"CO_SFBT": "SFBT"})
    rows = [_row_id("Leila Trabelsi", "Ste illisible", mf="666666F")]
    dyads = {("Leila Trabelsi", "Ste illisible"):
                 _dyad_id("Leila Trabelsi", "Ste illisible", mf="666666F")}
    stats = R.snowball(rows, dyads, idx, {},
                       id_to_org={"org_mf": {"666666F": "CO_SFBT"}, "org_rc": {}})
    assert stats["identifiers_seeded"] == 1
    assert rows[0]["resolved_org_id"] == "CO_SFBT"


def test_a_conflict_in_the_seeded_map_is_refused():
    idx = _idx(orgs={"CO_A": "ALPHA", "CO_B": "BETA"})
    rows = [_row_id("Leila Trabelsi", "Ste illisible", mf="777777G", rc="777777G")]
    dyads = {("Leila Trabelsi", "Ste illisible"):
                 _dyad_id("Leila Trabelsi", "Ste illisible",
                          mf="777777G", rc="777777G")}
    R.snowball(rows, dyads, idx, {},
               id_to_org={"org_mf": {"777777G": "CO_A"},
                          "org_rc": {"777777G": "CO_B"}})
    assert rows[0]["resolved_org_id"] == ""


def test_a_pass_that_only_learns_identifiers_does_not_end_the_loop():
    """The convergence test has to count identifiers as progress. A pass that
    named nothing but learned a matricule is exactly what the next pass fires
    on, and breaking there would stop one round short."""
    idx = _idx(orgs={"CO_SFBT": "SFBT"}, persons={"P_A": "Ali Ben Salah"},
               person_orgs={"P_A": {"CO_SFBT"}})
    rows = [_row_id("Ali Ben Salah", "Societe SFBT", mf="888888H",
                    pid="P_A", status="resolved")]
    dyads = {("Ali Ben Salah", "Societe SFBT"):
                 _dyad_id("Ali Ben Salah", "Societe SFBT", mf="888888H")}
    stats = R.snowball(rows, dyads, idx, {})
    # Pass 1 names the org and harvests its matricule; pass 2 adds nothing.
    assert stats["pass_1_identifiers_added"] == 1
    assert "pass_2_links" in stats
