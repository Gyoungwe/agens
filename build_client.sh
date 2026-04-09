#!/bin/bash
# build_client.sh - Build standalone executable
# Usage: ./build_client.sh

set -e

cd "$(dirname "$0")"
PROJECT_NAME="MultiAgentDashboard"

echo "🔨 Building Multi-Agent Dashboard Client"
echo "========================================"

# Check if PyInstaller is installed
if ! pip3 show pyinstaller > /dev/null 2>&1; then
    echo "📦 Installing PyInstaller..."
    pip3 install pyinstaller
fi

echo "📦 Creating spec file..."

# Create spec file for PyInstaller
cat > "${PROJECT_NAME}.spec" << 'SPEC_EOF'
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['dashboard_gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('dashboard_gui.py', '.'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MultiAgentDashboard',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
SPEC_EOF

echo "🔨 Building executable (this may take a minute)..."

# Build
pyinstaller --name "${PROJECT_NAME}" --onefile --windowed dashboard_gui.py

echo ""
echo "✅ Build complete!"
echo ""
echo "Executable location:"
if [ -d "dist" ]; then
    if [ -f "dist/${PROJECT_NAME}" ]; then
        echo "  macOS/Linux: ./dist/${PROJECT_NAME}"
    fi
    if [ -f "dist/${PROJECT_NAME}.app" ]; then
        echo "  macOS App: ./dist/${PROJECT_NAME}.app"
    fi
fi
if [ -f "${PROJECT_NAME}.exe" ]; then
    echo "  Windows: .\\${PROJECT_NAME}.exe"
fi
