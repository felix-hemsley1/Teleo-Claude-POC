"""SQLite connection management and data-access helpers for Teleo."""
import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from shared import config

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    """Create the database and all tables if they don't exist."""
    schema = SCHEMA_PATH.read_text()
    conn = get_connection()
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.utcnow().isoformat()


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------
def insert_events(rows: list[dict]) -> int:
    """Batch-insert event rows. Each dict matches the events table columns."""
    if not rows:
        return 0
    cols = [
        "event_id", "user_id", "device_id", "ts_utc", "event_type",
        "process_name", "window_title", "url", "control_type", "control_label",
        "control_value", "is_password", "semantic_label", "redacted",
        "pii_flags", "raw_json",
    ]
    placeholders = ", ".join(["?"] * len(cols))
    sql = f"INSERT OR REPLACE INTO events ({', '.join(cols)}) VALUES ({placeholders})"
    conn = get_connection()
    try:
        conn.executemany(sql, [[r.get(c) for c in cols] for r in rows])
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def count_events() -> int:
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    finally:
        conn.close()


def fetch_unenriched_events(limit: int = 50) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM events WHERE semantic_label IS NULL "
            "ORDER BY ts_utc LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def set_event_label(event_id: str, label: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE events SET semantic_label = ? WHERE event_id = ?",
            (label, event_id),
        )
        conn.commit()
    finally:
        conn.close()


def fetch_recent_events(limit: int = 100, process: Optional[str] = None) -> list[dict]:
    conn = get_connection()
    try:
        if process:
            rows = conn.execute(
                "SELECT * FROM events WHERE process_name = ? "
                "ORDER BY ts_utc DESC LIMIT ?",
                (process, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM events ORDER BY ts_utc DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def fetch_all_events_ordered() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM events ORDER BY ts_utc").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Enrichment cache
# ---------------------------------------------------------------------------
def cache_get(cache_key: str) -> Optional[str]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT semantic_label FROM enrichment_cache WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()
        return row["semantic_label"] if row else None
    finally:
        conn.close()


def cache_put(cache_key: str, label: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO enrichment_cache "
            "(cache_key, semantic_label, created_at) VALUES (?, ?, ?)",
            (cache_key, label, _now()),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------
def replace_sessions(sessions: list[dict]) -> None:
    """Clear and rewrite the sessions table (sessionization is idempotent)."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM sessions")
        conn.executemany(
            "INSERT INTO sessions (session_id, user_id, started_at, ended_at, "
            "event_count, apps_used, summary, embedding) "
            "VALUES (:session_id, :user_id, :started_at, :ended_at, "
            ":event_count, :apps_used, :summary, :embedding)",
            sessions,
        )
        conn.commit()
    finally:
        conn.close()


def fetch_recent_sessions(days_back: int = 14) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM sessions WHERE started_at >= datetime('now', ?) "
            "ORDER BY started_at",
            (f"-{days_back} days",),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------
def insert_workflow(wf: dict) -> str:
    workflow_id = wf.get("workflow_id") or str(uuid.uuid4())
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO workflows (workflow_id, detected_at, status, "
            "task_name, description, frequency, estimated_minutes_per_run, "
            "automation_confidence, occurrence_count, source_session_ids, "
            "definition_json, user_edits_json, hidden) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                workflow_id,
                wf.get("detected_at") or _now(),
                wf.get("status", "detected"),
                wf["task_name"],
                wf.get("description"),
                wf.get("frequency"),
                wf.get("estimated_minutes_per_run"),
                wf.get("automation_confidence"),
                wf.get("occurrence_count"),
                json.dumps(wf.get("source_session_ids", [])),
                wf["definition_json"],
                wf.get("user_edits_json"),
                int(wf.get("hidden", 0)),
            ),
        )
        conn.commit()
        return workflow_id
    finally:
        conn.close()


def fetch_workflows(status: Optional[str] = None, include_hidden: bool = False) -> list[dict]:
    conn = get_connection()
    try:
        clauses, params = [], []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if not include_hidden:
            clauses.append("hidden = 0")
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = conn.execute(
            f"SELECT * FROM workflows{where} ORDER BY detected_at DESC", params
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_workflow(workflow_id: str) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM workflows WHERE workflow_id = ?", (workflow_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_workflow_status(workflow_id: str, status: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE workflows SET status = ? WHERE workflow_id = ?",
            (status, workflow_id),
        )
        conn.commit()
    finally:
        conn.close()


def update_workflow_edits(workflow_id: str, edits_json: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE workflows SET user_edits_json = ? WHERE workflow_id = ?",
            (edits_json, workflow_id),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Rejected fingerprints (Milestone 3)
# ---------------------------------------------------------------------------
def add_rejected_fingerprint(fingerprint: str, task_name: str = "") -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO rejected_fingerprints "
            "(fingerprint, task_name, rejected_at) VALUES (?, ?, ?)",
            (fingerprint, task_name, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def fetch_rejected_fingerprints() -> set[str]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT fingerprint FROM rejected_fingerprints").fetchall()
        return {r["fingerprint"] for r in rows}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------
def insert_agent(agent: dict) -> str:
    agent_id = agent.get("agent_id") or str(uuid.uuid4())
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO agents (agent_id, workflow_id, deployed_at, "
            "status, name, trigger_type, trigger_config_json, generated_script) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                agent_id,
                agent["workflow_id"],
                agent.get("deployed_at") or _now(),
                agent.get("status", "awaiting_deployment"),
                agent["name"],
                agent.get("trigger_type", "manual"),
                agent.get("trigger_config_json"),
                agent["generated_script"],
            ),
        )
        conn.commit()
        return agent_id
    finally:
        conn.close()


def load_agent(agent_id: str) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM agents WHERE agent_id = ?", (agent_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def fetch_agents(status: Optional[str] = None) -> list[dict]:
    conn = get_connection()
    try:
        if status:
            rows = conn.execute(
                "SELECT * FROM agents WHERE status = ? ORDER BY deployed_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM agents ORDER BY deployed_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_agent_status(agent_id: str, status: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE agents SET status = ? WHERE agent_id = ?", (status, agent_id)
        )
        conn.commit()
    finally:
        conn.close()


def fetch_workflows_needing_scripts() -> list[dict]:
    """Detected/deployed workflows that have no agent script yet."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT w.* FROM workflows w "
            "LEFT JOIN agents a ON a.workflow_id = w.workflow_id "
            "WHERE a.agent_id IS NULL"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Agent runs
# ---------------------------------------------------------------------------
def create_run(agent_id: str, trigger_context: Optional[dict] = None) -> str:
    run_id = str(uuid.uuid4())
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO agent_runs (run_id, agent_id, started_at, status, "
            "trigger_context_json, log_text, minutes_saved) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                agent_id,
                _now(),
                "running",
                json.dumps(trigger_context or {}),
                "",
                0,
            ),
        )
        conn.commit()
        return run_id
    finally:
        conn.close()


def update_run_status(
    run_id: str,
    status: str,
    minutes_saved: Optional[int] = None,
    error_message: Optional[str] = None,
    completed_at: Optional[datetime] = None,
) -> None:
    sets, params = ["status = ?"], [status]
    if minutes_saved is not None:
        sets.append("minutes_saved = ?")
        params.append(minutes_saved)
    if error_message is not None:
        sets.append("error_message = ?")
        params.append(error_message)
    if completed_at is not None:
        sets.append("completed_at = ?")
        params.append(completed_at.isoformat())
    params.append(run_id)
    conn = get_connection()
    try:
        conn.execute(
            f"UPDATE agent_runs SET {', '.join(sets)} WHERE run_id = ?", params
        )
        conn.commit()
    finally:
        conn.close()


def update_run_log(run_id: str, log_text: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE agent_runs SET log_text = ? WHERE run_id = ?",
            (log_text, run_id),
        )
        conn.commit()
    finally:
        conn.close()


def fetch_runs(agent_id: Optional[str] = None, limit: int = 10) -> list[dict]:
    conn = get_connection()
    try:
        if agent_id:
            rows = conn.execute(
                "SELECT * FROM agent_runs WHERE agent_id = ? "
                "ORDER BY started_at DESC LIMIT ?",
                (agent_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM agent_runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Approval requests
# ---------------------------------------------------------------------------
def create_approval_request(run_id: str, description: str = "") -> str:
    request_id = str(uuid.uuid4())
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO approval_requests (request_id, run_id, description, "
            "status, created_at) VALUES (?, ?, ?, ?, ?)",
            (request_id, run_id, description, "pending", _now()),
        )
        conn.commit()
        return request_id
    finally:
        conn.close()


def get_approval_status(request_id: str) -> str:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT status FROM approval_requests WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        return row["status"] if row else "pending"
    finally:
        conn.close()


def resolve_approval(request_id: str, approved: bool) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE approval_requests SET status = ?, resolved_at = ? "
            "WHERE request_id = ?",
            ("approved" if approved else "rejected", _now(), request_id),
        )
        conn.commit()
    finally:
        conn.close()


def fetch_pending_approvals(run_id: Optional[str] = None) -> list[dict]:
    conn = get_connection()
    try:
        if run_id:
            rows = conn.execute(
                "SELECT * FROM approval_requests WHERE status = 'pending' "
                "AND run_id = ? ORDER BY created_at",
                (run_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM approval_requests WHERE status = 'pending' "
                "ORDER BY created_at"
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
