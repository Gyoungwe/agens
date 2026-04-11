from typing import Any, Dict

from core.base_skill import BaseSkill, SkillInput


def _normalize_assay(raw: str) -> str:
    normalized = (raw or "other").strip().lower().replace("-", "_").replace(" ", "_")
    return normalized or "other"


def _pipeline_template(assay_type: str) -> Dict[str, Any]:
    common_log = "logs/${params.run_id}/pipeline.log"
    profiles: Dict[str, Dict[str, Any]] = {
        "rna_seq": {
            "engine": "nextflow",
            "params": {
                "genome": "",
                "gtf": "",
                "outdir": "results/rnaseq",
            },
            "steps": [
                {
                    "name": "FASTQC",
                    "tool": "fastqc",
                    "input": "reads",
                    "output": "fastqc_reports",
                    "description": "Quality control on raw reads",
                },
                {
                    "name": "TRIM",
                    "tool": "trimgalore",
                    "input": "reads",
                    "output": "trimmed_reads",
                    "description": "Adapter and low-quality trimming",
                },
                {
                    "name": "ALIGN",
                    "tool": "star",
                    "input": "trimmed_reads",
                    "output": "bam",
                    "description": "Splice-aware genome alignment",
                },
                {
                    "name": "QUANTIFY",
                    "tool": "featurecounts",
                    "input": "bam",
                    "output": "count_matrix",
                    "description": "Gene-level quantification",
                },
            ],
        },
        "scrna_seq": {
            "engine": "nextflow",
            "params": {
                "genome": "",
                "outdir": "results/scrnaseq",
            },
            "steps": [
                {
                    "name": "FASTQC",
                    "tool": "fastqc",
                    "input": "reads",
                    "output": "fastqc_reports",
                    "description": "Read quality assessment",
                },
                {
                    "name": "CELL_CALL",
                    "tool": "cellranger_count",
                    "input": "reads",
                    "output": "cell_matrix",
                    "description": "Cell calling and barcode assignment",
                },
                {
                    "name": "NORMALIZE",
                    "tool": "scanpy_regress",
                    "input": "cell_matrix",
                    "output": "normalized_matrix",
                    "description": "Normalization and mitochondrial regression",
                },
                {
                    "name": "CLUSTER",
                    "tool": "scanpy_cluster",
                    "input": "normalized_matrix",
                    "output": "clusters",
                    "description": "PCA, neighborhood graph, and clustering",
                },
            ],
        },
        "wgs": {
            "engine": "nextflow",
            "params": {
                "genome": "",
                "known_sites": "",
                "outdir": "results/wgs",
            },
            "steps": [
                {
                    "name": "FASTQC",
                    "tool": "fastqc",
                    "input": "reads",
                    "output": "fastqc_reports",
                    "description": "Read quality assessment",
                },
                {
                    "name": "ALIGN",
                    "tool": "bwa_mem",
                    "input": "reads",
                    "output": "bam",
                    "description": "Genome alignment with BWA-MEM",
                },
                {
                    "name": "MARKDUP",
                    "tool": "gatk_markduplicates",
                    "input": "bam",
                    "output": "dedup_bam",
                    "description": "Mark duplicate reads",
                },
                {
                    "name": "BQSR",
                    "tool": "gatk_baserecalibrator",
                    "input": "dedup_bam",
                    "output": "recal_bam",
                    "description": "Base quality score recalibration",
                },
                {
                    "name": "HAPLOTYPECALLER",
                    "tool": "gatk_haplotypecaller",
                    "input": "recal_bam",
                    "output": "vcf",
                    "description": "Germline variant calling",
                },
            ],
        },
        "wes": {
            "engine": "nextflow",
            "params": {
                "genome": "",
                "targets": "",
                "outdir": "results/wes",
            },
            "steps": [
                {
                    "name": "FASTQC",
                    "tool": "fastqc",
                    "input": "reads",
                    "output": "fastqc_reports",
                    "description": "Read quality assessment",
                },
                {
                    "name": "ALIGN",
                    "tool": "bwa_mem",
                    "input": "reads",
                    "output": "bam",
                    "description": "Targeted alignment with BWA-MEM",
                },
                {
                    "name": "COVERAGECHECK",
                    "tool": "qualimap_bamqc",
                    "input": "bam",
                    "output": "coverage_metrics",
                    "description": "Target region coverage assessment",
                },
                {
                    "name": "HAPLOTYPECALLER",
                    "tool": "gatk_haplotypecaller",
                    "input": "bam",
                    "output": "vcf",
                    "description": "Somatic variant calling on exome",
                },
            ],
        },
        "metagenomics": {
            "engine": "nextflow",
            "params": {
                "outdir": "results/metagenomics",
            },
            "steps": [
                {
                    "name": "FASTQC",
                    "tool": "fastqc",
                    "input": "reads",
                    "output": "fastqc_reports",
                    "description": "Read quality assessment",
                },
                {
                    "name": "HOSTREMOVE",
                    "tool": "bowtie2",
                    "input": "reads",
                    "output": "depleted_reads",
                    "description": "Host/genome depletion",
                },
                {
                    "name": "TAXAPROFILE",
                    "tool": "kraken2",
                    "input": "depleted_reads",
                    "output": "taxonomic_profile",
                    "description": "Taxonomic classification",
                },
                {
                    "name": "FUNANNOT",
                    "tool": "humann3",
                    "input": "depleted_reads",
                    "output": "functional_profile",
                    "description": "Functional annotation",
                },
            ],
        },
        "atac_seq": {
            "engine": "nextflow",
            "params": {
                "genome": "",
                "outdir": "results/atacseq",
            },
            "steps": [
                {
                    "name": "FASTQC",
                    "tool": "fastqc",
                    "input": "reads",
                    "output": "fastqc_reports",
                    "description": "Read quality assessment",
                },
                {
                    "name": "TRIM",
                    "tool": "trimgalore",
                    "input": "reads",
                    "output": "trimmed_reads",
                    "description": "ATAC-seq specific trimming",
                },
                {
                    "name": "ALIGN",
                    "tool": "bowtie2",
                    "input": "trimmed_reads",
                    "output": "bam",
                    "description": "ATAC alignment",
                },
                {
                    "name": "PEAKCALL",
                    "tool": "macs3",
                    "input": "bam",
                    "output": "peaks",
                    "description": "Peak calling",
                },
            ],
        },
        "chip_seq": {
            "engine": "nextflow",
            "params": {
                "genome": "",
                "control": "",
                "outdir": "results/chipseq",
            },
            "steps": [
                {
                    "name": "FASTQC",
                    "tool": "fastqc",
                    "input": "reads",
                    "output": "fastqc_reports",
                    "description": "Read quality assessment",
                },
                {
                    "name": "ALIGN",
                    "tool": "bwa_mem",
                    "input": "reads",
                    "output": "bam",
                    "description": "ChIP-seq alignment",
                },
                {
                    "name": "PEAKCALL",
                    "tool": "macs3",
                    "input": "bam",
                    "output": "peaks",
                    "description": "Peak calling with control",
                },
                {
                    "name": "ANNOTATE",
                    "tool": "homer_annotatePeaks",
                    "input": "peaks",
                    "output": "annotated_peaks",
                    "description": "Peak annotation and motif discovery",
                },
            ],
        },
        "assembly": {
            "engine": "nextflow",
            "params": {
                "outdir": "results/assembly",
            },
            "steps": [
                {
                    "name": "FASTQC",
                    "tool": "fastqc",
                    "input": "reads",
                    "output": "fastqc_reports",
                    "description": "Read quality assessment",
                },
                {
                    "name": "ASSEMBLE",
                    "tool": "spades",
                    "input": "reads",
                    "output": "contigs",
                    "description": "De novo assembly",
                },
                {
                    "name": "POLISH",
                    "tool": "pilon",
                    "input": "contigs",
                    "output": "polished_assembly",
                    "description": "Assembly polishing",
                },
                {
                    "name": "CONTAMINATION",
                    "tool": "blobtools",
                    "input": "polished_assembly",
                    "output": "contamination_check",
                    "description": "Contamination screening",
                },
            ],
        },
    }

    default_template = {
        "engine": "nextflow",
        "params": {"outdir": "results/bio"},
        "steps": [
            {
                "name": "PREP",
                "tool": "bash",
                "input": "dataset",
                "output": "prepared",
                "description": "Data preparation",
            },
            {
                "name": "ANALYZE",
                "tool": "custom",
                "input": "prepared",
                "output": "results",
                "description": "Analysis step",
            },
        ],
    }

    return profiles.get(assay_type, default_template)


class Skill(BaseSkill):
    skill_id = "generate_bio_code"
    name = "生信代码生成"
    description = "生成生物信息学 pipeline 脚本建议"
    version = "0.02"
    tags = ["bioinformatics", "codegen", "pipeline"]

    async def run(self, input_data: SkillInput) -> Any:
        task = input_data.instruction
        context = input_data.context or {}
        assay_type = _normalize_assay(
            str(
                context.get("assay_type")
                or context.get("intent", {}).get("assay_type")
                or context.get("runtime_context", {}).get("assay_type")
                or "other"
            )
        )
        template = _pipeline_template(assay_type)
        return {
            "task": task,
            "assay_type": assay_type,
            "engine": template["engine"],
            "params": template["params"],
            "steps": template["steps"],
            "description": f"Generated pipeline template for assay_type={assay_type}",
        }
