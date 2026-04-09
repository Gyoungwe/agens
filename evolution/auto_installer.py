# evolution/auto_installer.py

import asyncio
import logging
from evolution.capability_sensor import CapabilitySensor
from evolution.request_generator import RequestGenerator

logger = logging.getLogger(__name__)


class AutoInstaller:
    """
    自动安装器。

    职责：
    1. 监听审批队列，发现 approved 状态自动安装
    2. 为 Agent 提供 evolve() 接口
    """

    def __init__(self, registry, installer, queue, provider_registry=None):
        self.registry = registry
        self.installer = installer
        self.queue = queue
        self.sensor = CapabilitySensor(registry)
        self.generator = RequestGenerator(provider_registry=provider_registry)
        self._running = False

    async def evolve(
        self,
        agent_id: str,
        instruction: str,
    ) -> dict:
        """Agent 在执行前调用此方法"""
        missing = self.sensor.detect_missing(instruction, agent_id)

        if not missing:
            return {
                "can_proceed": True,
                "missing": [],
                "submitted": [],
                "installed": [],
                "message": "技能完备，可以执行",
            }

        submitted, installed = [], []

        for item in missing:
            skill_id = item["skill_id"]

            approved = [
                a
                for a in self.queue.list_approved()
                if a["skill_id"] == skill_id and a["agent_id"] == agent_id
            ]

            if approved:
                approval = approved[0]
                success = await self.installer.install(skill_id, [agent_id])
                if success:
                    self.queue.mark_installed(approval["id"])
                    installed.append(skill_id)
                    logger.info(f"🚀 自动安装: [{skill_id}] for [{agent_id}]")
            else:
                request = await self.generator.generate(
                    agent_id=agent_id,
                    skill_id=skill_id,
                    instruction=instruction,
                    reason=item["reason"],
                )
                self.queue.submit(request)
                submitted.append(skill_id)

        still_missing = self.sensor.detect_missing(instruction, agent_id)
        can_proceed = len(still_missing) == 0

        message_parts = []
        if installed:
            message_parts.append(f"✅ 已自动安装: {', '.join(installed)}")
        if submitted:
            message_parts.append(
                f"📬 已提交审批: {', '.join(submitted)}（等待管理员审批后生效）"
            )

        return {
            "can_proceed": can_proceed,
            "missing": [m["skill_id"] for m in still_missing],
            "submitted": submitted,
            "installed": installed,
            "message": "\n".join(message_parts) or "处理完成",
        }

    async def start_watcher(self, interval: int = 30):
        """后台任务：每隔 interval 秒检查 approved 队列并自动安装"""
        self._running = True
        logger.info(f"👀 审批监听器已启动（间隔 {interval}s）")

        while self._running:
            try:
                approved = self.queue.list_approved()
                for approval in approved:
                    success = await self.installer.install(
                        approval["skill_id"], [approval["agent_id"]]
                    )
                    if success:
                        self.queue.mark_installed(approval["id"])
                        logger.info(
                            f"🚀 后台自动安装: [{approval['skill_id']}] "
                            f"for [{approval['agent_id']}]"
                        )
            except Exception as e:
                logger.error(f"审批监听器异常: {e}")

            await asyncio.sleep(interval)

    def stop_watcher(self):
        self._running = False
