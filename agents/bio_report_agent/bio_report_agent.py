# agents/bio_report_agent/bio_report_agent.py

from core.base_agent import BaseAgent


class BioReportAgent(BaseAgent):
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
            agent_id="bio_report_agent",
            bus=bus,
            skills=["compile_bio_report", "summarize", "format"],
            description="生信汇报 Agent：汇总分析结果并生成结构化报告",
            registry=registry,
            knowledge=knowledge,
            provider=provider,
            provider_registry=provider_registry,
            auto_installer=auto_installer,
            memory_store=memory_store,
        )

    async def execute(self, instruction: str, context: dict) -> str:
        skill_output = await self.use_skill("compile_bio_report", instruction, context)
        workflow_family = context.get("workflow_family") or context.get(
            "runtime_context", {}
        ).get("workflow_stage", "bioinformatics-mvp")
        report_instruction = (
            "你是生物信息学报告专家，输出严格 JSON ReportSpec。\n"
            "【重要】你的输出必须严格是一个合法的 JSON 对象，使用以下 schema：\n"
            '{"title":"<str>","workflow_family":"<str>",'
            '"sections":[{"heading":"<str>","key_points":["<str>"],"caveat":"<str>?"}],'
            '"reproducibility_summary":"<str>","limitations":["<str>"],"next_steps":["<str>"]}\n'
            "不要输出任何 JSON 之外的内容，不要有 markdown 包裹，只输出纯 JSON。\n"
            "每个 section 的 heading 必须是：executive_summary / key_findings / quality_assessment / limitations / next_steps。\n"
            "key_points 每节最多 3 条。\n"
            "limitations 最多 2 条，每条不超过 30 字。\n"
            "next_steps 最多 2 条，每条不超过 30 字。\n\n"
            f"workflow_family：{workflow_family}\n"
            f"骨架参考：{skill_output}\n\n"
            f"任务：{instruction}"
        )
        return await self._execute_with_llm(report_instruction, context)
