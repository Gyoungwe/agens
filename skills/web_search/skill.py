# skills/web_search/skill.py

import os
from core.base_skill import BaseSkill, SkillInput
from typing import Any


class Skill(BaseSkill):
    """
    网页搜索技能。

    实际项目中接入 Tavily / SerpAPI / Bing Search API。
    """

    skill_id    = "web_search"
    name        = "网页搜索"
    description = "使用搜索引擎搜索互联网信息"
    version     = "1.0.0"
    tags        = ["search", "internet", "research"]

    async def run(self, input_data: SkillInput) -> Any:
        query = input_data.instruction

        # ── 真实接入示例 ──
        # from tavily import TavilyClient
        # client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        # results = client.search(query, max_results=5)
        # return results

        # ── 模拟返回 ──
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
            ]
        }
