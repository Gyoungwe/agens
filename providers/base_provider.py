# providers/base_provider.py

from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Any, AsyncIterator, List


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str


class ProviderResponse(BaseModel):
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    provider: str = ""


class BaseProvider(ABC):
    """
    所有 LLM Provider 的基类。
    Agent 只依赖这个接口，不直接引用 SDK。
    """

    provider_id: str = ""
    name: str = ""

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
        yield resp.text

    @abstractmethod
    async def health_check(self) -> bool:
        """检查 Provider 是否可用"""
        ...
