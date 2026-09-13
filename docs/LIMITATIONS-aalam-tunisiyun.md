# Limitations — A'lam Tunisiyun

What this dataset cannot support, stated plainly. Every figure here is
measured; the counts come from `docs/VALIDATION-aalam-tunisiyun.md` and the
tables themselves.

## 1. Precision and recall are not measured

There is **no gold-standard score for this build**. All 38 entries have now
been read and the tables carry 873 ties, but nobody has drawn a stratified
sample and coded it against the printed pages, so there is no precision
figure and no recall figure.

What exists instead is weaker and should not be mistaken for it: every row
quotes its entry verbatim (§4), the seven rule-pass ties were checked by hand
and are correct, and a spot-check of twelve model-pass rows found one error
class, described in §5. Seven correct ties and one audited class are not an
estimate.

**Treat every count here as a lower bound of unknown tightness, and do not
publish a precision figure for this build, because there is not one.** Drawing
that sample is the single change that would most improve what can be claimed.

## 2. Subjects and alters are not the same kind of node

38 people have an essay to themselves. The other 204 appear because Zmerli
happened to name them. `is_subject` separates them and **degree is not
comparable across that line**: a subject's ties reflect what an author chose to
write about a life, an alter's reflect a passing mention. Pooling them and
ranking by degree measures the author's attention, not anyone's position.

The alters are also not a sample of anything. They are who a nationalist
intellectual writing in the mid-twentieth century thought worth naming. Of the
38 subjects, 28 are tied to at least one other subject, across 56 ties; the
remaining 10 connect only outward.

**11 person nodes are not named at all.** The book places them by a relation
only — ابنة الأصرم, شقيق محمد باي خير الدين, زوجته الثانية القيروانية. They
carry `name_kind = described`. The tie is real, but the person is not
identified, and two such nodes may or may not be the same person with no way
to tell. Exclude them before counting a population, and never merge two of
them on similarity.

## 3. Where the ties come from, and what that costs

866 of 873 ties come from the model pass; 7 from the rule pass. That split is
not an accident of effort, it is a property of the language.

Arabic is verb-subject-object. In «ارتقى الأمير مصطفى باي إلى العرش» the name
after the verb is the man ascending — the clause's *subject*. A pattern cannot
tell that from a counterparty, and an earlier version of the rule extractor,
which tried, attributed the Bey's accession to his court chaplain and made
Yusuf Sahib al-Tabi the son of Hammuda Pasha. The rule pass was therefore
confined to constructions whose grammar binds the counterparty — after a
preposition, or after a possessive pronoun with nobody else named first — and
that leaves it able to read almost nothing. Cues marked `vso` in
`config/aalam_vocab_relations.yaml` are recorded and never fired.

The consequence: **this dataset rests on a model reading Arabic prose, with the
guards in §4 and §5 as the check on it.** It is not reproducible from the
source by a third party the way the rule pass is. The assertions are committed
as a record so they can be audited against the text and so the tables rebuild
deterministically, but re-deriving them requires re-running a model.

## 4. What the quote gate guarantees, and what it does not

Every one of the 873 edges quotes its entry verbatim, checked on all rows
rather than a sample (`aalam.validate`). That guarantees the sentence exists
and says roughly what the row claims. A fabricated tie has no sentence to
quote and cannot survive.

It does **not** guarantee the row reads the sentence correctly. A quote can be
real while the relation drawn from it is wrong, the direction reversed, or the
wrong person picked out of it. The gate catches invention. It does not catch
misreading — and §5 is what misreading looks like.

## 5. The error class the gate is blind to

The book names what a man studied by naming its authors, in a list:
«الأشعري وابن سينا والزمخشري والغزالي وابن رشد، قد استأثروا بعنايته»,
«والرصافي وخليل مطران وحافظ إبراهيم». Read as teaching ties, these put a man
born in 1871 in the classroom of a scholar dead in 1198, and a Tunisian judge
in the classroom of three poets he never met. Every quote is genuine; only the
reading is wrong.

Ten such ties reached the first pass — at the time, 12% of the whole tutelage
layer. `config/aalam_authors_read.yaml` now lists the authors this happens
with, the pipeline rewrites the tie to `read_work_of`, flags the row
`needs_review`, and `aalam.validate` fails the build if one survives.

Two things follow. First, **a named list is not a general solution**: it
catches the authors already seen and nothing else. Second, and more important,
this class was found by reading twelve rows at random. **Others like it
probably remain, and only §1 would find them.**

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

Counterparty names discovered in text are sometimes stored in their folded
form («احمد الابي» rather than «أحمد الأبي»); the identifier is unaffected and
the evidence quote preserves the printed orthography.

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

**709 of 873 edges carry no date at all.** A biography states that a relation
existed far more often than it says when. `date_precision = none` means the
source never placed the tie in time — it is not a missing value to impute, and
these edges cannot be assembled into a panel or replayed as a dynamic network.
Only the 164 dated edges support anything temporal, and they are concentrated
in the political careers rather than spread evenly across the corpus.

## 9. Identity

Names are normalised on an identity key that strips titles, so
الجنرال خير الدين and خير الدين باشا are one person, while his sons
طاهر باشا خير الدين and محمد باي خير الدين stay distinct. That is the
behaviour the tests pin.

The risk runs the other way: two different men sharing a name fold into one
node, and this volume is full of common names across three centuries. No
disambiguation by date is possible, because alters carry no life dates. There
is no measured homonym rate.

## 10. Reproducibility

The scan is not redistributed. `data/raw/aalam/manifest.csv` carries a sha256
per page and pins the OCR engine, version and flags, so a re-OCR appears as a
diff rather than silently changing the text. The per-page OCR output is
committed, so the tables rebuild without an OCR engine installed and the quote
gate runs in CI on every row.

The model pass is committed as a record
(`data/processed/aalam-tunisiyun/records/assertions_model.jsonl.gz`), not
regenerated per build. Everything downstream of it is deterministic, so the
tables rebuild byte-identically and CI diffs them.
