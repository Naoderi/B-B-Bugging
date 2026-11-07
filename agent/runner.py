"""Official client adapter: no replacement uploads, no new checkpoint, real HOLD."""
from __future__ import annotations
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from strategy_core import VERSION, decide, portfolio_weights, validate_weights, PolicyError
from market_data import get_prices

class HoldRound(Exception):
    pass


def atomic_json(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp')
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as f:
        json.dump(value,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)


def stamp(value):
    from kit.contracts import timestamp
    return timestamp(value)


def prior_session(schedule, row):
    execution=stamp(row['execution_time']).astimezone(ZoneInfo('America/New_York'))
    rows=[r for r in schedule['rounds'] if r.get('status')!='CANCELLED'
          and stamp(r['close_time']).astimezone(ZoneInfo('America/New_York')).date()<execution.date()]
    if not rows: raise PolicyError('NO_PREVIOUS_SESSION_IN_SERVER_CALENDAR')
    close=max(stamp(r['close_time']) for r in rows)
    return close.astimezone(ZoneInfo('America/New_York')).date().isoformat(), close+timedelta(minutes=15)


def valid_receipt(result):
    # Support the documented receipt label as a nested status or receipt_status.
    positives=[]; negatives=[]
    def visit(obj):
        if isinstance(obj,dict):
            for key,v in obj.items():
                if key in ('status','receipt_status') and isinstance(v,str):
                    if v=='VALID': positives.append(v)
                    if v in ('INVALID','REJECTED','EARLY','LATE','MISSED_DEADLINE'): negatives.append(v)
                if isinstance(v,(dict,list)):visit(v)
        elif isinstance(obj,list):
            for v in obj:visit(v)
    visit(result)
    return bool(positives) and not negatives


class Adapter:
    def __init__(self, folder, sectors):
        self.folder=Path(folder);self.sectors=sectors
        self.state_path=self.folder/'strategy_state.json'
        self.state=json.loads(self.state_path.read_text()) if self.state_path.exists() else {
            'version':VERSION,'last_review_week':None,'held_rounds':{},'plans':{},'confirmed':{}}
        if self.state.get('version')!=VERSION:raise PolicyError('STATE_VERSION_MISMATCH')
        self.schedule=None;self.intentional_hold=False;self.policy_error=None;self.waiting=False
        self.called_round=None

    def save(self): atomic_json(self.state_path,self.state)

    def strategy(self, obs):
        self.called_round=obs['round']['id'];row=obs['round'];rid=row['id']
        if obs['phase']!='official' or row['phase']!='official':raise PolicyError('WRONG_PHASE')
        if rid in self.state['held_rounds'] or int(row['number'])!=1:
            self.intentional_hold=True
            raise HoldRound()
        expected,ready=prior_session(self.schedule,row)
        if stamp(obs['as_of'])<ready:
            self.intentional_hold=True;self.waiting=True
            raise HoldRound()
        if stamp(row['deadline'])-stamp(obs['as_of'])<timedelta(seconds=120):
            raise PolicyError('TOO_CLOSE_TO_DEADLINE: fewer than 120 seconds')
        current=portfolio_weights(obs['portfolio'],obs['symbols'])
        prices,source=get_prices(obs['symbols'],self.sectors,expected,obs['as_of'],self.folder/'market')
        target,reason,next_week=decide(prices,self.sectors,current,row['day'],self.state['last_review_week'])
        if target is None:
            self.state['last_review_week']=next_week
            self.state['held_rounds'][rid]=reason;self.save()
            self.intentional_hold=True
            raise HoldRound()
        target=validate_weights(target,obs['symbols'])
        # A failed pre-upload call may be recomputed; an existing official operation
        # bypasses this callback and is recovered byte-for-byte by OriginalSession.
        self.state['plans'][rid]={'weights':target,'reason':reason,'next_week':next_week,
                                  'signal_date':expected,'source':source}
        self.save()
        print('DECISION_READY '+rid+' '+reason+' stock_exposure='+str(round(sum(target.values()),4)),flush=True)
        return target

    def guarded_strategy(self,obs):
        try:return self.strategy(obs)
        except HoldRound:raise
        except PolicyError as e:
            self.policy_error=str(e);raise
        except Exception:
            self.policy_error='UNEXPECTED_LOCAL_STRATEGY_ERROR';raise

    def confirm_finished(self,session):
        for rid,plan in self.state['plans'].items():
            if rid in self.state['confirmed']:continue
            op=session.state['operations'].get('decision:official:'+rid)
            if not op or op['state']!='finished':continue
            res=op.get('result',{})
            if not valid_receipt(res):
                raise PolicyError('RECEIPT_NOT_CONFIRMED_VALID: preserve original submission/checkpoint; no replacement')
            self.state['last_review_week']=plan['next_week']
            self.state['confirmed'][rid]=res.get('platform_submission_id')
            print('RECEIPT_VALID '+rid+' submission='+str(res.get('platform_submission_id'))+' (execution still requires server confirmation)',flush=True)
        self.save()


def watch_pass(session, adapter):
    from kit.original_client import AutomationError
    adapter.intentional_hold=False;adapter.waiting=False;adapter.policy_error=None;adapter.called_round=None
    try:
        # On resume watch recovers earlier IDs before invoking this callback.
        # Commit recovered VALID plans before choosing the next round's action.
        def strategy(obs):
            try: adapter.confirm_finished(session)
            except PolicyError as e:
                adapter.policy_error=str(e);raise
            return adapter.guarded_strategy(obs)
        result=session.watch(strategy,phase='official',once=True,
                             max_wait_seconds=60,poll_seconds=30)
    except AutomationError:
        if adapter.intentional_hold:
            return {'status':'WAITING_FOR_COMPLETED_CANDLE' if adapter.waiting else 'HOLD_NO_UPLOAD',
                    'round_id':adapter.called_round}
        if adapter.policy_error:raise PolicyError(adapter.policy_error) from None
        raise
    adapter.confirm_finished(session)
    return result


def dry_check(session,adapter,schedule):
    now=session._now(schedule)
    rows=[r for r in schedule['rounds'] if r['phase']=='official' and r.get('status')!='CANCELLED' and int(r['number'])==1 and stamp(r['deadline'])>now]
    if not rows:raise PolicyError('NO_FUTURE_OFFICIAL_R1')
    row=min(rows,key=lambda r:stamp(r['deadline']))
    expected,ready=prior_session(schedule,row)
    current=portfolio_weights(session.portfolio('official'),schedule['symbols'])
    if now<ready:
        print('PREFLIGHT_ACCOUNT_OK; waiting for previous session final candle',flush=True)
        return
    prices,source=get_prices(schedule['symbols'],adapter.sectors,expected,now.isoformat(),adapter.folder/'market')
    target,reason,week=decide(prices,adapter.sectors,current,row['day'],adapter.state['last_review_week'])
    if target is not None:
        from kit.contracts import validate_payload
        payload={'submission_type':'decision','team_id':'local-dry-check','team_token':'local-dry-check',
                 'phase':'official','round_id':row['id'],'weights':target}
        schedule_path=adapter.folder/'schedule_check.json'
        atomic_json(schedule_path,schedule)
        validate_payload(payload,'decision.json',schedule_path=schedule_path)
    atomic_json(adapter.folder/'preflight.json',{'version':VERSION,'round_id':row['id'],'reason':reason,
        'source':source,'signal_date':expected,'weights':target,'submitted':False})
    print('PREFLIGHT_PASS: real account + completed market data + official payload validator; no order sent by preflight',flush=True)


def run(kit_root,folder,sectors,live=False):
    from kit.config import load_environment
    from kit.original_client import OriginalSession,load_profile,AutomationError,AmbiguousSubmission
    kit_root=Path(kit_root);os.chdir(kit_root)
    load_environment(kit_root/'.env')
    token=os.environ.get('CODABENCH_TOKEN')
    profile=os.environ.get('ICAIF_PROFILE')
    if not token or not profile:raise PolicyError('MISSING_EXISTING_CONFIGURATION: .env must provide CODABENCH_TOKEN and ICAIF_PROFILE')
    # Retain exact official default checkpoint used by the shown CLI. Never clone/reset.
    checkpoint=Path(os.environ.get('RO_CHECKPOINT','.icaif/checkpoint.json'))
    credentials=Path(os.environ.get('RO_CREDENTIALS','.icaif/credentials.json'))
    if not checkpoint.is_file() or not credentials.is_file():
        raise PolicyError('EXISTING_CHECKPOINT_OR_CREDENTIALS_MISSING: will not create a new account state')
    adapter=Adapter(folder,sectors)
    with OriginalSession(profile=load_profile(profile),token=token,checkpoint=checkpoint,
                         credentials=credentials,result_timeout=60) as session:
        schedule=session.schedule();adapter.schedule=schedule
        dry_check(session,adapter,schedule)
        if not live:
            print('DRY_RUN_COMPLETE: no uploads. Use --live only to run Official.',flush=True);return
        print('OFFICIAL_RUNNING: aggressive policy; R1 checks; R2-R7 hold without uploads. Keep Mac awake and online.',flush=True)
        last_message=None;last_heartbeat=0;errors=0
        while True:
            try:
                schedule=session.schedule();adapter.schedule=schedule
                result=watch_pass(session,adapter)
                errors=0
                status=result.get('status',result.get('receipt_status','RECEIPT_RECEIVED'))
                message=str(status)+' '+str(result.get('round_id',''))
                if message!=last_message:
                    print(message,flush=True);last_message=message
                if status=='SLOT_CONSUMED':
                    # Never replace an existing external submission. Stop if R1 was
                    # consumed by another runner so the user can inspect original ID.
                    rid=result.get('round_id','')
                    if rid.endswith('-r1') and rid not in adapter.state['confirmed']:
                        raise PolicyError('R1_ALREADY_CONSUMED_BY_OTHER_RUNNER: no replacement')
                if status=='TRADING_COMPLETE_FINAL_REQUIRED':
                    print('Trading complete. Final reproduction submission is still required.',flush=True);break
                if time.monotonic()-last_heartbeat>600:
                    print('HEARTBEAT server='+str(schedule.get('current_time'))+' next_deadline='+str(schedule.get('next_deadline')),flush=True)
                    last_heartbeat=time.monotonic()
            except AmbiguousSubmission:
                raise PolicyError('AMBIGUOUS_UPLOAD_STOPPED: original checkpoint retained; do not re-upload/delete it') from None
            except PolicyError as e:
                if str(e).startswith('MARKET_DATA_UNAVAILABLE'):
                    errors+=1
                    print('MARKET_DATA_RETRY: no order; retry in 30 seconds',flush=True)
                    if errors>=10:raise
                else:raise
            except AutomationError:
                # Let the official client recover known submitted IDs. No own POST retry.
                unfinished=[o for k,o in session.state['operations'].items() if k.startswith('decision:official:') and o.get('state')!='finished']
                if unfinished and any(o.get('state') not in ('submitted',) for o in unfinished):raise
                errors+=1
                print('OFFICIAL_CLIENT_READ_OR_RECEIPT_RETRY: same checkpoint / original ID only',flush=True)
                if errors>=10:raise
            time.sleep(30)
