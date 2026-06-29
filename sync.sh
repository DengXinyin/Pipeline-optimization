#!/bin/bash
# ============================================================
# 同步脚本：将服务器工作文件同步到 GitHub 私有仓库
# 用法: ./sync.sh "提交说明"
# ============================================================
set -euo pipefail

COMMIT_MSG="${1:-}"
if [ -z "$COMMIT_MSG" ]; then
    echo "用法: ./sync.sh \"提交说明\""
    echo "示例: ./sync.sh \"完成 Task 17-18 优化\""
    exit 1
fi

SRC="/home/xydeng/Metagenomics/scripts_dxy"
REPO="/home/xydeng/.cache/metagenome-sync"
DST="$REPO/宏基因组"

echo "========================================"
echo "同步宏基因组项目到 GitHub"
echo "========================================"

# 1. 同步文档
echo "→ 同步文档..."
cp "$SRC/Metagenomic_pipeline_optimization_kimi.Qmd" "$DST/"
cp "$SRC/Metagenomic_pipeline_overall.qmd"       "$DST/"
cp "$SRC/Readme_dxy.Qmd"                         "$DST/"
cp "$SRC/Todo_list.txt"                          "$DST/"
cp "$SRC/宏基因组优化效率统计.xlsx"               "$DST/"

# 2. 同步日志（仅 .log 文件）
echo "→ 同步日志..."
mkdir -p "$DST/logs"
rsync -a --delete "$SRC/logs/" "$DST/logs/"

# 3. 同步优化代码
echo "→ 同步代码..."
mkdir -p "$DST/Script"
rsync -a --delete "$SRC/Script/" "$DST/Script/"

# 4. Git 提交
echo "→ 提交..."
cd "$REPO"
git add -A
git commit -m "$COMMIT_MSG

Co-Authored-By: Claude <noreply@anthropic.com>"

# 5. 推送
echo "→ 推送..."
git push origin main

echo "========================================"
echo "✅ 同步完成"
echo "========================================"
