"""Turn cleaned JORT prose into structured personnel events.

The gazette publishes appointments in a small number of highly conventional
forms that have drifted only slowly since 1957.  Two layers do the work:

``iter_acts``     splits an issue into administrative acts (decret / arrete /
                  decision), each carrying the ministry heading it appeared
                  under, its number, its date and its signatory.

``extract_events``  reads the operative clauses inside an act and emits one
                  row per (person, office) transition: appointment,
                  termination, board seat, renewal, retirement — plus the
                  succession link when the text names the outgoing holder.

Everything here stays close to the source: fields ending in ``_raw`` hold the
surface string, and normalisation is deferred to :mod:`eltn.normalize` so that
coding decisions remain auditable against the published text.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field, asdict
from typing import Iterator

from .dates import parse_date, effective_date
from .textnorm import Block, body_start, to_blocks, arabic_ratio

# --------------------------------------------------------------------------
# Authority context: the ministry / institution heading an act sits under.
# --------------------------------------------------------------------------

AUTHORITY_HEADING = re.compile(
    r"^\s*("
    r"MINIST[ÈE]RE\b.*|"
    r"SECR[ÉE]TARIAT\s+D'[ÉE]TAT\b.*|"
    r"PR[ÉE]SIDENCE\s+DE\s+LA\s+R[ÉE]PUBLIQUE.*|"
    r"PR[ÉE]SIDENCE\s+DU\s+GOUVERNEMENT.*|"
    r"PREMIER\s+MINIST[ÈE]RE.*|"
    r"CHEF(?:FE)?\s+DU\s+GOUVERNEMENT.*|"
    r"ASSEMBL[ÉE]E\b.*|"
    r"CONSEIL\b.*|"
    r"BANQUE\s+CENTRALE.*|"
    r"HAUTE?\s+(AUTORIT[ÉE]|INSTANCE)\b.*|"
    r"INSTANCE\b.*|"
    r"COUR\s+(DES\s+COMPTES|DE\s+CASSATION).*|"
    r"TRIBUNAL\s+ADMINISTRATIF.*"
    r")\s*$",
    re.I,
)

# Section headings that classify the acts beneath them.
SECTION_HEADING = re.compile(
    r"^\s*(NOMINATIONS?|CESSATIONS?\s+DE\s+FONCTIONS?|MOUVEMENTS?|D[ÉE]MISSIONS?|"
    r"MISE\s+[ÀA]\s+LA\s+RETRAITE|D[ÉE]TACHEMENTS?|R[ÉE]INT[ÉE]GRATIONS?|"
    r"NOMINATION\b.*|CESSATION\b.*)\s*$",
    re.I,
)

# --------------------------------------------------------------------------
# Act headers
# --------------------------------------------------------------------------

_ACT_KINDS = r"(?P<kind>d[ée]crets?|arr[êe]t[ée]s?|d[ée]cisions?)"
_QUALIFIER = (
    r"(?P<qualifier>\s+(?:pr[ée]sidentiels?|gouvernementaux?|gouvernementals?|"
    r"gouvernemental|-?\s*loi))?"
)
_NUM = r"(?:n\s*[°ᵒoº]?\s*(?P<number>[\d]{2,4}\s*[-–]\s*[\d]{1,5}))?"

# "Par decret n° 87-1260 du 27 octobre 1987 :"  /  "Par arrete du ministre des
# finances du 6 aout 2011."  — the short form used for personnel acts.
PAR_ACT_RE = re.compile(
    r"^Par\s+" + _ACT_KINDS + _QUALIFIER + r"\s*"
    r"(?P<issuer>(?:de\s+la\s+|du\s+|des\s+|de\s+l'|de\s+)[^,\n]{0,120}?)?\s*"
    + _NUM + r"[^.:\n]{0,40}?"
    r"(?:\s*,?\s*(?:en\s+)?date\s+du|\s+du)\s+(?P<date>[^,.:;]{4,40})",
    re.I,
)

# Long-form act with a title: "Decret n° 2015-1142 du 26 aout 2015, portant ..."
TITLED_ACT_RE = re.compile(
    r"^(?P<kind>D[ée]cret|Arr[êe]t[ée]|D[ée]cision|Loi)"
    r"(?P<qualifier>\s+(?:[Pp]r[ée]sidentiel|[Gg]ouvernemental|-?\s*loi))?"
    r"\s*" + _NUM + r"[^,\n]{0,140}?\bdu\s+(?P<date>[^,;]{4,40})\s*,?\s*"
    r"(?P<title>(?:portant|relatif|fixant|modifiant|compl[ée]tant|abrogeant)\b.{0,400})?",
    re.I,
)

# Fallback for the 1957-1980 uppercase style: "DECRET N° 75-601 du 9 septembre".
UPPER_ACT_RE = re.compile(
    r"^(?P<kind>D[ÉE]CRET|ARR[ÊE]T[ÉE]|D[ÉE]CISION)S?\b"
    r"[^,\n]{0,120}?\bdu\s+(?P<date>[^,;]{4,40})",
    re.I,
)

PERSONNEL_TITLE = re.compile(
    r"\b(nomination|cessation\s+de\s+fonction|mise\s+[àa]\s+la\s+retraite|"
    r"d[ée]charge|mouvement|d[ée]mission|d[ée]tachement|r[ée]int[ée]gration|"
    r"attribution\s+de\s+fonctions?|renouvellement\s+du\s+mandat|d[ée]signation)\b",
    re.I,
)

SIGNATORY_RE = re.compile(
    r"(?P<office>Le\s+Pr[ée]sident\s+de\s+la\s+R[ée]publique(?:\s+tunisienne)?(?:\s+par\s+int[ée]rim)?|"
    r"Le\s+Premier\s+[Mm]inistre|La?\s+Chef(?:fe)?\s+du\s+[Gg]ouvernement|"
    r"Le\s+[Mm]inistre\s+[^,\n]{3,80}?|La\s+[Mm]inistre\s+[^,\n]{3,80}?|"
    r"Le\s+[Ss]ecr[ée]taire\s+d'[ÉE]tat[^,\n]{0,80}?)"
    r"\s+(?P<name>(?:[A-ZÉÈÊÀÂÎÔÛÇ][\wÀ-ÿ'’-]*\s*){1,5})\s*$"
)

PROPOSER_RE = re.compile(
    r"Sur\s+(?:la\s+)?proposition\s+(?P<who>d[eu][^,;.]{3,200})", re.I
)


@dataclass
class Act:
    """One administrative act as published."""

    issue_key: str
    year: int
    issue: str
    page: int
    seq: int
    kind: str                       # decret | arrete | decision | loi
    qualifier: str = ""             # presidentiel | gouvernemental | loi | ""
    number: str = ""                # e.g. "2011-1095"
    act_date: dt.date | None = None
    authority_raw: str = ""         # ministry heading the act sits under
    section_raw: str = ""           # NOMINATIONS / CESSATION DE FONCTIONS ...
    issuer_raw: str = ""            # "du ministre des finances"
    title: str = ""
    text: str = ""
    signatory_office: str = ""
    signatory_name: str = ""
    proposer_raw: str = ""


# --------------------------------------------------------------------------
# Person clauses
# --------------------------------------------------------------------------

HONORIFICS = (
    r"Monsieur|Madame|Mademoiselle|M\.|MM\.|Mme|Mmes|Mlle|Melle|Mlles|"
    # "Maitre de conferences" / "Maitre assistant" are academic ranks, not titles.
    r"Docteur|Dr\.?|Professeur|Pr\.?|"
    r"Ma[îi]tre(?!(?i:\s+(?:de\s+conf[ée]rences|assistant|de\s+recherche|d')))|Me\b|"
    r"G[ée]n[ée]ral|Colonel|Lieutenant[- ]colonel|Commandant|Capitaine|"
    r"Amiral|Cheikh|Hadj"
)

# A Tunisian/French personal name as printed: capitalised tokens, plus the
# lowercase particles that are part of the name ("ben", "el", "ould", "abd").
_NAME_TOKEN = r"[A-ZÉÈÊËÀÂÄÎÏÔÖÛÜÇ][\wÀ-ÿ'’.-]*"
# The trailing lookahead matters: without it "es" matches inside "est", and a
# name silently swallows the verb that governs it.
_PARTICLE = (
    r"(?:ben|bel|bin|bou|abou|abd|el|al|ez|es|ech|de|du|des|la|le)(?![\w'’-])"
)
NAME = rf"(?:{_NAME_TOKEN}|{_PARTICLE})(?:[\s-]+(?:{_NAME_TOKEN}|{_PARTICLE})){{0,6}}"

PERSON_RE = re.compile(
    rf"(?P<honorific>{HONORIFICS})\s+(?P<name>{NAME})", re.UNICODE
)

# Operative verbs, grouped by the transition they encode.
APPOINT_VERBS = (
    r"est\s+nomm[ée]e?s?|sont\s+nomm[ée]e?s?|"
    r"est\s+charg[ée]e?s?\s+des\s+fonctions|sont\s+charg[ée]e?s?\s+des\s+fonctions|"
    r"est\s+charg[ée]e?s?\s+de\s+la\s+gestion|"
    r"est\s+d[ée]sign[ée]e?s?|sont\s+d[ée]sign[ée]e?s?|"
    r"est\s+appel[ée]e?s?\s+(?:aux?|[àa]\s+exercer\s+les)\s+fonctions|"
    r"est\s+promue?s?\s+(?:aux?|[àa]\s+l'emploi)"
)
# A transfer keeps the office and changes the posting ("Messieurs les delegues
# ci-apres cites sont mutes en leurs memes fonctions").
TRANSFER_VERBS = (
    r"est\s+mut[ée]e?s?|sont\s+mut[ée]e?s?|"
    r"est\s+affect[ée]e?s?|sont\s+affect[ée]e?s?|"
    r"est\s+d[ée]tach[ée]e?s?|sont\s+d[ée]tach[ée]e?s?|"
    r"est\s+r[ée]int[ée]gr[ée]e?s?"
)
RENEW_VERBS = (
    r"est\s+reconduite?s?|sont\s+reconduits?|"
    r"est\s+maintenue?s?\s+(?:dans|en)\s+(?:ses|sa)\s+fonction"
)
END_VERBS = (
    r"[Ii]l\s+est\s+mis\s+fin\s+(?:aux?\s+fonctions?|[àa]\s+la\s+nomination|[àa]\s+la\s+d[ée]signation|au\s+d[ée]tachement)|"
    r"est\s+d[ée]charg[ée]e?s?\s+de\s+ses\s+fonctions|"
    r"est\s+relev[ée]e?s?\s+de\s+ses\s+fonctions|"
    r"sont\s+d[ée]charg[ée]e?s?\s+de\s+leurs\s+fonctions"
)
RETIRE_VERBS = (
    r"est\s+admis[e]?s?\s+[àa]\s+faire\s+valoir\s+ses\s+droits\s+[àa]\s+la\s+retraite|"
    r"est\s+admis[e]?s?\s+[àa]\s+la\s+retraite|"
    r"est\s+mis[e]?s?\s+[àa]\s+la\s+retraite"
)
RESIGN_VERBS = r"la\s+d[ée]mission\s+de|est\s+accept[ée]e\s+la\s+d[ée]mission"
# Delegation of signature: a directed tie from a principal (the signatory) to
# an agent, and one of the few relational acts the gazette states explicitly.
DELEGATION_VERBS = (
    r"d[ée]l[ée]gation\s+(?:de\s+signature\s+)?est\s+(?:donn[ée]e?|accord[ée]e?)\s+[àa]|"
    r"est\s+habilit[ée]e?s?\s+[àa]\s+signer|"
    r"re[çc]oit\s+d[ée]l[ée]gation\s+de\s+signature"
)

REPLACES_RE = re.compile(
    rf"en\s+remplacement\s+d[eu]\s*(?:{HONORIFICS})?\s*(?P<name>{NAME})", re.I
)
SUCCEEDS_RE = re.compile(
    rf"en\s+(?:son\s+)?remplacement|"
    rf"succ[èe]de\s+[àa]\s*(?:{HONORIFICS})?\s*(?P<name>{NAME})",
    re.I,
)

BOARD_RE = re.compile(
    r"\b(?P<seat>administrateur(?:s)?(?:\s+repr[ée]sentant\s+l'[ÉEe]tat)?|"
    r"membres?|pr[ée]sident(?:e)?|vice[- ]pr[ée]sident(?:e)?|rapporteur)\s+"
    r"(?:repr[ée]sentant[^,]{0,60}\s+)?"
    r"(?:au|du|dans\s+le|de)\s+(?P<body>conseil\s+d(?:'administration|e\s+surveillance|'[ée]tablissement|'entreprise)|"
    r"comit[ée]\s+[^,.;]{0,60}|commission\s+[^,.;]{0,60})"
    r"\s*(?:de\s+la|de\s+l'|du|des|de)?\s*(?P<org>[^,.;]{0,140})?",
    re.I,
)

GRADE_RE = re.compile(
    r"^[\s,(]*(?P<grade>[^,.()]{3,90})[)\s,]*$"
)

# Text that trails a position and should be cut off it.
_POSITION_STOP = re.compile(
    r"\s*(?:,\s*)?(?:et\s+ce\b|[àa]\s+compter\s+d|en\s+remplacement\s+d|"
    r"avec\s+effet\b|[àa]\s+partir\s+d|pour\s+une\s+p[ée]riode\b|"
    r"en\s+sus\s+de\b|et\s+b[ée]n[ée]ficie\b|conform[ée]ment\b|"
    r"tout\s+en\s+conservant\b|il\s+b[ée]n[ée]ficie\b|dans\s+cette\s+position\b|"
    r"avec\s+(?:le\s+)?(?:b[ée]n[ée]fice|rang\s+et\s+pr[ée]rogatives?|les\s+"
    r"indemnit[ée]s|maintien)\b|et\s+lui\s+sont\s+accord[ée]s\b|"
    r"tout\s+en\s+b[ée]n[ée]ficiant\b|[àa]\s+ce\s+titre\b|"
    r"pour\s+une\s+dur[ée]e\b|au\s+titre\s+de\s+l'ann[ée]e\b|"
    r"[àa]\s+l'effet\s+de\b|au\s+nom\s+d[eu]\b|[àa]\s+l'exclusion\s+de\b|"
    r"\(\s*sce\b|,\s*et\s+lui\b|Vu\s+(?:la|le|l'|les)\s)",
    re.I,
)

_LEADING_ARTICLE = re.compile(
    r"^(?:un|une|des|le|la|les|l'|au|aux|d'|de|du)\s+(?=\w)", re.I
)

# --- preamble vs. operative part -------------------------------------------
#
# A long-form decree opens with recitals ("Nous, ... ; Vu la loi ...; Vu le
# decret ... chargeant M. X des fonctions de ...") before "Decrete :".  Those
# recitals restate *earlier* appointments and must not be mistaken for the act
# itself — but they are dated, citable evidence of those earlier appointments,
# so we harvest them separately.

DISPOSITIF_RE = re.compile(
    r"\b(?:D[ée]cr[èe]t(?:e|ons|ent)|Arr[êe]t(?:e|ons|ent)|D[ée]cid(?:e|ons|ent))\s*:",
    re.I,
)

VU_CLAUSE_RE = re.compile(
    r"Vu\s+(?:le|la|l'|les)\s*"
    r"(?P<kind>d[ée]cret|arr[êe]t[ée]|d[ée]cision)"
    r"(?P<qualifier>\s+(?:[Pp]r[ée]sidentiel|[Gg]ouvernemental|-?\s*loi))?"
    r"[^,\n]{0,60}?(?:n\s*[°ᵒo]?\s*(?P<number>[\d]{2,4}\s*-\s*[\d]{1,5}))?"
    r"\s*,?\s*du\s+(?P<date>[^,;]{4,40})\s*,?\s*"
    r"(?P<verb>chargeant|nommant|portant\s+nomination\s+d[eu]|"
    r"portant\s+cessation\s+de\s+fonctions?\s+d[eu]|"
    r"d[ée]chargeant|mettant\s+fin\s+aux\s+fonctions\s+d[eu])"
    r"\s*(?P<rest>.{0,400}?)"
    r"(?=,\s*Vu\s|\bArr[êe]te\s*:|\bD[ée]cr[èe]te\s*:|\bD[ée]cide\s*:|$)",
    re.I | re.S,
)


def split_preamble(text: str) -> tuple[str, str]:
    """Return (recital preamble, operative part) for an act."""
    m = DISPOSITIF_RE.search(text)
    if m:
        return text[: m.start()], text[m.end():]
    # Short-form personnel acts ("Par decret n° ... :") have no preamble.
    if re.search(r"\bVu\s+(?:la|le|l'|les)\s", text) and re.match(
        r"^\s*(?:D[ée]cret|Arr[êe]t[ée]|D[ée]cision|Loi)\b", text
    ):
        return text, ""
    return "", text


@dataclass
class Event:
    """One person-office transition extracted from an act."""

    # provenance
    issue_key: str
    year: int
    issue: str
    page: int
    act_seq: int
    act_kind: str
    act_qualifier: str
    act_number: str
    act_date: dt.date | None
    authority_raw: str
    section_raw: str
    signatory_office: str
    signatory_name: str
    proposer_raw: str
    pdf_url: str
    # event
    event_type: str                  # appointment | termination | board | renewal | retirement | resignation
    person_raw: str
    honorific: str
    source_layer: str = "dispositif"  # dispositif | title | recital | list
    cited_act_number: str = ""        # for recitals: the act being cited
    cited_act_date: dt.date | None = None
    grade_raw: str = ""
    position_raw: str = ""
    org_raw: str = ""
    board_body_raw: str = ""
    replaces_raw: str = ""
    delegator_raw: str = ""           # principal named by a signature delegation
    effect_date: dt.date | None = None
    sentence: str = ""

    def as_row(self) -> dict:
        row = asdict(self)
        for k in ("act_date", "effect_date", "cited_act_date"):
            row[k] = row[k].isoformat() if row[k] else ""
        return row


# --------------------------------------------------------------------------


def _clean_position(s: str) -> str:
    s = s.strip(" ,;:.-—")
    m = _POSITION_STOP.search(s)
    if m:
        s = s[: m.start()]
    return re.sub(r"\s+", " ", s).strip(" ,;:.-—")


def _split_position_org(s: str) -> tuple[str, str]:
    """Split 'directeur des affaires administratives au ministere de la sante'."""
    s = _clean_position(s)
    m = re.search(
        r"\s+(?:au|aux|à\s+la|a\s+la|à\s+l'|a\s+l'|de\s+la|du|de\s+l'|des|de|"
        r"auprès\s+d[eu]\s*l?'?|pour\s+le|chez)\s+"
        r"((?:l'|la\s+|le\s+|les\s+)?(?:minist[èe]re|pr[ée]sidence|secr[ée]tariat|"
        r"office|agence|soci[ée]t[ée]|banque|caisse|centre|institut|[ée]cole|"
        r"universit[ée]|h[ôo]pital|commissariat|direction\s+g[ée]n[ée]rale|"
        r"[ée]tablissement|entreprise|conseil|instance|autorit[ée]|"
        r"gouvernorat|commune|r[ée]gie|fonds|comit[ée]|tribunal|cour)\b.*)$",
        s,
        re.I,
    )
    if m:
        return _clean_position(s[: m.start()]), _clean_position(m.group(1))
    return s, ""


def _signatory(blocks: list[str]) -> tuple[str, str]:
    """Read the signature block at the foot of a long-form act."""
    for text in reversed(blocks[-6:]):
        m = SIGNATORY_RE.search(text.strip())
        if m:
            name = re.sub(r"\s+", " ", m.group("name")).strip(" .,")
            if 2 <= len(name) <= 60 and not re.match(r"^(de|du|des|la|le)\b", name, re.I):
                return m.group("office").strip(), name
    return "", ""


def _match_act_header(text: str) -> dict | None:
    m = PAR_ACT_RE.match(text)
    if m:
        d = m.groupdict()
        d["form"] = "par"
        return d
    m = TITLED_ACT_RE.match(text)
    if m:
        d = m.groupdict()
        d["form"] = "titled"
        d.setdefault("issuer", "")
        return d
    m = UPPER_ACT_RE.match(text)
    if m and text[:6].isupper():
        d = m.groupdict()
        d["form"] = "upper"
        d.setdefault("number", "")
        d.setdefault("qualifier", "")
        d.setdefault("issuer", "")
        d.setdefault("title", "")
        return d
    return None


def _norm_kind(kind: str) -> str:
    k = kind.lower()
    if k.startswith("d") and "cret" in k:
        return "decret"
    if k.startswith("arr"):
        return "arrete"
    if k.startswith("d") and "cision" in k:
        return "decision"
    return "loi"


def _norm_qualifier(q: str | None) -> str:
    if not q:
        return ""
    q = q.strip().lower().replace("-", "").replace(" ", "")
    if q.startswith("pr"):
        return "presidentiel"
    if q.startswith("gouvernement"):
        return "gouvernemental"
    if "loi" in q:
        return "loi"
    return ""


def iter_acts(raw: str, *, issue_key: str, year: int, issue: str) -> Iterator[Act]:
    """Split one issue's OCR markdown into administrative acts."""
    blocks = to_blocks(raw)
    if not blocks:
        return
    start = body_start(blocks)
    body = blocks[start:]

    authority = ""
    section = ""
    current: Act | None = None
    buf: list[str] = []
    seq = 0

    def finish(act: Act | None, chunks: list[str]) -> Act | None:
        if act is None:
            return None
        act.text = " ".join(chunks).strip()
        act.signatory_office, act.signatory_name = _signatory(chunks)
        pm = PROPOSER_RE.search(act.text)
        if pm:
            act.proposer_raw = re.sub(r"\s+", " ", pm.group("who")).strip(" .,;")
        return act

    for blk in body:
        if blk.is_heading:
            if AUTHORITY_HEADING.match(blk.text):
                done = finish(current, buf)
                if done:
                    yield done
                current, buf = None, []
                authority = blk.text.strip()
                section = ""
                continue
            if SECTION_HEADING.match(blk.text):
                done = finish(current, buf)
                if done:
                    yield done
                current, buf = None, []
                section = blk.text.strip()
                continue
            # Unrecognised heading: treat as a soft boundary but keep context.
            done = finish(current, buf)
            if done:
                yield done
            current, buf = None, []
            # A heading may itself be an act header (common in the 1970s).
            hdr = _match_act_header(blk.text)
            if not hdr:
                continue
        else:
            hdr = _match_act_header(blk.text)

        if hdr:
            done = finish(current, buf)
            if done:
                yield done
            seq += 1
            number = (hdr.get("number") or "").replace(" ", "").replace("–", "-")
            current = Act(
                issue_key=issue_key,
                year=year,
                issue=issue,
                page=blk.page,
                seq=seq,
                kind=_norm_kind(hdr["kind"]),
                qualifier=_norm_qualifier(hdr.get("qualifier")),
                number=number,
                act_date=parse_date(hdr.get("date") or ""),
                authority_raw=authority,
                section_raw=section,
                issuer_raw=re.sub(r"\s+", " ", (hdr.get("issuer") or "")).strip(" .,"),
                title=re.sub(r"\s+", " ", (hdr.get("title") or "")).strip(),
            )
            buf = [blk.text]
        elif current is not None:
            buf.append(blk.text)

    done = finish(current, buf)
    if done:
        yield done



# --------------------------------------------------------------------------
# Event extraction inside an act
# --------------------------------------------------------------------------

_VERB_TABLE = [
    ("delegation", re.compile(DELEGATION_VERBS, re.I)),
    ("termination", re.compile(END_VERBS, re.I)),
    ("retirement", re.compile(RETIRE_VERBS, re.I)),
    ("renewal", re.compile(RENEW_VERBS, re.I)),
    ("transfer", re.compile(TRANSFER_VERBS, re.I)),
    ("appointment", re.compile(APPOINT_VERBS, re.I)),
]

# Sentence boundaries.  A colon counts: the gazette introduces enumerated
# appointment lists with "Sont nommes ... :" followed by one entry per line.
_SENT_SPLIT = re.compile(
    r"(?<=[.;:])\s+(?=[A-ZÉÈÀÂÎÔÛÇ«\-])|(?<=\.)\s*(?=- )"
)

# A list header: an operative verb whose subjects are enumerated below it,
# e.g. "Sont nommes Cheikhs a compter des dates suivantes :" / "Sont nommes
# membres du conseil d'administration de la STEG :".
_LIST_HEADER = re.compile(r":\s*$")
_LIST_ROSTER = re.compile(
    r"^\s*(Messieurs|Mesdames|Mesdemoiselles|MM\.|Mmes)\s*:?\s*$", re.I
)
# Item lead-in of a list entry that carries no honorific.
_BARE_NAME = re.compile(rf"^\s*[-–•*]?\s*(?P<name>{NAME})\s*(?=[,:.]|\s+(?:au|aux|[àa]|en|de|du|des)\s)")

# Titles of long-form personnel decrees.
_TITLE_ACTION = re.compile(
    r"portant\s+(?P<what>nomination|cessation\s+de\s+fonctions?|d[ée]charge|"
    r"mise\s+[àa]\s+la\s+retraite|renouvellement|d[ée]signation)\b",
    re.I,
)

_TITLE_KIND = {
    "nomination": "appointment",
    "designation": "appointment",
    "décharge": "termination",
    "decharge": "termination",
    "renouvellement": "renewal",
}


def _sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENT_SPLIT.split(text) if p and p.strip()]
    return parts or ([text] if text.strip() else [])


def _grade_from(prefix: str) -> str:
    """The apposition between a name and its verb: ', administrateur general,'."""
    g = prefix.strip(" ,;()")
    if not g or len(g) > 120:
        return ""
    if re.match(r"^(est|sont|et|qui|de|du|des|la|le|il|elle)\b", g, re.I):
        return ""
    return re.sub(r"\s+", " ", g)


def _office(complement: str) -> tuple[str, str, str]:
    """Return (position, organisation, board_body) for a verb complement."""
    c = complement.strip(" ,;:")
    c = re.sub(
        r"^(?:de\s+|des\s+|du\s+|d'|en\s+qualit[ée]\s+de\s+|au\s+poste\s+de\s+|"
        r"aux?\s+fonctions?\s+de\s+|[àa]\s+l'emploi\s+de\s+|[àa]\s+la\s+fonction\s+de\s+|"
        r"dans\s+le\s+grade\s+de\s+|pour\s+exercer\s+les\s+fonctions\s+de\s+)",
        "",
        c,
        flags=re.I,
    )
    board = BOARD_RE.search(c)
    if board:
        body = re.sub(r"\s+", " ", board.group("body")).strip()
        org = _clean_position(board.group("org") or "")
        seat = _LEADING_ARTICLE.sub("", re.sub(r"\s+", " ", board.group("seat")).strip())
        return seat, org, body
    pos, org = _split_position_org(c)
    pos = _LEADING_ARTICLE.sub("", pos)
    # "... pour representer l'Etat au conseil d'administration de X" lands the
    # collegial body in the organisation slot; recover it as a board seat.
    m = re.match(
        r"^(?:l')?(conseil\s+d(?:'administration|e\s+surveillance|'[ée]tablissement)|"
        r"comit[ée]\s+\w+|commission\s+\w+)\s+(?:de\s+la\s+|de\s+l'|du\s+|des\s+|de\s+)?(?P<rest>.*)$",
        org,
        re.I,
    )
    if m:
        return pos, _clean_position(m.group("rest")), re.sub(r"\s+", " ", m.group(1)).strip()
    return pos, org, ""


DELEGATOR_RE = re.compile(
    r"(?:par\s+d[ée]l[ée]gation\s+d[eu]|au\s+nom\s+d[eu])\s*(?P<who>l[ae]\s+)?"
    r"(?P<name>(?:ministre|secr[ée]taire\s+d'[ÉEe]tat|chef(?:fe)?\s+du\s+gouvernement|"
    r"premier\s+ministre|pr[ée]sident(?:e)?|gouverneur|directeur\s+g[ée]n[ée]ral|"
    r"maire)[^,.;]{0,80})",
    re.I,
)


def _mk_event(act, pdf_url, kind, person, honorific, grade, position, org, board,
              sentence, *, layer="dispositif", cited_number="", cited_date=None,
              effect=None) -> Event:
    repl = REPLACES_RE.search(sentence)
    delegator = ""
    if kind == "delegation":
        dm = DELEGATOR_RE.search(sentence)
        if dm:
            delegator = re.sub(r"\s+", " ", dm.group("name")).strip(" .,;")
        # For a delegation the complement describes the delegated scope, not an
        # office; keep the office only when it reads like one.
        if re.match(r"^\s*(?:par\s+d[ée]l[ée]gation|tous?\s+les|les\s+|des\s+)", position, re.I):
            position = ""
    return Event(
        issue_key=act.issue_key,
        year=act.year,
        issue=act.issue,
        page=act.page,
        act_seq=act.seq,
        act_kind=act.kind,
        act_qualifier=act.qualifier,
        act_number=act.number,
        act_date=act.act_date,
        authority_raw=act.authority_raw,
        section_raw=act.section_raw,
        signatory_office=act.signatory_office,
        signatory_name=act.signatory_name,
        proposer_raw=act.proposer_raw,
        pdf_url=pdf_url,
        event_type="board" if board else kind,
        person_raw=trim_name(re.sub(r"\s+", " ", person)),
        honorific=honorific.strip(),
        source_layer=layer,
        cited_act_number=cited_number,
        cited_act_date=cited_date,
        grade_raw=grade,
        position_raw=position,
        org_raw=org,
        board_body_raw=board,
        replaces_raw=trim_name(re.sub(r"\s+", " ", repl.group("name"))) if repl else "",
        delegator_raw=delegator,
        effect_date=effect or effective_date(sentence) or act.act_date,
        sentence=sentence[:600],
    )


def _from_title(act: Act, pdf_url: str, sentence: str) -> list[Event]:
    """Read a long-form decree whose personnel action sits in its title."""
    tm = _TITLE_ACTION.search(sentence)
    if not tm:
        return []
    what = tm.group("what").lower()
    kind = _TITLE_KIND.get(what)
    if kind is None:
        kind = ("termination" if "cessation" in what
                else "retirement" if "retraite" in what else "appointment")
    tail = sentence[tm.end():]
    pm = PERSON_RE.search(tail)
    if not pm:
        return []
    rest = tail[pm.end():]
    rest = re.sub(
        r"^\s*,?\s*(?:en\s+qualit[ée]\s+de|au\s+poste\s+de|aux?\s+fonctions?\s+de|"
        r"en\s+tant\s+que|comme)\s*",
        "",
        rest,
        flags=re.I,
    )
    pos, org, board = _office(rest)
    return [
        _mk_event(act, pdf_url, kind, pm.group("name"), pm.group("honorific"),
                  "", pos, org, board, sentence, layer="title")
    ]


def _from_recitals(act: Act, pdf_url: str, preamble: str) -> list[Event]:
    """Harvest the 'Vu le decret ... chargeant M. X des fonctions de Y' clauses.

    These restate appointments made by *earlier* acts.  They are dated and
    numbered, so they are usable evidence in their own right — especially for
    filling gaps where the original issue is missing or unOCR'd — but they are
    tagged ``source_layer='recital'`` so an analyst can exclude them.
    """
    out: list[Event] = []
    for m in VU_CLAUSE_RE.finditer(preamble):
        rest = m.group("rest")
        pm = PERSON_RE.search(rest)
        if not pm:
            continue
        verb = m.group("verb").lower()
        kind = ("termination" if ("cessation" in verb or "fin" in verb or "décharge" in verb
                                  or "decharge" in verb) else "appointment")
        tail = rest[pm.end():]
        tail = re.sub(
            r"^\s*,?\s*(?:[^,]{0,60}?,\s*)?(?:des\s+fonctions\s+de|"
            r"en\s+qualit[ée]\s+de|aux?\s+fonctions?\s+de)\s*",
            "",
            tail,
            flags=re.I,
        )
        grade_m = re.match(r"^\s*,\s*([^,]{3,60}?)\s*,\s*(?:des\s+fonctions|en\s+qualit)", rest[pm.end():], re.I)
        pos, org, board = _office(tail)
        cited_date = parse_date(m.group("date") or "")
        out.append(
            _mk_event(
                act, pdf_url, kind, pm.group("name"), pm.group("honorific"),
                grade_m.group(1) if grade_m else "", pos, org, board,
                m.group(0)[:600], layer="recital",
                cited_number=(m.group("number") or "").replace(" ", ""),
                cited_date=cited_date, effect=cited_date,
            )
        )
    return out


def _from_sentence(act: Act, pdf_url: str, sentence: str) -> list[Event]:
    """Ordinary operative sentence: persons matched to the verb governing them."""
    verb_hits = [(k, m) for k, pat in _VERB_TABLE for m in pat.finditer(sentence)]
    if not verb_hits:
        return []
    verb_hits.sort(key=lambda kv: kv[1].start())
    persons = list(PERSON_RE.finditer(sentence))
    if not persons:
        return []

    out: list[Event] = []
    for idx, pm in enumerate(persons):
        nxt = persons[idx + 1].start() if idx + 1 < len(persons) else len(sentence)
        following = [(k, m) for k, m in verb_hits if pm.end() <= m.start() < nxt]
        if following:
            kind, vm = following[0]
            grade = _grade_from(sentence[pm.end(): vm.start()])
            complement = sentence[vm.end(): nxt]
        else:
            # "Il est mis fin aux fonctions de M. X en qualite de ..." puts the
            # verb ahead of its object.
            preceding = [(k, m) for k, m in verb_hits if m.end() <= pm.start()]
            if not preceding:
                continue
            kind, vm = preceding[-1]
            if pm.start() - vm.end() > 40:
                continue
            grade = ""
            complement = sentence[pm.end(): nxt]
        pos, org, board = _office(complement)
        out.append(
            _mk_event(act, pdf_url, kind, pm.group("name"), pm.group("honorific"),
                      grade, pos, org, board, sentence)
        )
    return out


def _list_context(sentence: str) -> tuple[str, str, str, str] | None:
    """If ``sentence`` heads an enumerated appointment list, return its office."""
    if not _LIST_HEADER.search(sentence) or PERSON_RE.search(sentence):
        return None
    hits = [(k, m) for k, pat in _VERB_TABLE for m in pat.finditer(sentence)]
    if not hits:
        return None
    hits.sort(key=lambda kv: kv[1].start())
    kind, vm = hits[0]
    pos, org, board = _office(sentence[vm.end():].rstrip(" :"))
    return kind, pos, org, board


def extract_events(act: Act, pdf_url: str) -> list[Event]:
    """Emit one Event per person-office transition described by ``act``."""
    if not act.text:
        return []

    preamble, operative = split_preamble(act.text)
    events: list[Event] = _from_recitals(act, pdf_url, preamble) if preamble else []

    pending: tuple[str, str, str, str] | None = None
    for sentence in _sentences(operative):
        if len(sentence) > 1500:
            sentence = sentence[:1500]

        found = _from_sentence(act, pdf_url, sentence)
        if found:
            events.extend(found)
            pending = None
            continue

        ctx = _list_context(sentence)
        if ctx is not None:
            pending = ctx
            continue

        if _LIST_ROSTER.match(sentence):
            continue

        if pending is not None:
            kind, pos, org, board = pending
            pm = PERSON_RE.search(sentence)
            if pm and pm.start() <= 3:
                name, honorific = pm.group("name"), pm.group("honorific")
                tail = sentence[pm.end():]
            else:
                bm = _BARE_NAME.match(sentence)
                if not bm:
                    pending = None
                    continue
                name, honorific = bm.group("name"), ""
                tail = sentence[bm.end():]
            item_pos, item_org, item_board = _office(tail)
            events.append(
                _mk_event(act, pdf_url, kind, name, honorific, "",
                          pos or item_pos, item_org or org, board or item_board,
                          sentence, layer="list")
            )
            continue

        # Long-form decree stating the action in its title.
        if act.title or _TITLE_ACTION.search(sentence):
            events.extend(_from_title(act, pdf_url, sentence))

    return _dedupe(events)


_PARTICLE_ONLY = re.compile(rf"^(?:{_PARTICLE})(?:[\s-]+(?:{_PARTICLE}))*$", re.I)
# A name may not end on a particle: "chargeant Monsieur Ali Larayedh de former
# un gouvernement" otherwise yields the name "Ali Larayedh de".
_TRAILING_PARTICLE = re.compile(rf"(?:[\s-]+(?:{_PARTICLE}))+$", re.I)


def trim_name(name: str) -> str:
    return _TRAILING_PARTICLE.sub("", name.strip(" .,;-")).strip(" .,;-")
_HAS_REAL_TOKEN = re.compile(r"[A-ZÉÈÊËÀÂÄÎÏÔÖÛÜÇ][\wÀ-ÿ'’-]{1,}")


# Words that are offices or roles, never given names.  "Monsieur le Président
# de la République" and "Maitre de Conferences" otherwise enter the person
# register and accumulate a career.
_NOT_A_NAME = {
    "president", "presidente", "ministre", "ministres", "secretaire",
    "directeur", "directrice", "gouverneur", "representant", "representante",
    "conferences", "chef", "cheffe", "conseiller", "conseillere", "delegue",
    "administrateur", "membre", "membres", "inspecteur", "controleur",
    "premier", "premiere", "gouvernement", "republique", "etat", "ministere",
    "monsieur", "madame", "mademoiselle", "docteur", "professeur", "maitre",
    "interesse", "interessee", "nomme", "nommee", "charge", "chargee",
}


def is_person_name(name: str) -> bool:
    """Reject OCR debris, office titles and stray particles picked up as names."""
    n = name.strip(" .,;-")
    if len(n) < 4 or len(n) > 90:
        return False
    if _PARTICLE_ONLY.match(n):
        return False
    if not _HAS_REAL_TOKEN.search(n):
        return False
    # A lone token is usually a misread; the gazette always prints given name
    # plus patronym.  Allow a single token only if it is long and capitalised.
    # Many Tunisian names legitimately open with a particle ("Ben Salah",
    # "El Materi"), so only a name made *entirely* of particles is rejected.
    tokens = [t for t in re.split(r"[\s-]+", n) if t]
    if len(tokens) == 1 and len(tokens[0]) < 6:
        return False

    import unicodedata

    def fold(t: str) -> str:
        d = unicodedata.normalize("NFD", t.lower())
        return "".join(c for c in d if unicodedata.category(c) != "Mn")

    substantive = [fold(t) for t in tokens
                   if not re.fullmatch(_PARTICLE, t, re.I)]
    if not substantive or all(t in _NOT_A_NAME for t in substantive):
        return False
    return True


def _dedupe(events: list[Event]) -> list[Event]:
    """Collapse duplicates, preferring operative text over recitals."""
    rank = {"dispositif": 0, "list": 0, "title": 1, "recital": 2}
    best: dict[tuple, Event] = {}
    order: list[tuple] = []
    for e in events:
        if not is_person_name(e.person_raw):
            continue
        key = (
            e.person_raw.lower(),
            e.event_type,
            e.position_raw.lower()[:60],
            e.org_raw.lower()[:60],
            e.cited_act_number or e.act_number,
        )
        if key not in best:
            best[key] = e
            order.append(key)
        elif rank.get(e.source_layer, 3) < rank.get(best[key].source_layer, 3):
            best[key] = e
    return [best[k] for k in order]


def events_from_issue(raw: str, *, issue_key: str, year: int, issue: str,
                      pdf_url: str) -> list[Event]:
    """Full pipeline for one issue: skip Arabic scans, segment, extract."""
    if arabic_ratio(raw[:4000]) > 0.15:
        return []
    out: list[Event] = []
    for act in iter_acts(raw, issue_key=issue_key, year=year, issue=issue):
        out.extend(extract_events(act, pdf_url))
    return _dedupe(out)
