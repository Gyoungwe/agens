from __future__ import annotations

import io
import logging
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List

import httpx
import yaml

from core.skill_registry import SkillRegistry, SKILLS_DIR

logger = logging.getLogger(__name__)

SCIENTIFIC_SKILLS_ZIP_URL = (
    "https://codeload.github.com/K-Dense-AI/scientific-agent-skills/zip/refs/heads/main"
)

RESEARCH_SKILLS = {
    "database-lookup",
    "depmap",
    "imaging-data-commons",
    "primekg",
    "literature-review",
    "paper-lookup",
    "bgpt-paper-search",
    "parallel-web",
    "citation-management",
    "research-lookup",
    "market-research-reports",
    "clinical-trials",
    "open-notebook",
}

WRITER_SKILLS = {
    "scientific-writing",
    "peer-review",
    "scientific-slides",
    "latex-posters",
    "pptx-posters",
    "scientific-schematics",
    "infographics",
    "markdown-mermaid-writing",
    "clinical-reports",
    "venue-templates",
    "citation-management",
    "literature-review",
    "docx",
    "xlsx",
    "markitdown",
}

EXECUTION_PATTERNS = (
    "integration",
    "modal",
    "opentrons",
    "benchling",
    "dnanexus",
    "latchbio",
    "ginkgo",
    "omero",
    "protocols",
    "gpu",
    "generate-image",
    "get-available-resources",
)

EXECUTOR_ONLY_SKILLS = {
    "benchling-integration",
    "benchling_integration",
    "dnanexus-integration",
    "dnanexus_integration",
    "latchbio-integration",
    "latchbio_integration",
    "opentrons-integration",
    "opentrons_integration",
    "ginkgo-cloud-lab",
    "ginkgo_cloud_lab",
    "modal",
    "generate-image",
    "generate_image",
    "get-available-resources",
    "get_available_resources",
}

WRITER_ONLY_SKILLS = {
    "scientific-writing",
    "scientific_writing",
    "scientific-slides",
    "scientific_slides",
    "scientific-schematics",
    "scientific_schematics",
    "latex-posters",
    "latex_posters",
    "pptx-posters",
    "pptx_posters",
    "infographics",
    "markdown-mermaid-writing",
    "markdown_mermaid_writing",
    "venue-templates",
    "venue_templates",
    "docx",
    "xlsx",
    "markitdown",
}

BIO_CODE_ONLY_SKILLS = {
    "anndata",
    "arboreto",
    "biopython",
    "bioservices",
    "cellxgene-census",
    "cellxgene_census",
    "deepchem",
    "gget",
    "polars-bio",
    "polars_bio",
    "pyopenms",
    "rdkit",
    "scanpy",
    "scvi-tools",
    "scvi_tools",
    "datamol",
    "diffdock",
    "pydeseq2",
    "pysam",
}

BIO_CODE_PATTERNS = (
    "bio",
    "gene",
    "genom",
    "rna",
    "protein",
    "variant",
    "scanpy",
    "anndata",
    "scvelo",
    "scvi",
    "pydeseq",
    "biopython",
    "bioservices",
    "cellxgene",
    "pysam",
    "deeptools",
    "flowio",
    "gget",
    "geniml",
    "gtars",
    "pathml",
    "histolab",
    "pyopenms",
    "matchms",
    "rdkit",
    "deepchem",
    "datamol",
    "diffdock",
    "molfeat",
    "medchem",
    "torchdrug",
    "pytdc",
)


def _parse_skill_markdown(raw: str) -> tuple[Dict[str, Any], str]:
    match = re.match(r"^---\n(.*?)\n---\n?(.*)$", raw, re.DOTALL)
    if not match:
        return {}, raw.strip()

    frontmatter = yaml.safe_load(match.group(1)) or {}
    body = (match.group(2) or "").strip()
    return frontmatter, body


def _normalize_tools(frontmatter: Dict[str, Any]) -> List[str]:
    tools = frontmatter.get("allowed-tools") or frontmatter.get("tools") or []
    if isinstance(tools, str):
        tools = [t.strip() for t in re.split(r"[,\s]+", tools) if t.strip()]
    return [str(t) for t in tools]


def _infer_permissions(
    skill_name: str, tools: List[str], description: str
) -> Dict[str, bool]:
    lowered_tools = {tool.lower() for tool in tools}
    lowered_description = (description or "").lower()
    is_research_skill = skill_name.lower() in RESEARCH_SKILLS or any(
        token in skill_name.lower()
        for token in ["lookup", "paper", "search", "citation", "review"]
    )
    return {
        "network": bool(
            lowered_tools.intersection({"webfetch", "fetch", "web", "bash"})
            or any(
                keyword in lowered_description
                for keyword in ["api", "database", "search", "web", "download"]
            )
        ),
        "filesystem": False
        if is_research_skill
        else bool(lowered_tools.intersection({"read", "write", "edit", "bash"})),
        "shell": False
        if is_research_skill
        else ("bash" in lowered_tools or "shell" in lowered_tools),
    }


def _map_agents(skill_slug: str, description: str) -> List[str]:
    skill_name = skill_slug.lower()
    description_lower = (description or "").lower()

    if skill_name in EXECUTOR_ONLY_SKILLS:
        return ["executor_agent"]
    if skill_name in WRITER_ONLY_SKILLS:
        return ["writer_agent"]
    if skill_name in BIO_CODE_ONLY_SKILLS:
        return ["bio_code_agent"]

    agents: List[str] = []

    if skill_name in RESEARCH_SKILLS or any(
        token in skill_name
        for token in ["lookup", "paper", "search", "citation", "review"]
    ):
        agents.append("research_agent")

    if skill_name in WRITER_SKILLS or any(
        token in skill_name
        for token in [
            "writing",
            "review",
            "poster",
            "slides",
            "schematic",
            "mermaid",
            "infographic",
            "report",
        ]
    ):
        agents.append("writer_agent")

    if any(token in skill_name for token in BIO_CODE_PATTERNS) or any(
        token in description_lower
        for token in [
            "genomics",
            "single-cell",
            "bioinformatics",
            "proteomics",
            "pathology",
            "sequencing",
            "molecular biology",
        ]
    ):
        agents.append("bio_code_agent")

    explicit_executor = any(token in skill_name for token in EXECUTION_PATTERNS)
    generic_executor = any(
        token in description_lower
        for token in [
            "workflow",
            "automation",
            "cloud",
            "serverless",
            "platform",
            "integration",
        ]
    )

    if explicit_executor or (not agents and generic_executor):
        agents.append("executor_agent")

    if not agents:
        agents.append("executor_agent")

    return sorted(set(agents))


def _build_entry_py() -> str:
    return """from pathlib import Path

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
"""


class ScientificSkillImporter:
    def __init__(
        self, registry: SkillRegistry | None = None, skills_dir: Path = SKILLS_DIR
    ):
        self.registry = registry
        self.skills_dir = skills_dir

    async def import_all(self, dry_run: bool = False) -> dict:
        repo_root = await self._download_repo_archive()
        scientific_dir = repo_root / "scientific-skills"
        imported = []

        for skill_dir in sorted(scientific_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_doc = skill_dir / "SKILL.md"
            if not skill_doc.exists():
                continue

            frontmatter, readme_body = _parse_skill_markdown(
                skill_doc.read_text(encoding="utf-8")
            )
            local_skill_id = skill_dir.name.replace("-", "_")
            tools = _normalize_tools(frontmatter)
            description = frontmatter.get("description", "")
            skill_package = {
                "skill_id": local_skill_id,
                "name": frontmatter.get("name", skill_dir.name),
                "description": description,
                "version": str(frontmatter.get("version", "1.0.0")),
                "author": frontmatter.get("metadata", {}).get(
                    "skill-author", "K-Dense Inc."
                ),
                "license": frontmatter.get("license", ""),
                "tags": ["scientific-agent-skills", skill_dir.name],
                "tools": tools,
                "permissions": _infer_permissions(skill_dir.name, tools, description),
                "agents": _map_agents(skill_dir.name, description),
                "enabled": True,
                "source": "scientific-agent-skills",
                "entrypoint": "entry.py",
                "readme": "README.md",
                "input_schema": frontmatter.get("input_schema", {}),
                "output_schema": {"type": "object"},
                "metadata": {
                    "upstream_repo": "K-Dense-AI/scientific-agent-skills",
                    "upstream_skill": skill_dir.name,
                    "upstream_path": f"scientific-skills/{skill_dir.name}/SKILL.md",
                    "upstream_frontmatter": frontmatter,
                },
            }
            imported.append(skill_package)

            if not dry_run:
                self._write_local_skill_package(skill_package, readme_body)
                if self.registry:
                    self.registry._register_from_dir(self.skills_dir / local_skill_id)

        return {
            "imported_count": len(imported),
            "skills": imported,
            "dry_run": dry_run,
        }

    async def _download_repo_archive(self) -> Path:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.get(SCIENTIFIC_SKILLS_ZIP_URL)
            response.raise_for_status()

        archive = zipfile.ZipFile(io.BytesIO(response.content))
        root_name = archive.namelist()[0].split("/")[0]
        temp_root = Path("/tmp") / root_name
        if temp_root.exists():
            import shutil

            shutil.rmtree(temp_root)
        archive.extractall(temp_root.parent)
        return temp_root

    def _write_local_skill_package(
        self, skill_package: Dict[str, Any], readme_body: str
    ) -> None:
        target_dir = self.skills_dir / skill_package["skill_id"]
        target_dir.mkdir(parents=True, exist_ok=True)

        (target_dir / "skill.yaml").write_text(
            yaml.safe_dump(skill_package, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        (target_dir / "README.md").write_text(
            readme_body.strip() + "\n", encoding="utf-8"
        )
        (target_dir / "entry.py").write_text(_build_entry_py(), encoding="utf-8")


async def import_scientific_skills(
    registry: SkillRegistry | None = None, dry_run: bool = False
) -> dict:
    importer = ScientificSkillImporter(registry=registry)
    return await importer.import_all(dry_run=dry_run)
