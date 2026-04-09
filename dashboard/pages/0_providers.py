# dashboard/pages/0_providers.py

import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import asyncio
import yaml
import streamlit as st
from dashboard.components.tech_style import apply_tech_style

apply_tech_style()
require_login()

st.markdown(
    """
<div class="page-header">
    <h1 class="page-title">&gt; Model_Config</h1>
    <p class="page-subtitle">Configure and switch between AI providers</p>
</div>
""",
    unsafe_allow_html=True,
)

if "provider_msg" not in st.session_state:
    st.session_state["provider_msg"] = None

if "debug_info" not in st.session_state:
    st.session_state["debug_info"] = ""

try:
    from providers.provider_registry import ProviderRegistry
    from providers.base_provider import ChatMessage

    reg = ProviderRegistry()
    active = reg.get()
    providers = reg.list_all()

    st.markdown(
        """
    <div class="card">
        <div class="card-header">
            <span class="card-title">// Active_Model</span>
            <span class="status-badge status-online">Online</span>
        </div>
    """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f"""
        <div class="code-block">
Provider ID: {reg.active_id}
Type: {active.provider_id}
Model: {getattr(active, "model", "unknown")}
BaseURL: {getattr(active, "base_url", "N/A")}
        </div>
        """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            """
        <div style="color: var(--text-secondary);">
            <p style="font-family: 'JetBrains Mono', monospace; font-size: 13px;">
                <span style="color: var(--accent-cyan);">//</span> Registered Providers:
            </p>
        """,
            unsafe_allow_html=True,
        )
        for p in providers:
            icon = "🟢" if p["active"] else "⚪"
            st.markdown(
                f"<p style='color: var(--accent-green);'>{icon} {p['id']} — {p['name']}</p>",
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.get("debug_info"):
        with st.expander("🐛 Debug_Info"):
            st.code(st.session_state["debug_info"], language="text")

except Exception as e:
    st.error(f"Load failed: {e}")
    import traceback

    st.code(traceback.format_exc(), language="python")
    st.stop()

st.markdown('<hr class="divider">', unsafe_allow_html=True)

st.markdown(
    """
<div class="card">
    <div class="card-header">
        <span class="card-title">// Switch_Model</span>
    </div>
""",
    unsafe_allow_html=True,
)

available = [p["id"] for p in providers]
if not available:
    st.warning("No providers available")
else:
    cols = st.columns(min(len(available), 4))
    for i, pid in enumerate(available):
        with cols[i % 4]:
            is_active = pid == reg.active_id
            if st.button(
                f"{'✅ ' if is_active else '▶️ '} {pid}",
                key=f"switch_{pid}",
                use_container_width=True,
            ):
                try:
                    reg.use(pid)
                    st.session_state["provider_msg"] = f"✅ Switched to [{pid}]"
                    st.session_state["debug_info"] = (
                        f"Switch success, active: {reg.active_id}"
                    )
                    st.rerun()
                except Exception as e:
                    st.session_state["provider_msg"] = f"❌ Switch failed: {e}"
                    st.session_state["debug_info"] = f"Error: {traceback.format_exc()}"
                    st.rerun()

msg = st.session_state.get("provider_msg")
if msg:
    if "❌" in msg:
        st.error(msg)
    else:
        st.success(msg)
    st.session_state["provider_msg"] = None

st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<hr class="divider">', unsafe_allow_html=True)

st.markdown(
    """
<div class="card">
    <div class="card-header">
        <span class="card-title">// Test_Model</span>
    </div>
""",
    unsafe_allow_html=True,
)

col_a, col_b = st.columns([3, 1])
with col_a:
    test_input = st.text_input("Test_Input", value="Hello, how are you?")
with col_b:
    test_btn = st.button("🚀 Send", type="primary", use_container_width=True)

if test_btn and test_input:
    with st.spinner("Calling..."):
        try:
            prov = reg.get()
            st.info(
                f"Provider: {prov.provider_id}, Model: {getattr(prov, 'model', 'unknown')}"
            )

            async def t():
                r = await prov.chat(
                    messages=[ChatMessage(role="user", content=test_input)],
                    max_tokens=100,
                )
                return r.text

            result = asyncio.run(t())
            st.success("✅ Call successful")
            st.markdown(f"**Response:**\n\n{result}")
        except Exception as e:
            st.error(f"❌ Call failed: {e}")
            with st.expander("🐛 Error_Details"):
                import traceback

                st.code(traceback.format_exc(), language="python")

st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<hr class="divider">', unsafe_allow_html=True)

st.markdown(
    """
<div class="card">
    <div class="card-header">
        <span class="card-title">// Add_Custom_Provider</span>
    </div>
""",
    unsafe_allow_html=True,
)

with st.form("add_provider", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        new_id = st.text_input("Provider_ID", placeholder="my-gpt4")
        new_type = st.selectbox("Type", ["openai", "anthropic"])
    with col2:
        new_name = st.text_input("Display_Name", placeholder="My Custom Model")
        new_model = st.text_input("Model_Name", placeholder="gpt-4o")

    new_base_url = st.text_input("Base_URL", placeholder="https://api.example.com/v1")
    new_api_key = st.text_input("API_Key", type="password", placeholder="sk-...")

    submitted = st.form_submit_button("💾 Add_Provider", use_container_width=True)
    if submitted:
        if not new_id or not new_base_url or not new_api_key:
            st.warning("⚠️ Please fill all required fields")
        else:
            try:
                config_path = os.path.join(
                    os.path.dirname(__file__), "../..", "providers", "profiles.yaml"
                )
                with open(config_path) as f:
                    config = yaml.safe_load(f)

                existing = [p for p in config.get("profiles", []) if p["id"] == new_id]
                if existing:
                    st.warning(f"⚠️ Provider [{new_id}] already exists")
                else:
                    new_profile = {
                        "id": new_id,
                        "type": new_type,
                        "name": new_name or new_id,
                        "model": new_model or new_id,
                        "base_url": new_base_url,
                        "api_key": new_api_key,
                    }
                    config.setdefault("profiles", []).append(new_profile)

                    with open(config_path, "w") as f:
                        yaml.dump(
                            config, f, allow_unicode=True, default_flow_style=False
                        )

                    st.success(f"✅ Provider [{new_id}] added. Restart to take effect.")
            except Exception as e:
                st.error(f"❌ Add failed: {e}")

st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<hr class="divider">', unsafe_allow_html=True)

st.markdown(
    """
<div class="card">
    <div class="card-header">
        <span class="card-title">// profiles.yaml</span>
    </div>
""",
    unsafe_allow_html=True,
)

try:
    config_path = os.path.join(
        os.path.dirname(__file__), "../..", "providers", "profiles.yaml"
    )
    with open(config_path) as f:
        raw = f.read()
    st.code(raw, language="yaml", line_numbers=True)
except Exception as e:
    st.error(f"Read failed: {e}")

st.markdown("</div>", unsafe_allow_html=True)
