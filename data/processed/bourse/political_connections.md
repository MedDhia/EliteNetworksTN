# Political connections

Firms are coded connected through four observable channels, each
flagged separately so a narrow or a broad definition can be applied
without recoding. Rules live in `config/bourse_political_connections.csv`.

**349 firms** carry at least one connection in at least one year, over 28 years (1990–2026), on **800 pieces of evidence** (115 of them from OCR'd pages).

| Channel | Firms | Definition followed |
|---|---:|---|
| `state_ownership` | 15 | A state body holds equity (Boubakri et al. 2008) |
| `state_board` | 19 | A state body holds a board seat |
| `officeholder` | 11 | A director's title names a political or senior bureaucratic office (Faccio 2006) |
| `public_bank` | 333 | Board or equity tie to a majority state-owned bank (Khwaja and Mian 2005) |
| `political_figure` | 0 | Director matches a named roster (Rijkers et al. 2017) — **roster ships empty** |

`pc_narrow` — a sitting officeholder, a roster match, or a state stake at or above Faccio's 10% — holds for **9 firms**. `pc_broad` (any channel) holds for 349.

## What the zeros mean

A zero is *not* evidence that a firm is unconnected. It means no
filing in this corpus printed a connection the rules can see. Three
things follow, and they bound what the variable can be used for.

**Connection is coded from titles that firms chose to print.** A
board table that lists a director's occupation will reveal a ministry
post; one that lists only names will not, and both are common. The
measure is therefore closer to *disclosed* connection than to actual
connection, and the gap between them is not random: a firm with more
to disclose may disclose less.

**The channel that identifies Tunisian connection best is empty.**
Rijkers, Freund and Nucifora (2017) code connection by matching owners
against the Ben Ali confiscation lists. That is the design this
dataset should eventually carry, and the matching code is here and
tested. It has no names in it because a name in that file asserts that
a real, often living person was tied to an authoritarian regime, which
needs a citable primary source per row rather than recall. Until it is
populated from the Journal Officiel decrees, `pc_political_figure` is
structurally zero and any claim about regime connection specifically —
as against state connection generally — is out of reach.

**Coverage is filings-driven.** Connections can only appear in years
and firms the corpus covers; see §6.4 of the codebook. Counting
connected firms per year measures filings as much as politics.

## Where the officeholder channel actually is

Of the firms carrying an officeholder tie, the great majority are banks — ADWYA, BH BANK, BIAT, BNA, BT, BTE (ADP), BTK, BTQI, ….

That is a finding rather than a defect: Tunisian bank boards seat
ministry officials, central-bank staff and named state
representatives, and they say so in their filings. But it means the
officeholder channel is close to a *bank* indicator in this corpus,
and should not be entered into a regression alongside a sector
control without checking what is left of it.

Note also what is absent. **No sitting minister appears on any board
in this corpus.** The strongest personal ties observed are, counted
as distinct printed titles rather than as people:

- 5 × `cabinet_staff` (current)
- 3 × `minister` (former)
- 2 × `governor` (former)
- 2 × `ministerial_adviser` (current)
- 1 × `secretary_of_state` (current)

Those are title *occurrences*, deduplicated on the text. They are not
a headcount: one director at BIAT is an ex-minister and an ex-deputy
governor of the central bank and so appears under both, and a name
printed once in capitals and once in mixed case counts twice. The
evidence file carries no resolved person id, so a true headcount
needs the person layer joined on `counterpart`. Either way the order
of magnitude is the point: Faccio's own definition, applied strictly,
is close to empty in this corpus.

## Entity-resolution debris: 7 evidence rows (0.9%)

4 of the coded 'firms' are not companies at all but
extraction debris — a prospectus title fragment, a parenthetical
date, a committee name — carrying 7 evidence rows between them: '(Créé lors du CA du 02 octobre 2018)', '(créé lors du CA du 12 décembre 2006)', '/e Comité de Nomination', "D'ADMISSION".

The *evidence* on them is usually real: `D'ADMISSION` carries a
ministry representative on a 1990 board, correctly read from the
page, but attached to the issuer name a scanned prospectus title
yielded instead of the bank's. These rows are left in the output
rather than filtered, because dropping them would hide the defect
instead of measuring it. Exclude them on `entity_id` if the firm
list matters for your specification.

## Choices a reader should check rather than inherit

- **Civil servants count as officeholders.** Tunisian boards seat
  ministry staff far more often than ministers. They are a separate
  `category`, so they can be dropped, but they are in `pc_officeholder`.
- **Former office is flagged, not dropped** (`pc_officeholder_former`),
  after Hillman (2005). It is excluded from `pc_narrow`.
- **Public-bank subsidiaries are excluded.** A stake in a bank's
  leasing arm is not a credit relationship with the bank.
- **The public-bank channel is a governance tie, not lending.** The
  filings do not show loans, so it is outside `pc_narrow`.

## Files

`political_connections.csv` is the firm-year panel.
`political_connection_evidence.csv` is one row per supporting record,
each carrying the document URL and page, so every coded 1 can be read
back to the filing that produced it.
