#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
COG 差异分析（standalone 版）

输入：
    -I/--i_datadir      包含 sample-metadata.tsv 的目录
    --cog_stats         cog_stats_update.py 输出目录
    --outdir            输出目录

输出：
    COG_diff/COG_anova.tsv
    COG_diff/COG_anova_sign.tsv
    COG_diff/COG_anova_tukey.tsv
    COG_diff/COG_wilcoxon.tsv
    COG_diff/COG_wilcoxon_sign.tsv
    COG_diff/COG_wilcoxon_dunn.tsv
    以及 Category/Function group 级别的差异分析结果
"""

import os
import sys
import argparse
import logging

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from diff_method import anova, kw_wilcoxon

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)


def read_metadata(datadir):
    return pd.read_csv(
        os.path.join(datadir, 'sample-metadata.tsv'),
        sep='\t', skiprows=[1], dtype=str
    )


def run_anova(df, sam_gro, group_col, outdir, prefix):
    """对单个丰度表运行 ANOVA + Tukey。"""
    res = anova(df, sam_gro, group_col)
    if not res:
        log.warning('%s ANOVA 无显著结果或样本不足', prefix)
        return
    genus_p, genus_sign_pvalue, tukey_df = res

    genus_p.to_csv(os.path.join(outdir, f'{prefix}_anova.tsv'),
                   sep='\t', index=False, encoding='utf-8-sig')
    if not genus_sign_pvalue.empty:
        genus_sign_pvalue.to_csv(os.path.join(outdir, f'{prefix}_anova_sign.tsv'),
                                 sep='\t', index=False, encoding='utf-8-sig')
    if tukey_df is not None:
        tukey_df.to_csv(os.path.join(outdir, f'{prefix}_anova_tukey.tsv'),
                        sep='\t', index=False, encoding='utf-8-sig')


def run_wilcoxon(df, sam_gro, group_col, outdir, prefix):
    """对单个丰度表运行 Kruskal-Wallis + Wilcoxon + Dunn。"""
    res = kw_wilcoxon(df, sam_gro, group_col)
    if not res:
        log.warning('%s Wilcoxon 无显著结果或样本不足', prefix)
        return
    kww_p, kww_sign_pvalue, dunn_res = res

    kww_p.to_csv(os.path.join(outdir, f'{prefix}_wilcoxon.tsv'),
                 sep='\t', index=False, encoding='utf-8-sig')
    if not kww_sign_pvalue.empty:
        kww_sign_pvalue.to_csv(os.path.join(outdir, f'{prefix}_wilcoxon_sign.tsv'),
                               sep='\t', index=False, encoding='utf-8-sig')
    if dunn_res is not None:
        dunn_res.to_csv(os.path.join(outdir, f'{prefix}_wilcoxon_dunn.tsv'),
                        sep='\t', index=False, encoding='utf-8-sig')


def analyze_one_level(xlsx_path, sheet, sam_gro, group_col, outdir, prefix):
    """读取某一级别的 relative 表并做差异分析。"""
    df = pd.read_excel(xlsx_path, sheet_name=sheet)
    if df.empty:
        log.warning('%s 为空，跳过', prefix)
        return
    # 第一列为 feature 名称
    id_col = df.columns[0]
    df[id_col] = df[id_col].astype(str)

    # 只保留 metadata 中存在的样本
    sample_cols = [c for c in df.columns if c in sam_gro['sample-id'].values]
    df = df[[id_col] + sample_cols]

    run_anova(df, sam_gro, group_col, outdir, prefix)
    run_wilcoxon(df, sam_gro, group_col, outdir, prefix)


def main():
    parser = argparse.ArgumentParser(description='COG differential analysis')
    parser.add_argument('-I', '--i_datadir', required=True, help='Directory with sample-metadata.tsv')
    parser.add_argument('--cog_stats', required=True, help='COG stats directory')
    parser.add_argument('--outdir', default='COG_diff', help='Output directory')
    args = parser.parse_args()

    datadir = os.path.abspath(args.i_datadir)
    cog_stats_dir = os.path.abspath(args.cog_stats)
    outdir = os.path.abspath(args.outdir)
    os.makedirs(outdir, exist_ok=True)

    metadata = read_metadata(datadir)
    k = metadata.shape[1]

    for i in range(1, k):
        group_col = f'group{i}'
        sam_gro = metadata[['sample-id', group_col]].dropna()
        if sam_gro[group_col].nunique() < 2:
            log.warning('%s 分组数 < 2，跳过', group_col)
            continue

        log.info('开始 %s 差异分析', group_col)

        analyze_one_level(
            os.path.join(cog_stats_dir, 'COG.xlsx'),
            'samples.relative', sam_gro, group_col, outdir, f'{group_col}_COG'
        )
        analyze_one_level(
            os.path.join(cog_stats_dir, 'COG.Category.xlsx'),
            'samples.relative', sam_gro, group_col, outdir, f'{group_col}_COG_Category'
        )
        analyze_one_level(
            os.path.join(cog_stats_dir, 'COG.Function.xlsx'),
            'samples.relative', sam_gro, group_col, outdir, f'{group_col}_COG_Function'
        )

    log.info('COG 差异分析完成，输出目录: %s', outdir)


if __name__ == '__main__':
    main()
