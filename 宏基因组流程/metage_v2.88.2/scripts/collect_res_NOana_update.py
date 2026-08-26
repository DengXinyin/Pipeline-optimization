#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Update version of collect_res_NOana.py

import os
import sys
import argparse
import logging
import shutil

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)


def merge_dir(src, dst):
    """递归合并 src 到 dst。dst 中已存在的内容保留，只新增/覆盖 src 中的内容。"""
    if not os.path.isdir(src):
        raise FileNotFoundError(f'源目录不存在: {src}')
    src = os.path.abspath(src)
    dst = os.path.abspath(dst)
    if src == dst:
        log.info('源目录与目标目录相同，跳过复制: %s', src)
        return
    if not os.path.exists(dst):
        shutil.copytree(src, dst)
        log.info('复制 %s -> %s', src, dst)
        return
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            merge_dir(s, d)
        else:
            shutil.copy2(s, d)
    log.info('合并 %s -> %s', src, dst)


def main():
    parser = argparse.ArgumentParser(description='Collect analysis results without differential analysis (update version)')
    parser.add_argument('--res1', type=str, required=True, help='result directory 1 (e.g. Result)')
    parser.add_argument('--res2', type=str, required=True, help='result directory 2 (e.g. tax_base)')
    parser.add_argument('--res3', type=str, required=True, help='result directory 3 (e.g. func_base)')
    parser.add_argument('--readme', type=str, required=True, help='directory containing README_NOana.txt')
    parser.add_argument('--outdir', type=str, default='Result_update', help='output parent directory')
    args = parser.parse_args()

    outdir = os.path.abspath(args.outdir)
    os.makedirs(outdir, exist_ok=True)

    for src in [args.res1, args.res2, args.res3]:
        src = os.path.abspath(src)
        dst = os.path.join(outdir, os.path.basename(src))
        merge_dir(src, dst)

    readme_src = os.path.join(os.path.abspath(args.readme), 'README_NOana.txt')
    readme_dst = os.path.join(outdir, 'Result', 'README_NOana.txt')
    if not os.path.exists(readme_src):
        log.error('README 不存在: %s', readme_src)
        sys.exit(1)
    os.makedirs(os.path.dirname(readme_dst), exist_ok=True)
    shutil.copy2(readme_src, readme_dst)
    log.info('复制 README: %s -> %s', readme_src, readme_dst)


if __name__ == '__main__':
    try:
        main()
        log.info('collect_res_NOana 完成')
    except Exception as e:
        log.error('collect_res_NOana 失败: %s', e)
        sys.exit(1)
