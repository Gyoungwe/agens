# agents/bio_evolution_agent/bio_evolution_agent.py

from core.base_agent import BaseAgent


class BioEvolutionAgent(BaseAgent):
    def __init__(
        self,
        bus,
        provider=None,
        registry=None,
        knowledge=None,
        provider_registry=None,
        auto_installer=None,
        memory_store=None,
    ):
        super().__init__(
            agent_id="bio_evolution_agent",
            bus=bus,
            skills=["evolve_strategy", "summarize"],
            description="生信进化 Agent：总结经验并提出下一轮优化策略",
            registry=registry,
            knowledge=knowledge,
            provider=provider,
            provider_registry=provider_registry,
            auto_installer=auto_installer,
            memory_store=memory_store,
        )

    async def execute(self, instruction: str, context: dict) -> str:
        skill_output = await self.use_skill("evolve_strategy", instruction, context)
        workflow_family = context.get("workflow_family") or context.get(
            "runtime_context", {}
        ).get("workflow_stage", "bioinformatics-mvp")
        evolution_instruction = (
            "你是生物信息学进化策略专家，输出严格 JSON EvolutionSpec。\n"
            "【重要】你的输出必须严格是一个合法的 JSON 对象，使用以下 schema：\n"
            '{"workflow_family":"<str>",'
            '"success_factors":["<str>"],"failure_patterns":["<str>"],'
            '"priority_improvements":[{"category":"success|failure|improvement|skill_gap",'
            '"description":"<str>","priority":"high|medium|low"}],'
            '"automated_capability_gaps":["<str>"],'
            '"recommended_template_updates":["<str>"]}\n'
            "不要输出任何 JSON 之外的内容，不要有 markdown 包裹，只输出纯 JSON。\n"
            "success_factors 和 failure_patterns 各最多 3 条。\n"
            "priority_improvements 最多 3 项，每项 description 不超过 30 字。\n"
            "automated_capability_gaps 最多 2 条，每条不超过 30 字。\n"
            "recommended_template_updates 最多 2 条，每条不超过 30 字。\n\n"
            f"workflow_family：{workflow_family}\n"
            f"骨架参考：{skill_output}\n\n"
            f"任务：{instruction}"
        )
        return await self._execute_with_llm(evolution_instruction, context)
