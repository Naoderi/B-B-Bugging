"""Single-asset Agentverse signal stress adapter using the website's RO signal.

The kit buys an all-in integer position. It cannot score the multi-ETF
allocator, student suitability, diversification, or the website's paper ledger.
Kit paths are short, so 21 to 60 observations use the labelled short-history
form of RO: the 20- and 5-day terms in their original 35:10 ratio and the same
volatility penalty. The rule was fixed before the rerun recorded in evidence/.
"""
import json
import math
import statistics
import sys

from strategy import daily, ro_signal

SHORT = 21


def short_signal(closes: tuple[float, ...]) -> dict:
    m5, m20 = (closes[-1] / closes[-n - 1] - 1 for n in (5, 20))
    vol = statistics.stdev(daily(closes[-21:]))
    return {"m20": m20, "core": (.35 * m20 + .10 * m5) / .45 - .20 * vol * math.sqrt(20)}


def eligible(closes: tuple[float, ...]) -> bool:
    if len(closes) >= 61:
        scores = ro_signal(closes)
        return min(scores["m20"], scores["m60"], scores["core"]) > 0
    scores = short_signal(closes)
    return min(scores["m20"], scores["core"]) > 0


def handle(request):
    if request.get("task") != "market_step":
        return {"error": "unsupported_task"}
    data = request["input"]
    closes = tuple(row["price_pence"] / 100 for row in data["history"])
    if len(closes) < SHORT:
        return {"output": {"action": "hold"}}
    good = eligible(closes)
    shares = data["shares"]
    action = "buy" if good and not shares else "sell" if shares and not good else "hold"
    return {"output": {"action": action}}


if __name__ == "__main__":
    for line in sys.stdin:
        request = json.loads(line)
        try:
            result = handle(request)
        except (TypeError, KeyError, ValueError, ZeroDivisionError):
            result = {"error": "invalid_input"}
        print(json.dumps({"request_id": request["request_id"], **result}), flush=True)
