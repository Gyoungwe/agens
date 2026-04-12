from pathlib import Path

from core.base_skill import BaseSkill, SkillInput
from core.skill_manifest import load_skill_manifest


class Skill(BaseSkill):
    async def run(self, input_data: SkillInput):
        skill_dir = Path(__file__).resolve().parent
        manifest = load_skill_manifest(skill_dir)
        readme_path = skill_dir / manifest.readme
        readme_text = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""
        return {
            "skill_id": manifest.skill_id,
            "name": manifest.name,
            "instruction": input_data.instruction,
            "guidance": readme_text,
            "metadata": manifest.metadata,
            "allowed_tools": manifest.tools,
        }
