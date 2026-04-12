# agents/writer_agent/writer_agent.py

from core.base_agent import BaseAgent


class WriterAgent(BaseAgent):
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
            agent_id="writer_agent",
            bus=bus,
            skills=[
                "scientific_writing",
                "citation_management",
                "literature_review",
                "summarize",
            ],
            description="负责内容撰写、格式化、总结",
            registry=registry,
            knowledge=knowledge,
            provider=provider,
            provider_registry=provider_registry,
            auto_installer=auto_installer,
        )

    async def execute(self, instruction: str, context: dict) -> str:
        return await self._execute_with_llm(instruction, context)
