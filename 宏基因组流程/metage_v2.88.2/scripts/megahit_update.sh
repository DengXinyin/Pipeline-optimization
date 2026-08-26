#!/bin/bash
# v2.88 compatibility mode:
#   - 组装参数、样本并行数以及 contig 后处理均与 v2.87 保持一致；
#   - 仅保留输入解析、失败即停等健壮性处理；
#   - 增量流程的 sample_double_check 在 WDL task 中执行，不在本脚本中改变结果文件。

set -euo pipefail

datadir=${1}
cle_hodir=${2}
tmpdir=${3}
type=${4}

# 与 v2.87 的 MEGAHIT 参数保持一致。
PARALLEL_J=${PARALLEL_J:-7}
MEGAHIT_T=${MEGAHIT_T:-12}
SEQKIT_J=${SEQKIT_J:-36}
MEMFREE=${MEMFREE:-30G}

mkdir -p "${tmpdir}/length"

# 生成样本输入列表
awk 'NR!=1 {print}' "${datadir}/sample.txt" | while read id; do
    sample=$(echo "${id}" | awk '{print $2}' | tr -d '\n\r')
    if [ "${type}" = 'none' ]; then
        echo "${cle_hodir}/${sample}_clean_1.fastq.gz" >> "${tmpdir}/sample1.txt"
        echo "${cle_hodir}/${sample}_clean_2.fastq.gz" >> "${tmpdir}/sample2.txt"
    else
        echo "${cle_hodir}/${sample}_dehost_1.fastq.gz" >> "${tmpdir}/sample1.txt"
        echo "${cle_hodir}/${sample}_dehost_2.fastq.gz" >> "${tmpdir}/sample2.txt"
    fi
    echo "${tmpdir}/${sample}" >> "${tmpdir}/sample.name.txt"
done

# 运行参数与 v2.87 完全一致：7 个样本并行，每样本 12 线程，
# 不传 --min-count。
echo "[INFO] Running v2.87-compatible megahit: PARALLEL_J=${PARALLEL_J}, MEGAHIT_T=${MEGAHIT_T}, MEMFREE=${MEMFREE}"

parallel --verbose -j "${PARALLEL_J}" --memfree "${MEMFREE}" --xapply \
    "megahit -t ${MEGAHIT_T} -1 {1} -2 {2} -o {3}" \
    :::: "${tmpdir}/sample1.txt" :::: "${tmpdir}/sample2.txt" :::: "${tmpdir}/sample.name.txt"

# 后处理顺序、最小 contig 长度和 seqkit 线程数均与 v2.87 一致。
awk 'NR!=1 {print}' "${datadir}/sample.txt" | while read -r id; do
    sample=$(echo "${id}" | awk '{print $2}' | tr -d '\n\r')
    seqkit seq -m 500 "${tmpdir}/${sample}/final.contigs.fa" > "${tmpdir}/${sample}/final.contigs.fa.tmp"
    awk -v sample="${sample}" '$0 ~ /^>/ {count++; $0=">seq_" sample "." count}1' \
        "${tmpdir}/${sample}/final.contigs.fa.tmp" > "${tmpdir}/${sample}/final.contigs.fa"
    seqkit fx2tab -j "${SEQKIT_J}" -l -n -i -H "${tmpdir}/${sample}/final.contigs.fa" > "${tmpdir}/length/${sample}_length.txt"
    assembly-stats -t "${tmpdir}/${sample}/final.contigs.fa" > "${tmpdir}/length/${sample}_stats.txt"
done
