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


def arg_soap(dbdir, prodigal_dir, arg_dir):
    cmd = '''diamond blastx --threads 30 --db {0}/ARGs/SARG_v3.2 -e 1e-5 \
--query {1}/unique_gene.fasta --out {2}/ARGs_anno.txt
sed -i '1i\\qseqid\tsseqid\tpident\tlength\tmismatch\tgapopen\tqstart\tqend\tsstart\tsend\tevalue\tbiotscore' {2}/ARGs_anno.txt
'''.format(dbdir, prodigal_dir, arg_dir)
    run_cmd(cmd)


def get_argtable(dbdir, arg_dir, anno_dir, bowtie):
    arg_map = pd.read_csv('%s/ARGs/SARG_v3.2_S_database.txt' % dbdir, sep='\t')
    gene_tax = pd.read_csv('%s/gene.taxonomy.csv' % anno_dir, index_col=0)
    gene_tax['taxonomy'] = [';'.join(i) for i in gene_tax.values]
    gene_tax = gene_tax.reset_index().rename(columns={'index': 'GeneID'})
    gene_tax = gene_tax.loc[:, ['GeneID', 'taxonomy']]

    args_dat = pd.read_csv('%s/ARGs_anno.txt' % arg_dir, sep='\t')
    args_dat = args_dat.loc[:, ['qseqid', 'sseqid', 'evalue']]
    args_dat = args_dat.loc[args_dat.groupby('qseqid')['evalue'].idxmin()]
    arg_ano = pd.merge(left=args_dat, right=arg_map, left_on='sseqid', right_on='SARG.Seq.ID')
    arg_ano = arg_ano.loc[:, ['qseqid', 'Type', 'ARG']]
    arg_ano = arg_ano.rename(columns={'qseqid': 'GeneID'})
    arg_ano = pd.merge(left=gene_tax, right=arg_ano, on='GeneID')

    gene_tpm = pd.read_csv('%s/gene_tpm.csv' % bowtie)
    gene_arg_tpm = pd.merge(left=arg_ano, right=gene_tpm, on='GeneID')
    gene_arg_tpm.to_csv('%s/ARG.tpm.csv' % arg_dir, index=False, encoding='utf-8-sig')

    k = gene_arg_tpm.shape[1]
    arg_cat_tpm = gene_arg_tpm.iloc[:, [2] + list(range(4, k))]
    arg_cat_tpm = arg_cat_tpm.groupby('Type').sum()
    arg_cat_tpm.to_excel('%s/ARG.Category.tpm.xlsx' % arg_dir, index=True)


def main():
    parser = argparse.ArgumentParser(description='ARGs annotation (update version)')
    parser.add_argument('--Annotation', type=str, default='Annotation', help='the res of Annotation')
    parser.add_argument('--ARGdir', type=str, default='ARGs', help='the res of ARGs')
    parser.add_argument('--prodigal', type=str, default='prodigal', help='the res of prodigal')
    parser.add_argument('--dbdir', type=str, default='/data/data1/wangli/database', help='the dir of database')
    parser.add_argument('--bowtie', type=str, default='bowtie', help='the res of bowtie')
    args = parser.parse_args()

    anno_dir = os.path.abspath(args.Annotation)
    prodigal_dir = os.path.abspath(args.prodigal)
    arg_dir = os.path.abspath(args.ARGdir)
    dbdir = os.path.abspath(args.dbdir)
    bowtie = os.path.abspath(args.bowtie)

    os.makedirs(arg_dir, exist_ok=True)

    try:
        log.info('开始 ARGs diamond 比对')
        arg_soap(dbdir, prodigal_dir, arg_dir)
        log.info('开始生成 ARGs 丰度表')
        get_argtable(dbdir, arg_dir, anno_dir, bowtie)
        log.info('ARGs 注释完成，输出: %s', arg_dir)
    except Exception as e:
        log.error('ARGs 注释失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
