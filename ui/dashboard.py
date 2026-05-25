"""Dashboard tab: headline metrics and charts on agent activity."""
from collections import Counter
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd

from storage import db


def _parse(ts: str):
    try:
        return datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return None


def render():
    st.header("Dashboard")

    runs = db.fetch_runs(limit=1000)
    agents = db.fetch_agents()
    active_agents = [a for a in agents if a["status"] == "deployed"]

    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    def saved_since(cutoff):
        total = 0
        for r in runs:
            ts = _parse(r.get("started_at"))
            if ts and ts >= cutoff and r["status"] == "success":
                total += r.get("minutes_saved") or 0
        return total

    lifetime = sum(r.get("minutes_saved") or 0 for r in runs if r["status"] == "success")

    c = st.columns(4)
    c[0].metric("Hours saved (week)", f"{saved_since(week_ago) / 60:.1f}")
    c[1].metric("Hours saved (month)", f"{saved_since(month_ago) / 60:.1f}")
    c[2].metric("Hours saved (lifetime)", f"{lifetime / 60:.1f}")
    c[3].metric("Active agents", len(active_agents))

    c2 = st.columns(3)
    today = now.date()
    tasks_today = sum(
        1 for r in runs
        if r["status"] == "success" and _parse(r.get("started_at"))
        and _parse(r["started_at"]).date() == today
    )
    tasks_week = sum(
        1 for r in runs
        if r["status"] == "success" and _parse(r.get("started_at"))
        and _parse(r["started_at"]) >= week_ago
    )
    finished = [r for r in runs if r["status"] in ("success", "failed", "rejected")]
    rate = (sum(1 for r in finished if r["status"] == "success") / len(finished)
            if finished else 0)
    c2[0].metric("Tasks completed today", tasks_today)
    c2[1].metric("Tasks completed this week", tasks_week)
    c2[2].metric("Overall success rate", f"{rate:.0%}")

    st.divider()

    if not runs:
        st.info("No agent runs yet. Run an agent to populate the dashboard.")
        return

    # Hours saved over time.
    by_day = {}
    for r in runs:
        if r["status"] != "success":
            continue
        ts = _parse(r.get("started_at"))
        if not ts:
            continue
        day = ts.date().isoformat()
        by_day[day] = by_day.get(day, 0) + (r.get("minutes_saved") or 0) / 60
    if by_day:
        st.subheader("Hours saved over time")
        df = pd.DataFrame(
            sorted(by_day.items()), columns=["date", "hours"]
        ).set_index("date")
        st.line_chart(df)

    # Time saved by agent.
    name_by_id = {a["agent_id"]: a["name"] for a in agents}
    by_agent = {}
    for r in runs:
        if r["status"] != "success":
            continue
        name = name_by_id.get(r["agent_id"], r["agent_id"][:8])
        by_agent[name] = by_agent.get(name, 0) + (r.get("minutes_saved") or 0)
    if by_agent:
        st.subheader("Minutes saved by agent")
        st.bar_chart(pd.DataFrame(
            by_agent.items(), columns=["agent", "minutes"]
        ).set_index("agent"))

    # Run status breakdown.
    status_counts = Counter(r["status"] for r in runs)
    st.subheader("Run status breakdown")
    st.bar_chart(pd.DataFrame(
        status_counts.items(), columns=["status", "count"]
    ).set_index("status"))
