"""Generate docs/CODEBOOK-aalam-tunisiyun.md from the data and the config.

Column lists and row counts are read from the tables themselves and the
vocabularies from `config/`, so the codebook cannot drift from the dataset it
describes. A column with no note renders an empty cell rather than an invented
one: a partially documented codebook is honest, a confidently wrong one is not.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path

from .llm import open_text
from .paths import DOCS, PROCESSED, load_config

TABLE_DOCS = {
    "entries.csv": "One row per biographical essay: the 38 subjects, their cohort, "
                   "life dates and page range. The spine of the build.",
    "persons.csv": "Person register. `is_subject` separates the 38 men and women who "
                   "have an essay of their own from the alters merely named inside one.",
    "organisations.csv": "Schools, mosques, courts, ministries, newspapers and societies "
                         "named as the other end of a tie.",
    "edges/all.csv": "Every relational assertion, one row per tie, with the sentence "
                     "that states it.",
    "edges/tutelage.csv": "Who studied under whom, and where. The layer no other build "
                          "in this repository has.",
    "edges/office.csv": "Posts taken up and left.",
    "edges/kinship.csv": "Descent, marriage and affinity.",
    "edges/membership.csv": "Belonging to, founding or heading a body.",
}

COLUMN_NOTES = {
    "entry_uid": "`aalam:<cohort>.<entry>`, e.g. aalam:2.09 for the ninth essay of part two.",
    "cohort": "The author's own generational division: السابقون (predecessors), "
              "التابعون (followers), المعاصرون (contemporaries). Assigned by Zmerli, not by us.",
    "birth_year": "From the entry heading. Empty where the volume itself prints '(... - YYYY)'.",
    "death_year": "From the entry heading.",
    "role_descriptor_ar": "The epithet the author gives the subject beneath the dates, "
                          "e.g. الجندي والمصلح ورجل الدولة. His characterisation, not a coding.",
    "is_subject": "`yes` for the 38 with an essay; `no` for someone named inside one. "
                  "Degrees are not comparable across this line.",
    "name_kind": "`named` where the book gives a name; `described` where it places "
                 "the person only by a relation (ابنة الأصرم, شقيق محمد باي). A "
                 "described node is a real tie to an unidentified person, and two "
                 "such nodes may or may not be the same person. Do not merge them, "
                 "and exclude them before counting a population.",
    "name_translit": "Deterministic lossy ASCII, the input to the identifier. Drops ayn "
                     "and hamza, merges the emphatics, writes no vowels. NOT a "
                     "transliteration and not readable as one: use `name_fr` or "
                     "`name_ijmes`.",
    "name_fr": "Tunisian French orthography (Mohamed Tahar Ben Achour, Bechir Sfar). "
               "The form used in Tunisian archives and the one that joins this build "
               "to the gazette build, whose persons and organisations are all French.",
    "name_ijmes": "Middle East studies convention without diacritics (Muhammad al-Tahir "
                  "Ibn Ashur, al-Bashir Safar).",
    "gloss_tier": "`verified` where the Latin form was checked by hand: the 38 subjects, "
                  "and the institutions and alters with three or more ties. `romanised` "
                  "for the tail, where the consonants are gated but the vowels are a "
                  "reading. `described` where the row is not a name.",
    "gloss_mode": "`transliterated` renders the Arabic and is gated against it consonant "
                  "by consonant. `conventional` marks a body whose own French name is not "
                  "a rendering of its Arabic one (Collège Sadiki for المدرسة الصادقية). "
                  "`translated` marks a common-noun post or a description, where no "
                  "transliteration would mean anything -- do not read one as a proper "
                  "name.",
    "cohort_en": "The three cohorts in English. Zmerli's judgement, not an attribute of "
                 "the people.",
    "role_descriptor_en": "`role_descriptor_ar` in English. Five of the 38 are an OCR "
                          "failure that captured a sentence instead of the subtitle; the "
                          "English says what the fragment says rather than repairing it.",
    "from_fr": "`from_name` in Tunisian French orthography.",
    "from_ijmes": "`from_name` in the Middle East studies convention.",
    "to_fr": "`to_name` in Tunisian French orthography.",
    "to_ijmes": "`to_name` in the Middle East studies convention.",
    "org_kind": "What the body is: school, mosque, newspaper, association, party, court, "
                "office, work, or `org` where the volume does not say. `office` is a post "
                "rather than a body people meet in, and `work` is a published title.",
    "person_id": "`PERSON_<SURNAME>_<GIVEN>`, from the identity key only. Titles are "
                 "stripped, so الجنرال خير الدين and خير الدين باشا are one person.",
    "rank": "A title carried in the name (pasha, bey, agha, general). Stripped from the "
            "identifier, kept here as evidence of standing.",
    "layer": "One of tutelage, office, kinship, membership.",
    "relation": "The directed relation; see the controlled vocabulary below.",
    "subjects_studied": "For a tutelage tie, the subjects named as read with the teacher "
                        "(الفقه, النحو …), pipe-separated.",
    "year": "A single year where the sentence states one.",
    "year_lo": "Lower bound of the interval the sentence supports.",
    "year_hi": "Upper bound of the interval the sentence supports.",
    "date_precision": "`year`, `year_range`, or `none`. `none` means the source states the "
                      "tie without placing it in time -- not that the date is merely missing.",
    "evidence_tier": "Always `book_stated`. Everything here is one author's account; "
                     "nothing is confirmed against a document.",
    "extractor": "`rule` for the cue table, `llm` for the model pass. Both are gated on "
                 "the quote check; kept apart so either can be excluded from a result.",
    "pattern_id": "The cue that fired, or the model prompt version.",
    "evidence_quote": "The sentence, verbatim from the OCR. Every row is checked against "
                      "its entry by `aalam.validate`; a row that cannot be quoted is dropped.",
    "ocr_config": "The engine flags. Pinned per page so a re-OCR shows up as a diff.",
    "arabic_char_frac": "Share of Arabic characters. A low value marks a plate or a blank.",
    "needs_review": "Set where something did not reconcile. Never silently corrected.",
}


def _table_section(path: Path, label: str) -> list[str]:
    if not path.exists():
        return []
    with open_text(path) as fh:
        reader = csv.DictReader(fh)
        cols = reader.fieldnames or []
        n = sum(1 for _ in reader)
    out = [f"### `{label}`", "", f"{n:,} rows. {TABLE_DOCS.get(label, '')}", "",
           "| column | note |", "|---|---|"]
    out += [f"| `{c}` | {COLUMN_NOTES.get(c, '')} |" for c in cols]
    out.append("")
    return out


def build() -> Path:
    scope = load_config("aalam_scope")
    rel = load_config("aalam_vocab_relations")
    vol = scope["volume"]

    out = [
        "# Codebook — A'lam Tunisiyun", "",
        f"Generated {date.today().isoformat()} by `python -m aalam.codebook`. "
        "Do not edit by hand: column lists and counts are read from the data and "
        "vocabularies from `config/`, so this file cannot drift from the dataset.", "",
        "## Source", "",
        f"*{vol['title_ar']}* ({vol['title_translit']}), {vol['author_translit']}, "
        f"{vol['publisher_translit']}, {vol['place']}, {vol['pub_year']}. "
        f"{vol['n_pdf_pages']} pages, Arabic.", "",
        "38 biographical essays in three parts, which the author calls the "
        "predecessors, the followers and the contemporaries. The subjects span "
        f"{scope['window']['start_year']}-{scope['window']['end_year']}.", "",
        "The volume has no text layer: every page is a bilevel scan, and the text "
        "here was produced by OCR whose settings are recorded per page in "
        "`data/raw/aalam/manifest.csv`. The scan is not redistributed; the manifest "
        "carries a sha256 per page so it can be rebuilt and checked.", "",
        "## How to read a date", "",
        "A biography states a relation far more often than it dates one. Where the "
        "sentence gives a year, `year` holds it and `date_precision` is `year`. Where "
        "it gives a span, `year_lo`/`year_hi` bound it and precision is `year_range`. "
        "Where it gives neither, precision is `none`.", "",
        "`none` is a statement about the source, not a gap to be imputed: the book "
        "asserts that the tie existed without saying when. Treating those rows as "
        "contemporaneous with anything else is a modelling choice the data does not "
        "support.", "",
        "## Tables", "",
    ]
    out += _table_section(PROCESSED / "entries.csv", "entries.csv")
    out += _table_section(PROCESSED / "persons.csv", "persons.csv")
    out += _table_section(PROCESSED / "organisations.csv", "organisations.csv")
    for name in ("all", "tutelage", "office", "kinship", "membership"):
        out += _table_section(PROCESSED / "edges" / f"{name}.csv", f"edges/{name}.csv")

    out += ["## Controlled vocabularies", "", "### `layer`", "",
            "| value | meaning |", "|---|---|"]
    out += [f"| `{k}` | {v} |" for k, v in rel["layers"].items()]
    out += ["", "### `relation`", "", "| value | meaning |", "|---|---|"]
    out += [f"| `{k}` | {v} |" for k, v in rel["relation_types"].items()]
    out += ["", "### Cue bindings", "",
            "The rule pass emits only cues bound by a preposition or a possessive "
            "pronoun. Arabic is verb-subject-object, so a bare verb is followed by the "
            "clause's subject, and a pattern cannot tell that from the counterparty. "
            "Cues marked `vso` in `config/aalam_vocab_relations.yaml` are left to the "
            "model pass.", ""]

    edges = PROCESSED / "edges" / "all.csv"
    if edges.exists():
        with open_text(edges) as fh:
            rows = list(csv.DictReader(fh))
        from collections import Counter
        out += ["## Observed distributions", "", "### Edges by relation", "",
                "| relation | n |", "|---|---|"]
        out += [f"| `{k}` | {v} |" for k, v in Counter(r["relation"] for r in rows).most_common()]
        out += ["", "### Edges by layer", "", "| layer | n |", "|---|---|"]
        out += [f"| `{k}` | {v} |" for k, v in Counter(r["layer"] for r in rows).most_common()]
        out.append("")

    path = DOCS / "CODEBOOK-aalam-tunisiyun.md"
    path.write_text("\n".join(out), encoding="utf-8")
    return path


def main(argv=None) -> int:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    print(f"  wrote {build()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
