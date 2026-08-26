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


def get_table(datadir, res_dir, ARGdir, func_tmpdir):
    sam_gros = pd.read_csv('%s/sample-metadata.tsv' % datadir, sep='\t', skiprows=[1], dtype=str)
    k = sam_gros.shape[1]
    for i in range(1, k):
        sam_gro = sam_gros.iloc[:, [0] + [i]]
        sam_gro = sam_gro.dropna(axis=0).reset_index(drop=True)
        group_num = 'group' + str(i)
        group_dic = pd.Series(sam_gro[group_num].values, index=sam_gro['sample-id']).to_dict()
        samples_ls = sam_gro.loc[:, 'sample-id'].to_list()

        resdir = os.path.join(res_dir, group_num, '10-ARG')
        os.makedirs(resdir, exist_ok=True)
        tmpdir = os.path.join(func_tmpdir, group_num, 'ARG')
        os.makedirs(tmpdir, exist_ok=True)

        gene_ARG_tpm_all = pd.read_csv('%s/ARG.tpm.csv' % ARGdir)
        ARG_selected = gene_ARG_tpm_all.columns[0:4].to_list()
        gene_ARG_tpm = gene_ARG_tpm_all.loc[:, ARG_selected + samples_ls]
        gene_ARG_tpm = gene_ARG_tpm[~(gene_ARG_tpm[samples_ls] == 0).all(axis=1)]
        gene_ARG_tpm.to_csv('%s/gene.ARG.tpm.csv' % resdir, index=False, encoding='utf-8-sig')
        ARG_indexs = ['ARG', 'Type']
        for ARG_i in ARG_indexs:
            ARG_tpm = gene_ARG_tpm.groupby(ARG_i).sum(numeric_only=True)
            ARG_tpm_gro = ARG_tpm.groupby(by=group_dic, axis=1).mean()
            ARG_tpm_rel = ARG_tpm.div(ARG_tpm.sum())
            ARG_tpm_gro_rel = ARG_tpm_gro.div(ARG_tpm_gro.sum())
            if ARG_i == 'ARG':
                prefix = ''
                ARG_tpm_rel.to_csv('%s/ARG_diff.tsv' % tmpdir, sep='\t', index=True, encoding='utf-8-sig')
            else:
                prefix = '.Category'
                ARG_tpm_rel.to_csv('%s/ARG_sam.tsv' % tmpdir, sep='\t', index=True, encoding='utf-8-sig')
                ARG_tpm_gro_rel.to_csv('%s/ARG_group.tsv' % tmpdir, sep='\t', index=True, encoding='utf-8-sig')
            with pd.ExcelWriter('%s/ARG%s.xlsx' % (resdir, prefix)) as writer:
                ARG_tpm.to_excel(writer, sheet_name='samples.tpm', index=True)
                ARG_tpm_gro.to_excel(writer, sheet_name='group.tpm', index=True)
                ARG_tpm_rel.to_excel(writer, sheet_name='samples.relative', index=True)
                ARG_tpm_gro_rel.to_excel(writer, sheet_name='group.relative', index=True)


def main():
    parser = argparse.ArgumentParser(description='ARGs statistics (update version)')
    parser.add_argument('-I', '--i_datadir', type=str, required=True, default='data', help='the dir of sample.txt')
    parser.add_argument('--ARGdir', type=str, default='ARGs', help='the res of ARGdir')
    parser.add_argument('--resdir', type=str, default='Result', help='the resdir')
    parser.add_argument('--func_tmp', type=str, default='func_base', help='the func_base')
    args = parser.parse_args()

    ARGdir = os.path.abspath(args.ARGdir)
    datadir = os.path.abspath(args.i_datadir)
    res_dir = os.path.abspath(args.resdir)
    func_tmpdir = os.path.abspath(args.func_tmp)

    try:
        log.info('开始生成 ARGs 统计表')
        get_table(datadir, res_dir, ARGdir, func_tmpdir)
        log.info('ARGs 统计完成')
    except Exception as e:
        log.error('ARGs 统计失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
