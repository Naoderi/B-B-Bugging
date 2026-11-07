# ICAIF 2026 — RO V2 Aggressive LT

## System Overview
A deterministic, rule-based autonomous stock trading agent
developed for the ICAIF Trading Agent Competition.

The agent is not a trained machine-learning model and therefore
does not require neural-network weights or a model checkpoint.

## Architecture
- start.py: application entry point
- runner.py: official-session integration and execution control
- strategy_core.py: signal generation and portfolio policy
- market_data.py: historical market-data processing
- research_engine.py: simulation and turnover-control logic
- research_check.py: research validation
- smoke_pipeline.py: pipeline testing
- universe.json: supported stock universe
- tests/: automated tests

## Trading Strategy
The agent ranks eligible stocks using 5-day, 20-day and
60-day momentum together with 20-day volatility.

It applies market-breadth exposure adjustment and portfolio
constraints. Individual target positions are capped at 30%.
Leverage is prohibited.

The low-turnover policy avoids unnecessary rebalancing and
reduces transaction costs. Risk reduction and position-cap
repair may trigger additional portfolio adjustments.

## Environment
The development machine reported Python 3.14.8.

The tested environment used Python 3.14.8 with the pinned packages in
`requirements.txt`. From the agent directory, create a virtual environment
and install them:

    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt

The ICAIF 2026 Starter Kit is a separate prerequisite. It supplies the
`kit` package, official session interface, schedule, and private account
configuration. Keep its `.env` and `.icaif` files outside this package.
For research checks, `start.py` also expects the historical data ZIP at
`~/Downloads/hourly_market_data_2021_2026.zip` unless `--dataset` is given.
For live market data the agent requests adjusted daily prices using
Yahoo Finance through `yfinance`; an existing validated local cache may
be used when available. Review the provider's access terms before reuse.

## Running and Testing
Run the project's automated tests from the agent directory with the
Starter Kit path set (replace the example path):

    RO_KIT_ROOT=/path/to/starter-kit .venv/bin/python -m unittest discover -s tests -v

Original entry point, run from the configured Starter Kit directory:

    /path/to/agent/.venv/bin/python /path/to/agent/start.py --kit . --dataset /path/to/historical_data.zip

The `--live` flag starts the trading session and may submit decisions;
it is not needed to run the tests.

The live command requires an authorized, correctly configured
official competition environment. It is included for
documentation only and should not be used to create new
submissions after the trading phase has closed.

## Reproducibility
For an independent review, examine the source code, stock
universe, strategy logic, tests, and accompanying demo video.

Official execution receipts and account results are generated
by the competition server. Exact official execution results
cannot be independently reproduced without the corresponding
official platform state, data and services.

The strategy uses only market information available at the
decision time; subsequent prices must not be used as inputs.

## Security
Team tokens, account credentials, private configuration,
and authenticated session state are excluded from the
public reproducibility package.
