#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import subprocess
import logging

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


def plot_corv(bowtie_dir, datadir, res_dir):
    cmd = '''{0} {1}/sample.corr_heatmap.R {2} {3} {4}
{0} {1}/venn_flower.R {2} {3} {4}
'''.format(Rscript_j, scripts_path, bowtie_dir, datadir, res_dir)
    run_cmd(cmd)


def res(bowtie_dir, res_dir):
    cmd = '''
    ls -d %s/*/4-GeneAbundance | xargs -i cp %s/gene_tpm.csv {}
    ls -d %s/*/4-GeneAbundance | xargs -i cp %s/gene_count.csv {}
    ''' % (res_dir, bowtie_dir, res_dir, bowtie_dir)
    run_cmd(cmd)


def main():
    parser = argparse.ArgumentParser(description='BWA/bowtie abundance statistics (update version)')
    parser.add_argument('-I', '--i_datadir', type=str, required=True, default='data', help='the dir of sample.txt')
    parser.add_argument('--bowtie', type=str, default='bowtie', help='the res of bowtie')
    parser.add_argument('--resdir', type=str, default='Result', help='the resdir')
    args = parser.parse_args()

    datadir = os.path.abspath(args.i_datadir)
    bowtie_dir = os.path.abspath(args.bowtie)
    res_dir = os.path.abspath(args.resdir)

    try:
        log.info('开始绘制样本相关性热图和 Venn 图')
        plot_corv(bowtie_dir, datadir, res_dir)
        log.info('开始复制基因丰度表')
        res(bowtie_dir, res_dir)
        log.info('BWA 统计完成')
    except Exception as e:
        log.error('BWA 统计失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
