#!/bin/bash
# run_electron.sh - 启动 Electron 桌面应用

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "🚀 启动 Multi-Agent 桌面应用..."

# 检查是否安装了 electron
if ! command -v npx &> /dev/null; then
    echo "❌ npx 未安装，请先安装 Node.js"
    exit 1
fi

# 检查 package.json 是否存在
if [ ! -f "package.json" ]; then
    echo "❌ package.json 未找到"
    exit 1
fi

# 开发模式启动
if [ "$1" == "--dev" ]; then
    echo "🔧 开发模式启动..."
    npx electron . --dev
else
    # 检查是否需要安装依赖
    if [ ! -d "node_modules" ]; then
        echo "📦 安装依赖..."
        npm install
    fi

    echo "🖥️ 启动 Electron..."
    npx electron .
fi
