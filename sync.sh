#!/bin/bash
# ============================================================
# 同步脚本：将服务器工作文件直接推送到 GitHub
# 用法: sync "提交说明"
# 不在服务器上留任何 git 痕迹，每次在 /tmp 临时操作
# ============================================================
set -euo pipefail

COMMIT_MSG="${1:-}"
if [ -z "$COMMIT_MSG" ]; then
    echo "用法: sync \"提交说明\""
    echo "示例: sync \"完成 Task 17-18 优化\""
    exit 1
fi

SRC="/home/xydeng/Metagenomics/scripts_dxy"
REPO_URL="git@github.com:DengXinyin/Pipeline-optimization.git"

echo "========================================"
echo "同步宏基因组项目到 GitHub"
echo "========================================"

# 1. 临时克隆
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
echo "→ 拉取仓库..."
git clone --depth 1 "$REPO_URL" "$TMP" 2>&1 | tail -1

DST="$TMP/宏基因组"

# 2. 同步文档
echo "→ 同步文档..."
cp "$SRC/Metagenomic_pipeline_optimization_kimi.Qmd" "$DST/"
cp "$SRC/Metagenomic_pipeline_overall.qmd"       "$DST/"
cp "$SRC/Readme_dxy.Qmd"                         "$DST/"
cp "$SRC/Todo_list.txt"                          "$DST/"
cp "$SRC/宏基因组优化效率统计.xlsx"               "$DST/"

# 3. 同步日志
echo "→ 同步日志..."
mkdir -p "$DST/logs"
rsync -a --delete "$SRC/logs/" "$DST/logs/"

# 4. 同步优化代码
echo "→ 同步代码..."
mkdir -p "$DST/Script"
rsync -a --delete "$SRC/Script/" "$DST/Script/"

# 5. 提交并推送
echo "→ 提交推送..."
cd "$TMP"
git add -A
git -c user.name="DengXinyin" -c user.email="xydeng@metagenomics" \
    commit -m "$COMMIT_MSG

Co-Authored-By: Claude <noreply@anthropic.com>"
git push origin main

echo "========================================"
echo "✅ 同步完成（临时文件已清理）"
echo "========================================"
