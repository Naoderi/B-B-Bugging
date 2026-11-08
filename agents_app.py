"""Run the Campus Index uAgents: the Risk Guardian and the chat-enabled Coach.

    python agents_app.py guardian   # countersigns proposals by agent message or REST
    python agents_app.py coach      # ASI:One chat protocol agent, discoverable on Agentverse

Both need a private seed in CAMPUS_GUARDIAN_SEED / CAMPUS_COACH_SEED. The coach also needs ASI_ONE_API_KEY.
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from uagents import Agent, Context, Model, Protocol
from uagents.crypto import Identity
from uagents_core.contrib.protocols.chat import ChatAcknowledgement, ChatMessage, TextContent, chat_protocol_spec

import coach
import guardian

GUARDIAN_PORT = int(os.getenv("CAMPUS_GUARDIAN_PORT", "8101"))
COACH_PORT = int(os.getenv("CAMPUS_COACH_PORT", "8100"))


class CountersignRequest(Model):
    form: dict
    paper: Optional[dict] = None
    result: dict
    explanation: str
    student: str = ""
    whatifs: dict = {}


class Countersignature(Model):
    status: str
    checks: list[str]
    reasons: list[str]
    grounding: list[str]
    digest: str


def seed(name: str) -> str:
    value = os.getenv(name)
    if not value or len(value) < 16:
        sys.exit(f"Set {name} to a private phrase of at least 16 characters.")
    return value


def sign(request: CountersignRequest) -> Countersignature:
    verdict = guardian.countersign(request.form, request.paper, request.result, request.explanation,
                                   request.student, request.whatifs)
    return Countersignature(**{key: verdict[key] for key in Countersignature.__fields__})


def guardian_agent() -> Agent:
    agent = Agent(name="campus-index-guardian", seed=seed("CAMPUS_GUARDIAN_SEED"), port=GUARDIAN_PORT,
                  endpoint=[f"http://127.0.0.1:{GUARDIAN_PORT}/submit"],
                  description="Deterministic risk guardian. Recomputes Campus Index proposals and rejects ungrounded figures.")

    @agent.on_message(CountersignRequest, replies=Countersignature)
    async def on_request(ctx: Context, sender: str, msg: CountersignRequest):
        verdict = await asyncio.get_running_loop().run_in_executor(None, sign, msg)
        ctx.logger.info(f"{verdict.status} for {sender[:16]}… digest {verdict.digest[:12]}")
        await ctx.send(sender, verdict)

    @agent.on_rest_post("/countersign", CountersignRequest, Countersignature)
    async def on_rest(ctx: Context, req: CountersignRequest) -> Countersignature:
        verdict = await asyncio.get_running_loop().run_in_executor(None, sign, req)
        ctx.logger.info(f"{verdict.status} via REST, digest {verdict.digest[:12]}")
        return verdict

    return agent


def reply_text(events: list[tuple]) -> str:
    kinds = dict(events)
    if "answer" not in kinds:
        return kinds.get("ask", {}).get("text") or "Tell me your goal and when you might need the money."
    final = kinds["final"]
    verdict = final["verdict"]
    status = (f"Risk Guardian countersigned ({len(verdict['checks'])} checks)." if verdict["status"] == "countersigned"
              else "Risk Guardian rejected this: " + "; ".join(verdict["reasons"] + verdict["grounding"]))
    action = (" To act on it, run Campus Index locally. Paper changes always need your approval in the app."
              if final["result"]["state"] == "ready" else "")
    return f"{kinds['answer']['text']}\n\n{status}{action}"


def coach_agent() -> Agent:
    llm = coach.from_env()
    guardian_address = Identity.from_seed(seed("CAMPUS_GUARDIAN_SEED"), 0).address
    agent = Agent(name="campus-index-coach", seed=seed("CAMPUS_COACH_SEED"), port=COACH_PORT, mailbox=True,
                  description="Rent-safe ETF coach for UK students. Fictional paper portfolios only.")
    chat = Protocol(spec=chat_protocol_spec)

    @chat.on_message(ChatMessage)
    async def on_chat(ctx: Context, sender: str, msg: ChatMessage):
        await ctx.send(sender, ChatAcknowledgement(timestamp=datetime.now(timezone.utc), acknowledged_msg_id=msg.msg_id))
        text = " ".join(item.text for item in msg.content if isinstance(item, TextContent)).strip()[:coach.MAX_CHARS]
        if not text:
            return
        history = [*(ctx.storage.get(sender) or []), {"role": "user", "content": text}][-coach.MAX_TURNS:]
        while history[0]["role"] != "user":
            history.pop(0)
        loop = asyncio.get_running_loop()

        def countersign(form, paper, result, explanation, student="", whatifs=None):
            request = CountersignRequest(form=form, paper=paper, result=result, explanation=explanation,
                                         student=student, whatifs=whatifs or {})
            pending = asyncio.run_coroutine_threadsafe(
                ctx.send_and_receive(guardian_address, request, Countersignature, timeout=30), loop)
            response, _ = pending.result(timeout=60)
            if not isinstance(response, Countersignature):
                raise coach.CoachUnavailable("The Risk Guardian agent did not reply, so nothing was proposed.")
            return response.dict()

        def turn():
            try:
                return reply_text(list(coach.converse(history, None, llm, countersign)))
            except coach.CoachUnavailable as error:
                return str(error)

        answer = await loop.run_in_executor(None, turn)
        ctx.storage.set(sender, [*history, {"role": "assistant", "content": answer[:coach.MAX_CHARS]}])
        await ctx.send(sender, ChatMessage(timestamp=datetime.now(timezone.utc), msg_id=uuid4(),
                                           content=[TextContent(type="text", text=answer)]))

    @chat.on_message(ChatAcknowledgement)
    async def on_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
        pass

    agent.include(chat, publish_manifest=True)
    return agent


if __name__ == "__main__":
    role = sys.argv[1] if len(sys.argv) > 1 else ""
    if role not in ("guardian", "coach"):
        sys.exit(__doc__)
    asyncio.set_event_loop(asyncio.new_event_loop())  # Python 3.14 no longer creates one implicitly
    (guardian_agent if role == "guardian" else coach_agent)().run()
