# main.py

import asyncio
import logging
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

from bus.message_bus import MessageBus
from core.orchestrator import Orchestrator
from core.base_agent import BaseAgent
from core.skill_registry import SkillRegistry
from core.hooks import HookRegistry, ApprovalHook, LoggingHook, RateLimitHook
from knowledge.knowledge_base import KnowledgeBase
from knowledge.document_loader import DocumentLoader
from providers.provider_registry import ProviderRegistry
from session.session_store import SessionStore
from session.session_manager import SessionManager
from memory.vector_store import VectorStore
from memory.context_compressor import ContextCompressor
from memory.session_memory import SessionMemory
from evolution.approval_queue import ApprovalQueue
from evolution.auto_installer import AutoInstaller
from installer.skill_installer import SkillInstaller

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

AGENTS_CONFIG_PATH = Path("config/agents.yaml")
AGENT_CLASSES = {
    "research_agent": "agents.research_agent.research_agent.ResearchAgent",
    "executor_agent": "agents.executor_agent.executor_agent.ExecutorAgent",
    "writer_agent": "agents.writer_agent.writer_agent.WriterAgent",
}


def _import_agent_class(class_path: str):
    module_path, class_name = class_path.rsplit(".", 1)
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, class_name)


async def main():
    # ── 1. 基础设施 ───────────────────────────────
    bus = MessageBus()
    skill_registry = SkillRegistry()
    provider_registry = ProviderRegistry()
    session_store = SessionStore()
    session_manager = SessionManager(session_store)

    # ── 2. 会话记忆系统（向量存储 + 上下文压缩）─────
    vector_store = None
    context_compressor = None
    try:
        vector_store = VectorStore(db_path="./data/memory")
        context_compressor = ContextCompressor(
            provider=provider_registry.get(),
            max_messages=10,
            compress_threshold=20,
        )
        session_memory = SessionMemory(
            vector_store=vector_store,
            compressor=context_compressor,
            max_messages=10,
            compress_threshold=20,
        )
        session_manager.set_memory(session_memory)
        print("🧠 会话记忆系统已就绪（VectorStore + ContextCompressor）")
    except Exception as e:
        print(f"⚠️ 会话记忆系统不可用，跳过：{e}")
        vector_store = None
        context_compressor = None

    # ── 3. 知识库（可选，Qdrant 不可用时跳过）────────
    kb = None
    loader = None
    try:
        kb = KnowledgeBase(
            qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        )
        await kb.init()
        loader = DocumentLoader(kb)
        print("📚 知识库已就绪（Qdrant）")
    except Exception as e:
        print(f"⚠️ 知识库不可用，跳过：{e}")
        kb = None

    # ── 4. 自我进化系统（审批队列 + 自动安装器）─────
    approval_queue = None
    auto_installer = None
    try:
        approval_queue = ApprovalQueue(db_path=Path("./data/approvals.db"))
        skill_installer = SkillInstaller(registry=skill_registry)
        auto_installer = AutoInstaller(
            registry=skill_registry,
            installer=skill_installer,
            queue=approval_queue,
            provider_registry=provider_registry,
        )
        print("🔄 自我进化系统已就绪（ApprovalQueue + AutoInstaller）")
    except Exception as e:
        print(f"⚠️ 自我进化系统不可用，跳过：{e}")
        approval_queue = None
        auto_installer = None

    # ── 5. Hook 系统 ───────────────────────────────
    hook_registry = HookRegistry()
    try:
        hook_registry.register(LoggingHook())
        hook_registry.register(RateLimitHook(max_calls_per_minute=60))
        if approval_queue:
            hook_registry.register(ApprovalHook(approval_queue))
        print("🔗 Hook 系统已就绪")
    except Exception as e:
        print(f"⚠️ Hook 系统不可用，跳过：{e}")

    # ── 6. 动态创建 Agent ──────────────────────────
    agents_config = {}
    if AGENTS_CONFIG_PATH.exists():
        with open(AGENTS_CONFIG_PATH, encoding="utf-8") as f:
            agents_config = yaml.safe_load(f) or {}

    orchestrator = Orchestrator(
        bus=bus,
        provider_registry=provider_registry,
        session_manager=session_manager,
        context_compressor=context_compressor,
    )
    all_agents = [orchestrator]

    for agent_cfg in agents_config.get("agents", []):
        agent_id = agent_cfg.get("id")
        class_path = AGENT_CLASSES.get(agent_id)
        if not class_path:
            logging.warning(f"未知 Agent 类型: {agent_id}，跳过")
            continue

        try:
            AgentClass = _import_agent_class(class_path)
            agent = AgentClass(
                bus=bus,
                provider_registry=provider_registry,
                registry=skill_registry,
                knowledge=kb,
                auto_installer=auto_installer,
            )
            agent.set_hook_registry(hook_registry)
            all_agents.append(agent)
            logging.info(f"✅ Agent [{agent_id}] 已创建")
        except Exception as e:
            logging.error(f"创建 Agent [{agent_id}] 失败: {e}")

    # ── 4. 全部启动 ───────────────────────────────
    await asyncio.gather(*[a.start() for a in all_agents])

    print("\n🚀 Multi-Agent 系统已启动")
    print(f"🎯 当前 Provider: [{provider_registry.active_id}]")
    print(f"🤖 已加载 {len(all_agents) - 1} 个工作 Agent")
    print(
        "命令：/resume <session_id> | /sessions | /provider <id> | /load <url> | exit\n"
    )

    current_session = None

    try:
        while True:
            user_input = input("📝 你的任务: ").strip()

            if not user_input or user_input.lower() in ("exit", "q"):
                break

            if user_input.startswith("/resume "):
                sid = user_input.split(" ", 1)[1].strip()
                current_session = sid
                print(f"✅ 已切换到会话: {sid[:8]}...")
                continue

            if user_input == "/sessions":
                for s in session_manager.list_sessions()[:10]:
                    print(
                        f"  [{s['status']}] {s['session_id'][:8]}... "
                        f"| {s['title']} | {s['updated_at'][:16]}"
                    )
                continue

            if user_input.startswith("/provider "):
                pid = user_input.split(" ", 1)[1].strip()
                provider_registry.use(pid)
                print(f"✅ 已切换 Provider: {pid}")
                continue

            if user_input.startswith("/load "):
                url = user_input.split(" ", 1)[1].strip()
                if loader:
                    count = await loader.from_url(url)
                    print(f"✅ 已导入 {count} 个知识块")
                else:
                    print("⚠️ 知识库未初始化，无法导入")
                continue

            result = await orchestrator.run(
                user_input=user_input,
                session_id=current_session,
            )
            current_session = session_manager.current_session_id

            print(f"\n{'=' * 50}")
            print(f"🎯 结果:\n{result}")
            print(f"📌 会话 ID: {current_session[:8]}...")
            print(f"{'=' * 50}\n")

    finally:
        session_manager.close()
        await asyncio.gather(*[a.stop() for a in all_agents])
        print("👋 系统已关闭")


if __name__ == "__main__":
    asyncio.run(main())
