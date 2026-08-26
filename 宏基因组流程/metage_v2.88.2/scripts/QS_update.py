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


DIAMOND_COLS = ['qseqid', 'sseqid', 'pident', 'length', 'mismatch', 'gapopen',
                'qstart', 'qend', 'sstart', 'send', 'evalue', 'bitscore']


def ensure_header(out_file):
    """如果 diamond 输出为空，则写入表头，避免 pandas 解析失败。"""
    if not os.path.exists(out_file) or os.path.getsize(out_file) == 0:
        with open(out_file, 'w') as f:
            f.write('\t'.join(DIAMOND_COLS) + '\n')


def qs(dbdir, prodigal_dir, qs_dir):
    out_file = os.path.join(qs_dir, 'QS_anno.txt')
    cmd = '''diamond blastx --threads 30 --db {0}/QS/QS2025_12-29/QSgo_0009372_2025_1229 -e 1e-5 \
--query {1}/unique_gene.fasta --out {2} \
--outfmt 6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore
'''.format(dbdir, prodigal_dir, out_file)
    run_cmd(cmd)
    ensure_header(out_file)


def read_diamond_table(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return pd.DataFrame(columns=DIAMOND_COLS)
    table = pd.read_csv(
        path, sep='\t', header=None, names=DIAMOND_COLS,
        dtype={'qseqid': str, 'sseqid': str}
    )
    table = table.loc[table['qseqid'] != 'qseqid'].copy()
    if not table.empty:
        table['evalue'] = pd.to_numeric(table['evalue'], errors='raise')
    return table


def read_gene_taxonomy(anno_dir):
    table = pd.read_csv('%s/gene.taxonomy.csv' % anno_dir, dtype=str)
    if 'GeneID' not in table.columns:
        table = table.rename(columns={table.columns[0]: 'GeneID'})
    if table['GeneID'].isna().any() or table['GeneID'].duplicated().any():
        raise ValueError('gene.taxonomy.csv 的 GeneID 含空值或重复值')
    taxonomy_cols = [column for column in table.columns if column != 'GeneID']
    table['taxonomy'] = table[taxonomy_cols].fillna('').apply(
        lambda row: ';'.join(value for value in row.astype(str) if value), axis=1
    )
    return table.loc[:, ['GeneID', 'taxonomy']]


def read_gene_tpm(bowtie):
    table = pd.read_csv('%s/gene_tpm.csv' % bowtie, dtype={'GeneID': str})
    if 'GeneID' not in table.columns:
        raise ValueError('gene_tpm.csv 缺少 GeneID 字段')
    if table['GeneID'].isna().any() or table['GeneID'].duplicated().any():
        raise ValueError('gene_tpm.csv 的 GeneID 含空值或重复值')
    return table, [column for column in table.columns if column != 'GeneID']


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
            '请检查 GeneID 是否发生字符编码或格式损坏。'
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


def write_empty_output(qs_dir, sample_cols):
    annotation_cols = [
        'taxonomy', 'Entry', 'Reviewed', 'Entry Name', 'Gene Names', 'Length',
        'Protein names', 'Function [CC]', 'Protein family', 'GeneID'
    ]
    pd.DataFrame(columns=annotation_cols + sample_cols).to_csv(
        '%s/QS.tpm.csv' % qs_dir, index=False, encoding='utf-8-sig'
    )


def get_qs_table(dbdir, qs_dir, anno_dir, bowtie):
    qs_map = pd.read_excel(
        '%s/QS/QS2025_12-29/uniprotkb_go_0009372_2025_12_29.xlsx' % dbdir,
        dtype=str
    )
    annotation_fields = [
        'Entry', 'Reviewed', 'Entry Name', 'Gene Names', 'Length',
        'Protein names', 'Function [CC]', 'Protein family'
    ]
    required_map = set(annotation_fields)
    if not required_map.issubset(qs_map.columns):
        raise ValueError('QS 映射表缺少字段: %s' %
                         sorted(required_map - set(qs_map.columns)))
    qs_map['Entry'] = qs_map['Entry'].astype(str).str.strip()

    gene_tax = read_gene_taxonomy(anno_dir)
    gene_tpm, sample_cols = read_gene_tpm(bowtie)
    qs_dat = read_diamond_table('%s/QS_anno.txt' % qs_dir)

    if qs_dat.empty:
        log.info('QS DIAMOND 无命中，生成结构完整的空结果')
        write_empty_output(qs_dir, sample_cols)
        return

    qs_dat = qs_dat.loc[:, ['qseqid', 'sseqid', 'evalue']]
    qs_dat = qs_dat.loc[qs_dat.groupby('qseqid')['evalue'].idxmin()]
    qs_dat['ID'] = qs_dat['sseqid'].apply(extract_id)
    qs_ano = pd.merge(left=qs_dat, right=qs_map, left_on='ID', right_on='Entry')
    mapped_queries = qs_ano['qseqid'].nunique()
    log.info('QS 数据库映射: %d/%d 个最佳命中', mapped_queries,
             qs_dat['qseqid'].nunique())
    if qs_ano.empty:
        raise ValueError(
            'QS 有 DIAMOND 命中，但 sseqid 无法映射到 QS 注释表；'
            '请检查数据库与映射表版本。'
        )
    qs_ano = qs_ano.loc[:, ['qseqid'] + annotation_fields]
    qs_ano = qs_ano.rename(columns={'qseqid': 'GeneID'})
    check_gene_id_overlap(qs_ano['GeneID'], gene_tpm['GeneID'], 'QS 命中', 'gene_tpm.csv')
    gene_qs_tpm = pd.merge(left=qs_ano, right=gene_tpm, on='GeneID')
    gene_qs_tpm = add_optional_taxonomy(gene_qs_tpm, gene_tax, 'QS TPM 结果')
    output_cols = ['taxonomy'] + annotation_fields + ['GeneID'] + sample_cols
    gene_qs_tpm = gene_qs_tpm.loc[:, output_cols]
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
