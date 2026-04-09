# tests/test_message.py

import pytest
from core.message import Message, TaskPayload, ResultPayload, ErrorPayload, ChatMessage


class TestMessage:
    def test_message_creation(self):
        msg = Message(
            sender="agent1",
            recipient="agent2",
            type="task",
            payload={"instruction": "do something"},
        )
        assert msg.sender == "agent1"
        assert msg.recipient == "agent2"
        assert msg.type == "task"
        assert msg.id is not None
        assert msg.trace_id is not None

    def test_message_session_id(self):
        msg = Message(
            sender="agent1",
            recipient="agent2",
            type="task",
            payload={},
            session_id="session-123",
        )
        assert msg.session_id == "session-123"

    def test_message_correlation_id(self):
        msg = Message(
            sender="agent1",
            recipient="agent2",
            type="task",
            payload={},
            correlation_id="corr-456",
        )
        assert msg.correlation_id == "corr-456"

    def test_message_optional_fields_default(self):
        msg = Message(
            sender="agent1",
            recipient="agent2",
            type="task",
            payload={},
        )
        assert msg.session_id is None
        assert msg.correlation_id == ""

    def test_task_payload(self):
        payload = TaskPayload(
            instruction="test instruction",
            context={"key": "value"},
            priority=3,
        )
        assert payload.instruction == "test instruction"
        assert payload.context == {"key": "value"}
        assert payload.priority == 3

    def test_result_payload(self):
        payload = ResultPayload(
            success=True,
            output="test output",
            summary="summary",
            metadata={"tokens": 100},
        )
        assert payload.success is True
        assert payload.output == "test output"

    def test_error_payload(self):
        payload = ErrorPayload(
            error_type="TimeoutError",
            message="Request timed out",
            retryable=True,
        )
        assert payload.error_type == "TimeoutError"
        assert payload.retryable is True

    def test_chat_message(self):
        msg = ChatMessage(
            role="user",
            content="Hello",
            name="TestAgent",
            metadata={"source": "test"},
        )
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.name == "TestAgent"
