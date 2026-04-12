from typing import Any

from core.base_skill import BaseSkill, SkillInput


class Skill(BaseSkill):
    async def run(self, input_data: SkillInput) -> Any:
        assay_type = input_data.context.get("assay_type", "rna_seq")

        plans = {
            "rna_seq": {
                "workflow_family": "rna-seq",
                "stages": [
                    {"name": "planning", "goal": "define RNA-seq analysis scope"},
                    {
                        "name": "codegen",
                        "goal": "generate Nextflow pipeline for alignment and quantification",
                        "outputs": ["pipeline", "count_matrix", "qc_report"],
                    },
                    {"name": "execution", "goal": "run alignment and quantification"},
                    {"name": "qc", "goal": "check mapping and count quality"},
                    {
                        "name": "report",
                        "goal": "summarize differential expression results",
                    },
                ],
            },
            "wgs": {
                "workflow_family": "wgs-variant",
                "stages": [
                    {"name": "planning", "goal": "define variant calling scope"},
                    {
                        "name": "codegen",
                        "goal": "generate Nextflow pipeline for WGS alignment and variant calling",
                        "outputs": ["pipeline", "vcf", "qc_report"],
                    },
                    {
                        "name": "execution",
                        "goal": "run alignment and haplotype calling",
                    },
                    {"name": "qc", "goal": "validate coverage and variant metrics"},
                    {"name": "report", "goal": "summarize variant findings"},
                ],
            },
            "metagenomics": {
                "workflow_family": "metagenomics",
                "stages": [
                    {"name": "planning", "goal": "define profiling strategy"},
                    {
                        "name": "codegen",
                        "goal": "generate profiling workflow",
                        "outputs": [
                            "pipeline",
                            "taxonomic_profile",
                            "functional_profile",
                        ],
                    },
                    {
                        "name": "execution",
                        "goal": "run taxonomic and functional profiling",
                    },
                    {
                        "name": "qc",
                        "goal": "review contamination and assignment confidence",
                    },
                    {"name": "report", "goal": "summarize community composition"},
                ],
            },
        }

        plan = plans.get(assay_type, plans["rna_seq"])
        return {
            "goal": input_data.instruction,
            "assay_type": assay_type,
            **plan,
        }
