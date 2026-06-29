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
    gene_tpm = pd.read_csv('%s/gene_tpm.csv' % bowtie)
    gene_tax = pd.read_csv('%s/gene.taxonomy.csv' % anno_dir, index_col=0)
    gene_tax['taxonomy'] = [';'.join(i) for i in gene_tax.values]
    gene_tax = gene_tax.reset_index().rename(columns={'index': 'GeneID'})
    gene_tax = gene_tax.loc[:, ['GeneID', 'taxonomy']]

    cycdb_files = ['Carbon', 'Methane', 'Nitrogen', 'phosphorylation', 'Sulfur']
    for cyc in cycdb_files:
        cyc_map = pd.read_csv('%s/diting/%s.txt' % (dbdir, cyc), sep='\t')
        gene_ko = pd.read_csv('%s/KEGG/KEGG.tpm.csv' % anno_dir)
        gene_ko = gene_ko.iloc[:, 0:2]
        cyc_anno = pd.merge(left=gene_ko, right=cyc_map, on='KO')
        cyc_anno = pd.merge(left=gene_tax, right=cyc_anno, on='GeneID')

        cyc_tpm = pd.merge(left=cyc_anno, right=gene_tpm, on='GeneID')
        cyc_tpm = cyc_tpm.drop(['Cycle'], axis=1)
        cyc_tpm = cyc_tpm.drop_duplicates()
        if cyc_tpm.shape[0] == 0:
            log.info('%s 循环无注释结果，跳过', cyc)
            continue
        cyc_tpm.to_excel('%s/%s_Cycle.xlsx' % (cycdb_dir, cyc), index=False)

        k = cyc_tpm.shape[1]
        cyc_pathway = cyc_tpm.iloc[:, [3] + list(range(5, k))]
        cyc_pathway = cyc_pathway.groupby('Pathway').sum()
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
