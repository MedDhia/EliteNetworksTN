# Gold-sample score

Sampling seed `20260912`. 112 of 491 extracted events judged; 75 of 402 blocks coded.

## Precision

**0.982** (95% CI 0.937–0.995) on 112 decidable events; 0 judged unclear and excluded.

| verdict | n | share |
| --- | --- | --- |
| `correct` | 110 | 98.2% |
| `wrong_person` | 1 | 0.9% |
| `wrong_org` | 1 | 0.9% |

Strictly spurious events — a tie asserted that the text does not state — are 0 of 112 (0.0%). The remaining errors are events that exist but were mistyped or misattributed, which degrade a variable rather than invent a tie.

### Precision by event type

| event_type | n | correct | precision | 95% CI |
| --- | --- | --- | --- | --- |
| `appointed` | 36 | 34 | 0.944 | 0.819–0.985 |
| `constituted` | 32 | 32 | 1.000 | 0.893–1.000 |
| `shares_transferred` | 14 | 14 | 1.000 | 0.785–1.000 |
| `capital_increased` | 10 | 10 | 1.000 | 0.722–1.000 |
| `resigned` | 7 | 7 | 1.000 | 0.646–1.000 |
| `headquarters_moved` | 5 | 5 | 1.000 | 0.566–1.000 |
| `dissolved` | 2 | 2 | 1.000 | 0.342–1.000 |
| `liquidated` | 2 | 2 | 1.000 | 0.342–1.000 |
| `renewed` | 2 | 2 | 1.000 | 0.342–1.000 |
| `renamed` | 1 | 1 | 1.000 | 0.207–1.000 |
| `revoked` | 1 | 1 | 1.000 | 0.207–1.000 |

### Precision by year

| year | n | precision | 95% CI |
| --- | --- | --- | --- |
| 2008 | 71 | 0.986 | 0.924–0.998 |
| 2009 | 41 | 0.976 | 0.874–0.996 |

## Recall

**0.967** (95% CI 0.886–0.991) over 60 ties stated in 43 relational blocks: 58 extracted, 2 missed.

2 blocks state a tie but yielded no event at all — these are the blocks a rule layer misses entirely, and the place where an added pattern buys the most.

## Caveat on provenance of these figures

Read `docs/LIMITATIONS-multiplex-2008-2012.md` for who coded this sample. A figure produced by the same agent that wrote the extractors is a self-audit: it is a real check on a rule-based parser, since the judgement is made against the printed French rather than against the code, but it is not independent. Any published figure should rest on coding by someone who did not write the rules.

