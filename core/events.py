# core/events.py
# Agent 事件定义 - 贯穿整个系统的标准事件类型

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
import uuid

from core.runtime_contract import RUNTIME_CONTRACT_VERSION


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
    统一事件结构（合并 AgentEvent + EventEnvelope）
    提供 to_sse() 方法直接输出 SSE 格式
    """

    contract_version: str = RUNTIME_CONTRACT_VERSION
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    session_id: Optional[str] = None
    namespace: str = ""
    correlation_id: str = ""
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    type: str = ""
    agent: str = ""
    status: str = "pending"
    meta: Dict[str, Any] = field(default_factory=dict)
    data: Dict[str, Any] = field(default_factory=dict)

    _status_map = {
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "contract_version": self.contract_version,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "namespace": self.namespace,
            "correlation_id": self.correlation_id,
            "created_at": self.created_at,
            "type": self.type,
            "agent": self.agent,
            "status": self.status,
            "meta": self.meta,
            "data": self.data,
        }

    def to_sse(self) -> str:
        """输出 SSE 格式字符串"""
        data = self.to_dict()
        lines = [f"event: {self.type}"]
        for key, value in data.items():
            if key == "data":
                continue
            lines.append(f"{key}: {value}")
        if self.data:
            lines.append(f"data: {self.data}")
        return "\n".join(lines) + "\n\n"

    @classmethod
    def agent_start(
        cls,
        agent_id: str,
        trace_id: str,
        instruction: str,
        session_id: str = None,
        namespace: str = "",
    ):
        return cls(
            event_id=str(uuid.uuid4()),
            task_id=trace_id,
            session_id=session_id,
            namespace=namespace,
            correlation_id=trace_id,
            created_at=datetime.now().timestamp(),
            type=AgentEventType.AGENT_START.value,
            agent=agent_id,
            status="started",
            meta={"trace_id": trace_id},
            data={"instruction": instruction[:100], "status": "started"},
        )

    @classmethod
    def agent_thinking(
        cls,
        agent_id: str,
        trace_id: str,
        message: str = "",
        session_id: str = None,
        namespace: str = "",
    ):
        return cls(
            event_id=str(uuid.uuid4()),
            task_id=trace_id,
            session_id=session_id,
            namespace=namespace,
            correlation_id=trace_id,
            created_at=datetime.now().timestamp(),
            type=AgentEventType.AGENT_THINKING.value,
            agent=agent_id,
            status="running",
            meta={"trace_id": trace_id},
            data={"message": message or "LLM reasoning in progress..."},
        )

    @classmethod
    def agent_tool_call(
        cls,
        agent_id: str,
        trace_id: str,
        skill_id: str,
        instruction: str,
        session_id: str = None,
        namespace: str = "",
    ):
        return cls(
            event_id=str(uuid.uuid4()),
            task_id=trace_id,
            session_id=session_id,
            namespace=namespace,
            correlation_id=trace_id,
            created_at=datetime.now().timestamp(),
            type=AgentEventType.AGENT_TOOL_CALL.value,
            agent=agent_id,
            status="running",
            meta={"trace_id": trace_id},
            data={"skill_id": skill_id, "instruction": instruction[:100]},
        )

    @classmethod
    def agent_file_read(
        cls,
        agent_id: str,
        trace_id: str,
        file_path: str,
        session_id: str = None,
        namespace: str = "",
    ):
        return cls(
            event_id=str(uuid.uuid4()),
            task_id=trace_id,
            session_id=session_id,
            namespace=namespace,
            correlation_id=trace_id,
            created_at=datetime.now().timestamp(),
            type=AgentEventType.AGENT_FILE_READ.value,
            agent=agent_id,
            status="running",
            meta={"trace_id": trace_id},
            data={"file_path": file_path},
        )

    @classmethod
    def agent_output(
        cls,
        agent_id: str,
        trace_id: str,
        output: str,
        summary: str = "",
        session_id: str = None,
        namespace: str = "",
    ):
        return cls(
            event_id=str(uuid.uuid4()),
            task_id=trace_id,
            session_id=session_id,
            namespace=namespace,
            correlation_id=trace_id,
            created_at=datetime.now().timestamp(),
            type=AgentEventType.AGENT_OUTPUT.value,
            agent=agent_id,
            status="running",
            meta={"trace_id": trace_id},
            data={"output": output[:500], "summary": summary or output[:100]},
        )

    @classmethod
    def agent_done(
        cls,
        agent_id: str,
        trace_id: str,
        result: str,
        session_id: str = None,
        namespace: str = "",
    ):
        return cls(
            event_id=str(uuid.uuid4()),
            task_id=trace_id,
            session_id=session_id,
            namespace=namespace,
            correlation_id=trace_id,
            created_at=datetime.now().timestamp(),
            type=AgentEventType.AGENT_DONE.value,
            agent=agent_id,
            status="completed",
            meta={"trace_id": trace_id},
            data={"result": result[:200], "status": "completed"},
        )

    @classmethod
    def final_response(
        cls,
        agent_id: str,
        trace_id: str,
        response: str,
        session_id: str = None,
        namespace: str = "",
    ):
        return cls(
            event_id=str(uuid.uuid4()),
            task_id=trace_id,
            session_id=session_id,
            namespace=namespace,
            correlation_id=trace_id,
            created_at=datetime.now().timestamp(),
            type=AgentEventType.FINAL_RESPONSE.value,
            agent=agent_id,
            status="completed",
            meta={"trace_id": trace_id},
            data={"response": response},
        )

    @classmethod
    def task_failed(
        cls,
        agent_id: str,
        trace_id: str,
        error_message: str,
        session_id: str = None,
        error_code: str = "UNKNOWN",
        namespace: str = "",
    ):
        return cls(
            event_id=str(uuid.uuid4()),
            task_id=trace_id,
            session_id=session_id,
            namespace=namespace,
            correlation_id=trace_id,
            created_at=datetime.now().timestamp(),
            type=AgentEventType.TASK_FAILED.value,
            agent=agent_id,
            status="failed",
            meta={"trace_id": trace_id},
            data={
                "error": error_message,
                "error_code": error_code,
                "status": "failed",
            },
        )

    @classmethod
    def task_timeout(
        cls,
        agent_id: str,
        trace_id: str,
        timeout_seconds: float,
        session_id: str = None,
        namespace: str = "",
    ):
        return cls(
            event_id=str(uuid.uuid4()),
            task_id=trace_id,
            session_id=session_id,
            namespace=namespace,
            correlation_id=trace_id,
            created_at=datetime.now().timestamp(),
            type=AgentEventType.TASK_TIMEOUT.value,
            agent=agent_id,
            status="timeout",
            meta={"trace_id": trace_id},
            data={
                "timeout_seconds": timeout_seconds,
                "status": "timeout",
            },
        )

    @classmethod
    def error(
        cls,
        agent_id: str,
        trace_id: str,
        error_message: str,
        session_id: str = None,
        namespace: str = "",
    ):
        return cls(
            event_id=str(uuid.uuid4()),
            task_id=trace_id,
            session_id=session_id,
            namespace=namespace,
            correlation_id=trace_id,
            created_at=datetime.now().timestamp(),
            type=AgentEventType.ERROR.value,
            agent=agent_id,
            status="error",
            meta={"trace_id": trace_id},
            data={"error": error_message},
        )


@dataclass
class AgentEvent:
    """
    Agent 事件（兼容旧接口）
    请优先使用 EventEnvelope 的工厂方法
    """

    event_type: AgentEventType
    agent_id: str
    trace_id: str
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    data: Dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None
    namespace: str = ""
    contract_version: str = RUNTIME_CONTRACT_VERSION

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
            contract_version=self.contract_version,
            task_id=self.trace_id,
            session_id=self.session_id,
            namespace=self.namespace,
            correlation_id=correlation_id or self.trace_id,
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
            "contract_version": self.contract_version,
            "agent_id": self.agent_id,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "namespace": self.namespace,
            **self.data,
        }
