import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from storage.db import init_db
from ui import discovered_tasks, deployed_agents, activity_log, dashboard, demo_controls

st.set_page_config(
    page_title="Teleo",
    page_icon="\U0001F916",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
    .stApp { background-color: #0a0e27; color: white; }
    .stTabs [data-baseweb="tab-list"] { background-color: #1a1f3a; }
    h1, h2, h3 { color: #4a9eff; }
    div[data-testid="stMetricValue"] { color: #4a9eff; }
    .teleo-card {
        background-color: #141a35; border: 1px solid #2a3358;
        border-radius: 10px; padding: 18px; margin-bottom: 14px;
    }
</style>
""",
    unsafe_allow_html=True,
)

init_db()

st.title("Teleo")
st.caption("Self-Teaching Artificial Employees")

# Hidden demo control panel, reachable at ?demo=true
if st.query_params.get("demo") == "true":
    demo_controls.render()
    st.divider()

tab1, tab2, tab3, tab4 = st.tabs([
    "\U0001F50D Discovered Tasks",
    "\U0001F916 Deployed Agents",
    "\U0001F4CA Activity Log",
    "\U0001F4C8 Dashboard",
])

with tab1:
    discovered_tasks.render()
with tab2:
    deployed_agents.render()
with tab3:
    activity_log.render()
with tab4:
    dashboard.render()
