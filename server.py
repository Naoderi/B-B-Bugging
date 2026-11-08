"""Run the local-only Campus Index website and same-origin JSON APIs."""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import webbrowser
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import agent
import backtest
import coach as coach_agent
import paper
from market import FUNDS

WEB = Path(__file__).parent / "web"
ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/mark.svg": ("mark.svg", "image/svg+xml"),
    "/pitch.html": ("pitch.html", "text/html; charset=utf-8"),
}


class Handler(BaseHTTPRequestHandler):
    def send_response_headers(self, status, mime, size=None):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self'; frame-ancestors 'self'; base-uri 'none'")
        if size is not None:
            self.send_header("Content-Length", str(size))
        if getattr(self, "cookie", None):
            self.send_header("Set-Cookie", f"campus_lab={self.cookie}; HttpOnly; SameSite=Strict; Path=/")
        self.end_headers()

    def send_bytes(self, status, mime, body):
        self.send_response_headers(status, mime, len(body))
        self.wfile.write(body)

    def send_json(self, status, value):
        self.send_bytes(status, "application/json; charset=utf-8",
                        json.dumps(value, allow_nan=False, ensure_ascii=False).encode())

    def workspace(self):
        try:
            cookies = SimpleCookie(self.headers.get("Cookie", ""))
            value = cookies["campus_lab"].value if "campus_lab" in cookies else None
        except CookieError:
            value = None
        sid, created = paper.session(value)
        self.cookie = sid if created else None
        return sid

    def valid_host(self):
        return self.headers.get("Host") in {
            f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}",
        }

    def do_GET(self):
        if not self.valid_host():
            self.send_json(403, {"error": "Open the local Campus Index address."})
            return
        path = urlsplit(self.path).path
        if path in ASSETS:
            filename, mime = ASSETS[path]
            self.send_bytes(200, mime, (WEB / filename).read_bytes())
        elif path == "/api/bootstrap":
            sid = self.workspace()
            self.send_json(200, {**paper.get_state(sid), "presets": agent.PRESETS, "defaults": agent.BASE,
                                 "funds": [f.public() for f in FUNDS.values()], "tools": agent.TOOLS,
                                 "synthetic": not bool(os.getenv("CAMPUS_PRICE_CSV")),
                                 "coach": {"available": True, "model": coach_agent.from_env().name,
                                           "guardian": coach_agent.guardian_from_env()[1]}})
        elif path == "/api/state":
            self.send_json(200, paper.get_state(self.workspace()))
        elif path == "/api/evidence":
            try:
                result = backtest.evaluate() if os.getenv("CAMPUS_PRICE_CSV") else backtest.offline_evidence()
                self.send_json(200, result)
            except ValueError as exc:
                self.send_json(422, {"error": str(exc)})
        else:
            self.send_json(404, {"error": "Page unavailable."})

    def do_POST(self):
        host = self.headers.get("Host")
        if (not self.valid_host() or self.headers.get("X-Campus-Paper") != "1"
                or self.headers.get("Origin") not in (None, f"http://{host}")):
            self.send_json(403, {"error": "Use the local paper workspace to make changes."})
            return
        try:
            size = int(self.headers.get("Content-Length", 0))
            if not 0 < size <= 32000:
                raise ValueError("Paper request is empty or too large.")
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError("The paper request must be an object.")
            sid = self.workspace()
            path = urlsplit(self.path).path
            if path == "/api/analyse":
                self.analyse(sid, data)
            elif path == "/api/coach":
                self.coach(sid, data)
            elif path == "/api/proposal":
                self.send_json(200, paper.action(sid, data.get("id"), data.get("operation"), data.get("confirmed")))
            elif path == "/api/pause":
                paper.pause(sid, data.get("paused"))
                self.send_json(200, paper.get_state(sid))
            else:
                self.send_json(404, {"error": "Unknown paper action."})
        except (ValueError, UnicodeError) as exc:
            self.send_json(422, {"error": str(exc)})
        except (BrokenPipeError, ConnectionResetError):
            pass

    def analyse(self, sid, data):
        run, existing = paper.begin(sid)
        self.send_response_headers(200, "application/x-ndjson; charset=utf-8")

        def emit(event):
            self.wfile.write((json.dumps(event, allow_nan=False, ensure_ascii=False) + "\n").encode())
            self.wfile.flush()

        try:
            for event in agent.work(data, existing):
                kind, *payload = event
                if kind == "result":
                    result = payload[0]
                    if result["state"] == "ready" and not paper.save(sid, run, result):
                        result = {"state": "error", "reason": "A newer analysis superseded this run."}
                    else:
                        paper.record(sid, "Decision recorded", result["state"], run)
                    emit({"type": "result", "value": result})
                else:
                    key, detail = payload
                    name = dict(agent.TOOLS)[key]
                    paper.record(sid, name if kind == "step" else f"Blocked • {name}", detail, run)
                    emit({"type": kind, "key": key, "detail": detail})
        except (BrokenPipeError, ConnectionResetError):
            paper.record(sid, "Client disconnected", "The analysis stream closed before all events were delivered.", run)
        except Exception:
            paper.record(sid, "Analysis interrupted", "Unexpected local error. No new proposal was created.", run)
            sys.stderr.write("Campus Index analysis interrupted.\n")
            emit({"type": "result", "value": {"state": "error", "reason": "Analysis was interrupted. Try again."}})


    def coach(self, sid, data):
        state = paper.get_state(sid)
        messages = coach_agent.clean(data.get("messages"))
        if state["paused"]:
            raise ValueError("Paper actions are paused. Resume them to use the coach.")
        llm = coach_agent.from_env()
        countersign, guardian_name = coach_agent.guardian_from_env()
        turn = "coach-" + secrets.token_urlsafe(9)
        self.send_response_headers(200, "application/x-ndjson; charset=utf-8")

        def emit(event):
            self.wfile.write((json.dumps(event, allow_nan=False, ensure_ascii=False) + "\n").encode())
            self.wfile.flush()

        paper.record(sid, "Coach turn started", f"Student message received. Coach: {llm.name}. Countersigning by {guardian_name}.", turn)
        try:
            for kind, value in coach_agent.converse(messages, state["paper"], llm, countersign):
                if kind == "tool":
                    paper.record(sid, f"Coach tool • {value['name']}",
                                 value["summary"] + (f" Facts digest {value['digest']}." if value.get("digest") else ""), turn)
                elif kind == "guardian":
                    detail = "; ".join(value["reasons"] + value["grounding"]) or "; ".join(value["checks"])
                    paper.record(sid, f"Guardian {value['status']}", detail, turn)
                    value = {**value, "agent": guardian_name}
                elif kind == "whatif":
                    r = value["result"]
                    value = {**value, "result": {k: r.get(k) for k in ("state", "reason", "weights", "metrics", "lossLimit", "category", "risk")}}
                elif kind == "final":
                    result, verdict = value["result"], value["verdict"]
                    if result["state"] == "ready" and verdict["status"] == "countersigned":
                        run, _ = paper.begin(sid)
                        result = {**result, "countersignature": {**verdict, "agent": guardian_name},
                                  "coachQuotes": value["quotes"]}
                        if not paper.save(sid, run, result):
                            result = {"state": "error", "reason": "A newer analysis superseded this coach proposal."}
                    paper.record(sid, "Coach decision recorded", f"{result['state']} · Guardian {verdict['status']}", turn)
                    value = {"result": result, "verdict": {**verdict, "agent": guardian_name}, "quotes": value["quotes"]}
                emit({"type": kind, "value": value})
        except coach_agent.CoachUnavailable as error:
            paper.record(sid, "Coach unavailable", str(error), turn)
            emit({"type": "error", "value": {"reason": str(error)}})
        except (BrokenPipeError, ConnectionResetError):
            paper.record(sid, "Client disconnected", "The coach stream closed early. No proposal was created.", turn)
        except Exception:
            paper.record(sid, "Coach interrupted", "Unexpected local error. No new proposal was created.", turn)
            sys.stderr.write("Campus Index coach interrupted.\n")
            emit({"type": "error", "value": {"reason": "The coach was interrupted. Try again."}})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--open", action="store_true", help="Open the website in your browser.")
    args = parser.parse_args()
    paper.setup()
    with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as server:
        url = f"http://127.0.0.1:{server.server_port}"
        print(f"Campus Index is ready at {url}", flush=True)
        if args.open:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
