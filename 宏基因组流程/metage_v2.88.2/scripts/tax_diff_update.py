#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Update version of tax_diff.py

import os
import sys
import argparse
import logging
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd
from diff_method import anova, kw_wilcoxon
from get_scriptspath_update import scripts_path, Rscript_j
from subprocess_log_utils import run_with_failure_log
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

SPECIES = ['phylum', 'class', 'order', 'family', 'genus', 'species']
CLASSES = ['All', 'Archaea', 'bacteria', 'Fungi', 'Virus']


def read_metadata(datadir):
    return pd.read_csv(
        os.path.join(datadir, 'sample-metadata.tsv'),
        sep='\t', skiprows=[1], dtype=str
    )


def do_anova(datadir, res_dir, tpmdir, pre_resdir):
    sam_gros = read_metadata(datadir)
    k = sam_gros.shape[1]
    for i in range(1, k):
        sam_gro = sam_gros.iloc[:, [0] + [i]]
        sam_gro = sam_gro.dropna(axis=0).reset_index(drop=True)
        group_num = 'group' + str(i)

        for clas in CLASSES:
            tax_dir = os.path.join(pre_resdir, group_num, '5-TaxAnnotation', '1.Tables', 'Samples', clas)
            if not os.path.exists(tax_dir):
                log.warning('[%s %s] 目录不存在，跳过: %s', group_num, clas, tax_dir)
                continue
            for specie in SPECIES:
                log.info('ANOVA: %s %s %s', group_num, clas, specie)
                tpm_taxdir = os.path.join(tpmdir, group_num, 'anova', clas)
                os.makedirs(tpm_taxdir, exist_ok=True)
                resdir = os.path.join(res_dir, group_num, '6-TaxStatistical_analysis', clas, specie, '1.ANOVA')
                os.makedirs(resdir, exist_ok=True)

                tax_file = os.path.join(tax_dir, f'{specie}.xlsx')
                if not os.path.exists(tax_file):
                    log.warning('文件不存在，跳过: %s', tax_file)
                    continue
                tax_dat = pd.read_excel(tax_file, sheet_name='relative')
                if tax_dat.empty or len(tax_dat.columns) <= 1:
                    log.warning('ANOVA 数据为空，跳过: %s %s %s', group_num, clas, specie)
                    continue
                try:
                    res = anova(tax_dat, sam_gro, group_num)
                except Exception as e:
                    log.warning('ANOVA 分析失败，跳过: %s %s %s, error: %s', group_num, clas, specie, e)
                    continue
                if not res:
                    continue
                genus_p, genus_sign_pvalue, tukey_df = res

                genus_p.to_csv(
                    os.path.join(resdir, f'{specie}_anova.tsv'),
                    sep='\t', index=False, encoding='utf-8'
                )
                if not genus_sign_pvalue.empty:
                    genus_sign_pvalue.to_csv(
                        os.path.join(tpm_taxdir, f'{specie}_sign.tsv'),
                        sep='\t', index=False, encoding='utf-8'
                    )
                    genus_sign_pvalue.to_csv(
                        os.path.join(resdir, f'{specie}_sign.tsv'),
                        sep='\t', index=False, encoding='utf-8'
                    )
                if tukey_df is not None:
                    tukey_df.to_csv(
                        os.path.join(tpm_taxdir, f'{specie}_tukey.tsv'),
                        sep='\t', index=False, encoding='utf-8'
                    )
                    tukey_df.to_csv(
                        os.path.join(resdir, f'{specie}_tukey.tsv'),
                        sep='\t', index=False, encoding='utf-8'
                    )


def do_wilcoxon(datadir, tpmdir, res_dir, pre_resdir):
    sam_gros = read_metadata(datadir)
    k = sam_gros.shape[1]
    for i in range(1, k):
        sam_gro = sam_gros.iloc[:, [0] + [i]]
        sam_gro = sam_gro.dropna(axis=0).reset_index(drop=True)
        group_num = 'group' + str(i)

        for clas in CLASSES:
            tax_dir = os.path.join(pre_resdir, group_num, '5-TaxAnnotation', '1.Tables', 'Samples', clas)
            if not os.path.exists(tax_dir):
                log.warning('[%s %s] 目录不存在，跳过: %s', group_num, clas, tax_dir)
                continue
            for specie in SPECIES:
                log.info('Wilcoxon: %s %s %s', group_num, clas, specie)
                tpm_taxdir = os.path.join(tpmdir, group_num, 'wilcoxon', clas)
                os.makedirs(tpm_taxdir, exist_ok=True)
                resdir = os.path.join(res_dir, group_num, '6-TaxStatistical_analysis', clas, specie, '2.wilcoxon')
                os.makedirs(resdir, exist_ok=True)

                tax_file = os.path.join(tax_dir, f'{specie}.xlsx')
                if not os.path.exists(tax_file):
                    log.warning('文件不存在，跳过: %s', tax_file)
                    continue
                tax_dat = pd.read_excel(tax_file, sheet_name='relative')
                if tax_dat.empty or len(tax_dat.columns) <= 1:
                    log.warning('Wilcoxon 数据为空，跳过: %s %s %s', group_num, clas, specie)
                    continue
                try:
                    res = kw_wilcoxon(tax_dat, sam_gro, group_num)
                except Exception as e:
                    log.warning('Wilcoxon 分析失败，跳过: %s %s %s, error: %s', group_num, clas, specie, e)
                    continue
                if not res:
                    continue
                kww_p, kww_sign_pvalue, dunn_res = res

                kww_p.to_csv(
                    os.path.join(resdir, f'{specie}_wilcoxon.tsv'),
                    sep='\t', index=False, encoding='utf-8'
                )
                if not kww_sign_pvalue.empty:
                    kww_sign_pvalue.to_csv(
                        os.path.join(resdir, f'{specie}_sign.tsv'),
                        sep='\t', index=False, encoding='utf-8'
                    )
                    kww_sign_pvalue.to_csv(
                        os.path.join(tpm_taxdir, f'{specie}_sign.tsv'),
                        sep='\t', index=False, encoding='utf-8'
                    )
                if dunn_res is not None:
                    dunn_res.to_csv(
                        os.path.join(resdir, f'{specie}_dunn.tsv'),
                        sep='\t', index=False, encoding='utf-8'
                    )
                    dunn_res.to_csv(
                        os.path.join(tpm_taxdir, f'{specie}_dunn.tsv'),
                        sep='\t', index=False, encoding='utf-8'
                    )


def _run_tax_metaseq(tpmdir, datadir, res_dir, pre_resdir):
    r_script = 'tax_metaseq_update.R'
    log_dir = os.path.join(tpmdir, 'logs', 'R')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, r_script.replace('.R', '.log'))
    # 使用 update R 脚本自身所在目录，避免 METAGE_SCRIPTS_PATH 被覆盖后找不到 _update.R
    update_r_dir = os.path.dirname(os.path.abspath(__file__))
    cmd = [Rscript_j, os.path.join(update_r_dir, r_script), tpmdir, datadir, res_dir, pre_resdir]
    log.info('运行 R 脚本: %s', r_script)
    run_with_failure_log(cmd, log_file, stop_dir=tpmdir)
    return r_script


def plot(tpmdir, datadir, res_dir, pre_resdir):
    log_dir = os.path.join(tpmdir, 'logs', 'R')
    os.makedirs(log_dir, exist_ok=True)

    max_workers = min(8, os.cpu_count() or 1)
    errors = []

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(plot_anova_boxplots, tpmdir, datadir, res_dir, 'tax'): 'tax_anova',
            executor.submit(plot_wilcoxon_boxplots, tpmdir, datadir, res_dir, 'tax'): 'tax_wilcoxon',
            executor.submit(plot_stamp, pre_resdir, datadir, res_dir, 'tax'): 'tax_stamp',
            executor.submit(plot_random_forest, pre_resdir, datadir, res_dir, 'tax'): 'tax_randomForest',
            executor.submit(plot_anosim, pre_resdir, datadir, res_dir, 'tax'): 'tax_Anosim',
            executor.submit(plot_adonis, pre_resdir, datadir, res_dir, 'tax'): 'tax_Adonis',
            executor.submit(plot_mrpp, pre_resdir, datadir, res_dir, 'tax'): 'tax_MRPP',
            executor.submit(_run_tax_metaseq, tpmdir, datadir, res_dir, pre_resdir): 'tax_metaseq',
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
    parser = argparse.ArgumentParser(description='Taxonomy differential analysis (update version)')
    parser.add_argument('-I', '--i_datadir', type=str, default='data', help='the dir of sample-metadata.tsv')
    parser.add_argument('--resdir', type=str, default='Result', help='the resdir')
    parser.add_argument('--tpmdir', type=str, default='tax_diff', help='the tax_diff tmp dir')
    parser.add_argument('--pre_resdir', type=str, default='Result', help='the pre result dir')
    args = parser.parse_args()

    datadir = os.path.abspath(args.i_datadir)
    res_dir = os.path.abspath(args.resdir)
    tpmdir = os.path.abspath(args.tpmdir)
    pre_resdir = os.path.abspath(args.pre_resdir)

    if not os.path.exists(datadir):
        log.error('输入路径不存在: %s', datadir)
        sys.exit(1)

    try:
        log.info('开始 ANOVA 分析')
        do_anova(datadir, res_dir, tpmdir, pre_resdir)
        log.info('开始 Wilcoxon 分析')
        do_wilcoxon(datadir, tpmdir, res_dir, pre_resdir)
        log.info('开始 R 可视化')
        plot(tpmdir, datadir, res_dir, pre_resdir)
        log.info('tax_diff 完成')
    except subprocess.CalledProcessError as e:
        log.error('外部命令执行失败: %s', e)
        sys.exit(1)
    except Exception as e:
        log.error('tax_diff 运行失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
