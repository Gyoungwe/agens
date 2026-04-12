# core/message.py

from pydantic import BaseModel, Field
from typing import Any, Literal, Dict, Optional
from datetime import datetime
import uuid

from core.runtime_contract import RUNTIME_CONTRACT_VERSION


class Message(BaseModel):
    """
    Agent 之间传递的标准消息格式。
    所有通信都通过这个结构体，不允许直接调用。
    """

    contract_version: str = RUNTIME_CONTRACT_VERSION
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    # 路由信息
    sender: str  # 发送方 agent_id
    recipient: str  # 接收方 agent_id，"*" 表示广播

    # 消息类型
    type: Literal[
        "task",  # 分配任务
        "result",  # 返回结果
        "error",  # 报告错误
        "status",  # 状态更新
        "skill_request",  # 申请新技能（自我进化）
        "knowledge_request",  # 申请知识（自我进化）
    ]

    # 内容
    payload: Dict[str, Any] = {}
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    correlation_id: str = ""
    namespace: Optional[str] = None


class TaskPayload(BaseModel):
    """type=task 时的 payload 结构"""

    contract_version: str = RUNTIME_CONTRACT_VERSION
    instruction: str  # 给 Agent 的具体指令
    context: dict = {}  # 上下文数据（前序结果等）
    priority: int = 5  # 1=最高, 10=最低


class ResultPayload(BaseModel):
    """type=result 时的 payload 结构"""

    contract_version: str = RUNTIME_CONTRACT_VERSION
    success: bool
    output: Any  # Agent 的输出内容
    summary: str = ""  # 一句话摘要
    metadata: dict = {}  # 附加信息（耗时、token 数等）


class ErrorPayload(BaseModel):
    """type=error 时的 payload 结构"""

    contract_version: str = RUNTIME_CONTRACT_VERSION
    error_type: str
    message: str
    retryable: bool = False  # 是否可以重试


class ChatMessage(BaseModel):
    """
    聊天消息格式
    用于上下文管理和历史记录
    """

    role: str  # "user", "assistant", "system"
    content: str
    name: str = ""  # 可选，Agent 名称
    metadata: Dict[str, Any] = {}
