#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Update version of get_groups.py

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


def get_groups(datadir, resdir):
    sample_group = pd.read_csv(os.path.join(datadir, 'sample-metadata.tsv'), sep='\t')
    if len(sample_group) <= 1:
        log.warning('sample-metadata.tsv 数据行不足，跳过删除第二行')
    else:
        sample_group = sample_group.drop([0], axis=0)
    out_file = os.path.join(resdir, '分组信息表.xlsx')
    os.makedirs(resdir, exist_ok=True)
    sample_group.to_excel(out_file, index=False)
    log.info('保存分组信息表: %s', out_file)


def main():
    parser = argparse.ArgumentParser(description='Generate group information table (update version)')
    parser.add_argument('-I', '--i_datadir', type=str, default='data', help='the dir of sample-metadata.tsv')
    parser.add_argument('--res', type=str, default='Result', help='the dir of res')
    args = parser.parse_args()

    datadir = os.path.abspath(args.i_datadir)
    resdir = os.path.abspath(args.res)

    if not os.path.exists(datadir):
        log.error('数据目录不存在: %s', datadir)
        sys.exit(1)

    try:
        get_groups(datadir, resdir)
        log.info('get_groups 完成')
    except Exception as e:
        log.error('get_groups 失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
