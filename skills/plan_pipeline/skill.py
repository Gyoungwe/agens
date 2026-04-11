from typing import Any, Dict, List

from core.base_skill import BaseSkill, SkillInput


def _normalize_assay_type(raw: str) -> str:
    normalized = (raw or "other").strip().lower().replace("-", "_").replace(" ", "_")
    return normalized or "other"


def _assay_template(assay_type: str) -> Dict[str, Any]:
    common_tail = {
        "planning": {
            "name": "planning",
            "focus": "confirm assay-specific analysis contract, inputs, references, and success criteria",
        },
        "report": {
            "name": "report",
            "focus": "summarize biological findings, caveats, and reproducibility details",
        },
        "evolution": {
            "name": "evolution",
            "focus": "capture retrospective improvements for template, parameters, and failure handling",
        },
    }

    templates: Dict[str, Dict[str, Any]] = {
        "rna_seq": {
            "workflow_family": "rna-seq",
            "analysis_focus": "expression quantification and differential expression",
            "required_inputs": [
                "FASTQ",
                "sample sheet",
                "reference genome",
                "annotation GTF/GFF",
            ],
            "stage_blueprint": [
                {"name": "planning", "focus": common_tail["planning"]["focus"]},
                {
                    "name": "codegen",
                    "focus": "prepare trimming/alignment-or-quantification strategy, count matrix generation, and DEG-ready outputs",
                },
                {
                    "name": "qc",
                    "focus": "review read quality, alignment/assignment rates, sample clustering, and batch effects",
                },
                {"name": "report", "focus": common_tail["report"]["focus"]},
                {"name": "evolution", "focus": common_tail["evolution"]["focus"]},
            ],
            "key_outputs": ["count_matrix", "qc_report", "de_summary", "final_report"],
            "major_risks": ["batch_effect", "low_mapping_rate", "annotation_mismatch"],
        },
        "scrna_seq": {
            "workflow_family": "single-cell-rna",
            "analysis_focus": "cell calling, normalization, clustering, marker discovery",
            "required_inputs": [
                "FASTQ or count matrix",
                "sample metadata",
                "reference/transcriptome",
            ],
            "stage_blueprint": [
                {"name": "planning", "focus": common_tail["planning"]["focus"]},
                {
                    "name": "codegen",
                    "focus": "prepare cell calling, normalization, dimensionality reduction, clustering, and marker analysis steps",
                },
                {
                    "name": "qc",
                    "focus": "review cell filtering thresholds, doublets, mitochondrial fraction, and batch integration quality",
                },
                {"name": "report", "focus": common_tail["report"]["focus"]},
                {"name": "evolution", "focus": common_tail["evolution"]["focus"]},
            ],
            "key_outputs": [
                "filtered_matrix",
                "cluster_labels",
                "marker_table",
                "qc_report",
            ],
            "major_risks": [
                "doublets",
                "over_filtering",
                "batch_integration_artifacts",
            ],
        },
        "wgs": {
            "workflow_family": "wgs-variant",
            "analysis_focus": "alignment, recalibration, variant calling, annotation",
            "required_inputs": [
                "FASTQ/BAM",
                "reference genome",
                "known sites",
                "sample metadata",
            ],
            "stage_blueprint": [
                {"name": "planning", "focus": common_tail["planning"]["focus"]},
                {
                    "name": "codegen",
                    "focus": "prepare alignment, duplicate handling, recalibration, variant calling, filtering, and annotation steps",
                },
                {
                    "name": "qc",
                    "focus": "review coverage, contamination, duplication, Ti/Tv, and callset quality",
                },
                {"name": "report", "focus": common_tail["report"]["focus"]},
                {"name": "evolution", "focus": common_tail["evolution"]["focus"]},
            ],
            "key_outputs": ["aligned_bam", "vcf", "annotated_variants", "qc_report"],
            "major_risks": [
                "low_coverage",
                "contamination",
                "reference_build_mismatch",
            ],
        },
        "wes": {
            "workflow_family": "wes-variant",
            "analysis_focus": "targeted coverage analysis and variant calling",
            "required_inputs": [
                "FASTQ/BAM",
                "target regions BED",
                "reference genome",
                "known sites",
            ],
            "stage_blueprint": [
                {"name": "planning", "focus": common_tail["planning"]["focus"]},
                {
                    "name": "codegen",
                    "focus": "prepare target-aware alignment, coverage metrics, variant calling, filtering, and annotation steps",
                },
                {
                    "name": "qc",
                    "focus": "review on-target rate, coverage uniformity, duplicate rate, and callable exome fraction",
                },
                {"name": "report", "focus": common_tail["report"]["focus"]},
                {"name": "evolution", "focus": common_tail["evolution"]["focus"]},
            ],
            "key_outputs": [
                "coverage_metrics",
                "vcf",
                "annotated_variants",
                "qc_report",
            ],
            "major_risks": ["poor_target_capture", "uneven_coverage", "panel_mismatch"],
        },
        "metagenomics": {
            "workflow_family": "metagenomics",
            "analysis_focus": "taxonomic and functional profiling across mixed communities",
            "required_inputs": [
                "FASTQ",
                "sample metadata",
                "taxonomy/functional databases",
            ],
            "stage_blueprint": [
                {"name": "planning", "focus": common_tail["planning"]["focus"]},
                {
                    "name": "codegen",
                    "focus": "prepare host depletion, taxonomic profiling, functional annotation, and abundance summarization steps",
                },
                {
                    "name": "qc",
                    "focus": "review read complexity, host contamination, classifier confidence, and database coverage",
                },
                {"name": "report", "focus": common_tail["report"]["focus"]},
                {"name": "evolution", "focus": common_tail["evolution"]["focus"]},
            ],
            "key_outputs": [
                "taxonomic_profile",
                "functional_profile",
                "abundance_table",
                "qc_report",
            ],
            "major_risks": [
                "host_contamination",
                "database_bias",
                "low_complexity_reads",
            ],
        },
        "atac_seq": {
            "workflow_family": "atac-seq",
            "analysis_focus": "chromatin accessibility peak discovery and differential accessibility",
            "required_inputs": ["FASTQ/BAM", "reference genome", "sample sheet"],
            "stage_blueprint": [
                {"name": "planning", "focus": common_tail["planning"]["focus"]},
                {
                    "name": "codegen",
                    "focus": "prepare alignment, peak calling, accessibility quantification, and differential analysis steps",
                },
                {
                    "name": "qc",
                    "focus": "review fragment distribution, TSS enrichment, FRiP, and replicate concordance",
                },
                {"name": "report", "focus": common_tail["report"]["focus"]},
                {"name": "evolution", "focus": common_tail["evolution"]["focus"]},
            ],
            "key_outputs": [
                "peak_set",
                "accessibility_matrix",
                "qc_report",
                "final_report",
            ],
            "major_risks": [
                "low_tss_enrichment",
                "poor_fragment_profile",
                "batch_effect",
            ],
        },
        "chip_seq": {
            "workflow_family": "chip-seq",
            "analysis_focus": "binding/enrichment peak identification and annotation",
            "required_inputs": [
                "FASTQ/BAM",
                "control/input sample",
                "reference genome",
            ],
            "stage_blueprint": [
                {"name": "planning", "focus": common_tail["planning"]["focus"]},
                {
                    "name": "codegen",
                    "focus": "prepare alignment, enrichment peak calling, motif/annotation, and differential binding steps",
                },
                {
                    "name": "qc",
                    "focus": "review enrichment quality, FRiP, strand cross-correlation, and control suitability",
                },
                {"name": "report", "focus": common_tail["report"]["focus"]},
                {"name": "evolution", "focus": common_tail["evolution"]["focus"]},
            ],
            "key_outputs": ["peak_set", "annotated_peaks", "qc_report", "final_report"],
            "major_risks": [
                "weak_enrichment",
                "bad_control",
                "replicate_inconsistency",
            ],
        },
        "assembly": {
            "workflow_family": "assembly",
            "analysis_focus": "de novo assembly, polishing, and assembly QC",
            "required_inputs": ["reads", "platform metadata", "reference optional"],
            "stage_blueprint": [
                {"name": "planning", "focus": common_tail["planning"]["focus"]},
                {
                    "name": "codegen",
                    "focus": "prepare assembly, polishing, contamination screening, and annotation-ready outputs",
                },
                {
                    "name": "qc",
                    "focus": "review N50, completeness, contamination, and polishing convergence",
                },
                {"name": "report", "focus": common_tail["report"]["focus"]},
                {"name": "evolution", "focus": common_tail["evolution"]["focus"]},
            ],
            "key_outputs": [
                "assembly_fasta",
                "assembly_qc",
                "annotation_inputs",
                "final_report",
            ],
            "major_risks": ["contamination", "fragmentation", "platform_error_profile"],
        },
    }

    default_template = {
        "workflow_family": "bioinformatics-mvp",
        "analysis_focus": "generic bioinformatics analysis planning",
        "required_inputs": [
            "dataset description",
            "sample metadata",
            "reference resources",
        ],
        "stage_blueprint": [
            {"name": "planning", "focus": common_tail["planning"]["focus"]},
            {
                "name": "codegen",
                "focus": "prepare an executable analysis template for the requested objective",
            },
            {
                "name": "qc",
                "focus": "define assay-agnostic quality checks and decision gates",
            },
            {"name": "report", "focus": common_tail["report"]["focus"]},
            {"name": "evolution", "focus": common_tail["evolution"]["focus"]},
        ],
        "key_outputs": ["analysis_plan", "qc_report", "final_report"],
        "major_risks": ["ambiguous_assay", "missing_metadata", "reference_mismatch"],
    }

    return templates.get(assay_type, default_template)


class Skill(BaseSkill):
    skill_id = "plan_pipeline"
    name = "生信流程规划"
    description = "将生物信息学目标拆解为可执行阶段"
    version = "0.02"
    tags = ["bioinformatics", "planning", "workflow"]

    async def run(self, input_data: SkillInput) -> Any:
        goal = input_data.instruction
        context = input_data.context or {}
        assay_type = _normalize_assay_type(
            str(
                context.get("assay_type")
                or context.get("intent", {}).get("assay_type")
                or context.get("runtime_context", {}).get("assay_type")
                or "other"
            )
        )
        template = _assay_template(assay_type)
        expected_outputs = context.get("expected_outputs") or context.get(
            "intent", {}
        ).get("expected_outputs", [])
        if isinstance(expected_outputs, str):
            expected_outputs = [expected_outputs]
        if not isinstance(expected_outputs, list):
            expected_outputs = []

        return {
            "goal": goal,
            "assay_type": assay_type,
            "workflow_family": template["workflow_family"],
            "analysis_focus": template["analysis_focus"],
            "required_inputs": template["required_inputs"],
            "confirmed_outputs": expected_outputs,
            "major_risks": template["major_risks"],
            "stages": [
                {
                    "name": s["name"],
                    "goal": s["focus"],
                    "inputs": template["required_inputs"],
                    "outputs": template.get("key_outputs", []),
                    "primary_risk": template["major_risks"][0]
                    if template["major_risks"]
                    else "unknown",
                }
                for s in template["stage_blueprint"]
            ],
            "critical_notes": [],
            "fallback_strategy": "retry_with_simpler_params",
        }
