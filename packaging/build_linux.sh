#!/usr/bin/env bash
# ============================================================
#  MC Bridge Tool - Linux 打包脚本
#  产物：dist/MC Bridge Tool/   （onedir）
#        可进一步用 dist 目录打 tar.gz 或 AppImage
# ============================================================
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
echo "[mcbridge] 仓库根目录: $ROOT"

# ---- 检查 Python ----
if ! command -v python3 >/dev/null 2>&1; then
    echo "[错误] 未找到 python3。Ubuntu/Debian 请: sudo apt install python3 python3-pip python3-tk"
    exit 1
fi

echo "[mcbridge] Python 版本: $(python3 --version)"
echo "[mcbridge] 架构: $(uname -m)"

# ---- tkinter 依赖检查 ----
if ! python3 -c "import tkinter" >/dev/null 2>&1; then
    echo "[错误] 系统缺 tkinter。Ubuntu/Debian 安装: sudo apt install python3-tk"
    exit 1
fi

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

# ---- 打 tar.gz ----
echo "[mcbridge] 打 tar.gz ..."
cd dist
tar czf "mcbridge-linux-$(uname -m).tar.gz" "MC Bridge Tool/"
cd ..

echo ""
echo "============================================================"
echo " 打包完成！"
echo " 目录版:   dist/MC Bridge Tool/"
echo " 压缩包:   dist/mcbridge-linux-$(uname -m).tar.gz"
echo ""
echo " 运行:"
echo "   ./dist/MC Bridge Tool/MC Bridge Tool"
echo ""
echo " 依赖（在目标机器上需要）:"
echo "   - glibc 2.31+ (Ubuntu 20.04 及以上)"
echo "   - libtk8.6 / libtcl8.6（大多数桌面发行版自带）"
echo "   - 系统已安装 Java 21 或 Java 25（服务端用，不是本工具用）"
echo "============================================================"
