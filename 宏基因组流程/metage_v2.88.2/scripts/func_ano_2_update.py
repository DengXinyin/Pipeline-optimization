#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
func_anno step2 优化版：整合功能注释与基因丰度表。

优化点：
1. 参数化所有输入/输出路径。
2. eggNOG / KEGG / CAZy / GO 四类注释数据独立，使用多进程并行执行。
3. 减少重复 I/O：gene_tpm 和 func.emapper.annotations 只读取一次。
4. 统一日志、运行时间统计、失败即停。
5. 自动创建输出目录，支持 --force 清空旧结果。
"""

import os
import sys
import time
import argparse
import shutil
import multiprocessing as mp
import pandas as pd


def log(msg):
    """打印带时间戳的日志。"""
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def _prepare_output_dirs(anno_dir):
    """创建 eggNOG / KEGG / CAZy / GO 输出目录。"""
    for cla in ['eggNOG', 'KEGG', 'CAZy', 'GO']:
        os.makedirs(os.path.join(anno_dir, cla), exist_ok=True)


def _run_task(task):
    """供 multiprocessing.Pool 调用的任务包装函数。"""
    func, args = task
    return func(args)


def annotate_eggNOG(args_tuple):
    """eggNOG 注释与丰度汇总。"""
    anno_dir, mapdir, gene_tpm, ano_all = args_tuple
    log("开始 eggNOG 注释")

    cog = pd.read_csv(os.path.join(mapdir, 'eggNOG', 'cognames2003-2014.tab'), sep='\t')
    cogname = pd.read_csv(os.path.join(mapdir, 'eggNOG', 'cogfun2003-2014.tab'), sep='\t')
    kog = pd.read_excel(os.path.join(mapdir, 'eggNOG', 'kog_name.xlsx'))

    eggNOG = ano_all.loc[:, ['GeneID', 'eggNOG']].copy()
    eggNOG['eggNOG'] = eggNOG['eggNOG'].str.split(',').str[0]
    eggNOG['eggNOG'] = eggNOG['eggNOG'].str.split('@').str[0]

    eggNOG_COG_ano = pd.merge(left=eggNOG, right=cog, left_on='eggNOG', right_on='COG')
    eggNOG_COG_ano = pd.merge(left=eggNOG_COG_ano, right=cogname, left_on='category', right_on='category')
    eggNOG_COG_ano = eggNOG_COG_ano.loc[:, ['GeneID', 'eggNOG', 'description', 'category', 'category_description']]
    eggNOG_kOG_ano = pd.merge(left=eggNOG, right=kog, left_on='eggNOG', right_on='kog_ID')
    eggNOG_kOG_ano = eggNOG_kOG_ano.loc[:, ['GeneID', 'eggNOG', 'description', 'category', 'category_description']]

    eggNOG_ano = pd.concat([eggNOG_COG_ano, eggNOG_kOG_ano], axis=0).reset_index(drop=True)

    eggNOG_tpm = pd.merge(left=eggNOG_ano, right=gene_tpm, on='GeneID')
    eggNOG_tpm.to_csv(os.path.join(anno_dir, 'eggNOG', 'eggNOG.tpm.csv'), index=False, encoding='utf-8-sig')

    eggNOG_category = eggNOG_tpm.drop(['GeneID', 'eggNOG', 'description'], axis=1)
    eggNOG_category['category_description'] = eggNOG_category['category'].str.cat(
        eggNOG_category['category_description'], sep=':')
    eggNOG_category['category_description'] = eggNOG_category['category_description'].str.strip()
    eggNOG_category = eggNOG_category.drop(['category'], axis=1)
    eggNOG_category = eggNOG_category.groupby('category_description').sum()
    eggNOG_category.to_excel(os.path.join(anno_dir, 'eggNOG', 'eggNOG.Category.tpm.xlsx'), index=True)

    log("  eggNOG 注释完成")
    return 'eggNOG', len(eggNOG_tpm)


def annotate_KEGG(args_tuple):
    """KEGG 注释与丰度汇总。"""
    anno_dir, mapdir, gene_tpm, ano_all = args_tuple
    log("开始 KEGG 注释")

    ko_map = pd.read_excel(
        os.path.join(mapdir, 'KEGG', 'KO_map.xlsx'), engine='openpyxl'
    )
    kegg_level = pd.read_csv(os.path.join(mapdir, 'KEGG', 'kegg_level.txt'), sep='\t')

    # KO_map 中除关联键外的字段全部保留，并增加 KO_ 前缀，避免与
    # eggNOG-mapper 的 Description/Preferred_name 等列发生同名覆盖。
    ko_map_rename = {
        column: ('KO_' + str(column) if not str(column).startswith('KO_') else str(column))
        for column in ko_map.columns
        if column not in {'ko_ID', 'level3_pathway_ID'}
    }
    ko_map = ko_map.rename(columns=ko_map_rename)

    # 保留 eggNOG-mapper 提供的 KEGG/基因功能注释。后续一条基因可能
    # 对应多个 KO/pathway，因此这些 GeneID 级字段必须以 many-to-one
    # 方式并入，避免意外放大结果行数。
    kegg_info_cols = [
        'GeneID', 'Description', 'Preferred_name', 'EC',
        'KEGG_Pathway', 'KEGG_Module', 'KEGG_Reaction',
        'KEGG_rclass', 'BRITE', 'KEGG_TC',
    ]
    available_kegg_info_cols = [c for c in kegg_info_cols if c in ano_all.columns]
    gene_kegg_info = ano_all.loc[:, available_kegg_info_cols].copy()
    if gene_kegg_info['GeneID'].duplicated().any():
        raise ValueError('func.emapper.annotations 的 GeneID 存在重复，无法安全合并 KEGG 注释')

    ko = ano_all.loc[:, ['GeneID', 'KO']].copy()
    ko = ko[ko['KO'] != '-']
    ko['KO'] = ko['KO'].str.split(',')
    ko = ko.explode('KO').drop_duplicates()
    ko['KO'] = ko['KO'].str.split('ko:').str[1]

    ko_anno = pd.merge(left=ko, right=ko_map, left_on='KO', right_on='ko_ID')
    ko_anno = pd.merge(left=ko_anno, right=kegg_level, on='level3_pathway_ID')
    ko_anno = ko_anno.drop(['ko_ID'], axis=1)

    # gene.taxonomy.csv 由同一 anno task 的 tax_ano_2_update.py 先生成。
    # 报告只展示一列 taxonomy，不把 kingdom~species 拆成多列。
    taxonomy_path = os.path.join(anno_dir, 'gene.taxonomy.csv')
    gene_taxonomy = pd.read_csv(taxonomy_path, dtype=str)
    if 'GeneID' not in gene_taxonomy.columns:
        gene_taxonomy = gene_taxonomy.rename(columns={gene_taxonomy.columns[0]: 'GeneID'})
    if gene_taxonomy['GeneID'].duplicated().any():
        raise ValueError('gene.taxonomy.csv 的 GeneID 存在重复，无法安全合并 KEGG 注释')
    taxonomy_cols = [c for c in gene_taxonomy.columns if c != 'GeneID']
    gene_taxonomy['taxonomy'] = gene_taxonomy[taxonomy_cols].fillna('').apply(
        lambda row: ';'.join(str(value) for value in row if str(value).strip()), axis=1
    )
    gene_taxonomy = gene_taxonomy.loc[:, ['GeneID', 'taxonomy']]

    ko_anno = pd.merge(
        ko_anno, gene_taxonomy, on='GeneID', how='left', validate='many_to_one'
    )
    ko_anno = pd.merge(
        ko_anno, gene_kegg_info, on='GeneID', how='left', validate='many_to_one'
    )

    kegg_tpm = pd.merge(
        left=ko_anno, right=gene_tpm, on='GeneID', validate='many_to_one'
    )
    sample_cols = [c for c in gene_tpm.columns if c != 'GeneID']
    preferred_annotation_cols = [
        'GeneID', 'taxonomy', 'KO', 'Description', 'Preferred_name', 'EC',
        'KEGG_Pathway', 'KEGG_Module', 'KEGG_Reaction',
        'KEGG_rclass', 'BRITE', 'KEGG_TC',
        'level3_pathway_ID', 'level1_pathway_name',
        'level2_pathway_name', 'level3_pathway_name',
    ]
    annotation_cols = [c for c in preferred_annotation_cols if c in kegg_tpm.columns]
    # 保留 KO_map、kegg_level 或未来数据库版本新增的全部注释字段。
    annotation_cols += [
        c for c in kegg_tpm.columns
        if c not in sample_cols and c not in annotation_cols
    ]
    kegg_tpm = kegg_tpm.loc[:, annotation_cols + sample_cols]
    kegg_tpm.to_csv(os.path.join(anno_dir, 'KEGG', 'KEGG.tpm.csv'), index=False, encoding='utf-8-sig')

    kegg_l1 = kegg_tpm.loc[:, ['level1_pathway_name'] + sample_cols]
    kegg_l1 = kegg_l1.groupby('level1_pathway_name')[sample_cols].sum()
    kegg_l1.to_excel(os.path.join(anno_dir, 'KEGG', 'level1.tpm.xlsx'), index=True)

    kegg_l2 = kegg_tpm.loc[:, ['level2_pathway_name'] + sample_cols]
    kegg_l2 = kegg_l2.groupby('level2_pathway_name')[sample_cols].sum()
    kegg_l2.to_excel(os.path.join(anno_dir, 'KEGG', 'level2.tpm.xlsx'), index=True)

    kegg_l3 = kegg_tpm.loc[:, ['level3_pathway_ID', 'level3_pathway_name'] + sample_cols]
    kegg_l3 = kegg_l3.groupby(
        ['level3_pathway_ID', 'level3_pathway_name']
    )[sample_cols].sum()
    kegg_l3.to_excel(os.path.join(anno_dir, 'KEGG', 'level3.tpm.xlsx'), index=True)

    log("  KEGG 注释完成")
    return 'KEGG', len(kegg_tpm)


def annotate_CAZy(args_tuple):
    """CAZy 注释与丰度汇总。"""
    anno_dir, dbdir, gene_tpm, ano_all = args_tuple
    log("开始 CAZy 注释")

    CAZy_map = pd.read_csv(os.path.join(dbdir, 'CAZy', 'CAZy_map.tsv'), sep='\t')
    CAZy = ano_all.loc[:, ['GeneID', 'CAZy']].copy()
    CAZy = CAZy[CAZy['CAZy'] != '-']
    CAZy['CAZy'] = CAZy['CAZy'].str.split(',').str[0]
    CAZy_anno = pd.merge(left=CAZy, right=CAZy_map, on='CAZy')

    gene_CAZy_tpm = pd.merge(left=CAZy_anno, right=gene_tpm, on='GeneID')
    gene_CAZy_tpm.to_csv(os.path.join(anno_dir, 'CAZy', 'gene.CAZy.tpm.csv'), index=False, encoding='utf-8-sig')

    k = gene_CAZy_tpm.shape[1]
    CAZy_tpm = gene_CAZy_tpm.iloc[:, [1] + list(range(4, k))]
    CAZy_tpm = CAZy_tpm.groupby('CAZy').sum()
    CAZy_tpm.to_excel(os.path.join(anno_dir, 'CAZy', 'CAZy.tpm.xlsx'), index=True)

    CAZy_Category_tpm = gene_CAZy_tpm.iloc[:, 3:]
    CAZy_Category_tpm = CAZy_Category_tpm.groupby('Category').sum()
    CAZy_Category_tpm.to_excel(os.path.join(anno_dir, 'CAZy', 'CAZy.Category.tpm.xlsx'), index=True)

    log("  CAZy 注释完成")
    return 'CAZy', len(gene_CAZy_tpm)


def annotate_GO(args_tuple):
    """GO 注释与丰度汇总。"""
    anno_dir, dbdir, gene_tpm, ano_all = args_tuple
    log("开始 GO 注释")

    go_map = pd.read_csv(os.path.join(dbdir, 'GO', 'GO_map.txt'), sep='\t')
    go = ano_all.loc[:, ['GeneID', 'GO']].copy()
    go = go[go['GO'] != '-']
    go['GO'] = go['GO'].str.split(',')
    go = go.explode('GO').drop_duplicates()
    go_anno = pd.merge(left=go, right=go_map, left_on='GO', right_on='GO_ID')
    go_anno = go_anno.drop(['GO_ID'], axis=1)

    go_tpm = pd.merge(left=go_anno, right=gene_tpm, on='GeneID')
    go_tpm.to_csv(os.path.join(anno_dir, 'GO', 'GO.tpm.csv'), index=False, encoding='utf-8-sig')

    log("  GO 注释完成")
    return 'GO', len(go_tpm)


def func_table(bowtie, anno_dir, mapdir, dbdir, func_anno, n_workers=None):
    """整合功能注释与基因丰度表。"""
    gene_tpm_path = os.path.join(bowtie, 'gene_tpm.csv')
    func_anno_path = os.path.join(func_anno, 'func.emapper.annotations')

    log(f"读取基因丰度表: {gene_tpm_path}")
    gene_tpm = pd.read_csv(gene_tpm_path)

    log(f"读取功能注释表: {func_anno_path}")
    ano_all = pd.read_csv(func_anno_path, sep='\t')
    ano_all = ano_all.rename(columns={
        '#query': 'GeneID',
        'eggNOG_OGs': 'eggNOG',
        'KEGG_ko': 'KO',
        'GOs': 'GO'
    })

    _prepare_output_dirs(anno_dir)

    if n_workers is None:
        n_workers = min(4, mp.cpu_count())

    tasks = [
        (annotate_eggNOG, (anno_dir, mapdir, gene_tpm, ano_all)),
        (annotate_KEGG, (anno_dir, mapdir, gene_tpm, ano_all)),
        (annotate_CAZy, (anno_dir, dbdir, gene_tpm, ano_all)),
        (annotate_GO, (anno_dir, dbdir, gene_tpm, ano_all)),
    ]

    log(f"启动 {n_workers} 个进程并行执行功能注释")
    with mp.Pool(processes=n_workers) as pool:
        results = pool.map(_run_task, tasks)

    for name, count in results:
        log(f"  {name}: {count} 条注释记录")


def main():
    parser = argparse.ArgumentParser(
        description='Optimized func_anno step2: integrate functional annotation with gene abundance.'
    )
    parser.add_argument('--Annotation', type=str, default='Annotation',
                        help='Output directory for integrated annotation results')
    parser.add_argument('--dbdir', type=str, default='/data/data1/wangli/database',
                        help='Database directory containing CAZy/, GO/ subdirectories')
    parser.add_argument('--mapdir', type=str, default='/data/data1/wangli/database',
                        help='Map directory containing eggNOG/, KEGG/ subdirectories')
    parser.add_argument('--bowtie', type=str, default='bowtie',
                        help='Directory containing gene_tpm.csv')
    parser.add_argument('--fun_anno', type=str, default='Annotation',
                        help='Directory containing func.emapper.annotations')
    parser.add_argument('--workers', type=int, default=None,
                        help='Number of parallel workers for eggNOG/KEGG/CAZy/GO (default: min(4, CPU))')
    parser.add_argument('--force', action='store_true',
                        help='Remove existing output directory before running')
    args = parser.parse_args()

    anno_dir = os.path.abspath(args.Annotation)
    dbdir = os.path.abspath(args.dbdir)
    mapdir = os.path.abspath(args.mapdir)
    bowtie = os.path.abspath(args.bowtie)
    func_anno = os.path.abspath(args.fun_anno)

    start_time = time.time()
    log("=" * 60)
    log("func_ano_2_update.py 开始运行")
    log("=" * 60)

    # 输入检查
    for p, label in [(func_anno, 'fun_anno'), (dbdir, 'dbdir'), (mapdir, 'mapdir'), (bowtie, 'bowtie')]:
        if not os.path.exists(p):
            log(f"错误: {label} 目录不存在: {p}")
            sys.exit(1)

    required_files = [
        (os.path.join(func_anno, 'func.emapper.annotations'), 'func.emapper.annotations'),
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
        func_table(bowtie, anno_dir, mapdir, dbdir, func_anno, n_workers=args.workers)
    except Exception as e:
        log(f"错误: func_table 运行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    elapsed = time.time() - start_time
    log("=" * 60)
    log(f"func_ano_2_update.py 运行完成，总耗时: {elapsed:.3f} 秒 ({elapsed/60:.2f} 分钟)")
    log(f"输出目录: {anno_dir}")
    log("=" * 60)


if __name__ == '__main__':
    main()
