"""Deployed Agents tab: run agents, approve gates, view history and scripts."""
import streamlit as st

from storage import db
from ui import runtime


def _success_rate(runs: list[dict]) -> str:
    finished = [r for r in runs if r["status"] in ("success", "failed", "rejected")]
    if not finished:
        return "-"
    ok = sum(1 for r in finished if r["status"] == "success")
    return f"{ok / len(finished):.0%}"


def _render_pending_approvals(run_id: str):
    pending = db.fetch_pending_approvals(run_id)
    for req in pending:
        st.warning(f"Approval needed: {req['description']}")
        c1, c2 = st.columns(2)
        if c1.button("Approve", key=f"appr_yes_{req['request_id']}", type="primary"):
            db.resolve_approval(req["request_id"], True)
            st.rerun()
        if c2.button("Reject", key=f"appr_no_{req['request_id']}"):
            db.resolve_approval(req["request_id"], False)
            st.rerun()


def render():
    st.header("Deployed Agents")

    agents = [a for a in db.fetch_agents() if a["status"] in ("deployed", "paused")]
    if not agents:
        st.info("No deployed agents yet. Deploy one from Discovered Tasks.")
        return

    any_running = False
    for agent in agents:
        runs = db.fetch_runs(agent["agent_id"], limit=10)
        last_run = runs[0] if runs else None
        total_saved = sum(r.get("minutes_saved") or 0 for r in runs)
        running = runtime.is_running(agent["agent_id"]) or (
            last_run and last_run["status"] in ("running", "awaiting_approval")
        )
        any_running = any_running or bool(running)

        with st.container(border=True):
            head = st.columns([3, 1, 1, 1])
            status_dot = "🟢" if agent["status"] == "deployed" else "⏸️"
            head[0].subheader(f"{status_dot} {agent['name']}")
            head[1].metric("Last run",
                           last_run["status"] if last_run else "never")
            head[2].metric("Success", _success_rate(runs))
            head[3].metric("Mins saved", total_saved)

            cols = st.columns(3)
            run_disabled = bool(running)
            if cols[0].button("Run Now", key=f"run_{agent['agent_id']}",
                              type="primary", disabled=run_disabled):
                launched = runtime.launch_run(agent["agent_id"], {"source": "manual"})
                if launched:
                    st.toast(f"Started {agent['name']}")
                st.rerun()

            if agent["status"] == "deployed":
                if cols[1].button("Pause", key=f"pause_{agent['agent_id']}"):
                    db.update_agent_status(agent["agent_id"], "paused")
                    st.rerun()
            else:
                if cols[1].button("Resume", key=f"resume_{agent['agent_id']}"):
                    db.update_agent_status(agent["agent_id"], "deployed")
                    st.rerun()

            if running:
                st.info("Agent is running…")
                if last_run:
                    _render_pending_approvals(last_run["run_id"])

            if last_run and last_run.get("log_text"):
                with st.expander("Latest run log"):
                    st.code(last_run["log_text"])

            with st.expander("Recent runs"):
                for r in runs:
                    st.text(f"{r['started_at'][:19]}  {r['status']:<16} "
                            f"saved={r.get('minutes_saved') or 0}m")
                    if r.get("error_message"):
                        st.caption(f"  error: {r['error_message']}")

            with st.expander("Generated script"):
                st.code(agent["generated_script"], language="python")

    if any_running:
        # Lightweight auto-refresh while a run is active.
        st.caption("Auto-refreshing while agents run…")
        st.markdown(
            "<meta http-equiv='refresh' content='2'>", unsafe_allow_html=True
        )
