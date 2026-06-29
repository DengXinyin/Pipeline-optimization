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


def get_table(datadir, res_dir, BacMet2dir, func_tmpdir):
    sam_gros = pd.read_csv('%s/sample-metadata.tsv' % datadir, sep='\t', skiprows=[1], dtype=str)
    k = sam_gros.shape[1]
    for i in range(1, k):
        sam_gro = sam_gros.iloc[:, [0] + [i]]
        sam_gro = sam_gro.dropna(axis=0).reset_index(drop=True)
        group_num = 'group' + str(i)
        group_dic = pd.Series(sam_gro[group_num].values, index=sam_gro['sample-id']).to_dict()
        samples_ls = sam_gro.loc[:, 'sample-id'].to_list()

        resdir = os.path.join(res_dir, group_num, '13-HeavyMetals')
        os.makedirs(resdir, exist_ok=True)
        tmpdir = os.path.join(func_tmpdir, group_num, 'HeavyMetals')
        os.makedirs(tmpdir, exist_ok=True)

        gene_BacMet2_tpm_all = pd.read_csv('%s/BacMet2.tpm.csv' % BacMet2dir)
        BacMet2_selected = gene_BacMet2_tpm_all.columns[0:7].to_list()
        gene_BacMet2_tpm = gene_BacMet2_tpm_all.loc[:, BacMet2_selected + samples_ls]
        gene_BacMet2_tpm = gene_BacMet2_tpm[~(gene_BacMet2_tpm[samples_ls] == 0).all(axis=1)]
        gene_BacMet2_tpm.to_csv('%s/gene.HeavyMetals.tpm.csv' % resdir, index=False, encoding='utf-8-sig')
        BacMet2_indexs = ['Gene_name', 'Compound']
        for BacMet2_i in BacMet2_indexs:
            BacMet2_tpm = gene_BacMet2_tpm.groupby(BacMet2_i).sum(numeric_only=True)
            BacMet2_tpm_gro = BacMet2_tpm.groupby(by=group_dic, axis=1).mean()
            BacMet2_tpm_rel = BacMet2_tpm.div(BacMet2_tpm.sum())
            BacMet2_tpm_gro_rel = BacMet2_tpm_gro.div(BacMet2_tpm_gro.sum())
            if BacMet2_i == 'BacMet2':
                prefix = ''
                BacMet2_tpm_rel.to_csv('%s/HeavyMetals_diff.tsv' % tmpdir, sep='\t', index=True, encoding='utf-8-sig')
            else:
                prefix = '.Category'
                BacMet2_tpm_rel.to_csv('%s/HeavyMetals_sam.tsv' % tmpdir, sep='\t', index=True, encoding='utf-8-sig')
                BacMet2_tpm_gro_rel.to_csv('%s/HeavyMetals_group.tsv' % tmpdir, sep='\t', index=True, encoding='utf-8-sig')
            with pd.ExcelWriter('%s/HeavyMetals%s.xlsx' % (resdir, prefix)) as writer:
                BacMet2_tpm.to_excel(writer, sheet_name='samples.tpm', index=True)
                BacMet2_tpm_gro.to_excel(writer, sheet_name='group.tpm', index=True)
                BacMet2_tpm_rel.to_excel(writer, sheet_name='samples.relative', index=True)
                BacMet2_tpm_gro_rel.to_excel(writer, sheet_name='group.relative', index=True)


def main():
    parser = argparse.ArgumentParser(description='BacMet2 statistics (update version)')
    parser.add_argument('-I', '--i_datadir', type=str, required=True, default='data', help='the dir of sample.txt')
    parser.add_argument('--BacMet2dir', type=str, default='BacMet2', help='the res of BacMet2dir')
    parser.add_argument('--resdir', type=str, default='Result', help='the resdir')
    parser.add_argument('--func_tmp', type=str, default='func_base', help='the func_base')
    args = parser.parse_args()

    BacMet2dir = os.path.abspath(args.BacMet2dir)
    datadir = os.path.abspath(args.i_datadir)
    res_dir = os.path.abspath(args.resdir)
    func_tmpdir = os.path.abspath(args.func_tmp)

    try:
        log.info('开始生成 BacMet2 统计表')
        get_table(datadir, res_dir, BacMet2dir, func_tmpdir)
        log.info('BacMet2 统计完成')
    except Exception as e:
        log.error('BacMet2 统计失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
