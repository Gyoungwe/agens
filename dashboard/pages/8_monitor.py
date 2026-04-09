# dashboard/pages/8_monitor.py

import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import time
import streamlit as st
from dashboard.components.tech_style import apply_tech_style

apply_tech_style()
require_login()

st.markdown(
    """
<div class="page-header">
    <h1 class="page-title">&gt; Task_Monitor</h1>
    <p class="page-subtitle">Real-time agent and task visualization</p>
</div>
""",
    unsafe_allow_html=True,
)

if "monitor_refresh" not in st.session_state:
    st.session_state["monitor_refresh"] = True
if "refresh_interval" not in st.session_state:
    st.session_state["refresh_interval"] = 2

col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    st.toggle(
        "Auto_Refresh", value=st.session_state["monitor_refresh"], key="monitor_refresh"
    )

with col2:
    st.session_state["refresh_interval"] = st.slider(
        "Interval(s)", 1, 10, 2, key="refresh_interval_slider"
    )

with col3:
    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()

st.markdown('<hr class="divider">', unsafe_allow_html=True)

try:
    from bus.message_bus import MessageBus
    from core.skill_registry import SkillRegistry
    from session.session_store import SessionStore

    bus = MessageBus()
    registry = SkillRegistry()
    store = SessionStore()

    registered_agents = bus.registered_agents
    skills = registry.list_all()
    sessions = store.list_sessions(status="active")

    st.markdown('<div class="metric-grid">', unsafe_allow_html=True)

    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        st.markdown(
            f"""
        <div class="metric-card">
            <div class="metric-value">{len(registered_agents)}</div>
            <div class="metric-label">Registered Agents</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    with col_b:
        active_count = len([a for a in registered_agents if a != "orchestrator"])
        st.markdown(
            f"""
        <div class="metric-card">
            <div class="metric-value">{active_count}</div>
            <div class="metric-label">Active Agents</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    with col_c:
        st.markdown(
            f"""
        <div class="metric-card">
            <div class="metric-value">{len(skills)}</div>
            <div class="metric-label">Installed Skills</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    with col_d:
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

    st.markdown(
        """
    <div class="card">
        <div class="card-header">
            <span class="card-title">// Agent_Status</span>
            <span class="status-badge status-running">Live</span>
        </div>
    """,
        unsafe_allow_html=True,
    )

    agent_status = {
        "orchestrator": {
            "icon": "🎯",
            "status": "running",
            "skills": "task planning",
        },
        "research_agent": {
            "icon": "🔍",
            "status": "online",
            "skills": "web_search, summarize",
        },
        "executor_agent": {
            "icon": "⚡",
            "status": "online",
            "skills": "shell, github",
        },
        "writer_agent": {
            "icon": "✍️",
            "status": "online",
            "skills": "format, translate",
        },
    }

    for agent_id in registered_agents:
        if agent_id not in agent_status:
            agent_status[agent_id] = {
                "icon": "🤖",
                "status": "online",
                "skills": "-",
            }

    cols = st.columns(min(len(registered_agents), 4))
    for i, agent_id in enumerate(registered_agents):
        with cols[i % 4]:
            info = agent_status.get(
                agent_id, {"icon": "🤖", "status": "online", "skills": "-"}
            )
            st.markdown(
                f"""
            <div class="agent-card">
                <div class="agent-icon">{info["icon"]}</div>
                <div class="agent-info">
                    <div class="agent-name">{agent_id}</div>
                    <div class="agent-meta">Skills: {info["skills"]}</div>
                </div>
                <span class="status-badge status-{info["status"]}">{info["status"].upper()}</span>
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
            <span class="card-title">// Recent_Tasks</span>
        </div>
    """,
        unsafe_allow_html=True,
    )

    recent_sessions = store.list_sessions()[:5]
    if recent_sessions:
        for session in recent_sessions:
            results = store.get_results(session["session_id"])
            with st.expander(
                f"Session {session['session_id'][:8]}... | {session.get('title', 'No title')[:30]} | {session['updated_at'][:16]}"
            ):
                if results:
                    for r in results[-3:]:
                        status_icon = "✅" if r.get("status") == "success" else "❌"
                        st.write(
                            f"{status_icon} [{r.get('agent_id', 'unknown')}] {r.get('created_at', '')[:16]}"
                        )
                        st.code(
                            r.get("result", "")[:200]
                            if r.get("result")
                            else "No result",
                            language="text",
                        )
                else:
                    st.info("No task results yet")
    else:
        st.info("No task records yet")

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    st.markdown(
        """
    <div class="card">
        <div class="card-header">
            <span class="card-title">// Message_Bus_Status</span>
        </div>
    """,
        unsafe_allow_html=True,
    )

    col_x, col_y = st.columns(2)
    with col_x:
        st.markdown(
            """
        <div style="color: var(--text-secondary);">
            <p style="font-family: 'JetBrains Mono', monospace; font-size: 13px;">
                <span style="color: var(--accent-cyan);">//</span> Registered Agents:
            </p>
        """,
            unsafe_allow_html=True,
        )
        for a in registered_agents:
            queue_size = bus.queue_size(a)
            st.markdown(
                f"<p><span class='status-dot online'></span>{a} (pending: {queue_size})</p>",
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with col_y:
        history_count = len(bus.get_history())
        st.markdown(
            f"""
        <div class="metric-card" style="text-align: center;">
            <div class="metric-value">{history_count}</div>
            <div class="metric-label">Total Message History</div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"Load failed: {e}")
    import traceback

    st.code(traceback.format_exc(), language="python")

if st.session_state["monitor_refresh"]:
    time.sleep(st.session_state["refresh_interval"])
    st.rerun()
