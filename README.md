# Multi-Agent System

模块化多 Agent 协作框架，支持技能系统、知识库、多模型路由、会话管理和 Agent 自我进化。

## 技术栈

| 模块 | 选型 | 说明 |
|------|------|------|
| 向量数据库 | Qdrant | 知识库向量检索 |
| 技能存储 | SQLite | 技能元数据管理 |
| Agent 通信 | asyncio.Queue | 异步消息总线 |
| 管理面板 | Streamlit | 可视化管理界面 |
| LLM | LangChain + Anthropic | 兼容多 Provider |

## 目录结构

```
Dev1/
├── core/                        # 核心抽象
│   ├── message.py              # 消息数据结构
│   ├── base_agent.py           # Agent 基类
│   ├── orchestrator.py         # 任务调度器
│   ├── base_skill.py           # 技能基类
│   └── skill_registry.py       # 技能注册中心
├── bus/
│   └── message_bus.py          # asyncio.Queue 消息总线
├── agents/
│   ├── research_agent/         # 研究员 Agent
│   ├── executor_agent/         # 执行器 Agent
│   └── writer_agent/           # 写手 Agent
├── skills/                      # 技能目录（运行时生成）
│   └── README.md
├── knowledge/
│   ├── knowledge_base.py       # Qdrant 向量知识库
│   ├── document_loader.py       # 文档导入器
│   └── retriever.py            # 检索器
├── providers/
│   ├── base_provider.py        # Provider 基类
│   ├── anthropic_provider.py   # Anthropic 实现
│   ├── openai_provider.py      # OpenAI 兼容实现
│   ├── provider_registry.py     # Provider 注册中心
│   └── profiles.yaml           # Provider 配置文件
├── installer/
│   ├── skill_installer.py      # 技能安装器
│   └── nl_installer.py         # 自然语言安装器
├── evolution/
│   ├── capability_sensor.py     # 能力边界感知
│   ├── request_generator.py    # 申请单生成器
│   ├── approval_queue.py       # 审批队列
│   └── auto_installer.py       # 自动安装器
├── session/
│   ├── session_store.py        # SQLite 会话存储
│   └── session_manager.py      # 会话管理器
├── dashboard/                   # Streamlit 管理面板
│   ├── app.py
│   ├── components/auth.py
│   └── pages/
│       ├── 1_skills.py
│       ├── 2_knowledge.py
│       ├── 4_approvals.py
│       └── 5_sessions.py
├── config/
│   └── agents.yaml             # Agent 身份配置
├── data/                        # SQLite 数据目录
├── main.py                      # 主入口
└── requirements.txt
```

## 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动 Qdrant（知识库）
docker run -d -p 6333:6333 qdrant/qdrant

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Key

# 4. 启动系统
python main.py

# 5. 启动管理面板（新终端）
streamlit run dashboard/app.py
```

## 模块说明

### 模块一：多 Agent 基础架构
Orchestrator 负责任务拆解与分发，多个专职 Agent 异步协作，通过 asyncio.Queue 消息总线通信。

### 模块二：技能系统
`BaseSkill` Python 类体系 + `SKILL.md` 文件格式双支持，SkillRegistry 管理技能注册、分配和热重载。

### 模块三：知识库系统
基于 Qdrant 的 RAG 向量知识库，支持 URL / PDF / Markdown 导入，按 Agent 过滤检索范围。

### 模块四：Provider 多模型支持
统一的 BaseProvider 接口，支持切换 Anthropic / OpenAI / Ollama / SiliconFlow 等多种 LLM 后端。

### 模块五：Session 会话管理
SQLite 持久化存储，支持会话恢复、历史截断和任务结果记录。

### 模块六：NLInstaller 自然语言安装
LLM 解析自然语言意图，预览确认后执行安装/卸载/搜索。

### 模块七：Agent 自我进化
能力边界感知 → 自动生成申请单 → 审批队列 → 批准后自动安装。

### 模块八：Streamlit 管理面板
登录验证，技能管理 / 知识库管理 / 审批队列 / 会话历史可视化操作。

## 开发阶段

- **Phase 1**: 多 Agent 基础架构 + 消息总线
- **Phase 2**: 技能系统
- **Phase 3**: 知识库系统
- **Phase 4**: Provider 多模型支持 + Session
- **Phase 5**: NLInstaller + 自我进化
- **Phase 6**: Streamlit 管理面板
# agens
