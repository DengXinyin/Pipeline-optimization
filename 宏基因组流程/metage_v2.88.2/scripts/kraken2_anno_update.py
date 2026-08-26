#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
kraken2_anno_update.py

对去宿主/质控后的 clean FASTQ 数据执行 kraken2 物种注释，
并调用 bracken 校正丰度（Species / Genus 两个层级）。

输出结构：
    outdir/
        <sample>/<sample>.kraken2.out          # kraken2 原始输出
        <sample>/<sample>.kreport2.txt         # kraken2 report
        <sample>/<sample>.S.bracken.txt        # bracken Species 丰度
        <sample>/<sample>.G.bracken.txt        # braken Genus 丰度
        <sample>/<sample>.S.bracken.kreport.txt
        <sample>/<sample>.G.bracken.kreport.txt
"""

import os
import sys
import argparse
import logging
import subprocess
import gzip
import re

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)


def run_cmd(cmd, check=True):
    log.info('执行命令: %s', cmd.strip().split('\n')[0][:200])
    subprocess.run(cmd, shell=True, check=check)


def parse_sample_txt(sample_txt):
    """读取 sample.txt，返回 [(fastq_base, sample_id), ...]。"""
    samples = []
    with open(sample_txt, 'r') as f:
        header = f.readline().strip().split('\t')
        # 兼容列名大小写/空格
        header_lower = [h.strip().lower() for h in header]
        try:
            sample_idx = header_lower.index('sample')
        except ValueError:
            sample_idx = 1  # 默认第二列
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) > sample_idx:
                samples.append(parts[sample_idx])
    return samples


def get_clean_fastq(clean_dir, sample_id):
    """
    在 clean_dir 中定位 clean reads。
    优先找去宿主后的 *_rm_1/2.fastq.gz；其次找 *_clean_1/2.fastq.gz。
    """
    candidates = [
        ('{}_rm_1.fastq.gz'.format(sample_id), '{}_rm_2.fastq.gz'.format(sample_id)),
        ('{}_clean_1.fastq.gz'.format(sample_id), '{}_clean_2.fastq.gz'.format(sample_id)),
        ('{}_dehost_1.fastq.gz'.format(sample_id), '{}_dehost_2.fastq.gz'.format(sample_id)),
    ]
    for r1, r2 in candidates:
        p1 = os.path.join(clean_dir, r1)
        p2 = os.path.join(clean_dir, r2)
        if os.path.exists(p1) and os.path.exists(p2):
            return p1, p2
    return None, None


def estimate_read_length(fq_path, n=10000):
    """从 gzip fastq 中随机抽取 n 条 reads，估算平均读长。"""
    if not os.path.exists(fq_path):
        return 150
    try:
        cmd = "zcat {0} | awk 'NR%4==2 {{sum+=length($0); cnt++; if(cnt>={1}) exit}} END {{if(cnt>0) printf(\"%.0f\", sum/cnt); else print 150}}'".format(fq_path, n)
        out = subprocess.check_output(cmd, shell=True, text=True).strip()
        length = int(out) if out else 150
        return max(50, min(length, 500))
    except Exception as e:
        log.warning('估算读长失败，使用默认值 150: %s', e)
        return 150


def ensure_bracken_kmer_dist(db_dir, read_length, threads=8, kmer_len=35):
    """
    选择数据库中与实际读长最接近的 Bracken kmer distribution。

    预构建数据库通常只提供固定读长（例如 100/150/200 bp）。清洗后
    FASTQ 可能仍是 151 bp；这种情况下应使用最接近的 150 bp 分布，
    不能尝试修改只读的预构建数据库。
    """
    dist_file = os.path.join(db_dir, 'database{}mers.kmer_distrib'.format(read_length))
    if os.path.exists(dist_file) and os.path.getsize(dist_file) > 0:
        return read_length

    available = []
    pattern = re.compile(r'^database(\d+)mers\.kmer_distrib$')
    for name in os.listdir(db_dir):
        match = pattern.match(name)
        path = os.path.join(db_dir, name)
        if match and os.path.isfile(path) and os.path.getsize(path) > 0:
            available.append(int(match.group(1)))

    if not available:
        raise RuntimeError(
            'Bracken数据库没有可用的 database<mers>.kmer_distrib: {}'.format(db_dir)
        )

    selected = min(available, key=lambda length: (abs(length - read_length), length))
    log.warning(
        'Bracken无 %d bp 分布文件，使用最接近的 %d bp（可用: %s）',
        read_length, selected, ','.join(str(x) for x in sorted(available))
    )
    return selected


def run_kraken2(sample_id, r1, r2, db_dir, outdir, threads=8):
    sample_out = os.path.join(outdir, sample_id)
    os.makedirs(sample_out, exist_ok=True)

    kraken_out = os.path.join(sample_out, '{}.kraken2.out'.format(sample_id))
    kreport = os.path.join(sample_out, '{}.kreport2.txt'.format(sample_id))

    cmd = ('kraken2 --db {db} --paired --threads {t} '
           '--output {ko} --report {rep} {r1} {r2}').format(
        db=db_dir, t=threads, ko=kraken_out, rep=kreport, r1=r1, r2=r2)
    run_cmd(cmd)
    return kraken_out, kreport


def run_bracken(sample_id, kreport, db_dir, outdir, read_length, level, threads=8):
    sample_out = os.path.join(outdir, sample_id)
    os.makedirs(sample_out, exist_ok=True)

    output = os.path.join(sample_out, '{}.{}.bracken.txt'.format(sample_id, level))
    out_report = os.path.join(sample_out, '{}.{}.bracken.kreport.txt'.format(sample_id, level))

    cmd = ('bracken -d {db} -i {rep} -o {out} -w {wrep} '
           '-r {rl} -l {lvl} -t {t}').format(
        db=db_dir, rep=kreport, out=output, wrep=out_report,
        rl=read_length, lvl=level, t=threads)
    run_cmd(cmd)
    for path in (output, out_report):
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            raise RuntimeError('Bracken未生成有效输出: {}'.format(path))
    return output, out_report


def main():
    parser = argparse.ArgumentParser(description='kraken2 + bracken 物种注释')
    parser.add_argument('-i', '--cleandir', type=str, required=True,
                        help='clean reads 目录（含 *_clean_1/2.fastq.gz 或 *_rm_1/2.fastq.gz）')
    parser.add_argument('-I', '--i_datadir', type=str, required=True,
                        help='包含 sample.txt 的目录')
    parser.add_argument('--db', type=str, required=True,
                        help='kraken2 数据库目录')
    parser.add_argument('-o', '--outdir', type=str, default='kraken2_out',
                        help='输出目录')
    parser.add_argument('--threads', type=int, default=8,
                        help='kraken2 / bracken 线程数')
    parser.add_argument('--read-length', type=int, default=None,
                        help='bracken 读长，默认自动估算')
    parser.add_argument('--bracken-levels', type=str, default='S,G',
                        help='bracken 层级，逗号分隔，默认 S,G')
    args = parser.parse_args()

    cleandir = os.path.abspath(args.cleandir)
    datadir = os.path.abspath(args.i_datadir)
    db_dir = os.path.abspath(args.db)
    outdir = os.path.abspath(args.outdir)
    os.makedirs(outdir, exist_ok=True)

    sample_txt = os.path.join(datadir, 'sample.txt')
    if not os.path.exists(sample_txt):
        log.error('sample.txt 不存在: %s', sample_txt)
        sys.exit(1)

    if not os.path.isdir(db_dir):
        log.error('kraken2 数据库目录不存在: %s', db_dir)
        sys.exit(1)

    samples = parse_sample_txt(sample_txt)
    if not samples:
        log.error('sample.txt 中未解析到样本')
        sys.exit(1)

    # 估算读长：用第一个样本的 R1
    read_length = args.read_length
    if read_length is None:
        first_r1, _ = get_clean_fastq(cleandir, samples[0])
        if first_r1:
            read_length = estimate_read_length(first_r1)
        else:
            read_length = 150
        log.info('自动估算 bracken 读长: %d', read_length)

    # 使用数据库已有且最接近实际读长的 Bracken distribution。
    read_length = ensure_bracken_kmer_dist(
        db_dir, read_length, threads=args.threads
    )

    levels = [x.strip() for x in args.bracken_levels.split(',') if x.strip()]

    failed = []
    for sample_id in samples:
        r1, r2 = get_clean_fastq(cleandir, sample_id)
        if not r1 or not os.path.exists(r1):
            log.warning('[%s] clean reads 不存在，跳过', sample_id)
            failed.append(sample_id)
            continue
        try:
            log.info('[%s] 开始 kraken2 ...', sample_id)
            _, kreport = run_kraken2(sample_id, r1, r2, db_dir, outdir, threads=args.threads)
            for lvl in levels:
                log.info('[%s] 开始 bracken %s ...', sample_id, lvl)
                run_bracken(sample_id, kreport, db_dir, outdir, read_length, lvl, threads=args.threads)
        except Exception as e:
            log.error('[%s] kraken2/bracken 失败: %s', sample_id, e)
            failed.append(sample_id)

    if failed:
        log.error('以下样本运行失败: %s', failed)
        sys.exit(1)
    log.info('kraken2 + bracken 注释完成，输出: %s', outdir)


if __name__ == '__main__':
    main()
