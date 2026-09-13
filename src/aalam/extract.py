"""Stage 3: read relational assertions out of the entry text.

The book is narrative prose, so a tie is a sentence, not a field:
«وارتبط من أول وهلة بشيخها الطاهر بن مسعود وقرأ عليه الفقه والنحو» states a
pedagogical tie, its direction, the subjects read, and the institution, in one
clause. Two passes read it.

The **rule pass** here matches the cue table in
``config/aalam_vocab_relations.yaml`` against clause-sized spans. It is
deliberately high-precision and low-recall: it fires only where the book uses
one of the stock formulas.

The **model pass** (``aalam.llm``) covers the paraphrases, and is gated: every
assertion it returns must quote the text verbatim, and ``aalam.validate``
rejects any quote that is not literally present in its entry. A tie the source
does not state cannot survive that check, which is what makes the pass
defensible in a methods appendix rather than a leap of faith.

Finding a person in Arabic is the hard part, since there is no capitalisation
to lean on. Three anchors do the work, in descending order of confidence:
an honorific (الشيخ، الجنرال); a nasab particle (بن X); and a gazetteer built
from the volume's own table of contents.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from hashlib import blake2b

from .names_ar import fold, org_id, parse_person, person_id, strip_article
from .paths import CONFIG, INTERIM, PROCESSED, ensure_dirs, load_config
from .textnorm_ar import arabic_only, fold_pattern

ASSERTION_FIELDS = [
    "assertion_id", "entry_uid", "subject_id", "subject_name",
    "relation", "layer", "counterparty_id", "counterparty_name",
    "counterparty_kind", "subjects_studied", "org_mention",
    "year", "year_lo", "year_hi", "date_precision",
    "extractor", "pattern_id", "confidence", "evidence_quote", "char_offset",
    "needs_review",
]

# Clause boundaries. The Arabic comma and full stop do most of the work; the
# conjunction waw does not end a clause and must not be treated as one.
_CLAUSE = re.compile(r"[.،؛:؟!\n]+")
_WS = re.compile(r"\s+")
_YEAR = re.compile(r"\b(1[0-9]{3}|20[0-2][0-9])\b")

# Tokens that end a name span: prepositions, conjunctions and verbs cannot be
# part of the name they follow.
_NAME_STOP = {
    "في", "من", "إلى", "على", "عن", "مع", "بعد", "قبل", "عند", "لدى", "حتى",
    "الذي", "التي", "ثم", "قد", "كان", "كانت", "لم", "لا",
    "أن", "إن", "أنه", "له", "به", "بها", "هذا", "هذه", "ذلك",
    "أو", "بل", "لكن", "غير", "سنة", "عام", "بين", "خلال", "إثر", "نحو", "،",
    "إلا", "الا", "أن", "ان", "إذ", "اذ", "كما", "حين", "عندما", "الملك",
    "الجديد", "يعرب", "الأكبر", "الأصغر", "منه", "عنه", "إليه", "اليه",
    # Relational nouns. These are the cue words themselves -- "his shaykh",
    # "his pupil" -- and naming one is not naming a person, so a span that
    # begins on one would carry the cue into the name it is meant to find.
    "شيخه", "شيخها", "تلميذه", "أستاذه", "والده", "أبوه", "ابنه", "نجله",
    "أخوه", "شقيقه", "صهره", "عمه", "خاله", "حفيده", "زوجته", "زوجه",
    # Adjectives that commonly trail a name and are not part of it.
    "المشهور", "المعروف", "الشهير", "الكبير", "الأكبر", "المرحوم", "العظيم",
    "الأول", "الثاني", "الثالث", "الخامس", "الرابع",
}

# A token carrying the conjunction waw is almost never part of the name that
# precedes it: in «الطاهر بن مسعود وقرأ عليه» the verb would otherwise be
# swallowed into the shaykh's name. The cost is that a name genuinely opening
# with waw is missed, which in this volume does not occur.
_WAW_PREFIXED = re.compile(r"^و.")

# Arabic is written without spaces around its clitics, so a cue matched as a
# bare substring fires inside unrelated words: "ألف" (he authored) is a
# substring of "الفقه" (jurisprudence), which turned one man's reading list
# into a claim that he wrote a book. A cue must therefore end at a word
# boundary -- but attached object pronouns are part of the word, and the
# commonest form of the tutelage cue is "قرأ عليه", so those are allowed to
# follow. On the left the proclitics و ف ب ل ك are permitted, since "وقرأ" is
# the same verb as "قرأ".
_SUFFIX = r"(?:ها|هما|هم|هن|كم|نا|ه|ك|ني)?"
# An object pronoun on the cue is anaphoric: «بشيخها الطاهر بن مسعود وقرأ
# عليه» names the shaykh first and then refers back to him. So a cue that ends
# in one points backwards, and looking only forwards for the counterparty
# discards the very name the sentence is about.
_ANAPHORIC = re.compile(r"(?:ها|هما|هم|هن|ه)$")
_LEFT = r"(?:(?<![؀-ۿ])|(?<=[وفبلك]))"
_RIGHT = r"(?![؀-ۿ])"


def _bounded(pattern: str) -> str:
    return f"{_LEFT}(?:{pattern}){_SUFFIX}{_RIGHT}"


# Quotation marks around a cited title are stripped by folding, which let the
# title run on into the name before it ("الشيخ أحمد الأبي «البيان»"). They are
# mapped to an Arabic comma first, which survives folding and blocks the span.
_QUOTES = re.compile('[\u00ab\u00bb\u201c\u201d"\u2018\u2019\']')


# Bindings the rule pass can resolve. A bare verb cannot be, because Arabic
# word order puts the clause's subject after it; see the header note in
# config/aalam_vocab_relations.yaml.
RULE_BINDINGS = {"prepositional", "possessive"}


def _load_cues(bindings: set[str] | None = None) -> list[dict]:
    cfg = load_config("aalam_vocab_relations")
    allowed = RULE_BINDINGS if bindings is None else bindings
    out = []
    for layer, cues in cfg["cues"].items():
        for c in cues:
            if c.get("binding", "vso") not in allowed:
                continue
            out.append({
                "layer": layer, "id": c["id"], "relation": c["relation"],
                "direction": c["direction"], "binding": c.get("binding", "vso"),
                # Cues are written as the book prints them and matched against
                # folded text, so the pattern must be folded the same way, and
                # bounded so it cannot fire inside a longer word.
                "re": re.compile(_bounded(fold_pattern(c["re"]))),
            })
    return out


def _load_subjects_vocab() -> list[str]:
    return [fold(s) for s in load_config("aalam_vocab_relations")["subjects"]]


def load_gazetteer() -> dict[str, str]:
    """Folded name -> display name, seeded from the volume's own contents.

    The 38 subjects are the only names the book guarantees are people. Every
    other name is discovered in text, so seeding from the table of contents
    gives the matcher a floor it can trust.
    """
    gaz: dict[str, str] = {}
    with (CONFIG / "aalam_entries.csv").open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            name = row["name_ar"]
            p = parse_person(name)
            if p.is_empty:
                continue
            gaz[p.match_key] = name
            # The surname alone is how the book refers back to a man after
            # introducing him, so it has to match too.
            if len(p.match_tokens) > 1:
                gaz.setdefault(p.surname_key, name)
    return gaz


def _honorific_set() -> set[str]:
    """Every title, of either kind. All of them terminate a name span."""
    cfg = load_config("aalam_name_variants")
    return {fold(h) for h in cfg["honorifics"]}


def _prenominal_set() -> set[str]:
    """Titles that introduce the name after them, so they can anchor a span.

    Post-nominal titles are excluded: مصطفى باي is Mustafa Bey, and anchoring
    forward on باي reads the words after the title as though they were a name.
    """
    cfg = load_config("aalam_name_variants")
    post = {fold(h) for h in cfg.get("postnominal") or []}
    return {fold(h) for h in cfg["honorifics"]} - post


def find_persons(clause: str, gazetteer: dict[str, str]) -> list[tuple[str, str, int]]:
    """Locate person mentions in a clause: (display, folded_key, offset).

    Three anchors, tried in order and deduplicated by offset:

    1. an honorific -- الشيخ أحمد الأبي -- which in this book almost always
       introduces a named man;
    2. a nasab particle -- بن مسعود -- taking the token before it when that
       token is itself a name-shaped word;
    3. the gazetteer, which catches later references by surname alone.

    Spans stop at a preposition, conjunction or verb, because a name cannot
    continue through one. Without that guard ``قرأ على الشيخ أحمد الأبي البيان``
    swallows the book title into the name.
    """
    folded = fold(_QUOTES.sub(" ، ", clause))
    tokens = folded.split(" ")
    # Offsets of each token within the folded clause, so a quote can be sliced.
    offsets, pos = [], 0
    for t in tokens:
        offsets.append(pos)
        pos += len(t) + 1

    hon = _honorific_set()
    anchors = _prenominal_set()
    found: dict[int, tuple[str, str]] = {}

    def span_from(i: int, maxlen: int = 3) -> int:
        """Index one past the last token of a name starting at i."""
        j = i
        while j < len(tokens) and j - i < maxlen:
            tok = tokens[j]
            if not tok or tok in _NAME_STOP or tok in hon:
                break
            if j > i and _WAW_PREFIXED.match(tok):
                break
            j += 1
        return j

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in anchors:
            j = span_from(i + 1)
            if j > i + 1:
                name = " ".join(tokens[i + 1:j])
                found[offsets[i + 1]] = (name, name)
                i = j
                continue
        i += 1

    # Nasab: a particle joins the name before it to the name after it.
    for idx, tok in enumerate(tokens):
        if tok in {"بن", "ابن"} and 0 < idx < len(tokens) - 1:
            start = idx - 1
            end = span_from(idx + 1, maxlen=2)
            if end > idx + 1 and tokens[start] not in _NAME_STOP:
                name = " ".join(tokens[start:end])
                found.setdefault(offsets[start], (name, name))

    for key, display in gazetteer.items():
        for m in re.finditer(rf"(?<![؀-ۿ]){re.escape(key)}(?![؀-ۿ])", folded):
            found.setdefault(m.start(), (display, key))

    return [(d, fold(k), off) for off, (d, k) in sorted(found.items())]


def _plausible_name(display: str, gazetteer: dict[str, str]) -> bool:
    """Reject spans that are grammar rather than a name.

    A single unknown token is far more often a common noun that happened to
    follow a cue than it is a person, so a lone token has to be one the volume
    has already introduced. Anything carrying a stop word is not a name at all.
    """
    tokens = [t for t in fold(display).split(" ") if t]
    if not tokens or any(t in _NAME_STOP for t in tokens):
        return False
    if len(tokens) == 1:
        # Gazetteer keys are article-stripped, because the book writes both
        # "الورداني" and "الوردانيّ ..." and the article is not part of the name.
        return strip_article(tokens[0]) in gazetteer or tokens[0] in gazetteer
    return True


def _clauses(text: str) -> list[tuple[str, int]]:
    """Split into clause-sized spans, keeping each one's offset in the entry.

    Clause-sized rather than sentence-sized for the reason the multiplex
    extractor gives: an action in one clause must not be attributed to a person
    named in the next.
    """
    out, pos = [], 0
    for part in _CLAUSE.split(text):
        stripped = part.strip()
        if stripped:
            off = text.find(stripped, pos)
            out.append((stripped, off if off >= 0 else pos))
            pos = (off if off >= 0 else pos) + len(stripped)
    return out


def _years(clause: str) -> tuple[str, str, str, str]:
    """Years stated in a clause, as a value plus an interval and a precision."""
    found = [int(y) for y in _YEAR.findall(clause)]
    if not found:
        return "", "", "", "none"
    if len(found) == 1:
        y = found[0]
        return str(y), f"{y}-01-01", f"{y}-12-31", "year"
    lo, hi = min(found), max(found)
    return "", f"{lo}-01-01", f"{hi}-12-31", "year_range"


def _assertion_id(*parts: str) -> str:
    return "AS_" + blake2b("|".join(parts).encode("utf-8"), digest_size=10).hexdigest()


def extract_entry(entry: dict, cues: list[dict], gazetteer: dict[str, str],
                  subjects_vocab: list[str]) -> list[dict]:
    """Apply the cue table to one entry, returning assertion rows."""
    uid = entry["entry_uid"]
    subject_name = entry["name_ar"]
    subject = person_id(subject_name)
    text = entry["text"]
    rows: list[dict] = []
    seen: set[tuple] = set()

    for clause, offset in _clauses(text):
        folded = fold(clause)
        persons = find_persons(clause, gazetteer)
        year, lo, hi, precision = _years(clause)
        studied = [s for s in subjects_vocab if s in folded]

        for cue in cues:
            m = cue["re"].search(folded)
            if not m:
                continue
            before = [p for p in persons if p[2] < m.start()]
            after = [p for p in persons if p[2] >= m.start()]
            others_before = [p for p in before if fold(p[0]) != fold(subject_name)]

            # Where the counterparty sits relative to the cue is a property of
            # the construction, and getting it wrong is how a rule pass invents
            # ties.
            if cue["binding"] == "possessive":
                # «والده الجنرال خير الدين» -- the name follows the possessive.
                # The pronoun's referent must be the entry's subject for the
                # tie to be his, so if someone else has already been named the
                # possessive attaches to them instead: in «ارتقى الأمير مصطفى
                # باي خلفاً لشقيقه حسين باي» the brother is Mustafa's, not the
                # subject's. Left to the model pass rather than guessed at.
                if others_before:
                    continue
                pool = after
            elif _ANAPHORIC.search(m.group(0)):
                # «بشيخها الطاهر بن مسعود وقرأ عليه» -- the pronoun refers back,
                # so the counterparty is the last name already given.
                pool = list(reversed(before)) or after
            else:
                # «قرأ على الشيخ أحمد الأبي» -- the object of the preposition
                # follows it.
                if others_before:
                    continue
                pool = after
            if not pool:
                continue
            display, key, _ = pool[0]
            if fold(display) == fold(subject_name):
                continue  # a man is not his own teacher
            if not _plausible_name(display, gazetteer):
                continue

            cp_id = person_id(display)
            if cp_id == "PERSON_UNKNOWN":
                continue
            dedup = (uid, cue["relation"], cp_id, year)
            if dedup in seen:
                continue
            seen.add(dedup)

            quote = _WS.sub(" ", clause)[:240]
            rows.append({
                "assertion_id": _assertion_id(uid, cue["relation"], subject, cp_id, year),
                "entry_uid": uid,
                "subject_id": subject, "subject_name": subject_name,
                "relation": cue["relation"], "layer": cue["layer"],
                "counterparty_id": cp_id, "counterparty_name": display,
                "counterparty_kind": "person",
                "subjects_studied": "|".join(studied),
                "org_mention": "",
                "year": year, "year_lo": lo, "year_hi": hi,
                "date_precision": precision,
                "extractor": "rule", "pattern_id": cue["id"],
                "confidence": "0.85" if cue["binding"] == "prepositional" else "0.75",
                "evidence_quote": quote,
                "char_offset": offset,
                "needs_review": "",
            })
    return rows


def run(limit: int | None = None) -> dict[str, int]:
    ensure_dirs()
    src = INTERIM / "entry_texts.jsonl"
    if not src.exists():
        raise SystemExit("data/interim/aalam/entry_texts.jsonl missing. Run `make aalam-segment`.")

    meta = {}
    with (PROCESSED / "entries.csv").open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            meta[row["entry_uid"]] = row

    cues = _load_cues()
    gaz = load_gazetteer()
    vocab = _load_subjects_vocab()

    rows: list[dict] = []
    with src.open(encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if limit is not None and i >= limit:
                break
            rec = json.loads(line)
            entry = dict(meta[rec["entry_uid"]])
            entry["text"] = rec["text"]
            rows.extend(extract_entry(entry, cues, gaz, vocab))

    rows.sort(key=lambda r: (r["entry_uid"], r["char_offset"], r["assertion_id"]))
    out = INTERIM / "assertions_rule.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps({k: r.get(k, "") for k in ASSERTION_FIELDS},
                                ensure_ascii=False) + "\n")

    stats = {"assertions": len(rows), "entries": len(meta)}
    from collections import Counter
    for layer, n in sorted(Counter(r["layer"] for r in rows).items()):
        stats[f"layer_{layer}"] = n
    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=None, help="only the first N entries")
    args = ap.parse_args(argv)
    for k, v in run(limit=args.limit).items():
        print(f"  {k:22} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
