# core/events.py
# Agent 事件定义 - 贯穿整个系统的标准事件类型

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
import uuid


class AgentEventType(str, Enum):
    AGENT_START = "agent_start"
    AGENT_THINKING = "agent_thinking"
    AGENT_TOOL_CALL = "agent_tool_call"
    AGENT_FILE_READ = "agent_file_read"
    AGENT_OUTPUT = "agent_output"
    AGENT_DONE = "agent_done"
    FINAL_RESPONSE = "final_response"
    TASK_FAILED = "task_failed"
    TASK_TIMEOUT = "task_timeout"
    ERROR = "error"


@dataclass
class EventEnvelope:
    """
    所有事件的统一封装
    确保 SSE 前端、日志、调试接口共用同一 schema
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    session_id: Optional[str] = None
    correlation_id: str = ""
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    type: str = ""
    agent: str = ""
    status: str = "pending"
    meta: Dict[str, Any] = field(default_factory=dict)
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "correlation_id": self.correlation_id,
            "created_at": self.created_at,
            "type": self.type,
            "agent": self.agent,
            "status": self.status,
            "meta": self.meta,
            "data": self.data,
        }


@dataclass
class AgentEvent:
    """Agent 事件数据结构（兼容旧接口）"""

    event_type: AgentEventType
    agent_id: str
    trace_id: str
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    data: Dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None

    def to_envelope(self, correlation_id: str = "") -> EventEnvelope:
        """转换为统一事件封装"""
        status_map = {
            AgentEventType.AGENT_START: "started",
            AgentEventType.AGENT_THINKING: "running",
            AgentEventType.AGENT_TOOL_CALL: "running",
            AgentEventType.AGENT_FILE_READ: "running",
            AgentEventType.AGENT_OUTPUT: "running",
            AgentEventType.AGENT_DONE: "completed",
            AgentEventType.FINAL_RESPONSE: "completed",
            AgentEventType.TASK_FAILED: "failed",
            AgentEventType.TASK_TIMEOUT: "timeout",
            AgentEventType.ERROR: "error",
        }

        return EventEnvelope(
            event_id=str(uuid.uuid4()),
            task_id=self.trace_id,
            session_id=self.session_id,
            correlation_id=correlation_id,
            created_at=self.timestamp,
            type=self.event_type.value,
            agent=self.agent_id,
            status=status_map.get(self.event_type, "unknown"),
            meta={"trace_id": self.trace_id},
            data=self.data,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event": self.event_type.value,
            "agent_id": self.agent_id,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            **self.data,
        }

    @classmethod
    def agent_start(
        cls, agent_id: str, trace_id: str, instruction: str, session_id: str = None
    ):
        return cls(
            event_type=AgentEventType.AGENT_START,
            agent_id=agent_id,
            trace_id=trace_id,
            data={"instruction": instruction[:100], "status": "started"},
            session_id=session_id,
        )

    @classmethod
    def agent_thinking(
        cls, agent_id: str, trace_id: str, message: str = "", session_id: str = None
    ):
        return cls(
            event_type=AgentEventType.AGENT_THINKING,
            agent_id=agent_id,
            trace_id=trace_id,
            data={"message": message or "LLM reasoning in progress..."},
            session_id=session_id,
        )

    @classmethod
    def agent_tool_call(
        cls,
        agent_id: str,
        trace_id: str,
        skill_id: str,
        instruction: str,
        session_id: str = None,
    ):
        return cls(
            event_type=AgentEventType.AGENT_TOOL_CALL,
            agent_id=agent_id,
            trace_id=trace_id,
            data={"skill_id": skill_id, "instruction": instruction[:100]},
            session_id=session_id,
        )

    @classmethod
    def agent_file_read(
        cls, agent_id: str, trace_id: str, file_path: str, session_id: str = None
    ):
        return cls(
            event_type=AgentEventType.AGENT_FILE_READ,
            agent_id=agent_id,
            trace_id=trace_id,
            data={"file_path": file_path},
            session_id=session_id,
        )

    @classmethod
    def agent_output(
        cls,
        agent_id: str,
        trace_id: str,
        output: str,
        summary: str = "",
        session_id: str = None,
    ):
        return cls(
            event_type=AgentEventType.AGENT_OUTPUT,
            agent_id=agent_id,
            trace_id=trace_id,
            data={"output": output[:500], "summary": summary or output[:100]},
            session_id=session_id,
        )

    @classmethod
    def agent_done(
        cls, agent_id: str, trace_id: str, result: str, session_id: str = None
    ):
        return cls(
            event_type=AgentEventType.AGENT_DONE,
            agent_id=agent_id,
            trace_id=trace_id,
            data={"result": result[:200], "status": "completed"},
            session_id=session_id,
        )

    @classmethod
    def final_response(
        cls, agent_id: str, trace_id: str, response: str, session_id: str = None
    ):
        return cls(
            event_type=AgentEventType.FINAL_RESPONSE,
            agent_id=agent_id,
            trace_id=trace_id,
            data={"response": response},
            session_id=session_id,
        )

    @classmethod
    def task_failed(
        cls,
        agent_id: str,
        trace_id: str,
        error_message: str,
        session_id: str = None,
        error_code: str = "UNKNOWN",
    ):
        return cls(
            event_type=AgentEventType.TASK_FAILED,
            agent_id=agent_id,
            trace_id=trace_id,
            data={
                "error": error_message,
                "error_code": error_code,
                "status": "failed",
            },
            session_id=session_id,
        )

    @classmethod
    def task_timeout(
        cls,
        agent_id: str,
        trace_id: str,
        timeout_seconds: float,
        session_id: str = None,
    ):
        return cls(
            event_type=AgentEventType.TASK_TIMEOUT,
            agent_id=agent_id,
            trace_id=trace_id,
            data={
                "timeout_seconds": timeout_seconds,
                "status": "timeout",
            },
            session_id=session_id,
        )

    @classmethod
    def error(
        cls, agent_id: str, trace_id: str, error_message: str, session_id: str = None
    ):
        return cls(
            event_type=AgentEventType.ERROR,
            agent_id=agent_id,
            trace_id=trace_id,
            data={"error": error_message},
            session_id=session_id,
        )
