# api_server.py
# HTTP API 服务器，让系统可以非交互式运行

import asyncio
import logging
import os
import yaml
import threading
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from bus.message_bus import MessageBus
from core.orchestrator import Orchestrator
from core.skill_registry import SkillRegistry
from knowledge.knowledge_base import KnowledgeBase
from knowledge.document_loader import DocumentLoader
from providers.provider_registry import ProviderRegistry
from session.session_store import SessionStore
from session.session_manager import SessionManager

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

app = Flask(__name__)
CORS(app)

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


def _load_agents_config():
    if AGENTS_CONFIG_PATH.exists():
        with open(AGENTS_CONFIG_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


# 全局状态
state = {
    "orchestrator": None,
    "agents": [],
    "bus": None,
    "provider_registry": None,
    "session_manager": None,
    "kb": None,
    "loader": None,
    "ready": False,
}


async def init_system():
    """初始化所有组件"""
    bus = MessageBus()
    skill_registry = SkillRegistry()
    provider_registry = ProviderRegistry()
    session_store = SessionStore()
    session_manager = SessionManager(session_store)

    kb = None
    loader = None
    try:
        kb = KnowledgeBase(qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"))
        await kb.init()
        loader = DocumentLoader(kb)
        print("🧠 知识库已就绪（Qdrant）")
    except Exception as e:
        print(f"⚠️ 知识库不可用，跳过：{e}")

    orchestrator = Orchestrator(
        bus=bus,
        provider_registry=provider_registry,
        session_manager=session_manager,
    )

    agents = [orchestrator]
    agents_config = _load_agents_config()

    for agent_cfg in agents_config.get("agents", []):
        agent_id = agent_cfg.get("id")
        class_path = AGENT_CLASSES.get(agent_id)
        if not class_path:
            continue

        try:
            AgentClass = _import_agent_class(class_path)
            agent = AgentClass(
                bus=bus,
                provider_registry=provider_registry,
                registry=skill_registry,
                knowledge=kb,
            )
            agents.append(agent)
            logging.info(f"✅ Agent [{agent_id}] 已创建")
        except Exception as e:
            logging.error(f"创建 Agent [{agent_id}] 失败: {e}")

    await asyncio.gather(*[a.start() for a in agents])

    state.update(
        {
            "orchestrator": orchestrator,
            "agents": agents,
            "bus": bus,
            "provider_registry": provider_registry,
            "session_manager": session_manager,
            "kb": kb,
            "loader": loader,
            "ready": True,
        }
    )
    print(f"🚀 Multi-Agent 系统已启动（{len(agents) - 1} 个工作 Agent）")


def _get_event_loop():
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        return asyncio.new_event_loop()


# ── API 路由 ─────────────────────────────────────


@app.route("/health")
def health():
    return jsonify({"status": "ok", "ready": state["ready"]})


@app.route("/task", methods=["POST"])
def run_task():
    if not state["ready"]:
        return jsonify({"error": "系统未就绪"}), 503

    data = request.json or {}
    user_input = data.get("input", "")
    session_id = data.get("session_id")

    if not user_input:
        return jsonify({"error": "input 为空"}), 400

    loop = _get_event_loop()
    result = loop.run_until_complete(state["orchestrator"].run(user_input, session_id))
    sid = state["session_manager"].current_session_id
    return jsonify(
        {
            "result": result,
            "session_id": sid,
        }
    )


@app.route("/sessions")
def list_sessions():
    if not state["ready"]:
        return jsonify({"error": "系统未就绪"}), 503
    sessions = state["session_manager"].list_sessions()
    return jsonify({"sessions": sessions})


@app.route("/providers")
def list_providers():
    if not state["ready"]:
        return jsonify({"error": "系统未就绪"}), 503
    providers = state["provider_registry"].list_all()
    return jsonify({"providers": providers})


@app.route("/debug/provider")
def debug_provider():
    if not state["ready"]:
        return jsonify({"error": "系统未就绪"}), 503
    pr = state["provider_registry"]
    active = pr.get()
    return jsonify(
        {
            "active_id": pr.active_id,
            "active_provider": active.provider_id,
            "active_model": getattr(active, "model", "unknown"),
            "all_providers": [
                {"id": p.provider_id, "name": p.name}
                for p in [
                    pr.get(pid) for pid in ["anthropic_claude", "siliconflow-chat"]
                ]
            ],
        }
    )


@app.route("/provider/<pid>", methods=["POST"])
def switch_provider(pid):
    if not state["ready"]:
        return jsonify({"error": "系统未就绪"}), 503
    state["provider_registry"].use(pid)
    return jsonify({"active": pid})


@app.route("/knowledge/load", methods=["POST"])
def load_knowledge():
    if not state["ready"]:
        return jsonify({"error": "系统未就绪"}), 503
    if state["loader"] is None:
        return jsonify({"error": "知识库未初始化"}), 503

    data = request.json or {}
    url = data.get("url")
    agent_ids = data.get("agent_ids", [])
    topic = data.get("topic", "general")

    loop = _get_event_loop()
    count = loop.run_until_complete(state["loader"].from_url(url, agent_ids, topic))
    return jsonify({"count": count})


@app.route("/skills", methods=["GET"])
def list_skills():
    from core.skill_registry import SkillRegistry

    reg = SkillRegistry()
    skills = reg.list_all()
    return jsonify({"skills": skills})


if __name__ == "__main__":

    def run_async():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(init_system())
        loop.run_forever()

    t = threading.Thread(target=run_async, daemon=True)
    t.start()

    import time

    for _ in range(30):
        if state["ready"]:
            break
        time.sleep(0.5)

    print(f"🌐 API 服务器启动在 http://0.0.0.0:8891")
    app.run(host="0.0.0.0", port=8891, debug=False, threaded=True)
