# installer/nl_installer.py

import json
import logging
import os
from typing import List
from installer.skill_installer import SkillInstaller

logger = logging.getLogger(__name__)

INTENT_PROMPT = """你是一个技能安装助手，负责解析用户的自然语言请求。

用户可能说：
- "帮我安装一个能查天气的技能"
- "给 research_agent 装一个 PDF 阅读器"
- "卸载 shell 技能"
- "查一下有没有发邮件的技能"

输出 JSON 格式：
{
  "action":     "install" | "uninstall" | "search" | "list" | "unknown",
  "skill_id":   "推断出的技能ID，没有则为空字符串",
  "keywords":   ["搜索关键词列表"],
  "agent_ids":  ["目标 agent_id 列表，没有指定则为空"],
  "confidence": 0.0~1.0,
  "reason":     "你的推断理由"
}

只输出 JSON，不要其他内容。"""


class NLInstaller:
    """自然语言技能安装器"""

    def __init__(
        self,
        skill_registry,
        skill_installer: SkillInstaller,
        provider_registry=None,
        provider=None,
    ):
        self.registry = skill_registry
        self.installer = skill_installer
        if provider_registry:
            self.provider = provider_registry.get()
        elif provider:
            self.provider = provider
        else:
            from providers.anthropic_provider import AnthropicProvider

            self.provider = AnthropicProvider()

    async def handle(self, user_input: str) -> dict:
        """处理自然语言输入"""
        from providers.base_provider import ChatMessage

        intent = await self._parse_intent(user_input)
        logger.info(f"🧠 意图解析: {intent}")

        action = intent.get("action", "unknown")

        if action == "search":
            return await self._do_search(intent)
        elif action == "list":
            return self._do_list()
        elif action == "install":
            return await self._do_install(intent)
        elif action == "uninstall":
            return await self._do_uninstall(intent)
        else:
            return {
                "action": "unknown",
                "success": False,
                "message": f"无法理解指令：{user_input}",
                "needs_confirm": False,
                "data": {},
            }

    async def _parse_intent(self, user_input: str) -> dict:
        from providers.base_provider import ChatMessage

        resp = await self.provider.chat(
            messages=[ChatMessage(role="user", content=user_input)],
            system=INTENT_PROMPT,
            max_tokens=512,
        )
        raw = resp.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.error(f"意图解析 JSON 失败: {raw}")
            return {"action": "unknown", "keywords": [], "skill_id": ""}

    async def _do_search(self, intent: dict) -> dict:
        keywords = intent.get("keywords", [])
        query = " ".join(keywords) if keywords else intent.get("skill_id", "")
        results = await self.installer.search(query)

        if not results:
            return {
                "action": "search",
                "success": True,
                "message": f"未找到与「{query}」相关的技能",
                "needs_confirm": False,
                "data": {"results": []},
            }

        lines = [f"🔍 找到 {len(results)} 个相关技能：\n"]
        for r in results:
            lines.append(
                f"  📦 {r['skill_id']}  —  {r['name']}\n"
                f"     {r['description']}\n"
                f"     版本: {r['version']}  |  下载量: {r.get('downloads', 0)}\n"
            )
        return {
            "action": "search",
            "success": True,
            "message": "\n".join(lines),
            "needs_confirm": False,
            "data": {"results": results},
        }

    async def _do_install(self, intent: dict) -> dict:
        skill_id = intent.get("skill_id", "")
        agent_ids = intent.get("agent_ids", [])

        existing = self.registry.get(skill_id)
        if existing:
            return {
                "action": "install",
                "success": True,
                "message": f"✅ 技能 [{skill_id}] 已安装，执行热重载",
                "needs_confirm": False,
                "data": {"skill_id": skill_id, "action": "reload"},
            }

        preview = (
            f"📦 即将安装技能：{skill_id}\n"
            f"   目标 Agent：{', '.join(agent_ids) if agent_ids else '全部'}\n"
            f"   来源：ClawHub\n"
        )
        return {
            "action": "install",
            "success": None,
            "message": preview,
            "needs_confirm": True,
            "data": {"skill_id": skill_id, "agent_ids": agent_ids},
        }

    async def confirm_install(self, skill_id: str, agent_ids: List[str]) -> dict:
        success = await self.installer.install(skill_id, agent_ids)
        return {
            "action": "install",
            "success": success,
            "message": (
                f"✅ 技能 [{skill_id}] 安装成功"
                if success
                else f"❌ 技能 [{skill_id}] 安装失败"
            ),
            "needs_confirm": False,
            "data": {"skill_id": skill_id},
        }

    async def _do_uninstall(self, intent: dict) -> dict:
        skill_id = intent.get("skill_id", "")
        if not skill_id:
            return {
                "action": "uninstall",
                "success": False,
                "message": "未能识别要卸载的技能名称",
                "needs_confirm": False,
                "data": {},
            }
        self.installer.uninstall(skill_id, delete_files=False)
        return {
            "action": "uninstall",
            "success": True,
            "message": f"✅ 技能 [{skill_id}] 已卸载（文件保留）",
            "needs_confirm": False,
            "data": {"skill_id": skill_id},
        }

    def _do_list(self) -> dict:
        skills = self.registry.list_all()
        if not skills:
            return {
                "action": "list",
                "success": True,
                "message": "暂无已安装技能",
                "needs_confirm": False,
                "data": {"skills": []},
            }
        lines = [f"📦 已安装 {len(skills)} 个技能：\n"]
        for s in skills:
            status = "✅" if s["enabled"] else "❌"
            lines.append(f"  {status} {s['skill_id']}  —  {s['name']}")
        return {
            "action": "list",
            "success": True,
            "message": "\n".join(lines),
            "needs_confirm": False,
            "data": {"skills": skills},
        }
