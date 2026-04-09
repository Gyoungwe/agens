# Agens

模块化多 Agent 协作框架，支持 Hook 系统、记忆系统、知识库、多模型路由和实时事件流。

## 技术栈

| 模块 | 选型 | 说明 |
|------|------|------|
| 向量数据库 | LanceDB | 记忆存储 + 知识库向量检索 |
| 消息总线 | asyncio.Queue | 异步事件驱动通信 |
| Web UI | 原生 HTML/JS | SSE 实时事件流显示 |
| LLM | LangChain | 兼容多 Provider |

## 目录结构

```
Dev1/
├── core/                        # 核心抽象
│   ├── message.py              # 消息数据结构
│   ├── base_agent.py           # Agent 基类
│   ├── orchestrator.py         # 任务调度器
│   ├── events.py               # 事件系统（7种事件类型）
│   └── context_compressor.py   # 上下文压缩
├── bus/
│   └── message_bus.py          # asyncio.Queue 消息总线
├── agents/                      # 内置 Agent
│   ├── research_agent/         # 研究员 Agent
│   ├── executor_agent/         # 执行器 Agent
│   └── writer_agent/           # 写手 Agent
├── memory/
│   └── vector_store.py        # LanceDB 向量记忆
├── knowledge/
│   ├── knowledge_base.py      # LanceDB 知识库
│   └── document_loader.py      # 文档导入器
├── providers/
│   ├── base_provider.py        # Provider 基类
│   ├── anthropic_provider.py   # Anthropic 实现
│   ├── openai_provider.py      # OpenAI 兼容实现
│   ├── provider_registry.py     # Provider 注册中心
│   └── profiles.yaml           # Provider 配置文件
├── hooks/
│   ├── hook_registry.py       # Hook 注册中心
│   └── built_in_hooks.py       # 内置 Hook
├── session/
│   ├── session_store.py       # SQLite 会话存储
│   └── session_manager.py      # 会话管理器
├── api/
│   └── main.py                # FastAPI 后端 + SSE
├── web/
│   └── index.html             # Web UI 前端
├── config/
│   └── agents.yaml            # Agent 身份配置
├── version.py                  # 版本管理
├── main.py                     # 主入口
└── requirements.txt
```

## 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Key

# 3. 启动系统（API + Web UI）
python main.py

# 4. 打开浏览器
open http://localhost:8000
```

## 核心功能

### 1. 多 Agent 协作

Orchestrator 负责任务拆解与分发，多个专职 Agent 异步协作，通过 asyncio.Queue 消息总线通信。

```
用户输入 → Orchestrator 任务分解 → Agent 协作执行 → 结果汇总
```

**事件驱动架构**（`core/events.py`）：
- `TaskCreated` - 任务创建
- `TaskAssigned` - 任务分配
- `AgentStarted` - Agent 启动
- `AgentCompleted` - Agent 完成
- `HookTriggered` - Hook 触发
- `MemoryStored` - 记忆存储
- `FinalResult` - 最终结果

### 2. Hook 系统

Hook 允许在 Agent 执行过程中插入自定义逻辑：

```python
from hooks.hook_registry import HookRegistry

registry = HookRegistry()

@registry.hook("before_think")
async def before_think(agent, context):
    print(f"Agent {agent.name} 开始思考")
    return context
```

**内置 Hook**（`hooks/built_in_hooks.py`）：
- `TimingHook` - 记录执行时间
- `LoggingHook` - 记录执行日志
- `ValidationHook` - 参数验证

### 3. 记忆系统

基于 LanceDB 的向量记忆，支持语义检索：

```python
from memory.vector_store import VectorStore

store = VectorStore()
await store.store("用户喜欢喝咖啡", {"type": "preference"})
results = await store.search("饮料偏好", top_k=5)
```

### 4. 知识库系统

基于 LanceDB 的 RAG 向量知识库，支持 URL / PDF / Markdown 导入：

```python
from knowledge.knowledge_base import KnowledgeBase

kb = KnowledgeBase()
await kb.add_url("https://example.com/doc")
results = await kb.search("相关概念", top_k=5)
```

### 5. Provider 多模型支持

统一的 BaseProvider 接口，支持切换多种 LLM 后端：

| Provider | 模型示例 |
|----------|---------|
| Anthropic | claude-3-5-sonnet |
| OpenAI | gpt-4o |
| SiliconFlow | deepseek-ai/DeepSeek-V2.5 |

配置文件：`providers/profiles.yaml`

### 6. Session 会话管理

SQLite 持久化存储，支持会话恢复、历史截断和任务结果记录：

```python
from session.session_manager import SessionManager

manager = SessionManager()
session = await manager.create_session()
await manager.store_result(session.id, "task_result")
```

### 7. Web UI

实时事件流显示（SSE），支持：
- 模型选择和配置
- 实时对话交互
- 任务执行状态监控

API 端点：
- `GET /` - Web UI
- `POST /chat` - 普通聊天
- `GET /chat/stream` - SSE 流式事件
- `GET /providers` - 模型列表
- `POST /providers` - 添加模型
- `DELETE /providers/{name}` - 删除模型
- `GET /debug/results/{session_id}` - 任务结果

## 开发

```bash
# 运行测试
python -m pytest

# 代码检查
python -m ruff check .

# 格式化代码
python -m ruff format .
```
