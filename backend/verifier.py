"""Independent reconciliation of results before they can reach paper execution."""
from decimal import Decimal, ROUND_HALF_UP
import math

from market import FUNDS, History
from strategy import Profile, Suitability, RISK, STRESSES


def verify(history: History, profile: Profile, risk: Suitability, current: dict, weights: dict,
           positions: dict, cash: int, fee: int, shown: dict, scores: dict) -> list[str]:
    if risk.veto:
        raise ValueError("Verification rejected an affordability veto.")
    if (history.dates[-1] != history.cutoff or any(d > history.cutoff for d in history.dates)
            or any(a >= b for a, b in zip(history.dates, history.dates[1:]))):
        raise ValueError("Verification rejected future, stale or misordered observations.")
    if any(t not in history.prices or t not in FUNDS for t in current.keys() | positions.keys() | weights.keys()):
        raise ValueError("Verification rejected an unverified instrument or quote.")
    nav = profile.budget - fee
    if nav <= 0 or cash < 0 or sum(positions.values()) + cash + fee != profile.budget:
        raise ValueError("Verification could not reconcile GBP position values, cash and costs.")
    for ticker, value in positions.items():
        if type(value) is not int or value <= 0 or abs(value - nav * weights[ticker]) > 1.0001:
            raise ValueError("Verification rejected a GBP position value.")
    if any(t not in positions and nav * w >= 1.0001 for t, w in weights.items()):
        raise ValueError("Verification found an omitted funded position.")
    gross = sum(positions.values()) / nav
    exposure, equity = RISK[risk.category][1:]
    groups = {fund.group for fund in FUNDS.values()}
    if (gross > min(exposure, 1.0) + 1e-10 or any(v / nav > .30 + 1e-10 for v in positions.values())
            or sum(v for t, v in positions.items() if FUNDS[t].asset == "Equity") / nav > equity + 1e-10
            or any(sum(v for t, v in positions.items() if FUNDS[t].group == g) / nav > .30 + 1e-10 for g in groups)):
        raise ValueError("Verification rejected an exposure or concentration breach.")
    traded = sum(abs(current.get(t, 0) - positions.get(t, 0)) for t in current.keys() | positions.keys())
    expected_fee = int((Decimal(traded) * Decimal("0.0015")).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    if expected_fee != fee:
        raise ValueError("Verification disagreed on paper transaction costs.")
    n = len(history.dates) - 1
    fee_drag = math.fsum(positions[t] / nav * FUNDS[t].fee for t in positions)
    returns = []
    for i in range(n):
        changes = ((history.prices[t][i + 1] - history.prices[t][i]) / history.prices[t][i] * v / nav
                   for t, v in positions.items())
        returns.append(math.fsum(changes) - (0 if history.embedded_fee else fee_drag / 252))
    mean = math.fsum(returns) / n
    vol = math.sqrt(math.fsum((r - mean) ** 2 for r in returns) / (n - 1) * 252)
    drawdown = 0.
    accumulated = 0.
    peak = 0.
    for change in returns:
        accumulated += math.log1p(change)
        peak = max(peak, accumulated)
        drawdown = max(drawdown, -math.expm1(accumulated - peak))
    for label, expected in {"volatility": vol, "drawdown": drawdown, "annualised": math.expm1(accumulated * 252 / n),
                            "total": math.expm1(accumulated), "feeDrag": fee_drag}.items():
        if not math.isclose(shown[label], expected, abs_tol=1e-9):
            raise ValueError(f"Independent recomputation disagreed on {label}.")
    losses = {k: -math.fsum(v * shocks[FUNDS[t].asset] / nav for t, v in positions.items())
              for k, shocks in STRESSES.items()}
    if (any(not math.isclose(v, shown["stress"][k], abs_tol=1e-9) for k, v in losses.items())
            or max([drawdown, *losses.values()]) + fee / profile.budget > profile.loss + 1e-10):
        raise ValueError("Verification rejected a stress result or loss-budget breach.")
    for ticker, report in scores.items():
        prices = history.prices[ticker]
        momenta = [(prices[-1] - prices[-i - 1]) / prices[-i - 1] for i in (5, 20, 60)]
        one_day = [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(len(prices) - 20, len(prices))]
        center = math.fsum(one_day) / 20
        sigma = math.sqrt(math.fsum((r - center) ** 2 for r in one_day) / 19)
        score = .10 * momenta[0] + .35 * momenta[1] + .55 * momenta[2] - .20 * sigma * math.sqrt(20)
        actual = [report[k] for k in ("m5", "m20", "m60", "vol20", "core", "score")]
        expected = [*momenta, sigma * math.sqrt(252), score, score - FUNDS[ticker].fee - .0015
                    + (.04 if current.get(ticker, 0) / profile.budget >= .03 else 0)]
        if any(not math.isclose(a, b, abs_tol=1e-9) for a, b in zip(actual, expected)):
            raise ValueError(f"Independent recomputation disagreed on the {ticker} RO score.")
    return ["Completed observations only", "GBP and transaction costs reconciled", "Position, group and exposure caps",
            "Risk and loss metrics independently recomputed", "RO signals independently recomputed"]
