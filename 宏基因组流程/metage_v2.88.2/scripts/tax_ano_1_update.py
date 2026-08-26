#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
tax_anno 优化版核心脚本（保留全部分类的兼容版）。

优化点：
1. 用 daa-meganizer 替代 legacy 的 daa2rma，直接在 DAA 文件上追加分类索引，避免生成额外 RMA 文件。
2. 保留原代码的所有分类行为（Taxonomy / SEED / EGGNOG / GTDB），确保与下游流程最大兼容。
3. 用 daa2info 直接读取 meganized DAA，替代 rma2info。
4. 所有中间/最终输出写入 --Annotation 目录，避免污染 /prodigal 目录，便于与原始流程并行或独立运行。
5. 增加 argparse 参数化、失败即停（set -euo pipefail）、线程/块大小可调。
"""

import os
import argparse
import shutil


def run_cmd(cmd, step_name):
    """执行 shell 命令，失败时抛出异常并保留上下文。"""
    print(f"\n=== 开始执行: {step_name} ===")
    print(cmd)
    ret = os.system(cmd)
    if ret != 0:
        raise RuntimeError(f"步骤失败: {step_name} (exit code {ret})")
    print(f"=== 完成: {step_name} ===\n")


def diamond_blastx(dbdir, prodigal_dir, anno_dir, threads, block_size, fast=False):
    """运行 diamond blastx，输出到 Annotation 目录。"""
    daa_out = os.path.join(anno_dir, "unique.daa")
    tmp_dir = os.path.join(anno_dir, "tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    # block_size 控制 diamond 内存占用；None 时使用 diamond 默认值
    block_opt = f"--block-size {block_size}" if block_size else ""
    # fast 模式开关：用户显式指定 --fast 时强制使用；否则按文件大小自动判断
    fast_opt = "--fast" if fast else ""

    cmd = f'''
set -euo pipefail
file_size=$(du -b {prodigal_dir}/unique_gene.fasta | awk '{{print $1}}')
if [ "$file_size" -gt 16106127360 ] || [ "{fast}" = "True" ]; then
    echo "Performing fast operation..."
    diamond blastx --threads {threads} --fast --log --tmpdir {tmp_dir} \
        --db {dbdir}/metage2 -q {prodigal_dir}/unique_gene.fasta \
        --max-target-seqs 10 --evalue 1e-5 -o {daa_out} --outfmt 100 {block_opt}
else
    echo "File is smaller than 15GB, performing default operation..."
    diamond blastx --threads {threads} --log --tmpdir {tmp_dir} \
        --db {dbdir}/metage2 -q {prodigal_dir}/unique_gene.fasta \
        --max-target-seqs 10 --evalue 1e-5 -o {daa_out} --outfmt 100 {block_opt}
fi
'''
    run_cmd(cmd, "diamond blastx")


def meganize_daa(dbdir, anno_dir, megandir, threads):
    """用 daa-meganizer 在原 DAA 上追加全部分类索引（兼容原 daa2rma 行为）。"""
    daa_file = os.path.join(anno_dir, "unique.daa")
    mdb = os.path.join(dbdir, "megan-nr-r1.mdb")

    # 原 daa2rma 参数对应到 daa-meganizer：
    #   -ms 50          -> --minScore 50
    #   -me 1e-7        -> --maxExpected 1e-7
    #   --top 50        -> --topPercent 50
    #   --minSupport 1  -> --minSupport 1
    #   --minPercentIdentity 70 -> --minPercentIdentity 70
    #   --lcaCoveragePercent 51 -> --lcaCoveragePercent 51
    #   --threads 60    -> -t / --threads
    # 注意：不指定 -on，保留 megan-nr-r1.mdb 中所有可用分类（Taxonomy / SEED / EGGNOG / GTDB）
    cmd = f'''
set -euo pipefail
{megandir}/tools/daa-meganizer -i {daa_file} \
    -mdb {mdb} \
    -ms 50 -me 1.0E-7 -top 50 \
    --minSupport 1 --minPercentIdentity 70 \
    --lcaCoveragePercent 51 \
    -t {threads} -v
'''
    run_cmd(cmd, "daa-meganizer")


def extract_taxonomy(anno_dir, megandir):
    """从 meganized DAA 中提取 Taxonomy 映射表。"""
    daa_file = os.path.join(anno_dir, "unique.daa")
    tax_tmp = os.path.join(anno_dir, "Tax_id.tmp.txt")

    cmd = f'''
set -euo pipefail
{megandir}/tools/daa2info -i {daa_file} -r2c Taxonomy -v > {tax_tmp}
sed -i '1i\\GeneID\\ttaxid' {tax_tmp}
'''
    run_cmd(cmd, "daa2info + sed")


def main():
    parser = argparse.ArgumentParser(
        description="Optimized tax_anno: DIAMOND + daa-meganizer + daa2info")
    parser.add_argument("--Annotation", type=str, default="Annotation",
                        help="Output directory for tax_anno results")
    parser.add_argument("--prodigal", type=str, default="prodigal",
                        help="Directory containing unique_gene.fasta")
    parser.add_argument("--dbdir", type=str,
                        default="/data/data1/wangli/database/NR",
                        help="Directory containing NR database and MEGAN mapping DB")
    parser.add_argument("--megandir", type=str, default="/data/data1/wangli/soft/megan",
                        help="Directory containing MEGAN7 tools/")
    parser.add_argument("--threads", type=int, default=60,
                        help="Number of threads for diamond and daa-meganizer")
    parser.add_argument("--block-size", type=float, default=None,
                        help="Optional diamond --block-size (default: let diamond decide)")
    parser.add_argument("--fast", action="store_true",
                        help="Force diamond blastx --fast mode regardless of input file size")
    parser.add_argument("--force", action="store_true",
                        help="Remove existing output directory before running")
    args = parser.parse_args()

    anno_dir = os.path.abspath(args.Annotation)
    prodigal_dir = os.path.abspath(args.prodigal)
    dbdir = os.path.abspath(args.dbdir)
    megandir = os.path.abspath(args.megandir)

    if not os.path.exists(os.path.join(prodigal_dir, "unique_gene.fasta")):
        raise FileNotFoundError(
            f"Input not found: {prodigal_dir}/unique_gene.fasta")

    if args.force and os.path.exists(anno_dir):
        shutil.rmtree(anno_dir)
    os.makedirs(anno_dir, exist_ok=True)

    diamond_blastx(dbdir, prodigal_dir, anno_dir, args.threads, args.block_size, fast=args.fast)
    meganize_daa(dbdir, anno_dir, megandir, args.threads)
    extract_taxonomy(anno_dir, megandir)

    print("\ntax_anno 优化版运行完成。")
    print(f"输出目录: {anno_dir}")
    print(f"  unique.daa       -> {anno_dir}/unique.daa")
    print(f"  Tax_id.tmp.txt   -> {anno_dir}/Tax_id.tmp.txt")


if __name__ == "__main__":
    main()
