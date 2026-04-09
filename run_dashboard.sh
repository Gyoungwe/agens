#!/bin/bash
# Multi-Agent Dashboard Launcher
# Usage: ./run_dashboard.sh [gui|tui|web]

MODE="${1:-gui}"

cd "$(dirname "$0")"

echo "🚀 Multi-Agent Dashboard"
echo "========================"

case "$MODE" in
    gui)
        echo "Mode: Standalone GUI Client (recommended)"
        echo ""
        python3 dashboard_gui.py
        ;;
    tui)
        echo "Mode: Terminal UI"
        echo ""
        echo "Controls:"
        echo "  [1-7] Navigate pages"
        echo "  [t]   Toggle theme"
        echo "  [q]   Quit"
        echo ""
        python3 dashboard_tui.py
        ;;
    web)
        echo "Mode: Web UI (Streamlit)"
        echo ""
        streamlit run dashboard/app.py --server.headless true --browser.gatherUsageStats false
        ;;
    build)
        echo "Mode: Build executable"
        echo ""
        ./build_client.sh
        ;;
    *)
        echo "Usage: $0 [gui|tui|web|build]"
        echo ""
        echo "Options:"
        echo "  gui   - Standalone GUI (default, recommended)"
        echo "  tui   - Terminal UI"
        echo "  web   - Web UI via Streamlit"
        echo "  build - Build executable from GUI"
        exit 1
        ;;
esac
