# Campus Index

**Team B-B-Bugging · Agentverse Hackathon, 7–8 November 2026 · Finance Track**

Campus Index is a paper ETF research lab for UK university students. In the **Rent-safe Coach**, a student describes their money situation in plain English. An agent checks whether investing is safe for them, calls a verified portfolio engine as tools and compares what-ifs. A separate **Risk Guardian** agent recomputes every figure before the student sees it, and nothing changes in the paper portfolio unless the student approves.

> All portfolios, profiles and prices are fictional or synthetic. This is not financial advice.

## Quick start

```sh
python3 server.py --port 8766 --open     # offline, no API key needed
```

On the Coach page, click **Rent at risk** to see the affordability veto, then **Summer job savings** to see an analysis, a what-if, the Guardian's countersignature and the approval gate.

To run the Coach on Claude, use a standard API key starting with `sk-ant-api03-`:

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
export ANTHROPIC_API_KEY='sk-ant-api03-…'
.venv/bin/python server.py --port 8766 --open
```

## The problem

Students rarely lose money by picking the wrong ETF. They lose it by investing rent or tuition money after someone quotes a big return. Campus Index first asks whether the money can be invested at all, and then what to hold. It always states the return cost of the plan, not just what it protects.

## How it works

Three gates stand between the AI and the money:

1. **Affordability veto (deterministic).** If the money might be needed for essentials, or the student has less than three months of costs in cash, the engine refuses before any prices load.
2. **Risk Guardian (a separate uAgent, no AI model).** It reruns the analysis, matches a SHA-256 digest of the proposal, re-applies the veto and rejects leverage. Every £, % and × figure in the Coach's text must match a fact the Guardian recomputed and the sentence cites.
3. **Human approval.** Only the student can apply a change, and it is recorded once in an append-only SQLite audit.

The Coach (`coach.py`, `tools.py`) quotes the student's own words for every profile fact. It asks rather than assumes when safety facts are missing, and it is capped at 8 tool calls and 3 what-ifs. It has no write tools. It runs on **Claude**, **ASI:One** or a rule-based **offline planner**, chosen automatically, and all three go through the same Guardian. `agents_app.py` runs the Coach and Guardian as uAgents. The Coach speaks the Agentverse chat protocol and requests countersignatures by agent message.

## How we built it

1. **A verified core.** We implemented the RO momentum and volatility signals independently, with student-specific limits, and added an independent verifier (`verifier.py`) to reconcile every output.
2. **Made it agentic.** The original seven fixed steps became the toolset of a real agent, so the verified core stayed untouched.
3. **Added the Guardian** so safety never depends on which model is running.
4. **Tested on unseen data.** We committed 30 fresh seeds by hash before generating any market. Tuning, a 4% retention credit that cut turnover from 19.7× to 12.9×, used disclosed design seeds only.
5. **Fixed the kit adapter honestly.** It now trades from 21 bars instead of 61. We reran a fresh hidden challenge and reported the result as it came out.
6. **Made the demo failure-proof** with the offline planner, then hardened everything with 30 tests.

## Judging criteria

- **Traceable reasoning.** Every fact is quoted from the student. Every figure is a clickable citation to a recomputed fact. Every tool call and verdict goes into an audit that the database refuses to edit or delete.
- **Testing on unseen data.** A hash commitment was written before the markets existed (`backtest_seeds.py verify`). Tuning was kept separate on design seeds, and the kit challenge was rerun on fresh hidden data.
- **Risk controls and oversight.** Veto, then Guardian, then human approval. No write tools for the model. Leverage never reaches approval. The pause control stops everything, and if the Guardian can't be reached, nothing is proposed.
- **Relevance and impact.** It targets the most damaging student mistake, uses GBP UCITS ETFs and plain British English, and reports the return cost honestly.
- **Ambition and technical quality.** Two cooperating uAgents linked by a digest check, three interchangeable AI brains, a hash-committed evaluation and 30 passing tests. The default path needs only the Python standard library.

## Evidence

Results across 30 unseen, hash-committed seeds, for the adopted v1.1 strategy ([full report](evidence/multi-seed/REPORT.md)):

| Measure | Result |
| --- | ---: |
| Lower max drawdown than 60/40 | 100% of seeds (p < 0.001) |
| Median drawdown reduction vs 60/40 | 8.7 pp |
| Median return vs 60/40 | −5.17 pp |
| Median turnover · cost drag | 12.9× · 2.20% |

The finding is **risk reduction, not return**: RO cut the worst fall in every unseen market, and usually gave up some return to do so. In the [kit challenge](evidence/kit-challenge-v2/REPORT.md), the adapter traded on 25 of 60 hidden paths and went 39–21 against buy-and-hold. It avoided every falling and flat market, and entered rising ones late.

## Limitations

- **Live AI calls.** The Claude and ASI:One adapters are built, but neither has run a live conversation yet because we had no funded standard API key. They should work once one is supplied:
  - The same tool loop already runs end to end with the offline planner and a scripted test model.
  - The request format is checked against a stub.
  - Anthropic's API was reachable; the only failure was authentication.
  - Whatever the model writes, the Guardian and the human gate still apply.
- **Synthetic markets.** The evaluation shows the rules behave as designed on data they never saw. It says nothing about how real ETFs will perform. `CAMPUS_PRICE_CSV` accepts licensed prices.
- **Next:** publish seed commitments externally, score a sealed set of student conversations, add scheduled check-ins that draft proposals but never trade, and add an ETF holdings look-through.

## Reproduce

```sh
python3 -m unittest discover -s tests -v
python3 backtest_seeds.py verify
```

Technical details: [TECHNICAL.md](TECHNICAL.md). Sources and data rights: [SOURCES.md](SOURCES.md).
