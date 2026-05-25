"""Activity Log tab: recent captured events with redaction indicators."""
import json

import streamlit as st
import pandas as pd

from storage import db


def render():
    st.header("Activity Log")
    st.caption("Recent structured events captured from your desktop.")

    events = db.fetch_recent_events(limit=200)
    if not events:
        st.info("No events captured yet.")
        return

    processes = sorted({e["process_name"] for e in events if e.get("process_name")})
    selected = st.selectbox("Filter by application", ["All"] + processes)
    if selected != "All":
        events = [e for e in events if e["process_name"] == selected]

    events = events[:100]
    rows = []
    for e in events:
        flags = ""
        if e.get("redacted"):
            try:
                pii = json.loads(e.get("pii_flags") or "[]")
            except json.JSONDecodeError:
                pii = []
            flags = "🔒 " + (", ".join(pii) if pii else "redacted")
        rows.append({
            "Time": (e.get("ts_utc") or "")[:19],
            "App": e.get("process_name"),
            "Action": e.get("semantic_label") or e.get("control_label") or e.get("event_type"),
            "Redaction": flags,
        })

    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    if st.toggle("Auto-refresh (5s)", value=False):
        st.markdown("<meta http-equiv='refresh' content='5'>", unsafe_allow_html=True)
