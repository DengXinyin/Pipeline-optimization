#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
COG_update.py

使用 diamond 对非冗余基因进行 COG 数据库注释，并生成基因水平的 COG TPM 表。
"""

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

DIAMOND_COLS = ['qseqid', 'sseqid', 'pident', 'length', 'mismatch', 'gapopen',
                'qstart', 'qend', 'sstart', 'send', 'evalue', 'bitscore']


def run_cmd(cmd):
    log.info('执行命令: %s', cmd.strip().split('\n')[0])
    subprocess.run(cmd, shell=True, check=True)


def check_tpm_overlap(hit_ids, tpm_ids, label):
    hit_set = set(hit_ids.astype(str))
    tpm_set = set(tpm_ids.astype(str))
    overlap = hit_set & tpm_set
    ratio = len(overlap) / max(1, len(hit_set))
    log.info('%s 与 gene_tpm.csv 的 GeneID 交集: %d/%d (%.2f%%)',
             label, len(overlap), len(hit_set), ratio * 100)
    if not overlap or ratio < 0.01:
        examples = list(hit_set - tpm_set)[:3]
        raise ValueError(
            '%s 与 gene_tpm.csv 的 GeneID 几乎无法匹配（交集 %.2f%%；示例: %s）。'
            '请检查 GeneID 是否发生字符编码或格式损坏。'
            % (label, ratio * 100, examples)
        )


def add_optional_taxonomy(table, gene_tax, label):
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


def read_diamond_table(out_file):
    """DIAMOND outfmt 6 没有表头；空文件返回具有标准列的空表。"""
    if not os.path.exists(out_file) or os.path.getsize(out_file) == 0:
        return pd.DataFrame(columns=DIAMOND_COLS)
    return pd.read_csv(
        out_file, sep='\t', header=None, names=DIAMOND_COLS,
        dtype={'qseqid': str, 'sseqid': str}
    )


def write_empty_outputs(cog_dir, sample_cols):
    columns = ['GeneID', 'taxonomy', 'COG'] + sample_cols
    pd.DataFrame(columns=columns).to_csv(
        os.path.join(cog_dir, 'COG.tpm.csv'), index=False, encoding='utf-8-sig'
    )
    pd.DataFrame(columns=sample_cols, index=pd.Index([], name='COG')).to_excel(
        os.path.join(cog_dir, 'COG.Category.tpm.xlsx'), index=True
    )


def cog_diamond(dbdir, prodigal_dir, cog_dir):
    """diamond blastx 比对 COG 数据库。"""
    out_file = os.path.join(cog_dir, 'COG_anno.txt')
    cmd = '''diamond blastx --threads 30 --db {0}/COG/COG -e 1e-5 \
--query {1}/unique_gene.fasta --out {2} \
--outfmt 6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore
'''.format(dbdir, prodigal_dir, out_file)
    run_cmd(cmd)


def get_cog_table(dbdir, cog_dir, anno_dir, bowtie):
    """根据 diamond 结果生成 COG.tpm.csv。"""
    cog_map_path = os.path.join(dbdir, 'COG', 'cog2003-2014.csv')
    if not os.path.exists(cog_map_path):
        log.warning('COG 映射文件不存在: %s，使用占位映射', cog_map_path)
        cog_map = pd.DataFrame(columns=['protein_id', 'COG'])
    else:
        cog_map = pd.read_csv(cog_map_path, header=None, dtype=str)
        cog_map.columns = ['protein_id', 'COG'] + ['col{}'.format(i) for i in range(2, cog_map.shape[1])]

    gene_tax_raw = pd.read_csv(os.path.join(anno_dir, 'gene.taxonomy.csv'), dtype=str)
    if 'GeneID' not in gene_tax_raw.columns:
        raise ValueError('gene.taxonomy.csv 缺少 GeneID 列')
    if gene_tax_raw['GeneID'].isna().any() or gene_tax_raw['GeneID'].duplicated().any():
        raise ValueError('gene.taxonomy.csv 的 GeneID 含空值或重复值')
    taxonomy_cols = [c for c in gene_tax_raw.columns if c != 'GeneID']
    gene_tax = gene_tax_raw[['GeneID']].copy()
    gene_tax['taxonomy'] = gene_tax_raw[taxonomy_cols].fillna('').astype(str).agg(';'.join, axis=1)

    gene_tpm = pd.read_csv(os.path.join(bowtie, 'gene_tpm.csv'), dtype={'GeneID': str})
    if 'GeneID' not in gene_tpm.columns:
        raise ValueError('gene_tpm.csv 缺少 GeneID 列')
    if gene_tpm['GeneID'].isna().any() or gene_tpm['GeneID'].duplicated().any():
        raise ValueError('gene_tpm.csv 的 GeneID 含空值或重复值')
    sample_cols = [c for c in gene_tpm.columns if c != 'GeneID']

    cog = read_diamond_table(os.path.join(cog_dir, 'COG_anno.txt'))
    if cog.empty:
        log.warning('COG DIAMOND 无命中，输出带标准表头的空结果。')
        write_empty_outputs(cog_dir, sample_cols)
        return

    cog = cog.loc[:, ['qseqid', 'sseqid', 'evalue']]
    cog = cog.loc[cog.groupby('qseqid')['evalue'].idxmin()]
    # 提取蛋白ID：处理 piped (UniRef|protID) 和 plain (WP_xxx) 两种格式
    mask = cog['sseqid'].str.contains('|', regex=False)
    cog['protein_id'] = cog['sseqid'].where(~mask, cog['sseqid'].str.split('|').str[1])
    cog['protein_id'] = cog['protein_id'].astype(str)
    cog_map['protein_id'] = cog_map['protein_id'].astype(str)
    cog_ano = pd.merge(left=cog, right=cog_map, on='protein_id', how='left')
    cog_ano = cog_ano.loc[:, ['qseqid', 'COG']].rename(columns={'qseqid': 'GeneID'})
    cog_ano = cog_ano.dropna(subset=['COG'])
    if cog_ano.empty:
        raise ValueError(
            'COG DIAMOND 有命中，但没有任何 subject ID 可映射到 cog2003-2014.csv；'
            '请检查数据库与映射表版本。'
        )
    check_tpm_overlap(cog_ano['GeneID'], gene_tpm['GeneID'], 'COG 命中')
    gene_cog_tpm = pd.merge(left=cog_ano, right=gene_tpm, on='GeneID')
    gene_cog_tpm = add_optional_taxonomy(gene_cog_tpm, gene_tax, 'COG TPM 结果')
    gene_cog_tpm = gene_cog_tpm.loc[:, ['GeneID', 'taxonomy', 'COG'] + sample_cols]
    gene_cog_tpm.to_csv(os.path.join(cog_dir, 'COG.tpm.csv'), index=False, encoding='utf-8-sig')

    cog_cat = gene_cog_tpm.groupby('COG', dropna=True)[sample_cols].sum()
    cog_cat.to_excel(os.path.join(cog_dir, 'COG.Category.tpm.xlsx'), index=True)


def main():
    parser = argparse.ArgumentParser(description='COG 数据库注释（diamond）')
    parser.add_argument('--Annotation', type=str, default='Annotation', help='Annotation 结果目录')
    parser.add_argument('--COGdir', type=str, default='COG', help='COG 输出目录')
    parser.add_argument('--prodigal', type=str, default='prodigal', help='prodigal 结果目录')
    parser.add_argument('--dbdir', type=str, default='/data/data1/wangli/database', help='数据库目录')
    parser.add_argument('--bowtie', type=str, default='bowtie', help='bowtie 结果目录（含 gene_tpm.csv）')
    args = parser.parse_args()

    anno_dir = os.path.abspath(args.Annotation)
    prodigal_dir = os.path.abspath(args.prodigal)
    cog_dir = os.path.abspath(args.COGdir)
    dbdir = os.path.abspath(args.dbdir)
    bowtie = os.path.abspath(args.bowtie)

    os.makedirs(cog_dir, exist_ok=True)

    try:
        log.info('开始 COG diamond 比对')
        cog_diamond(dbdir, prodigal_dir, cog_dir)
        log.info('开始生成 COG 丰度表')
        get_cog_table(dbdir, cog_dir, anno_dir, bowtie)
        log.info('COG 注释完成，输出: %s', cog_dir)
    except Exception as e:
        log.error('COG 注释失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
