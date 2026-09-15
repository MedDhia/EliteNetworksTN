# Limitations — Rodovid genealogies

What this dataset cannot support, stated plainly. Most of it is a property of
the source rather than of the code, and none of it is fixable by tuning a
regex. The tables and their columns are in
[`CODEBOOK-rodovid.md`](CODEBOOK-rodovid.md).

## 1. The export is truncated, so every count is a floor

Both sheets of `RodovidData234862.xls` came out of Excel at exactly **65,535
data rows** — the BIFF8 row limit — so both were cut, not merely the larger
one. Two consequences:

- **3,872 people** are referenced by a tie but have no row of their own;
- **22,857 of the 37,819 Tunisians kept here have no surviving tie at all**,
  which is a property of the export rather than of the families.

The kinship graph is therefore partial, and anything computed on it is a lower
bound: the kept graph has 23,565 ties over 14,962 people, and its largest
connected component holds 4,189. A re-export in `.xlsx` would lift the cap, and
is the single change that would most improve this build.

## 2. There is no human-coded gold sample

The filter's held-out accuracy, **0.966**, is printed on every run and it is
not a validation figure of the kind the A'lam build reports. The name model is
trained on the 13,242 people the place signal already labels, and scored
against a held-out fifth of those same labels — so it measures agreement with
the place signal, not correctness. `sig_name` and the seeding place evidence
are not independent, and the accuracy should not be quoted as a precision.

What can be checked instead is the behaviour on known cases, and that is in the
codebook: all 2,906 rows across twenty well-known elite families are kept; the
Italian and Maltese families of Tunis are kept on Tunisian evidence despite
European names; the Egyptian, Hejazi, Persian, Ottoman and Abkhaz courts are
dropped on foreign evidence despite Arabic ones.

## 3. The low band is a maybe, not a finding

**437 kept rows score below 0.5**, most of them bare names with no record and
no surviving tie, where only the name model has anything to say. Every signal
is written out per person, so a stricter set costs nothing: `confidence ==
"high"` is 32,320 people.

## 4. Arabic names outside Tunisia are the hardest case

Where the record names Cairo, Istanbul or Tehran, or the family is attested
elsewhere, they are dropped correctly; a bare Arabic name with no record and no
ties can be kept on the name alone, and an Afghan and an Egyptian or two are in
the file.

## 5. Colonial France in Tunisia is a definitional question

Someone French by family and Tunisian only by posting or birthplace is
excluded, and flagged `tunisia_link` when the record says so — 8 rows: Roger
Seydoux, résident général; Baron Rodolphe d'Erlanger of Sidi Bou Saïd; a
British vice-consul. The filter answers the question one way. A study of the
protectorate administration would want it answered the other, and the flag is
there so that set can be recovered.

## 6. `sig_family` is surname-based

So it is weak for surnames common across the Arab world, and for the 193 kept
rows whose name survives only as a `Personne:<id>` wiki link.

## 7. Families are surnames, and some surnames are patronymics

Surnames are rodovid's own reduction of the name, and a blunt one: `Mohamed
Salah Ben Mrad` reduces to `Mrad`, which is right, but `Ahmed Ben Ali` with no
family name reduces to `Ali`, which makes a "family" out of a patronymic. Nodes
like `Ali`, `Mahmoud`, `Youssef` and `Amor` are aggregates of unrelated people
and must be named as such wherever the family tables are read. The large houses
— Bey, Mrad, Cherif, Belkhodja, Darghouth, Miled, Ayed, Lasram — are not
affected.

## 8. What the network is not

A force-directed picture always looks like it has neighbourhoods, because
putting connected things near each other is the algorithm's whole job. These do
not: the elite here marries *widely*, not into circles.

Against 50 rewirings that give every family the same number of allies and deal
the marriages at random (`make rodovid-audit`):

| | observed | null | |
|---|---|---|---|
| closure, whole network | 0.0220 | 0.0219 | **1.00x** |
| closure, the 5-core | 0.0693 | 0.0581 | **1.19x** |
| modularity, whole network | 0.3652 | 0.3386 | +0.027, z=+10.6 |
| modularity, the 5-core | 0.2689 | 0.2299 | +0.039, **z=+1.9** |

The triangles that exist are the ones the degree sequence forces. The
whole-network modularity excess is statistically obvious and substantively
nothing: it comes from the hundreds of detached fragments, each trivially its
own "community", rather than from any division of the elite. Inside the core,
where a bloc would actually mean something, the excess sits inside the noise of
the null itself. `figures/fig03_rodovid_alliance_null` is that comparison
drawn — two panels a reader cannot tell apart.

The community detection is one round of local moving (Louvain's first phase, no
aggregation), which understates modularity — but it understates it equally for
the observed graph and for its nulls, and the comparison is the point.

Truncation cuts the other way here and is the honest caveat: lost ties remove
triangles, so the observed closure is a floor. It would have to be several
times higher to change the reading.

One refinement, from the dated series in
[`CODEBOOK-rodovid.md`](CODEBOOK-rodovid.md): the 1.00x is an average over two
and a half centuries, and it is not flat underneath. Against the same
degree-preserving null, closure reaches 2.10 in the 1875 cohort and 2.28 in the
1900 one before falling back to 1.0 from 1950. "The elite marries widely rather
than in circles" holds for the network as a whole and for every generation
except that one half-century.

## 9. The dates are derived, and the derivation has a direction

Everything in `alliance_panel.csv` and `network_evolution.csv` rests on dates
that are not in the source. Four things follow, in descending order of how much
they should worry you.

**A period is a birth cohort, not a wedding date.** `cohort_year` is the mean
birth year of the two spouses. The wedding follows roughly a generation later —
the measured parent-child gap is 31 years — so a couple in the 1900 bin married
around 1925–1935. Any alignment of these periods with a political date is
off by that much before the estimation error is counted. **Do not read the
periods against events.** The build deliberately does not add the offset,
because a constant would give the series a precision it has not got.

**The dated alliances are not a random sample of the alliances.** 86% of
couples can be dated, and the 14% that cannot are the thinly recorded ones: no
birth year, no dated relative, often no tie at all. Those are systematically
the smaller and more peripheral families. Every count in the dated network is
therefore a floor that is *lower for peripheral families than for central
ones*, which biases concentration measures upward. The same caution applies to
the rise in the number of families over time: it is partly the field growing
and partly the record improving, and nothing here separates them.

**Error grows with distance from a recorded year.** Half the dated people are
three or more kinship hops from any observed birth year, where MAE runs 9.7 to
14.7 years. At a 25-year bin width this moves couples between adjacent periods
but not further: 95% of held-out people land within one bin. Filter on
`quality` if a finding depends on placement — `observed` and `kin1` are 336 and
974 of the 3,592 dated couples.

**The period boundaries are arbitrary.** 25 years is chosen because it is the
resolution the validation supports, not because Tunisian elite generations turn
over every 25 years. A finding that appears or disappears when the bins move
is a finding about the bins.

## 10. The last two periods are cut off by the calendar

A couple binned at 2000 was born 2000–2024 and will marry around 2030. The
`w_` (windowed) columns for 2000 and 2025 therefore measure a marriage market
that has not happened yet, not one that collapsed — `window_complete` is 0 on
those rows and the figures stop at 1975. The cumulative columns are unaffected.

## 11. Rodovid is a user-edited wiki

Coverage follows what contributors chose to enter: deep on a few Tunis
families, thin elsewhere, and dates and offices are as reliable as whoever
typed them. **This is a relational map of who is related to whom, not a
biographical source**, and it is not a sample of anything — the crawl was
seeded, so the families in it are the families someone chose to seed it with.
