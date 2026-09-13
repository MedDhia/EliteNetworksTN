"""Who, among the directors in this corpus, is recorded as a woman.

The dataset carries no gender variable, and there are two ways to add one. The
usual way is to guess from the given name against a name-gender dictionary.
That is not done here. Tunisian names reach these filings transliterated into
French by whoever typed the table, with no settled orthography - Mohamed,
Mohammed, Muhammad, Mohamad - and the dictionaries that cover them well are
built on French or Anglophone populations. The errors such a list makes are not
random: they fall hardest on the least European-looking names, which is exactly
the wrong bias for a study of a Tunisian elite.

The other way is to use what the filer wrote down. French corporate filings
print an honorific before a director's name - M., Mme, Mlle - and the extractor
keeps it in ``member_title``. That is a *recorded* marker rather than an
inference from the name, so where it exists it is close to ground truth, and
where it does not exist the person is **unknown** rather than guessed.

The price is coverage: about two thirds of board rows print no honorific, and
a third of directors are never seen with one. That is a large unknown group and
it must not be folded into "men" - doing so would understate women by
construction. Every count this module produces is therefore reported against
the *gendered* denominator, with the unknown share carried alongside it.

Run with::

    PYTHONPATH=src python -m bourse.gender

Writes data/processed/bourse/director_gender.csv.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict

from .common import PROCESSED, log, read_jsonl

RECORDS = PROCESSED / "records"
OUT = PROCESSED / "director_gender.csv"

# Honorifics as they survive extraction: lower-cased, trailing period stripped.
# "Mlle" is included because it appears, not because the distinction between
# it and "Mme" is wanted - both record the same thing for this purpose.
FEMALE = {"mme", "mmes", "madame", "mesdames", "mlle", "mlles", "mademoiselle",
          "mrs", "ms", "miss"}
MALE = {"m", "mr", "mrs.", "monsieur", "messieurs", "mm", "sir"}
# "mrs." would normalise to "mrs" and is female; guard against a typo in the
# set above by removing anything that appears in both.
MALE = MALE - FEMALE

# Fields that can carry a person's name, paired with the field carrying the
# honorific for that name. Only `board` records keep a separate title column;
# the others are searched for an inline honorific instead.
NAME_FIELD = "member_name_raw"
TITLE_FIELD = "member_title"


def normalise_title(raw: str | None) -> str:
    return (raw or "").strip().lower().rstrip(".").strip()


def classify_title(raw: str | None) -> str | None:
    """'F', 'M', or None for a title that records no gender."""
    t = normalise_title(raw)
    if t in FEMALE:
        return "F"
    if t in MALE:
        return "M"
    return None


def collect(resolver) -> dict[str, Counter]:
    """Honorifics seen for each resolved person, across the whole corpus.

    Collected per *person* rather than per row, because a director who is
    styled "Mme" in one filing and given no title in ten others is still
    recorded as a woman. This is what lifts coverage from a third of rows to a
    third of people.
    """
    seen: dict[str, Counter] = defaultdict(Counter)
    path = RECORDS / "board.jsonl.gz"
    if not path.exists():
        log.warning("no board records at %s", path)
        return seen
    for rec in read_jsonl(path):
        if rec.get("member_is_legal_person"):
            continue
        name = (rec.get(NAME_FIELD) or "").strip()
        if not name:
            continue
        eid, etype = resolver.resolve(name, hint="person")
        if not eid or etype != "person":
            continue
        g = classify_title(rec.get(TITLE_FIELD))
        seen[eid][g or "?"] += 1
    return seen


def decide(counts: Counter) -> tuple[str, str]:
    """(gender, basis) for one person's observed honorifics.

    A person styled both ways is left unknown rather than decided by majority.
    Two people in this corpus are, and both are cases where one filing's title
    column is offset by a row - a data fault, not a close call, and guessing
    between them would bury it.
    """
    f, m = counts["F"], counts["M"]
    if f and m:
        return "unknown", "conflicting honorifics"
    if f:
        return "F", f"{f} female honorific{'s' if f > 1 else ''}"
    if m:
        return "M", f"{m} male honorific{'s' if m > 1 else ''}"
    return "unknown", "no honorific printed"


FIELDS = ["entity_id", "canonical_name", "gender", "basis",
          "n_female_titles", "n_male_titles", "n_untitled_rows"]


def build(resolver) -> list[dict]:
    rows = []
    for eid, counts in collect(resolver).items():
        gender, basis = decide(counts)
        rows.append({
            "entity_id": eid,
            "canonical_name": resolver.canonical_name(eid),
            "gender": gender,
            "basis": basis,
            "n_female_titles": counts["F"],
            "n_male_titles": counts["M"],
            "n_untitled_rows": counts["?"],
        })
    rows.sort(key=lambda r: (r["gender"], r["canonical_name"]))
    return rows


def load() -> dict[str, str]:
    """entity_id -> 'F' | 'M', omitting everyone left unknown."""
    if not OUT.exists():
        return {}
    with OUT.open(encoding="utf-8") as fh:
        return {r["entity_id"]: r["gender"] for r in csv.DictReader(fh)
                if r["gender"] in ("F", "M")}


def main() -> None:
    from .build_dataset import seed_evidence
    from .entities import Resolver

    res = Resolver()
    seed_evidence(res)
    rows = build(res)

    with OUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    n = len(rows)
    by = Counter(r["gender"] for r in rows)
    gendered = by["F"] + by["M"]
    log.info("%-38s %6d rows", OUT.name, n)
    log.info("  directors seen on a board:      %5d", n)
    log.info("  recorded by an honorific:       %5d (%.1f%%)", gendered,
             100 * gendered / max(n, 1))
    log.info("  of those, women:                %5d (%.1f%%)", by["F"],
             100 * by["F"] / max(gendered, 1))
    log.info("  left unknown:                   %5d (%.1f%%)", by["unknown"],
             100 * by["unknown"] / max(n, 1))
    conflicts = sum(1 for r in rows if r["basis"] == "conflicting honorifics")
    if conflicts:
        log.info("  conflicting honorifics:         %5d", conflicts)


if __name__ == "__main__":
    main()
