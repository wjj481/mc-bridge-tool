#!/usr/bin/env bash
# ============================================================
#  MC Bridge Tool - macOS 打包脚本
#  产物：dist/MC Bridge Tool/      （onedir 命令行版）
#        dist/MC Bridge Tool.app   （macOS .app 包）
# ============================================================
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
echo "[mcbridge] 仓库根目录: $ROOT"

# ---- 检查 Python ----
if ! command -v python3 >/dev/null 2>&1; then
    echo "[错误] 未找到 python3，请先安装 Python 3.10+（推荐 brew install python@3.12）。"
    exit 1
fi

echo "[mcbridge] Python 版本: $(python3 --version)"
echo "[mcbridge] 架构: $(uname -m)"

# ---- 装依赖 ----
echo "[mcbridge] 安装依赖..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 -m pip install pyinstaller

# ---- 清理旧产物 ----
echo "[mcbridge] 清理 build/ dist/ ..."
rm -rf build dist

# ---- 打包 ----
echo "[mcbridge] 开始 PyInstaller 打包..."
python3 -m PyInstaller packaging/mcbridge.spec --noconfirm

echo ""
echo "============================================================"
echo " 打包完成！"
echo " 命令行版: dist/MC Bridge Tool/"
echo " .app 版:  dist/MC Bridge Tool.app"
echo ""
echo " 分发提示:"
echo "   1. 首次打开如提示「无法打开，因为无法验证开发者」，"
echo "      到 系统设置 -> 隐私与安全性 -> 仍要打开。"
echo "   2. 如要公证给别人用，需要 Apple 开发者账号做 codesign + notarize。"
echo "   3. Intel / Apple Silicon 分别在对应架构的 Mac 上跑本脚本。"
echo "============================================================"
