#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
COG_stats_update.py

对 COG 注释结果进行基础统计，生成样本/分组 TPM 与相对丰度表，
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


def get_table(datadir, cog_dir, res_dir, func_tmpdir):
    sam_gros = pd.read_csv(os.path.join(datadir, 'sample-metadata.tsv'), sep='\t', skiprows=[1], dtype=str)
    k = sam_gros.shape[1]
    for i in range(1, k):
        sam_gro = sam_gros.iloc[:, [0] + [i]]
        sam_gro = sam_gro.dropna(axis=0).reset_index(drop=True)
        group_num = 'group' + str(i)
        group_dic = pd.Series(sam_gro[group_num].values, index=sam_gro['sample-id']).to_dict()
        samples_ls = sam_gro.loc[:, 'sample-id'].to_list()

        resdir = os.path.join(res_dir, group_num, '15-COG')
        os.makedirs(resdir, exist_ok=True)
        tmpdir = os.path.join(func_tmpdir, group_num, 'COG')
        os.makedirs(tmpdir, exist_ok=True)

        try:
            cog_tpm_all = pd.read_csv(os.path.join(cog_dir, 'COG.tpm.csv'))
        except Exception:
            log.info('COG 无注释结果，跳过')
            continue

        if cog_tpm_all.empty:
            log.info('COG 注释结果为空，跳过')
            continue

        # 保留 GeneID, taxonomy, COG 与样本列
        sample_cols = [c for c in cog_tpm_all.columns if c in samples_ls]
        gene_cog_tpm = cog_tpm_all.loc[:, ['GeneID', 'taxonomy', 'COG'] + sample_cols]
        gene_cog_tpm = gene_cog_tpm[~(gene_cog_tpm[sample_cols] == 0).all(axis=1)]
        gene_cog_tpm.to_csv(os.path.join(resdir, 'gene.COG.tpm.csv'), index=False, encoding='utf-8-sig')

        cog_tpm = gene_cog_tpm.groupby('COG')[sample_cols].sum()
        cog_tpm_gro = cog_tpm.groupby(by=group_dic, axis=1).mean()
        cog_tpm_rel = cog_tpm.div(cog_tpm.sum())
        cog_tpm_gro_rel = cog_tpm_gro.div(cog_tpm_gro.sum())

        cog_tpm.to_csv(os.path.join(tmpdir, 'COG_sam.tsv'), sep='\t', index=True, encoding='utf-8-sig')
        cog_tpm_gro.to_csv(os.path.join(tmpdir, 'COG_group.tsv'), sep='\t', index=True, encoding='utf-8-sig')
        cog_tpm_rel.to_csv(os.path.join(tmpdir, 'COG_diff.tsv'), sep='\t', index=True, encoding='utf-8-sig')

        with pd.ExcelWriter(os.path.join(resdir, 'COG.xlsx')) as writer:
            cog_tpm.to_excel(writer, sheet_name='samples.tpm', index=True)
            cog_tpm_gro.to_excel(writer, sheet_name='group.tpm', index=True)
            cog_tpm_rel.to_excel(writer, sheet_name='samples.relative', index=True)
            cog_tpm_gro_rel.to_excel(writer, sheet_name='group.relative', index=True)


def main():
    parser = argparse.ArgumentParser(description='COG 基础统计')
    parser.add_argument('-I', '--i_datadir', type=str, required=True, default='data', help='包含 sample-metadata.tsv 的目录')
    parser.add_argument('--COG', type=str, default='COG', help='COG 注释结果目录')
    parser.add_argument('--resdir', type=str, default='Result', help='结果输出目录')
    parser.add_argument('--func_tmp', type=str, default='func_base', help='func_base 临时目录')
    args = parser.parse_args()

    cog_dir = os.path.abspath(args.COG)
    datadir = os.path.abspath(args.i_datadir)
    res_dir = os.path.abspath(args.resdir)
    func_tmpdir = os.path.abspath(args.func_tmp)

    try:
        log.info('开始生成 COG 统计表')
        get_table(datadir, cog_dir, res_dir, func_tmpdir)
        log.info('COG 统计完成')
    except Exception as e:
        log.error('COG 统计失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
