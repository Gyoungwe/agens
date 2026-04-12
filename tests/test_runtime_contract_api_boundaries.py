from api.main import ResearchRequest, SessionInfo, run_research
from core.runtime_contract import RUNTIME_CONTRACT_VERSION


def test_session_info_matches_runtime_session_contract_shape():
    session = SessionInfo(
        session_id="sess-1",
        title="Session",
        status="active",
        message_count=0,
        created_at="2026-01-01T00:00:00",
        updated_at="2026-01-01T00:00:00",
        metadata={"namespace": "chat_session"},
    )
    data = session.model_dump()

    assert data["session_id"] == "sess-1"
    assert data["title"] == "Session"
    assert data["status"] == "active"
    assert data["message_count"] == 0


async def _fake_research_run_single_agent(*args, **kwargs):
    agent_id = kwargs.get("agent_id")
    if agent_id == "research_agent":
        return "raw research body"
    if agent_id == "writer_agent":
        return "Executive summary\n\nKey findings..."
    return ""


class _FakeOrchestrator:
    async def run_single_agent(self, *args, **kwargs):
        return await _fake_research_run_single_agent(*args, **kwargs)


async def _fake_empty_memory_context(*args, **kwargs):
    return ""


def test_research_run_response_matches_runtime_output_contract_shape(monkeypatch):
    from api import main as api_main

    fake = _FakeOrchestrator()
    monkeypatch.setattr(api_main.state, "_get_orchestrator", lambda: fake)
    monkeypatch.setattr(
        api_main.state.session_manager,
        "new_session",
        lambda title, kind="research": "research-session",
    )
    monkeypatch.setattr(
        api_main,
        "_retrieve_research_knowledge_context",
        _fake_empty_memory_context,
    )

    response = api_main.asyncio.run(
        run_research(ResearchRequest(query="single cell workflow"))
    )

    assert response["success"] is True
    assert response["session_id"] == "research-session"
    assert response["summary_format"] == "text"
    assert response["summary"] == "Executive summary\n\nKey findings..."
    assert isinstance(RUNTIME_CONTRACT_VERSION, str)
