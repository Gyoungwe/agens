# providers/anthropic_provider.py

import os
from typing import AsyncIterator, List
from anthropic import AsyncAnthropic
from providers.base_provider import BaseProvider, ChatMessage, ProviderResponse


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
        resp = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system or None,
            messages=[
                {"role": m.role, "content": m.content}
                for m in messages
                if m.role != "system"
            ],
        )
        return ProviderResponse(
            text=resp.content[0].text,
            model=resp.model,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
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
        async with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=system or None,
            messages=[
                {"role": m.role, "content": m.content}
                for m in messages
                if m.role != "system"
            ],
        ) as stream:
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
