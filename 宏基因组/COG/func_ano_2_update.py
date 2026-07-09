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

    ko_map = pd.read_excel(os.path.join(mapdir, 'KEGG', 'KO_map.xlsx'))
    kegg_level = pd.read_csv(os.path.join(mapdir, 'KEGG', 'kegg_level.txt'), sep='\t')

    ko = ano_all.loc[:, ['GeneID', 'KO']].copy()
    ko = ko[ko['KO'] != '-']
    ko['KO'] = ko['KO'].str.split(',')
    ko = ko.explode('KO').drop_duplicates()
    ko['KO'] = ko['KO'].str.split('ko:').str[1]

    ko_anno = pd.merge(left=ko, right=ko_map, left_on='KO', right_on='ko_ID')
    ko_anno = pd.merge(left=ko_anno, right=kegg_level, on='level3_pathway_ID')
    ko_anno = ko_anno.drop(['ko_ID'], axis=1)

    kegg_tpm = pd.merge(left=ko_anno, right=gene_tpm, on='GeneID')
    kegg_tpm.to_csv(os.path.join(anno_dir, 'KEGG', 'KEGG.tpm.csv'), index=False, encoding='utf-8-sig')

    kegg_l1 = pd.concat([kegg_tpm.iloc[:, 3], kegg_tpm.iloc[:, 6:]], axis=1)
    kegg_l1 = kegg_l1.groupby('level1_pathway_name').sum()
    kegg_l1.to_excel(os.path.join(anno_dir, 'KEGG', 'level1.tpm.xlsx'), index=True)

    kegg_l2 = pd.concat([kegg_tpm.iloc[:, 4], kegg_tpm.iloc[:, 6:]], axis=1)
    kegg_l2 = kegg_l2.groupby('level2_pathway_name').sum()
    kegg_l2.to_excel(os.path.join(anno_dir, 'KEGG', 'level2.tpm.xlsx'), index=True)

    kegg_l3 = pd.concat([kegg_tpm.iloc[:, [2, 5]], kegg_tpm.iloc[:, 6:]], axis=1)
    kegg_l3 = kegg_l3.groupby(['level3_pathway_ID', 'level3_pathway_name']).sum()
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
