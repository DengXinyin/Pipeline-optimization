#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
kraken2_stats_update.py

将 kraken2 + bracken 的物种注释结果整合成与现有 MEGAN-based
species annotation 兼容的丰度表格式，便于复用 tax_stats_update.py、
tax_diff_update.py、tax_PCOA 等下游脚本。

输入：
    - kraken2_out/          # kraken2_anno_update.py 输出
    - sample.txt / sample-metadata.tsv
输出：
    - kraken2_taxonomy/
        All/All.taxonomy.csv
        gene.taxonomy.csv
        以及按分组聚合的 group*/5-TaxAnnotation/1.Tables/...
"""

import os
import re
import sys
import argparse
import logging
import subprocess
import pandas as pd
from collections import defaultdict

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

RANK_MAP = {
    'D': 'kingdom',      # superkingdom (Bacteria, Archaea, Eukaryota)
    'K': 'kingdom',
    'P': 'phylum',
    'C': 'class',
    'O': 'order',
    'F': 'family',
    'G': 'genus',
    'S': 'species',
}

TAX_PREFIX = {
    'kingdom': 'k__',
    'phylum': 'p__',
    'class': 'c__',
    'order': 'o__',
    'family': 'f__',
    'genus': 'g__',
    'species': 's__',
}


def run_cmd(cmd):
    log.info('执行: %s', cmd[:200])
    subprocess.run(cmd, shell=True, check=True)


def parse_kraken_report(report_path):
    """
    解析 kraken2 report，返回 taxid -> {rank, name, parent_taxid} 的 dict。
    利用缩进推断层级关系。
    """
    nodes = {}
    stack = []  # [(depth, taxid), ...]
    with open(report_path, 'r') as f:
        for line in f:
            if not line.strip():
                continue
            # 前 5 列是固定宽度/空格分隔的；第 6 列起是 name（含前导空格）
            parts = line.rstrip('\n').split('\t')
            if len(parts) >= 6:
                # 以 name 字段的原始前导空格数作为深度
                name_field = parts[5]
            else:
                #  fallback：按空格分割
                fields = line.rstrip('\n').split(' ')
                # 找到第一个非空字段作为 rank code 的位置？较复杂
                continue

            depth = len(name_field) - len(name_field.lstrip())
            name = name_field.strip()
            rank_code = parts[3].strip()
            taxid = parts[4].strip()
            rank = RANK_MAP.get(rank_code, rank_code)

            nodes[taxid] = {'rank': rank, 'name': name, 'parent': None}

            # 维护 stack：弹出比当前深度大的节点
            while stack and stack[-1][0] >= depth:
                stack.pop()
            if stack:
                nodes[taxid]['parent'] = stack[-1][1]
            stack.append((depth, taxid))

    return nodes


def build_lineage(nodes, taxid):
    """根据 parent 关系，生成完整 7 级 lineage。"""
    lineage = {k: 'Unclassified' for k in TAX_PREFIX}
    lineage['taxid'] = taxid
    current = taxid
    visited = set()
    while current and current in nodes and current not in visited:
        visited.add(current)
        node = nodes[current]
        rank = node['rank']
        if rank in TAX_PREFIX:
            lineage[rank] = node['name']
        current = node['parent']
    return lineage


def parse_bracken_output(bracken_file):
    """读取 bracken S-level 输出，返回 {taxid: new_est_reads}。"""
    df = pd.read_csv(bracken_file, sep='\t')
    # 列：name, taxonomy_id, taxonomy_lvl, kraken_assigned_reads, added_reads, new_est_reads, fraction_total_reads
    if 'taxonomy_id' not in df.columns or 'new_est_reads' not in df.columns:
        log.warning('bracken 文件列名异常: %s', bracken_file)
        return {}
    return dict(zip(df['taxonomy_id'].astype(str), df['new_est_reads'].astype(float)))


def build_taxid_lineage_map(kraken_report_paths):
    """合并多个样本的 kraken2 report，构建全局 taxid -> lineage。"""
    all_nodes = {}
    for report in kraken_report_paths:
        nodes = parse_kraken_report(report)
        all_nodes.update(nodes)

    lineage_map = {}
    for taxid in all_nodes:
        lineage_map[taxid] = build_lineage(all_nodes, taxid)
    return lineage_map


def read_sample_txt(sample_txt):
    """返回样本名列表。"""
    df = pd.read_csv(sample_txt, sep='\t')
    cols = [c.strip().lower() for c in df.columns]
    if 'sample' in cols:
        return df.iloc[:, cols.index('sample')].astype(str).tolist()
    return df.iloc[:, 1].astype(str).tolist()


def combine_bracken_to_table(kraken_outdir, samples, level='S'):
    """
    合并所有样本的 bracken 输出为 species x samples 的 DataFrame。
    同时收集每个样本的 kraken2 report 路径用于构建 lineage。
    """
    sample_values = {}
    kraken_reports = []
    missing = []

    for sample in samples:
        sample_dir = os.path.join(kraken_outdir, sample)
        bracken_file = os.path.join(sample_dir, '{}.{}.bracken.txt'.format(sample, level))
        report_file = os.path.join(sample_dir, '{}.kreport2.txt'.format(sample))

        if not os.path.exists(bracken_file):
            missing.append(sample)
            continue
        if os.path.exists(report_file):
            kraken_reports.append(report_file)

        sample_values[sample] = parse_bracken_output(bracken_file)

    if missing:
        log.warning('缺少 %d 个样本的 bracken 输出: %s', len(missing), missing[:5])
    if not sample_values:
        raise RuntimeError(
            '没有找到任何 Bracken {} 层级输出；请检查上游读长与数据库 distribution 是否匹配'.format(level)
        )

    # 构建全局 lineage
    lineage_map = build_taxid_lineage_map(kraken_reports)

    # 合并所有 taxid
    all_taxids = set()
    for vals in sample_values.values():
        all_taxids.update(vals.keys())

    rows = []
    for taxid in all_taxids:
        lineage = lineage_map.get(taxid, build_lineage({}, taxid))
        row = {'GeneID': 'gene_{}'.format(taxid)}
        for rank, prefix in TAX_PREFIX.items():
            val = lineage.get(rank, 'Unclassified')
            if val == 'Unclassified':
                row[rank] = prefix + 'Unclassified'
            else:
                row[rank] = prefix + val
        for sample in samples:
            row[sample] = sample_values.get(sample, {}).get(taxid, 0.0)
        rows.append(row)

    df = pd.DataFrame(rows)
    # 排序：先按分类层级，再按样本均值
    sample_cols = [c for c in df.columns if c not in ['GeneID'] + list(TAX_PREFIX.keys())]
    if sample_cols:
        df['__mean'] = df[sample_cols].sum(axis=1)
        df = df.sort_values(by=['kingdom', '__mean'], ascending=[True, False])
        df = df.drop('__mean', axis=1)

    col_order = ['GeneID'] + list(TAX_PREFIX.keys()) + sample_cols
    return df[col_order]


def write_outputs(df, outdir):
    """写出 All.taxonomy.csv 和 gene.taxonomy.csv。"""
    os.makedirs(os.path.join(outdir, 'All'), exist_ok=True)
    all_csv = os.path.join(outdir, 'All', 'All.taxonomy.csv')
    df.to_csv(all_csv, index=False, encoding='utf-8-sig')

    gene_csv = os.path.join(outdir, 'gene.taxonomy.csv')
    df.to_csv(gene_csv, index=False, encoding='utf-8-sig')
    log.info('写出 kraken2 物种丰度表: %s', all_csv)


def generate_group_tables(df, datadir, res_dir):
    """
    调用现有的 tax_stats_update.py 逻辑，按 sample-metadata.tsv 中的分组
    生成 group*/5-TaxAnnotation/1.Tables 和 2.Krona。
    """
    metadata = os.path.join(datadir, 'sample-metadata.tsv')
    if not os.path.exists(metadata):
        log.warning('sample-metadata.tsv 不存在，跳过分组表生成')
        return

    # 复用 tax_stats_update.py 完成分组表、Krona 等
    from tax_stats_update import get_table, krona
    try:
        get_table(outdir=res_dir, datadir=datadir, res_dir=res_dir)
        krona(res_dir=res_dir, anno_dir=outdir, datadir=datadir)
    except Exception as e:
        log.warning('生成分组表/Krona 失败: %s', e)


def main():
    parser = argparse.ArgumentParser(description='kraken2/bracken 结果统计为丰度表')
    parser.add_argument('-I', '--i_datadir', type=str, required=True,
                        help='包含 sample.txt / sample-metadata.tsv 的目录')
    parser.add_argument('--kraken2_out', type=str, required=True,
                        help='kraken2_anno_update.py 的输出目录')
    parser.add_argument('--resdir', type=str, default='Result',
                        help='结果输出目录（将生成 kraken2_taxonomy 子目录）')
    parser.add_argument('--level', type=str, default='S',
                        help='bracken 层级，默认 S（Species）')
    args = parser.parse_args()

    datadir = os.path.abspath(args.i_datadir)
    kraken_outdir = os.path.abspath(args.kraken2_out)
    res_dir = os.path.abspath(args.resdir)
    outdir = os.path.join(res_dir, 'kraken2_taxonomy')
    os.makedirs(outdir, exist_ok=True)

    sample_txt = os.path.join(datadir, 'sample.txt')
    if not os.path.exists(sample_txt):
        log.error('sample.txt 不存在: %s', sample_txt)
        sys.exit(1)

    samples = read_sample_txt(sample_txt)
    df = combine_bracken_to_table(kraken_outdir, samples, level=args.level)
    write_outputs(df, outdir)

    # 用 tax_stats_update.py 生成下游分组表和 Krona
    # 注意：需要把 kraken2_taxonomy 当作 Annotation 目录传进去
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from tax_stats_update import get_table, krona
        get_table(anno_dir=outdir, datadir=datadir, res_dir=res_dir)
        krona(res_dir=res_dir, anno_dir=outdir, datadir=datadir)
    except Exception as e:
        log.warning('调用 tax_stats_update 生成分组表/Krona 失败: %s', e)

    log.info('kraken2 统计完成，输出目录: %s', outdir)


if __name__ == '__main__':
    main()
