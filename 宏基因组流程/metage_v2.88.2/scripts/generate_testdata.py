#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从完整 FASTQ 数据生成小体积测试数据。

用途：
1. 为每个样本从完整 FASTQ 中提取前 N 条 reads，生成 testdata/ 下的测试文件；
2. 通过指定 --start-read 偏移量，生成与现有测试样本不重复的额外样本（用于模拟客户增加样本）。

示例：
  # 生成标准测试集（前 20 万 reads）
  python3 scripts/generate_testdata.py \
      --src /home/xydeng/Metagenomics_Docker/data \
      --out /home/xydeng/Metagenomics_Docker/testdata \
      --samples RCK1 RCK2 RCK3 RS1 RS2 RS3 SCK1 SCK2 SCK3 SS1 SS2 SS3 \
      --reads 200000

  # 追加 3 个额外样本（从第 20 万条之后取 20 万 reads，避免与现有测试数据重复）
  python3 scripts/generate_testdata.py \
      --src /home/xydeng/Metagenomics_Docker/data \
      --out /home/xydeng/Metagenomics_Docker/testdata \
      --samples NEW1 NEW2 NEW3 \
      --reads 200000 \
      --start-read 200000 \
      --source-samples RCK1 RS1 SCK1
"""

import argparse
import gzip
import os
import sys
from pathlib import Path


def extract_reads(src_r1, src_r2, out_r1, out_r2, reads, start_read=0):
    """从 paired FASTQ 中提取指定范围的 reads。"""
    start_line = start_read * 4
    end_line = (start_read + reads) * 4

    def slice_file(src, dst, start, end):
        with gzip.open(src, "rt") as f_in, gzip.open(dst, "wt", compresslevel=6) as f_out:
            count = 0
            written = 0
            for line in f_in:
                if count >= start and count < end:
                    f_out.write(line)
                    written += 1
                count += 1
                if count >= end:
                    break
        return written // 4

    n1 = slice_file(src_r1, out_r1, start_line, end_line)
    n2 = slice_file(src_r2, out_r2, start_line, end_line)
    if n1 != n2:
        raise ValueError(f"R1/R2 reads 不一致: {n1} vs {n2}")
    return n1


def main():
    parser = argparse.ArgumentParser(description="从完整 FASTQ 生成测试数据")
    parser.add_argument("--src", required=True, help="源 FASTQ 目录（含 *_R1.fq.gz / *_R2.fq.gz）")
    parser.add_argument("--out", required=True, help="输出目录")
    parser.add_argument("--samples", required=True, nargs="+", help="目标样本名列表")
    parser.add_argument("--source-samples", default=None, nargs="+", help="源样本名列表（与 --samples 一一对应；不指定则与 --samples 相同）")
    parser.add_argument("--reads", type=int, default=200000, help="每个样本提取的 reads 数（默认 20 万）")
    parser.add_argument("--start-read", type=int, default=0, help="起始 read 偏移量（默认 0，即从头开始）")
    args = parser.parse_args()

    src_dir = Path(args.src)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    source_samples = args.source_samples or args.samples
    if len(source_samples) != len(args.samples):
        print("ERROR: --samples 和 --source-samples 长度必须一致", file=sys.stderr)
        sys.exit(1)

    for target, source in zip(args.samples, source_samples):
        src_r1 = src_dir / f"{source}_R1.fq.gz"
        src_r2 = src_dir / f"{source}_R2.fq.gz"
        out_r1 = out_dir / f"{target}_R1.fq.gz"
        out_r2 = out_dir / f"{target}_R2.fq.gz"

        if not src_r1.exists() or not src_r2.exists():
            print(f"警告：源文件不存在，跳过 {source}: {src_r1}, {src_r2}", file=sys.stderr)
            continue

        print(f"生成 {target} <- {source} (reads {args.start_read}..{args.start_read + args.reads})")
        n = extract_reads(src_r1, src_r2, out_r1, out_r2, args.reads, args.start_read)
        print(f"  完成：{n} reads -> {out_r1}, {out_r2}")


if __name__ == "__main__":
    main()
