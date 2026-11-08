"""Read-only tools the coach can call. Every number they return comes from the deterministic engine."""
from __future__ import annotations

import hashlib
import json
import re

from agent import BASE, decision, work
from guardian import display, evidence_facts, facts
from market import FUNDS

SAFETY = ("essential", "runway", "years")
NUMBERS = {"target", "years", "budget", "monthly", "loss", "runway", "maxLeverage"}
CHOICES = {"objective": ("stability", "balance", "growth"), "volatility": ("low", "moderate", "high")}
FLAGS = {"essential", "leverage"}
WHAT_IF = {"years", "runway", "loss", "volatility", "objective", "budget", "monthly", "target"}
MAX_WHATIFS = 3

SPECS = [
    {"type": "function", "function": {
        "name": "update_profile",
        "description": "Record facts the student stated. Each field needs the student's exact words as a quote. "
                       "Fields: target (% a year), years (horizon), budget (£ to invest), monthly (£ a month), "
                       "loss (max tolerable loss %), runway (months of essential costs held in cash elsewhere), "
                       "objective (stability|balance|growth), volatility (low|moderate|high), "
                       "essential (true if the money might pay rent, tuition or bills), leverage (true if requested).",
        "parameters": {"type": "object", "required": ["fields"], "properties": {"fields": {
            "type": "array", "items": {"type": "object", "required": ["field", "value", "quote"], "properties": {
                "field": {"type": "string"}, "value": {}, "quote": {"type": "string"}}}}}}}},
    {"type": "function", "function": {
        "name": "run_analysis",
        "description": "Run the verified Campus Index analysis on the recorded profile. Needs essential, runway and years. "
                       "Returns citable fact ids.",
        "parameters": {"type": "object", "properties": {
            "holdings": {"type": "string", "enum": ["none", "paper"],
                         "description": "paper = start from the student's approved paper positions."}}}}},
    {"type": "function", "function": {
        "name": "what_if",
        "description": "Rerun the analysis with up to three hypothetical changes for comparison. It cannot change "
                       "essential or leverage, and its results are never approvable.",
        "parameters": {"type": "object", "required": ["label", "changes"], "properties": {
            "label": {"type": "string"}, "changes": {"type": "object"}}}}},
    {"type": "function", "function": {
        "name": "explain_fund",
        "description": "Issuer-sourced facts for one supported LSE ETF ticker.",
        "parameters": {"type": "object", "required": ["ticker"], "properties": {"ticker": {"type": "string"}}}}},
    {"type": "function", "function": {
        "name": "get_evidence",
        "description": "Backtest evidence for the strategy against passive baselines, with citable fact ids.",
        "parameters": {"type": "object", "properties": {}}}},
]


def normalise_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[‘’]", "'", text)).strip().lower()


def short_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()[:12]


def citable(table: dict) -> dict[str, str]:
    return {key: display(value, unit) for key, (value, unit) in table.items()}


class Session:
    """One coach turn. Holds the drafted profile and every analysis the coach asked for."""

    def __init__(self, student: str, paper: dict | None):
        self.student = normalise_text(student)
        self.paper = paper
        self.form = {**BASE, "positions": [], "acknowledged": False}
        self.quotes: dict[str, str] = {}
        self.base = None
        self.base_form = None
        self.whatifs: dict[str, dict] = {}
        self.table: dict[str, tuple] = dict(evidence_facts())

    def missing(self) -> list[str]:
        # A quoted fact that alone triggers the affordability veto makes the other questions moot.
        if self.form.get("essential") is True and "essential" in self.quotes:
            return []
        if "runway" in self.quotes and self.form["runway"] < 3:
            return []
        return [field for field in SAFETY if field not in self.quotes]

    def dispatch(self, name: str, args: dict) -> tuple[dict, list[tuple]]:
        handler = getattr(self, f"tool_{name}", None) if name in {s["function"]["name"] for s in SPECS} else None
        if handler is None:
            return {"error": f"Unknown tool {name}."}, []
        try:
            return handler(**args)
        except TypeError:
            return {"error": f"Invalid arguments for {name}."}, []

    def tool_update_profile(self, fields) -> tuple[dict, list]:
        accepted, rejected = {}, {}
        for item in fields if isinstance(fields, list) else []:
            field, value, quote = (item.get(k) for k in ("field", "value", "quote")) if isinstance(item, dict) else (None,) * 3
            if field not in NUMBERS | FLAGS | set(CHOICES):
                rejected[str(field)] = "Unsupported field."
            elif not isinstance(quote, str) or len(quote.strip()) < 2 or normalise_text(quote) not in self.student:
                rejected[field] = "Quote not found in the student's messages. Ask the student instead of assuming."
            elif field in FLAGS and type(value) is not bool:
                rejected[field] = "Use true or false."
            elif field in CHOICES and value not in CHOICES[field]:
                rejected[field] = f"Use one of {', '.join(CHOICES[field])}."
            elif field in NUMBERS and (isinstance(value, bool) or not isinstance(value, (int, float))):
                rejected[field] = "Use a number."
            else:
                self.form[field] = value
                self.quotes[field] = quote.strip()
                accepted[field] = value
        content = {"accepted": accepted, "rejected": rejected, "missingSafetyFacts": self.missing(),
                   "defaultsInUse": {k: BASE[k] for k in NUMBERS | set(CHOICES) | FLAGS if k not in self.quotes}}
        event = ("tool", {"name": "update_profile", "summary": f"Recorded {len(accepted)} quoted facts. "
                          + (f"Still needed: {', '.join(self.missing())}." if self.missing() else "Safety facts complete."),
                          "quotes": {k: self.quotes[k] for k in accepted}, "rejected": rejected})
        return content, [event]

    def tool_run_analysis(self, holdings="none") -> tuple[dict, list]:
        if self.missing():
            return {"error": "Ask the student about: " + ", ".join(self.missing()) + ". Do not assume them."}, []
        if holdings == "paper" and not self.paper:
            return {"error": "The student has no approved paper positions."}, []
        form = {**self.form, "mode": "paper" if holdings == "paper" else "zero"}
        events, result = [], None
        for event in work(form, self.paper):
            if event[0] == "result":
                result = event[1]
            else:
                events.append(("step", {"scenario": "base", "status": event[0], "key": event[1], "detail": event[2]}))
        self.base, self.base_form = result, form
        self.table.update(facts(result, "base"))
        table = citable(facts(result, "base"))
        events.append(("tool", {"name": "run_analysis", "summary": f"Verified analysis finished: {result['state']}.",
                                "digest": short_hash(table)}))
        return {"state": result["state"], "facts": table}, events

    def tool_what_if(self, label, changes) -> tuple[dict, list]:
        if self.base is None:
            return {"error": "Run the main analysis first."}, []
        if len(self.whatifs) >= MAX_WHATIFS:
            return {"error": "What-if budget used. Answer the student now."}, []
        if not isinstance(changes, dict) or not changes or not set(changes) <= WHAT_IF:
            return {"error": "Changes must use only: " + ", ".join(sorted(WHAT_IF)) + "."}, []
        key = f"w{len(self.whatifs) + 1}"
        form = {**self.base_form, **changes}
        result = decision(form, self.paper)
        self.whatifs[key] = form
        self.table.update(facts(result, key))
        table = citable(facts(result, key))
        events = [("whatif", {"id": key, "label": str(label)[:80], "changes": changes, "result": result}),
                  ("tool", {"name": "what_if", "summary": f"{key} “{str(label)[:60]}”: {result['state']}.",
                            "digest": short_hash(table)})]
        return {"id": key, "hypothetical": True, "state": result["state"], "facts": table}, events

    def tool_explain_fund(self, ticker) -> tuple[dict, list]:
        fund = FUNDS.get(str(ticker).upper().removesuffix(".L"))
        if not fund:
            return {"error": "Unsupported ticker. Only the 19 registered LSE GBP listings are available."}, []
        public = fund.public()
        content = {k: public[k] for k in ("ticker", "name", "isin", "asset", "group", "index", "income", "source")}
        content["ongoingCharge"] = f"{fund.fee * 100:.2f}%"
        return content, [("tool", {"name": "explain_fund", "summary": f"Issuer facts for {fund.ticker}."})]

    def tool_get_evidence(self) -> tuple[dict, list]:
        table = citable(evidence_facts())
        content = {"facts": table, "caveat": "Synthetic generated prices. This cannot establish a real ETF performance edge."}
        return content, [("tool", {"name": "get_evidence", "summary": "Loaded backtest evidence.", "digest": short_hash(table)})]
