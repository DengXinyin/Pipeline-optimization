#!/bin/bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
    echo "用法: $0 <包含15个样本的源FASTQ目录> <full专用空目录>" >&2
    exit 2
fi

SOURCE_DIR="${1%/}"
TARGET_DIR="${2%/}"
SAMPLES=(RCK1 RCK2 RCK3 RS1 RS2 RS3 SCK1 SCK2 SCK3 SS1 SS2 SS3)

if [ ! -d "$SOURCE_DIR" ]; then
    echo "ERROR: 源 FASTQ 目录不存在: $SOURCE_DIR" >&2
    exit 2
fi

mkdir -p "$TARGET_DIR"
if [ -n "$(find "$TARGET_DIR" -mindepth 1 -maxdepth 1 -print -quit)" ]; then
    echo "ERROR: 目标目录必须为空: $TARGET_DIR" >&2
    exit 2
fi

for sample in "${SAMPLES[@]}"; do
    for mate in 1 2; do
        source_file="$SOURCE_DIR/${sample}_R${mate}.fq.gz"
        if [ ! -f "$source_file" ]; then
            echo "ERROR: 缺少 FASTQ: $source_file" >&2
            exit 2
        fi
        ln -s "$source_file" "$TARGET_DIR/${sample}_R${mate}.fq.gz"
    done
done

link_count=$(find "$TARGET_DIR" -mindepth 1 -maxdepth 1 -type l | wc -l)
if [ "$link_count" -ne 24 ]; then
    echo "ERROR: 应生成24个FASTQ链接，实际为$link_count" >&2
    exit 2
fi

echo "full FASTQ 视图准备完成: $TARGET_DIR ($link_count files, 12 samples)"
