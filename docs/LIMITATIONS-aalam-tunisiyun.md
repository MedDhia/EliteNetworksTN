# Limitations — A'lam Tunisiyun

What this dataset cannot support, stated plainly. Every figure here is
measured; the counts come from `docs/VALIDATION-aalam-tunisiyun.md` and the
tables themselves.

## 1. Coverage is partial, and the gap is the whole point of the number

**The model pass has been run on 3 of the 38 entries** — aalam:1.09
(Khayr al-Din), aalam:2.02 (Bashir Sfar), aalam:3.12 (Muhammad al-Tahir ibn
Ashur) — covering **40,522 of 426,269 characters, or 9.5% of the text**. The
rule pass runs over all 38, but it is confined by design to constructions it
can resolve (§3) and yields 7 assertions in total.

So the 33 edges in this build are **a demonstration that the pipeline works,
not a census of the book's relational content**. Nothing here supports a claim
about how connected anyone was. A degree of 6 means six ties were extracted,
not six ties existed. The remaining 35 entries are not empty in the source;
they are unread by the model pass.

Running the model pass over the other 35 entries is the single change that
would make this a dataset rather than a worked example.

## 2. Subjects and alters are not the same kind of node

38 people have an essay to themselves. The other 10 appear because Zmerli
happened to name them. `is_subject` separates them and **degree is not
comparable across that line**: a subject's ties reflect what an author chose to
write about a life, an alter's reflect a passing mention. Pooling them and
ranking by degree measures the author's attention, not anyone's position.

The alters are also not a sample of anything. They are who a nationalist
intellectual writing in the mid-twentieth century thought worth naming.

## 3. The rule pass reads only two grammatical constructions

Arabic is verb-subject-object. In «ارتقى الأمير مصطفى باي إلى العرش» the name
after the verb is the man ascending — the clause's *subject*. A pattern cannot
tell that from a counterparty, and an earlier version of this extractor, which
tried, attributed the Bey's accession to his court chaplain and made Yusuf
Sahib al-Tabi the son of Hammuda Pasha.

The rule pass therefore fires only where the grammar binds the counterparty:
after a preposition («قرأ على الشيخ أحمد الأبي») or a possessive pronoun
(«والده الجنرال خير الدين»), and in the possessive case only when no one else
has been named first, since «شقيقه» after «الأمير مصطفى باي» is Mustafa's
brother and not the subject's. Cues marked `vso` in
`config/aalam_vocab_relations.yaml` are recorded but never emitted. This buys
precision at a large cost in recall, and the cost is real: most of what the
book asserts is carried by exactly the sentences the rule pass declines to read.

## 4. Precision and recall are not yet measured

There is **no gold-standard score for this build**. The seven rule assertions
were checked by hand against the printed pages and all seven are correct, but
seven is not a sample and 7/7 is not an estimate. The regression tests in
`tests/test_extract_aalam.py` encode specific defects found and fixed; they
are not a measurement either.

Until a stratified sample is drawn and coded, **treat every count here as a
lower bound of unknown tightness**. Do not publish a precision figure for this
build, because there is not one.

## 5. What the quote gate does and does not guarantee

Every one of the 33 edges quotes its entry verbatim, checked on all rows
rather than a sample (`aalam.validate`). That guarantees the sentence exists
and says roughly what the row claims. It does **not** guarantee the row reads
the sentence correctly: a quote can be real while the relation drawn from it
is wrong, the direction reversed, or the wrong person picked out of it. The
gate catches fabrication. It does not catch misreading, and only §4 would.

## 6. Text quality

The volume has no text layer; all 455,131 characters come from OCR. Body text
is clean — proper names, which are what the extractor needs, come through
correct. Two known problems:

- **Headings are display type and OCR badly.** 15 of 38 headings disagree with
  the printed contents list or could not be read at all («محمد الأميسن
  الشسابسى» for al-Shabbi). The contents list is authoritative for names and
  page ranges throughout; headings are used only to check it, and the
  disagreements are recorded in `entries.csv`, not silently resolved.
- **One page (p384, the back cover) was abandoned on a time limit.** It carries
  no biographical text.

Counterparty names discovered in text are stored in their folded form
(«احمد الابي» rather than «أحمد الأبي»); the identifier is unaffected and the
evidence quote preserves the printed orthography.

## 7. One author, one account, mid-century

Everything here is `evidence_tier = book_stated`. Nothing is confirmed against
a document, and the gazette build in this repository does not reach back far
enough to confirm any of it. Zmerli wrote about a milieu he belonged to; his
selection of 38 subjects, his cohort divisions, and his epithets
(`role_descriptor_ar`) are his judgements and are recorded as such rather than
as attributes of the people.

The Arabic text is itself a translation: Zmerli wrote in French, and this
volume is Hammadi Sahli's Arabic rendering. Quotations are therefore evidence
of what the translation says, one remove from what the author wrote.

## 8. Dates

**26 of 33 edges carry no date at all.** A biography states that a relation
existed far more often than it says when. `date_precision = none` means the
source never placed the tie in time — it is not a missing value to impute, and
these edges cannot be assembled into a panel or replayed as a dynamic network.
Only the seven dated edges support anything temporal, and that is too few for
any such use.

## 9. Reproducibility

The scan is not redistributed. `data/raw/aalam/manifest.csv` carries a sha256
per page and pins the OCR engine, version and flags, so a re-OCR appears as a
diff rather than silently changing the text. The per-page OCR output is
committed, so the tables rebuild without an OCR engine installed and the quote
gate runs in CI on every row.

The model pass is committed as a record
(`data/processed/aalam-tunisiyun/records/assertions_model.jsonl.gz`), not
regenerated per build. Everything downstream of it is deterministic, so the
tables rebuild byte-identically and re-running the model is a reviewable diff.
The corollary is that those 26 assertions are **not reproducible from the
source by a third party** in the way the rule pass is: they can be checked
against the text, which is what the gate does, but not independently
regenerated.
