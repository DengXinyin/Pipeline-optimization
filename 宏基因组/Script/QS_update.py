#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import subprocess
import re
import logging

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)


def run_cmd(cmd):
    log.info('执行命令: %s', cmd.strip().split('\n')[0])
    subprocess.run(cmd, shell=True, check=True)


def extract_id(sseqid):
    tr_match = re.search(r'(?:tr|sp)\|(\w+)\|', sseqid)
    if tr_match:
        return tr_match.group(1)
    return None


def qs(dbdir, prodigal_dir, qs_dir):
    cmd = '''diamond blastx --threads 30 --db {0}/QS/QS2025_12-29/QSgo_0009372_2025_1229 -e 1e-5 \
--query {1}/unique_gene.fasta --out {2}/QS_anno.txt
sed -i '1i\\qseqid\tsseqid\tpident\tlength\tmismatch\tgapopen\tqstart\tqend\tsstart\tsend\tevalue\tbiotscore' {2}/QS_anno.txt
'''.format(dbdir, prodigal_dir, qs_dir)
    run_cmd(cmd)


def get_qs_table(dbdir, qs_dir, anno_dir, bowtie):
    qs_map = pd.read_excel('%s/QS/QS2025_12-29/uniprotkb_go_0009372_2025_12_29.xlsx' % dbdir)
    gene_tax = pd.read_csv('%s/gene.taxonomy.csv' % anno_dir, index_col=0)
    gene_tax['taxonomy'] = [';'.join(i) for i in gene_tax.values]
    gene_tax = gene_tax.reset_index().rename(columns={'index': 'GeneID'})
    gene_tax = gene_tax.loc[:, ['GeneID', 'taxonomy']]

    qs_dat = pd.read_csv('%s/QS_anno.txt' % qs_dir, sep='\t')
    qs_dat = qs_dat.loc[:, ['qseqid', 'sseqid', 'evalue']]
    qs_dat = qs_dat.loc[qs_dat.groupby('qseqid')['evalue'].idxmin()]
    qs_dat['ID'] = qs_dat['sseqid'].apply(extract_id)
    qs_ano = pd.merge(left=qs_dat, right=qs_map, left_on='ID', right_on='Entry')
    qs_ano = qs_ano.loc[:, ['qseqid', 'Entry', 'Reviewed', 'Entry Name', 'Gene Names',
                            'Length', 'Protein names', 'Function [CC]', 'Protein family']]
    qs_ano = qs_ano.rename(columns={'qseqid': 'GeneID'})
    qs_ano = pd.merge(left=gene_tax, right=qs_ano, on='GeneID')

    gene_tpm = pd.read_csv('%s/gene_tpm.csv' % bowtie)
    gene_qs_tpm = pd.merge(left=qs_ano, right=gene_tpm, on='GeneID')
    gene_qs_tpm.to_csv('%s/QS.tpm.csv' % qs_dir, index=False, encoding='utf-8-sig')


def main():
    parser = argparse.ArgumentParser(description='QS annotation (update version)')
    parser.add_argument('--Annotation', type=str, default='Annotation', help='the res of Annotation')
    parser.add_argument('--QSdir', type=str, default='QS', help='the res of QS')
    parser.add_argument('--prodigal', type=str, default='prodigal', help='the res of prodigal')
    parser.add_argument('--dbdir', type=str, default='/data/data1/wangli/database', help='the dir of database')
    parser.add_argument('--bowtie', type=str, default='bowtie', help='the res of bowtie')
    args = parser.parse_args()

    anno_dir = os.path.abspath(args.Annotation)
    prodigal_dir = os.path.abspath(args.prodigal)
    qs_dir = os.path.abspath(args.QSdir)
    dbdir = os.path.abspath(args.dbdir)
    bowtie = os.path.abspath(args.bowtie)

    os.makedirs(qs_dir, exist_ok=True)

    try:
        log.info('开始 QS diamond 比对')
        qs(dbdir, prodigal_dir, qs_dir)
        log.info('开始生成 QS 丰度表')
        get_qs_table(dbdir, qs_dir, anno_dir, bowtie)
        log.info('QS 注释完成，输出: %s', qs_dir)
    except Exception as e:
        log.error('QS 注释失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
