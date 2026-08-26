#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Shared four-distance beta-diversity calculation with PCoA/NMDS plots."""

import logging
import os
import re
import shutil
import tempfile
import base64
import html

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from Bio import Phylo
from sklearn.manifold import MDS

LOG = logging.getLogger(__name__)


def read_metadata(datadir):
    path = os.path.join(os.path.abspath(datadir), 'sample-metadata.tsv')
    data = pd.read_csv(path, sep='\t', skiprows=[1], dtype=str)
    if 'sample-id' not in data.columns:
        raise ValueError('sample-metadata.tsv 缺少 sample-id 列')
    return data.dropna(subset=['sample-id'])


def read_abundance(path, sample_ids, excel_sheet=None):
    if path.lower().endswith(('.xlsx', '.xls')):
        engine = 'openpyxl' if path.lower().endswith('.xlsx') else 'xlrd'
        data = pd.read_excel(path, sheet_name=excel_sheet or 'relative', engine=engine)
    else:
        data = pd.read_csv(path, sep=None, engine='python')
    if data.empty or data.shape[1] < 3:
        raise ValueError('丰度表为空或列数不足')
    feature = data.columns[0]
    samples = [x for x in sample_ids if x in data.columns]
    if len(samples) < 3:
        raise ValueError('与 metadata 匹配的样本少于 3 个')
    values = data.set_index(feature)[samples].apply(pd.to_numeric, errors='coerce').fillna(0.0)
    values.index = values.index.map(lambda x: str(x).strip())
    values = values.groupby(level=0, sort=False).sum()
    if (values.to_numpy() < 0).any():
        raise ValueError('丰度表包含负值')
    values = values.loc[values.sum(axis=1) > 0]
    if len(values) < 2:
        raise ValueError('非零特征少于 2 个')
    return values


def read_tree(path):
    tree = Phylo.read(os.path.abspath(path), 'newick')
    tips = tree.get_terminals()
    names = [tip.name for tip in tips]
    if len(names) < 2 or any(not x for x in names) or len(names) != len(set(names)):
        raise ValueError('Newick 树叶节点不足、为空或不唯一')
    clades = [x for x in tree.find_clades(order='preorder') if x is not tree.root]
    if any(x.branch_length is None for x in clades):
        raise ValueError('Newick 树存在缺失的分支长度')
    if any(float(x.branch_length) < 0 for x in clades):
        raise ValueError('Newick 树存在负分支长度')
    return tree


def _alias(value):
    return re.sub(r'\s+', '_', str(value).strip())


def align_to_tree(abundance, tree):
    tips = [tip.name for tip in tree.get_terminals()]
    exact = set(tips)
    aliases = {}
    duplicated = set()
    for tip in tips:
        key = _alias(tip)
        if key in aliases and aliases[key] != tip:
            duplicated.add(key)
        aliases[key] = tip
    mapping = {}
    for feature in abundance.index:
        if feature in exact:
            mapping[feature] = feature
        elif _alias(feature) in aliases and _alias(feature) not in duplicated:
            mapping[feature] = aliases[_alias(feature)]
    if len(mapping) < 2:
        raise ValueError('丰度特征与树叶节点仅匹配 %d 个，至少需要 2 个' % len(mapping))
    result = abundance.loc[list(mapping)].copy()
    result.index = [mapping[x] for x in result.index]
    return result.groupby(level=0, sort=False).sum(), mapping


def _pairwise(abundance, distance):
    names = list(abundance.columns)
    matrix = np.zeros((len(names), len(names)), dtype=float)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            matrix[i, j] = matrix[j, i] = distance(
                abundance.iloc[:, i].to_numpy(float), abundance.iloc[:, j].to_numpy(float))
    return pd.DataFrame(matrix, index=names, columns=names)


def bray_curtis(abundance):
    def distance(a, b):
        den = np.sum(a + b)
        return 0.0 if den == 0 else float(np.sum(np.abs(a - b)) / den)
    return _pairwise(abundance, distance)


def binary_jaccard(abundance):
    def distance(a, b):
        a, b = a > 0, b > 0
        union = np.logical_or(a, b).sum()
        return 0.0 if union == 0 else float(np.logical_xor(a, b).sum() / union)
    return _pairwise(abundance, distance)


def unifrac(abundance, tree, weighted):
    tips = [tip.name for tip in tree.get_terminals()]
    position = {name: i for i, name in enumerate(tips)}
    tip_values = np.zeros((len(tips), abundance.shape[1]), dtype=float)
    for name, values in abundance.iterrows():
        tip_values[position[name], :] = values.to_numpy(float)
    branch_values, lengths = [], []
    for clade in tree.find_clades(order='preorder'):
        if clade is tree.root:
            continue
        indices = [position[x.name] for x in clade.get_terminals()]
        branch_values.append(tip_values[indices, :].sum(axis=0))
        lengths.append(float(clade.branch_length))
    branch_values, lengths = np.asarray(branch_values), np.asarray(lengths)
    totals = abundance.sum(axis=0).to_numpy(float)
    names = list(abundance.columns)
    result = np.zeros((len(names), len(names)), dtype=float)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if weighted:
                a = branch_values[:, i] / totals[i] if totals[i] else np.zeros(len(lengths))
                b = branch_values[:, j] / totals[j] if totals[j] else np.zeros(len(lengths))
                num, den = np.sum(lengths * np.abs(a-b)), np.sum(lengths * (a+b))
            else:
                a, b = branch_values[:, i] > 0, branch_values[:, j] > 0
                num = np.sum(lengths[np.logical_xor(a, b)])
                den = np.sum(lengths[np.logical_or(a, b)])
            result[i, j] = result[j, i] = 0.0 if den == 0 else float(num / den)
    return pd.DataFrame(result, index=names, columns=names)


def pcoa(distance):
    values = distance.to_numpy(float)
    n = len(values)
    center = np.eye(n) - np.ones((n, n)) / n
    gram = -0.5 * center.dot(values ** 2).dot(center)
    eigenvalues, eigenvectors = np.linalg.eigh(gram)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues, eigenvectors = eigenvalues[order], eigenvectors[:, order]
    positive = eigenvalues > max(1e-12, eigenvalues[0] * 1e-12)
    eigenvalues, eigenvectors = eigenvalues[positive], eigenvectors[:, positive]
    if len(eigenvalues) < 2:
        raise ValueError('距离矩阵不足以生成二维 PCoA')
    coordinates = eigenvectors[:, :2] * np.sqrt(eigenvalues[:2])
    explained = eigenvalues[:2] / eigenvalues.sum() * 100
    return pd.DataFrame(coordinates, index=distance.index, columns=['PCoA1', 'PCoA2']), explained


def nmds(distance):
    """Return deterministic two-dimensional non-metric MDS coordinates."""
    values = distance.to_numpy(float)
    if values.shape[0] < 3:
        raise ValueError('距离矩阵不足以生成二维 NMDS')
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError('NMDS 距离矩阵包含非有限值或负值')
    if not np.allclose(values, values.T, atol=1e-10):
        raise ValueError('NMDS 距离矩阵不对称')
    positive = values[np.triu_indices_from(values, k=1)]
    if not np.any(positive > 0):
        raise ValueError('所有样本间距离均为 0，无法生成 NMDS')
    model = MDS(
        n_components=2,
        metric=False,
        dissimilarity='precomputed',
        random_state=42,
        n_init=8,
        max_iter=1000,
        eps=1e-9,
        n_jobs=1,
    )
    coordinates = model.fit_transform(values)
    return (pd.DataFrame(coordinates, index=distance.index,
                         columns=['NMDS1', 'NMDS2']), float(model.stress_))


def _sample_labels(metadata, sample_index, group_column=None):
    group_columns = [x for x in metadata.columns if x != 'sample-id']
    if group_column is not None and group_column not in group_columns:
        raise ValueError('metadata 中不存在分组列: %s' % group_column)
    selected_group = group_column or (group_columns[0] if group_columns else None)
    groups = metadata.set_index('sample-id')[selected_group] if selected_group else None
    if groups is None:
        return pd.Series('All', index=sample_index)
    return groups.reindex(sample_index).fillna('NA')


def _save_embedded_html(png_path, html_path, page_title, alt_text):
    with open(png_path, 'rb') as handle:
        encoded = base64.b64encode(handle.read()).decode('ascii')
    with open(html_path, 'w', encoding='utf-8') as handle:
        handle.write(
            '<!doctype html><html><head><meta charset="utf-8">'
            '<title>{}</title></head><body style="margin:0;text-align:center">'
            '<h2>{}</h2><img alt="{}" style="max-width:100%;height:auto" '
            'src="data:image/png;base64,{}"></body></html>\n'.format(
                html.escape(page_title), html.escape(page_title),
                html.escape(alt_text), encoded))


def save_result(name, distance, outdir, metadata, title, group_column=None):
    os.makedirs(outdir, exist_ok=True)
    distance.to_csv(os.path.join(outdir, name + '_distance.csv'), encoding='utf-8-sig')
    coordinates, explained = pcoa(distance)
    coordinates.to_csv(os.path.join(outdir, name + '_PCoA_coordinates.csv'), encoding='utf-8-sig')
    labels = _sample_labels(metadata, coordinates.index, group_column)
    fig, ax = plt.subplots(figsize=(7.5, 6))
    for label in labels.drop_duplicates():
        selected = labels == label
        ax.scatter(coordinates.loc[selected, 'PCoA1'], coordinates.loc[selected, 'PCoA2'], label=label, s=38)
    ax.axhline(0, color='grey', linestyle='--', linewidth=.7)
    ax.axvline(0, color='grey', linestyle='--', linewidth=.7)
    ax.set_xlabel('PCoA1 (%.2f%%)' % explained[0])
    ax.set_ylabel('PCoA2 (%.2f%%)' % explained[1])
    ax.set_title('%s - %s' % (title, name))
    ax.legend(frameon=False)
    fig.tight_layout()
    png_path = os.path.join(outdir, name + '_PCoA.png')
    fig.savefig(png_path, dpi=300)
    fig.savefig(os.path.join(outdir, name + '_PCoA.pdf'))
    plt.close(fig)
    with pd.ExcelWriter(os.path.join(outdir, name + '_PCoA.xlsx'),
                        engine='openpyxl') as writer:
        distance.to_excel(writer, sheet_name='distance')
        coordinates.to_excel(writer, sheet_name='PCoA_coordinates')
    _save_embedded_html(
        png_path, os.path.join(outdir, name + '_PCoA.html'),
        '%s - %s' % (title, name), 'PCoA')


def save_nmds_result(name, distance, outdir, metadata, title, group_column=None):
    os.makedirs(outdir, exist_ok=True)
    coordinates, stress = nmds(distance)
    coordinates.to_csv(
        os.path.join(outdir, name + '_NMDS_coordinates.csv'), encoding='utf-8-sig')
    labels = _sample_labels(metadata, coordinates.index, group_column)
    fig, ax = plt.subplots(figsize=(7.5, 6))
    for label in labels.drop_duplicates():
        selected = labels == label
        ax.scatter(coordinates.loc[selected, 'NMDS1'],
                   coordinates.loc[selected, 'NMDS2'], label=label, s=38)
    ax.axhline(0, color='grey', linestyle='--', linewidth=.7)
    ax.axvline(0, color='grey', linestyle='--', linewidth=.7)
    ax.set_xlabel('NMDS1')
    ax.set_ylabel('NMDS2')
    ax.set_title('%s - %s NMDS (stress=%.4g)' % (title, name, stress))
    ax.legend(frameon=False)
    fig.tight_layout()
    png_path = os.path.join(outdir, name + '_NMDS.png')
    fig.savefig(png_path, dpi=300)
    fig.savefig(os.path.join(outdir, name + '_NMDS.pdf'))
    plt.close(fig)
    with pd.ExcelWriter(os.path.join(outdir, name + '_NMDS.xlsx'),
                        engine='openpyxl') as writer:
        distance.to_excel(writer, sheet_name='distance')
        coordinates.to_excel(writer, sheet_name='NMDS_coordinates')
        pd.DataFrame({'stress': [stress]}).to_excel(
            writer, sheet_name='NMDS_summary', index=False)
    _save_embedded_html(
        png_path, os.path.join(outdir, name + '_NMDS.html'),
        '%s - %s NMDS' % (title, name), 'NMDS')


def run_four(abundance, tree, outdir, metadata, title, group_column=None,
             merge_existing=False, nmds_outdir=None):
    """Calculate and publish all four distances as one output unit.

    Nothing is written to ``outdir`` until tree matching, all distance
    calculations and all plots have completed successfully.
    """
    aligned, mapping = align_to_tree(abundance, tree)
    distances = {
        'bray_curtis': bray_curtis(abundance),
        'jaccard_binary': binary_jaccard(abundance),
        'weighted_unifrac': unifrac(aligned, tree, True),
        'unweighted_unifrac': unifrac(aligned, tree, False),
    }

    outdir = os.path.abspath(outdir)
    parent = os.path.dirname(outdir)
    os.makedirs(parent, exist_ok=True)
    nmds_outdir = os.path.abspath(nmds_outdir or os.path.join(outdir, 'NMDS'))
    nmds_parent = os.path.dirname(nmds_outdir)
    os.makedirs(nmds_parent, exist_ok=True)
    staging = tempfile.mkdtemp(prefix='.%s.tmp-' % os.path.basename(outdir), dir=parent)
    nmds_staging = tempfile.mkdtemp(
        prefix='.%s.tmp-' % os.path.basename(nmds_outdir), dir=nmds_parent)
    backup = None
    try:
        pd.DataFrame({
            'feature_id': list(mapping),
            'tree_tip_id': list(mapping.values()),
        }).to_csv(os.path.join(staging, 'feature_tree_match.tsv'), sep='\t', index=False)
        for name, distance in distances.items():
            save_result(name, distance, staging, metadata, title, group_column=group_column)
            save_nmds_result(
                name, distance, nmds_staging, metadata, title,
                group_column=group_column)

        if merge_existing and os.path.isdir(outdir):
            for entry in os.listdir(staging):
                os.replace(os.path.join(staging, entry), os.path.join(outdir, entry))
            os.rmdir(staging)
            staging = None
            os.makedirs(nmds_outdir, exist_ok=True)
            for entry in os.listdir(nmds_staging):
                os.replace(os.path.join(nmds_staging, entry),
                           os.path.join(nmds_outdir, entry))
            os.rmdir(nmds_staging)
            nmds_staging = None
        else:
            if os.path.exists(outdir):
                backup = tempfile.mkdtemp(prefix='.%s.backup-' % os.path.basename(outdir), dir=parent)
                os.rmdir(backup)
                os.replace(outdir, backup)
            os.replace(staging, outdir)
            staging = None
            if os.path.exists(nmds_outdir):
                shutil.rmtree(nmds_outdir)
            os.replace(nmds_staging, nmds_outdir)
            nmds_staging = None
        if backup:
            shutil.rmtree(backup)
            backup = None
    except Exception:
        if staging and os.path.exists(staging):
            shutil.rmtree(staging)
        if nmds_staging and os.path.exists(nmds_staging):
            shutil.rmtree(nmds_staging)
        if backup and os.path.exists(backup) and not os.path.exists(outdir):
            os.replace(backup, outdir)
        raise
    return len(mapping)
