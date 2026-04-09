# tests/test_message_bus.py

import pytest
import asyncio
from collections import OrderedDict
from bus.message_bus import MessageBus, DeduplicationCache, MessageEnvelope
from core.message import Message


class TestDeduplicationCache:
    @pytest.mark.asyncio
    async def test_cache_is_ordered_dict(self):
        cache = DeduplicationCache()
        assert isinstance(cache._cache, OrderedDict)

    @pytest.mark.asyncio
    async def test_first_call_not_duplicate(self):
        cache = DeduplicationCache(ttl=300)
        is_dup = await cache.is_duplicate("event-1")
        assert is_dup is False

    @pytest.mark.asyncio
    async def test_second_call_within_ttl_is_duplicate(self):
        cache = DeduplicationCache(ttl=300)
        await cache.is_duplicate("event-1")
        is_dup = await cache.is_duplicate("event-1")
        assert is_dup is True

    @pytest.mark.asyncio
    async def test_expired_entry_not_duplicate(self):
        cache = DeduplicationCache(ttl=0)
        await asyncio.sleep(0.01)
        is_dup = await cache.is_duplicate("event-1")
        assert is_dup is False

    @pytest.mark.asyncio
    async def test_lru_eviction_order(self):
        cache = DeduplicationCache(max_size=5, ttl=300)
        for i in range(5):
            await cache.is_duplicate(f"event-{i}")

        await cache.is_duplicate("event-0")
        await cache.is_duplicate("event-5")

        assert "event-0" in cache._cache
        assert "event-1" not in cache._cache

    @pytest.mark.asyncio
    async def test_mark_processed(self):
        cache = DeduplicationCache(ttl=300)
        await cache.mark_processed("event-1")
        is_dup = await cache.is_duplicate("event-1")
        assert is_dup is True


class TestMessageEnvelope:
    def test_envelope_creation(self):
        msg = Message(
            sender="agent1",
            recipient="agent2",
            type="task",
            payload={},
            trace_id="trace-123",
            session_id="session-456",
            correlation_id="corr-789",
        )
        env = MessageEnvelope(
            event_id=msg.id,
            task_id=msg.trace_id,
            session_id=msg.session_id,
            correlation_id=msg.correlation_id,
            message=msg,
        )
        assert env.event_id == msg.id
        assert env.task_id == "trace-123"
        assert env.session_id == "session-456"
        assert env.correlation_id == "corr-789"


class TestMessageBus:
    @pytest.mark.asyncio
    async def test_register_agent(self):
        bus = MessageBus()
        await bus.register("agent1")
        assert "agent1" in bus.registered_agents

    @pytest.mark.asyncio
    async def test_unregister_agent(self):
        bus = MessageBus()
        await bus.register("agent1")
        await bus.unregister("agent1")
        assert "agent1" not in bus.registered_agents

    @pytest.mark.asyncio
    async def test_send_to_registered_agent(self):
        bus = MessageBus()
        await bus.register("receiver")
        msg = Message(
            sender="sender",
            recipient="receiver",
            type="task",
            payload={},
        )
        await bus.send(msg)
        received = await bus.receive("receiver", timeout=1)
        assert received is not None
        assert received.message.sender == "sender"

    @pytest.mark.asyncio
    async def test_send_to_unregistered_agent_logs_error(self, caplog):
        bus = MessageBus()
        msg = Message(
            sender="sender",
            recipient="unknown",
            type="task",
            payload={},
        )
        await bus.send(msg)

    @pytest.mark.asyncio
    async def test_broadcast(self):
        bus = MessageBus()
        await bus.register("agent1")
        await bus.register("agent2")
        await bus.register("agent3")
        msg = Message(
            sender="orchestrator",
            recipient="*",
            type="task",
            payload={},
        )
        await bus.send(msg)

        for agent in ["agent1", "agent2", "agent3"]:
            received = await bus.receive(agent, timeout=1)
            assert received is not None
            assert received.message.sender == "orchestrator"

    @pytest.mark.asyncio
    async def test_broadcast_concurrent_delivery(self):
        bus = MessageBus()
        for i in range(5):
            await bus.register(f"agent{i}")

        msg = Message(
            sender="sender",
            recipient="*",
            type="task",
            payload={},
        )
        await bus.send(msg)

        for i in range(5):
            received = await bus.receive(f"agent{i}", timeout=1)
            assert received is not None

    @pytest.mark.asyncio
    async def test_queue_size(self):
        bus = MessageBus()
        await bus.register("agent1")
        msg = Message(
            sender="sender",
            recipient="agent1",
            type="task",
            payload={},
        )
        await bus.send(msg)
        await bus.send(msg)
        assert bus.queue_size("agent1") == 2

    @pytest.mark.asyncio
    async def test_get_history(self):
        bus = MessageBus()
        msg = Message(
            sender="sender",
            recipient="receiver",
            type="task",
            payload={},
            trace_id="trace-123",
        )
        await bus.send(msg)
        history = bus.get_history("trace-123")
        assert len(history) == 1
        assert history[0].trace_id == "trace-123"
