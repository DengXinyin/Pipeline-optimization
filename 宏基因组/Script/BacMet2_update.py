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
    gi_match = re.search(r'gi\|(\d+)\|', sseqid)
    if gi_match:
        return gi_match.group(1)
    bac_match = re.search(r'(BAC\w+)\|', sseqid)
    if bac_match:
        return bac_match.group(1)
    return None


def bacmet2(dbdir, prodigal_dir, bacmet2_dir):
    cmd = '''diamond blastx --threads 30 --db {0}/BacMet/BacMet2 -e 1e-5 \
--query {1}/unique_gene.fasta --out {2}/BacMet_anno.txt
sed -i '1i\\qseqid\tsseqid\tpident\tlength\tmismatch\tgapopen\tqstart\tqend\tsstart\tsend\tevalue\tbiotscore' {2}/BacMet_anno.txt
'''.format(dbdir, prodigal_dir, bacmet2_dir)
    run_cmd(cmd)


def get_bacmet2_table(dbdir, bacmet2_dir, anno_dir, bowtie):
    bacmet2_map = pd.read_csv('%s/BacMet/BacMet2_all.mapping.txt' % dbdir, sep='\t')
    gene_tax = pd.read_csv('%s/gene.taxonomy.csv' % anno_dir, index_col=0)
    gene_tax['taxonomy'] = [';'.join(i) for i in gene_tax.values]
    gene_tax = gene_tax.reset_index().rename(columns={'index': 'GeneID'})
    gene_tax = gene_tax.loc[:, ['GeneID', 'taxonomy']]

    bacmet2 = pd.read_csv('%s/BacMet_anno.txt' % bacmet2_dir, sep='\t')
    bacmet2 = bacmet2.loc[:, ['qseqid', 'sseqid', 'evalue']]
    bacmet2 = bacmet2.loc[bacmet2.groupby('qseqid')['evalue'].idxmin()]
    bacmet2['ID'] = bacmet2['sseqid'].apply(extract_id)
    bacmet2_ano = pd.merge(left=bacmet2, right=bacmet2_map, left_on='ID', right_on='ID')
    bacmet2_ano = bacmet2_ano.loc[:, ['qseqid', 'Gene_name', 'Accession/GenBank_ID', 'Compound', 'Source', 'NCBI_annotation']]
    bacmet2_ano = bacmet2_ano.rename(columns={'qseqid': 'GeneID'})
    bacmet2_ano = pd.merge(left=gene_tax, right=bacmet2_ano, on='GeneID')

    gene_tpm = pd.read_csv('%s/gene_tpm.csv' % bowtie)
    gene_bacmet2_tpm = pd.merge(left=bacmet2_ano, right=gene_tpm, on='GeneID')
    gene_bacmet2_tpm.to_csv('%s/BacMet2.tpm.csv' % bacmet2_dir, index=False, encoding='utf-8-sig')


def main():
    parser = argparse.ArgumentParser(description='BacMet2 annotation (update version)')
    parser.add_argument('--Annotation', type=str, default='Annotation', help='the res of Annotation')
    parser.add_argument('--BacMet2dir', type=str, default='BacMet2', help='the res of BacMet2')
    parser.add_argument('--prodigal', type=str, default='prodigal', help='the res of prodigal')
    parser.add_argument('--dbdir', type=str, default='/data/data1/wangli/database', help='the dir of database')
    parser.add_argument('--bowtie', type=str, default='bowtie', help='the res of bowtie')
    args = parser.parse_args()

    anno_dir = os.path.abspath(args.Annotation)
    prodigal_dir = os.path.abspath(args.prodigal)
    bacmet2_dir = os.path.abspath(args.BacMet2dir)
    dbdir = os.path.abspath(args.dbdir)
    bowtie = os.path.abspath(args.bowtie)

    os.makedirs(bacmet2_dir, exist_ok=True)

    try:
        log.info('开始 BacMet2 diamond 比对')
        bacmet2(dbdir, prodigal_dir, bacmet2_dir)
        log.info('开始生成 BacMet2 丰度表')
        get_bacmet2_table(dbdir, bacmet2_dir, anno_dir, bowtie)
        log.info('BacMet2 注释完成，输出: %s', bacmet2_dir)
    except Exception as e:
        log.error('BacMet2 注释失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
