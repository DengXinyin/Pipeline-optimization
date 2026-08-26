#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
gene_func_taxonomy_update.py

整合基因物种注释、功能注释（eggNOG / KEGG / CAZy / GO）以及
KEGG/eggNOG/CAZy/GO 丰度结果，生成基因-功能-物种三联表。
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


def read_taxonomy(tax_file):
    """读取基因物种注释表。"""
    tax = pd.read_csv(tax_file, index_col=0)
    tax['taxonomy'] = [';'.join(str(x) for x in row) for row in tax.values]
    tax = tax.reset_index().rename(columns={'index': 'GeneID'})
    return tax[['GeneID', 'taxonomy']]


def read_func_anno(func_anno_file):
    """读取 eggNOG mapper 功能注释表。"""
    df = pd.read_csv(func_anno_file, sep='\t')
    df = df.rename(columns={
        '#query': 'GeneID',
        'eggNOG_OGs': 'eggNOG',
        'KEGG_ko': 'KEGG_KO',
        'GOs': 'GO',
        'CAZy': 'CAZy'
    })
    return df


def merge_function_taxonomy(tax_df, func_df):
    """合并物种注释与功能注释。"""
    # 保留关键功能列
    keep_cols = ['GeneID', 'eggNOG', 'KEGG_KO', 'CAZy', 'GO']
    keep_cols = [c for c in keep_cols if c in func_df.columns]
    func_df = func_df[keep_cols]
    merged = pd.merge(tax_df, func_df, on='GeneID', how='outer')
    return merged


def add_abundance_info(result_df, anno_dir):
    """
    TODO: 将 KEGG / eggNOG / CAZy / GO 的丰度/描述信息合并到三联表中。
    当前版本仅保留基因-功能-物种基础信息，后续可补充 TPM、pathway 等列。
    """
    log.info('TODO: 合并 KEGG/eggNOG/CAZy/GO 丰度与描述信息')
    return result_df


def main():
    parser = argparse.ArgumentParser(description='生成基因-功能-物种三联表')
    parser.add_argument('--Annotation', type=str, default='Annotation',
                        help='Annotation 结果目录，包含 gene.taxonomy.csv 与 func.emapper.annotations')
    parser.add_argument('--taxonomy', type=str, default=None,
                        help='gene.taxonomy.csv 路径（默认 Annotation/gene.taxonomy.csv）')
    parser.add_argument('--func_anno', type=str, default=None,
                        help='func.emapper.annotations 路径（默认 Annotation/func.emapper.annotations）')
    parser.add_argument('--outfile', type=str, default=None,
                        help='输出文件路径（默认 Annotation/gene_function_taxonomy.csv）')
    args = parser.parse_args()

    anno_dir = os.path.abspath(args.Annotation)
    tax_file = args.taxonomy or os.path.join(anno_dir, 'gene.taxonomy.csv')
    func_file = args.func_anno or os.path.join(anno_dir, 'func.emapper.annotations')
    outfile = args.outfile or os.path.join(anno_dir, 'gene_function_taxonomy.csv')

    for p in [tax_file, func_file]:
        if not os.path.exists(p):
            log.error('输入文件不存在: %s', p)
            sys.exit(1)

    try:
        log.info('读取物种注释: %s', tax_file)
        tax_df = read_taxonomy(tax_file)
        log.info('读取功能注释: %s', func_file)
        func_df = read_func_anno(func_file)
        log.info('合并基因-功能-物种信息')
        result_df = merge_function_taxonomy(tax_df, func_df)
        result_df = add_abundance_info(result_df, anno_dir)
        result_df.to_csv(outfile, index=False, encoding='utf-8-sig')
        log.info('三联表已输出: %s', outfile)
    except Exception as e:
        log.error('生成基因-功能-物种三联表失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
