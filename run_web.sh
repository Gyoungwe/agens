#!/bin/bash
# run_web.sh - 启动 Multi-Agent Web 界面

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "🚀 启动 Multi-Agent Web 界面..."
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 Python3"
    exit 1
fi

# 检查依赖
echo "📦 检查依赖..."
python3 -c "import fastapi" 2>/dev/null || {
    echo "❌ FastAPI 未安装，正在安装..."
    pip3 install fastapi uvicorn
}

# 启动 API 服务器
echo "🔧 启动 API 服务器 (http://localhost:8000)..."
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
