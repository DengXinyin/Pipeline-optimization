#!/usr/bin/env python
# -*- coding: utf-8 -*-
# By: Wang Li 2024
# 20260618_update_V1: 修复 Docker 挂载点 /megahit 已存在时 FileExistsError 的问题；
#                      调用优化后的 megahit_update_V1.sh，支持 pigz 和可调整并行参数。
# 注意：此版本每个样本 24 线程、同时跑 3 个样本，整体 wall-clock 反而慢于原代码。
#      已保留为 V1，当前优化版见 megahit_update.py / megahit_update.sh。

import os
import shutil
import argparse


def megahit(host, cleandir, host_dir, datadir, tmpdir, scripts_path):
    if not os.path.exists(os.path.join(tmpdir, 'length')):
        os.mkdir(os.path.join(tmpdir, 'length'))
    if host == 'none':
        cmd = '''
bash {0}/megahit_update_V1.sh {1} {2} {3} 'none'
'''.format(scripts_path, datadir, cleandir, tmpdir)
    else:
        cmd = '''
        bash {0}/megahit_update_V1.sh {1} {2} {3} 'host'
        '''.format(scripts_path, datadir, host_dir, tmpdir)
    os.system(cmd)


def main():
    parser = argparse.ArgumentParser(description='This script will assemble sequence through megahit')
    parser.add_argument('-I', '--i_datadir', type=str, required=True, default='data', help='the dir of sample.txt')
    parser.add_argument('--megahit', type=str, default='megahit', help='the res of megahit')
    parser.add_argument('--host_dir', type=str, default='de_host', help='the dir of dehost_data')
    parser.add_argument('--cleandir', type=str, default='cleandata', help='the dir of clean_data')
    parser.add_argument('--host', type=str, required=True, nargs='*', help='the host of metagenome')
    args = parser.parse_args()

    datadir = os.path.abspath(args.i_datadir)
    megahit_dir = os.path.abspath(args.megahit)
    cleandadir = os.path.abspath(args.cleandir)
    host_dir = os.path.abspath(args.host_dir)
    host = args.host[0]

    # 当 megahit_dir 是 Docker 挂载点时，不能删除目录本身，只清空内容
    if not os.path.exists(megahit_dir):
        os.mkdir(megahit_dir)
    else:
        for item in os.listdir(megahit_dir):
            item_path = os.path.join(megahit_dir, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path, ignore_errors=True)
            else:
                os.remove(item_path)

    scripts_path = os.path.dirname(os.path.abspath(__file__))
    megahit(host, cleandadir, host_dir, datadir, megahit_dir, scripts_path)


if __name__ == '__main__':
    main()
