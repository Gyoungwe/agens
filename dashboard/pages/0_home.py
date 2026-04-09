# dashboard/pages/0_home.py

import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from dashboard.components.tech_style import apply_tech_style

apply_tech_style()
require_login()

st.markdown(
    """
<div class="page-header">
    <h1 class="page-title">&gt; System_Overview</h1>
    <p class="page-subtitle">Multi-Agent Orchestration Platform v2.0</p>
</div>
""",
    unsafe_allow_html=True,
)

try:
    from core.skill_registry import SkillRegistry
    from evolution.approval_queue import ApprovalQueue
    from session.session_store import SessionStore
    from providers.provider_registry import ProviderRegistry

    registry = SkillRegistry()
    queue = ApprovalQueue()
    store = SessionStore()
    pr = ProviderRegistry()

    skills = registry.list_all()
    pending = queue.pending_count()
    sessions = store.list_sessions(status="active")
    providers = pr.list_all()
    active = pr.get()

    st.markdown('<div class="metric-grid">', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            f"""
        <div class="metric-card">
            <div class="metric-value">{len(skills)}</div>
            <div class="metric-label">Installed Skills</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    with col2:
        enabled = sum(1 for s in skills if s["enabled"])
        st.markdown(
            f"""
        <div class="metric-card">
            <div class="metric-value">{enabled}</div>
            <div class="metric-label">Active Skills</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            f"""
        <div class="metric-card">
            <div class="metric-value">{pending}</div>
            <div class="metric-label">Pending Approvals</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    with col4:
        st.markdown(
            f"""
        <div class="metric-card">
            <div class="metric-value">{len(sessions)}</div>
            <div class="metric-label">Active Sessions</div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)

    col_a, col_b = st.columns([1, 1])

    with col_a:
        st.markdown(
            """
        <div class="card">
            <div class="card-header">
                <span class="card-title">// Current_Model</span>
                <span class="status-badge status-online">Online</span>
            </div>
        """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
        <div class="code-block">
Provider: {pr.active_id}
Model: {getattr(active, "model", "unknown")}
Type: {active.provider_id}
        </div>
        """,
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with col_b:
        st.markdown(
            """
        <div class="card">
            <div class="card-header">
                <span class="card-title">// System_Status</span>
            </div>
        """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
        <div style="color: var(--text-secondary); font-family: 'JetBrains Mono', monospace; font-size: 13px;">
            <p><span style="color: var(--accent-green);">●</span> Registered Models: {len(providers)}</p>
            <p><span style="color: var(--accent-cyan);">●</span> Total Sessions: {len(store.list_sessions())}</p>
            <p><span style="color: #FBBF24;">●</span> Pending Approvals: {pending}</p>
        </div>
        """,
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    st.markdown(
        """
    <div class="card">
        <div class="card-header">
            <span class="card-title">// Quick_Actions</span>
        </div>
    """,
        unsafe_allow_html=True,
    )

    col_x, col_y, col_z = st.columns(3)
    with col_x:
        if st.button("💬 New_Chat", use_container_width=True):
            st.switch_page("pages/6_chat.py")
    with col_y:
        if st.button("📊 Task_Monitor", use_container_width=True):
            st.switch_page("pages/8_monitor.py")
    with col_z:
        if st.button("⚙️ Settings", use_container_width=True):
            st.switch_page("pages/7_settings.py")

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        """
    <div class="card">
        <div class="card-header">
            <span class="card-title">// Registered_Agents</span>
            <span class="status-badge status-running">Active</span>
        </div>
    """,
        unsafe_allow_html=True,
    )

    agents = [
        ("🤖", "Orchestrator", "Task planning & dispatch", "running"),
        ("🔍", "Research Agent", "Web search & analysis", "online"),
        ("⚡", "Executor Agent", "Code execution & tools", "online"),
        ("✍️", "Writer Agent", "Content generation", "online"),
    ]

    for icon, name, desc, status in agents:
        st.markdown(
            f"""
        <div class="agent-card">
            <div class="agent-icon">{icon}</div>
            <div class="agent-info">
                <div class="agent-name">{name}</div>
                <div class="agent-meta">{desc}</div>
            </div>
            <span class="status-badge status-{status}">{status.upper()}</span>
        </div>
        """,
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"Load failed: {e}")
    import traceback

    st.code(traceback.format_exc(), language="python")
