#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
tax_anno 优化版 V1：DIAMOND default 模式（精度优先）。

与 V2 的区别：DIAMOND 使用 default 模式（根据文件大小自动判断，>15GB 才启用 --fast）。
V1 的 DIAMOND 阶段与原代码完全一致，优化收益来自 MEGAN 后处理阶段。

优化点：
1. 用 daa-meganizer 替代 legacy 的 daa2rma，直接在 DAA 文件上追加分类索引，避免生成额外 RMA 文件。
2. 保留原代码的所有分类行为（Taxonomy / SEED / EGGNOG / GTDB），确保与下游流程最大兼容。
3. 用 daa2info 直接读取 meganized DAA，替代 rma2info。
4. 所有中间/最终输出写入 --Annotation 目录，避免污染 /prodigal 目录。
5. 增加 argparse 参数化、失败即停（set -euo pipefail）、线程/块大小可调。

对应启动脚本：run_10_tax_anno_update_V1.sh
"""

import os
import argparse
import shutil


def run_cmd(cmd, step_name):
    """执行 shell 命令，返回 exit code。调用方决定是否抛出异常。"""
    print(f"\n=== 开始执行: {step_name} ===")
    print(cmd)
    ret = os.system(cmd)
    if os.WIFEXITED(ret):
        ret = os.WEXITSTATUS(ret)
    elif os.WIFSIGNALED(ret):
        sig = os.WTERMSIG(ret)
        print(f"[ERROR] 进程被信号 {sig} 终止")
        ret = 128 + sig
    print(f"=== 完成: {step_name} (exit={ret}) ===\n")
    return ret


def diamond_blastx(dbdir, prodigal_dir, anno_dir, threads, block_size):
    """运行 diamond blastx（V1：default 模式，按文件大小自动判断）。
    支持 block-size 自适应降级：遇到 OOM 自动减半重试。"""
    daa_out = os.path.join(anno_dir, "unique.daa")
    tmp_dir = os.path.join(anno_dir, "tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    MIN_BLOCK_SIZE = 1.0
    bs = block_size if block_size else 2.0

    while bs >= MIN_BLOCK_SIZE:
        block_opt = f"--block-size {bs}" if bs else ""

        cmd = f'''
set -euo pipefail
file_size=$(du -b {prodigal_dir}/unique_gene.fasta | awk '{{print $1}}')
if [ "$file_size" -gt 16106127360 ]; then
    echo "File is larger than 15GB, performing fast operation..."
    diamond blastx --threads {threads} --fast --log --tmpdir {tmp_dir} \\
        --db {dbdir}/metage2 -q {prodigal_dir}/unique_gene.fasta \\
        --max-target-seqs 10 --evalue 1e-5 -o {daa_out} --outfmt 100 {block_opt} 2>&1
else
    echo "File is smaller than 15GB, performing default operation..."
    diamond blastx --threads {threads} --log --tmpdir {tmp_dir} \\
        --db {dbdir}/metage2 -q {prodigal_dir}/unique_gene.fasta \\
        --max-target-seqs 10 --evalue 1e-5 -o {daa_out} --outfmt 100 {block_opt} 2>&1
fi
'''

        if os.path.exists(daa_out):
            os.remove(daa_out)

        ret = run_cmd(cmd, f"diamond blastx (V1: default, block-size={bs})")

        if ret == 0:
            return

        oom_signal = (ret == 137)
        if oom_signal and bs > MIN_BLOCK_SIZE:
            new_bs = max(bs / 2, MIN_BLOCK_SIZE)
            print(f"[WARN] diamond OOM (block-size={bs})，自动降级为 block-size={new_bs} 重试...")
            bs = new_bs
            continue
        else:
            raise RuntimeError(f"diamond blastx 失败 (exit code {ret}, block-size={bs})")

    raise RuntimeError(f"diamond blastx 在最小 block-size={MIN_BLOCK_SIZE} 仍失败")


def meganize_daa(dbdir, anno_dir, megandir, threads):
    """用 daa-meganizer 在原 DAA 上追加全部分类索引。"""
    daa_file = os.path.join(anno_dir, "unique.daa")
    mdb = os.path.join(dbdir, "megan-nr-r1.mdb")

    cmd = f'''
set -euo pipefail
{megandir}/tools/daa-meganizer -i {daa_file} \\
    -mdb {mdb} \\
    -ms 50 -me 1.0E-7 -top 50 \\
    --minSupport 1 --minPercentIdentity 70 \\
    --lcaCoveragePercent 51 \\
    -t {threads} -v
'''
    ret = run_cmd(cmd, "daa-meganizer")
    if ret != 0:
        raise RuntimeError(f"daa-meganizer 失败 (exit code {ret})")


def extract_taxonomy(anno_dir, megandir):
    """从 meganized DAA 中提取 Taxonomy 映射表。"""
    daa_file = os.path.join(anno_dir, "unique.daa")
    tax_tmp = os.path.join(anno_dir, "Tax_id.tmp.txt")

    cmd = f'''
set -euo pipefail
{megandir}/tools/daa2info -i {daa_file} -r2c Taxonomy -v > {tax_tmp}
sed -i '1i\\GeneID\\ttaxid' {tax_tmp}
'''
    ret = run_cmd(cmd, "daa2info + sed")
    if ret != 0:
        raise RuntimeError(f"daa2info 失败 (exit code {ret})")


def main():
    parser = argparse.ArgumentParser(
        description="tax_anno V1: DIAMOND default 模式 + daa-meganizer + daa2info")
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

    diamond_blastx(dbdir, prodigal_dir, anno_dir, args.threads, args.block_size)
    meganize_daa(dbdir, anno_dir, megandir, args.threads)
    extract_taxonomy(anno_dir, megandir)

    print("\ntax_anno 优化版 V1 运行完成。")
    print(f"输出目录: {anno_dir}")
    print(f"  unique.daa       -> {anno_dir}/unique.daa")
    print(f"  Tax_id.tmp.txt   -> {anno_dir}/Tax_id.tmp.txt")


if __name__ == "__main__":
    main()
