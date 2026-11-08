# Multi-seed unseen-path evaluation

Run 2026-11-08T00:39:13+00:00. 30 evaluation seeds drawn with `secrets` after the rules were fixed. Seed commitment `bf07537455d06c6c816073a16c5073568912b4fd777b7bc006552d087e81e411` was written to `COMMITMENT.txt` before any path was generated. Seeds and nonce are in `SEED-REVEAL.txt`; `python3 backtest_seeds.py verify` recomputes the hash.

Each seed generates a new 956-observation synthetic GBP market with its own noise and a shuffled order of the eight drift regimes. The design seeds 1-10, used to choose the retention margin, are excluded. Rules, costs and the 200-observation warm-up match `backtest.py`. Balanced student profile, risk category 3.

| Version | Median RO − 60/40 (pp) | IQR (pp) | RO beats 60/40 | Sign-test p | Median drawdown cut (pp) | Drawdown lower | Sign-test p | Median turnover | Median cost drag | Limit checks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| campus-ro-1.0 | -6.65 | -17.9 to +4.1 | 37% | 0.200 | +8.2 (+4.9 to +10.6) | 100% | <0.001 | 19.7× | 3.17% | 100% |
| campus-ro-1.1 (adopted) | -5.17 | -17.1 to +3.0 | 33% | 0.099 | +8.7 (+5.3 to +10.7) | 100% | <0.001 | 12.9× | 2.20% | 100% |

## Do the signals beat the profile's own limits?

The policy benchmark holds the Balanced profile's caps without any signal: 50% VWRP, 34% VAGS, 16% cash, rebalanced every 21 observations with the same costs. It isolates what the RO timing adds.

| Version | Median RO − policy (pp) | IQR (pp) | RO beats policy | Sign-test p | Median drawdown cut vs policy (pp) | Drawdown lower |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| campus-ro-1.0 | -4.06 | -13.9 to +4.3 | 37% | 0.200 | +5.8 | 93% |
| campus-ro-1.1 | -2.71 | -10.9 to +3.2 | 37% | 0.200 | +6.4 | 100% |

## Reading the result

- Median net return over 756 forward observations: RO 9.5%, policy benchmark 14.0%, 60/40 16.5%.
- The worst seed for campus-ro-1.1 relative to 60/40 was 415189168.
- These are generated markets. They test whether the rules behave as designed on sequences they never saw, not whether any real ETF will perform this way.
