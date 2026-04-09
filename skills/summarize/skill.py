# skills/summarize/skill.py

import os
from core.base_skill import BaseSkill, SkillInput
from typing import Any


class Skill(BaseSkill):

    skill_id    = "summarize"
    name        = "内容摘要"
    description = "对长文本进行结构化摘要提炼"
    version     = "1.0.0"
    tags        = ["nlp", "summary", "text"]

    def __init__(self):
        super().__init__()
        from providers.anthropic_provider import AnthropicProvider
        self.provider = AnthropicProvider()

    async def run(self, input_data: SkillInput) -> Any:
        from providers.base_provider import ChatMessage
        resp = await self.provider.chat(
            messages=[ChatMessage(role="user", content=f"请摘要以下内容：\n\n{input_data.instruction}")],
            system="你是一个摘要专家，提炼核心要点，输出结构清晰的摘要。",
            max_tokens=1024,
        )
        return resp.text
