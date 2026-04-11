import asyncio

import pytest

from bus.message_bus import MessageBus
from core.base_agent import BaseAgent
from core.orchestrator import Orchestrator
from providers.provider_registry import ProviderRegistry
from session.session_manager import SessionManager
from session.session_store import SessionStore


class SlowEchoAgent(BaseAgent):
    async def execute(self, instruction: str, context: dict) -> str:
        await asyncio.sleep(0.02)
        return f"echo::{instruction}::{context.get('scope_id')}"


@pytest.mark.asyncio
async def test_concurrent_run_single_agent_trace_isolation(tmp_path):
    bus = MessageBus()
    session_store = SessionStore(db_path=tmp_path / "sessions.db")
    session_manager = SessionManager(session_store)
    provider_registry = ProviderRegistry()
    orchestrator = Orchestrator(
        bus=bus,
        provider_registry=provider_registry,
        session_manager=session_manager,
    )
    agent = SlowEchoAgent(
        agent_id="echo_agent", bus=bus, provider_registry=provider_registry
    )

    await orchestrator.start()
    await agent.start()

    session_a = session_manager.new_session(title="session-a")
    session_b = session_manager.new_session(title="session-b")

    trace_a_events = []
    trace_b_events = []
    orchestrator.set_event_callback(
        "trace-a", lambda event: trace_a_events.append(event)
    )
    orchestrator.set_event_callback(
        "trace-b", lambda event: trace_b_events.append(event)
    )
    agent.register_trace_emitter("trace-a", lambda event: trace_a_events.append(event))
    agent.register_trace_emitter("trace-b", lambda event: trace_b_events.append(event))

    try:
        result_a, result_b = await asyncio.gather(
            orchestrator.run_single_agent(
                user_input="alpha",
                agent_id="echo_agent",
                session_id=session_a,
                trace_id="trace-a",
                runtime_context={"scope_id": "scope-a"},
            ),
            orchestrator.run_single_agent(
                user_input="beta",
                agent_id="echo_agent",
                session_id=session_b,
                trace_id="trace-b",
                runtime_context={"scope_id": "scope-b"},
            ),
        )

        assert "scope-a" in result_a
        assert "scope-b" in result_b
        assert all(
            getattr(event, "trace_id", getattr(event, "task_id", "trace-a"))
            == "trace-a"
            for event in trace_a_events
        )
        assert all(
            getattr(event, "trace_id", getattr(event, "task_id", "trace-b"))
            == "trace-b"
            for event in trace_b_events
        )
    finally:
        agent.clear_trace_emitter("trace-a")
        agent.clear_trace_emitter("trace-b")
        orchestrator.clear_event_queue("trace-a")
        orchestrator.clear_event_queue("trace-b")
        await agent.stop()
        await orchestrator.stop()
