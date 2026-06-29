#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Updated: 2026-06-17
#   - 调用 QC_update.sh / Kneaddata_update.sh（GNU parallel 并行版）
#   - 使用多线程实现步骤间并行/依赖：
#       1) QC（必须完成）
#       2) deHOST 与 error_rate_table 可并行（均依赖 QC 输出）
#       3) QC_stats 等待 2) 完成后执行
#       4) plot_table 等待 QC_stats 完成后执行
#   - 所有子进程返回值与线程异常均被捕获，任意步骤失败即终止整个流程并输出错误信息。
# 从原始数据生成cleandata，注意格式必须为
# <sample><_1/2><.format><.gz>或者<sample><_R1/R2><.format><.gz>
import os, json, argparse, sys, subprocess
import pandas as pd
import threading
import numpy as np
from get_scriptspath import scripts_path, Rscript_j


class StepRunner:
    """简易线程调度器：启动线程、捕获异常/返回码、按阶段检查。"""
    def __init__(self):
        self.errors = {}
        self.lock = threading.Lock()

    def run(self, name, func, args):
        def wrapper():
            try:
                rc = func(*args)
                if rc != 0:
                    with self.lock:
                        self.errors[name] = f"exit code {rc}"
            except Exception as e:
                with self.lock:
                    self.errors[name] = f"{type(e).__name__}: {e}"
        t = threading.Thread(target=wrapper, name=name)
        t.start()
        return t

    def check(self, phase):
        if self.errors:
            print(f"[ERROR] Phase '{phase}' failed: {self.errors}", file=sys.stderr)
            sys.exit(1)


def run_cmd(cmd, step_name):
    """运行 shell 命令，返回 returncode；失败时打印错误。"""
    print(f"[INFO] [{step_name}] {cmd.strip()}")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"[ERROR] [{step_name}] exit code {result.returncode}", file=sys.stderr)
    return result.returncode


def QC(rawdatadir, datadir, cleandatadir):
    # 确保日志目录存在，避免重定向失败
    os.makedirs(os.path.join(cleandatadir, 'logs'), exist_ok=True)
    cmd = '''bash {0}/QC_update.sh {1} {2} {3} >{4}/logs/QC_update.sh.log 2>&1'''.format(
        scripts_path, rawdatadir, datadir, cleandatadir, cleandatadir)
    return run_cmd(cmd, "QC")


def error_rate_table(cleandatadir):
    qc_dir = os.path.join(cleandatadir, 'qc')
    res_dir = os.path.join(cleandatadir, 'table')
    if not os.path.exists(res_dir):
        os.mkdir(res_dir)
    files = os.listdir(qc_dir)
    for file in files:
        if file.endswith('.json'):
            prefix = file.split('.json')[0].strip()
            with open('%s/%s' % (qc_dir, file), 'r', encoding='utf-8') as fp:
                json_dat = json.load(fp)
                raw_quality1 = json_dat['read1_before_filtering']['quality_curves']['mean']
                raw_content1 = json_dat['read1_before_filtering']['content_curves']
                raw_quality2 = json_dat['read2_before_filtering']['quality_curves']['mean']
                raw_content2 = json_dat['read2_before_filtering']['content_curves']
                knums = len(raw_quality1)
                bp_r1 = list(range(1, knums+1))
                bp_r2 = list(range(knums+1, knums*2+1))

                raw_q1 = pd.DataFrame(list(zip(bp_r1, raw_quality1)), columns=['reads', 'Q'])
                raw_q2 = pd.DataFrame(list(zip(bp_r2, raw_quality2)), columns=['reads', 'Q'])
                raw_q1['group'] = 'Read1'
                raw_q2['group'] = 'Read2'
                raw_q = pd.concat([raw_q1, raw_q2], axis=0)
                error_rate = np.power(10, -raw_q['Q'].to_numpy() / 10)
                raw_q['error_rate'] = error_rate
                raw_q.to_csv('%s/%s_error_rate.tsv' % (res_dir, prefix), sep='\t', index=False)

                raw_c1 = pd.DataFrame(raw_content1)
                raw_c1['reads'] = bp_r1
                raw_c1['group'] = 'Read1'
                raw_c2 = pd.DataFrame(raw_content2)
                raw_c2['reads'] = bp_r2
                raw_c2['group'] = 'Read2'
                raw_c = pd.concat([raw_c1, raw_c2], axis=0)
                raw_c = raw_c.drop(['GC'], axis=1)
                raw_c.to_csv('%s/%s_content.tsv' % (res_dir, prefix), sep='\t', index=False)
    return 0


def plot_table(cleandatadir, datadir, res_dir, host_dir, host):
    table_dir = os.path.join(cleandatadir, 'table')
    cmd = '''
    {0} {1}/error_rate.R {2} {3} {4}
    {0} {1}/atgc_content.R {2} {3} {4}
    '''.format(Rscript_j, scripts_path, table_dir, datadir, res_dir)
    rc = run_cmd(cmd, "plot_table_phase1")
    if rc != 0:
        return rc

    if host == 'none':
        table_dir = os.path.join(cleandatadir, 'table')
    else:
        table_dir = os.path.join(host_dir, 'table')

    cmd = '''
    {0} {1}/data_composition_bar.R {2} {3} {4} {5}
    '''.format(Rscript_j, scripts_path, table_dir, datadir, res_dir, host)
    return run_cmd(cmd, "plot_table_phase2")


def deHOST(cleandatadir, datadir, host, mapdir, host_dir):
    if host == 'none':
        # 不去宿主，直接返回 0 表示该步骤成功
        return 0
    elif host == 'human':
        host_qcdir = os.path.join(host_dir, 'qc')
        if not os.path.exists(host_qcdir):
            os.makedirs(host_qcdir)
        cmd = '''
        bash {0}/Kneaddata_update.sh {1} {2} {3} {4} 'human_genome/hg37dec_v0.1'
        '''.format(scripts_path, datadir, mapdir, cleandatadir, host_dir)
        return run_cmd(cmd, "deHOST_human")
    elif host == 'mouse':
        host_qcdir = os.path.join(host_dir, 'qc')
        if not os.path.exists(host_qcdir):
            os.makedirs(host_qcdir)
        cmd = '''
        bash {0}/Kneaddata_update.sh {1} {2} {3} {4} 'mouse_C57BL_6NJ/mouse_C57BL_6NJ'
        '''.format(scripts_path, datadir, mapdir, cleandatadir, host_dir)
        return run_cmd(cmd, "deHOST_mouse")
    else:
        host_qcdir = os.path.join(host_dir, 'qc')
        if not os.path.exists(host_qcdir):
            os.makedirs(host_qcdir)
        cmd = '''
        bash {0}/Kneaddata_update.sh {1} {2} {3} {4} {5}/{5}
        '''.format(scripts_path, datadir, mapdir, cleandatadir, host_dir, host)
        return run_cmd(cmd, "deHOST_custom")


def QC_stats(datadir, cleandatadir, res_dir, host, host_dir):
    samples = []
    with open('%s/sample.txt' % datadir, 'r', encoding='utf-8') as f:
        f.readline()
        for line in f.readlines():
            samples.append(line.split('\t')[1].strip())

    df = pd.DataFrame()
    for sample in samples:
        filename = sample + '.json'
        with open('%s/qc/%s' % (cleandatadir, filename), 'r', encoding='utf-8') as f:
            data = json.load(f)
            raw = data['summary']['before_filtering']
            clean = data['summary']['after_filtering']
            raw = pd.DataFrame(raw, index=range(0, 1))
            raw = raw.loc[:, ['total_reads', 'total_bases']]
            raw.columns = ['Raw_reads', 'Raw_bases(G)']
            clean = pd.DataFrame(clean, index=range(0, 1))
            clean = clean.loc[:, ['total_reads', 'total_bases', 'q20_rate', 'q30_rate', 'gc_content']]
            clean.columns = ['Removed_low_quality_Reads', 'Removed_Low_Qualitybases(G)', 'Q20(%)', 'Q30(%)',
                            'GC_content(%)']
            new = pd.DataFrame({'Sample_name': [sample]})
            total = pd.concat([new, raw, clean], axis=1)
            df = df._append(total)
    df['Raw_bases(G)'] = df['Raw_bases(G)'].apply(lambda x: round(x / 10 ** 9, 2))
    df['Removed_Low_Qualitybases(G)'] = df['Removed_Low_Qualitybases(G)'].apply(lambda x: round(x / 10 ** 9, 2))
    df.to_csv('%s/table/sumary.txt' % cleandatadir, sep='\t', index=False)

    if host == 'none':
        df = pd.read_csv('%s/table/sumary.txt' % cleandatadir, sep='\t', dtype={'Sample_name': str})
        sam_gros = pd.read_csv('%s/sample-metadata.tsv' % datadir, sep='\t', skiprows=[1], dtype=str)
        k = sam_gros.shape[1]
        for i in range(1, k):
            sam_gro = sam_gros.iloc[:, [0] + [i]]
            sam_gro = sam_gro.dropna(axis=0).reset_index(drop=True)
            group_num = 'group' + str(i)

            sam_df = pd.merge(left=sam_gro, right=df, left_on='sample-id', right_on='Sample_name', how='inner')
            sam_df = sam_df.drop(['sample-id', group_num], axis=1)
            sam_dir = os.path.join(res_dir, group_num, '1-data_quality')
            if not os.path.exists(sam_dir):
                os.makedirs(sam_dir)
            sam_df.to_excel('%s/data_quality.xlsx' % sam_dir, index=False)
    else:
        if not os.path.exists(os.path.join(host_dir, 'table')):
            os.mkdir(os.path.join(host_dir, 'table'))
        pre_summary = pd.read_csv('%s/table/sumary.txt' % cleandatadir, sep='\t', dtype={'Sample_name': str})
        pre_summary = pre_summary.iloc[:, 0:5]

        df = pd.DataFrame()
        files = os.listdir('%s/qc' % host_dir)
        for file in files:
            if file.endswith('.json'):
                prefix = file.split('.json')[0].strip()
                with open('%s/qc/%s' % (host_dir, file), 'r', encoding='utf-8') as fp:
                    data = json.load(fp)
                    de_host = data['summary']['before_filtering']
                    de_host = pd.DataFrame(de_host, index=range(0, 1))
                    de_host = de_host.loc[:, ['total_reads', 'total_bases', 'q20_rate', 'q30_rate', 'gc_content']]
                    de_host.columns = ['Removed_host_Reads', 'Removed_host_bases(G)', 'Q20(%)', 'Q30(%)',
                                    'GC_content(%)']
                    new = pd.DataFrame({'Sample_name': [prefix]})
                    total = pd.concat([new, de_host], axis=1)
                    df = df._append(total)
        df['Removed_host_bases(G)'] = df['Removed_host_bases(G)'].apply(lambda x: round(x / 10 ** 9, 2))
        df_merge = pd.merge(left=pre_summary, right=df, on='Sample_name')
        df_merge.to_csv('%s/table/sumary.txt' % host_dir, sep='\t', index=False)

        sam_gros = pd.read_csv('%s/sample-metadata.tsv' % datadir, sep='\t', skiprows=[1], dtype=str)
        k = sam_gros.shape[1]
        for i in range(1, k):
            sam_gro = sam_gros.iloc[:, [0] + [i]]
            sam_gro = sam_gro.dropna(axis=0).reset_index(drop=True)
            group_num = 'group' + str(i)

            sam_df = pd.merge(left=sam_gro, right=df_merge, left_on='sample-id', right_on='Sample_name', how='inner')
            sam_df = sam_df.drop(['sample-id', group_num], axis=1)
            sam_dir = os.path.join(res_dir, group_num, '1-data_quality')
            if not os.path.exists(sam_dir):
                os.makedirs(sam_dir)
            sam_df.to_excel('%s/data_quality.xlsx' % sam_dir, index=False)
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='This script will generate clean_data through fastp')
    parser.add_argument('-i', '--i_rawdatadir', type=str, required=True, default='rawdata', help='the dir of raw_data')
    parser.add_argument('-I', '--i_datadir', type=str, required=True, default='data', help='the dir of sample.txt')
    parser.add_argument('--host', type=str, required=True, nargs='*', help='the host of metagenome')
    parser.add_argument('-o', '--output_dir', type=str, default='cleandata', help='the dir of clean_data')
    parser.add_argument('--host_dir', type=str, default='de_host', help='the dir of dehost_data')
    parser.add_argument('--resdir', type=str, default='Result', help='the resdir')
    parser.add_argument('--mapdir', type=str, default='/data/data1/wangli/database/kneaddata_database',
                        help='the dir of kneaddata_database.xlsx')
    args = parser.parse_args()

    rawdatadir = os.path.abspath(args.i_rawdatadir)
    datadir = os.path.abspath(args.i_datadir)
    cleandadir = os.path.abspath(args.output_dir)
    res_dir = os.path.abspath(args.resdir)
    mapdir = os.path.abspath(args.mapdir)
    host_dir = os.path.abspath(args.host_dir)
    host = args.host[0]

    if not os.path.exists(res_dir):
        os.mkdir(res_dir)

    runner = StepRunner()

    # Phase 1: QC（fastp 一次质控）
    # 必须全部完成，才能进入下一阶段
    t1 = runner.run("QC", QC, args=(rawdatadir, datadir, cleandadir))
    t1.join()
    runner.check("QC")

    # Phase 2: deHOST 与 error_rate_table 可并行
    # - deHOST 依赖 QC 生成的 *_clean_*.fastq.gz
    # - error_rate_table 只读取 QC 生成的 json 文件
    t2 = runner.run("deHOST", deHOST, args=(cleandadir, datadir, host, mapdir, host_dir))
    t3 = runner.run("error_rate_table", error_rate_table, args=(cleandadir,))
    t2.join()
    t3.join()
    runner.check("deHOST / error_rate_table")

    # Phase 3: QC_stats（汇总质控统计表）
    t4 = runner.run("QC_stats", QC_stats, args=(datadir, cleandadir, res_dir, host, host_dir))
    t4.join()
    runner.check("QC_stats")

    # Phase 4: plot_table（绘制质控图）
    t5 = runner.run("plot_table", plot_table, args=(cleandadir, datadir, res_dir, host_dir, host))
    t5.join()
    runner.check("plot_table")

    print("[INFO] All steps completed successfully.")


if __name__ == '__main__':
    main()
