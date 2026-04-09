# providers/base_provider.py
"""
Base Provider 接口定义

所有 LLM Provider 必须实现此接口，确保返回结构统一
"""

from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Any, AsyncIterator, List, Optional


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str


class UsageInfo(BaseModel):
    """Token 使用量"""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class ProviderResponse(BaseModel):
    """
    Provider 标准响应结构

    所有 Provider 必须返回此格式，上层 Agent 不用写 provider-specific 分支
    """

    text: str = ""
    model: str = ""
    finish_reason: str = "stop"
    usage: UsageInfo = UsageInfo()
    latency_ms: int = 0
    provider: str = ""
    error_code: str = ""
    error_message: str = ""

    def is_error(self) -> bool:
        return bool(self.error_code or self.error_message)


class BaseProvider(ABC):
    """
    所有 LLM Provider 的基类。
    Agent 只依赖这个接口，不直接引用 SDK。

    可靠性特性:
    - 统一返回 ProviderResponse
    - 包含 finish_reason / usage / latency_ms / error_code
    """

    provider_id: str = ""
    name: str = ""
    model: str = ""

    @abstractmethod
    async def chat(
        self,
        messages: List[ChatMessage],
        system: str = "",
        max_tokens: int = 2048,
        **kwargs,
    ) -> ProviderResponse:
        """发送对话请求，返回统一格式"""
        ...

    async def chat_stream(
        self,
        messages: List[ChatMessage],
        system: str = "",
        max_tokens: int = 2048,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        流式对话，默认实现是非流式。
        子类应覆盖此方法提供真正的流式支持。
        """
        resp = await self.chat(messages, system, max_tokens, **kwargs)
        if resp.error_code:
            yield f"Error: {resp.error_message}"
        else:
            yield resp.text

    @abstractmethod
    async def health_check(self) -> bool:
        """检查 Provider 是否可用"""
        ...
