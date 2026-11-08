"""Offline coach policy: drives the same tools as an LLM would, with rules instead of a model.

It reads the student's words, quotes them into update_profile, asks for missing safety facts,
runs the analysis, chooses one helpful what-if, loads the evidence and writes a fully cited answer.
"""
from __future__ import annotations

import json
import re

NAME = "Offline planner (rule-based, no LLM)"
WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
         "nine": 9, "ten": 10, "twelve": 12, "a": 1}
NUMBER = r"(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|twelve)"
NEGATION = r"(?:\bnot\b|n[’']t\b|\bnever\b|\bno longer\b|\bwont\b|\bdont\b|\bisnt\b)"
ESSENTIALS = r"(?:rent|tuition|bills?|fees|food|living costs|essentials)"


def value(token: str) -> float:
    return float(WORDS.get(token.lower(), token))


def find(pattern: str, text: str):
    return re.search(pattern, text, re.IGNORECASE)


def extract(text: str) -> list[dict]:
    """Each fact keeps the exact words it came from, so the tool layer can verify the quote."""
    fields = []

    def add(field, val, match):
        fields.append({"field": field, "value": val, "quote": match.group(0).strip()})

    not_essential = find(rf"{NEGATION}[^.;!?]{{0,30}}\b{ESSENTIALS}\b", text)
    essential = find(rf"\b(?:is|are|for|need(?:ed)?|pay(?:s|ing)?|cover)\b[^.;!?]{{0,20}}\b{ESSENTIALS}\b", text)
    if not_essential:
        add("essential", False, not_essential)
    elif essential:
        add("essential", True, essential)
    if m := find(rf"\b{NUMBER}\s+months?\b", text):
        add("runway", value(m.group(1)), m)
    elif m := find(r"\bno (?:savings|emergency fund|cash buffer)\b", text):
        add("runway", 0, m)
    if m := find(rf"\b{NUMBER}\s+(?:years?|yrs?)\b", text):
        add("years", value(m.group(1)), m)
    amounts = [m for m in re.finditer(r"£\s?(\d[\d,]*(?:\.\d+)?)", text)
               if not re.match(r"\s*(?:a|per|/)\s*month|\s*monthly", text[m.end():m.end() + 12], re.IGNORECASE)
               and not re.search(r"(?:rent|bills?|costs?) (?:is|are|of)\s*$", text[max(0, m.start() - 14):m.start()], re.IGNORECASE)]
    if amounts:
        add("budget", float(amounts[0].group(1).replace(",", "")), amounts[0])
    if m := find(r"£\s?(\d[\d,]*(?:\.\d+)?)\s*(?:a|per|/)\s*month", text):
        if find(r"\b(?:invest|add|put|contribut|top)", text[max(0, m.start() - 30):m.start()]):
            add("monthly", float(m.group(1).replace(",", "")), m)
    if m := find(r"(\d+(?:\.\d+)?)\s?%\s*(?:a|per|each)\s*year|(\d+(?:\.\d+)?)\s?%\s*annual", text):
        add("target", float(m.group(1) or m.group(2)), m)
    if m := find(r"\b(?:lose|loss of|drop of|fall of)\s*(?:up to|at most)?\s*(\d+(?:\.\d+)?)\s?%", text):
        add("loss", float(m.group(1)), m)
    for pattern, objective in ((r"\b(?:safe|stab\w*|low risk|cautious)\b", "stability"),
                               (r"\b(?:grow\w*|aggressive|high risk)\b", "growth"),
                               (r"\bbalance\w*\b", "balance")):
        if m := find(pattern, text):
            add("objective", objective, m)
            break
    if m := find(r"\b(?:leverage\w*|2x|margin)\b", text):
        add("leverage", True, m)
    return fields


def turn(messages: list[dict]) -> tuple[str, list[tuple[str, dict]]]:
    """Student text so far, and the (tool name, result) pairs made since the last student message."""
    student = "\n".join(m["content"] for m in messages
                        if m["role"] == "user" and not m["content"].startswith("[Risk Guardian]"))
    start = max(i for i, m in enumerate(messages) if m["role"] == "user" and not m["content"].startswith("[Risk Guardian]"))
    names = {}
    done = []
    for m in messages[start + 1:]:
        for call in m.get("tool_calls") or []:
            names[call["id"]] = call["function"]["name"]
        if m["role"] == "tool":
            done.append((names.get(m["tool_call_id"], ""), json.loads(m["content"])))
    return student, done


def call(name: str, step: int, **args) -> dict:
    return {"content": "", "tool_calls": [{"id": f"{name}-{step}", "type": "function",
                                           "function": {"name": name, "arguments": json.dumps(args)}}]}


def choose_what_if(facts: dict) -> tuple[str, dict] | None:
    runway = float(facts.get("base.runway", "0"))
    years = float(facts.get("base.horizon", "0"))
    if facts.get("base.state") == "veto":
        if "Essential" in facts.get("base.riskRule", ""):
            return None
        if runway < 3:
            return "Build three months of cash runway first", {"runway": 3}
        if years < 1:
            return "Wait until the money is free for a year", {"years": 1}
        return None
    if runway < 6:
        return "Six months of cash runway first", {"runway": 6}
    if years < 5:
        return "A five-year horizon", {"years": 5}
    return "A stricter loss limit", {"loss": 10}


def answer(base: dict, alt: dict | None, label: str | None, evidence: dict) -> str:
    state = base.get("base.state")
    if state in ("veto", "error"):
        text = [f"Investing this money is not appropriate yet: {base.get('base.reason')} [base.reason]",
                "The Risk Guardian will not let a proposal through until that rule is met."]
        if alt:
            outcome = "a paper allocation becomes possible" if alt.get("w1.state") == "ready" else "it would still be blocked"
            text.append(f"In a what-if where you {label.lower()}, {outcome} [w1.state].")
        return " ".join(text)
    weights = [k.removeprefix("base.weight.") for k in base if k.startswith("base.weight.")]
    holdings = ", ".join(f"{t} {base[f'base.weight.{t}']} [base.weight.{t}]" for t in weights)
    stress = max((k for k in base if k.startswith("base.stress.")), key=lambda k: float(base[k].rstrip("%")))
    text = ["Your plan passes the affordability checks, so a small paper ETF portfolio is reasonable to explore.",
            f"The verified allocation is {holdings}, with {base['base.cash']} left as cash [base.cash].",
            f"Its worst fall in the synthetic sample was {base['base.metrics.drawdown']} [base.metrics.drawdown], and the worst "
            f"modelled shock would lose {base[stress]} [{stress}] against your {base['base.lossLimit']} loss limit [base.lossLimit]."]
    if float(base.get("base.target", "0").rstrip("%")) >= 100:
        text.append(f"A {base['base.target']} yearly target [base.target] is not supported by any evidence here, so it does not change the allocation.")
    if alt and alt.get("w1.state") == "ready":
        text.append(f"With {label.lower()}, the loss limit would be {alt['w1.lossLimit']} [w1.lossLimit] and the worst "
                    f"sample fall {alt['w1.metrics.drawdown']} [w1.metrics.drawdown].")
    if "evidence.seeds.drawdownWinRate" in evidence:
        text.append(f"In {evidence['evidence.seeds.count']} unseen synthetic markets this strategy had a lower drawdown than 60/40 in "
                    f"{evidence['evidence.seeds.drawdownWinRate']} of them [evidence.seeds.drawdownWinRate], "
                    f"but beat it on return in only {evidence['evidence.seeds.returnWinRate']} [evidence.seeds.returnWinRate].")
    text.append("Treat it as a way to limit losses, not to chase returns. Prices are synthetic and nothing changes until you approve.")
    return " ".join(text)


class Planner:
    name = NAME

    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        student, done = turn(messages)
        names = [name for name, _ in done]
        results = dict(done)
        if "update_profile" not in names:
            return call("update_profile", len(done), fields=extract(student))
        if results["update_profile"].get("missingSafetyFacts"):
            return {"content": ""}
        if "run_analysis" not in names:
            holdings = "paper" if find(r"\bcheck(?:ing)?[ -]in\b|\bmy (?:approved|paper)\b", student) else "none"
            return call("run_analysis", len(done), holdings=holdings)
        base = results["run_analysis"].get("facts")
        if base is None:
            return call("run_analysis", len(done), holdings="none") if names.count("run_analysis") < 2 else {"content": ""}
        choice = choose_what_if(base)
        if choice and "what_if" not in names and tools:
            return call("what_if", len(done), label=choice[0], changes=choice[1])
        if "get_evidence" not in names and tools:
            return call("get_evidence", len(done))
        alt = results.get("what_if", {}).get("facts")
        return {"content": answer(base, alt, choice[0] if choice else None, results.get("get_evidence", {}).get("facts", {}))}
