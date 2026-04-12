import asyncio
from core.base_skill import BaseSkill, SkillInput
from typing import Any

ALLOWED = {"ls", "cat", "echo", "pwd", "python", "pip", "git", "curl", "node"}
BLOCKED = {"rm", "sudo", "chmod", "dd", "mkfs", ":(){ :|:& };:"}


class Skill(BaseSkill):
    async def run(self, input_data: SkillInput) -> Any:
        command = input_data.instruction.strip()
        cmd_name = command.split()[0]

        if cmd_name in BLOCKED:
            raise PermissionError(f"命令 [{cmd_name}] 在黑名单中，拒绝执行")
        if cmd_name not in ALLOWED:
            raise PermissionError(f"命令 [{cmd_name}] 不在白名单中")

        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

        return {
            "command": command,
            "exit_code": proc.returncode,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
        }
