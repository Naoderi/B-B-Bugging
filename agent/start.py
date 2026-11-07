#!/usr/bin/env python3
"""One command: dependency check, official-interface tests, research, preflight, live."""
import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime

ROOT=Path(__file__).resolve().parent

class Tee:
    def __init__(self,*streams):self.streams=streams
    def write(self,text):
        for stream in self.streams:stream.write(text);stream.flush()
        return len(text)
    def flush(self):
        for stream in self.streams:stream.flush()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--live',action='store_true',help='After all gates pass, start Official simulated competition trading')
    p.add_argument('--dataset',type=Path,default=Path.home()/'Downloads/hourly_market_data_2021_2026.zip')
    p.add_argument('--kit',type=Path,default=Path.cwd())
    a=p.parse_args();kit=a.kit.resolve()
    if not (kit/'tools/auto_submit.py').is_file() or not (kit/'kit/original_client.py').is_file():
        raise SystemExit('Run this command from the existing starter-kit directory, or pass --kit PATH.')
    if sys.version_info<(3,10):raise SystemExit('Python 3.10+ required; use existing .venv.')
    if sys.prefix==sys.base_prefix:raise SystemExit('Activate the existing starter-kit .venv before running; will not install globally.')
    requirements={'numpy':'numpy','pandas':'pandas','pyarrow':'pyarrow','httpx':'httpx==0.28.1','yfinance':'yfinance'}
    missing=[package for module,package in requirements.items() if importlib.util.find_spec(module) is None]
    if missing:
        print('Installing missing dependencies into the active virtual environment: '+', '.join(missing),flush=True)
        subprocess.run([sys.executable,'-m','pip','install',*missing],check=True)
    sys.path.insert(0,str(kit));os.environ['RO_KIT_ROOT']=str(kit)
    # Hold a local process lock before touching the custom strategy state.
    private=kit/'private'/'ro_v2_aggressive';private.mkdir(parents=True,exist_ok=True)
    import fcntl
    lock=(private/'runner.lock').open('a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:raise SystemExit('Another RO V2 process is active. No second runner started.')
    run_id=datetime.now().strftime('%Y%m%d_%H%M%S')
    output=private/('run_'+run_id);output.mkdir(exist_ok=False)
    os.chmod(private,0o700)
    with (output/'run.log').open('w',buffering=1) as log,contextlib.redirect_stdout(Tee(sys.stdout,log)):
        try:
            print('RO V2 AGGRESSIVE: fixed policy, no optimization grid. Output: '+str(output),flush=True)
            import unittest
            tests=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
            test_result=unittest.TextTestRunner(stream=sys.stdout,verbosity=2).run(tests)
            if not test_result.wasSuccessful():raise RuntimeError('LOCAL_TESTS_FAILED')
            print('TESTS_PASS',flush=True)
            from research_check import run_research
            from research_engine import load_universe
            from runner import run,atomic_json
            # Reuse only a successful gate for identical source + identical dataset.
            from research_engine import sha256_file
            digest=hashlib.sha256()
            for file in sorted(ROOT.rglob('*')):
                if file.is_file() and file.suffix in ('.py','.json') and '__pycache__' not in file.parts:
                    digest.update(str(file.relative_to(ROOT)).encode());digest.update(file.read_bytes())
            signature={'source_sha256':digest.hexdigest(),'data_sha256':sha256_file(a.dataset)}
            gate_file=private/'passed_gate.json'
            prior=json.loads(gate_file.read_text()) if gate_file.exists() else {}
            if prior.get('signature')==signature and prior.get('passed') is True:
                print('Reusing matching passed research gate. Original report: '+prior['report'],flush=True)
            else:
                report=run_research(a.dataset,output/'research')
                atomic_json(gate_file,{'signature':signature,'passed':True,'report':str(output/'research/summary.json')})
            symbols,sectors=load_universe(ROOT/'universe.json')
            atomic_json(output/'runtime.json',{'python':sys.version,'kit':str(kit),'source':signature,
                'official_client_sha256':sha256_file(kit/'kit/original_client.py'),'live_requested':a.live})
            # Prevent Mac idle sleep; normal shutdown/closed-lid sleep are not prevented.
            keep_awake=None
            if a.live and sys.platform=='darwin':
                keep_awake=subprocess.Popen(['/usr/bin/caffeinate','-i','-w',str(os.getpid())])
            try:run(kit,private,sectors,live=a.live)
            finally:
                if keep_awake is not None:keep_awake.terminate()
        except KeyboardInterrupt:
            print('STOPPED_BY_USER: checkpoint and original IDs retained.',flush=True)
        except Exception as exc:
            # Do not dump arbitrary HTTP responses, .env, credentials, or tracebacks.
            from strategy_core import PolicyError
            from kit.original_client import AutomationError
            if isinstance(exc,(PolicyError,AutomationError)):
                label=str(exc)
            elif isinstance(exc,ValueError) and str(exc).split(':')[0] in (
                'DATA_TIMING_GATE_FAILED','DATASET_COVERAGE_GATE_FAILED','RESEARCH_GATE_FAILED','DATASET_MISSING'):
                label=str(exc)
            else:label='LOCAL_CHECK_FAILED ('+type(exc).__name__+'); no blind resubmission'
            print('STOPPED: '+label,flush=True)
            (output/'STOPPED.txt').write_text(label+'\nOriginal checkpoint retained. Review run.log.\n')
            print('Report folder: '+str(output),flush=True)
            if sys.platform=='darwin':subprocess.run(['open',str(output)],check=False)
            return 2
    lock.close()
    return 0

if __name__=='__main__':raise SystemExit(main())
