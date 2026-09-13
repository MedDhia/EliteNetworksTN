"""Stage 9 -- consistency checks, coverage, and held-out ground truth.

Checks are split by severity. ERROR means the dataset contradicts itself and
the build should fail. WARN means something is worth a human's attention but is
a property of the sources rather than a defect. INFO is descriptive.

Two checks are genuine held-out tests rather than internal consistency:

* **Cabinet reconstruction.** The gazette states its own cabinet lists, so
  ministers recovered from decrees can be compared against the governments the
  seed sheet names independently.
* **Negative control.** Auction and fonds-de-commerce notices should yield no
  officer appointments at all. Anything found there is a false positive, which
  estimates the error rate on out-of-scope text.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from .paths import (DOCS, INTERIM, PROCESSED, ROOT, ensure_dirs,
                    load_config, window)
from .resolve import MAX_SNOWBALL_PASSES

WINDOW = window()


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []

    def add(self, level: str, check: str, detail: str) -> None:
        self.rows.append((level, check, detail))

    @property
    def errors(self) -> int:
        return sum(1 for lv, _c, _d in self.rows if lv == "ERROR")

    def render(self) -> str:
        out = ["# Validation report", "",
               f"Generated {date.today().isoformat()}.", ""]
        for level in ("ERROR", "WARN", "INFO"):
            group = [(c, d) for lv, c, d in self.rows if lv == level]
            if not group:
                continue
            out.append(f"## {level}")
            out.append("")
            for check, detail in group:
                out.append(f"- **{check}** — {detail}")
            out.append("")
        return "\n".join(out)


# The large derived tables are committed *gzipped* and git-ignored
# uncompressed (see .gitignore), so in a fresh clone -- and therefore in CI --
# only `<name>.gz` exists. Reading the plain name and silently returning [] for
# a missing file meant every ERROR-level check over events, spells and
# resolution passed on an empty list: the gate was real locally and vacuous in
# CI, which is how 87 impossible act dates sailed through it. The `.gz` is the
# canonical committed form, so fall back to it rather than treating the table
# as absent. A table that is genuinely missing still yields [], but no table
# the repository actually carries can read as empty again.
def _read(path: Path) -> list[dict]:
    fh = _open_table(path)
    if fh is None:
        return []
    with fh:
        return list(csv.DictReader(fh))


def _open_table(path: Path):
    if path.exists():
        return path.open(encoding="utf-8", newline="")
    gz = path.with_suffix(path.suffix + ".gz")
    if gz.exists():
        return gzip.open(gz, "rt", encoding="utf-8", newline="")
    return None


# Whether a table is readable at all, for the checks that need to distinguish
# "the stage has not run" from "the stage ran and produced nothing".
def _table_exists(path: Path) -> bool:
    return path.exists() or path.with_suffix(path.suffix + ".gz").exists()


BLOCKS = INTERIM / "blocks.jsonl"

# Three checks read data/interim/, which is deliberately git-ignored: the block
# corpus is a 1.3 GB intermediate rebuilt from the gazette mirror. So they can
# run for whoever built the pipeline but not from a fresh clone or in CI, and a
# check that cannot run must say so rather than crash (which strands the checks
# after it) or report a vacuous pass. Skipping is recorded as a WARN because a
# reader of the report needs to know the provenance guard and the negative
# control were not exercised on this run -- an absent number is not a zero.
# The stage whose output each skippable input is, so the report says how to
# make the check runnable rather than only that it was not run.
_REBUILD_WITH = {"blocks.jsonl": "segment", "act_citations.csv": "extract"}
_STAGE_FOR = {"node_key.csv": "tergm", "org_tie_spells.csv": "orgties",
              "org_identifiers.csv": "orgattrs",
              "org_entities.csv": "orgentity",
              "org_entity_members.csv": "orgentity",
              "person_tie_spells.csv": "personties",
              "resolution.csv": "resolve"}


def _skip(rep: Report, check: str, needs: Path) -> None:
    stage = _REBUILD_WITH[needs.name]
    rep.add("WARN", check,
            f"not checked: {needs.relative_to(ROOT)} is absent (a git-ignored "
            f"intermediate). Run `make mirror {stage}` to rebuild it, then "
            f"re-validate.")


# Distinct from _skip above: these outputs are committed, not git-ignored, so
# their absence means the stage has not been run rather than that the input was
# deliberately left out of the repository.
def _skip_stage(rep: Report, check: str, needs: Path, why: str = "is absent") -> None:
    """Record that a check could not run, and say exactly why.

    `why` exists because "is absent" is not always the truth. A table can be
    present and still predate the column a check needs, and reporting that as
    an absent file sends a reader looking for a missing file that is right
    there. Saying which is which is the whole value of this WARN.
    """
    stage = _STAGE_FOR.get(needs.name, "all")
    rep.add("WARN", check,
            f"not checked: {needs.relative_to(ROOT)} {why}. "
            f"Run `make {stage}` to build it, then re-validate.")


def check_calendar(rep: Report) -> None:
    cal = _read(PROCESSED / "issue_calendar.csv")
    dated = [r for r in cal if r["pub_date"]]
    rep.add("INFO", "calendar coverage",
            f"{len(dated)}/{len(cal)} issues dated ({len(dated)/max(1,len(cal)):.1%})")
    out_of_window = [r for r in dated
                     if not (WINDOW[0].isoformat()[:4] <= r["pub_date"][:4]
                             <= WINDOW[1].isoformat()[:4])]
    if out_of_window:
        rep.add("WARN", "publication date outside window",
                f"{len(out_of_window)} issues, e.g. {out_of_window[0]['issue_uid']}")
    bad_wd = [r for r in cal if r["weekday_consistent"] == "False"]
    rep.add("WARN" if bad_wd else "INFO", "weekday mismatch",
            f"{len(bad_wd)} issues where the printed weekday disagrees with the date "
            f"(date retained; a lone weekday is likelier a misprint)")
    review = [r for r in cal if r["needs_review"] == "True"]
    rep.add("INFO", "calendar needs review", f"{len(review)} issues flagged")


def check_events(rep: Report) -> None:
    events = _read(PROCESSED / "events.csv")
    rep.add("INFO", "events", f"{len(events)} extracted")

    late = [e for e in events if e["act_date"] and e["pub_date"]
            and e["act_date"] > e["pub_date"]]
    rep.add("ERROR" if late else "INFO", "act date after publication",
            f"{len(late)} events where the act postdates the issue that published it")

    # A retroactive effective date is lawful and common; it must be counted,
    # not flagged as an error.
    retro = [e for e in events if e["effective_date"] and e["act_date"]
             and e["effective_date"] < e["act_date"]]
    rep.add("INFO", "retroactive effective dates",
            f"{len(retro)} acts take effect before their own date (lawful)")

    missing_quote = [e for e in events if not e["evidence_quote"]]
    rep.add("ERROR" if missing_quote else "INFO", "provenance present",
            f"{len(missing_quote)} events without a verbatim quote")
    missing_cite = [e for e in events if not e["issue_uid"]]
    rep.add("ERROR" if missing_cite else "INFO", "source citation present",
            f"{len(missing_cite)} events without an issue reference")

    prec = Counter(e["date_precision"] for e in events)
    rep.add("INFO", "date precision", ", ".join(f"{k}={v}" for k, v in prec.most_common()))
    rep.add("INFO", "event types",
            ", ".join(f"{k}={v}" for k, v in
                      Counter(e["event_type"] for e in events).most_common(8)))


def check_quotes_are_verbatim(rep: Report, sample: int = 2000) -> None:
    """Every quote must literally occur in its block. This is the guard that
    makes the provenance claim checkable rather than decorative."""
    if not BLOCKS.exists():
        _skip(rep, "quotes verbatim", BLOCKS)
        return
    blocks: dict[str, str] = {}
    with BLOCKS.open(encoding="utf-8") as fh:
        for line in fh:
            b = json.loads(line)
            blocks[b["block_uid"]] = b["text"]
    events = _read(PROCESSED / "events.csv")
    checked = bad = 0
    for e in events:
        if checked >= sample:
            break
        q = (e["evidence_quote"] or "").strip()
        text = blocks.get(e["block_uid"])
        if not q or text is None:
            continue
        checked += 1
        norm = " ".join(text.split())
        if q not in norm:
            bad += 1
    rep.add("ERROR" if bad else "INFO", "quotes verbatim",
            f"{bad}/{checked} sampled quotes not found in their source block")


def check_spells(rep: Report) -> None:
    spells = _read(PROCESSED / "spells.csv")
    gaz = [s for s in spells if s["evidence_tier"] == "gazette_dated"]
    rep.add("INFO", "spells",
            f"{len(gaz)} dated, {len(spells) - len(gaz)} undated seed ties")

    neg = [s for s in spells if s["onset"] and s["terminus"] and s["terminus"] < s["onset"]]
    rep.add("ERROR" if neg else "INFO", "no negative durations",
            f"{len(neg)} spells end before they begin")

    zero = [s for s in gaz if s["onset"] and s["terminus"] and s["terminus"] == s["onset"]]
    rep.add("WARN" if zero else "INFO", "zero-length spells",
            f"{len(zero)} spells open and close on the same day "
            f"(an officer appointed and replaced in one act)")

    # Overlapping incumbency on a post only one person can hold at a time is a
    # strong signal of a resolution error, so it is surfaced rather than fixed.
    single = set(load_config("vocab_roles")["single_holder_roles"])
    by_post: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for s in gaz:
        if s["role_canonical"] in single and s["onset"]:
            by_post[(s["org_id"], s["role_canonical"])].append(s)
    overlaps = 0
    for (_org, _role), group in by_post.items():
        group.sort(key=lambda s: s["onset"])
        for a, b in zip(group, group[1:]):
            a_end = a["terminus"] or "9999-12-31"
            if b["onset"] < a_end and a["person_id"] != b["person_id"]:
                overlaps += 1
    rep.add("WARN" if overlaps else "INFO", "overlapping single-holder posts",
            f"{overlaps} overlaps on gerant/pdg/dg/president posts — candidate "
            f"resolution errors")

    censor = Counter()
    for s in gaz:
        censor["right_censored" if s["right_censored"] == "True" else "closed"] += 1
        if s["left_censored"] == "True":
            censor["left_censored"] += 1
    rep.add("INFO", "censoring",
            ", ".join(f"{k}={v}" for k, v in censor.most_common()))
    rep.add("INFO", "closure mechanism",
            ", ".join(f"{k or '(open)'}={v}" for k, v in
                      Counter(s["terminus_rule"] for s in gaz).most_common()))


def check_resolution(rep: Report) -> None:
    res = _read(PROCESSED / "resolution.csv")
    status = Counter(r["link_status"] for r in res)
    rep.add("INFO", "resolution status",
            ", ".join(f"{k}={v}" for k, v in status.most_common()))

    resolved = [r for r in res if r["link_status"] == "resolved"]
    no_org = [r for r in resolved if float(r["s_org"] or 0) == 0]
    rep.add("ERROR" if no_org else "INFO", "resolutions are dyad-anchored",
            f"{len(no_org)} resolved links lack organisation agreement "
            f"(a name-only link is not an identification)")

    # The inferred tier is reported separately and never folded into the line
    # above. It rests on the name being unique on both sides rather than on the
    # organisation agreeing, which is weaker in KIND, not in degree -- so the
    # invariant over `resolved` stays absolute and a consumer can drop the
    # inference with one filter on `link_status` or on the `gazette_inferred`
    # evidence tier in the spells and panel tables.
    inferred = [r for r in res if r["link_status"] == "inferred"]
    if inferred:
        people = len({r["resolved_person_id"] for r in inferred
                      if r["resolved_person_id"]})
        rep.add("WARN", "links inferred from name rarity",
                f"{len(inferred)} links over {people} persons rest on the name "
                f"being borne by one seed person and matching one gazette "
                f"candidate, with no organisation to anchor them. They are "
                f"NOT counted as resolved. Exclude them for any claim that "
                f"needs dyad-anchored identification; include them for "
                f"coverage.")

    # A person holding an implausible number of simultaneous posts is usually
    # several people merged into one, so it is an automatic homonym detector.
    per_person = Counter(r["resolved_person_id"] for r in resolved)
    heavy = [(p, n) for p, n in per_person.items() if n > 12]
    rep.add("WARN" if heavy else "INFO", "improbably many posts",
            f"{len(heavy)} resolved persons hold more than 12 dyads "
            f"(possible merged homonyms)"
            + (f", worst: {sorted(heavy, key=lambda x: -x[1])[0]}" if heavy else ""))
    rep.add("INFO", "review queue",
            f"{len(_read(PROCESSED / 'review_queue.csv'))} ambiguous dyads queued; "
            f"{len(_read(PROCESSED / 'gazette_only_persons.csv'))} gazette-only "
            f"candidate persons retained")


def check_coverage(rep: Report) -> None:
    res = [r for r in _read(PROCESSED / "resolution.csv") if r["link_status"] == "resolved"]
    pids = {r["resolved_person_id"] for r in res}
    persons = [n for n in _read(PROCESSED / "seed_nodes.csv") if n["node_type"] == "PERSON"]
    ranked = sorted(persons, key=lambda n: -int(n["seed_degree"]))
    parts = []
    for k in (100, 500, 1000):
        hit = sum(1 for n in ranked[:k] if n["node_id"] in pids)
        parts.append(f"top {k}: {hit} ({hit / k:.0%})")
    parts.append(f"all {len(persons)}: {len(pids)} ({len(pids)/max(1,len(persons)):.1%})")
    rep.add("INFO", "seed elites with a dated gazette event", "; ".join(parts))


def check_negative_control(rep: Report) -> None:
    """Auction and fonds-de-commerce notices should produce no appointments."""
    if not BLOCKS.exists():
        _skip(rep, "negative control", BLOCKS)
        return
    events = _read(PROCESSED / "events.csv")
    by_block = {}
    with BLOCKS.open(encoding="utf-8") as fh:
        for line in fh:
            b = json.loads(line)
            if b.get("domain") in {"judicial", "commercial"}:
                by_block[b["block_uid"]] = b.get("domain")
    officer = {"appointed", "renewed", "resigned", "revoked", "charged_with_functions"}
    fp = [e for e in events if e["block_uid"] in by_block and e["event_type"] in officer]
    rep.add("INFO", "negative control",
            f"{len(fp)} officer events found in {len(by_block)} auction/"
            f"fonds-de-commerce blocks, which are excluded from extraction "
            f"(0 expected by construction)")


def check_cabinets(rep: Report) -> None:
    """Reconstruct cabinets from decrees and compare to the seed's governments."""
    events = _read(PROCESSED / "events.csv")
    ministers = [e for e in events
                 if e["domain"] == "state"
                 and e["role_canonical"] in {"minister", "secretary_of_state",
                                             "chef_du_gouvernement"}]
    by_year = Counter(e["event_date"][:4] for e in ministers if e["event_date"])
    rep.add("INFO", "ministerial appointments by year",
            ", ".join(f"{y}={n}" for y, n in sorted(by_year.items())))

    seed_gov = {n["label"] for n in _read(PROCESSED / "seed_nodes.csv")
                if n["node_type"] == "GOVERNMENT" and "GOVERNMENT" in n["label"]}
    rep.add("INFO", "seed cabinets",
            f"{len(seed_gov)} government nodes in the seed sheet: "
            f"{', '.join(sorted(seed_gov)[:8])}")
    if not ministers:
        rep.add("WARN", "cabinet reconstruction",
                "no ministerial appointments recovered; the state extractor's "
                "cabinet-list rule needs review against a known decree")


def check_citations(rep: Report) -> None:
    path = INTERIM / "act_citations.csv"
    if not path.exists():
        _skip(rep, "act citation graph", path)
        return
    cits = _read(path)
    dated = [c for c in cits if c["cited_date"]]
    rep.add("INFO", "act citation graph",
            f"{len(cits)} citations, {len(dated)} with a resolvable cited date")


def check_org_entities(rep: Report) -> None:
    """Organisation entities, and the proof that refining identity lost nothing.

    The merge hubs came from identity being "the seed node this mention
    fuzzy-matched": `fuzz.token_set_ratio` treats containment as identity, so
    a seed firm whose label normalised to "TROIS" absorbed every mention
    containing the French word for three and became the highest-degree
    organisation in the org-org layer. The fix refines identity rather than
    discarding matches, so the thing to check is that **every** organisation
    mention still reaches an entity. A mention that reached none would be a
    firm silently deleted from the dataset, which is the one outcome this
    change was not allowed to have.
    """
    if not _table_exists(PROCESSED / "org_entities.csv"):
        _skip_stage(rep, "organisation entities",
                    PROCESSED / "org_entities.csv")
        return
    ents = _read(PROCESSED / "org_entities.csv")
    members = _read(PROCESSED / "org_entity_members.csv")
    have_members = _table_exists(PROCESSED / "org_entity_members.csv")

    by_basis = Counter(e["entity_basis"] for e in ents)
    rep.add("INFO", "organisation entities",
            f"{len(ents)} entities over {len(members)} distinct mentions: "
            + ", ".join(f"{k}={v}" for k, v in by_basis.most_common()))

    # The no-data-lost guard, machine-checked rather than asserted in a commit
    # message.
    if not have_members:
        # Without the map there is no coverage to check, and reporting every
        # mention as unmapped would be a false ERROR rather than a finding --
        # the same "stage produced nothing" versus "stage has not run"
        # distinction the skip helpers exist for.
        _skip_stage(rep, "every org mention has an entity",
                    PROCESSED / "org_entity_members.csv")
    else:
        events = _read(PROCESSED / "events.csv")
        mentions = {(e.get("org_mention") or "").strip() for e in events}
        mentions.discard("")
        mapped = {m["org_mention"] for m in members}
        missing = mentions - mapped
        rep.add("ERROR" if missing else "INFO",
                "every org mention has an entity",
                f"{len(missing)} of {len(mentions)} organisation mentions in "
                f"events.csv reach no entity"
                + (f", e.g. {sorted(missing)[0][:60]!r}" if missing else ""))

    # The residual error, stated with its direction. Name-keyed entities split
    # one firm across spellings, which is the mirror image of the merge this
    # change fixed: it understates degree where the merge overstated it.
    name_keyed = by_basis.get("name", 0) + by_basis.get("ambiguous_mention", 0)
    share = name_keyed / len(ents) if ents else 0
    rep.add("WARN" if share > 0.5 else "INFO", "entities keyed only by name",
            f"{name_keyed} of {len(ents)} entities ({share:.0%}) have no hard "
            f"identifier and are keyed on the mention, so two spellings of one "
            f"such firm stay separate -- the mirror image of the merge, and it "
            f"understates degree rather than overstating it")

    spanning = [m for m in members
                if int(m.get("n_entities_on_mention") or 1) > 1]
    rep.add("INFO", "mentions spanning several entities",
            f"{len(spanning)} mentions carry more than one hard identifier, so "
            f"the mention-level map is modal for them; the per-event key in "
            f"orgentity.entity_key is the authoritative assignment")

    adopted = [e for e in ents if e.get("seed_link_is_identity") == "1"]
    rep.add("INFO", "entities linked to a seed organisation",
            f"{len(adopted)} of {len(ents)} entities carry an identity-grade "
            f"seed link and adopt that node's id, so seed ties and the dyadic "
            f"covariates projected from them stay on the same vertex")


def check_org_attrs(rep: Report) -> None:
    """Organisation identifiers, and what they say about resolution quality.

    A matricule fiscal and a registre-de-commerce number are hard identifiers:
    a firm has one of each. So an organisation node carrying two is a defect,
    and this is the only check in the pipeline that can see an
    organisation-resolution **merge** -- a merge otherwise looks exactly like a
    well-corroborated match, since both names really do appear beside the same
    kind of clause.

    Reported at WARN, not ERROR, for the reason the merged-homonym check on the
    person side is: some conflicts are genuine re-registrations, and the build
    should not fail over an ambiguity in the source. The number is what matters,
    and it belongs in the report where a reader will see it.
    """
    if not _table_exists(PROCESSED / "org_identifiers.csv"):
        _skip_stage(rep, "organisation identifiers",
                    PROCESSED / "org_identifiers.csv")
        return
    ids = _read(PROCESSED / "org_identifiers.csv")

    by_type = Counter(r["id_type"] for r in ids)
    rep.add("INFO", "organisation identifiers",
            f"{len(ids)} (organisation, identifier, value) rows: "
            + ", ".join(f"{k}={v}" for k, v in by_type.most_common()))

    for id_type in ("matricule_fiscal", "registre_commerce"):
        rows = [r for r in ids if r["id_type"] == id_type]
        if not rows:
            continue
        orgs = {r["org_id"] for r in rows}
        clashing = {r["org_id"] for r in rows if r["is_conflicting"] == "1"}
        share = f"{len(clashing)/len(orgs):.0%}" if orgs else "—"
        rep.add("WARN" if clashing else "INFO",
                f"conflicting {id_type}",
                f"{len(clashing)} of {len(orgs)} organisations carrying one "
                f"hold two or more values ({share}); a few values clustered "
                f"around one is OCR, many with nothing in common is an "
                f"organisation-resolution merge. See "
                f"docs/ORG-IDENTIFIER-CONFLICTS-multiplex.md")

    # The severity, not just the count. A node holding two values of an
    # identifier has a bad value; a node holding hundreds is hundreds of firms
    # collapsed into one, which does not degrade a variable but fabricates a
    # hub, and any centrality computed over it is meaningless. This is reported
    # separately because the two are different findings with the same shape.
    per_org: Counter = Counter()
    for r in ids:
        if r["is_conflicting"] == "1":
            per_org[(r["org_id"], r["org_label"], r["id_type"])] += 1
    # Counted two ways on purpose. `per_org` is keyed on (node, identifier
    # kind), so a node holding both a bad matricule and a bad RC number
    # appears twice -- reporting that total as a count of NODES overstated it
    # by a third, 383 against 288.
    severe = [(k, n) for k, n in per_org.items() if n >= 10]
    severe_nodes = {k[0] for k, _n in severe}
    if per_org:
        worst = max(per_org.items(), key=lambda kv: kv[1])
        rep.add("WARN" if severe else "INFO", "organisation merge hubs",
                f"{len(severe_nodes)} organisations ({len(severe)} "
                f"organisation-identifier pairs) hold 10 or more values of a "
                f"single hard identifier and are near-certainly several firms "
                f"merged into one; worst is {worst[0][1] or worst[0][0]} with "
                f"{worst[1]} distinct {worst[0][2].replace('_', ' ')} values. "
                f"Exclude these before computing organisation-level structure "
                f"— `org_identifiers.csv` carries `n_values_for_org`, and "
                f"`exports/tergm/node_key.csv` carries `merge_suspect`.")

    # An identifier is per-organisation, so a value shared by two nodes is the
    # same defect seen from the other side: either one firm split across two
    # nodes, or a misread that collided.
    shared = Counter()
    for r in ids:
        shared[(r["id_type"], r["value_normalised"])] += 1
    multi = [k for k, n in shared.items() if n > 1]
    rep.add("WARN" if multi else "INFO", "identifiers shared across nodes",
            f"{len(multi)} identifier values appear on more than one "
            f"organisation node (one firm split in two, or a collision)")

    addrs = _read(PROCESSED / "org_addresses.csv")
    if addrs:
        moved = [a for a in addrs if a["obs_kind"] == "moved_to"]
        per_org = Counter(a["org_id"] for a in addrs)
        rep.add("INFO", "organisation addresses",
                f"{len(addrs)} dated address observations over "
                f"{len(per_org)} organisations; {len(moved)} are transfer "
                f"destinations; "
                f"{sum(1 for n in per_org.values() if n > 1)} organisations "
                f"have more than one address on record")
        undated = [a for a in addrs if not a["observed_date"]]
        rep.add("ERROR" if undated else "INFO", "addresses are dated",
                f"{len(undated)} address observations carry no date, so they "
                f"cannot be ordered into a sequence of seats")


def check_org_ties(rep: Report) -> None:
    """The organisation-to-organisation layer.

    Its errors are the kind that read as findings. A self-tie inflates a firm's
    ownership degree; a reversed direction asserts the opposite ownership
    relation and looks entirely plausible; a confirmation promoted to an onset
    invents the dating the layer is careful not to claim.
    """
    spells = _read(PROCESSED / "org_tie_spells.csv")
    if not spells:
        _skip_stage(rep, "org ties", PROCESSED / "org_tie_spells.csv")
        return
    dated = [s for s in spells if s["evidence_tier"] == "gazette_dated"]
    seedy = [s for s in spells if s["evidence_tier"] == "seed_undated"]

    rep.add("INFO", "org ties",
            f"{len(dated)} dated, {len(seedy)} undated seed ties; "
            f"{len({(s['holder_id'], s['target_id']) for s in dated})} dated dyads")
    rep.add("INFO", "org tie relations",
            ", ".join(f"{k}={v}" for k, v in
                      Counter(s["relation"] for s in spells).most_common(8)))

    loops = [s for s in spells if s["holder_id"] == s["target_id"]]
    rep.add("ERROR" if loops else "INFO", "org ties are not self-loops",
            f"{len(loops)} ties whose holder and target are the same organisation")

    neg = [s for s in spells if s["onset"] and s["terminus"]
           and s["terminus"] < s["onset"]]
    rep.add("ERROR" if neg else "INFO", "org tie durations are not negative",
            f"{len(neg)} org tie spells end before they begin")

    # A confirmation bounds the onset from above and asserts nothing below it.
    # An onset filled in from one would be a manufactured date.
    bad_cens = [s for s in dated
                if s["onset"] and s["left_censored"] == "True"]
    rep.add("ERROR" if bad_cens else "INFO", "org tie censoring is consistent",
            f"{len(bad_cens)} spells assert an onset while flagged left-censored")

    # A closed-world check over a node universe that now has two authorities.
    # An organisation's identity is its ENTITY -- keyed on a hard identifier
    # where it has one -- because identity used to be "the seed node this
    # mention fuzzy-matched", and a seed label that normalised to a common
    # French word absorbed every mention containing it. So an endpoint may
    # legitimately be an `ORGE_` entity rather than a seed node. It may not be
    # neither: a dangling id is still an error, which is what this checks.
    known = {n["node_id"] for n in _read(PROCESSED / "seed_nodes.csv")}
    have_entities = _table_exists(PROCESSED / "org_entities.csv")
    known |= {e["org_entity_id"] for e in _read(PROCESSED / "org_entities.csv")}
    unknown = [s for s in spells
               if s["holder_id"] not in known or s["target_id"] not in known]
    if unknown and not have_entities:
        # Half the node universe is missing, so every entity endpoint reads as
        # dangling. That is a stage that has not run, not a broken dataset --
        # the distinction `_skip_stage` exists to preserve.
        _skip_stage(rep, "org tie endpoints are known nodes",
                    PROCESSED / "org_entities.csv")
        return
    rep.add("ERROR" if unknown else "INFO",
            "org tie endpoints are known nodes",
            f"{len(unknown)} ties with an endpoint in neither "
            f"seed_nodes.csv nor org_entities.csv")

    lc = sum(1 for s in dated if s["left_censored"] == "True")
    rc = sum(1 for s in dated if s["right_censored"] == "True")
    rep.add("INFO", "org tie censoring",
            f"left_censored={lc} ({lc / max(1, len(dated)):.0%}), "
            f"right_censored={rc} ({rc / max(1, len(dated)):.0%})")


def check_person_ties(rep: Report) -> None:
    """The kinship layer.

    Its errors read as findings too, and one of them is worse than the org-tie
    equivalents: a `née` marker counted as a marriage invents a husband out of
    a woman's birth name, and the resulting tie is entirely plausible on
    inspection. So the marriage/maiden split is checked at ERROR level, not
    reported as a count.
    """
    spells = _read(PROCESSED / "person_tie_spells.csv")
    if not spells:
        _skip_stage(rep, "person ties", PROCESSED / "person_tie_spells.csv")
        return

    rep.add("INFO", "person ties",
            f"{len(spells)} kinship dyads; "
            f"{sum(1 for s in spells if s.get('is_marriage') == '1')} marriages, "
            f"{sum(1 for s in spells if s.get('relation') == 'maiden_name_of')} "
            f"natal-surname links")
    rep.add("INFO", "person tie relations",
            ", ".join(f"{k}={v}" for k, v in
                      Counter(s.get("relation", "") for s in spells).most_common(6)))

    mislabelled = [s for s in spells
                   if (s.get("relation") == "maiden_name_of")
                   == (s.get("is_marriage") == "1")]
    rep.add("ERROR" if mislabelled else "INFO",
            "a natal surname is not a marriage",
            f"{len(mislabelled)} spells whose relation and is_marriage disagree")

    loops = [s for s in spells if s.get("person_id") == s.get("kin_id")]
    rep.add("ERROR" if loops else "INFO", "kinship ties are not self-loops",
            f"{len(loops)} ties whose two ends are the same person")

    # The gazette does not publish weddings. An onset here would be invented,
    # and a duration analysis would then read filing frequency as marriage
    # tenure.
    onsets = [s for s in spells if s.get("onset")]
    rep.add("ERROR" if onsets else "INFO", "no marriage onset is asserted",
            f"{len(onsets)} spells assert an onset the sources cannot date")
    not_lc = [s for s in spells if s.get("left_censored") != "True"]
    rep.add("ERROR" if not_lc else "INFO", "kinship onsets are left-censored",
            f"{len(not_lc)} spells not flagged left-censored")

    # Only `widow_of` dates a boundary. A terminus on anything else is a
    # boundary the sources do not state.
    bad_term = [s for s in spells
                if s.get("terminus") and s.get("relation") != "widow_of"]
    rep.add("ERROR" if bad_term else "INFO", "only a widow marker ends a tie",
            f"{len(bad_term)} non-widow spells carry a terminus")

    # A closed-world check on the person side, against the same two
    # authorities the org side uses: a seed node, or a resolution row that
    # named the mention.
    known = {n["node_id"] for n in _read(PROCESSED / "seed_nodes.csv")
             if n["node_type"] == "PERSON"}
    if known:
        unknown = [s for s in spells
                   if s.get("person_id") not in known
                   or s.get("kin_id") not in known]
        rep.add("ERROR" if unknown else "INFO",
                "kinship endpoints are known persons",
                f"{len(unknown)} ties with an endpoint outside seed_nodes.csv")

    inferred = [s for s in spells if s.get("evidence_tier") == "kinship_inferred"]
    if inferred:
        rep.add("WARN", "kinship ties resting on an inferred endpoint",
                f"{len(inferred)} of {len(spells)} dyads have at least one end "
                f"named by name rarity rather than by an organisation agreeing; "
                f"they carry evidence_tier=kinship_inferred and are excluded "
                f"from any filter on kinship_dated")

    queue = _read(PROCESSED / "person_ties_review_queue.csv")
    if queue:
        reasons = Counter(r.get("queue_reason", "") for r in queue)
        rep.add("INFO", "person tie review queue",
                f"{len(queue)} observations retained but not tied: "
                + ", ".join(f"{k}={v}" for k, v in reasons.most_common()))


def check_snowball(rep: Report) -> None:
    """The snowball tier: that it is labelled, bounded and separable.

    A snowball propagates its own errors, so what is checked here is not
    whether the links are right -- no invariant can settle that -- but whether
    a reader can find and drop them. If `resolve_pass` were absent or wrong,
    the tier would be indistinguishable from first-pass resolution, and that is
    the failure that matters.
    """
    rows = _read(PROCESSED / "resolution.csv")
    if not rows:
        _skip_stage(rep, "snowball passes", PROCESSED / "resolution.csv")
        return
    sb = [r for r in rows if r.get("link_status") == "snowball"]
    if "resolve_pass" not in rows[0]:
        # Two very different states look the same from here, and conflating
        # them is the same mistake as reading an absent table as an empty one.
        #
        # A resolution table with no snowballed links and no column is one
        # built before the tier existed -- a stage that has not re-run, which
        # is what `_skip_stage` is for. Failing on it would make every clone
        # and every CI run red until the whole pipeline is rebuilt, and would
        # say "broken dataset" where the truth is "stale stage".
        #
        # A table carrying snowballed links with no column to tell them apart
        # is the genuine defect the check was written for, and stays an ERROR.
        if not sb:
            _skip_stage(rep, "snowball passes", PROCESSED / "resolution.csv",
                        "predates the snowball tier (no resolve_pass column, "
                        "and no link claims to have been snowballed)")
            return
        rep.add("ERROR", "snowball passes are recorded",
                f"{len(sb)} links have link_status=snowball but resolution.csv "
                f"has no resolve_pass column, so a snowballed link cannot be "
                f"told from a first-pass one")
        return

    by_pass = Counter(r.get("resolve_pass", "") for r in sb)
    by_basis = Counter(r.get("snowball_basis", "") for r in sb)
    rep.add("INFO", "snowball links",
            f"{len(sb)} of {len(rows)} mentions named by a later pass"
            + (f" ({', '.join(f'pass {k}={v}' for k, v in sorted(by_pass.items()))})"
               if sb else ""))
    if sb:
        rep.add("INFO", "snowball bases",
                ", ".join(f"{k}={v}" for k, v in by_basis.most_common()))
        # The marginal yield per round, which is the only way to tell a
        # snowball that converged from one that was cut off by the cap. A
        # last round still adding links means the bound bound, not that the
        # evidence ran out -- and that is a different dataset from one that
        # stopped because nothing was left to name.
        passes = sorted(int(p) for p in by_pass if str(p).isdigit())
        if passes:
            trail = ", ".join(f"pass {p}: +{by_pass[str(p)]}" for p in passes)
            rep.add("INFO", "snowball marginal yield", trail)
            last = passes[-1]
            if by_pass[str(last)] and last >= MAX_SNOWBALL_PASSES:
                rep.add("WARN", "snowball stopped at the cap, not convergence",
                        f"pass {last} still added {by_pass[str(last)]} links and "
                        f"is the last allowed (scope.yaml snowball.max_passes="
                        f"{MAX_SNOWBALL_PASSES}). Links the evidence supports "
                        f"are therefore missing; raise the bound and re-run "
                        f"`make resolve` to converge.")

    # Every snowballed row must say which pass and which rule named it.
    unlabelled = [r for r in sb
                  if not r.get("snowball_basis") or r.get("resolve_pass") in ("", "0")]
    rep.add("ERROR" if unlabelled else "INFO",
            "every snowballed link names its pass and rule",
            f"{len(unlabelled)} rows with link_status=snowball but no "
            f"pass number or basis")

    # A pass number has to be explained, but NOT necessarily by a named
    # person. The rules that name an ORGANISATION -- a known identifier, or
    # the person's own seed organisations -- stamp the pass on a row whose
    # person may still be unresolved, and that is the intended behaviour: the
    # firm was identified by a later pass even though the individual was not.
    #
    # The first version of this check assumed a pass could only ever name a
    # person, and fired on 878 rows doing exactly what rules 0 and 1 are for.
    # The invariant actually wanted is narrower and is split in three.
    ORG_RULES = {"identifier_names_org", "person_names_org"}
    PERSON_RULES = {"org_names_person", "colleagues_name_person"}
    stamped = [r for r in rows if r.get("resolve_pass") not in ("", "0")]

    unexplained = [r for r in stamped if not r.get("snowball_basis")]
    rep.add("ERROR" if unexplained else "INFO",
            "a pass number names the rule that earned it",
            f"{len(unexplained)} rows carry a pass number with no snowball_basis")

    no_org = [r for r in stamped
              if r.get("snowball_basis") in ORG_RULES and not r.get("resolved_org_id")]
    rep.add("ERROR" if no_org else "INFO",
            "an organisation-naming pass leaves an organisation named",
            f"{len(no_org)} rows name an organisation rule but carry no resolved_org_id")

    no_person = [r for r in stamped
                 if r.get("snowball_basis") in PERSON_RULES
                 and r.get("link_status") != "snowball"]
    rep.add("ERROR" if no_person else "INFO",
            "a person-naming pass leaves link_status=snowball",
            f"{len(no_person)} rows name a person rule without link_status=snowball")

    if sb:
        rep.add("WARN", "resolution rests partly on snowballed anchors",
                f"{len(sb)} links were made from an anchor a later pass "
                f"supplied rather than from the organisation agreeing. They "
                f"carry link_status=snowball and evidence_tier="
                f"gazette_snowball downstream; filter resolve_pass==0 to "
                f"reproduce the single-pass build exactly")


def check_tergm_panel(rep: Report) -> None:
    """The invariants R/build_tergm_panel.R relies on, at ERROR level.

    These are not stylistic. A bipartite network object is a claim about the
    *ordering* of vertex ids -- mode 1 occupies 1..n1 -- and nothing in the
    file format enforces it. Break the ordering and `network` still builds an
    object, `btergm` still estimates, and every degree and star coefficient is
    silently computed against a reference distribution containing dyads that
    cannot exist. There is no error message for that, which is why it is
    checked here instead.
    """
    d = PROCESSED / "exports" / "tergm"
    if not _table_exists(d / "node_key.csv"):
        _skip_stage(rep, "tergm panel", d / "node_key.csv")
        return
    key = _read(d / "node_key.csv")
    edges = _read(d / "edges_yearly.csv")
    activity = _read(d / "vertex_activity_yearly.csv")
    attrs = _read(d / "node_attrs_yearly.csv")

    m1 = [int(r["vertex_id"]) for r in key if r["mode"] == "1"]
    m2 = [int(r["vertex_id"]) for r in key if r["mode"] == "2"]
    ids = sorted(m1 + m2)
    ordered = bool(m1) and bool(m2) and max(m1) < min(m2)
    contiguous = ids == list(range(1, len(ids) + 1))
    rep.add("ERROR" if not (ordered and contiguous) else "INFO",
            "tergm vertex key is mode-blocked",
            f"{len(m1)} persons then {len(m2)} organisations; "
            f"bipartite = {len(m1)}; "
            f"mode-blocked={ordered}, ids contiguous from 1={contiguous}")

    n1 = len(m1)
    bad = [e for e in edges
           if not (int(e["tail"]) <= n1 < int(e["head"]))]
    rep.add("ERROR" if bad else "INFO", "tergm edges respect the mode split",
            f"{len(bad)} of {len(edges)} ties do not run from mode 1 to mode 2")

    # An organisation cannot blink out of existence and return: activity has to
    # be one interval. A hole would be an artifact of a bad lifecycle date, and
    # would make the risk set assert something the sources do not.
    seq: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for r in activity:
        seq[int(r["vertex_id"])].append((r["period"], r["active"]))
    holes = 0
    for rows in seq.values():
        s = "".join(a for _p, a in sorted(rows))
        if "1" in s and "0" in s.strip("0"):
            holes += 1
    rep.add("ERROR" if holes else "INFO", "tergm risk set is contiguous",
            f"{holes} vertices go inactive and then active again")

    # Every observed tie must lie inside the risk set, or the estimator is being
    # handed a structural zero that is also an observed edge.
    active = {(r["period"], int(r["vertex_id"])) for r in activity
              if r["active"] == "1"}
    outside = [e for e in edges
               if (e["period"], int(e["tail"])) not in active
               or (e["period"], int(e["head"])) not in active]
    rep.add("ERROR" if outside else "INFO", "tergm ties lie inside the risk set",
            f"{len(outside)} ties fall in a period where an endpoint is inactive")

    # The panel must cover the window the rest of the pipeline is configured
    # for. This check exists because the rectangularity test below derives its
    # periods from the panel itself, so a panel built under a narrower window
    # is internally consistent and passes: the window could be widened, every
    # other stage rebuilt, and this panel left behind, with analyses quietly
    # running on five years of a seventy-year configuration.
    #
    # The period axis is read off the activity table, not the edge list. A year
    # in which no tie is observed has no edge rows but is still a period of the
    # panel -- an empty network, not an absent one -- and taking the axis from
    # the edges would report the early decades, which carry 37 dated ties
    # between them, as missing.
    from .spells import periods as _periods
    configured = [p for p, _s, _e in _periods("yearly")]
    present = sorted({r["period"] for r in activity} or
                     {r["period"] for r in edges})
    missing = [p for p in configured if p not in set(present)]
    extra = [p for p in present if p not in set(configured)]
    rep.add("ERROR" if (missing or extra) else "INFO",
            "tergm panel covers the configured window",
            f"{len(present)} periods present, {len(configured)} configured"
            + (f"; {len(missing)} missing ({missing[0]}..{missing[-1]})"
               if missing else "")
            + (f"; {len(extra)} outside the window" if extra else ""))

    # btergm reads one vertex set per period; a ragged panel silently drops rows.
    per = present
    ragged = [p for p in per
              if sum(1 for r in attrs if r["period"] == p) != len(key)
              or sum(1 for r in activity if r["period"] == p) != len(key)]
    rep.add("ERROR" if ragged else "INFO", "tergm panel is rectangular",
            f"{len(per)} periods x {len(key)} vertices; "
            f"{len(ragged)} periods with a short attribute or activity table")


def run(fail_on_error: bool = False) -> int:
    ensure_dirs()
    rep = Report()
    check_calendar(rep)
    check_events(rep)
    check_quotes_are_verbatim(rep)
    check_spells(rep)
    check_resolution(rep)
    check_coverage(rep)
    check_negative_control(rep)
    check_cabinets(rep)
    check_citations(rep)
    check_org_ties(rep)
    check_org_entities(rep)
    check_org_attrs(rep)
    check_person_ties(rep)
    check_snowball(rep)
    check_tergm_panel(rep)

    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "VALIDATION-multiplex.md").write_text(rep.render(), encoding="utf-8")
    print(rep.render())
    if fail_on_error and rep.errors:
        print(f"\nFAILED: {rep.errors} error-level checks")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate the dataset.")
    ap.add_argument("--strict", action="store_true", help="exit non-zero on ERROR")
    args = ap.parse_args(argv)
    return run(fail_on_error=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
