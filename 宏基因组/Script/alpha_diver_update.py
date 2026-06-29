#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Pure-Python replacement for alpha_diver_update.R.

CLI: python alpha_diver_update.py <data_dir> <taxdir> <res_dir>
"""

import os
import sys
import argparse
import logging
from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import plotly.graph_objects as go
from plotly.subplots import make_subplots

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

CLASSES = ['All', 'Archaea', 'bacteria', 'Fungi', 'Virus']
INDEX_NAMES = ['Chao1', 'ACE', 'Shannon', 'Gini_simpson']

plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False


def _read_metadata(data_dir):
    path = os.path.join(data_dir, 'sample-metadata.tsv')
    df = pd.read_csv(path, sep='\t', skiprows=[1], dtype=str)
    return df


def _chao1(counts):
    counts = counts[counts > 0]
    s_obs = len(counts)
    f1 = np.sum(counts == 1)
    f2 = np.sum(counts == 2)
    if f2 > 0:
        return s_obs + (f1 ** 2) / (2.0 * f2)
    if f1 > 0:
        return s_obs + f1 * (f1 - 1) / 2.0
    return float(s_obs)


def _ace(counts):
    counts = np.asarray(counts, dtype=float)
    s_abund = np.sum(counts > 10)
    rare = counts[counts > 0]
    rare = rare[rare <= 10]
    s_rare = len(rare)
    n_rare = rare.sum()
    if n_rare == 0 or s_rare == 0:
        return float(np.sum(counts > 0))
    f1 = np.sum(rare == 1)
    c_ace = 1.0 - f1 / n_rare
    if c_ace == 0:
        return float(np.sum(counts > 0))
    k = np.arange(1, 11)
    f_k = np.array([np.sum(rare == i) for i in k])
    gamma2 = max((s_rare / c_ace) * np.sum(k * (k - 1) * f_k) / (n_rare * (n_rare - 1)) - 1.0, 0.0)
    return float(s_abund + s_rare / c_ace + f1 / c_ace * gamma2)


def _shannon(counts):
    total = counts.sum()
    if total == 0:
        return 0.0
    p = counts[counts > 0] / total
    return float(-np.sum(p * np.log(p)))


def _simpson(counts):
    total = counts.sum()
    if total == 0:
        return 0.0
    p = counts / total
    return float(1.0 - np.sum(p * p))


def _alpha_indices(otu):
    """
    otu: DataFrame samples x species (raw counts).
    Returns DataFrame samples x indices.
    """
    try:
        import skbio.diversity.alpha as skalpha
        rows = []
        for idx, row in otu.iterrows():
            counts = row.values.astype(int)
            rows.append({
                'Chao1': skalpha.chao1(counts),
                'ACE': skalpha.ace(counts),
                'Shannon': skalpha.shannon(counts, base=np.e),
                'Gini_simpson': skalpha.simpson(counts)
            })
        return pd.DataFrame(rows, index=otu.index)
    except Exception:
        pass

    rows = []
    for idx, row in otu.iterrows():
        counts = row.values.astype(float)
        rows.append({
            'Chao1': _chao1(counts),
            'ACE': _ace(counts),
            'Shannon': _shannon(counts),
            'Gini_simpson': _simpson(counts)
        })
    return pd.DataFrame(rows, index=otu.index)


def _two_group_pvalue(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a = a[~np.isnan(a)]
    b = b[~np.isnan(b)]
    if len(a) < 2 or len(b) < 2:
        return np.nan
    var_a = np.var(a, ddof=1) if len(a) > 1 else 0.0
    var_b = np.var(b, ddof=1) if len(b) > 1 else 0.0
    if len(a) >= 3 and len(b) >= 3 and var_a > 0 and var_b > 0:
        _, pa = stats.shapiro(a)
        _, pb = stats.shapiro(b)
        if pa > 0.05 and pb > 0.05:
            _, p = stats.ttest_ind(a, b, equal_var=False)
            return round(p, 6)
    _, p = stats.ranksums(a, b)
    return round(p, 6)


def _plot_alpha(diver, index, p_anova, pairs, pvals, resdir):
    os.makedirs(resdir, exist_ok=True)
    groups = diver['group'].unique().tolist()
    values = [diver.loc[diver['group'] == g, index].values for g in groups]

    # matplotlib
    fig, ax = plt.subplots(figsize=(6, 4))
    bp = ax.boxplot(values, labels=groups, patch_artist=True)
    for patch, color in zip(bp['boxes'], plt.cm.tab10.colors):
        patch.set_facecolor(color)
    ax.scatter(np.repeat(np.arange(1, len(groups) + 1), [len(v) for v in values]),
               np.concatenate(values), color='black', alpha=0.5, zorder=3)

    if pairs:
        y_max = diver[index].max()
        step = 0.1 * y_max if y_max != 0 else 0.1
        for k, (g1, g2, p) in enumerate(zip(pairs['group1'], pairs['group2'], pvals)):
            i1 = groups.index(g1) + 1
            i2 = groups.index(g2) + 1
            y = y_max + (k + 1) * step
            ax.plot([i1, i1, i2, i2], [y - step / 4, y, y, y - step / 4], color='black', lw=1)
            if p < 0.001:
                txt = '***'
            elif p < 0.01:
                txt = '**'
            elif p < 0.05:
                txt = '*'
            else:
                txt = f'p={p:.3f}'
            ax.text((i1 + i2) / 2.0, y, txt, ha='center', va='bottom', fontsize=9)

    ax.set_title(f'ANOVA: p={p_anova:.4f}')
    ax.set_ylabel(index)
    ax.set_xlabel('')
    plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
    plt.tight_layout()
    fig.savefig(os.path.join(resdir, f'{index}.pdf'), format='pdf', bbox_inches='tight')
    plt.close(fig)

    # plotly
    figp = go.Figure()
    for g, color in zip(groups, plt.cm.tab10.colors):
        figp.add_trace(go.Box(y=diver.loc[diver['group'] == g, index].values, name=g,
                              marker_color=f'rgb{tuple(int(c * 255) for c in color[:3])}',
                              boxpoints='all'))
    if pairs:
        y_max = diver[index].max()
        step = 0.1 * y_max if y_max != 0 else 0.1
        for k, (g1, g2, p) in enumerate(zip(pairs['group1'], pairs['group2'], pvals)):
            i1 = groups.index(g1) + 1
            i2 = groups.index(g2) + 1
            y = y_max + (k + 1) * step
            if p < 0.001:
                txt = '***'
            elif p < 0.01:
                txt = '**'
            elif p < 0.05:
                txt = '*'
            else:
                txt = f'p={p:.3f}'
            figp.add_annotation(x=(i1 + i2) / 2.0, y=y, text=txt, showarrow=False,
                                font=dict(size=12))
    figp.update_layout(title=f'ANOVA: p={p_anova:.4f}', yaxis_title=index, showlegend=False,
                       plot_bgcolor='white', xaxis=dict(showgrid=False))
    figp.write_html(os.path.join(resdir, f'{index}.html'), include_plotlyjs='cdn')


def run_alpha(data_dir, taxdir, res_dir):
    metadata = _read_metadata(data_dir)
    n_groups = metadata.shape[1] - 1

    for g in range(1, n_groups + 1):
        gro_num = f'group{g}'
        genecountfile = os.path.join(taxdir, gro_num, '4-GeneAbundance', 'gene_count.csv')
        taxfile = os.path.join(taxdir, gro_num, '5-TaxAnnotation', '1.Tables', 'gene.taxonomy.csv')
        if not os.path.exists(genecountfile):
            log.error('File not found: %s', genecountfile)
            continue
        if not os.path.exists(taxfile):
            log.error('File not found: %s', taxfile)
            continue

        otu = pd.read_csv(genecountfile, encoding='utf-8-sig', index_col=0)
        tax = pd.read_csv(taxfile, encoding='utf-8-sig', index_col=0)
        otu = otu[~otu.index.duplicated(keep='first')]
        tax = tax[~tax.index.duplicated(keep='first')]

        merged = tax.join(otu, how='inner')
        sample_cols = [c for c in merged.columns if c not in tax.columns]
        tax_otu_raw = merged.groupby('species')[sample_cols].sum().T
        tax_otu_raw.index.name = 'sample'

        group_col = metadata.columns[g]
        samples = metadata[['sample-id', group_col]].copy()
        samples = samples.dropna()
        samples = samples[samples[group_col] != '']
        samples.columns = ['sample-id', 'group']

        for j in CLASSES:
            specicestaxfile = os.path.join(taxdir, gro_num, '5-TaxAnnotation', '1.Tables', 'Samples', j, f'{j}.taxonomy.csv')
            if not os.path.exists(specicestaxfile):
                log.warning('Skip missing taxonomy file: %s', specicestaxfile)
                continue
            sp = pd.read_csv(specicestaxfile, encoding='utf-8-sig')
            keep_species = set(sp['species'].dropna().unique())
            tax_otu = tax_otu_raw[[c for c in tax_otu_raw.columns if c in keep_species]]
            tax_otu = tax_otu.loc[tax_otu.index.isin(samples['sample-id'])]
            if tax_otu.empty:
                log.warning('Empty OTU table for %s %s', gro_num, j)
                continue

            diver_index = _alpha_indices(tax_otu)
            diver_index = diver_index.fillna(0)

            resdir = os.path.join(res_dir, gro_num, '5-TaxAnnotation', '7.alpha_diversity_analysis', j)
            os.makedirs(resdir, exist_ok=True)
            diver_index.to_excel(os.path.join(resdir, 'diversity_index.xlsx'), index=True)

            diver = diver_index.copy()
            diver['sample'] = diver.index
            diver['group'] = samples.set_index('sample-id').loc[diver.index, 'group'].values

            for idx_name in INDEX_NAMES:
                vals = [diver.loc[diver['group'] == gr, idx_name].values for gr in diver['group'].unique()]
                try:
                    fstat, p_anova = stats.f_oneway(*vals)
                except Exception:
                    fstat, p_anova = np.nan, np.nan
                p_anova = round(p_anova, 4) if not np.isnan(p_anova) else np.nan

                groups = diver['group'].unique().tolist()
                pair_records = []
                pvals = []
                for g1, g2 in combinations(groups, 2):
                    a = diver.loc[diver['group'] == g1, idx_name].values
                    b = diver.loc[diver['group'] == g2, idx_name].values
                    p = _two_group_pvalue(a, b)
                    pair_records.append({'group1': g1, 'group2': g2, 'p_value': p})
                    pvals.append(p)
                pair_df = pd.DataFrame(pair_records)
                if not pair_df.empty:
                    pair_df.to_csv(os.path.join(resdir, f'{idx_name}_pairwise_pvalue.tsv'),
                                   sep='\t', index=False)

                _plot_alpha(diver, idx_name, p_anova, pair_df, pvals, resdir)


def main():
    parser = argparse.ArgumentParser(description='Alpha diversity analysis (Python replacement)')
    parser.add_argument('data_dir', help='Directory containing sample-metadata.tsv')
    parser.add_argument('taxdir', help='Taxonomy result directory')
    parser.add_argument('res_dir', help='Output result directory')
    args = parser.parse_args()

    data_dir = os.path.abspath(args.data_dir)
    taxdir = os.path.abspath(args.taxdir)
    res_dir = os.path.abspath(args.res_dir)

    for p in (data_dir, taxdir):
        if not os.path.exists(p):
            log.error('Path does not exist: %s', p)
            sys.exit(1)

    try:
        run_alpha(data_dir, taxdir, res_dir)
        log.info('alpha_diver 完成')
    except Exception as exc:
        log.error('alpha_diver 运行失败: %s', exc)
        sys.exit(1)


if __name__ == '__main__':
    main()
