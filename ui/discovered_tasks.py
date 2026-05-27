"""Discovered Tasks tab: review, edit, deploy, or reject detected workflows."""
import json

import streamlit as st

from storage import db
from pipeline.discovery import task_fingerprint


def _definition(wf: dict) -> dict:
    try:
        return json.loads(wf.get("definition_json") or "{}")
    except json.JSONDecodeError:
        return {}


def _deploy(workflow_id: str):
    db.update_workflow_status(workflow_id, "deployed")
    agents = db.fetch_agents()
    agent = next((a for a in agents if a["workflow_id"] == workflow_id), None)
    if agent:
        db.update_agent_status(agent["agent_id"], "deployed")


def _reject(wf: dict):
    db.update_workflow_status(wf["workflow_id"], "rejected")
    definition = _definition(wf)
    db.add_rejected_fingerprint(task_fingerprint(definition), wf.get("task_name", ""))


def _render_edit_form(wf: dict, definition: dict):
    with st.form(f"edit_{wf['workflow_id']}"):
        st.subheader("Edit task")
        new_name = st.text_input("Task name", value=wf.get("task_name", ""))

        steps = definition.get("steps", [])
        approval_flags = {}
        st.markdown("**Require approval per step:**")
        for step in steps:
            n = step.get("step_number")
            approval_flags[n] = st.checkbox(
                f"Step {n}: {step.get('description', '')}",
                value=bool(step.get("requires_approval")),
                key=f"appr_{wf['workflow_id']}_{n}",
            )

        trigger_type = st.selectbox(
            "Trigger type", ["manual", "scheduled", "event"],
            key=f"trig_{wf['workflow_id']}",
        )
        schedule = ""
        if trigger_type == "scheduled":
            schedule = st.text_input(
                "Schedule (cron or natural language)",
                value="0 15 * * 5",
                help="e.g. '0 15 * * 5' or 'every Friday at 3pm'",
            )

        submitted = st.form_submit_button("Save edits")
        if submitted:
            for step in steps:
                step["requires_approval"] = approval_flags.get(step.get("step_number"),
                                                               step.get("requires_approval"))
            edits = {
                "task_name": new_name,
                "trigger_type": trigger_type,
                "schedule": schedule,
                "steps": steps,
            }
            db.update_workflow_edits(wf["workflow_id"], json.dumps(edits))
            st.success("Edits saved.")
            st.rerun()


def render():
    st.header("Discovered Tasks")
    st.write("Tasks Teleo found by observing your work. Review and deploy.")

    workflows = db.fetch_workflows(status="detected")
    if not workflows:
        st.info("No discovered tasks yet. Run the pipeline or seed demo data.")
        return

    for wf in workflows:
        definition = _definition(wf)
        confidence = wf.get("automation_confidence") or 0
        minutes = wf.get("estimated_minutes_per_run") or 0
        occ = wf.get("occurrence_count") or 0

        with st.container(border=True):
            top = st.columns([3, 1, 1, 1])
            top[0].subheader(wf.get("task_name", "Untitled"))
            top[1].metric("Confidence", f"{confidence:.0%}")
            top[2].metric("Mins/run", minutes)
            top[3].metric("Seen", f"{occ}x")

            st.write(wf.get("description", ""))
            st.caption(f"Frequency: {wf.get('frequency', '?')} · "
                       f"Trigger: {definition.get('trigger_condition', '?')}")

            with st.expander("Steps & evidence"):
                for step in definition.get("steps", []):
                    flag = " (needs approval)" if step.get("requires_approval") else ""
                    st.markdown(
                        f"**{step.get('step_number')}. {step.get('target_app')}** "
                        f"— {step.get('description')}{flag}"
                    )
                occ_list = definition.get("occurrences", [])
                if occ_list:
                    st.caption("Observed on: " + ", ".join(map(str, occ_list)))

            cols = st.columns(3)
            if cols[0].button("Deploy Agent", key=f"deploy_{wf['workflow_id']}",
                              type="primary"):
                _deploy(wf["workflow_id"])
                st.success(f"Deployed: {wf.get('task_name')}")
                st.rerun()
            if cols[1].button("Edit First", key=f"editbtn_{wf['workflow_id']}"):
                st.session_state[f"editing_{wf['workflow_id']}"] = True
            if cols[2].button("Not a Real Task", key=f"reject_{wf['workflow_id']}"):
                _reject(wf)
                st.rerun()

            if st.session_state.get(f"editing_{wf['workflow_id']}"):
                _render_edit_form(wf, definition)
