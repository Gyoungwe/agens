from core.base_skill import BaseSkill, SkillInput
from integrations.langchain_bridge import run_search


class Skill(BaseSkill):
    async def run(self, input_data: SkillInput):
        query = input_data.context.get("query") or input_data.instruction
        max_results = int(input_data.context.get("max_results", 5))
        return await run_search(query=query, max_results=max_results)
