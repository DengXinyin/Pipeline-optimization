#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ref_mapping_update.py

将所有样本的 clean reads 比对到参考基因组，生成排序后的 BAM 文件。
使用 bowtie2 进行比对（镜像中 biobakery 环境已有），samtools 进行排序和索引。
"""

import os
import sys
import argparse
import logging
import subprocess

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)


def run_cmd(cmd):
    log.info('执行命令: %s', cmd.strip().split('\n')[0])
    subprocess.run(cmd, shell=True, check=True)


def parse_sample_txt(sample_txt):
    """解析 sample.txt，返回样本 ID 列表（第二列）。"""
    samples = []
    with open(sample_txt, 'r') as f:
        header = f.readline()
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split('\t')
            if len(parts) >= 2:
                samples.append(parts[1].strip())
    return samples


def find_clean_fastq(cleandir, sample_id):
    """
    定位指定样本的 paired clean reads。
    Kneaddata 输出: {sample}_clean_1.fastq.gz / {sample}_clean_2.fastq.gz
    也兼容非压缩 (.fastq) 版本。
    """
    r1 = os.path.join(cleandir, '{}_clean_1.fastq.gz'.format(sample_id))
    r2 = os.path.join(cleandir, '{}_clean_2.fastq.gz'.format(sample_id))

    if not os.path.exists(r1):
        r1 = r1.replace('.gz', '')
        r2 = r2.replace('.gz', '')
    return r1, r2


def build_bowtie2_index(ref_fasta, index_prefix):
    """构建 bowtie2 参考基因组索引（仅需一次）。"""
    cmd = 'bowtie2-build {ref} {prefix}'.format(ref=ref_fasta, prefix=index_prefix)
    run_cmd(cmd)


def map_sample(index_prefix, cleandir, sample_id, outdir, threads=16):
    """使用 bowtie2 将单个样本的 reads 比对到参考基因组。"""
    r1, r2 = find_clean_fastq(cleandir, sample_id)
    if not os.path.exists(r1) or not os.path.exists(r2):
        log.warning('样本 reads 不存在，跳过: %s', sample_id)
        return

    bam = os.path.join(outdir, '{}.sort.bam'.format(sample_id))

    bowtie_log = os.path.join(outdir, '{}.bowtie2.log'.format(sample_id))
    cmd = (
        'bowtie2 -p {threads} -x {index} -1 {r1} -2 {r2} '
        '2> {bowtie_log} '
        '| samtools sort -@ {threads} -o {bam} - '
        '&& samtools index {bam}'
    ).format(
        threads=threads, index=index_prefix,
        r1=r1, r2=r2, sample=sample_id,
        bam=bam, outdir=outdir, bowtie_log=bowtie_log
    )
    run_cmd(cmd)

    # 统计比对率
    with open(bowtie_log) as f:
        for line in f:
            if 'overall alignment rate' in line:
                log.info('%s: %s', sample_id, line.strip())
    os.remove(bowtie_log)


def main():
    parser = argparse.ArgumentParser(description='参考基因组 mapping')
    parser.add_argument('-I', '--i_datadir', type=str, required=True,
                        help='包含 sample.txt 的目录')
    parser.add_argument('--cleandir', type=str, required=True,
                        help='clean reads 目录')
    parser.add_argument('--ref_fasta', type=str, required=True,
                        help='参考基因组 FASTA 路径')
    parser.add_argument('-o', '--outdir', type=str, default='ref_mapping',
                        help='BAM 输出目录')
    parser.add_argument('--threads', type=int, default=16,
                        help='比对线程数')
    args = parser.parse_args()

    cleandir = os.path.abspath(args.cleandir)
    ref_fasta = os.path.abspath(args.ref_fasta)
    outdir = os.path.abspath(args.outdir)
    os.makedirs(outdir, exist_ok=True)

    sample_txt = os.path.join(os.path.abspath(args.i_datadir), 'sample.txt')
    if not os.path.exists(sample_txt):
        log.error('sample.txt 不存在: %s', sample_txt)
        sys.exit(1)

    try:
        # 1. 构建 bowtie2 索引（仅一次）
        index_prefix = os.path.join(outdir, 'ref')
        log.info('构建 bowtie2 参考基因组索引...')
        build_bowtie2_index(ref_fasta, index_prefix)

        # 2. 对所有样本进行比对
        samples = parse_sample_txt(sample_txt)
        log.info('共 %d 个样本待比对', len(samples))
        for sample_id in samples:
            log.info('mapping: %s', sample_id)
            map_sample(index_prefix, cleandir, sample_id, outdir, threads=args.threads)

        log.info('参考基因组 mapping 完成，输出: %s', outdir)
    except Exception as e:
        log.error('参考基因组 mapping 失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
