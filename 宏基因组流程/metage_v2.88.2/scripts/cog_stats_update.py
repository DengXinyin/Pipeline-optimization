#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
COG 丰度统计（standalone 版）

输入：
    --cog_anno      cog_anno_update.py 输出目录，需包含 cog.gene2cog.tsv
    --bowtie        包含 gene_tpm.csv 的目录
    --i_datadir     包含 sample-metadata.tsv 的目录（可选，用于分组均值）
    --outdir        输出目录

输出：
    COG/COG.tpm.csv               基因 × COG × 样本 TPM
    COG/COG.xlsx                  COG 级别样本/分组 TPM、relative
    COG/COG.Category.tpm.xlsx     COG Category 级别汇总
    COG/COG.Function.tpm.xlsx     COG Function group 级别汇总

如果提供 --func_tmp，还会生成 func_diff 所需的 _diff.tsv / _sam.tsv / _group.tsv。
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


def read_metadata(datadir):
    """读取 QIIME2 格式 sample-metadata.tsv（跳过第二行类型注释）。"""
    path = os.path.join(datadir, 'sample-metadata.tsv')
    if not os.path.exists(path):
        return None
    return pd.read_csv(path, sep='\t', skiprows=[1], dtype=str)


def build_group_dict(metadata, group_col='group1'):
    """返回 sample -> group 的字典。"""
    if metadata is None or group_col not in metadata.columns:
        return None
    return pd.Series(metadata[group_col].values, index=metadata['sample-id']).to_dict()


def main():
    parser = argparse.ArgumentParser(description='COG abundance statistics')
    parser.add_argument('--cog_anno', required=True, help='COG annotation directory with cog.gene2cog.tsv')
    parser.add_argument('--bowtie', required=True, help='Directory containing gene_tpm.csv')
    parser.add_argument('-I', '--i_datadir', default=None, help='Directory containing sample-metadata.tsv')
    parser.add_argument('--outdir', default='COG_stats', help='Output directory')
    parser.add_argument('--func_tmp', default=None, help='Optional func_base tmp dir to write _diff.tsv files')
    args = parser.parse_args()

    cog_anno_dir = os.path.abspath(args.cog_anno)
    bowtie_dir = os.path.abspath(args.bowtie)
    outdir = os.path.abspath(args.outdir)
    os.makedirs(outdir, exist_ok=True)

    gene2cog_path = os.path.join(cog_anno_dir, 'cog.gene2cog.tsv')
    gene_tpm_path = os.path.join(bowtie_dir, 'gene_tpm.csv')
    for p in [gene2cog_path, gene_tpm_path]:
        if not os.path.exists(p):
            log.error('缺少输入文件: %s', p)
            sys.exit(1)

    metadata = read_metadata(args.i_datadir) if args.i_datadir else None
    group_dic = build_group_dict(metadata) if metadata is not None else None

    log.info('读取 COG 注释表: %s', gene2cog_path)
    gene2cog = pd.read_csv(gene2cog_path, sep='\t', dtype=str)
    # 将 evalue/bitscore 转为数值
    gene2cog['bitscore'] = pd.to_numeric(gene2cog['bitscore'], errors='coerce')

    log.info('读取基因丰度表: %s', gene_tpm_path)
    gene_tpm = pd.read_csv(gene_tpm_path)

    samples = [c for c in gene_tpm.columns if c != 'GeneID']

    # 合并注释与丰度
    cog_tpm = pd.merge(gene2cog, gene_tpm, on='GeneID', how='inner')
    cog_tpm = cog_tpm[~(cog_tpm[samples] == 0).all(axis=1)]
    # 过滤未注释基因
    cog_tpm_annotated = cog_tpm[cog_tpm['COG'].notna() & (cog_tpm['COG'] != '')].copy()
    cog_tpm_annotated.to_csv(os.path.join(outdir, 'COG.tpm.csv'), index=False, encoding='utf-8-sig')
    log.info('写入 COG.tpm.csv: %d rows', len(cog_tpm_annotated))

    def aggregate_and_save(df, index_cols, out_xlsx, out_prefix=None, func_tmp_subdir=None):
        """按 index_cols 汇总，生成样本/分组 TPM 和 relative，写入 xlsx。"""
        keep_cols = [c for c in index_cols if c in df.columns]
        agg = df[keep_cols + samples].groupby(keep_cols).sum(numeric_only=True)

        if group_dic is not None:
            gro = agg[samples].groupby(by=group_dic, axis=1).mean()
        else:
            gro = pd.DataFrame()

        agg_rel = agg[samples].div(agg[samples].sum())
        if not gro.empty:
            gro_rel = gro.div(gro.sum())
        else:
            gro_rel = pd.DataFrame()

        # 以 index 作为行名写入 Excel，R 可用 rowNames = TRUE 读取
        with pd.ExcelWriter(out_xlsx, engine='openpyxl') as writer:
            agg.to_excel(writer, sheet_name='samples.tpm', index=True)
            if not gro.empty:
                gro.to_excel(writer, sheet_name='group.tpm', index=True)
            agg_rel.to_excel(writer, sheet_name='samples.relative', index=True)
            if not gro_rel.empty:
                gro_rel.to_excel(writer, sheet_name='group.relative', index=True)

        log.info('写入 %s', out_xlsx)

        if func_tmp_subdir and out_prefix:
            os.makedirs(func_tmp_subdir, exist_ok=True)
            diff_out = os.path.join(func_tmp_subdir, f'{out_prefix}_diff.tsv')
            agg_rel.to_csv(diff_out, sep='\t', index=False, encoding='utf-8-sig')
            sam_out = os.path.join(func_tmp_subdir, f'{out_prefix}_sam.tsv')
            agg_rel.to_csv(sam_out, sep='\t', index=False, encoding='utf-8-sig')
            if not gro_rel.empty:
                group_out = os.path.join(func_tmp_subdir, f'{out_prefix}_group.tsv')
                gro_rel.to_csv(group_out, sep='\t', index=False, encoding='utf-8-sig')

    func_tmp_cog = os.path.join(args.func_tmp, '5.COG') if args.func_tmp else None

    # 1) COG 级别：按 GeneID+COG 去重后汇总（避免多 category 拆行导致重复计数）
    cog_level = cog_tpm_annotated[['GeneID', 'COG', 'description'] + samples].copy()
    cog_level = cog_level.drop_duplicates(subset=['GeneID', 'COG'])
    cog_level = cog_level.groupby(['COG', 'description'])[samples].sum().reset_index()
    aggregate_and_save(
        cog_level, ['COG', 'description'],
        os.path.join(outdir, 'COG.xlsx'),
        out_prefix='COG', func_tmp_subdir=func_tmp_cog
    )

    # 2) Category 级别：使用拆行后的数据，按单字母 category 汇总
    cat_level = cog_tpm_annotated[['category_letter', 'category_description'] + samples].copy()
    cat_level = cat_level.dropna(subset=['category_letter'])
    cat_level['category_label'] = cat_level['category_letter'] + ': ' + cat_level['category_description']
    cat_level = cat_level[['category_label'] + samples]
    aggregate_and_save(
        cat_level, ['category_label'],
        os.path.join(outdir, 'COG.Category.xlsx'),
        out_prefix='COG_Category', func_tmp_subdir=func_tmp_cog
    )

    # 3) Function group 级别
    fun_level = cog_tpm_annotated[['function_group', 'function_group_description'] + samples].copy()
    fun_level = fun_level.dropna(subset=['function_group'])
    fun_level['function_group_label'] = fun_level['function_group'] + ': ' + fun_level['function_group_description']
    fun_level = fun_level[['function_group_label'] + samples]
    aggregate_and_save(
        fun_level, ['function_group_label'],
        os.path.join(outdir, 'COG.Function.xlsx'),
        out_prefix='COG_Function', func_tmp_subdir=func_tmp_cog
    )

    log.info('COG 统计完成，输出目录: %s', outdir)


if __name__ == '__main__':
    main()
