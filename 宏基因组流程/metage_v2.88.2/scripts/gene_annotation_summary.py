#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build one-row-per-GeneID summary from all v2.88.2 annotation databases."""

import argparse
import logging
import os
import sys

import pandas as pd


logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

TAXONOMY_RANKS = ['kingdom', 'phylum', 'class', 'order', 'family', 'genus', 'species']
EXCEL_MAX_DATA_ROWS = 1048575


def clean_value(value):
    if pd.isna(value):
        return ''
    value = str(value).strip()
    return '' if value.lower() in {'', 'nan', 'none', 'na', 'n/a', '-'} else value


def join_unique(series):
    seen = set()
    result = []
    for value in series:
        value = clean_value(value)
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return ';'.join(result)


def read_table(path):
    if path.lower().endswith(('.xlsx', '.xls')):
        return pd.read_excel(path, dtype=str)
    return pd.read_csv(path, dtype=str, low_memory=False)


def find_gene_column(frame, path):
    candidates = ['GeneID', 'gene_id', 'Gene ID', 'query', '#query']
    for column in candidates:
        if column in frame.columns:
            return column
    raise ValueError('没有找到 GeneID 列: %s；实际列: %s' % (path, ', '.join(map(str, frame.columns))))


def taxonomy_table(annotation_dir):
    path = os.path.join(annotation_dir, 'All', 'All.taxonomy.csv')
    frame = read_table(path)
    gene_column = find_gene_column(frame, path)
    frame = frame.rename(columns={gene_column: 'GeneID'})
    frame['GeneID'] = frame['GeneID'].map(clean_value)
    available = [rank for rank in TAXONOMY_RANKS if rank in frame.columns]
    if not available:
        raise ValueError('物种表缺少界门纲目科属种字段: %s' % path)

    def combine(row):
        # 保留层级位置；缺失层级统一写 unclassified。
        return '_'.join(clean_value(row.get(rank, '')) or 'unclassified' for rank in TAXONOMY_RANKS)

    frame['taxonomy'] = frame.apply(combine, axis=1)
    return frame.loc[frame['GeneID'] != '', ['GeneID', 'taxonomy']].groupby(
        'GeneID', as_index=False, sort=False
    ).agg({'taxonomy': join_unique})


def annotation_table(path, database, sample_ids):
    frame = read_table(path)
    gene_column = find_gene_column(frame, path)
    frame = frame.rename(columns={gene_column: 'GeneID'})
    frame['GeneID'] = frame['GeneID'].map(clean_value)
    frame = frame.loc[frame['GeneID'] != ''].copy()

    excluded = set(sample_ids) | {'GeneID', 'taxonomy'} | set(TAXONOMY_RANKS)
    annotation_columns = [column for column in frame.columns if column not in excluded]
    # TPM files occasionally carry generic abundance/length columns that are not annotations.
    annotation_columns = [column for column in annotation_columns
                          if str(column).strip().lower() not in {'tpm', 'abundance'}]
    if not annotation_columns:
        log.warning('%s 没有可汇总的注释字段，跳过: %s', database, path)
        return None

    selected = frame[['GeneID'] + annotation_columns].copy()
    renamed = {}
    for column in annotation_columns:
        name = str(column).strip()
        renamed[column] = name if name.startswith(database + '_') else database + '_' + name
    selected = selected.rename(columns=renamed)
    return selected.groupby('GeneID', as_index=False, sort=False).agg(
        {column: join_unique for column in renamed.values()}
    )


def source_files(args):
    sources = [
        ('KEGG', os.path.join(args.annotation, 'KEGG', 'KEGG.tpm.csv')),
        ('eggNOG', os.path.join(args.annotation, 'eggNOG', 'eggNOG.tpm.csv')),
        ('CAZy', os.path.join(args.annotation, 'CAZy', 'gene.CAZy.tpm.csv')),
        ('GO', os.path.join(args.annotation, 'GO', 'GO.tpm.csv')),
        ('ARG', os.path.join(args.argdir, 'ARG.tpm.csv')),
        ('VFDB', os.path.join(args.vfdb, 'gene.vf.tpm.csv')),
        ('mobileOG', os.path.join(args.mobileogs, 'mobileOG.tpm.csv')),
        ('BacMet2', os.path.join(args.bacmet2, 'BacMet2.tpm.csv')),
        ('QS', os.path.join(args.qs, 'QS.tpm.csv')),
        ('COG', os.path.join(args.cog, 'COG.tpm.csv')),
        ('MetaCyc', os.path.join(args.metacyc, 'MetaCyc.tpm.csv')),
    ]
    for cycle in ['Carbon', 'Methane', 'Nitrogen', 'phosphorylation', 'Sulfur']:
        sources.append(('CycDB_' + cycle, os.path.join(args.cycdb, cycle + '_Cycle.xlsx')))
    return sources


def main():
    parser = argparse.ArgumentParser(description='按 GeneID 汇总所有数据库原始注释字段')
    parser.add_argument('-I', '--i_datadir', required=True, help='包含 sample-metadata.tsv 的目录')
    parser.add_argument('--Annotation', dest='annotation', required=True)
    parser.add_argument('--CycDB', dest='cycdb', required=True)
    parser.add_argument('--ARGdir', dest='argdir', required=True)
    parser.add_argument('--VFDB', dest='vfdb', required=True)
    parser.add_argument('--mobileOGs', dest='mobileogs', required=True)
    parser.add_argument('--BacMet2', dest='bacmet2', required=True)
    parser.add_argument('--QS', dest='qs', required=True)
    parser.add_argument('--COG', dest='cog', required=True)
    parser.add_argument('--MetaCyc', dest='metacyc', required=True)
    parser.add_argument('--outdir', default='Result/GeneAnnotationSummary')
    args = parser.parse_args()

    try:
        metadata = pd.read_csv(os.path.join(args.i_datadir, 'sample-metadata.tsv'),
                               sep='\t', skiprows=[1], dtype=str)
        sample_ids = metadata['sample-id'].dropna().astype(str).tolist()
        tables = []
        taxonomy = taxonomy_table(args.annotation)
        tables.append(('taxonomy', taxonomy))

        missing = []
        for database, path in source_files(args):
            if not os.path.isfile(path):
                missing.append('%s\t%s' % (database, path))
                log.warning('%s 注释文件不存在，跳过: %s', database, path)
                continue
            table = annotation_table(path, database, sample_ids)
            if table is not None:
                tables.append((database, table))
                log.info('%s: %d GeneID, %d 个注释字段', database, len(table), len(table.columns) - 1)

        all_ids = pd.concat([table[['GeneID']] for _, table in tables], ignore_index=True)
        summary = all_ids.drop_duplicates('GeneID').reset_index(drop=True)
        # taxonomy 固定为 GeneID 后的第一列，其余数据库字段按上面的业务顺序排列。
        for _, table in tables:
            summary = summary.merge(table, on='GeneID', how='left', validate='one_to_one')
        if 'taxonomy' in summary.columns:
            summary = summary[['GeneID', 'taxonomy'] +
                              [column for column in summary.columns if column not in {'GeneID', 'taxonomy'}]]
        summary = summary.fillna('')

        outdir = os.path.abspath(args.outdir)
        os.makedirs(outdir, exist_ok=True)
        csv_path = os.path.join(outdir, 'All_gene_annotation_summary.csv')
        summary.to_csv(csv_path, index=False, encoding='utf-8-sig')
        if len(summary) <= EXCEL_MAX_DATA_ROWS:
            xlsx_path = os.path.join(outdir, 'All_gene_annotation_summary.xlsx')
            try:
                summary.to_excel(xlsx_path, index=False, sheet_name='GeneAnnotation')
            except Exception as error:
                # CSV 是无行数/单元格长度限制的主结果；Excel 失败不应丢失主结果。
                log.warning('Excel 汇总表写入失败，保留 CSV 结果: %s', error)
        else:
            log.warning('GeneID 行数 %d 超过 Excel 上限，仅输出 CSV', len(summary))

        with open(os.path.join(outdir, 'missing_annotation_sources.tsv'), 'w', encoding='utf-8') as handle:
            handle.write('database\tpath\n' + '\n'.join(missing) + ('\n' if missing else ''))
        log.info('综合注释汇总完成：%d GeneID，%d 列，输出 %s', len(summary), len(summary.columns), outdir)
    except Exception as error:
        log.error('综合注释汇总失败: %s', error)
        sys.exit(1)


if __name__ == '__main__':
    main()
