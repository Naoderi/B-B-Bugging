# Design stage (disclosed seeds, not used for evaluation)

Diagnosis on the original seed 261107: all 21.3× NAV turnover came from the 34 scheduled reviews, none from cap repairs or breadth rechecks. After the first build, 5.3× was equity/bond exposure change, 13.8× was rotation between exposure groups as momentum ranks shuffled, and 1.6× was swaps between near-identical funds. The lever is hysteresis: the retention credit a held fund receives in the ranking.

Criterion fixed before the sweep: choose the retention credit with the best median return against 60/40, provided the median drawdown reduction falls by no more than 1 percentage point relative to 0.5%.

`python3 backtest_seeds.py design`, seeds 1–10, regime order shuffled per seed:

| Retention credit | Median RO − 60/40 | RO beats 60/40 | Median drawdown cut | Median turnover | Median cost drag |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.5% (v1.0) | −19.89 pp | 0% | 7.1 pp | 19.4× | 3.21% |
| 1.0% | −19.86 pp | 10% | 7.0 pp | 18.0× | 2.98% |
| 2.0% | −19.08 pp | 10% | 7.0 pp | 15.6× | 2.70% |
| 4.0% (v1.1, adopted) | −17.98 pp | 10% | 6.5 pp | 13.7× | 2.32% |

4.0% meets the criterion (−0.6 pp drawdown change). It sits at the edge of the grid. We did not search further, to limit selection on the design seeds.

What the design stage already shows: turnover was a real but secondary cost. The large return gap to 60/40 comes from exposure. The Balanced profile caps equity at 52% (target 50%) and fund exposure at 86%, against 60% equity and 100% invested for 60/40. Every shuffled market has the same total drift, so a less-exposed portfolio trails in return. The evaluation therefore adds a policy-matched benchmark that holds those caps without signals.
