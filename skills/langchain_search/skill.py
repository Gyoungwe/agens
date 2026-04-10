from core.base_skill import BaseSkill, SkillInput
from integrations.langchain_bridge import run_search


class Skill(BaseSkill):
    skill_id = "langchain_search"
    name = "LangChain Web Search"
    description = "Search web content via LangChain DuckDuckGo with fallback"
    version = "0.02"
    author = "system"
    tags = ["langchain", "search", "web"]

    async def run(self, input_data: SkillInput):
        query = input_data.context.get("query") or input_data.instruction
        max_results = int(input_data.context.get("max_results", 5))
        return await run_search(query=query, max_results=max_results)
