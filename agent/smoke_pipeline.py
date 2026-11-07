"""Synthetic-only data/Parquet/research smoke. No market return evidence."""
import io
import os
import tempfile
import zipfile
from pathlib import Path
import numpy as np
import pandas as pd
from research_check import run_research


def main():
    from research_engine import load_universe
    symbols,_=load_universe(Path(__file__).with_name('universe.json'))
    days=pd.bdate_range('2024-06-03','2025-12-31')
    rows=[]
    for i,day in enumerate(days):
        for j,s in enumerate(symbols):
            for hour in range(7):
                op=100*np.exp((i+hour/7)*(.0008+j*.00002))
                close=op*np.exp(.0001)
                rows.append((day+pd.Timedelta(hours=9,minutes=30)+pd.Timedelta(hours=hour),day,s,op,close,close))
    frame=pd.DataFrame(rows,columns=['timestamp_et','trading_date','ticker','open','close','adj_close'])
    raw=io.BytesIO();frame.to_parquet(raw,index=False)
    with tempfile.TemporaryDirectory() as tmp:
        tmp=Path(tmp);zpath=tmp/'SYNTHETIC_DATA.zip'
        with zipfile.ZipFile(zpath,'w') as z:z.writestr('synthetic.parquet',raw.getvalue())
        result=run_research(zpath,tmp/'output')
        assert len(result['metrics'])==12
        assert result['passed']
        assert result['bar_audit']['passed']
        assert (tmp/'output/summary.json').is_file()
    print('SYNTHETIC_PIPELINE_PASS: parquet loading, timestamps, 12 simulations, diagnostics and gate. Not real-market performance.')

if __name__=='__main__':main()
