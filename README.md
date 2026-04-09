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
│   ├── events.py               # 事件系统（10种事件类型）
│   ├── hooks.py                # Hook 系统（优先级/超时/降级）
│   └── context_compressor.py   # 上下文压缩
├── bus/
│   └── message_bus.py          # 消息总线（envelope + 去重）
├── agents/                      # 内置 Agent
│   ├── research_agent/         # 研究员 Agent
│   ├── executor_agent/         # 执行器 Agent
│   └── writer_agent/           # 写手 Agent
├── memory/
│   └── vector_store.py        # LanceDB 向量记忆（scope 隔离）
├── knowledge/
│   ├── knowledge_base.py      # LanceDB 知识库（scope 隔离）
│   └── document_loader.py      # 文档导入器
├── providers/
│   ├── base_provider.py        # Provider 基类（标准响应结构）
│   ├── anthropic_provider.py   # Anthropic 实现
│   ├── openai_provider.py      # OpenAI 兼容实现
│   ├── provider_registry.py     # Provider 注册中心
│   └── profiles.yaml           # Provider 配置文件
├── session/
│   ├── session_store.py       # SQLite 会话存储（事务 + 索引）
│   └── session_manager.py      # 会话管理器
├── api/
│   └── main.py                # FastAPI 后端 + SSE + 心跳
├── web/
│   └── index.html             # Web UI 前端
├── utils/
│   └── logging.py             # 结构化日志
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

**事件驱动架构**（`core/events.py` - 10 种事件类型）：
- `agent_start` - Agent 启动
- `agent_thinking` - Agent 思考
- `agent_tool_call` - 工具调用
- `agent_file_read` - 文件读取
- `agent_output` - Agent 输出
- `agent_done` - Agent 完成
- `final_response` - 最终响应
- `task_failed` - 任务失败（系统级）
- `task_timeout` - 任务超时（系统级）
- `error` - 错误

**可靠性特性**：
- 消息统一封装（`MessageEnvelope`）：event_id, task_id, session_id, correlation_id
- 去重缓存防止重复消费
- 重试带 jitter + 指数退避
- 超时自动标记并发送事件

### 2. Hook 系统

Hook 允许在 Agent 执行过程中插入自定义逻辑：

```python
from core.hooks import HookRegistry, LoggingHook, RateLimitHook

registry = HookRegistry()
registry.register(LoggingHook())
registry.register(RateLimitHook(max_calls_per_minute=60))
```

**内置 Hook**（`core/hooks.py`）：
- `LoggingHook` - 记录所有工具调用（优先级 50）
- `RateLimitHook` - 限流（优先级 10）
- `ApprovalHook` - 高风险操作审批
- `TokenUsageHook` - Token 统计
- `ExecutionTimeHook` - 执行时间统计

**可靠性特性**：
- `priority`：执行优先级（数字越小越先执行）
- `timeout_ms`：超时时间（默认 5000ms）
- `critical`：是否为关键 Hook（失败时阻止执行）
- `graceful degradation`：Hook 失败默认降级继续

### 3. 记忆系统

基于 LanceDB 的向量记忆，支持语义检索：

```python
from memory.vector_store import VectorStore

store = VectorStore()
await store.add(
    text="用户喜欢喝咖啡",
    session_id="xxx",
    owner="xxx",
    source="chat",
    ttl_seconds=86400  # 24小时过期
)
results = await store.search("饮料偏好", session_id="xxx", top_k=5)
```

**Metadata 强制字段**：
- `scope`：固定为 "memory"
- `owner`：session_id / agent_id / "global"
- `source`：来源标识
- `version`：版本号
- `ttl_seconds`：过期时间（秒）

**可靠性特性**：
- scope 隔离防止记忆污染知识问答
- TTL 支持自动过期清理
- 搜索时强制 filter

### 4. 知识库系统

基于 LanceDB 的 RAG 向量知识库，支持 URL / PDF / Markdown 导入：

```python
from knowledge.knowledge_base import KnowledgeBase

kb = KnowledgeBase()
await kb.add(
    text="项目使用 Python 开发",
    agent_ids=["research_agent"],
    topic="技术栈",
    source="manual"
)
results = await kb.search("编程语言", agent_id="research_agent", top_k=5)
```

**Metadata 强制字段**：
- `scope`：固定为 "knowledge"
- `owner`：agent_ids JSON 或 "global"
- `source`：url / file / manual
- `version`：版本号

**可靠性特性**：
- scope 隔离防止知识污染记忆问答
- 按 agent_id + topic 过滤检索

### 5. Provider 多模型支持

统一的 BaseProvider 接口，支持切换多种 LLM 后端：

| Provider | 模型示例 |
|----------|---------|
| Anthropic | claude-3-5-sonnet |
| OpenAI | gpt-4o |
| SiliconFlow | Qwen/Qwen2.5-7B-Instruct |
| DeepSeek | deepseek-chat |

配置文件：`providers/profiles.yaml`

**标准响应结构**（`providers/base_provider.py`）：
```python
class ProviderResponse(BaseModel):
    text: str
    model: str
    finish_reason: str  # stop / length / error
    usage: UsageInfo     # input_tokens, output_tokens, total_tokens
    latency_ms: int
    provider: str
    error_code: str
    error_message: str
```

**可靠性特性**：
- 启动时 `health_check_all()` 检查所有 Provider
- 删除 Provider 前检查引用（不能删除正在使用的）

### 6. Session 会话管理

SQLite 持久化存储，支持会话恢复、历史截断和任务结果记录：

```python
from session.session_manager import SessionManager

manager = SessionManager()
session_id = manager.new_session(title="新会话")
await manager.add_user_message("你好")
messages = manager.get_history()
```

**可靠性特性**：
- 事务写入（BEGIN/COMMIT）
- 索引：`session_id`, `updated_at`, `trace_id`
- Token 预算截断（`truncate_messages_by_token_budget`）

### 7. Web UI

实时事件流显示（SSE），支持：
- 模型选择和配置
- 实时对话交互
- 任务执行状态监控

**API 端点**：
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | Web UI |
| POST | `/chat` | 普通聊天 |
| GET | `/chat/stream` | SSE 流式事件 |
| GET | `/providers` | 模型列表 |
| POST | `/providers` | 添加模型 |
| DELETE | `/providers/{name}` | 删除模型 |
| GET | `/debug/results/{session_id}` | 任务结果（需 DEBUG_DEV_MODE=true） |

**SSE 可靠性特性**：
- 心跳事件（每 15 秒）避免代理断流
- `Last-Event-ID` 支持断线重连
- `DEBUG_DEV_MODE=true` 启用 debug 接口

## 开发

```bash
# 语法检查
python -m py_compile <file>

# 环境变量
DEBUG_DEV_MODE=true  # 启用 debug 接口（默认关闭）
```
