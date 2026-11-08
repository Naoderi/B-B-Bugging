# Finance project test report

**CHALLENGE (self-serve): hidden markets cases**

Dataset: 60 cases; seed: None; source: AgentVerse seeded generator v2 (hidden challenge).

Exact checks: **0 passed, 0 failed, 0 execution errors**.
Market simulations completed: **60**. Cases not run: **0**.

Only the configured adapter and defined checks were exercised. A baseline run tests the kit, not your submission.

## Challenge integrity

- Cases were generated in memory after the adapter was fixed; no input or answer file existed during the run.
- Seed commitment (published before scoring): `3c4a12b453c7e3833fab37bcefda7a194cee9c5edc64f44d9a3bbce02e0ed005`
- Seed: fresh random; revealed in SEED-REVEAL.txt after this run
- Kit fingerprint: `5c90bf815848f4edd85bb2446e00382a24f003d936b3bad72f297a3b7885dad9` (compare with the organisers' published value)
- Project commit: `4baf054f3c67b2ad135b4c30f1987edd28de61fd`, uncommitted changes: 1
- Provenance review: **1 item(s) need a human look:**
  - `backtest_seeds.py`: references answer keys or seed files

## Coverage

| Task / scenario family | Pass | Fail | Error | Simulated |
| --- | ---: | ---: | ---: | ---: |
| markets / falling | 0 | 0 | 0 | 10 |
| markets / flat | 0 | 0 | 0 | 10 |
| markets / jump | 0 | 0 | 0 | 10 |
| markets / regime_change | 0 | 0 | 0 | 10 |
| markets / rising | 0 | 0 | 0 | 10 |
| markets / volatile | 0 | 0 | 0 | 10 |

## Strategy results after costs

| Case | Final cash | Profit / loss | Buy-and-hold final | Cash baseline | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| 33c47a72e32aecb71e2b | £2,840.85 | £0.00 | £3,046.29 | £2,840.85 | 0.00% |
| 1d1cefa7e1fd92721c88 | £8,603.46 | £0.00 | £6,288.99 | £8,603.46 | 0.00% |
| 31292d769549d61e8979 | £2,622.83 | £0.00 | £2,605.43 | £2,622.83 | 0.00% |
| a9f259ad841069cbe2b3 | £1,248.36 | £0.00 | £1,238.66 | £1,248.36 | 0.00% |
| 0d0d7c3fed4db1e9b662 | £5,249.84 | £0.00 | £4,951.74 | £5,249.84 | 0.00% |
| 625122f77d7519531fc3 | £1,563.83 | -£17.79 | £1,220.00 | £1,581.62 | 1.62% |
| 218258f30b42ba4c5d71 | £4,947.25 | £0.73 | £5,713.09 | £4,946.52 | 0.62% |
| 64c12822a971fd0c0581 | £4,198.66 | £0.00 | £2,578.08 | £4,198.66 | 0.00% |
| 97d992e2a53ae99d7da9 | £4,173.22 | £0.00 | £4,155.18 | £4,173.22 | 0.00% |
| c0b62ad0d3e2f0482572 | £4,984.94 | £0.00 | £2,803.96 | £4,984.94 | 0.00% |
| c698530b82355054f8ab | £3,240.54 | -£317.32 | £3,522.74 | £3,557.86 | 8.91% |
| a8855284e92c57e2ed69 | £7,349.60 | £0.00 | £9,391.92 | £7,349.60 | 0.00% |
| 88b44885ef30b36278ae | £12,795.27 | £3,450.70 | £14,861.51 | £9,344.57 | 0.38% |
| 5b602af53d593982b372 | £8,724.20 | £0.00 | £6,840.88 | £8,724.20 | 0.00% |
| 70d89a4f9405353e171d | £5,969.92 | £0.00 | £5,936.44 | £5,969.92 | 0.00% |
| 3c004ce29e5148e28bba | £1,297.60 | -£517.41 | £1,251.42 | £1,815.01 | 28.50% |
| 5a7cdb3401d7e59a47d4 | £3,383.05 | -£433.30 | £3,662.98 | £3,816.35 | 11.91% |
| 8f3ab9598f0cc654cc18 | £9,358.53 | -£210.78 | £11,886.93 | £9,569.31 | 2.91% |
| 40c1ef499f427cd944c0 | £6,595.40 | £2,016.81 | £7,678.62 | £4,578.59 | 0.40% |
| 933bf6bab9432699ebd2 | £1,984.67 | £0.00 | £1,778.29 | £1,984.67 | 0.00% |
| d4794c67145f0be479a5 | £7,770.25 | £0.00 | £7,750.45 | £7,770.25 | 0.00% |
| 43b8a3424a8ce9ff6873 | £1,733.22 | £0.00 | £1,382.55 | £1,733.22 | 0.00% |
| d827e97c48d3d22f5889 | £1,243.48 | £0.00 | £1,187.71 | £1,243.48 | 0.00% |
| 899bc4fe6aa98eca317c | £4,136.41 | £0.00 | £2,866.59 | £4,136.41 | 0.00% |
| 7a3982a27c497eaedb59 | £1,591.64 | £241.23 | £1,818.55 | £1,350.41 | 0.50% |
| a8f3afa4162bb23221f5 | £8,585.17 | £0.00 | £5,771.41 | £8,585.17 | 0.00% |
| 51ab9529d5d9b4cc3430 | £3,775.13 | £0.00 | £3,751.69 | £3,775.13 | 0.00% |
| f44fd2115d4ab0fb3110 | £3,468.12 | £0.00 | £2,773.58 | £3,468.12 | 0.00% |
| 83c7e243abfd3d1b148c | £4,997.88 | £328.18 | £4,724.88 | £4,669.70 | 12.33% |
| 9c14b34acc8e561d2ac5 | £8,123.43 | -£475.68 | £10,569.57 | £8,599.11 | 5.57% |

Showing 30 of 60 paths; every result and trade is in case-results.jsonl.
Completing a simulation does not mean the strategy is good. Compare losses, costs, baselines and drawdown. These price paths do not model real market liquidity or predict returns.

**Across 60 paths:** 39 wins, 21 losses, 0 ties vs buy-and-hold; beat cash on 10. Median excess 0.59% of capital; mean max drawdown 2.67%; sign-test p = 0.027.
**Beat buy-and-hold more often than chance would explain on these paths.**

## Next action

Run your actual submission adapter if this was a baseline. Add project-specific checks, then rerun with a fresh seed. Anything outside these checks remains untested.

Hidden challenge run: no input or answer file existed while the adapter ran, and the kit's reference calculations were disabled for it.
