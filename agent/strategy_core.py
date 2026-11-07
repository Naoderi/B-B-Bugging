"""RO V2 Aggressive LT. Pure deterministic policy; no network or credentials."""
from __future__ import annotations
import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from research_engine import low_turnover_decision

VERSION = 'RO_V2_AGGRESSIVE_LT_20261012_1'
WEIGHTS = (.30, .28, .24, .18)

class PolicyError(ValueError):
    pass


def validate_weights(weights, symbols, cap=True):
    if not isinstance(weights, dict) or set(weights) != set(symbols):
        raise PolicyError('WEIGHTS_SCHEMA: expected all 30 symbols')
    out = {}
    for s in symbols:
        v = weights[s]
        if isinstance(v, (bool, str)):
            raise PolicyError('WEIGHTS_TYPE: numbers required')
        v = float(v)
        if not math.isfinite(v) or v < 0 or (cap and v > .30 + 1e-12):
            raise PolicyError('WEIGHTS_RANGE: illegal weight')
        out[s] = v
    if sum(out.values()) > 1 + 1e-10:
        raise PolicyError('WEIGHTS_SUM: leverage is forbidden')
    return out


def aggressive_target(history, sector):
    symbols = list(history.columns)
    if len(symbols) != 30 or set(symbols) != set(sector) or len(history) < 65:
        raise PolicyError('HISTORY: need 65 daily rows and exact universe')
    recent = history.tail(65)
    valid = (recent.notna().all() & np.isfinite(recent).all() & (recent > 0).all())
    if valid.sum() < 25:
        raise PolicyError('COVERAGE: need 25 fully usable stocks')
    p = recent.loc[:, valid]
    m5, m20, m60 = [p.iloc[-1] / p.iloc[-1-n] - 1 for n in (5,20,60)]
    vol = p.pct_change(fill_method=None).tail(20).std()
    score = .55*m60 + .35*m20 + .10*m5 - .20*vol*math.sqrt(20)
    ranked = score[(m60 > 0) & (m20 > 0) & (score > 0)].sort_values(ascending=False, kind='stable')
    breadth = float((m20 > 0).mean())
    scale = .65 if breadth < .35 else (.85 if breadth < .50 else 1.)
    out = dict.fromkeys(symbols, 0.)
    used = {}
    available = list(ranked.index)
    for allocation in WEIGHTS:
        for s in available:
            group = sector[s]
            if used.get(group, 0.) + allocation <= .60 + 1e-12:
                out[s] = float(allocation*scale)
                used[group] = used.get(group, 0.) + allocation
                available.remove(s)
                break
    return validate_weights(out, symbols)


def portfolio_weights(portfolio, symbols):
    # The V1 wrapper already used this exact field. Never assume missing means cash.
    if not isinstance(portfolio, dict) or not isinstance(portfolio.get('current_weights'), dict):
        raise PolicyError('PORTFOLIO_SCHEMA: current_weights missing; refusing guessed holdings')
    raw = portfolio['current_weights']
    if set(raw) - set(symbols):
        raise PolicyError('PORTFOLIO_SCHEMA: unknown symbol')
    # Sparse responses accepted only if at least one weight is present. Empty
    # portfolios need an explicit cash and NAV identity to establish all-cash.
    if not raw:
        nav, cash = portfolio.get('nav'), portfolio.get('cash')
        if nav is None or cash is None or float(nav) <= 0 or not math.isclose(float(nav),float(cash),rel_tol=1e-8):
            raise PolicyError('PORTFOLIO_SCHEMA: empty weights without cash/NAV evidence')
    normalized = {}
    for s in symbols:
        value = raw.get(s, 0.)
        if isinstance(value, str):
            try:
                value = float(value)
            except ValueError:
                raise PolicyError('PORTFOLIO_WEIGHT_NOT_NUMERIC: ' + s) from None
        normalized[s] = value
    return validate_weights(normalized, symbols, cap=False)


def check_history(history, symbols, expected_date, as_of):
    p = history.copy().reindex(columns=symbols)
    if not isinstance(p.index, pd.DatetimeIndex):
        p.index = pd.to_datetime(p.index)
    if p.index.tz is not None:
        p.index = p.index.tz_convert('America/New_York').tz_localize(None)
    p.index = p.index.normalize()
    if p.index.has_duplicates:
        raise PolicyError('HISTORY_DUPLICATE_DATES')
    now = datetime.fromisoformat(as_of.replace('Z','+00:00')).astimezone(ZoneInfo('America/New_York'))
    cutoff = now.date() if (now.hour,now.minute) >= (16,15) else now.date()-timedelta(days=1)
    limit = min(cutoff, pd.Timestamp(expected_date).date())
    p = p.loc[p.index.date <= limit].sort_index().tail(130)
    if p.empty or p.index[-1].date() != pd.Timestamp(expected_date).date():
        raise PolicyError('STALE_DATA: expected last completed market session')
    return p


def decide(history, sector, current, day, last_review_week):
    target = aggressive_target(history, sector)
    # If a previous allocation did not execute, do not stay in cash for a week.
    if sum(current.values()) < .001 and sum(target.values()) > 0:
        return target, 'initial_allocation', str(pd.Timestamp(day).to_period('W-SUN'))
    return low_turnover_decision(target, current, day, last_review_week)
