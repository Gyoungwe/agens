# agents/bio_code_agent/bio_code_agent.py

from core.base_agent import BaseAgent


class BioCodeAgent(BaseAgent):
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
            agent_id="bio_code_agent",
            bus=bus,
            skills=["generate_bio_code", "shell"],
            description="生信代码 Agent：生成 pipeline 脚本与命令",
            registry=registry,
            knowledge=knowledge,
            provider=provider,
            provider_registry=provider_registry,
            auto_installer=auto_installer,
            memory_store=memory_store,
        )

    async def execute(self, instruction: str, context: dict) -> str:
        skill_output = await self.use_skill("generate_bio_code", instruction, context)
        workflow_family = context.get("workflow_family") or context.get(
            "runtime_context", {}
        ).get("workflow_stage", "bioinformatics-mvp")
        coding_instruction = (
            "你是生物信息学工程师，输出严格 JSON PipelineArtifactSpec。\n"
            "【重要】你的输出必须严格是一个合法的 JSON 对象，使用以下 schema：\n"
            '{"engine":"<str>","workflow_family":"<str>","assay_type":"<str>",'
            '"params":{"<param_name>":"<param_value>"},'
            '"processes":[{"name":"<str>","tool":"<str>","input":"<str>","output":"<str>","description":"<str>"}],'
            '"nextflow_script":"<str>","snakemake_script":"<str>","entrypoint":"<str>"}\n'
            "不要输出任何 JSON 之外的内容，不要有 markdown 包裹，只输出纯 JSON。\n"
            "nextflow_script 必须是完整可运行的 Nextflow DSL2 代码（包含 params / process / workflow 块），"
            "包含所有 processes，基于 skill_output 的 steps 和 tool 名称。\n"
            "params 必须包含 outdir，且 engine 必须是 'nextflow' 或 'snakemake'。\n"
            "processes 的 name/tool/input/output 必须与 nextflow_script 中的 process 定义一致。\n\n"
            f"workflow_family：{workflow_family}\n"
            f"模板骨架：{skill_output}\n\n"
            f"任务：{instruction}"
        )
        return await self._execute_with_llm(coding_instruction, context)
