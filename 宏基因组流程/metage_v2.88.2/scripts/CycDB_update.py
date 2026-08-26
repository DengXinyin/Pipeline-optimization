#!/usr/bin/env python
# -*- coding: utf-8 -*-

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


def get_cyctable(anno_dir, bowtie, cycdb_dir, dbdir):
    gene_tpm = pd.read_csv('%s/gene_tpm.csv' % bowtie, dtype={'GeneID': str})
    if 'GeneID' not in gene_tpm.columns:
        raise ValueError('gene_tpm.csv 缺少 GeneID 字段')
    if gene_tpm['GeneID'].isna().any() or gene_tpm['GeneID'].duplicated().any():
        raise ValueError('gene_tpm.csv 的 GeneID 含空值或重复值')
    sample_cols = [col for col in gene_tpm.columns if col != 'GeneID']

    gene_tax = pd.read_csv('%s/gene.taxonomy.csv' % anno_dir, dtype=str)
    if 'GeneID' not in gene_tax.columns:
        gene_tax = gene_tax.rename(columns={gene_tax.columns[0]: 'GeneID'})
    if gene_tax['GeneID'].isna().any() or gene_tax['GeneID'].duplicated().any():
        raise ValueError('gene.taxonomy.csv 的 GeneID 含空值或重复值')
    tax_cols = [col for col in gene_tax.columns if col != 'GeneID']
    gene_tax['taxonomy'] = gene_tax[tax_cols].fillna('').apply(
        lambda row: ';'.join(value for value in row.astype(str) if value), axis=1
    )
    gene_tax = gene_tax.loc[:, ['GeneID', 'taxonomy']]

    gene_ko = pd.read_csv('%s/KEGG/KEGG.tpm.csv' % anno_dir,
                          dtype={'GeneID': str, 'KO': str})
    required_ko = {'GeneID', 'KO'}
    if not required_ko.issubset(gene_ko.columns):
        raise ValueError('KEGG.tpm.csv 缺少字段: %s' % sorted(required_ko - set(gene_ko.columns)))
    gene_ko = gene_ko.loc[:, ['GeneID', 'KO']].drop_duplicates()
    ko_ids = set(gene_ko['GeneID'].astype(str))
    tpm_overlap = ko_ids & set(gene_tpm['GeneID'].astype(str))
    tpm_ratio = len(tpm_overlap) / max(1, len(ko_ids))
    log.info('KEGG.tpm.csv 与 gene_tpm.csv 的 GeneID 交集: %d/%d (%.2f%%)',
             len(tpm_overlap), len(ko_ids), tpm_ratio * 100)
    if ko_ids and (not tpm_overlap or tpm_ratio < 0.01):
        raise ValueError(
            'KEGG.tpm.csv 与 gene_tpm.csv 的 GeneID 几乎无法匹配（%.2f%%），'
            '请检查 GeneID 是否发生字符编码或格式损坏。' % (tpm_ratio * 100)
        )

    gene_ko_tpm = pd.merge(left=gene_ko, right=gene_tpm, on='GeneID')
    tax_overlap = set(gene_ko_tpm['GeneID'].astype(str)) & set(gene_tax['GeneID'].astype(str))
    tax_ratio = len(tax_overlap) / max(1, gene_ko_tpm['GeneID'].nunique())
    log.info('KEGG TPM 结果的 taxonomy 覆盖: %d/%d (%.2f%%)',
             len(tax_overlap), gene_ko_tpm['GeneID'].nunique(), tax_ratio * 100)

    cycdb_files = ['Carbon', 'Methane', 'Nitrogen', 'phosphorylation', 'Sulfur']
    for cyc in cycdb_files:
        cyc_map = pd.read_csv('%s/diting/%s.txt' % (dbdir, cyc), sep='\t', dtype=str)
        required_map = {'KO', 'Cycle', 'Pathway', 'Detail'}
        if not required_map.issubset(cyc_map.columns):
            raise ValueError('%s 循环映射表缺少字段: %s' %
                             (cyc, sorted(required_map - set(cyc_map.columns))))
        cyc_tpm = pd.merge(left=gene_ko_tpm, right=cyc_map, on='KO')
        cyc_tpm = pd.merge(
            left=cyc_tpm, right=gene_tax, on='GeneID', how='left', validate='many_to_one'
        )
        cyc_tpm['taxonomy'] = cyc_tpm['taxonomy'].replace(
            r'^\s*$', pd.NA, regex=True
        ).fillna('unclassified')
        cyc_tpm = cyc_tpm.drop(['Cycle'], axis=1)
        cyc_tpm = cyc_tpm.drop_duplicates()
        if cyc_tpm.shape[0] == 0:
            log.info('%s 循环无注释结果，跳过', cyc)
            continue
        # Detail 是下游 CycDB_stats_update.py 生成明细层统计表的必需字段。
        cyc_tpm = cyc_tpm.loc[
            :, ['GeneID', 'taxonomy', 'KO', 'Pathway', 'Detail'] + sample_cols
        ]
        cyc_tpm.to_excel('%s/%s_Cycle.xlsx' % (cycdb_dir, cyc), index=False)

        cyc_pathway = cyc_tpm.groupby('Pathway')[sample_cols].sum()
        cyc_pathway.to_excel('%s/%s_Cycle_pathway.xlsx' % (cycdb_dir, cyc), index=True)


def main():
    parser = argparse.ArgumentParser(description='CycDB annotation (update version)')
    parser.add_argument('--Annotation', type=str, default='Annotation', help='the res of Annotation')
    parser.add_argument('--CycDB', type=str, default='CycDB', help='the res of CycDB')
    parser.add_argument('--dbdir', type=str, default='/data/data1/wangli/database', help='the dir of database')
    parser.add_argument('--bowtie', type=str, default='bowtie', help='the res of bowtie')
    args = parser.parse_args()

    anno_dir = os.path.abspath(args.Annotation)
    cycdb_dir = os.path.abspath(args.CycDB)
    dbdir = os.path.abspath(args.dbdir)
    bowtie = os.path.abspath(args.bowtie)

    os.makedirs(cycdb_dir, exist_ok=True)

    try:
        log.info('开始生成 CycDB 丰度表')
        get_cyctable(anno_dir, bowtie, cycdb_dir, dbdir)
        log.info('CycDB 注释完成，输出: %s', cycdb_dir)
    except Exception as e:
        log.error('CycDB 注释失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
