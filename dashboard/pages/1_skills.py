# dashboard/pages/1_skills.py

import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from dashboard.components.tech_style import apply_tech_style

apply_tech_style()
require_login()

st.markdown(
    """
<div class="page-header">
    <h1 class="page-title">&gt; Skills_Manager</h1>
    <p class="page-subtitle">Manage and configure AI agent skills</p>
</div>
""",
    unsafe_allow_html=True,
)

try:
    from core.skill_registry import SkillRegistry

    registry = SkillRegistry()
    skills = registry.list_all()

    st.markdown(
        f"""
    <div class="card">
        <div class="card-header">
            <span class="card-title">// Installed_Skills</span>
            <span class="status-badge status-online">{len(skills)} Total</span>
        </div>
    """,
        unsafe_allow_html=True,
    )

    if skills:
        for skill in skills:
            with st.expander(
                f"📦 {skill['skill_id']} - {skill.get('name', skill['skill_id'])}"
            ):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(
                        f"""
                    <div style="color: var(--text-secondary); font-size: 13px;">
                        <p><strong>ID:</strong> <code>{skill["skill_id"]}</code></p>
                        <p><strong>Name:</strong> {skill.get("name", "N/A")}</p>
                        <p><strong>Description:</strong> {skill.get("description", "N/A")}</p>
                        <p><strong>Version:</strong> {skill.get("version", "1.0.0")}</p>
                        <p><strong>Author:</strong> {skill.get("author", "N/A")}</p>
                        <p><strong>Tags:</strong> {skill.get("tags", "N/A")}</p>
                    </div>
                    """,
                        unsafe_allow_html=True,
                    )
                with col2:
                    enabled = skill.get("enabled", 1) == 1
                    if st.button(
                        f"{'Disable' if enabled else 'Enable'}",
                        key=f"toggle_{skill['skill_id']}",
                    ):
                        if enabled:
                            registry.disable(skill["skill_id"])
                        else:
                            registry.enable(skill["skill_id"])
                        st.rerun()
    else:
        st.info("No skills installed yet")

    st.markdown("</div>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"Load failed: {e}")
    import traceback

    st.code(traceback.format_exc(), language="python")
