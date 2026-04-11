# agents/bio_qc_agent/bio_qc_agent.py

from core.base_agent import BaseAgent


class BioQCAgent(BaseAgent):
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
            agent_id="bio_qc_agent",
            bus=bus,
            skills=["qc_review", "summarize"],
            description="生信质检 Agent：检查流程输出与质量指标",
            registry=registry,
            knowledge=knowledge,
            provider=provider,
            provider_registry=provider_registry,
            auto_installer=auto_installer,
            memory_store=memory_store,
        )

    async def execute(self, instruction: str, context: dict) -> str:
        skill_output = await self.use_skill("qc_review", instruction, context)
        workflow_family = context.get("workflow_family") or context.get(
            "runtime_context", {}
        ).get("workflow_stage", "bioinformatics-mvp")
        qc_instruction = (
            "你是生物信息学质量审查员，输出严格 JSON QCSpec。\n"
            "【重要】你的输出必须严格是一个合法的 JSON 对象，使用以下 schema：\n"
            '{"workflow_family":"<str>","overall_pass":<bool>,'
            '"checks":[{"name":"<str>","threshold":"<str>","current_value":"<str>?",'
            '"status":"pass|warn|fail","recommendation":"<str>"}],'
            '"critical_failures":["<str>"],"recovery_suggestions":["<str>"]}\n'
            "不要输出任何 JSON 之外的内容，不要有 markdown 包裹，只输出纯 JSON。\n"
            "每个 check 的 status 必须是 pass / warn / fail 之一。\n"
            "critical_failures 仅列出 status 为 fail 的检查项名称。\n"
            "recovery_suggestions 最多 3 条，每条不超过 30 字。\n\n"
            f"workflow_family：{workflow_family}\n"
            f"骨架参考：{skill_output}\n\n"
            f"任务：{instruction}"
        )
        return await self._execute_with_llm(qc_instruction, context)
