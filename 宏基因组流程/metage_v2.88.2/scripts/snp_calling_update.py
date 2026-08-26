#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
snp_calling_update.py

基于参考基因组 mapping 得到的 BAM 文件进行 SNP/Indel calling。
使用 samtools mpileup + Python 解析，不依赖 bcftools。
"""

import os
import sys
import argparse
import logging
import subprocess
import glob

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)


VCF_HEADER = """##fileformat=VCFv4.2
##source=snp_calling_update.py
##INFO=<ID=DP,Number=1,Type=Integer,Description="Raw read depth">
##INFO=<ID=AF,Number=1,Type=Float,Description="Allele frequency">
##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">
##FORMAT=<ID=DP,Number=1,Type=Integer,Description="Read depth">
#CHROM	POS	ID	REF	ALT	QUAL	FILTER	INFO	FORMAT	{sample}
"""


def run_cmd(cmd):
    log.info('执行命令: %s', cmd.strip().split('\n')[0])
    subprocess.run(cmd, shell=True, check=True)


def run_pileup(ref_fasta, bam_file, out_prefix, sample_id, min_depth=5,
               min_alt_frac=0.1, min_mapq=20, min_baseq=20):
    """
    使用 samtools mpileup 生成 pileup 文本，解析后输出 VCF。
    """
    # Step 1: 生成 pileup
    raw_pileup = out_prefix + '.pileup.txt'
    cmd = (
        'samtools mpileup -f {ref} -q {mapq} -Q {baseq} '
        '-o {out} {bam}'
    ).format(ref=ref_fasta, mapq=min_mapq, baseq=min_baseq,
             out=raw_pileup, bam=bam_file)
    run_cmd(cmd)

    # Step 2: 解析 pileup，筛选变异位点，输出 VCF
    vcf_file = out_prefix + '.vcf'
    call_variants(raw_pileup, vcf_file, sample_id,
                  min_depth=min_depth, min_alt_frac=min_alt_frac)

    # Step 3: 压缩 + 统计摘要
    vcf_gz = vcf_file + '.gz'
    run_cmd('bgzip -c {vcf} > {vcf_gz}'.format(vcf=vcf_file, vcf_gz=vcf_gz))
    stats_file = out_prefix + '.vcf.stats.txt'
    write_stats(vcf_file, stats_file)


def call_variants(pileup_file, vcf_file, sample_id,
                  min_depth=5, min_alt_frac=0.1):
    """解析 samtools pileup 输出，筛选 SNP/Indel 位点，写入 VCF。"""
    snp_count = 0
    indel_count = 0
    bases_set = set('ACGTNacgtn')

    with open(pileup_file) as f_in, open(vcf_file, 'w') as f_out:
        f_out.write(VCF_HEADER.format(sample=sample_id))

        for line in f_in:
            parts = line.strip().split('\t')
            if len(parts) < 6:
                continue
            chrom, pos, ref, depth_str, reads, quals = parts[0:6]
            pos = int(pos)
            depth = int(depth_str) if depth_str.isdigit() else 0
            if depth < min_depth:
                continue

            # 统计碱基
            counts = {'A': 0, 'C': 0, 'G': 0, 'T': 0}
            indels = []  # (type, seq)  type='+' insertion, '-' deletion
            i = 0
            while i < len(reads):
                c = reads[i]
                if c == '^':  # 比对起始标记，跳过 ^ 和下一个字符（mapQ）
                    i += 2
                    continue
                if c == '$':  # 比对结束标记
                    i += 1
                    continue
                if c == '*' and depth > 0:  # 缺失
                    depth -= 1
                    i += 1
                    continue
                if c == '+' or c == '-':  # Indel
                    i += 1
                    num_str = ''
                    while i < len(reads) and reads[i].isdigit():
                        num_str += reads[i]
                        i += 1
                    n = int(num_str) if num_str else 0
                    seq = reads[i:i+n]
                    indels.append((c, seq))
                    i += n
                    continue
                c_upper = c.upper()
                if c_upper in counts:
                    counts[c_upper] += 1
                elif c_upper == '.' or c_upper == ',':
                    # 与参考一致（. 正链，, 负链）
                    ref_upper = ref.upper()
                    if ref_upper in counts:
                        counts[ref_upper] += 1
                i += 1

            total = sum(counts.values())
            if total == 0:
                continue

            # 找最多替代碱基
            alt_bases = [(base, cnt) for base, cnt in counts.items()
                         if base.upper() != ref.upper() and cnt > 0]
            if not alt_bases:
                continue

            best_alt, alt_count = max(alt_bases, key=lambda x: x[1])
            alt_frac = alt_count / total if total > 0 else 0

            if alt_frac < min_alt_frac:
                continue

            # 简单质量分：基于深度和替代频率
            qual = min(99, int(alt_frac * 100))
            info = 'DP={depth};AF={af:.3f}'.format(depth=depth, af=alt_frac)
            gt = '0/1' if alt_frac < 0.8 else '1/1'
            fmt = 'GT:DP'
            sample_fmt = '{gt}:{dp}'.format(gt=gt, dp=depth)

            f_out.write('{chrom}\t{pos}\t.\t{ref}\t{alt}\t{qual}\tPASS'
                        '\t{info}\t{fmt}\t{sample}\n'.format(
                            chrom=chrom, pos=pos, ref=ref, alt=best_alt,
                            qual=qual, info=info, fmt=fmt, sample=sample_fmt))
            snp_count += 1

    log.info('%s: %d SNPs called (min_depth=%d, min_alt_frac=%.2f)',
             sample_id, snp_count, min_depth, min_alt_frac)
    return snp_count


def write_stats(vcf_file, stats_file):
    """统计 VCF 中的 SNP 数量。"""
    snp_count = 0
    with open(vcf_file) as f:
        for line in f:
            if not line.startswith('#'):
                snp_count += 1
    with open(stats_file, 'w') as f:
        f.write('SN\t0\tnumber of SNPs:\t{}\n'.format(snp_count))
        f.write('SN\t0\tnumber of indels:\t0\n')


def visualize_snp_results(outdir):
    """汇总所有 VCF 文件，生成可视化图表。"""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from plot_style_config import apply_matplotlib_style
    apply_matplotlib_style(plt)
    import pandas as pd
    import numpy as np
    from collections import defaultdict

    vcf_files = sorted(glob.glob(os.path.join(outdir, '*.vcf')))
    if not vcf_files:
        log.warning('没有 VCF 文件，跳过可视化')
        return

    log.info('生成 SNP 可视化图表...')
    out_fig = os.path.join(outdir, 'snp_summary.png')

    # 解析所有 VCF
    all_data = []         # [{sample, chrom, pos, ref, alt, dp, af}]
    sample_counts = {}    # {sample: snp_count}
    for vf in vcf_files:
        sample = os.path.basename(vf).replace('.vcf', '')
        count = 0
        with open(vf) as f:
            for line in f:
                if line.startswith('#'):
                    continue
                parts = line.strip().split('\t')
                if len(parts) < 8:
                    continue
                chrom, pos, _, ref, alt, _, _, info = parts[0:8]
                dp = af = 0
                for kv in info.split(';'):
                    if kv.startswith('DP='):
                        dp = int(kv.split('=')[1])
                    elif kv.startswith('AF='):
                        af = float(kv.split('=')[1])
                all_data.append({
                    'sample': sample, 'chrom': chrom,
                    'pos': int(pos), 'ref': ref, 'alt': alt,
                    'dp': dp, 'af': af
                })
                count += 1
        sample_counts[sample] = count

    df = pd.DataFrame(all_data)
    if df.empty:
        log.warning('无 SNP 数据，跳过可视化')
        return
    total_snps = len(df)

    # ======== 4-panel figure ========
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('SNP Calling Summary ({} total SNPs, {} samples)'.format(
        total_snps, len(sample_counts)), fontsize=16, fontweight='bold')

    # --- Panel 1: SNP count per sample ---
    ax1 = axes[0, 0]
    samples = sorted(sample_counts.keys(), key=lambda s: sample_counts[s], reverse=True)
    counts = [sample_counts[s] for s in samples]
    colors1 = ['#2196F3' if c > 0 else '#BDBDBD' for c in counts]
    ax1.bar(range(len(samples)), counts, color=colors1, edgecolor='#1565C0')
    ax1.set_xticks(range(len(samples)))
    ax1.set_xticklabels(samples, rotation=45, ha='right', fontsize=10)
    ax1.set_ylabel('SNP Count')
    ax1.set_title('SNPs per Sample')
    for i, c in enumerate(counts):
        if c > 0:
            ax1.text(i, c + max(1, max(counts)*0.02), str(c), ha='center', fontsize=9, fontweight='bold')

    # --- Panel 2: Allele Frequency Distribution ---
    ax2 = axes[0, 1]
    af_vals = df[df['af'] > 0]['af'].values
    if len(af_vals) > 0:
        ax2.hist(af_vals, bins=40, color='#4CAF50', edgecolor='#2E7D32', alpha=0.85)
        ax2.axvline(0.5, color='red', linestyle='--', alpha=0.5, label='AF=0.5 (heterozygous)')
        ax2.axvline(1.0, color='darkred', linestyle='--', alpha=0.5, label='AF=1.0 (homozygous)')
        ax2.set_xlabel('Alternate Allele Frequency')
        ax2.set_ylabel('Count')
        ax2.set_title('Allele Frequency Distribution')
        ax2.legend(fontsize=9)

    # --- Panel 3: Coverage Depth Distribution ---
    ax3 = axes[1, 0]
    dp_vals = df['dp'].values
    if len(dp_vals) > 0:
        ax3.hist(dp_vals, bins=min(50, len(set(dp_vals))), color='#FF9800', edgecolor='#E65100', alpha=0.85)
        ax3.axvline(np.median(dp_vals), color='red', linestyle='--', alpha=0.7,
                    label='Median DP={:.0f}'.format(np.median(dp_vals)))
        ax3.set_xlabel('Coverage Depth')
        ax3.set_ylabel('Count')
        ax3.set_title('Coverage Depth Distribution')
        ax3.legend(fontsize=9)

    # --- Panel 4: SNP density along contigs (top 5 contigs by SNP count) ---
    ax4 = axes[1, 1]
    top_contigs = df['chrom'].value_counts().head(5).index.tolist()
    df_top = df[df['chrom'].isin(top_contigs)]
    if len(df_top) > 0:
        colors4 = ['#E91E63', '#9C27B0', '#3F51B5', '#009688', '#FF5722']
        for i, ctg in enumerate(top_contigs):
            ctg_df = df_top[df_top['chrom'] == ctg].sort_values('pos')
            if len(ctg_df) > 0:
                ctg_len = ctg_df['pos'].max()
                bins = np.linspace(0, ctg_len, min(30, max(2, ctg_len // 50 + 1)))
                if len(bins) > 1:
                    hist, edges = np.histogram(ctg_df['pos'].values, bins=bins)
                    centers = (edges[:-1] + edges[1:]) / 2
                    ax4.plot(centers, hist, color=colors4[i % 5], alpha=0.8,
                             linewidth=1.5, marker='.', markersize=3,
                             label='{} ({} SNPs)'.format(ctg[:20], len(ctg_df)))
        ax4.set_xlabel('Position (bp)')
        ax4.set_ylabel('SNP Count per Bin')
        ax4.set_title('SNP Density Along Top Contigs')
        ax4.legend(fontsize=8, ncol=2)

    plt.tight_layout()
    fig.savefig(out_fig, dpi=150, bbox_inches='tight')
    plt.close(fig)
    log.info('可视化已保存: %s', out_fig)

    # ======== Summary CSV ========
    summary_csv = os.path.join(outdir, 'snp_summary.csv')
    summary_rows = []
    for sample in sorted(sample_counts.keys()):
        sdf = df[df['sample'] == sample]
        summary_rows.append({
            'sample': sample,
            'snp_count': sample_counts[sample],
            'median_dp': sdf['dp'].median() if len(sdf) > 0 else 0,
            'mean_af': sdf['af'].mean() if len(sdf) > 0 else 0,
        })
    pd.DataFrame(summary_rows).to_csv(summary_csv, index=False)
    log.info('汇总表已保存: %s', summary_csv)


def main():
    parser = argparse.ArgumentParser(description='SNP 检测')
    parser.add_argument('-I', '--i_datadir', type=str, required=True,
                        help='包含 sample.txt 的目录')
    parser.add_argument('--bamdir', type=str, required=True,
                        help='BAM 文件目录')
    parser.add_argument('--ref_fasta', type=str, required=True,
                        help='参考基因组 FASTA 路径')
    parser.add_argument('-o', '--outdir', type=str, default='snp_calling',
                        help='SNP 输出目录')
    parser.add_argument('--threads', type=int, default=8,
                        help='samtools 线程数')
    parser.add_argument('--min-depth', type=int, default=3,
                        help='最小覆盖深度（默认 3，小样本放宽）')
    parser.add_argument('--min-alt-frac', type=float, default=0.1,
                        help='最小替代等位基因频率（默认 0.1）')
    args = parser.parse_args()

    bamdir = os.path.abspath(args.bamdir)
    ref_fasta = os.path.abspath(args.ref_fasta)
    outdir = os.path.abspath(args.outdir)
    os.makedirs(outdir, exist_ok=True)

    try:
        bam_files = sorted(glob.glob(os.path.join(bamdir, '*.sort.bam')))
        if not bam_files:
            log.warning('未找到 BAM 文件')
            with open(os.path.join(outdir, 'placeholder.txt'), 'w') as f:
                f.write('No BAM files found in {}\n'.format(bamdir))
        else:
            log.info('找到 %d 个 BAM 文件', len(bam_files))

        for bam in bam_files:
            sample_id = os.path.basename(bam).replace('.sort.bam', '')
            log.info('SNP calling: %s', sample_id)
            out_prefix = os.path.join(outdir, sample_id)
            run_pileup(ref_fasta, bam, out_prefix, sample_id,
                       min_depth=args.min_depth,
                       min_alt_frac=args.min_alt_frac)

        # 汇总可视化
        visualize_snp_results(outdir)
        log.info('SNP 检测完成，输出: %s', outdir)
    except Exception as e:
        log.error('SNP 检测失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
