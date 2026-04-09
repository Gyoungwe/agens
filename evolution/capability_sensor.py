# evolution/capability_sensor.py

import logging

logger = logging.getLogger(__name__)

CAPABILITY_MAP = {
    "发邮件":   ("email_sender",  "发送电子邮件"),
    "邮件":     ("email_sender",  "发送电子邮件"),
    "数据库":   ("db_query",      "执行 SQL 查询"),
    "sql":      ("db_query",      "执行 SQL 查询"),
    "画图":     ("chart_maker",  "生成数据图表"),
    "图表":     ("chart_maker",  "生成数据图表"),
    "翻译":     ("translator",   "多语言翻译"),
    "日历":     ("calendar",     "日历事件管理"),
    "定时":     ("scheduler",     "定时任务调度"),
    "截图":     ("screenshot",   "网页截图"),
    "ocr":      ("ocr_reader",   "图片文字识别"),
    "slack":    ("slack_bot",   "Slack 消息发送"),
    "钉钉":     ("dingtalk_bot", "钉钉消息发送"),
    "微信":     ("wechat_bot",   "微信消息推送"),
    "notion":   ("notion_api",  "Notion 文档操作"),
    "jira":     ("jira_api",    "Jira 任务管理"),
}


class CapabilitySensor:
    """能力边界感知器，检测指令中需要但尚未安装的技能"""

    def __init__(self, registry):
        self.registry = registry

    def detect_missing(
        self,
        instruction: str,
        agent_id: str,
    ) -> list[dict]:
        """返回缺失技能列表"""
        available = {s.skill_id for s in self.registry.get_for_agent(agent_id)}
        instruction_lower = instruction.lower()
        missing = {}

        for keyword, (skill_id, reason) in CAPABILITY_MAP.items():
            if keyword in instruction_lower and skill_id not in available:
                if skill_id not in missing:
                    missing[skill_id] = {
                        "skill_id": skill_id,
                        "reason":   reason,
                        "keyword":  keyword,
                    }

        result = list(missing.values())
        if result:
            logger.info(
                f"🔍 [{agent_id}] 检测到 {len(result)} 个缺失技能: "
                f"{[r['skill_id'] for r in result]}"
            )
        return result
