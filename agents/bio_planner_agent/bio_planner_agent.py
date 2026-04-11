# agents/bio_planner_agent/bio_planner_agent.py

from core.base_agent import BaseAgent


class BioPlannerAgent(BaseAgent):
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
            agent_id="bio_planner_agent",
            bus=bus,
            skills=["plan_pipeline", "summarize"],
            description="生信流程规划 Agent：拆解任务并产出执行计划",
            registry=registry,
            knowledge=knowledge,
            provider=provider,
            provider_registry=provider_registry,
            auto_installer=auto_installer,
            memory_store=memory_store,
        )

    async def execute(self, instruction: str, context: dict) -> str:
        skill_output = await self.use_skill("plan_pipeline", instruction, context)
        workflow_family = context.get("workflow_family") or context.get(
            "intent", {}
        ).get("system_inference", {}).get(
            "inferred_workflow_family", "bioinformatics-mvp"
        )

        # Retrieve relevant historical workflow retrospectives from knowledge base
        historical_ctx = ""
        if self._knowledge_base:
            try:
                scope_id = context.get("scope_id") if context else None
                results = await self._knowledge_base.search(
                    query=f"past {workflow_family} workflow retrospective lessons learned",
                    top_k=3,
                    topic="planning",
                    scope_id=scope_id,
                )
                if results:
                    entries = "\n".join(
                        f"- {r['text'][:300]}" for r in results if r.get("text")
                    )
                    historical_ctx = f"\n\n## 历史 Workflow 回顾\n请参考以下历史经验来优化当前计划：\n{entries}\n"
            except Exception:
                pass  # Non-blocking: knowledge retrieval failure shouldn't halt planning

        planning_instruction = (
            "你是生物信息学流程规划专家，输出严格 JSON PlanSpec。\n"
            "【重要】你的输出必须严格是一个合法的 JSON 对象，根对象使用以下 schema：\n"
            '{"workflow_family":"<str>","assay_type":"<str>","analysis_focus":"<str>",'
            '"confirmed_inputs":["<str>"],"confirmed_outputs":["<str>"],'
            '"stages":[{"name":"<str>","goal":"<str>","inputs":["<str>"],"outputs":["<str>"],'
            '"primary_risk":"<str>","rollback_note":"<str>?"}],'
            '"critical_notes":["<str>"],"fallback_strategy":"<str>"}\n'
            "不要输出任何 JSON 之外的内容，不要有 markdown 包裹，只输出纯 JSON。\n"
            "每个阶段名称必须是：planning / codegen / qc / report / evolution。\n"
            "confirmed_inputs 必须基于骨架的 required_inputs。\n"
            "confirmed_outputs 必须基于骨架的 confirmed_outputs 或 key_outputs。\n"
            "critical_notes 最多 2 条，每条不超过 20 字。\n\n"
            f"workflow_family：{workflow_family}\n"
            f"结构化骨架：{skill_output}"
            f"{historical_ctx}\n\n"
            f"用户任务：{instruction}"
        )
        return await self._execute_with_llm(planning_instruction, context)
