#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
COG-24 功能注释（standalone 版）

1. 用 diamond blastp 将 unique_gene.fasta 比对到 COGorg24.faa
2. 取最佳命中，通过 cog-24.cog.csv 映射到 COG ID
3. 结合 cog-24.def.tab / cog-24.fun.tab 输出注释表

输出：
    cog.diamond.tsv       diamond 原始比对结果（fmt6）
    cog.annotations.tsv   GeneID -> COG 注释
    cog.summary.tsv       各 COG 命中数统计
"""

import os
import sys
import argparse
import logging
import subprocess
import gzip
import shutil

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)


DIAMOND_FMT = '6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore'
DIAMOND_COLS = ['qseqid', 'sseqid', 'pident', 'length', 'mismatch', 'gapopen',
                'qstart', 'qend', 'sstart', 'send', 'evalue', 'bitscore']


def run_diamond(query, db, out_tsv, cpu=16, evalue='1e-5', max_targets=1,
                query_cover=50, subject_cover=50, sensmode='fast', blastx=False):
    """运行 diamond blastp/blastx。"""
    mode = 'blastx' if blastx else 'blastp'
    cmd = [
        'diamond', mode,
        '--db', db,
        '--query', query,
        '--out', out_tsv,
        '--outfmt', '6', 'qseqid', 'sseqid', 'pident', 'length', 'mismatch',
        'gapopen', 'qstart', 'qend', 'sstart', 'send', 'evalue', 'bitscore',
        '--evalue', str(evalue),
        '--max-target-seqs', str(max_targets),
        '--threads', str(cpu),
        '--query-cover', str(query_cover),
        '--subject-cover', str(subject_cover),
        '--' + sensmode,
    ]
    log.info('[CMD] %s', ' '.join(cmd))
    subprocess.run(cmd, check=True)


def load_cog_mapping(cog_csv):
    """读取 cog-24.cog.csv，建立 protein_id -> COG 映射。"""
    log.info('加载 COG mapping: %s', cog_csv)
    # 只读第 3 列（protein_id, 0-based index 2）和第 7 列（COG, index 6）
    df = pd.read_csv(
        cog_csv, header=None, usecols=[2, 6],
        names=['protein_id', 'COG'], dtype=str
    )
    mapping = df.drop_duplicates()
    log.info('COG mapping 行数: %d', len(mapping))
    return mapping


def load_cog_def(cog_def):
    """读取 cog-24.def.tab，获取 COG 描述和 category。"""
    log.info('加载 COG definition: %s', cog_def)
    df = pd.read_csv(cog_def, sep='\t', header=None, names=[
        'COG', 'category', 'description', 'gene_name', 'pathway',
        'pubmed_ids', 'pdb_ids'
    ], dtype=str)
    return df[['COG', 'category', 'description']]


def load_cog_fun(cog_fun):
    """读取 cog-24.fun.tab，获取 category -> 功能组/描述。"""
    log.info('加载 COG function table: %s', cog_fun)
    # 第一行是组标题，后面是 category 行
    rows = []
    with open(cog_fun, 'r') as f:
        current_group = None
        current_group_desc = None
        for line in f:
            line = line.rstrip('\n')
            if not line.strip():
                continue
            parts = line.split('\t')
            if len(parts) == 2 and parts[0].isdigit():
                # 功能大组，如 "1\tINFORMATION STORAGE AND PROCESSING"
                current_group = parts[0]
                current_group_desc = parts[1]
            elif len(parts) >= 4:
                # category 行: J\t1\tFCCCFC\tTranslation, ...
                rows.append({
                    'category': parts[0],
                    'function_group': current_group,
                    'function_group_description': current_group_desc,
                    'color': parts[2],
                    'category_description': parts[3]
                })
    return pd.DataFrame(rows)


def annotate(diamond_tsv, cog_csv, cog_def, cog_fun, out_annotations, out_summary):
    """将 diamond 结果与 COG 注释表合并。"""
    mapping = load_cog_mapping(cog_csv)
    cog_def_df = load_cog_def(cog_def)
    cog_fun_df = load_cog_fun(cog_fun)

    log.info('读取 diamond 结果: %s', diamond_tsv)
    diamond = pd.read_csv(diamond_tsv, sep='\t', header=None, names=DIAMOND_COLS)

    # 蛋白 ID -> COG
    annotated = pd.merge(diamond, mapping, left_on='sseqid', right_on='protein_id', how='left')
    annotated = annotated.drop(columns=['protein_id'])

    # COG -> 描述 + category（category 可能是多字母，如 JV）
    annotated = pd.merge(annotated, cog_def_df, on='COG', how='left')

    # 为每个 category 字母拆行，并合并功能描述（用于 category 级统计）
    cog_fun_df = cog_fun_df.rename(columns={'category': 'category_letter'})
    annotated_exp = annotated.copy()
    # 空/缺失 category 保持 NaN，避免拆成 'n','a','n'
    annotated_exp['_cat_letter'] = annotated_exp['category'].where(annotated_exp['category'].notna(), other=None)
    annotated_exp['_cat_letter'] = annotated_exp['_cat_letter'].apply(
        lambda x: list(x) if pd.notna(x) and x != '' else [None]
    )
    annotated_exp = annotated_exp.explode('_cat_letter')
    annotated_exp = pd.merge(annotated_exp, cog_fun_df, left_on='_cat_letter', right_on='category_letter', how='left')
    # 保留单字母 category 便于统计
    annotated_exp['category_letter'] = annotated_exp['_cat_letter']
    annotated_exp = annotated_exp.drop(columns=['_cat_letter'])

    # 保存原始注释表（保留所有 diamond 列，category 已拆行）
    annotated_exp.to_csv(out_annotations, sep='\t', index=False, encoding='utf-8-sig')
    log.info('写入注释表: %s (%d rows)', out_annotations, len(annotated_exp))

    # 生成 GeneID -> 最佳 COG 的简化表（按 category 字母拆行）
    gene_cog = annotated_exp[['qseqid', 'COG', 'category', 'category_letter',
                              'description', 'category_description', 'function_group',
                              'function_group_description', 'evalue', 'bitscore']].copy()
    gene_cog = gene_cog.rename(columns={'qseqid': 'GeneID'})
    gene_cog['evalue'] = gene_cog['evalue'].apply(lambda x: f'{x:.2e}' if pd.notna(x) else '')
    gene_cog = gene_cog.sort_values(['GeneID', 'bitscore'], ascending=[True, False])
    simple_out = out_annotations.replace('.annotations.tsv', '.gene2cog.tsv')
    gene_cog.to_csv(simple_out, sep='\t', index=False, encoding='utf-8-sig')
    log.info('写入 GeneID->COG 简表: %s (%d rows)', simple_out, len(gene_cog))

    # 汇总统计（按 COG，不拆 category）
    summary = annotated.groupby('COG').agg(
        hit_count=('qseqid', 'nunique'),
        category=('category', 'first'),
        description=('description', 'first'),
    ).reset_index().sort_values('hit_count', ascending=False)
    # 合并功能描述（多个 category 字母时取第一个可用的）
    summary = pd.merge(summary, cog_fun_df, left_on='category', right_on='category_letter', how='left')
    summary = summary.drop(columns=['category_letter'])
    summary.to_csv(out_summary, sep='\t', index=False, encoding='utf-8-sig')
    log.info('写入汇总表: %s', out_summary)

    total_genes = gene_cog['GeneID'].nunique()
    annotated_genes = gene_cog[gene_cog['COG'].notna()]['GeneID'].nunique()
    log.info('注释统计: %d / %d 基因获得 COG 注释 (%.2f%%)',
             annotated_genes, total_genes,
             annotated_genes / total_genes * 100 if total_genes else 0)


def main():
    parser = argparse.ArgumentParser(description='COG-24 annotation using diamond')
    parser.add_argument('--prodigal', required=True, help='Directory containing unique_gene.fasta')
    parser.add_argument('--dbdir', required=True, help='Directory containing COGorg24.dmnd and COG .tab/.csv files')
    parser.add_argument('--outdir', default='COG', help='Output directory')
    parser.add_argument('--cpu', type=int, default=16, help='Threads for diamond')
    parser.add_argument('--evalue', default='1e-5', help='E-value threshold')
    parser.add_argument('--max-target-seqs', type=int, default=1, help='Max target seqs per query')
    parser.add_argument('--query-cover', type=int, default=50, help='Minimum query cover %')
    parser.add_argument('--subject-cover', type=int, default=50, help='Minimum subject cover %')
    parser.add_argument('--sensmode', default='fast', choices=['fast', 'mid-sensitive', 'sensitive', 'more-sensitive', 'very-sensitive', 'ultra-sensitive'],
                        help='Diamond sensitivity mode')
    parser.add_argument('--blastx', action='store_true', help='Input is nucleotide (use diamond blastx instead of blastp)')
    parser.add_argument('--skip-diamond', action='store_true', help='Skip diamond, only annotate existing cog.diamond.tsv')
    args = parser.parse_args()

    prodigal_dir = os.path.abspath(args.prodigal)
    dbdir = os.path.abspath(args.dbdir)
    outdir = os.path.abspath(args.outdir)
    os.makedirs(outdir, exist_ok=True)

    query_fasta = os.path.join(prodigal_dir, 'unique_gene.fasta')
    if not args.skip_diamond and not os.path.exists(query_fasta):
        log.error('找不到输入文件: %s', query_fasta)
        sys.exit(1)

    dmnd = os.path.join(dbdir, 'COGorg24.dmnd')
    if not args.skip_diamond and not os.path.exists(dmnd):
        log.error('找不到 diamond 数据库: %s', dmnd)
        sys.exit(1)

    required_files = {
        'cog-24.cog.csv': os.path.join(dbdir, 'cog-24.cog.csv'),
        'cog-24.def.tab': os.path.join(dbdir, 'cog-24.def.tab'),
        'cog-24.fun.tab': os.path.join(dbdir, 'cog-24.fun.tab'),
    }
    for label, path in required_files.items():
        if not os.path.exists(path):
            log.error('找不到 %s: %s', label, path)
            sys.exit(1)

    diamond_tsv = os.path.join(outdir, 'cog.diamond.tsv')
    out_annotations = os.path.join(outdir, 'cog.annotations.tsv')
    out_summary = os.path.join(outdir, 'cog.summary.tsv')

    if not args.skip_diamond:
        run_diamond(query_fasta, dmnd, diamond_tsv, cpu=args.cpu, evalue=args.evalue,
                    max_targets=args.max_target_seqs, query_cover=args.query_cover,
                    subject_cover=args.subject_cover, sensmode=args.sensmode, blastx=args.blastx)
    else:
        if not os.path.exists(diamond_tsv):
            log.error('--skip-diamond 已设置，但找不到 %s', diamond_tsv)
            sys.exit(1)

    annotate(diamond_tsv, required_files['cog-24.cog.csv'],
             required_files['cog-24.def.tab'], required_files['cog-24.fun.tab'],
             out_annotations, out_summary)

    log.info('COG 注释完成，输出目录: %s', outdir)


if __name__ == '__main__':
    main()
