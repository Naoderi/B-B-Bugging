from __future__ import annotations

import copy
import json
import unittest

from agent import BASE, decision
from coach import MAX_TOOL_CALLS, converse, template
from guardian import countersign, grounding


def call(name, **args):
    return {"tool_calls": [{"id": name, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}


def field(name, value, quote):
    return {"field": name, "value": value, "quote": quote}


class FakeLLM:
    """Replays scripted replies. A callable reply receives the chat so far."""

    name = "Fake LLM"

    def __init__(self, *replies):
        self.replies = list(replies)
        self.seen_tools = []

    def complete(self, messages, tools):
        self.seen_tools.append(len(tools))
        reply = self.replies.pop(0) if self.replies else {"content": "Done."}
        return reply(messages) if callable(reply) else reply


def latest_facts(messages):
    return next(json.loads(m["content"])["facts"] for m in reversed(messages)
                if m["role"] == "tool" and "facts" in json.loads(m["content"]))


def run(student, llm, paper=None):
    return list(converse([{"role": "user", "content": student}], paper, llm))


class Coach(unittest.TestCase):
    def test_missing_runway_is_asked_not_assumed(self):
        events = run("I have £1500 to invest for 3 years and it's not rent money.", FakeLLM(
            call("update_profile", fields=[field("budget", 1500, "£1500"), field("years", 3, "for 3 years"),
                                           field("essential", False, "it's not rent money"),
                                           field("runway", 6, "six months saved")]),
            call("run_analysis"),
            {"content": "Roughly how many months of rent do you have saved?"},
        ))
        kinds = [k for k, _ in events]
        self.assertNotIn("final", kinds)
        self.assertNotIn("step", kinds)
        self.assertEqual(events[-1], ("ask", {"text": "Roughly how many months of rent do you have saved?", "missing": ["runway"]}))
        self.assertIn("runway", events[0][1]["rejected"])

    def test_offline_planner_end_to_end(self):
        from planner import Planner, extract
        rent = run("My £1,500 is for rent next term and I have about 1 month saved. Go all in on Nasdaq for 100% a year.", Planner())
        self.assertEqual(rent[-1][1]["result"]["state"], "veto")
        self.assertEqual(rent[-1][1]["verdict"]["status"], "countersigned")
        good = run("I have £2,000 from my summer job that I won't need for rent or bills. I keep 4 months of costs saved "
                   "and won't touch this for 3 years. I'd like balanced growth.", Planner())
        final = good[-1][1]
        self.assertEqual(final["result"]["state"], "ready")
        self.assertEqual(final["verdict"]["status"], "countersigned")
        self.assertFalse(final["verdict"].get("fallback"))
        self.assertEqual([p["name"] for k, p in good if k == "tool"], ["update_profile", "run_analysis", "what_if", "get_evidence"])
        growth = run("I have £5,000 I don't need for bills, 8 months of cash saved, investing for 10 years, "
                     "I want growth and I can lose up to 50%.", Planner())
        self.assertEqual(growth[-1][1]["result"]["state"], "ready")
        self.assertFalse(growth[-1][1]["verdict"].get("fallback"), growth[-1][1]["verdict"])
        vague = run("I've got £800 from tutoring and want to start investing.", Planner())
        self.assertEqual(vague[-1][0], "ask")
        for text, expected in (("I don't need it for bills", False), ("I don’t need it for rent", False),
                               ("it's not rent money", False), ("this is for rent", True)):
            with self.subTest(text=text):
                self.assertEqual({f["field"]: f["value"] for f in extract(text)}["essential"], expected)

    def test_invented_figures_in_a_question_are_replaced(self):
        events = run("Hi, I want to invest.", FakeLLM({"content": "Most students earn 12% a year. How long?"}))
        self.assertTrue(events[-1][1]["text"].startswith("Before I analyse anything"))
        self.assertNotIn("12%", events[-1][1]["text"])

    def test_rent_veto_survives_a_reckless_model(self):
        student = "My £1500 is for rent, I have 1 month saved, need it in 3 years. Go all in on Nasdaq."
        reckless = {"content": "Put 100% in CNX1 [base.state] for big gains."}
        events = run(student, FakeLLM(
            call("update_profile", fields=[field("essential", True, "is for rent"), field("runway", 1, "1 month saved"),
                                           field("years", 3, "in 3 years"), field("budget", 1500, "£1500")]),
            call("run_analysis"), reckless, reckless,
        ))
        final = events[-1][1]
        self.assertEqual(final["result"]["state"], "veto")
        self.assertTrue(final["verdict"].get("fallback"))
        self.assertNotIn("CNX1", dict(events)["answer"]["text"])
        self.assertEqual(dict(events)["answer"]["text"], template(final["result"]))
        self.assertIn("returned", [p.get("status") for k, p in events if k == "guardian"])

    def test_grounded_answer_with_what_if_is_countersigned(self):
        def explain(messages):
            base = next(json.loads(m["content"])["facts"] for m in messages
                        if m["role"] == "tool" and json.loads(m["content"]).get("state") and "id" not in json.loads(m["content"]))
            alt = latest_facts(messages)
            return {"content": f"This plan passes the safety checks. Its worst sample fall was "
                               f"{base['base.metrics.drawdown']} [base.metrics.drawdown]. With a longer horizon the "
                               f"loss limit becomes {alt['w1.lossLimit']} [w1.lossLimit]. Prices are synthetic."}
        student = "I've £2000 from my summer job, not needed for rent or bills, 4 months of costs saved, for 3 years."
        events = run(student, FakeLLM(
            call("update_profile", fields=[field("budget", 2000, "£2000"), field("essential", False, "not needed for rent"),
                                           field("runway", 4, "4 months of costs saved"), field("years", 3, "for 3 years")]),
            call("run_analysis"), call("what_if", label="Five-year horizon", changes={"years": 5}), explain,
        ))
        final = events[-1][1]
        self.assertEqual(final["result"]["state"], "ready")
        self.assertEqual(final["verdict"]["status"], "countersigned", final["verdict"])
        self.assertEqual(final["whatifs"], ["w1"])
        self.assertIn("step", [k for k, _ in events])

    def test_what_if_cannot_flip_the_rent_question(self):
        student = "£2000, not for rent, 4 months saved, for 3 years."
        llm = FakeLLM(
            call("update_profile", fields=[field("essential", False, "not for rent"), field("runway", 4, "4 months saved"),
                                           field("years", 3, "for 3 years")]),
            call("run_analysis"), call("what_if", label="Sneaky", changes={"essential": False, "leverage": True}),
            {"content": "Done."},
        )
        events = run(student, llm)
        self.assertNotIn("whatif", [k for k, _ in events])

    def test_tool_budget_is_enforced(self):
        llm = FakeLLM(*[call("get_evidence")] * 20)
        events = run("Show me the evidence.", llm)
        self.assertLessEqual(sum(1 for k, p in events if k == "tool"), MAX_TOOL_CALLS)
        self.assertIn(0, llm.seen_tools)

    def test_transcript_validation(self):
        for bad in ([], [{"role": "system", "content": "x"}], [{"role": "user", "content": "x" * 2001}],
                    [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                list(converse(bad, None, FakeLLM()))


class Guardian(unittest.TestCase):
    def setUp(self):
        self.form = {**BASE}
        self.result = decision(self.form)

    def test_accepts_template_and_rejects_wrong_or_uncited_numbers(self):
        self.assertEqual(countersign(self.form, None, self.result, template(self.result))["status"], "countersigned")
        for text in ("Your drawdown was 50.0% [base.metrics.drawdown].", "You could make 12% a year.",
                     "Fees are £3.00 [base.unknown]."):
            with self.subTest(text=text):
                self.assertEqual(countersign(self.form, None, self.result, text)["status"], "rejected")

    def test_student_figures_and_rounding(self):
        drawdown = self.result["metrics"]["drawdown"] * 100
        table = {"base.metrics.drawdown": (self.result["metrics"]["drawdown"], "pct")}
        self.assertEqual(grounding(f"A fall of about {round(drawdown)}% [base.metrics.drawdown].", table), [])
        self.assertEqual(grounding("You said £600 rent [student].", {}, "rent is £600"), [])
        self.assertTrue(grounding("You said £700 rent [student].", {}, "rent is £600"))

    def test_rejects_tampered_or_levered_proposals(self):
        tampered = copy.deepcopy(self.result)
        first = next(iter(tampered["weights"]))
        tampered["weights"][first] += .05
        self.assertIn("different proposal", " ".join(countersign(self.form, None, tampered, "")["reasons"]))
        levered = {**copy.deepcopy(self.result), "portfolioLeverage": 2.}
        self.assertEqual(countersign(self.form, None, levered, "")["status"], "rejected")
        rent = {**BASE, "essential": True}
        self.assertIn("veto", " ".join(countersign(rent, None, self.result, "")["reasons"]))


class CoachServer(unittest.TestCase):
    def setUp(self):
        import tempfile
        import threading
        from http.server import ThreadingHTTPServer
        from pathlib import Path
        from unittest.mock import patch

        import paper
        import server
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for target in (patch.object(paper, "DB", Path(tmp.name) / "paper.sqlite3"),
                       patch.dict("os.environ", {"ASI_ONE_API_KEY": "test"}),
                       patch("coach.from_env", lambda: self.llm)):
            target.start()
            self.addCleanup(target.stop)
        paper.setup()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.port = self.httpd.server_port

    def post(self, path, body, cookie=None):
        import http.client
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        headers = {"Content-Type": "application/json", "X-Campus-Paper": "1", "Host": f"127.0.0.1:{self.port}"}
        if cookie:
            headers["Cookie"] = cookie
        connection.request("POST", path, json.dumps(body), headers)
        response = connection.getresponse()
        return response.status, response.read().decode(), response.getheader("Set-Cookie")

    def test_coach_turn_creates_countersigned_proposal_and_needs_human_approval(self):
        import paper
        student = "I've £2000 from my summer job, not needed for rent or bills, 4 months of costs saved, for 3 years."
        self.llm = FakeLLM(
            call("update_profile", fields=[field("budget", 2000, "£2000"), field("essential", False, "not needed for rent"),
                                           field("runway", 4, "4 months of costs saved"), field("years", 3, "for 3 years")]),
            call("run_analysis"), lambda messages: {"content": template(decision({**BASE, "budget": 2000, "runway": 4, "years": 3}))},
        )
        status, body, cookie = self.post("/api/coach", {"messages": [{"role": "user", "content": student}]})
        self.assertEqual(status, 200, body)
        events = [json.loads(line) for line in body.splitlines() if line]
        final = events[-1]["value"]
        self.assertEqual(events[-1]["type"], "final")
        self.assertEqual(final["verdict"]["status"], "countersigned")
        self.assertIn("id", final["result"])
        sid = cookie.split("campus_lab=")[1].split(";")[0]
        state = paper.get_state(sid)
        self.assertEqual(state["pending"]["id"], final["result"]["id"])
        self.assertIsNone(state["paper"])
        actions = [row["action"] for row in state["audit"]]
        self.assertIn("Guardian countersigned", actions)
        self.assertIn("Coach tool • run_analysis", actions)
        with self.assertRaisesRegex(ValueError, "confirmation"):
            paper.action(sid, final["result"]["id"], "approve", False)
        self.assertIsNotNone(paper.action(sid, final["result"]["id"], "approve", True)["paper"])

    def test_pause_blocks_the_coach(self):
        import paper
        self.llm = FakeLLM()
        status, _, cookie = self.post("/api/coach", {"messages": [{"role": "user", "content": "hi"}]})
        sid = cookie.split("campus_lab=")[1].split(";")[0]
        paper.pause(sid, True)
        status, body, _ = self.post("/api/coach", {"messages": [{"role": "user", "content": "hi"}]}, f"campus_lab={sid}")
        self.assertEqual(status, 422)
        self.assertIn("paused", body)


if __name__ == "__main__":
    unittest.main()
