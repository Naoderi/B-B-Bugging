"""AI readiness checks: dummy credentials and local transports only, never live AI."""
from __future__ import annotations

import http.client
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error

import coach
from config import load_env
from tools import SPECS


class Configuration(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {}, clear=True)
        env.start()
        self.addCleanup(env.stop)

    def test_no_key_is_offline_and_offline_ignores_existing_keys(self):
        self.assertEqual(coach.status()["mode"], "offline")
        with patch.dict(os.environ, {"CAMPUS_COACH_PROVIDER": "offline", "ANTHROPIC_API_KEY": "dummy",
                                     "ASI_ONE_API_KEY": "dummy"}), patch("coach.Claude") as claude, patch("coach.ASIOne") as asi:
            self.assertEqual(coach.status()["mode"], "offline")
            claude.assert_not_called()
            asi.assert_not_called()

    def test_explicit_provider_requires_its_own_key(self):
        for provider in ("anthropic", "asi1"):
            with self.subTest(provider=provider), patch.dict(os.environ, {"CAMPUS_COACH_PROVIDER": provider}):
                with self.assertRaisesRegex(coach.CoachUnavailable, "missing"):
                    coach.from_env()
                self.assertFalse(coach.status()["available"])

    def test_auto_and_explicit_asi_selection_and_model_override(self):
        with patch.dict(os.environ, {"ASI_ONE_API_KEY": " dummy ", "ASI_ONE_MODEL": "asi1-mini"}):
            llm = coach.from_env()
            self.assertEqual((llm.key, llm.model), ("dummy", "asi1-mini"))
            self.assertEqual(coach.status()["mode"], "configured")
            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "dummy", "CAMPUS_COACH_PROVIDER": "asi1"}):
                self.assertIsInstance(coach.from_env(), coach.ASIOne)

    def test_missing_sdk_does_not_silently_switch_provider(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "dummy", "ASI_ONE_API_KEY": "dummy"}), \
                patch.dict("sys.modules", {"anthropic": None}):
            self.assertIn("requirements-ai.txt", coach.status()["error"])

    def test_invalid_provider_does_not_echo_setting(self):
        os.environ["CAMPUS_COACH_PROVIDER"] = "secret-accidentally-pasted"
        status = coach.status()
        self.assertFalse(status["available"])
        self.assertNotIn("secret-accidentally-pasted", json.dumps(status))

    def test_dotenv_quotes_comments_precedence_and_no_shell_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            marker = Path(directory) / "should-not-exist"
            path.write_text("# local settings\nCAMPUS_COACH_PROVIDER=offline\n"
                            "export ASI_ONE_API_KEY='dummy # literal'\nASI_ONE_MODEL=asi1 # comment\n"
                            f'TEST_LITERAL="$(touch {marker})"\n', encoding="utf-8")
            os.environ["CAMPUS_COACH_PROVIDER"] = "asi1"
            load_env(path)
            self.assertEqual(os.environ["CAMPUS_COACH_PROVIDER"], "asi1")
            self.assertEqual(os.environ["ASI_ONE_API_KEY"], "dummy # literal")
            self.assertEqual(os.environ["ASI_ONE_MODEL"], "asi1")
            self.assertIn("$(touch", os.environ["TEST_LITERAL"])
            self.assertFalse(marker.exists())

    def test_invalid_dotenv_is_atomic_and_does_not_reveal_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("ASI_ONE_API_KEY=dummy\nnot a setting secret-data\n")
            with self.assertRaisesRegex(ValueError, "line 2") as caught:
                load_env(path)
            self.assertNotIn("secret-data", str(caught.exception))
            self.assertNotIn("ASI_ONE_API_KEY", os.environ)


class ASITransport(unittest.TestCase):
    def test_authenticated_request_and_tool_results_roundtrip(self):
        call = {"id": "t1", "type": "function", "function": {"name": "get_evidence", "arguments": "{}"}}
        replies = [{"role": "assistant", "content": None, "tool_calls": [call]},
                   {"role": "assistant", "content": "This is a paper investing demo."}]
        sent = []

        def transport(request, timeout):
            self.assertEqual(request.full_url, "https://api.asi1.ai/v1/chat/completions")
            self.assertEqual(request.get_header("Authorization"), "Bearer dummy")
            self.assertEqual(timeout, 60)
            sent.append(json.loads(request.data))
            return io.BytesIO(json.dumps({"choices": [{"message": replies.pop(0)}]}).encode())

        with patch("urllib.request.urlopen", side_effect=transport):
            llm = coach.ASIOne("dummy", model="asi1-mini")
            messages = [{"role": "system", "content": coach.SYSTEM}, {"role": "user", "content": "What is this app?"}]
            reply = llm.complete(messages, SPECS)
            messages += [{**reply, "_raw": "internal-only"}, {"role": "tool", "tool_call_id": "t1", "content": "{}"}]
            self.assertIn("paper investing", llm.complete(messages, SPECS)["content"])
        self.assertEqual(sent[0]["model"], "asi1-mini")
        self.assertEqual(sent[0]["tools"], SPECS)
        self.assertNotIn("_raw", sent[1]["messages"][2])
        self.assertEqual(sent[1]["messages"][-1]["tool_call_id"], "t1")

    def test_api_errors_are_actionable_without_provider_body(self):
        for status, expected in ((401, "API key"), (404, "model"), (429, "rate-limited"), (503, "temporarily")):
            with self.subTest(status=status):
                error = urllib.error.HTTPError("https://api.asi1.ai", status, "provider-private-data", {}, None)
                self.addCleanup(error.close)
                with patch("urllib.request.urlopen", side_effect=error), self.assertRaises(coach.CoachUnavailable) as caught:
                    coach.ASIOne("dummy").complete([], [])
                self.assertIn(expected, str(caught.exception))
                self.assertNotIn("provider-private-data", str(caught.exception))

    def test_timeout_and_malformed_or_empty_responses(self):
        with patch("urllib.request.urlopen", side_effect=TimeoutError), self.assertRaisesRegex(coach.CoachUnavailable, "reached"):
            coach.ASIOne("dummy").complete([], [])
        for body in (b"not json", b"{}", b'{"choices":null}', b'{"choices":[{"message":{}}]}'):
            with self.subTest(body=body), patch("urllib.request.urlopen", return_value=io.BytesIO(body)), \
                    self.assertRaisesRegex(coach.CoachUnavailable, "unreadable"):
                coach.ASIOne("dummy").complete([], [])


class ClaudeTransport(unittest.TestCase):
    def setUp(self):
        try:
            import anthropic
            import httpx2 as httpx
        except ImportError:
            self.skipTest("Optional Claude SDK is not installed; install requirements-ai.txt to run SDK transport tests.")
        self.anthropic, self.httpx = anthropic, httpx
        env = patch.dict(os.environ, {}, clear=True)
        env.start()
        self.addCleanup(env.stop)

    def client(self, responses):
        sent = []

        def transport(request):
            self.assertEqual(str(request.url), "https://api.anthropic.com/v1/messages")
            self.assertEqual(request.headers["authorization"], "Bearer dummy")
            sent.append(json.loads(request.content))
            value = responses.pop(0)
            if isinstance(value, int):
                return self.httpx.Response(value, json={"type": "error", "error": {"type": "api_error", "message": "private-provider-body"}})
            return self.httpx.Response(200, json={"id": "msg_test", "type": "message", "role": "assistant",
                "model": "claude-opus-5-5", "content": value["content"], "stop_reason": value.get("stop_reason", "end_turn"),
                "stop_sequence": None, "usage": {"input_tokens": 12, "output_tokens": 20}})

        real_constructor = self.anthropic.Anthropic
        http = self.httpx.Client(transport=self.httpx.MockTransport(transport))
        def constructor(**kwargs):
            self.assertEqual(kwargs["timeout"], 60)
            self.assertEqual(kwargs["max_retries"], 0)
            return real_constructor(**kwargs, http_client=http)
        with patch.object(self.anthropic, "Anthropic", side_effect=constructor):
            llm = coach.Claude("dummy")
        self.addCleanup(llm.close)
        return llm, sent

    def test_real_sdk_serializes_tools_results_and_custom_model(self):
        os.environ["ANTHROPIC_MODEL"] = "claude-sonnet-5-5"
        llm, sent = self.client([
            {"content": [{"type": "tool_use", "id": "tool_1", "name": "get_evidence", "input": {}},
                         {"type": "tool_use", "id": "tool_2", "name": "get_fund", "input": {"ticker": "VWRP"}}], "stop_reason": "tool_use"},
            {"content": [{"type": "text", "text": "An ETF holds a basket of investments."}]},
        ])
        messages = [{"role": "system", "content": coach.SYSTEM}, {"role": "user", "content": "What is an ETF?"}]
        reply = llm.complete(messages, SPECS)
        self.assertEqual(len(reply["tool_calls"]), 2)
        messages += [{"role": "assistant", **reply}, {"role": "tool", "tool_call_id": "tool_1", "content": "{}"},
                     {"role": "tool", "tool_call_id": "tool_2", "content": "{}"}]
        self.assertIn("basket", llm.complete(messages, [])["content"])
        self.assertEqual(sent[0]["model"], "claude-sonnet-5-5")
        self.assertIn("input_schema", sent[0]["tools"][0])
        self.assertEqual(sent[1]["messages"][-1]["role"], "user")
        self.assertEqual(len(sent[1]["messages"][-1]["content"]), 2)
        self.assertEqual(sent[1]["tool_choice"], {"type": "none"})
        self.assertNotIn("_raw", json.dumps(sent))

    def test_real_sdk_errors_are_sanitized(self):
        for status, expected in ((401, "API key"), (404, "model"), (429, "rate-limited")):
            with self.subTest(status=status):
                llm, _ = self.client([status])
                with self.assertRaises(coach.CoachUnavailable) as caught:
                    llm.complete([{"role": "user", "content": "Hi"}], SPECS)
                self.assertIn(expected, str(caught.exception))
                self.assertNotIn("private-provider-body", str(caught.exception))

    def test_empty_and_truncated_responses_do_not_become_fake_answers(self):
        for response, expected in (({"content": []}, "empty reply"),
                                   ({"content": [{"type": "text", "text": "partial"}], "stop_reason": "max_tokens"}, "cut short")):
            with self.subTest(response=response):
                llm, _ = self.client([response])
                with self.assertRaisesRegex(coach.CoachUnavailable, expected):
                    llm.complete([{"role": "user", "content": "Hi"}], SPECS)


class WebsiteConnection(unittest.TestCase):
    def setUp(self):
        from http.server import ThreadingHTTPServer
        import paper
        import server
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for item in (patch.dict(os.environ, {"CAMPUS_COACH_PROVIDER": "asi1", "ASI_ONE_API_KEY": "dummy-private-key"}, clear=True),
                     patch.object(paper, "DB", Path(tmp.name) / "paper.sqlite3")):
            item.start()
            self.addCleanup(item.stop)
        paper.setup()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, path, messages=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)
        self.addCleanup(connection.close)
        headers = {"Content-Type": "application/json", "X-Campus-Paper": "1"}
        body = json.dumps({"messages": messages}) if messages is not None else None
        connection.request("POST" if body else "GET", path, body, headers)
        response = connection.getresponse()
        return response.status, response.read().decode()

    def test_bootstrap_describes_configuration_without_network_or_key_leak(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("No network allowed")):
            status, body = self.request("/api/bootstrap")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["coach"]["mode"], "configured")
        self.assertNotIn("dummy-private-key", body)
        self.assertEqual(self.request("/.env")[0], 404)

    def test_missing_key_keeps_site_usable_and_returns_clear_chat_error(self):
        del os.environ["ASI_ONE_API_KEY"]
        status, body = self.request("/api/bootstrap")
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(body)["coach"]["available"])
        status, body = self.request("/api/coach", [{"role": "user", "content": "What is an ETF?"}])
        self.assertEqual(status, 503)
        self.assertIn("missing", body)

    def test_real_chat_route_answers_and_preserves_followup_history(self):
        messages = [{"role": "user", "content": "What is an ETF?"}]
        answer = "An ETF is an exchange-traded fund holding a basket of investments. Its value can fall."
        sent = []
        def transport(request, timeout):
            sent.append(json.loads(request.data))
            return io.BytesIO(json.dumps({"choices": [{"message": {"role": "assistant", "content": answer}}]}).encode())
        with patch("urllib.request.urlopen", side_effect=transport):
            status, body = self.request("/api/coach", messages)
            self.assertEqual(status, 200)
            event = json.loads(body.splitlines()[-1])
            self.assertEqual(event["value"]["text"], answer)
            messages += [{"role": "assistant", "content": answer}, {"role": "user", "content": "How does diversification help?"}]
            self.assertEqual(self.request("/api/coach", messages)[0], 200)
        self.assertEqual(sent[1]["messages"][1:], messages)
        self.assertNotIn("dummy-private-key", body)

    def test_provider_failure_is_delivered_in_stream_without_secret(self):
        failure = urllib.error.HTTPError("https://api.asi1.ai", 401, "private-provider-body", {}, None)
        self.addCleanup(failure.close)
        with patch("urllib.request.urlopen", side_effect=failure):
            status, body = self.request("/api/coach", [{"role": "user", "content": "Hello"}])
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body.splitlines()[-1])["type"], "error")
        self.assertIn("API key", body)
        self.assertNotIn("private-provider-body", body)
        self.assertNotIn("dummy-private-key", body)


if __name__ == "__main__":
    unittest.main()
