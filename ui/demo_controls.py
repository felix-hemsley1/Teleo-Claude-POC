"""Hidden demo control panel, reachable at ?demo=true.

Lets the presenter reset state, repopulate demo data, and stage a "new
discovery" mid-demo.
"""
import subprocess
import sys
from pathlib import Path

import streamlit as st

from storage import db

ROOT = Path(__file__).resolve().parent.parent


def _reset_runtime_state():
    """Reset deployed agents back to fresh, clear runs/approvals."""
    conn = db.get_connection()
    try:
        conn.execute("DELETE FROM agent_runs")
        conn.execute("DELETE FROM approval_requests")
        conn.execute("UPDATE agents SET status = 'awaiting_deployment'")
        conn.execute("UPDATE workflows SET status = 'detected', hidden = 0")
        conn.commit()
    finally:
        conn.close()


def _stage_new_discovery():
    """Mark the most recently detected workflow as freshly surfaced."""
    workflows = db.fetch_workflows(status="detected", include_hidden=True)
    hidden = [w for w in workflows if w.get("hidden")]
    target = hidden[0] if hidden else (workflows[0] if workflows else None)
    if target:
        conn = db.get_connection()
        try:
            conn.execute(
                "UPDATE workflows SET hidden = 0, status = 'detected' "
                "WHERE workflow_id = ?",
                (target["workflow_id"],),
            )
            conn.commit()
        finally:
            conn.close()
        return target.get("task_name")
    return None


def render():
    st.warning("Demo control panel (?demo=true)")
    cols = st.columns(3)

    if cols[0].button("Reset state"):
        _reset_runtime_state()
        st.success("State reset: agents undeployed, runs cleared.")
        st.rerun()

    if cols[1].button("Pre-populate demo data"):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "seed_demo_data.py")],
            capture_output=True, text=True,
        )
        st.code(result.stdout or result.stderr)
        st.rerun()

    if cols[2].button("Simulate new discovery"):
        name = _stage_new_discovery()
        st.success(f"Surfaced new task: {name}" if name else "Nothing to surface.")
        st.rerun()
