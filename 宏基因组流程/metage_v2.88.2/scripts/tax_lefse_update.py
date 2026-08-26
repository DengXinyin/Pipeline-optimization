#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Update version of tax_lefse.py
# Python 2/3 compatible (lefse environment uses Python 2.7)

import os
import sys
import argparse
import logging
import subprocess
from multiprocessing import Pool, cpu_count

import pandas as pd
from get_scriptspath_update import scripts_path, Rscript_j
from subprocess_log_utils import run_commands_with_failure_log, run_with_failure_log

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

CLASSES = ['All', 'Archaea', 'bacteria', 'Fungi', 'Virus']
SPECIES = ['phylum', 'class', 'order', 'family', 'genus', 'species']


def _makedirs(path):
    """兼容 Python 2/3 的目录创建。"""
    if not os.path.exists(path):
        os.makedirs(path)


def load_metadata(datadir):
    return pd.read_csv(
        os.path.join(datadir, 'sample-metadata.tsv'),
        sep='\t', skiprows=[1], dtype=str
    )


def run_lefse(task):
    tpm_dir, specie, log_file = task
    tsv = os.path.join(tpm_dir, '{}.tsv'.format(specie))
    infile = os.path.join(tpm_dir, '{}.in'.format(specie))
    resfile = os.path.join(tpm_dir, '{}.res'.format(specie))

    if os.path.exists(resfile):
        return '{} exists'.format(specie)

    # 检查输入 TSV 是否有足够数据进行 LEfSe 分析
    try:
        tsv_data = pd.read_csv(tsv, sep='\t')
        if tsv_data.shape[0] < 2 or tsv_data.shape[1] < 3:
            log.warning('TSV 数据不足，跳过 LEfSe: %s (rows=%d, cols=%d)', specie, tsv_data.shape[0], tsv_data.shape[1])
            return '{} skipped (insufficient data)'.format(specie)
    except Exception as e:
        log.warning('无法读取 TSV，跳过 LEfSe %s: %s', specie, e)
        return '{} skipped (read error)'.format(specie)

    cmd1 = ['lefse-format_input.py', tsv, infile, '-c', '1', '-o', '1000000']
    cmd2 = ['run_lefse.py', infile, resfile]

    try:
        run_commands_with_failure_log(
            [cmd1, cmd2],
            log_file,
            # All workers share this directory.  Keep it in place so one
            # successful worker cannot remove it while another starts.
            stop_dir=os.path.dirname(log_file),
        )
        return '{} done'.format(specie)
    except subprocess.CalledProcessError as e:
        log.error('LEfSe 失败 %s: %s', specie, e)
        return '{} failed'.format(specie)


def filter_taxonomy(
    tax_dat,
    abundance_cutoff=0.0001,
    prevalence_ratio=0.10,
    total_count_cutoff=1,
    min_features_retained=500
):
    id_col = tax_dat.columns[0]
    abund_dat = tax_dat.iloc[:, 1:].copy()
    abund_dat = abund_dat.apply(pd.to_numeric, errors='coerce').fillna(0)

    raw_n = abund_dat.shape[0]
    rel_abund = abund_dat.div(abund_dat.sum(axis=0), axis=1)
    keep1 = rel_abund.mean(axis=1) >= abundance_cutoff
    min_samples = max(1, int(abund_dat.shape[1] * prevalence_ratio))
    keep2 = (abund_dat > 0).sum(axis=1) >= min_samples
    keep3 = abund_dat.sum(axis=1) >= total_count_cutoff
    keep = keep1 & keep2 & keep3

    tax_filtered = tax_dat.loc[keep].copy()
    filtered_n = tax_filtered.shape[0]
    removed_n = raw_n - filtered_n
    log.info('过滤 %s: raw=%d retained=%d removed=%d', id_col, raw_n, filtered_n, removed_n)

    if filtered_n < min_features_retained:
        log.warning('保留特征数 %d < %d，回退到未过滤表', filtered_n, min_features_retained)
        return tax_dat
    return tax_filtered


def lefse(datadir, tpmdir, pre_resdir, threads, min_features_retained=500):
    sam_gros = load_metadata(datadir)
    k = sam_gros.shape[1]
    lefse_log_dir = os.path.join(tpmdir, 'logs', 'lefse')
    _makedirs(lefse_log_dir)

    tasks = []
    for i in range(1, k):
        group_num = 'group' + str(i)
        sam_gro = sam_gros.iloc[:, [0, i]]
        sam_gro = sam_gro.dropna(axis=0).reset_index(drop=True)
        group_dic = pd.Series(sam_gro[group_num].values, index=sam_gro['sample-id']).to_dict()

        for clas in CLASSES:
            tax_dir = os.path.join(
                pre_resdir, group_num, '5-TaxAnnotation', '1.Tables', 'Samples', clas
            )
            tpm_dir = os.path.join(tpmdir, group_num, 'lefse', clas)
            _makedirs(tpm_dir)

            for specie in SPECIES:
                infile = os.path.join(tax_dir, '{}.xlsx'.format(specie))
                if not os.path.exists(infile):
                    continue

                out_tsv = os.path.join(tpm_dir, '{}.tsv'.format(specie))
                if not os.path.exists(out_tsv):
                    tax_dat_raw = pd.read_excel(infile, sheet_name='tpm')
                    tax_dat = filter_taxonomy(tax_dat_raw, min_features_retained=min_features_retained)
                    tax_dat = tax_dat.rename(columns=group_dic)
                    tax_dat = tax_dat.rename(columns={specie: 'group'})
                    tax_dat.to_csv(out_tsv, sep='\t', index=False, encoding='utf-8-sig')

                # A rank name alone is not unique: the same rank is processed
                # concurrently for every group and taxonomy class.  Sharing
                # e.g. ``order.lefse.log`` lets one successful worker delete
                # the file/directory while another worker is opening it.  A
                # skipped task makes that race especially visible because it
                # never creates a log of its own.  Give each actual analysis
                # a unique failure-log path; skipped analyses simply return
                # without touching that path.
                log_file = os.path.join(
                    lefse_log_dir,
                    '{}.{}.{}.lefse.log'.format(group_num, clas, specie)
                )
                tasks.append((tpm_dir, specie, log_file))

    log.info('启动 LEfSe 并行计算，任务数: %d，线程数: %d', len(tasks), threads)
    pool = Pool(threads)
    for result in pool.imap_unordered(run_lefse, tasks):
        log.info(result)
    pool.close()
    pool.join()


def get_table(datadir, tpmdir, res_dir):
    sam_gros = load_metadata(datadir)
    k = sam_gros.shape[1]

    for i in range(1, k):
        group_num = 'group' + str(i)
        log.info('整理 LEfSe 结果: %s', group_num)
        for clas in CLASSES:
            tpm_dir = os.path.join(tpmdir, group_num, 'lefse', clas)
            if not os.path.exists(tpm_dir):
                continue
            for specie in SPECIES:
                infile = os.path.join(tpm_dir, '{}.res'.format(specie))
                if not os.path.exists(infile):
                    continue

                resdir = os.path.join(
                    res_dir, group_num, '6-TaxStatistical_analysis', clas, specie, '9.Lefse'
                )
                _makedirs(resdir)

                try:
                    res = pd.read_csv(infile, sep='\t', header=None)
                    res.columns = ['Taxonomy', 'Mean', 'Group', 'LDA', 'Pvalue']
                    res = res.dropna(subset=['Group'])
                    if res.empty:
                        continue

                    res.to_csv(
                        os.path.join(tpm_dir, '{}_LDA.tsv'.format(specie)),
                        sep='\t', index=False, encoding='utf-8-sig'
                    )
                    res.to_excel(
                        os.path.join(resdir, 'LDA.xlsx'),
                        index=False, sheet_name='LDA_score'
                    )
                except Exception as e:
                    log.error('整理 %s %s %s 失败: %s', group_num, clas, specie, e)


def plot_lefse(tpmdir, datadir, res_dir):
    log_dir = os.path.join(tpmdir, 'logs', 'R')
    _makedirs(log_dir)
    log_file = os.path.join(log_dir, 'tax_LDAscore.log')
    cmd = [Rscript_j, os.path.join(scripts_path, 'tax_LDAscore_update.R'), tpmdir, datadir, res_dir]
    log.info('运行 R 脚本: tax_LDAscore_update.R')
    run_with_failure_log(cmd, log_file, stop_dir=tpmdir)


def main():
    parser = argparse.ArgumentParser(description='Taxonomy LEfSe analysis (update version)')
    parser.add_argument('-I', '--i_datadir', type=str, default='data', help='the dir of sample-metadata.tsv')
    parser.add_argument('--res_dir', type=str, default='Result', help='the result dir')
    parser.add_argument('--tpmdir', type=str, default='tax_diff', help='the tmp dir')
    parser.add_argument('--pre_resdir', type=str, default='Result', help='the pre result dir')
    parser.add_argument('-t', '--threads', type=int, default=max(cpu_count() - 1, 1), help='threads')
    parser.add_argument('--min-features-retained', type=int, default=500, help='min features retained after filter')
    args = parser.parse_args()

    datadir = os.path.abspath(args.i_datadir)
    res_dir = os.path.abspath(args.res_dir)
    tpmdir = os.path.abspath(args.tpmdir)
    pre_resdir = os.path.abspath(args.pre_resdir)

    if not os.path.exists(datadir):
        log.error('输入路径不存在: %s', datadir)
        sys.exit(1)

    try:
        log.info('使用 %d 线程运行 LEfSe', args.threads)
        lefse(datadir, tpmdir, pre_resdir, args.threads, args.min_features_retained)
        get_table(datadir, tpmdir, res_dir)
        plot_lefse(tpmdir, datadir, res_dir)
        log.info('tax_lefse 完成')
    except subprocess.CalledProcessError as e:
        log.error('外部命令执行失败: %s', e)
        sys.exit(1)
    except Exception as e:
        log.error('tax_lefse 运行失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
