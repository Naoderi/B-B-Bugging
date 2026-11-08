# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

**Primary: hackathon judges** at the Agentverse Hackathon (7–8 November 2026, Finance Track). They watch a live four-minute demo followed by two minutes of questions (`evidence/PITCH-NOTES.md`), then may open the app or the pitch deck themselves. Their job is to see quickly what the agent does, trust that its figures are real, and score it against the track rubric.

**Portrayed user: a UK university student** with fictional finances, deciding whether money for rent and essentials can safely go into ETFs. The app must read as credible for that student, but demo clarity for judges takes priority when the two conflict.

## Product Purpose

Campus Index is a paper ETF research lab. It checks whether a fictional investing plan leaves enough room for rent, analyses completed price observations and needs the student's explicit approval before it changes the paper ledger. Success means judges understand the three gates (affordability veto, Risk Guardian countersign, human approval) and believe the evidence within the demo window.

Scope is the hackathon only. Design decisions don't need to hold beyond judging.

## Positioning

The model never produces a number the system hasn't verified. The Rent-safe Coach (Claude, ASI:One or an offline planner) only chooses tools and writes text. A separate deterministic Risk Guardian uAgent reruns the analysis, matches the proposal digest and rejects any £, % or × figure that doesn't match a cited fact it recomputed. Only the student can apply a change. The evidence is about risk reduction, not returns: lower drawdown than 60/40 in 30 of 30 unseen, hash-committed synthetic markets, while giving up return (median −5.2 pp against 60/40).

## Operating Context

- Runs locally: `python3 server.py --port 8766` serves `web/index.html` on loopback. There is also a Finder launcher, `Start Campus Index.command`.
- App tabs include **Coach**, **Paper portfolio** (stop control, approved snapshot) and **Benchmark evidence**.
- Demo presets: *Balanced student*, *Aggressive student*, *Rent at risk*, *Summer job savings*.
- `web/pitch.html` is a self-contained browser deck with a print layout, linked from the Benchmark evidence tab.
- The demo follows the scripted sequence in `evidence/PITCH-NOTES.md`. It has to work offline with no API key.

## Capabilities and Constraints

- The Coach quotes the student's own words into the profile and asks rather than assumes when rent exposure, cash runway or horizon are missing. It can run up to three what-ifs and is capped at eight tool calls.
- Every figure in the Coach's answer is an expandable citation. Tool calls, quotes and Guardian verdicts appear in a trace and in an append-only audit.
- The leverage scenario (up to 2.0×) needs an explicit acknowledgement and never reaches the approval gate.
- Students can enter positions manually or upload a CSV (`ticker,quantity` or `isin,quantity`), and the mapping must be confirmed.
- The frontend is plain HTML/CSS/JS with no build step. The server uses only the Python standard library by default.
- All portfolios, profiles and prices are fictional or synthetic. This is not financial advice.

## Brand Commitments

- Name: **Campus Index**.
- Voice: plain British English. Cautious, cited and free of hype. Present the product as a risk tool, not a return engine, and keep the not-financial-advice framing.

## Evidence on Hand

- Multi-seed unseen-market evaluation: `evidence/multi-seed/REPORT.md`, `DESIGN.md`, `SEED-REVEAL.txt`.
- Original demo-seed replay: `evidence/benchmark.json`.
- Kit challenge runs: `evidence/kit-challenge/`, `evidence/kit-challenge-v2/` (39–21 against buy-and-hold, honestly explained).
- Source and licence register: `SOURCES.md`.
- **There is none of the following, and none may be fabricated:** real users, testimonials, real ETF price data, live performance, issuer logos or price data.

## Product Principles

1. **Every figure is traceable.** Nothing numeric appears without a citation back to a recomputed fact.
2. **Honest over impressive.** Show the return cost and the kit limits next to the drawdown win.
3. **The human applies the change.** Agents propose and check, and only the student approves.
4. **The demo must not fail.** The offline path is a first-class experience, not a fallback.
