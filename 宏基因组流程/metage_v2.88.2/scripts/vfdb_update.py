#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import subprocess
import logging
from datetime import datetime

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)


def run_cmd(cmd):
    """执行 shell 命令，失败则抛出异常。"""
    log.info('执行命令: %s', cmd.strip().split('\n')[0])
    subprocess.run(cmd, shell=True, check=True)


def vfdb(dbdir, prodigal_dir, vfdb_dir):
    cmd = '''diamond blastx --threads 30 --db {0}/VFDB/version-2025-12/VFDB_setA -e 1e-5 \
--query {1}/unique_gene.fasta --out {2}/vf_anno.txt
sed -i '1i\\qseqid\tsseqid\tpident\tlength\tmismatch\tgapopen\tqstart\tqend\tsstart\tsend\tevalue\tbiotscore' {2}/vf_anno.txt
'''.format(dbdir, prodigal_dir, vfdb_dir)
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


def write_empty_outputs(vfdb_dir, sample_cols):
    pd.DataFrame(columns=['GeneID', 'taxonomy', 'VF_Name', 'VFcategory'] + sample_cols).to_csv(
        '%s/gene.vf.tpm.csv' % vfdb_dir, index=False, encoding='utf-8-sig'
    )
    pd.DataFrame(columns=sample_cols, index=pd.Index([], name='VF_Name')).to_excel(
        '%s/vf.tpm.xlsx' % vfdb_dir
    )
    pd.DataFrame(columns=sample_cols, index=pd.Index([], name='VFcategory')).to_excel(
        '%s/vf.category.tpm.xlsx' % vfdb_dir
    )


def get_vftable(dbdir, vfdb_dir, bowtie, anno_dir):
    vf_map = pd.read_csv('%s/VFDB/version-2025-12/VF_map.csv' % dbdir, dtype=str)
    fasta2vf = pd.read_csv('%s/VFDB/version-2025-12/fasta2VFID.tsv' % dbdir,
                           sep='\t', dtype=str)
    required_vf_map = {'VFID', 'VF_Name', 'VFcategory'}
    required_fasta_map = {'fasta_ID', 'VFID'}
    if not required_vf_map.issubset(vf_map.columns):
        raise ValueError('VF_map.csv 缺少字段: %s' % sorted(required_vf_map - set(vf_map.columns)))
    if not required_fasta_map.issubset(fasta2vf.columns):
        raise ValueError('fasta2VFID.tsv 缺少字段: %s' %
                         sorted(required_fasta_map - set(fasta2vf.columns)))

    gene_tax = read_gene_taxonomy(anno_dir)
    gene_tpm = pd.read_csv('%s/gene_tpm.csv' % bowtie, dtype={'GeneID': str})
    if 'GeneID' not in gene_tpm.columns:
        raise ValueError('gene_tpm.csv 缺少 GeneID 字段')
    if gene_tpm['GeneID'].isna().any() or gene_tpm['GeneID'].duplicated().any():
        raise ValueError('gene_tpm.csv 的 GeneID 含空值或重复值')
    sample_cols = [col for col in gene_tpm.columns if col != 'GeneID']

    vfres = pd.read_csv('%s/vf_anno.txt' % vfdb_dir, sep='\t', dtype=str)
    if vfres.empty:
        log.info('VFDB DIAMOND 无命中，生成结构完整的空结果')
        write_empty_outputs(vfdb_dir, sample_cols)
        return
    vfres['evalue'] = pd.to_numeric(vfres['evalue'], errors='raise')
    vfres = vfres.loc[:, ['qseqid', 'sseqid', 'evalue']]
    vfres = vfres.loc[vfres.groupby('qseqid')['evalue'].idxmin()]
    vfres = pd.merge(left=vfres, right=fasta2vf, left_on='sseqid', right_on='fasta_ID')
    if vfres.empty:
        raise ValueError('VFDB 有 DIAMOND 命中，但 sseqid 无法映射到 fasta2VFID.tsv')
    vf_ano = pd.merge(left=vfres, right=vf_map, on='VFID')
    if vf_ano.empty:
        raise ValueError('VFDB 命中已映射到 VFID，但无法映射到 VF_map.csv')
    vf_ano = vf_ano.loc[:, ['qseqid', 'VF_Name', 'VFcategory']]
    vf_ano = vf_ano.rename(columns={'qseqid': 'GeneID'})
    check_gene_id_overlap(vf_ano['GeneID'], gene_tpm['GeneID'], 'VFDB 命中', 'gene_tpm.csv')
    gene_vf_tpm = pd.merge(left=vf_ano, right=gene_tpm, on='GeneID')
    gene_vf_tpm = add_optional_taxonomy(gene_vf_tpm, gene_tax, 'VFDB TPM 结果')
    gene_vf_tpm = gene_vf_tpm.loc[:,
                                  ['GeneID', 'taxonomy', 'VF_Name', 'VFcategory'] + sample_cols]
    gene_vf_tpm.to_csv('%s/gene.vf.tpm.csv' % vfdb_dir, index=False, encoding='utf-8-sig')

    vf_tpm = gene_vf_tpm.groupby('VF_Name')[sample_cols].sum()
    vf_tpm.to_excel('%s/vf.tpm.xlsx' % vfdb_dir, index=True)

    vf_ca_tpm = gene_vf_tpm.groupby('VFcategory')[sample_cols].sum()
    vf_ca_tpm.to_excel('%s/vf.category.tpm.xlsx' % vfdb_dir, index=True)


def main():
    parser = argparse.ArgumentParser(description='VFDB annotation (update version)')
    parser.add_argument('--Annotation', type=str, default='Annotation', help='the res of Annotation')
    parser.add_argument('--VFDB', type=str, default='VFDB', help='the res of VFDB')
    parser.add_argument('--prodigal', type=str, default='prodigal', help='the res of prodigal')
    parser.add_argument('--dbdir', type=str, default='/data/data1/wangli/database', help='the dir of database')
    parser.add_argument('--bowtie', type=str, default='bowtie', help='the res of bowtie')
    args = parser.parse_args()

    anno_dir = os.path.abspath(args.Annotation)
    prodigal_dir = os.path.abspath(args.prodigal)
    vfdb_dir = os.path.abspath(args.VFDB)
    dbdir = os.path.abspath(args.dbdir)
    bowtie = os.path.abspath(args.bowtie)

    os.makedirs(vfdb_dir, exist_ok=True)

    try:
        log.info('开始 VFDB diamond 比对')
        vfdb(dbdir, prodigal_dir, vfdb_dir)
        log.info('开始生成 VFDB 丰度表')
        get_vftable(dbdir, vfdb_dir, bowtie, anno_dir)
        log.info('VFDB 注释完成，输出: %s', vfdb_dir)
    except Exception as e:
        log.error('VFDB 注释失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
