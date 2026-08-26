#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
prodigal 基因预测优化版(prodigal_update.py)

优化点：
  1. 全局 chunk 池：所有样本的所有 chunk 进入同一个 GNU Parallel 任务池，
     同时实现样本内并行和样本间并行。
  2. 移除原代码保守的 `parallel --memfree 50G` 限制，充分利用 72 核。
  3. 输出文件已存在时默认跳过; chunk 中间结果已存在时也支持续跑。
  4. 增加失败即停、进度打印、运行时间记录，便于后续统计。
  5. mmseqs 聚类阶段保留原逻辑，线程数可参数化。

使用方法：
  python prodigal_update.py \
      --megahit /megahit \
      --prodigal /prodigal \
      --cdhitdir /app/cd-hit-v4.8.1-2019-0228 \
      --threads 60 \
      --chunk-size-mb 200
"""

import os
import sys
import math
import argparse
import subprocess
import time
import glob
import shutil
from datetime import datetime


def parse_args():
    parser = argparse.ArgumentParser(
        description='优化版 prodigal 基因预测与 mmseqs 去冗余聚类')
    parser.add_argument('--megahit', type=str, default='megahit',
                        help='megahit 输出目录，含 sample.name.txt 与各样本 final.contigs.fa')
    parser.add_argument('--prodigal', type=str, default='prodigal',
                        help='prodigal 输出目录')
    parser.add_argument('--cdhitdir', type=str, default='/app/cd-hit-v4.8.1-2019-0228',
                        help='cd-hit 目录（保留参数兼容，当前未使用）')
    parser.add_argument('--threads', type=int, default=60,
                        help='mmseqs 聚类使用的线程数（默认 60）')
    parser.add_argument('--chunk-size-mb', type=int, default=200,
                        help='每个 prodigal chunk 的目标大小（MB），默认 200')
    parser.add_argument('--force', action='store_true',
                        help='强制重新运行，即使输出文件已存在')
    return parser.parse_args()


def log(msg):
    """带时间戳的日志打印。"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def run_cmd(cmd, check=True, shell=True):
    """执行 shell 命令，支持失败即停。"""
    log(f"RUN: {cmd[:200]}{'...' if len(cmd) > 200 else ''}")
    ret = subprocess.run(cmd, shell=shell, executable='/bin/bash')
    if check and ret.returncode != 0:
        raise RuntimeError(f"命令执行失败，退出码 {ret.returncode}: {cmd[:200]}")
    return ret


def read_sample_names(sample_name_file):
    """读取 sample.name.txt，返回样本绝对路径列表。"""
    samples = []
    with open(sample_name_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(line)
    return samples


def estimate_chunks(contigs_file, chunk_size_mb):
    """根据文件大小估算需要拆分的 chunk 数。"""
    size_bytes = os.path.getsize(contigs_file)
    chunk_size_bytes = chunk_size_mb * 1024 * 1024
    if size_bytes <= chunk_size_bytes:
        return 1
    return max(1, math.ceil(size_bytes / chunk_size_bytes))


def split_fasta_python(input_file, out_dir, sample_basename, n_chunks):
    """
    使用纯 Python 按记录拆分 FASTA，尽量按总碱基数均衡。
    返回生成的 chunk 文件路径列表。
    """
    records = []
    total_bases = 0
    with open(input_file, 'r', encoding='utf-8') as f:
        current = None
        for line in f:
            line = line.rstrip('\n')
            if line.startswith('>'):
                if current is not None:
                    records.append(current)
                current = {'header': line, 'seq_parts': []}
            else:
                if current is None:
                    raise ValueError(f"FASTA 格式错误：在 {input_file} 中遇到序列前没有 header")
                current['seq_parts'].append(line)
                total_bases += len(line)
        if current is not None:
            records.append(current)

    if not records:
        raise ValueError(f"未在 {input_file} 中读取到任何序列")

    target_per_chunk = total_bases / n_chunks
    chunk_files = []
    chunk_idx = 0
    chunk_bases = 0
    chunk_path = os.path.join(out_dir, f"{sample_basename}_chunk_{chunk_idx:03d}.fa")
    chunk_files.append(chunk_path)
    out_f = open(chunk_path, 'w', encoding='utf-8')

    for rec in records:
        seq = ''.join(rec['seq_parts'])
        out_f.write(f"{rec['header']}\n")
        for i in range(0, len(seq), 60):
            out_f.write(seq[i:i+60] + '\n')
        chunk_bases += len(seq)

        if chunk_bases >= target_per_chunk and chunk_idx < n_chunks - 1:
            out_f.close()
            chunk_idx += 1
            chunk_bases = 0
            chunk_path = os.path.join(out_dir, f"{sample_basename}_chunk_{chunk_idx:03d}.fa")
            chunk_files.append(chunk_path)
            out_f = open(chunk_path, 'w', encoding='utf-8')

    out_f.close()
    return chunk_files


def split_fasta_seqkit(input_file, out_dir, sample_basename, n_chunks):
    """使用 seqkit split2 拆分 FASTA；失败则退回 Python 实现。"""
    chunk_subdir = os.path.join(out_dir, f"{sample_basename}_seqkit")
    os.makedirs(chunk_subdir, exist_ok=True)
    cmd = f"seqkit split2 -p {n_chunks} -f -O {chunk_subdir} {input_file}"
    try:
        run_cmd(cmd)
    except Exception as e:
        log(f"seqkit split2 失败，退回 Python 拆分: {e}")
        return split_fasta_python(input_file, out_dir, sample_basename, n_chunks)

    pattern = os.path.join(chunk_subdir, os.path.basename(input_file) + '.part_*.fa')
    files = sorted(glob.glob(pattern))
    if len(files) != n_chunks:
        log(f"seqkit 拆分结果数量不符（期望 {n_chunks}，实际 {len(files)}），退回 Python 拆分")
        return split_fasta_python(input_file, out_dir, sample_basename, n_chunks)
    return files


def final_outputs_exist(sample_basename, prodigal_dir):
    """检查样本最终输出是否已存在。"""
    out_gff = os.path.join(prodigal_dir, f"{sample_basename}.gff3")
    out_fastq = os.path.join(prodigal_dir, f"{sample_basename}.fastq")
    out_faa = os.path.join(prodigal_dir, f"{sample_basename}.faa")
    return all(os.path.exists(p) for p in [out_gff, out_fastq, out_faa])


def chunk_outputs_exist(chunk_file):
    """检查单个 chunk 的 prodigal 输出是否已全部存在。"""
    return all(os.path.exists(chunk_file + ext) for ext in ['.gff3', '.fastq', '.faa'])


def prepare_all_samples(sample_paths, megahit_dir, prodigal_dir,
                        chunk_size_mb, force, use_seqkit=False):
    """
    为所有样本准备 chunk。
    返回：
      - samples_to_run: [(sample_basename, chunk_files), ...]，仅包含需要处理的样本
      - skipped: 已跳过样本名列表
    """
    samples_to_run = []
    skipped = []

    for sample_path in sample_paths:
        sample_basename = os.path.basename(sample_path)
        contigs_file = os.path.join(megahit_dir, sample_basename, 'final.contigs.fa')

        if not force and final_outputs_exist(sample_basename, prodigal_dir):
            log(f"[SKIP] {sample_basename}: 最终输出已存在")
            skipped.append(sample_basename)
            continue

        n_chunks = estimate_chunks(contigs_file, chunk_size_mb)
        log(f"[PREPARE] {sample_basename}: {contigs_file} -> {n_chunks} chunk(s)")

        chunk_dir = os.path.join(prodigal_dir, '.chunks_v2', sample_basename)
        os.makedirs(chunk_dir, exist_ok=True)

        t0 = time.time()
        if use_seqkit:
            chunk_files = split_fasta_seqkit(contigs_file, chunk_dir, sample_basename, n_chunks)
        else:
            chunk_files = split_fasta_python(contigs_file, chunk_dir, sample_basename, n_chunks)
        log(f"[SPLIT] {sample_basename}: 拆分为 {len(chunk_files)} 个 chunk，耗时 {time.time()-t0:.1f}s")

        samples_to_run.append((sample_basename, chunk_files))

    return samples_to_run, skipped


def run_prodigal_global(samples_to_run, prodigal_dir):
    """
    全局 chunk 池：把所有需要跑的 chunk 汇总到一个 parallel 任务中。
    已存在的 chunk 输出会被跳过。
    """
    global_list_file = os.path.join(prodigal_dir, '.chunks_v2', 'global_chunks.list')
    os.makedirs(os.path.dirname(global_list_file), exist_ok=True)

    chunks_to_run = []
    skipped_chunks = 0
    for sample_basename, chunk_files in samples_to_run:
        for cf in chunk_files:
            if chunk_outputs_exist(cf):
                skipped_chunks += 1
            else:
                chunks_to_run.append(cf)

    if skipped_chunks:
        log(f"[RESUME] {skipped_chunks} 个 chunk 输出已存在，跳过 prodigal")

    if not chunks_to_run:
        log("[SKIP] 所有 chunk 输出均已存在，跳过 prodigal 阶段")
        return 0

    with open(global_list_file, 'w', encoding='utf-8') as f:
        for cf in chunks_to_run:
            f.write(cf + '\n')

    n_chunks = len(chunks_to_run)
    log(f"[PREDICT] 全局 chunk 池：共 {n_chunks} 个 chunk 进入并行 prodigal")

    t0 = time.time()
    cmd = f"""
parallel -j 0 --xapply \
    'prodigal -i {{1}} -f gff \
    -o {{1}}.gff3 -d {{1}}.fastq -a {{1}}.faa -p meta -q' \
    :::: {global_list_file}
"""
    run_cmd(cmd)
    elapsed = time.time() - t0
    log(f"[PREDICT] 全局 prodigal 完成，{n_chunks} 个 chunk，耗时 {elapsed:.1f}s")
    return elapsed


def merge_sample(sample_basename, chunk_files, prodigal_dir):
    """合并单个样本的 chunk 输出为最终 .gff3 / .fastq / .faa。"""
    out_gff = os.path.join(prodigal_dir, f"{sample_basename}.gff3")
    out_fastq = os.path.join(prodigal_dir, f"{sample_basename}.fastq")
    out_faa = os.path.join(prodigal_dir, f"{sample_basename}.faa")

    t0 = time.time()
    with open(out_gff, 'w', encoding='utf-8') as out_gff_f, \
         open(out_fastq, 'w', encoding='utf-8') as out_fastq_f, \
         open(out_faa, 'w', encoding='utf-8') as out_faa_f:
        for cf in chunk_files:
            with open(cf + '.gff3', 'r', encoding='utf-8') as f:
                out_gff_f.write(f.read())
            with open(cf + '.fastq', 'r', encoding='utf-8') as f:
                out_fastq_f.write(f.read())
            with open(cf + '.faa', 'r', encoding='utf-8') as f:
                out_faa_f.write(f.read())

    log(f"[MERGE] {sample_basename}: 合并 {len(chunk_files)} 个 chunk，耗时 {time.time()-t0:.1f}s")


def run_prodigal_all(sample_paths, megahit_dir, prodigal_dir,
                     chunk_size_mb, force, use_seqkit=False):
    """对所有样本执行全局 chunk 池优化版 prodigal。"""
    log("=" * 60)
    log("开始 prodigal 基因预测（全局 chunk 池：样本内 + 样本间并行）")
    log("=" * 60)
    t0 = time.time()

    samples_to_run, skipped = prepare_all_samples(
        sample_paths, megahit_dir, prodigal_dir,
        chunk_size_mb, force, use_seqkit)

    if skipped:
        log(f"[SKIP] 已跳过 {len(skipped)} 个样本: {', '.join(skipped)}")

    if not samples_to_run:
        log("所有样本最终输出均已存在，跳过 prodigal 阶段")
        return 0

    run_prodigal_global(samples_to_run, prodigal_dir)

    for sample_basename, chunk_files in samples_to_run:
        merge_sample(sample_basename, chunk_files, prodigal_dir)

    elapsed = time.time() - t0
    log(f"prodigal 阶段总耗时: {elapsed/60:.1f} 分钟")
    return elapsed


def run_mmseqs(prodigal_dir, threads):
    """执行 mmseqs 聚类去冗余，生成 unique_gene.fasta。"""
    log("=" * 60)
    log("开始 mmseqs 聚类去冗余")
    log("=" * 60)
    t0 = time.time()

    all_fa = os.path.join(prodigal_dir, 'all.fa')
    unique_gene = os.path.join(prodigal_dir, 'unique_gene.fasta')
    unique_length = os.path.join(prodigal_dir, 'unique_length.txt')
    unique_stats = os.path.join(prodigal_dir, 'unique_stats.txt')

    run_cmd(f"cat {prodigal_dir}/*.fastq > {all_fa}")
    all_fa_size = os.path.getsize(all_fa)
    log(f"all.fa 大小: {all_fa_size / 1024**3:.2f} GB")

    if all_fa_size > 20 * 1024**3:
        log("all.fa > 20GB，使用 mmseqs easy-linclust")
        cmd = (
            f"mmseqs easy-linclust {all_fa} {prodigal_dir}/clusterRes "
            f"{prodigal_dir}/tmp --kmer-per-seq-scale 0.3 --min-seq-id 0.95 "
            f"-c 0.9 --cov-mode 1 --cluster-mode 2 --threads {threads}"
        )
    else:
        log("all.fa <= 20GB，使用 mmseqs easy-cluster")
        cmd = (
            f"mmseqs easy-cluster {all_fa} {prodigal_dir}/clusterRes "
            f"{prodigal_dir}/tmp --min-seq-id 0.95 -c 0.9 --cov-mode 1 "
            f"--cluster-mode 2 --threads {threads}"
        )
    run_cmd(cmd)

    run_cmd(f"cp {prodigal_dir}/clusterRes_rep_seq.fasta {unique_gene}")
    run_cmd(f"seqkit fx2tab -j 36 -l -n -i -H {unique_gene} > {unique_length}")
    run_cmd(f"assembly-stats -t {unique_gene} > {unique_stats}")

    # 清理 mmseqs 临时目录，避免 broken symlink 导致 Cromwell localize 失败
    tmp_dir = os.path.join(prodigal_dir, 'tmp')
    if os.path.isdir(tmp_dir):
        log(f"清理 mmseqs 临时目录: {tmp_dir}")
        shutil.rmtree(tmp_dir)

    elapsed = time.time() - t0
    log(f"mmseqs 阶段总耗时: {elapsed/60:.1f} 分钟")
    return elapsed


def main():
    args = parse_args()
    megahit_dir = os.path.abspath(args.megahit)
    prodigal_dir = os.path.abspath(args.prodigal)

    if not os.path.exists(prodigal_dir):
        os.makedirs(prodigal_dir)

    sample_name_file = os.path.join(megahit_dir, 'sample.name.txt')
    if not os.path.exists(sample_name_file):
        raise FileNotFoundError(f"找不到 sample.name.txt: {sample_name_file}")

    sample_paths = read_sample_names(sample_name_file)
    log(f"样本列表: {sample_paths}")

    total_t0 = time.time()
    run_prodigal_all(sample_paths, megahit_dir, prodigal_dir,
                     args.chunk_size_mb, args.force, use_seqkit=False)
    run_mmseqs(prodigal_dir, args.threads)
    total_elapsed = time.time() - total_t0

    log("=" * 60)
    log(f"全部完成！总 wall-clock 时间: {total_elapsed/60:.1f} 分钟")
    log("=" * 60)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        log(f"ERROR: {e}")
        sys.exit(1)
