# Agens Multi-Agent 协作框架

模块化多 Agent 协作框架，支持 Hook 系统、记忆系统、知识库、多模型路由和实时事件流。

## 版本

**v0.02** - 生产级可靠性版本

## 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Key（DEEPSEEK_API_KEY 等）

# 3A. 前台交互模式
python main.py

# 3B. API 服务模式
python -m uvicorn api.main:app --reload --port 8000

# 4. 打开浏览器
open http://localhost:8000
```

## 目录结构

```
Dev1/
├── core/                        # 核心抽象
│   ├── message.py              # 消息数据结构（MessageEnvelope）
│   ├── base_agent.py           # Agent 基类（生命周期/Hook/重试）
│   ├── orchestrator.py         # 任务调度器（计划/分发/汇总）
│   ├── events.py               # 事件系统（10种事件 + to_sse()）
│   ├── hooks.py                # Hook 系统（优先级/超时/降级/并发）
│   ├── skill_registry.py       # 技能注册中心（WAL 模式）
│   └── context_compressor.py   # 上下文压缩
├── bus/
│   └── message_bus.py          # 消息总线（广播并发 + OrderedDict LRU 去重）
├── agents/                      # 内置 Agent
│   ├── research_agent/         # 研究员 Agent
│   ├── executor_agent/         # 执行器 Agent
│   └── writer_agent/           # 写手 Agent
├── memory/
│   └── vector_store.py        # LanceDB 向量记忆（scope 隔离/schema 迁移）
├── knowledge/
│   ├── knowledge_base.py      # LanceDB 知识库（scope 隔离/schema 迁移）
│   └── document_loader.py      # 文档导入器
├── providers/
│   ├── base_provider.py        # Provider 基类（标准响应结构）
│   ├── anthropic_provider.py   # Anthropic 实现
│   ├── openai_provider.py      # OpenAI 兼容实现（UsageInfo 嵌套修复）
│   ├── deepseek_provider.py    # DeepSeek 实现
│   ├── provider_registry.py     # Provider 注册中心
│   └── profiles.yaml           # Provider 配置文件（默认 deepseek-chat）
├── session/
│   ├── session_store.py       # SQLite 会话存储（token_count 列迁移）
│   └── session_manager.py      # 会话管理器
├── api/
│   └── main.py                # FastAPI 后端 + SSE + 心跳 + 统一日志
├── web/                        # Web UI 前端
├── dashboard/                  # Streamlit Dashboard
├── utils/
│   ├── logging.py             # 结构化日志
│   └── retry.py              # 重试机制（指数退避 + jitter）
├── config/
│   └── agents.yaml            # Agent 身份配置
├── tests/                      # 测试套件
│   ├── test_integration.py    # 32 个集成测试
│   └── ...                    # 单元测试
├── logs/                       # 日志目录（统一写入 logs/agens_YYYYMMDD.log）
├── main.py                     # 前台交互入口
└── requirements.txt
```

## 核心功能

### 1. 多 Agent 协作

Orchestrator 负责任务拆解与分发，多个专职 Agent 异步协作，通过 asyncio.Queue 消息总线通信。

```
用户输入 → Orchestrator 任务分解 → Agent 协作执行 → 结果汇总 → final_response
```

**事件驱动架构**（`core/events.py` - 10 种事件类型）：
- `agent_start` - Agent 启动
- `agent_thinking` - Agent 思考
- `agent_tool_call` - 工具调用
- `agent_file_read` - 文件读取
- `agent_output` - Agent 输出
- `agent_done` - Agent 完成
- `final_response` - 最终响应
- `task_failed` - 任务失败
- `task_timeout` - 任务超时
- `error` - 错误

### 2. Hook 系统

Hook 允许在 Agent 执行过程中插入自定义逻辑，支持优先级执行、超时控制、并发运行、优雅降级：

```python
registry.register(LoggingHook())           # 记录所有工具调用 (priority=50)
registry.register(RateLimitHook(60))      # 限流 60次/分钟 (priority=10)
registry.register(ApprovalHook())         # 高风险操作审批 (priority=100)
```

### 3. 记忆系统

基于 LanceDB 的向量记忆，支持语义检索和 TTL 自动过期。

### 4. 知识库系统

基于 LanceDB 的 RAG 向量知识库，支持 URL / PDF / Markdown 导入，按 agent_id + topic 过滤检索。

### 5. Provider 多模型支持

统一的 BaseProvider 接口，支持切换多种 LLM 后端。配置文件：`providers/profiles.yaml`

| Provider | 模型示例 |
|----------|---------|
| Anthropic | claude-3-5-sonnet, claude-3-haiku |
| OpenAI | gpt-4o, gpt-4o-mini |
| SiliconFlow | Qwen/Qwen2.5-7B-Instruct |
| DeepSeek | deepseek-chat |
| VolcEngine | doubao-pro |

### 6. Session 会话管理

SQLite 持久化存储，支持会话恢复、历史截断和任务结果记录。

### 7. Web UI + API

实时事件流显示（SSE），支持模型选择、实时对话交互、任务执行状态监控。

**API 端点**：
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | Web UI |
| POST | `/chat` | 普通聊天 |
| POST | `/chat/stream` | SSE 流式事件 |
| GET | `/health` | 健康检查 |
| GET | `/providers` | 模型列表 |
| POST | `/providers` | 添加模型 |
| DELETE | `/providers/{name}` | 删除模型 |
| GET | `/sessions` | 会话列表 |
| GET | `/skills` | 技能列表 |
| GET | `/hooks` | Hook 列表 |

**SSE 可靠性特性**：
- 心跳事件（每 15 秒）避免代理断流
- `Last-Event-ID` 支持断线重连
- `DEBUG_DEV_MODE=true` 启用 debug 接口

## 生产级可靠性改进 (v0.02)

### 已修复的问题

| ID | 模块 | 问题 | 修复 |
|----|------|------|------|
| BUG-1 | message.py | `Optional` 导入缺失 | 添加 `from typing import Optional` |
| BUG-2 | retry.py | 非重试异常被静默吞掉 | 区分 `RetryableError` 和其他异常，直接 raise |
| OPT-1 | message_bus | 广播串行等待单点失败 | `asyncio.gather` 并发广播 + 0.5s timeout |
| OPT-2 | message_bus | 去重缓存 O(n) 扫描 | `OrderedDict` 实现 O(1) LRU |
| OPT-3 | orchestrator | `_emit` 异常静默丢弃 | `_safe_emit_callback` + 可观测化日志 |
| DEF-1 | events.py | EventEnvelope + AgentEvent 分离 | 合并为统一结构 + `to_sse()` 方法 |
| DEF-2 | hooks.py | Hook 链串行阻塞 | 同 priority 并发执行 `asyncio.gather` |
| DEF-3 | orchestrator | `_pending` 字典无限增长 | TTL 清理（120s 超时强制标记） |
| QUAL-1 | skill_registry | SQLite 并发写入竞争 | WAL 模式 + 持久连接 |
| QUAL-2 | base_agent | AgentConfig 无 Schema 校验 | Pydantic `AgentConfig` 模型校验 |
| - | provider | UsageInfo 嵌套模型定义 | 展平为标准 `UsageInfo` 类 |
| - | session | token_count 列缺失 | ALTER TABLE 迁移脚本 |
| - | orchestrator | `_emit_event` 静默失败 | 完整日志 + 异常降级 |
| - | base_agent | `_emit` 无日志 | 添加调试日志 |
| - | vector_store | LanceDB schema 不兼容 | `drop_table` + 重建 + `exist_ok` |
| - | vector_store | `schema()` 是 property 非方法 | 修正为 `existing.schema` |
| - | vector_store | V1/V2 manifest 冲突 | 检测并 drop 重建 |
| - | knowledge_base | 同 vector_store 问题 | 统一修复 |
| - | api | 缺失 FastAPI/pydantic 导入 | 补充顶部导入 |
| - | api | SSE event_type 查找 `event` 字段 | fallback 到 `type` 字段 |
| - | orchestrator | `_current_trace_id` 并发覆盖 | `trace_id` 参数传递，不依赖实例状态 |
| - | api | `initialize_async` 异常静默 | 添加完整 try/except 日志 |
| - | api | API 日志未写入文件 | 添加 `setup_logging()` |
| - | api | 初始化无步骤日志 | 逐行日志追踪 |

### 日志系统

所有入口（main.py / API）统一写入 `logs/agens_YYYYMMDD.log`，格式一致：

```
%(asctime)s [%(levelname)s] %(name)s: %(message)s
```

关键日志标记：
- `🌐` - API 层（SSE 请求/事件）
- `🚀` - Orchestrator 执行流程
- `📤` - 事件发射
- `🎯` - Agent 任务接收
- `📋` - 任务计划
- `✅/❌` - 完成/失败
- `🔗` - Hook 注册
- `🤖` - Agent 生命周期

### 测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 集成测试
python -m pytest tests/test_integration.py -v

# 单个模块测试
python -m pytest tests/test_message_bus.py -v
python -m pytest tests/test_orchestrator.py -v
```

## 开发

```bash
# 语法检查
python -m py_compile <file>

# 环境变量
DEBUG_DEV_MODE=true  # 启用 debug 接口（默认关闭）
DEEPSEEK_API_KEY=sk-xxx  # DeepSeek API Key
```

## 已知问题

- LanceDB 数据目录在 V1/V2 manifest 混合时会自动重建（已处理）
- 旧版 Session 数据库需要 `token_count` 列迁移（自动执行）
- Python 3.13 推荐（已测试），Python 3.9 可能存在兼容性问题

## 更新日志

### v0.02 (2026-04-09) - 生产级可靠性版本
- 10 项可靠性改进完成并测试通过
- 32 个集成测试覆盖所有核心模块
- DeepSeek 模型集成验证
- LanceDB schema 自动迁移
- 完整日志系统
- SSE 事件流修复（event_type 字段匹配）
- 并发请求 trace_id 隔离

### v0.01
- 初始版本
