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


def read_gene_taxonomy(anno_dir):
    gene_tax = pd.read_csv('%s/gene.taxonomy.csv' % anno_dir, dtype=str)
    if 'GeneID' not in gene_tax.columns:
        gene_tax = gene_tax.rename(columns={gene_tax.columns[0]: 'GeneID'})
    if gene_tax['GeneID'].isna().any() or gene_tax['GeneID'].duplicated().any():
        raise ValueError('gene.taxonomy.csv 的 GeneID 含空值或重复值')
    tax_cols = [col for col in gene_tax.columns if col != 'GeneID']
    gene_tax['taxonomy'] = gene_tax[tax_cols].fillna('').apply(
        lambda row: ';'.join(value for value in row.astype(str) if value), axis=1
    )
    return gene_tax.loc[:, ['GeneID', 'taxonomy']]


def check_gene_id_overlap(left_ids, right_ids, left_name, right_name):
    left_set = set(left_ids.astype(str))
    right_set = set(right_ids.astype(str))
    overlap = left_set & right_set
    ratio = len(overlap) / max(1, len(left_set))
    log.info('%s 与 %s 的 GeneID 交集: %d/%d (%.2f%%)',
             left_name, right_name, len(overlap), len(left_set), ratio * 100)
    if not overlap or ratio < 0.01:
        examples = list(left_set - right_set)[:3]
        raise ValueError(
            '%s 与 %s 的 GeneID 几乎无法匹配（交集 %.2f%%；示例: %s）。'
            '请检查 GeneID 是否在分类转换过程中发生中文编码损坏。'
            % (left_name, right_name, ratio * 100, examples)
        )


def add_optional_taxonomy(table, gene_tax, label):
    """补充可选分类；功能基因没有 NR 分类时保留并标记为 unclassified。"""
    hit_ids = set(table['GeneID'].astype(str))
    tax_ids = set(gene_tax['GeneID'].astype(str))
    overlap = hit_ids & tax_ids
    ratio = len(overlap) / max(1, len(hit_ids))
    log.info('%s 的 taxonomy 覆盖: %d/%d (%.2f%%)',
             label, len(overlap), len(hit_ids), ratio * 100)
    table = pd.merge(
        left=table, right=gene_tax, on='GeneID', how='left', validate='many_to_one'
    )
    table['taxonomy'] = table['taxonomy'].replace(
        r'^\s*$', pd.NA, regex=True
    ).fillna('unclassified')
    return table


def write_empty_outputs(arg_dir, sample_cols):
    pd.DataFrame(columns=['GeneID', 'taxonomy', 'Type', 'ARG'] + sample_cols).to_csv(
        '%s/ARG.tpm.csv' % arg_dir, index=False, encoding='utf-8-sig'
    )
    pd.DataFrame(columns=sample_cols, index=pd.Index([], name='Type')).to_excel(
        '%s/ARG.Category.tpm.xlsx' % arg_dir
    )


def get_argtable(dbdir, arg_dir, anno_dir, bowtie):
    arg_map = pd.read_csv('%s/ARGs/SARG_v3.2_S_database.txt' % dbdir, sep='\t', dtype=str)
    required_map = {'SARG.Seq.ID', 'Type', 'ARG'}
    if not required_map.issubset(arg_map.columns):
        raise ValueError('SARG 数据库映射表缺少字段: %s' %
                         sorted(required_map - set(arg_map.columns)))
    gene_tax = read_gene_taxonomy(anno_dir)
    gene_tpm = pd.read_csv('%s/gene_tpm.csv' % bowtie, dtype={'GeneID': str})
    if 'GeneID' not in gene_tpm.columns:
        raise ValueError('gene_tpm.csv 缺少 GeneID 字段')
    if gene_tpm['GeneID'].isna().any() or gene_tpm['GeneID'].duplicated().any():
        raise ValueError('gene_tpm.csv 的 GeneID 含空值或重复值')
    sample_cols = [col for col in gene_tpm.columns if col != 'GeneID']

    args_dat = pd.read_csv('%s/ARGs_anno.txt' % arg_dir, sep='\t', dtype=str)
    if args_dat.empty:
        log.info('ARGs DIAMOND 无命中，生成结构完整的空结果')
        write_empty_outputs(arg_dir, sample_cols)
        return
    args_dat['evalue'] = pd.to_numeric(args_dat['evalue'], errors='raise')
    args_dat = args_dat.loc[:, ['qseqid', 'sseqid', 'evalue']]
    args_dat = args_dat.loc[args_dat.groupby('qseqid')['evalue'].idxmin()]
    arg_ano = pd.merge(left=args_dat, right=arg_map, left_on='sseqid', right_on='SARG.Seq.ID')
    if arg_ano.empty:
        raise ValueError('ARGs 有 DIAMOND 命中，但 sseqid 无法映射到 SARG 数据库映射表')
    arg_ano = arg_ano.loc[:, ['qseqid', 'Type', 'ARG']]
    arg_ano = arg_ano.rename(columns={'qseqid': 'GeneID'})
    check_gene_id_overlap(arg_ano['GeneID'], gene_tpm['GeneID'], 'ARGs 命中', 'gene_tpm.csv')
    gene_arg_tpm = pd.merge(left=arg_ano, right=gene_tpm, on='GeneID')
    gene_arg_tpm = add_optional_taxonomy(gene_arg_tpm, gene_tax, 'ARGs TPM 结果')
    gene_arg_tpm = gene_arg_tpm.loc[:, ['GeneID', 'taxonomy', 'Type', 'ARG'] + sample_cols]
    gene_arg_tpm.to_csv('%s/ARG.tpm.csv' % arg_dir, index=False, encoding='utf-8-sig')

    arg_cat_tpm = gene_arg_tpm.groupby('Type')[sample_cols].sum()
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
