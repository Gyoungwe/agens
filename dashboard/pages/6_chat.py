# dashboard/pages/6_chat.py

import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import asyncio
import streamlit as st
from dashboard.components.tech_style import apply_tech_style

apply_tech_style()
require_login()

st.markdown(
    """
<div class="page-header">
    <h1 class="page-title">&gt; Chat_Interface</h1>
    <p class="page-subtitle">Interact with the multi-agent system</p>
</div>
""",
    unsafe_allow_html=True,
)

if "orchestrator" not in st.session_state:
    try:
        from bus.message_bus import MessageBus
        from providers.provider_registry import ProviderRegistry
        from session.session_manager import SessionManager
        from core.orchestrator import Orchestrator

        bus = MessageBus()
        provider_registry = ProviderRegistry()
        session_manager = SessionManager()
        orchestrator = Orchestrator(
            bus=bus,
            provider_registry=provider_registry,
            session_manager=session_manager,
        )
        st.session_state["orchestrator"] = orchestrator
    except Exception as e:
        st.error(f"Init failed: {e}")
        import traceback

        st.code(traceback.format_exc(), language="python")
        st.stop()

orchestrator = st.session_state["orchestrator"]

if "messages" not in st.session_state:
    st.session_state["messages"] = []

for msg in st.session_state.messages:
    role = msg.get("role", "user")
    content = msg.get("content", "")
    with st.chat_message(role):
        st.markdown(content)

user_input = st.chat_input("Enter your task...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Processing..."):
            try:

                async def run_task():
                    result = await orchestrator.run(user_input)
                    return result

                result = asyncio.run(run_task())
                st.markdown(result)
                st.session_state.messages.append(
                    {"role": "assistant", "content": result}
                )
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_msg}
                )

if st.button("Clear Chat"):
    st.session_state.messages = []
    st.rerun()
