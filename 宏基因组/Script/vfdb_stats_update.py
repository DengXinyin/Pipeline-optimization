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


def get_table(datadir, res_dir, vfdb_dir, func_tmpdir):
    sam_gros = pd.read_csv('%s/sample-metadata.tsv' % datadir, sep='\t', skiprows=[1], dtype=str)
    k = sam_gros.shape[1]
    for i in range(1, k):
        sam_gro = sam_gros.iloc[:, [0] + [i]]
        sam_gro = sam_gro.dropna(axis=0).reset_index(drop=True)
        group_num = 'group' + str(i)
        group_dic = pd.Series(sam_gro[group_num].values, index=sam_gro['sample-id']).to_dict()
        samples_ls = sam_gro.loc[:, 'sample-id'].to_list()

        resdir = os.path.join(res_dir, group_num, '12-VFDB')
        os.makedirs(resdir, exist_ok=True)
        tmpdir = os.path.join(func_tmpdir, group_num, 'VFDB')
        os.makedirs(tmpdir, exist_ok=True)

        gene_vfdb_tpm_all = pd.read_csv('%s/gene.vf.tpm.csv' % vfdb_dir)
        vfdb_selected = gene_vfdb_tpm_all.columns[0:4].to_list()
        gene_vfdb_tpm = gene_vfdb_tpm_all.loc[:, vfdb_selected + samples_ls]
        gene_vfdb_tpm = gene_vfdb_tpm[~(gene_vfdb_tpm[samples_ls] == 0).all(axis=1)]
        gene_vfdb_tpm.to_csv('%s/gene.VFDB.tpm.csv' % resdir, index=False, encoding='utf-8-sig')
        vfdb_indexs = ['VF_Name', 'VFcategory']
        for vfdb_i in vfdb_indexs:
            vfdb_tpm = gene_vfdb_tpm.groupby(vfdb_i).sum(numeric_only=True)
            vfdb_tpm_gro = vfdb_tpm.groupby(by=group_dic, axis=1).mean()
            vfdb_tpm_rel = vfdb_tpm.div(vfdb_tpm.sum())
            vfdb_tpm_gro_rel = vfdb_tpm_gro.div(vfdb_tpm_gro.sum())
            if vfdb_i == 'VFDB':
                prefix = ''
                vfdb_tpm_rel.to_csv('%s/VFDB_diff.tsv' % tmpdir, sep='\t', index=True, encoding='utf-8-sig')
            else:
                prefix = '.Category'
                vfdb_tpm_rel.to_csv('%s/VFDB_sam.tsv' % tmpdir, sep='\t', index=True, encoding='utf-8-sig')
                vfdb_tpm_gro_rel.to_csv('%s/VFDB_group.tsv' % tmpdir, sep='\t', index=True, encoding='utf-8-sig')
            with pd.ExcelWriter('%s/VFDB%s.xlsx' % (resdir, prefix)) as writer:
                vfdb_tpm.to_excel(writer, sheet_name='samples.tpm', index=True)
                vfdb_tpm_gro.to_excel(writer, sheet_name='group.tpm', index=True)
                vfdb_tpm_rel.to_excel(writer, sheet_name='samples.relative', index=True)
                vfdb_tpm_gro_rel.to_excel(writer, sheet_name='group.relative', index=True)


def main():
    parser = argparse.ArgumentParser(description='VFDB statistics (update version)')
    parser.add_argument('-I', '--i_datadir', type=str, required=True, default='data', help='the dir of sample.txt')
    parser.add_argument('--vfdb_dir', type=str, default='vfdb', help='the res of vfdb_dir')
    parser.add_argument('--resdir', type=str, default='Result', help='the resdir')
    parser.add_argument('--func_tmp', type=str, default='func_base', help='the func_base')
    args = parser.parse_args()

    vfdb_dir = os.path.abspath(args.vfdb_dir)
    datadir = os.path.abspath(args.i_datadir)
    res_dir = os.path.abspath(args.resdir)
    func_tmpdir = os.path.abspath(args.func_tmp)

    try:
        log.info('开始生成 VFDB 统计表')
        get_table(datadir, res_dir, vfdb_dir, func_tmpdir)
        log.info('VFDB 统计完成')
    except Exception as e:
        log.error('VFDB 统计失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
