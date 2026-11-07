#!/usr/bin/env python3
"""RO V1/V2 research backtest — read-only; never imports official submission client.

Method: signals formed using adjusted *closing prices through prior trading day*,
orders filled at current trading day's adjusted first hourly-bar open, marked to
current day last hourly-bar adjusted close, 10bp of buy+sell notional commission.
Only ONE trade opportunity daily is simulated, unlike the official seven rounds.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

VARIANTS = ("V1_EXACT_SIGNAL", "V2_SECTOR", "V2_MIDTREND", "V2_REGIME", "V2_REGIME_LT")
WEIGHTS_V1 = [0.30, 0.30, 0.25, 0.15]
WEIGHTS_V2 = [0.24, 0.20, 0.18, 0.16, 0.12, 0.10]
DEFAULT_FEE = 0.001


def load_universe(p: Path):
    u = json.loads(p.read_text(encoding="utf-8"))
    by_sector = {ticker: name for name, stocks in u["sectors"].items() for ticker in stocks}
    assert len(by_sector) == 30, "Expected 30 unique competition tickers"
    return list(by_sector), by_sector


def load_dataset(zip_path: Path, symbols: list[str]):
    if not zip_path.is_file():
        raise FileNotFoundError(f"Dataset not found: {zip_path}")
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError("Install pyarrow in your Mac venv: python -m pip install pyarrow") from exc
    with zipfile.ZipFile(zip_path) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".parquet")]
        if len(names) != 1:
            raise ValueError("Expected exactly one parquet inside dataset zip")
        raw = io.BytesIO(z.read(names[0]))
    cols = ["timestamp_et", "trading_date", "ticker", "open", "close", "adj_close"]
    frame = pq.read_table(raw, columns=cols).to_pandas()
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    frame = frame.loc[frame["ticker"].isin(symbols)].copy()
    frame["trading_date"] = pd.to_datetime(frame["trading_date"], errors="coerce").dt.normalize()
    frame["timestamp_et"] = pd.to_datetime(frame["timestamp_et"], errors="coerce")
    for x in ["open", "close", "adj_close"]:
        frame[x] = pd.to_numeric(frame[x], errors="coerce")
    if frame[["trading_date", "timestamp_et"]].isna().any().any():
        raise ValueError("Invalid timestamps/dates; refusing silently dropped observations")
    if not np.isfinite(frame[["open", "close", "adj_close"]].to_numpy()).all():
        raise ValueError("Nonfinite OHLC observations")
    if (frame[["open", "close", "adj_close"]] <= 0).any().any():
        raise ValueError("Nonpositive OHLC observations")
    frame = frame.sort_values(["ticker", "trading_date", "timestamp_et"])
    duplicates = frame.duplicated(["ticker", "timestamp_et"]).sum()
    if duplicates:
        raise ValueError(f"Duplicate ticker/timestamp rows: {duplicates}")
    # Adjusted open and adjusted close share the same adjustment scale per hourly bar.
    frame["adjusted_open"] = frame["open"] * frame["adj_close"] / frame["close"]
    frame.loc[(frame["close"] <= 0) | (frame["open"] <= 0) |
              (frame["adj_close"] <= 0), "adjusted_open"] = np.nan
    # Keep literal boundary rows: groupby.first/last silently skip missing values.
    grouped = frame.groupby(["trading_date", "ticker"], sort=True)
    daily = grouped.agg(adj_open=("adjusted_open", lambda x: x.iloc[0]), adj_close=("adj_close", lambda x: x.iloc[-1]))
    opens = daily["adj_open"].unstack("ticker").reindex(columns=symbols)
    closes = daily["adj_close"].unstack("ticker").reindex(columns=symbols)
    opens = opens.where(opens > 0)
    closes = closes.where(closes > 0)
    opens, closes = opens.align(closes, join="inner", axis=0)
    return opens, closes, len(frame), len(frame["ticker"].unique())


def signals(history: pd.DataFrame, sector: dict, variant: str):
    """Strict point-in-time history: no current-day or future bars."""
    if variant in ("V2_REGIME_LT", "V2_AGGRESSIVE_LT"):
        variant = "V2_REGIME"
    symbols = list(history.columns)
    out = {s: 0.0 for s in symbols}
    if len(history) < 65:
        return out
    recent = history.tail(65)
    latest = recent.iloc[-1]
    mask = latest.notna() & (recent.tail(21).notna().sum() >= 20)
    # Original V1 fills gaps within its entire available history, after screening.
    p = recent.loc[:, mask].ffill()
    if len(p.columns) < 20:
        raise ValueError("Insufficient signal coverage; refusing to interpret missing data as all-cash signal")
    m5 = p.iloc[-1] / p.iloc[-6] - 1.0
    m20 = p.iloc[-1] / p.iloc[-21] - 1.0
    vol10 = p.pct_change(fill_method=None).tail(10).std()
    if variant == "V1_EXACT_SIGNAL":
        score = 0.65 * m20 + 0.35 * m5 - 0.10 * vol10 * math.sqrt(20)
        chosen = score[(m20 > 0) & (score > 0)].sort_values(ascending=False).head(4).index
        for symbol, w in zip(chosen, WEIGHTS_V1):
            out[str(symbol)] = float(w)
        return out

    vol20 = p.pct_change(fill_method=None).tail(20).std()
    if variant == "V2_SECTOR":
        score = 0.65 * m20 + 0.35 * m5 - 0.16 * vol20 * math.sqrt(20)
        eligible = score[(m20 > 0) & (score > 0)].sort_values(ascending=False)
        scale = 1.0
    elif variant in ("V2_MIDTREND", "V2_REGIME"):
        m60 = p.iloc[-1] / p.iloc[-61] - 1.0
        score = 0.55 * m60 + 0.35 * m20 + 0.10 * m5 - 0.20 * vol20 * math.sqrt(20)
        eligible = score[(m60 > 0) & (m20 > 0) & (score > 0)].sort_values(ascending=False)
        breadth = float((m20 > 0).mean())
        scale = 0.50 if breadth < 0.35 else (0.75 if breadth < 0.50 else 1.0)
        if variant == "V2_MIDTREND":
            scale = 1.0
    else:
        raise KeyError(variant)

    sector_weights = {}
    available = list(eligible.index)
    for desired in WEIGHTS_V2:
        for sym in available:
            group = sector[sym]
            if sector_weights.get(group, 0) + desired > 0.45 + 1e-10:
                continue
            out[str(sym)] += float(desired * scale)
            sector_weights[group] = sector_weights.get(group, 0) + desired
            available.remove(sym)
            break
    return out


def guarded_weights(target: dict, current: dict, variant: str):
    if not current:
        return target
    keys = target.keys()
    diff = np.array([abs(target[k] - current.get(k, 0.)) for k in keys])
    # Use identical guard thresholds for fair baseline comparison.
    if max(current.values(), default=0) <= .30 and sum(current.values()) <= 1.0 + 1e-12 and diff.sum()/2. < .10 and diff.max() < .05:
        return current
    return target


def low_turnover_decision(target, current, day, last_review_week):
    """Offline daily-open policy; all inputs known BEFORE execution.

    One calendar-week review (first observed trading day); immediate proportional
    risk reduction when desired exposure drops >=10 points. No grid search.
    None explicitly means no order, NOT cash. This is not a submission adapter.
    """
    vals = np.array(list(current.values()), dtype=float)
    if not np.isfinite(vals).all() or (vals < 0).any() or vals.sum() > 1 + 1e-8:
        raise ValueError("Invalid observed current weights")
    week = str(pd.Timestamp(day).to_period("W-SUN"))
    exposure = float(vals.sum())
    desired_exposure = sum(target.values())
    # A drifted portfolio must never be emitted as an invalid >30% target.
    if vals.max(initial=0) > .30:
        return {s: min(w, .30) for s, w in current.items()}, "cap_repair", last_review_week
    if exposure > desired_exposure + .10 + 1e-12:
        scale = desired_exposure / exposure
        return {s: w * scale for s, w in current.items()}, "risk_reduce", last_review_week
    if week == last_review_week:
        return None, "hold_week", last_review_week
    # Include cash in one-way turnover: cash->stocks must not count only half.
    delta = [abs(target[s] - current[s]) for s in target]
    turnover = (sum(delta) + abs(desired_exposure-exposure)) / 2
    if turnover < .10 and max(delta, default=0) < .05:
        return None, "hold_band", week
    return target, "weekly_review", week


@dataclass
class Portfolio:
    cash: float
    shares: pd.Series
    cumulative_fees: float = 0.0
    traded_notional: float = 0.0
    rebalance_count: int = 0


def trade_to_target(port: Portfolio, target: dict, prices: pd.Series, fee_rate: float):
    price = prices.reindex(port.shares.index)
    # Do not trade through missing, zero or nonfinite opening quotes.
    nonzero = (port.shares.abs() > 1e-12) | (pd.Series(target) > 1e-12)
    if (~np.isfinite(price[nonzero]) | (price[nonzero] <= 0)).any():
        return False
    price = price.fillna(1.0)
    nav = port.cash + (port.shares * price).sum()
    old_dollar = port.shares * price
    t = pd.Series(target, index=port.shares.index, dtype=float)
    assert len(t) == 30 and bool(np.isfinite(t).all())
    assert t.ge(0).all() and t.le(.30 + 1e-12).all() and t.sum() <= 1.000001
    # Iteratively solve NAV after costs, rather than buying more than available cash.
    fee = 0.0
    for _ in range(16):
        new_dollar = t * max(nav - fee, 0.0)
        new_fee = float((new_dollar - old_dollar).abs().sum() * fee_rate)
        if abs(fee-new_fee) < 1e-8:
            fee = new_fee
            break
        fee = new_fee
    new_dollar = t * (nav-fee)
    traded = float((new_dollar-old_dollar).abs().sum())
    if traded < 1e-8:
        return False
    port.shares = new_dollar / price
    port.cash = float((nav - fee) - new_dollar.sum())
    if port.cash < -1e-4:
        raise AssertionError("Cash went negative")
    port.cumulative_fees += fee
    port.traded_notional += traded
    port.rebalance_count += 1
    return True


def simulate(opens: pd.DataFrame, closes: pd.DataFrame, sector: dict,
             variant: str, start: pd.Timestamp, end: pd.Timestamp, fee_rate: float):
    all_days = closes.index[(closes.index >= start) & (closes.index <= end)]
    if len(all_days) < 20:
        raise ValueError(f"Too few days in interval: {start} – {end}")
    symbols = list(opens.columns)
    portfolio = Portfolio(1_000_000., pd.Series(0.0, index=symbols))
    curve = []
    invested = []
    dates = []
    valid_last = None
    last_review_week = None
    audit = []
    for d in all_days:
        preceding = closes.loc[closes.index < d]
        if len(preceding) < 65:
            continue
        # Don't use any intraday information from day d for selection.
        if variant == "V2_AGGRESSIVE_LT":
            from strategy_core import aggressive_target
            signal_history = preceding.ffill(limit=1)
            target = aggressive_target(signal_history, sector)
        else:
            signal_history = preceding
            target = signals(preceding, sector, variant)
        current_open = opens.loc[d]
        # Selection/guard at previous close. Today's open is execution-only.
        price_now = preceding.ffill().iloc[-1]
        if portfolio.shares.abs().sum() > 0 and price_now[portfolio.shares.abs() > 1e-12].isna().any():
            raise ValueError(f"Missing valuation for held stock: {d.date()}")
        current_nav = portfolio.cash + (portfolio.shares * price_now.fillna(0)).sum()
        current_weights = ((portfolio.shares * price_now.fillna(0))/current_nav).to_dict()
        current_weights = {k: float(v) for k,v in current_weights.items()}
        if variant == "V2_AGGRESSIVE_LT":
            from strategy_core import decide
            intended, reason, next_week = decide(signal_history, sector, current_weights, d, last_review_week)
        elif variant == "V2_REGIME_LT":
            intended, reason, next_week = low_turnover_decision(
                target, current_weights, d, last_review_week)
        else:
            intended = guarded_weights(target, current_weights, variant)
            reason, next_week = "baseline_guard", last_review_week
            if all(abs(intended[s]-current_weights[s]) < 1e-10 for s in symbols):
                intended = None
        executed = False
        before_fee = portfolio.cumulative_fees
        if intended is not None:
            executed = trade_to_target(portfolio, intended, current_open, fee_rate)
        # Retry a weekly review after unavailable execution quotes.
        if intended is None or executed:
            last_review_week = next_week
        audit.append({"date": str(d.date()), "reason": reason,
                      "executed": executed, "target": intended,
                      "fee": portfolio.cumulative_fees-before_fee})
        closing_today = closes.loc[d].combine_first(valid_last) if valid_last is not None else closes.loc[d]
        if (closing_today[portfolio.shares.abs()>1e-12].isna()).any():
            raise ValueError(f"Missing closing mark for held asset {d.date()}")
        nav_end = portfolio.cash + float((portfolio.shares * closing_today.fillna(0.0)).sum())
        if nav_end <= 0 or not math.isfinite(nav_end):
            raise ValueError(f"Invalid NAV {nav_end}")
        valid_last = closing_today
        dates.append(d)
        curve.append(nav_end)
        invested.append(float(1 - portfolio.cash/nav_end))
    nav = pd.Series(curve, index=pd.DatetimeIndex(dates), dtype=float)
    if nav.empty:
        raise ValueError("No simulation days after warmup")
    nav.attrs["decisions"] = audit
    r = nav.pct_change().fillna(nav.iloc[0]/1_000_000.-1)
    total_return = float(nav.iloc[-1] / 1_000_000. - 1)
    sharpe = float((r.mean()/r.std(ddof=1))*math.sqrt(252)) if r.std(ddof=1) > 1e-12 else 0.
    max_dd = float((1. - nav/nav.cummax().clip(lower=1_000_000)).max())
    years = len(nav)/252
    return {"strategy":variant, "start":str(nav.index.min().date()),
            "end":str(nav.index.max().date()), "days":len(nav),
            "return_pct":100*total_return,
            "sharpe":sharpe, "max_drawdown_pct":100*max_dd,
            "fees_usd":portfolio.cumulative_fees,
            "turnover_x_year":portfolio.traded_notional/1_000_000/max(years,1/252),
            "rebalances":portfolio.rebalance_count,
            "avg_invested_pct":100*float(np.mean(invested)),
            "ending_nav":float(nav.iloc[-1])}, nav


def choose_research_candidate(rows: pd.DataFrame):
    # Rank on DEVELOPMENT only; holdout is strictly for evaluation.
    tr = rows[(rows["period"] == "DEVELOPMENT") & (rows["fee_bps"] == 10)].copy()
    tr["rank_score"] = tr["sharpe"] - 0.018 * tr["max_drawdown_pct"] - .025 * tr["turnover_x_year"]
    tr = tr.sort_values("rank_score", ascending=False)
    return str(tr.iloc[0]["strategy"])


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()


