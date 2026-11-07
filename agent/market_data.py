"""Yahoo Finance adjusted daily prices with strict completed-session checks."""
import io
import contextlib
import os
from pathlib import Path
import pandas as pd
from strategy_core import check_history, aggressive_target, PolicyError


def get_prices(symbols, sectors, expected_date, as_of, folder):
    folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    cache=folder/('prices_'+expected_date+'.csv')
    if cache.exists():
        p=check_history(pd.read_csv(cache,index_col=0,parse_dates=True),symbols,expected_date,as_of)
        aggressive_target(p,sectors)
        return p,'verified_cache'
    import yfinance as yf
    try:
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            data=yf.download(symbols,period='6mo',interval='1d',auto_adjust=True,
                             progress=False,threads=False,timeout=20)
        if data.empty:
            raise PolicyError('MARKET_DATA_EMPTY')
        p=check_history(data['Close'],symbols,expected_date,as_of)
        aggressive_target(p,sectors)
    except Exception:
        raise PolicyError('MARKET_DATA_UNAVAILABLE: no valid fresh cache; no order') from None
    tmp=cache.with_suffix('.tmp')
    p.to_csv(tmp); os.chmod(tmp,0o600); os.replace(tmp,cache)
    return p,'yahoo_daily'
