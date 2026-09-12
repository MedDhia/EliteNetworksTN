"""Stage 5 -- extract dated relational events from blocks and acts.

The canonical output is one ``events`` table regardless of source. Each row is
a dyadic assertion (a person and an organisation, or an organisation and an
organisation) carrying an event type, a role, up to four distinct dates, and a
verbatim quote plus page citation so any claim can be checked at source.

Dates are never collapsed. A single announcement routinely carries the date of
the act itself, the date it was registered for tax, the date it was filed at
the court registry, and -- separately -- the date the gazette published it. The
act date is what an event happened on; the publication date is only an upper
bound on it.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import date
from pathlib import Path

from . import grammar as G
from .paths import INTERIM, PROCESSED, ensure_dirs, load_config

EVENT_FIELDS = [
    "event_id", "event_type", "source_type", "block_uid", "issue_uid",
    "collection", "year", "issue", "folio_page", "ocr_page",
    "person_mention", "person_married_name",
    "org_mention", "org_mf", "counterparty_mention",
    "role_canonical", "role_verbatim", "portfolio", "ministry",
    "act_date", "registration_date", "filing_date", "effective_date", "pub_date",
    "event_date", "event_date_source", "event_date_lo", "event_date_hi",
    "date_precision", "mandate_years", "amount_dt", "legal_form", "domain",
    "extractor", "pattern_id", "extract_confidence", "evidence_quote",
    "needs_review",
]

CITATION_FIELDS = [
    "block_uid", "issue_uid", "citing_act_number", "citing_act_date",
    "cited_kind", "cited_number", "cited_date", "cited_gist", "relation",
]

# --- corporate action cues -> event_type. Order matters: first match wins. ---
CORP_CUES: list[tuple[str, str, str]] = [
    ("corp.renewed",   r"renouvellement\s+du\s+mandat|mandats?\s+renouvel", "renewed"),
    ("corp.resigned",  r"d[ée]mission", "resigned"),
    ("corp.revoked",   r"r[ée]vocation|r[ée]voqu[ée]|il\s+est\s+mis\s+fin\s+aux\s+fonctions",
     "revoked"),
    ("corp.appointed", r"a\s+nomm[ée]|ont\s+nomm[ée]|est\s+nomm[ée]|sont\s+nomm[ée]|"
                       r"nomination\s+d|d[ée]sign[ée]|coopt[ée]|"
                       r"nomm[ée]\s+en\s+qualit[ée]|appel[ée]\s+aux\s+fonctions", "appointed"),
    ("corp.shares",    r"cession\s+de(?:s)?\s+(?:parts|actions)|transfert\s+de(?:s)?\s+"
                       r"(?:parts|actions)|c[èe]de\s+", "shares_transferred"),
    ("corp.cap_up",    r"augmentation\s+d[uе]\s+capital|augmentation\s+de\s+capital",
     "capital_increased"),
    ("corp.cap_down",  r"r[ée]duction\s+d[uе]\s+capital|r[ée]duction\s+de\s+capital",
     "capital_decreased"),
    ("corp.dissolved", r"dissolution\s+(?:anticip[ée]e\s+)?de", "dissolved"),
    ("corp.liquidated", r"liquidation", "liquidated"),
    ("corp.renamed",   r"changement\s+de\s+(?:la\s+)?d[ée]nomination|nouvelle\s+d[ée]nomination",
     "renamed"),
    ("corp.hq",        r"transfert\s+d[uе]\s+si[èe]ge", "headquarters_moved"),
]

# Roles that only appear as an appointment target, used when a clause names a
# role and a person but no explicit verb (e.g. "Gerance : Monsieur X").
RE_ROLE_COLON = re.compile(
    r"^\s*(?:G[ée]ran(?:t|ce)s?|Administrateurs?|Commissaires?\s+aux\s+comptes|"
    r"Pr[ée]sident[^\n:]{0,40}|Directeur[^\n:]{0,40}|Liquidateurs?)\s*[:：]",
    re.IGNORECASE)

# A board is published as an action, then a bulleted list of names, then the
# role that governs the whole list:
#     ... a nomme :
#     - Madame Cyrine Ben Ali Mabrouk
#     - Monsieur Fathi Bhoury.
#     en qualite d'administrateurs pour une duree de trois exercices sociaux.
# Splitting by line loses the link between the names and their shared role, so
# the list is matched as a unit before the clause-level pass runs.
RE_LIST_APPOINT = re.compile(
    r"(?P<verb>a\s+nomm[ée]{1,2}s?|ont\s+nomm[ée]{1,2}s?|sont\s+nomm[ée]{1,2}s?|"
    r"a\s+d[ée]sign[ée]{1,2}s?|ont\s+[ée]lu|sont\s+[ée]lus)\s*:?\s*\n"
    r"(?P<items>(?:\s*[-•*][^\n]*\n){1,30})"
    r"\s*en\s+qualit[ée]s?\s+d[e']\s*(?P<role>[^,.;\n]{3,90})",
    re.IGNORECASE)

RE_DENOM = re.compile(
    r"(?:D[ée]nomination|Raison\s+sociale)\s*(?:sociale)?\s*[:：]\s*(?P<v>[^\n.]{2,90})",
    re.IGNORECASE)
RE_GENERIC_HEAD = re.compile(
    r"^(?:constitution|construction|gestion|homologation|modification|cession|vente|"
    r"avis|notice|rectificatif|dissolution|liquidation|augmentation|r[ée]duction|"
    r"soci[ée]t[ée]s?\s+(?:anonymes?|[àa]\s+responsabilit[ée]|unipersonnelles?)|"
    r"autres\s+soci[ée]t[ée]s|annonces|sommaire)", re.IGNORECASE)
RE_PROSE_HEAD = re.compile(
    r"^(?:Suivant|Selon|Aux?\s+termes|D['’]apr[èe]s|En\s+vertu|Si[èe]ge|Au\s+capital|"
    r"MF|M\.F|Mat|Le\s+|La\s+|Il\s+|Les\s+associ)", re.IGNORECASE)


def org_name(text: str) -> str:
    """Best available organisation name for a corporate block."""
    m = RE_DENOM.search(text)
    if m:
        return _tidy_org(m.group("v"))
    for line in text.split("\n"):
        s = line.strip().strip("#*").strip()
        if len(s) < 3 or len(s) > 90:
            continue
        if RE_GENERIC_HEAD.match(s) or RE_PROSE_HEAD.match(s):
            continue
        if G.RE_DATE_TXT.search(s) or "enregistr" in s.lower():
            continue
        return _tidy_org(s)
    return ""


def _tidy_org(raw: str) -> str:
    s = re.sub(r"\s+", " ", raw).strip(" .,;:«»\"'*")
    s = re.sub(r"\s*[«\"]\s*", " ", s).strip()
    return s[:120]


def _clauses(text: str) -> list[str]:
    """Split a block into clause-sized units for action detection.

    Resolutions are published as bullets or short sentences, so keeping units
    small is what stops a resignation in one bullet being attributed to a
    person named in the next.
    """
    out: list[str] = []
    for line in re.split(r"\n+", text):
        line = line.strip()
        if not line:
            continue
        if len(line) < 400:
            out.append(line)
        else:
            out.extend(p.strip() for p in re.split(r"(?<=[.;])\s+", line) if p.strip())
    return out


def _event_id(*parts: object) -> str:
    key = "|".join(str(p) for p in parts)
    return "EV_" + hashlib.blake2b(key.encode(), digest_size=10).hexdigest()


def _quote(clause: str, limit: int = 200) -> str:
    return re.sub(r"\s+", " ", clause).strip()[:limit]


def _dates_for_block(text: str, pub_date: str) -> dict:
    """Pull the several distinct dates a block can carry."""
    out: dict[str, str] = {}
    for key, rx in (
        ("act_date", G.RE_ACT_DATE),
        ("registration_date", G.RE_REG_DATE),
        ("filing_date", G.RE_FILING_DATE),
        ("effective_date", G.RE_EFFECTIVE_DATE),
    ):
        m = rx.search(text)
        if m:
            d = G.parse_date_string(m.group("date"))
            if d:
                out[key] = d.isoformat()
    if "act_date" not in out:
        m = G.RE_ACT_DATE_ALT.search(text)
        if m:
            d = G.parse_date_string(m.group("date"))
            if d:
                out["act_date"] = d.isoformat()
    out["pub_date"] = pub_date
    return out


def _resolve_event_date(dates: dict, pub_date: str) -> tuple[str, str, str, str, str]:
    """Choose the event date and express what is and is not known about it.

    Priority runs effective > act > filing > registration > publication. When
    only the publication date is available the event is interval-censored: it
    happened at or before publication, and the lower bound is left open rather
    than invented.
    """
    for key, src in (("effective_date", "effective"), ("act_date", "act"),
                     ("filing_date", "filing"), ("registration_date", "registration")):
        if dates.get(key):
            d = dates[key]
            return d, src, d, d, "exact"
    if pub_date:
        return pub_date, "pub_only", "", pub_date, "pub_only"
    return "", "none", "", "", "unknown"


# --------------------------------------------------------------------------- #
# corporate and association blocks
# --------------------------------------------------------------------------- #

def extract_corporate(block: dict) -> list[dict]:
    text = block["text"]
    org = org_name(text)
    mfm = G.RE_MF.search(text)
    mf = G.normalise_mf(mfm.group("mf")) if mfm else ""
    dates = _dates_for_block(text, block["pub_date"])
    ev_date, ev_src, ev_lo, ev_hi, precision = _resolve_event_date(dates, block["pub_date"])
    capital = G.parse_capital(text)
    is_constitution = block.get("section") == "constitution"

    base = {
        "source_type": "annonce", "block_uid": block["block_uid"],
        "issue_uid": block["issue_uid"], "collection": block["collection"],
        "year": block["year"], "issue": block["issue"],
        "folio_page": block.get("folio_page_start") or "",
        "ocr_page": block.get("ocr_page_start") or "",
        "org_mention": org, "org_mf": mf,
        "ministry": "", "portfolio": "",
        "act_date": dates.get("act_date", ""),
        "registration_date": dates.get("registration_date", ""),
        "filing_date": dates.get("filing_date", ""),
        "effective_date": dates.get("effective_date", ""),
        "pub_date": block["pub_date"],
        "event_date": ev_date, "event_date_source": ev_src,
        "event_date_lo": ev_lo, "event_date_hi": ev_hi,
        "date_precision": precision,
        "legal_form": block.get("legal_form", ""), "domain": block.get("domain", ""),
        "extractor": "rule", "needs_review": False,
    }

    events: list[dict] = []
    seen: set[tuple] = set()

    def emit(**kw):
        row = {**base, **kw}
        row.setdefault("person_mention", "")
        row.setdefault("person_married_name", "")
        row.setdefault("counterparty_mention", "")
        row.setdefault("role_canonical", "")
        row.setdefault("role_verbatim", "")
        row.setdefault("mandate_years", "")
        row.setdefault("amount_dt", "")
        key = (row["event_type"], row["person_mention"], row["role_canonical"],
               row["org_mention"], row["event_date"], row.get("counterparty_mention", ""))
        if key in seen:
            return
        seen.add(key)
        row["event_id"] = _event_id(block["block_uid"], *key)
        events.append(row)

    # --- organisation-level events -------------------------------------- #
    if is_constitution and org:
        emit(event_type="constituted", pattern_id="corp.constituted",
             amount_dt=capital if capital is not None else "",
             extract_confidence=0.95, evidence_quote=_quote(block["heading"] or text))

    # --- representation: a legal person acting through an individual ----- #
    for m in G.RE_REPRESENTED.finditer(text):
        # Trim a trailing verb phrase before validating ("Mourad Fradi a ete nommee").
        raw = re.split(r"\s+(?:a|ont|est|sont)\s+", m.group("name"))[0]
        rep = G.clean_name(raw)
        if rep:
            emit(event_type="represented_by", pattern_id="corp.represented_by",
                 person_mention=rep, counterparty_mention=_tidy_org(m.group("org")),
                 role_canonical="representant", role_verbatim="représentée par",
                 extract_confidence=0.90, evidence_quote=_quote(m.group(0)))

    # --- bulleted appointment lists with a trailing shared role ---------- #
    listed: set[str] = set()
    for m in RE_LIST_APPOINT.finditer(text):
        canon, verb = G.match_role(m.group("role"))
        # The stated mandate term can sit inside the role phrase itself
        # ("administrateurs pour une duree de trois exercices sociaux"), so
        # search the whole match and a short tail.
        years = G.mandate_years(m.group(0) + text[m.end(): m.end() + 160])
        for item in m.group("items").split("\n"):
            item = item.strip().lstrip("-•*").strip()
            if not item:
                continue
            # A list entry may be a legal person acting through an individual;
            # the representation edge is emitted separately above, so here the
            # appointee is the legal person and is recorded as such.
            head = re.split(r"\s+repr[ée]sent[ée]e?\s+par\s+", item)[0]
            # An entry naming a legal person is an organisation, so it must not
            # go through the person validator, which requires two tokens and
            # would silently drop a board member named "La Societe CFI".
            is_org = bool(re.match(r"^(?:La\s+)?(?:Soci[ée]t[ée]|STE|Ste|SARL|SA)\b",
                                   head, re.IGNORECASE))
            if is_org and len(_tidy_org(head)) >= 3:
                emit(event_type="appointed", pattern_id="corp.list_org_member",
                     counterparty_mention=_tidy_org(head), role_canonical=canon,
                     role_verbatim=verb, mandate_years=years if years is not None else "",
                     extract_confidence=0.88, evidence_quote=_quote(item))
                continue
            person = G.clean_name(re.sub(r"^(?:Monsieur|Madame|Mademoiselle|M\.|Mme|Mlle)\s+",
                                         "", head, flags=re.IGNORECASE))
            if person:
                listed.add(person)
                emit(event_type="appointed", pattern_id="corp.list_appoint",
                     person_mention=person, role_canonical=canon, role_verbatim=verb,
                     mandate_years=years if years is not None else "",
                     extract_confidence=0.92, evidence_quote=_quote(item),
                     needs_review=not canon)

    # --- clause-level actions -------------------------------------------- #
    for clause in _clauses(text):
        folded = G.strip_accents(clause).lower()
        etype, pattern_id = "", ""
        for pid, cue, typ in CORP_CUES:
            if re.search(cue, folded, re.IGNORECASE):
                etype, pattern_id = typ, pid
                break

        # Clause-level role, used only as a fallback for people who do not
        # carry their own "en qualite de" phrase.
        role_canon, role_verb = G.match_role(clause)

        # A role heading with a colon and no verb still names an appointment.
        if not etype and RE_ROLE_COLON.match(clause) and role_canon:
            etype, pattern_id = "appointed", "corp.role_colon"
        # Founding officers in a constitution act.
        if not etype and is_constitution and role_canon:
            etype, pattern_id = "appointed", "corp.constitution_officer"

        if not etype:
            continue

        years = G.mandate_years(clause)
        amount = G.parse_capital(clause) if etype.startswith("capital") else None

        if etype in {"capital_increased", "capital_decreased", "dissolved",
                     "liquidated", "renamed", "headquarters_moved"}:
            emit(event_type=etype, pattern_id=pattern_id,
                 amount_dt=amount if amount is not None else "",
                 extract_confidence=0.85, evidence_quote=_quote(clause))
            continue

        # Pair each person with their own role where the text states one, so a
        # clause naming a chair and a chief executive does not give both the
        # same title.
        pairs = G.pair_person_roles(clause)
        if not pairs:
            pairs = [(n, "", "") for n in G.split_person_list(clause)]
        if not pairs:
            continue
        for name, married, own_role in pairs:
            canon, verb = (G.match_role(own_role) if own_role else ("", ""))
            if not canon:
                canon, verb = role_canon, role_verb
            # Already captured with an explicit role by the list pass.
            if etype == "appointed" and not canon and name in listed:
                continue
            emit(event_type=etype, pattern_id=pattern_id, person_mention=name,
                 person_married_name=married,
                 role_canonical=canon, role_verbatim=verb,
                 mandate_years=years if years is not None else "",
                 extract_confidence=0.90 if canon else 0.70,
                 evidence_quote=_quote(clause), needs_review=not canon)
    return events


# --------------------------------------------------------------------------- #
# state acts
# --------------------------------------------------------------------------- #

def extract_state(block: dict) -> tuple[list[dict], list[dict]]:
    text = block["text"]
    ministry = block.get("ministry", "")
    act_number = block.get("act_number", "")

    head = block.get("heading", "") or text[:400]
    act_date = ""
    mh = G.RE_ACT_HEAD.search(head)
    if mh:
        d = G.parse_date_string(mh.group("date"))
        if d:
            act_date = d.isoformat()
    if not act_number:
        # Lazy matching in the head pattern can skip the optional number group,
        # so the act number is read with its own pattern.
        mn = G.RE_ACT_NUMBER.search(head)
        if mn:
            act_number = mn.group("num").replace(" ", "")
    eff = ""
    me = G.RE_EFFECTIVE_DATE.search(text)
    if me:
        d = G.parse_date_string(me.group("date"))
        if d:
            eff = d.isoformat()

    dates = {"act_date": act_date, "effective_date": eff, "pub_date": block["pub_date"]}
    ev_date, ev_src, ev_lo, ev_hi, precision = _resolve_event_date(dates, block["pub_date"])

    base = {
        "source_type": "act", "block_uid": block["block_uid"],
        "issue_uid": block["issue_uid"], "collection": block["collection"],
        "year": block["year"], "issue": block["issue"],
        "folio_page": block.get("folio_page_start") or "",
        "ocr_page": block.get("ocr_page_start") or "",
        "org_mention": ministry, "org_mf": "", "ministry": ministry,
        "act_date": act_date, "registration_date": "", "filing_date": "",
        "effective_date": eff, "pub_date": block["pub_date"],
        "event_date": ev_date, "event_date_source": ev_src,
        "event_date_lo": ev_lo, "event_date_hi": ev_hi,
        "date_precision": precision,
        "legal_form": "", "domain": "state",
        "extractor": "rule", "needs_review": False,
    }

    events: list[dict] = []
    seen: set[tuple] = set()

    def emit(**kw):
        row = {**base, **kw}
        for k in ("person_mention", "person_married_name", "counterparty_mention",
                  "role_canonical", "role_verbatim", "portfolio"):
            row.setdefault(k, "")
        row.setdefault("mandate_years", "")
        row.setdefault("amount_dt", "")
        key = (row["event_type"], row["person_mention"], row["role_canonical"],
               row["portfolio"], row["event_date"])
        if key in seen:
            return
        seen.add(key)
        row["event_id"] = _event_id(block["block_uid"], *key)
        events.append(row)

    # "est charge des fonctions de X" -- an acting assignment, which the
    # gazette uses far more than titular appointment (10,731 vs 3,200 in the
    # window), and which is legally distinct, so it keeps its own type.
    for m in G.RE_CHARGE.finditer(text):
        name = G.clean_name(m.group("name"))
        if not name:
            continue
        canon, verb = G.match_role(m.group("role"))
        emit(event_type="charged_with_functions", pattern_id="state.charge",
             person_mention=name, person_married_name=G.clean_name(m.group("spouse") or ""),
             role_canonical=canon, role_verbatim=verb, portfolio=verb,
             extract_confidence=0.93, evidence_quote=_quote(m.group(0)),
             needs_review=not canon)

    for m in G.RE_NOMME.finditer(text):
        name = G.clean_name(m.group("name"))
        if not name:
            continue
        canon, verb = G.match_role(m.group("role"))
        emit(event_type="appointed", pattern_id="state.nomme",
             person_mention=name, person_married_name=G.clean_name(m.group("spouse") or ""),
             role_canonical=canon, role_verbatim=verb, portfolio=verb,
             extract_confidence=0.92, evidence_quote=_quote(m.group(0)),
             needs_review=not canon)

    # Cabinet lists: "Sont nommes Messieurs : - Name : portfolio,"
    for head in G.RE_LIST_HEAD.finditer(text):
        tail = text[head.end(): head.end() + 3000]
        for item in G.RE_LIST_ITEM.finditer(tail):
            name = G.clean_name(item.group("name"))
            if not name:
                continue
            role_text = item.group("role")
            canon, verb = G.match_role(role_text)
            # A bulleted "Name : role" list is not necessarily a cabinet: the
            # same layout is used for commission seats, where each entry reads
            # "representant du ministere de X". Defaulting these to `minister`
            # would invent cabinet members, so the role is taken as written and
            # a body representative is typed as such.
            is_delegate = re.search(
                r"repr[ée]sentante?s?\s+(?:du|de\s+la|de\s+l'|le|les|de)\s+",
                role_text, re.IGNORECASE)
            if is_delegate:
                canon = "representant"
            etype = "delegated_to_body" if is_delegate else "appointed"
            emit(event_type=etype, pattern_id="state.list",
                 person_mention=name, role_canonical=canon,
                 role_verbatim=verb, portfolio=verb,
                 extract_confidence=0.90 if canon else 0.70,
                 evidence_quote=_quote(item.group(0)), needs_review=not canon)

    for m in G.RE_CESSATION.finditer(text):
        name = G.clean_name(m.group("name"))
        if name:
            emit(event_type="terminated", pattern_id="state.cessation",
                 person_mention=name, extract_confidence=0.90,
                 evidence_quote=_quote(m.group(0)))

    for m in G.RE_RETIREMENT.finditer(text):
        name = G.clean_name(m.group("name"))
        if name:
            emit(event_type="retired", pattern_id="state.retirement",
                 person_mention=name, extract_confidence=0.88,
                 evidence_quote=_quote(m.group(0)))

    # --- citation graph ------------------------------------------------- #
    citations: list[dict] = []
    heading_l = (block.get("heading") or "").lower()
    relation = ("modifies" if "modifiant" in heading_l
                else "abrogates" if "abrogeant" in heading_l else "cites")
    for m in G.RE_VISA.finditer(text):
        cited_date = G.parse_date_string(m.group("date") or "")
        citations.append({
            "block_uid": block["block_uid"], "issue_uid": block["issue_uid"],
            "citing_act_number": act_number, "citing_act_date": act_date,
            "cited_kind": re.sub(r"\s+", " ", m.group("kind")).strip().lower(),
            "cited_number": (m.group("num") or "").replace(" ", ""),
            "cited_date": cited_date.isoformat() if cited_date else "",
            "cited_gist": _quote(m.group("gist") or "", 180),
            "relation": relation,
        })
    return events, citations


# --------------------------------------------------------------------------- #
# driver
# --------------------------------------------------------------------------- #

def run(limit: int | None = None) -> dict:
    ensure_dirs()
    cfg = load_config("vocab_events")
    relational = set(cfg["relational_domains"])

    ev_path = INTERIM / "events_raw.jsonl"
    stats = {"blocks": 0, "blocks_with_events": 0, "events": 0, "citations": 0,
             "corporate_blocks": 0, "state_acts": 0, "skipped_domain": 0}
    by_type: dict[str, int] = {}

    with (INTERIM / "blocks.jsonl").open(encoding="utf-8") as src, \
         ev_path.open("w", encoding="utf-8") as out, \
         (INTERIM / "act_citations.csv").open("w", encoding="utf-8", newline="") as cit_fh:
        cit = csv.DictWriter(cit_fh, fieldnames=CITATION_FIELDS)
        cit.writeheader()
        for i, line in enumerate(src):
            if limit and i >= limit:
                break
            block = json.loads(line)
            stats["blocks"] += 1
            if block["block_type"] == "act":
                stats["state_acts"] += 1
                events, citations = extract_state(block)
                for c in citations:
                    cit.writerow(c)
                stats["citations"] += len(citations)
            elif block.get("domain") in relational:
                stats["corporate_blocks"] += 1
                events = extract_corporate(block)
            else:
                stats["skipped_domain"] += 1
                continue
            if events:
                stats["blocks_with_events"] += 1
            for e in events:
                by_type[e["event_type"]] = by_type.get(e["event_type"], 0) + 1
                out.write(json.dumps({k: e.get(k, "") for k in EVENT_FIELDS},
                                     ensure_ascii=False) + "\n")
                stats["events"] += 1

    stats["by_type"] = dict(sorted(by_type.items(), key=lambda kv: -kv[1]))
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Extract dated events from blocks.")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)
    stats = run(limit=args.limit)
    by_type = stats.pop("by_type", {})
    for k, v in stats.items():
        print(f"  {k:22} {v}")
    print("  by event_type:")
    for k, v in by_type.items():
        print(f"    {k:26} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
