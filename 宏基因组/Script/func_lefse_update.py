#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Update version of func_lefse.py

import os
import sys
import argparse
import logging
import subprocess
from multiprocessing import Pool, cpu_count

import pandas as pd
from get_scriptspath_update import scripts_path, Rscript_j

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

FUNC_INDEX = [
    '1.KEGG', '2.eggNOG', '3.CAZy', '4.GO',
    'Carbon_Cycle', 'Methane_Cycle', 'Nitrogen_Cycle',
    'phosphorylation_Cycle', 'Sulfur_Cycle',
    'ARG', 'VFDB', 'BacMet2', 'mobileOG', 'QS'
]


def get_result_dir(res_dir, group_num, func):
    if func in ('1.KEGG', '2.eggNOG', '3.CAZy', '4.GO'):
        return os.path.join(res_dir, group_num, '8-FunctionStatistical_analysis', func, '9.Lefse')
    elif '_Cycle' in func:
        return os.path.join(res_dir, group_num, '9-METABOLIC', func, '6.Statistical_test_analysis', '9.Lefse')
    elif func == 'ARG':
        return os.path.join(res_dir, group_num, '10-ARG', '6.Statistical_test_analysis', '9.Lefse')
    elif func == 'VFDB':
        return os.path.join(res_dir, group_num, '11-VFDB', '6.Statistical_test_analysis', '9.Lefse')
    elif func == 'mobileOG':
        return os.path.join(res_dir, group_num, '12-mobileOG', '6.Statistical_test_analysis', '9.Lefse')
    elif func == 'BacMet2':
        return os.path.join(res_dir, group_num, '13-BacMet2', '6.Statistical_test_analysis', '9.Lefse')
    elif func == 'QS':
        return os.path.join(res_dir, group_num, '14-QS', '6.Statistical_test_analysis', '9.Lefse')
    else:
        raise ValueError(f'未知功能类型: {func}')


def load_metadata(datadir):
    return pd.read_csv(
        os.path.join(datadir, 'sample-metadata.tsv'),
        sep='\t', skiprows=[1], dtype=str
    )


def run_lefse(task):
    diff_dir, prefix, log_dir = task
    tsv = os.path.join(diff_dir, f'{prefix}.tsv')
    infile = os.path.join(diff_dir, f'{prefix}.in')
    resfile = os.path.join(diff_dir, f'{prefix}.res')
    log_file = os.path.join(log_dir, f'{prefix}.lefse.log')

    if os.path.exists(resfile):
        return '%s exists' % prefix

    cmd1 = ['lefse-format_input.py', tsv, infile, '-c', '1', '-o', '-1']
    cmd2 = ['run_lefse.py', infile, resfile]

    try:
        with open(log_file, 'w') as lf:
            subprocess.run(cmd1, stdout=lf, stderr=subprocess.STDOUT, check=True)
            subprocess.run(cmd2, stdout=lf, stderr=subprocess.STDOUT, check=True)
        return '%s done' % prefix
    except subprocess.CalledProcessError as e:
        log.error('LEfSe 失败 %s: %s', prefix, e)
        return '%s failed' % prefix


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


def lefse(datadir, func_diffdir, func_tmpdir, threads, min_features_retained=500):
    sam_gros = load_metadata(datadir)
    k = sam_gros.shape[1]

    lefse_log_dir = os.path.join(func_diffdir, 'logs', 'lefse')
    os.makedirs(lefse_log_dir, exist_ok=True)

    tasks = []
    for i in range(1, k):
        group_num = 'group' + str(i)
        sam_gro = sam_gros.iloc[:, [0, i]]
        sam_gro = sam_gro.dropna(axis=0).reset_index(drop=True)
        group_dic = pd.Series(sam_gro[group_num].values, index=sam_gro['sample-id']).to_dict()

        for func in FUNC_INDEX:
            table_dir = os.path.join(func_tmpdir, group_num, func)
            diff_dir = os.path.join(func_diffdir, group_num, 'lefse', func)

            if not os.path.exists(table_dir):
                continue
            os.makedirs(diff_dir, exist_ok=True)

            for file in os.listdir(table_dir):
                if not file.endswith('_diff.tsv'):
                    continue
                prefix = file.replace('_diff.tsv', '').strip()
                infile = os.path.join(table_dir, file)
                out_tsv = os.path.join(diff_dir, f'{prefix}.tsv')

                if not os.path.exists(out_tsv):
                    func_dat_raw = pd.read_csv(infile, sep='\t')
                    func_dat = filter_taxonomy(func_dat_raw, min_features_retained=min_features_retained)
                    func_dat = func_dat.rename(columns=group_dic)
                    old_name = func_dat.columns[0]
                    func_dat = func_dat.rename(columns={old_name: 'group'})
                    func_dat.to_csv(out_tsv, sep='\t', index=False, encoding='utf-8-sig')

                if (diff_dir, prefix, lefse_log_dir) not in tasks:
                    tasks.append((diff_dir, prefix, lefse_log_dir))

    log.info('启动功能 LEfSe 并行计算，任务数: %d，线程数: %d', len(tasks), threads)
    pool = Pool(threads)
    for result in pool.imap_unordered(run_lefse, tasks):
        log.info(result)
    pool.close()
    pool.join()


def get_table(datadir, res_dir, func_diffdir):
    sam_gros = load_metadata(datadir)
    k = sam_gros.shape[1]

    for i in range(1, k):
        group_num = 'group' + str(i)
        log.info('整理功能 LEfSe 结果: %s', group_num)
        for func in FUNC_INDEX:
            diff_dir = os.path.join(func_diffdir, group_num, 'lefse', func)
            if not os.path.exists(diff_dir):
                continue

            resdir = get_result_dir(res_dir, group_num, func)
            os.makedirs(resdir, exist_ok=True)

            for file in os.listdir(diff_dir):
                if not file.endswith('.res'):
                    continue
                prefix = file.replace('.res', '')
                try:
                    res = pd.read_csv(os.path.join(diff_dir, file), sep='\t', header=None)
                    res.columns = ['Taxonomy', 'Mean', 'Group', 'LDA', 'Pvalue']
                    res = res.dropna(subset=['Group'])
                    if res.empty:
                        continue

                    res.to_csv(
                        os.path.join(diff_dir, f'{prefix}_LDA.tsv'),
                        sep='\t', index=False, encoding='utf-8-sig'
                    )
                    res.to_excel(
                        os.path.join(resdir, f'{prefix}_LDA.xlsx'),
                        index=False, sheet_name='LDA_score'
                    )
                except Exception as e:
                    log.error('整理 %s %s %s 失败: %s', group_num, func, prefix, e)


def plot_lefse(func_diff, datadir, res_dir):
    log_dir = os.path.join(res_dir, 'logs', 'func_lefse')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'func_lefse.R.log')
    cmd = [Rscript_j, os.path.join(scripts_path, 'func_lefse.R'), func_diff, datadir, res_dir]
    log.info('运行 R 脚本: func_lefse.R')
    with open(log_file, 'w') as lf:
        subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, check=True)


def main():
    parser = argparse.ArgumentParser(description='Function LEfSe analysis (update version)')
    parser.add_argument('-I', '--i_datadir', type=str, default='data', help='the dir of sample-metadata.tsv')
    parser.add_argument('--resdir', type=str, default='Result', help='the result dir')
    parser.add_argument('--func_tmp', type=str, default='func_base', help='the func_base tmp dir')
    parser.add_argument('--func_diff', type=str, default='func_diff', help='the func_diff tmp dir')
    parser.add_argument('-t', '--threads', type=int, default=max(cpu_count() - 1, 1), help='threads')
    parser.add_argument('--min-features-retained', type=int, default=500, help='min features retained after filter')
    args = parser.parse_args()

    datadir = os.path.abspath(args.i_datadir)
    res_dir = os.path.abspath(args.resdir)
    func_tmpdir = os.path.abspath(args.func_tmp)
    func_diff = os.path.abspath(args.func_diff)

    if not os.path.exists(datadir):
        log.error('输入路径不存在: %s', datadir)
        sys.exit(1)

    try:
        log.info('使用 %d 线程运行功能 LEfSe', args.threads)
        lefse(datadir, func_diff, func_tmpdir, args.threads, args.min_features_retained)
        get_table(datadir, res_dir, func_diff)
        plot_lefse(func_diff, datadir, res_dir)
        log.info('func_lefse 完成')
    except subprocess.CalledProcessError as e:
        log.error('外部命令执行失败: %s', e)
        sys.exit(1)
    except Exception as e:
        log.error('func_lefse 运行失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
