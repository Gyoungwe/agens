# agents/research_agent/research_agent.py

import logging
import os
import re

from core.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ResearchAgent(BaseAgent):
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
            agent_id="research_agent",
            bus=bus,
            skills=["web_search", "summarize", "langchain_search"],
            description="负责信息搜集、分析、调研",
            registry=registry,
            knowledge=knowledge,
            provider=provider,
            provider_registry=provider_registry,
            auto_installer=auto_installer,
            memory_store=memory_store,
        )

    def _needs_search(self, query: str) -> bool:
        search_patterns = [
            r"天气",
            r"搜索",
            r"查询",
            r"最新",
            r"新闻",
            r"今天",
            r"search",
            r"weather",
            r"news",
            r"latest",
            r"find",
            r"什么是",
            r"how to",
            r"what is",
            r"why",
            r"who",
            r"哪个",
            r"怎么样",
            r"如何",
            r"哪款",
            r"哪个好",
            r"多少",
            r"哪里",
            r"\?",
        ]
        return any(re.search(p, query.lower()) for p in search_patterns)

    async def execute(self, instruction: str, context: dict) -> str:
        merged_context = dict(context or {})

        if self._needs_search(instruction) and self.registry:
            try:
                skill_to_use = (
                    "langchain_search"
                    if os.getenv("ENABLE_LANGCHAIN_TOOL_BRIDGE", "false").lower()
                    == "true"
                    else "web_search"
                )

                skill_output = await self.use_skill(
                    skill_to_use,
                    instruction=instruction,
                    context={"query": instruction, "max_results": 5},
                )
                if skill_output:
                    merged_context["search_result"] = skill_output
                    logger.info(
                        f"[research_agent] Search skill [{skill_to_use}] returned result"
                    )
            except Exception as e:
                logger.warning(
                    f"[research_agent] {skill_to_use} failed: {e}, falling back to LLM only"
                )

        result = await self._execute_with_llm(instruction, merged_context)

        # 自动将 research 结果凝练后写入本地知识库，供后续 chat research 检索复用
        if self.knowledge and not merged_context.get("skip_knowledge_persist"):
            try:
                source_items = []
                raw_sources = merged_context.get("search_result")
                if isinstance(raw_sources, dict):
                    for item in raw_sources.get("results", [])[:8]:
                        if isinstance(item, dict):
                            src = item.get("url") or item.get("source") or ""
                            if src:
                                source_items.append(str(src))

                condensed = (
                    f"[Research Memory]\n"
                    f"Query: {instruction[:300]}\n"
                    f"Key Findings:\n{str(result)[:2200]}\n"
                    + (
                        f"Sources:\n" + "\n".join(f"- {s}" for s in source_items)
                        if source_items
                        else ""
                    )
                )

                await self.knowledge.add(
                    text=condensed,
                    agent_ids=["global", "research_agent"],
                    topic="research",
                    source="research_agent",
                    metadata={
                        "kind": "research_condensed",
                        "query": instruction[:500],
                        "source_count": len(source_items),
                    },
                    scope_id=merged_context.get("scope_id"),
                )
            except Exception as e:
                logger.warning(f"[research_agent] persist knowledge failed: {e}")

        return result
