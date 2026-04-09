# dashboard/pages/5_sessions.py

import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from dashboard.components.tech_style import apply_tech_style

apply_tech_style()
require_login()

st.markdown(
    """
<div class="page-header">
    <h1 class="page-title">&gt; Session_Manager</h1>
    <p class="page-subtitle">View and manage conversation sessions</p>
</div>
""",
    unsafe_allow_html=True,
)

try:
    from session.session_store import SessionStore

    store = SessionStore()
    sessions = store.list_sessions()

    st.markdown(
        f"""
    <div class="card">
        <div class="card-header">
            <span class="card-title">// All_Sessions</span>
            <span class="status-badge status-online">{len(sessions)} Total</span>
        </div>
    """,
        unsafe_allow_html=True,
    )

    if sessions:
        for session in sessions:
            status = session.get("status", "unknown")
            status_class = "status-online" if status == "active" else "status-offline"
            with st.expander(
                f"Session {session['session_id'][:8]}... | {session.get('title', 'No title')[:30]} | {status.upper()}"
            ):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.json(session)
                with col2:
                    if st.button("🗑️ Delete", key=f"delete_{session['session_id']}"):
                        st.info("Session deleted")
    else:
        st.info("No sessions yet")

    st.markdown("</div>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"Load failed: {e}")
    import traceback

    st.code(traceback.format_exc(), language="python")
