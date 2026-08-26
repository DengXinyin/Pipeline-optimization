#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Update version of collect_res_bins.py

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


def collect_kraken2(outdir, raw_dir=None, tax_base_dir=None, tax_diff_dir=None):
    """Add optional Kraken2 outputs to the delivered result directory."""
    sources = [
        ('1-Raw_annotation', raw_dir),
        ('2-Taxonomy_statistics', tax_base_dir),
        ('3-Differential_analysis', tax_diff_dir),
    ]
    sources = [(label, path) for label, path in sources if path]
    if not sources:
        return

    kraken_dir = os.path.join(outdir, 'Result', '17-Kraken2')
    manifest_rows = []
    for label, src in sources:
        if not os.path.isdir(src):
            raise FileNotFoundError(f'Kraken2 源目录不存在: {src}')
        dst = os.path.join(kraken_dir, label)
        merge_dir(src, dst)
        for root, _, files in os.walk(dst):
            for filename in sorted(files):
                path = os.path.join(root, filename)
                manifest_rows.append((label, os.path.relpath(path, kraken_dir), os.path.getsize(path)))

    manifest = os.path.join(kraken_dir, 'Kraken2_result_manifest.tsv')
    with open(manifest, 'w', encoding='utf-8') as handle:
        handle.write('result_category\trelative_path\tsize_bytes\n')
        for row in manifest_rows:
            handle.write('\t'.join(map(str, row)) + '\n')
    log.info('已汇总 Kraken2 结果: %s（%d 个文件）', kraken_dir, len(manifest_rows))


def main():
    parser = argparse.ArgumentParser(description='Collect analysis results with bins (update version)')
    parser.add_argument('--res1', type=str, required=True, help='result directory 1 (e.g. Result)')
    parser.add_argument('--res2', type=str, required=True, help='result directory 2 (e.g. tax_base)')
    parser.add_argument('--res3', type=str, required=True, help='result directory 3 (e.g. func_base)')
    parser.add_argument('--res4', type=str, required=True, help='result directory 4 (e.g. tax_diff)')
    parser.add_argument('--res5', type=str, required=True, help='result directory 5 (e.g. func_diff)')
    parser.add_argument('--res6', type=str, required=True, help='result directory 6 (e.g. bins_stats_Result)')
    parser.add_argument('--kraken2-anno', type=str, default=None, help='optional Kraken2 raw annotation directory')
    parser.add_argument('--kraken2-tax-base', type=str, default=None, help='optional Kraken2 taxonomy statistics directory')
    parser.add_argument('--kraken2-tax-diff', type=str, default=None, help='optional Kraken2 differential analysis directory')
    parser.add_argument('--readme', type=str, required=True, help='directory containing README_bins.txt')
    parser.add_argument('--outdir', type=str, default='Result_update', help='output parent directory')
    args = parser.parse_args()

    outdir = os.path.abspath(args.outdir)
    os.makedirs(outdir, exist_ok=True)

    for src in [args.res1, args.res2, args.res3, args.res4, args.res5, args.res6]:
        src = os.path.abspath(src)
        dst = os.path.join(outdir, os.path.basename(src))
        merge_dir(src, dst)

    collect_kraken2(outdir, args.kraken2_anno, args.kraken2_tax_base, args.kraken2_tax_diff)

    readme_src = os.path.join(os.path.abspath(args.readme), 'README_bins.txt')
    readme_dst = os.path.join(outdir, 'Result', 'README_bins.txt')
    if not os.path.exists(readme_src):
        log.error('README 不存在: %s', readme_src)
        sys.exit(1)
    os.makedirs(os.path.dirname(readme_dst), exist_ok=True)
    shutil.copy2(readme_src, readme_dst)
    log.info('复制 README: %s -> %s', readme_src, readme_dst)


if __name__ == '__main__':
    try:
        main()
        log.info('collect_res_bins 完成')
    except Exception as e:
        log.error('collect_res_bins 失败: %s', e)
        sys.exit(1)
