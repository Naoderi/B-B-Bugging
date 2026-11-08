from __future__ import annotations

import copy
import json
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import paper
from agent import BASE, PRESETS, decision, normalise, parse_positions, work
from backtest import evaluate
from kit_adapter import handle
from market import DEMO_END, demo_history, gbp_quote, last_completed, licensed_csv, validate
from strategy import Profile, allocate, metrics, pennies, portfolio_returns, ro_signal, settle, stress, suitability
from verifier import verify


class Inputs(unittest.TestCase):
    def test_csv_requires_confirmed_mapping_and_rejects_extra_columns(self):
        source = {**BASE, "mode": "csv", "csv": "quantity,isin\n2.5,IE00BK5BQT80\n"}
        with self.assertRaisesRegex(ValueError, "Confirm"):
            parse_positions(source, None)
        source["mappingConfirmed"] = True
        self.assertEqual(normalise(parse_positions(source, None)), {"VWRP": 2.5})
        source["csv"] = "ticker,quantity,account\nVWRP,2.5,123"
        with self.assertRaisesRegex(ValueError, "exactly two"):
            parse_positions(source, None)

    def test_unknown_and_wrong_exchange_are_rejected(self):
        for ticker in ("AAPL", "VWRP.US", "FAKE", "VWRP GB"):
            with self.subTest(ticker=ticker):
                result = decision({**BASE, "mode": "manual", "positions": [{"identifier": ticker, "quantity": 1}]})
                self.assertEqual(result["state"], "error")
                self.assertIn("unverified", result["reason"])

    def test_accepted_aliases_and_duplicates_are_normalised(self):
        rows = [{"identifier": "vwrp.l", "quantity": 1}, {"identifier": "IE00BK5BQT80", "quantity": 2}]
        self.assertEqual(normalise(rows), {"VWRP": 3})
        self.assertEqual(pennies(1.015), 102)


class Market(unittest.TestCase):
    def test_gbp_normalisation(self):
        self.assertEqual(gbp_quote(1234, "GBp"), 12.34)
        self.assertEqual(gbp_quote(12.34, "GBP"), 12.34)
        with self.assertRaises(ValueError):
            gbp_quote(12.34, "USD")

    def test_conservative_close_time(self):
        self.assertEqual(last_completed(datetime(2026, 11, 6, 16, 59, tzinfo=UTC)), date(2026, 11, 5))
        self.assertEqual(last_completed(datetime(2026, 11, 7, 17, tzinfo=UTC)), DEMO_END)

    def test_missing_stale_and_outlier_data(self):
        h = demo_history().prefix(300)
        validate(h)
        for bad in (
            replace(h, cutoff=h.cutoff + timedelta(days=1)),
            replace(h, cutoff=h.cutoff - timedelta(days=1)),
            replace(h, dates=(h.dates[1], *h.dates[1:])),
            replace(h, prices={**h.prices, "VWRP": (*h.prices["VWRP"][:-1], 50_000.)}),
            replace(h, prices={**h.prices, "VWRP": h.prices["VWRP"][:-1]}),
        ):
            with self.assertRaises(ValueError):
                validate(bad)

    def test_licensed_price_reader_ignores_future_and_rejects_stale(self):
        h = demo_history()
        tickers = ("VWRP", "SWDA", "IGLS", "VAGS")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prices.csv"
            header = "date," + ",".join(t + ".L" for t in tickers) + "\n"
            rows = "\n".join(str(h.dates[i]) + "," + ",".join(str(h.prices[t][i] * 100) for t in tickers)
                             for i in range(210))
            path.write_text(header + rows, encoding="utf-8")
            manifest = path.with_suffix(".csv.json")
            manifest.write_text(json.dumps({"source": "Synthetic test fixture", "retrieved": "2024-01-01T12:00:00Z",
                                            "licence": "Authored test", "adjusted": True, "currency": "GBp"}))
            data = licensed_csv(str(path), 1, 1, h.dates[205])
            self.assertEqual(data.cutoff, h.dates[205])
            self.assertAlmostEqual(data.prices["VWRP"][-1], h.prices["VWRP"][205])
            with self.assertRaisesRegex(ValueError, "latest completed"):
                licensed_csv(str(path), 1, 1, h.dates[212])


class Strategy(unittest.TestCase):
    def test_ro_matches_constant_growth_known_answer(self):
        sample = tuple(100 * 1.001 ** i for i in range(61))
        r = ro_signal(sample)
        for n in (5, 20, 60):
            self.assertAlmostEqual(r[f"m{n}"], 1.001 ** n - 1, places=12)
        self.assertAlmostEqual(r["vol20"], 0, places=12)

    def test_personas_and_cash_runway_veto(self):
        for key in ("conservative", "balanced", "aggressive"):
            profile = PRESETS[key]["form"]
            with self.subTest(key=key):
                r = decision(profile)
                self.assertEqual(r["state"], "ready")
                self.assertLessEqual(max(r["weights"].values()), .3)
                self.assertEqual(sum(p["value"] for p in r["positions"]) + r["cash"] + r["fee"], r["balance"])
                self.assertLessEqual(max(r["metrics"]["stress"].values()) + r["fee"] / r["balance"], r["lossLimit"])
        rent = list(work(PRESETS["rent"]["form"]))
        self.assertEqual(rent[-1][1]["state"], "veto")
        self.assertNotIn("market", [x[1] for x in rent[:-1]])
        self.assertEqual(decision({**BASE, "runway": 2.9})["state"], "veto")
        self.assertEqual(decision({**BASE, "years": .75})["state"], "veto")

    def test_target_changes_explanation_and_never_increases_risk(self):
        a, b = decision(BASE), decision({**BASE, "target": 100})
        self.assertEqual(a["weights"], b["weights"])
        self.assertNotEqual(a["fit"], b["fit"])
        extreme = decision(PRESETS["aggressive"]["form"])
        self.assertEqual(extreme["leverage"]["state"], "veto")
        self.assertEqual(extreme["portfolioLeverage"], 1.)
        self.assertGreater(extreme["leverage"]["grossExposure"], 1.)

    def test_independent_verifier_rejects_tampering(self):
        h = demo_history(snapshot=True).prefix(len(demo_history().dates))
        p = Profile.parse(BASE)
        risk = suitability(p)
        a = allocate(h,p,{},risk)
        positions,cash,fee,_ = settle(p.budget,{},a["weights"])
        w = {t:v/(p.budget-fee) for t,v in positions.items()}
        m = metrics(portfolio_returns(h,w))
        m["stress"] = stress(w)
        from market import FUNDS
        m["feeDrag"] = sum(FUNDS[t].fee * v for t,v in w.items())
        self.assertGreater(len(verify(h,p,risk,{},a["weights"],positions,cash,fee,m,a["scores"])), 0)
        for kwargs in ({"cash": cash-1}, {"shown": {**m,"drawdown": 0.5}}, {"fee": fee+1},
                       {"history": replace(h,cutoff=h.cutoff-timedelta(days=1))}):
            args = {"history":h,"profile":p,"risk":risk,"current":{},"weights":a["weights"],
                    "positions":positions,"cash":cash,"fee":fee,"shown":m,"scores":a["scores"]}
            with self.assertRaises(ValueError):
                verify(**{**args,**kwargs})

    def test_penny_settlement_known_answer(self):
        self.assertEqual(settle(100000,{},{"VWRP":.3,"VAGS":.3}), ({"VWRP":29973,"VAGS":29973},39964,90,59946))

    def test_evaluation_is_chronological_and_reproducible(self):
        result = evaluate()
        self.assertEqual(result["observations"], 756)
        self.assertGreater(date.fromisoformat(result["first"]), demo_history().dates[199])
        self.assertEqual(result["paths"][0]["compliance"], 1.)
        self.assertEqual(len(result["paths"][0]["windowReturns"]), 3)
        self.assertGreater(result["paths"][0]["costDrag"], 0.)
        self.assertEqual(result, evaluate())

    def test_kit_adapter_warmup_short_history_and_exit(self):
        rows = [{"price_pence": 1000+i*10} for i in range(61)]
        req = {"task": "market_step", "input": {"shares": 0, "history": rows[:20]}}
        self.assertEqual(handle(req)["output"]["action"], "hold")
        for n in (21, 60, 61):
            req["input"]["history"] = rows[:n]
            self.assertEqual(handle(req)["output"]["action"], "buy", n)
        falling = [{"price_pence": 2000-i*10} for i in range(30)]
        self.assertEqual(handle({"task": "market_step", "input": {"shares": 5, "history": falling}})["output"]["action"], "sell")


class Paper(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        setting = patch.object(paper, "DB", Path(self.tmp.name) / "paper.sqlite3")
        setting.start()
        self.addCleanup(setting.stop)
        paper.setup()
        self.sid, _ = paper.session(None)

    def create_proposal(self):
        run, existing = paper.begin(self.sid)
        self.assertTrue(paper.save(self.sid,run,decision(BASE,existing)))
        return run

    def test_approval_pause_and_replay_controls(self):
        run = self.create_proposal()
        with self.assertRaisesRegex(ValueError, "confirmation"):
            paper.action(self.sid,run,"approve",False)
        paper.pause(self.sid,True)
        with self.assertRaisesRegex(ValueError, "paused"):
            paper.action(self.sid,run,"approve",True)
        self.assertIsNone(paper.get_state(self.sid)["paper"])
        paper.pause(self.sid,False)
        outcome = paper.action(self.sid,run,"approve",True)
        self.assertEqual(paper.get_state(self.sid)["paper"], outcome["paper"])
        with self.assertRaisesRegex(ValueError, "no longer"):
            paper.action(self.sid,run,"approve",True)

    def test_rejection_workspace_scope_and_supersession(self):
        run = self.create_proposal()
        other, _ = paper.session(None)
        with self.assertRaises(ValueError):
            paper.action(other,run,"approve",True)
        paper.action(self.sid,run,"reject",False)
        self.assertIsNone(paper.get_state(self.sid)["pending"])
        old = self.create_proposal()
        new = self.create_proposal()
        self.assertNotEqual(old,new)
        self.assertFalse(paper.save(self.sid,old,copy.deepcopy(decision(BASE))))
        self.assertEqual(paper.get_state(self.sid)["pending"]["id"],new)

    def test_audit_is_append_only(self):
        self.create_proposal()
        with paper.connect() as db:
            for statement in ("UPDATE audit SET detail='changed'", "DELETE FROM audit"):
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(statement)


if __name__ == "__main__":
    unittest.main()
