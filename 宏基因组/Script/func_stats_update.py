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


def get_table(anno_dir, datadir, res_dir, func_tmpdir, dbdir):
    kegg_tpm_all = pd.read_csv('%s/KEGG/KEGG.tpm.csv' % anno_dir)
    eggNOG_tpm_all = pd.read_csv('%s/eggNOG/eggNOG.tpm.csv' % anno_dir)
    gene_CAZy_tpm_all = pd.read_csv('%s/CAZy/gene.CAZy.tpm.csv' % anno_dir)
    go_tpm_all = pd.read_csv('%s/GO/GO.tpm.csv' % anno_dir)

    sam_gros = pd.read_csv('%s/sample-metadata.tsv' % datadir, sep='\t', skiprows=[1], dtype=str)
    k = sam_gros.shape[1]
    for i in range(1, k):
        sam_gro = sam_gros.iloc[:, [0] + [i]]
        sam_gro = sam_gro.dropna(axis=0).reset_index(drop=True)
        group_num = 'group' + str(i)
        group_dic = pd.Series(sam_gro[group_num].values, index=sam_gro['sample-id']).to_dict()
        samples_ls = sam_gro.loc[:, 'sample-id'].to_list()

        resdir = os.path.join(res_dir, group_num, '7-FunctionAnnotation')
        tmpdir = os.path.join(func_tmpdir, group_num)
        tax_cla = ['1.KEGG', '2.eggNOG', '3.CAZy', '4.GO']
        for cla in tax_cla:
            cla_dir = os.path.join(resdir, cla)
            tmpdir_c = os.path.join(tmpdir, cla)
            os.makedirs(cla_dir, exist_ok=True)
            os.makedirs(tmpdir_c, exist_ok=True)

        # kegg
        kegg_selected = kegg_tpm_all.columns[0:6].to_list()
        kegg_tpm = kegg_tpm_all.loc[:, kegg_selected + samples_ls]
        kegg_tpm = kegg_tpm[~(kegg_tpm[samples_ls] == 0).all(axis=1)]
        kegg_tpm.to_csv('%s/1.KEGG/KEGG.tpm.csv' % resdir, index=False, encoding='utf-8-sig')

        kegg_indexs = ['level1_pathway_name', 'level2_pathway_name', 'level3_pathway_name']
        for kegg_i in kegg_indexs:
            leveli = kegg_i.split('_pathway_name')[0].strip()
            kegg_li = kegg_tpm.loc[:, [kegg_i] + samples_ls]
            kegg_li = kegg_li.groupby(kegg_i).sum()
            kegg_li_gro = kegg_li.groupby(by=group_dic, axis=1).mean()
            kegg_li_rel = kegg_li.div(kegg_li.sum())
            kegg_li_gro_rel = kegg_li_gro.div(kegg_li_gro.sum())
            if kegg_i != 'level1_pathway_name':
                kegg_li_rel.to_csv('%s/1.KEGG/KEGG_%s_diff.tsv' % (tmpdir, leveli), sep='\t', index=True, encoding='utf-8-sig')
            kegg_li_rel.to_csv('%s/1.KEGG/KEGG_%s_sam.tsv' % (tmpdir, leveli), sep='\t', index=True, encoding='utf-8-sig')
            kegg_li_gro_rel.to_csv('%s/1.KEGG/KEGG_%s_group.tsv' % (tmpdir, leveli), sep='\t', index=True, encoding='utf-8-sig')
            with pd.ExcelWriter('%s/1.KEGG/%s.xlsx' % (resdir, leveli)) as writer:
                kegg_li.to_excel(writer, sheet_name='samples.tpm', index=True)
                kegg_li_gro.to_excel(writer, sheet_name='group.tpm', index=True)
                kegg_li_rel.to_excel(writer, sheet_name='samples.relative', index=True)
                kegg_li_gro_rel.to_excel(writer, sheet_name='group.relative', index=True)

        # eggNOG
        eggNOG_selected = eggNOG_tpm_all.columns[0:5].to_list()
        gene_eggNOG_tpm = eggNOG_tpm_all.loc[:, eggNOG_selected + samples_ls]
        gene_eggNOG_tpm = gene_eggNOG_tpm[~(gene_eggNOG_tpm[samples_ls] == 0).all(axis=1)]
        gene_eggNOG_tpm.to_csv('%s/2.eggNOG/gene_eggNOG.tpm.csv' % resdir, index=False, encoding='utf-8-sig')

        eggNOG_anno = eggNOG_tpm_all.iloc[:, 1:5]
        eggNOG_tpm = gene_eggNOG_tpm.drop(['GeneID'], axis=1)
        eggNOG_tpm['category_description'] = eggNOG_tpm['category'].str.cat(
            eggNOG_tpm['category_description'], sep=':')
        eggNOG_tpm['category_description'] = eggNOG_tpm['category_description'].str.strip()

        eggNOG_indexs = ['eggNOG', 'category_description']
        for eggNOG_i in eggNOG_indexs:
            eggNOG_tpm_i = eggNOG_tpm.groupby(eggNOG_i).sum(numeric_only=True)
            eggNOG_tpm_gro_i = eggNOG_tpm_i.groupby(by=group_dic, axis=1).mean()
            eggNOG_tpm_i_rel = eggNOG_tpm_i.div(eggNOG_tpm_i.sum())
            eggNOG_tpm_gro_i_rel = eggNOG_tpm_gro_i.div(eggNOG_tpm_gro_i.sum())
            if eggNOG_i == 'eggNOG':
                prefix = ''
                eggNOG_tpm_i_rel.to_csv('%s/2.eggNOG/eggNOG_diff.tsv' % tmpdir, sep='\t', index=True, encoding='utf-8-sig')
                eggNOG_tpm_i = pd.merge(left=eggNOG_anno, right=eggNOG_tpm_i, left_on='eggNOG', right_index=True).drop_duplicates().set_index('eggNOG')
                eggNOG_tpm_gro_i = pd.merge(left=eggNOG_anno, right=eggNOG_tpm_gro_i, left_on='eggNOG', right_index=True).drop_duplicates().set_index('eggNOG')
                eggNOG_tpm_i_rel = pd.merge(left=eggNOG_anno, right=eggNOG_tpm_i_rel, left_on='eggNOG', right_index=True).drop_duplicates().set_index('eggNOG')
                eggNOG_tpm_gro_i_rel = pd.merge(left=eggNOG_anno, right=eggNOG_tpm_gro_i_rel, left_on='eggNOG', right_index=True).drop_duplicates().set_index('eggNOG')
            else:
                prefix = '.Category'
                eggNOG_tpm_i_rel.to_csv('%s/2.eggNOG/eggNOG_sam.tsv' % tmpdir, sep='\t', index=True, encoding='utf-8-sig')
                eggNOG_tpm_gro_i_rel.to_csv('%s/2.eggNOG/eggNOG_group.tsv' % tmpdir, sep='\t', index=True, encoding='utf-8-sig')
            with pd.ExcelWriter('%s/2.eggNOG/eggNOG%s.xlsx' % (resdir, prefix)) as writer:
                eggNOG_tpm_i.to_excel(writer, sheet_name='samples.tpm', index=True)
                eggNOG_tpm_gro_i.to_excel(writer, sheet_name='group.tpm', index=True)
                eggNOG_tpm_i_rel.to_excel(writer, sheet_name='samples.relative', index=True)
                eggNOG_tpm_gro_i_rel.to_excel(writer, sheet_name='group.relative', index=True)

        # CAZy
        CAZy_selected = gene_CAZy_tpm_all.columns[0:4].to_list()
        gene_CAZy_tpm = gene_CAZy_tpm_all.loc[:, CAZy_selected + samples_ls]
        gene_CAZy_tpm = gene_CAZy_tpm[~(gene_CAZy_tpm[samples_ls] == 0).all(axis=1)]
        gene_CAZy_tpm.to_csv('%s/3.CAZy/gene.CAZy.tpm.csv' % resdir, index=False, encoding='utf-8-sig')

        CAZy_indexs = ['CAZy', 'Category']
        for CAZy_i in CAZy_indexs:
            CAZy_tpm_i = gene_CAZy_tpm.groupby(CAZy_i).sum(numeric_only=True)
            CAZy_tpm_gro_i = CAZy_tpm_i.groupby(by=group_dic, axis=1).mean()
            CAZy_tpm_i_rel = CAZy_tpm_i.div(CAZy_tpm_i.sum())
            CAZy_tpm_gro_i_rel = CAZy_tpm_gro_i.div(CAZy_tpm_gro_i.sum())
            if CAZy_i == 'CAZy':
                prefix = ''
                CAZy_tpm_i_rel.to_csv('%s/3.CAZy/CAZy_diff.tsv' % tmpdir, sep='\t', index=True, encoding='utf-8-sig')
            else:
                prefix = '.Category'
                CAZy_tpm_i_rel.to_csv('%s/3.CAZy/CAZy_sam.tsv' % tmpdir, sep='\t', index=True, encoding='utf-8-sig')
                CAZy_tpm_gro_i_rel.to_csv('%s/3.CAZy/CAZy_group.tsv' % tmpdir, sep='\t', index=True, encoding='utf-8-sig')
            with pd.ExcelWriter('%s/3.CAZy/CAZy%s.xlsx' % (resdir, prefix)) as writer:
                CAZy_tpm_i.to_excel(writer, sheet_name='samples.tpm', index=True)
                CAZy_tpm_gro_i.to_excel(writer, sheet_name='group.tpm', index=True)
                CAZy_tpm_i_rel.to_excel(writer, sheet_name='samples.relative', index=True)
                CAZy_tpm_gro_i_rel.to_excel(writer, sheet_name='group.relative', index=True)

        # GO
        go_map = pd.read_csv('%s/GO/GO_map.txt' % dbdir, sep='\t')
        go_map = go_map.rename(columns={'GO_ID':'GO'})
        go_selected = go_tpm_all.columns[0:4].to_list()
        gene_go_tpm = go_tpm_all.loc[:, go_selected + samples_ls]
        gene_go_tpm = gene_go_tpm[~(gene_go_tpm[samples_ls] == 0).all(axis=1)]
        gene_go_tpm.to_csv('%s/4.GO/gene_GO.tpm.csv' % resdir, index=False, encoding='utf-8-sig')

        go_tpm = gene_go_tpm.groupby('GO').sum(numeric_only=True)
        go_tpm_gro = go_tpm.groupby(by=group_dic, axis=1).mean()
        go_tpm_rel = go_tpm.div(go_tpm.sum())
        go_tpm_gro_rel = go_tpm_gro.div(go_tpm_gro.sum())
        go_tpm_rel.to_csv('%s/4.GO/GO_diff.tsv' % tmpdir, sep='\t', index=True, encoding='utf-8-sig')
        go_tpm_rel.to_csv('%s/4.GO/GO_sam.tsv' % tmpdir, sep='\t', index=True, encoding='utf-8-sig')
        go_tpm_gro_rel.to_csv('%s/4.GO/GO_group.tsv' % tmpdir, sep='\t', index=True, encoding='utf-8-sig')
        go_tpm = pd.merge(left=go_tpm, right=go_map, left_on='GO', right_on='GO').drop_duplicates()
        go_tpm_gro = pd.merge(left=go_tpm_gro, right=go_map, left_on='GO', right_on='GO').drop_duplicates()
        go_tpm_rel = pd.merge(left=go_tpm_rel, right=go_map, left_on='GO', right_on='GO').drop_duplicates()
        go_tpm_gro_rel = pd.merge(left=go_tpm_gro_rel, right=go_map, left_on='GO', right_on='GO').drop_duplicates()
        with pd.ExcelWriter('%s/4.GO/GO.xlsx' % resdir) as writer:
            go_tpm.to_excel(writer, sheet_name='samples.tpm', index=False)
            go_tpm_gro.to_excel(writer, sheet_name='group.tpm', index=False)
            go_tpm_rel.to_excel(writer, sheet_name='samples.relative', index=False)
            go_tpm_gro_rel.to_excel(writer, sheet_name='group.relative', index=False)


def main():
    parser = argparse.ArgumentParser(description='Function annotation statistics (update version)')
    parser.add_argument('-I', '--i_datadir', type=str, required=True, default='data', help='the dir of sample.txt')
    parser.add_argument('--Annotation', type=str, default='Annotation', help='the res of Annotation')
    parser.add_argument('--resdir', type=str, default='Result', help='the resdir')
    parser.add_argument('--dbdir', type=str, default='/data/data1/wangli/database', help='the dir of database')
    parser.add_argument('--func_tmp', type=str, default='func_base', help='the func_base')
    args = parser.parse_args()

    datadir = os.path.abspath(args.i_datadir)
    anno_dir = os.path.abspath(args.Annotation)
    res_dir = os.path.abspath(args.resdir)
    dbdir = os.path.abspath(args.dbdir)
    func_tmpdir = os.path.abspath(args.func_tmp)

    try:
        log.info('开始生成功能注释丰度表')
        get_table(anno_dir, datadir, res_dir, func_tmpdir, dbdir)
        log.info('功能注释统计完成')
    except Exception as e:
        log.error('功能注释统计失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
