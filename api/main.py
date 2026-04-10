# api/main.py
"""
FastAPI 后端 - Multi-Agent 系统 REST API

启动方式:
    python -m uvicorn api.main:app --reload --port 8000
"""

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager
from datetime import datetime
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from sse_starlette import EventSourceResponse

from api.routers import (
    skill_router,
    agent_router,
    soul_router,
    evolution_router,
    memory_router,
)
from api.auth import router as auth_router
from api.ws.events import websocket_endpoint
from utils.feature_logs import setup_feature_loggers, get_feature_logger

LOG_DIR = Path("./logs")
LOG_DIR.mkdir(exist_ok=True)


def setup_logging():
    today = datetime.now().strftime("%Y%m%d")
    log_file = LOG_DIR / f"agens_{today}.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logging.info(f"📝 日志文件: {log_file.absolute()}")
    feature_loggers = setup_feature_loggers(LOG_DIR)
    for feature in feature_loggers:
        logging.info(f"🧩 功能日志: {feature} -> {(LOG_DIR / 'features').absolute()}")
    return log_file


logger = logging.getLogger(__name__)


def _resolve_feature_from_path(path: str) -> str:
    p = (path or "").strip("/")
    if not p:
        return "system"
    first = p.split("/")[0]
    if first == "api" and len(p.split("/")) > 1:
        first = p.split("/")[1]

    mapping = {
        "auth": "auth",
        "chat": "chat",
        "sessions": "sessions",
        "providers": "providers",
        "agents": "agents",
        "skills": "skills",
        "memory": "memory",
        "evolution": "evolution",
        "hooks": "hooks",
        "traces": "traces",
        "ws": "ws",
    }
    return mapping.get(first, "system")


# ═══════════════════════════════════════════════════════════════════
# Pydantic 模型
# ═══════════════════════════════════════════════════════════════════


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    use_collaboration: bool = False


class ChatResponse(BaseModel):
    response: str
    session_id: str
    provider: str


class SessionInfo(BaseModel):
    session_id: str
    title: str
    status: str
    created_at: str
    updated_at: str
    message_count: int


class ProviderInfo(BaseModel):
    id: str
    name: str
    model: str
    active: bool


class SkillInfo(BaseModel):
    skill_id: str
    name: str
    description: str
    version: str
    tags: List[str]
    enabled: bool


class HealthResponse(BaseModel):
    status: str
    provider: str
    model: str
    providers_available: int
    skills_count: int
    memory_count: int


# ═══════════════════════════════════════════════════════════════════
# 全局状态
# ═══════════════════════════════════════════════════════════════════


class AgentSystemState:
    def __init__(self):
        self._initialized = False
        self._initializing = False

        # Lazy imports - only load when needed
        self._bus = None
        self._orchestrator = None
        self._provider_registry = None
        self._skill_registry = None
        self._hook_registry = None
        self._session_manager = None
        self._vector_store = None
        self._context_compressor = None
        self._knowledge_base = None
        self._all_agents = []  # 存储所有 Agent

    @property
    def all_agents(self):
        return self._all_agents

    @property
    def bus(self):
        return self._bus

    @property
    def orchestrator(self):
        return self._orchestrator

    @property
    def provider_registry(self):
        return self._get_provider_registry()

    @property
    def skill_registry(self):
        return self._get_skill_registry()

    @property
    def hook_registry(self):
        return self._get_hook_registry()

    @property
    def session_manager(self):
        return self._get_session_manager()

    @property
    def vector_store(self):
        return self._get_vector_store()

    @property
    def knowledge_base(self):
        return self._get_knowledge_base()

    def _get_provider_registry(self):
        if self._provider_registry is None:
            from providers.provider_registry import ProviderRegistry

            self._provider_registry = ProviderRegistry()
        return self._provider_registry

    def _get_skill_registry(self):
        if self._skill_registry is None:
            from core.skill_registry import SkillRegistry

            self._skill_registry = SkillRegistry()
        return self._skill_registry

    def _get_hook_registry(self):
        if self._hook_registry is None:
            from core.hooks import (
                HookRegistry,
                LoggingHook,
                RateLimitHook,
                ApprovalHook,
            )
            from core.integration_hooks import SafetyGuardHook, MLflowHook

            self._hook_registry = HookRegistry()
            self._hook_registry.register(LoggingHook())
            self._hook_registry.register(RateLimitHook(max_calls_per_minute=60))
            self._hook_registry.register(ApprovalHook())
            self._hook_registry.register(SafetyGuardHook())
            self._hook_registry.register(MLflowHook())
        return self._hook_registry

    def _get_session_manager(self):
        if self._session_manager is None:
            from session.session_store import SessionStore
            from session.session_manager import SessionManager
            from memory.vector_store import VectorStore
            from memory.context_compressor import ContextCompressor
            from memory.session_memory import SessionMemory

            session_store = SessionStore()
            self._session_manager = SessionManager(session_store)

            vector_store = VectorStore(db_path="./data/memory")
            context_compressor = ContextCompressor(
                provider=self._get_provider_registry().get(),
                max_messages=10,
                compress_threshold=20,
            )
            session_memory = SessionMemory(
                vector_store=vector_store,
                compressor=context_compressor,
                max_messages=10,
                compress_threshold=20,
            )
            self._session_manager.set_memory(session_memory)
            self._vector_store = vector_store

        return self._session_manager

    def _get_vector_store(self):
        if self._vector_store is None:
            from memory.vector_store import VectorStore

            self._vector_store = VectorStore(db_path="./data/memory")
        return self._vector_store

    def _get_knowledge_base(self):
        if self._knowledge_base is None:
            from knowledge.knowledge_base import KnowledgeBase

            self._knowledge_base = KnowledgeBase(db_path="./data/knowledge")
        return self._knowledge_base

    def _get_orchestrator(self):
        if self._orchestrator is None:
            logger.info("🚀 [_get_orchestrator] 创建新 Orchestrator 实例")
            from core.orchestrator import Orchestrator

            self._orchestrator = Orchestrator(
                bus=self._bus or self._get_bus(),
                provider_registry=self._get_provider_registry(),
                session_manager=self._get_session_manager(),
                context_compressor=self._get_session_manager()._memory.compressor
                if self._get_session_manager()._memory
                else None,
            )
        return self._orchestrator

    def _get_bus(self):
        if self._bus is None:
            from bus.message_bus import MessageBus

            self._bus = MessageBus()
        return self._bus

    async def _init_agents(self):
        """初始化并注册所有工作 Agent"""
        if self._all_agents:
            return  # 已初始化

        bus = self._get_bus()

        # 创建 Orchestrator
        orchestrator = self._get_orchestrator()
        self._all_agents.append(orchestrator)

        # Agent 配置
        AGENT_CLASSES = {
            "research_agent": "agents.research_agent.research_agent.ResearchAgent",
            "executor_agent": "agents.executor_agent.executor_agent.ExecutorAgent",
            "writer_agent": "agents.writer_agent.writer_agent.WriterAgent",
        }

        import importlib

        for agent_id, class_path in AGENT_CLASSES.items():
            try:
                module_path, class_name = class_path.rsplit(".", 1)
                module = importlib.import_module(module_path)
                AgentClass = getattr(module, class_name)

                agent = AgentClass(
                    bus=bus,
                    provider_registry=self._get_provider_registry(),
                    registry=self._get_skill_registry(),
                    knowledge=self._knowledge_base,
                    auto_installer=None,
                )
                agent.set_hook_registry(self._hook_registry)

                self._all_agents.append(agent)
                logger.info(f"✅ Agent [{agent_id}] 已创建")
            except Exception as e:
                logger.error(f"创建 Agent [{agent_id}] 失败: {e}")

        # 启动所有 Agent
        await self._start_agents()

    async def _start_agents(self):
        """启动所有 Agent"""
        for agent in self._all_agents:
            try:
                await agent.start()
            except Exception as e:
                logger.error(f"启动 Agent {agent.agent_id} 失败: {e}")

    async def initialize_async(self):
        if self._initialized or self._initializing:
            logger.info("initialize_async: 已初始化或正在初始化，跳过")
            return
        self._initializing = True
        logger.info("🚀 [initialize_async] 开始初始化...")
        try:
            # 触发所有属性的初始化
            logger.info("🚀 [initialize_async] 初始化 provider_registry...")
            _ = self.provider_registry
            logger.info("🚀 [initialize_async] 初始化 skill_registry...")
            _ = self.skill_registry
            logger.info("🚀 [initialize_async] 初始化 hook_registry...")
            _ = self.hook_registry
            logger.info("🚀 [initialize_async] 初始化 session_manager...")
            _ = self.session_manager
            logger.info("🚀 [initialize_async] 初始化 vector_store...")
            _ = self.vector_store
            kb = self._knowledge_base
            if kb:
                logger.info("🚀 [initialize_async] 初始化 knowledge_base...")
                await kb.init()
            logger.info("🚀 [initialize_async] 初始化 agents...")
            await self._init_agents()
            self._initialized = True
            logger.info("✅ Multi-Agent 系统初始化完成")
        except Exception as e:
            logger.error(f"初始化错误: {e}", exc_info=True)
        finally:
            self._initializing = False


state = AgentSystemState()


# ═══════════════════════════════════════════════════════════════════
# FastAPI 应用
# ═══════════════════════════════════════════════════════════════════


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logging.info("🚀 API 服务器启动")
    task = asyncio.ensure_future(state.initialize_async())
    try:
        await asyncio.wait_for(task, timeout=30.0)
    except asyncio.TimeoutError:
        logger.error("系统初始化超时")
    yield
    logging.info("👋 API 服务器关闭")


app = FastAPI(
    title="Multi-Agent System API",
    description="Multi-Agent 智能协作系统 REST API",
    version="0.02",
    lifespan=lifespan,
)

_cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000",
)
_cors_list = [o.strip() for o in _cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def feature_request_logger(request: Request, call_next):
    started = time.time()
    feature = _resolve_feature_from_path(request.url.path)
    flog = get_feature_logger(feature)
    request_id = str(uuid.uuid4())[:8]

    flog.info(
        f"[{request_id}] -> {request.method} {request.url.path} query={dict(request.query_params)}"
    )
    try:
        response = await call_next(request)
        elapsed_ms = int((time.time() - started) * 1000)
        flog.info(
            f"[{request_id}] <- status={response.status_code} elapsed_ms={elapsed_ms}"
        )
        return response
    except Exception as e:
        elapsed_ms = int((time.time() - started) * 1000)
        flog.error(
            f"[{request_id}] !! error={type(e).__name__}: {e} elapsed_ms={elapsed_ms}"
        )
        raise


app.include_router(skill_router)
app.include_router(agent_router)
app.include_router(soul_router)
app.include_router(evolution_router)
app.include_router(memory_router)

# API namespace aliases for frontend proxy (/api/*)
app.include_router(skill_router, prefix="/api")
app.include_router(agent_router, prefix="/api")
app.include_router(soul_router, prefix="/api")
app.include_router(evolution_router, prefix="/api")
app.include_router(memory_router, prefix="/api")
app.include_router(auth_router)

from fastapi import WebSocket

app.add_api_websocket_route("/ws/events", websocket_endpoint)


# ═══════════════════════════════════════════════════════════════════
# 健康检查
# ═══════════════════════════════════════════════════════════════════


@app.get("/health", response_model=HealthResponse)
@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """系统健康检查"""
    try:
        pr = state.provider_registry
        vs = state.vector_store
        sr = state.skill_registry

        return HealthResponse(
            status="healthy",
            provider=pr.active_id,
            model=pr.active_model,
            providers_available=len(pr.list_all()),
            skills_count=len(sr.list_all()),
            memory_count=await vs.count(),
        )
    except Exception as e:
        return HealthResponse(
            status="initializing",
            provider="unknown",
            model="unknown",
            providers_available=0,
            skills_count=0,
            memory_count=0,
        )


# ═══════════════════════════════════════════════════════════════════
# 聊天接口
# ═══════════════════════════════════════════════════════════════════


@app.post("/chat", response_model=ChatResponse)
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """发送消息并获取回复"""
    chat_log = get_feature_logger("chat")
    trace_id = str(uuid.uuid4())
    session_id = request.session_id or ""
    logging.info(
        f"🌐 [/chat] 请求开始 | trace_id={trace_id} | session_id={session_id[:8] if session_id else 'new'} | message_len={len(request.message)}"
    )
    chat_log.info(
        f"chat_start trace_id={trace_id} session_id={session_id or 'new'} message_len={len(request.message)}"
    )
    try:
        orch = state._get_orchestrator()
        if not orch:
            logging.error(f"🌐 [/chat] 系统未初始化")
            raise HTTPException(status_code=503, detail="System not initialized")

        logging.info(f"🌐 [/chat] 调用 orchestrator.run() | trace_id={trace_id}")
        chat_log.info(f"chat_orchestrator_run trace_id={trace_id}")
        result = await orch.run(
            user_input=request.message,
            session_id=request.session_id,
        )
        session_id = state.session_manager.current_session_id or ""
        logging.info(
            f"🌐 [/chat] ✅ 完成 | trace_id={trace_id} | session_id={session_id[:8]} | response_len={len(result) if result else 0}"
        )
        chat_log.info(
            f"chat_done trace_id={trace_id} session_id={session_id} response_len={len(result) if result else 0}"
        )
        return ChatResponse(
            response=result,
            session_id=session_id,
            provider=state.provider_registry.active_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logging.error(
            f"🌐 [/chat] ❌ 错误 | trace_id={trace_id} | {type(e).__name__}: {e}"
        )
        chat_log.error(f"chat_error trace_id={trace_id} error={type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agents/{agent_id}/chat")
@app.post("/api/agents/{agent_id}/chat")
async def chat_with_agent(agent_id: str, request: ChatRequest):
    """
    直接与指定 Agent 聊天（不经过 Orchestrator 调度）

    用于独立 Agent 问答模式
    """
    trace_id = str(uuid.uuid4())
    logging.info(
        f"🌐 [agents/{agent_id}/chat] 请求开始 | trace_id={trace_id} | message='{request.message[:50]}...' "
    )
    try:
        orch = state._get_orchestrator()

        valid_agent_ids = [
            a.agent_id for a in state._all_agents if a.agent_id != "orchestrator"
        ]
        if agent_id not in valid_agent_ids:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

        result = await orch.run_single_agent(
            user_input=request.message,
            agent_id=agent_id,
            session_id=request.session_id,
            trace_id=trace_id,
        )

        logging.info(
            f"🌐 [agents/{agent_id}/chat] ✅ 完成 | trace_id={trace_id} | response_len={len(result) if result else 0}"
        )

        return {
            "success": True,
            "response": result,
            "session_id": orch._current_session_id,
            "agent_id": agent_id,
            "provider": state.provider_registry.active_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(
            f"🌐 [agents/{agent_id}/chat] ❌ 错误 | trace_id={trace_id} | {type(e).__name__}: {e}"
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/stream")
@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest, last_event_id: str = None):
    """
    SSE 流式事件端点 - 实时推送 Agent 执行事件

    可靠性特性:
    - 心跳事件（每 15 秒）避免代理断流
    - 支持 Last-Event-ID 断线续传
    """
    trace_id = str(uuid.uuid4())
    chat_log = get_feature_logger("chat")
    session_desc = request.session_id or "new"
    logger.info(
        f"🌐 [/chat/stream] 请求开始 | trace_id={trace_id} | session_id={session_desc[:8]} | message='{request.message[:50]}...'"
    )
    chat_log.info(
        f"chat_stream_start trace_id={trace_id} session_id={session_desc} message_len={len(request.message)}"
    )

    HEARTBEAT_INTERVAL = 15

    async def event_generator():
        try:
            orch = state._get_orchestrator()
            if not orch:
                logger.error(f"🌐 [/chat/stream:{trace_id}] 系统未初始化")
                yield {"event": "error", "data": "System not initialized"}
                return

            session_id = request.session_id
            if not session_id:
                session_id = state.session_manager.new_session(
                    title=request.message[:40]
                )
                logger.info(f"🌐 [/chat/stream:{trace_id}] 🆕 创建新会话: {session_id}")
                chat_log.info(
                    f"chat_stream_new_session trace_id={trace_id} session_id={session_id}"
                )
            else:
                logger.info(
                    f"🌐 [/chat/stream:{trace_id}] ▶️ 恢复会话: {session_id[:8]}"
                )
                chat_log.info(
                    f"chat_stream_resume_session trace_id={trace_id} session_id={session_id}"
                )

            event_queue = asyncio.Queue()
            last_yielded_event_id = last_event_id or ""
            events_received = 0

            async def emit_to_queue(event):
                nonlocal events_received
                event_type = getattr(event, "type", None) or (
                    event.event_type.value
                    if hasattr(event, "event_type")
                    else "unknown"
                )
                event_id = getattr(event, "event_id", None) or str(uuid.uuid4())
                events_received += 1
                logger.info(
                    f"🌐 [SSE:{trace_id}] 📤 事件 [{events_received}] type={event_type} id={event_id[:8]}"
                )
                chat_log.info(
                    f"chat_stream_event trace_id={trace_id} event_type={event_type} event_id={event_id[:8]} idx={events_received}"
                )
                await event_queue.put((event_id, event))

            for agent in state._all_agents:
                if hasattr(agent, "set_event_emitter"):
                    agent.set_event_emitter(emit_to_queue)
                if hasattr(agent, "_current_trace_id"):
                    agent._current_trace_id = trace_id
                if hasattr(agent, "_current_session_id"):
                    agent._current_session_id = session_id

            orch._current_trace_id = trace_id
            orch.set_event_emitter(emit_to_queue)

            logger.info(f"🌐 [/chat/stream:{trace_id}] 🚀 启动 orchestrator.run()")

            task = asyncio.create_task(
                orch.run(
                    user_input=request.message,
                    session_id=session_id,
                    trace_id=trace_id,
                )
            )

            last_heartbeat = time.time()
            loop_count = 0
            while True:
                loop_count += 1
                try:
                    remaining = HEARTBEAT_INTERVAL - (time.time() - last_heartbeat)
                    if remaining <= 0:
                        logger.debug(f"🌐 [SSE:{trace_id}] ❤️ 心跳")
                        yield {
                            "event": "heartbeat",
                            "data": "keepalive",
                            "id": str(uuid.uuid4())[:8],
                        }
                        last_heartbeat = time.time()
                        remaining = HEARTBEAT_INTERVAL

                    logger.debug(f"🌐 [SSE:{trace_id}] ⏳ 等待事件 (loop={loop_count})")
                    event_id, event = await asyncio.wait_for(
                        event_queue.get(), timeout=remaining
                    )
                    event_queue.task_done()

                    if last_event_id and event_id <= last_event_id:
                        logger.info(
                            f"🌐 [SSE:{trace_id}] 🔁 跳过已发送: {event_id[:8]}"
                        )
                        continue

                    event_data = event.to_dict() if hasattr(event, "to_dict") else {}
                    event_type = event_data.get("event") or event_data.get(
                        "type", "message"
                    )

                    logger.info(
                        f"🌐 [SSE:{trace_id}] 📤 yield event={event_type} id={event_id[:8]}"
                    )
                    yield {
                        "event": event_type,
                        "data": json.dumps(event_data),
                        "id": event_id[:8] if len(event_id) > 8 else event_id,
                    }

                    last_yielded_event_id = event_id

                    if event_type in ("final_response", "task_failed", "task_timeout"):
                        logger.info(
                            f"🌐 [SSE:{trace_id}] 🛑 收到终止事件: {event_type}"
                        )
                        break

                except asyncio.TimeoutError:
                    logger.debug(f"🌐 [SSE:{trace_id}] ⏰ 超时等待")
                    yield {
                        "event": "heartbeat",
                        "data": "keepalive",
                        "id": str(uuid.uuid4())[:8],
                    }
                    last_heartbeat = time.time()
                    continue

            logger.info(f"🌐 [/chat/stream:{trace_id}] ⏳ 等待 orchestrator.run() 完成")
            result = await task
            response_len = len(result) if result else 0
            logger.info(
                f"🌐 [/chat/stream:{trace_id}] ✅ 完成 | response_len={response_len}"
            )
            if response_len == 0:
                chat_log.error(
                    f"chat_stream_no_response trace_id={trace_id} provider={state.provider_registry.active_id}"
                )
            else:
                chat_log.info(
                    f"chat_stream_done trace_id={trace_id} response_len={response_len} provider={state.provider_registry.active_id}"
                )
            yield {
                "event": "done",
                "data": f"Final response: {result[:500]}" if result else "No response",
                "id": str(uuid.uuid4())[:8],
            }

        except Exception as e:
            import traceback

            tb = traceback.format_exc()
            logger.error(
                f"🌐 [/chat/stream:{trace_id}] ❌ 异常: {type(e).__name__}: {e}\n{tb}"
            )
            chat_log.error(
                f"chat_stream_error trace_id={trace_id} error={type(e).__name__}: {e} provider={state.provider_registry.active_id}"
            )
            yield {"event": "error", "data": str(e)}

    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/chat/history/{session_id}")
@app.get("/api/chat/history/{session_id}")
async def get_chat_history(session_id: str):
    """获取会话历史"""
    try:
        session = state.session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        messages = state.session_manager.store.get_messages(session_id)
        return {**session, "messages": messages}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# 会话管理
# ═══════════════════════════════════════════════════════════════════


@app.get("/sessions", response_model=List[SessionInfo])
@app.get("/api/sessions", response_model=List[SessionInfo])
async def list_sessions():
    """列出所有会话"""
    session_log = get_feature_logger("sessions")
    try:
        sessions = state.session_manager.list_sessions()
        session_log.info(f"list_sessions total={len(sessions)}")
        return [
            SessionInfo(
                session_id=s.get("session_id", ""),
                title=s.get("title", "")[:50],
                status=s.get("status", "active"),
                created_at=s.get("created_at", ""),
                updated_at=s.get("updated_at", ""),
                message_count=s.get("message_count", 0),
            )
            for s in sessions[:50]
        ]
    except Exception as e:
        logger.error(f"List sessions error: {e}")
        session_log.error(f"list_sessions_error error={type(e).__name__}: {e}")
        return []


@app.post("/sessions")
@app.post("/api/sessions")
async def create_session(title: str = "新会话"):
    """创建新会话"""
    session_log = get_feature_logger("sessions")
    try:
        session_id = state.session_manager.new_session(title=title[:50])
        session_log.info(f"create_session session_id={session_id} title={title[:50]}")
        return {"session_id": session_id, "title": title}
    except Exception as e:
        session_log.error(
            f"create_session_error title={title[:50]} error={type(e).__name__}: {e}"
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions/{session_id}")
@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """获取会话详情"""
    session_log = get_feature_logger("sessions")
    try:
        session = state.session_manager.get_session(session_id)
        if not session:
            session_log.warning(f"get_session_not_found session_id={session_id}")
            raise HTTPException(status_code=404, detail="Session not found")
        session_log.info(f"get_session session_id={session_id}")
        return session
    except HTTPException:
        raise
    except Exception as e:
        session_log.error(
            f"get_session_error session_id={session_id} error={type(e).__name__}: {e}"
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/sessions/{session_id}")
@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    session_log = get_feature_logger("sessions")
    try:
        state.session_manager.delete_session(session_id)
        session_log.info(f"delete_session session_id={session_id}")
        return {"success": True}
    except Exception as e:
        session_log.error(
            f"delete_session_error session_id={session_id} error={type(e).__name__}: {e}"
        )
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# Provider 管理
# ═══════════════════════════════════════════════════════════════════


@app.get("/providers", response_model=List[ProviderInfo])
@app.get("/api/providers", response_model=List[ProviderInfo])
async def list_providers():
    """列出所有 Provider"""
    provider_log = get_feature_logger("providers")
    try:
        pr = state.provider_registry
        providers = pr.list_all()
        provider_log.info(
            f"list_providers total={len(providers)} active={pr.active_id}"
        )
        result = []
        for p in providers:
            try:
                prov = pr.get(p["id"])
                model = getattr(prov, "model", "")
            except Exception as e:
                logger.warning(f"Failed to get model for {p['id']}: {e}")
                model = ""
            result.append(
                ProviderInfo(
                    id=p["id"],
                    name=p["name"],
                    model=model,
                    active=p["active"],
                )
            )
        return result
    except Exception as e:
        logger.error(f"List providers error: {e}")
        provider_log.error(f"list_providers_error error={type(e).__name__}: {e}")
        return []


@app.post("/providers/{provider_id}/use")
@app.post("/api/providers/{provider_id}/use")
async def use_provider(provider_id: str):
    """切换 Provider"""
    try:
        state.provider_registry.use(provider_id)
        return {"success": True, "provider": provider_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/providers/current")
@app.get("/api/providers/current")
async def get_current_provider():
    """获取当前 Provider"""
    try:
        pr = state.provider_registry
        return {
            "id": pr.active_id,
            "name": pr.active_name,
            "model": pr.active_model,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


from pydantic import BaseModel


class AddProviderRequest(BaseModel):
    id: str
    name: str
    type: str  # "openai" or "anthropic"
    model: str
    base_url: str = ""
    api_key: str


@app.post("/providers")
@app.post("/api/providers")
async def add_provider(request: AddProviderRequest):
    """添加新 Provider"""
    try:
        pr = state.provider_registry
        from providers.openai_provider import OpenAIProvider
        from providers.anthropic_provider import AnthropicProvider

        if request.type == "anthropic":
            provider = AnthropicProvider(
                model=request.model,
                api_key=request.api_key,
            )
            provider.name = request.name
        else:
            provider = OpenAIProvider(
                model=request.model,
                base_url=request.base_url or "https://api.openai.com/v1",
                api_key=request.api_key,
            )
            provider.name = request.name

        profile = {
            "id": request.id,
            "name": request.name,
            "type": request.type,
            "model": request.model,
            "base_url": request.base_url or "https://api.openai.com/v1",
            "api_key": request.api_key,
            "active": False,
        }

        pr.add(request.id, provider, profile)

        logger.info(f"✅ 添加 Provider: {request.id} ({request.name})")
        return {
            "success": True,
            "provider_id": request.id,
            "name": request.name,
            "model": request.model,
        }
    except Exception as e:
        logger.error(f"添加 Provider 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/providers/{provider_id}")
@app.delete("/api/providers/{provider_id}")
async def delete_provider(provider_id: str):
    """删除 Provider"""
    try:
        pr = state.provider_registry
        if provider_id == pr.active_id:
            raise HTTPException(status_code=400, detail="不能删除当前使用的 Provider")

        pr.remove(provider_id)

        logger.info(f"🗑️ 删除 Provider: {provider_id}")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# 技能管理
# ═══════════════════════════════════════════════════════════════════


@app.get("/skills", response_model=List[SkillInfo])
@app.get("/api/skills", response_model=List[SkillInfo])
async def list_skills():
    """列出所有技能"""
    try:
        skills = state.skill_registry.list_all()
        return [
            SkillInfo(
                skill_id=s["skill_id"],
                name=s["name"],
                description=s.get("description", ""),
                version=s.get("version", "0.02"),
                tags=[],
                enabled=bool(s.get("enabled", 1)),
            )
            for s in skills
        ]
    except Exception as e:
        logger.error(f"List skills error: {e}")
        return []


@app.get("/skills/{skill_id}")
@app.get("/api/skills/{skill_id}")
async def get_skill(skill_id: str):
    """获取技能详情"""
    try:
        meta = state.skill_registry.get_metadata(skill_id)
        if not meta:
            raise HTTPException(status_code=404, detail="Skill not found")
        return meta.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/skills/{skill_id}/enable")
@app.post("/api/skills/{skill_id}/enable")
async def enable_skill(skill_id: str):
    """启用技能"""
    try:
        state.skill_registry.enable(skill_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/skills/{skill_id}/disable")
@app.post("/api/skills/{skill_id}/disable")
async def disable_skill(skill_id: str):
    """禁用技能"""
    try:
        state.skill_registry.disable(skill_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# 记忆管理
# ═══════════════════════════════════════════════════════════════════


@app.get("/memory/stats")
@app.get("/api/memory/stats")
async def get_memory_stats():
    """获取记忆统计"""
    try:
        return {
            "total": await state.vector_store.count(),
            "vector_store": "LanceDB",
        }
    except Exception as e:
        logger.error(f"Memory stats error: {e}")
        return {"total": 0, "vector_store": "LanceDB"}


@app.delete("/memory/{memory_id}")
@app.delete("/api/memory/{memory_id}")
async def delete_memory(memory_id: str):
    """删除记忆"""
    try:
        await state.vector_store.delete(memory_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# Hooks 管理
# ═══════════════════════════════════════════════════════════════════


@app.get("/hooks")
@app.get("/api/hooks")
async def list_hooks():
    """列出所有 Hook"""
    try:
        return state.hook_registry.list_hooks()
    except Exception as e:
        logger.error(f"List hooks error: {e}")
        return []


@app.get("/traces")
@app.get("/api/traces")
async def list_traces(limit: int = 20):
    """列出最近的 trace 运行记录（MLflow）"""
    traces_log = get_feature_logger("traces")
    try:
        from integrations.mlflow_trace import get_trace_tracker

        tracker = get_trace_tracker()
        traces = tracker.list_recent_traces(limit=limit)
        traces_log.info(f"list_traces limit={limit} returned={len(traces)}")
        return {"success": True, "traces": traces, "total": len(traces)}
    except Exception as e:
        logger.error(f"List traces error: {e}")
        traces_log.error(
            f"list_traces_error limit={limit} error={type(e).__name__}: {e}"
        )
        return {"success": True, "traces": [], "total": 0}


# ═══════════════════════════════════════════════════════════════════
# Debug / Status 接口
# ═══════════════════════════════════════════════════════════════════

DEBUG_DEV_MODE = os.getenv("DEBUG_DEV_MODE", "true").lower() == "true"


def _check_dev_mode():
    """检查是否为开发模式，非开发模式拒绝访问 debug 接口"""
    if not DEBUG_DEV_MODE:
        raise HTTPException(
            status_code=403,
            detail="Debug endpoints disabled. Set DEBUG_DEV_MODE=true to enable.",
        )


@app.get("/debug/status")
async def debug_status():
    """获取完整系统状态（用于调试）"""
    _check_dev_mode()
    try:
        return {
            "initialized": state._initialized,
            "agents_count": len(state.all_agents),
            "agents": [
                {
                    "id": a.agent_id,
                    "running": getattr(a, "_running", False),
                }
                for a in state.all_agents
            ],
            "bus_agents": list(state.bus.registered_agents) if state.bus else [],
            "hooks": state.hook_registry.list_hooks() if state.hook_registry else [],
            "providers": state.provider_registry.list_all()
            if state.provider_registry
            else [],
            "skills": state.skill_registry.list_all() if state.skill_registry else [],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Debug status error: {e}")
        return {"error": str(e)}


@app.get("/debug/agents")
async def debug_agents():
    """获取所有 Agent 详细信息"""
    _check_dev_mode()
    try:
        return {
            "agents": [
                {
                    "id": a.agent_id,
                    "description": getattr(a, "description", ""),
                    "skills": getattr(a, "skills", []),
                    "running": getattr(a, "_running", False),
                }
                for a in state.all_agents
            ],
            "bus_agents": list(state.bus.registered_agents) if state.bus else [],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Debug agents error: {e}")
        return {"error": str(e)}


@app.post("/debug/reload")
async def debug_reload():
    """重新加载系统"""
    _check_dev_mode()
    try:
        state._initialized = False
        state._initializing = False
        state._all_agents = []
        await state.initialize_async()
        return {"success": True, "message": "System reloaded"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reload error: {e}")
        return {"success": False, "error": str(e)}


@app.get("/debug/trace/{trace_id}")
async def get_trace(trace_id: str):
    """获取指定 trace 的详细信息"""
    _check_dev_mode()
    try:
        if not state.bus:
            return {"error": "MessageBus not available"}

        history = state.bus.get_history(trace_id=trace_id)

        return {
            "trace_id": trace_id,
            "message_count": len(history),
            "messages": [
                {
                    "id": m.id,
                    "sender": m.sender,
                    "recipient": m.recipient,
                    "type": m.type,
                    "created_at": m.created_at,
                    "payload": m.payload,
                }
                for m in history
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get trace error: {e}")
        return {"error": str(e)}


@app.get("/debug/results/{session_id}")
async def get_session_results(session_id: str):
    """获取会话的所有任务结果"""
    _check_dev_mode()
    try:
        results = state.session_manager.store.get_results(session_id)
        return {
            "session_id": session_id,
            "results_count": len(results),
            "results": results,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get results error: {e}")
        return {"error": str(e)}


@app.get("/")
async def root():
    return RedirectResponse(url="http://localhost:5173/", status_code=307)


@app.get("/agent.html")
async def agent_page():
    return RedirectResponse(url="http://localhost:5173/", status_code=307)


@app.get("/skills.html")
async def skills_page():
    return RedirectResponse(url="http://localhost:5173/skills", status_code=307)


@app.get("/evolution.html")
async def evolution_page():
    return RedirectResponse(url="http://localhost:5173/approvals", status_code=307)


@app.get("/memory.html")
async def memory_page():
    return RedirectResponse(url="http://localhost:5173/knowledge", status_code=307)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
