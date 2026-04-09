# core/events.py
# Agent 事件定义 - 贯穿整个系统的标准事件类型

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class AgentEventType(str, Enum):
    AGENT_START = "agent_start"
    AGENT_THINKING = "agent_thinking"
    AGENT_TOOL_CALL = "agent_tool_call"
    AGENT_FILE_READ = "agent_file_read"
    AGENT_OUTPUT = "agent_output"
    AGENT_DONE = "agent_done"
    FINAL_RESPONSE = "final_response"
    ERROR = "error"


@dataclass
class AgentEvent:
    """Agent 事件数据结构"""

    event_type: AgentEventType
    agent_id: str
    trace_id: str
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    data: Dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None

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
