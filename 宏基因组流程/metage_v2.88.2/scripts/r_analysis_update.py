#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Pure-Python replacements for the taxonomy / functional visualisation and
permutation-test R scripts used by tax_diff_update.py and func_diff_update.py.

All functions are intentionally top-level so they can be submitted directly to
a ProcessPoolExecutor.
"""

import os
import re
import logging
from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial.distance import pdist, squareform
from statsmodels.stats import multitest
from sklearn.ensemble import RandomForestClassifier

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from plot_style_config import apply_matplotlib_style, METAGE_PLOT_FONT

import plotly.graph_objects as go
from plotly.subplots import make_subplots

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants matching the original R scripts
# ---------------------------------------------------------------------------
YANSE = [
    '#178224', '#D51506', '#B300B5', '#0133C1', '#B6BF2D',
    '#2DBFB9', '#EE520A', '#E90A6D', '#F09013', '#5FD80A',
    "#A65628", "#984EA3", "#F781BF", "#FFFF33", "#377EB8",
    "#D3D93E", "#C0717C", "#CBD588", "#D7C1B1", "#673770",
    "#3F4921", "#38333E", "#689030", "#AD6F3B", "#D9B3A6",
    "#008B8B", "#8B008B", "#FF8C00", "#8B0000", "#FFD700",
    "#00FF00", "#00FFFF", "#FF00FF", "#FF0000", "#0000FF",
    "#006400", "#FF1493", "#FF4500", "#FF6347", "#FF69B4",
    "#8B658B", "#8B4513", "#FFD39B", "#FFA07A", "#FFA500",
    "#CDC9C9", "#CD9B9B", "#CD6889", "#CD3333", "#CD0000",
    "#AEEEEE", "#8B8B00", "#8DB6CD", "#8B864E", "#8B795E",
    "#9AC0CD", "#8B5A2B", "#8B4789", "#7208BE", "#6B0E06",
    "#FFE4C4", "#6FDAB9", "#1FC1C1", "#FFB6C1", "#FFAEB9"
]

CBB_PALETTE = ["#E69F00", "#56B4E9"]

SPECIES = ['phylum', 'class', 'order', 'family', 'genus', 'species']
CLASSES = ['All', 'Archaea', 'bacteria', 'Fungi', 'Virus']
FUNC_INDEX = [
    '1.KEGG', '2.eggNOG', '3.CAZy', '4.GO',
    'Carbon_Cycle', 'Methane_Cycle', 'Nitrogen_Cycle',
    'phosphorylation_Cycle', 'Sulfur_Cycle',
    'ARG', 'VFDB', 'BacMet2', 'mobileOG', 'QS',
    'COG', 'MetaCyc'
]

apply_matplotlib_style(plt)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _read_metadata(data_dir):
    path = os.path.join(data_dir, 'sample-metadata.tsv')
    if not os.path.exists(path):
        log.warning('Metadata file not found: %s', path)
        return None
    try:
        df = pd.read_csv(path, sep='\t', skiprows=[1], dtype=str)
    except Exception as exc:
        log.warning('Failed to read metadata %s: %s', path, exc)
        return None
    if df.shape[1] < 2:
        log.warning('Metadata has fewer than 2 columns')
        return None
    return df


def _iter_groups(metadata):
    n_groups = metadata.shape[1] - 1
    for i in range(1, n_groups + 1):
        gro_num = f'group{i}'
        col = metadata.columns[i]
        df = metadata[['sample-id', col]].copy()
        df = df.dropna()
        df = df[df[col] != '']
        df.columns = ['sample-id', 'group']
        df['group'] = df['group'].astype(str)
        yield gro_num, df


def _func_name(name, max_len=60):
    """Sanitise feature names the same way the original func R scripts do."""
    s = str(name)
    s = re.sub(r'[\/]', '_', s)
    s = s.replace(':', '_')
    s = s.replace('->', '_').replace('=>', '_')
    s = s.replace(' ', '')
    s = re.sub(r'[.()\[\]]', '', s)
    if len(s) > max_len:
        s = s[:max_len] + '...'
    return s or 'unknown'


def _tax_anova_name(name):
    # tax_anova_update.R does not sanitise beyond replacing filesystem separators
    return str(name).replace('/', '_').replace('\\', '_').replace(':', '_')


def _tax_wilcox_name(name):
    # tax_wilcoxon_update.R replaces / and :
    return str(name).replace('/', '_').replace(':', '_')


def _func_resdir(res_dir, group_num, func, test_type, prefix=None):
    if func in ('1.KEGG', '2.eggNOG', '3.CAZy', '4.GO'):
        base = os.path.join(res_dir, group_num, '8-FunctionStatistical_analysis', func, test_type)
    elif '_Cycle' in func:
        base = os.path.join(res_dir, group_num, '9-METABOLIC', func, '6.Statistical_test_analysis', test_type)
    elif func == 'ARG':
        base = os.path.join(res_dir, group_num, '10-ARG', '6.Statistical_test_analysis', test_type)
    elif func == 'VFDB':
        base = os.path.join(res_dir, group_num, '11-VFDB', '6.Statistical_test_analysis', test_type)
    elif func == 'mobileOG':
        base = os.path.join(res_dir, group_num, '12-mobileOG', '6.Statistical_test_analysis', test_type)
    elif func == 'BacMet2':
        base = os.path.join(res_dir, group_num, '13-BacMet2', '6.Statistical_test_analysis', test_type)
    elif func == 'QS':
        base = os.path.join(res_dir, group_num, '14-QS', '6.Statistical_test_analysis', test_type)
    elif func == 'COG':
        base = os.path.join(res_dir, group_num, '15-COG', '6.Statistical_test_analysis', test_type)
    elif func == 'MetaCyc':
        base = os.path.join(res_dir, group_num, '16-MetaCyc', '6.Statistical_test_analysis', test_type)
    else:
        raise ValueError(f'Unknown functional type: {func}')
    if prefix is not None and func == '1.KEGG':
        base = os.path.join(base, prefix)
    return base


def _read_tax_relative(type_dir, specie):
    path = os.path.join(type_dir, f'{specie}.xlsx')
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_excel(path, sheet_name='relative')
    except Exception as exc:
        log.warning('Failed to read %s: %s', path, exc)
        return None
    df = df.dropna(axis=1, how='all')
    return df


def _read_func_diff(table_dir, filename):
    path = os.path.join(table_dir, filename)
    df = pd.read_csv(path, sep='\t', encoding='utf-8-sig', index_col=0)
    # 保留 index.name，使 _prepare_beta_matrix 能正确区分 tax/func 格式
    return df


def _drop_constant_zero_cols(df):
    """Drop columns that are all NA or all equal (including all-zero)."""
    df = df.dropna(axis=1, how='all')
    numeric = df.select_dtypes(include=[np.number])
    keep = numeric.columns[numeric.std(skipna=True) > 0]
    return df[keep]


def _align_with_group(mat, group_df):
    """mat: samples x features DataFrame (no Group column). Returns mat with Group column."""
    mat = mat.loc[mat.index.isin(group_df['sample-id'])].copy()
    if mat.empty:
        return mat
    group_map = group_df.set_index('sample-id')['group']
    mat['Group'] = group_map.reindex(mat.index).values
    mat = mat.dropna(subset=['Group'])
    mat['Group'] = pd.Categorical(
        mat['Group'], categories=group_df['group'].unique(), ordered=True
    )
    return mat


def _dynamic_size(k_gros, base_w=6.0, base_h=6.0):
    w = base_w + (k_gros / 20.0) * 1.5
    h = base_h + (k_gros / 20.0) * 0.5
    return w, h


# ---------------------------------------------------------------------------
# Shared plotting helpers
# ---------------------------------------------------------------------------
def _save_boxplot(melted, title, ylabel, out_pdf, out_html, percent=False):
    group_labels = list(melted['group'].unique())
    data_by_group = [melted.loc[melted['group'] == g, 'value'].values for g in group_labels]
    k_gros = len(group_labels)
    w, h = _dynamic_size(k_gros)

    # matplotlib PDF
    fig, ax = plt.subplots(figsize=(w, h))
    bp = ax.boxplot(data_by_group, labels=group_labels, patch_artist=True,
                    widths=0.6, showcaps=True, showfliers=True)
    for patch, color in zip(bp['boxes'], YANSE):
        patch.set_facecolor(color)
    for whisker in bp['whiskers']:
        whisker.set_color('black')
    for cap in bp['caps']:
        cap.set_color('black')
    ax.set_title(title, fontsize=14)
    ax.set_ylabel(ylabel, fontsize=13)
    ax.set_xlabel('')
    ax.grid(False)
    if percent:
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.0%}'))
    plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
    plt.tight_layout()
    fig.savefig(out_pdf, format='pdf', bbox_inches='tight')
    plt.close(fig)

    # plotly HTML
    figp = go.Figure()
    for g, color in zip(group_labels, YANSE):
        figp.add_trace(go.Box(
            y=melted.loc[melted['group'] == g, 'value'].values,
            name=g,
            marker_color=color,
            boxmean=True
        ))
    yaxis = dict(title=ylabel)
    if percent:
        yaxis['tickformat'] = '.0%'
    figp.update_layout(
        title=title,
        yaxis=yaxis,
        showlegend=False,
        plot_bgcolor='white',
        xaxis=dict(showgrid=False),
        yaxis_gridcolor='lightgray'
    )
    figp.write_html(out_html, include_plotlyjs=True)


def _plot_sign_boxplots(tpm_dir, data_dir, res_dir, kind, test_type):
    """Shared implementation for anova / wilcoxon boxplots."""
    metadata = _read_metadata(data_dir)
    if metadata is None:
        return

    stat_cols = {'F_value', 'p_value', 'padj'} if test_type == 'anova' else {'statistic', 'p_value', 'padj'}
    if kind == 'tax':
        ylabel = 'Relative abundance'
        percent = True
    else:
        ylabel = 'Abundance'
        percent = False

    out_test = '1.ANOVA' if test_type == 'anova' else '2.wilcoxon'

    for gro_num, group_df in _iter_groups(metadata):
        if kind == 'tax':
            iterators = [(clas, os.path.join(tpm_dir, gro_num, test_type, clas), SPECIES)
                         for clas in CLASSES]
        else:
            iterators = [(func, os.path.join(tpm_dir, gro_num, test_type, func), None)
                         for func in FUNC_INDEX]

        for label, table_dir, subitems in iterators:
            if not os.path.exists(table_dir):
                continue
            if kind == 'tax':
                files = [(f'{specie}_sign.tsv', specie) for specie in subitems]
            else:
                files = [(f, f[:-9]) for f in os.listdir(table_dir) if f.endswith('_sign.tsv')]

            for sign_file, extra in files:
                sign_path = os.path.join(table_dir, sign_file)
                if not os.path.exists(sign_path):
                    continue
                try:
                    sign_df = pd.read_csv(sign_path, sep='\t', encoding='utf-8-sig')
                except Exception as exc:
                    log.warning('Skip %s: %s', sign_path, exc)
                    continue
                if sign_df.empty:
                    continue
                feature_col = sign_df.columns[0]
                sample_cols = [c for c in sign_df.columns[1:] if c not in stat_cols]
                n_plot = min(5, len(sign_df))

                for j in range(n_plot):
                    row = sign_df.iloc[j]
                    feat_name = row[feature_col]
                    melted = pd.DataFrame({
                        'sample-id': sample_cols,
                        'value': pd.to_numeric(row[sample_cols], errors='coerce').values
                    })
                    melted = melted.merge(group_df, on='sample-id', how='inner')
                    melted = melted.dropna()
                    if melted.empty:
                        continue
                    melted['group'] = pd.Categorical(
                        melted['group'], categories=group_df['group'].unique(), ordered=True
                    )
                    p_value = float(row['p_value'])
                    title = f"{feat_name}, pvalue={p_value:.3f}"

                    if kind == 'tax':
                        specie = extra
                        clas = label
                        resdir = os.path.join(res_dir, gro_num, '6-TaxStatistical_analysis', clas, specie, out_test)
                        out_name = _tax_anova_name(feat_name) if test_type == 'anova' else _tax_wilcox_name(feat_name)
                    else:
                        func = label
                        prefix = extra
                        resdir = _func_resdir(res_dir, gro_num, func, out_test, prefix)
                        out_name = _func_name(feat_name)

                    os.makedirs(resdir, exist_ok=True)
                    _save_boxplot(melted, title, ylabel,
                                  os.path.join(resdir, f'{out_name}.pdf'),
                                  os.path.join(resdir, f'{out_name}.html'),
                                  percent=percent)


def plot_anova_boxplots(tpm_dir, data_dir, res_dir, kind='tax'):
    log.info('ANOVA boxplots: %s', kind)
    _plot_sign_boxplots(tpm_dir, data_dir, res_dir, kind, 'anova')


def plot_wilcoxon_boxplots(tpm_dir, data_dir, res_dir, kind='tax'):
    log.info('Wilcoxon boxplots: %s', kind)
    _plot_sign_boxplots(tpm_dir, data_dir, res_dir, kind, 'wilcoxon')


# ---------------------------------------------------------------------------
# Two-group differential test used by Stamp
# ---------------------------------------------------------------------------
def _two_group_test(a, b):
    """Return (method, statistic, p_value) choosing t-test or Wilcoxon."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a = a[~np.isnan(a)]
    b = b[~np.isnan(b)]
    if len(a) < 2 or len(b) < 2:
        return None, np.nan, np.nan
    var_a = np.var(a, ddof=1) if len(a) > 1 else 0.0
    var_b = np.var(b, ddof=1) if len(b) > 1 else 0.0
    if len(a) >= 3 and len(b) >= 3 and var_a > 0 and var_b > 0:
        _, pa = stats.shapiro(a)
        _, pb = stats.shapiro(b)
        if pa > 0.05 and pb > 0.05:
            tstat, p = stats.ttest_ind(a, b, equal_var=False)
            return 't', tstat, p
    tstat, p = stats.ranksums(a, b)
    return 'wilcoxon', tstat, p


def _stamp_diff(mat, group_order):
    """
    mat: samples x features DataFrame with a 'Group' column.
    Returns a DataFrame of per-feature differential statistics (top 20 by BH-FDR).
    """
    g1, g2 = group_order
    feature_cols = [c for c in mat.columns if c != 'Group']
    rows = []
    for feat in feature_cols:
        vals = mat[[feat, 'Group']].dropna()
        a = vals.loc[vals['Group'] == g1, feat].values
        b = vals.loc[vals['Group'] == g2, feat].values
        method, stat, p = _two_group_test(a, b)
        if p is np.nan:
            continue
        estimate = np.mean(a) - np.mean(b)
        if method == 't':
            se = np.sqrt(np.var(a, ddof=1) / max(1, len(a)) + np.var(b, ddof=1) / max(1, len(b)))
            df = _welch_df(a, b)
            t_crit = stats.t.ppf(0.975, df) if df and df > 0 else 0
            ci_low = estimate - t_crit * se
            ci_high = estimate + t_crit * se
        else:
            ci_low = np.nan
            ci_high = np.nan
        higher = g1 if estimate > 0 else g2
        rows.append({
            'var': feat,
            'estimate': estimate,
            'conf.low': ci_low,
            'conf.high': ci_high,
            'p.value': p,
            'Group': higher
        })
    if not rows:
        return pd.DataFrame()
    diff = pd.DataFrame(rows)
    if diff.empty:
        return diff
    diff['p.value'] = multitest.fdrcorrection(diff['p.value'].values)[1]
    diff = diff.sort_values('p.value').head(20)
    return diff


def _welch_df(a, b):
    va = np.var(a, ddof=1)
    vb = np.var(b, ddof=1)
    na = len(a)
    nb = len(b)
    if va == 0 and vb == 0:
        return 1
    num = (va / na + vb / nb) ** 2
    den = (va ** 2) / (na ** 2 * (na - 1)) + (vb ** 2) / (nb ** 2 * (nb - 1))
    return num / den if den > 0 else 1


def _save_stamp_plots(mat, diff, resdir, out_prefix, width=11.0, height=7.0):
    if diff.empty:
        return
    g1, g2 = list(mat['Group'].unique())[:2]
    # Excel output: top 20 sorted by adjusted p-value
    xlsx_path = os.path.join(resdir, f'{out_prefix}.xlsx')
    diff.copy().to_excel(xlsx_path, index=False)

    # Plotting order: by estimate descending
    plot_diff = diff.sort_values('estimate', ascending=False).reset_index(drop=True)
    features = plot_diff['var'].tolist()

    # abun.bar: mean abundance per group per feature
    abun_rows = []
    for feat in features:
        for g, grp in mat.groupby('Group'):
            abun_rows.append({'variable': feat, 'Group': g, 'Mean': grp[feat].mean()})
    abun = pd.DataFrame(abun_rows)

    # matplotlib 3-panel plot
    fig = plt.figure(figsize=(width, height))
    gs = fig.add_gridspec(1, 3, width_ratios=[4, 5, 2])
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[0, 2])

    y = np.arange(len(features))
    bar_h = 0.35
    means_g1 = np.array([abun.loc[(abun['variable'] == f) & (abun['Group'] == g1), 'Mean'].values[0] for f in features])
    means_g2 = np.array([abun.loc[(abun['variable'] == f) & (abun['Group'] == g2), 'Mean'].values[0] for f in features])

    # alternating background bands
    for j in range(len(features) - 1):
        col = '#F2F2F2' if j % 2 == 0 else 'white'
        for ax in (ax1, ax2):
            ax.axhspan(j + 0.5, j + 1.5, color=col, zorder=0)

    ax1.barh(y + bar_h / 2, means_g1, height=bar_h, color=CBB_PALETTE[0], edgecolor='black', label=g1)
    ax1.barh(y - bar_h / 2, means_g2, height=bar_h, color=CBB_PALETTE[1], edgecolor='black', label=g2)
    ax1.set_yticks(y)
    ax1.set_yticklabels(features, fontsize=11)
    ax1.set_xlabel('Mean proportion', fontsize=13)
    ax1.set_ylim(-0.5, len(features) - 0.5)
    ax1.invert_yaxis()
    ax1.legend(loc='upper center', bbox_to_anchor=(0.5, 1.05), ncol=2, frameon=False)
    ax1.set_axisbelow(True)

    estimates = plot_diff['estimate'].values
    ci_low_raw = plot_diff['conf.low'].values
    ci_high_raw = plot_diff['conf.high'].values
    has_ci = np.isfinite(ci_low_raw) & np.isfinite(ci_high_raw)
    ci_low = np.where(has_ci, ci_low_raw, estimates)
    ci_high = np.where(has_ci, ci_high_raw, estimates)
    lower_err = np.maximum(estimates - ci_low, 0)
    upper_err = np.maximum(ci_high - estimates, 0)
    higher_group = plot_diff['Group'].values
    colors2 = [CBB_PALETTE[0] if g == g1 else CBB_PALETTE[1] for g in higher_group]

    ax2.errorbar(estimates, y, xerr=[lower_err, upper_err],
                 fmt='o', color='black', ecolor='black', capsize=3, markersize=7,
                 markerfacecolor='white', zorder=3)
    ax2.scatter(estimates, y, c=colors2, s=80, zorder=4, edgecolors='black')
    ax2.axvline(0, color='black', linestyle='--', linewidth=1)
    ax2.set_yticks(y)
    ax2.set_yticklabels([])
    ax2.set_xlabel('Difference in mean proportions', fontsize=13)
    ax2.set_title('95% confidence intervals', fontsize=14)
    ax2.set_ylim(-0.5, len(features) - 0.5)
    ax2.invert_yaxis()

    p_text = [f"{p:.3g}" for p in plot_diff['p.value'].values]
    for j, txt in enumerate(p_text):
        ax3.text(0.05, y[j], txt, va='center', ha='left', fontsize=11)
    ax3.text(0.5, len(features) / 2.0, 'P-value (corrected)', rotation=90, va='center', ha='center', fontsize=12)
    ax3.set_xlim(0, 1)
    ax3.set_ylim(-0.5, len(features) - 0.5)
    ax3.invert_yaxis()
    ax3.axis('off')

    plt.tight_layout()
    fig.savefig(os.path.join(resdir, f'{out_prefix}.pdf'), format='pdf', bbox_inches='tight')
    plt.close(fig)

    # plotly interactive version
    figp = make_subplots(rows=1, cols=3, column_widths=[0.36, 0.45, 0.19],
                         horizontal_spacing=0.02)
    figp.add_trace(go.Bar(
        y=features, x=means_g1, name=g1, marker_color=CBB_PALETTE[0],
        orientation='h', showlegend=True
    ), row=1, col=1)
    figp.add_trace(go.Bar(
        y=features, x=means_g2, name=g2, marker_color=CBB_PALETTE[1],
        orientation='h', showlegend=True
    ), row=1, col=1)
    figp.add_trace(go.Scatter(
        y=features, x=estimates, mode='markers',
        marker=dict(color=colors2, size=10, line=dict(color='black', width=1)),
        error_x=dict(type='data', symmetric=False, array=upper_err, arrayminus=lower_err),
        showlegend=False
    ), row=1, col=2)
    figp.add_vline(x=0, line=dict(dash='dash', color='black'), row=1, col=2)
    for j, txt in enumerate(p_text):
        figp.add_annotation(x=0.1, y=features[j], text=txt, showarrow=False,
                            xref='x3', yref='y3', xanchor='left', font=dict(size=10))
    figp.add_annotation(x=0.5, y=len(features) / 2.0, text='P-value (corrected)', showarrow=False,
                        xref='x3', yref='y3', textangle=-90, font=dict(size=11))
    figp.update_xaxes(title_text='Mean proportion', row=1, col=1)
    figp.update_xaxes(title_text='Difference in mean proportions', row=1, col=2)
    figp.update_xaxes(range=[0, 1], visible=False, row=1, col=3)
    figp.update_yaxes(row=1, col=2, showticklabels=False)
    figp.update_yaxes(row=1, col=3, showticklabels=False)
    figp.update_layout(title_text='Stamp plot', height=height * 80, width=width * 80,
                       plot_bgcolor='white', barmode='group')
    figp.write_html(os.path.join(resdir, f'{out_prefix}.html'), include_plotlyjs=True)


def plot_stamp(table_dir, data_dir, res_dir, kind='tax'):
    log.info('Stamp plot: %s', kind)
    metadata = _read_metadata(data_dir)
    if metadata is None:
        return

    for gro_num, group_df in _iter_groups(metadata):
        if group_df['group'].nunique() != 2:
            continue
        group_order = list(group_df['group'].unique())

        if kind == 'tax':
            for clas in CLASSES:
                type_dir = os.path.join(table_dir, gro_num, '5-TaxAnnotation', '1.Tables', 'Samples', clas)
                if not os.path.exists(type_dir):
                    continue
                for specie in SPECIES:
                    df = _read_tax_relative(type_dir, specie)
                    if df is None or df.shape[0] < 2:
                        continue
                    feat_col = df.columns[0]
                    mat = df.set_index(feat_col).T
                    mat = _align_with_group(mat, group_df)
                    if mat.empty or mat['Group'].nunique() != 2:
                        continue
                    diff = _stamp_diff(mat, group_order)
                    if diff.empty:
                        continue
                    resdir = os.path.join(res_dir, gro_num, '6-TaxStatistical_analysis', clas, specie, '3.Stamp')
                    os.makedirs(resdir, exist_ok=True)
                    _save_stamp_plots(mat, diff, resdir, f'{clas}_{specie}_stamp', width=11.0, height=7.0)
        else:
            for func in FUNC_INDEX:
                func_table_dir = os.path.join(table_dir, gro_num, func)
                if not os.path.exists(func_table_dir):
                    continue
                for file in os.listdir(func_table_dir):
                    if not file.endswith('_diff.tsv'):
                        continue
                    df = _read_func_diff(func_table_dir, file)
                    if df.shape[0] < 2:
                        continue
                    mat = df.T
                    mat = _align_with_group(mat, group_df)
                    if mat.empty or mat['Group'].nunique() != 2:
                        continue
                    diff = _stamp_diff(mat, group_order)
                    if diff.empty:
                        continue
                    prefix = file[:-9]
                    resdir = _func_resdir(res_dir, gro_num, func, '3.Stamp')
                    os.makedirs(resdir, exist_ok=True)
                    _save_stamp_plots(mat, diff, resdir, prefix, width=11.5, height=7.0)


# ---------------------------------------------------------------------------
# Random Forest
# ---------------------------------------------------------------------------
def _run_random_forest(mat, resdir, out_prefix, width=10.5, height=7.0):
    if mat.empty or 'Group' not in mat.columns:
        return
    y = mat['Group'].astype(str)
    if y.nunique() <= 1:
        return
    X = mat.drop(columns=['Group'])
    X = X.apply(pd.to_numeric, errors='coerce')
    X = _drop_constant_zero_cols(X)
    if X.empty:
        return
    X = X.dropna()
    y = y.loc[X.index]
    if len(y) < 2 or y.nunique() <= 1:
        return

    rf = RandomForestClassifier(n_estimators=500, random_state=123, n_jobs=1)
    rf.fit(X, y)

    gini = rf.feature_importances_
    # approximate SD of Gini importances across trees
    tree_imp = np.array([tree.feature_importances_ for tree in rf.estimators_])
    gini_sd = np.std(tree_imp, axis=0)

    save_tab = pd.DataFrame({
        'MeanDecreaseAccuracy': 0.0,
        'MeanDecreaseGini': gini,
        'MDA.p': gini_sd
    }, index=X.columns)
    save_tab = save_tab.round(2)
    save_tab_path = os.path.join(resdir, f'{out_prefix}.xlsx')
    save_tab.to_excel(save_tab_path, index=True)

    plot_tab = save_tab[save_tab['MeanDecreaseGini'] > 0].sort_values(
        'MeanDecreaseGini', ascending=False).head(10).reset_index()
    plot_tab = plot_tab.rename(columns={plot_tab.columns[0]: 'tax'})
    if plot_tab.empty:
        return
    plot_features = plot_tab['tax'].tolist()

    # mean and sd per group for top features
    plot_rows = []
    for feat in plot_features:
        for g, grp in mat.groupby('Group'):
            vals = pd.to_numeric(grp[feat], errors='coerce').dropna()
            plot_rows.append({'variable': feat, 'group': g, 'mean': vals.mean(), 'sd': vals.std()})
    plot_tax = pd.DataFrame(plot_rows)

    # matplotlib
    fig = plt.figure(figsize=(width, height))
    gs = fig.add_gridspec(1, 2, width_ratios=[1, 1])
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])

    y = np.arange(len(plot_features))
    gini_vals = plot_tab['MeanDecreaseGini'].values
    ax1.barh(y, gini_vals, color='steelblue', height=0.7)
    ax1.set_yticks(y)
    ax1.set_yticklabels(plot_features, fontsize=18)
    ax1.invert_yaxis()
    ax1.set_xlabel('MeanDecreaseGini', fontsize=20)
    ax1.set_title('Random Forest feature importance', fontsize=24)
    ax1.tick_params(axis='x', labelsize=18)
    ax1.grid(False)

    groups = list(plot_tax['group'].unique())
    n_g = len(groups)
    bar_h = 0.7 / max(1, n_g)
    for i_g, g in enumerate(groups):
        gdata = plot_tax[plot_tax['group'] == g]
        means = np.array([gdata.loc[gdata['variable'] == f, 'mean'].values[0] for f in plot_features])
        sds = np.array([gdata.loc[gdata['variable'] == f, 'sd'].values[0] for f in plot_features])
        offset = (i_g - (n_g - 1) / 2.0) * bar_h
        ax2.barh(y + offset, means, height=bar_h, label=g, color=YANSE[i_g % len(YANSE)])
        ax2.errorbar(means, y + offset, xerr=sds, fmt='none', ecolor='#939596', capsize=2)
    ax2.set_yticks(y)
    ax2.set_yticklabels([])
    ax2.invert_yaxis()
    ax2.set_xlabel('Relative abundance', fontsize=20)
    ax2.tick_params(axis='x', labelsize=18)
    ax2.legend(loc='best', fontsize=20, title_fontsize=22)
    ax2.grid(False)

    plt.tight_layout()
    fig.savefig(os.path.join(resdir, f'{out_prefix}.pdf'), format='pdf', bbox_inches='tight')
    plt.close(fig)

    # plotly
    figp = make_subplots(rows=1, cols=2, column_widths=[0.5, 0.5], subplot_titles=(
        'Random Forest feature importance', 'Group abundance'))
    figp.add_trace(go.Bar(y=plot_features, x=gini_vals, orientation='h', marker_color='steelblue',
                           showlegend=False), row=1, col=1)
    for i_g, g in enumerate(groups):
        gdata = plot_tax[plot_tax['group'] == g]
        means = [gdata.loc[gdata['variable'] == f, 'mean'].values[0] for f in plot_features]
        sds = [gdata.loc[gdata['variable'] == f, 'sd'].values[0] for f in plot_features]
        figp.add_trace(go.Bar(y=plot_features, x=means, orientation='h', name=g,
                               error_x=dict(type='data', array=sds, color='#939596'),
                               marker_color=YANSE[i_g % len(YANSE)]), row=1, col=2)
    figp.update_layout(
        height=height * 80,
        width=width * 80,
        barmode='group',
        plot_bgcolor='white',
        font=dict(family=METAGE_PLOT_FONT, size=18),
        legend=dict(
            font=dict(family=METAGE_PLOT_FONT, size=20),
            title=dict(font=dict(family=METAGE_PLOT_FONT, size=22)),
        ),
    )
    figp.update_annotations(font=dict(family=METAGE_PLOT_FONT, size=24))
    figp.update_xaxes(
        title_font=dict(family=METAGE_PLOT_FONT, size=20),
        tickfont=dict(family=METAGE_PLOT_FONT, size=18),
    )
    figp.update_yaxes(tickfont=dict(family=METAGE_PLOT_FONT, size=18))
    figp.update_yaxes(row=1, col=2, showticklabels=False)
    figp.write_html(os.path.join(resdir, f'{out_prefix}.html'), include_plotlyjs=True)


def plot_random_forest(table_dir, data_dir, res_dir, kind='tax'):
    log.info('Random Forest: %s', kind)
    metadata = _read_metadata(data_dir)
    if metadata is None:
        return

    for gro_num, group_df in _iter_groups(metadata):
        if kind == 'tax':
            for clas in CLASSES:
                type_dir = os.path.join(table_dir, gro_num, '5-TaxAnnotation', '1.Tables', 'Samples', clas)
                if not os.path.exists(type_dir):
                    continue
                for specie in SPECIES:
                    df = _read_tax_relative(type_dir, specie)
                    if df is None or df.shape[0] < 2:
                        continue
                    feat_col = df.columns[0]
                    mat = df.set_index(feat_col).T
                    mat = _align_with_group(mat, group_df)
                    if mat.empty:
                        continue
                    resdir = os.path.join(res_dir, gro_num, '6-TaxStatistical_analysis', clas, specie, '4.Random_Forest')
                    os.makedirs(resdir, exist_ok=True)
                    _run_random_forest(mat, resdir, f'{clas}_{specie}_random_forest', width=10.5, height=7.0)
        else:
            for func in FUNC_INDEX:
                func_table_dir = os.path.join(table_dir, gro_num, func)
                if not os.path.exists(func_table_dir):
                    continue
                for file in os.listdir(func_table_dir):
                    if not file.endswith('_diff.tsv'):
                        continue
                    df = _read_func_diff(func_table_dir, file)
                    if df.shape[0] == 0:
                        continue
                    mat = df.T
                    mat = _align_with_group(mat, group_df)
                    if mat.empty:
                        continue
                    prefix = file[:-9]
                    resdir = _func_resdir(res_dir, gro_num, func, '4.Random_Forest')
                    os.makedirs(resdir, exist_ok=True)
                    _run_random_forest(mat, resdir, prefix, width=12.0, height=7.0)


# ---------------------------------------------------------------------------
# Distance-based permutation tests
# ---------------------------------------------------------------------------
def _bray_curtis_matrix(mat):
    """mat: samples x features. Returns condensed distance vector and square matrix."""
    dist_vec = pdist(mat.values, metric='braycurtis')
    dist_sq = squareform(dist_vec)
    # 强制对称化并清零对角线，避免浮点精度导致 squareform/is_valid_dm 报错
    dist_sq = (dist_sq + dist_sq.T) / 2.0
    np.fill_diagonal(dist_sq, 0.0)
    return dist_vec, dist_sq


def _anosim(dist_vec, dist_sq, groups, n_perm=999, seed=123):
    rng = np.random.default_rng(seed)
    groups = np.asarray(groups)
    n = len(groups)
    pair_idx = np.triu_indices(n, k=1)
    pair_labels = []
    for i, j in zip(pair_idx[0], pair_idx[1]):
        gi, gj = groups[i], groups[j]
        label = f'{gi}:{gj}' if gi <= gj else f'{gj}:{gi}'
        pair_labels.append(label)
    pair_labels = np.array(pair_labels)
    pair_groups_same = np.array([groups[i] == groups[j] for i, j in zip(pair_idx[0], pair_idx[1])])
    ranks = stats.rankdata(dist_vec, method='average')

    def r_stat(lbls, same):
        r_w = ranks[same].mean() if same.any() else 0.0
        r_b = ranks[~same].mean() if (~same).any() else 0.0
        denom = n * (n - 1) / 4.0
        return (r_b - r_w) / denom if denom else np.nan

    r_obs = r_stat(pair_labels, pair_groups_same)
    r_perm = [r_stat(pair_labels, pair_groups_same[rng.permutation(len(pair_groups_same))]) for _ in range(n_perm)]
    r_perm = np.array(r_perm)
    p = (np.sum(r_perm >= r_obs) + 1) / (n_perm + 1) if not np.isnan(r_obs) else np.nan

    df_plot = pd.DataFrame({'x': pair_labels, 'y': ranks})
    return r_obs, p, df_plot


def _permanova(dist_sq, groups, n_perm=999, seed=123):
    rng = np.random.default_rng(seed)
    groups = np.asarray(groups)
    n = len(groups)
    D2 = dist_sq ** 2
    unique_groups = np.unique(groups)
    a = len(unique_groups)

    def ss_within(grp):
        ssw = 0.0
        for g in np.unique(grp):
            idx = np.where(grp == g)[0]
            ng = len(idx)
            if ng > 1:
                ssw += D2[np.ix_(idx, idx)].sum() / (2.0 * ng)
        return ssw

    ss_total = D2.sum() / (2.0 * n)
    ss_w = ss_within(groups)
    ss_m = ss_total - ss_w
    df_m = a - 1
    df_r = n - a
    ms_m = ss_m / df_m if df_m > 0 else np.nan
    ms_r = ss_w / df_r if df_r > 0 else np.nan
    f_obs = ms_m / ms_r if ms_r > 0 else np.nan
    r2 = ss_m / ss_total if ss_total > 0 else np.nan

    f_perm = []
    for _ in range(n_perm):
        perm = rng.permutation(groups)
        ssw_p = ss_within(perm)
        ssm_p = ss_total - ssw_p
        msr_p = ssw_p / df_r if df_r > 0 else np.nan
        f_perm.append(ssm_p / df_m / msr_p if df_m > 0 and msr_p > 0 else np.nan)
    f_perm = np.array(f_perm)
    p = (np.sum(f_perm >= f_obs) + 1) / (n_perm + 1) if not np.isnan(f_obs) else np.nan

    table = pd.DataFrame({
        'Df': [df_m, df_r, n - 1],
        'SumOfSqs': [ss_m, ss_w, ss_total],
        'R2': [r2, 1 - r2, 1.0],
        'F': [f_obs, np.nan, np.nan],
        'Pr(>F)': [p, np.nan, np.nan]
    }, index=['group', 'Residual', 'Total'])
    return table


def _mrpp(dist_vec, dist_sq, groups, n_perm=999, seed=123):
    rng = np.random.default_rng(seed)
    groups = np.asarray(groups)
    n = len(groups)
    pair_idx = np.triu_indices(n, k=1)
    pair_groups = np.array([tuple(sorted([groups[i], groups[j]])) for i, j in zip(pair_idx[0], pair_idx[1])])
    same_mask = np.array([groups[i] == groups[j] for i, j in zip(pair_idx[0], pair_idx[1])])

    def delta(grp):
        d = 0.0
        for g in np.unique(grp):
            idx = np.where(grp == g)[0]
            ng = len(idx)
            if ng > 1:
                mask = np.zeros(len(dist_vec), dtype=bool)
                # pairs fully inside group g
                pair_g = np.array([grp[i] == g and grp[j] == g for i, j in zip(pair_idx[0], pair_idx[1])])
                d += (ng / n) * dist_vec[pair_g].mean()
        return d

    obs_delta = delta(groups)
    expect_delta = dist_vec.mean()
    a = (expect_delta - obs_delta) / expect_delta if expect_delta else np.nan

    perm_deltas = []
    for _ in range(n_perm):
        perm = rng.permutation(groups)
        perm_deltas.append(delta(perm))
    perm_deltas = np.array(perm_deltas)
    p = (np.sum(perm_deltas <= obs_delta) + 1) / (n_perm + 1)

    df = pd.DataFrame({
        'group': ['all'],
        'distance': ['Bray-Curtis'],
        'A': [a],
        'observe_delta': [obs_delta],
        'expect_delta': [expect_delta],
        'p_value': [p]
    })
    return df


def _prepare_beta_matrix(df, group_df):
    """Return samples x features matrix aligned with group_df and group labels."""
    if isinstance(df, pd.DataFrame) and df.index.name is None:
        # tax relative format: first column is feature, rest samples
        feat_col = df.columns[0]
        mat = df.set_index(feat_col).T
    else:
        # functional diff format: features x samples
        mat = df.T
    mat = mat.apply(pd.to_numeric, errors='coerce')
    mat = mat.dropna(axis=1, how='all')
    mat = _drop_constant_zero_cols(mat)
    if mat.empty:
        return None, None
    common = [s for s in group_df['sample-id'] if s in mat.index]
    mat = mat.loc[common]
    groups = group_df.set_index('sample-id').loc[common, 'group'].values
    return mat, groups


def _anosim_plot(df_plot, r_value, p_value, out_pdf, out_html):
    classes = list(df_plot['x'].unique())
    k_gros = len(classes)
    w, h = _dynamic_size(k_gros)

    fig, ax = plt.subplots(figsize=(w, h))
    data_by_class = [df_plot.loc[df_plot['x'] == c, 'y'].values for c in classes]
    bp = ax.boxplot(data_by_class, labels=classes, patch_artist=True)
    for patch, color in zip(bp['boxes'], YANSE):
        patch.set_facecolor(color)
    ax.set_title(f'R={r_value:.3f}, pvalue={p_value:.4g}')
    ax.set_ylabel('Rank of Distance (Bray_Curtis)')
    ax.set_xlabel('')
    plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
    plt.tight_layout()
    fig.savefig(out_pdf, format='pdf', bbox_inches='tight')
    plt.close(fig)

    figp = go.Figure()
    for c, color in zip(classes, YANSE):
        figp.add_trace(go.Box(y=df_plot.loc[df_plot['x'] == c, 'y'].values, name=c, marker_color=color))
    figp.update_layout(title=f'R={r_value:.3f}, pvalue={p_value:.4g}',
                       yaxis_title='Rank of Distance (Bray_Curtis)', showlegend=False, plot_bgcolor='white')
    figp.write_html(out_html, include_plotlyjs=True)


def plot_anosim(table_dir, data_dir, res_dir, kind='tax'):
    log.info('ANOSIM: %s', kind)
    metadata = _read_metadata(data_dir)
    if metadata is None:
        return

    for gro_num, group_df in _iter_groups(metadata):
        if kind == 'tax':
            for clas in CLASSES:
                type_dir = os.path.join(table_dir, gro_num, '5-TaxAnnotation', '1.Tables', 'Samples', clas)
                if not os.path.exists(type_dir):
                    continue
                for specie in SPECIES:
                    df = _read_tax_relative(type_dir, specie)
                    if df is None or df.shape[0] < 2:
                        continue
                    mat, groups = _prepare_beta_matrix(df, group_df)
                    if mat is None:
                        continue
                    dist_vec, dist_sq = _bray_curtis_matrix(mat)
                    r, p, df_plot = _anosim(dist_vec, dist_sq, groups)
                    if np.isnan(r):
                        continue
                    resdir = os.path.join(res_dir, gro_num, '6-TaxStatistical_analysis', clas, specie, '6.Anosim')
                    os.makedirs(resdir, exist_ok=True)
                    comp = '_vs_'.join(map(str, np.unique(groups)))
                    res_df = pd.DataFrame({'group': [comp], 'distance': ['Bray-Curtis'], 'R': [r], 'p_value': [p]})
                    res_df.to_excel(os.path.join(resdir, f'{clas}_{specie}_Anosim.xlsx'), index=False)
                    _anosim_plot(df_plot, r, p,
                                 os.path.join(resdir, f'{clas}_{specie}_Anosim.pdf'),
                                 os.path.join(resdir, f'{clas}_{specie}_Anosim.html'))
        else:
            for func in FUNC_INDEX:
                func_table_dir = os.path.join(table_dir, gro_num, func)
                if not os.path.exists(func_table_dir):
                    continue
                for file in os.listdir(func_table_dir):
                    if not file.endswith('_diff.tsv'):
                        continue
                    df = _read_func_diff(func_table_dir, file)
                    if df.shape[0] < 2:
                        continue
                    mat, groups = _prepare_beta_matrix(df, group_df)
                    if mat is None:
                        continue
                    dist_vec, dist_sq = _bray_curtis_matrix(mat)
                    r, p, df_plot = _anosim(dist_vec, dist_sq, groups)
                    if np.isnan(r):
                        continue
                    prefix = file[:-9]
                    resdir = _func_resdir(res_dir, gro_num, func, '6.Anosim')
                    os.makedirs(resdir, exist_ok=True)
                    comp = '_vs_'.join(map(str, np.unique(groups)))
                    res_df = pd.DataFrame({'group': [comp], 'distance': ['Bray-Curtis'], 'R': [r], 'p_value': [p]})
                    res_df.to_excel(os.path.join(resdir, f'{prefix}_Anosim.xlsx'), index=False)
                    _anosim_plot(df_plot, r, p,
                                 os.path.join(resdir, f'{prefix}_Anosim.pdf'),
                                 os.path.join(resdir, f'{prefix}_Anosim.html'))


def plot_adonis(table_dir, data_dir, res_dir, kind='tax'):
    log.info('PERMANOVA (Adonis): %s', kind)
    metadata = _read_metadata(data_dir)
    if metadata is None:
        return

    for gro_num, group_df in _iter_groups(metadata):
        if kind == 'tax':
            for clas in CLASSES:
                type_dir = os.path.join(table_dir, gro_num, '5-TaxAnnotation', '1.Tables', 'Samples', clas)
                if not os.path.exists(type_dir):
                    continue
                for specie in SPECIES:
                    df = _read_tax_relative(type_dir, specie)
                    if df is None or df.shape[0] < 2:
                        continue
                    mat, groups = _prepare_beta_matrix(df, group_df)
                    if mat is None:
                        continue
                    _, dist_sq = _bray_curtis_matrix(mat)
                    table = _permanova(dist_sq, groups)
                    resdir = os.path.join(res_dir, gro_num, '6-TaxStatistical_analysis', clas, specie, '7.Adonis')
                    os.makedirs(resdir, exist_ok=True)
                    table.to_excel(os.path.join(resdir, 'Adonis.xlsx'), index=True)
        else:
            for func in FUNC_INDEX:
                func_table_dir = os.path.join(table_dir, gro_num, func)
                if not os.path.exists(func_table_dir):
                    continue
                for file in os.listdir(func_table_dir):
                    if not file.endswith('_diff.tsv'):
                        continue
                    df = _read_func_diff(func_table_dir, file)
                    if df.shape[0] < 2:
                        continue
                    mat, groups = _prepare_beta_matrix(df, group_df)
                    if mat is None:
                        continue
                    _, dist_sq = _bray_curtis_matrix(mat)
                    table = _permanova(dist_sq, groups)
                    prefix = file[:-9]
                    resdir = _func_resdir(res_dir, gro_num, func, '7.Adonis')
                    os.makedirs(resdir, exist_ok=True)
                    table.to_excel(os.path.join(resdir, f'{prefix}_Adonis.xlsx'), index=True)


def plot_mrpp(table_dir, data_dir, res_dir, kind='tax'):
    log.info('MRPP: %s', kind)
    metadata = _read_metadata(data_dir)
    if metadata is None:
        return

    for gro_num, group_df in _iter_groups(metadata):
        if kind == 'tax':
            for clas in CLASSES:
                type_dir = os.path.join(table_dir, gro_num, '5-TaxAnnotation', '1.Tables', 'Samples', clas)
                if not os.path.exists(type_dir):
                    continue
                for specie in SPECIES:
                    df = _read_tax_relative(type_dir, specie)
                    if df is None or df.shape[0] < 2:
                        continue
                    mat, groups = _prepare_beta_matrix(df, group_df)
                    if mat is None:
                        continue
                    dist_vec, dist_sq = _bray_curtis_matrix(mat)
                    res_df = _mrpp(dist_vec, dist_sq, groups)
                    resdir = os.path.join(res_dir, gro_num, '6-TaxStatistical_analysis', clas, specie, '8.MRPP')
                    os.makedirs(resdir, exist_ok=True)
                    res_df.to_excel(os.path.join(resdir, 'MRPP.xlsx'), index=False)
        else:
            for func in FUNC_INDEX:
                func_table_dir = os.path.join(table_dir, gro_num, func)
                if not os.path.exists(func_table_dir):
                    continue
                for file in os.listdir(func_table_dir):
                    if not file.endswith('_diff.tsv'):
                        continue
                    df = _read_func_diff(func_table_dir, file)
                    if df.shape[0] < 2:
                        continue
                    mat, groups = _prepare_beta_matrix(df, group_df)
                    if mat is None:
                        continue
                    dist_vec, dist_sq = _bray_curtis_matrix(mat)
                    res_df = _mrpp(dist_vec, dist_sq, groups)
                    prefix = file[:-9]
                    resdir = _func_resdir(res_dir, gro_num, func, '8.MRPP')
                    os.makedirs(resdir, exist_ok=True)
                    res_df.to_excel(os.path.join(resdir, f'{prefix}_MRPP.xlsx'), index=False)
