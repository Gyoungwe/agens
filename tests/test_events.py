# tests/test_events.py

import pytest
from core.events import EventEnvelope, AgentEvent, AgentEventType


class TestEventEnvelope:
    def test_to_dict(self):
        env = EventEnvelope(
            event_id="evt-1",
            task_id="task-1",
            session_id="sess-1",
            correlation_id="corr-1",
            type="agent_start",
            agent="test_agent",
            status="started",
            data={"key": "value"},
        )
        d = env.to_dict()
        assert d["event_id"] == "evt-1"
        assert d["task_id"] == "task-1"
        assert d["type"] == "agent_start"
        assert d["data"] == {"key": "value"}

    def test_to_sse_format(self):
        env = EventEnvelope(
            event_id="evt-1",
            task_id="task-1",
            type="agent_start",
            agent="test_agent",
            status="started",
            data={"message": "hello"},
        )
        sse = env.to_sse()
        assert "event: agent_start" in sse
        assert "evt-1" in sse
        assert "task-1" in sse
        assert "data:" in sse

    def test_factory_agent_start(self):
        env = EventEnvelope.agent_start(
            agent_id="test_agent",
            trace_id="trace-123",
            instruction="do something",
            session_id="sess-456",
        )
        assert env.type == "agent_start"
        assert env.agent == "test_agent"
        assert env.task_id == "trace-123"
        assert env.session_id == "sess-456"
        assert env.status == "started"

    def test_factory_agent_thinking(self):
        env = EventEnvelope.agent_thinking(
            agent_id="test_agent",
            trace_id="trace-123",
            message="thinking...",
        )
        assert env.type == "agent_thinking"
        assert env.status == "running"
        assert "thinking..." in env.data["message"]

    def test_factory_agent_tool_call(self):
        env = EventEnvelope.agent_tool_call(
            agent_id="test_agent",
            trace_id="trace-123",
            skill_id="web_search",
            instruction="search for x",
        )
        assert env.type == "agent_tool_call"
        assert env.data["skill_id"] == "web_search"

    def test_factory_agent_file_read(self):
        env = EventEnvelope.agent_file_read(
            agent_id="test_agent",
            trace_id="trace-123",
            file_path="/tmp/test.txt",
        )
        assert env.type == "agent_file_read"
        assert env.data["file_path"] == "/tmp/test.txt"

    def test_factory_agent_output(self):
        env = EventEnvelope.agent_output(
            agent_id="test_agent",
            trace_id="trace-123",
            output="result output",
            summary="short summary",
        )
        assert env.type == "agent_output"
        assert env.data["output"] == "result output"
        assert env.data["summary"] == "short summary"

    def test_factory_agent_done(self):
        env = EventEnvelope.agent_done(
            agent_id="test_agent",
            trace_id="trace-123",
            result="final result",
        )
        assert env.type == "agent_done"
        assert env.status == "completed"

    def test_factory_final_response(self):
        env = EventEnvelope.final_response(
            agent_id="test_agent",
            trace_id="trace-123",
            response="final answer",
        )
        assert env.type == "final_response"
        assert env.data["response"] == "final answer"

    def test_factory_task_failed(self):
        env = EventEnvelope.task_failed(
            agent_id="test_agent",
            trace_id="trace-123",
            error_message="something went wrong",
            error_code="ERR_001",
        )
        assert env.type == "task_failed"
        assert env.status == "failed"
        assert env.data["error"] == "something went wrong"
        assert env.data["error_code"] == "ERR_001"

    def test_factory_task_timeout(self):
        env = EventEnvelope.task_timeout(
            agent_id="test_agent",
            trace_id="trace-123",
            timeout_seconds=60.0,
        )
        assert env.type == "task_timeout"
        assert env.status == "timeout"
        assert env.data["timeout_seconds"] == 60.0

    def test_factory_error(self):
        env = EventEnvelope.error(
            agent_id="test_agent",
            trace_id="trace-123",
            error_message="error occurred",
        )
        assert env.type == "error"
        assert env.status == "error"
        assert env.data["error"] == "error occurred"


class TestAgentEvent:
    def test_to_envelope(self):
        event = AgentEvent(
            event_type=AgentEventType.AGENT_START,
            agent_id="test_agent",
            trace_id="trace-123",
            data={"instruction": "test"},
            session_id="sess-456",
        )
        env = event.to_envelope(correlation_id="corr-789")
        assert env.type == "agent_start"
        assert env.agent == "test_agent"
        assert env.task_id == "trace-123"
        assert env.correlation_id == "corr-789"
        assert env.session_id == "sess-456"

    def test_to_dict(self):
        event = AgentEvent(
            event_type=AgentEventType.AGENT_START,
            agent_id="test_agent",
            trace_id="trace-123",
            data={"instruction": "test"},
            session_id="sess-456",
        )
        d = event.to_dict()
        assert d["event"] == "agent_start"
        assert d["agent_id"] == "test_agent"
        assert d["trace_id"] == "trace-123"
        assert d["instruction"] == "test"

    def test_to_envelope_status_mapping(self):
        for event_type, expected_status in [
            (AgentEventType.AGENT_START, "started"),
            (AgentEventType.AGENT_THINKING, "running"),
            (AgentEventType.AGENT_TOOL_CALL, "running"),
            (AgentEventType.AGENT_FILE_READ, "running"),
            (AgentEventType.AGENT_OUTPUT, "running"),
            (AgentEventType.AGENT_DONE, "completed"),
            (AgentEventType.FINAL_RESPONSE, "completed"),
            (AgentEventType.TASK_FAILED, "failed"),
            (AgentEventType.TASK_TIMEOUT, "timeout"),
            (AgentEventType.ERROR, "error"),
        ]:
            event = AgentEvent(
                event_type=event_type,
                agent_id="test",
                trace_id="trace",
            )
            env = event.to_envelope()
            assert env.status == expected_status, f"Failed for {event_type}"
