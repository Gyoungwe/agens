# dashboard/pages/2_knowledge.py

import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from dashboard.components.tech_style import apply_tech_style

apply_tech_style()
require_login()

st.markdown(
    """
<div class="page-header">
    <h1 class="page-title">&gt; Knowledge_Base</h1>
    <p class="page-subtitle">Manage vector knowledge and RAG context</p>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="card">
    <div class="card-header">
        <span class="card-title">// Vector_Store_Status</span>
        <span class="status-badge status-online">Connected</span>
    </div>
    <div class="code-block">
Provider: LanceDB
Status: Ready
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
        <span class="card-title">// Query_Knowledge</span>
    </div>
""",
    unsafe_allow_html=True,
)

query = st.text_input("Search_Query", placeholder="Enter your search...")
top_k = st.slider("Top_K", 1, 10, 3)

if st.button("🔍 Search", use_container_width=True):
    if query:
        st.info(f"Searching for: {query} (top {top_k})")
    else:
        st.warning("Please enter a search query")

st.markdown("</div>", unsafe_allow_html=True)
