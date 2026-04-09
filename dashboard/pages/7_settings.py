# dashboard/pages/7_settings.py

import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from dashboard.components.tech_style import apply_tech_style

apply_tech_style()
require_login()

st.markdown(
    """
<div class="page-header">
    <h1 class="page-title">&gt; Settings</h1>
    <p class="page-subtitle">System configuration and preferences</p>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="card">
    <div class="card-header">
        <span class="card-title">// System_Info</span>
    </div>
    <div class="code-block">
Version: 2.0.0
Environment: Production
Python: 3.9+
Framework: Streamlit
    </div>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown('<hr class="divider">', unsafe_allow_html=True)

st.markdown(
    """
<div class="card">
    <div class="card-header">
        <span class="card-title">// Environment_Variables</span>
    </div>
""",
    unsafe_allow_html=True,
)

env_vars = [
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "QDRANT_HOST",
    "QDRANT_PORT",
    "SESSION_DB_PATH",
    "LANCEDB_PATH",
]

for var in env_vars:
    value = os.getenv(var, "not set")
    display = (
        value[:8] + "..." if value and value != "not set" and len(value) > 8 else value
    )
    st.markdown(
        f"""
    <p style="font-family: 'JetBrains Mono', monospace; font-size: 13px; color: var(--text-secondary);">
        <span style="color: var(--accent-cyan);">{var}</span>: {display}
    </p>
    """,
        unsafe_allow_html=True,
    )

st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<hr class="divider">', unsafe_allow_html=True)

st.markdown(
    """
<div class="card">
    <div class="card-header">
        <span class="card-title">// Theme_Settings</span>
    </div>
""",
    unsafe_allow_html=True,
)

col1, col2 = st.columns(2)
with col1:
    st.selectbox("Color_Accent", ["Cyan", "Green", "Purple", "Orange"])
with col2:
    st.selectbox("Font_Style", ["JetBrains Mono", "IBM Plex Sans", "Fira Code"])

st.markdown("</div>", unsafe_allow_html=True)
