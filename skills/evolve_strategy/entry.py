from typing import Any

from core.base_skill import BaseSkill, SkillInput


class Skill(BaseSkill):
    async def run(self, input_data: SkillInput) -> Any:
        return {
            "instruction": input_data.instruction,
            "success_factors": [
                "clear stage decomposition",
                "explicit QC checkpoint",
            ],
            "failure_patterns": [
                "insufficient reference data",
                "manual threshold drift",
            ],
            "priority_improvements": [
                {
                    "category": "improvement",
                    "description": "add domain-specific dataset validation",
                    "priority": "high",
                },
                {
                    "category": "skill_gap",
                    "description": "expand reproducible command templates",
                    "priority": "medium",
                },
            ],
            "automated_capability_gaps": [
                "dynamic threshold adaptation based on sample characteristics",
            ],
            "recommended_template_updates": [
                "add assay-specific QC thresholds to template",
            ],
        }
