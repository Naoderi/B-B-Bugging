"""The analysis workflow and its decision evidence."""
from __future__ import annotations

import csv
import io
from dataclasses import asdict

from market import FUNDS, IDENTIFIERS, load_history
from strategy import (Profile, allocate, fit, leverage_scenario, metrics, number,
                      pennies, portfolio_returns, settle, stress, suitability, turnover)
from verifier import verify

BASE = {"target": 5, "years": 3, "budget": 2000, "monthly": 100, "objective": "balance", "loss": 20,
        "volatility": "moderate", "essential": False, "runway": 4, "leverage": False, "maxLeverage": 1,
        "acknowledged": False, "mode": "zero", "positions": [], "csv": "", "mappingConfirmed": False}
PRESETS = {
    "conservative": {"label": "Conservative student", "caption": "3% target · stability first",
                     "form": {**BASE, "target": 3, "years": 2, "budget": 1200, "monthly": 40,
                              "objective": "stability", "loss": 10, "volatility": "low"}},
    "balanced": {"label": "Balanced student", "caption": "5% target · 3-year horizon", "form": BASE},
    "aggressive": {"label": "Aggressive student", "caption": "100% target · leverage requested",
                   "form": {**BASE, "target": 100, "years": 8, "objective": "growth", "loss": 50,
                            "volatility": "high", "runway": 7, "leverage": True, "maxLeverage": 2,
                            "acknowledged": True}},
    "rent": {"label": "Rent at risk", "caption": "Live veto · essential expenses",
             "form": {**BASE, "target": 100, "essential": True, "runway": 1,
                      "leverage": True, "maxLeverage": 2}},
}
SAMPLE_POSITIONS = [{"identifier": "VWRP", "quantity": 6}, {"identifier": "VAGS", "quantity": 7}]
TOOLS = [
    ("parse", "Parse fictional holdings"),
    ("normalise", "Normalise fund identifiers"),
    ("enrich", "Check fund metadata and student constraints"),
    ("market", "Validate completed price observations"),
    ("analyse", "Evaluate RO signals and exposure limits"),
    ("verify", "Recompute financial and risk calculations"),
    ("explain", "Prepare the paper decision"),
]


def parse_positions(form: dict, paper: dict | None) -> list[dict]:
    mode = form.get("mode")
    if mode == "zero":
        return []
    if mode == "sample":
        return SAMPLE_POSITIONS
    if mode == "paper":
        if not paper:
            raise ValueError("There are no approved holdings to reuse.")
        return [{"identifier": row["ticker"], "quantity": row["quantity"]} for row in paper["positions"]]
    if mode == "manual":
        positions = form.get("positions")
        if not isinstance(positions, list) or not 1 <= len(positions) <= 60:
            raise ValueError("Enter one to 60 fictional positions.")
        if any(not isinstance(p, dict) or set(p) != {"identifier", "quantity"} for p in positions):
            raise ValueError("Each fictional position needs an identifier and quantity.")
        return positions
    if mode != "csv":
        raise ValueError("Choose how to start your paper portfolio.")
    content = form.get("csv")
    if form.get("mappingConfirmed") is not True:
        raise ValueError("Confirm the identifier and quantity CSV mapping before processing.")
    if not isinstance(content, str) or not content.strip() or len(content) > 16000:
        raise ValueError("Choose a fictional CSV up to 16 KB.")
    try:
        reader = csv.reader(io.StringIO(content.removeprefix("\ufeff")), strict=True)
        headers = [h.strip().lower() for h in next(reader, [])]
        if len(headers) != 2 or "quantity" not in headers or len(set(headers) & {"ticker", "isin", "identifier"}) != 1:
            raise ValueError("CSV needs exactly two columns, ticker/isin/identifier and quantity.")
        rows = list(reader)
        if not 1 <= len(rows) <= 60 or any(len(row) != 2 for row in rows):
            raise ValueError("CSV needs one to 60 complete positions.")
        j = headers.index("quantity")
        return [{"identifier": row[1 - j], "quantity": row[j]} for row in rows]
    except csv.Error:
        raise ValueError("The CSV contains invalid quoting or incomplete records.") from None


def normalise(rows: list[dict]) -> dict[str, float]:
    quantities: dict[str, float] = {}
    for i, row in enumerate(rows, 1):
        identifier = row["identifier"]
        ticker = IDENTIFIERS.get(identifier.strip().upper()) if isinstance(identifier, str) else None
        if not ticker:
            raise ValueError(f"Position {i} has an unverified identifier. Select the exact supported LSE ticker or ISIN.")
        quantity = number(row["quantity"], f"Position {i} quantity", 0.00000001, 1_000_000)
        quantities[ticker] = quantities.get(ticker, 0) + quantity
    return quantities


def valued_rows(positions: dict, history, nav: int, old: dict | None = None) -> list[dict]:
    return [
        {**FUNDS[ticker].public(), "value": value, "weight": value / nav,
         "price": history.prices[ticker][-1], "quantity": (value / 100) / history.prices[ticker][-1],
         "trade": value - (old or {}).get(ticker, 0)}
        for ticker, value in sorted(positions.items(), key=lambda row: (-row[1], row[0]))
    ]


def profile_result(profile, risk):
    return {
        "target": profile.target, "horizon": profile.years, "balance": profile.budget, "monthly": profile.monthly,
        "lossLimit": profile.loss, "runway": profile.runway, "category": risk.category, "risk": risk.name,
        "riskRule": risk.rule, "exposureCap": risk.cap, "equityCap": risk.equity_cap,
    }


def work(form: dict, paper: dict | None = None):
    """Yield completed tool calls, then exactly one decision. Early vetoes skip trading work."""
    step = "parse"
    try:
        profile = Profile.parse(form)
        rows = parse_positions(form, paper)
        yield "step", step, f"Validated the fictional profile and read {len(rows)} position rows."
        step = "normalise"
        quantities = normalise(rows)
        yield "step", step, f"Resolved {len(quantities)} unique positions against the LSE ticker and ISIN register."
        step = "enrich"
        risk = suitability(profile)
        common = profile_result(profile, risk)
        if risk.veto:
            yield "blocked", step, risk.rule + ". " + risk.veto
            yield "result", {**common, "state": "veto", "reason": risk.veto, "fit": fit(profile.target, None, True),
                             "leverage": {"state": "veto", "maximum": 1., "reason": "Affordability gate blocked all paper actions."}}
            return
        yield "step", step, f"Matched verified fund identities. Assigned risk {risk.category}/5 under the student rules."
        step = "market"
        history = load_history()
        missing = quantities.keys() - history.prices.keys()
        if missing:
            raise ValueError("Completed GBP history is unavailable for one or more existing positions.")
        provenance = history.provenance()
        yield "step", step, f"Validated {provenance['observations']} completed observations for {provenance['funds']} GBP listings."
        step = "analyse"
        current = {t: pennies(q * history.prices[t][-1]) for t, q in quantities.items()}
        if sum(current.values()) > profile.budget:
            raise ValueError("Fictional holdings exceed the paper balance at the selected dataset’s last prices. Adjust the quantities or balance.")
        current_weights = {ticker: value / profile.budget for ticker, value in current.items()}
        allocation = allocate(history, profile, current_weights, risk)
        positions, cash, fee, traded = settle(profile.budget, current, allocation["weights"])
        if not positions:
            yield "blocked", step, "The available signals and loss budget produced an all-cash outcome."
            yield "result", {**common, "state": "veto", "reason": "No suitable ETF allocation under the available signals and loss budget.",
                             "fit": fit(profile.target, None, True), "provenance": provenance,
                             "leverage": {"state": "veto", "maximum": 1., "reason": "There is no suitable base allocation."}}
            return
        nav = profile.budget - fee
        actual = {t: v / nav for t, v in positions.items()}
        shown = metrics(portfolio_returns(history, actual))
        shown.pop("curve")
        shown["stress"] = stress(actual)
        shown["feeDrag"] = sum(FUNDS[t].fee * w for t, w in actual.items())
        leverage = leverage_scenario(profile, risk, history, actual)
        current_risk = metrics(portfolio_returns(history, current_weights))
        current_risk.pop("curve")
        current_risk.update({"maxPosition": max(current_weights.values(), default=0.),
                             "equity": sum(w for t, w in current_weights.items() if FUNDS[t].asset == "Equity"),
                             "cash": profile.budget - sum(current.values()),
                             "feeDrag": sum(FUNDS[t].fee * w for t, w in current_weights.items())})
        yield "step", step, f"Ranked {len(allocation['scores'])} ETFs, checked three stress scenarios and evaluated leverage."
        step = "verify"
        verified = verify(history, profile, risk, current, allocation["weights"], positions, cash, fee, shown, allocation["scores"])
        yield "step", step, f"{len(verified)} independent checks passed. Approval is required for any paper action."
        step = "explain"
        result = {
            **common, "state": "ready", "provenance": provenance, "weights": actual,
            "replacesSnapshot": bool(paper and form.get("mode") != "paper"),
            "positions": valued_rows(positions, history, nav, current),
            "existing": valued_rows(current, history, profile.budget), "existingMetrics": current_risk,
            "cash": cash, "nav": nav, "fee": fee, "traded": traded, "turnover": turnover(current_weights, actual),
            "exposure": sum(actual.values()), "portfolioLeverage": 1., "leverage": leverage, "metrics": shown,
            "fit": fit(profile.target, shown["annualised"]),
            "scores": allocation["scores"], "exclusions": allocation["exclusions"],
            "breadth": allocation["breadth"], "breadthScale": allocation["scale"], "allocationRule": allocation["rule"],
            "verified": verified,
            "diffs": [{"ticker": t, "delta": positions.get(t, 0) - current.get(t, 0)}
                      for t in sorted(positions.keys() | current.keys()) if positions.get(t, 0) != current.get(t, 0)],
        }
        if not traded and paper and form.get("mode") == "paper":
            result.update({"state": "hold", "reason": "The current paper positions are inside the review bands."})
        yield "step", step, "Prepared the proposed changes, limits, reasoning and source record."
        yield "result", result
    except ValueError as error:
        yield "blocked", step, str(error)
        yield "result", {"state": "error", "reason": str(error)}


def decision(form: dict, paper: dict | None = None) -> dict:
    for event in work(form, paper):
        if event[0] == "result":
            return event[1]
    raise RuntimeError("Analysis ended without a decision.")
