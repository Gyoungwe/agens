import logging

import pytest

from bus.message_bus import MessageBus
from core.base_agent import BaseAgent
from core.bio_harness import BioWorkflowHarness, HarnessStageSpec
from core.events import EventEnvelope
from providers.provider_registry import ProviderRegistry


class DummyAgent(BaseAgent):
    async def execute(self, instruction: str, context: dict) -> str:
        return "ok"


class FakeStore:
    def __init__(self):
        self.rows = []

    def save_result(self, session_id, trace_id, agent_id, result, status="ok"):
        self.rows.append(
            {
                "session_id": session_id,
                "trace_id": trace_id,
                "agent_id": agent_id,
                "result": result,
                "status": status,
            }
        )

    def get_results(self, session_id):
        return [row for row in self.rows if row["session_id"] == session_id]

    def get_results_by_trace(self, trace_id):
        return [row for row in self.rows if row["trace_id"] == trace_id]


class FakeSessionManager:
    def __init__(self):
        self.store = FakeStore()


class FakeVectorStore:
    def __init__(self):
        self.calls = []

    async def add(self, **kwargs):
        self.calls.append(kwargs)
        return "mem-1"


class FakeKnowledgeBase:
    def __init__(self):
        self.calls = []

    async def add(self, **kwargs):
        self.calls.append(kwargs)
        return "kb-1"


class HealthyProvider:
    async def health_check(self):
        return True


class UnhealthyProvider:
    async def health_check(self):
        return False


@pytest.mark.asyncio
async def test_trace_specific_emitters_are_isolated():
    bus = MessageBus()
    agent = DummyAgent(agent_id="dummy", bus=bus)
    received_t1 = []
    received_t2 = []

    agent.register_trace_emitter("trace-1", lambda event: received_t1.append(event))
    agent.register_trace_emitter("trace-2", lambda event: received_t2.append(event))

    agent._emit(
        EventEnvelope.agent_start(
            agent_id="dummy",
            trace_id="trace-1",
            instruction="hello",
            session_id="sess-1",
        )
    )

    assert len(received_t1) == 1
    assert len(received_t2) == 0


@pytest.mark.asyncio
async def test_provider_registry_returns_best_healthy_provider():
    registry = ProviderRegistry()
    registry._providers = {
        "bad": UnhealthyProvider(),
        "good": HealthyProvider(),
    }
    registry._active = "bad"

    best = await registry.get_best_available(preferred_id="bad")
    assert best == "good"


@pytest.mark.asyncio
async def test_bio_harness_persists_stage_memory_and_workflow_learning():
    session_manager = FakeSessionManager()
    vector_store = FakeVectorStore()
    knowledge_base = FakeKnowledgeBase()
    harness = BioWorkflowHarness(
        session_manager=session_manager,
        logger=logging.getLogger("test"),
        vector_store=vector_store,
        knowledge_base=knowledge_base,
    )

    class StubOrchestrator:
        async def run_single_agent(
            self,
            user_input: str,
            agent_id: str,
            session_id: str = None,
            trace_id: str = None,
            runtime_context=None,
        ) -> str:
            return f"{agent_id}:{runtime_context.get('scope_id')}:{runtime_context.get('provider_id')}"

    result = await harness.run(
        orchestrator=StubOrchestrator(),
        session_id="sess-1",
        trace_id="trace-1",
        goal="goal",
        dataset="dataset-a",
        stage_specs=[
            HarnessStageSpec(
                name="planning",
                agent_id="bio_planner_agent",
                prompt="plan {goal}",
                knowledge_topic="planning",
            ),
            HarnessStageSpec(
                name="evolution",
                agent_id="bio_evolution_agent",
                prompt="evolve {goal}",
                depends_on=["planning"],
                knowledge_topic="evolution",
            ),
        ],
        continue_on_error=True,
        scope_id="scope-a",
        provider_id="deepseek",
    )

    assert result["success"] is True
    assert len(vector_store.calls) == 2
    assert all(call["scope_id"] == "scope-a" for call in vector_store.calls)
    # Knowledge base is NOT written directly anymore (P8: approval-gated learning loop)
    # Instead, an EvolutionApproval record is created for later review.
    # Verify the approval was created.
    from api.routers.evolution_router import get_store

    store = get_store()
    approvals = store.list_by_status("pending")
    assert len(approvals) >= 1
    latest = next(a for a in approvals if a.request_id == "workflow_trace-1")
    assert latest.agent_id == "bio_evolution_agent"
    assert latest.changes["kind"] == "workflow_retrospective"
    assert latest.changes["scope_id"] == "scope-a"
    assert latest.changes["goal"] == "goal"
    assert latest.changes["dataset"] == "dataset-a"
