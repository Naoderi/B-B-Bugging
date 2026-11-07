"""Fixed diagnostic gate; no parameter search and no claim of fresh holdout."""
import json
import io
import zipfile
from pathlib import Path
import pandas as pd
from research_engine import load_dataset, load_universe, simulate, sha256_file
from strategy_core import VERSION


def audit_bar_times(dataset):
    import pyarrow.parquet as pq
    with zipfile.ZipFile(dataset) as z:
        members=[n for n in z.namelist() if n.endswith('.parquet')]
        if len(members)!=1: raise ValueError('Expected one parquet')
        f=pq.read_table(io.BytesIO(z.read(members[0])),columns=['timestamp_et','trading_date','ticker']).to_pandas()
    # Preserve naive ET; normalize timezone-aware/mixed-offset data to NY.
    try:
        stamps=pd.to_datetime(f['timestamp_et'])
        if stamps.dt.tz is not None: stamps=stamps.dt.tz_convert('America/New_York')
        minutes=stamps.dt.hour*60+stamps.dt.minute
        days=stamps.dt.strftime('%Y-%m-%d')
    except (AttributeError,ValueError):
        stamps=pd.to_datetime(f['timestamp_et'],utc=True).dt.tz_convert('America/New_York')
        minutes=stamps.dt.hour*60+stamps.dt.minute
        days=stamps.dt.strftime('%Y-%m-%d')
    trading=pd.to_datetime(f['trading_date']).dt.strftime('%Y-%m-%d')
    regular=bool(minutes.between(570,930).all())
    date_match=bool((days==trading).all())
    f['minute']=minutes
    first=f.groupby(['trading_date','ticker'])['minute'].min()
    opening_fraction=float((first==570).mean())
    return {'all_bars_0930_to_1530_ET':regular,'timestamp_matches_trading_date':date_match,
            'stock_sessions_starting_0930_fraction':opening_fraction,
            'passed':regular and date_match and opening_fraction>=.99}


def run_research(dataset, output):
    dataset=Path(dataset);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    if not dataset.is_file(): raise ValueError('DATASET_MISSING')
    symbols,sectors=load_universe(Path(__file__).with_name('universe.json'))
    audit=audit_bar_times(dataset)
    (output/'data_audit.json').write_text(json.dumps(audit,indent=2))
    if not audit['passed']:
        raise ValueError('DATA_TIMING_GATE_FAILED: inspect data_audit.json; no live start')
    op,cl,rows,nstocks=load_dataset(dataset,symbols)
    if nstocks!=30 or len(op)<300 or cl.index.max()<pd.Timestamp('2025-12-31'):
        raise ValueError('DATASET_COVERAGE_GATE_FAILED')
    periods={'DEVELOPMENT':(op.index[65],pd.Timestamp('2024-12-31')),
             'REUSED_2025':(pd.Timestamp('2025-01-02'),pd.Timestamp('2025-12-31'))}
    results=[];curves=[]
    for period,(start,end) in periods.items():
        for variant in ['V1_EXACT_SIGNAL','V2_REGIME_LT','V2_AGGRESSIVE_LT']:
            for bps in [10,20]:
                res,nav=simulate(op,cl,sectors,variant,start,end,bps/10000)
                res.update(period=period,fee_bps=bps);results.append(res)
                if bps==10:
                    nav.attrs={};curves.append(nav.rename(period+'__'+variant))
                print(f"{period} {variant} {bps}bps: return={res['return_pct']:.2f}% MDD={res['max_drawdown_pct']:.2f}% trades={res['rebalances']}",flush=True)
    aggressive=[r for r in results if r['strategy']=='V2_AGGRESSIVE_LT']
    # Fixed coarse deployment screen, not an optimizer. Already-seen 2025 is reused.
    gate=all(r['return_pct']>0 and r['max_drawdown_pct']<=35 and r['sharpe']>0 for r in aggressive)
    summary={'version':VERSION,'data_sha256':sha256_file(dataset),'data_end':str(cl.index.max().date()),
             'passed':gate,'gate_definition':'All four aggressive period/cost combinations: net return >0, Sharpe >0, MDD <=35%. Fixed screen; not independent OOS validation.',
             'important':'AGGRESSIVE is a new four-stock variant. Old +13.26% belongs to six-stock REGIME_LT and must not be attributed to this variant. Daily execution only; actual seven-round official metrics differ.',
             'bar_audit':audit,'metrics':results}
    pd.DataFrame(results).to_csv(output/'backtest_metrics.csv',index=False)
    pd.concat(curves,axis=1).to_csv(output/'equity_curves.csv')
    (output/'summary.json').write_text(json.dumps(summary,indent=2))
    if not gate: raise ValueError('RESEARCH_GATE_FAILED: aggressive variant will NOT start; no silent fallback')
    print('LOCAL_RESEARCH_GATE_PASS (historical diagnostic only)',flush=True)
    return summary
