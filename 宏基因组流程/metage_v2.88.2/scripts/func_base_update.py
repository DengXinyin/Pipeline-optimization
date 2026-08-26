#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Update version of func_base.py

import os
import sys
import argparse
import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

from get_scriptspath_update import scripts_path, Rscript_j
from subprocess_log_utils import run_with_failure_log

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)


def plot_func(func_tmpdir, datadir, res_dir):
    log_dir = os.path.join(res_dir, 'logs', 'func_base')
    os.makedirs(log_dir, exist_ok=True)
    r_scripts = [
        'func_barplot_update.R',
        'func_heatmap_update.R',
        'func_PCA_update.R',
        'func_PCOA_update.R',
        'func_NMDS_update.R',
    ]

    def run_r(r_script):
        log_file = os.path.join(log_dir, r_script.replace('.R', '.log'))
        cmd = [Rscript_j, os.path.join(scripts_path, r_script), func_tmpdir, datadir, res_dir]
        log.info('运行 R 脚本: %s', r_script)
        run_with_failure_log(cmd, log_file, stop_dir=res_dir)
        return r_script

    errors = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(run_r, r): r for r in r_scripts}
        for future in as_completed(futures):
            r_script = futures[future]
            try:
                future.result()
            except Exception as exc:
                log.error('R 脚本 %s 运行失败: %s', r_script, exc)
                errors.append(r_script)
    if errors:
        raise RuntimeError(f'以下 R 脚本失败: {", ".join(errors)}')


def main():
    parser = argparse.ArgumentParser(description='Function annotation visualization (update version)')
    parser.add_argument('-I', '--i_datadir', type=str, default='data', help='the dir of sample-metadata.tsv')
    parser.add_argument('--resdir', type=str, default='Result', help='the resdir')
    parser.add_argument('--func_tmp', type=str, default='func_base', help='the func_base tmp dir')
    args = parser.parse_args()

    datadir = os.path.abspath(args.i_datadir)
    res_dir = os.path.abspath(args.resdir)
    func_tmpdir = os.path.abspath(args.func_tmp)

    if not os.path.exists(datadir):
        log.error('输入路径不存在: %s', datadir)
        sys.exit(1)

    try:
        log.info('开始功能注释可视化')
        plot_func(func_tmpdir, datadir, res_dir)
        log.info('func_base 完成')
    except subprocess.CalledProcessError as e:
        log.error('外部命令执行失败: %s', e)
        sys.exit(1)
    except Exception as e:
        log.error('func_base 运行失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
