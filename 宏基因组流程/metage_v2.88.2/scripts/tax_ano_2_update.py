#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
tax_anno step2 优化版：整合物种注释与基因丰度表。

优化点：
1. 参数化所有输入/输出路径。
2. 修复原代码未调用 get_class_exp 的 bug：现在会生成 bacteria/Archaea/Fungi/Virus 各分类层级的 tpm/relative Excel。
3. 使用 pandas 高效 merge，避免重复 I/O。
4. 统一日志、运行时间统计、失败即停。
5. 自动创建输出目录，支持 --force 清空旧结果。
"""

import os
import sys
import time
import argparse
import shutil
import pandas as pd


def log(msg):
    """打印带时间戳的日志。"""
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def get_class_exp(bacteria_tpm, bacteria_rel, tax_dir):
    """按分类层级（kingdom ~ species）汇总 tpm 和 relative 丰度表。"""
    for i in range(1, 8):
        name = bacteria_tpm.columns[i]
        bacta_tax_tpm = bacteria_tpm.iloc[:, [i] + list(range(8, len(bacteria_tpm.columns)))]
        bacta_tax_tpm = bacta_tax_tpm.groupby(by=name).sum()
        bacta_tax_rela = bacteria_rel.iloc[:, [i] + list(range(8, len(bacteria_rel.columns)))]
        bacta_tax_rela = bacta_tax_rela.groupby(by=name).sum()
        out_xlsx = os.path.join(tax_dir, f"{name}.xlsx")
        with pd.ExcelWriter(out_xlsx) as writer:
            bacta_tax_tpm.to_excel(writer, sheet_name='tpm', index=True)
            bacta_tax_rela.to_excel(writer, sheet_name='relative', index=True)
        log(f"  已生成: {out_xlsx}")


def tax_table(anno_dir, dbdir, bowtie, tax_anno):
    """生成物种注释整合表与各域/层级汇总表。"""
    tax_id_path = os.path.join(tax_anno, 'Tax_id.tmp.txt')
    tax_map_path = os.path.join(dbdir, 'metage.taxonomy.txt')
    gene_tpm_path = os.path.join(bowtie, 'gene_tpm.csv')

    log(f"读取物种注释: {tax_id_path}")
    taxid = pd.read_csv(tax_id_path, sep='\t', dtype=str)

    log(f"读取物种层级表: {tax_map_path}")
    tax_ano = pd.read_csv(tax_map_path, sep='\t', dtype=str)

    log("合并生成 gene.taxonomy.csv")
    gene2tax = pd.merge(left=taxid, right=tax_ano, on='taxid')
    gene2tax = gene2tax.drop(['taxid'], axis=1)
    gene_taxonomy_path = os.path.join(anno_dir, 'gene.taxonomy.csv')
    gene2tax.to_csv(gene_taxonomy_path, index=False, encoding='utf-8-sig')
    log(f"  已生成: {gene_taxonomy_path}")

    tax_cla = ['All', 'bacteria', 'Archaea', 'Fungi', 'Virus']
    for cla in tax_cla:
        tax_dir = os.path.join(anno_dir, cla)
        os.makedirs(tax_dir, exist_ok=True)

    log(f"读取基因丰度表: {gene_tpm_path}")
    gene_tpm = pd.read_csv(gene_tpm_path, dtype={'GeneID': str})
    if 'GeneID' not in gene_tpm.columns:
        raise ValueError(f"gene_tpm.csv 缺少 GeneID 列: {gene_tpm_path}")

    gene2tax['GeneID'] = gene2tax['GeneID'].astype(str)
    gene_tpm['GeneID'] = gene_tpm['GeneID'].astype(str)
    tax_ids = set(gene2tax['GeneID'])
    tpm_ids = set(gene_tpm['GeneID'])
    overlap_ids = tax_ids & tpm_ids
    overlap_ratio = len(overlap_ids) / max(1, min(len(tax_ids), len(tpm_ids)))
    log(
        "GeneID 一致性: taxonomy=%d, abundance=%d, overlap=%d, ratio=%.2f%%"
        % (len(tax_ids), len(tpm_ids), len(overlap_ids), overlap_ratio * 100)
    )
    if tax_ids and tpm_ids and (not overlap_ids or overlap_ratio < 0.01):
        tax_example = next(iter(tax_ids), '')
        tpm_example = next(iter(tpm_ids), '')
        raise ValueError(
            "taxonomy 与 gene_tpm 的 GeneID 交集异常低，可能存在字符编码或 ID 格式错误。"
            f" taxonomy示例={tax_example!r}, abundance示例={tpm_example!r}"
        )

    log("合并基因丰度与物种注释")
    all_tpm = pd.merge(left=gene2tax, right=gene_tpm, on='GeneID')
    if all_tpm.empty and not gene2tax.empty and not gene_tpm.empty:
        raise ValueError("物种注释与丰度表合并后为 0 行，请检查 GeneID 编码和格式。")

    sample_cols = [c for c in gene_tpm.columns if c != 'GeneID']

    log("生成 All/All.taxonomy.csv 和 All/All.taxonomy.rel.csv")
    all_rel = all_tpm[sample_cols].div(all_tpm[sample_cols].sum())
    all_rel = pd.concat([all_tpm.iloc[:, :8], all_rel], axis=1)
    all_tpm.to_csv(os.path.join(anno_dir, 'All', 'All.taxonomy.csv'), index=False, encoding='utf-8-sig')
    all_rel.to_csv(os.path.join(anno_dir, 'All', 'All.taxonomy.rel.csv'), index=False, encoding='utf-8-sig')
    log("  已生成 All 层级表")

    # 按域过滤并生成各级汇总表
    domain_filters = {
        'bacteria': lambda df: df['kingdom'].str.lower() == 'k__bacteria',
        'Archaea': lambda df: df['kingdom'].str.lower() == 'k__archaea',
        'Virus': lambda df: df['kingdom'].str.lower() == 'k__viruses',
        # Fungi 属于 Eukaryota，这里按 phylum 包含 Fungi 或常见真菌门进行过滤
        'Fungi': lambda df: (
            (df['kingdom'].str.lower() == 'k__eukaryota') &
            (df['phylum'].str.lower().str.contains('fungi|ascomycota|basidiomycota|chytridiomycota|zygomycota|mucoromycota|glomeromycota'))
        ),
    }

    for cla, mask_func in domain_filters.items():
        tax_dir = os.path.join(anno_dir, cla)
        mask = mask_func(all_tpm)
        subset = all_tpm[mask]
        if subset.empty:
            log(f"  警告: {cla} 无匹配记录，跳过")
            continue
        log(f"生成 {cla} 各层级汇总表 ({len(subset)} 条记录)")
        subset_rel = pd.concat([subset.iloc[:, :8], subset[sample_cols].div(subset[sample_cols].sum())], axis=1)
        get_class_exp(subset, subset_rel, tax_dir)


def main():
    parser = argparse.ArgumentParser(
        description='Optimized tax_anno step2: integrate taxonomy annotation with gene abundance.'
    )
    parser.add_argument('--Annotation', type=str, default='Annotation',
                        help='Output directory for integrated annotation results')
    parser.add_argument('--dbdir', type=str, default='/data/data1/wangli/database/NR',
                        help='Directory containing NR database (metage.taxonomy.txt)')
    parser.add_argument('--bowtie', type=str, default='bowtie',
                        help='Directory containing gene_tpm.csv')
    parser.add_argument('--tax_anno', type=str, default='Annotation',
                        help='Directory containing Tax_id.tmp.txt from tax_anno')
    parser.add_argument('--force', action='store_true',
                        help='Remove existing output directory before running')
    args = parser.parse_args()

    anno_dir = os.path.abspath(args.Annotation)
    dbdir = os.path.abspath(args.dbdir)
    bowtie = os.path.abspath(args.bowtie)
    tax_anno = os.path.abspath(args.tax_anno)

    start_time = time.time()
    log("=" * 60)
    log("tax_ano_2_update.py 开始运行")
    log("=" * 60)

    # 输入检查
    for p, label in [(tax_anno, 'tax_anno'), (dbdir, 'dbdir'), (bowtie, 'bowtie')]:
        if not os.path.exists(p):
            log(f"错误: {label} 目录不存在: {p}")
            sys.exit(1)

    required_files = [
        (os.path.join(tax_anno, 'Tax_id.tmp.txt'), 'Tax_id.tmp.txt'),
        (os.path.join(dbdir, 'metage.taxonomy.txt'), 'metage.taxonomy.txt'),
        (os.path.join(bowtie, 'gene_tpm.csv'), 'gene_tpm.csv'),
    ]
    for fp, label in required_files:
        if not os.path.exists(fp):
            log(f"错误: 缺少输入文件 {label}: {fp}")
            sys.exit(1)

    if args.force and os.path.exists(anno_dir):
        log(f"--force 已启用，清空旧输出: {anno_dir}")
        shutil.rmtree(anno_dir)
    os.makedirs(anno_dir, exist_ok=True)

    try:
        tax_table(anno_dir, dbdir, bowtie, tax_anno)
    except Exception as e:
        log(f"错误: tax_table 运行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    elapsed = time.time() - start_time
    log("=" * 60)
    log(f"tax_ano_2_update.py 运行完成，总耗时: {elapsed:.3f} 秒 ({elapsed/60:.2f} 分钟)")
    log(f"输出目录: {anno_dir}")
    log("=" * 60)


if __name__ == '__main__':
    main()
