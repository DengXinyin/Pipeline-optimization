#!/bin/bash
# 20260624_update:
#   在上一个优化版（megahit_update_V1.sh）基础上，修正并行策略：
#   - 恢复为 6 个样本同时并行，每个样本 12 线程，与原代码一致；
#   - 默认不添加 --min-count，保证输出与原代码可比；
#   - 保留 V1 的 bug 修复：挂载点保护、tab 分隔解析、失败即停。
#   - 删除未生效的 pigz 检测；通过管道合并 seqkit seq 与 awk，减少中间 .tmp 文件。

set -euo pipefail

datadir=${1}
cle_hodir=${2}
tmpdir=${3}
type=${4}

# 可配置参数（可通过 docker -e 传入覆盖）
PARALLEL_J=${PARALLEL_J:-6}          # 同时运行的样本数，默认 6（与原代码一致）
MEGAHIT_T=${MEGAHIT_T:-12}           # 每个 megahit 任务使用的线程数，默认 12（与原代码一致）
SEQKIT_J=${SEQKIT_J:-36}             # 原代码 seqkit fx2tab 线程数，默认 36（顺序后处理时使用）
SEQKIT_POST_J=${SEQKIT_POST_J:-2}    # 并行后处理时每个 seqkit fx2tab 使用的线程数，避免并发过多线程
POST_J=${POST_J:-6}                  # 后处理并行样本数，默认 6
MEMFREE=${MEMFREE:-30G}              # parallel --memfree，默认 30G（与原代码一致）
# MIN_COUNT: 默认空，即不传入 --min-count；如需启用可设 MIN_COUNT=3
MIN_COUNT=${MIN_COUNT:-}

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

# 构造 --min-count 参数（默认不传，保持与原代码一致）
if [ -n "${MIN_COUNT}" ]; then
    MIN_COUNT_ARG="--min-count ${MIN_COUNT}"
else
    MIN_COUNT_ARG=""
fi

# 运行 megahit
# 说明：
#   -j ${PARALLEL_J}     控制同时运行的样本数，默认 6，确保 6 样本×12 线程 = 72 线程满载
#   -t ${MEGAHIT_T}      单个 megahit 任务线程数，默认 12
#   默认不传入 --min-count，保证与原代码结果可比

echo "[INFO] Running megahit with PARALLEL_J=${PARALLEL_J}, MEGAHIT_T=${MEGAHIT_T}, MIN_COUNT_ARG='${MIN_COUNT_ARG}', MEMFREE=${MEMFREE}"

parallel --verbose -j "${PARALLEL_J}" --memfree "${MEMFREE}" --xapply \
    "megahit -t ${MEGAHIT_T} ${MIN_COUNT_ARG} -1 {1} -2 {2} -o {3}" \
    :::: "${tmpdir}/sample1.txt" :::: "${tmpdir}/sample2.txt" :::: "${tmpdir}/sample.name.txt"

# 后处理：过滤长度、重命名序列、生成长度表和统计表
# 1. 使用管道将 seqkit seq 的输出直接传给 awk，避免生成 .tmp 中间文件
# 2. 使用 GNU parallel 对 6 个样本的后处理并行执行，缩短整体 wall-clock

postprocess() {
    set -euo pipefail
    local sample="$1"
    seqkit seq -m 500 "${tmpdir}/${sample}/final.contigs.fa" | \
        awk -v sample="${sample}" '$0 ~ /^>/ {count++; $0=">seq_" sample "." count}1' \
        > "${tmpdir}/${sample}/final.contigs.fa"
    seqkit fx2tab -j "${SEQKIT_POST_J}" -l -n -i -H "${tmpdir}/${sample}/final.contigs.fa" > "${tmpdir}/length/${sample}_length.txt"
    assembly-stats -t "${tmpdir}/${sample}/final.contigs.fa" > "${tmpdir}/length/${sample}_stats.txt"
}
export -f postprocess
export tmpdir SEQKIT_POST_J

awk 'NR!=1 {print $2}' "${datadir}/sample.txt" | tr -d '\r' | \
    parallel -j "${POST_J}" --verbose postprocess {}
