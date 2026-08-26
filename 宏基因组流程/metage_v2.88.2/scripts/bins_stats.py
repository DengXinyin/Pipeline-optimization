#!/usr/bin/env python
# -*- coding: utf-8 -*-
# By: Wang Li 2024

import os
import glob
import ast
import shutil
import argparse
from get_scriptspath import scripts_path, Rscript_j
import pandas as pd

def get_table(classfiDir, drep_dir, resdir):
    res_dir_1 = os.path.join(resdir, 'binning', '1.Bin')
    res_dir_4 = os.path.join(resdir, 'binning', '4.Bin_classify')
    dirs_index = [res_dir_1, res_dir_4]
    for dirs_i in dirs_index:
        if not os.path.exists(dirs_i):
            os.makedirs(dirs_i)
    if not os.path.exists(os.path.join(res_dir_1, 'bins')):
        os.makedirs(os.path.join(res_dir_1, 'bins'))
    fa_files = glob.glob('%s/drep/dereplicated_genomes/*.fa' % drep_dir)
    for fa_file in fa_files:
        shutil.copy(fa_file, '%s/bins' % res_dir_1)
    bins_stat = pd.read_csv('%s/checkm/bins_stats.txt' % drep_dir, sep='\t')
    bins_stat.to_excel('%s/bins_stats.xlsx' % res_dir_1, index=False)

    classf_dat = pd.read_csv('%s/bin_taxonomy.tab' % classfiDir, sep='\t')
    classf_dat['bin'] = classf_dat['bin'].apply(lambda x: x.split('.fa')[0])
    classf_dat.to_excel('%s/bins_classify.xlsx' % res_dir_4, index=False)


def plot_pic(blobology_dir, quantDir, resdir):
    cmd = '''
        {0} {1}/GC-cov.R {2} {3}
        {0} {1}/bins_heatmap.R {4} {3}
        '''.format(Rscript_j, scripts_path, blobology_dir, resdir, quantDir)
    os.system(cmd)


def main():
    parser = argparse.ArgumentParser(description='This script will drep the bins')
    parser.add_argument('--blobology', type=str,default='blobology', help='the res of blobology')
    parser.add_argument('--quantDir', type=str,default='quant_bins', help='the res of quant_bins')
    parser.add_argument('--drep', type=str,default='drep', help='the res of drep')
    parser.add_argument('--classfiDir', type=str,default='bin_classfication', help='the res of bin_classfication')
    parser.add_argument('--resdir', type=str, default='Result', help='the resdir')
    args = parser.parse_args()

    blobology_dir = os.path.abspath(args.blobology)
    drep_dir = os.path.abspath(args.drep)
    quantDir = os.path.abspath(args.quantDir)
    classfiDir = os.path.abspath(args.classfiDir)
    resdir = os.path.abspath(args.resdir)

    get_table(classfiDir, drep_dir, resdir)
    plot_pic(blobology_dir, quantDir, resdir)

if __name__ == '__main__':
    main()
