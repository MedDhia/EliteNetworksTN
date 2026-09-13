"""Shared French grammar primitives for event extraction.

The gazette's language is highly formulaic, so a rule layer carries most of the
work and -- unlike a statistical tagger -- a reviewer can read the rule that
produced any given record. Every pattern here is keyed by a ``pattern_id`` that
is stamped onto the events it generates.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from functools import lru_cache

from .names import parse_person
from .paths import load_config

# Uppercase and lowercase letter classes covering the accented French range.
U = r"A-ZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÑÒÓÔÕÖØÙÚÛÜÝ"
L = r"a-zà-öø-ÿ"

# The title is matched case-insensitively with a scoped flag: the gazette
# prints "monsieur" in lower case 5,840 times, and those mentions were being
# missed. The flag must NOT extend to the name itself -- NAME relies on
# uppercase initials to find a name at all, and making it case-insensitive
# would let any run of ordinary words look like one.
TITLE = (r"(?i:Monsieur|Madame|Mademoiselle|Messieurs|Mesdames|"
         r"M\.|Mme|Mlle|Mr\.?|Dr\.?|Me\.?|Maître)")
PARTICLE = r"(?:ben|bent|bin|el|al|ould|ouled|abou|abd|abdel|si|sidi|bel|bou|ibn|ebn)"
_TOK = rf"[{U}][{U}{L}'’\.\-]*"
# A role word must not be swallowed into the name: "Mr Ayadi Bouguerba
# Commissaire aux Comptes" was yielding a person called "Ayadi Bouguerba
# Commissaire". Titles of function are excluded from name continuation.
_NOT_NAME = (r"(?!(?i:Commissaire|G[ée]rant|G[ée]rante|G[ée]rants|Administrateur|"
             r"Administrateurs|Pr[ée]sident|Pr[ée]sidente|Directeur|Directrice|"
             r"Liquidateur|Tr[ée]sorier|Secr[ée]taire|Membre|Associ[ée]|"
             r"Actionnaire|Cog[ée]rant|Co)\b)")
NAME = (rf"(?:{_TOK}|{PARTICLE})"
        rf"(?:[ \-]{_NOT_NAME}(?:{_TOK}|{PARTICLE})){{0,4}}")
# Two different relations hide behind one surface shape. "Fatma Trabelsi
# epouse Ben Ali" is a marriage; "Fatma Ben Ali nee Trabelsi" is the same woman
# giving her natal surname. Folding them together -- which the single SPOUSE
# group did -- makes a spousal tie out of a birth name. They are captured
# together, because the grammar is the same, and told apart by the marker.
#
# Bare "EP" without the period is included: it is rare (122 blocks) and
# ambiguous in isolation -- "Raison sociale : EP Technology" is a firm, not a
# marriage -- but harmless here, because the group only ever matches in the
# position immediately after a person name.
SPOUSE_MARKERS = r"[ée]pouse|[ée]p\.|EP\.|EP|veuve|vve"
MAIDEN_MARKERS = r"n[ée]e"
_NAME_LINK = rf"(?P<link>{SPOUSE_MARKERS}|{MAIDEN_MARKERS})"
SPOUSE = rf"(?:\s+{_NAME_LINK}\s+(?P<spouse>{NAME}))?"

# Which relation a captured marker states. Returns "" for anything else so a
# caller can treat an unrecognised marker as no claim rather than as a marriage.
_SPOUSE_KIND = {"epouse": "spouse_of", "ep.": "spouse_of", "ep": "spouse_of",
                "veuve": "widow_of", "vve": "widow_of",
                "nee": "maiden_name_of", "ne": "maiden_name_of"}


def name_link_kind(marker: str) -> str:
    """The relation a spousal/maiden marker asserts, or "" if unrecognised."""
    return _SPOUSE_KIND.get(strip_accents(marker or "").strip().lower(), "")


RE_PERSON = re.compile(rf"{TITLE}\s+(?P<name>{NAME}){SPOUSE}", re.UNICODE)

# The same pair without requiring a title in front. Two thirds of the corpus's
# spousal markers sit in prose that never titles the woman -- "la nommee Fekria
# Bent Mohamed Osman epouse Ben Salem", "sa mere M'na Bent M'barek Ben Guiza
# veuve Najar Ben Ali Khai" -- so a title-anchored pattern sees 984 of them
# against 41,088 in the text. Precision is carried by `clean_name`, which
# rejects both single tokens and boilerplate: it discards 35,123 of the 41,088
# raw captures ("Son epouse Khadija" among them) and leaves 5,965 where both
# ends are full multi-token names.
RE_NAME_LINK = re.compile(
    rf"(?P<name>{NAME})\s+{_NAME_LINK}\s+(?P<spouse>{NAME})", re.UNICODE)

# Without a title anchor to consume it, a leading "Mme"/"Mr" lands inside the
# name capture, and "Mme Sihem Temimi" then resolves as a different person from
# "Sihem Temimi". NAME_STOPWORDS catches the spelt-out forms but not the
# abbreviations, which is what the gazette almost always uses.
_RE_LEAD_TITLE = re.compile(rf"^{TITLE}\s+")

# Words that follow a title in boilerplate but are not names. Without this the
# label "M." in "M. Siege social" and similar produce spurious people.
NAME_STOPWORDS = {
    "SIEGE", "CAPITAL", "DENOMINATION", "OBJET", "DUREE", "FISC", "F", "GERANCE",
    "ADRESSE", "RAISON", "FORME", "SOCIETE", "STE", "EXERCICE", "ASSEMBLEE",
    "CONSEIL", "ADMINISTRATION", "TUNIS", "MATRICULE", "NOMBRE", "VALEUR",
    "AFFECTATION", "DEPOT", "DELAI", "MODALITE", "CONDITIONS", "PROJET",
    "TRIBUNAL", "GREFFE", "RECETTE", "QUITTANCE", "MONSIEUR", "MADAME",
    "ARTICLE", "ART", "NOTA", "REGISTRE", "NATIONAL", "ENTREPRISES",
    # Signature lines: a block often closes with "Le Gerant" or "La Gerance",
    # which is the signatory's function, not a name.
    "LE", "LA", "LES", "GERANT", "GERANTE", "GERANTS", "LIQUIDATEUR",
    "PRESIDENT", "ADMINISTRATEUR", "COMMISSAIRE", "SECRETAIRE", "TRESORIER",
}

# Identity-document labels that trail a name in association filings.
_ID_LABELS = {"CIN", "CNI", "PASSEPORT", "CIF", "MF"}

MONTHS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "decembre": 12,
    # OCR and abbreviation variants
    "janiver": 1, "fervier": 2, "fevier": 2, "avirl": 4, "jullet": 7,
    "juilet": 7, "aoutt": 8, "setpembre": 9, "octbre": 10, "novmbre": 11,
    "decmbre": 12, "janv": 1, "fev": 2, "sept": 9, "oct": 10, "nov": 11,
    "dec": 12,
}
_MONTH_ALT = "|".join(sorted(MONTHS, key=len, reverse=True))

RE_DATE_TXT = re.compile(
    r"\b(?P<d>1er|1ere|0?[1-9]|[12][0-9]|3[01])\s*(?:er|ere)?\s+"
    r"(?P<m>" + _MONTH_ALT + r")\s+(?P<y>19[5-9][0-9]|20[0-4][0-9])\b",
    re.IGNORECASE,
)
RE_DATE_NUM = re.compile(
    r"\b(?P<d>0?[1-9]|[12][0-9]|3[01])\s*[/.]\s*(?P<m>0?[1-9]|1[0-2])\s*[/.]\s*"
    r"(?P<y>19[5-9][0-9]|20[0-4][0-9])\b"
)

# A date as it appears inside a clause. Used wherever a clause anchor is
# followed by "du <date>", so the capture cannot drift onto ordinary prose.
DATE_CORE = (r"(?:(?:1er|1ere|\d{1,2})\s*(?:er|ere)?\s+[A-Za-zÀ-ÿ]{3,12}\s+\d{4}"
             r"|(?:1er|\d{1,2})\s*[/.]\s*\d{1,2}\s*[/.]\s*\d{4})")

# --- dated clause anchors: which of the several dates in a block is which ---
RE_ACT_DATE = re.compile(
    r"(?:suivant|selon|aux?\s+termes?\s+d[eu]|d'apr[èe]s)[^\n]{0,200}?"
    r"en\s+date\s+du\s+(?P<date>" + DATE_CORE + r")", re.IGNORECASE)
RE_ACT_DATE_ALT = re.compile(
    r"(?:P\.?V\.?|proc[èe]s[- ]verbal|acte|statuts?|assembl[ée]e[^\n]{0,40}|"
    r"conseil\s+d'administration)[^\n]{0,120}?"
    r"(?:en\s+date\s+du|du|r[ée]unie?\s+le)\s+(?P<date>" + DATE_CORE + r")", re.IGNORECASE)
RE_REG_DATE = re.compile(
    r"enregistr[ée]s?\s+(?:[àa]\s+la\s+|au\s+)?(?:recette|R\.?E\.?A\.?S)"
    r"[^\n]{0,140}?\s(?:le|en\s+date\s+du)\s+(?P<date>" + DATE_CORE + r")", re.IGNORECASE)
RE_FILING_DATE = re.compile(
    r"d[ée]pos[ée]s?\s+au\s+greffe[^\n]{0,160}?\s(?:le|en\s+date\s+du)\s+"
    r"(?P<date>" + DATE_CORE + r")", re.IGNORECASE)
RE_EFFECTIVE_DATE = re.compile(
    r"(?:prend\s+effet\s+)?[àa]\s+compter\s+du\s+(?P<date>" + DATE_CORE + r")", re.IGNORECASE)

# --- firm identifiers and figures ---
RE_MF = re.compile(
    r"(?:M(?:at)?\.?\s*Fisc\.?|\bMF\b|matricule\s+fiscal)\s*[:.]?\s*"
    r"(?P<mf>\d{6,8}\s*[/\s]?[A-Z]{1,4}(?:\s*[/\s]\s*[A-Z])*(?:\s*[/\s]\s*\d{3})?)",
    re.IGNORECASE)
# The registre-de-commerce number. Two things make the naive pattern useless.
# `R.?C.?` without a leading word boundary matches inside ordinary French --
# exe*rc*ices, ma*rc*he, comme*rc*iales, exclusion -- which inflated a first
# corpus count by 70%. And the value has a shape: an optional bureau letter
# then the sequence and the registration year run together (B133371997 =
# B + 13337 + 1997), so requiring five or more digits rejects the bare years
# that follow "exercices 2003, 2004".
RE_RC = re.compile(
    r"(?:\bR\.?\s?C\.?S?\b|\bregistre\s+d[eu]\s+commerce\b)"
    r"(?:\s*(?:sous\s+le\s+)?(?:n[°ºo]\.?|num[ée]ro\b))?"
    r"\s*[:.]?\s*"
    r"(?P<rc>[A-Z]\s?\d{5,12}|\d{6,12})\b",
    re.IGNORECASE)
RE_CAPITAL = re.compile(
    r"[Aa]u\s+capital\s+(?:social\s+)?(?:de\s+)?(?P<amount>[\d][\d\s.,]{2,20})\s*"
    r"(?P<cur>dinars?|DT|D\b)", re.IGNORECASE)
RE_MANDATE_YEARS = re.compile(
    r"pour\s+une\s+(?:p[ée]riode|dur[ée]e)\s+de\s+(?P<n>un|deux|trois|quatre|cinq|six|\d{1,2})\s+"
    r"(?:ans?|ann[ée]es?|exercices?)", re.IGNORECASE)
RE_MANDATE_EXERCICES = re.compile(
    r"pour\s+(?:une\s+dur[ée]e\s+de\s+)?(?P<n>un|deux|trois|quatre|cinq|six|\d{1,2})\s+"
    r"exercices?\s+sociaux", re.IGNORECASE)

WORD_NUMBERS = {"un": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6}

# --- representation: a legal person acting through a named individual ---
RE_REPRESENTED = re.compile(
    rf"(?P<org>(?:La\s+)?(?:Soci[ée]t[ée]|STE|Ste|SARL|SA)\s+[^,\n]{{2,80}}?)\s+"
    rf"repr[ée]sent[ée]e?\s+par\s+{TITLE}?\s*(?P<name>{NAME})", re.IGNORECASE)

# --- corporate parties: an organisation acting in another firm's filing ---
# The person formulas all require a title (Monsieur, Madame), so a corporate
# party is invisible to them: "la societe X a cede ses parts" matches nothing,
# and of 232,693 share-transfer, capital and constitution events only 13 ever
# captured a company -- those misfiled as persons. These patterns read the
# other side of the register.
#
# ORG_FORM is deliberately broader than names.org_legal_forms, which is used to
# strip a form marker off a name. Here the marker is what identifies the string
# as a company at all, so SICAR/SICAV/SICAF/HOLDING/GROUPE are wanted: in
# Tunisian practice those are the corporate shareholders.
ORG_FORM = (r"(?:soci[eé]t[eé]|ste\.?|sarl|s\.a\.r\.l|suarl|s\.a\b|s\.p\.a"
            r"|sicar|sicav|sicaf|holding|groupe|banque|compagnie|entreprise"
            r"|[eé]tablissements?)")
# A company name as printed: the form marker, then the name, stopping at a
# comma, semicolon, full stop or newline. Quotes are common and are kept for
# _tidy_org to strip.
ORG_NAMED = rf"(?:la\s+|le\s+)?{ORG_FORM}\s*[«\"']?\s*[^,.;:\n]{{2,70}}"

# "la societe X a cede / a vendu ... parts"  -- X is giving shares up.
RE_ORG_CEDES = re.compile(
    rf"(?P<org>{ORG_NAMED}?)\s+a\s+(?:c[eé]d[eé]|vendu)\b", re.IGNORECASE)

# "cede ... au profit de la societe Y" / "cede ... a la societe Y" -- Y acquires.
# `au profit de` is the register's own formula and is tried first because the
# bare preposition also introduces non-parties.
RE_ORG_ACQUIRES = re.compile(
    rf"(?:c[eé]d[eé]|vendu|transf[eé]r[eé])[^.;\n]{{0,80}}?"
    rf"\s+(?:au\s+profit\s+de\s+|[aà]\s+)(?P<org>{ORG_NAMED})", re.IGNORECASE)

# "actionnaires : la societe X" / "associes : la societe X" -- a standing
# holding, confirmed at the filing date rather than opened by it.
RE_ORG_SHAREHOLDER = re.compile(
    rf"(?:actionnaires?|associ[eé]s?)\s*:?[^.;\n]{{0,30}}?(?P<org>{ORG_NAMED})",
    re.IGNORECASE)

# "la societe X a souscrit"
RE_ORG_SUBSCRIBES = re.compile(
    rf"(?P<org>{ORG_NAMED}?)\s+a\s+souscrit\b", re.IGNORECASE)

# "commissaire aux comptes : la societe X" -- an audit firm designated inside
# another firm's filing. This is the relation behind many of the 1,137
# represented_by events.
RE_ORG_AUDITOR = re.compile(
    rf"commissaires?\s+aux\s+comptes?\s*:?[^.;\n]{{0,30}}?(?P<org>{ORG_NAMED})",
    re.IGNORECASE)

# "succursale de la societe X"
RE_ORG_BRANCH = re.compile(
    rf"succursale\s+(?:de\s+|d[eu]\s+)?(?P<org>{ORG_NAMED})", re.IGNORECASE)

# "filiale de la societe X" -- a subsidiary, which is an ownership relation and
# not merely a structural one: the parent holds the subsidiary. Kept separate
# from `branch` because a succursale has no legal personality of its own and so
# cannot be a distinct node, where a filiale can and usually is.
#
# Only the possessive form counts. "creation d'une filiale commerciale" and
# "ouverture d'une filiale" name no parent and no child, so a pattern that did
# not require "de <org>" would emit a tie with one end invented. The
# `du/de la/des` alternation is spelled out rather than folded into ORG_NAMED
# because ORG_NAMED already absorbs a leading article.
RE_ORG_SUBSIDIARY = re.compile(
    rf"filiales?\s+(?:de\s+|du\s+|d[eu]\s+|des\s+)?(?P<org>{ORG_NAMED})",
    re.IGNORECASE)


# In a transfer clause the company whose shares move is named explicitly --
# "de sa participation au capital de la societe Mehari Beach" -- and that, not
# the block's subject line, is the target of the tie. Taking it from here rather
# than from org_name() matters twice over: org_name() resolves on only 55% of
# these blocks and sometimes returns a clause, and in a transfer the subject
# line often names the *seller* instead of the company being sold into.
RE_ORG_TARGET = re.compile(
    rf"(?:au\s+capital\s+d[eu]\s*|dans\s+|parts?\s+sociales?\s+d[eu]\s*"
    rf"|actions\s+d[eu]\s*|participation\s+(?:au\s+capital\s+)?d[eu]\s*)"
    rf"(?P<org>{ORG_NAMED})", re.IGNORECASE)


# The name capture above is permissive by design -- a Tunisian company name can
# run to sixty characters and contain almost anything -- so it is trimmed here
# instead of being constrained in the pattern.
#
# The hard case is " et ". It separates two parties in "la societe SICAR INVEST
# et Monsieur X", and it is part of the name in "la societe Commissariat Audit
# et Organisation". So it only cuts when what follows is plainly another party:
# a person title or a second company.
_ORG_PARTY_STOP = re.compile(
    r"\s+(?:repr[eé]sent[eé]e?s?\s+par"
    r"|aux?\s+profits?\s+d[eu]|au\s+b[eé]n[eé]fice\s+d[eu]"
    r"|a\s+(?:c[eé]d[eé]|vendu|souscrit|acquis)"
    r"|ayant|dont|demeurant|sises?|sis|domicili[eé]e?s?"
    r"|immatricul[eé]e?s?|inscrite?s?|au\s+capital"
    r"|et\s+(?=(?:Monsieur|Madame|Mademoiselle|MM\.|M\.|Mme|Mlle"
    r"|la\s+soci[eé]t[eé]|le\s+groupe|les\s+soci[eé]t[eé]s)))"
    r"\b|\s+et\s+(?=(?:Monsieur|Madame|Mademoiselle|MM\.|M\.|Mme|Mlle))",
    re.IGNORECASE,
)


def trim_org_party(raw: str) -> str:
    """Cut a captured corporate-party name at the first clause boundary."""
    s = (raw or "").strip()
    m = _ORG_PARTY_STOP.search(s)
    if m:
        s = s[:m.start()]
    return s.strip(" .,;:«»\"'-")


# --- headquarters address -------------------------------------------------
# The label is followed by the address in a running clause ("Siege social :
# 2, rue des metiers Z.I. Charguia") and, in the tabular notices, by a line
# break and the address on its own line. Both forms occur in the same issue,
# so the newline is allowed inside the capture.
# The label must name the seat. A bare "adresse" also introduces the
# correspondence address of a liquidator and the address of a court registry
# ("a l'adresse du greffe"), which are not the firm's seat; allowing it raised
# the hit rate from 38% of blocks to 71% and every added capture sampled was
# one of those.
_SIEGE_LABEL = r"(?:adresse\s+d[eu]\s+)?si[èe]ge(?:\s+social)?"
RE_SIEGE = re.compile(
    _SIEGE_LABEL + r"\s*"
    r"(?:est\s+)?(?:sis(?:e)?\s+|situ[ée]e?\s+(?:au?x?\s+)?)?[:,]?\s*"
    # Not the transfer form: "siege social de la societe de X a Y" states two
    # addresses and neither is the standing seat. RE_SIEGE_MOVE reads those.
    r"(?P<addr>(?!de\s+la\s+soci[ée]t[ée]\b)\S[^\n]{3,119}"
    r"(?:\n[^\n]{4,120})?)",
    re.IGNORECASE)

# The transfer form, which states the old seat and the new one in one clause:
# "transfert du siege social de la societe de 1, rue Jobrane Khalil Jobrane
# - Bordj Louzir Ariana a 8, rue Ibn Abi Dhiaf El Menzah V - Ariana".
RE_SIEGE_MOVE = re.compile(
    _SIEGE_LABEL + r"\s*(?:de\s+la\s+soci[ée]t[ée]\s*)?"
    r"(?:sis(?:e)?\s+|situ[ée]e?\s+)?"
    r"(?:de\s+|du\s+|d[eu]\s+l[ae']\s*)"
    r"(?P<from>[^\n]{6,110}?)"
    r"\s+(?:au?\s+|vers\s+|[àa]\s+l[ae']\s*)"
    r"(?P<to>[^\n.]{6,110})",
    re.IGNORECASE)

# An address capture has to be cut, exactly as a corporate-party name does: a
# sampled capture ran from the address straight through the RC number and into
# the next clause ("a Tunis rue Hedi Nouira RC n 14231996, ayant elu domicile
# en l'etude de son avocat"). These are the clause heads that follow an address.
_SIEGE_STOP = re.compile(
    r"\s*(?:\bR\.?\s?C\.?S?\b\s*(?:(?:sous\s+le\s+)?(?:n[°ºo]\.?|num[ée]ro\b))?"
    r"\s*[:.]?\s*[A-Z]?\s?\d{5}"
    r"|\bregistre\s+d[eu]\s+commerce"
    r"|\bmatricule\s+fiscal|\bM(?:at)?\.?\s*Fisc\b"
    r"|\bimmatricul[eé]e?s?\b|\binscrite?s?\s+a[ud]\b"
    r"|\bau\s+capital\b|\brepr[eé]sent[eé]e?s?\s+par\b"
    r"|\bayant\s+[ée]lu\s+domicile\b|\bannonce(?:nt)?\b"
    r"|\bd[ée]cide(?:nt)?\b|\bconform[ée]ment\b"
    # The tabular constitution notice prints one rubric per line, so the
    # label of whichever rubric follows the address ends it.
    r"|\bobjet\s+social\b|\bforme\s+juridique\b|\bd[ée]nomination\b"
    r"|\bdur[ée]e\b|\bg[ée]rance\b|\bcapital\s+social\b"
    r"|\bexercice\s+social\b|\bnombre\s+de\s+parts\b"
    r"|\bassoci[ée]s?\s*:|\bcommissaire\s+aux\s+comptes\b"
    r"|\bobjet\b\s*:|\b\d\s*[)\]]\s*[A-Z]"
    r"|\benregistr[ée]e?s?\b|,?\s+du\s+\d{1,2}\s+\w+\s+(?:19|20)\d\d"
    r"|\bpour\s+d[ée]lib[ée]rer\b|\bordre\s+du\s+jour\b"
    r"|\bfonds\s+de\s+commerce\b|\b[àa]\s+l['’]effet\s+de\b"
    # A person named after the seat -- "..., gerant : Mr Faouzi Neji, avec
    # tous les pouvoirs" -- is the next clause, not part of the address.
    r"|,?\s*\bg[ée]ran(?:t|ce)s?\s*:|,\s*\bM(?:r|me|lle|onsieur|adame)\b"
    r"|\bavec\s+tous\s+les\s+pouvoirs\b|\ba\s+le\s+pouvoir\b)",
    re.IGNORECASE)

# A tabular notice prints "Siege social" as a column header, and the cell
# under it is sometimes the company name rather than the street. A capture
# that opens with a legal form is that header artefact, not an address.
_NOT_AN_ADDRESS = re.compile(
    r"^(?:la\s+)?(?:soci[ée]t[ée]|ste\b|s\.?a\.?r\.?l|s\.?a\b|entreprise"
    r"|groupe|[«\"]"
    # A genuine stated seat does not open with a bare preposition. When it
    # does, the clause is the transfer form ("...de la Z.I Charguia ... au 28,
    # rue Alain Savary"), whose first address is the seat being left, not the
    # standing one. Those belong to RE_SIEGE_MOVE; recording the old address
    # as the current seat would date the move backwards.
    r"|d[eu]\s|d['’]|social\b|transf[ée]r)",
    re.IGNORECASE)

# The transfer preposition, but only where a second address plainly follows:
# a street number or a street type. "a Tunis rue Hedi Nouira" is one address
# and must not be cut; "au 28, rue Alain Savary" is a second one.
_SECOND_ADDRESS = re.compile(
    r"\s+(?:[àa]u?x?|vers)\s+(?=\d|(?:la\s+|le\s+|l['’])?"
    r"(?:rue|avenue|av\.|boulevard|bd\b|impasse|route|zone|z\.?\s?i\b"
    r"|cit[ée]|immeuble|km\b|place|passage|lotissement))",
    re.IGNORECASE)


# A person's stated residence: "demeurant a la plage - Soliman", "domiciliee
# au 12 rue de Rome Tunis". Extracted for the same reason a firm's seat is: an
# address is the only discriminator in the corpus that separates two people who
# share a name, and merged homonyms are the largest remaining error in the
# person layer. It is deliberately *not* an identity claim on its own -- two
# brothers share a house -- which is why it lands in its own column and is
# scored, not matched.
RE_RESIDENCE = re.compile(
    r"\b(?:demeurant(?:e|es|s)?|domicili[ée]e?s?|r[ée]sidant(?:e|es|s)?)\s+"
    r"(?:[àa]u?x?\s+|[àa]\s+|en\s+|de\s+)?"
    # The capture must not run through the *next* party's residence marker.
    # An unconstrained span does, and `finditer` then never reaches the second
    # clause at all -- a notice with two parties yielded one address, and the
    # one it yielded was the two concatenated.
    r"(?P<addr>(?:(?!\bdemeurant|\bdomicili|\br[ée]sidant)[^\n]){6,90})",
    re.IGNORECASE)

# "elisant domicile en l'etude de son avocat" is a procedural election of
# address at a lawyer's office, not where the person lives. Admitting it would
# put every litigant in a case at the same address and make them homonyms of
# each other -- the exact error the residence column exists to fix.
_ELECTED_DOMICILE = re.compile(
    r"^(?:en\s+)?l[ae']?\s*(?:[ée]tude|cabinet)\b|^chez\s+(?:M|Me|Ma[îi]tre)\b",
    re.IGNORECASE)

# What follows a residence in the gazette's sentence order. `_SIEGE_STOP` is
# tuned to what follows a company seat and misses all of these: an identity
# document, an election of address, a further party, or the end of the
# sentence. Left uncut, a capture runs from the street through the CIN number
# and into the next clause, and the address then never matches another
# printing of itself.
_RESIDENCE_STOP = re.compile(
    r"\s*(?:\btitulaire\b|\bporteu(?:r|se)\b|\bC\.?\s?I\.?N\b"
    r"|\bcarte\s+d['’]identit[ée]\b|\bpasseport\b"
    r"|\b[ée]lisant\b|\bayant\s+[ée]lu\b|\brepr[ée]sent[ée]e?\b"
    r"|\bagissant\b|\bn[ée]e?\s+le\b|\bde\s+nationalit[ée]\b"
    r"|\b(?:et|[àa])\s+(?:M|Mr|Me|Mme|Mlle|Monsieur|Madame|Mademoiselle)\b"
    # The sentence resumes with what the party did. These are the verbs the
    # transaction notices actually use, and without them a capture runs from
    # the street through the whole clause and into the next party's address.
    r"|\ba\s+(?:vendu|c[ée]d[ée]|lou[ée]|achet[ée]|donn[ée]|apport[ée]|"
    r"d[ée]clar[ée]|constitu[ée]|nomm[ée])\b"
    r"|\b(?:a\s+vendu|ont\s+vendu|a\s+c[ée]d[ée]|ont\s+c[ée]d[ée])\b"
    r"|\bdemeurant\b|\bdomicili|\br[ée]sidant\b"
    # The object of the sale, where no comma separates it from the address.
    r"|\bla\s+totalit[ée]\b|\btout\s+le\b|\btous\s+les\b|\ble\s+fonds\b"
    r"|\.\s|\.$)",
    re.IGNORECASE)

# A general cut where the enumerated heads run out. An address continues after
# a comma with a place name or a number ("l'avenue Habib Bourguiba, Sidi
# Bouzid", "34 rue de Marseille, 1001 Tunis"); prose continues with a
# lowercase word ("Tunis, la totalite du fonds", "Tunis, gerant"). The
# exception list is the handful of lowercase words that really do open an
# address component. This costs the tail of an address written ", la Marsa",
# which keeps its head and still matches on it.
# The trailing class is deliberately case-sensitive -- a capitalised word after
# a comma is a place name and keeps the address going -- so the exception list
# carries its own inline flag rather than the pattern being IGNORECASE.
_RESIDENCE_TAIL = re.compile(
    r",\s+(?!(?i:rue|avenue|av\.|boulevard|bd|impasse|route|zone|z\.?\s?i"
    r"|cit[ée]|immeuble|imm\.|km|place|passage|lotissement|bloc|appartement"
    # "la" and "le" are deliberately absent: ", la totalite du fonds" is far
    # commoner in these notices than ", la Marsa", and the second keeps its
    # head either way.
    r"|app\.|[ée]tage|villa|r[ée]sidence|el|sidi|borj|bordj"
    r"|a[ïi]n|beb|bab|menzel|hammam|dar)\b)[a-zà-ÿ]",
    re.UNICODE)


def trim_address(raw: str) -> str:
    """Cut a captured address at the first clause boundary after it."""
    s = " ".join((raw or "").split())
    for pat in (_SIEGE_STOP, _SECOND_ADDRESS):
        m = pat.search(s)
        if m:
            s = s[:m.start()]
    s = s.strip(" .,;:«»\"'-")
    return "" if _NOT_AN_ADDRESS.match(s) or len(s) < 4 else s


def trim_residence(raw: str) -> str:
    """Cut a captured residence at the first clause boundary after it.

    `_NOT_AN_ADDRESS`, which `trim_address` applies, rejects a capture opening
    with a bare preposition because for a *seat* that shape means the transfer
    form. A residence has no transfer form, and "demeurant a la Marsa" is
    ordinary, so the leading preposition is consumed by the pattern instead.
    """
    s = " ".join((raw or "").split())
    for pat in (_RESIDENCE_STOP, _RESIDENCE_TAIL):
        m = pat.search(s)
        if m:
            s = s[:m.start()]
    # The capture keeps a leading preposition whenever dropping it would leave
    # the address below the pattern's minimum length ("demeurant a Tunis"), so
    # it is stripped here instead.
    s = re.sub(r"^(?:[àa]u?x?|en|de|d[eu])\s+", "", s, flags=re.IGNORECASE)
    s = trim_address(s)
    return "" if not s or _ELECTED_DOMICILE.match(s) or len(s) < 6 else s


def find_residences(text: str) -> list[tuple[str, str, int]]:
    """(person, residence, offset) for every stated residence in a block.

    Each residence is attributed to the nearest person named before it, which
    is the order the gazette prints: "Madame Hajer Ben Ahmed Sehili epouse Ben
    Mahmoud, demeurant a la plage - Soliman". A residence with no person before
    it in the block belongs to nobody and is dropped -- attributing it to
    whoever comes next would put people at addresses they were never given.
    """
    people = [(m.start(), m.end(), clean_name(_RE_LEAD_TITLE.sub("", m.group("name"))))
              for m in RE_NAME_LINK.finditer(text)]
    people += [(m.start(), m.end(), clean_name(m.group("name")))
               for m in RE_PERSON.finditer(text)]
    people = sorted((s, e, n) for s, e, n in people if n)
    if not people:
        return []
    out: list[tuple[str, str, int]] = []
    for m in RE_RESIDENCE.finditer(text):
        addr = trim_residence(m.group("addr"))
        if not addr:
            continue
        # The nearest person whose mention ends before this clause opens.
        prior = [p for p in people if p[1] <= m.start()]
        if not prior:
            continue
        # A residence more than a sentence away from the name it would attach
        # to is a different party's.
        start, end, name = prior[-1]
        if m.start() - end > 120:
            continue
        out.append((name, addr, m.start()))
    return out


def normalise_address(raw: str) -> str:
    """Fold an address to a comparable key.

    Casing, accents, punctuation and the abbreviation of the street type all
    vary between two printings of the same address, so comparing the raw
    strings would report a move that never happened.
    """
    s = (raw or "").lower()
    for a, b in (("à", "a"), ("â", "a"), ("é", "e"), ("è", "e"), ("ê", "e"),
                 ("î", "i"), ("ï", "i"), ("ô", "o"), ("û", "u"), ("ç", "c")):
        s = s.replace(a, b)
    s = re.sub(r"\bav(?:e?nue)?\b", "avenue", s)
    s = re.sub(r"\b(?:bd|boul(?:evard)?)\b", "boulevard", s)
    s = re.sub(r"\bz\.?\s?i\.?\b", "zi", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


RE_POSTAL = re.compile(r"\b(?P<code>[1-9]\d{3})\b")


def normalise_rc(raw: str) -> str:
    """Reduce a registre-de-commerce number to a comparable stem.

    The bureau letter is sometimes dropped and sometimes lower-cased, and the
    spacing before the digits varies, so only the letter and the digit run
    identify the registration.
    """
    if not raw:
        return ""
    compact = re.sub(r"[^0-9A-Za-z]", "", raw).upper()
    m = re.match(r"([A-Z])?(\d{5,12})$", compact)
    if not m:
        return ""
    return (m.group(1) or "") + m.group(2)


# --- state appointment / departure formulas (journal-officiel) ---
RE_CHARGE = re.compile(
    rf"{TITLE}\s+(?P<name>{NAME}){SPOUSE}\s*(?:,\s*(?P<grade>[^,\n]{{3,90}}))?,?\s+"
    rf"est\s+charg[ée]{{1,2}}s?\s+des\s+fonctions\s+de\s+(?P<role>[^.\n]{{3,220}})",
    re.IGNORECASE)
RE_NOMME = re.compile(
    rf"{TITLE}\s+(?P<name>{NAME}){SPOUSE}\s*(?:,\s*(?P<grade>[^,\n]{{3,90}}))?,?\s+"
    rf"est\s+nomm[ée]{{1,2}}s?\s+(?P<role>[^.\n]{{3,220}})", re.IGNORECASE)
RE_LIST_HEAD = re.compile(
    r"(?:Sont\s+nomm[ée]{1,2}s?|Sont\s+charg[ée]{1,2}s)\s*"
    r"(?:Messieurs|Mesdames(?:\s+et\s+Messieurs)?|Mesdames|Mesdemoiselles)?\s*:?",
    re.IGNORECASE)
RE_LIST_ITEM = re.compile(
    rf"^\s*[-•*]\s*(?P<name>{NAME})\s*:\s*(?P<role>[^\n]{{3,200}}?)\s*[,;.]?\s*$",
    re.MULTILINE)
RE_CESSATION = re.compile(
    rf"(?:il\s+est\s+mis\s+fin\s+aux\s+fonctions\s+de|cessation\s+de(?:s)?\s+fonctions\s+de|"
    rf"est\s+d[ée]charg[ée]{{1,2}}s?\s+de(?:s)?\s+fonctions\s+de)\s*{TITLE}?\s*"
    rf"(?P<name>{NAME})", re.IGNORECASE)
RE_RETIREMENT = re.compile(
    rf"{TITLE}\s+(?P<name>{NAME})[^.\n]{{0,120}}?(?:est\s+)?admis[e]?\s+[àa]\s+"
    rf"(?:faire\s+valoir\s+ses\s+droits\s+[àa]\s+)?la\s+retraite", re.IGNORECASE)

# --- act citations ("Vu le decret ... du ...") ---
RE_VISA = re.compile(
    r"^Vu\s+(?:le|la|l')\s*(?P<kind>d[ée]cret(?:-loi)?(?:\s+Pr[ée]sidentiel|"
    r"\s+gouvernemental)?|arr[êe]t[ée]|loi(?:\s+organique)?|d[ée]cision)"
    r"(?P<rest>[^\n]{0,400})", re.IGNORECASE | re.MULTILINE)
RE_VISA_DATE = re.compile(r"du\s+(?P<date>" + DATE_CORE + r")", re.IGNORECASE)
RE_VISA_GIST = re.compile(r",\s*(?P<gist>portant[^,\n]{0,200}|"
                          r"fixant[^,\n]{0,200}|relatif[^,\n]{0,200}|"
                          r"modifiant[^,\n]{0,200})", re.IGNORECASE)

# --- act's own number and date ---
RE_ACT_NUMBER = re.compile(r"n[°ºo]\s*(?P<num>\d{2,4}\s*-\s*\d{1,4})", re.IGNORECASE)

RE_ACT_HEAD = re.compile(
    r"(?P<kind>d[ée]cret(?:-loi)?(?:\s+Pr[ée]sidentiel|\s+gouvernemental)?|"
    r"arr[êe]t[ée]s?|loi(?:\s+organique)?)"
    r"[^\n]{0,140}?(?:n[°ºo]\s*(?P<num>\d{2,4}\s*-\s*\d{1,4}))?"
    r"[^\n]{0,140}?du\s+(?P<date>" + DATE_CORE + r")", re.IGNORECASE)


def strip_accents(text: str) -> str:
    d = unicodedata.normalize("NFKD", text.replace("’", "'"))
    return "".join(c for c in d if not unicodedata.combining(c))


def parse_date_string(text: str) -> date | None:
    """Parse the first date in a short clause, textual or numeric."""
    folded = strip_accents(text).lower()
    m = RE_DATE_TXT.search(folded)
    if m:
        day_raw = m.group("d")
        day = 1 if day_raw.startswith("1er") or day_raw.startswith("1ere") else int(day_raw)
        month = MONTHS.get(m.group("m"))
        if month:
            try:
                return date(int(m.group("y")), month, day)
            except ValueError:
                return None
    m = RE_DATE_NUM.search(folded)
    if m:
        try:
            return date(int(m.group("y")), int(m.group("m")), int(m.group("d")))
        except ValueError:
            return None
    return None


# Lowercase words that may legitimately appear inside a Tunisian name.
_ALLOWED_LOWER = {
    "ben", "bent", "bin", "el", "al", "ould", "ouled", "abou", "abu", "abd",
    "abdel", "si", "sidi", "bel", "bou", "ibn", "ebn", "de", "du", "da", "la",
    "le", "van", "von", "dos", "di",
}


def clean_name(raw: str) -> str:
    """Tidy a captured name and reject boilerplate that is not a name.

    Validation is deliberately strict: the surrounding prose is dense with
    capitalised institutional phrases ("La declaration de souscription",
    "Recu par Madame le Receveur de l'Enregistrement"), and admitting those as
    people would pollute every downstream table.
    """
    name = re.sub(r"\s+", " ", (raw or "").strip())
    name = name.strip(" .,;:-'’")
    # drop a dangling particle left at the end of a truncated capture
    toks = name.split()
    while toks and strip_accents(toks[-1]).upper() in _ID_LABELS:
        toks.pop()
    name = " ".join(toks)
    while toks and strip_accents(toks[-1]).lower() in {
        "ben", "bent", "bin", "el", "al", "ould", "ouled", "abou", "abd",
        "abdel", "si", "sidi", "bel", "bou", "ibn", "ebn", "et", "de", "du",
    }:
        toks.pop()
    name = " ".join(toks)
    if len(name) < 4 or " " not in name:
        # A single token is too ambiguous to treat as a person.
        return ""
    toks = name.split()
    if len(toks) > 5:
        return ""
    if re.search(r"[\d:;()/»«\"]", name):
        return ""
    for tok in toks:
        bare = strip_accents(tok).strip(".").upper()
        if bare in NAME_STOPWORDS:
            return ""
        low = strip_accents(tok).strip(".").lower()
        # Every token must look like a name component: capitalised, all-caps,
        # or one of the recognised Arabic/European particles.
        if low not in _ALLOWED_LOWER and not re.match(rf"^[{U}]", tok):
            return ""
    # Require at least one token that is not a particle.
    if not any(strip_accents(t).strip(".").lower() not in _ALLOWED_LOWER for t in toks):
        return ""
    return name


@lru_cache(maxsize=1)
def role_lookup() -> list[tuple[str, str]]:
    """Surface role forms, longest first so 'directeur general adjoint' wins."""
    cfg = load_config("vocab_roles")
    pairs = [(strip_accents(k).lower(), v) for k, v in cfg["surface_forms"].items()]
    return sorted(pairs, key=lambda p: -len(p[0]))


def match_role(text: str) -> tuple[str, str]:
    """Map a role phrase onto the controlled vocabulary.

    Returns (canonical_role, verbatim). The verbatim form is always kept so an
    unmapped or mis-mapped role can be audited and the lexicon extended.
    """
    if not text:
        return "", ""
    verbatim = re.sub(r"\s+", " ", text.strip()).strip(" .,;:")
    folded = strip_accents(verbatim).lower()
    for surface, canon in role_lookup():
        if re.search(rf"(?<![a-z]){re.escape(surface)}(?![a-z])", folded):
            return canon, verbatim[:200]
    return "", verbatim[:200]


def mandate_years(text: str) -> float | None:
    for rx in (RE_MANDATE_YEARS, RE_MANDATE_EXERCICES):
        m = rx.search(text)
        if m:
            raw = m.group("n").lower()
            return float(WORD_NUMBERS.get(raw, raw)) if raw.isalpha() or raw.isdigit() else None
    return None


def normalise_mf(raw: str) -> str:
    """Reduce a matricule fiscal to a comparable stem.

    Three surface forms occur (1518656/S/A/M/000, 1516084T, 007240 WPM 000);
    the leading digits plus the first letter identify the firm.
    """
    if not raw:
        return ""
    compact = re.sub(r"[^0-9A-Za-z]", "", raw).upper()
    m = re.match(r"(\d{6,8})([A-Z])?", compact)
    if not m:
        return ""
    return m.group(1).lstrip("0") + (m.group(2) or "")


def parse_capital(text: str) -> float | None:
    m = RE_CAPITAL.search(text)
    if not m:
        return None
    raw = m.group("amount")
    raw = re.sub(r"[\s.]", "", raw).replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def find_persons(text: str) -> list[tuple[str, str, int]]:
    """Every titled person mention: (name, married_name, offset)."""
    out = []
    for m in RE_PERSON.finditer(text):
        name = clean_name(m.group("name"))
        if name:
            out.append((name, clean_name(m.group("spouse") or ""), m.start()))
    return out


def find_name_links(text: str) -> list[tuple[str, str, str, str, int]]:
    """Every marriage or maiden-name claim: (person, other, relation, marker, offset).

    `relation` is one of `spouse_of`, `widow_of`, `maiden_name_of`. Both ends
    are put through `clean_name`, so a pair is returned only when each side is
    a plausible multi-token name -- a bare surname ("epouse Bouricha") is not
    an identifiable second person and yields nothing here. It survives in the
    `person_married_name` column on the role event, which is unchanged.
    """
    out: list[tuple[str, str, str, str, int]] = []
    for m in RE_NAME_LINK.finditer(text):
        relation = name_link_kind(m.group("link"))
        if not relation:
            continue
        person = clean_name(_RE_LEAD_TITLE.sub("", m.group("name")))
        other = clean_name(_RE_LEAD_TITLE.sub("", m.group("spouse")))
        # A capture that resolves to the same name on both sides is OCR
        # doubling, not a marriage to oneself.
        if not person or not other or parse_person(person).match_key == parse_person(other).match_key:
            continue
        out.append((person, other, relation, m.group("link"), m.start()))
    return out


# The role phrase must stop before the next person or the next "en qualite":
# a resolution naming two officers has no punctuation between them, so an
# unbounded capture swallows the second person and mis-titles them.
RE_QUALITE = re.compile(
    r"en\s+(?:(?:sa|leur|ses)?\s*qualit[ée]s?\s+d[e\']|tant\s+qu[e\'])\s*"
    r"(?P<role>(?:(?!\s+et\s+(?:" + TITLE + r"))(?!\s+en\s+qualit)[^,.;\n]){3,90})",
    re.IGNORECASE)


@lru_cache(maxsize=1)
def _role_word_re() -> re.Pattern:
    """Alternation over every surface role form, longest first."""
    forms = sorted((re.escape(s) for s, _c in role_lookup()), key=len, reverse=True)
    return re.compile(r"(?<![a-z])(" + "|".join(forms) + r")(?![a-z])", re.IGNORECASE)


def pair_person_roles(clause: str) -> list[tuple[str, str, str]]:
    """Associate each person in a clause with their own role.

    A single resolution often names several people in different roles --
    "Mme Saida Bessrour est nommee gerante ... et Mr Sami Ben Sedrine est nomme
    co-gerant" -- so a clause-level role applied to everyone mis-titles people.
    Each person takes the first role that appears after them and before the
    next person named.

    Role anchors are not limited to "en qualite de": a bare role word counts
    too, which is how the majority of appointments are actually phrased.

    Returns (name, married_name, role_phrase); role_phrase is empty when the
    text gives that person no role of their own.
    """
    persons = [(m.start(), clean_name(m.group("name")),
                clean_name(m.group("spouse") or ""))
               for m in RE_PERSON.finditer(clause)]
    persons = [(o, n, s) for o, n, s in persons if n]
    if not persons:
        return []

    roles = [(m.start(), m.group("role")) for m in RE_QUALITE.finditer(clause)]
    # Fall back to bare role words where no explicit "en qualite de" phrase sits
    # between this person and the next.
    # The role lexicon is accent-stripped, so the search runs on a folded copy
    # of the clause. Folding a Latin-1 accented letter leaves length unchanged,
    # so offsets still line up with the original.
    folded = strip_accents(clause)
    if len(folded) == len(clause):
        roles += [(m.start(), clause[m.start():m.end()])
                  for m in _role_word_re().finditer(folded)]
    roles.sort()
    out: list[tuple[str, str, str]] = []
    for i, (offset, name, spouse) in enumerate(persons):
        next_offset = persons[i + 1][0] if i + 1 < len(persons) else len(clause) + 1
        own = ""
        for r_off, r_text in roles:
            if offset < r_off < next_offset:
                own = r_text
                break
        out.append((name, spouse, own))

    # A single role phrase before every person governs them all
    # ("sont nommes en qualite d'administrateurs : X, Y et Z").
    if len(roles) == 1 and all(not r for _n, _s, r in out) and roles[0][0] < persons[0][0]:
        return [(n, s, roles[0][1]) for n, s, _r in out]

    return out


RE_PLURAL_TITLE = re.compile(
    r"(?i:Messieurs|Mesdames(?:\s+et\s+Messieurs)?|Mesdemoiselles)\s+(?P<span>[^.;:\n]{6,220})")


def split_plural_title(text: str) -> list[str]:
    """Names introduced by a plural title and joined by commas or "et".

    "Messieurs Foued Noomen et Nizar Frikha" yielded only the first name,
    because only the first carries a title of its own. The construction appears
    in 1,166 corporate blocks, so every later name in it was being lost.
    """
    out: list[str] = []
    for m in RE_PLURAL_TITLE.finditer(text):
        span = m.group("span")
        # stop at the first verb-like continuation so the span stays a name list
        span = re.split(r"\s+(?:ont|sont|a|est|au|du|de\s+la|en\s+qualit|en\s+tant)\s+",
                        span)[0]
        for part in re.split(r",|\bet\b", span):
            name = clean_name(part)
            if name:
                out.append(name)
    return out


def split_person_list(text: str) -> list[str]:
    """Split an enumeration of people into individual names.

    Needed for the common 'Monsieur X, Monsieur Y et Madame Z' construction.
    """
    names = [n for n, _s, _o in find_persons(text)]
    names += [n for n in split_plural_title(text) if n not in names]
    if names:
        return names
    # Fall back to splitting an untitled enumeration, but validate each part:
    # a bare comma split over prose otherwise yields institutional phrases.
    out = []
    for part in re.split(r",|\bet\b|;|\n", text):
        part = part.strip()
        if len(part.split()) > 4:
            continue
        name = clean_name(part)
        if name:
            out.append(name)
    return out
