# agents/research_agent/research_agent.py

from core.base_agent import BaseAgent


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
        return await self._execute_with_llm(instruction, context)
