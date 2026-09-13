"""Stage 16 -- individuals connected to registered SARL and SA companies.

The question this answers is "who is connected to the SARL and SA companies in
the register", and answering it honestly requires saying which half of it each
source can do. Neither source can do both.

The register knows which companies exist; it does not know their legal form
-------------------------------------------------------------------------

`registres.categorie` is `SOCIETE` for 201,938 of 203,788 companies. It
separates a company from an association and stops there: SARL, SUARL, SA and
everything else are one value. So the register, on its own, cannot produce the
list of SARL and SA companies that the question asks for. Parsing the form out
of the registered *name* recovers only 5.4% of rows, because most companies do
not carry their form in their denomination.

The gazette knows the legal form, from its own filing structure
---------------------------------------------------------------

Every announcement carries a rubric code, and the rubric *is* the legal form:
`SRLB1` is a SARL constitution, `SANB2` an SA management filing, `SRUB1` a
SUARL constitution (`config/vocab_events.yaml`). That is the gazette's own
structured classification of the notice, not a phrase matched in OCR'd prose,
and it is the strongest form evidence available anywhere in this project.

It is attributable because `extract` already keeps the notice's identifier
attached to the notice's *subject* firm: where a tie's target is a company
named inside a clause instead, `org_mf` and `org_rc` are cleared rather than
copied (`extract.py`). So a rubric form and an identifier on one event always
describe the same company, and the join is not manufacturing an attribution.

Neither source knows the officers -- only the gazette names people
------------------------------------------------------------------

**The register has no officer table.** Its second table, `personnes
physiques`, is sole proprietors and merchants registered in their own name --
315,659 people who *are* businesses, not people who run companies. There is no
row anywhere in the register that connects a natural person to a SARL. So
every person-to-company link in this stage comes from JORT, and the register's
role is confined to saying which companies are registered ones.

Three things this stage refuses to do
-------------------------------------

**It does not report an undetermined form as "not SARL/SA".** The form is
determinable for the companies the gazette filed a notice about; for the rest
it is unknown. Those are different statements and the table carries
`form_basis` so they cannot be confused. The headline is therefore a count of
companies whose form is *known*, with the remainder reported as a bound.

**It does not fold SUARL into SARL.** A SUARL is a single-member company: one
associate, so no internal coalition and no shareholder network to speak of.
Counting it as a SARL would inflate the SARL population by 19% with firms
whose ownership structure is categorically different. It is labelled and
reported beside them, and the caller decides.

**It does not collapse a company's forms to the modal one.** A company filing
first under one form and later under another has *transformed* -- a SARL
opening its capital and becoming an SA is a real corporate event with a date,
and this project has a standing rule against resolving a disagreement by
majority. **795** companies convert, and the date of the switch is recorded.

But a conversion has to be sustained on both sides, and getting that wrong
was the first error here. Taking the *latest* filing as the current form let
one stray rubric override every other: `HANNIBAL LEASE` files as an SA 47
times and as a SARL once, and reading the last filing turned a leasing
company into a SARL. That rule produced **1,637** conversions, of which
**842 -- 51% -- were single anomalous filings**. `decide_form` now requires
each side of the switch to carry at least `CONVERSION_MIN_SUPPORT` filings of
its own form; a minority that fails the test is recorded in `minority_forms`
and does not decide. The 795 that survive split 263 SARL->SA, 258
SUARL->SARL, 165 SARL->SUARL and 101 SA->SARL -- all directions a company
can actually move in.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from .paths import PROCESSED, ensure_dirs
from .rne import load_register

# The forms this stage is asked about, plus SUARL, which is kept distinct.
# AUTRE/COOP/ASSOC rubrics exist and are deliberately not in scope.
FORMS = ("SARL", "SUARL", "SA")

# SARL and SA read off a registered name, for companies the gazette never
# filed about. Deliberately strict: a bare "SA" inside a name is a frequent
# false positive ("SA MAISON"), so it is required to be delimited and to sit
# at the end of the name, where a legal form actually goes.
RE_SUARL = re.compile(r"\bS\.?\s?U\.?\s?A\.?\s?R\.?\s?L\b\.?", re.I)
RE_SARL = re.compile(r"\bS\.?\s?A\.?\s?R\.?\s?L\b\.?", re.I)
RE_SA_TAIL = re.compile(r"[\s,\-(]S\.?\s?A\.?\s*[)\.]?\s*$", re.I)
# Arabic. "ذات مسؤولية محدودة" is *limited liability* -- a SARL. A SUARL is
# that plus a sole-partner qualifier, so the qualifier is what separates them
# and the bare phrase must not be read as SUARL.
RE_SUARL_AR = re.compile(
    r"(?:الشريك|شريك)\s+(?:الواحد|الوحيد|واحد)|ش\.?\s?ذ\.?\s?م\.?\s?م\.?\s?و")
RE_SARL_AR = re.compile(r"ذات\s+مسؤولي[ةه]\s+محدودة|ش\.?\s?ذ\.?\s?م\.?\s?م")
RE_SA_AR = re.compile(r"خفي[ةه]\s+(?:الاسم|الإسم)|شرك[ةه]\s+مساهم[ةه]")

FIELDS_FORMS = [
    "company_key", "matricule", "num_registre", "identifiers_in_gazette",
    "legal_form", "legal_form_first", "is_conversion",
    "conversion_date", "minority_forms", "form_basis", "forms_stated",
    "n_forms_stated", "rne_name_fr",
    "rne_name_ar", "rne_category", "rne_year_creation", "jort_label",
    "org_entity_id", "seed_org_id", "first_seen", "last_seen", "n_events",
    "n_persons", "n_persons_seed_elite", "n_persons_gazette_only",
]
FIELDS_PERSONS = [
    "company_key", "matricule", "num_registre", "legal_form", "rne_name_fr",
    "jort_label", "person_key", "person_label", "link_grade", "is_seed_elite",
    "role_primary", "roles", "n_events", "first_event_date", "last_event_date",
    "org_entity_id", "resolved_org_id", "mention_cluster_id", "issue_uid",
    "source_url", "evidence_quote",
]

# A person mention that is only a role title, or a clause fragment. These are
# `clean_name` escapes rather than people, and they are few -- 186 links of
# 113,400 -- but they sort straight to the top of any "connected to the most
# companies" ranking, which is precisely where a non-person does damage. They
# are excluded and counted, not silently dropped.
NOT_A_PERSON = {
    "directeur general", "directeur general adjoint",
    "president directeur general", "commissaire aux comptes", "gerant",
    "co gerant", "cogerant", "le gerant", "administrateur", "liquidateur",
    "president", "directeur", "nomination de m", "vice president",
    "directeur general adjoint", "associe", "president du conseil",
}


def _fold(text: str) -> str:
    """Accent-stripped, punctuation-free lower case, for the title test."""
    s = unicodedata.normalize("NFKD", text)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z ]+", " ", s.lower()).strip()


def is_a_person_name(mention: str) -> bool:
    """False where the mention is a bare role title or a clause fragment."""
    folded = _fold(mention)
    return bool(folded) and folded not in NOT_A_PERSON

# A person's link to the company, strongest first. `gazette_only` is a person
# the gazette names in the filing who is not in the 13,630-name seed roster --
# 95% of this table, and excluding them would answer a different question than
# the one asked.
GRADES = ("resolved", "inferred", "snowball", "gazette_only")


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


def _iter(name: str):
    """Stream a table. events.csv is 781,233 rows; resolution.csv 462,177."""
    path = PROCESSED / name
    if path.exists():
        with path.open(encoding="utf-8", newline="") as fh:
            yield from csv.DictReader(fh)
        return
    gz = PROCESSED / (name + ".gz")
    if gz.exists():
        with gzip.open(gz, "rt", encoding="utf-8", newline="") as fh:
            yield from csv.DictReader(fh)


def _write(name: str, rows: list[dict], fields: list[str]) -> None:
    path = PROCESSED / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def form_from_name(fr: str, ar: str) -> str:
    """SARL / SUARL / SA read off a registered name, or "".

    Only reached for companies the gazette never filed about, so it widens
    coverage where the stronger evidence is absent and never overrides it.
    SUARL is tested first: every SUARL string contains a SARL substring.
    """
    for text in (fr, ar):
        if not text:
            continue
        if RE_SUARL.search(text) or RE_SUARL_AR.search(text):
            return "SUARL"
    for text in (fr, ar):
        if not text:
            continue
        if RE_SARL.search(text) or RE_SARL_AR.search(text):
            return "SARL"
    for text in (fr, ar):
        if not text:
            continue
        if RE_SA_TAIL.search(text) or RE_SA_AR.search(text):
            return "SA"
    return ""


# A conversion has to be *sustained* on both sides of the switch. Without
# this, one stray filing overrides every other: HANNIBAL LEASE files 47 times
# as an SA and once as a SARL, and taking the last filing read that as a
# leasing company demoting itself to a SARL. A single anomalous rubric is far
# likelier than that, and "take the latest" cannot tell the two apart.
CONVERSION_MIN_SUPPORT = 2


def decide_form(forms: Counter, dated: list[tuple[str, str]]) -> dict:
    """The company's legal form, and whether it converted.

    Returns `legal_form` (current), `legal_form_first`, `is_conversion`,
    `conversion_date` and `minority_forms`.

    A conversion is asserted only where the timeline splits into two runs that
    each have real support -- at least `CONVERSION_MIN_SUPPORT` filings of
    their own dominant form. Otherwise the modal form stands and the odd
    filing is recorded as a minority rather than allowed to decide, which is
    this project's standing rule for a source disagreeing with itself.
    """
    modal = forms.most_common(1)[0][0]
    out = {"legal_form": modal, "legal_form_first": modal,
           "is_conversion": 0, "conversion_date": "", "minority_forms": ""}
    if len(forms) == 1 or not dated:
        return out
    minority = "|".join(f"{k}:{v}" for k, v in sorted(forms.items())
                        if k != modal)
    out["minority_forms"] = minority

    rows = sorted(dated)
    # Best split: the cut maximising filings that sit on the side their form
    # dominates. Scanning every cut is linear in a company's filing count,
    # which is at most a few dozen.
    best = None
    for cut in range(1, len(rows)):
        left, right = rows[:cut], rows[cut:]
        lc, rc = Counter(f for _, f in left), Counter(f for _, f in right)
        lform, ln = lc.most_common(1)[0]
        rform, rn = rc.most_common(1)[0]
        if lform == rform:
            continue
        if ln < CONVERSION_MIN_SUPPORT or rn < CONVERSION_MIN_SUPPORT:
            continue
        score = ln + rn
        if best is None or score > best[0]:
            best = (score, lform, rform, right[0][0])
    if best is None:
        return out
    _score, first_form, last_form, boundary = best
    out.update({"legal_form": last_form, "legal_form_first": first_form,
                "is_conversion": 1, "conversion_date": boundary})
    return out


def company_index(by_mf: dict[str, dict],
                  by_rc: dict[str, dict]) -> tuple[dict[str, dict], dict[str, str]]:
    """(company_key -> register row, identifier -> company_key).

    The *register row* is the company, not the identifier. 99.0% of rows carry
    both a matricule fiscal and a numRegistre, so keying on the identifier
    counted a company twice wherever the gazette printed both of its numbers
    -- 13,111 of them. `numRegistre` is the register's own primary key and is
    used as the company key where present.
    """
    companies: dict[str, dict] = {}
    key_of: dict[str, str] = {}
    for store in (by_rc, by_mf):
        for value, rec in store.items():
            ck = (rec.get("rne_num_registre") or rec.get("rne_matricule")
                  or value)
            companies.setdefault(ck, rec)
            key_of[value] = ck
    return companies, key_of


def gazette_forms(key_of: dict[str, str]) -> tuple[dict, dict]:
    """Per register-listed *company*, every legal form the gazette filed it under.

    Returns (observations, diagnostics). An observation is
    {company_key: {"forms": Counter, "dated": [(date, form)], "label",
                   "n_events", "first_seen", "last_seen", "identifiers"}}.

    Both identifier columns are read and both resolve through `key_of` to the
    same company, so a firm whose matricule appears on one filing and whose
    RC number appears on another is one company with two identifiers rather
    than two companies.
    """
    diag: Counter = Counter()
    obs: dict[str, dict] = {}
    for r in _iter("events.csv"):
        form = (r.get("legal_form") or "").strip()
        if form not in FORMS:
            continue
        diag[f"events_{form}"] += 1
        date = (r.get("event_date") or r.get("pub_date") or "")[:10]
        # One event can print both of a company's numbers. Resolve them to
        # company keys first and de-duplicate, so a single filing contributes
        # one form observation rather than two.
        keys: dict[str, set[str]] = {}
        for col, id_type in (("org_mf", "matricule_fiscal"),
                             ("org_rc", "registre_commerce")):
            # Already normalised by `extract`, and `normalise_mf` is not
            # idempotent -- see the note in `rne.link_identifiers`.
            value = (r.get(col) or "").strip()
            if not value:
                continue
            diag[f"identifier_seen_{id_type}"] += 1
            ck = key_of.get(value)
            if ck is None:
                diag["identifier_not_in_register"] += 1
                continue
            keys.setdefault(ck, set()).add(value)
        for ck, values in keys.items():
            rec = obs.get(ck)
            if rec is None:
                rec = obs[ck] = {
                    "forms": Counter(), "dated": [], "label": "",
                    "n_events": 0, "first_seen": "", "last_seen": "",
                    "identifiers": set(),
                }
            rec["identifiers"] |= values
            rec["forms"][form] += 1
            rec["n_events"] += 1
            if date:
                rec["dated"].append((date, form))
                if not rec["first_seen"] or date < rec["first_seen"]:
                    rec["first_seen"] = date
                if date > rec["last_seen"]:
                    rec["last_seen"] = date
            if not rec["label"] and (r.get("org_mention") or "").strip():
                rec["label"] = r["org_mention"].strip()
    diag["register_listed_companies_with_a_gazette_form"] = len(obs)
    return obs, dict(diag)


def _zero_persons() -> dict:
    """Explicit zeros, so "no person found" never reads as a blank cell."""
    return {"n_persons": 0, "n_persons_seed_elite": 0,
            "n_persons_gazette_only": 0}


def build_forms(companies: dict[str, dict], obs: dict[str, dict],
                entity_of: dict[str, str],
                seed_of: dict[str, str]) -> tuple[list[dict], dict]:
    """One row per register-listed company whose legal form is determinable.

    The gazette's rubric is the primary basis. A register name stating a form
    corroborates it, and where the gazette filed nothing it stands alone. The
    two disagreeing is recorded as `both_disagree` and the gazette is kept,
    because a rubric is the form the company filed *under* and a name is a
    string that may never have been updated.
    """
    diag: Counter = Counter()
    rows: list[dict] = []
    for ck, rec in sorted(obs.items()):
        reg = companies.get(ck, {})
        decided = decide_form(rec["forms"], rec["dated"])
        first_form = decided["legal_form_first"]
        last_form = decided["legal_form"]
        conversion = decided["is_conversion"]
        if conversion:
            diag["conversions"] += 1
            diag[f"conversion_{first_form}_to_{last_form}"] += 1
        elif decided["minority_forms"]:
            # Two forms filed, but not as two sustained runs. The modal form
            # stands and the odd filing is recorded, not obeyed.
            diag["minority_form_not_obeyed"] += 1
        name_form = form_from_name(reg.get("rne_name_fr", ""),
                                   reg.get("rne_name_ar", ""))
        if not name_form:
            basis = "gazette_rubric"
        elif name_form == last_form:
            basis = "gazette_and_register_name_agree"
            diag["register_name_corroborates"] += 1
        else:
            basis = "gazette_and_register_name_disagree"
            diag["register_name_disagrees"] += 1
        diag[f"form_{last_form}"] += 1
        diag["companies"] += 1
        rows.append({
            "company_key": ck,
            "matricule": reg.get("rne_matricule", ""),
            "num_registre": reg.get("rne_num_registre", ""),
            # Which of the company's numbers the gazette actually printed.
            "identifiers_in_gazette": "|".join(sorted(rec["identifiers"])),
            # The form the company last filed under is its current one; the
            # first is kept beside it so a conversion is not erased.
            "legal_form": last_form, "legal_form_first": first_form,
            "is_conversion": conversion,
            "conversion_date": decided["conversion_date"],
            "minority_forms": decided["minority_forms"],
            "form_basis": basis,
            "forms_stated": "|".join(
                f"{k}:{v}" for k, v in sorted(rec["forms"].items())),
            "n_forms_stated": len(rec["forms"]),
            "rne_name_fr": reg.get("rne_name_fr", ""),
            "rne_name_ar": reg.get("rne_name_ar", ""),
            "rne_category": reg.get("rne_category", ""),
            "rne_year_creation": reg.get("rne_year_creation", ""),
            "jort_label": rec["label"],
            "org_entity_id": entity_of.get(rec["label"], ""),
            "seed_org_id": next((seed_of[v] for v in sorted(rec["identifiers"])
                                 if v in seed_of), ""),
            "first_seen": rec["first_seen"], "last_seen": rec["last_seen"],
            "n_events": rec["n_events"],
            **_zero_persons(),
        })
    return rows, dict(diag)


def register_name_only(companies: dict[str, dict], known: set[str],
                       seed_of: dict[str, str]) -> tuple[list[dict], dict]:
    """Companies the gazette never filed about, whose *name* states a form.

    A weaker basis and labelled as one. It is included because leaving it out
    would understate the SARL/SA population by exactly the firms that never
    reached the French gazette, which is not a random subset.
    """
    diag: Counter = Counter()
    rows: list[dict] = []
    for ck, reg in companies.items():
        if ck in known:
            continue
        form = form_from_name(reg.get("rne_name_fr", ""),
                              reg.get("rne_name_ar", ""))
        if form not in FORMS:
            continue
        diag["companies"] += 1
        diag[f"form_{form}"] += 1
        mf, rc = reg.get("rne_matricule", ""), reg.get("rne_num_registre", "")
        rows.append({
            "company_key": ck, "matricule": mf, "num_registre": rc,
            "identifiers_in_gazette": "",
            "legal_form": form, "legal_form_first": form,
            "is_conversion": 0, "conversion_date": "",
            "minority_forms": "", "form_basis": "register_name_only",
            "forms_stated": f"{form}:0", "n_forms_stated": 1,
            "rne_name_fr": reg.get("rne_name_fr", ""),
            "rne_name_ar": reg.get("rne_name_ar", ""),
            "rne_category": reg.get("rne_category", ""),
            "rne_year_creation": reg.get("rne_year_creation", ""),
            "jort_label": "", "org_entity_id": "",
            "seed_org_id": next((seed_of[v] for v in (mf, rc)
                                 if v and v in seed_of), ""),
            "first_seen": "", "last_seen": "", "n_events": 0,
            **_zero_persons(),
        })
    return rows, dict(diag)


def company_persons(forms: dict[str, dict], key_of: dict[str, str],
                    entity_of: dict[str, str]) -> tuple[list[dict], dict]:
    """Every individual the gazette connects to one of these companies.

    One row per (company, person). A person is keyed by their seed id where
    resolution named one and by their mention cluster otherwise, so the two
    are never silently pooled: `link_grade` and `is_seed_elite` say which.

    Roles are accumulated rather than reduced. "gerant" and "liquidateur" on
    one person mean two different relationships to the firm at two different
    times, and which of them a reader wants is not this stage's call.

    Both of a company's identifiers resolve through `key_of` to one company
    key, so a person named on a filing that printed both numbers is one link
    rather than two.
    """
    diag: Counter = Counter()
    agg: dict[tuple[str, str], dict] = {}
    for r in _iter("resolution.csv"):
        person = (r.get("person_mention") or "").strip()
        if not person:
            continue
        if not is_a_person_name(person):
            diag["mention_is_a_role_title_not_a_person"] += 1
            continue
        cks: set[str] = set()
        for col in ("org_mf", "org_rc"):
            value = (r.get(col) or "").strip()
            if not value:
                continue
            ck = key_of.get(value)
            if ck is not None and ck in forms:
                cks.add(ck)
        if not cks:
            continue
        status = (r.get("link_status") or "").strip()
        pid = (r.get("resolved_person_id") or "").strip()
        cluster = (r.get("mention_cluster_id") or "").strip()
        if status in ("resolved", "inferred", "snowball") and pid:
            grade, key, label = status, pid, (
                r.get("resolved_person_label") or person)
        else:
            # Named in print, absent from the seed roster. Keyed on the
            # mention cluster, which is the only person identity available
            # for someone the roster does not contain.
            grade = "gazette_only"
            key = cluster or f"MENTION:{person}"
            label = person
        diag[f"dyads_{grade}"] += 1
        for ck in cks:
            k = (ck, key)
            rec = agg.get(k)
            if rec is None:
                rec = agg[k] = {
                    "company_key": ck,
                    "person_key": key, "person_label": label,
                    "link_grade": grade, "roles": Counter(), "n_events": 0,
                    "first_event_date": "", "last_event_date": "",
                    "mention_cluster_id": cluster,
                    "resolved_org_id": (r.get("resolved_org_id") or ""),
                    "issue_uid": (r.get("issue_uid") or ""),
                    "source_url": (r.get("source_url") or ""),
                    "evidence_quote": (r.get("evidence_quote") or "")[:300],
                }
            elif GRADES.index(grade) < GRADES.index(rec["link_grade"]):
                # The same person may reach one company by two routes. Keep
                # the strongest, so a grade never reads weaker than the best
                # evidence actually available for that pair.
                rec["link_grade"] = grade
                rec["person_label"] = label
            role = (r.get("role_observed") or "").strip()
            if role:
                rec["roles"][role] += 1
            try:
                rec["n_events"] += int(r.get("n_events") or 0)
            except ValueError:
                pass
            for field, better in (("first_event_date", min),
                                  ("last_event_date", max)):
                v = (r.get(field) or "").strip()
                if v:
                    rec[field] = better(rec[field], v) if rec[field] else v

    rows: list[dict] = []
    per_company: dict[str, Counter] = defaultdict(Counter)
    for rec in agg.values():
        ck = rec["company_key"]
        meta = forms[ck]
        seed = int(rec["link_grade"] != "gazette_only")
        per_company[ck][rec["link_grade"]] += 1
        per_company[ck]["_total"] += 1
        per_company[ck]["_seed"] += seed
        rows.append({
            **rec,
            "matricule": meta.get("matricule", ""),
            "num_registre": meta.get("num_registre", ""),
            "legal_form": meta["legal_form"],
            "rne_name_fr": meta["rne_name_fr"],
            "jort_label": meta["jort_label"],
            "org_entity_id": entity_of.get(meta["jort_label"], ""),
            "is_seed_elite": seed,
            "role_primary": (rec["roles"].most_common(1)[0][0]
                             if rec["roles"] else ""),
            "roles": "|".join(f"{k}:{v}"
                              for k, v in rec["roles"].most_common()),
        })
    rows.sort(key=lambda r: (r["legal_form"], r["company_key"],
                             GRADES.index(r["link_grade"]), r["person_label"]))
    for ck, c in per_company.items():
        forms[ck]["n_persons"] = c["_total"]
        forms[ck]["n_persons_seed_elite"] = c["_seed"]
        forms[ck]["n_persons_gazette_only"] = c["gazette_only"]
    diag["person_company_links"] = len(rows)
    diag["distinct_persons"] = len({r["person_key"] for r in rows})
    diag["distinct_persons_seed_elite"] = len(
        {r["person_key"] for r in rows if r["is_seed_elite"]})
    diag["companies_with_a_named_person"] = len(per_company)
    return rows, dict(diag)


def run() -> dict:
    ensure_dirs()
    by_mf, by_rc, d_reg = load_register()
    if not by_mf and not by_rc:
        print("register not present under data/processed/rne -- nothing to do")
        return {}

    entity_of = {r["org_mention"]: r["org_entity_id"]
                 for r in _read("org_entity_members.csv")
                 if r.get("org_mention")}
    # Which of these companies is also a seed elite organisation. Only
    # identity-grade register links, same rule `resolve` applies.
    seed_of = {r["value_normalised"]: r["seed_org_id"]
               for r in _read("rne_org_links.csv")
               if r.get("is_identity") == "1" and r.get("seed_org_id")}

    companies, key_of = company_index(by_mf, by_rc)
    obs, d_gaz = gazette_forms(key_of)
    rows, d_form = build_forms(companies, obs, entity_of, seed_of)
    extra, d_name = register_name_only(companies, set(obs), seed_of)
    rows.extend(extra)

    forms = {r["company_key"]: r for r in rows}
    persons, d_person = company_persons(forms, key_of, entity_of)

    in_scope = [r for r in rows if r["legal_form"] in FORMS]
    _write("rne_company_forms.csv", in_scope, FIELDS_FORMS)
    _write("rne_company_persons.csv", persons, FIELDS_PERSONS)

    register_ids = len(companies)
    determined = len(in_scope)
    strict = [r for r in in_scope if r["legal_form"] in ("SARL", "SA")]
    diag = {
        "register_rows": d_reg.get("register_rows", 0),
        "register_companies": register_ids,
        **{f"gazette_{k}": v for k, v in d_gaz.items()},
        **{f"form_{k}": v for k, v in d_form.items()},
        **{f"name_only_{k}": v for k, v in d_name.items()},
        **d_person,
        "companies_in_scope": determined,
        "companies_sarl_or_sa_strict": len(strict),
        "form_undetermined": register_ids - determined,
        "form_undetermined_pct": round(
            100 * (register_ids - determined) / max(register_ids, 1), 1),
    }

    print("individuals connected to registered SARL and SA companies")
    for k in ("register_rows", "register_companies",
              "gazette_register_listed_companies_with_a_gazette_form",
              "gazette_identifier_not_in_register",
              "form_companies", "form_form_SARL", "form_form_SUARL",
              "form_form_SA", "form_conversions",
              "form_register_name_corroborates", "form_register_name_disagrees",
              "name_only_companies", "companies_in_scope",
              "companies_sarl_or_sa_strict",
              "form_undetermined", "form_undetermined_pct",
              "person_company_links", "distinct_persons",
              "distinct_persons_seed_elite",
              "companies_with_a_named_person",
              "dyads_resolved", "dyads_inferred", "dyads_snowball",
              "dyads_gazette_only"):
        if k in diag:
            v = diag[k]
            print(f"  {k:<52} {v:>12,}" if isinstance(v, int)
                  else f"  {k:<52} {v:>12}")
    print(f"  -- the register has NO officer table: all {diag.get('person_company_links', 0):,} "
          "person links come from JORT")
    print(f"  -- {diag['form_undetermined']:,} register identifiers "
          f"({diag['form_undetermined_pct']}%) have an UNDETERMINED form; "
          "that is not the same as 'not SARL/SA'")
    return diag


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(
        description="Individuals connected to registered SARL/SA companies."
    ).parse_args(argv)
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
