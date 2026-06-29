#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import subprocess
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


def mobileog(dbdir, prodigal_dir, mobileog_dir):
    cmd = '''diamond blastx --threads 30 --db {0}/mobileOG/mobileOG_beatrix-1.6 -e 1e-5 \
--query {1}/unique_gene.fasta --out {2}/mobileOG_anno.txt
sed -i '1i\\qseqid\tsseqid\tpident\tlength\tmismatch\tgapopen\tqstart\tqend\tsstart\tsend\tevalue\tbiotscore' {2}/mobileOG_anno.txt
'''.format(dbdir, prodigal_dir, mobileog_dir)
    run_cmd(cmd)


def get_mobileog_table(dbdir, mobileog_dir, anno_dir, bowtie):
    mobileog_map = pd.read_csv('%s/mobileOG/mobileOG-db-beatrix-1.6-All.csv' % dbdir, sep=',')
    gene_tax = pd.read_csv('%s/gene.taxonomy.csv' % anno_dir, index_col=0)
    gene_tax['taxonomy'] = [';'.join(i) for i in gene_tax.values]
    gene_tax = gene_tax.reset_index().rename(columns={'index': 'GeneID'})
    gene_tax = gene_tax.loc[:, ['GeneID', 'taxonomy']]

    mobileogs = pd.read_csv('%s/mobileOG_anno.txt' % mobileog_dir, sep='\t')
    mobileogs = mobileogs.loc[:, ['qseqid', 'sseqid', 'evalue']]
    mobileogs = mobileogs.loc[mobileogs.groupby('qseqid')['evalue'].idxmin()]
    mobileog_ano = pd.merge(
        left=mobileogs, right=mobileog_map,
        left_on='sseqid', right_on='mobileOG fasta Header'
    )
    mobileog_ano = mobileog_ano.loc[:, ['qseqid', 'mobileOG Entry Name', 'Best Hit ID', 'mobileOG Cluster', 'Name',
                                          'Manual Annotation', 'Major mobileOG Category', 'Minor mobileOG Categories',
                                          'Reference(s)', 'Evidence']]
    mobileog_ano = mobileog_ano.rename(columns={'qseqid': 'GeneID'})
    mobileog_ano = pd.merge(left=gene_tax, right=mobileog_ano, on='GeneID')

    gene_tpm = pd.read_csv('%s/gene_tpm.csv' % bowtie)
    gene_mobileog_tpm = pd.merge(left=mobileog_ano, right=gene_tpm, on='GeneID')
    gene_mobileog_tpm.to_csv('%s/mobileOG.tpm.csv' % mobileog_dir, index=False, encoding='utf-8-sig')


def main():
    parser = argparse.ArgumentParser(description='mobileOG annotation (update version)')
    parser.add_argument('--Annotation', type=str, default='Annotation', help='the res of Annotation')
    parser.add_argument('--mobileOGdir', type=str, default='mobileOGs', help='the res of mobileOGs')
    parser.add_argument('--prodigal', type=str, default='prodigal', help='the res of prodigal')
    parser.add_argument('--dbdir', type=str, default='/data/data1/wangli/database', help='the dir of database')
    parser.add_argument('--bowtie', type=str, default='bowtie', help='the res of bowtie')
    args = parser.parse_args()

    anno_dir = os.path.abspath(args.Annotation)
    prodigal_dir = os.path.abspath(args.prodigal)
    mobileog_dir = os.path.abspath(args.mobileOGdir)
    dbdir = os.path.abspath(args.dbdir)
    bowtie = os.path.abspath(args.bowtie)

    os.makedirs(mobileog_dir, exist_ok=True)

    try:
        log.info('开始 mobileOG diamond 比对')
        mobileog(dbdir, prodigal_dir, mobileog_dir)
        log.info('开始生成 mobileOG 丰度表')
        get_mobileog_table(dbdir, mobileog_dir, anno_dir, bowtie)
        log.info('mobileOG 注释完成，输出: %s', mobileog_dir)
    except Exception as e:
        log.error('mobileOG 注释失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
