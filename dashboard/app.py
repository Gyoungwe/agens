#!/usr/bin/env python3
# dashboard/app.py
# Multi-Agent Dashboard - Standalone Application
# Features: Day/Night mode, Real-time Agent Monitoring, Step Results

import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import time
import asyncio
import uuid
import requests
from datetime import datetime

API_BASE = "http://localhost:18792"

st.set_page_config(
    page_title="Multi-Agent Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════════════════════════════════════
# Theme Management
# ══════════════════════════════════════════════════════════════════════════════

THEME_CSS_DARK = """
* { font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
.stApp { background: #0d1117; color: #e6edf3; min-height: 100vh; }
[data-testid="stSidebar"] { background: #161b22; border-right: 1px solid #30363d; width: 240px; }
.sidebar-header { padding: 16px; border-bottom: 1px solid #30363d; display: flex; align-items: center; justify-content: space-between; }
.sidebar-logo { font-size: 16px; font-weight: 700; color: #e6edf3; font-family: 'JetBrains Mono', monospace; }
.sidebar-logo span { color: #58a6ff; }
.nav-section { padding: 12px 8px; }
.nav-section-title { font-size: 11px; font-weight: 600; color: #6e7681; text-transform: uppercase; letter-spacing: 0.5px; padding: 8px 12px 4px; }
.nav-item { display: flex; align-items: center; padding: 8px 12px; margin: 2px 4px; border-radius: 6px; color: #8b949e; font-size: 13px; font-weight: 500; cursor: pointer; transition: all 0.15s ease; }
.nav-item:hover { background: #21262d; color: #e6edf3; }
.nav-item.active { background: #58a6ff15; color: #58a6ff; }
.nav-item-icon { width: 18px; margin-right: 10px; font-size: 14px; }
.main-content { padding: 24px; max-width: 1400px; }
.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
.card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid #30363d; }
.card-title { font-size: 14px; font-weight: 600; color: #e6edf3; font-family: 'JetBrains Mono', monospace; }
.metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 20px; }
.metric-card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; transition: all 0.2s ease; }
.metric-card:hover { border-color: #58a6ff; box-shadow: 0 2px 8px rgba(0,0,0,0.4); }
.metric-value { font-size: 28px; font-weight: 700; color: #58a6ff; font-family: 'JetBrains Mono', monospace; }
.metric-label { font-size: 12px; color: #6e7681; margin-top: 4px; font-weight: 500; }
.status-badge { display: inline-flex; align-items: center; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }
.status-running { background: #58a6ff20; color: #58a6ff; }
.status-success, .status-online { background: #3fb95020; color: #3fb950; }
.status-pending { background: #d2992220; color: #d29922; }
.status-error { background: #f8514920; color: #f85149; }
.agent-card { background: #21262d; border: 1px solid #30363d; border-radius: 8px; padding: 12px 16px; display: flex; align-items: center; gap: 12px; transition: all 0.2s ease; }
.agent-card:hover { border-color: #58a6ff; }
.agent-card.active { border-color: #58a6ff; background: #58a6ff10; }
.agent-icon { width: 36px; height: 36px; border-radius: 8px; background: #58a6ff20; display: flex; align-items: center; justify-content: center; font-size: 16px; }
.agent-info { flex: 1; }
.agent-name { font-size: 13px; font-weight: 600; color: #e6edf3; font-family: 'JetBrains Mono', monospace; }
.agent-status { font-size: 11px; color: #6e7681; margin-top: 2px; }
.step-tracker { display: flex; flex-direction: column; gap: 0; }
.step-item { display: flex; gap: 12px; padding: 12px 0; position: relative; }
.step-item:not(:last-child)::before { content: ''; position: absolute; left: 15px; top: 44px; bottom: 0; width: 2px; background: #30363d; }
.step-item.completed:not(:last-child)::before { background: #3fb950; }
.step-icon { width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 14px; flex-shrink: 0; z-index: 1; }
.step-icon.pending { background: #21262d; border: 2px solid #30363d; }
.step-icon.running { background: #58a6ff; color: white; animation: pulse 1.5s infinite; }
.step-icon.completed { background: #3fb950; color: white; }
.step-icon.error { background: #f85149; color: white; }
.step-content { flex: 1; padding-bottom: 12px; }
.step-title { font-size: 13px; font-weight: 600; color: #e6edf3; }
.step-description { font-size: 12px; color: #6e7681; margin-top: 2px; }
.step-result { margin-top: 8px; padding: 10px 12px; background: #0d1117; border: 1px solid #30363d; border-radius: 6px; font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #8b949e; max-height: 200px; overflow-y: auto; white-space: pre-wrap; }
.code-block { background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 12px; font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #3fb950; overflow-x: auto; }
.chat-container { display: flex; flex-direction: column; gap: 16px; height: 400px; overflow-y: auto; padding: 16px; background: #0d1117; border: 1px solid #30363d; border-radius: 8px; }
.chat-message { max-width: 80%; padding: 12px 16px; border-radius: 12px; font-size: 13px; line-height: 1.5; }
.chat-message.user { align-self: flex-end; background: #58a6ff; color: white; border-bottom-right-radius: 4px; }
.chat-message.assistant { align-self: flex-start; background: #21262d; color: #e6edf3; border-bottom-left-radius: 4px; }
.stTextInput > div > div > input, .stTextArea > div > div > textarea { background: #21262d; border: 1px solid #30363d; border-radius: 6px; color: #e6edf3; font-size: 13px; }
.stTextInput > div > div > input:focus, .stTextArea > div > div > textarea:focus { border-color: #58a6ff; box-shadow: 0 0 0 2px #58a6ff20; }
.stSelectbox > div > div { background: #21262d; border: 1px solid #30363d; border-radius: 6px; }
.stButton > button { border-radius: 6px; font-weight: 500; font-size: 13px; border: 1px solid #30363d; background: #21262d; color: #e6edf3; transition: all 0.15s ease; }
.stButton > button:hover { border-color: #58a6ff; color: #58a6ff; }
.stTabs [data-baseweb="tab-list"] { gap: 8px; border-bottom: 1px solid #30363d; }
.stTabs [data-baseweb="tab"] { background: transparent; color: #8b949e; border: none; border-bottom: 2px solid transparent; padding: 8px 16px; font-weight: 500; font-size: 13px; }
.stTabs [data-baseweb="tab"]:hover { color: #e6edf3; }
.stTabs [data-baseweb="tab"][aria-selected="true"] { color: #58a6ff; border-bottom-color: #58a6ff; }
hr { border: none; height: 1px; background: #30363d; margin: 20px 0; }
.streamlit-expander { background: #161b22; border: 1px solid #30363d; border-radius: 8px; }
.stProgress > div > div > div { background: #58a6ff; }
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #30363d; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #6e7681; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }
"""

THEME_CSS_LIGHT = """
* { font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
.stApp { background: #ffffff; color: #1f2328; min-height: 100vh; }
[data-testid="stSidebar"] { background: #f6f8fa; border-right: 1px solid #d0d7de; width: 240px; }
.sidebar-header { padding: 16px; border-bottom: 1px solid #d0d7de; display: flex; align-items: center; justify-content: space-between; }
.sidebar-logo { font-size: 16px; font-weight: 700; color: #1f2328; font-family: 'JetBrains Mono', monospace; }
.sidebar-logo span { color: #0969da; }
.nav-section { padding: 12px 8px; }
.nav-section-title { font-size: 11px; font-weight: 600; color: #656d76; text-transform: uppercase; letter-spacing: 0.5px; padding: 8px 12px 4px; }
.nav-item { display: flex; align-items: center; padding: 8px 12px; margin: 2px 4px; border-radius: 6px; color: #656d76; font-size: 13px; font-weight: 500; cursor: pointer; transition: all 0.15s ease; }
.nav-item:hover { background: #eaeef2; color: #1f2328; }
.nav-item.active { background: #0969da15; color: #0969da; }
.nav-item-icon { width: 18px; margin-right: 10px; font-size: 14px; }
.main-content { padding: 24px; max-width: 1400px; }
.card { background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
.card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid #d0d7de; }
.card-title { font-size: 14px; font-weight: 600; color: #1f2328; font-family: 'JetBrains Mono', monospace; }
.metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 20px; }
.metric-card { background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 8px; padding: 16px; transition: all 0.2s ease; }
.metric-card:hover { border-color: #0969da; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
.metric-value { font-size: 28px; font-weight: 700; color: #0969da; font-family: 'JetBrains Mono', monospace; }
.metric-label { font-size: 12px; color: #656d76; margin-top: 4px; font-weight: 500; }
.status-badge { display: inline-flex; align-items: center; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }
.status-running { background: #0969da20; color: #0969da; }
.status-success, .status-online { background: #1a7f3720; color: #1a7f37; }
.status-pending { background: #9a670020; color: #9a6700; }
.status-error { background: #cf222e20; color: #cf222e; }
.agent-card { background: #eaeef2; border: 1px solid #d0d7de; border-radius: 8px; padding: 12px 16px; display: flex; align-items: center; gap: 12px; transition: all 0.2s ease; }
.agent-card:hover { border-color: #0969da; }
.agent-card.active { border-color: #0969da; background: #0969da10; }
.agent-icon { width: 36px; height: 36px; border-radius: 8px; background: #0969da20; display: flex; align-items: center; justify-content: center; font-size: 16px; }
.agent-info { flex: 1; }
.agent-name { font-size: 13px; font-weight: 600; color: #1f2328; font-family: 'JetBrains Mono', monospace; }
.agent-status { font-size: 11px; color: #656d76; margin-top: 2px; }
.step-tracker { display: flex; flex-direction: column; gap: 0; }
.step-item { display: flex; gap: 12px; padding: 12px 0; position: relative; }
.step-item:not(:last-child)::before { content: ''; position: absolute; left: 15px; top: 44px; bottom: 0; width: 2px; background: #d0d7de; }
.step-item.completed:not(:last-child)::before { background: #1a7f37; }
.step-icon { width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 14px; flex-shrink: 0; z-index: 1; }
.step-icon.pending { background: #eaeef2; border: 2px solid #d0d7de; }
.step-icon.running { background: #0969da; color: white; animation: pulse 1.5s infinite; }
.step-icon.completed { background: #1a7f37; color: white; }
.step-icon.error { background: #cf222e; color: white; }
.step-content { flex: 1; padding-bottom: 12px; }
.step-title { font-size: 13px; font-weight: 600; color: #1f2328; }
.step-description { font-size: 12px; color: #656d76; margin-top: 2px; }
.step-result { margin-top: 8px; padding: 10px 12px; background: #ffffff; border: 1px solid #d0d7de; border-radius: 6px; font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #656d76; max-height: 200px; overflow-y: auto; white-space: pre-wrap; }
.code-block { background: #ffffff; border: 1px solid #d0d7de; border-radius: 6px; padding: 12px; font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #1a7f37; overflow-x: auto; }
.chat-container { display: flex; flex-direction: column; gap: 16px; height: 400px; overflow-y: auto; padding: 16px; background: #ffffff; border: 1px solid #d0d7de; border-radius: 8px; }
.chat-message { max-width: 80%; padding: 12px 16px; border-radius: 12px; font-size: 13px; line-height: 1.5; }
.chat-message.user { align-self: flex-end; background: #0969da; color: white; border-bottom-right-radius: 4px; }
.chat-message.assistant { align-self: flex-start; background: #eaeef2; color: #1f2328; border-bottom-left-radius: 4px; }
.stTextInput > div > div > input, .stTextArea > div > div > textarea { background: #eaeef2; border: 1px solid #d0d7de; border-radius: 6px; color: #1f2328; font-size: 13px; }
.stTextInput > div > div > input:focus, .stTextArea > div > div > textarea:focus { border-color: #0969da; box-shadow: 0 0 0 2px #0969da20; }
.stSelectbox > div > div { background: #eaeef2; border: 1px solid #d0d7de; border-radius: 6px; }
.stButton > button { border-radius: 6px; font-weight: 500; font-size: 13px; border: 1px solid #d0d7de; background: #f6f8fa; color: #1f2328; transition: all 0.15s ease; }
.stButton > button:hover { border-color: #0969da; color: #0969da; }
.stTabs [data-baseweb="tab-list"] { gap: 8px; border-bottom: 1px solid #d0d7de; }
.stTabs [data-baseweb="tab"] { background: transparent; color: #656d76; border: none; border-bottom: 2px solid transparent; padding: 8px 16px; font-weight: 500; font-size: 13px; }
.stTabs [data-baseweb="tab"]:hover { color: #1f2328; }
.stTabs [data-baseweb="tab"][aria-selected="true"] { color: #0969da; border-bottom-color: #0969da; }
hr { border: none; height: 1px; background: #d0d7de; margin: 20px 0; }
.streamlit-expander { background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 8px; }
.stProgress > div > div > div { background: #0969da; }
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: #ffffff; }
::-webkit-scrollbar-thumb { background: #d0d7de; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #656d76; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }
"""


def init_session_state():
    if "theme" not in st.session_state:
        st.session_state.theme = "dark"
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "task_steps" not in st.session_state:
        st.session_state.task_steps = []
    if "current_task_id" not in st.session_state:
        st.session_state.current_task_id = None
    if "agent_states" not in st.session_state:
        st.session_state.agent_states = {
            "orchestrator": {
                "status": "running",
                "current_task": "Waiting for task...",
                "last_update": time.time(),
            },
            "research_agent": {
                "status": "online",
                "current_task": "Idle",
                "last_update": time.time(),
            },
            "executor_agent": {
                "status": "online",
                "current_task": "Idle",
                "last_update": time.time(),
            },
            "writer_agent": {
                "status": "online",
                "current_task": "Idle",
                "last_update": time.time(),
            },
        }


def render_theme_toggle():
    col1, col2 = st.columns([1, 1])
    with col1:
        is_dark = st.session_state.theme == "dark"
        new_theme = "light" if is_dark else "dark"
        if st.button(
            f"{'☀️' if is_dark else '🌙'} {'Light Mode' if is_dark else 'Dark Mode'}",
            use_container_width=True,
        ):
            st.session_state.theme = new_theme
            st.rerun()
    st.markdown(
        THEME_CSS_DARK if st.session_state.theme == "dark" else THEME_CSS_LIGHT,
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Sidebar Navigation
# ══════════════════════════════════════════════════════════════════════════════


def render_sidebar():
    with st.sidebar:
        st.markdown('<div class="sidebar-header">', unsafe_allow_html=True)
        st.markdown(
            '<div class="sidebar-logo"><span>&gt;</span> Multi-Agent</div>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="nav-section">', unsafe_allow_html=True)
        st.markdown(
            '<div class="nav-section-title">Dashboard</div>', unsafe_allow_html=True
        )

        pages = [
            ("🏠", "Overview", "overview"),
            ("🤖", "Agent Monitor", "monitor"),
            ("📊", "Task Results", "results"),
            ("💬", "Chat", "chat"),
        ]

        if "current_page" not in st.session_state:
            st.session_state.current_page = "overview"

        for icon, name, page_id in pages:
            is_active = st.session_state.current_page == page_id
            if st.button(
                f"{icon} {name}", use_container_width=True, key=f"nav_{page_id}"
            ):
                st.session_state.current_page = page_id
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<hr style="margin: 16px 0;">', unsafe_allow_html=True)

        st.markdown('<div class="nav-section">', unsafe_allow_html=True)
        st.markdown(
            '<div class="nav-section-title">Settings</div>', unsafe_allow_html=True
        )

        settings_pages = [
            ("🔌", "Providers", "providers"),
            ("🧩", "Skills", "skills"),
            ("⚙️", "Configuration", "config"),
        ]

        for icon, name, page_id in settings_pages:
            is_active = st.session_state.current_page == page_id
            if st.button(
                f"{icon} {name}", use_container_width=True, key=f"nav_{page_id}"
            ):
                st.session_state.current_page = page_id
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Page: Overview
# ══════════════════════════════════════════════════════════════════════════════


def _fetch_api(path, fallback=None):
    try:
        return requests.get(f"{API_BASE}{path}", timeout=5).json()
    except Exception:
        return fallback


def render_overview():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="card-header"><span class="card-title">// System_Overview</span></div>',
        unsafe_allow_html=True,
    )

    debug_status = _fetch_api("/debug/status", {})
    agents = debug_status.get("agents", [])
    providers = debug_status.get("providers", [])
    skills_count = len(_fetch_api("/skills", []))

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            f'<div class="metric-card"><div class="metric-value">{len(agents)}</div><div class="metric-label">Active Agents</div></div>',
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f'<div class="metric-card"><div class="metric-value">{skills_count}</div><div class="metric-label">Installed Skills</div></div>',
            unsafe_allow_html=True,
        )
    with col3:
        sessions = _fetch_api("/sessions", [])
        active_count = len([s for s in sessions if s.get("status") == "active"])
        st.markdown(
            f'<div class="metric-card"><div class="metric-value">{active_count}</div><div class="metric-label">Active Sessions</div></div>',
            unsafe_allow_html=True,
        )
    with col4:
        st.markdown(
            f'<div class="metric-card"><div class="metric-value">{len(providers)}</div><div class="metric-label">Providers</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="card-header"><span class="card-title">// Registered_Agents</span></div>',
        unsafe_allow_html=True,
    )

    for agent in agents:
        status = "running" if agent.get("running") else "offline"
        st.markdown(
            f"""
        <div class="agent-card">
            <div class="agent-icon">🤖</div>
            <div class="agent-info">
                <div class="agent-name">{agent.get("id", "unknown")}</div>
                <div class="agent-status">{agent.get("id", "unknown")}</div>
            </div>
            <span class="status-badge status-{status}">{status.upper()}</span>
        </div>
        """,
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Page: Agent Monitor (Real-time)
# ══════════════════════════════════════════════════════════════════════════════


def render_agent_monitor():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="card-header"><span class="card-title">// Agent_Monitor</span><span class="status-badge status-running">LIVE</span></div>',
        unsafe_allow_html=True,
    )

    if st.button("🔄 Refresh Status", use_container_width=True):
        st.rerun()

    agent_states = st.session_state.agent_states

    for agent_id, state in agent_states.items():
        status = state["status"]
        task = state["current_task"]
        icon = {
            "orchestrator": "🎯",
            "research_agent": "🔍",
            "executor_agent": "⚡",
            "writer_agent": "✍️",
        }.get(agent_id, "🤖")

        with st.expander(f"{icon} {agent_id} — {status.upper()}", expanded=True):
            st.markdown(f"**Status:** `{status}`")
            st.markdown(f"**Current Task:** {task}")
            st.markdown(
                f"**Last Update:** {datetime.fromtimestamp(state['last_update']).strftime('%H:%M:%S')}"
            )

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="card-header"><span class="card-title">// Quick_Actions</span></div>',
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🎯 New Task", use_container_width=True):
            st.session_state.current_page = "chat"
            st.rerun()
    with col2:
        if st.button("🔄 Reset All", use_container_width=True):
            for agent_id in st.session_state.agent_states:
                st.session_state.agent_states[agent_id] = {
                    "status": "online",
                    "current_task": "Idle",
                    "last_update": time.time(),
                }
            st.rerun()
    with col3:
        if st.button("📊 View Results", use_container_width=True):
            st.session_state.current_page = "results"
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Page: Task Results (Step-by-step view)
# ══════════════════════════════════════════════════════════════════════════════


def render_results():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="card-header"><span class="card-title">// Task_Execution_Results</span></div>',
        unsafe_allow_html=True,
    )

    if not st.session_state.task_steps:
        st.info(
            "No task results yet. Start a task from the Chat tab to see step-by-step results here."
        )
    else:
        for i, step in enumerate(st.session_state.task_steps):
            status_class = step.get("status", "pending")
            status_icon = {
                "pending": "⏳",
                "running": "🔄",
                "completed": "✅",
                "error": "❌",
            }.get(status_class, "⚪")

            st.markdown(
                f"""
            <div class="step-item {status_class}">
                <div class="step-icon {status_class}">{status_icon}</div>
                <div class="step-content">
                    <div class="step-title">{step.get("agent", "Unknown Agent")}</div>
                    <div class="step-description">{step.get("instruction", "No instruction")[:100]}...</div>
                    {f'<div class="step-result">{step.get("result", "")}</div>' if step.get("result") else ""}
                </div>
            </div>
            """,
                unsafe_allow_html=True,
            )

    st.markdown("</div>", unsafe_allow_html=True)

    if st.button("🗑️ Clear Results", use_container_width=True):
        st.session_state.task_steps = []
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# Page: Chat
# ══════════════════════════════════════════════════════════════════════════════


EVENT_ICONS = {
    "agent_start": "🚀",
    "agent_thinking": "🤔",
    "agent_tool_call": "🔧",
    "agent_file_read": "📂",
    "agent_output": "📤",
    "agent_done": "✅",
    "final_response": "🎉",
    "error": "❌",
}

EVENT_COLORS = {
    "agent_start": "#58a6ff",
    "agent_thinking": "#f0883e",
    "agent_tool_call": "#a371f7",
    "agent_file_read": "#3fb950",
    "agent_output": "#79c0ff",
    "agent_done": "#3fb950",
    "final_response": "#ffa657",
    "error": "#f85149",
}


def render_chat():
    if "task_events" not in st.session_state:
        st.session_state.task_events = []

    left_col, right_col = st.columns([3, 2])

    with left_col:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="card-header"><span class="card-title">// Task_Input</span></div>',
            unsafe_allow_html=True,
        )

        user_input = st.text_area(
            "Enter your task...",
            placeholder="e.g., Research the latest AI developments and write a summary",
            height=100,
            key="task_input",
        )

        col1, col2 = st.columns([1, 4])
        with col1:
            run_btn = st.button(
                "🚀 Execute Task", type="primary", use_container_width=True
            )

        st.markdown("</div>", unsafe_allow_html=True)

        if run_btn and user_input:
            st.session_state.task_events = []

            if "chat_session_id" not in st.session_state:
                try:
                    resp = requests.post(
                        f"{API_BASE}/sessions",
                        json={"title": "Dashboard Chat"},
                        timeout=10,
                    )
                    if resp.status_code == 200:
                        st.session_state.chat_session_id = resp.json()["session_id"]
                    else:
                        st.error(f"创建 Session 失败: {resp.status_code}")
                        return
                except Exception as e:
                    st.error(f"Failed to create session: {e}")
                    return

            st.session_state.agent_states["orchestrator"]["status"] = "running"
            st.session_state.agent_states["orchestrator"]["current_task"] = (
                "Processing request"
            )
            st.session_state.agent_states["orchestrator"]["last_update"] = time.time()

            try:
                st.session_state.messages.append(
                    {
                        "role": "user",
                        "content": user_input,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

                import json

                with requests.post(
                    f"{API_BASE}/chat/stream",
                    json={
                        "message": user_input,
                        "session_id": st.session_state.chat_session_id,
                    },
                    stream=True,
                    timeout=180,
                ) as resp:
                    if resp.status_code != 200:
                        st.error(f"API error: {resp.status_code}")
                        return

                    events = []
                    for line in resp.iter_lines():
                        if line:
                            line = line.decode("utf-8")
                            if line.startswith("event:"):
                                current_event = line[6:].strip()
                            elif line.startswith("data:"):
                                data = line[5:].strip()
                                try:
                                    event_data = json.loads(data)
                                    event_data["_event_type"] = current_event
                                    events.append(event_data)
                                    st.session_state.task_events.append(event_data)
                                except:
                                    pass

                    final_response = ""
                    for evt in reversed(events):
                        if evt.get("event") == "final_response":
                            final_response = evt.get("response", "")
                            break
                        elif evt.get("_event_type") == "done":
                            text = evt.get("data", "")
                            if "Final response:" in text:
                                final_response = text.split("Final response: ", 1)[1][
                                    :500
                                ]
                            break

                    if not final_response:
                        final_response = "任务完成"

                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": final_response,
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                    st.success("✅ Task completed!")

            except requests.exceptions.Timeout:
                st.error("Request timed out. Please try again.")
            except Exception as e:
                st.error(f"Request failed: {e}")
            finally:
                st.session_state.agent_states["orchestrator"]["status"] = "online"
                st.session_state.agent_states["orchestrator"]["current_task"] = "Idle"
                st.session_state.agent_states["orchestrator"]["last_update"] = (
                    time.time()
                )

    with right_col:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="card-header"><span class="card-title">// Agent_Timeline</span></div>',
            unsafe_allow_html=True,
        )

        if st.session_state.task_events:
            for evt in reversed(st.session_state.task_events[-20:]):
                event_type = evt.get("event", "message")
                icon = EVENT_ICONS.get(event_type, "📝")
                color = EVENT_COLORS.get(event_type, "#cdd6f4")

                content_parts = []
                if evt.get("instruction"):
                    content_parts.append(f"指令: {evt.get('instruction')[:50]}")
                if evt.get("skill_id"):
                    content_parts.append(f"工具: {evt.get('skill_id')}")
                if evt.get("output"):
                    content_parts.append(f"输出: {evt.get('output')[:80]}")
                if evt.get("result"):
                    content_parts.append(f"结果: {evt.get('result')[:80]}")
                if evt.get("response"):
                    content_parts.append(f"响应: {evt.get('response')[:80]}")
                if evt.get("error"):
                    content_parts.append(f"错误: {evt.get('error')[:50]}")

                content = " | ".join(content_parts) if content_parts else str(evt)[:100]

                st.markdown(
                    f'<div style="padding: 8px; margin: 4px 0; border-left: 3px solid {color}; background: #161b22; border-radius: 4px;">'
                    f'<span style="font-size: 16px;">{icon}</span> '
                    f'<span style="color: {color}; font-weight: bold;">{event_type}</span>'
                    f'<div style="color: #a6adc8; font-size: 12px; margin-top: 4px;">{content}</div>'
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.info("Agent events will appear here when you run a task")

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="card-header"><span class="card-title">// Conversation_History</span></div>',
        unsafe_allow_html=True,
    )

    if st.session_state.messages:
        for msg in st.session_state.messages:
            st.markdown(
                f'<div class="chat-message {msg["role"]}">{msg["content"]}</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No messages yet. Start a task above to begin.")

    st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Page: Providers
# ══════════════════════════════════════════════════════════════════════════════


def render_providers():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="card-header"><span class="card-title">// Model_Providers</span></div>',
        unsafe_allow_html=True,
    )

    providers = _fetch_api("/providers", [])

    for p in providers:
        status = "online" if p.get("active") else "offline"
        st.markdown(
            f"""
        <div class="agent-card">
            <div class="agent-icon">🔌</div>
            <div class="agent-info">
                <div class="agent-name">{p.get("name", p.get("id"))}</div>
                <div class="agent-status">Model: {p.get("model", "unknown")}</div>
            </div>
            <span class="status-badge status-{status}">{status.upper()}</span>
        </div>
        """,
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Page: Skills
# ══════════════════════════════════════════════════════════════════════════════


def render_skills():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="card-header"><span class="card-title">// Installed_Skills</span></div>',
        unsafe_allow_html=True,
    )

    skills = _fetch_api("/skills", [])

    for s in skills:
        status = "online" if s.get("enabled") else "offline"
        st.markdown(
            f"""
        <div class="agent-card">
            <div class="agent-icon">🧩</div>
            <div class="agent-info">
                <div class="agent-name">{s.get("name", s.get("skill_id"))}</div>
                <div class="agent-status">{s.get("description", "")}</div>
            </div>
            <span class="status-badge status-{status}">{"ENABLED" if s.get("enabled") else "DISABLED"}</span>
        </div>
        """,
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Page: Configuration
# ══════════════════════════════════════════════════════════════════════════════


def render_config():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="card-header"><span class="card-title">// System_Configuration</span></div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        """
    <div class="code-block">
Version: 2.0.0
Environment: Production
Python: 3.9+
Framework: Streamlit
Database: SQLite
Vector Store: LanceDB
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Main Application
# ══════════════════════════════════════════════════════════════════════════════


def main():
    init_session_state()
    render_theme_toggle()
    render_sidebar()

    st.markdown('<div class="main-content">', unsafe_allow_html=True)

    page = st.session_state.current_page

    if page == "overview":
        render_overview()
    elif page == "monitor":
        render_agent_monitor()
    elif page == "results":
        render_results()
    elif page == "chat":
        render_chat()
    elif page == "providers":
        render_providers()
    elif page == "skills":
        render_skills()
    elif page == "config":
        render_config()

    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
