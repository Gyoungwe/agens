# providers/anthropic_provider.py

import os
import time
from typing import AsyncIterator, List
from anthropic import AsyncAnthropic
from providers.base_provider import BaseProvider, ChatMessage, ProviderResponse
from providers.base_provider import UsageInfo
from utils.retry import retry_with_backoff


class AnthropicProvider(BaseProvider):
    provider_id = "anthropic"
    name = "Anthropic Claude"

    def __init__(self, api_key: str = None, model: str = "claude-sonnet-4-5"):
        self.model = model
        self.client = AsyncAnthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))

    async def chat(
        self,
        messages: List[ChatMessage],
        system: str = "",
        max_tokens: int = 2048,
        **kwargs,
    ) -> ProviderResponse:
        start = time.time()

        async def do_request():
            return await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system or None,
                messages=[
                    {"role": m.role, "content": m.content}
                    for m in messages
                    if m.role != "system"
                ],
            )

        resp = await retry_with_backoff(
            do_request,
            max_retries=3,
            base_delay=0.5,
            max_delay=5.0,
        )
        return ProviderResponse(
            text=resp.content[0].text,
            model=resp.model,
            usage=UsageInfo(
                input_tokens=resp.usage.input_tokens,
                output_tokens=resp.usage.output_tokens,
                total_tokens=resp.usage.input_tokens + resp.usage.output_tokens,
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
        """Anthropic 流式响应"""

        async def get_stream_manager():
            return self.client.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                system=system or None,
                messages=[
                    {"role": m.role, "content": m.content}
                    for m in messages
                    if m.role != "system"
                ],
            )

        stream_manager = await retry_with_backoff(
            get_stream_manager,
            max_retries=3,
            base_delay=0.5,
            max_delay=5.0,
        )
        async with stream_manager as stream:
            async for text in stream.text_stream:
                yield text

    async def health_check(self) -> bool:
        try:
            resp = await self.chat(
                messages=[ChatMessage(role="user", content="hi")],
                max_tokens=10,
            )
            return bool(resp.text)
        except Exception:
            return False
