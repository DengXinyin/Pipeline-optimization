#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Update version of tax_base.py

import os
import sys
import argparse
import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from get_scriptspath_update import scripts_path, Rscript_j
from subprocess_log_utils import run_with_failure_log

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
        run_with_failure_log(krona_cmd, log_file, stop_dir=res_dir)


def _run_r_script(r_script, cmd, log_file):
    """运行单个 R 脚本，返回 (r_script, None) 或抛出异常。"""
    run_with_failure_log(
        cmd,
        log_file,
        stop_dir=os.path.dirname(os.path.dirname(log_file)),
    )
    return r_script


def plot(datadir, res_dir, pre_resdir, max_workers=None):
    log_dir = os.path.join(res_dir, 'logs', 'tax_base')
    os.makedirs(log_dir, exist_ok=True)
    r_scripts = [
        'tax_bar_plot_update.R',
        'bar_tree_update.R',
        'tax_heatmap_update.R',
        'tax_PCA_update.R',
        'tax_PCoA_update.R',
        'tax_NMDS_update.R',
    ]
    cmds = []
    for r_script in r_scripts:
        log_file = os.path.join(log_dir, r_script.replace('.R', '.log'))
        cmd = [Rscript_j, os.path.join(scripts_path, r_script), pre_resdir, datadir, res_dir]
        cmds.append((r_script, cmd, log_file))

    if max_workers is None:
        max_workers = min(len(cmds), os.cpu_count() or 1)
    log.info('启动 %d 个 R 可视化脚本并行运行', max_workers)

    errors = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_run_r_script, r_script, cmd, log_file): r_script
            for r_script, cmd, log_file in cmds
        }
        for future in as_completed(futures):
            r_script = futures[future]
            try:
                future.result()
                log.info('R 脚本完成: %s', r_script)
            except Exception as exc:
                log.error('R 脚本失败: %s, 错误: %s', r_script, exc)
                errors.append(r_script)

    if errors:
        raise RuntimeError(f'以下 R 脚本运行失败: {", ".join(errors)}')


def main():
    parser = argparse.ArgumentParser(description='Taxonomy base statistics and visualization (update version)')
    parser.add_argument('-I', '--i_datadir', type=str, default='data', help='the dir of sample-metadata.tsv')
    parser.add_argument('--Annotation', type=str, default='Annotation', help='the res of Annotation')
    parser.add_argument('--resdir', type=str, default='Result', help='the resdir')
    parser.add_argument('--pre_resdir', type=str, default='Result', help='the pre result dir used by R scripts')
    parser.add_argument('-j', '--jobs', type=int, default=None,
                        help='R 可视化脚本并行数（默认自动，最多 6）')
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
        plot(datadir, res_dir, pre_resdir, max_workers=args.jobs)
        log.info('tax_base 完成')
    except subprocess.CalledProcessError as e:
        log.error('外部命令执行失败: %s', e)
        sys.exit(1)
    except Exception as e:
        log.error('tax_base 运行失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
