"""Stage 6: the Latin edition of the registers.

Every name in this build is Arabic script, and the column that looks like the
Latin one is not. ``name_translit`` is a vowel-less consonant skeleton built to
generate identifiers -- it drops ayn and hamza, merges the emphatics with their
plain counterparts, and deletes any letter missing from its table -- so
``سالم بو حاجب`` comes out ``SALM BW HAJB``. Arabic script does not write short
vowels, so nothing can recover ``Salem`` from that. The vowels are not in the
data and never were. Every Latin form therefore has to be supplied by hand or
by a reader, and ``config/aalam_names_latin.yaml`` is where they are kept.

Two columns, not one
--------------------
``name_fr`` is the Tunisian French form, which is how these people are spelled
in Tunisian archives and in the gazette build in this repository (45,634
persons, 8,803 institutions, all French). It is also the author's own
orthography: Zmerli wrote in French and this volume is Hammadi Sahli's Arabic
rendering, so the French form restores a spelling rather than inventing one.

``name_ijmes`` is the Middle East studies convention, which is what an
Anglophone journal expects and what makes the volume's people findable in a
literature that does not use the French forms.

Neither column translates. ``جريدة الحاضرة`` is ``al-Hadira``, never "The
Metropolis": a newspaper's title is its name. The one exception is declared,
not silent -- see ``fr_conventional`` below.

What guarantees a gloss
-----------------------
The extraction passes were admitted by quoting the page verbatim. A gloss has
no page to quote, so it gets the analogous check: ``spine()`` reduces a Latin
form and an Arabic string to the same sequence of consonants, and a pair that
disagrees is refused. This catches a gloss attached to the wrong name, which is
the failure that matters, and it is checked on every row rather than a sample.

It cannot catch a wrong **vowel**. ``Salim`` and ``Salem`` have one spine, and
the vowel is exactly what the Arabic never recorded. That residual falls on the
rows glossed by reading rather than by knowledge, which is why they carry
``gloss_tier`` and why the ones a reader will actually meet are verified by
hand. See ``docs/LIMITATIONS-aalam-tunisiyun.md``.
"""
from __future__ import annotations

import argparse
import csv
import re
import unicodedata
from functools import lru_cache

from .llm import open_text
from .textnorm_ar import strip_harakat
from .paths import PROCESSED, load_config

# --- the gate --------------------------------------------------------------

# Digraphs first, longest first, or `sh` inside `Achour` would resolve as A-C-H.
# The French column and the IJMES column spell the same consonant differently
# (`ch` against `sh`, `dj` against `j`), so both spellings fold to one class.
_DIGRAPHS = [
    ("sch", "S"),
    ("kh", "X"), ("gh", "V"), ("dh", "D"), ("th", "T"), ("sh", "S"),
    ("ch", "S"), ("dj", "J"), ("ph", "F"),
]

# The Tunisian letters for a hard g, absent from the identifier table, which
# therefore deletes them: `حسن ڤلاتي` would lose its middle consonant entirely
# and no correct gloss could match it. Mapped here, in the gate only, so no
# identifier moves.
_EXTRA_LETTERS = {"ڤ": "ق", "ڨ": "ق", "پ": "ب", "چ": "ج", "ﭬ": "ق"}

# `عبد الجليل` is `Abd al-Jalil` with the article written out and `Abdeljelil`
# with it swallowed into the word. Both are the same name; the compound head is
# normalised so the article can be removed once, by the pattern below.
_COMPOUND = re.compile(r"\babd[\s-]*[ae]l[\s-]*", re.I)

# Written in Latin, never present in the Arabic skeleton: the short vowels the
# script omits, and the matres lectionis, which `transliterate` renders A, W
# and Y but which surface in Latin as any vowel at all (`بو` is Bou, Bu, Bo).
_VOWELS = set("AEIOUWY")

# The article, on both sides. Arabic prefixes it to the word; Latin writes it
# al-, el-, ez-, es-, ech- (assimilated to a sun letter) or drops it outright.
# `خير الدين` is `Khereddine` with no l at all, so the article is removed
# rather than matched.
_LATIN_ARTICLE = re.compile(
    r"\b(?:al|el|ad|ar|as|az|ech|esh|ez|es|er|ed)[-\s]", re.I)
# The same proclitics as on the Arabic side, and removed the same way: the
# preposition's consonant stays, only the article goes. `lil-Hizb` is لل + حزب.
_LATIN_PROCLITIC = re.compile(r"\b(b|l)(?:il|i[-\s]*al|i[-\s]*el)[-\s]", re.I)
# French prefixes its own article to a transliterated name: La Khaldounia,
# Le Tunisien. It is French grammar, not part of the Arabic string.
# The article is a separate word, so the pattern demands the space. Without it
# `Lavisse` lost its first two letters and no correct gloss of لافيس could pass.
_FRENCH_ARTICLE = re.compile(r"^\s*(?:(?:la|le|les)\s+|l['’])", re.I)


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text)
                   if unicodedata.category(c) != "Mn")


def _squeeze(spine: str) -> str:
    """Collapse a doubled consonant: `Khereddine` and `Khayr al-Din` are one name."""
    out = []
    for ch in spine:
        if not out or out[-1] != ch:
            out.append(ch)
    return "".join(out)


def _labial(spine: str) -> str:
    """`حانبة` is written Hanba and said Hamba; French spells what is said."""
    return re.sub(r"N(?=[BM])", "M", spine)


# `th` and `dh` are the two Latin digraphs that are also a legal pair of single
# letters: `th` is ث in `Othmana` but ت followed by ح in `Fathallah`, and `dh`
# is ذ in `Fadhel` but د followed by ه in `Midhat`. Both readings are tried.
# The others are not ambiguous and are always folded: reading the `ch` of
# `Pacha` as two letters would invent a consonant.
_AMBIGUOUS = ("th", "dh")


def latin_spine(text: str, *, split: tuple = ()) -> str:
    """The consonants of a Latin name, with everything the Arabic omits removed.

    Digraphs named in ``split`` are read as two letters rather than one.
    """
    s = _strip_accents(text).lower()
    s = _FRENCH_ARTICLE.sub("", s)
    s = _COMPOUND.sub("abd ", s)
    s = _LATIN_PROCLITIC.sub(r"\1 ", s)
    s = _LATIN_ARTICLE.sub(" ", s)
    # Before the digraphs, because the class marker for غ is v and this would
    # otherwise rewrite it: Ghattas would come back Fattas.
    s = s.replace("v", "f")
    for src, dst in _DIGRAPHS:
        if src not in split:
            s = s.replace(src, dst.lower())
    # French g is two consonants. Before a front vowel it is the sound of ج;
    # elsewhere, and in the digraph gu, it is the hard g that Tunisian French
    # writes for ق (Bourguiba is بورقيبة). The orthographic rule decides.
    s = re.sub(r"gu(?=[eiy])", "k", s)
    s = re.sub(r"g(?=[eiy])", "j", s)
    s = s.replace("g", "k")
    s = re.sub(r"c(?=[eiy])", "s", s)
    s = s.replace("c", "k").replace("ç", "s").replace("q", "k")
    # Arabic has no p: `باشا` comes back as Pasha in both conventions. It has
    # no v either, and writes ف for one -- فيكتور is Victor, لافيس is Lavisse --
    # which is handled above, before the digraph pass.
    s = s.replace("p", "b")
    s = re.sub(r"[^a-z]", "", s)
    s = "".join(c for c in s.upper() if c not in _VOWELS)
    return _squeeze(_labial(s))


# The spine reads the Arabic letters directly rather than folding the output of
# `transliterate`. That skeleton writes ث as TH and ذ as DH, so a د followed by
# a ه is indistinguishable from a single ذ: `محمد عبده` came out MHMDBD and no
# correct gloss of Abduh could match it. One letter, one class, no ambiguity.
_ARABIC_CLASS = {
    "ب": "B", "ت": "T", "ث": "T", "ج": "J", "ح": "H", "خ": "X",
    "د": "D", "ذ": "D", "ر": "R", "ز": "Z", "س": "S", "ش": "S",
    "ص": "S", "ض": "D", "ط": "T", "ظ": "Z", "غ": "V", "ف": "F",
    "ق": "K", "ك": "K", "ل": "L", "م": "M", "ن": "N", "ه": "H",
    # The Tunisian letters for a hard g and a p, absent from the identifier
    # table, which therefore deletes them: `حسن ڤلاتي` would lose its middle
    # consonant and no correct gloss could match it.
    "ڤ": "K", "ڨ": "K", "ﭬ": "K", "پ": "B", "چ": "J",
    # Written, not sounded as a consonant: the long vowels, the glottals the
    # Latin forms drop, and the diacritics.
    "ا": "", "أ": "", "إ": "", "آ": "", "و": "", "ي": "", "ى": "",
    "ء": "", "ئ": "", "ؤ": "", "ة": "",
}

# The article, with the proclitics that fuse to it. Only the article is
# removed: the ب of `بالقاهرة` is a preposition and a consonant the Latin form
# writes (`bi-al-Qahira`), so stripping the pair whole would make every correct
# gloss fail. و is a vowel class and leaves nothing behind either way.
# A bracket counts as a boundary, for `كلية الآداب (السوربون)`.
_AR_PROCLITIC = [(re.compile(r"(?:^|(?<=[\s(\[«]))بال"), "ب"),
                 (re.compile(r"(?:^|(?<=[\s(\[«]))لل"), "ل"),
                 (re.compile(r"(?:^|(?<=[\s(\[«]))(?:وال|ال)"), " ")]


def arabic_spine(text: str) -> str:
    """The consonants of an Arabic string, by the same reduction as the Latin."""
    s = strip_harakat(text)
    for pattern, repl in _AR_PROCLITIC:
        s = pattern.sub(repl, s)
    out = "".join(_ARABIC_CLASS.get(ch, "") for ch in s)
    return _squeeze(_labial(out))


def spines_agree_exact(arabic: str, latin: str) -> bool:
    return bool(latin_spine(latin)) and latin_spine(latin) == arabic_spine(arabic)


# An organisation is stored under the string a sentence used, which usually
# carries the common noun for what it is: `جريدة الحاضرة`, `جمعية قدماء
# الصادقية`, `جامع الزيتونة`. The Latin form drops it -- nobody writes
# "Newspaper al-Hadira" -- and the kind is already a column, so the gate
# accepts a spine with the head removed as well as the full one.
_ORG_HEADS = ("جريدة", "مجلة", "جمعية", "الجمعية", "جامع", "مدرسة", "المدرسة",
              "معهد", "المعهد", "حزب", "الحزب", "نادي", "النادي", "لجنة",
              "اللجنة", "حركة", "مؤتمر", "مكتبة", "الهيئة المديرة للجمعية",
              "الهيئة المديرة", "هيئة تحرير جريدة", "هيئة تحرير", "مجمع",
              "ديوان", "مجلس", "المجلس", "محكمة", "المحكمة", "وزارة", "الوزارة")


def _spines(arabic: str) -> set[str]:
    """Every spine a correct Latin form of this string is allowed to have.

    Two licensed variants beside the plain reading. A leading common noun may
    be dropped, as above. And ta marbuta, which the skeleton deletes, is
    pronounced and written t when the word governs another: `حركة الشباب` is
    `Harakat al-Shabab`, so both readings are allowed.
    """
    stripped = arabic.strip()
    forms = [stripped]
    for head in _ORG_HEADS:
        if stripped.startswith(head + " "):
            forms.append(stripped[len(head):].strip())
    out = set()
    for f in forms:
        out.add(arabic_spine(f))
        # One ta marbuta at a time: `جمعية قدماء الصادقية` is `Jamiyyat Qudama
        # al-Sadiqiyya`, where the first is sounded and the second is not.
        for i, ch in enumerate(f):
            if ch == "ة":
                out.add(arabic_spine(f[:i] + "ت" + f[i + 1:]))
    # A word-final ه is weak and French does not write it: `محمد عبده` is
    # `Mohamed Abdou`, where the vowel carries what is left of the consonant.
    out |= {s[:-1] for s in out if s.endswith("H")}
    return {s for s in out if s}


def spines_agree(arabic: str, latin: str) -> bool:
    """Whether a proposed Latin form is a rendering of this Arabic string."""
    ours = {latin_spine(latin, split=s)
            for s in ((), ("th",), ("dh",), _AMBIGUOUS)}
    return bool(latin_spine(latin)) and bool(ours & _spines(arabic))


# --- the stage -------------------------------------------------------------

# `transliterated`: the Latin form renders the Arabic and must pass the gate.
# `conventional`: the body's own French name is not a rendering of its Arabic
#   one (Collège Sadiki for المدرسة الصادقية), so only the French side is let
#   through; the IJMES side still transliterates and is still gated.
# `translated`: the row is a common-noun post or a description rather than a
#   name -- `وزير الداخلية`, `الأساتذة الذين ساهموا في تكوينهما` -- and no
#   transliteration of it would mean anything. Neither side is gated, and the
#   mode is what stops a reader taking the English for a proper name.
MODES = {"transliterated", "conventional", "translated"}

PERSON_FIELDS = [
    "person_id", "name_ar", "name_fr", "name_ijmes", "gloss_tier", "gloss_mode",
    "name_translit", "is_subject", "name_kind", "entry_uid", "cohort",
    "cohort_en", "birth_year", "death_year", "role_descriptor_ar",
    "role_descriptor_en", "rank", "n_assertions", "n_ties", "first_seen_entry",
]
ORG_FIELDS = [
    "org_id", "name_ar", "name_fr", "name_ijmes", "gloss_tier", "gloss_mode",
    "name_translit", "org_kind", "n_ties", "first_seen_entry",
]
EDGE_FIELDS = [
    "edge_id", "layer", "relation", "from_id", "from_name", "from_fr",
    "from_ijmes", "to_id", "to_name", "to_fr", "to_ijmes", "to_kind",
    "subjects_studied", "year", "year_lo", "year_hi", "date_precision",
    "evidence_tier", "extractor", "pattern_id", "confidence", "entry_uid",
    "evidence_quote",
]


@lru_cache(maxsize=1)
def glosses() -> dict[str, dict]:
    return load_config("aalam_names_latin")["names"]


@lru_cache(maxsize=1)
def cohorts() -> dict[str, str]:
    return load_config("aalam_names_latin")["cohorts"]


@lru_cache(maxsize=1)
def descriptors() -> dict[str, str]:
    return load_config("aalam_names_latin").get("role_descriptors", {})


def check(name: str, entry: dict) -> list[str]:
    """Everything wrong with one gloss, as sentences. Empty means it holds."""
    bad = []
    mode = entry.get("mode", "transliterated")
    if mode not in MODES:
        bad.append(f"{name}: unknown mode {mode!r}")
    for key in ("fr", "ijmes"):
        if not str(entry.get(key, "")).strip():
            bad.append(f"{name}: empty {key}")
    if mode == "translated":
        return bad
    if not spines_agree(name, entry["ijmes"]):
        bad.append(f"{name}: ijmes {entry['ijmes']!r} is not a rendering of it "
                   f"({arabic_spine(name)} against {latin_spine(entry['ijmes'])})")
    if mode == "transliterated" and not spines_agree(name, entry["fr"]):
        bad.append(f"{name}: fr {entry['fr']!r} is not a rendering of it "
                   f"({arabic_spine(name)} against {latin_spine(entry['fr'])}); "
                   "mark it conventional if that is deliberate")
    return bad


def _read(path):
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _write(path, fields, rows) -> None:
    with open_text(path, "w") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def run(*, strict: bool = True) -> dict[str, int]:
    table, missing, problems = glosses(), [], []
    persons = _read(PROCESSED / "persons.csv")
    orgs = _read(PROCESSED / "organisations.csv")

    for name, entry in table.items():
        problems.extend(check(name, entry))

    def gloss(name: str) -> dict:
        entry = table.get(name)
        if entry is None:
            missing.append(name)
            return {"fr": "", "ijmes": "", "tier": "", "mode": ""}
        return entry

    for r in persons:
        g = gloss(r["name_ar"])
        r["name_fr"], r["name_ijmes"] = g.get("fr", ""), g.get("ijmes", "")
        r["gloss_tier"] = g.get("tier", "")
        r["gloss_mode"] = g.get("mode", "transliterated") if g.get("fr") else ""
        r["cohort_en"] = cohorts().get(r.get("cohort", ""), "")
        r["role_descriptor_en"] = descriptors().get(r.get("role_descriptor_ar", ""), "")
    for r in orgs:
        g = gloss(r["name_ar"])
        r["name_fr"], r["name_ijmes"] = g.get("fr", ""), g.get("ijmes", "")
        r["gloss_tier"] = g.get("tier", "")
        r["gloss_mode"] = g.get("mode", "transliterated") if g.get("fr") else ""

    if missing:
        problems.append(f"{len(missing)} names have no gloss, first: "
                        + ", ".join(sorted(set(missing))[:5]))
    if problems:
        for p in problems[:40]:
            print(f"  ! {p}")
        if strict:
            raise SystemExit(f"{len(problems)} problems; nothing written")

    fr = {r["person_id"]: r["name_fr"] for r in persons}
    ij = {r["person_id"]: r["name_ijmes"] for r in persons}
    fr.update({r["org_id"]: r["name_fr"] for r in orgs})
    ij.update({r["org_id"]: r["name_ijmes"] for r in orgs})

    _write(PROCESSED / "persons.csv", PERSON_FIELDS, persons)
    _write(PROCESSED / "organisations.csv", ORG_FIELDS, orgs)

    entries = _read(PROCESSED / "entries.csv")
    for r in entries:
        r["cohort_en"] = cohorts().get(r.get("cohort", ""), "")
        r["role_descriptor_en"] = descriptors().get(r.get("role_descriptor_ar", ""), "")
    # Each gloss sits beside the column it glosses, so the pair reads together.
    entry_fields = list(entries[0])
    for col, after in (("cohort_en", "cohort"),
                       ("role_descriptor_en", "role_descriptor_ar")):
        if col not in entry_fields:
            entry_fields.insert(entry_fields.index(after) + 1, col)
    _write(PROCESSED / "entries.csv", entry_fields, entries)

    n_edges = 0
    for path in sorted((PROCESSED / "edges").glob("*.csv")):
        rows = _read(path)
        for r in rows:
            r["from_fr"], r["from_ijmes"] = fr.get(r["from_id"], ""), ij.get(r["from_id"], "")
            r["to_fr"], r["to_ijmes"] = fr.get(r["to_id"], ""), ij.get(r["to_id"], "")
        _write(path, EDGE_FIELDS, rows)
        if path.name == "all.csv":
            n_edges = len(rows)

    from collections import Counter
    tiers = Counter(r["gloss_tier"] for r in persons + orgs)
    return {
        "glosses": len(table), "persons": len(persons), "organisations": len(orgs),
        "edges": n_edges, "entries": len(entries),
        **{f"tier_{k or 'none'}": v for k, v in sorted(tiers.items())},
        "conventional": sum(1 for e in table.values()
                            if e.get("mode") == "conventional"),
        "translated": sum(1 for e in table.values()
                          if e.get("mode") == "translated"),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lax", action="store_true",
                    help="report gate failures instead of refusing to write")
    args = ap.parse_args(argv)
    for k, v in run(strict=not args.lax).items():
        print(f"  {k:22} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
