#!/usr/bin/env python
# -*- coding: utf-8 -*-
# By: Wang Li 2024

import os
import ast
import shutil
import argparse
from get_scriptspath import scripts_path
import pandas as pd

def drep(datadir, bining_dir, drep_dir):
    cmd = '''
        bash {0}/drep.sh {1} {2} {3}
        '''.format(scripts_path, datadir, bining_dir, drep_dir)
    os.system(cmd)


def check_stats(drep_dir):
    check_res = []
    with open('%s/checkm/storage/bin_stats_ext.tsv' % drep_dir, 'r', encoding='utf-8') as f:
        data = f.readlines()
        for line in data:
            bin_id = line.split('\t')[0]
            stats_dict = ast.literal_eval(line.split('\t')[1])
            Completeness = stats_dict['Completeness']
            Contamination = stats_dict['Contamination']
            GC = stats_dict['GC']
            # Genome_size = stats_dict['Genome size']
            # N50 = stats_dict['N50 (contigs)']

            check_res.append({
            'Bin_ID': bin_id,
            'Completeness': Completeness,
            'Contamination': Contamination,
            'GC_percent': GC})
    check_df = pd.DataFrame(check_res)

    # N50等信息合并
    bins_dat = pd.read_csv('%s/drep/stats/bin.all.stats' % drep_dir, sep='\t')
    bins_dat['Bin_ID'] = bins_dat['Bin_ID'].apply(lambda x: x.split('.fa')[0])
    merge_stats = pd.merge(left=check_df, right=bins_dat, on='Bin_ID')
    merge_stats = merge_stats.sort_values('Bin_ID')
    merge_stats.to_csv('%s/checkm/bins_stats.txt' % drep_dir, index=False, sep='\t')


def main():
    parser = argparse.ArgumentParser(description='This script will drep the bins')
    parser.add_argument('-I', '--i_datadir', type=str, required=True,default='data', help='the dir of sample.txt')
    parser.add_argument('--drep', type=str,default='drep', help='the res of drep')
    parser.add_argument('--binning', type=str,default='binning', help='the res of binning')
    args = parser.parse_args()

    datadir = os.path.abspath(args.i_datadir)
    drep_dir = os.path.abspath(args.drep)
    binning_dir = os.path.abspath(args.binning)
    if not os.path.exists(drep_dir):
        os.mkdir(drep_dir)
    else:
        shutil.rmtree(drep_dir, ignore_errors=True)
        os.mkdir(drep_dir)

    # drep_dir = r'D:\宏基因组更新'

    drep(datadir, binning_dir, drep_dir)
    check_stats(drep_dir)


if __name__ == '__main__':
    main()
