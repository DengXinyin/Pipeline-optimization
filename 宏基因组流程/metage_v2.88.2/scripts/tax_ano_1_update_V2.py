#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
tax_anno 优化版 V2：DIAMOND --fast 模式（速度优先）。

与 V1 的区别：DIAMOND 强制使用 --fast 模式，不考虑文件大小。
V2 wall-clock 预计 7–12h（V1 约 32h），但灵敏度下降，可能丢失部分低相似度/远缘物种比对。

优化点：
1. 保留 DIAMOND 的 --fast 模式与可调 block-size。
2. MEGAN 分类转换恢复为原流程的 daa2rma → rma2info，只提取 Taxonomy。
3. 所有中间/最终输出写入 --Annotation 目录，避免污染 /prodigal 目录。
4. 增加 argparse 参数化、失败即停（set -euo pipefail）、线程/块大小可调。

对应启动脚本：run_10_tax_anno_update_V2.sh
"""

import os
import argparse
import shutil


def run_cmd(cmd, step_name):
    """执行 shell 命令，返回 exit code。调用方决定是否抛出异常。"""
    print(f"\n=== 开始执行: {step_name} ===")
    print(cmd)
    ret = os.system(cmd)
    # os.system 返回 waitpid 状态，需提取真实 exit code
    if os.WIFEXITED(ret):
        ret = os.WEXITSTATUS(ret)
    elif os.WIFSIGNALED(ret):
        sig = os.WTERMSIG(ret)
        print(f"[ERROR] 进程被信号 {sig} 终止")
        ret = 128 + sig
    print(f"=== 完成: {step_name} (exit={ret}) ===\n")
    return ret


def diamond_blastx(dbdir, prodigal_dir, anno_dir, threads, block_size):
    """运行 diamond blastx（V2：强制 --fast 模式，速度优先）。
    支持 block-size 自适应降级：遇到 OOM 自动减半重试。"""
    daa_out = os.path.join(anno_dir, "unique.daa")
    tmp_dir = os.path.join(anno_dir, "tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    MIN_BLOCK_SIZE = 1.0
    bs = block_size if block_size else 2.0  # diamond 默认值

    while bs >= MIN_BLOCK_SIZE:
        block_opt = f"--block-size {bs}" if bs else ""

        cmd = f'''
set -euo pipefail
echo "V2: 强制使用 --fast 模式（速度优先，灵敏度下降）"
diamond blastx --threads {threads} --fast --log --tmpdir {tmp_dir} \\
    --db {dbdir}/metage2 -q {prodigal_dir}/unique_gene.fasta \\
    --max-target-seqs 10 --evalue 1e-5 -o {daa_out} --outfmt 100 {block_opt} 2>&1
'''

        # 清空可能残留的 daa 文件
        if os.path.exists(daa_out):
            os.remove(daa_out)

        ret = run_cmd(cmd, f"diamond blastx (V2: --fast, block-size={bs})")

        if ret == 0:
            return  # 成功

        # 判断是否为内存不足
        oom_signal = (ret == 137)  # SIGKILL (9) by OOM killer → 128+9=137
        if oom_signal and bs > MIN_BLOCK_SIZE:
            new_bs = max(bs / 2, MIN_BLOCK_SIZE)
            print(f"[WARN] diamond OOM (block-size={bs})，自动降级为 block-size={new_bs} 重试...")
            bs = new_bs
            continue
        else:
            raise RuntimeError(f"diamond blastx 失败 (exit code {ret}, block-size={bs})")

    raise RuntimeError(f"diamond blastx 在最小 block-size={MIN_BLOCK_SIZE} 仍失败")


def convert_daa_to_rma(dbdir, anno_dir, megandir, threads):
    """恢复原流程：用 daa2rma 将 DAA 转换为 RMA。"""
    daa_file = os.path.join(anno_dir, "unique.daa")
    rma_file = os.path.join(anno_dir, "unique.rma")
    mdb = os.path.join(dbdir, "megan-nr-r1.mdb")

    cmd = f'''
set -euo pipefail
{megandir}/tools/daa2rma -i {daa_file} \\
    -mdb {mdb} \\
    -ms 50 -me 1.0E-7 -top 50 \\
    --minSupport 1 --minPercentIdentity 70 \\
    --lcaCoveragePercent 51 \\
    --threads {threads} -o {rma_file}
'''
    ret = run_cmd(cmd, "daa2rma")
    if ret != 0:
        raise RuntimeError(f"daa2rma 失败 (exit code {ret})")
    return rma_file


def extract_taxonomy_from_rma(rma_file, anno_dir, megandir):
    """恢复原流程：从 RMA 中提取 Taxonomy 映射表。"""
    tax_tmp = os.path.join(anno_dir, "Tax_id.tmp.txt")

    cmd = f'''
set -euo pipefail
{megandir}/tools/rma2info -i {rma_file} -r2c Taxonomy -v > {tax_tmp}
sed -i '1i\\GeneID\\ttaxid' {tax_tmp}
'''
    ret = run_cmd(cmd, "rma2info + sed")
    if ret != 0:
        raise RuntimeError(f"rma2info 失败 (exit code {ret})")


def main():
    parser = argparse.ArgumentParser(
        description="tax_anno V2: DIAMOND --fast 模式 + daa2rma + rma2info")
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
                        help="Number of threads for diamond and daa2rma")
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
    rma_file = convert_daa_to_rma(dbdir, anno_dir, megandir, args.threads)
    extract_taxonomy_from_rma(rma_file, anno_dir, megandir)

    print("\ntax_anno 优化版 V2 运行完成。")
    print(f"输出目录: {anno_dir}")
    print(f"  unique.daa       -> {anno_dir}/unique.daa")
    print(f"  unique.rma       -> {anno_dir}/unique.rma")
    print(f"  Tax_id.tmp.txt   -> {anno_dir}/Tax_id.tmp.txt")


if __name__ == "__main__":
    main()
