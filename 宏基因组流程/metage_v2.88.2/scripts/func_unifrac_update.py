#!/usr/bin/env python
# -*- coding: utf-8 -*-
import argparse
import glob
import logging
import os
import re
import sys

from beta_four_distances import read_abundance, read_metadata, read_tree, run_four

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='功能注释四类 Beta 距离及 PCoA')
    parser.add_argument('-I', '--i_datadir', required=True)
    parser.add_argument('--tree', required=True)
    parser.add_argument('--func_table', default=None)
    parser.add_argument('--func_tmp', default='func_base')
    parser.add_argument('--outdir', default='func_unifrac')
    args = parser.parse_args()
    try:
        metadata, tree = read_metadata(args.i_datadir), read_tree(args.tree)
        root = os.path.abspath(args.func_tmp)
        tables = [os.path.abspath(args.func_table)] if args.func_table else sorted(
            glob.glob(os.path.join(root, 'group*', '**', '*_sam.tsv'), recursive=True))
        if not tables:
            raise FileNotFoundError('func_base 中未找到 *_sam.tsv')
        failures, completed = [], 0
        for table in tables:
            relative = os.path.relpath(table, root)
            outdir = os.path.join(os.path.abspath(args.outdir), os.path.splitext(relative)[0])
            try:
                group = next((part for part in relative.split(os.sep)
                              if re.fullmatch(r'group\d+', part)), None)
                if group is None:
                    raise ValueError('无法从功能表路径识别 groupN')
                abundance = read_abundance(table, metadata['sample-id'].tolist())
                matched = run_four(abundance, tree, outdir, metadata, relative, group_column=group)
                completed += 1
                log.info('%s 完成，UniFrac 匹配 %d 个树叶节点', relative, matched)
            except Exception as error:
                failures.append('%s\t%s' % (relative, error))
                log.warning('%s 跳过: %s', relative, error)
        os.makedirs(os.path.abspath(args.outdir), exist_ok=True)
        with open(os.path.join(os.path.abspath(args.outdir), 'skipped_tables.tsv'), 'w', encoding='utf-8') as handle:
            handle.write('table\treason\n' + '\n'.join(failures) + ('\n' if failures else ''))
        if completed == 0:
            raise RuntimeError('没有任何功能表完成四类距离计算，详见 skipped_tables.tsv')
    except Exception as error:
        log.error('功能四距离分析失败: %s', error)
        sys.exit(1)


if __name__ == '__main__':
    main()
