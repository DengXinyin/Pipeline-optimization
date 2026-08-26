#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import subprocess
import logging
import shutil

import pandas as pd
from get_scriptspath import scripts_path, Rscript_j

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)


def run_cmd(cmd):
    log.info('执行命令: %s', cmd.strip().split('\n')[0])
    subprocess.run(cmd, shell=True, check=True)


def load_and_validate_metadata(datadir):
    """读取并校验下游统计所需的样本分组，防止空 group 延迟到绘图阶段才失败。"""
    metadata_path = os.path.join(datadir, 'sample-metadata.tsv')
    sample_path = os.path.join(datadir, 'sample.txt')
    for path in [metadata_path, sample_path]:
        if not os.path.isfile(path):
            raise FileNotFoundError('缺少元数据文件: %s' % path)

    metadata = pd.read_csv(metadata_path, sep='\t', skiprows=[1], dtype=str).fillna('')
    if 'sample-id' not in metadata.columns:
        raise ValueError('sample-metadata.tsv 缺少 sample-id 列')
    group_cols = [c for c in metadata.columns if c != 'sample-id']
    if not group_cols:
        raise ValueError('sample-metadata.tsv 没有任何 group 列')

    metadata['sample-id'] = metadata['sample-id'].astype(str).str.strip()
    if (metadata['sample-id'] == '').any():
        raise ValueError('sample-metadata.tsv 存在空 sample-id')
    if metadata['sample-id'].duplicated().any():
        duplicated = sorted(metadata.loc[metadata['sample-id'].duplicated(keep=False), 'sample-id'].unique())
        raise ValueError('sample-metadata.tsv 存在重复 sample-id: %s' % ', '.join(duplicated))

    for column in group_cols:
        metadata[column] = metadata[column].astype(str).str.strip()
    ungrouped = metadata.loc[(metadata[group_cols] == '').all(axis=1), 'sample-id'].tolist()
    if ungrouped:
        raise ValueError(
            '以下样本没有任何有效分组，请检查 data.xlsx 的 sample.group 和 comparison: %s'
            % ', '.join(ungrouped)
        )
    return metadata, group_cols


def length_table(megahit_dir, datadir, res_dir):
    len_dir = os.path.join(megahit_dir, 'length')
    # length_count_update.R 放在优化脚本同目录，避免依赖原 scripts/ 中的旧版
    update_script_dir = os.path.dirname(os.path.realpath(__file__))
    cmd = '{0} {1}/length_count_update.R {2} {3} {4}'.format(
        Rscript_j, update_script_dir, len_dir, datadir, res_dir)
    run_cmd(cmd)


def get_contigs(megahit_dir, res_dir, datadir):
    metadata, group_cols = load_and_validate_metadata(datadir)
    for group_index, group_col in enumerate(group_cols, start=1):
        group_num = 'group%d' % group_index
        selected = metadata.loc[metadata[group_col] != '', 'sample-id'].tolist()
        for sample in selected:
            source = os.path.join(megahit_dir, sample, 'final.contigs.fa')
            if not os.path.isfile(source):
                raise FileNotFoundError('缺少样本 contig: %s' % source)
            target_dir = os.path.join(res_dir, group_num, '2-Assembly', sample)
            os.makedirs(target_dir, exist_ok=True)
            shutil.copy2(source, os.path.join(target_dir, 'final.contigs.fa'))


def stats_table(megahit_dir, datadir, res_dir):
    stat_dir = os.path.join(megahit_dir, 'length')
    stat_ls = list()
    files = os.listdir(stat_dir)
    for file in files:
        if file.endswith('_stats.txt'):
            prefix = file.split('_stats.txt')[0]
            stat_dat = pd.read_csv('%s/%s' % (stat_dir, file), sep='\t')
            stat_dat = stat_dat.iloc[:, list(range(0, 6)) + [8]]
            stat_dat.loc[:, 'filename'] = prefix
            stat_dat = stat_dat.rename(columns={'filename': 'sample', 'number': 'num_contigs',
                                                'total_length': 'total_length(bp)', 'shortest': 'min_length',
                                                'longest': 'max_length', 'mean_length': 'average_length', 'N50': 'N50'})
            stat_ls.append(stat_dat)
    statat = pd.concat(stat_ls, axis=0)
    statat.to_excel('%s/assembly_stat.xlsx' % megahit_dir, index=False)

    sam_gros = pd.read_csv('%s/sample-metadata.tsv' % datadir, sep='\t', skiprows=[1], dtype=str)
    k = sam_gros.shape[1]
    for i in range(1, k):
        sam_gro = sam_gros.iloc[:, [0] + [i]]
        sam_gro = sam_gro.dropna(axis=0).reset_index(drop=True)
        group_num = 'group' + str(i)

        sam_df = pd.merge(left=sam_gro, right=statat, left_on='sample-id', right_on='sample', how='inner')
        sam_df = sam_df.drop(['sample-id', group_num], axis=1)
        grodir = os.path.join(res_dir, group_num)
        os.makedirs(grodir, exist_ok=True)
        assembly_dir = os.path.join(grodir, '2-Assembly')
        os.makedirs(assembly_dir, exist_ok=True)
        sam_df.to_excel(os.path.join(assembly_dir, 'assembly_stat.xlsx'), index=False)


def main():
    parser = argparse.ArgumentParser(description='MEGAHIT assembly statistics (update version)')
    parser.add_argument('-I', '--i_datadir', type=str, required=True, default='data', help='the dir of sample.txt')
    parser.add_argument('--megahit', type=str, default='megahit', help='the res of megahit')
    parser.add_argument('--resdir', type=str, default='Result', help='the resdir')
    args = parser.parse_args()

    datadir = os.path.abspath(args.i_datadir)
    megahit_dir = os.path.abspath(args.megahit)
    res_dir = os.path.abspath(args.resdir)

    try:
        load_and_validate_metadata(datadir)
        log.info('开始 MEGAHIT 长度统计图')
        length_table(megahit_dir, datadir, res_dir)
        log.info('开始复制组装结果到各分组')
        get_contigs(megahit_dir, res_dir, datadir)
        log.info('开始生成组装统计表')
        stats_table(megahit_dir, datadir, res_dir)
        log.info('MEGAHIT 统计完成')
    except Exception as e:
        log.error('MEGAHIT 统计失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
