# providers/openai_provider.py

import os
import time
from typing import AsyncIterator, List
from openai import AsyncOpenAI
from providers.base_provider import (
    BaseProvider,
    ChatMessage,
    ProviderResponse,
    UsageInfo,
)
from utils.retry import retry_with_backoff


class OpenAIProvider(BaseProvider):
    """
    兼容所有 OpenAI-Compatible 接口：
    OpenAI / DeepSeek / Moonshot / Ollama / SiliconFlow 等
    """

    provider_id = "openai"
    name = "OpenAI Compatible"

    def __init__(
        self,
        api_key: str = None,
        model: str = "gpt-4o",
        base_url: str = None,
        max_retries: int = 3,
        timeout: float = 120.0,
    ):
        self.model = model
        self.client = AsyncOpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url or os.getenv("OPENAI_BASE_URL"),
            max_retries=max_retries,
            timeout=timeout,
        )

    async def chat(
        self,
        messages: List[ChatMessage],
        system: str = "",
        max_tokens: int = 2048,
        **kwargs,
    ) -> ProviderResponse:
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs += [{"role": m.role, "content": m.content} for m in messages]

        start = time.time()

        async def do_request():
            return await self.client.chat.completions.create(
                model=self.model,
                messages=msgs,
                max_tokens=max_tokens,
            )

        resp = await retry_with_backoff(
            do_request,
            max_retries=3,
            base_delay=0.5,
            max_delay=5.0,
        )
        usage = resp.usage
        return ProviderResponse(
            text=resp.choices[0].message.content,
            model=resp.model,
            finish_reason=resp.choices[0].finish_reason or "stop",
            usage=UsageInfo(
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
            ),
            latency_ms=int((time.time() - start) * 1000),
            provider=self.provider_id,
        )

    async def chat_stream(
        self,
        messages: List[ChatMessage],
        system: str = "",
        max_tokens: int = 2048,
        **kwargs,
    ) -> AsyncIterator[str]:
        """OpenAI 兼容流式响应"""
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs += [{"role": m.role, "content": m.content} for m in messages]

        async def do_stream_request():
            return await self.client.chat.completions.create(
                model=self.model,
                messages=msgs,
                max_tokens=max_tokens,
                stream=True,
            )

        stream = await retry_with_backoff(
            do_stream_request,
            max_retries=3,
            base_delay=0.5,
            max_delay=5.0,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def health_check(self) -> bool:
        try:
            resp = await self.chat(
                messages=[ChatMessage(role="user", content="hi")],
                max_tokens=10,
            )
            return bool(resp.text)
        except Exception:
            return False
