"""Transactional local paper ledger. Audit events are insert-only."""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

DB = Path(os.getenv("CAMPUS_LEDGER", Path(__file__).parent / ".local" / "paper.sqlite3"))


def stamp() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def setup() -> None:
    DB.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS workspace (
                id TEXT PRIMARY KEY, paused INTEGER NOT NULL DEFAULT 0,
                paper TEXT, run TEXT
            );
            CREATE TABLE IF NOT EXISTS proposal (
                id TEXT PRIMARY KEY, workspace TEXT NOT NULL, state TEXT NOT NULL, result TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT, workspace TEXT NOT NULL,
                time TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL, run TEXT
            );
            CREATE TRIGGER IF NOT EXISTS audit_no_edit BEFORE UPDATE ON audit
                BEGIN SELECT RAISE(ABORT, 'Audit rows are append only'); END;
            CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit
                BEGIN SELECT RAISE(ABORT, 'Audit rows are append only'); END;
        """)
    DB.chmod(0o600)


@contextmanager
def connect():
    db = sqlite3.connect(DB, timeout=15)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()


def session(existing: str | None) -> tuple[str, bool]:
    with connect() as db:
        if existing and db.execute("SELECT 1 FROM workspace WHERE id=?", (existing,)).fetchone():
            return existing, False
        value = secrets.token_urlsafe(24)
        db.execute("INSERT INTO workspace(id) VALUES(?)", (value,))
        return value, True


def note(db, sid: str, action: str, detail: str, run: str | None = None):
    db.execute("INSERT INTO audit(workspace,time,action,detail,run) VALUES(?,?,?,?,?)",
               (sid, stamp(), action, detail, run))


def record(sid: str, action: str, detail: str, run: str | None = None):
    with connect() as db:
        note(db, sid, action, detail, run)


def get_state(sid: str) -> dict:
    with connect() as db:
        workspace = db.execute("SELECT * FROM workspace WHERE id=?", (sid,)).fetchone()
        pending = db.execute("SELECT result FROM proposal WHERE id=? AND workspace=? AND state='pending'",
                             (workspace["run"], sid)).fetchone()
        events = db.execute("SELECT time,action,detail,run FROM audit WHERE workspace=? ORDER BY id DESC LIMIT 150",
                            (sid,)).fetchall()
        return {"paused": bool(workspace["paused"]), "paper": json.loads(workspace["paper"] or "null"),
                "pending": json.loads(pending["result"]) if pending else None, "audit": [dict(row) for row in events]}


def begin(sid: str) -> tuple[str, dict | None]:
    run = secrets.token_urlsafe(18)
    with connect() as db:
        db.execute("UPDATE workspace SET run=? WHERE id=?", (run, sid))
        db.execute("UPDATE proposal SET state='superseded' WHERE workspace=? AND state='pending'", (sid,))
        row = db.execute("SELECT paper FROM workspace WHERE id=?", (sid,)).fetchone()
        note(db, sid, "Analysis started", "Any previous pending proposal was superseded.", run)
        return run, json.loads(row["paper"] or "null")


def save(sid: str, run: str, result: dict) -> bool:
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        workspace = db.execute("SELECT run FROM workspace WHERE id=?", (sid,)).fetchone()
        if workspace["run"] != run:
            note(db, sid, "Proposal superseded", "A newer analysis started before this one finished.", run)
            return False
        result["id"] = run
        result["created"] = stamp()
        db.execute("INSERT INTO proposal VALUES(?,?,?,?)", (run, sid, "pending", json.dumps(result)))
        note(db, sid, "Human review requested", "Verified unlevered paper proposal saved. No allocation has been applied.", run)
        return True


def pause(sid: str, paused: bool):
    if type(paused) is not bool:
        raise ValueError("Choose pause or resume for paper actions.")
    with connect() as db:
        db.execute("UPDATE workspace SET paused=? WHERE id=?", (int(paused), sid))
        note(db, sid, "Paper actions paused" if paused else "Paper actions resumed", "The student changed the execution stop control.")


def action(sid: str, proposal_id: str, operation: str, confirmed: bool) -> dict:
    if operation not in ("approve", "reject") or not isinstance(proposal_id, str):
        raise ValueError("Choose a valid paper proposal and action.")
    problem = None
    paper = None
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        workspace = db.execute("SELECT * FROM workspace WHERE id=?", (sid,)).fetchone()
        row = db.execute("SELECT * FROM proposal WHERE id=? AND workspace=?", (proposal_id, sid)).fetchone()
        if not row or row["state"] != "pending" or workspace["run"] != proposal_id:
            problem = "This proposal is no longer available. Run a new analysis."
        elif operation == "reject":
            db.execute("UPDATE proposal SET state='rejected' WHERE id=?", (proposal_id,))
            note(db, sid, "Proposal rejected", "The student declined the proposed paper changes.", proposal_id)
        elif confirmed is not True:
            problem = "Explicit human confirmation is required."
        elif workspace["paused"]:
            problem = "Paper actions are paused. Resume before approving."
        else:
            proposal = json.loads(row["result"])
            if not proposal["provenance"]["synthetic"]:
                from market import last_completed
                if proposal["provenance"]["cutoff"] != last_completed().isoformat():
                    problem = "A newer market session completed. Rerun analysis before approving."
            if (not problem and (proposal["state"] != "ready" or not proposal["verified"]
                                or proposal["portfolioLeverage"] != 1 or proposal["exposure"] > 1 + 1e-10)):
                problem = "Execution requires a verified unlevered paper allocation."
            if not problem:
                paper = {key: proposal[key] for key in ("positions", "cash", "nav", "fee", "exposure", "provenance")}
                paper.update({"approved": stamp(), "proposalId": proposal_id})
                db.execute("UPDATE workspace SET paper=? WHERE id=?", (json.dumps(paper), sid))
                db.execute("UPDATE proposal SET state='approved' WHERE id=?", (proposal_id,))
                note(db, sid, "Paper allocation applied", f"Student approved {len(paper['positions'])} fictional ETF positions.", proposal_id)
        if problem:
            note(db, sid, "Paper action blocked", problem, proposal_id)
    if problem:
        raise ValueError(problem)
    return {"paper": paper}
