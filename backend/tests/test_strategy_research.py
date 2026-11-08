import unittest
from dataclasses import replace
from types import SimpleNamespace

from market import demo_history, LOOKBACK
from strategy import TRADE_RATE
from strategy_research import evaluate, fund_curves, basket_metrics


class Research(unittest.TestCase):
    def test_flat_prices_pay_entry_cost_once(self):
        h = SimpleNamespace(prices={'ISF': [100.] * 10}, embedded_fee=True)
        result = basket_metrics(fund_curves(h, 2, 10), ('ISF',))
        self.assertAlmostEqual(result['total'], 1 / (1 + TRADE_RATE) - 1)

    def test_first_close_is_execution_not_free_return(self):
        h = SimpleNamespace(prices={'ISF': [1., 100., 110., 110.]}, embedded_fee=True)
        result = basket_metrics(fund_curves(h, 1, 4), ('ISF',))
        self.assertAlmostEqual(result['total'], 1.1 / (1 + TRADE_RATE) - 1)

    def test_holdout_changes_cannot_affect_selection(self):
        history = demo_history()
        first = evaluate(history)
        split = LOOKBACK + 504
        changed = replace(history, prices={k: tuple(v[:split]) + tuple(x * (1.01 if k == 'VWRP' else .99) ** (i + 1)
            for i, x in enumerate(v[split:])) for k, v in history.prices.items()})
        second = evaluate(changed)
        self.assertEqual(first['training'], second['training'])
        self.assertEqual(first['holdout']['holdings'], second['holdout']['holdings'])
        self.assertNotEqual(first['holdout']['total'], second['holdout']['total'])
        self.assertNotEqual(first['dataHash'], second['dataHash'])

    def test_short_history_is_explicitly_unavailable(self):
        h = demo_history().prefix(LOOKBACK + 252)
        self.assertFalse(evaluate(h)['available'])
