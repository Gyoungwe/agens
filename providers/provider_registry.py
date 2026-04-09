# providers/provider_registry.py
"""
Provider 注册中心

管理多个 LLM Provider，支持按 ID 切换

默认 Provider: minimax_m2
"""

import asyncio
import yaml
import logging
import os
from pathlib import Path
from typing import Dict, Dict as TypingDict
from providers.base_provider import BaseProvider

logger = logging.getLogger(__name__)

import sys

# 内置 Provider 配置（使用环境变量）
BUILTIN_PROFILES = """
default: siliconflow

profiles:
  - id: minimax_m2
    type: openai
    name: MiniMax M2.7
    model: MiniMax-M2.7
    base_url: https://api.minimaxi.com/v1
    api_key: ${MINIMAX_API_KEY}

  - id: siliconflow
    type: openai
    name: SiliconFlow (Qwen)
    model: Qwen/Qwen2.5-7B-Instruct
    base_url: https://api.siliconflow.cn/v1
    api_key: ${SILICONFLOW_API_KEY}

  - id: anthropic_claude3sonnet
    type: anthropic
    name: Anthropic Claude 3 Sonnet
    model: claude-3-sonnet-20240229
    api_key: ${ANTHROPIC_API_KEY}

  - id: anthropic_claude3haiku
    type: anthropic
    name: Anthropic Claude 3 Haiku
    model: claude-3-haiku-20240307
    api_key: ${ANTHROPIC_API_KEY}

  - id: deepseek
    type: openai
    name: DeepSeek
    model: deepseek-chat
    base_url: https://api.deepseek.com/v1
    api_key: ${DEEPSEEK_API_KEY}

  - id: volcengine
    type: openai
    name: 火山引擎方舟 (Doubao)
    model: ${VOLCENGINE_PLAN_ID:093c16f4-86d5-4cbb-833a-37bfb1d448bf}:doubao-pro-32k
    base_url: https://ark.cn-beijing.volces.com/api/v3
    api_key: ${VOLCENGINE_API_KEY}
"""

if getattr(sys, "frozen", False):
    PROFILES_PATH = Path(sys._MEIPASS) / "providers" / "profiles.yaml"
else:
    PROFILES_PATH = Path(__file__).parent / "profiles.yaml"


class ProviderRegistry:
    """
    Provider 注册中心

    从 profiles.yaml 加载配置，支持按 profile_id 切换当前 Provider
    """

    def __init__(self):
        self._providers: Dict[str, BaseProvider] = {}
        self._profiles: Dict[str, dict] = {}
        self._active: str = ""
        self._load_profiles()

    def _load_profiles(self):
        config = None

        if PROFILES_PATH.exists():
            try:
                config = yaml.safe_load(PROFILES_PATH.read_text(encoding="utf-8"))
                logger.info(f"✅ 已加载配置文件: {PROFILES_PATH}")
            except Exception as e:
                logger.warning(f"配置文件加载失败: {e}，使用内置配置")
                config = None

        if config is None:
            try:
                config = yaml.safe_load(BUILTIN_PROFILES)
                logger.info("✅ 使用内置 Provider 配置")
            except Exception as e:
                logger.error(f"内置配置加载失败: {e}")
                self._register_default()
                return

        default = config.get("default", "")

        for profile in config.get("profiles", []):
            pid = profile.get("id", "unknown")
            try:
                api_key_raw = profile.get("api_key", "")
                api_key = self._resolve_env(api_key_raw)

                if not api_key:
                    logger.warning(f"⏭️ Provider [{pid}] API Key 为空，跳过")
                    continue

                logger.info(f"🔧 正在加载 Provider [{pid}]")
                provider = self._build_provider(profile)
                self._providers[pid] = provider
                logger.info(f"✅ Provider [{pid}] 已加载")
            except Exception as e:
                logger.error(f"Provider [{pid}] 加载失败: {e}")

        if default and default in self._providers:
            self._active = default
        elif self._providers:
            self._active = next(iter(self._providers))
        else:
            logger.error("没有可用的 Provider")
            self._register_default()
            return

        logger.info(f"🎯 当前激活 Provider: [{self._active}]")

    def _resolve_env(self, value):
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            default_val = None
            if ":" in env_var:
                env_var, default_val = env_var.split(":", 1)
            return os.getenv(env_var, default_val or "")
        return value

    def _build_provider(self, profile: dict) -> BaseProvider:
        ptype = profile.get("type", "anthropic")
        if ptype == "anthropic":
            from providers.anthropic_provider import AnthropicProvider

            return AnthropicProvider(
                api_key=self._resolve_env(profile.get("api_key") or ""),
                model=profile.get("model", "claude-sonnet-4-5"),
            )
        elif ptype == "openai":
            from providers.openai_provider import OpenAIProvider

            return OpenAIProvider(
                api_key=self._resolve_env(profile.get("api_key") or ""),
                model=profile.get("model", "gpt-4o"),
                base_url=self._resolve_env(profile.get("base_url") or ""),
            )
        else:
            raise ValueError(f"未知 Provider 类型: {ptype}")

    def _register_default(self):
        from providers.anthropic_provider import AnthropicProvider

        self._providers["default"] = AnthropicProvider()
        self._active = "default"

    # ── 公开 API ─────────────────────────────────

    def get(self, profile_id: str = None) -> BaseProvider:
        pid = profile_id or self._active
        if pid not in self._providers:
            logger.error(
                f"Provider [{pid}] 未注册，可用: {list(self._providers.keys())}"
            )
            raise ValueError(
                f"Provider [{pid}] 未注册，可用: {list(self._providers.keys())}"
            )
        return self._providers[pid]

    def use(self, profile_id: str):
        if profile_id not in self._providers:
            logger.error(f"Provider [{profile_id}] 未注册")
            raise ValueError(
                f"Provider [{profile_id}] 未注册，可用: {list(self._providers.keys())}"
            )
        self._active = profile_id
        logger.info(f"🔄 切换 Provider → [{profile_id}]")

    def list_all(self) -> list[dict]:
        return [
            {"id": pid, "name": p.name, "active": pid == self._active}
            for pid, p in self._providers.items()
        ]

    @property
    def profiles(self) -> Dict[str, dict]:
        """返回所有 profile 配置（用于动态添加/删除）"""
        return self._profiles

    @profiles.setter
    def profiles(self, value: Dict[str, dict]):
        """设置 profile 配置"""
        self._profiles = value

    def add(self, profile_id: str, provider: BaseProvider, profile: dict):
        """动态添加 Provider"""
        self._providers[profile_id] = provider
        self._profiles[profile_id] = profile
        logger.info(f"✅ 动态添加 Provider: {profile_id}")

    def remove(self, profile_id: str):
        """动态删除 Provider（删除前检查引用）"""
        if profile_id == self._active:
            raise ValueError(f"Cannot remove active Provider [{profile_id}]")

        if profile_id not in self._providers and profile_id not in self._profiles:
            logger.warning(f"Provider [{profile_id}] not found, skip removal")
            return

        del self._providers[profile_id]
        if profile_id in self._profiles:
            del self._profiles[profile_id]
        logger.info(f"🗑️ 删除 Provider: {profile_id}")

    async def health_check_all(self) -> Dict[str, bool]:
        """启动时检查所有 Provider 健康状态"""
        results = {}
        for pid, provider in self._providers.items():
            try:
                results[pid] = await asyncio.wait_for(
                    provider.health_check(), timeout=5.0
                )
            except asyncio.TimeoutError:
                logger.warning(f"Provider [{pid}] health check timeout")
                results[pid] = False
            except Exception as e:
                logger.warning(f"Provider [{pid}] health check failed: {e}")
                results[pid] = False
        return results

    @property
    def active_id(self) -> str:
        return self._active

    @property
    def active_name(self) -> str:
        return self._providers[self._active].name if self._active else ""

    @property
    def active_model(self) -> str:
        p = self._providers.get(self._active)
        return getattr(p, "model", "") if p else ""
