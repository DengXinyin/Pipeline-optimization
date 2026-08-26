#!/usr/bin/env python
# -*- coding: utf-8 -*-

import scipy.stats as stats
import pandas as pd
from statsmodels.stats import multitest
from statsmodels.stats.multicomp import pairwise_tukeyhsd
import scikit_posthocs as sp
from joblib import Parallel, delayed
# =====================================================
# 单个 feature 做 Tukey（并行调用）
# =====================================================
def tukey_one_feature(genus, tax_dat, sam_gro, taxname, group_num):
    """
    genus     : 单个物种/代谢物名称
    tax_dat   : 丰度矩阵（第一列为名称，其余列为样本）
    sam_gro   : 分组表
    taxname   : 第一列列名
    group_num : 分组列名
    """

    try:
        row = tax_dat[tax_dat[taxname] == genus].iloc[0]

        tmp = pd.DataFrame({
            "sample-id": row.index[1:],
            "abundance": row.values[1:]
        })

        tmp = tmp.merge(sam_gro, on="sample-id")

        tmp["abundance"] = pd.to_numeric(tmp["abundance"], errors="coerce")

        tmp = tmp.dropna()

        # 至少2组
        if tmp[group_num].nunique() < 2:
            return None

        tukey = pairwise_tukeyhsd(
            endog=tmp["abundance"],
            groups=tmp[group_num],
            alpha=0.05
        )

        res = pd.DataFrame(
            tukey._results_table.data[1:],
            columns=tukey._results_table.data[0]
        )

        res[taxname] = genus

        res = res[[taxname, "group1", "group2", "p-adj"]]

        return res

    except:
        return None


# =====================================================
# 主函数：高速 ANOVA + Tukey
# =====================================================
def anova(tax_dat, sam_gro, group_num, n_jobs=-1):
    """
    tax_dat:
        第一列为 feature 名称
        后面列为 sample abundance

    sam_gro:
        必须包含：
        sample-id
        group_num（分组列）

    group_num:
        分组列名

    n_jobs:
        并行线程数
        -1 = 全核
    """

    try:
        tax_dat = tax_dat.copy()

        # ----------------------------------
        # 去掉全空列
        # ----------------------------------
        tax_dat = tax_dat.dropna(axis=1, how="all")

        taxname = tax_dat.columns[0]

        sample_cols = tax_dat.columns[1:]

        # ----------------------------------
        # 样本列转数字
        # ----------------------------------
        tax_dat[sample_cols] = tax_dat[sample_cols].apply(
            pd.to_numeric,
            errors="coerce"
        )

        # ----------------------------------
        # 去掉全零行 / 常数行
        # ----------------------------------
        tax_dat = tax_dat.loc[
            tax_dat[sample_cols].std(axis=1, skipna=True) > 0
        ].reset_index(drop=True)

        if tax_dat.empty:
            return None

        # ----------------------------------
        # 分组信息
        # ----------------------------------
        k = sam_gro[group_num].nunique()

        n = sam_gro[group_num].value_counts().min()

        if k <= 1 or n <= 1:
            return None

        # ----------------------------------
        # 构建 group 字典
        # ----------------------------------
        group_dic = pd.Series(
            sam_gro[group_num].values,
            index=sam_gro["sample-id"]
        ).to_dict()

        # ----------------------------------
        # 按组拆矩阵（矢量化）
        # ----------------------------------
        groups_array = []

        for name, cols in pd.Series(sample_cols).groupby(
            pd.Series(sample_cols).map(group_dic)
        ):
            mat = tax_dat[cols.values].to_numpy(dtype=float)
            groups_array.append(mat)

        # ----------------------------------
        # 批量 ANOVA（极快）
        # ----------------------------------
        F_statistic, pVal = stats.f_oneway(*groups_array, axis=1)

        padj = multitest.fdrcorrection(pVal)[1]

        # ----------------------------------
        # 拼接结果
        # ----------------------------------
        tax_dat_p = tax_dat.copy()

        tax_dat_p["F_value"] = F_statistic
        tax_dat_p["p_value"] = pVal
        tax_dat_p["padj"] = padj

        tax_dat_sign_pvalue = tax_dat_p[
            tax_dat_p["p_value"] < 0.05
        ].reset_index(drop=True)

        # =================================================
        # Tukey（仅显著 feature）
        # =================================================
        tukey_results_df = None

        if k > 2 and not tax_dat_sign_pvalue.empty:

            sig_taxa = tax_dat_sign_pvalue[taxname].tolist()

            tukey_list = Parallel(n_jobs=n_jobs)(
                delayed(tukey_one_feature)(
                    genus,
                    tax_dat,
                    sam_gro,
                    taxname,
                    group_num
                )
                for genus in sig_taxa
            )

            tukey_list = [x for x in tukey_list if x is not None]

            if len(tukey_list) > 0:
                tukey_results_df = pd.concat(
                    tukey_list,
                    ignore_index=True
                )

        return tax_dat_p, tax_dat_sign_pvalue, tukey_results_df
    except Exception as e:
        print(f"[diff_method.anova warning] anova failed for group {group_num}: {e}")
        return None


def dunn_one_feature(genus, tax_dat, sam_gro, taxname, group_num):
    try:
        row = tax_dat[tax_dat[taxname] == genus].iloc[0]

        tmp = pd.DataFrame({
            "sample-id": row.index[1:],
            "abundance": row.values[1:]
        })

        tmp = tmp.merge(sam_gro, on="sample-id")

        tmp["abundance"] = pd.to_numeric(
            tmp["abundance"],
            errors="coerce"
        )

        tmp = tmp.dropna()

        # 至少两组
        if tmp[group_num].nunique() < 2:
            return None

        dunn = sp.posthoc_dunn(
            tmp,
            val_col="abundance",
            group_col=group_num,
            p_adjust="fdr_bh"
        )

        dunn = dunn.reset_index()
        dunn = dunn.rename(columns={"index": "group1"})

        dunn = dunn.melt(
            id_vars="group1",
            var_name="group2",
            value_name="p-adj"
        )

        dunn[taxname] = genus

        dunn = dunn[[taxname, "group1", "group2", "p-adj"]]

        return dunn

    except:
        return None


# =====================================================
# 主函数：高速 Wilcoxon / Kruskal + Dunn
# =====================================================
def kw_wilcoxon(tax_dat, sam_gro, group_num, n_jobs=-1):

    try:
        tax_dat = tax_dat.copy()

        # ----------------------------------
        # 去空列
        # ----------------------------------
        tax_dat = tax_dat.dropna(axis=1, how="all")

        taxname = tax_dat.columns[0]

        sample_cols = tax_dat.columns[1:]

        # ----------------------------------
        # 转数字
        # ----------------------------------
        tax_dat[sample_cols] = tax_dat[sample_cols].apply(
            pd.to_numeric,
            errors="coerce"
        )

        # ----------------------------------
        # 去常数行
        # ----------------------------------
        tax_dat = tax_dat.loc[
            tax_dat[sample_cols].std(axis=1, skipna=True) > 0
        ].reset_index(drop=True)

        if tax_dat.empty:
            return None

        # ----------------------------------
        # 组信息
        # ----------------------------------
        k = sam_gro[group_num].nunique()
        n = sam_gro[group_num].value_counts().min()

        if k <= 1 or n <= 1:
            return None

        # ----------------------------------
        # group 字典
        # ----------------------------------
        group_dic = pd.Series(
            sam_gro[group_num].values,
            index=sam_gro["sample-id"]
        ).to_dict()

        # ----------------------------------
        # 分组矩阵
        # ----------------------------------
        groups_array = []

        for name, cols in pd.Series(sample_cols).groupby(
            pd.Series(sample_cols).map(group_dic)
        ):
            mat = tax_dat[cols.values].to_numpy(dtype=float)
            groups_array.append(mat)

        # =====================================================
        # 两组：Wilcoxon rank-sum
        # =====================================================
        if k == 2:

            statistic, pVal = stats.ranksums(
                groups_array[0],
                groups_array[1],
                axis=1
            )

            padj = multitest.fdrcorrection(pVal)[1]

            tax_dat_p = tax_dat.copy()
            tax_dat_p["statistic"] = statistic
            tax_dat_p["p_value"] = pVal
            tax_dat_p["padj"] = padj

            tax_dat_sign = tax_dat_p[
                tax_dat_p["p_value"] < 0.05
            ].reset_index(drop=True)

            return tax_dat_p, tax_dat_sign, None

        # =====================================================
        # 多组：Kruskal-Wallis
        # =====================================================
        elif k > 2:

            H_statistic, pVal = stats.kruskal(
                *groups_array,
                axis=1
            )

            padj = multitest.fdrcorrection(pVal)[1]

            tax_dat_p = tax_dat.copy()
            tax_dat_p["statistic"] = H_statistic
            tax_dat_p["p_value"] = pVal
            tax_dat_p["padj"] = padj

            tax_dat_sign = tax_dat_p[
                tax_dat_p["p_value"] < 0.05
            ].reset_index(drop=True)

            # ==========================================
            # Dunn（仅显著行）
            # ==========================================
            dunn_results = None

            if not tax_dat_sign.empty:

                sig_taxa = tax_dat_sign[taxname].tolist()

                dunn_list = Parallel(n_jobs=n_jobs)(
                    delayed(dunn_one_feature)(
                        genus,
                        tax_dat,
                        sam_gro,
                        taxname,
                        group_num
                    )
                    for genus in sig_taxa
                )

                dunn_list = [
                    x for x in dunn_list
                    if x is not None
                ]

                if len(dunn_list) > 0:
                    dunn_results = pd.concat(
                        dunn_list,
                        ignore_index=True
                    )

            return tax_dat_p, tax_dat_sign, dunn_results
    except Exception as e:
        print(f"[diff_method.kw_wilcoxon warning] kw_wilcoxon failed for group {group_num}: {e}")
        return None
