#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import logging

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)


def restore_detail_column(cyc_tpm, cyc, dbdir):
    """兼容旧 CycDB 结果：按 KO + Pathway 从原始映射表补回 Detail。"""
    if 'Detail' in cyc_tpm.columns:
        return cyc_tpm
    if not dbdir:
        raise ValueError(
            '%s_Cycle.xlsx 缺少 Detail 字段，且未提供 --dbdir，无法从映射表恢复。' % cyc
        )

    map_file = os.path.join(dbdir, 'diting', '%s.txt' % cyc)
    if not os.path.isfile(map_file):
        raise FileNotFoundError('%s_Cycle.xlsx 缺少 Detail，且映射表不存在: %s' % (cyc, map_file))
    cyc_map = pd.read_csv(map_file, sep='\t', dtype=str)
    required = {'KO', 'Pathway', 'Detail'}
    if not required.issubset(cyc_map.columns):
        raise ValueError('%s 映射表缺少字段: %s' %
                         (cyc, sorted(required - set(cyc_map.columns))))

    detail_map = cyc_map.loc[:, ['KO', 'Pathway', 'Detail']].drop_duplicates()
    restored = pd.merge(
        left=cyc_tpm, right=detail_map,
        on=['KO', 'Pathway'], how='left', validate='many_to_many'
    )
    missing = restored['Detail'].isna() | restored['Detail'].astype(str).str.strip().eq('')
    if missing.any():
        examples = restored.loc[missing, ['KO', 'Pathway']].drop_duplicates().head(3)
        raise ValueError(
            '%s_Cycle.xlsx 有 %d 行无法从映射表恢复 Detail；示例: %s'
            % (cyc, int(missing.sum()), examples.to_dict('records'))
        )
    log.info('%s_Cycle.xlsx 缺少 Detail，已按 KO + Pathway 从映射表恢复', cyc)
    return restored


def get_table(datadir, CycDB_dir, res_dir, func_tmpdir, dbdir=None):
    sam_gros = pd.read_csv('%s/sample-metadata.tsv' % datadir, sep='\t', skiprows=[1], dtype=str)
    k = sam_gros.shape[1]
    for i in range(1, k):
        sam_gro = sam_gros.iloc[:, [0] + [i]]
        sam_gro = sam_gro.dropna(axis=0).reset_index(drop=True)
        group_num = 'group' + str(i)
        group_dic = pd.Series(sam_gro[group_num].values, index=sam_gro['sample-id']).to_dict()
        samples_ls = sam_gro.loc[:, 'sample-id'].to_list()

        CycDB_f = ['Carbon', 'Methane', 'Nitrogen', 'phosphorylation', 'Sulfur']
        for Cyc in CycDB_f:
            resdir = os.path.join(res_dir, group_num, '9-METABOLIC', '%s_Cycle' % Cyc)
            os.makedirs(resdir, exist_ok=True)
            tmpdir = os.path.join(func_tmpdir, group_num, '%s_Cycle' % Cyc)
            os.makedirs(tmpdir, exist_ok=True)
            try:
                Cyc_tpm_all = pd.read_excel('%s/%s_Cycle.xlsx' % (CycDB_dir, Cyc))
            except Exception:
                log.info('%s 循环无注释结果，跳过', Cyc)
                continue
            required_base = {'GeneID', 'taxonomy', 'KO', 'Pathway'}
            if not required_base.issubset(Cyc_tpm_all.columns):
                raise ValueError('%s_Cycle.xlsx 缺少字段: %s' %
                                 (Cyc, sorted(required_base - set(Cyc_tpm_all.columns))))
            missing_samples = sorted(set(samples_ls) - set(Cyc_tpm_all.columns))
            if missing_samples:
                raise ValueError('%s_Cycle.xlsx 缺少样本列: %s' % (Cyc, missing_samples))
            Cyc_tpm_all = restore_detail_column(Cyc_tpm_all, Cyc, dbdir)
            Cyc_selected = ['GeneID', 'taxonomy', 'KO', 'Pathway', 'Detail']
            gene_Cyc_tpm = Cyc_tpm_all.loc[:, Cyc_selected + samples_ls]
            gene_Cyc_tpm = gene_Cyc_tpm[~(gene_Cyc_tpm[samples_ls] == 0).all(axis=1)]
            gene_Cyc_tpm.to_csv('%s/gene.%s_Cycle.tpm.csv' % (resdir, Cyc), index=False, encoding='utf-8-sig')

            Cyc_indexs = ['Detail', 'Pathway']
            for Cyc_i in Cyc_indexs:
                Cyc_tpm = gene_Cyc_tpm.groupby(Cyc_i).sum(numeric_only=True)
                Cyc_tpm_gro = Cyc_tpm.T.groupby(group_dic).mean().T
                Cyc_tpm_rel = Cyc_tpm.div(Cyc_tpm.sum())
                Cyc_tpm_gro_rel = Cyc_tpm_gro.div(Cyc_tpm_gro.sum())
                if Cyc_i == 'Detail':
                    prefix = ''
                else:
                    prefix = '_pathway'
                    Cyc_tpm_rel.to_csv('%s/%s_sam.tsv' % (tmpdir, Cyc), sep='\t', index=True, encoding='utf-8-sig')
                    Cyc_tpm_gro_rel.to_csv('%s/%s_group.tsv' % (tmpdir, Cyc), sep='\t', index=True, encoding='utf-8-sig')
                    Cyc_tpm_rel.to_csv('%s/%s_diff.tsv' % (tmpdir, Cyc), sep='\t', index=True, encoding='utf-8-sig')
                with pd.ExcelWriter('%s/%s_Cycle%s.xlsx' % (resdir, Cyc, prefix)) as writer:
                    Cyc_tpm.to_excel(writer, sheet_name='samples.tpm', index=True)
                    Cyc_tpm_gro.to_excel(writer, sheet_name='group.tpm', index=True)
                    Cyc_tpm_rel.to_excel(writer, sheet_name='samples.relative', index=True)
                    Cyc_tpm_gro_rel.to_excel(writer, sheet_name='group.relative', index=True)


def main():
    parser = argparse.ArgumentParser(description='CycDB statistics (update version)')
    parser.add_argument('-I', '--i_datadir', type=str, required=True, default='data', help='the dir of sample.txt')
    parser.add_argument('--CycDB', type=str, default='CycDB', help='the res of CycDB')
    parser.add_argument('--resdir', type=str, default='Result', help='the resdir')
    parser.add_argument('--func_tmp', type=str, default='func_base', help='the func_base')
    parser.add_argument('--dbdir', type=str, default=None,
                        help='数据库根目录；旧 CycDB 结果缺少 Detail 时用于恢复映射')
    args = parser.parse_args()

    CycDB_dir = os.path.abspath(args.CycDB)
    datadir = os.path.abspath(args.i_datadir)
    res_dir = os.path.abspath(args.resdir)
    func_tmpdir = os.path.abspath(args.func_tmp)
    dbdir = os.path.abspath(args.dbdir) if args.dbdir else None

    try:
        log.info('开始生成 CycDB 统计表')
        get_table(datadir, CycDB_dir, res_dir, func_tmpdir, dbdir)
        log.info('CycDB 统计完成')
    except Exception as e:
        log.error('CycDB 统计失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
