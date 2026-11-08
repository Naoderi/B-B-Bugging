"""Disclosed hindsight search, separate from the frozen student strategy.

Search every equal-weight four-equity-ETF basket with distinct exposure groups.
The full-period winner is selected AFTER observing all outcomes. A separate
walk-forward check selects on the first two years and tests on the last year.
"""
from itertools import combinations
import hashlib
import json

from market import FUNDS, LOOKBACK
from strategy import TRADE_RATE, metrics


def fund_curves(history, start, stop):
    curves = {}
    for ticker, prices in history.prices.items():
        if FUNDS[ticker].asset != 'Equity':
            continue
        fee = 0 if history.embedded_fee else FUNDS[ticker].fee / 252
        # Start in cash. Buy at the first evaluation close, including costs.
        wealth = 1 / (1 + TRADE_RATE)
        curve = [1., wealth]
        for t in range(start + 1, stop):
            wealth *= prices[t] / prices[t - 1] - fee
            curve.append(wealth)
        curves[ticker] = curve
    return curves


def basket_metrics(curves, basket):
    values = [sum(curves[k][t] for k in basket) / len(basket) for t in range(len(curves[basket[0]]))]
    result = metrics([b / a - 1 for a, b in zip(values, values[1:])])
    result['curve'] = [*result['curve'][::7], result['curve'][-1]]
    result['holdings'] = list(basket)
    return result


def candidates(curves):
    return [basket for basket in combinations(sorted(curves), 4)
            if len({FUNDS[k].group for k in basket}) == 4]


def best(curves, baskets):
    return max(baskets, key=lambda basket: sum(curves[k][-1] for k in basket))


def evaluate(history):
    start = LOOKBACK
    length = ((len(history.dates) - start) // 252) * 252
    if length < 756:
        return {'available': False, 'reason': 'Research comparison needs at least three years after warm-up.'}
    stop, split = start + length, start + length - 252
    all_curves = fund_curves(history, start, stop)
    baskets = candidates(all_curves)
    if not baskets:
        return {'available': False, 'reason': 'Not enough distinct equity groups for the research comparison.'}
    winner = best(all_curves, baskets)
    training = fund_curves(history, start, split)
    selected = best(training, baskets)
    validation = fund_curves(history, split, stop)
    fingerprint = hashlib.sha256(json.dumps({'dates': [str(d) for d in history.dates[:stop]],
        'prices': {k: list(v[:stop]) for k, v in sorted(history.prices.items())}}, sort_keys=True).encode()).hexdigest()
    return {'available': True, 'selection': 'hindsight', 'candidateCount': len(baskets),
            'synthetic': history.synthetic, 'observations': length,
            'first': str(history.dates[start]), 'last': str(history.dates[stop - 1]),
            'dataHash': fingerprint, 'hindsight': basket_metrics(all_curves, winner),
            'training': basket_metrics(training, selected), 'holdout': basket_metrics(validation, selected),
            'holdoutFirst': str(history.dates[split]), 'holdoutLast': str(history.dates[stop - 1]),
            'method': 'All equal-weight four-equity-ETF baskets with distinct exposure groups. Buy at the first evaluation close, then hold. Entry spread and commission total 15 bp; issuer fund fees deducted daily unless embedded in prices. Cash earns zero. No leverage or contributions. Ending values are marked to market without a final sale.',
            'limitation': 'Full-period selection uses future outcomes and is not an independent backtest. This all-equity research basket does not apply the student portfolio risk limits; weights drift after purchase. The separate holdout basket is chosen using only the preceding observations. Neither result establishes future performance.'}


if __name__ == '__main__':
    from market import load_history
    print(json.dumps(evaluate(load_history(full=True)), indent=2, allow_nan=False))
