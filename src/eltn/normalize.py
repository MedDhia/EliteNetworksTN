"""Normalisation and entity resolution for extracted JORT events.

Three vocabularies are built here:

*persons*        OCR-tolerant clustering of name strings into person ids.
*organisations*  canonical institution names, with a crosswalk that keeps a
                 ministry identifiable across its many renamings.
*positions*      a hierarchical rank code (the analytically useful part) plus
                 a cleaned position label.

Everything is deterministic and rule-based: no model, no hand-labelling, so
the same corpus always yields the same ids and a coding decision can always be
traced back to the rule that produced it.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict

# --------------------------------------------------------------------------
# String folding
# --------------------------------------------------------------------------


def fold(s: str) -> str:
    """Lowercase, strip accents and punctuation, squeeze spaces."""
    if not s:
        return ""
    s = unicodedata.normalize("NFD", str(s).lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("'", " ").replace("’", " ").replace("-", " ")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# Consonant-skeleton transliteration.  Tunisian names are romanised from
# Arabic inconsistently across seventy years of the gazette (Chedly/Chadly,
# Béchir/Bachir, Aïcha/Aicha, Mohamed/Mohammed/Muhamed), and OCR adds more
# noise.  Collapsing predictable vowel and digraph variation gives a blocking
# key that survives all of it.
_TRANSLIT = [
    (r"ph", "f"), (r"ck", "k"), (r"qu", "k"), (r"q", "k"), (r"x", "ks"),
    (r"ch", "5"), (r"sh", "5"), (r"kh", "6"), (r"gh", "7"), (r"dh", "8"),
    (r"th", "9"), (r"ou", "u"), (r"ww", "w"), (r"y", "i"), (r"j", "j"),
    (r"z", "z"), (r"c", "k"), (r"[aeiou]+", "a"),
]


# The Arabic definite article assimilates onto the following consonant when
# romanised ("Ennaceur" / "Naceur", "Essebsi" / "Sebsi", "Ettounsi" /
# "Tounsi").  Both forms are printed, sometimes in the same issue.
_ASSIMILATED_ARTICLE = re.compile(r"^e([bcdfgjklmnpqrstvwxz])\1")


def skeleton(name: str) -> str:
    """Vowel-collapsed consonant skeleton used as a blocking key."""
    s = _ASSIMILATED_ARTICLE.sub(r"\1", fold(name))
    for pat, rep in _TRANSLIT:
        s = re.sub(pat, rep, s)
    s = re.sub(r"(.)\1+", r"\1", s)   # de-double letters
    return s


# Honorific / relational tokens that are not part of the name proper.
_NAME_NOISE = re.compile(
    r"\b(epouse|epse|ep|veuve|vve|nee|ne|dit|dite|fils\s+de|bent|bint)\b"
)
_NAME_PARTICLES = {"ben", "bel", "bin", "bou", "abou", "abd", "el", "al",
                   "ez", "es", "ech", "de", "du", "des", "la", "le", "sidi"}


def clean_name(raw: str) -> str:
    """Canonical display form of a personal name."""
    s = re.sub(r"\s+", " ", str(raw or "")).strip(" .,;-")
    s = re.sub(r"\s*\([^)]*\)\s*", " ", s)
    return re.sub(r"\s+", " ", s).strip(" .,;-")


def name_key(raw: str) -> str:
    """Order-insensitive matching key for a personal name.

    The gazette prints both "Mohamed Gargouri" and "Gargouri Mohamed"; the
    sorted token skeleton makes those the same person, while dropping the
    particles that appear and disappear between printings.
    """
    s = _NAME_NOISE.sub(" ", fold(clean_name(raw)))
    tokens = [t for t in s.split() if t and t not in _NAME_PARTICLES and len(t) > 1]
    if not tokens:
        tokens = [t for t in s.split() if t]
    return " ".join(sorted(skeleton(t) for t in tokens))


# --------------------------------------------------------------------------
# Organisations
# --------------------------------------------------------------------------

_ORG_LEAD = re.compile(
    r"^(?:au?\s+|aux\s+|[àa]\s+|de\s+la\s+|de\s+l\s*'|du\s+|des\s+|de\s+|"
    r"l\s*'|la\s+|le\s+|les\s+|dudit\s+|ladite\s+)+",
    re.I,
)
_ORG_TRAIL = re.compile(
    r"\s*(?:,?\s*(?:et\s+ce|conform[ée]ment|dans\s+la\s+limite|"
    r"tel\s+que|susvis[ée]e?|pr[ée]cit[ée]e?)\b.*)$",
    re.I,
)

# Ministries are renamed constantly (education/enseignement/formation split
# and re-merge, "domaines de l'Etat" folds into finance, etc.).  We keep the
# *portfolio* as the stable unit: a ministry is identified by the policy
# domains in its title, so a renamed ministry stays comparable over time while
# a genuinely different portfolio stays distinct.
MINISTRY_DOMAINS = [
    ("justice", r"\bjustice\b"),
    ("interieur", r"\binterieur\b"),
    ("defense", r"\bdefense\b"),
    ("affaires_etrangeres", r"\baffaires\s+etrangeres\b|\bdiplomatie\b"),
    ("finances", r"\bfinances?\b"),
    ("plan", r"\bplan\b|\bplanification\b"),
    ("economie", r"\beconomie\b|\beconomique\b"),
    ("developpement", r"\bdeveloppement\b"),
    ("investissement", r"\binvestissement\b"),
    ("cooperation", r"\bcooperation\s+internationale\b"),
    ("commerce", r"\bcommerce\b"),
    ("industrie", r"\bindustrie\b"),
    ("energie", r"\benergie\b|\bmines\b"),
    ("agriculture", r"\bagriculture\b|\bpeche\b|\bhydraulique\b"),
    ("environnement", r"\benvironnement\b|\bdeveloppement\s+durable\b"),
    ("equipement", r"\bequipement\b|\bhabitat\b|\blogement\b|\binfrastructure"),
    ("transport", r"\btransports?\b"),
    ("tourisme", r"\btourisme\b|\bartisanat\b"),
    ("sante", r"\bsante\b"),
    ("affaires_sociales", r"\baffaires\s+sociales\b|\bsolidarite\b"),
    ("emploi", r"\bemploi\b|\bformation\s+professionnelle\b"),
    ("education", r"\beducation\b|\benseignement\s+(?:de\s+base|secondaire|primaire)\b"),
    ("enseignement_superieur", r"\benseignement\s+superieur\b|\brecherche\s+scientifique\b"),
    ("culture", r"\bculture\b|\bculturelles\b|\bpatrimoine\b"),
    ("information", r"\binformation\b|\bcommunication\b"),
    ("jeunesse_sport", r"\bjeunesse\b|\bsports?\b|\benfance\b"),
    ("affaires_religieuses", r"\baffaires\s+religieuses\b"),
    ("femme_famille", r"\bfemme\b|\bfamille\b"),
    ("fonction_publique", r"\bfonction\s+publique\b|\breforme\s+administrative\b"),
    ("domaines_etat", r"\bdomaines?\s+de\s+l\s*etat\b|\baffaires\s+foncieres\b"),
    ("technologies", r"\btechnologies?\s+de\s+la\s+communication\b|\bnumerique\b"),
    ("droits_homme", r"\bdroits\s+de\s+l\s*homme\b|\bjustice\s+transitionnelle\b"),
    ("relations_assemblee", r"\brelations?\s+avec\s+(?:l\s*assemblee|les\s+instances)\b"),
]

CENTRAL_EXECUTIVE = [
    ("presidence_republique", r"^presidence\s+de\s+la\s+republique|^cabinet\s+presidentiel"),
    ("presidence_gouvernement", r"^presidence\s+du\s+gouvernement|^premier\s+ministere|"
                                r"^chefe?\s+du\s+gouvernement|^premier\s+ministre"),
]

ORG_FORMS = [
    ("ministere", r"^ministere\b|^secretariat\s+d\s*etat\b|^sous\s+secretariat"),
    ("presidence", r"^presidence\b"),
    ("gouvernorat", r"^gouvernorat\b"),
    ("commune", r"^commune\b|^municipalite\b"),
    ("banque", r"\bbanque\b|^caisse\b"),
    ("entreprise_publique", r"^societe\b|^office\b|^agence\b|^regie\b|^entreprise\b|"
                            r"^compagnie\b|^groupe\b"),
    ("etablissement_sante", r"^hopital\b|^centre\s+hospitalier\b|^institut\b.*\bsante\b|"
                            r"^etablissement\s+(?:public\s+de\s+)?sante\b"),
    ("universite", r"^universite\b|^faculte\b|^ecole\s+(?:nationale|superieure)\b|"
                   r"^institut\s+superieur\b|^institut\s+national\b"),
    ("juridiction", r"^cour\b|^tribunal\b|^conseil\s+d\s*etat\b|^parquet\b"),
    ("instance_independante", r"^instance\b|^haute\s+autorite\b|^autorite\b|^comite\b|"
                              r"^conseil\s+(?:national|superieur|constitutionnel)\b"),
    ("direction", r"^direction\b|^unite\b|^cellule\b|^commissariat\b|^inspection\b"),
]


def clean_org(raw: str) -> str:
    s = re.sub(r"\s+", " ", str(raw or "")).strip(" .,;:-")
    s = _ORG_TRAIL.sub("", s)
    s = _ORG_LEAD.sub("", s)
    s = re.sub(r"^«\s*|\s*»$", "", s).strip(" .,;:-«»\"")
    return re.sub(r"\s+", " ", s)


def org_form(name: str) -> str:
    f = fold(name)
    for label, pat in ORG_FORMS:
        if re.search(pat, f):
            return label
    return "autre"


def ministry_portfolio(name: str) -> str:
    """Stable portfolio id for a ministry / central-executive body."""
    f = fold(name)
    for label, pat in CENTRAL_EXECUTIVE:
        if re.search(pat, f):
            return label
    if not re.search(r"^ministere\b|^secretariat\s+d\s*etat\b", f):
        return ""
    hits = [label for label, pat in MINISTRY_DOMAINS if re.search(pat, f)]
    return "min_" + "+".join(sorted(hits)) if hits else "min_autre"


def org_key(raw: str) -> str:
    """Matching key for an organisation string."""
    name = clean_org(raw)
    port = ministry_portfolio(name)
    if port:
        return port
    f = fold(name)
    f = re.sub(r"\b(de|du|des|la|le|les|l|d|a|au|aux|en|et|pour|sur)\b", " ", f)
    return re.sub(r"\s+", " ", f).strip()


# --------------------------------------------------------------------------
# Positions
# --------------------------------------------------------------------------
#
# Rank is ordered so that a career can be read as a trajectory.  The scale is
# the one Tunisian administrative law actually uses for "emplois fonctionnels",
# extended upwards to political office.

RANK_SCALE = [
    ("chef_etat", 100, r"^president\s+de\s+la\s+republique\b"),
    ("chef_gouvernement", 95, r"^(?:chefe?\s+du\s+gouvernement|premier\s+ministre)\b"),
    ("ministre", 90, r"^ministre\b|^ministre\s+d\s*etat\b"),
    ("secretaire_etat", 85, r"^secretaire\s+d\s*etat\b|^sous\s+secretaire\s+d\s*etat\b"),
    ("gouverneur", 80, r"^gouverneur\b"),
    ("chef_cabinet", 74, r"^chefe?\s+d[eu]\s+cabinet\b|^directeur\s+du\s+cabinet\b"),
    ("conseiller_pol", 72, r"^conseiller\b.*\b(?:president|chef\s+du\s+gouvernement|"
                           r"premier\s+ministre|ministre)\b|^charge\s+de\s+mission\b"),
    ("secretaire_general", 70, r"^secretaire\s+general\b|^secretaire\s+generale\b"),
    ("pdg", 68, r"^president\s+directeur\s+general\b|^pdg\b"),
    ("directeur_general", 65, r"^directeur\s+general\b|^directrice\s+generale\b|"
                              r"^gouverneur\s+de\s+la\s+banque\s+centrale\b"),
    ("president_juridiction", 64, r"^(?:premier\s+)?president\b.*\b(?:cour|tribunal)\b|"
                                  r"^procureur\s+general\b"),
    ("inspecteur_general", 60, r"^inspecteur\s+general\b|^controleur\s+general\b"),
    ("directeur", 55, r"^directeur\b|^directrice\b|^commissaire\s+regional\b|"
                      r"^delegue\s+regional\b"),
    ("sous_directeur", 45, r"^sous\s+directeur\b|^sous\s+directrice\b|"
                           r"^directeur\s+adjoint\b"),
    ("chef_service", 35, r"^chef\s+(?:de\s+)?service\b|^chef\s+de\s+division\b|"
                         r"^chef\s+de\s+departement\b|^chef\s+de\s+bureau\b|"
                         r"^chef\s+de\s+subdivision\b|^chef\s+d\s*arrondissement\b"),
    ("administrateur_ca", 30, r"^administrateur\b|^membre\b|^representant\b"),
    ("magistrat", 28, r"^juge\b|^conseiller\b.*\b(?:cour|tribunal)\b|^substitut\b"),
    ("cadre", 20, r"^attache\b|^inspecteur\b|^ingenieur\b|^redacteur\b|^analyste\b|"
                  r"^controleur\b|^receveur\b|^percepteur\b"),
    ("local", 15, r"^cheikh\b|^omda\b|^delegue\b|^maire\b|^president\s+de\s+la\s+commune\b"),
    ("academique", 12, r"^professeur\b|^maitre\s+de\s+conferences\b|^maitre\s+assistant\b|"
                       r"^assistant\b|^doyen\b|^directeur\s+d\s*etudes\b"),
    ("medical", 10, r"^chef\s+de\s+service\s+hospitalier\b|^medecin\b|^praticien\b"),
]

_POS_LEAD = re.compile(
    r"^(?:un|une|des|le|la|les|l\s*'|d\s*'|de|du|au|aux|en\s+qualite\s+de)\s+", re.I
)


def clean_position(raw: str) -> str:
    s = re.sub(r"\s+", " ", str(raw or "")).strip(" .,;:-")
    s = _POS_LEAD.sub("", s)
    return s.strip(" .,;:-")


def position_rank(raw: str) -> tuple[str, int]:
    """Return (rank_label, rank_score) for a position string."""
    f = fold(clean_position(raw))
    if not f:
        return "", 0
    # Longest, most specific patterns are listed first within each tier, and
    # the scale is walked from the top so that "directeur general" does not
    # fall through to "directeur".
    # The gazette pluralises the office when one act appoints several people
    # ("Sont nommes cheikhs", "... nommes directeurs").
    variants = (f, re.sub(r"\b(?!sous\b|des\b|les\b|aux\b|plus\b|hors\b)(\w{3,})s\b",
                          r"\1", f))
    for label, score, pat in RANK_SCALE:
        if any(re.search(pat, v) for v in variants):
            return label, score
    return "autre", 5


def position_key(raw: str) -> str:
    f = fold(clean_position(raw))
    f = re.sub(r"\b(de|du|des|la|le|les|l|d|a|au|aux|en|et|pour|sur|charge)\b", " ", f)
    return re.sub(r"\s+", " ", f).strip()


# --------------------------------------------------------------------------
# Person resolution
# --------------------------------------------------------------------------


class _Union:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def _block_key(key: str) -> str:
    """Coarse block: the stem of the longest skeleton token (the patronym)."""
    tokens = key.split()
    return max(tokens, key=len)[:4] if tokens else ""


def _affix_variant(a: str, b: str, max_gap: int = 2) -> bool:
    """True when two keys differ only by truncated/extended token endings.

    This is the shape of the residual variation the exact key misses: a
    dropped final vowel, a lost OCR character, a French feminine ending
    ("Romdhan" / "Romdhane").  Requiring a prefix relationship rather than a
    similarity score keeps genuinely different names apart -- "salah" and
    "salem" score alike under any edit-distance ratio but are not variants of
    one another.
    """
    ta, tb = a.split(), b.split()
    if len(ta) != len(tb) or not ta:
        return False
    differing = 0
    for x, y in zip(ta, tb):
        if x == y:
            continue
        short, long_ = (x, y) if len(x) <= len(y) else (y, x)
        if not long_.startswith(short) or len(long_) - len(short) > max_gap:
            return False
        if len(short) < 3:
            return False
        differing += 1
    return 0 < differing <= 2


def resolve_persons(names, *, fuzzy: bool = True, threshold: int = 90) -> dict[str, str]:
    """Map every raw name string to a stable person id.

    Two passes.  Exact blocking on the sorted-token skeleton merges spelling
    and word-order variants ("Gargouri Mohamed" / "Mohamed Gargouri",
    "Chedly" / "Chadly").  A second, conservative fuzzy pass then merges keys
    that share their longest token and are near-identical overall, which
    catches the residue of OCR damage and dropped final letters
    ("Bouden Romdhane" / "Bouden Romdhan").

    Deliberately blunt in one direction: two different people who share a
    name are merged.  Homonymy is the standing limitation of gazette-based
    prosopography; the codebook documents it and the panel keeps the raw
    strings so a researcher can split a suspect id by hand.
    """
    groups: dict[str, Counter] = defaultdict(Counter)
    for raw in names:
        key = name_key(raw)
        if key:
            groups[key][clean_name(raw)] += 1

    keys = sorted(groups)
    uf = _Union()
    for k in keys:
        uf.find(k)

    if fuzzy and len(keys) > 1:
        blocks: dict[str, list[str]] = defaultdict(list)
        for k in keys:
            blocks[_block_key(k)].append(k)
        for block in blocks.values():
            if len(block) < 2 or len(block) > 600:
                continue  # an oversized block means a generic token, not a name
            for i, a in enumerate(block):
                for b in block[i + 1:]:
                    if _affix_variant(a, b):
                        uf.union(a, b)

    roots = sorted({uf.find(k) for k in keys})
    ids = {root: f"P{i:06d}" for i, root in enumerate(roots, start=1)}
    key_to_id = {k: ids[uf.find(k)] for k in keys}

    return {raw: key_to_id.get(name_key(raw), "") for raw in set(names)}


def person_display(names: Counter) -> str:
    """Most frequent surface spelling, ties broken by the longest form."""
    return max(names.items(), key=lambda kv: (kv[1], len(kv[0])))[0]
