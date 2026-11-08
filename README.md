# Campus Index

Campus Index is a paper ETF research lab for UK university students. It checks whether a fictional investing plan leaves enough room for rent and other essentials, analyses completed price observations and asks for explicit approval before changing the paper ledger.

## Rent-safe coach (agentic)

A student describes their situation in plain English. Two cooperating agents then take over.

- **Coach** (`coach.py` and `tools.py`). It picks a brain automatically: **Claude** (`claude-opus-5-5` through the `anthropic` SDK) when `ANTHROPIC_API_KEY` is set, **ASI:One** when `ASI_ONE_API_KEY` is set, and otherwise the **offline planner** (`planner.py`). The planner is a rule-based policy that drives the same tools with no key or network, so the demo always works. The page shows which one is running. It records each fact with the student's exact words as a quote. If the student has not said whether the money could pay rent or bills, how much cash runway they hold, or when they need it back, the Coach asks instead of assuming. It then calls the verified engine (`agent.work()`) as a tool. It may run up to three what-if comparisons (for example, more runway first or a longer horizon) and explains the outcome with a citation on every figure.
- **Risk Guardian** (deterministic, `guardian.py`, no model). It reruns the analysis independently and requires the proposal digest to match. It re-applies the affordability veto and rejects leverage. Every £, % and × figure in the Coach's text must match a cited, recomputed fact. A failed explanation goes back to the Coach once, and is then replaced by a verified template. The Coach has no write tools. Only a countersigned, unlevered proposal reaches the existing human approval gate.

Every tool call, quote and Guardian verdict is written to the append-only audit. The tool loop is capped at eight calls, and pausing paper actions also stops the coach.

`agents_app.py` runs both as uAgents. The **Guardian** accepts `CountersignRequest` messages and a REST route. The **Coach** speaks the Agentverse chat protocol (`publish_manifest=True`, mailbox), so ASI:One users can talk to it directly, and it requests countersignatures from the Guardian by agent message.

```sh
python3 server.py --port 8766 --open    # offline planner, no setup

# optional: Claude as the coach's brain
.venv/bin/pip install -r requirements.txt
ANTHROPIC_API_KEY=... .venv/bin/python server.py --port 8766 --open

# optional: the uAgents
export ASI_ONE_API_KEY=... CAMPUS_GUARDIAN_SEED=... CAMPUS_COACH_SEED=...
.venv/bin/python agents_app.py guardian &
.venv/bin/python agents_app.py coach &          # optional: Agentverse chat agent
CAMPUS_GUARDIAN_URL=http://127.0.0.1:8101/countersign python3 server.py --port 8766
```

Without `CAMPUS_GUARDIAN_URL` the website countersigns in-process with the same code. If the Guardian agent is configured but unreachable, nothing is proposed. Python.org builds on macOS need root certificates for HTTPS: run *Install Certificates.command* once, or `export SSL_CERT_FILE="$(.venv/bin/python -m certifi)"`.

## Run locally

Requires Python 3.11 or later. The default demo runs offline with the standard library. On macOS, open `Start Campus Index.command` from Finder to start the server and open your browser. Keep the Terminal window open while using the app.

```sh
python3 server.py --port 8766
```

Open [Campus Index](http://127.0.0.1:8766/) on the same computer. Use **Balanced student** for a paper allocation. Try **Aggressive student** for the 100% target and leverage stress check. Use **Rent at risk** to demonstrate the affordability veto. The **Paper portfolio** tab holds the stop control and the approved snapshot.

You can enter positions manually or upload a fictional CSV with the columns `ticker,quantity` or `isin,quantity`. A two-position example follows.

```csv
ticker,quantity
VWRP,2.5
VAGS,4
```

The starting balance includes these positions and any residual cash. The CSV mapping requires confirmation. To modify an existing approved allocation, choose **Use my approved paper positions**. Approving a separate scenario replaces that browser workspace’s snapshot. The local SQLite ledger persists in the ignored `.local/` folder. Opening the app in a separate browser profile starts a separate workspace.

## Strategy and architecture

The frontend is responsive HTML, CSS and JavaScript. A loopback-only Python server runs the same deterministic strategy and verifier used in tests. It streams actual tool completions. SQLite transactions enforce one-time approval, rejection, pause and session isolation. Audit rows are append-only in the database.

- `market.py` holds 19 issuer-sourced LSE GBP UCITS listing identities, synthetic paths and licensed file validation.
- `agent.py` runs parse, normalise, enrich, analyse, verify and explain. It can ask for corrected identifiers, stop at the cash runway check, exclude an exposure and block unsafe leverage.
- `strategy.py` and `verifier.py` compute and independently reconcile GBP values, RO signals, risk and costs. The engine never calls a model. The coach's model only chooses tools and writes text, which the Guardian checks.
- `paper.py` owns proposals, approval and audit. Execution uses a confirmed fictional snapshot and supports fractional paper units.
- `backtest.py` replays frozen rules on 756 later observations after a 200-observation warm-up. `kit_adapter.py` connects the same RO signal to the Agentverse single-asset test runner.

RO’s 5-, 20- and 60-day momentum, 20-day sample volatility, 55/35/10 momentum mix, volatility penalty and 35%/50% breadth thresholds carry over as formulas. ETF scores subtract the annual fund charge and a 15 bp execution proxy and add a 4% retention credit for existing positions of at least 3% (v1.1; chosen on design seeds to cut rotation churn). Asset sleeves, fixed stress shocks, a 27% target with a 30% hard position and exposure-group cap, return-correlation screening, and a 10%/5% turnover band adapt the policy. Category-specific limits depend on loss tolerance, horizon, cash runway and objectives. Return targets affect the explanation only.

The standard portfolio uses up to 1.0× exposure. The separate daily-reset scenario explores up to a 2.0× multiplier subject to explicit acknowledgement, suitability and hard limits. Its assumed annual financing cost is 5.5% on gross exposure above NAV. Only the standard portfolio reaches the approval gate.

## Reproduce the evaluation

```sh
python3 -m unittest discover -s tests -v
python3 backtest.py
python3 backtest_seeds.py verify
```

**Unseen markets (headline evidence).** The rules were frozen and their file hashes recorded. Then 30 fresh seeds were drawn and their hash written to `COMMITMENT.txt` before any path existed. Each seed generates a new market with its own noise and a shuffled order of drift regimes. The retention credit was chosen beforehand on separate, disclosed design seeds 1–10 ([DESIGN.md](evidence/multi-seed/DESIGN.md)). Results ([REPORT.md](evidence/multi-seed/REPORT.md)), with the Balanced student profile and the costs below:

| Across 30 unseen seeds | v1.0 | v1.1 (adopted) |
| --- | ---: | ---: |
| Median return vs 60/40 | −6.65 pp | −5.17 pp |
| RO beats 60/40 on return | 37% of seeds | 33% (sign test p = 0.10) |
| Median max-drawdown reduction vs 60/40 | 8.2 pp | 8.7 pp |
| RO has the lower drawdown | 100% (p < 0.001) | 100% (p < 0.001) |
| Median return vs its own limits held statically | −4.06 pp | −2.71 pp |
| Lower drawdown than those static limits | 93% | 100% |
| Median turnover · cost drag | 19.7× · 3.17% | 12.9× · 2.20% |

The finding is risk reduction, not return. In every unseen market RO cut the worst fall, by a median 8.7 points against 60/40 and 6.4 points against its own policy limits held without signals. It usually gave up some return to do so: median net returns were 9.5% for RO, 14.0% for the policy benchmark and 16.5% for 60/40. The coach is instructed to present it to students that way. All emitted targets met the position and exposure limits.

**Original demo seed.** On seed 261107, v1.1 returned −5.3% against −8.2% for 60/40, with a 9.2% vs 18.0% drawdown. That seed informed the turnover diagnosis, so it is not unseen evidence. Read [the full replay](evidence/benchmark.json) or open **Benchmark evidence**. Evaluation uses next-close fills, 10 bp adverse half-spread and 5 bp commission per traded pound, synthetic daily OCF accrual, 0% cash yield and a constant 3% GBP reference for Sharpe.

**Kit challenge.** The first run ([kit-challenge](evidence/kit-challenge/REPORT.md)) traded on only 1 of 60 paths, because kit paths are 12–78 bars and the 60-day signal needs 61. Its 39–21 record against buy-and-hold was cash sitting out falling markets, not signal skill. The adapter now uses a labelled short-history form of RO from 21 bars, fixed before a fresh hidden rerun ([kit-challenge-v2](evidence/kit-challenge-v2/REPORT.md)). It traded on 25 of 60 paths and beat cash on 10, up from 1. It still went 39–21 against buy-and-hold: it stayed out of all 20 falling and flat paths, and lost all 10 rising paths because it entered late or, in 2 of them, not at all. The kit's provenance scan flagged `backtest_seeds.py` because it mentions seed files. Those are this project's own multi-seed files, not kit answer keys. The kit measures single-asset signal behaviour only, not the multi-ETF optimiser or the suitability workflow. To run a fresh hidden challenge with the supplied kit:

```sh
python3 "/path/to/agentverse/finance/bench.py" challenge --pack markets --cases 60 \
  --project . --output /path/to/new-result-folder --adapter python3 kit_adapter.py
```

Judges can add the kit’s `--seed-prompt --team "Team Name"` options. [Pitch evidence](web/pitch.html) is a self-contained browser deck with a print layout. The **Benchmark evidence** tab links to it.

## Licensed price input

The demo uses fictional GBP price paths. To run on rights-cleared history, set `CAMPUS_PRICE_CSV` to a wide CSV whose first column is `date` in ISO format and whose other columns contain four or more unique supported GBP listings. Use one currency unit across the file. Include VWRP and VAGS for the benchmarks. The signal needs at least 200 aligned adjusted closes. The evaluation needs at least 452. Place a companion `<filename>.csv.json` next to the CSV:

```json
{
  "source": "Name of rights-cleared provider or file",
  "retrieved": "2026-11-06T18:00:00+00:00",
  "licence": "Provider licence or written permission reference",
  "adjusted": true,
  "currency": "GBP"
}
```

GBP and GBp/GBX are accepted. Mixed or unsupported quote currencies are rejected. The importer filters dates beyond a conservative London 17:00 weekday cutoff, requires the latest completed session and fails closed after reloading a bad or stale input. London exchange holidays need a session calendar before use with real data. Cash values are illustrative at the final adjusted close. Full holdings overlap, volume-based liquidity, wrapper eligibility for some funds and real ETF performance remain unresolved. See the [source and licence register](SOURCES.md).

The project is local. GitHub submission and hosted deployment require the team’s repository and publishing approval. Suggested commit message `Build Campus Index ETF paper research lab`. Review the application files, tests, documentation and evidence before committing. The local ledger, credentials and licensed data files belong outside version control.
