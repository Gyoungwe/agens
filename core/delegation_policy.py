from typing import List, Optional

from core.runtime_contract import (
    RuntimeDelegationDecisionContract,
)


RESEARCH_MARKERS = [
    "research",
    "search",
    "paper",
    "literature",
    "survey",
    "evidence",
    "latest",
    "recent",
    "citation",
    "citations",
    "doi",
    "pmid",
    "method",
    "methods",
    "approach",
    "论文",
    "研究",
    "检索",
    "文献",
    "证据",
    "最新",
    "近年",
    "近年来",
    "引用",
    "参考文献",
    "方法",
    "最新论文",
]

FORCE_RESEARCH_PREFIXES = [
    "[research]",
    "research:",
    "research：",
    "检索:",
    "检索：",
    "研究:",
    "研究：",
]

RESEARCH_PATTERNS = [
    "如何处理",
    "怎么处理",
    "处理方法",
    "最新方法",
    "最新进展",
    "最新论文",
    "相关论文",
    "相关文献",
    "综述",
    "review",
    "state of the art",
]

BIO_MARKERS = [
    "rna-seq",
    "rna_seq",
    "wgs",
    "wes",
    "metagenomics",
    "atac",
    "chip",
    "assembly",
    "fastq",
    "bam",
    "vcf",
    "gtf",
    "fasta",
    "nextflow",
    "snakemake",
    "pipeline",
    "workflow",
    "生信",
    "生物信息",
    "差异表达",
    "变异检测",
    "质控",
    "qc",
]


def looks_like_research_query(text: str) -> bool:
    normalized = (text or "").lower()
    if any(normalized.startswith(prefix) for prefix in FORCE_RESEARCH_PREFIXES):
        return True
    return any(marker in normalized for marker in RESEARCH_MARKERS)


def strip_force_research_prefix(text: str) -> str:
    raw = text or ""
    normalized = raw.lower()
    for prefix in FORCE_RESEARCH_PREFIXES:
        if normalized.startswith(prefix):
            return raw[len(prefix) :].lstrip()
    return raw


def decide_delegation(
    user_input: str,
    available_agents: List[str],
    selected_agents: Optional[List[str]] = None,
    recommendation: Optional[str] = None,
    decision_reason: str = "",
) -> RuntimeDelegationDecisionContract:
    selected_agents = list(selected_agents or [])
    text = (user_input or "").lower()

    explicit_research = looks_like_research_query(text)
    heuristic_research = any(pattern in text for pattern in RESEARCH_PATTERNS)

    if (
        explicit_research or heuristic_research
    ) and "research_agent" in available_agents:
        research_agents = [
            agent_id
            for agent_id in ["research_agent", "writer_agent"]
            if agent_id in available_agents
        ]
        return RuntimeDelegationDecisionContract(
            mode="research",
            selected_agents=research_agents,
            reason=(
                "Explicit research intent detected; routing to research mode."
                if explicit_research
                else "Methods/literature-style query detected; routing to research mode."
            ),
            recommendation=recommendation or "",
        )

    if recommendation and any(marker in text for marker in BIO_MARKERS):
        return RuntimeDelegationDecisionContract(
            mode="clarify_first",
            selected_agents=selected_agents,
            reason="Workflow intent is underspecified; clarification is required before execution.",
            recommendation=recommendation,
            clarification_question=recommendation,
        )

    if selected_agents:
        return RuntimeDelegationDecisionContract(
            mode="multi_agent",
            selected_agents=selected_agents,
            reason=decision_reason
            or "Specialized workflow intent detected; using multi-agent collaboration.",
            recommendation=recommendation or "",
        )

    return RuntimeDelegationDecisionContract(
        mode="direct_chat",
        selected_agents=[],
        reason=decision_reason
        or "No explicit delegation intent detected; defaulting to direct chat.",
        recommendation=recommendation or "",
    )
