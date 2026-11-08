"""Frozen chronological RO replay with next-close fills and transparent benchmarks."""
from __future__ import annotations

import json
import math
from functools import lru_cache

from agent import BASE
from market import FUNDS, LOOKBACK, load_history
from strategy import (POSITION_TARGET, TRADE_RATE, Profile, allocate, metrics, ro_signal,
                      suitability, turnover, weight_limits)

RF = .03
WINDOW = 252


def path(history, kind, start):
    profile = Profile.parse(BASE)
    risk = suitability(profile)
    weights = {}
    value = 1.
    returns = []
    costs = []
    trades = []
    checks = []
    for t in range(start, len(history.dates)):
        target = None
        if kind == "ro":
            observed = history.prefix(t)
            assert observed.dates[-1] < history.dates[t]
            if not weight_limits(weights, risk):
                # Cap repair trims the drifted exposures without rotating ETFs.
                groups = {fund.group for fund in FUNDS.values()}
                totals = {g: sum(w for k, w in weights.items() if FUNDS[k].group == g) for g in groups}
                target = {k: w * min(1., POSITION_TARGET / totals[FUNDS[k].group]) for k, w in weights.items()}
                equity = sum(w for k, w in target.items() if FUNDS[k].asset == "Equity")
                if equity > risk.equity_cap:
                    target = {k: w * (risk.equity_cap - .02) / equity if FUNDS[k].asset == "Equity" else w
                              for k, w in target.items()}
                total = sum(target.values())
                if total > risk.cap:
                    target = {k: w * (risk.cap - .02) / total for k, w in target.items()}
            elif (t - start) % 21 == 0:
                desired = allocate(observed, profile, weights, risk)["weights"]
                if turnover(weights, desired) >= .10 or max(
                        (abs(desired.get(k, 0) - weights.get(k, 0)) for k in weights.keys() | desired.keys()), default=0
                ) >= .05 or t == start:
                    target = desired
            elif weights:
                # Recheck breadth between scheduled reviews for significant exposure drops.
                signals = [ro_signal(prices[t - 61:t]) for ticker, prices in history.prices.items() if FUNDS[ticker].asset == "Equity"]
                breadth = sum(s["m20"] > 0 for s in signals) / len(signals)
                scale = .65 if breadth < .35 else .85 if breadth < .50 else 1.
                cap = risk.cap * scale
                if sum(weights.values()) > cap + .10:
                    target = {ticker: weight * cap / sum(weights.values()) for ticker, weight in weights.items()}
            if target is not None:
                passed = weight_limits(target, risk)
                checks.append(passed)
                if not passed:
                    raise RuntimeError("Replay attempted to emit an invalid target.")
        elif kind == "equity":
            if t == start:
                target = {"VWRP": 1.}
        elif kind == "balanced" and (t - start) % 21 == 0:
            target = {"VWRP": .60, "VAGS": .40}
        elif kind == "policy" and (t - start) % 21 == 0:
            # The RO profile's own equity and fund caps held statically: what the limits give without signals.
            target = {"VWRP": risk.equity_cap - .02, "VAGS": risk.cap - risk.equity_cap}

        moved = {ticker: w * history.prices[ticker][t] / history.prices[ticker][t - 1]
                 for ticker, w in weights.items()}
        ongoing = 0 if history.embedded_fee else sum(FUNDS[k].fee * w for k, w in weights.items()) / 252
        gross = 1 - sum(weights.values()) + sum(moved.values()) - ongoing
        weights = {ticker: w / gross for ticker, w in moved.items()}
        traded, cost = 0., 0.
        if target is not None:
            traded = sum(abs(target.get(k, 0) - weights.get(k, 0)) for k in weights.keys() | target.keys())
            cost = traded * TRADE_RATE
            # At execution, post-fee weights are the declared targets. Iterate the
            # fee until the bought/sold notional and the reduced NAV agree.
            for _ in range(12):
                traded = sum(abs(target.get(k, 0) * (1 - cost) - weights.get(k, 0))
                             for k in weights.keys() | target.keys())
                cost = traded * TRADE_RATE
            weights = target
        costs.append((ongoing + gross * cost) * value)
        trades.append(traded)
        returns.append(gross * (1 - cost) - 1)
        value *= 1 + returns[-1]
    result = metrics(returns, RF)
    result["costDrag"] = math.fsum(costs)
    result["turnover"] = math.fsum(trades)
    result["compliance"] = sum(checks) / len(checks) if checks else None
    result["decisionCount"] = len(checks)
    windows = []
    for offset in range(0, len(returns) - WINDOW + 1, WINDOW):
        stop = offset + WINDOW
        block = metrics(returns[offset:stop], RF)
        block.pop("curve")
        block["costDrag"] = math.fsum(costs[offset:stop]) / result["curve"][offset]
        block["turnover"] = math.fsum(trades[offset:stop])
        windows.append(block)
    result["windows"] = windows
    result["windowReturns"] = [block["total"] for block in windows]
    result["curve"] = [*result["curve"][::7], result["curve"][-1]]
    return result


@lru_cache(maxsize=1)
def offline_evidence():
    return evaluate()


def evaluate(history=None):
    history = history or load_history(full=True)
    if len(history.dates) < LOOKBACK + WINDOW:
        raise ValueError("Benchmark replay requires 200 warm-up observations and at least 252 later observations.")
    if not {"VWRP", "VAGS"} <= history.prices.keys():
        raise ValueError("Benchmark replay needs completed histories for VWRP and VAGS.")
    start = LOOKBACK
    length = ((len(history.dates) - start) // WINDOW) * WINDOW
    history = history.prefix(start + length, start + length)
    paths = [
        {"name": "Campus Index RO", **path(history, "ro", start)},
        {"name": "Global equity buy & hold", **path(history, "equity", start)},
        {"name": "60/40 global equity & bonds", **path(history, "balanced", start)},
    ]
    return {"strategyVersion": "campus-ro-1.1", "paths": paths, "observations": length, "warmup": start,
            "first": history.dates[start].isoformat(), "last": history.dates[-1].isoformat(),
            "synthetic": history.synthetic, "source": history.source, "riskFree": RF, "feeRate": TRADE_RATE,
            "windowSize": WINDOW, "difference": paths[0]["total"] - paths[2]["total"],
            "notes": [
                "Rules are fixed before the replay. Every decision uses at most 200 earlier closes. Execution uses the next close.",
                "The RO portfolio reviews every 21 observations, with between-review repairs. The 60/40 benchmark rebalances every 21 observations. Global equity buys once.",
                "Every fill includes 10 bp adverse half-spread and 5 bp commission. Synthetic paths deduct issuer OCF daily. Approved adjusted price files already embed OCF.",
                "Paper cash earns 0%. Sharpe uses an assumed constant 3% annual GBP reference rate and 252 observations per year.",
                "Calendar windows share one market path. Their result ranges show variation across regimes, with limited statistical power.",
            ]}


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2, allow_nan=False))
