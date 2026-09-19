#!/usr/bin/env bash
# 一键发布：在已存在的空仓库上推送代码 + tag，并创建 GitHub Release 上传产物。
# 用法：
#   1) 网页先建好空 Public 仓库 wjj481/mc-bridge-tool（不要勾 README/LICENSE/.gitignore）
#   2) 本脚本与 Linux 二进制在项目根目录，执行：
#        bash scripts/publish.sh
#   3) 如需用 API 建仓/发 Release（需要 PAT）：
#        GH_TOKEN=ghp_xxx bash scripts/publish.sh create-release
set -euo pipefail
cd "$(dirname "$0")/.."

TAG="v1.0.0"
REMOTE="git@github.com:wjj481/mc-bridge-tool.git"

echo "==> 推送 main 与 tag $TAG"
git remote remove origin 2>/dev/null || true
git remote add origin "$REMOTE"
git push -u origin main
git push origin "$TAG"

if [ "${1:-}" = "create-release" ]; then
  : "${GH_TOKEN:?需要 GH_TOKEN=ghp_xxx}"
  echo "==> 创建 Release 并上传 Linux 产物"
  gh release create "$TAG" \
    --repo wjj481/mc-bridge-tool \
    --title "MC Bridge Tool $TAG" \
    --notes "全按钮化 MC Java/基岩互通管理器。详见 README。Windows/macOS/Android 二进制由 Actions 自动构建。" \
    MC-Bridge-Tool-Linux-x86_64.tar.gz \
    MC-Bridge-Tool-Linux-x86_64.sha256
else
  echo "==> 代码与 tag 已推送。Windows/macOS/Android 由 Actions 自动出包。"
  echo "==> 若要本地上传 Linux 产物到 Release，执行：GH_TOKEN=xxx bash scripts/publish.sh create-release"
fi
