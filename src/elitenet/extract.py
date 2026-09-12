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
import html
import json
import re
from datetime import date
from pathlib import Path

from . import grammar as G
from .names import parse_org
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

# --- corporate action cues -> event_type. First match wins *within* a list. ---
# Person-level and organisation-level actions are kept apart because one clause
# routinely states both: "decide de la dissolution totale de la societe et la
# designation de Mr Brahim Hami comme liquidateur" is a dissolution *and* an
# appointment, and a single first-match-wins list silently dropped one of them.
CORP_CUES: list[tuple[str, str, str]] = [
    ("corp.renewed",   r"renouvellement\s+d[eu]\s+mandat|mandats?\s+renouvel|"
                       r"reconduction\s+d[eu]\s+mandat", "renewed"),
    ("corp.resigned",  r"d[ée]mission|d[ée]sist[ée]\s+de\s+s[ae]\s+fonction|"
                       r"renonc[ée]\s+[àa]\s+s[ae]\s+fonction", "resigned"),
    ("corp.revoked",   r"r[ée]vocation|r[ée]voqu[ée]|\bde\s+r[ée]voquer\b|"
                       r"il\s+est\s+mis\s+fin\s+aux\s+fonctions", "revoked"),
    # The infinitive forms carry a large share of appointments: "il a ete decide
    # de nommer ..." occurs in 4,983 blocks and "de designer" in 681, and the
    # earlier cue list caught neither.
    ("corp.appointed", r"a\s+nomm[ée]|ont\s+nomm[ée]|est\s+nomm[ée]|sont\s+nomm[ée]|"
                       r"\bde\s+nommer\b|\bde\s+d[ée]signer\b|\bnomme\s+(?:M|Mme|Mlle)|"
                       r"nomination\s+d|d[ée]sign(?:[ée]|ation)|coopt[ée]|"
                       r"nomm[ée]\s+en\s+qualit[ée]|appel[ée]\s+aux\s+fonctions", "appointed"),
    # "a cede/vendu ses parts" occurs in 1,396 blocks; the earlier cue matched
    # only the unaccented present tense and missed every past participle.
    ("corp.shares",    r"cession\s+de(?:s)?\s+(?:parts|actions)|"
                       r"transfert\s+de(?:s)?\s+(?:parts|actions)|"
                       r"(?:c[èe]de|c[ée]d[ée]s?|vendu|vend)\s+[^.\n]{0,140}?"
                       r"(?:parts|actions)", "shares_transferred"),
]

# Organisation-level actions, evaluated independently of the person-level list.
ORG_CUES: list[tuple[str, str, str]] = [
    ("corp.cap_up",    r"augmentation\s+d[uе]\s+capital|augmentation\s+de\s+capital|"
                       r"augmenter\s+le\s+capital|porter\s+le\s+capital",
     "capital_increased"),
    ("corp.cap_down",  r"r[ée]duction\s+d[uе]\s+capital|r[ée]duction\s+de\s+capital|"
                       r"r[ée]duire\s+le\s+capital", "capital_decreased"),
    # "dissolution totale de" and "dissolution definitive de" appear in 168
    # blocks and were missed by a pattern that allowed only "anticipee".
    ("corp.dissolved", r"dissolution\s+(?:\w+e?\s+)?de|de\s+dissoudre", "dissolved"),
    ("corp.liquidated", r"liquidation", "liquidated"),
    ("corp.renamed",   r"changement\s+de\s+(?:la\s+)?d[ée]nomination|nouvelle\s+d[ée]nomination",
     "renamed"),
    ("corp.hq",        r"transfert\s+d[uе]?\s*si[èe]ge|transf[ée]r[ée]\s+son\s+"
                       r"(?:si[èe]ge|adresse)|changement\s+d[eu]?['’]?\s*(?:si[èe]ge|adresse)",
     "headquarters_moved"),
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

# An association's officers are published as a bureau, with the role first and
# the name after a colon -- the reverse of the corporate "Name : role" layout:
#     Bureau :
#     - President : Mohamed Ben Sedrine,
#     - Secretaire general : Nooman Ben Ameur,
#     - Tresorerie : Lotfi Hedhili.
# This appears in 3,746 of the 7,144 association blocks and yielded nothing at
# all, because no action verb is present and the role precedes the name.
RE_BUREAU_ITEM = re.compile(
    r"^[ \t]*[-•*]?[ \t]*(?P<role>Pr[ée]sident(?:e)?|Vice[- ]pr[ée]sident(?:e)?|"
    r"Secr[ée]taire\s+g[ée]n[ée]ral(?:e)?(?:\s+adjoint(?:e)?)?|Secr[ée]taire|"
    r"Tr[ée]sorier(?:e)?(?:\s+adjoint(?:e)?)?|Tr[ée]sorerie|Membre)"
    r"[ \t]*:[ \t]*(?:(?i:M\.|Mr\.?|Mme|Mlle|Monsieur|Madame|Mademoiselle)\s+)?"
    r"(?P<name>" + G.NAME + r")",
    re.IGNORECASE | re.MULTILINE)

# "Denomination : X", but also "Denomination sociale : X", "Denomination de
# l'association : X" and "Raison sociale : X".
RE_DENOM = re.compile(
    r"(?:D[ée]nomination|Raison\s+social[e]?)\b[^:\n]{0,30}?[:：]\s*(?P<v>[^\n.]{2,90})",
    re.IGNORECASE)

# A block's first heading is very often the *action* rather than the company
# ("Nomination d'un nouveau gerant", "Transfert du siege social"). Taking it as
# the organisation name gave a wrong org on 12.3% of corporate and association
# blocks, and since the organisation anchors identity resolution, a wrong name
# there loses the tie entirely.
RE_ACTION_TITLE = re.compile(
    r"^(?:d[ée]signation|nomination|reconduction|renouvellement|cession|"
    r"cr[ée]ation|adoption|approbation|d[ée]cision|notice|extrait\b|"
    r"changement|augmentation|r[ée]duction|dissolution|liquidation|transfert|"
    r"d[ée]mission|r[ée]vocation|constitution|construction|modification|"
    r"homologation|extrait|avis|proc[èe]s|assembl[ée]e|convocation|"
    r"d[ée]nomination|raison\s+sociale|bureau|classification|si[èe]ge|"
    r"capital|objet|dur[ée]e|gestion|autres|cooperatives|coop[ée]ratives|"
    r"nombre|forme|adresse|matricule|registre|identifiant|activit[ée]|"
    r"exercice|r[ée]partition|associ[ée]s|g[ée]rance|g[ée]rant|administrateur|"
    r"commissaire|pr[ée]sident|secr[ée]taire|tr[ée]sor|membre|"
    r"actes?\b|bilans?|rectificatif|annonces|sommaire|fonds\s+de\s+commerce|"
    r"vente|location|adjonction|retrait|r[ée]partition|apport|fusion|"
    r"soci[ée]t[ée]s?\s+(?:anonymes?|[àa]\s+responsabilit[ée]|unipersonnelles?|"
    r"coop[ée]rative))", re.IGNORECASE)

# Lines that mention a legal form but describe something else. A capital line
# ("S.A au capital de 5 000 000 dinars") contains "S.A" and was therefore
# preferred over the real company name.
RE_NOT_A_NAME = re.compile(
    r"(?:au\s+capital|capital\s+(?:social|de)|si[èe]ge\s+social|"
    r"matricule|registre\s+de\s+commerce|^RC\b|^R\.C|exercice|"
    r"nombre\s+d|objet\s+social"
    # Closing and signature lines that sit where a name would.
    r"|^pour\s+extrait|^pour\s+le|^p/|^le\s+g[ée]ran|^la\s+g[ée]ran"
    # A bare legal form with no distinguishing name ("S.A.R.L non residente").
    r"|^(?:S\.?A\.?R\.?L|S\.?U\.?A\.?R\.?L|S\.?A)\b[\s,]*"
    r"(?:non\s+r[ée]sidente?|r[ée]sidente?|unipersonnelle)?[\s.]*$"
    r")", re.IGNORECASE)

RE_PROSE_HEAD = re.compile(
    r"^(?:Suivant|Selon|Aux?\s+termes|D['’]apr[èe]s|En\s+vertu|Au\s+capital|"
    r"MF|M\.F|Mat|RC\b|R\.C|CNSS|Le\s+|La\s+|Les\s+|Il\s+|Par\s+|Une\s+|"
    r"Il\s+ressort|Il\s+appert|Messieurs|Mesdames)", re.IGNORECASE)

# Tokens that mark a line as naming a company rather than describing an action.
RE_LEGAL_FORM_HINT = re.compile(
    r"\b(?:S\.?A\.?R\.?L|S\.?U\.?A\.?R\.?L|S\.?A\b|SICAR|SICAF|SICAV|"
    r"Soci[ée]t[ée]|St[ée]\b|Holding|Group[e]?|Compagnie|Etablissements?|"
    r"Entreprise|Association|Mutuelle|Coop[ée]rative)\b", re.IGNORECASE)


RE_NAMED_IN_PROSE = re.compile(
    r"(?:dite|d[ée]nomm[ée]e|sous\s+la\s+d[ée]nomination\s+(?:de|sociale\s+de)?|"
    r"sous\s+le\s+nom\s+de|la\s+soci[ée]t[ée]\s+)«?\s*(?P<v>[A-ZÀ-Þ][^,.;«»\n]{2,60})",
    re.IGNORECASE)


def _candidate_lines(text: str) -> list[str]:
    out = []
    for line in text.split("\n"):
        s = line.strip().strip("#*").strip()
        s = re.sub(r"\s+", " ", s).strip(" .,;:«»\"'*-")
        if len(s) < 3 or len(s) > 90:
            continue
        if RE_ACTION_TITLE.match(s) or RE_PROSE_HEAD.match(s):
            continue
        if G.RE_DATE_TXT.search(s) or "enregistr" in s.lower():
            continue
        if RE_NOT_A_NAME.search(s):
            continue
        out.append(s)
    return out


def org_name(text: str) -> str:
    """Best available organisation name for a corporate or association block.

    Tried in order: the stated denomination; a line that carries a legal-form
    marker and so plainly names a company; then any remaining line that is
    neither an action title nor running prose. Returning nothing is preferred
    to returning an action title, because a wrong name resolves to the wrong
    organisation while an empty one merely leaves the tie unresolved.
    """
    m = RE_DENOM.search(text)
    if m:
        value = _tidy_org(m.group("v"))
        if value and not RE_ACTION_TITLE.match(value):
            return value

    lines = _candidate_lines(text)
    for s in lines:
        if RE_LEGAL_FORM_HINT.search(s):
            return _tidy_org(s)
    if lines:
        return _tidy_org(lines[0])
    # Nothing in the layout names the company, but the prose often does:
    # "une societe ... est constituee dite Comptoir de Boulanger".
    m = RE_NAMED_IN_PROSE.search(text)
    return _tidy_org(m.group("v")) if m else ""


def _same_org(a: str, b: str) -> bool:
    """Whether two mentions normalise to the same organisation."""
    ka, kb = parse_org(a or "").match_key, parse_org(b or "").match_key
    return bool(ka) and ka == kb


def _tidy_org(raw: str) -> str:
    # The OCR layer leaves HTML entities in place, and an undecoded "&amp;"
    # survived into 2,654 organisation names, where it blocks resolution.
    s = html.unescape(raw or "")
    s = re.sub(r"\s+", " ", s).strip(" .,;:«»\"'*-")
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


# Dates an act cannot legitimately carry later than its own publication.
# `effective_date` is deliberately absent: an act published in 1974 may
# lawfully take effect in 1975, and 1,629 acts in this corpus take effect
# before their own date, which is equally lawful.
_CANNOT_POSTDATE_PUBLICATION = ("act_date", "registration_date", "filing_date")


def drop_impossible_dates(dates: dict, pub_date: str) -> dict:
    """An act cannot be published before it happens.

    Where a parsed date postdates the issue, the reading is wrong -- usually an
    OCR-damaged numeral, and the corpus shows the shape of it: an act printed
    "1976-01-31" in a 1974 issue whose day and month match the issue to within
    a week, so 1974 was read as 1976. The date is dropped rather than repaired
    by guessing, and the event falls back to the next available date.

    Shared by both extractors. It used to live only in the corporate path,
    which left 87 state acts asserting an act date after their own publication
    -- the kind of divergence that appears the moment two copies of a rule
    exist.
    """
    if not pub_date:
        return dates
    return {k: ("" if k in _CANNOT_POSTDATE_PUBLICATION and v and v > pub_date
                else v)
            for k, v in dates.items()}


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
    out = {k: v for k, v in drop_impossible_dates(out, pub_date).items() if v}
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

RE_CONVOCATION = re.compile(
    r"convocation|sont\s+convoqu[ée]s|ordre\s+du\s+jour\s+suivant", re.IGNORECASE)


def is_convocation(block: dict) -> bool:
    """True for a notice convening a future meeting.

    Its agenda reads like a list of acts ("1 - Augmentation du capital") but
    nothing in it has happened, so extracting from it invents events. The
    rubric catches most of these; a few sit under other rubrics, so the heading
    is checked too.
    """
    if block.get("domain") == "convocation":
        return True
    head = (block.get("heading") or "")[:120]
    return bool(RE_CONVOCATION.search(head))


def extract_corporate(block: dict) -> list[dict]:
    if is_convocation(block):
        return []
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

    # --- corporate parties: an organisation tied to another organisation - #
    # Kept apart from the person-level and organisation-level cue lists for the
    # same reason those are kept apart from each other: one clause routinely
    # states several acts, and a single first-match-wins pass drops all but one.
    #
    # The holder goes in counterparty_mention, which already exists for exactly
    # this -- an entity other than the subject firm -- and is already carried
    # through events.csv. `relation` is recorded in role_canonical so the layer
    # can be filtered without a schema change.
    #
    # Nothing is resolved here. Whether the holder and the subject are distinct
    # seed organisations is a resolution question, and a self-match is dropped
    # there, not guessed at here.
    # For a transfer, the company being bought into is named in the clause; for
    # a standing holding or an audit mandate it is the block's subject firm.
    mt = G.RE_ORG_TARGET.search(text)
    stated_target = _tidy_org(G.trim_org_party(mt.group("org"))) if mt else ""

    def _ok(name: str) -> bool:
        # A bare form marker with no name behind it ("la societe") resolves to
        # nothing and would only add noise.
        return len(name) >= 6 and bool(re.search(r"[A-Za-zÀ-ÿ]{3}", name))

    # The stated target wins wherever the clause names one, for every relation:
    # it is a targeted capture, while org_name() resolves on only 55% of these
    # blocks and sometimes returns a clause. Where no target is stated -- a
    # constitution listing its own associates, say -- the subject firm is right.
    for rx, relation, conf in (
        (G.RE_ORG_ACQUIRES,    "shares_acquired",       0.88),
        (G.RE_ORG_CEDES,       "shares_ceded",          0.88),
        (G.RE_ORG_SHAREHOLDER, "shareholder_confirmed", 0.80),
        (G.RE_ORG_SUBSCRIBES,  "capital_subscribed",    0.88),
        (G.RE_ORG_AUDITOR,     "auditor",               0.90),
        (G.RE_ORG_BRANCH,      "branch",                0.90),
    ):
        for m in rx.finditer(text):
            holder = _tidy_org(G.trim_org_party(m.group("org")))
            if not _ok(holder):
                continue
            target = stated_target if _ok(stated_target) else org
            # A self-tie compared on raw strings slips through: "la societe
            # Alpha Holding" and "Societe Alpha Holding" are the same firm and
            # differ only by an article. Compare on the normalised key that
            # resolution uses for exact matching. Resolution drops self-matches
            # again once both ends carry seed ids -- this only keeps the
            # obvious ones out of events.csv.
            if not _ok(target or "") or _same_org(target, holder):
                continue
            emit(event_type="org_tie", pattern_id=f"corp.org_{relation}",
                 counterparty_mention=holder, org_mention=target,
                 role_canonical=relation,
                 role_verbatim=_tidy_org(m.group(0))[:90],
                 extract_confidence=conf, evidence_quote=_quote(m.group(0)))

    # --- association bureau: "Role : Name" ------------------------------- #
    if block.get("domain") == "association":
        for m in RE_BUREAU_ITEM.finditer(text):
            person = G.clean_name(m.group("name"))
            if not person:
                continue
            canon, verb = G.match_role(m.group("role"))
            emit(event_type="appointed", pattern_id="assoc.bureau",
                 person_mention=person,
                 role_canonical=canon or "association_officer",
                 role_verbatim=verb or m.group("role"),
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

        # Organisation-level action, if any: emitted on its own terms.
        for pid, cue, typ in ORG_CUES:
            if re.search(cue, folded, re.IGNORECASE):
                emit(event_type=typ, pattern_id=pid,
                     amount_dt=(G.parse_capital(clause)
                                if typ.startswith("capital") else "") or "",
                     extract_confidence=0.85, evidence_quote=_quote(clause))
                break

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

        # Pair each person with their own role where the text states one, so a
        # clause naming a chair and a chief executive does not give both the
        # same title.
        pairs = G.pair_person_roles(clause)
        # "Messieurs Foued Noomen et Nizar Frikha" gives only the first name a
        # title of its own, so the rest never reached the pairing at all.
        known = {n for n, _s, _r in pairs}
        pairs += [(n, "", "") for n in G.split_plural_title(clause) if n not in known]
        if not pairs:
            pairs = [(n, "", "") for n in G.split_person_list(clause)]
        if not pairs:
            continue
        # Where the text gives some of the people named their own role and
        # others none, the ones without are usually bystanders rather than the
        # object of the action: "de nommer M. X en tant que co-gerant ainsi que
        # M. Y a confie 10% de ses parts" appoints X only, and attributing the
        # clause role to Y invented an appointment.
        #
        # The exception is a role stated once after a list of names -- "Mr A et
        # Mr B sont nommes les gerants" anchors only the last -- where the role
        # plainly governs everyone. Treating that as one appointee dropped the
        # others, so a single anchor on the last person is shared instead.
        if etype in {"appointed", "renewed"}:
            anchored = [i for i, (_n, _s, r) in enumerate(pairs) if r]
            if len(anchored) == 1 and len(pairs) > 1 and anchored[0] == len(pairs) - 1:
                shared = pairs[-1][2]
                pairs = [(n, s, shared) for n, s, _r in pairs]
            elif anchored:
                pairs = [(n, s, r) for n, s, r in pairs if r]
        for name, married, own_role in pairs:
            canon, verb = (G.match_role(own_role) if own_role else ("", ""))
            # "Monsieur X, membre de l'ordre des experts comptables, comme
            # commissaire aux comptes" states a professional qualification
            # before the role conferred. A generic `member` is therefore
            # yielded to a specific role found later in the clause.
            if canon == "member" and role_canon and role_canon != "member":
                canon, verb = role_canon, role_verb
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

    dates = drop_impossible_dates(
        {"act_date": act_date, "effective_date": eff,
         "pub_date": block["pub_date"]}, block["pub_date"])
    act_date = dates["act_date"]
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
        rest = m.group("rest") or ""
        mnum = G.RE_ACT_NUMBER.search(rest)
        mdate = G.RE_VISA_DATE.search(rest)
        mgist = G.RE_VISA_GIST.search(rest)
        cited_date = G.parse_date_string(mdate.group("date")) if mdate else None
        citations.append({
            "block_uid": block["block_uid"], "issue_uid": block["issue_uid"],
            "citing_act_number": act_number, "citing_act_date": act_date,
            "cited_kind": re.sub(r"\s+", " ", m.group("kind")).strip().lower(),
            "cited_number": mnum.group("num").replace(" ", "") if mnum else "",
            "cited_date": cited_date.isoformat() if cited_date else "",
            "cited_gist": _quote(mgist.group("gist") if mgist else "", 180),
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
