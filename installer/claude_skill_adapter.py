# installer/claude_skill_adapter.py
# Claude Skill 导入转换器 - 将 Claude Tool JSON Schema 转为 BaseSkill

import ast
import json
import re
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ClaudeToolSchema:
    """Claude Tool JSON Schema 结构"""

    name: str
    description: str
    input_schema: Dict[str, Any]
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillDraft:
    """技能草稿"""

    tool_name: str
    description: str
    parameters: List[Dict[str, Any]]
    execute_template: str
    source: str = "claude_skill"
    original_schema: Dict = field(default_factory=dict)
    validation_warnings: List[str] = field(default_factory=list)


@dataclass
class ImportResult:
    """导入结果"""

    success: bool
    skill_id: Optional[str] = None
    draft_id: Optional[str] = None
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


class ClaudeSkillAdapter:
    """Claude Skill 转换适配器"""

    DANGEROUS_PATTERNS = [
        (r"os\.system", "os.system 调用存在安全风险"),
        (r"subprocess\.", "subprocess 调用存在安全风险"),
        (r"eval\s*\(", "eval() 存在代码注入风险"),
        (r"exec\s*\(", "exec() 存在代码注入风险"),
        (r"__import__", "__import__ 存在代码注入风险"),
        (r"open\s*\([^)]*['\"][wr]['\"]", "文件写入操作需要额外审查"),
        (r"requests\.post.*api", "网络请求可能泄露敏感信息"),
    ]

    def __init__(self, skills_dir: str = "skills"):
        self.skills_dir = Path(skills_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.drafts: Dict[str, SkillDraft] = {}

    def parse_schema(self, schema: Dict[str, Any]) -> ClaudeToolSchema:
        """解析 Claude Tool JSON Schema"""
        name = schema.get("name")
        description = schema.get("description", "")
        input_schema = schema.get("input_schema", {})

        if not name:
            raise ValueError("Tool schema must have a 'name' field")

        if not isinstance(input_schema, dict):
            raise ValueError("input_schema must be a dictionary")

        return ClaudeToolSchema(
            name=name, description=description, input_schema=input_schema, raw=schema
        )

    def extract_parameters(self, input_schema: Dict) -> List[Dict[str, Any]]:
        """从 input_schema 提取参数定义"""
        properties = input_schema.get("properties", {})
        required = input_schema.get("required", [])

        params = []
        for param_name, param_spec in properties.items():
            param_info = {
                "name": param_name,
                "type": param_spec.get("type", "string"),
                "description": param_spec.get("description", ""),
                "required": param_name in required,
                "default": param_spec.get("default"),
                "enum": param_spec.get("enum"),
            }
            params.append(param_info)
        return params

    def generate_execute_template(
        self, tool_name: str, description: str, parameters: List[Dict]
    ) -> str:
        """生成 execute() 函数骨架（仅方法体）"""
        param_lines = []
        for p in parameters:
            line = f'            "{p["name"]}": {self._type_hint(p)}'
            if p.get("description"):
                line += f"  # {p['description']}"
            param_lines.append(line)

        params_str = ",\n".join(param_lines) if param_lines else ""

        template = f"""        import json
        import logging
        logger = logging.getLogger(__name__)

        # 解析输入参数
        try:
            params = json.loads(instruction)
        except json.JSONDecodeError:
            params = {{}}

        # 参数验证
        required_params = [{", ".join(f'"{p["name"]}"' for p in parameters if p.get("required"))}]
        missing = [p for p in required_params if p not in params]
        if missing:
            raise ValueError(f"Missing required parameters: {{missing}}")

        # TODO: 实现 {tool_name} 技能逻辑
        logger.info(f"Executing {tool_name} with params: {{params}}")

        result = {{
{params_str}
        }}

        # 返回 JSON 结果
        return json.dumps(result, ensure_ascii=False, indent=2)
"""
        return template

    def _type_hint(self, param: Dict) -> str:
        """生成 Python 类型提示"""
        param_type = param.get("type", "string")
        default = param.get("default")

        if default is not None:
            return f'params.get("{param["name"]}", {repr(default)})'

        type_map = {
            "string": '""',
            "integer": "0",
            "number": "0.0",
            "boolean": "False",
            "array": "[]",
            "object": "{{}}",
        }

        return f'params.get("{param["name"]}", {type_map.get(param_type, "None")})'

    def scan_dangerous_code(self, code: str) -> List[Tuple[str, str]]:
        """静态安全扫描 - 检测危险代码模式"""
        warnings = []
        for pattern, message in self.DANGEROUS_PATTERNS:
            if re.search(pattern, code):
                warnings.append((pattern, message))
        return warnings

    def validate_schema(self, schema: Dict) -> List[str]:
        """验证 Schema 合法性"""
        warnings = []

        if not schema.get("name"):
            warnings.append("缺少 'name' 字段")

        if not schema.get("description"):
            warnings.append("建议添加 'description' 字段")

        input_schema = schema.get("input_schema", {})
        if not isinstance(input_schema, dict):
            warnings.append("'input_schema' 必须是对象类型")
        elif "properties" not in input_schema:
            warnings.append("'input_schema' 建议包含 'properties' 定义")

        return warnings

    def create_draft(self, schema: Dict) -> Tuple[str, SkillDraft]:
        """从 Schema 创建技能草稿"""
        validation_warnings = self.validate_schema(schema)
        parsed = self.parse_schema(schema)
        parameters = self.extract_parameters(parsed.input_schema)
        execute_template = self.generate_execute_template(
            parsed.name, parsed.description, parameters
        )

        draft = SkillDraft(
            tool_name=parsed.name,
            description=parsed.description,
            parameters=parameters,
            execute_template=execute_template,
            original_schema=parsed.raw,
            validation_warnings=validation_warnings,
        )

        draft_id = f"{parsed.name}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.drafts[draft_id] = draft

        return draft_id, draft

    def generate_skill_code(self, draft: SkillDraft) -> str:
        """生成完整的技能代码"""
        class_name = self._to_class_name(draft.tool_name)

        code = f'''# skills/{draft.tool_name}.py
# 由 Claude Skill Adapter 自动生成
# 源: {draft.source}
# 生成时间: {datetime.now().isoformat()}

import logging
from typing import Any

logger = logging.getLogger(__name__)


class {class_name}Skill:
    """
    {draft.description}

    参数:
{self._generate_param_doc(draft.parameters)}

    示例:
        >>> skill = {class_name}Skill()
        >>> result = await skill.execute('{{"param1": "value1"}}')
    """

    def __init__(self):
        self.name = "{draft.tool_name}"
        self.description = """{draft.description}"""
        self.version = "1.0.0"
        self.source = "{draft.source}"

    async def execute(self, instruction: str, context: dict = {{}}) -> str:
        """
        执行技能

        Args:
            instruction: JSON 格式的指令字符串
            context: 可选的上下文字典

        Returns:
            str: JSON 格式的执行结果
        """
{draft.execute_template}

    async def validate(self, params: dict) -> tuple[bool, str]:
        """
        验证参数是否合法

        Args:
            params: 参数字典

        Returns:
            (is_valid, error_message)
        """
{self._generate_validation_code(draft.parameters)}


# 快捷函数
async def create_skill() -> {class_name}Skill:
    """创建技能实例"""
    return {class_name}Skill()
'''

        return code

    def _to_class_name(self, tool_name: str) -> str:
        """将 tool_name 转换为类名"""
        clean_name = tool_name

        if clean_name.lower().endswith("_skill"):
            clean_name = clean_name[:-6]
        elif clean_name.lower().endswith("skill"):
            clean_name = clean_name[:-5]

        parts = clean_name.replace("-", "_").replace("_", " ").title().split()
        return "".join(parts)

    def _generate_param_doc(self, parameters: List[Dict]) -> str:
        """生成参数文档"""
        lines = []
        for p in parameters:
            req = "必需" if p.get("required") else "可选"
            lines.append(
                f"        {p['name']} ({p.get('type', 'Any')}): {p.get('description', '')} [{req}]"
            )
        return "\n".join(lines) if lines else "        (无)"

    def _generate_validation_code(self, parameters: List[Dict]) -> str:
        """生成参数验证代码"""
        lines = ["        errors = []"]

        for p in parameters:
            name = p["name"]
            ptype = p.get("type", "string")

            if p.get("required"):
                lines.append(f'        if "{name}" not in params:')
                lines.append(
                    f'            errors.append(f"Missing required parameter: {name}")'
                )

            if p.get("enum"):
                enum_list = ", ".join(repr(e) for e in p["enum"])
                lines.append(
                    f'        if "{name}" in params and params["{name}"] not in [{enum_list}]:'
                )
                lines.append(
                    f'            errors.append(f"Invalid value for {name}: must be one of [{enum_list}]")'
                )

        lines.append("        if errors:")
        lines.append('            return False, "; ".join(errors)')
        lines.append('        return True, ""')

        return "\n".join(lines)

    def preview_draft(self, draft_id: str) -> Optional[Dict]:
        """预览草稿内容"""
        draft = self.drafts.get(draft_id)
        if not draft:
            return None

        return {
            "draft_id": draft_id,
            "tool_name": draft.tool_name,
            "description": draft.description,
            "parameters": draft.parameters,
            "execute_template": draft.execute_template,
            "warnings": draft.validation_warnings,
        }

    def update_draft(self, draft_id: str, updates: Dict) -> bool:
        """更新草稿（用户编辑后）"""
        draft = self.drafts.get(draft_id)
        if not draft:
            return False

        if "execute_template" in updates:
            dangerous = self.scan_dangerous_code(updates["execute_template"])
            if dangerous:
                logger.warning(
                    f"Draft {draft_id} contains dangerous code patterns: {dangerous}"
                )

        draft.execute_template = updates.get("execute_template", draft.execute_template)
        return True

    def install_draft(self, draft_id: str) -> ImportResult:
        """安装草稿为正式技能"""
        draft = self.drafts.get(draft_id)
        if not draft:
            return ImportResult(success=False, error=f"Draft {draft_id} not found")

        dangerous = self.scan_dangerous_code(draft.execute_template)
        if dangerous:
            warning_msgs = [msg for _, msg in dangerous]
            return ImportResult(
                success=False, error="技能包含危险代码模式", warnings=warning_msgs
            )

        skill_code = self.generate_skill_code(draft)
        skill_path = self.skills_dir / f"{draft.tool_name}.py"

        try:
            skill_path.write_text(skill_code, encoding="utf-8")
            logger.info(f"Skill {draft.tool_name} installed to {skill_path}")

            skill_id = f"{draft.tool_name}"
            del self.drafts[draft_id]

            return ImportResult(success=True, skill_id=skill_id, warnings=[])
        except Exception as e:
            return ImportResult(success=False, error=str(e))

    def import_from_json(self, json_str: str) -> Tuple[str, SkillDraft]:
        """从 JSON 字符串导入"""
        try:
            schema = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

        return self.create_draft(schema)

    def import_from_file(self, file_path: str) -> Tuple[str, SkillDraft]:
        """从文件导入"""
        content = Path(file_path).read_text(encoding="utf-8")

        try:
            schema = json.loads(content)
        except json.JSONDecodeError:
            raise ValueError(f"File does not contain valid JSON: {file_path}")

        return self.create_draft(schema)


def create_claude_skill_adapter(skills_dir: str = "skills") -> ClaudeSkillAdapter:
    """创建适配器实例"""
    return ClaudeSkillAdapter(skills_dir=skills_dir)


def import_claude_skill(schema: Dict, skills_dir: str = "skills") -> ImportResult:
    """便捷函数：直接导入 Claude Skill"""
    adapter = create_claude_skill_adapter(skills_dir)
    draft_id, draft = adapter.create_draft(schema)
    return adapter.install_draft(draft_id)
