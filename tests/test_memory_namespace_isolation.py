import pytest

from knowledge.knowledge_base import KnowledgeBase
from memory.vector_store import VectorStore


async def fake_embed(text: str):
    value = float(sum(ord(ch) for ch in text) % 17 + 1)
    return [value] * 1024


@pytest.mark.asyncio
async def test_vector_store_isolates_memory_by_namespace(tmp_path):
    store = VectorStore(db_path=str(tmp_path / "memory"))
    store._embed = fake_embed

    await store.add(
        text="chat-only memory",
        session_id="sess-1",
        metadata={"namespace": "chat_memory"},
        namespace="chat_memory",
    )
    await store.add(
        text="research-only memory",
        session_id="sess-1",
        metadata={"namespace": "research_memory"},
        namespace="research_memory",
    )

    chat_results = await store.search(
        query="memory",
        session_id="sess-1",
        namespace="chat_memory",
    )
    research_results = await store.search(
        query="memory",
        session_id="sess-1",
        namespace="research_memory",
    )

    assert any(item["text"] == "chat-only memory" for item in chat_results)
    assert all(item["namespace"] == "chat_memory" for item in chat_results)
    assert any(item["text"] == "research-only memory" for item in research_results)
    assert all(item["namespace"] == "research_memory" for item in research_results)


@pytest.mark.asyncio
async def test_knowledge_base_isolates_results_by_namespace(tmp_path):
    kb = KnowledgeBase(db_path=str(tmp_path / "knowledge"))
    kb._embed = fake_embed
    kb._lance_table = None
    kb._in_memory = []

    await kb.add(
        text="chat-shared knowledge",
        agent_ids=["agent-a"],
        topic="general",
        namespace="shared_knowledge",
        metadata={"namespace": "shared_knowledge"},
    )
    await kb.add(
        text="research knowledge only",
        agent_ids=["research_agent"],
        topic="research",
        namespace="research_memory",
        metadata={"namespace": "research_memory"},
    )

    research_results = await kb.search(
        query="research knowledge only",
        agent_id="research_agent",
        topic="research",
        namespace="research_memory",
    )
    shared_results = await kb.search(
        query="chat-shared knowledge",
        agent_id="agent-a",
        topic="general",
        namespace="shared_knowledge",
    )

    assert any(item["text"] == "research knowledge only" for item in research_results)
    assert all(item["text"] != "chat-shared knowledge" for item in research_results)
    assert any(item["text"] == "chat-shared knowledge" for item in shared_results)
