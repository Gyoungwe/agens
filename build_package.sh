#!/bin/bash
# build_package.sh - 构建 Multi-Agent 系统打包目录

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DIST_DIR="$SCRIPT_DIR/dist/MultiAgentSystem-Package"

echo "🔨 开始构建 Multi-Agent 系统打包目录..."
echo "📁 输出目录: $DIST_DIR"

# 创建目录结构
echo "📦 创建目录结构..."
mkdir -p "$DIST_DIR"/{api,web,config,providers,skills,data,core,session,memory,bus,knowledge,evolution,installer,agents,utils,desktop}

# 复制 MultiAgentSystem 可执行文件
echo "📄 复制可执行文件..."
if [ -f "$SCRIPT_DIR/dist/MultiAgentSystem" ]; then
    cp "$SCRIPT_DIR/dist/MultiAgentSystem" "$DIST_DIR/MultiAgentSystem"
else
    echo "⚠️ 警告: dist/MultiAgentSystem 不存在，跳过"
fi

# 复制 API
echo "📦 复制 API..."
cp "$SCRIPT_DIR/api"/*.py "$DIST_DIR/api/" 2>/dev/null || true

# 复制 Web 前端
echo "🌐 复制 Web 前端..."
cp "$SCRIPT_DIR/web"/*.html "$DIST_DIR/web/" 2>/dev/null || true

# 复制 providers
echo "🔧 复制 providers..."
cp "$SCRIPT_DIR/providers"/*.py "$DIST_DIR/providers/" 2>/dev/null || true
cp "$SCRIPT_DIR/providers"/*.yaml "$DIST_DIR/providers/" 2>/dev/null || true
touch "$DIST_DIR/providers/__init__.py"

# 复制 core
echo "🧠 复制 core..."
cp "$SCRIPT_DIR/core"/*.py "$DIST_DIR/core/" 2>/dev/null || true
touch "$DIST_DIR/core/__init__.py"

# 复制 session
echo "💬 复制 session..."
cp "$SCRIPT_DIR/session"/*.py "$DIST_DIR/session/" 2>/dev/null || true
touch "$DIST_DIR/session/__init__.py"

# 复制 memory
echo "🧠 复制 memory..."
cp "$SCRIPT_DIR/memory"/*.py "$DIST_DIR/memory/" 2>/dev/null || true
touch "$DIST_DIR/memory/__init__.py"

# 复制 bus
echo "🚌 复制 bus..."
cp "$SCRIPT_DIR/bus"/*.py "$DIST_DIR/bus/" 2>/dev/null || true
touch "$DIST_DIR/bus/__init__.py"

# 复制 knowledge
echo "📚 复制 knowledge..."
cp "$SCRIPT_DIR/knowledge"/*.py "$DIST_DIR/knowledge/" 2>/dev/null || true
touch "$DIST_DIR/knowledge/__init__.py"

# 复制 evolution
echo "🔄 复制 evolution..."
cp "$SCRIPT_DIR/evolution"/*.py "$DIST_DIR/evolution/" 2>/dev/null || true
touch "$DIST_DIR/evolution/__init__.py"

# 复制 installer
echo "🔧 复制 installer..."
cp "$SCRIPT_DIR/installer"/*.py "$DIST_DIR/installer/" 2>/dev/null || true
touch "$DIST_DIR/installer/__init__.py"

# 复制 agents
echo "🤖 复制 agents..."
find "$SCRIPT_DIR/agents" -name "*.py" -exec cp {} "$DIST_DIR/agents/" \; 2>/dev/null || true
touch "$DIST_DIR/agents/__init__.py"

# 复制 utils
echo "🛠️ 复制 utils..."
cp "$SCRIPT_DIR/utils"/*.py "$DIST_DIR/utils/" 2>/dev/null || true
touch "$DIST_DIR/utils/__init__.py"

# 复制 config
echo "⚙️ 复制 config..."
cp -r "$SCRIPT_DIR/config"/* "$DIST_DIR/config/" 2>/dev/null || true

# 复制 skills
echo "🔧 复制 skills..."
cp -r "$SCRIPT_DIR/skills"/* "$DIST_DIR/skills/" 2>/dev/null || true

# 复制 main.py
echo "📄 复制 main.py..."
cp "$SCRIPT_DIR/main.py" "$DIST_DIR/" 2>/dev/null || true

# 复制 gui.py
echo "📄 复制 gui.py..."
cp "$SCRIPT_DIR/gui.py" "$DIST_DIR/" 2>/dev/null || true

# 复制 requirements.txt
echo "📄 复制 requirements.txt..."
cp "$SCRIPT_DIR/requirements.txt" "$DIST_DIR/" 2>/dev/null || true

# 复制 desktop
echo "🖥️ 复制 desktop..."
cp "$SCRIPT_DIR/desktop"/*.js "$DIST_DIR/desktop/" 2>/dev/null || true
cp "$SCRIPT_DIR/desktop"/*.json "$DIST_DIR/desktop/" 2>/dev/null || true

# 创建 README
echo "📝 创建 README..."
cat > "$DIST_DIR/README.md" << 'EOF'
# Multi-Agent 智能协作系统

## 快速开始

### 1. 命令行模式
```bash
./MultiAgentSystem
```

### 2. Web 界面模式
```bash
./run_web.sh
```
然后打开浏览器访问: http://localhost:8000

### 3. Electron 桌面应用（需要 Node.js）
```bash
cd desktop
npm install
npm start
```

## 功能特性

- 🤖 **多 Agent 协作**: Research/Executor/Writer Agent 协作处理任务
- 💬 **多会话管理**: 支持多会话并行，历史记录持久化
- 🔄 **模型切换**: 5 个预置模型 (MiniMax/SiliconFlow/Anthropic/DeepSeek)
- 🔗 **Hook 系统**: Pre/Post/Error 拦截器（Logging/RateLimit/Approval/TokenUsage）
- 🧠 **记忆系统**: LanceDB 向量存储 + 上下文压缩
- 📚 **知识库**: 文档导入和语义搜索
- 🔧 **技能系统**: 可扩展的技能架构（标准化 SKILL.md 格式）

## 默认配置

- **默认模型**: MiniMax-M2.7
- **向量存储**: LanceDB (SiliconFlow BAAI/bge-m3 embedding)
- **API 端口**: 8000

## API 接口

| 接口 | 方法 | 描述 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/chat` | POST | 发送消息 |
| `/sessions` | GET/POST | 会话管理 |
| `/providers` | GET | 模型列表 |
| `/skills` | GET | 技能列表 |
| `/hooks` | GET | Hook 列表 |

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Cmd/Ctrl+N` | 新会话 |
| `Cmd/Ctrl+K` | 命令面板 |
| `Cmd/Ctrl+,` | 设置 |

## 版本信息

- 版本: 1.0.0
- Python: 3.9+
- Node.js: 18+ (Electron)
EOF

# 创建 .env
echo "📄 创建 .env..."
cat > "$DIST_DIR/.env" << 'EOF'
# MiniMax API (默认)
MINIMAX_API_KEY=sk-cp-qjBXaAt2bmqLvwHwKKOLKGmNK1_rPr5nERXJ4RlLLwZC1Zx-zsCibrFoDayBD8G1_KqhLLPmyyTb6teTSYHod5q4e42ZVFPRSxbeUekUGsN0QVBJF-rhjjU

# SiliconFlow API (向量模型)
SILICONFLOW_API_KEY=sk-unvzxjvgymzfsgvjfywnkfcmsrgwqbmgdpqlpbnbqabvriqv

# 其他 API Keys (需要时配置)
ANTHROPIC_API_KEY=your_anthropic_key_here
DEEPSEEK_API_KEY=your_deepseek_key_here
EOF

# 创建启动脚本
echo "🚀 创建启动脚本..."
cat > "$DIST_DIR/run_web.sh" << 'EOF'
#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
export PYTHONPATH="$DIR:$PYTHONPATH"
echo "🚀 启动 Multi-Agent Web 界面..."
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000
EOF
chmod +x "$DIST_DIR/run_web.sh"

echo ""
echo "✅ 构建完成！"
echo "📁 目录: $DIST_DIR"
echo "📊 大小: $(du -sh "$DIST_DIR" | cut -f1)"
echo ""
echo "启动方式:"
echo "  Web: cd $DIST_DIR && ./run_web.sh"
echo "  CLI: cd $DIST_DIR && ./MultiAgentSystem"
