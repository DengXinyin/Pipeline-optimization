#!/usr/bin/env python
# -*- coding: utf-8 -*-
import argparse
import glob
import logging
import os
import re
import sys

from Bio import Phylo
from beta_four_distances import read_abundance, read_metadata, read_tree, run_four
from ncbi_taxonomy_tree import NCBITaxonomy, write_mapping

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='物种四类 Beta 距离及 PCoA/NMDS')
    parser.add_argument('-I', '--i_datadir', required=True)
    parser.add_argument('--tree', default=None,
                        help='可选的自定义 Newick 树；默认使用 --taxonomy-dir 自动裁剪')
    parser.add_argument('--taxonomy-dir', default=None,
                        help='包含 nodes.dmp/names.dmp/merged.dmp 的 NCBI taxonomy 目录')
    parser.add_argument('--tax_table', default=None)
    parser.add_argument('--resdir', default='Result')
    parser.add_argument('--outdir', default='tax_unifrac')
    parser.add_argument('--embed-beta', action='store_true',
                        help='写入现有 6.Beta_diversity_analysis/.../2.PCoA 目录')
    args = parser.parse_args()
    try:
        if bool(args.tree) == bool(args.taxonomy_dir):
            raise ValueError('--tree 与 --taxonomy-dir 必须且只能提供一个')
        metadata = read_metadata(args.i_datadir)
        custom_tree = read_tree(args.tree) if args.tree else None
        taxonomy = NCBITaxonomy(args.taxonomy_dir) if args.taxonomy_dir else None
        if args.tax_table:
            tables = [os.path.abspath(args.tax_table)]
        else:
            tables = sorted(glob.glob(os.path.join(os.path.abspath(args.resdir), 'group*',
                '5-TaxAnnotation', '1.Tables', 'Samples', '*', 'species.xlsx')))
        if not tables:
            raise FileNotFoundError('tax_base Result 中未找到 species.xlsx')
        completed, failures, summaries = 0, [], []
        for table in tables:
            relative = os.path.relpath(table, os.path.abspath(args.resdir))
            try:
                group = next((part for part in relative.split(os.sep)
                              if re.fullmatch(r'group\d+', part)), None)
                if group is None:
                    raise ValueError('无法从物种表路径识别 groupN: %s' % table)
                tax_class = table.split(os.sep)[-2]
                if args.embed_beta:
                    outdir = os.path.join(os.path.abspath(args.outdir), group,
                        '5-TaxAnnotation', '6.Beta_diversity_analysis', tax_class,
                        'species', '2.PCoA')
                    nmds_outdir = os.path.join(os.path.abspath(args.outdir), group,
                        '5-TaxAnnotation', '6.Beta_diversity_analysis', tax_class,
                        'species', '3.NMDS')
                else:
                    outdir = os.path.join(os.path.abspath(args.outdir), group,
                                          tax_class, 'species')
                    nmds_outdir = os.path.join(outdir, '3.NMDS')
                abundance = read_abundance(
                    table, metadata['sample-id'].tolist(), excel_sheet='relative')
                tree = custom_tree
                mapping_rows = None
                if taxonomy:
                    resolved, unmapped, ambiguous = taxonomy.resolve_features(
                        abundance.index, result_root=args.resdir)
                    if len(resolved) < 2:
                        raise ValueError('仅 %d 个非零物种可映射到 NCBI TaxID' % len(resolved))
                    mapping_rows = (list(abundance.index), resolved, unmapped, ambiguous)
                    # merged.dmp 可能把多个旧物种TaxID合并为同一现行TaxID。
                    # 先按现行TaxID合并丰度，保证四种距离使用完全相同的特征集合。
                    abundance = abundance.loc[list(resolved)].copy()
                    abundance.index = [resolved[x] for x in abundance.index]
                    abundance = abundance.groupby(level=0, sort=False).sum()
                    if len(abundance) < 2:
                        raise ValueError('合并旧TaxID后非零物种少于 2 个')
                    tree = taxonomy.build_tree({x: x for x in abundance.index})
                matched = run_four(
                    abundance, tree, outdir, metadata,
                    '%s/%s/species' % (group, tax_class), group_column=group,
                    merge_existing=args.embed_beta, nmds_outdir=nmds_outdir)
                if mapping_rows:
                    os.makedirs(outdir, exist_ok=True)
                    write_mapping(os.path.join(outdir, 'species_taxid_map.tsv'), *mapping_rows)
                    Phylo.write(tree, os.path.join(outdir, 'ncbi_taxonomy_pruned.nwk'), 'newick')
                    with open(os.path.join(outdir, 'UNIFRAC_METHOD.txt'), 'w', encoding='utf-8') as handle:
                        handle.write('NCBI taxonomy parent-child edges; unit branch length = 1.0\n')
                completed += 1
                summaries.append((relative, len(mapping_rows[0]) if mapping_rows else matched,
                                  matched, len(mapping_rows[2]) if mapping_rows else 0,
                                  len(mapping_rows[3]) if mapping_rows else 0))
                log.info('%s 完成，UniFrac 匹配 %d 个树叶节点', table, matched)
            except Exception as error:
                failures.append('%s\t%s' % (relative, error))
                log.warning('%s 跳过: %s', relative, error)
        os.makedirs(os.path.abspath(args.outdir), exist_ok=True)
        with open(os.path.join(os.path.abspath(args.outdir),
                               'tax_four_distances_skipped.tsv'), 'w', encoding='utf-8') as handle:
            handle.write('table\treason\n' + '\n'.join(failures) + ('\n' if failures else ''))
        with open(os.path.join(os.path.abspath(args.outdir),
                               'tax_four_distances_summary.tsv'), 'w', encoding='utf-8') as handle:
            handle.write('table\tinput_features\ttree_tips\tunmapped\tambiguous\tbranch_model\n')
            for row in summaries:
                handle.write('\t'.join(map(str, row)) + '\tNCBI_taxonomy_unit_edge_1.0\n')
        if completed == 0:
            log.warning('没有物种表满足四距离计算条件；原因已写入 skipped TSV')
    except Exception as error:
        log.error('物种四距离分析失败: %s', error)
        sys.exit(1)


if __name__ == '__main__':
    main()
