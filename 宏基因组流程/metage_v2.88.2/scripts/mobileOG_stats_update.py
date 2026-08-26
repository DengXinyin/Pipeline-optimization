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


def get_table(datadir, res_dir, mobileOGdir, func_tmpdir):
    sam_gros = pd.read_csv('%s/sample-metadata.tsv' % datadir, sep='\t', skiprows=[1], dtype=str)
    k = sam_gros.shape[1]
    for i in range(1, k):
        sam_gro = sam_gros.iloc[:, [0] + [i]]
        sam_gro = sam_gro.dropna(axis=0).reset_index(drop=True)
        group_num = 'group' + str(i)
        group_dic = pd.Series(sam_gro[group_num].values, index=sam_gro['sample-id']).to_dict()
        samples_ls = sam_gro.loc[:, 'sample-id'].to_list()

        resdir = os.path.join(res_dir, group_num, '12-mobileOG')
        os.makedirs(resdir, exist_ok=True)
        tmpdir = os.path.join(func_tmpdir, group_num, 'mobileOG')
        os.makedirs(tmpdir, exist_ok=True)

        gene_mobileOG_tpm_all = pd.read_csv('%s/mobileOG.tpm.csv' % mobileOGdir)
        mobileOG_selected = gene_mobileOG_tpm_all.columns[0:11].to_list()
        gene_mobileOG_tpm = gene_mobileOG_tpm_all.loc[:, mobileOG_selected + samples_ls]
        gene_mobileOG_tpm = gene_mobileOG_tpm[~(gene_mobileOG_tpm[samples_ls] == 0).all(axis=1)]
        gene_mobileOG_tpm.to_csv('%s/gene.mobileOG.tpm.csv' % resdir, index=False, encoding='utf-8-sig')
        mobileOG_indexs = ['mobileOG Entry Name', 'Major mobileOG Category']
        for mobileOG_i in mobileOG_indexs:
            mobileOG_tpm = gene_mobileOG_tpm.groupby(mobileOG_i).sum(numeric_only=True)
            mobileOG_tpm_gro = mobileOG_tpm.T.groupby(by=group_dic).mean().T
            mobileOG_tpm_rel = mobileOG_tpm.div(mobileOG_tpm.sum())
            mobileOG_tpm_gro_rel = mobileOG_tpm_gro.div(mobileOG_tpm_gro.sum())
            if mobileOG_i == 'mobileOG Entry Name':
                prefix = ''
                mobileOG_tpm_rel.to_csv('%s/mobileOG_diff.tsv' % tmpdir, sep='\t', index=True, encoding='utf-8-sig')
            else:
                prefix = '.Category'
                mobileOG_tpm_rel.to_csv('%s/mobileOG_sam.tsv' % tmpdir, sep='\t', index=True, encoding='utf-8-sig')
                mobileOG_tpm_gro_rel.to_csv('%s/mobileOG_group.tsv' % tmpdir, sep='\t', index=True, encoding='utf-8-sig')
            with pd.ExcelWriter('%s/mobileOG%s.xlsx' % (resdir, prefix)) as writer:
                mobileOG_tpm.to_excel(writer, sheet_name='samples.tpm', index=True)
                mobileOG_tpm_gro.to_excel(writer, sheet_name='group.tpm', index=True)
                mobileOG_tpm_rel.to_excel(writer, sheet_name='samples.relative', index=True)
                mobileOG_tpm_gro_rel.to_excel(writer, sheet_name='group.relative', index=True)


def main():
    parser = argparse.ArgumentParser(description='mobileOG statistics (update version)')
    parser.add_argument('-I', '--i_datadir', type=str, required=True, default='data', help='the dir of sample.txt')
    parser.add_argument('--mobileOGdir', type=str, default='mobileOG', help='the res of mobileOGdir')
    parser.add_argument('--resdir', type=str, default='Result', help='the resdir')
    parser.add_argument('--func_tmp', type=str, default='func_base', help='the func_base')
    args = parser.parse_args()

    mobileOGdir = os.path.abspath(args.mobileOGdir)
    datadir = os.path.abspath(args.i_datadir)
    res_dir = os.path.abspath(args.resdir)
    func_tmpdir = os.path.abspath(args.func_tmp)

    try:
        log.info('开始生成 mobileOG 统计表')
        get_table(datadir, res_dir, mobileOGdir, func_tmpdir)
        log.info('mobileOG 统计完成')
    except Exception as e:
        log.error('mobileOG 统计失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
