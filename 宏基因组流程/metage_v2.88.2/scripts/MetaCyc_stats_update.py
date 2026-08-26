#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MetaCyc_stats_update.py

对 MetaCyc 注释结果进行基础统计，生成样本/分组 TPM 与相对丰度表，
并将差异分析所需的 group/sample 文件写入 func_tmpdir。
"""

import os
import sys
import argparse
import logging
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)


def get_table(datadir, metacyc_dir, res_dir, func_tmpdir):
    sam_gros = pd.read_csv(os.path.join(datadir, 'sample-metadata.tsv'), sep='\t', skiprows=[1], dtype=str)
    k = sam_gros.shape[1]
    for i in range(1, k):
        sam_gro = sam_gros.iloc[:, [0] + [i]]
        sam_gro = sam_gro.dropna(axis=0).reset_index(drop=True)
        group_num = 'group' + str(i)
        group_dic = pd.Series(sam_gro[group_num].values, index=sam_gro['sample-id']).to_dict()
        samples_ls = sam_gro.loc[:, 'sample-id'].to_list()

        resdir = os.path.join(res_dir, group_num, '16-MetaCyc')
        os.makedirs(resdir, exist_ok=True)
        tmpdir = os.path.join(func_tmpdir, group_num, 'MetaCyc')
        os.makedirs(tmpdir, exist_ok=True)

        try:
            metacyc_tpm_all = pd.read_csv(os.path.join(metacyc_dir, 'MetaCyc.tpm.csv'))
        except Exception:
            log.info('MetaCyc 无注释结果，跳过')
            continue

        if metacyc_tpm_all.empty:
            log.info('MetaCyc 注释结果为空，跳过')
            continue

        sample_cols = [c for c in metacyc_tpm_all.columns if c in samples_ls]
        gene_metacyc_tpm = metacyc_tpm_all.loc[:, ['GeneID', 'taxonomy', 'MetaCyc'] + sample_cols]
        gene_metacyc_tpm = gene_metacyc_tpm[~(gene_metacyc_tpm[sample_cols] == 0).all(axis=1)]
        gene_metacyc_tpm.to_csv(os.path.join(resdir, 'gene.MetaCyc.tpm.csv'), index=False, encoding='utf-8-sig')

        metacyc_tpm = gene_metacyc_tpm.groupby('MetaCyc')[sample_cols].sum()
        metacyc_tpm_gro = metacyc_tpm.groupby(by=group_dic, axis=1).mean()
        metacyc_tpm_rel = metacyc_tpm.div(metacyc_tpm.sum())
        metacyc_tpm_gro_rel = metacyc_tpm_gro.div(metacyc_tpm_gro.sum())

        metacyc_tpm.to_csv(os.path.join(tmpdir, 'MetaCyc_sam.tsv'), sep='\t', index=True, encoding='utf-8-sig')
        metacyc_tpm_gro.to_csv(os.path.join(tmpdir, 'MetaCyc_group.tsv'), sep='\t', index=True, encoding='utf-8-sig')
        metacyc_tpm_rel.to_csv(os.path.join(tmpdir, 'MetaCyc_diff.tsv'), sep='\t', index=True, encoding='utf-8-sig')

        with pd.ExcelWriter(os.path.join(resdir, 'MetaCyc.xlsx')) as writer:
            metacyc_tpm.to_excel(writer, sheet_name='samples.tpm', index=True)
            metacyc_tpm_gro.to_excel(writer, sheet_name='group.tpm', index=True)
            metacyc_tpm_rel.to_excel(writer, sheet_name='samples.relative', index=True)
            metacyc_tpm_gro_rel.to_excel(writer, sheet_name='group.relative', index=True)


def main():
    parser = argparse.ArgumentParser(description='MetaCyc 基础统计')
    parser.add_argument('-I', '--i_datadir', type=str, required=True, default='data', help='包含 sample-metadata.tsv 的目录')
    parser.add_argument('--MetaCyc', type=str, default='MetaCyc', help='MetaCyc 注释结果目录')
    parser.add_argument('--resdir', type=str, default='Result', help='结果输出目录')
    parser.add_argument('--func_tmp', type=str, default='func_base', help='func_base 临时目录')
    args = parser.parse_args()

    metacyc_dir = os.path.abspath(args.MetaCyc)
    datadir = os.path.abspath(args.i_datadir)
    res_dir = os.path.abspath(args.resdir)
    func_tmpdir = os.path.abspath(args.func_tmp)

    try:
        log.info('开始生成 MetaCyc 统计表')
        get_table(datadir, metacyc_dir, res_dir, func_tmpdir)
        log.info('MetaCyc 统计完成')
    except Exception as e:
        log.error('MetaCyc 统计失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
