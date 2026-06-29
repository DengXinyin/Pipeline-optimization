#!/usr/bin/env python
# -*- coding: utf-8 -*-
# By: Wang Li 2024
# 20260626_update:
#   1. 输出隔离：emapper 结果写入 --Annotation 目录，不再污染 /prodigal
#   2. 参数化 CPU 数、敏感度模式、e-value、输出前缀
#   3. 使用 subprocess + set -euo pipefail 实现失败即停
#   4. 自动检测 emapper.py，允许通过 --emapperdir 覆盖
#   5. 保留原代码对 >15GB 序列使用 fast 模式、否则用 mid-sensitive 的逻辑

import os
import sys
import argparse
import subprocess


def run_cmd(cmd, step_name):
    """执行 shell 命令，失败即退出。"""
    print(f"[INFO] Starting {step_name}...")
    print(f"[CMD] {cmd}")
    ret = subprocess.run(cmd, shell=True, executable='/bin/bash')
    if ret.returncode != 0:
        print(f"[ERROR] {step_name} failed with exit code {ret.returncode}", file=sys.stderr)
        sys.exit(ret.returncode)
    print(f"[INFO] {step_name} completed.")


def eggNOG_mapper(emapperdir, prodigal_dir, dbdir, anno_dir, cpu, evalue, prefix):
    # 文件大小阈值：15 GB
    threshold = 16106127360

    cmd = f'''
set -euo pipefail

file_size=$(du -b "{prodigal_dir}/unique_gene.fasta" | awk '{{print $1}}')
mkdir -p "{anno_dir}"

if [ "$file_size" -gt {threshold} ]; then
    echo "[INFO] File is larger than 15GB, using --sensmode fast"
    python "{emapperdir}/emapper.py" --cpu {cpu} \
        -i "{prodigal_dir}/unique_gene.fasta" \
        --itype CDS -m diamond --evalue {evalue} \
        --sensmode fast --dmnd_iterate no \
        --data_dir "{dbdir}/eggNOG" \
        -o "{prefix}" \
        --output_dir "{anno_dir}"
else
    echo "[INFO] File is smaller than 15GB, using --sensmode mid-sensitive"
    python "{emapperdir}/emapper.py" --cpu {cpu} \
        -i "{prodigal_dir}/unique_gene.fasta" \
        --itype CDS -m diamond --evalue {evalue} \
        --sensmode mid-sensitive \
        --data_dir "{dbdir}/eggNOG" \
        -o "{prefix}" \
        --output_dir "{anno_dir}"
fi

# 去掉 eggnog-mapper 输出的前 4 行注释和最后 2 行统计信息
annotations="{anno_dir}/{prefix}.emapper.annotations"
sed '1,4d' "$annotations" > "{anno_dir}/{prefix}.emapper.annotations.tmp"
num=$(wc -l < "{anno_dir}/{prefix}.emapper.annotations.tmp")
start=$((num - 2))
sed "${{start}},${{num}}d" "{anno_dir}/{prefix}.emapper.annotations.tmp" > "{anno_dir}/{prefix}.emapper.annotations"
rm -f "{anno_dir}/{prefix}.emapper.annotations.tmp"
'''
    run_cmd(cmd, "eggNOG-mapper annotation")


def main():
    parser = argparse.ArgumentParser(
        description='Optimized func_anno: annotate unique_gene.fasta using eggNOG-mapper'
    )
    parser.add_argument('--Annotation', type=str, default='Annotation',
                        help='Output directory for functional annotation results')
    parser.add_argument('--prodigal', type=str, default='prodigal',
                        help='Directory containing unique_gene.fasta')
    parser.add_argument('--dbdir', type=str, default='/data/data2/metagenome-DB/database',
                        help='Database directory containing eggNOG/ subdirectory')
    parser.add_argument('--emapperdir', type=str, default=None,
                        help='Path to eggnog-mapper directory containing emapper.py '
                             '(default: auto-detect in PATH or common locations)')
    parser.add_argument('--cpu', type=int, default=50,
                        help='Number of CPUs for eggnog-mapper (default: 50)')
    parser.add_argument('--evalue', type=str, default='1e-5',
                        help='E-value threshold for diamond (default: 1e-5)')
    parser.add_argument('--prefix', type=str, default='func',
                        help='Output prefix for eggnog-mapper files (default: func)')
    args = parser.parse_args()

    prodigal_dir = os.path.abspath(args.prodigal)
    anno_dir = os.path.abspath(args.Annotation)
    dbdir = os.path.abspath(args.dbdir)
    cpu = args.cpu
    evalue = args.evalue
    prefix = args.prefix

    if args.emapperdir:
        emapperdir = os.path.abspath(args.emapperdir)
    else:
        # 优先尝试容器内常见路径和 PATH
        candidates = [
            '/app/eggnog-mapper',
            '/opt/eggnog-mapper',
            '/root/eggnog-mapper',
        ]
        emapperdir = None
        for c in candidates:
            if os.path.exists(os.path.join(c, 'emapper.py')):
                emapperdir = c
                break
        if emapperdir is None:
            # 尝试 PATH 中的 emapper.py
            import shutil
            emapper_py = shutil.which('emapper.py')
            if emapper_py:
                emapperdir = os.path.dirname(emapper_py)
        if emapperdir is None:
            print("[ERROR] Cannot find emapper.py. Please specify --emapperdir", file=sys.stderr)
            sys.exit(1)

    if not os.path.exists(os.path.join(prodigal_dir, 'unique_gene.fasta')):
        print(f"[ERROR] unique_gene.fasta not found in {prodigal_dir}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(anno_dir, exist_ok=True)

    print(f"[INFO] prodigal_dir: {prodigal_dir}")
    print(f"[INFO] anno_dir: {anno_dir}")
    print(f"[INFO] dbdir: {dbdir}")
    print(f"[INFO] emapperdir: {emapperdir}")
    print(f"[INFO] cpu: {cpu}")

    eggNOG_mapper(emapperdir, prodigal_dir, dbdir, anno_dir, cpu, evalue, prefix)


if __name__ == '__main__':
    main()
