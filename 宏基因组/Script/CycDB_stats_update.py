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


def get_table(datadir, CycDB_dir, res_dir, func_tmpdir):
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
            Cyc_selected = Cyc_tpm_all.columns[0:5].to_list()
            gene_Cyc_tpm = Cyc_tpm_all.loc[:, Cyc_selected + samples_ls]
            gene_Cyc_tpm = gene_Cyc_tpm[~(gene_Cyc_tpm[samples_ls] == 0).all(axis=1)]
            gene_Cyc_tpm.to_csv('%s/gene.%s_Cycle.tpm.csv' % (resdir, Cyc), index=False, encoding='utf-8-sig')

            Cyc_indexs = ['Detail', 'Pathway']
            for Cyc_i in Cyc_indexs:
                Cyc_tpm = gene_Cyc_tpm.groupby(Cyc_i).sum(numeric_only=True)
                Cyc_tpm_gro = Cyc_tpm.groupby(by=group_dic, axis=1).mean()
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
    args = parser.parse_args()

    CycDB_dir = os.path.abspath(args.CycDB)
    datadir = os.path.abspath(args.i_datadir)
    res_dir = os.path.abspath(args.resdir)
    func_tmpdir = os.path.abspath(args.func_tmp)

    try:
        log.info('开始生成 CycDB 统计表')
        get_table(datadir, CycDB_dir, res_dir, func_tmpdir)
        log.info('CycDB 统计完成')
    except Exception as e:
        log.error('CycDB 统计失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
