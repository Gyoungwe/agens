# tests/test_orchestrator.py

import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from core.orchestrator import Orchestrator
from bus.message_bus import MessageBus


class TestOrchestratorPendingTTL:
    @pytest.mark.asyncio
    async def test_pending_timestamp_recorded(self):
        bus = MessageBus()
        registry = MagicMock()
        registry.get.return_value = MagicMock()

        orch = Orchestrator(bus=bus, provider_registry=registry)
        orch._pending = {"trace-1": {"agent1": None}}
        orch._pending_timestamps = {"trace-1": 1000.0}

        assert "trace-1" in orch._pending
        assert orch._pending_timestamps["trace-1"] == 1000.0

    @pytest.mark.asyncio
    async def test_cleanup_removes_stale_pending(self):
        bus = MessageBus()
        registry = MagicMock()
        registry.get.return_value = MagicMock()

        orch = Orchestrator(bus=bus, provider_registry=registry)
        import time

        now = time.time()
        orch._pending = {
            "trace-old": {"agent1": None},
            "trace-new": {"agent2": None},
        }
        orch._pending_timestamps = {
            "trace-old": now - 1000,
            "trace-new": now,
        }
        orch._events = {"trace-old": asyncio.Event(), "trace-new": asyncio.Event()}
        orch._event_queues = {
            "trace-old": asyncio.Queue(),
            "trace-new": asyncio.Queue(),
        }
        orch._event_callbacks = {"trace-old": MagicMock(), "trace-new": MagicMock()}
        orch._PENDING_TTL = 600

        await orch._cleanup_stale_pending()

        assert "trace-old" not in orch._pending
        assert "trace-new" in orch._pending

    @pytest.mark.asyncio
    async def test_cleanup_task_is_started(self):
        bus = MessageBus()
        registry = MagicMock()
        registry.get.return_value = MagicMock()

        orch = Orchestrator(bus=bus, provider_registry=registry)

        assert orch._cleanup_task is not None
        assert not orch._cleanup_task.done()

        orch._cleanup_task.cancel()
        try:
            await orch._cleanup_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_result_pop_cleans_timestamp(self):
        bus = MessageBus()
        registry = MagicMock()
        registry.get.return_value = MagicMock()

        orch = Orchestrator(bus=bus, provider_registry=registry)
        orch._pending = {"trace-1": {"agent1": {"output": "done"}}}
        orch._pending_timestamps = {"trace-1": 1000.0}
        orch._events = {"trace-1": asyncio.Event()}

        results = orch._pending.pop("trace-1", {})
        orch._pending_timestamps.pop("trace-1", None)
        orch._events.pop("trace-1", None)

        assert results == {"agent1": {"output": "done"}}
        assert "trace-1" not in orch._pending_timestamps
        assert "trace-1" not in orch._events


class TestOrchestratorEventEmission:
    @pytest.mark.asyncio
    async def test_safe_emit_callback_handles_exception(self):
        bus = MessageBus()
        registry = MagicMock()
        registry.get.return_value = MagicMock()

        orch = Orchestrator(bus=bus, provider_registry=registry)

        async def bad_callback(event):
            raise RuntimeError("callback error")

        orch._event_callbacks["trace-1"] = bad_callback

        from core.events import EventEnvelope

        event = EventEnvelope.agent_start(
            agent_id="test",
            trace_id="trace-1",
            instruction="test",
        )

        await orch._safe_emit_callback(event, "trace-1")
        await asyncio.sleep(0.1)
