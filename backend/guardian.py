"""Risk Guardian: deterministic countersignature for coach proposals. No model calls."""
from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

from agent import decision
from strategy import Profile, suitability

CITE = re.compile(r"\[([A-Za-z0-9_.\-]+)\]")
FIGURE = re.compile(r"£\s?(?P<gbp>\d[\d,]*(?:\.\d+)?)|(?P<pct>\d+(?:\.\d+)?)\s?%|(?P<x>\d+(?:\.\d+)?)\s?×")
SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")
CORE = ("state", "weights", "cash", "nav", "fee", "traded", "exposure", "portfolioLeverage", "metrics", "verified")
SEEDS_REPORT = Path(__file__).parent / "evidence" / "multi-seed" / "summary.json"


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def facts(result: dict, prefix: str) -> dict[str, tuple]:
    """Flatten a decision into citable (value, unit) facts. Units: pct fraction, gbp pennies, x, num, text."""
    table = {}

    def put(key, value, unit):
        if value is not None and not isinstance(value, bool):
            table[f"{prefix}.{key}"] = (value, unit)

    for key in ("state", "reason", "riskRule", "fit"):
        put(key, result.get(key), "text")
    for key in ("target", "lossLimit", "exposureCap", "equityCap", "exposure", "turnover"):
        put(key, result.get(key), "pct")
    for key in ("balance", "monthly", "cash", "nav", "fee", "traded"):
        put(key, result.get(key), "gbp")
    for key in ("horizon", "runway", "category"):
        put(key, result.get(key), "num")
    put("portfolioLeverage", result.get("portfolioLeverage"), "x")
    for key, value in (result.get("metrics") or {}).items():
        if key == "stress":
            for name, loss in value.items():
                put(f"stress.{slug(name)}", loss, "pct")
        else:
            put(f"metrics.{key}", value, "num" if key == "sharpe" else "pct")
    for row in result.get("positions") or []:
        put(f"weight.{row['ticker']}", row["weight"], "pct")
        put(f"value.{row['ticker']}", row["value"], "gbp")
    for ticker, reason in (result.get("exclusions") or {}).items():
        put(f"excluded.{ticker}", reason, "text")
    leverage = result.get("leverage") or {}
    put("leverage.state", leverage.get("state"), "text")
    put("leverage.requested", leverage.get("requested"), "x")
    for key in ("drawdown", "stress"):
        put(f"leverage.{key}", leverage.get(key), "pct")
    return table


@lru_cache(maxsize=1)
def evidence_facts() -> dict[str, tuple]:
    from backtest import offline_evidence
    evidence = offline_evidence()
    table = {"evidence.source": (evidence["source"], "text"),
             "evidence.ro_vs_6040": (evidence["difference"], "pct")}
    for path, key in zip(evidence["paths"], ("ro", "equity", "balanced")):
        for metric in ("total", "drawdown", "volatility", "costDrag"):
            table[f"evidence.{key}.{metric}"] = (path[metric], "pct")
    if SEEDS_REPORT.exists():
        seeds = json.loads(SEEDS_REPORT.read_text(encoding="utf-8"))
        table["evidence.seeds.count"] = (seeds["seeds"], "num")
        for key in ("medianExcess", "medianDrawdownReduction", "drawdownWinRate", "returnWinRate"):
            table[f"evidence.seeds.{key}"] = (seeds[key], "pct")
    return table


def display(value, unit: str) -> str:
    if unit == "pct":
        return f"{value * 100:.1f}%"
    if unit == "gbp":
        return f"£{value / 100:,.2f}"
    if unit == "x":
        return f"{value:.1f}×"
    if unit == "num":
        return f"{value:.2f}" if isinstance(value, float) and not value.is_integer() else f"{value:g}"
    return str(value)


def figures(text: str) -> list[tuple[str, float, int]]:
    found = []
    for match in FIGURE.finditer(text):
        kind = match.lastgroup
        raw = match.group(kind).replace(",", "")
        found.append((kind, float(raw), len(raw.split(".")[1]) if "." in raw else 0))
    return found


def matches(kind: str, number: float, places: int, value, unit: str) -> bool:
    scale = {("pct", "pct"): 100, ("gbp", "gbp"): .01, ("x", "x"): 1}.get((kind, unit))
    if scale is None or not isinstance(value, (int, float)):
        return False
    return abs(number - abs(value) * scale) <= .5 * 10 ** -places + 1e-9


def grounding(text: str, table: dict[str, tuple], student: str = "") -> list[str]:
    """Every £, % and × figure must match a fact cited in the same sentence, or a figure the student wrote."""
    problems = [f"Unknown citation [{cid}]." for cid in dict.fromkeys(CITE.findall(text))
                if cid != "student" and cid not in table]
    said = figures(student)
    for sentence in SENTENCE.split(text):
        cited = [table[cid] for cid in CITE.findall(sentence) if cid in table]
        for kind, number, places in figures(CITE.sub("", sentence)):
            if any(matches(kind, number, places, *fact) for fact in cited):
                continue
            if "[student]" in sentence and any(k == kind and abs(n - number) < 1e-9 for k, n, _ in said):
                continue
            problems.append(f"Ungrounded figure in: “{sentence.strip()[:140]}”")
            break
    return problems


def digest(result: dict) -> str:
    core = json.dumps({key: result.get(key) for key in CORE}, sort_keys=True, allow_nan=False)
    return hashlib.sha256(core.encode()).hexdigest()


def countersign(form: dict, paper: dict | None, result: dict, explanation: str,
                student: str = "", whatifs: dict[str, dict] | None = None) -> dict:
    """Recompute everything the coach relied on, then accept or reject. The coach's numbers are never trusted."""
    checks, reasons = [], []
    try:
        risk = suitability(Profile.parse(form))
    except ValueError as error:
        risk = None
        reasons.append(f"Profile failed validation: {error}")
    if risk and risk.veto and result.get("state") != "veto":
        reasons.append("An affordability veto applies but the proposal is not vetoed.")
    elif risk:
        checks.append("Affordability rules re-applied")
    rerun = decision(form, paper)
    if digest(rerun) != digest(result):
        reasons.append("An independent rerun produced a different proposal.")
    else:
        checks.append("Independent rerun matched the proposal digest")
    if result.get("state") == "ready":
        if result.get("portfolioLeverage") != 1 or result.get("exposure", 2) > 1 + 1e-10 or not result.get("verified"):
            reasons.append("Only verified, unlevered allocations can reach approval.")
        else:
            checks.append("Unlevered and verifier-passed")
    table = {**facts(rerun, "base"), **evidence_facts()}
    for key, alternative in (whatifs or {}).items():
        table.update(facts(decision(alternative, paper), key))
    problems = grounding(explanation, table, student)
    if not problems:
        checks.append("Every figure in the explanation matches a cited, recomputed fact")
    return {"status": "rejected" if reasons or problems else "countersigned", "checks": checks,
            "reasons": reasons, "grounding": problems, "digest": digest(result)}
