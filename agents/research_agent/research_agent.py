# agents/research_agent/research_agent.py

import logging
import os

from core.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ResearchAgent(BaseAgent):
    def __init__(
        self,
        bus,
        provider=None,
        registry=None,
        knowledge=None,
        provider_registry=None,
        auto_installer=None,
    ):
        super().__init__(
            agent_id="research_agent",
            bus=bus,
            skills=["web_search", "summarize"],
            description="负责信息搜集、分析、调研",
            registry=registry,
            knowledge=knowledge,
            provider=provider,
            provider_registry=provider_registry,
            auto_installer=auto_installer,
        )

    async def execute(self, instruction: str, context: dict) -> str:
        merged_context = dict(context or {})

        if os.getenv("ENABLE_LANGCHAIN_TOOL_BRIDGE", "false").lower() == "true":
            try:
                skill_output = await self.use_skill(
                    "langchain_search",
                    instruction=instruction,
                    context={"query": instruction, "max_results": 5},
                )
                if getattr(skill_output, "success", False):
                    merged_context["langchain_search"] = skill_output.result
            except Exception as e:
                logger.warning(f"[research_agent] langchain_search degraded: {e}")

        return await self._execute_with_llm(instruction, merged_context)
