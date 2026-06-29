#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Update version of tax_base.py

import os
import sys
import argparse
import logging
import subprocess

import pandas as pd
from get_scriptspath_update import scripts_path, Rscript_j

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)


def krona(res_dir, anno_dir, datadir):
    krona_tmpdir = os.path.join(anno_dir, 'krona')
    os.makedirs(krona_tmpdir, exist_ok=True)
    species_ls = ['kingdom', 'phylum', 'class', 'order', 'family', 'genus', 'species']

    all_dat = pd.read_csv(os.path.join(anno_dir, 'All', 'All.taxonomy.csv'))
    all_dat = all_dat.drop(['GeneID'], axis=1)
    all_dat = all_dat.groupby(by=species_ls, as_index=False).sum()

    sam_gros = pd.read_csv(
        os.path.join(datadir, 'sample-metadata.tsv'),
        sep='\t', skiprows=[1], dtype=str
    )
    k = sam_gros.shape[1]
    for i in range(1, k):
        sam_gro = sam_gros.iloc[:, [0] + [i]]
        sam_gro = sam_gro.dropna(axis=0).reset_index(drop=True)
        samples = sam_gro['sample-id'].to_list()
        group_num = 'group' + str(i)
        res_grodir = os.path.join(res_dir, group_num, '5-TaxAnnotation', '2.Krona')
        os.makedirs(res_grodir, exist_ok=True)

        gro_dat = all_dat.loc[:, species_ls + samples]
        command_str = ''
        for j in range(7, gro_dat.shape[1]):
            sample_tax = gro_dat.iloc[:, [j] + list(range(0, 7))]
            sample_name = gro_dat.columns[j]
            sample_file = os.path.join(krona_tmpdir, f'{sample_name}.txt')
            sample_tax.to_csv(sample_file, sep='\t', index=False)
            command_str = command_str + sample_file + ' '

        krona_html = os.path.join(res_grodir, 'krona.html')
        krona_cmd = ['ktImportText'] + command_str.split() + ['-o', krona_html]
        log_file = os.path.join(res_grodir, 'krona.log')
        log.info('[%s] 生成 Krona: %s', group_num, krona_html)
        with open(log_file, 'w') as lf:
            subprocess.run(krona_cmd, stdout=lf, stderr=subprocess.STDOUT, check=True)


def plot(datadir, res_dir, pre_resdir):
    log_dir = os.path.join(res_dir, 'logs', 'tax_base')
    os.makedirs(log_dir, exist_ok=True)
    r_scripts = [
        'tax_bar_plot.R',
        'bar_tree.R',
        'tax_heatmap.R',
        'tax_PCA.R',
        'tax_PCoA.R',
        'tax_NMDS.R',
    ]
    cmds = []
    for r_script in r_scripts:
        log_file = os.path.join(log_dir, r_script.replace('.R', '.log'))
        cmd = [Rscript_j, os.path.join(scripts_path, r_script), pre_resdir, datadir, res_dir]
        cmds.append((r_script, cmd, log_file))

    for r_script, cmd, log_file in cmds:
        log.info('运行 R 脚本: %s', r_script)
        with open(log_file, 'w') as lf:
            subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, check=True)


def main():
    parser = argparse.ArgumentParser(description='Taxonomy base statistics and visualization (update version)')
    parser.add_argument('-I', '--i_datadir', type=str, default='data', help='the dir of sample-metadata.tsv')
    parser.add_argument('--Annotation', type=str, default='Annotation', help='the res of Annotation')
    parser.add_argument('--resdir', type=str, default='Result', help='the resdir')
    parser.add_argument('--pre_resdir', type=str, default='Result', help='the pre result dir used by R scripts')
    args = parser.parse_args()

    datadir = os.path.abspath(args.i_datadir)
    anno_dir = os.path.abspath(args.Annotation)
    res_dir = os.path.abspath(args.resdir)
    pre_resdir = os.path.abspath(args.pre_resdir)

    for path in [datadir, anno_dir]:
        if not os.path.exists(path):
            log.error('输入路径不存在: %s', path)
            sys.exit(1)

    try:
        log.info('开始 tax_base Krona 生成')
        krona(res_dir, anno_dir, datadir)
        log.info('开始 tax_base R 可视化')
        plot(datadir, res_dir, pre_resdir)
        log.info('tax_base 完成')
    except subprocess.CalledProcessError as e:
        log.error('外部命令执行失败: %s', e)
        sys.exit(1)
    except Exception as e:
        log.error('tax_base 运行失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
