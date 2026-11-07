import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import timedelta
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
KIT=Path(os.environ['RO_KIT_ROOT']).resolve()
sys.path.insert(0,str(KIT))
from kit.original_client import OriginalSession, AutomationError
from kit.contracts import validate_payload, timestamp
from strategy_core import aggressive_target, decide, check_history, portfolio_weights, PolicyError
from research_engine import load_universe, simulate, Portfolio, trade_to_target
from runner import Adapter,watch_pass,valid_receipt,prior_session,dry_check

symbols,sectors=load_universe(ROOT/'universe.json')

def history():
    days=pd.bdate_range(end='2026-10-09',periods=100)
    return pd.DataFrame({s:100*np.exp(np.arange(100)*(.001+i*.00008)) for i,s in enumerate(symbols)},index=days)

def schedule(now='2026-10-12T01:00:00+00:00'):
    v=json.loads((KIT/'schedule.json').read_text())
    v.update(current_time=now,symbols=symbols,universe_confirmed=True)
    return v

def fake_session(sched=None,weights=None,own=None):
    client=OriginalSession.__new__(OriginalSession)
    client.state={'operations':{}};client.clock=None
    client.schedule=lambda:sched or schedule()
    client.portfolio=lambda phase:{'current_weights':weights or dict.fromkeys(symbols,0.),'nav':1000000,'cash':1000000}
    client.round=lambda rid:own or {'decisions':[]}
    client._team=lambda:{'team_id':'test-team','team_token':'test-token'}
    client.uploads=[]
    def decision(raw,payload):
        validate_payload(payload,'decision.json')
        result={'receipt_status':'VALID','platform_submission_id':123,'round_id':payload['round_id']}
        client.uploads.append(payload)
        client.state['operations']['decision:official:'+payload['round_id']]={'state':'finished','result':result}
        return result
    client._decision=decision
    return client

class CoreTests(unittest.TestCase):
    def test_aggressive_full_allocation_four_stocks(self):
        w=aggressive_target(history(),sectors)
        self.assertEqual(sum(v>0 for v in w.values()),4)
        self.assertAlmostEqual(sum(w.values()),1.)
        self.assertEqual(sorted([v for v in w.values() if v],reverse=True),[.30,.28,.24,.18])
        for group in set(sectors.values()):self.assertLessEqual(sum(w[s] for s in symbols if sectors[s]==group),.60+1e-10)

    def test_no_positive_trend_all_cash_is_explicit(self):
        p=history();p[:]=100*np.exp(-np.arange(100)[:,None]*.002)
        self.assertEqual(sum(aggressive_target(p,sectors).values()),0.)

    def test_incomplete_coverage_is_error_not_cash(self):
        p=history();p.iloc[-1,:6]=np.nan
        with self.assertRaises(PolicyError):aggressive_target(p,sectors)

    def test_hold_same_week(self):
        p=history();w=aggressive_target(p,sectors)
        out,reason,week=decide(p,sectors,w,'2026-10-13','2026-10-12/2026-10-18')
        self.assertIsNone(out)

    def test_drift_target_capped(self):
        p=history();w=aggressive_target(p,sectors)
        first=max(w,key=w.get);second=next(s for s in symbols if w[s]>0 and s!=first)
        w[first]+=.01;w[second]-=.01
        out,reason,_=decide(p,sectors,w,'2026-10-13','2026-10-12/2026-10-18')
        self.assertEqual(reason,'cap_repair');self.assertLessEqual(max(out.values()),.30)

    def test_no_future_daily_candle(self):
        p=history();p.loc[pd.Timestamp('2026-10-12')]=1e12
        cleaned=check_history(p,symbols,'2026-10-09','2026-10-12T14:00:00+00:00')
        self.assertEqual(cleaned.index[-1],pd.Timestamp('2026-10-09'))
        self.assertEqual(aggressive_target(cleaned,sectors),aggressive_target(history(),sectors))

    def test_stale_cache_rejected(self):
        with self.assertRaises(PolicyError):check_history(history().iloc[:-1],symbols,'2026-10-09','2026-10-12T01:00:00+00:00')

    def test_unknown_holdings_fail_closed(self):
        with self.assertRaises(PolicyError):portfolio_weights({},symbols)
        with self.assertRaises(PolicyError):portfolio_weights({'current_weights':{}},symbols)

    def test_confirmed_cash_allowed(self):
        self.assertEqual(sum(portfolio_weights({'current_weights':{},'nav':1000,'cash':1000},symbols).values()),0)

    def test_missing_quote_does_not_trade(self):
        p=Portfolio(1000000,pd.Series(0.,index=symbols));prices=pd.Series(100.,index=symbols)
        w=aggressive_target(history(),sectors);prices[next(s for s in symbols if w[s])]=np.nan
        self.assertFalse(trade_to_target(p,w,prices,.001));self.assertEqual(p.cash,1000000)

    def test_initial_cost_conservation(self):
        p=Portfolio(1000000,pd.Series(0.,index=symbols));prices=pd.Series(100.,index=symbols)
        trade_to_target(p,aggressive_target(history(),sectors),prices,.001)
        self.assertAlmostEqual(p.cash+(p.shares*prices).sum()+p.cumulative_fees,1000000,places=6)

    def test_execution_price_not_decision_information(self):
        p=history();op=p.shift(1).fillna(100);op2=op.copy();op2.iloc[80,0]=100000
        _,a=simulate(op,p,sectors,'V2_AGGRESSIVE_LT',p.index[65],p.index[-1],.001)
        _,b=simulate(op2,p,sectors,'V2_AGGRESSIVE_LT',p.index[65],p.index[-1],.001)
        self.assertEqual(a.attrs['decisions'][15]['target'],b.attrs['decisions'][15]['target'])

class OfficialAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.adapter=Adapter(self.temp.name,sectors);self.adapter.schedule=schedule()
        self.data=patch('runner.get_prices',return_value=(history(),'synthetic-test'))
        self.data.start();self.addCleanup(self.data.stop)
        self.silence=patch('runner.print',create=True);self.silence.start();self.addCleanup(self.silence.stop)

    def test_official_watch_submits_legal_payload_once(self):
        client=fake_session();result=watch_pass(client,self.adapter)
        self.assertTrue(valid_receipt(result));self.assertEqual(len(client.uploads),1)
        self.assertEqual(self.adapter.state['last_review_week'],'2026-10-12/2026-10-18')
        watch_pass(client,self.adapter);self.assertEqual(len(client.uploads),1)

    def test_hold_calls_actual_watch_and_creates_no_upload(self):
        self.adapter.state['last_review_week']='2026-10-12/2026-10-18'
        client=fake_session(weights=aggressive_target(history(),sectors))
        result=watch_pass(client,self.adapter)
        self.assertEqual(result['status'],'HOLD_NO_UPLOAD');self.assertEqual(client.uploads,[])
        self.assertFalse(client.state['operations'])

    def test_intraday_round_is_not_rebalanced(self):
        sched=schedule('2026-10-12T13:45:00+00:00');self.adapter.schedule=sched
        client=fake_session(sched);result=watch_pass(client,self.adapter)
        self.assertEqual(result['status'],'HOLD_NO_UPLOAD');self.assertEqual(client.uploads,[])

    def test_r1_waits_for_previous_session_close(self):
        sched=schedule('2026-10-09T19:45:00+00:00');self.adapter.schedule=sched
        client=fake_session(sched);result=watch_pass(client,self.adapter)
        self.assertEqual(result['status'],'WAITING_FOR_COMPLETED_CANDLE');self.assertEqual(client.uploads,[])

    def test_invalid_existing_slot_never_replaced(self):
        client=fake_session(own={'decisions':[{'selection_status':'SELECTED','receipt_status':'INVALID'}]})
        result=watch_pass(client,self.adapter)
        self.assertEqual(result['status'],'SLOT_CONSUMED');self.assertEqual(client.uploads,[])

    def test_deadline_exclusive(self):
        client=fake_session(schedule('2026-10-12T13:10:00+00:00'))
        result=watch_pass(client,self.adapter)
        self.assertEqual(result['status'],'WAITING_FOR_ROUND');self.assertEqual(client.uploads,[])

    def test_near_deadline_no_upload(self):
        sched=schedule('2026-10-12T13:09:00+00:00');self.adapter.schedule=sched
        client=fake_session(sched)
        with self.assertRaises(PolicyError):watch_pass(client,self.adapter)
        self.assertEqual(client.uploads,[])

    def test_reused_state_prevents_repeated_hold(self):
        self.adapter.state['last_review_week']='2026-10-12/2026-10-18'
        client=fake_session(weights=aggressive_target(history(),sectors))
        watch_pass(client,self.adapter)
        restored=Adapter(self.temp.name,sectors);restored.schedule=schedule()
        result=watch_pass(client,restored)
        self.assertEqual(result['status'],'HOLD_NO_UPLOAD');self.assertEqual(client.uploads,[])

    def test_recover_pending_original_id_without_new_decision(self):
        client=fake_session();watch_pass(client,self.adapter)
        rid=client.uploads[0]['round_id'];key='decision:official:'+rid
        result=client.state['operations'][key]['result']
        import base64
        client.state['operations'][key]={'state':'submitted','raw_b64':base64.b64encode(b'original').decode()}
        recovered=[]
        def submit(k,raw,filename,phase):
            self.assertEqual(raw,b'original');recovered.append(k)
            client.state['operations'][k]={'state':'finished','result':result}
            return result
        client._submit=submit
        watch_pass(client,self.adapter)
        self.assertEqual(recovered,[key]);self.assertEqual(len(client.uploads),1)

    def test_unknown_receipt_does_not_mark_success(self):
        self.assertFalse(valid_receipt({'status':'Finished'}))
        self.assertFalse(valid_receipt({'receipt_status':'INVALID'}))
        self.assertTrue(valid_receipt({'receipt':{'status':'VALID'}}))

    def test_dry_check_does_not_submit(self):
        client=fake_session();dry_check(client,self.adapter,schedule())
        self.assertEqual(client.uploads,[])
        self.assertFalse(json.loads((Path(self.temp.name)/'preflight.json').read_text())['submitted'])

    def test_dst_uses_server_timestamp(self):
        s=schedule('2026-10-26T12:00:00+00:00')
        row=next(r for r in s['rounds'] if r['id']=='official-2026-10-26-r1')
        self.assertEqual(timestamp(row['deadline']).hour,13)
        expected,ready=prior_session(s,row)
        self.assertEqual(expected,'2026-10-23')

if __name__=='__main__':unittest.main()
