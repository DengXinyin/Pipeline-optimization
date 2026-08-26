#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Update version of res2json.py

import os
import sys
import json
import time
import glob
import argparse
import logging

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)


def get_businfo(datadir, respath):
    project_info_path = os.path.join(datadir, 'project_info.json')
    if not os.path.exists(project_info_path):
        raise FileNotFoundError(f'project_info.json 不存在: {project_info_path}')
    with open(project_info_path, encoding='utf-8') as f:
        bus_info = json.load(f)
    bus_dict = {
        '客户名称': bus_info['客户名称'],
        '客户单位': bus_info['客户单位'],
        '项目编号': bus_info['项目编号'],
        '报告时间': str(time.strftime('%Y-%m-%d', time.localtime())),
    }
    out_path = os.path.join(respath, 'bus_info.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(bus_dict, f, ensure_ascii=False)
    log.info('生成 %s', out_path)


def get_sample(datadir, respath):
    sample = pd.read_csv(os.path.join(datadir, 'sample-metadata.tsv'), sep='\t', skiprows=[1])
    sample_dict = {
        'columns': ['样品', '分组'],
        'data': sample.to_numpy().tolist(),
    }
    out_path = os.path.join(respath, 'sample_info.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(sample_dict, f, ensure_ascii=False)
    log.info('生成 %s', out_path)


def get_filenames(org_path, max_files=20):
    file_ls_h = []
    file_ls_p = []
    for ch_path in glob.iglob(org_path):
        for path, _dir_list, file_list in os.walk(ch_path):
            for file in file_list:
                file_path = os.path.abspath(os.path.join(path, file))
                if file.endswith('html'):
                    file_ls_h.append(file_path)
                elif file.endswith('png'):
                    file_ls_p.append(file_path)
    return file_ls_h[:max_files] + file_ls_p[:max_files]


def get_path_kv(path, end_chr, keyword, max_files=20):
    secondary_dict = {}
    file_list = get_filenames(path, max_files)
    for i, file_path in enumerate(file_list):
        if not file_path.endswith(end_chr):
            continue
        if keyword and keyword not in file_path:
            continue
        file_name = os.path.basename(file_path) + str(i + 1)
        secondary_dict[file_name] = file_path
    return secondary_dict


def image2json(sorpath, end_chr, keyword, max_files=20):
    main_dict = {
        'isGetFileToProject': True,
        'data': get_path_kv(sorpath, end_chr, keyword, max_files),
    }
    return main_dict


def write_json(sorpath, respath, json_name, subpath, end_chr, keyword=False, max_files=20):
    out_path = os.path.join(respath, json_name)
    try:
        main_dict = image2json(os.path.join(sorpath, subpath), end_chr, keyword, max_files)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(main_dict, f, ensure_ascii=False)
        log.info('生成 %s', out_path)
    except Exception as e:
        log.error('生成 %s 失败: %s', out_path, e)


def get_image_json(sorpath, respath, max_files=20):
    tasks = [
        ('error_rate.json', 'Result/group*/1-data_quality', 'html', 'error_rate'),
        ('ATGC_content.json', 'Result/group*/1-data_quality', 'html', 'ATGC_content'),
        ('reads_quality_summary.json', 'Result/group*/1-data_quality', 'png', 'reads_quality_summary'),
        ('contig_length.json', 'Result/group*/2-Assembly', 'html', False),
        ('gene_length.json', 'Result/group*/3-GenePredict', 'html', False),
        ('sample.corr_heatmap.json', 'Result/group*/4-GeneAbundance/Sample_correlation', 'png', False),
        ('upset.json', 'Result/group*/4-GeneAbundance/Venn', 'png', False),
        ('krona.json', 'Result/group*/5-TaxAnnotation/2.Krona', 'html', False),
        ('tax_barplot.json', 'Result/group*/5-TaxAnnotation/3.Barplot/Samples', 'html', False),
        ('tax_bar_tree.json', 'Result/group*/5-TaxAnnotation/4.Bar_tree', 'png', False),
        ('tax_heatmap.json', 'Result/group*/5-TaxAnnotation/5.Heatmap/Samples', 'html', False),
        ('alpha.json', 'Result/group*/5-TaxAnnotation/7.alpha_diversity_analysis/*', 'html', False),
        ('tax_PCA.json', 'Result/group*/5-TaxAnnotation/6.Beta_diversity_analysis/*/*/1.PCA', 'html', False),
        ('tax_PCoA.json', 'Result/group*/5-TaxAnnotation/6.Beta_diversity_analysis/*/*/2.PCoA', 'html', False),
        ('tax_NMDS.json', 'Result/group*/5-TaxAnnotation/6.Beta_diversity_analysis/*/*/3.NMDS', 'html', False),
        ('tax_ANOVA.json', 'Result/group*/6-TaxStatistical_analysis/*/*/1.ANOVA', 'html', False),
        ('tax_wilcoxon.json', 'Result/group*/6-TaxStatistical_analysis/*/*/2.wilcoxon', 'html', False),
        ('tax_Stamp.json', 'Result/group*/6-TaxStatistical_analysis/*/*/3.Stamp', 'png', False),
        ('tax_Random_Forest.json', 'Result/group*/6-TaxStatistical_analysis/*/*/4.Random_Forest', 'html', False),
        ('tax_metagenomeSeq.json', 'Result/group*/6-TaxStatistical_analysis/*/*/5.metagenomeSeq', 'html', False),
        ('tax_Anosim.json', 'Result/group*/6-TaxStatistical_analysis/*/*/6.Anosim', 'html', False),
        ('tax_Lefse.json', 'Result/group*/6-TaxStatistical_analysis/*/*/9.Lefse', 'html', False),
        ('func_Barplot.json', 'Result/group*/7-FunctionAnnotation/*/1.Barplot', 'html', False),
        ('func_Heatmap.json', 'Result/group*/7-FunctionAnnotation/*/2.Heatmap', 'html', False),
        ('func_PCA.json', 'Result/group*/7-FunctionAnnotation/*/3.PCA', 'html', False),
        ('func_PCoA.json', 'Result/group*/7-FunctionAnnotation/*/4.PCoA', 'html', False),
        ('func_NMDS.json', 'Result/group*/7-FunctionAnnotation/*/5.NMDS', 'html', False),
        ('func_ANOVA.json', 'Result/group*/8-FunctionStatistical_analysis/*/1.ANOVA', 'html', False),
        ('func_wilcoxon.json', 'Result/group*/8-FunctionStatistical_analysis/*/2.wilcoxon', 'html', False),
        ('func_Stamp.json', 'Result/group*/8-FunctionStatistical_analysis/*/3.Stamp', 'png', False),
        ('func_Random_Forest.json', 'Result/group*/8-FunctionStatistical_analysis/*/4.Random_Forest', 'html', False),
        ('func_metagenomeSeq.json', 'Result/group*/8-FunctionStatistical_analysis/*/5.metagenomeSeq', 'html', False),
        ('func_Anosim.json', 'Result/group*/8-FunctionStatistical_analysis/*/6.Anosim', 'html', False),
        ('func_Lefse.json', 'Result/group*/8-FunctionStatistical_analysis/*/9.Lefse', 'html', False),
        ('Cyc_Barplot.json', 'Result/group*/9-METABOLIC/*/1.Barplot', 'html', False),
        ('Cyc_Heatmap.json', 'Result/group*/9-METABOLIC/*/2.Heatmap', 'html', False),
        ('Cyc_PCA.json', 'Result/group*/9-METABOLIC/*/3.PCA', 'html', False),
        ('Cyc_PCoA.json', 'Result/group*/9-METABOLIC/*/4.PCoA', 'html', False),
        ('Cyc_NMDS.json', 'Result/group*/9-METABOLIC/*/5.NMDS', 'html', False),
        ('Cyc_ANOVA.json', 'Result/group*/9-METABOLIC/*/6.Statistical_test_analysis/1.ANOVA', 'html', False),
        ('Cyc_wilcoxon.json', 'Result/group*/9-METABOLIC/*/6.Statistical_test_analysis/2.wilcoxon', 'html', False),
        ('Cyc_Stamp.json', 'Result/group*/9-METABOLIC/*/6.Statistical_test_analysis/3.Stamp', 'png', False),
        ('Cyc_Random_Forest.json', 'Result/group*/9-METABOLIC/*/6.Statistical_test_analysis/4.Random_Forest', 'html', False),
        ('Cyc_metagenomeSeq.json', 'Result/group*/9-METABOLIC/*/6.Statistical_test_analysis/5.metagenomeSeq', 'html', False),
        ('Cyc_Anosim.json', 'Result/group*/9-METABOLIC/*/6.Statistical_test_analysis/6.Anosim', 'html', False),
        ('Cyc_Lefse.json', 'Result/group*/9-METABOLIC/*/6.Statistical_test_analysis/9.Lefse', 'html', False),
        ('ARG_Barplot.json', 'Result/group*/10-ARG/1.Barplot', 'html', False),
        ('ARG_Heatmap.json', 'Result/group*/10-ARG/2.Heatmap', 'html', False),
        ('ARG_PCA.json', 'Result/group*/10-ARG/3.PCA', 'html', False),
        ('ARG_PCoA.json', 'Result/group*/10-ARG/4.PCoA', 'html', False),
        ('ARG_NMDS.json', 'Result/group*/10-ARG/5.NMDS', 'html', False),
        ('ARG_ANOVA.json', 'Result/group*/10-ARG/6.Statistical_test_analysis/1.ANOVA', 'html', False),
        ('ARG_wilcoxon.json', 'Result/group*/10-ARG/6.Statistical_test_analysis/2.wilcoxon', 'html', False),
        ('ARG_Stamp.json', 'Result/group*/10-ARG/6.Statistical_test_analysis/3.Stamp', 'png', False),
        ('ARG_Random_Forest.json', 'Result/group*/10-ARG/6.Statistical_test_analysis/4.Random_Forest', 'html', False),
        ('ARG_metagenomeSeq.json', 'Result/group*/10-ARG/6.Statistical_test_analysis/5.metagenomeSeq', 'html', False),
        ('ARG_Anosim.json', 'Result/group*/10-ARG/6.Statistical_test_analysis/6.Anosim', 'html', False),
        ('ARG_Lefse.json', 'Result/group*/10-ARG/6.Statistical_test_analysis/9.Lefse', 'html', False),
        ('VFDB_Barplot.json', 'Result/group*/11-VFDB/1.Barplot', 'html', False),
        ('VFDB_Heatmap.json', 'Result/group*/11-VFDB/2.Heatmap', 'html', False),
        ('VFDB_PCA.json', 'Result/group*/11-VFDB/3.PCA', 'html', False),
        ('VFDB_PCoA.json', 'Result/group*/11-VFDB/4.PCoA', 'html', False),
        ('VFDB_NMDS.json', 'Result/group*/11-VFDB/5.NMDS', 'html', False),
        ('VFDB_ANOVA.json', 'Result/group*/11-VFDB/6.Statistical_test_analysis/1.ANOVA', 'html', False),
        ('VFDB_wilcoxon.json', 'Result/group*/11-VFDB/6.Statistical_test_analysis/2.wilcoxon', 'html', False),
        ('VFDB_Stamp.json', 'Result/group*/11-VFDB/6.Statistical_test_analysis/3.Stamp', 'png', False),
        ('VFDB_Random_Forest.json', 'Result/group*/11-VFDB/6.Statistical_test_analysis/4.Random_Forest', 'html', False),
        ('VFDB_metagenomeSeq.json', 'Result/group*/11-VFDB/6.Statistical_test_analysis/5.metagenomeSeq', 'html', False),
        ('VFDB_Anosim.json', 'Result/group*/11-VFDB/6.Statistical_test_analysis/6.Anosim', 'html', False),
        ('VFDB_Lefse.json', 'Result/group*/11-VFDB/6.Statistical_test_analysis/9.Lefse', 'html', False),
        ('mobileOG_Barplot.json', 'Result/group*/12-mobileOG/1.Barplot', 'html', False),
        ('mobileOG_Heatmap.json', 'Result/group*/12-mobileOG/2.Heatmap', 'html', False),
        ('mobileOG_PCA.json', 'Result/group*/12-mobileOG/3.PCA', 'html', False),
        ('mobileOG_PCoA.json', 'Result/group*/12-mobileOG/4.PCoA', 'html', False),
        ('mobileOG_NMDS.json', 'Result/group*/12-mobileOG/5.NMDS', 'html', False),
        ('mobileOG_ANOVA.json', 'Result/group*/12-mobileOG/6.Statistical_test_analysis/1.ANOVA', 'html', False),
        ('mobileOG_wilcoxon.json', 'Result/group*/12-mobileOG/6.Statistical_test_analysis/2.wilcoxon', 'html', False),
        ('mobileOG_Stamp.json', 'Result/group*/12-mobileOG/6.Statistical_test_analysis/3.Stamp', 'png', False),
        ('mobileOG_Random_Forest.json', 'Result/group*/12-mobileOG/6.Statistical_test_analysis/4.Random_Forest', 'html', False),
        ('mobileOG_metagenomeSeq.json', 'Result/group*/12-mobileOG/6.Statistical_test_analysis/5.metagenomeSeq', 'html', False),
        ('mobileOG_Anosim.json', 'Result/group*/12-mobileOG/6.Statistical_test_analysis/6.Anosim', 'html', False),
        ('mobileOG_Lefse.json', 'Result/group*/12-mobileOG/6.Statistical_test_analysis/9.Lefse', 'html', False),
        ('BacMet2_Barplot.json', 'Result/group*/13-BacMet2/1.Barplot', 'html', False),
        ('BacMet2_Heatmap.json', 'Result/group*/13-BacMet2/2.Heatmap', 'html', False),
        ('BacMet2_PCA.json', 'Result/group*/13-BacMet2/3.PCA', 'html', False),
        ('BacMet2_PCoA.json', 'Result/group*/13-BacMet2/4.PCoA', 'html', False),
        ('BacMet2_NMDS.json', 'Result/group*/13-BacMet2/5.NMDS', 'html', False),
        ('BacMet2_ANOVA.json', 'Result/group*/13-BacMet2/6.Statistical_test_analysis/1.ANOVA', 'html', False),
        ('BacMet2_wilcoxon.json', 'Result/group*/13-BacMet2/6.Statistical_test_analysis/2.wilcoxon', 'html', False),
        ('BacMet2_Stamp.json', 'Result/group*/13-BacMet2/6.Statistical_test_analysis/3.Stamp', 'png', False),
        ('BacMet2_Random_Forest.json', 'Result/group*/13-BacMet2/6.Statistical_test_analysis/4.Random_Forest', 'html', False),
        ('BacMet2_metagenomeSeq.json', 'Result/group*/13-BacMet2/6.Statistical_test_analysis/5.metagenomeSeq', 'html', False),
        ('BacMet2_Anosim.json', 'Result/group*/13-BacMet2/6.Statistical_test_analysis/6.Anosim', 'html', False),
        ('BacMet2_Lefse.json', 'Result/group*/13-BacMet2/6.Statistical_test_analysis/9.Lefse', 'html', False),
        ('QS_Barplot.json', 'Result/group*/14-QS/1.Barplot', 'html', False),
        ('QS_Heatmap.json', 'Result/group*/14-QS/2.Heatmap', 'html', False),
        ('QS_PCA.json', 'Result/group*/14-QS/3.PCA', 'html', False),
        ('QS_PCoA.json', 'Result/group*/14-QS/4.PCoA', 'html', False),
        ('QS_NMDS.json', 'Result/group*/14-QS/5.NMDS', 'html', False),
        ('QS_ANOVA.json', 'Result/group*/14-QS/6.Statistical_test_analysis/1.ANOVA', 'html', False),
        ('QS_wilcoxon.json', 'Result/group*/14-QS/6.Statistical_test_analysis/2.wilcoxon', 'html', False),
        ('QS_Stamp.json', 'Result/group*/14-QS/6.Statistical_test_analysis/3.Stamp', 'png', False),
        ('QS_Random_Forest.json', 'Result/group*/14-QS/6.Statistical_test_analysis/4.Random_Forest', 'html', False),
        ('QS_metagenomeSeq.json', 'Result/group*/14-QS/6.Statistical_test_analysis/5.metagenomeSeq', 'html', False),
        ('QS_Anosim.json', 'Result/group*/14-QS/6.Statistical_test_analysis/6.Anosim', 'html', False),
        ('QS_Lefse.json', 'Result/group*/14-QS/6.Statistical_test_analysis/9.Lefse', 'html', False),
        ('Bin_Plot.json', 'Result/binning/2.Bin_Plot', 'html', False),
        ('Bin_Abundance.json', 'Result/binning/3.Bin_Abundance', 'html', False),
    ]

    for json_name, subpath, end_chr, keyword in tasks:
        write_json(sorpath, respath, json_name, subpath, end_chr, keyword, max_files)


def json_check(dest_path):
    for file in os.listdir(dest_path):
        file_path = os.path.join(dest_path, file)
        if not file.endswith('.json'):
            continue
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data.get('data') == {}:
                log.info('删除空 JSON: %s', file)
                os.remove(file_path)
        except Exception as e:
            log.error('检查 %s 失败: %s', file, e)


def main():
    parser = argparse.ArgumentParser(description='Convert results to JSON (update version)')
    parser.add_argument('--sorc_path', type=str, required=True, help='the dir of Source path (Result)')
    parser.add_argument('-I', '--i_datadir', type=str, required=True, help='the dir of sample-metadata.tsv and project_info.json')
    parser.add_argument('--dest_path', type=str, default='jsonFile', help='the dir of Destination path')
    parser.add_argument('--max-files', type=int, default=20, help='max files per JSON')
    args = parser.parse_args()

    datadir = os.path.abspath(args.i_datadir)
    sorc_path = os.path.abspath(args.sorc_path)
    dest_path = os.path.abspath(args.dest_path)

    if not os.path.isdir(datadir):
        log.error('数据目录不存在: %s', datadir)
        sys.exit(1)
    if not os.path.isdir(sorc_path):
        log.error('源结果目录不存在: %s', sorc_path)
        sys.exit(1)
    os.makedirs(dest_path, exist_ok=True)

    try:
        get_image_json(sorc_path, dest_path, args.max_files)
        get_businfo(datadir, dest_path)
        get_sample(datadir, dest_path)
        json_check(dest_path)
        log.info('res2json 完成')
    except Exception as e:
        log.error('res2json 失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
