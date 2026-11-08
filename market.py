"""Issuer-sourced fund identities and point-in-time GBP price inputs."""
from __future__ import annotations

import csv
import json
import math
import os
import random
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

CHECKED = "2026-11-07"
DEMO_END = date(2026, 11, 6)
LOOKBACK = 200
SEED = 261107
LONDON = ZoneInfo("Europe/London")


@dataclass(frozen=True)
class Fund:
    ticker: str
    name: str
    isin: str
    asset: str
    group: str
    index: str
    fee: float
    income: str
    source: str
    base: float

    def public(self):
        share_currency = "EUR" if self.ticker == "VEUR" else "GBP" if self.asset == "Bond" and self.ticker != "IBTS" else "GBP" if self.ticker in {"ISF", "IUKP"} else "USD"
        return {
            **{k: v for k, v in asdict(self).items() if k != "base"},
            "listing": "LSE • GBP", "domicile": "Ireland", "structure": "UCITS ETF",
            "uk_reporting": "Yes (issuer)", "wrapper": "ISA / SIPP (issuer)" if self.source.startswith(I) else None,
            "share_currency": share_currency, "holdings_overlap": None,
            "checked": CHECKED,
        }


V = "https://www.vanguard.co.uk"
I = "https://www.ishares.com/uk/individual/en"
FUNDS = {f.ticker: f for f in (
    Fund("VWRP", "Vanguard FTSE All-World", "IE00BK5BQT80", "Equity", "Global equity",
         "FTSE All-World", .0014, "Accumulating", V + "/professional/product/etf/equity/9679/x", 95),
    Fund("SWDA", "iShares Core MSCI World", "IE00B4L5Y983", "Equity", "Global equity",
         "MSCI World", .0020, "Accumulating", I + "/products/251882/", 73),
    Fund("VUAG", "Vanguard S&P 500", "IE00BFMXXD54", "Equity", "US large-cap",
         "S&P 500", .0007, "Accumulating", V + "/professional/product/etf/equity/9694/sp-500-ucits-etf-usd-accumulating", 58),
    Fund("CNX1", "iShares Nasdaq 100", "IE00B53SZB19", "Equity", "US large-cap",
         "Nasdaq-100", .0030, "Accumulating", I + "/products/253741/", 470),
    Fund("ISF", "iShares Core FTSE 100", "IE0005042456", "Equity", "UK equity",
         "FTSE 100", .0007, "Distributing", I + "/products/251795/", 7),
    Fund("EMIM", "iShares Core MSCI EM IMI", "IE00BKM4GZ66", "Equity", "Emerging markets",
         "MSCI EM IMI", .0018, "Accumulating", I + "/products/264659/", 24),
    Fund("VAGS", "Vanguard Global Aggregate Bond", "IE00BG47K971", "Bond", "Global bonds",
         "Bloomberg Global Aggregate Float Adjusted and Scaled", .0008, "Accumulating",
         V + "/uk-fund-directory/product/etf/bond/9685/global-aggregate-bond-ucits", 21),
    Fund("VAGP", "Vanguard Global Aggregate Bond", "IE00BG47KG48", "Bond", "Global bonds",
         "Bloomberg Global Aggregate Float Adjusted and Scaled", .0008, "Distributing",
         V + "/professional/product/etf/bond/9442/global-aggregate-bond-ucits", 20),
    Fund("IGLS", "iShares UK Gilts 0–5yr", "IE00B4WXJK79", "Bond", "Short UK gilts",
         "FTSE Actuaries UK Conventional Gilts up to 5 Years", .0007, "Distributing",
         I + "/literature/fact-sheet/igls-ishares-uk-gilts-0-5yr-ucits-etf-fund-fact-sheet-en-gb.pdf", 105),
    Fund("IGLT", "iShares Core UK Gilts", "IE00B1FZSB30", "Bond", "UK gilts",
         "FTSE Actuaries UK Conventional Gilts All Stocks", .0007, "Distributing", I + "/products/251806/", 10),
    Fund("VGOV", "Vanguard UK Gilt", "IE00B42WWV65", "Bond", "UK gilts",
         "Bloomberg Sterling Gilt Float Adjusted", .0005, "Distributing",
         V + "/professional/product/etf/bond/9501/ftse-global-all-cap-index-fund-gbp-acc", 16),
    Fund("IITU", "iShares S&P 500 Information Technology", "IE00B3WJKG14", "Equity", "US large-cap",
         "S&P 500 Capped 35/20 Information Technology", .0015, "Accumulating", I + "/products/280510/", 19),
    Fund("IBTG", "iShares US Treasury 1–3yr GBP Hedged", "IE00BDFK1N50", "Bond", "Short US Treasuries",
         "ICE US Treasury 1–3 Year Bond", .0010, "Distributing", I + "/products/296771/", 5),
    Fund("IBTS", "iShares US Treasury 1–3yr", "IE00B14X4S71", "Bond", "Short US Treasuries",
         "ICE US Treasury 1–3 Year Bond", .0007, "Distributing", I + "/products/251715/", 83),
    Fund("INXG", "iShares GBP Index-Linked Gilts", "IE00B1FZSD53", "Bond", "Inflation-linked gilts",
         "Bloomberg UK Government Inflation-Linked Bond", .0010, "Distributing", I + "/products/251717/", 14),
    Fund("SEMA", "iShares MSCI Emerging Markets", "IE00B4L5YC18", "Equity", "Emerging markets",
         "MSCI Emerging Markets", .0018, "Accumulating", I + "/products/251858/fund", 31),
    Fund("IUKP", "iShares UK Property", "IE00B1TXLS18", "Equity", "UK equity",
         "FTSE EPRA Nareit UK", .0040, "Distributing", I + "/products/251802/IUKP", 5),
    Fund("VJPN", "Vanguard FTSE Japan", "IE00B95PGT31", "Equity", "Japan equity",
         "FTSE Japan", .0010, "Distributing", V + "/professional/product/etf/equity/9504/ftse-japan-ucits-etf-distributing", 31),
    Fund("VEUR", "Vanguard FTSE Developed Europe", "IE00B945VV12", "Equity", "Europe equity",
         "FTSE Developed Europe", .0010, "Distributing", V + "/professional/product/etf/equity/9520/ftse-developed-europe-ucits-etf", 34),
)}
IDENTIFIERS = {key: ticker for ticker, fund in FUNDS.items() for key in (ticker, ticker + ".L", fund.isin)}


@dataclass(frozen=True)
class History:
    dates: tuple[date, ...]
    prices: dict[str, tuple[float, ...]]
    cutoff: date
    source: str
    stamp: str
    licence: str
    synthetic: bool
    embedded_fee: bool

    def prefix(self, stop: int, limit: int = LOOKBACK) -> History:
        start = max(0, stop - limit)
        dates = self.dates[start:stop]
        return History(dates, {ticker: values[start:stop] for ticker, values in self.prices.items()},
                       dates[-1], self.source, self.stamp, self.licence, self.synthetic, self.embedded_fee)

    def provenance(self):
        return {
            "source": self.source, "retrieved": self.stamp, "licence": self.licence,
            "first": self.dates[0].isoformat(), "last": self.dates[-1].isoformat(),
            "cutoff": self.cutoff.isoformat(), "observations": len(self.dates), "funds": len(self.prices),
            "currency": "GBP", "synthetic": self.synthetic,
        }


REGIMES = (.0006, -.0014, .0009, .00015, -.0006, .0007, .00045, .00085)


@lru_cache(maxsize=4)
def demo_history(snapshot: bool = False, seed: int = SEED) -> History:
    """Factor paths with a seed, alternating regimes and weekday-only fictional dates.

    Other seeds also shuffle the regime order, so evaluation paths differ in sequence, not only noise."""
    dates = []
    day = DEMO_END
    while len(dates) < 956:
        if day.weekday() < 5:
            dates.append(day)
        day -= timedelta(days=1)
    dates.reverse()
    rng = random.Random(seed)
    regimes = list(REGIMES)
    if seed != SEED:
        random.Random(f"regimes-{seed}").shuffle(regimes)
    groups = sorted({f.group for f in FUNDS.values()})
    current = {f.ticker: f.base for f in FUNDS.values()}
    paths: dict[str, list[float]] = {key: [] for key in FUNDS}
    for t in range(len(dates)):
        regime = regimes[min(7, t // 120)]
        equity = rng.gauss(.0024 if snapshot and t >= 881 else regime, .008)
        rates = rng.gauss(.00014, .0027)
        factors = {group: rng.gauss(0, .004 if "equity" in group or group in {"US large-cap", "Emerging markets"} else .0011) for group in groups}
        fx = rng.gauss(0, .0035)
        for f in FUNDS.values():
            if f.asset == "Bond":
                shock = rates * (.44 if f.ticker in {"IGLS", "IBTS", "IBTG"} else 1.35 if f.ticker == "INXG" else 1.13 if f.group == "UK gilts" else .77)
                if f.ticker == "IBTS":
                    shock += fx
            else:
                shock = equity * (1.35 if f.ticker == "CNX1" else .75 if f.ticker == "ISF" else 1)
            idio = rng.gauss(0, .00024 if f.asset == "Bond" else .0026)
            current[f.ticker] *= math.exp(shock + factors[f.group] + idio)
            paths[f.ticker].append(round(current[f.ticker], 6))
    label = "recovery illustration" if snapshot else "chronological evaluation path"
    return History(tuple(dates), {k: tuple(v) for k, v in paths.items()}, DEMO_END,
                   f"Campus Index synthetic GBP {label} v1 (seed {seed})", datetime.now(UTC).isoformat(timespec="seconds"),
                   "Authored for this project. No third-party market prices.", True, False)


def last_completed(now: datetime | None = None) -> date:
    """Conservative weekday cutoff. Missing holiday data requires a licensed calendar."""
    now = (now or datetime.now(UTC)).astimezone(LONDON)
    day = now.date() - timedelta(days=int(now.hour < 17))
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def validate(history: History, minimum: int = LOOKBACK) -> None:
    if (len(history.dates) < minimum or tuple(sorted(set(history.dates))) != history.dates
            or history.dates[-1] != history.cutoff or not history.prices):
        raise ValueError("Market data is stale, duplicated, future-dated, or incomplete.")
    if any((b - a).days > 5 for a, b in zip(history.dates, history.dates[1:])):
        raise ValueError("Market data has an unexplained gap of more than five calendar days.")
    for ticker, prices in history.prices.items():
        if (ticker not in FUNDS or len(prices) != len(history.dates)
                or any(not math.isfinite(p) or p <= 0 for p in prices)
                or any(abs(b / a - 1) > .25 for a, b in zip(prices, prices[1:]))):
            raise ValueError(f"{ticker} has an unsupported identifier, missing price or >25% daily outlier.")


def gbp_quote(value: float, currency: str) -> float:
    if currency in {"GBp", "GBX"}:
        return value / 100
    if currency == "GBP":
        return value
    raise ValueError("Only verified GBP and GBp listings are supported.")


@lru_cache(maxsize=2)
def licensed_csv(path: str, modified: int, manifest_modified: int, cutoff: date) -> History:
    """Load a rights-cleared wide adjusted-close file, with a separate provenance manifest."""
    manifest = json.loads(Path(path + ".json").read_text(encoding="utf-8"))
    required = {"source", "retrieved", "licence", "adjusted", "currency"}
    if (not isinstance(manifest, dict) or not required <= manifest.keys()
            or manifest["adjusted"] is not True or manifest["currency"] not in {"GBP", "GBp", "GBX"}
            or not all(isinstance(manifest[k], str) and manifest[k].strip() for k in ("source", "retrieved", "licence"))):
        raise ValueError("The price manifest must specify source, retrieval timestamp, licence and adjusted GBP/GBp prices.")
    retrieved = datetime.fromisoformat(manifest["retrieved"])
    if retrieved.tzinfo is None or retrieved > datetime.now(UTC):
        raise ValueError("Price retrieval must have an explicit, non-future timezone.")
    with open(path, encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(source, strict=True)
        header = next(reader, [])
        symbols = [IDENTIFIERS.get(x.strip().upper()) for x in header[1:]]
        if header[:1] != ["date"] or len(symbols) < 4 or None in symbols or len(symbols) != len(set(symbols)):
            raise ValueError("Price headers need date and at least four unique verified GBP listings.")
        prices = {ticker: [] for ticker in symbols}
        dates = []
        for row in reader:
            if len(row) != len(header):
                raise ValueError("An adjusted close row is incomplete.")
            day = date.fromisoformat(row[0])
            if day > cutoff:
                continue
            dates.append(day)
            for ticker, value in zip(symbols, row[1:]):
                prices[ticker].append(gbp_quote(float(value), manifest["currency"]))
    if not dates or dates[-1] != cutoff or retrieved.astimezone(LONDON).date() < dates[-1]:
        raise ValueError("The verified feed does not contain the latest completed session.")
    history = History(tuple(dates), {k: tuple(v) for k, v in prices.items()}, cutoff, manifest["source"],
                      retrieved.isoformat(), manifest["licence"], False, True)
    validate(history)
    return history


def load_history(*, full: bool = False) -> History:
    path = os.getenv("CAMPUS_PRICE_CSV")
    if path:
        cutoff = last_completed()
        for attempt in range(2):
            try:
                data = licensed_csv(path, Path(path).stat().st_mtime_ns, Path(path + ".json").stat().st_mtime_ns, cutoff)
                break
            except (OSError, ValueError, csv.Error):
                licensed_csv.cache_clear()
                if attempt:
                    raise ValueError("Licensed price validation failed after a refresh. Check source, licence, completed sessions and missing prices.") from None
    else:
        data = demo_history(snapshot=not full)
    result = data if full else data.prefix(len(data.dates))
    validate(result)
    return result
