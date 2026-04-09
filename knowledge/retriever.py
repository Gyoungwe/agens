# knowledge/retriever.py

from knowledge.knowledge_base import KnowledgeBase


class Retriever:
    """检索器：Agent 调用的高层接口"""

    def __init__(self, kb: KnowledgeBase):
        self.kb = kb

    async def get_context(
        self,
        query:    str,
        agent_id: str,
        topic:    str = None,
        top_k:    int = 3,
    ) -> str:
        """检索并格式化为可直接拼入 prompt 的字符串"""
        results = await self.kb.search(
            query    = query,
            agent_id = agent_id,
            topic    = topic,
            top_k    = top_k,
        )

        if not results:
            return ""

        lines = ["【相关知识库内容】"]
        for i, r in enumerate(results, 1):
            lines.append(
                f"{i}. [相关度 {r['score']}] {r['text']}"
                + (f"\n   来源: {r['source']}" if r["source"] else "")
            )

        return "\n".join(lines)
