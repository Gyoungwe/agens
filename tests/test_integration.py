# tests/test_integration.py
"""
Agens Multi-Agent 系统集成测试

测试所有核心模块的功能：
1. Provider (DeepSeek chat)
2. Session 管理
3. Skill Registry
4. Knowledge Base
5. Hook System
6. Multi-Agent 协作
7. Web API
"""

import asyncio
import logging
import sys
import time
from pathlib import Path
from datetime import datetime
import tempfile
import shutil

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def add_pass(self, name):
        self.passed += 1
        print(f"  ✅ {name}")

    def add_fail(self, name, reason):
        self.failed += 1
        self.errors.append((name, reason))
        print(f"  ❌ {name}: {reason}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'=' * 60}")
        print(f"测试结果: {self.passed}/{total} 通过")
        if self.errors:
            print(f"\n失败项:")
            for name, reason in self.errors:
                print(f"  - {name}: {reason}")
        return self.failed == 0


async def test_provider_deepseek(results: TestResults):
    """测试 DeepSeek Provider"""
    print("\n📦 测试 Provider (DeepSeek)")
    try:
        from providers.provider_registry import ProviderRegistry
        from providers.base_provider import ChatMessage

        registry = ProviderRegistry()
        registry.use("deepseek")
        provider = registry.get()

        resp = await provider.chat(
            messages=[ChatMessage(role="user", content="Say 'OK' in one word")],
            max_tokens=20,
        )

        if resp.text and len(resp.text) > 0:
            results.add_pass("DeepSeek chat")
            print(f"    Response: {resp.text[:50]}")
        else:
            results.add_fail("DeepSeek chat", f"Empty response: {resp}")

        if resp.usage:
            results.add_pass("ProviderResponse usage info")
        else:
            results.add_fail("ProviderResponse usage info", "No usage info")

    except Exception as e:
        results.add_fail("DeepSeek chat", str(e))


async def test_provider_siliconflow_embedding(results: TestResults):
    """测试 SiliconFlow Embedding"""
    print("\n📦 测试 SiliconFlow Embedding")
    try:
        from memory.vector_store import VectorStore

        vs = VectorStore(db_path="./data/memory_test_embed")
        vector = await vs._embed("Hello world")

        if vector and len(vector) == 1024:
            results.add_pass("SiliconFlow embedding (1024 dims)")
        else:
            results.add_fail(
                "SiliconFlow embedding",
                f"Wrong dimension: {len(vector) if vector else 0}",
            )

        shutil.rmtree("./data/memory_test_embed", ignore_errors=True)
    except Exception as e:
        results.add_fail("SiliconFlow embedding", str(e))


async def test_session_management(results: TestResults):
    """测试 Session 管理"""
    print("\n📦 测试 Session 管理")
    try:
        from session.session_store import SessionStore
        from session.session_manager import SessionManager
        from pathlib import Path

        tmpdb = Path(tempfile.mktemp(suffix=".db"))
        store = SessionStore(db_path=tmpdb)
        sm = SessionManager(store)

        # Test new session
        sm.new_session(title="Test Session")
        session_id = sm.current_session_id
        results.add_pass("Create new session")

        # Test add messages
        await sm.add_user_message("Hello")
        await sm.add_assistant_message("Hi there!")
        results.add_pass("Add messages to session")

        # Test history
        history = sm.get_history()
        if len(history) == 2:
            results.add_pass("Get session history")
        else:
            results.add_fail(
                "Get session history", f"Expected 2 messages, got {len(history)}"
            )

        # Test resume session
        sm2 = SessionManager(store)
        sm2.resume_session(session_id)
        resumed_history = sm2.get_history()
        if len(resumed_history) == 2:
            results.add_pass("Resume session")
        else:
            results.add_fail(
                "Resume session", f"Expected 2 messages, got {len(resumed_history)}"
            )

        # Test list sessions
        sessions = sm.list_sessions()
        if len(sessions) >= 1:
            results.add_pass("List sessions")
        else:
            results.add_fail("List sessions", "No sessions found")

        sm.close()
        sm2.close()
        tmpdb.unlink(missing_ok=True)

    except Exception as e:
        results.add_fail("Session management", str(e))


async def test_skill_registry(results: TestResults):
    """测试 Skill Registry"""
    print("\n📦 测试 Skill Registry")
    try:
        from core.skill_registry import SkillRegistry

        registry = SkillRegistry()
        skills = registry.list_all()

        if len(skills) >= 3:
            results.add_pass(f"List skills ({len(skills)} skills)")
            print(f"    Skills: {[s['skill_id'] for s in skills[:5]]}")
        else:
            results.add_fail("List skills", f"Expected >=3 skills, got {len(skills)}")

        # Test get metadata
        if skills:
            skill_id = skills[0]["skill_id"]
            meta = registry.get_metadata(skill_id)
            if meta:
                results.add_pass("Get skill metadata")
            else:
                results.add_fail("Get skill metadata", "Not found")

    except Exception as e:
        results.add_fail("Skill registry", str(e))


async def test_knowledge_base(results: TestResults):
    """测试 Knowledge Base"""
    print("\n📦 测试 Knowledge Base")
    try:
        import pyarrow as pa
        from knowledge.knowledge_base import KnowledgeBase
        from pathlib import Path

        kb = KnowledgeBase(db_path="./data/knowledge_test")
        await kb.init()

        # Test add_batch document
        doc_ids = await kb.add_batch(
            [
                {
                    "text": "Python is a programming language.",
                    "metadata": {"source": "test", "category": "tech"},
                },
                {
                    "text": "Machine learning is a subset of AI.",
                    "metadata": {"source": "test", "category": "ml"},
                },
            ]
        )
        if doc_ids and len(doc_ids) == 2:
            results.add_pass("Add text to knowledge base")
        else:
            results.add_fail(
                "Add text to knowledge base", f"No doc_id returned: {doc_ids}"
            )

        # Test count
        count = await kb.count()
        if count >= 2:
            results.add_pass(f"Knowledge base count ({count})")
        else:
            results.add_fail("Knowledge base count", f"Count is {count}, expected >=2")

        shutil.rmtree("./data/knowledge_test", ignore_errors=True)

    except Exception as e:
        results.add_fail("Knowledge base", str(e))


async def test_hook_system(results: TestResults):
    """测试 Hook System"""
    print("\n📦 测试 Hook System")
    try:
        from core.hooks import (
            HookRegistry,
            LoggingHook,
            RateLimitHook,
            HookResult,
            ToolUseEvent,
            ToolUseResult,
        )

        registry = HookRegistry()
        registry.register(LoggingHook())
        registry.register(RateLimitHook(max_calls_per_minute=60))

        hooks = registry.list_hooks()
        if len(hooks) >= 2:
            results.add_pass(f"Register hooks ({len(hooks)} hooks)")
        else:
            results.add_fail("Register hooks", f"Expected >=2, got {len(hooks)}")

        # Test pre hook execution
        event = ToolUseEvent(
            tool_name="test_tool",
            tool_input={"key": "value"},
            agent_id="test_agent",
        )
        result = await registry.run_pre_hooks(event)
        if result.allowed:
            results.add_pass("Run pre hooks")
        else:
            results.add_fail("Run pre hooks", "Hook denied execution")

        # Test rate limit
        for i in range(5):
            await registry.run_pre_hooks(event)
        results.add_pass("Rate limit hook execution")

        # Test unregister
        if registry.unregister("rate_limit_hook"):
            results.add_pass("Unregister hook")
        else:
            results.add_fail("Unregister hook", "Failed to unregister")

    except Exception as e:
        results.add_fail("Hook system", str(e))


async def test_message_bus(results: TestResults):
    """测试 Message Bus"""
    print("\n📦 测试 Message Bus")
    try:
        from bus.message_bus import MessageBus
        from core.message import Message

        bus = MessageBus()

        # Test register
        await bus.register("agent1")
        await bus.register("agent2")
        if "agent1" in bus.registered_agents:
            results.add_pass("Register agents")
        else:
            results.add_fail("Register agents", "Agent not registered")

        # Test send message
        msg = Message(
            sender="agent1",
            recipient="agent2",
            type="task",
            payload={"instruction": "test"},
            trace_id="trace-123",
        )
        await bus.send(msg)
        results.add_pass("Send message")

        # Test receive message
        received = await bus.receive("agent2", timeout=1)
        if received and received.message.sender == "agent1":
            results.add_pass("Receive message")
        else:
            results.add_fail("Receive message", "Message not received correctly")

        # Test broadcast (using task type for wildcard recipient)
        msg2 = Message(
            sender="agent1",
            recipient="*",
            type="task",
            payload={"instruction": "broadcast test"},
            trace_id="trace-456",
        )
        await bus.send(msg2)
        results.add_pass("Broadcast message")

        # Test deduplication
        is_dup1 = await bus.check_duplicate("event-1")
        is_dup2 = await bus.check_duplicate("event-1")
        if not is_dup1 and is_dup2:
            results.add_pass("Message deduplication")
        else:
            results.add_fail(
                "Message deduplication", f"is_dup1={is_dup1}, is_dup2={is_dup2}"
            )

    except Exception as e:
        results.add_fail("Message bus", str(e))


async def test_vector_store(results: TestResults):
    """测试 Vector Store"""
    print("\n📦 测试 Vector Store")
    try:
        from memory.vector_store import VectorStore
        import shutil

        vs = VectorStore(db_path="./data/vector_test")

        # Test add memory
        mem_id = await vs.add(
            text="I love coding in Python",
            session_id="test-session",
            role="user",
        )
        if mem_id:
            results.add_pass("Add memory")
        else:
            results.add_fail("Add memory", "No memory_id returned")

        # Test search
        search_results = await vs.search(
            "Python coding", session_id="test-session", top_k=5
        )
        if len(search_results) >= 1:
            results.add_pass("Search memories")
        else:
            results.add_fail("Search memories", "No results")

        # Test get recent
        recent = await vs.get_recent("test-session", limit=10)
        if len(recent) >= 1:
            results.add_pass("Get recent memories")
        else:
            results.add_fail("Get recent memories", "No recent memories")

        # Test health check
        health = await vs.health_check()
        if health.get("status"):
            results.add_pass("Vector store health check")
        else:
            results.add_fail("Vector store health check", "No status")

        shutil.rmtree("./data/vector_test", ignore_errors=True)

    except Exception as e:
        results.add_fail("Vector store", str(e))


async def test_multi_agent_collab(results: TestResults):
    """测试 Multi-Agent 协作"""
    print("\n📦 测试 Multi-Agent 协作")
    try:
        from bus.message_bus import MessageBus
        from core.orchestrator import Orchestrator
        from core.base_agent import BaseAgent
        from providers.provider_registry import ProviderRegistry
        from session.session_store import SessionStore
        from session.session_manager import SessionManager
        from pathlib import Path

        tmpdb = Path(tempfile.mktemp(suffix=".db"))

        bus = MessageBus()
        provider_registry = ProviderRegistry()
        provider_registry.use("deepseek")
        session_store = SessionStore(db_path=tmpdb)
        session_manager = SessionManager(session_store)

        # Create orchestrator
        orchestrator = Orchestrator(
            bus=bus,
            provider_registry=provider_registry,
            session_manager=session_manager,
        )
        await bus.register("orchestrator")
        await orchestrator.start()

        # Create simple echo agent
        class EchoAgent(BaseAgent):
            async def execute(self, instruction, context):
                return f"Echo: {instruction[:50]}"

        echo = EchoAgent(
            agent_id="echo_agent",
            bus=bus,
            provider=provider_registry.get(),
        )
        await bus.register("echo_agent")
        await echo.start()

        # Run task
        result = await orchestrator.run(
            user_input="Ask echo_agent to say hello",
            session_id=None,
        )

        if result and len(result) > 0:
            results.add_pass("Multi-agent task distribution")
            print(f"    Result: {result[:100]}...")
        else:
            results.add_fail("Multi-agent task distribution", "Empty result")

        await orchestrator.stop()
        await echo.stop()
        tmpdb.unlink(missing_ok=True)

    except Exception as e:
        results.add_fail("Multi-agent collaboration", str(e))


async def test_event_system(results: TestResults):
    """测试 Event System"""
    print("\n📦 测试 Event System")
    try:
        from core.events import EventEnvelope, AgentEvent, AgentEventType

        # Test EventEnvelope factory
        env = EventEnvelope.agent_start(
            agent_id="test",
            trace_id="trace-1",
            instruction="test instruction",
            session_id="sess-1",
        )
        results.add_pass("EventEnvelope factory methods")

        # Test to_dict
        d = env.to_dict()
        if d.get("agent") == "test":
            results.add_pass("EventEnvelope to_dict")
        else:
            results.add_fail("EventEnvelope to_dict", "Wrong data")

        # Test to_sse
        sse = env.to_sse()
        if "event: agent_start" in sse:
            results.add_pass("EventEnvelope to_sse")
        else:
            results.add_fail("EventEnvelope to_sse", "Wrong format")

        # Test AgentEvent.to_envelope
        event = AgentEvent(
            event_type=AgentEventType.AGENT_DONE,
            agent_id="test",
            trace_id="trace-2",
        )
        env2 = event.to_envelope()
        if env2.status == "completed":
            results.add_pass("AgentEvent to_envelope")
        else:
            results.add_fail("AgentEvent to_envelope", f"Wrong status: {env2.status}")

    except Exception as e:
        results.add_fail("Event system", str(e))


async def test_api_server(results: TestResults):
    """测试 API Server (FastAPI)"""
    print("\n📦 测试 API Server")
    try:
        from api.main import app
        from fastapi.testclient import TestClient

        # Use TestClient for synchronous testing
        client = TestClient(app)

        # Test health endpoint
        resp = client.get("/health")
        if resp.status_code == 200:
            results.add_pass("API health endpoint")
        else:
            results.add_fail("API health endpoint", f"Status: {resp.status_code}")

        # Test providers endpoint
        resp = client.get("/providers")
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                results.add_pass("API providers endpoint")
            else:
                results.add_fail("API providers endpoint", "Invalid response")
        else:
            results.add_fail("API providers endpoint", f"Status: {resp.status_code}")

    except Exception as e:
        results.add_fail("API server", str(e))


async def main():
    print("=" * 60)
    print("🚀 Agens Multi-Agent 系统集成测试")
    print("=" * 60)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python: {sys.version.split()[0]}")

    results = TestResults()

    start_time = time.time()

    await test_provider_deepseek(results)
    await test_provider_siliconflow_embedding(results)
    await test_session_management(results)
    await test_skill_registry(results)
    await test_knowledge_base(results)
    await test_hook_system(results)
    await test_message_bus(results)
    await test_vector_store(results)
    await test_event_system(results)
    await test_multi_agent_collab(results)
    await test_api_server(results)

    elapsed = time.time() - start_time

    print(f"\n⏱️  测试耗时: {elapsed:.1f}秒")

    success = results.summary()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
