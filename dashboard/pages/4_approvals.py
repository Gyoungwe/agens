# dashboard/pages/4_approvals.py

import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from dashboard.components.tech_style import apply_tech_style

apply_tech_style()
require_login()

st.markdown(
    """
<div class="page-header">
    <h1 class="page-title">&gt; Approval_Queue</h1>
    <p class="page-subtitle">Review and approve pending actions</p>
</div>
""",
    unsafe_allow_html=True,
)

try:
    from evolution.approval_queue import ApprovalQueue

    queue = ApprovalQueue()
    pending = queue.list_pending()

    st.markdown(
        f"""
    <div class="card">
        <div class="card-header">
            <span class="card-title">// Pending_Approvals</span>
            <span class="status-badge status-pending">{len(pending)}</span>
        </div>
    """,
        unsafe_allow_html=True,
    )

    if pending:
        for item in pending:
            with st.expander(f"Request: {item.get('id', 'unknown')}"):
                st.json(item)
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Approve", key=f"approve_{item.get('id')}"):
                        st.info("Approved")
                with col2:
                    if st.button("❌ Reject", key=f"reject_{item.get('id')}"):
                        st.info("Rejected")
    else:
        st.info("No pending approvals")

    st.markdown("</div>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"Load failed: {e}")
    import traceback

    st.code(traceback.format_exc(), language="python")
