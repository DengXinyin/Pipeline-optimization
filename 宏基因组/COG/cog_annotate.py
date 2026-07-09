#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cog_annotate.py
根据 DIAMOND 比对结果和 NCBI COG2024 定义文件，将基因映射到 COG 功能类别。

用法：
    python cog_annotate.py <diamond.m8> <cog-24.def.tab> <cog-24.fun.tab> <output.tsv>

输入：
    - diamond.m8: DIAMOND blastp 输出（outfmt 6，包含 stitle 列）
    - cog-24.def.tab: COG 定义文件
    - cog-24.fun.tab: COG 功能类别描述文件

输出：
    - output.tsv: 基因 → COG 功能类别注释表
"""

import sys
import pandas as pd


def load_cog_definition(def_file):
    """读取 COG 定义：COG ID -> (功能类别字母, COG名称)"""
    cog_dict = {}
    with open(def_file, 'r') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 3:
                cog_id = parts[0]
                func_cat = parts[1]
                cog_name = parts[2]
                cog_dict[cog_id] = (func_cat, cog_name)
    return cog_dict


def load_cog_function(fun_file):
    """读取 COG 功能类别：字母 -> (功能组, 功能描述)"""
    fun_dict = {}
    with open(fun_file, 'r') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 4:
                letter = parts[0]
                group = parts[1]
                desc = parts[3]
                fun_dict[letter] = (group, desc)
    return fun_dict


def annotate(diamond_file, cog_dict, fun_dict, output_file):
    """根据 DIAMOND 结果注释每个基因的 COG 类别"""
    # 读取 m8 格式：qseqid sseqid ... stitle
    cols = [
        'qseqid', 'sseqid', 'pident', 'length', 'mismatch',
        'gapopen', 'qstart', 'qend', 'sstart', 'send',
        'evalue', 'bitscore', 'stitle'
    ]
    df = pd.read_csv(diamond_file, sep='\t', header=None, names=cols)

    # 从 sseqid 提取 COG ID（如 COG0001）
    df['cog_id'] = df['sseqid'].str.extract(r'(COG\d+)')

    # 映射 COG 定义
    df['cog_func_letters'] = df['cog_id'].map(
        lambda x: cog_dict.get(x, ('', ''))[0]
    )
    df['cog_name'] = df['cog_id'].map(
        lambda x: cog_dict.get(x, ('', ''))[1]
    )

    # 取第一个功能字母对应的功能描述
    df['cog_func_desc'] = df['cog_func_letters'].map(
        lambda x: fun_dict.get(x[0], ('', ''))[1] if x else ''
    )

    # 保存结果
    out_df = df[[
        'qseqid', 'cog_id', 'cog_func_letters',
        'cog_func_desc', 'cog_name', 'evalue', 'bitscore'
    ]]
    out_df.to_csv(output_file, sep='\t', index=False)
    print(f'已保存注释结果：{output_file}')


if __name__ == '__main__':
    if len(sys.argv) != 5:
        print('用法：python cog_annotate.py <diamond.m8> <cog-24.def.tab> <cog-24.fun.tab> <output.tsv>')
        sys.exit(1)

    diamond_file = sys.argv[1]
    def_file = sys.argv[2]
    fun_file = sys.argv[3]
    output_file = sys.argv[4]

    cog_dict = load_cog_definition(def_file)
    fun_dict = load_cog_function(fun_file)
    annotate(diamond_file, cog_dict, fun_dict, output_file)
