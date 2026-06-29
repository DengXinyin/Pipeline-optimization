#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Update version of func_diff.py

import os
import sys
import argparse
import logging
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd
from diff_method import anova, kw_wilcoxon
from get_scriptspath_update import scripts_path, Rscript_j
from r_analysis_update import (
    plot_anova_boxplots,
    plot_wilcoxon_boxplots,
    plot_stamp,
    plot_random_forest,
    plot_anosim,
    plot_adonis,
    plot_mrpp,
)

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

FUNC_INDEX = [
    '1.KEGG', '2.eggNOG', '3.CAZy', '4.GO',
    'Carbon_Cycle', 'Methane_Cycle', 'Nitrogen_Cycle', 'phosphorylation_Cycle', 'Sulfur_Cycle',
    'ARG', 'VFDB', 'BacMet2', 'mobileOG', 'QS'
]


def get_resdir(res_dir, group_num, func, test_type):
    if func in ('1.KEGG', '2.eggNOG', '3.CAZy', '4.GO'):
        return os.path.join(res_dir, group_num, '8-FunctionStatistical_analysis', func, test_type)
    elif '_Cycle' in func:
        return os.path.join(res_dir, group_num, '9-METABOLIC', func, '6.Statistical_test_analysis', test_type)
    elif func == 'ARG':
        return os.path.join(res_dir, group_num, '10-ARG', '6.Statistical_test_analysis', test_type)
    elif func == 'VFDB':
        return os.path.join(res_dir, group_num, '11-VFDB', '6.Statistical_test_analysis', test_type)
    elif func == 'mobileOG':
        return os.path.join(res_dir, group_num, '12-mobileOG', '6.Statistical_test_analysis', test_type)
    elif func == 'BacMet2':
        return os.path.join(res_dir, group_num, '13-BacMet2', '6.Statistical_test_analysis', test_type)
    elif func == 'QS':
        return os.path.join(res_dir, group_num, '14-QS', '6.Statistical_test_analysis', test_type)
    else:
        raise ValueError(f'未知功能类型: {func}')


def read_metadata(datadir):
    return pd.read_csv(
        os.path.join(datadir, 'sample-metadata.tsv'),
        sep='\t', skiprows=[1], dtype=str
    )


def do_anova(datadir, func_diffdir, res_dir, func_tmpdir):
    sam_gros = read_metadata(datadir)
    k = sam_gros.shape[1]
    for i in range(1, k):
        sam_gro = sam_gros.iloc[:, [0] + [i]]
        sam_gro = sam_gro.dropna(axis=0).reset_index(drop=True)
        group_num = 'group' + str(i)

        for func in FUNC_INDEX:
            tpm_diffdir = os.path.join(func_diffdir, group_num, 'anova', func)
            os.makedirs(tpm_diffdir, exist_ok=True)
            resdir = get_resdir(res_dir, group_num, func, '1.ANOVA')
            os.makedirs(resdir, exist_ok=True)

            table_dir = os.path.join(func_tmpdir, group_num, func)
            if not os.path.exists(table_dir):
                log.warning('目录不存在，跳过: %s', table_dir)
                continue
            files = [f for f in os.listdir(table_dir) if f.endswith('_diff.tsv')]
            if not files:
                log.warning('无 *_diff.tsv 文件: %s', table_dir)
                continue

            for file in files:
                prefix = file.replace('_diff.tsv', '')
                log.info('ANOVA: %s %s %s', group_num, func, prefix)
                func_dat = pd.read_csv(os.path.join(table_dir, file), sep='\t')
                res = anova(func_dat, sam_gro, group_num)
                if not res:
                    continue
                genus_p, genus_sign_pvalue, tukey_df = res

                genus_p.to_csv(
                    os.path.join(resdir, f'{prefix}_anova.tsv'),
                    sep='\t', index=False, encoding='utf-8'
                )
                if not genus_sign_pvalue.empty:
                    genus_sign_pvalue.to_csv(
                        os.path.join(tpm_diffdir, f'{prefix}_sign.tsv'),
                        sep='\t', index=False, encoding='utf-8-sig'
                    )
                    genus_sign_pvalue.to_csv(
                        os.path.join(resdir, f'{prefix}_sign.tsv'),
                        sep='\t', index=False, encoding='utf-8'
                    )
                if tukey_df is not None:
                    tukey_df.to_csv(
                        os.path.join(tpm_diffdir, f'{prefix}_tukey.tsv'),
                        sep='\t', index=False, encoding='utf-8'
                    )
                    tukey_df.to_csv(
                        os.path.join(resdir, f'{prefix}_tukey.tsv'),
                        sep='\t', index=False, encoding='utf-8'
                    )


def do_wilcoxon(datadir, func_diffdir, res_dir, func_tmpdir):
    sam_gros = read_metadata(datadir)
    k = sam_gros.shape[1]
    for i in range(1, k):
        sam_gro = sam_gros.iloc[:, [0] + [i]]
        sam_gro = sam_gro.dropna(axis=0).reset_index(drop=True)
        group_num = 'group' + str(i)

        for func in FUNC_INDEX:
            tpm_diffdir = os.path.join(func_diffdir, group_num, 'wilcoxon', func)
            os.makedirs(tpm_diffdir, exist_ok=True)
            resdir = get_resdir(res_dir, group_num, func, '2.wilcoxon')
            os.makedirs(resdir, exist_ok=True)

            table_dir = os.path.join(func_tmpdir, group_num, func)
            if not os.path.exists(table_dir):
                log.warning('目录不存在，跳过: %s', table_dir)
                continue
            files = [f for f in os.listdir(table_dir) if f.endswith('_diff.tsv')]
            if not files:
                log.warning('无 *_diff.tsv 文件: %s', table_dir)
                continue

            for file in files:
                prefix = file.replace('_diff.tsv', '')
                log.info('Wilcoxon: %s %s %s', group_num, func, prefix)
                func_dat = pd.read_csv(os.path.join(table_dir, file), sep='\t')
                res = kw_wilcoxon(func_dat, sam_gro, group_num)
                if not res:
                    continue
                kww_p, kww_sign_pvalue, dunn_res = res

                kww_p.to_csv(
                    os.path.join(resdir, f'{prefix}_wilcoxon.tsv'),
                    sep='\t', index=False, encoding='utf-8'
                )
                if not kww_sign_pvalue.empty:
                    kww_sign_pvalue.to_csv(
                        os.path.join(resdir, f'{prefix}_sign.tsv'),
                        sep='\t', index=False, encoding='utf-8'
                    )
                    kww_sign_pvalue.to_csv(
                        os.path.join(tpm_diffdir, f'{prefix}_sign.tsv'),
                        sep='\t', index=False, encoding='utf-8'
                    )
                if dunn_res is not None:
                    dunn_res.to_csv(
                        os.path.join(resdir, f'{prefix}_dunn.tsv'),
                        sep='\t', index=False, encoding='utf-8'
                    )
                    dunn_res.to_csv(
                        os.path.join(tpm_diffdir, f'{prefix}_dunn.tsv'),
                        sep='\t', index=False, encoding='utf-8'
                    )


def _run_func_metaseq(func_tmpdir, datadir, res_dir):
    r_script = 'func_metaseq_update.R'
    log_dir = os.path.join(res_dir, 'logs', 'func_diff')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, r_script.replace('.R', '.log'))
    cmd = [Rscript_j, os.path.join(scripts_path, r_script), func_tmpdir, datadir, res_dir]
    log.info('运行 R 脚本: %s', r_script)
    with open(log_file, 'w') as lf:
        subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, check=True)
    return r_script


def plot(func_diff, datadir, res_dir, func_tmpdir):
    log_dir = os.path.join(res_dir, 'logs', 'func_diff')
    os.makedirs(log_dir, exist_ok=True)

    max_workers = min(8, os.cpu_count() or 1)
    errors = []

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(plot_anova_boxplots, func_diff, datadir, res_dir, 'func'): 'func_anova',
            executor.submit(plot_wilcoxon_boxplots, func_diff, datadir, res_dir, 'func'): 'func_wilcoxon',
            executor.submit(plot_stamp, func_tmpdir, datadir, res_dir, 'func'): 'func_stamp',
            executor.submit(plot_random_forest, func_tmpdir, datadir, res_dir, 'func'): 'func_randomForest',
            executor.submit(plot_anosim, func_tmpdir, datadir, res_dir, 'func'): 'func_Anosim',
            executor.submit(plot_adonis, func_tmpdir, datadir, res_dir, 'func'): 'func_Adonis',
            executor.submit(plot_mrpp, func_tmpdir, datadir, res_dir, 'func'): 'func_MRPP',
            executor.submit(_run_func_metaseq, func_tmpdir, datadir, res_dir): 'func_metaseq',
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                future.result()
            except Exception as exc:
                log.error('任务 %s 运行失败: %s', name, exc)
                errors.append(name)

    if errors:
        raise RuntimeError(f'以下任务失败: {", ".join(errors)}')


def main():
    parser = argparse.ArgumentParser(description='Function differential analysis (update version)')
    parser.add_argument('-I', '--i_datadir', type=str, default='data', help='the dir of sample-metadata.tsv')
    parser.add_argument('--resdir', type=str, default='Result', help='the resdir')
    parser.add_argument('--func_tmp', type=str, default='func_base', help='the func_base tmp dir')
    parser.add_argument('--func_diff', type=str, default='func_diff', help='the func_diff tmp dir')
    args = parser.parse_args()

    datadir = os.path.abspath(args.i_datadir)
    res_dir = os.path.abspath(args.resdir)
    func_tmpdir = os.path.abspath(args.func_tmp)
    func_diff = os.path.abspath(args.func_diff)

    if not os.path.exists(datadir):
        log.error('输入路径不存在: %s', datadir)
        sys.exit(1)

    try:
        log.info('开始功能 ANOVA 分析')
        do_anova(datadir, func_diff, res_dir, func_tmpdir)
        log.info('开始功能 Wilcoxon 分析')
        do_wilcoxon(datadir, func_diff, res_dir, func_tmpdir)
        log.info('开始功能差异 R 可视化')
        plot(func_diff, datadir, res_dir, func_tmpdir)
        log.info('func_diff 完成')
    except subprocess.CalledProcessError as e:
        log.error('外部命令执行失败: %s', e)
        sys.exit(1)
    except Exception as e:
        log.error('func_diff 运行失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
