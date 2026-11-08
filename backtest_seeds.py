"""Multi-seed replay with a design/evaluation split and a seed commitment.

    python3 backtest_seeds.py design      # disclosed seeds 1-10, used to choose the retention margin
    python3 backtest_seeds.py challenge   # 30 fresh seeds, committed by hash before any result exists
    python3 backtest_seeds.py verify      # recompute the commitment from the revealed seeds
    python3 backtest_seeds.py report      # re-render REPORT.md from the saved summary (no new seeds)
"""
from __future__ import annotations

import hashlib
import json
import math
import secrets
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path

import backtest
import strategy
from market import SEED, demo_history, validate

HERE = Path(__file__).parent
OUT = HERE / "evidence" / "multi-seed"
DESIGN_SEEDS = tuple(range(1, 11))
DESIGN_GRID = (.005, .01, .02, .04)
VERSIONS = {"campus-ro-1.0": .005, "campus-ro-1.1": .04}  # 1.1 chosen on design seeds only, see DESIGN.md
ADOPTED = "campus-ro-1.1"
RULE_FILES = ("strategy.py", "backtest.py", "market.py", "backtest_seeds.py")


def replay(seed: int, retention: float) -> dict:
    live, strategy.RETENTION = strategy.RETENTION, retention
    try:
        history = demo_history(seed=seed)
        validate(history)
        ro, equity, balanced = backtest.evaluate(history)["paths"]
        length = ((len(history.dates) - backtest.LOOKBACK) // backtest.WINDOW) * backtest.WINDOW
        policy = backtest.path(history.prefix(backtest.LOOKBACK + length, backtest.LOOKBACK + length), "policy", backtest.LOOKBACK)
    finally:
        strategy.RETENTION = live
    return {"seed": seed, "retention": retention, "roTotal": ro["total"], "balancedTotal": balanced["total"],
            "policyTotal": policy["total"], "policyDrawdown": policy["drawdown"],
            "excessPolicy": ro["total"] - policy["total"], "drawdownVsPolicy": policy["drawdown"] - ro["drawdown"],
            "equityTotal": equity["total"], "roDrawdown": ro["drawdown"], "balancedDrawdown": balanced["drawdown"],
            "equityDrawdown": equity["drawdown"], "roVolatility": ro["volatility"], "balancedVolatility": balanced["volatility"],
            "roTurnover": ro["turnover"], "roCostDrag": ro["costDrag"], "compliance": ro["compliance"],
            "excess": ro["total"] - balanced["total"], "drawdownReduction": balanced["drawdown"] - ro["drawdown"]}


def sign_test(wins: int, n: int) -> float:
    tail = sum(math.comb(n, k) for k in range(min(wins, n - wins) + 1)) / 2 ** n
    return min(1., 2 * tail)


def quartiles(values: list[float]) -> tuple[float, float, float]:
    q1, q2, q3 = statistics.quantiles(values, n=4, method="inclusive")
    return q1, q2, q3


def summarise(rows: list[dict]) -> dict:
    n = len(rows)
    wins = sum(r["excess"] > 0 for r in rows)
    dd_wins = sum(r["drawdownReduction"] > 0 for r in rows)
    excess, reduction = [r["excess"] for r in rows], [r["drawdownReduction"] for r in rows]
    return {"seeds": n, "medianExcess": statistics.median(excess), "excessIQR": quartiles(excess)[::2],
            "returnWinRate": wins / n, "returnSignP": sign_test(wins, n),
            "medianDrawdownReduction": statistics.median(reduction), "drawdownIQR": quartiles(reduction)[::2],
            "drawdownWinRate": dd_wins / n, "drawdownSignP": sign_test(dd_wins, n),
            "medianTurnover": statistics.median(r["roTurnover"] for r in rows),
            "medianCostDrag": statistics.median(r["roCostDrag"] for r in rows),
            "medianRoTotal": statistics.median(r["roTotal"] for r in rows),
            "medianBalancedTotal": statistics.median(r["balancedTotal"] for r in rows),
            "medianPolicyTotal": statistics.median(r["policyTotal"] for r in rows),
            "medianExcessPolicy": statistics.median(r["excessPolicy"] for r in rows),
            "excessPolicyIQR": quartiles([r["excessPolicy"] for r in rows])[::2],
            "policyWinRate": sum(r["excessPolicy"] > 0 for r in rows) / n,
            "policySignP": sign_test(sum(r["excessPolicy"] > 0 for r in rows), n),
            "medianDrawdownVsPolicy": statistics.median(r["drawdownVsPolicy"] for r in rows),
            "policyDrawdownWinRate": sum(r["drawdownVsPolicy"] > 0 for r in rows) / n,
            "compliance": min(r["compliance"] for r in rows),
            "worstSeed": min(rows, key=lambda r: r["excess"])["seed"]}


def rules_digest() -> dict:
    files = {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in RULE_FILES}
    return {"files": files, "versions": VERSIONS, "adopted": ADOPTED}


def commitment(seeds: list[int], nonce: str) -> str:
    return hashlib.sha256(json.dumps({"seeds": seeds, "nonce": nonce}, sort_keys=True).encode()).hexdigest()


def design():
    print("Design seeds", DESIGN_SEEDS, "(disclosed; never reused for evaluation)")
    for retention in DESIGN_GRID:
        s = summarise([replay(seed, retention) for seed in DESIGN_SEEDS])
        print(f"retention {retention:.3f}: median excess vs 60/40 {s['medianExcess'] * 100:+.2f} pp, "
              f"return wins {s['returnWinRate']:.0%}, median drawdown cut {s['medianDrawdownReduction'] * 100:.1f} pp, "
              f"median turnover {s['medianTurnover']:.1f}x, median cost drag {s['medianCostDrag'] * 100:.2f}%")


def pvalue(p: float) -> str:
    return "<0.001" if p < .001 else f"{p:.3f}"


def pct(value: float, places: int = 1) -> str:
    return f"{value * 100:+.{places}f}"


def report(summary: dict, stamp: str, digest: str) -> str:
    lines = ["# Multi-seed unseen-path evaluation", "",
             f"Run {stamp}. {summary['n']} evaluation seeds drawn with `secrets` after the rules were fixed. "
             f"Seed commitment `{digest}` was written to `COMMITMENT.txt` before any path was generated. "
             "Seeds and nonce are in `SEED-REVEAL.txt`; `python3 backtest_seeds.py verify` recomputes the hash.", "",
             "Each seed generates a new 956-observation synthetic GBP market with its own noise and a shuffled order of the "
             "eight drift regimes. The design seeds 1-10, used to choose the retention margin, are excluded. "
             "Rules, costs and the 200-observation warm-up match `backtest.py`. Balanced student profile, risk category 3.", "",
             "| Version | Median RO − 60/40 (pp) | IQR (pp) | RO beats 60/40 | Sign-test p | Median drawdown cut (pp) | "
             "Drawdown lower | Sign-test p | Median turnover | Median cost drag | Limit checks |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for name, s in summary["versions"].items():
        lo, hi = s["excessIQR"]
        dlo, dhi = s["drawdownIQR"]
        lines.append(f"| {name}{' (adopted)' if name == ADOPTED else ''} | {pct(s['medianExcess'], 2)} | {pct(lo, 1)} to {pct(hi, 1)} | "
                     f"{s['returnWinRate']:.0%} | {pvalue(s['returnSignP'])} | {pct(s['medianDrawdownReduction'])} "
                     f"({pct(dlo)} to {pct(dhi)}) | {s['drawdownWinRate']:.0%} | {pvalue(s['drawdownSignP'])} | "
                     f"{s['medianTurnover']:.1f}× | {s['medianCostDrag'] * 100:.2f}% | {s['compliance']:.0%} |")
    lines += ["", "## Do the signals beat the profile's own limits?", "",
              "The policy benchmark holds the Balanced profile's caps without any signal: 50% VWRP, 34% VAGS, 16% cash, "
              "rebalanced every 21 observations with the same costs. It isolates what the RO timing adds.", "",
              "| Version | Median RO − policy (pp) | IQR (pp) | RO beats policy | Sign-test p | Median drawdown cut vs policy (pp) | Drawdown lower |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for name, s in summary["versions"].items():
        lo, hi = s["excessPolicyIQR"]
        lines.append(f"| {name} | {pct(s['medianExcessPolicy'], 2)} | {pct(lo, 1)} to {pct(hi, 1)} | {s['policyWinRate']:.0%} | "
                     f"{pvalue(s['policySignP'])} | {pct(s['medianDrawdownVsPolicy'])} | {s['policyDrawdownWinRate']:.0%} |")
    a = summary["versions"][ADOPTED]
    lines += ["", "## Reading the result", "",
              f"- Median net return over 756 forward observations: RO {a['medianRoTotal'] * 100:.1f}%, "
              f"policy benchmark {a['medianPolicyTotal'] * 100:.1f}%, 60/40 {a['medianBalancedTotal'] * 100:.1f}%.",
              f"- The worst seed for {ADOPTED} relative to 60/40 was {a['worstSeed']}.",
              "- These are generated markets. They test whether the rules behave as designed on sequences they never saw, "
              "not whether any real ETF will perform this way.", ""]
    return "\n".join(lines)


def challenge(count: int = 30):
    OUT.mkdir(parents=True, exist_ok=True)
    seeds = []
    while len(seeds) < count:
        seed = secrets.randbelow(2 ** 31)
        if seed not in DESIGN_SEEDS and seed != SEED and seed not in seeds:
            seeds.append(seed)
    nonce = secrets.token_hex(16)
    digest = commitment(seeds, nonce)
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    (OUT / "COMMITMENT.txt").write_text(
        f"{digest}\ncommitted {stamp}\nrules {json.dumps(rules_digest(), sort_keys=True)}\n", encoding="utf-8")
    rows = [replay(seed, retention) | {"version": name} for seed in seeds for name, retention in VERSIONS.items()]
    (OUT / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    versions = {name: summarise([r for r in rows if r["version"] == name]) for name in VERSIONS}
    summary = {**versions[ADOPTED], "adopted": ADOPTED, "versions": versions, "n": count,
               "commitment": digest, "completed": datetime.now(UTC).isoformat(timespec="seconds")}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT / "SEED-REVEAL.txt").write_text(json.dumps({"seeds": seeds, "nonce": nonce}) + "\n", encoding="utf-8")
    (OUT / "REPORT.md").write_text(report(summary, stamp, digest), encoding="utf-8")
    print((OUT / "REPORT.md").read_text(encoding="utf-8"))


def verify():
    reveal = json.loads((OUT / "SEED-REVEAL.txt").read_text(encoding="utf-8"))
    committed = (OUT / "COMMITMENT.txt").read_text(encoding="utf-8").split()[0]
    ok = commitment(reveal["seeds"], reveal["nonce"]) == committed
    print("Commitment matches revealed seeds." if ok else "Commitment MISMATCH.")
    return ok


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "design":
        design()
    elif mode == "challenge":
        challenge()
    elif mode == "report":
        saved = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
        stamp = (OUT / "COMMITMENT.txt").read_text(encoding="utf-8").splitlines()[1].removeprefix("committed ")
        (OUT / "REPORT.md").write_text(report(saved, stamp, saved["commitment"]), encoding="utf-8")
    elif mode == "verify":
        sys.exit(0 if verify() else 1)
    else:
        sys.exit(__doc__)
