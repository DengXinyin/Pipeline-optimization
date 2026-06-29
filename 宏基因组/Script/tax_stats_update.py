#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import shutil
import subprocess
import logging

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)


def get_class_exp(bacteria_tpm, type, res_grodir):
    bacteria_rel = bacteria_tpm.iloc[:, 7:].div(bacteria_tpm.iloc[:, 7:].sum())
    bacteria_rel = pd.concat([bacteria_tpm.iloc[:, 0: 7], bacteria_rel], axis=1)
    bacteria_tpm.to_csv('%s/%s/%s.taxonomy.csv' % (res_grodir, type, type), index=False, encoding='utf-8-sig')
    for i in range(0, 7):
        name = bacteria_tpm.columns[i]
        bacta_tax_tpm = bacteria_tpm.iloc[:, [i] + list(range(7, len(bacteria_tpm.columns)))]
        bacta_tax_tpm = bacta_tax_tpm.groupby(by=name).sum()
        bacta_tax_rela = bacteria_rel.iloc[:, [i] + list(range(7, len(bacteria_rel.columns)))]
        bacta_tax_rela = bacta_tax_rela.groupby(by=name).sum()
        with pd.ExcelWriter('%s/%s/%s.xlsx' % (res_grodir, type, name)) as writer:
            bacta_tax_tpm.to_excel(writer, sheet_name='tpm', index=True)
            bacta_tax_rela.to_excel(writer, sheet_name='relative', index=True)


def krona(res_dir, anno_dir, datadir):
    krona_dir = os.path.join(anno_dir, 'krona')
    os.makedirs(krona_dir, exist_ok=True)
    sepecies_ls = ['kingdom', 'phylum', 'class', 'order', 'family', 'genus', 'species']

    all_dat = pd.read_csv('%s/All/All.taxonomy.csv' % anno_dir)
    all_dat = all_dat.drop(['GeneID'], axis=1)
    all_dat = all_dat.groupby(by=sepecies_ls, as_index=False).sum()

    sam_gros = pd.read_csv('%s/sample-metadata.tsv' % datadir, sep='\t', skiprows=[1], dtype=str, encoding='utf-8')
    k = sam_gros.shape[1]
    for i in range(1, k):
        sam_gro = sam_gros.iloc[:, [0] + [i]]
        sam_gro = sam_gro.dropna(axis=0).reset_index(drop=True)
        samples = sam_gro['sample-id'].to_list()
        group_num = 'group' + str(i)
        res_grodir = os.path.join(res_dir, group_num, '5-TaxAnnotation', '2.Krona')
        os.makedirs(res_grodir, exist_ok=True)

        gro_dat = all_dat.loc[:, sepecies_ls + samples]
        command_str = ''
        for i in range(7, gro_dat.shape[1]):
            sample_tax = gro_dat.iloc[:, [i] + list(range(0, 7))]
            sample_name = gro_dat.columns[i]
            sample_tax.to_csv('%s/krona/%s.txt' % (anno_dir, sample_name), sep='\t', index=False)
            command_str = command_str + '%s/krona/%s.txt ' % (anno_dir, sample_name)
        krona_cmd = 'ktImportText %s -o %s/krona.html' % (command_str, res_grodir)
        krona_sh = os.path.join(anno_dir, 'krona.sh')
        with open(krona_sh, 'w', encoding='utf-8') as f:
            f.write(krona_cmd)
        log.info('生成 Krona 图: %s', res_grodir)
        subprocess.run('bash %s >%s 2>&1' % (krona_sh, os.path.join(anno_dir, 'krona.log')),
                       shell=True, check=True)


def get_table(anno_dir, datadir, res_dir):
    sepecies_ls = ['kingdom', 'phylum', 'class', 'order', 'family', 'genus', 'species']
    all_dat = pd.read_csv('%s/All/All.taxonomy.csv' % anno_dir)
    all_dat = all_dat.drop(['GeneID'], axis=1)
    all_dat = all_dat.groupby(by=sepecies_ls, as_index=False).sum()

    sam_gros = pd.read_csv('%s/sample-metadata.tsv' % datadir, sep='\t', skiprows=[1], dtype=str)
    k = sam_gros.shape[1]
    for i in range(1, k):
        sam_gro = sam_gros.iloc[:, [0] + [i]]
        sam_gro = sam_gro.dropna(axis=0).reset_index(drop=True)
        samples = sam_gro['sample-id'].to_list()
        group_num = 'group' + str(i)
        sam_gro_dc = pd.Series(sam_gro[group_num].values, index=sam_gro['sample-id']).to_dict()

        grodir = os.path.join(res_dir, group_num, '5-TaxAnnotation', '1.Tables')
        samples_dir = os.path.join(grodir, 'Samples')
        groups_dir = os.path.join(grodir, 'Groups')
        type_ls = ['All', 'Archaea', 'bacteria', 'Fungi', 'Virus']
        for type in type_ls:
            os.makedirs(os.path.join(samples_dir, type), exist_ok=True)
            os.makedirs(os.path.join(groups_dir, type), exist_ok=True)
        shutil.copy('%s/gene.taxonomy.csv' % anno_dir, grodir)

        all_tpm = all_dat.loc[:, sepecies_ls + samples]
        get_class_exp(all_tpm, 'All', samples_dir)
        bacteria_tpm = all_tpm[all_tpm['kingdom'] == 'k__Bacteria']
        get_class_exp(bacteria_tpm, 'bacteria', samples_dir)
        Archaea_tpm = all_tpm[all_tpm['kingdom'] == 'k__Archaea']
        get_class_exp(Archaea_tpm, 'Archaea', samples_dir)
        Fungi_tpm = all_tpm[all_tpm['kingdom'] == 'k__Eukaryota']
        get_class_exp(Fungi_tpm, 'Fungi', samples_dir)
        Virus_tpm = all_tpm[all_tpm['kingdom'] == 'k__Viruses']
        get_class_exp(Virus_tpm, 'Virus', samples_dir)

        all_group = all_tpm.groupby(by=sam_gro_dc, axis=1).mean()
        all_group = pd.concat([all_tpm.iloc[:, 0: 7], all_group], axis=1)
        get_class_exp(all_group, 'All', groups_dir)
        bacteria_tpm_gro = all_group[all_group['kingdom'] == 'k__Bacteria']
        get_class_exp(bacteria_tpm_gro, 'bacteria', groups_dir)
        Archaea_tpm_gro = all_group[all_group['kingdom'] == 'k__Archaea']
        get_class_exp(Archaea_tpm_gro, 'Archaea', groups_dir)
        Fungi_tpm_gro = all_group[all_group['kingdom'] == 'k__Eukaryota']
        get_class_exp(Fungi_tpm_gro, 'Fungi', groups_dir)
        Virus_tpm_gro = all_group[all_group['kingdom'] == 'k__Viruses']
        get_class_exp(Virus_tpm_gro, 'Virus', groups_dir)


def main():
    parser = argparse.ArgumentParser(description='Taxonomy statistics (update version)')
    parser.add_argument('-I', '--i_datadir', type=str, required=True, default='data', help='the dir of sample.txt')
    parser.add_argument('--Annotation', type=str, default='Annotation', help='the res of Annotation')
    parser.add_argument('--resdir', type=str, default='Result', help='the resdir')
    args = parser.parse_args()

    datadir = os.path.abspath(args.i_datadir)
    anno_dir = os.path.abspath(args.Annotation)
    res_dir = os.path.abspath(args.resdir)

    try:
        log.info('开始生成物种丰度表')
        get_table(anno_dir, datadir, res_dir)
        log.info('开始生成 Krona 图')
        krona(res_dir, anno_dir, datadir)
        log.info('物种统计完成')
    except Exception as e:
        log.error('物种统计失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
