# agents/research_agent/research_agent.py

import logging
import os
import re
from typing import Any, Dict, List

from core.base_agent import BaseAgent
from core.events import EventEnvelope

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
            skills=[
                "web_search",
                "langchain_search",
                "database_lookup",
                "bgpt_paper_search",
                "literature_review",
                "citation_management",
                "summarize",
            ],
            description="负责信息搜集、分析、调研",
            registry=registry,
            knowledge=knowledge,
            provider=provider,
            provider_registry=provider_registry,
            auto_installer=auto_installer,
            memory_store=memory_store,
        )

    def _available_skill_ids(self) -> set[str]:
        if not self.registry:
            return set(self.skills)
        try:
            return {
                meta.skill_id
                for meta in self.registry.get_for_agent_metadata(self.agent_id)
            }
        except Exception:
            return set(self.skills)

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

    def _select_research_skills(self, instruction: str) -> List[str]:
        available = self._available_skill_ids()
        normalized = (instruction or "").lower()
        selected: List[str] = []

        def add(skill_id: str):
            if skill_id in available and skill_id not in selected:
                selected.append(skill_id)

        if any(
            token in normalized
            for token in [
                "最新",
                "recent",
                "latest",
                "论文",
                "paper",
                "文献",
                "literature",
                "review",
                "综述",
            ]
        ):
            add("bgpt_paper_search")
            add("paper_lookup")
            add("literature_review")

        if any(
            token in normalized
            for token in [
                "database",
                "数据库",
                "gene",
                "protein",
                "pathway",
                "trial",
                "clinical",
                "variant",
                "药物",
                "基因",
                "蛋白",
                "通路",
            ]
        ):
            add("database_lookup")
            add("depmap")
            add("primekg")

        if any(
            token in normalized
            for token in ["citation", "doi", "pmid", "引用", "参考文献"]
        ):
            add("citation_management")

        if any(
            token in normalized
            for token in ["web", "网页", "官网", "news", "新闻", "latest", "最新"]
        ):
            add("parallel_web")

        if not selected:
            if os.getenv("ENABLE_LANGCHAIN_TOOL_BRIDGE", "false").lower() == "true":
                add("langchain_search")
            else:
                add("web_search")
            add("database_lookup")

        return selected[:3]

    def _explain_research_skill_selection(
        self, instruction: str, selected: List[str]
    ) -> str:
        normalized = (instruction or "").lower()
        reasons: List[str] = []

        if any(
            token in normalized
            for token in [
                "最新",
                "recent",
                "latest",
                "论文",
                "paper",
                "文献",
                "literature",
                "review",
                "综述",
            ]
        ):
            reasons.append("scholarly/latest-paper query")
        if any(
            token in normalized
            for token in [
                "database",
                "数据库",
                "gene",
                "protein",
                "pathway",
                "trial",
                "clinical",
                "variant",
                "药物",
                "基因",
                "蛋白",
                "通路",
            ]
        ):
            reasons.append("database/entity query")
        if any(
            token in normalized
            for token in ["citation", "doi", "pmid", "引用", "参考文献"]
        ):
            reasons.append("citation query")
        if any(
            token in normalized
            for token in ["web", "网页", "官网", "news", "新闻", "latest", "最新"]
        ):
            reasons.append("web/latest query")
        if not reasons:
            reasons.append("fallback to default web research")

        selected_text = ", ".join(selected) if selected else "none"
        return (
            f"Research skill selection: {selected_text} | reasons: {', '.join(reasons)}"
        )

    async def _collect_research_skill_outputs(self, instruction: str) -> Dict[str, Any]:
        collected: Dict[str, Any] = {}
        selected_skills = self._select_research_skills(instruction)
        self._emit(
            EventEnvelope.agent_thinking(
                agent_id=self.agent_id,
                trace_id=self._current_trace_id or "",
                message=self._explain_research_skill_selection(
                    instruction, selected_skills
                ),
                session_id=self._current_session_id,
                namespace=self._current_namespace,
            )
        )
        for skill_id in selected_skills:
            try:
                output = await self.use_skill(
                    skill_id,
                    instruction=instruction,
                    context={"query": instruction, "max_results": 5},
                )
                if output:
                    collected[skill_id] = output
                    logger.info(
                        f"[research_agent] Research skill [{skill_id}] returned result"
                    )
            except Exception as e:
                logger.warning(
                    f"[research_agent] {skill_id} failed: {e}, continuing with remaining research skills"
                )
        self._emit(
            EventEnvelope.agent_output(
                agent_id=self.agent_id,
                trace_id=self._current_trace_id or "",
                output=str(
                    {
                        "selected_skills": selected_skills,
                        "completed_skills": list(collected.keys()),
                    }
                ),
                summary="research_skill_selection",
                extra_data={
                    "selected_skills": selected_skills,
                    "completed_skills": list(collected.keys()),
                },
                session_id=self._current_session_id,
                namespace=self._current_namespace,
            )
        )
        return collected

    async def execute(self, instruction: str, context: dict) -> str:
        merged_context = dict(context or {})

        if self._needs_search(instruction) and self.registry:
            research_outputs = await self._collect_research_skill_outputs(instruction)
            if research_outputs:
                first_output = next(iter(research_outputs.values()))
                merged_context["search_result"] = first_output
                merged_context["research_skill_outputs"] = research_outputs
                merged_context["research_skill_order"] = list(research_outputs.keys())

        result = await self._execute_with_llm(instruction, merged_context)

        # 自动将 research 结果凝练后写入本地知识库，供后续 chat research 检索复用
        if self.knowledge and not merged_context.get("skip_knowledge_persist"):
            try:
                source_items = []
                raw_outputs = merged_context.get("research_skill_outputs") or {}
                source_candidates = [merged_context.get("search_result")] + list(
                    raw_outputs.values()
                )
                for raw_sources in source_candidates:
                    if isinstance(raw_sources, dict):
                        for item in raw_sources.get("results", [])[:8]:
                            if isinstance(item, dict):
                                src = (
                                    item.get("url")
                                    or item.get("source")
                                    or item.get("link")
                                    or ""
                                )
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
                    agent_ids=["research_agent"],
                    topic="research",
                    source="research_agent",
                    namespace="research_memory",
                    metadata={
                        "kind": "research_condensed",
                        "namespace": "research_memory",
                        "query": instruction[:500],
                        "source_count": len(source_items),
                    },
                    scope_id=merged_context.get("scope_id"),
                )
            except Exception as e:
                logger.warning(f"[research_agent] persist knowledge failed: {e}")

        return result
