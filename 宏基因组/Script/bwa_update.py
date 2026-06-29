#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
bwa_no / bowtie 比对优化版

优化点：
  1. 调用 bowtie_update.sh，调整并行度为 6 样本 * 12 线程 = 72 线程，避免超配
  2. bowtie2 直接管道到 samtools sort，不写中间 .sam 文件
  3. 移除 --memfree 50G 限制
  4. subprocess.run(check=True) 失败即停
  5. 输出目录挂载点保护：先清空内容再重建，避免直接 rmtree 挂载点失败
"""

import os
import shutil
import pandas as pd
import argparse
import subprocess
import sys
from get_scriptspath import scripts_path


def log(msg):
    print(f"[{__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def bowtie(datadir, cleandadir, host_dir, prodigal_dir, bowtie_dir, host):
    if host == 'none':
        cmd = f'bash {scripts_path}/bowtie_update.sh {datadir} {cleandadir} {prodigal_dir} {bowtie_dir} {host}'
    else:
        cmd = f'bash {scripts_path}/bowtie_update.sh {datadir} {host_dir} {prodigal_dir} {bowtie_dir} {host}'
    log(f"RUN: {cmd}")
    ret = subprocess.run(cmd, shell=True, executable='/bin/bash')
    if ret.returncode != 0:
        raise RuntimeError(f"bowtie_update.sh 执行失败，退出码 {ret.returncode}")


def tpm(bowtie_dir):
    count_ls = []
    tpm_ls = []
    files = os.listdir(bowtie_dir)
    for file in files:
        if file.endswith('_mapped_cut.txt'):
            prefix = file.split('_mapped_cut.txt')[0]
            count = pd.read_csv('%s/%s' % (bowtie_dir, file), sep='\t', index_col=0)
            count = count[count.index != '*']
            # 基因长度单位为kb
            count['RPK'] = (count['mapped_read'] * 1000) / count['length']
            count['TPM'] = (count['RPK'] * 10e6) / count['RPK'].sum()
            count_data = count.loc[:, 'mapped_read']
            count_data = count_data.rename(prefix)
            count_ls.append(count_data)
            tpm_data = count.loc[:, 'TPM']
            tpm_data = tpm_data.rename(prefix)
            tpm_ls.append(tpm_data)
    count_data_a = pd.concat(count_ls, axis=1)
    tpm_data_a = pd.concat(tpm_ls, axis=1)
    count_data_a.to_csv('%s/gene_count.csv' % bowtie_dir, index=True, encoding='utf-8-sig')
    tpm_data_a.to_csv('%s/gene_tpm.csv' % bowtie_dir, index=True, encoding='utf-8-sig')
    log(f"生成 {bowtie_dir}/gene_count.csv 和 {bowtie_dir}/gene_tpm.csv")


def main():
    parser = argparse.ArgumentParser(
        description='优化版 bowtie 比对与 TPM 计算')
    parser.add_argument('-I', '--i_datadir', type=str, required=True, help='the dir of sample.txt')
    parser.add_argument('--host_dir', type=str, default='de_host', help='the dir of dehost_data')
    parser.add_argument('--cleandir', type=str, default='cleandata', help='the dir of clean_data')
    parser.add_argument('--bowtie', type=str, default='bowtie', help='the res of bowtie')
    parser.add_argument('--prodigal', type=str, default='prodigal', help='the res of prodigal')
    parser.add_argument('--host', type=str, required=True, nargs='*', help='the host of metagenome')
    args = parser.parse_args()

    datadir = os.path.abspath(args.i_datadir)
    cleandadir = os.path.abspath(args.cleandir)
    host_dir = os.path.abspath(args.host_dir)
    bowtie_dir = os.path.abspath(args.bowtie)
    prodigal_dir = os.path.abspath(args.prodigal)
    host = args.host[0]

    # 兼容挂载点：先清空内容，再确保目录存在
    if os.path.exists(bowtie_dir):
        shutil.rmtree(bowtie_dir, ignore_errors=True)
    os.makedirs(bowtie_dir, exist_ok=True)

    bowtie(datadir, cleandadir, host_dir, prodigal_dir, bowtie_dir, host)
    tpm(bowtie_dir)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        log(f"ERROR: {e}")
        sys.exit(1)
