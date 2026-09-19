#!/data/data/com.termux/files/usr/bin/env bash
# =============================================================================
# MC互通管家 —— Termux 一键引导脚本
# 在 Termux 内执行：bash termux_setup.sh
# 作用：安装 openjdk / python、创建服务器目录、检测 Java 版本
# =============================================================================
set -euo pipefail

# ---- 颜色 ----
G=$'\033[0;32m'; Y=$'\033[1;33m'; R=$'\033[1;31m'; N=$'\033[0m'
info()  { echo "${G}[✓]${N} $*"; }
warn()  { echo "${Y}[!]${N} $*"; }
err()   { echo "${R}[✗]${N} $*" >&2; }

echo "============================================================"
echo "  MC互通管家 · Termux 环境引导"
echo "============================================================"

# ---- 0) 必须在 Termux 里跑 ----
if [ "${PREFIX:-}" != "/data/data/com.termux/files/usr" ]; then
  err "本脚本必须在 Termux 内运行！"
  echo "  当前 PREFIX=${PREFIX:-（空）}"
  exit 1
fi

# ---- 1) 刷新软件源 ----
info "pkg update …"
pkg update -y

# ---- 2) 安装 openjdk-21（Paper 1.21.x 适用，最稳） ----
# 说明：Paper 26.x 需要 openjdk-25，见文末提示；默认装 21 以兼容绝大多数服务端。
info "安装 openjdk-21 / python / 常用工具 …"
pkg install -y openjdk-21 python termux-tools wget curl

# 若用户想用 Paper 26.x，可额外装 openjdk-25（不存在则跳过）
if pkg show openjdk-25 >/dev/null 2>&1; then
  warn "检测到 openjdk-25 可用；如需跑 Paper 26.x，请再执行：pkg install -y openjdk-25"
else
  warn "当前 Termux 源暂无 openjdk-25；Paper 26.x 需 Java 25，可稍后再试。"
fi

# ---- 3) 创建服务器目录 ----
SRV="${HOME}/mcbridge/server"
mkdir -p "${SRV}/plugins"
info "服务器目录已就绪：${SRV}"

# ---- 4) 检测 Java 版本 ----
info "检测 Java 版本 …"
if command -v java >/dev/null 2>&1; then
  JVER="$(java -version 2>&1 | head -n1 || true)"
  info "java 命令：${JVER}"
else
  err "仍未找到 java 命令，请重启 Termux 后再试。"
  exit 1
fi

echo "============================================================"
info "环境引导完成！下一步："
echo "  1) 打开「MC互通管家」App → 环境页 → 点「刷新检测」确认 Java 已识别；"
echo "  2) 到「部署」页选 Paper 版本 → 一键部署；"
echo "  3) 到「配置」页改端口 / 内存 → 保存；"
echo "  4) 到「控制台」页点「启动」；"
echo "  5) 同 Wi-Fi 下用 基岩版(手机/Win10/Xbox) 连接："
echo "       手机IP:19132"
echo "============================================================"
warn "提示：Paper 26.x 需要 openjdk-25；若你选了 26.x 但只装了 21，启动会报错。"
warn "查看本机 IP：ifconfig 或 ip addr show wlan0"
