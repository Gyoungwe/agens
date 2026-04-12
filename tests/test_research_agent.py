from unittest.mock import AsyncMock, MagicMock

import pytest

from agents.research_agent.research_agent import ResearchAgent
from core.events import AgentEventType


def make_registry(skill_ids: list[str]):
    registry = MagicMock()
    registry.get_for_agent_metadata.return_value = [
        MagicMock(skill_id=skill_id) for skill_id in skill_ids
    ]
    return registry


def test_select_research_skills_prefers_scholarly_tools_for_latest_paper_queries():
    agent = ResearchAgent(
        bus=MagicMock(),
        registry=make_registry(
            [
                "bgpt_paper_search",
                "paper_lookup",
                "literature_review",
                "database_lookup",
                "web_search",
            ]
        ),
    )

    selected = agent._select_research_skills("帮我查最新的重复序列处理方法和论文")

    assert selected[:3] == ["bgpt_paper_search", "paper_lookup", "literature_review"]


def test_select_research_skills_prefers_database_tools_for_entity_queries():
    agent = ResearchAgent(
        bus=MagicMock(),
        registry=make_registry(
            [
                "database_lookup",
                "depmap",
                "primekg",
                "web_search",
            ]
        ),
    )

    selected = agent._select_research_skills(
        "查询 EGFR gene pathway 和 clinical trial 信息"
    )

    assert selected[:3] == ["database_lookup", "depmap", "primekg"]


@pytest.mark.asyncio
async def test_collect_research_skill_outputs_uses_multiple_research_skills():
    agent = ResearchAgent(
        bus=MagicMock(),
        registry=make_registry(
            [
                "bgpt_paper_search",
                "paper_lookup",
                "literature_review",
            ]
        ),
    )
    agent.use_skill = AsyncMock(
        side_effect=[
            {"results": [{"url": "https://example.com/paper1"}]},
            {"results": [{"url": "https://example.com/paper2"}]},
            {"results": [{"url": "https://example.com/paper3"}]},
        ]
    )

    outputs = await agent._collect_research_skill_outputs(
        "latest papers on repeat sequences"
    )

    assert list(outputs.keys()) == [
        "bgpt_paper_search",
        "paper_lookup",
        "literature_review",
    ]
    assert agent.use_skill.await_count == 3


def test_explain_research_skill_selection_mentions_reason_categories():
    agent = ResearchAgent(
        bus=MagicMock(), registry=make_registry(["bgpt_paper_search"])
    )

    explanation = agent._explain_research_skill_selection(
        "帮我查最新论文并整理 DOI 引用",
        ["bgpt_paper_search", "citation_management"],
    )

    assert "bgpt_paper_search" in explanation
    assert "scholarly/latest-paper query" in explanation
    assert "citation query" in explanation


@pytest.mark.asyncio
async def test_collect_research_skill_outputs_emits_selection_events():
    agent = ResearchAgent(
        bus=MagicMock(),
        registry=make_registry(["bgpt_paper_search", "paper_lookup"]),
    )
    emitted = []
    agent._emit = emitted.append
    agent._current_trace_id = "trace-1"
    agent.use_skill = AsyncMock(
        side_effect=[
            {"results": [{"url": "https://example.com/p1"}]},
            {"results": [{"url": "https://example.com/p2"}]},
        ]
    )

    await agent._collect_research_skill_outputs("latest papers on repeat sequences")

    assert len(emitted) >= 2
    assert emitted[0].type == AgentEventType.AGENT_THINKING.value
    assert "Research skill selection:" in emitted[0].data["message"]
    assert emitted[-1].type == AgentEventType.AGENT_OUTPUT.value
    assert emitted[-1].data["summary"] == "research_skill_selection"
    assert emitted[-1].data["selected_skills"] == ["bgpt_paper_search", "paper_lookup"]
    assert emitted[-1].data["completed_skills"] == ["bgpt_paper_search", "paper_lookup"]
