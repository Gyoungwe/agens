# dashboard/pages/3_logs.py

import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from dashboard.components.tech_style import apply_tech_style

apply_tech_style()
require_login()

st.markdown(
    """
<div class="page-header">
    <h1 class="page-title">&gt; System_Logs</h1>
    <p class="page-subtitle">View and search system logs</p>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="card">
    <div class="card-header">
        <span class="card-title">// Recent_Logs</span>
        <span class="status-badge status-running">Live</span>
    </div>
""",
    unsafe_allow_html=True,
)

log_levels = ["ALL", "INFO", "WARNING", "ERROR"]
selected_level = st.selectbox("Log_Level", log_levels)

st.code(
    """[2024-01-01 12:00:00] INFO: System initialized
[2024-01-01 12:00:01] INFO: ProviderRegistry loaded
[2024-01-01 12:00:02] INFO: SkillRegistry initialized
[2024-01-01 12:00:03] INFO: MessageBus ready
[2024-01-01 12:00:04] INFO: Orchestrator started""",
    language="text",
)

st.markdown("</div>", unsafe_allow_html=True)
