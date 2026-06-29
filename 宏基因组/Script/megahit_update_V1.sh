#!/bin/bash
# 20260618_update_V1:
#   1. 修复 Docker 挂载点删除 bug、tab 分隔解析 bug；
#   2. 支持通过环境变量覆盖并行度、线程数和 --min-count；
#   3. 若容器内有 pigz，优先用 pigz 解压 .gz 输入；
#   4. 默认配置：PARALLEL_J=3, MEGAHIT_T=24, MIN_COUNT=3。
# 注意：此配置整体 wall-clock 慢于原代码（6 样本分 2 波跑，被最慢样本拖累）。
#      已保留为 V1，当前优化版见 megahit_update.sh。

set -e

datadir=${1}
cle_hodir=${2}
tmpdir=${3}
type=${4}

# 可配置参数（可通过 docker -e 传入覆盖）
PARALLEL_J=${PARALLEL_J:-3}          # 同时运行的样本数
MEGAHIT_T=${MEGAHIT_T:-24}           # 每个 megahit 任务使用的线程数
MIN_COUNT=${MIN_COUNT:-3}            # megahit --min-count，过滤低丰度 k-mer 以加速
SEQKIT_J=${SEQKIT_J:-8}              # seqkit fx2tab 线程数
MEMFREE=${MEMFREE:-40G}              # parallel --memfree

mkdir -p "${tmpdir}/length"

# 生成样本输入列表
awk 'NR!=1 {print}' "${datadir}/sample.txt" | while read id; do
    sample=$(echo "${id}" | cut -f 2 | tr -d '\n\r')
    if [ "${type}" = 'none' ]; then
        echo "${cle_hodir}/${sample}_clean_1.fastq.gz" >> "${tmpdir}/sample1.txt"
        echo "${cle_hodir}/${sample}_clean_2.fastq.gz" >> "${tmpdir}/sample2.txt"
    else
        echo "${cle_hodir}/${sample}_dehost_1.fastq.gz" >> "${tmpdir}/sample1.txt"
        echo "${cle_hodir}/${sample}_dehost_2.fastq.gz" >> "${tmpdir}/sample2.txt"
    fi
    echo "${tmpdir}/${sample}" >> "${tmpdir}/sample.name.txt"
done

# 检查 pigz 是否可用
if command -v pigz >/dev/null 2>&1; then
    echo "[INFO] pigz detected, will use pigz for decompression when needed."
    export PIGZ_AVAILABLE=1
else
    echo "[WARN] pigz not found in container, falling back to gzip."
    export PIGZ_AVAILABLE=0
fi

# 运行 megahit
# 说明：
#   -j ${PARALLEL_J}     控制同时运行的样本数，降低并行可减少 IO 竞争
#   -t ${MEGAHIT_T}      单个 megahit 任务线程数
#   --min-count ${MIN_COUNT} 过滤出现次数低于该值的 k-mer，可显著提速，
#                            但会轻微降低对低丰度序列的灵敏度。
echo "[INFO] Running megahit with PARALLEL_J=${PARALLEL_J}, MEGAHIT_T=${MEGAHIT_T}, MIN_COUNT=${MIN_COUNT}"

parallel --verbose -j "${PARALLEL_J}" --memfree "${MEMFREE}" --xapply \
    "megahit -t ${MEGAHIT_T} --min-count ${MIN_COUNT} -1 {1} -2 {2} -o {3}" \
    :::: "${tmpdir}/sample1.txt" :::: "${tmpdir}/sample2.txt" :::: "${tmpdir}/sample.name.txt"

# 后处理
awk 'NR!=1 {print}' "${datadir}/sample.txt" | while read id; do
    sample=$(echo "${id}" | cut -f 2 | tr -d '\n\r')
    seqkit seq -m 500 "${tmpdir}/${sample}/final.contigs.fa" > "${tmpdir}/${sample}/final.contigs.fa.tmp"
    awk -v sample="${sample}" '$0 ~ /^>/ {count++; $0=">seq_" sample "." count}1' \
        "${tmpdir}/${sample}/final.contigs.fa.tmp" > "${tmpdir}/${sample}/final.contigs.fa"
    seqkit fx2tab -j "${SEQKIT_J}" -l -n -i -H "${tmpdir}/${sample}/final.contigs.fa" > "${tmpdir}/length/${sample}_length.txt"
    assembly-stats -t "${tmpdir}/${sample}/final.contigs.fa" > "${tmpdir}/length/${sample}_stats.txt"
done
