# evolution/request_generator.py

import json
import logging
import os

logger = logging.getLogger(__name__)

REQUEST_PROMPT = """你是一个 AI Agent，在执行任务时发现自己缺少某些技能。
请根据任务描述和缺失技能信息，生成一份正式的技能申请单。

输出 JSON 格式：
{
  "title":       "申请标题",
  "reason":      "申请原因（结合任务说明）",
  "benefit":     "预期收益",
  "risk":        "风险评估",
  "urgency":     "low|medium|high",
  "description": "详细说明"
}

只输出 JSON。"""


class RequestGenerator:
    """技能申请单生成器"""

    def __init__(self, provider_registry=None, provider=None):
        if provider_registry:
            self.provider = provider_registry.get()
        elif provider:
            self.provider = provider
        else:
            from providers.anthropic_provider import AnthropicProvider

            self.provider = AnthropicProvider()

    async def generate(
        self,
        agent_id: str,
        skill_id: str,
        instruction: str,
        reason: str,
    ) -> dict:
        context = (
            f"Agent ID: {agent_id}\n"
            f"缺失技能: {skill_id}（{reason}）\n"
            f"当前任务: {instruction}"
        )

        from providers.base_provider import ChatMessage

        resp = await self.provider.chat(
            messages=[ChatMessage(role="user", content=context)],
            system=REQUEST_PROMPT,
            max_tokens=512,
        )
        raw = resp.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        try:
            request = json.loads(raw)
        except json.JSONDecodeError:
            request = {
                "title": f"{agent_id} 申请安装 {skill_id}",
                "reason": reason,
                "benefit": "完成当前任务",
                "risk": "低风险",
                "urgency": "medium",
                "description": instruction[:200],
            }

        request.update(
            {
                "agent_id": agent_id,
                "skill_id": skill_id,
                "instruction": instruction[:500],
            }
        )
        logger.info(
            f"📋 申请单已生成: [{agent_id}] → [{skill_id}] "
            f"紧急度: {request.get('urgency')}"
        )
        return request
