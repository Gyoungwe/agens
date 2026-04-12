from core.base_skill import BaseSkill, SkillInput
from typing import Any


class Skill(BaseSkill):
    async def run(self, input_data: SkillInput) -> Any:
        query = input_data.instruction
        return {
            "query": query,
            "results": [
                {
                    "title": f"搜索结果 1：关于「{query}」的分析",
                    "url": "https://example.com/1",
                    "snippet": f"这是关于 {query} 的详细介绍...",
                },
                {
                    "title": f"搜索结果 2：{query} 最新动态",
                    "url": "https://example.com/2",
                    "snippet": f"{query} 在近期有以下进展...",
                },
            ],
        }
