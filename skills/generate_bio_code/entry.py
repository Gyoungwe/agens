from typing import Any

from core.base_skill import BaseSkill, SkillInput


class Skill(BaseSkill):
    async def run(self, input_data: SkillInput) -> Any:
        assay_type = input_data.context.get("assay_type", "rna_seq")

        workflows = {
            "rna_seq": {
                "engine": "nextflow",
                "assay_type": "rna_seq",
                "steps": [
                    {"name": "ALIGN", "tool": "STAR"},
                    {"name": "QUANTIFY", "tool": "featureCounts"},
                    {"name": "DESEQ", "tool": "DESeq2"},
                    {"name": "MULTIQC", "tool": "MultiQC"},
                ],
            },
            "wgs": {
                "engine": "nextflow",
                "assay_type": "wgs",
                "steps": [
                    {"name": "ALIGN", "tool": "BWA-MEM2"},
                    {"name": "MARKDUP", "tool": "samtools"},
                    {"name": "HAPLOTYPECALLER", "tool": "GATK"},
                    {"name": "FILTER", "tool": "bcftools"},
                ],
            },
            "metagenomics": {
                "engine": "nextflow",
                "assay_type": "metagenomics",
                "steps": [
                    {"name": "PREPROCESS", "tool": "fastp"},
                    {"name": "TAXAPROFILE", "tool": "kraken2"},
                    {"name": "FUNCTION", "tool": "humann"},
                    {"name": "REPORT", "tool": "MultiQC"},
                ],
            },
        }

        return {
            "instruction": input_data.instruction,
            "files": ["main.nf", "nextflow.config", "README.md"],
            "commands": ["nextflow run main.nf -profile docker"],
            **workflows.get(assay_type, workflows["rna_seq"]),
        }
