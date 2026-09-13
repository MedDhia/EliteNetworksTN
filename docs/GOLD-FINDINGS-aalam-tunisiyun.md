# What the gold sample exposed — A'lam Tunisiyun

Hand-written, unlike `GOLD-SCORE-aalam-tunisiyun.md`, which is generated. This
records the defects coding the sample turned up, so that each becomes a named
test rather than a remark. The scores themselves, and what a self-audited
score is worth, are in the generated report.

**Nothing here has been fixed yet, on purpose.** The sample was coded against
the committed tables, so changing the extractor before scoring would leave
verdicts pointing at rows that no longer exist. Fixes land after the score,
each with a regression test, and the sample is then recoded — it is seeded, so
recoding means the same 206 ties and 60 passages.

---

## 1. A verbatim quote can be about the opposite of what the row claims

`E0025` asserts that Aziza Othmana was a member of the zawiya of Sidi Ahmad
b. Arous. Its quote is genuinely in the entry. The sentence immediately before
it says she was **refused** burial there: «لم يُسمح لأسباب غامضة بدفنها في
زاويته». The row records an affiliation the passage denies.

This is the clearest possible demonstration of what
`LIMITATIONS` §4 claims and §5 describes: the quote gate proves a sentence
exists, not that the row reads it correctly. No amount of quote checking
catches this. Only a coder reading the surrounding text does.

It is also a row this project's own model pass authored, which is the honest
form of the point.

## 2. The reading-versus-tutelage class is wider than a name list

`config/aalam_authors_read.yaml` catches a tutelage tie whose counterparty is
a listed author. Coding found the same error where the list is not the cue:

- `E0180` records al-Bakkouche as a pupil of Mahmud Qabadu. The paragraph
  enumerates poets whose work he studied — «الذين درس إنتاجهم ... أصبحت
  دواوينهم لا تفارق مكتبته» — and Qabadu closes the enumeration, detached by
  «وعلى وجه الخصوص». The governing verb is «درس إنتاجهم», studied their
  output. Qabadu escaped the list-based guard because he is a near-contemporary
  Tunisian, not a pre-modern authority.
- The same entry's prose-thinker list *was* caught, so the guard works where
  the names are known and fails where they are not.

**The cue is the governing verb, not membership of a list.** A rule keyed on
«درس إنتاج», «استهواه نظمه», «لا تفارق مكتبته» would generalise; a longer list
never will. `E0201` is the control: there Qabadu genuinely is one of Bu Hajib's
«أساتذته» whose «دروس» he followed, and the row is right.

## 3. Credential direction is read backwards

Two errors turn on what a certificate does. The volume states plainly that the
ijaza is a **teaching** licence: «الإجازة التي هي بمثابة شهادة الكفاءة
للتدريس» (`aalam:1.04`). The extractor treats any ijaza near an institution as
inbound schooling.

- `E0200` records Ibrahim al-Riyahi as having studied at the Zaytuna. The
  passage says his ijaza «ستفتح في وجهه أبواب جامع الزيتونة» — future tense —
  and then describes what the doors opened onto: «خطواته الأولى الموفقة بجامع
  الزيتونة، سواء كمدرس أو كعالم وأديب», «إقبال الطلبة على حلقات دروسه». The
  book never says he studied there. The tie should be `taught_at`.
- `E0195` maps a 1936 Hamburg doctorate onto `licensed_by`, a relation the
  codebook defines as receiving an ijaza. A modern شهادة has been collapsed
  into a traditional إجازة.

## 4. No threshold between an event and a post

`taught_at` is defined as holding a teaching post. It is currently assigned to:

- one guest lecture — `E0177`, «ألقى على منبر الخلدونية محاضرة بليغة»;
- a series of private conversations the subject then declined to continue —
  `E0193`, which closes «فقد قرر العدول عن التقدّم إلى أبعد من ذلك»;
- an invited teaching mission, which is correct.

Either `taught_at` needs an appointment cue («تصدّى لتدريس», «عهد إليه بإلقاء
عدّة دروس», «مدرس من مدرسي») or the vocabulary needs a `lectured_at` for the
single occasion.

## 5. Translators and editors are recorded as authors

Four rows across two coders. «تحقيق محمد الصادق بسيس» made Bsis the author of
a work whose real author is named in the same footnote; «نقل إلى اللغة العربية»
did the same for two European works, one of them explicitly unfinished. The
vocabulary has no `translated` or `edited`, so the pipeline coerces both to
`authored`. This book is full of translations — it is itself one — so the
relations are worth having rather than working around.

## 6. Bare given names are completed from the wrong man

`E0020` gives al-Tayyib Radwan's father as «مصطفى آغة». The entry says only
«أنجب أبوه مصطفى، رئيس قسم الإنشاء بإدارة المالية», and names him مصطفى رضوان
two paragraphs later. «آغة» appears nowhere in the entry — and مصطفى آغة is a
different man with an essay of his own (`aalam:2.11`, 1871–1946) who cannot be
the father of a man born in 1869.

A corpus-wide name index is being consulted to flesh out a bare given name,
and it is merging two people. This is the homonym risk `LIMITATIONS` §9 names,
caught in the act.

## 7. Collective and descriptive counterparties reach the node list

`E0191` stores «الأساتذة الذين ساهموا في تكوينهما» — a definite plural noun
phrase — as a `person` node. The sentence says only that Agha and Bakkouche
admired the same teachers. The edge has no resolvable counterparty.

The `name_kind = described` flag added while drawing the figures marks these,
but marking is not enough here: a **singular** description
(«ابنة الأصرم») is a real tie to one unidentified person and worth keeping,
while a **plural** one is not a person at all. The two need separating.

## 8. The same tie is extracted twice under different name strings

`E0014` and `E0019` are one sentence and one tie, emitted by the model pass and
the rule pass under «طاهر خير الدين» and «طاهر باشا خير الدين». Both are
correct, so both inflate the numerator and the edge count.

Deduplication should run on `(entry_uid, relation, folded quote)` across
extractors before anything is counted.

## 9. Quotes too short to carry the tie they support

Repeatedly flagged: a stored quote is a bare fragment of a name list while the
relation lives in a preceding clause or a footnote the quote does not reach
(`E0072`, `E0036`, `E0050`, `E0053`, `E0064`). The ties are right, but a quote
that cannot support its row on its own **defeats the purpose of the gate** —
it makes a spurious edge unfalsifiable at the quote level, which is precisely
what happened in §1.

A minimum-span rule, or a requirement that the quote contain both the relation
cue and the counterparty, would restore the guarantee the gate is supposed to
give.

Measured, not impressionistic: one coder reported that **four of their
thirty-five rows would score `spurious` if judged strictly from
`evidence_quote` alone**, because the quote clips at a comma and the
load-bearing predicate sits in the next breath («…بمناسبة إحالته على
التقاعد»). Those four ties are real. The guard passed spans that cannot audit
themselves, which is how §1 got through.

A related blind spot: subject resolution is doing real work that the quote
does not show. Four rows resolve a subject correctly across paragraphs — a
father rather than the entry's subject, «الصدر الأعظم» resolved to Khayr
al-Din several paragraphs later — and every one checks out, but none is
verifiable from the stored quote. That is silent risk in any entry holding two
men of one surname, which this book has several of.

## 10. Departures manufactured from the end of a tenure

`E0149` records Muhammad al-Amin al-Shabbi as having **left** the education
ministry. The sentence states tenure and nothing else: «بتكليفه غداة الاستقلال
بمهمة وزير التربية القومية التي اضطلع بها مدة سنتين (1956-1958)». No departure
predicate appears anywhere in the entry — no ترك, غادر, أحيل, استقال, خلفه.
The `left_post` was inferred from the closing year of a bounded span.

`E0142` is the control: there the text really does say «بمناسبة إحالته على
التقاعد». The sweep this implies is mechanical — any `left_post` whose quote
contains a date range but no departure verb is suspect.

## 11. `appointed_to` is carrying three different relations

Coded `correct` throughout, because the person-office tie is stated and the
vocabulary offers nothing better, but the label spans:

- a genuine appointment — «تعيينه والياً بسوسة»;
- an appositive title with no appointment event — «أبوه مصطفى، رئيس قسم
  الإنشاء بإدارة المالية», which merely identifies the father;
- a self-chosen career — «فاختار مهنة المحاماة», «الالتحاق بسلك التعليم».

Anyone reading `appointed_to` as evidence of state patronage will over-count.
It needs splitting, probably into `appointed_to`, `held_office` and
`entered_profession`.

## 12. Office nodes minted from things that are not posts

`appointed_to` is defined as taking up a named post. It has produced office
nodes for a profession (`E0134`, «أول محام تونسي» — an epithet, nobody
appointed him), a teaching duty (`E0113`, «تدريس التاريخ») and a military rank
(`E0132`, «رتبة أمير لواء»). The underlying facts are all stated; the nodes
pollute the office vocabulary and inflate office degree.

Related, and the reason §11 matters: four rows harvest a **titular
apposition** — «اغتيال الصدر الأعظم ووزير الحرب محمد شوكت باشا», «وزيره الأكبر
مصطفى خوجة», «والده الوزير الأكبر خير الدين باشا». Each states a true
office-holding fact about someone mentioned in passing, each has an empty
`year`, and none states an appointment event. If the office layer is to be
read as a sequence of tenures these are a different kind of object.

## 13. One antagonism recorded twice, and a direction the vocabulary cannot hold

`E0114` and `E0116` are the same tie: the same body under two designations in
one paragraph («لجنة الاتحاد والترقي» and «الحزب الحاكم»), double-counted in
any degree measure.

Worse, `E0114`'s sentence states the arrow the other way — his press campaigns
provoking the CUP — and the vocabulary has no `opposed` to record that. So
`opposed_by` is being used as an undirected antagonism label while being
documented as directed. Either add the converse or document the relation as
symmetric; it cannot stay both.

## 14. Recall: ties between two other people are dropped

The passage sheet makes this the dominant miss. The pipeline anchors an edge
on the entry's subject, so a relation stated between two *other* people in the
same paragraph is lost: every miss in `P0004` concerns Husayn Bey and the two
princes rather than Yusuf Sahib al-Tabi, whose entry it is.

Cousin ties are never caught at all («ابن عمهما حسين باي», «ابن عمه الملك
الجديد محمد باي»), though father and brother ties are. Also missed: the tail of
enumerated lists, hostile and violent relations, and succession where the
successor is designated by office rather than named.
