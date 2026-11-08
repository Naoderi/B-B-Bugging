# Four minute demo

- **0:00–0:30.** The failure we target: a student puts rent money into ETFs because a friend quoted a huge return.
- **0:30–1:30.** On the **Coach** tab, click *Rent at risk*. The Coach quotes the student's words into the profile and calls the verified engine. The affordability veto fires before any prices load. Open the trace: each tool call, quote and Guardian check is there, and in the audit history.
- **1:30–2:30.** Click *Summer job savings*. The Coach runs the analysis plus a what-if, and every figure in its answer is a citation you can expand. The Risk Guardian, a separate deterministic uAgent, reruns everything, matches the digest and countersigns. Click *Review and approve*. The student, not the agent, applies the paper change.
- **2:30–3:20.** Evidence. On 30 unseen markets committed by hash before generation, RO had the lower drawdown in 100% of them (median 8.7 points less than 60/40, p < 0.001). It gave up return: median −5.2 points against 60/40, and −2.7 points against its own limits held statically. We present it as a risk tool, not a return engine.
- **3:20–4:00.** Honesty about the kit. Our first kit run traded on only 1 of 60 paths, so its 39–21 record was cash sitting out falling markets. We fixed the warm-up, reran the hidden challenge, and now trade on 25 of 60 paths. The record is still 39–21, because a trend filter avoids falls and enters rising markets late. Close on the three gates: veto, Guardian, human.

## Two minutes of questions

- **What stops the LLM making up numbers?** The Guardian accepts no £, % or × figure unless it matches a cited fact it recomputed itself. A failed answer goes back once, then gets replaced by a verified template. The model has no tool that writes to the ledger.
- **Could a student talk the coach into leverage?** No. Leverage needs the acknowledgement checkbox in the form. what_if cannot change the rent or leverage answers, and the Guardian rejects any levered proposal.
- **Is "unseen" real?** The seed hash was written before the paths existed (`backtest_seeds.py verify`). The tuning used disclosed design seeds 1–10 only. The limit: the markets are synthetic, and the commitment is local unless published first.
- **What would stronger evidence need?** A licensed point-in-time ETF panel, real execution-cost estimates, and an organiser-sealed holdout.
