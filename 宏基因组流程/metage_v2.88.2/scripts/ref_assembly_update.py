#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ref_assembly_update.py

对指定参考样本的 clean reads 进行 de novo 组装，生成参考基因组序列。
使用 MEGAHIT 进行组装，输出 ref.fa 供下游 mapping 和 SNP calling 使用。
"""

import os
import sys
import argparse
import logging
import subprocess
import glob

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)


def run_cmd(cmd):
    log.info('执行命令: %s', cmd.strip().split('\n')[0])
    subprocess.run(cmd, shell=True, check=True)


def find_clean_fastq(cleandir, sample_id):
    """
    在 cleandata 目录中定位指定样本的 paired clean reads。
    Kneaddata 输出格式: {sample}_clean_1.fastq.gz / {sample}_clean_2.fastq.gz
    """
    r1 = os.path.join(cleandir, '{}_clean_1.fastq.gz'.format(sample_id))
    r2 = os.path.join(cleandir, '{}_clean_2.fastq.gz'.format(sample_id))

    # fallback: 尝试不带 .gz 的版本
    if not os.path.exists(r1):
        r1_alt = r1.replace('.gz', '')
        r2_alt = r2.replace('.gz', '')
        if os.path.exists(r1_alt):
            return r1_alt, r2_alt

    return r1, r2


def assemble_ref(cleandir, sample_id, outdir, threads=24):
    """使用 MEGAHIT 对参考样本 reads 进行组装。"""
    r1, r2 = find_clean_fastq(cleandir, sample_id)
    if not os.path.exists(r1):
        log.error('参考样本 clean reads 不存在: %s', r1)
        sys.exit(1)
    if not os.path.exists(r2):
        log.error('参考样本 clean reads 不存在: %s', r2)
        sys.exit(1)

    assembly_dir = os.path.join(outdir, 'assembly')
    # MEGAHIT 不允许输出目录已存在，先清理
    if os.path.exists(assembly_dir):
        import shutil
        shutil.rmtree(assembly_dir)
    os.makedirs(assembly_dir, exist_ok=True)

    cmd = (
        'megahit -1 {r1} -2 {r2} -t {threads} -o {assembly_dir} '
        '&& cp {assembly_dir}/final.contigs.fa {outdir}/ref.fa'
    ).format(r1=r1, r2=r2, threads=threads, assembly_dir=assembly_dir, outdir=outdir)
    run_cmd(cmd)

    # 统计组装结果
    with open(os.path.join(outdir, 'ref.fa'), 'r') as f:
        contig_count = 0
        total_bp = 0
        for line in f:
            if line.startswith('>'):
                contig_count += 1
            else:
                total_bp += len(line.strip())
    log.info('参考基因组组装统计: %d contigs, %d bp', contig_count, total_bp)


def main():
    parser = argparse.ArgumentParser(description='参考基因组组装')
    parser.add_argument('-I', '--i_datadir', type=str, required=True,
                        help='包含 sample.txt 的目录')
    parser.add_argument('--cleandir', type=str, required=True,
                        help='clean reads 目录')
    parser.add_argument('--ref_sample', type=str, required=True,
                        help='参考样本 ID')
    parser.add_argument('-o', '--outdir', type=str, default='ref_assembly',
                        help='输出目录')
    parser.add_argument('--threads', type=int, default=24,
                        help='组装线程数')
    args = parser.parse_args()

    outdir = os.path.abspath(args.outdir)
    os.makedirs(outdir, exist_ok=True)

    try:
        log.info('开始参考样本组装: %s', args.ref_sample)
        assemble_ref(args.cleandir, args.ref_sample, outdir, threads=args.threads)
        log.info('参考基因组组装完成，输出: %s/ref.fa', outdir)
    except Exception as e:
        log.error('参考基因组组装失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
