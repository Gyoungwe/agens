from typing import Dict, List, Optional, Literal

from pydantic import BaseModel, Field


class InputAsset(BaseModel):
    kind: str = "other"
    path: str
    sample_id: Optional[str] = None
    paired_end: Optional[bool] = None


class SampleSheetSpec(BaseModel):
    sample_count: int = 0
    groups: List[str] = Field(default_factory=list)
    has_control: Optional[bool] = None
    design_summary: Optional[str] = None


class ReferenceBundleSpec(BaseModel):
    genome: Optional[str] = None
    annotation: Optional[str] = None
    dbs: List[str] = Field(default_factory=list)


class ConstraintSpec(BaseModel):
    time_budget: Optional[str] = None
    compute_budget: Optional[str] = None
    privacy_level: Optional[Literal["low", "medium", "high"]] = None
    internet_allowed: Optional[bool] = None


class SystemInferenceSpec(BaseModel):
    inferred_assay_type: Optional[str] = None
    inferred_workflow_family: Optional[str] = None
    inferred_risks: List[str] = Field(default_factory=list)
    confidence: float = 0.0


class WorkflowIntentSpec(BaseModel):
    request_id: Optional[str] = None
    goal: str
    assay_type: str = "other"
    analysis_type: Optional[str] = None
    dataset: Optional[str] = None
    input_assets: List[InputAsset] = Field(default_factory=list)
    sample_sheet: Optional[SampleSheetSpec] = None
    reference_bundle: Optional[ReferenceBundleSpec] = None
    expected_outputs: List[str] = Field(default_factory=list)
    constraints: Optional[ConstraintSpec] = None
    system_inference: Optional[SystemInferenceSpec] = None
    fields_requiring_confirmation: List[str] = Field(default_factory=list)
    user_confirmed: bool = False


class ToolContractSpec(BaseModel):
    engine: Optional[str] = None
    entrypoint: Optional[str] = None


class WorkflowStageSpec(BaseModel):
    id: str
    name: str
    agent_id: Optional[str] = None
    kind: str = "analysis"
    depends_on: List[str] = Field(default_factory=list)
    inputs: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)
    approval_required: bool = False
    qc_gate: bool = False
    prompt_template: Optional[str] = None
    timeout_seconds: Optional[int] = None
    critical: bool = False
    knowledge_topic: Optional[str] = None
    tool_contract: Optional[ToolContractSpec] = None


class ProvenancePolicySpec(BaseModel):
    capture_inputs: bool = True
    capture_versions: bool = True
    capture_params: bool = True


class WorkflowPlanSpec(BaseModel):
    plan_id: Optional[str] = None
    intent_id: Optional[str] = None
    workflow_family: str = "bioinformatics-mvp"
    stages: List[WorkflowStageSpec] = Field(default_factory=list)
    provenance_policy: ProvenancePolicySpec = Field(
        default_factory=ProvenancePolicySpec
    )


class PlanStageArtifact(BaseModel):
    name: str
    goal: str
    inputs: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)
    primary_risk: str = "unknown"
    rollback_note: Optional[str] = None


class PlanSpec(BaseModel):
    """Planner agent structured output — replaces freeform planning text."""

    workflow_family: str = "bioinformatics-mvp"
    assay_type: str = "other"
    analysis_focus: str = ""
    confirmed_inputs: List[str] = Field(default_factory=list)
    confirmed_outputs: List[str] = Field(default_factory=list)
    stages: List[PlanStageArtifact] = Field(default_factory=list)
    critical_notes: List[str] = Field(default_factory=list)
    fallback_strategy: str = "retry_with_simpler_params"


class QCCheckItem(BaseModel):
    name: str
    threshold: str
    current_value: Optional[str] = None
    status: Literal["pass", "warn", "fail"] = "warn"
    recommendation: str = ""


class QCSpec(BaseModel):
    """QC agent structured output — replaces freeform QC review text."""

    workflow_family: str = "bioinformatics-mvp"
    overall_pass: bool = False
    checks: List[QCCheckItem] = Field(default_factory=list)
    critical_failures: List[str] = Field(default_factory=list)
    recovery_suggestions: List[str] = Field(default_factory=list)


class ReportSectionArtifact(BaseModel):
    heading: str
    key_points: List[str] = Field(default_factory=list)
    caveat: Optional[str] = None


class ReportSpec(BaseModel):
    """Report agent structured output — replaces freeform report text."""

    title: str = "Bioinformatics Analysis Report"
    workflow_family: str = "bioinformatics-mvp"
    sections: List[ReportSectionArtifact] = Field(default_factory=list)
    reproducibility_summary: str = ""
    limitations: List[str] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)


class EvolutionArtifact(BaseModel):
    category: Literal["success", "failure", "improvement", "skill_gap"]
    description: str
    priority: Literal["high", "medium", "low"] = "medium"


class EvolutionSpec(BaseModel):
    """Evolution agent structured output — replaces freeform retrospective text."""

    workflow_family: str = "bioinformatics-mvp"
    success_factors: List[str] = Field(default_factory=list)
    failure_patterns: List[str] = Field(default_factory=list)
    priority_improvements: List[EvolutionArtifact] = Field(default_factory=list)
    automated_capability_gaps: List[str] = Field(default_factory=list)
    recommended_template_updates: List[str] = Field(default_factory=list)


class PipelineProcessSpec(BaseModel):
    name: str
    tool: str
    input: str
    output: str
    description: str = ""


class PipelineArtifactSpec(BaseModel):
    """bio_code_agent structured output — real pipeline DSL artifact."""

    engine: str = "nextflow"
    workflow_family: str = "bioinformatics-mvp"
    assay_type: str = "other"
    params: Dict[str, str] = Field(default_factory=dict)
    processes: List[PipelineProcessSpec] = Field(default_factory=list)
    nextflow_script: str = ""
    snakemake_script: str = ""
    entrypoint: str = ""
