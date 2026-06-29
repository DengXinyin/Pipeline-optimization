#!/bin/bash
# 并行化修改说明（2026-06-17）：
# 1. 使用 GNU parallel 按样本并行运行 megahit 组装。
# 2. 修复 sample.txt 解析：用 awk 直接取第 2 列，兼容制表符分隔。
# 3. parallel 增加 --halt soon,fail=1，任意一个样本组装失败立即终止其余任务。
# 4. 脚本使用 set -uo pipefail；关键命令通过显式判断返回码来报错。
# 5. 当前默认 -j 7（同时跑 7 个样本），每个 megahit 用 -t 12；
#    请根据实际 CPU 资源调整 -j 和 -t，避免过度超配。
set -uo pipefail

datadir=${1}
cle_hodir=${2}
tmpdir=${3}
type=${4}

# 创建输出子目录
mkdir -p ${tmpdir}/length

# 生成 parallel 输入文件
awk 'NR!=1 {print $2}' "${datadir}/sample.txt" | while read sample; do
    sample=$(echo "${sample}" | tr -d '\n\r')
    if [ -z "${sample}" ]; then
        continue
    fi
    if [ "${type}" = 'none' ]; then
        echo "${cle_hodir}/${sample}_clean_1.fastq.gz" >> ${tmpdir}/sample1.txt
        echo "${cle_hodir}/${sample}_clean_2.fastq.gz" >> ${tmpdir}/sample2.txt
    else
        echo "${cle_hodir}/${sample}_dehost_1.fastq.gz" >> ${tmpdir}/sample1.txt
        echo "${cle_hodir}/${sample}_dehost_2.fastq.gz" >> ${tmpdir}/sample2.txt
    fi
    echo "${tmpdir}/${sample}" >> ${tmpdir}/sample.name.txt
done

# 检查是否生成了输入列表
if [ ! -s "${tmpdir}/sample1.txt" ]; then
    echo "[ERROR] No sample input files generated. Please check ${datadir}/sample.txt" >&2
    exit 1
fi

# 并行运行 megahit
# --halt soon,fail=1：任意一个样本失败立即终止其余并行任务
echo "Starting parallel megahit assembly..."
if ! parallel --verbose -j 7 --halt soon,fail=1 --memfree 30G --xapply \
    'megahit -t 12 -1 {1} -2 {2} -o {3}' \
    :::: ${tmpdir}/sample1.txt :::: ${tmpdir}/sample2.txt :::: ${tmpdir}/sample.name.txt; then
    echo "[ERROR] megahit parallel assembly failed. Check outputs in ${tmpdir}/" >&2
    exit 1
fi

# 后处理：过滤 contigs、重命名、统计
awk 'NR!=1 {print $2}' "${datadir}/sample.txt" | while read sample; do
    sample=$(echo "${sample}" | tr -d '\n\r')
    if [ -z "${sample}" ]; then
        continue
    fi
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Post-processing: ${sample}"
    seqkit seq -m 500 ${tmpdir}/${sample}/final.contigs.fa > ${tmpdir}/${sample}/final.contigs.fa.tmp
    awk -v sample="${sample}" '$0 ~ /^>/ {count++; $0=">seq_" sample "." count}1' ${tmpdir}/${sample}/final.contigs.fa.tmp > ${tmpdir}/${sample}/final.contigs.fa
    seqkit fx2tab -j 36 -l -n -i -H ${tmpdir}/${sample}/final.contigs.fa > ${tmpdir}/length/${sample}_length.txt
    assembly-stats -t ${tmpdir}/${sample}/final.contigs.fa > ${tmpdir}/length/${sample}_stats.txt
done

echo '------------megahit finish!------------'
