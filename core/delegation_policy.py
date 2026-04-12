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
    "论文",
    "研究",
    "检索",
    "文献",
    "证据",
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
    return any(marker in normalized for marker in RESEARCH_MARKERS)


def decide_delegation(
    user_input: str,
    available_agents: List[str],
    selected_agents: Optional[List[str]] = None,
    recommendation: Optional[str] = None,
    decision_reason: str = "",
) -> RuntimeDelegationDecisionContract:
    selected_agents = list(selected_agents or [])
    text = (user_input or "").lower()

    if looks_like_research_query(text) and "research_agent" in available_agents:
        research_agents = [
            agent_id
            for agent_id in ["research_agent", "writer_agent"]
            if agent_id in available_agents
        ]
        return RuntimeDelegationDecisionContract(
            mode="research",
            selected_agents=research_agents,
            reason="Research intent detected; routing to research mode.",
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
