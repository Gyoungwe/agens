# agents/executor_agent/executor_agent.py

from core.base_agent import BaseAgent


class ExecutorAgent(BaseAgent):
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
            agent_id="executor_agent",
            bus=bus,
            skills=[
                "shell",
                "benchling_integration",
                "dnanexus_integration",
                "latchbio_integration",
                "modal",
            ],
            description="负责执行具体操作",
            registry=registry,
            knowledge=knowledge,
            provider=provider,
            provider_registry=provider_registry,
            auto_installer=auto_installer,
        )

    async def execute(self, instruction: str, context: dict) -> str:
        return await self._execute_with_llm(instruction, context)
