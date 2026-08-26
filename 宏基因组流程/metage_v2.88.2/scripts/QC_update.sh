#!/bin/bash
# 并行化修改说明（2026-06-17）：
# 1. 使用 GNU parallel 按样本并行运行 fastp 质控。
# 2. 通过 --halt soon,fail=1 实现：任意一个并行任务失败时立即终止整个流程。
# 3. 脚本使用 set -uo pipefail；关键命令通过显式判断返回码来报错，
#    最终由上层 Python 流程捕获非零退出码并终止后续步骤。
# 4. 当前默认 -j 6（同时跑 6 个样本），每个 fastp 用 --thread 16；
#    若 Docker 分配 CPU 较少，可适当降低 -j 或 fastp 线程数，避免过度超配。
set -uo pipefail

rawdatadir=${1}
datadir=${2}
cleandatadir=${3}

# 创建 qc 目录
mkdir -p ${cleandatadir}/qc
mkdir -p ${cleandatadir}/logs

# 定义处理单个样本的函数
process_sample() {
    local fqn=$1
    local sample=$2
    local rc=0

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Processing: ${fqn} -> ${sample}"

    # 创建软链接（R1）
    for suffix in "_1.fq.gz" "_R1.fq.gz" ".1.fq.gz" ".1.fastq.gz" "_1.fastq.gz" "_R1.fastq.gz" ".R1.raw.fastq.gz" ".R1.raw.fq.gz" ".R1.fq.gz" "_R1_001.fastq.gz"; do
        if [ -e "${rawdatadir}/${fqn}${suffix}" ]; then
            ln -sf "${rawdatadir}/${fqn}${suffix}" "${fqn}_1.fastq.gz"
            break
        fi
    done

    # 创建软链接（R2）
    for suffix in "_2.fq.gz" "_R2.fq.gz" ".2.fq.gz" ".2.fastq.gz" "_2.fastq.gz" "_R2.fastq.gz" ".R2.raw.fastq.gz" ".R2.raw.fq.gz" ".R2.fq.gz" "_R2_001.fastq.gz"; do
        if [ -e "${rawdatadir}/${fqn}${suffix}" ]; then
            ln -sf "${rawdatadir}/${fqn}${suffix}" "${fqn}_2.fastq.gz"
            break
        fi
    done

    # fastp 质控
    fastp -3 -5 -W 4 -M 20 -l 100 --thread 16 \
        -i ${fqn}_1.fastq.gz -I ${fqn}_2.fastq.gz \
        -o ${cleandatadir}/${sample}_clean_1.fastq.gz \
        -O ${cleandatadir}/${sample}_clean_2.fastq.gz \
        -h ${cleandatadir}/qc/${sample}.html \
        -j ${cleandatadir}/qc/${sample}.json \
        > ${cleandatadir}/logs/${sample}.log 2>&1 || rc=$?

    # 清理软链接
    rm -f ${fqn}_1.fastq.gz ${fqn}_2.fastq.gz

    if [ ${rc} -ne 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: fastp failed for ${sample}, see ${cleandatadir}/logs/${sample}.log" >&2
        return ${rc}
    fi

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Finished: ${sample}"
}
export -f process_sample
export rawdatadir cleandatadir

# 提取所有样本信息（跳过表头）
echo "Starting parallel QC with parallel..."

# 按行读取 sample.txt，用制表符分隔两列传给 parallel
# --halt soon,fail=1：只要有一个样本失败，立即终止其余并行任务并返回非零退出码
if ! awk 'NR!=1 {print $1"\t"$2}' "${datadir}/sample.txt" | \
    parallel -j 6 --halt soon,fail=1 --colsep '\t' --bar process_sample {1} {2}; then
    echo "[ERROR] QC parallel processing failed. Please check logs in ${cleandatadir}/logs/" >&2
    exit 1
fi

echo '------------clean data finish!------------'
