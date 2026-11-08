"""Deterministic RO adaptation. User goals enter the fit report, never the score."""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from market import FUNDS, History

POSITION_CAP = .30
POSITION_TARGET = .27  # Headroom for price drift before mandatory repairs
EXPOSURE_CAP = 1.
LEVERAGE_CAP = 2.
TRADE_RATE = .0015  # 10 bp adverse half-spread + 5 bp commission on each traded pound
FINANCING = .055
RETENTION = .04  # Rank credit for held funds (≥3%). Chosen on design seeds, see evidence/multi-seed/DESIGN.md
STRESSES = {
    "Equity sell-off": {"Equity": -.35, "Bond": -.08},
    "Rate shock": {"Equity": -.18, "Bond": -.16},
    "Joint drawdown": {"Equity": -.42, "Bond": -.14},
}
RISK = {
    1: ("Capital preservation", 0., 0.),
    2: ("Defensive", .60, .22),
    3: ("Balanced", .86, .52),
    4: ("Growth", 1., .75),
    5: ("High volatility", 1., .90),
}


def number(value, label: str, lower: float, upper: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"Enter a number for {label}.")
    try:
        value = float(value)
    except (ValueError, OverflowError):
        raise ValueError(f"Enter a number for {label}.") from None
    if not math.isfinite(value) or not lower <= value <= upper:
        raise ValueError(f"{label} must be between {lower:g} and {upper:g}.")
    return value


def pennies(value: float) -> int:
    return int((Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class Profile:
    target: float
    years: float
    budget: int
    monthly: int
    objective: str
    loss: float
    volatility: str
    essential: bool
    runway: float
    leverage: bool
    max_leverage: float
    acknowledged: bool

    @classmethod
    def parse(cls, form: dict) -> Profile:
        if not isinstance(form, dict):
            raise ValueError("Provide a fictional student profile.")
        objective = form.get("objective")
        volatility = form.get("volatility")
        if objective not in ("stability", "balance", "growth") or volatility not in ("low", "moderate", "high"):
            raise ValueError("Choose an objective and a volatility preference.")
        essential, leverage, ack = (form.get(k) for k in ("essential", "leverage", "acknowledged"))
        if any(type(v) is not bool for v in (essential, leverage, ack)):
            raise ValueError("Choose your affordability and leverage preferences.")
        return cls(
            number(form.get("target"), "Annual target (%)", 0, 1_000_000) / 100,
            number(form.get("years"), "Horizon (years)", .25, 50),
            pennies(number(form.get("budget"), "Paper balance (£)", 0, 10_000_000)),
            pennies(number(form.get("monthly"), "Monthly contribution (£)", 0, 100_000)),
            objective, number(form.get("loss"), "Loss tolerance (%)", 0, 95) / 100, volatility,
            essential, number(form.get("runway"), "Cash runway (months)", 0, 60),
            leverage, number(form.get("maxLeverage"), "Maximum simulated leverage", 1, LEVERAGE_CAP), ack,
        )


@dataclass(frozen=True)
class Suitability:
    category: int
    rule: str
    veto: str | None

    @property
    def name(self):
        return RISK[self.category][0]

    @property
    def cap(self):
        return RISK[self.category][1]

    @property
    def equity_cap(self):
        return RISK[self.category][2]


def suitability(profile: Profile) -> Suitability:
    if profile.essential:
        return Suitability(1, "Essential expenses veto", "The fictional funds may be needed for rent, tuition or living expenses.")
    if profile.runway < 3:
        return Suitability(1, "Minimum three-month cash runway", "The fictional emergency reserve covers fewer than three months.")
    if profile.years < 1:
        return Suitability(1, "Minimum one-year horizon", "The fictional funds are needed within one year.")
    if profile.budget <= 0:
        return Suitability(1, "Positive paper balance required", "The fictional portfolio has no capital to allocate.")
    if profile.loss <= 0:
        return Suitability(1, "Positive loss budget required", "Even a defensive ETF allocation can lose value.")
    if profile.years < 3 or profile.loss < .15 or profile.volatility == "low" or profile.objective == "stability":
        return Suitability(2, "Shorter horizon, low tolerance or stability objective", None)
    if profile.years < 5 or profile.loss < .30 or profile.volatility == "moderate" or profile.objective == "balance":
        return Suitability(3, "Balanced objective or moderate risk capacity", None)
    if profile.years < 7 or profile.loss < .45 or profile.runway < 6:
        return Suitability(4, "Growth with a moderate loss budget, runway or horizon", None)
    return Suitability(5, "High tolerance, at least seven years and six months of runway", None)


def daily(prices: tuple[float, ...]) -> list[float]:
    return [b / a - 1 for a, b in zip(prices, prices[1:])]


def ro_signal(prices: tuple[float, ...]) -> dict:
    if len(prices) < 61:
        raise ValueError("At least 61 completed observations are required for RO momentum.")
    m5, m20, m60 = (prices[-1] / prices[-n-1] - 1 for n in (5, 20, 60))
    vol = statistics.stdev(daily(prices[-21:]))
    core = .55 * m60 + .35 * m20 + .10 * m5 - .20 * vol * math.sqrt(20)
    return {"m5": m5, "m20": m20, "m60": m60, "vol20": vol * math.sqrt(252), "core": core,
            "close": prices[-1], "base5": prices[-6], "base20": prices[-21], "base60": prices[-61]}


def metrics(returns: list[float], risk_free: float = .03) -> dict:
    wealth, peak, drawdown = 1., 1., 0.
    curve = [wealth]
    for ret in returns:
        wealth *= 1 + ret
        peak = max(peak, wealth)
        drawdown = max(drawdown, 1 - wealth / peak)
        curve.append(wealth)
    volatility = statistics.stdev(returns) * math.sqrt(252)
    cash_daily = (1 + risk_free) ** (1 / 252) - 1
    return {
        "total": wealth - 1, "annualised": wealth ** (252 / len(returns)) - 1,
        "volatility": volatility, "drawdown": drawdown,
        "sharpe": (statistics.mean(returns) - cash_daily) * 252 / volatility if volatility else None,
        "curve": curve,
    }


def portfolio_returns(history: History, weights: dict[str, float]) -> list[float]:
    count = len(history.dates) - 1
    series = {ticker: daily(history.prices[ticker]) for ticker in weights if weights[ticker]}
    fee = 0 if history.embedded_fee else sum(FUNDS[ticker].fee * weights[ticker] for ticker in series) / 252
    return [sum(values[t] * weights[ticker] for ticker, values in series.items()) - fee for t in range(count)]


def stress(weights: dict[str, float]) -> dict[str, float]:
    return {name: -sum(shocks[FUNDS[t].asset] * w for t, w in weights.items()) for name, shocks in STRESSES.items()}


def correlate(a: list[float], b: list[float]) -> float:
    if not statistics.pvariance(a) or not statistics.pvariance(b):
        return 0.
    return statistics.correlation(a, b)


def turnover(current: dict[str, float], target: dict[str, float]) -> float:
    traded = sum(abs(target.get(k, 0) - current.get(k, 0)) for k in current.keys() | target.keys())
    return (traded + abs(sum(current.values()) - sum(target.values()))) / 2


def weight_limits(weights: dict[str, float], risk: Suitability) -> bool:
    group = {}
    for ticker, weight in weights.items():
        if ticker not in FUNDS or not math.isfinite(weight) or not 0 <= weight <= POSITION_CAP + 1e-10:
            return False
        group[FUNDS[ticker].group] = group.get(FUNDS[ticker].group, 0) + weight
    equity = sum(w for t, w in weights.items() if FUNDS[t].asset == "Equity")
    return (sum(weights.values()) <= min(EXPOSURE_CAP, risk.cap) + 1e-10
            and equity <= risk.equity_cap + 1e-10 and max(group.values(), default=0) <= POSITION_CAP + 1e-10)


def allocate(history: History, profile: Profile, current: dict[str, float], risk: Suitability) -> dict:
    scores = {ticker: ro_signal(prices) for ticker, prices in history.prices.items()}
    if not {"Equity", "Bond"} <= {FUNDS[t].asset for t in scores}:
        raise ValueError("Both equity and bond prices are required for a diversified recommendation.")
    equities = [s for t, s in scores.items() if FUNDS[t].asset == "Equity"]
    breadth = sum(s["m20"] > 0 for s in equities) / len(equities)
    scale = .65 if breadth < .35 else .85 if breadth < .50 else 1.
    for ticker, s in scores.items():
        # Same dimensionless return units as RO. Annual OCF and 15 bp execution
        # proxy are a modest rank penalty. Existing weights reduce churn.
        s["costPenalty"] = FUNDS[ticker].fee + TRADE_RATE
        s["retentionCredit"] = RETENTION if current.get(ticker, 0) >= .03 else 0
        s["score"] = s["core"] - s["costPenalty"] + s["retentionCredit"]
    desired_equity = max(0., risk.equity_cap * scale - .02)
    sleeves = {"Equity": desired_equity, "Bond": max(0, (risk.cap - risk.equity_cap) * scale)}
    weights: dict[str, float] = {}
    exclusions = {t: "Completed GBP history unavailable." for t in FUNDS.keys() - scores.keys()}
    ordered = sorted(scores, key=lambda t: (-scores[t]["score"], t))
    groups: set[str] = set()
    return_series = {t: daily(history.prices[t][-61:]) for t in scores}
    for ticker in ordered:
        s, fund = scores[ticker], FUNDS[ticker]
        if ticker in {"IITU", "IUKP", "CNX1"} and risk.category < 4:
            exclusions[ticker] = "Sector or concentrated index exposure requires risk category 4 or 5."
        elif fund.asset == "Equity" and (min(s["m20"], s["m60"], s["score"]) <= 0):
            exclusions[ticker] = "Equity trend gate needs positive 20-day and 60-day momentum and a positive adjusted score."
        elif sleeves[fund.asset] < .01:
            exclusions[ticker] = "Higher-ranked funds filled the sleeve or the profile has no budget for it."
        elif fund.group in groups:
            exclusions[ticker] = "A higher-ranked ETF already covers this exposure group."
        elif any(correlate(return_series[ticker], return_series[t]) >= .95 for t in weights):
            exclusions[ticker] = "60-day returns correlated ≥0.95 with an earlier pick. Holdings overlap remains unresolved."
        else:
            weights[ticker] = min(POSITION_TARGET, sleeves[fund.asset])
            sleeves[fund.asset] -= weights[ticker]
            groups.add(fund.group)

    rule = "Allocate by sleeve and scale risky exposure down to meet the loss budget."
    worst = max(stress(weights).values(), default=0.)
    loss_budget = max(0., profile.loss - .003)
    if worst > loss_budget and worst > 0:
        weights = {t: w * loss_budget / worst for t, w in weights.items()}
    observed = metrics(portfolio_returns(history, weights))["drawdown"]
    if observed > loss_budget:
        # Geometric drawdown is nonlinear in exposure. Verify each reduction.
        for _ in range(15):
            weights = {t: w * .75 for t, w in weights.items()}
            if metrics(portfolio_returns(history, weights))["drawdown"] <= loss_budget:
                break
        else:
            weights = {}
    weights = {t: w for t, w in weights.items() if w >= .005}
    delta = max((abs(current.get(t, 0) - weights.get(t, 0)) for t in current.keys() | weights.keys()), default=0)
    if (current and turnover(current, weights) < .10 and delta < .05
            and sum(current.values()) <= sum(weights.values()) + .10 and weight_limits(current, risk)
            and max(stress(current).values()) <= loss_budget
            and metrics(portfolio_returns(history, current))["drawdown"] <= loss_budget):
        weights = dict(current)
        rule = "Keep the current positions inside the 10% turnover and 5% per-position review bands."
    return {"weights": weights, "scores": scores, "exclusions": exclusions,
            "breadth": breadth, "scale": scale, "rule": rule}


def settle(budget: int, current: dict[str, int], target: dict[str, float]) -> tuple[dict[str, int], int, int, int]:
    """Resolve target pennies after costs. Fractional paper quantities are supported."""
    fee = 0
    for _ in range(20):
        positions = {t: math.floor((budget - fee) * w + 1e-12) for t, w in target.items()}
        traded = sum(abs(positions.get(t, 0) - current.get(t, 0)) for t in positions.keys() | current.keys())
        new_fee = (traded * 15 + 5_000) // 10_000
        if new_fee == fee:
            positions = {t: v for t, v in positions.items() if v > 0}
            return positions, budget - fee - sum(positions.values()), fee, traded
        fee = new_fee
    raise ValueError("Transaction costs did not converge to a consistent penny total.")


def leverage_scenario(profile: Profile, risk: Suitability, history: History, weights: dict[str, float]) -> dict:
    maximum = min(LEVERAGE_CAP, profile.max_leverage)
    if not profile.leverage or maximum <= 1:
        return {"state": "off", "maximum": 1., "reason": "Standard paper portfolios use at most 1.0× exposure."}
    if not profile.acknowledged or risk.category < 5 or risk.veto or not weights:
        return {"state": "veto", "maximum": 1., "reason": "Exploration needs acknowledgement, high loss tolerance, seven years and six months of cash runway."}
    raw = portfolio_returns(history, weights)
    exposure = sum(weights.values()) * maximum
    financed = max(0., exposure - 1)
    path = [maximum * r - financed * FINANCING / 252 for r in raw]
    scenario_stress = max(stress(weights).values()) * maximum + .003 * maximum
    drawdown = metrics(path)["drawdown"]
    facts = {"requested": maximum, "stress": scenario_stress, "drawdown": drawdown, "financing": FINANCING,
             "grossExposure": exposure}
    if max(scenario_stress, drawdown) > profile.loss or max(weights.values()) * maximum > POSITION_CAP:
        return {**facts, "state": "veto", "maximum": 1.,
                "reason": "Scaled positions breach the 30% cap or the modelled loss exceeds your stated limit."}
    return {**facts, "state": "preview", "maximum": maximum,
            "reason": "Daily-reset synthetic exposure illustration. Paper approval applies only to the unlevered allocation."}


def fit(target: float, observed: float | None, blocked: bool = False) -> str:
    if blocked:
        return "No suitable allocation under the affordability or data rules."
    if target >= 1:
        return "A 100%+ annual objective is exceptionally aggressive. The evidence does not support it."
    if observed is None or target > max(0, observed):
        return "The objective exceeds the annualised result in this price sample."
    return "The objective is within the annualised sample result. Future returns remain uncertain and losses can exceed your limit."
