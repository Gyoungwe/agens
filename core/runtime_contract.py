from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


SessionNamespace = Literal[
    "chat_session",
    "research_session",
    "workflow_session",
    "channel_session",
]

MemoryNamespace = Literal[
    "chat_memory",
    "research_memory",
    "workflow_memory",
    "shared_knowledge",
]

RuntimeNamespace = Literal[
    "chat_runtime",
    "research_runtime",
    "workflow_runtime",
    "system_runtime",
]

DelegationMode = Literal[
    "direct_chat",
    "research",
    "clarify_first",
    "multi_agent",
]

RuntimeMessageType = Literal["task", "result", "error", "status"]
RuntimeContentFormat = Literal["text", "markdown", "json"]
RuntimeOutputType = Literal["final", "partial", "report", "error"]
RUNTIME_CONTRACT_VERSION = "1.0"


class RuntimeSessionContract(BaseModel):
    contract_version: str = RUNTIME_CONTRACT_VERSION
    session_id: str
    title: str
    status: Literal["active", "completed", "closed"] = "active"
    namespace: SessionNamespace
    created_at: str
    updated_at: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RuntimeMessageContract(BaseModel):
    contract_version: str = RUNTIME_CONTRACT_VERSION
    id: str
    created_at: str
    sender: str
    recipient: str
    type: RuntimeMessageType
    trace_id: str
    session_id: Optional[str] = None
    correlation_id: str = ""
    namespace: Optional[RuntimeNamespace] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class RuntimeTaskPayloadContract(BaseModel):
    contract_version: str = RUNTIME_CONTRACT_VERSION
    instruction: str
    context: Dict[str, Any] = Field(default_factory=dict)
    priority: int = 5


class RuntimeResultPayloadContract(BaseModel):
    contract_version: str = RUNTIME_CONTRACT_VERSION
    success: bool
    output: Any
    summary: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RuntimeMemoryRecordContract(BaseModel):
    contract_version: str = RUNTIME_CONTRACT_VERSION
    id: str
    text: str
    owner: str = ""
    source: str = ""
    created_at: str = ""
    scope_id: Optional[str] = None
    namespace: MemoryNamespace
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RuntimeEventContract(BaseModel):
    contract_version: str = RUNTIME_CONTRACT_VERSION
    event_id: str
    task_id: str
    session_id: Optional[str] = None
    correlation_id: str = ""
    created_at: float
    type: str
    agent: str
    status: str
    namespace: Optional[RuntimeNamespace] = None
    meta: Dict[str, Any] = Field(default_factory=dict)
    data: Dict[str, Any] = Field(default_factory=dict)


class RuntimeCitationContract(BaseModel):
    contract_version: str = RUNTIME_CONTRACT_VERSION
    text: str
    type: Literal["paper", "website", "other"] = "other"
    link: Optional[str] = None


class RuntimeOutputContract(BaseModel):
    contract_version: str = RUNTIME_CONTRACT_VERSION
    session_id: Optional[str] = None
    trace_id: Optional[str] = None
    namespace: RuntimeNamespace
    output_type: RuntimeOutputType = "final"
    content: str
    content_format: RuntimeContentFormat = "text"
    summary_format: Optional[Literal["text", "json"]] = None
    citations: List[RuntimeCitationContract] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RuntimeWorkflowBoundaryContract(BaseModel):
    """Workflow-specific structured contracts remain internal runtime artifacts."""

    contract_version: str = RUNTIME_CONTRACT_VERSION
    workflow_family: str = "bioinformatics-mvp"
    intent_contract: str = "WorkflowIntentSpec"
    plan_contract: str = "WorkflowPlanSpec"
    stage_contract: str = "WorkflowStageSpec"
    report_contract: str = "ReportSpec"
    evolution_contract: str = "EvolutionSpec"


class RuntimeDelegationDecisionContract(BaseModel):
    contract_version: str = RUNTIME_CONTRACT_VERSION
    mode: DelegationMode
    selected_agents: List[str] = Field(default_factory=list)
    reason: str = ""
    recommendation: str = ""
    clarification_question: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
